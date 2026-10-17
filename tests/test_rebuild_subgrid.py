"""``scripts/rebuild_subgrid.py``: the overlay wrapper, ``--manning-overlay`` and the
lower-only ``--overlay <key>:min`` paint.

Pins the two things a roughness overlay must not break: WITHOUT the flag the roughness
list is the premier's one-entry NLCD list (every bed-only rebuild must reproduce), and
the wrapper paints an overlay's n ONLY where the overlay is valid, on top of hydromt's
own merge, which it leaves untouched. And for ``:min``: a plain overlay still overwrites
a deeper pixel (the 10-06 recipe), a lower-only one never raises one, and the paint ORDER
decides which wins. Synthetic rasters only; no run dir is read.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import unittest
from unittest import mock

import numpy as np

from nj_sfincs.config import ROOT


def _load():
    spec = importlib.util.spec_from_file_location(
        "rebuild_subgrid", ROOT / "scripts" / "rebuild_subgrid.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class _Base:
    roughness_lulc = "nlcd_x"
    reclass_table = "table.csv"

    def elevation(self):
        return [{"elevation": "dem_a"}, {"elevation": "dem_b", "zmin": 0.001}]


def _args(**kw):
    a = dict(tier=[], overlay=[], manning_overlay=[], reproj_method="nearest")
    a.update(kw)
    return argparse.Namespace(**a)


def _raster(values, x0=500000.0, y1=4400000.0, res=3.0, nodata=np.nan):
    import xarray as xr

    ny, nx = values.shape
    da = xr.DataArray(
        values.astype("float32"),
        dims=("y", "x"),
        coords={
            "y": y1 - res * (np.arange(ny) + 0.5),
            "x": x0 + res * (np.arange(nx) + 0.5),
        },
    )
    da.raster.set_crs(32618)
    da.raster.set_nodata(nodata)
    return da


@mock.patch.dict(os.environ, {"NJ_DOMAIN": "v1_monmouth"})
class TestRebuildSubgridLists(unittest.TestCase):
    def test_no_manning_flag_is_the_premier_roughness_list(self):
        rbs = _load()
        elev, rgh = rbs.input_lists(_args(overlay=["burn"]), _Base())
        self.assertEqual(rgh, [{"lulc": "nlcd_x", "reclass_table": "table.csv"}])
        self.assertEqual(
            elev,
            [
                {"elevation": "dem_a"},
                {"elevation": "dem_b", "zmin": 0.001},
                {"elevation": "burn", "merge_method": "overlay"},
            ],
        )

    def test_manning_overlay_goes_after_the_nlcd_reclass(self):
        rbs = _load()
        elev, rgh = rbs.input_lists(_args(manning_overlay=["n_water"]), _Base())
        self.assertEqual(rgh[0], {"lulc": "nlcd_x", "reclass_table": "table.csv"})
        self.assertEqual(rgh[1:], [{"manning": "n_water", "merge_method": "overlay"}])
        self.assertEqual(elev, _Base().elevation())  # the bed is untouched

    def test_min_suffix_keeps_its_slot_in_the_paint_order(self):
        rbs = _load()
        elev, _ = rbs.input_lists(_args(overlay=["burn", "lake:min", "chan"]), _Base())
        self.assertEqual(
            elev[2:],
            [
                {"elevation": "burn", "merge_method": "overlay"},
                {"elevation": "lake", "merge_method": "overlay_min"},
                {"elevation": "chan", "merge_method": "overlay"},
            ],
        )

    def test_bad_suffixes_are_refused(self):
        rbs = _load()
        for tok in ("lake:max", "lake:", ":min"):
            with self.assertRaises(SystemExit, msg=tok):
                rbs.input_lists(_args(overlay=[tok]), _Base())
        with self.assertRaises(SystemExit):  # bed only
            rbs.input_lists(_args(manning_overlay=["n_water:min"]), _Base())
        with self.assertRaises(SystemExit):  # caught before --force's rmtree
            rbs.input_lists(_args(overlay=["lake:low"]), None, validate_only=True)


@mock.patch.dict(os.environ, {"NJ_DOMAIN": "v1_monmouth"})
class TestOverlayWrapper(unittest.TestCase):
    def setUp(self):
        from hydromt_sfincs.components.quadtree import subgrid_quadtree_builder as bld

        self.bld = bld
        self.orig = bld.merge_multi_dataarrays
        self.addCleanup(setattr, bld, "merge_multi_dataarrays", self.orig)
        _load().install_overlay_merge()

    def test_paints_only_where_the_overlay_is_valid(self):
        base = _raster(np.full((40, 40), 0.13))  # a developed NLCD class
        ov = np.full((40, 40), -9999.0)
        ov[10:20, 5:30] = 0.02  # a channel polygon
        ovr = _raster(ov, nodata=-9999.0)
        like = _raster(np.zeros((20, 20)), res=6.0)
        ref = self.orig(da_list=[{"da": base}], da_like=like)
        got = self.bld.merge_multi_dataarrays(
            da_list=[{"da": base}, {"da": ovr, "merge_method": "overlay"}],
            da_like=like,
        )
        painted = ~np.isclose(got.values, ref.values)
        # every painted pixel took the overlay's n; the rest is hydromt's merge, exact
        self.assertTrue(painted.any())
        np.testing.assert_allclose(got.values[painted], 0.02)
        np.testing.assert_array_equal(got.values[~painted], ref.values[~painted])
        # and only inside the channel's footprint (6 m pixels 5:10 x 2.5:15)
        rows, cols = np.nonzero(painted)
        self.assertGreaterEqual(rows.min(), 5)
        self.assertLessEqual(rows.max(), 9)
        self.assertGreaterEqual(cols.min(), 2)
        self.assertLessEqual(cols.max(), 15)

    def test_no_overlay_entry_is_a_pass_through(self):
        base = _raster(np.random.default_rng(0).uniform(0.02, 0.16, (40, 40)))
        like = _raster(np.zeros((20, 20)), res=6.0)
        ref = self.orig(da_list=[{"da": base}], da_like=like)
        got = self.bld.merge_multi_dataarrays(da_list=[{"da": base}], da_like=like)
        np.testing.assert_array_equal(got.values, ref.values)

    # ---- lower-only paint (--overlay <key>:min); one 3 m lattice, so nearest is exact
    def _bed(self):
        bed = np.full((12, 12), 1.0)
        bed[:, :6] = -2.0  # a deep half (the lake bottom the plain paint overwrote)
        return _raster(bed)

    def _paint(self, *entries):
        like = _raster(np.zeros((12, 12)))
        da_list = [{"da": self._bed()}] + [
            {"da": da, "merge_method": m} for da, m in entries
        ]
        ref = self.orig(da_list=[{"da": self._bed()}], da_like=like)
        return ref.values, self.bld.merge_multi_dataarrays(
            da_list=da_list, da_like=like
        ).values

    def _lake(self):
        ov = np.full((12, 12), 0.0)  # above the deep half, below the high half
        ov[8:, :] = -9999.0  # NoData rows
        return ov, _raster(ov, nodata=-9999.0)

    def test_plain_overlay_overwrites_a_deeper_pixel(self):
        ov, da = self._lake()
        ref, got = self._paint((da, "overlay"))
        np.testing.assert_array_equal(ref, self._bed().values)  # merge is identity
        np.testing.assert_array_equal(got[:8], 0.0)  # deep half RAISED to 0
        np.testing.assert_array_equal(got[8:], ref[8:])

    def test_lower_only_overlay_never_raises(self):
        ov, da = self._lake()
        ref, got = self._paint((da, "overlay_min"))
        self.assertTrue(np.all(got <= ref))
        valid = ov != -9999.0
        np.testing.assert_array_equal(got[valid], np.minimum(ref, ov)[valid])
        np.testing.assert_array_equal(got[~valid], ref[~valid])
        np.testing.assert_array_equal(got[:8, :6], -2.0)  # deep pixels kept
        np.testing.assert_array_equal(got[:8, 6:], 0.0)  # high pixels lowered

    def test_lower_only_fills_a_nodata_block_pixel(self):
        like = _raster(np.zeros((12, 12)))
        bed = self._bed().values.copy()
        bed[0, 0] = np.nan
        ov, da = self._lake()
        got = self.bld.merge_multi_dataarrays(
            da_list=[{"da": _raster(bed)}, {"da": da, "merge_method": "overlay_min"}],
            da_like=like,
        ).values
        self.assertEqual(got[0, 0], 0.0)  # as a plain paint would

    def test_paint_order_decides_the_winner(self):
        _, lake = self._lake()
        high = _raster(np.full((12, 12), 5.0))  # a plain overlay above everything
        low = _raster(np.full((12, 12), -1.0))
        # plain AFTER lower-only: the plain one wins everywhere it is valid
        _, got = self._paint((lake, "overlay_min"), (high, "overlay"))
        np.testing.assert_array_equal(got, 5.0)
        # lower-only AFTER plain: min(plain result, lower-only)
        _, got = self._paint((high, "overlay"), (lake, "overlay_min"))
        np.testing.assert_array_equal(got[:8], 0.0)
        np.testing.assert_array_equal(got[8:], 5.0)
        # lower-only AFTER plain cannot raise what the plain one lowered
        _, got = self._paint((low, "overlay"), (lake, "overlay_min"))
        np.testing.assert_array_equal(got, -1.0)


if __name__ == "__main__":
    unittest.main()
