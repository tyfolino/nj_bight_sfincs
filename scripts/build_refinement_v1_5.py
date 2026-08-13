#!/usr/bin/env python
"""Write the v1_5_raritan quadtree refinement recipe.

    python scripts/build_refinement_v1_5.py            # write the geojson
    python scripts/build_refinement_v1_5.py --plot     # + a figure

🔴 A REFINEMENT RECIPE IS NOT PORTABLE. `build_static` refuses to reuse one from
another domain, and for a specific reason: a gate is a *box plus a depth band*, and a
depth band written for one basin will happily refine a different basin's open water to
its finest level. v1's recipe would put 25 m cells across the whole of Raritan Bay,
which v1 never contained. Hence a new file.

LEVELS. `BaseConfig.base_res` is 200 m, and level N is 200 / 2**N:

    L0 = 200 m   L1 = 100 m   L2 = 50 m   L3 = 25 m

WHAT DRIVES THE SIZING. SnapWave is 90-95% of runtime and scales per-iteration with
cell count, so faces ratio ~= runtime ratio against the v1 yardstick of 547,408 faces
at ~3 h. Every gate below is therefore justified by what it BUYS, not by "finer is
better": the two forced cuts must carry flux, the estuaries must convey, and the open
shelf must not be paid for twice.

⚠️ Gates are boxes with DEPTH BANDS, and the band is what keeps a box from over-reaching.
`bay_fringe` spans the whole bay but is gated to -1..+2 m, so it only catches the
shoreline. Widen a band without re-running `probe_mesh_size.py` and you can multiply the
mesh without noticing.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "quadtree" / "refinement_v1_5_raritan.geojson"
FIG = ROOT / "reports" / "figures"
EPSG = 32618

# ═══════════════════════════════════════════════════════════════════════════════
# THE GATES. (name, level, lon/lat box, zmin, zmax, why)
# ═══════════════════════════════════════════════════════════════════════════════
# Boxes are lon/lat and fully bounded — coordinate boxes over auto-derived polygons.
# Order does not matter: hydromt takes the FINEST level that applies to a cell.
GATES = [
    # ── L1, 100 m ──────────────────────────────────────────────────────────────
    ("shelf_shoaling", 1, (-74.10, -73.45, 40.10, 40.56), -30.0, -8.0,
     "100 m across the shoaling band. Deeper than -30 m is outside create_active "
     "anyway; shallower than -8 m is picked up by the surf gate at 25 m."),
    ("inland_floodplain", 1, (-74.30, -73.95, 40.10, 40.52), 0.0, 9.0,
     "100 m on inland ground so land steps 50 -> 100 -> 200 m rather than jumping two "
     "levels at once, which makes a visible stair in the flood edge."),
    # ── L2, 50 m ───────────────────────────────────────────────────────────────
    ("bay_water", 2, (-74.30, -73.93, 40.40, 40.62), -20.0, 3.0,
     "50 m over Raritan / Lower / Sandy Hook Bay — the water this domain exists to "
     "COMPUTE. The working resolution for the interior."),
    ("coastal_corridor", 2, (-74.10, -73.93, 40.10, 40.50), -20.0, 5.0,
     "50 m along the Monmouth coastal strip, matching v1's working resolution so the "
     "open coast stays comparable between the two domains."),
    # ── L3, 25 m ───────────────────────────────────────────────────────────────
    ("narrows_cut", 3, (-74.075, -74.020, 40.585, 40.625), -40.0, 2.0,
     "25 m across the Verrazzano Narrows: ~1.9 km / 25 m = ~76 cells carrying the "
     "Upper Bay + Hudson tidal prism. This cut IS the measurement (crs flux), so it "
     "is the one place resolution is not negotiable."),
    ("arthur_kill_cut", 3, (-74.285, -74.235, 40.490, 40.520), -40.0, 2.0,
     "25 m across the Arthur Kill mouth: ~1.46 km / 25 m = ~58 cells."),
    ("surf_dune", 3, (-74.05, -73.93, 40.10, 40.50), -8.0, 3.0,
     "25 m in the surf zone, foredune and barrier. Gated -8..+3 m so it cannot reach "
     "back into the bay, which shares part of that depth band."),
    ("shrewsbury_navesink", 3, (-74.08, -73.96, 40.33, 40.42), -8.0, 3.0,
     "25 m through the behind-barrier estuaries — the conveyance test, and the basin "
     "where a throttled inlet has twice been mistaken for a boundary problem."),
    ("bay_fringe", 3, (-74.30, -73.93, 40.40, 40.62), -1.0, 2.0,
     "25 m on the bay MARGIN only. The band is the whole point: the bay interior is "
     "deeper than -1 m so it stays at 50 m, and only shoreline, marsh and mudflat — "
     "where wetting is threshold-nonlinear — are refined."),
]


def to_utm(lon, lat):
    import pyproj

    return pyproj.Transformer.from_crs(4326, EPSG, always_xy=True).transform(lon, lat)


def build():
    import geopandas as gpd
    from shapely.geometry import Polygon

    rows, geoms = [], []
    for name, lvl, (lo0, lo1, la0, la1), zmin, zmax, why in GATES:
        xs, ys = to_utm([lo0, lo1, lo1, lo0], [la0, la0, la1, la1])
        geoms.append(Polygon(zip(xs, ys)))
        rows.append(dict(name=name, refinement_level=lvl, zmin=zmin, zmax=zmax, why=why))
    return gpd.GeoDataFrame(rows, geometry=geoms, crs=EPSG)


def area_report(g) -> None:
    """Crude upper bound on what each gate could cost, if its box were fully wet."""
    print(f"{'gate':22s} {'lvl':>3} {'res':>5} {'box km2':>9} "
          f"{'cells if ALL in band':>21}")
    for _, r in g.iterrows():
        res = 200 / 2 ** int(r.refinement_level)
        km2 = r.geometry.area / 1e6
        print(f"{r['name']:22s} {int(r.refinement_level):3d} {res:5.0f} {km2:9.1f} "
              f"{km2 * 1e6 / res ** 2:21,.0f}")
    print("\n⚠️ The right-hand column is an UPPER BOUND only — it assumes every cell in "
          "the box\n   falls inside the depth band, which is exactly what the bands "
          "prevent. The real\n   number comes from scripts/probe_mesh_size.py.")


def plot(g) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(11, 9), dpi=160)
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    colors = {1: "#2a78d6", 2: "#eb6834", 3: "#1baf7a"}
    for lvl in (1, 2, 3):
        sub = g[g.refinement_level == lvl]
        sub.boundary.plot(ax=ax, color=colors[lvl], lw=2.0,
                          label=f"L{lvl} = {200 / 2 ** lvl:.0f} m  (n={len(sub)})")
    for _, r in g.iterrows():
        c = r.geometry.centroid
        ax.annotate(f"{r['name']}\n{r.zmin:+.0f}..{r.zmax:+.0f} m", (c.x, c.y),
                    fontsize=7, ha="center", color="#52514e")
    ax.set_title("v1_5_raritan refinement gates — each is a BOX plus a DEPTH BAND",
                 fontsize=12, loc="left", color="#0b0b0b", pad=10)
    ax.set_xlabel("easting (m, EPSG 32618)", fontsize=9, color="#52514e")
    ax.set_ylabel("northing (m)", fontsize=9, color="#52514e")
    ax.legend(loc="lower left", frameon=True, facecolor="#fcfcfb", edgecolor="#d5d4cc",
              fontsize=8.5)
    ax.set_aspect("equal")
    for s in ax.spines.values():
        s.set_color("#d5d4cc")
    ax.tick_params(colors="#52514e", labelsize=8)
    FIG.mkdir(parents=True, exist_ok=True)
    p = FIG / "refinement_v1_5_raritan.png"
    fig.savefig(p, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"[plot] {p}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plot", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    g = build()
    area_report(g)
    if not args.check:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        tmp = OUT.with_suffix(OUT.suffix + ".tmp")
        g.to_file(tmp, driver="GeoJSON")
        tmp.replace(OUT)
        print(f"\n[write] {OUT}")
    if args.plot:
        plot(g)


if __name__ == "__main__":
    main()
