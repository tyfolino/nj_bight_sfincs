# STATUS — live campaign state

**Edit this file in place; keep it under ~300 lines.** It holds what is happening NOW: what is
running, what is next, what is open. When an item closes, its durable fact goes to
[FINDINGS.md](FINDINGS.md) (or CLAUDE.md §5 if it is a trap) and the item is deleted here.
Git has the history. The campaign log this file grew into until 2026-09-29 (6,767 lines) is
`git show d70dd1e:docs/STATUS.md`; FINDINGS cites it as "STATUS <date>".

▶ **PICK UP (10-28): PHASE 4 SOLVES ALL DONE CLEAN; THE READ CONTINUES AS `p4_read2` 63177634.** All 13 v4
arms of 63094139 ended exit 0 (wave 2 at 10-27 16:26–17:24); preflight (`read/out/preflight.csv`): every arm `output
WHOLE`, seeded engine, hal (no halk), `segments: 0` — nothing to re-run. ✅ `p4-premier` vs `p4-premier-repeat`:
**BIT-IDENTICAL** (`read/out/repeat_p4.json`). 63094139 TIMED OUT at 05:09 validating `p4-nowaves` (the node-1 risk) →
no `metrics.csv` row / gallery for it. `p4_read` 63094140 ran preflight, repeat and residuals `p4` … `wk0`, then hit
its 6 h limit in `res_wk165`. **63177634 `p4_read2`** (`read/read_phase4_cont.slurm`, afterany 63094140, 16 h,
EXPECT_MD5 `read/expected_cont.md5`): validate `p4-nowaves`, then the read from the step 63094140 died in (`wk165`) to
the end (residuals, 17 zsmax pairs, report, null band, Sluice, PREREG marks). First numbers (median, 50 m, n 110, not
paired): `p4-premier` RMSE 0.408 / bias −0.099 / CSI 0.785 vs the 10-11 `naccs-premier` 0.436 / −0.110 / 0.780.
**Next:** read `p4_read2`'s output; re-publish the site for `p4-nowaves`. 🔴 **Hold the `nj_sfincs/experiments.py`
(rain-off description) and `provenance.py` (v4 forcing labels: the meteo label says `pres:naccs_blend` where the run
used ERA5 pressure inside the blend) fixes until `p4_read2` ends:** both are in its EXPECT_MD5, and its `p4-nowaves`
validation writes `provenance.py`'s labels into `metrics.csv` — edit after, then relabel all rows.

Last updated: **2026-10-28** — Phase 4 solves done + repeat bit-identical; read continues (63177634); site shows `p4-premier`.

---

## Now

- **v3 is DONE** (2026-09-24). Reference `naccs-premier` — HWM RMSE 0.329 / bias −0.143 (median, 50 m, n 94),
  MOTF CSI 0.706; re-run on the seeded engine in Phase 4 (`p4-ref` / `p4-ref-nowaves`).
- **v4 = `v4_refreeze`** (`378014e154b4ff41`). Premier `naccs-premier` (NACCS-blend wind, CN infiltration,
  unseeded engine): RMSE 0.436 / bias −0.110 (n 110), CSI 0.780; without the 5 noted marks 0.408 / −0.095 (n 105);
  10 marks outside ±0.5 m, inventoried in FINDINGS part 4 (h).
- **Heading for:** the Phase 4 re-baseline (below), before maintenance 11-10.

## Running (10-28)

- ⏳ **63177634 `p4_read2`** (`logs/rebaseline_2026-10-19/read/read_phase4_cont.slurm`, afterany `p4_read` 63094140,
  240 G, ≤ 16 h; EXPECT_MD5 `read/expected_cont.md5`, which also covers `run_experiments.py`, `nj_sfincs/provenance.py`,
  `nj_sfincs/experiments.py`): validate `p4-nowaves`, then the rest of the read (PICK UP). The zsmax pairs were never
  timed (attempts 1–2 skipped them). `res_nowv` ran before `p4-nowaves` had a row, so its self-check is blank; the marks
  file does not depend on the row. Attempt 1 (62827640 + its read 62831580): `attempt1_62827640/`, `failed_62827640/`.
  Attempt 2 (62963088 + read 62963089, 10-26): never solved; what its read wrote from older runs is filed in
  `attempt2_62963088/` — **not Phase 4 results**.
- ⚠️ **Sluice Creek gauge** reads an ASSUMED bed (pool painted at −0.24 m; nudged 10-22, FINDINGS part 4): observed
  lows reach −0.43 m, so its deepest troughs cannot be matched — read Phase 4's Sluice trough with that.
- ⚠️ **Keansburg pocket** (weir = NLD centreline, ADOPTED 10-24, FINDINGS §38): as drawn it is watertight
  and fills by rain only; 6133 / 6155 / 6156 are noted `leak` marks. The two weir ASSUMPTIONS (railroad stop logs in,
  navigation gate held) push the pocket toward its marks — those marks do not test the levees.
- 🔴 Side-by-side `engine_gate.py run` copies need `taskset` on disjoint cores (FINDINGS §44 (i)).

## ⭐ FINAL AUDIT → "the v4 premier is ready" (plan approved 10-15)

Plan: `~/.claude/plans/i-think-i-m-ready-warm-trinket.md`. Phases 0–3 ✅ (seed patch, cleanup, seeded-engine
test, code; details FINDINGS part 4 (h), §44, git log). Desktop backup re-run 10-22 (user).

- **Closed 10-20 (user; facts in FINDINGS part 4 (h)):** no lake pool start; no Wreck Pond culvert; Wreck Pond
  "band" = the 1st Ave bridge deck, already removed — no fix; Atlantic City +0.5 m = NACCS forcing; paved
  channels — federal channels clear (`audit_paved_channels.py` retired); `noaa_cape_may` /
  `usgs_tidal_cape_may_harbor` / `usgs_tidal_barnegat_light` nudged onto sea-connected faces (old v4_refreeze
  runs audit "OBS STALE", truthfully); NOAA gauges scored from 6-min on v3 + v4; `motf_km2_fa_rainonly` retired
  (MOTF false alarms: rain 79 / surge 27 / waves 22 of 128.5 km², twin-run split); creek beds = an ASSUMED bed at
  ≈ MLW (Salem River + Mannington Creek left out); HWM marks 6169 / 6202 (questioned) and 6121 / 6398 / 6188
  (run-up) kept, drawn hollow, `hwm_*_scored_excl_noted` beside the headline.
- **Phase 4 (attempt 3 63094139, `logs/rebaseline_2026-10-19/`):** ONE 2-node emeraldrapids job, seeded engine
  `…igseed-wmseed-1-gf11`, 40 h: stage 10 v4_refreeze arms, 4 × 16-thread slots per node, each node validates
  its own. Node 1 (`node1.txt`): `p4-premier`, its repeat, the two `rhoa` null copies | wave 2: `bed-breach-wreck0`
  (late-staged), `cnb` 1.0, `p4-nowaves`. Node 2: `+wave-nowavemaker`, `cnb` 2.38, `+rain-off`, `src-deal-overtop` |
  wave 2: `bed-nobuildings`, `bed-breach-wreck165` (late-staged). v3 `p4-ref` / `p4-ref-nowaves` = attempt 1's.
  PREREG `PREREG.md` (+ attempt-2 addendum). Budget: v4 waves-on ≈ 13 h at 16 threads (attempt 1's rain-off:
  12.7 h) → two waves ≈ 27 h + staging + scoring. 🔴 A preempted-and-RESUMED waves-on arm is a different run
  (§44 (j)): check every `restart_history.txt` before pairing; re-run a resumed premier / repeat / `rhoa` copy.
- **Phase 5–6:** ✅ site (10-28, user's ask): `publish_gallery.py` `SITE_REFERENCE` marks `p4-premier` as the v4 reference and `NEXT_PREMIER` now reads "New in the premier" — site-only; `premier.PREMIER_NAME` stays `naccs-premier` until the Phase 5 tag (then drop `SITE_REFERENCE`). Reads →
  frozen premier (user tags git), `docs/MODEL.md`, validation summary, research-group brief (incl. the
  status-notebook "rise above normal water" fig., `logs/notebook_qc_2026-10-11/baseline_check.py`), docs, backup.
- **DEP one-pager** (claude.ai doc "A Compound-Flood Model of the New Jersey Coast", 10-20; figures + scripts
  `logs/one_pager_2026-10-20/`): essentially done — no post-Phase-4 refresh planned (user 10-26). Its Fig. 2 and
  quoted HWM numbers are the 10-11 premier WITHOUT 5 marks (6155 Keansburg pocket; 6122, 6124, 6129, 6130 Monmouth
  lakes). The bona-fides sheet behind the NJDEP pitch (✅ pitch CLOSED 10-25: finished by the user + supervisor).
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

**Cohansey bed (10-22, `logs/cohansey_sources_2026-10-22/README.md`):** the model's LOWER river is several metres
too shallow — crowdsourced soundings (2024, raw) read 5.4–8.4 m median over 39.345–39.36 N where the model's faces sit
≈ 0.1–1.0 m below MLLW (the hierarchy kept CUDEM there: section mean 0.35–0.50 m below MLLW for 0.75–4.1 km); its
shallowest point to Greenwich (~0.5 m below MLLW) is above the ENC's charted controlling depth (1.5 m, 1988–2014). No
sill (Greenwich face reached at −1.4 m). Above 39.36 N: no soundings anywhere — only the 1906 USACE report ("30 and 40
feet", one ~7 ft bar) and the ENC floors (1.5 → 1.2 → 0.3 m). Scans: 1905 USACE sheets (RUcore 56574 mouth, 56588
Bridgeton, MLW). Greenwich tide 0.62 of observed. Candidate fix (after Phase 4, user's call): D00081 + tide-reduced CSB
as tier 3 in the lower reach, ENC controlling depths as a thalweg floor, a deeper section from the 1905/06 material.
✅ USER AGREED the fix 10-22. ▶ **10-23 BUILT as `riverbeds_hierarchy_v4c`** (`logs/cohansey_fix_2026-10-23/README.md`): the hierarchy gained opt-in survey checks (CSB + D00081 as tier 3; CUDEM not a bed above the ENC controlling depth or > 1 m above the soundings) and `--version` (v4 FROZEN). Lower 3.4 km section mean 0.4 → 2.5–4.9 m below MLLW; Greenwich 1.2 → ~3.0 (still the slope GUESS above 3.6 km). Job **62908942** builds `_subgrid_refreeze_lakes_min_creeks_cohansey` + the Greenwich tide test (waves-off, base = Phase 4 bed); its EXPECT_MD5 covers `data/data_catalog.yml` — don't edit the catalog until it starts. Tide-reduced soundings (`csb_tide_reduce.py`, lower bounds, no
draft): from 39.349 N to 39.361 N the river is ≥ 4.5–8.4 m below MLLW where the model's deepest face is 0.8–1.0 m.
The sfincs-nj-agri session's test (10-20, its 100 m model, calm May 2023 week, beds only): Big Timber on NOS H09886
took Westville 0.47 → 0.97 of the expected range; the Cohansey at 7 ft below MLLW mouth → Fairton took Greenwich
0.55 → 0.72.

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
- **Capped calls inject river pulses on v4 (§44 (h)).** ✅ Counted 10-27 (Phase 4 wave 1, `snapwave_niter` 200
  sweeps = 50 logged iterations): premier 26 / 73 calls capped (repeat: the same 26), nulls 20 / 25, other
  waves-on arms 22–34; 10-30 00:00 capped in every arm (%ok 88–90, the worst call), 01:00–02:00 in nearly all.
  ✅ Delaware gauges clean on the Phase 4 premier vs `p4-nowaves` (10-27, `logs/capped_calls_2026-10-27/`).
  Close: whether any face's `zsmax` is set inside a capped hour (map read; fold into the Phase 4 reads).
- **Delaware low-water deficit (10-27 triage, p4-premier `his`, rough high/low picker):** pre-storm the model sits
  0.2–0.4 m low at highs AND lows from Lewes to Newbold (a level deficit, lows a little worse); the storm low
  (10-29 22:00 → 10-30 01:00) misses by −0.36 at Lewes, −0.6…−0.7 Ship John → Philadelphia, −0.7…−1.0 at Newbold;
  after the storm the model runs 0.1–0.2 m high. ✅ **At the mouth it is the NACCS forcing** (10-27,
  `logs/delaware_lowwater_2026-10-27/`; NACCS save points ON the Lewes / Cape May gauges + VDatum, vs CO-OPS 6-min
  NAVD88): calm 10-12 → 10-25 NACCS − obs mean +0.07 / +0.04, range ratio 0.99 / 0.95, but its 12.4 h-mean error
  wanders ±0.2–0.3 m with the weather; from 10-27 it runs −0.15…−0.25 (−0.26 / −0.33 at the 10-29 evening low), peaks
  −0.18 / −0.22, then +0.1 after; model − obs tracks NACCS − obs at both. Still open: the growth upriver
  (−0.3 at the mouth → −0.6…−1.0 Ship John → Newbold at the storm low, part of it a late low at Newbold, +100 min).
  Close: Phase 4's per-gauge tide + residual reads; mouth-deficit-corrected (`BRACKET+`) test only if the user wants it.
- **Southern back-bay deficit (§57):** the Great Egg inlet sill (§54 h) a candidate share. Close: the
  v3 re-run's Great Egg / Ocean City pre-storm bay-minus-pier; calm-month datum check of the seven
  southern USGS stations.
- **NY east bay ~0.2 m low after the repair (§50);** `lower_bay_si_shore` (n 3) moves the wrong way;
  the cross-Narrows tilt at `sss_narrows_bkln`. Close: per-mark and Narrows Q(t).
- ▶ **Great Kills sensor offset — CAUSE FOUND 10-23** (`logs/great_kills_offset_2026-10-23/README.md`): a co-located USGS rapid-deployment gage (NWIS 403236074073983, same dock) reads the sensor **+0.339 m high** (sd 0.016, n 21; RDG vs Sandy Hook −0.04); wet/dry onsets put the orifice at 1.56–1.60 m, not the assigned 1.902 → the sensor ELEVATION is wrong (which survey step: untestable). Baro, density, GEOID, mid-storm movement ruled out. Corrected peak ≈ 3.65–3.69 m; NACCS's 0.35–0.39 m Great Kills deficit → ~0–0.05. USGS never re-published (file still "provisional 12/18/2012"). ✅ APPLIED 10-23 (user): `ObsGauge.obs_offset_m` −0.34, FINDINGS §50; Phase 4 + read `expected.md5` re-written deliberately (backups `.bak_2026-10-23`).
- ▶ **12 USGS gauges empty over the storm day — ANSWERED 10-23** (`logs/usgs_gap_2026-10-23/README.md`): the hole (2012-10-29 EDT, one local day) is in USGS's published archive (legacy NWIS IV = OGC, one series per site, no revisions) — not our fetch. Published crests exist for all 12 + 3 more that only LOOK like dying records (Shark R., Sea Bright, Absecon Channel): OFR 2013-1043 Table 4 (NAVD88, GMT) = SIR 2016-5085 = NWIS peak file within 0.05 ft → `peaks_recovered.csv`. Hydrographs through the gap digitised from SIR 2016-5085 Fig. 18 (vector; RMSE 1–4 cm on overlap, EDT clock) for Tuckerton, Absecon Ck, Keansburg, Manasquan (+ Sea Bright) — possibly USGS-reconstructed. 🔴 The 10-29 daily "tidal high" is the first post-gap sample at 6 gauges: never a peak. OFR's Waretown row (7.3 ft) contradicts NWIS / SIR (5.5): wrong. (The five gauges the agent thought lacked `record_ends` carry it via `_v4_gauge(..., ends=)`.) ✅ APPLIED 10-23 (user): `ObsGauge.published_peak` → `peak_err_pub_*` (v3 + v4 family), the report's published-crest table, FINDINGS §60 (f). First hint, unscored: Keansburg published 4.20 vs the 10-11 premier ~3.76.
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
  the low end (slowest component 462 s instead of 2000 s at the defaults; bulk period unchanged at Tp_ig ≤ 100 s).
  Draft question `docs/upstream/wavemaker_freq_offset_issue.md` (10-26) — filing = user.
- **Engine follow-ups:** the interior initial-guess remap and per-point boundary direction (§43/§44)
  never built; the dead-corner rule not reported upstream (re-check on `main` first: #300 / #351 / #382 reworked
  that code). Wind direction FIXED upstream (#371, merged 10-08). Seed + wavemaker-resume issue drafted 10-26
  (`docs/upstream/sfincs_reproducibility_issue.md` + `…_main.patch`, tested on `main` f3647fc) — filing = user.
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

## Future: make the model faster (user 10-27 — after we are happy with the v4 simulations)

SnapWave is ~97 % of a waves-on run (§20) and its sweep is SERIAL: a 64-thread solve averages ~6 busy cores. No OpenMP
around the sweep loop on `main` (checked 10-26). Don't write our own SnapWave (months to validate).

- **(b) Parallel SnapWave, bit-identical → no new engine gate, no re-baseline.** In this order:
  1. *Warm-up:* OpenMP on the dependency-free per-node loops (energy → wave height, the convergence check); a few
     lines, maybe 1.2–1.3×.
  2. *The big one:* level-scheduled ("wavefront") sweep — build each sweep's upwind dependency graph once per call,
     group nodes into levels, run each level in parallel; every node reads the same values as in serial order.
     Sweep ≈ 70–80 % of a call (§20 fit) → estimated 3–5× per run (13 h premier → a few h). Estimate, not measured.
     A few hundred lines of Fortran.
  3. *Memory order:* renumber nodes so sweep order = memory order (no arithmetic change; gain unknown).
  4. *Per-call setup:* each call re-sorts all nodes four times (part of the fixed ~42 s/call) — cache it.
  Check each against the toy and a 6 h v4 cut (bit-for-bit). A natural upstream contribution, and the same level
  structure is what a GPU port of SnapWave would need. *Number-changing* speed-ups (`-march=native`, fixing the Sandy
  Hook limit cycle — capped calls cost ~2×, §44 (g)) need a new engine label + re-baseline: separate decision.
- **(a) GPU build, timed on a waves-off arm.** SFINCS's flow solver is ported (OpenACC, maintained on `main`);
  SnapWave is NOT (no directives) — it stays on the CPU, so waves-on runs gain ~nothing until (b) or an upstream port.
  Waves-off runs (rain / river / SLR sweeps, forecast-style) could drop from hours to minutes. Needs NVIDIA's
  `nvfortran` (HPC SDK, self-installed — Amarel has only `pgi/19.4`) or a Deltares GPU container if one exists; GPU
  arithmetic is not bit-identical → engine-gate it. First: ask Deltares (reproducibility thread) whether SnapWave on
  GPU is planned; then build + time one waves-off v4 arm vs the CPU build.

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

- **Home** (`/cache/home`, GPFS): 100 G soft / 110 G hard; **89.2 G on 2026-10-28**. Ask
  `/usr/lpp/mmfs/bin/mmlsquota -u $USER --block-size auto cache` (lags ~10 min).
- **Scratch** (`/scratch/tpj8`): 1 T soft / 2 T hard, **704 G on 2026-10-22** (after the four pre-creek beds were deleted; the 39 G pre-inflows template is
  gone too). 🔴 **Not backed up; files not accessed for 90 days are deleted.** `experiments/`
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
