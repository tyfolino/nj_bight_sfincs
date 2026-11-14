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
from pathlib import Path

from .config import DATA, CalmForcing, Experiment, WaveConfig
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
# 2026-10-17 (user): the Deal Lake wave-OVERTOPPING sensitivity arm — the premier plus ONE
# extra point source inside Deal Lake's ocean end carrying the EurOtop (2018) mean overtopping
# discharge over the 260 m lake front, computed from the premier's OWN toe Hm0 / Tp / zs
# (scripts/eurotop_overtopping.py; logs/overtopping_2026-10-17/README.md). SFINCS + SnapWave
# has setup but no short-wave overtopping; mark 6122 (3.14 m) reads -2.37 m on the premier.
# Appended to the staged discharge file (`Experiment.extra_discharge`), so mesh, mask, bed and
# the template's 61 sources are the premier's. The forcing was derived from the UNSEEDED
# premier, so it carries that run's waves-on noise (FINDINGS §44).
_V4_REFREEZE["naccs-premier+src-deal-overtop"] = replace(
    _V4_REFREEZE["naccs-premier"],
    name="naccs-premier+src-deal-overtop",
    description="naccs-premier + an empirical wave-overtopping inflow into Deal Lake (EurOtop "
    "2018 sloping-front mean q from the premier's own toe Hm0/Tp/zs, post-storm USACE 2012 "
    "crest, 260 m frontage; peak 31.7 m3/s at 10-30 00 UTC, 0.29 Mm3) at the lake's ocean "
    "end, 841 m from mark 6122. Pair: naccs-premier. Sensitivity forcing, not a premier "
    "candidate.",
    extra_discharge=DATA / "discharge_v4" / "deal_lake_overtopping_v4_refreeze.nc",
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


# ── PHASE 4 (2026-10-19, user; STATUS FINAL AUDIT): the re-baseline on the SEEDED engine ─
# Candidate names `p4-…` while they run; after the read the winners are renamed into place
# (`naccs-premier`, …) and the current runs parked with their rows frozen — the 10-11 recipe.
# The engine is not an arm field: the job sets SFINCS_BIN to the seeded build
# (`v2.3.3-winddir-igk-igseed-wmseed-1-gf11`). Every p4 arm stages from the 10-17 template
# (moved inflows) at `snapwave_niter` 200 (the premier waves' own value, user 10-17).
#   p4-premier                     the new premier: the lower-only lake-fixed bed, `cnb` 1.5,
#                                  ERA5 pressure inside the blend, and the `snapbeach` wavemaker
#   p4-premier-repeat              identical — the seeded engine must repeat it exactly
#   p4-premier+wave-nowavemaker    the wavemaker's effect (user 10-17: measured, not assumed)
#   p4-nowaves                     SnapWave off
#   p4-premier+rain-cnb1.0 / 2.38  wetter (AMC II) / drier (AMC I) soil
#   p4-premier+rain-off            no rain: the waves-ON rain / coastal split (user 10-20)
#   bed-nobuildings+p4-premier     the building burn's effect on the apex band (§55)
#   bed-breach-wreck0 / -wreck165+p4-premier   the breach sensitivity (user 10-15 / 10-17)
#   p4-premier+src-deal-overtop    the Deal Lake overtopping inflow; its forcing is from the
#                                  UNSEEDED 10-11 premier's waves (user 10-19: run it, flagged)
#   null-rhoa1.2501 / 1.2499+p4-premier   the waves-on noise band through the peak (10-17)
# Horton infiltration: dropped from Phase 4 (user 10-19; the cnb ladder brackets infiltration).
# The *_creeks beds (2026-10-21): each Phase 4 bed + Beach Creek + the Delaware Bay creek beds
# (logs/creek_beds_2026-10-20/; FINDINGS part 4 (h)). The *_creeks_cohansey beds (2026-10-24,
# user: folded into the Phase 4 re-run with the NLD Keansburg weir and the cnb netCDF fix):
# the same recipes with riverbeds_hierarchy_v4c (logs/cohansey_fix_2026-10-23/).
_P4_BED = "_subgrid_refreeze_lakes_min_creeks_cohansey"
_NACCS_BLEND_P_ERA5 = DATA / "wind_v4" / "naccs_blend_p_era5"
_P4_WAVES = replace(
    _V4_PREMIER_WAVES,
    wavemaker=True,
    wavemaker_line=DATA / "wavemakers_v4" / "v4_wavemaker_5m_mhw_snapbeach.geojson",
)
_P4_WHY = (
    " Phase 4 candidate (seeded engine, 2026-10-19); renamed into place after the read."
)
_p4 = replace(
    _V4_REFREEZE["naccs-premier"],
    name="p4-premier",
    waves=_P4_WAVES,
    description="The new v4 premier candidate: naccs-premier on the lower-only lake-fixed bed "
    "(_subgrid_refreeze_lakes_min_creeks_cohansey), the Keansburg levee system on the "
    "USACE NLD line (data/structures_v4/sfincs.weir, 10-24), curve number with recovery (cnb, AMC factor 1.5), the "
    "NACCS-blend wind with ERA5 pressure inside the blend (data/wind_v4/naccs_blend_p_era5), "
    "the moved inflows (template 10-17) and the snap-seaward-of-beach wavemaker line "
    "(8 pieces, 157.7 km; logs/wavemaker_v4_2026-10-17/)." + _P4_WHY,
    subgrid_from=_P4_BED,
    meteo_from=_NACCS_BLEND_P_ERA5,
    cnb_effective=1.5,
)


def _p4_arm(name: str, description: str, **changes) -> Experiment:
    return replace(_p4, name=name, description=description + _P4_WHY, **changes)


_V4_REFREEZE.update(
    {
        "p4-premier": _p4,
        "p4-premier-repeat": _p4_arm(
            "p4-premier-repeat",
            "p4-premier, identical: on the seeded engine it must repeat bit for bit.",
        ),
        "p4-premier+wave-nowavemaker": _p4_arm(
            "p4-premier+wave-nowavemaker",
            "p4-premier with the wavemaker OFF (IG computed but not in the water, as the "
            "10-11 premier). Pair: p4-premier — the wavemaker's effect.",
            waves=replace(_P4_WAVES, wavemaker=False),
        ),
        "p4-nowaves": _p4_arm(
            "p4-nowaves",
            "p4-premier with SnapWave off (one flag). Pair: p4-premier.",
            waves=WaveConfig(use_waves=False),
        ),
        **{
            f"p4-premier+rain-cnb{e}": _p4_arm(
                f"p4-premier+rain-cnb{e}",
                f"p4-premier with the cnb antecedent-moisture factor {e} "
                f"({'AMC II, wetter' if e == '1.0' else 'AMC I, drier'} soil than the "
                "premier's 1.5). Pair: p4-premier.",
                cnb_effective=float(e),
            )
            for e in ("1.0", "2.38")
        },
        "p4-premier+rain-off": _p4_arm(
            "p4-premier+rain-off",
            "p4-premier with the rain forcing removed (netamprfile and the infiltration "
            "keys stripped: SFINCS infiltration acts only on rain, model.py). The waves-ON "
            "twin for splitting flooding into "
            "rain and coastal: the 10-20 split had only waves-off twins (user 10-20). "
            "Pair: p4-premier.",
            rain=False,
        ),
        "bed-nobuildings+p4-premier": _p4_arm(
            "bed-nobuildings+p4-premier",
            "p4-premier on the same bed WITHOUT the building burn "
            "(_subgrid_refreeze_lakes_min_nobuildings_creeks_cohansey: the premier's recipe "
            "minus bed_buildings_v4_cap10; logs/nobuildings_2026-10-19/). Pair: p4-premier.",
            subgrid_from="_subgrid_refreeze_lakes_min_nobuildings_creeks_cohansey",
        ),
        **{
            f"bed-breach-{v}+p4-premier": _p4_arm(
                f"bed-breach-{v}+p4-premier",
                f"p4-premier on the breach bed _subgrid_breach_{v}_creeks_cohansey: Wreck Pond "
                "channel at "
                f"{'0.0' if v == 'wreck0' else '1.65'} m NAVD88 + the Mantoloking cuts "
                "(post-storm EAARL-B), n 0.025 on the cut, open all run — an upper bound "
                "(FINDINGS part 4 (h)). Pair: p4-premier.",
                subgrid_from=f"_subgrid_breach_{v}_creeks_cohansey",
            )
            for v in ("wreck0", "wreck165")
        },
        "p4-premier+src-deal-overtop": _p4_arm(
            "p4-premier+src-deal-overtop",
            "p4-premier + the Deal Lake EurOtop overtopping inflow. ⚠️ The inflow was "
            "derived from the UNSEEDED 10-11 premier's toe waves (user 10-19: run it, "
            "flagged; re-derive only if p4-premier's toe waves move much). Pair: p4-premier.",
            extra_discharge=_V4_REFREEZE[
                "naccs-premier+src-deal-overtop"
            ].extra_discharge,
        ),
        **{
            f"null-rhoa{r}+p4-premier": _p4_arm(
                f"null-rhoa{r}+p4-premier",
                f"p4-premier with rhoa {r} (template 1.25): a NULL perturbation. The two "
                "null copies give the waves-on noise band through the peak as a spread "
                "(FINDINGS §44 (e); user 10-17). Pair: p4-premier.",
                rhoa=float(r),
            )
            for r in ("1.2501", "1.2499")
        },
    }
)
# v3's reference pair, re-run on the seeded engine under NEW names (user 10-19), so the
# 10-11 unseeded runs and their rows stay beside them.
_V3.update(
    {
        "p4-ref": replace(
            _V3["bed-v4fixes+wave-dt3600+wind-naccs"],
            name="p4-ref",
            description="bed-v4fixes+wave-dt3600+wind-naccs re-run on the seeded engine "
            "(the v3 reference for Phase 4)." + _P4_WHY,
        ),
        "p4-ref-nowaves": replace(
            _V3["bed-v4fixes+naccs-nowaves+wind-naccs"],
            name="p4-ref-nowaves",
            description="bed-v4fixes+naccs-nowaves+wind-naccs re-run on the seeded engine "
            "(the v3 reference's waves-off twin)." + _P4_WHY,
        ),
    }
)


def reference_arm(arm: str, domain_name: str | None = None) -> str | None:
    """The arm a given arm is paired against: its family's premier.

    A ``p4-`` candidate pairs against ``p4-premier`` (``p4-ref`` on a domain without one);
    every other arm against the domain's ``naccs-premier``. ``None`` where that arm is
    not registered.
    """
    arms = EXPERIMENTS_BY_DOMAIN.get(domain_name or active().name, {})
    if "p4-" in arm:
        ref = "p4-premier" if "p4-premier" in arms else "p4-ref"
    else:
        ref = "naccs-premier"
    return ref if ref in arms else None


def _calm_arm(name: str, description: str, calm: CalmForcing) -> Experiment:
    return replace(
        _V4_REFREEZE["p4-nowaves"],
        name=name,
        description=description,
        subgrid_from="_subgrid_modern2026",
        meteo_from=None,
        rain=False,
        infiltration=False,
        cnb_effective=None,
        calm=calm,
    )


_CALM_T0 = "20121012 000000"
_STILL_TSTOP = "20121013 000000"
#: Mean LMSL -> NAVD88 over the 241 points: where the tide arms start (points_241.csv).
_TIDE_MEAN_OFFSET = -0.082
#: The tidal twin's boundary files (EC2015, logs/modern_bed_2026-10-30/tide/README.md).
_TIDE_DIR = Path("/scratch/tpj8/nj_bight_sfincs_data/modern_2026/derived/tide")
#: The collaborator's comparison (user 10-28 / 29 / 30): waves, wind, rain, rivers off, modern
#: land + beach under the Phase 4 channels and fixes; face z is SnapWave's alone, so the mesh
#: and the domain stay swz's (FINDINGS §63 (a)). Offsets 0.61 / 1.22 m are the 2 ft / 4 ft.
_CALM_ARMS: dict[str, Experiment] = {
    **{
        f"bed-modern+still-{ft}ft": _calm_arm(
            f"bed-modern+still-{ft}ft",
            f"Calm still water at VDatum MHHW + {s} m ({ft} ft): boundary constant, start on "
            "the same sloped surface, connected through the sills and weirs. Nothing holds the "
            "slope up, so it relaxes: read the start or the first zsmax block (nj_sfincs/calm.py).",
            CalmForcing(s, "mhhw", _CALM_T0, _STILL_TSTOP),
        )
        for ft, s in (("2", 0.61), ("4", 1.22))
    },
    **{
        f"bed-modern+tide-{ft}ft": _calm_arm(
            f"bed-modern+tide-{ft}ft",
            f"EC2015 astronomical tide + {s} m ({ft} ft) at the boundary, 10-12 to 11-13 (first "
            "2.5 d spin-up). Unscaled, C&D Canal point as is, rivers off (user 10-30). zsmax in "
            "3 h blocks gives the mean higher-high and the max at every face.",
            CalmForcing(
                s,
                str(_TIDE_DIR / f"sfincs_netbndbzsbzifile_tide_ec2015_{tag}.nc"),
                _CALM_T0,
                "20121113 000000",
                level_m=round(s + _TIDE_MEAN_OFFSET, 3),
                dtmapout=21600.0,
                dtmaxout=10800.0,
            ),
        )
        for ft, s, tag in (("2", 0.61, "p061"), ("4", 1.22, "p122"))
    },
}
#: 2026-11-07: the same four calm arms with the Elizabeth River South + Rahway South Branch
#: levees as weirs, re-tied to the 2026 ground (logs/walls_elizabeth_rahway_modern_2026-11-06/).
#: NEW arms, because the four above are scored runs; each pairs with its namesake without the
#: suffix (one file changed: sfincs.weir). Overpeck dam IN, as in the template's weir.
_CALM_ARMS.update(
    {
        f"{k}+weir-elizabeth-rahway": replace(
            e,
            name=f"{k}+weir-elizabeth-rahway",
            description=e.description
            + " + the Elizabeth / Rahway levees as weirs on 2026 ground (pair: "
            + k
            + ").",
            weir_from=DATA
            / "structures_v4"
            / "sfincs_modern_elizabeth_rahway_ground.weir",
        )
        for k, e in list(_CALM_ARMS.items())
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
    # 2026-10-28 (FINDINGS §63): the Phase 4 premier and its waves-off twin with SnapWave on
    # the flow's bed. Pairs: p4-premier vs v4_refreeze's (the effect); p4-nowaves vs
    # v4_refreeze's must be BIT-IDENTICAL (the flow never reads face z, §63 (a)).
    # 2026-10-29 (user): the premier moved here; the null band and the lake arms re-run on it
    # (their lake answers came from the old wave bed).
    "v4_refreeze_swz": {
        k: _V4_REFREEZE[k]
        for k in (
            "p4-premier",
            "p4-nowaves",
            "p4-premier-repeat",
            "null-rhoa1.2501+p4-premier",
            "null-rhoa1.2499+p4-premier",
            "p4-premier+src-deal-overtop",
            "p4-premier+wave-nowavemaker",
        )
    }
    | {
        # 2026-10-30: the northern Arthur Kill sill test (logs/akn_sill_2026-10-30/), waves-off
        # so a bed swap is complete and the pair against p4-nowaves is well-conditioned.
        "bed-aknsill+p4-nowaves": replace(
            _V4_REFREEZE["p4-nowaves"],
            name="bed-aknsill+p4-nowaves",
            description="p4-nowaves with a Sandy-era channel carved through the northern Arthur "
            "Kill sill (_subgrid_p4_aknsill; akn_sill_sandy_v4, ASSUMED depth). Pair: p4-nowaves.",
            subgrid_from="_subgrid_p4_aknsill",
        ),
        # 2026-11-03: the lower Mullica + the river_drain sills (logs/mullica_bed_2026-11-03/),
        # waves-off: the flow never reads face z, so the 1.0.0 wave bed can stay as it is.
        "bed-hierv4d+p4-nowaves": replace(
            _V4_REFREEZE["p4-nowaves"],
            name="bed-hierv4d+p4-nowaves",
            description="p4-nowaves on the 1.0.0 flow bed with riverbeds_hierarchy_v4d for "
            "v4c: the lower Mullica from NOS 1935 / ENC soundings, and new hierarchy reaches "
            "on the Tuckahoe (lower), Toms, Cedar Ck (Barnegat), Westecunk, Raccoon and Mantua "
            "(most of the last four an ASSUMED sloping section). _subgrid_p4_hierv4d. "
            "Pair: p4-nowaves.",
            subgrid_from="_subgrid_p4_hierv4d",
        ),
        # 2026-11-04: bridge decks out of the bed (logs/decks_2026-11-04/), on the v4d bed,
        # waves-off: the flow never reads face z.
        "bed-decks+bed-hierv4d+p4-nowaves": replace(
            _V4_REFREEZE["p4-nowaves"],
            name="bed-decks+bed-hierv4d+p4-nowaves",
            description="bed-hierv4d+p4-nowaves with deck_fix_v4 painted LAST, lower-only: the "
            "bridge decks and viaducts that lidar put in the bed (529 OSM bridge sites) replaced "
            "by the channel or ground either side, or by CUDEM where the USACE 2010 lidar holds "
            "the deck (an ASSUMED bed). _subgrid_p4_decks. Pair: bed-hierv4d+p4-nowaves (the "
            "decks alone) and p4-nowaves.",
            subgrid_from="_subgrid_p4_decks",
        ),
        # 2026-11-03: developed-land Manning (logs/developed_manning_2026-11-03/): NLCD 22-24
        # IN NJ -> n 0.04 on 1.0.0's exact bed, waves-off (the flow never reads face z).
        "bed-devmanning+p4-nowaves": replace(
            _V4_REFREEZE["p4-nowaves"],
            name="bed-devmanning+p4-nowaves",
            description="p4-nowaves with NLCD developed classes 22-24 in New Jersey at "
            "Manning n 0.04 (manning_developed_v4, painted before manning_water_v4; PA / DE "
            "/ Staten Island keep NLCD n) on Model 1.0.0's flow bed (_subgrid_p4_devmanning; "
            "bed tables bit-identical). Pair: p4-nowaves.",
            subgrid_from="_subgrid_p4_devmanning",
        ),
        # 2026-11-04: v4e = v4d + the Christina's Wilmington plug opened, and the channel-Manning
        # arm on the same bed (logs/tidal_reach_2026-11-04/).
        "bed-hierv4e+p4-nowaves": replace(
            _V4_REFREEZE["p4-nowaves"],
            name="bed-hierv4e+p4-nowaves",
            description="p4-nowaves on the 1.0.0 flow bed with riverbeds_hierarchy_v4e for v4c: v4d + the "
            "Christina's Wilmington plug opened from eHydro CR_02_UPR 2015 + NOS H10042 1982. "
            "_subgrid_p4_hierv4e. Pair: bed-hierv4d+p4-nowaves.",
            subgrid_from="_subgrid_p4_hierv4e",
        ),
        "bed-hierv4e+manchan+p4-nowaves": replace(
            _V4_REFREEZE["p4-nowaves"],
            name="bed-hierv4e+manchan+p4-nowaves",
            description="bed-hierv4e+p4-nowaves with manning_channel_v4e: n 0.02 on every hierarchy-painted channel pixel, "
            "painted after manning_water_v4 (the reach-head channels lose the marsh n 0.03-0.14). Bed tables bit-identical "
            "to _subgrid_p4_hierv4e. _subgrid_p4_hierv4e_manchan. Pair: bed-hierv4e+p4-nowaves; also p4-nowaves.",
            subgrid_from="_subgrid_p4_hierv4e_manchan",
        ),
        # 2026-11-03: the Overpeck tidal dam bracket (logs/ironbound_overpeck_2026-11-03/),
        # waves-off so the pair against p4-nowaves is well-conditioned; one file differs
        # (sfincs.weir, through Experiment.weir_from).
        "p4-nowaves+weir-overpeck-open": replace(
            _V4_REFREEZE["p4-nowaves"],
            name="p4-nowaves+weir-overpeck-open",
            description="p4-nowaves with the Overpeck tidal dam (NID NJ00799) weir line "
            "REMOVED: gates and stoplogs open, the creek meets the Hackensack over the bed's "
            "own lanes (0.44 m on the mesh; 1.57 m as built). Bypass sill, Keansburg system "
            "and the -1.005 m pool start unchanged. Bounds the gates-held assumption from "
            "below. Pair: p4-nowaves.",
            weir_from=DATA / "structures_v4" / "sfincs_overpeck_open.weir",
        ),
        "p4-nowaves+weir-overpeck-high": replace(
            _V4_REFREEZE["p4-nowaves"],
            name="p4-nowaves+weir-overpeck-high",
            description="p4-nowaves with the Overpeck tidal dam crest raised 1.74 -> 3.28 m "
            "(the walkway, 11.75 ft NGVD29 via VDatum): closed to the deck, so Sandy "
            "(2.5-2.6 m outside) never overtops it and the valley fills only over the bypass "
            "sill (1.57 m on the mesh) and by rain. Bounds the dam from above. "
            "Pair: p4-nowaves.",
            weir_from=DATA / "structures_v4" / "sfincs_overpeck_high.weir",
        ),
        # 2026-11-05: Elizabeth River South (RB + LB) + Rahway South Branch RB levees as weirs
        # (logs/walls_elizabeth_rahway_2026-11-05/), on top of Overpeck open; waves-off, one file differs.
        "p4-nowaves+weir-elizabeth-rahway+weir-overpeck-open": replace(
            _V4_REFREEZE["p4-nowaves"],
            name="p4-nowaves+weir-elizabeth-rahway+weir-overpeck-open",
            description="p4-nowaves+weir-overpeck-open plus the USACE Elizabeth River Right / Left Bank South "
            "(NLD 4505000007 / -09) and Rahway River South Branch RB (4505000027) levee + floodwall lines at the NLD "
            "crest (3.0-3.9 m), the 85 m Bayway wall (no NLD height: lidar ground), 3 end tie-ins and 11 ground "
            "guards at the lidar ridge. Gates closed. Pair: p4-nowaves+weir-overpeck-open.",
            weir_from=DATA
            / "structures_v4"
            / "sfincs_overpeck_open_elizabeth_rahway_ground.weir",
        ),
        # 2026-11-01: the first 1.x runs, on the modern bed (logs/modern_bed_2026-11-01/).
        **_CALM_ARMS,
    },
    # 2026-11-06: Model v1.1 (logs/v1_1_premier_2026-11-06/README.md): 1.0.0's premier on the v1.1c
    # flow bed, SnapWave on that bed (the domain's face z comes from _subgrid_v1_1c), the Overpeck
    # dam OPEN (user 11-05), and the Elizabeth / Rahway levees as the second option (pick after the
    # levee pair's read). The domain's own premier is named p4-premier (the same name means a different
    # model on each domain, CLAUDE.md §2). Pair: v4_refreeze_swz's p4-premier (Model 1.0.0).
    "v4_refreeze_swz_v11": {
        "p4-premier": replace(
            _V4_REFREEZE["p4-premier"],
            name="p4-premier",
            description="Model v1.1 candidate: p4-premier on the v1.1c flow bed (_subgrid_v1_1c: "
            "riverbeds v4e, deck_fix_v4b, developed-land n 0.04 in NJ, channel n 0.02, Alloway / "
            "Silver Lake pools, ehydro_fill_v4, nbi_open_v4; Little Egg overlay kept) with SnapWave "
            "on the same bed, and the Overpeck tidal dam weir line REMOVED (Keansburg system and "
            "the bypass sill kept). Pair: v4_refreeze_swz/p4-premier.",
            subgrid_from="_subgrid_v1_1c",
            weir_from=DATA / "structures_v4" / "sfincs_overpeck_open.weir",
        ),
        "p4-premier+weir-elizabeth-rahway": replace(
            _V4_REFREEZE["p4-premier"],
            name="p4-premier+weir-elizabeth-rahway",
            description="This domain's p4-premier (Overpeck open) plus the USACE Elizabeth River Right / Left "
            "Bank South (NLD 4505000007 / -09) and Rahway River South Branch RB (4505000027) "
            "levee + floodwall lines at the NLD crest, the Bayway wall, 3 end tie-ins and 11 "
            "ground guards (logs/walls_elizabeth_rahway_2026-11-05/). Gates closed. "
            "Pair: p4-premier (this domain) and v4_refreeze_swz/p4-premier.",
            subgrid_from="_subgrid_v1_1c",
            weir_from=DATA
            / "structures_v4"
            / "sfincs_overpeck_open_elizabeth_rahway_ground.weir",
        ),
        # 2026-11-06: the v1.2a bed test (logs/relevance_fixes_2026-11-06/): waves-off, Overpeck open, v1.1c
        # bed vs v1.1c + the five relevance-fix overlays. Pair: this domain's p4-nowaves.
        "p4-nowaves": replace(
            _V4_REFREEZE["p4-nowaves"],
            description="Waves-off reference on the v1.1 domain: p4-nowaves on the v1.1c flow bed with the "
            "Overpeck dam open (= this domain's p4-premier without SnapWave).",
            subgrid_from="_subgrid_v1_1c",
            weir_from=DATA / "structures_v4" / "sfincs_overpeck_open.weir",
        ),
        # 2026-11-12: the Gloucester culverts (user eye check 11-09, crests #1 / #13 / #16 of logs/crests_2026-11-09):
        # open highway culverts the bed reads as solid embankments, added as engine culverts (drnfile type 2), no bed
        # edit. Waves-off, paired with this domain's p4-nowaves. logs/culverts_drn_2026-11-12/README.md.
        "p4-nowaves+struct-culverts-gloucester": replace(
            _V4_REFREEZE["p4-nowaves"],
            name="p4-nowaves+struct-culverts-gloucester",
            description="p4-nowaves (this domain) + 7 open culverts as SFINCS drainage structures (type 2, Q = par1 "
            "sqrt(dh), both ways, no sill), NJDOT 0817154 / 0817155 (Little Timber Creek, Moss Branch under US 130), "
            "0820166 (Little Timber Creek under I-295), 0821157 / 0821158 (Still Run under I-295 & US 130 and CR 653), "
            "0821154 / 0821156 (Pargey Creek, London Branch under I-295 & US 130): par1 9-52 m2.5/s from the NJDOT "
            "span, skew, lidar invert and an assumed rise (data/structures_v4/gloucester_culverts_v11.drn). The bed, "
            "mask and weirs are this domain's. Pair: p4-nowaves (this domain).",
            subgrid_from="_subgrid_v1_1c",
            weir_from=DATA / "structures_v4" / "sfincs_overpeck_open.weir",
            drn_from=DATA / "structures_v4" / "gloucester_culverts_v11.drn",
        ),
        "bed-v12a+p4-nowaves": replace(
            _V4_REFREEZE["p4-nowaves"],
            name="bed-v12a+p4-nowaves",
            description="p4-nowaves (this domain) on _subgrid_v1_2a = v1.1c + raritan_mouth_fix_v4, "
            "gmrt_gap_fix_v4, nj36_deck_recut_v4, greategg_plug_fix_v4, barnegat_flat_fix_v4 (all :min; "
            "logs/relevance_fixes_2026-11-06/VERDICTS.md). Pair: p4-nowaves (this domain).",
            subgrid_from="_subgrid_v1_2a",
            weir_from=DATA / "structures_v4" / "sfincs_overpeck_open.weir",
        ),
        # 2026-11-09: the Cape May back-bay tests (logs/capemay_tests_2026-11-09/README.md; the diagnosis is
        # logs/capemay_backbay_2026-11-09/README.md). Test 1, waves-ON: Model 1.1.0 with the SnapWave boundary Hs x 1.3
        # (CORA -> STWAVE at the 8 m line); one input file differs (snapwave.bhs). Pair: p4-premier+weir-elizabeth-rahway.
        "p4-premier+wave-hs130+weir-elizabeth-rahway": replace(
            _V4_REFREEZE["p4-premier"],
            name="p4-premier+wave-hs130+weir-elizabeth-rahway",
            description="Model 1.1.0 (p4-premier+weir-elizabeth-rahway, this domain) with the SnapWave boundary wave "
            "height x 1.3 at all 69 support points (data/waves_v4/cora_waves_v4_hs130.nc: CORA hs x 1.3; Tp, direction, "
            "nodes, times unchanged). Asks whether the Cape May back-bay deficit is the incident waves (SnapWave/STWAVE "
            "0.77 at the 8 m line). A forcing sensitivity, not a candidate. Pair: p4-premier+weir-elizabeth-rahway.",
            waves=replace(
                _P4_WAVES,
                wave_point_dataset=DATA / "waves_v4" / "cora_waves_v4_hs130.nc",
            ),
            subgrid_from="_subgrid_v1_1c",
            weir_from=DATA
            / "structures_v4"
            / "sfincs_overpeck_open_elizabeth_rahway_ground.weir",
        ),
        # Test 3, waves-OFF bed arms on this domain's p4-nowaves (the flow never reads face z, FINDINGS §63 (f)).
        "bed-inlets1m+p4-nowaves": replace(
            _V4_REFREEZE["p4-nowaves"],
            name="bed-inlets1m+p4-nowaves",
            description="p4-nowaves (this domain) on _subgrid_v1_1c_inlets1m = v1.1c + inlets_deepen1m_capemay_v4:min: the "
            "wet bed (< 0 m NAVD88) within 600 m of the Great Egg, Corson, Townsends, Hereford and Cape May Inlet axes "
            "lowered 1 m (an ASSUMED bed: a conveyance sensitivity, not a survey). Pair: p4-nowaves (this domain).",
            subgrid_from="_subgrid_v1_1c_inlets1m",
            weir_from=DATA / "structures_v4" / "sfincs_overpeck_open.weir",
        ),
        "bed-marshnhalf+p4-nowaves": replace(
            _V4_REFREEZE["p4-nowaves"],
            name="bed-marshnhalf+p4-nowaves",
            description="p4-nowaves (this domain) on _subgrid_v1_1c_marshnhalf = v1.1c with manning_marsh_half_capemay_v4 "
            "painted after manning_developed_v4: NLCD 95 marsh in the Cape May County Atlantic back bays at n 0.0225 "
            "(half of 0.045); lake and channel n still win. Bed tables as v1.1c. Pair: p4-nowaves (this domain).",
            subgrid_from="_subgrid_v1_1c_marshnhalf",
            weir_from=DATA / "structures_v4" / "sfincs_overpeck_open.weir",
        ),
        # Test 2: the inlet-setup BRACKET and its zero-lift control (same five lines, set-up 0), waves-OFF.
        # Pairs: bracket vs p4-nowaves (what the lift buys); control vs p4-nowaves (what the lines alone do);
        # bracket vs control (the lift alone).
        "BRACKET+inlet-setup+p4-nowaves": replace(
            _V4_REFREEZE["p4-nowaves"],
            name="BRACKET+inlet-setup+p4-nowaves",
            description="INADMISSIBLE upper bound: p4-nowaves (this domain) + NACCS's bay-minus-offshore lift "
            "(24.84 h mean, >= 0; 0.01-0.54 m, per inlet) imposed across the Great Egg, Corson, Townsends, Hereford "
            "and Cape May Inlet mouths by the engine's wavemaker set-up input (data/inlet_setup_v4/setup, wmfred 1.0). "
            "Pair: p4-nowaves and p4-nowaves+tide-inletlines0 (this domain).",
            subgrid_from="_subgrid_v1_1c",
            weir_from=DATA / "structures_v4" / "sfincs_overpeck_open.weir",
            wavemaker_setup_from=DATA / "inlet_setup_v4" / "setup",
            bracket="inlet-setup",
        ),
        "p4-nowaves+tide-inletlines0": replace(
            _V4_REFREEZE["p4-nowaves"],
            name="p4-nowaves+tide-inletlines0",
            description="Mechanism control for BRACKET+inlet-setup: p4-nowaves (this domain) with the same five "
            "inlet-mouth wavemaker lines at ZERO set-up (data/inlet_setup_v4/setup0): what the lines alone do to the "
            "tide and the crest. Not a candidate. Pair: p4-nowaves (this domain).",
            subgrid_from="_subgrid_v1_1c",
            weir_from=DATA / "structures_v4" / "sfincs_overpeck_open.weir",
            wavemaker_setup_from=DATA / "inlet_setup_v4" / "setup0",
        ),
        # 2026-11-12 (user standing decision 11-09): the rain-OFF twin of Model 1.1.0 is the standard run for MOTF
        # comparisons (MOTF is a surge extent: it contains no rain). Waves on, one flag differs. Pair: 1.1.0.
        "p4-premier+rain-off+weir-elizabeth-rahway": replace(
            _V4_REFREEZE["p4-premier+rain-off"],
            name="p4-premier+rain-off+weir-elizabeth-rahway",
            description="Model 1.1.0 (p4-premier+weir-elizabeth-rahway, this domain) with the rain forcing removed "
            "(netamprfile and the infiltration keys stripped, as v4_refreeze's p4-premier+rain-off): the standard "
            "rain-off twin for MOTF comparisons (user 11-09). Pair: p4-premier+weir-elizabeth-rahway (this domain).",
            subgrid_from="_subgrid_v1_1c",
            weir_from=DATA
            / "structures_v4"
            / "sfincs_overpeck_open_elizabeth_rahway_ground.weir",
        ),
        # 2026-11-12 (user): Keansburg at its 2012 crests (logs/keansburg_breach_2026-11-09/README.md, "Decision
        # 2026-11-12"). Waves-OFF, so the pair is well-conditioned; one file differs (sfincs.weir), and only in 15
        # Keansburg dune vertices (the 2014 beach fill out, the Carr Ave gap open). The waves-off twin of 1.1.0
        # (Elizabeth / Rahway levees in) did not exist on this domain, so it is registered as the pair.
        "p4-nowaves+weir-elizabeth-rahway": replace(
            _V4_REFREEZE["p4-nowaves"],
            name="p4-nowaves+weir-elizabeth-rahway",
            description="Waves-off twin of Model 1.1.0: this domain's p4-nowaves (Overpeck open) plus the "
            "Elizabeth / Rahway levees (the 1.1.0 weir file; 819 engine u/v). Pair: p4-nowaves (this domain) for "
            "the levees; p4-premier+weir-elizabeth-rahway for SnapWave.",
            subgrid_from="_subgrid_v1_1c",
            weir_from=DATA
            / "structures_v4"
            / "sfincs_overpeck_open_elizabeth_rahway_ground.weir",
        ),
        "p4-nowaves+weir-elizabeth-rahway+weir-keansburg-2012crest": replace(
            _V4_REFREEZE["p4-nowaves"],
            name="p4-nowaves+weir-elizabeth-rahway+weir-keansburg-2012crest",
            description="p4-nowaves+weir-elizabeth-rahway (this domain) with the Keansburg bayfront dune at its "
            "2012 crests: 15 weir vertices that the 2014 USACE fill raised > 0.3 m above the 2010 pre-storm lidar "
            "set back to it (the Carr Ave gap K2 4.36-5.22 -> 2.73-4.64 m, 2 at -74.139, 3 on the K3 reach; "
            "data/structures_v4/sfincs_overpeck_open_elizabeth_rahway_keansburg_2012crest.weir, 819 engine u/v). "
            "No Pews Creek tide gate (built 2016-20; in neither the weir nor the bed). "
            "Pair: p4-nowaves+weir-elizabeth-rahway (this domain).",
            subgrid_from="_subgrid_v1_1c",
            weir_from=DATA
            / "structures_v4"
            / "sfincs_overpeck_open_elizabeth_rahway_keansburg_2012crest.weir",
        ),
        # 2026-11-13 (user decisions 11-12, logs/weirs_dikes_levees_2026-11-12/README.md "Pair prepared 11-13"): the
        # Delaware-side NLD levees + diked impoundments as weirs, Pennsauken skipped, Hancocks Bridge left open, the
        # Cohansey (Bacons Neck Rd) tide gate SHUT + a type-3 check valve. Waves-OFF, so the pair is well-conditioned;
        # two files differ (sfincs.weir: 1.1.0's lines + 25 appended polylines; + sfincs.drn). Engine u/v 3571.
        "p4-nowaves+struct-cohansey-checkvalve+weir-dikes-levees+weir-elizabeth-rahway": replace(
            _V4_REFREEZE["p4-nowaves"],
            name="p4-nowaves+struct-cohansey-checkvalve+weir-dikes-levees+weir-elizabeth-rahway",
            description="p4-nowaves+weir-elizabeth-rahway (this domain) plus, appended to the 1.1.0 weir file: the "
            "Rohm & Haas (NLD 1305000013), Chester (4805000005) and Henby Creek (1205000139 / -140) levees at the "
            "NLD crest; 20 diked-impoundment lines (Forsythe West Pool, Tuckahoe WMA x2, 9 Delaware-bayshore "
            "over-reach outlines at the r 60 m lidar ridge, 8 agri NLD / NWI alignments); and the Cohansey gate = "
            "the Bacons Neck Rd levee (NLD 1205000177) SHUT at its NLD 1.80 m across the tide-gate opening the "
            "lidar reads as open water (data/structures_v4/sfincs_overpeck_open_elizabeth_rahway_dikes_levees_"
            "cohansey_ground.weir, 3571 engine u/v). Drainage: the Cohansey gate as a type-3 check valve, Pine "
            "Mount meadow -> Cohansey side, Q = 6.2 sqrt(dh) (ASSUMED 2 x 48 in pipes; "
            "data/structures_v4/cohansey_bacons_neck_gate_checkvalve.drn). Pennsauken skipped, Hancocks Bridge "
            "open. Pair: p4-nowaves+weir-elizabeth-rahway (this domain).",
            subgrid_from="_subgrid_v1_1c",
            weir_from=DATA
            / "structures_v4"
            / "sfincs_overpeck_open_elizabeth_rahway_dikes_levees_cohansey_ground.weir",
            drn_from=DATA
            / "structures_v4"
            / "cohansey_bacons_neck_gate_checkvalve.drn",
        ),
    },
    # The breach arms, each on a domain whose face z comes from its own breach bed.
    "v4_refreeze_swz_wk0": {
        k: _V4_REFREEZE[k] for k in ("bed-breach-wreck0+p4-premier",)
    },
    "v4_refreeze_swz_wk165": {
        k: _V4_REFREEZE[k] for k in ("bed-breach-wreck165+p4-premier",)
    },
    # 2026-10-30 (user): buildings in the waves, measured. SnapWave on bare ground; p4-premier
    # keeps buildings in the flow (pair: v4_refreeze_swz's p4-premier = buildings in the waves),
    # bed-nobuildings drops them from the flow too (pair: this domain's p4-premier).
    "v4_refreeze_swz_bare": {
        k: _V4_REFREEZE[k] for k in ("p4-premier", "bed-nobuildings+p4-premier")
    },
    # nj2 (Model 2.0, 2026-11-14): the MESH domain, building then frozen — no arms (they live on
    # nj2_bed2012 / nj2_bed2026 after the freeze; logs/nj2_freeze_2026-11-14/README.md).
    "nj2": {},
}


# 2026-11-12 (user decisions 11-12; poster 11-13): Sandy on the 2026 bed ("if Sandy happened today"), Model 1.1.0's
# twin. Model 1.1.0 (this domain's p4-premier+weir-elizabeth-rahway: waves on, rain on, Overpeck dam open, SnapWave on
# the v1.1c wave bed) with only the ground and today's structures changed: the modern b bed (_subgrid_modern2026b,
# built from v1.1c's base tiers with v1.1c's fixes, user-approved + audited 11-06, logs/modern_bed_b_2026-11-06/;
# hard-linked here with this domain's sfincs.nc, so face z = 1.1.0's wave bed), the Elizabeth / Rahway levees re-tied to
# 2026 ground, Port Monmouth as built by 2026 with the Pews Creek tide gate SHUT (logs/portmonmouth_2026bed_2026-11-12/,
# variant b) and a type-3 check valve through it, marsh -> bay (variant c), the Overpeck dam OPEN as in 1.1.0.
# ADDITIVE: no existing arm changes. Engine weir u/v 864 (float32 rule; reports/poster_2026-11-13/weircount/).
EXPERIMENTS_BY_DOMAIN["v4_refreeze_swz_v11"][
    "bed-modernb+p4-premier+struct-pews-checkvalve+weir-elizabeth-rahway+weir-portmonmouth"
] = replace(
    EXPERIMENTS_BY_DOMAIN["v4_refreeze_swz_v11"]["p4-premier+weir-elizabeth-rahway"],
    name="bed-modernb+p4-premier+struct-pews-checkvalve+weir-elizabeth-rahway+weir-portmonmouth",
    description="Sandy on the 2026 bed, PRELIMINARY (an unvalidated bed): Model 1.1.0 (p4-premier+weir-elizabeth-"
    "rahway, this domain: 2012 storm and sea level, waves + rain on, Overpeck dam open, SnapWave on the v1.1c wave "
    "bed) on _subgrid_modern2026b (2026 topo / bathy; buildings and land cover still 2012's; "
    "logs/modern_bed_b_2026-11-06/README.md). Weirs: the Elizabeth / Rahway levees on 2026 ground, the Overpeck "
    "tidal dam line removed, + the Port Monmouth C2 / C3 lines with the Pews Creek tide gate and the Old Port "
    "Monmouth Rd gate SHUT (data/structures_v4/sfincs_modern_overpeck_open_elizabeth_rahway_portmonmouth_ground.weir, "
    "864 engine u/v); drainage: the Pews gate as a type-3 check valve, marsh -> bay, Q = 100.4 sqrt(dh) "
    "(data/structures_v4/portmonmouth_pews_gate_checkvalve.drn; logs/portmonmouth_2026bed_2026-11-12/README.md, "
    "decision 11-12). Pair: p4-premier+weir-elizabeth-rahway (Model 1.1.0, this domain).",
    subgrid_from="_subgrid_modern2026b",
    weir_from=DATA
    / "structures_v4"
    / "sfincs_modern_overpeck_open_elizabeth_rahway_portmonmouth_ground.weir",
    drn_from=DATA / "structures_v4" / "portmonmouth_pews_gate_checkvalve.drn",
)


# 2026-11-12 (user decisions 11-12): the NORMAL-WEATHER calm arms on Model 1.1.0's domain = the re-issue of the
# MHHW + 2 / + 4 ft maps for the climate hazard team, plus the +0 ft tide twins (STATUS backlog "+0 ft tidal twin:
# v1.1 bed + modern b, paired"). Normal weather = closures OPEN (logs/portmonmouth_2026bed_2026-11-12/README.md and
# logs/waackaack_gate_check_2026-11-12/README.md, "Decision"): the Waackaack navigation gate open (segments 13-16
# removed), the Pews Creek stop logs out (1.77 m trail floor), the Port Monmouth tide gate + road gate open (weir (a)),
# the 8 Elizabeth / Rahway NLD closures open (crest lowered to the lidar ground under each), and the Overpeck tidal dam
# SHUT (crest 1.74 m; user 11-12: a normally-shut tide barrier; storm runs keep 1.1.0's removal). One weir file for
# all seven: data/structures_v4/sfincs_modern_normalweather_ground.weir
# (logs/mhhw_v2_2026-11-12/build_weir.py; engine u/v in logs/mhhw_v2_2026-11-12/README.md). Same recipe as the
# 11-01 calm arms (_calm_arm: waves, wind, rain, rivers off; CalmForcing) but on THIS domain's waves-off arm
# (p4-nowaves: the v1.1c flow bed, face z = 1.1.0's wave bed, unused waves-off). The still arms are STAGE-ONLY: the
# still map is read off the connected start (user 11-02), never solved. ADDITIVE: no existing arm changes.
_NW_WEIR = DATA / "structures_v4" / "sfincs_modern_normalweather_ground.weir"
_NW_WHY = (
    " Normal weather, closures OPEN (user 11-12; logs/portmonmouth_2026bed_2026-11-12/README.md + "
    "logs/waackaack_gate_check_2026-11-12/README.md, 'Decision'): Waackaack gate open, Pews stop logs out, Port "
    "Monmouth tide + road gates open, the 8 Elizabeth / Rahway closures open, the Overpeck tidal dam SHUT (a "
    "normally-shut tide barrier; 1.1.0 removes it for storms); weir data/structures_v4/sfincs_modern_normalweather_"
    "ground.weir (logs/mhhw_v2_2026-11-12/README.md)."
)


def _nw_calm_arm(name: str, description: str, calm: CalmForcing, subgrid_from: str) -> Experiment:
    return replace(
        EXPERIMENTS_BY_DOMAIN["v4_refreeze_swz_v11"]["p4-nowaves"],
        name=name,
        description=description + _NW_WHY,
        subgrid_from=subgrid_from,
        weir_from=_NW_WEIR,
        meteo_from=None,
        rain=False,
        infiltration=False,
        cnb_effective=None,
        calm=calm,
    )


def _nw_tide(offset_m: float, tag: str) -> CalmForcing:
    return CalmForcing(
        offset_m,
        str(_TIDE_DIR / f"sfincs_netbndbzsbzifile_tide_ec2015_{tag}.nc"),
        _CALM_T0,
        "20121113 000000",
        level_m=round(offset_m + _TIDE_MEAN_OFFSET, 3),
        dtmapout=21600.0,
        dtmaxout=10800.0,
    )


EXPERIMENTS_BY_DOMAIN["v4_refreeze_swz_v11"].update(
    {
        **{
            f"bed-modernb+still-{ft}ft+weir-normalweather": _nw_calm_arm(
                f"bed-modernb+still-{ft}ft+weir-normalweather",
                f"Calm still water at VDatum MHHW + {s} m ({ft} ft) on the 2026 bed (_subgrid_modern2026b, "
                "logs/modern_bed_b_2026-11-06/README.md), Model 1.1.0's domain: boundary constant, start on the same "
                "sloped surface connected through the sills and weirs. STAGE ONLY: the map is the start "
                "(nj_sfincs/calm.py). Re-issue of v4_refreeze_swz/bed-modern+still-" + ft + "ft (the 11-04 maps; "
                "different domain, bed and weir: not a one-file pair).",
                CalmForcing(s, "mhhw", _CALM_T0, _STILL_TSTOP),
                "_subgrid_modern2026b",
            )
            for ft, s in (("2", 0.61), ("4", 1.22))
        },
        **{
            f"bed-modernb+tide-{ft}ft+weir-normalweather": _nw_calm_arm(
                f"bed-modernb+tide-{ft}ft+weir-normalweather",
                f"EC2015 astronomical tide + {s} m ({ft} ft) at the boundary on the 2026 bed (_subgrid_modern2026b), "
                "Model 1.1.0's domain, 10-12 to 11-13 (first 2.5 d spin-up; logs/modern_bed_2026-10-30/tide/"
                "README.md). zsmax in 3 h blocks -> mean higher-high + month max. Re-issue of v4_refreeze_swz/"
                "bed-modern+tide-" + ft + "ft (the 11-04 maps). Pair (same bed, offset only): "
                "bed-modernb+tide-0ft+weir-normalweather.",
                _nw_tide(s, tag),
                "_subgrid_modern2026b",
            )
            for ft, s, tag in (("2", 0.61, "p061"), ("4", 1.22, "p122"))
        },
        "bed-modernb+tide-0ft+weir-normalweather": _nw_calm_arm(
            "bed-modernb+tide-0ft+weir-normalweather",
            "+0 ft tide twin on the 2026 bed (_subgrid_modern2026b): EC2015 astronomical tide at the boundary on "
            "the NTDE 1983-2001 sea level (VDatum LMSL->NAVD88, the datum the + 2 / + 4 ft arms add to; no "
            "sea-level trend), 10-12 to 11-13, first 2.5 d spin-up (boundary file p000 = p061 - 0.61, "
            "logs/mhhw_v2_2026-11-12/make_tide_p000.py). Pair (one file changed: the subgrid): "
            "p4-nowaves+tide-0ft+weir-normalweather (1.1.0's v1.1c bed); and bed-modernb+tide-0ft-msl2026+weir-normalweather "
            "(the same at 2026 mean sea level).",
            _nw_tide(0.0, "p000"),
            "_subgrid_modern2026b",
        ),
        "p4-nowaves+tide-0ft+weir-normalweather": _nw_calm_arm(
            "p4-nowaves+tide-0ft+weir-normalweather",
            "+0 ft tide twin on Model 1.1.0's own bed (_subgrid_v1_1c): EC2015 astronomical tide at the boundary on "
            "the NTDE 1983-2001 sea level, 10-12 to 11-13, first 2.5 d spin-up (p000, as its pair). Today's "
            "structures on 2012 ground, so the pair isolates the bed. Pair (one file changed: the subgrid): "
            "bed-modernb+tide-0ft+weir-normalweather.",
            _nw_tide(0.0, "p000"),
            "_subgrid_v1_1c",
        ),
        # 2026-11-12 (user): the +0 ft twin at 2026 MEAN SEA LEVEL as well: p000 + the 1992 -> 2026 rise (34 yr x the
        # NOAA CO-OPS trend of the nearest boundary gauge, per point: +0.100 ... +0.174 m, mean 0.148;
        # logs/mhhw_v2_2026-11-12/make_tide_msl2026.py, msl2026_points.csv).
        "bed-modernb+tide-0ft-msl2026+weir-normalweather": _nw_calm_arm(
            "bed-modernb+tide-0ft-msl2026+weir-normalweather",
            "+0 ft tide twin on the 2026 bed at 2026 MEAN SEA LEVEL: EC2015 astronomical tide + VDatum LMSL->NAVD88 "
            "(NTDE 1983-2001, midpoint 1992) + the relative sea-level rise 1992 -> 2026 at each boundary point "
            "(34 yr x the NOAA CO-OPS linear trend of the nearest of Lewes, Cape May, Atlantic City, Sandy Hook, the "
            "Battery and Bergen Point (Kill van Kull arm only): +0.100 ... +0.174 m, mean 0.148 m; boundary file "
            "p000_msl2026, logs/mhhw_v2_2026-11-12/make_tide_msl2026.py), 10-12 to 11-13, first 2.5 d spin-up. "
            "Pair (one file changed: the boundary, + its start level): bed-modernb+tide-0ft+weir-normalweather.",
            _nw_tide(0.148, "p000_msl2026"),
            "_subgrid_modern2026b",
        ),
    }
)


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
