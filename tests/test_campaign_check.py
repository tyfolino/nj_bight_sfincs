"""scripts/campaign_check.py: which md5 file a job checks, what fails, and which jobs a
changed file would kill (a pending job at start, an old-pattern running one on a requeue)."""

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


class TestJobMd5(unittest.TestCase):
    """The md5 file Slurm names beats the inference (63887750 / 63887749, 2026-11-14:
    the newest ``expected.md5`` before submit was another job's file)."""

    def setUp(self):
        self.cc = _cc()
        self.tmp = Path(tempfile.mkdtemp())
        self.t0 = datetime(2026, 11, 13, 12, 42)
        (self.tmp / "a.py").write_text("x = 1\n")
        ok = hashlib.md5(b"x = 1\n").hexdigest()
        self.resume = _touch(
            self.tmp / "expected_resume.md5", f"{ok}  a.py\n", self.t0 - timedelta(1)
        )
        self.newest = _touch(self.tmp / "expected.md5", "", self.t0)  # the decoy
        self.script = self.tmp / "resume.slurm"
        self.spooled = (
            "#!/bin/bash\n"
            "#   env EXPECT_MD5=expected_resume.md5 NWEIR=862 \\\n"
            "#       sbatch resume.slurm\n"
            'if [ -n "${EXPECT_MD5:-}" ]; then md5sum -c "$EXPECT_MD5" || exit 3; fi\n'
        )
        _touch(self.script, self.spooled, self.t0)

    def _job(self, spooled, env=lambda _id: None):
        j = self.cc.Job("9", "r", "PENDING", "None", "", "1:00:00", "0:00", "", "")
        j.command, j.workdir, j.submit = str(self.script), str(self.tmp), self.t0
        self.cc.attach_guards([j], spool=lambda _id: spooled, env=env)
        return j

    def test_documented_submit_line_beats_inference(self):
        j = self._job(self.spooled)
        self.assertEqual(j.md5_file, self.resume)
        self.assertIn("documented submit line", j.md5_note)
        self.assertEqual(j.guarded, [self.tmp / "a.py"])

    def test_environment_beats_the_script(self):
        other = _touch(self.tmp / "expected_x.md5", "", self.t0)
        j = self._job(self.spooled, env=lambda _id: str(other))
        self.assertEqual(j.md5_file, other)
        self.assertIn("sacct --env-vars", j.md5_note)
        j = self._job(self.spooled, env=lambda _id: "gone.md5")
        self.assertIsNone(j.md5_file)
        self.assertIn("does not exist", j.md5_note)

    def test_a_value_the_script_sets_beats_its_comments(self):
        j = self._job(self.spooled + "export EXPECT_MD5=expected.md5\n")
        self.assertEqual(j.md5_file, self.newest)
        self.assertIn("sets it", j.md5_note)

    def test_ambiguous_or_absent_falls_back_to_inference(self):
        two = self.spooled + "#   EXPECT_MD5=expected.md5 sbatch resume.slurm\n"
        for spooled in (two, self.spooled.replace("expected_resume", "deleted")):
            j = self._job(spooled)
            self.assertEqual(j.md5_file, self.newest, spooled)
            self.assertIn("inferred", j.md5_note)

    def test_sacct_env_parse(self):
        out = (
            "Environment used for 9 (must be batch to display)\n"
            + "-" * 80
            + "\nHOME=/x\nEXPECT_MD5=logs/a/expected_resume.md5\n"
        )
        orig = self.cc._run
        try:
            self.cc._run = lambda cmd: out
            self.assertEqual(self.cc.sacct_env_md5("9"), "logs/a/expected_resume.md5")
            self.cc._run = lambda cmd: out.split("HOME")[0] + "NONE\n"
            self.assertIsNone(self.cc.sacct_env_md5("9"))
        finally:
            self.cc._run = orig


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


OLD = 'if [ -n "${EXPECT_MD5:-}" ]; then md5sum -c "$EXPECT_MD5" || exit 3; fi\n'
NEW = (
    'if [ "${SLURM_RESTART_COUNT:-0}" -gt 0 ]; then\n'
    '  md5sum -c --quiet "$EXPECT_MD5" || echo "guarded files changed since submit '
    '— continuing"\nfi\n'
)


class TestRunningJobs(unittest.TestCase):
    """A preemption requeue re-runs the EXPECT_MD5 check (job 63524748, 2026-11-04)."""

    def setUp(self):
        self.cc = _cc()
        self.tmp = Path(tempfile.mkdtemp())
        self.t0 = datetime(2026, 11, 4, 10, 0)
        self.script = _touch(self.tmp / "test.slurm", OLD, self.t0)
        (self.tmp / "a.py").write_text("x = 1\n")
        ok = hashlib.md5(b"x = 1\n").hexdigest()
        _touch(self.tmp / "expected.md5", f"{ok}  a.py\n", self.t0)

    def _job(self, state, spooled, restarts=0, requeue=True):
        j = self.cc.Job("1", "t", state, "None", "", "1:00:00", "0:10", "", "")
        j.command, j.workdir, j.submit = str(self.script), str(self.tmp), self.t0
        j.restarts, j.requeue = restarts, requeue
        self.cc.attach_guards([j], spool=lambda _id: spooled)
        return j

    def test_pattern_is_read_from_the_spooled_script(self):
        self.assertFalse(self._job("RUNNING", OLD).tolerant)
        self.assertTrue(self._job("RUNNING", OLD + NEW).tolerant)
        self.assertTrue(
            self.cc.requeue_tolerant((ROOT / "hpc" / "job_template.slurm").read_text())
        )

    def test_which_jobs_an_edit_would_kill(self):
        cases = [
            (("PENDING", OLD), True),
            (("PENDING", NEW), True),  # first start stays strict
            (("PENDING", NEW, 1), False),  # a requeue that will warn
            (("PENDING", OLD, 1), True),
            (("RUNNING", OLD), True),  # dies on a preemption requeue
            (("RUNNING", NEW), False),
            (("RUNNING", OLD, 0, False), False),  # not requeueable: cancelled anyway
        ]
        for args, want in cases:
            j = self._job(*args)
            self.assertEqual(j.would_refuse, want, args)
            gm = self.cc.guarded_map([j])
            self.assertEqual(bool(gm), want, args)

    def test_running_report_line(self):
        import contextlib
        import io

        (self.tmp / "a.py").write_text("x = 2\n")  # an edit after the start
        for spooled, mark, words in (
            (OLD, "🔴", "a preemption would kill it"),
            (NEW, "⚠️", "would WARN and continue on a requeue"),
        ):
            j = self._job("RUNNING", spooled)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.assertEqual(self.cc.running_guard(j), 1)
            self.assertIn(mark, buf.getvalue())
            self.assertIn(words, buf.getvalue())
        (self.tmp / "a.py").write_text("x = 1\n")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(self.cc.running_guard(self._job("RUNNING", OLD)), 0)
        self.assertIn("✅", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
