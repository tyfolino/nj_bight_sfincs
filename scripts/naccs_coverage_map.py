#!/usr/bin/env python
"""Inventory the CHS/NACCS zips: which save points have ADCIRC, which have STWAVE.

    python scripts/naccs_coverage_map.py            # CSV + map into reports/naccs/
    python scripts/naccs_coverage_map.py --no-plot  # CSV only

WHY THIS EXISTS
---------------

The CHS webtool ships ADCIRC (water level) and STWAVE (waves) as SEPARATE products
that arrive in the SAME zip, and the two have **disjoint save-point ID spaces** —
measured here, zero collisions across 532 ADCIRC and 193 STWAVE ids, while STWAVE
SP0089 and ADCIRC SP03584 are the same physical point. **Join on coordinates, never
on id.**

⚠️ Match on coordinates with a TOLERANCE. 83 of 85 apparent "STWAVE-only" points
were an exact-float-match artefact: they sit 0 m from an ADCIRC point but differ in
trailing precision. At 50 m the two products are essentially co-located and the
real question — how many ADCIRC points still lack a wave twin — becomes answerable.

This script only reads the FIRST data row of each member (id/lat/lon/depth), so it
is a coverage map, not a parse. It says nothing about whether a point is wet
through Sandy; ``build_naccs_boundary.py`` owns the dry screen, the storm filter and
the datum conversion.
"""

from __future__ import annotations

import argparse
import csv
import io
import math
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NACCS = ROOT / "data" / "NACCS"
OUT = ROOT / "reports" / "naccs"
#: Figures go to reports/figures/, which .gitignore excludes — the repo tracks scored
#: CSVs but deliberately not figure bulk.
FIG = ROOT / "reports" / "figures"

#: Two members are the same physical point within this distance. Chosen with margin:
#: the co-located pairs measure 0 m and the nearest genuinely-distinct neighbour is
#: >1 km, so anything from ~1 m to ~500 m gives the same answer. Not a knife edge.
MATCH_TOL_M = 50.0

#: Indicative lon/lat boxes. ⚠️ These OVERLAP by design (the Sandy Hook -> Rockaway
#: cut runs through Lower Bay) and are NOT the v1.5 boundary arms, which do not exist
#: yet. They are a reading aid for "where is the wave data thin", nothing more. The
#: real per-arm screen is distance to a ``mask==2`` cell, and it needs a frozen mesh.
ZONES: dict[str, tuple[float, float, float, float]] = {
    # name:            (lon_min, lon_max, lat_min, lat_max)
    "verrazzano_narrows": (-74.075, -74.010, 40.580, 40.630),
    "kill_van_kull": (-74.160, -74.060, 40.630, 40.660),
    "arthur_kill": (-74.290, -74.150, 40.500, 40.650),
    "raritan_bay": (-74.300, -74.080, 40.420, 40.530),
    "lower_bay": (-74.100, -73.950, 40.470, 40.600),
    "sandy_hook_bay": (-74.100, -73.980, 40.400, 40.470),
    "sh_rockaway_cut": (-74.060, -73.900, 40.450, 40.580),
    "atlantic_shelf": (-74.350, -73.850, 39.950, 40.450),
}

#: Landmarks, for reading the map only.
LANDMARKS = {
    "Verrazzano Narrows": (-74.0447, 40.6066),
    "Kill Van Kull": (-74.1000, 40.6450),
    "Perth Amboy": (-74.2667, 40.5083),
    "Sandy Hook": (-74.0091, 40.4669),
    "Rockaway Point": (-73.9364, 40.5497),
}

# ══════════════════════════════════════════════════════════════════════════════
# 🔴 A SKETCH. NOT THE REGION POLYGON, AND NOT A DECISION.
# ══════════════════════════════════════════════════════════════════════════════
# These vertices exist so the plan can be LOOKED AT against the save points. They
# are eyeballed from the description in docs/FINDINGS.md §2, not surveyed, not
# snapped to an isobath, and not registered anywhere.
#
# The real geometry is `scripts/build_region_v1_5.py` (STATUS Phase 5b step 1), whose
# vertices become module constants there and whose ring segments carry the
# ocean/land/narrows/arthur_kill tags. `nj_sfincs/domain.py` owns all geography.
# ⚠️ Do NOT import these from anywhere. If they ever start being read by the build,
# the domain registry has been bypassed and that is the defect class premier.py exists
# to prevent.
#
# The OCEAN arm is NOT sketched. v1.5 keeps v1's southern limit (lat 40.150) and its
# Atlantic side, so the honest proxy is v1's OWN `mask==2` cells, read straight off the
# frozen mesh — measured, not eyeballed. Only the closure across the Lower Bay mouth is
# new geometry, and that is the one segment drawn by hand below.
FROZEN_MESH = ROOT / "data" / "frozen_mesh_v1_monmouth" / "sfincs.nc"
#: ⚠️ The frozen mesh's `crs` variable has no usable `epsg` attribute — hardcode.
MESH_EPSG = 32618

#: The NEW closure. Measured, not guessed: v1's ocean-side trace already runs at
#: lon -73.936..-73.947 from lat 40.44 to its north edge at 40.5202, and at the
#: 40.46-40.47 band its easternmost cell is at -73.9364 — Rockaway Point's own
#: longitude. So the ocean arm is not a diagonal across the bay mouth; it is a
#: ~3.3 km STRAIGHT CONTINUATION north of where v1 already stops.
SKETCH_ROCKAWAY_CLOSURE = [
    (-73.9400, 40.5100),
    (-73.9380, 40.5300),
    (-73.9364, 40.5497),  # closes on Rockaway Point
]
#: The two SHORT forced cross-sections. Each is a cut, not a contour.
SKETCH_NARROWS = [(-74.0555, 40.6010), (-74.0340, 40.6060)]
#: ⭐ CHANGED 2026-08-13, on the user's call: Arthur Kill is cut at its MOUTH
#: (Perth Amboy / Ward Point), not at the Kill Van Kull junction. The whole kill is
#: therefore OUT of the domain.
#:
#: Why the original north cut was dropped: it had NO NACCS support (nearest point
#: 9.56 km, 0% within 2 km) and needed the 1-node gauge fallback, while its stated
#: justification — "Perth Amboy / Carteret / Woodbridge stay computed, that's
#: HWM-rich ground" — is unverified. `sandy_hwms.geojson` has ZERO marks up the limb.
#: ⚠️ That file looks CLIPPED at lat 40.515, so the marks may simply never have been
#: pulled; the claim is untested, not disproved. See docs/STATUS.md.
#:
#: The mouth cut forces from NACCS directly: nearest point 0.21-0.87 km across the
#: mouth, 16-19 within 2 km.
SKETCH_ARTHUR_KILL = [(-74.2660, 40.5060), (-74.2500, 40.5010)]
#: Staten Island's south shore: a declared LAND boundary, drawn to show what is
#: being closed off rather than forced. Runs from the Arthur Kill mouth at Ward
#: Point east along the south shore to Fort Wadsworth at the Narrows.
SKETCH_SI_SOUTH = [
    (-74.2500, 40.5010),
    (-74.2000, 40.5100),
    (-74.1350, 40.5350),
    (-74.0800, 40.5750),
    (-74.0555, 40.6010),
]

#: The published rule: nothing extrapolated past 2 km from a boundary cell.
SUPPORT_RADIUS_M = 2000.0

#: dataviz categorical slots 1-3. palette.md certifies exactly these three under
#: ``--pairs all`` (scatter) in both modes: worst pair CVD dE 9.2 light / 9.4 dark.
#: Do not add a fourth slot to this chart -- slot 4 puts yellow beside orange and
#: fails the all-pairs floors.
COLORS = {
    "both": "#2a78d6",
    "adcirc_only": "#eb6834",
    "stwave_only": "#1baf7a",
}
LABELS = {
    "both": "ADCIRC + STWAVE",
    "adcirc_only": "ADCIRC only — wave data missing",
    "stwave_only": "STWAVE only — no water level",
}


def _first_row(zf: zipfile.ZipFile, member: str):
    """(id, lat, lon, depth) from a member's first data row, or None.

    The webtool NUL-pads every CSV out to a power-of-two size; strip before decoding.
    Three header rows precede the data: names, codes, units.
    """
    with zf.open(member) as fh:
        head = fh.read(4096).rstrip(b"\x00").decode("utf-8", "replace")
    lines = head.splitlines()
    if len(lines) < 4:
        return None
    r = next(csv.reader(io.StringIO(lines[3])))
    if len(r) < 4:
        return None
    return int(r[0]), float(r[1]), float(r[2]), float(r[3])


def scan() -> tuple[dict, dict, dict]:
    """Return (adcirc, stwave, zips_holding) keyed by save-point id."""
    zips = sorted(NACCS.glob("CHSFileDownload_*.zip"))
    if not zips:
        raise SystemExit(f"no CHS zips in {NACCS}")

    products: dict[str, dict] = {"ADCIRC": {}, "STWAVE": {}}
    holders: dict[tuple[str, int], set[str]] = defaultdict(set)

    for z in zips:
        zf = zipfile.ZipFile(z)
        members = [
            m
            for m in zf.namelist()
            if m.startswith("CSV/") and m.endswith("Timeseries.csv")
        ]
        n_new = 0
        for m in members:
            got = _first_row(zf, m)
            if got is None:
                continue
            sp, lat, lon, depth = got
            # ⭐ The product is in the MEMBER NAME. The column layout differs between
            # them and index 9 is water elevation in one and mean wave period in the
            # other, so this string is load-bearing, not cosmetic.
            prod = "STWAVE" if "STWAVE" in m else "ADCIRC"
            if sp not in products[prod]:
                n_new += 1
            products[prod][sp] = dict(lat=lat, lon=lon, depth=depth)
            holders[(prod, sp)].add(z.name)
        print(f"[scan] {z.name}: {len(members):4d} members, {n_new:4d} new points")

    return products["ADCIRC"], products["STWAVE"], holders


def _metres(lat1, lon1, lat2, lon2) -> float:
    return math.hypot(
        (lat1 - lat2) * 111_320.0,
        (lon1 - lon2) * 111_320.0 * math.cos(math.radians(lat1)),
    )


def match(adcirc: dict, stwave: dict) -> list[dict]:
    """Fuse the two products on coordinates. Returns one row per physical point."""
    rows: list[dict] = []
    used_stwave: set[int] = set()

    for sp, a in adcirc.items():
        best, best_d = None, math.inf
        for sid, s in stwave.items():
            if sid in used_stwave:
                continue
            d = _metres(a["lat"], a["lon"], s["lat"], s["lon"])
            if d < best_d:
                best, best_d = sid, d
        pair = best if best_d <= MATCH_TOL_M else None
        if pair is not None:
            used_stwave.add(pair)
        rows.append(
            dict(
                lon=a["lon"],
                lat=a["lat"],
                depth_m=a["depth"],
                adcirc_id=sp,
                stwave_id=pair if pair is not None else "",
                match_dist_m=round(best_d, 1) if pair is not None else "",
                have="both" if pair is not None else "adcirc_only",
            )
        )

    for sid, s in stwave.items():
        if sid in used_stwave:
            continue
        rows.append(
            dict(
                lon=s["lon"],
                lat=s["lat"],
                depth_m=s["depth"],
                adcirc_id="",
                stwave_id=sid,
                match_dist_m="",
                have="stwave_only",
            )
        )

    rows.sort(key=lambda r: (r["lat"], r["lon"]))
    return rows


def in_zone(row, box) -> bool:
    lo0, lo1, la0, la1 = box
    return lo0 <= row["lon"] <= lo1 and la0 <= row["lat"] <= la1


def report(rows: list[dict], holders: dict) -> None:
    counts = defaultdict(int)
    for r in rows:
        counts[r["have"]] += 1
    total = len(rows)
    print(f"\n{'':24s} {'pts':>5s} {'both':>6s} {'AD only':>8s} {'ST only':>8s}")
    print(f"{'ALL':24s} {total:5d} {counts['both']:6d} "
          f"{counts['adcirc_only']:8d} {counts['stwave_only']:8d}")

    for name, box in ZONES.items():
        sub = [r for r in rows if in_zone(r, box)]
        if not sub:
            print(f"{name:24s} {0:5d} {'':>6s} {'':>8s} {'':>8s}   ⚠️ EMPTY")
            continue
        c = defaultdict(int)
        for r in sub:
            c[r["have"]] += 1
        flag = "  ⚠️ no waves" if c["both"] == 0 else ""
        print(f"{name:24s} {len(sub):5d} {c['both']:6d} "
              f"{c['adcirc_only']:8d} {c['stwave_only']:8d}{flag}")

    dup = sum(len(v) - 1 for v in holders.values() if len(v) > 1)
    print(f"\nredundant member copies across zips: {dup}")
    per_zip = defaultdict(lambda: [0, 0])
    for key, zs in holders.items():
        for z in zs:
            per_zip[z][0] += 1
            if len(zs) > 1:
                per_zip[z][1] += 1
    print(f"{'zip':24s} {'members':>8s} {'also elsewhere':>15s}")
    for z in sorted(per_zip):
        n, d = per_zip[z]
        tag = "  ← fully redundant" if n == d else ""
        print(f"{z[16:35]:24s} {n:8d} {d:15d}{tag}")


def load_v1_boundary():
    """v1's real ``mask==2`` cells in lon/lat, or None if the frozen mesh is absent."""
    if not FROZEN_MESH.exists():
        return None
    import pyproj
    import xarray as xr

    ds = xr.open_dataset(FROZEN_MESH)
    m = ds["mask"].values
    tr = pyproj.Transformer.from_crs(MESH_EPSG, 4326, always_xy=True)
    lo, la = tr.transform(ds["mesh2d_face_x"].values[m == 2],
                          ds["mesh2d_face_y"].values[m == 2])
    return lo, la


def load_dem(bounds):
    """Decimated CUDEM over ``bounds`` = (W, S, E, N), or None."""
    vrt = ROOT / "data" / "elevation" / "cudem_nj.vrt"
    if not vrt.exists():
        return None
    import numpy as np
    import rasterio
    from rasterio.windows import from_bounds

    with rasterio.open(vrt) as s:
        win = from_bounds(*bounds, transform=s.transform)
        a = s.read(1, window=win, out_shape=(1500, 1100), masked=True).filled(np.nan)
    lon = np.linspace(bounds[0], bounds[2], a.shape[1])
    lat = np.linspace(bounds[3], bounds[1], a.shape[0])
    return lon, lat, a


def arm_coverage(arm_pts, rows, label, as_polyline: bool = True) -> None:
    """Nearest ADCIRC support distance along an arm. Indicative only.

    ⚠️ ``as_polyline=False`` for an unordered CELL SET. `mask==2` cells are not
    ordered along the boundary, so densifying between consecutive entries invents
    straight segments that cut across the domain and reports a gap that is an
    artefact of the ordering, not of the data.
    """
    import numpy as np

    ad = [r for r in rows if r["have"] != "stwave_only"]
    alon = np.array([float(r["lon"]) for r in ad])
    alat = np.array([float(r["lat"]) for r in ad])

    if as_polyline:
        seg = []
        for (x0, y0), (x1, y1) in zip(arm_pts[:-1], arm_pts[1:]):
            n = max(2, int(_metres(y0, x0, y1, x1) / 250))
            seg += list(zip(np.linspace(x0, x1, n), np.linspace(y0, y1, n)))
    else:
        seg = list(arm_pts)
    slon = np.array([p[0] for p in seg])
    slat = np.array([p[1] for p in seg])

    d = np.hypot((slat[:, None] - alat[None, :]) * 111_320,
                 (slon[:, None] - alon[None, :]) * 111_320
                 * np.cos(np.radians(slat[:, None])))
    nn = d.min(axis=1)
    ok = (nn <= SUPPORT_RADIUS_M).mean() * 100
    flag = "" if ok > 90 else "   🔴 NO SUPPORT"
    print(f"  {label:34s} median {np.median(nn)/1000:5.2f} km  max "
          f"{nn.max()/1000:6.2f} km  within 2 km {ok:5.1f}%{flag}")


def plot(rows: list[dict], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    bounds = (-74.36, 39.94, -73.84, 40.69)
    fig, ax = plt.subplots(figsize=(11.5, 12), dpi=160)
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#eef3f7")            # water

    # Natural Earth land first: CUDEM's tiles stop at lon -74.255, which is exactly
    # over Arthur Kill, so the detailed source alone leaves the arm under discussion
    # unshaded. NE is coarse but complete; CUDEM's 0 m contour goes on top for detail.
    try:
        import cartopy.io.shapereader as shpreader
        from matplotlib.patches import Polygon as MplPolygon

        shp = shpreader.natural_earth(resolution="10m", category="physical",
                                      name="land")
        for geom in shpreader.Reader(shp).geometries():
            polys = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
            for p in polys:
                xs, ys = p.exterior.xy
                if max(xs) < bounds[0] or min(xs) > bounds[2]:
                    continue
                if max(ys) < bounds[1] or min(ys) > bounds[3]:
                    continue
                ax.add_patch(MplPolygon(list(zip(xs, ys)), closed=True,
                                        fc="#e6e3d8", ec="none", zorder=0))
    except Exception as e:  # noqa: BLE001 - context only, never fatal
        print(f"[plot] no Natural Earth land ({e})")

    dem = load_dem(bounds)
    if dem is not None:
        dlon, dlat, z = dem
        ax.contourf(dlon, dlat, z, levels=[0, 1e4], colors=["#e6e3d8"], zorder=0)
        ax.contour(dlon, dlat, z, levels=[0], colors=["#a8a496"], linewidths=0.5,
                   zorder=1)
        # The -10 m isobath, thin and recessive: it is CONTEXT, not the boundary.
        # Drawing it shows why a depth rule cannot BE the boundary — it threads the
        # dredged channels straight into the bay (FINDINGS 9).
        ax.contour(dlon, dlat, z, levels=[-10], colors=["#b9cfe0"], linewidths=0.6,
                   zorder=1)

    v1 = load_v1_boundary()
    if v1 is not None:
        ax.scatter(v1[0], v1[1], s=1.4, c="#4a3aa7", zorder=2,
                   label=f"v1 water-level boundary, mask==2  (n={len(v1[0])})")

    for have in ("both", "adcirc_only", "stwave_only"):
        sub = [r for r in rows if r["have"] == have]
        if not sub:
            continue
        ax.scatter(
            [r["lon"] for r in sub], [r["lat"] for r in sub],
            s=24 if have != "both" else 16,
            c=COLORS[have], label=f"{LABELS[have]}  (n={len(sub)})",
            edgecolors="#fcfcfb", linewidths=0.5,
            zorder=4 if have == "both" else 5,
        )

    def draw(pts, color, lw, ls, label=None, z=6):
        ax.plot([p[0] for p in pts], [p[1] for p in pts], color=color, lw=lw, ls=ls,
                solid_capstyle="round", label=label, zorder=z)

    draw(SKETCH_ROCKAWAY_CLOSURE, "#e34948", 2.4, "-",
         "v1.5 ocean arm — NEW closure (sketch)")
    draw(SKETCH_NARROWS, "#e34948", 3.4, "-", "v1.5 forced cross-sections (sketch)")
    draw(SKETCH_ARTHUR_KILL, "#e34948", 3.4, "-")
    draw(SKETCH_SI_SOUTH, "#0b0b0b", 1.6, (0, (5, 3)),
         "v1.5 declared LAND boundary (sketch)")

    ax.annotate(
        "Arthur Kill cut at the MOUTH\nnearest NACCS 0.21 km\nkill is OUT of the domain",
        xy=SKETCH_ARTHUR_KILL[0], xytext=(-74.352, 40.600), fontsize=8,
        color="#e34948", zorder=7,
        arrowprops=dict(arrowstyle="->", color="#e34948", lw=1.2),
    )
    ax.annotate(
        "ocean arm: v1 trace\nextended ~3.3 km north",
        xy=(-73.9380, 40.5300), xytext=(-73.980, 40.605), fontsize=8,
        color="#e34948", zorder=7,
        arrowprops=dict(arrowstyle="->", color="#e34948", lw=1.2),
    )

    for name, (lon, lat) in LANDMARKS.items():
        ax.plot(lon, lat, marker="*", ms=10, color="#0b0b0b", zorder=8)
        ax.annotate(name, (lon, lat), textcoords="offset points", xytext=(7, 4),
                    fontsize=8, color="#0b0b0b", zorder=8)

    ax.set_xlim(bounds[0], bounds[2])
    ax.set_ylim(bounds[1], bounds[3])
    ax.set_xlabel("longitude", fontsize=9, color="#52514e")
    ax.set_ylabel("latitude", fontsize=9, color="#52514e")
    ax.set_title(
        "v1.5 boundary against NACCS support\n"
        "red = sketch, NOT the region polygon",
        fontsize=13, color="#0b0b0b", pad=12, loc="left",
    )
    ax.set_aspect(1.0 / math.cos(math.radians(40.4)))
    for s in ax.spines.values():
        s.set_color("#d5d4cc")
    ax.tick_params(colors="#52514e", labelsize=8)
    ax.legend(loc="lower left", frameon=True, facecolor="#fcfcfb",
              edgecolor="#d5d4cc", fontsize=8, framealpha=0.95)

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"[plot] {path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-plot", action="store_true")
    args = ap.parse_args()

    adcirc, stwave, holders = scan()
    print(f"\n[scan] {len(adcirc)} ADCIRC points, {len(stwave)} STWAVE points")
    rows = match(adcirc, stwave)
    report(rows, holders)

    # ⚠️ INDICATIVE per-arm screen. The real gate is distance to a `mask==2` cell and
    # needs the v1.5 mesh; these are sampled along the SKETCH. It also ignores the dry
    # and depth screens, so every number here is an upper bound on the support that
    # will actually survive `build_naccs_boundary.py`.
    print("\nper-arm ADCIRC support, sampled every 250 m along the SKETCH:")
    arm_coverage(SKETCH_ROCKAWAY_CLOSURE, rows, "ocean arm — Rockaway closure")
    arm_coverage(SKETCH_NARROWS, rows, "Verrazzano Narrows cut")
    arm_coverage(SKETCH_ARTHUR_KILL, rows, "Arthur Kill cut (MOUTH)")

    v1 = load_v1_boundary()
    if v1 is not None:
        pts = list(zip(v1[0], v1[1]))
        print(f"\nv1's REAL mask==2 boundary ({len(pts)} cells), the Atlantic side "
              "v1.5 inherits — per CELL, not a polyline:")
        arm_coverage(pts, rows, "v1 ocean boundary (measured)", as_polyline=False)

    OUT.mkdir(parents=True, exist_ok=True)
    csv_path = OUT / "coverage_inventory.csv"
    with csv_path.open("w", newline="") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=["lon", "lat", "depth_m", "adcirc_id", "stwave_id",
                        "match_dist_m", "have"],
        )
        w.writeheader()
        w.writerows(rows)
    print(f"[csv ] {csv_path}")

    if not args.no_plot:
        plot(rows, FIG / "naccs_coverage_map.png")


if __name__ == "__main__":
    main()
