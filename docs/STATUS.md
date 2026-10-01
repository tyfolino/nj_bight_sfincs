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
  (1) repo cleanup — done today, staged for the user to commit; (2) literature review of
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

1. User reviews and commits the cleanup (`git status`; manifest
   `reports/cleanup/deletion_manifest_2026-09-30.md`).
2. Literature review — DONE 2026-09-30: `reports/literature_review_2026-10.md` (+ three
   appendices with the verbatim quotes). Still owed: the plain-language summary page for
   the user, folded into the decision memo.
3. Wave cost tests on v3 (section below) — submit, read with `scripts/snapwave_cost.py` and
   `scripts/paired_hwm_bootstrap.py --by-basin`.
4. Decision memo: four river policies (today's head of tide / the gauge / the +3 m rule /
   whole watersheds), each costed for a Sandy-only and a +3 m model; the wave-cost table.
   The user decides; then the memory rule "do not exclude upriver communities" and the +3 m
   rule are kept or rewritten explicitly.

## Jobs

**Paired reads, submitted 2026-10-01 16:16:** job **62099849** (`wcost_paired`, hal, 220 G)
runs `paired_hwm_bootstrap.py <arm> {naccs-premier,naccs-nowaves} --by-basin` for the three
full-window arms, sequentially → `logs/wave_cost_2026-10-01/paired_<arm>__vs__<ref>.txt`.
Fold the paired CIs into the results table below, then the decision memo.

- Maintenance 10-13 08:00 — the job above ends well before it.

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

HWM median 50 m, n 94 (unpaired headline; paired CIs pending, job 62099849):

| arm | RMSE | bias | MOTF CSI |
|---|---|---|---|
| `naccs-premier` | 0.329 | −0.143 | 0.706 |
| `wave-dt3600+wave-dtheta10+wave-noig` | **0.328** | −0.137 | 0.708 |
| `wave-nowind` ⚠️ | 0.355 | −0.117 | 0.711 |
| `…+wave-nowind` ⚠️ | 1.009 | +0.501 | 0.721 |
| `naccs-nowaves` (not ranked) | 0.393 | −0.246 | 0.697 |

- **The physics-preserving cheap config costs 0.36× the premier's solve and scores the
  same.** Paired vs `naccs-premier` (median, 50 m, n 94): ΔRMSE −0.0018 m [−0.0072,
  +0.0027], P(A better) 0.77. By group: open coast −0.003 [−0.010, +0.003], NY bays −0.006
  [−0.019, +0.003], NJ back bays −0.005 [−0.011, −0.000]; the INLETS move: marks 1 cm lower,
  ΔRMSE +0.013 [+0.002, +0.021] (n 14). Blow-up faces 1,580 vs the premier's 1,511 (the
  known boundary-point artefact, FINDINGS "Closed").
- 🔴 **Wind growth OFF makes SnapWave DIVERGE on this engine.** Faces whose hm0 is ever
  `inf` or > 20 m: premier 1,511, cheap config 1,580, `wave-nowind` **34,845**, all-four
  **83,273** (hm0max p99.9 73 m and 611 m). Brief sub-hourly spikes — the hourly zs matches
  the healthy arm except the `inf` hour — but `zsmax` catches them: 294 m at a face near
  Cape May, 22–48 m at Coney Island and Brigantine. The all-four arm's excess is northern
  (Sandy Hook Bay +1.63 m bias, Raritan +1.32, Shrewsbury +0.98; southern bays within cm).
  `wave-nowind`'s 0.355 is therefore NOT a clean "what wind growth is worth" number
  (Lower Bay SI shore +0.36 vs −0.18). The 12 h wind-off cut already showed it: SnapWave's
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
