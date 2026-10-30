# scripts/ — index

One row per script, grouped by what you would be looking for. `tests/test_repo_hygiene.py`
keeps this list and the directory in step: add a row when you add a script, delete the row
when you retire one (convention: "retired <date>, in git history" wherever it was cited).

The directory stays FLAT on purpose: 50 scripts find the repo root with `parents[1]`, tests
load scripts by path, and `hpc/sfincs_run.slurm` calls two of them at run time. A subfolder
would silently point those at the wrong place.

**Status:**
- **live** — part of the current workflow.
- **provenance** — built data that is on disk; re-run only to rebuild that data.
- **frozen** — serves a frozen or archived domain (v1_monmouth, v1_5_raritan, v2_barnegat).

Every script reads `NJ_DOMAIN` unless its row names a domain. Run from the repo root with
`PYTHONPATH=$PWD`, and on a compute node for anything heavier than a quick read.

## Run, stage, operate

| script | what it does | status |
|---|---|---|
| `campaign_check.py` | ⭐ The morning check-in, READ-ONLY: queue + start estimates, every pending job's EXPECT_MD5 checked now, finished jobs (non-COMPLETED / `halk` flagged), maintenance overlap, home quota; `--guarded` = JSON of files queued jobs will check (feeds `.claude/hooks/guard.py`) | live |
| `accept_domain.py` | One read-only command: is this domain fit to run? | live |
| `freeze_mesh.py` | Build the static mesh once and freeze it (via `hpc/freeze_mesh.slurm`) | live |
| `probe_mesh_size.py` | Cell counts per size before paying for the subgrid | live |
| `rebuild_subgrid.py` | Rebuild only the subgrid on a frozen mesh; `--overlay` for burn rasters (CLAUDE.md §5; `--overlay <key>:min` = lower-only, `min(bed, overlay)`, never raises — order kept, later wins), `--manning-overlay` paints a Manning-n raster over the NLCD reclass the same way | live |
| `fix_meteo_grid_origin.py` | Rewrite a template's / staged dir's `netamuv`/`netamp`/`netampr` x, y to the engine's corner convention (centre − signed step/2; data untouched, idempotent); `--check` read-only, `--era5-bilinear` re-samples wind + pressure from native ERA5 (2026-10-06, `nj_sfincs/meteo_grid.py`) | live |
| `build_wind_naccs_blend.py` | NACCS ADCIRC save-point wind + pressure (Delaunay on u, v, p; long / land triangles dropped) blended into ERA5 bilinear over a 15 km taper, on a 500 m UTM grid covering every active + SnapWave face; writes `sfincs_netamuv.nc` / `sfincs_netamp.nc` with the engine corner convention + marker to `data/wind_v4/naccs_blend/` (`--extra-dir` adds CHS save points; 2026-10-06, `nj_sfincs/meteo_blend.py`, `logs/wind_naccs_blend_2026-10-06/`) | live |
| `setup_boundary_depth.py` | Stage a mask-variant domain (boundary depth, trimmed ring) from its frozen mesh | live |
| `setup_face_z.py` | Stage a face-z-variant domain: mesh `z` = a subgrid bed's mean ground, so SnapWave sees that bed (FINDINGS §63) | live |
| `build_modern_land.py` | The modern land + beach overlay for a 2026 bed: newest survey wins, and land lidar is refused over today's water | live |
| `restage_mask_repair.py` | Stage a mask repair from the frozen mesh and show the diff | live |
| `sync_obs_points.py` | Rewrite `sfincs.obs` from the registry without a rebuild | live |
| `sfincs_restart.py` | Resume / stitch a preempted solve (called by `hpc/sfincs_run.slurm`) | live |
| `record_engine.py` | Stamp a run dir with the engine that solved it (called by `hpc/sfincs_run.slurm`) | live |
| `engine_gate.py` | Cut a finished run to a short window, run it on a binary, compare fields | live |
| `retire_arm.py` | Retire a solved arm: keep its record, delete its bulk, manifest first | live |
| `dedupe_experiment_inputs.py` | Hard-link identical inputs within a domain | live |
| `dedupe_home.py` | Hard-link identical large files across the four data roots | live |
| `desktop_pull_backup.sh` | Run on the desktop: rsync the irreplaceable outputs off Amarel | live |
| `ring_to_geojson.py` | Region GeoJSON from the named-vertex ring CSV | live |
| `export_share_floodmap.py` | Share-ready max-depth GeoTIFF for a collaborator | live |
| `build_gallery.py` | Run-gallery figures (`nj_sfincs/gallery.py`) for finished arms, one subprocess per arm, serially — for arms validated before the `run_experiments.py` hook (which draws them after every validate; `--no-gallery` skips it) or to re-draw (`--only <keys>`); ~17 G peak per v4 arm, compute node | live |
| `publish_gallery.py` | Collect every domain's arm galleries + `metrics.csv` into the static GitHub Pages site (default `~/sandy_flood_site` = GitHub `tyfolino/sandy-flood-model`, its own repo, never committed here): per-domain sortable arm table with flag badges, a page per arm, a two-arm compare page; PNGs only | live |

## Score and read results

| script | what it does | status |
|---|---|---|
| `paired_hwm_bootstrap.py` | Paired HWM comparison of two arms; `--bbox` zone and `--by-basin` groups | live |
| `v4_first_results.py` | The first waves-on v4 read in one command: setup, scores, paired marks (incl. v4 vs v3), gauge/HWM/zsmax figures, summary skeleton; `submit --preset refreeze` | live |
| `overflow_check.py` | Where the peak water reaches the model edge; `--compare` for the SLR ladder | live |
| `source_proximity.py` | Which marks and gauges sit close enough to a river inflow to read it | live |
| `lake_outlet_blocked.py` | Which marks sit in a basin whose outlet the model holds shut above the local sea peak (`lake_outlet_blocked`; light, no floodmap); `--marks` prints the headline with and without | live |
| `relocate_coarse_inflows.py` | Flag inflows piling up on a coarse face; move them down the creek (screen / write / apply) | live |
| `compare_usgs_transects.py` | Model beach runup level vs USGS Sandy transects (TWL, dune crest, sandline washover) — the read where IG shows | live (restored 2026-10-01) |
| `stockdon_envelope.py` | Stockdon (2006) runup envelope on a still-water run (diagnostic) | live |
| `verify_port.py` | The port gate: the scorer reproduces the archive bit for bit (v1_monmouth) | frozen |

## Waves

| script | what it does | status |
|---|---|---|
| `snapwave_cost.py` | Per-call SnapWave cost from `sfincs.log`, overflowed `******` calls imputed | live |
| `snapwave_parameters.py` | Every SnapWave parameter: ours, the engine default, the meaning (writes `docs/snapwave_parameters.md`) | live |
| `snapwave_direction_check.py` | Did SnapWave launch the imposed waves and reach the shelf? | live |
| `snapwave_bay_census.py` | Per map hour: bay wind-sea, spike cells, IG ratio, CORA in the bay | live |
| `wave_boundary_ring.py` | Dead-ring census on a SnapWave boundary + setup transects | live |
| `wave_shelf_reference.py` | Share of CORA's wave height a SnapWave arm delivers to the −9 m shelf | live |
| `check_snapwave_domain.py` | Preflight a stepped SnapWave boundary on the frozen mesh | live |
| `make_snapwave_reproducer.py` | Plane-beach toy model (the §43 bug reproducer; wavemaker cases) | live |
| `build_wavemaker_line.py` | The wavemaker line: the "5 m at high tide" contour, smoothed | live |
| `build_cora_waves.py` | CORA SWAN wave boundary for the SnapWave support points | provenance |

## Check and audit (read-only)

| script | what it does | status |
|---|---|---|
| `audit_region_v4.py` | Audit a v4 region ring against what the mask builder will do | live |
| `audit_ocean_line_v4.py` | Audit v4's forced sea line against bed, ring and NACCS | live |
| `check_dem_clip.py` | A clipped DEM vs reference DEMs at random land points | live |
| `check_naccs_vs_sensors.py` | NACCS forcing product vs interior storm-tide sensors (forcing diagnostic) | live |
| `check_buildings_adequacy.py` | Adequacy checks before burning building footprints | live |
| `plot_waterlevel_boundary.py` | Map the built water-level boundary by arm (v1.5 layout) | frozen |

## Build model inputs

| script | what it does | status |
|---|---|---|
| `build_naccs_boundary.py` | NACCS / CHS water-level boundary forcing for Sandy | live |
| `build_merged_subgrid_dep.py` | One merged subgrid DEM covering every active face (the scoring bed) | live |
| `build_motf_valid_mask.py` | Where the MOTF sheet can adjudicate, on the MOTF grid | live |
| `build_coarse_bed.py` | A domain's 25 m coarse bed from its elevation list | live |
| `burn_building_footprints.py` | Building-block elevation tier for the subgrid | live |
| `build_cn_nj.py` | Curve Number raster for infiltration; `--ksat` = the SSURGO ksat raster for `cnb` | live |
| `build_lake_fix_overlay.py` | lower-only coastal-lake bed overlay (10 ft lidar under the USACE 2010 lake fill; 10-15 audit) | live |
| `build_breach_overlay_v4.py` | lower-only breach bed overlays for the `bed-breach` arms: Wreck Pond a stated channel (0.0 / 1.65 m), Mantoloking the EAARL post-Sandy surface, in the user's polygons | live |
| `eurotop_overtopping.py` | EurOtop (2018) mean wave-overtopping q over a front, from a finished run's own toe Hm0 / Tp / zs (segments CSV + crest columns), scenario table (crest ±0.5, Hm0 ±20 %, pre crest, setup-free SWL, vertical wall) + Stockdon R2% check; writes a one-point discharge NetCDF for `Experiment.extra_discharge` (2026-10-17, Deal Lake, `logs/overtopping_2026-10-17/`) | live |
| `build_refinement_v4.py` | v4 quadtree refinement polygons from a readable recipe; diffs names vs v3 | live |
| `build_riverbeds_v4.py` | v4 river beds where no survey reaches, one carving raster per reach | live |
| `build_usace_unpave_v4.py` | CUDEM painted back where the 2010 USACE lidar paves deep water (3 boxes), an overlay tier | live |
| `build_usace_unpave_backbay_v4.py` | The same un-paving in 11 back-bay channel / basin boxes (Ocean City → Wildwood incl. Beach Creek, LBI, Atlantic City, Keansburg), a second overlay tier | live |
| `build_creek_bed_nj10ft_v4.py` | Lower-only ASSUMED tidal-creek beds (`:min`): the NJ 10 ft DEM's hydro-flat water fill (≈ USACE MLW) along named creeks where CUDEM holds the water surface — Sluice / Dennis + 51 NJ Delaware Bay shore creeks (2026-10-20) | live |
| `build_riverbed_sayreville_v4.py` | The Raritan's side channels and bank margins at Sayreville from the 2012 survey, NOS H05647 and ENC soundings (was 3DEP's water surface), an overlay tier | provenance |
| `build_littleegg_channel_v4.py` | Little Egg Inlet's flood channels + the NJIWW behind Holgate from NOS H12597 (2014) and eHydro IW_08 (2024): an OPTIONAL post-Sandy overlay tier | provenance |
| `build_riverbed_cohansey_v4.py` | The tidal Cohansey at a stated depth below MLLW (no measured bed), an overlay tier | live |
| `build_riverbeds_gmrt_v4.py` | The four A+ tidal rivers whose bed falls through to GMRT (Maurice, Mullica, Tuckahoe, Rancocas): soundings, else a stated depth below MLLW, one overlay VRT | live |
| `build_riverbeds_tidal_v4.py` | The tidal Christina, Big Timber Creek and St Jones (NOS soundings, else 1.2 m below MLLW), one overlay VRT; `--section shaped` = a measured parabolic-type section option for these, the GMRT reaches and the Cohansey; `evidence` / `conveyance` tables | live |
| `build_riverbeds_hierarchy_v4.py` | ONE bed-source hierarchy (eHydro → real CUDEM → chart/NOS → sloping river, shaped section) for 18 tidal reaches incl. the Cohansey / GMRT / tidal ones it REPLACES; fill test, provenance raster, domain-wide fill screen, premier-tier consistency report; one overlay VRT; opt-in survey checks on CUDEM (crowdsourced / NOS point sets, charted controlling depths) and `--version` (v4 frozen; Cohansey → `v4c`, 10-23) | provenance |
| `build_inland_water_v4.py` | v4 inland water: CUDEM's 0 m fill under lakes and rivers, channel roughness (`manning` step → `manning_water_v4.tif`, n = 0.02 on every NHD lake/river polygon in the A+ ring) | live |
| `build_river_table_v4.py` | v4 river-inflow decision table: gauge flow vs flow at the model edge | live |
| `build_normal_surface_v4.py` | v4 usual-surface rasters for "depth" maps (`nj_sfincs/normal_surface.py`): VDatum MHHW (m NAVD88, mhhw − tss, along-water fill up the tidal reaches + ≤ 2 km land extension) and the pools of non-tidal NHD lakes (3DEP / NJ 10 ft lidar water surface), the mapped-water mask (NHD river areas + lakes, for `normally_wet`); CO-OPS station check, lake table, coverage → `data/normal_surface_v4/` (2026-10-19) | live |
| `build_v3_coarse_bed.sh` | The v3 coarse bed as actually built (its tier order differs from `domain.py`) | provenance |
| `build_coned_sw_raritan.py` | CoNED topobathy tier for the SW Raritan box (in the frozen v1.5 bed) | provenance |

## Acquire data

| script | what it does | status |
|---|---|---|
| `download_usgs_sandy_discharge.py` | River discharge at USGS gauges; the per-domain source lists and area scaling | live |
| `download_usgs_sandy_tidal.py` | USGS tidal water levels for validation | live |
| `download_noaa_sandy_wl.py` | NOAA CO-OPS water levels (forcing anchors + validation) | live |
| `download_sandy_hwms.py` | USGS high-water marks | provenance |
| `download_sandy_motf_extent.py` | FEMA MOTF Sandy surge extent as a raster | provenance |
| `download_sandy_storm_tide_sensors.py` | USGS storm-tide sensor series | provenance |
| `download_aorc_sandy_precip.py` | AORC hourly precipitation | provenance |
| `download_3dep.py` | NJ statewide lidar DEM clip (and 3DEP) | provenance |
| `download_cudem.py` | CUDEM 1/9″ tiles + VRT | provenance |
| `download_cudem13.py` | CUDEM 1/3″ fill tier | provenance |
| `download_gmrt.py` | GMRT offshore bathymetry | provenance |
| `download_pre_sandy_topobathy.py` | USACE 2010 pre-Sandy topobathy | provenance |
| `download_ehydro_nj.py` | eHydro carving tier (imported by `download_ehydro_v4.py`) | provenance |
| `download_ehydro_shrewsbury.py` | eHydro 2015 Shrewsbury survey tier | provenance |
| `download_ehydro_v4.py` | eHydro surveys for the v4 rivers + a CUDEM check | provenance |
| `download_nos_hydro_v4.py` | NOS hydrographic surveys for the v4 rivers | provenance |
| `download_nlcd.py` | Annual NLCD 2012 land cover on its own grid | provenance |
| `download_building_footprints.py` | Building footprints, two sources | provenance |
| `download_era5_cds.py` | ERA5 10 m wind + pressure | provenance |
| `download_era5_overwater_vars.py` | ERA5 surface-layer fields for over-water wind | provenance |
| `download_era5_waves_cds.py` | ERA5 waves (inadmissible at the boundary, FINDINGS §21; still a catalog default) | provenance |
| `download_ndbc_sandy_waves.py` | NDBC buoy 44025 waves | provenance |
| `download_sandy_winds.py` | Observed 10 m wind for checking a gridded product | provenance |
| `naccs_h5_to_csv.py` | Convert H5-only NACCS save points to the CSV layout | provenance |
| `repack_naccs_zips.py` | Repack the CHS zips into per-product zips | provenance |
| `naccs_coverage_map.py` | Inventory which save points have ADCIRC / STWAVE | provenance |

## Figures

| script | what it does | status |
|---|---|---|
| `plot_v4_domain_figures.py` | v4 figures: the SnapWave domain, the MOTF extent as scored | live |
