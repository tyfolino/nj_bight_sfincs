# Poster Figure 3: model flood extent vs FEMA's MOTF Sandy surge extent

## Files

| file | what |
|---|---|
| `fig3_motf.py` | the figure, parameterised by arm (`--arm`, `--stem`; domain from `NJ_DOMAIN`) |
| `fig3_motf.{png,pdf}` | **the poster figure**: 1.1.0's RAIN-OFF twin (`p4-premier+rain-off+weir-elizabeth-rahway`). Made tonight by job `63850142` once job 63843110 has scored that arm |
| `fig3_motf_standin_v110.{png,pdf}` | stand-in made 11-12 afternoon from Model 1.1.0 itself (`p4-premier+weir-elizabeth-rahway`, rain ON) |
| `fig3_rainoff_watch.slurm` | the watcher job (polls for the rain-off arm's `scored_ok`, then runs the script) |
| `logs/` | run logs (`fig3_standin_v110.log`, `fig3_rainoff_watch_<job>.out`) |

Class rasters (uint8, MOTF 15 m grid, codes in the tif tags) are cached in
`/scratch/tpj8/poster_2026-11-13/fig3/<domain>__<arm>__motf_classes.tif`; a second call reuses them
(re-plot in seconds after a layout tweak; `--reclassify` forces a rebuild).

## How the classification is done (same rules as the scorer)

`fig3_motf.py` reproduces `nj_sfincs/validate/metrics.py::motf_metrics` line for line, read-only:

- floodmap: `$FM_ROOT/<domain>/<arm>/floodmap_hmax_native.tif` (the 11-12 native 3.125 m re-score)
  if it exists, else the run dir's `floodmap_hmax_lev3.tif` **only if** native and fresh; otherwise
  it refuses. It never downscales and never writes into a run dir.
- opened through `validate.load_floodmap` (de-rotated through the affine, then the MOTF cell centres
  sampled exactly as the scorer samples them); model wet = peak depth >= `DEPTH_MIN` (0.15 m).
- scored set = MOTF footprint (bed > 0 m) AND `simulated_mask` (the run's own active faces) AND NOT
  `motf_exclude_mask` (v4: the NJ-only validity raster; the FEMA sheet renders DE / PA / NY land
  as dry). Excluded land is grey on the map.
- CSI / POD / FAR recomputed from the class raster are checked against the arm's metric row and
  printed (`[self-check ...]` in the log).

Display: insets at the full 15 m. The overview is reduced 8x (120 m) with a categorical block mode:
a block shows its commonest flood class if hit / miss / false alarm cover >= 25 % of it, else its
commonest background class (never bilinear). The inset CSIs are local (that box only).

## Numbers plotted

**Stand-in (`fig3_motf_standin_v110`)**: `v4_refreeze_swz_v11 / p4-premier+weir-elizabeth-rahway` (Model 1.1.0,
rain ON), floodmap `/scratch/tpj8/floodmap_fix_2026-11-12/v4_refreeze_swz_v11/p4-premier+weir-elizabeth-rahway/floodmap_hmax_native.tif`
(native 3.125 m). Row: `logs/floodmap_fix_2026-11-12/rows/v4_refreeze_swz_v11__p4-premier+weir-elizabeth-rahway.csv`.

| | class raster | row | |
|---|---|---|---|
| CSI | 0.801964 | 0.801964 | plotted 0.80 |
| POD | 0.867566 | 0.867566 | plotted 0.87 |
| FAR | 0.086164 | 0.086164 | plotted 0.09 |

Max |diff| 2.8e-17: the figure's classes ARE the scorer's. Areas: hit 1,201.3 km², miss 183.4 km²,
false alarm 113.3 km² (= the row's 42.2 connected + 71.1 disconnected), not scored as outside NJ 2,412.7 km².
Inset CSIs (local, that box only): A Hoboken / Jersey City / Newark Bay 0.70, B Barnegat Bay / LBI 0.87,
C Cape May 0.69.

**Rain-off (`fig3_motf`)**: filled in tonight from `experiments/v4_refreeze_swz_v11/metrics.csv`; the
watcher's log prints the same `[self-check ...]` line.

## Re-run for the rain-off arm (one command)

The capemay job validates the arm with `run_experiments.py --validate-only`, which writes the
native floodmap into the run dir, `experiments/v4_refreeze_swz_v11/p4-premier+rain-off+weir-elizabeth-rahway/floodmap_hmax_lev3.tif`,
and the row into `experiments/v4_refreeze_swz_v11/metrics.csv` (marker:
`logs/capemay_tests_2026-11-09/out/p4-premier+rain-off+weir-elizabeth-rahway/scored_ok`).
The script finds both on its own. From the repo root, on a compute node with ~100 G (peak measured 97.5 G MaxRSS, 6 min on 16 cores) (fish-safe):

```
srun --jobid=<holder> --overlap -n 1 -c 8 env NJ_DOMAIN=v4_refreeze_swz_v11 PYTHONPATH=$PWD $HOME/nj_sandy_sfincs/micromamba/envs/sfincs/bin/python reports/poster_2026-11-13/fig3_motf.py --arm p4-premier+rain-off+weir-elizabeth-rahway --stem fig3_motf
```

(Or let job `63850142` do it: it starts at 19:00, polls every 10 min, and gives up on `FAILED` or if
63843110 leaves the queue without the marker. Its log: `logs/fig3_rainoff_watch_63850142.out`.)

## Unsure / caveats

- The stand-in is RAIN ON. Some of its pink false alarms inland (the Delaware Bay shore, Cape May,
  Ocean County creeks) are probably rain ponding, which is why the rain-off twin is the standard for this
  comparison (user 11-09). Expect FAR down and CSI up a little in `fig3_motf`; the miss areas should
  barely move. If the subtitle needs to change, pass `--subtitle "..."`.
- The watcher's EXPECT_MD5 guards `fig3_motf.py` only. If that file is edited before the job starts
  (19:00), re-write the md5 (`md5sum reports/poster_2026-11-13/fig3_motf.py >
  reports/poster_2026-11-13/logs/fig3_watch_expected.md5`), or the job refuses. `poster_style.py` is
  NOT guarded, so style edits are picked up.
- `scored_ok` is written only after the paired HWM bootstrap, about 30+ min after the metrics row
  exists. If the row is there and the bootstrap fails, the marker never comes: run the one-line command
  by hand. It only needs the run dir's native floodmap.
- "Open water" = bed <= 0 m on the model's own bed (the scorer's footprint rule), not a coastline product.
  The staircase edges in insets A and B are the edges of the model's grid cells.
- The overview's 8x reduction slightly thins thin flooded strips and slightly widens patchy ones. The
  insets are at the full 15 m.
