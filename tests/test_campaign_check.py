"""scripts/campaign_check.py: which md5 file a pending job checks, and what fails."""

import hashlib
import importlib.util
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _cc():
    spec = importlib.util.spec_from_file_location(
        "campaign_check", ROOT / "scripts" / "campaign_check.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # @dataclass looks its module up here
    spec.loader.exec_module(mod)
    return mod


def _touch(p: Path, text: str, when: datetime) -> Path:
    p.write_text(text)
    os.utime(p, (when.timestamp(), when.timestamp()))
    return p


class TestPickMd5(unittest.TestCase):
    def setUp(self):
        self.cc = _cc()
        self.tmp = Path(tempfile.mkdtemp())
        self.t0 = datetime(2026, 10, 24, 9, 0)
        self.script = _touch(self.tmp / "job.slurm", "md5sum -c $EXPECT_MD5\n", self.t0)

    def test_newest_before_submit_wins_and_bak_is_ignored(self):
        _touch(self.tmp / "expected.md5", "", self.t0 - timedelta(days=1))
        new = _touch(self.tmp / "beds_expected.md5", "", self.t0)
        _touch(self.tmp / "expected.md5.bak_2026-10-24", "", self.t0)
        got, note = self.cc.pick_md5(self.script, self.t0 + timedelta(seconds=30))
        self.assertEqual(got, new)
        self.assertIn("before submit", note)

    def test_rewritten_after_submit_is_still_found(self):
        f = _touch(self.tmp / "expected.md5", "", self.t0 + timedelta(hours=3))
        got, note = self.cc.pick_md5(self.script, self.t0)
        self.assertEqual(got, f)
        self.assertIn("NEWER", note)

    def test_unguarded_script(self):
        self.script.write_text("echo hi\n")
        got, note = self.cc.pick_md5(self.script, self.t0)
        self.assertIsNone(got)
        self.assertIn("no EXPECT_MD5", note)


class TestMd5Failures(unittest.TestCase):
    def test_changed_and_missing(self):
        cc = _cc()
        tmp = Path(tempfile.mkdtemp())
        (tmp / "a.py").write_text("x = 1\n")
        (tmp / "b.py").write_text("y = 2\n")
        ok = hashlib.md5(b"x = 1\n").hexdigest()
        stale = hashlib.md5(b"y = 1\n").hexdigest()
        md5 = tmp / "expected.md5"
        md5.write_text(f"{ok}  a.py\n{stale}  b.py\n{ok}  gone.py\n")
        entries = cc.md5_entries(md5, tmp)
        self.assertEqual(len(entries), 3)
        bad = cc.md5_failures(entries)
        self.assertEqual(sorted(b.split(": ")[1] for b in bad), ["CHANGED", "MISSING"])


class TestParseLimit(unittest.TestCase):
    def test_formats(self):
        cc = _cc()
        self.assertEqual(cc.parse_limit("1-16:00:00"), timedelta(hours=40))
        self.assertEqual(cc.parse_limit("6:00:00"), timedelta(hours=6))
        self.assertEqual(cc.parse_limit("30:00"), timedelta(minutes=30))
        self.assertIsNone(cc.parse_limit("UNLIMITED"))


if __name__ == "__main__":
    unittest.main()
