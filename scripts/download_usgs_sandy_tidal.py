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

SOURCE (2026-09-26): the USGS Water Data OGC API `continuous` collection
(`nj_sfincs/usgs_ogc.py`) — the instantaneous values the retired
`waterservices.usgs.gov/nwis/iv` served, timestamps in UTC. The port was checked by
re-fetching the v1 and v3 lists into a scratch file and diffing against the products on
disk.

Usage:
    NJ_DOMAIN=v4 python scripts/download_usgs_sandy_tidal.py
    NJ_DOMAIN=v3 python scripts/download_usgs_sandy_tidal.py --out /tmp/check.nc
A built domain's existing product is never overwritten without `--overwrite`.
"""

import argparse
import os
from pathlib import Path

import pandas as pd
import xarray as xr

from nj_sfincs import usgs_ogc

ROOT = Path(os.environ.get("NJ_ROOT", Path(__file__).resolve().parents[1]))
OUT_DIR = ROOT / "data/gtsm"

# Per-domain station list + output (2026-08-24). The v1/v1.5 file stays byte-identical
# under its old name; v3 writes its own, beside naccs_sandy_<domain>.nc.
from nj_sfincs import domain as _domain  # noqa: E402

_DOM = _domain.active()
OUT = OUT_DIR / (
    "usgs_sandy_tidal_nj.nc"
    if _DOM.name in _domain.ARCHIVED_TIER_DOMAINS
    else f"usgs_sandy_tidal_{_DOM.name}.nc"
)

FT_TO_M = 0.3048
PARM = "72279"  # Tidal elevation, NOS-averaged, NAVD88, feet
# v4 widens the window so the Delaware's later crest (Newbold 10-30 09:18Z) and the
# ebb after it are inside; the older domains keep theirs so their products reproduce.
WINDOW_BY_DOMAIN = {"v4": ("2012-10-26T00:00:00Z", "2012-11-02T00:00:00Z")}
BEGIN, END = WINDOW_BY_DOMAIN.get(
    _DOM.name, ("2012-10-27T00:00:00Z", "2012-10-31T12:00:00Z")
)
API = f"{usgs_ogc.BASE}/collections/continuous/items"

# fmt: off
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

# v3 (2026-08-24): every NWIS site in lat 38.85-39.80 with parameter 72279 over
# 2012-10-27..31, probed directly (n = 6-min samples in the window). ⚠️ Unlike the four
# above, most of these run THROUGH the peak, so on v3 a station's own record length
# decides what it is good for (interior holdout vs tide-only check), not the file note.
# Sluice Creek (South Dennis) is Delaware Bay side, outside the ring; kept so the region
# clip is what drops it.
STATIONS_V3 = STATIONS + [
    {"id": "01409146", "name": "East Thorofare at Ship Bottom NJ",        "lon": -74.1858, "lat": 39.6542},  # n=714
    {"id": "01409335", "name": "Little Egg Inlet near Tuckerton NJ",      "lon": -74.3247, "lat": 39.5089},  # n=960
    {"id": "01410510", "name": "Absecon Creek at Absecon NJ",             "lon": -74.5000, "lat": 39.4231},  # n=958
    {"id": "01410560", "name": "Inside Thorofare at Atlantic City NJ",    "lon": -74.4569, "lat": 39.3536},  # n=958
    {"id": "01410600", "name": "Absecon Channel at Atlantic City NJ",     "lon": -74.4236, "lat": 39.3778},  # n=480
    {"id": "01411320", "name": "Great Egg Harbor Bay at Ocean City NJ",   "lon": -74.5756, "lat": 39.2858},  # n=720
    {"id": "01411350", "name": "Ludlum Thorofare at Sea Isle City NJ",    "lon": -74.6978, "lat": 39.1578},  # n=960
    {"id": "01411355", "name": "Ingram Thorofare at Avalon NJ",           "lon": -74.7419, "lat": 39.1086},  # n=720
    {"id": "01411360", "name": "Great Channel at Stone Harbor NJ",        "lon": -74.7650, "lat": 39.0569},  # n=960
    {"id": "01411390", "name": "Cape May Harbor at Cape May NJ",          "lon": -74.8889, "lat": 38.9483},  # n=471
    {"id": "01411435", "name": "Sluice Creek at South Dennis NJ",         "lon": -74.8322, "lat": 39.1617},  # n=1188, Delaware Bay side
]
# fmt: on

# ═══════════════════════════════════════════════════════════════════════════════
# v4 (2026-09-26): v3's list + every USGS estuary / tidal-stream site in the v4 box
# (lon -75.75..-73.55, lat 38.70..41.00) with an INSTANTANEOUS series already in NAVD88
# over the window, found through the OGC `time-series-metadata` + `monitoring-locations`
# collections (site types ES and ST-TS). Three parameter codes qualify:
#   72279  tidal elevation, NOS-averaged, NAVD88, ft          (as v1-v3)
#   62620  estuary / ocean water surface elevation, NAVD88, ft
#   63160  stream water level elevation, NAVD88, ft
#   00065  gage height, ft — ONLY where `monitoring-locations` gives the gage datum as
#          altitude 0.0 ft, vertical_datum NAVD88, i.e. gage height IS NAVD88 feet.
#          `gage_datum_ft` records that 0.0 and where it came from; it is ADDED.
# NOT included: Beach Thorofare at Margate 01411330 and Hackensack R at Hackensack
# 01378570 — listed with a 72279 series spanning 2012 but NO values in the window;
# 62619 (NGVD29) series; 00065 at Red Lion Ck 01482320 (datum NGVD29) and
# Little Egg Inlet nr Beach Haven Hts 01409334 (no datum); reservoir levels (62614/62615);
# the Long Island south-shore / Jamaica Bay / LI Sound sites (shut basins); Barnegat
# Inlet 01409147 and Manahawkin Bay 0140914550 (no datum). The USGS Delaware main-stem
# stations run by NOAA are in download_noaa_sandy_wl.py instead.
# Record length decides what each is good for, exactly as on v3 (the fetch reports it).
# fmt: off
STATIONS_V4 = STATIONS_V3 + [
    {"id": "01412150", "name": "Maurice River at Bivalve NJ",               "lon": -75.0328, "lat": 39.2325},
    {"id": "01413038", "name": "Cohansey River at Greenwich NJ",            "lon": -75.3503, "lat": 39.3836},
    {"id": "01409110", "name": "Barnegat Bay at Waretown NJ",               "lon": -74.1819, "lat": 39.7911, "parm": "00065", "gage_datum_ft": 0.0},
    {"id": "01408043", "name": "Point Pleasant Canal at Point Pleasant NJ", "lon": -74.0594, "lat": 40.0708, "parm": "00065", "gage_datum_ft": 0.0},
    {"id": "01408050", "name": "Manasquan River at Point Pleasant NJ",      "lon": -74.0375, "lat": 40.1017, "parm": "00065", "gage_datum_ft": 0.0},
    {"id": "01407081", "name": "Raritan Bay at Keansburg NJ",               "lon": -74.1475, "lat": 40.4492},
    {"id": "01406710", "name": "Raritan River at South Amboy NJ",           "lon": -74.2817, "lat": 40.4922, "parm": "00065", "gage_datum_ft": 0.0},
    {"id": "01392650", "name": "Newark Bay at PVSC at Newark NJ",           "lon": -74.1229, "lat": 40.7113},
    {"id": "01311875", "name": "Rockaway Inlet nr Floyd Bennett Field NY",  "lon": -73.8855, "lat": 40.5742, "parm": "62620"},  # on the rockaway_inlet forced line
    {"id": "01484080", "name": "Murderkill River at Frederica DE",          "lon": -75.4583, "lat": 39.0105, "parm": "62620"},
    {"id": "01484085", "name": "Murderkill River at Bowers DE",             "lon": -75.3976, "lat": 39.0583, "parm": "00065", "gage_datum_ft": 0.0},
    {"id": "01482170", "name": "Delaware River at New Castle DE",           "lon": -75.5869, "lat": 39.6514, "parm": "63160"},
    {"id": "01480065", "name": "Christina River at Newport DE",             "lon": -75.6087, "lat": 39.7106, "parm": "00065", "gage_datum_ft": 0.0},
    {"id": "01480120", "name": "Christina River at Wilmington DE",          "lon": -75.5406, "lat": 39.7361, "parm": "00065", "gage_datum_ft": 0.0},
]
# fmt: on
STATIONS_BY_DOMAIN = {"v4": STATIONS_V4}
if _DOM.name not in _domain.ARCHIVED_TIER_DOMAINS:
    STATIONS = STATIONS_BY_DOMAIN.get(_DOM.name, STATIONS_V3)


def fetch(st: dict) -> tuple[pd.Series, pd.Series]:
    """Instantaneous water level (m NAVD88) and approval status for one gauge."""
    parm = st.get("parm", PARM)
    df = usgs_ogc.continuous(st["id"], parm, "ft", BEGIN, END)
    ft = df["value"] + st.get("gage_datum_ft", 0.0)
    return (ft * FT_TO_M).rename(st["id"]), df["approval"].rename(st["id"])


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--out", type=Path, help="write here instead of the domain product")
    ap.add_argument(
        "--overwrite",
        action="store_true",
        help="allow replacing an EXISTING product of a built (not acquisition-only) domain",
    )
    return ap.parse_args()


def main():
    args = parse_args()
    out = args.out or OUT
    # 🔴 A built domain's validation file is what its scored runs were scored against.
    if (
        out.exists()
        and not args.out
        and not _DOM.acquisition_only
        and not args.overwrite
    ):
        raise SystemExit(
            f"{out} exists for built domain {_DOM.name!r}; use --out or --overwrite"
        )
    print(
        f"Fetching {len(STATIONS)} USGS tidal gauges (NAVD88) {BEGIN}..{END} [{_DOM.name}] ..."
    )
    series, approval = {}, {}
    for st in STATIONS:
        series[st["id"]], approval[st["id"]] = fetch(st)
    for st in STATIONS:
        s = series[st["id"]]
        parm = st.get("parm", PARM)
        if len(s):
            # Sandy's NJ crest is ~2012-10-30 00:00-06:00Z. Say which side of it
            # the record actually ends on rather than asserting "pre-storm" for
            # every gauge — two of these four DO survive the peak, and that is
            # the entire reason they are here.
            crest = pd.Timestamp("2012-10-30 00:00")
            note = (
                "captures the peak"
                if s.index[-1] > crest
                else "PRE-STORM only; record ends before the peak"
            )
            # "Ends after the crest" is not "saw the crest": several records have a
            # ~1-day hole across it (Keansburg, Little Egg, Absecon Ck, Stone Harbor...).
            before, after = s.index[s.index <= crest], s.index[s.index > crest]
            if (
                len(before)
                and len(after)
                and after[0] - before[-1] > pd.Timedelta("1h")
            ):
                note = f"record continues, but a GAP {before[-1]} .. {after[0]} spans the crest"
            prov = int((approval[st["id"]] != "Approved").sum())
            note += f"; {prov} provisional" if prov else ""
            print(
                f"  {st['id']} {st['name'][:40]:40s} [{parm}]: n={len(s)}  span {s.index[0]} .. {s.index[-1]}  "
                f"max={s.max():.2f} m @ {s.idxmax()} ({note})"
            )
        else:
            print(f"  {st['id']} {st['name'][:40]:40s} [{parm}]: NO DATA returned")

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
            "source": f"USGS Water Data OGC API: {API} (72279 unless noted per station)",
            "datum": "NAVD88",
            "units": "m",
            "note": (
                "v1/v1.5 stations: uv record ends 2012-10-28 23:54, ~24 h before the storm peak — "
                "tidal check only. v3 southern stations mostly run through the peak; "
                "judge each by its own record length."
            ),
        },
    )
    ds["waterlevel"].attrs.update(
        units="m", datum="NAVD88", long_name="tidal water surface elevation"
    )
    ds["lon"].attrs.update(units="degrees_east", standard_name="longitude")
    ds["lat"].attrs.update(units="degrees_north", standard_name="latitude")

    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    ds.to_netcdf(tmp)
    os.replace(tmp, out)
    print(f"Wrote {out}  ({len(STATIONS)} stations)")


if __name__ == "__main__":
    main()
