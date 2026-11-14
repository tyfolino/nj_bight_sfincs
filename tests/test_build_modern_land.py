"""``scripts/build_modern_land.py`` ``--bed`` / ``--out`` (2026-11-14, Model 2.0's 2026 bed).

The modern land overlay judges every survey pixel against a CURRENT bed (land lidar is refused
over today's water). 1.x's bed and output dir were module constants; Model 2.0 needs the same
build against its own mesh's 2012 bed, written somewhere that does not overwrite 1.x's raster.
Pinned here, on a synthetic 2-source case with a ROTATED bed (as every subgrid raster is):

* the defaults still mean ``BED`` / ``OUT`` — no flags reproduces the old call byte for byte,
  and ``--bed BED --out OUT`` written elsewhere gives the same bytes;
* ``--bed`` really is the bed the blocks read (a bed with water where the other has land
  refuses the land lidar there), also through the process pool, which on Python 3.14
  re-imports the module in each worker (so a module global could not carry it).
"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_modern_land as bml  # noqa: E402

CRS = "EPSG:32618"
X0, Y0 = 500_000.0, 4_400_000.0  # top-left of the survey tiles
N = 120  # survey tiles: N x N px at 1 m


def _tif(path, arr, transform, nodata=-9999.0):
    with rasterio.open(
        path, "w", driver="GTiff", width=arr.shape[1], height=arr.shape[0], count=1,
        dtype="float32", crs=CRS, transform=transform, nodata=nodata,
    ) as d:  # fmt: skip
        d.write(arr.astype("float32"), 1)


def _bed(path, water_west: bool):
    """A ROTATED 2 m bed over the tiles: land (+2 m), or water (-3 m) on the west half."""
    t = (
        Affine.translation(X0 - 20, Y0 + 20)
        * Affine.rotation(-0.8)
        * Affine.scale(2.0, -2.0)
    )
    z = np.full((90, 90), 2.0, "float32")
    if water_west:
        z[:, :45] = -3.0
    _tif(path, z, t)


@unittest.skipUnless(shutil.which("gdalbuildvrt"), "gdalbuildvrt not on PATH")
class TestBedOut(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bml_"))
        raw = self.tmp / "raw"
        (raw / "lidar").mkdir(parents=True)
        (raw / "topo").mkdir(parents=True)
        t = Affine(1.0, 0, X0, 0, -1.0, Y0)
        yy, xx = np.mgrid[0:N, 0:N]
        _tif(raw / "lidar/a.tif", 1.0 + 0.01 * xx, t)  # land lidar, metres
        topo = (0.5 + 0.02 * yy) / bml.FT  # topobathy in US survey feet
        topo[:, : N // 3] = -9999.0
        _tif(raw / "topo/b.tif", topo, t)
        self.sources = [
            ("lidar_a", 2024, str(raw / "lidar/*.tif"), 1.0, False),
            ("topo_b", 2017, str(raw / "topo/*.tif"), bml.FT, True),
        ]
        self.bed_land = self.tmp / "bed_land.tif"
        self.bed_water = self.tmp / "bed_water.tif"
        _bed(self.bed_land, False)
        _bed(self.bed_water, True)
        self._saved = (bml.BED, bml.OUT, bml.SOURCES)
        bml.BED, bml.OUT, bml.SOURCES = (
            self.bed_land,
            self.tmp / "default_out",
            self.sources,
        )

    def tearDown(self):
        bml.BED, bml.OUT, bml.SOURCES = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, tag, *extra, workers=1):
        rc = bml.main(
            [
                "--workers",
                str(workers),
                "--report",
                str(self.tmp / f"rep_{tag}"),
                *extra,
            ]
        )
        self.assertEqual(rc, 0)

    @staticmethod
    def _bytes(d):
        return {
            n: (Path(d) / n).read_bytes()
            for n in ("modern_land_2026.tif", "modern_land_2026_source.tif")
        }

    def test_defaults_are_the_module_constants(self):
        ap_defaults = {}
        orig = bml.argparse.ArgumentParser.parse_args

        def spy(parser, argv=None, namespace=None):
            ns = orig(parser, argv, namespace)
            ap_defaults.update(vars(ns))
            raise SystemExit(0)

        bml.argparse.ArgumentParser.parse_args = spy
        try:
            with self.assertRaises(SystemExit):
                bml.main(["--report", str(self.tmp / "r")])
        finally:
            bml.argparse.ArgumentParser.parse_args = orig
        self.assertEqual(ap_defaults["bed"], bml.BED)
        self.assertEqual(ap_defaults["out"], bml.OUT)

    def test_no_flags_equals_explicit_flags(self):
        self._run("default")
        other = self.tmp / "explicit_out"
        self._run("explicit", "--bed", str(self.bed_land), "--out", str(other))
        a, b = self._bytes(bml.OUT), self._bytes(other)
        for n in a:
            self.assertEqual(a[n], b[n], n)
        ja = json.loads((self.tmp / "rep_default/modern_land_sources.json").read_text())
        jb = json.loads(
            (self.tmp / "rep_explicit/modern_land_sources.json").read_text()
        )
        self.assertEqual(ja, jb)
        self.assertTrue((other / "vrt" / "lidar_a.vrt").exists())
        self.assertGreater(sum(r["taken_km2"] for r in ja), 0)

    def test_bed_is_the_one_the_blocks_read(self):
        # through the pool too: workers re-import the module, so --bed must travel in the job
        self._run("land", "--out", str(self.tmp / "o_land"), workers=2)
        self._run(
            "water",
            "--bed",
            str(self.bed_water),
            "--out",
            str(self.tmp / "o_water"),
            workers=2,
        )
        with rasterio.open(self.tmp / "o_land/modern_land_2026_source.tif") as d:
            s_land, T = d.read(1), d.transform
        with rasterio.open(self.tmp / "o_water/modern_land_2026_source.tif") as d:
            s_water = d.read(1)
            self.assertEqual(d.transform, T)
        # a pixel well inside the tiles' west third: only the land lidar covers it
        col, row = ~T * (X0 + 15, Y0 - 60)
        r, c = int(row), int(col)
        self.assertEqual(s_land[r, c], 1)  # land bed: lidar taken
        self.assertEqual(
            s_water[r, c], 0
        )  # water bed: land lidar refused, no topobathy there
        # east half: land in both beds, identical
        col, row = ~T * (X0 + 100, Y0 - 60)
        self.assertEqual(s_land[int(row), int(col)], s_water[int(row), int(col)])
        rep = json.loads((self.tmp / "rep_water/modern_land_sources.json").read_text())
        self.assertGreater(rep[0]["refused_km2"], 0)

    def test_missing_bed_refused(self):
        with self.assertRaises(SystemExit):
            bml.main(
                ["--report", str(self.tmp / "r"), "--bed", str(self.tmp / "nope.tif")]
            )


if __name__ == "__main__":
    unittest.main()
