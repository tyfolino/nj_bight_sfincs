# Bed audit check: `water_surface`

**Question:** where does the bed hold a WATER SURFACE instead of the bottom? (SCHEMA.md one level up.)

Two ways a water surface ends up in our beds:

1. **Lidar hydro-flattening.** A bare-earth lidar DEM is flattened to the water level on the day of the flight wherever
   the laser saw water (lakes, rivers, bays) and in the shadow under bridge decks. The modern bed paints that lidar
   over the 2012 stack wherever it reads ≥ −0.25 m (STATUS "Sweeps"), so a flattened creek at 1.6 m replaces a real
   creek bed. Topobathy (USACE NCMP / NAN, CZMIL) measures the bottom where the water is clear, but in turbid water
   and under decks it returns the surface or interpolates across the gap, with a few cm of noise.
2. **CUDEM's constant fills.** CUDEM holds non-tidal water as a flat ~0 m surface (fake pits under lakes) and
   backfills some rivers (FINDINGS §54).

## Sources

| source | what | where |
|---|---|---|
| **3DEP hydro-flattening breaklines** (USGS Lidar Base Specification deliverable: water-body polygons with the flattened water-surface Z; rivers carry a Z that falls downstream) | the authoritative "this pixel is a water surface" record for every USGS lidar project our beds use | public bucket `s3://prd-tnm/StagedProducts/Elevation/metadata/<project>/<work unit>/breaklines/` (https://prd-tnm.s3.amazonaws.com/ — no auth; rockyweb's copy rate-limits). Downloaded 2026-11-05 by `fetch_breaklines.py` (450 MB) into `/scratch/tpj8/nj_bight_sfincs_data/audit/water_surface/breaklines/`. Public domain (USGS). |
| NOAA VDatum MHHW + its source codes; NHD water mask; non-tidal lake pools | which water is tidal (VDatum region or along a tidal reach — NOT the ≤ 2 km land extension, source 20) and which lake is held at a pool (intended) | `data/normal_surface_v4/` (built 2026-10-19; its README) |
| 1.0.0's Sandy peak; power assets | context columns | `experiments/v4_refreeze_swz/p4-premier/sfincs_map.nc`; `data/power_infra/*_polygons.geojson` |

### Breakline coverage (all eight USGS projects behind our tiers have them)

| 3DEP project | our tier | breakline water polygons (lake / ocean / river) | Z units |
|---|---|---|---|
| NJ_New_Jersey_SANDY_LiDAR_15 (2014) | behind `nj_10ft_dem` / `dep3` (2012 bed) | 706 (one `PolygonZ` layer) | m |
| NJ_NW_New_Jersey_6_County_Lidar_2017_B17 | usgs_nw_nj_2017 | 1264 / – / 14 | ftUS |
| NJ_South_Jersey_Lidar_2018_B18 | usgs_south_nj_2019 | 813 / 894 / 21 | ftUS |
| NJ_South_Jersey_Lidar_2018_B18_FEMA | usgs_south_nj_fema_2019 | 454 / 605 / 11 | ftUS |
| NJ_NE6County_B23 | usgs_nj_ne6county_2024 | 710 / 12 / 22 | ftUS |
| DE_Statewide_B23 | usgs_de_statewide_2023 | 1785 / – / 13 | m |
| PA_17County_D24 | pa_17county_2024 | 2024 / – / 25 | m (UTM, no vertical CRS: assumed m; checked against the bed) |
| NY_SouthEast4County_A22 | usgs_ny_se4county_2022 | 1742 / – / 18 | m |

11,133 water polygons in all (cache: `/scratch/.../audit/water_surface/cache/breakline_water_32618.gpkg`; Z converted
to m NAVD88 per layer from the layer's CRS). **No breaklines** for the non-USGS tiers: USACE NCMP / NAN topobathy
(2010, 2017, 2020, 2022), Philadelphia 2022, NYC 2017, DVRPC 2015, CUDEM, GMRT — there the check falls back to the
signature below. ⭐ The same deliverables also carry **bridge breaklines** (lines along every bridge deck the vendor
removed: NJ NE6 ~21,000, NW 7,861, South NJ 1,578 + 666, DE 2,032, NY 10,102): a second, lidar-side list of crossings for
the `crossing_nbi` check.

## Rule

Sample the bed on a 3 m north-up lattice, 2.4 km tiles, every tile in the ring holding water (rotated beds read
through the inverse affine). A pixel is WET if NHD water, a breakline water polygon, a non-tidal lake pool, or tidal
(VDatum) with bed < MHHW + 0.3 m.

- **Tier A, EXACTLY flat:** range ≤ 5 mm over a 5 × 5 window (15 m). Measured beds (lidar ground, surveys, GMRT) are
  never that flat over 15 m; flattened water and constant fills are. A patch must also be mostly ONE value (≥ 50 % of
  its pixels within 2 mm of its median) unless a breakline confirms it, which drops smooth interpolated surfaces.
- **Tier B, NEAR-flat sill:** range ≤ 0.15 m over 3 × 3 (9 m) in tidal water, kept only with the SILL signature:
  deeper bed ≥ 1 m below on ≥ 2 separate sides, patch std ≤ 8 cm, ≤ 2 ha. HIGH only inside MAPPED water (NHD river /
  lake area or a breakline water polygon); outside it, a near-flat strip between creeks is most likely a marsh
  platform (low), a strip above MHHW a causeway (medium).
- **A water surface lies within the tidal range:** in tidal water, an unconfirmed flat more than 3 m below MHHW is
  not a water surface (the largest range in the domain is ~2.6 m, Trenton) — those are the constant blocks of coarse
  tiers (GMRT 50 m, CUDEM 1/3″) and are dropped (counted in the summary); channel depth is another check. This is the topobathy water-surface return /
  under-deck shadow fill (M181, M232, M271 carry cm of noise, so Tier A cannot see them).
- **Breakline-confirmed** = the patch overlaps a breakline polygon and its level sits inside the polygon's Z range
  ± 0.15 m.
- Patches ≥ 200 m² (Tier B ≥ 90 m²). The hydraulic signature is read on a 9 m and a 15 m ring.

### Classes and severity

| kind | meaning |
|---|---|
| `water_surface_as_bed` | a flattened water surface held as the bed |
| `near_flat_sill` | Tier B: a near-flat strip across a channel at a water level |
| `structure_over_water` | Tier B above MHHW + 0.3 m: a deck / pier / causeway strip, not water (→ crossing checks) |
| `cudem_flat_fill` | CUDEM's 0 m constant fill in tidal water |
| `cudem_fill_under_lake` | CUDEM's 0 m fill under a lake whose normal pool is higher: a fake pit (→ impoundment check) |
| `lake_surface_mismatch` | a lake surface > 0.3 m off its normal pool |
| `intended_pool` | a non-tidal lake at its pool — INTENDED, counted in the summary, not exported |

- **high:** in tidal water, a sill (deeper ≥ 1 m on ≥ 2 sides), or a surface at / above MHHW over ≥ 1000 m² (normal
  tides cannot enter it).
- **medium:** holds a tidal channel shallow (deeper ≥ 0.5 m on one side), or a breakline-confirmed water surface on a
  mapped tidal channel (the bottom is missing), or a ≥ 0.5 ha flat in the tidal range, or a CUDEM pit under a lake.
- **low:** everything else (small flats in marsh ponds, non-tidal water).

## Calibration (known cases)

On the two beds (`modern` = modern merged bed + v1.1 deck pixels as min; `v1_1b` = `_subgrid_v1_1` + `deck_fix_v4b` as
min, the stand-in until `_subgrid_v1_1b` exists — it does NOT carry `alloway_pool_v4`). Site points in
`candidates.csv` are rounded to ~100 m, so matches are read within 400 m.

| case | expected | modern | v1_1b |
|---|---|---|---|
| M537 Grays Ferry, flat −1.2 m over an 8.5 m channel | high | ✅ high, Tier A, breakline-confirmed (PA 17-county), sill, drop 5–6 m | ✅ high: the 2012 bed's own ~0 m fill there is a sill too (drop 6 m) — the 2012 bed is blocked as well |
| M232 Cape May harbour flats | flag | ✅ high near-flat sills (−0.73, −0.45 m) | (nothing flat in the 2012 bed) |
| M181 Cape May rail trestle | flag | ❌ not resolved (the strip next to it is outside mapped water → low, then out of the 400 m window) | ✅ high near-flat sill at −1.56 m, 30 m away |
| M271 Shark River at Ocean Ave | flag | ⚠️ medium: the river beside the deck, breakline-confirmed flat −1.14 m; the strip under the deck is narrower than 9 m | – |
| E3 / Alloway Lake arm | 2012: fake tidal arm; 2026: the real pool | ✅ not flagged (pool, intended) | ⚠️ CUDEM 0 m fill flagged LOW (the NHD outline is too thin for the pool raster; the impoundment check owns this; fixed in the real v1.1b by `alloway_pool_v4`) |
| E4 Silver Lake | 2012: CUDEM pit under the lake | – (its tidal creek below the dam: a breakline flat at −0.25 m, medium) | ✅ `cudem_fill_under_lake`, medium |
| E1, E2 | not a water-surface case | not flagged (E1 = road embankment over a culvert; E2 = a connectivity sill) → crossing checks | – |

Caught 6 of 8 cases where a water surface is the problem (M537 both beds, M232, M181 on 2012, E4, E3 as a fill);
missed M181 on the modern bed and the under-deck strip at M271 (sampling limit, below).

## Results (2026-11-05, both beds, 4,203 tiles, 7 min on 32 cores)

| bed | high | medium | low | breakline-confirmed | intended pools (not flagged) | dropped: below any water level (coarse-tier blocks) |
|---|---|---|---|---|---|---|
| `v1_1b` | 924 | 1,817 | 6,904 | 1,813 | 1,166 | 127,288 |
| `modern` | 1,471 | 3,705 | 6,500 | 5,117 | 2,158 | 127,077 |

The modern bed holds ~3× as many breakline-confirmed water surfaces as the 2012 bed (5,117 vs 1,813): the
2017–2024 lidar's flattened water replacing the 2012 stack, as the 11-04 sweep said. Of the high rows, ~250 per
bed are `structure_over_water` (deck / pier / causeway strips: hand to the crossing checks).

**Largest high findings** (area × drop; full list in `../../out/<bed>/water_surface.csv`):

1. **Raritan River mouth off Sayreville / South Amboy** (−74.320, 40.491; −74.315, 40.500), BOTH beds: a 0.82 km² +
   0.19 km² EXACTLY flat −1.36 / −1.66 m with deeper bed on up to 30 sides, NO breakline — a constant level, not a
   lidar water surface: most likely one of our stated-depth / surveyed constant beds (`riverbed_sayreville_v4`,
   `coned_sw_raritan`, the 1934 NOS reach in `riverbeds_v4`). Sandy peak 4.1 m; MCUA power plant 0.4 km.
2. **Arthur Kill at Sewaren / Woodbridge** (−74.253, 40.536 / 40.542 / 40.551), BOTH beds: flats at −0.79…−0.80 m
   matching the NE6 lidar's flattened river Z, with the channel 4–9 m below on 13–19 sides — a water surface in the
   federal channel's margin. The Arthur Kill is where the table-cliff noise is (FINDINGS part 4 (l)): check whether
   these flats are its "high land + sliver of channel" faces. Sewaren 7 0.75 km.
3. **Delaware off Paulsboro** (−75.261, 39.856), modern only: 0.16 km² breakline-confirmed (PA) flat −1.49 m, drop
   2.5 m on 9 sides — the 2023/24 lidar's water surface painted over the 2012 bed. Paulsboro Refinery plant 1.7 km.
4. **Lower Bay off Keansburg / Sandy Hook Bay** (−74.003, 40.479), modern only: 0.14 km² flat −1.13 m (NE6 "Oceans"
   breakline), deeper on 13 sides — bay water surface in the modern bed.
5. **Delaware at Trenton / Morrisville** (−74.800, 40.234), 2012 bed: 0.21 km² flat +2.16 m matching the PA river
   breakline, deeper on 44 sides — above the falls; check against `riverbeds_v4` (3DEP water surface minus 1.20 m).

⚠️ A known false-positive class: a NON-tidal pool reached by MHHW's along-river fill (source 21), e.g. the Schuylkill
above Fairmount Dam (−75.188, 39.969, +1.81 m, modern) reads as "tidal". The impoundment check's dam list should
veto those.

## Files

| file | what |
|---|---|
| `fetch_breaklines.py` | lists / downloads every breakline deliverable (`python -I fetch_breaklines.py [--download]`) |
| `check.py` | the check (SCHEMA CLI; `--box lon0 lat0 lon1 lat1` and `--limit` for tests) |
| `run_both.sh` | the one-shot run of both beds (`srun -p main --exclude=halk[0001-0159] -c 32 --mem=150G -t 3:00:00 bash run_both.sh`) |
| `../../out/<bed>/water_surface.csv` + `.summary.json` | the exceptions and counts |

## Limits

- 3 m sampling cannot resolve a sill narrower than ~9 m, or an under-deck strip shorter than the deck is wide.
- Flatness is a signature, not proof: a constant-value survey patch or a dredged flat would pass Tier A without a
  breakline. Every exception is a REVIEW item; the severity ranks the review, it does not decide the fix.
- PA's breakline Z has no vertical CRS in the file; metres are assumed (the lake levels match the bed).
