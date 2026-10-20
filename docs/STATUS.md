# STATUS — live campaign state

**Edit this file in place; keep it under ~300 lines.** It holds what is happening NOW: what is
running, what is next, what is open. When an item closes, its durable fact goes to
[FINDINGS.md](FINDINGS.md) (or CLAUDE.md §5 if it is a trap) and the item is deleted here.
Git has the history. The campaign log this file grew into until 2026-09-29 (6,767 lines) is
`git show d70dd1e:docs/STATUS.md`; FINDINGS cites it as "STATUS <date>".

▶ **PICK UP (10-20 evening): Phase 4 = job 62757492, HELD by the user** until (a) the creek beds are rebuilt and
checked (**job 62759318**) and (b) the Keansburg weir test reads (**job 62759323**). Then: nudge the Sluice gauge onto
its opened channel face, adopt the weir if it passes, point the Phase 4 arms at the `*_creeks` beds, refresh
`logs/rebaseline_2026-10-19/expected.md5`, `--check` + tests, retire the four old beds, user releases 62757492.

Last updated: **2026-10-20** — desk checks done; gauge nudges; 6-min NOAA scoring; `fa_rainonly` retired; creek
beds (Beach Creek + 52 Delaware Bay creek groups, an ASSUMED bed); Keansburg weir candidate; HWM inventory + STN
records + noted marks; the run gallery simplified (view runs, next-premier list). Before: 10-19 (Phase 4 arms +
job drafted; gallery + one public site; depth convention).

---

## Now

- **v3 is DONE** (2026-09-24). Reference `naccs-premier` — HWM RMSE 0.329 / bias −0.143 (median, 50 m, n 94),
  MOTF CSI 0.706; re-run on the seeded engine in Phase 4 (`p4-ref` / `p4-ref-nowaves`).
- **v4 = `v4_refreeze`** (`378014e154b4ff41`). Premier `naccs-premier` (NACCS-blend wind, CN infiltration,
  unseeded engine): RMSE 0.436 / bias −0.110 (n 110), CSI 0.780; without the 5 noted marks 0.408 / −0.095 (n 105);
  10 marks outside ±0.5 m, inventoried in FINDINGS part 4 (h).
- **Heading for:** the Phase 4 re-baseline (below), before maintenance 11-10.

## Running (10-20)

- ▶ **62759318 `beds_creeks`** — rebuilds `_subgrid_refreeze_lakes_min` / `_nobuildings` / `_breach_wreck0` /
  `_wreck165` as `*_creeks` (+ `usace_unpave_backbay_v4` with Beach Creek, + `creek_bed_nj10ft_v4:min`), then
  `logs/creek_beds_2026-10-20/check_beds.py` (changes inside the fix boxes only; no raise outside Beach Creek;
  the Sluice gauge's connection level before / after).
- ▶ **62759323 `kburg_weir`** — base vs `logs/keansburg_pocket_2026-10-20/candidate_sfincs.weir` (railroad gap at
  Pews OPEN), two 60 h waves-off cuts of naccs-nowaves (`/scratch/tpj8/engine_gate/keansburg_2026-10-20/`) →
  `test_result.txt`. Adopt if 6155 / 6156 / 6133 drop and 6154 / 6157 / 6158 / 6132 hold: copy into
  `data/structures_v4/sfincs.weir` AND the template (weir only — no fingerprint move; check the log's
  "structure u/v points"). Next leak: the Thornes Creek marsh near Rt 36 (unmapped).
- ⏸ **62757492 `phase4`** HELD (user). Its EXPECT_MD5 predates 10-20's code edits — refresh before release.
- 🔴 Side-by-side `engine_gate.py run` copies need `taskset` on disjoint cores (FINDINGS §44 (i)).

## ⭐ FINAL AUDIT → "the v4 premier is ready" (plan approved 10-15)

Plan: `~/.claude/plans/i-think-i-m-ready-warm-trinket.md`. Phases 0–3 ✅ (seed patch, cleanup, seeded-engine
test, code; details FINDINGS part 4 (h), §44, git log). 🔴 USER: re-run `scripts/desktop_pull_backup.sh` once.

- **Closed 10-20 (user; facts in FINDINGS part 4 (h)):** no lake pool start; no Wreck Pond culvert; Wreck Pond
  "band" = the 1st Ave bridge deck, already removed — no fix; Atlantic City +0.5 m = NACCS forcing; paved
  channels — federal channels clear (`audit_paved_channels.py` retired); `noaa_cape_may` /
  `usgs_tidal_cape_may_harbor` / `usgs_tidal_barnegat_light` nudged onto sea-connected faces (old v4_refreeze
  runs audit "OBS STALE", truthfully); NOAA gauges scored from 6-min on v3 + v4; `motf_km2_fa_rainonly` retired
  (MOTF false alarms: rain 79 / surge 27 / waves 22 of 128.5 km², twin-run split); creek beds = an ASSUMED bed at
  ≈ MLW (Salem River + Mannington Creek left out); HWM marks 6169 / 6202 (questioned) and 6121 / 6398 / 6188
  (run-up) kept, drawn hollow, `hwm_*_scored_excl_noted` beside the headline.
- **Phase 4 (job 62757492, `logs/rebaseline_2026-10-19/`):** ONE 2-node emeraldrapids job, seeded engine
  `…igseed-wmseed-1-gf11`, 40 h: stage 12 v4_refreeze + 2 v3 arms, 4 × 16-thread slots per node, each node
  validates its own. Node 1 (`node1.txt`): v3 `p4-ref`, `p4-premier`, its repeat, the two `rhoa` null copies,
  `bed-breach-wreck0`. Node 2: `p4-nowaves`, `+wave-nowavemaker`, `cnb` 1.0 / 2.38, `bed-nobuildings`,
  `bed-breach-wreck165`, `src-deal-overtop`, v3 `p4-ref-nowaves`. PREREG `PREREG.md`. Budget: v4 waves-on
  ≈ 10 h on emeraldrapids. 🔴 A preempted-and-RESUMED waves-on arm is a different run (§44 (j)): check every
  `restart_history.txt` before pairing; re-run a resumed premier / repeat / `rhoa` copy.
- **Phase 5–6:** ⚠️ update `scripts/publish_gallery.py` `NEXT_PREMIER` when the new premier lands. Reads →
  frozen premier (user tags git), `docs/MODEL.md`, validation summary, research-group brief (incl. the
  status-notebook "rise above normal water" fig., `logs/notebook_qc_2026-10-11/baseline_check.py`), docs, backup.
- **Gallery / site:** `~/sandy_flood_site` = `tyfolino/sandy-flood-model`, written by `scripts/publish_gallery.py`
  (user commits + pushes); figures by `nj_sfincs/gallery.py` in every validate (`--no-gallery` to skip),
  re-draw `scripts/build_gallery.py` / `hpc/build_gallery.slurm`. Depth convention: CLAUDE.md §6.

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

**Cohansey bed sources (from the sfincs-nj-agri session, 10-20; unchecked here):** our Cohansey is the stated
1.2 m-below-MLLW section (no soundings above the mouth). Candidates: USACE NCF federal channel `CENAP_CO_01_CRC`
(6 ft authorized, 100 ft, 2.7 mi ≈ Fairton → Bridgeton; no eHydro, last dredging ~1985 — authorized ≠ actual);
Coast Pilot 3 ch. 6 (controlling ~7 ft at the entrance); 1905–06 USACE survey sheets with soundings, Rutgers RUcore
`rutgers-lib:56574` (mouth) / `56588` (Bridgeton → Lupton's Landing). Big Timber H09886 / Alloway H10112 / Cohansey
mouth D00081 are already in the hierarchy; Oldmans (H10027) is outside the ring. After Phase 4.
The sfincs-nj-agri session's test (10-20, its 100 m model, calm May 2023 week, beds only): soundings / a stated depth
fixed most of its creek tide — Big Timber (H09886, MLW → MLLW −0.058) Westville 0.47 → 0.97 of the expected range;
Cohansey at 7 ft below MLLW (Coast Pilot controlling depth) mouth → Fairton: Greenwich 0.55 → 0.72. Ours: Greenwich
0.62 of observed on the 1.2 m-below-MLLW section — a deeper Cohansey section is the candidate fix (riverbeds_hierarchy
rebuild).

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
- **Waves-on noise band (§44 (e)):** not the cap (10-17); how wide is it through the peak? One
  null copy is ONE draw of the band. Close: Phase 4's two full-length null copies (`rhoa` 1.2501 /
  1.2499; user 10-17).
- **Capped calls inject river pulses on v4 (§44 (h)).** Close: count capped calls in every v4 log;
  check whether any face's `zsmax` is set inside a capped hour (niter 800 still caps the t = 0 call).
- **Southern back-bay deficit (§57):** the Great Egg inlet sill (§54 h) a candidate share. Close: the
  v3 re-run's Great Egg / Ocean City pre-storm bay-minus-pier; calm-month datum check of the seven
  southern USGS stations.
- **NY east bay ~0.2 m low after the repair (§50);** `lower_bay_si_shore` (n 3) moves the wrong way;
  the cross-Narrows tilt at `sss_narrows_bkln`. Close: per-mark and Narrows Q(t).
- **Great Kills sensor offset cause (§50).** Close: USGS STN deployment / survey records.
- **12 USGS gauges empty over the storm day (§60f).** Close: NWISWeb 2012 / the USGS Sandy report.
- **NY-bay waves-on crest = seiche phase** (§61 (g)): how much of the wave gain survives a fine
  `dtwave` is unmeasured (the dtwave-600 swing leg was never run).
- **Unread from the 10-05 pre-registration:** do the Maurice / Mullica / Tuckahoe / Rancocas reaches
  wet; hm0 vs depth at the SnapWave band's 53 boundary cells shallower than −20 m. Close: one read of
  the premier's map output.
- **IG in the water:** the v3 / old v4 premiers compute IG but do not couple it (`snapwave_igwaves = 1`, no
  `wvmfile`; §45). ✅ The Phase 4 premier carries the wavemaker (user 10-17; line `snapbeach`, user 10-19;
  engine `…igseed-wmseed-1…`, repeat test passed — §44 (j)) with a no-wavemaker arm beside it.
  ⚠️ `dep_subgrid_lev0.tif` is NaN over the Cape May peninsula block (no level-1 faces there).
- **Test 8 (setup-only wavemaker line):** evidence says don't run it as designed (§62); user's call.
- **Buildings never re-run on the apex band (§55).** Close: `bed-nobuildings` in Phase 4.
- **No model M2 test** of the interior amplification (part 2). Close: modelled M2 at Port Reading /
  Keasbey / South Amboy / Great Kills vs the NOAA harcon table.
- **Flux cross-sections never read** (Narrows prism, Rockaway throat). Close: `crosssection_discharge`.
- **Wavemaker IG spectrum shift (upstream, untouched):** `dphi = 2π·1e-6/f` moves each component's
  frequency up by 1e-6/f Hz — with `freqminig` 0 the lowest bin goes 0.0005 → 0.0025 Hz, distorting
  the low end. Changing it changes physics; report upstream with the seed issue.
- **Engine follow-ups:** the interior initial-guess remap and per-point boundary direction (§43/§44)
  never built; the dead-corner rule not reported upstream; PR #363 open; the igseed issue not filed.
- **`accept_domain.py` FAILS on v3** (15 inflows on dry ground, 1 inactive; pre-existing); on a mask
  variant it needs `--mesh <template>`.
- **Basin labels on v4 inherit v1's `shark_river` box** (x < 584,300, y < 4,450,800 in `domain.py`
  `_V1_BASIN_RULES` / `_V1_5_…`): Wreck Pond mark 6129 is grouped `shark_river`, its neighbour 6130
  `barnegat_bay`. Per-basin numbers only; close: give v4 its own Wreck Pond / Shark River split (a
  domain change — re-check the port gate, which pins the v1 order).
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

- **Home** (`/cache/home`, GPFS): 100 G soft / 110 G hard; **63.1 G on 2026-10-19**. Ask
  `/usr/lpp/mmfs/bin/mmlsquota -u $USER --block-size auto cache` (lags ~10 min).
- **Scratch** (`/scratch/tpj8`): 1 T soft / 2 T hard, **689 G on 2026-10-19 before the 37 G delete** (the three new beds) (incl. the 39 G
  `_template_sealed_pre_inflows_2026-10-06` — deletable once Phase 4 has staged from the new one). 🔴 **Not backed up; files not accessed for 90 days are deleted.** `experiments/`
  and most of `data/` (the 10-05 swap is finished) live here; the durable copy is the desktop pull
  (`scripts/desktop_pull_backup.sh`) — re-run it whenever an arm is scored. The engine sources
  (`/scratch/tpj8/sfincs-build/`) live here too; the patches are in `hpc/patches/` + `docs/upstream/`.
- **Camden** (`cmain`, halc*) sees its OWN `/scratch`: stage inputs via home (the igseed recipe).
- **Maintenance:** every hal/halk node, next **11-10 08:00 → 11-11 23:59**, then 12-15.
- **10-17:** ~186 `main` nodes draining ("Reduce Temps"); Camden had idle nodes.
- Claude Code may run on a LOGIN node (`amarel*`) or a small VS Code allocation (10-17: 4 CPU / 32 G):
  heavy work through `sbatch` / `srun`.

## Housekeeping

- Last cleanup: **2026-10-20** (engine-gate dirs on scratch: `igseed_sens3_62670893_r0` 61 G, `swing_3600`,
  `repro_ig`, `repro`, `swing_rst`; the unused v4 wavemaker line `git rm`'d). Before: 2026-10-17 (120 G), 2026-10-15
  repo + scratch + home (`reports/cleanup/deletion_manifest_2026-10-15.md`).
- Kept on purpose, user's call to remove: `data/NACCS/_originals_pending_delete/` (3.2 G — the only
  byte-reproducible source of v3's NACCS boundary, part 3; durable copy in
  `~/nj_bight_durable/NACCS_originals_pending_delete/` with `MD5SUMS`); `data/gtsm/retired_v1_monmouth/`;
  the v1.5 / v3 notebooks and the weekly reports;
  `logs/audit_v4_hot_plus_2026-10-05/v4_vs_v3_deficit/shadow_hp_norain/` (705 MB rebuildable floodmap).
