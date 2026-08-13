<!--
FROZEN PLANNING ARTIFACT — copied 2026-08-13 from
    ~/.claude/plans/nah-skip-wind-py-and-rustling-neumann.md   (authored 2026-08-12)

⚠️ docs/STATUS.md IS AUTHORITATIVE for what remains. This is the original plan, kept in the
repo because ~/.claude/plans/ is outside version control and can be rotated away.

Executed since it was written: Phase 1 (freeze), Phase 2 (repo), Phase 3 (port),
Phase 4 (port gate — PASSED bit-for-bit), Phase 6 (docs + memory rebuild).
Still live: Phase 5 (build v1.5) and Phase 7 (retire v1_monmouth).

Where the execution DEVIATED from this text, the deviation and its reason are recorded in
the relevant module docstring, not here. Delete this file once Phase 5–7 land.
-->

# Fresh-start repo + the v1.5 Raritan domain

## Context

The water-level boundary currently runs **through the middle of Raritan Bay**, forced by a
2-node Battery↔Atlantic City linear interpolant. NOAA harmonics show the interior tidal
maximum is real (0.732–0.761 m, exceeding *both* outside anchors), so a linear interpolation
between two exterior points **structurally cannot** reproduce it — the north lobe is ~15%
under-forced by construction. Switching to NACCS (hundreds of support points) closes the
deficit and then **overshoots** (`sandy_hook_bay` bias −0.495 → +0.327 with waves on), which
is what forcing a basin harder looks like when the real problem is that it is being forced
at all.

v1.5 relocates the boundary so Lower Bay, Raritan Bay and Sandy Hook Bay are **computed**:
one ocean boundary (Atlantic contour wrapped around Sandy Hook, closing on Rockaway Point)
plus two short forced cross-sections at **Verrazzano Narrows** and **Arthur Kill**. Staten
Island south shore is a **hard bank**; Jamaica Bay is excluded; no NYC land in the model.

At the same time the repo restarts. The knowledge is worth keeping; the *format* is the
problem — 26 reverse-chronological campaign logs with retractions stacked above the claims
they retract, a 12 KB "current state" memory file, and a `.git` of 300 MB for 11 commits.
The old repo stays on disk as a read-only archive.

### Evidence this rests on (measured 2026-08-12)

The waves-on 3×2 scored, n=38 common marks, `median`/50 m:

| arm | wave src | HWM RMSE | HWM bias | within 0.5 | CSI | POD |
|---|---|---|---|---|---|---|
| `tide-shift+wave-cora` | CORA | 0.585 | −0.402 | 0.58 | 0.624 | 0.747 |
| `tide-naccs+wave-cora` | CORA | 0.543 | +0.233 | 0.87 | 0.664 | 0.844 |

**P1 failed** and the ranking is identical on both wave sources, so the pre-registration's own
clause fires: the wave-source worry is dead, quote the CORA row. But the paired bootstrap does
**not** separate them — ΔRMSE −0.042 m, CI [−0.238, +0.137], P=0.706. NACCS wins every point
estimate and is not a demonstrated win.

⇒ **v1.5's case rests on the boundary being in the wrong place (structural), not on this
margin.** Say so in the paper and in `docs/STATUS.md`.

---

## Deviations from what was discussed — accept or override

1. **Repo name.** Proposed `~/nj_bight_sfincs`, not "sfincs_v1.5". Naming a *repo* after a
   version guarantees it is misnamed by v2; the old repo is already a Monmouth/Barnegat repo
   called "nj_coast". The **domain** carries the version: `v1_5_raritan`. Override if you want
   the v1.5 label on the directory.
2. **Docs = 2 files as you chose** (`FINDINGS.md`, `STATUS.md`), plus `CLAUDE.md` and
   `ARCHIVE.md` at root — those are the entry point and the archive index, not campaign docs.
   The v1.5 design record and the NACCS construction notes become *sections* of `FINDINGS.md`.
3. **Boundary depth is a domain axis, not an arm axis.** `mask_zmin` is half of
   `sha_z_mask`, so an arm that changes it fails `assert_sealed_domain` on its own staged copy.
   −10 and −15 become two registered domains sharing one frozen mesh.
4. **−2 m is dropped.** Leijnse et al. 2025 §4.4: setup-at-the-boundary XOR SnapWave, never
   both. At −2 m NACCS's embedded setup is the whole signal so SnapWave must be off — the
   branch they measured overestimating max water depth by ~1 m.

---

## Phase 1 — Freeze the archive

- Record `git -C ~/nj_coast_sfincs rev-parse HEAD` into `ARCHIVE.md`.
- `chmod -R a-w` on repo A's `nj_sfincs/ scripts/ docs/ reports/ tests/ data/ *.md *.py`.
- Working tree is already clean (0 uncommitted files) — nothing to commit first.

## Phase 2 — Stand up the repo

```
~/nj_bight_sfincs/
  CLAUDE.md  README.md  ARCHIVE.md  ruff.toml  .gitignore  environment.yml
  run_experiments.py  nj_sfincs/  scripts/  tests/  hpc/
  docs/FINDINGS.md  docs/STATUS.md
  reports/.gitkeep  logs/.gitkeep
  experiments/            gitignored, LOCAL — never a symlink
  data/                   real dir, per-subdir symlinks below
  micromamba, hydromt_sfincs, *.sif  -> ~/nj_sandy_sfincs/...   (toolchain, as today)
```

**Archive symlinks (read-only bulk, never written):** `data/{elevation,roughness,infiltration,waves,era5,precip,wind,discharge,validation,wavemakers}` → `~/nj_coast_sfincs/data/...`, plus `data/frozen_mesh_v1_monmouth` (port verification only, deleted in Phase 7).

**Real local dirs (v1.5 writes here):** `data/NACCS/` (copy the 6 CHS zips + VDatum cache — Phase 4 *adds* zips), `data/gtsm/`, `data/quadtree/`, `data/region_v1_5_raritan.geojson`.

Do **not** bring `frozen_mesh_v2_barnegat` (2.7 G), `sfincs-env.tar.gz`, `notebooks/`, `reports/`, or `.git`.

**Rule, enforced by a test:** the archive is referenced for **data and docs only, never code**. Same rule `CLAUDE.md` already applies to the toolchain repo.

### Fix on import, don't inherit

- 🔴 **`$PROJ`.** The login profile exports `PROJ=~/nj_sandy_sfincs` (the *toolchain* dir) and `hpc/*.slurm` does `PROJ="${PROJ:-$PWD}"` — this already resolved to the wrong repo once. `PROJ` is **not read by the PROJ library** (that's `PROJ_LIB`/`PROJ_DATA`), so the export does no work. Replace every use with self-location: `REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"`. Add a runtime assert in `nj_sfincs/__init__.py` that `NJ_ROOT` resolves to the package's own parent. Ask the user to drop the profile export.
- **`.gitignore` ignores itself** in repo A, so a fresh clone gets none of it. Delete that line.
- Run `ruff format .` **once, in its own commit, before any logic edits** — this is the only moment it is free (nothing is frozen yet).

## Phase 3 — Port the code

**Verbatim** (~640 lines): `__init__.py` (the pyproj-before-hydromt_sfincs ordering is load-bearing — keep the comment), `gdaltools.py`, `run.py`, `report.py`, `animate.py`.

**Reworked:**
- `config.py` (1143 → ~450) — ⭐ **`EXPERIMENTS` becomes domain-scoped.** Today it's one flat namespace of ~31 arms and `--experiments all` on a fresh domain would attempt every one. Move to `nj_sfincs/experiments.py`, `dict[domain][arm]`. Seed v1.5 with **four** arms: `naccs-premier`, `naccs-nowaves`, `noaa-2node` (the incumbent, kept only to show what relocation bought), `naccs-premier-z15`.
- `validate.py` (1488 → package) — split `core.py` (floodmap + atomic cache + series helpers) / `metrics.py` (registry-driven). Delete `shrewsbury_gauge_peak` and `sandy_hook_bay_hm0`, generalize to `named_gauge_peak(dom, name)`. **Pin `estimator="median"` and stamp `hwm_estimator`/`hwm_radius_m` on every row.**
- `model.py` (~1139 → ~1000) — keep `_fill_inactive_holes`, `_inactive_components`, `check_waterlevel_support`, the `snapwave=0` branch, `restore_diagnostics`; every one is a scar. Rewrite `apply_mask_and_boundary` around boundary arms (Phase 5).
- `plots.py` (1545 → ~450) — keep the generic panel machinery parameterized on `dom.plot_window`/`dom.hwm_rules`; delete every named-place figure.
- `domain.py` / `premier.py` — keep both patterns, re-seed contents. Carry `premier.py`'s module docstring verbatim (it is the institutional memory of the void sweep). Keep `Bracket` with an **empty** `BRACKETS`. Drop `LEGACY`, `V2_BARNEGAT_PREMASK`, `NJ_TEMPLATE`.

**Dropped:** `wind.py` (per instruction), `params.py` (0 importers), the 13 zero-reference scripts, all three superseded boundary-builder generations, every `setup_*_template.py` except a rewritten `setup_v1_5_template.py`, `score_v2.py`, all v2-specific build scripts.

**`provenance.py`** comes over **and gets called from `model.finalize`**. If it isn't wired in by the time v1.5's template seals, delete it — an uncalled provenance module reads like coverage.

**~24 of 63 scripts import.** All `download_*` take their bbox from `dom.bbox_ll()`, so they re-target for free. Recover `setup_boundary_depth.py` from `docs/campaigns/retired_scripts/` — it's the mechanism for the −10/−15 pair.

## Phase 4 — Port verification (the gate)

A clean SLURM sweep once completed with plausible numbers and was scientifically void. The port is that failure mode again: new repo, refactored scorer, same-looking numbers.

Register `v1_monmouth` with `frozen=True`, fingerprint `(547408, 1635, 45f4f74ca9a2347d)`. **Copy** (don't symlink — the floodmap cache writes into it) one run dir: `experiments/v1_monmouth/faber-waves-premier`. **Do not re-run the solver** — scoring the same `sfincs_map.nc` isolates the `validate.py` port from any build question.

🔴 **Pin against `experiments/v1_monmouth/metrics.csv` as regenerated 2026-08-12, NOT
`reports/v1_monmouth/faber-waves-premier_rescored.csv`.** The July file is `hwm_n_scored=19`
with no estimator column; current code gives 38. Pinning to it fails on `n` alone and reads
as a port bug that isn't there.

| metric | target |
|---|---|
| `hwm_bias_scored_m` | −0.363106 |
| `hwm_rmse_scored_m` | 0.570499 |
| `hwm_n_scored` | 38 |
| `motf_csi` / `pod` / `far` | 0.637834 / 0.766245 / 0.208073 |
| `phase_lag_sandy_hook_min` | 17.6 |
| `gauge_peak_err_prefail_m` | −0.311682 |

**Tolerance: bit-for-bit** (`assertAlmostEqual(places=9)`). Same input, same code path,
deterministic arithmetic — any drift is a bug, not a tolerance. Carry `_V1_BASIN_RULES`
verbatim; per-basin numbers depend on first-match-wins ordering.

*Tier 2:* stage `faber-waves-premier` from the archived `_template_sealed` and assert the
fingerprint, `check_waterlevel_support == 2`, and an empty `sfincs.inp` diff. ~1 min, no solver.

**v1.5 work does not start until both tiers pass.**

## Phase 5 — Build v1.5

### 5a. The gate before any polygon

Two manual facts can kill the design; confirm both first:

1. **NACCS coverage** inside Raritan Bay, the Narrows, Arthur Kill and along the Sandy Hook→Rockaway cut. `build_naccs_boundary.py` keeps only points within 2.0 km of a `mask==2` cell and drops any point dry for even one step. If the Narrows or Arthur Kill has no wet save point within 2 km, fall back to 1-node-per-arm gauge forcing (Battery 8518750 for the Narrows, Bergen Point West Reach 8519483 for Arthur Kill) — defensible for two ~1 km cuts, unlike a 123 km gauge desert.
2. **At least two interior Raritan/Sandy Hook Bay gauges that survive the crest.** The whole claim is "Raritan Bay is computed, not forced"; if nothing inside can be scored, the claim is untestable. Sandy Hook 8531680 dies mid-storm and cannot be the answer alone.

⚠️ **The flanking-gauge convention breaks on v1.5.** The Battery sits ~10 km north of the Narrows — *immediately outside a forced boundary*. It stops being an independent holdout and becomes a forcing input. Rewrite that clause: flanking gauges are a forcing-product diagnostic only; the model holdouts are the interior Raritan gauges.

### 5b. Sequence

**Region polygon** — `scripts/build_region_v1_5.py`, named lon/lat vertices as module constants (coordinate boxes over auto-derived polygons). Ring segments tagged `ocean` / `land` / `narrows` / `arthur_kill`. Cut Arthur Kill at the **north** end (Kill Van Kull junction) so Perth Amboy / Carteret / Woodbridge stay computed — that's HWM-rich ground.

**Mesh + refinement** — new `refinement_v1_5_raritan.geojson`. Both existing recipes are wrong here (v1's gate would refine all of Raritan to 25 m; v2's polygons are 50 km south). L3/L4 on the two cuts and their approaches, L3 Sandy Hook Bay + Shrewsbury/Navesink, L2 Raritan open water, L0/L1 shelf. Size with `probe_mesh_size.py` **before** building — v2 at 1.14 M faces already needs 12 h for SnapWave.

**Subgrid + freeze** — the expensive irreversible step. Do the elevation check first: `nj_10ft_dem` is NJ-only, so Staten Island, the Rockaway shore and the Narrows fall through to CUDEM/3DEP. Add an invariant that **no active cell has NoData in the merged bed**.

**Mask + boundary — replace half-plane patches with an arm whitelist.**

```python
@dataclass(frozen=True)
class BoundaryArm:
    name: str                                 # ocean | narrows | arthur_kill
    box: tuple[float, float, float, float]    # ALL FOUR bounds required
    btype: str = "waterlevel"
    min_cells: int = 1
    max_cells: int = 10_000
    max_bed_m: float = -0.5                   # a BC cell must be WET
    why: str = ""
```

Order: `create_active` → region clip → **`land_boxes` → mask 0** (Staten Island, Jamaica Bay — declared, *not* DEM-dependent) → `_fill_inactive_holes` → `create_boundary` → **`mask==2` outside every arm box demoted to 1** → wet-outflow sealing.

This kills `arthur_kill_north` outright. That override flips `3→2` for everything north of `y=4,484,000` with **three unbounded sides** and today puts **70 BC cells on dry land**. Under the whitelist there is no override: Arthur Kill's BC cells exist because they're inside the arm box and must satisfy `zb <= max_bed_m` or the build fails. `MaskOverride.box` loses `None` from its type, making the whole defect class unrepresentable.

**Flux cross-sections** — `sfincs.crs` observation lines just *inside* each arm. SFINCS writes `crosssection_discharge` every 10 min, so you get Q(t) through the Narrows and Arthur Kill. **This is what makes the relocation auditable** — the Narrows carries the Upper Bay + Hudson prism, and a tidal prism is comparable against literature. Without it the new boundary is asserted, not measured.

**NACCS forcing** — `build_naccs_boundary.py` runs unchanged in structure. Two additions: report the screen **per arm** (aggregate coverage hides "0 points on Arthur Kill"), and emit a support-coordinate sha16.

### 5c. Build-time invariants

Carried: no free-outflow on water below −0.5 m; no interior inactive islands; no `mask==2` in a `NoWaterLevelBox`; no paved-over surveyed channel.

New: every `mask==2` inside exactly one arm box · per-arm cell count in `[min,max]` · every `mask==2` has `zb <= max_bed_m` · no active cell in a `land_box` · no NoData on an active cell · support count **and** geometry hash.

### 5d. The −10 / −15 pair

Two registered domains, **one frozen mesh** (`mesh_key="v1_5_raritan"`), staged via `setup_boundary_depth.py` which re-derives mask + boundary at the new depth and reuses subgrid tables — no rebuild, and subgrid is the dominant compute. Two fingerprints with identical `n_faces`/`n_boundary_edges` differing **only in `sha_z_mask`** — exactly the V2/PREMASK situation, so carry that test retargeted.

`mask_zmin` moves from `BaseConfig` to `Domain` (via `default_factory`). `add_waves` also reads it for the SnapWave seaward band and will follow automatically — state that in the docstring.

## Phase 6 — Docs (2 files, per your choice)

The complaint is right and the cause is diagnosable: `docs/campaigns/` is a reverse-chronological log, so the reader reconstructs current state by replaying history. **Summarizing 5,700 such lines produces 1,500 such lines. Change the genre.**

- **`ARCHIVE.md`** (~60 lines) — repo A path + pinned commit sha, the read-only rule, then a **26-line index**, one line per campaign log. Copy the table of contents, not the contents.
- **`docs/FINDINGS.md`** (~200 lines) — current state only, no history, no retractions. Sections: (1) the ~17 **general** findings that transfer to any NJ domain — HWM `max`-estimator artefact, depth-threshold masks are topological not elevational (4 instances now), free-outflow on deep water is a drain, the Cape May trap, a third support point perturbs a two-node line, SnapWave X1 = dry cells, eHydro sign flips by USACE district, diff `z_volmax` not `z_zmin`, MOTF is a bathtub of the HWMs, waves-off ⇒ extent inadmissible, the bracket/pre-registration/paired-bootstrap method, disk quota never says "quota", truncated floodmap caches read clean, `zb` is NaN on inactive faces, SnapWave is 90–95% of runtime; (2) the v1.5 design record — why the boundary moved, the region vertices, the three arms, the SI bank; (3) NACCS construction — the CHS portal query **verbatim** so the manual grab is reproducible, the four parsing traps, the 2 km screen, VDatum per point, steric already applied.
- **`docs/STATUS.md`** (~60 lines) — live campaign state, replacing the 12 KB memory file. **This is what the memory store should stop holding.**
- Arm-naming convention folds into `CLAUDE.md §Conventions`. **The frozen v1 scoreboard is dropped** — n=19, `max` estimator, non-comparable to anything current.
- `docs/roadmap.md` (232 lines) — drop. The one live item ("march south to Cape May") is three lines in `CLAUDE.md`.

**Discipline that keeps it small:** a new investigation edits `STATUS.md` in place. Git has the history.

### Memory store rebuild
Rewrite from scratch pointed at the new repo. **Numbers come out of `MEMORY.md`** — a measurement in the index gets quoted without the conditions that make it true, which is exactly how γ 0.86–0.89 (an ERA5 wave-source property) got read as a boundary-depth property this session. One line per memory, hook only.

## Phase 7 — Retire v1_monmouth

One commit deleting the registry entries, the mesh symlink, the run dir and the temporary test, titled so the reason is legible in a year.

---

## Verification

**Tests** (~40, stdlib `unittest`, no pytest, <30 s, no writes into `experiments/`).

Carried verbatim — each is a paid-for scar:
- ⭐ `test_domain_is_checked_before_anything_destructive` — **including the spy-on-rmtree/copytree mechanism**. The *ordering* is the property, not the end state. This is the 2026-08-05 data-loss regression.
- `test_check_template_domain_touches_nothing`, all of `TestFingerprints`, all of `TestWavesOffIsWrittenNotAssumed`.

Changed:
- `test_domain_default_is_still_two_everywhere` → **`test_support_counts_match_pinned_table`**. It asserts a *constant* where it meant *stability*; v1.5 has hundreds of NACCS points. Replace with an explicit `PINNED_SUPPORT` dict, never computed from the `Domain` object (that makes it tautological — what a relaxed assertion always becomes).
- `test_frozen_mesh_declared_per_domain` → `mesh_key`-aware, plus an assertion that a `mesh_key` sibling must differ in `mask_zmin`, so it can't become a general escape hatch.

New: `test_mask_override_boxes_are_fully_bounded` (the `arthur_kill_north` regression) · `test_boundary_arms_fully_bounded_and_disjoint` · `test_land_boxes_declared` · `test_experiments_are_domain_scoped` · `test_all_sweep_requires_confirmation` · ⭐ `test_no_proj_env_in_hpc` · ⭐ `test_no_code_references_the_archive` · `test_hwm_estimator_default_is_median`.

**End to end:**

```bash
export PATH=$HOME/nj_sandy_sfincs/micromamba/envs/sfincs/bin:$PATH   # git lives here
cd ~/nj_bight_sfincs && export PYTHONPATH=$PWD

python -m unittest discover -s tests -v
python -m nj_sfincs.premier
NJ_DOMAIN=v1_5_raritan python scripts/validate_domain.py
python run_experiments.py --experiments naccs-premier --check          # READ-ONLY
python run_experiments.py --experiments naccs-nowaves --tstop 2012-10-29
python run_experiments.py --experiments naccs-premier --slurm --slurm-args "--time=12:00:00"
python run_experiments.py --validate-only
```

Read off the build log rather than assuming: `_report_waterlevel_boundary`'s per-band table across the Sandy Hook→Rockaway cut (Ambrose Channel is dredged to ~−16 m and crosses it — same geometry as the Barnegat gorge); per-arm BC counts; the per-arm NACCS screen. After the run, **the Narrows and Arthur Kill Q(t)** — the tidal prism is the one number that says the relocated boundary is physically right rather than merely legal.

---

## Open, deliberately not decided here

- **STWAVE vs CORA waves.** Already the planned single-variable arm (`tide-naccs+wave-naccs`); STWAVE was withheld to avoid moving two variables at once. Same logic says don't bundle it with a domain move. CORA-as-wave-boundary is *adopted* settled physics (admissible 7/7 support points vs ERA5's 1/7).
- **The +0.027 m setup problem.** The premier generates only +0.027 m of setup from the −10 m boundary to shore with waves on — far too small, and an open thread. It bears directly on whether a deeper boundary buys anything.
- **`south_coast`.** 4 of 38 marks are hydraulically disconnected from the boundary and contribute a fixed −0.53 bias / 0.785 RMSE to every arm. Flagged in `config.py` *before* results landed, so excluding them is a pre-flagged re-analysis. Likely why `within 0.5 m` moves hard while RMSE barely does.
