#!/usr/bin/env python
"""Draft the v4 region ring from the user's QGIS sketch + the v4 design rules, and CHECK
every river crossing. Read-only on the inputs; writes only the draft products.

The rules (STATUS PICK UP, 2026-09-24 evening; plan `hey-claude-we-are-goofy-reddy`):

  1. inland edge on ground >= +10 m NAVD88 — everywhere, NJ and the far banks alike;
  2. river cuts at the head of tide, DRY and walled, discharge injected just inside;
  3. far banks (DE / PA / Staten Island) COMPUTED to +10 m, not walled;
  4. Brooklyn is the one exception: a straight walled cut short of Jamaica Bay;
  5. Arthur Kill NJ shore IN, forced at the Goethals Bridge (Newark Bay stays out until
     the user decides otherwise — remove the `goethals` barrier to bring it in).

How the draft is made (all on a 50 m UTM 18N raster):

  water     = bed < -0.5 m connected to the ocean
  WL        = nearest NACCS ADCIRC Sandy peak (m MSL ~ NAVD88 here, +-0.1)
  wet(s)    = cells with bed < WL + s hydraulically connected to `water` (s = 0, 2, 3 m)
  lowland   = cells with bed < +10 m connected to `water` through bed < +10 m
  keep      = sketch  U  ( lowland  ∩  dilate(wet(3 m), 3 km) )
  barriers  = the CUTS below, burnt into every connectivity step so nothing leaks past
              a head-of-tide cut, the Brooklyn cut, the Goethals cut or Cape Henlopen
  ring      = the component of `keep` that contains the ocean, polygonised, buffered
              by BUF and simplified by TOL < BUF (so the ring still CONTAINS the lowland),
              then re-clipped upstream of every cut

The 3 km dilation of the +3 m sheet is what stops the +10 m lowland running 30 km up
every valley on the Delaware coastal plain: the ring reaches +10 m ground *or* 3 km past
anything a Sandy + 3 m could wet, whichever comes first.

Crossing check, per cut: bed profile along the line (min, wet width), whether the MOTF
sheet touches it, whether the +0 / +2 / +3 m sheets reach it from downstream, and the
nearest head-of-tide gauge from GAUGES. A cut that the +3 m sheet reaches with a wet
width > 0 is a WET cut — allowed only as a forced line (mouth, Narrows, Goethals).

Outputs (data/v4_design/):
  ../region_v4_DRAFT.geojson   the ring (EPSG:4326), for QGIS editing (tracked: data/region_*)
  v4_draft.gpkg                layers: draft_ring, sketch, cuts (+check columns),
                               lowland10, wet0, wet2, wet3, motf, naccs_forced_lines,
                               v3_inflows (+check columns)
  v4_draft_checks.txt          the crossing-check table
  reports/figures/v4_draft_ring.png   overview map

Usage:
    PYTHONPATH=$PWD python scripts/draft_region_v4.py [--res 50] [--buf 900] [--tol 700]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.features import rasterize, shapes
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT
from scipy import ndimage
from scipy.spatial import cKDTree
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "v4_design"
CRS = 32618

SKETCH = DATA / "v4_region_first_edit.geojson"
CONTEXT = OUT / "v4_design_context.gpkg"
MOTF = DATA / "validation_v4" / "sandy_motf_extent_v4.tif"
V3_INFLOWS = DATA / "discharge_v3" / "usgs_sandy_discharge_v3.nc"

# Elevation stack, first valid wins. m NAVD88. The Delaware VRT is the 17 western
# CUDEM 1/9" tiles (data/elevation_v4, overviews on scratch); bed_v3_coarse_25m is the
# v3 gating raster (lon >= -75.01); nj_10ft is NJ land only; gmrt fills the shelf.
ELEV = [
    (
        DATA / "elevation_v3" / "bed_v3_coarse_25m.tif",
        Resampling.average,
        -99999.0,
        None,
    ),
    (
        DATA / "elevation_v4" / "cudem_delaware_v4.vrt",
        Resampling.average,
        -99999.0,
        None,
    ),
    (DATA / "elevation_v4" / "nj_10ft_dem_v4.tif", Resampling.average, None, "land"),
    (DATA / "elevation_v3" / "nj_10ft_dem_v3.tif", Resampling.average, None, "land"),
    # USGS 3DEP 1/3" (NAVD88 m) for PA / DE land beyond the CUDEM footprint
    (
        DATA / "elevation_v4" / "3dep" / "USGS_13_n40w076.tif",
        Resampling.average,
        None,
        "land",
    ),
    (
        DATA / "elevation_v4" / "3dep" / "USGS_13_n39w076.tif",
        Resampling.average,
        None,
        "land",
    ),
    (
        DATA / "elevation_v4" / "3dep" / "USGS_13_n41w076.tif",
        Resampling.average,
        None,
        "land",
    ),
    (
        DATA / "elevation_v4" / "3dep" / "USGS_13_n41w075.tif",
        Resampling.average,
        None,
        "land",
    ),
    (DATA / "elevation_v3" / "gmrt_v3.tif", Resampling.bilinear, None, None),
]

# ── the cuts: (name, [(lon, lat), ...], kind, note) ─────────────────────────────────
# kind: "cut"    = dry head-of-tide cut, walled, discharge just inside
#       "forced" = a forced water-level line (must be WET; needs NACCS points)
#       "wall"   = a land cut we accept as a wall (Brooklyn)
# Lines are drawn generously across the valley; only the crossing matters. Adjust in
# QGIS — the check table tells you what each line does.
CUTS = [
    (
        "delaware_trenton",
        [(-74.800, 40.238), (-74.752, 40.238)],
        "cut",
        "Falls of the Delaware, 1.8 km above the Calhoun St gauge 01463500 (MOTF reached 40.232)",
    ),
    (
        "raritan_island_farm_weir",
        [(-74.505, 40.498), (-74.505, 40.535)],
        "cut",
        "Island Farm Weir (MOTF reached -74.497); source = Bound Brook 01403060 + Lawrence + Middle Brook",
    ),
    (
        "rahway_dam",
        [(-74.290, 40.596), (-74.290, 40.622), (-74.262, 40.640), (-74.258, 40.664)],
        "cut",
        "Rahway River head of tide at Rahway",
    ),
    (
        "goethals",
        [
            (-74.258, 40.664),
            (-74.190, 40.640),
            (-74.160, 40.636),
            (-74.135, 40.646),
            (-74.118, 40.632),
        ],
        "forced",
        "Arthur Kill north end; 34 NACCS pts (3.4-3.7 m) merged 09-24 16:10. Remove to bring Newark Bay in",
    ),
    (
        "rockaway_inlet",
        [(-73.940, 40.530), (-73.930, 40.546), (-73.902, 40.580)],
        "forced",
        "Jamaica Bay stays OUT but its mouth is a forced water-level line, not a wall (23 NACCS pts, 3.0-3.4 m)",
    ),
    (
        "brooklyn_wall",
        [(-73.902, 40.580), (-73.950, 40.602), (-74.032, 40.618), (-74.046, 40.604)],
        "wall",
        "Floyd Bennett -> Fort Hamilton across Gravesend: the one +10 m exception",
    ),
    (
        "cape_henlopen",
        [(-75.260, 38.765), (-75.088, 38.765)],
        "cut",
        "keeps the Lewes-Rehoboth canal lowland out; the mouth line ends on the Henlopen dune",
    ),
    (
        "schuylkill_fairmount",
        [(-75.205, 39.972), (-75.168, 39.972)],
        "cut",
        "Fairmount Dam = USGS 01474500 (25,700 cfs on the peak day)",
    ),
    (
        "brandywine_wilmington",
        [(-75.585, 39.772), (-75.548, 39.772)],
        "cut",
        "Brandywine gorge above the Wilmington riverfront (39.762 was on 2 m ground, wet at +2 m); USGS 01481500 just below",
    ),
    (
        "christina_newport",
        [(-75.618, 39.700), (-75.618, 39.732)],
        "cut",
        "Christina River at Newport",
    ),
    (
        "neshaminy",
        [(-74.945, 40.112), (-74.880, 40.112)],
        "cut",
        "Neshaminy head of tide below Langhorne 01465500",
    ),
    # Rancocas: no cut — MOTF shows Sandy flooding 7 km2 above the forks (the tidal reach runs
    # to Mount Holly / Lumberton); the +10 m rule and the 3 km reach close it (09-24 check).
    (
        "cohansey_bridgeton",
        [(-75.255, 39.440), (-75.205, 39.440)],
        "cut",
        "Cohansey head of tide at Bridgeton; 01412800 upstream",
    ),
    (
        "maurice_millville",
        [(-75.075, 39.403), (-75.025, 39.403)],
        "cut",
        "Union Lake dam, Millville (39.412 crossed the lake); 01411500 upstream",
    ),
    # Salem River: no cut — the +10 m rule and the 3 km reach close its valley on their own
    # (a N-S line there ran ALONG 2.7 km of tidal marsh, 09-24 check).
]

# The upstream EXCLUSION ZONE of each cut: (side, D_km, L_km). A line only blocks paths
# that cross it, and the sketch / +10 m lowland is wider than every line, so the region
# walked around the line-ends and kept 4–10 km of land above each dam (09-24 check by
# the user). Now each line is extended L km along its own direction at both ends and
# swept D km toward `side` (compass letter of the upstream / excluded side); the zone is
# removed from the raster before connectivity AND subtracted from the final polygon, so
# the ring edge lies ON the cut. Edit these with the lines.
UPSTREAM = {
    "delaware_trenton": ("N", 20, 10),
    "raritan_island_farm_weir": ("W", 20, 6),
    "rahway_dam": ("W", 8, 2),
    "goethals": ("N", 15, 3),
    "rockaway_inlet": ("E", 12, 2),
    "brooklyn_wall": ("N", 10, 1),
    "cape_henlopen": ("S", 20, 8),
    "schuylkill_fairmount": ("N", 15, 2.5),
    "brandywine_wilmington": ("N", 12, 2),
    "christina_newport": ("W", 15, 2),
    "neshaminy": ("N", 12, 2.5),
    "cohansey_bridgeton": ("N", 12, 2.5),
    "maurice_millville": ("N", 12, 2.5),
}


def extend_line(ln: LineString, L: float) -> LineString:
    """Prolong both end segments of a polyline by L metres along their own direction."""
    c = np.array(ln.coords)
    d0 = c[0] - c[1]
    d1 = c[-1] - c[-2]
    d0 = d0 / np.hypot(*d0) * L
    d1 = d1 / np.hypot(*d1) * L
    return LineString(np.vstack([c[0] + d0, c, c[-1] + d1]))


def upstream_zone(ln: LineString, side: str, D: float, L: float) -> Polygon:
    """Union of per-segment single-sided buffers of the extended line on the compass
    `side` (per segment, because one buffer of a bent polyline can wrap the wrong side
    at a corner). Each segment's normal is oriented by the compass letter."""
    ext = extend_line(ln, L)
    c = np.array(ext.coords)
    pieces = []
    for i in range(len(c) - 1):
        d = c[i + 1] - c[i]
        u = d / np.hypot(*d)
        # each segment overlaps its neighbours by 100 m so the union stays connected
        seg = LineString([c[i] - 100.0 * u, c[i + 1] + 100.0 * u])
        left = np.array([-d[1], d[0]])  # left-hand normal
        want = {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}[side]
        sign = 1.0 if np.dot(left, want) >= 0 else -1.0
        pieces.append(seg.buffer(sign * D, single_sided=True))
    z = unary_union(pieces)
    if isinstance(z, MultiPolygon):
        z = max(z.geoms, key=lambda g: g.area)
    return Polygon(z.exterior)


# Deep water OUTSIDE the sketch that MAY carry connectivity (lon/lat boxes). The carrier
# rule blocks open water outside the sketch so the sheet cannot run along the Long Island
# or Delaware coasts; the Arthur Kill north of v3's AK-mouth boundary is the one deep
# channel v4 deliberately adds, so it is opened here up to the Goethals barrier.
CARRIER_BOXES = [("arthur_kill", (-74.30, 40.50, -74.14, 40.66))]


# forced lines that already exist (for the NACCS count only); the Delaware mouth line is
# read from the context gpkg (`mouth_line`, drawn 09-24 with the NACCS pull)
FORCED_EXISTING = [
    ("narrows", [(-74.060, 40.605), (-74.030, 40.605)]),
]

# head-of-tide gauges near the cuts (id, name, lon, lat, peak-day cfs) — from the 09-24
# source probe; used only to name the nearest gauge in the check table.
GAUGES = [
    ("01463500", "Delaware at Trenton", -74.7781, 40.2217, 25800),
    ("01474500", "Schuylkill at Philadelphia", -75.1885, 39.9678, 25700),
    ("01403060", "Raritan blw Calco Dam, Bound Brook", -74.5483, 40.5511, 3900),
    ("01481500", "Brandywine at Wilmington", -75.5767, 39.7695, 7220),
    ("01465500", "Neshaminy nr Langhorne", -74.9568, 40.1740, 1830),
    ("01464000", "Assunpink at Trenton", -74.7492, 40.2242, 385),
    ("01405030", "Lawrence Brook, Westons Mills", -74.4128, 40.4831, 0),
    ("01395000", "Rahway at Rahway", -74.2996, 40.6218, 0),
    ("01465850", "Rancocas S Br, Vincentown", -74.7455, 39.9350, 668),
    ("01412800", "Cohansey at Seeley", -75.2515, 39.4720, 698),
    ("01411500", "Maurice at Norma", -75.0770, 39.4950, 480),
    ("01483700", "St Jones at Dover", -75.4900, 39.1580, 880),
]


def log(msg: str, t0: float) -> None:
    print(f"[{time.time() - t0:6.0f} s] {msg}")
    sys.stdout.flush()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", type=float, default=50.0)
    ap.add_argument(
        "--buf", type=float, default=2000.0, help="outward buffer before simplify (m)"
    )
    ap.add_argument(
        "--tol",
        type=float,
        default=1600.0,
        help="simplify tolerance (m), must be < --buf",
    )
    ap.add_argument(
        "--dilate-km",
        type=float,
        default=3.0,
        help="how far past the +3 m sheet the ring may reach",
    )
    args = ap.parse_args()
    assert args.tol < args.buf, "tol must be < buf or the ring can cut into the lowland"
    t0 = time.time()
    OUT.mkdir(exist_ok=True)
    RES = args.res
    km2 = RES * RES / 1e6

    sketch = gpd.read_file(SKETCH).to_crs(CRS)
    sk = unary_union(sketch.geometry)
    # analysis bbox: the sketch + room to the west (DE coastal plain) and north (Rahway)
    x0, y0, x1, y1 = sk.bounds
    x0 -= 32_000
    x1 += 3_000
    y0 -= 3_000
    y1 += 6_000  # DE coastal plain needs room west
    x0, y0 = np.floor(x0 / 1000) * 1000, np.floor(y0 / 1000) * 1000
    x1, y1 = np.ceil(x1 / 1000) * 1000, np.ceil(y1 / 1000) * 1000
    W, H = int((x1 - x0) / RES), int((y1 - y0) / RES)
    T = from_origin(x0, y1, RES, RES)
    log(f"grid {W} x {H} at {RES:.0f} m; bbox {x0:.0f} {y0:.0f} {x1:.0f} {y1:.0f}", t0)

    def warp(path, rs, nd):
        with rasterio.open(path) as src:
            nodata = src.nodata if nd is None else nd
            with WarpedVRT(
                src,
                crs=f"EPSG:{CRS}",
                transform=T,
                width=W,
                height=H,
                resampling=rs,
                nodata=nodata,
                dtype="float32",
            ) as v:
                a = v.read(1).astype("float32")
        if nodata is not None and not np.isnan(nodata):
            a[a == nodata] = np.nan
        a[(a < -3000) | (a > 3000)] = np.nan
        return a

    z = np.full((H, W), np.nan, "float32")
    for path, rs, nd, kind in ELEV:
        if not path.exists():
            log(f"  SKIP missing {path.name}", t0)
            continue
        a = warp(path, rs, nd)
        if kind == "land":
            a[a <= 0] = np.nan
        fill = np.isnan(z) & ~np.isnan(a)
        z[fill] = a[fill]
        log(
            f"  {path.name}: filled {fill.sum()} cells, valid {np.isfinite(z).mean():.3f}",
            t0,
        )
    nodata_mask = np.isnan(z)
    log(f"elevation ready; NoData {nodata_mask.sum() * km2:.0f} km2 on the grid", t0)

    with rasterio.open(MOTF) as src:
        with WarpedVRT(
            src,
            crs=f"EPSG:{CRS}",
            transform=T,
            width=W,
            height=H,
            resampling=Resampling.max,
            nodata=255,
            dtype="uint8",
        ) as v:
            motf = v.read(1) == 1

    # NACCS Sandy peak, nearest neighbour
    pts = gpd.read_file(CONTEXT, layer="naccs_points").to_crs(CRS)
    wl = pts["sandy_max_m_msl"].astype(float).values
    ok = np.isfinite(wl) & (wl > -100)
    tree = cKDTree(np.c_[pts.geometry.x.values[ok], pts.geometry.y.values[ok]])
    cc, rr = np.meshgrid(np.arange(W), np.arange(H))
    gx = x0 + (cc + 0.5) * RES
    gy = y1 - (rr + 0.5) * RES
    _, idx = tree.query(np.c_[gx.ravel(), gy.ravel()], k=1)
    WL = wl[ok][idx].reshape(H, W).astype("float32")
    del cc, rr, gx, gy, idx
    log(
        f"NACCS peak field: p10 {np.percentile(wl[ok], 10):.2f} p50 {np.percentile(wl[ok], 50):.2f} "
        f"p90 {np.percentile(wl[ok], 90):.2f} m from {ok.sum()} pts",
        t0,
    )

    # barriers
    def to_utm(coords):
        return gpd.GeoSeries([LineString(coords)], crs=4326).to_crs(CRS).iloc[0]

    cut_lines = {name: to_utm(c) for name, c, kind, note in CUTS}
    zones = {}
    for name, ln in cut_lines.items():
        if name in UPSTREAM:
            side, D, L = UPSTREAM[name]
            zones[name] = upstream_zone(ln, side, D * 1000.0, L * 1000.0)
    zone_union = unary_union(list(zones.values()))
    barrier = rasterize(
        [(ln.buffer(RES * 1.1), 1) for ln in cut_lines.values()]
        + [(g, 1) for g in zones.values()],
        out_shape=(H, W),
        transform=T,
        fill=0,
        dtype="uint8",
    ).astype(bool)
    log(
        f"upstream exclusion zones: {len(zones)} cuts, {zone_union.area / 1e6:.0f} km2",
        t0,
    )
    S8 = np.ones((3, 3), bool)

    # the ocean: the biggest sub -0.5 m component inside the sketch's ocean part
    zf = np.where(nodata_mask, 5.0, z)  # NoData -> low land: conservative (included)
    sk_mask = rasterize(
        [(sk, 1)], out_shape=(H, W), transform=T, fill=0, dtype="uint8"
    ).astype(bool)
    # Connectivity may leave the sketch only over LAND (and the shallowest water): the
    # open ocean outside the sketch must not carry the sheet along the Long Island or
    # Delaware coasts to shores the ring never meant to include (09-24: Jamaica Bay and
    # Long Beach were reached that way, around the Rockaway barrier).
    carrier = sk_mask | (zf >= -0.5)
    for _name, (w, s_, e, n) in CARRIER_BOXES:
        box = (
            gpd.GeoSeries([Polygon([(w, s_), (e, s_), (e, n), (w, n)])], crs=4326)
            .to_crs(CRS)
            .iloc[0]
        )
        carrier |= rasterize(
            [(box, 1)], out_shape=(H, W), transform=T, fill=0, dtype="uint8"
        ).astype(bool)

    def connected(mask, seeds):
        m = mask & ~barrier & carrier
        lab, _ = ndimage.label(m, structure=S8)
        ids = np.unique(lab[seeds & m])
        ids = ids[ids > 0]
        return np.isin(lab, ids)

    deep = (zf < -0.5) & ~barrier
    lab, n = ndimage.label(deep, structure=S8)
    sizes = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
    ocean_id = int(np.argmax(sizes)) + 1
    water = lab == ocean_id
    log(f"ocean+bays component: {water.sum() * km2:.0f} km2", t0)

    wet = {}
    for s in (0.0, 2.0, 3.0):
        wet[s] = connected(zf < WL + s, water)
        log(
            f"wet(+{s:.0f} m): {wet[s].sum() * km2:.0f} km2, land {np.sum(wet[s] & (zf >= 0)) * km2:.0f} km2",
            t0,
        )
    lowland = connected(zf < 10.0, water)
    reach = ndimage.binary_dilation(
        wet[3.0], iterations=int(args.dilate_km * 1000 / RES)
    )
    keep_low = lowland & reach
    log(
        f"lowland(<10 m connected): {lowland.sum() * km2:.0f} km2; within {args.dilate_km:.0f} km of the +3 m sheet: "
        f"{keep_low.sum() * km2:.0f} km2",
        t0,
    )
    keep = (sk_mask | keep_low) & ~barrier
    lab, _ = ndimage.label(keep, structure=S8)
    ids = np.unique(lab[water & keep])
    ids = ids[ids > 0]
    # everything connected to the ocean through `keep` — the biggest id is the ocean
    main_id = ids[np.argmax([np.sum(lab == i) for i in ids])]
    region = lab == main_id
    dropped = keep & ~region
    log(
        f"region raster: {region.sum() * km2:.0f} km2 (sketch {sk_mask.sum() * km2:.0f}); "
        f"dropped {dropped.sum() * km2:.0f} km2 of sketch/lowland not connected to the ocean",
        t0,
    )

    # polygonise, buffer, simplify, re-clip upstream of the cuts
    polys = [
        shape(g)
        for g, v in shapes(region.astype("uint8"), mask=region, transform=T)
        if v == 1
    ]
    ring = unary_union(polys)
    if isinstance(ring, MultiPolygon):
        ring = max(ring.geoms, key=lambda g: g.area)
    ring = Polygon(
        ring.exterior
    )  # drop holes: interior high ground is cheap and harmless
    ring = ring.buffer(args.buf, join_style=2).simplify(
        args.tol, preserve_topology=True
    )
    ring = Polygon(ring.exterior)
    # re-clip: the buffer bled <= BUF past each cut; subtract every upstream zone so the
    # ring edge lies exactly on the cut lines
    clipped = ring.difference(zone_union)
    if isinstance(clipped, MultiPolygon):
        clipped = max(clipped.geoms, key=lambda g: g.area)
    ring = Polygon(clipped.exterior)
    n_v = len(ring.exterior.coords)
    for name, ln in cut_lines.items():
        d = np.array(
            [
                ring.exterior.distance(ln.interpolate(f, normalized=True))
                for f in np.linspace(0.02, 0.98, 25)
            ]
        )
        if d.max() > RES:
            log(f"  ⚠️ {name}: ring edge is up to {d.max():.0f} m off the cut line", t0)
    jb = (
        gpd.GeoSeries(
            [
                Polygon(
                    [(-73.93, 40.58), (-73.75, 40.58), (-73.75, 40.66), (-73.93, 40.66)]
                )
            ],
            crs=4326,
        )
        .to_crs(CRS)
        .iloc[0]
    )
    jb_mask = rasterize(
        [(jb, 1)], out_shape=(H, W), transform=T, fill=0, dtype="uint8"
    ).astype(bool)
    ring_mask0 = rasterize(
        [(ring, 1)], out_shape=(H, W), transform=T, fill=0, dtype="uint8"
    ).astype(bool)
    log(
        f"Jamaica Bay water inside the draft: {np.sum(ring_mask0 & jb_mask & (zf < 0)) * km2:.1f} km2 (want 0)",
        t0,
    )
    log(
        f"draft ring: {ring.area / 1e6:.0f} km2, {n_v} vertices (sketch {len(sk.exterior.coords)})",
        t0,
    )
    ring_mask = rasterize(
        [(ring, 1)], out_shape=(H, W), transform=T, fill=0, dtype="uint8"
    ).astype(bool)
    comp = {
        "water(<0)": np.sum(ring_mask & (zf < 0)),
        "land 0-10 m": np.sum(ring_mask & (zf >= 0) & (zf < 10)),
        "land >=10 m": np.sum(ring_mask & (zf >= 10)),
        "NoData": np.sum(ring_mask & nodata_mask),
    }
    composition = " | ".join(f"{k} {v * km2:.0f} km2" for k, v in comp.items())
    log("draft composition: " + composition, t0)

    # ── crossing check ─────────────────────────────────────────────────────────────
    def sample(mask_or_arr, ln, step=25.0):
        d = np.arange(0, ln.length, step)
        p = [ln.interpolate(s) for s in d]
        c = np.array([((pt.x - x0) / RES, (y1 - pt.y) / RES) for pt in p])
        col = np.clip(c[:, 0].astype(int), 0, W - 1)
        row = np.clip(c[:, 1].astype(int), 0, H - 1)
        return mask_or_arr[row, col]

    gauges = gpd.GeoDataFrame(
        [dict(id=g[0], name=g[1], cfs=g[4]) for g in GAUGES],
        geometry=[Point(g[2], g[3]) for g in GAUGES],
        crs=4326,
    ).to_crs(CRS)
    rows = []
    lines = []
    for name, coords, kind, note in CUTS:
        ln = cut_lines[name]
        zz = sample(zf, ln)
        near = ndimage.binary_dilation(
            rasterize(
                [(ln, 1)], out_shape=(H, W), transform=T, fill=0, dtype="uint8"
            ).astype(bool),
            iterations=4,
        )  # 200 m
        # wet width = the longer of the two sides' wet runs, sampled 75 m off the line
        # (the barrier itself is dry by construction, so sample beside it)
        wet_w = {
            s: float(
                max(
                    np.sum(sample(wet[s], ln.parallel_offset(RES * 1.5, "right"))),
                    np.sum(sample(wet[s], ln.parallel_offset(RES * 1.5, "left"))),
                )
                * 25
                / 1000
            )
            for s in (0.0, 2.0, 3.0)
        }
        d = gauges.distance(ln)
        gi = int(np.argmin(d.values))
        e0 = ln.coords[0]
        e1 = ln.coords[-1]
        z_ends = [
            float(zf[int((y1 - e[1]) / RES), int((e[0] - x0) / RES)]) for e in (e0, e1)
        ]
        row = dict(
            name=name,
            kind=kind,
            z_end0=round(z_ends[0], 1),
            z_end1=round(z_ends[1], 1),
            length_km=round(ln.length / 1000, 1),
            z_min=round(float(np.nanmin(zz)), 1),
            z_mean=round(float(np.nanmean(zz)), 1),
            channel_km=round(float(np.sum(zz < 0)) * 25 / 1000, 2),
            motf_touch=bool((motf & near).any()),
            wet0_km=round(wet_w[0.0], 2),
            wet2_km=round(wet_w[2.0], 2),
            wet3_km=round(wet_w[3.0], 2),
            nearest_gauge=f"{gauges.id[gi]} {gauges.name[gi]}",
            gauge_km=round(float(d.values[gi]) / 1000, 1),
            in_draft=bool(ring.intersects(ln)),
            note=note,
        )
        rows.append(row)
        lines.append(ln)
    cuts = gpd.GeoDataFrame(rows, geometry=lines, crs=CRS)

    # NACCS coverage of forced lines
    forced = [(n, cut_lines[n]) for n, c, k, _ in CUTS if k == "forced"] + [
        (n, to_utm(c)) for n, c in FORCED_EXISTING
    ]
    try:
        ml = gpd.read_file(CONTEXT, layer="mouth_line").to_crs(CRS)
        forced.append(("delaware_mouth", unary_union(ml.geometry)))
    except Exception as e:  # noqa: BLE001
        log(f"mouth_line layer not read: {e}", t0)
    frows = []
    for n, ln in forced:
        near = pts[pts.distance(ln) < 1500]
        frows.append(
            dict(
                name=n,
                naccs_pts_within_1500m=int(len(near)),
                sandy_peak_min=float(
                    near.sandy_max_m_msl[near.sandy_max_m_msl > -100].min()
                )
                if len(near)
                else np.nan,
                sandy_peak_max=float(near.sandy_max_m_msl.max())
                if len(near)
                else np.nan,
            )
        )
    fl = gpd.GeoDataFrame(frows, geometry=[ln for _, ln in forced], crs=CRS)

    # v3 inflow points (where v3 injected discharge = where its ring crossed each river)
    import xarray as xr

    dset = xr.open_dataset(V3_INFLOWS)
    irows, ipts = [], []
    for i in range(dset.sizes["index"]):
        p = (
            gpd.GeoSeries([Point(float(dset.lon[i]), float(dset.lat[i]))], crs=4326)
            .to_crs(CRS)
            .iloc[0]
        )
        col = int((p.x - x0) / RES)
        row = int((y1 - p.y) / RES)
        sl = (slice(max(row - 4, 0), row + 5), slice(max(col - 4, 0), col + 5))
        irows.append(
            dict(
                site=int(dset["index"][i]),
                qmax_m3s=round(float(dset.discharge[:, i].max()), 1),
                z=round(float(zf[row, col]), 1),
                wet3_within_200m=bool(wet[3.0][sl].any()),
                motf_within_200m=bool(motf[sl].any()),
                in_draft_interior=bool(ring.contains(p)),
                dist_to_draft_edge_km=round(ring.exterior.distance(p) / 1000, 2),
            )
        )
        ipts.append(p)
    inflows = gpd.GeoDataFrame(irows, geometry=ipts, crs=CRS)

    # ── write ───────────────────────────────────────────────────────────────────────
    def polys_of(mask, tol=RES):
        gs = [
            shape(g)
            for g, v in shapes(mask.astype("uint8"), mask=mask, transform=T)
            if v == 1
        ]
        return gpd.GeoDataFrame(geometry=[unary_union(gs).simplify(tol)], crs=CRS)

    gpkg = OUT / "v4_draft.gpkg"
    if gpkg.exists():
        gpkg.unlink()
    gpd.GeoDataFrame(
        {
            "name": ["region_v4_DRAFT"],
            "vertices": [n_v],
            "km2": [round(ring.area / 1e6)],
        },
        geometry=[ring],
        crs=CRS,
    ).to_file(gpkg, layer="draft_ring", driver="GPKG")
    sketch.to_file(gpkg, layer="sketch", driver="GPKG")
    cuts.to_file(gpkg, layer="cuts", driver="GPKG")
    fl.to_file(gpkg, layer="naccs_forced_lines", driver="GPKG")
    inflows.to_file(gpkg, layer="v3_inflows", driver="GPKG")
    polys_of(lowland).to_file(gpkg, layer="lowland10", driver="GPKG")
    for s in (0.0, 2.0, 3.0):
        polys_of(wet[s]).to_file(gpkg, layer=f"wet{int(s)}", driver="GPKG")
    polys_of(motf).to_file(gpkg, layer="motf", driver="GPKG")
    polys_of(nodata_mask & region).to_file(gpkg, layer="nodata_in_draft", driver="GPKG")
    gpd.GeoDataFrame(
        {
            "name": ["region_v4_DRAFT"],
            "note": [
                f"drafted {time.strftime('%Y-%m-%d')} by scripts/draft_region_v4.py from v4_region_first_edit.geojson; "
                f"rules: +10 m inland edge, far banks computed, cuts at head of tide; buf {args.buf:.0f} tol {args.tol:.0f}"
            ],
        },
        geometry=[ring],
        crs=CRS,
    ).to_crs(4326).to_file(DATA / "region_v4_DRAFT.geojson", driver="GeoJSON")

    with open(OUT / "v4_draft_checks.txt", "w") as f:
        f.write(
            f"v4 draft ring: {ring.area / 1e6:.0f} km2, {n_v} vertices; sketch {sk.area / 1e6:.0f} km2\n"
        )
        f.write(
            f"NoData elevation inside the draft: {np.sum(nodata_mask & region) * km2:.0f} km2\n"
        )
        f.write(f"composition: {composition}\n")
        f.write(
            f"land the sketch left out that the +3 m sheet wets: "
            f"{np.sum(wet[3.0] & (zf >= 0) & ~sk_mask) * km2:.0f} km2; MOTF outside the sketch: "
            f"{np.sum(motf & ~sk_mask) * km2:.0f} km2; MOTF outside the DRAFT: {np.sum(motf & ~ring_mask) * km2:.0f} km2\n\n"
        )
        f.write(
            "CUTS (wet*_km = wet width along the line for the +0/+2/+3 m sheets; a 'cut' should be 0)\n"
        )
        f.write(cuts.drop(columns="geometry").to_string(index=False) + "\n\n")
        f.write(
            "FORCED LINES vs NACCS points\n"
            + fl.drop(columns="geometry").to_string(index=False)
            + "\n\n"
        )
        f.write(
            "v3 INFLOW POINTS (v3 injected discharge here; in v4 the source moves to the gauge if the cut moved)\n"
        )
        f.write(inflows.drop(columns="geometry").to_string(index=False) + "\n")
    print(open(OUT / "v4_draft_checks.txt").read())

    # overview figure
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(11, 13))
        ax.imshow(
            np.where(zf < 0, 0, np.minimum(zf, 12)),
            extent=(x0, x1, y0, y1),
            cmap="terrain",
            vmin=-4,
            vmax=14,
            alpha=0.6,
        )
        for s, c in ((3.0, "#9ecae1"), (0.0, "#3182bd")):
            m = wet[s] & (zf >= 0)
            ax.contourf(
                np.arange(W) * RES + x0 + RES / 2,
                y1 - np.arange(H) * RES - RES / 2,
                m.astype(float),
                levels=[0.5, 1.5],
                colors=[c],
                alpha=0.8,
            )
        ax.contour(
            np.arange(W) * RES + x0 + RES / 2,
            y1 - np.arange(H) * RES - RES / 2,
            motf.astype(float),
            levels=[0.5],
            colors="red",
            linewidths=0.4,
        )
        sketch.boundary.plot(
            ax=ax, color="k", linewidth=0.8, linestyle="--", label="sketch"
        )
        gpd.GeoSeries([ring.exterior], crs=CRS).plot(
            ax=ax, color="magenta", linewidth=1.2, label="draft"
        )
        cuts.plot(ax=ax, color="orange", linewidth=2)
        for _, r in cuts.iterrows():
            c = r.geometry.centroid
            ax.annotate(r["name"], (c.x, c.y), fontsize=6, color="darkorange")
        ax.set_title(
            "v4 draft ring (magenta) vs sketch (dashed); blue = Sandy / Sandy+3 m bathtub on land; red = MOTF"
        )
        ax.set_aspect("equal")
        ax.legend(loc="lower right")
        (ROOT / "reports" / "figures").mkdir(parents=True, exist_ok=True)
        fig.savefig(
            ROOT / "reports" / "figures" / "v4_draft_ring.png",
            dpi=150,
            bbox_inches="tight",
        )
        ax.set_xlim(545_000, 600_000)
        ax.set_ylim(4_470_000, 4_505_000)
        ax.set_title("v4 draft — NY corner (Goethals / Rahway / Brooklyn / Rockaway)")
        fig.savefig(
            ROOT / "reports" / "figures" / "v4_draft_ring_ny.png",
            dpi=150,
            bbox_inches="tight",
        )
        log("figure written", t0)
    except Exception as e:  # noqa: BLE001
        log(f"figure skipped: {e}", t0)
    log("done", t0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
