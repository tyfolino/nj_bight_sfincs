#!/usr/bin/env python
"""J1b read-out: the nj2 probes against each other and against v4's frozen mesh. Read-only.

    NJ_DOMAIN=nj2 python logs/nj2_freeze_2026-11-14/j1b_compare.py <probe_dir> <v4_mesh_cache.npz> <noext_refinement.geojson>

Variants in <probe_dir>: c0_v4only (v4's recipe on the nj2 ring), f1_final (the 2.0.0 file),
f2_noext (the 2.0.0 file without the new-ground narrow channels).

1. faces / active / mask2 / mask3 per variant, vs v4 / 1.1.0 (4,881,654).
2. faces the new-ground narrow channels add (f1 - f2), and where (25 m faces gained, ~1 km cells).
3. OLD-GROUND IDENTITY: every face (centre x, y, level) of v4's frozen mesh vs the probe's, on
   the common grid, split by distance to ground the recipe CHANGED on purpose (new / trimmed ring
   ground, and for f1 the new bands + the dropped `narrows_cut`); expected 0 mismatches > 1 km
   from it (the 2:1 transition reaches a few cells).
4. per-arm boundary census (mask 2 inside each declared arm) for c0 and f1 + the two NY walls.
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

import nj_sfincs  # noqa: F401
from nj_sfincs import domain as D

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import build_refinement_nj2 as B  # noqa: E402
import build_refinement_v4 as V4R  # noqa: E402

F0 = 4_881_654
CHANGED_BANDS = ("hudson_waterfront", "newark_meadowlands", "capemay_inlets")


def _load(p):
    d = np.load(p)
    return {k: d[k] for k in d.files}


def _keys(d):
    return pd.DataFrame(
        {
            "x": np.round(d["x"] * 10).astype(np.int64),
            "y": np.round(d["y"] * 10).astype(np.int64),
            "level": d["level"].astype(np.int64),
        }
    )


def _v(d):
    """Grid-frame row coordinate (v4's frozen quadtree: x0, y0, rotation)."""
    from netCDF4 import Dataset

    with Dataset(ROOT / "data" / "frozen_mesh_v4" / "sfincs.nc") as nc:
        x0, y0, rot = (float(nc.getncattr(k)) for k in ("x0", "y0", "rotation"))
    r = np.radians(rot)
    return -(d["x"] - x0) * np.sin(r) + (d["y"] - y0) * np.cos(r)


def identity(name, d, v4, changed, top_v):
    """Faces of v4's mesh missing from the probe (and vice versa), by distance to `changed`."""
    a, b = _keys(v4), _keys(d)
    # the common grid: nj2's rectangle (same x0, y0, rotation) is 25 rows shorter at the top
    a = a[_v(v4) < top_v]
    b = b[_v(d) < top_v]
    m = a.merge(b, how="outer", indicator=True)
    only = m[m["_merge"] != "both"]
    pts = shapely.points(only.x.values / 10.0, only.y.values / 10.0)
    dist = shapely.distance(changed, pts)
    near = dist <= 1000.0
    print(
        f"\n== {name}: old-ground identity vs v4's frozen mesh (common grid, grid row v < {top_v:.0f} m)"
        f"\n   faces v4 {len(a):,}  probe {len(b):,}  identical {int((m['_merge'] == 'both').sum()):,}"
        f"\n   differ: {len(only):,} ({int((only['_merge'] == 'left_only').sum()):,} v4-only, "
        f"{int((only['_merge'] == 'right_only').sum()):,} probe-only); within 1 km of changed "
        f"ground {int(near.sum()):,}; FARTHER {int((~near).sum()):,}"
    )
    if (~near).any():
        far = only[~near].copy()
        far["cx"] = (far.x // 50_000) * 5
        far["cy"] = (far.y // 50_000) * 5
        print("   farther-than-1-km differences by 5 km cell (UTM km):")
        print(
            far.groupby(["cx", "cy"])
            .size()
            .sort_values(ascending=False)
            .head(15)
            .to_string()
        )
    return int((~near).sum())


def census(name, d, dom):
    m, x, y = d["mask"], d["x"], d["y"]
    print(f"\n== {name}: boundary census")
    print(
        f"   faces {m.size:,}; active {(m > 0).sum():,}; mask2 {(m == 2).sum():,}; mask3 {(m == 3).sum():,}"
    )
    claimed = np.zeros(m.size, bool)
    out = {}
    for a in dom.boundary_arms:
        sel = a.contains(x, y) & (m == 2)
        claimed |= sel
        n = int(sel.sum())
        out[a.name] = n
        flag = "" if a.min_cells <= n <= a.max_cells else "  🔴 OUTSIDE"
        print(
            f"   arm {a.name:20s} {n:6d}  (bracket {a.min_cells}..{a.max_cells}){flag}"
        )
    print(f"   mask2 outside every arm: {int(((m == 2) & ~claimed).sum())}")
    for o in dom.mask_overrides:
        if o.name in ("wall_e88", "wall_hellgate_east"):
            x0, y0, x1, y1 = o.box
            s = (x > x0) & (x < x1) & (y > y0) & (y < y1) & (m > 0)
            print(
                f"   {o.name}: {int(s.sum())} active faces in box, mask3 {int((s & (m == 3)).sum())}"
            )
    return out


def main(probe_dir, v4_cache, noext_ref) -> int:
    P = Path(probe_dir)
    dom = D.active()
    v4 = _load(v4_cache)
    V = {
        n: _load(P / n / "domain_dryrun.npz")
        for n in ("c0_v4only", "f1_final", "f2_noext")
    }
    print(f"v4 / 1.1.0 mesh: {len(v4['x']):,} faces")
    for n, d in V.items():
        lev = d["level"]
        per = "  ".join(
            f"{200 / 2 ** (L - 1):g} m {int((lev == L).sum()):,}"
            for L in np.unique(lev)
        )
        print(
            f"{n:10s} faces {len(lev):,} ({len(lev) - F0:+,} vs v4, "
            f"{(len(lev) / F0 - 1) * 100:+.2f} %)  active {int((d['mask'] > 0).sum()):,}  [{per}]"
        )

    # 2. the new-ground narrow channels
    f1, f2 = V["f1_final"], V["f2_noext"]
    k1, k2 = _keys(f1), _keys(f2)
    mm = k1.merge(k2, how="outer", indicator=True)
    gain = mm[mm["_merge"] == "left_only"]
    print(
        f"\n== new-ground narrow channels: f1 - f2 = {len(f1['x']) - len(f2['x']):+,} faces "
        f"(active {int((f1['mask'] > 0).sum()) - int((f2['mask'] > 0).sum()):+,}); faces only in f1 "
        f"{len(gain):,} (of them 25 m: {int((gain.level == 4).sum()):,}), only in f2 "
        f"{int((mm['_merge'] == 'right_only').sum()):,}"
    )
    from pyproj import Transformer

    t = Transformer.from_crs(32618, 4326, always_xy=True)
    g4 = gain[gain.level == 4]
    lo, la = t.transform(g4.x.values / 10.0, g4.y.values / 10.0)
    cell = pd.DataFrame({"lon": np.round(lo, 2), "lat": np.round(la, 2)})
    print("   25 m faces gained, by ~1 km cell (lon, lat):")
    print(cell.value_counts().sort_index().to_string())

    # 3. identity
    land = B.landward(dom, None)
    land4 = V4R.landward()
    ring = gpd.read_file(dom.region).to_crs(32618).geometry.iloc[0]
    ring4 = gpd.read_file(D.DOMAINS["v4"].region).to_crs(32618).geometry.iloc[0]
    ground = shapely.union_all(
        [land.symmetric_difference(land4), ring.symmetric_difference(ring4)]
    )
    ref = gpd.read_file(B.V4_FILE).to_crs(32618).dissolve("name")
    fin = gpd.read_file(dom.refinement).to_crs(32618).dissolve("name")
    bands = shapely.union_all(
        [fin.geometry[b] for b in CHANGED_BANDS] + [ref.geometry["narrows_cut"]]
    )
    top_v = min(_v(f1).max(), _v(v4).max()) - 1000.0
    far_c0 = identity("c0_v4only", V["c0_v4only"], v4, ground, top_v)
    far_f1 = identity("f1_final", f1, v4, shapely.union_all([ground, bands]), top_v)

    # 4. census
    census("c0_v4only (control)", V["c0_v4only"], dom)
    census("f1_final", f1, dom)
    print(f"\nRESULT identity_far_c0={far_c0} identity_far_f1={far_f1}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:]))
