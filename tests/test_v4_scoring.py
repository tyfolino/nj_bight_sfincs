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


if __name__ == "__main__":
    unittest.main()
