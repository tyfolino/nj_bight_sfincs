"""The experiment library, KEYED BY DOMAIN.

WHY THIS IS NOT ONE FLAT DICT
-----------------------------
It used to be. By the end of the previous repo ``EXPERIMENTS`` held ~31 arms in a single
namespace spanning two domains, and ``--experiments all`` meant "every arm ever defined,
whichever domain you happen to be on". On a fresh domain that is not a sweep, it is an
attempt to stage thirty configurations whose forcing files, support-point counts and
templates belong to somewhere else — and the ones that happen to be staged-compatible
would run and write plausible rows.

An arm is a configuration ON A DOMAIN. So the registry says so:
``EXPERIMENTS_BY_DOMAIN[domain][arm]``, and ``experiments()`` returns only the arms
defined for the active one. An arm that has not been thought about for this domain simply
does not exist here, which is the correct answer.

The second thing that changes: **retired arms are not kept.** The old registry carried
every closed question as a live entry with a ⛔ prefix and several hundred words of
retraction, because deleting them would have lost the reasoning. That reasoning belongs in
``docs/FINDINGS.md`` and in git history, not in a dict the sweep driver iterates.

NAMING (see CLAUDE.md §Conventions)
-----------------------------------
The premier plus ``wave-`` / ``tide-`` / ``solver-`` / ``mask-`` / ``bed-`` deltas; a union
is its parents joined by ``+`` in ALPHABETICAL order, so ``tide-*`` precedes ``wave-*``.
A ``BRACKET+`` prefix marks a deliberately inadmissible bound.
"""

from __future__ import annotations

from dataclasses import replace

from .config import DATA, Experiment, WaveConfig
from .domain import active

# ── v1_5_raritan ─────────────────────────────────────────────────────────────
# The four arms this repo is being built to run. Seeded now so the shape of the campaign
# is on the record before the domain exists; the domain itself is registered in domain.py
# once its two viability gates pass (docs/STATUS.md).
#
# ⚠️ THE PREMIER'S CASE IS STRUCTURAL, NOT MARGINAL. State it that way everywhere. The
# measured waves-on comparison that motivated relocating the boundary does NOT separate
# the two candidates: ΔRMSE −0.042 m, 95% CI [−0.238, +0.137], P = 0.706 on 38 marks.
# NACCS wins every point estimate and is not a demonstrated win. What justifies v1.5 is
# that a boundary running through the middle of Raritan Bay, forced by a linear
# interpolation between two points OUTSIDE it, structurally cannot reproduce an interior
# tidal maximum that NOAA harmonics say is real (0.732–0.761 m, exceeding BOTH anchors).
# Forcing that basin harder closes the deficit and then overshoots, which is what
# over-forcing looks like when the real problem is being forced at all.
_CORA = DATA / "waves" / "cora_waves_nj.nc"

_PREMIER_WAVES = WaveConfig(
    use_waves=True,
    wave_wind=True,
    wave_igwaves=False,
    tune_physics=True,
    wave_point_dataset=_CORA,
)

_V1_5_RARITAN: dict[str, Experiment] = {
    "naccs-premier": Experiment(
        "naccs-premier",
        _PREMIER_WAVES,
        "THE PREMIER. NACCS/CHS ADCIRC storm tide on the relocated boundary — one ocean "
        "arm plus the Verrazzano Narrows and Arthur Kill cross-sections — with CORA "
        "per-support-point waves. Lower Bay, Raritan Bay and Sandy Hook Bay are COMPUTED. "
        "Since 2026-08-21 the config includes the USACE Keansburg protection line "
        "(sfincs.weir, staged in the TEMPLATE so every arm inherits it — FINDINGS §38; "
        "user decision). "
        "The auditable claim is the flux cross-sections: Q(t) through the Narrows carries "
        "the Upper Bay + Hudson tidal prism, which is comparable against literature. "
        "Without that the relocated boundary is asserted, not measured.",
        waterlevel_geodataset="naccs_sandy_v1_5_raritan",
        # Measured on the FROZEN mesh 2026-08-14: 532 NACCS save points -> 139
        # within 2 km of a mask==2 cell -> 71 after the dry (-29) and open-coast
        # depth (-39) screens. Per arm: ocean 43, narrows 13, arthur_kill 15 —
        # no arm empty, which was gate 1. Declared on the ARM, never by relaxing
        # Domain.n_waterlevel_support (which guards the base NOAA selection).
        n_waterlevel_support=71,
    ),
    "naccs-nowaves": Experiment(
        "naccs-nowaves",
        WaveConfig(use_waves=False),
        "The premier boundary with SnapWave OFF. SnapWave is 90–95% of runtime, so this "
        "is the cheap arm for anything about LEVELS and PHASE. "
        "⚠️ Its CSI / POD / FAR are kept and flagged extent_admissible=False: SnapWave "
        "is worth ΔCSI 0.018 here, against ΔCSI 0.011 between the waves-on arms, so "
        "do not RANK it against them. FINDINGS §4.",
        waterlevel_geodataset="naccs_sandy_v1_5_raritan",
        # Measured on the FROZEN mesh 2026-08-14: 532 NACCS save points -> 139
        # within 2 km of a mask==2 cell -> 71 after the dry (-29) and open-coast
        # depth (-39) screens. Per arm: ocean 43, narrows 13, arthur_kill 15 —
        # no arm empty, which was gate 1. Declared on the ARM, never by relaxing
        # Domain.n_waterlevel_support (which guards the base NOAA selection).
        n_waterlevel_support=71,
    ),
    # "noaa-2node" — RETIRED 2026-08-20 (user decision: NACCS forcing is adopted going
    # forward). The 2-node Battery↔Atlantic City interpolant existed only to show what
    # relocation + dense forcing bought, and that result is banked: final scoring
    # 2026-08-20 in experiments/v1_5_raritan/metrics.csv (HWM RMSE 0.474 vs premier
    # 0.402; paired Δ −0.0717, CI [−0.161, −0.013], P 0.994 — STATUS 2026-08-17).
    # The run dir and its scores are KEPT; only the registry entry is gone, so no
    # future sweep can stage it. Re-instate the entry if it ever needs a rescore.
    "naccs-premier-z15": Experiment(
        "naccs-premier-z15",
        _PREMIER_WAVES,
        "The premier at a −15 m boundary instead of −10 m. ⚠️ THIS IS A DIFFERENT DOMAIN, "
        "not a knob: `mask_zmin` is half of sha(z, mask). It is staged from the "
        "v1_5_raritan_z15 registry entry, which shares one `mesh_key` with the premier "
        "and re-derives only the mask and boundary. Motivated by the open thread that the "
        "premier generates only +0.027 m of setup between the boundary and the shore with "
        "waves on — far too small — which bears directly on whether a deeper boundary "
        "buys anything. ⚠️ −2 m was considered and DROPPED: at that depth NACCS's embedded "
        "wave setup is the whole signal, so SnapWave would have to be off, and "
        "setup-at-the-boundary XOR SnapWave is the branch measured to overestimate max "
        "water depth by ~1 m.",
        waterlevel_geodataset="naccs_sandy_v1_5_raritan",
        # Measured on the FROZEN mesh 2026-08-14: 532 NACCS save points -> 139
        # within 2 km of a mask==2 cell -> 71 after the dry (-29) and open-coast
        # depth (-39) screens. Per arm: ocean 43, narrows 13, arthur_kill 15 —
        # no arm empty, which was gate 1. Declared on the ARM, never by relaxing
        # Domain.n_waterlevel_support (which guards the base NOAA selection).
        n_waterlevel_support=71,
    ),
}


#: ``domain name -> {arm name -> Experiment}``.
#:
#: ``v1_monmouth`` is deliberately EMPTY. It is a frozen port-verification fixture: its
#: one run directory is copied out of the archive and RESCORED, never staged from a
#: config and never re-run. An empty dict is the honest statement of that — a populated
#: one would invite `--experiments all` to try.
# ── v3 ────────────────────────────────────────────────────────────────────────
# The full Jersey shore. Frozen 2026-08-26; three arms (user, 2026-08-26): CORA waves,
# NACCS STWAVE waves, waves off. Same NACCS 224-point water level on all three.
_V3_CORA = DATA / "waves_v3" / "cora_waves_v3.nc"
_V3_STWAVE = DATA / "waves_v3" / "naccs_stwave_v3.nc"
# v1.5 put 7 wave support points on a 25 km open-coast edge. v3's open-coast boundary
# runs ~178 km of northing (y 4,298,500 .. 4,476,000), so 7 would be one point per
# 25 km; 36 keeps ~5 km, the CORA/STWAVE nearest-node limit in model._point_wave_bnd.
_V3_WAVE_N = 36
_V3_WL = dict(
    waterlevel_geodataset="naccs_sandy_v3",
    # Measured 2026-08-26 on the v3 mask==2 line (6,835 cells): 1,321 NACCS save points
    # -> 406 within 2 km -> 224 after the dry (-67) and open-coast depth (-115) screens.
    # Per arm: ocean 44, narrows 13, arthur_kill 15, ocean_south 154. Declared on the
    # ARM, never by relaxing Domain.n_waterlevel_support.
    n_waterlevel_support=224,
)
# The stepped-boundary wave config, hoisted so its one-flag unions below are built with
# `replace()` and cannot drift from it (STATUS 2026-09-09: three arms share this band).
_V3_SHELF_STEPS_WAVES = WaveConfig(
    use_waves=True,
    wave_wind=True,
    wave_igwaves=False,
    tune_physics=True,
    wave_point_dataset=_V3_CORA,
    snapwave_domain="v3_shelf_steps",
    # ~275 km of stepped line at ~4.6 km — the CORA nearest-node limit is 5 km.
    wave_n_support=60,
    # 17 % of the premier's SnapWave calls hit the 25-iteration cap with the
    # unconverged nodes ≈ the boundary ring; a higher cap keeps convergence from
    # masking whether the ring is fixed. Costs time only on calls that need it.
    snapwave_niter=200,
)
# ── THE ENGINE EPOCH — 2026-09-11 ───────────────────────────────────────────────
# SFINCS v2.3.3 through v2.4.1 launch the imposed boundary spectrum in the domain-mean
# WIND direction when `snapwave_wind = 1` (FINDINGS §43). Every wind-on arm scored before
# this date carries that; their rows stay in metrics.csv with `snapwave_direction = wind`
# and their metrics table is frozen as metrics_2026-09-11_pre_winddir_rebaseline.csv.
# The arms below run on the patched native engine (`nj-winddir-fix-1`,
# hpc/build_sfincs_native.sh, hpc/patches/snapwave_winddir_v2.3.3.patch).
#
# The retired v3 arms — the old `naccs-premier` (36-point isobath band, fw 0.02, IG off,
# template subgrid), `wave-stwave`, `diag-premier-norain`, `bed-buildings`,
# `wave-shelf-steps`, `wave-fw01+wave-shelf-steps`, `wave-nowind+wave-shelf-steps`,
# `BRACKET+setup-stockdon` — are not registered any more: their configs are in git
# (this file before 2026-09-11), their numbers in the CSVs, their reads in STATUS and
# FINDINGS. `premier.BRACKETS["setup-stockdon"]` stays, so the bracket dir still audits.
#
# ONE constant defines the premier's wave physics; every attribution arm is ONE field
# off it (tests/test_engine_epoch.py pins that), so the 2×2×2 reads paired and clean:
#   premier              APEX band · wind ON · IG ON · fw 0.01 · buildings subgrid
#   wave-fw02            fw 0.02 (what every arm ran to 09-10; engine default is 0.01)
#   wave-noig            IG OFF — ⚠️ a null by construction without a wavemaker (§45)
#   bed-nobuildings      the sealed template's subgrid (no footprints)
#   naccs-nowaves        SnapWave OFF, buildings subgrid (so waves-on/off is one flag)
# ⚠️ wave-fw02 / wave-noig / bed-nobuildings have NOT been run on the apex band yet
# (09-17); their scored twins were the old-band `wave-band-sandy-hook+…` rows, retired
# 2026-09-21 (rows kept in metrics.csv, arms out of the registry 09-22).
# ── THE APEX BAND — 2026-09-17 ──────────────────────────────────────────────────
# The premier's SnapWave band now runs its east leg north past Sandy Hook to the Long
# Island shore (`v3_shelf_steps_apex`, +3 support points, the open-coast demotion
# lifted). Scored as `wave-apex` against the Sandy-Hook-cut band on 09-14/17: paired
# HWM ΔRMSE −0.0145 m, 95 % CI [−0.0249, −0.0053], carried by the Sandy Hook Bay and
# Raritan Bay marks; 0.1–0.3 m more hm0 at the Lower Bay entrance on most hours; the
# coast south of Sandy Hook unchanged on cap-hit-free hours (STATUS 09-17). User
# decision 09-17: every future run shares this boundary. The runs made with the OLD
# band were renamed on disk and in metrics.csv to `wave-band-sandy-hook[+…]`, retired
# 2026-09-21 and dropped from the registry 2026-09-22 (git has the entries).
# metrics_2026-09-17_pre_apex_rebaseline.csv is the table as it stood before the rename.
_V3_PREMIER_WAVES = replace(
    _V3_SHELF_STEPS_WAVES,
    snapwave_fw=0.01,
    wave_igwaves=True,
    snapwave_domain="v3_shelf_steps_apex",
    wave_n_support=63,  # +3 for the 11.8 km leg, keeps ~4.6 km spacing
    open_coast_max_y=float("inf"),
)
_V3_BUILDINGS = dict(subgrid_from="_subgrid_buildings")

_V3: dict[str, Experiment] = {
    "naccs-premier": Experiment(
        "naccs-premier",
        _V3_PREMIER_WAVES,
        "THE v3 PREMIER, engine epoch nj-winddir-fix-1 (2026-09-11). NACCS/CHS ADCIRC "
        "storm tide on the 224-point boundary; CORA waves imposed at 63 support points "
        "on the grid-aligned shelf-steps band (~25-30 m) whose east leg runs north to "
        "the Long Island shore (the apex band, 2026-09-17), launched in the "
        "direction CORA gives them; wind growth ON; infragravity ON (engine defaults: "
        "Herbers bound long wave, gamma_ig 0.2, fw_ig 0.015); bottom friction fw 0.01 "
        "(the engine default; every arm to 09-10 ran 0.02); NJDEP building footprints in "
        "the subgrid at ground + 4 m. PRE-REGISTRATION lives in STATUS (09-11): boundary "
        "wavdir within 5 deg of .bwd every hour; entry-band transmission >= the wind-off "
        "run's; -9 m shelf >= wind-off's at every site; bay hm0 0.2-0.5 m; cap-hits "
        "<= 8 of 145; hm0ig/hm0 p99 <= 0.5 below 5 m depth, no cell hm0ig > 1 m; "
        "runtime <= 2x the wind-off run.",
        **_V3_BUILDINGS,
        **_V3_WL,
    ),
    "wave-fw02": Experiment(
        "wave-fw02",
        replace(_V3_PREMIER_WAVES, snapwave_fw=0.02),
        "Premier with SnapWave bottom friction fw 0.01 -> 0.02, the value every arm ran "
        "to 2026-09-10. Attribution of the friction lever alone on the fixed engine: "
        "measured 09-09 on the misdirected engine as the quarter-lever (shelf ratio "
        "+0.02..+0.12); expected the same size here, bay hm0 unchanged.",
        **_V3_BUILDINGS,
        **_V3_WL,
    ),
    "wave-noig": Experiment(
        "wave-noig",
        replace(_V3_PREMIER_WAVES, wave_igwaves=False),
        "Premier with the infragravity balance OFF, the setting every arm ran to "
        "2026-09-10. The old 'IG is a null lever' verdict (FINDINGS Closed) was measured "
        "with misdirected waves at a -10 m boundary; this is its retest on the fixed "
        "engine and the shelf-steps band. Read: open-coast HWM maxima (IG adds 0-0.1 m "
        "of runup-side level), bay pre-storm means unchanged within +-0.02 m, paired "
        "dRMSE with CI.",
        **_V3_BUILDINGS,
        **_V3_WL,
    ),
    "wave-wavemaker": Experiment(
        "wave-wavemaker",
        replace(
            _V3_PREMIER_WAVES,
            wavemaker=True,
            wavemaker_line=DATA / "wavemakers_v3" / "v3_wavemaker_5m_mhw.geojson",
        ),
        "Premier plus the ocean-side WAVEMAKER line: 10 pieces, 142.8 km, along the "
        "MHW-5 m contour of the open coast, 600 m setback from every inlet, land on "
        "the LEFT of every piece's vertex order (checked against the bed 2026-09-18). "
        "The first arm on which the infragravity balance can touch the water level at "
        "all (FINDINGS 45: without a wavemaker IG is a null by construction), so this "
        "is the IG lever, one change from the premier. Engine: v2.3.3-winddir-igk-fix-1 "
        "(the wavemaker-orientation + IG-wavenumber backport; the premier's build "
        "injects NOTHING on a mis-oriented line, FINDINGS 47). IG knobs at the engine "
        "defaults (gamma_ig 0.2). PRE-REGISTRATION in STATUS (09-18): oceanfront HWM "
        "bias moves toward 0 (+0.05..+0.15 m on atlantic_oceanfront / south_coast / "
        "lbi_barrier / absecon_atlantic_city marks, paired), bays unchanged within "
        "+-0.02 m paired median, MOTF POD up in overwash zones, no cell zs > 5 m, "
        "nothing seaward of the line, runtime <= 1.3x the premier.",
        **_V3_BUILDINGS,
        **_V3_WL,
    ),
    "wave-wavemaker+wind-x110": Experiment(
        "wave-wavemaker+wind-x110",
        replace(
            _V3_PREMIER_WAVES,
            wavemaker=True,
            wavemaker_line=DATA / "wavemakers_v3" / "v3_wavemaker_5m_mhw.geojson",
        ),
        "The wavemaker premier candidate with the ERA5 10 m wind scaled by 1.10 "
        "(both components; pressure untouched; SnapWave wind growth sees the same "
        "field). A forcing-SENSITIVITY probe, not a candidate: measured 2026-09-20, "
        "ERA5 matches the NDBC buoys offshore and runs ~10 % low at the exposed harbour "
        "and coast stations (Robbins Reef 0.89, Cape May 0.90), so x1.10 is the size of "
        "the shortfall over the bays. Read: dEta/dU at Great Kills / Arthur Kill mouth / "
        "the raritan_bay + sandy_hook_bay marks (paired vs wave-wavemaker), the forced "
        "Narrows unchanged, the open coast within +-0.03. PRE-REGISTRATION in STATUS "
        "(09-20). Same engine as wave-wavemaker (v2.3.3-winddir-igk-fix-1).",
        wind_scale=1.10,
        **_V3_BUILDINGS,
        **_V3_WL,
    ),
    "bed-nobuildings": Experiment(
        "bed-nobuildings",
        _V3_PREMIER_WAVES,
        "Premier on the sealed template's subgrid (no building footprints). The "
        "buildings lever alone: measured 09-08 as paired dRMSE +0.008 [-0.027, +0.041] "
        "on the old engine; expected within +-0.02 m again.",
        **_V3_WL,
    ),
    # The five Sandy-Hook-cut-band runs (`wave-band-sandy-hook[+…]`, renamed 09-17)
    # were RETIRED 2026-09-21 (`experiments/v3/_retired/`, maps gone, metrics rows kept)
    # and left the registry 2026-09-22 with `_V3_OLD_BAND`; both are in git history.
    "naccs-nowaves": Experiment(
        "naccs-nowaves",
        WaveConfig(use_waves=False),
        "Premier with SnapWave OFF, buildings subgrid kept so waves-on/off is ONE flag. "
        "Extent metrics flagged extent_admissible=False, never ranked against a "
        "waves-on arm (CLAUDE.md §6). Re-run on the fixed engine (52 min) so the pair "
        "shares an engine label.",
        **_V3_BUILDINGS,
        **_V3_WL,
    ),
}


EXPERIMENTS_BY_DOMAIN: dict[str, dict[str, Experiment]] = {
    "v1_monmouth": {},
    "v1_5_raritan": _V1_5_RARITAN,
    "v1_5_raritan_z15": _V1_5_RARITAN,
    # Frozen archive fixture, score-only (scripts/score_v2_barnegat.py): its five
    # archived runs are RESCORED in place, never staged from a config.
    "v2_barnegat": {},
    # ⏳ BUILDING (see nj_sfincs/domain.py): the polygon is drawn and gated, the mesh is
    # not frozen. Arms (`naccs-premier`, `naccs-nowaves`) are registered at the freeze,
    # once there is a fingerprint for premier.py to check them against.
    "v3": _V3,
}


def experiments(domain_name: str | None = None) -> dict[str, Experiment]:
    """The arms defined for a domain (the ACTIVE one by default).

    Returns an empty dict for a domain with no arms — that is a real state (a frozen
    fixture, a domain registered but not yet planned), not an error.
    """
    return dict(EXPERIMENTS_BY_DOMAIN.get(domain_name or active().name, {}))


def sweepable(domain_name: str | None = None) -> dict[str, Experiment]:
    """The arms ``--experiments all`` may stage: everything except brackets.

    A bracket is a deliberately inadmissible bound; sweeping one would put a known-wrong
    domain into a candidate table, which is exactly the failure the Barnegat Inlet clamp
    taught us to design against. Naming it explicitly (plus ``NJ_ALLOW_BRACKET``) is the
    only way to run one.
    """
    return {n: e for n, e in experiments(domain_name).items() if e.bracket is None}
