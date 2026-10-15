# Cleanup — 2026-10-15 (the final-audit pass)

**Why:** this is the last cleanup before the v4 premier is declared ready.
- `/scratch/tpj8` holds ~723 G against the 1 T soft limit (about 600 G of it ours).
- Home holds 68 G of 100 G.
- The repo carries scripts, logs and reports that are no longer used.

**How "freed" is measured:** one read-only per-inode walk. It counts only files whose EVERY hard link lies inside the set, so the figure is what deleting the set actually returns. The set lists are in the session scratchpad (`deletion_sets.json`); the per-path list goes to `deleted_2026-10-15.txt` when the deletions are applied.

**Status: DONE 2026-10-15** (after the desktop backup and the user's commit).
- Tiers A + B applied; every path is in `deleted_2026-10-15.txt`, and retired arms are in each domain's `_retired/MANIFEST.md` (26 arms, via `retire_arm.py`).
- Scratch 713 → 438.1G (mmlsquota lags ~10 min); home 71 → 63.45G.
- The home items below are done, and the NACCS originals are now a symlink to the home copy.
- Same pass: `premier.py` labels v4 / v4_hot / v4_hot_plus RETIRED; `v4_first_results.py` `test` preset points at `_retired/`; `retire_arm.py` learned 5 more record types (`sfincs.wvm`, the mask-repair records, the `overflow_check` outputs, `sfincs_ini_*`).
- 🔴 **Found:** `desktop_pull_backup.sh` copied `data/`'s scratch symlinks as links, so `nj_bight_sfincs_data/` (78 G: frozen meshes, beds, NACCS) was never in the backup. It is now pulled as its own tier, with `~/nj_bight_durable/`.

## Tier A — rebuildable or duplicated (no record lost)

| set | files | freed | why it is safe |
|---|---|---|---|
| every `snapwave.upw` (experiments + engine_gate) | 23 | **13.1 G** | runtime table, regenerated on a re-run (CLAUDE.md §5) |
| `engine_gate/inflow_move_2026-10-11/` | 27 | **1.9 G** | finished test; result in `logs/inflow_move_2026-10-11/compare.txt` |
| probe dirs: `wind_setup_toy_2026-10-06`, `roughness_test_2026-10-05`, `meteo_fix_regrid_2026-10-06`, `manning_water_v4_old_2026-10-05`, `nj_bight_sfincs_data/{bed_candidates_2026-10-05,probe_mesh_v4}` | 643 | **1.2 G** | one-off probes; findings recorded in FINDINGS part 4 / logs |
| `env_backup_2026-09-24/sfincs-env.bight_2026-08-21.tar.gz` | 1 | **0.9 G** | `cmp`-identical to `~/nj_bight_sfincs/sfincs-env.tar.gz` (KEPT) |

KEPT in `env_backup_2026-09-24/`: the sandy tarball (it differs from the home copy) and the pip / explicit freezes.

## Tier B — superseded records (user approved 10-15)

Run dirs are retired with `scripts/retire_arm.py`. It keeps `sfincs_his.nc`, `sfincs.inp`, `sfincs.log`, `provenance*`, `engine.txt`, `gis/`, the forcing files and the wave boundary, and deletes the map, the floodmap and the hard-linked inputs. Metrics rows stay in each domain's `metrics.csv`.

| set | files | freed | note |
|---|---|---|---|
| `v4/`, `v4_hot/`, `v4_hot_plus/`: arms' bulk + `_template_sealed` + `_subgrid_*` + `floodmaps/` | 345 | **110.6 G** | superseded mask variants. The registry entries stay, labelled retired. Each domain keeps `metrics.csv` / `report.html`. `v4_first_results.py` `test` preset updated. |
| v3 `wave-*` ×7 + `mask-drain-edge+*` ×4 (bulk) | 180 | **65.3 G** | §61 / §54 numbers live in `v3/metrics.csv`; the mask-drain-edge runs are pre-repair (§50) |
| v3 non-reference floodmaps (all but `naccs-premier`, `naccs-nowaves`, `bed-v4fixes+wave-dt3600+wind-naccs` and twin) + `v4_hot_plus_walls/floodmaps/` | 15 | **39.0 G** | re-downscalable from the kept `sfincs_map.nc` (`--validate-only`) |
| `v4_refreeze/_pre_rebaseline_2026-10-11/` (arms' bulk + floodmaps) | 51 | **29.5 G** | parked ERA5 pair; rows in `metrics_2026-10-11_pre_rebaseline.csv` |
| `audit_v4_hot_plus_2026-10-05_channels/`, `wind_products_2026-10-06/` | 9,764 | **10.5 G** | audit of a superseded domain; NAM / RAP / RTMA downloads (re-downloadable; FINDINGS part 4 (e)) |

## Totals (scratch)

**A + B = 271.9 G freed** (357.8 G apparent) → ~450 G of 1 T.

## Moved, not deleted

`nj_bight_sfincs_data/NACCS/_originals_pending_delete/` (3.2 G, 33 zips) is the only byte-reproducible source of v3's NACCS boundary (FINDINGS part 3).
- Copied on 10-15 to `/cache/home/tpj8/nj_bight_durable/NACCS_originals_pending_delete/`, which is backed up. Every file is md5-verified (`MD5SUMS` beside them).
- After the backup gate, the scratch dir becomes a symlink to the home copy, because `scripts/repack_naccs_zips.py` and `naccs_h5_to_csv.py` read it through `data/NACCS/`.

## Home (planned, Phase 1)

| item | frees | note |
|---|---|---|
| `micromamba clean -a` | ~6.0 G | package cache; only `nlink == 1` files go (envs keep their hard links) |
| `data/elevation_v4/{nj_10ft_dem_v4.tif.ovr, gmrt_v4.tif}` → symlinks to scratch | 1.65 G | `cmp`-identical to the scratch copies |
| `data/elevation_v4/inland_water/` → copy its 4 home-only files to scratch, then symlink | 0.4 G | finishes the 10-05 data swap; check `relativeToVRT` paths first (CLAUDE.md §5) |
| `~/.cache/{pip,conda}`, old `~/.vscode-server/cli` builds | ≤ 1.2 G | caches |

## Not ours

`/scratch/tpj8/sfincs-nj-agri/` (123 G) belongs to another project; its job was writing on 10-15. Never touched.
