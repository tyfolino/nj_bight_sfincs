"""The power-asset and share-map scripts read the bed's BASE band, not its first overview.

2026-11-13. ``rasterio.open(path, overview_level=0)`` opens the FIRST OVERVIEW (in GDAL,
level 0 is the first reduced copy; the full raster is ``overview_level=None``). Our subgrid
beds carry ``average`` overviews, so a street pixel between two burned buildings read
building height there (``logs/floodmap_fix_2026-11-12/README.md``). ``scripts/power_exposure.py``
and ``scripts/export_share_floodmap.py`` opened their beds that way until 2026-11-13.

Pinned here, on a small ROTATED synthetic bed with average overviews (the v4 frame is
rotated, CLAUDE.md §5):

* ``power_exposure.open_bed`` + ``read_at_xy`` returns the street's own ground, and the
  first-overview read (the bug) would not have;
* ``power_exposure.py`` asks for an overview level nowhere.
"""

import importlib.util
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import rasterio
from affine import Affine
from rasterio.enums import Resampling

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ("power_exposure.py",)  # export_share_floodmap.py: being reworked 11-13


def _load_power_exposure():
    spec = importlib.util.spec_from_file_location(
        "power_exposure_under_test", ROOT / "scripts" / "power_exposure.py"
    )
    mod = importlib.util.module_from_spec(spec)
    with mock.patch.dict(os.environ, {"NJ_DOMAIN": "v1_monmouth"}):
        spec.loader.exec_module(mod)  # module constants call exp_root()
    return mod


def _rotated_bed(path: Path) -> tuple[np.ndarray, Affine]:
    """8 x 8 bed, 3.125 m pixels, rotated 0.8 deg: 10 m buildings, a 1 m street in
    column 3 (one pixel wide, so the 2x average overview mixes it with a building)."""
    z = np.full((8, 8), 10.0, "float32")
    z[:, 3] = 1.0
    tf = Affine.translation(500_000.0, 4_400_000.0) * Affine.rotation(-0.8)
    tf = tf * Affine.scale(3.125, -3.125)
    with rasterio.open(
        path, "w", driver="GTiff", width=8, height=8, count=1, dtype="float32",
        crs="EPSG:32618", transform=tf, nodata=np.nan,
    ) as dst:  # fmt: skip
        dst.write(z, 1)
        dst.build_overviews([2], Resampling.average)
    return z, tf


class TestBaseBand(unittest.TestCase):
    def test_open_bed_reads_street_ground(self):
        pe = _load_power_exposure()
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "dep.tif"
            z, tf = _rotated_bed(p)
            rows = np.arange(8)
            cols = np.full(8, 3)
            x, y = tf * (cols + 0.5, rows + 0.5)
            x, y = np.asarray(x), np.asarray(y)
            with pe.open_bed(p) as bed:
                self.assertEqual(bed.shape, (8, 8))
                got = pe.read_at_xy(bed, x, y)
            np.testing.assert_array_equal(got, z[rows, cols])
            # the bug: the first overview puts the street under averaged building height
            with rasterio.open(p, overview_level=0) as ov:
                self.assertEqual(ov.shape, (4, 4))
                bad = pe.read_at_xy(ov, x, y)
            self.assertTrue((bad > 5.0).all(), bad)

    def test_no_overview_level_in_scripts(self):
        for name in SCRIPTS:
            src = (ROOT / "scripts" / name).read_text()
            self.assertIsNone(
                re.search(r"overview_level\s*=", src), f"{name} reads an overview"
            )
            self.assertNotIn("utils.downscale_floodmap(", src, name)


if __name__ == "__main__":
    unittest.main()
