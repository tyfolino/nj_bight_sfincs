#!/usr/bin/env python
"""Compare a clipped DEM against reference DEMs at random LAND points. Read-only.

    python scripts/check_dem_clip.py CLIP.tif --ref REF.tif [--ref ...] [--n 40000]

Why: the 09-24 v4 re-clip of the NJ 10-ft DEM was georeferenced ~14 km west and nothing
noticed until a ring audit read nonsense heights (STATUS 09-25). This is the check that
catches that class of error in seconds: at N random points inside the clip where both
rasters are valid land (> ``--land-min`` m), the per-reference distribution of
clip − ref. A correct clip of the same lidar reads ~0 against the previous clip and
within ~0.5 m of 3DEP; a shifted one reads metres off on most points.

Each ``--ref`` may be repeated; several files passed under one ``--ref-group NAME`` are
sampled first-valid-wins (e.g. a set of 3DEP tiles). Prints, never gates.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import transform as warp_xy


def sample(paths: list[Path], lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    z = np.full(lon.shape, np.nan)
    for p in paths:
        need = np.isnan(z)
        if not need.any():
            break
        with rasterio.open(p) as s:
            x, y = warp_xy("EPSG:4326", s.crs, lon[need].tolist(), lat[need].tolist())
            v = np.array([r[0] for r in s.sample(zip(x, y))], dtype="float64")
            if s.nodata is not None:
                v[v == s.nodata] = np.nan
            v[np.abs(v) > 1e4] = np.nan
            z[need] = v
    return z


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("clip", type=Path)
    ap.add_argument(
        "--ref", type=Path, action="append", default=[], help="one reference"
    )
    ap.add_argument(
        "--ref-group",
        nargs="+",
        action="append",
        default=[],
        metavar=("NAME", "FILE"),
        help="NAME then files, sampled first-valid-wins",
    )
    ap.add_argument("--n", type=int, default=40_000)
    ap.add_argument("--land-min", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    with rasterio.open(a.clip) as c:
        w, s, e, n = rasterio.warp.transform_bounds(c.crs, "EPSG:4326", *c.bounds)
    rng = np.random.default_rng(a.seed)
    lon = rng.uniform(w, e, a.n)
    lat = rng.uniform(s, n, a.n)
    zc = sample([a.clip], lon, lat)
    land = zc > a.land_min
    print(
        f"{a.clip.name}: lon {w:.3f}..{e:.3f} lat {s:.3f}..{n:.3f}; "
        f"{int(land.sum())} of {a.n} random points are land (> {a.land_min} m)"
    )
    groups = [(p.name, [p]) for p in a.ref] + [
        (g[0], [Path(f) for f in g[1:]]) for g in a.ref_group
    ]
    for name, paths in groups:
        zr = sample(paths, lon[land], lat[land])
        ok = zr > a.land_min
        d = zc[land][ok] - zr[ok]
        if d.size == 0:
            print(f"  vs {name}: no overlapping land")
            continue
        q = np.percentile(d, [5, 50, 95])
        print(
            f"  vs {name}: n {d.size}  median {q[1]:+.3f} m  p5 {q[0]:+.2f}  p95 {q[2]:+.2f}  "
            f"|Δ|>1 m {np.mean(np.abs(d) > 1):.1%}  |Δ|>5 m {np.mean(np.abs(d) > 5):.1%}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
