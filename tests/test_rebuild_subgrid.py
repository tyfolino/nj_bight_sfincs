"""``scripts/rebuild_subgrid.py``: the overlay wrapper and ``--manning-overlay``.

Pins the two things a roughness overlay must not break: WITHOUT the flag the roughness
list is the premier's one-entry NLCD list (every bed-only rebuild must reproduce), and
the wrapper paints an overlay's n ONLY where the overlay is valid, on top of hydromt's
own merge, which it leaves untouched. Synthetic rasters only; no run dir is read.
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


if __name__ == "__main__":
    unittest.main()
