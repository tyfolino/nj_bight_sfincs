# Flood depth AT EACH BUILDING (for Delft-FIAT) — `sandy_hmax_v4_refreeze_swz_v11_bed2012_bareground_buildings_EPSG32618.tif`

**Preliminary.** Built from the plain bare-ground depth map `sandy_hmax_v4_refreeze_swz_v11_bed2012_bareground_EPSG32618.tif` (read its
README, `sandy_hmax_v4_refreeze_swz_v11_bed2012_bareground_README.md`, for the model run, version, terrain year, CRS, scores and
caveats — all of it applies here) by `scripts/fiat_building_depth.py`.

## Why this file exists

The plain map measures depth from bare ground, but a building big enough to fill a whole
model cell still reads dry there even when the streets around it flood (the model has no
street-level water inside that cell). Here every building footprint gets the water of the
streets around it.

## The rule

- **Water level at a building** = the MEDIAN peak water level (m NAVD88) of the wet
  (depth >= 0.15 m) non-building pixels within 50 m of its footprint (16
  pixels: a square window, the same median / 50 m estimator our high-water-mark scoring
  uses).
- **Depth** = that level − the bare ground (m NAVD88) at the building's centroid.
- In the GeoTIFF, every pixel inside a footprint (and each centroid's own pixel) holds
  level − bare ground at that pixel where that is above 0.05 m, else NaN (dry). **Pixels
  outside footprints are copied unchanged** from the plain map
  (0 pixels differ there).
- Footprints: **njdep** (`/scratch/tpj8/nj_bight_sfincs_data/buildings/raw/njdep_building_footprints_nj.fgb`), 2,635,828 buildings with a
  centroid in the grid.

## Files

| file | what |
|---|---|
| `sandy_hmax_v4_refreeze_swz_v11_bed2012_bareground_buildings_EPSG32618.tif` | the plain map with footprints filled — sample it at each building's centroid |
| `sandy_hmax_v4_refreeze_swz_v11_bed2012_bareground_buildings_njdep.csv` | one row per building (below) |
| `sandy_hmax_v4_refreeze_swz_v11_bed2012_bareground_buildings_njdep.gpkg` | the same table as centroid POINTS (EPSG:32618), for GIS |

Columns: `building_id` (the source's id: NJDEP `objectid`, or the hybrid layer's row id
`fid`), `source`, `x_utm18n` / `y_utm18n` (centroid, EPSG:32618 m), `level_m_navd88`,
`bare_ground_centroid_m`, `bare_ground_footprint_median_m`, `depth_m` (level − ground at
the centroid; negative = the street water stayed below this building's ground),
`n_wet_pixels` (how many street pixels the median used), `flag`, and the depth at the
centroid in the plain and the filled GeoTIFF.

`flag`: **wet** (depth >= 0.05 m), **dry** (street water within 50 m, but below the
building's ground), **no_wet_neighbour** (no wet street pixel within 50 m: depth NaN).

## Counts

| | buildings |
|---|---|
| wet (depth >= 0.05 m) | 124,575 (of which >= 0.15 m: 112,187) |
| dry | 147,814 |
| no wet street pixel within 50 m | 2,363,439 |

Against the plain map at the centroid: 3,793 buildings went from blank to a
depth, 692 from a depth to blank, 14,562 changed by
more than 1 cm, 2,616,781 unchanged. Median depth of the wet buildings:
0.55 m.

## Buildings beside the water but dry

Of the buildings with at least 0.15 m of water somewhere on a ring just outside their footprint
(that depth measured from the ring's own ground), 121,206 get a depth here and 27,309 read **dry**:
they stand on higher ground (a pad, or a rise at the edge of the flood) and the median street water
around them peaked below their centroid ground (by 0.12 m in the middle case). Another 1,826 have no
wet street pixel within 50 m in this map. **12,556 of the dry buildings are within 0.10 m of being
wet**, so for damage counts a few-centimetre change in the water (or in first-floor height) moves
them; the rule uses the MEDIAN street level, not the highest. Diagnosis:
`logs/fiat_geotiffs_2026-11-13/README.md` ("Check (a) read").

Questions to Ty.
