"""
Download observed tidal water level at the two USGS NWIS estuary gauges that
sit INSIDE the NJ model domain during Hurricane Sandy, for validation.

  01407770  Shark River at Belmar NJ        (40.186, -74.026)  -> southern domain
  01407600  Shrewsbury River at Sea Bright  (40.366, -73.975)  -> mid-north back-bay

Parameter 72279 = "Tidal elevation, NOS-averaged, NAVD88, feet" -> already NAVD88
(converted to metres here), so it is directly comparable to the model `point_zs`.

IMPORTANT — these records do NOT reach Sandy's peak.
  The instantaneous (uv) record for BOTH gauges stops at 2012-10-28 23:54, ~24 h
  before the storm peak (~10-29 23:00 .. 10-30 01:00 UTC). Every permanent coastal
  gauge in the domain (incl. NOAA Sandy Hook) failed mid-storm. So this product is
  for a PRE-STORM TIDAL check only — does the model reproduce tidal range/phase at
  the open coast (40.37) and the south (40.19)? — NOT for validating the surge peak.
  The post-storm USGS HWMs remain the peak/spatial validation.

Output schema (hydromt GeoDataset, mirrors noaa_sandy_validation.nc):
  dims:   (time, stations)
  coords: time, stations(int site no.), lon(stations), lat(stations)
  var:    waterlevel(time, stations)  [m NAVD88]

Catalog entry to add (data/data_catalog.yml): `usgs_sandy_tidal_nj` (GeoDataset).
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import xarray as xr

ROOT = Path(os.environ.get("NJ_ROOT", Path(__file__).resolve().parents[1]))
OUT_DIR = ROOT / "data/gtsm"
OUT = OUT_DIR / "usgs_sandy_tidal_nj.nc"

FT_TO_M = 0.3048
PARM = "72279"            # Tidal elevation, NOS-averaged, NAVD88, feet
BEGIN = "2012-10-27T00:00Z"
END = "2012-10-31T12:00Z"
API = "https://waterservices.usgs.gov/nwis/iv/"

STATIONS = [
    # ── v1 domain: PRE-STORM tide only. Both records end ~2012-10-29 04:00, so
    # they constrain tidal range and phase but say nothing about the peak.
    {"id": "01407770", "name": "Shark River at Belmar NJ",       "lon": -74.0261, "lat": 40.1856},
    {"id": "01407600", "name": "Shrewsbury River at Sea Bright", "lon": -73.9747, "lat": 40.3656},

    # ── NEW in v2_barnegat: the first interior gauges in this project that SURVIVE
    # SANDY'S PEAK. Every permanent gauge inside the v1 domain failed mid-storm,
    # which is why the peak has only ever been scored against high-water marks
    # plus a single open-coast wave sensor.
    #
    # These two are complete 6-min records straight through the crest, and the
    # pair is worth more than either alone: Mantoloking sits 35 km up the lagoon
    # from the inlet and peaks 0.52 m HIGHER and ~6 h LATER than Barnegat Light
    # just inside it. Level plus timing at both ends of a lagoon is a direct
    # constraint on bay conveyance and inlet exchange — the quantity the tidal-
    # phase and bay-amplification work has had no interior data to test.
    #
    #   01408168  721 pts, max gap  6 min, peak 2.11 m NAVD88 @ 2012-10-30 06:18Z
    #   01409125  708 pts, max gap 18 min, peak 1.59 m NAVD88 @ 2012-10-30 00:24Z
    {"id": "01408168", "name": "Barnegat Bay at Mantoloking NJ", "lon": -74.0544, "lat": 40.0406},
    {"id": "01409125", "name": "Barnegat Bay at Barnegat Light", "lon": -74.1106, "lat": 39.7608},
    # NOT included: 01409146 East Thorofare at Ship Bottom. Its record ends
    # 2012-10-28 (pre-peak) AND it lies south of the 39.70 domain edge.
]


def fetch(site_id: str) -> pd.Series:
    """Return instantaneous tidal elevation (m NAVD88) for one gauge."""
    params = {
        "format": "json", "sites": site_id, "parameterCd": PARM,
        "startDT": BEGIN, "endDT": END,
    }
    j = requests.get(API, params=params, timeout=60).json()
    ts = j["value"]["timeSeries"]
    if not ts:
        return pd.Series(dtype="float64", name=site_id)
    t = ts[0]
    nd = float(t["variable"]["noDataValue"])
    recs = [(pd.Timestamp(p["dateTime"]).tz_convert("UTC").tz_localize(None), float(p["value"]))
            for p in t["values"][0]["value"]
            if p["value"] not in (None, "") and float(p["value"]) != nd]
    s = pd.Series(dict(recs)).sort_index() * FT_TO_M
    return s.rename(site_id)


def main():
    print(f"Fetching {len(STATIONS)} USGS tidal gauges (param {PARM}, NAVD88) {BEGIN}..{END} ...")
    series = {st["id"]: fetch(st["id"]) for st in STATIONS}
    for st in STATIONS:
        s = series[st["id"]]
        if len(s):
            # Sandy's NJ crest is ~2012-10-30 00:00-06:00Z. Say which side of it
            # the record actually ends on rather than asserting "pre-storm" for
            # every gauge — two of these four DO survive the peak, and that is
            # the entire reason they are here.
            crest = pd.Timestamp("2012-10-30 00:00")
            note = ("captures the peak" if s.index[-1] > crest
                    else "PRE-STORM only; record ends before the peak")
            print(f"  {st['id']} {st['name']:34s}: n={len(s)}  span {s.index[0]} .. {s.index[-1]}  "
                  f"max={s.max():.2f} m ({note})")
        else:
            print(f"  {st['id']} {st['name']:34s}: NO DATA returned")

    # union time index across gauges (records may differ slightly)
    df = pd.concat([series[st["id"]] for st in STATIONS], axis=1)
    df.columns = [st["id"] for st in STATIONS]

    ds = xr.Dataset(
        {"waterlevel": (("time", "stations"), df.values.astype("float64"))},
        coords={
            "time": df.index.values,
            "stations": [int(st["id"]) for st in STATIONS],
            "lon": ("stations", [st["lon"] for st in STATIONS]),
            "lat": ("stations", [st["lat"] for st in STATIONS]),
        },
        attrs={
            "title": "USGS in-domain tidal gauges (NAVD88) — Hurricane Sandy PRE-STORM only",
            "source": "https://waterservices.usgs.gov/nwis/iv/ (parameter 72279)",
            "datum": "NAVD88", "units": "m",
            "note": "uv record ends 2012-10-28 23:54, ~24 h before the storm peak — tidal check only",
        },
    )
    ds["waterlevel"].attrs.update(units="m", datum="NAVD88", long_name="tidal water surface elevation")
    ds["lon"].attrs.update(units="degrees_east", standard_name="longitude")
    ds["lat"].attrs.update(units="degrees_north", standard_name="latitude")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(OUT.suffix + ".tmp")
    ds.to_netcdf(tmp)
    os.replace(tmp, OUT)
    print(f"Wrote {OUT}  ({len(STATIONS)} stations)")


if __name__ == "__main__":
    main()
