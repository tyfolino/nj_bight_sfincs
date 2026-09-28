"""Sea-level offset runs: the connected start, the uv order, and the v4 gate ladder.

The trap these pin: ``zsini`` alone floods every diked marsh and coastal lake below the
offset at t = 0 (SFINCS sets zs = max(z_zmin, zsini) on every active cell), which is
exactly the ground the v4 overflow test asks about. Nothing here runs SFINCS.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import os
import unittest
from pathlib import Path

import numpy as np

from nj_sfincs import sea_level

ROOT = Path(__file__).resolve().parents[1]


def _row(n: int):
    """A 1-D row of n same-level cells: mu1 = right neighbour, no mu2/nu*."""
    mu = np.zeros(n, int)
    mu1 = np.r_[np.arange(1, n), -1]
    none = np.full(n, -1)
    return mu, mu1, none, np.zeros(n, int), none, none


class TestUvPairs(unittest.TestCase):
    def test_row_order(self):
        a, b = sea_level.uv_pairs(*_row(4))
        self.assertEqual(a.tolist(), [0, 1, 2])
        self.assertEqual(b.tolist(), [1, 2, 3])

    def test_mu2_only_when_finer(self):
        # cell 0 has a finer right side (mu=1): two uv points, mu1 then mu2
        mu = np.array([1, 0, 0])
        mu1 = np.array([1, -1, -1])
        mu2 = np.array([2, 7, -1])  # cell 1's mu2 must be ignored (mu = 0)
        none = np.full(3, -1)
        a, b = sea_level.uv_pairs(mu, mu1, mu2, np.zeros(3, int), none, none)
        self.assertEqual(list(zip(a.tolist(), b.tolist())), [(0, 1), (0, 2)])


class TestConnectedStart(unittest.TestCase):
    def setUp(self):
        # forced | low | DIKE SILL | low | low     (cells 0..4, level +2)
        self.mask = np.array([2, 1, 1, 1, 1])
        self.zmin = np.array([-5.0, 0.5, 0.4, 0.3, 1.0])
        self.a, self.b = sea_level.uv_pairs(*_row(5))
        self.uv = np.array([-5.0, 0.6, 3.5, 1.1])  # the 2|3 sill is the dike

    def test_dike_keeps_the_back_side_dry(self):
        zs = sea_level.connected_initial_zs(
            2.0, self.mask, self.zmin, self.a, self.b, self.uv
        )
        self.assertEqual((zs > sea_level.DRY).tolist(), [1, 1, 1, 0, 0])
        self.assertTrue(np.all(zs[:3] == 2.0))

    def test_overtopped_dike_connects(self):
        zs = sea_level.connected_initial_zs(
            4.0, self.mask, self.zmin, self.a, self.b, self.uv
        )
        self.assertTrue(np.all(zs == 4.0))

    def test_inactive_cell_breaks_the_path(self):
        mask = self.mask.copy()
        mask[1] = 0
        zs = sea_level.connected_initial_zs(
            4.0, mask, self.zmin, self.a, self.b, self.uv
        )
        self.assertEqual((zs > sea_level.DRY).tolist(), [1, 0, 0, 0, 0])

    def test_cell_above_level_stays_dry(self):
        zs = sea_level.connected_initial_zs(
            0.45, self.mask, self.zmin, self.a, self.b, self.uv
        )
        self.assertEqual((zs > sea_level.DRY).tolist(), [1, 0, 0, 0, 0])


class TestWriteConnectedIni(unittest.TestCase):
    def test_binary_is_active_points_in_face_order(self):
        import json
        import tempfile

        import xarray as xr

        # forced | low | INACTIVE | low (reached round nothing: row broken) | low
        mask = np.array([2, 1, 0, 1, 1])
        mu, mu1, _, nu, _, _ = _row(5)
        one = {
            k: ("mesh2d_nFaces", v)
            for k, v in {
                "mask": mask.astype(np.uint8),
                "mu": mu,
                "nu": nu,
                "mu1": mu1 + 1,  # sfincs.nc is 1-based, 0 = none
                "mu2": np.zeros(5, int),
                "nu1": np.zeros(5, int),
                "nu2": np.zeros(5, int),
            }.items()
        }
        a, _b = sea_level.uv_pairs(*_row(5))
        with tempfile.TemporaryDirectory() as d:
            xr.Dataset(one).to_netcdf(Path(d) / "sfincs.nc")
            xr.Dataset(
                {
                    "z_zmin": ("np", np.array([-5.0, 0.5, 0.5, 0.3, 1.0])),
                    "uv_zmin": ("npuv", np.full(len(a), 0.6)),
                }
            ).to_netcdf(Path(d) / "sfincs_subgrid.nc")
            meta = sea_level.write_connected_ini(d, 2.0, boundary_offset_m=2.0)
            zs = sea_level.read_ini(d)
            side = json.loads((Path(d) / sea_level.INI_META).read_text())
        self.assertEqual(len(zs), 4)  # the inactive face is not in the stream
        self.assertEqual(zs.tolist()[:2], [2.0, 2.0])
        self.assertTrue(np.all(zs[2:] == sea_level.DRY))  # cut off by the inactive cell
        self.assertEqual(meta["disconnected_dry_cells"], 2)
        self.assertEqual(side["boundary_offset_m"], 2.0)


class TestIniKeys(unittest.TestCase):
    def test_replaces_zsini_and_adds_inifile(self):
        text = "tspinup              = 3600.0\nzsini                = 0.0\n"
        out = sea_level.ini_keys(text, 3.0)
        kv = {
            ln.split("=")[0].strip(): ln.split("=")[1].strip()
            for ln in out.splitlines()
        }
        self.assertEqual(kv["zsini"], "3.0")
        self.assertEqual(kv["inifile"], sea_level.INI_FILE)
        self.assertEqual(out.count("zsini"), 1)


class TestOutflowProxy(unittest.TestCase):
    def test_outflow_takes_neighbour_depth_not_level(self):
        spec = importlib.util.spec_from_file_location(
            "overflow_check", ROOT / "scripts" / "overflow_check.py"
        )
        oc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oc)
        # cell 0 outflow on a slope (bed 30), cell 1 uphill with 0.2 m of water at 50.2
        mask = np.array([3, 1])
        zs = np.array([np.nan, 50.2])
        h = np.array([np.nan, 0.2])
        nb = {k: np.array([-1, -1]) for k in oc.NEIGH}
        nb["mu1"] = np.array([1, -1])
        h2, zs2 = oc.neighbour_depth_on_outflow(h, zs, mask, nb)
        self.assertAlmostEqual(h2[0], 0.2)  # not 50.2 - 30
        self.assertAlmostEqual(zs2[0], 50.2)


class TestV4Ladder(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.get("NJ_DOMAIN")
        os.environ["NJ_DOMAIN"] = "v4"

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("NJ_DOMAIN", None)
        else:
            os.environ["NJ_DOMAIN"] = self._saved

    def test_ladder_differs_only_in_the_offset(self):
        from nj_sfincs import experiments

        arms = experiments.experiments("v4")
        ladder = {k: v for k, v in arms.items() if "+slr-" in k}
        self.assertEqual(
            sorted(v.sea_level_offset_m for v in ladder.values()), [0.0, 2.0, 3.0]
        )
        skip = {"name", "description", "sea_level_offset_m"}
        shapes = {
            tuple(
                (f.name, getattr(v, f.name))
                for f in dataclasses.fields(v)
                if f.name not in skip
            )
            for v in ladder.values()
        }
        self.assertEqual(
            len(shapes), 1, "the +0/+2/+3 arms differ in more than the offset"
        )
        self.assertTrue(
            all(not v.rain and not v.waves.use_waves for v in ladder.values())
        )


if __name__ == "__main__":
    unittest.main()
