#!/usr/bin/env python
"""ONE bed-source hierarchy for every tidal channel reach of the frozen v4 → one overlay.

    python scripts/build_riverbeds_hierarchy_v4.py fetch    # network: eHydro, ENC, NOS, CO-OPS
    python scripts/build_riverbeds_hierarchy_v4.py build    # rasters, VRTs, tables, cases
    python scripts/build_riverbeds_hierarchy_v4.py maps     # before / after PNG per reach
    python scripts/build_riverbeds_hierarchy_v4.py cases    # the fill test on known cases
    python scripts/build_riverbeds_hierarchy_v4.py screen   # the fill test, domain-wide
    python scripts/build_riverbeds_hierarchy_v4.py premier  # the premier's own tiers vs it
    ... build --reach maurice --reach cohansey              # a subset (no VRT written)

THE RULE (user, 2026-10-05 evening): "eHydro surveys as the gospel truth, then CUDEM, then
NOAA nautical charts, and finally if those aren't available, the sloping river
approximation." Consistency is the point, not perfection. Per pixel of a reach's channel:

  1. USACE eHydro — the survey NEAREST SANDY that covers the pixel (the house conventions of
     ``download_ehydro_v4.py``: linear interpolation inside the survey's own
     ``Bathymetry_Vector`` coverage, water-only z < -1 m; CENAN .XYZ = negative elevation
     below MLLW, plane from VDatum; CENAP gdb ``SurveyPoint.Z_use`` = +ft below MLLW,
     plane = the reach's CO-OPS MLLW). An existing eHydro OVERLAY of the re-freeze bed
     (``ehydro_refreeze_cenan_v4``, ``ehydro_harbour_v4``) and the premier's own eHydro
     tiers (``PREMIER_EHYDRO``) count as tier 1 as they are.
  2. CUDEM 1/9" — ONLY where it is a real bed. THE FILL TEST, per 25 m station over a
     +-50 m slice of the channel polygon: CUDEM is a FILL (a water surface, not a bed) when
     NOTHING IN THE SECTION REACHES HALF A METRE BELOW LOW WATER (p5 > MLLW -
     ``FILL_BELOW_MLLW_M`` = 0.5 m). A real tidal channel carries its thalweg below MLLW;
     an interpolator's water surface (CUDEM's ~0 m, 3DEP's -0.6..-1.1 m) does not. The
     flatness of the deepest quarter (p25 - p5) is recorded, not tested (``is_fill``).
     Shown on seven known cases (``cases`` -> ``fill_test_cases.csv``). ⚠️ Necessary, not
     sufficient: a water surface held DEEPER than MLLW - 0.5 m passes as a bed (the
     Passaic / Hackensack, §54 b) — only a survey comparison sees that.
  3. NOAA charts / NOS H-surveys — a 1-D along-channel running median (+-300 m) of the
     soundings within 150 m of the channel, interpolated between soundings, never
     extrapolated. Several sources: the NOS survey NEAREST SANDY first, then older ones,
     then ENC SOUNDG, station by station. MLW surveys -> NAVD88 with the reach's CO-OPS
     MLW, epoch-corrected (``download_nos_hydro_v4``: 2.9 mm/yr from 1992). Thalweg vs
     bank-to-bank is MEASURED (position across the channel of the soundings: xi p25 <
     ``XI_SECTION`` = 0.35 -> a section survey), and sets d_c as
     ``build_riverbeds_tidal_v4.centre_depth`` does.
  4. The sloping-river approximation where none of 1-3 exists: the SECTION-MEAN depth
     below MLLW runs LINEARLY along the centreline from the last downstream control (the
     median section-mean depth of the bed the model will see over the 10 stations = 250 m
     below the gap) to ``DEPTH_HEAD_M`` = 1.2 m below MLLW at the head of tide (or to the
     next control upstream), FLOORED at ``DEPTH_FLOOR_M`` = 1.2 m (user, 2026-10-06: a
     guessed section is never shallower; tiers 1-3 keep their values, a measured bar stays
     a bar) on runs that END AT A HEAD OF TIDE (a gap between two measured stretches is
     plain linear interpolation); across the channel the SHAPED section
     ``depth = d_c * (1 - (1 - xi)^1.5)`` (xi = 0 bank, 1 centreline; mean = 0.6 d_c),
     d_c = section mean / the station's mean shape factor (10-05 evidence: natural sections
     here average 0.55-0.65 of their deepest depth).

  Tier 2 is painted only below MLLW (the channel): CUDEM's banks and marsh keep the
  merge's own tier order. A station is CONTROLLED when tiers 1+2 cover >= 50 % of its
  channel pixels or tier 3 has a value there; tier 4 fills every uncontrolled station.
  Pixels of a tier-1/2-controlled station that neither survey nor real CUDEM covers are
  left alone. A tributary with no control of its own starts from the main stem's
  section mean at the fork. THE HEAD OF TIDE: the 10-05 spans for the 10-05 reaches; for
  the others the hand-set end (a dam, the A+ cut), moved DOWN to where the merged bed's
  channel first rises above MHHW (a lidar water surface above the highest tide is not
  tidal water; ``_head_by_mhhw``). A canal's open end carries its last control.
  MLLW (and MHHW, MLW) - NAVD88 per reach: NOAA CO-OPS stations that publish BOTH datums
  (VDatum's API answers 412 on this coast): the station on the reach (within
  ``ONREACH_M`` of the channel) where one exists, else the mean of the two nearest to the
  reach's mouth.

OPT-IN SURVEY CHECKS (2026-10-23; a reach sets them, every other reach is unchanged): the
fill test cannot see a CUDEM water surface held below MLLW - 0.5 m, so where a reach has
the evidence, CUDEM at a station is also NOT a bed when (a) its p5 is shallower than the
charted CONTROLLING depth (``HReach.controlling``: the ENC's "controlling depth" notes — the
shallowest centreline depth, a floor), or (b) its tier-3 bed is more than
``survey_over_cudem_m`` deeper than CUDEM's p5. ``HReach.points`` adds tier-3 point sets
(crowdsourced soundings, digitised NOS) BEFORE the reach's own, old reaches included, and
re-measures the branch's kind on them. Tiers 3 and 4 never put the axis above a charted
controlling depth. Station tables gain ``cudem_demoted`` / ``controlling_m``.

VERSIONS (``--version``, 2026-10-23): outputs carry the tag; ``v4`` is FROZEN (the Phase 4
beds and every bed before were built from it) and is never rewritten. ``build --reach X
--version v4c`` writes X's ``_v4c`` rasters and a FULL ``riverbeds_hierarchy_v4c.vrt`` = the
v4 members with X's swapped in. The Cohansey's checks exist only from ``v4c`` on.

PAINTING. The hierarchy value is painted over the premier's untouched merge
(``rebuild_subgrid.py --overlay``) only where it DIFFERS from the bed the model will
otherwise see by more than ``TOL_M`` = 0.10 m — so where the merge already follows the
hierarchy (real CUDEM, a survey overlay) nothing is painted. "The bed the model will
otherwise see" = the A+ sealed template's merged bed (= ``v4_hot_plus_walls``'s, same
mesh and tiers; ROTATED, read through its affine and self-checked against
``rasterio.sample``) with the re-freeze overlays this one does NOT replace painted on top in
order (``REF_OVERLAYS``). Pixels of the survey / chart / lake overlays in ``PROTECT`` and
of the premier's ``riverbeds_v4`` tier are never painted. Unlike the 10-05 builds this is NOT deepen-only: a hierarchy value
shallower than the bed is painted too (and counted, ``raised_km2``).

REPLACES ``riverbed_cohansey_v4``, ``riverbeds_gmrt_v4``, ``riverbeds_tidal_v4`` and their
``_shaped`` options (same reaches and spans, re-derived under the hierarchy), and adds the
creeks with 2019-25 eHydro surveys, the Raritan-corner creek heads, the Rahway and the
Schuylkill below the Fairmount Dam; and (2026-10-06) the screen's damped fill-bed tidal creeks
(Murderkill, Wading, Bass, Alloway, Stow, Dividing, Cedar, Great Egg Harbor River, Broadkill,
Overpeck below its tidal dam, Appoquinimink, Blackbird, Smyrna, Leipsic). Nothing is painted outside the A+ ring
(``RING``) or over an earlier reach's pixels. 🔴 NEW FILES ONLY (``_out`` refuses every older name).
Outputs in data/elevation_v4/riverbeds/ (EPSG:32618, 5 m, NoData -9999, m NAVD88):
  riverbed_hier_<reach>_v4.tif + riverbeds_hierarchy_v4.vrt       the overlay
  riverbed_hier_<reach>_tier_v4.tif + riverbeds_hierarchy_tier_v4.vrt  provenance (uint8:
      1 eHydro / 2 CUDEM / 3 chart-NOS / 4 slope; 0 = not painted)
  riverbeds_hierarchy_v4_profiles.csv                               every station
Tables + figures: logs/refreeze_2026-10-05/bed_hierarchy/. Bulk inputs: ``SRC`` (scratch).
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
import warnings
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_riverbed_cohansey_v4 as coh  # noqa: E402
import build_riverbeds_gmrt_v4 as gm  # noqa: E402
import build_riverbeds_tidal_v4 as td  # noqa: E402
import build_riverbeds_v4 as rb  # noqa: E402
import download_ehydro_v4 as dl  # noqa: E402
import download_nos_hydro_v4 as nos  # noqa: E402

warnings.filterwarnings("ignore", category=RuntimeWarning)

DATA = ROOT / "data"
#: bulk inputs (eHydro zips, ENC cells, NOS surveys, CO-OPS datums): scratch, not home
SRC = Path("/scratch/tpj8/nj_bight_sfincs_data/elevation_v4/bed_hierarchy")
LOG_DIR = ROOT / "logs" / "refreeze_2026-10-05" / "bed_hierarchy"
OUT = rb.RB  # data/elevation_v4/riverbeds (a symlink into scratch)
# the A+ merged bed (rotated): gm.MODEL_BED was v4_hot_plus/_template_sealed's copy, deleted
# 10-11; A+ is a mask-only variant, so its merged bed IS the frozen mesh's (same inode as
# v4_hot_plus_walls' template, checked 2026-10-23)
TEMPLATE = DATA / "frozen_mesh_v4" / "subgrid" / "dep_subgrid_merged.tif"
CUDEM = (
    DATA / "elevation_v3" / "cudem_nj_v3.vrt",  # the premier's order: NJ set first
    DATA / "elevation_v4" / "cudem_delaware_v4.vrt",
)
NHD_RIVERS = DATA / "elevation_v4" / "inland_water" / "nhd_river_v4.gpkg"
#: overlays of the re-freeze bed that this one does NOT replace, in paint order (later
#: wins). The buildings burn is left out: footprints never stand in a channel.
REF_OVERLAYS = (
    ("inland_water_bed_v4", DATA / "elevation_v4/inland_water/inland_water_bed_v4.tif"),
    ("usace_unpave_v4", DATA / "elevation_v4/usace_unpave/usace_unpave_v4.vrt"),
    ("ehydro_harbour_v4", DATA / "elevation_v4/ehydro/ehydro_harbour_v4.tif"),
    (
        "ehydro_refreeze_cenan_v4",
        DATA / "elevation_v4/ehydro/ehydro_refreeze_cenan_v4.tif",
    ),
    (
        "usace_unpave_backbay_v4",
        DATA / "elevation_v4/usace_unpave_backbay/usace_unpave_backbay_v4.vrt",
    ),
    (
        "riverbed_sayreville_v4",
        DATA / "elevation_v4/riverbed_margins/riverbed_sayreville_v4.tif",
    ),
    (
        "littleegg_channel_v4",
        DATA / "elevation_v4/littleegg_channel/littleegg_channel_v4.tif",
    ),
)
#: the premier's own eHydro tiers (top of ``V4_ELEVATION_LIST``): tier 1 where they reach
PREMIER_EHYDRO = (
    ("ehydro_passaic_v4", DATA / "elevation_v4/ehydro/ehydro_passaic_v4.tif"),
    ("ehydro_hackensack_v4", DATA / "elevation_v4/ehydro/ehydro_hackensack_v4.tif"),
    ("ehydro_south_v3", DATA / "elevation_v3/ehydro_south_v3.tif"),
    ("ehydro_raritan_ak", DATA / "elevation_v1_5/ehydro_raritan_ak.tif"),
    ("ehydro_nj", DATA / "elevation/ehydro_nj.tif"),
    ("ehydro_south", DATA / "elevation/ehydro_south.tif"),
    ("shrewsbury_ehydro_2015", DATA / "elevation/shrewsbury_ehydro_2015.tif"),
)
RIVERBEDS_V4 = DATA / "elevation_v4/riverbeds/riverbeds_v4.vrt"
#: the A+ ring (v4_hot_plus / v4_hot_plus_walls): nothing is painted outside it
RING = DATA / "region_v4_hot_plus.geojson"
#: survey/chart overlays painted pixel by pixel: never painted over
PROTECT = (
    "inland_water_bed_v4",  # the decided non-tidal lake / river beds
    "ehydro_harbour_v4",
    "ehydro_refreeze_cenan_v4",
    "riverbed_sayreville_v4",
    "littleegg_channel_v4",
)
#: the 10-05 builds this one replaces (flat, shaped) — compared in ``conveyance.csv``
OLD_BUILDS = {
    "maurice": ("riverbed_gmrt_maurice_v4.tif", "riverbed_gmrt_maurice_shaped_v4.tif"),
    "mullica": ("riverbed_gmrt_mullica_v4.tif", "riverbed_gmrt_mullica_shaped_v4.tif"),
    "tuckahoe": (
        "riverbed_gmrt_tuckahoe_v4.tif",
        "riverbed_gmrt_tuckahoe_shaped_v4.tif",
    ),
    "rancocas": (
        "riverbed_gmrt_rancocas_v4.tif",
        "riverbed_gmrt_rancocas_shaped_v4.tif",
    ),
    "cohansey": ("riverbed_cohansey_v4.tif", "riverbed_cohansey_shaped_v4.tif"),
    "christina": (
        "riverbed_tidal_christina_v4.tif",
        "riverbed_tidal_christina_shaped_v4.tif",
    ),
    "bigtimber": (
        "riverbed_tidal_bigtimber_v4.tif",
        "riverbed_tidal_bigtimber_shaped_v4.tif",
    ),
    "stjones": (
        "riverbed_tidal_stjones_v4.tif",
        "riverbed_tidal_stjones_shaped_v4.tif",
    ),
}

RES = rb.RES  # 5 m
NODATA = rb.NODATA
EPSG = rb.EPSG
FT = dl.FT
P_SHAPE = td.P_DEFAULT  # 1.5
DEPTH_HEAD_M = 1.2  # section-mean depth below MLLW at a head of tide
DEPTH_FLOOR_M = 1.2  # tier 4 only: the guessed section mean is never shallower (10-06)
FILL_BELOW_MLLW_M = 0.5
FILL_MIN_PX = 8
STATION_M = 25.0
SLICE_STATIONS = 2  # +-2 stations = +-50 m
CTRL_FRAC = 0.5
CTRL_STATIONS = 10  # 250 m of controls each side of a gap
TOL_M = 0.10
EXT_DN_M = 1500.0  # old reaches: evaluate this far below the painted span (the control)
ONREACH_M = 2000.0
XI_SECTION = 0.35
WINDOW_M = gm.WINDOW_M  # 300 m running median
NEAR_CHANNEL_M = gm.NEAR_CHANNEL_M  # 150 m
WATER_MAX = dl.WATER_MAX  # -1 m: eHydro water-only clip
TIER_NAME = {1: "eHydro", 2: "CUDEM", 3: "chart/NOS", 4: "slope"}
ENC_DIRS = (
    SRC / "enc" / "ENC_ROOT",
    gm.ENC_ROOT,
    DATA / "elevation_v4" / "enc" / "raw",
)
EHYDRO_URL = (
    "https://ehydroprod.blob.core.usgovcloudapi.net/ehydro-surveys/{d}/{sid}.ZIP"
)
COOPS = (
    "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/{id}/datums.json"
    "?units=metric"
)
COOPS_LISTS = (
    "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json?type=tidepredictions",
    "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json?type=waterlevels",
)
SANDY_YEAR = 2012

#: Files this script must never write (the frozen / queued tiers and the 10-05 builds).
_OWN_PREFIXES = ("riverbed_hier_", "riverbeds_hierarchy_")


#: output version tag (``--version``): file names carry it, ``riverbed_hier_<reach>_<VER>.tif``
VER = "v4"
#: versions whose files a finished bed was built from — never rewritten (Phase 4's beds
#: and everything before them read ``v4``; 2026-10-23)
FROZEN_VERSIONS = ("v4",)


def _out(name: str) -> Path:
    if not name.startswith(_OWN_PREFIXES):
        raise SystemExit(f"🔴 refusing to write {name}: not this tier's file")
    out = OUT / name
    if out.exists() and any(
        name.endswith(f"_{v}{out.suffix}") for v in FROZEN_VERSIONS
    ):
        raise SystemExit(
            f"🔴 refusing to overwrite {name}: version frozen (built beds read it); "
            "build a new one with --version <tag>"
        )
    return out


# ── reach definitions ─────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Ehydro:
    sid: str
    district: str  # "CENAN" | "CENAP"


@dataclass(frozen=True)
class Nos:
    sid: str
    block: str  # NCEI block, e.g. "H10001-H12000"
    year: int
    plane: str  # "MLLW" | "MLW"


@dataclass(frozen=True)
class PointSet:
    """Tier-3 soundings from a CSV (lon, lat, depth below MLLW) — CSB, a digitised NOS."""

    path: str  # relative to ROOT
    label: str
    year: int  # epoch correction as ``_nos_points``
    depth_col: str = "depth_m"


@dataclass(frozen=True)
class TBranch:
    name: str
    mouth: tuple[float, float]  # downstream end (lon, lat); may sit in the parent water
    head: tuple[float, float]  # upstream end (lon, lat)
    head_of_tide: bool = True  # False: the upstream end is open water (a canal)


@dataclass(frozen=True)
class HReach:
    name: str
    label: str
    old: str = ""  # "gmrt" | "tidal" | "cohansey": re-derive a 10-05 reach's geometry
    box: tuple[float, float, float, float] = (0, 0, 0, 0)  # trace reaches: lon/lat clip
    branches: tuple[TBranch, ...] = ()
    halfwidth_m: float = rb.MAX_HALFWIDTH_M
    ehydro: tuple[Ehydro, ...] = ()  # tier 1 gridded here, NEAREST SANDY LAST (wins)
    ehydro_overlays: tuple[str, ...] = ()  # REF_OVERLAYS keys that ARE tier 1 here
    nos: tuple[Nos, ...] = ()  # tier 3, nearest Sandy first
    enc: bool = True  # tier 3: ENC SOUNDG after the NOS surveys
    why: str = ""
    # ── opt-in survey checks on CUDEM (2026-10-23; inert unless set) ──
    points: tuple[PointSet, ...] = ()  # extra tier 3, before any other, old reaches too
    #: CUDEM is NOT a bed at a station whose tier-3 bed is this much DEEPER than CUDEM's p5
    survey_over_cudem_m: float | None = None
    #: charted CONTROLLING depths (m below MLLW), mouth upward: ((lon, lat), depth) — each
    #: holds from the previous end (or the mouth) to the station nearest (lon, lat). CUDEM
    #: whose p5 is shallower is not a bed; tiers 3 and 4 never put the axis above it.
    controlling: tuple[tuple[tuple[float, float], float], ...] = ()


REACHES: tuple[HReach, ...] = (
    # ── the 10-05 reaches (same NHD polygons, centrelines and spans) ─────────────────
    # 2026-10-23 (user agreed the fix 10-22; logs/cohansey_sources_2026-10-22/): CUDEM's
    # lower Cohansey passes the fill test by a narrow strip but sits 4-7 m above the
    # tide-reduced crowdsourced soundings (lower bounds: no draft offset) and above the
    # ENC controlling depth (CTNARE, surveys 1988-2014). Only ``--version v4c`` builds
    # it as such; the v4 overlay (Phase 4's beds) was built without these fields.
    HReach(
        "cohansey",
        "Cohansey River, mouth -> Bridgeton",
        old="cohansey",
        points=(
            PointSet(
                "logs/cohansey_sources_2026-10-22/csb_mllw.csv",
                "CSB AquaMap 2024-26 (tide-reduced, Ship John)",
                2025,
                "depth_mllw_min_m",
            ),
            PointSet(
                "logs/cohansey_sources_2026-10-22/cohansey_D00081_in_river.csv",
                "NOS D00081 (1987, MLLW)",
                1987,
            ),
        ),
        survey_over_cudem_m=1.0,
        controlling=(
            # "1.5 m to ~3450 m W of Tindalls Wharf (CO-OPS 8537353, -75.235 39.3783),
            # then 1.2 m to 3573 m N of Fairton, thence 0.3 m to Bridgeton"
            ((-75.235 - 3450 / 86000, 39.3783), 1.5),
            ((-75.2196, 39.3815 + 3573 / 111000), 1.2),
            ((-75.2340, 39.4300), 0.3),
        ),
    ),
    HReach("maurice", "Maurice River, Mauricetown -> Millville", old="gmrt"),
    HReach("mullica", "Mullica River, below Lower Bank -> Batsto", old="gmrt"),
    HReach("tuckahoe", "Tuckahoe River, above Tuckahoe", old="gmrt"),
    HReach("rancocas", "Rancocas Creek, main stem + both branches", old="gmrt"),
    HReach("christina", "Christina River, CR_02's end -> Christiana", old="tidal"),
    HReach("bigtimber", "Big Timber Creek + both branches", old="tidal"),
    HReach("stjones", "St Jones River, Bowers -> Silver Lake dam", old="tidal"),
    # ── creeks with 2019-25 eHydro surveys (tier 1 wins) ─────────────────────────────
    HReach(
        "tuckerton",
        "Tuckerton Creek, Little Egg Harbor -> Tuckerton Lake dam",
        box=(-74.3470, 39.5730, -74.3330, 39.6062),
        branches=(
            TBranch("Tuckerton Creek", (-74.3352, 39.5762), (-74.3416, 39.6046)),
        ),
        halfwidth_m=80.0,
        ehydro=(Ehydro("TC_01_TCC_20200129_CS", "CENAP"),),
    ),
    HReach(
        "matawan",
        "Matawan Creek, Keyport Harbor -> Lake Lefferts",
        box=(-74.2335, 40.4140, -74.2000, 40.4445),
        branches=(TBranch("Matawan Creek", (-74.2035, 40.4405), (-74.2325, 40.4158)),),
        halfwidth_m=100.0,
        ehydro=(
            Ehydro("NJ_16_KEY_20180723_CS_4721_15", "CENAN"),  # Keyport Harbor
            Ehydro("NJ_18_MAT_20190801_CS_4851_15", "CENAN"),
        ),
    ),
    HReach(
        "lewes_canal",
        "Lewes & Rehoboth Canal, Roosevelt Inlet -> the ring at Rehoboth",
        box=(-75.1620, 38.6990, -75.0860, 38.7930),
        branches=(
            TBranch(
                "Lewes and Rehoboth Canal",
                (-75.1590, 38.7900),
                (-75.0935, 38.7000),
                head_of_tide=False,
            ),
        ),
        halfwidth_m=80.0,
        ehydro=(  # LR_03_BRC (2024) is not on the canal: 17 soundings, 0 px
            Ehydro("LR_02_STR_20211103_CS", "CENAP"),
            Ehydro("LR_01_LRC_20210909_CS", "CENAP"),
        ),
    ),
    HReach(
        "little_river_de",
        "Little River (DE), Delaware Bay -> the Little Creek millpond dam",
        box=(-75.4650, 39.1540, -75.4000, 39.1700),
        branches=(TBranch("Little River", (-75.4045, 39.1615), (-75.4605, 39.1612)),),
        halfwidth_m=100.0,
        ehydro=(Ehydro("LI_01_LIR_20220802_CS", "CENAP"),),
    ),
    # ── the Raritan corner (tier 1 = ehydro_refreeze_cenan_v4, already in the bed) ───
    HReach(
        "south_river",
        "South River + Washington Canal, Raritan -> Old Bridge",
        box=(-74.3960, 40.3990, -74.3500, 40.4730),
        branches=(TBranch("South River", (-74.3655, 40.4718), (-74.3805, 40.4025)),),
        halfwidth_m=120.0,
        ehydro_overlays=("ehydro_refreeze_cenan_v4",),
    ),
    HReach(
        "woodbridge",
        "Woodbridge Creek, Arthur Kill -> head",
        box=(-74.2760, 40.5340, -74.2500, 40.5620),
        branches=(
            TBranch("Woodbridge Creek", (-74.2510, 40.5395), (-74.2640, 40.5585)),
        ),
        halfwidth_m=80.0,
        ehydro_overlays=("ehydro_refreeze_cenan_v4",),
    ),
    HReach(
        "cheesequake",
        "Cheesequake Creek, Raritan Bay -> the state park",
        box=(-74.2900, 40.4330, -74.2500, 40.4650),
        branches=(
            TBranch("Cheesequake Creek", (-74.2525, 40.4625), (-74.2865, 40.4360)),
        ),
        halfwidth_m=100.0,
        ehydro_overlays=("ehydro_refreeze_cenan_v4",),
        nos=(Nos("H05636", "H04001-H06000", 1934, "MLW"),),
    ),
    HReach(
        "compton",
        "Compton Creek / Shoal Harbor, Belford -> head",
        box=(-74.1010, 40.4195, -74.0770, 40.4400),
        branches=(TBranch("Compton Creek", (-74.0790, 40.4370), (-74.0985, 40.4225)),),
        halfwidth_m=80.0,
        ehydro_overlays=("ehydro_refreeze_cenan_v4",),
        nos=(
            Nos("H10049", "H10001-H12000", 1982, "MLLW"),
            Nos("H05617", "H04001-H06000", 1934, "MLW"),
        ),
    ),
    HReach(
        "rahway",
        "Rahway River, Arthur Kill -> head of tide (both arms)",
        box=(-74.2990, 40.5900, -74.2410, 40.6250),
        branches=(
            TBranch("Rahway River", (-74.2425, 40.5995), (-74.2805, 40.6185)),
            TBranch(
                "South Branch Rahway River", (-74.2750, 40.6035), (-74.2925, 40.5950)
            ),
        ),
        halfwidth_m=80.0,
        ehydro_overlays=("ehydro_harbour_v4",),
    ),
    HReach(
        "schuylkill",
        "Schuylkill, end of the surveyed channel -> Fairmount Dam",
        box=(-75.2060, 39.9280, -75.1780, 39.9680),
        branches=(
            TBranch("Schuylkill River", (-75.2025, 39.9300), (-75.1838, 39.9663)),
        ),
        halfwidth_m=120.0,
        ehydro=(
            Ehydro("SR_05_005_20200930_CS", "CENAP"),
            Ehydro("SR_04_004_20200810_CS", "CENAP"),
            Ehydro("SR_03_003_20200810_CS", "CENAP"),
        ),
        nos=(Nos("H09942", "H08001-H10000", 1981, "MLW"),),
    ),
    # ── 2026-10-06: the damped fill-bed tidal creeks of the domain-wide screen ───────
    HReach(
        "murderkill",
        "Murderkill, Bowers -> Frederica -> head of tide (+ Spring Creek, Browns Br.)",
        box=(-75.5200, 38.9620, -75.3850, 39.0680),
        branches=(
            TBranch("Murderkill River", (-75.3985, 39.0585), (-75.5095, 38.9905)),
            TBranch("Spring Creek", (-75.4700, 39.0220), (-75.5030, 39.0340)),
            TBranch("Browns Branch", (-75.4740, 38.9830), (-75.4910, 38.9680)),
        ),
        halfwidth_m=100.0,
        ehydro=(Ehydro("MU_01_MUR_20220329_CS", "CENAP"),),
        nos=(Nos("H10079", "H10001-H12000", 1983, "MLLW"),),
    ),
    HReach(
        "wading",
        "Wading River, the Mullica -> head of tide",
        box=(-74.5350, 39.5500, -74.4650, 39.6680),
        branches=(TBranch("Wading River", (-74.4775, 39.5585), (-74.5265, 39.6620)),),
        halfwidth_m=100.0,
        nos=(
            Nos("H05894", "H04001-H06000", 1935, "MLW"),
            Nos("H05893", "H04001-H06000", 1935, "MLW"),
        ),
    ),
    HReach(
        "bass",
        "Bass River, the Mullica -> New Gretna -> head of tide",
        box=(-74.4650, 39.5480, -74.4300, 39.6300),
        branches=(TBranch("Bass River", (-74.4555, 39.5560), (-74.4425, 39.6225)),),
        halfwidth_m=100.0,
        nos=(
            Nos("H05894", "H04001-H06000", 1935, "MLW"),
            Nos("H05893", "H04001-H06000", 1935, "MLW"),
        ),
    ),
    HReach(
        "alloway",
        "Alloway Creek, Delaware -> Alloway (screen's 'Salem River at Salem')",
        box=(-75.5450, 39.4450, -75.3550, 39.5750),
        branches=(TBranch("Alloway Creek", (-75.5410, 39.4970), (-75.3615, 39.5675)),),
        halfwidth_m=100.0,
        nos=(
            Nos("H10200", "H10001-H12000", 1986, "MLLW"),
            Nos("H10112", "H10001-H12000", 1983, "MLLW"),
        ),
    ),
    HReach(
        "stow",
        "Stow Creek, Delaware -> head of tide (screen's 'Alloway Creek')",
        box=(-75.4950, 39.3750, -75.3550, 39.4900),
        branches=(TBranch("Stow Creek", (-75.4170, 39.3810), (-75.3645, 39.4660)),),
        halfwidth_m=100.0,
        nos=(
            Nos("H10200", "H10001-H12000", 1986, "MLLW"),
            Nos("H10217", "H10001-H12000", 1986, "MLLW"),
        ),
    ),
    HReach(
        "dividing",
        "Dividing Creek, Delaware Bay -> head of tide",
        box=(-75.1350, 39.2050, -75.0550, 39.2920),
        branches=(TBranch("Dividing Creek", (-75.1125, 39.2120), (-75.0650, 39.2870)),),
        halfwidth_m=100.0,
        nos=(
            Nos("F00290", "F00001-F02000", 1987, "MLLW"),
            Nos("H10167", "H10001-H12000", 1984, "MLLW"),
        ),
    ),
    HReach(
        "cedar_nj",
        "Cedar Creek (Cumberland), Delaware Bay -> the Cedarville dam",
        box=(-75.2450, 39.2720, -75.1500, 39.3180),
        branches=(TBranch("Cedar Creek", (-75.2378, 39.2825), (-75.1580, 39.3115)),),
        halfwidth_m=100.0,
        nos=(Nos("D00081", "D00001-D02000", 1987, "MLLW"),),
    ),
    HReach(
        "greategg",
        "Great Egg Harbor River, the bay -> Mays Landing (Lake Lenape dam)",
        box=(-74.7650, 39.2250, -74.6850, 39.4580),
        branches=(
            TBranch("Great Egg Harbor River", (-74.6820, 39.3260), (-74.7270, 39.4500)),
        ),
        halfwidth_m=120.0,
        nos=(
            Nos("H06217", "H06001-H08000", 1937, "MLW"),
            Nos("H06218", "H06001-H08000", 1937, "MLW"),
            Nos("H06254", "H06001-H08000", 1937, "MLW"),
        ),
    ),
    HReach(
        "broadkill",
        "Broadkill River, Roosevelt Inlet -> Milton (the Lake Milton dam)",
        box=(-75.3300, 38.7650, -75.1500, 38.8500),
        branches=(
            TBranch("Broadkill River", (-75.1660, 38.7920), (-75.3130, 38.7765)),
        ),
        halfwidth_m=100.0,
        ehydro=(Ehydro("LR_01_LRC_20210909_CS", "CENAP"),),
        nos=(
            Nos("H09202", "H08001-H10000", 1971, "MLW"),
            Nos("H09203", "H08001-H10000", 1971, "MLW"),
            Nos("H07034", "H06001-H08000", 1945, "MLW"),
        ),
    ),
    HReach(
        "overpeck",
        "Overpeck Creek, the Hackensack -> the Overpeck Tidal Dam (Turnpike, Ridgefield)",
        box=(-74.0400, 40.8320, -73.9800, 40.9000),
        # CUT AT THE OVERPECK TIDAL DAM (NJ00799, Bergen County; 1950 plans, rebuilt 1977;
        # 2 bascule + 4 tainter gates + 7 stoplog bays under the NJ Turnpike northbound
        # bridge, N40 50.4' W74 01.1'; built "to prevent tidal flow into Overpeck Creek";
        # NJSEA 2016 inspection: fully functional). Its sill is the CUDEM ridge at
        # stations 1775-1925 of this trace; the head sits at 1650 so the 80 m channel
        # buffer stops short of it: nothing is painted on or above the dam.
        branches=(TBranch("Overpeck Creek", (-74.0300, 40.8420), (-74.0217, 40.8399)),),
        halfwidth_m=80.0,
    ),
    HReach(
        "appoquinimink",
        "Appoquinimink River, Delaware -> Odessa -> below the Noxontown Pond dam",
        box=(-75.7000, 39.4250, -75.5700, 39.4900),
        branches=(
            TBranch("Appoquinimink River", (-75.5785, 39.4490), (-75.6920, 39.4405)),
        ),
        halfwidth_m=100.0,
        nos=(Nos("H10200", "H10001-H12000", 1986, "MLLW"),),
    ),
    HReach(
        "blackbird",
        "Blackbird Creek, Delaware -> head of tide",
        box=(-75.6600, 39.3700, -75.5650, 39.4460),
        branches=(
            TBranch("Blackbird Creek", (-75.5735, 39.4405), (-75.6510, 39.3765)),
        ),
        halfwidth_m=100.0,
        nos=(Nos("H10200", "H10001-H12000", 1986, "MLLW"),),
    ),
    HReach(
        "smyrna",
        "Smyrna River, Delaware Bay -> Smyrna (below Lake Como)",
        box=(-75.6000, 39.2950, -75.5000, 39.3720),
        branches=(TBranch("Smyrna River", (-75.5120, 39.3660), (-75.5880, 39.3030)),),
        halfwidth_m=100.0,
        nos=(Nos("D00081", "D00001-D02000", 1987, "MLLW"),),
    ),
    HReach(
        "leipsic",
        "Leipsic River, Delaware Bay -> Leipsic -> head of tide (never the millpond, A2)",
        box=(-75.6000, 39.2000, -75.3950, 39.2700),
        branches=(TBranch("Leipsic River", (-75.4050, 39.2520), (-75.5880, 39.2420)),),
        halfwidth_m=100.0,
        nos=(Nos("H10255", "H10001-H12000", 1987, "MLLW"),),
    ),
)
BY_NAME = {r.name: r for r in REACHES}


# ── small IO helpers ──────────────────────────────────────────────────────────────
def _get(url: str, timeout: int = 300) -> bytes:
    for k in range(5):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as f:
                return f.read()
        except Exception as e:  # noqa: BLE001
            if k == 4:
                raise
            print(f"    retry {k + 1} ({e})")
            time.sleep(5 * (k + 1))
    raise RuntimeError("unreachable")


def _atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


def _atomic_csv(path: Path, df) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".csv")
    os.close(fd)
    df.to_csv(tmp, index=False, float_format="%.4g")
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


def _utm(lon: float, lat: float):
    return gm._utm(lon, lat)


def _to_ll(x, y):
    import pyproj

    t = pyproj.Transformer.from_crs(EPSG, 4326, always_xy=True)
    return t.transform(x, y)


# ── CO-OPS datums: the one MLLW rule ──────────────────────────────────────────────
#: stations on ANOTHER estuary's tide, never a reach's datum (2026-10-06): Chesapeake
#: City sits on the C&D canal (Chesapeake-side range, MLLW -0.487 vs Reedy Point's -0.905)
#: yet is among the "two nearest" to the Alloway / Appoquinimink mouths
NOT_THIS_ESTUARY = {"8573927": "Chesapeake City, C&D canal"}


def _stations() -> dict[str, tuple[str, float, float, dict]]:
    """id -> (name, lat, lon, datums) for every cached station publishing MLLW + NAVD88."""
    meta = json.loads((SRC / "coops" / "stations_bbox.json").read_text())
    out = {}
    for sid, (name, lat, lon) in meta.items():
        if sid in NOT_THIS_ESTUARY:
            continue
        p = SRC / "coops" / f"datums_{sid}.json"
        if not p.exists():
            continue
        try:
            d = json.loads(p.read_text())
        except ValueError:
            continue
        ds = {a["name"]: a["value"] for a in (d.get("datums") or [])}
        if "MLLW" in ds and "NAVD88" in ds and ds["MLLW"] is not None:
            out[sid] = (name, float(lat), float(lon), ds)
    return out


@dataclass
class Datum:
    mllw: float
    mlw: float
    mhhw: float
    note: str


def datum_rule(mouth_ll: tuple[float, float], chan) -> Datum:
    """MLLW/MLW/MHHW - NAVD88: the station ON the reach (<= ONREACH_M of the channel),
    else the mean of the two nearest the mouth. Stations publishing both datums only."""
    st = _stations()
    ids = list(st)
    pts = [_utm(st[i][2], st[i][1]) for i in ids]
    don = np.array([chan.distance(p) for p in pts])
    m = _utm(*mouth_ll)
    dmouth = np.array([m.distance(p) for p in pts])
    on = np.nonzero(don <= ONREACH_M)[0]
    pick = [on[np.argmin(dmouth[on])]] if len(on) else list(np.argsort(dmouth)[:2])
    rows = [st[ids[i]][3] for i in pick]

    def mean(key):
        return float(np.mean([r[key] - r["NAVD88"] for r in rows]))

    how = "on the reach" if len(on) else "two nearest the mouth"
    note = f"{how}: " + "; ".join(
        f"{ids[i]} {st[ids[i]][0]} ({st[ids[i]][3]['MLLW'] - st[ids[i]][3]['NAVD88']:+.3f}"
        f", {dmouth[i] / 1000:.1f} km)"
        for i in pick
    )
    return Datum(mean("MLLW"), mean("MLW"), mean("MHHW"), note)


# ── fetch ─────────────────────────────────────────────────────────────────────────
def fetch() -> None:
    (SRC / "coops").mkdir(parents=True, exist_ok=True)
    meta_p = SRC / "coops" / "stations_bbox.json"
    if not meta_p.exists():
        meta = {}
        for u in COOPS_LISTS:
            for s in json.loads(_get(u))["stations"]:
                lat, lon = float(s["lat"]), float(s["lng"])
                if -75.9 < lon < -73.6 and 38.5 < lat < 41.1:
                    meta[s["id"]] = (s["name"], lat, lon)
        _atomic_bytes(meta_p, json.dumps(meta).encode())
    for sid in json.loads(meta_p.read_text()):
        p = SRC / "coops" / f"datums_{sid}.json"
        if not p.exists():
            try:
                _atomic_bytes(p, _get(COOPS.format(id=sid), timeout=60))
            except Exception as e:  # noqa: BLE001
                _atomic_bytes(p, json.dumps({"error": str(e)}).encode())
            time.sleep(0.2)
    for r in (*REACHES, *FILL_CASES):
        for e in r.ehydro:
            z = SRC / "ehydro" / f"{e.sid}.ZIP"
            if not z.exists():
                print(f"  eHydro {e.sid}")
                _atomic_bytes(z, _get(EHYDRO_URL.format(d=e.district, sid=e.sid), 1800))
        for s in r.nos:
            gz = SRC / "nos" / f"{s.sid}.a93.gz"
            if not gz.exists():
                _atomic_bytes(gz, _get(nos.A93.format(blk=s.block, sid=s.sid)))
    cells = (
        "US4NJ1FE US5NYCAD US4NY1AP US5NYCBB US5NYCBC US4NJ1FF US5NJ1UM US5NYCAE US5NYCAF "
        "US5NYCCD US5PHLCD US4DE1CB US5NYCAC US4NJ1CE US4NJ1DE US5NJ1JI US5NJ1JJ "
        "US5NJ1KJ US4DE1AC US4DE1BC US5DE1DF US5DE1DG US5DE1EF US5DE1EG "
        # 2026-10-06 reaches (NOAA ENCProdCat_19115 polygons over each reach box)
        "US4DE1BB US4DE1DB US4DE1DA US5ILGAE US5ILGAF US5ILGAG US5ILGBE US5ILGBF "
        "US5ILGCE US5ILGCF US5DE1KE US5DE1DE US5DE1EE US5DE1KC US5DE1LB US5DE1LC "
        "US4NJ1BD US5NJ1FE US5NJ1GE US5NJ1HD US4NY1AQ US4NY1BP US4NY1BQ US5NYCEG "
        "US5NYCFG"
    ).split()
    for c in cells:
        if (SRC / "enc" / "ENC_ROOT" / c).exists():
            continue
        z = SRC / "enc" / f"{c}.zip"
        if not z.exists():
            _atomic_bytes(z, _get(f"https://charts.noaa.gov/ENCs/{c}.zip"))
        with zipfile.ZipFile(z) as f:
            f.extractall(SRC / "enc")
    _enc_table(rebuild=True)
    print(f"inputs cached under {SRC}")


def _enc_table(rebuild: bool = False):
    """Every ENC SOUNDG point in the cached cells: lon, lat, depth (m below MLLW), cell."""
    import geopandas as gpd
    import pandas as pd
    import pyogrio

    p = SRC / "enc" / "soundg_all.parquet"
    if p.exists() and not rebuild:
        return pd.read_parquet(p)
    os.environ["OGR_S57_OPTIONS"] = "SPLIT_MULTIPOINT=ON,ADD_SOUNDG_DEPTH=ON"
    rows = []
    for d in ENC_DIRS:
        for f in sorted(glob.glob(str(d / "*" / "*.000"))):
            if "SOUNDG" not in {n for n, _ in pyogrio.list_layers(f)}:
                continue
            g = gpd.read_file(f, layer="SOUNDG", engine="pyogrio")
            for q in g.geometry:
                rows.append((Path(f).stem, q.x, q.y, q.z))
    t = pd.DataFrame(rows, columns=["cell", "lon", "lat", "depth"])
    t = t.drop_duplicates(["lon", "lat", "depth"])
    fd, tmp = tempfile.mkstemp(dir=p.parent, suffix=".parquet")
    os.close(fd)
    t.to_parquet(tmp)
    os.replace(tmp, p)
    return t


# ── geometry ──────────────────────────────────────────────────────────────────────
@dataclass
class Br:
    """One branch: centreline (station 0 downstream), channel, tier-3 profile, ranges."""

    reach: str
    name: str
    line: object
    chan: object
    grid: np.ndarray
    lo: float  # evaluate from here ...
    hi: float  # ... to here (m along the line)
    plo: float  # paint from here ...
    phi: float  # ... to here
    head_of_tide: bool = True
    t3: np.ndarray | None = None  # bed m NAVD88 per station (NaN: no chart/NOS)
    t3src: np.ndarray | None = None  # source label per station
    kind: str = "thalweg"  # what a tier-3 value means
    deep: np.ndarray | None = None  # running p5 of the sounding beds
    extra: dict = field(default_factory=dict)


def _trace(poly, a, b, res: float = 10.0):
    """Least-cost path a -> b on 1/(distance to bank + 1)^2 inside ``poly``; outside it a
    flat cost 2 (crosses an NHD gap at a bridge, never prefers land)."""
    import shapely
    from rasterio import features
    from rasterio.transform import from_origin
    from scipy import ndimage
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import dijkstra

    x0, y0, x1, y1 = shapely.union_all(
        [poly.envelope, a.buffer(50), b.buffer(50)]
    ).bounds
    nx, ny = int((x1 - x0) / res) + 1, int((y1 - y0) / res) + 1
    T = from_origin(x0, y1, res, res)
    inside = features.rasterize([(poly, 1)], out_shape=(ny, nx), transform=T) > 0
    dist = ndimage.distance_transform_edt(inside) * res
    cost = np.where(inside, 1.0 / (dist + 1.0) ** 2, 2.0)
    ids = np.arange(ny * nx).reshape(ny, nx)
    rows, cols, w = [], [], []
    for dy, dx in ((0, 1), (1, 0), (1, 1), (1, -1)):
        aa = ids[0 : ny - dy, max(0, -dx) : nx - max(0, dx)].ravel()
        bb = ids[dy:ny, max(0, dx) : nx - max(0, -dx)].ravel()
        ww = np.hypot(dy, dx) * 0.5 * (cost.ravel()[aa] + cost.ravel()[bb])
        rows += [aa, bb]
        cols += [bb, aa]
        w += [ww, ww]
    n = ny * nx
    G = coo_matrix(
        (np.concatenate(w), (np.concatenate(rows), np.concatenate(cols))), (n, n)
    ).tocsr()
    yy, xx = np.divmod(np.arange(n), nx)
    px, py = x0 + (xx + 0.5) * res, y1 - (yy + 0.5) * res
    ia = int(np.argmin(np.hypot(px - a.x, py - a.y)))
    ib = int(np.argmin(np.hypot(px - b.x, py - b.y)))
    _, pred = dijkstra(G, indices=ia, return_predecessors=True)
    path = [ib]
    while path[-1] != ia:
        nxt = pred[path[-1]]
        if nxt < 0:
            raise SystemExit("trace: mouth and head not connected")
        path.append(nxt)
    path = path[::-1]
    return shapely.LineString(np.column_stack([px[path], py[path]])).simplify(res)


def _survey_cover(r: HReach):
    """Union of the reach's eHydro coverage polygons (UTM), or None."""
    import geopandas as gpd
    import shapely

    polys = []
    for e in r.ehydro:
        d = _unzipped(e.sid)
        gdb = dl.ehnj._one(d, ".gdb")
        polys.append(
            shapely.union_all(
                gpd.read_file(gdb, layer="Bathymetry_Vector")
                .to_crs(EPSG)
                .geometry.values
            )
        )
    return shapely.union_all(polys) if polys else None


def branches_trace(r: HReach) -> list[Br]:
    import geopandas as gpd
    import shapely

    box = gpd.GeoSeries([shapely.box(*r.box)], crs=4326).to_crs(EPSG).iloc[0]
    g = gpd.read_file(NHD_RIVERS, bbox=r.box).to_crs(EPSG)
    poly = shapely.union_all(g.geometry.values).intersection(box)
    cov = _survey_cover(r)
    if cov is not None:
        poly = shapely.union_all([poly, cov.intersection(box)])
    poly = poly.buffer(0)
    out = []
    for b in r.branches:
        line = _trace(poly, _utm(*b.mouth), _utm(*b.head))
        chan = poly.intersection(line.buffer(r.halfwidth_m)).intersection(box)
        grid = np.arange(0.0, line.length + STATION_M, STATION_M)
        out.append(
            Br(
                r.name,
                b.name,
                line,
                chan,
                grid,
                0.0,
                line.length,
                0.0,
                line.length,
                b.head_of_tide,
            )
        )
        print(
            f"{r.name} / {b.name}: traced {line.length / 1000:.2f} km, channel "
            f"{chan.area / 1e6:.3f} km²"
        )
    return out


def branches_old(r: HReach) -> tuple[list[Br], float]:
    """The 10-05 geometry (NHD polygons, centrelines, painted spans) and its MLLW."""
    if r.old == "gmrt":
        gr = next(x for x in gm.REACHES if x.name == r.name)
        parts, old_mllw = td.parts_gmrt(gr), gr.mllw_navd88_m
        kinds = td.KIND_EXISTING[r.name]
        label = (
            f"NOS {'+'.join(s for s, _, _ in gr.nos_surveys)}"
            if gr.points == "nos"
            else "ENC"
        )
        enc_based = gr.points == "enc"
        names = [b.river for b in gr.branches]
    elif r.old == "tidal":
        tr = next(x for x in td.REACHES if x.name == r.name)
        parts, old_mllw, kinds = td.parts_tidal(tr), tr.mllw_navd88_m, tr.kind
        label = "NOS " + "+".join(s.sid for s in tr.surveys)
        # MLLW-plane surveys hang from the reach's MLLW exactly as ENC depths do
        enc_based = all(s.plane == "MLLW" for s in tr.surveys)
        names = [b.river for b in tr.branches]
    else:
        parts, old_mllw, kinds = td.parts_cohansey(), coh.MLLW_NAVD88_M, "section"
        label, enc_based, names = "", False, ["Cohansey River"]
    out = []
    for nm, pt in zip(names, parts):
        t3 = np.where(pt.src == "soundings", pt.prof, np.nan)
        out.append(
            Br(
                r.name,
                nm,
                pt.line,
                pt.chan,
                pt.grid,
                max(0.0, pt.lo - EXT_DN_M),
                pt.hi,
                pt.lo,
                pt.hi,
                True,
                t3,
                np.where(np.isfinite(t3), label, ""),
                kinds,
                pt.deep,
                {"enc_based": enc_based, "old_mllw": old_mllw},
            )
        )
    return out, old_mllw


# ── raster sampling on a reach grid ───────────────────────────────────────────────
@dataclass
class RGrid:
    x0: float
    y1: float
    w: int
    h: int

    @property
    def T(self):
        from rasterio.transform import from_origin

        return from_origin(self.x0, self.y1, RES, RES)

    def centres(self, rr, cc):
        return self.x0 + (cc + 0.5) * RES, self.y1 - (rr + 0.5) * RES


def _grid_for(brs: list[Br]) -> RGrid:
    b = np.array([x.chan.bounds for x in brs])
    x0 = np.floor(b[:, 0].min() / RES) * RES - RES
    y1 = np.ceil(b[:, 3].max() / RES) * RES + RES
    w = int(np.ceil((b[:, 2].max() - x0) / RES)) + 1
    h = int(np.ceil((y1 - b[:, 1].min()) / RES)) + 1
    return RGrid(float(x0), float(y1), w, h)


def warp(path: Path, g: RGrid) -> np.ndarray:
    """Any raster onto the reach grid, NEAREST, through its full affine (the rotated
    template included); NaN off-raster / NoData / |z| > 1e5."""
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.warp import reproject

    out = np.full((g.h, g.w), np.nan, "float32")
    with rasterio.open(path) as s:
        reproject(
            source=rasterio.band(s, 1),
            destination=out,
            dst_transform=g.T,
            dst_crs=f"EPSG:{EPSG}",
            dst_nodata=np.nan,
            src_nodata=s.nodata,
            resampling=Resampling.nearest,
        )
    out[np.abs(out) > 1e5] = np.nan
    return out


def _selfcheck(path: Path, g: RGrid, arr: np.ndarray, rr, cc, n: int = 2000) -> float:
    """Warped template == rasterio.sample at random channel pixels (CLAUDE.md §5)."""
    import rasterio

    k = np.random.default_rng(0).choice(len(rr), min(n, len(rr)), replace=False)
    x, y = g.centres(rr[k], cc[k])
    with rasterio.open(path) as s:
        v = np.array([t[0] for t in s.sample(zip(x, y))], "float64")
        if s.nodata is not None and np.isfinite(s.nodata):
            v[v == s.nodata] = np.nan
    a = arr[rr[k], cc[k]].astype("float64")
    same = (np.isnan(a) & np.isnan(v)) | (np.abs(a - v) < 1e-4)
    frac = float(same.mean())
    if frac < 0.995:
        raise SystemExit(f"🔴 rotated-template sampler disagrees: {frac:.4f} agree")
    return frac


# ── tier 1: eHydro surveys gridded on the reach grid ──────────────────────────────
def _unzipped(sid: str) -> Path:
    d = SRC / "ehydro" / sid
    if not d.exists():
        tmp = Path(tempfile.mkdtemp(dir=SRC / "ehydro", prefix=f".{sid}."))
        with zipfile.ZipFile(SRC / "ehydro" / f"{sid}.ZIP") as z:
            z.extractall(tmp)
        os.chmod(tmp, 0o755)
        os.replace(tmp, d)
    return d


def survey_points(e: Ehydro, dat: Datum):
    """(x, y, z m NAVD88, coverage gdf UTM, plane note) for one eHydro survey."""
    import geopandas as gpd

    if e.district == "CENAN":
        dl.RAW = SRC / "ehydro"  # VDatum cache + zips live with this tier's inputs
        lon, lat, xm, ym, z, cover = dl.soundings(e.sid, "CENAN", 1.0)
        return xm, ym, z, cover, "CENAN XYZ, VDatum MLLW field (download_ehydro_v4)"
    d = _unzipped(e.sid)
    gdb = dl.ehnj._one(d, ".gdb")
    sp = gpd.read_file(gdb, layer="SurveyPoint")
    zr = sp.Z_use.astype(float).to_numpy()
    ok = np.isfinite(zr)
    neg = float((zr[ok] < 0).mean())
    if neg > 0.05:
        raise SystemExit(f"🔴 {e.sid}: CENAP expects +depth, {neg:.0%} of Z_use < 0")
    sp = sp[ok].to_crs(EPSG)
    z = dat.mllw - zr[ok] * FT
    cover = gpd.read_file(gdb, layer="Bathymetry_Vector").to_crs(EPSG)
    return (
        sp.geometry.x.to_numpy(),
        sp.geometry.y.to_numpy(),
        z,
        cover,
        f"CENAP gdb SurveyPoint.Z_use (+ft below MLLW), plane {dat.mllw:+.3f}",
    )


def tier1(r: HReach, g: RGrid, dat: Datum, ref_layers: dict) -> tuple[np.ndarray, list]:
    """The tier-1 bed on the reach grid (NaN where no survey) and a note per source."""
    from rasterio.features import geometry_mask
    from scipy.interpolate import griddata

    t1 = np.full((g.h, g.w), np.nan, "float32")
    notes = []
    for e in r.ehydro:  # nearest Sandy LAST: it wins where surveys overlap
        x, y, z, cover, how = survey_points(e, dat)
        inb = (
            (x > g.x0 - 50)
            & (x < g.x0 + g.w * RES + 50)
            & (y < g.y1 + 50)
            & (y > g.y1 - g.h * RES - 50)
        )
        if inb.sum() < 4:
            notes.append(f"{e.sid}: 0 soundings on the reach grid")
            continue
        X, Y = np.meshgrid(
            g.x0 + (np.arange(g.w) + 0.5) * RES, g.y1 - (np.arange(g.h) + 0.5) * RES
        )
        v = griddata((x[inb], y[inb]), z[inb], (X, Y), method="linear").astype(
            "float32"
        )
        inside = geometry_mask(cover.geometry, (g.h, g.w), g.T, invert=True)
        v[~inside] = np.nan
        n_cov = int(np.isfinite(v).sum())
        v[v >= WATER_MAX] = np.nan  # water-only, the house rule
        t1 = np.where(np.isfinite(v), v, t1)
        notes.append(
            f"{e.sid}: {inb.sum()} soundings ({how}); {n_cov} px covered, "
            f"{int(np.isfinite(v).sum())} after the < {WATER_MAX:g} m clip"
        )
    for k in r.ehydro_overlays:
        v = ref_layers[k]
        t1 = np.where(np.isfinite(t1), t1, v)
        notes.append(f"{k} (existing overlay): {int(np.isfinite(v).sum())} px")
    for k, path in PREMIER_EHYDRO:  # the premier's eHydro tiers ARE tier 1 where valid
        v = warp(path, g)
        n = int((np.isfinite(v) & ~np.isfinite(t1)).sum())
        if n:
            t1 = np.where(np.isfinite(t1), t1, v)
            notes.append(f"{k} (premier tier): {n} px")
    return t1, notes


# ── tier 3: charts / NOS ──────────────────────────────────────────────────────────
def _nos_points(s: Nos, dat: Datum):
    d = nos.read_a93(SRC / "nos" / f"{s.sid}.a93.gz")  # (lat, lon, depth below plane)
    plane = dat.mllw if s.plane == "MLLW" else dat.mlw
    epoch = -nos.SLR_M_PER_YR * (nos.EPOCH_MID - s.year)
    return d[:, 1], d[:, 0], plane + epoch - d[:, 2]


def _profile(br: Br, lon, lat, z):
    """Running median (+-WINDOW_M) of soundings within NEAR_CHANNEL_M of the channel,
    interpolated between soundings, never extrapolated. Also the xi of the soundings."""
    import geopandas as gpd
    import shapely

    p = np.asarray(gpd.points_from_xy(lon, lat, crs=4326).to_crs(EPSG))
    near = shapely.dwithin(br.chan, p, NEAR_CHANNEL_M)
    prof = np.full(br.grid.shape, np.nan)
    if near.sum() < 3:
        return prof, None, 0, np.full(br.grid.shape, np.nan)
    s = shapely.line_locate_point(br.line, p[near])
    prof = rb._running_median(s, z[near], br.grid, WINDOW_M)
    ok = np.isfinite(prof)
    if ok.sum() >= 2:
        inside = (br.grid >= br.grid[ok][0]) & (br.grid <= br.grid[ok][-1])
        prof[inside] = np.interp(br.grid[inside], br.grid[ok], prof[ok])
    deep = td._deep(br.line, br.chan, (lon, lat, z, ""), br.grid)
    xs = np.array([q.x for q in p[near]])
    ys = np.array([q.y for q in p[near]])
    return prof, (xs, ys), int(near.sum()), deep


def tier3_trace(r: HReach, br: Br, dat: Datum) -> None:
    """Fill ``br.t3`` station by station: NOS nearest Sandy first, then older, then ENC."""
    br.t3 = np.full(br.grid.shape, np.nan)
    br.t3src = np.full(br.grid.shape, "", dtype=object)
    br.deep = np.full(br.grid.shape, np.nan)
    sources = []
    for s in sorted(r.nos, key=lambda s: abs(s.year - SANDY_YEAR)):
        sources.append((f"NOS {s.sid} ({s.year}, {s.plane})", *_nos_points(s, dat)))
    if r.enc:
        t = _enc_table()
        b = r.box
        t = t[(t.lon > b[0]) & (t.lon < b[2]) & (t.lat > b[1]) & (t.lat < b[3])]
        if len(t):
            sources.append(
                ("ENC SOUNDG", t.lon.to_numpy(), t.lat.to_numpy(), dat.mllw - t.depth)
            )
    xi_pts = []
    for label, lon, lat, z in sources:
        prof, xy, n, deep = _profile(
            br, np.asarray(lon), np.asarray(lat), np.asarray(z)
        )
        new = np.isfinite(prof) & ~np.isfinite(br.t3)
        br.t3[new] = prof[new]
        br.t3src[new] = label
        br.deep[new] = deep[new]
        if new.any() and xy is not None:
            xi_pts.append(xy)
        br.extra.setdefault("t3_notes", []).append(
            f"{label}: {n} soundings near the channel, {int(new.sum())} stations"
        )
    br.kind = _measured_kind(br, xi_pts)


def _pointset(s: PointSet, dat: Datum):
    import pandas as pd

    d = pd.read_csv(ROOT / s.path, usecols=["lon", "lat", s.depth_col]).dropna()
    d = d[d[s.depth_col] > 0]
    epoch = -nos.SLR_M_PER_YR * (nos.EPOCH_MID - s.year)
    return (
        d.lon.to_numpy(),
        d.lat.to_numpy(),
        dat.mllw + epoch - d[s.depth_col].to_numpy(),
    )


def tier3_points(r: HReach, br: Br, dat: Datum) -> None:
    """``r.points`` as tier 3, BEFORE the branch's own (old-build / NOS / ENC) values; the
    branch's kind is then measured on the new points (``_measured_kind``)."""
    n = len(br.grid)
    old = br.t3 if br.t3 is not None else np.full(n, np.nan)
    oldsrc = br.t3src if br.t3src is not None else np.full(n, "", dtype=object)
    t3 = np.full(n, np.nan)
    src = np.full(n, "", dtype=object)
    deep = np.full(n, np.nan)
    xi_pts = []
    for s in r.points:
        prof, xy, npts, dp = _profile(br, *_pointset(s, dat))
        new = np.isfinite(prof) & ~np.isfinite(t3)
        t3[new], src[new], deep[new] = prof[new], s.label, dp[new]
        if new.any() and xy is not None:
            xi_pts.append(xy)
        br.extra.setdefault("t3_notes", []).append(
            f"{s.label}: {npts} soundings near the channel, {int(new.sum())} stations"
        )
    keep = ~np.isfinite(t3) & np.isfinite(old)
    t3[keep], src[keep] = old[keep], oldsrc[keep]
    if br.deep is not None:
        deep = np.where(np.isfinite(deep), deep, br.deep)
    br.t3, br.t3src, br.deep = t3, src, deep
    if xi_pts:
        br.kind = _measured_kind(br, xi_pts)


def _controlling(r: HReach, br: Br) -> np.ndarray:
    """Charted controlling depth (m below MLLW) per station; NaN where none is charted."""
    c = np.full(len(br.grid), np.nan)
    s0 = 0.0
    for i, ((lon, lat), depth) in enumerate(r.controlling):
        s1 = br.line.project(_utm(lon, lat))
        if i == len(r.controlling) - 1:
            s1 = br.grid[-1]
        c[(br.grid >= s0) & (br.grid <= s1)] = depth
        br.extra.setdefault("ctrl_notes", []).append(
            f"controlling {depth:.1f} m below MLLW, stations {s0:.0f}..{s1:.0f} m"
        )
        s0 = s1
    return c


def _measured_kind(br: Br, xi_pts) -> str:
    """'section' when the soundings spread bank to bank (xi p25 < XI_SECTION)."""
    if not xi_pts:
        return "thalweg"
    x = np.concatenate([a for a, _ in xi_pts])
    y = np.concatenate([b for _, b in xi_pts])
    pt = td.Part(
        br.line, br.chan, br.grid, br.grid * 0, br.grid * 0, 0, 0, "thalweg", 0.0
    )
    xi, _, inside = td._xi_of_points(pt, x, y)
    xi = xi[inside]
    if len(xi) < 10:
        return "thalweg"
    br.extra["xi_p25"] = float(np.percentile(xi, 25))
    return "section" if br.extra["xi_p25"] < XI_SECTION else "thalweg"


# ── the hierarchy on one reach ────────────────────────────────────────────────────
@dataclass
class Result:
    reach: HReach
    g: RGrid
    dat: Datum
    brs: list
    ref: np.ndarray
    val: np.ndarray  # hierarchy bed (NaN off-channel / no value)
    tier: np.ndarray  # hierarchy tier of every evaluated pixel (0 none)
    paint: np.ndarray  # bool: painted
    inspan: np.ndarray  # bool: inside a paint span
    stations: list  # per-branch station tables
    notes: list
    cudem: np.ndarray
    t1: np.ndarray


def is_fill(v: np.ndarray, mllw: float) -> tuple[bool, float, float]:
    """THE FILL TEST on the CUDEM pixels of one channel slice: (fill?, flatness, p5).

    A fill = NOTHING in the section reaches half a metre below MLLW (p5 > MLLW -
    FILL_BELOW_MLLW_M). A real tidal channel carries its thalweg below low water; CUDEM's
    water-surface fills sit at ~0 m (or 3DEP's -0.6..-1.1 m), within half a metre of MLLW
    or above it. Flatness of the deepest quarter (p25 - p5) is returned for the record, not
    tested: NHD polygons carry marsh and banks, so a fill's section is not flat as a whole,
    and a dredged channel's floor is flat and real."""
    q5, q25 = np.percentile(v, [5, 25])
    return bool(q5 > mllw - FILL_BELOW_MLLW_M), float(q25 - q5), float(q5)


def _station_slices(k: np.ndarray, n: int):
    """Indices of pixels per station (k sorted)."""
    o = np.argsort(k, kind="stable")
    bounds = np.searchsorted(k[o], np.arange(n + 1))
    return o, bounds


def evaluate(r: HReach) -> Result:
    import shapely

    if r.old:
        brs, old_mllw = branches_old(r)
        mouth = brs[0].line.interpolate(brs[0].plo)
        mouth_ll = _to_ll(mouth.x, mouth.y)
    else:
        brs = branches_trace(r)
        old_mllw = None
        mouth_ll = r.branches[0].mouth
    chan_all = shapely.union_all([b.chan for b in brs])
    dat = datum_rule(mouth_ll, chan_all)
    notes = [
        f"MLLW {dat.mllw:+.3f}, MLW {dat.mlw:+.3f}, MHHW {dat.mhhw:+.3f} ({dat.note})"
    ]
    if old_mllw is not None and abs(old_mllw - dat.mllw) > 0.005:
        notes.append(f"⚠️ 10-05 build used MLLW {old_mllw:+.3f}")
        for b in brs:  # ENC / MLLW-plane depths hang from MLLW: move them with it
            if b.extra.get("enc_based"):
                b.t3 = b.t3 + (dat.mllw - old_mllw)
    g = _grid_for(brs)
    # reference bed = template + REF_OVERLAYS in order
    tpl = warp(TEMPLATE, g)
    ref = tpl.copy()
    layers = {k: warp(p, g) for k, p in REF_OVERLAYS}
    for k, _ in REF_OVERLAYS:
        ref = np.where(np.isfinite(layers[k]), layers[k], ref)
    protect = np.zeros(ref.shape, bool)
    for k in PROTECT:
        if k not in r.ehydro_overlays:
            protect |= np.isfinite(layers[k])
    # the premier's own river-bed tier (riverbeds_v4) is left as it is here: its
    # consistency with the hierarchy is reported by ``premier``, not patched piecemeal
    protect |= np.isfinite(warp(RIVERBEDS_V4, g))
    # earlier reaches of this overlay own their pixels (no two reach rasters overlap)
    for q in REACHES[: [x.name for x in REACHES].index(r.name)]:
        f = OUT / f"riverbed_hier_{q.name}_v4.tif"
        if f.exists():
            protect |= np.isfinite(warp(f, g))
    inring = _ring_mask(g)
    cud = warp(CUDEM[0], g)
    cud2 = warp(CUDEM[1], g)
    cud = np.where(np.isfinite(cud), cud, cud2)
    del cud2
    t1, t1notes = tier1(r, g, dat, layers)
    notes += t1notes
    if not r.old:
        for b in brs:
            tier3_trace(r, b, dat)
            notes += [f"{b.name}: {x}" for x in b.extra.get("t3_notes", [])]
            if "xi_p25" in b.extra:
                notes.append(
                    f"{b.name}: soundings xi p25 {b.extra['xi_p25']:.2f} -> {b.kind}"
                )
    if r.points:
        for b in brs:
            b.extra.pop("t3_notes", None)
            tier3_points(r, b, dat)
            notes += [f"{b.name}: {x}" for x in b.extra.get("t3_notes", [])]
            notes.append(
                f"{b.name}: point sets -> kind {b.kind}"
                + (f" (xi p25 {b.extra['xi_p25']:.2f})" if "xi_p25" in b.extra else "")
            )
    val = np.full(ref.shape, np.nan, "float32")
    tier = np.zeros(ref.shape, "uint8")
    inspan = np.zeros(ref.shape, bool)
    tables = []
    checked = False
    done_lines = []  # (line, station grid, D per station) of earlier branches (forks)
    for b in brs:
        pt = td.Part(
            b.line, b.chan, b.grid, b.grid * 0.0, b.grid * 0.0, b.lo, b.hi, "", 0
        )
        rr, cc, px, py, st, e, Bw = td.bank_field(pt, (g.h, g.w), g.T)
        if not r.old and b.head_of_tide:
            cut = _head_by_mhhw(b, st, ref[rr, cc], dat.mhhw)
            if cut is not None:
                lon, lat = _to_ll(*np.asarray(b.line.interpolate(cut).coords[0]))
                notes.append(
                    f"{b.name}: head of tide moved to {cut:.0f} m of {b.hi:.0f} "
                    f"({lon:.4f}, {lat:.4f}): the bed's water surface rises above MHHW"
                )
                b.hi = b.phi = cut
        on = (st >= b.lo) & (st <= b.hi)
        rr, cc, st, e, Bw = rr[on], cc[on], st[on], e[on], Bw[on]
        if not checked and len(rr):
            notes.append(
                f"template self-check {_selfcheck(TEMPLATE, g, tpl, rr, cc):.4f}"
            )
            checked = True
        n = len(b.grid)
        k = np.clip(np.rint(st / STATION_M).astype(int), 0, n - 1)
        xi = np.clip(e / Bw, 0.0, 1.0)
        gg = td.g_shape(xi, P_SHAPE)
        mg = td._mean_g(st, gg, n, P_SHAPE)
        z_ref = ref[rr, cc].astype("float64")
        z1 = t1[rr, cc].astype("float64")
        zc = cud[rr, cc].astype("float64")
        o, bnd = _station_slices(k, n)
        # fill test per station over +-SLICE_STATIONS
        real = np.zeros(n, bool)
        relief = np.full(n, np.nan)
        p5 = np.full(n, np.nan)
        npx = np.diff(bnd)
        for i in range(n):
            a, c = bnd[max(0, i - SLICE_STATIONS)], bnd[min(n, i + SLICE_STATIONS + 1)]
            v = zc[o[a:c]]
            v = v[np.isfinite(v)]
            if len(v) < FILL_MIN_PX:
                continue
            fill, relief[i], p5[i] = is_fill(v, dat.mllw)
            real[i] = not fill
        # opt-in survey checks (2026-10-23): a CUDEM "bed" a survey or the chart
        # contradicts is a water surface — the fill test alone cannot see it (§54 (j))
        cdep = _controlling(r, b) if r.controlling else np.full(n, np.nan)
        demoted = np.full(n, "", dtype=object)
        if r.controlling:
            bad = real & np.isfinite(cdep) & (p5 > dat.mllw - cdep)
            real[bad], demoted[bad] = False, "controlling"
            notes += [f"{b.name}: {x}" for x in b.extra.get("ctrl_notes", [])]
            notes.append(
                f"{b.name}: CUDEM above the controlling depth: {bad.sum()} st."
            )
        if r.survey_over_cudem_m is not None and b.t3 is not None:
            bad = real & np.isfinite(b.t3) & (b.t3 < p5 - r.survey_over_cudem_m)
            real[bad], demoted[bad] = False, "survey"
            notes.append(
                f"{b.name}: CUDEM > {r.survey_over_cudem_m:.1f} m above the soundings: "
                f"{bad.sum()} st."
            )
        has1 = np.isfinite(z1)
        has2 = ~has1 & np.isfinite(zc) & real[k]
        f1 = np.bincount(k, has1, minlength=n) / np.maximum(npx, 1)
        f2 = np.bincount(k, has2, minlength=n) / np.maximum(npx, 1)
        t3 = b.t3 if b.t3 is not None else np.full(n, np.nan)
        has3s = np.isfinite(t3)
        ctrl = (f1 + f2 >= CTRL_FRAC) | has3s
        ctrl[npx == 0] = False  # no pixels: transparent (never a control)
        tz = np.zeros(len(k), "uint8")
        v = np.full(len(k), np.nan)
        tz[has1], v[has1] = 1, z1[has1]
        tz[has2], v[has2] = 2, zc[has2]
        # tier 3: the shaped section from the profile (td.centre_depth's meanings)
        s3 = ~has1 & ~has2 & has3s[k]
        dep3 = dat.mllw - t3
        dc3 = td.centre_depth(
            np.where(has3s, dep3, 0.0), np.full(n, "soundings"), b.kind, P_SHAPE, mg
        )
        if b.kind == "section" and b.deep is not None:
            cap = dat.mllw - b.deep
            dc3 = np.where(
                np.isfinite(cap), np.minimum(dc3, np.maximum(cap, dep3)), dc3
            )
        dc3 = np.where(np.isfinite(cdep), np.maximum(dc3, cdep), dc3)  # charted floor
        d3 = dc3[k] * gg
        v3 = np.where(dep3[k] > 0, dat.mllw - d3, t3[k])
        tz[s3], v[s3] = 3, v3[s3]
        # section-mean depth of the bed the model will see, per controlled station
        zseen = np.where(np.isfinite(v), v, z_ref)
        dpx = np.clip(dat.mllw - zseen, 0.0, None)
        dsum = np.bincount(k, np.nan_to_num(dpx), minlength=n)
        dcnt = np.bincount(k, np.isfinite(dpx), minlength=n)
        Dctrl = np.where(ctrl & (dcnt > 0), dsum / np.maximum(dcnt, 1), np.nan)
        # tier 4: linear section-mean depth across every uncontrolled run
        D4 = np.full(n, np.nan)
        lo_i = int(np.searchsorted(b.grid, b.lo))
        hi_i = int(np.searchsorted(b.grid, b.hi, side="right")) - 1
        runs = []
        i = lo_i
        while i <= hi_i:
            if ctrl[i]:
                i += 1
                continue
            j = i
            while j + 1 <= hi_i and not ctrl[j + 1]:
                j += 1
            runs.append((i, j))
            i = j + 1
        for i, j in runs:
            dn = [q for q in range(i - 1, lo_i - 1, -1) if np.isfinite(Dctrl[q])]
            dn = dn[:CTRL_STATIONS]
            up = [q for q in range(j + 1, hi_i + 1) if np.isfinite(Dctrl[q])]
            up = up[:CTRL_STATIONS]
            if dn:
                D_dn, s_dn, how_dn = float(np.median(Dctrl[dn])), b.grid[dn[0]], "ctrl"
            else:
                D_dn, s_dn, how_dn = _fork_control(b, done_lines), b.grid[i], "fork"
            if j >= hi_i and b.head_of_tide:
                D_up, s_up, how_up = DEPTH_HEAD_M, b.grid[hi_i], "head"
            elif up:
                D_up, s_up, how_up = float(np.median(Dctrl[up])), b.grid[up[0]], "ctrl"
            elif b.head_of_tide:
                D_up, s_up, how_up = DEPTH_HEAD_M, b.grid[j], "head"
            else:  # open water upstream, no control: carry the downstream one
                D_up, s_up, how_up = D_dn, b.grid[j], "open"
            if not np.isfinite(D_dn):
                D_dn, how_dn = D_up, "none"
            ss = b.grid[i : j + 1]
            lin = D_dn + (D_up - D_dn) * np.clip(
                (ss - s_dn) / max(s_up - s_dn, 1.0), 0, 1
            )
            # THE FLOOR (user, 2026-10-06): a GUESSED section is never shallower than
            # DEPTH_FLOOR_M below MLLW; measured tiers keep their values (a bar stays a bar)
            # SCOPE (user, 2026-10-06, second decision): only runs that END AT A HEAD OF
            # TIDE (nothing measured upstream); a gap with a measured bed on BOTH sides
            # is plain linear interpolation between the two measurements
            floor = how_up == "head"
            D4[i : j + 1] = np.maximum(lin, DEPTH_FLOOR_M) if floor else lin
            b.extra.setdefault("runs", []).append(
                (
                    b.grid[i],
                    b.grid[j],
                    D_dn,
                    how_dn,
                    D_up,
                    how_up,
                    float(np.mean(lin < DEPTH_FLOOR_M)) if floor else 0.0,
                )
            )
        s4 = (tz == 0) & np.isfinite(D4[k])
        dc4 = D4 / np.clip(mg, 0.4, 1.0)
        dc4 = np.where(np.isfinite(cdep), np.maximum(dc4, cdep), dc4)  # charted floor
        v4 = dat.mllw - dc4[k] * gg
        tz[s4], v[s4] = 4, v4[s4]
        # station table
        Dsec = np.where(np.isfinite(D4), D4, Dctrl)
        cnt = np.bincount(k * 5 + tz, minlength=n * 5).reshape(n, 5)
        cnt[:, 0] = 0
        stier = np.where(cnt.max(1) > 0, cnt.argmax(1), 0).astype("uint8")
        tables.append(
            {
                "branch": b.name,
                "station_m": b.grid,
                "tier": stier,
                "f_ehydro": f1,
                "f_cudem_real": f2,
                "cudem_flat_p25_p5": relief,
                "cudem_p5": p5,
                "cudem_real": real,
                "cudem_demoted": demoted,
                "controlling_m": cdep,
                "t3_bed": t3,
                "t3_src": b.t3src if b.t3src is not None else np.full(n, ""),
                "section_mean_depth": Dsec,
                "d_c": np.where(np.isfinite(D4), dc4, np.where(has3s, dc3, np.nan)),
                "in_paint": (b.grid >= b.plo) & (b.grid <= b.phi),
                "npx": npx,
            }
        )
        done_lines.append((b.line, b.grid, Dsec))
        # merge into the reach grid: deepest where branches overlap
        cur = val[rr, cc]
        take = np.isfinite(v) & (~np.isfinite(cur) | (v < cur))
        val[rr[take], cc[take]] = v[take]
        tier[rr[take], cc[take]] = tz[take]
        pin = (st >= b.plo) & (st <= b.phi)
        inspan[rr[pin], cc[pin]] = True
    out_ring = int((inspan & np.isfinite(val) & ~inring).sum())
    if out_ring:
        notes.append(f"⚠️ {out_ring} evaluated px outside the A+ ring: never painted")
    paint = (
        inspan
        & inring
        & np.isfinite(val)
        & (tier > 0)
        & ~protect
        & (~np.isfinite(ref) | (np.abs(ref - val) > TOL_M))
        & ((tier != 2) | (val < dat.mllw))  # CUDEM banks / marsh keep the merge
    )
    return Result(r, g, dat, brs, ref, val, tier, paint, inspan, tables, notes, cud, t1)


def _ring_mask(g: RGrid) -> np.ndarray:
    """True inside the A+ region ring (rivers cut at today's head of tide)."""
    import geopandas as gpd
    from rasterio.features import geometry_mask

    ring = gpd.read_file(RING).to_crs(EPSG)
    return geometry_mask(ring.geometry, (g.h, g.w), g.T, invert=True)


def _head_by_mhhw(b: Br, st, zref, mhhw: float, skip_m: float = 500.0):
    """The station where the merged bed's channel (p5 per station, +-50 m, running median
    over +-100 m) first rises above MHHW — a lidar water surface above the highest tide
    is non-tidal water: the head of tide is there, whatever the hand-set end says."""
    n = len(b.grid)
    k = np.clip(np.rint(st / STATION_M).astype(int), 0, n - 1)
    o, bnd = _station_slices(k, n)
    p5 = np.full(n, np.nan)
    for i in range(n):
        a, c = bnd[max(0, i - SLICE_STATIONS)], bnd[min(n, i + SLICE_STATIONS + 1)]
        v = zref[o[a:c]]
        v = v[np.isfinite(v)]
        if len(v) >= FILL_MIN_PX:
            p5[i] = np.percentile(v, 5)
    sm = np.array([np.nanmedian(p5[max(0, i - 4) : i + 5]) for i in range(n)])
    hit = np.nonzero((b.grid >= skip_m) & (b.grid <= b.hi) & (sm > mhhw))[0]
    return float(b.grid[hit[0]]) if len(hit) else None


def _fork_control(b: Br, done_lines) -> float:
    """A tributary with no control of its own: the section-mean depth of the main stem
    at the nearest station to the branch's first point."""
    if not done_lines:
        return np.nan
    p0 = b.line.interpolate(b.lo)
    best = (np.inf, np.nan)
    for line, grid, D in done_lines:
        s = line.project(p0)
        d = line.interpolate(s).distance(p0)
        i = int(np.clip(np.rint(s / STATION_M), 0, len(grid) - 1))
        win = D[max(0, i - 4) : i + 5]
        if d < best[0] and np.isfinite(win).any():
            best = (d, float(np.nanmedian(win)))
    return best[1]


# ── writing ───────────────────────────────────────────────────────────────────────
def _write_tif(a: np.ndarray, g: RGrid, name: str, dtype: str, nodata, tags) -> Path:
    import rasterio

    out = _out(name)
    fd, tmp = tempfile.mkstemp(dir=OUT, prefix=f".{out.name}.", suffix=".tif")
    os.close(fd)
    with rasterio.open(
        tmp,
        "w",
        driver="GTiff",
        height=g.h,
        width=g.w,
        count=1,
        dtype=dtype,
        crs=f"EPSG:{EPSG}",
        transform=g.T,
        nodata=nodata,
        compress="deflate",
        tiled=True,
    ) as d:
        d.write(a.astype(dtype), 1)
        d.update_tags(**{k: str(v) for k, v in tags.items()})
    os.chmod(tmp, 0o644)
    os.replace(tmp, out)
    return out


def _write_vrt(name: str, tifs: list[Path], nodata) -> Path:
    vrt = _out(name)
    fd, tmp = tempfile.mkstemp(dir=OUT, prefix=f".{vrt.name}.", suffix=".vrt")
    os.close(fd)
    subprocess.run(
        [
            "gdalbuildvrt",
            "-overwrite",
            "-srcnodata",
            str(nodata),
            "-vrtnodata",
            str(nodata),
            tmp,
            *map(str, tifs),
        ],
        check=True,
        capture_output=True,
    )
    os.chmod(tmp, 0o644)
    os.replace(tmp, vrt)
    print(f"wrote {vrt}")
    return vrt


def _area_below(z: np.ndarray, plane: float) -> float:
    return float(np.nansum(np.clip(plane - z, 0.0, None)) * RES**2)


def summarise(res: Result) -> dict:
    """The per-reach row of ``reaches.csv``."""
    r, g, dat = res.reach, res.g, res.dat
    km2 = RES**2 / 1e6
    P = res.paint
    after = np.where(P, res.val, res.ref)
    row = {
        "reach": r.name,
        "label": r.label,
        "mllw": round(dat.mllw, 3),
        "mhhw": round(dat.mhhw, 3),
        "datum_stations": dat.note,
        "painted_km2": round(P.sum() * km2, 4),
    }
    for t in (1, 2, 3, 4):
        row[f"painted_t{t}_km2"] = round((P & (res.tier == t)).sum() * km2, 4)
    sp = res.inspan & np.isfinite(res.val)
    for t in (1, 2, 3, 4):
        row[f"channel_t{t}_km2"] = round((sp & (res.tier == t)).sum() * km2, 4)
    km = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 0: 0.0}
    span_m = 0.0
    for tb in res.stations:
        m = tb["in_paint"]
        span_m += m.sum() * STATION_M
        for t in km:
            km[t] += float((m & (tb["tier"] == t)).sum()) * STATION_M / 1000
    for t in (1, 2, 3, 4):
        row[f"km_t{t}"] = round(km[t], 2)
    row["km_none"] = round(km[0], 2)
    if P.any():
        row["old_bed_p50"] = round(float(np.nanmedian(res.ref[P])), 2)
        row["new_bed_p50"] = round(float(np.nanmedian(res.val[P])), 2)
        row["new_bed_p5"] = round(float(np.nanpercentile(res.val[P], 5)), 2)
        row["new_bed_p95"] = round(float(np.nanpercentile(res.val[P], 95)), 2)
        row["raised_km2"] = round((P & (res.val > res.ref + TOL_M)).sum() * km2, 4)
    # span-mean section area below MLLW over the paint span (m²)
    span_px = res.inspan
    L = max(span_m, 1.0)
    row["span_km"] = round(span_m / 1000, 2)
    row["a_mllw_before"] = round(_area_below(res.ref[span_px], dat.mllw) / L, 1)
    row["a_mllw_after"] = round(_area_below(after[span_px], dat.mllw) / L, 1)
    if r.name in OLD_BUILDS:
        for tag, fn in zip(("flat", "shaped"), OLD_BUILDS[r.name]):
            o = warp(rb.RB / fn, g)
            z = np.fmin(res.ref, o)
            row[f"a_mllw_old_{tag}"] = round(_area_below(z[span_px], dat.mllw) / L, 1)
    return row


def write_reach(res: Result) -> tuple[Path, Path]:
    r = res.reach
    z = np.where(res.paint, res.val, NODATA)
    t = np.where(res.paint, res.tier, 0)
    tags = {
        "reach": r.name,
        "rule": "hierarchy eHydro>CUDEM real>chart/NOS>slope",
        "mllw_navd88": res.dat.mllw,
        "datum": res.dat.note,
    }
    a = _write_tif(
        z, res.g, f"riverbed_hier_{r.name}_{VER}.tif", "float32", NODATA, tags
    )
    b = _write_tif(t, res.g, f"riverbed_hier_{r.name}_tier_{VER}.tif", "uint8", 0, tags)
    return a, b


def build(names: list[str] | None) -> None:
    import pandas as pd

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    todo = [BY_NAME[n] for n in names] if names else list(REACHES)
    rows, prof_rows, tifs, tiers, notes = [], [], [], [], []
    for r in todo:
        t0 = time.time()
        print(f"\n=== {r.name}: {r.label}")
        res = evaluate(r)
        a, b = write_reach(res)
        tifs.append(a)
        tiers.append(b)
        row = summarise(res)
        rows.append(row)
        notes.append(f"## {r.name}\n" + "\n".join(f"- {x}" for x in res.notes))
        for br in res.brs:
            for x in br.extra.get("runs", []):
                fl = f", floored on {x[6]:.0%}" if x[6] > 0 else ""
                notes.append(
                    f"- {br.name}: slope {x[0]:.0f}..{x[1]:.0f} m, section mean "
                    f"{x[2]:.2f} m ({x[3]}) -> {x[4]:.2f} m ({x[5]}) below MLLW{fl}"
                )
        for tb in res.stations:
            df = pd.DataFrame({k: v for k, v in tb.items() if k != "branch"})
            df.insert(0, "branch", tb["branch"])
            df.insert(0, "reach", r.name)
            prof_rows.append(df)
        _save_npz(res)
        for k, v in row.items():
            if k not in ("label", "datum_stations"):
                print(f"   {k}: {v}")
        print("   " + "\n   ".join(res.notes))
        print(f"   ({time.time() - t0:.0f} s)")
    tag = ("" if names is None else "_subset") + ("" if VER == "v4" else f"_{VER}")
    _atomic_csv(LOG_DIR / f"reaches{tag}.csv", pd.DataFrame(rows))
    prof = pd.concat(prof_rows, ignore_index=True)
    _atomic_csv(LOG_DIR / f"stations{tag}.csv", prof)
    _atomic_bytes(LOG_DIR / f"notes{tag}.md", ("\n\n".join(notes) + "\n").encode())
    if names is not None and VER != "v4":
        # a new VERSION of a subset: the full overlay = the v4 members, rebuilt ones swapped
        for kind, built, nodata in (("", tifs, NODATA), ("tier_", tiers, 0)):
            members = _vrt_members(OUT / f"riverbeds_hierarchy_{kind}v4.vrt")
            swap = {
                f"riverbed_hier_{r.name}_{kind}v4.tif": p for r, p in zip(todo, built)
            }
            new = [swap.get(m.name, m) for m in members]
            assert sum(m.name in swap for m in members) == len(swap), "reach not in v4"
            _write_vrt(f"riverbeds_hierarchy_{kind}{VER}.vrt", new, nodata)
    if names is None:
        cols = ["reach", "branch", "station_m", "tier", "section_mean_depth", "d_c"]
        _atomic_csv(_out(f"riverbeds_hierarchy_{VER}_profiles.csv"), prof[cols])
        _write_vrt(f"riverbeds_hierarchy_{VER}.vrt", tifs, NODATA)
        _write_vrt(f"riverbeds_hierarchy_tier_{VER}.vrt", tiers, 0)
        fill_cases()


def _cache_name(reach: str) -> str:
    return f"{reach}.npz" if VER == "v4" else f"{reach}_{VER}.npz"


def _vrt_members(vrt: Path) -> list[Path]:
    import xml.etree.ElementTree as ET

    root = ET.parse(vrt).getroot()
    return [
        (vrt.parent / e.text) if e.get("relativeToVRT") == "1" else Path(e.text)
        for e in root.iter("SourceFilename")
    ]


def _save_npz(res: Result) -> None:
    """Arrays the maps need, cached on scratch (not home)."""
    d = SRC / "cache"
    d.mkdir(parents=True, exist_ok=True)
    lines = [np.asarray(b.line.coords) for b in res.brs]
    np.savez_compressed(
        d / _cache_name(res.reach.name),
        ref=res.ref,
        val=res.val,
        tier=res.tier,
        paint=res.paint,
        inspan=res.inspan,
        cudem=res.cudem,
        t1=res.t1,
        grid=np.array([res.g.x0, res.g.y1, res.g.w, res.g.h]),
        mllw=res.dat.mllw,
        mhhw=res.dat.mhhw,
        **{f"line{i}": ln for i, ln in enumerate(lines)},
        **{f"span{i}": np.array([b.plo, b.phi]) for i, b in enumerate(res.brs)},
    )


# ── the fill test on known cases ──────────────────────────────────────────────────
#: Known cases for the fill test, each evaluated EXACTLY as a reach station is: a centreline
#: traced through the NHD polygon (+ survey coverage), +-50 m slices of CUDEM, ``is_fill``.
FILL_CASES = (
    HReach(
        "fill",
        "Cohansey above the mouth (CUDEM ~0 m)",
        box=(-75.370, 39.360, -75.300, 39.420),
        branches=(TBranch("Cohansey", (-75.356, 39.366), (-75.312, 39.405)),),
    ),
    HReach(
        "real",
        "Cohansey mouth (CUDEM holds NOS D00081's scour hole)",
        box=(-75.385, 39.335, -75.350, 39.366),
        branches=(TBranch("Cohansey", (-75.373, 39.343), (-75.357, 39.362)),),
    ),
    HReach(
        "real",
        "Maurice federal reach below 39.21 (eHydro MA_01_MRC 2021)",
        box=(-75.060, 39.165, -75.000, 39.212),
        branches=(TBranch("Maurice", (-75.037, 39.172), (-75.030, 39.210)),),
        ehydro=(
            Ehydro("MA_01_MRC_20210721_CS", "CENAP"),
        ),  # its coverage = the channel
    ),
    HReach(
        "real",
        "Delaware main channel off Marcus Hook (eHydro PS_12_MAR 2016)",
        box=(-75.465, 39.775, -75.375, 39.830),
        branches=(TBranch("Delaware", (-75.4568, 39.7823), (-75.3825, 39.8235)),),
    ),
    HReach(
        "real",
        "Inside Thorofare under the 2010 lidar (CUDEM beneath it)",
        box=(-74.485, 39.335, -74.440, 39.367),
        branches=(TBranch("Inside Thorofare", (-74.478, 39.342), (-74.446, 39.361)),),
        halfwidth_m=80.0,
        ehydro=(Ehydro("IW_10_174_20230911_XC", "CENAP"),),
    ),
    HReach(
        "fill",
        "Rancocas lower main stem (CUDEM 0.00 m)",
        box=(-74.985, 40.020, -74.900, 40.050),
        branches=(TBranch("Rancocas", (-74.975, 40.042), (-74.905, 40.025)),),
    ),
    HReach(
        "fill",
        "Mullica 2 km below the GMRT hole (CUDEM -0.56 m)",
        box=(-74.510, 39.540, -74.460, 39.575),
        branches=(TBranch("Mullica", (-74.471, 39.552), (-74.500, 39.565)),),
    ),
)


def fill_cases() -> None:
    """The fill test on the known cases (``FILL_CASES``): per station, as in ``evaluate``."""
    import pandas as pd
    import shapely

    rows = []
    for c in FILL_CASES:
        brs = branches_trace(c)
        b = brs[0]
        g = _grid_for(brs)
        cu = warp(CUDEM[0], g)
        cu = np.where(np.isfinite(cu), cu, warp(CUDEM[1], g))
        dat = datum_rule(c.branches[0].mouth, shapely.union_all([x.chan for x in brs]))
        pt = td.Part(b.line, b.chan, b.grid, b.grid * 0.0, b.grid * 0.0, 0, 0, "", 0)
        rr, cc, _, _, st, _, _ = td.bank_field(pt, (g.h, g.w), g.T)
        n = len(b.grid)
        k = np.clip(np.rint(st / STATION_M).astype(int), 0, n - 1)
        z = cu[rr, cc].astype("float64")
        o, bnd = _station_slices(k, n)
        fills, flats, p5s = [], [], []
        for i in range(n):
            a_, c_ = (
                bnd[max(0, i - SLICE_STATIONS)],
                bnd[min(n, i + SLICE_STATIONS + 1)],
            )
            v = z[o[a_:c_]]
            v = v[np.isfinite(v)]
            if len(v) < FILL_MIN_PX:
                continue
            f, fl, q5 = is_fill(v, dat.mllw)
            fills.append(f)
            flats.append(fl)
            p5s.append(q5)
        fills = np.array(fills)
        rows.append(
            {
                "case": c.label,
                "expected": c.name,
                "stations": len(fills),
                "frac_fill": round(float(fills.mean()), 3) if len(fills) else np.nan,
                "verdict": ("fill" if fills.mean() > 0.5 else "real")
                if len(fills)
                else "",
                "mllw": round(dat.mllw, 3),
                "cudem_p5_median": round(float(np.median(p5s)), 2) if p5s else np.nan,
                "flat_p25_p5_median": round(float(np.median(flats)), 2)
                if flats
                else np.nan,
                "cudem_p50": round(float(np.nanmedian(z)), 2),
            }
        )
        print(rows[-1])
    _atomic_csv(LOG_DIR / "fill_test_cases.csv", pd.DataFrame(rows))


# ── maps ──────────────────────────────────────────────────────────────────────────
def maps(names: list[str] | None) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap

    (LOG_DIR / "maps").mkdir(parents=True, exist_ok=True)
    tcmap = ListedColormap(["#1f77b4", "#2ca02c", "#ff7f0e", "#d62728"])
    for r in [BY_NAME[n] for n in names] if names else REACHES:
        f = SRC / "cache" / _cache_name(r.name)
        if not f.exists():
            continue
        d = np.load(f)
        x0, y1, w, h = d["grid"]
        ext = (x0, x0 + w * RES, y1 - h * RES, y1)
        P = d["paint"]
        after = np.where(P, d["val"], d["ref"])
        lines = [d[k] for k in sorted(d.files) if k.startswith("line")]
        spans = [d[k] for k in sorted(d.files) if k.startswith("span")]
        fig = plt.figure(figsize=(22, 13), constrained_layout=True)
        gs = fig.add_gridspec(2, 3, height_ratios=[1.6, 1])
        ax = [fig.add_subplot(gs[0, i]) for i in range(3)]
        kw = dict(extent=ext, origin="upper", interpolation="nearest")
        lo = float(np.nanpercentile(d["val"][P], 2)) if P.any() else -4.0
        vmin, vmax = min(lo, -3.0), 2.0
        cm = plt.get_cmap("terrain").copy()
        msk = d["inspan"] | P
        bb = np.nonzero(msk.any(0))[0], np.nonzero(msk.any(1))[0]
        for a, z, t in ((ax[0], d["ref"], "before"), (ax[1], after, "after (painted)")):
            im = a.imshow(
                np.where(np.isfinite(z), z, np.nan), cmap=cm, vmin=vmin, vmax=vmax, **kw
            )
            a.set_title(f"{r.name}: {t}")
        fig.colorbar(im, ax=ax[:2], shrink=0.6, label="bed, m NAVD88")
        tt = np.where(P, d["tier"], 0).astype(float)
        tt[tt == 0] = np.nan
        ax[2].imshow(
            np.where(d["inspan"], 0.5, np.nan), cmap="Greys", vmin=0, vmax=1, **kw
        )
        ti = ax[2].imshow(tt, cmap=tcmap, vmin=0.5, vmax=4.5, **kw)
        cb = fig.colorbar(ti, ax=ax[2], shrink=0.6, ticks=[1, 2, 3, 4])
        cb.ax.set_yticklabels([TIER_NAME[i] for i in (1, 2, 3, 4)])
        ax[2].set_title("painted pixels by tier (grey: span, unpainted)")
        if len(bb[0]):
            xa = x0 + np.array([bb[0][0] - 40, bb[0][-1] + 40]) * RES
            ya = y1 - np.array([bb[1][-1] + 40, bb[1][0] - 40]) * RES
            for a in ax:
                a.set_xlim(*xa)
                a.set_ylim(*ya)
        for a in ax:
            for ln in lines:
                a.plot(ln[:, 0], ln[:, 1], "k-", lw=0.4, alpha=0.6)
            a.set_xticks([])
            a.set_yticks([])
        # profile along each branch: axis (p5 per 100 m) before / after
        axp = fig.add_subplot(gs[1, :])
        import shapely

        rr, cc = np.nonzero(d["inspan"])
        px, py = x0 + (cc + 0.5) * RES, y1 - (rr + 0.5) * RES
        off = 0.0
        for i, (ln, sp) in enumerate(zip(lines, spans)):
            L = shapely.LineString(ln)
            s = shapely.line_locate_point(L, shapely.points(px, py))
            dist = shapely.distance(shapely.points(px, py), L)
            sel = (dist < 300) & (s >= sp[0]) & (s <= sp[1])
            bins = np.arange(sp[0], sp[1] + 100, 100)
            kb = np.digitize(s[sel], bins)
            zb, za, tb = [], [], []
            for j in range(1, len(bins)):
                m = kb == j
                if m.sum() < 3:
                    zb.append(np.nan)
                    za.append(np.nan)
                    tb.append(0)
                    continue
                zb.append(np.nanpercentile(d["ref"][rr[sel][m], cc[sel][m]], 5))
                za.append(np.nanpercentile(after[rr[sel][m], cc[sel][m]], 5))
                tv = d["tier"][rr[sel][m], cc[sel][m]]
                tv = tv[tv > 0]
                tb.append(int(np.bincount(tv).argmax()) if len(tv) else 0)
            xk = (off + bins[1:] - sp[0]) / 1000
            axp.plot(
                xk, zb, color="0.5", lw=1, label="before (axis p5)" if i == 0 else None
            )
            axp.plot(
                xk, za, color="k", lw=1.4, label="after (axis p5)" if i == 0 else None
            )
            tb = np.array(tb)
            for t in (1, 2, 3, 4):
                m = tb == t
                axp.scatter(
                    xk[m],
                    np.array(za)[m],
                    s=8,
                    color=tcmap(t - 1),
                    label=TIER_NAME[t] if i == 0 else None,
                    zorder=3,
                )
            off += sp[1] - sp[0] + 500
        axp.axhline(float(d["mllw"]), color="b", ls="--", lw=0.8, label="MLLW")
        axp.axhline(float(d["mhhw"]), color="c", ls=":", lw=0.8, label="MHHW")
        axp.set_xlabel("km along the painted span (branches end to end, 0.5 km gaps)")
        axp.set_ylabel("m NAVD88")
        axp.legend(ncol=8, fontsize=8)
        axp.grid(alpha=0.3)
        png = f"{r.name}.png" if VER == "v4" else f"{r.name}_{VER}.png"
        fig.savefig(LOG_DIR / "maps" / png, dpi=70)
        plt.close(fig)
        print(f"wrote maps/{png}")


# ── the fill test, domain-wide (a screen for reaches not built here) ─────────────
AUDIT = ROOT / "logs" / "audit_v4_hot_plus_2026-10-05"
LATTICE = AUDIT / "channels_and_3dep" / "raw" / "grids" / "lattice25.npz"
OSC = AUDIT / "blocked_low_ground" / "osc.npz"
LAND_TIERS = (
    "usace_nj_2010_v3",
    "coned_sw_raritan",
    "cudem_nj_v3",
    "cudem_delaware_v4",
    "nj_10ft_dem_v4",
    "cudem13_v3",
    "dep3_v4",
    "gmrt_v4",
)


def _tier_keys() -> list[str]:
    sys.path.insert(0, str(AUDIT / "channels_and_3dep"))
    import common  # noqa: PLC0415  (the audit's tier list = the premier's)

    return list(common.TIER_KEYS)


def screen() -> None:
    """Every active 25 m lattice cell inside an NHD river polygon whose winning tier is a
    lidar / DEM product that reads FLAT (+-12.5 m range < 5 cm, the audit's ``rng``) and
    NOT BELOW low water (> nearest-station MLLW - 0.5 m): a proxy of the station test at
    25 m. Grouped by NHD polygon; polygons a reach here covers are flagged."""
    import geopandas as gpd
    import pandas as pd

    keys = _tier_keys()
    L = np.load(LATTICE)
    osc = np.load(OSC)["osc_sandy"]
    x, y, win, val, rng = L["x"], L["y"], L["win"], L["val"], L["rng"]
    land = np.isin(win, [keys.index(k) for k in LAND_TIERS])
    mllw = _mllw_nearest(x, y)
    cand = land & (rng < 0.05) & (val > mllw - FILL_BELOW_MLLW_M) & (val < 1.5)
    idx = np.nonzero(cand)[0]
    g = gpd.read_file(NHD_RIVERS).to_crs(EPSG).reset_index(drop=True)
    pts = gpd.GeoDataFrame(geometry=gpd.points_from_xy(x[idx], y[idx]), crs=EPSG)
    hit = gpd.sjoin(pts, g[["geometry"]], predicate="within", how="inner")
    built = _built_footprint()
    rows = []
    for pid, sub in hit.groupby("index_right"):
        ii = idx[sub.index.to_numpy()]
        a = len(ii) * 625 / 1e6
        if a < 0.02:
            continue
        geom = g.geometry.iloc[pid]
        c = geom.representative_point()
        lon, lat = _to_ll(c.x, c.y)
        cov = built.intersection(geom).area / max(geom.area, 1)
        rows.append(
            {
                "nhd_id": g.permanent_identifier.iloc[pid],
                "ftype": int(g.ftype.iloc[pid]),
                "lon": round(lon, 4),
                "lat": round(lat, 4),
                "polygon_km2": round(geom.area / 1e6, 3),
                "fill_km2": round(a, 3),
                "bed_p50": round(float(np.median(val[ii])), 2),
                "mllw": round(float(np.median(mllw[ii])), 3),
                "tiers": ", ".join(
                    f"{keys[t]} {n}"
                    for t, n in zip(*np.unique(win[ii], return_counts=True))
                ),
                "osc_p50": round(float(np.nanmedian(osc[L["face"][ii]])), 2),
                "frac_in_this_overlay": round(float(cov), 2),
            }
        )
    df = pd.DataFrame(rows).sort_values("fill_km2", ascending=False)
    _atomic_csv(LOG_DIR / "fill_screen.csv", df)
    print(df.head(60).to_string(index=False))
    print(f"{len(df)} polygons, {df.fill_km2.sum():.2f} km² fill-like")


def _built_footprint():
    """Union of this overlay's evaluated channels (from the cached arrays), UTM."""
    import shapely
    from rasterio import features

    polys = []
    for r in REACHES:
        f = SRC / "cache" / _cache_name(r.name)
        if not f.exists():
            continue
        d = np.load(f)
        x0, y1, w, h = d["grid"]
        g = RGrid(float(x0), float(y1), int(w), int(h))
        m = d["inspan"].astype("uint8")
        for geom, v in features.shapes(m, mask=m > 0, transform=g.T):
            polys.append(shapely.geometry.shape(geom).buffer(10))
    return shapely.union_all(polys) if polys else shapely.Point(0, 0)


# ── the premier's own tiers against the hierarchy ─────────────────────────────────
def _mllw_nearest(x, y) -> np.ndarray:
    """MLLW - NAVD88 of the nearest station publishing both datums (a screen, not the
    per-reach rule)."""
    from scipy.spatial import cKDTree

    sx, sy, sm = [], [], []
    for _, (_, la, lo, ds) in _stations().items():
        p = _utm(lo, la)
        sx.append(p.x)
        sy.append(p.y)
        sm.append(ds["MLLW"] - ds["NAVD88"])
    _, j = cKDTree(np.column_stack([sx, sy])).query(np.column_stack([x, y]))
    return np.asarray(sm)[j]


def premier() -> None:
    """Where four premier tiers win the merge (the audit's 25 m lattice of active cells):
    their area, and their bed against CUDEM where CUDEM itself says SUB-TIDAL WATER and
    passes the fill test cell by cell (CUDEM < MLLW - 0.5 m: there the hierarchy's answer
    is CUDEM, unless a survey or chart outranks it). Plus Shooters Island."""
    import pandas as pd

    keys = _tier_keys()
    L = np.load(LATTICE)
    x, y, win, val = L["x"], L["y"], L["win"], L["val"]
    rows = []
    for k in (
        "riverbeds_v4",
        "usace_nj_2010_v3",
        "coned_sw_raritan",
        "ehydro_south_v3",
    ):
        sel = np.nonzero(win == keys.index(k))[0]
        if not len(sel):
            continue
        cu = rb._sample(list(CUDEM), x[sel], y[sel])
        mllw = _mllw_nearest(x[sel], y[sel])
        d = val[sel] - cu
        water = np.isfinite(cu) & (cu < mllw - FILL_BELOW_MLLW_M)
        lon, lat = _to_ll(x[sel], y[sel])
        km2 = 625 / 1e6
        row = {
            "tier": k,
            "wins_km2": round(len(sel) * km2, 2),
            "with_cudem_km2": round(np.isfinite(cu).sum() * km2, 2),
            "cudem_subtidal_km2": round(water.sum() * km2, 2),
            "there_tier_minus_cudem_p50": round(float(np.nanmedian(d[water])), 2)
            if water.any()
            else np.nan,
            "there_shallower_by_0.5_km2": round((water & (d > 0.5)).sum() * km2, 3),
            "there_deeper_by_0.5_km2": round((water & (d < -0.5)).sum() * km2, 3),
            "tier_below_mllw_no_cudem_km2": round(
                (~np.isfinite(cu) & (val[sel] < mllw)).sum() * km2, 2
            ),
            "lon": f"{np.min(lon):.3f}..{np.max(lon):.3f}",
            "lat": f"{np.min(lat):.3f}..{np.max(lat):.3f}",
        }
        rows.append(row)
        print(row)
    _atomic_csv(LOG_DIR / "premier_tiers.csv", pd.DataFrame(rows))
    shooters()


def shooters() -> None:
    """South of Shooters Island: how much of NJ_07_SSI's own coverage the
    ``ehydro_refreeze_cenan_v4`` overlay paints, and what the bed is where it does not."""
    import geopandas as gpd
    from rasterio.features import geometry_mask

    d = DATA / "elevation_v4/ehydro/raw/NJ_07_SSI_20141229_CS_4243_25X"
    cov = gpd.read_file(dl.ehnj._one(d, ".gdb"), layer="Bathymetry_Vector").to_crs(EPSG)
    a, b, c, e = cov.total_bounds
    g = RGrid(
        np.floor(a / RES) * RES,
        np.ceil(e / RES) * RES,
        int((c - a) / RES) + 2,
        int((e - b) / RES) + 2,
    )
    inside = geometry_mask(cov.geometry, (g.h, g.w), g.T, invert=True)
    ov = warp(DATA / "elevation_v4/ehydro/ehydro_refreeze_cenan_v4.tif", g)
    tpl = warp(TEMPLATE, g)
    painted = inside & np.isfinite(ov)
    rest = inside & ~np.isfinite(ov)
    txt = (
        f"Shooters Island NJ_07_SSI: coverage {inside.sum() * RES**2 / 1e6:.3f} km2, "
        f"painted by ehydro_refreeze_cenan_v4 {painted.sum() / max(inside.sum(), 1):.1%}"
        f" (bed p50 {np.nanmedian(ov[painted]):+.2f}); the rest (the survey's own >= -1 m"
        f" water-only clip + interpolation gaps) keeps the merge, p50 "
        f"{np.nanmedian(tpl[rest]):+.2f} m"
    )
    print(txt)
    _atomic_bytes(LOG_DIR / "shooters_island.txt", (txt + "\n").encode())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "stage", choices=["fetch", "build", "maps", "screen", "premier", "cases"]
    )
    ap.add_argument("--reach", action="append", choices=sorted(BY_NAME))
    ap.add_argument(
        "--version",
        default="v4",
        help="output tag (riverbed_hier_<reach>_<tag>.tif); v4 is frozen — 2026-10-23",
    )
    a = ap.parse_args()
    global VER  # noqa: PLW0603 (a CLI-wide output tag, read by the writers)
    VER = a.version
    if a.stage == "fetch":
        fetch()
    elif a.stage == "build":
        build(a.reach)
    elif a.stage == "maps":
        maps(a.reach)
    elif a.stage == "screen":
        screen()
    elif a.stage == "cases":
        fill_cases()
    else:
        premier()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
