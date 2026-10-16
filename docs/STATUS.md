# STATUS — live campaign state

**Edit this file in place; keep it under ~300 lines.** It holds what is happening NOW: what is
running, what is next, what is open. When an item closes, its durable fact goes to
[FINDINGS.md](FINDINGS.md) (or CLAUDE.md §5 if it is a trap) and the item is deleted here.
Git has the history. The campaign log this file grew into until 2026-09-29 (6,767 lines) is
`git show d70dd1e:docs/STATUS.md`; FINDINGS cites it as "STATUS <date>".

Last updated: **2026-10-16** (check-in: `igseed_sens` and `sbg_lakes` both PREEMPTED; igseed resubmitted with the core-pinning fix).
Before: **2026-10-15** (the four pre-maintenance jobs read — "Read 10-15" below; the
readiness audit for experiments is in progress). Before: 2026-10-11 (every 10-09 job read). The re-frozen v4 is
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

- **62670930** `igseed_sens` on **CAMDEN** (`cmain`, halc073, icelake 8352Y; RUNNING since 10-16 15:56;
  `logs/ig_det_2026-10-15/igseed_sens3c.slurm`). Camden sees its own `/scratch`, so the premier's 19 solver
  inputs were copied to `/cache/home/tpj8/nj_bight_staging/igseed_src_v4refreeze_premier/` (5.6 G, md5 vs the
  premier OK; a cut from it gives a byte-identical `sfincs.inp`); solves in Camden
  `/scratch/tpj8/igseed_camden/` (maps stay there — reach them via a `cmain` srun); comparisons + his + logs
  come back to `logs/ig_det_2026-10-15/sens3c_62670930_r0/`. Master threads pinned 0/16/32/48 ✅. icelake
  is ~3× slower per core on SnapWave → timeouts 16 h / 3 h, limit 22 h. Delete the home staging copy once
  read. **62670893** = the same test on `main` (PENDING) — whichever finishes first wins; cancel the other.
- **62670893** `igseed_sens` (submitted 10-16 15:55, PENDING; `logs/ig_det_2026-10-15/igseed_sens3.slurm`,
  out `/scratch/tpj8/engine_gate/igseed_sens3_<job>_r<restart>/`). Resubmit of 62645470, which ran 10-16
  10:03 → **PREEMPTED 15:47** (no `--requeue`, nothing finished; its partial dirs are in
  `/scratch/tpj8/engine_gate/igseed_sens/`, safe to delete). 🔴 That run also went at ~¼ speed:
  `engine_gate.py run` sets `OMP_PROC_BIND=spread` + `OMP_PLACES=cores`, so all four 16-thread copies
  pinned to the SAME cores (0,4,…,60) and their serial SnapWave master threads shared core 0 (node 98 %
  idle; SEED_a 30 %, ON_a 45 %, SEED_b / SEED_p 65 % after 5.6 h). sens3 runs each copy under
  `taskset` on its own core block (libgomp places stay inside the mask; thread counts unchanged), adds
  `--requeue`, and a fresh out dir per attempt. Same engine_gate / his_pair / binaries (md5) as sens2.
  Any future side-by-side `engine_gate.py run` needs disjoint cores the same way. The SEEDED engine — repeat (SEED_a vs SEED_b,
  predicted STRICT) AND sensitivity to a null perturbation (`rhoa` 1.25 → 1.2501, waves on and
  waves off), plus seeded vs unseeded (one IG sample vs another). Repeating is necessary but not
  sufficient: if capped calls amplify tiny input differences, two ARMS still diverge in the bays.
  Supersedes 62625419 (cancelled) and 62626666.

## Read 10-15 — v4 vs v3, like for like (`reports/v4_first_results_2026-10-11/`, job 62625293)

- ⭐ **On the 94 shared marks, v4 = v3 once the rain is treated alike** (v4 `+rain-noinfil` vs the
  NACCS-wind v3; median, 50 m): waves off ΔRMSE **−0.001 [−0.037, +0.035]**, every group within
  ±0.02; waves on +0.017 [−0.031, +0.057] (NY bays +0.027, v4 bias +0.05 vs v3 −0.05 — the
  waves-on crest, see the noise below). The 10-09 "+0.18" was all infiltration.
- **The premier's RMSE is two marks:** 6122 (Deal Lake, `south_coast`) and 6130 (Wreck Pond,
  `barnegat_bay`) read −2.37 / −2.34 m; without them 0.436 → 0.301 (n 108). The sea never enters
  either lake in the model (part 4 (g)).
- **Waves-on noise reaches the zsmax MAP:** infiltration off − on, median zsmax per basin, waves
  on vs waves off: Delaware Bay NJ shore +0.139 vs +0.003, DE +0.067 vs +0.005, Raritan Bay
  +0.050 vs +0.001 → ~5–14 cm of the waves-on Δ is run-to-run noise (`zsmax/*_stats.csv`).

## Read 10-15 — the four jobs that finished before maintenance (all audited `output WHOLE`, uninterrupted, one engine)

- **62551000 / 62554764 (premier candidates)** — median, 50 m, paired B 200 k
  (`logs/premier_2026-10-11/paired_*.txt`):
  v3 `bed-v4fixes+wave-dt3600+wind-naccs` **0.300 / −0.097** (n 94) vs the ERA5 twin 0.323 / −0.157:
  ΔRMSE −0.023 [−0.066, +0.014] (meteo AND the weir-crest rounding differ); bias moves +0.08 in NY
  bays and the NJ back bays, 0 on the open coast. v3 wave lift with NACCS wind −0.057 [−0.088, −0.028].
  v4 `naccs-premier+rain-noinfil` **0.307 / −0.034** (n 110), CSI 0.763 (FAR 0.143) vs the premier
  0.436 / −0.110, CSI 0.780: ΔRMSE −0.129 [−0.260, −0.010] — `south_coast` / `barnegat_bay` rain
  ponds as on 10-09. v4 wave lift (no infiltration) −0.037 [−0.074, −0.004].
- **62561016 (MOTF gap box `salem_marshes`)**: 418 km² of valid ground → 0, nothing outside the box.
  CSI +0.05 on every arm (premier 0.728 → **0.780**, FAR 0.162 → 0.098); HWM unchanged.
- **62561797 (inflow move, rain-off waves-off copy)**: the 12 moved sources drop the old-face peak
  1–10 m (e.g. idx 46 11.70 → 2.93 within 3 km); > 10 km away p99 0.2 mm; obs points ≤ 1.3 cm
  except `sss_great_kills` 7.6 cm (dry-bank sensor, §60). Ready to ship — needs the walls kept on the
  OLD points (`model.py:987` builds them from `discharge_geodataset`).
- 🔴 **§44 confirmed on FULL runs:** `naccs-premier` vs `+rain-noinfil` (waves on) differ by 0.12 m
  at Keansburg in the FIRST HOUR (rain 0.008 mm/h; the waves-off pair: 0.2 mm), 0.54 m at the
  Narrows by 12 h; the Delaware River pulse (Delaware City +1.4 m at 10-29 20:00) is in the
  premier and NOT in its twin. Capped SnapWave calls: v4 18 / 21 of 73, v3 23 / 27 of 73, on
  different hours in twins. At the marks the noise is a COHERENT NY-bay shift (+0.037 m, 44 of 46
  marks one sign) that the paired bootstrap reads as significant (CI [+0.028, +0.044]).
- 🔴 **Suspected cause (10-15, source read + a 3-line test; RUN 62625419 decides):** SnapWave's
  Herbers IG boundary draws `RANDOM_NUMBER` for 400 wave components every call
  (`snapwave_infragravity.f90:285`) and nothing seeds it; the engine's libgfortran seeds from the
  OS, so every run draws differently. The IG source is subtracted from the INCIDENT energy
  (`snapwave_solver.f90:664`, `snapwave_shinc2ig` reader default **1.0** — the solver comment
  saying 0 is stale), so it reaches breaking, the wave force and zs. Every bit-identical repeat
  on record (G1, G3_patched_rep = the F.4 cut) was IG OFF; every non-repeating one (pack test,
  det test, the 10-11 pair) IG ON. ⇒ §44's "v3 is deterministic" holds for IG off only, and
  §45's "IG does nothing to water levels" is wrong as mechanism (its measured null at the marks
  stands). Test: job 62645470 (queued).
  ✅ **User 10-15: IG STAYS ON in the premier; fix by SEEDING, not by switching IG off.** Engine
  variant `v2.3.3-winddir-igseed-1-gf11` = the premier's source (diff sha `02aa32005413ad5c`, same
  compiler / flags) + a fixed `random_seed(put=…)` before the 400 draws in `compute_herbers`,
  re-set on EVERY call (same sample at every point and call — independent of restarts, `dtwave`
  and boundary count). Source `/scratch/tpj8/sfincs-build/src-igseed-1` (`git diff 091f531`).
  A new binary is a new engine label: every arm after the switch is re-baselined, never Δ'd
  against a pre-seed run.

## ⭐ FINAL AUDIT → "the v4 premier is ready" (plan approved 10-15)

▶ **HANDOFF (10-15 evening).** In flight / next, in order:
1. **`igseed_sens`** (seeded-engine repeat + `rhoa` nudge, 6 h cut; pinning fixed): **62670930 RUNNING on
   Camden** + 62670893 PENDING on `main` (see Running). Their md5 guards (`igseed_sens3{,c}_expected.md5`)
   cover `scripts/engine_gate.py`, `logs/ig_det_2026-10-15/{igseed_sens3{,c}.slurm,his_pair.py}`, both engine
   binaries and the staged-source md5 — do not edit them while either is queued or running. Read
   `logs/ig_det_2026-10-15/igseed_sens3c_62670930.out` + `sens3c_62670930_r0/`.
1b. **62670904 `sbg_lakes`** (PENDING on `main`; resubmitted 10-16 with `--force` + `--requeue` via
   `logs/rebaseline_2026-10-15/submit_bed_lakes_resubmit.sh` — the first try, 62646886, was PREEMPTED 10-15
   19:52 after 1 h 24 with no requeue). What it builds: the premier bed rebuilt
   = the 10-06 recipe UNCHANGED (all 58 bed rasters md5-identical to `logs/refreeze_2026-10-06/rebuild_expected.md5`)
   + `lake_fix_v4` painted last → `experiments/v4_refreeze/_subgrid_refreeze_lakes`. 🔴 EXPECT_MD5 guards
   `data/data_catalog.yml`, `nj_sfincs/domain.py`, `nj_sfincs/premier.py`, `scripts/rebuild_subgrid.py` + the
   rasters — do NOT edit them until it STARTS (or re-write `logs/rebaseline_2026-10-15/rebuild_lakes_expected.md5`
   right after an edit). Read: its `subgrid_diff.json` is vs the TEMPLATE; the check that matters is
   `z_volmax` vs `_subgrid_refreeze` — changed ONLY on faces inside the 14 lakes, bit-identical elsewhere.
2. ✅ **Lake bed fix DECIDED + BUILT.** Scan `logs/lake_audit_2026-10-15/lake_scan.py` (+ per-pixel source):
   15 of 127 coastal lakes carry a > 300 m² patch > 1 m above the 10 ft lidar, and in ALL 15 it is the
   **USACE 2010 tier** (`usace_nj_2010_v3`) interpolated across the water (Wesley 2.2 m on a 0.61 m surface),
   plus outlet crossings and a filled Point Pleasant lagoon canal. User 10-15: **fix 14, keep Lake of the
   Lilies** (`decisions_2026-10-15.csv`; review page https://claude.ai/artifact/XVdVLkbrke5CTmspseyShu).
   Overlay `lake_fix_v4` (`scripts/build_lake_fix_overlay.py`): inside each outline, lidar where lidar <
   merged bed — 1.25 km² lowered, 0.53 Mm³ removed (per-lake `lake_fix_v4.json`). Paint it LAST in the
   premier bed rebuild (`rebuild_subgrid.py --overlay … lake_fix_v4`); check `z_volmax`.
3. **Breach arm** (sensitivity, not premier): Mantoloking = the user's polygons; Wreck Pond = a STATED channel
   beside the outfall + optional open-pipe culvert; Deal Lake none.
4. **Phase 3 code — done so far (staged, tests pass):**
   - ✅ inflow-wall split: `Domain.wall_sources_geodataset`; v4_refreeze discharge =
     `usgs_sandy_discharge_v4_refreeze` (the 12 moves), walls stay on run B's points (`model.wall_sources_key`).
     Reaches runs only through a RE-STAGED template; gate = sha `378014e154b4ff41` unchanged.
   - ✅ `cnb` code: `Experiment.cnb_effective` → `nj_sfincs/infiltration.py` writes `smax`/`seff`/`ks` binaries
     (active-point order) + `smaxfile`/`sefffile`/`ksfile`; label `cnb:e<eff>`; `tests/test_cnb.py`.
     ✅ **User OK'd 10-15:** the engine clamps `Se = min(Se, smax)` after any dry spell > 0.06/kr h
     (~2 h on sand), and 10-28's rain is patchy, so with `smax` = S_II an `effective` 1.5 collapses to 1.0
     before the main rain. Hence `smax = max(1, e)·S_II`, `seff = e·S_II`. `smax` = the premier's own CN map.
   - ✅ `ksat_v4_refreeze` built (SSURGO, 209,643 of 220,760 polygons carry a surface ksat; median 23 µm/s).
     Dry run on the premier's faces: 2.0 M of 3.97 M active faces infiltrate, `seff` (e 1.5) median 6.7 cm,
     `ks` median 262 mm/h, 7.4 % without ksat (no recovery); the dry spell before the clamp is 1.4 h at the
     median — the `smax` raise is load-bearing.
   - ✅ `data/wind_v4/naccs_blend_p_era5` built: wind bit-identical to `naccs_blend`, pressure differs only in
     the NACCS zone (p99 7.8 hPa, max 19.7). NOT yet in the registry: the new premier (seeded engine + `cnb`
     1.5 + ERA5 pressure + moved inflows + lake-fixed bed) is registered under a candidate name in the
     re-baseline pass, run, then renamed into place (the 10-11 recipe); brackets `cnb` 1.0 / 2.38 + Horton.
   - ✅ metrics read-back now also checks the label columns (`_ROUNDTRIP_LABELS`); ✅ islands log prints
     its BC count only when the mask has BC cells. ✅ HWM 6044: no v4 action — with the 12 moved inflows,
     0 of 193 v4 marks are within 500 m of a source (nearest 6208, 970 m); 6044 is a v3 mark.
   - Still to do: `lake_outlet_blocked` flag (plan: reuse `sea_level.connected_initial_zs` at the local sea
     peak), README, desk checks, env lock; the re-baseline job (Phase 4).

Plan: `~/.claude/plans/i-think-i-m-ready-warm-trinket.md`. User decisions 10-15: lakes = rule-based
flag + a documented-site breach SENSITIVITY arm (not in the premier); IG stays on, seeded; v3
reference re-run on the seeded engine; retired domains keep their registry entries (labelled), their
scripts go; scratch tiers A + B of `reports/cleanup/deletion_manifest_2026-10-15.md` approved.

- **Phase 0 ✅ (10-15):** seed patch + Deltares issue draft (`docs/upstream/snapwave_igseed*`; the
  bug is on upstream `main` too); NACCS originals copied to `~/nj_bight_durable/` (md5-verified);
  deletion manifest drafted (A + B = **271.9 G** freed by nlink). 🔴 USER: run
  `scripts/desktop_pull_backup.sh` — it gates every scratch deletion.
- **Phase 1 (repo part ✅ 10-15):** 8 frozen-domain scripts retired (`git rm`, citations say
  "retired 2026-10-15"); 4 v4 overlay builders relabelled provenance; 70 job stdout files filed into
  `logs/slurm/<yyyy-mm>/`; caches, 3 orphan log files, 4 tracked + 11 untracked obsolete report
  files, 2 data leftovers removed; suite 299 OK. KEPT (evidence, cited now in the index below):
  `pressure_2026-10-07`, `dune_lever_2026-09-23`, `weekly_2026-10-06` (the brief builder),
  `data_move_2026-10-05` (the swap script), `wind_x110_reads_2026-09-22`, `naccs_chs_2026-10-06`; both
  09-09 weeklies (plain + technical versions). KEPT scripts the plan listed: `plot_waterlevel_boundary`
  (`accept_domain.py` runs it), `stockdon_envelope` (run-up — the Deal Lake question), two downloaders
  (catalog provenance). ✅ **Scratch + home DONE 10-15** after the backup: 26 arms retired
  (`retire_arm.py`), the superseded domains' templates / subgrids / floodmaps and tiers A + B deleted →
  scratch 713 → 438 G, home 71 → 63 G; elevation_v4 swap finished; NACCS originals → symlink to home;
  `premier.py` labels v4 / v4_hot / v4_hot_plus RETIRED. 🔴 The backup never pulled
  `nj_bight_sfincs_data/` (data/'s symlink targets, 78 G) — fixed in `desktop_pull_backup.sh`; USER: re-run
  it once (big first pull). Still open: env lock file (`micromamba env export --explicit`).
- **Phase 2:** read 62645470 → A (clean) / B (noise band + cap test) / C (snan build); FINDINGS
  §44/§45 rewrite; CLAUDE.md §5 RNG trap.
- **Phase 3 (code, no solves):** `cnb` (SSURGO ksat → `create_cn_with_recovery`, `effective` 1.5,
  brackets 1.0 / 2.38; soil-RESET warning `cna`-only; toy resume test — soil on 10-28 was DRIER than
  AMC II, so expect MORE infiltration); inflow moves with a separate wall-points field (walls on the
  OLD points; `discharge_geodataset` is mask-defining — restaged sha must stay `378014e154b4ff41`);
  `--pressure era5` blend; `_subgrid_breach` (post-storm CZMIL / EAARL in hand-drawn polygons at
  Wreck Pond outlet, Deal Lake flume / Ocean Ave, Mantoloking / Bay Head; `logs/dune_lever_2026-09-23/`;
  USER draws them in the Breach Picker https://claude.ai/artifact/T6vURCojwcXQCo3voMcHdo, built by
  `logs/breach_picker_2026-10-15/build_breach_picker.py`; LOWER-ONLY overlay (min of bed and post-storm —
  lidar reads the pond / bay water surface), painted after the buildings (houses inside are removed; drawn
  around except at Mantoloking), ~25 m into the water on each side);
  `lake_outlet_blocked` scorer flag (headline with and without; never dropped); fixes (provenance
  NACCS label, meteo / infiltration / engine_seed columns, metrics round-trip, refuse an unset engine,
  HWM 6044 flag, islands log, `README.md`); desk checks (Atlantic City datum, paved channels).
  Pre-register in `logs/rebaseline_2026-10-xx/PREREG.md`.
- **Phase 4:** ONE 2-node job on the seeded engine: new premier + repeat + `bed-breach` + waves-off
  + `cnb` 1.0 / 2.38 + `bed-nobuildings` + a waves-off Horton (`hor`) arm — the standing-water
  drainage bracket; `cnb` stays the premier (user 10-15; FINDINGS §59) (node 1); v3 reference pair + a
  full-length `rhoa` 1.2501 copy of the new premier — the noise band THROUGH the peak (62645470 sees only
  the calm first 6 h) (node 2); validate; paired reads.
  Must end before maintenance 11-10 08:00.
- **Phase 5–6:** reads (new preset) → frozen premier (engine `…igseed-1…@2e4e9645`, user tags git),
  `docs/MODEL.md` model card (processes in / out with literature, patches, cost, reproducibility,
  data attribution, "how to start an experiment"), validation summary, research-group brief,
  docs refresh, backup, user commits.
- 🔴 **Wreck Pond is cut in two by the model's BED (10-15, user's 1st Ave hunch):** inside the NHD outline the
  merged bed carries a band 1.7–3.9 m (max 4.2) across the east end (−74.0285…−74.0317, ~40.1385) where the
  statewide 10 ft lidar reads water / < 1 m; within the pond, east end ↔ the rest connect only at 3.74 m
  (mid ↔ 6130 at 1.0 m). Premier zsmax: sea 2.80, east end 1.88, mid pond 0.38, 6130 0.86 (obs 2.74). The
  ocean ↔ pond sill is the beach at the outfall (−74.0261, 40.1391), 3.1–3.65 m. The post-storm surveys do
  NOT show the Sandy inlet (it healed within ~2 weeks; NJDEP / press) — so the breach arm needs a STATED
  channel at Wreck Pond, not a lidar overlay; the broken tide gate left the 7-ft outfall pipe open (a culvert
  candidate; nothing in nj_sfincs writes a drainage-structure file yet). Mantoloking: user's two polygons
  checked OK (`logs/breach_picker_2026-10-15/polygons_final_2026-10-15.csv`); Deal Lake: no breach polygon
  (overtopping — user). **Lake-crossing audit:** 15 of 127 coastal NHD lakes have > 300 m² where the model
  bed is > 1 m above the 10 ft lidar (Wesley — likely the deliberate 10-05 clamp; Deal, Spring Lake,
  Little Silver, Lake Louise, Takanassee, Twilight, … — decks / buildings?); per-lake read + user call next.
- **Status notebook fig. 2** ("rise above normal water", user 10-11) goes into the brief: normally-wet
  faces → peak − pre-storm high water; normally-dry → depth; baseline from the premier's early 6-h
  `zsmax` blocks (`logs/notebook_qc_2026-10-11/baseline_check.py` picks them).
- **The lakes (10-15):** Sandy breached the dune at Wreck Pond beside the outfall pipe and reopened a
  natural inlet (NJDEP Wreck Pond EA; closed in ~2 weeks; the expanded gated culvert is 2016 —
  present-day, not 2012); the ocean overwashed Ocean Ave into Deal Lake at the flume (Asbury Park Sun,
  2012). Model: lowest ocean–lake connection 3.10 m (Wreck Pond) / 3.62 m (Deal) vs a sea-side peak of
  2.81–3.01 m; post-storm lidar crest at the Wreck Pond outlet 1.65–2.49 m (was 4.89). Deal Lake's
  mark (3.14) stands ABOVE the modelled sea → needs run-up, which a fixed-bed SFINCS without a
  wavemaker lacks. Not done: the 12-creek refinement band (next mesh); the dtwave-600 swing leg.

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
| meteo, dunes, briefs, data moves | `pressure_2026-10-07/` (blend pressure < 1–4 cm), `wind_x110_reads_2026-09-22/`, `naccs_chs_2026-10-06/`, `dune_lever_2026-09-23/` (pre/post-Sandy crests — the breach arm), `weekly_2026-10-06/build_brief.py`, `data_move_2026-10-05/swap.sh` | in-folder | part 4 (e), §38 |
| v4 vs v3 like for like; IG seed | `premier_2026-10-11/`, `ig_det_2026-10-15/`, `reports/v4_first_results_2026-10-11/` | `v4_first_results.py --preset premier`, `engine_gate.py` | §44, part 4 |
| SLURM stdout | `logs/slurm/<yyyy-mm>/` (filed by month; batch scripts write to `logs/`) | — | — |

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

- Last cleanup: **2026-10-15 repo** (FINAL AUDIT Phase 1 above); scratch + home pass pending the
  backup — `reports/cleanup/deletion_manifest_2026-10-15.md`. Before: 2026-10-11 scratch (~374 G,
  `deletion_manifest_2026-10-11.md`). Report job stdout (`reports/**/jobs/*.out`) is gitignored.
- Kept on purpose, user's call to remove: `data/NACCS/_originals_pending_delete/` (3.2 G — the
  only byte-reproducible source of v3's NACCS boundary, FINDINGS part 3; durable copy since 10-15 in
  `~/nj_bight_durable/NACCS_originals_pending_delete/` with `MD5SUMS`);
  `data/gtsm/retired_v1_monmouth/`; the v1.5 / v3 notebooks and the weekly reports;
  `logs/audit_v4_hot_plus_2026-10-05/v4_vs_v3_deficit/shadow_hp_norain/` (705 MB rebuildable
  floodmap, on scratch; user 10-05: keep for now).
- `data/discharge_v4/usgs_sandy_discharge_v4_hot_plus.nc` will carry the 4 inflow moves after
  job 62279940 (only a future A+ restage reads it).
