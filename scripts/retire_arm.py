#!/usr/bin/env python
"""Retire a solved arm: keep its small record, delete its bulk — MANIFEST FIRST.

    PYTHONPATH=$PWD NJ_DOMAIN=v3 python scripts/retire_arm.py wave-stwave bed-buildings
    PYTHONPATH=$PWD NJ_DOMAIN=v3 python scripts/retire_arm.py wave-stwave --reason "…" --apply

Default is a MANIFEST ONLY: every file classified KEEP or DELETE, apparent vs TRUE reclaim
(hard-linked inputs free nothing until the last link goes), and the scratch quota. Nothing
moves until ``--apply``, and ``--apply`` does the safe half first:

    mkdir _retired/<arm>  →  move every KEEP (os.replace)  →  verify each landed at its size
    →  ONLY THEN unlink the DELETEs  →  rmdir the run dir (never rmtree; a leftover = stop)
    →  write _retired/<arm>/.retired (JSON) and append _retired/MANIFEST.md

So a failure anywhere before the first unlink leaves the run dir intact minus the KEEPs,
which are sitting whole in ``_retired/<arm>``. ``python -m nj_sfincs.premier`` lists retired
arms as ``RET`` so a moved dir does not silently vanish from the audit.

REFUSALS (each one has cost a run or would): names starting with ``_`` (the sealed template,
the buildings subgrid, ``_retired`` itself), ``floodmaps`` (the gallery), a symlink, a dir with
``restart_segments/`` (a resumed solve whose stitch is not verified), a ``sfincs_map.nc``
younger than 30 min or a job in ``squeue`` whose name carries the arm (still writing), an
existing ``_retired/<arm>`` (retire is one-way; a second run would clobber the record), and
ANY file the table below does not classify — there is no silent default for an unknown file.

⚠️ This script deletes nothing the scores need to be RE-READ: ``sfincs_his.nc`` (gauge
series), ``sfincs.inp`` / ``provenance*.txt`` / ``engine.txt`` (what ran, on what),
``snapwave.b*`` (the wave boundary), ``gis/`` and ``sfincs_net*.nc`` (the forcing) all stay.
What goes is what can be RE-MADE from those plus the sealed template: the map, the floodmap,
the restart files, the hard-linked mesh/subgrid/roughness inputs.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import nj_sfincs  # noqa: F401 — pyproj-before-hydromt import order
from nj_sfincs.config import exp_root

# ---- the classification: NO default. An unlisted file refuses the whole arm. ------------
KEEP_FILES = {
    "sfincs.inp",
    "sfincs.log",
    "sfincs_his.nc",
    "engine.txt",
    "restart_history.txt",
    "RENAMED.txt",
    "sfincs.obs",
    "sfincs.weir",
    "sfincs.crs",
    "sfincs.bnd",
    "sfincs.bzs",
    "sfincs.src",
    "sfincs.dis",
    ".window",
    ".subgrid_sha256",
    "subgrid_provenance.txt",
    "metrics.json",
    "cut_faces_reopened_idx.npy",  # hand-staged nyedge-only test: the 35 cut faces put back to outflow (stage_nyedge_only.py)
    "report.html",
}
KEEP_GLOBS = (
    "provenance*.txt",
    "snapwave.b??",
    "snapwave.bnd",
    "subgrid_*diff.json",
    "sfincs_net*.nc",
)
KEEP_DIRS = {"gis"}
DELETE_FILES = {
    "sfincs_map.nc",
    "snapwave.upw",
    "floodmap_hmax_lev3.tif",
    "floodmap_hmax_lev3.tif.aux.xml",
    "sfincs.nc",
    "sfincs_subgrid.nc",
    "roughness.nc",
}
DELETE_GLOBS = ("*.rst", "sfincs.*.rst")
DELETE_DIRS = {"subgrid"}
GALLERY = "floodmaps"
RETIRED = "_retired"
FRESH_S = 30 * 60


class Refused(RuntimeError):
    """The arm cannot be retired; the message says why. Nothing was touched."""


@dataclass
class Entry:
    path: Path  # absolute source path
    rel: str  # path relative to the run dir (or 'floodmaps/<f>' for the gallery tif)
    action: str  # KEEP | DELETE
    size: int
    nlink: int
    is_dir: bool = False


@dataclass
class Plan:
    arm: str
    root: Path
    run_dir: Path
    entries: list[Entry] = field(default_factory=list)
    reason: str = ""

    @property
    def keeps(self):
        return [e for e in self.entries if e.action == "KEEP"]

    @property
    def deletes(self):
        return [e for e in self.entries if e.action == "DELETE"]

    @property
    def apparent_reclaim(self) -> int:
        return sum(e.size for e in self.deletes)

    @property
    def true_reclaim(self) -> int:
        return sum(e.size for e in self.deletes if e.nlink == 1)


def _classify(name: str, is_dir: bool) -> str | None:
    if is_dir:
        if name in KEEP_DIRS:
            return "KEEP"
        if name in DELETE_DIRS:
            return "DELETE"
        return None
    if name in KEEP_FILES or any(fnmatch.fnmatch(name, g) for g in KEEP_GLOBS):
        return "KEEP"
    if name in DELETE_FILES or any(fnmatch.fnmatch(name, g) for g in DELETE_GLOBS):
        return "DELETE"
    return None


def _tree_size_links(d: Path) -> tuple[int, int]:
    """(bytes, min nlink) over a directory's files — a hard-linked subgrid/ frees nothing."""
    size, nlink = 0, 1 << 30
    for f in d.rglob("*"):
        if f.is_file():
            st = f.stat()
            size += st.st_size
            nlink = min(nlink, st.st_nlink)
    return size, (1 if nlink == 1 << 30 else nlink)


def _jobs_named(arm: str) -> list[str]:
    try:
        out = subprocess.run(
            ["squeue", "-u", os.environ.get("USER", ""), "-h", "-o", "%i %j"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [ln for ln in out.splitlines() if arm in ln.split(maxsplit=1)[-1]]


def plan(
    arm: str, root: Path | None = None, reason: str = "", check_queue: bool = True
) -> Plan:
    """Classify every file of ``root/arm``; raise ``Refused`` rather than guess."""
    root = Path(root or exp_root())
    if arm.startswith("_") or arm == GALLERY or "/" in arm:
        raise Refused(
            f"{arm}: refused by name (template / subgrid / gallery / _retired)"
        )
    run_dir = root / arm
    if run_dir.is_symlink():
        raise Refused(f"{arm}: is a symlink — retire the target, not the link")
    if not run_dir.is_dir():
        raise Refused(f"{arm}: no such run dir under {root}")
    if (root / RETIRED / arm).exists():
        raise Refused(f"{arm}: {RETIRED}/{arm} already exists — retire is one-way")
    if (run_dir / "restart_segments").exists():
        raise Refused(
            f"{arm}: has restart_segments/ — a resumed solve; verify the stitch "
            "and remove the segments by hand first"
        )
    m = run_dir / "sfincs_map.nc"
    if m.exists() and time.time() - m.stat().st_mtime < FRESH_S:
        raise Refused(f"{arm}: sfincs_map.nc was written < 30 min ago — still running?")
    if check_queue:
        jobs = _jobs_named(arm)
        if jobs:
            raise Refused(f"{arm}: a queued/running job carries its name: {jobs}")

    p = Plan(arm=arm, root=root, run_dir=run_dir, reason=reason)
    unknown = []
    for f in sorted(run_dir.iterdir()):
        act = _classify(f.name, f.is_dir())
        if act is None:
            unknown.append(f.name)
            continue
        if f.is_dir():
            size, nlink = _tree_size_links(f)
            p.entries.append(Entry(f, f.name, act, size, nlink, is_dir=True))
        else:
            st = f.stat()
            p.entries.append(Entry(f, f.name, act, st.st_size, st.st_nlink))
    if unknown:
        raise Refused(
            f"{arm}: unclassified file(s) — add them to KEEP or DELETE first: {unknown}"
        )
    g = root / GALLERY / f"{arm}_hmax_lev3.tif"
    if g.exists():
        st = g.stat()
        p.entries.append(
            Entry(g, f"{GALLERY}/{g.name}", "DELETE", st.st_size, st.st_nlink)
        )
    return p


def _gb(n: int) -> str:
    return f"{n / 1e9:.2f} G"


def report(p: Plan) -> str:
    lines = [f"== {p.arm}   ({p.run_dir})"]
    for e in sorted(p.entries, key=lambda e: (e.action, -e.size)):
        tag = "dir " if e.is_dir else "    "
        link = f"nlink={e.nlink}" if e.nlink > 1 else ""
        lines.append(f"  {e.action:6s} {tag}{e.rel:44s} {_gb(e.size):>9s}  {link}")
    lines.append(
        f"  apparent reclaim {_gb(p.apparent_reclaim)}   "
        f"TRUE reclaim {_gb(p.true_reclaim)} (nlink == 1 only)   "
        f"keeps {len(p.keeps)} ({_gb(sum(e.size for e in p.keeps))})"
    )
    return "\n".join(lines)


def quota() -> str:
    exe = Path("/usr/lpp/mmfs/bin/mmlsquota")
    if not exe.exists():
        return "(mmlsquota not available)"
    try:
        out = (
            subprocess.run(
                [
                    str(exe),
                    "-u",
                    os.environ.get("USER", ""),
                    "--block-size",
                    "auto",
                    "scratch",
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            .stdout.strip()
            .splitlines()
        )
    except (OSError, subprocess.TimeoutExpired):
        return "(mmlsquota failed)"
    return out[-1].strip() if out else "(no quota line)"


# ---- apply: moves before unlinks, verify between ---------------------------------------
def _verify_moved(entry: Entry, dst: Path) -> None:
    """Raise unless the KEEP landed whole. Patched by the safety test to simulate failure."""
    if entry.is_dir:
        got, _ = _tree_size_links(dst)
    else:
        got = dst.stat().st_size if dst.exists() else -1
    if got != entry.size:
        raise RuntimeError(f"{entry.rel}: moved size {got} != recorded {entry.size}")


def apply(p: Plan) -> dict:
    dst_dir = p.root / RETIRED / p.arm
    if dst_dir.exists():
        raise Refused(f"{p.arm}: {dst_dir} exists")
    dst_dir.mkdir(parents=True)

    moved = []
    for e in p.keeps:  # 1. the safe half: every KEEP moves, each verified
        dst = dst_dir / e.rel
        os.replace(e.path, dst)
        _verify_moved(e, dst)
        moved.append(e.rel)

    deleted = []
    for e in p.deletes:  # 2. only now the destructive half
        if e.is_dir:
            for f in sorted(e.path.rglob("*"), reverse=True):
                if f.is_dir():
                    os.rmdir(f)
                else:
                    os.unlink(f)
            os.rmdir(e.path)
        else:
            os.unlink(e.path)
        deleted.append(e.rel)

    leftovers = sorted(x.name for x in p.run_dir.iterdir())
    if leftovers:  # never rmtree: something we did not classify appeared
        raise RuntimeError(
            f"{p.arm}: run dir not empty after retire, NOT removed: "
            f"{leftovers} (keeps are in {dst_dir})"
        )
    os.rmdir(p.run_dir)

    rec = dict(
        arm=p.arm,
        retired=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        reason=p.reason,
        run_dir=str(p.run_dir),
        kept=moved,
        deleted=deleted,
        apparent_reclaim_bytes=p.apparent_reclaim,
        true_reclaim_bytes=p.true_reclaim,
    )
    (dst_dir / ".retired").write_text(json.dumps(rec, indent=2) + "\n")
    man = p.root / RETIRED / "MANIFEST.md"
    new = not man.exists()
    with man.open("a") as fh:
        if new:
            fh.write(
                "# Retired arms\n\n| arm | retired (UTC) | true reclaim | reason |\n"
                "|---|---|---|---|\n"
            )
        fh.write(
            f"| `{p.arm}` | {rec['retired']} | {_gb(p.true_reclaim)} | "
            f"{p.reason or '—'} |\n"
        )
    return rec


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("arms", nargs="+")
    ap.add_argument("--reason", default="", help="one line, goes into the manifest")
    ap.add_argument(
        "--apply",
        action="store_true",
        help="actually retire (default: print the manifest and stop)",
    )
    ap.add_argument(
        "--root",
        type=Path,
        default=None,
        help="experiment root (default: exp_root() for NJ_DOMAIN)",
    )
    a = ap.parse_args(argv)
    if a.apply and not a.reason:
        ap.error("--apply needs --reason (it goes into the permanent manifest)")

    print(f"scratch quota before: {quota()}")
    plans, refused = [], 0
    for arm in a.arms:
        try:
            p = plan(arm, a.root, a.reason)
        except Refused as e:
            print(f"  REFUSED {e}")
            refused += 1
            continue
        print(report(p))
        plans.append(p)
    tot_true = sum(p.true_reclaim for p in plans)
    print(
        f"\n{len(plans)} arm(s) plannable, {refused} refused; TRUE reclaim if applied "
        f"{_gb(tot_true)} (apparent {_gb(sum(p.apparent_reclaim for p in plans))})"
    )
    if not a.apply:
        print(
            "manifest only — nothing moved. Re-run with --apply --reason '…' to retire."
        )
        return 1 if refused else 0

    for p in plans:
        rec = apply(p)
        print(
            f"  retired {p.arm}: kept {len(rec['kept'])}, deleted {len(rec['deleted'])}, "
            f"true reclaim {_gb(rec['true_reclaim_bytes'])} → {p.root / RETIRED / p.arm}"
        )
    print(f"scratch quota after:  {quota()}")
    return 1 if refused else 0


if __name__ == "__main__":
    sys.exit(main())
