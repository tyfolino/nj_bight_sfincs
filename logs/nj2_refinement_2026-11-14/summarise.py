"""Read the probe npz files: faces per variant, faces added per new band, the global flow
time step, and a runtime estimate.

    python logs/nj2_refinement_2026-11-14/summarise.py <probe_dir> <control.npz> <mesh_now_cache.npz> <refinement.geojson> name...

* faces added per band = faces inside the band polygon (+300 m for the 2:1 transition ring)
  in the variant minus in the control probe (`p0_v4`: v4's own file on v4's ring; the bands do not touch each other).
* time step: SFINCS takes ONE dt for the whole mesh, alpha * min over uv points of
  dx / max(sqrt(g h), |u|) (sfincs_momentum.f90 L727). Estimated per active face as
  0.5 * dx / sqrt(g (zs - zmin)), zs = +1 m, zmin = the lowest subgrid pixel of the CURRENT
  (v1.1.0) faces under it (a finer child's zmin is >= its parent's, so for a new 12.5 m face
  this is a LOWER bound on dt, i.e. pessimistic). Checked on the current mesh: 0.684 s at the
  Narrows against the 1.1.0 premier's logged average 0.689 s.
* runtime: the 1.1.0 premier's log split (flow-type work 70 %: momentum 49.2, continuity
  12.3, meteo 4.8, infiltration 2.4, wave maker 1.1, boundaries 0.5 — per face per step;
  SnapWave 28 % — per face per hourly call, independent of dt; I/O 1.6 % — per face), scaled
  from the production 72 h waves-on run on 4,881,654 faces = 2.5 h at 64 threads (FINDINGS §20,
  9,052 s). Assumes cost per face is the same everywhere (SnapWave iterations, wet fraction).
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
from scipy.spatial import cKDTree

G, ALPHA, ZS = 9.81, 0.5, 1.0
F0, T0 = 4_881_654, 9052.0
FLOW, SW, IO = 0.704, 0.280, 0.016
BANDS = (
    "hudson_waterfront",
    "newark_meadowlands",
    "capemay_inlets",
    "capemay_ebb_12m",
    "narrows_cut",
)


def main(probe_dir, control, cache, ref, *names):
    cur = dict(np.load(cache))
    tree = cKDTree(np.c_[cur["x"], cur["y"]])
    czmin = cur["zmin"]
    cdx = 200.0 / 2 ** (cur["level"] - 1.0)
    act0 = int((cur["mask"] > 0).sum())
    g = gpd.read_file(ref).dissolve("name")
    ctrl = dict(np.load(control))
    rows = []
    for name in names:
        d = dict(np.load(Path(probe_dir) / name / "domain_dryrun.npz"))
        x, y, lev, m = d["x"], d["y"], d["level"], d["mask"]
        dx = 200.0 / 2 ** (lev - 1.0)
        act = m > 0
        print(
            f"\n== {name}: faces {len(x):,} ({len(x) - len(ctrl['x']):+,} vs control)  "
            f"active {int(act.sum()):,}"
        )
        for L in np.unique(lev):
            s = lev == L
            print(f"   {200 / 2 ** (L - 1):6.1f} m {int(s.sum()):>10,}")
        for b in BANDS:
            if b not in g.index:
                continue
            poly = g.geometry[b].buffer(300.0)
            from shapely import contains_xy

            n1 = int(contains_xy(poly, x, y).sum())
            n0 = int(contains_xy(poly, ctrl["x"], ctrl["y"]).sum())
            print(f"   band {b:22s} faces {n0:>9,} -> {n1:>9,}  ({n1 - n0:+,})")
        # time step: zmin of the current faces under each active probe face
        # candidates only: faces whose coarse z, 4 m deeper, would give dt < 1.0 s
        dt_c = ALPHA * dx / np.sqrt(G * np.clip(ZS - d["z"] + 4.0, 0.1, None))
        sel = np.flatnonzero(act & (dt_c < 1.0))
        print(f"   dt candidates {len(sel):,}")
        zmin = np.full(len(x), np.nan)
        for size in np.unique(dx[sel]):
            k = sel[dx[sel] == size]
            # current faces whose centres fall inside this face's square
            r = size * 0.71
            hits = tree.query_ball_point(np.c_[x[k], y[k]], r)
            for i, hit in zip(k, hits):
                h = [
                    j
                    for j in hit
                    if abs(cur["x"][j] - x[i]) <= size / 2
                    and abs(cur["y"][j] - y[i]) <= size / 2
                    and cdx[j] <= size
                ]
                if not h:
                    dist, j = tree.query([x[i], y[i]])
                    if dist > 150.0:  # outside today's mesh (the Hudson strip)
                        zmin[i] = d["z"][i] - 2.0  # coarse face z, 2 m deeper
                        continue
                    h = [j]
                zmin[i] = czmin[h].min()
        h = ZS - zmin
        dt = np.where(
            np.isfinite(h) & (h > 0.1),
            ALPHA * dx / np.sqrt(G * np.clip(h, 0.1, None)),
            np.inf,
        )
        o = np.argsort(dt)[:5]
        print(f"   min dt {dt[o[0]]:.3f} s; five smallest:")
        from pyproj import Transformer

        t = Transformer.from_crs(32618, 4326, always_xy=True)
        for i in o:
            lo, la = t.transform(x[i], y[i])
            print(
                f"     dt {dt[i]:.3f}  dx {dx[i]:5.1f}  zmin {zmin[i]:7.2f}  "
                f"({lo:.4f}, {la:.4f})"
            )
        rows.append((name, len(x), int(act.sum()), float(dt[o[0]])))
    dt0 = 0.684  # the current mesh, same estimator (mesh_now.txt)
    print("\n== runtime estimate (production engine, 72 h waves-on, 64 threads) ==")
    print(
        f"   reference: v4 / 1.1.0 mesh {F0:,} faces, active {act0:,}, dt {dt0} s, "
        f"{T0 / 3600:.2f} h"
    )
    for name, f, a, dtm in rows:
        r = FLOW * (a / act0) * (dt0 / dtm) + SW * (f / F0) + IO * (f / F0)
        print(
            f"   {name:16s} faces {f:>10,} ({(f / F0 - 1) * 100:+5.1f} %)  dt {dtm:.3f} s  "
            f"-> x{r:.3f}  ~{T0 * r / 3600:.2f} h"
        )


if __name__ == "__main__":
    main(*sys.argv[1:])
