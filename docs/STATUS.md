# STATUS — live campaign state

**Edit this file in place; keep it under ~300 lines.** It holds what is happening NOW: what is
running, what is next, what is open. When an item closes, its durable fact goes to
[FINDINGS.md](FINDINGS.md) (or CLAUDE.md §5 if it is a trap) and the item is deleted here.
Git has the history. The campaign log this file grew into until 2026-09-29 (6,767 lines) is
`git show d70dd1e:docs/STATUS.md`; FINDINGS cites it as "STATUS <date>".

Last updated: **2026-10-11** (every 10-09 job read; was 2026-10-09 12:00). The re-frozen v4 is
solved, scored and written up: `reports/v4_first_results_2026-10-09/summary.md`, FINDINGS part 4 (g).
Infiltration decided (stays on; `cnb` with ERA5-Land soil state next). Open: declaring the v4 premier,
submitting the v3-reference job. Scratch cleaned 10-11 (was over its soft quota).

---

## Now

- **v3 is DONE** (2026-09-24). Reference `naccs-premier` on the repaired mask — HWM RMSE 0.329 /
  bias −0.143 (median, 50 m, n 94), MOTF CSI 0.706. Its shared-bed-fix re-run
  (`bed-v4fixes+wave-dt3600`, 0.323 / −0.157) is read; whether it replaces the reference is the
  user's call (it is hourly waves + the Great Egg un-pave, FINDINGS §54 (h)).
- **v4 = `v4_refreeze`** (= `v4_hot_plus_walls` + Lewes; `378014e154b4ff41`; bed `_subgrid_refreeze`,
  Keansburg + Overpeck weirs, ERA5-bilinear meteo on the engine's corner convention). Run B
  (`v4_hot_plus_walls`) stays in its own domain as the pre-re-freeze record.
- **10-09 scores** (median, 50 m, n 110; FINDINGS part 4 (g)):

  | arm (names since the 10-11 re-baseline) | RMSE | bias | CSI | note |
  |---|---|---|---|---|
  | **`naccs-premier`** (NACCS wind) | **0.436** | −0.110 | 0.728 | THE premier; uninterrupted |
  | `naccs-nowaves` (NACCS wind) | 0.490 | −0.240 | 0.718 | its twin |
  | parked: ERA5 `naccs-premier` | 0.479 | −0.174 | 0.713 | ⚠️ soil RESET at resume (§59) |
  | parked: ERA5 `naccs-nowaves` | 0.539 | −0.361 | 0.698 | |
  | parked: ERA5 `naccs-nowaves+rain-noinfil` | 0.407 | −0.294 | 0.689 | FAR 0.144 → 0.186 |

  Wave lift −0.060 [−0.115, −0.019]; NACCS wind (waves off) −0.049 [−0.084, −0.023]; v4 trails v3
  by +0.18 on the 94 shared marks — mostly the rain-pond basins, and switching infiltration off
  closes most of it. The Raritan Bay low is mostly gone waves-on (`raritan_bay` bias +0.01, South
  Amboy −0.03 m; seiche-phase caveat). SLR gate +0/+2/+3 m: no outflow edge wets.

## Running

- **62561797** `inflow_move` (10-11 evening, 32 c / 128 G / 6 h): the moved-inflow test (PICK UP 1b).
- **62561016** `motf_gap_rescore` (submitted 2026-10-11 evening, 400 G, 12 h; `logs/motf_gap_2026-10-11/`):
  rebuilds `sandy_motf_valid_nj_v4.tif` with `Domain.motf_gap_boxes_xy` (checks it changed ONLY
  inside the box, 1 → 0), freezes `metrics_2026-10-11_pre_motf_gap.csv`, then `--validate-only` the
  five v4_refreeze arms serially (~1.5 h each). Then: re-render the status notebook (PICK UP 1a).
- **62551000** `premier_candidates` (submitted 2026-10-11 ~14:00; one exclusive emeraldrapids node,
  23 h, `--requeue`; `logs/premier_2026-10-11/`): v3 `bed-v4fixes+wave-dt3600+wind-naccs` + twin
  (the matching v3 reference) and v4 `naccs-premier+rain-noinfil` + twin (like-for-like, v3 has no
  infiltration): suite → stage both domains → verify each vs its pair → 4 solves side by side →
  validate → paired reads. Progress: `CHECKS.txt`; per-step markers in `state/`. 🔴 EXPECT_MD5
  guards experiments.py, model.py, premier.py, run_experiments.py, sfincs_run.slurm,
  sfincs_restart.py and the script — do NOT edit them until it STARTS. Must start by ~Mon 09:00 or
  it waits for maintenance (10-13 08:00 → 10-14 23:59). Read: v3 meteo pair (old ERA5 vs NACCS),
  v3 wave lift, v4 premier vs v3 reference on shared marks (`v4_first_results.py`, new preset).
- **62554764** `premier_v3` (13:41, emeraldrapids, 32 cores, 23 h): THE V3 HALF of 62551000,
  re-launched — 62551000's verify refused the v3 arms because their `sfincs.weir` is the EXACT
  frozen-mesh file while the 10-05 pair carries the hydromt-rounded one (crests ±5 cm, the 10-07
  `restore_weir` fix); this copy accepts the frozen-mesh file. So the v3 pair (new vs 10-05)
  differs in meteo AND the levee crests' rounding. Solves started 13:42, 214 weir points.
  62551000 will end non-zero (its v3 pipeline exit) even when its v4 half is fine — read CHECKS.txt.

## ☀️ PICK UP (Monday 10-12)

0. ⚠️ **Maintenance 10-13 08:00 → 10-14 23:59 takes every hal node.** A waves-on v4 solve is
   10–11 h on emeraldrapids; anything submitted after ~Mon 18:00 will not start until 10-15.
1. ✅ **Infiltration stays ON (user 10-11); next run uses `cnb` with data (after maintenance).**
   The no-infiltration HWM gain is closed-basin rain ponding still rising at tstop, and the sea
   never enters Wreck Pond in either arm (FINDINGS part 4 (g); `logs/infiltration_2026-10-11/`).
   Soil on 10-28 (`logs/soil_moisture_2026-10-11/README.md`): ERA5-Land relative wetness 0.73–0.78
   on the coastal plain (3rd driest Oct-28 of 2002–16), AORC 0.3 mm in the 5 days before (AMC I),
   no drought (USDM 10-23) — DRIER than the AMC II we assume, so the curve number errs toward too
   LITTLE infiltration, not too much. `cnb` = CN with recovery: `smax` / `seff` / `ks`; its soil
   state IS in the restart file (type 4, `scs_Se`), unlike `cna` (§59). To build: `create_cn_with_
   recovery` on the quadtree (needs a ksat layer — SSURGO), `effective` ≈ 1.5 (log-S interpolation
   AMC II → I by the wetness anomaly) with brackets 1.0 / 2.38; `_infiltration_keys` for the cnb
   keys; `restart.py`'s soil-RESET warning only for `cna`; a toy resume test. Then re-baseline.
1a. **Status notebook, fig. 2 (peak map) → "rise above normal water" (user 10-11).** A level in
   m NAVD88 reads a river flowing on a 7 m bed as deep water. Plot instead, per face: normally-wet
   faces → peak − the pre-storm high water; normally-dry faces → depth. Baseline = max of the
   premier's own early 6-h `zsmax` blocks; first run `logs/notebook_qc_2026-10-11/baseline_check.py`
   (surge already in by 10-28 evening? river reaches filled by then?) to pick the blocks. Re-render
   together with fig. 4 once 62561016 has re-scored. The notebook holds all its code (edit in place).
1b. **Inflow pile-ups — user approved 10-11; screen DONE, test RUNNING (62561797).**
   `scripts/relocate_coarse_inflows.py screen` (coarse face > 50 m, depth at the source > 2 m,
   peak falls > 1 m within 4 km): 12 of 61 — NJ: Salem R. 01482500, 01475001, Crosswicks 01464500,
   Assunpink 01464000; PA/DE: Chester, Ridley, Frankford, Pennypack, Poquessing, White Clay, Red
   Clay, Brandywine (`logs/notebook_qc_2026-10-11/relocate_screen.txt`); every unflagged source
   stands 0.3–1.9 m deep. Each moves 1.1–4.2 km down its creek to the first ≤ 50 m channel face.
   🔴 `discharge_geodataset` is MASK-DEFINING (the 500 m inflow walls are built from it), so the
   walls must stay on the OLD points: a registry change needs a separate wall-points source, or
   the mask, fingerprint and old crossings all move. Test: full-window copy of the rain-off arm
   with only `sfincs_netsrcdisfile.nc` changed (`/scratch/tpj8/engine_gate/inflow_move_2026-10-11/`),
   `logs/inflow_move_2026-10-11/compare.txt`. Then: ship in the `cnb` re-baseline.
   **Next mesh (user 10-11: OK to refine around problem rivers):** a 25–50 m refinement band along
   the 12 flagged creeks (and the Christina, 25 m but still +0.9 m) — a new mesh is a new domain
   freeze, so it waits for the next one; the source moves are the fix until then.
2. ✅ **v4 premier DECLARED (user 10-11): `naccs-premier` on `v4_refreeze` = the NACCS-blend pair**
   (was `wind-naccs+naccs-premier`, uninterrupted; RMSE 0.436 / bias −0.110 / CSI 0.728). Re-baseline
   done: rows frozen (`metrics_2026-10-11_pre_rebaseline.csv`), the ERA5 pair + ERA5 noinfil parked
   in `_pre_rebaseline_2026-10-11/`, NACCS pair renamed into place, registry + tests + the 10-09
   preset paths updated, audit 7/7. The next re-baseline is the `cnb` premier (item 1). Blend
   pressure: rebuild with `--pressure era5` in that round (< 1–4 cm, 10-07).
   **v3 matching reference job SUBMITTED** (62551000, "Running" above); when it is read, re-baseline v3's
   `naccs-premier` the same way onto `bed-v4fixes+wave-dt3600+wind-naccs`.
3. **Run-to-run noise (FINDINGS §44).** Lone 64-thread copies differ; the 1-thread pair was cut
   by its 5 h limit but differs from the first SnapWave call. Next, cheapest first: run the
   1-thread pair to the end of a 1 h window (the first call already decides it); if 1-thread
   repeats, it is a threading race; if not, build with `-finit-real=snan -finit-integer=-999999`
   and look for the uninitialised field. Until then: a few cm at an NY-bay gauge between two
   waves-on arms is noise.
4. **Hourly-wave swing test (FINDINGS §61 (g))**: only the dtwave 3600 leg finished
   (`/scratch/tpj8/engine_gate/swing_3600/`); the 600 leg was killed at 14 h (its partial output was
   deleted 10-11). Re-run 600 alone with ~20 h, and a SECOND 3600 copy so §44's noise can be
   subtracted. Low priority unless the NY-bay crest matters for a decision.
5. Small: record the meteo convention in `metrics.csv` / `provenance.txt` (like
   `snapwave_direction`); re-run `scripts/desktop_pull_backup.sh` (the 10-09 arms are scored and live
   only on scratch until it runs); finish the data swap (below); USER: commit (reports + docs `git add`-ed 10-11).

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

- **River inflows that pile up on a ~0 m bed (FINDINGS part 4, "Still open"):** peak at the
  source vs bed — Ridley Ck 5.98 / 0.27, Chester Ck 5.51 / 0.04, Frankford Ck 6.70 / 2.56,
  Red Clay 5.40 / −0.02, White Clay 4.62 / −0.16, Christina 3.83 / −0.05 (PA/DE, unscored), and
  **Salem R. at Woodstown 4.38 / 0.01 (NJ)** (`logs/notebook_qc_2026-10-11/river_heads.py`).
  Most other "high water at river heads" on the peak map is the river's own stage on a 4–8 m
  bed (depth 0.3–1.5 m): the v3-inherited southern cuts sit at the gauges, above today's head
  of tide (the Great Egg reach above Mays Landing). **Mechanism (10-11):** every
  one sits on a COARSE face (100–200 m; Christina 25 m) over a narrow creek valley (`z_zmax`
  10–33 m) and steps down 2–3.5 m in 2 km on rain-off alone; the Maurice on a 25 m wet face is
  flat (`logs/notebook_qc_2026-10-11/inflow_pileups.py`). Close: see PICK UP (folds into the `cnb`
  re-baseline after maintenance).

- **Southern back-bay deficit (§57):** mechanism unknown; the Great Egg inlet sill (FINDINGS
  §54 h) is now a candidate share. Close: the v3 re-run's Great Egg / Ocean City pre-storm
  bay-minus-pier; the calm-month datum check of the seven southern USGS stations.
- **NY east bay ~0.2 m low after the repair (§50);** `lower_bay_si_shore` (n 3) keeps moving the
  wrong way; the cross-Narrows tilt at `sss_narrows_bkln`. Close: per-mark and Narrows Q(t).
- **Great Kills sensor offset cause (§50).** Close: USGS STN deployment / survey records.
- **12 USGS gauges empty over the storm day (§60f).** Close: NWISWeb 2012 / the USGS Sandy report.
- **Atlantic City peak ~+0.5 m high on every run, v3 and v4, waves on and off** (+0.47…+0.55).
  Close: NACCS at the nearest save point vs the gauge; the gauge's datum.
- **IG on the premier costs ~4 h with no wavemaker (§45).** Close: user decision.
- **NY-bay waves-on crest = seiche phase** (FINDINGS §61 (g)): how much of the NY-bay wave gain
  survives a fine `dtwave` is unmeasured. Close: PICK UP 4.
- **v4 waves-on is not repeatable run to run (§44).** Close: PICK UP 3.
- **Capped SnapWave calls inject river pulses on v4 (§44, 10-11):** the premier's 10-29 18:00 and
  20:00 calls ended at the 50-iteration cap; hm0 to 11 m in the upper Delaware Bay for an hour and a
  ~1 m long wave up the river (waves-off twin clean). Close: count capped calls in every v4 log;
  test a higher cap / `snapwave_crit` on a restart cut from 10-29 17:00 (`engine_gate.py make`);
  check whether any face's `zsmax` is set inside a capped hour.
- **Infiltration vs the rain-pond marks** (part 4 (d), (g)). Close: user call + the lakes' timing.
- **Unread from the 10-05 pre-registration:** do the Maurice / Mullica / Tuckahoe / Rancocas reaches
  wet on the re-freeze; hm0 vs depth at the SnapWave band's 53 boundary cells shallower than −20 m
  (depth-limited breaking at the boundary?). Close: one read of `naccs-premier`'s map output.
- **Test 8 (setup-only wavemaker line):** evidence says don't run it as designed (FINDINGS §62,
  `reports/literature_review_2026-10/B2_back_bay_setup_followup.md`); user's call. Optional
  check: USGS doi:10.5066/P99K85SW (Defne & Ganju 2019) — server timed out 10-03.
- **Buildings never re-run on the apex band (§55).** Close: `bed-nobuildings` on the premier.
- **No model M2 test** of the interior amplification (FINDINGS part 2). Close: modelled M2 at
  Port Reading / Keasbey / South Amboy / Great Kills vs the NOAA harcon table.
- **Flux cross-sections never read** (Narrows prism, Rockaway throat). Close: read
  `crosssection_discharge` from a finished run.
- **Engine follow-ups:** the interior initial-guess remap and per-point boundary direction
  (§43/§44) never built; the dead-corner rule not reported upstream; PR #363 still open.
- **`accept_domain.py` FAILS on v3** (15 inflows on dry ground, 1 inactive; pre-existing); on
  A+ it needs `--mesh <template>` (the default reads v4's frozen mesh).
- **v3 scorer does not flag HWM 6044** (49 m from the Absecon Creek source, §40).
- **`plots.plot_hwm_residual_panels` peaks at 165 G for six arms.** Close: release per arm.
- **`metrics.csv` last-digit drift** (no `round_trip` guard in `_write_outputs`). Close:
  read → write → byte-compare once.
- **`_drop_detached_active_islands`** logs "N BC cells" before the BC exists (always 0).
- **Deliberately deferred by the user:** the dune-failure `bed-postsandy` lever; an ICW
  (`bed-icw`) survey tier; raising `bay_fringe` past zmax 2.0; §49's pre-repair beach numbers
  (flagged in FINDINGS with the post-repair baseline beside them).

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
| SLURM stdout | `logs/slurm/<yyyy-mm>/` | — | — |

## Disk and cluster

- **Home** (`/cache/home`, GPFS): 100 G soft / 110 G hard; **68.3 G on 2026-10-11**. The data swap
  is unfinished: `data/elevation_v4/enc`, `gmrt_v4.tif`, `inland_water`, `nj_10ft_dem_v4.tif.ovr`
  (~2.1 G) are still on home — job 62282097 refused at `enc` because scratch holds an extra
  `raw_cohansey/`; finish with a diff that allows dst-only files. Ask `/usr/lpp/mmfs/bin/mmlsquota -u $USER
  --block-size auto cache` (lags ~10 min).
- **Scratch** (`/scratch/tpj8`): 1 T soft / 2 T hard. 🔴 **Not backed up; files not accessed for
  90 days are deleted.** `experiments/` and now most of `data/` live here; the durable copy is
  the desktop pull (`scripts/desktop_pull_backup.sh`) — re-run it whenever an arm is scored.
- **Attic:** `/scratch/tpj8/nj_bight_attic_2026-09-30/` (manifest lists every file; purges
  itself after 90 days).
- **Maintenance:** every hal/halk node, 10-13 08:00 → 10-14 23:59, then 11-10 and 12-15.
- Claude Code may run on a LOGIN node (`amarel*`): heavy work through `srun` on an allocation.

## Housekeeping

- Last cleanup: **2026-10-11 scratch**, `reports/cleanup/deletion_manifest_2026-10-11.md` (~374 G: finished
  engine_gate tests, the Lewes test, the v4 trial build, every `snapwave.upw`, the superseded v4 /
  v4_hot / v4_hot_plus floodmaps, the `_pre_darby` / `_pre_flankwall` / `_pre_damcrest` runs). Also 10-11:
  removed `reports/v4_first_results_test/` (a trial run of the report script); report job stdout
  (`reports/**/jobs/*.out`) is gitignored like `logs/`.
- Kept on purpose, user's call to remove: `data/NACCS/_originals_pending_delete/` (3.2 G — the
  only byte-reproducible source of v3's NACCS boundary, FINDINGS part 3);
  `data/gtsm/retired_v1_monmouth/`; the v1.5 / v3 notebooks and the weekly reports;
  `logs/audit_v4_hot_plus_2026-10-05/v4_vs_v3_deficit/shadow_hp_norain/` (705 MB rebuildable
  floodmap, on scratch; user 10-05: keep for now).
- Candidates for the user (10-05, not deleted): `data/elevation_v4/inland_water/
  inland_water_bed_v4_draft.tif` (byte-identical to the registered `inland_water_bed_v4.tif`);
  `data/discharge_v4/usgs_sandy_discharge_v4_hot_plus.nc` will carry the 4 inflow moves after
  job 62279940 (only a future A+ restage reads it).
