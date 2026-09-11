"""SnapWave parameter reference — data only, no imports beyond the stdlib.

Three tables, each keyed by the ``sfincs.inp`` keyword:

``ENGINE_DEFAULTS_V233``
    What SFINCS v2.3.3 (tag ``091f531a``, our container engine) uses when the key is
    ABSENT from ``sfincs.inp``. Transcribed 2026-09-10/11 from
    ``source/src/sfincs_snapwave.f90::read_snapwave_input`` (lines 614–680) and
    ``source/src/sfincs_input.f90`` (``dtwave`` 67, ``snapwave`` 113,
    ``wave_enhanced_roughness`` 197, ``storefw``/``storewavdir`` 292–293,
    ``snapwave_use_nearest`` 296, ``snapwave_wind`` 302,
    ``snapwave_waveforces_factor`` 303). ⚠️ Two engine defaults are NOT what this repo
    has always written: ``snapwave_fw`` is **0.01** (we wrote 0.02 on every arm to
    2026-09-10) and ``snapwave_igwaves`` is **1** (we write 0 explicitly).

``HYDROMT_DEFAULTS``
    What ``hydromt_sfincs`` (``components/config/config_variables.py``) writes into the
    inp on its own. Only seven SnapWave keys are in hydromt's schema at all —
    ``snapwave_alpha / gamma / fw / niter / sector / hmin`` reach the inp ONLY through
    ``model.finalize``'s raw-text append (``nj_sfincs/model.py``, the ``sw_keys`` block).

``MEANINGS``
    One line per key, quoting the engine form where there is one. The formulas are the
    v2.3.3 source (``snapwave_solver.f90``, ``snapwave_windsource.f90``,
    ``snapwave_boundaries.f90``), not the manual.

🔴 The wind-direction caveat (FINDINGS §43): on v2.3.3–v2.4.1 with ``snapwave_wind = 1``
the boundary spectrum is launched in the domain-mean WIND direction, not the imposed
``.bwd`` direction. ``scripts/snapwave_parameters.py`` prints it whenever a run has wind on
and its ``sfincs.log`` Build-Revision lacks the ``nj-winddir-fix`` tag.
"""

from __future__ import annotations

import math

_TWO_PI = 2.0 * math.pi

#: (keyword, engine default). Order = print order. Groups are marked by ``GROUPS``.
ENGINE_DEFAULTS_V233: dict[str, object] = {
    # ── switches ──────────────────────────────────────────────────────────────
    "snapwave": 0,
    "snapwave_wind": 0,
    "snapwave_igwaves": 1,
    "dtwave": 3600.0,
    "snapwave_use_nearest": True,
    "snapwave_waveforces_factor": 1.0,
    "wave_enhanced_roughness": False,
    "vegetation": 0,
    # ── breaking + friction ───────────────────────────────────────────────────
    "snapwave_gamma": 0.7,
    "snapwave_gammax": 2.0,
    "snapwave_alpha": 1.0,
    "snapwave_baldock_opt": 1,
    "snapwave_baldock_ratio": 0.2,
    "snapwave_fw": 0.01,
    "snapwave_fw_ratio": 1.0,
    "snapwave_hmin": 0.1,
    # ── directional grid + solver ─────────────────────────────────────────────
    "snapwave_dtheta": 10.0,
    "snapwave_sector": 180.0,
    "snapwave_niter": 10,
    "snapwave_nrsweeps": 4,
    "snapwave_crit": 0.001,
    "snapwave_dt": 36000.0,
    "snapwave_tol": 1000.0,
    "snapwave_Tpini": 1.0,
    "snapwave_jadcgdx": 1,
    "snapwave_c_dispT": 1.0,
    # ── wind growth ───────────────────────────────────────────────────────────
    "snapwave_mwind": 2,
    "snapwave_sigmin": _TWO_PI / 25.0,
    "snapwave_sigmax": _TWO_PI / 1.0,
    # ── infragravity ──────────────────────────────────────────────────────────
    "snapwave_alpha_ig": 1.0,
    "snapwave_gammaig": 0.2,
    "snapwave_fwig": 0.015,
    "snapwave_fwig_ratio": 1.0,
    "snapwave_baldock_ratio_ig": 0.2,
    "snapwave_shinc2ig": 1.0,
    "snapwave_alphaigfac": 1.0,
    "snapwave_ig_opt": 1,
    "snapwave_iterative_srcig": 0,
    "snapwave_use_herbers": 1,
    "snapwave_tpig_opt": 1,
    "snapwave_jonswapgamma": 3.3,
    "snapwave_eeinc2ig": 0.01,
    "snapwave_Tinc2ig": 7.0,
    # ── output ────────────────────────────────────────────────────────────────
    "storefw": 0,
    "storewavdir": 0,
    # ── files ─────────────────────────────────────────────────────────────────
    "snapwave_bndfile": "none",
    "snapwave_bhsfile": "none",
    "snapwave_btpfile": "none",
    "snapwave_bwdfile": "none",
    "snapwave_bdsfile": "none",
    "snapwave_upwfile": "snapwave.upw",
}

#: Print groups: (title, first key). A key belongs to the last group started before it.
GROUPS: list[tuple[str, str]] = [
    ("Switches and coupling", "snapwave"),
    ("Breaking and bottom friction", "snapwave_gamma"),
    ("Directional grid and solver", "snapwave_dtheta"),
    ("Wind growth", "snapwave_mwind"),
    ("Infragravity waves", "snapwave_alpha_ig"),
    ("Output", "storefw"),
    ("Boundary files", "snapwave_bndfile"),
]

#: What hydromt_sfincs writes on its own (config_variables.py). Everything else in
#: ENGINE_DEFAULTS_V233 is absent from hydromt's schema.
HYDROMT_DEFAULTS: dict[str, object] = {
    "snapwave": 0,
    "snapwave_wind": 0,
    "snapwave_use_nearest": 1,
    "snapwave_igwaves": 1,
    "snapwave_dtheta": 10.0,
    "snapwave_nrsweeps": 4,
    "snapwave_crit": 0.001,
    "snapwave_hmin": 0.1,
    "dtwave": 3600.0,
    "wave_enhanced_roughness": 0,
}

#: Keys this repo can only set through ``model.finalize``'s raw-text append.
RAW_APPEND_ONLY = (
    "snapwave_alpha",
    "snapwave_gamma",
    "snapwave_fw",
    "snapwave_niter",
    "snapwave_sector",
    "storefw",
    "storewavdir",
)

MEANINGS: dict[str, str] = {
    "snapwave": "master switch: 1 couples the SnapWave stationary wave solver to SFINCS",
    "snapwave_wind": "1 = local wind-wave growth (Kahma–Calkoen) on the model wind. "
    "🔴 v2.3.3–v2.4.1: also rotates the IMPOSED boundary spectrum to "
    "the domain-mean wind direction (FINDINGS §43)",
    "snapwave_igwaves": "1 = solve the infragravity (IG) energy balance beside the incident",
    "dtwave": "coupling interval [s]: SnapWave is re-solved every dtwave of SFINCS time",
    "snapwave_use_nearest": "water level / wind at wave nodes by nearest SFINCS cell",
    "snapwave_waveforces_factor": "multiplier on the wave force handed to SFINCS",
    "wave_enhanced_roughness": "let the wave orbital velocity raise SFINCS bed roughness",
    "vegetation": "vegetation dissipation switch (0 = off)",
    "snapwave_gamma": "Baldock breaking: Hmax = γ·h (baldock_opt 1); larger γ = later "
    "breaking",
    "snapwave_gammax": "depth cap on the energy: E /= max(1, (H/(γmax·h))²)",
    "snapwave_alpha": "Baldock dissipation scale: Dw = 0.28·α·ρ·g/T·exp(−(Hmax/H)²)"
    "·(Hmax²+H²)",
    "snapwave_baldock_opt": "1 = the (Hmax²+H²) Baldock form above; 2 = the "
    "(Hmax³+H³)/(γ·h) form",
    "snapwave_baldock_ratio": "breaking is applied only where H > ratio·Hmax",
    "snapwave_fw": "bottom-friction factor: Df = 0.28·ρ·fw·u_orb³, u_orb = ½·σ·H/sinh(kh); "
    "always on; there is no whitecapping term",
    "snapwave_fw_ratio": "multiplier on fw where a spatially varying fw file is used",
    "snapwave_hmin": "minimum water depth [m] at which a wave node is solved",
    "snapwave_dtheta": "directional bin width [deg]; the grid has sector/dtheta bins",
    "snapwave_sector": "directional sector [deg] centred on the mean direction; 360 = "
    "full circle. < 360 clips energy > sector/2 from the centre "
    "(0.999·π/2 test)",
    "snapwave_niter": "maximum sweeps; convergence is tested every 4th sweep, so the log "
    "counts niter/4 'iterations'",
    "snapwave_nrsweeps": "sweeps per convergence test (the log's one 'iteration')",
    "snapwave_crit": "convergence: max|ΔE|/Emax < crit over all nodes",
    "snapwave_dt": "internal pseudo-time step [s] of the stationary iteration",
    "snapwave_tol": "solver tolerance parameter (unused in the sweeping scheme)",
    "snapwave_Tpini": "initial-guess peak period [s] before the first solve",
    "snapwave_jadcgdx": "1 = include the ∂cg/∂x term in the energy transport",
    "snapwave_c_dispT": "scale on the dispersion-relation period",
    "snapwave_mwind": "cos^mwind directional spreading of the wind source about the wind",
    "snapwave_sigmin": "lower clamp on the wind-sea radian frequency σ = E/A [rad/s] "
    "(2π/25 s)",
    "snapwave_sigmax": "upper clamp on σ [rad/s] (2π/1 s); growth stops at the "
    "Pierson–Moskowitz state (E_ful 0.0036, T_ful 7.69)",
    "snapwave_alpha_ig": "Baldock α for the IG balance",
    "snapwave_gammaig": "Baldock γ for the IG balance (Hmax_ig = γ_ig·h)",
    "snapwave_fwig": "bottom-friction factor for the IG waves",
    "snapwave_fwig_ratio": "multiplier on fwig where a varying file is used",
    "snapwave_baldock_ratio_ig": "IG breaking applied only where H_ig > ratio·Hmax_ig",
    "snapwave_shinc2ig": "fraction of the IG source subtracted from the incident energy",
    "snapwave_alphaigfac": "multiplier on the IG shoaling source (∝ ∂Sxx)",
    "snapwave_ig_opt": "1 = conservative shoaling source from dSxx (Leijnse et al. 2024)",
    "snapwave_iterative_srcig": "1 = IG source inside the iteration; 0 = from the previous "
    "call",
    "snapwave_use_herbers": "1 = bound-long-wave IG boundary from Herbers on a JONSWAP "
    "spectrum",
    "snapwave_tpig_opt": "IG period from the Herbers spectrum: 1 Tm01, 2 Tp smooth, 3 Tp, "
    "4 Tm−1,0",
    "snapwave_jonswapgamma": "JONSWAP peak enhancement for the Herbers spectrum",
    "snapwave_eeinc2ig": "IG/incident energy ratio at the boundary when use_herbers = 0",
    "snapwave_Tinc2ig": "IG period [s] at the boundary when use_herbers = 0",
    "storefw": "1 = write the wave forces fwx/fwy (and snapwavedepth) to the map",
    "storewavdir": "1 = write the mean wave direction wavdir to the map",
    "snapwave_bndfile": "support-point coordinates (x y per line)",
    "snapwave_bhsfile": "Hs per support point per time",
    "snapwave_btpfile": "Tp per support point per time",
    "snapwave_bwdfile": "mean direction (nautical, from) per support point per time",
    "snapwave_bdsfile": "directional spread per support point per time",
    "snapwave_upwfile": "the solver's upwind-neighbour cache; regenerated when absent",
}

#: The Build-Revision tag the patched native engine carries (Phase 2 of the 09-10 plan).
WINDDIR_FIX_TAG = "nj-winddir-fix"


def has_direction_bug(inp: dict, build_revision: str | None) -> bool:
    """True when this run launched its boundary waves in the WIND direction.

    ``inp`` is ``provenance.read_inp``'s dict; ``build_revision`` the SFINCS
    ``Build-Revision`` log line (``None`` = unknown → assume the unpatched engine).
    """
    if str(inp.get("snapwave", "0")).strip() != "1":
        return False
    if str(inp.get("snapwave_wind", "0")).strip() != "1":
        return False
    return WINDDIR_FIX_TAG not in (build_revision or "")
