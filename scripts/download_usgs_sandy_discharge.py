"""
Download observed river discharge at USGS NWIS gauges feeding the NJ model
domain during Hurricane Sandy and write a hydromt_sfincs GeoDataset NetCDF.

Two coastal rivers enter the active SFINCS domain and have a gauged record:

  Shark River      -> Shark River estuary / inlet (Belmar). Gauge 01407705
                      "Shark River near Neptune City" sits just W of the domain.
  Navesink/        -> Shrewsbury-Navesink estuary into Sandy Hook Bay. Gauge
  Shrewsbury          01407500 "Swimming River near Red Bank" drains the
                      Navesink headwaters.

Only DAILY-mean discharge (parameter 00060, statistic 00003) is archived for
these small gauges in 2012 — instantaneous (IV) values are not available that
far back. Daily resolution is adequate here: SFINCS interpolates the `dis`
series, and these are small flashy coastal-plain streams whose discharge
(Sandy peaks ~3.5 and ~7.9 m3/s) is a minor compound contributor next to the
multi-metre surge. We pad one day either side so the sim window is bracketed.

IMPORTANT — src placement vs gauge location:
  The point coords written here are NOT the gauge coords. They are the cell
  where each river *enters the active model domain* (a wet estuary cell,
  verified against model/gis/{mask,dep}.tif). The gauge is upstream; we neglect
  the small ungauged drainage between gauge and inflow, and (for the Navesink)
  the Swimming River gauge captures only part of the system — both
  under-estimates, acceptable for a first-pass compound run.

Output schema (hydromt_sfincs GeoDataset). NOTE the location dim is `index`,
not `stations`: discharge_points.create() reads `da.vector.index_dim` and feeds
it back to GeoDataset.from_gdf, which assumes the conventional `index` name —
a `stations` dim raises "Index dimension stations not found in data_vars".
  dims:   (time, index)
  coords: time, index, lon(index), lat(index)
  var:    discharge(time, index)  [m3/s]

Catalog usage after running:
    sf.discharge_points.create(geodataset="usgs_sandy_discharge", merge=False)
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import xarray as xr

ROOT = Path(os.environ.get("NJ_ROOT", Path(__file__).resolve().parents[1]))
# 🔴 NOT `data/discharge` — that is a SYMLINK INTO THE FROZEN ARCHIVE and is read-only.
# The archived `discharge/usgs_sandy_discharge.nc` feeds v1_monmouth and the port-
# verification fixture is pinned against it, so this script must never be able to
# rewrite it. Same rule, and same reason, as `data/elevation` vs `data/elevation_v1_5`.
OUT_DIR = ROOT / "data/discharge_v1_5"
OUT = OUT_DIR / "usgs_sandy_discharge_v1_5.nc"

CFS_TO_CMS = 0.0283168466

# Pad either side of the 2012-10-28..31 sim window so it is fully bracketed.
BEGIN = "2012-10-27"
END = "2012-11-01"

API = "https://waterservices.usgs.gov/nwis/dv/"

# site = USGS gauge id; (src_lat, src_lon) = inflow cell into the ACTIVE domain
# (wet estuary cell, NOT the gauge location — see module docstring).
STATIONS = [
    {"id": "01407705", "name": "Shark River nr Neptune City",
     "src_lon": -74.035, "src_lat": 40.195},
    {"id": "01407500", "name": "Swimming River nr Red Bank (Navesink)",
     "src_lon": -74.045, "src_lat": 40.370},

    # ── NEW in v2_barnegat: the Barnegat Bay tributaries ────────────────────────
    # The lagoon has real freshwater inflow that the v1 domain never contained.
    # Toms River is much the largest.
    #
    # Every src_lon/src_lat below was CHOSEN BY SAMPLING THE MERGED DEM and
    # taking a cell that is actually water — not the gauge coordinate, which sits
    # tens of km upstream on dry land. The sampled bed depth is noted so a future
    # elevation change that dries one of these out is obvious rather than silent.
    {"id": "01408500", "name": "Toms River nr Toms River",
     "src_lon": -74.170, "src_lat": 39.945},   # bed -2.24 m, Toms R estuary
    {"id": "01408120", "name": "N Br Metedeconk R nr Lakewood",
     "src_lon": -74.115, "src_lat": 40.056},   # bed -1.73 m, Metedeconk estuary
    {"id": "01408900", "name": "Cedar Creek nr Lanoka Harbor",
     "src_lon": -74.135, "src_lat": 39.878},   # bed < -0.5 m, Cedar Ck mouth
    {"id": "01408029", "name": "Manasquan River nr Allenwood",
     "src_lon": -74.095, "src_lat": 40.114},   # bed -0.92 m, Manasquan estuary

    # ── NEW in v1_5_raritan: the Raritan River ─────────────────────────────────
    # The domain's west limit cuts the tidal Raritan at lon -74.2993..-74.3004, and
    # until now that cut was a CLOSED WALL — a compound-flood hindcast with no river.
    # Both gauges below enter through that one cross-section, so both inflow points sit
    # in the same reach ~300 m apart; kept separate rather than summed so each gauge
    # stays independently auditable.
    #
    # 🔴 A DISCHARGE, NEVER A WATER LEVEL. An imposed ocean level across a tidal river
    # PUMPS it — the mirror of the free-outflow face that drained the Navesink — and it
    # would fight the inflow. `domain.no_waterlevel_boxes['raritan_cut']` makes a mask==2
    # cell here a build-time error.
    {"id": "01403060", "name": "Raritan R below Calco Dam at Bound Brook",
     "src_lon": -74.2997, "src_lat": 40.5090},  # bed -2.08 m (coned_sw_raritan)
    {"id": "01405030", "name": "Lawrence Brook at Westons Mills",
     "src_lon": -74.2960, "src_lat": 40.5085},  # bed -2.09 m (coned_sw_raritan)
]

# 🔴 THE UNGAUGED REMAINDER, DECLARED RATHER THAN ABSORBED.
#
# STATUS flagged 01403060 as "a LOWER BOUND: Lawrence Brook and the South River join
# below it. Check for a South River gauge rather than accept the deficit silently."
# Checked, 2026-08-14, against the NWIS site service over the Raritan basin:
#
#   01403060  Raritan R below Calco Dam       785.0 mi2   ✅ full Sandy record
#   01405030  Lawrence Brook at Westons Mills  44.9 mi2   ✅ full Sandy record
#   01405500  South River at Old Bridge        94.6 mi2   ❌ DISCONTINUED 1988-10-04
#   01405400  Manalapan Bk at Spotswood        40.7 mi2   ⚠️ record exists but reads
#                                                            0.00 cfs on 2012-10-29,
#                                                            the day the Raritan more
#                                                            than doubled. Regulated
#                                                            above Duhernal Lake; not a
#                                                            usable proxy.
#
# So the South River (94.6 mi2) is genuinely ungauged for Sandy and is NOT included.
# Gauged area feeding the cut: 829.9 mi2. Scaling the South River from the main stem's
# unit runoff at peak (3,900 cfs / 785 mi2 = 4.97 cfs/mi2) puts the missing flow at
# roughly 470 cfs ~ 13 m3/s, against a modelled peak of ~110 m3/s here.
#
# ⚠️ Deliberately NOT synthesised. Against a multi-metre surge in Raritan Bay a 13 m3/s
# deficit is immaterial (the same argument this module's docstring already makes for
# Shark River and the Navesink), and a drainage-area-ratio estimate would look like data
# in the output file while being an assumption. If it ever matters, add it as its own
# declared arm so the assumption is visible.
UNGAUGED_NOTE = "South River (94.6 mi2) ungauged for Sandy; gauge 01405500 ended 1988"


def fetch(site_id: str) -> pd.Series:
    """Return daily-mean discharge (m3/s) for one gauge over the padded window."""
    params = {
        "format": "rdb",
        "sites": site_id,
        "parameterCd": "00060",   # discharge
        "statCd": "00003",        # daily mean
        "startDT": BEGIN,
        "endDT": END,
    }
    r = requests.get(API, params=params, timeout=30)
    r.raise_for_status()
    rows = [ln.split("\t") for ln in r.text.splitlines()
            if ln and not ln.startswith("#")]
    header = rows[0]
    # discharge column is the 00060_00003 value; date is 'datetime'.
    dt_i = header.index("datetime")
    val_i = next(i for i, h in enumerate(header) if h.endswith("_00060_00003"))
    recs = [(pd.Timestamp(row[dt_i]), float(row[val_i]))
            for row in rows[2:] if len(row) > val_i and row[val_i] not in ("", "Ice")]
    s = pd.Series(dict(recs)).sort_index() * CFS_TO_CMS
    return s.rename(site_id)


def main():
    print(f"Fetching {len(STATIONS)} USGS gauges (daily discharge) {BEGIN}..{END} ...")
    series = {st["id"]: fetch(st["id"]) for st in STATIONS}
    for st in STATIONS:
        s = series[st["id"]]
        print(f"  {st['id']} {st['name']:38s}: n={len(s)}  "
              f"peak={s.max():.2f} m3/s on {s.idxmax().date()}")

    df = pd.concat([series[st["id"]] for st in STATIONS], axis=1)
    df.columns = [st["id"] for st in STATIONS]

    ds = xr.Dataset(
        {"discharge": (("time", "index"), df.values.astype("float64"))},
        coords={
            "time": df.index.values,
            "index": [int(st["id"]) for st in STATIONS],
            "lon": ("index", [st["src_lon"] for st in STATIONS]),
            "lat": ("index", [st["src_lat"] for st in STATIONS]),
        },
        attrs={
            "title": "USGS daily-mean river discharge at domain inflows — Hurricane Sandy",
            "source": "https://waterservices.usgs.gov/nwis/dv/ (00060/00003)",
            "units": "m3/s",
            "note": "point coords are the model-domain inflow cells, not the gauge sites",
        },
    )
    ds["discharge"].attrs.update(units="m3/s", long_name="river discharge")
    ds["lon"].attrs.update(units="degrees_east", standard_name="longitude")
    ds["lat"].attrs.update(units="degrees_north", standard_name="latitude")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(OUT.suffix + ".tmp")
    ds.to_netcdf(tmp)
    os.replace(tmp, OUT)
    print(f"Wrote {OUT}  ({len(STATIONS)} src points)")


if __name__ == "__main__":
    main()
