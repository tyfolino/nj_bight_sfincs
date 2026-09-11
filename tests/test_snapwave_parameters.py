"""The SnapWave parameter sheet (nj_sfincs/snapwave_params.py, scripts/snapwave_parameters.py).

Pins: every engine key is documented and printed; hydromt's subset is a subset; a wind-on
run on the unpatched engine is flagged for the direction bug (FINDINGS §43) and a run on
the patched engine is not; an absent key is reported as the engine default, marked.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from nj_sfincs import snapwave_params as P
from nj_sfincs.config import ROOT


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "snapwave_parameters", ROOT / "scripts" / "snapwave_parameters.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = (
        mod  # dataclasses resolve postponed annotations via sys.modules
    )
    spec.loader.exec_module(mod)
    return mod


INP_WIND_ON = (
    "tref                 = 20121028 000000\n"
    "snapwave             = 1\n"
    "snapwave_wind        = 1\n"
    "snapwave_igwaves     = 0\n"
    "snapwave_fw          = 0.02\n"
    "snapwave_bndfile     = snapwave.bnd\n"
)
LOG_OLD = "Build-Revision: $Rev: v2.3.3 mt. Faber+\nBuild-Date: $Date: 2025-05-12\n"
LOG_FIXED = "Build-Revision: $Rev: v2.3.3 mt. Faber+ nj-winddir-fix-1\n"


class TestTables(unittest.TestCase):
    def test_every_engine_key_has_a_meaning(self):
        missing = [k for k in P.ENGINE_DEFAULTS_V233 if k not in P.MEANINGS]
        self.assertEqual(missing, [])

    def test_hydromt_keys_are_engine_keys(self):
        self.assertTrue(set(P.HYDROMT_DEFAULTS) <= set(P.ENGINE_DEFAULTS_V233))
        self.assertTrue(set(P.RAW_APPEND_ONLY) <= set(P.ENGINE_DEFAULTS_V233))

    def test_the_two_surprising_defaults(self):
        """The two engine defaults this repo has always overridden without knowing it."""
        self.assertEqual(P.ENGINE_DEFAULTS_V233["snapwave_fw"], 0.01)
        self.assertEqual(P.ENGINE_DEFAULTS_V233["snapwave_igwaves"], 1)

    def test_every_group_starts_on_a_real_key(self):
        for _, first in P.GROUPS:
            self.assertIn(first, P.ENGINE_DEFAULTS_V233)


class TestDirectionFlag(unittest.TestCase):
    def test_truth_table(self):
        on = {"snapwave": "1", "snapwave_wind": "1"}
        self.assertTrue(P.has_direction_bug(on, "$Rev: v2.3.3 mt. Faber+"))
        self.assertTrue(
            P.has_direction_bug(on, None), "unknown engine = assume unpatched"
        )
        self.assertFalse(P.has_direction_bug(on, "v2.3.3 nj-winddir-fix-1"))
        self.assertFalse(
            P.has_direction_bug({"snapwave": "1", "snapwave_wind": "0"}, None)
        )
        self.assertFalse(
            P.has_direction_bug({"snapwave": "0", "snapwave_wind": "1"}, None)
        )


class TestScript(unittest.TestCase):
    def _run_dir(self, td: str, inp: str, log: str | None) -> Path:
        d = Path(td) / "arm"
        d.mkdir()
        (d / "sfincs.inp").write_text(inp)
        (d / "snapwave.bnd").write_text("1 2\n3 4\n5 6\n")
        if log is not None:
            (d / "sfincs.log").write_text(log)
        return d

    def test_one_row_per_engine_key_and_defaults_marked(self):
        S = _load_script()
        with tempfile.TemporaryDirectory() as td:
            run = S.read_run(self._run_dir(td, INP_WIND_ON, LOG_OLD))
            df = S.table([run])
        self.assertEqual(list(df["key"]), list(P.ENGINE_DEFAULTS_V233))
        row = df.set_index("key")["arm"]
        self.assertEqual(row["snapwave_fw"], "≠ 0.02")  # written, differs
        self.assertEqual(row["snapwave_igwaves"], "≠ 0")  # written, differs
        self.assertEqual(row["snapwave_gamma"], "0.7 *")  # absent → engine default
        self.assertEqual(row["snapwave_wind"], "≠ 1")
        self.assertEqual(run.n_support, 3)

    def test_caveat_fires_on_old_engine_only(self):
        S = _load_script()
        with tempfile.TemporaryDirectory() as td:
            old = S.read_run(self._run_dir(td, INP_WIND_ON, LOG_OLD))
            self.assertTrue(old.direction_bug)
            self.assertIn("inferred", old.engine_label)
            for fn in (S.render_text, S.render_md, S.render_html):
                self.assertIn("WIND", fn([old]))
        with tempfile.TemporaryDirectory() as td:
            new = S.read_run(self._run_dir(td, INP_WIND_ON, LOG_FIXED))
            self.assertFalse(new.direction_bug)
            self.assertNotIn("misdirected", S.render_md([new]))
        with tempfile.TemporaryDirectory() as td:
            off = S.read_run(self._run_dir(td, "snapwave = 0\n", LOG_OLD))
            self.assertFalse(off.direction_bug)
            self.assertEqual(
                S.table([off]).set_index("key")["arm"]["snapwave_fw"], "(off)"
            )

    def test_differences_lists_only_departures(self):
        S = _load_script()
        with tempfile.TemporaryDirectory() as td:
            run = S.read_run(self._run_dir(td, INP_WIND_ON, LOG_OLD))
            dd = S.differences([run])
        # The master switch and the boundary FILE names are what waves-on means, not a
        # lever, so they are left to the full table.
        self.assertEqual(
            set(dd["key"]), {"snapwave_wind", "snapwave_igwaves", "snapwave_fw"}
        )


if __name__ == "__main__":
    unittest.main()
