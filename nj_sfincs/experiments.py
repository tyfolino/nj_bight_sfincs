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


# ── v4 ────────────────────────────────────────────────────────────────────────
# v3 + Delaware Bay / river, the Raritan to Manville, Newark Bay + the Meadowlands, far
# banks computed. First runs = the design's own GATE (STATUS 09-24/25): waves-off Sandy at
# +0 / +2 / +3 m — does the ring contain the water it was drawn to contain? All three use
# the connected sea-level start (nj_sfincs/sea_level.py), +0 included, so the ladder
# differs ONLY in the offset; rain off (a surge target). Read with
# scripts/overflow_check.py.
_V4_WL = dict(
    waterlevel_geodataset="naccs_sandy_v4",
    # Built 2026-09-28 on the frozen mesh (scripts/build_naccs_boundary.py): 1,957 save
    # points -> 388 within 2 km of a mask==2 cell -> 241 after the dry (-64) and
    # open-coast depth (-83) screens; every arm covered (cd_canal by one point, 0.76 km).
    n_waterlevel_support=241,
)
_V4_SLR_WHY = (
    "Waves-off Sandy with {m:+.0f} m on the whole water-level boundary and a connected "
    "start at {m:+.0f} m (dry where the sea does not reach through the subgrid sills). "
    "The v4 design GATE: the ring was drawn to contain the NACCS Sandy peak + 3 m; this "
    "reads where the model's own water reaches the ring edge, the walls and the river "
    "cuts. RAIN OFF (rivers on): the ring contains a SURGE target, and with rain on, "
    "ponding at an upland edge reads as water reaching it. Extent flagged "
    "extent_admissible=False like every waves-off arm."
)
_V4: dict[str, Experiment] = {
    "naccs-nowaves": Experiment(
        "naccs-nowaves",
        WaveConfig(use_waves=False),
        "NACCS/CHS ADCIRC storm tide on the drawn water-level line, SnapWave OFF, the "
        "template's start (zsini 0). The v4 baseline every later arm is paired against.",
        **_V4_WL,
    ),
    **{
        f"naccs-nowaves+rain-off+slr-{m}m": Experiment(
            f"naccs-nowaves+rain-off+slr-{m}m",
            WaveConfig(use_waves=False),
            _V4_SLR_WHY.format(m=m),
            rain=False,
            sea_level_offset_m=float(m),
            **_V4_WL,
        )
        for m in (0, 2, 3)
    },
}
# A+ (v4_hot_plus, user's pick 2026-10-05) = v4's arms + bed tests on its own mesh.
_V4_HOT_PLUS: dict[str, Experiment] = {
    **_V4,
    # 2026-10-05 (STATUS "Raritan Bay / harbour low in v4", Step 2): CUDEM has none of the
    # dredged harbour trench (Kill van Kull -0.2..-4 m vs a 50 ft project, Newark Bay
    # -0.6..-3.4 vs -13..-18), and the Kill van Kull is Newark Bay's only modelled inlet —
    # the Step-1 chain: choked KvK -> low, late Newark Bay -> the Arthur Kill drains western
    # Raritan Bay. The USACE eHydro surveys painted OVER the unchanged merge
    # (`rebuild_subgrid.py --overlay ehydro_harbour_v4`); paired against naccs-nowaves.
    "bed-harbour+naccs-nowaves": Experiment(
        "bed-harbour+naccs-nowaves",
        WaveConfig(use_waves=False),
        "naccs-nowaves with the surveyed harbour channels (Kill van Kull, Newark Bay, the "
        "port channels, the Arthur Kill) carved into the subgrid by overlay. The test of "
        "the Step-1 chain: Newark Bay's tide and peak should recover and western Raritan "
        "Bay rise toward the observed 4.09 m at South Amboy.",
        subgrid_from="_subgrid_kills",
        **_V4_WL,
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
    "wave-coupled": Experiment(
        "wave-coupled",
        replace(
            _V3_PREMIER_WAVES,
            snapwave_domain=None,
            decouple_snapwave=False,
            # the SFINCS ocean arms, Rockaway leg included (the apex lesson, FINDINGS
            # §46); NOT the Narrows / Arthur Kill cuts inside the harbour
            wave_boundary_arms=("ocean", "ocean_south"),
            # northing bins, Cape May -> Rockaway Point (~181 km) at ~4.5 km
            wave_n_support=40,
        ),
        "Premier with the SnapWave boundary pulled back ONTO the water-level boundary "
        "(the pre-09-08 coupled mask, no shelf band), on the fixed engine. The band was "
        "adopted 09-08 on two reads made with the wind-direction bug in (FINDINGS §43): "
        "the -9 m shelf keeping 0.14-0.62 of the imposed Hs, and 39 % of the cells "
        "touching the -10 m boundary carrying no waves (the dead ring). The bug explained "
        "most of the first; the second was never re-measured. ONE change against the "
        "premier: where the waves enter (the Lower Bay entrance stays forced, as the apex "
        "band supplies it). PRE-REGISTRATION in STATUS 2026-09-28.",
        **_V3_BUILDINGS,
        **_V3_WL,
    ),
    # ── WAVE COST TESTS — 2026-09-30 (plan Phase 3; STATUS "Wave cost tests") ─────────
    # SnapWave is ~97 % of the premier's wall time (FINDINGS §20). Which cheaper setting
    # keeps the waves-on gain (ΔRMSE −0.064 m vs naccs-nowaves, §48)? Full-window, scored.
    # The wind-off arms pin the 360° sector so switching wind off is ONE physics change.
    "wave-dt3600+wave-dtheta10+wave-noig": Experiment(
        "wave-dt3600+wave-dtheta10+wave-noig",
        replace(
            _V3_PREMIER_WAVES, dtwave=3600.0, snapwave_dtheta=10, wave_igwaves=False
        ),
        "Premier with the three settings that cost time without (as far as we know) "
        "buying setup: SnapWave every 60 min instead of 30 (the engine default), 10° "
        "direction bins over the full 360° (36 bins, not 72; the engine default bin), "
        "and the IG balance off (a null without a wavemaker, FINDINGS §45). Wind growth "
        "stays ON. The physics-preserving cheap configuration; scored paired against "
        "the premier and naccs-nowaves, by basin group.",
        **_V3_BUILDINGS,
        **_V3_WL,
    ),
    "wave-dt3600": Experiment(
        "wave-dt3600",
        replace(_V3_PREMIER_WAVES, dtwave=3600.0),
        "Premier with ONE change: SnapWave every 60 min instead of 30 (5° bins and IG "
        "kept). Isolates the Cape May jetty pocket (STATUS 10-02): both dt3600+dtheta10 "
        "arms hold the water west of the Cape May Inlet south jetty ~1 m above the "
        "full-cost arms for 3-4 h at the peak. Pocket here = the update interval; "
        "absent = the 10° bins.",
        **_V3_BUILDINGS,
        **_V3_WL,
    ),
    # 2026-10-05 (user): v3 re-run with the beds fixed on v4 the same day that fall inside
    # v3 — the §54 inland lakes (its 9 rain-pond lake marks), the 2010 lidar's sills undone
    # (Great Egg Harbor Inlet, Inside Thorofare, Compton Ck), the harbour + Raritan-corner
    # creek surveys, the Mullica / Tuckahoe GMRT holes carved (Cohansey rule) — overlaid
    # after v3's own building burn (`_subgrid_v4fixes`). Hourly SnapWave like v4. Paired
    # against wave-dt3600 (the bed alone) and its twin against naccs-nowaves.
    "bed-v4fixes+wave-dt3600": Experiment(
        "bed-v4fixes+wave-dt3600",
        replace(_V3_PREMIER_WAVES, dtwave=3600.0),
        "wave-dt3600 on v3's buildings bed plus the 10-05 v4 bed fixes inside v3: inland "
        "lakes, the 2010-lidar sills undone, harbour and creek surveys, the Mullica and "
        "Tuckahoe GMRT holes carved. Paired against wave-dt3600, it reads the beds alone.",
        subgrid_from="_subgrid_v4fixes",
        **_V3_WL,
    ),
    "bed-v4fixes+naccs-nowaves": Experiment(
        "bed-v4fixes+naccs-nowaves",
        WaveConfig(use_waves=False),
        "naccs-nowaves on the bed of bed-v4fixes+wave-dt3600 (v3 buildings + the 10-05 v4 "
        "bed fixes inside v3). Paired against naccs-nowaves: the beds alone, waves off.",
        subgrid_from="_subgrid_v4fixes",
        **_V3_WL,
    ),
    "wave-dt3600+wave-dtheta10+wave-wavemaker": Experiment(
        "wave-dt3600+wave-dtheta10+wave-wavemaker",
        replace(
            _V3_PREMIER_WAVES,
            dtwave=3600.0,
            snapwave_dtheta=10,
            wavemaker=True,
            wavemaker_line=DATA / "wavemakers_v3" / "v3_wavemaker_5m_mhw.geojson",
        ),
        "The cheap configuration's two real changes (SnapWave every 60 min, 10° bins) "
        "on wave-wavemaker: IG ON and the same ocean-side line, so the IG balance "
        "reaches the water (FINDINGS §45, §49). Does the cheap setup still deliver the "
        "shoreline IG? Engine v2.3.3-winddir-igk-fix-1, as wave-wavemaker; paired "
        "against wave-wavemaker (same binary), read at the beach (Sea Bright storm-tide "
        "sensor, USGS sandline transects), not only the pooled marks. STATUS 10-01.",
        **_V3_BUILDINGS,
        **_V3_WL,
    ),
    "wave-nowind": Experiment(
        "wave-nowind",
        replace(_V3_PREMIER_WAVES, wave_wind=False, snapwave_sector=360),
        "Premier with SnapWave wind growth OFF, sector kept at 360°. What wind growth is "
        "worth on the FIXED engine (the only wind-off rows so far are on the misdirected "
        "engine and old band). Wind-off removes the 0.2–0.5 m bay fetch waves (§43) but "
        "also the wind-mode limit cycle; expected several times cheaper.",
        **_V3_BUILDINGS,
        **_V3_WL,
    ),
    "wave-dt3600+wave-dtheta10+wave-noig+wave-nowind": Experiment(
        "wave-dt3600+wave-dtheta10+wave-noig+wave-nowind",
        replace(
            _V3_PREMIER_WAVES,
            dtwave=3600.0,
            snapwave_dtheta=10,
            wave_igwaves=False,
            wave_wind=False,
            snapwave_sector=360,
        ),
        "The cheapest real SnapWave: the cheap configuration above with wind growth off "
        "as well. Swell and its setup only. Scored like the others.",
        **_V3_BUILDINGS,
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


# ── A+ (v4_hot_plus): the first waves-on v4 run, 2026-10-05 ───────────────────
# The v3 premier's wave physics (wind ON, IG ON, fw 0.01, 5° bins) with the user's cheap
# setting (10-05: HOURLY updates, dtwave 3600 — FINDINGS §61: half the solve, nothing at
# the marks) on v4's own band (`v4_shelf_steps`, carried south across the Delaware mouth),
# CORA at 69 support points (~4.6 km, v3's spacing; preflight
# logs/audit_v4_hot_plus_2026-10-05/snapwave_domain.txt) and no demotion north of Sandy
# Hook (the band's leg runs to Long Island, as v3's apex). Bed `_subgrid_premier`
# (logs/bedfix_2026-10-05/): the NJDEP building burn (ground + 4 m), then the 10-05
# channel fixes — the 2010 lidar's sills undone, the harbour and Raritan-corner creek
# surveys, the Cohansey at a stated depth. Named `bed-…` because A+'s own premier (the bed
# every non-bed arm shares, tests/test_bed_arms.py) is still the template's until the
# re-freeze. Paired: its waves-off twin (one flag), and naccs-nowaves (bed + waves).
_V4_CORA = DATA / "waves_v4" / "cora_waves_v4.nc"
_V4_PREMIER_WAVES = replace(
    _V3_PREMIER_WAVES,
    wave_point_dataset=_V4_CORA,
    snapwave_domain="v4_shelf_steps",
    wave_n_support=69,
    dtwave=3600.0,
)
_V4_HOT_PLUS.update(
    {
        "bed-buildings+bed-channels+naccs-premier": Experiment(
            "bed-buildings+bed-channels+naccs-premier",
            _V4_PREMIER_WAVES,
            "THE first waves-on v4 (A+) run: the v3 premier's wave physics with hourly "
            "SnapWave updates on v4's shelf-steps band, CORA at 69 points; NACCS on the "
            "drawn line; rain + infiltration; the building burn and the 10-05 channel "
            "fixes in the subgrid. Imperfect by design (mask leaks, GMRT reaches, inland "
            "lakes still open — reports/v4_refreeze_list_2026-10-05.md).",
            subgrid_from="_subgrid_premier",
            **_V4_WL,
        ),
        "bed-buildings+bed-channels+naccs-nowaves": Experiment(
            "bed-buildings+bed-channels+naccs-nowaves",
            WaveConfig(use_waves=False),
            "The waves-on run's waves-off twin (one flag): the same building + channel "
            "subgrid, SnapWave off. Against naccs-nowaves it reads the bed changes alone.",
            subgrid_from="_subgrid_premier",
            **_V4_WL,
        ),
    }
)


# ── v4_hot_plus_walls (run B, 2026-10-05): A+ + the edge audit's leak walls + four
# inflows in their channels; its OWN premier carries the whole 10-05 bed (`_subgrid_premier`
# on this domain: buildings, the 2010-lidar sills undone, harbour + Raritan-corner creek
# surveys, the Cohansey and the four GMRT reaches at a stated depth) + the §54 inland
# lakes (bed only; user 10-05, DECISIONS.md). Deferred: the building cap, lake n 0.02.
_V4_HOT_PLUS_WALLS: dict[str, Experiment] = {
    "naccs-premier": Experiment(
        "naccs-premier",
        _V4_PREMIER_WAVES,
        "Run B: the first waves-on v4 run with every 10-05 fix the user approved — A+ "
        "with the leak walls, the four inflows in their channels, and the full channel / "
        "river bed (buildings, the 2010-lidar sills undone, harbour and Raritan-corner "
        "surveys, the Cohansey and the four GMRT reaches). Waves as A+'s run A.",
        subgrid_from="_subgrid_premier",
        **_V4_WL,
    ),
    "naccs-nowaves": Experiment(
        "naccs-nowaves",
        WaveConfig(use_waves=False),
        "Run B's waves-off twin (one flag), on the same bed: SnapWave off, NACCS on the "
        "drawn line, so waves-on minus this reads the wave contribution alone.",
        subgrid_from="_subgrid_premier",
        **_V4_WL,
    ),
}


# ── v4_refreeze (2026-10-06, user): THE re-frozen v4 = v4_hot_plus_walls + the Lewes ring
# edit, on the re-freeze bed `_subgrid_refreeze` (buildings cap 10 → lakes → unpave →
# harbour / Raritan-corner surveys → back-bay unpave → Sayreville → Little Egg → the
# bed-source hierarchy LAST; n 0.02 on non-marsh NHD water; job 62308704). Every arm runs
# on that bed — it is this domain's premier bed, so no `bed-` prefix. The template carries
# the Keansburg + Overpeck weirs, the Overpeck pool start (−1.005 m, regional inifile) and
# the ERA5-bilinear meteo on the engine's corner convention; arms inherit all three by
# copytree (the SLR arms replace the start with their own connected one).
_REFREEZE_BED = "_subgrid_refreeze"
# The NACCS-blend wind + pressure (user 10-06; logs/wind_naccs_blend_2026-10-06/README.md):
# NACCS save-point field blended into ERA5 bilinear (linear Delaunay, long/land triangles
# dropped, 15 km harmonic taper, 500 m, 30 min), REPLACED after the write by
# `Experiment.meteo_from`; the template keeps the ERA5-bilinear file. Blend pressure (the
# file's default; `--pressure era5` rebuilds it with ERA5 pressure).
_NACCS_BLEND = DATA / "wind_v4" / "naccs_blend"
# 🔴 RE-BASELINED 2026-10-11 (user): `naccs-premier` / `naccs-nowaves` ARE the NACCS-blend
# pair (run 10-09 as `wind-naccs+naccs-premier` / `wind-naccs+naccs-nowaves`, renamed into
# place, uninterrupted). The ERA5-bilinear pair and the ERA5 no-infiltration test are parked
# in experiments/v4_refreeze/_pre_rebaseline_2026-10-11/ with their rows frozen in
# metrics_2026-10-11_pre_rebaseline.csv (FINDINGS part 4 (g)). The SLR gate arms keep the
# template's ERA5-bilinear meteo (rain off, waves off: a containment check, not a score).
_V4_REFREEZE: dict[str, Experiment] = {
    "naccs-premier": Experiment(
        "naccs-premier",
        _V4_PREMIER_WAVES,
        "THE v4 premier (re-baselined 2026-10-11): run B's waves (SnapWave 5°, hourly "
        "dtwave 3600, CORA at 69 points on v4_shelf_steps) and NACCS on the drawn line, "
        "the Lewes edge, the re-freeze bed, the Keansburg + Overpeck weirs, the Overpeck "
        "pool start, rain + curve-number infiltration (AMC II), and the NACCS-blend wind "
        "+ pressure (data/wind_v4/naccs_blend). Over-water lights 0.71 -> 1.06x observed "
        "vs ERA5; Raritan E-W stress 2.05x; Barnegat N-S 0.38x.",
        subgrid_from=_REFREEZE_BED,
        meteo_from=_NACCS_BLEND,
        **_V4_WL,
    ),
    "naccs-nowaves": Experiment(
        "naccs-nowaves",
        WaveConfig(use_waves=False),
        "The premier's waves-off twin (one flag): same bed, structures, start, rain, "
        "infiltration and NACCS-blend meteo, SnapWave off.",
        subgrid_from=_REFREEZE_BED,
        meteo_from=_NACCS_BLEND,
        **_V4_WL,
    ),
    **{
        f"naccs-nowaves+rain-off+slr-{m}m": replace(
            _V4[f"naccs-nowaves+rain-off+slr-{m}m"], subgrid_from=_REFREEZE_BED
        )
        for m in (0, 2, 3)
    },
}
# 2026-10-11: the LIKE-FOR-LIKE v4 counterpart of the v3 reference below — the premier pair
# with the curve-number infiltration OFF (v3 has none). One flag off its twin each. NOT a
# premier candidate: the no-infiltration gain at the coastal-lake marks is closed-basin
# rain ponding (FINDINGS part 4 (g)). (The 10-08 ERA5 `naccs-nowaves+rain-noinfil` test is
# parked with the ERA5 pair; this name now means the NACCS-wind version.)
_V4_REFREEZE.update(
    {
        f"{n}+rain-noinfil": replace(
            _V4_REFREEZE[n],
            name=f"{n}+rain-noinfil",
            description=f"{n} with the curve-number infiltration OFF (rain kept, every "
            f"drop runs off — v3's setup). Pair: {n}. Like-for-like counterpart of v3's "
            "NACCS-wind reference (2026-10-11).",
            infiltration=False,
        )
        for n in ("naccs-premier", "naccs-nowaves")
    }
)
# 2026-10-11 (user): the v3 reference re-run to MATCH v4 — the shared-bed-fix pair on v4's
# exact wind + pressure (the same NACCS-blend files, staged by `meteo_from`, which refuses
# if any v3 active face falls outside the blend grid). The 10-05 `bed-v4fixes` runs carry
# the pre-10-06 meteo (ERA5 sampled half a cell off, FINDINGS part 4 (e)); a run staged
# now also gets the corner-fixed AORC rain. v3 has no infiltration (Domain), as above.
_V3.update(
    {
        f"{n}+wind-naccs": replace(
            _V3[n],
            name=f"{n}+wind-naccs",
            description=f"{n} with the 10 m wind + MSL pressure replaced by v4's "
            "NACCS-blend field (data/wind_v4/naccs_blend). Pair: "
            f"{n} (pre-10-06 ERA5). Candidate v3 reference matching the v4 premier "
            "(user 2026-10-11).",
            meteo_from=_NACCS_BLEND,
        )
        for n in ("bed-v4fixes+wave-dt3600", "bed-v4fixes+naccs-nowaves")
    }
)


EXPERIMENTS_BY_DOMAIN: dict[str, dict[str, Experiment]] = {
    "v1_monmouth": {},
    "v1_5_raritan": _V1_5_RARITAN,
    "v1_5_raritan_z15": _V1_5_RARITAN,
    # Frozen archive fixture, score-only (scripts/score_v2_barnegat.py, retired 2026-10-15, in git history): its five
    # archived runs are RESCORED in place, never staged from a config.
    "v2_barnegat": {},
    # DONE 2026-09-24; reference = naccs-premier on the repaired mask (FINDINGS §50).
    "v3": _V3,
    # FROZEN 2026-09-28; waves-off design-gate arms only, no waves-on premier yet.
    "v4": _V4,
    # 2026-10-02: the head-of-tide variants of v4 (A / A+, the river-cut memo) run v4's
    # own arms, so each pairs against v4 and against the other run for run.
    "v4_hot": _V4,
    "v4_hot_plus": _V4_HOT_PLUS,
    "v4_hot_plus_walls": _V4_HOT_PLUS_WALLS,
    # Re-baselined 2026-10-11: naccs-premier = the NACCS-blend wind pair (above).
    "v4_refreeze": _V4_REFREEZE,
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
