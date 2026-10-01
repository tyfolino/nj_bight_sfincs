# STATUS — live campaign state

**Edit this file in place; keep it under ~300 lines.** It holds what is happening NOW: what is
running, what is next, what is open. When an item closes, its durable fact goes to
[FINDINGS.md](FINDINGS.md) (or CLAUDE.md §5 if it is a trap) and the item is deleted here.
Git has the history. The campaign log this file grew into until 2026-09-29 (6,767 lines) is
`git show d70dd1e:docs/STATUS.md`; FINDINGS cites it as "STATUS <date>".

Last updated: **2026-10-01** — wave cost tests read; wind-off SnapWave diverges; subgrid write-through fixed.

---

## Now

- **v3 is DONE** (user, 2026-09-24). Reference: `naccs-premier` on the repaired mask — HWM
  RMSE 0.329 / bias −0.143 (median, 50 m, n 94), MOTF CSI 0.706 / POD 0.880 / FAR 0.219.
- **v4 is FROZEN but PARKED.** Its inland-water fixes and its first waves-on run are on hold
  while the river policy and the wave treatment are re-decided (user, 2026-09-30). Only
  waves-off runs exist; the first look is in FINDINGS part 4.
- **The rethink (plan `~/.claude/plans/pasted-content-id-5f76-hey-claude-giggly-star.md`):**
  (1) repo cleanup — done, committed 2026-10-01; (2) literature review of
  where others end their rivers and how they treat wave setup; (3) SnapWave cost tests on
  v3; (4) a plain-language decision memo. No domain changes until the user picks from it.
- **Subgrid write-through, FIXED 2026-10-01 (staged, uncommitted).** `finalize()`'s
  `sf.write()` rewrote `sfincs_subgrid.nc` THROUGH the `swap_subgrid` hard link, i.e. into
  the premier's and 15 other runs' table, at every staging that borrowed
  `_subgrid_buildings`. No harm done: the 09-23 snapshot and today's file are bit-identical
  in every variable (only `_NCProperties` netCDF 4.10.0 → 4.10.1, 7 bytes; the stamp
  `8518110d` → `af1bd866` in `metrics.csv` is that and nothing else). Fix:
  `model.break_hardlinks()` before the write + `TestBreakHardlinks`; 238 tests OK.

## Next, in order

1. Read the cheap + wavemaker arm when it lands (Jobs; 5b pre-registration): `sacct`
   NodeList → `premier` audit `output WHOLE` → cost → transects vs the POST-repair baseline →
   paired marks vs `wave-wavemaker`. Only post-09-22-repair runs and numbers as references.
2. Unread from the wave tests: `engine_gate.py compare` on cuts 2–4 vs c1 (does crit 0.01
   freeze bay cells?). Then a user call: chase the wind-off divergence or strike that option;
   is test 8 (formula setup at the shoreline) still worth 2–3 days now the cheap config ties.
3. Decision memo: the four river policies (head of tide / gauge / +3 m rule / whole
   watersheds), each costed Sandy-only and +3 m; the wave table (cheap config, ± wavemaker);
   the literature summary folded in. The user decides; then the "do not exclude upriver
   communities" and +3 m rules are kept or rewritten explicitly.
4. FINDINGS §49's beach numbers are PRE-repair — flag or revise once arm 5b is read (user
   call). Fold today's durable results (cheap config, wind-off divergence, IG null) into
   FINDINGS when the wave half of the memo is settled.

## Jobs

**Cheap + wavemaker arm, submitted 2026-10-01 17:32:** solve **62104450**
(`wave-dt3600+wave-dtheta10+wave-wavemaker`, igk engine, emeraldrapids, 24 h) → validate
**62104451** (afterok, 160 G). Staged inputs checked against `wave-wavemaker`: only `dtwave`
and `snapwave_dtheta` differ; `sfincs.wvm` and SnapWave boundary files identical; the three
forcing NetCDFs differ only in bytes, every variable and attribute identical
(`forcing_diff.txt`). Read per the 5b pre-registration below: `sacct` NodeList first.

- Maintenance 10-13 08:00 → 10-14 23:59.

## Domains at a glance

| domain | status | fingerprint (faces / boundary edges / sha) | reference arm |
|---|---|---|---|
| `v1_monmouth` | frozen, port fixture | 547,408 | — |
| `v1_5_raritan` | frozen 2026-08-14 | 696,230 / 1,652 / `2a23667dd16e449c` | `naccs-premier` (carries the §50 edge drain, unmeasured) |
| `v2_barnegat` | archived, score-only | — | 5 rescored rows in `experiments/v2_barnegat/metrics.csv` (three fingerprints; compare within one) |
| `v3` | DONE 2026-09-24 | 3,412,470 / 4,108 / `1596ce1ecc71b374` | `naccs-premier`, engine `bin:v2.3.3-winddir-fix-1-gf11@673ee3bf` |
| `v4` | frozen 2026-09-28, parked | 4,881,654 / 4,388 / `23ea65f8b81ee1bd` | none yet (waves-off gate arms only) |

## v4 — live state

**Decisions in force** (the why is in FINDINGS part 4 and §53): ring = Sandy + 3 m target,
hand-edited CSV, audited; forced sea line replaces the isobath; far banks computed; river
cuts where the +3 m water ends, walled, gauge flow scaled by drainage area; outflow walled
within 500 m of every source and forced line; 16 px subgrid; score on the 3.125 m bed, NJ
land only; infiltration on (v4 only); buildings burned (NJDEP only).

**Known defects, not fixed** (all parked with the river decision): CUDEM ~0 m fill under
lakes / non-tidal rivers (§54a); the Schuylkill backing up through Philadelphia (box-mean
Manning, untested); creek channels missing at four Delaware-tributary gauges (§60g);
Union / Sunset Lake dam crests unchecked; no bed above the Trenton falls (DRBC request out
via the user's supervisor); the building cap (+4 m) is overtopped at +3 m SLR; 24.6 km² of
footprints skipped as ground < 0 m (Meadowlands / Newark — look before a waves-on run);
`passaic_charted` carve runs its MLLW tail past Dundee Dam.

**User decisions that were pending on 09-29 (inland water), now parked:** (1) the clamp
`bed = max(current bed, surface − depth)`; (2) exclude Christina at Newport and Big Timber
Creek (tidal); (3) Manor Lake — tide-connected or closed?; (4) keep the other 45
1.5–2.5 m-surface lakes. Tooling: `scripts/build_inland_water_v4.py`
(fetch / depths / inventory / review → `data/elevation_v4/inland_water/`).

**Unread:** why v4's waves-off run sits so far below v3's in the basins they share
(Barnegat Bay −0.84 vs −0.38, Raritan Bay −0.42 vs −0.20). Candidates: rain + infiltration,
the coarse shelf seaward of the drawn line, the drawn-line forcing, the CUDEM fills. A
paired read on common marks is the first step if v4 continues.

## Wave cost tests (Phase 3 of the plan) — cuts 1–4 and arms 5–7 RUN, read 10-01

Question: the cheapest wave treatment that keeps most of v3's waves-on gain
(ΔRMSE −0.064 m [−0.086, −0.042], FINDINGS §48). Levers ranked by the log's cost anatomy
(§20): direction bins and wind growth dominate; an iteration cap does not.

| # | arm | window | answers |
|---|---|---|---|
| 1 | control (premier inp) | 12 h cut, `engine_gate.py make` | baseline per-call cost |
| 2 | `snapwave_dtheta` 10° (360° kept) | 12 h cut | cost ratio; hm0 on surf strip, shelf, bays |
| 3 | `snapwave_crit` 0.01 | 12 h cut | do low-energy bay nodes freeze early? |
| 4 | wind growth off | 12 h cut | cost; how much coast hm0 survives |
| 5 | dtheta 10 + dtwave 3600 + IG off | full 73 h | the physics-preserving cheap config, scored |
| 6 | wind off | full | what wind growth is worth on the fixed engine |
| 7 | 5 + wind off | full | cheapest real solver, scored |
| 8 | shoreline setup through the wavemaker `wstfile`, no SnapWave | full | the parameterised floor (last; needs a builder) |

**📝 Pre-registration, arm 5b `wave-dt3600+wave-dtheta10+wave-wavemaker` (written 2026-10-01,
before submission; user asked).** The cheap config's two real changes (60 min, 10°) on
`wave-wavemaker` (IG on, same line, engine `v2.3.3-winddir-igk-fix-1-gf11`). Question: does
the cheap setup still deliver the shoreline IG, so the memo's wave recommendation covers a
model WITH beach IG? **Reads**, all paired against `wave-wavemaker` (same binary): (a) cost —
`snapwave_cost.py` vs `wave-wavemaker` and vs the cheap arm; (b) the beach —
`compare_usgs_transects.py wave-wavemaker <arm>` (restored today): Δ beach level on the
with-line transects, level − USGS TWL, overwash POD/FAR vs Z_Max; the Sea Bright storm-tide
peak (post-repair `wave-wavemaker` 3.35, premier 2.91, obs 3.47 m — 🔴 NOT §49's 3.30 / transect numbers, which are the PRE-09-22-repair `mask-drain-edge+` run; baseline re-read on the repaired runs: `logs/wave_cost_2026-10-01/transects_baseline_postrepair.txt`); (c) `paired_hwm_bootstrap.py <arm> wave-wavemaker
--by-basin`; (d) the NY-bay > 1 h motion as in `ig_seiche_check.py`. **What I expect, to
check, not a rule:** solver ~10–12 h (cheap 9.3 h + the IG balance); beach level within a
decimetre of `wave-wavemaker` at the median — the injected IG follows `hm0ig`, which is
updated hourly instead of half-hourly and computed on 36 bins, so a lower or smoother
shoreline signal is the risk; marks ~unchanged; NY-bay marks moved by a phase, either sign.
**Post-repair beach baseline (read 2026-10-01, before the arm ran):** `wave-wavemaker` vs
`naccs-premier`, all 2,348 transects: Δ beach level p50 **+0.63 m** (p10 0.00, p90 +1.95);
level − USGS TWL p50 −1.45 → −0.66 m (n 1,356); overwash vs Z_Max POD 0.115 → 0.165, FAR
0.348 → 0.239 (observed rate 0.49). The arm is read against THESE, not §49's pre-repair set.

Not tested: a 180° sector (the SnapWave literature thread and Deltares' own practice say
360° when wind is on).

**📝 Pre-registration, cuts 1–4 (written 2026-09-30, before submission).** Four 12 h cuts
of `experiments/v3/naccs-premier` (10-28 00:00 → 12:00, pre-storm; premier engine
`bin:v2.3.3-winddir-fix-1-gf11`, 64 threads, emeraldrapids) under
`/scratch/tpj8/engine_gate/wave_cost_2026-09-30/`, made by `engine_gate.py make --hours 12
[--set …]`. **Reads:** (a) cost — `snapwave_cost.py` on each log: median and total call
time, cap-hits, W, input time; each as a ratio to cut 1. (b) fields — `engine_gate.py
compare <cut> c1_control`: zs, zsmax and hm0 differences on cells finite in both; hm0 by
region (open-coast surf strip, shelf band, NJ back bays, NY bays) with
`snapwave_bay_census.py` where it applies. **What I expect, to be checked, not a rule:**
dtheta 10° ~2× cheaper per call with small hm0 changes on the open coast (Roelvink found
height "little sensitive" to direction resolution — never tested against setup); crit 0.01
cheaper, with the risk of low-energy bay cells freezing early (bay hm0 lower); wind off 3–5×
cheaper with bay hm0 → ~0 and open-coast hm0 close to the control. These are pre-storm
hours: they time cost and compare fields, they cannot score HWMs.

**Results (2026-10-01; `logs/wave_cost_2026-10-01/`).** All on the premier binary, all hal
(emeraldrapids), audit `output WHOLE`. Times are the solver's own `Total time` / `Time in
SnapWave` (`snapwave_cost.py`, overflowed calls imputed); "input" (~84 min) is fixed.

| run | window | solver total | SnapWave | median call | cap-hits |
|---|---|---|---|---|---|
| c1 control | 12 h | 5.85 h | 4.35 h | 477 s | 11/25 |
| c2 dtheta 10° | 12 h | 4.53 h | 3.03 h (0.70×) | 295 s | 10/25 |
| c3 crit 0.01 | 12 h | 4.11 h | 2.60 h (0.60×) | 392 s | 11/25 |
| c4 wind off | 12 h | 2.19 h | 0.69 h (0.16×) | 92 s | 4/25 |
| `naccs-premier` | 73 h | 25.5 h | 23.4 h | 453 s | 50/145 |
| `wave-dt3600+wave-dtheta10+wave-noig` | 73 h | **9.26 h** | 7.13 h | 236 s | 35/73 |
| `wave-nowind` | 73 h | 6.12 h | 3.99 h | 95 s | 17/145 |
| `…+wave-nowind` (all four) | 73 h | 2.87 h | 0.75 h | 36 s | 7/73 |

HWM median 50 m, n 94; paired ΔRMSE vs the premier and vs waves-off (`paired_hwm_bootstrap.py --by-basin`, B 200,000; `paired_<arm>__vs__<ref>.txt`):

| arm | RMSE | bias | MOTF CSI | ΔRMSE vs premier | ΔRMSE vs waves-off |
|---|---|---|---|---|---|
| `naccs-premier` | 0.329 | −0.143 | 0.706 | — | (−0.064, §48) |
| `wave-dt3600+wave-dtheta10+wave-noig` | **0.328** | −0.137 | 0.708 | −0.002 [−0.007, +0.003] | **−0.066 [−0.088, −0.044]** |
| `wave-nowind` ⚠️ | 0.355 | −0.117 | 0.711 | +0.026 [+0.010, +0.044] | −0.038 [−0.062, −0.016] |
| `…+wave-nowind` ⚠️ | 1.009 | +0.501 | 0.721 | +0.679 [+0.470, +0.879] | +0.615 [+0.402, +0.818] |
| `naccs-nowaves` (not ranked) | 0.393 | −0.246 | 0.697 | | — |

- **The physics-preserving cheap config costs 0.36× the premier's solve and keeps ALL of
  the waves-on gain** (−0.066 vs waves-off, the premier's own −0.064). Paired vs `naccs-premier` (median, 50 m, n 94): ΔRMSE −0.0018 m [−0.0072,
  +0.0027], P(A better) 0.77. By group: open coast −0.003 [−0.010, +0.003], NY bays −0.006
  [−0.019, +0.003], NJ back bays −0.005 [−0.011, −0.000]; the INLETS move: marks 1 cm lower,
  ΔRMSE +0.013 [+0.002, +0.021] (n 14). Blow-up faces 1,580 vs the premier's 1,511 (the
  known boundary-point artefact, FINDINGS "Closed").
- **The tie is not a seiche hiding lost open-coast setup** (user question; `ig_seiche_check.txt`).
  IG off is a null by construction (§45: no wavemaker → IG never reaches the flow), so the
  cheap config's changes are dtheta and dtwave. Where the premier's waves lift `zsmax` > 5 cm
  (982k faces, boundary blow-ups dropped) the cheap config keeps, median: Monmouth 0.97,
  Barnegat–LBI 0.99, AC–Cape May 1.12, NY bays 0.84 (p10 0.21 — small lifts, phase-sensitive).
  Sea Bright storm-tide setup (vs waves-off) 0.137 → 0.166 m day-mean; AC pier 0.059 →
  0.073. NY-bay > 1 h motion std is LOWER in the cheap run (Great Kills 0.076 → 0.057 m), so
  hourly forcing does not ring the bay harder. Outlier: Cape May Harbor peak +0.11 m.
  ⚠️ Open, and bigger than this question: waves ON ring the NY bays 3–5× more than waves-off
  (> 1 h std 0.045–0.076 vs 0.012–0.021 m), the same size as the NY-bay waves-on gain
  (Δ mean +0.063 m) — how much of that gain is `zsmax` sampling a wave-excited seiche is
  unmeasured (§40: envelope robust, phase not).
- 🔴 **Wind growth OFF makes SnapWave DIVERGE on this engine.** Faces whose hm0 is ever
  `inf` or > 20 m: premier 1,511, cheap config 1,580, `wave-nowind` **34,845**, all-four
  **83,273** (hm0max p99.9 73 m and 611 m). Brief sub-hourly spikes — the hourly zs matches
  the healthy arm except the `inf` hour — but `zsmax` catches them: 294 m at a face near
  Cape May, 22–48 m at Coney Island and Brigantine. The all-four arm's excess is northern
  (Sandy Hook Bay +1.63 m bias, Raritan +1.32, Shrewsbury +0.98; southern bays within cm).
  `wave-nowind`'s 0.355 is therefore NOT a clean "what wind growth is worth" number
  (Lower Bay SI shore +0.36 vs −0.18). Its paired read shows the split: vs the premier the
  typical mark moves ~1 cm DOWN in every group (Δ median −0.008 to −0.013 m), while the
  means are pulled up by a few blown-up marks (open coast Δ mean +0.069, NY bays +0.027).
  So the clean part of wind growth looks like ~1 cm at the marks; the +0.026 m ΔRMSE is
  mostly the divergence. The 12 h wind-off cut already showed it: SnapWave's
  error field `**********` and a 0.99989 oscillation with %ok = 100.
  (`blowup_where.txt`, `hm0_blowup_census.txt`). Mechanism not read.
- **Against the pre-registration:** dtheta 10° came in at 0.70× SnapWave time, not ~0.5×;
  wind off at 0.16×, cheaper than the 3–5× guessed — but it is unusable as built. crit
  0.01 is 0.60×; whether bay cells freeze early is still unread (`engine_gate.py compare`).
- Still to read: `engine_gate.py compare` on cuts 2–4 vs c1 (hm0 by region).

## Open questions (each with what would close it)

- **Wind-off SnapWave diverges (above).** Close: where the first `inf` appears (boundary
  points vs interior; Sandy Hook / Coney Island shoals) on c4, then decide whether "no wind
  growth" is a config worth repairing for the memo or simply struck.

- **Southern back-bay deficit (§57):** mechanism unknown. Close: pre-storm bay-minus-pier on
  a fixed-engine run whose inlet setup lifts the bays; and the calm-month datum check of the
  seven southern USGS stations against Atlantic City / Cape May NOAA.
- **NY east bay ~0.2 m low after the repair (§50);** `lower_bay_si_shore` (n 3) keeps moving the
  wrong way; the cross-Narrows tilt at `sss_narrows_bkln`. Close: per-mark and Narrows Q(t)
  reads on the repaired premier.
- **Great Kills sensor offset cause (§50).** Close: USGS STN deployment / survey records.
- **12 USGS gauges empty over the storm day (§60f).** Close: NWISWeb 2012 or the USGS Sandy data
  report.
- **Atlantic City peak +0.47 m high on v4 waves-off** (+0.49 on the 08-27 v3 arms). Close: the
  current v3 premier's AC `peak_err`, then NACCS at the nearest save point vs the gauge.
- **IG on the premier costs ~4 h with no wavemaker (§45).** Close: user decision (drop IG from
  the premier definition, a re-baseline; or keep it for `hm0ig` diagnostics).
- **Buildings never re-run on the apex band (§55).** Close: `bed-nobuildings` on the current
  premier, masked CSI.
- **No model M2 test** of the interior amplification (FINDINGS part 2). Close: modelled M2 at
  Port Reading / Keasbey / South Amboy / Great Kills vs the NOAA harcon table.
- **Flux cross-sections never read** (Narrows tidal prism, Rockaway throat). Close: read
  `crosssection_discharge` from a finished run.
- **Engine follow-ups:** the interior initial-guess remap and per-point boundary direction
  (§43/§44) never built; the dead-corner rule not reported upstream; PR #363 still open.
- **`accept_domain.py` FAILS on v3** (15 inflows on dry ground, 1 inactive; pre-existing).
- **v3 scorer does not flag HWM 6044** (49 m from the Absecon Creek source, §40).
- **`plots.plot_hwm_residual_panels` peaks at 165 G for six arms** (112 G for one): it keeps
  each arm's rasters. Close: release per arm; until then render at ≥ 200 G.
- **`metrics.csv` last-digit drift:** the `float_precision="round_trip"` guard left with the
  retired `stamp_metrics_epoch.py`; `run_experiments._write_outputs` read-merge-writes without
  it. Close: read → write → byte-compare once; add the flag if anything moves.
- **`_drop_detached_active_islands`** logs "N BC cells" before the BC exists (always 0).
- **Deliberately deferred by the user:** the dune-failure `bed-postsandy` lever; an ICW
  (`bed-icw`) survey tier as its own arm; raising `bay_fringe` past zmax 2.0.

## Evidence index

| topic | logs | scripts | FINDINGS |
|---|---|---|---|
| SnapWave cost anatomy | `wave_boundary_v4_2026-09-29/`, `snapwave_diag_scratch_2026-09-10/` | `snapwave_cost.py` | §20 |
| wind-direction bug + engine gates | `engine_gate_2026-09-11/`, `phase4_2026-09-13/`, `upstream_2026-09-14/` | `engine_gate.py`, `snapwave_direction_check.py` | §43, §44 |
| IG / wavemaker | `engine_gate_2026-09-17/`, `wavemaker_reads_2026-09-20/` | `build_wavemaker_line.py`, `make_snapwave_reproducer.py` | §45, §47, §49 |
| Sandy Hook shadow, D3/D4 | `phase4b_2026-09-17/` | `paired_hwm_bootstrap.py --bbox` | §48 |
| buildings | `phase8_2026-09-17/` | `burn_building_footprints.py`, `check_buildings_adequacy.py` | §55 |
| NY edge drain / mask repair | `great_kills_2026-09-21/`, `mask_repair_2026-09-22/`, `wind_x110_reads_2026-09-22/` | `restage_mask_repair.py`, `paired_hwm_bootstrap.py --by-basin` | §50 |
| dune failure (parked) | `dune_lever_2026-09-23/` | — | Closed list |
| v4 ring, line, rivers | `v4_design_2026-09-24` … `-28/`, `v4_freeze_2026-09-28/` | `audit_region_v4.py`, `audit_ocean_line_v4.py`, `build_river_table_v4.py`, `build_riverbeds_v4.py` | part 4, §53 |
| v4 SLR gate | `v4_gate_2026-09-28/`, `v4_gate_2026-09-29/` | `overflow_check.py` | part 4 |
| v4 inland water | `inland_water_v4_2026-09-29/` | `build_inland_water_v4.py` | §54 |
| wave boundary for v4 | `wave_boundary_v4_2026-09-29/` | `wave_boundary_ring.py`, `wave_shelf_reference.py`, `check_snapwave_domain.py` | §52 |
| SLURM stdout | `logs/slurm/<yyyy-mm>/` | — | — |

## Disk and cluster

- **Home** (`/cache/home`, GPFS): 100 G soft / 110 G hard; 90.6 G used on 2026-09-30. Ask
  `/usr/lpp/mmfs/bin/mmlsquota -u $USER --block-size auto cache` (it lags ~10 min after a
  hard-link dedupe).
- **Scratch** (`/scratch/tpj8`): 1 T soft / 2 T hard, 324 G used. 🔴 **Not backed up, and
  files not accessed for 90 days are deleted automatically** (OARC user guide). `experiments/`
  lives here; the durable copy is the desktop pull (`scripts/desktop_pull_backup.sh`) — re-run
  it whenever an arm is scored.
- **Attic:** `/scratch/tpj8/nj_bight_attic_2026-09-30/` holds what the cleanup moved out of the
  repo's untracked trees (manifest lists every file). It will purge itself after 90 days.
- **Maintenance:** every hal/halk node, 10-13 08:00 → 10-14 23:59, then 11-10 and 12-15 — a
  job whose limit overlaps it will not start.
- Claude Code may run on a LOGIN node (`amarel*`): heavy work goes through `srun` on an
  allocation (memory: shell gotchas).

## Housekeeping

- Last cleanup: 2026-09-30, `reports/cleanup/deletion_manifest_2026-09-30.md`.
- Kept on purpose, user's call to remove: `data/NACCS/_originals_pending_delete/` (3.2 G — the
  only byte-reproducible source of v3's NACCS boundary, FINDINGS part 3);
  `data/gtsm/retired_v1_monmouth/` (the record of the sealed v1 campaign); the v1.5 / v3
  notebooks and the weekly reports (kept item by item on 09-21).
