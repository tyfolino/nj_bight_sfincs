"""``bed-*`` arms: a bed edit reaches a run ONLY through ``Experiment.subgrid_from``.

``build_static`` copies the frozen mesh and returns early, so a bed change routed through
the template builder is a silent no-op (CLAUDE.md §5). These tests pin the contract that
keeps that path closed: every ``bed-`` arm names a ``_subgrid_*`` source, nothing else
does, and the naming convention is the one ``scripts/rebuild_subgrid.py`` enforces.

Nothing here reads a run dir or a raster.
"""

from __future__ import annotations

import unittest

from nj_sfincs.config import Experiment, WaveConfig
from nj_sfincs.experiments import EXPERIMENTS_BY_DOMAIN


class TestBedArms(unittest.TestCase):
    def test_default_is_no_subgrid_swap(self):
        e = Experiment("x", WaveConfig(use_waves=False))
        self.assertIsNone(e.subgrid_from)

    def test_bed_arms_declare_a_subgrid_source(self):
        for dom, arms in EXPERIMENTS_BY_DOMAIN.items():
            for name, exp in arms.items():
                with self.subTest(domain=dom, arm=name):
                    if name.startswith("bed-") or "+bed-" in name:
                        self.assertIsNotNone(
                            exp.subgrid_from,
                            f"{dom}/{name} is a bed- arm with no subgrid_from: it would "
                            "run the premier's subgrid",
                        )
                    else:
                        self.assertIsNone(
                            exp.subgrid_from,
                            f"{dom}/{name} swaps its subgrid but is not named bed-*",
                        )

    def test_subgrid_source_naming(self):
        for dom, arms in EXPERIMENTS_BY_DOMAIN.items():
            for name, exp in arms.items():
                if exp.subgrid_from is None:
                    continue
                with self.subTest(domain=dom, arm=name):
                    self.assertTrue(exp.subgrid_from.startswith("_subgrid_"))
                    self.assertNotIn("/", exp.subgrid_from)

    def test_v3_bed_buildings_registered(self):
        exp = EXPERIMENTS_BY_DOMAIN["v3"]["bed-buildings"]
        self.assertEqual(exp.subgrid_from, "_subgrid_buildings")
        self.assertTrue(exp.waves.use_waves)  # premier physics, only the bed differs
        self.assertTrue(exp.rain)


if __name__ == "__main__":
    unittest.main()
