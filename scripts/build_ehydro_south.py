#!/usr/bin/env python3
"""Build the eHydro CARVING TIER for the v2_barnegat southern lobe.

Ported from the archive 2026-11-03 (ARCHIVE.md; its history is there): `ehydro_south` is in Model 1.0.0's
elevation list. Writes `data/elevation/ehydro_south.tif`, which is on disk; re-run only to rebuild it.

Companion to scripts/download_ehydro_nj.py (which carves Shark River Inlet only, a
2.5 x 1 km raster at 40.18N). The expanded domain reaches to 39.70N and that whole
southern lobe currently has NO channel survey in the elevation stack at all.

This tier supplies the federal navigation channels inside it: Barnegat Inlet, Manasquan
Inlet, the New Jersey Intracoastal Waterway segments, Point Pleasant Canal, Toms River and
Oyster Creek.

⚠️⚠️ THE SIGN CONVENTION VARIES BY USACE DISTRICT, AND THIS DOMAIN STRADDLES THE BOUNDARY.
Shark River Inlet is New York District (CENAN) and its XYZ ships NEGATIVE ELEVATIONS.
Everything in Barnegat Bay is Philadelphia District and ships POSITIVE DEPTHS below MLLW
(raw z +1.5 .. +64 ft). download_ehydro_nj.py hardcodes `z = z_ft * FT_TO_M + off`, which is
right only for the former; applied to a southern survey it yields POSITIVE "elevations",
the water-only clip then drops 100% of them, and the tier silently produces an EMPTY raster
with no error. So the convention is DETECTED per survey here, not assumed:

    a navigation channel is never mostly above MLLW  =>  median(z_raw) > 0 means depth-down

Everything else follows the proven chain: EPSG:3424 US-ft -> UTM18N, a spatially-varying
VDatum MLLW->NAVD88 offset FIELD (not a constant — the separation drifts across the lobe),
linear interpolation to a 5 m grid, masking to each survey's own Bathymetry_Vector coverage
polygons, and the water-only clip that makes it impossible to flatten a structure.

⚠️ CONSUMING IT NEEDS A SUBGRID REBUILD, NOT A TEMPLATE REBUILD FROM SCRATCH:
`build_static` copies the frozen mesh (z, mask and all) and returns early, so a new
elevation tier never reaches the coarse `z`. Regenerate only the subgrid on the frozen grid
(scripts/rebuild_subgrid.py). The subgrid tables are what the solver uses for conveyance, and
leaving `z`/`mask` untouched keeps the domain fingerprint intact.

Run:  PYTHONPATH=$PWD python scripts/build_ehydro_south.py
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ELEV = ROOT / "data" / "elevation"
EHYDRO = ELEV / "ehydro"
RAW = EHYDRO / "raw_south"

E = ("https://services7.arcgis.com/n1YM8pTrFmm7L4hs/arcgis/rest/services/"
     "eHydro_Survey_Data/FeatureServer/0/query")
# UTM18N envelope over the southern lobe (Manasquan Inlet down past Barnegat Inlet)
BBOX = "555000,4395000,595000,4440000"
# Navigation features to carve. Matched case-insensitively against sdsfeaturename.
WANT = ("BARNEGAT INLET", "MANASQUAN INLET", "INTRACOASTAL", "ICW", "IW 0",
        "POINT PLEASANT", "TOMS RIVER", "OYSTER CREEK")

EPSG_SRC = 3424
EPSG_DST = 32618
FT_TO_M = 0.3048006096012192
RES = 5.0
N_VDATUM = 120          # thinned VDatum nodes per survey (cached); the lobe is smooth
WATER_MAX = -1.0
RASTER_OUT = ELEV / "ehydro_south.tif"
NODATA = np.float32(-9999.0)


def surveys() -> list[dict]:
    p = dict(where="1=1", geometry=BBOX, geometryType="esriGeometryEnvelope",
             inSR="32618", spatialRel="esriSpatialRelIntersects",
             outFields="surveyjobidpk,sdsfeaturename,surveydatestart,surveytype,"
                       "sourcedatalocation",
             returnGeometry="false", f="json", resultRecordCount="1000")
    feats = [f["attributes"] for f in
             json.load(urllib.request.urlopen(E + "?" + urllib.parse.urlencode(p),
                                              timeout=90))["features"]]
    keep = [f for f in feats
            if any(k in (f["sdsfeaturename"] or "").upper() for k in WANT)
            and f.get("sourcedatalocation")]
    # EARLIEST survey per feature: closest to 2012. (The southern archive starts in 2015 —
    # there is nothing in the 2009-2014 window, so this is as close as the record gets.)
    best: dict[str, dict] = {}
    for f in sorted(keep, key=lambda a: a.get("surveydatestart") or 0):
        best.setdefault((f["sdsfeaturename"] or "").upper(), f)
    return list(best.values())


def fetch(att: dict) -> Path | None:
    RAW.mkdir(parents=True, exist_ok=True)
    sid = att["surveyjobidpk"]
    zp = RAW / f"{sid}.ZIP"
    if not zp.exists():
        try:
            urllib.request.urlretrieve(att["sourcedatalocation"], zp)
        except Exception as exc:  # noqa: BLE001
            print(f"    download failed: {exc}")
            return None
    out = RAW / sid
    if not out.exists():
        try:
            with zipfile.ZipFile(zp) as z:
                z.extractall(out)
        except Exception as exc:  # noqa: BLE001
            print(f"    unzip failed: {exc}")
            return None
    return out


def vdatum_offset(lon: float, lat: float) -> float:
    url = ("https://vdatum.noaa.gov/vdatumweb/api/convert?"
           f"s_x={lon:.6f}&s_y={lat:.6f}&s_z=0&region=contiguous&s_coor=geo"
           "&s_h_frame=NAD83_2011&s_v_frame=MLLW&s_v_unit=us_ft"
           "&t_h_frame=NAD83_2011&t_v_frame=NAVD88&t_v_unit=m")
    try:
        tz = float(json.load(urllib.request.urlopen(url, timeout=30))["t_z"])
    except Exception:  # noqa: BLE001
        return float("nan")
    return tz if tz > -1000 else float("nan")


def offset_field(sid: str, lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    from scipy.interpolate import griddata
    EHYDRO.mkdir(parents=True, exist_ok=True)
    cache_csv = EHYDRO / f"vdatum_south_{sid}.csv"
    if cache_csv.exists():
        cache = np.loadtxt(cache_csv, delimiter=",", skiprows=1)
    else:
        idx = np.unique(np.linspace(0, len(lon) - 1, N_VDATUM).astype(int))
        print(f"    querying VDatum at {len(idx)} thinned locations ...")
        rows = []
        for k, i in enumerate(idx):
            off = vdatum_offset(lon[i], lat[i])
            if np.isfinite(off):
                rows.append((lon[i], lat[i], off))
            time.sleep(0.10)
        if len(rows) < 3:
            print("    !! VDatum returned too few nodes — falling back to -0.50 m constant")
            return np.full(lon.shape, -0.50)
        cache = np.array(rows)
        np.savetxt(cache_csv, cache, delimiter=",",
                   header="lon,lat,offset_navd88_m", comments="")
    if cache.ndim == 1:
        cache = cache.reshape(1, -1)
    print(f"    VDatum offset field: mean {cache[:, 2].mean():+.3f}  "
          f"min {cache[:, 2].min():+.3f}  max {cache[:, 2].max():+.3f} m ({len(cache)} nodes)")
    off = griddata(cache[:, :2], cache[:, 2], (lon, lat), method="linear")
    bad = ~np.isfinite(off)
    if bad.any():
        off[bad] = griddata(cache[:, :2], cache[:, 2], (lon[bad], lat[bad]), method="nearest")
    return off


def main() -> int:
    import geopandas as gpd
    import pyproj
    import rasterio
    from rasterio.features import geometry_mask
    from rasterio.transform import from_origin
    from scipy.interpolate import griddata

    to_ll = pyproj.Transformer.from_crs(EPSG_SRC, 4326, always_xy=True)
    to_utm = pyproj.Transformer.from_crs(EPSG_SRC, EPSG_DST, always_xy=True)

    sel = surveys()
    print(f"{len(sel)} navigation features in the southern lobe (earliest survey each):")
    for a in sel:
        d = (dt.datetime.fromtimestamp(a["surveydatestart"] / 1000, dt.UTC).date()
             if a.get("surveydatestart") else "?")
        print(f"   {str(d):12s} {a['sdsfeaturename'][:40]:40s} {a['surveytype']}")

    parts = []
    for att in sel:
        sid, name = att["surveyjobidpk"], att["sdsfeaturename"]
        print(f"\n[{name}]  {sid}")
        d = fetch(att)
        if d is None:
            continue
        xyz = list(d.glob("**/*.XYZ")) or list(d.glob("**/*.xyz"))
        gdbs = list(d.glob("**/*.gdb"))
        if not xyz:
            print("    no XYZ — skipping")
            continue
        try:
            raw = np.loadtxt(xyz[0])
        except Exception as exc:  # noqa: BLE001
            print(f"    unreadable XYZ: {exc}")
            continue
        if raw.ndim != 2 or raw.shape[0] < 50:
            print("    too few soundings — skipping")
            continue
        x_ft, y_ft, z_raw = raw[:, 0], raw[:, 1], raw[:, 2]

        # ⚠️ per-survey sign detection — see the module docstring
        depth_down = float(np.median(z_raw)) > 0
        z_ft = -z_raw if depth_down else z_raw
        print(f"    {len(raw)} soundings; raw z {z_raw.min():+.1f}..{z_raw.max():+.1f} ft "
              f"=> {'DEPTH-positive-down (Philadelphia District)' if depth_down else 'ELEVATION-negative (NY District)'}")

        lon, lat = to_ll.transform(x_ft, y_ft)
        xm, ym = to_utm.transform(x_ft, y_ft)
        off = offset_field(sid, np.asarray(lon), np.asarray(lat))
        z = z_ft * FT_TO_M + off
        print(f"    NAVD88 m: {z.min():+.2f} .. {z.max():+.2f}  (median {np.median(z):+.2f})")
        if np.median(z) > 0:
            print("    !! median bed is ABOVE NAVD88 — sign detection is suspect, SKIPPING")
            continue

        cover = None
        for g in gdbs:
            try:
                cover = gpd.read_file(g, layer="Bathymetry_Vector").to_crs(EPSG_DST)
                break
            except Exception:  # noqa: BLE001
                continue
        parts.append((np.asarray(xm), np.asarray(ym), z, cover, name))

    if not parts:
        sys.exit("no usable surveys — nothing written")

    xs = np.concatenate([p[0] for p in parts])
    ys = np.concatenate([p[1] for p in parts])
    xmin, ymin = np.floor(xs.min() / RES) * RES, np.floor(ys.min() / RES) * RES
    xmax, ymax = np.ceil(xs.max() / RES) * RES, np.ceil(ys.max() / RES) * RES
    ncol, nrow = int((xmax - xmin) / RES), int((ymax - ymin) / RES)
    transform = from_origin(xmin, ymax, RES, RES)
    gx, gy = np.meshgrid(xmin + (np.arange(ncol) + 0.5) * RES,
                         ymax - (np.arange(nrow) + 0.5) * RES)
    print(f"\ngrid {nrow} x {ncol} @ {RES:g} m")

    grid = np.full((nrow, ncol), np.nan, dtype="float32")
    for xm, ym, z, cover, name in parts:
        # interpolate only over this survey's own bounding window (the lobe grid is large)
        g = griddata((xm, ym), z, (gx, gy), method="linear").astype("float32")
        if cover is not None and len(cover):
            inside = ~geometry_mask(cover.geometry, out_shape=(nrow, ncol),
                                    transform=transform, invert=False)
            g[~inside] = np.nan
        else:
            print(f"    [{name}] no coverage polygons — relying on the convex hull")
        n = int(np.isfinite(g).sum())
        grid = np.where(np.isfinite(g), g, grid)
        print(f"    [{name}] contributed {n} cells")

    n_cover = int(np.isfinite(grid).sum())
    grid[np.isfinite(grid) & (grid >= WATER_MAX)] = np.nan
    n_water = int(np.isfinite(grid).sum())
    print(f"\nsurveyed cells {n_cover} -> after the water-only clip (< {WATER_MAX} m): "
          f"{n_water}  (dropped {n_cover - n_water}: structures, banks, spoil)")
    if n_water == 0:
        sys.exit("!! EMPTY after the clip — this is the sign-convention failure mode")

    fin = grid[np.isfinite(grid)]
    print(f"carved bed: min {fin.min():+.2f}  median {np.median(fin):+.2f}  max {fin.max():+.2f} m")

    grid[~np.isfinite(grid)] = NODATA
    with rasterio.open(RASTER_OUT, "w", driver="GTiff", height=nrow, width=ncol, count=1,
                       dtype="float32", crs=EPSG_DST, transform=transform, nodata=NODATA,
                       compress="DEFLATE", tiled=True, blockxsize=512, blockysize=512) as dst:
        dst.write(grid, 1)
    print(f"\nwrote {RASTER_OUT.relative_to(ROOT)}  ({n_water} carved cells, "
          f"{RASTER_OUT.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
