"""``lake_outlet_blocked``: the sea-connection level and the per-mark rule.

Pins (a) that ``connection_level(...) < L`` is EXACTLY ``connected_initial_zs(L, ...)``
reaching a face, so the flag and the sea-level start read the sills the same way, and
(b) the rule on a tiny grid: a basin behind a sill above the local sea peak is flagged,
the same basin with the sill below it is not, an open-coast mark is not, and a mark on
ground above the sea peak (run-up, not a closed outlet) is not. Nothing here runs SFINCS.
"""

from __future__ import annotations

import unittest

import numpy as np

from nj_sfincs import sea_level
from nj_sfincs.validate import lake_flag


def _grid(nx: int, ny: int):
    """Regular nx * ny grid in face order (row-major), 0-based neighbour arrays."""
    n = nx * ny
    idx = np.arange(n).reshape(ny, nx)
    mu1 = np.full((ny, nx), -1)
    mu1[:, :-1] = idx[:, 1:]
    nu1 = np.full((ny, nx), -1)
    nu1[:-1, :] = idx[1:, :]
    none = np.full(n, -1)
    zero = np.zeros(n, int)
    return sea_level.uv_pairs(zero, mu1.ravel(), none, zero, nu1.ravel(), none)


class TestConnectionLevel(unittest.TestCase):
    def test_matches_connected_initial_zs_on_a_random_grid(self):
        rng = np.random.default_rng(7)
        nx, ny = 23, 17
        a, b = _grid(nx, ny)
        n = nx * ny
        z = rng.uniform(-3, 4, n).astype(np.float32)
        mask = (rng.uniform(size=n) > 0.08).astype(int)
        mask[:nx][mask[:nx] > 0] = 2  # the first row is the forced boundary
        z[5] = np.nan
        uv = (np.maximum(z[a], z[b]) + rng.uniform(0, 1.5, len(a))).astype(np.float32)
        uv[3] = np.nan
        conn = lake_flag.connection_level(mask, z, a, b, uv)
        for level in (-2.5, -1.0, 0.0, 0.37, 1.2, 2.0, 3.3, 5.0):
            zs = sea_level.connected_initial_zs(level, mask, z, a, b, uv)
            np.testing.assert_array_equal(
                conn < level, zs > sea_level.DRY, err_msg=f"level {level}"
            )

    def test_inactive_and_unreached_are_inf(self):
        a, b = _grid(4, 1)
        mask = np.array([2, 1, 0, 1])
        z = np.zeros(4, np.float32)
        conn = lake_flag.connection_level(mask, z, a, b, np.zeros(len(a), np.float32))
        self.assertTrue(np.isinf(conn[2]) and np.isinf(conn[3]))
        self.assertEqual(conn[:2].tolist(), [0.0, 0.0])


class TestRule(unittest.TestCase):
    """A 1-D transect, 50 m cells, x = 25, 75, ...:

    forced ocean (0-3) | beach (4) | DUNE SILL between 5 and 6 | lake (6-9) | upland (10)
    """

    def _case(self, sill: float, peak: float = 2.8):
        n = 11
        a, b = _grid(n, 1)
        mask = np.array([2] * 4 + [1] * 7)
        z = np.array(
            [-8, -6, -4, -2, 0.5, 1.0, -0.5, -1.0, -1.0, -0.5, 4.0], np.float32
        )
        uv = np.maximum(z[a], z[b]) + np.float32(0.01)
        uv[5] = sill  # the 5|6 face: the dune between beach and lake
        conn = lake_flag.connection_level(mask, z, a, b, uv)
        zsmax = np.where(np.arange(n) < 6, peak, 0.4).astype(np.float32)
        fx = 25.0 + 50.0 * np.arange(n)
        return dict(
            face_x=fx,
            face_y=np.zeros(n),
            mask=mask,
            z_zmin=z,
            conn=conn,
            zsmax=zsmax,
            sea_level0=0.0,
        )

    def _flag(self, run, x):
        return lake_flag.flags(
            np.array([x]), np.array([0.0]), radius_m=30.0, sea_band_m=1000.0, **run
        )

    def test_sill_above_sea_peak_is_flagged(self):
        df = self._flag(self._case(sill=3.1), x=375.0)  # in the lake
        self.assertTrue(bool(df.lake_outlet_blocked[0]))
        self.assertAlmostEqual(df.lake_connect_level_m[0], 3.1, places=5)
        self.assertAlmostEqual(df.lake_sea_peak_m[0], 2.8, places=5)

    def test_sill_below_sea_peak_is_not_flagged(self):
        df = self._flag(self._case(sill=2.5), x=375.0)
        self.assertFalse(bool(df.lake_outlet_blocked[0]))
        self.assertAlmostEqual(df.lake_connect_level_m[0], 2.5, places=5)

    def test_open_coast_mark_is_not_flagged(self):
        df = self._flag(self._case(sill=3.1), x=225.0)  # on the beach face
        self.assertFalse(bool(df.lake_outlet_blocked[0]))

    def test_mark_above_the_sea_peak_is_not_flagged(self):
        # upland face (z 4.0 > peak): a run-up shortfall, not a closed outlet
        df = self._flag(self._case(sill=3.1), x=525.0)
        self.assertFalse(bool(df.lake_outlet_blocked[0]))
        self.assertGreaterEqual(df.lake_floor_m[0], df.lake_sea_peak_m[0])


class TestHeadlineKeys(unittest.TestCase):
    """``metrics.lake_blocked_keys``: the headline again without the flagged marks."""

    def test_excl_keys_and_ids(self):
        import tempfile
        from pathlib import Path
        from unittest import mock

        import geopandas as gpd
        import pandas as pd

        from nj_sfincs.validate import metrics

        hwm = gpd.GeoDataFrame(
            {"hwm_id": ["1", "2", "3", "4"]},
            geometry=gpd.points_from_xy([0, 1, 2, 3], [0, 0, 0, 0]),
            crs=32618,
        )
        resid = np.array([0.1, -2.3, -0.2, 9.9])
        head = np.array([True, True, True, False])  # mark 4 is not scored (q > 2)
        wet = np.array([True, False, True, True])
        flagged = pd.DataFrame({"lake_outlet_blocked": [False, True, False, True]})
        with tempfile.TemporaryDirectory() as d:
            Path(d, "sfincs.inp").write_text("epsg                 = 32618\n")
            with mock.patch.object(
                lake_flag, "lake_outlet_blocked", return_value=flagged
            ):
                k = metrics.lake_blocked_keys(d, hwm, resid, head, wet, 50.0)
        self.assertEqual(k["hwm_n_lake_outlet_blocked"], 1)  # 4 is flagged, not scored
        self.assertEqual(k["hwm_lake_outlet_blocked_ids"], "[2]")
        self.assertEqual(k["hwm_n_scored_excl_lake_blocked"], 2)
        self.assertEqual(k["hwm_n_dry_scored_excl_lake_blocked"], 0)
        self.assertAlmostEqual(k["hwm_bias_scored_excl_lake_blocked_m"], -0.05)
        self.assertAlmostEqual(
            k["hwm_rmse_scored_excl_lake_blocked_m"], np.sqrt((0.01 + 0.04) / 2)
        )
        self.assertEqual(k["hwm_within0.5_scored_excl_lake_blocked"], 1.0)
        self.assertIn("window50m", k["hwm_lake_flag_rule"])


if __name__ == "__main__":
    unittest.main()
