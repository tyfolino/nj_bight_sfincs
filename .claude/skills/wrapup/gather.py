#!/usr/bin/python3
"""Collect the facts for /wrapup: what git would need staged or removed, strays, the
scripts index, today's campaign dirs, STATUS age and size, the queue (with idle holder
jobs to cancel), and ruff on the changed Python files.  READ-ONLY; plain text.

Usage: gather.py

Stdlib only (system python 3.9), like ``checkin/gather.py``.  The queue / md5-guard /
quota part is ``scripts/campaign_check.py``: an edit to a file a pending or running job
guards must not happen during the wrap-up (CLAUDE.md §5), so the guarded list is shown.
"""

import glob
import os
import re
import shutil
import subprocess
from datetime import date, datetime

REPO = "/cache/home/tpj8/nj_bight_sfincs"
USER = os.environ.get("USER", "tpj8")
TOOLBIN = os.path.join(
    os.environ.get("NJ_TOOLCHAIN") or os.path.expanduser("~/nj_sandy_sfincs"),
    "micromamba/envs/sfincs/bin",
)
GIT = shutil.which("git") or os.path.join(TOOLBIN, "git")
RUFF = shutil.which("ruff") or os.path.join(TOOLBIN, "ruff")
PY = os.path.join(TOOLBIN, "python")
BIG = 5 * 1024 * 1024  # an untracked file this size is almost never source
# Top-level entries that belong there (anything else untracked at the root is a stray).
ROOT_OK = {
    "ARCHIVE.md",
    "CHANGELOG.md",
    "CLAUDE.md",
    "README.md",
    "run_experiments.py",
    "environment.yml",
    "ruff.toml",
    ".gitignore",
    ".claude",
    ".git",
    "data",
    "docs",
    "env",
    "experiments",
    "hpc",
    "hydromt_sfincs",
    "logs",
    "micromamba",
    "nj_sfincs",
    "notebooks",
    "__pycache__",
    "refs",
    "reports",
    "scripts",
    "share",
    "tests",
    "sfincs-desktop.sif",
    ".gitattributes",
    ".ruff_cache",
}


def sh(cmd, timeout=60):
    try:
        return subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            cwd=REPO,
        ).stdout.rstrip()
    except subprocess.TimeoutExpired:
        return "(timed out: %s)" % cmd


def git_state():
    """Porcelain v1 -z: XY path.  Returns dict of lists."""
    out = subprocess.run(
        [GIT, "-C", REPO, "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    st = {"staged": [], "modified": [], "deleted": [], "untracked": [], "renamed": []}
    parts = out.split("\0")
    i = 0
    while i < len(parts):
        e = parts[i]
        i += 1
        if len(e) < 4:
            continue
        x, y, p = e[0], e[1], e[3:]
        if x in "RC":
            st["renamed"].append(p)
            i += 1  # the original path follows
            continue
        if x == "?":
            st["untracked"].append(p)
            continue
        if x not in " ?":
            st["staged"].append("%s %s" % (x, p))
        if y == "M":
            st["modified"].append(p)
        elif y == "D":
            st["deleted"].append(p)
    return st


def main():
    now = datetime.now()
    today = date.today().isoformat()
    print(
        "== wrapup facts (%s, host %s)"
        % (now.strftime("%Y-%m-%d %a %H:%M"), sh("hostname -s"))
    )

    # ---- git
    st = git_state()
    print("\n== git (never commit: the user does)")
    for k, label in (
        ("staged", "staged already"),
        ("modified", "modified, NOT staged (git add if it belongs)"),
        ("deleted", "deleted from disk, still tracked (git rm)"),
        ("renamed", "renamed (staged)"),
    ):
        print("-- %s: %d" % (label, len(st[k])))
        for p in st[k][:60]:
            print("   %s" % p)
    unt = st["untracked"]
    big = [
        p
        for p in unt
        if os.path.isfile(os.path.join(REPO, p))
        and os.path.getsize(os.path.join(REPO, p)) >= BIG
    ]
    print(
        "-- untracked, not ignored: %d (add if source, else move / ignore / delete)"
        % len(unt)
    )
    for p in unt[:80]:
        flag = (
            "   ⚠️ %.0f MB" % (os.path.getsize(os.path.join(REPO, p)) / 2**20)
            if p in big
            else ""
        )
        print("   %s%s" % (p, flag))
    if len(unt) > 80:
        print("   … %d more" % (len(unt) - 80))

    # ---- strays at the root
    strays = sorted(set(os.listdir(REPO)) - ROOT_OK)
    print("\n== repo root: entries outside the expected layout: %d" % len(strays))
    for s in strays:
        print("   %s" % s)

    # ---- scripts index (tests/test_repo_hygiene.py::test_index_matches_directory)
    idx = open(os.path.join(REPO, "scripts", "README.md"), errors="replace").read()
    files = sorted(
        os.path.basename(p)
        for p in glob.glob(os.path.join(REPO, "scripts", "*"))
        if os.path.isfile(p) and not p.endswith("README.md")
    )
    missing = [f for f in files if f not in idx]
    gone = sorted(
        f
        for f in set(re.findall(r"`([\w.-]+\.(?:py|sh))`", idx)) - set(files)
        if not any(
            os.path.exists(os.path.join(REPO, d, f))
            for d in ("", "nj_sfincs", "nj_sfincs/validate", "hpc", "tests")
        )
    )
    print("\n== scripts/README.md index")
    print("   not indexed: %s" % (", ".join(missing) or "none"))
    print("   indexed but no file: %s" % (", ".join(gone) or "none"))

    # ---- today's campaign dirs
    print("\n== logs/ dirs touched today (each wants a README.md)")
    n = 0
    for d in sorted(glob.glob(os.path.join(REPO, "logs", "*"))):
        if not os.path.isdir(d):
            continue
        if datetime.fromtimestamp(
            os.path.getmtime(d)
        ).date().isoformat() != today and today not in os.path.basename(d):
            continue
        n += 1
        has = (
            "README ✓" if os.path.exists(os.path.join(d, "README.md")) else "NO README"
        )
        print("   %-55s %s" % (os.path.relpath(d, REPO), has))
    if not n:
        print("   none")

    # ---- STATUS
    sp = os.path.join(REPO, "docs", "STATUS.md")
    lines = open(sp, errors="replace").read().splitlines()
    pick = next((ln for ln in lines if "PICK UP" in ln), "")
    m = re.search(r"PICK UP \(([^)]*)\)", pick)
    print(
        "\n== docs/STATUS.md: %d lines (keep ≤ ~300); PICK UP dated %s; file mtime %s"
        % (
            len(lines),
            m.group(1) if m else "?",
            datetime.fromtimestamp(os.path.getmtime(sp)).strftime("%m-%d %H:%M"),
        )
    )
    print(
        "   sections: %s" % " · ".join(ln[3:40] for ln in lines if ln.startswith("## "))
    )

    # ---- ruff on changed python
    py = [
        p
        for p in st["modified"] + [s[2:] for s in st["staged"]] + unt
        if p.endswith(".py") and os.path.exists(os.path.join(REPO, p))
    ]
    py = sorted(set(py))
    print("\n== ruff on %d changed .py file(s)" % len(py))
    if py and os.path.exists(RUFF):
        q = " ".join("'%s'" % p for p in py)
        print(sh("%s check %s 2>&1 | tail -15" % (RUFF, q)) or "   check: clean")
        fmt = sh(
            "%s format --check %s 2>&1 | grep -i 'would reformat' | head" % (RUFF, q)
        )
        print("   format: %s" % (fmt or "clean"))
    elif py:
        print("   (ruff not found at %s)" % RUFF)

    # ---- queue: holders / idle allocations the user should scancel
    print("\n== jobs: name | state | elapsed | limit | node | command")
    rows = sh("squeue -u %s -h -o '%%i|%%j|%%T|%%M|%%l|%%N|%%o'" % USER).splitlines()
    for r in rows:
        jid, name, state, el, lim, node, cmd = (r.split("|") + [""] * 7)[:7]
        hint = ""
        if name != "vscode" and (
            "sleep" in cmd or "wrap" in cmd or name.startswith("agents")
        ):
            hint = "   ← holder: give the user `scancel %s` if nothing uses it" % jid
        print(
            "   %s | %s | %s | %s | %s | %s | %s%s"
            % (jid, name, state, el, lim, node, os.path.basename(cmd)[:40], hint)
        )
    if not rows:
        print("   none")

    print()
    print(sh("%s %s/scripts/campaign_check.py --hours 12" % (PY, REPO), timeout=180))


if __name__ == "__main__":
    main()
