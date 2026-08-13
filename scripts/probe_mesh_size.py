#!/usr/bin/env python
"""Cell-count probe: how big is the mesh, BEFORE paying for the subgrid?

The subgrid is the expensive step by a wide margin (it samples every elevation
tier at ~3 m subgrid pixels across every face). The face count, though, is fixed
by the grid + mask alone — which `build_static(..., skip_subgrid=True)` produces
in minutes. So the refinement recipe can be tuned against a real measurement
instead of an area estimate, and the full build run once against the chosen one.

It also reports the two domain invariants and a runtime projection, so a bad
refinement or a leaking boundary shows up here rather than hours later.

Usage:
    NJ_ROOT=$PWD PYTHONPATH=$PWD python scripts/probe_mesh_size.py [out_dir]
"""

from __future__ import annotations

import shutil
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

import nj_sfincs  # noqa: F401
from nj_sfincs import model
from nj_sfincs import domain as _domain
from nj_sfincs.config import ROOT, BaseConfig

# The sealed v1 premier, as the yardstick: 547,408 faces at ~3.95 s/iteration
# for the coupled SnapWave solve, and 6.18 s/iteration for the deep-boundary
# variant. SnapWave is 90-95% of runtime and scales per-iteration with cell
# count, so faces ratio ~ runtime ratio.
V1_FACES = 547_408
V1_HOURS_PREMIER = 3.0
V1_HOURS_DEEP = 3.08


def main(out: str = "data/probe_mesh") -> int:
    out_path = Path(out)
    if not out_path.is_absolute():
        out_path = ROOT / out_path
    # Reuse an existing dry run. `--rebuild` forces a fresh one; without this
    # guard the wipe below would delete the npz we are about to look for, and
    # every re-analysis would silently pay the full ~8 min build again.
    rebuild = "--rebuild" in sys.argv
    dryrun = out_path / "domain_dryrun.npz"
    if rebuild and out_path.exists():
        shutil.rmtree(out_path)

    dom = _domain.active()
    base = replace(BaseConfig(), frozen_mesh=None)
    print(f"probing domain {dom.name!r}")
    print(f"  region     {base.region}")
    print(f"  refinement {base.refinement}")
    print(f"  mask_zmin  {base.mask_zmin}\n")

    if not dryrun.exists():
        model.build_static(base, out_path, skip_subgrid=True)
    else:
        print(f"reusing existing dry run at {dryrun} (pass --rebuild to redo)\n")

    # skip_subgrid=True does NOT write sfincs.nc — it stops after mask/boundary
    # and dumps face coords + z + mask to domain_dryrun.npz. That is deliberate
    # (the point is to avoid the expensive step), so read the npz.
    d = np.load(dryrun)
    fx, fy, zb, m = d["x"], d["y"], d["z"], d["mask"]
    faces = len(zb)
    active = int((m > 0).sum())

    print("\n" + "=" * 64)
    print(f"FACES {faces:,}   active {active:,}   "
          f"waterlevel-BC {int((m == 2).sum()):,}   outflow {int((m == 3).sum()):,}")
    ratio = faces / V1_FACES
    print(f"vs sealed v1 ({V1_FACES:,}): x{ratio:.2f}  ({faces - V1_FACES:+,} faces)")
    print(f"projected SnapWave runtime: premier-style ~{V1_HOURS_PREMIER * ratio:.1f} h, "
          f"deep-boundary ~{V1_HOURS_DEEP * ratio:.1f} h")

    # ── Invariants ──────────────────────────────────────────────────────────
    print("\ninvariants:")
    n_wet_out = int(((m == 3) & (zb < -1.0)).sum())
    print(f"  free-outflow BC on water : {n_wet_out}  "
          f"{'OK' if n_wet_out == 0 else '*** LEAK ***'}")

    # The artificial south edge must resolve to a WALL, not a drain. Anything
    # still flagged mask==3 down there would be a Neumann boundary on the
    # Manahawkin cross-section.
    south = fy < 4_400_000
    if south.any():
        print(f"  south edge (y<4.40e6)    : {int((m[south] == 3).sum())} outflow, "
              f"{int((m[south] == 2).sum())} waterlevel, "
              f"{int((m[south] == 1).sum()):,} active")

    # NOTE: the X1 hazard check (SnapWave-active + SFINCS-inactive + dry) cannot
    # run here. snapwave_mask is set in add_waves, not build_static, so the dry
    # run has no wave mask to inspect. It has to be checked after the wave block.

    # ── Where did the cells go? ─────────────────────────────────────────────
    print("\nface count by region:")
    for label, sel in [
        ("southern lobe (y < 4.446e6)", fy < 4_446_000),
        ("v1 footprint  (y >= 4.446e6)", fy >= 4_446_000),
    ]:
        print(f"  {label:30s} {int(sel.sum()):>9,}  "
              f"(active {int((m[sel] > 0).sum()):>9,})")

    print("\nactive faces by depth band:")
    a = m > 0
    for lo, hi in [(-1e9, -30), (-30, -20), (-20, -10), (-10, -2), (-2, 0), (0, 1e9)]:
        n = int((a & (zb >= lo) & (zb < hi)).sum())
        print(f"  z [{lo:>8.0f}, {hi:>6.0f})  {n:>9,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:]))
