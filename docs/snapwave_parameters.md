# SnapWave parameters — GENERATED, do not hand-edit

Generated 2026-09-11 by `scripts/snapwave_parameters.py` from the run dirs below. Regenerate after every change of premier. Engine defaults are SFINCS v2.3.3 (`sfincs_snapwave.f90::read_snapwave_input`); hydromt defaults are `hydromt_sfincs/components/config/config_variables.py`. Keys marked ⚙ reach the inp only through `model.finalize`'s raw-text append (not in hydromt's schema).

| run | engine | support points | wind | direction |
|---|---|---|---|---|
| `naccs-premier` | container v2.3.3 [$Rev: v2.3.3 mt. Faber+] (inferred from sfincs.log) | 36 | 1 | 🔴 WIND (misdirected) |
| `wave-shelf-steps` | container v2.3.3 [$Rev: v2.3.3 mt. Faber+] (inferred from sfincs.log) | 60 | 1 | 🔴 WIND (misdirected) |
| `wave-nowind+wave-shelf-steps` | container v2.3.3 [$Rev: v2.3.3 mt. Faber+] (inferred from sfincs.log) | 60 | 0 | imposed |
| `naccs-nowaves` | container v2.3.3 [$Rev: v2.3.3 mt. Faber+] (inferred from sfincs.log) | — | (off) | n/a |

🔴 **naccs-premier: snapwave_wind = 1 on engine [$Rev: v2.3.3 mt. Faber+] — the boundary waves were launched in the domain-mean WIND direction, not the imposed .bwd direction (FINDINGS §43). Its wave numbers describe misdirected waves.**

🔴 **wave-shelf-steps: snapwave_wind = 1 on engine [$Rev: v2.3.3 mt. Faber+] — the boundary waves were launched in the domain-mean WIND direction, not the imposed .bwd direction (FINDINGS §43). Its wave numbers describe misdirected waves.**

`≠` = differs from the engine default; `*` = key absent from the inp, engine default applied.

## What we changed from the engine defaults

| key | `naccs-premier` | `wave-shelf-steps` | `wave-nowind+wave-shelf-steps` | `naccs-nowaves` | engine default | meaning |
|---|---|---|---|---|---|---|
| `snapwave_wind` | `≠ 1` | `≠ 1` | `0` | `(off)` | `0` | 1 = local wind-wave growth (Kahma–Calkoen) on the model wind. 🔴 v2.3.3–v2.4.1: also rotates the IMPOSED boundary spectrum to the domain-mean wind direction (FINDINGS §43) |
| `snapwave_igwaves` | `≠ 0` | `≠ 0` | `≠ 0` | `(off)` | `1` | 1 = solve the infragravity (IG) energy balance beside the incident |
| `dtwave` | `≠ 1800.0` | `≠ 1800.0` | `≠ 1800.0` | `(off)` | `3600` | coupling interval [s]: SnapWave is re-solved every dtwave of SFINCS time |
| `snapwave_gamma` ⚙ | `≠ 0.78` | `≠ 0.78` | `≠ 0.78` | `(off)` | `0.7` | Baldock breaking: Hmax = γ·h (baldock_opt 1); larger γ = later breaking |
| `snapwave_fw` ⚙ | `≠ 0.02` | `≠ 0.02` | `≠ 0.02` | `(off)` | `0.01` | bottom-friction factor: Df = 0.28·ρ·fw·u_orb³, u_orb = ½·σ·H/sinh(kh); always on; there is no whitecapping term |
| `snapwave_hmin` | `≠ 0.01` | `≠ 0.01` | `≠ 0.01` | `(off)` | `0.1` | minimum water depth [m] at which a wave node is solved |
| `snapwave_dtheta` | `≠ 5.0` | `≠ 5.0` | `≠ 5.0` | `(off)` | `10` | directional bin width [deg]; the grid has sector/dtheta bins |
| `snapwave_sector` ⚙ | `≠ 360` | `≠ 360` | `≠ 360` | `(off)` | `180` | directional sector [deg] centred on the mean direction; 360 = full circle. < 360 clips energy > sector/2 from the centre (0.999·π/2 test) |
| `snapwave_niter` ⚙ | `≠ 100` | `≠ 200` | `≠ 200` | `(off)` | `10` | maximum sweeps; convergence is tested every 4th sweep, so the log counts niter/4 'iterations' |
| `storefw` ⚙ | `≠ 1` | `≠ 1` | `≠ 1` | `(off)` | `0` | 1 = write the wave forces fwx/fwy (and snapwavedepth) to the map |
| `storewavdir` ⚙ | `≠ 1` | `≠ 1` | `≠ 1` | `(off)` | `0` | 1 = write the mean wave direction wavdir to the map |

## Every key

### Switches and coupling

| key | `naccs-premier` | `wave-shelf-steps` | `wave-nowind+wave-shelf-steps` | `naccs-nowaves` | engine | hydromt | meaning |
|---|---|---|---|---|---|---|---|
| `snapwave` | `≠ 1` | `≠ 1` | `≠ 1` | `0` | `0` | 0 | master switch: 1 couples the SnapWave stationary wave solver to SFINCS |
| `snapwave_wind` | `≠ 1` | `≠ 1` | `0` | `(off)` | `0` | 0 | 1 = local wind-wave growth (Kahma–Calkoen) on the model wind. 🔴 v2.3.3–v2.4.1: also rotates the IMPOSED boundary spectrum to the domain-mean wind direction (FINDINGS §43) |
| `snapwave_igwaves` | `≠ 0` | `≠ 0` | `≠ 0` | `(off)` | `1` | 1 | 1 = solve the infragravity (IG) energy balance beside the incident |
| `dtwave` | `≠ 1800.0` | `≠ 1800.0` | `≠ 1800.0` | `(off)` | `3600` | 3600 | coupling interval [s]: SnapWave is re-solved every dtwave of SFINCS time |
| `snapwave_use_nearest` | `.true. *` | `.true. *` | `.true. *` | `(off)` | `.true.` | 1 | water level / wind at wave nodes by nearest SFINCS cell |
| `snapwave_waveforces_factor` | `1 *` | `1 *` | `1 *` | `(off)` | `1` | — | multiplier on the wave force handed to SFINCS |
| `wave_enhanced_roughness` | `.false. *` | `.false. *` | `.false. *` | `(off)` | `.false.` | 0 | let the wave orbital velocity raise SFINCS bed roughness |
| `vegetation` | `0 *` | `0 *` | `0 *` | `(off)` | `0` | — | vegetation dissipation switch (0 = off) |

### Breaking and bottom friction

| key | `naccs-premier` | `wave-shelf-steps` | `wave-nowind+wave-shelf-steps` | `naccs-nowaves` | engine | hydromt | meaning |
|---|---|---|---|---|---|---|---|
| `snapwave_gamma` ⚙ | `≠ 0.78` | `≠ 0.78` | `≠ 0.78` | `(off)` | `0.7` | — | Baldock breaking: Hmax = γ·h (baldock_opt 1); larger γ = later breaking |
| `snapwave_gammax` | `2 *` | `2 *` | `2 *` | `(off)` | `2` | — | depth cap on the energy: E /= max(1, (H/(γmax·h))²) |
| `snapwave_alpha` ⚙ | `1` | `1` | `1` | `(off)` | `1` | — | Baldock dissipation scale: Dw = 0.28·α·ρ·g/T·exp(−(Hmax/H)²)·(Hmax²+H²) |
| `snapwave_baldock_opt` | `1 *` | `1 *` | `1 *` | `(off)` | `1` | — | 1 = the (Hmax²+H²) Baldock form above; 2 = the (Hmax³+H³)/(γ·h) form |
| `snapwave_baldock_ratio` | `0.2 *` | `0.2 *` | `0.2 *` | `(off)` | `0.2` | — | breaking is applied only where H > ratio·Hmax |
| `snapwave_fw` ⚙ | `≠ 0.02` | `≠ 0.02` | `≠ 0.02` | `(off)` | `0.01` | — | bottom-friction factor: Df = 0.28·ρ·fw·u_orb³, u_orb = ½·σ·H/sinh(kh); always on; there is no whitecapping term |
| `snapwave_fw_ratio` | `1 *` | `1 *` | `1 *` | `(off)` | `1` | — | multiplier on fw where a spatially varying fw file is used |
| `snapwave_hmin` | `≠ 0.01` | `≠ 0.01` | `≠ 0.01` | `(off)` | `0.1` | 0.1 | minimum water depth [m] at which a wave node is solved |

### Directional grid and solver

| key | `naccs-premier` | `wave-shelf-steps` | `wave-nowind+wave-shelf-steps` | `naccs-nowaves` | engine | hydromt | meaning |
|---|---|---|---|---|---|---|---|
| `snapwave_dtheta` | `≠ 5.0` | `≠ 5.0` | `≠ 5.0` | `(off)` | `10` | 10 | directional bin width [deg]; the grid has sector/dtheta bins |
| `snapwave_sector` ⚙ | `≠ 360` | `≠ 360` | `≠ 360` | `(off)` | `180` | — | directional sector [deg] centred on the mean direction; 360 = full circle. < 360 clips energy > sector/2 from the centre (0.999·π/2 test) |
| `snapwave_niter` ⚙ | `≠ 100` | `≠ 200` | `≠ 200` | `(off)` | `10` | — | maximum sweeps; convergence is tested every 4th sweep, so the log counts niter/4 'iterations' |
| `snapwave_nrsweeps` | `4 *` | `4 *` | `4 *` | `(off)` | `4` | 4 | sweeps per convergence test (the log's one 'iteration') |
| `snapwave_crit` | `0.001 *` | `0.001 *` | `0.001 *` | `(off)` | `0.001` | 0.001 | convergence: max|ΔE|/Emax < crit over all nodes |
| `snapwave_dt` | `36000 *` | `36000 *` | `36000 *` | `(off)` | `36000` | — | internal pseudo-time step [s] of the stationary iteration |
| `snapwave_tol` | `1000 *` | `1000 *` | `1000 *` | `(off)` | `1000` | — | solver tolerance parameter (unused in the sweeping scheme) |
| `snapwave_Tpini` | `1 *` | `1 *` | `1 *` | `(off)` | `1` | — | initial-guess peak period [s] before the first solve |
| `snapwave_jadcgdx` | `1 *` | `1 *` | `1 *` | `(off)` | `1` | — | 1 = include the ∂cg/∂x term in the energy transport |
| `snapwave_c_dispT` | `1 *` | `1 *` | `1 *` | `(off)` | `1` | — | scale on the dispersion-relation period |

### Wind growth

| key | `naccs-premier` | `wave-shelf-steps` | `wave-nowind+wave-shelf-steps` | `naccs-nowaves` | engine | hydromt | meaning |
|---|---|---|---|---|---|---|---|
| `snapwave_mwind` | `2 *` | `2 *` | `2 *` | `(off)` | `2` | — | cos^mwind directional spreading of the wind source about the wind |
| `snapwave_sigmin` | `0.251327 *` | `0.251327 *` | `0.251327 *` | `(off)` | `0.251327` | — | lower clamp on the wind-sea radian frequency σ = E/A [rad/s] (2π/25 s) |
| `snapwave_sigmax` | `6.28319 *` | `6.28319 *` | `6.28319 *` | `(off)` | `6.28319` | — | upper clamp on σ [rad/s] (2π/1 s); growth stops at the Pierson–Moskowitz state (E_ful 0.0036, T_ful 7.69) |

### Infragravity waves

| key | `naccs-premier` | `wave-shelf-steps` | `wave-nowind+wave-shelf-steps` | `naccs-nowaves` | engine | hydromt | meaning |
|---|---|---|---|---|---|---|---|
| `snapwave_alpha_ig` | `1 *` | `1 *` | `1 *` | `(off)` | `1` | — | Baldock α for the IG balance |
| `snapwave_gammaig` | `0.2 *` | `0.2 *` | `0.2 *` | `(off)` | `0.2` | — | Baldock γ for the IG balance (Hmax_ig = γ_ig·h) |
| `snapwave_fwig` | `0.015 *` | `0.015 *` | `0.015 *` | `(off)` | `0.015` | — | bottom-friction factor for the IG waves |
| `snapwave_fwig_ratio` | `1 *` | `1 *` | `1 *` | `(off)` | `1` | — | multiplier on fwig where a varying file is used |
| `snapwave_baldock_ratio_ig` | `0.2 *` | `0.2 *` | `0.2 *` | `(off)` | `0.2` | — | IG breaking applied only where H_ig > ratio·Hmax_ig |
| `snapwave_shinc2ig` | `1 *` | `1 *` | `1 *` | `(off)` | `1` | — | fraction of the IG source subtracted from the incident energy |
| `snapwave_alphaigfac` | `1 *` | `1 *` | `1 *` | `(off)` | `1` | — | multiplier on the IG shoaling source (∝ ∂Sxx) |
| `snapwave_ig_opt` | `1 *` | `1 *` | `1 *` | `(off)` | `1` | — | 1 = conservative shoaling source from dSxx (Leijnse et al. 2024) |
| `snapwave_iterative_srcig` | `0 *` | `0 *` | `0 *` | `(off)` | `0` | — | 1 = IG source inside the iteration; 0 = from the previous call |
| `snapwave_use_herbers` | `1 *` | `1 *` | `1 *` | `(off)` | `1` | — | 1 = bound-long-wave IG boundary from Herbers on a JONSWAP spectrum |
| `snapwave_tpig_opt` | `1 *` | `1 *` | `1 *` | `(off)` | `1` | — | IG period from the Herbers spectrum: 1 Tm01, 2 Tp smooth, 3 Tp, 4 Tm−1,0 |
| `snapwave_jonswapgamma` | `3.3 *` | `3.3 *` | `3.3 *` | `(off)` | `3.3` | — | JONSWAP peak enhancement for the Herbers spectrum |
| `snapwave_eeinc2ig` | `0.01 *` | `0.01 *` | `0.01 *` | `(off)` | `0.01` | — | IG/incident energy ratio at the boundary when use_herbers = 0 |
| `snapwave_Tinc2ig` | `7 *` | `7 *` | `7 *` | `(off)` | `7` | — | IG period [s] at the boundary when use_herbers = 0 |

### Output

| key | `naccs-premier` | `wave-shelf-steps` | `wave-nowind+wave-shelf-steps` | `naccs-nowaves` | engine | hydromt | meaning |
|---|---|---|---|---|---|---|---|
| `storefw` ⚙ | `≠ 1` | `≠ 1` | `≠ 1` | `(off)` | `0` | — | 1 = write the wave forces fwx/fwy (and snapwavedepth) to the map |
| `storewavdir` ⚙ | `≠ 1` | `≠ 1` | `≠ 1` | `(off)` | `0` | — | 1 = write the mean wave direction wavdir to the map |

### Boundary files

| key | `naccs-premier` | `wave-shelf-steps` | `wave-nowind+wave-shelf-steps` | `naccs-nowaves` | engine | hydromt | meaning |
|---|---|---|---|---|---|---|---|
| `snapwave_bndfile` | `≠ snapwave.bnd` | `≠ snapwave.bnd` | `≠ snapwave.bnd` | `(off)` | `none` | — | support-point coordinates (x y per line) |
| `snapwave_bhsfile` | `≠ snapwave.bhs` | `≠ snapwave.bhs` | `≠ snapwave.bhs` | `(off)` | `none` | — | Hs per support point per time |
| `snapwave_btpfile` | `≠ snapwave.btp` | `≠ snapwave.btp` | `≠ snapwave.btp` | `(off)` | `none` | — | Tp per support point per time |
| `snapwave_bwdfile` | `≠ snapwave.bwd` | `≠ snapwave.bwd` | `≠ snapwave.bwd` | `(off)` | `none` | — | mean direction (nautical, from) per support point per time |
| `snapwave_bdsfile` | `≠ snapwave.bds` | `≠ snapwave.bds` | `≠ snapwave.bds` | `(off)` | `none` | — | directional spread per support point per time |
| `snapwave_upwfile` | `snapwave.upw *` | `snapwave.upw *` | `snapwave.upw *` | `(off)` | `snapwave.upw` | — | the solver's upwind-neighbour cache; regenerated when absent |
