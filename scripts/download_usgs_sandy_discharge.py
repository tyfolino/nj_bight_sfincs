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
# 🔴 PER-DOMAIN OUTPUT AND PER-DOMAIN SITE LIST.
# This script used ONE global SITES list and ONE hardcoded output path. Running it under
# a new domain would therefore have silently rewritten v1.5's forcing file with a
# different set of sources — invisibly changing a frozen domain's inputs. v1_5_raritan
# keeps its literal path and its list byte-identical; anything new gets its own.
from nj_sfincs import domain as _domain_out  # noqa: E402
_DOM = _domain_out.active()
if _DOM.name == "v1_5_raritan":
    OUT_DIR = ROOT / "data/discharge_v1_5"
    OUT = OUT_DIR / "usgs_sandy_discharge_v1_5.nc"
else:
    OUT_DIR = _domain_out.acquisition_dir("discharge")
    OUT = OUT_DIR / f"usgs_sandy_discharge_{_DOM.name}.nc"

CFS_TO_CMS = 0.0283168466

# Pad either side of the 2012-10-28..31 sim window so it is fully bracketed.
BEGIN = "2012-10-27"
END = "2012-11-01"

API = "https://waterservices.usgs.gov/nwis/dv/"

# site = USGS gauge id; (src_lat, src_lon) = inflow cell into the ACTIVE domain
# (wet estuary cell, NOT the gauge location — see module docstring).
STATIONS_V1_5 = [
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

# ═══════════════════════════════════════════════════════════════════════════════
# v3 — the full Jersey shore. Same gauges, but the SRC POINTS move with the ring.
# ═══════════════════════════════════════════════════════════════════════════════
# 🔴 A SRC POINT IS NOT A PROPERTY OF THE RIVER, IT IS A PROPERTY OF THE RING. It has to
# sit ON the cut where the region boundary crosses the channel. v1.5's Toms River src at
# (-74.170, 39.945) was placed for a different ring and lies 1.5 km EAST of — i.e. INSIDE
# — v3's cut, which would leave the reach between cut and src with no inflow while the cut
# itself carried a water-level BC. Measured on the merged bed, 2026-08-24:
#     old src  (-74.1700, 39.9450)  bed -2.29 m   ← inside v3's ring, wrong side of the cut
#     v3 cut   (-74.1878, 39.9460)  bed -1.72 m   ← WET+ACTIVE, and where the ring crosses
#     +200 m E (-74.1855, 39.9460)  bed -0.08 m   ← too shallow, do not drift east
#
# ⚠️ THE UNGAUGED REMAINDER FOR TOMS RIVER. `01408500` is DA 123 mi2 and is the ONLY Toms
# River gauge with an Oct-2012 record — checked against NWIS over the basin, both daily
# and instantaneous. **Wrangle Brook is ungauged**, and the user confirmed (2026-08-24,
# from imagery) that the v3 cut lies BELOW its confluence, so Wrangle Brook's catchment is
# outside the domain and its flow is missing. Moving the cut ABOVE the confluence was
# considered and rejected: with no Wrangle Brook gauge it buys no data and turns one
# declared crossing into two, the second wholly ungauged. State it as a lower bound, the
# way 01403060 is stated for the Raritan.
# ⭐ v3 (2026-08-24): the ring crosses EVERY river at its head of tide on dry ground, so
# there is no cut to put a source on — each source sits AT ITS GAUGE, inside the ring.
# Coordinates are NWIS `dec_lat_va/dec_long_va`. Two v1.5 sources stay at their v1.5
# points (Shark, Navesink) because that stretch of ring is unchanged.
# Lower bounds, declared: Toms excludes nothing now (Wrangle Brook joins INSIDE the ring,
# ungauged but rained on); the Mullica sum omits Batsto River (01409500, 67.8 mi2 — NO
# Sandy record) and the Great Egg omits the Middle River (ungauged).
STATIONS_V3 = [
    # The Raritan cut is v1.5's, verbatim: same ring vertices, same NoWaterLevelBox, same
    # two sources AT THE CUT (it is the one crossing on v3 that is still on tidal water).
    {"id": "01403060", "name": "Raritan R below Calco Dam at Bound Brook",
     "src_lon": -74.2997, "src_lat": 40.5090},
    {"id": "01405030", "name": "Lawrence Brook at Westons Mills",
     "src_lon": -74.2960, "src_lat": 40.5085},
    {"id": "01407705", "name": "Shark River nr Neptune City",
     "src_lon": -74.035, "src_lat": 40.195},
    {"id": "01407500", "name": "Swimming River nr Red Bank (Navesink)",
     "src_lon": -74.045, "src_lat": 40.370},
    {"id": "01408029", "name": "Manasquan River nr Allenwood",
     "src_lon": -74.1222, "src_lat": 40.1467},   # at the gauge (ring moved west of it)
    {"id": "01408120", "name": "N Br Metedeconk R nr Lakewood",
     "src_lon": -74.1525, "src_lat": 40.0917},   # at the gauge
    {"id": "01408151", "name": "S Br Metedeconk R at New Hampshire Av nr Lakewood",
     "src_lon": -74.1797, "src_lat": 40.0831},
    {"id": "01408500", "name": "Toms River nr Toms River",
     "src_lon": -74.2233, "src_lat": 39.9864},   # at the gauge; cut is dry (+3.6 m)
    {"id": "01408900", "name": "Cedar Creek at Western Blvd nr Lanoka Harbor",
     "src_lon": -74.1906, "src_lat": 39.8792},
    {"id": "01409095", "name": "Oyster Creek nr Brookville",
     "src_lon": -74.2503, "src_lat": 39.7983},
    {"id": "01409210", "name": "Mill Ck at Manahawkin",
     "src_lon": -74.2597, "src_lat": 39.6953},
    {"id": "01409280", "name": "Westecunk Creek at Stafford Forge",
     "src_lon": -74.3203, "src_lat": 39.6667},
    {"id": "01409810", "name": "W Br Wading River nr Jenkins",
     "src_lon": -74.5481, "src_lat": 39.6881},
    {"id": "01410000", "name": "Oswego River at Harrisville",
     "src_lon": -74.5234, "src_lat": 39.6639},
    {"id": "01409400", "name": "Mullica River nr Batsto",
     "src_lon": -74.6650, "src_lat": 39.6744},
    {"id": "01410150", "name": "E Br Bass River nr New Gretna",
     "src_lon": -74.4414, "src_lat": 39.6231},
    {"id": "01410500", "name": "Absecon Creek at Absecon",
     "src_lon": -74.5206, "src_lat": 39.4303},
    {"id": "01411000", "name": "Great Egg Harbor River at Folsom",
     "src_lon": -74.7350, "src_lat": 39.4650},   # gauge OUTSIDE; src at the Mays Landing cut
    {"id": "01411300", "name": "Tuckahoe River at Head of River",
     "src_lon": -74.8206, "src_lat": 39.3069},
]
STATIONS_BY_DOMAIN = {"v1_5_raritan": STATIONS_V1_5, "v3": STATIONS_V3}
#: ⚠️ Unknown domains fall back to the v1.5 list rather than to an empty one: an empty
#: list would write a VALID NetCDF with no sources, i.e. a silent no-river run.
STATIONS = STATIONS_BY_DOMAIN.get(_DOM.name, STATIONS_V1_5)

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
