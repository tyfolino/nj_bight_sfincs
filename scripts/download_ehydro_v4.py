#!/usr/bin/env python3
"""USACE eHydro channel surveys for the v4 RIVERS, and a check of CUDEM against them.

    python scripts/download_ehydro_v4.py                  # report only: list surveys
    python scripts/download_ehydro_v4.py --apply          # download + build + compare
    python scripts/download_ehydro_v4.py --apply --set passaic

WHAT IT IS FOR
--------------
v4 carries the model up the Passaic, the Hackensack and the tidal Delaware. The bed there
comes from NCEI CUDEM 1/9" (``ncei19_n41x00_w074x25_2015v1`` in the Newark Bay rivers,
``ncei19_n40x25_w075x00_2014v1`` on the Delaware). CUDEM's river pixels look SHALLOW in
the Passaic (channel 1st-percentile bed -2.7..-0.5 m NAVD88 between lat 40.72 and 40.84),
and nothing in the stack says whether that is the river or the interpolator. An eHydro
condition survey is a boat with an echo sounder: it is the independent measurement.

For each preset this script
  1. downloads the chosen surveys (report mode only lists what exists, with the days from
     Sandy, 2012-10-29, so the choice is visible);
  2. converts every sounding to NAVD88 metres on UTM18N;
  3. samples CUDEM at every sounding and writes the difference by latitude band
     (``*_vs_cudem.csv``) — that is the verdict on CUDEM;
  4. writes a 5 m carving raster in the house style of ``download_ehydro_nj.py``:
     linear interpolation, masked to the survey's own ``Bathymetry_Vector`` coverage,
     water-only clip (z < -1 m) so it can never flatten a structure.
It does NOT register the raster as a tier (``data/data_catalog.yml`` is not touched).

WHICH SURVEYS — the one NEAREST SANDY that reaches the reach
------------------------------------------------------------
eHydro's archive starts late here. Every candidate is POST-Sandy:
  * Passaic   PR_01_PAR_20151216 (+1143 d) — the earliest, and the last one that still
              reaches lat 40.779 (the 2020+ surveys stop at 40.733). It predates the
              Lower Passaic 8.3-mile remedial dredging; the 2012 Tierra Phase 1 and the
              2013-14 RM 10.9 removals are outside or at the margin of its footprint.
  * Hackensack NJ_17_HAC_20181022 (+2184 d) — nothing earlier exists in eHydro.
  * Delaware  the earliest survey of each Philadelphia-to-Trenton reach, 2013-11 .. 2016-05.
              ⚠️ PT_08_PER_20141217_131's own metadata says "Survey Date: May 21, 2014";
              it is kept because its footprint (40.135..40.208) is the larger one.
              ⚠️ CENAP bins soundings 30 ft x 30 ft with "Shot Selection Method: Shoal":
              each point is the SHOALEST sounding in its bin, biased high by design.

🔴 SIGN AND DATUM ARE PER-DISTRICT FACTS (same trap as download_ehydro_nj.py)
---------------------------------------------------------------------------
  CENAN (New York): the .XYZ carries NEGATIVE elevations below MLLW (the .DAT duplicate
        in the same zip carries POSITIVE depths — never read the .DAT). The XYZ states no
        plane, the .XML says MLLW, so the MLLW->NAVD88 offset is the VDatum field
        (the VDatum web API answers in NY Harbor; cached per survey).
  CENAP (Philadelphia): POSITIVE depths below MLLW (1983-2001 epoch, per the .xml).
        🔴 Its 2013-2016 .xyz files are PARTIAL (2-30% of the soundings, one corner of
        the coverage; PT_04_BEV's is a byte copy of PT_03_MUD's), so CENAP soundings are
        read from the gdb ``SurveyPoint`` layer (EPSG:3424, ``Z_use`` = +ft below MLLW).
        VDatum's API fails on the tidal Delaware (HTTP 412 at Trenton, Burlington and
        Philadelphia, 2026-09-26), so the plane is the NOAA CO-OPS MLLW-NAVD88 of the
        tide stations on the river, interpolated LINEARLY IN LATITUDE (the reach runs
        SW->NE and latitude is monotonic along it). Table ``DELAWARE_MLLW`` below.
A sign check refuses a survey whose Z signs disagree with its district's convention.

OUTPUTS (``--apply``; every file written atomically via a temp file + rename)
  data/elevation_v4/ehydro/  (symlink -> /scratch/tpj8/nj_bight_sfincs_data/...)
    raw/<sid>.ZIP                      the survey as served
    raw/vdatum_<sid>.csv               cached VDatum nodes (CENAN only)
    ehydro_<set>_v4.tif                5 m UTM18N NAVD88 carving raster, NoData off-channel
    ehydro_<set>_v4_points.csv         every sounding: lon, lat, x/y UTM, z NAVD88, CUDEM
    ehydro_<set>_v4_vs_cudem.csv       CUDEM - survey by latitude band
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import download_ehydro_nj as ehnj  # noqa: E402  (read_xyz, stated_offset_m, VDatum)

#: data/elevation_v4/ehydro is a symlink into /scratch (home is a GPFS quota), the same
#: pattern as data/elevation_v4/3dep. Created on --apply if missing.
OUT = ROOT / "data" / "elevation_v4" / "ehydro"
SCRATCH = Path("/scratch/tpj8/nj_bight_sfincs_data/elevation_v4/ehydro")
RAW = OUT / "raw"

CUDEM_VRTS = [  # first hit wins; both NAD83 geographic
    ROOT / "data" / "elevation_v3" / "cudem_nj_v3.vrt",  # lon -75.75..-71.75
    ROOT / "data" / "elevation_v4" / "cudem_delaware_v4.vrt",  # lon -75.75..-75.00
]

SERVICE = (
    "https://services7.arcgis.com/n1YM8pTrFmm7L4hs/arcgis/rest/services/"
    "eHydro_Survey_Data/FeatureServer/0/query"
)
ZIP_URL = "https://ehydroprod.blob.core.usgovcloudapi.net/ehydro-surveys/{d}/{sid}.ZIP"
SANDY = dt.date(2012, 10, 29)

EPSG_SRC = 3424  # NAD83 / NJ State Plane, US survey ft (both districts, per .xml)
EPSG_UTM = 32618
FT = 0.3048006096012192
RES = 5.0
WATER_MAX = -1.0
NODATA = np.float32(-9999.0)
LAT_BAND = 0.01  # degrees, for the CUDEM comparison table

#: NOAA CO-OPS datums (mdapi .../stations/<id>/datums.json, metric, epoch 1983-2001),
#: MLLW minus NAVD88 in metres, fetched 2026-09-26. Stations on the river with BOTH
#: datums published; Bridesburg, Tacony-Palmyra, Burlington and Newbold publish no NAVD88.
DELAWARE_MLLW: list[tuple[float, float, str]] = [  # (lat, MLLW-NAVD88 m, station)
    (39.9331, -0.945, "8545240 Philadelphia"),
    (39.9533, -0.987, "8545530 Philadelphia Pier 11 N"),
    (40.0133, -0.888, "8538875 Pompeston Creek"),
    (40.0733, -0.903, "8539058 Assiscunk Creek"),
    (40.1367, -1.140, "8539487 Fieldsboro"),
    (40.1883, -1.175, "8539993 Trenton Marine Terminal"),
]

#: preset -> (district, sign, [survey ids], eHydro feature names for the report)
#: sign multiplies the XYZ Z into "elevation relative to MLLW" (ft).
PRESETS: dict[str, tuple[str, float, list[str], list[str]]] = {
    "passaic": ("CENAN", 1.0, ["PR_01_PAR_20151216_CS_4400_15"], ["Passaic River"]),
    "hackensack": (
        "CENAN",
        1.0,
        ["NJ_17_HAC_20181022_CS_4758_20"],
        ["Hackensack River"],
    ),
    "delaware": (
        "CENAP",
        -1.0,
        [
            "PS_24_RIC_20131120",  # Port Richmond Anchorage   +387 d
            "PT_01_HAR_20160308",  # Harbor to Bridesburg     +1226 d
            "PT_02_FRA_20160330",  # Frankford to Torresdale  +1248 d
            "PT_03_MUD_20160420",  # Mud Island to Enterprise +1269 d
            "PT_04_BEV_20160420",  # Beverly to Devlin        +1269 d  (gdb only)
            "PT_10_AUX_20140520",  # Aux. E of Burlington I.   +568 d
            "PT_05_LEH_20160512",  # Lehigh to Florence Bend  +1291 d
            "PT_06_FLO_20160121",  # Florence to Newbold      +1179 d
            "PT_07_BLA_20151228",  # Blake to Duck Island     +1155 d
            "PT_08_PER_20141217_131",  # Perriwig to Bridge (metadata: 2014-05-21)
        ],
        [
            "Port Richmond Anchorage",
            "Harbor to Bridesburg",
            "Frankfurt to Torresdale",
            "Frankford to Torresdale",
            "Mud Island to Enterprise",
            "Beverly to Devlin",
            "Auxillary Channel East of Burlington Island",
            "Lehigh to Florence Bend",
            "Florence to Newbold",
            "Blake to Duck Island",
            "Perriwig to Bridge",
        ],
    ),
}


# ── polite HTTP ─────────────────────────────────────────────────────────────────────
def _get(url: str, timeout: int = 120, tries: int = 5) -> bytes:
    for k in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return r.read()
        except OSError as exc:
            wait = 10 * 2**k
            print(f"    retry {k + 1}/{tries} in {wait}s: {exc}", file=sys.stderr)
            time.sleep(wait)
    raise SystemExit(f"🔴 giving up on {url}")


def _atomic_bytes(path: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    os.chmod(tmp, 0o755 if os.path.isdir(tmp) else 0o644)  # mkstemp: 0600
    os.replace(tmp, path)


def _atomic_csv(path: Path, df) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".csv")
    os.close(fd)
    df.to_csv(tmp, index=False, float_format="%.3f")
    os.chmod(tmp, 0o755 if os.path.isdir(tmp) else 0o644)  # mkstemp: 0600
    os.replace(tmp, path)


# ── report ──────────────────────────────────────────────────────────────────────────
def report(name: str) -> None:
    district, _, chosen, features = PRESETS[name]
    where = " OR ".join(f"sdsfeaturename='{f}'" for f in features)
    q = {
        "where": where,
        "outFields": "surveyjobidpk,sdsfeaturename,surveydatestart,surveytype",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "geojson",
        "resultRecordCount": "2000",
    }
    feats = json.loads(_get(SERVICE + "?" + urllib.parse.urlencode(q)))["features"]
    print(f"\n[{name}] {district} — {len(feats)} surveys on {len(features)} feature(s)")
    rows = []
    for f in feats:
        p = f["properties"]
        d = dt.datetime.fromtimestamp(p["surveydatestart"] / 1000, dt.UTC).date()
        ring = np.asarray(
            [c for poly in _polys(f["geometry"]) for c in poly], dtype=float
        )
        rows.append((p["sdsfeaturename"], d, p["surveyjobidpk"], ring[:, 1].max()))
    rows.sort()
    for feat, d, sid, latmax in rows:
        mark = "  <== chosen" if sid in chosen else ""
        print(
            f"  {feat[:34]:34s} {d}  {(d - SANDY).days:+5d} d  lat<={latmax:.3f}  "
            f"{sid}{mark}"
        )
    missing = set(chosen) - {r[2] for r in rows}
    if missing:
        print(f"  ⚠️ chosen but not served: {sorted(missing)}")


def _polys(geom: dict) -> list:
    if geom is None:
        return []
    if geom["type"] == "Polygon":
        return [geom["coordinates"][0]]
    return [p[0] for p in geom["coordinates"]]


# ── build ───────────────────────────────────────────────────────────────────────────
def fetch(sid: str, district: str) -> Path:
    zp = RAW / f"{sid}.ZIP"
    if not zp.exists():
        url = ZIP_URL.format(d=district, sid=sid)
        print(f"  downloading {url}")
        _atomic_bytes(zp, _get(url, timeout=900))
        time.sleep(2)
    out = RAW / sid
    if not out.exists():
        tmp = Path(tempfile.mkdtemp(dir=RAW, prefix=f".{sid}."))
        with zipfile.ZipFile(zp) as z:
            z.extractall(tmp)
        os.chmod(tmp, 0o755 if os.path.isdir(tmp) else 0o644)  # mkstemp: 0600
        os.replace(tmp, out)
    return out


def delaware_plane(lat: np.ndarray) -> np.ndarray:
    la = np.array([r[0] for r in DELAWARE_MLLW])
    off = np.array([r[1] for r in DELAWARE_MLLW])
    return np.interp(lat, la, off)  # constant beyond the end stations


def soundings(sid: str, district: str, sign: float):
    """(lon, lat, xm, ym, z_navd88_m, coverage_gdf_utm) for one survey."""
    import geopandas as gpd
    import pyproj

    d = fetch(sid, district)
    gdb = ehnj._one(d, ".gdb")
    # the THINNED file, <sid>.XYZ; newer zips add <sid>_FULL.XYZ / <sid>_A.XYZ beside it
    xyz = next((f for f in d.iterdir() if f.name.lower() == f"{sid}.xyz".lower()), None)
    xyz = xyz or ehnj._one(d, ".xyz")
    if district == "CENAP":
        # 🔴 the CENAP 2013-2016 .xyz is NOT the survey: it holds 2-30% of the points,
        # in one corner of the coverage, and PT_04_BEV's is byte-identical to
        # PT_03_MUD's. The gdb SurveyPoint layer (EPSG:3424, Z_use = +depth ft below
        # MLLW) spans the whole Bathymetry_Vector coverage, so it is read instead.
        sp = gpd.read_file(gdb, layer="SurveyPoint")
        if sp.crs is None or sp.crs.to_epsg() != EPSG_SRC:
            raise SystemExit(f"🔴 {sid}: SurveyPoint CRS {sp.crs}, expected {EPSG_SRC}")
        raw = np.column_stack([sp.geometry.x, sp.geometry.y, sp.Z_use.astype(float)])
        raw = raw[np.isfinite(raw).all(axis=1)]
    else:
        raw = ehnj.read_xyz(xyz)
    zr = raw[:, 2]
    neg = float((zr < 0).mean())
    # the district convention, checked on the data rather than trusted
    if sign > 0 and neg < 0.5:
        raise SystemExit(f"🔴 {sid}: CENAN expects negative Z, only {neg:.0%} are")
    if sign < 0 and neg > 0.05:
        raise SystemExit(f"🔴 {sid}: CENAP expects +depth, {neg:.0%} of Z are negative")
    z_mllw_ft = sign * zr
    to_ll = pyproj.Transformer.from_crs(EPSG_SRC, 4326, always_xy=True)
    to_utm = pyproj.Transformer.from_crs(EPSG_SRC, EPSG_UTM, always_xy=True)
    lon, lat = (np.asarray(v) for v in to_ll.transform(raw[:, 0], raw[:, 1]))
    xm, ym = (np.asarray(v) for v in to_utm.transform(raw[:, 0], raw[:, 1]))

    stated = ehnj.stated_offset_m(xyz)
    if stated is not None:
        off = np.full(len(zr), stated)
        how = f"survey-stated plane {stated:+.3f} m"
    elif district == "CENAP":
        off = delaware_plane(lat)
        how = f"CO-OPS MLLW by latitude {off.min():+.3f}..{off.max():+.3f} m"
    else:
        ehnj.N_VDATUM = 120
        off = ehnj.offset_field(sid, lon, lat, RAW)
        how = f"VDatum MLLW field {off.min():+.3f}..{off.max():+.3f} m"
    z = z_mllw_ft * FT + off
    print(
        f"    {len(zr)} soundings, lat {lat.min():.3f}..{lat.max():.3f}; "
        f"{how}; NAVD88 {z.min():.2f}..{z.max():.2f} m"
    )
    cover = gpd.read_file(gdb, layer="Bathymetry_Vector").to_crs(EPSG_UTM)
    return lon, lat, xm, ym, z, cover


def sample_cudem(lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    import rasterio

    out = np.full(len(lon), np.nan)
    for vrt in CUDEM_VRTS:
        todo = ~np.isfinite(out)
        if not todo.any():
            break
        with rasterio.open(vrt) as src:
            v = np.array([s[0] for s in src.sample(zip(lon[todo], lat[todo]))], float)
            v[(v == src.nodata) | (v < -1000)] = np.nan
        out[todo] = v
    return out


def build(name: str) -> None:
    import pandas as pd
    import rasterio
    from rasterio.features import geometry_mask
    from rasterio.transform import from_origin
    from scipy.interpolate import griddata

    district, sign, sids, _ = PRESETS[name]
    print(f"\n[{name}] {district}: {len(sids)} survey(s)")
    parts, pts = [], []
    for sid in sids:
        print(f"  {sid}")
        lon, lat, xm, ym, z, cover = soundings(sid, district, sign)
        parts.append((xm, ym, z, cover))
        pts.append(
            pd.DataFrame(
                {"survey": sid, "lon": lon, "lat": lat, "x": xm, "y": ym, "z": z}
            )
        )
    P = pd.concat(pts, ignore_index=True)
    P["cudem"] = sample_cudem(P.lon.to_numpy(), P.lat.to_numpy())
    P["cudem_minus_survey"] = P.cudem - P.z
    _atomic_csv(OUT / f"ehydro_{name}_v4_points.csv", P)

    P["band"] = (np.floor(P.lat / LAT_BAND) * LAT_BAND).round(3)
    ok = P[np.isfinite(P.cudem_minus_survey)]
    T = (
        ok.groupby("band")
        .agg(
            n=("z", "size"),
            survey_med=("z", "median"),
            survey_p05=("z", lambda s: s.quantile(0.05)),
            cudem_med=("cudem", "median"),
            cudem_p05=("cudem", lambda s: s.quantile(0.05)),
            diff_med=("cudem_minus_survey", "median"),
            diff_p10=("cudem_minus_survey", lambda s: s.quantile(0.10)),
            diff_p90=("cudem_minus_survey", lambda s: s.quantile(0.90)),
        )
        .reset_index()
    )
    allrow = {
        "band": "ALL",
        "n": len(ok),
        "survey_med": ok.z.median(),
        "survey_p05": ok.z.quantile(0.05),
        "cudem_med": ok.cudem.median(),
        "cudem_p05": ok.cudem.quantile(0.05),
        "diff_med": ok.cudem_minus_survey.median(),
        "diff_p10": ok.cudem_minus_survey.quantile(0.10),
        "diff_p90": ok.cudem_minus_survey.quantile(0.90),
    }
    T = pd.concat([T, pd.DataFrame([allrow])], ignore_index=True)
    _atomic_csv(OUT / f"ehydro_{name}_v4_vs_cudem.csv", T)
    print(f"\n  CUDEM - survey (m, + = CUDEM shallower), {len(ok)}/{len(P)} on CUDEM")
    print(T.round(2).to_string(index=False))

    # ── raster: each survey interpolated on its own window of one common lattice ──
    xs, ys = P.x.to_numpy(), P.y.to_numpy()
    x0 = np.floor(xs.min() / RES) * RES - RES
    y1 = np.ceil(ys.max() / RES) * RES + RES
    ncol = int((np.ceil(xs.max() / RES) * RES + RES - x0) / RES)
    nrow = int((y1 - (np.floor(ys.min() / RES) * RES - RES)) / RES)
    grid = np.full((nrow, ncol), np.nan, dtype="float32")
    for xm, ym, z, cover in parts:
        c0 = int((xm.min() - x0) // RES)
        c1 = int((xm.max() - x0) // RES) + 1
        r0 = int((y1 - ym.max()) // RES)
        r1 = int((y1 - ym.min()) // RES) + 1
        tr = from_origin(x0 + c0 * RES, y1 - r0 * RES, RES, RES)
        cx = x0 + (np.arange(c0, c1) + 0.5) * RES
        cy = y1 - (np.arange(r0, r1) + 0.5) * RES
        gx, gy = np.meshgrid(cx, cy)
        g = griddata((xm, ym), z, (gx, gy), method="linear").astype("float32")
        inside = geometry_mask(
            cover.geometry, out_shape=g.shape, transform=tr, invert=True
        )
        g[~inside] = np.nan
        sub = grid[r0:r1, c0:c1]
        grid[r0:r1, c0:c1] = np.where(np.isfinite(g), g, sub)
    n_cov = int(np.isfinite(grid).sum())
    grid[np.isfinite(grid) & (grid >= WATER_MAX)] = np.nan
    n_wat = int(np.isfinite(grid).sum())
    grid[~np.isfinite(grid)] = NODATA
    dst = OUT / f"ehydro_{name}_v4.tif"
    fd, tmp = tempfile.mkstemp(dir=OUT, prefix=f".{dst.name}.", suffix=".tif")
    os.close(fd)
    with rasterio.open(
        tmp,
        "w",
        driver="GTiff",
        height=nrow,
        width=ncol,
        count=1,
        dtype="float32",
        crs=EPSG_UTM,
        transform=from_origin(x0, y1, RES, RES),
        nodata=NODATA,
        compress="DEFLATE",
        tiled=True,
        blockxsize=512,
        blockysize=512,
    ) as ds:
        ds.write(grid, 1)
        ds.update_tags(
            source="USACE eHydro " + ",".join(sids),
            units="m NAVD88",
            water_only_clip=str(WATER_MAX),
        )
    os.chmod(tmp, 0o755 if os.path.isdir(tmp) else 0o644)  # mkstemp: 0600
    os.replace(tmp, dst)
    print(
        f"\n  wrote {dst.relative_to(ROOT)}: {nrow}x{ncol} @ {RES:g} m, "
        f"{n_cov} surveyed cells -> {n_wat} after the < {WATER_MAX} m clip"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--set", choices=sorted(PRESETS), action="append", dest="sets")
    ap.add_argument(
        "--apply",
        action="store_true",
        help="download, convert, compare with CUDEM and write rasters",
    )
    a = ap.parse_args()
    sets = a.sets or list(PRESETS)
    if not a.apply:
        for s in sets:
            report(s)
            time.sleep(1)
        print("\n(report only — pass --apply to download and build)")
        return 0
    if not OUT.exists():
        SCRATCH.mkdir(parents=True, exist_ok=True)
        OUT.symlink_to(SCRATCH)
    RAW.mkdir(parents=True, exist_ok=True)
    for s in sets:
        build(s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
