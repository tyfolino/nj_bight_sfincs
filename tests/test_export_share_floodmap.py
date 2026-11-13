"""``scripts/export_share_floodmap.py``: base band, explicit north-up lattice (2026-11-13).

The FIAT export (``logs/fiat_geotiffs_2026-11-13/``) needs a depth at every building at the
bed's NATIVE pixel. Two ways it went wrong before, pinned here:

* the first-overview read: rasterio's ``overview_level=0`` is the first REDUCED copy, and
  hydromt's path-mode ``downscale_floodmap`` opens the dep that way (6.25 m on v4, buildings
  averaged into streets; ``logs/floodmap_fix_2026-11-12/README.md``) — the script must ask
  for an overview level nowhere and downscale through ``downscale_floodmap_native``;
* the de-rotation grid: ``rio.reproject(crs)`` chose its own grid (the rotated SHAPE from the
  top-left corner: a clipped wedge, a pixel that is not the bed's). ``snap_grid`` /
  ``derotate`` put it on absolute multiples of the bed's pixel — on v4 the lattice of
  ``bed_buildings_v4_cap10`` — with the values of a plain nearest warp.
"""

import importlib.util
import re
import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio
import rioxarray  # noqa: F401
import xarray as xr
from affine import Affine
from rasterio.enums import Resampling

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "export_share_floodmap.py"

# the v4 subgrid lattice (rotated) and its rotated-corner bbox, as read 2026-11-13
V4_T = Affine(
    3.1245927615330813, -0.05044873214535665, 438968.4068477649,
    0.05044873214535662, 3.1245927615330835 * -1, 4536245.883758573,
)  # fmt: skip
V4_SHAPE = (80336, 59920)


def _load():
    spec = importlib.util.spec_from_file_location("export_share_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestNoOverviewRead(unittest.TestCase):
    def test_no_overview_level_and_native_downscale(self):
        code = SCRIPT.read_text()
        body = code.split('"""', 2)[2]  # skip the module docstring
        lines = [ln for ln in body.splitlines() if not ln.lstrip().startswith("#")]
        src = "\n".join(lines)
        self.assertIsNone(re.search(r"overview_level\s*=", src))
        self.assertNotIn("utils.downscale_floodmap", src)
        self.assertIn("downscale_floodmap_native(", src)


class TestLattice(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load()

    def test_v4_pixel_is_3125(self):
        self.assertEqual(self.m.lattice_res(V4_T), 3.125)

    def test_snap_grid_reproduces_cap10_lattice(self):
        h, w = V4_SHAPE
        xs, ys = V4_T * (np.array([0, w, 0, w]), np.array([0, 0, h, h]))
        tf, shape = self.m.snap_grid((xs.min(), ys.min(), xs.max(), ys.max()), 3.125)
        # bed_buildings_v4_cap10.tif: origin 434912.5 / 4539271.875, 61211 x 81294
        self.assertEqual((tf.c, tf.f, tf.a, tf.e, tf.b, tf.d), (
            434912.5, 4539271.875, 3.125, -3.125, 0.0, 0.0))  # fmt: skip
        self.assertEqual(shape, (81294, 61211))

    def test_snap_grid_covers_bounds(self):
        tf, (h, w) = self.m.snap_grid((10.2, -7.9, 30.0, 4.0), 3.125)
        self.assertLessEqual(tf.c, 10.2)
        self.assertGreaterEqual(tf.f, 4.0)
        self.assertGreaterEqual(tf.c + w * 3.125, 30.0)
        self.assertLessEqual(tf.f - h * 3.125, -7.9)
        self.assertEqual(tf.c % 3.125, 0.0)
        self.assertEqual(tf.f % 3.125, 0.0)

    def test_derotate_matches_nearest_warp(self):
        rng = np.random.default_rng(0)
        z = rng.normal(1.0, 0.5, (40, 30)).astype("float32")
        z[5:9, 3:12] = np.nan
        tf = Affine.translation(500_000.0, 4_400_000.0) * Affine.rotation(-0.925)
        tf = tf * Affine.scale(3.125, -3.125)
        with tempfile.TemporaryDirectory() as d:
            fn = Path(d) / "rot.tif"
            with rasterio.open(
                fn, "w", driver="GTiff", width=30, height=40, count=1,
                dtype="float32", crs="EPSG:32618", transform=tf, nodata=np.nan,
            ) as dst:  # fmt: skip
                dst.write(z, 1)
                dst.build_overviews([2], Resampling.average)
            h, w = z.shape
            xs, ys = tf * (np.array([0, w, 0, w]), np.array([0, 0, h, h]))
            gtf, shape = self.m.snap_grid(
                (xs.min(), ys.min(), xs.max(), ys.max()), self.m.lattice_res(tf)
            )
            got = self.m.derotate(fn, gtf, shape, threads=1)
            ref = (
                rioxarray.open_rasterio(fn, masked=True)
                .squeeze(drop=True)
                .rio.reproject(
                    "EPSG:32618",
                    shape=shape,
                    transform=gtf,
                    resampling=Resampling.nearest,
                )  # fmt: skip
            )
        self.assertIsInstance(got, xr.DataArray)
        self.assertEqual(got.rio.transform(), gtf)
        self.assertEqual(got.shape, shape)
        np.testing.assert_array_equal(got.values, ref.values.astype("float32"))
        # every finite value came from the base band, none from the averaged overview
        fin = got.values[np.isfinite(got.values)]
        self.assertTrue(np.isin(fin, z[np.isfinite(z)]).all())
        self.assertGreater(fin.size, 0.8 * np.isfinite(z).sum())


if __name__ == "__main__":
    unittest.main()
