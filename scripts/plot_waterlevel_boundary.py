#!/usr/bin/env python
"""Map the water-level boundary the build actually produced, coloured by declared arm.

    NJ_DOMAIN=v1_5_raritan PYTHONPATH=$PWD python scripts/plot_waterlevel_boundary.py \
        [probe_dir]                       # default data/probe_mesh_v1_5

WHY THIS EXISTS. `_report_waterlevel_boundary` prints the BC set as a table every build,
because the one thing every historical boundary defect shared was that nobody looked at
the set AS A WHOLE. A table is not a picture, though, and two of those defects — an
ocean level imposed 2.6 km inside an inlet, and a free-outflow face across a tidal river
— were obvious the moment anyone plotted them.

⚠️ This reads the DRY-RUN npz that `probe_mesh_size.py` writes (`skip_subgrid=True`
stops before `sfincs.nc` exists), so it maps the mask as built, not as run.

⚠️ The alongshore `dW` heuristic in the text report assumes ONE alongshore boundary and
reads as a false intrusion on a multi-arm domain — a band containing both the Arthur
Kill arm and the ocean arm shows a ~18 km west-edge "jump" that is simply two different
arms in one latitude band. This map is the check that disambiguates it.
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIG = ROOT / "reports" / "figures"

#: dataviz categorical slots 1-3 — certified all-pairs (scatter) in both modes.
ARM_COLOR = {"ocean": "#2a78d6", "narrows": "#eb6834", "arthur_kill": "#1baf7a"}
#: Reserved status colour, never a categorical slot: an unclaimed BC cell is a DEFECT.
UNCLAIMED = "#e34948"


def main(probe: str = "data/probe_mesh_v1_5") -> int:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pyproj

    from nj_sfincs import domain as _domain

    dom = _domain.active()
    npz = (ROOT / probe) / "domain_dryrun.npz"
    if not npz.exists():
        raise SystemExit(f"no dry run at {npz} — run scripts/probe_mesh_size.py first")

    d = np.load(npz)
    x, y, zb, m = d["x"], d["y"], d["z"], d["mask"]
    lon, lat = pyproj.Transformer.from_crs(dom.epsg, 4326, always_xy=True).transform(x, y)

    bc = m == 2
    print(f"{int(bc.sum()):,} water-level BC cells, {int((m == 3).sum()):,} outflow, "
          f"{int((m > 0).sum()):,} active of {len(m):,} faces")

    # Classify by DECLARED arm. A cell in no arm is a defect, not a category.
    claimed = np.zeros(len(m), dtype=bool)
    groups = {}
    for arm in dom.boundary_arms:
        if arm.btype != "waterlevel":
            continue
        x0, y0, x1, y1 = arm.box
        sel = bc & (x > x0) & (x < x1) & (y > y0) & (y < y1)
        groups[arm.name] = sel
        claimed |= sel
        print(f"  {arm.name:14s} {int(sel.sum()):>6,} cells  "
              f"bed {zb[sel].min():+.2f}..{zb[sel].max():+.2f} m  "
              f"[{arm.min_cells}..{arm.max_cells}]")
    orphan = bc & ~claimed
    if orphan.any():
        print(f"  🔴 UNCLAIMED     {int(orphan.sum()):>6,} cells — a mask==2 cell "
              f"outside every declared arm is a BUG")

    fig, ax = plt.subplots(figsize=(12, 10), dpi=160)
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#eef3f7")

    # Active interior, recessive: the boundary must read against the domain it bounds.
    act = (m > 0) & ~bc & (m != 3)
    ax.scatter(lon[act], lat[act], s=0.05, c="#dfe7ee", linewidths=0, zorder=1)
    dry = act & (zb > 0)
    ax.scatter(lon[dry], lat[dry], s=0.05, c="#e6e3d8", linewidths=0, zorder=1)

    if (m == 3).any():
        ax.scatter(lon[m == 3], lat[m == 3], s=6, c="#4a3aa7", linewidths=0, zorder=3,
                   label=f"outflow (mask 3)  n={int((m == 3).sum()):,}")
    for name, sel in groups.items():
        if not sel.any():
            continue
        ax.scatter(lon[sel], lat[sel], s=7, c=ARM_COLOR.get(name, "#8a8980"),
                   linewidths=0, zorder=4,
                   label=f"{name}  n={int(sel.sum()):,}")
    if orphan.any():
        ax.scatter(lon[orphan], lat[orphan], s=26, c=UNCLAIMED, marker="x",
                   linewidths=1.4, zorder=5,
                   label=f"🔴 UNCLAIMED  n={int(orphan.sum()):,}")

    for g in dom.obs_gauges:
        ax.plot(g.lon, g.lat, marker="*", ms=12, color="#0b0b0b", zorder=6)
        ax.annotate(g.name, (g.lon, g.lat), fontsize=7.5, color="#0b0b0b", zorder=6,
                    textcoords="offset points", xytext=(7, 4))

    ax.set_xlabel("longitude", fontsize=9, color="#52514e")
    ax.set_ylabel("latitude", fontsize=9, color="#52514e")
    ax.set_title(f"{dom.name} — the water-level boundary AS BUILT, by declared arm",
                 fontsize=13, loc="left", color="#0b0b0b", pad=10)
    ax.set_aspect(1.0 / math.cos(math.radians(40.4)))
    for s in ax.spines.values():
        s.set_color("#d5d4cc")
    ax.tick_params(colors="#52514e", labelsize=8)
    leg = ax.legend(loc="lower left", frameon=True, facecolor="#fcfcfb",
                    edgecolor="#d5d4cc", fontsize=8.5, markerscale=2.2)
    leg.set_zorder(7)

    FIG.mkdir(parents=True, exist_ok=True)
    p = FIG / f"waterlevel_boundary_{dom.name}.png"
    fig.savefig(p, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"[plot] {p}")

    # A zoom on each short cut — 229 and 177 cells are invisible at domain scale.
    cuts = [a for a in dom.boundary_arms if a.name in ("narrows", "arthur_kill")]
    if cuts:
        fig2, axes = plt.subplots(1, len(cuts), figsize=(6.5 * len(cuts), 6), dpi=160)
        fig2.patch.set_facecolor("#fcfcfb")
        for axz, arm in zip(np.atleast_1d(axes), cuts):
            x0, y0, x1, y1 = arm.box
            pad = 2500
            w = (x > x0 - pad) & (x < x1 + pad) & (y > y0 - pad) & (y < y1 + pad)
            axz.set_facecolor("#eef3f7")
            axz.scatter(lon[w & act], lat[w & act], s=2.5, c="#dfe7ee", linewidths=0)
            axz.scatter(lon[w & act & (zb > 0)], lat[w & act & (zb > 0)], s=2.5,
                        c="#e6e3d8", linewidths=0)
            sel = groups.get(arm.name, np.zeros(len(m), bool))
            axz.scatter(lon[sel], lat[sel], s=22, c=ARM_COLOR[arm.name], linewidths=0)
            axz.set_title(f"{arm.name} — {int(sel.sum()):,} cells", fontsize=10,
                          loc="left", color="#0b0b0b")
            axz.set_aspect(1.0 / math.cos(math.radians(40.5)))
            axz.tick_params(colors="#52514e", labelsize=7)
            for s in axz.spines.values():
                s.set_color("#d5d4cc")
        p2 = FIG / f"waterlevel_boundary_{dom.name}_cuts.png"
        fig2.tight_layout()
        fig2.savefig(p2, bbox_inches="tight", facecolor=fig2.get_facecolor())
        print(f"[plot] {p2}")
    return 0


if __name__ == "__main__":
    os.environ.setdefault("NJ_DOMAIN", "v1_5_raritan")
    raise SystemExit(main(*[a for a in sys.argv[1:] if not a.startswith("--")]))
