#!/usr/bin/env python
"""v4 river beds where no survey reaches: one 5 m carving raster per reach + a VRT.

    python scripts/build_riverbeds_v4.py fetch     # network: NHD outlines, VDatum MLLW
    python scripts/build_riverbeds_v4.py build     # rasters (no network)

WHY. Above the last federal survey the lidar DEMs hold the WATER SURFACE, not the bed
(CUDEM reads +3.7 m high on the Passaic, +8.5 m on the Hackensack; the Delaware above
the falls and the Raritan above New Brunswick have no bathymetry at all — STATUS
RIVERBEDS). Decisions (user, 2026-09-27): the Passaic / Hackensack take the NOAA chart
soundings (ENC; the upper Passaic's are a 2004 USACE survey) and a uniform depth above
them; the non-tidal reaches take a uniform depth below the lidar surface, rebuilt when
the DRBC bathymetry arrives.

HOW, per reach (``REACHES``):
  * the CHANNEL is the NHD Area (large scale, FType 460 StreamRiver) polygon the
    centreline runs through, inside the reach box and within 300 m of the centreline;
    the CENTRELINE is the NHD flowline of the named river, merged.
  * every bed value is a function of distance ALONG the centreline (a 1-D profile), then
    painted across the channel — a flat cross-section. 2-D interpolation between sparse
    soundings leaks across meander bends; a profile cannot.
  * ``soundings``: points within 150 m of the channel, stationed on the centreline, a
    running median over ±``window_m``; ``tail_mllw_m`` then continues it UPSTREAM of the
    last sounding as that depth below MLLW (VDatum MLLW → NAVD88 along the line).
  * ``surface``: the low decile of 3DEP 1/3" water pixels per 100 m of centreline (robust
    to bank pixels caught in the polygon), running median, minus ``depth_m``. Bins whose
    surface is blank (3DEP blanks water ≤ 0: tidal) get no burn.
  * ``skip_below_m``: leave pixels alone where the named tier already holds a real bed
    deeper than this (the Delaware's CUDEM is a real bed to the falls, ~40.21).

Output (``build``): data/elevation_v4/riverbeds/riverbed_<reach>_v4.tif (EPSG:32618,
5 m, NoData −9999 off-channel) + riverbeds_v4.vrt + riverbeds_v4_profiles.csv (the
profile of every reach, for review). Datum: m NAVD88.
⚠️ Chart soundings are SHOAL-BIASED (a chart keeps the shallowest); H05647 (1934) reads
~1.2 m shallow in the dredged channel. Both read the bed HIGH if anything.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RB = DATA / "elevation_v4" / "riverbeds"
ENC = DATA / "elevation_v4" / "enc" / "raw"
H05647 = DATA / "elevation_v4" / "nos_hydro" / "nos_H05647_v4_points.csv"
DEP3 = sorted((DATA / "elevation_v4" / "3dep").glob("USGS_13_*.tif"))
#: The real-bed check for ``skip_below_m``: BOTH CUDEM sets — the Delaware tiles stop at
#: lon -75.00, and Trenton (-74.76) is on the NJ ones (a first build read only the
#: Delaware set and painted over the real bed below the falls).
CUDEM = (
    DATA / "elevation_v4" / "cudem_delaware_v4.vrt",
    DATA / "elevation_v3" / "cudem_nj_v3.vrt",
)

NHD = "https://hydro.nationalmap.gov/arcgis/rest/services/nhd/MapServer"
VDATUM = (
    "https://vdatum.noaa.gov/vdatumweb/api/convert?s_x={x:.6f}&s_y={y:.6f}&s_z=0"
    "&region=contiguous&s_coor=geo&s_h_frame=NAD83_2011&s_v_frame=MLLW&s_v_unit=m"
    "&t_h_frame=NAD83_2011&t_v_frame=NAVD88&t_v_unit=m"
)
RES = 5.0
NODATA = -9999.0
EPSG = 32618
#: Paint no further than this from the centreline (the tidal Raritan is ~600 m wide).
MAX_HALFWIDTH_M = 300.0


@dataclass(frozen=True)
class Reach:
    name: str
    box: tuple[float, float, float, float]  # lon/lat
    river: str  # NHD gnis_name of the centreline
    head: tuple[float, float]  # a lon/lat near the UPSTREAM end (orients stations)
    mode: str  # "soundings" | "surface"
    why: str
    depth_m: float | None = None  # surface: depth below the lidar surface
    points: str | None = None  # soundings: "enc" | "h05647"
    window_m: float = 300.0
    tail_mllw_m: float | None = None  # soundings: depth below MLLW upstream of the last
    skip_below_m: float | None = None  # leave pixels where CUDEM is deeper than this


REACHES = (
    Reach(
        "delaware_above_falls",
        (-74.90, 40.195, -74.74, 40.30),
        "Delaware River",
        (-74.86, 40.28),
        "surface",
        depth_m=1.20,
        skip_below_m=-1.5,
        why="User 09-27: uniform depth until the DRBC bathymetry. 1.20 m = Trenton "
        "01463500, median mean depth (area/width) of 296 channel measurements at flows "
        "p25–p75 (p10 0.98, p90 1.54). CUDEM keeps its real bed below the falls.",
    ),
    Reach(
        "raritan_above_new_brunswick",
        (-74.60, 40.47, -74.435, 40.58),
        "Raritan River",
        (-74.575, 40.555),
        "surface",
        depth_m=0.55,
        why="Uniform depth: Manville 01400500 median 0.47 m (n 399), Bound Brook "
        "01403060 0.59 m (n 361), flows p25–p75. Gauge sections sit on riffles, so "
        "pools read deeper — the ±0.5 m sensitivity covers it.",
    ),
    Reach(
        "raritan_h05647",
        (-74.445, 40.46, -74.305, 40.53),
        "Raritan River",
        (-74.44, 40.49),
        "soundings",
        points="h05647",
        window_m=200.0,
        why="NOS H05647 (1934 lead line, MLW, epoch-corrected; 4,783 pts) — the only "
        "measured bed west of CoNED's clip (-74.312) to New Brunswick. ⚠️ ~1.2 m "
        "SHALLOW in the dredged channel vs the 2012 survey where they overlap.",
    ),
    Reach(
        "passaic_charted",
        (-74.20, 40.735, -74.10, 40.892),
        "Passaic River",
        (-74.13, 40.888),
        "soundings",
        points="enc",
        tail_mllw_m=1.2,
        why="NOAA ENC soundings (2004 USACE DD-15654 to 40.85, chart 12337 above), "
        "MLLW → NAVD88 by VDatum; above the last sounding (40.866) to Dundee Dam, "
        "1.2 m below MLLW — the chart's own last-2-km depth. eHydro (to 40.779) "
        "outranks this tier.",
    ),
    Reach(
        "hackensack_charted",
        (-74.10, 40.735, -73.98, 40.956),
        "Hackensack River",
        (-74.02, 40.95),
        "soundings",
        points="enc",
        tail_mllw_m=1.2,
        why="NOAA ENC soundings (mostly carried from paper chart 12337, W-355 2014, "
        "H03725 1915), MLLW → NAVD88 by VDatum; above the last sounding (40.891) to "
        "the Oradell dam, 1.2 m below MLLW. eHydro (to 40.751) outranks this tier. "
        "The reservoir above the dam keeps its lidar surface.",
    ),
)


# ── helpers ───────────────────────────────────────────────────────────────────
def _get(url: str, tries: int = 5) -> bytes:
    for k in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=180) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            if k == tries - 1:
                raise
            print(f"    retry {k + 1} ({e})")
            time.sleep(5 * (k + 1))
    raise RuntimeError("unreachable")


def _atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def _nhd(layer: int, where: str, box) -> bytes:
    q = {
        "where": where,
        "geometry": ",".join(map(str, box)),
        "geometryType": "esriGeometryEnvelope",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "gnis_name,ftype",
        "outSR": 4326,
        "f": "geojson",
    }
    return _get(f"{NHD}/{layer}/query?" + urllib.parse.urlencode(q))


def fetch() -> None:
    import geopandas as gpd

    for r in REACHES:
        a = RB / f"nhd_area_{r.name}.geojson"
        f = RB / f"nhd_flowline_{r.name}.geojson"
        if not a.exists():
            _atomic_bytes(a, _nhd(9, "ftype=460", r.box))
        if not f.exists():
            name = r.river.replace("'", "''")
            _atomic_bytes(f, _nhd(6, f"gnis_name='{name}'", r.box))
        na, nf = len(gpd.read_file(a)), len(gpd.read_file(f))
        print(f"{r.name}: NHD {na} area polygons, {nf} flowline pieces")
        if r.points == "enc" or r.tail_mllw_m is not None:
            _vdatum_nodes(r)


def _vdatum_nodes(r: Reach) -> None:
    """MLLW−NAVD88 (m) at ~25 nodes along the reach centreline; cached."""
    out = RB / f"vdatum_mllw_{r.name}.csv"
    if out.exists():
        return
    line = _centreline(r)
    import geopandas as gpd

    pts = gpd.GeoSeries(
        [line.interpolate(d) for d in np.linspace(0, line.length, 25)], crs=EPSG
    ).to_crs(4326)
    rows = ["lon,lat,mllw_navd88_m"]
    for p in pts:
        d = json.loads(_get(VDATUM.format(x=p.x, y=p.y)))
        z = float(d.get("t_z", -999999))
        rows.append(f"{p.x:.6f},{p.y:.6f},{z if z > -1e5 else 'nan'}")
        time.sleep(0.3)
    _atomic_bytes(out, ("\n".join(rows) + "\n").encode())
    print(f"    VDatum MLLW: {len(rows) - 1} nodes -> {out.name}")


# ── build ─────────────────────────────────────────────────────────────────────
def _centreline(r: Reach):
    """The named river's NHD flowline in the box, merged; longest piece; UTM;
    oriented so station 0 is the DOWNSTREAM end (head = the far end)."""
    import geopandas as gpd
    import shapely
    from shapely.ops import linemerge

    g = gpd.read_file(RB / f"nhd_flowline_{r.name}.geojson").to_crs(EPSG)
    g = g.clip(gpd.GeoSeries([shapely.box(*r.box)], crs=4326).to_crs(EPSG).iloc[0])
    merged = linemerge(shapely.union_all(g.geometry.values))
    parts = list(getattr(merged, "geoms", [merged]))
    line = max(parts, key=lambda p: p.length)
    head = gpd.GeoSeries([shapely.Point(r.head)], crs=4326).to_crs(EPSG).iloc[0]
    if head.distance(shapely.Point(line.coords[0])) < head.distance(
        shapely.Point(line.coords[-1])
    ):
        line = shapely.reverse(line)
    return line


def _channel(r: Reach, line):
    """The river's own NHD Area polygon(s) — only those the centreline passes through —
    within ``MAX_HALFWIDTH_M`` of the centreline, inside the reach box.

    A first build took every StreamRiver polygon in the box and painted tributary creeks
    with the main stem's profile (Passaic 6.05 km² vs 2.77 on its own polygon). NHD also
    merges the Meadowlands creeks INTO the Hackensack's polygon (10.9 km²), which only
    the half-width cap limits: a side creek keeps the main-stem depth for ≤ 300 m.
    """
    import geopandas as gpd
    import shapely

    g = gpd.read_file(RB / f"nhd_area_{r.name}.geojson").to_crs(EPSG)
    g = g[g.intersects(line.buffer(10.0))]
    box = gpd.GeoSeries([shapely.box(*r.box)], crs=4326).to_crs(EPSG).iloc[0]
    return (
        shapely.union_all(g.geometry.values)
        .intersection(box)
        .intersection(line.buffer(MAX_HALFWIDTH_M))
    )


def _enc_points(box) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """ENC SOUNDG inside ``box``: lon, lat, depth below chart datum (MLLW, m)."""
    import warnings

    import geopandas as gpd
    import shapely

    warnings.filterwarnings("ignore")
    os.environ["OGR_S57_OPTIONS"] = "SPLIT_MULTIPOINT=ON,ADD_SOUNDG_DEPTH=ON"
    lon, lat, dep = [], [], []
    seen = set()
    import pyogrio

    for f in sorted(ENC.glob("*/*.000")):
        if "SOUNDG" not in {n for n, _ in pyogrio.list_layers(f)}:
            continue
        g = gpd.read_file(f, layer="SOUNDG", engine="pyogrio")
        g = g[g.geometry.within(shapely.box(*box))]
        for p in g.geometry:
            k = (round(p.x, 6), round(p.y, 6), p.z)
            if k in seen:
                continue
            seen.add(k)
            lon.append(p.x)
            lat.append(p.y)
            dep.append(p.z)
    return np.array(lon), np.array(lat), np.array(dep)


def _mllw_along(r: Reach, line) -> tuple[np.ndarray, np.ndarray]:
    """(station, MLLW−NAVD88) nodes along the centreline; off-grid nodes dropped."""
    import geopandas as gpd

    v = np.genfromtxt(RB / f"vdatum_mllw_{r.name}.csv", delimiter=",", names=True)
    ok = np.isfinite(v["mllw_navd88_m"])
    p = gpd.points_from_xy(v["lon"][ok], v["lat"][ok], crs=4326).to_crs(EPSG)
    s = np.array([line.project(q) for q in p])
    o = np.argsort(s)
    return s[o], v["mllw_navd88_m"][ok][o]


def _running_median(s: np.ndarray, z: np.ndarray, grid: np.ndarray, half: float):
    out = np.full(grid.shape, np.nan)
    o = np.argsort(s)
    s, z = s[o], z[o]
    lo = np.searchsorted(s, grid - half)
    hi = np.searchsorted(s, grid + half)
    for i, (a, b) in enumerate(zip(lo, hi)):
        if b > a:
            out[i] = np.median(z[a:b])
    return out


def _sample(paths, x, y, crs=EPSG) -> np.ndarray:
    import rasterio
    from rasterio.warp import transform as warp_xy

    z = np.full(len(x), np.nan)
    for p in paths:
        need = np.isnan(z)
        if not need.any():
            break
        with rasterio.open(p) as s:
            xx, yy = warp_xy(f"EPSG:{crs}", s.crs, x[need].tolist(), y[need].tolist())
            v = np.array([t[0] for t in s.sample(zip(xx, yy))], dtype="float64")
            if s.nodata is not None:
                v[v == s.nodata] = np.nan
            v[np.abs(v) > 1e4] = np.nan
            z[need] = v
    return z


def profile(r: Reach, line, chan) -> tuple[np.ndarray, np.ndarray, str]:
    """Bed (m NAVD88) at 25 m stations along the centreline, and a note."""
    import geopandas as gpd
    import shapely

    grid = np.arange(0.0, line.length + 25.0, 25.0)
    if r.mode == "soundings":
        if r.points == "h05647":
            v = np.genfromtxt(
                H05647, delimiter=",", names=True, dtype=None, encoding=None
            )
            lon, lat, z = v["lon"], v["lat"], v["z_navd88"]
            src = "H05647 z_navd88"
        else:
            lon, lat, dep = _enc_points(r.box)
            ms, mz = _mllw_along(r, line)
            p = gpd.points_from_xy(lon, lat, crs=4326).to_crs(EPSG)
            s0 = np.array([line.project(q) for q in p])
            z = np.interp(s0, ms, mz) - dep
            src = "ENC depth below MLLW, VDatum"
        p = gpd.points_from_xy(lon, lat, crs=4326).to_crs(EPSG)
        near = shapely.dwithin(chan, np.asarray(p), 150.0)
        s = np.array([line.project(q) for q in np.asarray(p)[near]])
        zz = np.asarray(z)[near]
        prof = _running_median(s, zz, grid, r.window_m)
        # interior gaps between soundings: linear along the line; no extrapolation
        ok = np.isfinite(prof)
        if ok.sum() >= 2:
            inside = (grid >= grid[ok][0]) & (grid <= grid[ok][-1])
            prof[inside] = np.interp(grid[inside], grid[ok], prof[ok])
        note = (
            f"{near.sum()} soundings ({src}), stations {s.min():.0f}..{s.max():.0f} m"
        )
        if r.tail_mllw_m is not None and ok.any():
            last = grid[ok][-1]
            ms, mz = _mllw_along(r, line)
            up = grid > last
            prof[up] = np.interp(grid[up], ms, mz) - r.tail_mllw_m
            note += f"; tail {r.tail_mllw_m} m below MLLW above {last:.0f} m"
        return grid, prof, note
    # surface: low decile of 3DEP water per 100 m of centreline
    # cross-section samples: the centreline point and ±10/20 m along the local normal
    c = shapely.line_interpolate_point(line, grid)
    a = shapely.line_interpolate_point(line, np.clip(grid - 5.0, 0, line.length))
    b = shapely.line_interpolate_point(line, np.clip(grid + 5.0, 0, line.length))
    tx, ty = shapely.get_x(b) - shapely.get_x(a), shapely.get_y(b) - shapely.get_y(a)
    tn = np.hypot(tx, ty)
    tn[tn == 0] = 1.0
    nx, ny = -ty / tn, tx / tn
    offs = np.array([-20.0, -10.0, 0.0, 10.0, 20.0])
    xs = (shapely.get_x(c)[:, None] + nx[:, None] * offs).ravel()
    ys = (shapely.get_y(c)[:, None] + ny[:, None] * offs).ravel()
    ss = np.repeat(grid, len(offs))
    keep = shapely.contains_xy(chan, xs, ys)
    xs, ys, ss = xs[keep], ys[keep], ss[keep]
    zs = _sample(DEP3, xs, ys)
    ok = np.isfinite(zs)
    surf = np.full(grid.shape, np.nan)
    for i, d in enumerate(grid):
        m = ok & (np.abs(ss - d) <= 50.0)
        if m.sum() >= 3:
            surf[i] = np.percentile(zs[m], 10)
    surf = _running_median(
        grid[np.isfinite(surf)], surf[np.isfinite(surf)], grid, 150.0
    )
    prof = surf - r.depth_m
    note = f"3DEP surface p10 per 100 m, {int(np.isfinite(surf).sum())} of {len(grid)} stations"
    return grid, prof, note


def paint(r: Reach, line, chan, grid, prof) -> Path:
    import rasterio
    import shapely
    from rasterio.features import geometry_mask
    from rasterio.transform import from_origin

    x0, y0, x1, y1 = chan.bounds
    x0, y1 = np.floor(x0 / RES) * RES, np.ceil(y1 / RES) * RES
    w = int(np.ceil((x1 - x0) / RES))
    h = int(np.ceil((y1 - y0) / RES))
    T = from_origin(x0, y1, RES, RES)
    inside = ~geometry_mask([chan], (h, w), T)
    rr, cc = np.nonzero(inside)
    px = x0 + (cc + 0.5) * RES
    py = y1 - (rr + 0.5) * RES
    st = shapely.line_locate_point(line, shapely.points(px, py))
    ok = np.isfinite(prof)
    z = np.full(px.shape, np.nan)
    if ok.any():
        span = (st >= grid[ok][0]) & (st <= grid[ok][-1])
        z[span] = np.interp(st[span], grid[ok], prof[ok])
    if r.skip_below_m is not None:
        cz = _sample(CUDEM, px, py)
        z[cz < r.skip_below_m] = np.nan
    a = np.full((h, w), NODATA, dtype="float32")
    a[rr, cc] = np.where(np.isfinite(z), z, NODATA)
    out = RB / f"riverbed_{r.name}_v4.tif"
    fd, tmp = tempfile.mkstemp(dir=RB, prefix=f".{out.name}.", suffix=".tif")
    os.close(fd)
    with rasterio.open(
        tmp,
        "w",
        driver="GTiff",
        height=h,
        width=w,
        count=1,
        dtype="float32",
        crs=f"EPSG:{EPSG}",
        transform=T,
        nodata=NODATA,
        compress="deflate",
        tiled=True,
    ) as d:
        d.write(a, 1)
        d.update_tags(reach=r.name, why=r.why)
    os.replace(tmp, out)
    n = int(np.isfinite(z).sum())
    zz = z[np.isfinite(z)]
    print(
        f"  -> {out.name}: {n} px painted of {len(z)} in channel"
        + (
            f", bed {np.percentile(zz, 5):+.2f}..{np.percentile(zz, 95):+.2f} m (p5..p95)"
            if n
            else ""
        )
    )
    return out


def build() -> None:
    import subprocess

    rows = ["reach,station_m,bed_navd88_m"]
    outs = []
    for r in REACHES:
        line = _centreline(r)
        chan = _channel(r, line)
        grid, prof, note = profile(r, line, chan)
        print(
            f"{r.name}: centreline {line.length / 1000:.1f} km, channel "
            f"{chan.area / 1e6:.2f} km²; {note}"
        )
        rows += [
            f"{r.name},{s:.0f},{z:.3f}" for s, z in zip(grid, prof) if np.isfinite(z)
        ]
        outs.append(paint(r, line, chan, grid, prof))
    _atomic_bytes(RB / "riverbeds_v4_profiles.csv", ("\n".join(rows) + "\n").encode())
    vrt = RB / "riverbeds_v4.vrt"
    subprocess.run(
        [
            "gdalbuildvrt",
            "-overwrite",
            "-srcnodata",
            str(NODATA),
            "-vrtnodata",
            str(NODATA),
            str(vrt),
            *map(str, outs),
        ],
        check=True,
    )
    print(f"wrote {vrt}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("stage", choices=["fetch", "build"])
    a = ap.parse_args()
    RB.mkdir(parents=True, exist_ok=True)
    fetch() if a.stage == "fetch" else build()
    return 0


if __name__ == "__main__":
    sys.exit(main())
