# STATUS — live campaign state

**Edit this file in place; keep it under ~300 lines.** It holds what is happening NOW: what is
running, what is next, what is open. When an item closes, its durable fact goes to
[FINDINGS.md](FINDINGS.md) (or CLAUDE.md §5 if it is a trap) and the item is deleted here.
Git has the history. The campaign log this file grew into until 2026-09-29 (6,767 lines) is
`git show d70dd1e:docs/STATUS.md`; FINDINGS cites it as "STATUS <date>".

▶ **PICK UP (10-19 evening; running: 62734605 `sbg_nobldg` → ~22:00):**
1. ✅ **Wavemaker line DECIDED (user 10-19): `--snap-seaward-of-beach`** =
   `data/wavemakers_v4/v4_wavemaker_5m_mhw_snapbeach.geojson` (8 pieces, 157.7 km; Cape May / Wildwood
   left out as in v3). ✅ the v4 6 h-cut wavemaker repeat PASSED (62734681: bit-identical; a resumed copy
   differs by up to 1.99 m at the Narrows — FINDINGS §44 (j)).
2. ✅ **Phase 4 arms REGISTERED (10-19; `nj_sfincs/experiments.py` PHASE 4 block, user choices 10-19):**
   v4_refreeze `p4-premier` (lower-only lake bed, `cnb` 1.5, ERA5 pressure in the blend, `snapbeach`
   wavemaker) + `p4-premier-repeat`, `p4-premier+wave-nowavemaker`, `p4-nowaves`, `p4-premier+rain-cnb1.0`
   / `2.38`, `bed-nobuildings+p4-premier`, `bed-breach-wreck0` / `-wreck165+p4-premier`,
   `p4-premier+src-deal-overtop` (old unseeded forcing, flagged), `null-rhoa1.2501` / `1.2499+p4-premier`;
   v3 `p4-ref` / `p4-ref-nowaves` (new names, the 10-11 runs stay). Horton DROPPED (user). New
   `Experiment.rhoa` (null arms); `experiments.reference_arm()` = the family premier (the bed test
   pairs against it). `--check`: 12/12 + 2/2 would stage. ▶ **62734605 `sbg_nobldg`** builds
   `_subgrid_refreeze_lakes_min_nobuildings` (~7 h; `logs/nobuildings_2026-10-19/`). ✅ PREREG drafted
   (`logs/rebaseline_2026-10-19/PREREG.md`). ✅ Job DRAFTED, NOT submitted: `logs/rebaseline_2026-10-19/phase4.slurm` + `pack_worker.sh`
   (ONE 2-node emeraldrapids job: stage 14 arms + checks → 4×16-thread slots per node via hpc/sfincs_run.slurm → each node
   validates its own arms; lists `node1.txt` / `node2.txt`; ~23 h solves, 40 h limit). Then: the
   2-node job (wavemaker repeat ✅ passed; ENGINE = the home copy
   `~/nj_sandy_sfincs/sfincs-native/v2.3.3-winddir-igk-igseed-wmseed-1-gf11/bin/sfincs` — the `/scratch/tpj8/sfincs-build/` dir holds
   no binary), desk checks (Atlantic City datum, paved channels).
3. **Run gallery (user 10-19):** a standard figure set per arm, made in the validate stage and
   collected into a static GitHub Pages site (per-domain arm table with flags, a page per arm, a
   two-arm compare page). Ready before the Phase 4 reads, so they land in it. Showcase site
   (10-19 meeting) = `~/sandy_flood_site`, builders in `logs/showcase_2026-10-19/`.
   🔴 **Depth convention (user 10-19; CLAUDE.md §6):** flood depth = water above the pixel ground,
   on NORMALLY-DRY land only (ground ≥ MHHW / lake pool), NOAA/NHC style; water bodies blank; a separate
   peak WATER-LEVEL map for water. (Briefly "drawn everywhere" — reversed by the user the same hour.)
   Reference ✅: `nj_sfincs/normal_surface.py` + `data/normal_surface_v4/` (VDatum MHHW, lidar lake pools).
   The gallery's zsmax map had used the face's LOWEST pixel as ground (rain films read as floods,
   Highlands bluffs as 5 m+): fixed to the face's mean ground. The showcase animation / tiles / SLR
   images ✅ REBUILT 10-19 evening on `normal_surface.normally_dry` (land only; builders
   `logs/showcase_2026-10-19/rise/`): premier peak 1,020.7 km² of normally-dry land ≥ 0.15 m; SLR +0/+2/+3 m
   708 / 1,733 / 2,168 km². Private page republished (v7). Unchased: 4.68 m on a few Absecon pixels.
   ✅ **Gallery BUILT 10-19** (`nj_sfincs/gallery.py`; job 62734964, 55 min, ~21 G peak per v4 arm / ~16 G v3):
   9 figures per arm (zsmax LEVEL, flood depth on normally-dry land via `normally_wet`, Δzsmax vs
   `experiments.reference_arm`, HWM map + scatter/basins, MOTF, gauges, gauge peaks, hm0) + run card + flags
   in `<run>/gallery/manifest.json`; HWM / MOTF reproduce every metrics.csv row (self-check in the manifest).
   Hook: `run_experiments.py` draws it after every validate (subprocess per arm, warn-only; `--no-gallery`).
   All 7 v4_refreeze + 6 v3 arms drawn (v3: no flood depth — no `normal_surface_dir`; 2 bed-v4fixes arms lack a
   gallery tif → HWM/MOTF skipped, flagged). ONE public site (user 10-19): the gallery IS
   `~/sandy_flood_site` = GitHub `tyfolino/sandy-flood-model` (Pages on `main` /), written by
   `scripts/publish_gallery.py` (default `--site`); ▶ USER commits + pushes. Re-draw: `scripts/build_gallery.py` /
   `hpc/build_gallery.slurm`. The meeting showcase lives on only as the private claude.ai page
   (https://claude.ai/artifact/NfCNKozVV3BzdKF4r7mpCw); its last land-only build is parked in
   `/scratch/tpj8/sandy_showcase_2026-10-19/` (builders `logs/showcase_2026-10-19/`).

Last updated: **2026-10-19** (evening) — Phase 4 arms registered + job drafted; the run gallery built (one
public site); depth convention + `nj_sfincs/normal_surface.py`; both 10-17 bed builds checked. Before: **2026-10-17** (end of day) — the seeded-engine test read (repeats bit-for-bit across machines; a
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

## Running (10-19)

- ✅ **62734681 `wm_repeat`** COMPLETED (3 h 07, halc075): BIT-IDENTICAL; resume read in FINDINGS §44 (j).
- ▶ **62734605 `sbg_nobldg`** (~15:00 → ~22:00): `_subgrid_refreeze_lakes_min_nobuildings`.
- ✅ 10-17 jobs read and closed: `igcap` (FINDINGS §44 (e); user keeps `snapwave_niter` 200), the inflow
  re-stage (swapped in; 10-06 copy = `_template_sealed_pre_inflows_2026-10-06`; the hand-step trap is in
  CLAUDE.md §5), `sbg_lakes_min` + `sbg_breach` (checked 10-19, FINDINGS part 4 (h)). Clean-up done
  (10-17 / 10-19, ~160 G incl. `_subgrid_refreeze_lakes`).
- 🔴 Side-by-side `engine_gate.py run` copies need `taskset` on disjoint cores (FINDINGS §44 (i)).

## ⭐ FINAL AUDIT → "the v4 premier is ready" (plan approved 10-15)

Plan: `~/.claude/plans/i-think-i-m-ready-warm-trinket.md`. User decisions 10-15: lakes = rule-based
flag + a documented-site breach SENSITIVITY arm (not in the premier); IG stays on, seeded; v3
reference re-run on the seeded engine; `cnb` stays the premier's infiltration (FINDINGS §59).

- **Phase 0–1 ✅ (10-15):** seed patch + Deltares issue draft (`docs/upstream/snapwave_igseed*`); NACCS
  originals in `~/nj_bight_durable/`; repo, scratch and home cleanup (scratch 713 → 438 G).
  🔴 USER: re-run `scripts/desktop_pull_backup.sh` once (first pull of `nj_bight_sfincs_data/`, 78 G) —
  in progress 10-17.
- **Phase 2 ✅ (10-17):** outcome B — seeded repeat STRICT across clusters, null perturbation diverges
  waves-on (FINDINGS §44 (d)–(e)); §44 / §45 rewritten; CLAUDE.md §5 RNG trap; the cap test says the
  amplifier is the coupled solve, not the cap (§44 (e)).
- **Phase 3 (code, no solves) ✅ except the open items below.** Done 10-15 → 10-19: inflow-wall split +
  re-stage; `cnb` (`Experiment.cnb_effective`, `ksat_v4_refreeze`); `naccs_blend_p_era5` (registered in
  `p4-premier`); lake audit + `lake_fix_v4` + `--overlay <key>:min`; `lake_outlet_blocked` flag; breach
  design (user 10-17: Wreck 0.0 m main + 1.65 m bracket, Mantoloking post-storm EAARL-B, n 0.025) +
  overlays + beds (checked 10-19); the Deal overtopping arm (`Experiment.extra_discharge`); metrics label
  round-trip, env lock, README; the Phase 4 arms + PREREG (10-19). Details: FINDINGS part 4 (h), git log.
  - ☐ **Coastal lakes start EMPTY:** `zsini` 0 vs normal pools ~0.5–0.65 m (Deal Lake bed 0.16–0.30 m
    under a 0.61 m surface) — rain first fills a dry basin. Candidate fix: the Overpeck mechanism
    (`sfincs_ini_regional.bin`) at each lake's pool — `data/normal_surface_v4/lake_pool_v4.tif` (10-19) now
    holds those pools. A template change (re-stage + diff) — user's call.
  - ☐ Optional, user's call: the open 7-ft Wreck Pond outfall pipe as a culvert (no drainage-file writer
    yet); with the channel open, 6129 is controlled by the pond's internal band at 2.27 m.
  - ☐ desk checks: Atlantic City datum, paved channels.
- **Phase 4:** ONE 2-node job on the seeded engine. Node 1: new premier (seeded + `cnb` 1.5 + ERA5
  pressure + moved inflows + lake-fixed bed) + its repeat + `bed-breach` + waves-off + `cnb` 1.0 / 2.38
  + `bed-nobuildings` + a waves-off Horton (`hor`) arm. Node 2: v3 reference pair + TWO full-length null
  copies of the new premier, `rhoa` 1.2501 and 1.2499 (user 10-17: the noise band THROUGH the peak as a
  spread, not one draw). All at `snapwave_niter` 200. Validate; paired reads. Must end
  before 11-10 08:00. **Wall budget:** the v4 premier took 10 h 05 on emeraldrapids (job 62328438;
  SnapWave 28,568 of 36,258 s; 18 capped calls × 539 s, 55 converged × 343 s); packed 4×16 about the
  same (packing test); niter 800 measured +12 % on the 6 h cut. On icelake ×3 → ~30 h, near
  the 40 h limit, and a TIMEOUT is not requeued (a hand-resume resets `cna` soil) →
  `SOLVE_CONSTRAINT=emeraldrapids`. 🔴 A preempted-and-RESUMED waves-on arm is a different run (FINDINGS
  §44 (j); dm at single gauges on the toy): check every arm's `restart_history.txt` before pairing, and
  re-run a resumed premier / repeat / `rhoa` copy rather than read it.
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
- **Atlantic City peak ~+0.5 m high on every run** (+0.47…+0.55). Close: NACCS at the nearest save
  point vs the gauge; the gauge's datum (Phase 3 desk check).
- **NY-bay waves-on crest = seiche phase** (§61 (g)): how much of the wave gain survives a fine
  `dtwave` is unmeasured (the dtwave-600 swing leg was never run).
- **Unread from the 10-05 pre-registration:** do the Maurice / Mullica / Tuckahoe / Rancocas reaches
  wet; hm0 vs depth at the SnapWave band's 53 boundary cells shallower than −20 m. Close: one read of
  the premier's map output.
- 🔴 **IG in the premier = computed, NOT coupled to the water (checked 10-17).** v4 and v3 premiers:
  `snapwave_igwaves = 1`, no `wvmfile`; IG then acts only by removing short-wave energy (§45). The
  user's supervisor wants IG ON (user 10-17) — in the sense of IG motion in the water that takes the
  wavemaker (§49: v3 `wave-wavemaker` lifted 6122 Deal Lake +0.27, 6124 +0.53, 6123 +0.29 m; open coast
  median +0.021; NY bays −0.049 re-ring). A v4 premier wavemaker needs: a v4 line
  (`build_wavemaker_line.py`), an engine with igk-fix + igseed + a SEED for the wavemaker's own
  random phases (`sfincs_wavemaker.f90:1322`, drawn once at init, unseeded), a repeat test, and a
  check of the IG phase across a restart. ✅ **User 10-17: the wavemaker goes INTO the new premier**
  (with a no-wavemaker arm beside it, so its effect is measured). In progress 10-17 (subagents): the
  engine ✅ `v2.3.3-winddir-igk-igseed-wmseed-1-gf11` (toy: repeats exactly; FINDINGS §44 (j)); ✅ the v4 line built
  (`data/wavemakers_v4/`, `logs/wavemaker_v4_2026-10-17/README.md`; on `_subgrid_refreeze` lev0, v3's rules:
  9 pieces / 140.6 km, within 1–3 m of v3 (median) on the shared coast, all checks pass; the
  re-freeze's dredged back-bay channels make v3's snap rule drop 4.5 km at Holgate → alternative
  `--snap-seaward-of-beach`: 8 pieces / 157.7 km, Holgate back + 3 old v3 gaps closed (Brigantine N,
  Longport, Sea Bright–Sandy Hook), 2 vertices fail the land test; Cape May / Wildwood oceanfront left
  out by v3's `--x-min 520000`, optional `alt/v4_xmin505.geojson`). ✅ user 10-19: the `snapbeach` line; then the
  v4 6 h-cut repeat (Camden). Arm: `replace(_V4_PREMIER_WAVES, wavemaker=True, wavemaker_line=…)`.
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

- Last cleanup: **2026-10-17** (the igseed partials, Camden duplicates and cap-test maps, the home
  staging copy: 120 G). Before: 2026-10-15
  repo + scratch + home (`reports/cleanup/deletion_manifest_2026-10-15.md`).
- Kept on purpose, user's call to remove: `data/NACCS/_originals_pending_delete/` (3.2 G — the only
  byte-reproducible source of v3's NACCS boundary, part 3; durable copy in
  `~/nj_bight_durable/NACCS_originals_pending_delete/` with `MD5SUMS`); `data/gtsm/retired_v1_monmouth/`;
  the v1.5 / v3 notebooks and the weekly reports;
  `logs/audit_v4_hot_plus_2026-10-05/v4_vs_v3_deficit/shadow_hp_norain/` (705 MB rebuildable floodmap).
