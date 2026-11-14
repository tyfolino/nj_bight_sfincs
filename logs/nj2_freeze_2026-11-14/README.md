# nj2 (Model 2.0): registration, coarse bed (J1), freeze chain (J2) — 2026-11-14

Goal (user 11-14): Model 2.0.0 "ready to run" by Mon 11-16 on the 2012 bed (2026 bed Tue/Wed). Domain names
(user 11-14): mesh domain **`nj2`**; face-z bed domains **`nj2_bed2012`**, **`nj2_bed2026`** (after the freeze).
This agent owned `nj_sfincs/{domain,premier,experiments}.py`, `data/data_catalog.yml`, the ring, and the freeze
job scripts. Other agents delivered the refinement (`data/nj2_design/refinement_nj2*.geojson`), the sea line, the
two cut files, the obs table and the structures (`data/nj2_design/`), and their logs are `logs/nj2_{refinement,edges,bed2026}_2026-11-14/`.

STATUS AT HAND-OFF: see "Where it stands" at the end.

## 1. What is registered / written

| item | where | how |
|---|---|---|
| ring (201 named vertices) | `data/nj2_design/region_nj2_vertices.csv` → `data/region_nj2.geojson` (sha256 `9c66f3be…`) | `make_ring.py`: coordinates = `logs/v2_prep_2026-11-04/ring_new_full_v2edit.csv` VERBATIM (asserted, same order); the `note` column the splice dropped is restored (v4_hot_plus's notes; the new legs' kind + note); header written. Then `scripts/ring_to_geojson.py`. Not audited by `audit_region_v4.py` (it hard-codes v4's basins and overwrites the v4 record). |
| Domain `nj2` (BUILDING) | `nj_sfincs/domain.py` (block = `domain_nj2_block.py`) | `replace(V4_REFREEZE_SWZ_V11, …)`; see §2 |
| tests | `tests/test_nj2_domain.py` (11 tests) + `test_no_domain_is_building` now expects `{"nj2"}` | |
| catalog keys | `data/data_catalog.yml` (+8; previous copy `data_catalog.yml.before`) | `bed_nj2_coarse_25m`, `ehydro_hud_2012_v2`, `carve_v2_2012`, `carve_v2_2026`, `nyc_topobathy_2017_m` (11-12 draft, verbatim), `piers_v2_2012`, `gowanus_upper_v2` (new, §4), `naccs_sandy_nj2` (written by J2 step 4). All raster keys read through hydromt's `DataCatalog` (checked). URIs under `data/elevation_nj2/` — a real dir whose `v2` → `/scratch/tpj8/nj_bight_sfincs_data/v2` |
| mark file | `data/validation_nj2/sandy_hwms_nj2.geojson` | byte copy of `logs/v2_prep_2026-11-04/sandy_hwms_v2.geojson` (md5 `1e0214e9…`): 276 marks, headline 163 |
| J1 coarse bed | `j1_coarse_bed.slurm` + `check_coarse_bed.py` | §3 |
| J2 freeze chain (DRAFT, not submitted) | `j2_freeze_nj2.slurm` (+ `j2_md5_files.txt`) | §5 |
| J3 design gate (DRAFT) + its 4 arms | `j3_gate_nj2.slurm` (+ `j3_md5_files.txt`); arms in `experiments_nj2_block.py` (applied to `experiments.py` after GATE 2) | §6 |
| nj2 flux cross-sections | `data/nj2_design/flux_crosssections_nj2.crs` (`make_crs_nj2.py`) = `Domain.flux_crosssections` | §2 |
| weir-aware connected start | `nj_sfincs/sea_level.py` (`weir_uv_crests`): +2 / +3 m starts no longer fill ground behind a levee | §6 |
| base support-count preview | `base_support_count.py` → `base_support_nj2.txt` (J2 step 4b) | §5 |
| 2012-bed pier carve | `build_piers_2012.py` → `/scratch/…/v2/carves/piers_v2_2012.{tif,csv}` (Gowanus: the 2026-bed agent's build, §4) | §4 |
| §5 diff | `domain_diff.py` → `domain_diff.txt` (written 11-14 12:28; re-run once the refinement settles) | §2 |

Nothing in `premier.py` or `experiments.py` changed: `nj2` has no fingerprint until the freeze (the BUILDING state
forbids one), and no arms until its bed domain exists. Audit fixes of 11-14 (afternoon) touched `domain.py` (one new
field), `model.py` (`restore_diagnostics` reads it; one `[slr]` log line) and `sea_level.py` (weirs), all
behaviour-preserving for every existing domain (tests `test_flux_crosssections.py`, `test_sea_level.py`).

## 2. The nj2 Domain vs Model 1.1.0's (`v4_refreeze_swz_v11`) — field by field (`domain_diff.txt`)

**Changed (18 of 51 fields; `flux_crosssections` added 11-14):**

| field | 1.1.0 → nj2 |
|---|---|
| name, region, region_source | → `nj2`, `region_nj2.geojson`, `nj2_design/region_nj2_vertices.csv` |
| refinement | `quadtree/refinement_v4.geojson` → `nj2_design/refinement_nj2.geojson` (refinement agent's; see below) |
| mesh_key / face_z_from / building / n_waterlevel_support | `v4` / `_subgrid_v1_1c` / False / 3 → None / None / **True** / None (the building state: set at the freeze) |
| coarse_elevation_list | `bed_v4_coarse_25m` → `bed_nj2_coarse_25m` (J1) |
| waterlevel_line | `v4_design/waterlevel_line_v4.csv` → `nj2_design/waterlevel_line_nj2.csv` — **the same vertices** (asserted), an nj2 header |
| boundary_arms | − `narrows`, − `kvk_east`; + `hudson` (1,941 m), + `hell_gate` (684 m) as one-section LINE arms on `cut_hudson_nj2.csv` / `cut_hell_gate_nj2.csv` (flat ends, corridor 300 m), **bracketed from the J1b probe: `hudson` 28 cells → [22, 36], `hell_gate` 10 → [7, 14]** (11-14); the 4 sea sections + `cd_canal` identical to v4's (asserted) |
| mask_overrides | − `wall_bayonne`; + `wall_e88` (261 m of 3.22 m ground, e88→hellgate_w), + `wall_hellgate_east` (Astoria 300 m, low 2.02 m); the other 27 identical |
| obs_gauges | 1.1.0's 48 unchanged + 7: `noaa_battery` (scored holdout), `noaa_bergen_point` (scored, MLLW-derived NAVD88), `sss_gowanus` / `sss_hoboken` / `sss_hackensack_hud002` (output only, no series), `bc_hudson_cut` / `bc_hell_gate` (forcing diagnostics ~110 m inside the cuts). Rendered = the obs agent's `obs_nj2.obs` byte for byte (test) |
| dry_land_boxes_ll | + `prospect_park` (≥ 10 m), `green_wood_cemetery` (≥ 5 m), `jersey_city_heights` (≥ 15 m): positive checks on the new ground (CUDEM min 19.0 / 5.8 / 27.1 m) |
| hwm_rules | + 4 rules FIRST: `upper_bay_islands`, `hudson_nj`, `east_river`, `upper_bay_ny` (logs/v2_validation_2026-11-03 §1); no 1.x mark inside the 1.x ring changes basin (test) |
| hwm_geojson | `validation_v4/sandy_hwms_v4_1x.geojson` → `validation_nj2/sandy_hwms_nj2.geojson` |
| map_windows | + `upper_bay_hudson` |
| flux_crosssections (NEW field, 11-14) | `data/flux_crosssections.crs` (every other domain, unchanged) → `nj2_design/flux_crosssections_nj2.crs`: `barrier` + `throat` VERBATIM + `hudson_cut` / `hell_gate_cut` (each cut line moved 110 m inside, through `bc_hudson_cut` / `bc_hell_gate`, extended 150 m onto the banks) + `narrows` (Verrazzano) + `kvk` (lon −74.100). Copied to `sfincs.crs` at ARM staging (`model.restore_diagnostics`); `nj2_bed2012` inherits it. Outside the fingerprint |

**Unchanged (35)**, deliberately: epsg, latitude (39.86 — the nj2 ring's mid-latitude is 39.837; kept for
comparability), mask_zmin, nr_subgrid_pixels 16, the inflow walls and their radii, land boxes, sea closure (incl.
the Lewes vertices), no-waterlevel boxes (the river cuts), **discharge** (`usgs_sandy_discharge_v4_refreeze`, 61
points; walls from `…_v4_hot_plus_walls`, 61 — no new inflow in the new area), **elevation_list** (=
`V4_ELEVATION_LIST`: the NY ground is CUDEM 1/9″, `cudem_nj_v3` holds the 2015v1 NY tiles), precip / CN /
land cover / ksat / CORA waves (all clipped on v4's bbox, which contains the new area), **MOTF** raster, validity
raster and gap box (user 11-03: no new exclusion boxes), merged_dep_base_level 2, open_coast_max_y,
**snapwave_footprint_ll** (v3's area + Delaware Bay — see §4 (3)), plot_window, normal_surface_dir (v4's MHHW
raster covers the new area: Battery 0.70, Gowanus 0.72 m), waterlevel_buffer.

**Refinement polygons by name** (CLAUDE.md §5 trap): v1.1.0 1,528 → nj2 1,514 (J1's file: 1,513; 1,532 since the new-ground `narrow_channels`, next paragraph). Dropped names: none. Added:
`capemay_inlets` (×5), `hudson_waterfront`, `newark_meadowlands`. **Count changed: `narrow_channels` 1,503 → 1,482
(−21; area 161.8 → 159.8 km² in the refinement agent's own log)** — every other name identical in count. Ask the
refinement agent to confirm the 21 are the Narrows / KvK cut polygons it meant to drop (it is the one surprise).
(`domain_diff.txt` as re-run 11-14 12:28 reads the refinement agent's working file: 1,513 polygons, `narrows_cut` dropped.)

**`narrow_channels` on the new ground (user 11-14; `scripts/build_refinement_nj2.py`, 2.0.0 file).** v4's polygon
kept v4's geometry, so it stopped at v4's ring. Now `narrow_channels` = v4's geometry (clipped as before) ∪ v4's
SAME rule (`build_refinement_v4.narrow_from`: L3, bed −∞..+3 m, 25 m faces within 50 m of an NHD centreline where
the channel is < 50 m wide, sampled every 25 m) applied to the new ground only (nj2 landward ring − v4's, 246.9 km²:
the NY piece + 1.5 km² at Lewes). One change of SOURCE, not of rule: NHD maps New York's tidal creeks as part of the
Estuary waterbody (493), not StreamRiver areas (460), and Gowanus's centreline has no name, so v4's source (460 +
named paths) finds none of them. The new ground reads 460 / 336 / 312 areas + 493 waterbodies + every 558 path
(cache `data/nj2_design/nhd_new_area/`, `--fetch-nhd`). Result: 295 samples → **0.83 km² in 19 pieces; rows
1,482 → 1,501, area 159.8 → 160.7 km²**. By name: **Gowanus Canal** 73 samples (w ≈ 24–26 m) to the NHD head at
40.6817 N = Butler St (the flushing-tunnel station); **Newtown Creek** 42 (36–49 m), **English Kills** ~51, **East
Branch** ~1–3, **Dutch Kills** 30 (~39 m), **Maspeth Creek** 3 (it is mostly 50–80 m wide). **Not picked, by the
rule:** Wallabout Channel / Bay (100–180 m wide) and Bushwick Inlet (60–87 m, and no NHD centreline). Also picked:
the Lewes and Rehoboth Canal + its Lewes basins (41 + 12, 19–38 m; the 1.5 km² Lewes piece), a ~9 m creek in Jersey
City at (−74.071, 40.693) (26, near Caven Point / Port Liberté), and 2–5-sample spots at (−73.967, 40.842) Edgewater /
Fort Lee shore, (−73.964, 40.747) Long Island City, (−74.026, 40.704) and (−74.009, 40.697). Nothing along the
Hudson / East River pier slips (no centrelines there), the Kill van Kull or Bayonne. Faces: J1b below.

**Surprises / things to know**
- `wall_leak_bergen_rail_cut` (B4) sat on v4's Bergen-ridge edge; that edge is interior now, so the wall has no
  outflow cell left to act on. Harmless (walls act on mask 3 only); kept so the 27 inherited walls stay verbatim.
- The forced Hudson line holds ~330 m of low bank at `hudson_w` (accepted 11-03); those faces read z > −1 m, so
  `create_boundary` does not force them, and `wall_outflow_near_forced_m` (500 m) walls their outflow.
- `latitude` stays 39.86 (above).

## 3. J1 — the 25 m coarse bed for the nj2 ring

`NJ_DOMAIN=nj2 EXPECT_MD5=logs/nj2_freeze_2026-11-14/j1_expected.md5 sbatch logs/nj2_freeze_2026-11-14/j1_coarse_bed.slurm`
(main, 4 c, 32 G, 2 h limit; v4's build took 1 min 50 s, 4.2 G RSS, 0.34 G). Step 1 `scripts/build_coarse_bed.py`
(writes `/scratch/…/elevation_nj2/bed_nj2_coarse_25m.tif`, linked from `data/elevation_nj2/`); step 2
`check_coarse_bed.py`: lattice = v4's (whole-km origin, 25 m), max |nj2 − v4| where both exist, NoData inside the
ring (must be 0), the new ground's z distribution, and the bed along the two cuts (samples below −1 m / −0.5 m).
JOB / RESULT: see "Where it stands".

**J1b (63918563, `j1b_composite_probe.slurm`): the coarse bed is now a COMPOSITE = v4's, verbatim.** J1's warp
(md5 `8dd909a1…`) was NOT pixel-identical to `bed_v4_coarse_25m` where both exist: 292,857 px > 1 mm, max 4.61 m
(7 px > 0.3 m; Raritan Bay, Sandy Hook, Cape May). Why: `gdalwarp` output depends on the output EXTENT (nj2's box is
5 km shorter at the top). The same tier (`cudem_nj_v3`) warped today with the same GDAL 3.13.3 on v4's and on nj2's
box differs on 78,687 px (max 1.3 cm), identically with `-et 0`, so not the approximate transformer: the per-chunk
resampling, whose chunks follow the extent. Steep pixels (jetties, channel walls) and the MIN carving tiers turn that
into dm–m. Not chased further. Since the coarse bed gates refinement and sets face z, `composite_coarse_bed.py`
writes v4's pixels wherever v4 has one and the nj2 warp elsewhere — which is NOWHERE (v4's box contains nj2's and
`gmrt_v4` fills it), so `bed_nj2_coarse_25m.tif` = v4's 7560 × 10120 px verbatim (pixels and 2/4/8 overviews checked
exact; md5 `d30684e8…`; sidecar `…/elevation_nj2/bed_nj2_coarse_25m.tif.composite.txt`). It also covers the grid's
top strip that J1's warp missed (hydromt "does not fully cover bbox", 3,066–4,454 cells interpolated). The warp
was deleted after the check. Catalog `bed_nj2_coarse_25m` text updated; the key and path are unchanged.

## 4. User decisions of 11-14 wired in

1. **Pile-supported piers CARVED open in both beds** (supersedes 11-03's "piers solid"). 2012 bed: `piers_v2_2012`
   (`build_piers_2012.py`). **Units = the 2026 bed's rule, so both beds share ONE classification** (coordinator
   11-14, from the 2026-bed agent): `carve_2012` (PILE + a deck in the 2012 bed, p50 > 1.2 m; minus any the user's
   11-12 eye check called fill — none) + the eye check's `pile` units with a 2012 deck (Brooklyn Bridge Park Piers
   2 / 3 / 5, Piers 8 / 9A / 9B, w1012705545) = **29 units, 26.6 ha** (the first build today used `carve_2012`
   alone: 22, 13.7 ha). Solid-fill piers untouched. **Depth rule (shared with the 2026 bed; flag for the Fable
   audit / the user):** each unit = the median of the 2012 bed's water (< −0.5 m; HD_HUD else CUDEM) in a 5–40 m
   ring outside it: −0.59 … −13.11 m (p50 −4.06). The big Manhattan / Brooklyn piers come out −8.7 … −13 m because
   the ring reaches the deep pier-head water — a flat slab at that depth under a 1–2 ha deck adds more storage than
   a sloping slip bottom would. A shallower statistic is a one-line change in both builders; per-unit table
   `…/carves/piers_v2_2012.csv`. In J2 as `piers_v2_2012:min`.
2. **Upper Gowanus: the GCK 2020 section carried up the arm, both beds, ASSUMED.** ONE build serves both beds: the
   2026-bed agent's `gowanus_upper_v2_{2012,2026}` (`logs/nj2_bed2026_2026-11-14/build_gowanus_upper.py`: the 2020
   survey's last main-channel section, median **−2.69 m**, carried flat to the Butler St head over the NYC 2017
   lidar's water surface; on the 2012 bed only the cells `carve_v2_2012` does not hold, 1.55 ha). The catalog key
   J2 reads, `gowanus_upper_v2`, points at the `_2012` file (md5 `04b5828e…`). My own earlier build of the same
   thing (−2.87 m from a 25 m band, CUDEM outline) was deleted with its script — one build, not two.
3. **SnapWave OFF over the Upper Bay / lower Hudson** (as Newark Bay in 1.1.0): `snapwave_footprint_ll` unchanged
   (v3's area ends at the Narrows; the boundary agent measured 0.000 km² of the new area inside it,
   `logs/nj2_edges_2026-11-14/snapwave_footprint_check.txt`). Outside the fingerprint. Test-pinned.
4. Defaults kept: bank cut deferred; premier weirs = 1.1.0's file (`data/structures_v4/sfincs_overpeck_open_elizabeth_rahway_ground.weir`,
   md5 `e11966fc…` = the structures agent's copy); East River / Pierhead / Buttermilk 2012 surveys deferred;
   tide gates = 1.1.0's state (Overpeck dam open, its pool start file as in 1.1.0's template).

## 5. J2 — the freeze chain (DRAFT, not submitted): `j2_freeze_nj2.slurm`

One `nonpre` job (32 c, 180 G, 30 h, requeue), every step skip-if-done, two passes split by the one thing no job
may do — register a fingerprint:

| pass | step | what | est. time | scratch |
|---|---|---|---|---|
| 1 | 0 | preconditions (ring = CSV, line = nj2's, refinement + coarse bed exist, arms dropped / declared; **REFUSES** while `hudson` / `hell_gate` are unbracketed (1..10,000); **REFUSES** a base grid ≠ v4's (x0, y0, rotation, dx, dy predicted from the ring with hydromt's own rotated fit; 11-14: identical, nmax 1230 vs 1255)); quota (refuse within 200 G of hard) | ~30 s | — |
| 1 | 1 | `scripts/freeze_mesh.py` → `/scratch/…/frozen_mesh_nj2`, link `data/frozen_mesh_nj2`; **asserts the frozen x0 / y0 / rotation / dx / dy = `frozen_mesh_v4`'s** (`v4_shelf_steps` is level-1 index space) and that the band fits nmax × mmax; fingerprint → `fingerprint_nj2.txt` | 6–9 h (v4: 4 h 39 on emeraldrapids, 72–90 G) | +40 G |
| 1 | 2 | `premier.obs_points_ok` on the frozen mesh (build_static writes the registry's 55 points) | s | — |
| 1 | 3 | hand-placed files: `sfincs.weir` = 1.1.0's (or `NJ2_WEIR=`), md5; `diff <(ls frozen_mesh_v4) <(ls frozen_mesh_nj2)`; engine float32 u/v count (warn) | s | — |
| 1 | 4 | NACCS boundary on the frozen mask: the boundary agent's `build_naccs_boundary_nj2.py` → `data/gtsm/naccs_sandy_nj2.nc`. Its count → `experiments._NJ2_NACCS_SUPPORT` (the ARMS) | min | small |
| 1 | 4b | **BASE support-count preview** (`base_support_count.py` → `base_support_nj2.txt`, `[base-bnd] N`): hydromt's own selection (frozen `mask == 2` lines, `Domain.waterlevel_buffer`, `noaa_sandy_nj`) without a template. Tested on `frozen_mesh_v4`: 3 (Battery, Atlantic City, Cape May), 54 s, 5 G. WARN only | ~1 min | — |
| — | **GATE 1** | not registered → "pass 1 DONE", exit 0. Registered and consistent → pass 2. **Registered but inconsistent → REFUSES (exit 4, 🔴 in J2_CHECKS.txt)**: fingerprint mismatch, half-registered (EXPECTED without building=False or the reverse), `n_waterlevel_support` None or ≠ the 4b preview | | |
| 2 | 5 | base template (`run_experiments.build_template`; its `[bnd]` line is the first REAL assertion of `n_waterlevel_support`), then 1.1.0's hand steps: `fix_meteo_grid_origin.py --era5-bilinear` + `--check`; Overpeck pool start (`pool_ini.py`, `inifile` key). Skipped only when sealed + `sfincs_ini_regional.bin` + `inifile = sfincs_ini_regional.bin` in the inp; the key is then ASSERTED. Weir = frozen mesh's; premier audit; `compare_templates.py` vs 1.1.0's template: must succeed, both file lists go to J2_CHECKS.txt, and any file only in 1.1.0's template outside {`face_z_report.json`, `snapwave.{bnd,bhs,btp,bwd,bds}`, `sfincs.crs`, `subgrid/dep_subgrid_merged.tif`, `.subgrid_sha256`} REFUSES (each is written later by design; override one file after reading it: `J2_ALLOW_ONLY_OLD=`) | ~20–40 min | +40 G (copy) |
| 2 | 6 | **2012 bed** `_subgrid_nj2_2012`, parallel builder, 16 workers: v1.1c's plain paints → **`ehydro_hud_2012_v2` (PAINT)** → v1.1c's `:min` group → the v1.2a five (`raritan_mouth_fix_v4`, `gmrt_gap_fix_v4`, `nj36_deck_recut_v4`, `greategg_plug_fix_v4`, `barnegat_flat_fix_v4`) → **`carve_v2_2012`, `gowanus_upper_v2`, `piers_v2_2012`** (`:min`); v1.1c's Manning overlays. Asserts the provenance = exactly that list, the base (non-overlay) tiers = v1.1c's, no prepended tiers, Manning = v1.1c's (all GATED; the old ungated "base list" line compared overlays too and read False) | ~2–2.5 h (v1.1c: 7,494 s at 16) | +35 G bed, +~35 G checkpoints (removed) |
| 2 | 7 | merged-bed sweep `scripts/bed_audit.py --bed … --label nj2_2012` — ridges / decks / seams / NBI crossings, a LOCATOR, warn only (some checks hard-code the v4 ring) | ≤ 1 h | small |
| 2 | 7b | deck / connectivity re-check of the BUILT bed in the new area (`logs/nj2_decks_2026-11-14/`: `planned_bed.py --built experiments/nj2/_subgrid_nj2_2012/subgrid/dep_subgrid_merged.tif`, then `connect.py built_2012` → `blocked_built_2012.csv`; the planned bed had no dams). WARN only; summary in J2_CHECKS.txt | ~5 min, few G | ~0.3 G (scratch/tmp) |
| 2 | — | `dedupe_experiment_inputs.py --apply`; remove the builder's checkpoint dir | | |
| — | **GATE 2** (by hand, ~2 min) | register `nj2_bed2012` (`face_z_from="_subgrid_nj2_2012"`, `mesh_key="nj2"`), `NJ_DOMAIN=nj2_bed2012 python scripts/setup_face_z.py --from nj2 --bed _subgrid_nj2_2012`, register the sha it prints | 34 s | hard links |

**Disk:** peak +~150 G, net +~115 G (frozen mesh 40, template 40, bed 35). Scratch was **1,008 G of the 1 T soft
quota** on 11-14 (2 T hard): pass 1 alone crosses the soft limit (a grace period, not a failure). Free space first
(OneDrive archive of retired runs) or accept the grace period knowingly.

**Submit (both passes, from the repo root):**
```
md5sum $(cat logs/nj2_freeze_2026-11-14/j2_md5_files.txt) > logs/nj2_freeze_2026-11-14/j2_expected.md5
NJ_DOMAIN=nj2 EXPECT_MD5=logs/nj2_freeze_2026-11-14/j2_expected.md5 sbatch logs/nj2_freeze_2026-11-14/j2_freeze_nj2.slurm
```
(`j2_md5_files.txt` lists every file the chain reads: all `nj_sfincs/*.py`, `run_experiments.py`, the scripts it
calls, the ring / line / cut / refinement / weir / pool files, the catalog.) After GATE 1's registration, re-write
the md5 file and resubmit the same line. **Register (GATE 1):** `premier.EXPECTED["nj2"]` = the line in
`fingerprint_nj2.txt`; `domain.py` nj2 `building=False`; `n_waterlevel_support` = the `[base-bnd] N` in
`base_support_nj2.txt` — the BASE `noaa_sandy_nj` count (v4: 3), NOT step 4's NACCS count (that goes to
`experiments._NJ2_NACCS_SUPPORT`). The cut-arm brackets must already be tight: step 0 refuses otherwise.

**Waits for:** the refinement decided + the cut-arm brackets from the probe (step 0 now REFUSES without them), a Fable audit of this packet (the J2
script, the Domain block, the two carve builders), and the user's go.

## 6. J3 — the 2.0 design gate (DRAFT, not submitted): `j3_gate_nj2.slurm`

As v4's first runs (coordinator 11-14): waves-off Sandy on **nj2_bed2012**, rain off, +0 / +2 / +3 m on the
boundary, one job (`main`, emeraldrapids, 64 c, 200 G, 16 h, requeue; resumable), arms registered in
`EXPERIMENTS_BY_DOMAIN["nj2_bed2012"]` (`experiments.py`; block = `experiments_nj2_block.py`), in run order:

| arm | weirs / drainage | role |
|---|---|---|
| `p4-nowaves+rain-off+slr-0m` (added 11-14, user) | 1.1.0's premier weirs | the SMOKE run + the CLEAN +0 baseline every read compares against |
| `p4-nowaves+rain-off+slr-2m`, `…-3m` | 1.1.0's premier weirs | leak hunt: the Hudson / Hell Gate edges and the ring (`--compare` the clean +0: the sea level alone) |
| `p4-nowaves+rain-off+slr-0m+struct-cohansey-checkvalve+weir-dikes-levees` | the edges agent's fixed dikes / levees set (Chester redraw) on 1.1.0's weirs + the Cohansey Bacons Neck check valve (`data/nj2_design/structures/`) | a PAIRED comparison against the clean +0 (same forcing): every difference is the dike set + the check valve |

Physics = 1.1.0's `p4-nowaves` (NACCS-blend wind, cnb, moved inflows) with `rain=False`, `sea_level_offset_m`,
`subgrid_from="_subgrid_nj2_2012"`, NACCS from `naccs_sandy_nj2` with its support count DECLARED in
`experiments._NJ2_NACCS_SUPPORT` (None until J2 step 4 prints it; staging and J3 refuse while None).
Read: `scripts/overflow_check.py <run> --map --compare <clean +0>` for +2, +3 and the dike set (wet outflow edges,
wet land walls, margins) + premier audit (output WHOLE; captured, then grepped — no SIGPIPE under pipefail) +
weir u/v + `restart_history`. Each arm's flux cross-sections (`hudson_cut`, `hell_gate_cut`, `narrows`, `kvk`,
+ `barrier` / `throat`) are in `sfincs_his.nc` `crosssection_discharge`.

**The connected start is weir-aware (11-14).** `sea_level.write_connected_ini` now closes every link the ENGINE
puts a weir on (float32 snap rule, `weir_uv_crests`; it reproduces 819 on 1.1.0's premier run dir) whose crest is
at or above the start level, so the Elizabeth / Rahway levees, Keansburg and the dike set no longer start FULL
behind their crests at +2 / +3 m and get read as leaks. On 1.1.0's template with its premier weirs that keeps
4,831 cells dry at +2 m and 6,267 at +3 m that the sill-only rule filled. The sidecar
(`sfincs_ini_sealevel.json`) records `weir_uv_points`, `weir_uv_at_or_above_level`, `cells_kept_dry_by_weirs`.
Without a weir file the start is byte-identical to before. ⚠️ A `sea_level_offset_m` arm's `inifile` REPLACES the
template's Overpeck pool start (`sfincs_ini_regional.bin`) — true of all four arms, +0 included.

**Expect wet edges near Hell Gate at +3 m — read them before calling them a leak.** The ring there was walked
against 6.44 m (the Battery's Sandy peak + 3 m), but the forced level AT the cut is NACCS's ~3.60 m + 3 = ~6.60 m,
and the declared wall `wall_hellgate_east` holds 2.02 m ground beside it. Water on the ring cells within a few
hundred metres of the cut at +3 m is the forced crest exceeding the walk level by ~0.16 m, not a path out. **2.0.0 is final only after the gate reads clean;
a leak is a mask change through `setup_boundary_depth.py` (a new sha), not a new mesh.**

**Compute:** waves-off 72 h Sandy on 1.1.0's mesh with the production engine = 5,705 s at 64 threads
(`bed-v12a+p4-nowaves`, hal0384). nj2 is +2.5 % faces; +2 / +3 m wet more ground (assume ×1.2 / ×1.4): **~1.7 +
2.0 + 2.3 + 1.7 h solve + ~1 h staging + ~25 min reads ≈ 9 h** (the 4th run adds ~1.7 h solve + ~15 min staging);
limit 16 h (~1.7×). Disk: net +~55 G (four runs' map / his ~8–11 G each; staging copies deduped), peak +~95 G.

**Submit (after GATE 2 and the support count):**
```
md5sum $(cat logs/nj2_freeze_2026-11-14/j3_md5_files.txt) > logs/nj2_freeze_2026-11-14/j3_expected.md5
NJ_DOMAIN=nj2_bed2012 EXPECT_MD5=logs/nj2_freeze_2026-11-14/j3_expected.md5 sbatch logs/nj2_freeze_2026-11-14/j3_gate_nj2.slurm
```

## Where it stands

**J1 (63918506) — FAILED, superseded by J1b.** Its coarse bed was built and checked, but both nj2-ring probes
failed the domain invariants (sea arms 0 cells, 301,597 cells active inside the declared sea). Cause: NOT the ring or
the sea closure, but `model._inactive_components`. The quadtree grid is the ring's minimum rotated rectangle (here
v4's exact lattice: same x0 / y0 / rotation, 25 rows shorter). nj2's ring tops out on the 5.2 km FLAT Hackensack
New Milford head-of-tide cut, so 217 top-row faces lie inside the ring and split the outside of the ring into a west
(PA / NJ land) and an east (NY + the sea) component. The hole fill treated only the LARGEST inactive component (the
west) as exterior and re-activated the east one, sea included (408,637 cells). v4 escaped by one face (its top
was a single vertex). Fix (11-14): exterior = the largest component plus every component that reaches outside the
region; a hole lies wholly inside the ring. It only ever fills less than before. Tests:
`tests/test_inactive_components.py`. No ring vertex, sea closure or domain field moved for this.

**J1b (63918563, `j1b_composite_probe.slurm`, 28 min, hal0385) — CLEAN.** Composite coarse bed (§3), refinement
with the new-ground narrow channels (§2), three nj2 probes, all "domain invariants OK" (the job now FAILS on any probe
exception). Read-outs: `j1b_probe_summary.txt`, `j1b_compare.txt`, `j1b_probe_*.txt`; npz under
`/scratch/tpj8/nj2_refinement_probe/nj2_j1b/`.

| variant | faces | vs v4 / 1.1.0 (4,881,654) | active | min dt (estimate), where |
|---|---|---|---|---|
| `c0_v4only` (control: v4's recipe on the nj2 ring) | 4,899,645 | +17,991 (+0.37 %) | 4,018,963 | 0.684 s, the Narrows (−33 m, 25 m `narrows_cut`) |
| **`f1_final` (2.0.0)** | **5,181,372** | **+299,718 (+6.14 %)** | 4,300,646 | **0.830 s, Cape May Inlet jetty channel** (−74.864, 38.936; −22.1 m, 25 m) |
| `f2_noext` (2.0.0 without the new-ground narrow channels) | 5,179,788 | +298,134 | 4,299,077 | 0.830 s, same |

- J1's `n1_final` (2.0.0 before the narrow channels, J1's warp bed): 5,179,779. The new-ground narrow channels add
  **+1,584 faces** (+1,569 active; 2,048 new 25 m faces, 528 coarser ones replaced): Gowanus ~476, the Newtown Creek
  system (Newtown / English Kills / East Branch / Dutch Kills / Maspeth) ~1,170 (incl. the Long Island City spot), Lewes canal ~310, the Jersey City creek
  and the 2–5-sample spots ~90 (25 m faces gained). They do NOT set the time step (the limiter is unchanged).
- Bands (+300 m, vs the control): `newark_meadowlands` +245,705, `hudson_waterfront` +35,890 (the real nj2 number;
  memo estimate ~64 k for the 25 m NJ band), `capemay_inlets` +9,936. Runtime estimate ~2.37 h for the 72 h waves-on
  premier on 64 threads (×0.943 of 1.1.0's; a guess, `summarise.py`).
- **Old-ground identity vs v4's frozen mesh** (face centre + level, common grid): control 4,841,627 of 4,851,978 v4
  faces identical; every difference but **35** lies within 1 km of ground that changed on purpose (new ground, the
  A+ river cuts; for 2.0.0 also the new bands and `narrows_cut`). The 35 are two spots on Delaware River tributaries
  near Chester PA (−75.347, 39.825; −75.300, 39.749), 17 km from any change, under tiny abutting `narrow_channels`
  pieces that are geometrically v4's but in a different row order in the file (the builder dissolves by name and
  re-explodes). Not chased; harmless.
- **Arm census** (identical in all three variants): `delaware_mouth` 606, `ocean` 3,372, `lower_bay_entrance` 360,
  `rockaway_inlet` 69, `cd_canal` 5 — **v4's exact counts, inside v4's brackets** — `hudson` 28, `hell_gate` 10;
  mask 2 outside every arm 0; `wall_e88` / `wall_hellgate_east` boxes hold no outflow cell. Brackets set in
  `domain.py`: `hudson` [22, 36], `hell_gate` [7, 14] (v4's small-arm practice).

