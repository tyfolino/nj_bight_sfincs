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

## 1. What this repo is FOR

**Move the water-level boundary out of Raritan Bay.**

The previous domains ran their boundary *through the middle of Raritan Bay*, forced by a
linear interpolation between two NOAA gauges that both sit **outside** it. NOAA harmonics
say the interior tidal maximum is real — 0.732–0.761 m, exceeding both exterior anchors —
and a linear interpolation between two outside points **structurally cannot** produce an
interior maximum. That lobe was under-forced by construction, not by calibration error.

`v1_5_raritan` relocates the boundary so Lower Bay, Raritan Bay and Sandy Hook Bay are
**computed**: one ocean arm (v1's own Atlantic trace, extended ~3.3 km straight north to
Rockaway Point) plus two short forced cross-sections at **Verrazzano Narrows** and the
**Arthur Kill MOUTH**. Staten Island's south shore is a declared land boundary; Jamaica Bay
is excluded; no NYC land is in the model. v1.5 keeps v1's southern limit, lat 40.150.

🔴 **The case for it is STRUCTURAL, and must be argued that way.** The measured waves-on
comparison that motivated the move does **not** separate the two candidate boundaries:
ΔRMSE −0.042 m, 95% CI [−0.238, +0.137], P = 0.706 on 38 marks. The dense boundary wins
every point estimate and is **not a demonstrated win**. Do not quote that margin as the
justification; quote the geometry.

## 2. The one thing that will bite you: domains

Every geographic fact lives in **`nj_sfincs/domain.py`**, keyed by the `NJ_DOMAIN` env var.

| `NJ_DOMAIN` | what | status |
|---|---|---|
| `v1_monmouth` | Sandy Hook → Sea Girt, 547,408 faces | **FROZEN** — port-verification fixture only |
| `v1_5_raritan` | boundary relocated to the Narrows + Arthur Kill | **not yet registered** (see STATUS) |

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
python -m nj_sfincs.premier                    # audit every run dir on the active domain
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
  experiments.py    the arm registry, KEYED BY DOMAIN
  config.py         BaseConfig + WaveConfig + Experiment; exp_root()
  model.py          build_static / add_forcing / add_waves / finalize
  validate/         core.py (floodmap + caches + series) · metrics.py (the scores)
  plots.py animate.py provenance.py run.py report.py gdaltools.py
run_experiments.py  the sweep driver (stage → run → validate → aggregate)
scripts/            data acquisition, staging, scoring, verify_port.py
experiments/<domain>/<arm>/     run dirs (gitignored, LOCAL — never a symlink)
data/               per-subdir symlinks into the archive for bulk; NACCS/ gtsm/ quadtree/ local
docs/FINDINGS.md    ⭐ what is believed true NOW. No history, no retractions.
docs/STATUS.md      ⭐ the live campaign state.
ARCHIVE.md          the frozen predecessor + an index of its 26 campaign logs
```

## 4. Running things

```bash
export PATH=$HOME/nj_sandy_sfincs/micromamba/envs/sfincs/bin:$PATH   # git lives here too
export PYTHONPATH=$PWD

python -m unittest discover -s tests            # 54 tests, ~2 s
python scripts/verify_port.py                   # ⭐ the port gate (see STATUS)

python run_experiments.py --experiments <arm> --check       # READ-ONLY
python run_experiments.py --experiments <arm> --tstop 2012-10-29   # short-window smoke
python run_experiments.py --experiments <arm> --slurm --slurm-args "--time=12:00:00"
python run_experiments.py --experiments <arm> --validate-only
```

🔴 **`--check` is the ONLY read-only mode.** `--inputs-only`, `--no-run` and the deprecated
`--dry-run` all `rmtree` each experiment directory before skipping the solver. Reading "dry
run" as "touches nothing" destroyed 1.8 GB of solver output once;
`tests/test_domain_and_staging.py` now pins the ordering that prevents it.

⚠️ **`--experiments` has no default and `all` needs `--yes`.** A bare invocation used to be
a full destructive sweep.

⚠️ **Submit the STAGED dir via `run.submit_slurm(dir, sif=...)`, not `--slurm`,** when you
have already staged. Always pass `sif` explicitly — leaving it to the batch script's
fallback is how a sweep silently ran on the wrong engine.

⚠️ **`build_template()` calls `rmtree` on its target.** It refuses when the template is
already sealed for the active domain, but a template whose fingerprint has *drifted* does
not trip that guard. Do not run the sweep driver to "just rebuild" a template.

## 5. Traps that have actually cost runs

- **A roughness or elevation change needs a SUBGRID rebuild on the frozen mesh.**
  `build_static` copies the frozen mesh and returns early, so it will silently produce a
  no-op template. A *mask* change is the opposite: no subgrid rebuild, but the fingerprint
  moves.
- **For any bed edit, diff `z_volmax`, not `z_zmin`.** A carve restores sub-cell relief; it
  is not a uniform lowering, and `z_zmin` shows ~nothing while the run changes.
- **eHydro sign convention flips by USACE district.** New York district ships negative
  elevations; Philadelphia ships positive depths. A hardcoded formula produces a silently
  empty raster on the wrong side.
- **`nj_10ft_dem` is NEW-JERSEY-ONLY.** Any domain reaching Staten Island, the Narrows or
  the Rockaway shore falls through it to CUDEM/3DEP. `build_static` now asserts no active
  cell has NoData in the merged bed.
- **Import `pyproj` before `hydromt_sfincs`** — `nj_sfincs/__init__.py` does this; it
  prevents a native double-free in `downscale_floodmap`.
- **Disk quota exhaustion never says "quota".** It SIGSEGVs jobs or silently truncates
  output maps while `sacct` reports COMPLETED. Run `scripts/dedupe_experiment_inputs.py`.
- **A truncated floodmap cache reads back clean and scores bone-dry.** Writes are atomic
  now; do not weaken that.
- **SnapWave is 90–95% of runtime** and scales per-iteration; the 3 h batch default is not
  enough for a large domain. Pass `--slurm-args "--time=12:00:00"`.
- **`zb` is NaN on SFINCS-inactive faces**, so any hm0 comparison must restrict to faces
  active in *both* runs.
- **An HWM records that water ARRIVED, not which way it came in.**

## 6. Conventions

- Domains are registry entries; arms are `naccs-premier` plus `wave-`, `tide-`, `solver-`,
  `mask-`, `bed-` deltas; unions joined by `+` in alphabetical order; a deliberately
  inadmissible bound is prefixed `BRACKET+`.
- **The user commits and pushes. Claude may `git add`, never `git commit`.**
- 🔴 **Never quote an HWM bias without its estimator and radius.** The estimator alone flips
  the sign of the bias and inverts the ranking of every arm. Use the `_scored` keys.
- 🔴 **Waves off ⇒ CSI / POD / FAR / n_dry are INADMISSIBLE.** The runner drops them from
  the row and stamps `extent_admissible=False`. Score levels and phase only.
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
- `ruff.toml` sets line length 88 and pins the lint select explicitly. Ruff is *not* in the
  pinned env — install it separately. Format the files you are editing, not the tree.
- A new investigation **edits `docs/STATUS.md` in place**. Git has the history. That
  discipline is what keeps the docs small; the previous repo grew 26 reverse-chronological
  campaign logs, and summarising 5,700 such lines only produces 1,500 such lines.
