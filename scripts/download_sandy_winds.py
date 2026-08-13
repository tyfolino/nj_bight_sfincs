"""Download OBSERVED 10 m wind during Sandy, to verify a gridded wind source.

WHY (2026-08-03). The bay under-fills and the leading suspect is the wind forcing. Before
spending a 3 h solve on a wind arm, the hypothesis has to be testable against
observations — and this repo had NO observed wind at all. (Ironically
``download_ndbc_sandy_waves.py`` has parsed ``WDIR``/``WSPD``/``GST`` all along and then
dropped them at its ``["WVHT","DPD","MWD"]`` slice. The observation was one line away.)

WHAT IT ESTABLISHED. ERA5's wind MAGNITUDE over open water during Sandy is right — within
a few percent of three independent buoys. So "ERA5 is too weak" is FALSE as a blanket
statement. The defect is narrower and worse: ERA5's 10 m wind is a DIAGNOSTIC computed
from the surface-layer profile using ERA5's own LOCAL roughness, and the 0.25 deg cells
covering 4-6 km-wide Barnegat Bay are LAND cells. SFINCS then applies a marine drag law
to a forest-diagnosed wind.

⚠️ THE HEIGHT ADJUSTMENT IS AN ASSUMPTION, AND IT IS WORTH ~7%.
Buoy anemometers are not at 10 m. Each station's height is declared in ``STATIONS`` below
and the neutral log law ``U10 = U_z * ln(10/z0) / ln(z/z0)`` (z0 = 2e-4 m, open ocean) is
applied. BOTH the raw and the adjusted series are written, plus the assumed height, so a
later reader can undo or revise it. Do not quote a ratio without saying which one it is.

⚠️ NOAA 8534720 (Atlantic City) HAS NO WIND PRODUCT for 2012 — verified, do not add it.

Output: data/wind/sandy_wind_obs.nc
  dims  (time, stations); vars wspd_raw, wspd_10m, wdir; coords lon, lat, anem_height_m
"""
from __future__ import annotations

import gzip
import io
import os
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import xarray as xr

ROOT = Path(os.environ.get("NJ_ROOT", Path(__file__).resolve().parents[1]))
OUT = ROOT / "data" / "wind" / "sandy_wind_obs.nc"

BEGIN, END = "2012-10-28", "2012-10-31"

#: Open-ocean roughness for the neutral log law. 2e-4 m is a standard mid-range value;
#: the adjustment is only weakly sensitive to it (a decade in z0 moves U10 by ~3%).
Z0_SEA = 2.0e-4

#: ``kind``: "ndbc" = historical stdmet file; "coops" = NOAA CO-OPS datagetter.
#: ``anem`` = anemometer height (m). NDBC 3-m discus buoys carry the anemometer at ~4-5 m;
#: NOS shore stations are typically higher. These are the declared values used for the
#: adjustment — they are the main assumption in this file.
STATIONS = [
    dict(id="44025", kind="ndbc",  lon=-73.164, lat=40.251, anem=5.0,
         name="NDBC 44025 Long Island 30NM S of Islip"),
    dict(id="44009", kind="ndbc",  lon=-74.702, lat=38.457, anem=5.0,
         name="NDBC 44009 Delaware Bay 26NM SE of Cape May"),
    dict(id="44065", kind="ndbc",  lon=-73.703, lat=40.369, anem=5.0,
         name="NDBC 44065 New York Harbor Entrance"),
    dict(id="8531680", kind="coops", lon=-74.009, lat=40.467, anem=10.0,
         name="NOAA 8531680 Sandy Hook"),
    dict(id="8536110", kind="coops", lon=-74.960, lat=38.968, anem=10.0,
         name="NOAA 8536110 Cape May"),
]

NDBC_URL = ("https://www.ndbc.noaa.gov/view_text_file.php"
            "?filename={sid}h2012.txt.gz&dir=data/historical/stdmet/")
COOPS_API = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"

COLS = ["YY", "MM", "DD", "hh", "mm", "WDIR", "WSPD", "GST", "WVHT",
        "DPD", "APD", "MWD", "PRES", "ATMP", "WTMP", "DEWP", "VIS", "TIDE"]


def to_10m(u: np.ndarray, z: float, z0: float = Z0_SEA) -> np.ndarray:
    """Neutral log-law adjustment of a wind speed from height ``z`` to 10 m."""
    if abs(z - 10.0) < 1e-6:
        return np.asarray(u, float)
    return np.asarray(u, float) * np.log(10.0 / z0) / np.log(z / z0)


def fetch_ndbc(sid: str) -> pd.DataFrame:
    r = requests.get(NDBC_URL.format(sid=sid), timeout=90)
    r.raise_for_status()
    raw = r.content
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    df = pd.read_csv(io.BytesIO(raw), sep=r"\s+", comment="#", names=COLS, header=None)
    df["time"] = pd.to_datetime(df[["YY", "MM", "DD", "hh", "mm"]].rename(
        columns={"YY": "year", "MM": "month", "DD": "day",
                 "hh": "hour", "mm": "minute"}))
    df = df.set_index("time").sort_index().loc[BEGIN:END]
    out = df[["WSPD", "WDIR"]].astype(float)
    out.loc[out["WSPD"] >= 99.0, "WSPD"] = np.nan      # NDBC sentinels
    out.loc[out["WDIR"] >= 999.0, "WDIR"] = np.nan
    return out.rename(columns={"WSPD": "wspd_raw", "WDIR": "wdir"})


def fetch_coops(sid: str) -> pd.DataFrame:
    params = {
        "product": "wind", "station": sid,
        "begin_date": BEGIN.replace("-", ""), "end_date": END.replace("-", ""),
        "time_zone": "gmt", "units": "metric", "format": "json",
        "application": "nj_bight_sfincs",
    }
    r = requests.get(COOPS_API, params=params, timeout=90)
    r.raise_for_status()
    js = r.json()
    if "data" not in js:
        raise RuntimeError(f"no wind product for {sid}: {js.get('error', js)}")
    d = pd.DataFrame(js["data"])
    # ⚠️ .to_numpy() is REQUIRED. Passing the Series directly makes pandas ALIGN them
    # (integer RangeIndex) against the datetime index, silently producing all-NaN — which
    # reads exactly like "this station has no data" rather than like a bug.
    out = pd.DataFrame({
        "wspd_raw": pd.to_numeric(d["s"], errors="coerce").to_numpy(),
        "wdir": pd.to_numeric(d["d"], errors="coerce").to_numpy(),
    }, index=pd.to_datetime(d["t"].to_numpy()))
    return out.sort_index()


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    frames, meta = {}, []
    for st in STATIONS:
        try:
            df = fetch_ndbc(st["id"]) if st["kind"] == "ndbc" else fetch_coops(st["id"])
        except Exception as e:                       # a dead station must not kill the set
            print(f"  {st['name']:48s} FAILED: {e}")
            continue
        df = df[np.isfinite(df["wspd_raw"])]
        if df.empty:
            print(f"  {st['name']:48s} no data in window")
            continue
        df["wspd_10m"] = to_10m(df["wspd_raw"].to_numpy(), st["anem"])
        frames[st["id"]] = df
        meta.append(st)
        print(f"  {st['name']:48s} n={len(df):5d}  peak raw {df.wspd_raw.max():5.1f} "
              f"-> 10 m {df.wspd_10m.max():5.1f} m/s  (anem {st['anem']:.1f} m)")

    if not frames:
        print("nothing downloaded")
        return 1

    # ⚠️ USE THE UNION OF THE STATIONS' OWN TIMESTAMPS — never an invented grid.
    # This was `pd.date_range(BEGIN, END, freq="6min")`, and NDBC stdmet reports at :50
    # past the hour. 50 is not a multiple of 6, so every NDBC row reindexed to NaN and
    # the file was written with three all-NaN stations — after the console had already
    # printed their correct peaks. The failure was invisible until a downstream ratio
    # came back NaN. Same class as the pandas index-alignment bug in fetch_coops.
    idx = pd.DatetimeIndex(sorted(set().union(*(f.index for f in frames.values()))))
    ids = [m["id"] for m in meta]
    ds = xr.Dataset(
        {
            v: (("time", "stations"),
                np.column_stack([frames[i][v].reindex(idx).to_numpy() for i in ids]))
            for v in ("wspd_raw", "wspd_10m", "wdir")
        },
        coords={
            "time": idx, "stations": ids,
            "lon": ("stations", [m["lon"] for m in meta]),
            "lat": ("stations", [m["lat"] for m in meta]),
            "anem_height_m": ("stations", [m["anem"] for m in meta]),
            "name": ("stations", [m["name"] for m in meta]),
        },
        attrs={
            "title": "Observed wind during Hurricane Sandy (NDBC stdmet + NOAA CO-OPS)",
            "height_adjustment": (f"neutral log law to 10 m, z0={Z0_SEA} m; "
                                  "anem_height_m records the assumed sensor height"),
            "note": ("wspd_raw is AS REPORTED at anem_height_m; wspd_10m is adjusted. "
                     "Quote which one you mean. NOAA 8534720 Atlantic City has no wind "
                     "product for 2012."),
        },
    )
    ds["wspd_raw"].attrs.update(units="m s-1", long_name="wind speed at sensor height")
    ds["wspd_10m"].attrs.update(units="m s-1", long_name="wind speed adjusted to 10 m")
    ds["wdir"].attrs.update(units="degrees", long_name="wind direction (coming from)")
    ds.to_netcdf(OUT)
    print(f"\nwrote {OUT}  ({len(ids)} stations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
