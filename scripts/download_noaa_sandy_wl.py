"""
Download observed water levels at NOAA CO-OPS gauges spanning the NJ coast
during Hurricane Sandy and write hydromt_sfincs GeoDataset NetCDFs.

Writes TWO files:
  noaa_sandy_nj.nc          forcing — only gauges with a COMPLETE record over
                            the sim window. This is what the boundary uses.
  noaa_sandy_validation.nc  validation — ALL gauges, including ones that failed
                            mid-storm. For comparing modeled zs vs observed at
                            obs points; NOT safe as boundary forcing.

Why the split: the Sandy Hook gauge (8531680) flooded out and stopped
reporting at 2012-10-29 23:00 — half its record is NaN. Feeding that into
the boundary collapses the forcing on the northern stretch mid-storm (the
boundary cell loses its water level and the domain drains there). The Battery
(8518750, ~5 km north, stayed online, peak 3.42 m) anchors that latitude
instead. Sandy Hook is kept for validation only.

Output schema (both files) matches `gtsm_nj_2012_10_ready.nc`:
  dims:   (time, stations)
  coord:  time, stations, lon(stations), lat(stations)
  var:    waterlevel(time, stations)  [m NAVD88]

Catalog usage after running:
    sf.water_level.create(geodataset="noaa_sandy_nj", buffer=50000)

🔴 PER-DOMAIN OUTPUT (2026-09-26). The two paths above are FIXED for the domains that
already use them (v1_monmouth, v1_5_raritan, v2_barnegat, v3: same 4 gauges, same
file, byte-for-byte the product their runs were staged from). Any other domain writes
`noaa_sandy_<domain>.nc` + `noaa_sandy_validation_<domain>.nc` beside them, with its own
station list — running this under v4 used to overwrite v3's forcing.

MLLW-only stations. CO-OPS refuses `datum=NAVD` where it has no NAVD88 tie (Ship John
Shoal, Delaware City, Burlington, Newbold: "The supported Datum values are: MHHW, MHW,
MTL, MSL, MLW, MLLW, LWI, HWI"), and their `datums.json` carries no NAVD88 row. The
NOAA VDatum web API answers MLLW->NAVD88 at the Battery / Atlantic City but returns
errorCode 412 everywhere in Delaware Bay (probed 2026-09-26, incl. Cape May / Lewes).
So such a station is fetched in MLLW and shifted by a DERIVED offset,

    NAVD88 - MLLW  =  (MSL - MLLW)_station  +  mean over neighbours of (NAVD88 - MSL)

i.e. the station's own tidal datums (same 1983-2001 NTDE) plus the mean-sea-level-to-
NAVD88 separation measured at the named NAVD88-tied neighbours. Every number is pulled
live from the CO-OPS `datums.json` endpoint and printed; the neighbours are named in the
station list. ⚠️ An ESTIMATE, not a levelling tie: across the neighbours used, (NAVD88 -
MSL) varies by ~1-4 cm, and by up to ~0.13 m between the bay mouth and the upper river.

Usage:
    NJ_DOMAIN=v4 python scripts/download_noaa_sandy_wl.py
    NJ_DOMAIN=v3 python scripts/download_noaa_sandy_wl.py --out-dir /tmp/check
A built domain's existing product is never overwritten without `--overwrite`.
"""

import argparse
import os
import time
from pathlib import Path

import pandas as pd
import requests
import xarray as xr

from nj_sfincs import domain as _domain

ROOT = Path(os.environ.get("NJ_ROOT", Path(__file__).resolve().parents[1]))
OUT_DIR = ROOT / "data/gtsm"
_DOM = _domain.active()
#: The domains that were staged from the FIXED files. Their list and paths never change.
LEGACY_DOMAINS = ("v1_monmouth", "v1_5_raritan", "v2_barnegat", "v3")
_SUFFIX = "" if _DOM.name in LEGACY_DOMAINS else f"_{_DOM.name}"
OUT_FORCING = OUT_DIR / (
    "noaa_sandy_nj.nc" if not _SUFFIX else f"noaa_sandy{_SUFFIX}.nc"
)
OUT_VALIDATION = OUT_DIR / f"noaa_sandy_validation{_SUFFIX}.nc"

# NOAA CO-OPS stations along NJ + NY Bight, north to south.
# role="forcing"    -> complete record, safe as a boundary source
# role="validation" -> incomplete record (gauge failure), validation use only
# fmt: off
STATIONS = [
    {"id": "8518750", "name": "The Battery, NY",   "lon": -74.0142, "lat": 40.7006, "role": "forcing"},
    {"id": "8531680", "name": "Sandy Hook, NJ",    "lon": -74.0091, "lat": 40.4669, "role": "validation"},  # failed 10-29 23:00
    {"id": "8534720", "name": "Atlantic City, NJ", "lon": -74.4181, "lat": 39.3550, "role": "forcing"},
    {"id": "8536110", "name": "Cape May, NJ",      "lon": -74.9600, "lat": 38.9683, "role": "forcing"},
]
# fmt: on


# ═══════════════════════════════════════════════════════════════════════════════
# v4: + the NOAA CO-OPS Delaware Bay / River gauges that ran through Sandy
# (logs/v4_design_2026-09-24/probe_sources.txt). All VALIDATION: which of them (Lewes
# and Cape May at the mouth) should force the v4 mouth line is a design decision the
# station list does not make. Bridesburg 8546252 served no data for the window.
# `navd_from` = the NAVD88-tied CO-OPS neighbours whose (NAVD88 - MSL) is transferred
# (see the module docstring); distances are straight-line.
# fmt: off
STATIONS_V4 = STATIONS + [
    {"id": "8557380", "name": "Lewes, DE",                "lon": -75.1193, "lat": 38.7828, "role": "validation"},
    {"id": "8555889", "name": "Brandywine Shoal Light",   "lon": -75.1133, "lat": 38.9867, "role": "validation",
     "datum": "MLLW", "navd_from": ["8557380", "8536110"]},  # Lewes 22 km, Cape May 17 km; record ENDS 10-29 12:00, pre-peak
    {"id": "8537121", "name": "Ship John Shoal, NJ",      "lon": -75.3767, "lat": 39.3054, "role": "validation",
     "datum": "MLLW", "navd_from": ["8557380", "8551910"]},  # Lewes 67 km, Reedy Point 29 km: the bay-axis pair
    # ⚠️ SJS is the least certain offset. Fortescue Ck (8536931, 17 km, a creek) gives
    # NAVD88-MSL +0.008 and put SJS's calm 10-01..20 mean at +0.18 m NAVD88 — ABOVE Reedy
    # Point upstream (+0.095) and far above the mouth (+0.02), which the along-bay profile
    # rules out. The Lewes/Reedy pair gives +0.068 (-> +0.12). The profile itself suggests
    # ~+0.13 (-> +0.06); the choice is worth ~0.1 m at this gauge.
    {"id": "8551910", "name": "Reedy Point, DE",          "lon": -75.5719, "lat": 39.5583, "role": "validation"},
    {"id": "8551762", "name": "Delaware City, DE",        "lon": -75.5890, "lat": 39.5822, "role": "validation",
     "datum": "MLLW", "navd_from": ["8551910"]},  # Reedy Point 3 km
    {"id": "8540433", "name": "Marcus Hook, PA",          "lon": -75.4095, "lat": 39.8118, "role": "validation"},
    {"id": "8545240", "name": "Philadelphia, PA",         "lon": -75.1420, "lat": 39.9331, "role": "validation"},
    {"id": "8539094", "name": "Burlington, NJ",           "lon": -74.8697, "lat": 40.0817, "role": "validation",
     "datum": "MLLW", "navd_from": ["8538875", "8539487"]},  # Pompeston Ck 15 km down, Fieldsboro 12 km up
    {"id": "8548989", "name": "Newbold, PA",              "lon": -74.7518, "lat": 40.1373, "role": "validation",
     "datum": "MLLW", "navd_from": ["8539487"]},  # Fieldsboro 1.3 km, across the river
]
# fmt: on
STATIONS_BY_DOMAIN = {"v4": STATIONS_V4}
if _DOM.name not in LEGACY_DOMAINS:
    STATIONS = STATIONS_BY_DOMAIN.get(_DOM.name, STATIONS)

# Sandy window — pad either side of landfall (2012-10-29 ~23:30 UTC at Atlantic City).
# v4 is wider: the upper Delaware crests ~10 h after the coast (Newbold 10-30 09:18Z).
WINDOW_BY_DOMAIN = {"v4": ("20121026", "20121102")}
BEGIN, END = WINDOW_BY_DOMAIN.get(_DOM.name, ("20121028", "20121031"))

API = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
MDAPI = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations"


def _get_json(url: str, params: dict | None = None) -> dict:
    """GET with a polite pause and backoff on 429 / 5xx."""
    delay = 5.0
    for attempt in range(6):
        time.sleep(0.5)
        r = requests.get(url, params=params, timeout=60)
        if r.status_code not in (429, 500, 502, 503, 504) or attempt == 5:
            r.raise_for_status()
            return r.json()
        print(f"    (HTTP {r.status_code}; retry in {delay:.0f} s)")
        time.sleep(delay)
        delay *= 2
    raise RuntimeError("unreachable")


def datums(station_id: str) -> dict[str, float]:
    """CO-OPS tidal datums for a station, metres on station datum."""
    j = _get_json(f"{MDAPI}/{station_id}/datums.json", {"units": "metric"})
    return {d["name"]: float(d["value"]) for d in j.get("datums") or []}


def navd_minus_mllw(st: dict) -> float:
    """Derived NAVD88 - MLLW (m) for an MLLW-only station (module docstring)."""
    own = datums(st["id"])
    if "NAVD88" in own:  # CO-OPS has since added a tie — use it, not the estimate
        print(f"    {st['id']}: CO-OPS NAVD88 tie now exists")
        return own["NAVD88"] - own["MLLW"]
    seps = {}
    for n in st["navd_from"]:
        d = datums(n)
        seps[n] = d["NAVD88"] - d["MSL"]
    sep = sum(seps.values()) / len(seps)
    off = own["MSL"] - own["MLLW"] + sep
    print(
        f"    {st['id']} {st['name']}: MSL-MLLW {own['MSL'] - own['MLLW']:.3f} + "
        f"(NAVD88-MSL) {sep:+.3f} from {seps} => NAVD88-MLLW {off:.3f} m"
    )
    return off


def fetch(st: dict) -> pd.Series:
    """Return hourly water level (m NAVD88) for one station."""
    datum = st.get("datum", "NAVD")
    params = {
        "product":    "hourly_height",
        "application": "nj_bight_sfincs",
        "begin_date": BEGIN,
        "end_date":   END,
        "datum":      datum,
        "station":    st["id"],
        "time_zone":  "gmt",
        "units":      "metric",
        "format":     "json",
    }  # fmt: skip
    j = _get_json(API, params)
    if "data" not in j:
        raise RuntimeError(f"No data for {st['id']}: {j}")
    df = pd.DataFrame(j["data"])
    df["t"] = pd.to_datetime(df["t"])
    df["v"] = pd.to_numeric(df["v"], errors="coerce")
    v = df.set_index("t")["v"].rename(st["id"])
    if datum == "MLLW":
        st["navd88_minus_mllw_m"] = navd_minus_mllw(st)
        v = v - st["navd88_minus_mllw_m"]
    return v


def build_dataset(
    stations: list[dict], series: dict[str, pd.Series], title: str
) -> xr.Dataset:
    """Assemble a (time, stations) GeoDataset from a station subset."""
    df = pd.concat([series[s["id"]] for s in stations], axis=1)
    df.columns = [s["id"] for s in stations]
    ds = xr.Dataset(
        {"waterlevel": (("time", "stations"), df.values.astype("float64"))},
        coords={
            "time": df.index.values,
            "stations": [int(s["id"]) for s in stations],
            "lon": ("stations", [s["lon"] for s in stations]),
            "lat": ("stations", [s["lat"] for s in stations]),
        },
        attrs={
            "title": title,
            "source": "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter",
            "datum": "NAVD88",
            "units": "m",
        },
    )
    ds["waterlevel"].attrs.update(units="m", datum="NAVD88")
    conv = {
        s["id"]: round(s["navd88_minus_mllw_m"], 4)
        for s in stations
        if "navd88_minus_mllw_m" in s
    }
    if conv:
        ds.attrs["mllw_stations_navd88_minus_mllw_m"] = str(conv)
        ds.attrs["mllw_conversion"] = (
            "fetched in MLLW (no CO-OPS NAVD88 tie); shifted by (MSL-MLLW) of the "
            "station + mean (NAVD88-MSL) of named NAVD88-tied CO-OPS neighbours; "
            "an estimate, see scripts/download_noaa_sandy_wl.py"
        )
    ds["lon"].attrs.update(units="degrees_east", standard_name="longitude")
    ds["lat"].attrs.update(units="degrees_north", standard_name="latitude")
    return ds


def write_atomic(ds: xr.Dataset, path: Path) -> None:
    """Write to a temp file then os.replace into place.

    netCDF/HDF5 takes an exclusive lock to write, so writing directly fails
    with PermissionError if another process (e.g. a Jupyter kernel that cached
    the file via the data catalog) holds it open. Writing to a temp file and
    atomically renaming sidesteps that — the holder keeps its old inode, new
    readers get the new file.
    """
    tmp = path.with_suffix(path.suffix + ".tmp")
    ds.to_netcdf(tmp)
    os.replace(tmp, path)


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--out-dir", type=Path, help="write both files here instead")
    ap.add_argument(
        "--overwrite",
        action="store_true",
        help="allow replacing the EXISTING files of a built (not acquisition-only) domain",
    )
    return ap.parse_args()


def main():
    args = parse_args()
    out_f, out_v = OUT_FORCING, OUT_VALIDATION
    if args.out_dir:
        out_f, out_v = args.out_dir / out_f.name, args.out_dir / out_v.name
    # 🔴 noaa_sandy_nj.nc is the base forcing four domains were staged from.
    exists = [p for p in (out_f, out_v) if p.exists()]
    if exists and not args.out_dir and not _DOM.acquisition_only and not args.overwrite:
        raise SystemExit(
            f"{exists} exist for built domain {_DOM.name!r}; use --out-dir or --overwrite"
        )
    print(f"Fetching {len(STATIONS)} NOAA stations for {BEGIN}-{END} [{_DOM.name}] ...")
    series = {s["id"]: fetch(s) for s in STATIONS}
    # Completeness is judged against the HOURS OF THE WINDOW, not the rows returned: a
    # gauge that stops reporting simply stops sending rows (Sandy Hook: 48 rows, all
    # valid), so `notna().sum() == len(v)` could never see it.
    hours = pd.date_range(
        pd.Timestamp(BEGIN), pd.Timestamp(END) + pd.Timedelta("23h"), freq="h"
    )
    n_hours = len(hours)
    for s in STATIONS:
        v = series[s["id"]]
        n_valid = int(v.reindex(hours).notna().sum())
        complete = n_valid == n_hours
        flag = (
            ""
            if complete
            else f"  <- INCOMPLETE ({n_hours - n_valid} h missing), {s['role']}-only"
        )
        conv = (
            f"  [MLLW - {s['navd88_minus_mllw_m']:.3f}]"
            if "navd88_minus_mllw_m" in s
            else ""
        )
        print(
            f"  {s['id']} {s['name']:22s}: n={n_valid}/{n_hours}  peak={v.max():.2f} m NAVD88"
            f" @ {v.idxmax()}{conv}{flag}"
        )

    out_f.parent.mkdir(parents=True, exist_ok=True)

    # Forcing file: only stations with a complete record. Guard against a
    # station silently degrading in a future re-download.
    forcing = [s for s in STATIONS if s["role"] == "forcing"]
    incomplete = [
        s
        for s in forcing
        if int(series[s["id"]].reindex(hours).notna().sum()) != n_hours
    ]
    if incomplete:
        raise RuntimeError(
            f"forcing stations have gaps: {[s['id'] for s in incomplete]} — "
            "inspect before writing the boundary file"
        )
    ds_forcing = build_dataset(
        forcing,
        series,
        "NOAA CO-OPS hourly water levels (forcing subset) — Hurricane Sandy",
    )
    write_atomic(ds_forcing, out_f)
    print(
        f"Wrote {out_f}  ({len(forcing)} stations: "
        f"{', '.join(s['id'] for s in forcing)})"
    )

    # Validation file: all stations, gaps and all.
    ds_val = build_dataset(
        STATIONS,
        series,
        "NOAA CO-OPS hourly water levels (all gauges, validation) — Hurricane Sandy",
    )
    write_atomic(ds_val, out_v)
    print(f"Wrote {out_v}  ({len(STATIONS)} stations, includes incomplete records)")


if __name__ == "__main__":
    main()
