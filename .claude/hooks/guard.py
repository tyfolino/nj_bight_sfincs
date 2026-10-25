#!/usr/bin/env python3
"""PreToolUse guard for Claude Code: three CLAUDE.md traps, enforced instead of remembered.

Wired in ``.claude/settings.json``; reads the hook JSON on stdin, prints a decision.

- **ASK** before an edit to a file a PENDING job's EXPECT_MD5 will check at start
  (editing it kills the job — "STALE FILES" — and strands every ``afterok`` job behind
  it; CLAUDE.md §5).  Ask, not deny: re-writing the md5 file right after a deliberate
  edit is a legitimate route.  The list comes from
  ``scripts/campaign_check.py --guarded``.
- **DENY** ``run_experiments.py`` with ``--inputs-only`` / ``--no-run`` / ``--dry-run``:
  all three ``rmtree`` each experiment dir first (CLAUDE.md §4; ``--check`` is the
  read-only mode).
- **DENY** ``git commit``: the user commits and pushes (CLAUDE.md §6).

Any error inside the guard lets the call through: it must never wedge a session.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shlex
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
RMTREE_FLAGS = ("--inputs-only", "--no-run", "--dry-run")
SEGMENT = re.compile(r"\|\||&&|[;|&\n]")
# Commands that modify the paths they name.  cp: the destination only.
MODIFIERS = {"rm", "mv", "truncate", "ln", "chmod", "touch"}
REDIRECT = re.compile(r"(?:^|[^0-9&<>])>>?\s*([^\s;&|<>]+)")
PY_WRITE = re.compile(r"open\(|write_text|write_bytes|\.write\(")


def _tokens(seg: str) -> list[str]:
    try:
        return shlex.split(seg, comments=False, posix=True)
    except ValueError:
        return seg.split()


def git_commit(cmd: str) -> bool:
    for seg in SEGMENT.split(cmd):
        t = _tokens(seg)
        for i, tok in enumerate(t):
            if os.path.basename(tok) != "git":
                continue
            j = i + 1
            while j < len(t) and t[j].startswith("-"):
                j += 2 if t[j] in ("-C", "-c", "--git-dir", "--work-tree") else 1
            if j < len(t) and t[j] == "commit":
                return True
    return False


def rmtree_flags(cmd: str) -> list[str]:
    hits = []
    for seg in SEGMENT.split(cmd):
        if "run_experiments.py" in seg:
            t = _tokens(seg)
            hits += [f for f in RMTREE_FLAGS if any(x.split("=")[0] == f for x in t)]
    return hits


def _resolve(p: str, cwd: Path) -> str:
    q = Path(os.path.expanduser(p))
    return str((q if q.is_absolute() else cwd / q).resolve())


def bash_targets(cmd: str, cwd: Path) -> set[str]:
    """Absolute paths a shell command may WRITE (a heuristic, tuned for no misses on
    the usual edit idioms: sed -i, redirects, tee, mv/rm/cp, python writes)."""
    out: set[str] = set()
    for seg in SEGMENT.split(cmd):
        t = _tokens(seg)
        if not t:
            continue
        names = [os.path.basename(x) for x in t]
        args = [x for x in t[1:] if not x.startswith("-")]
        inplace = ("sed" in names or "perl" in names) and any(
            x.startswith("-i") or x == "--in-place" for x in t
        )
        if (
            inplace
            or names[0] in MODIFIERS
            or (names[0].startswith("python") and PY_WRITE.search(seg))
        ):
            out |= {_resolve(a, cwd) for a in args}
        if names[0] == "cp" and args:
            out.add(_resolve(args[-1], cwd))
        if "tee" in names:
            k = names.index("tee")
            out |= {_resolve(a, cwd) for a in t[k + 1 :] if not a.startswith("-")}
        out |= {_resolve(m, cwd) for m in REDIRECT.findall(seg)}
    return out


def guarded() -> dict[str, list[str]]:
    spec = importlib.util.spec_from_file_location(
        "campaign_check", ROOT / "scripts" / "campaign_check.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    jobs = mod.queue(os.environ.get("USER", "tpj8"))
    mod.attach_guards(jobs)
    return mod.guarded_map(jobs)


def decide(event: dict, guard_map=guarded) -> tuple[str, str] | None:
    """(decision, reason) or None to let the call through.  ``guard_map`` is
    injectable so tests need no SLURM."""
    tool = event.get("tool_name", "")
    ti = event.get("tool_input") or {}
    cwd = Path(event.get("cwd") or ROOT)
    targets: set[str] = set()
    if tool == "Bash":
        cmd = ti.get("command", "")
        if git_commit(cmd):
            return "deny", (
                "git commit is refused here: the user commits and pushes; Claude "
                "may only `git add` (CLAUDE.md §6). Stage the files and say so."
            )
        flags = rmtree_flags(cmd)
        if flags:
            return "deny", (
                f"run_experiments.py {' '.join(flags)} rmtree's every experiment dir "
                "before skipping the solver (CLAUDE.md §4). The read-only mode is "
                "--check."
            )
        targets = bash_targets(cmd, cwd)
    elif tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        fp = ti.get("file_path") or ti.get("notebook_path")
        if fp:
            targets = {_resolve(fp, cwd)}
    if not targets:
        return None
    gm = guard_map()
    hit = sorted(t for t in targets if t in gm)
    if not hit:
        return None
    lines = [f"{os.path.relpath(h, ROOT)} ← {', '.join(gm[h])}" for h in hit]
    return "ask", (
        "This edits a file a QUEUED job checks against its EXPECT_MD5 at start; the job "
        "would refuse (STALE FILES) and strand its afterok chain (CLAUDE.md §5):\n  "
        + "\n  ".join(lines)
        + "\nApprove only if the edit is deliberate AND the job's md5 file will be "
        "re-written right after (python scripts/campaign_check.py shows the state)."
    )


def main() -> int:
    try:
        event = json.load(sys.stdin)
        d = decide(event)
    except Exception as e:  # noqa: BLE001 — a guard bug must never wedge a session
        print(json.dumps({"systemMessage": f"guard.py error (call allowed): {e}"}))
        return 0
    if d:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": d[0],
                        "permissionDecisionReason": d[1],
                    }
                }
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
