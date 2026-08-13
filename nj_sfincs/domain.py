"""Domain registry — ALL geography, in one place, keyed by ``NJ_DOMAIN``.

The rule of thumb for what belongs here: if moving the domain would make a number
wrong, it is domain geography and belongs in ``Domain``. If it would stay right (a
physics constant, a solver tolerance, a datum offset), it does not.

This registry exists because the alternative was measured. In the first version of this
project every geographic fact was a literal somewhere — ``SANDY_HOOK_TIP_Y = 4_476_000``
in ``model.py``, a sloped-easting HWM classifier in ``validate.py``, a window in
``plots.py``, ``latitude = 40.32`` in ``config.py``, a hand-typed bbox in half the
download scripts. That is fine for exactly one domain and becomes a hunt through five
modules for every new one, with a silent stale value as the failure mode.

TWO INVARIANTS THIS FILE ENFORCES BY CONSTRUCTION
-------------------------------------------------
1. **Every box is fully bounded.** ``MaskOverride``, ``BoundaryArm``, ``NoWaterLevelBox``
   and ``land_boxes`` all require four finite bounds. The previous repo allowed ``None``
   for "unbounded on that side", and two of its three overrides used it — including
   ``arthur_kill_north``, which flipped ``3 -> 2`` for everything north of a latitude
   with THREE unbounded sides and put 70 water-level boundary cells on dry land. An
   unbounded box is silently correct on the domain it was written for and silently wrong
   on the next one. There is no type here that can express one.

2. **A frozen domain cannot be built.** ``frozen=True`` marks a domain that exists only
   so archived runs can be staged and scored. ``build_static`` refuses it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

ROOT = Path(os.environ.get("NJ_ROOT", Path(__file__).resolve().parents[1]))
DATA = ROOT / "data"

Box = tuple[float, float, float, float]  # (xmin, ymin, xmax, ymax), ALL required


@dataclass(frozen=True)
class ObsGauge:
    """One SFINCS observation point + how to score it.

    ``name`` is what lands in ``sfincs.obs`` and therefore in ``sfincs_his.nc``;
    every his-based metric matches it by substring, so it must stay unique.
    ``obs_file`` / ``obs_var`` / ``obs_station`` say where the OBSERVED series
    lives (relative to ``data/``); ``None`` means model-only (no scoring).
    ``kind`` is ``surge`` (compare the peak) or ``tide`` (compare range/phase).
    """

    name: str
    lon: float
    lat: float
    kind: str = "surge"
    obs_file: str | None = None
    obs_var: str | None = None
    obs_station: str | int | None = None

    #: True if this gauge's record survives the storm crest. The whole claim of a domain
    #: that COMPUTES a basin instead of forcing it is untestable without at least two of
    #: these inside that basin — see the gate in docs/STATUS.md.
    survives_crest: bool = False

    #: Last good sample, ``YYYY-MM-DD HH:MM``, for a gauge that DIED mid-storm. When set,
    #: the peak comparison is made over ``[start, record_ends]`` on both sides. Comparing
    #: a full model peak against a truncated observed one understates the model by
    #: whatever the gauge missed, and reads as a model error.
    record_ends: str | None = None

    #: Where this gauge's MODELLED series comes from — and the two are not
    #: interchangeable:
    #:   ``"his"``  the SFINCS observation point, 10-min. Resolves the crest.
    #:   ``"map"``  the median over wet channel cells near the gauge, hourly.
    #: SFINCS snaps an obs point to whatever cell contains it, and several of these sit on
    #: DRY BANK cells (measured ``point_zb`` +0.99, +1.14, +1.79 m). That does not
    #: invalidate the PEAK — at the crest the water surface is locally continuous, so a
    #: bank cell and the channel beside it share the same ``zs`` — but it is fatal for the
    #: pre-storm TIDE, which is ~0.7 m about NAVD88 0 and never reaches such a cell at all.
    #: Its "tide" is then pure artifact. Set ``"map"`` for any gauge whose obs point lands
    #: dry; the cost is hourly resolution.
    series_source: str = "his"

    note: str = ""


@dataclass(frozen=True)
class MaskOverride:
    """One rectangular mask reclass, applied after hydromt sets the boundaries.

    ``frm``/``to`` are SFINCS mask codes (1 active, 2 waterlevel BC, 3 outflow).
    ``box`` is in the domain's projected CRS and **all four bounds are required** —
    see this module's docstring for the 70-cells-on-dry-land reason why.
    """

    name: str
    frm: int
    to: int
    box: Box
    why: str = ""


@dataclass(frozen=True)
class BoundaryArm:
    """A declared stretch of open boundary. A ``mask==2`` cell outside every arm is a BUG.

    THE INVERSION THIS REPRESENTS. Previously the water-level boundary was whatever
    ``create_boundary`` produced, patched afterwards by half-plane ``MaskOverride``\\ s.
    That is a blacklist: it can only remove the wrongness someone already noticed, and
    three separate times it did not (a free-outflow face across the Navesink, an ocean
    level across the Manahawkin bay cross-section, an ocean level 2.6 km inside Barnegat
    Inlet). Every one of them ran to completion and produced numbers nobody could tell
    were wrong.

    An arm whitelist inverts it. The boundary must be declared before it can exist, every
    ``mask==2`` cell must fall inside exactly one arm box, and every one of them must be
    genuinely wet (``zb <= max_bed_m``) or the build fails. The per-arm cell count is
    bracketed too, so an arm that silently gains or loses most of its cells — the way a
    mask change or a new ``mask_zmin`` would do it — is a build error rather than a
    different experiment wearing the same name.

    ``btype`` is SFINCS's own vocabulary: ``waterlevel`` (mask 2) or ``outflow`` (mask 3).
    """

    name: str
    box: Box
    btype: str = "waterlevel"
    min_cells: int = 1
    max_cells: int = 10_000
    #: A boundary-condition cell must be WET. A BC on dry ground is not a weak boundary,
    #: it is a source term with no physical meaning.
    max_bed_m: float = -0.5
    why: str = ""


@dataclass(frozen=True)
class NoWaterLevelBox:
    """A rectangle in which a water-level BC (``mask==2``) is a BUILD-TIME ERROR.

    ``MaskOverride`` repairs a bad boundary cell after the fact; this asserts one can
    never appear. Both are wanted: the override is the repair, this is the alarm that
    says the repair is still needed. A repair with no invariant behind it is the exact
    structural gap that produced the Barnegat Inlet clamp.

    Redundant with ``boundary_arms`` on a domain that declares them — deliberately.
    """

    name: str
    box: Box
    why: str = ""


@dataclass(frozen=True)
class BasinRule:
    """One HWM reporting basin, as coordinate thresholds in the domain CRS.

    Rules are evaluated IN ORDER and the FIRST match wins, so write them most-specific
    first. The last rule should be an unconstrained catch-all.

    ⚠️ ORDER IS LOAD-BEARING AND IS PART OF THE PUBLISHED NUMBERS. Every per-basin
    statistic depends on first-match-wins, so reordering rules silently re-partitions
    the marks.

    Thresholds rather than hand-drawn polygons is a deliberate choice: a box and a slope
    are auditable numbers that can be checked against a chart, whereas a digitised
    polygon is opaque once written. The one concession to geometry is ``slope``, because
    the NJ barrier coast runs NNE — so the ocean/estuary divide is a SLOPED easting,
    ``x = slope_x0 + slope * (y - slope_y0)``, and ``side`` selects east (+1) or
    west (-1) of it.
    """

    name: str
    xmin: float | None = None
    ymin: float | None = None
    xmax: float | None = None
    ymax: float | None = None
    slope_x0: float | None = None
    slope_y0: float | None = None
    slope: float = 0.0
    side: int = 1
    why: str = ""

    def matches(self, x, y):
        import numpy as np

        ok = np.ones(np.shape(x), dtype=bool)
        if self.xmin is not None:
            ok &= x >= self.xmin
        if self.xmax is not None:
            ok &= x < self.xmax
        if self.ymin is not None:
            ok &= y >= self.ymin
        if self.ymax is not None:
            ok &= y < self.ymax
        if self.slope_x0 is not None:
            div = self.slope_x0 + self.slope * (y - self.slope_y0)
            ok &= (x > div) if self.side > 0 else (x <= div)
        return ok


@dataclass(frozen=True)
class Domain:
    name: str
    region: Path
    epsg: int
    latitude: float  # Coriolis reference [deg N] — domain mean

    #: 🔴 THE DEPTH THE ACTIVE MASK IS CUT AT, and therefore where the water-level
    #: boundary lands. This lives on the DOMAIN, not on ``BaseConfig``, because it is
    #: half of ``sha(z, mask)`` — the domain fingerprint. An "arm" that changed it would
    #: fail ``assert_sealed_domain`` on its own staged copy, which is the guard working
    #: correctly and the arm being the wrong shape. A −10 m and a −15 m boundary are two
    #: DOMAINS, registered separately, sharing one ``mesh_key``.
    #:
    #: ``add_waves`` also reads this for the SnapWave seaward band, so it follows
    #: automatically — a boundary-depth domain does not need a second knob set.
    mask_zmin: float = -10.0

    #: Which frozen mesh directory this domain is built from: ``data/frozen_mesh_<key>``.
    #: Defaults to the domain's own name. Two domains SHARE a key when they differ only
    #: in ``mask_zmin`` — same faces, same bed, re-derived mask, subgrid tables reused
    #: (every face already has them), so no rebuild and no re-tabulation.
    mesh_key: str | None = None

    #: A frozen domain is staged and scored, never built. Set on any domain kept purely
    #: so archived runs stay reproducible.
    frozen: bool = False

    #: Quadtree refinement polygons for THIS domain. A refinement recipe is not portable:
    #: a level gate written for one basin will happily refine a different basin's open
    #: water to its finest level, and a shelf polygon written for one coast lands in open
    #: ocean on another.
    refinement: Path | None = None

    obs_gauges: tuple[ObsGauge, ...] = ()
    mask_overrides: tuple[MaskOverride, ...] = ()

    #: THE WHITELIST. When non-empty, every ``mask==2`` cell must sit inside exactly one
    #: of these and satisfy its ``max_bed_m``; see ``BoundaryArm``.
    boundary_arms: tuple[BoundaryArm, ...] = ()

    #: Rectangles forced INACTIVE regardless of what the DEM says — a declared land
    #: boundary. Used where the model must stop at a real shoreline that no depth
    #: threshold reproduces (a bank opposite a forced cross-section, an excluded bay).
    #: Declared rather than DEM-dependent on purpose: a depth threshold is a statement
    #: about elevation, and the mask it produces is a statement about topology.
    land_boxes: tuple[tuple[str, Box, str], ...] = ()

    #: Force these lon/lat boxes active at any depth, so dredged channels and scoured
    #: inlet gorges don't punch inactive holes through an interior.
    always_active_boxes_ll: tuple[tuple[float, float, float, float], ...] = ()

    #: Rectangles (projected CRS) in which a water-level BC is a build-time error.
    no_waterlevel_boxes: tuple[NoWaterLevelBox, ...] = ()

    #: Northing above which the coast is no longer open ocean (a spit tip, a harbour
    #: mouth). Incident wave energy and wave-boundary support points are taken only
    #: below it.
    open_coast_max_y: float | None = None

    #: Ordered HWM basin rules, first match wins. Splitting marks by hydraulic basin
    #: stops the pooled RMSE from blending ocean-front marks (surge delivered directly)
    #: with behind-barrier estuary marks (the conveyance test). Pooling them once hid a
    #: completely dammed inlet behind a near-perfect basin bias.
    hwm_rules: tuple[BasinRule, ...] = ()

    #: Default map window for the diagnostic panels (xmin, xmax, ymin, ymax).
    plot_window: tuple[float, float, float, float] | None = None

    #: Named map windows for plots/animations, ``label -> (x0, x1, y0, y1)`` in the
    #: domain CRS; ``None`` means the whole domain. These were a flat module-level dict
    #: in ``animate.py`` shared across domains — which worked only because the keys
    #: happened not to collide, which is luck, not design.
    map_windows: dict[str, tuple[float, float, float, float] | None] = field(
        default_factory=dict
    )

    # ── Water-level boundary support points ──────────────────────────────────
    # hydromt selects the forcing gauges by BUFFERING the model region, so the number
    # of support points is a function of the DOMAIN, not of the forcing file. That makes
    # a single shared buffer silently domain-dependent, and it very nearly bit us:
    # `noaa_sandy_nj.nc` carries THREE gauges, and pushing the domain 0.45 deg south
    # dropped Cape May from 150.7 km to 99.1 km — INSIDE a 100 km buffer by 0.9 km,
    # silently converting a 2-node boundary into a 3-node one. Inserting a support point
    # is not cosmetic: it cost one retired arm +0.18 m of HWM bias.
    #
    # So the buffer is a per-domain fact chosen with MARGIN rather than tuned to a knife
    # edge, and `n_waterlevel_support` is asserted AFTER hydromt has actually selected.
    waterlevel_buffer: int = 100_000
    n_waterlevel_support: int | None = None

    def frozen_mesh_dir(self) -> Path:
        """``data/frozen_mesh_<mesh_key or name>``."""
        return DATA / f"frozen_mesh_{self.mesh_key or self.name}"

    def bbox_ll(self, buffer_deg: float = 0.0) -> tuple[float, float, float, float]:
        """Region bounding box in WGS-84 as ``(west, south, east, north)``.

        The single source of truth for every download/clip extent, so the acquisition
        scripts re-target a new domain for free. The old repo hand-typed a bbox into
        three separate download scripts, each with a comment reading "update this if
        region.geojson changes" — three separate chances to forget.
        """
        return _bbox_ll(self.region, buffer_deg)


@lru_cache(maxsize=8)
def _bbox_ll(region: Path, buffer_deg: float) -> tuple[float, float, float, float]:
    import geopandas as gpd

    w, s, e, n = gpd.read_file(region).to_crs(4326).total_bounds
    b = buffer_deg
    # Cast off numpy scalars: these values get formatted straight into gdal command
    # lines, and np.float64 reprs ("np.float64(-74.3)") poison them.
    return (
        round(float(w) - b, 6),
        round(float(s) - b, 6),
        round(float(e) + b, 6),
        round(float(n) + b, 6),
    )


# ═════════════════════════════════════════════════════════════════════════════
# v1_monmouth — FROZEN. Port-verification fixture only.
# ═════════════════════════════════════════════════════════════════════════════
# Sandy Hook -> Sea Girt, 547,408 faces. The whole 2026-07/08 campaign was measured on
# it. It is registered here for ONE job: scoring the archived
# `faber-waves-premier` run dir, bit for bit, so the validation port is proved against a
# known answer before any new-domain number is believed. See docs/STATUS.md.
#
# ⚠️ WHAT IS DELIBERATELY ABSENT. No `refinement`, no `mask_overrides`, no
# `always_active_boxes_ll`, no `mesh_key` for building. This domain is never rebuilt —
# `frozen=True` makes `build_static` refuse — so carrying its build-time geography would
# be recording, in live code, a recipe that can no longer be executed. Two of its three
# mask overrides were half-planes that the current `MaskOverride` type cannot even
# express. The recipe is in the archive; see ARCHIVE.md.
_SANDY_HOOK = ObsGauge(
    "sandy_hook",
    -74.0091,
    40.4669,
    "surge",
    "gtsm/noaa_sandy_validation.nc",
    "waterlevel",
    8531680,
    survives_crest=False,
    record_ends="2012-10-29 23:00",
    series_source="his",
    note="NOAA CO-OPS. Died on the RISING limb before Sandy's peak (last read ~2.81 m); "
    "48 of 96 hours are NaN, the whole back half 10-30T00:00..10-31T23:00. Score the "
    "PRE-FAILURE peak. ⚠️ You cannot calibrate a boundary against this gap, because the "
    "data you would validate the fill against IS the gap.",
)
_SSS_SEA_BRIGHT = ObsGauge(
    "usgs_stormtide_sea_bright",
    -73.97304,
    40.37222,
    "surge",
    "gtsm/sandy_storm_tide_nj.nc",
    "stormtide_m",
    2258,
    survives_crest=True,
    note="USGS SSS rapid-deployment wave sensor — the only open-coast record that "
    "survived the peak.",
)
_USGS_SEA_BRIGHT = ObsGauge(
    "usgs_tidal_sea_bright",
    -73.97494,
    40.36557,
    "tide",
    "gtsm/usgs_sandy_tidal_nj.nc",
    None,
    1407600,
    survives_crest=False,
    record_ends="2012-10-29 04:00",
    series_source="his",
    note="Shrewsbury R. ⚠️ NUDGED 21 m into the channel — the published coords snap to a "
    "dry bank. This coordinate is the nudged one, and premier.obs_points_ok asserts it. "
    "Record ends ~10-29 04:00, so tidal range/phase only, not the peak.",
)
_USGS_SHARK = ObsGauge(
    "usgs_tidal_shark_river",
    -74.0261,
    40.1856,
    "tide",
    "gtsm/usgs_sandy_tidal_nj.nc",
    None,
    1407770,
    survives_crest=False,
    record_ends="2012-10-29 04:00",
    # Its his obs point snapped to a +1.79 m DRY BANK, so the map at wet channel cells is
    # the only honest modelled series here. Cost: hourly, so coarser lag resolution.
    series_source="map",
    note="Shark R. Record ends ~10-29 04:00 — pre-storm tide only.",
)

# The NNE barrier axis: the ocean/estuary divide is a sloped easting, not a meridian.
_BARRIER = dict(slope_x0=586_000, slope_y0=4_456_000, slope=0.075)

#: ⚠️ CARRIED VERBATIM, ORDER INCLUDED. Every per-basin number in the archive depends on
#: first-match-wins over exactly this sequence. The port-verification gate compares
#: per-basin values, so a reorder here fails it — which is the point.
_V1_BASIN_RULES = (
    BasinRule(
        "shark_river",
        xmax=584_300,
        ymax=4_450_800,
        why="Fed through Shark River Inlet, so these are a CONVEYANCE test, not an "
        "open-coast one. Split out of south_coast after pooling hid the dammed inlet: "
        "the estuary marks were dry and silently dropped, so the basin reported a "
        "near-perfect -0.055 m bias while the river behind it never wetted at all.",
    ),
    BasinRule(
        "south_coast",
        ymax=4_458_000,
        why="Belmar/Avon ocean front — surge delivered directly. ⚠️ 4 of the 38 scored "
        "marks, and they move by 0.0005 m across FOUR different water-level boundaries "
        "including one that adds +0.115 m uniformly to every boundary cell. They are "
        "hydraulically DISCONNECTED from the boundary in the model, contribute a fixed "
        "-0.53 bias / 0.785 RMSE to every arm, and dilute any pooled score.",
    ),
    BasinRule("sandy_hook_bay", ymin=4_474_000, why="Open Sandy Hook / Raritan Bay."),
    BasinRule(
        "atlantic_oceanfront",
        ymin=4_458_000,
        ymax=4_474_000,
        side=+1,
        **_BARRIER,
        why="Seaward of the Sea Bright barrier axis.",
    ),
    BasinRule(
        "shrewsbury_navesink",
        why="Catch-all: the behind-barrier estuaries — the conveyance test.",
    ),
)

V1_MONMOUTH = Domain(
    name="v1_monmouth",
    region=DATA / "region_v1_monmouth.geojson",
    epsg=32618,
    latitude=40.32,
    mask_zmin=-10.0,
    frozen=True,
    obs_gauges=(_SANDY_HOOK, _SSS_SEA_BRIGHT, _USGS_SEA_BRIGHT, _USGS_SHARK),
    open_coast_max_y=4_476_000,
    hwm_rules=_V1_BASIN_RULES,
    plot_window=(578_500, 592_000, 4_462_000, 4_482_000),
    map_windows={
        "domain": None,
        "shrewsbury": (578_500, 592_000, 4_462_000, 4_482_000),
        "sandy_hook": (574_000, 592_000, 4_468_000, 4_486_000),
        "shark": (573_000, 588_000, 4_442_000, 4_456_000),
    },
    # Battery 20.0 km, Atlantic City 92.5 km, Cape May 150.7 km => 2 support points.
    # This reproduces the archived premier's boundary exactly.
    waterlevel_buffer=100_000,
    n_waterlevel_support=2,
)


# ═════════════════════════════════════════════════════════════════════════════
# v1_5_raritan — NOT YET REGISTERED
# ═════════════════════════════════════════════════════════════════════════════
# The domain this repo exists to build: the boundary relocated OUT of Raritan Bay, so
# Lower Bay / Raritan Bay / Sandy Hook Bay are COMPUTED rather than forced. One ocean
# boundary (the Atlantic contour wrapped around Sandy Hook, closing on Rockaway Point)
# plus two short forced cross-sections at Verrazzano Narrows and Arthur Kill. Staten
# Island south shore is a declared land boundary; Jamaica Bay is excluded.
#
# It is deliberately ABSENT rather than stubbed. An unregistered domain fails loudly at
# `active()`; a stubbed one with placeholder geometry would build, run, and produce
# numbers. Two manual facts have to be confirmed before any polygon is drawn — NACCS
# coverage at both cuts, and at least two interior gauges that survive the crest — and
# both are recorded in docs/STATUS.md.

# ── v1.5 interior gauges: the USGS storm-tide (SSS) water-level units ─────────────
# Gate 2. These are what make "Raritan Bay is COMPUTED, not forced" testable at all.
# Series live in data/gtsm/sandy_storm_tide_raritan.nc — a SEPARATE file from
# sandy_storm_tide_nj.nc, which feeds the frozen v1_monmouth port fixture.
#
# 🔴 EVERY ONE IS MOUNTED ABOVE NORMAL WATER and reads its own floor below that; the
# downloader masks those samples to NaN. `above_floor` records how much of each raw
# record survives, because a long record is NOT a usable record here.
#
# ⚠️ COORDINATES ARE NUDGED into water, like `usgs_tidal_sea_bright`. The published
# positions sit on bulkheads with a bed of +0.45..+1.26 m; each is moved 7-34 m to the
# nearest cell at <= -1.0 m. At 25-50 m cell size that is well under one cell, so the
# nudge is insurance, not a fix — if `point_zb` still comes back dry after the mesh is
# built, switch that gauge to `series_source="map"` (see `usgs_tidal_shark_river`).
_SSS_GREAT_KILLS = ObsGauge(
    "sss_great_kills", -74.127762, 40.543441, "surge",
    "gtsm/sandy_storm_tide_raritan.nc", "stormtide_m", 2295,
    survives_crest=True, series_source="his",
    note="SSS-NY-RIC-004WL. ⭐ THE interior holdout: 8.85 km from the nearest arm, so "
    "it scores water the model COMPUTES. Floor 1.97 m NAVD88, 13.7% of the raw record "
    "above it (n=112 six-min points) — peak-worthy, thin for tide. Observed peak "
    "3.99 m. ⚠️ NACCS itself runs 0.35-0.39 m low here; that is a source-product fact "
    "and does NOT enter this model, which computes this water.",
)
_SSS_ARTHUR_KILL = ObsGauge(
    "sss_arthur_kill_mouth", -74.230355, 40.501682, "surge",
    "gtsm/sandy_storm_tide_raritan.nc", "stormtide_m", 2294,
    survives_crest=True, series_source="his",
    note="SSS-NY-RIC-003WL. Best-covered unit of the set — floor 0.54 m, 57.5% above "
    "(n=614), tidal peaks resolved. ⚠️ 1.67 km from the arthur_kill arm, so it is a "
    "FORCING-ADJACENT diagnostic, not an independent holdout. Observed peak 3.81 m.",
)
_SSS_NARROWS_SI = ObsGauge(
    "sss_narrows_si", -74.059676, 40.593873, "surge",
    "gtsm/sandy_storm_tide_raritan.nc", "stormtide_m", 2291,
    survives_crest=True, series_source="his",
    note="SSS-NY-RIC-001WL. ⚠️ 0.87 km from the narrows arm — a forcing-product "
    "diagnostic only, the same standing the Battery has. Floor 1.28 m, 19.8% above.",
)
_SSS_NARROWS_BKLN = ObsGauge(
    "sss_narrows_bkln", -74.011806, 40.580262, "surge",
    "gtsm/sandy_storm_tide_raritan.nc", "stormtide_m", 2270,
    survives_crest=True, series_source="his",
    note="SSS-NY-KIN-001WL. 3.46 km from the narrows arm — marginal. Floor 0.62 m, "
    "48.4% above (n=524), tidal peaks resolved.",
)
# ⚠️ DELIBERATELY ABSENT: SSS-NJ-MID-001WL (2255), S Raritan Bay. The bed under it is
# +1.45 m at the point and +1.78 m median within 150 m — it is sited on ground that is
# ABOVE ordinary water, so only 1.9% of its record clears its 1.75 m floor and its
# 30-min still-water mean averages across a partly-DRY window. It is an HWM with a
# clock, not a gauge. Score it as an HWM (peak >= 3.57 m); a declared-but-meaningless
# gauge looks like coverage.

#: ⚠️ PROVISIONAL — registered 2026-08-13 so `scripts/probe_mesh_size.py` can measure the
#: mesh BEFORE the subgrid is paid for. It is deliberately INCOMPLETE: no `obs_gauges`,
#: no `hwm_rules`, no fingerprint in `premier.EXPECTED`. Those do not affect the face
#: count, and registering them half-done would be worse than leaving them absent —
#: a declared-but-unfed gauge looks like coverage.
#:
#: 🔴 DO NOT RUN AN EXPERIMENT ON THIS YET. `premier` has no fingerprint for it, so the
#: staging guard cannot tell a correct mesh from a drifted one, which is the exact
#: condition that once produced a full sweep of scientifically void results.
V1_5_RARITAN = Domain(
    name="v1_5_raritan",
    region=DATA / "region_v1_5_raritan.geojson",
    refinement=DATA / "quadtree" / "refinement_v1_5_raritan.geojson",
    epsg=32618,
    latitude=40.40,
    mask_zmin=-10.0,
    mesh_key="v1_5_raritan_z10",
    obs_gauges=(_SSS_GREAT_KILLS, _SSS_ARTHUR_KILL, _SSS_NARROWS_SI, _SSS_NARROWS_BKLN,
                _SANDY_HOOK),
    # ── The arm whitelist. A mask==2 cell outside all three is a BUILD ERROR. ──
    # Boxes are padded around each cut so they contain every BC cell it produces, and
    # are DISJOINT — the ocean box stops at easting 593,125 / northing 4,490,496, well
    # south-east of both estuary cuts.
    boundary_arms=(
        BoundaryArm(
            "ocean",
            (580_926, 4_443_729, 593_125, 4_490_496),
            min_cells=200, max_cells=4_000,
            why="The Atlantic side, inherited from v1 unchanged (same southern limit, "
            "lat 40.150) and continued ~3.3 km north to close on Rockaway Point. v1's "
            "own mask==2 already ran at lon -73.936..-73.947 up to its north edge at "
            "40.5202, so this is a CONTINUATION, not new geometry.",
        ),
        BoundaryArm(
            "narrows",
            (577_851, 4_493_651, 583_315, 4_497_041),
            min_cells=20, max_cells=400,
            why="Verrazzano Narrows, ~1.9 km. Carries the Upper Bay + Hudson tidal "
            "prism. ⚠️ Must stay a WATER-LEVEL boundary: a discharge BC over-determines "
            "a tidal strait (its flux is a RESPONSE to the level difference across it) "
            "and destroys the audit, since Q(t) here is the validation.",
        ),
        BoundaryArm(
            "arthur_kill",
            (561_016, 4_482_616, 564_384, 4_485_197),
            min_cells=15, max_cells=300,
            why="The Arthur Kill MOUTH at Perth Amboy / Ward Point, ~1.46 km. Cut here "
            "rather than at the Kill Van Kull junction (2026-08-13): the north cut had "
            "NO NACCS support within 9.56 km, the mouth has a point at 0.21 km. ⚠️ This "
            "walls off the Raritan Bay <-> Newark Bay exchange and forces ~1 km of "
            "Raritan shoreline — a milder instance of the defect v1.5 fixes, so do not "
            "claim the interior is WHOLLY computed.",
        ),
    ),
    # 🔴 THE CLOSURE CORRIDOR. ONE box, ~1.8 km wide, along the whole 11.13 km cut
    # from the isobath's easternmost point to Rockaway Point.
    #
    # WHY A CORRIDOR AND NOT PER-CHANNEL PATCHES. Measured off CUDEM, **28% of the
    # closure is deeper than mask_zmin**, in FIVE separate runs (0.19-1.31 km; the
    # deepest reaches -27.2 m in the Ambrose Channel). `create_active` would deactivate
    # every one, so the closure would be a dashed line rather than a cut, with the gaps
    # sited exactly on the deepest, highest-conveyance ground. An earlier attempt boxed
    # the two biggest runs individually; that leaves three more gaps AND gives each box
    # its own active/inactive rim for `create_boundary` to trace. One continuous
    # corridor yields ONE continuous boundary.
    #
    # `_fill_inactive_holes` cannot do this job: it fills INTERIOR holes, and these sit
    # on the region edge (finding 9 — the topological fill and this box list are used
    # TOGETHER, never one alone).
    #
    # Not a knife edge: the corridor clears the cut by ~500 m on each side, and any
    # half-width from ~200 m to ~1 km closes the same five gaps.
    always_active_boxes_ll=(
        # ⭐ THE BAY. Raritan + Lower + Sandy Hook Bay, active at ANY depth.
        #
        # This is the fix for the tangle, and it is a STATEMENT rather than a patch:
        # "bay water is in the domain, however deep it is." Without it `mask_zmin`
        # deactivates the dredged channels (Ambrose to -27 m, Chapel Hill, Raritan
        # Reach), `_fill_inactive_holes` cannot reach them because they stay CONNECTED
        # to the sea through the bay mouth (finding 9, exactly), and `create_boundary`
        # then rings every channel with imposed ocean level inside the water this
        # domain exists to COMPUTE.
        #
        # ⚠️ Generous on purpose and safe to be so: `include_polygon` only ever ADDS
        # active cells, land above `mask_zmin` is active already, and the region clip
        # runs AFTER `create_active`, so anything outside the ring is removed anyway.
        # The only cells this changes are bay water deeper than -10 m.
        (-74.30, 40.42, -73.93, 40.60),
        # The closure corridor, ~1.8 km wide along the 11.13 km cut. Still needed:
        # 28% of the cut is deeper than mask_zmin and it runs east of the bay box.
        (-73.9522, 40.4450, -73.9304, 40.5547),
    ),
    open_coast_max_y=4_476_000,
    plot_window=(556_000, 596_000, 4_476_000, 4_500_000),
    map_windows={
        "domain": None,
        "raritan": (556_000, 596_000, 4_476_000, 4_500_000),
        "narrows": (574_000, 586_000, 4_490_000, 4_500_000),
        "arthur_kill": (556_000, 570_000, 4_478_000, 4_490_000),
        "sandy_hook": (574_000, 592_000, 4_468_000, 4_486_000),
    },
    waterlevel_buffer=100_000,
    # ⚠️ Declared AFTER the builder reports its screen, never by relaxing this to fit.
    n_waterlevel_support=None,
)


DOMAINS: dict[str, Domain] = {d.name: d for d in (V1_MONMOUTH, V1_5_RARITAN)}

#: Until v1_5_raritan is registered the only domain is the frozen port-verification
#: fixture. That is the safe default: anything that tries to BUILD on it is refused.
DEFAULT_DOMAIN = "v1_monmouth"


def classify_hwm_basin(x, y, dom: "Domain | None" = None):
    """Label each HWM (easting/northing in the domain CRS) by hydraulic basin.

    First matching rule wins; anything unmatched is ``"unassigned"`` rather than being
    silently folded into a real basin, so a mark that falls outside every rule shows up
    as a visible bucket instead of quietly biasing a neighbour.
    """
    import numpy as np

    dom = dom or active()
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    basin = np.full(x.shape, "unassigned", dtype=object)
    todo = np.ones(x.shape, dtype=bool)
    for rule in dom.hwm_rules:
        if not todo.any():
            break
        hit = todo & rule.matches(x, y)
        basin[hit] = rule.name
        todo &= ~hit
    return basin


def hwm_basin_names(dom: "Domain | None" = None) -> tuple[str, ...]:
    dom = dom or active()
    return tuple(r.name for r in dom.hwm_rules)


def map_windows(dom: "Domain | None" = None) -> dict:
    dom = dom or active()
    return dict(dom.map_windows)


def active() -> Domain:
    """The domain this process is working on (``NJ_DOMAIN`` env var)."""
    name = os.environ.get("NJ_DOMAIN", DEFAULT_DOMAIN)
    if name not in DOMAINS:
        raise KeyError(
            f"NJ_DOMAIN={name!r} is not a known domain. Known: {sorted(DOMAINS)}"
        )
    return DOMAINS[name]
