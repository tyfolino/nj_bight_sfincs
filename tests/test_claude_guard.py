""".claude/hooks/guard.py: the three traps it enforces, without SLURM."""

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _guard():
    spec = importlib.util.spec_from_file_location(
        "claude_guard", ROOT / ".claude" / "hooks" / "guard.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


GUARDED = str((ROOT / "logs" / "job" / "pack_worker.sh").resolve())


def _gm():
    return {GUARDED: ["123 phase4"]}


def _bash(g, cmd):
    return g.decide(
        {"tool_name": "Bash", "cwd": str(ROOT), "tool_input": {"command": cmd}}, _gm
    )


class TestGuard(unittest.TestCase):
    def setUp(self):
        self.g = _guard()

    def test_git_commit_denied_other_git_allowed(self):
        self.assertEqual(_bash(self.g, "git -C . commit -m x")[0], "deny")
        self.assertEqual(_bash(self.g, "git add a && git commit")[0], "deny")
        self.assertIsNone(_bash(self.g, "git log --grep commit"))
        self.assertIsNone(_bash(self.g, "git add docs/STATUS.md"))

    def test_rmtree_flags_denied_check_allowed(self):
        for f in ("--inputs-only", "--no-run", "--dry-run"):
            d = _bash(self.g, f"python run_experiments.py --experiments a {f}")
            self.assertEqual(d[0], "deny", f)
        self.assertIsNone(_bash(self.g, "python run_experiments.py --check"))

    def test_guarded_writes_ask_reads_pass(self):
        rel = "logs/job/pack_worker.sh"
        for cmd in (
            f"sed -i s/a/b/ {rel}",
            f"echo x >> {rel}",
            f"echo x | tee {rel}",
            f"cp /tmp/a {rel}",
            f"rm {rel}",
        ):
            self.assertEqual(_bash(self.g, cmd)[0], "ask", cmd)
        for cmd in (f"cat {rel}", f"grep x {rel} > /tmp/o", f"cp {rel} /tmp/x"):
            self.assertIsNone(_bash(self.g, cmd), cmd)

    def test_edit_tool(self):
        ev = {"tool_name": "Edit", "tool_input": {"file_path": GUARDED}}
        self.assertEqual(self.g.decide(ev, _gm)[0], "ask")
        ev["tool_input"]["file_path"] = str(ROOT / "docs" / "STATUS.md")
        self.assertIsNone(self.g.decide(ev, _gm))


if __name__ == "__main__":
    unittest.main()
