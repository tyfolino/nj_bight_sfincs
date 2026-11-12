# Poster Figure 4: power assets Sandy floods (2026-11-12)

## Files

| file | what |
|---|---|
| `fig4_power_2012bed.{png,pdf}` | **FALLBACK, done.** Sandy, Model 1.1.0 (2012 ground) against today's plants + substations |
| `fig4_power_2026bed.{png,pdf}` | **Made by job 63850177 when it finishes.** The same storm on 2026 ground, PRELIMINARY; rings = sites where the two runs differ |
| `exposure_poster.py` | the exposure read, NATIVE 3.125 m (see "Method") |
| `fig4_power.py` | both figures (`python fig4_power.py 2012` / `2026`) |
| `compare_2012_2026.py` | counts + every NJ site that changes state → `exposure/changes_2012_vs_2026.{txt,csv}` |
| `run_fig4_2026bed.slurm` | the chain job: check staged dir → solve → weir/drain counts → audit WHOLE → exposure → figure → compare → native floodmap |
| `exposure/` | `v110_2012bed_assets.csv` (+ `_faces.npz`); `v11_modernb_2026bed_*` arrive with the job |
| `job/` | stage logs, `expected.md5`, the job's stdout, `solve.log`, `structures.txt`, `audit.txt` |
| `weircount/engine_snap_overpeck_open.txt` | engine (float32) weir u/v count: **864** Overpeck open, 867 dam in (reproduces the 11-12 count) |

## Headline numbers (New Jersey, buildings-burned read at 3.125 m)

| | wet | dry | not computed | (out of model) |
|---|---|---|---|---|
| **2012 ground, Model 1.1.0** | **60** (34 plants, 26 substations) | **122** | **71** | 192 |
| **2026 ground** | from job 63850177 (`exposure/changes_2012_vs_2026.txt`) | | | |

Against the 11-09 read of the same run (6.25 m overview, 62 / 120 / 71 bare ground; 67 / 115 / 71 buildings burned):
the not-computed set is identical; the wet/dry flips are fringe sites with 1-7 wet pixels (mostly solar farms whose
coarse-pixel "wet" was an average of road and building), and rooftop solar (Westside Ave, EWR6, River Terminal …) that
the bare-ground read calls wet and the burned read cannot (the roof is the "ground"). Quote 60 as "about 60".

## The 2026-bed run

- **Arm** `bed-modernb+p4-premier+struct-pews-checkvalve+weir-elizabeth-rahway+weir-portmonmouth` on **`v4_refreeze_swz_v11`**
  (registered additively in `nj_sfincs/experiments.py`). **Pair = Model 1.1.0** (`p4-premier+weir-elizabeth-rahway`, same domain).
- **Job 63850177** (`main`, hal0328, 64 threads, 12 h limit; staged + checked 14:29, solve started 14:32 on 11-12;
  ~2.5-4 h solve + ~15 min read → figure ~17:00-18:30; a preemption RE-STAGES and re-solves from the start, never
  resumes). Engine log CONFIRMED at start: **864 structure u/v points**, **1 drainage point** (sfincs.drn). Output: job stdout
  `job/run_fig4_2026bed_63850177.out`, then `exposure/changes_2012_vs_2026.txt` + `fig4_power_2026bed.png`.
  ⚠️ The superseded job 63849792 writes the same `job/solve.log`, `structures.txt`, `audit.txt` names: read the run dir's own
  `sfincs.log` and the 63850177 stdout, not those, until 63849792 is cancelled.
- **Every difference from 1.1.0** (checked file by file on the staged dir, `job/stage_v11.log`):
  1. `sfincs_subgrid.nc` + `subgrid/` = **`_subgrid_modern2026b`** (2026 topo / bathy: 2023-25 lidar on land, latest
     eHydro + newer BlueTopo in channels, modern deck pass; built from v1.1c's base tiers WITH v1.1c's fixes, so
     developed-land n 0.04, deck_fix_v4b, riverbeds v4e, pools, nbi_open are in both). **Buildings (NJDEP footprints) and
     land cover / roughness are still 2012's** (modern b has no modern footprints or NLCD 2025). `roughness.nc` is identical.
  2. `sfincs.weir`: `sfincs_modern_overpeck_open_elizabeth_rahway_portmonmouth_ground.weir` vs 1.1.0's
     `sfincs_overpeck_open_elizabeth_rahway_ground.weir`. Same in both: the Keansburg system (incl. the Waackaack gate /
     Pews stop logs shut), the three NLD levee lines at NLD crest, the Overpeck bypass sill; Overpeck dam **OPEN in both**.
     Different: the Elizabeth / Rahway **ground-read lines re-tied to 2026 lidar** (Bayway wall, 3 tie-ins, 4 lidar sills,
     8 mesh guards: crests −3.0…+3.0 m vs 1.1.0's, 1 guard re-drawn; logs/walls_elizabeth_rahway_modern_2026-11-06/) + 3 new
     guards (m1, m2, a1) + the **Port Monmouth** C2 / C3 lines (levee, sheetpile, floodwall at +13 ft = 3.96 m) with the
     **Pews Creek tide gate and the Old Port Monmouth Rd gate SHUT** (logs/portmonmouth_2026bed_2026-11-12/).
  3. `sfincs.drn` (new): the Pews gate as a **type-3 check valve**, marsh → bay, Q = 100.4·√Δh; `sfincs.inp` gains
     `drnfile` + `storeqdrain` (the ONLY inp difference).
  4. Identical to 1.1.0: `sfincs.nc` (face z = 1.1.0's wave bed: SnapWave sees the same bed), wind / pressure / rain,
     water-level boundary, river inflows, SnapWave boundary + wavemaker, initial state, obs points, curve number, roughness,
     engine (`hpc/production_engine.txt`), 2012 sea level.
- So the asset flips are **differences between the two runs** = 2026 ground + today's walls / gates together, not ground alone.
- Modern b is an unvalidated bed (no 2026 observations to score against): the figure says PRELIMINARY.

## Method (`exposure_poster.py`)

Per asset footprint, pixel centres on a 3.125 m lattice; ground = the run's own bed **base band** (the old scripts read
the 6.25 m overview); water level = the face's zsmax (faces that never got 5 cm of water paint nothing); face must be
active (else NOT COMPUTED); depth counted only on **normally-dry ground** (`normal_surface.normally_wet`: mapped water,
lake pool, or below MHHW → "water", not land). Wet = any land pixel ≥ 0.15 m. Dry needs half the footprint on active
faces. Assets and the three-state rule are `scripts/power_exposure.py`'s (imported unchanged). Map shading = faces with
zsmax ≥ 0.15 m above the face's mean ground on normally-dry ground, binned at 300 m (a picture, not the count).

## Re-run by hand

```bash
cd ~/nj_bight_sfincs
set -x PATH $HOME/nj_sandy_sfincs/micromamba/envs/sfincs/bin $PATH; set -x PYTHONPATH $PWD; set -x NJ_DOMAIN v4_refreeze_swz_v11
# on a compute node (srun --jobid=<holder> --overlap -n 1 -c 4 --mem=40G …), ~2 min, ~3 G:
set R experiments/v4_refreeze_swz_v11/bed-modernb+p4-premier+struct-pews-checkvalve+weir-elizabeth-rahway+weir-portmonmouth
python -m nj_sfincs.premier $R                     # must say output WHOLE
python reports/poster_2026-11-13/exposure_poster.py $R v4_refreeze_swz_v11 v11_modernb_2026bed
python reports/poster_2026-11-13/fig4_power.py 2026
python reports/poster_2026-11-13/compare_2012_2026.py
```
(The 2012 fallback: `exposure_poster.py experiments/v4_refreeze_swz_v11/p4-premier+weir-elizabeth-rahway v4_refreeze_swz_v11 v110_2012bed`, then `fig4_power.py 2012`.)

## For the user

- **scancel 63849792**: the first 2026-bed run, on the 1.0.0 domain (`v4_refreeze_swz`, SnapWave on the 2012 1.0.0
  wave bed), superseded by the 1.1.0 twin. Then `rm -rf experiments/v4_refreeze_swz/bed-modernb+p4-premier+struct-pews-checkvalve+weir-elizabeth-rahway+weir-overpeck-open+weir-portmonmouth` (32 G; its registration is already removed).
- **Asset locations on a public poster:** the footprints are OSM-derived (`data/power_infra`). The figures name no site;
  decide whether exact substation positions are OK to print, or coarsen / drop the zoom panel.
- The old `scripts/power_exposure.py` and `export_share_floodmap.py` still read the 6.25 m overview (not touched: not
  needed here; `exposure_poster.py` replaces them for this figure).
