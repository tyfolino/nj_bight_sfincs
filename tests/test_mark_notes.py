"""Noted marks: ``HWM_MARK_NOTES`` plus the mark file's own ``note_kind`` (2026-11-18).

The nj2 mark file carries 10 notes; 6415 (run-up) and 6081 (questioned) were in the file but
not in ``HWM_MARK_NOTES``, so the ``*_excl_noted`` score kept them (the 2.0 audit,
logs/audit_2_0_hwm_2026-11-18/). The excl-noted keys now read both.
"""

import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from nj_sfincs.validate.metrics import HWM_MARK_NOTES, mark_note_kinds, noted_keys

ROOT = Path(__file__).resolve().parents[1]


class TestMarkNotes(unittest.TestCase):
    def test_file_notes_join_the_dict(self):
        hwm = pd.DataFrame(
            {
                "hwm_id": [6121, 6415, 6081, 1, 2],
                "note_kind": ["runup", "runup", "questioned", None, ""],
            }
        )
        kind = mark_note_kinds(hwm)
        self.assertEqual(list(kind), ["runup", "runup", "questioned", "", ""])

    def test_dict_wins_and_no_column_is_fine(self):
        hwm = pd.DataFrame({"hwm_id": ["6121", "7"]})
        self.assertEqual(list(mark_note_kinds(hwm)), [HWM_MARK_NOTES["6121"][0], ""])

    def test_noted_keys_drop_file_noted_marks(self):
        hwm = pd.DataFrame(
            {"hwm_id": ["6415", "8", "9"], "note_kind": ["runup", None, None]}
        )
        resid = np.array([-1.0, 0.1, -0.1])
        head = np.ones(3, bool)
        out = noted_keys(hwm, resid, head, np.ones(3, bool))
        self.assertEqual(out["hwm_n_scored_excl_noted"], 2)
        self.assertAlmostEqual(out["hwm_rmse_scored_excl_noted_m"], 0.1)
        self.assertEqual(out["hwm_noted_ids"], "[6415]")

    def test_nj2_mark_file_has_the_two_extra_notes(self):
        import geopandas as gpd

        f = ROOT / "data/validation_nj2/sandy_hwms_nj2.geojson"
        if not f.is_file():
            self.skipTest("nj2 mark file absent")
        hwm = gpd.read_file(f)
        kind = dict(zip(hwm["hwm_id"].astype(str), mark_note_kinds(hwm)))
        self.assertEqual(kind["6415"], "runup")
        self.assertEqual(kind["6081"], "questioned")
        self.assertEqual(sum(1 for v in kind.values() if v), 10)


if __name__ == "__main__":
    unittest.main()
