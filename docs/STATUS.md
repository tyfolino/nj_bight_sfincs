# STATUS — live campaign state

**Edit this file in place; keep it under ~300 lines.** It holds what is happening NOW: what is
running, what is next, what is open. When an item closes, its durable fact goes to
[FINDINGS.md](FINDINGS.md) (or CLAUDE.md §5 if it is a trap) and the item is deleted here.
Git has the history. The campaign log this file grew into until 2026-09-29 (6,767 lines) is
`git show d70dd1e:docs/STATUS.md`; FINDINGS cites it as "STATUS <date>".

Last updated: **2026-10-11** (every 10-09 job read; was 2026-10-09 12:00). The re-frozen v4 is
solved, scored and written up: `reports/v4_first_results_2026-10-09/summary.md`, FINDINGS part 4 (g).
Nothing is running. Two calls are the user's: **infiltration** and **which arm is the v4 reference**.

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

  | arm | RMSE | bias | CSI | note |
  |---|---|---|---|---|
  | `naccs-premier` | 0.479 | −0.174 | 0.713 | ⚠️ resumed 10-29 12:00 with the CN soil RESET (§59) |
  | `naccs-nowaves` | 0.539 | −0.361 | 0.698 | |
  | `wind-naccs+naccs-premier` | **0.436** | −0.110 | 0.728 | uninterrupted |
  | `wind-naccs+naccs-nowaves` | 0.490 | −0.240 | 0.718 | |
  | `naccs-nowaves+rain-noinfil` | 0.407 | −0.294 | 0.689 | FAR 0.144 → 0.186 |

  Wave lift −0.060 [−0.115, −0.019]; NACCS wind (waves off) −0.049 [−0.084, −0.023]; v4 trails v3
  by +0.18 on the 94 shared marks — mostly the rain-pond basins, and switching infiltration off
  closes most of it. The Raritan Bay low is mostly gone waves-on (`raritan_bay` bias +0.01, South
  Amboy −0.03 m; seiche-phase caveat). SLR gate +0/+2/+3 m: no outflow edge wets.

## ☀️ PICK UP (Monday 10-12)

0. ⚠️ **Maintenance 10-13 08:00 → 10-14 23:59 takes every hal node.** A waves-on v4 solve is
   10–11 h on emeraldrapids; anything submitted after ~Mon 18:00 will not start until 10-15.
1. ❓ **USER: infiltration.** Curve number (v4 now) vs none (v3) — none fits the marks
   (−0.13 m RMSE, Barnegat Bay 1.12 → 0.50, south coast 1.47 → 0.76) and costs extent (FAR +0.04,
   more inland ponding). A middle option is a CN arm with wetter antecedent soil. The marks alone do
   not tell "CN over-infiltrates" from "v3 right for the wrong reason" (FINDINGS part 4 (d), (g));
   the rain-pond lakes' timing would (v3's keep rising a day after the ocean falls).
2. ❓ **USER: the v4 reference arm.** `naccs-premier` carries the soil reset (~0.3 m low at the
   `south_coast` marks), so as it stands it is not a clean reference. Rec.: make the NACCS-blend
   wind the default (`wind-naccs` is better on both twins, uninterrupted) and re-run the reference
   once the infiltration call is made — one solve, before the maintenance if the call comes early.
   Rebuild the blend with `--pressure era5` when it is next rebuilt (ERA5 is closer to the
   barometers; < 1–4 cm effect, 10-07).
3. **Run-to-run noise (FINDINGS §44).** Lone 64-thread copies differ; the 1-thread pair was cut
   by its 5 h limit but differs from the first SnapWave call. Next, cheapest first: run the
   1-thread pair to the end of a 1 h window (the first call already decides it); if 1-thread
   repeats, it is a threading race; if not, build with `-finit-real=snan -finit-integer=-999999`
   and look for the uninitialised field. Until then: a few cm at an NY-bay gauge between two
   waves-on arms is noise.
4. **Hourly-wave swing test (FINDINGS §61 (g))**: only the dtwave 3600 leg finished
   (`/scratch/tpj8/engine_gate/swing_3600/`); the 600 leg was killed at 14 h (partial output in
   `swing_600/`). Re-run 600 alone with ~20 h, and a SECOND 3600 copy so §44's noise can be
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
| `v4_hot_plus` | A+ (dam-crest recut 10-05) | same / `e5e9d8668fe29292` (old: `207ae7f7f0b805ae`, runs in `_pre_damcrest/`) | waves-off; run A |
| `v4_hot_plus_walls` | A+ + walls (10-05) — run B, the pre-re-freeze record | same / `77b5eda1fcd51cf6` | run B |
| **`v4_refreeze`** | **THE re-frozen v4** (10-06) = above + Lewes | same / `378014e154b4ff41` | `naccs-premier` (⚠️ soil reset; PICK UP 2) |

## Open questions (each with what would close it)

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

- Last cleanup: 2026-09-30, `reports/cleanup/deletion_manifest_2026-09-30.md`. 2026-10-11:
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
