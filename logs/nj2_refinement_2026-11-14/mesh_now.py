"""What the CURRENT mesh (v4 frozen, as v4_refreeze_swz_v11) has where nj2 wants to change it.

    python logs/nj2_refinement_2026-11-14/mesh_now.py [cache.npz]

1. Cell size over each Cape May - Great Egg inlet's throat (the 11-09 inlet line) and ebb shoal
   (the `EBB` boxes of build_refinement_nj2.py), by depth band.
2. The flow time step: per ACTIVE face, dt = alpha * dx / sqrt(g * h), h = zs - z_zmin (the
   face's lowest subgrid pixel; SFINCS uses the uv point's depth, which is >= this, so this is
   a LOWER bound on the face's dt) at zs = +1 m and +3 m, alpha 0.5 (sfincs.inp). Lists the
   places that hold the global minimum (SFINCS takes ONE dt for the whole mesh,
   sfincs_momentum.f90 L727) - i.e. what coarsening the Narrows could buy.
Read-only. Light (~1 GB); ran in the VS Code allocation.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from netCDF4 import Dataset
from pyproj import Transformer

R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R / "scripts"))
from build_refinement_nj2 import EBB, INLETS  # noqa: E402

TPL = R / "experiments/v4_refreeze_swz_v11/_template_sealed"
G, ALPHA = 9.81, 0.5


def load(cache: Path):
    if cache.exists():
        return dict(np.load(cache))
    with Dataset(TPL / "sfincs.nc") as nc:
        d = {
            k: nc[v][:].filled(np.nan) if hasattr(nc[v][:], "filled") else nc[v][:]
            for k, v in (
                ("x", "mesh2d_face_x"),
                ("y", "mesh2d_face_y"),
                ("level", "level"),
                ("mask", "mask"),
                ("z", "z"),
            )
        }
    with Dataset(TPL / "sfincs_subgrid.nc") as nc:
        d["zmin"] = np.asarray(nc["z_zmin"][:])
    d = {k: np.asarray(v) for k, v in d.items()}
    np.savez(cache, **d)
    return d


def main(cache: str) -> int:
    d = load(Path(cache))
    x, y, lev, m, zmin = d["x"], d["y"], d["level"], d["mask"], d["zmin"]
    dx = 200.0 / 2 ** (lev - 1)
    act = m > 0
    print(f"faces {len(x):,}  active {int(act.sum()):,}")

    print("\n== Cape May - Great Egg inlets: current cell size (active faces) ==")
    to_utm = Transformer.from_crs(4326, 32618, always_xy=True)
    for name, (a, b) in INLETS.items():
        # throat: faces within 60 m of the 11-09 line
        ax, ay = a
        bx, by = b
        px, py = x - ax, y - ay
        vx, vy = bx - ax, by - ay
        t = np.clip((px * vx + py * vy) / (vx * vx + vy * vy), 0, 1)
        dist = np.hypot(px - t * vx, py - t * vy)
        sel = act & (dist < 60)
        ebb = EBB[name]
        ex, ey = to_utm.transform([p[0] for p in ebb[0]], [p[1] for p in ebb[0]])
        from matplotlib.path import Path as MP

        inside = MP(np.c_[ex, ey]).contains_points(np.c_[x, y]) & act
        for lab, s in (("throat", sel), ("ebb box", inside)):
            out = []
            for lo, hi in ((-99, -8), (-8, -2), (-2, 1), (1, 99)):
                k = s & (zmin >= lo) & (zmin < hi)
                if k.any():
                    sizes, cnt = np.unique(dx[k], return_counts=True)
                    out.append(
                        f"z[{lo},{hi}) "
                        + "/".join(f"{c}x{sz:g}m" for sz, c in zip(sizes, cnt))
                    )
            print(f"  {name:15s} {lab:8s} n={int(s.sum()):6,}  " + "  ".join(out))

    print("\n== global flow time step: who holds the minimum (active faces) ==")
    to_ll = Transformer.from_crs(32618, 4326, always_xy=True)
    for zs in (1.0, 3.0):
        h = np.where(act, zs - zmin, np.nan)
        dt = ALPHA * dx / np.sqrt(G * np.clip(h, 1e-3, None))
        dt[~act | (h <= 0.1)] = np.inf
        order = np.argsort(dt)[:4000]
        print(
            f"\n zs = {zs:+.0f} m: min dt {dt[order[0]]:.3f} s; "
            f"p0.01 {np.percentile(dt[np.isfinite(dt)], 0.01):.3f} s"
        )
        # cluster the 4000 smallest by 2 km cells
        key = (x[order] // 2000).astype(int) * 100000 + (y[order] // 2000).astype(int)
        seen = {}
        for i, k in zip(order, key):
            if k not in seen:
                seen[k] = i
            if len(seen) >= 12:
                break
        for k, i in seen.items():
            lo, la = to_ll.transform(x[i], y[i])
            n_lt = int((dt[order][key == k] < 1e9).sum())
            print(
                f"   dt {dt[i]:.3f} s  dx {dx[i]:5.1f} m  zmin {zmin[i]:7.2f}  "
                f"({lo:.4f}, {la:.4f})  [{n_lt} of the 4000 in this 2 km cell]"
            )
        # by cell size: the smallest dt among each resolution
        for sz in (25.0, 50.0, 100.0):
            k = np.isfinite(dt) & (dx == sz)
            i = np.flatnonzero(k)[np.argmin(dt[k])]
            lo, la = to_ll.transform(x[i], y[i])
            print(
                f"   smallest at {sz:4.0f} m: dt {dt[i]:.3f} s, zmin {zmin[i]:.1f} "
                f"at ({lo:.4f}, {la:.4f})"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "mesh_now_cache.npz"))
