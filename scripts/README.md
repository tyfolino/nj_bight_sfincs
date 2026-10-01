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
| `accept_domain.py` | One read-only command: is this domain fit to run? | live |
| `freeze_mesh.py` | Build the static mesh once and freeze it (via `hpc/freeze_mesh.slurm`) | live |
| `probe_mesh_size.py` | Cell counts per size before paying for the subgrid | live |
| `rebuild_subgrid.py` | Rebuild only the subgrid on a frozen mesh; `--overlay` for burn rasters (CLAUDE.md §5) | live |
| `setup_boundary_depth.py` | Stage a boundary-depth domain from its `mesh_key` sibling | live |
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

## Score and read results

| script | what it does | status |
|---|---|---|
| `paired_hwm_bootstrap.py` | Paired HWM comparison of two arms; `--bbox` zone and `--by-basin` groups | live |
| `overflow_check.py` | Where the peak water reaches the model edge; `--compare` for the SLR ladder | live |
| `source_proximity.py` | Which marks and gauges sit close enough to a river inflow to read it | live |
| `compare_usgs_transects.py` | Model beach runup level vs USGS Sandy transects (TWL, dune crest, sandline washover) — the read where IG shows | live (restored 2026-10-01) |
| `stockdon_envelope.py` | Stockdon (2006) runup envelope on a still-water run (diagnostic) | live |
| `diagnose_bay_seiche.py` | Raritan Bay sub-hourly motion: coherent seiche or chatter (v1.5) | frozen |
| `make_flux_crosssections.py` | Two control lines partitioning inflow to the Shrewsbury / Navesink | frozen |
| `score_bracket.py` | Score the Manahawkin bracket (v2) | frozen |
| `score_v2_barnegat.py` | Score the archived v2_barnegat runs to a CSV | frozen |
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
| `validate_domain.py` | Prove a rebuilt domain before paying for a subgrid (v1) | frozen |
| `validate_region_v3.py` | Validate the hand-edited v3 region polygon | frozen |
| `sweep_cudem_flatfill.py` | Find phantom water: stack says water, CoNED says land (v1.5) | frozen |
| `audit_paved_channels.py` | Channels the top lidar paved over (v1.5 Workstream L) | frozen |

## Build model inputs

| script | what it does | status |
|---|---|---|
| `build_naccs_boundary.py` | NACCS / CHS water-level boundary forcing for Sandy | live |
| `build_merged_subgrid_dep.py` | One merged subgrid DEM covering every active face (the scoring bed) | live |
| `build_motf_valid_mask.py` | Where the MOTF sheet can adjudicate, on the MOTF grid | live |
| `build_coarse_bed.py` | A domain's 25 m coarse bed from its elevation list | live |
| `burn_building_footprints.py` | Building-block elevation tier for the subgrid | live |
| `build_cn_nj.py` | Curve Number raster for infiltration | live |
| `build_refinement_v4.py` | v4 quadtree refinement polygons from a readable recipe; diffs names vs v3 | live |
| `build_riverbeds_v4.py` | v4 river beds where no survey reaches, one carving raster per reach | live |
| `build_inland_water_v4.py` | v4 inland water: CUDEM's 0 m fill under lakes and rivers, channel roughness | live |
| `build_river_table_v4.py` | v4 river-inflow decision table: gauge flow vs flow at the model edge | live |
| `build_v3_coarse_bed.sh` | The v3 coarse bed as actually built (its tier order differs from `domain.py`) | provenance |
| `build_coned_sw_raritan.py` | CoNED topobathy tier for the SW Raritan box (in the frozen v1.5 bed) | provenance |
| `build_refinement_v1_5.py` | The v1.5 refinement recipe (kept by user decision 09-21) | frozen |

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
