#!/usr/bin/env python
"""Audit a candidate v4 region ring against what the mask builder will do with it.

Read-only on every input. Usage:

    python scripts/audit_region_v4.py --ring <ring.geojson | vertices.csv> [--maps]

The v4 ring RULE (user, 2026-09-25): contain the TARGET — the NACCS Sandy peak + 3 m, connected
from the ocean, rivers open until that water ends, the neighbour basins with their own inlets
(NEIGHBOUR_BASINS below) shut off — with the edge on ground at least MARGIN above that level
or on a declared line. The source of truth for the ring is the named-vertex list
`data/v4_design/region_v4_vertices.csv`.

It walks the whole ring PERIMETER every 50 m and asks what `nj_sfincs/model.py` makes of
each metre, because today

  * an edge cell with bed < -1 m becomes a water-level BC, then is DEMOTED to a wall
    unless it sits in a declared `boundary_arms` box;
  * EVERY other edge cell (OUTFLOW_MAX_BED = 1e4) becomes FREE OUTFLOW unless a
    `mask_overrides` box walls it — any undeclared low rim is a drain (FINDINGS §50);
  * cells deeper than mask_zmin (-10 m) are INACTIVE unless an always-active box says
    otherwise, and an inactive channel connected to the ocean is not an interior hole.

Checks: A geometry · B perimeter walk (class per 50 m; anything within 200 m of a
declared crossing SPAN in `data/v4_design/v4_crossings.geojson` counts as declared) ·
C in-ring bathtub rim contact at the NACCS Sandy peak +0/+2/+3 m · D every declared
crossing vs the ring · E deep water below mask_zmin · F forcing / validation coverage ·
G (--maps) zoom maps of six hotspot windows + bed profiles along every span · H the TARGET
outside the ring, MOTF land inside it · I every valley the edge crosses (ground below the level
+ MARGIN), with the USGS discharge gauges upstream of it.

Writes data/v4_design/v4_audit.{txt,gpkg} (layers rim_segments, rim_flags,
declared_lines, deeper_than_zmin, target, target_outside, valley_crossings) and, with --maps, reports/figures/v4_audit_*.png.

History: born 2026-09-25 as the independent check of the generated v4 draft ring; the
two generators it checked (`scripts/draft_region_v4.py`, a HUC-12 watershed walker)
were retired the same day. The +3 m target rule replaced the flat +10 m edge rule that
evening; the ring was traced once around it and is edited by hand since (STATUS).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
import xarray as xr
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT
from scipy import ndimage
from scipy.spatial import cKDTree
from shapely.geometry import LineString, Point, Polygon, box

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DESIGN = DATA / "v4_design"
CONTEXT = DESIGN / "v4_design_context.gpkg"
CROSSINGS = DESIGN / "v4_crossings.geojson"
OUT_TXT = DESIGN / "v4_audit.txt"
OUT_GPKG = DESIGN / "v4_audit.gpkg"
FIG = ROOT / "reports" / "figures"
CRS = 32618
RES = 50.0  # audit grid
STEP = 50.0  # perimeter sample spacing
RES_MAP = 25.0  # zoom-map grid
SLR = 3.0  # the target: NACCS Sandy peak + SLR, connected from the ocean
MARGIN = 2.0  # an undeclared edge wants ground >= that level + MARGIN

# Basins that have their own inlets, so the v4 boundary never forces them: shut off (lon/lat).
# Edges follow the declared lines in v4_crossings.geojson (upper_bay_hudson_route, narrows,
# jamaica_bay_wall, rockaway_inlet; cape_henlopen / ocean_south_de; cd_canal).
_ROUTE = [(-74.0586, 40.6021), (-74.068, 40.61), (-74.077, 40.619), (-74.081, 40.629),
          (-74.08, 40.639), (-74.09, 40.644), (-74.09, 40.6545), (-74.1, 40.66),
          (-74.114, 40.668), (-74.106, 40.679), (-74.1, 40.69), (-74.096, 40.7),
          (-74.086, 40.708), (-74.076, 40.724), (-74.056, 40.748), (-74.018, 40.772),
          (-74.012, 40.804), (-73.995, 40.828), (-73.975, 40.852), (-73.968, 40.876),
          (-73.962, 40.9), (-73.955, 40.93), (-73.95, 41.05)]  # fmt: skip
NEIGHBOUR_BASINS = {
    "ny_upper_bay_hudson_jamaica_bay": _ROUTE
    + [(-73.0, 41.05), (-73.0, 40.45), (-73.94, 40.45), (-73.94, 40.53),
       (-73.93, 40.546), (-73.902, 40.58),
       # jamaica_bay_wall, then the Harbor Hill moraine crest (Brooklyn option B, 09-26):
       # drawn well NORTH of the ring's Brooklyn edge so the audit, not this polygon,
       # decides whether the +3 m water stops short of it
       (-73.912, 40.60), (-73.915, 40.65), (-73.915, 40.675), (-73.94, 40.67),
       (-73.97, 40.66), (-74.00, 40.645), (-74.025, 40.625), (-74.0294, 40.6109)],
    "rehoboth_bay_and_the_sea_south": [(-76.0, 38.40), (-76.0, 38.725), (-74.985, 38.725),
                                       (-74.97, 38.76), (-73.0, 38.855), (-73.0, 38.40)],
    "chesapeake_via_cd_canal": [(-76.0, 39.46), (-75.699, 39.46), (-75.699, 39.62),
                                (-76.0, 39.62)],
}  # fmt: skip

# Elevation stack, first valid wins, m NAVD88 (checked 2026-09-25).
# kind: None = as is; "land" = land-only DEM whose values <= 0 are water it does not
# measure (dropped, remembered as water for the NoData fill); "nozero" = drop EXACT
# zeros, which bed_v3_coarse_25m uses as a fill outside v3's DEM coverage (upper
# Delaware 40.0-40.25, upper Raritan: 0.000 where 3DEP has 2.6-3.7 m).
# 🔴 NOT nj_10ft_dem_v4.tif: that 09-24 re-clip was CORRUPT (> 5 m off 3DEP on 81 % of
# land cells; the v3 clip of the same source agrees to 0.1 %) and was deleted 09-25.
ELEV = [
    (
        DATA / "elevation_v3" / "bed_v3_coarse_25m.tif",
        Resampling.average,
        -99999.0,
        "nozero",
    ),
    (
        DATA / "elevation_v4" / "cudem_delaware_v4.vrt",
        Resampling.average,
        -99999.0,
        None,
    ),
    (DATA / "elevation_v3" / "nj_10ft_dem_v3.tif", Resampling.average, None, "land"),
    # USGS 3DEP 1/3" for PA / DE / NY land beyond the CUDEM footprint
    *[
        (
            DATA / "elevation_v4" / "3dep" / f"USGS_13_{t}.tif",
            Resampling.average,
            None,
            "land",
        )
        for t in ("n40w076", "n39w076", "n41w076", "n41w075", "n41w074")
    ],
    (DATA / "elevation_v3" / "gmrt_v3.tif", Resampling.bilinear, None, None),
]

# zoom-map windows (lon/lat)
WINDOWS = {
    "ny_corner": (-74.30, 40.49, -73.87, 40.68),
    "newark_bay": (-74.30, 40.58, -73.93, 40.97),
    "trenton": (-74.90, 40.18, -74.72, 40.30),
    "wilmington": (-75.78, 39.50, -75.47, 39.83),
    "delaware_mouth": (-75.36, 38.68, -74.88, 38.97),
    "raritan": (-74.58, 40.46, -74.42, 40.58),
}

_lines: list[str] = []


def say(s: str = "") -> None:
    print(s)
    _lines.append(s)
    sys.stdout.flush()


def to_ll(x, y):
    p = gpd.GeoSeries([Point(x, y)], crs=CRS).to_crs(4326).iloc[0]
    return round(p.x, 4), round(p.y, 4)


def lon_to_x(lon, lat=39.2):
    return gpd.GeoSeries([Point(lon, lat)], crs=4326).to_crs(CRS).iloc[0].x


def utm(geom_ll):
    return gpd.GeoSeries([geom_ll], crs=4326).to_crs(CRS).iloc[0]


def elevation_stack(transform, width: int, height: int, crs=CRS):
    """The ELEV stack on any grid. Returns (z, landwater): z is NaN where no tier
    measured anything; `landwater` marks cells a land-only DEM called water (<= 0 m)
    — 3DEP blanks tidal rivers, so those must not read as land."""
    z = np.full((height, width), np.nan, "float32")
    landwater = np.zeros((height, width), bool)
    for path, rs, nd, kind in ELEV:
        if not path.exists():
            print(f"  SKIP missing {path.name}")
            continue
        with rasterio.open(path) as src:
            nodata = src.nodata if nd is None else nd
            with WarpedVRT(
                src,
                crs=crs if not isinstance(crs, int) else f"EPSG:{crs}",
                transform=transform,
                width=width,
                height=height,
                resampling=rs,
                nodata=nodata,
                dtype="float32",
            ) as v:
                a = v.read(1).astype("float32")
        if nodata is not None and not np.isnan(nodata):
            a[a == nodata] = np.nan
        a[(a < -3000) | (a > 3000)] = np.nan
        if kind == "land":
            landwater |= np.isnan(z) & (a <= 0)
            a[a <= 0] = np.nan
        elif kind == "nozero":
            a[np.abs(a) < 0.005] = np.nan
        fill = np.isnan(z) & ~np.isnan(a)
        z[fill] = a[fill]
    return z, landwater


def fill_nodata(z, landwater):
    """NoData -> 0 m where a land DEM saw water (a tidal river surface), else +5 m."""
    return np.where(np.isnan(z), np.where(landwater, 0.0, 5.0), z).astype("float32")


def load_z25(x0, y0, x1, y1):
    W, H = int((x1 - x0) / RES_MAP), int((y1 - y0) / RES_MAP)
    T = from_origin(x0, y1, RES_MAP, RES_MAP)
    z, landwater = elevation_stack(T, W, H)
    return np.where(np.isnan(z) & landwater, 0.0, z), T, W, H


def read_ring(path: Path) -> gpd.GeoDataFrame:
    """A ring file: GeoJSON / any OGR polygon, or the named-vertex CSV (name, lon, lat)."""
    if path.suffix == ".csv":
        v = pd.read_csv(path, comment="#")
        return gpd.GeoDataFrame(
            {"name": [path.stem]}, geometry=[Polygon(zip(v.lon, v.lat))], crs=4326
        )
    return gpd.read_file(path).to_crs(4326)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--ring", type=Path, required=True, help="the ring to audit (GeoJSON / any OGR)"
    )
    ap.add_argument(
        "--maps", action="store_true", help="also write the zoom maps + span profiles"
    )
    args = ap.parse_args()
    say(f"ring audited: {args.ring}")
    ring_ll = read_ring(args.ring)
    ring = ring_ll.to_crs(CRS).geometry.iloc[0]

    # ── A. geometry ─────────────────────────────────────────────────────────────
    say("A. GEOMETRY")
    c = np.array(ring.exterior.coords)[:-1]
    seg = np.hypot(*np.diff(np.vstack([c, c[:1]]), axis=0).T)
    say(
        f"  valid={ring.is_valid} holes={len(ring.interiors)} vertices={len(c)} "
        f"area={ring.area / 1e6:.0f} km2 perimeter={ring.length / 1e3:.0f} km"
    )
    say(
        f"  segment length: min {seg.min():.0f} m, p10 {np.percentile(seg, 10):.0f}, "
        f"max {seg.max() / 1e3:.1f} km"
    )
    angs = []
    for i in range(len(c)):
        a, b, d = c[i - 1], c[i], c[(i + 1) % len(c)]
        u, v = a - b, d - b
        ang = np.degrees(np.arccos(np.clip(u @ v / np.hypot(*u) / np.hypot(*v), -1, 1)))
        angs.append(ang)
    angs = np.array(angs)
    for i in np.where(angs < 30)[0]:
        say(f"  ⚠ spike: interior angle {angs[i]:.0f}° at {to_ll(*c[i])}")
    opened = ring.buffer(-400).buffer(400)
    necks = ring.difference(opened)
    necks = [g for g in getattr(necks, "geoms", [necks]) if g.area > 0.5e6]
    for g in necks:
        say(
            f"  neck/sliver narrower than 800 m: {g.area / 1e6:.1f} km2 at "
            f"{to_ll(g.centroid.x, g.centroid.y)}"
        )
    if not necks:
        say("  no neck narrower than 800 m holding > 0.5 km2")

    # ── grid + elevation (the draft's own stack, so the two agree on z) ──────────
    x0, y0, x1, y1 = ring.buffer(3000).bounds
    x0, y0 = np.floor(x0 / 1e3) * 1e3, np.floor(y0 / 1e3) * 1e3
    x1, y1 = np.ceil(x1 / 1e3) * 1e3, np.ceil(y1 / 1e3) * 1e3
    W, H = int((x1 - x0) / RES), int((y1 - y0) / RES)
    T = from_origin(x0, y1, RES, RES)
    z, landwater = elevation_stack(T, W, H)
    inring = rasterize(
        [(ring, 1)], out_shape=(H, W), transform=T, fill=0, dtype="uint8"
    ).astype(bool)
    say(
        f"  NoData inside ring: {np.sum(inring & np.isnan(z) & ~landwater) * RES * RES / 1e6:.2f} km2"
    )
    zf = fill_nodata(z, landwater)

    def rc(x, y):
        return (
            np.clip(((y1 - np.asarray(y)) / RES).astype(int), 0, H - 1),
            np.clip(((np.asarray(x) - x0) / RES).astype(int), 0, W - 1),
        )

    # NACCS Sandy peak, nearest node
    pts = gpd.read_file(CONTEXT, layer="naccs_points").to_crs(CRS)
    wl = pts["sandy_max_m_msl"].astype(float).values
    ok = np.isfinite(wl) & (wl > -100)
    tree = cKDTree(np.c_[pts.geometry.x.values[ok], pts.geometry.y.values[ok]])
    cc, rr = np.meshgrid(np.arange(W), np.arange(H))
    _, idx = tree.query(
        np.c_[(x0 + (cc.ravel() + 0.5) * RES), (y1 - (rr.ravel() + 0.5) * RES)], k=1
    )
    WL = wl[ok][idx].reshape(H, W).astype("float32")
    del cc, rr, idx

    # ── the TARGET (section H reports it; B uses it) ─────────────────────────────
    S8 = np.ones((3, 3), bool)
    zt = np.where(np.isnan(z), np.where(landwater, 0.0, 99.0), z)  # missing = never wet
    shut = rasterize(
        [(utm(Polygon(p)), 1) for p in NEIGHBOUR_BASINS.values()],
        out_shape=(H, W),
        transform=T,
        fill=0,
        dtype="uint8",
    ).astype(bool)
    lab, n = ndimage.label((zt < -5) & ~shut, structure=S8)
    sea = (
        lab == int(np.argmax(ndimage.sum(np.ones_like(lab), lab, range(1, n + 1)))) + 1
    )
    m = (zt < WL + SLR) & ~shut
    lab, _ = ndimage.label(m, structure=S8)
    ids = np.unique(lab[sea & m])
    target = np.isin(lab, ids[ids > 0])
    del lab, m, zt

    # ── C. in-ring bathtub (connected from the ocean INSIDE THE RING ONLY) ───────
    deep = inring & (zf < -5)
    lab, n = ndimage.label(deep, structure=S8)
    sizes = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
    ocean = lab == (int(np.argmax(sizes)) + 1)
    wet = {}
    for s in (0.0, 2.0, 3.0):
        m = inring & (zf < WL + s)
        lab, _ = ndimage.label(m, structure=S8)
        ids = np.unique(lab[ocean & m])
        wet[s] = np.isin(lab, ids[ids > 0])
    # a rim cell "sees" water if a wet cell lies within 100 m of it
    wetd = {s: ndimage.binary_dilation(w, iterations=2) for s, w in wet.items()}

    # ── declared lines: the SPANS in the crossings file (the part of each line that is
    # the crossing) — an overlong line must not hide a low rim ─────────────────────
    cx = gpd.read_file(CROSSINGS).to_crs(CRS)
    cx = cx[cx.kind.isin(["cut", "forced", "wall", "sea_inactive"])]
    decl = [(r["name"], r["kind"], r.geometry) for _, r in cx.iterrows()]
    dgdf = gpd.GeoDataFrame(
        {"name": [d[0] for d in decl], "kind": [d[1] for d in decl]},
        geometry=[d[2] for d in decl],
        crs=CRS,
    )

    # ── B. perimeter walk ─────────────────────────────────────────────────────────
    ext = ring.exterior
    s_along = np.arange(0, ext.length, STEP)
    P = [ext.interpolate(s) for s in s_along]
    px = np.array([p.x for p in P])
    py = np.array([p.y for p in P])
    r, cidx = rc(px, py)
    zp = zf[r, cidx]
    # lowest ground within 100 m INSIDE the ring (what the edge face's subgrid sees)
    zmin_in = np.where(inring, zf, np.inf)
    zmin_in = ndimage.minimum_filter(zmin_in, size=5)[r, cidx]
    near_name = np.array([""] * len(P), dtype=object)
    near_kind = np.array([""] * len(P), dtype=object)
    for name, kind, ln in decl:
        dd = np.array([ln.distance(p) for p in P])
        hit = (dd < 200) & (near_name == "")
        near_name[hit] = name
        near_kind[hit] = kind
    lvl = WL[r, cidx] + SLR
    tgt_touch = ndimage.binary_dilation(target, iterations=2)[r, cidx]
    cls = np.where(
        near_name != "",
        "declared",
        np.where(
            zp < -10,
            "deep_water",
            np.where(
                zp < -1,
                "water_undeclared",
                np.where(
                    zp < 0,
                    "shallow_undeclared",
                    np.where(zmin_in < lvl + MARGIN, "land_low", "land_ok"),
                ),
            ),
        ),
    )
    touch = {s: wetd[s][r, cidx] for s in wet}

    # group consecutive samples (the ring is closed: rotate to start on a class change)
    brk = np.where(cls != np.roll(cls, 1))[0]
    start = brk[0] if len(brk) else 0
    order = np.r_[start : len(P), 0:start]
    segs = []
    cur = [order[0]]
    for k in order[1:]:
        if cls[k] == cls[cur[-1]] and near_name[k] == near_name[cur[-1]]:
            cur.append(k)
        else:
            segs.append(cur)
            cur = [k]
    segs.append(cur)
    rows, geoms = [], []
    for seg_idx in segs:
        sg = np.array(seg_idx)
        g = (
            LineString(np.c_[px[sg], py[sg]])
            if len(sg) > 1
            else Point(px[sg[0]], py[sg[0]]).buffer(1).exterior
        )
        mid = sg[len(sg) // 2]
        rows.append(
            dict(
                cls=cls[sg[0]],
                declared=near_name[sg[0]],
                kind=near_kind[sg[0]],
                length_km=round(len(sg) * STEP / 1e3, 2),
                z_min=round(float(zp[sg].min()), 1),
                z_p50=round(float(np.median(zp[sg])), 1),
                zin_min=round(float(zmin_in[sg].min()), 1),
                wet0_km=round(touch[0.0][sg].sum() * STEP / 1e3, 2),
                wet2_km=round(touch[2.0][sg].sum() * STEP / 1e3, 2),
                wet3_km=round(touch[3.0][sg].sum() * STEP / 1e3, 2),
                target_km=round(tgt_touch[sg].sum() * STEP / 1e3, 2),
                level=round(float(lvl[sg].max()), 1),
                lon=to_ll(px[mid], py[mid])[0],
                lat=to_ll(px[mid], py[mid])[1],
            )
        )
        geoms.append(g)
    rim = gpd.GeoDataFrame(rows, geometry=geoms, crs=CRS)

    say("\nB. PERIMETER WALK (every 50 m of the ring edge)")
    tot = rim.groupby("cls").length_km.sum().round(1)
    for k, v in tot.items():
        say(f"  {k:20s} {v:7.1f} km")
    say(
        "  classes: declared = within 200 m of a cut / forced / wall line; land_ok = "
        f"ground >= the local Sandy peak + {SLR:.0f} m + {MARGIN:.0f} m; land_low = dry ground "
        "below that (→ FREE OUTFLOW by default; harmless unless the target reaches it); "
        "shallow/water_undeclared = bed < 0 not on any declared line (→ wall if < -1, "
        "else outflow); deep_water = < -10 m (inactive under mask_zmin)"
    )

    say(
        "\n  every NON-declared WATER stretch, and every land_low stretch the target or the "
        "in-ring bathtub reaches (target_km > 0 is the failure):"
    )
    water = rim.cls.isin(["shallow_undeclared", "water_undeclared", "deep_water"])
    wet_land = (rim.cls == "land_low") & ((rim.wet3_km > 0) | (rim.target_km > 0))
    bad = rim[(water & (rim.length_km >= 0.2)) | wet_land].sort_values(
        ["lat"], ascending=False
    )
    with pd.option_context("display.width", 250, "display.max_rows", 500):
        say(bad.drop(columns="geometry").to_string(index=False))

    say("\n  bathtub rim contact (km of perimeter within 100 m of the in-ring sheet):")
    for s in (0.0, 2.0, 3.0):
        k = f"wet{int(s)}_km"
        by = rim.groupby(rim.declared.where(rim.declared != "", "(" + rim.cls + ")"))[
            k
        ].sum()
        by = by[by > 0].round(2)
        say(f"   +{s:.0f} m: " + ", ".join(f"{i} {v}" for i, v in by.items()))

    # ── D. declared lines vs the ring ────────────────────────────────────────────
    say("\nD. DECLARED LINES vs THE RING")
    drows = []
    for name, kind, ln in decl:
        on = np.mean(
            [
                ext.distance(ln.interpolate(f, normalized=True)) < 150
                for f in np.linspace(0, 1, 101)
            ]
        )
        inside = ln.intersection(ring.buffer(-150)).length / ln.length
        outside = ln.difference(ring.buffer(150)).length / ln.length
        ends = [Point(ln.coords[0]), Point(ln.coords[-1])]
        zr = [float(zf[rc(e.x, e.y)]) for e in ends]
        wlend = [float(WL[rc(e.x, e.y)]) for e in ends]
        dmax = max(
            ext.distance(ln.interpolate(f, normalized=True))
            for f in np.linspace(0, 1, 101)
        )
        drows.append(
            dict(
                name=name,
                kind=kind,
                len_km=round(ln.length / 1e3, 1),
                on_ring_frac=round(on, 2),
                frac_inside=round(inside, 2),
                frac_outside=round(outside, 2),
                max_off_ring_m=round(dmax),
                z_end0=round(zr[0], 1),
                z_end1=round(zr[1], 1),
                peak_wl=round(max(wlend), 2),
                end_margin_3m=round(min(zr) - (max(wlend) + 3), 1),
            )
        )
    dtab = pd.DataFrame(drows)
    with pd.option_context("display.width", 250):
        say(dtab.to_string(index=False))
    say(
        "  on_ring_frac = share of the line within 150 m of the ring edge (1.0 = the edge IS the "
        "line); end_margin_3m = lower end z − (peak + 3 m), should be > 0 for a forced line"
    )

    # ── E. deep water below mask_zmin inside the ring ────────────────────────────
    say(
        "\nE. WATER DEEPER THAN mask_zmin (-10 m) INSIDE THE RING — inactive unless boxed"
    )
    dz = inring & (zf < -10)
    lab, n = ndimage.label(dz, structure=S8)
    sizes = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
    big = int(np.argmax(sizes)) + 1
    from nj_sfincs.domain import V3

    boxes = gpd.GeoSeries(
        [
            gpd.GeoSeries.from_xy([b[0], b[2]], [b[1], b[3]], crs=4326)
            .to_crs(CRS)
            .union_all()
            .envelope
            for b in V3.always_active_boxes_ll
        ],
        crs=CRS,
    )
    boxmask = rasterize(
        [(g, 1) for g in boxes], out_shape=(H, W), transform=T, fill=0, dtype="uint8"
    ).astype(bool)
    regions = {
        "delaware_bay_river (lat>38.80, lon<-74.93)": (-75.8, 38.80, -74.93, 40.3),
        "ny_harbor_lower_bay (lat>40.42, lon<-73.93)": (-74.35, 40.42, -73.93, 40.70),
        "arthur_kill_upper (lat>40.55, lon<-74.17)": (-74.30, 40.55, -74.17, 40.70),
        "kvk_newark_bay (lat>40.63, lon -74.17..-74.08)": (
            -74.17,
            40.63,
            -74.08,
            40.76,
        ),
    }
    for nm, (w, s_, e, nn) in regions.items():
        bx = (
            gpd.GeoSeries.from_xy([w, e], [s_, nn], crs=4326)
            .to_crs(CRS)
            .union_all()
            .envelope
        )
        bm = rasterize(
            [(bx, 1)], out_shape=(H, W), transform=T, fill=0, dtype="uint8"
        ).astype(bool)
        a = dz & bm
        con = a & (lab == big)
        say(
            f"  {nm}: {a.sum() * RES * RES / 1e6:6.1f} km2 below -10 m; "
            f"{con.sum() * RES * RES / 1e6:6.1f} km2 of it connected to the open-shelf deep "
            f"component; covered by v3's always-active boxes {np.sum(a & boxmask) * RES * RES / 1e6:.1f} km2; "
            f"deepest {zf[a].min() if a.any() else np.nan:.1f} m"
        )
    # longest deep thalweg into the Delaware: northernmost deep cell connected to the shelf
    dcon = lab == big
    col_lim = int((lon_to_x(-74.93) - x0) / RES)
    rows_, cols_ = np.where(dcon[:, :col_lim])
    if len(rows_):
        k = np.argmin(rows_)
        say(
            f"  the shelf's deep component reaches INTO the Delaware as far north as "
            f"{to_ll(x0 + (cols_[k] + 0.5) * RES, y1 - (rows_[k] + 0.5) * RES)}"
        )

    # ── F. coverage ───────────────────────────────────────────────────────────────
    say("\nF. FORCING / VALIDATION COVERAGE vs the ring")
    lon0, lat0, lon1, lat1 = ring_ll.total_bounds
    say(f"  ring bounds lon {lon0:.3f}..{lon1:.3f}, lat {lat0:.3f}..{lat1:.3f}")
    for f, xs0, ys0 in [
        (DATA / "precip_v4" / "aorc_sandy_v4.nc", "x", "y"),
        (DATA / "era5" / "era5_nj_sandy_2012_10_28_31.nc", "x", "y"),
        (DATA / "waves_v3" / "cora_waves_v3.nc", "lon", "lat"),
        (DATA / "waves_v3" / "naccs_stwave_v3.nc", None, None),
    ]:
        ds = xr.open_dataset(f)
        xs, ys = xs0, ys0
        if xs is None:
            xs = [
                k
                for k in list(ds.coords) + list(ds.data_vars)
                if "lon" in k or k == "x"
            ]
            ys = [
                k
                for k in list(ds.coords) + list(ds.data_vars)
                if "lat" in k or k == "y"
            ]
            xs, ys = (xs[0], ys[0]) if xs and ys else (None, None)
        if xs is None:
            say(f"  {f.name}: no lon/lat found")
            continue
        bx = float(ds[xs].min()), float(ds[xs].max())
        by = float(ds[ys].min()), float(ds[ys].max())
        gap = []
        if bx[0] > lon0:
            gap.append(f"west short by {bx[0] - lon0:.3f}°")
        if bx[1] < lon1:
            gap.append(f"east short by {lon1 - bx[1]:.3f}°")
        if by[0] > lat0:
            gap.append(f"south short by {by[0] - lat0:.3f}°")
        if by[1] < lat1:
            gap.append(f"north short by {lat1 - by[1]:.3f}°")
        say(
            f"  {f.name}: lon {bx[0]:.3f}..{bx[1]:.3f} lat {by[0]:.3f}..{by[1]:.3f}  {'; '.join(gap) or 'covers'}"
        )
    hwm = gpd.read_file(DATA / "validation_v4" / "sandy_hwms_v4.geojson").to_crs(CRS)
    say(f"  HWMs inside ring: {int(hwm.within(ring).sum())} of {len(hwm)}")
    ng = gpd.read_file(CONTEXT, layer="noaa_gauges").to_crs(CRS)
    namecol = [k for k in ng.columns if k.lower() in ("name", "station", "label")]
    for _, g in ng.iterrows():
        dd = ring.exterior.distance(g.geometry)
        say(
            f"   NOAA {g[namecol[0]] if namecol else _}: "
            f"{'inside' if ring.contains(g.geometry) else 'OUTSIDE'}, {dd / 1e3:.1f} km from edge"
        )

    # ── H. the TARGET vs the ring ─────────────────────────────────────────────────
    say(
        f"\nH. TARGET = NACCS Sandy peak + {SLR:.0f} m, connected from the ocean, rivers open, "
        f"neighbour basins shut ({', '.join(NEIGHBOUR_BASINS)})"
    )
    land = zf > 0
    out = target & ~inring
    say(
        f"  target {target.sum() * RES * RES / 1e6:,.0f} km2 (land "
        f"{np.sum(target & land) * RES * RES / 1e6:,.0f}); OUTSIDE the ring "
        f"{out.sum() * RES * RES / 1e6:.2f} km2 (land {np.sum(out & land) * RES * RES / 1e6:.2f})"
    )
    lab, n = ndimage.label(
        out & land, structure=S8
    )  # land pieces (open sea is the isobath's job)
    sizes = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1)) * RES * RES / 1e6
    trows, tgeo = [], []
    for i in np.argsort(sizes)[::-1]:
        if sizes[i] < 0.05:
            break
        rr_, cc_ = np.where(lab == i + 1)
        x, y = x0 + (cc_.mean() + 0.5) * RES, y1 - (rr_.mean() + 0.5) * RES
        trows.append(
            dict(km2=round(float(sizes[i]), 2), lon=to_ll(x, y)[0], lat=to_ll(x, y)[1])
        )
        tgeo.append(Point(x, y))
        say(
            f"   {sizes[i]:6.2f} km2 of target LAND outside at {to_ll(x, y)}, ground p50 "
            f"{np.median(zf[lab == i + 1]):.1f} m, level {np.median(WL[lab == i + 1]) + SLR:.1f} m"
        )
    tout = gpd.GeoDataFrame(trows, geometry=tgeo, crs=CRS) if trows else None
    with rasterio.open(DATA / "validation_v4" / "sandy_motf_extent_v4.tif") as src:
        with WarpedVRT(
            src, crs=f"EPSG:{CRS}", transform=T, width=W, height=H,
            resampling=Resampling.max, nodata=255,
        ) as v:  # fmt: skip
            motf = v.read(1) == 1
    mw = motf & land
    say(
        f"  FEMA MOTF flooded land (NJ only) inside the ring: {np.mean(inring[mw]):.3f} of "
        f"{mw.sum() * RES * RES / 1e6:,.0f} km2; inside the target (±100 m): "
        f"{np.mean(ndimage.binary_dilation(target, iterations=2)[mw]):.3f}"
    )

    # ── I. valley crossings: where the edge dips below the level + MARGIN ─────────
    say(
        f"\nI. VALLEYS THE EDGE CROSSES (ground < level + {MARGIN:.0f} m for ≥ 100 m, not sea), "
        "with USGS discharge gauges (Sandy record) OUTSIDE the ring within 6 km"
    )
    usgs = gpd.read_file(CONTEXT, layer="usgs_q_sandy").to_crs(CRS)
    usgs = usgs[~usgs.within(ring)]
    low = (zmin_in < lvl + MARGIN) & (zmin_in > -1)
    lab1, n1 = ndimage.label(low)
    if low[0] and low[-1]:
        lab1[lab1 == lab1[-1]] = lab1[0]
    vrows, vgeo = [], []
    for i in np.unique(lab1[lab1 > 0]):
        idx = np.where(lab1 == i)[0]
        if len(idx) < 2:
            continue
        k = idx[np.argmin(zmin_in[idx])]
        pk = Point(px[k], py[k])
        dg = usgs.distance(pk)
        near = usgs[dg < 6000].assign(km=dg[dg < 6000] / 1e3)
        near = near.sort_values("da", ascending=False).head(2)
        vrows.append(
            dict(
                lon=to_ll(px[k], py[k])[0],
                lat=to_ll(px[k], py[k])[1],
                length_km=round(len(idx) * STEP / 1e3, 2),
                z_min=round(float(zmin_in[k]), 1),
                level=round(float(lvl[k]), 1),
                declared=near_name[k],
                touched_by_target=bool(tgt_touch[idx].any()),
                gauges=
                "; ".join(f"{str(q.site)[5:]} {str(q['name'])[:30]} {q.da:.0f} mi2 {q.km:.1f} km"
                          for _, q in near.iterrows()),
            )
        )  # fmt: skip
        vgeo.append(LineString(np.c_[px[idx], py[idx]]))
    val = gpd.GeoDataFrame(vrows, geometry=vgeo, crs=CRS)
    say(
        f"  {len(val)} valleys, {val.length_km.sum():.1f} km; touched by the target: "
        f"{int(val.touched_by_target.sum())}; declared: {int((val.declared != '').sum())}"
    )
    with pd.option_context("display.width", 250, "display.max_colwidth", 90):
        show = val[(val.gauges != "") | (val.declared != "") | val.touched_by_target]
        say(show.drop(columns="geometry").to_string(index=False))

    # ── write ─────────────────────────────────────────────────────────────────────
    OUT_GPKG.unlink(missing_ok=True)  # no stale layer survives a re-run
    rim.to_file(OUT_GPKG, layer="rim_segments", driver="GPKG")
    bad.to_file(OUT_GPKG, layer="rim_flags", driver="GPKG")
    dgdf.merge(dtab, on=["name", "kind"]).to_file(
        OUT_GPKG, layer="declared_lines", driver="GPKG"
    )
    # deep inactive water as polygons (coarse) for QGIS
    from rasterio.features import shapes
    from shapely.geometry import shape

    dp = [
        shape(g) for g, v in shapes(dz.astype("uint8"), mask=dz, transform=T) if v == 1
    ]
    gpd.GeoDataFrame(geometry=dp, crs=CRS).to_file(
        OUT_GPKG, layer="deeper_than_zmin", driver="GPKG"
    )
    if tout is not None:
        tout.to_file(OUT_GPKG, layer="target_outside", driver="GPKG")
    val.to_file(OUT_GPKG, layer="valley_crossings", driver="GPKG")
    tp = [
        shape(g)
        for g, v in shapes(target.astype("uint8"), mask=target, transform=T)
        if v == 1
    ]
    tp = gpd.GeoDataFrame(geometry=tp, crs=CRS)
    tp = tp[tp.area > 2 * RES * RES]
    tp.geometry = tp.simplify(RES / 2)
    tp.to_file(OUT_GPKG, layer="target", driver="GPKG")
    if args.maps:
        maps(ring, args.ring.name)
    OUT_TXT.write_text("\n".join(_lines) + "\n")
    say(f"\nwrote {OUT_TXT.relative_to(ROOT)} and {OUT_GPKG.relative_to(ROOT)}")
    return 0


def maps(ring, ring_name: str) -> None:
    """Zoom maps of the hotspot windows + bed profiles along every declared span."""
    flags = gpd.read_file(OUT_GPKG, layer="rim_flags")
    decl = gpd.read_file(OUT_GPKG, layer="declared_lines")
    deep = gpd.read_file(OUT_GPKG, layer="deeper_than_zmin")
    hwm = gpd.read_file(DATA / "validation_v4" / "sandy_hwms_v4.geojson").to_crs(CRS)
    colors = {"cut": "orange", "forced": "cyan", "wall": "red", "sea_inactive": "grey"}
    say("\nG. ZOOM MAPS")

    for name, (w, s, e, n) in WINDOWS.items():
        bb = utm(box(w, s, e, n)).bounds
        z, T, W, H = load_z25(*bb)
        ext = (bb[0], bb[2], bb[1], bb[3])
        fig, ax = plt.subplots(figsize=(10, 10 * (bb[3] - bb[1]) / (bb[2] - bb[0])))
        ax.imshow(np.clip(z, -15, 15), cmap="terrain", vmin=-15, vmax=15, extent=ext)
        ax.contour(np.flipud(z), levels=[10], colors="k", linewidths=0.5, extent=ext)
        ax.contour(
            np.flipud(z),
            levels=[-10],
            colors="navy",
            linewidths=0.5,
            linestyles="dashed",
            extent=ext,
        )
        gpd.GeoSeries([ring.exterior], crs=CRS).plot(ax=ax, color="magenta", lw=2)
        for _, r in decl.iterrows():
            gpd.GeoSeries([r.geometry], crs=CRS).plot(
                ax=ax, color=colors[r.kind], lw=3, alpha=0.9
            )
            c = r.geometry.interpolate(0.5, normalized=True)
            if bb[0] < c.x < bb[2] and bb[1] < c.y < bb[3]:
                ax.annotate(
                    r["name"],
                    (c.x, c.y),
                    fontsize=8,
                    color="k",
                    bbox=dict(fc="w", alpha=0.7, lw=0),
                )
        fl = flags.cx[bb[0] : bb[2], bb[1] : bb[3]]
        if len(fl):
            fl.plot(ax=ax, color="yellow", lw=5, alpha=0.9)
        dp = deep.cx[bb[0] : bb[2], bb[1] : bb[3]]
        if len(dp):
            dp.plot(ax=ax, facecolor="none", edgecolor="navy", hatch="///", lw=0.3)
        hw = hwm.cx[bb[0] : bb[2], bb[1] : bb[3]]
        if len(hw):
            hw.plot(ax=ax, color="k", markersize=10, marker="^")
        ax.set_xlim(bb[0], bb[2])
        ax.set_ylim(bb[1], bb[3])
        ax.set_title(
            f"v4 audit — {ring_name} — {name}: ring (magenta), cut (orange) / forced (cyan) / wall (red); "
            "yellow = flagged rim (undeclared water, or low ground the target reaches);\n"
            "black = +10 m contour, navy dashed/hatched = "
            "-10 m (inactive under mask_zmin); ▲ HWM",
            fontsize=9,
        )
        fig.tight_layout()
        fig.savefig(FIG / f"v4_audit_{name}.png", dpi=110)
        plt.close(fig)
        say(f"  map: reports/figures/v4_audit_{name}.png")

    say("\nG. BED PROFILES along each declared span (every 100 m)")
    for label, ln in zip(decl.name, decl.geometry):
        bb = ln.buffer(200).bounds
        z, T, W, H = load_z25(*bb)
        vals = []
        for s in np.arange(0, ln.length, 100.0):
            p = ln.interpolate(s)
            r = int((bb[3] - p.y) / RES_MAP)
            c = int((p.x - bb[0]) / RES_MAP)
            vals.append(z[min(r, H - 1), min(c, W - 1)])
        say(f"  {label} ({ln.length / 1e3:.1f} km):")
        say("    " + " ".join(f"{v:.1f}" for v in vals))


if __name__ == "__main__":
    sys.exit(main())
