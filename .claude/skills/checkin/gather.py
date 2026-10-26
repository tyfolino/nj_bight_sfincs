#!/usr/bin/python3
"""Collect the facts for /checkin: node, scratch, the campaign check, log tails of failed
jobs, git state, and how the previous Claude session ended.  READ-ONLY; plain text.

Usage: gather.py [SESSION_ID]   (the current session, skipped when finding the previous one)

The SLURM part is ``scripts/campaign_check.py`` (queue, EXPECT_MD5 guards, finished jobs,
maintenance, quota), run over a window that starts at the previous session's last write
(or 24 h ago, whichever is earlier).  This script adds what that one does not: which repo
a job belongs to (by WorkDir), the tail of a failed job's log (``logs/**/*_<jobid>.out``),
git, and the previous session.  Stdlib only (system python 3.9).
"""

import glob
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime

REPO = "/cache/home/tpj8/nj_bight_sfincs"
TRANSCRIPTS = os.path.expanduser("~/.claude/projects/-cache-home-tpj8-nj-bight-sfincs")
USER = os.environ.get("USER", "tpj8")
# git is off the default PATH on Amarel; it lives in the sfincs env (CLAUDE.md §4).
GIT = (
    shutil.which("git")
    or "/cache/home/tpj8/nj_sandy_sfincs/micromamba/envs/sfincs/bin/git"
)
BAD = (
    "FAILED",
    "TIMEOUT",
    "OUT_OF_ME",
    "NODE_FAIL",
    "PREEMPTED",
    "CANCELLED",
    "BOOT_FAIL",
)


def sh(cmd, timeout=60):
    try:
        return subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        ).stdout.rstrip()
    except subprocess.TimeoutExpired:
        return "(timed out: %s)" % cmd


def tail(path, n):
    with open(path, errors="replace") as f:
        return [ln.rstrip()[:160] for ln in f.readlines()[-n:]]


def repo_tag(workdir):
    if workdir.startswith(REPO):
        return "bight"
    return os.path.basename(workdir.rstrip("/")) or "?"


def text_of(content):
    if isinstance(content, str):
        return content
    return " ".join(
        c.get("text", "")
        for c in content or []
        if isinstance(c, dict) and c.get("type") == "text"
    )


def previous_session(current):
    files = sorted(
        glob.glob(os.path.join(TRANSCRIPTS, "*.jsonl")), key=os.path.getmtime
    )
    if current and not current.startswith("$"):
        files = [f for f in files if os.path.basename(f) != current + ".jsonl"]
    elif files:
        files = files[:-1]  # no session id: assume the newest file is this session
    if not files:
        return None
    path = files[-1]
    users, last_reply = [], ""
    for line in open(path, errors="replace"):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("isMeta") or d.get("isSidechain"):
            continue
        msg = d.get("message") or {}
        txt = text_of(msg.get("content")).strip()
        if not txt:
            continue
        if d.get("type") == "user" and not txt.startswith("<"):
            users.append(txt)
        elif d.get("type") == "assistant":
            last_reply = txt
    return path, users, last_reply


def main():
    current = sys.argv[1] if len(sys.argv) > 1 else ""
    now = datetime.now()
    host = sh("hostname -s")
    print("== checkin facts (%s, host %s)" % (now.strftime("%Y-%m-%d %a %H:%M"), host))

    # The VS Code session runs inside the `vscode` job; on a halk node, files written
    # here reach the compute nodes late (CLAUDE.md §5).
    vs = sh("squeue -u %s -n vscode -h -o '%%N %%L'" % USER).split()
    if host.startswith("amarel"):
        print("node: LOGIN node, heavy work goes through srun")
    elif not vs:
        print("node: no vscode job in squeue")
    elif vs[0] != host:
        print("node: MISMATCH: on %s but the vscode job is on %s" % (host, vs[0]))
    else:
        print("node: on the vscode node, %s left" % vs[1])
    if host.startswith("halk"):
        print("  ⚠️ halk: submit with EXPECT_MD5 (late-write trap)")

    exp = os.path.join(REPO, "experiments")
    if os.path.isdir(exp):
        print(
            "experiments/ → %s (%d entries)"
            % (os.path.realpath(exp), len(os.listdir(exp)))
        )
    else:
        print("experiments/: MISSING (scratch purged, or a Camden node?)")

    prev = previous_session(current)
    since = time.time() - 86400
    if prev:
        since = min(since, os.path.getmtime(prev[0]))
    hours = (time.time() - since) / 3600 + 0.1
    since_s = datetime.fromtimestamp(since).strftime("%Y-%m-%dT%H:%M")

    print()
    print(
        sh(
            "%s %s/scripts/campaign_check.py --hours %.1f"
            % (sys.executable, REPO, hours),
            timeout=180,
        )
    )

    print("\n== ended since %s, by repo (failed ones in this repo: log tail)" % since_s)
    ended = sh(
        "sacct -u %s -X -n -P -S %s -o JobID,JobName,State,WorkDir" % (USER, since_s)
    ).splitlines()
    n = 0
    for row in ended:
        jid, name, state, wd = (row.split("|") + [""] * 4)[:4]
        if name == "vscode" or state in ("RUNNING", "PENDING", "REQUEUED"):
            continue
        n += 1
        tag = repo_tag(wd)
        print("  %s %-16s %-10s [%s]" % (jid, name, state.split()[0], tag))
        if tag != "bight" or not state.startswith(BAD):
            continue
        logs = glob.glob(
            os.path.join(REPO, "logs", "**", "*_%s.out" % jid), recursive=True
        )
        if not logs:
            print("      (no logs/**/*_%s.out)" % jid)
        for lg in logs:
            print("      %s:" % os.path.relpath(lg, REPO))
            for ln in tail(lg, 12):
                print("        %s" % ln)
    if not n:
        print("  none")

    print("\n== git")
    print(sh("%s -C %s status --short --branch" % (GIT, REPO)))
    print("last commits:")
    print(
        sh(
            "%s -C %s log --format='  %%h %%ad %%s' --date=format:'%%m-%%d %%H:%%M' -6"
            % (GIT, REPO)
        )
    )
    print(
        "STATUS.md: last updated %s, last committed %s"
        % (
            sh(
                "grep -m1 -o 'Last updated: \\*\\*[0-9-]*' %s/docs/STATUS.md | tr -d '*'"
                % REPO
            ).replace("Last updated: ", ""),
            sh(
                "%s -C %s log -1 --format=%%ad --date=short -- docs/STATUS.md"
                % (GIT, REPO)
            ),
        )
    )

    print("\n== previous session")
    if not prev:
        print("  none found")
        return
    path, users, last_reply = prev
    print(
        "  %s, last write %s"
        % (
            os.path.basename(path),
            datetime.fromtimestamp(os.path.getmtime(path)).strftime("%m-%d %H:%M"),
        )
    )
    if users:
        print("  opened with: %s" % users[0][:400].replace("\n", " "))
        for u in users[-3:] if len(users) > 1 else []:
            print("  user, late: %s" % u[:250].replace("\n", " "))
    print(
        "  Claude's last message:\n    %s" % last_reply[-1500:].replace("\n", "\n    ")
    )


if __name__ == "__main__":
    main()
