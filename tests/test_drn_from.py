"""``Experiment.drn_from`` (2026-11-12): an arm's drainage structures (culverts) staged as ``sfincs.drn``.

First use: the Gloucester culverts (logs/culverts_drn_2026-11-12/), seven open highway culverts the bed reads as
solid embankments, on ``v4_refreeze_swz_v11`` paired with ``p4-nowaves``.
"""

from __future__ import annotations

import dataclasses
import os
import tempfile
import unittest
from pathlib import Path

from nj_sfincs import model, provenance
from nj_sfincs.config import Experiment
from nj_sfincs.experiments import EXPERIMENTS_BY_DOMAIN

GOOD = "472674.11 4405938.50 472672.48 4406038.50 2 9.17\n475950.48 4406654.25 475899.67 4406703.00 3 48.39\n"


class TestDrnFrom(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.d = Path(self._td.name)
        self.addCleanup(self._td.cleanup)
        self.run_dir = self.d / "run"
        self.run_dir.mkdir()
        (self.run_dir / "sfincs.inp").write_text(
            "tref                 = 20121028 000000\nsnapwave             = 0\n"
        )
        (self.run_dir / "provenance.txt").write_text("staged\n")
        self.src = self.d / "arm.drn"
        self.src.write_text(GOOD)

    def test_default_is_none(self):
        f = {x.name: x for x in dataclasses.fields(Experiment)}["drn_from"]
        self.assertIsNone(f.default)

    def test_good_file_parsed(self):
        rows = model.read_drn_from(self.src)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][4], 2)
        self.assertEqual(rows[1][4], 3)
        self.assertAlmostEqual(rows[1][5], 48.39)

    def test_malformed_refused(self):
        for bad in (
            "",
            "# a comment the engine would count as a structure\n" + GOOD,
            GOOD + "\n",  # a blank line: also a structure to the engine
            "0 0 10 0 4 5 0.5 0.02 -99 99 600\n",  # controlled gate: refused (0/0 under the sill)
            "0 0 10 0 2\n",
            "0 0 10 0 2 0\n",
            "0 0 0 0 2 5\n",
            "0 0 10 0 2 5 7\n",
            "x 0 10 0 2 5\n",
        ):
            f = self.d / "bad.drn"
            f.write_text(bad)
            with self.assertRaises(SystemExit, msg=repr(bad)):
                model.read_drn_from(f)
        with self.assertRaises(SystemExit):
            model.read_drn_from(self.d / "missing.drn")

    def test_apply_copies_keys_and_records(self):
        out = model.apply_drainage(self.run_dir, self.src)
        keys = model._inp_keys(self.run_dir / "sfincs.inp")
        self.assertEqual(keys["drnfile"], "sfincs.drn")
        self.assertEqual(keys["storeqdrain"], "1")
        self.assertEqual(keys["snapwave"], "0")
        self.assertEqual((self.run_dir / "sfincs.drn").read_text(), GOOD)
        self.assertEqual(out["n"], 2)
        self.assertEqual(out["types"], ["check_valve", "culvert"])
        prov = (self.run_dir / "provenance.txt").read_text()
        self.assertTrue(prov.startswith("staged\n"))
        self.assertIn("drn_from = ", prov)
        self.assertIn(out["md5"], prov)

    def test_new_inode(self):
        model.apply_drainage(self.run_dir, self.src)
        self.assertNotEqual(
            os.stat(self.run_dir / "sfincs.drn").st_ino, os.stat(self.src).st_ino
        )

    def test_refuses_a_second_set(self):
        model.apply_drainage(self.run_dir, self.src)
        with self.assertRaises(SystemExit):
            model.apply_drainage(self.run_dir, self.src)
        (self.run_dir / "sfincs.drn").unlink()
        with self.assertRaises(SystemExit):  # the key alone is enough
            model.apply_drainage(self.run_dir, self.src)

    def test_staged_after_every_writer(self):
        """On the written inp: after finalize and restore_diagnostics, which rewrite sfincs.inp."""
        text = (
            Path(model.__file__).resolve().parents[1] / "run_experiments.py"
        ).read_text()  # import needs NJ_DOMAIN
        src = text[text.index("def prepare_experiment(") :]
        src = src[: src.index("\ndef ", 1)]
        i_fin = src.index("model.finalize(")
        i_diag = src.index("model.restore_diagnostics(exp_dir)")
        i_drn = src.index("model.apply_drainage(exp_dir, exp.drn_from)")
        self.assertLess(i_fin, i_diag)
        self.assertLess(i_diag, i_drn)

    def test_label(self):
        self.assertEqual(provenance.drainage_label(self.run_dir), "none")
        model.apply_drainage(self.run_dir, self.src)
        lab = provenance.drainage_label(self.run_dir)
        self.assertTrue(lab.startswith("md5:"))
        self.assertIn("n=2 check_valve+culvert", lab)
        self.assertNotIn("log:", lab)
        (self.run_dir / "sfincs.log").write_text(
            " Reading sfincs.drn (2 drainage points found) ...\n"
        )
        self.assertTrue(provenance.drainage_label(self.run_dir).endswith(" log:2"))
        (self.run_dir / "sfincs.log").write_text(
            " Reading sfincs.drn (2 drainage points found) ...\n"
            "Warning ! For some sink/source drainage points no matching active grid cell was found!\n"
        )
        self.assertTrue(
            provenance.drainage_label(self.run_dir).endswith(" log:2 SKIPPED")
        )

    def test_gloucester_arm(self):
        arms = EXPERIMENTS_BY_DOMAIN["v4_refreeze_swz_v11"]
        exp = arms["p4-nowaves+struct-culverts-gloucester"]
        ref = arms["p4-nowaves"]
        self.assertFalse(exp.waves.use_waves)
        self.assertEqual(exp.subgrid_from, ref.subgrid_from)
        self.assertEqual(exp.weir_from, ref.weir_from)
        self.assertIsNone(ref.drn_from)
        rows = model.read_drn_from(exp.drn_from)
        self.assertEqual(len(rows), 7)
        self.assertEqual({r[4] for r in rows}, {2})
        diff = [
            f.name
            for f in dataclasses.fields(Experiment)
            if f.name not in ("name", "description")
            and getattr(exp, f.name) != getattr(ref, f.name)
        ]
        self.assertEqual(diff, ["drn_from"])  # the pair differs in the culverts only


if __name__ == "__main__":
    unittest.main()
