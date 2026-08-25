#!/usr/bin/env python
"""Validate the HAND-EDITED v3 region polygon. Writes nothing, ever.

    python scripts/validate_region_v3.py            # the gate
    python scripts/validate_region_v3.py --verbose  # per-reach sample dumps
    python scripts/validate_region_v3.py --plot     # + a figure

🔴 **THE DRAWN FILE IS THE AUTHORITY.** `data/region_v3_EDITED_inland.geojson` was edited by
hand in QGIS. This script READS it. It has no write path and must never grow one — the
same rule as `validate_region_v1_5.py`, and for the same reason: once a hand-drawn ring
exists, a generator pointed at it is a loaded gun aimed at the only copy of the geometry.
(The draft generators that preceded it — build_v3_isobath_seed.py, build_region_v3_draft.py —
were retired 2026-08-24 once the ring was drawn; git history has them.)

WHY A VALIDATOR, AND WHY IT CHECKS *WET REACHES* RATHER THAN SEGMENTS
--------------------------------------------------------------------

The region is NOT the boundary. `build_static` runs

    create_active(zmin=mask_zmin)  →  region clip  →  land_boxes → 0
    →  _fill_inactive_holes  →  create_boundary  →  demote mask==2 outside every arm

so what decides where a water-level BC can appear is **wherever the ring crosses water
shallower than `mask_zmin`**. `create_boundary` puts `mask==2` on the outermost active
WET cells; every one not inside a declared arm has to be demoted. An undeclared wet
crossing is imposed ocean level somewhere nobody looked.

⚠️ **Ring VERTICES are not hydrography.** A hand-drawn vertex lands where the cursor
landed. v1.5's predecessor tagged *segments*, which attributed a crossing to whichever
vertex pair happened to straddle it — that is how 1.79 km of dry ground came to be
recorded as "the Raritan River cut". So this script ignores segment structure: it walks
the ring at a fixed ground step, reads the merged bed, and finds contiguous runs where
the bed is WET and ACTIVE. Those runs are the objects that must each be declared.

THE THREE-WAY CLASSIFICATION, WHICH IS THE POINT
------------------------------------------------

    bed >= 0          LAND      — a real coastline; no BC possible
    mask_zmin <= bed < 0   WET+ACTIVE — 🔴 CAN CARRY mask==2. Must be declared.
    bed < mask_zmin   DEEP      — create_active already switched it off; no BC

Only the middle class matters. Note it is NOT "wet": water deeper than `mask_zmin` is
inactive and carries nothing, which is exactly why the ocean side can be a straight box.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import nj_sfincs  # noqa: F401  — sets PROJ_DATA
from nj_sfincs.gdaltools import run_gdal

DRAWN = ROOT / "data" / "region_v3_EDITED_inland.geojson"
FIG = ROOT / "reports" / "figures"

#: The bed, in DEFAULT_ELEVATION_LIST order, BOTTOM first (gdalbuildvrt: later wins).
#: ⚠️ `nj_10ft_dem` is included LAST-but-one because the ring runs over a lot of inland
#: NJ that no marine tier covers — without it 22% of the walk reads NoData. It is
#: NJ-land-only and reads 0.0 (not NoData) over water, which is why the model gives it
#: `zmin: 0.001`; the same filter is applied below.
TIERS = [
    # ⭐ gmrt_v3 first (lowest priority) — it is the ONLY tier covering the outer shelf
    # south of lat 39.6, which is where 131.8 km of the ring read NoData before it landed.
    ("gmrt_v3 ~50 m", "elevation_v3/gmrt_v3.tif"),
    ("gmrt ~50 m (archived)", "elevation/gmrt_nj.tif"),
    ("cudem13 1/3\"", "elevation_v3/cudem13_v3.vrt"),
    ("cudem 1/9\"", "elevation/cudem_nj.vrt"),
]
LAND_FILL = ("nj_10ft_dem (zmin 0.001)", "elevation_v3/nj_10ft_dem_v3.tif")
LAND_FILL_ZMIN = 0.001

STEP_KM = 0.050       #: ground step along the ring
MIN_REACH_KM = 0.15   #: shorter runs are single-pixel noise, reported but not failed
GRID_DEG = 1.0 / 1200.0

#: 🔴 THE DECLARATIONS. Every WET+ACTIVE reach must fall inside exactly one box.
#: (name, (lon_min, lat_min, lon_max, lat_max), kind, why)
#: kind: "forced" — will carry mask==2 and needs NACCS/gauge support
#:       "closed" — will be demoted to land; the exchange is outside the model
#:       "river"  — a tidal river cut: NO water-level BC (a `no_waterlevel_box`), and a
#:                  DISCHARGE source at the cut fed by the named upstream gauge. This is
#:                  the v1.5 Raritan pattern (FINDINGS; scripts/download_usgs_sandy_discharge.py).
CROSSINGS: list[tuple[str, tuple[float, float, float, float], str, str]] = [
    # ── inherited from v1.5, already declared there ────────────────────────────
    ("ocean_arm", (-73.98, 40.44, -73.92, 40.59), "forced",
     "v1.5's Atlantic side + the Sandy Hook -> Rockaway Point closure. ⚠️ The west edge "
     "must reach -73.98: the closure runs NW from Rockaway Point (-73.9364, 40.5497) to "
     "(-73.9732, 40.5794), and a -73.96 box left 3.00 km of it undeclared."),
    ("narrows", (-74.06, 40.59, -74.02, 40.62), "forced",
     "Verrazzano Narrows. Carries the Upper Bay + Hudson tidal prism; must stay open."),
    ("arthur_kill", (-74.31, 40.49, -74.24, 40.52), "forced",
     "Arthur Kill MOUTH at Perth Amboy / Ward Point."),
    # ── v3. The three RIVER boxes (toms_river, great_egg_tuckahoe, mullica_lower) were
    # RETIRED 2026-08-24: the inland ring crosses every river at its head of tide on
    # bed >= 0, so no river reach exists to declare. If one reappears here it means the
    # ring drifted back onto tidal water — declare nothing, move the ring.
    ("cape_may_bay", (-75.00, 38.85, -74.942, 38.99), "forced",
     "The Delaware Bay wedge that keeps the Cape May "
     "CANAL uncut -- ring leaves land north of the canal's bay mouth (NOAA 8536110 sits ON "
     "that mouth, -74.960 38.968), runs ~1.5 km offshore round Cape May Point and joins the "
     "south closure. NACCS: sp7548 (4.8 m) and sp15260 (8.4 m) lie on it; thin -- ask for "
     "more save points here."),
    ("cape_may_south", (-74.942, 38.85, -74.83, 38.94), "forced",
     "The south-west corner and the south edge west of the -10 m isobath (lon split at -74.942 with cape_may_bay, which is where the bottom line's bed crosses -10 m off Cape May Point; both the EDITED and the inland-draft ring gate clean on it). Below lat "
     "~38.92 there is no NJ land at lon -74.93, so the ring is in water. NACCS support "
     "is excellent here (Cape May Inlet 0.23 km, 26 pts within 2 km)."),
]


def _km_per_deg(lat: float) -> tuple[float, float]:
    return 111.320 * np.cos(np.radians(lat)), 110.574


def _bed(work: Path, bounds) -> tuple:
    w, s, e, n = bounds
    pad = 0.05
    have = [(nm, ROOT / "data" / r) for nm, r in TIERS if (ROOT / "data" / r).exists()]
    if not have:
        raise SystemExit("no elevation tier on disk")
    vrt = work / "bed.vrt"
    run_gdal("gdalbuildvrt", ["-overwrite", "-allow_projection_difference",
                              "-resolution", "user", "-tr", f"{GRID_DEG:.12f}",
                              f"{GRID_DEG:.12f}", str(vrt),
                              *[str(p) for _, p in have]])
    tif = work / "bed.tif"
    run_gdal("gdalwarp", ["-q", "-overwrite", "-te", f"{w-pad:.6f}", f"{s-pad:.6f}",
                          f"{e+pad:.6f}", f"{n+pad:.6f}",
                          "-tr", f"{GRID_DEG:.12f}", f"{GRID_DEG:.12f}", "-r", "max",
                          "-of", "GTiff", str(vrt), str(tif)])
    import rasterio

    with rasterio.open(tif) as src:
        z = src.read(1).astype("float64")
        z[z == src.nodata] = np.nan
        tr = src.transform
    used = [nm for nm, _ in have]

    lf = ROOT / "data" / LAND_FILL[1]
    if lf.exists():
        ltif = work / "land.tif"
        run_gdal("gdalwarp", ["-q", "-overwrite", "-te", f"{w-pad:.6f}", f"{s-pad:.6f}",
                              f"{e+pad:.6f}", f"{n+pad:.6f}",
                              "-tr", f"{GRID_DEG:.12f}", f"{GRID_DEG:.12f}", "-r", "max",
                              "-of", "GTiff", str(lf), str(ltif)])
        with rasterio.open(ltif) as src:
            L = src.read(1).astype("float64")
        L[L < -1e30] = np.nan
        fill = np.isnan(z) & np.isfinite(L) & (L > LAND_FILL_ZMIN)
        z[fill] = L[fill]
        used.append(f"{LAND_FILL[0]} -> filled {int(fill.sum()):,} px")
    return z, tr, used


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--plot", action="store_true")
    ap.add_argument("--region", type=Path, default=DRAWN,
                    help="ring to walk (default: the drawn v3 ring). Lets a candidate "
                         "redraw be gated BEFORE it replaces the drawn one.")
    args = ap.parse_args()

    from tempfile import TemporaryDirectory

    from shapely.geometry import LineString, Polygon

    from nj_sfincs.domain import DOMAINS

    zmin = DOMAINS["v3"].mask_zmin
    drawn = args.region.resolve()
    ring = np.array(json.loads(drawn.read_text())["features"][0]["geometry"]["coordinates"][0])
    poly = Polygon(ring)
    print(f"{drawn.relative_to(ROOT)}  —  {len(ring)} vertices, mask_zmin {zmin}")
    print(f"  valid={poly.is_valid}  simple={LineString(ring).is_simple}")
    w, s, e, n = poly.bounds
    print(f"  bounds lon {w:.5f}..{e:.5f}  lat {s:.5f}..{n:.5f}")

    with TemporaryDirectory(prefix="v3reg_") as td:
        z, tr, used = _bed(Path(td), poly.bounds)
        print("  bed tiers:", "; ".join(used))

        pts, segs = [], []
        for i in range(len(ring) - 1):
            (x0, y0), (x1, y1) = ring[i], ring[i + 1]
            kx, ky = _km_per_deg((y0 + y1) / 2)
            d = np.hypot((x1 - x0) * kx, (y1 - y0) * ky)
            m = max(2, int(d / STEP_KM))
            t = np.linspace(0, 1, m, endpoint=False)
            pts.append(np.c_[x0 + t * (x1 - x0), y0 + t * (y1 - y0)])
            segs.append(np.full(m, i))
        P = np.vstack(pts)
        SEG = np.concatenate(segs)
        c = ((P[:, 0] - tr.c) / tr.a).astype(int)
        r = ((P[:, 1] - tr.f) / tr.e).astype(int)
        ok = (c >= 0) & (c < z.shape[1]) & (r >= 0) & (r < z.shape[0])
        bed = np.full(len(P), np.nan)
        bed[ok] = z[r[ok], c[ok]]

    land = bed >= 0
    active = (bed >= zmin) & (bed < 0)
    deep = bed < zmin
    nod = np.isnan(bed)
    tot = len(P) * STEP_KM
    print(f"\n  ring perimeter {tot:.1f} km, {len(P)} samples at {STEP_KM*1000:.0f} m")
    for lbl, m in (("LAND      bed >= 0", land),
                   (f"WET+ACTIVE {zmin} <= bed < 0", active),
                   (f"DEEP      bed < {zmin}", deep),
                   ("NO DATA", nod)):
        print(f"    {lbl:28s} {100*m.mean():5.1f}%  {m.sum()*STEP_KM:7.1f} km")
    if nod.mean() > 0.02:
        print(f"    ⚠️ {nod.mean()*100:.1f}% NoData — a reach there is unclassifiable")

    d = np.diff(active.astype(np.int8))
    st = np.flatnonzero(d == 1) + 1
    en = np.flatnonzero(d == -1) + 1
    if active[0]:
        st = np.r_[0, st]
    if active[-1]:
        en = np.r_[en, len(active)]
    reaches = [(a, b) for a, b in zip(st, en) if (b - a) * STEP_KM >= MIN_REACH_KM]
    tiny = len(st) - len(reaches)

    print(f"\n  WET+ACTIVE reaches >= {MIN_REACH_KM*1000:.0f} m: {len(reaches)} "
          f"({tiny} shorter ones ignored)")
    # ⚠️ A sub-threshold reach is NOT noise when it is a channel: on the 2026-08-24 ring
    # the Cape May CANAL (~100 m wide, bed -4 m) and the tidal Metedeconk (54 m, -1.07 m)
    # both hid here. Listed, never failed — the reader decides which ones are channels.
    short = [(a, b) for a, b in zip(st, en) if (b - a) * STEP_KM < MIN_REACH_KM]
    for a, b in short:
        mz = np.nanmin(bed[a:b])
        tag = "  ⚠️ CHANNEL? bed < -0.5 m" if mz < -0.5 else ""
        print(f"      short {int((b-a)*STEP_KM*1000):4d} m at lon {P[a:b,0].mean():.4f} "
              f"lat {P[a:b,1].mean():.4f}  min bed {mz:6.2f}  seg {sorted(set(SEG[a:b].tolist()))}{tag}")
    undeclared, by_box = [], {}
    for a, b in reaches:
        lo, la = P[a:b, 0], P[a:b, 1]
        hit = [nm for nm, (x0, y0, x1, y1), _, _ in CROSSINGS
               if (lo.min() >= x0 and lo.max() <= x1 and la.min() >= y0 and la.max() <= y1)]
        L = (b - a) * STEP_KM
        rec = (L, lo.min(), lo.max(), la.min(), la.max(), np.nanmin(bed[a:b]),
               sorted(set(SEG[a:b].tolist())))
        if len(hit) == 1:
            by_box.setdefault(hit[0], []).append(rec)
        else:
            undeclared.append((rec, hit))

    kinds = {nm: k for nm, _, k, _ in CROSSINGS}
    for nm, _, k, why in CROSSINGS:
        rs = by_box.get(nm, [])
        tot_km = sum(r[0] for r in rs)
        flag = "" if rs else "   ⚠️ box matches NO reach — stale or the ring moved"
        print(f"    ✅ {nm:20s} {k:7s} {len(rs):2d} reach(es) {tot_km:6.2f} km{flag}")
        if args.verbose:
            for L, x0, x1, y0, y1, mz, sg in rs:
                print(f"         {L:5.2f} km  lon {x0:.4f}..{x1:.4f}  lat {y0:.4f}..{y1:.4f}"
                      f"  min bed {mz:6.2f}  seg {sg}")
            print(f"         why: {why}")

    if undeclared:
        print(f"\n  🔴 {len(undeclared)} UNDECLARED WET+ACTIVE REACH(ES) — this is a FAILURE:")
        for (L, x0, x1, y0, y1, mz, sg), hit in sorted(undeclared, key=lambda r: -r[0][0]):
            extra = f"  (matches {len(hit)} boxes: {hit})" if len(hit) > 1 else ""
            print(f"    {L:6.2f} km  lon {x0:.4f}..{x1:.4f}  lat {y0:.4f}..{y1:.4f}"
                  f"  min bed {mz:6.2f}  seg {sg}{extra}")
        print("\n  Each is imposed ocean level somewhere nobody looked. Either move the "
              "ring, or add a CROSSINGS box saying what it is.")

    print(f"\n  river cuts declared: "
          f"{[nm for nm, k in kinds.items() if k == 'river']}")
    print("  ⚠️ each needs BOTH a no_waterlevel_box (an imposed level PUMPS a tidal "
          "river) AND a discharge source at the cut — the v1.5 Raritan pattern.")

    if args.plot:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        FIG.mkdir(parents=True, exist_ok=True)
        fig, ax = plt.subplots(figsize=(10, 12))
        ax.plot(ring[:, 0], ring[:, 1], "-", lw=1.2, color="#1f77b4", label="v3 EDITED ring")
        ax.plot(P[active, 0], P[active, 1], ".", ms=5, color="#ff7f0e",
                label="WET+ACTIVE (needs declaring)")
        for nm, (x0, y0, x1, y1), k, _ in CROSSINGS:
            ax.add_patch(plt.Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False,
                                       ec="#2ca02c" if k != "river" else "#9467bd", lw=1.4))
            ax.text(x1, y1, nm, fontsize=7, color="#333333")
        for (L, x0, x1, y0, y1, _, _), _ in undeclared:
            ax.plot([(x0 + x1) / 2], [(y0 + y1) / 2], "x", ms=12, mew=2.5, color="red")
        ax.set_aspect(1 / np.cos(np.radians(39.6)))
        ax.grid(alpha=0.3); ax.legend(loc="upper right", fontsize=8)
        ax.set_xlabel("lon"); ax.set_ylabel("lat")
        ax.set_title("v3 region — declared crossings (boxes) vs measured wet reaches\n"
                     "red x = UNDECLARED")
        fig.tight_layout()
        p = FIG / "region_v3_validation.png"
        fig.savefig(p, dpi=130)
        print(f"\n  wrote {p.relative_to(ROOT)}")

    return 1 if undeclared else 0


if __name__ == "__main__":
    raise SystemExit(main())
