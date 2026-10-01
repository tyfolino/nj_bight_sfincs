# Deletion manifest — 2026-09-30 (the repo cleanup before the river / wave rethink)

**Sign-off model (user, 2026-09-30): by RULE.** Tracked files are `git rm`'d and staged —
history keeps them, and the user reviews `git status` / `git diff --cached` and commits.
Untracked files are MOVED, never deleted, to `/scratch/tpj8/nj_bight_attic_2026-09-30/`
(repo paths mirrored). 🔴 Scratch is not backed up and purges files unread for 90 days, so
the attic empties itself by ~2026-12-29; move anything back before then if it is wanted.
Nothing below was deleted outright. Precedents: `deletion_manifest_2026-08.md`,
`deletion_manifest_2026-09-20.md` (whose user decisions this pass respects — see F).

**Rules.** A script goes only if no code, test or hpc file uses it, its purpose is closed,
and it is not the provenance of data still on disk; every candidate was re-grepped at
removal time. A figure goes to the attic unless FINDINGS, CLAUDE, code or a notebook cites
it or a surviving script regenerates it. Promoted log code replaces its log copy.

**Verification** (before and after, on a compute node): `python -m unittest discover -s
tests`; `python -m nj_sfincs.premier` on v3 (20/24 — the four `mask-drain-edge+…` BAD rows
are the deliberately kept pre-repair runs) and v4 (6/6); `run_experiments.py --experiments
naccs-premier --check` on v3; ruff on every edited file (pre-existing findings unchanged).
New guards: `TestNoDanglingScriptPaths` (every `scripts/…` / `hpc/…` path the docs name
exists, or its line says it was retired) and `TestScriptsIndex` (`scripts/README.md` ↔ the
directory).

## A. Tracked — `git rm` (staged)

Scripts (one-off reads of closed investigations, or superseded):
- `scripts/compare_usgs_transects.py` (⚠️ RESTORED 2026-10-01 for the cheap-wavemaker arm), `scripts/score_beach_strip.py`,
  `scripts/engine_gate_reads.py`, `scripts/render_notebook_profiled.py` — 09-17…09-20 reads,
  results in FINDINGS §44/§49.
- `scripts/make_v3_epoch_notebook.py` — generated the v3 epoch notebooks; v3 is DONE.
- `scripts/paired_hwm_basin_split.py` — folded into `paired_hwm_bootstrap.py --by-basin`.
- `scripts/stamp_metrics_epoch.py` + its test class `TestStampTouchesOnlyEpochColumns` — the
  09-11 migration ran; the test was its only reason to stay (kept 09-21 for that reason only).

hpc:
- `hpc/build_mesh.slurm`, `hpc/probe_mesh.slurm` — `-p main-redhat` (fails outright since
  08-20) and default `NJ_DOMAIN=v2_barnegat`; superseded by `freeze_mesh.slurm` /
  `probe_mesh_size.py`.
- `hpc/subgrid_probe_v3.slurm` — self-described one-off (08-26).
- `hpc/freeze_mesh_v4.slurm` → RENAMED `hpc/freeze_mesh.slurm`, `NJ_DOMAIN` required, and it
  now refuses to clear a COMPLETE mesh on a resubmit (the old script would have `rm -rf`'d a
  frozen mesh); it clears only partial output.

Docs:
- `docs/plan_v1_5_original.md` — the 08-13 v1.5 plan, referenced nowhere; FINDINGS part 2 is
  the v1.5 design record.

Code:
- `nj_sfincs/plots.py`: `plot_hwm_scatter`, `plot_depth_panels`, `plot_depth_difference`,
  `plot_experiment_comparison` — referenced nowhere (222 lines).
- `data/data_catalog.yml`: `inlet_channels_burn`, `narrows_wide_h` — their files and builders
  exist nowhere; six builders that live only in the archive now say so.

## B. Tracked — rewritten in place

- `docs/STATUS.md` 6,767 → ~175 lines of live state. Before cutting, five slices of the old
  log were checked claim by claim against FINDINGS and CLAUDE (~180 durable facts found
  missing); what still holds was moved to FINDINGS §15, §20, §37, §39, §40, §42–§44, §48,
  §50, §52, §53–§60, parts 2–4, and CLAUDE.md §5. The old text is `git show
  d70dd1e:docs/STATUS.md`, which FINDINGS' "STATUS <date>" citations now point at.
- `docs/FINDINGS.md` — corrected where it was wrong: §3 VDatum (offline grids), §4 (seiche
  settled; fixed-engine ΔCSI 0.009), §20 (cost anatomy; serial sweep), §38 (`bay_fringe`),
  §42 (engine conditions), §43 (the initial-guess cause is a hypothesis), §47 (NY bays
  −0.02..−0.10), Closed (`sfincs-desktop.sif`, engine lineage), part 2 (Carteret priced).
- `CLAUDE.md` §1 reframed on the present; §2 v4 sha `23ea65f8…`, 194 vertices; §3–§4 layout,
  test count, `--tstop`, the login-node rule; §5 threading (~30 → 5.9–6.8 cores), ~97 %,
  maintenance dates, and new traps (fills, narrow channels, bridge decks, `output WHOLE`,
  MaxRSS, rotated `boundless` reads, porting drops fields).
- `README.md` — reframed; stale "54 tests" and "never a symlink".
- `.gitattributes` — the `nbstripout` filter declaration removed (never installed;
  installing it would have silently stripped the rendered notebooks); `hpc/amarel_bootstrap.md`
  and `.gitignore` comments to match.
- Stale comments: `nj_sfincs/model.py` (the outflow-edge rationale §50 disproved),
  `nj_sfincs/domain.py` ("no outflow BC on any river"; `cn_v4` / `cora_waves_v4` "not built"),
  `nj_sfincs/experiments.py` (v3 "BUILDING", v4 "ACQUISITION-ONLY"),
  `scripts/rebuild_subgrid.py` (`z_zmin` claim), `hpc/stage_and_submit_v3.slurm` (validate
  memory; the arm list is now REQUIRED — the old default named a retired arm and the v3
  reference dir), `hpc/run_experiments.slurm` header, `hpc/vscode_node.sh` partition,
  `scripts/build_naccs_boundary.py`, `scripts/audit_region_v4.py`,
  `scripts/download_pre_sandy_topobathy.py` (dangling script names).

## C. Promoted from `logs/` into `scripts/` (their log copies are in the attic, D)

- `scripts/build_river_table_v4.py` ← `logs/v4_design_2026-09-28/river_table/build_river_table.py`
  (logic unchanged; writes to the same folder by default, so its cache still serves).
- `scripts/paired_hwm_bootstrap.py --by-basin` ← the three `grouped_paired_ab.py` copies +
  `paired_hwm_basin_split.py`; re-checked on v3 premier vs nowaves: RMSE 0.3294 / 0.3934 as
  published.
- `scripts/wave_boundary_ring.py` ← restored from `56e37ae^` (identical to the log copy).
- `scripts/snapwave_cost.py` ← grown from `logs/snapwave_diag_scratch_2026-09-10/convergence.py`.
- `scripts/README.md` — new index.

## D. Untracked — moved to the attic (58 files, 2.2 MB)

Figures (49), no live citation and no surviving producer (kept: the v4 audit / ocean-line / domain figures, `v4_region_satellite.png`, `v4_ring_review.png`, and the five figures FINDINGS or a notebook cites):

- `reports/figures/bay_mask_coverage.png`
- `reports/figures/bed_dam_1450.png`
- `reports/figures/bed_dam_157.png`
- `reports/figures/bed_dam_62.png`
- `reports/figures/bed_dam_980.png`
- `reports/figures/bed_dam_980_sw.png`
- `reports/figures/bed_dams_v3.png`
- `reports/figures/buildings/item4_absecon_island.png`
- `reports/figures/buildings/item4_ocean_city.png`
- `reports/figures/buildings/item4_seaside_ortley.png`
- `reports/figures/mask_repair_v3_2026-09-22.png`
- `reports/figures/motf_v3_vs_ring_EDITED.png`
- `reports/figures/naccs_cape_may_after_merge.png`
- `reports/figures/naccs_cape_may_coverage.png`
- `reports/figures/region_v1_5_raritan.png`
- `reports/figures/region_v3_draft_inland.png`
- `reports/figures/region_v3_draft.png`
- `reports/figures/region_v3_edited_crossings.png`
- `reports/figures/si_edge_drain_2026-09-21.png`
- `reports/figures/snapwave_domain/wave-shelf-steps_domain.png`
- `reports/figures/v3_depth_absecon.gif`
- `reports/figures/v3_depth_cape_may_2026-09-14.gif`
- `reports/figures/v3_depth_cape_may_2026-09-20.gif`
- `reports/figures/v3_depth_raritan_2026-09-14.gif`
- `reports/figures/v3_depth_raritan_2026-09-20.gif`
- `reports/figures/v3_depth_raritan.gif`
- `reports/figures/v3_depth_sandy_hook_2026-09-20.gif`
- `reports/figures/v3_hm0_cape_may_2026-09-14.gif`
- `reports/figures/v3_hm0_cape_may_2026-09-20.gif`
- `reports/figures/v3_hm0_cape_may.gif`
- `reports/figures/v3_probe_mask.png`
- `reports/figures/v3_river_cuts_and_gauges.png`
- `reports/figures/v3_seed_isobath10m.png`
- `reports/figures/v3_winddir_fix_gauges.png`
- `reports/figures/v3_winddir_fix_hm0.png`
- `reports/figures/v3_winddir_fix_hm0_sandy_hook_patched.gif`
- `reports/figures/v3_winddir_fix_hm0_sandy_hook_unpatched.gif`
- `reports/figures/v3_winddir_fix_hwm_paired.png`
- `reports/figures/v3_winddir_fix_wavdir.png`
- `reports/figures/v3_winddir_fix_zsmax.png`
- `reports/figures/v4_brooklyn_and_naccs.png`
- `reports/figures/v4_design_motf_extent.png`
- `reports/figures/v4_naccs_nodes_delaware_mouth.png`
- `reports/figures/v4_naccs_nodes_delaware.png`
- `reports/figures/v4_naccs_nodes_lower_bay.png`
- `reports/figures/ward_point_ring_vs_cudem.png`
- `reports/figures/waterlevel_boundary_v1_5_raritan_cuts.png`
- `reports/figures/waterlevel_boundary_v1_5_raritan.png`
- `reports/figures/wavemaker_line_v3_2026-09-17.png`

Log code superseded by C (6):

- `logs/v4_design_2026-09-28/river_table/build_river_table.py`
- `logs/wind_x110_reads_2026-09-22/grouped_paired_ab.py`
- `logs/mask_repair_2026-09-22/grouped_paired_ab.py`
- `logs/great_kills_2026-09-21/grouped_paired_ab.py`
- `logs/wave_boundary_v4_2026-09-29/wave_boundary_ring_from_git_56e37ae^.py`
- `logs/snapwave_diag_scratch_2026-09-10/convergence.py`

Data leftovers (3):

- `data/buildings_v3/provenance_VOID_prepend_2026-09-04.json` — data leftover: VOID record / unreferenced
- `data/buildings_v3/subgrid_diff_VOID_prepend_2026-09-04.json` — data leftover: VOID record / unreferenced
- `data/naccs_support_points.geojson` — data leftover: VOID record / unreferenced

## E. Untracked — reorganised in place

- `logs/`: the 261 loose top-level files (SLURM stdout, md5 lists, job-id files) were
  filed by modification month under `logs/slurm/<yyyy-mm>/` (2026-08: 46, 2026-09: 215).
  Three that FINDINGS or a script cites by path stay at the top. The 23 dated campaign
  folders stay; STATUS's evidence index maps them to topics.

## F. Proposed and NOT done, with the reason

- Notebooks (`sandy-v3-viz-2026-09-14/-20`, `sandy-v1_5-viz-2026-08-21`), the two
  `reports/weekly_2026-09-09*.html` and `reports/naccs/` (incl. the 20 MB
  `bathy_v1_5_drawing_aid.tif`) — the user KEPT each explicitly on 09-21
  (`deletion_manifest_2026-09-20.md` §C). Not re-litigated.
- `scripts/build_refinement_v1_5.py` — kept by user decision 09-21.
- `scripts/build_v3_coarse_bed.sh` — provenance: it records the tier order v3's coarse bed
  was actually built with, which differs from `domain.py`.
- `scripts/check_buildings_adequacy.py` — v4's burn skipped 24.6 km² of low ground; the check
  may be needed again.
- `scripts/stockdon_envelope.py`, `check_naccs_vs_sensors.py`, `restage_mask_repair.py`,
  `snapwave_bay_census.py`, `export_share_floodmap.py`, `score_bracket.py`,
  `score_v2_barnegat.py`, every `download_*` — each has a live caller, a live use, or is
  data provenance (`scripts/README.md` says which).
- `data/NACCS/_originals_pending_delete/` (3.2 G) — NOT moved: after the 09-26 merge it is the
  only byte-reproducible source of v3's NACCS boundary (FINDINGS part 3). User's call.
- `data/gtsm/retired_v1_monmouth/` — the catalog keeps it deliberately as the sealed v1
  campaign's record.
- Removing the frozen domains (`v1_monmouth`, `v1_5_raritan`, `v2_barnegat`) from the
  registry — `v2_barnegat` is wired into the fingerprint registry and a test, and what is
  "frozen" depends on the river decision. Revisit after it.
- Reorganising `scripts/` into subfolders — 50 scripts locate the repo root with
  `parents[1]` and would silently point at the wrong place; kept flat + indexed.

