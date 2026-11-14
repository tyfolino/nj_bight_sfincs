"""Mesh-size probe of ONE refinement file on the ACTIVE domain's ring + coarse bed.

    NJ_DOMAIN=v4 python logs/nj2_refinement_2026-11-14/probe_variant.py <refinement.geojson> <out_dir>

`scripts/probe_mesh_size.py` with two changes: the refinement file is an argument (the
domain's own is replaced), and a mask / boundary / invariant failure is PRINTED, not fatal.
The face count is set by the grid alone, before the mask; on v4's ring the Narrows variant
moves the `narrows` arm's cell count out of its v4 bracket, which must not lose the count.
Writes `<out_dir>/domain_dryrun.npz` (x, y, z, mask, level per face). Idempotent.
"""

from __future__ import annotations

import sys
import traceback
from dataclasses import replace
from pathlib import Path

import numpy as np

import nj_sfincs  # noqa: F401  (pyproj before hydromt_sfincs)
from nj_sfincs import domain as _domain
from nj_sfincs import model
from nj_sfincs.config import BaseConfig


def _lenient(fn):
    def wrap(*a, **k):
        try:
            return fn(*a, **k)
        except Exception:  # noqa: BLE001
            print(f"[probe] ⚠️ {fn.__name__} raised (continuing, count unaffected):")
            traceback.print_exc(limit=3)

    return wrap


def main(ref: str, out: str) -> int:
    out_p = Path(out)
    npz = out_p / "domain_dryrun.npz"
    dom = _domain.active()
    print(f"[probe] domain {dom.name}  refinement {ref}  -> {out_p}")
    if not npz.exists():
        base = replace(BaseConfig(), frozen_mesh=None, refinement=Path(ref))
        model.apply_mask_and_boundary = _lenient(model.apply_mask_and_boundary)
        model.build_static(base, out_p, skip_subgrid=True)
    d = np.load(npz)
    lev, m = d["level"], d["mask"]
    print(
        f"[probe] FACES {len(lev):,}  active {int((m > 0).sum()):,}  "
        f"mask2 {int((m == 2).sum()):,}  mask3 {int((m == 3).sum()):,}"
    )
    for L in np.unique(lev):
        s = lev == L
        print(
            f"[probe]   {200.0 / 2 ** (int(L) - 1):6.1f} m  {int(s.sum()):>10,}  "
            f"(active {int((m[s] > 0).sum()):>10,})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
