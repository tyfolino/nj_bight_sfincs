"""Hard-link byte-identical experiment INPUT files to reclaim disk.

Every experiment staged from a frozen mesh carries its own full copy of the same
mesh/subgrid/roughness inputs (~1.2 GB each). With ~26 experiments on disk that is
>30 GB of pure duplication, and it is what pushed us over the disk quota on
2026-07-13 (killing two running jobs mid-write).

Files are grouped by (basename, md5) and every duplicate in a group is replaced by a
HARD LINK to one canonical copy. Grouping by content — not by name — matters: the
narrows_wide_* runs carry a REBUILT (dredged) subgrid and nw_open/nw_wall sit on the
12.5 m mesh, so they must NOT be linked to the 25 m originals. Content grouping keeps
those separate automatically.

Hard links are safe here: SFINCS only ever READS these files, a hard link is
indistinguishable from a regular file inside the Singularity bind mount, and deleting
one experiment dir just decrements the link count.

NOT touched: sfincs_map.nc / sfincs_his.nc (results, all distinct), sfincs.inp (the
one file that differs per run), snapwave.upw (SFINCS-generated; delete it instead).

Usage:  python scripts/dedupe_experiment_inputs.py [--apply] [--domain D ...]
        (default = dry run over every domain; --help prints this and touches nothing)

The dry run still md5s every candidate (~40 min over all domains): pass --domain to
limit the walk. Grouping only ever links byte-identical files, so a --domain run can
miss a cross-domain twin, never mislink one.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from collections import defaultdict
from pathlib import Path

from nj_sfincs.config import ROOT

# ALL domains, not exp_root()'s single one. Grouping is by (basename, md5), so a file is
# only ever linked to a byte-identical twin — two domains with different meshes simply
# never match, and the cross-domain scan costs nothing but finds the cases that do (a
# shared roughness/subgrid tier between domains built from the same source rasters).
EXP = ROOT / "experiments"

# Large, read-only inputs that are identical across runs staged from the same mesh.
TARGETS = {"sfincs.nc", "sfincs_subgrid.nc", "roughness.nc"}
TARGET_DIRS = {"subgrid"}  # dep_/manning_ subgrid GeoTIFFs
MIN_BYTES = 1 << 20  # don't bother with small files


def md5(p: Path, chunk: int = 1 << 22) -> str:
    h = hashlib.md5()
    with p.open("rb") as fh:
        while b := fh.read(chunk):
            h.update(b)
    return h.hexdigest()


def runs(domains: set[str] | None = None):
    """Every run dir, across every domain (or only `domains`): experiments/<domain>/<arm>.

    The extra nesting level arrived with the 2026-08-05 domain namespacing. Walking
    `EXP.iterdir()` directly would iterate the DOMAIN dirs and find no `sfincs.nc` in
    them — which reports "0 files, 0.0 GB" and reads exactly like "already deduped".
    """
    for dom in sorted(EXP.iterdir()):
        if not dom.is_dir() or (domains is not None and dom.name not in domains):
            continue
        for run in sorted(dom.iterdir()):
            # _retired/ holds keeps only (scripts/retire_arm.py); floodmaps/ is the gallery
            if run.is_dir() and run.name not in {"_retired", "floodmaps"}:
                yield run


def candidates(domains: set[str] | None = None):
    for run in runs(domains):
        for f in sorted(run.iterdir()):
            if f.is_file() and f.name in TARGETS and f.stat().st_size >= MIN_BYTES:
                yield f
        for d in TARGET_DIRS:
            sub = run / d
            if sub.is_dir():
                for f in sorted(sub.iterdir()):
                    if f.is_file() and f.stat().st_size >= MIN_BYTES:
                        yield f


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Hard-link byte-identical experiment INPUT files "
        "(sfincs.nc, sfincs_subgrid.nc, roughness.nc, subgrid/*) across "
        "experiments/<domain>/<arm>. Default is a DRY RUN (it still hashes everything)."
    )
    ap.add_argument(
        "--apply", action="store_true", help="replace duplicates with hard links"
    )
    ap.add_argument(
        "--domain",
        action="append",
        metavar="D",
        help="only walk experiments/D (repeatable; default: every domain)",
    )
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    apply = args.apply
    domains = set(args.domain) if args.domain else None
    if domains is not None:
        missing = sorted(d for d in domains if not (EXP / d).is_dir())
        if missing:
            raise SystemExit(f"no such domain dir under {EXP}: {', '.join(missing)}")
    groups: dict[tuple[str, str], list[Path]] = defaultdict(list)
    print("hashing…", flush=True)
    for f in candidates(domains):
        groups[(f.name, md5(f))].append(f)

    saved = 0
    linked = 0
    for (name, digest), files in sorted(groups.items()):
        if len(files) < 2:
            continue
        canon = files[0]
        canon_ino = canon.stat().st_ino
        dups = [f for f in files[1:] if f.stat().st_ino != canon_ino]
        if not dups:
            continue
        size = canon.stat().st_size
        # Bytes freed = (distinct inodes - 1) x size, NOT (files - 1) x size. Several of
        # the `dups` usually already share ONE inode with each other; re-linking them
        # frees one physical copy between them, not one per file. Counting files
        # overstated the 2026-08-05 reclaim as 17.5 GB when the truth was 9.3 GB.
        n_ino = len({f.stat().st_ino for f in files})
        print(
            f"  {name:<28} {digest[:8]}  {len(files):2d} copies, {n_ino} inodes "
            f"({size / (1 << 20):6.0f} MB)  -> linking {len(dups)}, freeing "
            f"{(n_ino - 1) * size / (1 << 20):.0f} MB"
        )
        for d in dups:
            if apply:
                tmp = d.with_suffix(d.suffix + ".dedupe_tmp")
                os.link(canon, tmp)  # link first, then atomically replace
                os.replace(tmp, d)
            linked += 1
        saved += (n_ino - 1) * size

    G = 1 << 30
    print(
        f"\n{'APPLIED' if apply else 'DRY RUN'}: {linked} files -> hard links, "
        f"{saved / G:.1f} GB reclaimed"
    )
    if not apply:
        print("re-run with --apply to do it")


if __name__ == "__main__":
    main()
