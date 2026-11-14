#!/usr/bin/env python
"""The morning check-in: what is queued, running, finished, and is it safe.  READ-ONLY.

    python scripts/campaign_check.py              # the report
    python scripts/campaign_check.py --hours 48   # look further back for finished jobs
    python scripts/campaign_check.py --guarded    # JSON {abs path: [job ids]} (the hook)

One pass over everything a check-in used to take a dozen commands for:

- **queue** — your pending / running jobs, start estimates, dependencies;
  ``DependencyNeverSatisfied`` is flagged, it never clears on its own (CLAUDE.md §5).
- **EXPECT_MD5 guards** — every PENDING job's checksum file is checked NOW, so an
  edit that would make the job refuse at start ("STALE FILES") is caught while it
  can still be undone.  Which file a job checks is read, in order, from: (1) the
  job's environment as Slurm accounting stored it (``sacct --env-vars``; empty on
  Amarel, whose ``AccountingStoreFlags`` lacks ``job_env``, 2026-11-14); (2) the
  SPOOLED script — an ``EXPECT_MD5=<path>`` it sets itself, else the one path its
  comments name in the documented submit line (``env EXPECT_MD5=… sbatch …``); and
  only then (3) INFERRED: the newest ``*expected.md5`` beside the job script written
  before the submit (``.bak_*`` copies never match the glob).  The report names the
  file and which of the three it came from.
  RUNNING jobs are checked too, because a PREEMPTION requeue re-runs the check
  (job 63524748, 2026-11-04): the job's SPOOLED script (``scontrol write
  batch_script``, what a requeue re-runs) says whether it warns and continues on a
  restart (the 2026-11-04 pattern) or refuses — and then a mismatch is 🔴.
- **finished** — jobs that ended in the last ``--hours``; anything not COMPLETED,
  and any ``halk`` node (the late-write trap, CLAUDE.md §5), is flagged.
- **maintenance** — maintenance reservations in the next 3 weeks, and any pending
  job whose time limit would run into one (it will not start).
- **quota** — the GPFS home quota (``quota -s`` prints nothing here).

``--guarded`` feeds ``.claude/hooks/guard.py``, which warns before an edit to a file
a job would REFUSE on at its next start: any pending job's (unless it is a requeue with
the warn-on-restart branch), and a requeueable running job's whose spooled script still
refuses on a restart (``Job.would_refuse``).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

MMLSQUOTA = "/usr/lpp/mmfs/bin/mmlsquota"
SUBMIT_SLACK = timedelta(minutes=2)
#: The 2026-11-04 requeue branch's message (hpc/job_template.slurm): a spooled script
#: carrying it WARNS and continues when a restart finds the guarded files changed.
TOLERANT_MARK = "changed since submit"
RES_HORIZON = timedelta(days=21)


@dataclass
class Job:
    jobid: str
    name: str
    state: str
    reason: str
    start: str
    limit: str
    elapsed: str
    nodes: str
    dependency: str
    command: str = ""
    workdir: str = ""
    submit: datetime | None = None
    md5_file: Path | None = None
    md5_note: str = ""
    guarded: list[Path] = field(default_factory=list)
    restarts: int = 0
    requeue: bool = True
    #: the spooled batch script's text ("" when scontrol could not print it)
    spooled: str = ""

    @property
    def tolerant(self) -> bool:
        """True if the script WARNS and continues when a requeue finds a mismatch."""
        return requeue_tolerant(self.spooled)

    @property
    def would_refuse(self) -> bool:
        """An edit to a guarded file would make this job exit at its next start."""
        if self.state == "PENDING":
            return not (self.restarts > 0 and self.tolerant)
        if self.state == "RUNNING":
            return self.requeue and not self.tolerant
        return False


def _run(cmd: list[str]) -> str:
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=60, check=False
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _when(s: str) -> datetime | None:
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def parse_limit(s: str) -> timedelta | None:
    """SLURM time limit ``[D-]HH:MM:SS`` (or ``MM:SS``) → timedelta."""
    m = re.fullmatch(r"(?:(\d+)-)?(?:(\d+):)?(\d+):(\d+)", s.strip())
    if not m:
        return None
    d, h, mi, se = (int(g) if g else 0 for g in m.groups())
    return timedelta(days=d, hours=h, minutes=mi, seconds=se)


def queue(user: str) -> list[Job]:
    out = _run(["squeue", "-u", user, "-h", "-o", "%i|%j|%T|%r|%S|%l|%M|%N|%E"])
    jobs = []
    for line in out.splitlines():
        parts = line.split("|")
        if len(parts) == 9:
            jobs.append(Job(*parts))
    for j in jobs:
        info = _run(["scontrol", "show", "job", j.jobid])
        for key in ("Command", "WorkDir", "SubmitTime", "Restarts", "Requeue"):
            m = re.search(rf"\b{key}=(\S+)", info)
            if not m:
                continue
            if key == "Command":
                j.command = m.group(1)
            elif key == "WorkDir":
                j.workdir = m.group(1)
            elif key == "SubmitTime":
                j.submit = _when(m.group(1))
            elif key == "Restarts":
                j.restarts = int(m.group(1)) if m.group(1).isdigit() else 0
            else:
                j.requeue = m.group(1) != "0"
    return jobs


def requeue_tolerant(text: str) -> bool:
    """Does this job script WARN and continue when a requeue finds changed files?"""
    return "SLURM_RESTART_COUNT" in text and TOLERANT_MARK in text


def spooled_script(jobid: str) -> str:
    """The batch script SLURM spooled at submit (a requeue re-runs THIS, not the file
    on disk); "" if scontrol cannot print it."""
    return _run(["scontrol", "write", "batch_script", jobid, "-"])


#: ``EXPECT_MD5=<path>`` in a shell line: an optional ``export``/``env``, a literal path
#: (a ``$``-expansion or an empty value is not one); quotes allowed.
_ASSIGN = re.compile(r"""(?:^|[\s;(])EXPECT_MD5=(["']?)([^\s"';$`|&)]+)\1""")


def _read(p: Path) -> str:
    try:
        return p.read_text(errors="replace")
    except OSError:
        return ""


def sacct_env_md5(jobid: str) -> str | None:
    """``EXPECT_MD5`` from the job's environment as Slurm accounting stored it, or None.
    Only when the cluster stores job environments (``AccountingStoreFlags=job_env``);
    otherwise sacct prints ``NONE``."""
    out = _run(["sacct", "-j", jobid, "--env-vars", "-X"])
    m = re.search(r"^EXPECT_MD5=(.*)$", out, re.M)
    return (m.group(1).strip() or None) if m else None


def spooled_md5(text: str) -> tuple[str | None, str]:
    """``(path, how)`` from a spooled script: a value the script SETS on a code line
    wins; else the single path its comments name (the documented submit line).  None
    when there is neither, or the comments name more than one."""
    code, docs = [], []
    for line in (text or "").splitlines():
        s = line.strip()
        found = [m.group(2) for m in _ASSIGN.finditer(s.lstrip("#"))]
        (docs if s.startswith("#") else code).extend(found)
    if code:
        return code[-1], "the spooled script sets it"
    uniq = list(dict.fromkeys(docs))
    if len(uniq) == 1:
        return uniq[0], "the spooled script's documented submit line"
    return None, ""


def job_md5(
    jobid: str, text: str, workdir: Path, env=sacct_env_md5
) -> tuple[Path | None, str]:
    """The EXPECT_MD5 file a job checks when Slurm can tell us (its stored environment,
    then its spooled script), resolved against the job's working directory; ``(None,
    "")`` when neither names one, so the caller falls back to ``pick_md5``."""
    val = env(jobid)
    if val:
        p = Path(val) if Path(val).is_absolute() else workdir / val
        src = "from the job's environment (sacct --env-vars)"
        return (p, src) if p.is_file() else (None, f"🔴 {val} ({src}) does not exist")
    val, src = spooled_md5(text)
    if val:
        p = Path(val) if Path(val).is_absolute() else workdir / val
        if p.is_file():  # a stale comment naming a deleted file falls through
            return p, f"from {src}"
    return None, ""


def pick_md5(
    script: Path, submit: datetime | None, text: str | None = None
) -> tuple[Path | None, str]:
    """The ``*expected.md5`` a job was most likely submitted with, and why.  ``text``
    is the spooled script when known (it is what runs); else the file on disk."""
    if not script.is_file():
        return None, "job script not found"
    try:
        if "EXPECT_MD5" not in (text or script.read_text(errors="replace")):
            return None, "script has no EXPECT_MD5 guard"
    except OSError:
        return None, "job script unreadable"
    cands = sorted(script.parent.glob("*expected.md5"), key=lambda p: p.stat().st_mtime)
    if not cands:
        return None, "no *expected.md5 beside the script (submitted without one?)"
    if submit is not None:
        before = [
            p
            for p in cands
            if datetime.fromtimestamp(p.stat().st_mtime) <= submit + SUBMIT_SLACK
        ]
        if before:
            return before[-1], "inferred: newest *expected.md5 written before submit"
        return cands[-1], "inferred: every *expected.md5 is NEWER than the submit"
    return cands[-1], "inferred: newest *expected.md5 (submit time unknown)"


def md5_entries(md5_file: Path, workdir: Path) -> list[tuple[str, Path]]:
    rows = []
    for line in md5_file.read_text().splitlines():
        m = re.match(r"([0-9a-f]{32})\s+\*?(.+)$", line.strip())
        if m:
            p = Path(m.group(2))
            rows.append((m.group(1), p if p.is_absolute() else workdir / p))
    return rows


def md5_failures(entries: list[tuple[str, Path]]) -> list[str]:
    bad = []
    for want, p in entries:
        try:
            got = hashlib.md5(p.read_bytes()).hexdigest()
        except OSError:
            bad.append(f"{p}: MISSING")
            continue
        if got != want:
            bad.append(f"{p}: CHANGED")
    return bad


def attach_guards(jobs: list[Job], spool=spooled_script, env=sacct_env_md5) -> None:
    """Pending and running jobs: the md5 file each checks, and the files it lists.
    ``spool`` and ``env`` are injectable so tests need no SLURM.  The file is the one
    Slurm names (``job_md5``) when it can, else the inferred one (``pick_md5``)."""
    for j in jobs:
        if j.state not in ("PENDING", "RUNNING") or not j.command or j.name == "vscode":
            continue
        j.spooled = spool(j.jobid)
        wd = Path(j.workdir) if j.workdir else Path(j.command).parent
        script = Path(j.command)
        j.md5_file, j.md5_note = None, ""
        if "EXPECT_MD5" in (j.spooled or _read(script)):
            j.md5_file, j.md5_note = job_md5(j.jobid, j.spooled, wd, env=env)
        if j.md5_file is None and not j.md5_note:
            j.md5_file, j.md5_note = pick_md5(script, j.submit, j.spooled or None)
        if j.md5_file is not None:
            j.guarded = [p for _, p in md5_entries(j.md5_file, wd)]


def guarded_map(jobs: list[Job]) -> dict[str, list[str]]:
    """{abs path: [jobs]} for the files whose edit would make a job REFUSE at its next
    start (``Job.would_refuse``) — the hook's ASK list."""
    out: dict[str, list[str]] = {}
    for j in jobs:
        if not j.would_refuse:
            continue
        tag = f"{j.jobid} {j.name}"
        if j.state == "RUNNING":
            tag += " (running; refuses on a preemption requeue)"
        for p in j.guarded:
            out.setdefault(str(p.resolve()), []).append(tag)
    return out


def recent(user: str, hours: float) -> list[list[str]]:
    since = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M")
    out = _run(
        [
            "sacct", "-u", user, "-S", since, "-X", "-n", "-P",
            "--format=JobID,JobName,State,Elapsed,End,NodeList,ExitCode",
        ]
    )  # fmt: skip
    rows = []
    for line in out.splitlines():
        r = line.split("|")
        if len(r) == 7 and r[2] not in ("PENDING", "RUNNING") and r[1] != "vscode":
            rows.append(r)
    return rows


def reservations() -> list[tuple[str, datetime, datetime]]:
    out = _run(["scontrol", "show", "reservation"])
    res = []
    for block in out.split("\n\n"):
        name = re.search(r"ReservationName=(\S+)", block)
        st = re.search(r"StartTime=(\S+)", block)
        en = re.search(r"EndTime=(\S+)", block)
        if (
            name
            and st
            and en
            and (s := _when(st.group(1)))
            and (e := _when(en.group(1)))
        ):
            res.append((name.group(1), s, e))
    return res


def quota(user: str) -> str:
    if not os.path.exists(MMLSQUOTA):
        return "(mmlsquota not found)"
    out = _run([MMLSQUOTA, "-u", user, "--block-size", "auto", "cache"])
    return (
        "\n".join("  " + ln for ln in out.splitlines() if ln.strip()) or "  (no output)"
    )


def running_guard(j: Job) -> int:
    """Print one running job's guard line; return 1 if it is a flag."""
    if j.md5_file is None:
        print(f"  {j.jobid} {j.name}: — {j.md5_note}")
        return 0
    wd = Path(j.workdir) if j.workdir else Path(j.command).parent
    bad = md5_failures(md5_entries(j.md5_file, wd))
    rel = os.path.relpath(j.md5_file, wd)
    if not j.spooled:
        kind = "spooled script unreadable; pattern unknown"
    elif j.tolerant:
        kind = "warns on a requeue"
    else:
        kind = "OLD pattern: refuses on a requeue"
    if not j.requeue:
        kind += "; not requeueable (a preemption cancels it)"
    kind = f"{j.md5_note}; {kind}"  # which source named the md5 file, then the pattern
    if not bad:
        print(
            f"  ✅ {j.jobid} {j.name}: {len(j.guarded)}/{len(j.guarded)} OK "
            f"({rel}; {kind})"
        )
        return 0
    if not j.requeue:
        head, tail = "⚠️", "irrelevant unless resubmitted"
    elif j.tolerant:
        head, tail = "⚠️", "would WARN and continue on a requeue"
    else:
        head, tail = (
            "🔴",
            "a preemption would kill it; re-write its md5 deliberately",
        )
    print(
        f"  {head} {j.jobid} {j.name}: {len(bad)} of {len(j.guarded)} FAIL "
        f"({rel}; {kind}) — {tail}:"
    )
    for b in bad:
        print(f"      {os.path.relpath(b.split(': ')[0], wd)}: {b.split(': ')[1]}")
    return 1


def report(user: str, hours: float) -> int:
    now = datetime.now()
    jobs = queue(user)
    attach_guards(jobs)
    flags = 0

    print(
        f"== campaign check {now:%Y-%m-%d %H:%M} ({user}, host {os.uname().nodename})"
    )
    print("\n-- queue")
    if not jobs:
        print("  (nothing queued or running)")
    for j in jobs:
        if j.name == "vscode":
            continue
        where = j.nodes if j.state == "RUNNING" else f"start est. {j.start}"
        print(
            f"  {j.jobid} {j.name:<16} {j.state:<8} {j.reason:<22} {where}  "
            f"[{j.elapsed} / {j.limit}]"
        )
        if j.dependency and j.dependency != "(null)":
            print(f"      depends: {j.dependency}")
        if "DependencyNeverSatisfied" in j.reason:
            flags += 1
            print(
                "      🔴 DependencyNeverSatisfied — will never start; cancel + resubmit"
            )
        if "halk" in j.nodes:
            flags += 1
            print("      🔴 running on a halk node (late-write trap)")

    print("\n-- EXPECT_MD5 guards (pending jobs; checked now)")
    pend = [j for j in jobs if j.state == "PENDING" and j.name != "vscode"]
    if not pend:
        print("  (no pending jobs)")
    for j in pend:
        if j.md5_file is None:
            print(f"  {j.jobid} {j.name}: — {j.md5_note}")
            continue
        wd = Path(j.workdir) if j.workdir else Path(j.command).parent
        bad = md5_failures(md5_entries(j.md5_file, wd))
        rel = os.path.relpath(j.md5_file, wd)
        if bad:
            flags += 1
            head, tail = "🔴", "the job will refuse at start"
            if not j.would_refuse:  # a requeued job with the warn-on-restart branch
                head, tail = "⚠️", f"requeued ({j.restarts}): will WARN and continue"
            print(
                f"  {head} {j.jobid} {j.name}: {len(bad)} of {len(j.guarded)} FAIL "
                f"({rel}; {j.md5_note}) — {tail}:"
            )
            for b in bad:
                print(
                    f"      {os.path.relpath(b.split(': ')[0], wd)}: {b.split(': ')[1]}"
                )
        else:
            print(
                f"  ✅ {j.jobid} {j.name}: {len(j.guarded)}/{len(j.guarded)} OK "
                f"({rel}; {j.md5_note})"
            )

    print(
        "\n-- EXPECT_MD5 guards (running jobs; a preemption requeue re-runs the check)"
    )
    run = [j for j in jobs if j.state == "RUNNING" and j.name != "vscode"]
    if not run:
        print("  (no running jobs)")
    for j in run:
        flags += running_guard(j)

    print(f"\n-- finished in the last {hours:g} h")
    rows = recent(user, hours)
    if not rows:
        print("  (none)")
    for jid, name, state, el, end, nodes, code in rows:
        mark = "  "
        if not state.startswith("COMPLETED") or code != "0:0":
            mark, flags = "⚠️", flags + 1
        if "halk" in nodes:
            mark, flags = "🔴", flags + 1
        print(f"  {mark} {jid} {name:<16} {state:<12} {el:>10}  end {end}  {nodes}")

    print("\n-- maintenance (next 3 weeks)")
    res = [
        r
        for r in reservations()
        if "maint" in r[0] and now < r[2] and r[1] < now + RES_HORIZON
    ]
    for name, s, e in res:
        print(f"  {name}: {s:%Y-%m-%d %H:%M} → {e:%Y-%m-%d %H:%M}")
    if not res:
        print("  (none)")
    for j in pend:
        st, lim = _when(j.start), parse_limit(j.limit)
        if st is None or lim is None:
            continue
        for name, s, e in res:
            if st < e and st + lim > s:
                flags += 1
                print(
                    f"  🔴 {j.jobid} {j.name}: est. start + {j.limit} runs into {name}"
                )

    print("\n-- home quota (GPFS cache)")
    print(quota(user))

    print(f"\n== {flags} flag(s)" if flags else "\n== all clear")
    return 1 if flags else 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--hours", type=float, default=36.0, help="finished-job window")
    ap.add_argument("--guarded", action="store_true", help="JSON of guarded files")
    a = ap.parse_args()
    user = os.environ.get("USER", "tpj8")
    if a.guarded:
        jobs = queue(user)
        attach_guards(jobs)
        print(json.dumps(guarded_map(jobs)))
        return 0
    return report(user, a.hours)


if __name__ == "__main__":
    raise SystemExit(main())
