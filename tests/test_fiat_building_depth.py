"""``scripts/fiat_building_depth.py``: the 11-05 centroid rule on a synthetic block.

A 64 x 64 north-up 3.125 m grid, bare ground 1.0 m (2.0 m in one far corner), a
building in the middle whose pixels are NaN in the plain depth map (the face it fills was
dropped), streets 0.5 m deep (water level 1.5 m) and dry ground 30 m+ away. Pinned:
level = median street level within 50 m; depth = level - bare ground; footprint pixels
filled; everything outside footprints unchanged; a building with no wet street within
50 m is ``no_wet_neighbour`` with NaN depth.
"""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "fiat_building_depth_under_test", ROOT / "scripts" / "fiat_building_depth.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write(path, arr, tf):
    with rasterio.open(
        path, "w", driver="GTiff", width=arr.shape[1], height=arr.shape[0], count=1,
        dtype="float32", crs="EPSG:32618", transform=tf, nodata=np.nan,
    ) as dst:  # fmt: skip
        dst.write(arr.astype("float32"), 1)


class TestCentroidRule(unittest.TestCase):
    def test_block(self):
        m = _load()
        res, x0, y1, n = 3.125, 500_000.0, 4_400_000.0, 64
        tf = from_origin(x0, y1, res, res)
        bare = np.full((n, n), 1.0)
        depth = np.full((n, n), 0.5)
        depth[:, 48:] = np.nan  # dry strip on the east (> 50 m from building A? no:
        # building B sits in it, its window reaches only dry ground)
        bare[:, 48:] = 2.0
        depth[24:40, 20:36] = np.nan  # building A: its face dropped in the plain map
        with tempfile.TemporaryDirectory() as tmpd:
            d = Path(tmpd)
            _write(d / "depth.tif", depth, tf)
            _write(d / "bare.tif", bare, tf)
            A = box(x0 + 20 * res, y1 - 40 * res, x0 + 36 * res, y1 - 24 * res)
            B = box(x0 + 60 * res, y1 - 40 * res, x0 + 63 * res, y1 - 30 * res)
            gpd.GeoDataFrame(
                {"role": [1, 1]}, geometry=[A, B], crs="EPSG:32618"
            ).to_file(d / "fp.gpkg", engine="pyogrio")
            rc = m.main(
                [
                    "--depth", str(d / "depth.tif"), "--bare", str(d / "bare.tif"),
                    "--footprints", str(d / "fp.gpkg"), "--source", "test",
                    "--out-tif", str(d / "out.tif"), "--out-csv", str(d / "b.csv"),
                    "--out-gpkg", str(d / "b.gpkg"), "--json", str(d / "s.json"),
                    "--radius", "50", "--tile", "40",
                ]
            )  # fmt: skip
            self.assertEqual(rc, 0)
            tab = pd.read_csv(d / "b.csv").sort_values("x_utm18n")
            s = json.loads((d / "s.json").read_text())
            with rasterio.open(d / "out.tif") as f:
                out = f.read(1)
        a, b = tab.iloc[0], tab.iloc[1]
        self.assertAlmostEqual(a.level_m_navd88, 1.5, places=5)
        self.assertAlmostEqual(a.depth_m, 0.5, places=5)
        self.assertEqual(a.flag, "wet")
        self.assertTrue(np.isnan(a.plain_tif_depth_at_centroid_m))
        self.assertAlmostEqual(a.filled_tif_depth_at_centroid_m, 0.5, places=5)
        self.assertGreater(a.n_wet_pixels, 0)
        # B: 12 px (37.5 m) east of the wet edge: within 50 m, so it sees the 1.5 m level,
        # but its ground is 2.0 m -> dry
        self.assertEqual(b.flag, "dry")
        self.assertAlmostEqual(b.depth_m, -0.5, places=5)
        np.testing.assert_allclose(out[24:40, 20:36], 0.5, atol=1e-6)
        outside = np.ones_like(out, bool)
        outside[24:40, 20:36] = False
        outside[30:40, 60:63] = False
        same = (out == depth) | (np.isnan(out) & np.isnan(depth))
        self.assertTrue(same[outside].all())
        self.assertEqual(s["pixels_changed_outside_footprints"], 0)
        self.assertEqual(s["centroid_vs_plain"]["nan_to_finite"], 1)

    def test_no_wet_neighbour(self):
        m = _load()
        res, x0, y1, n = 3.125, 500_000.0, 4_400_000.0, 80
        tf = from_origin(x0, y1, res, res)
        depth = np.full((n, n), np.nan)
        depth[:, :5] = 0.4  # wet only far west, > 50 m from the building
        with tempfile.TemporaryDirectory() as tmpd:
            d = Path(tmpd)
            _write(d / "depth.tif", depth, tf)
            _write(d / "bare.tif", np.zeros((n, n)), tf)
            gpd.GeoDataFrame(
                {"role": [1]},
                geometry=[
                    box(x0 + 60 * res, y1 - 50 * res, x0 + 70 * res, y1 - 40 * res)
                ],
                crs="EPSG:32618",
            ).to_file(d / "fp.gpkg", engine="pyogrio")
            m.main(
                [
                    "--depth", str(d / "depth.tif"), "--bare", str(d / "bare.tif"),
                    "--footprints", str(d / "fp.gpkg"), "--source", "test",
                    "--out-tif", str(d / "out.tif"), "--out-csv", str(d / "b.csv"),
                    "--out-gpkg", str(d / "b.gpkg"), "--json", str(d / "s.json"),
                ]
            )  # fmt: skip
            tab = pd.read_csv(d / "b.csv")
        self.assertEqual(tab.flag.iloc[0], "no_wet_neighbour")
        self.assertTrue(np.isnan(tab.depth_m.iloc[0]))
        self.assertEqual(tab.n_wet_pixels.iloc[0], 0)


if __name__ == "__main__":
    unittest.main()
