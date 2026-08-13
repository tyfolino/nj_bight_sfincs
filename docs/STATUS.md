# STATUS — live campaign state

**Edit this file in place.** Git has the history. This replaces the previous project's
12 KB "current state" memory file and its 26 reverse-chronological campaign logs; the point
of the format is that a reader gets the current state without replaying how it was reached.

Last updated: **2026-08-13**

📋 The original plan this work follows is frozen at
[docs/plan_v1_5_original.md](plan_v1_5_original.md) (Phases 1–4 and 6 are done; 5 and 7 are
live). **This file is authoritative for what remains** — the plan is the record of what was
intended, not of where things stand.

---

## Where we are

The repo has been stood up and the code ported from `~/nj_coast_sfincs`
(commit `21e28f2`, see [ARCHIVE.md](../ARCHIVE.md)). **The port gate passes.** The v1.5
domain is **not yet registered** — it is blocked on two manual facts, below.

### ✅ Port verification — PASSED 2026-08-13

`scripts/verify_port.py`, tier 1 (rescore, no solver) and tier 2 (fingerprint + obs points
on the archived template). Tolerance is **bit-for-bit** (`places=9`): same input, same code
path, deterministic arithmetic, so any drift is a bug, not a tolerance.

Baseline: `experiments/v1_monmouth/metrics.csv` **as regenerated 2026-08-12** — NOT the
older July `_rescored.csv`, which is `hwm_n_scored=19` with no estimator column and would
fail on `n` alone, reading as a port bug that is not there.

| metric | archive | ported |
|---|---|---|
| `hwm_bias_scored_m` | −0.363105931 | −0.363105931 |
| `hwm_rmse_scored_m` | 0.570499300 | 0.570499300 |
| `hwm_n_scored` | 38 | 38 |
| `motf_csi` / `pod` / `far` | 0.637834 / 0.766245 / 0.208073 | identical |
| `phase_lag_sandy_hook_min` | 17.6 | 17.6 |
| `gauge_peak_err_prefail_m` | −0.311681898 | −0.311681898 |

Per-basin marks reproduce too (they depend on first-match-wins over `hwm_rules` IN ORDER,
so a reorder shows up here): `south_coast` 4 · `sandy_hook_bay` 21 · `atlantic_oceanfront`
3 · `shrewsbury_navesink` 10 · `shark_river` 0 — total 38.

**One key renamed by the port**, listed in `RENAMES` in the gate rather than hidden behind
an alias: `gauge_peak_err_prefail_m` → `peak_err_prefail_sandy_hook_m`. The archive had one
function per named place, so `gauge_*` needed no gauge in it; the port drives everything off
the domain registry. Phase-lag keys are now the registry gauge name (`sandy_hook` is
unchanged, which is why it is the pinned one).

**One real bug the gate caught:** a `round(..., 6)` inside the peak metric differed from the
archive at 1e-7. Rounding inside a metric is a silent lossy step that makes a CSV
non-reproducible — it now rounds nothing, and rounding happens in the report.

---

## 🔴 BLOCKED: the two gates before any v1.5 polygon is drawn

Two manual facts can kill the design. Confirm both **before** drawing a region polygon —
neither is expensive, and both are cheaper than a mesh.

### Gate 1 — NACCS coverage at both cuts

Does the CHS/NACCS save-point set have a **wet** point within 2.0 km of the mask==2 cells at
the **Verrazzano Narrows**, the **Arthur Kill**, and along the **Sandy Hook → Rockaway
Point** cut?

`scripts/build_naccs_boundary.py` now reports coverage **per arm**, because aggregate
coverage hides "0 points on Arthur Kill" — which on a domain whose entire claim is that two
short cross-sections carry the exchange is the single most important thing to know before
the run rather than after it.

> **Fallback if an arm comes back empty:** 1-node-per-arm gauge forcing — the Battery
> (8518750) for the Narrows, Bergen Point West Reach (8519483) for Arthur Kill. Defensible
> for two ~1 km cuts, unlike a 123 km gauge desert.

#### 🟡 Indicative coverage, 2026-08-13 — encouraging, NOT the gate passing

8 CHS zips in `data/NACCS/`, all integrity-checked, **695 unique save points** spanning
lat 39.976–40.619, lon −74.326 to −73.877. 342 of them are from the 2026-08-13 grab, which
was clearly aimed at the Narrows.

Counted in **rough indicative lon/lat boxes I invented** — there is no region polygon yet:

| zone | pts | new | save-point depth (m) |
|---|---|---|---|
| Verrazzano Narrows | 52 | **52** | −1.49 … **+23.30** |
| Arthur Kill (S half) | 23 | 2 | −1.18 … **+9.07** |
| Raritan Bay open | 214 | 107 | −2.60 … +13.92 |
| Lower Bay | 85 | 54 | −3.21 … +12.33 |
| Sandy Hook → Rockaway cut | 122 | 101 | −3.21 … +12.33 |

⚠️ **This is not gate 1.** The real screen is "within 2.0 km of a `mask==2` cell", which
needs the frozen mesh, and these boxes are not the arms. Read it as: the Narrows is
comfortably covered and **Arthur Kill is the thin arm to watch** — 23 points, only 2 of them
new, and its maximum save-point depth is +9.07 m. Negative depths are above datum and will
drop out on the wet/depth screens.

#### Where the zips go

`~/nj_bight_sfincs/data/NACCS/` — a real local directory (the builder reads
`ROOT/data/NACCS`). **Point the browser here.** ⚠️ Two zips from 2026-08-13 originally
landed in the **archive's** `data/NACCS/`, which the freeze then made read-only; they were
moved across (sha256-verified identical, then deleted from the archive, which was re-frozen).
The archive's NACCS dir is back to the 6 zips it held before the restart, which is what it
should contain — those two were never part of its record.

⚠️ **There is deliberately no `_sandy_parsed.npz` here.** That parse cache is keyed to
nothing — `read_zips(use_cache=True)` would load it and never notice a new zip. If one ever
appears and you have since downloaded more data, run with `--no-cache`.

⏳ **STWAVE is still to come.** The 2026-08-13 zips are ADCIRC water level, confirmed by the
column check: `ET00` present, zero wave parameters (`Hs`, `Tp`, `STWAVE`, direction all
absent). Members are named `..._ADCIRC01_Timeseries.csv`.

### Gate 2 — at least two interior gauges that survive the crest

The whole claim is "Raritan Bay is COMPUTED, not forced". **If nothing inside can be
scored, the claim is untestable.** Sandy Hook (8531680) dies mid-storm — 48 of 96 hours NaN,
the whole back half — and cannot be the answer alone.

`ObsGauge.survives_crest` now records this per gauge, so the registry states it rather than
leaving it to be rediscovered.

---

## Then: the build sequence (Phase 5b)

1. **Region polygon** — `scripts/build_region_v1_5.py`, named lon/lat vertices as module
   constants. Ring segments tagged `ocean` / `land` / `narrows` / `arthur_kill`.
   ⚠️ Cut Arthur Kill at its **north** end (the Kill Van Kull junction) so Perth Amboy /
   Carteret / Woodbridge stay computed — that is HWM-rich ground.
2. **Refinement** — a NEW `refinement_v1_5_raritan.geojson`. Neither existing recipe is
   usable: a refinement recipe is not portable, and a level gate written for one basin will
   refine another basin's open water to its finest level. L3/L4 on the two cuts and their
   approaches, L3 Sandy Hook Bay + Shrewsbury/Navesink, L2 Raritan open water, L0/L1 shelf.
   **Size it with `scripts/probe_mesh_size.py` BEFORE building** — SnapWave is 90–95% of
   runtime and scales with the mesh.
3. **Subgrid + freeze** — the expensive irreversible step. Do the elevation check first:
   `nj_10ft_dem` is NJ-only, so Staten Island, the Rockaway shore and the Narrows fall
   through to CUDEM/3DEP. `build_static` now asserts no active cell has NoData in the merged
   bed, which turns a silent hole into a build error.
4. **Mask + boundary** — declare `boundary_arms` (ocean / narrows / arthur_kill) and
   `land_boxes` (Staten Island south shore, Jamaica Bay). The whitelist replaces the
   half-plane `MaskOverride` patches; the type no longer has an unbounded side, so the
   defect class is unrepresentable.
5. **Flux cross-sections** — `sfincs.crs` observation lines just *inside* each arm. SFINCS
   writes `crosssection_discharge` every 10 min. ⭐ **This is what makes the relocation
   auditable**: the Narrows carries the Upper Bay + Hudson tidal prism, and a tidal prism is
   comparable against literature. Without it the new boundary is asserted, not measured.
6. **NACCS forcing** — `build_naccs_boundary.py`, with the depth screen applied **seaward of
   `open_coast_max_y` only**. Declare the resulting count as
   `Experiment.n_waterlevel_support`, never by relaxing the domain value.
7. **Register the fingerprint** in `premier.EXPECTED` + `KNOWN` **before** running anything.

---

## The four seeded arms

Already in `nj_sfincs/experiments.py` under `v1_5_raritan`:

| arm | what it is |
|---|---|
| `naccs-premier` | the premier: relocated boundary + CORA per-support-point waves |
| `naccs-nowaves` | same boundary, SnapWave off — cheap, levels + phase only |
| `noaa-2node` | the incumbent 2-node interpolant, kept only to show what relocation bought |
| `naccs-premier-z15` | −15 m boundary: **a different DOMAIN**, `mesh_key` sibling |

---

## Open, deliberately not decided

- **STWAVE vs CORA waves.** A single-variable arm, withheld to avoid moving two variables at
  once. Same logic says do not bundle it with a domain move. CORA-as-wave-boundary is
  *adopted* settled physics (admissible at 7/7 support points vs ERA5's 0/7).
- **The +0.027 m setup problem.** The reference configuration generates only +0.027 m of
  setup from the −10 m boundary to shore with waves ON — far too small, and an open thread.
  It bears directly on whether a deeper boundary buys anything, which is why
  `naccs-premier-z15` exists.
- **−2 m boundary: DROPPED, not deferred.** Setup-at-the-boundary XOR SnapWave, never both
  (Leijnse et al. 2025 §4.4). At −2 m the embedded setup in NACCS is the whole signal, so
  SnapWave would have to be off — the branch measured to overestimate max water depth by
  ~1 m.
- **`south_coast` marks.** 4 of 38 are hydraulically disconnected from the water-level
  boundary in the model: they move by 0.0005 m across four different boundaries, including
  one that adds +0.115 m uniformly to every boundary cell. They contribute a fixed −0.53
  bias / 0.785 RMSE to every arm and dilute any pooled score. Flagged **before** the results
  landed, so excluding them is a pre-flagged re-analysis, not a post-hoc one.

---

## Known gaps in this repo

- **The archive is not yet read-only on disk.** Run, once:
  `cd ~/nj_coast_sfincs && chmod -R a-w nj_sfincs scripts docs reports tests data *.md *.py`
  (undo with `u+w`). Leave `experiments/` writable — the port fixture is copied out of it.
- **`ruff` is not installed anywhere on this machine**, so the tree has not been formatted.
  It is written to the 88-column style by hand. Run `ruff format . && ruff check .` once,
  in its own commit, before any logic edits — that is the only moment it is free.
- **`nj_sfincs/plots.py` is untested at runtime.** It imports cleanly, but no figure has
  been drawn since the port.
- **No `notebooks/`.** Deliberate; add one when there is something to look at.
