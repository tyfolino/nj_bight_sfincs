#!/usr/bin/env python
"""Build the canonical static mesh ONCE for the ACTIVE domain, and freeze it.

The quadtree grid + subgrid build is environment-sensitive: two builds of identical
code/config can differ by ~18 cells, enough to shift MOTF CSI by ~0.04. Freezing one mesh
and having every run reuse it removes that variance.

Usage
-----
    NJ_DOMAIN=<domain> python scripts/freeze_mesh.py        # -> data/frozen_mesh_<mesh_key>
    NJ_DOMAIN=<domain> python scripts/freeze_mesh.py DIR    # custom location

The output path is keyed on the domain's ``mesh_key``, matching ``BaseConfig.frozen_mesh``,
so a build cannot land on another domain's mesh by omission.

⚠️ TWO DOMAINS THAT DIFFER ONLY IN ``mask_zmin`` SHARE A ``mesh_key`` DELIBERATELY. Do not
run this twice for them. The second is staged from the first with
``scripts/setup_boundary_depth.py``, which re-derives the mask and boundary on a COPY and
reuses the subgrid tables — every face already carries them, since the subgrid is computed
per face from elevation + roughness and is independent of the mask. Rebuilding instead
would burn the CPU peak to produce the same tables and would risk the ~18-cell drift.

⚠️ THIS IS THE EXPENSIVE, IRREVERSIBLE STEP. Size the refinement recipe with
``scripts/probe_mesh_size.py`` FIRST — it runs the same build with ``skip_subgrid=True``,
so the face count (decided by the grid and mask) is known in minutes rather than hours.
The domain invariants also run BEFORE the subgrid, so a bad region or elevation stack
aborts early with a clear error instead of after hours of tabulation.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import nj_sfincs  # noqa: F401  (PROJ primer — must precede hydromt_sfincs)
from nj_sfincs import domain as _domain
from nj_sfincs import model
from nj_sfincs.config import ROOT, BaseConfig


def main(out: str | None = None) -> int:
    dom = _domain.active()
    out_path = Path(out) if out else dom.frozen_mesh_dir()
    if not out_path.is_absolute():
        out_path = ROOT / out_path
    print(f"domain {dom.name}  (mesh_key={dom.mesh_key or dom.name})  ->  {out_path}")

    if (out_path / "sfincs.inp").exists():
        print(
            f"Refusing to overwrite an existing mesh at {out_path} "
            f"(delete it first to re-freeze)."
        )
        return 1
    # frozen_mesh=None so build_static actually BUILDS (it copies otherwise).
    base = replace(BaseConfig(), frozen_mesh=None)
    print(f"Building canonical static mesh -> {out_path} (this is the CPU peak) ...")
    model.build_static(base, out_path)
    print(f"Done. It is now the default for domain {dom.name!r}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:]))
