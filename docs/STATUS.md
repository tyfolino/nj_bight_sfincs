# STATUS — live campaign state

**Edit this file in place; keep it under ~300 lines.** It holds what is happening NOW: what is
running, what is next, what is open. When an item closes, its durable fact goes to
[FINDINGS.md](FINDINGS.md) (or CLAUDE.md §5 if it is a trap) and the item is deleted here.
Git has the history. The campaign log this file grew into until 2026-09-29 (6,767 lines) is
`git show d70dd1e:docs/STATUS.md`; FINDINGS cites it as "STATUS <date>".

▶ **PICK UP (11-13 evening → 11-14): poster goes to print MON 11-16** — `reports/poster_2026-11-13/poster_draft_2026-11-13.pptx` (v9; drafts v1–v8 + superseded figs in `drafts/`, gitignored). Tomorrow: **v10** = add 2 Results-1 bullets (gauges, waves — `logs/poster_diagnostics_2026-11-13/README.md`) + replace "about 30 at 1.2 m" with the fresh tidal mean-higher-high count (63895431) + optional hydrograph panel (`fig_hydrographs.png`); 7 red FIAT stubs are the undergrad's (delete box + stubs if FIAT isn't ready); FIAT caption must say "flood run uses 2012 buildings; damage counted on today's building outlines" (the 2026-ground run still burns the 2012 NJDEP footprints; today's footprints enter the MODEL only with the round c bed rebuild). Poster decisions (user 11-13): submitted abstract + title "NJ-SFINCS: …"; novelty = "first SFINCS model to cover the New Jersey coast as a whole…" (no "to our knowledge"; the Hoboken / Gloucester City SFINCS papers are in `lit_check.md`, not on the poster); ALL scores = Model 1.1.0 RAIN ON (HWM RMSE 0.35 m, > 86 % of FEMA's extent, CSI 0.80); assets on TODAY's ground only (no 2012-ground counts: assets moved); two experiments (Results 1 Sandy test / Results 2 power grid + buildings); Fig 1b inset C = Atlantic City; Fig 3 water = Fig 1b's definition. Fonts = template #2's (PT Serif / Source Sans 3).
**Done 11-13:** poster v1→v9 (Fable review: `poster_review_2026-11-13.md`); MOTF re-classify READ (`logs/motf_classify_v11_2026-11-12/READ.md`: rain off trades −72 km² FA for +31 km² misses; FINDINGS text proposed); Cape May read (`logs/capemay_tests_2026-11-09/READ.md`: hs130 + inlets1m don't close the back-bay deficit; bracket ran away → needs a mechanism decision); 63843110 OOM cause = `report._thumb` reading 19 G gallery tifs → decimated read; gallery tif now compressed (`validate/metrics.py`); scratch 1,113 → ~955 G (safe list + recompress + 3 wave caches; more Amarel space is PAID, user 11-13); public site = "1.1.0 at a glance" + rain-off FEMA reference (pushed); MOTF product cutoffs found (Jersey City / Bayonne + Linden; `logs/motf_cutoff_jc_2026-11-13/README.md`); poster diagnostics (40 fair gauges RMSE 0.226 m / bias −0.10 / 85 % within ±0.25 m; waves on vs off ΔRMSE −0.186 [−0.317, −0.072], median 50 m, n 119); power_exposure.py reads the base band (old "30" unchanged); FIAT bare-ground + building-centroid tooling (`scripts/fiat_building_depth.py`); SLOSH-style idea logged (Later).
**Running:** **63853850** `mhhw_v2` (arms 1–2 = +2 / +4 ft tidal, TIMEOUT ~11-14 11:08 by design) + **63887749** companion (arms 7, 6 in `_inflight_`) + **63887750** resume (PENDING afterany:63853850; all MHHW done ~11-15; 🔴 its `expected_resume.md5` = 26 files incl. `nj_sfincs/config.py`, `model.py`, `domain.py`, `run_experiments.py`, `mhhw_maps.py`: **no edits to those until it starts**; `expected_resume.md5` + `expected_companion.md5` re-verified OK 11-14 08:50); **63895431** SLR asset watcher (+4 ft tidal read started 11-14 08:47, still-water later). ✅ `campaign_check.py` now reads each job's md5 file from its spooled script (11-14; `sacct --env-vars` is off on Amarel: no `job_env` flag) — the morning's 🔴 was a false alarm.
**Finished overnight 11-13 (all on hal nodes; the 4 solves audit clean, no resumes):** **63893637** weirs pair score-only (re-score of 63887740, which refused on the old valve-sign check): dikes + levees move gauge crests ≤ 0.03 m (Greenwich), 0 assets change state — to read (`logs/weirs_dikes_levees_2026-11-12/pair_63893637.out`). **63887739** Cape May re-run: K12, marsh-half, inletlines0 scored; inletlines0 LOWERS back-bay crests 0.05–0.23 m vs `p4-nowaves` (Stone Harbor worst) — to read (`rerun_failed_63887739.out`). **63894123** native re-score: all checks PASS — 1.1.0 RMSE 0.348 / CSI 0.802; vs 1.0.0 ΔRMSE −0.072 [−0.166, −0.007] (1.x file, n 119); rain-on vs off −0.017 [−0.028, −0.007]; galleries ready → `publish_gallery.py --current`. **63895831** FIAT GeoTIFFs: all files written (`share/…bed{2026,2012}_bareground*`); checks (b) open ground, (c) grid, beds PASS; (a) missed its 95 % bar (85.4 / 80.1 %), **read 11-14: the bar was mis-specified** — every building the rule calls wet has a depth; the 15–18 % blank stand above the street water around them (only 195 / 455 have any ring level ≥ 0.15 m above their ground); 9–13 k are within 0.10 m of wet (README "Check (a) read", `why_nan*.py`). **User 11-14: hand over as-is** → old 1.0.0 share READMEs marked SUPERSEDED by hand, a "beside the water but dry" note added to both `_buildings_README.md`; user sends Nithila the `share/…v11_bed{2026,2012}_bareground*` files. **63895426** waves pair = the poster's waves on/off number.
**Done 11-14 (agents):** gallery re-published native (`publish_gallery.py` reads the manifest's floodmap now; USER PUSHES `~/sandy_flood_site`); FINDINGS §37 / §39 / part 4 (n)(o) + MODEL.md §6 + CHANGELOG carry the native numbers, gauges, waves, MOTF classification (⚠️ the waves-off twin `p4-nowaves` also lacks the E/R levees — noted; levees alone leave RMSE unchanged); `paired_hwm_bootstrap.py --floodmap-root` cross-domain fixed (`run_domain()`, tests).
**Poster v10 DONE 11-14** (`build_v10.py`; `poster_text.md` "v10 changes"): gauge + waves bullets in Results 1 (26 pt), SLR "about 30 (still water)" → **22 of 182 on a typical high tide** (+4 ft tidal mean higher-high, today's ground, 63895431) in Abstract / Methods / Results 2; hydrograph panel skipped (no room); FIAT box + stubs unchanged (user's call before print).
**Next (in order):** (1) FIAT: user sends Nithila the files (decided 11-14); (2) poster: FIAT box keep / drop before print; (3) read 63893637 weirs pair, 63887739 Cape May re-run; publish native galleries (user pushes); (3b) after 63887750 starts: apply the 4 MOTF cutoff boxes in `domain.py` + re-score MOTF rows; (4) MHHW v2 products → climate team + FIAT MHHW export (README command); (5) FINDINGS: MOTF re-classify + gauges + waves + native 1.x numbers into MODEL.md / CHANGELOG; (6) Cape May bracket mechanism; weirs hand passes; (7) scratch: OneDrive archive list (~200 G); (8) round c bed rebuild; (9) 2.0 mesh / domain / forced line.
**Standing decisions:** NO 1.2, straight to 2.0; no Sandy-specific tuning; behind-a-levee diagnostic beside the headline; HD_HUD paints the 2.0 2012 bed; 2.0 = Hudson to 40.860 + Hell Gate, ONE 2.0.0 with 2012 and 2026 beds (`logs/hudson_design_2026-11-02/README.md`); production engine `hpc/production_engine.txt`; erosion = 3.0; Sedge Island #11 CLOSED 2012 / OPEN today (user 11-12); 11-12 decisions (Keansburg / Port Monmouth / normal-weather closures OPEN except Overpeck SHUT / +0 ft both datums / weirs list / round c roofs + asset guard) are in git history of this file (11-12 commit).

**Phase 4 still to read:** capped-hour `zsmax` (open question below).
Last updated: **2026-11-13** (evening wrap-up) — poster v9, diagnostics, MOTF cutoffs, 9 jobs overnight.

---

## Now

- **v3 is DONE** (2026-09-24). Reference `naccs-premier` — HWM RMSE 0.329 / bias −0.143 (median, 50 m, n 94),
  MOTF CSI 0.706; re-run on the seeded engine in Phase 4 (`p4-ref` / `p4-ref-nowaves`).
- **Model 1.1.0 (11-09): `v4_refreeze_swz_v11` / `p4-premier+weir-elizabeth-rahway`** (`4bc97aae885f0aa4`, job 63617802): RMSE 0.355 / bias −0.072 (median, 50 m, n 119, 1.x mark file; 6.25 m map) → **0.348 / −0.067 on the native 3.125 m map (11-12)**; paired vs 1.0.0 ΔRMSE −0.069 [−0.158, −0.007]; CSI 0.795 → **0.802 native**. `docs/MODEL.md`, `CHANGELOG.md`.
- **Model 1.0.0: `v4_refreeze_swz` / `p4-premier`** (`90cc7468614a5814`, job 63181564): RMSE 0.439 / bias −0.128 (median, 50 m, n 110), CSI 0.784 (6.25 m map; **0.791 native**, 11-12); without the 6 noted marks 0.354 / −0.093 (n 104). `docs/MODEL.md`.

## Running (11-13) — see PICK UP for the queue

Finished items 11-05 → 11-07 (each closed; read the README): v1.1 levee premier scored + merge check
(`logs/scoring_2026-11-07/`); v1.2a bed test → read 11-12 (`logs/relevance_fixes_2026-11-06/READ_v1_2a.md`); levees vs
Overpeck-only tie (`logs/v1_1_read_2026-11-06/READ.md`); statewide MOTF classification on 1.0.0 (`logs/motf_classify_2026-11-07/`,
superseded by the v11 / native re-run, `logs/motf_classify_v11_2026-11-12/`); weir count 819 (`weircount_819.md`); modern b
audit + verdicts (`logs/modern_audit_triage_2026-11-07/VERDICTS.md`); modern levee arms registered (`bed-modern+…+weir-elizabeth-rahway`,
823 u/v, not solved; superseded for new maps by the 11-12 `bed-modernb+…+weir-normalweather` arms); Little Egg overlay KEPT
(`logs/barnegat_tide_2026-11-04/READ.md`); v1.1c bed built (`bed_summary_v1_1c.txt`); E/R levee pair read; bed audit + relevance
ranker (`logs/bed_audit_2026-11-05/`); E/R levees on the 2026 bed (`logs/walls_elizabeth_rahway_modern_2026-11-06/`); BlueTopo
MLLW fix (`logs/bluetopo_mllw_2026-11-06/`); Christina gauge datum fix (FINDINGS ~l.2342; downloader must run with `NJ_DOMAIN=v4`).
Scratch → OneDrive: `logs/scratch_survey_2026-11-12/README.md` (current; 11-04 survey superseded).

## Modern (2026) bed: audit + decisions (11-04, `logs/modern_bed_checks_2026-11-04/README.md`)

- **Audit:** `_subgrid_modern2026` = 1.0.0's recipe + `modern_land_2026` painted first; all 16 tiers + 11 overlays present by name. Behind on: (a) the v1.1 fixes (ride along), (b) its own plan — `ehydro_latest_2026.tif` built 10-30 but in no recipe, BlueTopo / dune check / footprints / land cover never added, (c) sweeps run only on the 2012 bed. **Decks:** removed decks come back as FLAT water-surface sills at −0.7 to −0.9 m across deep channels (ACE −0.91 m × 130 m over −4.6 m) — the sweep calls them clear; 288 crossings not in the v1.1 overlay (115 major road / rail). The v1.1 overlay still applies (584 / 769 ways still flagged).
- **Decisions (user 11-04):** (1) rebuild a 1.x modern bed once the deck pass + sweeps are ready, not before; (2) latest channel surveys everywhere, deepenings included ("2026 as built"); (3) BlueTopo only where its survey is newer than CUDEM's; (4) modern building footprints + latest annual NLCD (roughness + curve number); (5) post-Sandy walls / NLD floodwalls: inventory first (crest Z from NLD), user picks. Salem River paint: still open (both beds).
- **Sweeps (11-04, `logs/modern_sweeps_2026-11-04/`):** water opened 135 km², closed 23 km² (6 km² loses the tide at MHHW, ~16 sites); federal channels 98.3 % unchanged. Cause: `build_modern_land.py` replaces the 2012 bed wherever it reads ≥ −0.25 m — lidar water surfaces over CUDEM fills open creeks, but also cover `riverbeds_v4` (Delaware at Trenton +1.2 m, Raritan above New Brunswick: a recipe bug). Fixes: paint `riverbeds_v4` + base eHydro AFTER `modern_land`; min(2012, modern) on mapped water < MHHW + 0.5 (lakes exempt); refuse lidar < −3 m where the 2012 bed ≥ −0.25 (Navy Yard dry docks); deck pass; re-sweep (~20 min). The +70 m = Tullytown landfill cells (real).
- **Inputs (11-04, `logs/modern_inputs_2026-11-04/`):** `ehydro_latest_2026` ready (166 surveys, 134 km² new channel) except 10 (+4) surveys reading 0.8–1 m deeper than BlueTopo's copy (Christina, SR_02–05, LR_01–03, Newtown, Cape May Canal …); BlueTopo-newer-than-CUDEM mask 524 km² (237 km² Delaware Bay), no download; footprints: NJDEP vs Microsoft vs FEMA/ORNL USA Structures (24 / 186 NJ power assets swing ≥ 10 pts on the choice); Annual NLCD 2025 C1V2 clipped (3.6 % changed). ~~DROP the 10 (+4) datum-disagreeing surveys~~ → **RESTORED (user 11-05; `logs/ehydro_datum_2026-11-05/README.md`): ours are right — BlueTopo leaves MLLW unconverted where VDatum has no grid** (the jump sits on VDatum's coverage edge inside single surveys CC_01 / LI_01 / RI_01 / SR_01; CUDEM agrees with ours across it; Delaware main-stem controls +0.04–0.06 m); use the 10-30 `ehydro_latest_2026` as built. M537 Grays Ferry channel = **−7.2 m NAVD88** (newest Schuylkill survey 60–120 m either side), not the picker's −5.5. ⚠️ The planned BlueTopo-newer layer has the same fault on 6.3 km² outside VDatum (Maurice 2.2 km², Schuylkill / Darby, Christina, Lewes–Rehoboth): its builder must add the tidal plane there or drop those pixels. **Decisions (user 11-04):** footprints = HYBRID (USA Structures, pre-2019 polygons swapped for Microsoft's; ODbL attribution on the public gallery, OK); buildings + developed-n 0.04 stay NJ ONLY; BlueTopo overrides our carves (hierarchy, Little Egg, Sayreville) where its survey is newer. Plumbing (Claude): `--ground` for the burn, `--nlcd` for `build_cn_nj.py`, after the guarded jobs.
- **Walls (11-04, `logs/walls_inventory_2026-11-04/`; decisions user 11-04):** only Keansburg + Overpeck block flow in either bed (a 25–50 m cell averages a levee away; beds SHOW crests to 0.1–0.2 m). (1) **Elizabeth River South (R + L bank, 1988, crest 3.65–3.72 m) + Rahway South Branch (1966, 3.72 m) as weirs in BOTH beds** (1.x, after the v1.1 tag → 1.2 or rides into 2.0; ~1 day hand tie-ins + a waves-off pair to read Bayway 345 kV, which 1.0.0 floods 99.8 %, median 0.80 m; Sandy overtopped by 0.05–0.7 m); (2) Port Monmouth: note now, full line (3.96 m) a 2.x scenario; (3) Delaware Bay salt-hay / meadow dikes: note only — Delaware is not a focus. The agri session has the NJ bayshore ones already BUILT as weirs from NLD (~113 km, crest = lidar ridge, farm-dike notches filled + one check-valve gate per leveed area: `~/sfincs-nj-agri/data/structures/dikes.weir`, `dikes_open.weir`, `dikes_built.gpkg`; read-only, reuse if ever wanted); its DE side is NWI impounded-wetland outlines only, not surveyed dikes; (4) Keansburg weir unchanged; (5) Atlantic City bulkheads: note only.
- **Elizabeth + Rahway weirs PREPARED 11-05 (`logs/walls_elizabeth_rahway_2026-11-05/README.md`; nothing registered / submitted):** `sfincs_overpeck_open_elizabeth_rahway_ground.weir` = 1.0.0's weir with Overpeck OPEN + 7 structure lines (3 NLD routes at NLD crest, 85 m Bayway wall, 3 tie-ins) + 11 ground lines (lidar ridge where the mesh averaged a rise away); `_closed` variant (tie-ins + Bayway wall at crest). 817 structure u/v points on the 1.0.0 / v1.1 beds. First entry into each area ≈ the 3 m lidar's (RB 3.14 / LB 2.82 / Rahway 3.38 m) vs Sandy 3.76 (Elizabeth) / 3.86 (Rahway): **all three still flood, Bayway shallower + later, not dry**; Bayway also reachable from the S via the refinery / rail corridor at 3.25 m. Beds sit 0.14–0.32 m under the NLD crest. Pair `pair.slurm` (one job, ~5–6 h, 320 G) = new arm vs `p4-nowaves+weir-overpeck-open` (already scored); read `read_er_rw.py` self-checks Bayway 0.969 / 0.79 m vs 0.968 / 0.81. **Decided (user 11-05): the defaults** — ER-1 tie-in at ground, ER-3 Bayway wall at lidar ground, ER-4 refinery / rail flank open, G-1 all closures + pipe gates shut; ER-2 (LB east tie at ground) + ER-5 (NLD crest as is) keep their defaults → the `_ground` file. The 2026 bed needs a second ground-line pass (RB opens 0.35 m lower). Register + copy into `data/structures_v4/` after 63538727 + 63538729.
- **Deck pass (11-04, `logs/modern_decks_2026-11-04/`):** automatic, 4 independent signals (bed, OSM, water, open-under); 343 sites REMOVE, 5 LOWER-SILL, 97 KEEP; agrees with v1.1's decisions on 93.5 % of firm calls (98.4 % of REMOVE vs v1.1 painted). Draft overlay `deck_fix_modern_draft.vrt` (lower-only, applied after `deck_fix_v4`). **Short list (15) = picker https://claude.ai/artifact/MpQb2PH4G5xB4Uve5Dmj9Y** (v2 11-05: a plan-view bed map per site — 2012 / 2026-with-v1.1 / if opened, MHHW contour, OSM line — from `m7_bedmaps.py`, PNGs in `fig/bedmaps/`); user round 1: E1–E3 OPEN — they are BRIDGES (GSP / Bennett Ck, I-95 interchange / Christina, CR 581 / Alloway Ck), not culverts: OSM bridge tags were missing or offset; the sill sweep found them independently (keep it as the safety net). **Round 2 DONE 11-05** (bed maps in the picker; `user_decisions_2026-11-05.csv` = final per site): the flat "sills" (M537 / M181 / M271 / M232) are lidar blind spots (low-tide water surface under the deck), not pilings → open; most fixed by the min(2012, 2026)-on-mapped-water rule, except **M537** (2012 blocked too: needs the dropped Schuylkill SR surveys' datum resolved or ENC soundings) and **M271** (the fix reaches only −1.08 m in a −5 to −7 m inlet: carve to the eHydro channel). Viaducts: **M364 open** (Foundry St, deck 4.7 m over a ~2 m street), **M049 keep** (street-level gap exists), **M064 keep** (fill ramp + Morristown rail embankment). Penn's Landing **M562 / M561 → min rule, NO carve** (the carve cuts −9 m trenches). **E4 keep** (2012 water = CUDEM ~0 fill). **E3 REVISED to KEEP (user 11-05):** it sits on an arm of **Alloway Lake** (impounded, NID dam 20 ft, NWI diked 99 %); the 2026 1.61 m is the real pool, the 2012 "open" creek is CUDEM ~0 fill (as E4). **Inland-water sliver sized 11-05 (`logs/inland_water_lines_2026-11-05/README.md`):** 584 sliver pixels in 26 of 87 painted items, identical in 1.0.0 / v1.1; 536 at Alloway Lake (the NHD outline's 1–2 px tail painted at the pool, ~1.6 km), the rest 1–5 px each; every lake held at pool as intended; nothing crosses a tidal channel. The real defect: the arm's valley is CUDEM ~0 fill (~0.17 km², ~270,000 m³ below pool) acting as a tidal arm of an impounded lake. **DECIDED (user 11-05): raise the arm to the 1.61 m pool INTO v1.1b** **`alloway_pool_v4` BUILT 11-05** (`data/elevation_v4/inland_water/alloway_pool_v4.{tif,vrt}`, `logs/inland_water_lines_2026-11-05/build_alloway_pool.py`, `out/alloway_pool_check.txt`): max(bed, 1.61) on the CUDEM-fill floor (≤ 0.6 m) connected to the lake outline, cut at the NID dam crest (NJ00038): 0.388 km², ~600,000 m³ (NE arm 0.237 + SE arm / north margin 0.151 km² — more than the first 0.17 km² estimate), 0 px at / below the dam or on the tidal channel; the arm's link to the tide −0.36 → 1.61 m (dam + pool control). In `build_v1_1b.slurm` after `inland_water_bed_v4`; catalog snippet in that README. ✅ **Overland-underpass sweep SIZED 11-05 (`logs/underpass_sweep_2026-11-05/README.md`, `candidates.csv`, `top15.md`):** 273 bridges over a street / rail hold back water that stood above the street in 1.0.0's Sandy run (212 in the v1.1 bed, 177 modern, 116 both; 84 hold back ≥ 1 m), but only 124 show a peak difference across them (71 ≥ 0.25 m, 41 ≥ 0.5 m, 11 ≥ 1 m) — mostly the water went round. 81 within 1 km of a power asset (18 with ≥ 0.25 m). ≥ 0.25 m sites: Essex 14 (airport + NEC embankment streets), New Castle 11, Atlantic 8, Philadelphia 6, Camden 6, Ocean 6, Hudson 4, Kings 4. M364 open in v1.1, blocked 0.8–1.0 m modern; M064 has nothing passing under it. A screen, not a fix list (rain ponding in the peaks, OSM up to ~25 m off, opening width unknown). **Recommendation: 1.2 + modern bed** (~1 day: eye check top ~15 of the 41, street-width lower-only slots, rebuild, waves-off pair). **No South Street path for v1.1 (11-05):** none of the 6 sites near it carries the 3.6 m Ironbound water on its high side (peaks 2.46–3.22 m; differences 0.00–0.35 m where blocked in v1.1; U1039 Chestnut St 1.11 m is already open in v1.1). **Eye-check picker (15 sites) = https://claude.ai/artifact/UNFLEfMp4Y9Ae32DTnjEtG** (`picker_page.html`, `build_picker.py`; user's, no deadline). ⚠️ Scratch 1008 G of the 1,024 G soft quota (11-05) → **deleted 4 read-done test beds (user 11-05):** `_subgrid_p4_hierv4e`, `_hierv4e_manchan`, `_subgrid_p4_devmanning`, `_subgrid_modern2026_akbank` (~140 G nominal; run dirs keep their hard-linked tables; re-staging those arms = a ~15 min parallel rebuild first). `_subgrid_p4_hierv4d` KEPT (63538729 + the modern deck pass read it as the 2012 bed). ⚠️ **v1.1 deck-carve audit DONE 11-05 (`logs/deck_carve_audit_2026-11-05/README.md`, `out/flagged_sites.csv`):** same error, ~2 % of the carved volume, local: of 525 sites, 118 OVER-DEEP (> 1 m below a CUDEM-confirmed bed; 1.9 ha, 38,500 of 2.15 M m³; 102 on tidal crossings), 65 turn land above MHHW into water (0.73 ha), 18 cut a crossing embankment (Cape May Canal NJ 109, Rumson–Sea Bright, Lincoln Hwy, NJ 21, Reedy Pt), 86 viaducts opened on bed evidence only (unverified). No closed-basin trench, no protecting barrier breached. Cause: "ground" = p25 of the bed 6–36 m out lands on the riverbed beside viaducts (NEC / Passaic, Pulaski Skyway, P&H, NJ 3), and OSM ways running onto fill / along banks (Tuckerton Ck ~150 m of bank, 130 m from a mark). Shrewsbury / NJ 36 false alarm, but ~120 m of the 2010 +1 m deck pad remains. **Corrected rule (paper-tested, not built):** lower only deck pixels, each to its own side's bank, skip ridge stations → 587 of 597 wet crossings stay open (Normandy Rd keeps its override + 9 marginal close). Same fix due in `m4_overlay.py` (modern). Decks test 63538729 ran the UNcorrected overlay; watch the 11 flagged sites within 1 km of a mark in its read. **DECIDED (user 11-05): fix NOW, into v1.1** → **`deck_fix_v4b` BUILT 11-05** (`data/elevation_v4/deck_fix/deck_fix_v4b.vrt`, 583 tiles; `logs/deck_carve_audit_2026-11-05/build_v4b.py`, `out/verify_v4b.txt`): deck pixels only, each to its own bank, ridge stations skipped, no paint where any overlapping way reads natural bed; 588 / 597 wet crossings open (the 9 re-closed end 0.05–0.7 m above MHHW); over-deep 212 → 1, land-to-water 139 → 1 (both Normandy, override kept), embankment cuts 21 → 0. Job `build_v1_1b.slurm` (nonpre, parallel builder, A2 + B checks; refuses until the catalog key exists) — **add the README's catalog snippet + submit after 63538729 finishes.**
- **Next (11-07):** modern b is BUILT (`logs/modern_bed_b_2026-11-06/README.md`) and audited; round c follows [BED_QUALITY.md](BED_QUALITY.md) — observation-found blockages (tidal reach on the 2026 bed), the survey depth rule, plus the known items (`raritan_mouth_fix_v4` / `greategg_plug_fix_v4` on the 2026 bed, M537 / M271 full carves, the deck pass re-run on this bed, footprints + NLCD 2025 when the builder has `--ground` / `--nlcd`).

- **Parallel subgrid builder ✅ (11-04, `logs/subgrid_parallel_2026-11-04/README.md`):** `scripts/rebuild_subgrid_parallel.py` (+ `hpc/rebuild_subgrid_parallel.slurm`, `nj_sfincs/subgrid_parallel.py`, tests; `git add`ed) is **BIT-IDENTICAL** to the serial rebuild on `_subgrid_p4_hierv4d`: all 11 `sfincs_subgrid.nc` variables (same sha256), every tif pixel + overview, at 8 / 16 / 32 workers and after a SIGKILL + resume. 18,293 s → 916 s at 16 workers (~140 GB) / 673 s at 32 (~253 GB). Per-block checkpoints: a requeue resumes (`--force`), so `main` is safe again. Default: `nonpre`, `-c 16 --mem=170G`. The 80% it removed was Python index loops over empty blocks. Open: skip overlay paint where a footprint can't reach (bit-identical, touches `install_overlay_merge`); reusing the cell merge in the uv pass is NOT bit-identical (−45%, re-baseline only). The queued decks / devmanning `ONLY_A` rebuilds still use the serial script.

## MHHW + 2 ft / + 4 ft for the climate hazard team: two versions (user 10-29)

- **Still water, no solve: DONE** (63440060, `logs/still_maps_2026-11-02/`): `floodmaps/bed-modern+still-{2ft,4ft}_depth.tif`. Sloped VDatum MHHW + s, sea-connected through the subgrid sills and weirs (405 of 407 weir points closed). Normally-dry land 652 / 963 km², depth p50 0.46 / 0.93 m. The job's "figure FAILED" was the wrapper's `grep -v Warning` exiting 1 on a step that prints nothing; `qc_views.png` is fine.
- **Hydrodynamic (tidal twin): DONE** (63482546, `logs/tide_maps_2026-11-03/`): `floodmaps/bed-modern+tide-{2ft,4ft}_{mhh,max}_depth.tif`. Normally-dry land >= 0.15 m, + 2 / + 4 ft: still 582 / 890 km², tidal mean higher-high 370 / 748, tidal month max 519 / 846. Barnegat agrees with still (tidal slightly wetter); the gap is largest up the Delaware River (+ 2 ft 18 vs 3 km²) and around Newark Bay (12 vs 4) (`compare_still.csv` / `.png`). **Packaged 11-03 in `share/mhhw_plus{2,4}ft_*` + `share/mhhw_plus2ft_4ft_README.md`** (both versions, VDatum table, region table): ✅ sent by the user 11-04. ⚠️ **Its high tide against VDatum MHHW** (`tide_maps_2026-11-03/README.md`): open coast within ~3 cm; Newark Bay −0.11, Philadelphia −0.20, Newbold −0.29, Great Bay −0.35, Greenwich (Cohansey) −0.34, Christina at Newport −0.45 m (+2 ft run). So on these beds the hydrodynamic maps UNDER-flood the river shores and those back bays. Agreed 11-03: send both, preliminary, with the table; fix tidal reach in v1.1; re-run the twin on the v1.1 bed.

## Power exposure: first pass (11-02, `logs/power_exposure_2026-11-02/README.md`)

- Sandy, Model 1.0.0, preliminary: NJ 59 wet / 123 dry / 71 not computed. **Still water (read 11-03):** NJ wet + 2 ft 17 (none on >= 25% of its land), + 4 ft 30 (6 on >= 50%: small sites; the big plants wet at the edge, their burned buildings read dry — read `band_*`). ⚠️ The asset files are believed to be today's (PSE&G moved assets after Sandy; user), so this is today's layout against a Sandy-sized flood, not what flooded in 2012. **Sandy is the test case (user 11-02): no 2012 asset list exists or is needed; the end read is today's assets on the modern bed ("if Sandy happened today"), which needs Sandy's forcing on the modern bed.** Leonia Substation is wet at + 2 ft (one edge pixel) but dry in Sandy: re-read after the Overpeck test.

- **Later — FIAT output (user 11-05):** the depth FIAT wants must be INTERPOLATED to each building's CENTROID. Partly in place: `scripts/export_share_floodmap.py --ground <nobuildings subgrid dir>` (10-29) downscales the run's `zsmax` onto the bare-ground bed so a footprint carries the depth against its building (the burned bed reads NaN / shallow inside footprints). Still to do when FIAT comes back: the centroid interpolation itself (zsmax from the surrounding street faces → centroid, minus bare ground there; a building that fills a whole cell reads dry otherwise), on the 1.x / 2026 bed.

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

## ⭐ Final audit → 1.0.0 (plan approved 10-15): DONE

Plan `~/.claude/plans/i-think-i-m-ready-warm-trinket.md`; Phases 0–6 closed (FINDINGS part 4 (h)–(j); `logs/rebaseline_2026-10-19/`;
1.0.0 chosen 11-01, limits in `docs/MODEL.md` §4). DEP one-pager done (`logs/one_pager_2026-10-20/`; its numbers are the 10-11 premier
without 5 marks). **Gallery / site:** `~/sandy_flood_site` (`scripts/publish_gallery.py`; user commits + pushes) shows Model 1.1.0
since 11-09; depth convention CLAUDE.md §6. The full 10-15 → 11-02 text is in git history of this file.

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

## Later: SLOSH-style synthetic hurricanes on today's coast (user 11-13: "I would totally do those")

Like NOAA's SLOSH MEOW / MOM surge maps, but with NJ-SFINCS physics (waves, rain, rivers, 25 m / 3 m subgrid): idealised
parametric storms (e.g. Holland wind + pressure; Category 1–4 × a few tracks / forward speeds / landfall points, at
high tide) on the 2026 ground, then envelopes per category and the power-asset / FIAT reads. Each run ~3 h on one
64-core node, so a few dozen tracks is feasible. **Decided (user 11-13):** wind model = TEST BOTH (Holland and
hydromt-sfincs' built-in spiderweb); rain = NONE (surge only, as SLOSH); ocean boundary = later (our NACCS-forced line
needs a surge boundary per synthetic storm: a coarse parent model, or NACCS's own synthetic-storm set); tracks = TBD
(NACCS JPM-OS storms that hit NJ vs a SLOSH-like grid). **Waves (proposed, not decided):** waves OFF for the full set
(SLOSH-comparable, cheaper, no per-storm wave boundary needed) + waves ON for the worst track per category to measure
what SLOSH leaves out (on Sandy waves were worth +0.2–0.3 m at the marks; waves-off RMSE 0.53 vs 0.35 m). After 2.0.

## Later: channel-deepening attribution experiment (user 11-05: after we're happy with v1.1)

Sandy on the 2012 bed with ONLY the federal channels swapped to their post-deepening surveys (NY/NJ Harbor 50 ft ~2016: Ambrose, Anchorage, KVK, Newark Bay, Port Elizabeth / Newark, Arthur Kill; Delaware main channel 40 → 45 ft ~2010–2017), waves-off pair vs the 2012 channels → the peak / tide-range change at Newark Bay, the Delaware gauges and inland = the deepening alone. Needs the deepened-channel list + survey pairs from `logs/ehydro_inventory_2026-11-05/`. Context: the 10-06 harbour trench test (no channel → surveyed channel) raised Newark Bay's Sandy peak 2.99 → 3.50 m and its range ratio 0.68 → 1.04 (FINDINGS, Raritan record); literature: Familkhalili & Talke 2016, Ralston et al. 2019, Chant / Sommerfield / Talke (Newark Bay), Talke & Jay 2020 (verify before citing).

## Later: upstream contributions to Deltares (user 11-04: "do that all later"; good for the CV)

Issues / PRs to SFINCS + hydromt_sfincs: meteo corner-vs-centre offset (FINDINGS part 4 (e)); unseeded IG `RANDOM_NUMBER` (§44); SnapWave wind-direction bug (§43); NetCDF `inifile` read as binary (§51); swomp (fork `nj/v2.3.3-swomp-2`, `hpc/patches/`); the parallel subgrid builder (`logs/subgrid_parallel_2026-11-04/`, bit-identical, 20× faster).

## Future: make the model faster — DONE for now (11-02)

**Production engine `…swomp-2-gf11@dd78d82a`** (`hpc/production_engine.txt`, user 11-02): full storm BIT-IDENTICAL to the old engine,
2.51 h on 64 threads / 5.44 h on 16 vs 12.99 h (FINDINGS §20; `logs/snapwave_parallel_2026-10-28/`,
`logs/snapwave_wavefront_2026-10-29/`). Left for later: memory-order renumbering + per-call setup caching (bit-identical,
gain unknown); number-changing speed-ups (`-march=native`, the Sandy Hook limit cycle, §44 (g)) need a new engine label +
re-baseline. GPU build DROPPED (user 11-01, `logs/gpu_feasibility_2026-11-01/`). Upstream: see "Later: upstream contributions".

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

- **Home** (`/cache/home`, GPFS): 100 G soft / 110 G hard; **64 G on 2026-11-07** (was 93.7: agri beds → scratch, caches; `logs/home_trim_2026-11-07/`). Ask
  `/usr/lpp/mmfs/bin/mmlsquota -u $USER --block-size auto cache` (lags ~10 min).
- **Scratch** (`/scratch/tpj8`): 1 T soft / 2 T hard; 980 G on 11-01 after 12 v4 arms + `_subgrid_refreeze` went here and `sfincs-nj-agri` hard-linked 253.6 G; thin headroom, shared. **11-06: 1005 G (over soft; the v1.1c build crossed it) → 858 G** after deleting the rebuildable bed tables (`subgrid/`, `sfincs_subgrid.nc`) + gallery floodmaps of the 5 read waves-off tests (hierv4d, hierv4e, hierv4e+manchan, devmanning, decks) and `_subgrid_p4_hierv4d` / `_subgrid_p4_decks` (user 11-06; list in `logs/scratch_cleanup_2026-11-06/deleted_files.txt`; re-staging `bed-hierv4d` / `bed-decks` now needs a rebuild). ✅ **11-06: the 11-04 archive list ARCHIVED + DELETED → 638 G** (6 units VERIFIED on the desktop, OneDrive "Up to date"; restore note `experiments/ARCHIVED.md` = `logs/scratch_cleanup_2026-11-06/ARCHIVED.md`, file list beside it; the arms stay registered). Was: the 11-04 archive list (~182 G) to OneDrive by the DESKTOP pull — rclone is BLOCKED by the Rutgers tenant (AADSTS50105, tested 11-06; binary removed); md5 manifests re-made 11-06 (identical to 11-04; the copy is ~109 G). 🔴 **Not backed up; files not accessed for 90 days are deleted.** `experiments/`
  and most of `data/` (the 10-05 swap is finished) live here; the durable copy is the desktop pull
  (`scripts/desktop_pull_backup.sh`) — re-run it whenever an arm is scored. The engine sources
  (`/scratch/tpj8/sfincs-build/`) live here too; the patches are in `hpc/patches/` + `docs/upstream/`.
- **Camden** (`cmain`, halc*) sees its OWN `/scratch`: stage inputs via home (the igseed recipe).
- **Maintenance:** every hal/halk node, next **11-10 08:00 → 11-11 23:59**, then 12-15.
- **10-17:** ~186 `main` nodes draining ("Reduce Temps"); Camden had idle nodes.
- Claude Code may run on a LOGIN node (`amarel*`) or a small VS Code allocation (10-17: 4 CPU / 32 G):
  heavy work through `sbatch` / `srun`.

## Housekeeping

- Last cleanup: **2026-11-07** (home trim: VS Code leftovers, conda caches, 17 agri beds → `/scratch/tpj8/sfincs-nj-agri/data_bulk/elevation` with symlinks; tell the agri session). Before: **2026-11-03** (user: "not going back to v3"; scratch 991 → 762 G, home 95.6 → 85.4 GiB;
  `logs/run_records_2026-11-03/`): the side-run floodmaps; `null-rhoa*` and `bed-aknsill+p4-nowaves` retired
  (`retire_arm.py`) + `_subgrid_p4_aknsill`; the disk survey's safe-now list (`cleanup_extra.sh`: showcase grids,
  `infiltration_v3`, attics, toy runs, superseded engine build trees, `~/nj_bight_staging`, the NACCS pre-merge
  originals, the v3 footprint clip). The pre-1.0.0 domains' runs + the v3 / v1.5 frozen meshes: records kept, then
  `cleanup.sh delete` (user runs it). Before: 2026-10-20, 2026-10-17 (120 G), 2026-10-15
  (`reports/cleanup/deletion_manifest_2026-10-15.md`). `git rm` of the old domains' tracked files: in Phase 1.
- Kept on purpose, user's call to remove: `data/gtsm/retired_v1_monmouth/`;
  the v1.5 / v3 notebooks and the weekly reports;
  `logs/audit_v4_hot_plus_2026-10-05/v4_vs_v3_deficit/shadow_hp_norain/` (705 MB rebuildable floodmap).
