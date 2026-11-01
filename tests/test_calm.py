"""Calm runs: the connected start, the weirs, the inp, the boundary. Nothing here runs SFINCS.

The traps these pin: a sloped start floods nothing the sea cannot reach; a weir above the level
closes its link (the subgrid sills do not know about it); a calm arm names no meteo or river file.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import numpy as np

from nj_sfincs import calm, sea_level
from nj_sfincs.config import CalmForcing
from nj_sfincs.experiments import EXPERIMENTS_BY_DOMAIN

DRY = sea_level.DRY


def _row(n: int):
    """A row of n cells, 0 forced: links (i, i+1)."""
    mask = np.ones(n, int)
    mask[0] = 2
    return mask, np.arange(n - 1), np.arange(1, n)


class TestConnectedStart(unittest.TestCase):
    def test_per_face_level_is_kept(self):
        mask, a, b = _row(3)
        lev = np.array([1.0, 1.1, 1.2])
        zs = calm.connected_start(lev, mask, np.full(3, -1.0), a, b, np.full(2, -1.0))
        self.assertTrue(np.allclose(zs, lev))

    def test_a_high_sill_stops_the_water(self):
        mask, a, b = _row(3)
        zs = calm.connected_start(
            1.0, mask, np.full(3, -1.0), a, b, np.array([-1.0, 2.0])
        )
        self.assertEqual(zs.tolist(), [1.0, 1.0, DRY])

    def test_the_sill_is_read_at_the_lower_of_the_two_levels(self):
        mask, a, b = _row(2)
        zs = calm.connected_start(
            np.array([1.0, 2.0]), mask, np.full(2, -1.0), a, b, np.array([1.5])
        )
        self.assertEqual(zs.tolist(), [1.0, DRY])

    def test_a_weir_above_the_level_closes_the_link(self):
        mask, a, b = _row(3)
        z, sill = np.full(3, -1.0), np.full(2, -1.0)
        crest = np.array([np.nan, 1.7])
        low = calm.connected_start(1.4, mask, z, a, b, sill, crest)
        high = calm.connected_start(2.0, mask, z, a, b, sill, crest)
        self.assertEqual(low.tolist()[2], DRY)
        self.assertEqual(high.tolist()[2], 2.0)

    def test_a_weir_at_or_below_the_sill_is_no_structure(self):
        # the engine drops it (sfincs_structures.f90), so it must not block here either
        mask, a, b = _row(2)
        zs = calm.connected_start(
            2.0, mask, np.full(2, -1.0), a, b, np.array([1.8]), np.array([1.7])
        )
        self.assertEqual(zs.tolist(), [2.0, 2.0])


class TestWeirs(unittest.TestCase):
    def test_read_two_polylines(self):
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / "sfincs.weir"
            f.write_text(
                "a\n2 4\n0 0 1.5 0.6\n1 1 2.5 0.6\nb\n2 4\n5 5 3 0.6\n6 6 3 0.6\n"
            )
            w = calm.read_weirs(f)
        self.assertEqual([len(p) for p in w], [2, 2])
        self.assertEqual(w[0][1].tolist(), [1.0, 1.0, 2.5])

    def test_crest_on_the_crossed_link_only(self):
        x = np.array([0.0, 10.0, 20.0])
        y = np.zeros(3)
        nm, nmu = np.array([0, 1]), np.array([1, 2])
        weir = np.array([[15.0, -5.0, 3.0], [15.0, 5.0, 3.0]])
        crest = calm.weir_crests(x, y, nm, nmu, np.ones(3, bool), [weir], reach=50.0)
        self.assertTrue(np.isnan(crest[0]))
        self.assertAlmostEqual(crest[1], 3.0)

    def test_inactive_face_is_no_link(self):
        x, y = np.array([0.0, 10.0]), np.zeros(2)
        weir = np.array([[5.0, -5.0, 3.0], [5.0, 5.0, 3.0]])
        crest = calm.weir_crests(
            x,
            y,
            np.array([0]),
            np.array([1]),
            np.array([True, False]),
            [weir],
            reach=50.0,
        )
        self.assertTrue(np.isnan(crest[0]))


class TestArms(unittest.TestCase):
    ARMS = EXPERIMENTS_BY_DOMAIN["v4_refreeze_swz"]
    NAMES = [f"bed-modern+{k}-{ft}ft" for k in ("still", "tide") for ft in ("2", "4")]

    def test_registered_and_calm(self):
        for n in self.NAMES:
            e = self.ARMS[n]
            self.assertFalse(e.waves.use_waves)
            self.assertFalse(e.rain)
            self.assertFalse(e.infiltration)
            self.assertIsNone(e.meteo_from)
            self.assertEqual(e.subgrid_from, "_subgrid_modern2026")
            self.assertEqual(e.name, n)

    def test_restart_divides(self):
        for n in self.NAMES:
            calm.inp_keys(self.ARMS[n].calm, 0.5, still=True)
        with self.assertRaises(ValueError):
            calm.inp_keys(
                CalmForcing(0.61, "mhhw", "a", "b", dtmaxout=7000.0), 0.5, True
            )

    def test_spinup_only_on_tide(self):
        c = self.ARMS[self.NAMES[0]].calm
        self.assertEqual(calm.inp_keys(c, 0.5, True)["tspinup"], "0.0")
        self.assertEqual(calm.inp_keys(c, 0.5, False)["tspinup"], "3600.0")


class TestInp(unittest.TestCase):
    def test_drops_meteo_and_river_keys(self):
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / "sfincs.inp"
            f.write_text(
                "tstart               = 20121028 000000\n"
                "netamuamvfile        = sfincs_netamuv.nc\n"
                "netsrcdisfile        = sfincs_netsrcdisfile.nc\n"
                "weirfile             = sfincs.weir\n"
            )
            calm._set_inp(f, {"tstart": "20121012 000000"}, drop=calm._DROP_KEYS)
            text = f.read_text()
        self.assertIn("20121012 000000", text)
        self.assertIn("weirfile", text)
        self.assertNotIn("netamuamvfile", text)
        self.assertNotIn("netsrcdisfile", text)


if __name__ == "__main__":
    os.environ.setdefault("NJ_DOMAIN", "v1_monmouth")
    unittest.main()
