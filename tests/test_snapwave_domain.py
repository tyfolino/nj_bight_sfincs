"""The grid-aligned SnapWave boundary (nj_sfincs/snapwave_domain.py).

Synthetic base grid, no files. Pins the three things a solve would otherwise reveal
ten hours late: the band stops at the step table, boundary cells are the seaward EDGE
only (east / south / north outside, bottom row) and never SFINCS-active cells, and an
inner corner is the ONLY place an interior cell touches two boundary cells.
"""

from __future__ import annotations

import unittest

import numpy as np

from nj_sfincs import snapwave_domain as sd
from nj_sfincs.config import WaveConfig
from nj_sfincs.domain import SNAPWAVE_STEPS
from nj_sfincs.experiments import EXPERIMENTS_BY_DOMAIN


def _grid(nrows=8, ncols=10):
    """A level-1 grid: rows 1..nrows, cols 1..ncols; z = -20 everywhere; SFINCS active
    in cols 1..3 (the 'coast'); face ids row-major; 4-neighbour face_faces."""
    n, m = np.meshgrid(np.arange(1, nrows + 1), np.arange(1, ncols + 1), indexing="ij")
    n, m = n.ravel(), m.ravel()
    lev = np.ones_like(n)
    z = np.full(n.shape, -20.0)
    sm = np.where(m <= 3, 1, 0)
    idx = {(a, b): k for k, (a, b) in enumerate(zip(n, m))}
    ff = np.full((len(n), 8), np.nan)
    for k, (a, b) in enumerate(zip(n, m)):
        nb = [idx.get((a + 1, b)), idx.get((a - 1, b)), idx.get((a, b + 1)), idx.get((a, b - 1))]
        nb = [v for v in nb if v is not None]
        ff[k, : len(nb)] = nb
    return n, m, lev, z, sm, ff, idx


class TestBuildMask(unittest.TestCase):
    def setUp(self):
        self.n, self.m, self.lev, self.z, self.sm, self.ff, self.idx = _grid()
        # rows 1-4 out to column 6, rows 5-8 out to column 8: one inner corner at (5, 7)
        self.steps = sd.SnapWaveSteps("t", ((1, 4, 6), (5, 8, 8)), m_west=1, n_top=8)

    def test_band_is_bounded_by_the_table(self):
        swm, info = sd.build_snapwave_mask(self.n, self.m, self.lev, self.z, self.sm, self.steps, -10.0)
        self.assertEqual(int(swm[self.idx[(2, 6)]]), 2)  # east edge, rows 1-4
        self.assertEqual(int(swm[self.idx[(2, 7)]]), 0)  # outside
        self.assertEqual(int(swm[self.idx[(6, 8)]]), 2)
        self.assertEqual(int(swm[self.idx[(6, 9)]]), 0)
        self.assertEqual(info["n_sfincs_outside_band"], 0)

    def test_sfincs_cells_are_never_wave_boundary(self):
        swm, _ = sd.build_snapwave_mask(self.n, self.m, self.lev, self.z, self.sm, self.steps, -10.0)
        self.assertTrue(np.all(swm[self.sm > 0] == 1))

    def test_edges_are_east_south_north_and_bottom_row_only(self):
        swm, _ = sd.build_snapwave_mask(self.n, self.m, self.lev, self.z, self.sm, self.steps, -10.0)
        self.assertEqual(int(swm[self.idx[(1, 5)]]), 2)  # bottom row
        self.assertEqual(int(swm[self.idx[(5, 7)]]), 2)  # step: south neighbour outside
        self.assertEqual(int(swm[self.idx[(8, 7)]]), 2)  # top row: north outside
        self.assertEqual(int(swm[self.idx[(3, 5)]]), 1)  # interior
        self.assertEqual(int(swm[self.idx[(3, 4)]]), 1)  # no WEST rule
        self.assertEqual(int(swm[self.idx[(6, 4)]]), 1)

    def test_only_corners_touch_two_boundary_cells(self):
        swm, _ = sd.build_snapwave_mask(self.n, self.m, self.lev, self.z, self.sm, self.steps, -10.0)
        rr = sd.ring_report(self.ff, swm)
        two = set(rr["two_plus_faces"].tolist())
        # Exactly four: the step's inner corner produces TWO — (5, 6) has boundary to
        # its east (5, 7) and south (4, 6); (6, 7) has boundary to its south (5, 7) and
        # east (6, 8) — and the two outer corners where the forced bottom / top rows meet
        # the east column. On the real mesh the top row is demoted, so it is ~two per
        # step plus the bottom-right — 38 of 2,381 ring cells on v3, vs 2,580 before.
        self.assertEqual(
            two, {self.idx[(5, 6)], self.idx[(6, 7)], self.idx[(2, 5)], self.idx[(7, 7)]}
        )
        self.assertEqual(rr["n_one"], rr["n_ring"] - 4)

    def test_shallow_edge_cell_is_not_forced(self):
        z = self.z.copy()
        z[self.idx[(2, 6)]] = -8.0
        swm, info = sd.build_snapwave_mask(self.n, self.m, self.lev, z, self.sm, self.steps, -10.0)
        self.assertEqual(int(swm[self.idx[(2, 6)]]), 0)  # above mask_zmin: not even band
        z[self.idx[(2, 6)]] = -11.0
        swm, info = sd.build_snapwave_mask(self.n, self.m, self.lev, z, self.sm, self.steps, -10.0)
        self.assertEqual(int(swm[self.idx[(2, 6)]]), 1)  # band but too shallow for a boundary
        self.assertEqual(info["n_edge_too_shallow"], 1)

    def test_poke_through_is_counted(self):
        sm = self.sm.copy()
        sm[self.idx[(2, 7)]] = 1  # a SFINCS cell east of M=6
        _, info = sd.build_snapwave_mask(self.n, self.m, self.lev, self.z, sm, self.steps, -10.0)
        self.assertEqual(info["n_sfincs_outside_band"], 1)

    def test_table_must_tile(self):
        with self.assertRaises(ValueError):
            sd.SnapWaveSteps("bad", ((1, 4, 6), (6, 8, 8)), 1, 8).validate()
        with self.assertRaises(ValueError):
            sd.SnapWaveSteps("bad", ((1, 4, 6), (5, 7, 8)), 1, 8).validate()


class TestLevelIndexAndGeometry(unittest.TestCase):
    def test_level1_index(self):
        n1, m1 = sd.level1_index(np.array([1, 2, 3, 4, 5]), np.array([1, 2, 3, 4, 5]), np.array([1, 2, 2, 3, 3]))
        np.testing.assert_array_equal(n1, [1, 1, 2, 1, 2])
        np.testing.assert_array_equal(m1, [1, 1, 2, 1, 2])

    def test_face_xy_unrotated(self):
        x, y = sd.face_xy(np.array([1, 1]), np.array([1, 2]), np.array([1, 2]),
                          dict(x0=0.0, y0=0.0, dx=200.0, dy=200.0, rotation=0.0))
        np.testing.assert_allclose(x, [100.0, 150.0])
        np.testing.assert_allclose(y, [100.0, 50.0])

    def test_polyline_and_support_points(self):
        steps = sd.SnapWaveSteps("t", ((1, 4, 6), (5, 8, 8)), m_west=1, n_top=8)
        attrs = dict(x0=0.0, y0=0.0, dx=200.0, dy=200.0, rotation=0.0)
        poly = sd.boundary_polyline(steps, attrs)
        np.testing.assert_allclose(poly[0], [1600.0, 1600.0])  # top of the east segment
        np.testing.assert_allclose(poly[-1], [0.0, 0.0])  # bottom-west end
        bxy = np.array([[1500.0, y] for y in range(900, 1600, 200)] + [[1100.0, y] for y in range(100, 900, 200)])
        pts = sd.support_points(poly, bxy, 6)
        self.assertTrue(1 <= len(pts) <= 6)
        for p in pts:
            self.assertTrue(any(np.allclose(p, b) for b in bxy))


class TestRegistry(unittest.TestCase):
    def test_v3_table_validates(self):
        SNAPWAVE_STEPS["v3_shelf_steps"].validate()

    def test_arm_names_a_registered_table(self):
        for dom, arms in EXPERIMENTS_BY_DOMAIN.items():
            for name, exp in arms.items():
                if exp.waves.snapwave_domain is not None:
                    self.assertIn(exp.waves.snapwave_domain, SNAPWAVE_STEPS, f"{dom}/{name}")

    def test_default_is_off(self):
        self.assertIsNone(WaveConfig().snapwave_domain)


if __name__ == "__main__":
    unittest.main()
