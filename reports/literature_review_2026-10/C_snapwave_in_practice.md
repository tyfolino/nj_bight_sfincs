> **Appendix to [../literature_review_2026-10.md](../literature_review_2026-10.md)** — the research notes as written on 2026-09-30, kept for their verbatim quotes, page numbers and read-status tags. Paths to scratch extracts (`*.txt`, `up/`, `gh/`) did not survive the session; the sources are cited in full at the end.

# Literature thread C: SnapWave configuration, cost, and alternatives

Compiled 2026-09-30. Research only; nothing under `~/nj_bight_sfincs` or `~/nj_sandy_sfincs` was modified.

**Read-status tags:** `FULL TEXT READ` = every page read; `PARTIAL (…)` = the parts named were read; `ABSTRACT ONLY`. Text extracted from PDFs (pypdf) is kept in the scratchpad next to this file: `leijnse2025.txt`, `roelvink2025.txt`, `leijnse_thesis.txt`, `roelvink_ww2025.txt`, `egus_AR1.txt`, `cd2025_hits.txt`. Upstream source was downloaded to `up/`, `swsa/` and `cht/`, and GitHub issue JSON to `gh/`.

**Our run used as the reference:** `experiments/v3/naccs-premier` (engine `bin:v2.3.3-winddir-fix-1-gf11`, 64 threads, `hal0383`). Its `sfincs.log` reports `Number of active SnapWave nodes: 2888437` (l.175) and `1123952 SnapWave node(s) do not have a matching SFINCS point` (l.184). I parsed all 145 SnapWave calls from that log (see Q6).

---

## Headline (plain language)

1. **Our cost is mostly a configuration and version effect, not a mystery.** Leijnse et al. (2025) ran SFINCS v2.1.1. Reading that release's source shows it had:
   - no wind growth at all;
   - a sector hard-coded to 180°;
   - an iteration cap hard-coded at 40 sweeps (10 iterations);
   - a default convergence criterion (`crit`) of 0.01;
   - a warm start (each solve starts from the previous wave field).

   The paper does not state its directional resolution. If it ran the default 10°, that is **18 direction bins against our 72**, on **1.4 M wave nodes against our 2.89 M**. Plugging those numbers into Roelvink's published cost rate (about 0.3 µs per node per bin per wave condition) gives **7.6 s per call**. Leijnse reports 5–10 s. Our median call is 453 s.

2. **The iteration cap is not the problem.** A regression over our 129 timed calls (R² = 0.999) splits each call as:
   - about 42 s fixed;
   - about 1.3 s per extra "tail" iteration;
   - about 103 s per full-domain-equivalent iteration.

   The 50 calls that hit the cap were already ≥99% converged for most of their tail. v2.4.x's looser "99% of nodes converged" rule would save only about 0.8 h of about 23 h. The cost is **nodes × direction bins × work per node × about 3.8 full-domain passes per call**. The 3.8 passes come from the cold start plus wind growth.

3. **The cheapest large levers:**
   - `snapwave_dtheta` 5°→10° while keeping 360°: about 2×.
   - `dtwave` 1800→3600 s: about 2×.
   - Coarsening the SnapWave-only shelf band, which is 74% 50-m cells, to 200 m: about 1.5×.

   These gains were derived from our own log and assume cost scales with bins, calls and nodes. Combined, they come to roughly 23 h → about 4 h. None removes wind growth, which is what makes bay waves exist.

4. **Upstream has no parallel SnapWave sweep.** This holds in v2.3.3, v2.4.x, upstream `main` and the standalone SnapWave code. Leijnse et al. (2025) call it the "non-parallelized SnapWave solver". In v2.3.3 one core of our 64 does 97% of the wall-clock work.

---

## (a) Table of SnapWave applications with settings and cost

"Stated" means the source says it. "Source-inferred" means taken from the code release the paper names. "—" means not given.

| Application | Engine | Wave nodes | Resolution | Dir. bins / sector | Update interval | Wind growth | IG | Iteration settings | Where the wave domain ends | Hardware | Reported cost |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Leijnse et al. 2025**, Hurricane Florence, Carolinas, 950 km [FULL TEXT READ] | SFINCS v2.1.1 Dollerup (stated) | **1.4 M** SnapWave cells of 5 M (stated) | 1,600 m offshore, halved 6× to **25 m** at barrier/surf zone (stated) | **not stated**; v2.1.1 code: `ntheta = int(180.1/dtheta)`, default `dtheta` 10 → **18 bins / 180°** (source-inferred) | **30 min** (stated) | **No.** v2.1.1 has no `snapwave_wind` key (source-inferred) | Yes, with wavemakers at about 5 m depth (stated) | v2.1.1: `niter = 40` sweeps hard-coded, `crit` default 0.01, warm start (source-inferred) | Seaward to the ERA5 points; SFINCS starts at about −10 m (stated) | 16 vCPU, Deltares HPC; also a 4-core PC | 6.12 h for 5 days; **SnapWave 13.3%**, IG boundary 1.5%; "one stationary timestep … takes 5–10 s" |
| **Leijnse et al. 2025 (CD2025 ch. 25)**: GLOBEX lab test and Hernani (Haiyan) [FULL TEXT READ] | SFINCS + SnapWaveIG | — | — | — | — | — | Yes | — | Hernani: model starts in about 45 m depth; wavemaker at about 3 m (stated) | — | Hernani: "20 s" vs XBeach "over three hours" |
| **Leijnse et al. 2024** (Frontiers), Outer Banks demo, via thesis ch. 5 [PARTIAL: §5.2.1.1, §5.3.4, conclusions, appendix settings] | Standalone SnapWave-IG | **4,493,839** cells | 1,000 m → **31.25 m** (stated) | — | single stationary field | No | Yes | — | Offshore boundary at the **200 m** contour | "regular laptop PC" | "mere seconds" per field |
| **Roelvink et al. 2025**, Coast3D large-scale [FULL TEXT READ] | Standalone SnapWave | 338,292 | 800 → 100 m, local 14 m | **18 bins**, 10° (stated; sector not stated) | hourly, 288 conditions | No | No | default crit 1e-5; "typically took 10 iterations" | ERA5 points about 0.5° offshore | HP ZBook laptop, i7-13800H (threading not stated) | 1.9 s per condition; **0.31 µs/node/bin/condition** |
| Roelvink 2025, Coast3D local | same | 4,964 | 70 → 13 m | 18 | half-hourly, 576 | No | No | typically 6 iterations | 15 m depth | same | 0.016 s; 0.17 µs |
| Roelvink 2025, Ameland | same | 226,258 | 800 → 100 m | **36 bins**: "directional resolution of 10° and a directional sector of 360°" | 1,440 conditions | No | No | — | ERA5 points | same | 2.4 s; 0.3 µs |
| Roelvink 2025, St Croix | same | 36,236 | 800 → 200 m | 36 | 3,672 | No | No | — | all sides ERA5 | same | 0.82 s; 0.6 µs ("outlier") |
| Roelvink 2025, Ningaloo large / local | same | 100,146 / 46,146 | 500 → 16 m / 16 m | 36 | 456 | No | No | — | ERA5 | same | 1.1 s / 0.26 s; 0.3 / 0.16 µs |
| Roelvink 2025, Haringvliet vs unSWAN | same | 5,961 | triangular | 36 | 1 | off in both models | No | crit 0.02; converged in 3 iterations | — | same | SnapWave 0.03 s vs unSWAN 6 s ("factor of 200") |
| Roelvink et al. 2025, Waves Workshop slides [FULL TEXT READ] | SnapWave | "~650,000 points, resolution 800–100 m" (NL example) | | | | "New developments: wave growth included …" | | | | | "Wind growth publication in prep." |
| **Our v3 premier** | v2.3.3 + wind-dir patch, native gfortran, OpenMP | **2,888,437** (1,124,003 SnapWave-only; 74% of those are 50 m cells) | 25–200 m | **72 bins**: 5° / 360° | **30 min**, 145 calls | **Yes** | Yes, but no wavemaker in the premier inp | niter 200 sweeps = 50 iterations, crit 0.001, cold start (v2.3.3) | Shelf band to z ≈ −30 m (1st pct −29.9 m) | `hal0383`, 64 threads | median **453 s** per call; SnapWave about 97% of 25.5 h |

**Other studies checked:**
- **No waves in SFINCS:** Nederhoff et al. 2024c (GMD 17:1789); van Ormondt 2025 ICCE; Leijnse et al. 2023 ICCE Australia; Geertsen & Burmester CD2025.
- **Waves supplied another way:** Khan et al. 2025 (Madagascar); Storlazzi et al. 2024 (USGS DR1184); Gaido-Lasserre et al. 2024. See Q5.

Upstream GitHub issues show unpublished SnapWave-in-SFINCS use at the Danish Coastal Authority:
- #193: "In DCA Pilot site-1 the wave patterns … show weird strikey patterns".
- #184: "DCA_sfincs model case study 2".

Settings and costs for that work are not published.

---

## (b) Answers

### Q1. Every published or documented SnapWave application, with settings

**Leijnse et al. (2025)**, *Coastal Engineering* 199:104726, doi:10.1016/j.coastaleng.2025.104726 [FULL TEXT READ; local `refs/1-s2.0-S0378383925000316-main.pdf`, 20 pp. incl. Appendices A–D]

Settings stated:
- Version: "The v2.1.1 Dollerup Release of the SFINCS software is used" (p.3).
- Shared grid: "The model domains and grid are used by both the SFINCS software and the coupled SnapWave solver … For SnapWave, the domain is extended seaward to the nearest ERA5 … wave input points" (p.4).
- Resolution: "resolution at the barrier islands, dunes and surf zone was refined to 25 m" (p.4). "For SnapWave, the grid resolution offshore at the ERA5 input points is 1,600 m, which refines 6 times stepwise towards the coast by factors of 2. In total, the grid consists of 5 million active grid cells for SFINCS, of which 1.4 million are active grid cells of the wave solver" (pp.4–5).
- Update interval: "The stationary wave solver updates the incident and IG wave conditions every 30 min of the 5-day simulation" (p.5).
- Wavemakers: "placed at a water depth corresponding to approximately 5 m deep during high tide" (p.5).

Cost (§4.5, p.13):
- "takes 1.2 h per simulated day and 6.12 h in total on 16 virtual CPU cores … Of this, 13.3% of the computation time was needed for the SnapWave solver and 1.5% by the IG wave boundary condition."
- "For 4 CPU cores, the additional contribution of SnapWave and wavemakers drops to only 6% … The number of cores mostly impacts the highly parallelized momentum and continuity equation loops in SFINCS, where that of the boundary conditions, SnapWave and wavemakers remains more similar."
- "Generally, one stationary timestep of the SnapWave wave solver takes 5–10 s."
- "It should be investigated whether the non-parallelized SnapWave solver on GPU would become a bottle neck."

Not stated anywhere in the paper, appendices included:
- `dtheta`, sector, `niter`, `crit`, wind growth;
- `hmin`, `gamma`, `fw`;
- CPU model.

Appendix A gives only the equations.

**Settings inferred from the v2.1.1 source** (`up/v2.1.1_Dollerup_release_*.f90`, downloaded from tag `v2.1.1_Dollerup_release`):
- `sfincs_snapwave.f90` l.378 `'snapwave_dtheta',dtheta,10.0` and l.379 `'snapwave_crit',crit,0.01`.
- `snapwave_domain.f90` l.97 `ntheta = int(180.1/dtheta)`: sector fixed at 180°.
- `snapwave_solver.f90` l.275 `niter = 40` (hard-coded; the loop `do iter=1,niter` counts sweeps, so 10 iterations).
- No `wind`/`u10` anywhere in the v2.1.1 SnapWave sources: no wind growth.
- No `omp` directive in the v2.1.1 SnapWave solver.
- Initial condition at inner cells is based on the previous `ee` ("Make sure DoverE is filled based on previous ee"): a warm start after the first call.

These are the release defaults. **The paper does not say whether Leijnse overrode `dtheta` or `crit`.**

**Leijnse et al. (2025), "Fast Modelling of Wave-Driven Flooding for Sandy and Coral Reef-Lined Coasts"**, *Coastal Dynamics 2025* (Coastal Research Library 42), pp.155–160, doi:10.1007/978-3-032-15477-4_25 [FULL TEXT READ; local `refs/978-3-032-15477-4.pdf` pp.175–179]
- "The model starts in about 45 m offshore water depth and the IG wavemaker is placed just offshore of the reef edge, at about 3 m water depth."
- "The corresponding computational gain is a factor 500 (deduced from a 3 h computing time for XBeach and 20 s for SFINCS)."
- No SnapWave settings are given.

**Leijnse PhD thesis (2025)**, "Riding the wave", VU Amsterdam, doi:10.5463/thesis.1031 [PARTIAL: abstract; ch. 5 §5.2.1.1, §5.3.4, conclusions and appendix settings; ch. 6 §6.4.5 (same text as the CE paper). PDF from research.vu.nl, 258 pp.]
- Outer Banks demo: "The area model has an offshore boundary at the 200 m water depth contour … 1,000 m grid cells in deep water, increasing in resolution in steps of a factor 2, up to the finest grid cells of 31.25 m in the surf zone. The total domain has 4,493,839 active grid cells."
- "The computation of a single stationary wave field (combining both incident and IG waves) of 4.5 million grid cells takes mere seconds on a regular laptop PC."
- Settings given: "γ = 0.78 … f_w = 0.0001" (Duck/Outer Banks, incident waves).
- No `dtheta`, sector or iteration count given.

**Roelvink et al. (2025)**, "SnapWave: fast, implicit wave transformation from offshore to nearshore", *GMD* 18:9469–9495, doi:10.5194/gmd-18-9469-2025 [FULL TEXT READ; downloaded PDF, 27 pp. incl. Appendix A tables]

Cost formula:
- "In general we can conclude that the model takes around 0.15 µs per node, directional bin and wave condition for the simplest rectangular grids, and around 0.3 µs for more complex, unstructured grids. The St Croix model is an outlier with 0.6 µs" (§5.3). Table 3 lists nodes, bins and seconds per case (reproduced in the table above).

Iterations:
- "The process generally converges within 4–6 iterations" (§2.4).
- "(typically a relative error of 10×10⁻⁵ within 10 iterations or less), and in closed-coast cases the first sweep of the first iteration resolves most of the final solution" (§5.1).
- "the more complex large-scale model typically took 10 iterations to fully converge, where the local model typically took 6" (§5.3).
- Default crit: "we can set the default crit at a comfortably low value of 10⁻⁵" (§2.4).

Directional resolution and sector:
- Coast3D: "Sensitivity tests indicated that the results were little sensitive to the directional resolution, so a directional step of 10° was applied."
- Ameland: "Default parameter settings were chosen with gamma of 0.75, a directional resolution of 10° and a directional sector of 360°."
- Circular island: 5°, 360°. Shoaling/refraction test: 1°, 180° (Table 1).

Wind growth is explicitly excluded:
- "In a forthcoming paper we will detail the method of including wave growth by wind, which is relevant in lakes, estuaries and tidal inlets" (§2.2).
- "The functionality described here does not include wave growth by wind, although this process has been implemented and is currently being tested" (§5.5).

**The paper therefore gives no convergence cost for wind growth.**

Grid guidance:
- "for providing boundary conditions to coastline models typically a grid size of 100 m would be sufficient, but the finer resolution is needed to resolve the breaker bars in the surf zone" (§4.1.1).
- "having the right resolution where the steepest gradients are governs the accuracy" (§5.1).

Parallelisation:
- The paper gives only the laptop: "13th Gen Intel(R) Core(TM) i7-13800H … 14 Core(s), 20 Logical Processor(s)".
- Referee #2 asked: "Provide clear information on computational environment (CPU core count, parallelization, memory footprint) and indicate whether SnapWave supports multi-threading or GPU acceleration" (EGUsphere discussion, RC2 [PARTIAL]).
- The published text does not answer this. The editor decision the same day was "Publish as is".

Standalone code (github.com/danoroelvink/SnapWave, `src/snapwave_solver.f90`, main as of 2026-07-08):
- OpenMP on set-up loops only.
- The node sweep (`do count = 1, no_nodes`, l.557) is serial.
- Default `restart = 0`, i.e. a cold start per condition (`snapwave_input.f90` l.126).
- So Roelvink's µs rates are **cold-start, no wind, no IG** figures.

**Roelvink et al. (2025) Waves Workshop slides**, waveworkshop.org/18thWaves [FULL TEXT READ, 42 slides]
- "Applications in North Carolina (Leijnse et al, 2025), Denmark, Maldives, Black Sea"
- "Wind growth publication in prep."
- The runtime table on slide 22 is the same as GMD Table 3.

**Deltares' own default settings.** These are tooling, not publications.
- CHT toolbox used by DelftDashboard and CoSMoS: github.com/Deltares-research/cht_sfincs `cht_sfincs/input.py` l.119–136 (read):

  ```
  dtwave = 1800.0
  snapwave_gamma = 0.8
  snapwave_gammax = 1.0
  snapwave_dtheta = 15.0
  snapwave_hmin = 0.1
  snapwave_crit = 0.01
  snapwave_nrsweeps = 1
  snapwave_use_herbers = 0
  ```

  `nrsweeps` has no effect in v2.3.3: the loop hard-codes `mod(iter,4)`.
- CoSMoS (github.com/Deltares/CoSMoS `src/cosmos/sfincs.py` l.288–300) nests SnapWave boundaries from HurryWave: "If SFINCS nested in Hurrywave for SNAPWAVE setup, separately run BEWARE nesting for LF waves". It writes `wfpfile`/`whifile`/`wtifile` for that nesting.

**Not found:**
- van Ormondt et al. CoSMoS/FHICS *published* SnapWave settings.
- Athif / IHE MSc theses on SFINCS+SnapWave+IG.
- de Goede et al. as a SnapWave application.
- Nederhoff et al. Puerto Rico or Pacific SnapWave applications. The USGS reef work uses SWAN + XBeach-1D + SFINCS (Q5).

A TU Delft MSc (Al Bagir, 2025, vegetation in SFINCS–SnapWave) is known only from a LinkedIn search snippet. See (d).

### Q2. What upstream says about performance, with quotes and URLs

**Shipped documentation.** Local `docs/*.rst` in both trees and sfincs.readthedocs.io/en/latest (checked 2026-09-30) are identical and contain **no SnapWave parameter documentation.**
- `waves.rst` (entire content): "The input of waves as boundary conditions is still work in progress. Right now the following files should not be used: bwvfile … bhsfile … btpfile … cstfile".
- `numerical_implementation.rst`: "Wave generation (Work in progress)", "Wave-induced setup (Work in progress)"; "Computational efficiency" is an empty heading.
- `developments.rst` lists SnapWave only under "Advanced user options - currently as alpha/beta functionality: NOTE - please contact Deltares-SFINCS group in case you want to use any of this functionality." Examples:
  - v2.3.0: "Update of the integrated SnapWave solver to be consistent the latest standalone version … Option to include or exclude wind from SFINCS to SnapWave coupling, to include wind growth on wave heights or not."
  - v2.4.0: "Improvements of the integrated SnapWave solver for wave breaking … Added vegetation effects …"

  There is no text on recommended `dtheta`, sector, `dtwave`, `niter` or `crit`, and none on performance.

**HydroMT-SFINCS 2.0.0-rc2** (installed copy, `components/config/config_variables.py` l.132–512):
- Exposes `dtwave`, `snapwave_dtheta`, `snapwave_nrsweeps`, `snapwave_crit`, `snapwave_hmin`, `snapwave_wind`, `snapwave_igwaves`.
- Omits `snapwave_niter` and `snapwave_sector`.
- Describes `snapwave_nrsweeps` as "SnapWave maximum number of sweeps (-)". That is wrong for the engine, where it is only validated to be 1 or 4 (v2.3.3 `sfincs_snapwave.f90` l.722–725) and the loop ignores it.
- "SnapWave is not supported for regular grid models!" (`snapwave_boundary_conditions.py` l.411).

**Code facts: OpenMP, warm start and convergence.** Verified by reading tags downloaded from GitHub.

| | v2.1.1 | v2.3.3 (ours) | v2.4.0 / v2.4.1 / main |
|---|---|---|---|
| OpenMP directives in `snapwave_solver.f90` | 0 | **0** | 13 regions: pre-sweep, convergence and post loops. **Node sweep `do count = 1, no_nodes` (local main l.629) serial** |
| Warm start | yes | **no**: block "0-c) Set initial condition at inner cells" resets `ee(:,k) = waveps` every call (l.486–496), even though `restart = .true.` is set (`sfincs_snapwave.f90` l.729) | yes: no per-call reset; `restart = .true.` (upstream `snapwave_input.f90` l.129) |
| `niter` meaning | 40 sweeps, hard-coded | sweeps: `do iter=1,niter` (l.528); default 10 = 2.5 iterations | **iterations**: `do iter = 1, niter * 4` (l.526); default 10 |
| Stop rule | `error<crit` | `error<crit` (l.873) | `error < crit .or. percok > 99.0` (v2.4.1 l.1001, 1021) |
| Default `crit` | 0.01 | 0.001 | 0.001 |
| Under-relaxation of D/E, D/A | — | `fac=1.0` (none) | `snapwave_relax_factor_DoverE/DoverA` = 0.25 |

Wind growth cost, from the v2.3.3 source (`snapwave_solver.f90` l.604–733, `snapwave_windsource.f90` l.67–94):
- With `wind`, each node in each sweep solves **two** tridiagonal systems (energy `ee` and action `aa`).
- It calls `windinput` (an `ntheta` loop).
- It calls `compute_celerities` **three** times (l.620, 658, 729).
- Each `compute_celerities` loops over `ntheta` and evaluates `sinh(min(2.0*kwav*hh,50.0))` inside that loop (windsource l.88).
- With IG on, a third tridiagonal is solved (l.744–803).

**Issues and PRs** (github.com/Deltares/SFINCS; bodies and comments read via the GitHub API on 2026-09-30):

*#362 / #363 (ours).*
- #362, "SnapWave boundary wave direction replaced with domain-mean wind direction": open.
- Leynse (Tim Leijnse), 2026-09-15: "In case of snapwave_wind = 1, for SnapWave it is needed to build the grid around the mean wind direction. However, note that in that case we always set snapwave_direction to 360 instead of 180 degrees when wind is turned on. Would that already solve your issue?"
- After the reply, 2026-09-16: "@MarliesA - do you have time to look into this case and PR in more detail?"
- PR #363: open, not merged, `mergeable_state: unstable`, no reviews.
- **New today: PR #371, "Snapwave wind only no bnd"** (Leynse, opened 2026-09-30, open). Its diff to `snapwave_boundaries.f90` includes the #363 fix:
  - uncomments `call build_boundary_support_points_spectra()` "(on the final theta grid)";
  - builds the lobe on `cos(theta - wdmean_bwv)`;
  - adds the sector warning.

  It also adds wind-only runs with no wave boundary (#306, open: "Make possible to run SnapWave without wave boundary condition, and only wind growth").

*Wind growth convergence.*
- PR #147 (2025-04): "Added Dano's changes to SFINCS. Improved convergence for Lake George, Ameland". Merged via #152/#153.
- PR #351 (2026-07, merged): "Fix directional edge boundary conditions in snapwave wind solver … `solve_tridiag` is a plain Thomas solver that ignores `A(1)` and `C(ntheta)`, so the periodic coupling was silently dropped."
  - That code is present in v2.3.3 l.676–682 (`A(1) = -ctheta(ntheta,k)…`, `C(ntheta) = ctheta(1,k)…`). **Our engine has the pre-#351 behaviour.**

*Directional grid and upwind file.*
- #258: "the upwfile of dtheta=5 was used for running with dtheta=10 degrees … one should also not reuse if the directional grid has been changed!"
- #304 (open) proposes encoding `dtheta` in the `snapwave.upw` name.
- **Any `dtheta` test must delete `snapwave.upw`.** The premier's is 4.18 GB.

*Other performance-related issues:*
- #224/#225 parallelised `find_matching_cells` (set-up only).
- #324 fixed 32-bit timer overflow ("negative elapsed times").
- #353 (merged 2026-09-29) added a `sfincs_timers` module.

  Searches for "openmp", "parallel", "performance", "slow" and "GPU" found **no issue or PR on parallelising the SnapWave sweep, on SnapWave GPU support, or on SnapWave slowness with wind.** GPU status in `developments.rst` (general): "Docker GPU version … removed from the repo. If you'd want to use the GPU version of SFINCS, get in touch."

*Release notes* (GitHub API, all releases): no SnapWave performance item. v2.3.0: "Added wave enhanced roughness when bmi coupled with hurrywave."

**Recommended values documented upstream: none.**
- The only recommendation-like statement is Leijnse's in #362 ("we always set … 360 … when wind is turned on").
- The Deltares tool defaults are in Q1.

### Q3. How others limit where SnapWave runs

**In the coupled quadtree path, SnapWave always uses the SFINCS quadtree cells.**
- `snapwave_domain.f90` hard-codes `ext = 'qt'` (v2.3.3 l.42; main l.45) and calls `read_snapwave_quadtree_mesh`.
- The only per-cell selector is `snapwave_mask` on the quadtree (HydroMT `SnapWaveQuadtreeMask.create(zmin, zmax, include_polygon, exclude_polygon, open_boundary_polygon, neumann_boundary_polygon …)`, `snapwave_quadtree_mask.py` l.45–88).
- `snapwave_mskfile`/`snapwave_depfile` override the mask and depth on those same points (main `snapwave_domain.f90` l.1135–1159).
- `snapwave_ncfile`/`netsnapwavefile` are read as keywords, but the ASCII/structured-mesh branches are unreachable while `ext='qt'`.
- **A SnapWave mesh coarser than the flow grid is therefore not supported in the quadtree path.** The practical equivalent, used by Leijnse et al. (2025): make the shared quadtree coarse where only SnapWave is active ("1,600 m … refines 6 times … towards the coast").

**SnapWave-only cells are allowed** (mask > 0 where SFINCS mask = 0). Depth and wind there come from the nearest SFINCS cell:
- log message: "SnapWave node(s) do not have a matching SFINCS point, so water depth and wind conditions from the nearest SFINCS point within 1000 km are used";
- #184 discusses artefacts from this extrapolation.

**Our shelf band** (read from the premier `sfincs.nc`, read-only):
- 1,124,003 SnapWave-only cells.
- Quadtree levels {1 (200 m): 8,729; 2 (100 m): 280,231; **3 (50 m): 834,042**; 4 (25 m): 1,001}.
- z percentiles 1/50/99 = −29.9 / −17.9 / −10.3 m.

By contrast, Leijnse starts the SnapWave domain at 1,600 m, and Roelvink uses 800 → 100 m.

**Where others end the wave domain:**
- Leijnse 2025: ERA5 points with the SFINCS boundary at about −10 m.
- Leijnse 2024: 200 m isobath.
- Roelvink 2025: ERA5 points about 0.5° offshore; Coast3D local model at 15 m.
- Hernani: 45 m.

### Q4. The SFINCS wavemaker (`wvmfile`, `wfpfile`, `whifile`, `wtifile`, `wstfile`)

**Purpose (Leijnse et al. 2025, Appendix B, p.15):**
- "The wavemaker is based on the absorbing-generating boundary condition of van Dongeren and Svendsen (1997), as added to SFINCS in Leijnse et al. (2021)."
- Flux: "q(t) = √(g/h(t)) (ζ(t) − ζ0(t)) … ζ0 the slowly-varying water level due to the tide, storm surge and mean incident-wave-induced setup."
- IG signal: "a randomly phased time-series … Alongshore, phases are kept the same leading to long-crested waves."

It exists to force **dynamic IG waves** near the shore. Incident setup in their method comes from SnapWave wave forces, not from the wavemaker.

**User-supplied time series (source):**
- main `sfincs_input.f90` l.131–143:
  - `wavemaker_timeseries_wvmfile` ("wavemaker polyline file (forced by IG timeseries)");
  - `wfpfile` (forcing points), `whifile` (IG Hm0), `wtifile` (IG period), `wstfile` ("wave set-up time series file").
- `sfincs_wavemaker.f90` (main l.1549–1610): "Only IG wave forcing supported at the moment !" and "A time series forced wave maker always forces IG waves: that is its purpose".
- Setup is used as `zs0nmb = zs(nmb) + setup` (l.1707): it offsets the mean level on the boundary side of the wavemaker polyline.
- The same `wstfile` path exists in v2.3.3 (`sfincs_wavemaker.f90` l.1214–1222, 1590–1592).
- Since PR #359 (merged 2026-08-18, after v2.3.3) a SnapWave-forced wavemaker and a time-series one can coexist.

**What the `wstfile` route is not.** It is **not a substitute for SnapWave setup over an area.** It imposes a level offset along one polyline. The code has no radiation-stress forcing anywhere else and no bay waves. This is our reading of the code; no documentation describes `wstfile`.

**Used with externally supplied time series:**
- USGS DR1184 (Storlazzi et al. 2024, doi:10.3133/dr1184) [PARTIAL (web-tool extraction)]: SFINCS "forced with 'water level and infragravity wave time series'" from XBeach-1D on "18,357 cross-shore transects" for "999 combinations of sea states".
- Gaido-Lasserre et al. 2024 (*Ocean Modelling* 189:102358, doi:10.1016/j.ocemod.2024.102358) [ABSTRACT ONLY] coupled SFINCS to XBeach-1D. Abstract: "approximately 100 times greater computational efficiency" than 2D XBeach, "a hit rate of 92%".
- CoSMoS "BEWARE nesting for LF waves" writes `sfincs.wfp/whi/wti` (source only; settings not published).

**Validation:**
- Leijnse 2025 §4.3 against XBeach-SurfBeat at Wrightsville Beach: runup "2.87 vs 3.43 m", mean water level "2.19 vs 2.33 m".
- CD2025 GLOBEX A3 ("similar accuracy as XBeach") and Hernani ("similar flood extent and depth").

### Q5. Alternatives for supplying waves, and their cost

- **XBeach 2D / surfbeat.**
  - Leijnse 2025 Table 1: "XBeach 27 h on 4 cores" for 7 km and 8 h vs SFINCS "33 s on 16 cores".
  - Extrapolated: "approximately 55,000 h" for 950 km and 5 days.
- **XBeach-1D transects feeding SFINCS** (CoSMoS / USGS reef work):
  - Gaido-Lasserre 2024: about 100× cheaper than 2D XBeach [ABSTRACT ONLY].
  - DR1184: 18,357 transects × 999 sea states, precomputed.
  - Leijnse 2025: transects are "not well suited for complex coastlines when the shore normal transect has little physical meaning".
- **Coupled circulation–spectral-wave models:**
  - Leijnse 2025 (citing Ye et al. 2021; not verified by me): ADCIRC-SWAN or Delft3D FLOW+WAVE "may add an additional computational burden of >50%".
  - Roelvink 2025: unSWAN 200× slower than SnapWave on the same grid, with wind off in both.
- **Offline spectral model plus a parametric setup at the SFINCS boundary.** Khan et al. 2025 (*Nat. Hazards*, doi:10.1007/s11069-025-07209-z) [PARTIAL: methods passages]:
  - SCHISM-WWM ("36 directional bins (0–360°) and 24 frequency bins").
  - The boundary is at 10–15 m depth: "wave setup is vastly underestimated in SCHISM-WWM … our resolution in SCHISM-WWM is 500 m or coarser".
  - They add Stockdon setup to the boundary level.
  - Leijnse 2025 §4.4: Stockdon gives errors of "0.5–1 m over/underestimation depending on the region"; the "20% of Hs" rule gives "major overestimations … in the order of meters".
- **HurryWave** (Deltares quadtree third-generation spectral model):
  - DestinE page [FULL TEXT READ; not peer-reviewed]: "HurryWave is, on average, an order of magnitude faster than the SWAN model."
  - Coupling to SFINCS exists only as boundary nesting (CoSMoS) and "wave enhanced roughness when bmi coupled with hurrywave" (v2.3.0 notes).
  - **No published cost comparison with SnapWave found.** No peer-reviewed HurryWave description found.
- **Injecting precomputed wave forces into SFINCS** (e.g. SWAN or STWAVE radiation stress): **no input path exists** in v2.3.3 or local main.
  - No `*file` keyword for wave forces in `sfincs_input.f90`.
  - The BMI exposes only `zs`, `zb`, `uorb`, `qext`, `z_xz`, `z_yz`, `subgrid_z_zmin` (`sfincs_bmi.f90` l.114–201).
  - This route would need code changes.
- **Precomputed SnapWave look-up tables: no published use found.**
  - For our case the stationary solution depends on boundary Hs/Tp/direction/spread, the full wind field and the full water-level field.
  - A hurricane's wind field has no low-dimensional parameterisation, so a LUT is impractical (our assessment).
  - What *is* feasible in principle is **parallel-in-time**: the 145 solves are independent given water levels, so they could run concurrently on a first-pass water level. This needs the force-injection path above (our assessment; not published).

### Q6. Why 13% for Leijnse vs 97% for us

**Stated by Leijnse:** 1.4 M wave cells; 30-min updates; 5–10 s per SnapWave solve; 13.3% of 6.12 h on 16 vCPU; SnapWave not parallelised; IG on; wavemakers on; v2.1.1.

**Inferred from the v2.1.1 source:** 18 bins / 180° (if `dtheta` was left at its default); no wind growth possible; at most 40 sweeps; `crit` 0.01 default; warm start.

**Derived: per call.**
- Leijnse: 0.133 × 6.12 h × 3600 / 240 calls ≈ **12 s/call**, consistent with "5–10 s" plus overhead.
- Ours: (25.5 h − 0.77 h) / 145 ≈ **614 s/call** mean, 453 s median.
- Per simulated day: **SnapWave about 50× more expensive** for us (about 8.1 h/day vs 0.16 h/day).
- Flow per simulated day: **about 4× cheaper** for us (0.25 h/day with subgrid vs 1.04 h/day for their 5 M cells at 25 m without subgrid).
- 50 × 4 ≈ 200 is the ratio of the two SnapWave-to-flow ratios (their 0.16 vs our about 32). **That, not a bug, is why 13% became 97%.**

**Roelvink's formula** (t ≈ c · nodes · bins per converged condition; c = 0.15–0.3 µs, 0.6 outlier; no wind, no IG, cold start):
- Leijnse check: 1.4e6 × 18 × 0.3 µs = **7.6 s**, matching the stated 5–10 s.
- Ours: 2,888,437 × 72 = 2.08e8 node-bins → **31 s (c=0.15), 62 s (c=0.3), 125 s (c=0.6)**.
- Measured median **453 s** is **3.6–7.3×** the formula (2.18 µs per node·bin·call).

**Decomposing the excess from our log** (145 calls; 129 timed; 16 printed `******`, i.e. >999.99 s):
- Least squares: **t = 41.7 s + 1.33 s·n_iter + 103.1 s·W** (R² = 0.999), where W = Σ over iterations of (1 − %ok at the start of the iteration) = the number of full-domain-equivalent iterations.
- Median W = **3.83**; median n_iter = 24; 95 calls converged (median 12 iterations); 50 hit the cap.
- The capped calls end at error ≈ 1.0 but **median %ok 99.6**: a tiny set of oscillating nodes.
- %ok after iterations 1/2/3 = 38/50/58% (median). Cold start plus probably dry nodes explain the first 38%.
- Totals: fixed 1.7 h + tail iterations 1.5 h + full-domain work 20.1 h = 23.3 h (the log total is about 24.7 h including untimed calls).

**Apples-to-apples per-iteration rate:**
- Ours: 453 s / (2.08e8 × 24 iterations) = **0.091 µs per node·bin·iteration**.
- Roelvink: 0.31 µs / 10 iterations = 0.031 (Coast3D large); 0.17 / 6 = 0.028 (local).
- **About 3× per iteration × about 2.4× more iterations ≈ 7.3×.**
- The 3× per-iteration factor is consistent with the wind-growth code path: two tridiagonal solves, three `compute_celerities` calls with an `ntheta` loop of `sinh`, and `windinput`. The IG balance and memory footprint add to it: 72 bins × 2.9 M × 4 B = 0.83 GB per spectral array; about 10 such arrays with wind and IG.

This attribution is **inference.** No profile was taken.

**Why Leijnse's per call is about 50× smaller than ours:**
- nodes ×2.06;
- bins ×4 (inferred);
- remaining ×6: wind off; warm start plus crit 0.01 plus 40-sweep cap, so W likely about 1–1.5; hardware unknown.

**Which of their settings are stated vs inferred:**
- Stated: nodes, update interval, per-call time, share, cores, version.
- Inferred: bins/sector, wind off, `crit`, cap, warm start.

### Q7. Physical validity of the cheaper settings for our case

**Directional resolution (10° vs 5°):**
- Roelvink: Coast3D "little sensitive to the directional resolution, so a directional step of 10° was applied"; Ameland default 10°/360°.
- Engine default 10°; Deltares CHT default 15°.
- **No source tests directional resolution against *setup*** (as opposed to Hm0/direction). Not found.

**Sector 180° with wind:**
- v2.3.3 centres the grid on the domain-mean wind (log: "INFO SnapWave - Making directional grid around boundary mean wind direction").
- Wind-sea is generated with `cos^mwind` spreading about the *local* wind (`mwind` = 2), so within ±90° of the local wind.
- In a hurricane the local wind direction rotates across a 200-km domain. A 180° sector centred on the *domain mean* would clip:
  - wind-sea wherever the local wind differs from the mean by more than 90°;
  - boundary swell arriving more than 90° from the mean wind (Sandy: NE wind, SE swell = 90°, borderline);
  - energy refracted to large angles.
- This is our inference. Upstream practice per Leijnse (#362): 360° when wind is on. Roelvink uses 360° at Ameland, where there is no wind.
- Bay wind-sea travelling seaward is aligned with the wind that makes it, so it survives 180° **only where the local and mean winds agree.**

**Update interval:**
- Leijnse 30 min; CHT default 1800 s; engine default 3600 s.
- **No published sensitivity of setup to `dtwave` through a peak was found.**

**Diffraction:**
- The governing equation (Roelvink Eq. 11: propagation, refraction Cθ, dissipation) has no diffraction term.
- **No source discusses its absence for inlets or sheltered bays.** Not found.
- Roelvink only says the model "is therefore suited for swell propagation and wave propagation over limited distances … when the dominant processes are wave shoaling, refraction and dissipation by friction and depth-limited wave breaking" (§5.5).

**Convergence criterion relative to the global maximum** (source; bears on bay waves):
- v2.3.3 marks a node converged when `diff(k)/eemax < crit` with `eemax = maxval(ee)` over the whole domain (l.855, 864).
- A 0.5 m bay sea has about (0.5/8)² ≈ 0.4% of the energy of an 8 m offshore sea. At crit = 0.001, bay nodes count as "converged" while still changing by about 25% of their own energy per iteration.
- Loosening `crit` is therefore riskier for bay waves than it looks.

---

## (c) What this implies for us: ranked options

Speed-ups are for SnapWave time only (about 23.3 h of the 25.5 h run). Provenance labels:
- **[derived]** = our 145-call log fit plus Roelvink's cost ∝ nodes × bins;
- **[est.]** = my estimate;
- **[measured by X]** = published.

Assume multiplicative combination only as a rough guide.

1. **`snapwave_dtheta` 5° → 10°, keep `snapwave_sector` 360 (72 → 36 bins).**
   - Gain: **1.9–2.0×** [derived]; 23.3 → 11.7–12.5 h.
   - Physics given up: directional resolution only. Roelvink found Hm0 "little sensitive"; the effect on setup is not published.
   - Bays keep wind-sea. Must delete `snapwave.upw` (#258).
   - Test paired on HWMs and the gauges.
2. **`dtwave` 1800 → 3600 s (145 → 73 calls).**
   - Gain: **about 2.0×** [derived]. v2.3.3 cold-starts, so per-call cost does not depend on the interval.
   - Physics given up: setup held piecewise constant for 60 min instead of 30. This matters only if Hm0 or water level at the breaker line changes a lot inside an hour near the peak.
   - A cheap check: compare consecutive 30-min SnapWave fields (e.g. `point_hm0` in `sfincs_his.nc`) around the peak before committing.
   - Engine default is 3600; Leijnse used 1800.
3. **Coarsen the SnapWave-only shelf band** (z −10 to −30 m; 834 k cells at 50 m, 280 k at 100 m) to 200 m (the base level).
   - Gain: about 1.12 M → about 0.13 M cells; total 2.89 M → about 1.9 M; **about 1.5×** if cost ∝ nodes [derived upper bound]. Deep nodes may converge sooner than average, so the real gain could be smaller.
   - Physics given up: shelf refraction and shoaling resolved at 200 m instead of 50 m. Leijnse used 1,600 m stepping down; Roelvink 800 → 100 m.
   - Nothing changes in the SFINCS-active area, apart from the obligatory level transitions at the edge.
   - This is a mesh and fingerprint change, i.e. a new domain (CLAUDE.md §2, §5).
4. **`snapwave_igwaves = 0`** (the premier has no wavemaker, so IG energy is not used to force water levels).
   - Gain: **1.1–1.3×** [est.; unmeasured]. Removes the third tridiagonal and the IG source term.
   - Physics given up: the incident → IG sink (`shinc2ig` = 1 subtracts `srcig` from the incident balance, v2.3.3 l.664). This slightly changes incident dissipation and hence setup. Needs a paired test.
5. **Run several arms per node with fewer threads each.**
   - Gain: throughput up to **about N×** for N concurrent arms [est.]. v2.3.3 SnapWave is serial (0 OpenMP directives), so 63 of 64 threads idle about 97% of the wall time. Per-arm latency rises only in the 3% flow part.
   - Physics given up: none.
   - Note: the CLAUDE.md remark that `sstat AveCPU` shows about 30 effective cores is hard to square with a serial solver dominating. Worth a look (thread spin-waiting?).
6. **Move to v2.4.x** (warm start, 99% rule, OpenMP on pre/post loops, under-relaxation).
   - Gain: the 99% rule alone saves **about 0.8 h (−3.5%)** [derived from the log: stopping at %ok > 99 cuts total iterations 4,092 → 2,299, but those tail iterations cost 1.3 s each]. Warm start: **1.2–2×** [est.]. W is currently 3.8, but offshore nodes are held to a strict global-max criterion, so a warm start may not converge them in one pass.
   - Costs:
     - `snapwave_niter` changes meaning (sweeps → iterations): our `200` would become 800 sweeps; set 50.
     - Defaults change: `gammax` 2 → 999, `gammaig` 0.2 → 0.7, new `baldock_exponent` = 2, relax 0.25.
     - The #363 fix must be carried (or #371 merged).
     - Re-baseline.
7. **`snapwave_sector` 180 with 10° (18 bins, Leijnse-like).**
   - Gain: **3.3–4×** combined [derived].
   - **Not recommended for Sandy**: clips energy more than 90° from the domain-mean wind (Q7). Upstream itself uses 360° with wind (#362).
8. **Tighter or looser convergence (`crit`, cap).**
   - Stopping at error < 0.01: **< 1%**. Stopping at %ok > 99: 3.5%. A hard 10-iteration cap: 27%, but truncates unconverged fields [all derived from the log].
   - Not the lever. The capped calls' error ≈ 1.0 plateau at 99.6% ok suggests a few oscillating nodes; v2.4's 0.25 under-relaxation may cure them.
9. **Parallelise the node sweep** (code work).
   - Gain: potentially **several×** on the dominant term [est.]; nobody has published it.
   - Physics given up: none if done as a block Gauss–Seidel over subdomains or dependency-level scheduling; iteration counts may rise slightly.
   - Out of scope for a config change.
   - A cheaper code-level check first: profile whether the per-bin `sinh` in `compute_celerities` (called 3× per node per sweep with wind) is a hotspot.
10. **`snapwave_hmin` 0.01 → 0.1 / trim land above the Sandy +3 m mark from `snapwave_mask`.**
    - Gain: small [est.]; dry nodes are already skipped but still cost set-up, sort and convergence passes.
    - Physics given up: wave energy in films under 11 cm deep.
11. **Wind off: rejected.** Bay Hm0 ≈ 0 without it (the brief's own finding).
12. **Replace SnapWave:**
    - `wstfile` wavemaker setup: a polyline offset only; loses the setup field and bay waves.
    - HurryWave: no cost comparison published; coupling is boundary nesting or BMI roughness.
    - Offline SWAN radiation stress: SFINCS has no force input path; needs code.
    - XBeach transects: not suited to back bays.

    None is a drop-in for a barrier coast with bay wind-sea.

**Rough combination** of 1 + 2 + 3: 23.3 h / 2 / 2 / 1.5 ≈ **4 h** SnapWave [derived, multiplicative assumption], keeping 360°, wind growth and IG. Adding 4 and a warm start could reach about 2–3 h [est.].

---

## (d) Not verified / not found

- van Ormondt et al. 2023, "Wave effects in a rapid compound flood model" (17th Waves Workshop): listed in `overview.rst`; content not found online.
- Van Dongeren et al. 2023, Coastal Sediments, doi:10.1142/9789811275135_0242 (COSMOS with SFINCS/HurryWave/XBeach): only a search-engine snippet seen; not opened.
- Leijnse et al. 2024, *Front. Mar. Sci.* 11:1355095: read only as thesis ch. 5 (the same text as the paper is assumed, not checked).
- Nederhoff et al. 2024a (Salish Sea, *Water* 16:346): MDPI returned 403. The wave approach is not verified.
- Gaido-Lasserre et al. 2024: ScienceDirect returned 403; abstract only (via USGS). Methods and costs not verified.
- Maldives 2022 flooding paper (PMC12645334; possibly a SnapWave application): blocked by reCAPTCHA; not verified.
- Al Bagir 2025 TU Delft MSc (SFINCS–SnapWave vegetation): known only from a search snippet; thesis not located.
- Athif (IHE) and de Goede et al. as SnapWave applications: nothing found.
- Nederhoff Puerto Rico / Pacific SFINCS+SnapWave: nothing found (the USGS reef products use SWAN + XBeach-1D).
- Denmark (DCA) and Black Sea SnapWave applications: mentioned in upstream issues #184/#193 and Roelvink slide 26 only; no settings or costs.
- The forthcoming SnapWave wind-growth paper: "in prep." per Roelvink 2025 slides and GMD §2.2. Not available; **no published convergence cost for wind growth exists** as far as I found.
- Ye et al. 2021 (ADCIRC-SWAN ">50%" burden): cited second-hand from Leijnse 2025; not opened.
- HurryWave: no peer-reviewed model description or SnapWave cost comparison found. The "order of magnitude faster than SWAN" claim is from the DestinE web page only.
- Whether Leijnse overrode v2.1.1's `dtheta`/`crit` defaults: not stated. The 18-bin figure is an inference.
- The CPU model of Deltares' HPC (Leijnse) and whether Roelvink's laptop runs were single-threaded: not stated.
- My per-iteration attribution (wind path ≈ 3× cost) and the warm-start and `igwaves=0` gains: estimates, not profiled or measured.
