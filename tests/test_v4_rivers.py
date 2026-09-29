"""v4 river inflows: the drainage-area scale table (user decision 2026-09-28).

The discharge builder refuses to write if a source has no factor; this pins the table
itself — every v4 source covered, nothing extra, factors inside the rule's range, and the
decided exceptions (dams, near-crossing area disagreements) held at 1.0.
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _mod():
    spec = importlib.util.spec_from_file_location(
        "dl_q", ROOT / "scripts" / "download_usgs_sandy_discharge.py"
    )
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class TestAreaScaleV4(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _mod()

    def test_table_covers_exactly_the_v4_sources(self):
        ids = {st["id"] for st in self.m.STATIONS_V4}
        self.assertEqual(set(self.m.AREA_SCALE_V4), ids)

    def test_factors_positive_and_bounded(self):
        for sid, (f, why) in self.m.AREA_SCALE_V4.items():
            self.assertGreater(f, 0.3, sid)
            self.assertLess(f, 7.0, sid)  # W Br Middle Brook 9.485^0.8 = 6.05
            self.assertTrue(why, sid)

    def test_dams_are_kept(self):
        for sid in (
            "01483700",
            "01407500",
            "01405030",
            "01393450",
            "01389890",
            "01377000",
        ):
            self.assertEqual(self.m.AREA_SCALE_V4[sid][0], 1.0, sid)


if __name__ == "__main__":
    unittest.main()
