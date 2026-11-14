#!/usr/bin/env python
"""Run scripts/build_naccs_boundary.py for Model 2.0 (nj2) on the nj2 zip set, touching nothing of v4's.

    NJ_DOMAIN=<nj2 domain> python -I logs/nj2_edges_2026-11-14/build_naccs_boundary_nj2.py [builder args]
    NJ_DOMAIN=<nj2 domain> python -I logs/nj2_edges_2026-11-14/build_naccs_boundary_nj2.py --parse-only

Why a wrapper: the builder reads every ``data/NACCS/*.zip`` and caches its parse in
``data/NACCS/_sandy_parsed.npz``. The 2026-11-02 Hudson / East River pull was moved OUT of
``data/NACCS/`` (to ``hudson_pull_2026-11-02/``) so that a v4 rebuild cannot pick up Upper Bay
points near its ``narrows`` / ``kvk_east`` arms. This wrapper points the builder at
``data/nj2_design/naccs/`` instead: SYMLINKS to the same 7 zips in ``data/NACCS/`` plus the
8 Hudson zips; nothing is moved or rewritten. Three module globals are swapped, nothing else:

* ``NACCS``        -> ``data/nj2_design/naccs``  (the zip glob)
* ``PARSE_CACHE``  -> ``data/nj2_design/naccs/_sandy_parsed_nj2.npz``  (v4's cache untouched)
* ``VDATUM_CACHE`` -> ``data/nj2_design/naccs/vdatum_lmsl_navd88_nj2.csv`` (a copy of v4's; new
  points get their MSL->NAVD88 offset from the same offline grids, ``VDATUM_GRIDS`` stays
  ``data/NACCS/vdatum_grids``)

The output is the builder's own: ``data/gtsm/naccs_sandy_<domain>.nc``. Every other rule
(dedupe asserted identical, Sandy = storm 001, dry-at-any-step dropped, 2 km screen against
the frozen mesh's mask==2 cells, per-arm coverage, the Sandy Hook datum anchor) is unchanged.
``--parse-only`` runs just the parse + dedupe (no domain, no mesh) and prints the save points
near the two new cuts.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import pyproj  # noqa: E402,F401  (project convention: pyproj before hydromt)

import build_naccs_boundary as B  # noqa: E402

NJ2 = ROOT / "data" / "nj2_design" / "naccs"
B.NACCS = NJ2
B.PARSE_CACHE = NJ2 / "_sandy_parsed_nj2.npz"
B.VDATUM_CACHE = NJ2 / "vdatum_lmsl_navd88_nj2.csv"
assert B.VDATUM_GRIDS == ROOT / "data" / "NACCS" / "vdatum_grids"

# The two new cuts (logs/v2_prep_2026-11-04/ring_recommended_v2edit.csv, forced vertices).
CUTS = {
    "hudson": ((-73.95753, 40.8600), (-73.9345, 40.8600)),
    "hell_gate": ((-73.9425, 40.7765), (-73.9345, 40.7775)),
}


def parse_only() -> int:
    import numpy as np
    import shapely

    pts = B.read_zips(use_cache=True)
    times = pts.pop("_times")
    print(f"[nj2] {len(pts)} unique save points, {len(times)} steps")
    t = pyproj.Transformer.from_crs(4326, 32618, always_xy=True)
    sp = np.array(sorted(pts))
    lon = np.array([pts[s]["lon"] for s in sp])
    lat = np.array([pts[s]["lat"] for s in sp])
    x, y = t.transform(lon, lat)
    for name, (a, b) in CUTS.items():
        ln = shapely.LineString([t.transform(*a), t.transform(*b)])
        d = shapely.distance(ln, shapely.points(x, y))
        for k in np.argsort(d)[:12]:
            if d[k] > 2000:
                break
            w = pts[int(sp[k])]["wl"]
            dry = int((w < B.DRY).sum())
            print(f"  {name:<9} SP{int(sp[k]):<6} {d[k]:6.0f} m  depth {pts[int(sp[k])]['depth']:6.2f}"
                  f"  dry steps {dry:4d}  peak {np.nanmax(np.where(w < B.DRY, np.nan, w)):.3f} m MSL")
    return 0


if __name__ == "__main__":
    if "--parse-only" in sys.argv:
        sys.exit(parse_only())
    sys.exit(B.main())
