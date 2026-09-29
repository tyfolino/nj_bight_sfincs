"""Observations are never bridged across an outage (``validate.metrics._in_obs_gap``).

2026-09-29 (user): the gauge panels drew straight lines through USGS outages, because
``gauge_series_frame`` interpolated over the finite samples only. Pins that a model time
inside a gap wider than the tolerance is masked, that ordinary sampling and a single
dropped sample are not, and that a time sitting exactly on a sample survives.
"""

from __future__ import annotations

import unittest

import numpy as np

from nj_sfincs.validate.metrics import _in_obs_gap, _obs_gap_tol_s


class TestObsGaps(unittest.TestCase):
    def setUp(self):
        six = 360.0
        a = np.arange(0, 10) * six  # 0 .. 54 min, 6-min sampling
        b = 5 * 3600.0 + np.arange(0, 10) * six  # resumes after a ~4 h outage
        self.xs = np.r_[a, b]

    def test_tolerance_floor_and_scale(self):
        self.assertEqual(_obs_gap_tol_s(np.arange(0, 10) * 360.0), 1800.0)
        self.assertEqual(_obs_gap_tol_s(np.arange(0, 10) * 900.0), 2700.0)

    def test_outage_is_masked_and_samples_are_not(self):
        xt = np.array([0.0, 600.0, 3 * 3600.0, 5 * 3600.0, 5 * 3600.0 + 400.0])
        got = _in_obs_gap(xt, self.xs)
        np.testing.assert_array_equal(got, [False, False, True, False, False])

    def test_one_dropped_sample_is_bridged(self):
        xs = np.delete(np.arange(0, 20) * 360.0, 7)  # a 12-min hole < 30 min
        self.assertFalse(_in_obs_gap(np.array([7 * 360.0]), xs).any())


if __name__ == "__main__":
    unittest.main()
