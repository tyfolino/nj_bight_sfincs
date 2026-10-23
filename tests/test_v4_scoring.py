"""v4 scoring inputs: the gauges and the HWM basin rules (2026-09-28).

The basin rules are FIRST-MATCH-WINS and the eight v4 rules sit in front of v3's, so the
property that matters is that no mark inside v3's ring changes basin — that is what keeps
v3 and v4 per-basin numbers comparable. Reads the real HWM file and rings; skips if absent.
"""

from __future__ import annotations

import os
import unittest

import numpy as np

from nj_sfincs import domain
from nj_sfincs.config import DATA


class _V4(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.get("NJ_DOMAIN")
        os.environ["NJ_DOMAIN"] = "v4"

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("NJ_DOMAIN", None)
        else:
            os.environ["NJ_DOMAIN"] = self._saved


def _labels(rules, x, y):
    out = np.full(len(x), "unassigned", dtype=object)
    for r in reversed(rules):
        out[r.matches(x, y)] = r.name
    return out


class TestV4Basins(_V4):
    def test_v3_marks_keep_their_basin_and_none_unassigned(self):
        import geopandas as gpd

        f = domain.V4.hwm_geojson
        if not (
            f.is_file() and domain.V3.region.is_file() and domain.V4.region.is_file()
        ):
            self.skipTest("HWM file or rings not on disk")
        h = gpd.read_file(f).to_crs(domain.V4.epsg)
        x, y = h.geometry.x.values, h.geometry.y.values
        r3 = gpd.read_file(domain.V3.region).to_crs(domain.V4.epsg).union_all()
        r4 = gpd.read_file(domain.V4.region).to_crs(domain.V4.epsg).union_all()
        in3 = np.array([r3.contains(p) for p in h.geometry])
        in4 = np.array([r4.contains(p) for p in h.geometry])
        l3 = _labels(domain.V3.hwm_rules, x, y)
        l4 = _labels(domain.V4.hwm_rules, x, y)
        moved = np.flatnonzero(in3 & (l3 != l4))
        self.assertEqual(
            len(moved), 0, f"v3 marks re-basined: {[(l3[i], l4[i]) for i in moved]}"
        )
        self.assertFalse(np.any(in4 & (l4 == "unassigned")))

    def test_v4_rules_lead_and_v3_rules_follow_verbatim(self):
        n = len(domain.V4.hwm_rules) - len(domain.V3.hwm_rules)
        self.assertEqual(domain.V4.hwm_rules[n:], domain.V3.hwm_rules)


class TestV4Gauges(_V4):
    def test_names_unique_and_no_substring_clash(self):
        names = [g.name for g in domain.V4.obs_gauges]
        self.assertEqual(len(names), len(set(names)))
        clash = [(a, b) for a in names for b in names if a != b and a in b]
        self.assertEqual(clash, [], "his metrics match stations by SUBSTRING")

    def test_v3_gauges_carried_verbatim(self):
        self.assertEqual(
            domain.V4.obs_gauges[: len(domain.V3.obs_gauges)], domain.V3.obs_gauges
        )

    def test_every_new_station_is_in_its_obs_file(self):
        import xarray as xr

        for g in domain.V4.obs_gauges[len(domain.V3.obs_gauges) :]:
            f = DATA / g.obs_file
            if not f.is_file():
                self.skipTest(f"{f} not on disk")
            with xr.open_dataset(f) as ds:
                self.assertIn(
                    int(g.obs_station), set(int(s) for s in ds.stations.values), g.name
                )

    def test_record_ends_on_every_gauge_that_missed_the_crest(self):
        for g in domain.V4.obs_gauges[len(domain.V3.obs_gauges) :]:
            if not g.survives_crest:
                self.assertIsNotNone(g.record_ends, g.name)


class TestGaugeFacts20261023(unittest.TestCase):
    """The Great Kills obs correction + published crests (2026-10-23): on v3 and the v4
    family only, applied once in the shared obs loader, scored beside the prefail pair."""

    PUB_V3 = (
        "usgs_tidal_ship_bottom",
        "usgs_tidal_tuckerton",
        "usgs_tidal_absecon_creek",
        "usgs_tidal_inside_thorofare",
        "usgs_tidal_sea_isle",
        "usgs_tidal_avalon",
        "usgs_tidal_stone_harbor",
        "usgs_tidal_shark_river",
        "usgs_tidal_sea_bright",
        "usgs_tidal_absecon_channel",
    )
    PUB_V4 = PUB_V3 + (
        "usgs_tidal_bivalve",
        "usgs_tidal_greenwich",
        "usgs_tidal_pt_pleasant_canal",
        "usgs_tidal_manasquan_pp",
        "usgs_tidal_keansburg",
    )

    def test_which_domains_carry_them(self):
        for dn, pub in (
            ("v3", self.PUB_V3),
            ("v4", self.PUB_V4),
            ("v4_refreeze", self.PUB_V4),
        ):
            gs = {g.name: g for g in domain.DOMAINS[dn].obs_gauges}
            self.assertEqual(gs["sss_great_kills"].obs_offset_m, -0.34, dn)
            got = {n for n, g in gs.items() if g.published_peak is not None}
            self.assertEqual(got, set(pub), dn)
        for dn in ("v1_monmouth", "v1_5_raritan"):  # frozen, pinned by the port gate
            for g in domain.DOMAINS[dn].obs_gauges:
                self.assertEqual(g.obs_offset_m, 0.0, (dn, g.name))
                self.assertIsNone(g.published_peak, (dn, g.name))

    def test_published_crests_are_after_the_hole_opens(self):
        for g in domain.DOMAINS["v4_refreeze"].obs_gauges:
            if g.published_peak is None:
                continue
            m, t, src = g.published_peak
            self.assertTrue(1.5 < m < 4.5, g.name)
            self.assertGreaterEqual(t, "2012-10-29 04:00", g.name)
            self.assertIn("OFR 2013-1043", src)

    def test_offset_is_applied_once_in_the_loader(self):
        from nj_sfincs.validate.metrics import _obs_series

        raw = {g.name: g for g in domain.V1_5_RARITAN.obs_gauges}["sss_great_kills"]
        cor = {g.name: g for g in domain.V3.obs_gauges}["sss_great_kills"]
        if not (DATA / raw.obs_file).is_file():
            self.skipTest("obs file not on disk")
        (t0, v0), (t1, v1) = _obs_series(raw), _obs_series(cor)
        np.testing.assert_array_equal(t0, t1)
        ok = np.isfinite(v0)
        np.testing.assert_allclose(v1[ok] - v0[ok], -0.34, atol=1e-9)

    def test_scorer_writes_the_published_pair(self):
        from dataclasses import replace
        from types import SimpleNamespace
        from unittest import mock

        from nj_sfincs.validate import metrics

        g = replace(
            domain.ObsGauge("x", 0.0, 0.0, obs_file="f", obs_station=1),
            record_ends="2012-10-29 03:54",
            published_peak=(2.0, "2012-10-30 00:00", "test"),
            obs_offset_m=-0.1,
        )
        t = np.arange(
            "2012-10-28T00",
            "2012-10-31T00",
            np.timedelta64(1, "h"),
            dtype="datetime64[s]",
        )
        crest = np.datetime64("2012-10-30T01:00", "s")
        mv = 2.3 - np.abs((t - crest) / np.timedelta64(1, "h")) * 0.05
        ov = np.where(t <= np.datetime64("2012-10-29T03:54"), mv - 0.5, np.nan)
        with (
            mock.patch.object(
                metrics._domain, "active", return_value=SimpleNamespace(obs_gauges=[g])
            ),
            mock.patch.object(metrics, "_obs_series", return_value=(t, ov)),
            mock.patch.object(metrics, "his_series", return_value=(t, mv)),
            mock.patch.object(metrics, "his_bed", return_value=0.0),
        ):
            out = metrics.gauge_peak_metrics(None, None)
        self.assertAlmostEqual(out["peak_pub_x_m"], 2.0)
        self.assertAlmostEqual(out["peak_err_pub_x_m"], 0.3, places=6)  # full peak 2.3
        self.assertAlmostEqual(out["peak_lag_pub_x_min"], 60.0)
        self.assertEqual(out["obs_offset_x_m"], -0.1)
        self.assertIn("peak_err_prefail_x_m", out)  # beside, not instead of


if __name__ == "__main__":
    unittest.main()
