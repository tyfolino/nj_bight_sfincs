#!/usr/bin/env python
"""Reclaim quota by HARD-LINKING byte-identical large files across the whole home dir.

    python scripts/dedupe_home.py            # report only
    python scripts/dedupe_home.py --apply    # actually link

WHY THIS EXISTS SEPARATELY FROM `dedupe_experiment_inputs.py`
------------------------------------------------------------
That script dedupes *within* `experiments/<domain>/` on the active repo. But the account
holds three repos plus a 29 GB raw-data store, and the same 300 MB `sfincs.nc` /
217 MB `sfincs_subgrid.nc` / 240 MB `roughness.nc` triple is copied into EVERY run dir of
every campaign — 26 campaigns' worth sit frozen in `~/nj_coast_sfincs/experiments`. The
duplication that actually fills the quota is BETWEEN roots, so the reclaim has to be too.

🔴 IT LINKS, IT NEVER DELETES. One root (`~/nj_coast_sfincs`) is a frozen archive whose
whole value is that it still holds what it held. A hard link keeps every path readable at
every location it was readable before; only the duplicate *blocks* go away. If this script
is wrong, the cost is a wasted walk, not a lost campaign.

⚠️ The flip side of a hard link: an in-place write through one path is now visible through
the other. Every writer here (xarray/netCDF4, GDAL, shutil.copy) creates a NEW file and
renames it over the target, which BREAKS the link instead of following it — that is why
this is safe for `.nc`/`.tif` data. It is NOT safe for anything edited in place, so the
scope is deliberately narrow: large binary data only, no source, no environments.

HOW TO READ THE QUOTA (this filesystem is GPFS, and `quota -s` says nothing):
    mmlsquota -u $USER --block-size auto cache      # /usr/lpp/mmfs/bin

🔴 NEVER measure headroom by `dd`-ing until ENOSPC. On 2026-08-14 that filled the
filesystem for a few seconds while three SFINCS jobs were starting; they could not create
their stdout files OR `sfincs_map.nc`, and one still exited `COMPLETED 0:0` after 14
minutes having written nothing. Ask the quota, do not probe it.

🔴 THE KEEPER MUST BE THE COPY IN THE READ-ONLY TREE. Replacing a path means creating
`<name>.dedupe-tmp` IN ITS OWN DIRECTORY, so the copy being replaced needs a writable
parent. `~/nj_coast_sfincs/data` is `dr-xr-xr-x` (the archive freeze), so a keeper chosen
by link count alone left every loser inside it and all 3.5 GB of candidates failed EPERM.
Keeping the frozen copy and relinking the writable one reclaims the same blocks and never
writes to the archive at all — strictly safer than the direction that failed.

⚠️ `freed` counts only inodes actually released. On 2026-08-14 it accumulated candidate
gain unconditionally, so a run that linked NOTHING printed `RECLAIMED: 3.5 GB` beside
`(0 files linked)`. A reclaim total that does not depend on the reclaim succeeding is the
same failure shape as a `COMPLETED 0:0` job — it reads as success and is a no-op.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from collections import defaultdict
from pathlib import Path

HOME = Path("/cache/home/tpj8")

#: Only files at least this big. All the reclaimable space is in model I/O; going smaller
#: multiplies the file count by ~100 and the reclaim by ~1%.
MIN_SIZE = 8 * 1024 * 1024

#: Extensions worth linking: bulk binary data written whole-file-then-renamed.
DATA_SUFFIXES = {".nc", ".tif", ".tiff", ".sif", ".gz", ".tar", ".zip", ".nc4",
                 ".bin", ".dat", ".npy", ".npz", ".parquet", ".gpkg", ".img"}

#: Never walk into these. Environments and caches hardlink internally by their own rules
#: (conda/pip/singularity), source control needs its objects left alone, and the editor
#: server rewrites files in place.
SKIP_DIRS = {".git", "micromamba", ".vscode-server", ".apptainer", ".cache",
             "site-packages", "node_modules", ".claude", "__pycache__", ".ipython"}


def walk(root: Path):
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            p = Path(dirpath) / fn
            if p.is_symlink() or p.suffix.lower() not in DATA_SUFFIXES:
                continue
            try:
                st = p.lstat()
            except OSError:
                continue
            if st.st_size >= MIN_SIZE:
                yield p, st


def replaceable(path: Path) -> bool:
    """Can this path be swapped for a link? Needs a writable PARENT, not a writable file.

    `os.link` writes `<name>.dedupe-tmp` into the containing directory, so a read-only
    file in a writable dir is fine and a writable file in a read-only dir is not.
    """
    return os.access(path.parent, os.W_OK)


def sha(path: Path, size: int) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(8 << 20):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="link (default: report only)")
    ap.add_argument("--root", default=str(HOME), help="tree to dedupe")
    ap.add_argument("--min-mb", type=float, default=MIN_SIZE / 1048576)
    args = ap.parse_args()
    min_size = int(args.min_mb * 1048576)

    by_size: dict[int, list] = defaultdict(list)
    n = 0
    for p, st in walk(Path(args.root)):
        if st.st_size >= min_size:
            by_size[st.st_size].append((p, st))
            n += 1
    print(f"scanned {n} data files >= {args.min_mb:.0f} MB under {args.root}\n")

    freed = 0
    linked = 0
    blocked = 0
    # Only sizes with more than one file can hold a duplicate; hashing is the expensive
    # step so it is paid only for those.
    for size, entries in sorted(by_size.items(), key=lambda kv: -kv[0] * len(kv[1])):
        if len(entries) < 2:
            continue
        by_hash: dict[str, list] = defaultdict(list)
        for p, st in entries:
            try:
                by_hash[sha(p, size)].append((p, st))
            except OSError:
                continue
        for digest, group in by_hash.items():
            # An INODE is what holds blocks, and it is released only when EVERY path
            # pointing at it has been relinked. Reason in inodes, not in paths.
            by_inode: dict[int, list[Path]] = defaultdict(list)
            nlink: dict[int, int] = {}
            for p, st in group:
                by_inode[st.st_ino].append(p)
                nlink[st.st_ino] = st.st_nlink
            if len(group) < 2 or len(by_inode) < 2:
                continue

            # Keep the copy that CANNOT be replaced (read-only parent, i.e. the frozen
            # archive) — the losers then all sit in writable dirs. Among equals, keep the
            # one with the most links: it frees the most at once. Choosing by link count
            # alone is what left every loser in the archive and reclaimed nothing.
            def rank(ino: int) -> tuple[int, int]:
                stuck = not all(replaceable(p) for p in by_inode[ino])
                return (1 if stuck else 0, nlink[ino])

            keep_ino = max(by_inode, key=rank)
            keeper = by_inode[keep_ino][0]

            losers = {i: ps for i, ps in by_inode.items() if i != keep_ino}
            movable = {i: ps for i, ps in losers.items()
                       if all(replaceable(p) for p in ps)}
            gain = size * len(movable)
            stuck_bytes = size * (len(losers) - len(movable))

            print(f"  {keeper.name:<28} {digest[:8]}  {len(group)} copies, "
                  f"{len(by_inode)} inodes ({size / 1048576:7.0f} MB)"
                  f"  -> {gain / 1048576:8.0f} MB")
            print(f"      keep {keeper.relative_to(HOME)}")
            for ino, paths in losers.items():
                if ino not in movable:
                    for p in paths:
                        print(f"      BLOCKED (read-only dir) {p.relative_to(HOME)}")
                    continue
                ok = True
                for p in paths:
                    print(f"      link {p.relative_to(HOME)}")
                    if not args.apply:
                        continue
                    tmp = p.with_name(p.name + ".dedupe-tmp")
                    try:
                        os.link(keeper, tmp)
                        os.replace(tmp, p)
                        linked += 1
                    except OSError as exc:
                        print(f"        SKIPPED ({exc})")
                        tmp.unlink(missing_ok=True)
                        ok = False
                # Only a fully-relinked inode actually gives its blocks back. In report
                # mode nothing was relinked, so the estimate comes from `gain` instead —
                # counting both is what once reported exactly double the real figure.
                if args.apply and ok:
                    freed += size
            if not args.apply:
                freed += gain
            blocked += stuck_bytes

    verb = "RECLAIMED" if args.apply else "reclaimable"
    print(f"\n{verb}: {freed / 1024**3:.1f} GB"
          + (f" ({linked} files linked)" if args.apply else " — rerun with --apply"))
    if blocked:
        print(f"blocked by a read-only parent dir: {blocked / 1024**3:.1f} GB "
              f"(both copies frozen — chmod u+w one side to reclaim)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
