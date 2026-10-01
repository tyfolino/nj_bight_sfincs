# nj_bight_sfincs — read this first

SFINCS compound-flood hindcast of **Hurricane Sandy (28–31 Oct 2012)** on the New York
Bight, built with HydroMT-SFINCS. Compound = surge + wave setup + wind + rain + river
discharge together, validated against NOAA/USGS gauges, USGS high-water marks and the FEMA
MOTF surge extent.

This repo is a **fresh start**. Everything before 2026-08-13 is in `~/nj_coast_sfincs`,
frozen and read-only — see [ARCHIVE.md](ARCHIVE.md). What is believed true *now* is in
[docs/FINDINGS.md](docs/FINDINGS.md); what is happening now is in
[docs/STATUS.md](docs/STATUS.md).

---

## 1. What this repo is for, and where it stands

A Sandy compound-flood hindcast of the New Jersey coast that holds up against the gauges,
the marks and the MOTF extent, built domain by domain (§2). **v3** (Cape May → the Narrows)
is DONE and is the reference. **v4** (v3 + Delaware Bay and river, the Raritan to Manville,
Newark Bay; the far banks computed) is frozen but PARKED while two things are re-decided
(user, 2026-09-30): **where rivers are cut** (today's head of tide, the gauge, the Sandy
+3 m rule, or whole watersheds) and **how waves are represented** (SnapWave is ~97 % of the
wall time, FINDINGS §20). STATUS has the plan; nothing about the domain changes until the
user picks from the decision memo.

**The lineage's founding argument, still the rule for how to argue a boundary:** the
predecessors ran the water-level boundary *through the middle of Raritan Bay*, forced by a
linear interpolation between two NOAA gauges that both sit outside it. NOAA harmonics say
the interior tidal maximum is real — 0.732–0.761 m, exceeding both exterior anchors — and an
interpolation between two outside points **structurally cannot** produce an interior
maximum. `v1_5_raritan` moved the boundary to the Narrows and the Arthur Kill mouth; v3 and
v4 keep Lower, Raritan and Sandy Hook Bays computed.

🔴 **That case is STRUCTURAL and must be argued that way.** The measured waves-on comparison
that motivated the move does **not** separate the two candidate boundaries: ΔRMSE −0.042 m,
95% CI [−0.238, +0.137], P = 0.706 on 38 marks. Quote the geometry, not that margin.

## 2. The one thing that will bite you: domains

Every geographic fact lives in **`nj_sfincs/domain.py`**, keyed by the `NJ_DOMAIN` env var.
🔴 **`NJ_DOMAIN` has NO default (2026-10-01)** — `domain.active()` and the hpc scripts refuse
to run until it is set; tests that need *a* domain declare the `v1_monmouth` fixture.

| `NJ_DOMAIN` | what | status |
|---|---|---|
| `v1_monmouth` | Sandy Hook → Sea Girt, 547,408 faces | **FROZEN** — port-verification fixture only |
| `v1_5_raritan` | boundary relocated to the Narrows + Arthur Kill | **FROZEN 2026-08-14** — `faces=696230 boundary_edges=1652 sha=2a23667dd16e449c`, three arms run + scored (see STATUS) |
| `v3` | full NJ ocean coast, Cape May → the Narrows, NACCS boundary | **DONE 2026-09-24** — `faces=3412470 boundary_edges=4108 sha=1596ce1ecc71b374` (mask repaired 09-22); reference = `naccs-premier` (FINDINGS §50) |
| `v4` | v3 + Delaware Bay and river to where Sandy +3 m ends (Washington Crossing; forced at the mouth) + the Raritan to Manville + the Arthur Kill shore **and Newark Bay**; **far banks (DE/PA/Staten Island) COMPUTED, not walled**; Track C coarse shelf | **FROZEN 2026-09-28, PARKED 2026-09-30** — `faces=4881654 boundary_edges=4388 sha=23ea65f8b81ee1bd` (after the freeze, on the same mesh: 4 Elizabeth-crossing faces walled, then 193 forced-line-end + Henlopen-Atlantic outflow faces, then 5 Darby Creek faces; FINDINGS part 4); the forced boundary is the DRAWN line `data/v4_design/waterlevel_line_v4.csv` (7 arms, NACCS 241 points), the ring `data/v4_design/region_v4_vertices.csv` (194 named vertices; edit by hand, check with `scripts/audit_region_v4.py --ring <csv>`); first runs = the design gate, waves-off Sandy at +0/+2/+3 m (`naccs-nowaves+rain-off+slr-*`, read with `scripts/overflow_check.py … --compare`) — STATUS |

**The same experiment name exists on every domain and means a different model each time.**
That is why runs live at `experiments/<domain>/<arm>`, why `EXPERIMENTS` is keyed by domain
in `nj_sfincs/experiments.py`, and why `nj_sfincs/premier.py` checks a **fingerprint**
(`faces`, `boundary_edges`, `sha256(z, mask)`) rather than trusting a name.

That guard exists because a full SLURM sweep once completed cleanly, with plausible
numbers, and was **scientifically void** — it had been staged from the wrong template. The
open coast is nearly domain-independent, so the coastal control *passed*, while the estuary
the experiment was about was 30% down in tidal range. Read `premier.py`'s module docstring
before touching staging.

```bash
NJ_DOMAIN=v3 python -m nj_sfincs.premier       # audit every run dir on that domain
NJ_DOMAIN=v1_monmouth python -m nj_sfincs.premier
```

🔴 **`mask_zmin` is HALF OF THE FINGERPRINT, so boundary depth is a DOMAIN axis, not an arm
axis.** An "arm" that changed it would fail `assert_sealed_domain` on its own staged copy.
A −10 m and a −15 m boundary are two registered domains sharing one `mesh_key`, staged with
`scripts/setup_boundary_depth.py`. Their fingerprints differ **only in the sha** — identical
face and boundary-edge counts — so you cannot tell them apart by counting anything.

## 3. Layout

```
nj_sfincs/          the package
  domain.py         ⭐ ALL geography. Add a domain here, not as literals elsewhere.
  premier.py        ⭐ the fingerprints. The staging guard.
  restart.py        resume a preempted solve from its restart file + stitch the segments
  experiments.py    the arm registry, KEYED BY DOMAIN
  config.py         BaseConfig + WaveConfig + Experiment; exp_root()
  model.py          build_static / add_forcing / add_waves / finalize
  validate/         core.py (floodmap + caches + series) · metrics.py (the scores)
  plots.py animate.py provenance.py run.py report.py gdaltools.py
run_experiments.py  the sweep driver (stage → run → validate → aggregate)
scripts/            flat, indexed in scripts/README.md (a hygiene test keeps them in step)
experiments/<domain>/<arm>/     run dirs (gitignored; SYMLINK → /scratch/tpj8 — NOT backed up,
                                 files unread for 90 days are purged; STATUS "Disk")
data/               per-subdir symlinks into the archive for bulk; NACCS/ gtsm/ quadtree/ local
docs/FINDINGS.md    ⭐ what is believed true NOW. No history, no retractions.
docs/STATUS.md      ⭐ the live campaign state (≤ ~300 lines; the old log is git history).
logs/               gitignored; dated campaign dirs + logs/slurm/<yyyy-mm>/ for job stdout
ARCHIVE.md          the frozen predecessor + an index of its 26 campaign logs
```

## 4. Running things

```bash
export PATH=$HOME/nj_sandy_sfincs/micromamba/envs/sfincs/bin:$PATH   # git lives here too
export PYTHONPATH=$PWD

python -m unittest discover -s tests            # ~240 tests, ~30 s on a compute node
python scripts/verify_port.py                   # ⭐ the port gate (see STATUS)

python run_experiments.py --experiments <arm> --check       # READ-ONLY
python run_experiments.py --experiments <arm> --slurm --slurm-args "--time=12:00:00"
python run_experiments.py --experiments <arm> --validate-only
```

⚠️ **This session may be on a LOGIN node** (`hostname` = `amarel*`). Anything heavier than
a grep — scoring, floodmaps, figures, the test suite — goes through `srun` on an
allocation (`salloc --no-shell -p main --exclude=halk[0001-0159] …`, then
`srun --jobid=<id> --overlap …`). A v3 paired score peaks at ~121 GB.

⚠️ **`--tstop` cannot run on a sealed template** (a window change makes the driver try to
rebuild it, and the seal refuses). For a short window on a finished run use
`scripts/engine_gate.py make <run> <dst> --hours H` (outside `experiments/`).

🔴 **`--check` is the ONLY read-only mode.** `--inputs-only`, `--no-run` and the deprecated
`--dry-run` all `rmtree` each experiment directory before skipping the solver. Reading "dry
run" as "touches nothing" destroyed 1.8 GB of solver output once;
`tests/test_domain_and_staging.py` now pins the ordering that prevents it.

⚠️ **`--experiments` has no default and `all` needs `--yes`.** A bare invocation used to be
a full destructive sweep.

✅ **Preemption is survivable since 2026-09-10.** `main` preempts (two 40 h solves lost 21 h
and 19 h in one second). Every arm staged since **2026-09-12** writes `sfincs.YYYYMMDD.HHMMSS.rst`
every 6 h (`dtrstout = dtmaxout = 21600`, set per arm by `model.restore_diagnostics` —
🔴 between 09-10 and 09-12 only HAND-ENABLED arms had it: the sealed template predates the
hook and staging copies its inp; check `grep dtrstout <dir>/sfincs.inp` before a long submit), and `hpc/sfincs_run.slurm` asks
`nj_sfincs/restart.py` on every start: a requeue **resumes** from the newest restart file,
parks the earlier output in `restart_segments/`, and **stitches** one `sfincs_map.nc` /
`sfincs_his.nc` afterwards (`restart_history.txt` records it). `python
scripts/sfincs_restart.py plan <dir>` is read-only; `enable <dir>` retrofits a staged dir.
🔴 `dtmaxout` must divide `dtrstout` — the stitch keeps whole `zsmax` blocks only. A job
submitted BEFORE 09-10 runs the old spooled batch script: it still restarts from scratch,
resume it by hand (`prepare`, then `run.submit_slurm`). Measured on the toy model: the
resumed trajectory differs from the uninterrupted one by ≤ 0.2 mm (p90), 8 mm max on a
2 cm wetting front, mean −0.08 mm — the same size as changing `tstop` alone.

⚠️ **Submit the STAGED dir via `run.submit_slurm(dir, sif=... | binary=...)`, not
`--slurm`,** when you have already staged. 🔴 **The engine is always explicit (2026-09-11):**
exactly one of `sif` (container) or `binary` (a native build from
`hpc/build_sfincs_native.sh`) — `run.py` and `hpc/sfincs_run.slurm` both REFUSE a run with
none or both; the old fallback to `sfincs-cpu.sif` (Galibier v2.4.0, NOT the premier's Faber
v2.3.3) is gone. `SFINCS_BIN=<path>` in the environment makes the sweep driver and
`stage_and_submit_v3.slurm` use the native engine. Every finished run gets `engine.txt`
(label `sif:<stem>@<sha8>` / `bin:<variant>@<sha8>`, Build-Revision, host, job) and
`metrics.csv` carries `engine`, `snapwave_direction` (`wind` = the FINDINGS §43 bug) and
`subgrid` on every row.

⚠️ **`build_template()` calls `rmtree` on its target.** It refuses when the template is
already sealed for the active domain, but a template whose fingerprint has *drifted* does
not trip that guard. Do not run the sweep driver to "just rebuild" a template.

## 5. Traps that have actually cost runs

- 🔴 **A ported refinement recipe silently drops polygons, and nothing catches it.**
  `refinement_v3.geojson` was built without v1.5's `bay_fringe` / `shrewsbury_navesink` /
  `coastal_corridor` bands — the bay margin ran at 50 m where v1.5 had 25 m, the wave
  setup there changed by +0.5 m, and all three 08-27 v3 arms were voided (STATUS 08-31).
  Every guard passed: the fingerprint seals whatever mesh you built, not the one you
  meant. When a new domain claims comparability with a predecessor, **diff the two
  refinement polygon LISTS by name** before freezing — and the predecessor's Domain FIELDS,
  boxes and discharge list: v3 also silently lost v1.5's always-active / dry-land /
  no-water-level boxes, its Raritan sources and `open_coast_max_y` (FINDINGS §58i). Also: staging's transient is ~3
  full template copies BEFORE `dedupe_experiment_inputs` runs — budget ~25 G free.
- **A roughness or elevation change needs a SUBGRID rebuild on the frozen mesh.**
  `build_static` copies the frozen mesh and returns early, so it will silently produce a
  no-op template. A *mask* change is the opposite: no subgrid rebuild, but the fingerprint
  moves.
- **For any bed edit, diff `z_volmax`, not `z_zmin`.** A carve restores sub-cell relief; it
  is not a uniform lowering, and `z_zmin` shows ~nothing while the run changes. For a
  building BURN read `z_level` instead (FINDINGS §15).
- 🔴 **Do not PREPEND a burn raster (footprints, walls) to the elevation list.** hydromt's
  `merge_multi_dataarrays` forces BILINEAR on every tier but the first, whatever
  `reproj_method` says, so a NoData-edged raster grows by a pixel at full height; and the
  FIRST tier defines the lattice every later tier is regridded onto, so the premier's own
  pixels move (v3, 2026-09-04: 1.25 M faces got a new `z_zmin`, 29 by > 1 m, from a tier
  that touched 12% of cells). Use `scripts/rebuild_subgrid.py --overlay`, which runs the
  premier's merge untouched and paints the raster on top with nearest. STATUS 09-04.
- 🔴 **The v3 subgrid rasters are ROTATED.** `experiments/v3/_template_sealed/subgrid/*.tif`
  are written on the quadtree frame (rotation 359.183°): the GeoTIFF transform has b, d ≠ 0.
  Any code that maps pixels to coordinates with `x0 + col*res` is wrong by up to 3 km at
  the far end of the domain — the first wavemaker line (2026-09-17) ran through land and on
  the wrong side of the barrier islands. Go through the affine (`~transform`,
  `rasterio.sample`); rioxarray's "non-rectilinear or with rotation" warning is that fact.
  ⚠️ The run dir's `floodmap_hmax_lev3.tif` and `subgrid/dep_subgrid_merged.tif` are on that
  frame too; the de-rotated product is `experiments/v3/floodmaps/<arm>_hmax_lev3.tif`. A
  scorer that samples them with `x0 + col*res` reproduces the premier's CSI as 0.572
  instead of 0.706 and finds an EMPTY beach band (2026-09-20) — a self-check against the
  published row is what caught it (a correct affine sampler reproduces it to 3 decimals,
  not 4; arm-to-arm deltas to 4). ⚠️ `rasterio` `read(window, boundless=True)` on a rotated
  raster returns pixels from the WRONG PLACE (v4's first scoring bed: 47 of 54 sampled
  pixels wrong, +8.2 m on the −15.2 m Delaware channel; FINDINGS §37) —
  `build_merged_subgrid_dep.py` now spot-checks its output.
- **eHydro sign convention flips by USACE district.** New York district ships negative
  elevations; Philadelphia ships positive depths. A hardcoded formula produces a silently
  empty raster on the wrong side.
- **`nj_10ft_dem` is NEW-JERSEY-ONLY.** Any domain reaching Staten Island, the Narrows or
  the Rockaway shore falls through it to CUDEM/3DEP. `build_static` now asserts no active
  cell has NoData in the merged bed. 🔴 **That assert cannot see a FILL:** CUDEM holds
  non-tidal water as a flat ~0 m surface (fake pits under lakes and above-tide rivers),
  holds the water SURFACE on the upper Passaic / Hackensack, and backfilled Ward Point as
  bay; GMRT at 50 m sits under every gap and is ~5 m shallow in dredged channels. Only an
  independent product or a POSITIVE check (declared dry-land boxes) finds a bed that is
  present and wrong. FINDINGS §54.
- 🔴 **A ring audit on a coarse bed cannot see a narrow channel.** A 75 m walk missed a
  110 m Cape May Canal crossing; v4's audit on the 25 m coarse bed missed Darby Creek, which
  drained the +2/+3 m water until walled. Walk creek and canal crossings at 10 m on 1/9″
  CUDEM, and let the SLR gate runs be the real sweep. FINDINGS §58f.
- **Bridge decks:** lidar puts a deck on the bed and the model reads a causeway as a dam
  (the Shrewsbury lesson). Sweep the MERGED bed for ridges across wet channels BEFORE a
  freeze — a dam found after it is a new domain. FINDINGS "Closed".
- **Import `pyproj` before `hydromt_sfincs`** — `nj_sfincs/__init__.py` does this; it
  prevents a native double-free in `downscale_floodmap`.
- 🔴 **The `halk*` nodes write to `/cache/home` LATE, and their late writes CLOBBER a good
  run.** ⚠️ 2026-08-20 Amarel merged `main-redhat` INTO `main`; submitting to
  `main-redhat` now fails outright. All 159 `halk*` nodes are in the DEFAULT partition
  now, so this trap is closer to hand, not further. `hpc/sfincs_run.slurm` sets
  `#SBATCH --exclude=halk[0001-0159]`; **an `sbatch` that bypasses that script is unprotected.**
  First thing to check when output looks wrong: `sacct -j <id> --format=NodeList`.
  ⚠️ **Some halk jobs produce nothing** (exit `COMPLETED 0:0`, no output, not even a SLURM
  stdout file) — that is the 2026-08-14 signature and it merely wastes a slot. **Others write
  partial output whose flush lands HOURS OR DAYS later, on top of whatever ran after them in
  the same run dir.** On 2026-08-15 that destroyed all three v1.5 arms: the good `hal*` runs
  had completed correctly on 08-14, and ~25 h later the dead halk jobs' buffered writes
  overwrote them with 12–86% of the window and, on two arms, an all-fill `zsmax`. Re-running
  the same arm on a halk node and then a good node is enough to trigger it.
  🔴 **The tell is timestamps, and it is invisible to `ls`:** the clobbered file carries the
  *halk* job's mtime, so it never looks stale. Compare three clocks —
  `stat -c '%y %z'` (mtime, ctime) against `mmlsattr -L <f> | grep creation`. Creation
  matches the job that legitimately made the file, mtime belongs to the halk job that died
  before it, and ctime marks when the clobber landed.
  🔴 **The same lag runs the OTHER way from the VS Code session, which itself runs on a halk
  node** (`hpc/vscode_node.sh`; `squeue` shows `vscode` on `halk00xx`). A file edited there
  can read STALE — or EMPTY — on a compute node for a minute or more: on 2026-09-27 a job
  started 15 s after a script was created ran it as an empty file and **exited 0 in 0.4 s**,
  and the job before it ran the pre-edit version. Submit with a checksum:
  `md5sum <files> > logs/<job>_expected.md5; EXPECT_MD5=logs/<job>_expected.md5 sbatch …`
  (`hpc/build_coarse_bed.slurm`, `hpc/clip_nj_dem.slurm` honour it), or wait a few minutes.
- **Disk quota exhaustion never says "quota".** It SIGSEGVs jobs or silently truncates
  output maps while `sacct` reports COMPLETED. Home is **GPFS, 100 G soft / 110 G hard**, and
  `quota -s` prints nothing — ask `mmlsquota -u $USER --block-size auto cache`
  (in `/usr/lpp/mmfs/bin`, not on PATH). 🔴 **Never probe headroom by `dd`-ing to ENOSPC**:
  it starves any job that is starting, and the wreckage is indistinguishable from the `halk`
  trap above. Reclaim with `scripts/dedupe_experiment_inputs.py` (within a domain) or
  `scripts/dedupe_home.py` (across all four data roots — it hard-links, never deletes, so it
  is safe to point at the frozen archive; 20 GB the first time). `mmlsquota` lags ~10 min
  after a dedupe, and after hard-linking `du` counts shared inodes — measure a trim by
  `st_nlink`. `snapwave.upw` is a rebuildable runtime table (safe to delete); a
  `*_hmax_lev3.tif` is re-downscalable from a surviving `sfincs_map.nc`.
- 🔴 **Do not score or plot a run until the audit says `output WHOLE`** (`python -m
  nj_sfincs.premier`). A run read mid-write looks like a plausible catastrophe (v1.5:
  "median −1.87 m, 20 of 46 dry, CSI 0.20" — the output stopped 0.7 h before the crest).
- **`sacct MaxRSS` is a 30 s sample and under-reads a fast OOM** (a render killed at 100 G
  read 32 G). Scorer rasters ACCUMULATE across arms in one process: three v3 arms OOM at
  128 G where one fits; the v3 HWM panel figure peaks at 165 G for six arms.
- **A truncated floodmap cache reads back clean and scores bone-dry.** Writes are atomic
  now; do not weaken that.
- **SnapWave is ~97% of runtime** (FINDINGS §20; `scripts/snapwave_cost.py` reads it off a
  log); the 3 h batch default is not enough for a large domain. Pass `--slurm-args "--time=12:00:00"`.
- 🔴 **A wind-on SnapWave solve on v3 needs the FAST nodes** (confirmed 2026-09-13 on the
  full 73 h run): 3.3 sim-h per wall-h on `emeraldrapids` (21 h 55 total) vs 0.98 on
  `icelake` (`hal02xx`) → ~74 h, past the 40 h limit, and a TIMEOUT is NOT auto-requeued
  (`--requeue` covers preemption only). Submit with `SOLVE_CONSTRAINT=emeraldrapids`
  (`hpc/stage_and_submit_v3.slurm`) or `--constraint=emeraldrapids`; check `sacct
  --format=NodeList` before believing a pace. It is per-core speed plus cap-hits, not
  threading: the SnapWave node sweep is SERIAL (FINDINGS §20), so every finished 64-thread
  solve used 5.9–6.8 effective cores. ⚠️ 3.3 was F.4 (IG off, `fw 0.02`,
  no buildings); the PREMIER config paces 2.2–2.6 on the same nodes (09-14) — budget
  33–36 h. Read pace from the restart-file mtimes: a SnapWave call over 999.99 s logs
  `took ****** seconds` (Fortran overflow), so summing the `took` field drops the slowest calls. ⚠️ And check
  `scontrol show reservation` first: the monthly maintenance takes every hal node for ~40 h,
  (next: 10-13, 11-10, 12-15, 08:00 → next day 23:59),
  and a job whose time limit overlaps it will not START (`Reserved for maintenance`) —
  ~1.5× the measured pace is enough, and users may shorten a queued job's limit with
  `scontrol update JobId=<id> TimeLimit=<h>:00:00` (only an increase is refused).
- **`zb` is NaN on SFINCS-inactive faces**, so any hm0 comparison must restrict to faces
  active in *both* runs.
- 🔴 **`da_dep` is valid on ground the model never simulated**, so `dep > 0` is NOT a
  "was this cell in the domain" test — the subgrid DEM covers the whole grid RECTANGLE.
  And **`downscale_floodmap` BLEEDS**: it paints zsmax onto low ground under INACTIVE
  faces, so a floodmap shows water the solver never computed (v1_monmouth: 3.68 km², up
  to 1.45 km outside the mask). Screen spatial metrics with `validate.simulated_mask`,
  which reads the run's own `msk` — **not** a region polygon, which is a build input the
  mask legitimately grows past. FINDINGS §37.
- 🔴 **A NetCDF `inifile` is read as raw BINARY by our SFINCS** (`nchar` never assigned in
  `sfincs_initial_conditions.F90`), and `zsini` alone floods every disconnected low spot
  below it. A start other than the template's goes through `nj_sfincs/sea_level.py`
  (binary `real*4`, active points in face order, sea-connected through the subgrid sills).
  FINDINGS §51.
- **An HWM records that water ARRIVED, not which way it came in.**
- ⚠️ **A station or mark within ~500 m of a discharge source reads the INJECTION, not the
  basin.** `rb_axis_559k` sits 253 m from the Raritan source (Qmax 110 m³/s) and carries a
  single-face, sub-2-minute **1.33 m** `zsmax` spike its own 60 s series never sees;
  neighbouring faces do not share it. `scripts/source_proximity.py` computes the distance
  from every staged source to every mark and gauge, as a flag column, not a filter
  (v1.5 0 of 46, v3 1 of 140 — HWM 6044, v4 0 of 166) — **re-check on any new domain**,
  because it is a per-domain fact. FINDINGS §40.

## 6. Conventions

- Domains are registry entries; arms are `naccs-premier` plus `wave-`, `tide-`, `solver-`,
  `mask-`, `bed-` deltas; unions joined by `+` in alphabetical order; a deliberately
  inadmissible bound is prefixed `BRACKET+`.
- **The user commits and pushes. Claude may `git add`, never `git commit`.**
- 🔴 **Never quote an HWM bias without its estimator and radius.** The estimator alone flips
  the sign of the bias and inverts the ranking of every arm. Use the `_scored` keys.
- **Which MOTF raster a domain scores, and where that raster is VALID, are DOMAIN facts**
  (`Domain.motf_tif`, `Domain.motf_exclude_boxes_ll`). The source layer is NJ-only and
  renders NY land as confidently dry — quote `motf_km2_excluded_boxes` beside any CSI.
  The FA decomposition keys (`motf_far_connected` etc.) are diagnostic, reported beside
  the headline keys, never instead. FINDINGS §37–38.
- ⚠️ **A waves-off arm's CSI / POD / FAR are KEPT and flagged** `extent_admissible=False`
  — waves-off is a legitimate configuration, not a broken one. The caution is against
  RANKING one against a waves-on arm: on v1.5 SnapWave is worth ΔCSI 0.018, against
  ΔCSI 0.011 between the two waves-on arms (container engine, waves misdirected —
  FINDINGS §43). FINDINGS §4.
- **Compare arms PAIRED** — bootstrap the per-mark differences, not the two pooled
  statistics (`scripts/paired_hwm_bootstrap.py`).
- **Write the pre-registration BEFORE running the scorer** — pick the diagnostic before you
  know which side it lands on. ⚠️ It is a helpful practice, **not a gate**: never block a
  run on writing one.
- **The flanking-gauge check is a forcing-product diagnostic, never a model diagnostic.**
  ⚠️ On this domain it changes meaning: the Battery sits ~10 km north of the Narrows —
  *immediately outside a forced boundary* — so it is a forcing INPUT, not an independent
  holdout. The model holdouts are the interior Raritan gauges.
- Prefer coordinate boxes and thresholds over auto-derived polygons.
- `ruff.toml` sets line length 88 and pins the lint select explicitly. Ruff IS in the
  sfincs env since 2026-09-17 (`micromamba install -n sfincs -c conda-forge ruff`), so the
  §4 PATH export finds it; the earlier copy in `~/.local/bin` was never on that PATH, which
  is why it "kept disappearing". Format the files you are editing, not the tree.
- A new investigation **edits `docs/STATUS.md` in place**. Git has the history. That
  discipline is what keeps the docs small; the previous repo grew 26 reverse-chronological
  campaign logs, and summarising 5,700 such lines only produces 1,500 such lines.
