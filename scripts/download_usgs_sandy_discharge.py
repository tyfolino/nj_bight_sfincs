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

SOURCE (2026-09-26): the USGS Water Data OGC API `daily` collection
(`nj_sfincs/usgs_ogc.py`), parameter 00060, statistic 00003 — the same daily means the
retired `waterservices.usgs.gov/nwis/dv` served. The port was checked by re-fetching the
v1.5 and v3 lists into a scratch file and diffing against the products on disk.

Usage:
    NJ_DOMAIN=v4 python scripts/download_usgs_sandy_discharge.py
    NJ_DOMAIN=v3 python scripts/download_usgs_sandy_discharge.py --out /tmp/check.nc
A built domain's existing product is never overwritten without `--overwrite`.
"""

import argparse
import os
from pathlib import Path

import pandas as pd
import xarray as xr

from nj_sfincs import usgs_ogc

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


def default_out() -> Path:
    """The domain's product path. Resolved lazily: `acquisition_dir` refuses a frozen
    domain, and a `--out` check run must not need a writable domain."""
    if _DOM.name == "v1_5_raritan":
        return ROOT / "data/discharge_v1_5" / "usgs_sandy_discharge_v1_5.nc"
    d = _domain_out.acquisition_dir("discharge")  # data/discharge_<domain>
    return d / f"usgs_sandy_discharge_{_DOM.name}.nc"


CFS_TO_CMS = 0.0283168466

# Pad either side of the 2012-10-28..31 sim window so it is fully bracketed. v4 uses the
# wider 10-26..11-02 window its site list was chosen on (a gauge had to have a daily
# record over all of it); the older domains keep theirs so their products reproduce.
WINDOW_BY_DOMAIN = {"v4": ("2012-10-26", "2012-11-02")}
BEGIN, END = WINDOW_BY_DOMAIN.get(_DOM.name, ("2012-10-27", "2012-11-01"))

API = f"{usgs_ogc.BASE}/collections/daily/items (00060/00003)"

# site = USGS gauge id; (src_lat, src_lon) = inflow cell into the ACTIVE domain
# (wet estuary cell, NOT the gauge location — see module docstring).
STATIONS_V1_5 = [
    {
        "id": "01407705",
        "name": "Shark River nr Neptune City",
        "src_lon": -74.035,
        "src_lat": 40.195,
    },
    {
        "id": "01407500",
        "name": "Swimming River nr Red Bank (Navesink)",
        "src_lon": -74.045,
        "src_lat": 40.370,
    },
    # ── NEW in v2_barnegat: the Barnegat Bay tributaries ────────────────────────
    # The lagoon has real freshwater inflow that the v1 domain never contained.
    # Toms River is much the largest.
    #
    # Every src_lon/src_lat below was CHOSEN BY SAMPLING THE MERGED DEM and
    # taking a cell that is actually water — not the gauge coordinate, which sits
    # tens of km upstream on dry land. The sampled bed depth is noted so a future
    # elevation change that dries one of these out is obvious rather than silent.
    {
        "id": "01408500",
        "name": "Toms River nr Toms River",
        "src_lon": -74.170,
        "src_lat": 39.945,
    },  # bed -2.24 m, Toms R estuary
    {
        "id": "01408120",
        "name": "N Br Metedeconk R nr Lakewood",
        "src_lon": -74.115,
        "src_lat": 40.056,
    },  # bed -1.73 m, Metedeconk estuary
    {
        "id": "01408900",
        "name": "Cedar Creek nr Lanoka Harbor",
        "src_lon": -74.135,
        "src_lat": 39.878,
    },  # bed < -0.5 m, Cedar Ck mouth
    {
        "id": "01408029",
        "name": "Manasquan River nr Allenwood",
        "src_lon": -74.095,
        "src_lat": 40.114,
    },  # bed -0.92 m, Manasquan estuary
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
    {
        "id": "01403060",
        "name": "Raritan R below Calco Dam at Bound Brook",
        "src_lon": -74.2997,
        "src_lat": 40.5090,
    },  # bed -2.08 m (coned_sw_raritan)
    {
        "id": "01405030",
        "name": "Lawrence Brook at Westons Mills",
        "src_lon": -74.2960,
        "src_lat": 40.5085,
    },  # bed -2.09 m (coned_sw_raritan)
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
    {
        "id": "01403060",
        "name": "Raritan R below Calco Dam at Bound Brook",
        "src_lon": -74.2997,
        "src_lat": 40.5090,
    },
    {
        "id": "01405030",
        "name": "Lawrence Brook at Westons Mills",
        "src_lon": -74.2960,
        "src_lat": 40.5085,
    },
    {
        "id": "01407705",
        "name": "Shark River nr Neptune City",
        "src_lon": -74.035,
        "src_lat": 40.195,
    },
    {
        "id": "01407500",
        "name": "Swimming River nr Red Bank (Navesink)",
        "src_lon": -74.045,
        "src_lat": 40.370,
    },
    {
        "id": "01408029",
        "name": "Manasquan River nr Allenwood",
        "src_lon": -74.1222,
        "src_lat": 40.1467,
    },  # at the gauge (ring moved west of it)
    {
        "id": "01408120",
        "name": "N Br Metedeconk R nr Lakewood",
        "src_lon": -74.1525,
        "src_lat": 40.0917,
    },  # at the gauge
    {
        "id": "01408151",
        "name": "S Br Metedeconk R at New Hampshire Av nr Lakewood",
        "src_lon": -74.1797,
        "src_lat": 40.0831,
    },
    {
        "id": "01408500",
        "name": "Toms River nr Toms River",
        "src_lon": -74.2233,
        "src_lat": 39.9864,
    },  # at the gauge; cut is dry (+3.6 m)
    {
        "id": "01408900",
        "name": "Cedar Creek at Western Blvd nr Lanoka Harbor",
        "src_lon": -74.1906,
        "src_lat": 39.8792,
    },
    {
        "id": "01409095",
        "name": "Oyster Creek nr Brookville",
        "src_lon": -74.2503,
        "src_lat": 39.7983,
    },
    {
        "id": "01409210",
        "name": "Mill Ck at Manahawkin",
        "src_lon": -74.2597,
        "src_lat": 39.6953,
    },
    {
        "id": "01409280",
        "name": "Westecunk Creek at Stafford Forge",
        "src_lon": -74.3203,
        "src_lat": 39.6667,
    },
    {
        "id": "01409810",
        "name": "W Br Wading River nr Jenkins",
        "src_lon": -74.5481,
        "src_lat": 39.6881,
    },
    {
        "id": "01410000",
        "name": "Oswego River at Harrisville",
        "src_lon": -74.5234,
        "src_lat": 39.6639,
    },
    {
        "id": "01409400",
        "name": "Mullica River nr Batsto",
        "src_lon": -74.6650,
        "src_lat": 39.6744,
    },
    {
        "id": "01410150",
        "name": "E Br Bass River nr New Gretna",
        "src_lon": -74.4414,
        "src_lat": 39.6231,
    },
    {
        "id": "01410500",
        "name": "Absecon Creek at Absecon",
        "src_lon": -74.5206,
        "src_lat": 39.4303,
    },
    {
        "id": "01411000",
        "name": "Great Egg Harbor River at Folsom",
        "src_lon": -74.7350,
        "src_lat": 39.4650,
    },  # gauge OUTSIDE; src at the Mays Landing cut
    {
        "id": "01411300",
        "name": "Tuckahoe River at Head of River",
        "src_lon": -74.8206,
        "src_lat": 39.3069,
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
# v4 — v3 + the Delaware estuary, the Raritan to Manville, Newark Bay / Passaic /
# Hackensack. 🔴 PROVISIONAL: the ring (data/v4_design/region_v4_vertices.csv) is still
# edited by hand, and every src point below is a property of THAT ring (see the v3 note).
# ═══════════════════════════════════════════════════════════════════════════════
# How the list was built (2026-09-26, reproducible from the files named):
#  1. Candidates: the 213 gauges in `v4_design_context.gpkg:usgs_q_sandy` (a daily-mean
#     00060 series spanning Sandy), those inside the ring or within 25 km of it.
#  2. Where each one's river crosses the ring: the USGS NLDI mainstem flowlines
#     (api.water.usgs.gov/nldi, NHDPlus v2) — downstream from a gauge outside the ring,
#     upstream from one inside — intersected with the ring edge. `along_km` is the
#     distance ALONG THAT FLOWLINE from the gauge to the crossing; `side` says whether the
#     gauge is above the crossing (outside the ring) or below it (inside).
#  3. Rule: per crossing, the MOST-DOWNSTREAM gauge (largest drainage area) on that river,
#     except where it also measures another crossing's water (see the Raritan below).
#  4. src point: 150 m inside the ring along the flowline, then moved to the LOWEST cell
#     within 100 m of it that is inside the ring and >= 50 m from the edge, sampled on
#     `scripts/audit_region_v4.py`'s elevation stack at 5 m. The `z` comment is that
#     bed (m NAVD88). ⚠️ Re-check each against the MERGED bed once v4 is built — NHDPlus
#     flowlines sit tens of metres off the channel in places, and several sources
#     landed at the 100 m search limit.
# Crossings that coincide with a declared `kind: cut` in v4_crossings.geojson are marked
# `cut=`; the rest are valleys the ring crosses undeclared (audit section I), plus the
# v3 Atlantic-side rivers, which cross the rim on higher ground.
#
# DECISIONS THE USER HAS NOT MADE (each is the default here, and each is reversible):
#  * Raritan (RESOLVED 09-26, user): the cut once named `raritan_manville` was on the
#    MILLSTONE; it is now `millstone_blackwells_mills`, and the main stem's crossing at
#    (-74.5695, 40.5505) is the new declared `raritan_manville`. Sources = Manville
#    01400500 (490 mi2, 1.3 km above) + Blackwells Mills 01402000 (258 mi2, 8.6 km above),
#    NOT Bound Brook 01403060 (785 mi2, 2.8 km below, it measures both rivers). 748 of
#    785 mi2 gauged.
#  * Schuylkill: Philadelphia 01474500 (1,893 mi2) sits 12.2 km BELOW the Manayunk cut and
#    includes the Wissahickon (01474000, 64 mi2), whose own crossing is 0.8 km above its
#    mouth. Default: Philadelphia at the cut, NO Wissahickon source (volume conserved,
#    the Wissahickon's 3 % enters ~3 km upstream of its mouth). Alternatives: Norristown
#    01473500 (1,760 mi2, 13.5 km above) + Wissahickon; or Philadelphia − Wissahickon.
#  * Delaware: Trenton 01463500 is 9.7 km along the river BELOW the Washington Crossing
#    cut (the crossing note's "3.9 km" is wrong); Jacobs Creek and other small
#    tributaries between are counted twice (gauge + rain on grid).
#  * Far above the crossing (> 5 km along): Great Egg Harbor at Folsom 16.7 km (ungauged
#    Hospitality Br etc. between), N Br Rancocas 8.6, Millstone 8.6, W Br Middle Brook
#    7.8, Crosswicks 7.6, Neshaminy 7.2, Maurice 5.2,
#    Ridley 6.7.
#  * Partial basins (gauge measures a fraction of what crosses): Mantua Creek 6.2 mi2
#    (Pitman), S Br Pennsauken 9.0, W Br Middle Brook 2.0 of Middle Brook's 17.2.
#  * Regulated: Hackensack at Rivervale (below Lake Tappan), Swimming River (below its
#    reservoir), Lawrence Brook (Westons Mills), Elizabeth R (Ursino Lake), Passaic
#    (Dundee Dam), St Jones (Silver Lake, Dover).
#  * Rahway / Maurice (RESOLVED 09-26, user): each crossed the ring 3 times at a meander;
#    the ring corners were moved so each crosses ONCE, and their sources re-placed by the
#    same rule. Springfield 01394500 (25.5 mi2) stays out: Rahway 01395000 (40.9 mi2),
#    now 7.7 km below the crossing, contains it.
#  * Gauge BELOW its crossing (inside the ring): its in-ring catchment is counted twice
#    (gauge + rain on grid). Largest cases: Delaware, Schuylkill, Manasquan (Allenwood,
#    4.5 km below; Squankum 01408000, 44 mi2, is 0.5 km below), St Jones, Tuckahoe,
#    S Br Pennsauken, Deep Run, Absecon, Mullica.
# LEFT OUT (candidates with a Sandy record; see EXCLUDED_V4).
# Ungauged for Sandy (no daily 00060 across the event): Darby Creek above Cobbs, the
# South River main stem, Oldmans / Alloway / Big Timber / N Br Pennsauken, Appoquinimink
# and Smyrna main stems, Crum Creek below its reservoirs.
def _v4(site, river, name, da_mi2, along_km, side, lon, lat):
    return {
        "id": site,
        "river": river,
        "name": name,
        "da_mi2": da_mi2,
        "along_km": along_km,
        "side": side,
        "src_lon": lon,
        "src_lat": lat,
    }


# fmt: off
STATIONS_V4 = [
    _v4("01484100", "Beaverdam Branch (Murderkill trib.)", "BEAVERDAM BRANCH AT HOUSTON, DE", 3.02, 3.78, "above", -75.4741, 38.9071),  # z +6.1
    _v4("01483700", "St Jones", "ST JONES RIVER AT DOVER, DE", 31.9, 4.44, "below", -75.5501, 39.185),  # z +4.2
    _v4("01411300", "Tuckahoe", "Tuckahoe River at Head of River NJ", 30.8, 5.16, "below", -74.8613, 39.3252),  # z +6.9
    _v4("01483200", "Blackbird Creek", "BLACKBIRD CREEK AT BLACKBIRD, DE", 4.06, 0.87, "below", -75.6728, 39.3611),  # z +8.6
    _v4("01483155", "Silver Lake trib. (Appoquinimink)", "SILVER LAKE TRIBUTARY AT MIDDLETOWN, DE", 1.73, 0.72, "below", -75.72, 39.4323),  # z +7.1
    _v4("01410500", "Absecon Creek", "Absecon Creek at Absecon NJ", 17.9, 4.15, "below", -74.5557, 39.4404),  # z +6.4
    _v4("01411500", "Maurice", "Maurice River at Norma NJ", 112.0, 5.24, "above", -75.0816, 39.4545),  # z +0.2, cut=maurice_above_union_lake
    _v4("01483170", "Dove Nest Branch", "DOVE NEST BRANCH NEAR ODESSA, DE", 4.68, 1.52, "below", -75.7002, 39.4592),  # z +5.5
    _v4("01412800", "Cohansey", "Cohansey River at Seeley NJ", 28.0, 1.41, "above", -75.2479, 39.4623),  # z +5.7, cut=cohansey_above_sunset_lake
    _v4("01483165", "Spring Mill Branch", "SPRING MILL BRANCH NEAR ARMSTRONG, DE", 1.79, 0.24, "below", -75.6968, 39.4853),  # z +5.2
    _v4("01411000", "Great Egg Harbor", "Great Egg Harbor River at Folsom NJ", 57.1, 16.66, "above", -74.7835, 39.5224),  # z +7.8
    _v4("01478000", "Christina", "CHRISTINA RIVER AT COOCHS BRIDGE, DE", 20.5, 3.62, "above", -75.7064, 39.6358),  # z +4.6, cut=christina_coochs
    _v4("01410150", "E Br Bass River", "East Branch Bass River near New Gretna NJ", 8.11, 3.39, "below", -74.4265, 39.6433),  # z +6.4
    _v4("01482500", "Salem River", "Salem River at Woodstown NJ", 14.6, 1.38, "above", -75.3368, 39.6537),  # z -0.3
    _v4("01409280", "Westecunk Creek", "Westecunk Creek at Stafford Forge NJ", 15.8, 0.47, "below", -74.3217, 39.6697),  # z +5.5
    _v4("01410000", "Oswego River", "Oswego River at Harrisville NJ", 72.5, 3.72, "below", -74.5085, 39.686),  # z +5.8
    _v4("01409810", "W Br Wading River", "West Branch Wading River near Jenkins NJ", 84.1, 0.49, "below", -74.546, 39.6899),  # z +6.7
    _v4("01479000", "White Clay Creek", "WHITE CLAY CREEK NEAR NEWARK, DE", 89.1, 0.58, "below", -75.6794, 39.6977),  # z -0.4, cut=white_clay
    _v4("01409400", "Mullica", "Mullica River near Batsto NJ", 46.7, 4.04, "below", -74.6809, 39.7026),  # z +6.4
    _v4("01409210", "Mill Creek (Manahawkin)", "Mill Ck at Manahawkin NJ", 20.4, 1.15, "below", -74.2655, 39.7031),  # z +6.4
    _v4("01480015", "Red Clay Creek", "RED CLAY CREEK NEAR STANTON, DE", 52.4, 1.59, "below", -75.6356, 39.7254),  # z -0.5, cut=red_clay
    _v4("01477120", "Raccoon Creek", "Raccoon Creek near Swedesboro NJ", 26.9, 2.96, "below", -75.2306, 39.737),  # z +5.8
    _v4("01481500", "Brandywine", "BRANDYWINE CREEK AT WILMINGTON, DE", 314.0, 1.9, "above", -75.5572, 39.7642),  # z +8.0, cut=brandywine_wilmington
    _v4("01477800", "Shellpot Creek", "SHELLPOT CREEK AT WILMINGTON, DE", 7.46, 0.92, "below", -75.5182, 39.7667),  # z +12.6
    _v4("01475001", "Mantua Creek", "Mantua Creek at East Holly Avenue at Pitman NJ", 6.24, 4.74, "above", -75.1314, 39.7691),  # z +4.0
    _v4("01409095", "Oyster Creek", "Oyster Creek near Brookville NJ", 7.43, 1.03, "above", -74.2389, 39.803),  # z +6.3
    _v4("01477000", "Chester Creek", "Chester Creek near Chester, PA", 61.1, 1.07, "above", -75.3981, 39.8656),  # z -0.2
    _v4("01476480", "Ridley Creek", "Ridley Creek at Media, PA", 30.5, 6.65, "above", -75.3764, 39.8738),  # z -0.3
    _v4("01467150", "Cooper River", "Cooper River at Haddonfield NJ", 17.0, 3.03, "below", -75.0206, 39.8819),  # z +5.5
    _v4("01408900", "Cedar Creek", "Cedar Creek at Western Blvd near Lanoka Harbor NJ", 49.9, 3.85, "below", -74.2169, 39.8893),  # z +5.6
    _v4("01467081", "S Br Pennsauken Creek", "South Branch Pennsauken Creek at Cherry Hill NJ", 8.98, 5.61, "below", -74.9755, 39.9216),  # z +10.0
    _v4("01475548", "Cobbs Creek", "Cobbs Creek at Mt. Moriah Cemetery, Philadelphia", 19.9, 0.48, "below", -75.2366, 39.9345),  # z +6.0
    _v4("01465850", "S Br Rancocas", "South Branch Rancocas Creek at Vincentown NJ", 64.5, 1.94, "below", -74.753, 39.9383),  # z +5.5
    _v4("01467000", "N Br Rancocas", "North Branch Rancocas Creek at Pemberton NJ", 118.0, 8.61, "above", -74.7422, 39.9838),  # z +5.6
    _v4("01408500", "Toms River", "Toms River near Toms River NJ", 123.0, 0.35, "below", -74.2245, 39.9876),  # z +4.7
    _v4("01467087", "Frankford Creek", "Frankford Creek at Castor Ave, Philadelphia, PA", 30.4, 0.27, "above", -75.0936, 40.0126),  # z +2.7
    _v4("01474500", "Schuylkill", "Schuylkill River at Philadelphia, PA", 1893.0, 12.19, "below", -75.2536, 40.046),  # z +11.4, cut=schuylkill_manayunk
    _v4("01467048", "Pennypack Creek", "Pennypack Cr at Lower Rhawn St Bdg, Phila., PA", 49.8, 1.95, "above", -75.0198, 40.0465),  # z -0.3
    _v4("01465798", "Poquessing Creek", "Poquessing Creek at Grant Ave. at Philadelphia, PA", 21.4, 1.09, "below", -74.981, 40.0637),  # z +3.1
    _v4("01408151", "S Br Metedeconk", "SB Metedeconk R at New Hampshire Av nr Lakewood NJ", 29.5, 1.5, "below", -74.1929, 40.0874),  # z +7.1
    _v4("01408120", "N Br Metedeconk", "North Branch Metedeconk River near Lakewood NJ", 34.9, 3.43, "below", -74.173, 40.1087),  # z +6.8
    _v4("01465500", "Neshaminy", "Neshaminy Creek near Langhorne, PA", 210.0, 7.16, "above", -74.9204, 40.1472),  # z +6.3, cut=neshaminy
    _v4("01464500", "Crosswicks Creek", "Crosswicks Creek at Extonville NJ", 81.5, 7.57, "above", -74.6562, 40.1604),  # z +4.0
    _v4("01408029", "Manasquan", "Manasquan River near Allenwood NJ", 63.3, 4.5, "below", -74.1568, 40.1617),  # z +7.3
    _v4("01407705", "Shark River", "Shark River near Neptune City NJ", 9.96, 1.64, "below", -74.0835, 40.2037),  # z +6.6
    _v4("01407760", "Jumping Brook (Shark R. trib.)", "Jumping Brook near Neptune City NJ", 6.46, 1.64, "below", -74.0742, 40.2142),  # z +11.6
    _v4("01464000", "Assunpink Creek", "Assunpink Creek at Trenton NJ", 90.6, 0.64, "below", -74.7472, 40.2273),  # z +9.7
    _v4("01463500", "Delaware", "Delaware River at Trenton NJ", 6780.0, 9.74, "below", -74.8573, 40.2735),  # z +5.8, cut=delaware_washington_crossing
    _v4("01407500", "Swimming River (Navesink)", "Swimming River near Red Bank NJ", 49.2, 1.44, "below", -74.1274, 40.3194),  # z +10.1
    _v4("01406050", "Deep Run (South River)", "Deep Run at Old Bridge NJ", 16.0, 4.64, "below", -74.3213, 40.39),  # z +8.7
    _v4("01405030", "Lawrence Brook", "Lawrence Brook at Westons Mills NJ", 44.9, 2.89, "below", -74.4279, 40.4665),  # z +5.5
    _v4("01402000", "Millstone", "Millstone River at Blackwells Mills NJ", 258.0, 8.56, "above", -74.5795, 40.5395),  # z +6.8, cut=millstone_blackwells_mills
    _v4("01400500", "Raritan", "Raritan River at Manville NJ", 490.0, 1.27, "above", -74.5686, 40.5496),  # z +6.7, cut=raritan_manville
    _v4("01403150", "Middle Brook (W Br)", "West Branch Middle Brook near Martinsville NJ", 1.99, 7.76, "above", -74.5452, 40.5578),  # z +6.4
    _v4("01395000", "Rahway", "Rahway River at Rahway NJ", 40.9, 7.71, "below", -74.3012, 40.6458),  # z +14.5, cut=rahway
    _v4("01393450", "Elizabeth River", "Elizabeth River at Ursino Lake at Elizabeth NJ", 16.9, 2.42, "below", -74.2373, 40.6864),  # z +7.8
    _v4("01392500", "Second River", "Second River at Belleville NJ", 11.6, 0.7, "above", -74.1618, 40.7845),  # z +10.3
    _v4("01389890", "Passaic", "Passaic River at Dundee Dam at Clifton NJ", 805.0, 0.46, "below", -74.1304, 40.8872),  # z +7.4, cut=passaic_dundee
    _v4("01391500", "Saddle River", "Saddle River at Lodi NJ", 54.6, 0.94, "below", -74.079, 40.8963),  # z +8.4
    _v4("01377500", "Pascack Brook", "Pascack Brook at Westwood NJ", 29.6, 2.16, "above", -74.0032, 40.9861),  # z +6.1, cut=pascack
    _v4("01377000", "Hackensack", "Hackensack River at Rivervale NJ", 58.0, 1.27, "above", -73.9889, 40.9903),  # z +6.2, cut=hackensack_rivervale
]
# fmt: on
#: Candidates with a Sandy record that are deliberately NOT sources (flip by moving one
#: into STATIONS_V4 — each is a judgement the user owns).
EXCLUDED_V4 = {
    # 🔴 NO DAILY VALUES 2012-10-26..11-02 although `usgs_q_sandy` lists them: that layer
    # tested the PERIOD OF RECORD (begin <= Sandy <= end), and these four have a gap
    # across it (checked against the daily AND continuous collections, 2026-09-26).
    "01484000": "Murderkill nr Felton: no data in the window (record gap)",
    "01483500": "Leipsic nr Cheswold: no data in the window (record gap)",
    "01412000": "Menantico Ck nr Millville: no data in the window (record gap)",
    "01403900": "Bound Brook at Middlesex: no data in the window (daily resumes "
    "2013-02-01); upstream Green Bk 01403400 (6.2 mi2) + Stony Bk 01403540 (5.5 mi2) "
    "are the only gauged part",
    "01405400": "Manalapan Bk at Spotswood: regulated above Duhernal Lake, read 0.00 cfs "
    "on 2012-10-29 (v1.5 audit, below)",
    "01475850": "Crum Ck nr Newtown Square: 17.9 km above its crossing and above the "
    "Springton + Crum reservoirs; 15.8 of ~38 mi2",
    "01474000": "Wissahickon at Mouth: already inside Schuylkill at Philadelphia",
    "01394500": "Rahway nr Springfield: already inside Rahway at Rahway",
    "01408000": "Manasquan at Squankum: upstream of Allenwood (most-downstream rule)",
    "01403060": "Raritan below Calco Dam: measures Raritan + Millstone (two crossings)",
    "01378500": "Hackensack at New Milford: below Oradell dam, inside the ring; an "
    "interior check on the reservoir release, not a source",
}

STATIONS_BY_DOMAIN = {
    "v1_5_raritan": STATIONS_V1_5,
    "v3": STATIONS_V3,
    "v4": STATIONS_V4,
}
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


def fetch(site_id: str) -> tuple[pd.Series, pd.Series]:
    """Daily-mean discharge (m3/s) and approval status for one gauge, padded window."""
    df = usgs_ogc.daily_mean_discharge(site_id, BEGIN, END)
    return (df["cfs"] * CFS_TO_CMS).rename(site_id), df["approval"].rename(site_id)


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
    out = args.out or default_out()
    # 🔴 A built domain's forcing file is an input a sealed template was staged from.
    # Re-pulling it silently (a revised gauge, a changed list) would change that domain
    # under its own name, so it takes an explicit --overwrite. v4 (acquisition-only) and
    # --out scratch files are written freely, atomically.
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
        f"Fetching {len(STATIONS)} USGS gauges (daily discharge) {BEGIN}..{END} "
        f"[{_DOM.name}] via {API} ..."
    )
    series, approval = {}, {}
    for st in STATIONS:
        series[st["id"]], approval[st["id"]] = fetch(st["id"])
    days = pd.date_range(BEGIN, END, freq="D")
    for st in STATIONS:
        s = series[st["id"]]
        missing = days.difference(s.index)
        prov = int((approval[st["id"]] != "Approved").sum())
        flag = (
            f"  ⚠️ MISSING {len(missing)} day(s): {[d.date() for d in missing]}"
            if len(missing)
            else ""
        )
        flag += f"  ⚠️ {prov} provisional" if prov else ""
        peak = (
            f"peak={s.max():8.2f} m3/s on {s.idxmax().date()}" if len(s) else "NO DATA"
        )
        print(f"  {st['id']} {st['name'][:44]:44s}: n={len(s)}  {peak}{flag}")

    empty = [st["id"] for st in STATIONS if series[st["id"]].empty]
    if empty:
        # An all-NaN column is a source that silently injects nothing.
        raise SystemExit(f"no daily values in {BEGIN}..{END} for {empty}; drop them")

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
            "source": f"USGS Water Data OGC API: {API}",
            "units": "m3/s",
            "domain": _DOM.name,
            "note": "point coords are the model-domain inflow cells, not the gauge sites",
        },
    )
    ds["discharge"].attrs.update(units="m3/s", long_name="river discharge")
    ds["lon"].attrs.update(units="degrees_east", standard_name="longitude")
    ds["lat"].attrs.update(units="degrees_north", standard_name="latitude")

    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    ds.to_netcdf(tmp)
    os.replace(tmp, out)
    print(f"Wrote {out}  ({len(STATIONS)} src points)")


if __name__ == "__main__":
    main()
