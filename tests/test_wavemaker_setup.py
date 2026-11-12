"""model.apply_wavemaker_setup (Experiment.wavemaker_setup_from, 2026-11-09): copies, keys, refusals."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from nj_sfincs import model


def _set(d: Path, wst: str = "0.0 0.1 0.1\n") -> Path:
    s = d / "set"
    s.mkdir()
    for n, body in (
        ("a.wvm", "l1\n2 2\n0 0\n1 0\n"),
        ("a.wfp", "0 0\n1 0\n"),
        ("a.whi", "0.0 0 0\n"),
        ("a.wti", "0.0 60 60\n"),
        ("a.wst", wst),
    ):
        (s / n).write_text(body)
    keys = {
        "wvmfile": "a.wvm",
        "wfpfile": "a.wfp",
        "whifile": "a.whi",
        "wtifile": "a.wti",
        "wstfile": "a.wst",
        "wmfred": "1.0",
    }
    (s / "keys.json").write_text(json.dumps(keys))
    return s


class TestApplyWavemakerSetup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.run_dir = self.d / "run"
        self.run_dir.mkdir()
        (self.run_dir / "sfincs.inp").write_text(
            "tref                 = 20121028 000000\nsnapwave             = 0\n"
        )
        (self.run_dir / "provenance.txt").write_text("staged\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_copies_keys_and_records(self):
        src = _set(self.d)
        out = model.apply_wavemaker_setup(self.run_dir, src)
        keys = model._inp_keys(self.run_dir / "sfincs.inp")
        self.assertEqual(keys["wvmfile"], "a.wvm")
        self.assertEqual(keys["wstfile"], "a.wst")
        self.assertEqual(keys["wmfred"], "1.0")
        self.assertEqual(keys["snapwave"], "0")
        self.assertEqual(
            (self.run_dir / "a.wst").read_text(), (src / "a.wst").read_text()
        )
        self.assertEqual(len(out["files"]), 5)
        self.assertIn(
            "wavemaker_setup_from", (self.run_dir / "provenance.txt").read_text()
        )

    def test_new_inode_not_a_link(self):
        src = _set(self.d)
        os.link(
            src / "a.wst", self.run_dir / "a.wst"
        )  # a stale hard link in the run dir
        model.apply_wavemaker_setup(self.run_dir, src)
        self.assertNotEqual(
            os.stat(self.run_dir / "a.wst").st_ino, os.stat(src / "a.wst").st_ino
        )

    def test_refuses_waves_on(self):
        (self.run_dir / "sfincs.inp").write_text("snapwave             = 1\n")
        with self.assertRaises(SystemExit):
            model.apply_wavemaker_setup(self.run_dir, _set(self.d))

    def test_refuses_existing_wavemaker(self):
        (self.run_dir / "sfincs.inp").write_text(
            "snapwave             = 0\nwvmfile              = sfincs.wvm\n"
        )
        with self.assertRaises(SystemExit):
            model.apply_wavemaker_setup(self.run_dir, _set(self.d))

    def test_refuses_missing_file(self):
        src = _set(self.d)
        (src / "a.wti").unlink()
        with self.assertRaises(SystemExit):
            model.apply_wavemaker_setup(self.run_dir, src)


if __name__ == "__main__":
    unittest.main()
