"""nj_sfincs.normal_surface — the usual surface "water depth" is measured from."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from nj_sfincs import normal_surface as ns


class TestUsualSurface(unittest.TestCase):
    """Land → ground; tidal water → MHHW; a lake → its pool; NaN W → ground."""

    def setUp(self):
        # 0: dry land above MHHW, 1: tidal bay bed, 2: lake bed, 3: inland, no W,
        # 4: marsh just below MHHW, 5: unknown ground
        self.ground = np.array([2.0, -3.0, -1.5, 5.0, 0.6, np.nan])
        self.W = np.array([0.7, 0.7, 1.2, np.nan, 0.7, 0.7])

    def test_usual_surface(self):
        u = ns.usual_surface(self.ground, self.W)
        np.testing.assert_allclose(u[:5], [2.0, 0.7, 1.2, 5.0, 0.7])
        self.assertTrue(np.isnan(u[5]))

    def test_rise_above_usual(self):
        wl = np.array([2.5, 1.9, 1.4, 4.0, 1.0, 1.0])
        r = ns.rise_above_usual(wl, self.ground, self.W)
        np.testing.assert_allclose(r[:5], [0.5, 1.2, 0.2, -1.0, 0.3])
        self.assertTrue(np.isnan(r[5]))

    def test_scalars_and_broadcast(self):
        self.assertEqual(float(ns.usual_surface(-2.0, 0.5)), 0.5)
        self.assertEqual(float(ns.usual_surface(3.0, np.nan)), 3.0)
        r = ns.rise_above_usual(np.array([[1.0, 2.0]]), np.array([0.0, 3.0]), 0.5)
        np.testing.assert_allclose(r, [[0.5, -1.0]])


class TestRasters(unittest.TestCase):
    """Paths per domain, and the affine sampler on a north-up synthetic grid."""

    @classmethod
    def setUpClass(cls):
        import rasterio
        from rasterio.transform import from_origin

        cls.tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls.tmp.name) / "normal_surface_toy"
        cls.dir.mkdir()
        T = from_origin(1000.0, 2000.0, 25.0, 25.0)  # 4 x 4 px, x 1000–1100
        mhhw = np.full((4, 4), 0.7, np.float32)
        mhhw[:, 3] = np.nan  # inland column: no MHHW
        pool = np.full((4, 4), np.nan, np.float32)
        pool[0, 1] = 1.25  # one lake pixel (row 0 = y 1975–2000, col 1 = x 1025–1050)
        for name, a in (("mhhw_navd88_toy.tif", mhhw), ("lake_pool_toy.tif", pool)):
            with rasterio.open(
                cls.dir / name,
                "w",
                driver="GTiff",
                height=4,
                width=4,
                count=1,
                dtype="float32",
                crs="EPSG:32618",
                transform=T,
                nodata=np.nan,
            ) as d:
                d.write(a, 1)
        wm = np.zeros((4, 4), np.uint8)
        wm[3, 3] = (
            1  # a mapped river channel in the inland column (x 1075–1100, y 1900–1925)
        )
        with rasterio.open(
            cls.dir / "water_mask_toy.tif",
            "w",
            driver="GTiff",
            height=4,
            width=4,
            count=1,
            dtype="uint8",
            crs="EPSG:32618",
            transform=T,
        ) as d:
            d.write(wm, 1)
        from nj_sfincs import domain

        cls.dom = mock.Mock(normal_surface_dir=cls.dir)
        cls.dom.name = "toy"
        cls.patch = mock.patch.dict(domain.DOMAINS, {"toy": cls.dom})
        cls.patch.start()

    @classmethod
    def tearDownClass(cls):
        cls.patch.stop()
        cls.tmp.cleanup()

    def test_paths(self):
        self.assertEqual(ns.mhhw_path("toy"), self.dir / "mhhw_navd88_toy.tif")
        self.assertEqual(ns.pool_path("toy"), self.dir / "lake_pool_toy.tif")
        self.assertEqual(ns.water_mask_path("toy"), self.dir / "water_mask_toy.tif")

    def test_paths_follow_nj_domain(self):
        with mock.patch.dict(os.environ, {"NJ_DOMAIN": "toy"}):
            self.assertEqual(ns.mhhw_path(), self.dir / "mhhw_navd88_toy.tif")

    def test_no_dir_refuses(self):
        with self.assertRaises(ValueError):
            ns.mhhw_path("v3")

    def test_usual_water_surface(self):
        x = np.array([1030.0, 1060.0, 1090.0, 990.0, 1030.0])
        y = np.array([1990.0, 1940.0, 1940.0, 1990.0, 2010.0])
        W = ns.usual_water_surface(x, y, "toy")
        np.testing.assert_allclose(
            W[:2], [1.25, 0.7], rtol=1e-6
        )  # pool wins, else MHHW
        self.assertTrue(
            np.isnan(W[2:]).all()
        )  # inland column, west of / above the grid

    def test_normally_wet(self):
        pts = [
            # (x, y, ground, wet?)
            (1060.0, 1940.0, 2.0, False),  # land above MHHW
            (1060.0, 1940.0, 0.5, True),  # tidal ground below MHHW 0.7
            (1030.0, 1990.0, 3.0, True),  # lake pool pixel, whatever the DEM says
            (1090.0, 1990.0, -0.5, True),  # no MHHW: below 0 m NAVD88
            (1090.0, 1990.0, 2.0, False),  # no MHHW: above 0
            (1090.0, 1910.0, 2.0, True),  # mapped river: DEM holds the water surface
            (990.0, 1990.0, 1.0, False),  # off the rasters: the 0 m rule
            (990.0, 1990.0, -1.0, True),
            (1060.0, 1940.0, np.nan, False),  # unknown ground: only mask / pool count
            (1090.0, 1910.0, np.nan, True),
        ]
        x, y, g, want = (np.array(c) for c in zip(*pts))
        wet = ns.normally_wet(x, y, g, "toy")
        self.assertEqual(wet.dtype, bool)
        np.testing.assert_array_equal(wet, want.astype(bool))
        np.testing.assert_array_equal(
            ns.normally_dry(x, y, g, "toy"), ~want.astype(bool)
        )

    def test_normally_wet_broadcasts_ground(self):
        wet = ns.normally_wet(np.full((2, 2), 1060.0), 1940.0, [[0.0, 1.0]], "toy")
        np.testing.assert_array_equal(wet, [[True, False], [True, False]])

    def test_sampler_keeps_shape(self):
        W = ns.usual_water_surface(np.full((2, 3), 1060.0), 1940.0, "toy")
        self.assertEqual(W.shape, (2, 3))


class TestShippedRasters(unittest.TestCase):
    """The v4 rasters, when built: north-up EPSG:32618 grids that sample MHHW at Sandy
    Hook to the CO-OPS datum (MHHW − NAVD88 = 0.735 m) within a few cm."""

    def test_sandy_hook(self):
        p = ns.mhhw_path("v4_refreeze")
        if not p.exists():
            self.skipTest("v4 usual-surface rasters not built")
        import rasterio
        from pyproj import Transformer

        with rasterio.open(p) as d:
            self.assertEqual(d.crs.to_epsg(), 32618)
            self.assertEqual((d.transform.b, d.transform.d), (0.0, 0.0))
        x, y = Transformer.from_crs(4326, 32618, always_xy=True).transform(
            -74.0094, 40.4669
        )
        self.assertAlmostEqual(float(ns.sample_raster(p, x, y)), 0.735, delta=0.03)


if __name__ == "__main__":
    unittest.main()
