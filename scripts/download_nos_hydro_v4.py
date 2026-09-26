#!/usr/bin/env python3
"""NOAA NOS hydrographic surveys (NCEI, HYD93 soundings) for the v4 rivers eHydro misses.

    python scripts/download_nos_hydro_v4.py            # report only
    python scripts/download_nos_hydro_v4.py --apply    # download, convert, compare

WHY
---
USACE eHydro surveys only federal channels, and only from ~2012 on. Three v4 reaches have
no eHydro survey at all, and one has no CUDEM either:
  * H05647  Raritan River, mouth -> New Brunswick (lon -74.44), 1934, lead line, MLW.
            THE ONLY MEASURED BED for the Raritan west of RR_01_RAR's end (lon -74.331),
            and CUDEM has no tile west of -74.25. CoNED NJ/DE's "NJNY_bathy_10m" and
            BlueTopo's "H05647.interpolated" pixels there are built FROM this survey, so
            they are not independent of it.
  * H03725  Hackensack River, Saw Mill Creek -> Berry's Creek (lat 40.758..40.801), 1915,
            lead line, MLW. The only sounding of the Hackensack north of NJ_17_HAC's end
            (lat 40.751). 🔴 Horizontal datum "Undetermined" in NCEI's own header: its
            positions are indicative, not survey-grade.
  * H09772  Delaware River, Roebling -> Trenton (to lat 40.20), 1978, echo sounder, MLW.
            The only bed on the last ~2 km below the Trenton falls that eHydro's
            PT_08_PER (to 40.188) does not reach. NOTHING exists above the falls.

DATUM
-----
HYD93 depths are metres below the survey's sounding datum, positive down (NCEI HYD93 spec:
"DEPTH VALUE x 10 IN METERS"; negative = an elevation). All three are MEAN LOW WATER.
  NY Harbor (H05647, H03725): VDatum web API, MLW -> NAVD88, a cached field (it answers
      here: -0.917 m at lon -74.40, -0.933 m at -74.44 on the Raritan, 2026-09-26).
  Delaware (H09772): VDatum's API returns HTTP 412 on the tidal Delaware, so the plane is
      the CO-OPS MLW-NAVD88 of 8539993 Trenton Marine Terminal (-1.114 m) and 8539487
      Fieldsboro (-1.079 m), interpolated in latitude (constant beyond them).
🔴 EPOCH: those planes are the 1983-2001 tidal epoch. A 1934 MLW sat lower by the
relative sea-level rise in between; left uncorrected, a 1934 bed reads too HIGH by about
2.9 mm/yr x (1992 - year) = 0.17 m (1934) / 0.22 m (1915) / 0.04 m (1978) (rate: the
Battery, 8518750). ``z_navd88`` below INCLUDES that correction; ``epoch_corr_m`` shows it.

OUTPUTS (``--apply``, atomic): data/elevation_v4/nos_hydro/ (symlink -> /scratch)
    raw/<id>.a93.gz                    as served by NCEI
    raw/vdatum_mlw_<id>.csv            cached VDatum nodes
    nos_<id>_v4_points.csv             lon, lat, depth_mlw, z_navd88, and every reference
                                       bed sampled at the sounding (CUDEM, eHydro tiers)
    nos_hydro_v4_compare.csv           per survey x reference x 0.01-degree lon/lat band
No raster is written: 1915/1934 lead-line soundings at 1:5,000-1:10,000 are a decision
for the tier builder (spacing, epoch, post-Sandy change), not for a downloader.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "elevation_v4" / "nos_hydro"
SCRATCH = Path("/scratch/tpj8/nj_bight_sfincs_data/elevation_v4/nos_hydro")
RAW = OUT / "raw"

A93 = "https://data.ngdc.noaa.gov/platforms/ocean/nos/coast/{blk}/{sid}/GEODAS/{sid}.a93.gz"
VDATUM = (
    "https://vdatum.noaa.gov/vdatumweb/api/convert?s_x={x:.6f}&s_y={y:.6f}&s_z=0"
    "&region=contiguous&s_coor=geo&s_h_frame=NAD83_2011&s_v_frame=MLW&s_v_unit=m"
    "&t_h_frame=NAD83_2011&t_v_frame=NAVD88&t_v_unit=m"
)
SLR_M_PER_YR = 0.0029  # the Battery 8518750 relative SLR, NOAA CO-OPS trend
EPOCH_MID = 1992  # centre of the 1983-2001 NTDE the modern planes refer to
N_VDATUM = 60

#: id -> (NCEI block, year, river, plane: "vdatum" | [(lat, MLW-NAVD88 m, station)])
SURVEYS: dict[str, tuple[str, int, str, object]] = {
    "H05647": ("H04001-H06000", 1934, "raritan", "vdatum"),
    "H03725": ("H02001-H04000", 1915, "hackensack", "vdatum"),
    "H09772": (
        "H08001-H10000",
        1978,
        "delaware",
        [
            (40.1367, -1.079, "8539487 Fieldsboro"),
            (40.1883, -1.114, "8539993 Trenton Marine Terminal"),
        ],
    ),
}

#: reference beds sampled at each sounding: (label, path, band) — first valid wins per
#: label. NAD83-geographic VRTs are sampled in lon/lat, the UTM tiers in UTM18N.
REFS = [
    ("cudem", ROOT / "data/elevation_v3/cudem_nj_v3.vrt"),
    ("ehydro_rr_2012", ROOT / "data/elevation_v1_5/ehydro_raritan_ak.tif"),
    ("ehydro_hac_2018", ROOT / "data/elevation_v4/ehydro/ehydro_hackensack_v4.tif"),
    ("ehydro_del_2014_16", ROOT / "data/elevation_v4/ehydro/ehydro_delaware_v4.tif"),
]


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


def _atomic_write(path: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    os.chmod(tmp, 0o755 if os.path.isdir(tmp) else 0o644)  # mkstemp: 0600
    os.replace(tmp, path)


def _atomic_csv(path: Path, df) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".csv")
    os.close(fd)
    df.to_csv(tmp, index=False, float_format="%.4f")
    os.chmod(tmp, 0o755 if os.path.isdir(tmp) else 0o644)  # mkstemp: 0600
    os.replace(tmp, path)


def read_a93(path: Path) -> np.ndarray:
    """(lat, lon, depth_m) for the SOUNDING records (value type 0, carto code 711)."""
    rows = []
    with gzip.open(path, "rt", errors="replace") as f:
        for ln in f:
            if len(ln) < 37:
                continue
            try:
                lat = int(ln[8:17]) / 1e6
                lon = int(ln[17:27]) / 1e6
                dep = int(ln[27:33]) / 10.0
                vtype, code = int(ln[33]), ln[34:37]
            except ValueError:
                continue
            if vtype == 0 and code == "711":
                rows.append((lat, lon, dep))
    return np.asarray(rows)


def vdatum_field(sid: str, lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    from scipy.interpolate import griddata

    cache = RAW / f"vdatum_mlw_{sid}.csv"
    if cache.exists():
        c = np.loadtxt(cache, delimiter=",", skiprows=1, ndmin=2)
    else:
        idx = np.unique(np.linspace(0, len(lon) - 1, N_VDATUM).astype(int))
        rows = []
        for i in idx:
            try:
                r = json.loads(_get(VDATUM.format(x=lon[i], y=lat[i]), tries=3))
                tz = float(r["t_z"])
            except (KeyError, ValueError, SystemExit) as exc:
                print(f"    VDatum miss at {lon[i]:.4f},{lat[i]:.4f}: {exc}")
                continue
            if tz > -1000:
                rows.append((lon[i], lat[i], tz))
            time.sleep(0.5)
        c = np.asarray(rows)
        fd, tmp = tempfile.mkstemp(dir=RAW, prefix=f".{cache.name}.")
        os.close(fd)
        np.savetxt(tmp, c, delimiter=",", header="lon,lat,mlw_navd88_m", comments="")
        os.chmod(tmp, 0o755 if os.path.isdir(tmp) else 0o644)  # mkstemp: 0600
        os.replace(tmp, cache)
    off = griddata(c[:, :2], c[:, 2], (lon, lat), method="linear")
    bad = ~np.isfinite(off)
    off[bad] = griddata(c[:, :2], c[:, 2], (lon[bad], lat[bad]), method="nearest")
    print(
        f"    VDatum MLW field: {len(c)} nodes, {c[:, 2].min():+.3f}..{c[:, 2].max():+.3f}"
    )
    return off


def sample(path: Path, lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    import rasterio
    from pyproj import Transformer

    out = np.full(len(lon), np.nan)
    if not path.exists():
        return out
    with rasterio.open(path) as src:
        if src.crs.is_geographic:
            xs, ys = lon, lat
        else:
            t = Transformer.from_crs(4326, src.crs, always_xy=True)
            xs, ys = t.transform(lon, lat)
        b = src.bounds
        inb = (xs >= b.left) & (xs <= b.right) & (ys >= b.bottom) & (ys <= b.top)
        if inb.any():
            v = np.array(
                [
                    s[0]
                    for s in src.sample(zip(np.asarray(xs)[inb], np.asarray(ys)[inb]))
                ],
                float,
            )
            if src.nodata is not None:
                v[v == src.nodata] = np.nan
            v[v < -1000] = np.nan
            out[inb] = v
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true", help="download, convert, compare")
    a = ap.parse_args()
    if not a.apply:
        for sid, (blk, yr, river, plane) in SURVEYS.items():
            kind = "VDatum MLW field" if plane == "vdatum" else "CO-OPS MLW by latitude"
            print(f"{sid} {yr} {river:10s} MLW -> NAVD88 via {kind}")
            print(f"    {A93.format(blk=blk, sid=sid)}")
        print("\n(report only — pass --apply to download and compare)")
        return 0

    import pandas as pd

    if not OUT.exists():
        SCRATCH.mkdir(parents=True, exist_ok=True)
        OUT.symlink_to(SCRATCH)
    RAW.mkdir(parents=True, exist_ok=True)
    comp = []
    for sid, (blk, yr, river, plane) in SURVEYS.items():
        print(f"\n[{sid}] {river} {yr}")
        gz = RAW / f"{sid}.a93.gz"
        if not gz.exists():
            _atomic_write(gz, _get(A93.format(blk=blk, sid=sid)))
            time.sleep(1)
        d = read_a93(gz)
        lat, lon, dep = d[:, 0], d[:, 1], d[:, 2]
        if plane == "vdatum":
            off = vdatum_field(sid, lon, lat)
        else:
            la = np.array([p[0] for p in plane])
            off = np.interp(lat, la, np.array([p[1] for p in plane]))
            print(f"    CO-OPS MLW plane {off.min():+.3f}..{off.max():+.3f} m")
        epoch = -SLR_M_PER_YR * (EPOCH_MID - yr)
        z = off - dep + epoch
        print(
            f"    {len(dep)} soundings, lon {lon.min():.3f}..{lon.max():.3f}, lat "
            f"{lat.min():.3f}..{lat.max():.3f}; epoch corr {epoch:+.3f} m; NAVD88 "
            f"{z.min():.2f}..{z.max():.2f} m"
        )
        P = pd.DataFrame(
            {
                "survey": sid,
                "year": yr,
                "lon": lon,
                "lat": lat,
                "depth_mlw_m": dep,
                "mlw_navd88_m": off,
                "epoch_corr_m": epoch,
                "z_navd88": z,
            }
        )
        for label, path in REFS:
            P[label] = sample(path, lon, lat)
        _atomic_csv(OUT / f"nos_{sid}_v4_points.csv", P)
        key = "lon" if river == "raritan" else "lat"
        P["band"] = (np.floor(P[key] / 0.01) * 0.01).round(2)
        for label, _ in REFS:
            ok = P[np.isfinite(P[label])]
            if ok.empty:
                continue
            ok = ok.assign(diff=ok[label] - ok.z_navd88)
            for band, g in list(ok.groupby("band")) + [("ALL", ok)]:
                comp.append(
                    {
                        "survey": sid,
                        "ref": label,
                        "band_axis": key,
                        "band": band,
                        "n": len(g),
                        "survey_med": g.z_navd88.median(),
                        "ref_med": g[label].median(),
                        "diff_med": g["diff"].median(),
                        "diff_p10": g["diff"].quantile(0.1),
                        "diff_p90": g["diff"].quantile(0.9),
                    }
                )
        s = P.groupby("band").z_navd88.agg(["size", "median", "min"]).round(2)
        print(f"    by {key} band (NAVD88 m):\n" + s.to_string())
    C = pd.DataFrame(comp)
    _atomic_csv(OUT / "nos_hydro_v4_compare.csv", C)
    print("\nREF - SURVEY (m, + = reference shallower):")
    print(C.round(2).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
