"""The engine epoch in the v3 registry (nj_sfincs/experiments.py, 2026-09-11).

Pins: the premier is ONE constant off the shelf-steps wave config (fw 0.01, IG on); every
attribution arm differs from the premier in exactly the fields its name says; union names
are alphabetical; and the retired arms are gone. (The one-off epoch stamp,
``scripts/stamp_metrics_epoch.py``, and its test were retired 2026-09-30, in git history —
the migration ran on 2026-09-11 and every row carries its columns.)
"""

from __future__ import annotations

import unittest
from dataclasses import asdict, replace

from nj_sfincs.experiments import _V3_SHELF_STEPS_WAVES, EXPERIMENTS_BY_DOMAIN

V3 = EXPERIMENTS_BY_DOMAIN["v3"]
PREMIER = V3["naccs-premier"]


def _diff_fields(a, b) -> set[str]:
    da, db = asdict(a.waves), asdict(b.waves)
    out = {k for k in da if da[k] != db[k]}
    if a.subgrid_from != b.subgrid_from:
        out.add("subgrid_from")
    if a.rain != b.rain:
        out.add("rain")
    if a.waterlevel_geodataset != b.waterlevel_geodataset:
        out.add("waterlevel_geodataset")
    if a.wind_scale != b.wind_scale:
        out.add("wind_scale")
    return out


class TestPremierConstant(unittest.TestCase):
    def test_premier_is_shelf_steps_plus_fw01_plus_ig(self):
        # 2026-09-17: the premier carries the APEX band (east leg to the Long Island
        # shore, +3 support points, open-coast demotion lifted) — user decision after
        # the paired −0.0145 m [−0.0249, −0.0053] read (STATUS 09-17).
        self.assertEqual(
            PREMIER.waves,
            replace(
                _V3_SHELF_STEPS_WAVES,
                snapwave_fw=0.01,
                wave_igwaves=True,
                snapwave_domain="v3_shelf_steps_apex",
                wave_n_support=63,
                open_coast_max_y=float("inf"),
            ),
        )
        self.assertTrue(PREMIER.waves.wave_wind)
        self.assertEqual(PREMIER.waves.sector(), 360)
        self.assertEqual(PREMIER.waves.wave_n_support, 63)
        self.assertEqual(PREMIER.subgrid_from, "_subgrid_buildings")
        self.assertIsNone(PREMIER.bracket)

    def test_attribution_arms_are_one_field_each(self):
        expect = {
            "wave-fw02": {"snapwave_fw"},
            "wave-noig": {"wave_igwaves"},
            "bed-nobuildings": {"subgrid_from"},
            # 2026-09-18: the IG lever is the LINE (two fields: the switch and its path).
            "wave-wavemaker": {"wavemaker", "wavemaker_line"},
            # 2026-09-20: the wind-sensitivity probe on top of the wavemaker line.
            "wave-wavemaker+wind-x110": {"wavemaker", "wavemaker_line", "wind_scale"},
            # 2026-09-30: the wave cost tests. Wind off pins the sector so it is ONE
            # physics change (without it the sector would narrow to 180° as well).
            "wave-dt3600+wave-dtheta10+wave-noig": {
                "dtwave",
                "snapwave_dtheta",
                "wave_igwaves",
            },
            "wave-nowind": {"wave_wind", "snapwave_sector"},
            "wave-dt3600+wave-dtheta10+wave-noig+wave-nowind": {
                "dtwave",
                "snapwave_dtheta",
                "wave_igwaves",
                "wave_wind",
                "snapwave_sector",
            },
        }
        for name, fields in expect.items():
            self.assertEqual(_diff_fields(V3[name], PREMIER), fields, name)
        self.assertEqual(V3["wave-fw02"].waves.snapwave_fw, 0.02)
        for name in ("wave-nowind", "wave-dt3600+wave-dtheta10+wave-noig+wave-nowind"):
            self.assertFalse(V3[name].waves.wave_wind, name)
            self.assertEqual(V3[name].waves.sector(), 360, name)
        self.assertFalse(V3["wave-noig"].waves.wave_igwaves)
        self.assertTrue(V3["wave-wavemaker"].waves.wavemaker)
        self.assertTrue(V3["wave-wavemaker"].waves.wave_igwaves)
        self.assertTrue(V3["wave-wavemaker"].waves.wavemaker_line.exists())
        self.assertEqual(V3["wave-wavemaker+wind-x110"].wind_scale, 1.10)
        self.assertEqual(PREMIER.wind_scale, 1.0)
        self.assertEqual(V3["wave-wavemaker"].wind_scale, 1.0)

    def test_nowaves_shares_the_premier_subgrid(self):
        self.assertFalse(V3["naccs-nowaves"].waves.use_waves)
        self.assertEqual(V3["naccs-nowaves"].subgrid_from, PREMIER.subgrid_from)

    def test_union_names_are_alphabetical(self):
        for name in V3:
            parts = name.split("+")
            self.assertEqual(parts, sorted(parts), name)

    def test_retired_arms_are_gone(self):
        for old in (
            "wave-stwave",
            "diag-premier-norain",
            "bed-buildings",
            "wave-shelf-steps",
            "wave-fw01+wave-shelf-steps",
            "wave-nowind+wave-shelf-steps",
            "BRACKET+setup-stockdon",
            "wave-apex",  # promoted INTO the premier 2026-09-17
            "bed-nobuildings+wave-fw02+wave-noig",  # renamed …+wave-band-sandy-hook+…
            # the five old-band runs, retired 2026-09-21, out of the registry 09-22
            "wave-band-sandy-hook",
            "wave-band-sandy-hook+wave-fw02",
            "wave-band-sandy-hook+wave-noig",
            "bed-nobuildings+wave-band-sandy-hook",
            "bed-nobuildings+wave-band-sandy-hook+wave-fw02+wave-noig",
        ):
            self.assertNotIn(old, V3, old)


if __name__ == "__main__":
    unittest.main()
