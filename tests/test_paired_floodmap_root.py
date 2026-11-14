"""``paired_hwm_bootstrap.py --floodmap-root``: which floodmap each arm is read from.

The native-floodmap fix (2026-11-12, ``logs/floodmap_fix_2026-11-12/``) re-scores the
published reference runs into a separate root, so their run dirs keep the pre-fix maps.
A paired comparison against such a run must read the ROOT's native map and must never
re-downscale into the reference run dir. Synthetic layout, no model run needed.
"""

import importlib.util
import os
import tempfile
import time
import unittest
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine
from rasterio.enums import Resampling

ROOT = Path(__file__).resolve().parents[1]


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "paired_hwm_bootstrap", ROOT / "scripts" / "paired_hwm_bootstrap.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _tif(path, shape, res, overviews=False):
    T = (
        Affine.translation(500_000, 4_400_000)
        * Affine.rotation(0.8)
        * Affine.scale(res)
    )
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=shape[1],
        height=shape[0],
        count=1,
        dtype="float32",
        crs="EPSG:32618",
        transform=T,
        nodata=np.nan,
    ) as d:
        d.write(np.ones(shape, dtype="float32"), 1)
    if overviews:
        with rasterio.open(path, "r+") as d:
            d.build_overviews([2], Resampling.average)


class TestFloodmapRoot(unittest.TestCase):
    def setUp(self):
        self._orig = os.environ.get("NJ_DOMAIN")
        os.environ["NJ_DOMAIN"] = "v1_monmouth"
        from nj_sfincs import domain as _domain

        if hasattr(_domain.active, "cache_clear"):
            _domain.active.cache_clear()
        self.pb = _load_script()
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.run = t / "experiments" / "v1_monmouth" / "arm-x"
        (self.run / "subgrid").mkdir(parents=True)
        _tif(self.run / "subgrid" / "dep_subgrid_merged.tif", (40, 60), 1.0, True)
        self.root = t / "fmroot"

    def tearDown(self):
        self.tmp.cleanup()
        if self._orig is None:
            os.environ.pop("NJ_DOMAIN", None)
        else:
            os.environ["NJ_DOMAIN"] = self._orig

    def test_no_root_is_todays_behaviour(self):
        fm, why = self.pb.pick_floodmap(self.run, None)
        self.assertIsNone(fm)
        self.assertIn("default", why)

    def test_root_file_is_used(self):
        native = self.root / "v1_monmouth" / "arm-x" / "floodmap_hmax_native.tif"
        native.parent.mkdir(parents=True)
        _tif(native, (40, 60), 1.0)
        fm, why = self.pb.pick_floodmap(self.run, self.root)
        self.assertEqual(fm, native)
        self.assertIn("floodmap root", why)

    def test_prefix_run_dir_map_is_never_the_write_target(self):
        # the run dir holds a first-overview (pre-fix) map: stale, so the downscale must
        # go to the root path, not replace the run dir's published map
        _tif(self.run / "floodmap_hmax_lev3.tif", (20, 30), 2.0)
        fm, why = self.pb.pick_floodmap(self.run, self.root)
        self.assertEqual(
            fm, self.root / "v1_monmouth" / "arm-x" / "floodmap_hmax_native.tif"
        )
        self.assertNotEqual(fm.parent, self.run)
        self.assertIn("not the run dir", why)

    def test_native_fresh_run_dir_map_is_read_in_place(self):
        time.sleep(0.01)
        own = self.run / "floodmap_hmax_lev3.tif"
        _tif(own, (40, 60), 1.0)  # same lattice as the dep, newer than it
        fm, why = self.pb.pick_floodmap(self.run, self.root)
        self.assertEqual(fm, own)
        self.assertIn("read only", why)

    def test_cross_domain_arm_reads_its_own_domain(self):
        # 1.1.0 - 1.0.0 (2026-11-13): under NJ_DOMAIN=v4_refreeze_swz_v11 the arm
        # ``../v4_refreeze_swz/p4-premier`` must be looked up (and, if absent, written)
        # under v4_refreeze_swz/, not v4_refreeze_swz_v11/ (another arm's tree)
        exp = self.run.parent.parent
        other = exp / "v1_monmouth" / ".." / "v1_5_raritan" / "arm-x"
        (exp / "v1_5_raritan" / "arm-x" / "subgrid").mkdir(parents=True)
        _tif(
            exp / "v1_5_raritan/arm-x/subgrid/dep_subgrid_merged.tif", (40, 60), 1, True
        )
        self.assertEqual(self.pb.run_domain(other), "v1_5_raritan")
        self.assertEqual(self.pb.run_domain(self.run), "v1_monmouth")
        want = self.root / "v1_5_raritan" / "arm-x" / "floodmap_hmax_native.tif"
        fm, why = self.pb.pick_floodmap(other, self.root)
        self.assertEqual(fm, want)  # absent: the downscale target, under ITS domain
        self.assertIn("not the run dir", why)
        want.parent.mkdir(parents=True)
        _tif(want, (40, 60), 1.0)
        mine = self.root / "v1_monmouth" / "arm-x" / "floodmap_hmax_native.tif"
        mine.parent.mkdir(parents=True)
        _tif(mine, (40, 60), 1.0)
        self.assertEqual(self.pb.pick_floodmap(other, self.root)[0], want)
        # same-domain arm: unchanged, byte for byte
        self.assertEqual(
            self.pb.pick_floodmap(self.run, self.root),
            (mine, f"{mine} (floodmap root)"),
        )

    def test_unregistered_parent_falls_back_to_the_active_domain(self):
        odd = Path(self.tmp.name) / "elsewhere" / "arm-x"
        self.assertEqual(self.pb.run_domain(odd), "v1_monmouth")


if __name__ == "__main__":
    unittest.main()
