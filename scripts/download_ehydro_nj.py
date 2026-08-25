#!/usr/bin/env python3
"""Build the eHydro CARVING TIER — federal channel surveys that un-pave the lidar.

WHY THIS TIER EXISTS
--------------------
`usace_nj_2010` (1 m pre-Sandy topobathy lidar) is the TOP entry in
`DEFAULT_ELEVATION_LIST`, because in clear shallow water its green lidar returns the real
bed. But in deep or turbid water it fails to penetrate and returns the **water surface**
instead — ~0 to +2 m, indistinguishable from ordinary land. Ranked first, those bogus
returns shadow CUDEM's correct bed underneath, and where it happens across a channel the
channel is **sealed shut**.

That is what dammed Shark River Inlet. Real bed (eHydro soundings): −4.6 to −10.8 m. Lidar:
+0.4 to +2.2 m. CUDEM: −2.2 to −4.5 m, correct, and never consulted. Result: the entire
Shark River estuary **never floods in any run of this project — peak water level exactly
+0.00 m, its initial condition — while the ocean 1.8 km away reaches +2.9 m.** It is not a
bridge: the dam's western edge is exactly the edge of the lidar tile's coverage.

An eHydro condition survey is a boat with an echo sounder. It is the only source here that
directly measures the bed *under* the water, so it is the only thing that can outrank the
lidar. It goes ON TOP.

WHICH SURVEYS
-------------
Chosen by `scripts/audit_paved_channels.py`, which screens the whole domain for "model says
land, CUDEM says >2 m of water" and then arbitrates each candidate by asking whether a boat
actually sounded WATER at those cells. That audit's verdict was mostly NEGATIVE, and usefully
so — the Sea Bright revetment patches were rejected (soundings there read +2.4 m: the seawall
is real and the 1 m lidar has it right), Sandy Hook Channel was rejected (the patches sit on
the spit, not the channel), and the Shrewsbury is already carved. **Shark River Inlet is
essentially the only genuine paving in the domain.**

THE WATER-ONLY CLIP (the safety rail)
-------------------------------------
This tier is a CARVING tier, not a general DEM. It supplies values only where it says WATER
(z < ``WATER_MAX``); everywhere else it is NoData and the normal tiers show through. That is
what makes it impossible for a survey to accidentally flatten a structure: a beach or
shore-protection survey that happens to cover the revetment reports +2.4 m there, which is
clipped out, so the seawall can never be carved away by this file. Given the revetment is a
knife edge in this model (storm tide lands ON it, 59–75% overtopped), that rail is not
optional.

PROCESSING (unchanged from the proven Shrewsbury chain)
-------------------------------------------------------
  1. horizontal  EPSG:3424 (NAD83 / NJ State Plane, US survey ft) -> EPSG:32618 (UTM18N, m)
  2. vertical    MLLW ft -> NAVD88 m via the NOAA VDatum REST API. The separation is NOT
                 constant (−0.45 m south to −0.84 m north over the Shrewsbury footprint — a
                 0.39 m gradient that matters at channel-depth precision), so we query VDatum
                 at ~N_VDATUM thinned sounding locations, cache them, and interpolate the
                 offset FIELD onto every point.
  3. rasterise   linear (Delaunay) interpolation onto a 5 m UTM18N grid, then MASK to the
                 survey's `Bathymetry_Vector` coverage polygons, then apply the water-only
                 clip -> NoData everywhere except real surveyed channel bed.

OUTPUT: data/elevation/ehydro_nj.tif   (5 m, UTM18N, NAVD88 m, NoData off-channel)

Run:  NJ_ROOT=$PWD PYTHONPATH=$PWD micromamba/envs/sfincs/bin/python scripts/download_ehydro_nj.py
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ELEV = ROOT / "data" / "elevation"

#: ⚠️ `data/elevation` is a SYMLINK into the frozen archive and is READ-ONLY. The `nj`
#: preset below is therefore a RECORD of how `ehydro_nj.tif` was made, not something that
#: can be re-run in place — it would have to write into the archive. Anything new goes to
#: `data/elevation_<domain>/`, a real local directory — resolved through
#: `nj_sfincs.domain.acquisition_dir` so a new domain cannot inherit v1.5's.
#: ⚠️ The v1.5 presets keep the literal path: they are a RECORD of files that already
#: exist, and re-pointing them at the active domain would make the record lie.
ELEV_LOCAL = ROOT / "data" / "elevation_v1_5"

#: Presets: (surveys, output raster, raw-cache dir, title).
#: A survey is (id, channel, USACE district).
#:
#: 🔴 SELECT SURVEYS BY FOOTPRINT, NEVER BY CHANNEL NAME. The surveys actually *called*
#: "Arthur Kill" (`NJ_04_AKS_*`) start at lat 40.521 — NORTH of the v1.5 Arthur Kill mouth
#: cut at 40.504 — and never touch it. The mouth is surveyed under "Seguin Pt.-Ward
#: Pt.-Outerbridge" and "Perth Amboy Anch & 2nd Chnl". Picking on the name would have
#: carved the wrong reach and looked like a success.
#: 🔴 SIGN IS A DISTRICT FACT. New York (CENAN) XYZ files carry signed elevations below
#: the plane (negative = deeper); Philadelphia (CENAP) ships POSITIVE DEPTHS (measured
#: 2026-08-24 on CM_01_CMC_20150319_CS: Z = +0.18..+38.3 ft). A preset's 5th element is
#: the multiplier that turns its Z into "elevation relative to the plane"; the two
#: CENAN presets predate it and default to +1 in main().
PRESETS: dict[str, tuple] = {
    # v3 southern channels (2026-08-24). CENAP surveys nearest Sandy are all 2015
    # (+865..+877 d) — there is nothing closer; the alternative tier is CUDEM, which is
    # post-Sandy too. Federal channels only: Great Egg, Townsends and Hereford inlets are
    # unsurveyed. Barnegat Inlet is already in ehydro_south (archived tier).
    "south_v3": (
        [
            ("CM_01_CMC_20150319_CS", "Cape May Canal", "CENAP"),
            ("CS_02_CMH_20150313_CS", "Cold Spring Inlet (Cape May Inlet)", "CENAP"),
            ("AI_01_AIE_20150325_CS", "Absecon Inlet", "CENAP"),
        ],
        ROOT / "data" / "elevation_v3" / "ehydro_south_v3.tif",
        ROOT / "data" / "elevation_v3" / "ehydro" / "raw",
        "v3 southern inlet + canal carving tier (Philadelphia district, +depth)",
        -1.0,
    ),
    # The frozen v1_monmouth carving tier. Verdicts from scripts/audit_paved_channels.py
    # (2026-07-14). Shrewsbury (NJ_14_SNR_20150902_CS_4368_15) is deliberately NOT here:
    # it ships as its own tier, `shrewsbury_ehydro_2015`, from the bridge-as-dam fix.
    "nj": (
        [("NJ_10_SRI_20150902_CS_4383_15", "Shark River Inlet", "CENAN")],
        ELEV / "ehydro_nj.tif",
        ELEV / "ehydro" / "raw",
        "v1_monmouth open-coast carving tier (FROZEN — read-only target)",
    ),
    # v1.5's two western forced cuts, where CUDEM has no tile at all west of lon -74.25
    # and the merged bed otherwise falls through to gmrt_nj (~50 m). One survey per cut,
    # chosen as the survey NEAREST SANDY that actually reaches the cut.
    "raritan": (
        [
            # +654 d. The nearest-Sandy survey whose footprint reaches the Arthur Kill
            # MOUTH cut; covers 0.255 km of its 0.684 km wet width (37%). Perth Amboy
            # Anch (NJ_02_PAA_20130502, +185 d) is closer in time but does not reach it.
            ("NJ_03_SWO_20140814_CS_4160_45X", "Seguin Pt.-Ward Pt.-Outerbridge", "CENAN"),
            # -95 d — PRE-Sandy. Covers 0.049 km of the Raritan cut's 0.342 km wet width
            # (14%): the dredged channel only, which is where the flow is.
            ("RR_01_RAR_20120726_CS_3844_15X", "Raritan River w/Spur Channel", "CENAN"),
        ],
        ELEV_LOCAL / "ehydro_raritan_ak.tif",
        ELEV_LOCAL / "ehydro" / "raw",
        "v1_5_raritan Arthur Kill mouth + Raritan River carving tier",
    ),
}

ZIP_URL = ("https://ehydroprod.blob.core.usgovcloudapi.net/"
           "ehydro-surveys/{district}/{sid}.ZIP")

EPSG_SRC = 3424      # NAD83 / NJ State Plane (US survey foot)
EPSG_DST = 32618     # WGS84 / UTM 18N (metre) -- model CRS
FT_TO_M = 0.3048006096012192

RES = 5.0            # output raster resolution (m) ~ the sounding spacing
N_VDATUM = 250       # thinned VDatum query nodes per survey (cached)
WATER_MAX = -1.0     # the carving clip: this tier only ever supplies REAL WATER

NODATA = np.float32(-9999.0)


def fetch(sid: str, district: str, raw: Path) -> Path:
    raw.mkdir(parents=True, exist_ok=True)
    zp = raw / f"{sid}.ZIP"
    if not zp.exists():
        url = ZIP_URL.format(district=district, sid=sid)
        print(f"  downloading {url}")
        urllib.request.urlretrieve(url, zp)
    out = raw / sid
    if not out.exists():
        with zipfile.ZipFile(zp) as z:
            z.extractall(out)
    return out


def _one(d: Path, *exts: str) -> Path:
    """The single member with one of these extensions, case-insensitively.

    eHydro is not consistent about case (`.XYZ` vs `.xyz`) across districts and years.
    """
    hits = [f for f in d.iterdir()
            if f.suffix.lower() in {e.lower() for e in exts}]
    if len(hits) != 1:
        raise SystemExit(f"🔴 {d.name}: expected 1 {exts} member, found {len(hits)}")
    return hits[0]


def read_xyz(path: Path) -> np.ndarray:
    """Soundings from an eHydro XYZ, skipping its NOTES/BENCHMARKS/PROJECT_NAME header.

    Older surveys ship a bare x/y/z triple per line; newer ones prepend a metadata block,
    so `np.loadtxt` cannot be used directly.
    """
    rows = []
    for ln in path.read_text(errors="replace").splitlines():
        f = ln.split()
        if len(f) < 3:
            continue
        try:
            rows.append((float(f[0]), float(f[1]), float(f[2])))
        except ValueError:
            continue
    if not rows:
        raise SystemExit(f"🔴 {path.name}: no numeric soundings found")
    return np.asarray(rows)


def stated_offset_m(path: Path) -> float | None:
    """The survey's OWN reduction plane, in metres NAVD88, parsed from its header.

    🔴 The sounding datum is a PER-SURVEY fact and is not always MLLW. Of the two v1.5
    surveys, `RR_01_RAR` is on MEAN LOWER LOW WATER (2.9-3.0 ft below NAVD88) while
    `NJ_03_SWO` is on **C.O.E. MEAN LOW WATER** (3.5 ft below NAVD88) — a different plane.
    Converting both with a VDatum MLLW query would put a systematic ~0.17 m error into the
    Arthur Kill cut, so prefer what the survey states about its own reduction; VDatum is
    the fallback for surveys that state nothing.

    A "2.9-3.0" style range is the survey's own spatial spread and is averaged (0.03 m
    wide here, versus the 0.39 m gradient that made the VDatum field necessary elsewhere).
    """
    txt = path.read_text(errors="replace")[:8000]
    m = re.search(
        r"PLANE OF [A-Z. ]*?MEAN LOW(?:ER LOW)? WATER (?:IS|WAS)[^0-9]*"
        r"([0-9]+(?:\.[0-9]+)?)(?:\s*-\s*([0-9]+(?:\.[0-9]+)?))?\s*FEET\s+(BELOW|ABOVE)",
        txt, re.I)
    if not m:
        return None
    lo = float(m.group(1))
    ft = (lo + float(m.group(2))) / 2 if m.group(2) else lo
    if m.group(3).upper() == "BELOW":
        ft = -ft
    return ft * FT_TO_M


#: 🔴 VDatum's web API is BROKEN south of Barnegat (2026-08-24): `region=contiguous`
#: returns "Uncaught error" for every point tested at Cape May and Great Egg, every
#: named regional grid returns "Input Region is not correct", and the /regions endpoint
#: is a 404 — while the same query at the Arthur Kill still answers. The CENAP XYZ files
#: state no plane in their header (bare x y z from line 1). So for these surveys the
#: sounding plane is the MLLW-NAVD88 datum of the nearest NOAA station, from the CO-OPS
#: metadata API (mdapi .../stations/<id>/datums.json, feet, epoch 1983-2001):
#:   8536110 Cape May (on the canal's bay mouth):  MLLW 2.42 ft, NAVD88 5.44 ft -> -3.02 ft
#:   8534720 Atlantic City (Steel Pier):            MLLW 4.96 ft, NAVD88 7.57 ft -> -2.61 ft
#: A single station offset ignores the along-channel gradient the VDatum field was built
#: to capture; over a 5 km canal between two ~1.4 m-range basins that is small, and it is
#: declared here rather than hidden in a NaN.
STATION_PLANE_M: dict[str, tuple[float, str]] = {
    "CM_01_CMC_20150319_CS": (-3.02 * 0.3048, "8536110 Cape May, 0.5-5 km from the survey"),
    "CS_02_CMH_20150313_CS": (-3.02 * 0.3048, "8536110 Cape May, ~4 km"),
    "AI_01_AIE_20150325_CS": (-2.61 * 0.3048, "8534720 Atlantic City, ~2 km"),
}


def vdatum_offset(lon: float, lat: float) -> float:
    """NAVD88 height (m) of the MLLW=0 surface at (lon, lat); NaN outside coverage."""
    url = (
        "https://vdatum.noaa.gov/vdatumweb/api/convert?"
        f"s_x={lon:.6f}&s_y={lat:.6f}&s_z=0&region=contiguous&s_coor=geo"
        "&s_h_frame=NAD83_2011&s_v_frame=MLLW&s_v_unit=us_ft"
        "&t_h_frame=NAD83_2011&t_v_frame=NAVD88&t_v_unit=m"
    )
    try:
        r = json.load(urllib.request.urlopen(url, timeout=30))
        tz = float(r["t_z"])
    except Exception as exc:  # noqa: BLE001
        print(f"    VDatum err at {lon:.4f},{lat:.4f}: {exc}", file=sys.stderr)
        return float("nan")
    return tz if tz > -1000 else float("nan")


def offset_field(sid: str, lon: np.ndarray, lat: np.ndarray, cache_dir: Path) -> np.ndarray:
    """Spatially-varying MLLW->NAVD88 offset (m). A single mean is NOT good enough."""
    from scipy.interpolate import griddata

    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_csv = cache_dir / f"vdatum_{sid}.csv"
    if cache_csv.exists():
        cache = np.loadtxt(cache_csv, delimiter=",", skiprows=1)
        print(f"    {len(cache)} cached VDatum nodes")
    else:
        idx = np.unique(np.linspace(0, len(lon) - 1, N_VDATUM).astype(int))
        print(f"    querying VDatum at {len(idx)} thinned locations …")
        rows = []
        for k, i in enumerate(idx):
            off = vdatum_offset(lon[i], lat[i])
            if np.isfinite(off):
                rows.append((lon[i], lat[i], off))
            if (k + 1) % 50 == 0:
                print(f"      {k + 1}/{len(idx)}")
            time.sleep(0.12)
        cache = np.array(rows)
        np.savetxt(cache_csv, cache, delimiter=",",
                   header="lon,lat,offset_navd88_m", comments="")
        print(f"    cached {len(cache)} nodes -> {cache_csv.name}")

    print("    offset field (m): mean %.3f  min %.3f  max %.3f"
          % (cache[:, 2].mean(), cache[:, 2].min(), cache[:, 2].max()))
    off = griddata(cache[:, :2], cache[:, 2], (lon, lat), method="linear")
    bad = ~np.isfinite(off)
    if bad.any():
        off[bad] = griddata(cache[:, :2], cache[:, 2], (lon[bad], lat[bad]), method="nearest")
    return off


def main(preset: str = "nj") -> None:
    import geopandas as gpd
    import pyproj
    import rasterio
    from rasterio.features import geometry_mask
    from rasterio.transform import from_origin
    from scipy.interpolate import griddata

    surveys, raster_out, raw, title, *rest = PRESETS[preset]
    zsign = rest[0] if rest else 1.0
    print(f"[{preset}] {title}")
    print(f"        {len(surveys)} survey(s) -> {raster_out}")
    if preset == "nj" and raster_out.exists():
        raise SystemExit(
            "🔴 the 'nj' preset targets the FROZEN archive tier and would rewrite it. "
            "It is kept as a record of how ehydro_nj.tif was built, not to be re-run."
        )

    to_ll = pyproj.Transformer.from_crs(EPSG_SRC, 4326, always_xy=True)
    to_utm = pyproj.Transformer.from_crs(EPSG_SRC, EPSG_DST, always_xy=True)

    parts = []   # (xm, ym, z_navd88, coverage_gdf)
    for sid, chan, district in surveys:
        print(f"\n[{chan}]  {sid}")
        d = fetch(sid, district, raw)
        xyz = _one(d, ".xyz")
        gdb = _one(d, ".gdb")
        raw_pts = read_xyz(xyz)
        x_ft, y_ft, z_mllw_ft = raw_pts[:, 0], raw_pts[:, 1], zsign * raw_pts[:, 2]
        if zsign < 0 and raw_pts[:, 2].min() < 0:
            print(f"    ⚠️ preset says +depth but Z has negatives (min {raw_pts[:, 2].min():.1f}); "
                  "check the district convention for this survey")
        print(f"    {len(raw_pts)} soundings; survey-datum ft "
              f"{z_mllw_ft.min():.1f}..{z_mllw_ft.max():.1f}")

        lon, lat = to_ll.transform(x_ft, y_ft)
        xm, ym = to_utm.transform(x_ft, y_ft)
        stated = stated_offset_m(xyz)
        if stated is not None:
            print(f"    survey states its plane at {stated:+.3f} m NAVD88 — using it")
            off = np.full(len(z_mllw_ft), stated)
        elif sid in STATION_PLANE_M:
            plane, prov = STATION_PLANE_M[sid]
            print(f"    survey states no plane; VDatum is unusable here -> NOAA station "
                  f"datum {plane:+.3f} m NAVD88 ({prov})")
            off = np.full(len(z_mllw_ft), plane)
        else:
            print("    survey states no plane; falling back to the VDatum MLLW field")
            off = offset_field(sid, np.asarray(lon), np.asarray(lat), raw.parent)
        z = z_mllw_ft * FT_TO_M + off
        print(f"    NAVD88 m: {z.min():.2f} .. {z.max():.2f}")

        cover = gpd.read_file(gdb, layer="Bathymetry_Vector").to_crs(EPSG_DST)
        parts.append((np.asarray(xm), np.asarray(ym), z, cover))

    # --- common grid over every survey ---------------------------------------------------
    xs = np.concatenate([p[0] for p in parts])
    ys = np.concatenate([p[1] for p in parts])
    xmin = np.floor(xs.min() / RES) * RES
    ymin = np.floor(ys.min() / RES) * RES
    xmax = np.ceil(xs.max() / RES) * RES
    ymax = np.ceil(ys.max() / RES) * RES
    ncol = int((xmax - xmin) / RES)
    nrow = int((ymax - ymin) / RES)
    transform = from_origin(xmin, ymax, RES, RES)
    cx = xmin + (np.arange(ncol) + 0.5) * RES
    cy = ymax - (np.arange(nrow) + 0.5) * RES
    gx, gy = np.meshgrid(cx, cy)
    print(f"\ngrid {nrow} x {ncol} @ {RES:g} m")

    grid = np.full((nrow, ncol), np.nan, dtype="float32")
    for xm, ym, z, cover in parts:
        g = griddata((xm, ym), z, (gx, gy), method="linear").astype("float32")
        inside = ~geometry_mask(cover.geometry, out_shape=(nrow, ncol),
                                transform=transform, invert=False)
        g[~inside] = np.nan
        grid = np.where(np.isfinite(g), g, grid)

    n_cover = int(np.isfinite(grid).sum())

    # --- the carving clip: this tier only ever supplies REAL WATER ------------------------
    # Anything the survey reports at or above WATER_MAX is dropped, so a shore-protection or
    # beach survey can never flatten a seawall/jetty through this file. See the module docstring.
    grid[np.isfinite(grid) & (grid >= WATER_MAX)] = np.nan
    n_water = int(np.isfinite(grid).sum())
    print(f"surveyed cells: {n_cover}   -> after water-only clip (< {WATER_MAX} m): {n_water}"
          f"   (dropped {n_cover - n_water} at/above the clip — structures, banks, spoil)")

    grid[~np.isfinite(grid)] = NODATA
    raster_out.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        raster_out, "w", driver="GTiff", height=nrow, width=ncol, count=1,
        dtype="float32", crs=EPSG_DST, transform=transform, nodata=NODATA,
        compress="DEFLATE", tiled=True, blockxsize=512, blockysize=512,
    ) as dst:
        dst.write(grid, 1)
    print(f"\nwrote {raster_out.relative_to(ROOT)}  ({n_water} carved cells)")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--set", choices=sorted(PRESETS), default="nj", dest="preset",
                    help="'nj' = the frozen v1_monmouth tier (a record; cannot re-run); "
                         "'raritan' = the v1.5 Arthur Kill mouth + Raritan River cuts")
    main(ap.parse_args().preset)
