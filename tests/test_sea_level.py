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


def _toy_grid(n=5):
    """One level-1 row of n 100 m faces, origin (0, 0), no rotation: centres x = 50, 150, …"""
    return {
        "x0": 0.0,
        "y0": 0.0,
        "dx": 100.0,
        "dy": 100.0,
        "rotation": 0.0,
        "nr_levels": 1,
        "n": np.ones(n, np.int64),
        "m": np.arange(1, n + 1, dtype=np.int64),
        "level": np.ones(n, np.int64),
    }


def _weir(x, crest, y0=-100.0, y1=200.0):
    return [("w", np.array([[x, y0, crest, 0.6], [x, y1, crest, 0.6]]))]


class TestWeirUvCrests(unittest.TestCase):
    """The engine's float32 snap rule (logs/walls_elizabeth_rahway_2026-11-05/weircount_819.md)
    on a toy row; on 1.1.0's premier run dir the same code gives the logged 819."""

    def setUp(self):
        self.mask = np.array([2, 1, 1, 1, 1])
        self.zmin = np.full(5, -1.0)
        self.a, self.b = sea_level.uv_pairs(*_row(5))
        self.slot, self.dir = sea_level._uv_slots(*_row(5))
        self.uv = np.full(4, -1.0)

    def crest(self, polylines, uv=None):
        return sea_level.weir_uv_crests(
            polylines,
            _toy_grid(),
            self.mask,
            self.zmin,
            self.a,
            self.b,
            self.uv if uv is None else uv,
            self.slot,
            self.dir,
        )

    def test_segment_between_centres_marks_one_link(self):
        c = self.crest(_weir(200.0, 3.0))  # between centres 150 and 250: link 1|2
        self.assertEqual(np.flatnonzero(np.isfinite(c)).tolist(), [1])
        self.assertAlmostEqual(float(c[1]), 3.0, places=5)

    def test_centre_on_the_line_marks_all_its_links(self):
        # the engine counts "touching" as crossing (the Elizabeth RB +2 of weircount_819.md)
        c = self.crest(_weir(150.0, 3.0))
        self.assertEqual(np.flatnonzero(np.isfinite(c)).tolist(), [0, 1])

    def test_crest_below_the_sill_is_not_kept(self):
        uv = self.uv.copy()
        uv[1] = 3.5
        self.assertFalse(np.isfinite(self.crest(_weir(200.0, 3.0), uv)).any())

    def test_highest_crest_wins_over_polylines(self):
        c = self.crest(_weir(200.0, 2.0) + _weir(210.0, 3.5))
        self.assertAlmostEqual(float(c[1]), 3.5, places=5)

    def test_slots_follow_uv_pairs_order(self):
        mu = np.array([1, 0, 0])
        mu1 = np.array([1, -1, -1])
        mu2 = np.array([2, 7, -1])
        nu1 = np.array([-1, 2, -1])
        none = np.full(3, -1)
        slot, d = sea_level._uv_slots(mu, mu1, mu2, np.zeros(3, int), nu1, none)
        a, b = sea_level.uv_pairs(mu, mu1, mu2, np.zeros(3, int), nu1, none)
        self.assertEqual(list(zip(a.tolist(), b.tolist())), [(0, 1), (0, 2), (1, 2)])
        self.assertEqual(slot[0, :2].tolist(), [0, 1])
        self.assertEqual(slot[1, 2], 2)
        self.assertEqual(d.tolist(), [0, 0, 1])


class TestWeirAwareStart(unittest.TestCase):
    def setUp(self):
        self.mask = np.array([2, 1, 1, 1, 1])
        self.zmin = np.full(5, -1.0)
        self.a, self.b = sea_level.uv_pairs(*_row(5))
        self.uv = np.full(4, -1.0)
        self.crest = np.array([np.nan, 3.0, np.nan, np.nan], np.float32)

    def zs(self, level, crest):
        return sea_level.connected_initial_zs(
            level, self.mask, self.zmin, self.a, self.b, self.uv, crest
        )

    def test_levee_keeps_the_protected_side_dry(self):
        self.assertEqual(
            (self.zs(2.0, self.crest) > sea_level.DRY).tolist(), [1, 1, 0, 0, 0]
        )

    def test_crest_equal_to_the_level_still_holds(self):
        self.assertEqual(
            (self.zs(3.0, self.crest) > sea_level.DRY).tolist(), [1, 1, 0, 0, 0]
        )

    def test_overtopped_levee_connects(self):
        self.assertTrue(np.all(self.zs(4.0, self.crest) == 4.0))

    def test_no_weir_is_bit_identical(self):
        for level in (0.0, 2.0, 3.0):
            old = sea_level.connected_initial_zs(
                level, self.mask, self.zmin, self.a, self.b, self.uv
            )
            for crest in (None, np.full(4, np.nan, np.float32)):
                self.assertEqual(old.tobytes(), self.zs(level, crest).tobytes())


class TestWriteConnectedIniWeir(unittest.TestCase):
    def _stage(self, d, weir_text=None):
        import xarray as xr

        mu, mu1, _, nu, _, _ = _row(5)
        g = _toy_grid()
        ds = xr.Dataset(
            {
                k: ("mesh2d_nFaces", v)
                for k, v in {
                    "mask": np.array([2, 1, 1, 1, 1], np.uint8),
                    "mu": mu,
                    "nu": nu,
                    "mu1": mu1 + 1,
                    "mu2": np.zeros(5, int),
                    "nu1": np.zeros(5, int),
                    "nu2": np.zeros(5, int),
                    "n": g["n"],
                    "m": g["m"],
                    "level": g["level"],
                }.items()
            },
            attrs={k: g[k] for k in ("x0", "y0", "dx", "dy", "rotation", "nr_levels")},
        )
        ds.to_netcdf(Path(d) / "sfincs.nc")
        xr.Dataset(
            {
                "z_zmin": ("np", np.full(5, -1.0, np.float32)),
                "uv_zmin": ("npuv", np.full(4, -1.0, np.float32)),
            }
        ).to_netcdf(Path(d) / "sfincs_subgrid.nc")
        if weir_text is not None:
            (Path(d) / sea_level.WEIR_FILE).write_text(weir_text)

    def test_weir_file_closes_the_link_and_is_recorded(self):
        import json
        import tempfile

        weir = "levee\n2 4\n200.0 -100.0 3.0 0.6\n200.0 200.0 3.0 0.6\n"
        with tempfile.TemporaryDirectory() as d:
            self._stage(d, weir)
            meta = sea_level.write_connected_ini(d, 2.0)
            zs = sea_level.read_ini(d)
            side = json.loads((Path(d) / sea_level.INI_META).read_text())
        self.assertEqual((zs > sea_level.DRY).tolist(), [1, 1, 0, 0, 0])
        self.assertEqual(meta["weir_uv_points"], 1)
        self.assertEqual(meta["weir_uv_at_or_above_level"], 1)
        self.assertEqual(meta["cells_kept_dry_by_weirs"], 3)
        self.assertEqual(side["weir_file"], sea_level.WEIR_FILE)

    def test_without_weir_file_output_unchanged(self):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            self._stage(d)
            meta = sea_level.write_connected_ini(d, 2.0)
            zs = sea_level.read_ini(d)
        self.assertTrue(np.all(zs == 2.0))
        self.assertNotIn("weir_uv_points", meta)


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
        zmin = np.array([30.0, 50.0])
        h2, zs2 = oc.neighbour_depth_on_outflow(h, zs, mask, nb, zmin)
        self.assertAlmostEqual(h2[0], 0.2)  # not 50.2 - 30
        self.assertAlmostEqual(zs2[0], 50.2)

    def test_outflow_bank_beside_a_deep_channel_is_dry(self):
        spec = importlib.util.spec_from_file_location(
            "overflow_check", ROOT / "scripts" / "overflow_check.py"
        )
        oc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oc)
        # cell 0 outflow bank at +2.4 m beside a 13 m canal whose level is +1.5 m
        mask = np.array([3, 1])
        zs = np.array([np.nan, 1.5])
        h = np.array([np.nan, 14.5])
        nb = {k: np.array([-1, -1]) for k in oc.NEIGH}
        nb["mu1"] = np.array([1, -1])
        h2, _ = oc.neighbour_depth_on_outflow(h, zs, mask, nb, np.array([2.4, -13.0]))
        self.assertLess(h2[0], 0.0)  # not 14.5


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
