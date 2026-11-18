"""``scripts/dedupe_experiment_inputs.py``: ``--help`` must touch nothing; ``--apply`` keeps
the exact semantics its callers rely on (``hpc/stage_and_submit_v3.slurm``,
``logs/nj2_freeze_2026-11-14/j2_freeze_nj2.slurm`` / ``j3_gate_nj2.slurm`` all call it as
``python scripts/dedupe_experiment_inputs.py --apply``).

Before 2026-11-16 the script read ``"--apply" in sys.argv`` only, so ``--help`` ran a full
~40-minute dry-run md5 walk over every domain.
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import dedupe_experiment_inputs as dd  # noqa: E402

MB = 1 << 20


def _make_exp(tmp: Path) -> Path:
    exp = tmp / "experiments"
    for dom, arms in {"domA": ("a1", "a2"), "domB": ("b1",)}.items():
        for arm in arms:
            run = exp / dom / arm
            (run / "subgrid").mkdir(parents=True)
            (run / "sfincs.nc").write_bytes(b"m" * MB)  # identical everywhere
            (run / "subgrid" / "dep_0.tif").write_bytes(b"d" * MB)
            (run / "sfincs.inp").write_text(f"{arm}\n")  # never a target
    (exp / "domA" / "_retired").mkdir()
    return exp


def _inodes(exp: Path) -> dict[str, int]:
    return {
        str(p.relative_to(exp)): p.stat().st_ino
        for p in sorted(exp.rglob("*"))
        if p.is_file()
    }


class TestDedupeArgs(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.exp = _make_exp(Path(self._tmp.name))
        self._patch = mock.patch.object(dd, "EXP", self.exp)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self._tmp.cleanup()

    def _run(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            dd.main(argv)
        return out.getvalue()

    def test_help_hashes_nothing_and_exits_zero(self):
        before = _inodes(self.exp)
        with mock.patch.object(dd, "md5", side_effect=AssertionError("hashed")):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                with self.assertRaises(SystemExit) as cm:
                    dd.main(["--help"])
        self.assertEqual(cm.exception.code, 0)
        self.assertIn("--apply", out.getvalue())
        self.assertEqual(_inodes(self.exp), before)

    def test_unknown_flag_is_refused_before_hashing(self):
        with mock.patch.object(dd, "md5", side_effect=AssertionError("hashed")):
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as cm:
                    dd.main(["--aply"])
        self.assertEqual(cm.exception.code, 2)

    def test_dry_run_changes_no_inode(self):
        before = _inodes(self.exp)
        text = self._run([])
        self.assertIn("DRY RUN", text)
        self.assertEqual(_inodes(self.exp), before)

    def test_apply_links_every_domain_like_the_callers(self):
        text = self._run(["--apply"])  # the exact argv J2/J3/stage_and_submit pass
        self.assertIn("APPLIED", text)
        ino = _inodes(self.exp)
        for name in ("sfincs.nc", "subgrid/dep_0.tif"):
            self.assertEqual(
                len({ino[f"{d}/{name}"] for d in ("domA/a1", "domA/a2", "domB/b1")}), 1
            )
        inps = {ino[f"{d}/sfincs.inp"] for d in ("domA/a1", "domA/a2", "domB/b1")}
        self.assertEqual(len(inps), 3)
        self.assertFalse(list(self.exp.rglob("*.dedupe_tmp")))

    def test_domain_filter_leaves_other_domains_alone(self):
        b_before = os.stat(self.exp / "domB" / "b1" / "sfincs.nc").st_ino
        self._run(["--apply", "--domain", "domA"])
        ino = _inodes(self.exp)
        self.assertEqual(ino["domA/a1/sfincs.nc"], ino["domA/a2/sfincs.nc"])
        self.assertEqual(ino["domB/b1/sfincs.nc"], b_before)
        self.assertNotEqual(ino["domB/b1/sfincs.nc"], ino["domA/a1/sfincs.nc"])

    def test_unknown_domain_is_refused(self):
        with mock.patch.object(dd, "md5", side_effect=AssertionError("hashed")):
            with self.assertRaises(SystemExit) as cm:
                dd.main(["--domain", "no_such_domain"])
        self.assertIn("no_such_domain", str(cm.exception.code))


if __name__ == "__main__":
    unittest.main()
