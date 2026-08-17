#!/usr/bin/env python
"""Rewrite ``sfincs.obs`` from the domain registry, WITHOUT rebuilding the template.

WHY THIS EXISTS (2026-08-17)
----------------------------
Observation points are diagnostic: SFINCS writes a time series at each one into
``sfincs_his.nc`` and the solution does not depend on them. But ``sfincs.obs`` is only
written by ``build_static`` -> ``sf.observation_points.create``, which sits behind the
subgrid rebuild — by far the most expensive step — and ``build_template()`` calls
``rmtree`` on its target. So "add a gauge" used to imply "rebuild the mesh", which is
absurd for a change that cannot move a single water level.

Adding a gauge to ``Domain.obs_gauges`` also makes ``premier.assert_sealed_domain`` raise
``WrongDomainError`` on every already-staged dir, because ``obs_points_ok`` requires every
registered gauge to be present in ``sfincs.obs``. This script is what closes that gap: it
re-syncs the text file, the audit goes green, and the arms can simply be re-run to pick up
the new stations.

🔴 THE FORMAT IS VERIFIED, NOT ASSUMED. ``--check`` regenerates the file from the gauges
ALREADY present and asserts it reproduces the existing bytes exactly. If hydromt's writer
ever changes, that fails loudly instead of writing a file SFINCS parses differently. The
default mode runs that check first and refuses to write if it fails.

⚠️ Re-running the solver is still required for the new stations to appear in
``sfincs_his.nc``. This only changes what the NEXT run will record.

Usage:
    PYTHONPATH=$PWD python scripts/sync_obs_points.py --check
    PYTHONPATH=$PWD python scripts/sync_obs_points.py --apply
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pyproj import Transformer

import nj_sfincs  # noqa: F401 — pins the pyproj-before-hydromt import order
from nj_sfincs import domain as _domain
from nj_sfincs.config import exp_root


def render(gauges, epsg: int) -> str:
    """The exact text hydromt's observation_points writer produces."""
    tf = Transformer.from_crs(4326, epsg, always_xy=True)
    out = []
    for g in gauges:
        x, y = tf.transform(g.lon, g.lat)
        out.append(f'{x:11.1f} {y:11.1f} "{g.name}"')
    return "\n".join(out) + "\n"


def existing_names(path: Path) -> list[str]:
    names = []
    for line in path.read_text().splitlines():
        if '"' in line:
            names.append(line.split('"')[1])
    return names


def check_roundtrip(path: Path, dom) -> tuple[bool, str]:
    """Regenerate from the gauges ALREADY in the file and compare bytes."""
    have = existing_names(path)
    subset = [g for g in dom.obs_gauges if g.name in have]
    if len(subset) != len(have):
        missing = set(have) - {g.name for g in subset}
        return False, f"file has station(s) absent from the registry: {sorted(missing)}"
    # preserve the file's own ordering, which is what hydromt wrote
    subset.sort(key=lambda g: have.index(g.name))
    got, want = render(subset, dom.epsg), path.read_text()
    if got != want:
        return False, (
            "format drift — regenerating the CURRENT points does not reproduce the file:\n"
            f"  existing: {want.splitlines()[0]!r}\n"
            f"  rendered: {got.splitlines()[0]!r}"
        )
    return True, f"format verified on {len(subset)} existing point(s)"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--apply", action="store_true",
                   help="write the file; without it nothing is modified")
    p.add_argument("--check", action="store_true",
                   help="only verify the format round-trip, never write")
    p.add_argument("--dirs", nargs="*", default=None,
                   help="run dirs (default: every dir with a sfincs.obs on this domain)")
    a = p.parse_args()

    dom = _domain.active()
    root = exp_root()
    dirs = [Path(d) for d in a.dirs] if a.dirs else sorted(
        d for d in root.iterdir() if d.is_dir() and (d / "sfincs.obs").exists()
    )
    if not dirs:
        print(f"no dir with a sfincs.obs under {root}")
        return 1

    print(f"domain {dom.name}: registry has {len(dom.obs_gauges)} gauge(s)")
    rc = 0
    for d in dirs:
        obs = d / "sfincs.obs"
        ok, msg = check_roundtrip(obs, dom)
        have = existing_names(obs)
        want = [g.name for g in dom.obs_gauges]
        adding = [n for n in want if n not in have]
        dropping = [n for n in have if n not in want]
        status = "OK " if ok else "BAD"
        print(f"  {status} {d.name:24s} {len(have)} -> {len(want)}  {msg}")
        if adding:
            print(f"        + {', '.join(adding)}")
        if dropping:
            print(f"        - {', '.join(dropping)}")
        if not ok:
            rc = 1
            continue
        if a.apply and not a.check:
            obs.write_text(render(dom.obs_gauges, dom.epsg))
            print(f"        wrote {obs}")

    if not a.apply and not a.check:
        print("\nnothing written — pass --apply")
    if a.apply:
        print("\n⚠️  Re-run the solver: the new stations only appear in a NEW sfincs_his.nc.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
