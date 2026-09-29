"""``build_merged_subgrid_dep``: the all-level scoring bed, on the lev3 or lev2 lattice.

Four tiny nested rasters (res 1 / 2 / 4 / 8, lev3's origin two lev3 pixels inside the
others', a small rotation so the affine is exercised) with a known answer. Pins that the
default lev3 merge is the old one, and that ``base_level=2`` (v4, 2026-09-29) block-means
lev3 2x2 onto lev2's lattice, counts the partial blocks, and fills the rest from lev2 →
lev1 → lev0.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import rasterio  # noqa: E402
from build_merged_subgrid_dep import build_merged  # noqa: E402
from rasterio.transform import Affine  # noqa: E402

ROT = Affine.rotation(0.5)
X0, Y0 = 500_000.0, 4_400_000.0


def _write(p: Path, a: np.ndarray, res: float, off_px3: float = 0.0) -> None:
    """``off_px3``: origin shift in lev3 (res 1) pixels, right and DOWN (rows run -y)."""
    t = Affine.translation(X0, Y0) * ROT * Affine.translation(off_px3, -off_px3)
    t = t * Affine.scale(res, -res)
    with rasterio.open(
        p,
        "w",
        driver="GTiff",
        width=a.shape[1],
        height=a.shape[0],
        count=1,
        dtype="float32",
        crs="EPSG:32618",
        transform=t,
        nodata=np.nan,
    ) as d:
        d.write(a.astype("float32"), 1)


class TestMergedDep(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rng = np.random.default_rng(0)
        cls.tmp = tempfile.TemporaryDirectory()
        sg = cls.sg = Path(cls.tmp.name)
        nan = np.nan
        # lev3: 30 x 30 at res 1, origin (+2, -2) → covers lev2 px 1..15; data in its
        # top-left 13 x 13 (an ODD edge, so lev2 row/col 7 is a partial 2x2 block).
        l3 = np.full((30, 30), nan)
        l3[:13, :13] = rng.uniform(-3, 3, (13, 13))
        # lev2: 16 x 16 at res 2 — data top-right; lev1 8 x 8 bottom-left; lev0 all.
        l2 = np.full((16, 16), nan)
        l2[:8, 8:] = rng.uniform(-3, 3, (8, 8))
        l1 = np.full((8, 8), nan)
        l1[4:, :4] = rng.uniform(-3, 3, (4, 4))
        l0 = rng.uniform(-3, 3, (4, 4))
        _write(sg / "dep_subgrid_lev3.tif", l3, 1, off_px3=2)
        _write(sg / "dep_subgrid_lev2.tif", l2, 2)
        _write(sg / "dep_subgrid_lev1.tif", l1, 4)
        _write(sg / "dep_subgrid_lev0.tif", l0, 8)
        cls.l3, cls.l2, cls.l1, cls.l0 = l3, l2, l1, l0
        cls.out2 = build_merged(sg, sg / "m2.tif", base_level=2)
        cls.out3 = build_merged(sg, sg / "m3.tif", base_level=3)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_base2_is_on_the_lev2_lattice(self):
        with (
            rasterio.open(self.out2) as m,
            rasterio.open(self.sg / "dep_subgrid_lev2.tif") as b,
        ):
            self.assertEqual(m.shape, b.shape)
            self.assertEqual(m.transform, b.transform)

    def test_base2_means_lev3_blocks(self):
        with rasterio.open(self.out2) as m:
            a = m.read(1)
        # lev2 px (r, c) covers lev3 rows 2r-2..2r-1 (lev3 origin is 2 lev3 px in)
        for r in range(1, 7):
            for c in range(1, 7):
                blk = self.l3[2 * r - 2 : 2 * r, 2 * c - 2 : 2 * c]
                self.assertAlmostEqual(a[r, c], blk.mean(), places=5)
        # the partial edge block (lev3 row 12 finite, 13 not): mean of the finite pair
        blk = self.l3[12:14, 2:4]
        self.assertAlmostEqual(a[7, 2], np.nanmean(blk), places=5)

    def test_base2_fills_from_coarser_levels(self):
        with rasterio.open(self.out2) as m:
            a = m.read(1)
        self.assertAlmostEqual(a[2, 12], self.l2[2, 12], places=5)  # lev2 itself
        self.assertAlmostEqual(a[12, 2], self.l1[6, 1], places=5)  # lev1, nearest
        self.assertAlmostEqual(a[12, 12], self.l0[3, 3], places=5)  # lev0, nearest
        self.assertTrue(np.isfinite(a).all())

    def test_default_lev3_merge_is_unchanged(self):
        with rasterio.open(self.out3) as m:
            a = m.read(1)
        self.assertEqual(a.shape, self.l3.shape)
        np.testing.assert_array_equal(a[:13, :13], self.l3[:13, :13].astype("float32"))
        # a lev3 hole under lev2's data: lev3 px (r, c) sits in lev2 px ((r+2)//2, ..)
        self.assertAlmostEqual(a[2, 20], self.l2[2, 11], places=5)
        self.assertTrue(np.isfinite(a).all())


class TestMergedDepV4Layout(unittest.TestCase):
    """v4's actual lattice: rows run +y (``e > 0``) and lev2's origin sits OUTSIDE lev3's
    (the base window starts at a negative fine offset); the oracle is a plain in-bounds
    read of each 2x2 block. ⚠️ This does NOT reproduce the 2026-09-29 boundless-read bug —
    that appeared only on the real 160,656-row raster, which is why ``build_merged``
    spot-checks its own output (``_spot_check``) before publishing it."""

    @classmethod
    def setUpClass(cls):
        rng = np.random.default_rng(1)
        cls.tmp = tempfile.TemporaryDirectory()
        sg = cls.sg = Path(cls.tmp.name)
        rot = Affine.rotation(0.925)

        def write(name, a, res, off_px3=0.0):
            t = Affine.translation(X0, Y0) * rot * Affine.translation(off_px3, off_px3)
            t = t * Affine.scale(res, res)  # e > 0: row 0 is the SOUTH edge
            with rasterio.open(
                sg / name,
                "w",
                driver="GTiff",
                width=a.shape[1],
                height=a.shape[0],
                count=1,
                dtype="float32",
                crs="EPSG:32618",
                transform=t,
                nodata=np.nan,
            ) as d:
                d.write(a.astype("float32"), 1)

        cls.l3 = rng.uniform(-15, 5, (60, 60))
        write(
            "dep_subgrid_lev3.tif", cls.l3, 1, off_px3=4
        )  # lev2 origin at lev3 (-4,-4)
        write("dep_subgrid_lev2.tif", rng.uniform(-15, 5, (34, 34)), 2)
        write("dep_subgrid_lev1.tif", rng.uniform(-15, 5, (17, 17)), 4)
        write("dep_subgrid_lev0.tif", rng.uniform(-15, 5, (9, 9)), 8)
        cls.out = build_merged(sg, sg / "m2.tif", base_level=2)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_covered_pixel_is_its_own_2x2_mean(self):
        with rasterio.open(self.out) as m:
            a = m.read(1)
        # lev2 px (r, c) covers lev3 rows 2r-4..2r-3; fully covered for r, c in 2..31
        for r in range(2, 32):
            for c in range(2, 32):
                blk = self.l3[2 * r - 4 : 2 * r - 2, 2 * c - 4 : 2 * c - 2]
                self.assertAlmostEqual(a[r, c], blk.mean(), places=4, msg=(r, c))


if __name__ == "__main__":
    unittest.main()
