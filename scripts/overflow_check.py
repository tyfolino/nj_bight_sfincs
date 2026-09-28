#!/usr/bin/env python
"""Where does a run's peak water reach the EDGE of the model? (v4 design gate, 2026-09-28)

    NJ_DOMAIN=v4 PYTHONPATH=$PWD python scripts/overflow_check.py experiments/v4/<arm> [...]
        [--hmin 0.10] [--map]

Read-only on the run. Writes ``<run>/overflow_check.csv`` (one row per edge cell) and,
with ``--map``, ``<run>/overflow_check.png``.

WHAT IT ANSWERS. The v4 ring was drawn to CONTAIN the NACCS Sandy peak + 3 m (STATUS
09-25): every stretch of edge is either a forced line, a declared wall (a river cut, a
land line), or ground the water should never reach. This reads the solver's own answer:
for every active cell on the edge of the model (a missing or inactive neighbour on any
side), its category and its peak depth ``zsmax - z_zmin`` (subgrid lowest point), then

* ``forced``   mask 2 — wet by construction; listed for completeness.
* ``outflow``  mask 3 — free outflow: water that reaches it LEAVES the model. Wet here
               means the ring is too small at that spot (or the edge is undeclared water).
               SFINCS writes no zsmax there: it takes its deepest active neighbour's depth.
* ``wall:<n>`` mask 1 inside a declared ``MaskOverride`` box — the river cuts and land
               lines. A river cut is wet by design; a land wall that is wet is a
               reflecting wall standing in water, the thing the far-bank rule avoids.
* ``closed``   any other mask 1 edge cell (demoted wet cells, walls round the inflows,
               the flat ends of the forced line).

and, for every DRY outflow / closed edge cell, the distance to the nearest wet cell — the
ring's margin, against the design rule "the edge sits >= 500 m from the target".

⚠️ Read a RAIN-OFF run for the gate: with rain on, ponding at an upland edge reads as
"water reached the edge". The v4 gate arms are rain-off for that reason.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

import nj_sfincs  # noqa: F401 — pyproj before hydromt
from nj_sfincs import domain as _domain

NEIGH = ("mu1", "mu2", "md1", "md2", "nu1", "nu2", "nd1", "nd2")
SIDES = ("mu1", "md1", "nu1", "nd1")  # a side with no neighbour at all


def edge_cells(mask: np.ndarray, nb: dict[str, np.ndarray]) -> np.ndarray:
    """Active cells with a missing neighbour on some side, or an inactive neighbour."""
    act = mask > 0
    edge = np.zeros(mask.shape, bool)
    for k in SIDES:
        edge |= nb[k] < 0
    for k in NEIGH:
        j = nb[k]
        has = j >= 0
        edge[has] |= ~act[j[has]]
    return act & edge


def neighbour_depth_on_outflow(h, zs, mask, nb):
    """``h``/``zs`` with each mask-3 cell taking its deepest non-outflow neighbour's."""
    h, zs = h.copy(), zs.copy()
    o = np.flatnonzero(mask == 3)
    best_h = np.full(o.shape, np.nan)
    best_z = np.full(o.shape, np.nan)
    for k in NEIGH:
        j = nb[k][o]
        jj = np.maximum(j, 0)
        ok = (j >= 0) & np.isin(mask[jj], (1, 2)) & np.isfinite(h[jj])
        better = ok & ~(h[jj] <= best_h)  # NaN-safe: first valid, then deeper
        best_h = np.where(better, h[jj], best_h)
        best_z = np.where(better, zs[jj], best_z)
    h[o], zs[o] = best_h, best_z
    return h, zs


def classify(mask, fx, fy, edge, overrides) -> np.ndarray:
    """Category string per cell ('' off the edge). First match wins, in this order."""
    cat = np.full(mask.shape, "", dtype=object)
    cat[edge & (mask == 2)] = "forced"
    cat[edge & (mask == 3)] = "outflow"
    for ov in overrides:
        if ov.to != 1:
            continue
        x0, y0, x1, y1 = ov.box
        inb = edge & (mask == 1) & (cat == "") & (fx > x0) & (fx < x1)
        inb &= (fy > y0) & (fy < y1)
        cat[inb] = f"wall:{ov.name.removeprefix('wall_')}"
    cat[edge & (mask == 1) & (cat == "")] = "closed"
    return cat


def run_one(run: Path, hmin: float, make_map: bool) -> None:
    import pandas as pd
    import xarray as xr
    from pyproj import Transformer
    from scipy.spatial import cKDTree

    dom = _domain.active()
    with xr.open_dataset(run / "sfincs.nc") as g:
        mask = g["mask"].values.astype(int)
        fx, fy = g["mesh2d_face_x"].values, g["mesh2d_face_y"].values
        nb = {k: g[k].values.astype(np.int64) - 1 for k in NEIGH}
    with xr.open_dataset(run / "sfincs_subgrid.nc") as s:
        zmin = s["z_zmin"].values
    with xr.open_dataset(run / "sfincs_map.nc") as m:
        zs = m["zsmax"].max("timemax").values  # fill decodes to NaN
    # 🔴 SFINCS writes NO zsmax on outflow (mask 3) cells — all fill (v3 naccs-nowaves:
    # 1,332 of 1,332). Without this the one category that means "water LEFT the model"
    # reads dry by construction. Proxy: the deepest peak DEPTH among the cell's active
    # neighbours (the water arriving at the exit). A depth, not a level: on an upland
    # slope a neighbour's level minus this cell's bed reads metres of phantom water.
    h = zs - zmin
    h, zs = neighbour_depth_on_outflow(h, zs, mask, nb)
    wet = (mask > 0) & np.isfinite(h) & (h > hmin)

    edge = edge_cells(mask, nb)
    cat = classify(mask, fx, fy, edge, dom.mask_overrides)
    lon, lat = Transformer.from_crs(dom.epsg, 4326, always_xy=True).transform(fx, fy)

    # margin: dry outflow/closed edge cell -> nearest wet cell
    dry_rim = edge & ~wet & np.isin(cat, ["outflow", "closed"])
    dist = np.full(mask.shape, np.nan)
    if wet.any() and dry_rim.any():
        d, _ = cKDTree(np.c_[fx[wet], fy[wet]]).query(np.c_[fx[dry_rim], fy[dry_rim]])
        dist[dry_rim] = d

    idx = np.flatnonzero(edge)
    df = pd.DataFrame(
        {
            "category": cat[idx].astype(str),
            "lon": lon[idx],
            "lat": lat[idx],
            "z_zmin": zmin[idx],
            "zsmax": zs[idx],
            "hmax": np.where(wet[idx], h[idx], 0.0),
            "wet": wet[idx],
            "dist_to_wet_m": dist[idx],
        }
    )
    out = run / "overflow_check.csv"
    df.to_csv(out, index=False, float_format="%.4f")

    print(f"\n=== {run}  (hmin {hmin} m; {wet.sum():,} wet cells) ===")
    t = df.groupby("category").agg(
        edge_cells=("wet", "size"),
        wet=("wet", "sum"),
        hmax_max=("hmax", "max"),
    )
    print(t.to_string(float_format=lambda v: f"{v:.2f}"))
    for c in ("outflow", "closed"):
        w = df[(df.category == c) & df.wet].sort_values("hmax", ascending=False)
        if len(w):
            print(f"\n  {c}: {len(w)} WET edge cells — deepest:")
            for _, r in w.head(10).iterrows():
                print(
                    f"    ({r.lon:.4f}, {r.lat:.4f})  h {r.hmax:.2f} m  zb {r.z_zmin:.2f}"
                )
    rim = df[df.dist_to_wet_m.notna()]
    if len(rim):
        n500 = int((rim.dist_to_wet_m < 500).sum())
        print(
            f"\n  margin (dry outflow/closed edge -> nearest wet cell): min "
            f"{rim.dist_to_wet_m.min():.0f} m; {n500:,} of {len(rim):,} within 500 m"
        )
        for _, r in rim.nsmallest(10, "dist_to_wet_m").iterrows():
            print(
                f"    ({r.lon:.4f}, {r.lat:.4f})  {r.category:8s} "
                f"{r.dist_to_wet_m:6.0f} m  zb {r.z_zmin:.2f}"
            )
    print(f"\n  wrote {out}")

    if make_map:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(9, 11))
        ax.scatter(lon[wet], lat[wet], s=0.05, c="#9ecae1", lw=0, rasterized=True)
        dry = df[~df.wet]
        ax.scatter(dry.lon, dry.lat, s=0.3, c="#bdbdbd", lw=0, label="edge, dry")
        colors = {"forced": "#3182bd", "outflow": "#de2d26", "closed": "#756bb1"}
        for c, grp in df[df.wet].groupby("category"):
            ax.scatter(
                grp.lon,
                grp.lat,
                s=2,
                lw=0,
                c=colors.get(c, "#e6550d"),
                label=f"wet {c.split(':')[0]}",
            )
        ax.set_aspect(1 / np.cos(np.deg2rad(np.nanmean(lat[mask > 0]))))
        ax.legend(markerscale=6, fontsize=8, loc="lower right")
        ax.set_title(f"{run.name}: peak water at the model edge (h > {hmin} m)")
        fig.tight_layout()
        fig.savefig(run / "overflow_check.png", dpi=200)
        print(f"  wrote {run / 'overflow_check.png'}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("runs", nargs="+", type=Path)
    ap.add_argument("--hmin", type=float, default=0.10, help="wet threshold [m]")
    ap.add_argument("--map", action="store_true")
    a = ap.parse_args()
    for r in a.runs:
        run_one(r, a.hmin, a.map)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
