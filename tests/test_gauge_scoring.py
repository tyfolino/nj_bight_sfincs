"""Storm-tide sensor averaging and the creek-not-resolved gauge flag (user 2026-11-24)."""

from __future__ import annotations

import os
import unittest
from unittest import mock

import numpy as np

with mock.patch.dict(os.environ, {"NJ_DOMAIN": "v1_monmouth"}):
    from nj_sfincs import domain
    from nj_sfincs.validate import metrics


def _g(name, obs_var=None):
    return domain.ObsGauge(name, 0.0, 0.0, obs_var=obs_var)


def _times(n=60):
    return np.datetime64("2012-10-29T00:00") + (np.arange(n) * 10).astype(
        "timedelta64[m]"
    )


class TestStormtideAveraging(unittest.TestCase):
    def test_class_is_by_obs_var(self):
        self.assertTrue(_g("a", "stormtide_m").is_stormtide_sensor)
        self.assertFalse(_g("b", "waterlevel").is_stormtide_sensor)
        self.assertFalse(_g("c").is_stormtide_sensor)

    def test_centred_mean_cuts_a_spike_and_keeps_a_ramp(self):
        t = _times()
        v = np.full(t.size, 2.0)
        v[30] = 5.0  # one 10-min-wide spike
        _, sm = metrics.centred_mean(t, v)
        self.assertLess(np.nanmax(sm), 4.0)
        ramp = np.linspace(0, 1, t.size)
        _, sr = metrics.centred_mean(t, ramp)
        ok = np.isfinite(sr)
        self.assertTrue(ok[5:-5].all())
        np.testing.assert_allclose(sr[ok], ramp[ok], atol=1e-9)  # linear: unchanged

    def test_only_stormtide_gauges_are_averaged(self):
        t = _times()
        v = np.zeros(t.size)
        v[30] = 3.0
        _, a = metrics._match_obs_averaging(_g("s", "stormtide_m"), t, v)
        _, b = metrics._match_obs_averaging(_g("n", "waterlevel"), t, v)
        self.assertLess(np.nanmax(a), 3.0)
        self.assertEqual(np.nanmax(b), 3.0)


class TestCreekFlag(unittest.TestCase):
    def test_listed_names(self):
        self.assertEqual(
            set(domain.CREEK_NOT_RESOLVED_GAUGES),
            {"usgs_tidal_murderkill_frederica", "usgs_tidal_sluice_creek"},
        )
        self.assertTrue(_g("usgs_tidal_sluice_creek").creek_unresolved)
        self.assertFalse(_g("usgs_tidal_murderkill_bowers").creek_unresolved)

    def test_summary_excludes_flagged_but_keeps_their_row(self):
        class Dom:
            obs_gauges = (
                _g("good1"),
                _g("good2"),
                _g("usgs_tidal_sluice_creek"),
                _g("usgs_tidal_murderkill_frederica"),
            )

        row = {
            "peak_err_good1_m": 0.1,
            "peak_err_good2_m": -0.3,
            "peak_err_usgs_tidal_sluice_creek_m": -0.9,
            "peak_err_usgs_tidal_murderkill_frederica_m": 0.8,
        }
        s = metrics.gauge_peak_summary(row, Dom)
        self.assertEqual(s["gauge_peak_n"], 2)
        self.assertEqual(s["gauge_peak_n_excluded"], 2)
        self.assertAlmostEqual(s["gauge_peak_err_mean_m"], -0.1)
        self.assertAlmostEqual(s["gauge_peak_err_mae_m"], 0.2)
        self.assertIn("peak_err_usgs_tidal_sluice_creek_m", row)  # never deleted


if __name__ == "__main__":
    unittest.main()
