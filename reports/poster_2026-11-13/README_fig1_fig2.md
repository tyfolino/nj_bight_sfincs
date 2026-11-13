# Poster figures 1 and 2: sources of every number (2026-11-12)

Model **1.1.0** = arm `p4-premier+weir-elizabeth-rahway` on domain `v4_refreeze_swz_v11`
(`sha(z,mask)=4bc97aae885f0aa4`, run job 63617802; `docs/MODEL.md`).

| file | made by | reads |
|---|---|---|
| `fig1_model.{png,pdf}` | `fig1_model.py` (plot only) | `fig1_data.npz`, `fig1_inflows.csv`, `fig1_gauges.csv`, `fig1_weirs.csv` (`fig1_prep.py`, run on holder 63849505), `hwm_per_mark_v110_native.csv`, `data/v4_design/waterlevel_line_v4.csv`, Natural Earth 10 m land / states (cartopy cache) |
| `fig2_hwm.{png,pdf}` | `fig2_hwm.py` (plot only) | `hwm_per_mark_v110_native.csv`, Natural Earth |
| `hwm_per_mark_v110_native.csv` | `hwm_per_mark.py` (holder 63849505, 4 cores / 16 G) | the native floodmap `/scratch/tpj8/floodmap_fix_2026-11-12/v4_refreeze_swz_v11/p4-premier+weir-elizabeth-rahway/floodmap_hmax_native.tif`, the run's `subgrid/dep_subgrid_merged.tif`, the 1.x mark file |

## Figure 2: the HWM numbers

**Estimator: median of the modelled water level over flooded pixels within 50 m of the mark**
(`hwm_metrics`, the `_scored` keys: q <= 2, a dry mark scores at the lowest ground in the window;
0 marks dry). Floodmap: **native 3.125 m** (the 11-12 re-score, `logs/floodmap_fix_2026-11-12/`,
job 63843110 step R). Mark file `data/validation_v4/sandy_hwms_v4_1x.geojson` (206 marks, 27 outside the
region, 119 scored).

| plotted | value | re-score row (`logs/floodmap_fix_2026-11-12/rows/v4_refreeze_swz_v11__p4-premier+weir-elizabeth-rahway.csv`) |
|---|---|---|
| n | 119 | `hwm_n_scored` 119, `hwm_n_dry_scored` 0 |
| RMSE | 0.35 m (0.3484) | `hwm_rmse_scored_m` 0.3484480319487689 |
| bias | −0.07 m (−0.0674) | `hwm_bias_scored_m` −0.06739936785738 |
| within ±0.5 m | 93 % (0.9328) | `hwm_within0.5_scored` 0.93277 |
| footnote: without the 5 lake-outlet-blocked marks | RMSE 0.24 m, n 114 | `hwm_rmse_scored_excl_lake_blocked_m` 0.23992, ids 6121 / 6122 / 6124 / 6129 / 6130 |

**Per-mark values.** The re-score wrote only the pooled row, not per-mark values, and a full
`load_floodmap` would de-rotate the 4.8 G-pixel map (~130 GiB). `hwm_per_mark.py` instead
de-rotates only a 50 m window per mark, onto the same north-up pixels rioxarray's full reproject
makes (its own `_make_dst_affine`, nearest), and applies `hwm_metrics`'s rule. **Self-check: n,
RMSE, bias and within-0.5 match the re-score row to every printed digit**
(0.3484480319487689 / −0.06739936785738004 / 0.93277 / 119).

**Regions** (colour + marker shape) group the scorer's basins (`Domain.hwm_rules`) into six,
south to north; counts in the legend. One override: mark **6130** is Wreck Pond (Spring Lake), labelled
`barnegat_bay` by the v1 basin box (FINDINGS says so); the figure puts it in "North Jersey Shore"
by latitude (> 40.1° N). The scorer's own per-basin keys are unchanged.

Panel b colours each mark by model − observed, clipped at ±0.6 m (the colour bar has extend
arrows; 6 marks lie beyond −0.6, 1 beyond +0.6).

## Figure 1: the side panel and the map

| text | value | source |
|---|---|---|
| active cells | 3.97 M (3,965,303) | `fig1_prep.py` printout: `mask` > 0 in the run's `sfincs.nc` (= MODEL.md §2) |
| cell sizes | 25 / 50 / 100 / 200 m (active: 1,419,799 / 2,244,354 / 251,206 / 49,944) | `level` 4..1, base `dx` 200 m |
| flood-map ground | 3.125 m | `logs/floodmap_fix_2026-11-12/README.md` |
| storm tide | NACCS Sandy (storm 001), 241 support points at the drawn line | MODEL.md "Forcing" |
| waves | SnapWave + wavemaker (IG in the water), NOAA CORA SWAN boundary | MODEL.md |
| wind / pressure | NACCS save-point wind blended into ERA5; pressure ERA5 | MODEL.md |
| rain | NOAA AORC v1.1 hourly, curve-number infiltration | MODEL.md |
| rivers | 61 inflows, USGS daily discharge | `sfincs_netsrcdisfile.nc` (61 stations) |
| buildings | NJDEP footprints (NJ only) | MODEL.md |
| levees, dams | Keansburg system, Elizabeth / Rahway (USACE NLD crests), Pews gap, Overpeck bypass sill; 24 lines in `sfincs.weir` | run dir |
| gauges | 48 obs points (`sfincs.obs`), all with an observed record in the metric row | run dir |
| HWMs | 119 scored | as Fig. 2 |

Map: active faces binned to a ~100 m lon/lat grid showing the finest cell size present in each
bin (a picture of the mesh, not the mesh). Orange = the drawn forced line
`data/v4_design/waterlevel_line_v4.csv` plus the forced faces (`mask` 2), which also cover the
Narrows / Kill van Kull boxes.

## Unsure / worth a look

- **Gauges**: all 48 obs points are drawn. The Narrows pair (`sss_narrows_si` / `_bkln`) sit
  at the forced boundary, so they are forcing inputs, not validation; the figure does not set them
  apart. "Checked against … 48 tide gauges" is therefore generous; no gauge hydrograph panel was
  made.
- FEMA MOTF extent is named in "Checked against" but not drawn (native re-score: CSI 0.802,
  POD 0.868, FAR 0.086, same row).
- Region grouping and the 6130 override are poster choices, not scorer facts.

## 11-12 trims (user)
- Fig 1 is map-only (`SIDE = False` in `fig1_model.py`; set True to bring the driver panel back). The poster text describes the model.
- Fig 2 is the scatter alone (the residual map read as worse than it is). Caption to paste on the poster (the estimator must travel with the numbers, CLAUDE.md §6):

> Model 1.1.0 vs USGS high-water marks from Hurricane Sandy (quality excellent/good, inside the model domain, n = 119). Model value = median water level of flooded ground within 50 m of each mark, on the 3.125 m flood map. The few large misses are marks behind coastal lakes (Deal Lake, Wreck Pond) whose outlets the model's ground holds shut; without those five, RMSE 0.24 m (n = 114).

## Poster v3 (2026-11-13): combined Figure 1

`fig1_model_hwm.py` → `fig1_model_hwm.{png,pdf}`: the fig1 map (widened west to 76.5° W so the inset sits
on empty PA land) with the fig2 scatter as inset (b), all 119 scored marks in one colour (the map's pink; the
six-region colouring of `fig2_hwm.png` is dropped to fit). Same inputs as the two scripts (cached, plotting only);
its printout reproduces n 119, RMSE 0.3484, bias −0.0674, within-0.5 0.9328. Sized to print 8.8 in wide;
legend 17 pt. On the v3 poster it is Fig 1; the FEMA extent is Fig 2 and the power-asset map Fig 3.

## Poster v4 (2026-11-13)

- `fig1_model_fema.py` → `fig1_model_fema.{png,pdf}` (v4 Fig 1): (a) the model map (fig1 inputs, warped to UTM 18N)
  beside (b) Model 1.1.0 **rain on** vs FEMA MOTF from the cached class raster
  `/scratch/tpj8/poster_2026-11-13/fig3/v4_refreeze_swz_v11__p4-premier+weir-elizabeth-rahway__motf_classes.tif`,
  same extent; insets A 0.70 / B 0.87 / C 0.69 (v5: C = Atlantic City, 0.77); CSI 0.801964 / POD 0.867566 / FAR 0.086164 = the 11-12 row (self-check printed).
  Drawn at print size (18.5 × 8.3 in).
- `fig2_hwm.py`: tick 17 pt, labels 19 pt, legend 16 pt (printed ~7 in wide in the Methods column). Numbers unchanged.
- `fig3_power_compact.py` → `fig3_power_compact.{png,pdf}` (v4 Fig 3): fig4_power.py's 2026 panel without the
  Newark Bay inset; counts today's ground (2012 ground): 52 (60) flood, 130 (122) dry, 71 (71) not computed; 10 rings.
- v8: `fig3_wet_layer.py` (block-wise, through the rotated affine, `simulated_mask`, GDAL_CACHEMAX 512 → 7.4 GB peak)
  makes the 15 m wet/dry/water layer behind Fig 3 on Fig 1b's rules; logs `logs/fig3_wet15_{2012,2026}.log`.
  2012-ground self-check vs Fig 1b: 1,307.7 vs 1,314.6 km² model-wet in the scored NJ area, 99.93 % of cells agree.
  2026 ground: 1,837 km² wet on all model land (2012 ground: 1,923).
