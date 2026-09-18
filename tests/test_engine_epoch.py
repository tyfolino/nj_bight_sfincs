"""The engine epoch in the v3 registry (nj_sfincs/experiments.py, 2026-09-11).

Pins: the premier is ONE constant off the shelf-steps wave config (fw 0.01, IG on); every
attribution arm differs from the premier in exactly the fields its name says; union names
are alphabetical; the retired arms are gone; and scripts/stamp_metrics_epoch.py fills the
epoch columns and touches nothing else.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from dataclasses import asdict, replace
from pathlib import Path

import pandas as pd

from nj_sfincs.config import ROOT
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
        }
        # The old band is one lever, three fields (2026-09-13): the band table, the
        # support-point count, and the open-coast demotion. Every renamed old-band run
        # differs from the premier by those three plus what its name says.
        band = {"snapwave_domain", "wave_n_support", "open_coast_max_y"}
        expect.update(
            {
                "wave-band-sandy-hook": band,
                "wave-band-sandy-hook+wave-fw02": band | {"snapwave_fw"},
                "wave-band-sandy-hook+wave-noig": band | {"wave_igwaves"},
                "bed-nobuildings+wave-band-sandy-hook": band | {"subgrid_from"},
                "bed-nobuildings+wave-band-sandy-hook+wave-fw02+wave-noig": band
                | {"snapwave_fw", "wave_igwaves", "subgrid_from"},
            }
        )
        self.assertEqual(
            V3["wave-band-sandy-hook"].waves.snapwave_domain, "v3_shelf_steps"
        )
        for name, fields in expect.items():
            self.assertEqual(_diff_fields(V3[name], PREMIER), fields, name)
        self.assertEqual(V3["wave-fw02"].waves.snapwave_fw, 0.02)
        self.assertFalse(V3["wave-noig"].waves.wave_igwaves)
        self.assertTrue(V3["wave-wavemaker"].waves.wavemaker)
        self.assertTrue(V3["wave-wavemaker"].waves.wave_igwaves)
        self.assertTrue(V3["wave-wavemaker"].waves.wavemaker_line.exists())

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
        ):
            self.assertNotIn(old, V3, old)


def _load_stamp():
    spec = importlib.util.spec_from_file_location(
        "stamp_metrics_epoch", ROOT / "scripts" / "stamp_metrics_epoch.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestStampTouchesOnlyEpochColumns(unittest.TestCase):
    def test_stamp_and_diff(self):
        S = _load_stamp()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for arm, wind in (("old-arm", "1"), ("off-arm", "0")):
                d = root / arm
                d.mkdir()
                (d / "sfincs.inp").write_text(f"snapwave = 1\nsnapwave_wind = {wind}\n")
                (d / "sfincs.log").write_text(
                    "Build-Revision: $Rev: v2.3.3 mt. Faber+\n"
                )
            (root / "_retired" / "gone-arm").mkdir(parents=True)
            (root / "_retired" / "gone-arm" / "sfincs.inp").write_text("snapwave = 0\n")
            df = pd.DataFrame(
                {"hwm_rmse_m": [0.38, 0.40, 0.41, 0.5], "domain": ["v3"] * 4},
                index=["old-arm", "off-arm", "gone-arm", "vanished"],
            )
            new = S.stamp(df, root)
            self.assertEqual(new.loc["old-arm", "snapwave_direction"], "wind")
            self.assertEqual(new.loc["off-arm", "snapwave_direction"], "imposed")
            self.assertIn("faber", new.loc["old-arm", "engine"])
            self.assertEqual(new.loc["gone-arm", "retired_to"], "_retired/gone-arm")
            self.assertEqual(new.loc["gone-arm", "snapwave_direction"], "off")
            self.assertEqual(new.loc["vanished", "engine"], "unknown (run dir gone)")
            lines = S.diff(df, new)
            self.assertEqual(len(lines), 4 * 4)  # four epoch cells per row
            self.assertTrue(new["hwm_rmse_m"].equals(df["hwm_rmse_m"]))
            # a changed number is refused
            bad = new.copy()
            bad.loc["old-arm", "hwm_rmse_m"] = 0.0
            with self.assertRaises(AssertionError):
                S.diff(df, bad)


if __name__ == "__main__":
    unittest.main()
