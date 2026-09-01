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

    #: 🔴 ACQUISITION-ONLY: registered so the DOWNLOADERS can resolve a bbox, and for
    #: nothing else. There is no polygon, no mesh and no fingerprint yet.
    #:
    #: Every acquisition script resolves its extent from ``active().region``'s bbox, so a
    #: domain has to exist before its data can be pulled — but the registry's guards
    #: rightly demand a fingerprint (needs a mesh) and real basin rules (needs a polygon),
    #: which is the polygon-first order. This flag is the DELIBERATE, NARROW exemption:
    #: those guards skip an acquisition-only domain, and ``_check_acquisition_only``
    #: replaces them with harder ones — no ``mesh_key``, no arms, no boundary arms, no
    #: HWM rules, no declared support count, and ``frozen`` off.
    #:
    #: ⚠️ It is NOT a placeholder fingerprint. Inventing one would make
    #: ``assert_sealed_domain`` pass on a domain that does not exist — the "success
    #: message over a no-op" this project keeps paying for. Anything that tries to BUILD,
    #: STAGE, PROBE or FREEZE an acquisition-only domain must refuse; ``build_static``
    #: does, and so does ``premier``.
    #:
    #: Clearing this flag is the moment the real polygon lands: swap ``region`` to the
    #: drawn file, drop the flag, and every skipped guard comes back on.
    acquisition_only: bool = False
    #: The polygon is DRAWN and gated but no mesh is frozen yet: the state between
    #: ``acquisition_only`` and sealed. Everything that needs a fingerprint, basin rules
    #: or a support count skips it — those are asserted on the real mesh at freeze —
    #: while ``assert_buildable`` lets it through, which is the point. Set 2026-08-24 on
    #: v3 the moment ``region_v3_EDITED_inland`` landed; cleared at freeze.
    building: bool = False

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

    #: (name, (lon_min, lat_min, lon_max, lat_max), min_z, why) — ground the merged bed
    #: MUST report as dry land, at or above ``min_z`` metres NAVD88.
    #:
    #: 🔴 THIS IS A POSITIVE CHECK, AND THAT IS THE ENTIRE POINT. The existing bed
    #: invariant asks "is there data here" (invariant 6, NoData under an active cell) and
    #: is therefore STRUCTURALLY BLIND to the failure that actually happened: on
    #: 2026-08-14 `cudem_nj` was found to be missing the Ward Point headland, truncating
    #: New York State at lat 40.49982 and backfilling ~230 m of it as -3 to -5.5 m of bay,
    #: while Conference House Park — dry parkland — fell past every tier to 50 m GMRT and
    #: read -0.06 m. Nothing was NoData. Nothing fired. It was caught by eye, on a figure.
    #:
    #: A tier that is deleted, mis-ordered, mis-clipped, or that silently reverts to a
    #: coarse fallback will fail THIS check loudly, because it asserts what the ground IS
    #: rather than merely that something was returned for it.
    #:
    #: ⚠️ Draw each box TIGHT and on unambiguously dry ground — the check is "every face
    #: in the box", so a box that clips a shoreline will fail on real water.
    dry_land_boxes_ll: tuple[tuple[str, tuple[float, float, float, float], float, str], ...] = ()

    #: Rectangles (projected CRS) in which a water-level BC is a build-time error.
    no_waterlevel_boxes: tuple[NoWaterLevelBox, ...] = ()

    #: Catalog key for the river-discharge GeoDataset. A DOMAIN fact, not a global one:
    #: which rivers enter is decided by where the boundary is drawn. v1_5_raritan adds
    #: the Raritan (110.4 m3/s peak, the largest inflow anywhere in either domain) and
    #: Lawrence Brook, which v1_monmouth's footprint does not contain.
    #: ⚠️ v1_monmouth must keep the 6-point archived file — the port fixture is pinned
    #: to it, and `data/discharge` is a read-only symlink into the frozen archive.
    discharge_geodataset: str = "usgs_sandy_discharge"
    #: Per-domain data keys (2026-08-24). Which catalog entries a build reads is a
    #: consequence of where the ring is, exactly like ``discharge_geodataset``: the
    #: archived ``*_nj`` products stop at v2's southern limit and a v3 build that
    #: silently used them would have NoData rain, CN and bed over the whole south.
    #: ``None`` for ``elevation_list`` means ``config.DEFAULT_ELEVATION_LIST``.
    elevation_list: tuple[dict, ...] | None = None
    #: What the QUADTREE REFINEMENT gates zmin/zmax against AND what the FACE elevation
    #: (``z``, the mask's input and half the fingerprint) is merged from. ``None`` = the
    #: elevation list itself (v1/v1.5/v2 behaviour). v3 sets a single pre-merged 25 m
    #: raster: hydromt's block loop (``compute_quadtree``, nrmax=2000 cells) makes ONE
    #: block of the whole 130 x 200 km bbox at level 0 and ``merge`` clip+LOADS every
    #: native tier for it — 164 GB on v3, twice, 2026-08-24. The finest face is 25 m, so
    #: a 25 m average bed is an honest face elevation. ⚠️ The SUBGRID must still sample
    #: the native tiers; its memory is handled separately (see STATUS).
    coarse_elevation_list: tuple[dict, ...] | None = None
    precip_dataset: str = "aorc_sandy_nj"
    cn_dataset: str = "cn_nj"
    cora_waves: Path = DATA / "waves" / "cora_waves_nj.nc"

    #: The high-water-mark set this domain is scored against. A DOMAIN fact for the same
    #: reason `discharge_geodataset` is: `download_sandy_hwms.py` selects marks by the
    #: ACTIVE region's bbox, so a bigger domain is entitled to more marks.
    #: 🔴 `v1_monmouth` must keep the archived file. `premier`'s port fixture pins
    #: `hwm_n_scored=38` and the per-basin split, and finding 6 says a changed scored-mark
    #: count invalidates the comparison outright. `data/validation` is a read-only symlink
    #: into the frozen archive, which enforces that on disk.
    hwm_geojson: Path = DATA / "validation" / "sandy_hwms.geojson"

    #: The FEMA MOTF extent raster this domain is scored against — a DOMAIN fact for
    #: the same reason ``hwm_geojson`` is: ``download_sandy_motf_extent.py`` renders the
    #: ACTIVE region's bbox, so a bigger domain needs its own, bigger sheet. Found the
    #: hard way (2026-08-20): the archived raster was rendered on the v1_monmouth bbox
    #: and stops at lat 40.5283, so v1.5's northern ~9 km — the Narrows, the upper
    #: Staten Island shore — was silently absent from every CSI.
    #: 🔴 ``v1_monmouth`` must keep the archived file — the port fixture pins
    #: ``motf_csi=0.637834`` pre-screen; ``data/validation`` is the read-only archive.
    motf_tif: Path = DATA / "validation" / "sandy_motf_extent.tif"

    #: (name, (lon_min, lat_min, lon_max, lat_max), why) — ground EXCLUDED from the MOTF
    #: comparison footprint because the MOTF sheet is known-invalid there, not because
    #: the model is. The sheet is an NJ-statewide render whose pixels are only {0, 1} —
    #: nodata never occurs — so New York land it does not cover reads as CONFIDENTLY DRY
    #: rather than as missing, and every model-wet pixel on Staten Island books a false
    #: alarm the sheet cannot adjudicate. Coordinate boxes by convention (CLAUDE.md §6).
    #: ``motf_km2_excluded_boxes`` reports what the screen removed — quote it beside CSI.
    motf_exclude_boxes_ll: tuple[tuple[str, tuple[float, float, float, float], str], ...] = ()

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

#: v1.5's basins. ⚠️ NOT a superset of `_V1_BASIN_RULES` and deliberately so.
#:
#: 🔴 v1's rule 3 is ``BasinRule("sandy_hook_bay", ymin=4_474_000)`` with NO western
#: bound, because on v1's footprint there was nothing west of Sandy Hook Bay to confuse
#: it with. On v1.5 that same rule swallows the ENTIRE Raritan Bay — the water this
#: domain exists to test — into a basin named after a different one. Carrying the v1
#: tuple over unchanged would have produced per-basin numbers that looked fine and
#: answered nothing. (Same failure mode as a refinement recipe: a gate written for one
#: basin, applied to another, silently does the wrong thing.)
#:
#: So `sandy_hook_bay` is bounded here, and the water it used to absorb becomes
#: `raritan_bay`. ⚠️ CONSEQUENCE: `sandy_hook_bay` does NOT mean the same thing on the
#: two domains, so its per-basin statistics are NOT comparable across them. Compare arms
#: within a domain; that is the only comparison this project makes anyway.
_V1_5_BASIN_RULES = (
    # ── carried VERBATIM from v1, order preserved ────────────────────────────
    BasinRule(
        "shark_river", xmax=584_300, ymax=4_450_800,
        why="As v1: fed through Shark River Inlet, so a CONVEYANCE test.",
    ),
    BasinRule("south_coast", ymax=4_458_000, why="As v1: Belmar/Avon ocean front."),
    # ── the northern split, NEW in v1.5 ──────────────────────────────────────
    BasinRule(
        "sandy_hook_bay", ymin=4_474_000, ymax=4_486_000, xmin=574_000,
        why="Sandy Hook Bay PROPER. Bounded west at easting 574,000 and north at "
        "4,486,000, unlike v1's unbounded version — see the note above this tuple.",
    ),
    BasinRule(
        "raritan_bay", ymin=4_474_000, ymax=4_486_000, xmax=574_000,
        why="⭐ THE TARGET. Raritan Bay and its NJ shore round to the Arthur Kill "
        "mouth — the water the boundary relocation exists to COMPUTE rather than "
        "force. On v1 these marks fell inside `sandy_hook_bay`.",
    ),
    BasinRule(
        "lower_bay_si_shore", ymin=4_486_000,
        why="The Staten Island frontage and the Narrows approach. Entirely NEW water: "
        "every mark here is outside the v1_monmouth footprint, so this basin exists "
        "only because the domain moved.",
    ),
    # ── back to v1's ordering for the southern estuaries ─────────────────────
    BasinRule(
        "atlantic_oceanfront", ymin=4_458_000, ymax=4_474_000, side=+1, **_BARRIER,
        why="As v1: seaward of the Sea Bright barrier axis.",
    ),
    BasinRule(
        "shrewsbury_navesink", ymin=4_458_000, ymax=4_474_000,
        why="As v1's catch-all, but BOUNDED: on v1 this was the unconstrained last "
        "rule, which on v1.5 would collect every northern mark the rules above miss.",
    ),
    BasinRule(
        "unclassified",
        why="🔴 Must stay EMPTY. The rules above are bounded, so this is the alarm for "
        "a mark that fell through every one of them — which means a threshold is wrong, "
        "not that a new basin was discovered.",
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
# v1_5_raritan — REGISTERED AND FROZEN (2026-08-14)
# ═════════════════════════════════════════════════════════════════════════════
# The domain this repo exists to build: the boundary relocated OUT of Raritan Bay, so
# Lower Bay / Raritan Bay / Sandy Hook Bay are COMPUTED rather than forced. One ocean
# boundary (the Atlantic contour wrapped around Sandy Hook, closing on Rockaway Point)
# plus two short forced cross-sections at Verrazzano Narrows and Arthur Kill. Staten
# Island south shore is a declared land boundary; Jamaica Bay is excluded.
#
# Frozen mesh: data/frozen_mesh_v1_5_raritan_z10 — fingerprint faces=696230
# boundary_edges=1652 sha(z,mask)=2a23667dd16e449c, pinned in premier.EXPECTED.
# Both pre-polygon gates (NACCS coverage at the cuts; interior gauges surviving the
# crest) passed 2026-08-13 — the record is in docs/STATUS.md.

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

# ── The v1 southern estuary gauges, RE-NUDGED for v1.5's mesh ────────────────────────
# 🔴 THE v1 COORDINATES DO NOT TRANSFER, AND THE FAILURE IS SILENT.
# v1.5 refines the quadtree differently in the southern estuaries, so all three of v1's
# points land on DRY BANKS here — measured on the sealed template, bed +3.48 / +4.42 /
# +3.57 m. That is precisely the scar `premier.obs_points_ok` was generalised for: a bank
# cell only wets during the storm, so every pre-storm tide and phase metric returns NaN
# without ever raising. `usgs_tidal_sea_bright` carries a 21 m nudge that was tuned on v1's
# faces and is worth nothing on these.
#
# So each gauge gets its OWN v1.5 entry, nudged to the nearest `mask==1` face with bed
# < −1.0 m. They cannot reuse the v1 constants: those coordinates are asserted against
# `v1_monmouth`'s own sfincs.obs by `obs_points_ok`, and the port fixture is pinned to them.
#
# | gauge | nudge | v1.5 bed | v1 bed |
# |---|---|---|---|
# | usgs_tidal_sea_bright | 24.8 m | −4.20 | −4.33 (21 m) |
# | usgs_tidal_shark_river | 35.0 m | −2.22 | map-sourced on v1 |
# | usgs_stormtide_sea_bright | 105.9 m | −1.19 | published coords |
#
# ⚠️ The open-coast SSS nudge is the big one — 105.9 m, because the nearest wet face is
# offshore of the beach it sits on. Its published cell is +3.48 m and would wet by only
# ~0.9 m at Sandy's observed 4.4 m peak there; a barely-wet cell is a bad place to read a
# modelled crest. 106 m of open coast is flat compared with that, but it IS a nudge across
# the surf zone and the comparison should be read as "the model's nearshore level", not
# "the model at the sensor".
_V15_SSS_SEA_BRIGHT = ObsGauge(
    "usgs_stormtide_sea_bright",
    -73.97200,
    40.37275,
    "surge",
    "gtsm/sandy_storm_tide_nj.nc",
    "stormtide_m",
    2258,
    survives_crest=True,
    series_source="his",
    note="USGS SSS rapid-deployment sensor, Sea Bright — the only open-coast record that "
    "survived the peak. ⚠️ NUDGED 105.9 m offshore onto a −1.19 m face; the published "
    "point is a +3.48 m bank on this mesh. Read as nearshore level, not at-sensor.",
)
_V15_USGS_SEA_BRIGHT = ObsGauge(
    "usgs_tidal_sea_bright",
    -73.97523,
    40.36554,
    "tide",
    "gtsm/usgs_sandy_tidal_nj.nc",
    None,
    1407600,
    survives_crest=False,
    record_ends="2012-10-29 04:00",
    series_source="his",
    note="Shrewsbury R. ⚠️ NUDGED 24.8 m into the channel (bed −4.20 m) — this is v1.5's "
    "OWN nudge, not v1's 21 m one, which lands on a +4.42 m bank here. Record ends "
    "~10-29 04:00, so tidal range/phase only, not the peak.",
)
_V15_USGS_SHARK = ObsGauge(
    "usgs_tidal_shark_river",
    -74.02597,
    40.18530,
    "tide",
    "gtsm/usgs_sandy_tidal_nj.nc",
    None,
    1407770,
    survives_crest=False,
    record_ends="2012-10-29 04:00",
    # v1 had to fall back to `series_source="map"` here because its obs point snapped to a
    # +1.79 m bank. v1.5 has a wet face 35 m away, so this one can be scored off `his` at
    # 10-min instead of hourly — strictly better resolution for tidal phase.
    series_source="his",
    note="Shark R. ⚠️ NUDGED 35.0 m onto a −2.22 m face. Record ends ~10-29 04:00 — "
    "pre-storm tide only.",
)

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
    # 🔴 THE HAND-DRAWN ring, not a generated one. Drawn in QGIS over Esri imagery +
    # CUDEM, 2026-08-13; 40 vertices, 2,281 km². `scripts/validate_region_v1_5.py` is
    # its gate and has NO write path — the generator that used to own this filename was
    # retired precisely because it would have overwritten the only copy of the geometry.
    region=DATA / "region_v1_5_raritan_edited.geojson",
    refinement=DATA / "quadtree" / "refinement_v1_5_raritan.geojson",
    epsg=32618,
    latitude=40.40,
    mask_zmin=-10.0,
    mesh_key="v1_5_raritan_z10",
    obs_gauges=(_SSS_GREAT_KILLS, _SSS_ARTHUR_KILL, _SSS_NARROWS_SI, _SSS_NARROWS_BKLN,
                _SANDY_HOOK,
                _V15_SSS_SEA_BRIGHT, _V15_USGS_SEA_BRIGHT, _V15_USGS_SHARK),
    # ── The arm whitelist. A mask==2 cell outside all three is a BUILD ERROR. ──
    # Boxes are padded around each cut so they contain every BC cell it produces, and
    # are DISJOINT — the ocean box stops at easting 593,125 / northing 4,490,496, well
    # south-east of both estuary cuts.
    boundary_arms=(
        BoundaryArm(
            "ocean",
            (580_926, 4_443_729, 593_125, 4_490_496),
            # AS BUILT 2026-08-14 on probe_mesh_v1_5_fix3: 1,187 cells, in 2 runs
            # (1,170 + 17) separated by the Breezy Point spit — see STATUS 3c/3d, that
            # split is real sand and is NOT a defect.
            min_cells=1_000, max_cells=1_400,
            why="The Atlantic side, inherited from v1 unchanged (same southern limit, "
            "lat 40.150) and continued ~3.3 km north to close on Rockaway Point. v1's "
            "own mask==2 already ran at lon -73.936..-73.947 up to its north edge at "
            "40.5202, so this is a CONTINUATION, not new geometry.",
        ),
        BoundaryArm(
            "narrows",
            (577_851, 4_493_651, 583_315, 4_497_041),
            min_cells=45, max_cells=85,  # as built 2026-08-14: 61 cells, 1 run
            why="Verrazzano Narrows, ~1.9 km. Carries the Upper Bay + Hudson tidal "
            "prism. ⚠️ Must stay a WATER-LEVEL boundary: a discharge BC over-determines "
            "a tidal strait (its flux is a RESPONSE to the level difference across it) "
            "and destroys the audit, since Q(t) here is the validation.",
        ),
        BoundaryArm(
            "arthur_kill",
            (561_016, 4_482_616, 564_384, 4_485_197),
            # 🔴 RE-BRACKETED 2026-08-14, and the old [15..300] is why this matters.
            # Until the CoNED tier landed this arm was 59 cells in TWO runs — 24 real
            # plus 35 spawned by cudem_nj's phantom water at Ward Point — and 59 sailed
            # through [15..300] without comment. A bracket wide enough to admit the
            # defect it exists to catch is not a bracket. As built: 24 cells, 1 run.
            min_cells=16, max_cells=40,
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
        # 🔴 NORTH EDGE IS 40.6125, NOT 40.60, AND THAT NUMBER IS LOad-BEARING.
        # At 40.60 this box's own north edge cut straight across the Verrazzano Narrows
        # approach. The Narrows is ~30 m deep, so above the box `create_active(zmin=-10)`
        # deactivated the channel, and `create_boundary` traced the BOX EDGE instead of
        # the drawn cut: the narrows arm came out as an L — a 3 km limb sitting along
        # lat 40.6005 plus a stub of the real cut — 209 cells instead of a clean line,
        # ~670 m south of the Verrazzano Bridge the cut was drawn on.
        # The ring's northernmost vertex is lat 40.61090, so 40.6125 clears it; the
        # region clip runs AFTER create_active, so extending the box cannot pull in
        # anything outside the drawn ring.
        # West edge -74.32 rather than -74.30: PRECAUTIONARY SLACK, not a fix.
        # ⚠️ Measured 2026-08-14 — moving it changed the mask by exactly ZERO cells, and
        # the reasoning that motivated it was wrong. The old -74.30 edge sat 34 m east of
        # the ring's westernmost vertex (-74.30043), so it did clip a sliver of the
        # Raritan crossing, but the bed there is ~-2 m — above `mask_zmin` — so nothing
        # was being deactivated. A probe at -74.303 reading mask==0 was the REGION CLIP
        # (the ring ends at -74.3004), not this box.
        # Kept anyway because it is free and it is insurance: if a future carve deepened
        # that reach past -10 m, the -74.30 edge WOULD deactivate the channel a few tens
        # of metres from where the Raritan discharge is imposed. Safe for the same reason
        # the north edge is — include_polygon only ADDS active cells, and the region clip
        # runs afterwards, so nothing outside the drawn ring can survive it.
        (-74.32, 40.42, -73.93, 40.6125),
        # The closure corridor, ~1.8 km wide along the 11.13 km cut. Still needed:
        # 28% of the cut is deeper than mask_zmin and it runs east of the bay box.
        (-73.9522, 40.4450, -73.9304, 40.5547),
    ),
    # 🔴 THE GROUND CUDEM LOST. Both boxes sit on the Tottenville / Ward Point headland,
    # which `cudem_nj` truncates at lat 40.49982 and backfills as -3 to -5.5 m of bay, and
    # which no other tier covers: `nj_10ft_dem` is NEW-JERSEY-ONLY and this is New York, so
    # without `coned_sw_raritan` the bed here falls to 50 m GMRT and reads ~0.
    #
    # These assert what the ground IS. Delete the CoNED tier, order it below `cudem_nj`,
    # mis-clip its box, or let a future stack edit shadow it, and the build stops here
    # instead of quietly flooding a public park and splitting the arthur_kill arm in two.
    #
    # Thresholds are well below the measured bed (CoNED reads +7.6 m minimum in the park
    # box, +1.6 m in the headland box) so these fail on a REGRESSION, not on resampling.
    dry_land_boxes_ll=(
        (
            "conference_house_park",
            (-74.2528, 40.5012, -74.2502, 40.5026),
            2.0,
            "Conference House Park, Tottenville — dry NYC parkland that the merged bed "
            "reported as -0.06 m (50 m GMRT) before the CoNED tier existed.",
        ),
        (
            "ward_point_headland",
            (-74.2492, 40.4983, -74.2465, 40.4996),
            0.5,
            "The Ward Point headland itself — the southernmost land in New York State, "
            "~230 m of which cudem_nj omits. The drawn ring runs along its shore, and "
            "when this reads as water the arthur_kill arm breaks into two runs.",
        ),
    ),
    # 🔴 The Raritan River cut is a DISCHARGE boundary, so a water-level BC across it is a
    # build-time error. An imposed ocean level across a tidal river PUMPS it — the mirror
    # of the free-outflow face that drained the Navesink — and it would also fight the
    # inflow. Deliberately NOT a `boundary_arms` entry: arms are where mask==2 is allowed,
    # and here it never is. Both mechanisms are wanted (the arm whitelist demotes; this is
    # the alarm that says the demotion still happened).
    #
    # ⚠️ The cut is at lon -74.2997, lat 40.5065..40.5115 — inside the segment NORTH of the
    # 1.79 km one that was long recorded as "the Raritan cut" and is dry ground end to end.
    no_waterlevel_boxes=(
        NoWaterLevelBox(
            "raritan_cut",
            (558_700, 4_484_000, 560_500, 4_485_000),
            why="The tidal Raritan River at the domain's west limit takes a river "
            "discharge, never an imposed level. Stops ~300 m clear of the arthur_kill "
            "arm box, which starts at easting 561,016.",
        ),
    ),
    discharge_geodataset="usgs_sandy_discharge_v1_5",
    hwm_geojson=DATA / "validation_v1_5" / "sandy_hwms_v1_5.geojson",
    # Own MOTF render: the archived sheet was rendered on the v1_monmouth bbox and
    # stops at lat 40.5283 — the Narrows and the upper SI shore were silently unscored.
    # Built by `NJ_DOMAIN=v1_5_raritan python scripts/download_sandy_motf_extent.py`.
    motf_tif=DATA / "validation_v1_5" / "sandy_motf_extent_v1_5.tif",
    # The MOTF source layer is NEW JERSEY ONLY and renders NY land as 0 = confidently
    # dry, so every model-wet pixel there booked a false alarm the sheet cannot
    # adjudicate. Boxes validated 2026-08-20 against the nj_10ft_dem footprint (an
    # NJ-only product, so its data extent IS the NJ-land discriminator): 0 NJ pixels
    # inside either box; Ward Point (40.4961) and all SI shore contained; Perth Amboy
    # (west of the Arthur Kill) untouched. 4.50 km² of scored land removed on the
    # archived sheet; the brooklyn_rockaway box only bites on the v1.5 render, which
    # reaches past lat 40.53.
    motf_exclude_boxes_ll=(
        (
            "staten_island",
            (-74.2525, 40.4870, -74.030, 40.6500),
            "NY land east of the Arthur Kill — outside the NJ-only MOTF layer, reads "
            "as fake-dry. West edge splits the Kill: Ward Point (SI, -74.249) in, "
            "Perth Amboy (NJ, -74.256 and west) out.",
        ),
        (
            "brooklyn_rockaway",
            (-74.0300, 40.5300, -73.850, 40.6500),
            "Brooklyn / Rockaway shore — NY land on the v1.5 render north of the "
            "archived sheet's 40.5283 cutoff.",
        ),
    ),
    hwm_rules=_V1_5_BASIN_RULES,
    # 🔴 THIS IS THE COUNT FOR THE **BASE** FORCING (`noaa_sandy_nj`), NOT FOR NACCS.
    # The template is built from BaseConfig, whose water level is the NOAA gauge set, and
    # each arm then swaps in its own source. hydromt picks NOAA gauges by BUFFERING the
    # region, so this is the number that catches an extra gauge silently appearing when
    # the domain is extended — which is exactly what it is for.
    # Measured during the 2026-08-14 template build: `[bnd] 2 water-level support point(s)`.
    #
    # ⚠️ The NACCS arms force from 71 points, and that number belongs on the ARM
    # (`Experiment.n_waterlevel_support`), never here: relaxing this value would disable
    # the guard for every other arm on the domain. It was briefly set to 71 here, and the
    # template build failed loudly rather than quietly forcing from the wrong set — the
    # guard working as designed.
    n_waterlevel_support=2,
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
)


# ═════════════════════════════════════════════════════════════════════════════
# v2_barnegat — FROZEN ARCHIVE FIXTURE, registered 2026-08-20 for SCORING ONLY
# ═════════════════════════════════════════════════════════════════════════════
# The archive's v1-plus-Barnegat-lobe domain (nj_coast_sfincs/nj_sfincs/domain.py:550).
# Its five kept runs (8.79 GB of sfincs_map.nc) had NO metrics.csv anywhere — their
# scores existed only as prose in the archived campaign logs, so trimming the maps
# would have made them unre-scorable forever. This entry exists so the bight scorer
# can bank a CSV first (scripts/score_v2_barnegat.py); the maps are then trimmable.
#
# frozen=True: staged and scored, never built — the frozen mesh was deliberately not
# ported (ARCHIVE.md). Only the fields the SCORER touches are populated; build-time
# fields (mask overrides, always-active boxes, refinement) stay in the archive with
# the mesh they describe. region is a data/ symlink into the read-only archive.
# The archived sandy_hwms.geojson (95 marks) and sandy_motf_extent.tif were both
# built on the V2 bbox (lat 39.69–40.53) — the defaults are exactly right here,
# which is also WHY v1_monmouth could score against them all along.

_BB_MANTOLOKING = ObsGauge(
    "usgs_tidal_bb_mantoloking", -74.0544444, 40.0405556, "surge",
    "gtsm/usgs_sandy_tidal_nj.nc", None, 1408168,
    survives_crest=True,
    note="Barnegat Bay at Mantoloking. 721 pts, complete through the peak. Observed "
    "peak 2.11 m NAVD88 at 2012-10-30 06:18 UTC — 0.52 m HIGHER and ~6 h LATER than "
    "Barnegat Light at the inlet; the pair constrains bay conveyance.",
)
_BB_BARNEGAT_LIGHT = ObsGauge(
    "usgs_tidal_bb_barnegat_light", -74.1105556, 39.7608333, "surge",
    "gtsm/usgs_sandy_tidal_nj.nc", None, 1409125,
    survives_crest=True,
    note="Barnegat Bay at Barnegat Light, just inside the inlet. Observed peak 1.59 m "
    "NAVD88 at 2012-10-30 00:24 UTC. Inside the 6 km buffer to the artificial "
    "Manahawkin south edge, so it is also the check on that boundary.",
)
_SSS_BARNEGAT_INLET = ObsGauge(
    "usgs_stormtide_barnegat_inlet", -74.104167, 39.763611, "surge",
    "gtsm/sandy_storm_tide_nj.nc", "stormtide_m", 2260,
    survives_crest=True,
    note="USGS SSS-NJ-OCE-001WV, in Barnegat Inlet itself. Peak 1.65 m NAVD88 at "
    "2012-10-30 00:00 — corroborates Barnegat Light (1.59 m at 00:24) from ~1 km.",
)

# Sloped divider fitted to the barrier's bay-side shore between Barnegat and
# Manasquan Inlets (x = 576,000 + 0.160*(y - 4,402,000)) — ported verbatim from the
# archive so the basin split reproduces its campaign's.
_S_BARRIER = dict(slope_x0=576_000, slope_y0=4_402_000, slope=0.160)
_V2_SOUTH_RULES = (
    BasinRule("manasquan", xmax=582_600, ymin=4_434_000, ymax=4_443_000,
              why="Manasquan River estuary, behind the inlet — a conveyance basin."),
    BasinRule("barnegat_barrier", ymax=4_444_000, side=+1, **_S_BARRIER,
              why="Ocean-front barrier: Island Beach, Bay Head/Mantoloking and the "
                  "north end of LBI. Includes the Mantoloking breach zone."),
    BasinRule("barnegat_bay", ymax=4_444_000,
              why="The lagoon and its mainland shore — behind-barrier, so the "
                  "conveyance test for Barnegat and Manasquan Inlets."),
)

V2_BARNEGAT = Domain(
    name="v2_barnegat",
    region=DATA / "region_v2_barnegat.geojson",
    epsg=32618,
    latitude=40.11,  # domain mean, (39.70 + 40.52) / 2 — the archive's value
    frozen=True,
    obs_gauges=(_SANDY_HOOK, _SSS_SEA_BRIGHT, _USGS_SEA_BRIGHT, _USGS_SHARK,
                _BB_MANTOLOKING, _BB_BARNEGAT_LIGHT, _SSS_BARNEGAT_INLET),
    open_coast_max_y=4_476_000,
    hwm_rules=_V2_SOUTH_RULES + _V1_BASIN_RULES,
    plot_window=(578_500, 592_000, 4_462_000, 4_482_000),
    # Battery 20.0 km, AC 39.6 km, Cape May 99.1 km — 100 km would admit Cape May by
    # 0.9 km. The archive chose 60 km with ~20 km margin either side; kept verbatim.
    waterlevel_buffer=60_000,
    n_waterlevel_support=2,
)


# ═══════════════════════════════════════════════════════════════════════════════
# v3 — the full Jersey shore, Raritan Bay -> Cape May. BUILDING (polygon drawn, no mesh).
# ═══════════════════════════════════════════════════════════════════════════════
# The ring: `data/region_v3_EDITED_inland.geojson` (user, QGIS, 2026-08-24). v1.5's three
# FORCED cuts verbatim (ocean arm, Narrows, Arthur Kill mouth); the landward edge runs
# through the head of tide of every southern river (Metedeconk, Toms, Wading, Mullica,
# Great Egg, Tuckahoe) so every river crossing is DRY — no water-level or outflow BC on
# any river, discharge sources at the gauges, inside. The Cape May Canal is NOT cut: the
# ring leaves land north of the canal's Delaware Bay mouth (NOAA 8536110 sits on it) and
# a forced wedge in Delaware Bay rounds Cape May Point. Gate: scripts/validate_region_v3.py
# (exit 0, 17 declared reaches, zero river reaches). docs/STATUS.md has the measurements.
#
# ⚠️ `n_waterlevel_support` stays UNSET until hydromt selects on the real mesh: Cape May
# is INSIDE the ring (on the canal mouth), so the base NOAA count should become 3 —
# ASSERT it at the template build, do not declare it. `boundary_arms` come from the
# mesh probe (Step 2 of the build plan); `hwm_rules` from the v3 HWM pull.
#: v3 bed, top tier first (hydromt: earlier wins). Same ORDER as DEFAULT_ELEVATION_LIST
#: with the v3 pulls substituted; the archived carving tiers stay because they are
#: NoData outside their surveyed channels (ehydro_south = Barnegat Inlet + Manasquan +
#: Metedeconk channels, lat 39.66-40.11). ehydro_south_v3 goes on top: it is the only
#: measurement of the bed under the Cape May Canal, which the ring's forcing depends on.
V3_ELEVATION_LIST: tuple[dict, ...] = (
    {"elevation": "ehydro_south_v3"},
    {"elevation": "ehydro_raritan_ak"},
    {"elevation": "ehydro_nj"},
    {"elevation": "ehydro_south"},
    {"elevation": "shrewsbury_ehydro_2015"},
    {"elevation": "usace_nj_2010_v3"},
    {"elevation": "coned_sw_raritan"},
    {"elevation": "cudem_nj_v3"},  # the archive's 1/9" CUDEM, with local overviews
    {"elevation": "nj_10ft_dem_v3", "zmin": 0.001},
    {"elevation": "cudem13_v3"},
    {"elevation": "gmrt_v3"},
)


# ── v3 validation ─────────────────────────────────────────────────────────────
# Wired 2026-08-26 (the freeze). The northern eight are v1.5's VERBATIM (same files,
# same notes); the south is the 2026-08-24 pulls. Names are unique substrings for the
# his matcher. Pre-registration (STATUS): the interior holdouts are Atlantic City and
# the southern USGS/STN gauges; ⚠️ Cape May 8536110 sits ON the wedge forcing line at
# the canal mouth, so it is a FORCING diagnostic like the Battery on v1.5, never a
# holdout. Sluice Creek 1411435 is on the Delaware Bay side outside the ring — not
# listed. STN 2245 / 2261 read 4.47 / 4.45 m at their FIRST sample (STATUS 08-24): not a
# surge shape, not listed; 2248 has 3 h — not listed.
_V3_USGS = "gtsm/usgs_sandy_tidal_v3.nc"
_V3_STN = "gtsm/sandy_storm_tide_south.nc"
_NOAA_ATLANTIC_CITY = ObsGauge(
    "noaa_atlantic_city", -74.4181, 39.3550, "surge",
    "gtsm/noaa_sandy_validation.nc", "waterlevel", 8534720,
    survives_crest=True, series_source="his",
    note="NOAA CO-OPS 8534720, Steel Pier. ⭐ THE southern interior holdout: hourly, "
    "complete, observed peak 1.88 m NAVD88 at 10-30 00:00. Sits ~1.8 km inside the ocean "
    "arm, so it tests the nearshore/setup step the boundary product does not carry.",
)
_NOAA_CAPE_MAY = ObsGauge(
    "noaa_cape_may", -74.9600, 38.9683, "surge",
    "gtsm/noaa_sandy_validation.nc", "waterlevel", 8536110,
    survives_crest=True, series_source="his",
    note="NOAA CO-OPS 8536110, Cape May Harbor / canal mouth. ⚠️ ON THE WEDGE FORCING "
    "LINE — a forcing-product diagnostic (CLAUDE.md §6), NOT a model holdout. Observed "
    "peak 1.75 m at 10-29 13:00 (the Delaware Bay side peaks half a day before the coast).",
)


def _usgs_v3(name, lon, lat, sid, kind="surge", survives=True, record_ends=None, note=""):
    return ObsGauge(name, lon, lat, kind, _V3_USGS, None, sid, survives_crest=survives,
                    record_ends=record_ends, series_source="his", note=note)


_V3_USGS_GAUGES = (
    _usgs_v3("usgs_tidal_mantoloking", -74.0544, 40.0406, 1408168,
             note="01408168 Barnegat Bay at Mantoloking. Complete through the window; "
             "peak 2.11 m at 10-30 06:18 — the bay peaks HOURS after the coast, and the "
             "Mantoloking breach is 1 km away. Barnegat/Manasquan conveyance holdout."),
    _usgs_v3("usgs_tidal_barnegat_light", -74.1106, 39.7608, 1409125,
             note="01409125 Barnegat Bay at Barnegat Light, inside the inlet. Peak 1.59 m "
             "at 10-30 00:24. Complete."),
    _usgs_v3("usgs_tidal_ship_bottom", -74.1858, 39.6542, 1409146,
             note="01409146 East Thorofare at Ship Bottom (LBI bay side). ⚠️ 596 of 1081 "
             "samples and its recorded peak (1.02 m, 10-29 02:54) is the pre-storm tide — "
             "the crest is in a GAP. Score with care; the peak comparison is not valid."),
    _usgs_v3("usgs_tidal_tuckerton", -74.3247, 39.5089, 1409335,
             note="01409335 Little Egg Inlet near Tuckerton. Peak 1.59 m at 10-30 04:00. "
             "841 samples, through the window."),
    _usgs_v3("usgs_tidal_absecon_creek", -74.5000, 39.4231, 1410510,
             note="01410510 Absecon Creek at Absecon — head of the Absecon back bay. Peak "
             "1.87 m at 10-30 04:00 (Absecon src is upstream; check dist_nearest_src_m)."),
    _usgs_v3("usgs_tidal_inside_thorofare", -74.4569, 39.3536, 1410560,
             note="01410560 Inside Thorofare at Atlantic City — the AC back bay, 3.5 km "
             "from the NOAA ocean-side gauge: the ocean-vs-bay pair. Peak 1.71 m at "
             "10-30 04:00."),
    _usgs_v3("usgs_tidal_absecon_channel", -74.4236, 39.3778, 1410600, kind="tide",
             survives=False, record_ends="2012-10-29 03:54",
             note="01410600 Absecon Channel at Atlantic City. DIED 10-29 03:54 on the "
             "rising limb — pre-storm tide only."),
    _usgs_v3("usgs_tidal_ocean_city", -74.5756, 39.2858, 1411320,
             note="01411320 Great Egg Harbor Bay at Ocean City (9th St bridge). Peak "
             "2.21 m at 10-30 00:00 — the highest southern gauge. 601 samples."),
    _usgs_v3("usgs_tidal_sea_isle", -74.6978, 39.1578, 1411350,
             note="01411350 Ludlum Thorofare at Sea Isle City. ⚠️ Recorded peak 1.58 m at "
             "10-29 01:18 is the pre-storm tide; the crest is likely in a gap (841 samples "
             "but check before scoring the peak)."),
    _usgs_v3("usgs_tidal_avalon", -74.7419, 39.1086, 1411355,
             note="01411355 Ingram Thorofare at Avalon. Peak 1.14 m at 10-30 04:00 — LOW "
             "for a back bay at the crest; 601 samples. Read the series before trusting."),
    _usgs_v3("usgs_tidal_stone_harbor", -74.7650, 39.0569, 1411360,
             note="01411360 Great Channel at Stone Harbor. ⚠️ Recorded peak 1.55 m at "
             "10-29 01:12 — pre-storm tide; check for a crest gap."),
    _usgs_v3("usgs_tidal_cape_may_harbor", -74.8889, 38.9483, 1411390,
             record_ends="2012-10-30 03:54",
             note="01411390 Cape May Harbor. Stops 10-30 03:54; peak 1.80 m at 10-29 "
             "12:42 — the Delaware-Bay-timed crest, which it does catch. 2.6 km from the "
             "canal-mouth forcing: half holdout, half forcing check."),
)
_V3_STN_GAUGES = (
    ObsGauge("sss_great_bay", -74.4628, 39.5533, "surge", _V3_STN, "stormtide_m", 2244,
             survives_crest=True, series_source="his",
             note="NJATL00001, Great Bay / lower Mullica. Peak 2.39 m at 10-30 02:00; "
             "467 samples to 10-30 18:30. The Mullica conveyance holdout."),
    ObsGauge("sss_great_egg", -74.6275, 39.2883, "surge", _V3_STN, "stormtide_m", 2246,
             survives_crest=True, series_source="his",
             note="NJCAP00001, Great Egg Harbor Bay. Peak 2.10 m at 10-30 00:36; 638 "
             "samples through 10-31."),
    ObsGauge("sss_cape_may", -74.8656, 38.9364, "surge", _V3_STN, "stormtide_m", 2247,
             survives_crest=True, record_ends="2012-10-30 03:12", series_source="his",
             note="NJCAP00035, Cape May. 140 samples 10-29 .. 10-30 03:12, peak 2.24 m at "
             "10-29 13:48 — catches the Delaware-Bay-timed crest, then dies."),
)

# ── v3 HWM basins. FIRST MATCH WINS; the south is declared FIRST because v2's
# barnegat_* rules and v1's south_coast are open to the south (ymax only) and would
# otherwise swallow the whole shore. Boxes from the 185-mark pull (2026-08-24), read
# against the marks' descriptions/coordinates on 2026-08-26 — a first partition by
# county-scale basin, NOT yet an ocean-front/back-bay split south of LBI (n is small
# there: 5–12 marks per basin). Refine after the first score, never silently.
_LBI_LINE = dict(slope_x0=563_168, slope_y0=4_375_852, slope=0.340)  # Holgate→Barnegat Light
_V3_SOUTH_RULES = (
    BasinRule("delaware_bay_shore", xmax=515_000, ymin=4_318_000, ymax=4_345_000,
              why="Reeds Beach / Villas — the Delaware Bay shore inside the wedge. Water "
              "delivered by the bay, timed half a day before the coast."),
    BasinRule("cape_may", ymax=4_320_000,
              why="Cape May city + Point: ocean-front beach marks and the town behind."),
    BasinRule("cape_may_back_bays", ymin=4_320_000, ymax=4_340_000,
              why="Wildwood / Stone Harbor / Avalon behind Hereford and Townsends inlets — "
              "a conveyance basin on unsurveyed (non-federal) inlets."),
    BasinRule("great_egg", ymin=4_340_000, ymax=4_352_000,
              why="Ocean City / Somers Point / Great Egg Harbor Bay."),
    BasinRule("absecon_atlantic_city", ymin=4_352_000, ymax=4_367_000,
              why="Atlantic City, Ventnor, Margate, Brigantine, Absecon — ocean front and "
              "Absecon back bay together (split later if n allows)."),
    BasinRule("lbi_barrier", ymin=4_367_000, ymax=4_412_000, side=+1, **_LBI_LINE,
              why="Long Beach Island ocean front, Holgate to Barnegat Light: east of the "
              "Holgate→Barnegat Light line."),
    BasinRule("great_bay_mullica", ymin=4_367_000, ymax=4_412_000,
              why="Mainland behind LBI: Tuckerton, Manahawkin, Great Bay, the Mullica up "
              "to Green Bank — fed through Little Egg Inlet, a conveyance test."),
)

V3 = Domain(
    name="v3",
    region=DATA / "region_v3_EDITED_inland.geojson",
    refinement=DATA / "quadtree" / "refinement_v3.geojson",
    # ── Inherited from v1.5 VERBATIM: the northern ring is v1.5's, so its mask facts
    # are v3's. Measured 2026-08-24: without the two always-active boxes the Lower Bay /
    # Raritan Bay channels deeper than mask_zmin sever the whole Raritan lobe from the
    # ocean and `_drop_detached_islands` DROPS it (41k + 20k + 11k cells, bed -12..+30).
    boundary_arms=(
        # v1.5's three arms verbatim (its ocean box ends at its lat-40.150 south limit)…
        *V1_5_RARITAN.boundary_arms,
        # …plus everything south of it: the -10 m isobath to Cape May, the closure west
        # at lat 38.93, and the Delaware Bay wedge round Cape May Point to the canal
        # mouth. One contiguous run with v1.5's ocean arm (the probe counts them as one
        # run of ~6,700 cells across the two boxes). Counts are PROVISIONAL bounds from
        # the first clean probe (2026-08-24); tighten at the freeze.
        BoundaryArm(
            "ocean_south",
            (501_000, 4_298_500, 634_000, 4_443_729),
            min_cells=5_000, max_cells=6_200,  # measured 5,598 on the clean probe
            why="The Jersey shore south of v1.5's limit: isobath, Cape May closure, "
            "Delaware Bay wedge (NOAA 8536110 sits on the wedge at the canal mouth).",
        ),
    ),
    land_boxes=(
        (
            "tuckahoe_head_of_tide",
            (514_700, 4_350_500, 515_150, 4_351_300),
            "The ring crosses the Tuckahoe on dry ground 480 m upstream of the source "
            "at gauge 01411300, and hydromt puts FREE-OUTFLOW cells on that edge at "
            "+1.22..+2.97 m — low enough for injected discharge or a surge that reaches "
            "the head of tide to DRAIN out of the model (the Navesink failure). 13 edge "
            "cells -> inactive = a wall, which is what a head-of-tide crossing is. Every "
            "other river crossing's nearest outflow cell is above +7 m (measured "
            "2026-08-24); the Delaware Bay shore leg north of the canal carries 34 "
            "outflow cells at -0.94..+3 m and is left OPEN on purpose: water reaching "
            "them from inside would be leaving to an unmodelled bay, and a box there "
            "would deactivate Villas.",
        ),
    ),
    always_active_boxes_ll=V1_5_RARITAN.always_active_boxes_ll,
    dry_land_boxes_ll=V1_5_RARITAN.dry_land_boxes_ll,
    no_waterlevel_boxes=V1_5_RARITAN.no_waterlevel_boxes,  # the Raritan River cut
    elevation_list=V3_ELEVATION_LIST,
    coarse_elevation_list=({"elevation": "bed_v3_coarse_25m"},),
    # v1.5's value verbatim: the Raritan / Narrows / Arthur Kill limb is not open coast,
    # so its NACCS support is exempt from the 8 m depth screen. Left unset on 08-24 the
    # screen was applied to ALL 406 candidates and the ocean arm kept 29 points where
    # v1.5 keeps 43, the Narrows 4 vs 13 (found 2026-08-26 on the first v3 boundary
    # build). ⚠️ A northing cannot exempt the Delaware Bay wedge — that is a separate
    # question, see STATUS.
    open_coast_max_y=V1_5_RARITAN.open_coast_max_y,
    precip_dataset="aorc_sandy_v3",
    cn_dataset="cn_v3",
    cora_waves=DATA / "waves_v3" / "cora_waves_v3.nc",
    epsg=32618,
    latitude=39.74,  # (38.855 + 40.62) / 2, the drawn ring's mid-latitude
    # Plot metadata only — no bearing on the mesh or the fingerprint. The whole drawn
    # ring in UTM 18N as the default frame; v1.5's windows verbatim (the northern ring
    # is v1.5's) plus one window per southern back-bay compartment.
    plot_window=(498_000, 623_000, 4_301_000, 4_498_000),
    map_windows={
        **V1_5_RARITAN.map_windows,
        "barnegat": (564_000, 587_000, 4_395_000, 4_435_000),
        "great_bay": (543_000, 564_000, 4_367_000, 4_389_000),
        "absecon": (539_000, 559_000, 4_352_000, 4_367_000),
        "great_egg": (522_000, 541_000, 4_341_000, 4_356_000),
        "cape_may": (498_000, 524_000, 4_303_000, 4_328_000),
    },
    # FROZEN 2026-08-26: data/frozen_mesh_v3 (no mesh_key — one boundary depth so far),
    # fingerprint premier.V3. `building` cleared the same pass.
    # The BASE (NOAA) water-level selection on the template: noaa_sandy_nj holds the
    # Battery, Atlantic City and Cape May, all within the 100 km buffer of the line →
    # 3. Asserted at the template build. The arms override with the NACCS 224.
    n_waterlevel_support=3,
    discharge_geodataset="usgs_sandy_discharge_v3",
    hwm_geojson=DATA / "validation_v3" / "sandy_hwms_v3.geojson",
    obs_gauges=(*V1_5_RARITAN.obs_gauges, _NOAA_ATLANTIC_CITY, _NOAA_CAPE_MAY,
                *_V3_USGS_GAUGES, *_V3_STN_GAUGES),
    # south first (bounded), then v2's Barnegat rules (ymax 4,444,000 → effectively
    # 4,412,000..4,444,000 after the south), then v1.5's northern rules + catch-all.
    hwm_rules=_V3_SOUTH_RULES + _V2_SOUTH_RULES + _V1_5_BASIN_RULES,
    # ⭐ Rendered on the acquisition RECTANGLE on purpose (2026-08-24): on v3 the MOTF
    # extent was a DOMAIN-DESIGN input — it decided how far up the Great Egg / Mullica
    # the ring had to reach — so it covers more ground than the ring. Scoring restricts
    # to the run's own `msk` (validate.simulated_mask), so a superset raster costs
    # nothing there. No re-render needed.
    motf_tif=DATA / "validation_v3" / "sandy_motf_extent_v3.tif",
    # v1.5's two NY-validity boxes VERBATIM (2026-09-01, STATUS 09-01 NEXT #4): the MOTF
    # source layer is NJ-only and renders NY land as confidently dry, and v3 shares
    # v1.5's northern geometry (Narrows + Arthur Kill cuts, ocean arm to Rockaway
    # Point). Quote `motf_km2_excluded_boxes` beside any CSI.
    motf_exclude_boxes_ll=V1_5_RARITAN.motf_exclude_boxes_ll,
)


DOMAINS: dict[str, Domain] = {
    d.name: d for d in (V1_MONMOUTH, V1_5_RARITAN, V2_BARNEGAT, V3)
}


def _check_acquisition_only(dom: "Domain") -> None:
    """An acquisition-only domain must be INERT: extent resolution and nothing else.

    Called at import for every registered domain. The three registry guards that an
    acquisition-only domain skips (fingerprint, per-domain fingerprint resolution, basin
    rules) are replaced by these, which are strictly harder to satisfy by accident.
    """
    if not dom.acquisition_only:
        return
    bad = []
    if dom.mesh_key is not None:
        bad.append("mesh_key is set — an acquisition-only domain has no mesh")
    if dom.frozen:
        bad.append("frozen is set — frozen means staged-and-scored, the opposite")
    if dom.boundary_arms:
        bad.append("boundary_arms are declared — there is no boundary to whitelist")
    if dom.hwm_rules:
        bad.append("hwm_rules are declared — there is nothing to score")
    if dom.n_waterlevel_support is not None:
        bad.append(
            "n_waterlevel_support is declared — it must be asserted against hydromt's "
            "own selection on the real mesh, not guessed from a rectangle"
        )
    if bad:
        raise ValueError(f"domain {dom.name!r} is acquisition_only but: " + "; ".join(bad))


def _check_building(dom: "Domain") -> None:
    """A building domain has a REAL polygon and NO mesh. Both halves are asserted.

    The first half is what separates it from ``acquisition_only`` (a rectangle); the
    second is what separates it from sealed (a fingerprint). A domain that is both
    flags at once is a contradiction.
    """
    if not dom.building:
        return
    bad = []
    if dom.acquisition_only:
        bad.append("acquisition_only is ALSO set — a domain is one state, not two")
    if "PROVISIONAL" in dom.region.name:
        bad.append(f"region is still the provisional rectangle ({dom.region.name})")
    if dom.mesh_key is not None:
        bad.append("mesh_key is set — building means no frozen mesh yet")
    if dom.frozen:
        bad.append("frozen is set — freeze clears `building`, not the other way round")
    if bad:
        raise ValueError(f"domain {dom.name!r} is building but: " + "; ".join(bad))


for _d in DOMAINS.values():
    _check_acquisition_only(_d)
    _check_building(_d)


#: Domains whose elevation/precip/etc. tiers live in the READ-ONLY archive
#: (``data/elevation`` and friends are symlinks into ``~/nj_coast_sfincs``, mode
#: ``dr-xr-xr-x``). A puller must never target these: the freeze is what keeps their
#: fingerprints reproducible, and on disk it simply returns EPERM.
ARCHIVED_TIER_DOMAINS = ("v1_monmouth", "v1_5_raritan", "v2_barnegat")


def acquisition_dir(kind: str, dom: "Domain | None" = None) -> Path:
    """``data/<kind>_<domain>`` for a domain being assembled. Refuses the built ones.

    Every acquisition script used to write a FIXED path under ``data/<kind>/`` — which
    is a symlink into the frozen archive, so all of them failed EPERM the moment a new
    domain needed data. This is the one place that decides where a new domain's pulls
    land, so a sixth puller cannot quietly reintroduce the fixed path.

    ⚠️ Returns the directory only; it is NOT created here. The caller creates it when it
    is about to write, so a script that dies in its argument parsing leaves no empty
    directory behind to look like a completed pull.
    """
    dom = dom or active()
    if dom.frozen or dom.name in ARCHIVED_TIER_DOMAINS:
        raise SystemExit(
            f"refusing to acquire {kind!r} for domain {dom.name!r}: its tiers are the "
            f"archived, read-only data/{kind}/. Run under the NEW domain being "
            "assembled (e.g. NJ_DOMAIN=v3)."
        )
    return DATA / f"{kind}_{dom.name}"


def assert_buildable(dom: "Domain | None" = None) -> "Domain":
    """Refuse to build/stage/probe/freeze an acquisition-only domain.

    The failure this prevents is not subtle but it IS silent: a rectangle resolves a
    bbox perfectly well, so a build launched on one produces a plausible mesh over open
    ocean and inland NJ, and nothing in the numbers says so.
    """
    dom = dom or active()
    if dom.acquisition_only:
        raise RuntimeError(
            f"domain {dom.name!r} is acquisition_only: its region is a PROVISIONAL "
            f"bbox rectangle ({dom.region.name}), not a modelling polygon. It may "
            "resolve a download extent and nothing else. Draw the polygon, point "
            "`region` at it and clear `acquisition_only` first."
        )
    return dom

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
