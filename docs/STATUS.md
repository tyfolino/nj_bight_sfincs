# STATUS — live campaign state

**Edit this file in place; keep it under ~300 lines.** It holds what is happening NOW: what is
running, what is next, what is open. When an item closes, its durable fact goes to
[FINDINGS.md](FINDINGS.md) (or CLAUDE.md §5 if it is a trap) and the item is deleted here.
Git has the history. The campaign log this file grew into until 2026-09-29 (6,767 lines) is
`git show d70dd1e:docs/STATUS.md`; FINDINGS cites it as "STATUS <date>".

Last updated: **2026-10-17** — the seeded-engine test read (repeats bit-for-bit across machines; a
null perturbation still diverges waves-on → FINDINGS §44 (d)–(e)); the lake-fixed bed built; the 10-15
reads moved to FINDINGS part 4 (h); cap test, template re-stage and the lower-only lake-bed rebuild
submitted; `--overlay <key>:min`, env lock (`env/`), README done. Before: 2026-10-15 (pre-maintenance
jobs read; FINAL AUDIT plan approved).

---

## Now

- **v3 is DONE** (2026-09-24). Reference `naccs-premier` on the repaired mask — HWM RMSE 0.329 /
  bias −0.143 (median, 50 m, n 94), MOTF CSI 0.706. Its NACCS-wind re-run
  `bed-v4fixes+wave-dt3600+wind-naccs` reads 0.300 / −0.097 (part 4 (h)); the v3 reference is re-run
  on the seeded engine in Phase 4.
- **v4 = `v4_refreeze`** (`378014e154b4ff41`; bed `_subgrid_refreeze`, Keansburg + Overpeck weirs,
  ERA5-bilinear meteo on the engine's corner convention). Premier `naccs-premier` (NACCS-blend wind,
  CN infiltration, unseeded engine): RMSE 0.436 / bias −0.110 (n 110), CSI 0.780 with the
  `salem_marshes` box — and 0.301 without marks 6122 / 6130, the two lakes the sea never enters in the
  model (part 4 (g)–(h)). Run B (`v4_hot_plus_walls`) stays as the pre-re-freeze record.
- **Heading for:** ONE Phase 4 re-baseline job on the seeded engine (below), before maintenance 11-10.

## Running (10-17)

- **62678718 `igcap`** on CAMDEN (halc073, since 08:27; `logs/ig_cap_2026-10-17/igcap.slurm`): the cap
  test — 6 h cut of the premier, seeded engine, four copies on disjoint cores: `snapwave_niter` 800
  (N8_a / N8_p) and `snapwave_crit` 0.01 (C2_a / C2_p), each `_p` with `rhoa` 1.2501; read against the
  10-16 SEED_a / SEED_p (`logs/ig_det_2026-10-15/sens3c_62670930_r0/`). Expectation in the script
  header. Out `igcap_62678718.out` + `igcap_62678718_r0/`; maps on Camden scratch. Its md5 guard covers
  `scripts/engine_gate.py` + `logs/ig_det_2026-10-15/his_pair.py` (a requeue re-checks). Read also the
  "SnapWave s per call" lines (×~1/3 for emeraldrapids) — they set Phase 4's wall budget.
- ✅ **62678743 `restage_inflows` DONE** (12 min, 14 G): `experiments/v4_refreeze/_template_inflows` =
  the v4_refreeze template with the 12 moved inflows (walls on run B's points). Fingerprint
  `378014e154b4ff41` unchanged; `premier.assert_sealed_domain` OK. Three 10-06 hand steps were missing
  (meteo `--era5-bilinear`, the Absecon obs nudge — staging copies `frozen_mesh_v4/sfincs.obs` —, the
  Overpeck `sfincs_ini_regional.bin` + `inifile`); none depends on the inflows and the mask is
  byte-identical, so the files were copied from `_template_sealed`. Final diff vs `_template_sealed`
  (`logs/restage_2026-10-17/compare_after_handsteps.txt`): ONLY `sfincs_netsrcdisfile.nc` (12 of 61
  points), `gis/dis.geojson`, `provenance.txt`, `.subgrid_sha256` (inode / mtime fields; same hash).
  ▶ **Swap — needs the user's OK, and AFTER 62678757 ends (it reads `_template_sealed`):**
  `mv _template_sealed _template_sealed_pre_inflows_2026-10-06 && mv _template_inflows _template_sealed`.
  🔴 Trap for the next re-stage: `setup_boundary_depth.py` does NOT replay the 10-06 hand steps.
- **62678757 `sbg_lakes_min`** (`main`; `logs/lakes_min_2026-10-17/submit.sh`): the lake-fixed bed again,
  with `--overlay lake_fix_v4:min` (lower-only, user 10-17) → `_subgrid_refreeze_lakes_min`. Checks: vs
  `_subgrid_refreeze` NO face gets a higher `z_zmin` / `uv_zmin`; changed faces ⊆ the 10-16 build's 2,952.
  ⚠️ Submitted without `--force`: a requeue refuses on its own partial dst — resubmit with `--force`.
  Guard: `data_catalog.yml`, `rebuild_subgrid.py`, `domain.py`, `premier.py` + the 58 rasters.
- 🔴 Side-by-side `engine_gate.py run` copies need `taskset` on disjoint cores (FINDINGS §44 (i)).
- **Clean-up (user OK 10-17):** ✅ `/scratch/tpj8/engine_gate/igseed_sens/` (59 G), ✅ Camden's 10-16
  maps (28 G). KEEP `/cache/home/tpj8/nj_bight_staging/igseed_src_v4refreeze_premier/` (5.6 G, Camden's
  input) until the cap test is read. After the lakes_min build is checked, `_subgrid_refreeze_lakes`
  (10-16, superseded) can go.

## ⭐ FINAL AUDIT → "the v4 premier is ready" (plan approved 10-15)

Plan: `~/.claude/plans/i-think-i-m-ready-warm-trinket.md`. User decisions 10-15: lakes = rule-based
flag + a documented-site breach SENSITIVITY arm (not in the premier); IG stays on, seeded; v3
reference re-run on the seeded engine; `cnb` stays the premier's infiltration (FINDINGS §59).

- **Phase 0–1 ✅ (10-15):** seed patch + Deltares issue draft (`docs/upstream/snapwave_igseed*`); NACCS
  originals in `~/nj_bight_durable/`; repo, scratch and home cleanup (scratch 713 → 438 G).
  🔴 USER: re-run `scripts/desktop_pull_backup.sh` once (first pull of `nj_bight_sfincs_data/`, 78 G) —
  in progress 10-17.
- **Phase 2 ✅ (10-17):** outcome B — seeded repeat STRICT across clusters, null perturbation diverges
  waves-on (FINDINGS §44 (d)–(e)); §44 / §45 rewritten; CLAUDE.md §5 RNG trap. Open: the cap test.
- **Phase 3 (code, no solves):**
  - ✅ inflow-wall split (`Domain.wall_sources_geodataset`; discharge `usgs_sandy_discharge_v4_refreeze`,
    walls on run B's points) — reaches runs via the re-stage (Running).
  - ✅ `cnb` (`Experiment.cnb_effective` → `nj_sfincs/infiltration.py`; `smax = max(1, e)·S_II`,
    `seff = e·S_II` because the engine clamps `Se ≤ smax` after a dry spell > 0.06/kr h — user OK 10-15);
    `ksat_v4_refreeze` built (SSURGO; dry run: 2.0 M of 3.97 M active faces infiltrate, `seff` (e 1.5)
    median 6.7 cm, `ks` median 262 mm/h, 7.4 % without ksat).
  - ✅ `data/wind_v4/naccs_blend_p_era5` (wind = `naccs_blend`, pressure ERA5 outside / blend inside the
    NACCS zone; p99 7.8 hPa); not yet registered.
  - ✅ lake bed: audit + `lake_fix_v4` (part 4 (h)); ✅ `rebuild_subgrid.py --overlay <key>:min`
    (lower-only paint, 10-17; `tests/test_rebuild_subgrid.py`); lower-only rebuild running.
  - ✅ metrics label round-trip, islands log, HWM 6044 (no v4 action), env lock (`env/`), README (10-17).
  - ✅ `lake_outlet_blocked` flag (10-17; rule + v4 premier read in FINDINGS part 4 (h)): new keys
    `hwm_*_excl_lake_blocked`, `hwm_lake_outlet_blocked_ids` (label round-trip), per-mark columns in
    `v4_first_results.py` marks CSVs; light per-run read `scripts/lake_outlet_blocked.py`. Suite 322 OK.
  - ☐ `_subgrid_breach` (sensitivity arm): Mantoloking = the user's two polygons
    (`logs/breach_picker_2026-10-15/polygons_final_2026-10-15.csv`, painted `:min` after the buildings);
    Wreck Pond = a STATED channel beside the outfall (the inlet healed within ~2 weeks, so no survey shows
    it) + optionally the open 7-ft outfall pipe as a culvert (nothing in nj_sfincs writes a drainage
    file yet); Deal Lake none (overtopping — user). Needs the channel's width / invert from the user.
  - ☐ desk checks: Atlantic City datum, paved channels.
  - ☐ register the Phase 4 arms (candidate premier name; renamed into place after, the 10-11 recipe) +
    `logs/rebaseline_2026-10-xx/PREREG.md`. Waits on the cap test (`snapwave_niter` enters every arm).
  - ✅ full suite 322 OK / 6 skipped (10-17, ~14 G peak; under an 8 G cap `test_motf_simulated_mask` errors).
- **Phase 4:** ONE 2-node job on the seeded engine. Node 1: new premier (seeded + `cnb` 1.5 + ERA5
  pressure + moved inflows + lake-fixed bed) + its repeat + `bed-breach` + waves-off + `cnb` 1.0 / 2.38
  + `bed-nobuildings` + a waves-off Horton (`hor`) arm. Node 2: v3 reference pair + a full-length `rhoa`
  1.2501 copy of the new premier (the noise band THROUGH the peak). Validate; paired reads. Must end
  before 11-10 08:00. **Wall budget:** the v4 premier took 10 h 05 on emeraldrapids (job 62328438;
  SnapWave 28,568 of 36,258 s; 18 capped calls × 539 s, 55 converged × 343 s). At `snapwave_niter` 800 a
  call that still caps costs ~4× → worst case ~18 h, packed 4×16 about the same; on icelake ×3 → past
  the 40 h limit, and a TIMEOUT is not requeued (a hand-resume resets `cna` soil) →
  `SOLVE_CONSTRAINT=emeraldrapids`.
- **Phase 5–6:** reads (new preset) → frozen premier (engine `…igseed-1…@2e4e9645`, user tags git),
  `docs/MODEL.md` model card, validation summary, research-group brief (incl. status-notebook fig. 2,
  "rise above normal water": baseline from the premier's early 6-h `zsmax` blocks,
  `logs/notebook_qc_2026-10-11/baseline_check.py`), docs refresh, backup, user commits.

## Re-freeze bed — notes that still apply

The bed is `_subgrid_refreeze`: buildings cap10 → lakes → unpave → harbour → Raritan-corner
surveys → back-bay unpave → Sayreville → Little Egg → `riverbeds_hierarchy_v4` LAST, plus
`--manning-overlay manning_water_v4` (marsh n kept on tidal polygons and tidal-looking lakes;
0.02 on lakes, non-tidal rivers, developed overrides). One bed-source hierarchy (user 10-05):
eHydro → real CUDEM → NOAA charts / NOS → shaped sloping-river section; the 1.2 m-below-MLLW floor
only on runs ending at a head of tide. 🔴 `riverbeds_hierarchy_tier_v4.vrt` is provenance, NOT a
bed — never `--overlay` it. Premier-tier inconsistencies: `premier_tiers.csv`.

**Fix-material registry (catalog keys, all overlays):** `bed_buildings_v4` (+4) /
`bed_buildings_v4_cap10`; `inland_water_bed_v4` (85 lakes + 2 rivers, 5.16 km², bed only);
`usace_unpave_v4` / `usace_unpave_backbay_v4`; `ehydro_harbour_v4` / `ehydro_refreeze_cenan_v4`
(`download_ehydro_v4.py --set …`); `riverbed_sayreville_v4`; `littleegg_channel_v4`;
`riverbeds_hierarchy_v4` (replaces the 10-05 Cohansey / GMRT / tidal builds). Paint order:
buildings → lakes → channel fixes (later wins).

**Still open on the bed:** the Schuylkill below Fairmount (fill bed + box-mean Manning;
FINDINGS part 4 "Still open"); optional `jamaica_wall_mid` west of Paerdegat; Big Timber branch
heads may still be tidal (unpainted). Paerdegat: leave it (user).

## Domains at a glance

| domain | status | fingerprint (faces / boundary edges / sha) | reference arm |
|---|---|---|---|
| `v1_monmouth` | frozen, port fixture | 547,408 | — |
| `v1_5_raritan` | frozen 2026-08-14 | 696,230 / 1,652 / `2a23667dd16e449c` | `naccs-premier` (carries the §50 edge drain, unmeasured) |
| `v2_barnegat` | archived, score-only | — | 5 rescored rows in `experiments/v2_barnegat/metrics.csv` |
| `v3` | DONE 2026-09-24 | 3,412,470 / 4,108 / `1596ce1ecc71b374` | `naccs-premier`, engine `bin:v2.3.3-winddir-fix-1-gf11@673ee3bf` |
| `v4` | frozen 2026-09-28, superseded by the A+ variants | 4,881,654 / 4,388 / `23ea65f8b81ee1bd` | waves-off gate arms only |
| `v4_hot` | A, record of the 10-02 cut memo | same / `446d671cd97037ee` | waves-off |
| `v4_hot_plus` | A+ (dam-crest recut 10-05) | same / `e5e9d8668fe29292` (old: `207ae7f7f0b805ae`; its runs deleted 10-11, rows in metrics.csv) | waves-off; run A |
| `v4_hot_plus_walls` | A+ + walls (10-05) — run B, the pre-re-freeze record | same / `77b5eda1fcd51cf6` | run B |
| **`v4_refreeze`** | **THE re-frozen v4** (10-06) = above + Lewes | same / `378014e154b4ff41` | `naccs-premier` = NACCS-blend wind (re-baselined 10-11) |

## Open questions (each with what would close it)

- **River inflows that pile up on a ~0 m bed (FINDINGS part 4, "Still open"):** Ridley, Chester,
  Frankford, Red Clay, White Clay, Christina (PA/DE, unscored) and **Salem R. at Woodstown 4.38 / 0.01
  (NJ)**; every one on a COARSE face (100–200 m) over a narrow creek valley, stepping down 2–3.5 m in
  2 km on rain-off alone (`logs/notebook_qc_2026-10-11/inflow_pileups.py`). Close: read on the Phase 4
  premier; a refinement band is the next-mesh fix.
- **Waves-on noise band (§44 (e)):** does `snapwave_niter` close it, and how wide is it through the
  peak? Close: the cap test (Running), then Phase 4's full-length `rhoa` copy.
- **Capped calls inject river pulses on v4 (§44 (h)).** Close: count capped calls in every v4 log;
  check whether any face's `zsmax` is set inside a capped hour; the cap test's niter-800 copies.
- **Southern back-bay deficit (§57):** the Great Egg inlet sill (§54 h) a candidate share. Close: the
  v3 re-run's Great Egg / Ocean City pre-storm bay-minus-pier; calm-month datum check of the seven
  southern USGS stations.
- **NY east bay ~0.2 m low after the repair (§50);** `lower_bay_si_shore` (n 3) moves the wrong way;
  the cross-Narrows tilt at `sss_narrows_bkln`. Close: per-mark and Narrows Q(t).
- **Great Kills sensor offset cause (§50).** Close: USGS STN deployment / survey records.
- **12 USGS gauges empty over the storm day (§60f).** Close: NWISWeb 2012 / the USGS Sandy report.
- **Atlantic City peak ~+0.5 m high on every run** (+0.47…+0.55). Close: NACCS at the nearest save
  point vs the gauge; the gauge's datum (Phase 3 desk check).
- **NY-bay waves-on crest = seiche phase** (§61 (g)): how much of the wave gain survives a fine
  `dtwave` is unmeasured (the dtwave-600 swing leg was never run).
- **Unread from the 10-05 pre-registration:** do the Maurice / Mullica / Tuckahoe / Rancocas reaches
  wet; hm0 vs depth at the SnapWave band's 53 boundary cells shallower than −20 m. Close: one read of
  the premier's map output.
- **Test 8 (setup-only wavemaker line):** evidence says don't run it as designed (§62); user's call.
- **Buildings never re-run on the apex band (§55).** Close: `bed-nobuildings` in Phase 4.
- **No model M2 test** of the interior amplification (part 2). Close: modelled M2 at Port Reading /
  Keasbey / South Amboy / Great Kills vs the NOAA harcon table.
- **Flux cross-sections never read** (Narrows prism, Rockaway throat). Close: `crosssection_discharge`.
- **Engine follow-ups:** the interior initial-guess remap and per-point boundary direction (§43/§44)
  never built; the dead-corner rule not reported upstream; PR #363 open; the igseed issue not filed.
- **`accept_domain.py` FAILS on v3** (15 inflows on dry ground, 1 inactive; pre-existing); on a mask
  variant it needs `--mesh <template>`.
- **v3 scorer does not flag HWM 6044** (49 m from the Absecon Creek source, §40).
- **`plots.plot_hwm_residual_panels` peaks at 165 G for six arms.** Close: release per arm.
- **`metrics.csv` last-digit drift:** the read-back checks row presence and the label columns
  (`run_experiments._ROUNDTRIP_LABELS`), not the floats. Close: read → write → byte-compare once.
- **Deliberately deferred by the user:** the dune-failure `bed-postsandy` lever; an ICW (`bed-icw`)
  survey tier; raising `bay_fringe` past zmax 2.0; §49's pre-repair beach numbers; the 12-creek
  refinement band (next mesh).

## Evidence index

| topic | logs | scripts | FINDINGS |
|---|---|---|---|
| SnapWave cost anatomy | `wave_boundary_v4_2026-09-29/`, `wave_cost_2026-10-0{1,2,3}/` | `snapwave_cost.py` | §20, §61 |
| wind-direction bug + engine gates | `engine_gate_2026-09-11/`, `phase4_2026-09-13/`, `upstream_2026-09-14/` | `engine_gate.py`, `snapwave_direction_check.py` | §43, §44 |
| IG / wavemaker / back-bay lift | `engine_gate_2026-09-17/`, `wavemaker_reads_2026-09-20/` | `build_wavemaker_line.py` | §45, §47, §49, §62 |
| buildings | `phase8_2026-09-17/`, `refreeze_2026-10-05/buildings/` | `burn_building_footprints.py` | §55 |
| NY edge drain / mask repair | `great_kills_2026-09-21/`, `mask_repair_2026-09-22/` | `restage_mask_repair.py`, `paired_hwm_bootstrap.py --by-basin` | §50 |
| v4 ring, line, rivers | `v4_design_2026-09-24` … `-28/`, `v4_freeze_2026-09-28/` | `audit_region_v4.py`, `build_river_table_v4.py`, `build_riverbeds_v4.py` | part 4, §53 |
| v4 SLR gate | `v4_gate_2026-09-28/`, `-29/` | `overflow_check.py` | part 4 |
| head-of-tide variants, Union Lake dam | `v4_hot_2026-10-02/`, `-03/`, `union_lake_2026-10-05/`, `river_memo_2026-10-02/` | `setup_boundary_depth.py` | part 4 |
| A+ pre-freeze audit | `audit_v4_hot_plus_2026-10-05/` (edge walk, blocked ground, channels + 3DEP, inflows, v4-vs-v3) | in-folder scripts | §54 (h)–(l), part 4 |
| Raritan / harbour low | `raritan_2026-10-05/` (A/B tide axis, C kills bed, D drain census) | `kills_transects.py`, `drain_census.py` | part 4 (e) |
| bed fixes + walls + inflows | `bedfix_2026-10-05/` (cohansey, gmrt_reaches, walls, inflows) | `build_usace_unpave_v4.py`, `build_riverbed_cohansey_v4.py`, `build_riverbeds_gmrt_v4.py`, `download_ehydro_v4.py` | part 4 |
| inland water | `inland_water_v4_2026-09-29/`, `inland_water_2026-10-05/` (DECISIONS.md) | `build_inland_water_v4.py` | §54, part 4 |
| wave boundary for v4 | `wave_boundary_v4_2026-09-29/`, `bedfix_2026-10-05/snapwave_preflight_n69_inf.txt` | `check_snapwave_domain.py` | §52 |
| re-freeze first results | `reports/v4_first_results_2026-10-09/`, `logs/refreeze_2026-10-06/` | `v4_first_results.py --preset refreeze` | part 4 (g) |
| no-infiltration test | `logs/noinfil_2026-10-08/` | — | part 4 (g) |
| determinism + packing | `logs/det_test_2026-10-09/`, `logs/pack_test_2026-10-07/` | `engine_gate.py` | §44 |
| hourly-wave swing | `logs/waves_swing_2026-10-07/` | in-folder scripts | §61 (g) |
| meteo, dunes, briefs, data moves | `pressure_2026-10-07/` (blend pressure < 1–4 cm), `wind_x110_reads_2026-09-22/`, `naccs_chs_2026-10-06/`, `dune_lever_2026-09-23/` (pre/post-Sandy crests — the breach arm), `weekly_2026-10-06/build_brief.py`, `data_move_2026-10-05/swap.sh` | in-folder | part 4 (e), §38 |
| v4 vs v3 like for like; IG seed | `premier_2026-10-11/`, `ig_det_2026-10-15/`, `reports/v4_first_results_2026-10-11/` | `v4_first_results.py --preset premier`, `engine_gate.py` | §44, part 4 |
| SLURM stdout | `logs/slurm/<yyyy-mm>/` (filed by month; batch scripts write to `logs/`) | — | — |
| seeded engine, cap test | `ig_det_2026-10-15/` (sens3 / sens3c), `ig_cap_2026-10-17/` | `engine_gate.py` | §44 (d)–(e) |
| lake audit + fix, lower-only paint | `lake_audit_2026-10-15/`, `rebaseline_2026-10-15/`, `lakes_min_2026-10-17/` | `build_lake_fix_overlay.py`, `rebuild_subgrid.py --overlay <key>:min` | part 4 (h) |
| inflow re-stage | `restage_2026-10-17/` | `setup_boundary_depth.py`, in-folder `compare_templates.py` | part 4 (h) |

## Disk and cluster

- **Home** (`/cache/home`, GPFS): 100 G soft / 110 G hard; **68.6 G on 2026-10-17**. Ask
  `/usr/lpp/mmfs/bin/mmlsquota -u $USER --block-size auto cache` (lags ~10 min).
- **Scratch** (`/scratch/tpj8`): 1 T soft / 2 T hard, **567 G on 2026-10-17** (incl. the 39 G
  `_template_inflows`). 🔴 **Not backed up; files not accessed for 90 days are deleted.** `experiments/`
  and most of `data/` (the 10-05 swap is finished) live here; the durable copy is the desktop pull
  (`scripts/desktop_pull_backup.sh`) — re-run it whenever an arm is scored. The engine sources
  (`/scratch/tpj8/sfincs-build/`) live here too; the patches are in `hpc/patches/` + `docs/upstream/`.
- **Camden** (`cmain`, halc*) sees its OWN `/scratch`: stage inputs via home (the igseed recipe).
- **Maintenance:** every hal/halk node, next **11-10 08:00 → 11-11 23:59**, then 12-15.
- **10-17:** ~186 `main` nodes draining ("Reduce Temps"); Camden had idle nodes.
- Claude Code may run on a LOGIN node (`amarel*`) or a small VS Code allocation (10-17: 4 CPU / 32 G):
  heavy work through `sbatch` / `srun`.

## Housekeeping

- Last cleanup: **2026-10-17** (the igseed partials + Camden duplicates, 87 G). Before: 2026-10-15
  repo + scratch + home (`reports/cleanup/deletion_manifest_2026-10-15.md`).
- Kept on purpose, user's call to remove: `data/NACCS/_originals_pending_delete/` (3.2 G — the only
  byte-reproducible source of v3's NACCS boundary, part 3; durable copy in
  `~/nj_bight_durable/NACCS_originals_pending_delete/` with `MD5SUMS`); `data/gtsm/retired_v1_monmouth/`;
  the v1.5 / v3 notebooks and the weekly reports;
  `logs/audit_v4_hot_plus_2026-10-05/v4_vs_v3_deficit/shadow_hp_norain/` (705 MB rebuildable floodmap).
