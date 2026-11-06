# Bed audit: shared format (2026-11-05)

User 11-05: "a defensible way of catching these issues with our bed on both the 2012 and modern bed, so we aren't so
reliant on patterns or visible inspection", plus "a way to catch anything that seems funky to flag for manual review".

One audit = several CHECKS. Each check compares a bed against an independent, authoritative layer (or, for the
anomaly checks, against the bed's own expected structure) and writes an EXCEPTIONS table. Eye review covers the
exceptions only; the user's calls on them are the record.

## Layout

```
logs/bed_audit_2026-11-05/
  SCHEMA.md                 this file
  checks/<check>/           one folder per check: its README.md (sources, licence, rule, threshold + why), its
                            script, its raw-data notes. Raw downloads go to /scratch/tpj8/nj_bight_sfincs_data/audit/<check>/
                            (scratch is near its soft quota: clip to the v4 box, keep each check's data < ~10 G).
  out/<bed_label>/<check>.csv   the exceptions, one file per check per bed
```

Each check is a script `checks/<check>/check.py` with the CLI

```
python checks/<check>/check.py --bed <subgrid dir> --label <bed_label> [--overlay-min <catalog key> ...] --out out/<bed_label>/<check>.csv
```

`--bed` is a subgrid dir (`experiments/v4_refreeze_swz/_subgrid_*`; the check reads `subgrid/dep_subgrid_merged.tif`).
🔴 Those rasters are ROTATED: sample through the inverse affine (`logs/decks_2026-11-04/common.py` `Bed`, or
`logs/modern_decks_2026-11-04/common_m.py` `EffBed` for "bed + a lower-only overlay"; import them, never edit them).

## The beds to run

| label | bed |
|---|---|
| `v1_1b` | `experiments/v4_refreeze_swz/_subgrid_v1_1b` (job 63577223, building 11-05). Until it exists: `_subgrid_v1_1` with `deck_fix_v4b` applied as a min (`EffBed`) |
| `modern` | `_subgrid_modern2026` + v1.1's deck overlay as a min (`common_m.EffBed(BED_MOD, Overlay())`, what the modern deck pass judged) |
| `p100` (optional reference) | `_subgrid_refreeze_lakes_min_creeks_cohansey` (Model 1.0.0's bed) |

## Exceptions CSV columns (all checks)

| column | meaning |
|---|---|
| `check` | the check's name (`impoundment`, `water_surface`, `channel_depth`, `crossing_nbi`, `levee_continuity`, `anomaly_*`) |
| `id` | stable id within the check (e.g. NID id, NCF reach id, NBI structure number, a hash of the location) |
| `lon`, `lat` | WGS84, the point to look at |
| `severity` | `high` / `medium` / `low` — high = changes whether the tide or a surge path reaches somewhere |
| `kind` | the specific failure (e.g. `impounded_lake_tidal_link`, `bed_shallower_than_authorized`, `water_surface_as_bed`) |
| `metric`, `value`, `expected`, `units` | what was measured, the bed's value, what the authoritative layer says it should be |
| `area_m2` | footprint of the exception, where it has one |
| `sandy_peak_m` | 1.0.0's Sandy peak nearby (`experiments/v4_refreeze_swz/p4-premier/sfincs_map.nc` zsmax), if relevant |
| `near_asset`, `asset_km` | nearest power asset (`logs/power_exposure_2026-11-02/`), if within 2 km |
| `source` | the authoritative layer + version / date |
| `note` | one plain-English line for the reviewer |
| `fix` | the proposed fix (overlay type, level), or blank if the reviewer must decide |

Severity, not count, sets the review order. A check that cannot decide says so (`kind = undecidable_<why>`) rather
than guessing.

## Ground truth for calibration

The user's eye checks: `logs/modern_decks_2026-11-04/user_decisions_2026-11-04.csv`, `..._2026-11-05.csv`,
`logs/underpass_sweep_2026-11-05/user_decisions_2026-11-05.csv`, the 11-04 v1.1 deck picker decisions in
`logs/decks_2026-11-04/`, and the known cases in docs/FINDINGS.md (§54 inland water, part 4 (l), (m)): Alloway Lake,
Silver Lake (E4), Manor Lake, Union Lake, the Overpeck, the Maurice GMRT fall-through, the Christina plug, Grays Ferry.
Every check reports which known cases it catches and which it misses.

## Out of bounds for all checks

No edits to `data/data_catalog.yml`, `nj_sfincs/*`, `run_experiments.py`, `hpc/sfincs_run.slurm`,
`scripts/paired_hwm_bootstrap.py`, `docs/STATUS.md`, `docs/FINDINGS.md`, or any existing data tier. No commit, no
sbatch. Heavy work via a one-shot `srun -p main --exclude=halk[0001-0159] -c 16 --mem=150G -t 3:00:00`.
