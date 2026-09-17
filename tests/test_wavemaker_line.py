"""scripts/build_wavemaker_line.py on a synthetic coast (2026-09-17).

A north-up bed raster: a plane beach rising eastward (sea to the WEST, land to the EAST),
with a barrier island backed by a bay in the north half and an inlet through it, plus a
closed offshore shoal. The −4.4 m line must: exist only on the ocean side (not the bay's
own −4.4 m contour, not the shoal's ring), break at the inlet, run with land on the LEFT
(here: north→south, since land is east), and sit within 2 m of the target depth.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

from nj_sfincs.config import ROOT


def _load():
    spec = importlib.util.spec_from_file_location(
        "build_wavemaker_line", ROOT / "scripts" / "build_wavemaker_line.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _synthetic_bed(path: Path, res=25.0):
    import rasterio
    from rasterio.transform import from_origin

    nx, ny = 800, 1200  # 20 km × 30 km
    x0, y0 = 500_000.0, 4_330_000.0  # top-left
    xs = x0 + res * (np.arange(nx) + 0.5)
    ys = y0 - res * (np.arange(ny) + 0.5)
    xx, yy = np.meshgrid(xs, ys)
    # plane: −20 m at the west edge rising to +4 m at x = 4 km (a 1:167 shoreface; the
    # −4.4 m line sits at x = 2.6 km, 730 m off the shoreline, NJ-like), then land
    z = -20.0 + 24.0 * np.clip((xx - x0) / 4_000.0, 0, 1)
    z = np.where(xx - x0 > 4_000.0, 4.0, z)
    # north half: a 600 m barrier island at +2 m from x = 3.33..3.93 km, bay (−3 m) behind
    north = yy > y0 - 15_000.0
    island = north & (xx - x0 >= 3_333.0) & (xx - x0 < 3_933.0)
    bay = north & (xx - x0 >= 3_933.0) & (xx - x0 < 19_000.0)
    z = np.where(island, 2.0, z)
    z = np.where(bay, -3.0, z)
    # an inlet 400 m wide through the island at y = 4,322,000, channel −8 m, from the
    # −4.4 m line out to the bay
    inlet = (
        north
        & (np.abs(yy - 4_322_000.0) < 200.0)
        & (xx - x0 >= 1_000.0)
        & (xx - x0 < 4_000.0)
    )
    z = np.where(inlet, -8.0, z)
    # an offshore shoal (closed −4.4 ring) at x = 0.9 km, y = 4,310,000
    shoal = np.hypot(xx - (x0 + 900.0), yy - 4_310_000.0) < 500.0
    z = np.where(shoal, -3.0, z)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=ny,
        width=nx,
        count=1,
        dtype="float32",
        crs="EPSG:32618",
        transform=from_origin(x0, y0, res, res),
        nodata=np.nan,
    ) as dst:
        dst.write(z.astype("float32"), 1)
    return x0, y0


class TestWavemakerLine(unittest.TestCase):
    def test_open_coast_only_inlet_break_and_orientation(self):
        import geopandas as gpd

        B = _load()
        with tempfile.TemporaryDirectory() as td:
            bed = Path(td) / "bed.tif"
            x0, y0 = _synthetic_bed(bed)
            out = Path(td) / "wm.geojson"
            rc = B.main(
                [
                    "--dep",
                    str(bed),
                    "--mesh",
                    "",
                    "--out",
                    str(out),
                    "--y-max",
                    "9e6",
                    "--x-min",
                    "0",
                ]
            )
            self.assertEqual(rc, 0)
            g = gpd.read_file(out)
            # two pieces (the inlet splits the island's line from... no: the south half
            # is mainland beach, the north half the island; the inlet breaks the north)
            self.assertGreaterEqual(len(g), 2, g)
            for _, row in g.iterrows():
                xy = np.asarray(row.geometry.coords)
                # on the ocean side: x well west of the island, never in the bay
                self.assertLess(xy[:, 0].max(), x0 + 3_333.0, "vertex in the bay/land")
                # near the −4.4 m plane position (x = 3.9 km on the plane)
                self.assertTrue(np.all(np.abs(xy[:, 0] - (x0 + 2_600.0)) < 500.0))
                # land is EAST → land on the left means walking SOUTH
                self.assertLess(
                    xy[-1, 1], xy[0, 1], "not ordered with land on the left"
                )
            # the inlet at y = 4,322,000 is not crossed by any piece
            for _, row in g.iterrows():
                ys = np.asarray(row.geometry.coords)[:, 1]
                self.assertFalse(
                    ys.min() < 4_321_800.0 < ys.max()
                    and ys.min() < 4_322_200.0 < ys.max(),
                    "a piece crosses the inlet",
                )
            # the shoal ring and the bay contour produced no piece
            self.assertLess(g.length_km.sum(), 31.0)
            self.assertGreater(g.length_km.sum(), 20.0)


if __name__ == "__main__":
    unittest.main()
