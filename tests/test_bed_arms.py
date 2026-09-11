"""``bed-*`` arms: a bed edit reaches a run ONLY through ``Experiment.subgrid_from``.

``build_static`` copies the frozen mesh and returns early, so a bed change routed through
the template builder is a silent no-op (CLAUDE.md §5). These tests pin the contract that
keeps that path closed: every ``bed-`` arm runs a DIFFERENT subgrid from its premier,
nothing else does, and the naming convention is the one ``scripts/rebuild_subgrid.py``
enforces.

Nothing here reads a run dir or a raster.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from nj_sfincs.config import Experiment, WaveConfig
from nj_sfincs.experiments import EXPERIMENTS_BY_DOMAIN


class TestBedArms(unittest.TestCase):
    def test_default_is_no_subgrid_swap(self):
        e = Experiment("x", WaveConfig(use_waves=False))
        self.assertIsNone(e.subgrid_from)

    def test_bed_arms_and_only_bed_arms_change_the_subgrid(self):
        """A `bed-` arm's subgrid source differs from its domain's PREMIER; no other arm's
        does. (Until 2026-09-11 the premier always ran the sealed template's subgrid, so
        this read "bed- arms name a source, nothing else does"; since the engine epoch
        the v3 premier itself carries `_subgrid_buildings` and `bed-nobuildings` is the
        arm that swaps back to the template — the contract is relative to the premier.)"""
        for dom, arms in EXPERIMENTS_BY_DOMAIN.items():
            prem = arms.get("naccs-premier")
            base = prem.subgrid_from if prem is not None else None
            for name, exp in arms.items():
                with self.subTest(domain=dom, arm=name):
                    if name.startswith("bed-") or "+bed-" in name:
                        self.assertNotEqual(
                            exp.subgrid_from,
                            base,
                            f"{dom}/{name} is a bed- arm on the premier's own subgrid",
                        )
                    else:
                        self.assertEqual(
                            exp.subgrid_from,
                            base,
                            f"{dom}/{name} changes the subgrid but is not named bed-*",
                        )

    def test_subgrid_source_naming(self):
        for dom, arms in EXPERIMENTS_BY_DOMAIN.items():
            for name, exp in arms.items():
                if exp.subgrid_from is None:
                    continue
                with self.subTest(domain=dom, arm=name):
                    self.assertTrue(exp.subgrid_from.startswith("_subgrid_"))
                    self.assertNotIn("/", exp.subgrid_from)

    def test_swap_refuses_a_source_without_the_merged_dep(self):
        """The scorer falls back to lev3 SILENTLY; staging is where it must be loud."""
        import tempfile

        import run_experiments as rx

        with tempfile.TemporaryDirectory() as td:
            tpl, src = Path(td) / "tpl", Path(td) / "_subgrid_x"
            for d in (tpl, src):
                (d / "subgrid").mkdir(parents=True)
            # template without a merged dep (v1.5-like): nothing to match, no refusal
            self.assertIsNone(rx.missing_merged_dep(src, tpl))
            (tpl / rx.MERGED_DEP).write_bytes(b"x")
            msg = rx.missing_merged_dep(src, tpl)
            self.assertIsNotNone(msg)
            self.assertIn("dep_subgrid_merged.tif", msg)
            self.assertIn("build_merged_subgrid_dep", msg)
            (src / rx.MERGED_DEP).write_bytes(b"x")
            self.assertIsNone(rx.missing_merged_dep(src, tpl))

    def test_hwm_count_mismatch_is_flagged_not_hidden(self):
        import pandas as pd

        import run_experiments as rx

        df = pd.DataFrame(
            {"hwm_n_scored": [94, 94, 83, float("nan")]},
            index=["naccs-premier", "wave-stwave", "bed-buildings", "BRACKET+x"],
        )
        lines = rx.hwm_count_mismatches(df)
        self.assertEqual(len(lines), 1)
        self.assertIn("bed-buildings", lines[0])
        self.assertIn("83", lines[0])
        self.assertEqual(rx.hwm_count_mismatches(df.drop(index="naccs-premier")), [])
        self.assertEqual(rx.hwm_count_mismatches(pd.DataFrame(index=["a"])), [])

    def test_v3_premier_carries_the_buildings_subgrid(self):
        """Since the 2026-09-11 engine epoch the PREMIER runs on the buildings subgrid and
        `bed-nobuildings` is the one-field attribution arm (the old `bed-buildings` arm is
        retired)."""
        v3 = EXPERIMENTS_BY_DOMAIN["v3"]
        self.assertEqual(v3["naccs-premier"].subgrid_from, "_subgrid_buildings")
        self.assertIsNone(v3["bed-nobuildings"].subgrid_from)
        self.assertEqual(v3["bed-nobuildings"].waves, v3["naccs-premier"].waves)
        self.assertTrue(v3["naccs-premier"].rain)
        self.assertEqual(
            v3["naccs-nowaves"].subgrid_from,
            "_subgrid_buildings",
            "waves-on/off must stay ONE flag",
        )


if __name__ == "__main__":
    unittest.main()
