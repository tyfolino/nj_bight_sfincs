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
    use_waves=True, wave_wind=True, wave_igwaves=False, tune_physics=True,
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
_V3: dict[str, Experiment] = {
    "naccs-premier": Experiment(
        "naccs-premier",
        WaveConfig(use_waves=True, wave_wind=True, wave_igwaves=False, tune_physics=True,
                   wave_point_dataset=_V3_CORA, wave_n_support=_V3_WAVE_N),
        "THE v3 PREMIER: NACCS/CHS ADCIRC storm tide on v1.5's three cuts plus the "
        "isobath to Cape May and the Delaware Bay wedge, with CORA per-support-point "
        "waves (v1.5's premier wave config verbatim). Every back bay from Raritan Bay to "
        "Cape May Harbor is COMPUTED.",
        **_V3_WL,
    ),
    "wave-stwave": Experiment(
        "wave-stwave",
        WaveConfig(use_waves=True, wave_wind=True, wave_igwaves=False, tune_physics=True,
                   wave_point_dataset=_V3_STWAVE, wave_n_support=_V3_WAVE_N),
        "Premier with the wave boundary from NACCS's OWN STWAVE save points instead of "
        "CORA — the same CSTORM-MS system that produced the water level, so the waves "
        "and the surge are internally consistent. ⚠️ STWAVE's `alpham` is read as a "
        "nautical FROM direction by inference, not documentation "
        "(scripts/build_naccs_stwave_waves.py).",
        **_V3_WL,
    ),
    "naccs-nowaves": Experiment(
        "naccs-nowaves",
        WaveConfig(use_waves=False),
        "Premier with SnapWave OFF. Extent metrics flagged extent_admissible=False, "
        "never ranked against a waves-on arm (CLAUDE.md §6).",
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
