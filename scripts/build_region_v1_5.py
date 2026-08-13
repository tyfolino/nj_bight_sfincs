#!/usr/bin/env python
"""Draw the v1_5_raritan region polygon. Named vertices, tagged ring segments.

    python scripts/build_region_v1_5.py            # write the geojson
    python scripts/build_region_v1_5.py --plot     # + a figure to reports/figures/
    python scripts/build_region_v1_5.py --check    # report only, write nothing

WHAT A "REGION" IS HERE, AND WHAT IT IS NOT
-------------------------------------------

🔴 **The region is NOT the boundary.** `build_static` runs

    create_active(zmin=mask_zmin)  →  region clip  →  land_boxes → 0
    →  _fill_inactive_holes  →  create_boundary  →  demote mask==2 outside every arm

so `create_active` has ALREADY trimmed the domain seaward at the ``mask_zmin`` isobath
before the region is applied. Measured on v1: its region box reaches lon −73.45, but its
`mask==2` stops at −73.91, because −10 m gets there first. The region therefore only has
to be *generous* offshore; it decides the LANDWARD and LATERAL extent, not the ocean arm.

That is why this polygon may run coarsely along Staten Island's shore: the ring is a
container, and `land_boxes` does the precise excluding. Prefer the box.

⚠️ **Every vertex here is a decision, so every vertex is named.** No auto-derived
geometry, no buffering, no contour following. If a number changes, it changes in this
file and nowhere else, and `nj_sfincs/domain.py` points at the output.

THE SHAPE
---------

v1.5 = v1's footprint (same southern limit, lat 40.150; same Atlantic side) with the
north end reopened so Lower Bay, Raritan Bay and Sandy Hook Bay become COMPUTED water
instead of a boundary running through them. v1's north edge at lat 40.5202 and its west
edge at lon −74.28 both ran *through* Raritan Bay; both are gone.

Three water cuts remain, and only these three may carry `mask==2`:
  * ``ocean``       — the Atlantic side, closing north on Rockaway Point
  * ``narrows``     — Verrazzano Narrows, ~1.6 km
  * ``arthur_kill`` — the Arthur Kill MOUTH at Perth Amboy / Ward Point, ~1.4 km

Everything else is land or an inland region limit. Staten Island and Jamaica Bay are
excluded; no NYC land is in the model.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "region_v1_5_raritan.geojson"
FIG = ROOT / "reports" / "figures"

# ═══════════════════════════════════════════════════════════════════════════════
# THE VERTICES. Counter-clockwise from the south-west corner of the southern limb.
# ═══════════════════════════════════════════════════════════════════════════════
# ⭐ A..D and N..P are carried VERBATIM from region_v1_monmouth.geojson so the two
# domains share an Atlantic side exactly. Do not "tidy" them — a moved vertex there
# makes v1 and v1.5 incomparable on the open coast for no gain.
V = {
    # ── the southern limb, inherited from v1 ────────────────────────────────────
    "A_sw_south_limb":  (-74.09596, 40.15037),   # v1 vertex, verbatim
    "B_se_corner":      (-73.45000, 40.15000),   # v1 vertex, verbatim
    # ── the Atlantic side, closed on the SANDY HOOK -> ROCKAWAY POINT line ─────
    # ⚠️ v1 turned west at lat 40.5202, cutting across Raritan Bay. v1.5 does NOT
    # simply carry on north: the domain is closed across the Lower Bay MOUTH, on the
    # Sandy Hook -> Rockaway Point line, as FINDINGS §2 describes. That wedge of open
    # Atlantic north-east of the line (the NY Bight apex / Ambrose approaches) is
    # OUTSIDE the domain; NACCS carries its surge in across the closure.
    #
    # ⭐ Why draw it rather than let the isobath decide: over most of Lower Bay the
    # water is shallower than `mask_zmin`, so `create_active` does NOT trim there and
    # the region edge IS the boundary. Left at a latitude line the closure wandered
    # through the bay mouth; drawn, it is the cross-section we intend to force.
    # ⭐ D is the EASTERNMOST point of the −10 m isobath in the Sandy Hook section,
    # measured off CUDEM (lon −73.9462 at lat 40.45; north of 40.47 the isobath swings
    # WEST into the bay mouth). Closing from the hook's tip instead let the isobath
    # keep running north-west past the closure, and `create_boundary` then traced it —
    # producing a tangle of imposed ocean level THROUGH Lower Bay, the exact defect
    # this domain exists to remove. Cut at the turn, not before it.
    "C_ne_corner":       (-73.45000, 40.45000),   # east edge stops at the turn's lat
    "D_isobath_east":    (-73.94620, 40.45000),   # ← the isobath's easternmost point
    "E_rockaway_point":  (-73.93640, 40.54970),   # ⭐ THE CLOSURE, 11.13 km
    # ── the Brooklyn shore of Lower Bay, up to the Narrows ─────────────────────
    "F_coney_island":    (-73.98000, 40.57500),
    "G_narrows_bkln":    (-74.03400, 40.60600),   # ← NARROWS cut, east end
    "H_narrows_si":      (-74.05550, 40.60100),   # ← NARROWS cut, west end
    # ── Staten Island's south shore (COARSE — land_boxes does the real excluding) ─
    "I_si_east":         (-74.08000, 40.57500),
    "J_great_kills":     (-74.13500, 40.53500),
    "K_si_southwest":    (-74.20000, 40.51000),
    "L_ward_point":      (-74.25000, 40.50100),   # ← ARTHUR KILL cut, east end
    "M_perth_amboy":     (-74.26600, 40.50600),   # ← ARTHUR KILL cut, west end
    # ── the NJ shore and the inland region limit ───────────────────────────────
    "N_raritan_west":    (-74.28000, 40.50000),
    "O_w_limit_south":   (-74.28000, 40.38000),   # v1 vertex, verbatim
    "P_notch_east":      (-74.09289, 40.38034),   # v1 vertex, verbatim
}

#: The ring, in order. The polygon closes A -> ... -> O -> A.
RING = list(V)

#: What each SEGMENT is, keyed by its starting vertex. Only `ocean`, `narrows` and
#: `arthur_kill` may ever carry a water-level BC; `land` is a real coastline the model
#: is closed against; `inland` is a region limit sitting on dry ground, where a
#: `mask==2` cell would mean something has gone badly wrong.
SEGMENT = {
    "A_sw_south_limb":  "ocean",       # the lat-40.150 southern limit
    "B_se_corner":      "ocean",       # the offshore east limit
    "C_ne_corner":      "ocean",       # west along SH's latitude, deep -> deactivated
    "D_isobath_east":  "ocean",       # ⭐ THE closure: isobath turn -> Rockaway Point
    "E_rockaway_point": "land",        # Brooklyn / Coney Island shore
    "F_coney_island":   "land",
    "G_narrows_bkln":   "narrows",     # ⭐ FORCED CUT
    "H_narrows_si":     "land",        # Staten Island south shore
    "I_si_east":        "land",
    "J_great_kills":    "land",
    "K_si_southwest":   "land",
    "L_ward_point":     "arthur_kill",  # ⭐ FORCED CUT
    "M_perth_amboy":    "land",        # NJ shore, Raritan Bay west end
    "N_raritan_west":   "inland",
    "O_w_limit_south":  "inland",
    "P_notch_east":     "inland",
}

#: Sanity bracket on the two cuts. A cut that comes out far from this is a typo, not a
#: design change — the Narrows is ~1.6 km wide and the Arthur Kill mouth ~1.4 km.
CUT_LENGTH_BRACKET_KM = {"narrows": (1.0, 3.0), "arthur_kill": (0.8, 3.0)}


def _km(p, q) -> float:
    return math.hypot((q[1] - p[1]) * 111.320,
                      (q[0] - p[0]) * 111.320 * math.cos(math.radians(p[1])))


def segments():
    """Yield (name, tag, p0, p1, km) for each ring segment, closing the loop."""
    for i, name in enumerate(RING):
        p0 = V[name]
        p1 = V[RING[(i + 1) % len(RING)]]
        yield name, SEGMENT[name], p0, p1, _km(p0, p1)


def check() -> list[str]:
    """Structural checks. Returns a list of problems; empty means the ring is sane."""
    bad = []
    if set(SEGMENT) != set(V):
        bad.append("SEGMENT and V disagree on the vertex set")

    tags = {t for _, t, *_ in segments()}
    for need in ("ocean", "narrows", "arthur_kill"):
        if need not in tags:
            bad.append(f"no {need!r} segment — the arm cannot exist")

    for name, tag, p0, p1, km in segments():
        if tag in CUT_LENGTH_BRACKET_KM:
            lo, hi = CUT_LENGTH_BRACKET_KM[tag]
            if not lo <= km <= hi:
                bad.append(f"{tag} cut at {name} is {km:.2f} km, outside [{lo}, {hi}]")

    # Self-intersection would make an invalid polygon that hydromt silently mangles.
    try:
        from shapely.geometry import Polygon

        poly = Polygon([V[n] for n in RING])
        if not poly.is_valid:
            bad.append(f"polygon is INVALID: {poly.buffer(0).area and 'self-intersects'}")
        if poly.exterior.is_ccw is False:
            print("[note] ring is clockwise; geojson does not care, but the tag order "
                  "was written counter-clockwise — check SEGMENT if you reorder")
    except ImportError:
        print("[note] shapely absent — skipped the validity check")
    return bad


def write() -> None:
    coords = [list(V[n]) for n in RING] + [list(V[RING[0]])]
    fc = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {
                "name": "v1_5_raritan",
                "note": "Generated by scripts/build_region_v1_5.py — edit the vertices "
                        "THERE, never this file. The region is a container: "
                        "create_active(zmin=mask_zmin) trims seaward before this is "
                        "applied, and land_boxes excludes Staten Island and Jamaica Bay.",
                "segments": {n: t for n, t in SEGMENT.items()},
            },
            "geometry": {"type": "Polygon", "coordinates": [coords]},
        }],
    }
    tmp = OUT.with_suffix(OUT.suffix + ".tmp")
    tmp.write_text(json.dumps(fc, indent=1))
    tmp.replace(OUT)
    print(f"[write] {OUT}")


def plot() -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    import rasterio
    from rasterio.windows import from_bounds

    bounds = (-74.36, 40.05, -73.40, 40.66)
    fig, ax = plt.subplots(figsize=(13, 9), dpi=160)
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#eef3f7")

    try:
        import cartopy.io.shapereader as shpreader
        from matplotlib.patches import Polygon as MplPolygon

        shp = shpreader.natural_earth(resolution="10m", category="physical", name="land")
        for geom in shpreader.Reader(shp).geometries():
            for p in (geom.geoms if geom.geom_type == "MultiPolygon" else [geom]):
                xs, ys = p.exterior.xy
                if max(xs) < bounds[0] or min(xs) > bounds[2]:
                    continue
                if max(ys) < bounds[1] or min(ys) > bounds[3]:
                    continue
                ax.add_patch(MplPolygon(list(zip(xs, ys)), closed=True,
                                        fc="#e6e3d8", ec="#a8a496", lw=0.5, zorder=0))
    except Exception as e:  # noqa: BLE001
        print(f"[plot] no Natural Earth land ({e})")

    vrt = ROOT / "data" / "elevation" / "cudem_nj.vrt"
    if vrt.exists():
        with rasterio.open(vrt) as s:
            win = from_bounds(*bounds, transform=s.transform)
            z = s.read(1, window=win, out_shape=(1200, 1800), masked=True).filled(np.nan)
        dlon = np.linspace(bounds[0], bounds[2], z.shape[1])
        dlat = np.linspace(bounds[3], bounds[1], z.shape[0])
        # ⚠️ CUDEM's OWN 0 m line, drawn because the Natural Earth land fill above is
        # a ~1:10M coastline and sits up to a km or two off the real shore. Without
        # this the −10 m isobath appears to run onto "land" that is really just the
        # coarse polygon in the wrong place. The two contours share a source here.
        ax.contour(dlon, dlat, z, levels=[0], colors=["#a8a496"], linewidths=0.6,
                   zorder=2)
        # ⭐ The mask_zmin isobath — where create_active actually stops. Drawn because
        # this, not the region ring, is what puts the ocean arm where it lands ON THE
        # OPEN COAST. In Lower Bay the water is shallower than mask_zmin, so there the
        # region ring itself is the boundary — hence the drawn closure.
        ax.contour(dlon, dlat, z, levels=[-10], colors=["#4a3aa7"], linewidths=0.7,
                   zorder=2)

    style = {"ocean": ("#2a78d6", 2.6), "narrows": ("#e34948", 4.0),
             "arthur_kill": ("#e34948", 4.0), "land": ("#0b0b0b", 1.6),
             "inland": ("#8a8980", 1.4)}
    seen = set()
    for name, tag, p0, p1, km in segments():
        c, lw = style[tag]
        ls = (0, (5, 3)) if tag == "inland" else "-"
        ax.plot([p0[0], p1[0]], [p0[1], p1[1]], color=c, lw=lw, ls=ls, zorder=4,
                solid_capstyle="round",
                label=tag if tag not in seen else None)
        seen.add(tag)
    for name, (lo, la) in V.items():
        ax.plot(lo, la, "o", ms=4, color="#0b0b0b", zorder=5)
        ax.annotate(name.split("_", 1)[1].replace("_", " "), (lo, la), fontsize=6.5,
                    textcoords="offset points", xytext=(4, 3), color="#52514e", zorder=5)

    ax.set_xlim(bounds[0], bounds[2]); ax.set_ylim(bounds[1], bounds[3])
    ax.set_aspect(1.0 / math.cos(math.radians(40.4)))
    ax.set_title("v1_5_raritan region — purple is the −10 m isobath, where "
                 "create_active actually stops",
                 fontsize=12, loc="left", color="#0b0b0b", pad=10)
    ax.set_xlabel("longitude", fontsize=9, color="#52514e")
    ax.set_ylabel("latitude", fontsize=9, color="#52514e")
    for s in ax.spines.values():
        s.set_color("#d5d4cc")
    ax.tick_params(colors="#52514e", labelsize=8)
    ax.legend(loc="lower left", frameon=True, facecolor="#fcfcfb", edgecolor="#d5d4cc",
              fontsize=8.5)
    FIG.mkdir(parents=True, exist_ok=True)
    p = FIG / "region_v1_5_raritan.png"
    fig.savefig(p, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"[plot] {p}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plot", action="store_true")
    ap.add_argument("--check", action="store_true", help="report only, write nothing")
    args = ap.parse_args()

    print(f"{'segment':22s} {'tag':12s} {'km':>7}")
    total = {}
    for name, tag, p0, p1, km in segments():
        print(f"{name:22s} {tag:12s} {km:7.2f}")
        total[tag] = total.get(tag, 0.0) + km
    print("\nby tag: " + "  ".join(f"{t}={v:.1f} km" for t, v in sorted(total.items())))

    bad = check()
    if bad:
        print("\n🔴 PROBLEMS:")
        for b in bad:
            print(f"   - {b}")
        raise SystemExit(1)
    print("\n✅ ring is structurally sane")

    if not args.check:
        write()
    if args.plot:
        plot()


if __name__ == "__main__":
    main()
