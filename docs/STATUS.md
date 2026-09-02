# STATUS — live campaign state

**Edit this file in place.** Git has the history. This replaces the previous project's
12 KB "current state" memory file and its 26 reverse-chronological campaign logs; the point
of the format is that a reader gets the current state without replaying how it was reached.

Last updated: **2026-09-02** (rain-off arm `diag-premier-norain` registered on v3 and RUNNING, solve 61190532 → validate 61190533 — see the 09-02 section; 2026-09-01: ⭐ v3 REBUILD LANDED AND RE-SCORED — three arms clean on
hal nodes, premier 4/4 on the new fingerprint, merged dep rebuilt, HWM RMSE
0.384/0.400/0.431, extent unchanged; bay SnapWave setup HALVED and the v3↔v1.5 Monmouth
offset is GONE (sign-test P 0.011 → 0.152), Sandy Hook tide-range gap healed
(−0.40 → −0.04 m); waves-on vs off paired ΔRMSE −0.046 [−0.072, −0.017] — see the 09-01
section; 2026-08-31: 🔴 v3 MESH REBUILD — the bay-side 25 m
refinement bands were silently dropped from `refinement_v3.geojson`; restored verbatim,
old v3 runs void by decision, see the 08-31 section. Also: Monmouth HWM overshoot vs
v1.5 traced to SnapWave setup; v3 results notebook
`notebooks/v3/sandy-v3-viz-2026-08-29.ipynb` executed — v1_5-viz layout on the three v3
arms, GIFs embedded statically; `V3.plot_window` + `map_windows` added in `domain.py`,
plot metadata only, 89 tests OK; 2026-08-27: ⭐ ALL THREE v3 ARMS COMPLETED CLEAN on hal nodes, 4/4 premier OK, HWM 6044 src-flagged, FIRST v3 SCORES in (premier HWM RMSE 0.355 / CSI 0.828; quota hit hard limit mid-validate, reclaimed); 2026-08-26: ⭐ v3 FROZEN, 25 gauges + 17 basins wired, 3 arms staged+submitted overnight, offline VDatum grids, STWAVE wave file; levers restored, subgrid 30 GB/1 h, dam sweep closed; 2026-08-25: ⭐ v3 PRE-FREEZE PASS: levers pulled (−1.3%, the driver is the 25 m surf band), dam sweep → 4 candidates, VDatum fallback, build-QC notebook; SUBGRID MEMORY PROBE running — see PICK UP; 2026-08-24: v3 WIRED + ALL DATA PULLED + CLEAN MESH PROBE 3.31 M faces — Steps 0–2 done, see PICK UP; earlier: MOTF sheet, inland ring, canal uncut; v3 REGION DRAWN + GATED — `region_v3_EDITED.geojson`
passes `validate_region_v3.py`; ⭐ `acquisition_only` domain state, v3 REGISTERED, all
five+one downloaders domain-aware, **v3 DATA ACQUISITION COMPLETE** (4.2 G);
Toms River src moved onto its cut · 🔴 **PAUSED ON A SCOPE DECISION: the ring currently
excludes Mays Landing and Batsto and that is NOT accepted** — see PICK UP · 2026-08-21:
seiche FINDINGS §40 · weir FINDINGS §38 · rain FINDINGS §39)

## ⏳ PICK UP — next session

### ⏳ 2026-09-02 — v3 RAIN-OFF arm registered, staged and RUNNING (solve 61190532 → validate 61190533)

**Ask (user):** the v3 premier with rain off, to see what it does to CSI. Registered as
`diag-premier-norain` on v3 (same name as the v1.5 diagnostic so
`scripts/measure_rain_share.py` runs unchanged with `NJ_DOMAIN=v3`): premier waves,
water level, wind, pressure, rivers verbatim; `Experiment.rain=False` makes `finalize`
drop `netamprfile` from `sfincs.inp` and unlink the copied `sfincs_netampr.nc` — written,
not merely not-written, the waves-off lesson. `--check` passes on the sealed template
(`5ad01a84978a87f8`). Tests +6 (rain declared/stripped/staged; metrics merge).

**Pre-registration (before the scorer runs).** MOTF is a surge-only extent, so rain-fed
wet pixels are false alarms the reference cannot contain; on v1.5 75.7% of premier FA
was rain-true (FINDINGS §39). Predict, premier → norain: `motf_far` DOWN by roughly the
disconnected-FA share (`motf_far_disconnected`), `motf_pod` ≈ unchanged or slightly
down (rain-triggered marginal cells), `motf_csi` UP; HWM RMSE ≈ unchanged at coastal
marks, worse at any rain-fed inland mark. Waves are ON, so `extent_admissible=True`;
but rain-off is a diagnostic, not a candidate — Sandy's rain happened. A CSI gain here
measures the reference's blind spot, not model skill.

**Disk, then launch.** Home was 102.4 G / 100 G soft / 110 G hard. Reclaimed: the
score-banked retired v1.5 dirs `noaa-2node`, `preweir-naccs-premier`,
`preweir-naccs-nowaves` (Claude, −2.4 G net — inputs were hard-links) and the three
regenerable `experiments/v3/floodmaps/*.tif` gallery copies (user, −7.0 G; the notebook
reads each arm's own `floodmap_hmax_lev3.tif`, which stays). Checked and NOT useful:
`v1_monmouth/faber-waves-premier` is already a hard-link of the archive (nlink 2);
`data/v2_barnegat_runs` is a symlink INTO the read-only archive; `dedupe_home.py` finds
nothing. User has authorised deleting the live v1.5 `sfincs_map.nc` files (1.3 G) if
needed — not done.

**Launched 14:27 via `sbatch hpc/stage_and_submit_v3.slurm diag-premier-norain`**
(job 61190511, hal0139): quota guard saw 18 G headroom; staged; `[rain] OFF` logged;
`dedupe_experiment_inputs --apply` linked 13 files, −9.8 G → 91.8 G; solve **61190532**
on hal0305 (12 h / 64 G, `sfincs-desktop.sif` explicit, ~5 h expected); validation
**61190533** `afterok` on it (128 G, `--validate-only`, merges its row into
`metrics.csv`). Staged deck verified: no `netamprfile`, no `sfincs_netampr.nc`,
provenance says precipitation ABSENT; on-disk rain-off test passes.

⏳ **NEXT (09-03 morning):** `sacct -j 61190532,61190533 --format=JobID,NodeList,State,Elapsed`
(no halk; if the validate job shows DependencyNeverSatisfied the solve failed — read
`logs/sfincs_61190532.out`); three clocks on the outputs; quota; then read the
`diag-premier-norain` row in `experiments/v3/metrics.csv` against the pre-registration
above, and `NJ_DOMAIN=v3 python scripts/measure_rain_share.py` for the FA rain share.
Gallery tifs for the other three arms are gone until a full `--validate-only` regenerates
them (7 G — check quota first); `report.html`'s gallery is empty for them meanwhile.

### 🔵 2026-08-31 — Monmouth/Sandy Hook Bay HWMs read HIGHER in v3 than v1.5: REAL, and it is SnapWave SETUP, not seiche phase

Asked by the user off the v3 viz notebook (premier median −0.08 vs v1.5's low bias in
Monmouth). Measured premier-vs-premier on the 46 marks scored in BOTH domains (same
estimator/radius as `hwm_metrics`, via the `paired_hwm_bootstrap.residuals` mirror):

- **Paired, it is real.** v1.5 median residual −0.108 vs v3 +0.064; mean paired delta
  +0.122 m. Monmouth-side basins (sandy_hook_bay / shrewsbury_navesink /
  atlantic_oceanfront / south_coast / shark_river): **18 of 24 marks up, sign-test
  P = 0.011**; sandy_hook_bay mean delta +0.52 (4/4 up, min +0.35).
- **Not a seiche/tide phase change.** Pre-storm tide at the 8 shared his stations is in
  phase to < 10 min (the output interval); the surge peak arrives 10–80 min *earlier*
  in v3, and the v3−v1.5 difference series is a peak-shape dipole, not a phase flip.
- **The mechanism is SnapWave setup.** Waves-OFF the two domains agree at the bay
  stations (Sandy Hook −0.10, Great Kills −0.16, Sea Bright storm tide +0.00 peak
  delta); premier differs +0.44 / +0.46 there. Setup at the peak (premier − nowaves):
  **v1.5 ≈ 0 in the bay** (Sandy Hook −0.03, Great Kills −0.10) vs **v3 ≈ +0.5 m**
  (Sandy Hook +0.51, Great Kills +0.52, Narrows +0.36; Sea Bright only +0.14).
- **Not the wave forcing.** `snapwave.{bnd,bhs,btp,bwd}` at the 7 shared northern
  points are near-identical at the peak (Hs within ~0.2 m, same Tp and direction);
  `sfincs.inp` identical except `latitude` and weirfile line order. The extra setup is
  generated on the mesh — v3's coarser bay refinement (≈50 m vs ≈36 m mean face in the
  Sandy Hook Bay box), the ring-wide 25 m surf band, and a wave boundary spanning the
  whole shelf (36 pts vs v1.5's 7 on 25 km). Bay-interior `hm0` max median:
  raritan_bay_mid 0.82 (v1.5) → 1.27 m (v3).
- **Verdict vs obs is mixed, so this is not simply an error:** Great Kills −0.53 →
  −0.07 (much better), Narrows +0.07 → +0.24/+0.37 (worse), Arthur Kill mouth −0.16 →
  −0.39 (worse), Sea Bright storm tide −0.60 → −0.53 (low in both).
- ⚠️ 23 of the 46 common marks are lev3-UNCOVERED on v3 (scored off the merged fill —
  a sampling change riding on the hydro change; the raritan_bay per-mark scatter,
  −1.34..+1.08, is dominated by these). The station-based conclusion uses the his
  files only and does not depend on them; covered-only Monmouth deltas hold
  (+0.38 sandy_hook_bay, +0.14 shrewsbury_navesink).
- Unexplained side observation: v3 premier's pre-storm TIDAL RANGE at the shared
  stations is smaller (Sandy Hook −0.40 m vs v1.5, but only −0.13 waves-off) —
  setup raising the low waters is the suspect; worth a look beside §40.

🔴 **Follow-up (same day, user: "resolution should be the same in v1_5 and v3"): it is
NOT, and the difference was never decided.** `refinement_v3.geojson` carries v1.5's
L2 50 m rule ring-wide (`low_water` = "v1.5's bay_water, ring-wide") and the ocean-shore
25 m `surf_dune_*` buffers + the two cuts — but v1.5's OTHER three overlap-region
polygons are absent: **`bay_fringe` (25 m on the bay margin, −1..+2), `shrewsbury_navesink`
(25 m through the behind-barrier estuaries), and `coastal_corridor` (50 m)**. The written
plan said the opposite — Step 2 (STATUS) and FINDINGS §38 both say *raise* the
`bay_fringe` zmax past 2.0 (the Keansburg lesson), not delete the band. Measured at the
marks: 6154 / 6153 / 6142 / Navesink cluster sit on ≈25 m faces in v1.5 and ≈51 m faces
in v3; this is exactly why 23 of the 46 shared marks are lev3-uncovered on v3 (the
merged-dep fix SCORES them correctly — the mesh under them is still coarser), and it is
a concrete, unplanned candidate for the SnapWave-setup difference above (bay-margin
breaking resolved at 50 m vs 25 m).

🔴 **DECIDED (user, 2026-08-31): the v3↔v1.5 bay numbers are NOT comparable and the mesh
gets REBUILT with the bands restored before anything else moves.** The paired bootstrap
(NEXT #2) waits for the new runs. `bay_fringe` restored **VERBATIM (zmax 2.0)** — the
user chose exact v1.5 parity over the §38 zmax raise; comparability is the point of the
rebuild (the berm-crest raise can be its own deliberate change later). Campaign, in order:
1. ✅ `refinement_v3.geojson` → 23 polygons: `coastal_corridor` / `shrewsbury_navesink` /
   `bay_fringe` appended verbatim from `refinement_v1_5_raritan.geojson`, `why` fields
   carry the restore note. 89 tests OK.
2. ✅ Disk: `experiments/v3/floodmaps/` (7.0 G, regenerable) deleted; `metrics.csv` banked
   as `metrics_2026-08-31_pre_refinement_rebaseline.csv`. Quota 94.4 G of 100 G.
3. ✅ Probe on the restored recipe: **FACES 3,412,470 (+99,903 / +3.0%) · active
   1,764,488 · mask==2 6,836 (ocean arm 1,156, +1 cell, in range) · outflow 1,961 ·
   every invariant OK · 25 obs points.** The NACCS boundary file needs no rebuild —
   support interpolates onto the mask==2 line at staging.
4. ✅ Subgrid build job **61095299, hal0121, 1:02:51, peak RSS 24.4 GB, exit 0**;
   three-clock test clean. Adopted by `mv` → `data/frozen_mesh_v3` (old mesh deleted at
   adoption); `keansburg_weir.weir` copied in (staging re-adds the inp key);
   `sfincs.obs` written by `build_static` itself (gauges wired since 08-26).
   **`premier.V3` = (3412470, 4108, "5ad01a84978a87f8")**, 89 tests OK. Audit now reads
   the old template + three 08-27 arms as UNRECOGNISED — correct, they are void.
5. ✅ (completed 2026-09-01 — runs, checklist, merged dep, re-score and paired
   comparisons all in the 09-01 section.) Template deleted deliberately (9.3 G);
   staging job 61098904 **FAILED at 5 min on
   quota** — the hard 110 G limit, mid-copy of wave-stwave (the template build itself
   completed and its fingerprint verifies against the new `premier.V3`). ⚠️ The staging
   transient is ~3 full template copies BEFORE `dedupe_experiment_inputs` runs; budget
   ~25 G free, not ~10. Reclaimed to **79.6 G**: the three arm dirs deleted (one partial,
   two void old-mesh) + `dedupe_home.py --apply` (5.7 G — the new template vs
   `data/frozen_mesh_v3` duplication). **Resubmitted as job 61102453** — re-stages the
   three arms from the verified sealed template, dedupes, submits the solves
   (`--time=30:00:00 --mem=180G`, sif explicit). Then the 08-27 morning checklist (no halk, three-clock,
   premier audit 4/4), **rebuild `dep_subgrid_merged.tif` on the NEW template**
   (`build_merged_subgrid_dep.py --subgrid-dir experiments/v3/_template_sealed/subgrid`,
   hard-link into the arms — the merged raster is mesh-derived and the old one died with
   the template), `--validate-only` → new baseline → paired bootstrap on THAT.

### ✅ 2026-08-24 — THE RING IS DRAWN (`region_v3_EDITED_inland.geojson`) and the Cape May NACCS gap is filled

**`data/region_v3_EDITED_inland.geojson` is the v3 ring** (user, QGIS, from the inland
draft). 54 vertices, 52 verbatim from the draft. Gate: **exit 0, 17 declared reaches,
ZERO wet river cuts** — `toms_river`, `great_egg_tuckahoe`, `mullica_lower` boxes all
match nothing (retire them with the domain wiring). 15 of 16 gauges inside; Folsom
`01411000` outside by design (+19 m, 20 km above Mays Landing — src goes at the Great Egg
cut above Lake Lenape). The user's two Monmouth moves (v37 → −74.125, 40.353; v38 →
−74.119, 40.158) bring the **Manasquan gauge inside** (my draft had it 1.7 km OUT — only
v1.5's src point was in) and take in more Navesink headwater; all three touched segments
are dry at 10 m (min +2.95 / +10.1 / +17.9 m). ⚠️ So "v1.5's ring verbatim" now means
its **forced cuts** (ocean arm, Narrows, Arthur Kill) — the landward Monmouth edge moved
~2.5 km west on dry ground. Toms cut moved to its gauge too (decision reversed from the
morning: MOTF surge reaches lon −74.226, the gauge is at −74.222, a N–S line there is dry
at +3.6 m; the Wrangle Brook confluence is now inside).

**NACCS merge — `repack_naccs_zips.py` now MERGES:** a new `CHSFileDownload_*.zip` is
inventoried WITH the canonical `naccs_repack_*.zip` as sources (same CRC-identity assert;
the PROVENANCE/ tree passes through verbatim); previous canonical zips go to
`_originals_pending_delete/` as `*.pre-merge-<stamp>.zip`. Applied 2026-08-24 on the
user's Cape May pull: 63 ADCIRC members, 29 re-requests (CRC-identical), **34 new save
points → 1,321 total**; STWAVE03 301 → 335 (parked, unread). Gate reproduced:
`--report-only --no-cache` under v1_monmouth → 1,321 points, **support sha16
21f967f9798a6945 unchanged**. `_originals_pending_delete/` (646 MB) is safe to delete —
user's call. Figure `reports/figures/naccs_cape_may_after_merge.png`.
Where the new points are: a **cluster of 5 on the canal mouth** (around NOAA 8536110),
a nearshore line up the Villas shore (15258, 11168, 11205, 13425, 11169; 1–6 m, two of
them ≤ 0 m and will be dry-screened as usual), and 5 deep-bay anchors 15–30 km west
(11013/11014/7168, 10–14 m). The wedge's N–S leg at lon −74.985 still has no point ON it
south of the mouth; nearest support is the mouth cluster (~1 km) and 7548 / 15260 at the
Point — **adequate for a 2-node interpolant along a 4 km leg, and the user has pulled what
the webtool offers there.** Not a gap to chase further.

## ✅ STEPS 0 + 1 DONE — 2026-08-24 evening. v3 is `building`; every Step-1 input is on disk

**Step 0.** `Domain.building` is a new registry state (real polygon, no mesh) between
`acquisition_only` and sealed: fingerprint / basin-rule / support-count guards skip it,
`assert_buildable` passes it, `_check_building` refuses a PROVISIONAL region or a
`mesh_key`. v3: `region=region_v3_EDITED_inland`, `latitude=39.74`,
`discharge_geodataset=usgs_sandy_discharge_v3`, own `hwm_geojson`. The three river
`CROSSINGS` boxes are retired (gate: exit 0, `river cuts declared: []`). **89 tests OK.**

**Step 1 — pulled (all under `NJ_DOMAIN=v3`):**

| input | file | what landed | ⚠️ |
|---|---|---|---|
| discharge | `discharge_v3/usgs_sandy_discharge_v3.nc` | **17 sources at their NWIS gauge coordinates** (snapped — my hand copies were 100–770 m off) | Folsom's src is at the Mays Landing cut (gauge outside). Batsto R / Middle R ungauged. |
| HWMs | `validation_v3/sandy_hwms_v3.geojson` | **185 marks** in the ring bbox (q1 48 · q2 79 · q3 33 · q4 25), 1.34–5.79 m | src-contamination 500 m check still to run (needs the mesh's src faces) |
| USGS tidal | `gtsm/usgs_sandy_tidal_v3.nc` | **15 stations**: v1's 4 + 11 southern (param 72279). Most run THROUGH the peak (n≈960); Cape May Harbor stops 10-30 03:54, Absecon Channel n=480 | Sluice Creek is Delaware-Bay side, outside the ring (region clip drops it) |
| STN sensors | `gtsm/sandy_storm_tide_south.nc` | 6 instruments, preset `south` | 🔴 **2245 (Great Bay) and 2261 (Barnegat Inlet) read 4.47 / 4.45 m at their FIRST sample and never higher — not a surge shape; likely a barometric or mis-datumed file. Do not use without looking.** 2248 (Cape May) has 3 h only. 2244 (2.39 m), 2246 (2.10 m), 2247 (2.24 m) look real. |
| CORA waves | `waves_v3/cora_waves_v3.nc` | 11,594 nodes × 121 h, offshore of the ring | `build_cora_waves.py` now writes to `acquisition_dir("waves")` for a non-archived domain |
| curve numbers | `infiltration_v3/cn_v3.nc` | 16.6 M land cells, CN 30–95, mean 71.6 | SDA returned 413 on the v3 bbox → `build_cn_nj.py` now tiles the query (0.25°, dedup on mukey+wkt) |
| eHydro south | `elevation_v3/ehydro_south_v3.tif` | Cape May Canal + Cold Spring (Cape May) Inlet + Absecon Inlet, 30,312 carved cells at 5 m, −19.3..−1.1 m; **12,783 cells in the canal, −12.6..−1.1 m** | 🔴 CENAP ships **+depth** — `PRESETS` now carry a sign (5th element). 🔴 **VDatum is unusable south of Barnegat** (every region errors); planes come from NOAA station datums (Cape May −0.920 m, Atlantic City −0.796 m), declared in `STATION_PLANE_M`. Surveys are 2015 (+865..+877 d) — nothing nearer exists. Great Egg / Townsends / Hereford inlets are unsurveyed (non-federal). |
| MOTF, NACCS, precip, wind, roughness, elevation tiers | — | already covered | — |

Quota 70.3 G of 100 G. `data/NACCS/_originals_pending_delete/` (646 MB) still awaits the user.

🔴 **STEP 2 FINDINGS — the v3 quadtree build, 2026-08-24 evening.** Four things, each
measured, each now in code:

1. **hydromt's block loop is bbox-proportional in memory.** `compute_quadtree` chunks by
   `nrmax=2000` CELLS, so at level 0 (200 m) one chunk is the whole 130 × 200 km bbox and
   `merge` clip+LOADS every native tier for it (`workflows/merge.py:264-273`). The first
   probes hit **158 GB / 164 GB / 166 GB RSS** and were killed — in refinement gating AND
   again in face elevation; splitting the 25 m polygon into 14 pieces changed nothing.
   Fix: `Domain.coarse_elevation_list` (new; `BaseConfig.coarse_elevation()`) — v3 gates
   refinement AND merges face `z` from **one 25 m raster**, `bed_v3_coarse_25m`, built by
   `scripts/build_v3_coarse_bed.sh` (base tiers bilinear = hydromt's own face method;
   carving tiers MIN so a 5 m channel survives a 25 m cell — bilinear paved 69 Shark-inlet
   faces). Peak RSS after: ~3 GB. The finest face is 25 m, so a 25 m face bed loses
   nothing. ⚠️ The SUBGRID still needs the native tiers: that is what the overviews are for
   — `gdaladdo -ro` (2..64×, average) on every v3 tier + a local `cudem_nj_v3.vrt` over
   the archive tiles, because hydromt picks an overview from `zoom=(res,"meter")` and the
   subgrid asks for `dx/8` per level (25 m at level 0). Not yet measured on the subgrid.
2. 🔴 **The NJ lidar reads 0.0 over water and its rectangle covers the shelf.** The model
   applies `zmin=0.001` to it; the first coarse bed did not, and **817,718 offshore faces
   were paved to z = 0** and dropped as an "island". The build script thresholds it now.
3. 🔴 **v3 must inherit v1.5's mask boxes.** Without `always_active_boxes_ll` the Lower
   Bay / Raritan Bay channels deeper than −10 m sever the Raritan lobe and
   `_drop_detached_islands` removed it (41k + 20k + 11k cells). `always_active_boxes_ll`,
   `dry_land_boxes_ll` (Ward Point) and `no_waterlevel_boxes` (the Raritan cut) are now
   `V1_5_RARITAN.<same>` on V3 — and **`STATIONS_V3` had dropped the two Raritan sources
   at that cut; restored, 19 sources.**
4. The paved-channel invariant checked only the archive's Shark survey; it now checks
   every `ehydro*`/`shrewsbury*` tier in the active domain's list. `build_static` no
   longer dies on a domain with no `obs_gauges` (warns; the freeze must assert them).

✅ **THE CLEAN PROBE (2026-08-24, last run): FACES 3,312,567 · active 1,704,096 ·
water-level BC 6,835 in 4 runs over 4 declared arms · outflow 1,800, none on water ·
every invariant OK.** Per arm: ocean 1,155 [1000..1400] · narrows 59 [45..85] ·
arthur_kill 23 [16..40] · **ocean_south 5,598 [5000..6200]** (new arm: isobath south of
lat 40.15 + Cape May closure + Delaware Bay wedge). Active by depth: −20..−10 26k ·
−10..−2 627k · −2..0 305k · land 741k. v1 footprint 313k active. Figure
`reports/figures/v3_probe_mask.png`. **Projected SnapWave ≈ 18 h per run** (×6.05 v1's
faces) — the runtime is now the v3 cost; a 24 h SLURM window is the minimum.
Levers if that is too much: L2 `low_water` zmax 3 → 2 m and L1 `inland_floodplain` 6 → 5 m
(the L2 ring-wide 50 m gate is the driver). ⚠️ Peak RSS of the probe ≈ 3 GB; **the SUBGRID
build has not been run yet** — with the new overviews it should stay bounded, but it must
be MEASURED (run the template build under a memory watch) before it goes on a SLURM node.

**Outflow edges vs the head-of-tide sources, measured on the probe:** every source's
nearest free-outflow cell is on ground above +7 m except the Raritan cut (+2.3 m bank,
same as v1.5) and **Tuckahoe (+1.22 m, 480 m from the source)** → `land_boxes`
`tuckahoe_head_of_tide` walls it (73 cells inactive). The Delaware Bay shore leg north of
the canal carries 34 outflow cells at −0.94..+3 m and is left open, declared, in the box's
`why`. 40 water-level BC cells fell outside every arm and were demoted to interior
(hydromt's own rim cells around filled holes) — the invariant then held.

### ✅ 2026-08-25 — the pre-freeze pass (user decisions: pull the levers, defer ICW, sweep, measure)

**The two levers DID NOT MOVE THE COUNT.** `low_water` zmax 3→2 and `inland_floodplain`
6→5 (recorded in each polygon's `why`, with the restore condition) took the probe from
3,312,567 → **3,267,861 faces (−1.3%)**, active 1,704,096 → 1,659,778; BC 6,835, outflow
1,664, every invariant OK, 4:57 wall, 7.9 GB RSS. The realised-size map in the notebook
says why: **971k of the active faces are 25 m, in the ring-wide `surf_dune_*` band**
(2.5 km buffer, z −8..+3); L2 50 m is 656k, L1 100 m 40k, base 37k. The cell-count lever
is the surf band's buffer width / zmax, not L1/L2. ⏳ user decision: keep the 25 m surf
band (≈18 h/run) or narrow it. Added resolution later is fine as long as it is noted here.

**Bridge-as-dam sweep done** — `scripts/sweep_bed_dams.py` (reads the 25 m coarse bed
inside the ring; wet = z < −1 m; 4-connected bodies; ocean = largest; reports every other
body's wall thickness to the ocean and the lowest bed in that wall). `reports/bed_dams_v3.csv`
+ `reports/figures/bed_dams_v3.png`. 47 bodies ≥ 0.02 km² behind a wall < 300 m; 43 have
a crest in −1..0 m (shoals). **Four crests above 0 m — the candidates, user to judge:**
| body | crest | wall | area | where |
|---|---|---|---|---|
| 1450 | +1.00 m (max 2.15) | 125 m | 0.06 km² | 39.092 N −74.736 — Grassy Sound / N. Wildwood causeway |
| 980 | +0.66 m (max 2.05) | 135 m | 0.41 km² | 39.392 N −74.407 — Absecon / Brigantine |
| 62 | +0.56 m | 50 m | 0.25 km², −7.7 m basin | 40.353 N −73.976 — Shrewsbury, with `shrewsbury_ehydro_2015` in the list |
| 157 | +0.42 m (max 1.72) | 266 m | 0.02 km² | 40.023 N −74.059 — Point Pleasant Canal |

**VDatum fallback in `build_naccs_boundary.py`** — the service is broken south of lat
~39.34 (`contiguous` = "Uncaught error" at every point tested; named regions rejected;
/regions 404) — 70 of v3's 190 support points. `datum_offsets()` no longer exits: a point
VDatum cannot place takes the nearest NOAA station's MSL→NAVD88 plane
(`STATION_MSL_PLANE_M`: Atlantic City −0.122, Cape May −0.137 m, mdapi datums, 1983–2001)
and the cache CSV records `source`; those rows are re-queried every run. Warns, never gates.

**Build-QC notebook** `notebooks/v3/sandy-v3-build-qc-2026-08-25.ipynb` — 4 plots off the
probe: boundary + NACCS support, realised face size, 33 gauges vs the NACCS product, sites.
The two "flat NACCS node" panels (NOAA Cape May → node 7549, dry 1,877 samples; USGS
1411350 → 13483) are plot artefacts: neither node passes the 8 m screen, neither is in
the forcing set. The notebook's matcher now requires never-dry as well as deep.

**ICW eHydro tier: deferred (user).** Add later as its own `bed-icw` arm, never silently.

### ✅ 2026-08-27 morning — ALL THREE v3 ARMS COMPLETED CLEAN; validation running

**The runs are real.** Every check on the morning checklist passed, per arm
(`naccs-premier` 60995929 hal0290 5 h 36 · `wave-stwave` 60995930 hal0308 5 h 39 ·
`naccs-nowaves` 60995931 hal0360 43 min):
- **no `halk`** in any final job; GPFS three-clock test clean (creation 18:35–18:36 =
  the job that made the file, mtime = ctime = job end — no late clobber);
- `sfincs.log` ends `Closing off SFINCS`, no NaN/instability, all SnapWave iterations
  converged at 100 % ok; only warning is the expected `manningfile ignored (sbgfile)`;
- `sfincs_his.nc` 10-28 00:00 → 10-31 00:00, 433 steps, **25 stations, zero NaN**;
  `sfincs_map.nc` 73 steps, `zsmax` finite on exactly the active fraction (0.508) in all
  three — no all-fill map. The `zsmax` max of 100.85 m is bed on a never-wet face
  (`zb` max 100.84), not a blow-up;
- `python -m nj_sfincs.premier` → **4/4 OK on v3, output WHOLE**;
- the 18:01 `FAILED 11:0` attempts left nothing (re-staged over at 18:24–18:35).
Peaks (premier): Great Kills 3.92 m, Sandy Hook 3.82, Narrows 3.66–3.69, Arthur Kill mouth
3.43, Sea Bright ~2.9, Absecon Creek 2.92.

**Runtime was NOT anomalously fast** — the 18 h projection was wrong, not the runs.
v3 has 1.70 M active z points vs v1.5's 412 k (4.1×), same average dt (0.69 s), 64
threads both. Waves-off scaled with cell count (2,587 s vs 795 s = 3.3×); premier
20,064 s vs 8,328 s = **2.4×** because SnapWave's share fell 89 % → 83 % (the new inland
and lagoon cells cost SnapWave little). MaxRSS 12.4 G (wave arms) / 1.3 G — `--mem=180G`
can drop to ~32 G next time; `--time=30:00:00` to ~8 h.

**§40 src-contamination sweep on the 185 v3 HWMs — DONE (against the staged src faces,
UTM 18N):** **1 of 185 within 500 m** — HWM **6044** ("rip-rap on dam exterior",
39.4306 N −74.5202, 2.316 m, q4) sits **49 m from the Absecon Creek source**
(USGS 01410500, Qmax 3.5 m³/s — small injection, but it reads the injection, FINDINGS
§40). Next nearest: 6102 at 674 m, 6101 at 921 m (the Raritan src, Qmax 110). ⏳ Wire
`src_contaminated` as a column in the v3 scorer / report so 6044 is flagged, not dropped
(warn, never gate).

✅ **FIRST v3 SCORES — `--validate-only`, 2026-08-27 afternoon** (`experiments/v3/metrics.csv`,
`report.html`, floodmaps 2.48 GB each). 🔴 The first pass **failed on `wave-stwave` with
"Write failed"** — home had hit the **110 G hard quota** (three 2.5 GB floodmaps) and the
TIFF was truncated at 1.35 GB. Truncated cache deleted, `dedupe_home.py --apply` reclaimed
5.5 GB (20 hard-links), re-run clean. ✅ **Reclaim EXECUTED 2026-08-29 (user):** v1.5 `diag-nowaves-fasthis`
2.0 G + `diag-premier-norain` 1.4 G (both banked — FINDINGS §40 / §39 +
`reports/rain/rain_share.csv`), v1.5 `floodmaps/` 1.1 G (regenerable via
`--validate-only`), and the two v3 `snapwave.upw` 2.3 G each (staging input — re-stage
before re-launching those dirs). ≈9 G → back under the 100 G soft limit; premier audit
4/4 (v3) and 6/6 (v1.5) after. `preweir-*` banked runs kept.

HWMs: **median, 50 m, q≤2 → n=63** (140 of 185 in region — 45 clipped as outside;
88 wet / 52 dry in-domain; 0 dry among the scored). MOTF `excluded_boxes = 0 km²` — ⚠️ v3
declares no NY-validity boxes yet; the SI shore is out of the model so it may be moot,
but check before quoting CSI beside v1.5's.

| arm | HWM RMSE | bias | within 0.5 | CSI | POD | FAR | CSI_conn | admissible |
|---|---|---|---|---|---|---|---|---|
| naccs-premier (CORA) | **0.355** | **−0.123** | **0.873** | 0.828 | 0.871 | 0.056 | 0.855 | yes |
| wave-stwave | 0.358 | −0.217 | 0.873 | **0.830** | 0.872 | 0.055 | 0.856 | yes |
| naccs-nowaves | 0.402 | −0.288 | 0.794 | 0.807 | 0.843 | 0.049 | 0.831 | flagged |

Read: waves are worth ΔRMSE ≈ 0.045 m / ΔCSI 0.02 again (same size as on v1.5); the two
wave sources are a wash on extent and differ on bias, and the difference is **in the
Raritan lobe**: Great Kills peak err −0.07 (CORA) vs −0.60 (STWAVE) vs −0.59 (off),
Arthur Kill mouth −0.39 / −0.69 / −0.66 — consistent with STWAVE grid 07 (NY Bight)
running low. Not yet PAIRED — `paired_hwm_bootstrap.py` is the next call, not this table.

Gauges (19 with a real peak; premier / nowaves / stwave mean |err| 0.39 / 0.42 / 0.41 m):
- ⚠️ **Sea Isle, Ship Bottom, Stone Harbor peak lag ≈ +1450 min** — the "obs peak" is the
  pre-storm-tide gap artefact noted 08-26; their `peak_err` (+0.25/+0.64/+0.31) is against
  the wrong peak and means nothing until the obs series is trimmed.
- ⚠️ **Absecon Creek +1.04 m in all three** — its obs face bed is 0.00 m AND the gauge is
  the Absecon Creek src (01410500) — reads the injection, same as HWM 6044 beside it.
- 🔴 **Five obs faces sit ABOVE MSL and show no tide** — Cape May NOAA (bed +1.39 m,
  modelled range 0.05 vs 1.56 obs), Barnegat Light (+1.07; 0.06 vs 1.00), Great Bay
  (+0.56), Inside Thorofare (+0.40; 0.16 vs 1.22), Absecon Creek (0.00). The 50 m obs
  face is the pier/bank. **Not an inlet problem**: `usgs_tidal_cape_may_harbor` next door
  (bed −1.30) carries a full 1.39 m range. ⏳ Fix on the validation side: score each
  gauge against the nearest face with bed < −0.5 m (an obs-snap analogue of
  `_snap_sources_to_active_faces`); no re-run needed for the peak, but the obs points in
  `data/frozen_mesh_v3/sfincs.obs` should move before the next solve.
- Real signal so far: **Atlantic City NOAA +0.49 m (all arms, oceanfront — a forcing
  question, NACCS is the input there)**; Sea Bright storm-tide −0.5; Mantoloking / Ocean
  City −0.3 / −0.4; southern back-bays Avalon +0.76, Tuckerton +0.59 high.

⏳ **NEXT:** (1) ✅ quota reclaimed 2026-08-29; (2) paired bootstrap premier vs stwave vs nowaves;
(3) obs-face snap in the scorer + trim the three gap-artefact obs series; (4) wire
`src_contaminated` (HWM 6044, Absecon Creek gauge); (5) MOTF validity boxes for v3;
(6) ✅ ANSWERED 2026-08-29 — great_bay_mullica's marks sit on 50 m faces with no lev3
DEM coverage, see the 08-29 section below; (7) dry-crossing creek sweep.

### 🔴 2026-08-29 — THE LEV3 FLOODMAP DEM DOES NOT COVER 51 OF v3'S 140 IN-REGION HWMs

Found from the viz notebook's grey backdrop (user: "why is Raritan Bay cut off?"). The
HWM/MOTF pipeline downscales zsmax onto `subgrid/dep_subgrid_lev3.tif`, which hydromt
writes **only under level-3 (25 m) faces** — on v3 that is the surf band + low-water
areas, 10% of the raster rectangle. The scorer's "is this mark on this model's grid"
test is *finite dep within the 50 m radius* (`_sample_hwm.mod_ground`), so an in-region
mark over a coarser face is silently classed OUT OF DOMAIN, exactly like a mark outside
the mesh. Measured on `naccs-premier` (nearest-active-face lookup on the map file):

- **51 of 140 in-region marks have no lev3 coverage. All 51 sit on an ACTIVE face**
  (50 within 40 m, worst 67 m); **49 are WET at face level; 31 are q≤2** — the scored
  n=63 would be ~94 with them in. The current CSV is not wrong, it under-samples.
- The (553–560 km E, 4378–4388 km N) cluster is Tuckerton / Great Bay — this is why
  `great_bay_mullica` scored 0 of its 15 assigned marks (NEXT #6). The Keansburg pocket
  marks 6155/6156/6133 (FINDINGS §38) are also among the 51 on v3.
- **v1_5 measured CLEAN — 0 of 69 in-region marks uncovered** — which is why the
  "lev3 covers every mark" assumption held until now. It is a per-domain fact of the
  refinement scheme, like §40 src-contamination.
- ⚠️ **The MOTF extent scores share the exposure:** the downscaled floodmap paints only
  lev3-covered ground, so a WET coarse face reads model-dry to the extent comparison →
  artifact misses inside `simulated_mask`. Not yet quantified; do so before quoting v3
  CSI against v1.5's.

Fix options (user to pick; either re-baselines the v3 CSV — decide deliberately):
(a) build a merged all-level dep mosaic (lev0–3 on the lev3 grid, coarser levels
nearest-filled) and downscale onto that — fixes HWMs AND the MOTF extent in one move;
(b) scorer-side fallback to face-level sampling where dep is NaN — fixes HWMs only.
The viz-notebook backdrop itself is only cosmetic: the grey is `dep_subgrid_lev3`, the
holes are coarser faces, the region ring and mask are intact (premier 4/4).

✅ **DECIDED (user, 2026-08-29): (a).** Executed the same day:
`scripts/build_merged_subgrid_dep.py` builds `subgrid/dep_subgrid_merged.tif` (exact
nearest fill — the four levels share one rotated lattice, ratios asserted powers of 2);
built once in `_template_sealed/subgrid/`, hard-linked into the three arms.
`load_floodmap` and `plots.load_cached_floodmap` prefer the merged raster and fall back
to lev3 (v1.5 unchanged, bit-for-bit); floodmap-cache freshness now also checks the dep
mtime, so the merge self-invalidates the old caches. Old CSV banked as
`metrics_2026-08-29_pre_depmerge_rebaseline.csv`.
**Pre-registration (written before the re-score):** hwm_n_scored 63 → ≈94 (the 31
q≤2 uncovered marks come in; 6411 should score dry-at-ground); `great_bay_mullica`
n_scored rises from 0; MOTF misses drop in the back-bay marsh on all three arms.
No prediction on the direction of RMSE/bias/CSI — the new marks are back-bay
conveyance tests the old sample never saw, and that is the point of scoring them.

✅ **RE-BASELINED SCORES (merged dep, 2026-08-29; 2h11m, peak RSS 120 GB).**
Pre-reg: n 63 → **94** exact; `great_bay_mullica` 0 → **9 scored** (RMSE 0.44–0.48,
bias ≈ −0.03 — the basin is FINE, it was never scored); POD up 0.871 → 0.895 (misses
down) ✓. Missed: 6411 scored WET, not dry-at-ground (0 dry of 94). The merged tif
needed a gdaladdo overview ladder (the pipeline opens the dep by overview level) —
now in the build script.

| arm | HWM RMSE | bias | within 0.5 | CSI | POD | FAR | FARc | CSIc |
|---|---|---|---|---|---|---|---|---|
| naccs-premier | **0.418** | **−0.065** | **0.872** | 0.704 | 0.895 | 0.232 | 0.118 | 0.799 |
| wave-stwave | 0.426 | −0.225 | 0.840 | **0.706** | 0.894 | 0.230 | 0.113 | 0.803 |
| naccs-nowaves | 0.458 | −0.281 | 0.766 | 0.703 | 0.875 | 0.219 | 0.102 | 0.796 |

Read, and the caveats that must travel with these numbers:
- **The old CSI 0.83 was flattered by the truncated dep** — the extent comparison was
  confined to the lev3 band (the surf zone, where the model is best). On the full
  frame CSI is 0.70 — coincidentally v1.5's 0.704, but now measured over 15k km².
  🔴 Never quote the 0.83-row and the 0.70-row as the same metric. The same truncation
  hid model SKILL, not just error: hits 359 → **702 km²** (premier) — the back-bay
  flooding the model gets right was invisible to the old comparison.
- FA grew 21 → ≈212 km²: painting coarse faces is the model's real claim (a wet
  face's level intersected with the fine bed — the same rule lev3 pixels always
  used), and MOTF is a bathtub that cannot contain rain. 119 km² of the FA is
  never-sea-connected (tan, §39 rain family); connected-only FARc is 0.102–0.118.
- `motf_km2_unsimulated` 61 → 7,818 km² is the screen finally seeing the whole
  rectangle (upland inactive faces under the now-covered dep), not a regression;
  `unsim_motfwet` 3.8 → 184 km² is MOTF-wet ground v3 does not simulate — worth a
  look when drawing the next domain.
- HWM: premier still best on every column; waves worth ≈0.04 RMSE; the 31 new marks
  pull premier's bias from −0.123 to −0.065. Waves-on extent separation shrank to
  ≈0.003 CSI (extent is now dominated by back-bay/inland ground where SnapWave
  matters less).
- ⏳ The paired bootstrap (NEXT #2) must run on THIS baseline, not the banked one.
  Quota after: 101.4 G — over soft again (7-day grace); the three `floodmaps/`
  gallery tifs (2.48 G each, regenerable at next validate) are the obvious reclaim,
  user's call.

### 🔵 2026-08-26 evening — v3 IS FROZEN AND THE THREE ARMS ARE GOING OVERNIGHT

**Frozen:** `data/frozen_mesh_v3` = the subgrid probe adopted by `mv` (same
`build_static(frozen_mesh=None)` call `freeze_mesh.py` makes; rebuilding would only risk
the ~18-cell drift). `premier.V3 = (3312567, 4010, "ae28ac5ef3aeb599")`, `building`
cleared, `n_waterlevel_support=3` (base NOAA: Battery + AC + Cape May). 89 tests OK.

**Validation wired on V3** (`domain.py`): v1.5's 8 gauges verbatim + NOAA Atlantic City
(⭐ southern holdout) + NOAA Cape May (⚠️ ON the wedge forcing line — forcing diagnostic,
not a holdout) + 12 USGS v3 tidal gauges + 3 STN (2244 Great Bay, 2246 Great Egg, 2247
Cape May) = **25**. Sluice Creek, STN 2245/2261/2248 deliberately not listed (notes say
why). ⚠️ Several southern USGS gauges show a pre-storm-tide "peak" (Ship Bottom, Sea Isle,
Stone Harbor) — likely crest GAPS; read the series before scoring their peaks.
**HWM basins:** `_V3_SOUTH_RULES` (7, bounded, FIRST) + `_V2_SOUTH_RULES` + `_V1_5_BASIN_RULES`;
all 185 marks assigned, none `unassigned`: lower_bay_si_shore 42 · raritan_bay 31 ·
shrewsbury_navesink 15 · great_bay_mullica 15 · absecon_atlantic_city 13 · manasquan 12 ·
barnegat_bay 10 · atlantic_oceanfront 9 · lbi_barrier 7 · sandy_hook_bay 6 ·
cape_may_back_bays 5 · cape_may 5 · south_coast 5 · shark_river 4 · great_egg 3 ·
delaware_bay_shore 2 · barnegat_barrier 1. A first county-scale partition; no
ocean-front/back-bay split south of LBI yet (n too small) — refine after the first score.

**Three arms (user):** `naccs-premier` (CORA waves), `wave-stwave` (NACCS STWAVE waves),
`naccs-nowaves`. All: `naccs_sandy_v3` (224 pts), `wave_n_support=36` (~5 km on a 178 km
open-coast edge; v1.5 used 7 on 25 km).
**STWAVE file** `data/waves_v3/naccs_stwave_v3.nc` from `scripts/build_naccs_stwave_waves.py`:
274 nodes ≥ 8 m (1,095 shallower grid-points dropped), 193 half-hour steps 10-28..11-01,
hold-padded to 10-27. 🔴 **The three STWAVE grids DISAGREE where they overlap** — median
max|ΔHs| 2.5 m (02∩03), 2.6 m (02∩07), 3.7 m (03∩07); 07 (NY Bight) runs low. Shared
points take the grid whose centre they are nearest (most interior); `grid` is a per-node
coord. ⚠️ `alpham` read as nautical-FROM by inference (10-28 00:00: waves 28°, wind 64°),
not documentation. Hs max 9.74 m at SP1197 (19 m). Kept by grid 02: 89 · 03: 86 · 07: 99.

🔴 **FIRST SUBMISSION (jobs 60995570/71/72) SIGSEGV'd on all three arms within 70 s** —
the waves-off arm in 14 s with an EMPTY `sfincs.log`, the wave arms just past the SnapWave
banner at 11 GB RSS; the initial `sfincs_map.nc` (10 MB) and `sfincs_his.nc` were written,
so the solver died on the first time step. Not the stack (`ulimit -s unlimited` +
`OMP_STACKSIZE=1G`, now in `hpc/sfincs_run.slurm`, changed nothing). Three staging gaps
found by inspection, all fixed and re-staged (job 60995740, `--rebuild-template`):
1. 🔴 **The Raritan source (Qmax 110 m³/s) sat on an INACTIVE face** — hydromt snaps a
   source to the nearest face by distance alone; on v3's slightly different mesh the
   nearest face 24 m from the cut is mask 0 (on v1.5 it was active, 7 m). A source on
   mask 0 is a first-step segfault in SFINCS. `model._snap_sources_to_active_faces`
   (new, in `add_forcing`) moves any such source to the nearest active face, prints the
   move, raises over 300 m, and re-checks. The other 18 sources were on active faces.
2. **No `sfincs.obs`** — the frozen mesh was built by the probe BEFORE the gauges were
   wired, and obs points are written in `build_static` only. Wrote the 25 points into
   `data/frozen_mesh_v3/sfincs.obs` (`sync_obs_points.render`, format round-trip OK) and
   `obsfile = sfincs.obs` into its `sfincs.inp`.
3. **No `sfincs.weir`** — the Keansburg line (FINDINGS §38) lives in v1.5's frozen mesh
   dir; copied verbatim to `data/frozen_mesh_v3/` (all 89 vertices on active v3 faces,
   ≤ 35 m). `_ensure_weirfile_key` re-adds the inp key.
Neither 2 nor 3 can segfault; 1 is the diagnosis. If the re-stage still dies, the next
suspects are the 25 obs points (any outside the grid?) and an index overflow in the
6.65 M-uv-point subgrid — bisect with the waves-off arm, it fails in 14 s.

✅ **RUNNING since 18:35 — jobs 60995929 (naccs-premier, hal0290) · 60995930
(wave-stwave, hal0308) · 60995931 (naccs-nowaves, hal0360).** Re-staged from a deleted
template (the sealed-template guard refuses `--rebuild-template` by design — delete
deliberately). Staged arms carry `obsfile` (25) + `weirfile` (89 vertices) +
`[src] 1 of 19 sources moved; all 19 now on active faces` (Raritan src now at
559361, 4484475). 10 min in: map/his growing on all three, RSS 12.4 G (wave arms) /
1.3 G (waves-off); first-look rate ≈ 2 model-h per 3 min waves-off, ≈ 1.5 model-h per
4 min with SnapWave — far under the 18 h projection so far, but the crest will be slower.
Quota 52 G of 100 G after dedupe (mmlsquota lags ~10 min after hard-linking: it read
88.8 G right after `dedupe --apply` both times, then 52 G).

Cleanup 2026-08-26 evening: `data/probe_mesh_v3/` (the 08-25 dry-run npz) deleted — the
frozen mesh supersedes it; `build_naccs_boundary.py --mesh` now takes
`data/frozen_mesh_v3/sfincs.nc`. Scratch VDatum zips removed (the six `*_tss.gtx` under
`data/NACCS/vdatum_grids/` are the keepers). `data/NACCS/_originals_pending_delete/` deleted (user, 2026-08-26).

**Submitted via** `hpc/stage_and_submit_v3.slurm` (hal-only): stages the three arms with
`--no-run`, hard-links duplicated inputs (`dedupe_experiment_inputs.py --apply`), then
`run.submit_slurm(dir, sif=sfincs-desktop.sif, --time=30:00:00 --mem=180G)` per arm.
Log `logs/stage_v3_<job>.out`; solves `logs/sfincs_<job>.out`. Projected ~18 h SnapWave
per wave arm. Disk before staging 49.5 G / 100 G; template + 3 arms ≈ +28 G before
dedupe. ⏳ **Morning checklist:** `sacct --format=JobID,JobName,NodeList,State,Elapsed`
(no halk!), quota, then `--validate-only` on each arm; then the §40 src-contamination
sweep on the 185 HWMs (needs the staged src faces) and the dry-crossing creek sweep —
both still TODO.

### 2026-08-26 — levers RESTORED (user); subgrid probe SUBMITTED; dam-candidate maps

**Levers undone.** `low_water` zmax back to 3 m, `inland_floodplain` back to 6 m
(`why` records the try and the restore) — 1.3% was not worth the resolution. The v3
mesh to freeze is therefore the 3,312,567-face clean probe of 08-24.

**Subgrid probe** submitted as SLURM job **60979984** (`hpc/subgrid_probe_v3.slurm`,
hal-only, 180 G, 12 h, `/usr/bin/time -v`, log `logs/subgrid_probe_v3_<job>.out`) on the
restored mesh. Result (peak RSS, wall, `sfincs.sbg` size) goes here.

**Dam-candidate maps** `reports/figures/bed_dam_{1450,980,62,157}.png` from
`scripts/plot_bed_dam_candidates.py` (lidar vs the 25 m coarse bed, 1.5 km window, lon/lat
frame for Google Maps; green = the body's cells, yellow = the wall segment the CSV crest
refers to). ⚠️ The CSV's lon/lat is the body cell NEAREST the ocean, not the wall, and the
wall is the nearest approach — for a long channel that is not necessarily the blocked one.
Read with the user: **1450** — a marsh creek behind the lagoon block; the 125 m wall is the
lagoon's real bank; its NE outlet is a −1..0 m marsh channel pinched by the threshold. Not
a dam. **62** — lagoon opens to the Shrewsbury over −1..0 m flats; threshold artefact.
**157** — one lagoon pocket whose thin channel the 25 m averaging paved; subgrid carries
it. **980** — the flagged wall
is the Brigantine Blvd causeway (real land); the channel's SW end (`bed_dam_980_sw.png`,
`--centre -74.4165 39.3875`) meets Absecon Inlet across a 150 m band of −1..0 m flats —
threshold again; the +8 m ridge there is the Route 87 bridge RAMP on the peninsula, not a
deck. ✅ **Sweep closed: no bridge-as-dam carve on v3's premier bed.** All four are the
−1 m threshold reading shallow flats as a wall, or real land on the nearest-approach line.

**VDatum: the web service is REPLACED by NOAA's own separation grids, sampled offline.**
The web failure south of lat ~39.4 is exactly the footprint of NOAA's March-2024 grids
(`NJscstemb32` / `NJVAmab33` / `DEdelbay33`), whose `tss` reads +0.44 m at Atlantic City
against a 0.12 m gauge — a different geoid reference, not NAVD88. The previous (2019,
NAD83/NAVD88) release is still at `vdatum.noaa.gov/download/data/<name>.zip`; six
`*_tss.gtx` now live in `data/NACCS/vdatum_grids/` (67 MB, gitignored; `.met` beside
each). `tss` = NAVD88 − LMSL, offset to add = −tss, lon 0..360. **Verified:** grid −
web = 0.0000 mean, 0.0009 m max over all 144 v1.5 cached points; Atlantic City +0.120,
Cape May +0.137, Lewes +0.121 vs gauges 0.122 / 0.137 / 0.122. Of the 1,308 save points
in the v3 bbox the grids place 1,251 (871 ncstemb, 340 scstemb, 40 delbay); the 57
uncovered are back-bay/marsh points that the grid models as land — they fall to
web → station plane with a warning, and are unlikely to be on the `mask==2` line.
`datum_offsets()` now: grids → web → station plane, `source` per row, only `grid` rows
trusted across runs; `--check-vdatum-web` cross-checks against the service. ⚠️ The
station-plane error is 2–3 cm on the shelf and up to 8 cm in the bays (Great Egg
+0.045 vs AC +0.122), not the 0.015 m assumed on 08-25. Old web cache kept as
`vdatum_lmsl_navd88.web-2026-08-25.csv`. vyperdatum (NOAA's package) does the same
thing with extra machinery — not needed.

✅ **v3 NACCS BOUNDARY BUILT — `data/gtsm/naccs_sandy_v3.nc`, 224 support points,
support sha16 `19f53cfd4cb804fb`** (built on the 08-25 levers-pulled probe via the new
`--mesh data/probe_mesh_v3/domain_dryrun.npz`; its `mask==2` line is 6,835 cells,
identical to the clean probe's — the line is set by `mask_zmin` and the boxes, not the
refinement — so the freeze will not change the support). Datum: all 224 from the offline
grids, Sandy Hook anchor −0.077 vs −0.073 known (diff −0.004), offsets −0.045..−0.136 m
(spread 0.090). Peak +4.119 m NAVD88 at 10-30 00:45.
🔴 **Found and fixed on the first build: V3 had no `open_coast_max_y`,** so the 8 m
depth screen hit ALL 406 candidates and the v1.5 limb was under-supported — ocean arm
29 pts (v1.5: 43), Narrows 4 (13), Arthur Kill 5 (15). Now `V1_5_RARITAN.open_coast_max_y`
verbatim → ocean 44 · narrows 13 · arthur_kill 15 · ocean_south 154; 89 tests OK.
⏳ **OPEN (user): the Delaware Bay wedge / Cape May canal mouth is screened as OPEN
COAST.** A northing cannot exempt it. The canal-mouth cluster of 5 (1–6 m) and the
Villas nearshore line are dropped as < 8 m, leaving the largest gaps on the whole
boundary exactly there: 5.97 km at −74.961, 38.984 (bed −1.2 m, the canal mouth), 5.88 /
5.78 km on the two wedge legs at lat 38.88, 4.15 km at −74.985, 38.964. 854 of 6,835
cells sit > 2 km from support, nearly all on the wedge; the rest of `ocean_south` is
86% < 2 km. With the screen off entirely (`--min-depth 0`) the wedge max gap is still
5.88 km (no point ON the legs), so the shallow cluster buys the canal mouth, not the legs.
Options: (a) a wedge exemption box for the depth screen (NACCS's wave setup is small in
the bay, which is the screen's rationale); (b) accept the interpolant — the wedge is a
closure, not the forcing that matters. **DECIDED 2026-08-26 (user: either): (b) — accept the interpolant, no exemption
box.** The wedge is a temporary closure; the planned Delaware Bay expansion re-draws that
edge. Revisit the screen then, not now.

✅ **SUBGRID MEASURED — job 60979984, hal0164, 2026-08-26: peak RSS 30.4 GB, wall
1:06:35 (quadtree ~10 min + subgrid ~55 min over 4 levels, 12/40/160/434 blocks), on
the RESTORED-lever mesh: faces 3,312,567 · active 1,704,096 · mask==2 6,835 · outflow
1,800 — the clean-probe fingerprint counts exactly.** Output `experiments/v3/_subgrid_probe`:
`sfincs.nc` 1.51 GB, `sfincs_subgrid.nc` 1.08 GB (np 3,312,567 × 10 levels, npuv
6,653,590), `roughness.nc` 1.20 GB, `subgrid/*.tif` 2.3 GB — 7.2 GB total. Quota 49.5 G
of 100 G after. sacct says FAILED only because the batch script's final `ls *.sbg` glob
matched nothing (hydromt writes `sfincs_subgrid.nc`, not `.sbg`); `/usr/bin/time` exit 0.
Any 64 G node builds this; `hpc/subgrid_probe_v3.slurm` can drop to `--mem=64G`.

⏳ **OPEN, for the user:** (1) surf-band width (see above);
(2) an ICW eHydro tier — the only southern channel surveys are 2021–2024 sparse
cross-sections (`IW_*_XC`, ~50–150 m between soundings, post the Sandy-funded dredging);
eHydro has NO Mullica / Great Egg / Metedeconk / Townsends / Hereford surveys (not federal
channels). Worth it for the causeway bridges the ICW passes; declare it as its own tier
(`bed-icw` arm-able), never folded silently into the premier bed.

**NEXT = Step 2:** `data_catalog.yml` keys for the v3 tiers (`cudem13_v3`, `gmrt_v3`,
`nj_10ft_dem_v3`, `usace_nj_2010_v3`, `ehydro_south_v3`, `cora_waves_v3`, `cn_v3`,
`usgs_sandy_tidal_v3`, `sandy_storm_tide_south`) + a v3 `elevation_list` (eHydro above
CUDEM); `refinement_v3.geojson`; `probe_mesh_size.py` → coarse-cell decision.

## ⭐ THE v3 BUILD PLAN — written 2026-08-24, measured against what is on disk

The ring is lat 38.855–40.62, lon −75.0–−73.55. Every input was checked for its southern
(and, for the Delaware Bay wedge, western) extent. ✅ = already covers v3; 🔴 = must be
pulled/rebuilt before the mesh; 🟡 = wait for the mesh.

**Step 0 — wire the domain (Claude, next).** `Domain.region` → `region_v3_EDITED_inland`,
clear `acquisition_only`, `latitude` from the real ring, retire the three river
`CROSSINGS` boxes, `STATIONS_V3` = every source AT ITS GAUGE (Toms override dropped),
`obs_gauges`/`hwm_rules` stubs, tests. Everything below selects on the ACTIVE region's
bbox, so it runs AFTER this and not before.

**Step 1 — data pulls that do NOT need the mesh (all bbox-driven; run as one sweep):**

| input | on disk | v3 needs | action |
|---|---|---|---|
| ✅ CUDEM 1/9″, GMRT v3, nj_10ft v3, USACE 2010 v3 | to 38.75 / 38.75 / 38.80 / 38.93 | 38.855 | done. ⚠️ USACE stops at 38.928 = Cape May Point; the Point + wedge sit on 1/9″ CUDEM only. cudem13 1/3″ ends at lon −74.75 — same fallback. |
| 🔴 eHydro channels | `ehydro_south.tif` stops at **39.66** | Barnegat Inlet is in; **Absecon, Great Egg, Townsends, Hereford, Cape May Inlet + CANAL, Cold Spring** are not | new preset(s) in `download_ehydro_nj.py`; 🔴 Philadelphia district = **positive depths** (needs the per-preset sign field). The canal's bed is the one channel a hand-drawn ring made a forcing argument about — survey it. |
| 🔴 HWMs | `sandy_hwms.geojson` 95 marks to 39.71; v1.5's 107 to 40.17 | whole shore | `download_sandy_hwms.py` under v3 → `validation_v3/`. Then re-run the 500 m src-contamination check (FINDINGS §40, per-domain). |
| ✅ MOTF | `sandy_motf_extent_v3.tif` | — | done (superset). `motf_exclude_boxes_ll`: none needed — no NY land; Delaware Bay shore inside the wedge is NJ. |
| 🔴 USGS tidal gauges | `usgs_sandy_tidal_nj.nc` 4 stations, ≥ 39.76 | Atlantic City, Great Egg, Tuckerton, Cape May Harbor, Barnegat Bay | extend the hardcoded list in `download_usgs_sandy_tidal.py` south (NWIS site sweep, site_tp ST-TS / ES). |
| 🔴 STN storm-tide sensors | `sandy_storm_tide_nj.nc` 3, ≥ 39.76 | the southern deployment (Sandy STN had ~20 in Atlantic/Cape May counties) | `download_sandy_storm_tide_sensors.py` south. |
| ✅ NOAA | Battery, Atlantic City, **Cape May** (forcing subset); Sandy Hook in the validation file | — | Cape May is a **forcing input** on v3 (on the canal mouth), Atlantic City is the interior holdout. `n_waterlevel_support` asserted on the mesh, not now. |
| 🔴 discharge | `usgs_sandy_discharge_v1_5.nc`, 8 sources | 6 southern + 5 coastal-creek + Manasquan/Metedeconk at their gauges | `download_usgs_sandy_discharge.py` under v3 → `discharge_v3/`. Daily means only (2012). |
| 🔴 CORA waves | `cora_waves_nj.nc` ≥ **39.35** | 38.85 | `build_cora_waves.py` re-clip; check CORA's grid actually reaches Delaware Bay's mouth. |
| 🔴 curve numbers | `cn_nj.nc` stops at **39.556** | 38.85 | `build_cn_nj.py` under v3 (already domain-aware). |
| ✅ NLCD roughness, AORC precip v3, ERA5 wind (37–42) | | | done. |
| ✅ NACCS | 1,321 pts, Delaware Bay wedge filled | | done; boundary build is 🟡. |

**Step 2 — catalog + template.** v3 `elevation_list` in `data_catalog.yml` (v3 tiers +
southern eHydro, eHydro ABOVE CUDEM), `refinement_v3.geojson` (bay fringe gate — raise
zmax past 2.0, the Keansburg lesson), `probe_mesh_size.py` → face count. ⚠️ v1.5 was
696k faces on 5,700 km²; v3 is 15,087 km², mostly coarse upland — expect ~1.5–2 M and
SnapWave to be the cost. Decide the coarse-cell size from the probe, not by analogy.

🔴 **Step 3, FIRST: the bridge-as-dam sweep (user, 2026-08-24).** Lidar puts a bridge deck
on the bed and the model reads a causeway as an earthen dam — the Shrewsbury lesson
(`shrewsbury_ehydro_2015` exists because of it). On v3 the exposure is far larger: the
whole ICW, the Route 72 (Manahawkin), Route 52 (Ocean City), Parkway (Mullica, Great Egg,
Cape May Canal), Route 30/40/322 (Absecon) and Townsends/Corson's inlet crossings, plus
the canal's three bridges. eHydro covers the canal and the two inlets; everything else is
CUDEM. Sweep the probe's merged bed along every estuary axis and the ICW for ridges that
rise above −1 m across a wet channel, BEFORE freezing — a dam found after the freeze is a
new domain.

**Step 3 — mesh-dependent (🟡).** `build_naccs_boundary.py` under v3 (support selection
reads `mask==2`; assert the 3-gauge NOAA support count here), `no_waterlevel_boxes` = none
on rivers (all dry) — only the canal-mouth/wedge check that NOAA and NACCS agree there,
`check_naccs_vs_sensors.py` south, src-contamination sweep on the HWMs, dry-crossing
creek sweep (which gauged creeks cross the ring on land with no source — Absecon is
inside now, re-run the list), then freeze + fingerprint + `EXPECTED["v3"]`.

**Step 4 — arms.** `naccs-premier`, `naccs-nowaves`. Pre-registration before the scorer:
the interior holdouts are Atlantic City + the southern USGS tidal gauges; the flanking
check at Cape May is a FORCING diagnostic (it is on the boundary).

### ✅ 2026-08-24 (later) — the inland move is DRAFTED, MEASURED and GATED; the user draws the real ring

**The v3 MOTF sheet is rendered** — `data/validation_v3/sandy_motf_extent_v3.tif`, 1,443 km²
on the acquisition rectangle (deliberately a superset: the sheet is a domain-DESIGN input;
scoring restricts to the run's own `msk`, so no re-render when the polygon lands). The
renderer is now **tiled** — the Rutgers service caps one export at 4096 px and v3 needs
9,256 × 13,173 at 15 m. Figure: `reports/figures/motf_v3_vs_ring_EDITED.png`.

**What the EDITED ring excludes, measured:** 588 km² of MOTF surge lies outside it. Only
two patches are ours — **Great Egg + Tuckahoe up to Mays Landing / Head of River,
122 km²** and **Mullica + Wading + Bass up to Batsto, 116 km²**. The rest is Delaware Bay
shore (200 km² at Dennis/Maurice), the tidal Delaware at Trenton (62 km²) and the Raritan
above v1.5's cuts — all out of scope. Plus 2.8 km² above the Toms cut and 1.9 km² at the
Metedeconk.

⭐ **The head-of-tide insight: moving the landward edge to the gauges turns every southern
river cut DRY.** The DEM under each head-of-tide gauge is ≥ +1 m (Tuckahoe 1.0, E Br
Bass 1.9, Batsto 3.6/4.2, Oswego 4.9, W Br Wading 6.3), so a ring through them crosses
the rivers on `bed ≥ 0` — the validator classes it LAND, hydromt puts NO water-level or
outflow BC there, and the discharge source sits at the gauge, inside. No
`no_waterlevel_box`, no pumping, no Navesink drain. This is strictly better than the
Raritan pattern where the geography allows it; the Raritan pattern stays for Toms (and
for v1.5, whose cuts are on tidal water by necessity).

**`data/region_v3_DRAFT_inland.geojson`** — 53 vertices, vertices 0–40 identical to the
EDITED ring, then: W Br Wading at Jenkins (−74.555, 39.700) → west of the Mullica gauge
(−74.690, 39.690) → west of Batsto (−74.680, 39.620) → above Lake Lenape / Mays Landing
(−74.745, 39.478) → west of Head of River (−74.835, 39.322) → EDITED v42, v43 → land N of
the canal's Delaware Bay mouth (−74.958, 38.985) → Delaware Bay (−74.985, 38.975) →
(−74.985, 38.880) → EDITED v46. Area 13,628 → 14,786 km² (+1,157, pine barrens above
+3 m — mostly inactive cells). Figure `reports/figures/region_v3_draft_inland.png`.
🔴 **It is a DRAFT for QGIS, not the ring** — the user draws the ring (v1.5 rule).

**Gate on the draft: `validate_region_v3.py --region data/region_v3_DRAFT_inland.geojson`
→ exit 0, 18 declared reaches.** `great_egg_tuckahoe` and `mullica_lower` boxes match
NO reach (the cuts are dry now — retire those boxes when the real ring lands).
`toms_river` is the only wet river cut left. MOTF inside 1,003 → **1,254 km²**; the only
surge left outside on the Atlantic side is the 2.8 km² above Toms and 1.9 km² Metedeconk.

🔴 **THE CAPE MAY CANAL WAS BEING CUT, and the validator could not see it.** A 10 m walk of
the EDITED ring's seg 43→44 on 1/9″ CUDEM finds **110 m wet, bed −4.23 m at (−74.924,
38.962)** — mid-canal, 2.5 km from its bay end. The validator resamples the bed to 3″
(~75 m) with `-r max`, which erases any channel narrower than that; it now lists
sub-threshold reaches with a `CHANNEL?` tag, but a 100 m canal on a 75 m max-grid is still
invisible. 🔴 **Any hand-drawn segment near a canal or tidal creek needs a 10 m walk on
1/9″ CUDEM** (the snippet is in this session's log; worth a `--fine` flag).
⭐ **NOAA 8536110 Cape May sits ON the canal's Delaware Bay mouth, (−74.960, 38.968)** —
it is in `noaa_sandy_nj.nc` already. So it is a forcing INPUT on v3, like the Battery on
v1.5, NOT an interior holdout; `n_waterlevel_support` reasoning must reflect that.

**The draft's Cape May answer (user's rule: do not cut the canal):** leave land north of
the canal mouth (draft seg 47→48 walked at 10 m: **0 % wet, min +1.02 m**), step into
Delaware Bay and run a **forced wedge** ~1.5 km offshore round Cape May Point to the south
closure — `cape_may_bay` box in `CROSSINGS`, 12.25 km, min bed −9.8 m. Both canal ends are
then inside the domain and the bay end sees the forced Delaware Bay level. NACCS on the
wedge is THIN: sp7548 (4.8 m) and sp15260 (8.4 m) only, 2 pts within 6 km at lat 39.0.
⭐ **Ask of the user (they offered): NACCS save points lon −75.00..−74.94, lat
38.90..39.00** — the wedge and the canal mouth — plus 2–3 north along Villas (39.00–39.05)
for margin. The MOTF flooding on the Delaware Bay shore NORTH of the canal mouth stays
outside (Delaware Bay coast, out of scope — say so in the write-up).

**Gauge sweep (PICK UP #4, done once, 117 NWIS sites in the box, 61 with a Sandy daily
record; table in the session log):** peak southern inflows are small — Manasquan 18.4,
W Br Wading 17.7, Toms 13.9, Oswego 12.5, Great Egg/Folsom 10.1, Mullica/Batsto 8.0,
Tuckahoe 7.1, Cedar 6.1, Mill/Manahawkin 4.6, Westecunk 3.7, Absecon 3.5, Oyster 3.3,
E Br Bass 2.0 m³/s. **River flow is not why these valleys flood; the sources exist so the
model does not DRAIN them.** 🔴 **`01409500` Batsto R at Batsto (67.8 mi²) has NO Sandy
record**, so the Mullica's gauged ~211 mi² is a lower bound (Batsto R is ungauged for
Sandy, like the Middle River and Wrangle Brook). Cedar, Oyster, Mill, Westecunk, Absecon
gauges are already INSIDE the ring — they become in-domain sources at the gauge.

⚠️ **Metedeconk:** the inherited seg 38→39 crosses its tidal reach in a 54 m wet reach,
bed −1.07 m at (−74.134, 40.065) — sub-threshold, undeclared, same family. v1.5's
Metedeconk src (−74.115, 40.056) is 1.6 km INSIDE it. Fix in the same QGIS pass: swing the
segment west of the Lakewood dam (Lake Carasaljo, −74.21, 40.09) so the cut is dry, and
move the src to the gauge (`01408120`, +3.7 m). Manasquan src (−74.095, 40.114) is inside
by 1.3 km and its crossing is dry — leave it.

**Then, in order:** (1) user redraws in QGIS from the draft; (2) gate it; (3) sources:
Tuckahoe `01411300`, Great Egg `01411000` (at Folsom, 20 km above Mays Landing — place the
src at the gauge, it is inside), Mullica `01409400`, W Br Wading `01409810`, Oswego
`01410000`, E Br Bass `01410150`, plus the five coastal creeks above, all AT THE GAUGE;
`no_waterlevel_box` only on Toms; (4) retire the two river boxes; (5) clear
`acquisition_only`, refinement, `probe_mesh_size.py`.

✅ Deletion manifest EXECUTED 2026-08-21 on the user's sign-off — 10.5 G reclaimed,
quota 65.22 G, details at the top of
`reports/cleanup/deletion_manifest_2026-08.md`. Kept: `sfincs-env.tar.gz`,
`.vscode-server`, the blocked 16.5 G `.ige`.

### ✅ THE WEIR IS PROMOTED — executed 2026-08-21 (user decision), FINDINGS §38

The Keansburg protection line is now part of the domain's model config, staged in the
TEMPLATE so **every arm inherits it** (a premier-only weir would confound
premier-vs-nowaves forever). No new solver time was spent: the verified-WHOLE weir
runs — byte-identical stagings plus exactly the one `weirfile` line, full window —
were ADOPTED as the arms.

- `data/structures_v1_5/keansburg_weir.weir` (+ PROVENANCE.md) is the durable source;
  `_template_sealed` carries `sfincs.weir` + the `weirfile` key (fingerprint
  unmoved, audit 8/8); `model.finalize` re-adds the key if hydromt's writer drops it
  (`_ensure_weirfile_key`, pinned by `tests/test_weir_staging.py` — the latitude
  failure shape).
- Run dirs: `naccs-premier` ← `diag-premier-keansburg-weir`,
  `naccs-nowaves` ← `diag-nowaves-keansburg-weir`; the pre-weir runs are banked as
  `preweir-naccs-premier` / `preweir-naccs-nowaves` (provenance.txt in all four
  records the rename). Last pre-weir scoring banked at
  `metrics_2026-08-21_pre_weir_rebaseline.csv`.
- **New headline (weir premier): HWM RMSE 0.4084, bias −0.037** (pre-weir 0.4018 /
  −0.081 — bias halves; `raritan_bay` RMSE 0.452 → 0.405 with the pocket outlier
  fixed), **CSI 0.7044, POD 0.8214, FAR 0.1682** (pre-weir 0.7108 / 0.8384 / 0.1764
  — POD drops because the weir correctly dries a pocket the MOTF bathtub wrongly
  floods), CSIc 0.7893. nowaves: HWM RMSE 0.3867, flagged `extent_admissible=False`
  as always. Tests re-pinned with BOTH baselines in their docstrings; 73 OK; port
  gate bit-for-bit.
- ⚠️ `diag-premier-norain` remains a rain-off copy of the PRE-weir premier. Its
  banked result (FINDINGS §39) is untouched; a rain diagnostic on the weir baseline
  would need a fresh staging.

✅ **The diag runs are ACCEPTED (user decision, 2026-08-21):** visual inspection +
the `output WHOLE` audit, waiving the >26 h three-clock re-audit. Neither diag run
ever had a halk submission against its directory (the clobber's precondition), and
no halk job has run since the exclude line landed. The two sections below are no
longer provisional; the rain share is written into **FINDINGS §39** and the weir
decision-run result into **FINDINGS §38**.

### ✅ 2026-08-21 — rain ground truth: the FA classifier is validated (FINDINGS §39)

`scripts/measure_rain_share.py` (pre-registered diagnostic in its docstring, written
before the numbers) → `reports/rain/rain_share.csv`, premier vs `diag-premier-norain`
on the MOTF grid, same screens as `motf_metrics` + simulated-in-BOTH:

| field | value |
|---|---|
| FA total | 11.40 km² |
| **FA rain share** (wet-in-premier ∧ dry-in-norain) | **75.7%** (8.62 km²) |
| `disc_precision` — P(rain-true \| labelled disconnected) | **0.991** |
| `disc_recall` | 0.914 |
| flip-marginal FA (premier depth within 5 cm of DEPTH_MIN) | 1.35 km² |
| rain share of the WHOLE premier wet extent | 19.7% |

The connectivity heuristic is a near-perfect rain detector on this domain: 99% of
disconnected-labelled FA is dry with rain off, and it catches 91% of the rain-true FA
(conservative in the direction fa_decomp claims). The 70%-of-FA figure from the
classifier was, if anything, an undercount (truth 75.7%).

### ✅ 2026-08-21 — weir decision inputs (FINDINGS §38; pre-reg:
`reports/keansburg/preregistration_weir_decision.md`, written first)

`diag-premier-keansburg-weir` (A) vs `naccs-premier` (B):

1. **Primary — pocket marks: PASSED.** 6155/6156/6133 model 2.45–2.46 m (residual
   +0.87–0.91, was +1.68–1.77). Same capping as the nowaves pair (FINDINGS §38).
2. **Paired HWM: the pre-registered bound is NOT met as stated, and the failure is
   the bay band, stated honestly.** Δ RMSE +0.007 m, 95% CI [−0.114, +0.120], n=46
   (A RMSE 0.4084 vs B 0.4018). The CI is inflated by ±0.13–0.43 m residual moves at
   marks 12–15 km from the weir on BOTH flanks (Navesink shore, Perth Amboy/Ward
   Point; worst 6406 +1.03) — see the his-ringing entry below for why that is not
   weir physics.
3. **Extent: the expected signature.** Domain CSI 0.7108 → 0.7044 (POD −0.017,
   FAR improves 0.1764 → 0.1682). Keansburg box (−74.155..−74.105, 40.425..40.455):
   CSI 0.761 → **0.783**, FA 1.28 → **0.52 km²**, miss 0.24 → 0.68 km² (MOTF floods
   the pocket too — bathtub, no structures — so drying it correctly books "misses"
   against a reference error).

Recommendation to put to the user: the physical case for promotion is strong
(pocket capped, box extent better, FAR better); the domain-wide HWM delta is a wash
inside the ringing band. Decision is the user's.

### 🔴 NEW 2026-08-21 — the bay rings DIFFERENTLY BETWEEN ARMS on the 10-min his

Measured comparing `sfincs_his.nc` of the two waves-on premier-physics arms (differ
only by the 2 km weir): instantaneous |Δzs| reaches **1.32 m at Arthur Kill mouth
(inside the crest window)**, 0.58 m Great Kills, 0.4–0.8 m at the Narrows (mostly
pre-storm) — while CREST PEAKS differ only −0.03..−0.15 m and the open coast is
clean (≤0.04 m; Shark River 0.004 m). So the arm-dependence is in the PHASE of
large fast bay oscillations and it is in the 10-min series itself — **not merely
zsmax sub-hourly excess**. Consequences:
- The "do not quote a Raritan Bay HWM/extent difference between waves-on and
  waves-off arms" caveat extends to ANY pair of arms: a local perturbation re-rings
  the whole bay at the ±0.1–0.4 m level at marks 12–15 km away.
- ✅ Mechanism SETTLED 2026-08-21 (FINDINGS §40): a **coherent seiche**, not chatter.
  This measurement's reading — envelope robust, phase not — is exactly what a real
  basin oscillation sampled by a running max produces, and it is now the explanation
  rather than an open question.

### ✅ 2026-08-21 — housekeeping landed with the above

- `scripts/paired_hwm_bootstrap.py` was missing the 2026-08-17 region clip and
  scored n=53 / RMSE 1.21 (the documented artefact). Now applies `_clip_to_region`;
  premier reproduces the pinned 0.4018 / −0.0806 at n=46.
- `plot_motf_panels(split_fa=True)` draws never-sea-connected FAs in tan with
  CSIc/FARc beside the headline keys (never instead); connectivity shared with
  `fa_decomp.sea_connected` so panel and CSV cannot disagree.
- Advisor notebook: `notebooks/v1_5_raritan/sandy-v1_5-viz-2026-08-21.ipynb` —
  executed clone with the boundary-support figure (71/71 NACCS points inside the
  domain vs 0/2 for the 2-node interpolant) and the split-FA MOTF panels. The
  original keeps its pre-rebaseline outputs deliberately (side-by-side demo).
- `sfincs-env.tar.gz` rebuilt (880 M, deleted in the 08-20 cleanup; `hpc/pack-env.sh`)
  and deployed to `/tmp/tpj8/sfincs` on hal0308; `sfincs` + `sfincs-local` Jupyter
  kernels registered.
- `scripts/score_v2_barnegat.py` docstring reworded — it tripped the repo-hygiene
  archive grep ("symlink" beside the archive name). 68 tests OK, port gate passes.

📋 The original plan this work follows is frozen at
[docs/plan_v1_5_original.md](plan_v1_5_original.md) (Phases 1–4 and 6 are done; 5 and 7 are
live). **This file is authoritative for what remains** — the plan is the record of what was
intended, not of where things stand.

---

## Where we are

The repo has been stood up and the code ported from `~/nj_coast_sfincs`
(commit `21e28f2`, see [ARCHIVE.md](../ARCHIVE.md)). **The port gate passes.** The two manual
gates below both passed on 2026-08-13.

**v1.5 is FROZEN and the first sweep has COMPLETED (2026-08-14).**
`data/frozen_mesh_v1_5_raritan_z10` exists and `premier.EXPECTED` carries the fingerprint —
`faces=696230 boundary_edges=1652 sha(z,mask)=2a23667dd16e449c`; `python -m nj_sfincs.premier`
reports **4/4** (template + three staged arms). Everything below that still reads "nothing may
be staged or run yet" describes the road to that freeze, not the current state.

| arm | job | node | elapsed | `sfincs_map.nc` | SnapWave | state |
|---|---|---|---|---|---|---|
| `naccs-premier` | 60582145 | hal0338 | 2:19:46 | 1.10 GB | 88.6% | ✅ ran clean — **output later destroyed** |
| `naccs-nowaves` | 60582164 | hal0388 | 0:09:27 | 243 MB | — | ✅ ran clean — **output later destroyed** |
| `noaa-2node` | 60582165 | hal0391 | 1:36:07 | 1.09 GB | 89.0% | ✅ ran clean — **output later destroyed** |

⭐ **These three runs were CORRECT.** They landed on `hal*`, closed with a full timing block,
and the sizes above are real — the 2026-08-16 re-run of `naccs-nowaves` reproduced **243.0 MB**
exactly. The 08-14 sweep was never scientifically void; only its output was lost.

### 🔴 THE `halk*` NODES CLOBBERED ALL THREE, ~25 h LATER — diagnosed 2026-08-16

Each arm was submitted **twice**: once onto a `halk*` node (before the exclude line existed),
once onto a good `hal*` node, **both against the same run dir**.

| arm | halk attempt | fate | hal attempt | fate |
|---|---|---|---|---|
| `naccs-premier` | 60582058 · halk0064 | CANCELLED 19:48:41 | 60582145 · hal0338 | ✅ 19:59:30→22:19:16 |
| `naccs-nowaves` | 60582059/60582146 | ended 19:32 / CANCELLED 20:11:14 | 60582164 · hal0388 | ✅ 20:13:41→20:23:08 |
| `noaa-2node` | 60582060/60582147 | CANCELLED 19:48:41 / 20:11:14 | 60582165 · hal0391 | ✅ 20:13:41→21:49:48 |

The good runs finished and wrote correct output. **On 08-15 evening the dead halk jobs'
buffered writes finally landed on top of them**, leaving 29% / 86% / 11% of the window and, on
the two waves-on arms, an `zsmax` that is entirely fill.

🔴 **It is invisible to `ls`, because the clobbered file carries the HALK job's mtime.** Three
clocks disagree, and that is the only tell:

| | premier `sfincs_map.nc` |
|---|---|
| GPFS creation (`mmlsattr -L`) | 08-14 **19:59:47** — the *hal* job, to the second |
| mtime (`stat -c %y`) | 08-14 **19:47:41** — the *halk* job that died before it |
| ctime (`stat -c %z`) | 08-15 **20:42:16** — when the clobber landed |

Proof the content changed rather than the metadata: the floodmap cached 08-15 12:24 holds
**11,985,450** valid pixels, and the same downscale from the file as it stood on 08-16 yields
**0** — its `zsmax` is 0 finite of 2,088,690.

⚠️ **Not the quota, and not an external sync.** No SFINCS job ran on 08-15; GPFS snapshots are
weekly and the newest (`cache.2026-08-11`) predates the sweep, so there was no recovery path.
`dedupe_home.py` is cleared — it groups by exact size then full SHA-256 and cannot link
non-identical files.

✅ **Re-submitted 2026-08-16** on `hal0384/0385/0386` with `sfincs-desktop.sif` (Faber, the
engine the 08-14 output records) via `run.submit_slurm(dir, sif=...)`, `--time=12:00:00`:
jobs **60622418** premier · **60622419** noaa-2node · **60622420** nowaves.
`naccs-nowaves` is back and **WHOLE** — 73/73 map steps, 433/433 his steps, all three `zsmax`
blocks written.

⭐ **`premier.output_complete()` now exists and is the guard that was missing.** Every other
check in `premier.py` tests *identity* — that a run is on the domain it claims. Nothing tested
that output is *whole*. `python -m nj_sfincs.premier` now reports `output WHOLE` /
`OUTPUT TRUNCATED` / `no output` per run dir and names the shortfall. It is wired into the
audit only, never into a staging assert, so it cannot block a build.

✅ **ALL THREE ARMS ARE BACK AND WHOLE — re-run 2026-08-16, verified 2026-08-17.**
Jobs **60622418** premier · hal0384 · 1:38:23 · 1.096 GB · SnapWave 89.4% ·
**60622419** noaa-2node · hal0385 · 1:35:20 · 1.094 GB · SnapWave 89.4% ·
**60622420** nowaves · hal0386 · 0:09:27 · 243.0 MB. All three closed with a full timing
block; `NJ_DOMAIN=v1_5_raritan python -m nj_sfincs.premier` reports **4/4, `output WHOLE`**.

⭐ **The clobber did NOT recur, and the timestamps are the proof.** On each `sfincs_map.nc`,
mtime **==** ctime **==** the job's own end time to the second (11:15:35 / 11:12:32 /
09:46:39). Only GPFS creation still reads 08-14 — the inode was made then and rewritten in
place, which is expected. Checked at 2026-08-17 12:00, ~26 h after the runs, i.e. **past the
~25 h window in which the 08-15 clobber landed.** `sacct -u $USER -S 2026-08-15` shows no
`halk*` job at all since the exclude line went in.

✅ **SCORED 2026-08-17.** `experiments/v1_5_raritan/metrics.csv` + `report.html` exist.
The three stale floodmap caches self-invalidated on mtime exactly as designed
(`validate/core.py:529`) and were rebuilt 12:07–12:12. `naccs-nowaves` came back
`extent_admissible=False`. ⚠️ At that time the runner also DELETED its CSI/POD/FAR; since
2026-08-20 it keeps them and only flags them (FINDINGS §4).

### 🔴 THE FIRST SCORES WERE 3/4 ARTEFACT — out-of-domain HWMs scored as DRY, fixed 2026-08-17

The first `metrics.csv` reported `hwm_rmse_scored_m` = **1.210 m**. The real figure is
**0.402 m**. The difference was **7 marks that are not in the model at all.**

`score_hwm` deliberately does not drop a mark the model leaves dry — it scores it against
`nanmin` of the nearby BED, so "the model says water never got above this ground" still
counts against the model. That is right for a mark inside the domain. 🔴 **`da_dep` is the
downscaled subgrid DEM, and it carries valid bed values across the whole grid RECTANGLE,
including every cell the region clip made inactive.** So a mark outside the region finds
finite ground, never finds water, and books a residual of (bare earth − observed flood
elevation). It never drops out, because dropping out requires NaN bed.

| set | n | bias | RMSE |
|---|---|---|---|
| inside the region | 46 | −0.081 | **0.402** |
| outside it (**all 7 dry**) | 7 | −2.788 | 3.165 |
| what the CSV first reported | 53 | −0.438 | 1.210 |

⭐ **All 7 dry marks were outside the region; there were ZERO dry marks inside it.** The
domain does not have a wet/dry problem — it was being scored against Staten Island.

⚠️ **This is the same confusion as `_fill_inactive_holes` (2026-08-14), one section below.**
After a region clip, "outside the domain" and "inside the domain" are indistinguishable to
anything reading only a raster. Every piece of code reasoning about cells beyond the mask
has to be told which is which.

✅ **Fixed by `_clip_to_region` in `validate/metrics.py`**, applied where the marks are
loaded so every downstream key inherits it, and applied to the same two places in
`plots.py` so the panels cannot plot marks the CSV never scored.
`tests/test_hwm_region_clip.py` pins it.

⭐ **SAFE FOR THE PORT FIXTURE BY MEASUREMENT, NOT BY ARGUMENT.** `v1_monmouth` has 0 scored
marks outside its region and 0 dry marks, so clipping 32 of its 95 changes nothing:
`scripts/verify_port.py` still passes **bit-for-bit**, `hwm_n_scored` still 38,
`hwm_bias_scored_m` still −0.363105931. That check is the reason this was safe to land.

#### ✅ PAIRED, on the 46 in-region marks — and the artefact was DILUTING the signal

The 7 out-of-domain marks are dry in both arms, so they contribute a near-identical large
residual to each and compress the RMSE difference toward zero. Removing them roughly
**triples** the measured effect.

| comparison | Δ on 53 (contaminated) | **Δ on 46 in-region** | 95% CI | P(A better) |
|---|---|---|---|---|
| premier − noaa-2node | −0.0223 | **−0.0717** | [−0.161, −0.013] | 0.994 |
| premier − nowaves | −0.0142 | **−0.0469** | [−0.108, −0.008] | 0.995 |

Both CIs exclude zero. `naccs-premier` RMSE **0.402** vs noaa-2node **0.474** vs nowaves
**0.449**; bias −0.081 / −0.255 / −0.037.

🔴 **This is a FORCING-DENSITY result, not the boundary-move argument.** It says dense NACCS
forcing beats 2-node NOAA forcing *on this domain*. It is NOT the v1_monmouth comparison
CLAUDE.md warns about (ΔRMSE −0.042, CI [−0.238, +0.137], P = 0.706, 38 marks), and it does
not make the boundary relocation an empirical result. **The case for v1.5 remains
STRUCTURAL.**

⚠️ No pre-registration was written before this scorer run.

#### Other first-read numbers

| | premier | noaa-2node | nowaves |
|---|---|---|---|
| `motf_csi` | **0.662** | 0.652 | not scored at the time |
| Great Kills peak err (m) | −0.385 | −0.281 | −0.374 |

Great Kills is the one true interior holdout (8.85 km from any arm, so the model COMPUTES
it) and every arm runs ~0.3–0.4 m low there — close to the **−0.350 m** that NACCS itself
runs low at that sensor (§ "NACCS vs those sensors"). ⚠️ Suggestive only: that NACCS figure
is a high-water-only comparison at n=112, and NACCS forces nothing within 8.85 km of it.

⚠️ **Per-basin counts still do not match the classification table above** (46 scored vs 69
in-region). `score_hwm` also keeps only `quality <= 2`. Reconcile before quoting per-basin
numbers — the table and the CSV count different populations.

### ✅ The v1 southern estuary gauges are now on v1.5 — re-run 2026-08-17

Jobs **60657512** premier · **60657513** noaa-2node · **60657514** nowaves, on
hal0259/0260/0262. Adding the three v1 gauges — Shark River, Shrewsbury, Sea Bright
open-coast — takes v1.5 from 5 observation points to **8**.

⭐ **No mesh rebuild and no re-stage.** Observation points are diagnostic: SFINCS writes a
series at each into `sfincs_his.nc` and the solution does not depend on them. But
`sfincs.obs` is only written inside `build_static`, behind the subgrid, and `build_template`
`rmtree`s its target. `scripts/sync_obs_points.py` rewrites the text file from the registry
instead. 🔴 **It verifies the format rather than assuming it** — it regenerates the file from
the points ALREADY in it and refuses to write unless that reproduces the existing bytes.

🔴 **v1's COORDINATES DO NOT TRANSFER, AND THE FAILURE WOULD HAVE BEEN SILENT.** v1.5 refines
the quadtree differently in the southern estuaries: all three v1 points land on DRY BANKS
here — bed **+3.48 / +4.42 / +3.57 m** on the sealed template. `usgs_tidal_sea_bright`'s
famous 21 m nudge was tuned on v1's faces and is worth nothing on these. A bank cell only
wets during the storm, so every pre-storm tide and phase metric would return NaN without
raising — exactly the scar `premier.obs_points_ok` was generalised for.

So each gets its own v1.5 entry, nudged to the nearest `mask==1` face with bed < −1.0 m:

| gauge | nudge | v1.5 bed | v1 |
|---|---|---|---|
| `usgs_tidal_sea_bright` | 24.8 m | −4.20 | −4.33 at a 21 m nudge |
| `usgs_tidal_shark_river` | 35.0 m | −2.22 | map-sourced (its v1 point was a +1.79 m bank) |
| `usgs_stormtide_sea_bright` | **105.9 m** | −1.19 | published coords |

⚠️ **The open-coast SSS nudge is the big one.** The nearest wet face is offshore of the beach
the sensor sits on; its published cell is +3.48 m and would wet by only ~0.9 m at the
observed 4.4 m peak, and a barely-wet cell is a bad place to read a modelled crest. Read that
panel as **the model's nearshore level, not the model at the sensor**.

⭐ Shark River gains resolution over v1: v1 had to fall back to `series_source="map"`
(hourly) because its point was on a bank, while v1.5 has a wet face 35 m away and can be
scored off `his` at 10 min.

⚠️ **There is NO Navesink gauge.** `usgs_sandy_tidal_nj.nc` holds 4 stations, of which only
1407770 (Shark R) and 1407600 (Shrewsbury) are inside v1.5; 1408168 and 1409125 are south of
lat 40.150. The Navesink is an HWM basin only — `shrewsbury_navesink`, 12 marks, and it is
the **best**-scoring basin on the domain (bias +0.013, RMSE 0.185).

#### ⏳ PICK UP HERE — rescore, then re-execute the notebook

✅ **THE RE-RUN LANDED AND THE ARMS ARE WHOLE — verified 2026-08-20.**
`python -m nj_sfincs.premier` reports `output WHOLE` for all three and **4/4 on domain**.
Map sizes reproduce `map_sizes_pre` byte for byte (premier 1,095,742,111 · noaa-2node
1,094,248,175 · nowaves 242,972,872). Three-clock check clean — `mtime == ctime` on all
three, so these were in-place re-runs, not the `halk` late-flush signature.

✅ **RESCORED 2026-08-20 — the gate PASSED on every pinned number.** `--validate-only`
on all three arms against the verified-WHOLE re-runs:

| arm | HWM RMSE (median, 50 m) | bias | CSI | POD | FAR |
|---|---|---|---|---|---|
| `naccs-premier` | **0.401777** (= the pinned 0.402) | −0.081 | **0.6846** | 0.8207 | 0.1950 |
| `naccs-nowaves` | 0.448715 | −0.037 | 0.6663 ⚠️ `extent_admissible=False` | 0.7910 | 0.1913 |
| `noaa-2node` | 0.473515 | −0.255 | 0.6738 | 0.8026 | 0.1924 |

n=46 scored, 0 dry, on every arm — exactly the pre-re-run HWM numbers, as diagnostic obs
points must produce. CSI/POD/FAR match the expected post-active-mask-screen values to
4 decimals. `metrics.csv` + `report.html` rewritten 2026-08-20.

🔴 **This is the LAST SCORING OF `noaa-2node`.** Decision (user, 2026-08-20): NACCS
forcing is adopted going forward and the 2-node interpolant is retired from future
sweeps. Its banked result — the forcing-density comparison above and the paired
Δ = −0.0717 [−0.161, −0.013] — is the record; the arm will be retired from
`experiments.py` (run dir and scores kept).

⚠️ These CSI values are the **pre-Staten-Island-screen baseline**, banked deliberately:
the MOTF raster is NJ-only and stops at lat 40.5283 (rendered on the v1_monmouth bbox),
so v1.5's SI sliver scores as false alarm and its northern 9 km is unscored. The full
3-arm pre-rebaseline CSV is preserved at
`experiments/v1_5_raritan/metrics_2026-08-20_pre_motf_rebaseline.csv` — the ONLY place
noaa-2node's final per-basin keys live.

### ✅ MOTF REBASELINED 2026-08-20 — own render + NJ-validity screen, same session

Two defects, one fix, landed together (`Domain.motf_tif` + `Domain.motf_exclude_boxes_ll`):

1. **The archived sheet was rendered on the v1_monmouth bbox** and stops at lat
   40.5283 — the Narrows and the upper SI shore were silently unscored. v1.5 now
   scores its own render, `data/validation_v1_5/sandy_motf_extent_v1_5.tif`
   (`download_sandy_motf_extent.py` grew the same domain-output guard as the HWM
   downloader; the archived raster cannot be overwritten).
2. **The MOTF source layer is NJ-ONLY and its pixels are only {0,1}** — nodata never
   occurs — so NY land reads as *confidently dry* and every model-wet Staten Island
   pixel booked a false alarm the sheet cannot adjudicate. Two exclude boxes
   (`staten_island`, `brooklyn_rockaway`), validated against the `nj_10ft_dem`
   footprint (an NJ-only product, so its data extent IS the NJ discriminator):
   0 NJ pixels inside either box; Ward Point in, Perth Amboy out.

| arm | CSI | POD | FAR | vs pre-rebaseline |
|---|---|---|---|---|
| `naccs-premier` | **0.7108** | 0.8384 | **0.1764** | CSI 0.6846, FAR 0.1950 |
| `naccs-nowaves` ⚠️ | 0.6920 | 0.8086 | 0.1724 | (flagged, as before) |

New CSV key `motf_km2_excluded_boxes` = **13.98 km²** (what the NJ screen removed from
the scored set — quote it beside the CSI). `motf_km2_unsim_motfwet` is now 18.65 km²:
the new sheet's bbox includes real Sandy flooding up the Raritan valley outside the
region, correctly screened as unreachable. HWM side untouched — RMSE 0.401777 exactly.
`tests/test_motf_simulated_mask.py` re-pinned with both baselines in its docstring;
port gate bit-for-bit (v1_monmouth keeps the archived sheet and declares no boxes).

### ✅ THE FALSE ALARMS ARE MOSTLY NOT SURGE — FA decomposition landed 2026-08-20

MOTF is a surge-only bathtub and cannot contain rain ponding; our arms force AORC rain
with infiltration effectively OFF (`model.py:1398-1408` strips the CN keys —
`create_cn` runs but writes no file, so rain lands on impervious-in-effect ground).
`validate/fa_decomp.py` splits every false-alarm pixel by whether its water EVER had a
wet surface path to tidal water (`hmax` is a running max, so its footprint is the
union of everything ever wet; a component that never touches the sea got its water
from rain/runoff, not surge). On the rebaselined premier:

| | km² | share of FA |
|---|---|---|
| FA, connected to the sea | 3.45 | 30% |
| **FA, never connected** | **7.96** | **70%** |
| of which within the LOCAL rain total | 0.0 | (bound is conservative — see test) |

`motf_far_connected` **0.061** vs `motf_far` 0.176; `motf_csi_connected` **0.795** vs
0.711. ⚠️ Diagnostic keys, ALWAYS reported beside the headline keys, never instead.
`naccs-nowaves` decomposes almost identically (disconnected 7.49 km²) — consistent
with the disconnected share being rain, which is arm-independent.
`tests/test_fa_decomp.py` pins it.

⏳ **`diag-premier-norain` RUNNING — SLURM 60700612, hal0338, submitted 2026-08-20.**
Byte-identical staging of `naccs-premier` (bulk inputs hardlinked, ~0 disk; fingerprint
verified 6/6; `snapwave.upw` deliberately NOT linked — the solver regenerates it in
place, and a shared inode would clobber premier's copy) minus the `netamprfile` line:
rain OFF, everything else identical. Read it as ground truth for the classifier:
wet-in-premier ∧ dry-in-norain ≈ the rain share of the extent. Not in `experiments.py`
by design — the `diag-nowaves-fasthis` precedent: diagnostics are staged by hand and
documented, not registered where `--experiments all` can re-stage them.

⚠️ The floodmap caches for premier and noaa-2node were stale against the re-run and were
rebuilt 2026-08-20 (~3 min each). That is the mtime invalidation working, not a fault.

🔴 **DO NOT TRUST ANY PREMIER / NOAA-2NODE NUMBER UNTIL `python -m nj_sfincs.premier` REPORTS
`output WHOLE` FOR BOTH.** Mid-run they read back as a plausible-looking catastrophe — the
notebook was run against the half-written files and produced `median −1.87 m, 20 of 46 dry`
and `CSI 0.20`, because output stopped at hour 48.0 of 72 and Sandy's crest is at hour 48.7.
The arms were fine; the files were half there. The audit named it immediately
(`OUTPUT TRUNCATED — ends at 48.0 h of 72.0 h`), which is exactly what `output_complete()`
exists for.

⚠️ **Every score in this file above is from the PRE-re-run scoring, and every CSI / POD /
FAR in it also predates the active-mask screen** (FINDINGS §37) — those are two separate
reasons the extent numbers above are stale. Observation points are diagnostic and cannot
change the solution, so the HWM side should return to **RMSE 0.402** exactly; if it does
not, chase that before reporting the new number.

⚠️ The notebook has the CORRUPTED figures embedded in its outputs from that mid-write run.
Re-execute it after the rescore before those outputs are committed.

✅ **The interior holdouts ARE registered** — checked 2026-08-15, `domain.py:643`:
`obs_gauges=(_SSS_GREAT_KILLS, _SSS_ARTHUR_KILL, _SSS_NARROWS_SI, _SSS_NARROWS_BKLN,
_SANDY_HOOK)`, all four reading `gtsm/sandy_storm_tide_raritan.nc`. The "register as
`ObsGauge`s when `v1_5_raritan` is" note below is **done**; the scoring run will test the
interior.

⚠️ **What still governs how the scores must be read:**

1. **`naccs-nowaves` has waves off**, so its CSI/POD/FAR/n_dry are INADMISSIBLE and the runner
   will drop them (`extent_admissible=False`). Levels and phase only.
2. **Every sensor statistic is a HIGH-WATER statistic.** All four holdouts sit above normal
   water, so their troughs are below the recordable floor and the clipping is not
   missing-at-random — see the floor table below. High-water amplitude and phase are
   available; full M2 range is not, at any of them.

### 🟡 Stockdon as a DIAGNOSTIC — why waves buy only 5 cm, 2026-08-17

`scripts/stockdon_envelope.py`. 🔴 **It is a post-hoc envelope on a finished still-water run,
NOT an arm.** A `naccs-stockdon` solver arm was proposed and NOT built: NACCS already carries
wave setup (§23) and adding a parametric term on top is the double count §22 measures at
~1 m. Nothing here modifies a water level, so no double counting is possible.

⭐ **The framing that makes the rule intuitive:** setup accumulates from deep water to the
beach. NACCS hands us the total *seaward* of the boundary; SnapWave adds the surf zone
*shoreward* of it — two legs of one trip, no overlap. **Stockdon prices the whole trip in one
number**, from deep water to the shore, with no knowledge of where our boundary is. Add it to
NACCS and the seaward leg is paid twice. ⚠️ So Stockdon is not inherently a double count —
against a boundary product with NO wave coupling it is the correct and legal branch, which is
what the archive was doing. **The boundary product changed, not the formula.**

🔴 **The envelope test is VACUOUS and must not be quoted as validation.** `R2%` is ~2.98 m
tall, so 86–92% of marks fall inside it and **0% fall above it** — at β_f 0.02, 0.05 AND 0.10
alike. A test that returns the same answer across a 5× parameter swing measures nothing.

⭐ **What IS informative: how much water each mark needs above still water** (`obs − still`),
compared against `eta` — the setup term, the only part of Stockdon that is a water LEVEL.
Swash is an excursion, not a level, and no still-water model can reproduce it.

| basin | n (q≤3) | water needed | `eta` β_f=0.02 | `eta` β_f=0.05 |
|---|---|---|---|---|
| open beach (pooled) | 12 | **+0.37** | 0.33 | 0.82 |
| `atlantic_oceanfront` | 8 | +0.41 | 0.34 | 0.86 |
| `raritan_bay` | 23 | **−0.11** | — | — |
| `sandy_hook_bay` | 5 | −0.02 | — | — |

1. 🔴 **RETRACTED 2026-08-20 — it was a TWO-way agreement, not three.** As written: "on the
   open beach three independent routes agree at ~0.35 m: marks need 0.37, SnapWave delivers
   ~0.34 (§4), Stockdon at β_f=0.02 gives 0.33." Measured off the finished premier run,
   **SnapWave delivers +0.024 m at those marks, not 0.34** (FINDINGS §4) — §4's figure was
   an unmeasured assertion that this passage then cited as independent corroboration.
   Marks-need (0.37) and Stockdon (0.33) still agree with each other. ⚠️ **β_f was chosen
   AFTER seeing the target — that is calibration, not validation**, so the surviving pair
   is one measurement and one curve fitted to it. The archive's 0.05 overshoots by >2×,
   consistent with its own note that it ran high in sheltered spots.
2. **The bay needs NO wave contribution.** `need` is negative and ~60% of bay marks already
   sit at or below the still-water surface. Any uniform setup there makes it worse. Waves are
   an open-beach lever on this domain, nothing else.
3. ⭐ **That explains the paired result.** SnapWave costs 90–95% of runtime and moves HWM RMSE
   by only 0.047 m because it is fixing **12 marks of 58** — well, on those twelve, and
   invisibly on the rest.

⚠️ Small-n throughout, and 5 of the 12 are `q==3` marks readmitted by `--max-quality 3`.

#### ⚠️ The q≤2 cut removes the marks a wave question needs

Open coast holds **14** in-region marks; only **7** pass `q<=2`. The dropped ones are
systematically HIGHER — q≤2 tops out at 4.18 m while the single tallest open-coast mark,
**5.79 m, is a q==3 we never score.** The archive saw the same thing (the tallest beach marks
ride the runup top). So the headline is testing "do waves matter" on a set with much of the
wave-driven tail filtered out.

🔴 **`--max-quality 3` is a STANDALONE diagnostic and its numbers are NOT comparable with
`metrics.csv`** — a changed scored-mark count invalidates a comparison (FINDINGS §6). The
script prints a banner whenever the cut is not 2. ⚠️ `quality` is VERTICAL survey precision
only, so "taller marks are worse-quality" may have nothing to do with runup; the direction is
suggestive, not established.

✅ **RESOLVED 2026-08-20, off the finished premier run — and the answer is the awkward
one.** The conflict was: §4 put SnapWave at +0.34 m (premier − nowaves) while the `z15`
entry recorded only +0.027 m of setup between boundary and shore *within* premier.
**§4's number was wrong.** Measured, SnapWave delivers +0.024 m at the open-beach marks —
which is the `z15` entry's order of magnitude, not §4's. The two now agree.

🔴 **The "dissipation" reading is RETRACTED (2026-08-20, same session).** It was reported
as measured, on four lines of evidence, all of which came from `zsmax` and all of which
inherited one bias. `zsmax` is a running max at the solver timestep; hourly `zs` is not,
and the gap between them differs by ARM — in Raritan Bay premier carries 0.255 m of
sub-hourly excess against nowaves' **0.431 m**, an arm gap of −0.176 m that fully accounts
for the −0.129 m "damping". On hourly `zs` the sign reverses to **+0.059**; basin volume at
the crest is **+0.8% higher** in premier; the 10-min stations differ by ≤0.05 m. No
surge-damping signal survives. FINDINGS §4 has the table.

🔴 **The replacement problem is worse.** Every spatial score here — HWM residuals, floodmap,
MOTF CSI — is built from `zsmax`, so inside Raritan Bay they all carry a ~0.18 m
arm-dependent offset before any physics. The open coast is clean (arm gap +0.007, zsmax and
hourly agree to 1 mm), so this is basin-local, but Raritan Bay is **the basin v1.5 exists to
compute**.

⏳ **RUNNING — `diag-nowaves-fasthis`, SLURM 60693810, submitted 2026-08-20.** A copy of
`naccs-nowaves` (identical physics; fingerprint verified `faces=696230 boundary_edges=1652
sha=2a23667dd16e449c`) with `dthisout` 600 s → **60 s** and a six-point observation transect
down the Raritan Bay deep axis (`rb_axis_571k` … `rb_axis_559k`, depths 10–16 m), because
there were no obs points west of the Arthur Kill mouth. Bulk inputs are HARDLINKED from
`naccs-nowaves`, so it cost ~0 disk. 803 s of solve.
**Read it as: is the sub-hourly motion COHERENT between bay points?** A basin seiche is
coherent with a consistent period; numerical chatter is not. Coherent ⇒ the original
"SnapWave damps it" hypothesis is right by a different route; incoherent ⇒ `zsmax` is
contaminated in this basin and every spatial score there needs re-examining.

✅ **THE TRANSECT DID TAKE — the "SFINCS silently dropped all six points" entry was
WRONG, corrected 2026-08-21.** The run's own log lists `observation point 1..14` and
`wc -l sfincs.obs` is 14; the `his` carries 14 stations × 4321 steps. Whatever produced
the earlier "1..8" reading, it was not the run. The acceptance check that entry demanded
(log lines vs `wc -l sfincs.obs`) is still the right guard and **passes** — keep doing it,
it costs nothing. No re-run was required.

### ✅ ANSWERED 2026-08-21 — it is a COHERENT SEICHE, not chatter (FINDINGS §40)

`scripts/diagnose_bay_seiche.py`; pre-registration
`reports/seiche/preregistration_bay_seiche.md` written before any number. Read off the
existing `diag-nowaves-fasthis` (waves-off, PRE-weir).

1. **Primary — the excess is RESOLVED at 60 s: `recovery_frac` median 0.985** (min 0.950
   over the five clean axis points). No physical mode of this basin lives under the 120 s
   Nyquist, so the `zsmax` excess is not sub-timestep noise.
2. **Coherent, and organized at all times.** γ² between the axis ENDS (11.6 km) = 0.934,
   band mean 0.437 vs a 0.084 noise floor; every pair stays coherent in the quiet
   pre-storm window too (0.48–0.80, floor 0.26). Bay `hp_std` 0.067 m vs open coast
   0.016 m. Lags mixed-sign at ~8% of a period ⇒ quasi-standing; periods 34–60 min.
3. ⚠️ **`rb_axis_559k` is a discharge artefact** — 253 m from the Raritan source
   (Qmax 110 m³/s), a single-face sub-2-min 1.33 m `zsmax` spike. Flagged in the CSV
   (`src_contaminated`), not dropped. **No scored HWM mark is within 500 m of a source**
   (closest 674 m of 46), so nothing in `metrics.csv` is touched.

🔴 **Consequence for scoring: `zsmax` in Raritan Bay STANDS for a single arm** — it is
measuring real water, so the bay spatial scores do NOT need a filtered or hourly basis.
**The arm-comparison caution is unchanged and is now explained**: a real seiche has a
phase, `zsmax` samples it, and a local perturbation re-rings the basin — hence
instantaneous |Δzs| of 1.32 m against crest peaks differing only 0.03–0.15 m. The
envelope is robust, the phase is not. Keep comparing bay arms paired, and keep treating a
bay-wide Δ inside ±0.1–0.4 m as unattributable.

⚠️ One arm, one storm; the axis follows the dredged channel (flank points agree, which is
the check). The earlier framing "is the 0.431 m excursion a real seiche **SnapWave damps**"
is only half-answered: the motion is real, but this run cannot say why two arms ring
differently. A weir-era or waves-on fasthis would be the next step **if** that is ever
worth ~14 min of solver — it was not needed for the question as posed.

### ⏳ v3 — the full Jersey shore, Raritan Bay → Cape May (kicked off 2026-08-20)

**Decision (user, 2026-08-20): v3 spans v1.5's drawn northern ring to Cape May, forced
by NACCS (the 2-node interpolant is retired). Arms: `naccs-premier`, `naccs-nowaves`.**

**Already in hand (verified 2026-08-20):**
- NACCS: `data/NACCS/` repacked to 5 canonical zips; **1,287 ADCIRC save points,
  lat 38.83–40.62** — the whole shore past Cape May. STWAVE02/03/07 (563/301/523 pts)
  parked in their own zips (no reader; CORA is the adopted wave boundary).
- NOAA: `noaa_sandy_nj.nc` already holds **Cape May 8536110** → a v3 template gets
  3 base support points, not 2. Set `n_waterlevel_support=3` DELIBERATELY (the
  99.1 km buffer scar).
- CUDEM: the VRT + tile list already reach lat 38.75 (Cape May ✅ — no extension).
- `scripts/build_cn_nj.py` ported from the archive (domain-aware, per-domain output
  guard) — `cn_nj` stops at 39.556 and the catalog named a script the port had lost.
- v2_barnegat registered in bight as a frozen score-only fixture; its Manahawkin wall
  is what v3 removes.

**Blocked on the USER's QGIS polygon** — inherit v1.5's drawn northern ring (Narrows +
Arthur Kill cuts) verbatim, NOT v2's straight lat-40.52 line; no Manahawkin wall;
extend to Cape May Point. Consider raising the `bay_fringe` refinement gate zmax
(2.0 excludes every berm crest — the Keansburg lesson, FINDINGS §38).

#### ✅ THE v3 RING IS DRAWN AND PASSES ITS GATE — 2026-08-24

`data/region_v3_EDITED.geojson` (user, hand-edited in QGIS from the draft). 48 vertices,
valid, simple, **38 identical to v1.5's ring**. The user replaced the draft's box-corner
west edge with a coast-following diagonal and pulled the Cape May vertices east onto land.

⭐ **`scripts/validate_region_v3.py` — the gate. Reads, never writes.** Same rule and
shape as `validate_region_v1_5.py`: it ignores segment structure entirely (a hand-drawn
vertex is not hydrography) and walks the ring at 50 m steps against the merged bed,
classifying three ways — LAND (`bed ≥ 0`), **WET+ACTIVE (`mask_zmin ≤ bed < 0`)**, DEEP
(`bed < mask_zmin`). Only the middle class can carry `mask==2`; every reach ≥150 m of it
must fall inside exactly one declared `CROSSINGS` box or the script FAILS.

**Result on the edited ring: 595.8 km walked, 24.7 km WET+ACTIVE in 22 reaches, ALL
DECLARED, exit 0.** ✅ All 1,429 vertices of the −10 m isobath are INSIDE the ring, so
`create_active` decides the boundary everywhere, not the cursor. ✅ All 5 NACCS STWAVE
points deeper than 20 m are inside (62 fall outside, every one ≤10.2 m and hard against
the ring).

⚠️ **The `ocean_arm` box had to reach lon −73.98, not −73.96** — the Rockaway closure runs
NW from (−73.9364, 40.5497) to (−73.9732, 40.5794) and a tighter box left 3.00 km
undeclared. That was the validator catching its own declaration, which is the point.

**THREE NEW RIVER CUTS, introduced by the coast-following diagonal.** 🔴 This is the
Navesink failure family — v1's west edge once cut the Navesink mid-channel, hydromt put a
free-outflow BC on the 5 m face, and the model drained 92.5% of the estuary's inflow.
⚠️ Names for the first two are INFERRED FROM GAUGE PROXIMITY, not a hydrography layer:

| cut | width | bed | nearest gauge | dist | DA |
|---|---|---|---|---|---|
| Toms River (−74.189, 39.944) | 0.40 km | −1.72 m | `01408500` | 2.7 km | **123 mi²** ✅ |
| head of Great Egg Harbor Bay / Tuckahoe (−74.648, 39.303) | 1.15 km | −4.96 m | `01411300` Tuckahoe at Head of River | 14.9 km | 30.8 mi² ⚠️ partial |
| lower Mullica / Bass River (−74.44, 39.55) | 0.70 km | −1.24 m | `01410150` E Br Bass R | 8.1 km | **8.11 mi²** 🔴 |

All three are tidally connected to the open Atlantic (flood-fill, not assumed).

**Decision taken: the RARITAN PATTERN, with the cut placed deliberately.** Moving the ring
inland to cross only land is NOT cheaper — an estuary inside with no wet crossing needs the
ring west of its head of tide (Batsto 20 km inland, Head of River 15 km west), it still
needs a discharge source there, and the alternative (ring east of the rivers) would drop
Great Egg Harbor Bay and the Mullica estuary, real Jersey-shore flood targets. So: cross
the river, `no_waterlevel_box` on the cut (an imposed level PUMPS a tidal river), discharge
source AT the cut from the upstream gauge — and choose WHERE to cross so the gauge is good.

#### 🔴 THE THREE RIVER CUTS — one settled, two open, all subject to the inland move

⚠️ **All of this is on the CURRENT ring and must be re-checked after the inland move
(PICK UP #1).** The cut locations will change; the gauge inventory will not.

**✅ TOMS RIVER — SETTLED 2026-08-24.** Cut at (−74.1878, 39.9460), bed −1.72 m, 0.40 km.
The src moved ONTO the cut (`STATIONS_V3` in `download_usgs_sandy_discharge.py`).
⭐ **A src point is a property of the RING, not of the river.** v1.5's Toms src at
(−74.170, 39.945) was placed for a different ring and sits 1.5 km EAST of v3's cut —
i.e. INSIDE it — which would leave the reach between cut and src with no inflow while the
cut carried a water-level BC. Measured: old src bed −2.29 m, the cut −1.72 m, and 200 m
further east already −0.08 m (too shallow — do not drift east).
⚠️ **123 mi² is a LOWER BOUND.** `01408500` is the ONLY Toms River gauge with an Oct-2012
record (checked over the basin, daily AND instantaneous). **Wrangle Brook is ungauged**
and the cut lies BELOW its confluence (user, from imagery), so that catchment is outside
the domain and its flow is missing. Moving the cut ABOVE the confluence was considered and
rejected: with no gauge it buys no data and turns one crossing into two, the second wholly
ungauged.

**⏳ GREAT EGG / TUCKAHOE — geometry identified by the user 2026-08-24, sources not built.**
The two reaches are **two DIFFERENT rivers**, not one channel crossed twice:

| cut | width / bed | what it is | gauge |
|---|---|---|---|
| NE (−74.6456, 39.3059) | 0.90 km, −4.96 m | **Great Egg Harbor River**, just downstream of where the **Middle River** joins | `01411000` at Folsom, DA 57.1 mi² |
| SW (−74.6586, 39.2912) | 0.25 km, −1.58 m | **Tuckahoe River**, just before it enters Great Egg Harbor Bay | `01411300` at Head of River, DA 30.8 mi² |

🔴 **So it is TWO sources, not one sum.** The wider NE cut is **upstream of the Tuckahoe
confluence**, so the two rivers do not combine above the ring. ⚠️ The **Middle River is
ungauged** and joins above the NE cut, so 57.1 mi² is a lower bound there too.
Both gauges are outside the ring (correct — upstream). Mays Landing and Tuckahoe village
are currently outside too, which is what PICK UP #1 overturns.

**⏳ MULLICA — still open, and the earlier recommendation was WRONG.** I first said "move
the cut, the nearest gauge is only DA 8.11 mi²". Plotting it showed the cuts at lat 39.55
sit **downstream of the whole gauge cluster** (39.62–39.69), so the v1.5 Raritan
multi-gauge pattern applies instead — inject the sum at the cut, no ring move needed for
that reason:

| gauge | DA |
|---|---|
| `01409400` Mullica R nr Batsto | 46.7 mi² |
| `01409810` W Br Wading R nr Jenkins | 84.1 mi² |
| `01410000` Oswego R at Harrisville | 72.5 mi² |
| `01410150` E Br Bass R nr New Gretna | 8.11 mi² |
| **total** | **≈ 211 mi²** |

⚠️ **Still unresolved:** the two cuts, (−74.4389, 39.5550) 0.45 km and (−74.4453, 39.5470)
0.25 km, are 0.9 km apart and may be two channels (Mullica main stem vs Bass River). If
so the sources split between them. Needs imagery. ⚠️ And Batsto is currently OUTSIDE the
ring — PICK UP #1.

**The pattern for all of them (v1.5 Raritan):** cross the river, `no_waterlevel_box` on the
cut (an imposed level PUMPS a tidal river; a free-outflow DRAINS it — the Navesink lost
92.5% of its inflow that way), discharge source AT the cut fed by the upstream gauge(s).
⚠️ Moving the ring inland to cross only land is NOT the cheaper alternative: an estuary
inside with no wet crossing needs the ring west of its head of tide, it still needs a
source there, and the discharge is DAILY-mean only (USGS archived nothing finer for these
gauges in 2012) — fine for streams peaking at a few m³/s, worth re-examining for the
Mullica's ~211 mi².

#### ⭐ THE v3 REGION DRAFT — `scripts/build_region_v3_draft.py`, 2026-08-24

🔴 **THE REGION IS NOT THE BOUNDARY, AND THIS COST MOST OF A SESSION.** `build_static`
runs `create_active(zmin=mask_zmin)` **before** the region clip, so the ocean boundary
lands on the −10 m isobath whether or not the polygon traces it. Measured on v1: its
region box reaches lon −73.45 while its `mask==2` stops at −73.91. **That is why v1 is 7
vertices and v2 is 9**, and why `region_v2_barnegat.geojson`'s own properties record
`"offshore_edge_lon": -73.45`. Nobody ever traced a contour. The archive's v1 notebook
says it outright: *"Cells with z ≥ CONFIG['mask_zmin'] (-10 m) become active — the NJ
shelf is shallow enough that the -10 m contour is a good seaward edge."*
⚠️ A traced-isobath polygon is actively WORSE than a box: where the trace lands even
slightly landward of the true isobath, the region clip wins and the boundary is wherever
the cursor went.

`data/region_v3_DRAFT.geojson` — **48 vertices: 38 inherited from v1.5, 9 new.**
Figure `reports/figures/region_v3_draft.png`. Shape = v1.5's ring from its NE corner
round the Narrows / Staten Island / Arthur Kill mouth and back down the NJ side, then
v2's step at lat 40.150, then south.

**Offshore edge trimmed to lon −73.55** (user, 2026-08-24; v1/v1.5/v2 used −73.45).
⚠️ The obvious reading — "those are inactive cells, so who cares" — is wrong: the
quadtree fills the region's **rotated bounding box** (model.py:705) and the clip only
DEACTIVATES afterwards, so offshore cells ARE built, refined and stored. On the frozen
v1.5 mesh 284,176 of 696,230 faces (40.8%) are `mask==0`; 182,890 (26.3%) sit east of
lon −73.95.

🔴 **WHAT SETS THE EDGE IS THE WAVE FORCING, NOT THE WATER-LEVEL BOUNDARY.** Three
constraints, weakest first:

| constraint | east limit | margin at −73.55 |
|---|---|---|
| −10 m isobath (`mask_zmin`, the SFINCS mask) | −73.9946 | +37.8 km |
| −30 m isobath (`snapwave_mask_zmin`) | −73.6438 | +8.0 km |
| ⭐ **NACCS STWAVE save points** (planned wave forcing) | **−73.8300** | **+23.8 km** |

The STWAVE set is 1,387 points over STWAVE02/03/07, lon −75.1227..−73.8300, depths to
**31.5 m** (parsed from the repacked zips; each CSV carries its own lat/lon/depth).
🔴 **−73.85 was tried and REVERTED**: it put 2 of 1,387 outside, and they are the **two
DEEPEST in the whole set** (25–35 m, both at lon −73.8300) — precisely the points a
STWAVE-forced wave boundary wants. −73.55 keeps all 1,387 inside and leaves
`decouple_snapwave` possible.
⚠️ v1.5's NE vertex (−73.45, 40.45) is clamped to −73.55, so the inheritance is no longer
bit-for-bit. One constant restores it.

⚠️ **`snapwave_mask_zmin = −30.0` IS A DORMANT DEFAULT — do not read it as a rule.**
`decouple_snapwave` is **False on all six registered arms**, so SnapWave currently shares
the SFINCS mask at −10 m. The −30 m number came from the archive's 2026-07 `wave-deep30`
campaign, fixing **ERA5** imposing Hs 8.624 m at the ~10 m contour — γ 0.86–0.89, above
the 0.78 depth-limited breaking cap, physically inadmissible. That campaign records
itself as *"likely SUPERSEDED by wave-cora"*: CORA's shelf-resolving SWAN gives
4.98–6.11 m there (γ 0.50–0.63, admissible), and CORA is the adopted wave source. It is a
**wave-source property, not a boundary-depth rule** — the exact confusion MEMORY.md
already warns about. ⚠️ **Not a literature number either**: Grimley and Leijnse both
concern the WATER-LEVEL boundary (Leijnse, Parker-corrected GTSM at −10 m; Grimley, drawn
from a curated NHD shapefile). Neither sets a SnapWave mask depth.

**West staircase** placed against measured land extent (CUDEM 1/9", land = z ≥ 0): the
Cape May peninsula's Delaware Bay shore is lon −74.885 at lat 39.15, −74.929 at 39.05,
−74.969 at 38.95. South edge lat 38.855, ~8.5 km past Cape May Point (38.930).
🔴 **Wrapping the peninsula puts ~1 km of Delaware Bay inside the ring at lat 38.95–39.05
— a WET ring crossing that must be DECLARED** (`closed` per the terminus decision, or
forced). Same decision as the Cape May Canal. An undeclared wet crossing is imposed ocean
level somewhere nobody looked — what `validate_region_v1_5.py` exists to catch.

#### THE ISOBATH REFERENCE LINE — `scripts/build_v3_isobath_seed.py` (NOT the ring)

`data/region_v3_seed_isobath10m.geojson` shows WHERE `create_active` will put the
boundary. It is a reference layer for drawing against, **not** the polygon. Built on the
merged bed at CUDEM **1/9" native (~3.4 m)** — 🔴 note `cudem_nj.vrt` is 1/9", the
`ncei19_*` tiles, NOT 1 arc-second; a first cut decimated it to 93 m and threw away a
factor of 27. For scale, v1.5's ocean arm is 1,074 faces at 25–50 m.
1,429 vertices primary + 149 slack past Cape May Point + a `ring_edge_smoothed` variant
(rolling max ±2 km then +1 km seaward, 121 vertices, clearance 1.0–10.4 km).
Cross-check: at lat 40.1536 v1.5's frozen `mask==2` sits at lon −74.0165, the line says
−74.017.

⚠️ **Three screens were tried; two failed. Do not re-try them.** (a) components touching
the corridor's landward wall — at 3 m an ebb channel severs a shoal from shore, so the
line pinned to the wall, 5 km of artefact; (b) a pure run-length filter with no topology
— the envelope hopped onto every detached shoal, **1,500 flagged jumps against 25**.
What works is seeding pass 2's components from pass 1's own crossing.
A raw contour is unusable: **317 components, 952 km** over this window.

#### ✅ THE CAPE MAY CLOSURE — measured 2026-08-24, recommend closing DUE WEST to the beach

The seed's south terminus is (−74.8670, 38.9304); lat 38.930 is the southernmost latitude
at which NJ Atlantic land still exists in CUDEM (easternmost land there, lon −74.9121).
Three candidate closures, measured on the same 3″ CUDEM:

| closure | length | bed | verdict |
|---|---|---|---|
| **(a) due WEST at lat 38.930, terminus → Cape May beach** | **4.55 km sampled, ~3.9 km of it water** | min −9.9 m, **0.00 km deeper than −10 m**, one single water run | ⭐ **recommended** |
| (c) cut at Cape May Inlet, lat 38.9496 | 5.12 km | min −10.4 m, and it crosses land–water–land–water: **two** separate wet reaches | rejected — two crossings, and it drops Cape May city |
| (b) carry on around Cape May Point into Delaware Bay | — | — | rejected by the terminus decision above |

(a) is the **Rockaway analogue**: v1.5 closed its ocean arm on an 11.13 km drawn line, and
this is the same move at 4.55 km. It is one contiguous wet reach entirely shallower than
10 m, so `validate_region_v3.py` will see exactly one crossing to declare. NACCS support is
the best on the whole southern end — **Cape May Inlet 0.23 km to the nearest ADCIRC save
point, 26 points within 2 km** (table above).

⚠️ Consequence, and it is the reason the next item exists: closing at lat 38.930 puts Cape
May Harbour and the whole Cape May Canal INSIDE the domain, so the ring must then cross the
peninsula and meet the canal's Delaware Bay end near (−74.958, 38.968).

🔴 **The one real design question the terminus forces: the CAPE MAY CANAL.** It is a real
navigable tidal connection from Delaware Bay through to Cape May Harbour. If v3 includes
the harbour but excludes Delaware Bay, the canal is an unforced hole in the boundary.
Three options, to settle against bathymetry + the polygon:
- **(a) short forced cross-section at the canal** — the Arthur Kill analogue, and the
  spirit of v1.5. NACCS is marginal there (2.43 km), but the documented per-arm fallback
  applies: **1-node gauge forcing, and Cape May 8536110 is already in
  `noaa_sandy_nj.nc`.** *Preferred.*
- (b) declare the canal closed (`land_boxes`) — cheapest and reversible, but ⚠️ **it is a
  WALL, and removing v2's Manahawkin wall is v3's whole premise.** If taken, measure what
  it costs with `make_flux_crosssections.py` rather than asserting it is small.
- (c) cut on the Atlantic side at Cape May Inlet — cleanest topology, but drops Cape May
  city, a real NJ flood target.

#### ✅ DATA ACQUISITION — UNBLOCKED AND RUNNING, 2026-08-24

Both 2026-08-21 blockers are cleared. Nothing here waits on the polygon any more.

**BLOCKER 2 — v3 is REGISTERED, via a new `acquisition_only` domain state.**
`Domain.acquisition_only` (nj_sfincs/domain.py) is the deliberate, narrow exemption
STATUS scoped as option (ii): the three registry guards that need a mesh or a polygon
skip such a domain, and `_check_acquisition_only` replaces them with **harder** ones —
no `mesh_key`, `frozen` off, no `boundary_arms`, no `hwm_rules`, and
`n_waterlevel_support` **must stay None** (it has to be asserted against what hydromt
actually selects on the real mesh, not guessed from a rectangle). `assert_buildable()`
refuses to build/stage/probe/freeze one. 🔴 **No placeholder fingerprint was invented** —
`premier.EXPECTED` deliberately has no `v3` key, and a test pins that it never gets one.
`EXPERIMENTS_BY_DOMAIN["v3"] = {}`. **82 tests OK** (73 + 9 new in `TestAcquisitionOnly`).

v3's `region` is `data/region_v3_PROVISIONAL_acquisition_bbox.geojson`, lon[−75.05,
−73.45] lat[38.85, 40.62] — a superset rectangle, and a test asserts it stays a
5-vertex rectangle so nobody can point the flag at a real polygon without clearing it.
**Clearing `acquisition_only` is exactly the moment the drawn polygon lands.**

**BLOCKER 1 — the five downloaders are domain-aware.** New helper
`nj_sfincs.domain.acquisition_dir(kind)` is the single place that decides where a new
domain's pulls land (`data/elevation_v3/`, `data/precip_v3/`); it refuses
`ARCHIVED_TIER_DOMAINS` outright, so a sixth puller cannot quietly reintroduce the fixed
archive path. Patched: `download_cudem13`, `download_gmrt`, `download_3dep`,
`download_pre_sandy_topobathy`, `download_aorc_sandy_precip`.
⚠️ `download_3dep`'s RAW_DIR deliberately still points into the archive — the 16.5 GB
statewide `.ige` is already there and is only READ; the southern extension is a local
**re-clip**, not a download.

**Pull status:**

| tier | old southern limit | state |
|---|---|---|
| `cudem13` 1/3″ | 39.499 | ✅ **DONE** — 14 tiles (6 new southern), `data/elevation_v3/cudem13_v3.vrt`, 255 MB, now lat **38.749**–40.50 |
| `gmrt` ~50 m | 39.600 | ✅ `gmrt_v3.tif` 15.3 MB, lat **38.75**–40.72 (timed out twice, landed on retry 3) |
| `usace_nj_2010` 1 m | 39.680 | ✅ 750 MB, lat **38.928**–40.482 |
| AORC precip | — | ✅ `precip_v3/aorc_sandy_v3.nc`, 8.8 MB |
| `nj_10ft_dem` 3 m | 39.645 | ✅ 3.4 GB, lat **38.797**–40.675 (local re-clip) |

⭐ **GMRT was NOT optional.** Before it landed, 131.8 km of the v3 ring (22.1%) read NoData
— the outer shelf south of lat 39.6, where the 1/3" tiles do not reach lon −73.55 and the
archived `gmrt_nj` stops at 39.60. With `gmrt_v3` in the stack the ring walk is **0.0%
NoData** and all 131.8 km resolves to DEEP, leaving the 22 wet reaches unchanged.

Totals: `data/elevation_v3` 4.2 G + `data/precip_v3` 8.5 M; quota 69.4 G of 100 G.

⚠️ **Measured gap in the 1/3″ product:** `cudem13_v3.vrt`'s western edge is lon −74.75,
so the Cape May peninsula west of that has **no 1/3″ tile at all** — there is no
`n39x00_w075x00` in NOAA's own urllist. Cape May stays on 1/9″ `cudem_nj` there, which
does cover it. Not a download anyone skipped.

**Still to do, and these DO wait on the polygon:** catalog keys + a v3
`elevation_list`; the eHydro **southern** preset (Philadelphia district ⇒ **positive
depths**, needs a per-preset sign field); extending the hardcoded USGS tidal + STN sensor
lists southward; HWMs and the MOTF render (both select on the ACTIVE region's bbox, so
they should be pulled on the REAL polygon, not the superset rectangle);
`build_cn_nj.py`; CORA waves.

Quota 65.27 G of 100 G soft at launch (~35 G headroom).

### 🔴 Two infrastructure traps that ate five submissions, 2026-08-14

Both produce **`COMPLETED 0:0` with no output and no error anywhere**, which is the single
most expensive failure shape in this project. Both are now fixed in code; this is the record
of why those lines exist.

**1. The `halk*` nodes do not write to `/cache/home` on time.** ⚠️ **2026-08-20: Amarel
merged `main-redhat` into `main`** — sbatch to `main-redhat` now fails with "invalid
partition specified", and `hpc/sfincs_run.slurm` + `hpc/amarel_bootstrap.md` were updated.
**All 159 `halk*` nodes are now in the DEFAULT partition**, so an sbatch that bypasses the
batch script is more exposed than before, not less. `hpc/sfincs_run.slurm` now carries
`#SBATCH --exclude=halk[0001-0159]`. Re-check with the probe below before removing it.

⚠️ **This was first recorded as "writes nothing at all", and that is only half of it — the
harmless half.** Some halk jobs do produce nothing: allocated, runs, exits clean, no
`sfincs_map.nc`, no `sfincs_his.nc`, not even a SLURM stdout file. Evidence: a 2 GB probe
pinned to `halk0064` running only `hostname; touch` returned COMPLETED 0:0 in 8 s with no
output file and no marker, while the identical probe on `hal0338` worked. That costs a slot.

🔴 **Others write partial output whose flush lands HOURS OR DAYS later, on top of whatever ran
after them in the same directory.** 60582058 on halk0064 produced a 4,377-byte stdout *and*
real map/his output — so "5/5 halk submissions produced nothing" was wrong, and reading it as
"a halk job is merely wasted" is what left the good 08-14 runs unprotected. See the clobber
section above: this is the single most expensive failure this project has had, precisely
because the result reads back clean and carries a plausible mtime.

**2. Home is a GPFS filesystem with a 100 G soft / 110 G hard quota, and `quota -s` prints
nothing.** Ask it properly — `/usr/lpp/mmfs/bin` is not on PATH:

```bash
mmlsquota -u $USER --block-size auto cache      # blocks / quota / limit / grace
```

🔴 **Never measure headroom by `dd`-ing to ENOSPC.** Doing that filled the filesystem for a
few seconds while three jobs were starting; they could not create their output files and one
still exited `COMPLETED 0:0` after 14 minutes having written nothing. The failure looks
exactly like trap 1, which is how the two got confused for an hour.

Usage was **102.8 G (over soft, in the 7-day grace)** and is now **86.57 G**, reclaimed by
`scripts/dedupe_home.py` — it hard-links byte-identical large data files across
`nj_bight_sfincs`, `nj_coast_sfincs`, `nj_sandy_sfincs` and `sfincs_data`. **It links, it
never deletes**, which is what makes it safe to point at the frozen archive: every path stays
readable, only duplicate blocks go away. 20.1 GB over 142 files, then a further **3.42 G over
195 files on 2026-08-15** (89.99 → 86.57 G, measured on the quota either side). All four
v1.5 dirs and both v1_monmouth dirs still fingerprint afterwards, and `verify_port.py` still
passes bit-for-bit. Rerun it whenever a sweep is staged — `copytree` re-duplicates ~1.5 GB
per arm every time.

#### 🔴 That script silently reclaimed NOTHING for a whole run — two bugs, fixed 2026-08-15

The 2026-08-15 run first printed **`RECLAIMED: 3.5 GB (0 files linked)`** and the quota did not
move a byte. Both bugs are the same failure shape this project keeps paying for: **a success
message over a no-op.**

**1. The keeper was chosen in the direction that cannot work.** `os.link` writes
`<name>.dedupe-tmp` **into the loser's own directory**, so the copy being *replaced* is the one
that needs a writable parent. The archive freeze has since been applied, so
`nj_coast_sfincs/data` is `dr-xr-xr-x` while `nj_coast_sfincs/experiments` is writable (exactly
as the "Known gaps" entry prescribes). Choosing the keeper by link count alone put **every**
loser inside the frozen `data/`, and all 3.5 GB of candidates failed `EPERM` one by one.

✅ **Fixed by inverting the preference: KEEP THE COPY THAT CANNOT BE REPLACED.** The frozen
inode survives untouched and the writable copy becomes the link — same blocks reclaimed, and
the archive is never written to at all. Strictly safer than the direction that failed.

**2. `freed` did not depend on the reclaim succeeding.** It accumulated candidate gain
unconditionally and `--apply` merely relabelled the total `RECLAIMED`. It now counts only
inodes actually released, and **reasons in inodes, not paths** — an inode gives its blocks back
only when *every* path pointing at it has been relinked. A `blocked by a read-only parent dir`
line now reports pairs where both copies are frozen.

⚠️ Verify a reclaim **against `mmlsquota`, never against the script's own summary.** That is
what caught this, and the check costs one command.

The 5 sweep-only CoNED tiles were deleted for space (`10_20`, the Ward Point defect tile, is
kept so the tier and the cited figure stay rebuildable). `sweep_cudem_flatfill.py` now prints
a **PARTIAL SWEEP** banner when fewer than 6 tiles are present, so "0 patches" can never be
misread as "nothing wrong" — re-download the other five before trusting a clean sweep.

### ✅ Port verification — PASSED 2026-08-13

`scripts/verify_port.py`, tier 1 (rescore, no solver) and tier 2 (fingerprint + obs points
on the archived template). Tolerance is **bit-for-bit** (`places=9`): same input, same code
path, deterministic arithmetic, so any drift is a bug, not a tolerance.

Baseline: `experiments/v1_monmouth/metrics.csv` **as regenerated 2026-08-12** — NOT the
older July `_rescored.csv`, which is `hwm_n_scored=19` with no estimator column and would
fail on `n` alone, reading as a port bug that is not there.

| metric | archive | ported |
|---|---|---|
| `hwm_bias_scored_m` | −0.363105931 | −0.363105931 |
| `hwm_rmse_scored_m` | 0.570499300 | 0.570499300 |
| `hwm_n_scored` | 38 | 38 |
| `motf_csi` / `pod` / `far` | 0.637834 / 0.766245 / 0.208073 | identical |
| `phase_lag_sandy_hook_min` | 17.6 | 17.6 |
| `gauge_peak_err_prefail_m` | −0.311681898 | −0.311681898 |

Per-basin marks reproduce too (they depend on first-match-wins over `hwm_rules` IN ORDER,
so a reorder shows up here): `south_coast` 4 · `sandy_hook_bay` 21 · `atlantic_oceanfront`
3 · `shrewsbury_navesink` 10 · `shark_river` 0 — total 38.

**One key renamed by the port**, listed in `RENAMES` in the gate rather than hidden behind
an alias: `gauge_peak_err_prefail_m` → `peak_err_prefail_sandy_hook_m`. The archive had one
function per named place, so `gauge_*` needed no gauge in it; the port drives everything off
the domain registry. Phase-lag keys are now the registry gauge name (`sandy_hook` is
unchanged, which is why it is the pinned one).

**One real bug the gate caught:** a `round(..., 6)` inside the peak metric differed from the
archive at 1e-7. Rounding inside a metric is a silent lossy step that makes a CSV
non-reproducible — it now rounds nothing, and rounding happens in the report.

---

## 🔴 BLOCKED: the two gates before any v1.5 polygon is drawn

Two manual facts can kill the design. Confirm both **before** drawing a region polygon —
neither is expensive, and both are cheaper than a mesh.

### Gate 1 — NACCS coverage at both cuts

Does the CHS/NACCS save-point set have a **wet** point within 2.0 km of the mask==2 cells at
the **Verrazzano Narrows**, the **Arthur Kill**, and along the **Sandy Hook → Rockaway
Point** cut?

`scripts/build_naccs_boundary.py` now reports coverage **per arm**, because aggregate
coverage hides "0 points on Arthur Kill" — which on a domain whose entire claim is that two
short cross-sections carry the exchange is the single most important thing to know before
the run rather than after it.

> **Fallback if an arm comes back empty:** 1-node-per-arm gauge forcing — the Battery
> (8518750) for the Narrows, Bergen Point West Reach (8519483) for Arthur Kill. Defensible
> for two ~1 km cuts, unlike a 123 km gauge desert.

#### 🟢 Indicatively CLEARED on all three arms, 2026-08-13 — no further download needed

Sampled every 250 m along the sketched arms (`scripts/naccs_coverage_map.py`), against
ADCIRC points only:

| arm | median | max | within 2 km |
|---|---|---|---|
| ocean arm — Rockaway extension | 0.85 km | 1.85 km | **100%** |
| Verrazzano Narrows cut | 0.37 km | 0.68 km | **100%** |
| Arthur Kill cut (MOUTH) | 0.55 km | 0.87 km | **100%** |

And against v1's **real** `mask==2` cells (1,669, read off the frozen mesh, measured per
cell rather than as a polyline) — the Atlantic side v1.5 inherits unchanged: median
**0.46 km**, max **2.77 km**, **95.5%** within 2 km.

⚠️ Still not gate 1. These are the SKETCH, not `mask==2` on a mesh that does not exist, and
they ignore the dry and depth screens — so every number is an **upper bound** on the support
that will survive `build_naccs_boundary.py`. The gauge fallback is no longer needed on any
arm. **No further CHS download is required for the premier.**

#### 🟡 Indicative coverage, 2026-08-13 — encouraging, NOT the gate passing

9 CHS zips in `data/NACCS/`. **532 ADCIRC save points and 193 STWAVE save points**, spanning
lat 39.976–40.619, lon −74.326 to −73.877. Regenerate with
`python scripts/naccs_coverage_map.py` → `reports/naccs/` (CSV + map).

🔴 **The two products ship in the SAME zip and have DISJOINT save-point ID spaces** — zero
collisions across the 532 and the 193, while STWAVE `SP0089` and ADCIRC `SP03584` are the
same physical point. **Join on coordinates, never on id**, and with a tolerance: exact float
matching reported 85 "STWAVE-only" points, 83 of which sit 0 m from an ADCIRC point and
differ only in trailing precision. At 50 m the real figure is 2.

Counted in **rough indicative lon/lat boxes** (module constants in
`scripts/naccs_coverage_map.py`; they OVERLAP by design and are not the arms):

| zone | pts | ADCIRC+STWAVE | ADCIRC only |
|---|---|---|---|
| Verrazzano Narrows | 27 | **27** | 0 |
| Kill Van Kull | 0 | — | — |
| Arthur Kill | 54 | 23 | 31 |
| Raritan Bay | 156 | 54 | 102 |
| Lower Bay | 85 | 62 | 23 |
| Sandy Hook Bay | 60 | **2** | 58 |
| Sandy Hook → Rockaway cut | 90 | 64 | 26 |
| Atlantic shelf | 198 | **2** | 194 |

⚠️ **This is not gate 1.** The real screen is "within 2.0 km of a `mask==2` cell", which
needs the frozen mesh, and these boxes are not the arms. Read it as: the Narrows is
comfortably covered on both products; **Arthur Kill is the thin arm to watch**; and wave
coverage is a northern crescent — Sandy Hook Bay and the Atlantic shelf are ADCIRC-only.

#### ✅ STWAVE HAS ARRIVED — and the ADCIRC-only claim was wrong

The 2026-08-13 zips are **mixed**: `..._ADCIRC01_Timeseries.csv` *and*
`..._STWAVE07_Timeseries.csv` members side by side. The earlier "ADCIRC only, zero wave
parameters" reading came from inspecting ADCIRC-named members only, while the 695 count it
sat beside had already swallowed STWAVE members as save points (532 + 193 − 30 new in the
ninth zip = 695 exactly). **Per-zip verdicts on product are invalid; the product is a
per-MEMBER fact.**

STWAVE columns: `alpham`, `TM`, `Tp`, `DADD`, `UDIR`, `U`, `Hmo` — and the records are
**30-minute**, where ADCIRC is 15-minute.

✅ **`build_naccs_boundary.py` FIXED 2026-08-13 and verified on the mixed directory.**
It selected members on `CSV/…Timeseries.csv` with no product filter and took water level
from **hardcoded column index 9** — `ET00` water elevation in ADCIRC, **`TM` mean wave
period in STWAVE**. It never silently corrupted (the 30-vs-15-minute step tripped the
`times_ref` guard) but it exited blaming timestamps. Two changes:

1. Members are filtered on `ADCIRC_MEMBER = "_ADCIRC01_"`, and the skipped count is
   printed per zip so the STWAVE members are visibly excluded rather than silently.
2. The water-level column is looked up **by code (`ET00`) in header row 1**, not by
   position, and a member without it is a loud exit. A column-order change is now a
   failure, not a wrong variable.

Verified `--report-only --no-cache` on `v1_monmouth`: 532 unique ADCIRC points (177
duplicate files, values agree), Sandy window 2012-10-11 12:15 → 2012-11-01 00:00 at 15 min,
532 → 151 within 2 km → 92 kept after the dry (−23) and open-coast depth (−36) screens.
Coverage **max gap 2.76 km, 95.6% within 2 km**, support sha16 `21f967f9798a6945` — which
independently reproduces the 2.77 km / 95.5% measured off the mesh by
`naccs_coverage_map.py`.

⏳ STWAVE still has no reader; it needs its own, for its own column layout and 30-minute
step. Not on the premier's path.

#### Where the zips go — REPACKED 2026-08-20

`~/nj_bight_sfincs/data/NACCS/` — a real local directory (the builder reads
`ROOT/data/NACCS`). ✅ **The 24 request zips were repacked into 5 canonical zips**
(`naccs_repack_<PRODUCT>.zip` + provenance; `scripts/repack_naccs_zips.py`,
`_repack/repack_manifest.json` is the member→source record): 1,843 cross-zip duplicate
members all CRC-verified identical, the never-read `H5/` mirror dropped (user decision),
1.6 G → 590 MB. Originals deleted AFTER `build_naccs_boundary.py --report-only
--no-cache` reproduced the 1,287-point parse and the v1_monmouth support sha16
`21f967f9798a6945` on the repacked set. ⚠️ New CHS downloads land beside them as
`CHSFileDownload_*.zip` and simply coexist (both readers glob `*.zip` now); rerun the
repack script to fold them in. The archive's NACCS dir (6 zips) is untouched.

✅ **`_sandy_parsed.npz` is present and is SAFE.** An earlier note here claimed the parse
cache was "keyed to nothing" and would never notice a new zip. That is wrong:
`read_zips` stamps `st_mtime_ns` for every zip and invalidates unless both the **count and
every mtime** match (`build_naccs_boundary.py:206-209`), so adding, re-downloading or
touching a zip is a cache miss. `--no-cache` remains available and is still the right
reflex after any change you are unsure about.

⏳ **STWAVE is partially in** — 193 points against ADCIRC's 532, concentrated north of Sandy
Hook. See the coverage table above. ⚠️ STWAVE-vs-CORA is a **deliberately withheld
single-variable arm** (FINDINGS §1.21, and "Open, deliberately not decided" below); CORA is
the adopted wave boundary. Completing STWAVE coverage is not on the v1.5 critical path.

### 🟢 12 more HWMs are available in the target basin, and they are SAFE to add

Same STN query. In the Raritan Bay + Lower Bay box (−74.32…−74.00, 40.40…40.60) — the water
v1.5 exists to test — STN holds **45** marks with an elevation against our local file's
**33**. The **12** we do not have are all `Coastal`; by *vertical* quality, 6 Excellent
(±0.05 ft), 3 Fair, 3 Poor.

⭐ **None of the 12 falls inside v1_monmouth's footprint**, so adding them **cannot** move
the port fixture's pinned `hwm_n_scored=38`. That was the risk worth checking before
touching `sandy_hwms.geojson` (finding 6: a changed scored-mark count invalidates a
comparison), and it does not bite.

⚠️ `hwmQualityName` is **VERTICAL** accuracy only. It says nothing about where the mark is,
which is the uncertainty that forces the radius-and-estimator choice (finding 1). Do not
read "6 Excellent" as 6 well-located marks.

✅ **DONE 2026-08-14 — marks and rules added together, as required.**

`data/validation_v1_5/sandy_hwms_v1_5.geojson`, 107 marks in the v1.5 bbox, **69 inside the
drawn region** (archived file: 63 → **+6**). The other 38 are inside the bbox but outside the
ring — Staten Island proper and the Brooklyn side, excluded by design. ⚠️ So the "12 more
marks" figure was against a lon/lat box, not the region; **+6** is what the domain can score.

🔴 **A SECOND FILE, and `download_sandy_hwms.py` now REFUSES to write the first.** That script
selects marks by the ACTIVE region's bbox, so simply running it on v1.5 would have rewritten
the archived 95-mark file that the port fixture pins `hwm_n_scored=38` against — silently
rescoring the fixture. It exits with an error instead. Which HWM file a domain scores against
is now `Domain.hwm_geojson`, resolved through `_hwm_path()` in `validate/metrics.py` and
`plots.py`, the same pattern as `discharge_geodataset`.

**Basins, classified 2026-08-14 (`_V1_5_BASIN_RULES`, 69 in-region marks):**

| basin | marks | of which NEW to v1.5 |
|---|---|---|
| `shark_river` | 3 | 0 |
| `south_coast` | 5 | 0 |
| `sandy_hook_bay` | 6 | 0 |
| **`raritan_bay`** | **25** | 2 |
| **`lower_bay_si_shore`** | **6** | **6** |
| `atlantic_oceanfront` | 9 | 0 |
| `shrewsbury_navesink` | 15 | 0 |
| `unclassified` | **0** | — |

🔴 **v1's rule tuple could NOT be carried over, and this is the trap worth naming.** v1's rule
3 is `BasinRule("sandy_hook_bay", ymin=4_474_000)` with **no western bound** — harmless on v1,
where nothing lay west of Sandy Hook Bay. On v1.5 that one rule swallows **the whole of
Raritan Bay**, the water this domain exists to test, into a basin named after a different one.
It would have produced per-basin numbers that looked entirely reasonable and answered nothing.
`sandy_hook_bay` is therefore bounded here (`xmin=574_000`, `ymax=4_486_000`) and the water it
used to absorb is `raritan_bay`.

⚠️ **CONSEQUENCE: `sandy_hook_bay` does not mean the same thing on the two domains**, so its
per-basin statistics are not comparable across them. Compare arms within a domain — which is
the only comparison this project makes.

⭐ `lower_bay_si_shore` is 6 marks, **all 6 outside the v1_monmouth footprint**: a basin that
exists only because the boundary moved. And the last rule, `unclassified`, is an unconstrained
catch-all that must stay empty — it is the alarm for a wrong threshold, not a new basin.

### ✅ Gate 2 — PASSED 2026-08-13. Two interior holdouts survive the crest.

The whole claim is "Raritan Bay is COMPUTED, not forced". If nothing inside can be scored,
the claim is untestable. Sandy Hook (8531680) dies mid-storm — 48 of 96 hours NaN — and
cannot be the answer alone.

**It does not have to be.** USGS deployed rapid-deployment storm-tide sensors (SSS) across
Raritan Bay for Sandy and they all survived. Found via `Instruments/{id}/Files.json` →
`Files/{file_id}/item` on STN event 24 — *not* the bulk `Instruments.json`, whose
`data_files` is empty for every one of them (`download_sandy_storm_tide_sensors.py`
already documents that quirk).

Distances are to the **v1.5** arms. ⚠️ Computing them against v1's `mask==2` is wrong and
inverts the answer: 511 of v1's 1,669 boundary cells are its north edge (lat 40.5202) and
west edge (lon −74.28), **both of which run through Raritan Bay and both of which v1.5
deletes**. v1.5 inherits the 1,158 Atlantic-facing cells only.

| instrument | where | record | peak m NAVD88 | to nearest arm | role |
|---|---|---|---|---|---|
| **2255** `SSS-NJ-MID-001WL` | S Raritan Bay, NJ shore | 10-28 10:00 → 11-02 | 3.57 | 4.67 km | ✅ **holdout** |
| **2295** `SSS-NY-RIC-004WL` | Great Kills | 10-29 07:00 → 11-01 | 4.03 | 8.85 km | ✅ **holdout** |
| 2294 `SSS-NY-RIC-003WL` | Arthur Kill mouth | 10-28 06:00 → 11-01 | 4.88 | 1.67 km | ⚠️ forcing-adjacent |
| 2291 `SSS-NY-RIC-001WL` | Narrows, SI side | 10-28 06:00 → 11-01 | 4.58 | 0.87 km | ⚠️ forcing-adjacent |
| 2270 `SSS-NY-KIN-001WL` | Narrows, Brooklyn | 10-28 06:00 → 11-01 | 4.06 | 3.46 km | ~ marginal |
| 2265 `SSS-NJ-UNI-002WL` | up Arthur Kill | 10-28 10:00 → 10-31 | 3.84 | — | out of domain |

🔴 **THESE SENSORS ARE MOUNTED ABOVE NORMAL WATER. A long record is not a usable record.**
Each has a "lowest recordable water elevation"; below it the unit reads its own floor, and
`download_sandy_storm_tide_sensors.py` masks that to NaN. The fraction of each raw record
actually above its floor:

| inst | floor m NAVD88 | above floor | usable |
|---|---|---|---|
| 2255 | 1.75 | **1.9%** | ❌ **NO** — 28 six-min points, a 2 h blip at the crest |
| 2295 | 1.97 | 13.7% | ~ 112 points, high water only |
| 2291 | 1.28 | 19.8% | ~ 204 points |
| 2270 | 0.62 | 48.4% | ✅ 524 points |
| 2294 | 0.54 | 57.5% | ✅ 614 points |

⚠️ **So "record starts 10-28" does NOT mean "1.5 days of pre-storm tide".** 2255 spans the
period but was dry for 98% of it, and its 30-min still-water mean is not a water level at a
site that only briefly floods. **2255 is not a quantitative holdout** — at best a peak bound.

#### 🔴 Why 2255 is wonky — DIAGNOSED, and it is not a product error

**The sensor is sited on ground that is above normal water.** CUDEM under it reads
**+1.45 m** NAVD88 at the point and a **+1.78 m median within 150 m** — the whole
neighbourhood is dry land at ordinary tide, which is exactly why its recordable floor is
1.75 m and only 1.9% of the record clears it. Contrast 2294, whose 150 m median bed is
**−0.07 m**: real water at the sensor.

So 2255 is functionally **an HWM with a clock**, not a tide gauge: it answers "did water
reach here, when, and how deep", and its 30-min still-water mean averages across a window
that is partly *dry*, which is not a water level at all.

Its NACCS counterpart node sits in **2.86 m of open bay 0.88 km away**. Open-bay level
against shoreline overtopping depth is a category mismatch, so the +1.665 m "peak error" is
an artefact of the pairing, not a NACCS deficiency. ⚠️ **Drop 2255 from quantitative
scoring**; keep it only as a peak bound (water reached ≥3.57 m raw there) and score it as an
HWM, which is what it physically is.

⭐ **What IS testable: tidal HIGH WATER, not tidal RANGE.** Every sensor's troughs sit below
its floor, so peak-to-trough range is unmeasurable everywhere. But at 2294 and 2270 the
floors are low enough (0.54 / 0.62 m) that the tidal *peaks* clear them, and those peaks are
resolved in both level and timing. High-water amplitude and phase are therefore available;
full M2 range is not. ⚠️ Statistics computed on retained points are **high-water
statistics** — the clipping is not missing-at-random.

✅ **Ingested** to `data/gtsm/sandy_storm_tide_raritan.nc` via
`download_sandy_storm_tide_sensors.py --set raritan`. Deliberately a SECOND file:
`sandy_storm_tide_nj.nc` feeds `_SSS_SEA_BRIGHT` (2258) in the frozen v1_monmouth registry
and the port fixture is pinned against it. Register as `ObsGauge`s when `v1_5_raritan` is.

### 🟡 NACCS vs those sensors — the forcing product is good at the straits, LOW in the bay

`scripts/check_naccs_vs_sensors.py` → `reports/naccs/naccs_vs_sensors.{csv,png}`.
🔴 **A FORCING-PRODUCT diagnostic, never a model diagnostic** — no SFINCS run is involved.
The NACCS nodes used are INTERIOR nodes that on v1.5 force nothing; they stand in for "what
does the source product think the interior does".

| inst | role | node dist | bias | RMSE | peak err | lag |
|---|---|---|---|---|---|---|
| 2294 | forcing-adj, 1.67 km | 0.47 km | **−0.007** | 0.168 | +0.168 | +12 min |
| 2270 | marginal, 3.46 km | 0.24 km | −0.067 | 0.173 | +0.058 | +48 min |
| 2291 | forcing-adj, 0.87 km | 0.29 km | −0.092 | 0.178 | +0.001 | +54 min |
| **2295** | **holdout, 8.85 km** | 0.70 km | **−0.389** | 0.410 | **−0.350** | +18 min |
| 2255 | unusable (n=28) | 0.88 km | +1.234 | 1.315 | +1.665 | +66 min |

⭐ **The result that licenses the build: at the three places NACCS actually FORCES v1.5 —
the ocean arm, the Narrows, the Arthur Kill mouth — it is excellent.** Bias ≤0.09 m, RMSE
~0.17 m, tidal peaks tracked in both level and phase across the whole record.

At Great Kills it runs 0.35–0.39 m low. **Do not read a mechanism into that.** It is one
high-water-only comparison (n=112; everything below the sensor's 1.97 m floor is clipped
away) of one model against another model. Checked and ruled out: the node is *inside* the
harbour — bed along the 0.70 km line to it is water for 59 of 60 samples, to −9 m in the
dredged channel — and 8 save points sit within 2.1 km, so neither density nor a land block
explains it. **More NACCS points there would buy nothing.**

🔴 **And it does not propagate.** Great Kills is **8.85 km from the nearest arm**: on v1.5 it
is interior water that SFINCS COMPUTES. NACCS forces only the three arms, so a NACCS error
in the middle of the bay never enters the model. Not inheriting it is exactly what moving
the boundary out buys — under the old design, with the boundary through the bay, it would
have been a source term.

⚠️ **Pick the NACCS node by DEPTH, not distance alone.** NACCS ships save points with
negative depth (above datum — marsh/bank). The nearest node to 2255 is at −1.25 m and read
as a +1.7 m product error that was really a node-choice error; the script now requires
`depth >= 0.5 m`.

⏳ **The M2 amplification claim still has no direct time-series test.** The cleanest route
does not need 2012 data at all: run the model, extract its harmonic constituents at Port
Reading / Keasbey / South Amboy / Great Kills and compare against the NOAA published
`harcon` values already tabulated in FINDINGS §2.

---

## 🔵 LIVE — Phase 5b in progress, 2026-08-13. Pick up here.

### 🔴 READ FIRST — three boundary defects found by LOOKING at the map, 2026-08-13

The build reported *every invariant green* while the boundary was wrong in three places.
All three were caught by plotting the BC set and comparing it against what the user drew —
not by any assert. `scripts/plot_waterlevel_boundary.py <probe_dir>` after every mesh
change; the invariants do not check that the boundary is where you MEANT it.

**⚠️ A stale figure is worse than none.** The plot that exposed this was two builds old and
its counts (ocean 1,202 / narrows 153 / arthur_kill 41 / outflow 320) belonged to the
retired 16-vertex polygon. Regenerate before reading.

#### 1. ✅ FIXED — the Narrows arm was tracing the ALWAYS-ACTIVE BOX, not the drawn cut

The `narrows` arm came out as an **L**: a ~3 km limb along lat 40.6005 plus a stub of the
real cut, **209 cells**, sitting ~670 m south of the Verrazzano Bridge the user drew the cut
on (`v9 (-74.02941, 40.61090) → v10 (-74.05864, 40.60208)`, midpoint −74.044, 40.6065 — the
bridge).

**Cause: the bay `always_active_boxes_ll` entry ended at lat 40.60**, which is *inside* the
Narrows approach. The Narrows is ~30 m deep, so above the box `create_active(zmin=-10)`
deactivated the channel and `create_boundary` traced the box edge instead. Active cells in
the corridor collapsed across it: 2,779 (below 40.60) → 887 → 336 → **0** above 40.61.

**Fix: north edge 40.60 → 40.6125.** The ring's northernmost vertex is 40.61090, and the
region clip runs after `create_active`, so extending cannot pull in anything outside the
ring. Result: **209 → 61 cells, one continuous run, bed −29.57 m** — the real channel.

#### 2. ✅ FIXED (but see 2b) — the edge was DISJOINTED: the outflow gate stopped at +2 m

`create_boundary(btype="outflow", zmin=-1, zmax=2)` only made a cell free-outflow if its bed
sat between −1 m and **+2 m**. Measured along the 21.5 km Staten Island shore, only 42% of
edge cells fell in that window, so **209 of 411 stayed mask==1** and a cleanly-drawn
shoreline came out as a dashed line. Bed there reaches +26 m; the inland limits reach +80 m.

**Fix: `OUTFLOW_MAX_BED = 1.0e4` in `model.py` — every DRY edge cell is now outflow.**
Safe in the only direction that has ever bitten: `zmin` is still `OUTFLOW_MAX_DEPTH`, and
step 5c still re-seals any outflow cell landing on water, so the Navesink drain cannot
return (`free-outflow BC on water: 0` still holds). On dry ground a Neumann face is inert
until water reaches it, and then letting flood water leave beats ponding it against an
artificial wall — which on SI's south shore would push water back into the Raritan lobe.

| ring stretch | closed (mask 1) BEFORE | AFTER |
|---|---|---|
| Staten Island shore (411 edge cells) | 209 (51%) | **7 (2%)** |
| Rockaway → Narrows (207) | 119 (70%) | **34 (16%)** |
| NJ shore + west limit (318) | 281 (88%) | 234 (74%) |

Outflow total **240 → 957**.

⚠️ **The NJ/west limit stays mostly closed and that is FINE, not a fourth defect.** Those
234 cells have median bed **+19.7 m** (max +89 m); only 12 sit below 0 m. Nine are within
300 m of the grid's own west edge (x=559,113), where there is no neighbouring cell for
hydromt to flag against, so SFINCS treats them as a closed wall by default. High dry inland
ground never floods, so mask 1 vs 3 is immaterial there.

#### 2b. ✅ FIXED 2026-08-14 — the built domain extended beyond the drawn region

Raising the outflow gate made this visible: the boundary in the new figure runs down the
**grid rectangle's** west and south edges, not the drawn ring. Measured on
`data/probe_mesh_v1_5_fix2`:

| mask | cells | inside the drawn region | OUTSIDE it |
|---|---|---|---|
| 2 waterlevel | 1,307 | 1,307 | **0** ✅ |
| 3 outflow | 957 | 668 | **289** 🔴 |
| 1 active interior | 426,399 | 412,258 | **14,141** 🔴 |

The 14,141 sit at lon −74.30…−74.10, lat 40.15…40.50, bed **+3.7 … +58.3 m** — i.e. the
**dry inland notch** of the L that the region clip is supposed to remove.

⚠️ **PRE-EXISTING, not caused by the outflow change.** The gate only decides mask 3 vs 1;
it cannot make a cell active. Raising it merely put 289 BC cells on ground that was already
wrongly active, which is what made it visible. `base.region` resolves correctly to the drawn
polygon, and the clip at `model.py` (`mask[_outside] = 0`) is applied.

#### ✅ CAUSE CONFIRMED 2026-08-14 — it IS `_fill_inactive_holes`

Tested by monkeypatching the fill to a no-op (no edit to `model.py`) and rebuilding the
mask-only probe on `v1_5_raritan`:

```
[TEST] fill DISABLED — it would have activated 14435 cells
RuntimeError: [build_static] DOMAIN INVARIANTS FAILED:
  - 14435 inactive cells form islands INSIDE the model (deepest -11.02 m, ...)
```

**14,435 filled vs 14,141 outside the region.** The fill is the cause, and the ~294-cell
remainder is the point: those are the *legitimate* interior holes the fill exists for
(finding 9 — the scoured inlet throats). Largest kept active component also drops
426,399 → 414,228 with the fill off, consistent.

⭐ **So the fix is NOT to remove the fill** — with it off the build correctly refuses to
proceed, which is the invariant doing its job. `_fill_inactive_holes` cannot distinguish "an
inactive island inside the model" from "the inactive ground I just clipped away", because
after the clip they are topologically the same thing: neither is the largest `mask==0`
component.

**The fix is to RE-APPLY THE REGION CLIP AFTER THE FILL**, so the fill keeps its ~294 real
holes and gives back the 14,141 cells that were never in the domain. ✅ Implemented as step
**4c** in `apply_mask_and_boundary`, and it prints what it undoes:

```
[mask] filled 14435 interior inactive cells ...
[mask] region re-clip after hole-fill: 14431 cells outside the region were
       re-activated by the fill -> inactive again
```

**Result — every mask class is now entirely inside the drawn ring:**

| mask | fix2 total | fix2 OUTSIDE | **fix3 total** | **fix3 OUTSIDE** |
|---|---|---|---|---|
| 1 active interior | 426,399 | 14,142 | 409,712 | **0** ✅ |
| 2 waterlevel BC | 1,307 | 0 | 1,272 | **0** ✅ |
| 3 outflow BC | 957 | 289 | 1,070 | **0** ✅ |

#### 🔴 AND THE SAME BLINDNESS WAS IN INVARIANT 3 — found because the fix made it fire

The first build after the re-clip **failed**, on `14431 inactive cells form islands INSIDE
the model`. Not a misfire: invariant 3 calls `_inactive_components` and inherits its
definition of a hole — *any* `mask == 0` component that is not the largest — so the ground
the clip had just correctly removed came straight back as an invariant violation. The clip
and the check were fighting.

✅ **Fixed by scoping "inside the model" to mean inside the REGION** (`hole &= ~outside`),
with **one shared `_outside_region(sf, region)` helper** now used by the clip, the re-clip
and the invariant. They must agree by construction, or one removes ground the other demands.

⭐ Worth stating plainly because it is the same lesson twice in one day: the defect was never
"the fill is buggy". It is that **after a region clip, "outside the domain" and "an island
inside the domain" are topologically identical**, and every piece of code that reasons about
`mask == 0` connectivity has to be told which is which.

**Impact if left:** ~3% more active cells (compute only) and a boundary that plots along the
grid edge. All of it is dry ground +3.7 m and up that ocean water never reaches, and no
`mask==2` cell is outside the region, so **no water-level forcing is misplaced.** It is a
correctness/"what did I actually build" issue, not a physics error.

#### 3. ✅ FIXED 2026-08-14 — `arthur_kill` is ONE run of 24 cells, and the polygon never moved

**`arthur_kill` 59 cells / 2 runs → 24 cells / 1 run**, bed −13.71…−1.46 m, by adding the
`coned_sw_raritan` elevation tier and nothing else. The 35-cell spurious run was the
phantom-water rectangle; once Ward Point is land, it cannot form. `narrows` stays 61 cells /
1 run. ⭐ **The user's hand-drawn ring was correct as drawn and was never edited.**

Below is what the defect was and why it was misread — kept because the misreading is the
instructive part.

The arm is legitimately one cut, but the build gave **two disconnected runs**:

| run | where | bed | what it is |
|---|---|---|---|
| 24 cells | lon −74.2617…−74.2549, lat 40.5038…40.5052 | −13.71…−1.38 | ✅ the real mouth cut (the eHydro-carved channel) |
| 35 cells | lon −74.2501…−74.2404, lat 40.4971…40.4996 | −5.68…−3.02 | 🔴 spurious — **fake water, see below** |

🔴 **RETRACTED 2026-08-14.** This was recorded as "the ring cuts a corner across open water
south of Ward Point" with an instruction to pull v29/v30/v31 north onto the shoreline. **That
was wrong, and acting on it would have moved a correctly-drawn ring off the real coast.** The
user challenged it against Esri imagery; the imagery is right.

**CUDEM IS MISSING THE WARD POINT HEADLAND AND BACKFILLS IT AS WATER.** In `cudem_nj`
(1/9″), the southernmost land cell sits at lat **40.49982 in EVERY column** from lon −74.2486
to −74.2393 — a razor-straight cutoff, not a coastline — and there is **no land at all** west
of lon −74.2504, which is the tile edge. Ward Point is the southernmost point of New York
State at ≈**40.4961 N**, so ~230 m of real headland is absent and reads as −3 to −5.5 m of
bay. Figure: `reports/figures/ward_point_ring_vs_cudem.png` (drawn ring over CUDEM's z=0).

The three vertices are therefore on the **real** shore. Distances to CUDEM's fake land edge —
v29 **28 m**, v31 195 m, v30 306 m — cannot be one horizontal offset, which is the tell that
this is missing data and not a datum or grid shift.

⚠️ Do NOT "fix" this by shrinking the `arthur_kill` arm box, and do NOT move the ring. The
fix is an elevation tier — see the section below.

⚠️ **`validate_region_v1_5.py` reporting segments 28–33 as wet is not corroboration.** It
reads the same stack, so it inherits the same hole. A wet-reach validator can only ever say
"the bed I was given is below −0.5 m there".

#### 3b. ✅ FIXED 2026-08-14 — Staten Island had no valid TOPO in the stack; land read as water

Found while diagnosing defect 3, and it is the general form of it. This is the CLAUDE.md
`nj_10ft_dem` trap firing exactly as written.

| point | `cudem_nj` | `cudem13_nj` | `nj_10ft_dem` | `gmrt_nj` | merged |
|---|---|---|---|---|---|
| Ward Point tip (−74.2490, 40.4980) | −4.96 (fill) | — | — | 0.00 | **−4.96** |
| Conference House Park (−74.2515, 40.5005) | — (past tile edge) | — | — | −0.06 | **−0.06** |
| real shore 1 km east (−74.2380, 40.5025) | 7.45 | 6.04 | — | 6.04 | 7.45 ✅ |

Conference House Park is dry parkland and the stack hands back **−0.06 m**. `nj_10ft_dem` is
New-Jersey-only so Staten Island falls through it; `cudem_nj` truncates; `cudem13_nj` does
not reach; and the last tier standing is **50 m GMRT, which puts the whole shoreline at ≈0**.

🔴 **`build_static`'s no-NoData assert CANNOT catch this.** GMRT covers everything, so the bed
is not missing — it is *present and wrong*. The assert was written against a hole; this is a
fill. Any check that only tests for NoData will pass on it forever.

**Extent, measured on a ~87 m grid inside the drawn region:** **7.29 km² is GMRT-only**
(no CUDEM, no NJ lidar), spanning lon −74.2991…−74.2505, lat 40.4800…40.5115. That overlaps
the CUDEM hole already documented under the eHydro section, but that section framed it as a
*bathymetry* gap at two forced cuts. It is also a **topography** gap along the Tottenville /
Ward Point / Conference House shore, and the topography half was never noticed because the
symptom is silent: land simply becomes water.

#### ✅ THE FIX EXISTS AND IS DOWNLOADED — USGS CoNED NJ/DE topobathy, 1 m

**`1888–2014 USGS CoNED Topobathy DEM (Compiled 2015): New Jersey and Delaware`**, 1 m,
EPSG:26918 (NAD83 UTM 18N), NAVD88 — the same product family already listed as an open
alternative in the eHydro section. Despite the "New Jersey and Delaware" name it **covers
Staten Island**; the New England CoNED, which is the one that lists NY counties, does *not*
list Richmond. Do not select on the dataset name.

Bulk: `https://noaa-nos-coastal-lidar-pds.s3.amazonaws.com/dem/NewJersey_Delaware_Coned_Topobathy_DEM_2015_5040/`
— 597 tiles of 8192², ~190 MB each, plus a VRT whose `DstRect` offsets give the tile index
without downloading anything.

⭐ **31 tiles intersect the drawn region (1,332 of 2,281 km²) but the whole defect is inside
ONE**, `NJ_DE_Topobathy_DEM_v2_10_20.tif` (lon −74.3128…−74.2154, lat 40.4625…40.5357).
✅ Downloaded to `data/elevation_v1_5/coned/`.

| point | current stack | CoNED |
|---|---|---|
| Ward Point tip | −4.96 (CUDEM fill) | **+2.67 LAND** |
| Conference House Pk | −0.06 (GMRT) | **+8.23 LAND** |
| ring vertex v30 | −5.48 | **+2.33 LAND** |
| ring vertex v31 | −5.06 | **+2.89 LAND** |
| Arthur Kill mid-channel | −8.14 GMRT (eHydro −13.56) | −9.81 |
| Raritan R channel | −3.15 GMRT (eHydro −9.85) | −2.08 |
| Perth Amboy waterfront | −0.76 GMRT | −2.09 |
| control: real shore 1 km east | 7.45 CUDEM | 7.36 |

**Measured over a ~10 m grid, lon −74.300…−74.215 × lat 40.463…40.535:**

| | |
|---|---|
| CoNED has data | **98.9%** of the box (CUDEM: 41.4%) |
| CoNED fills where CUDEM is ABSENT | **33.28 km²** |
| CoNED − CUDEM where both exist | median **+0.069 m**, 90.6% within 1 m |
| CUDEM says water, CoNED says LAND | **0.307 km²** (CUDEM median −4.44, CoNED +2.36) |
| CUDEM says land, CoNED says water | **0.006 km²** |

⭐ The 0.307 vs 0.006 km² asymmetry is the whole argument: CoNED is not trading one error for
another, it is adding land CUDEM lost. And the control point agrees to 0.09 m, so this is not
two products disagreeing about datum.

🔴 **CoNED MUST GO ABOVE `cudem_nj` IN THE TIER LIST, and that is the load-bearing decision.**
The phantom water is a *value*, not NoData, so a tier placed below CUDEM changes nothing at
Ward Point. Above CUDEM, CoNED supersedes it everywhere both have data. It stays BELOW the
eHydro carve tiers — eHydro is the dredged-channel survey and is deeper at both forced cuts
(−13.56 vs −9.81; −9.85 vs −2.08) and, for the Raritan, 95 days pre-Sandy.

#### ✅ SWEPT 2026-08-14 — Ward Point was the ONLY significant one

`scripts/sweep_cudem_flatfill.py` → `reports/coned/phantom_water_patches.json`. Diffs the
**merged stack** against CoNED at 10 m, inside the region, and reports contiguous patches
where the stack says water (< −0.5 m) and CoNED says land (> +0.5 m). 6 tiles, the whole
Staten Island + Rockaway frontage.

| tile | what it covers | phantom water in-region |
|---|---|---|
| 10_20 | Ward Pt / Arthur Kill / Raritan | **0.200 km²** |
| 09_21 | SI west / Arthur Kill north | 0.017 km² |
| 09_23 | Rockaway / Coney Island | 0.010 km² |
| 10_21 | SI south shore, mid | 0.007 km² |
| 09_22 | SI east shore + **the Narrows** | 0.001 km² |
| 10_22 | Great Kills | **0.000 km²** |

Only 3 patches clear 0.005 km²:

| area km² | lon | lat | stack z | CoNED z | verdict |
|---|---|---|---|---|---|
| **0.1870** | −74.2537…−74.2372 | 40.4961…40.5012 | −3.16 | +2.04 | **Ward Point** |
| 0.0071 | −74.1330…−74.1305 | 40.5461…40.5468 | −3.22 | +0.93 | ⚠️ leave alone — see below |
| 0.0063 | −74.2552…−74.2542 | 40.5021…40.5039 | −2.36 | +1.83 | Perth Amboy, adjoins Ward Pt |

⭐ **93.5% of all phantom water on the frontage is the one Ward Point patch**, and the two
places that most needed to be sound are: **Great Kills — where the only true interior holdout
sensor (2295) sits — has ZERO**, and the **Narrows arm has 0.001 km²**. Nothing else needs
fixing, and the mesh does not have a second hidden headland.

🔴 **`build_static`'s no-NoData assert cannot find any of this, and neither can
`validate_region_v1_5.py`** — the latter reads the same stack, so it inherits the same hole.
Only an INDEPENDENT product can. That is what the sweep is for; re-run it whenever a tier
changes.

#### ⚠️ CoNED IS POST-SANDY, AND THAT IS WHY THE SWAP MUST STAY CLIPPED

The product is compiled 2015 from sources through 2014, so on Staten Island the lidar is
**after** the storm this model hindcasts. On bedrock upland — Ward Point, Conference House —
that is irrelevant: the headland did not appear between 2012 and 2014. On **erodible beach,
dune and berm** it is not irrelevant at all, and post-Sandy topography is the *wrong* bed for
a Sandy hindcast.

That is almost certainly what the 0.0071 km² patch at lon −74.133 is: Oakwood Beach, where
CUDEM reads −4.08 m and CoNED +0.93 m, in ground that saw post-Sandy berm and buyout work.
**Do not "fix" it.** There the older bed is the more correct one.

⭐ **So the clipped box is not merely the conservative option, it is the correct one:** it
takes CoNED exactly where CUDEM is structurally broken and leaves the erodible shorelines on
a pre-storm bed.

#### ⏳ NEXT — the declared box, chosen but not yet implemented

**Decision (user, 2026-08-14): clip the CoNED override to a declared box.** Proposed:

```
coned_sw_raritan   lon -74.3120 … -74.2320,  lat 40.4640 … 40.5340
```

Covers the CUDEM hole (−74.2991…−74.2505, 40.4800…40.5115, where CoNED adds **33.28 km²**
of bed that does not currently exist), the Ward Point patch and the Perth Amboy patch; it
**excludes** Oakwood Beach. It sits entirely inside the single tile
`NJ_DE_Topobathy_DEM_v2_10_20.tif`.

**The seam was measured before the box was adopted** — CoNED − merged stack along each edge:

| edge | n | median | p95 abs | max abs |
|---|---|---|---|---|
| east lon −74.2320 | 46 | **+0.012** | 1.02 | 1.76 |
| west lon −74.3120 | 46 | **−0.004** | 0.65 | 1.59 |
| north lat 40.5340 | 44 | **+0.000** | 1.07 | 14.44 |
| south lat 40.4640 | 44 | **+0.016** | 0.95 | 1.18 |

Median step is ±0.02 m, so the discontinuity a hard box edge introduces is centimetres. ⚠️
The 14.44 m outlier is on the north edge, which runs across **inland** Staten Island — a
building seen by 1 m lidar and not by 3 m CUDEM, on ground the region excludes anyway.

✅ **ALL FOUR LANDED TOGETHER, 2026-08-14, as one fingerprint move:**
1. ✅ `scripts/build_coned_sw_raritan.py` → `data/elevation_v1_5/coned_sw_raritan.tif`
   (6843 × 7826 @ 1 m, 98.4% valid, z −17.14…+50.26 m), catalogued as `coned_sw_raritan`,
   inserted **above `cudem_nj`** and **below the eHydro tiers**.
2. ✅ The defect-2b re-clip, plus the invariant-3 sibling it exposed.
3. ✅ `dry_land_boxes_ll` + invariant 8 + 5 tests.
4. ✅ Re-probed → `data/probe_mesh_v1_5_fix3`, re-plotted, and LOOKED at
   (`reports/figures/waterlevel_boundary_v1_5_raritan{,_cuts}.png`). The boundary now traces
   the drawn ring instead of the grid rectangle, and both cuts are single clean runs.

⚠️ The 943 MB of raw CoNED tiles under `data/elevation_v1_5/coned/` are the SWEEP inputs, not
the tier. Only `coned_sw_raritan.tif` is in the elevation stack. Keep them: re-running
`sweep_cudem_flatfill.py` after any tier change is how the next Ward Point gets found.

⚠️ It goes in `data/elevation_v1_5/` — `data/elevation` is a symlink into the frozen archive
and is read-only.

⭐ ✅ **DONE — a POSITIVE check, not another NoData assert.** New domain field
`dry_land_boxes_ll` and **invariant 8** (`model.check_dry_land_boxes`): declared ground must
report a bed at or above a stated elevation, so a tier that is deleted, mis-ordered,
mis-clipped or silently shadowed fails the build instead of quietly flooding a park.

Two boxes registered on `v1_5_raritan`: `conference_house_park` (min +2.0 m; CoNED reads
+7.6 m minimum there) and `ward_point_headland` (min +0.5 m; CoNED reads +1.6 m minimum).
Thresholds sit well below the measured bed so they fail on a REGRESSION, not on resampling.

🔴 **The check is SEEN TO FAIL** — 5 new tests in `tests/test_domain_and_staging.py`, one of
which feeds it CUDEM's actual −4.96 m at Ward Point and asserts it fires. An assert nobody
has watched fire is a decoration. One test covers the characteristic failure of any positive
check: **a box containing no grid faces asserts nothing and would pass forever**, so that is
an explicit error, not silence. Another pins each box inside the CoNED tier's clip, since a
dry-land box on ground the tier does not cover is a trap rather than a check.

#### 3c. ✅ THE UN-MASKED STRETCH IS THE JAMAICA BAY WALL — as designed

The user asked about "the portion of the boundary that has no mask whatsoever" southeast of
Brooklyn. **It is the Rockaway Inlet closure, and it is correct.** Ring walked at 50 m
against the nearest `mask==2`/`mask==3` cell, on `data/probe_mesh_v1_5_fix3`:

| bare stretch | lon | lat | bed | max dist to any BC |
|---|---|---|---|---|
| 121.45 km | −74.012…−73.450 | 40.150…40.450 | −65.2…−13.8 | 46,955 m |
| **1.20 km** | −73.963…−73.953 | 40.5632…40.5711 | −6.80…−4.38 | 993 m |

The 121 km stretch is **not a defect and must not be "fixed"**: the drawn ring runs out to
lon −73.45 over the deep shelf, and `create_active(zmin=-10)` stops the model at the −10 m
isobath, so the legitimate BC line lies well INSIDE the ring there (`model.py` says exactly
this in its own notes).

The 1.20 km stretch is the closure between Coney Island and Rockaway Point — real water at
−4 to −7 m carrying no boundary cell, i.e. a closed wall. That is *how* "Jamaica Bay is
excluded" is implemented, `validate_region_v1_5.CROSSINGS` declares it `closed`, and the
justification stands: that prism exchanges with the ocean through this inlet, not with Lower
Bay.

⚠️ **Say the cost out loud: this is a closed wall on WATER, not on land.** It reflects rather
than transmits, and it removes the Jamaica Bay tidal prism entirely. Accepted by design, but
it is the mirror of the free-outflow-on-water defect and deserves to be stated rather than
inherited silently.

#### 3d. 🟢 NOT A DEFECT — the ocean arm continues past Rockaway Point, and that is FINE

Found while chasing 3c (and initially mistaken FOR it). Measured on
`data/probe_mesh_v1_5_fix3`:

The `ocean` arm is **2 runs, 1,170 + 17 cells**, separated by a **1,257 m gap** at
lon −73.9416…−73.9372, lat 40.5428…40.5536. What fills the gap is the **Rockaway / Breezy
Point barrier spit** — 1,832 land cells up to **+6.19 m**, carrying 43 outflow cells (bed
−0.77…+5.75 m). So the arm is not broken by a defect; it is interrupted by a real sand spit,
and the outflow gate correctly makes the dry crossing free-outflow.

⚠️ **But the 17-cell run is on the FAR side of that spit** — lon −73.9498…−73.9413, lat
40.5536…40.5603, bed −9.78…−1.47 m — i.e. north of the Rockaway Point tip, in the Rockaway
Inlet throat. The design says the ocean arm is "v1's trace extended ~3.3 km straight north
**to Rockaway Point**", and `validate_region_v1_5.CROSSINGS` declares `rockaway_inlet`
**closed** — "which is how 'Jamaica Bay is excluded' is implemented". Those 17 cells are
imposed ocean level past the declared stopping point.

🔴 **Two declarations disagree, and that is the actual finding.** The `ocean` boundary ARM
box runs north to northing **4,490,496**, and these cells sit at 4,488,287…4,490,473 — inside
it, so the whitelist keeps them. The ring-walk CROSSING boxes say this is `rockaway_inlet`,
closed. The arm box and the crossing declarations are separate lists and nothing cross-checks
them.

⚠️ **Do not read "24 BC cells inside the rockaway_inlet box" as the count.** The `ocean`
(lat ≤ 40.560) and `rockaway_inlet` (lat ≥ 40.540) crossing boxes OVERLAP by 0.02°, so
membership alone proves nothing; the defensible number is the **17-cell disconnected run
beyond the spit**.

#### 🔴 RECOMMENDATION RETRACTED 2026-08-14 — do NOT move the arm box

This was first written as "pull the `ocean` arm box south of the Rockaway Point tip so those
17 cells demote". **That was wrong, and the user was right to challenge it.** Measured:

| | |
|---|---|
| distance from each of the 17 cells to the nearest NACCS support point | min 273 m, median 672 m, **max 1,129 m** |
| the domain's own support screen | 2.0 km |
| distance to the nearest active WET interior cell | min 25 m, median 50 m |
| distance to Raritan Bay | 13.5 km |

Every cell is well inside the support screen, so these are forced by **real save points, not
by extrapolation** — which is the single thing that would have made this a defect. They
border live interior water at 25–50 m, so they are a working open boundary, not a stranded
fragment.

⭐ **And the physics runs the OTHER way.** A closed wall across 1.2 km of −4 to −7 m water
reflects; a well-supported forced opening does not. Demoting these 17 cells would make the
model slightly worse. "Part forced, part walled" was rhetoric — an inlet that is partly open
is not obviously wrong, and nothing measured says it is.

**What IS wrong is bookkeeping only:** `validate_region_v1_5.CROSSINGS` declares
`rockaway_inlet` `closed` while the build forces 17 cells of it. ⏳ **Fix the DECLARATION,
not the geometry** — split the crossing, or restate it as "closed except its outer throat,
which the ocean arm forces from NACCS at ≤1.13 km support". This touches no mask and
therefore **does not block the freeze**.

⚠️ One thing worth WATCHING rather than pre-empting: a narrow forced opening immediately
beside a 1.2 km wall is the geometry that can produce an artificial jet. That is measurable
with the flux cross-sections (build sequence step 5), not by argument, and it is not a reason
to change anything now.

#### 4. ✅ FIXED 2026-08-14 — the Raritan discharge is IN, and it is the biggest inflow anywhere

`data/discharge_v1_5/usgs_sandy_discharge_v1_5.nc`, catalogued as
`usgs_sandy_discharge_v1_5`. 🔴 A **second** file: `data/discharge` is a symlink into the
frozen archive and the port fixture is pinned to its 6-point version — the same rule as
`data/elevation` vs `data/elevation_v1_5`.

| gauge | mi² | peak m³/s |
|---|---|---|
| **01403060** Raritan R below Calco Dam | 785.0 | **110.4** |
| **01405030** Lawrence Brook at Westons Mills | 44.9 | 2.0 |
| *(next largest in either domain: Manasquan)* | | *18.4* |

⭐ **110.4 m³/s is six times the largest inflow the model previously had.** The cut was a
closed wall, so this was a compound-flood hindcast with its main river missing.

Inflow points sit in the same reach ~300 m apart — (−74.2997, 40.5090) bed **−2.08 m** and
(−74.2960, 40.5085) bed **−2.09 m**, both verified against the post-CoNED merged bed and both
landing on `mask==1` cells within 8 m. 🔴 NOT the previously queued (−74.2920, 40.4905),
re-checked here and confirmed to be **+8.99 m of dry land on a `mask==3` cell**.

**Which discharge file a domain uses is now a DOMAIN fact** (`Domain.discharge_geodataset` →
`BaseConfig` → `model.py`), like `region` and `refinement`, because which rivers enter is
decided by where the boundary was drawn. `v1_monmouth` still resolves to the archived
6-point file, so the port fixture is untouched. `provenance.py` resolves it at call time so
the recorded provenance names the file actually read.

##### ⚠️ The South River is ungauged for Sandy, and is DECLARED rather than absorbed

STATUS asked to "check for a South River gauge rather than accept the deficit silently".
Checked against the NWIS site service over the Raritan basin:

| gauge | mi² | Sandy record |
|---|---|---|
| 01405500 South River at Old Bridge | 94.6 | ❌ **discharge ended 1988-10-04** |
| 01405400 Manalapan Bk at Spotswood | 40.7 | ⚠️ exists, but reads **0.00 cfs on 2012-10-29** |

Manalapan is regulated above Duhernal Lake, and a zero on the day the Raritan more than
doubled is not a usable proxy. So the South River (94.6 mi²) is genuinely missing. Gauged
area feeding the cut: **829.9 mi²**. Scaling from the main stem's peak unit runoff
(3,900 cfs / 785 mi² = 4.97 cfs/mi²) puts the deficit near **470 cfs ≈ 13 m³/s** against a
modelled peak of ~110 m³/s.

🔴 **Deliberately NOT synthesised.** Against a multi-metre surge in Raritan Bay, 13 m³/s is
immaterial — the same argument the discharge module already makes for Shark River and the
Navesink — and a drainage-area-ratio estimate would sit in the output file looking like data
while being an assumption. If it ever matters, it goes in as its own declared arm.

#### 4b. ✅ ARM BRACKETS RE-CUT 2026-08-14 — the old ones could not catch the defect they exist for

| arm | as built | old bracket | **new** |
|---|---|---|---|
| ocean | 1,187 | [200..4000] | **[1000..1400]** |
| narrows | 61 | [20..400] | **[45..85]** |
| arthur_kill | **24** | [15..300] | **[16..40]** |

🔴 **`arthur_kill` is the lesson.** Before the CoNED tier it was **59 cells in two runs** — 24
real plus 35 spawned by phantom water — and 59 passed `[15..300]` without a murmur. A bracket
wide enough to admit the defect it exists to catch is not a bracket.

⚠️ **A `raritan` boundary ARM was NOT added, and queue item 3 asking for one is withdrawn.**
`domain.py` already says why: arms are where `mask==2` is *allowed*, and across a discharge
cut it never is. The cut is governed by `no_waterlevel_boxes['raritan_cut']`, which makes an
imposed level there a build-time error — the correct mechanism, and it asserts clean. The
old warning that the `arthur_kill` box "was silently ADOPTING THE RARITAN RIVER" is also
stale: that box spans lon −74.2800…−74.2400 and the Raritan cut is at −74.2997, ~500 m
outside it. Both were true of the mis-located cut, and neither survived its correction.

Correct observation: there is no discharge yet. The Raritan cut currently has its `mask==2`
demoted and a `raritan_cut` no-waterlevel zone asserting clean, so it is a **closed wall**.
It needs step 4 of the queue below (USGS `01403060` + an inflow point at −74.2997, 40.5090).

---

### ✅ The mesh is SIZED ON THE DRAWN POLYGON and every invariant is green

`scripts/probe_mesh_size.py` → `data/probe_mesh_v1_5_drawn`, 2026-08-13, on the hand-drawn
region with the eHydro tier in the stack:

**698,969 faces · 428,663 active · ×1.28 v1 (547,408) · projected SnapWave ~3.8 h** —
comfortably inside a 12 h batch. Boundary: **1,307** water-level cells, **957** outflow.
Latest probe dir: `data/probe_mesh_v1_5_fix2` (both boundary fixes above applied).

| arm | cells | runs | bracket | z range |
|---|---|---|---|---|
| ocean | 1,187 | 2 (1,170 + 17) | [200..4000] | −26.95 … −1.35 |
| narrows | 61 | **1** ✅ | [20..400] | −29.57 … −1.18 |
| arthur_kill | 59 | **2** 🔴 see defect 3 | [15..300] | −13.71 … −1.38 |

⭐ **`mask==2` cells outside every declared arm are demoted** — Rockaway Inlet and the
Raritan cut, exactly the two crossings `validate_region_v1_5.py` predicted would need it.
The `raritan_cut` no-waterlevel zone asserts clean, so the discharge cut carries no imposed
level.

All invariants pass: no outflow BC on water · no paved-over surveyed channel · no interior
inactive islands · **no NoData under an active cell** (the eHydro tier closed that) · no
active cell in a land box · every `mask==2` inside exactly one arm, all wet, counts in
range · no imposed level in a no-waterlevel zone.

⚠️ `arthur_kill` at 59 cells sits in the lower third of its `[15..300]` bracket, and 35 of
those 59 are the SPURIOUS run (defect 3). The real cut is 24 cells. Re-bracket only after
the polygon is fixed.

### The geometry as drawn

🔴 **`data/region_v1_5_raritan_edited.geojson` IS THE REGION.** Hand-drawn in QGIS by the
user, 2026-08-13, over Esri imagery + CUDEM: 40 vertices, valid, CCW, 2,281 km².
`nj_sfincs/domain.py` now points at it (it had been left on the superseded generated
polygon, which has been deleted).

✅ **The generator is retired.** `scripts/build_region_v1_5.py` →
`scripts/validate_region_v1_5.py`: it READS the drawn file and has no write path. Run it as
the gate — `python scripts/validate_region_v1_5.py [--plot]`.

⭐ **It declares CROSSINGS, not segment tags, and that change caught two errors.** A
hand-drawn vertex lands where the cursor landed, so attributing a crossing to a vertex pair
is unsound. The validator walks the ring at 50 m through the *same* elevation stack
`build_static` reads, finds contiguous reaches below −0.5 m, and requires each to sit inside
exactly one declared coordinate box. An undeclared wet reach is a failure — it is imposed
ocean level somewhere nobody looked.

🔴 **The crossing table below REPLACES the earlier one, which was wrong in two places.**
"nearest ADCIRC" is now the WORST gap along the reach, and only over the **load-bearing**
band (−10 m ≤ z < −0.5 m): where the ring runs deeper than `mask_zmin`, `create_active`
trimmed first and the ring decides nothing.

| crossing | kind | wet length | worst NACCS gap | bed source |
|---|---|---|---|---|
| ocean (limits + closure, one reach) | forced | 134.42 km (44.63 load-bearing) | 2.58 km | CUDEM |
| **Rockaway Inlet** | **closed** | 2.99 km | — | CUDEM |
| Verrazzano Narrows | forced | 1.55 km | 0.32 km | CUDEM |
| Arthur Kill mouth | forced | 1.53 km, **2 reaches** | 0.76 km | CUDEM + **GMRT** |
| Raritan River | **discharge** | 0.45 km | — | **GMRT** |

**Error 1 — the Raritan cut was mis-located.** It was recorded as a 1.79 km segment which is
**dry ground from end to end** (+5.8 to +22 m in both `nj_10ft_dem` and GMRT). The real
crossing is a **0.45 km** wet reach at **lon −74.2997, lat ~40.5065–40.5115**, inside the
*neighbouring* 2.39 km segment. ⚠️ The queued inflow point (−74.2920, 40.4905) derives from
the wrong segment's midpoint and sits at **+8.9 m on land**; use ≈(−74.2997, 40.5090).

**Error 2 — Rockaway Inlet was never listed.** The ring closes across **2.99 km of water
reaching −10 m** between Rockaway Point and Coney Island. That is *how* "Jamaica Bay is
excluded" is implemented, and it is fine — that prism exchanges with the ocean through this
inlet, not with Lower Bay — but it is a third wet cut and `create_boundary` will raise
`mask==2` along it, to be demoted. It is now declared `closed`.

Also: the Arthur Kill crossing is **two** reaches spanning several segments, not the single
1.06 km segment labelled `arthur_kill` — the ring runs through water from the Ward Point
shore round to Perth Amboy.

All five obs gauges fall INSIDE, including `sss_great_kills` — the ring goes around the
landward side of the harbour, so the only true interior holdout survives.

### ✅ RESOLVED 2026-08-13 — the two western cuts now have real soundings

**Decision (user, 2026-08-13): one near-Sandy eHydro survey per cut, GMRT for the rest,
and move on.** Built by `python scripts/download_ehydro_nj.py --set raritan` →
`data/elevation_v1_5/ehydro_raritan_ak.tif` (5 m, UTM18N, NAVD88, **187,138 carved
cells**), catalogued as `ehydro_raritan_ak` and now the **TOP tier** of
`DEFAULT_ELEVATION_LIST`.

| cut | survey | vs Sandy | min bed GMRT → eHydro |
|---|---|---|---|
| Arthur Kill mouth | `NJ_03_SWO_20140814_CS_4160_45X` | +654 d | −8.98 → **−13.56 m** |
| Raritan River | `RR_01_RAR_20120726_CS_3844_15X` | **−95 d** | −4.94 → **−9.85 m** |

⭐ **GMRT was under-cutting both channels by ~5 m.** That is the number that justifies the
detour: a 50 m bed does not resolve a dredged channel, and both of these cuts are where the
domain's exchange is imposed.

⚠️ **Accepted, not fixed:** eHydro surveys navigation channels, so it reaches ~37% of the
Arthur Kill cut's wet width and ~14% of the Raritan's; the flanks and the remaining
~5.5 km² of the CUDEM hole stay on GMRT **by decision**. `validate_region_v1_5.py` now
passes.

🔴 **`data/elevation` is a symlink into the FROZEN archive and is read-only**, so the new
tier lives in `data/elevation_v1_5/`. `download_ehydro_nj.py` grew a `--set` preset
(`nj` | `raritan`) and now refuses to run the `nj` preset at all, since that would rewrite
the archived tier.

⚠️ Two things the build had to handle, recorded so they are not rediscovered: the two
surveys are on **different reduction planes** (`NJ_03_SWO` on C.O.E. Mean Low Water, 3.5 ft
below NAVD88; `RR_01_RAR` on MLLW, 2.9–3.0 ft below), so the builder now reads each survey's
stated plane from its own header rather than assuming MLLW and querying VDatum — that
assumption would have put ~0.17 m of systematic error into the Arthur Kill. And newer eHydro
XYZ files ship a metadata header and a lowercase `.xyz` extension, so the reader is
header-tolerant and the globs are case-insensitive.

<details><summary>The gap this replaced (kept for the record)</summary>

### ~~🔴 BLOCKER — the two western cuts have NO real bathymetry~~

`validate_region_v1_5.py` fails on this, and it is a genuine data gap, not a threshold to
relax. **CUDEM has no tile west of lon −74.25** in this latitude band — a clean vertical
edge — so at the Arthur Kill mouth, the Perth Amboy waterfront and the Raritan River the
merged bed falls all the way through the stack to **`gmrt_nj`, the ~50 m offshore tail**.
Every tier above it is NoData there:

| point | only tier with data |
|---|---|
| Arthur Kill mid-channel (−74.2599, 40.5049) | `gmrt_nj` (−8.14 m) |
| Raritan R channel (−74.2997, 40.5090) | `gmrt_nj` (−3.15 m) |
| Perth Amboy waterfront (−74.2650, 40.5000) | `gmrt_nj` (−0.76 m) |
| Narrows mid-channel | ✅ `cudem_nj` (−29.47 m) |

⚠️ `nj_10ft_dem` *does* cover this ground, but its `zmin: 0.001` screen is there precisely
because it is a lidar topo product — it cannot supply a bed below the waterline, and it
reads +9 m across the (dry) mis-located Raritan segment.

🔴 **Confirmed NOT a download-script omission.** The `northeast_sandy` 1/9″ collection has no
`w074x50` tile at `n40x50` or `n40x75` (directory listing checked; the column stops at
`n39x75`), and the 1/3″ `NCEI_third_Topobathy` urllist has nothing north of `n40x00` in the
w074 column either. Adding tiles to `download_cudem.py` will not fix it.

**This is the elevation check that build sequence step 3 says to do before paying for the
subgrid, and it fails.** A forced cut is where the whole domain's exchange is imposed; a
50 m bed there sets the conveyance of the boundary the domain exists to test.

#### ✅ eHydro CHECKED 2026-08-13 — it is a real partial fix, not a dead end

134 surveys intersect the box (−74.34…−74.20, 40.46…40.54), **all CENAN** (New York
district), queried from the USACE eHydro FeatureServer. Measured against the WET part of
each cut, not the segment:

| cut | wet length | best single survey | union of all |
|---|---|---|---|
| Arthur Kill mouth | 0.684 km | 0.282 km (41%) `NJ_03_SWO_20160426` | **0.478 km — 70%** |
| Raritan River | 0.342 km | 0.058 km (17%) `RR_01_RAR_20140124` | **0.058 km — 17%** |

⭐ **A pre-Sandy Raritan survey exists**: `RR_01_RAR_20120726_CS_3844_15X`, **95 days
before** the storm — but it reaches only 14% of the cut.

🔴 **NO pre-Sandy survey covers the Arthur Kill MOUTH, and the naming is a trap.** The
surveys actually called *"Arthur Kill"* (`NJ_04_AKS_*`, including one from 2012-06-20) start
at **lat 40.521 — north of our cut at 40.504** and never touch it. The mouth is covered by
*"Seguin Pt.-Ward Pt.-Outerbridge"* (`NJ_03_SWO_*`, from 2014-08-14) and *"Perth Amboy Anch
& 2nd Chnl"* (`NJ_02_PAA_*`, from 2013-05-02). Selecting on the channel name would have
carved the wrong reach and reported success.

**What eHydro does NOT fix.** It surveys dredged channels, so the flanks stay on GMRT. Over
the whole CUDEM hole inside the region: **8.34 km² of water** (29% of the region's western
water), of which eHydro footprints reach **2.88 km² (35%)** — **5.45 km² stays on GMRT**
whatever we do.

**Verdict: worth doing for the Arthur Kill** (70% of a *forced* cut, and the covered part is
the dredged high-conveyance core that sets the exchange), **marginal for the Raritan** (17%,
and that cut is a discharge BC, where the cross-section bed matters less). The machinery
already exists — `download_ehydro_nj.py` is a carving tier with a water-only clip, VDatum
MLLW→NAVD88 offset field and a mask to each survey's `Bathymetry_Vector`. Adding surveys to
its `SURVEYS` list is the whole change.

⚠️ Two things to verify before trusting the output: `EPSG_SRC = 3424` (NJ State Plane) is
**hardcoded** and must be confirmed per survey rather than assumed; and the district sign
convention — all of these are CENAN, the same district as the Shark River survey the script
already handles, so the existing handling should carry, but check the sounding range.

Still open as alternatives for the 5.45 km² eHydro cannot reach: NOAA NOS hydrographic
surveys / BAG, or an NCEI CoNED NY–NJ harbor topobathy DEM.

</details>

### ⭐ What fixed the boundary, after three wrong attempts

The water-level boundary was a tangle looping through Lower Bay. **It was never the region
outline.** `create_boundary` puts `mask==2` on the outermost active WET cells, and the
active/inactive interface is set by `create_active(zmin=mask_zmin)` *before* the region clip.
In Lower Bay that deactivated the dredged channels (Ambrose −27 m, Chapel Hill, Raritan
Reach); they stay CONNECTED to the sea through the bay mouth so `_fill_inactive_holes` cannot
reach them (finding 9, verbatim), and every channel got ringed with imposed ocean level.

The fix is one declared `always_active_boxes_ll` entry over **Raritan + Lower + Sandy Hook
Bay** — "bay water is in the domain at any depth". Ocean arm 2,398 → 1,202 cells and one
continuous run; detached islands 25/41,478 cells → 5/169. ⚠️ Moving the closure, tightening
the isobath and patching individual channels all failed first. Do not re-try them.

### Queued, in order

1. ✅ **DONE — `build_region_v1_5.py` retired** to `scripts/validate_region_v1_5.py`, no
   write path, provenance recorded in the geojson's properties. The stale 16-tag `segments`
   property was stripped from the drawn file (geometry sha verified unchanged) — those tags
   are what produced the mis-located Raritan cut.
2. ✅ **DONE — the bed under the two western cuts** (eHydro tier, above).

2b. 🔴 **Test the hypothesis in defect 2b** (disable `_fill_inactive_holes`, re-probe,
   see whether the 14,141 out-of-region active cells vanish). Cheap, and it decides whether
   the built domain is the drawn domain.

2c. 🔴 **~~move ring vertices v29/v30/v31~~ — CANCELLED 2026-08-14. The ring is correct.**
   Replaced by: **add a Staten Island topo/topobathy tier** (defect 3b above) so the Ward
   Point headland exists in the bed. Everything after this bakes the geometry in, so do it
   before the freeze. Then re-run, in order:
   `python scripts/validate_region_v1_5.py` →
   `NJ_DOMAIN=v1_5_raritan python scripts/probe_mesh_size.py data/probe_mesh_v1_5_fix3` →
   `NJ_DOMAIN=v1_5_raritan python scripts/plot_waterlevel_boundary.py data/probe_mesh_v1_5_fix3`
   and LOOK at the figure before freezing.
3. **Declare a `raritan` boundary arm** in `domain.py` (there are only three: ocean, narrows,
   arthur_kill) and **tighten all four arm boxes and their cell brackets**. ⚠️ The current
   `arthur_kill` box runs to lon −74.280 and was silently ADOPTING THE RARITAN RIVER — 41
   cells in two fragments passed a `[15..300]` bracket doing no work. ⚠️ The bay
   `always_active_box` west edge is lon −74.30, which clips the Raritan crossing at
   −74.2993…−74.3004 almost exactly; give it slack.
4. **Raritan discharge** (user approved): add `01403060` *Raritan R below Calco Dam at Bound
   Brook* (−74.5483, 40.5511) to `SITES` in `download_usgs_sandy_discharge.py`; inflow point
   ≈**(−74.2997, 40.5090)** — 🔴 **NOT** the previously queued (−74.2920, 40.4905), which is
   +8.9 m of dry land. Add a `no_waterlevel_box` over the cut — an imposed ocean level
   across a tidal river PUMPS it, the mirror of the Navesink drain.
   ⚠️ `01403060` is a LOWER BOUND: Lawrence Brook and the South River join below it. Check
   for a South River gauge rather than accept the deficit silently.
4. **Re-probe, re-plot** (`scripts/plot_waterlevel_boundary.py`). Then verify Great Kills is
   hydraulically CONNECTED (a coarse cell across the entrance would seal it — the dammed-inlet
   failure) and that `point_zb` at 2295 is not dry (else `series_source="map"`).
5. **Then** the three bootstrap items: `n_waterlevel_support` (from the builder's screen on
   the real mesh), `hwm_rules` for v1.5 basins, and the fingerprint in `premier.EXPECTED`.
   Until all three land, 5 tests stay red BY DESIGN and nothing may be frozen or run.

### ⚠️ The freeze was STARTED and DELIBERATELY KILLED, 2026-08-13

`scripts/freeze_mesh.py` ran for ~4 minutes before the Narrows defect was spotted; it was
killed and `data/frozen_mesh_v1_5_raritan_z10` deleted. **There is no frozen mesh.** Do not
restart it until defect 3 is fixed — freezing bakes in the mask, and the fingerprint is
computed from it.

### Two known defects I introduced, still open

- **`_drop_detached_active_islands` can eat cut cells.** It cost `narrows` 229→113 and
  `arthur_kill` 177→92 before the bay box. Keeping only the largest component is too blunt
  near a 1 km cut.
- **Its log line is structurally wrong**: it reports "N of them were water-level BC cells",
  but it runs BEFORE `create_boundary`, so that count is always 0. Report bed range instead.

---

## Then: the build sequence (Phase 5b)

1. ✅ **Region polygon — DONE.** Hand-drawn, not generated:
   `data/region_v1_5_raritan_edited.geojson`, gated by `scripts/validate_region_v1_5.py`.
   ⚠️ The "ring segments tagged ocean/land/narrows/arthur_kill" design described below was
   tried and **abandoned** — see the crossing declarations above for why.

   ⭐ **TWO GEOMETRY DECISIONS TAKEN 2026-08-13** — these SUPERSEDE
   [plan_v1_5_original.md](plan_v1_5_original.md) lines 168 and 31. Indicative vertices
   are in `scripts/naccs_coverage_map.py`; see `reports/naccs/coverage_map.png`.

   **(a) Arthur Kill is cut at its MOUTH** (Perth Amboy / Ward Point), not at the Kill
   Van Kull junction. The whole kill is OUT of the domain. The plan's north cut had **no
   NACCS support at all** — nearest save point 9.56 km, 0% within 2 km — and would have
   needed the 1-node Bergen Point gauge fallback. The mouth cut forces straight from
   NACCS: nearest point **0.21–0.87 km**, 16–19 points within 2 km.

   ⚠️ **What this costs, stated plainly.** It walls off the Raritan Bay ↔ Newark Bay
   exchange, and it puts a forced level on ~1 km of the Raritan shoreline that v1.5
   otherwise computes. That is a *much* milder version of the defect v1.5 exists to fix
   — a dense product across a 1 km cut, not a 2-node interpolation across 123 km — but
   it is the same kind, so say so rather than claiming the interior is wholly computed.
   The Narrows still carries the Upper Bay + Hudson prism and stays open.

   ✅ **RESOLVED against USGS STN 2026-08-13 — the mouth cut costs 8 marks.** Queried
   `stn.wim.usgs.gov/STNServices/HWMs/FilteredHWMs.json?Event=24` (Sandy is event **24**;
   910 marks nationally). The Arthur Kill limb — Carteret / Woodbridge / Elizabeth, box
   (−74.30…−74.15, 40.52…40.68) — holds **8** marks in the FULL STN set. Our local file's
   zero was indeed its lat-40.515 clip, but "HWM-rich ground" was an overstatement
   regardless. 8 marks, on ground deliberately out of scope, is a price worth paying for
   an arm that forces from NACCS at 0.21 km instead of needing a gauge fallback at
   9.56 km. **Scope call, 2026-08-13: the goal is "can we force Raritan Bay correctly",
   not the limb. Extending north is possible future work.**

   **(b) The ocean arm is v1's trace extended ~3.3 km STRAIGHT north to Rockaway Point**
   — not a diagonal across the Lower Bay mouth. Measured off the frozen mesh: v1's
   ocean-side `mask==2` already runs at lon −73.936…−73.947 from lat 40.44 to its north
   edge at 40.5202, and in the 40.46–40.47 band its easternmost cell is at −73.9364,
   Rockaway Point's own longitude. The arm is a continuation, not new geometry.
2. **Refinement** — a NEW `refinement_v1_5_raritan.geojson`. Neither existing recipe is
   usable: a refinement recipe is not portable, and a level gate written for one basin will
   refine another basin's open water to its finest level. L3/L4 on the two cuts and their
   approaches, L3 Sandy Hook Bay + Shrewsbury/Navesink, L2 Raritan open water, L0/L1 shelf.
   **Size it with `scripts/probe_mesh_size.py` BEFORE building** — SnapWave is 90–95% of
   runtime and scales with the mesh.
3. **Subgrid + freeze** — the expensive irreversible step. Do the elevation check first:
   `nj_10ft_dem` is NJ-only, so Staten Island, the Rockaway shore and the Narrows fall
   through to CUDEM/3DEP. `build_static` now asserts no active cell has NoData in the merged
   bed, which turns a silent hole into a build error.
4. **Mask + boundary** — declare `boundary_arms` (ocean / narrows / arthur_kill) and
   `land_boxes` (Staten Island south shore, Jamaica Bay). The whitelist replaces the
   half-plane `MaskOverride` patches; the type no longer has an unbounded side, so the
   defect class is unrepresentable.
5. **Flux cross-sections** — `sfincs.crs` observation lines just *inside* each arm. SFINCS
   writes `crosssection_discharge` every 10 min. ⭐ **This is what makes the relocation
   auditable**: the Narrows carries the Upper Bay + Hudson tidal prism, and a tidal prism is
   comparable against literature. Without it the new boundary is asserted, not measured.
6. **NACCS forcing** — `build_naccs_boundary.py`, with the depth screen applied **seaward of
   `open_coast_max_y` only**. Declare the resulting count as
   `Experiment.n_waterlevel_support`, never by relaxing the domain value.
7. **Register the fingerprint** in `premier.EXPECTED` + `KNOWN` **before** running anything.

---

## The four seeded arms

Already in `nj_sfincs/experiments.py` under `v1_5_raritan`:

| arm | what it is |
|---|---|
| `naccs-premier` | the premier: relocated boundary + CORA per-support-point waves |
| `naccs-nowaves` | same boundary, SnapWave off — cheap, levels + phase only |
| `noaa-2node` | the incumbent 2-node interpolant, kept only to show what relocation bought |
| `naccs-premier-z15` | −15 m boundary: **a different DOMAIN**, `mesh_key` sibling |

---

## Open, deliberately not decided

- **STWAVE vs CORA waves.** A single-variable arm, withheld to avoid moving two variables at
  once. Same logic says do not bundle it with a domain move. CORA-as-wave-boundary is
  *adopted* settled physics (admissible at 7/7 support points vs ERA5's 0/7).
- **The +0.027 m setup problem.** The reference configuration generates only +0.027 m of
  setup from the −10 m boundary to shore with waves ON — far too small, and an open thread.
  It bears directly on whether a deeper boundary buys anything, which is why
  `naccs-premier-z15` exists.
- **−2 m boundary: DROPPED, not deferred.** Setup-at-the-boundary XOR SnapWave, never both
  (Leijnse et al. 2025 §4.4). At −2 m the embedded setup in NACCS is the whole signal, so
  SnapWave would have to be off — the branch measured to overestimate max water depth by
  ~1 m.
- **`south_coast` marks.** 4 of 38 are hydraulically disconnected from the water-level
  boundary in the model: they move by 0.0005 m across four different boundaries, including
  one that adds +0.115 m uniformly to every boundary cell. They contribute a fixed −0.53
  bias / 0.785 RMSE to every arm and dilute any pooled score. Flagged **before** the results
  landed, so excluding them is a pre-flagged re-analysis, not a post-hoc one.

---

## Known gaps in this repo

- ✅ **The archive IS read-only on disk** — `nj_coast_sfincs/data` is `dr-xr-xr-x`,
  `experiments/` deliberately left writable (the port fixture is copied out of it).
  ⚠️ That freeze is what broke `dedupe_home.py`; read the quota section above before
  changing either permission.
- **`ruff` is not installed anywhere on this machine**, so the tree has not been formatted.
  It is written to the 88-column style by hand. Run `ruff format . && ruff check .` once,
  in its own commit, before any logic edits — that is the only moment it is free.
- ⚠️ **`nj_sfincs/plots.py` was untested at runtime until 2026-08-15**, and the first thing
  to run it found a bug (below). `plot_gauge_verification`, `plot_hwm_residual_panels`,
  `plot_motf_panels` and `animate.animate_field` are now exercised on the v1.5 arms. The
  rest of the module still has not drawn a figure.
- ✅ **`notebooks/v1_5_raritan/sandy-v1_5-viz.ipynb`** — 16 cells, headers only, no
  narration: metrics → gauges → HWM → MOTF → 2 animations → an `ipywidgets` picker over
  run × field × window → GIF save. MOTF is fed the waves-on arms only.

### 🔴 `plot_gauge_verification` drew FIVE ERROR BOXES and looked like a figure

Found 2026-08-15 by running the notebook — nothing had called `plots.py` since the port.
`gauge_series_frame` documents `mod` as **optional**, but `_model_series` handed `None`
straight to `his_series`, which does `mod.output` → `AttributeError` on every
`series_source="his"` gauge, i.e. all five on this domain.

⭐ **Why it survived: the caller catches per gauge and draws the exception INTO the panel**
(`plots.py:786-790`, "one bad gauge must not kill the figure"). A total failure therefore
rendered as a clean five-panel figure full of grey text instead of a traceback. **A
per-item catch that degrades gracefully hides a 100% failure rate exactly as well as a 1%
one** — the count of panels that drew *nothing* is the thing worth asserting on.

✅ Fixed by `validate.core.open_run()`, memoised per run dir so the ~21 s `SfincsModel`
open is paid once per run instead of once per gauge per run. 59 tests OK, port gate still
bit-for-bit.

### 🟡 First v1.5 gauge numbers — PROVISIONAL, straight off `gauge_series_frame`

Not the validator, and every one is a **high-water** statistic (all four sensors clip below
their recordable floor). `naccs-premier`, model − observed:

| gauge | obs pts on model clock | bias |
|---|---|---|
| `sandy_hook` | 283 | **−0.006** |
| `sss_arthur_kill_mouth` | 384 | −0.107 |
| `sss_narrows_bkln` | 309 | −0.116 |
| `sss_narrows_si` | 236 | −0.401 |
| `sss_great_kills` | 101 | **−0.555** |

⚠️ **Great Kills is the one to chase, and it is NOT yet a model finding.** The forcing
product is independently measured 0.35–0.39 m LOW at that same sensor (§"NACCS vs those
sensors"). Two numbers of the same sign at the same place may share a cause or may be
coincidence at n=101 — do not attribute it to the relocated boundary until the scorer has
run and the arms are compared paired.

### 🗑️ Archive trimmed 2026-08-15 — 18 GB reclaimed, 89.99 → 72.02 G

🔴 **`du` on `nj_coast_sfincs/experiments` reported 32 G and was MISLEADING.** After the
dedupe, ~40 GB of apparent size there is *shared inodes* with `data/frozen_mesh_*`, so
deleting the `sfincs.nc` / `sfincs_subgrid.nc` / `roughness.nc` / subgrid-tif copies frees
**nothing at all**. Only ~24 GB was ever unique. Measure by `st_nlink`, not by `du`, before
planning any trim.

| removed | freed | recoverable? |
|---|---|---|
| `snapwave.upw` ×7 | 4.30 GB | ✅ runtime upwind table, NOT in `sfincs.inp` — the solver rebuilds it |
| 31 `*_hmax_lev3.tif` floodmaps | 5.06 GB | ✅ re-downscaled from a surviving `sfincs_map.nc` |
| 11 non-premier `v1_monmouth/sfincs_map.nc` | ~5.2 GB | ❌ gone — but every score is in `v1_monmouth/metrics.csv` |
| (dedupe, same day) | 3.42 GB | — |

**KEPT deliberately:** all 17 `sfincs_his.nc` (12 MB total — the gauge series, and what a
notebook actually opens), `v1_monmouth/metrics.csv`,
`v1_monmouth/faber-waves-premier/sfincs_map.nc`, and **all five
`v2_barnegat/sfincs_map.nc` (8.79 GB)**.

✅ **v2_barnegat SCORED 2026-08-20** — `experiments/v2_barnegat/metrics.csv` (5 rows,
184 keys) via `scripts/score_v2_barnegat.py`: the archived runs rescored in place
(through the `data/v2_barnegat_runs` symlink) with the CURRENT scorer, so the numbers
are NOT the archived campaign prose — active-mask screen, `_scored` HWM keys, FA
decomposition all apply. Headlines (median, 50 m; n=60): wave-cora RMSE 0.507 /
CSI 0.672 · +bed-ehydro **0.493** / 0.702 · +mask-inlet 0.582 / 0.553 ·
+tide-shift 0.599 / 0.550 · BRACKET+manahawkin-open 0.509 / 0.707 (`bracket=True`,
inadmissible by construction). ⚠️ The five arms span THREE fingerprints (pre/post
inlet-repair mask, ehydro bed) — compare within a fingerprint only. **The 8.79 GB of
maps are now trimmable** (deletion manifest; keep the floodmap caches + his files so
everything stays re-computable).
