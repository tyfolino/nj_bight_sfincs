# STATUS — live campaign state

**Edit this file in place; keep it under ~300 lines.** It holds what is happening NOW: what is
running, what is next, what is open. When an item closes, its durable fact goes to
[FINDINGS.md](FINDINGS.md) (or CLAUDE.md §5 if it is a trap) and the item is deleted here.
Git has the history. The campaign log this file grew into until 2026-09-29 (6,767 lines) is
`git show d70dd1e:docs/STATUS.md`; FINDINGS cites it as "STATUS <date>".

▶ **PICK UP (11-02): MODEL 1.0.0 = `p4-premier` on `v4_refreeze_swz` (`90cc7468614a5814`, tagged `v1.0.0`).** Read in FINDINGS part 4 (j) (`logs/swz_read_2026-11-01/`): buildings stay in flow and waves, the Arthur Kill sill does nothing, breach and Deal stay sensitivities. FIAT closed (user 11-01; the 10-30 maps in `share/` stand). **New runs use `SFINCS_BIN=$(cat hpc/production_engine.txt)`** (`…swomp-2-gf11@dd78d82a`, user 11-02; its first run is also its first through `hpc/sfincs_run.slurm` and its first possible resume). **Next (11-03; the full ordered list is the to-do panel, `.claude/todo.local.json`):** (1) ✋ user pushes master (9cc811c) and the v2.3.3 engine branch to the fork. (2) ✋ user sends the MHHW + 2 / + 4 ft package (`share/mhhw_plus2ft_4ft_README.md`, both versions) to the climate hazard team. (3) **Disk before anything stages:** scratch 991 G of the 1 T soft quota (2 T hard; over soft starts a grace clock) — survey running; free space before the Mullica submit, and ~200 G before 2.0 (or ask Amarel). (4) **v1.1 worklist** (each a paired waves-off test against `p4-nowaves`, then combine, paired vs 1.0.0, tag): Mullica bed from charts + the listed sills (`river_drain_2026-11-02/`; agent preparing a ONE-job rebuild + test, not submitted); remove elevated decks; Overpeck dam bracket (agent preparing); Arthur Kill subgrid-table repair test (`ak_noise_2026-11-02/`, below); South Ironbound's reported streets (agent); **tidal reach** in the Delaware above Reedy Pt, the Christina, the Cohansey and Great Bay (`tide_maps_2026-11-03/`, below). Decks, table repair and tidal reach reuse the Mullica rebuild script. **Mullica test SUBMITTED 11-03: 63483048** (`riverbeds_hierarchy_v4d`: lower Mullica + Tuckahoe, Toms, Cedar Ck, Westecunk, Raccoon, Mantua; ~13 h; its EXPECT_MD5 covers `nj_sfincs/experiments.py` + `data/data_catalog.yml` — no edits there until it starts). **Overpeck bracket agreed 11-03** (`logs/ironbound_overpeck_2026-11-03/`: open / high 3.28 m, plain arms, a `weir_from` field, pool start unchanged; register + submit once 63483048 has started). **13 marks the v4 file missed** (Newark Bay / Hackensack / Overpeck; pulled 09-24 on a box that stopped at 40.617 N) join the 1.x mark file in v1.1, 1.0.0 scored both ways (110 / 119) (`logs/v2_validation_2026-11-03/`). **South Street** (South Ironbound) is a located miss: 58% "path below the water, water never got there", 37% behind a sill; the level falls 3.66 → 2.4–2.55 m on the long route round. **Friction is double-counted in 1.0.0 (by construction, 11-03):** NLCD developed n 0.10 / 0.13 (23 / 24) were tuned 2026-05-25 on a model WITHOUT buildings to stand in for them; §55 (09-03) then burned the buildings in and kept those n. **The fix GOES IN v1.1 (user 11-03); the test sets the value and shows the side effects:** NLCD 22–24 → 0.04, NJ ONLY (burned footprints are NJ-only; PA / DE / Staten Island keep NLCD n) (`data/roughness_v4/manning_developed_v4.tif`, `logs/developed_manning_2026-11-03/`), waves-off vs `p4-nowaves`; job script being prepared, submit after 63483048 starts. Then re-run the 32-day tidal twin on the v1.1 bed (the real hydrodynamic product) and re-read power exposure. (5) **Phase 1 repo consolidation** (plan `~/.claude/plans/alright-claude-i-m-actually-humble-iverson.md`): **safe half DONE 11-03**: `build_ehydro_south.py` ported (the only archive-only builder in 1.0.0's recipe; the other five build v1–v3 products), ARCHIVE.md / README / `hpc/amarel_bootstrap.md` name both archives, agri session told (it reads `~/nj_bight_sfincs/data`, which keeps its names). ✋ User marks `nj_coast_sfincs` + `nj_sandy_sfincs` archived on GitHub (nothing unpushed, checked). **Waits for an empty queue (latest: the 11-10/11 maintenance):** `NJ_TOOLCHAIN` (55 lines in 35 files; `hpc/sfincs_run.slurm` is under 63483048's EXPECT_MD5) and the 13 data links into the archive. Catalog line ~166 `ehydro_south` still says "(archive; not ported)": fix with the friction-test catalog edit, after 63483048 starts. (6) **2.0 = Hudson + Upper Bay, decisions taken 11-03** (`hudson_design_2026-11-02/README.md` "Decisions"): cuts Hudson 40.860 + Hell Gate; ONE 2.0.0 with 2012 and 2026 (estimated) beds (version rule, CLAUDE.md §6); NY side coarse, no NY buildings; 2026 bed as built, Resist wall a later 2.x scenario; ~5 GB download approved (after the disk survey); Hell Gate as drawn, its ~0.2 m question a 2.1 note. Pre-freeze checks DONE, decisions taken (`logs/v2_prefreeze_2026-11-03/`, `logs/v2_validation_2026-11-03/`, "Decisions" in each): no deck dams; carve Newtown / Wallabout / Gowanus / Bushwick from surveys in both beds; BlueTopo contributor 0 out; Astoria vertex inland (141 m the 1/9" walk found); Hudson forced line +36 m; candidate mark file 275 marks (162 headline), no new MOTF boxes. NACCS pull CLOSED 284 of 312 in `data/NACCS/hudson_pull_2026-11-02/` (keep it out of `data/NACCS/`: the builder reads every zip there). (7) Later: Sandy's forcing on the modern bed for the end read on today's assets. (8) **Erosion / sediment transport (likely 3.0; user 11-03):** feasibility memo DONE (`logs/morpho_feasibility_2026-11-03/README.md`; plan Phase 8): empirical post-processor (Sallenger + Stockdon on the run's own zsm / hm0 / tp) → gate / scenario-bed tests → one-way 2D XBeach boxes as 3.0; two-way blocked by the subgrid tables; 7 decisions open.

**Phase 4 still to read:** capped-hour `zsmax` (open question below).

Last updated: **2026-11-03** — still-water maps done and read for power exposure; Arthur Kill noise is not dt / advection; the tidal twin's high tide checked against VDatum (10–45 cm low up the rivers); both MHHW map versions done and packaged in `share/`; 2.0 decisions taken. Scratch 762 G of the 1 T soft limit, home 85 of 100 GiB.

---

## Now

- **v3 is DONE** (2026-09-24). Reference `naccs-premier` — HWM RMSE 0.329 / bias −0.143 (median, 50 m, n 94),
  MOTF CSI 0.706; re-run on the seeded engine in Phase 4 (`p4-ref` / `p4-ref-nowaves`).
- **Model 1.0.0: `v4_refreeze_swz` / `p4-premier`** (`90cc7468614a5814`, job 63181564): RMSE 0.439 / bias −0.128 (median, 50 m, n 110), CSI 0.784; without the 6 noted marks 0.354 / −0.093 (n 104). `docs/MODEL.md`.

## Running (11-03)

- ⏳ **63483048 Mullica bed test** (`logs/mullica_bed_2026-11-03/`), pending at last look; its EXPECT_MD5 covers `nj_sfincs/experiments.py` + `data/data_catalog.yml`.

## MHHW + 2 ft / + 4 ft for the climate hazard team: two versions (user 10-29)

- **Still water, no solve: DONE** (63440060, `logs/still_maps_2026-11-02/`): `floodmaps/bed-modern+still-{2ft,4ft}_depth.tif`. Sloped VDatum MHHW + s, sea-connected through the subgrid sills and weirs (405 of 407 weir points closed). Normally-dry land 652 / 963 km², depth p50 0.46 / 0.93 m. The job's "figure FAILED" was the wrapper's `grep -v Warning` exiting 1 on a step that prints nothing; `qc_views.png` is fine.
- **Hydrodynamic (tidal twin): DONE** (63482546, `logs/tide_maps_2026-11-03/`): `floodmaps/bed-modern+tide-{2ft,4ft}_{mhh,max}_depth.tif`. Normally-dry land >= 0.15 m, + 2 / + 4 ft: still 582 / 890 km², tidal mean higher-high 370 / 748, tidal month max 519 / 846. Barnegat agrees with still (tidal slightly wetter); the gap is largest up the Delaware River (+ 2 ft 18 vs 3 km²) and around Newark Bay (12 vs 4) (`compare_still.csv` / `.png`). **Packaged 11-03 in `share/mhhw_plus{2,4}ft_*` + `share/mhhw_plus2ft_4ft_README.md`** (both versions, VDatum table, region table): ✋ user sends to the climate hazard team. ⚠️ **Its high tide against VDatum MHHW** (`tide_maps_2026-11-03/README.md`): open coast within ~3 cm; Newark Bay −0.11, Philadelphia −0.20, Newbold −0.29, Great Bay −0.35, Greenwich (Cohansey) −0.34, Christina at Newport −0.45 m (+2 ft run). So on these beds the hydrodynamic maps UNDER-flood the river shores and those back bays. Agreed 11-03: send both, preliminary, with the table; fix tidal reach in v1.1; re-run the twin on the v1.1 bed.

## Power exposure: first pass (11-02, `logs/power_exposure_2026-11-02/README.md`)

- Sandy, Model 1.0.0, preliminary: NJ 59 wet / 123 dry / 71 not computed. **Still water (read 11-03):** NJ wet + 2 ft 17 (none on >= 25% of its land), + 4 ft 30 (6 on >= 50%: small sites; the big plants wet at the edge, their burned buildings read dry — read `band_*`). ⚠️ The asset files are believed to be today's (PSE&G moved assets after Sandy; user), so this is today's layout against a Sandy-sized flood, not what flooded in 2012. **Sandy is the test case (user 11-02): no 2012 asset list exists or is needed; the end read is today's assets on the modern bed ("if Sandy happened today"), which needs Sandy's forcing on the modern bed.** Leonia Substation is wet at + 2 ft (one edge pixel) but dry in Sandy: re-read after the Overpeck test.

## Tidal twin: done, with open questions (11-02, `logs/tide_repair_2026-11-02/README.md`)

- **Whole:** `bed-modern+tide-2ft`, `-4ft`, 32 d, 256 blocks, all readable, `tide_stats.nc` in each run dir. Preempted 11-01, resumed and finished; the kill lost `zsmax` blocks 210–223 (one chunk), re-solved from the 11-07 06:00 restart file and stitched (restart_history.txt). Patch vs original: p99 of `zs` under 0.6 mm.
- ⚠️ **Noisy water on cut banks, IN 1.0.0 TOO (`logs/ak_noise_2026-11-02/README.md`):** faces holding a sliver of deep channel. **Not the time step or advection (63441387, read 11-03):** alpha 0.25 and advlim 0.1 leave it on the same faces (overlap >= 0.93), advection off doubles the flagged faces (468 → 957); only a bed change moves which faces are flagged, so the subgrid tables are the suspect (not proven; one draw each, no replicate). Next: a table-repair test (bank-slope overlay) + a `modern` replicate + `wiggle_suppression` off, one job. Peak water at the patch unaffected (42 persistently wet faces: p99 +0.002 m); tide statistics are biased, mask flagged faces. Original note: in a ~1 m tide, single faces near −74.245, 40.55 read 0.62 vs −1.41 m between the patch and the original. At least 260 faces (+2 ft) / 51 (+4 ft) parted by > 10 cm. A typical noisy face is within 2 cm of its neighbours in mean higher-high; the worst is ~0.7 m high.
- ⚠️ **Monthly peaks that are not tide:** 2.304 m at −73.9975, 40.5884 (+2 ft; a noisy cut-bank face, 4807804) and 3.080 m at −75.0973, 39.8538 (+4 ft; face 3622412, still unexplained), mean higher-high 2.246 and 2.604 there; Sandy Hook's mean higher-high is 1.31 / 1.92.
- Compared with VDatum MHHW 11-03: see the two-versions section above. The known deficiencies in the bullet on the first 1.x simulations below still stand.

- **Phase 4 read notes:** attempts 1–2 are filed under `logs/rebaseline_2026-10-19/attempt*/` — **not Phase 4 results**.
- ⚠️ **Sluice Creek gauge** reads an ASSUMED bed (pool painted at −0.24 m; nudged 10-22, FINDINGS part 4): observed
  lows reach −0.43 m, so its deepest troughs cannot be matched — read Phase 4's Sluice trough with that.
- ⚠️ **Keansburg pocket** (weir = NLD centreline, ADOPTED 10-24, FINDINGS §38): as drawn it is watertight
  and fills by rain only; 6133 / 6155 / 6156 are noted `leak` marks. The two weir ASSUMPTIONS (railroad stop logs in,
  navigation gate held) push the pocket toward its marks — those marks do not test the levees.
- 🔴 Side-by-side `engine_gate.py run` copies need `taskset` on disjoint cores (FINDINGS §44 (i)).

## ⭐ FINAL AUDIT → "the v4 premier is ready" (plan approved 10-15)

Plan: `~/.claude/plans/i-think-i-m-ready-warm-trinket.md`. Phases 0–3 ✅ (seed patch, cleanup, seeded-engine
test, code; details FINDINGS part 4 (h), §44, git log). Desktop backup re-run 11-02 (user), the first since the 10-05 move to include the scratch data behind `data/`'s symlinks; the script now pulls it.

- **Closed 10-20 (user; facts in FINDINGS part 4 (h)):** no lake pool start; no Wreck Pond culvert; Wreck Pond
  "band" = the 1st Ave bridge deck, already removed — no fix; Atlantic City +0.5 m = NACCS forcing; paved
  channels — federal channels clear (`audit_paved_channels.py` retired); `noaa_cape_may` /
  `usgs_tidal_cape_may_harbor` / `usgs_tidal_barnegat_light` nudged onto sea-connected faces (old v4_refreeze
  runs audit "OBS STALE", truthfully); NOAA gauges scored from 6-min on v3 + v4; `motf_km2_fa_rainonly` retired
  (MOTF false alarms: rain 79 / surge 27 / waves 22 of 128.5 km², twin-run split); creek beds = an ASSUMED bed at
  ≈ MLW (Salem River + Mannington Creek left out); HWM marks 6169 / 6202 (questioned) and 6121 / 6398 / 6188
  (run-up) kept, drawn hollow, `hwm_*_scored_excl_noted` beside the headline.
- **Phase 4 ✅ (63094139, 10-28; `logs/rebaseline_2026-10-19/`, PREREG `PREREG.md`):** 13 v4 arms + the v3 seeded pair,
  read in FINDINGS part 4 (i). Its lake arms re-run on swz in 63231557.
- **First 1.x simulations (staged 11-01, `logs/modern_bed_2026-11-01/README.md`; tidal twin done; still water mapped without a solve, user 11-02, so the staged `still-*` arms are inputs only and are not to be solved; user 10-28, re-confirmed 10-29): calm still water at MHHW + 2 ft / + 4 ft on the MODERN
  bed, waves off**, for the collaborator's comparison (their own 2 ft / 4 ft maps disagree — negatives on every coast;
  they suspect their data). Plan + data: `logs/modern_bed_2026-10-28/README.md` (download ✅; next: bed-recipe code,
  `_subgrid_modern2026` build ~7 h, buildings + fixes re-checked). Still water = the SLOPED VDatum MHHW surface + s
  (MHHW ~0.8 m at the mouth → ~1.5 m at Trenton), sea-connected via `sea_level.py` — not one flat boundary level.
  **AND a tidal twin (user 10-29: both):** same bed, waves/wind/rain off, astronomical tide + 0.61 / 1.22 m at the
  boundary over ≥ one spring–neap cycle (a lunar month is better); report the model's mean higher-high + the max.
  Tide source: ✅ EC2015 forcing written 10-30, checked, not yet read by SFINCS (`logs/modern_bed_2026-10-30/tide/README.md`; window 10-12 → 11-13, analysis month from 10-14 12:00). **User 10-30, first run:** unscaled, C&D Canal point as is, rivers OFF, restarts on. **Deficiencies to revisit:** tide 5.6 % (Sandy Hook) to 12 % (the Battery) low in M2, mean higher-high 3–6 cm below VDatum MHHW on most arms; C&D Canal point +32 % range vs NACCS; no river baseflow, so levels near Trenton read a little low; ~42 h estimated, so it may resume after a timeout.
- **v1.0.0: chosen 11-01.** Known limits in `docs/MODEL.md` §4 (Monmouth lakes; Delaware lows + 3 marks; Cape May back bays; coarse-face inflow pile-ups incl. Salem R.; building cap overtopped at +3 m SLR). ✋ User tags.
- **Phase 6:** frozen premier in the docs ✅ (`premier_arm`, `MODEL.md`, FINDINGS part 4 (j)); research-group brief (incl. the status-notebook "rise above normal water" fig., `logs/notebook_qc_2026-10-11/baseline_check.py`), docs, backup remain.
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
- **Waves-on noise band:** measured on swz 11-01, FINDINGS part 4 (j).
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
- **Monmouth lakes:** a known limit of 1.0.0 (§63 (h), part 4 (j)). 6121 + 6122 stay ~2 m low; why the sea does not reach them is open.
- **IG in the water:** the v3 / old v4 premiers compute IG but do not couple it (`snapwave_igwaves = 1`, no
  `wvmfile`; §45). ✅ The Phase 4 premier carries the wavemaker (user 10-17; line `snapbeach`, user 10-19;
  engine `…igseed-wmseed-1…`, repeat test passed — §44 (j)) with a no-wavemaker arm beside it.
  ⚠️ `dep_subgrid_lev0.tif` is NaN over the Cape May peninsula block (no level-1 faces there).
- **Test 8 (setup-only wavemaker line):** evidence says don't run it as designed (§62); user's call.
- ⚠️ `motf_metrics` does not mask footprints, so `bed-nobuildings`' CSI is inflated; masked CSI in part 4 (j).
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

▶ **11-02: `…swomp-2-gf11@dd78d82a` IS THE PRODUCTION ENGINE for new runs (user): full storm BIT-IDENTICAL at 64 and 16 threads, 2.51 h and 5.44 h vs 12.99 h (FINDINGS §20).** Below, the path. **10-28 anatomy + prototype** (`logs/snapwave_parallel_2026-10-28/README.md`): on the v4 `p4-premier` (16 threads)
SnapWave is **8.6 of 14.1 h (61 %)**, not 97 % (that was v3 at 64 threads); the sweep is 6.7 h of it. Ceiling at 16
threads: ~2.6× (the flow is ~5 h). Step 1 patched + compiled (`…-gf11-swomp/`, tag `nj-swomp-1`): ✅ **toy
BIT-IDENTICAL 10-28** (old 1 thread vs new 1 / 4 / 16, three cases incl. wind-on 5° bins; his + map + restart files +
iteration lines; the comparator catches a wind-on/off difference: `toy_compare.txt`); ~1.1× estimated. ⚠️ that test
binary was built by hand, so its log says `svn 197-branch:SnapWave_IG` — install through `hpc/build_sfincs_native.sh`. Wavefront levels measured on the v4 mesh (8–21 k levels per direction, median width 116–351) → ~2.3×
estimated. 🔴 glibc `libmvec`: restructuring a vectorized sin/cos/exp/pow loop changes the last bit even with exact
OpenMP — checked loop by loop (`vec_compare.py`). ✅ **6 h v4 cut (63182232, 10-28): BIT-IDENTICAL** at 16 and 64
threads (`engine_gate` STRICT + byte check, 229 iteration lines). **SnapWave 3,091 → 2,421 s = 1.28×** — quote that,
not the 1.6× wall (5,983 → 3,679 s): the old copy's input phase took 1,785 s vs 143 s (cold cache / disk contention
side by side, not the patch). 64 threads add nothing to SnapWave (2,424 s). A sequential cold-cache pair would settle
the wall figure — fold into the wavefront test. ▶ **Wavefront sweep (nj-swomp-2) 10-29** (`logs/snapwave_wavefront_2026-10-29/README.md`): prototype `sfincs-swomp2-43cf6bfb` (level schedule, one sweep body, serial fallback); vectorization gate ✅; **toy BIT-IDENTICAL** at 1 / 4 / 16 threads AND with the schedule forced on at 1 thread (a different node order); ✅ **6 h swz-premier cut 63242704 (10-29): BIT-IDENTICAL** to production at 16 and 64 threads (`engine_gate` STRICT + byte check, 198 iteration lines). **SnapWave 2,858 → 539 s = 5.3× at 16 threads, 282 s = 10× at 64.** Quote those, not the 3.2× wall (old copy's input 1,810 s vs 141 s again). Whole-run estimate ~14 h → ~7 h (16) / ~3.5 h (64): the cut is the quiet first 6 h (7 calls), no storm peak — **next: full 72 h bit-for-bit run, install via `hpc/build_sfincs_native.sh`.** GPU flow + parallel SnapWave together: ~14 h → ~1.5–2 h (estimate; needs
SnapWave to run beside a GPU flow build — ask Deltares).
SnapWave is ~97 % of a v3 64-thread waves-on run (§20) and its sweep is SERIAL: a 64-thread solve averages ~6 busy cores. No OpenMP
around the sweep loop on `main` (checked 10-26). Don't write our own SnapWave (months to validate).

- **(b) Parallel SnapWave, bit-identical → no new engine gate, no re-baseline.** In this order:
  1. *Warm-up:* OpenMP on the dependency-free per-node loops (energy → wave height, the convergence check); a few
     lines, maybe 1.2–1.3×.
  2. *The big one:* level-scheduled ("wavefront") sweep — build each sweep's upwind dependency graph once per call,
     group nodes into levels, run each level in parallel; every node reads the same values as in serial order.
     Sweep ≈ 78 % of SnapWave on v4 (10-28 fit) → estimated ~2.3× per v4 run (14 h → ~6 h). Estimate, not measured.
     A few hundred lines of Fortran.
  3. *Memory order:* renumber nodes so sweep order = memory order (no arithmetic change; gain unknown).
  4. *Per-call setup:* each call re-sorts all nodes four times (part of the fixed ~42 s/call) — cache it.
  Check each against the toy and a 6 h v4 cut (bit-for-bit). A natural upstream contribution, and the same level
  structure is what a GPU port of SnapWave would need. *Number-changing* speed-ups (`-march=native`, fixing the Sandy
  Hook limit cycle — capped calls cost ~2×, §44 (g)) need a new engine label + re-baseline: separate decision.
- **(a) GPU build: DROPPED by the user 11-01.** Beta upstream, no recipe, and SnapWave would stay serial; `logs/gpu_feasibility_2026-11-01/README.md`, unsent draft beside it (user handles Deltares separately).

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
- **Scratch** (`/scratch/tpj8`): 1 T soft / 2 T hard; 980 G on 11-01 after 12 v4 arms + `_subgrid_refreeze` went here and `sfincs-nj-agri` hard-linked 253.6 G; thin headroom, shared. 🔴 **Not backed up; files not accessed for 90 days are deleted.** `experiments/`
  and most of `data/` (the 10-05 swap is finished) live here; the durable copy is the desktop pull
  (`scripts/desktop_pull_backup.sh`) — re-run it whenever an arm is scored. The engine sources
  (`/scratch/tpj8/sfincs-build/`) live here too; the patches are in `hpc/patches/` + `docs/upstream/`.
- **Camden** (`cmain`, halc*) sees its OWN `/scratch`: stage inputs via home (the igseed recipe).
- **Maintenance:** every hal/halk node, next **11-10 08:00 → 11-11 23:59**, then 12-15.
- **10-17:** ~186 `main` nodes draining ("Reduce Temps"); Camden had idle nodes.
- Claude Code may run on a LOGIN node (`amarel*`) or a small VS Code allocation (10-17: 4 CPU / 32 G):
  heavy work through `sbatch` / `srun`.

## Housekeeping

- Last cleanup: **2026-11-03** (user: "not going back to v3"; scratch 991 → 762 G, home 95.6 → 85.4 GiB;
  `logs/run_records_2026-11-03/`): the side-run floodmaps; `null-rhoa*` and `bed-aknsill+p4-nowaves` retired
  (`retire_arm.py`) + `_subgrid_p4_aknsill`; the disk survey's safe-now list (`cleanup_extra.sh`: showcase grids,
  `infiltration_v3`, attics, toy runs, superseded engine build trees, `~/nj_bight_staging`, the NACCS pre-merge
  originals, the v3 footprint clip). The pre-1.0.0 domains' runs + the v3 / v1.5 frozen meshes: records kept, then
  `cleanup.sh delete` (user runs it). Before: 2026-10-20, 2026-10-17 (120 G), 2026-10-15
  (`reports/cleanup/deletion_manifest_2026-10-15.md`). `git rm` of the old domains' tracked files: in Phase 1.
- Kept on purpose, user's call to remove: `data/gtsm/retired_v1_monmouth/`;
  the v1.5 / v3 notebooks and the weekly reports;
  `logs/audit_v4_hot_plus_2026-10-05/v4_vs_v3_deficit/shadow_hp_norain/` (705 MB rebuildable floodmap).
