# STATUS — live campaign state

**Edit this file in place; keep it under ~300 lines.** It holds what is happening NOW: what is
running, what is next, what is open. When an item closes, its durable fact goes to
[FINDINGS.md](FINDINGS.md) (or CLAUDE.md §5 if it is a trap) and the item is deleted here.
Git has the history. The campaign log this file grew into until 2026-09-29 (6,767 lines) is
`git show d70dd1e:docs/STATUS.md`; FINDINGS cites it as "STATUS <date>".

Last updated: **2026-10-06 16:30 (end of day)** — overnight read: the harbour trench fixes Newark Bay but not
Raritan Bay (the Arthur Kill drain is ruled out); runs A / B solving ~3× faster than planned, both
validated tonight; the v3 re-run's Great Egg inlet fix restores the southern back-bay tide.

---

## Now

- **v3 is DONE** (2026-09-24). Reference `naccs-premier` on the repaired mask — HWM RMSE 0.329 /
  bias −0.143 (median, 50 m, n 94), MOTF CSI 0.706 / POD 0.880 / FAR 0.219. A re-run with the
  shared bed fixes is in flight (below); the reference stays until it is read.
- **v4 is DECIDED and RE-FROZEN (user 10-05):** rivers at today's head of tide (A+), waves 5° /
  hourly, buildings +10 m, frozen domain **`v4_hot_plus_walls`** (A+ + 11 leak walls + the
  Henlopen gap + 4 inflows in their channels; `77b5eda1fcd51cf6`). FINDINGS part 4 has the
  decisions and the audit. Its bed fixes are subgrid overlays; the final re-freeze bed adds the
  pieces still being built (below) and then re-baselines the premier.
- **Goal: first waves-on v4 results for Wednesday morning.**

## ☀️ PICK UP (Wednesday 10-07 morning)

1. `squeue -u tpj8` + `sacct -S 2026-10-06T16:00 -X`: rebuild 62308704 → the `v4_refreeze` stagings
   and solves (ids in `logs/refreeze_2026-10-06/v4_refreeze/README.md`); run B validate 62291413;
   the Wednesday read (report 62305023). `DependencyNeverSatisfied` = something upstream failed.
2. `v4_refreeze` checks in each arm's `sfincs.log`: "221 structure u/v points found"; the binary
   ini line (premier / nowaves); `fix_meteo_grid_origin.py --check` says fixed; fingerprint as
   registered; the `wind-naccs` arms' `sfincs_netamuv.nc` = `data/wind_v4/naccs_blend/`'s.
3. Read `reports/v4_first_results_2026-10-07/summary.md` (B vs A, v4 vs v3 re-run, harbour vs v3_off on
   shared marks). Flag the Keansburg pocket marks (6133/6155/6156: runs A/B had no levee) and the
   7 crest-hole gauges. Then the `v4_refreeze` scores: new reference + the NACCS-wind pair (Raritan:
   South Amboy obs 4.09; Barnegat — NACCS pushes south 0.38× ERA5, unrefereed).
4. Stage the `v4_refreeze` subagent's code once its suite is green (domain / experiments / premier /
   config / model / provenance / run_experiments / tests) — review the diff for any change to
   EXISTING domains first. Republish the brief (same file) with the morning's scores.
5. Next tests: the hourly-wave ±0.15 m swing (short window, finer `dtwave`); NACCS vs ERA5 pressure
   (`--pressure era5`); record the meteo convention in metrics/provenance.

## Tuesday 10-06 — the overnight read (10:45) and the day's list

**Overnight:** every chain staged; all solves on emeraldrapids, logs clean.

| run | state (10:45) | next |
|---|---|---|
| harbour test `v4_hot_plus/bed-harbour+naccs-nowaves` | ✅ solved + validated | read below; FINDINGS part 4 (e) |
| run A twin `v4_hot_plus/bed-buildings+bed-channels+naccs-nowaves` | ✅ validated | Wednesday read |
| run A `…+naccs-premier` | solving, **62289819** (hal0408), 54 of 72 sim-h; ~6–8 sim-h per wall-h | done ~13:30–14:00 → validate **62289820** |
| run B `v4_hot_plus_walls/naccs-premier` | solving, **62291412** (hal0441), 36 of 72 sim-h | done ~16:00–16:30 → validate **62291413** |
| run B twin `v4_hot_plus_walls/naccs-nowaves` | ✅ solved 08:03; validate **62291643** pending (Priority) | — |
| v3 re-run `bed-v4fixes+naccs-nowaves` | ✅ validated | read below |
| v3 re-run `bed-v4fixes+wave-dt3600` | ✅ solved (14 h 42); validate 62284068 PREEMPTED 10:39 → resubmitted **62304642** (`--requeue`) | — |
| data swap 62282097 | FAILED at `elevation_v4/enc`: scratch holds `raw_cohansey/` (written there by the 10-05 Cohansey build), so the strict listing diff refused. Everything before `enc` swapped; `enc`, `gmrt_v4.tif`, `inland_water`, `nj_10ft_dem_v4.tif.ovr` (~2.1 G) still on home. Home 67 G — not urgent | finish with a diff that allows dst-only files |

**Run A waves-on SCORED (16:xx):** HWM RMSE 0.565 → 0.501, bias −0.383 → −0.266 (median, 50 m,
n 110; waves-off twin → on), CSI 0.704 (admissible); wave lift −0.064 RMSE = v3's §48 −0.064.
Lift by basin +0.06…+0.23 (Raritan +0.15, Barnegat Bay +0.20, LBI +0.18); South Amboy 3.57 → 3.72
(obs 4.09). ⚠️ NY-bay lifts carry the hourly-wave swing. Solve 9 h 20 on emeraldrapids.
Pace is ~3× the 10-05 estimate (hourly waves; SnapWave calls 280–380 s), so both waves-on runs
are validated tonight, not Wednesday.

**Harbour test read (vs the 10-05 pre-registration):** Newark Bay ✅ (peak 2.99 → 3.50, obs 3.70;
range ratio 0.68 → 1.04; timing +67 → −6 min vs obs); Arthur Kill marks −0.58 → −0.25 (n 3);
open coast / Narrows < 1 cm ✅; the Arthur Kill flux REVERSES (+9.9 → −24.2 Mm³). **But South
Amboy 3.56 → 3.57 (predicted +0.2–0.4) and Raritan Bay marks −0.419 → −0.409 (predicted
+0.15–0.35)** ✗. The drain was not the Raritan cause → the Arthur-Kill-walled bracket is moot
(the Kill already flows the other way). v4's harbour-side gauge peaks sit 5–6 cm under v3's
(Sandy Hook, AK mouth, Great Kills); the basin-bias gap to v3 (−0.41 vs −0.20) mixes different
mark sets → read it PAIRED on shared marks (Wednesday preset).

**v3 re-run, waves-off twin (vs `naccs-nowaves`):** HWM RMSE 0.393 → 0.382, bias −0.246 → −0.250
(median, 50 m, n 94); CSI 0.697 → 0.705. Great Egg inlet fix is large: Great Egg tide range 0.70
→ 1.31 (obs 1.23), Ocean City 0.74 → 1.34 (obs 1.13), peaks −0.34/−0.41 → −0.13/−0.14; absecon
basin +0.12. Inside Thorofare is now TIDAL (range 0.12 → 1.42, obs 1.22); its "+0.44 m peak" is
an obs artefact (the crest falls in the §60f hole; 7 gauges lack `record_ends` — FINDINGS §60f).
`great_bay_mullica` −0.08 → −0.25 is TWO marks (6066 +0.75 → −0.19, 6053 +0.13 → −0.48): the
`riverbeds_gmrt_v4` carve removed a GMRT plug (+2.8…+3.9 m) behind which v3's no-infiltration
rain ponded — −0.25 is the honest number (= the §57 deficit); NOT the lakes overlay (no lake pixel
within 3 km). Barnegat / south_coast rain-pond marks sit by no lake-overlay pixel either
(`logs/morning_2026-10-06/per_mark/`). Predict for B twin vs A twin: 6066 falls, 6053 rises.

**Today, in order:**
1. ✅ **USER decisions (10-06):** (a) a 1.2 m-below-MLLW FLOOR on the guessed (slope) tier only —
   measured tiers keep their values; (b) ADD the damped fill-bed tidal reaches of the screen
   (Wading/Bass, Murderkill, Alloway, Salem R., Dividing, Great Egg Harbor R., Cedar/Nantuxent,
   Broadkill, Overpeck, Appoquinimink/Blackbird, Leipsic–Smyrna; NOT the Salem/Pennsville shore
   polygon or the Mispillion, already tidal); (c) KEEP marsh n (NLCD 90/95) on tidal polygons —
   0.02 stays on lakes, non-tidal rivers and the developed-class overrides; marsh n is ALSO kept on
   the 20.5 km² of tidal-looking LAKE polygons (marsh pools; user 10-06). Subagents building
   (a)+(b) (`bed_hierarchy/`) and (c) (`roughness/`). (a)+(b) ✅ DONE: `riverbeds_hierarchy_v4`
   rebuilt, 32 reaches, 48.52 km² (eHydro 0.75 / CUDEM 0.58 / chart-NOS 13.25 / slope 33.94);
   md5 list `bed_hierarchy/riverbeds_hierarchy_v4.md5`. ❓ USER: the floor also fills 12.6 km of
   gaps BETWEEN two measured stretches (pockets deeper than both neighbours: Overpeck, Lewes,
   St Jones) — rec. limit it to runs ending at a head of tide; Overpeck: tide gate? The screen
   mislabelled 120006713 (= Alloway) / 120006724 (= Stow Creek); Salem River (120006699) stays out. (c) ✅ DONE: `manning_water_v4.tif` rebuilt (painted 580.7 → 486.9 km²; n
   changes on 58.5 km²; check clean; old raster `/scratch/tpj8/manning_water_v4_old_2026-10-05/`).
2. ✅ **Wednesday read SUBMITTED** with the v3 re-run pairs, harbour vs `Aplus_base` / `v3_off`, and
   B vs the v3 re-run (on + off): 21 jobs `62305002`–`62305022` (afterok on 62289820, 62291413,
   62291643, 62304642), report **62305023** → `reports/v4_first_results_2026-10-07/`. No
   `--requeue` on these: a preempted residual job shows up as "missing" in the summary.
3. ✅ Per-mark read DONE (above). Follow-up: add `record_ends="2012-10-29 03:54"` (or a crest-hole
   flag) to the 7 gauges in `_V3_USGS_GAUGES` — no fingerprint change; after the queued jobs start.
4. After run B validates: park run B under `_pre_refreeze/` + its KNOWN fingerprint; apply the
   Lewes edit as an override on `V4_HOT_PLUS_WALLS` only (test 62283012: invariants OK, active
   3,965,068 → 3,965,303 (+235), 61 sources active, SnapWave band −4 cells, new sha
   `378014e154b4ff41`); move the `usgs_tidal_absecon_creek` obs point off its +2.92 m face.
4b. **Raritan Bay low (calm-water, ~0.5 m at the west end):** v3 forced NACCS at the Arthur Kill
   mouth, v4 doesn't (FINDINGS part 4 (e)). Subagents: a toy-basin wind-setup test of our engine
   (`logs/raritan_2026-10-06/wind_setup_toy/`) and SnapWave vs NACCS/STWAVE bay waves
   (`logs/raritan_2026-10-06/waves_vs_naccs/`). Then one targeted waves-on bracket run.
   ✅ Toy test DONE: the engine reproduces analytical wind setup (0.99–1.02×), but 🔴 its
   `netamuv`/`netamp` reader shifts every wind/pressure sample ~12.5 km W + 12.5 km N (half an
   ERA5 cell; FINDINGS 'NOT wind-limited' entry) — applied stress 0.73–0.86× in the NY bays, in
   EVERY run. v4's ~0.18 m Raritan tilt ≈ what that wind can build; the rest of the ~0.67 m is
   forcing (wind strength + wave setup), not the solver. ❓ USER: fix it (write half-cell-shifted
   coordinates, verify with the toy `probe_lin` → zero shift) and fold it into the re-baseline?
   ✅ Waves vs NACCS DONE: the bay's missing push is mostly WIND (ERA5 0.63–0.72× NACCS along
   the axis; NACCS = observed at Robbins Reef), waves second (SnapWave hm0 ≈ 0.65× STWAVE; +0.05–0.1
   m). Hourly wave updates make a ±0.15 m bay swing (§40's waves-on ringing?). FINDINGS part 4 (e).
   🔜 **Better wind (user 10-06):** subagent scoring ERA5 (true positions) vs RAP 13 km, NAM 12/4 km,
   RTMA 2.5 km, H*Wind, NACCS save-point winds against over-water stations + buoys
   (`logs/wind_products_2026-10-06/`); it will name the NACCS OFFSHORE save points the user
   should fetch from CHS. ✅ DONE: no gridded product helps over the bays; rec. a BLEND — NACCS
   save-point u, v, p on a ~0.5–1 km grid inside the domain, tapered into ERA5 (true positions)
   offshore → a `wind-naccs` arm beside the ERA5 baseline (user 10-06: YES; subagent building
   `nj_sfincs/meteo_blend.py` + `data/wind_v4/naccs_blend/`; user fetching the CHS points). USER to fetch
   from CHS (`logs/wind_products_2026-10-06/naccs_fetch_list.csv`): SP05387, SP06904, SP13201
   (min; near buoys 44009 / 44065 / 44025) — 15 for the full set; optional 58 shelf points.
**🌙 Tonight (user 10-06 evening): NEW domain `v4_refreeze`** (= `v4_hot_plus_walls` + Lewes; run B
untouched for the Wednesday read) on `_subgrid_refreeze` + ERA5-bilinear meteo + weirs (Keansburg +
Overpeck dam + bypass sill, expect 221 structure points) + Overpeck pool start −1.005 m + obs fixes;
arms `naccs-premier`, `naccs-nowaves`, SLR gate +0/+2/+3, and `wind-naccs` on/off if the blend is
ready. Subagent registering + staging (`logs/refreeze_2026-10-06/v4_refreeze/`). CHS points (436,
incl. SP05387 by 44009): `data/NACCS/naccs_chs_2026-10-06.zip`. Brief: `reports/weekly_2026-10-06.html`.
5. **Tonight's re-freeze (user 10-06: floor only on runs ending at a head of tide; Overpeck cut at
   its Ridgefield tide gate — being verified; FIX the meteo half-cell shift and fold it in):**
   ✅ Hierarchy revised (47.93 km²; floor on head-of-tide runs only; Overpeck cut 125 m below the
   OVERPECK TIDAL DAM, NJ00799, Ridgefield, crest ~1.7 m NAVD88 — overtopped by Sandy; user 10-06:
   model it as a WEIR. 🔴 v4 had silently DROPPED v3's Keansburg levee weir (FINDINGS §38) —
   runs A / B score pocket marks 6133/6155/6156 ~+1.7 m (6155 is a headline mark): flag it in the
   Wednesday summary. ✅ `data/structures_v4/sfincs.weir` (Keansburg + Overpeck 1.74 m) copied into
   `data/frozen_mesh_v4/`; at restage also copy it into the template + `weirfile` key, expect
   "216 structure u/v points" (re-predict on `_subgrid_refreeze` with `structures/weir_on_mesh.py`).
   ❓ Overpeck: the subgrid opens a BYPASS round the dam at 0.84 m (lidar divide 1.30–1.37 m;
   Hackensack MHHW 0.77) and the pool starts at 0 m vs its normal −1.0 m. **REBUILD SUBMITTED 62308704** —
   `logs/refreeze_2026-10-06/submit_rebuild.sh` → `_subgrid_refreeze` on
   `v4_hot_plus_walls`: buildings cap10 → lakes → unpave → harbour → Raritan-corner surveys →
   back-bay unpave → Sayreville → Little Egg → `riverbeds_hierarchy_v4` LAST; `--manning-overlay
   manning_water_v4`. 🔴 Its md5 guard covers `nj_sfincs/domain.py`: the Lewes override waits
   until the rebuild job STARTS. ✅ Meteo fix DONE (`nj_sfincs/meteo_grid.py`, applied in `finalize`;
   13 new tests, suite 256 OK; real engine now samples at +0.0 / −1.7 m): at restage run
   `python scripts/fix_meteo_grid_origin.py --era5-bilinear experiments/v4_hot_plus_walls/_template_sealed`
   (user 10-06: YES, ERA5 bilinear on a 5 km UTM grid; hydromt's own regrid is nearest-neighbour). To do:
   record the meteo convention in `metrics.csv` / `provenance.txt` (like `snapwave_direction`). Then re-baseline (freeze run B's rows, park run B, repoint
   `naccs-premier`), waves-on + waves-off + SLR gate.
6. Finish the data swap (above).

**Read plans still open (pre-registered 10-05):**
- **Runs A / B:** the wave lift = waves-on − twin (v3: −0.064 m RMSE); Raritan / Newark Bay
  should read the harbour fix; the Maurice / Mullica / Tuckahoe / Rancocas reaches should wet
  (B only). Check: the SnapWave band's 53 boundary cells shallower than −20 m (to −12 m, the
  southern E–W step) — hm0 there vs depth (depth-limited breaking at the boundary?).
- **v3 re-run waves-on:** as the twin above, plus the wave lift vs `wave-dt3600`.

**Wednesday read — `scripts/v4_first_results.py`** (built + tested 10-05; reproduces metrics.csv
and §48's v3 ΔRMSE −0.0640 [−0.0859, −0.0424] exactly): `plan --preset wednesday` (read-only) →
`submit` → `reports/v4_first_results_2026-10-07/summary.md`. v4 residual jobs ~211 GiB each, one
run per job. B − A differs in bed AND mask AND inflows; CSI is not comparable across domains.

**Bed hierarchy (DONE 10-05):** `riverbeds_hierarchy_v4` (18 tidal reaches, 29.6 km²) REPLACES the
Cohansey, GMRT and tidal builds (+ `_shaped`); paint it LAST. `riverbeds_hierarchy_tier_v4.vrt`
is provenance, NOT a bed — never `--overlay` it. Premier-tier inconsistencies
(`premier_tiers.csv`): `riverbeds_v4` form (flat), `usace_nj_2010_v3` over 4.8 km² of real CUDEM,
`coned_sw_raritan` east of −74.25. Paerdegat: leave it (user).

## The re-freeze — what is left (`reports/v4_refreeze_list_2026-10-05.md`)

**In progress (subagents, 10-05 PM; notes under `logs/refreeze_2026-10-05/`):**
1. ✅ **Roughness overlay route DONE** (`roughness/README.md`): `rebuild_subgrid.py
   --manning-overlay <key>` (byte-identical without it; only the uv n-tables move with it;
   `tests/test_rebuild_subgrid.py`) + `manning_water_v4` (catalog; n 0.02 on all NHD water in the
   ring, 581 km² painted, n changes on 152 km²). ❓ USER: keep 0.02 on the ~94 km² of tidal marsh
   creeks NLCD calls marsh / woody wetland? **Schuylkill:** the whole 4.8 m excess is the first
   3 km below the dam, exactly where the bed is CUDEM's ~0 m fill (then −7…−11 m); 1-D backwater
   needs n ≳ 0.06 for 6.8 m, n 0.02 gives ~3.1 m — roughness AND the fill bed; fix both (the
   reach joins §2's "CUDEM ~0 m on tidal rivers").
2. ✅ **Bed candidates DONE** (`bed_candidates/README.md`; catalog keys added):
   `usace_unpave_backbay_v4` (11 laser-paved back-bay channels/basins, none are bridges; 9 more
   patches are beach / inlet shoals → keep the 2010 bed), `riverbed_sayreville_v4` (2012 survey +
   H05647, within 4 cm of the 2012 survey), `littleegg_channel_v4` (NOAA H12597 2014 agrees with
   the 2024 eHydro to 0.35 m — CUDEM missed a 5–14 m inlet channel; IN per the hierarchy,
   eHydro first). Rahway mouth: no material → the slope rule. No raster needed: Cape May Pt
   (marginal), the "Trenton crossing" (a sand-and-gravel pit), the C&D "ridge" (a spoil dike),
   the DE borrow pit. ❓ USER: **Lewes ring edit** (edge ~250 m east so the Lewes–Rehoboth canal
   isn't cut off, 0.92 km²) and optionally move `jamaica_wall_mid` west of Paerdegat.
3. ✅ **Tidal carves DONE** (`tidal_carves/README.md`): `riverbeds_tidal_v4` (catalog) —
   Christina (NOS H10042 1982, then −2.11 m; 1.17 km²), Big Timber (NOS H09886 1980; branches
   −2.17 m; 1.26 km²), St Jones (stated −2.09 m; 1.56 km²; the real channel at Lebanon is
   narrower and deeper). **Shaped-section OPTION** (catalog `*_shaped_v4` keys; each REPLACES its
   flat twin): natural sections here average 0.55–0.65 of their deepest depth, so depth below
   MLLW = d_c·(1−(1−ξ)^1.5); area below MLLW Maurice −33 %, Christina −37 %, Big Timber −33 %,
   Rancocas −21 %, Mullica −16 %, Tuckahoe −5 %, stated-depth reaches unchanged. ❓ USER: adopt
   shaped? (rec. yes). Minor: St Jones MLLW −0.890 vs −1.011 (cross-bay pair); Big Timber
   branch heads may still be tidal (+1.1–1.5 m lidar water vs MHHW 1.09) — unpainted.

4. **ONE bed-source hierarchy (user 10-05 evening; no sensitivity test):** eHydro → real CUDEM
   → NOAA charts / NOS → sloping-river approximation (shaped section). Subagent building
   `riverbeds_hierarchy_v4` (`bed_hierarchy/`) to REPLACE the 10-05 Cohansey / GMRT / tidal
   builds in the final bed, plus a consistency report on the premier's own tiers.

**Then (main session):** the final overlay list (cap10 buildings; lakes; every channel fix; the
new pieces; manning) → rebuild on `v4_hot_plus_walls` → **re-baseline**: freeze run B's rows
as `metrics_<date>_pre_refreeze_rebaseline.csv`, park run B's dirs, point `naccs-premier` at the
final bed (never repoint it silently) → waves-on + waves-off + the +0/+2/+3 m SLR gate.
**After run B stages (~21:00), not before** (its template audit checks obs points): move the
`usgs_tidal_absecon_creek` obs point off its +2.92 m face (Inside Thorofare's +3.47 m face is the
2010-lidar paving, fixed by the unpave overlay — confirm on run B's bed).

**Fix-material registry (catalog keys, all overlays):** `bed_buildings_v4` (+4) /
`bed_buildings_v4_cap10`; `inland_water_bed_v4` (85 lakes + 2 rivers, 5.16 km², bed only;
user's four calls); `usace_unpave_v4` (`build_usace_unpave_v4.py`, 3 boxes);
`ehydro_harbour_v4` / `ehydro_refreeze_cenan_v4` (`download_ehydro_v4.py --set …`);
`riverbed_cohansey_v4` (`build_riverbed_cohansey_v4.py`; −2.14 m); `riverbeds_gmrt_v4`
(`build_riverbeds_gmrt_v4.py`; ENC / NOS H06254+H06218 soundings, else 1.2 m below MLLW from
on-river CO-OPS stations; `logs/bedfix_2026-10-05/gmrt_reaches/`). Paint order: buildings →
lakes → channel fixes (later wins). Run B's discharge file: `usgs_sandy_discharge_v4_hot_plus_walls`.

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
| **`v4_hot_plus_walls`** | **THE re-frozen v4** (10-05) | same / `77b5eda1fcd51cf6` | run B (to be re-baselined) |

## Open questions (each with what would close it)

- **Southern back-bay deficit (§57):** mechanism unknown; the Great Egg inlet sill (FINDINGS
  §54 h) is now a candidate share. Close: the v3 re-run's Great Egg / Ocean City pre-storm
  bay-minus-pier; the calm-month datum check of the seven southern USGS stations.
- **NY east bay ~0.2 m low after the repair (§50);** `lower_bay_si_shore` (n 3) keeps moving the
  wrong way; the cross-Narrows tilt at `sss_narrows_bkln`. Close: per-mark and Narrows Q(t).
- **Great Kills sensor offset cause (§50).** Close: USGS STN deployment / survey records.
- **12 USGS gauges empty over the storm day (§60f).** Close: NWISWeb 2012 / the USGS Sandy report.
- **Atlantic City peak +0.47 m high on v4 waves-off.** Close: the v3 premier's AC `peak_err`,
  then NACCS at the nearest save point vs the gauge.
- **IG on the premier costs ~4 h with no wavemaker (§45).** Close: user decision.
- **Waves ON ring the NY bays 3–5× more than waves-off** (> 1 h std 0.045–0.076 vs 0.012–0.021
  m; `logs/wave_cost_2026-10-01/ig_seiche_check.txt`) — how much of the NY-bay waves-on gain is
  `zsmax` sampling a seiche is unmeasured (§40); hourly updates add +0.04 m there (§61a).
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
| SLURM stdout | `logs/slurm/<yyyy-mm>/` | — | — |

## Disk and cluster

- **Home** (`/cache/home`, GPFS): 100 G soft / 110 G hard; **67 G on 2026-10-06** (after the partial data swap; 93.4 G on 10-05) after moving
  the 10-05 audit intermediates to `/scratch/tpj8/nj_bight_sfincs/logs_offload/` (symlinked back);
  the data swap (above) takes ~29 G more off. Ask `/usr/lpp/mmfs/bin/mmlsquota -u $USER
  --block-size auto cache` (lags ~10 min).
- **Scratch** (`/scratch/tpj8`): 1 T soft / 2 T hard. 🔴 **Not backed up; files not accessed for
  90 days are deleted.** `experiments/` and now most of `data/` live here; the durable copy is
  the desktop pull (`scripts/desktop_pull_backup.sh`) — re-run it whenever an arm is scored.
- **Attic:** `/scratch/tpj8/nj_bight_attic_2026-09-30/` (manifest lists every file; purges
  itself after 90 days).
- **Maintenance:** every hal/halk node, 10-13 08:00 → 10-14 23:59, then 11-10 and 12-15.
- Claude Code may run on a LOGIN node (`amarel*`): heavy work through `srun` on an allocation.

## Housekeeping

- Last cleanup: 2026-09-30, `reports/cleanup/deletion_manifest_2026-09-30.md`.
- Kept on purpose, user's call to remove: `data/NACCS/_originals_pending_delete/` (3.2 G — the
  only byte-reproducible source of v3's NACCS boundary, FINDINGS part 3);
  `data/gtsm/retired_v1_monmouth/`; the v1.5 / v3 notebooks and the weekly reports;
  `logs/audit_v4_hot_plus_2026-10-05/v4_vs_v3_deficit/shadow_hp_norain/` (705 MB rebuildable
  floodmap, on scratch; user 10-05: keep for now).
- Candidates for the user (10-05, not deleted): `data/elevation_v4/inland_water/
  inland_water_bed_v4_draft.tif` (byte-identical to the registered `inland_water_bed_v4.tif`);
  `data/discharge_v4/usgs_sandy_discharge_v4_hot_plus.nc` will carry the 4 inflow moves after
  job 62279940 (only a future A+ restage reads it).
