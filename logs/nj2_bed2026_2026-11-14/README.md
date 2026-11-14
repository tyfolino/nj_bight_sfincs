# Model 2.0.0's 2026 bed on the nj2 mesh: code, inputs and the build job (2026-11-14)

**In plain words.** Model 2.0.0 is one new mesh (v4's ring plus the Hudson to 40.860 N and Hell Gate) with two beds:
2012 (Sandy's ground; another agent's job, `logs/nj2_freeze_2026-11-14/`) and an estimated 2026 ("today's") bed.
This directory gets the 2026 bed ready to build the moment the mesh and its 2012 bed exist. Nothing here needed the
mesh, and nothing was built on it. What is ready:

1. **`scripts/build_modern_land.py` takes `--bed` / `--out`.** It used to judge the modern lidar only against v4's
   bed. It can now judge it against nj2's 2012 bed and write somewhere new. With no flags it does exactly what it did
   before, byte for byte (tested).
2. **Today's buildings now cover the new Hudson strip.** The hybrid footprint layer (USA Structures, pre-2019
   polygons swapped for Microsoft's) was rebuilt for the nj2 ring, New Jersey only, with the power-asset guard the
   user asked for on 11-12 (not on solar sites: panels are not buildings, user 11-14). Hudson County's waterfront
   gains ~33,000 buildings (11.7 km² of roof).
3. **Two 2.0 carves for the 2026 bed** (user 11-14): the pile-supported piers (62 units, 35 ha) and the upper
   Gowanus Canal (assumed depth). The Gowanus file for the 2012 bed is built too.
4. **The recipe and one chained job** (`build_nj2_2026.slurm`, not submitted): about 2 hours on 32 cores.

## 1. `build_modern_land.py --bed / --out`

- `--bed PATH`: the current bed the surveys are judged against. Any GDAL raster works, rotated or not. The output
  extent is the bed's bounding box. Default: `BED`, v4's no-buildings refreeze bed, as before.
- `--out DIR`: where `modern_land_2026.tif`, `modern_land_2026_source.tif` and `vrt/` go. Default: `OUT`, 1.x's dir.
- The bed path now travels inside each block's job tuple. On Python 3.14 the process pool re-imports the module in
  every worker (forkserver), so a module global could not carry it.
- **Tests:** `tests/test_build_modern_land.py`, 4 tests, all pass (~3 s). They use a synthetic 2-source case with a
  rotated bed, and check four things:
  - the defaults are the module constants;
  - no flags gives the same bytes as `--bed BED --out <elsewhere>`;
  - a bed with water refuses the land lidar there, through a 2-worker pool;
  - a missing bed is refused.
- **Against the 11-13 code (HEAD c60be62):** `head_equivalence.py` → `head_equivalence.txt`. Both rasters and the
  source table are byte-identical.
- ⚠️ Since 11-12, `raw/nyc_topobathy_2017/` holds 21 tiles, not 16. Any re-run reads all 21, with or without the
  flags.
- ⚠️ The nj2 2012 bed carries the +10 m building burn. That does not change the output rasters: the burn sits only on
  ground ≥ 0 m, so a building pixel never reads as water. It does bias the per-source medians "on land" low.

## 2. Hybrid footprints for nj2 (`hybrid_footprints_nj2.py`, job 63918184, 4 min; `hybrid_nj2_summary.txt`)

**Area.** The nj2 ring plus a 500 m buffer, intersected with NJ. This is what round c's README asked for: edge faces
whose subgrid pixels reach past the ring see buildings too.

**NJ only** (user 11-04: buildings and developed n 0.04 stay NJ only).
- Both sources are NJ state files.
- A polygon is kept when its representative point lies within 250 m of the Census NJ state polygon AND inside no
  other state's polygon.
- Dropped: USA 4 NY + 2 far outside; MS 362 PA + 7 NY + 44 far outside.
- **Output check:** 0 kept polygons sit in NY, PA or DE. 619 sit on NJ waterfront (piers) that the 1:500k shoreline
  cuts off.

**The rule** is round c's, unchanged (roles 1–4), plus one new role:
- **role 5 `usa_asset_guard`**: a pre-2019 USA polygon the rule would swap is KEPT where it overlaps an NJ power
  asset and Microsoft release 2 covers less than half of that overlap.
- **The guard skips solar sites** (user 11-14: solar-panel arrays are NOT buildings). A plant whose OSM
  `plant:source` contains "solar" gets no guard; there the round c rule alone decides.
- **Two exceptions, by name** (user 11-14): CCMUA and Jersey City DWP. OSM tags them solar, but their real buildings
  keep the guard.
- In all, the guard skips 78 of the 195 assets in the area (677 solar plants in the asset file).

| role | n | km² |
|---|---|---|
| 1 usa_post2019 | 657,971 | 160.20 |
| 2 usa_pre2019_kept | 190,026 | 49.62 |
| 3 ms_swap | 330,845 | 87.51 |
| 4 usa_bigroof | 48 | 1.09 |
| 5 usa_asset_guard | 139 (37 assets) | 0.11 |
| **total** | **1,179,029** | **298.54** |

Earlier runs, superseded:

| run | job | rule | polygons | km² | guard |
|---|---|---|---|---|---|
| 1 | 63918118 | guarded everywhere | 1,178,993 | 298.55 | 161 polygons / 44 assets |
| 2 | 63918136 | solar skipped, no exceptions | 1,179,031 | 298.53 | 137 polygons / 35 assets |

**Where it differs from the v4 layer.**
- **Inside region_v4 × NJ:** 1,082,036 polygons vs v4's 1,093,129. nj2 drops the river reaches above the
  head-of-tide cuts (115 km² of region_v4), and adds the guard.
- **Outside region_v4:** 96,993 polygons, 28.0 km². Of that, the Hudson waterfront is **33,299 polygons, 11.7 km²**:

| town | new km² |
|---|---|
| Jersey City | 5.27 |
| Hoboken | 1.07 |
| Fort Lee | 0.95 |
| Bayonne | 0.92 |
| Cliffside Park | 0.60 |
| West New York | 0.57 |
| Union City | 0.55 |
| North Bergen | 0.54 |
| Edgewater | 0.48 |
| Weehawken | 0.46 |
| Guttenberg | 0.16 |

  The rest of the 28 km² is the 500 m margin along the inland edge of the ring.

**The guard does what was asked** (`hybrid_nj2_power_assets.csv`; building share by asset):

| asset | v4 hybrid | nj2 | USA alone |
|---|---|---|---|
| Wheelabrator Gloucester | 0.07 | 0.28 | 0.28 |
| Camden Cogeneration | 0.06 | 0.22 | 0.22 |
| CCMUA (exempt) | 0.66 | 1.00 | 1.00 |
| Jersey City DWP (exempt, new area) | — | 0.35 | — |
| MCUA | 0.19 | 0.28 | |
| Sayreville GS | 0.08 | 0.15 | |

- The new-area assets now carry buildings: Newport 0.15, Hoboken 0.09, South Waterfront 0.08.
- **Solar sites keep the plain rule.** Parlin Solar stays 0.00 and French's Landfill PV 0.00 (run 1's guard had
  brought back panel polygons: 0.14 / 0.06).
- **The two exempt plants keep the guard.**
  - CCMUA: 1.00 (NJDEP 0.89, USA 1.00; 0.66 without the guard).
  - Jersey City DWP: 0.35. ⚠️ That is lower than without the guard (0.62). The kept 1,947 m² pre-2019 USA roof then
    blocks the Microsoft polygons it half-covers. Worth one look at imagery.

**Output:** `/scratch/tpj8/nj_bight_sfincs_data/modern_2026/derived/round_c/footprints_hybrid_nj2.gpkg` (330 MB,
layer `footprints`). The v4 files were not touched. It is not rasterised here: the burn lattice comes from the nj2
merged bed (job step P5).

## 3. 2.0 carves for the 2026 bed (user 11-14: both IN)

- **Pile piers, `piers_v2_2026`** (`build_pier_carves.py`; `pier_carves.txt`, per unit in
  `…/v2/carves/piers_v2_2026.csv`).
  - Same depth rule as the 2012 agent's `build_piers_2012.py`: the median water bed (< −0.5 m) in a 5–40 m ring
    around each unit, on a 5 m grid, applied as `:min`.
  - The water bed is `ehydro_latest_2026` where it has data, else CUDEM. This is the 2026 twin of their
    "HD_HUD 2012, else CUDEM".
  - **Units: `carve_2026` (53) + 9 that the user's 11-12 eye check called `pile` and that have a deck in the 2026
    bed = 62** (35.9 ha). The eye check added no `fill` vetoes to the 53.
  - 60 units carved, 2 skipped (no water within 40 m; Red Hook, 326 m² and 8,386 m²).
  - Depth p10 / p50 / p90: −10.1 / −6.2 / −1.8 m.
  - **Edgewater:** w538964867 is carved. w538964866 has no 2026 bed value under it, so it has no deck in the bed and
    is not carved.
  - ⚠️ **To reconcile:** the 2012 builder uses `carve_2012` only, without the eye check (22 units; with it, 29). The
    beds should probably share the unit rule.
- **Upper Gowanus Canal, `gowanus_upper_v2_{2012,2026}`** (`build_gowanus_upper.py`; `gowanus_upper.txt`; ASSUMED).
  - **Depth:** the median of GC_01_GCK_20200512's last main-channel section, **−2.69 m NAVD88** (p10 −3.62, p90
    −1.87), carried flat from ~40.676 N to the Butler St head (40.6817).
  - **Canal outline:** the NYC 2017 lidar's flat water surface (p50 +0.20 m), < 0.6 m, the component that touches
    that section.
  - **Pixels painted:** only those the bed's own `carve_v2_<bed>` does not already hold.
    - 2012: 1.55 ha (the 2013 survey reaches further up).
    - 2026: 2.27 ha.
  - Apply `:min` after `carve_v2_<bed>`.
  - The 2012 job (`j2_freeze_nj2.slurm`) expects a key `gowanus_upper_v2`: point it at the `_2012` file (snippet
    below).
  - md5: 2012 `04b5828e…`, 2026 `e5dd87de…`, piers 2026 `16a59926…`.

## 4. The 2026 recipe for nj2, against `_subgrid_modern2026b`'s provenance

**Base tiers:** the nj2 2012 bed's. They are 1.1.0's 16 (`V4_ELEVATION_LIST`), the same as modern b's.

**Overlays, in paint order** (`OVERLAYS` in `build_nj2_2026.slurm`):

| slot | modern 2026b (v4) | nj2 2026 | why |
|---|---|---|---|
| 1–2 | `modern_land_paint_2026b`, `…lower_2026b:min` | **`modern_land_paint_nj2`, `modern_land_lower_nj2:min`** | re-made (P1 + P2) against the nj2 2012 bed. v4's raster already spans the new area, but it was judged against v4's bed, which has no Hudson water: land lidar would be taken over the river. It also has only 16 of 21 NYC tiles |
| 3–10 | `riverbeds_v4` … `ehydro_passaic_v4` (base survey repaint) | same 8 | same base list |
| 11 | `bed_buildings_v4_cap10` (NJDEP, 2012 roofs) | **`bed_buildings_hybrid_cap10_nj2`** | round c: today's footprints, burned at ground + 10 m on a no-buildings 2026 nj2 bed (P4 + P5) |
| 12–21 | `inland_water_bed_v4` … `riverbeds_hierarchy_v4e` | same 10 | |
| 22 | `bluetopo_newer_2026` (region_v4, ends 40.804 N) | **`bluetopo_newer_nj2`** | re-run (P3) inside the nj2 ring, against the nj2 modern land |
| 23 | `ehydro_latest_2026` | same | already spans the new area (to 41.01 N) |
| 24–28 | `lake_fix_v4:min` … `deck_fix_modern_b:min` | same 5 | |
| new | — | **`raritan_mouth_fix_v4:min`, `greategg_plug_fix_v4:min`** | the two v1.2a fixes marked BOTH beds (the other three are 2012-only) |
| new | — | **`carve_v2_2026:min`, `gowanus_upper_v2_2026:min`, `piers_v2_2026:min`** | 2.0's carves (Newtown / Wallabout / Gowanus / Bushwick; upper Gowanus; pile piers) |

**Not in the 2026 list:** `ehydro_hud_2012_v2` (2012 only), `deck_fix_v4b` / `ehydro_fill_v4` (2012 only, as in
modern b), and `gmrt_gap_fix_v4` / `nj36_deck_recut_v4` / `barnegat_flat_fix_v4` (2012 only by their own notes).

**Manning.**
- Modern b: base NLCD 2012 + `manning_developed_v4`, `manning_water_v4`, `manning_channel_v4e`.
- nj2 2026: base NLCD 2012 + **`manning_nlcd_2025_v4`** + **`manning_developed_2025_v4`** + `manning_water_v4` +
  `manning_channel_v4e`.
- `manning_nlcd_2025_v4` (round c) is the same hydromt reclass applied to NLCD 2025, painted first. It makes the
  base n 2025's everywhere without a builder flag or a domain edit.
- The alternative is to register the template domain with `landcover = nlcd_2025_v4`. That is the domain agent's
  call: then drop the first overlay.
- ⚠️ Assumption: overlay painting reproduces the base reclass's own regrid. Both are 30 m-pixel nearest reads, so
  this is expected but not tested.

**Curve number:** `cn_dataset = "cn_2025_v4"` on the `nj2_bed2026` domain (domain agent). It covers the nj2 bbox
(−76.34 … −72.86, 38.36 … 41.35).

### Round c and the known gaps: IN vs deferred

| item | | one-line reason |
|---|---|---|
| NLCD 2025 Manning (base + developed, NJ only) | **IN** | rasters built in round c; enter as overlays |
| NLCD 2025 curve number | **IN** (domain field) | `cn_2025_v4` built in round c; set on `nj2_bed2026` |
| hybrid footprints + burn | **IN** | nj2 layer built here; the burn runs in the job (P4/P5) |
| asset guard | **IN** | role 5 above; not on solar sites, except CCMUA + Jersey City DWP by name (user 11-14) |
| 39 + 9 big pre-2019 roofs (role 4) | **IN** | user 11-12 "keep" |
| pile-pier carve (Edgewater = pile) | **IN** | user 11-14; built |
| upper Gowanus (both beds) | **IN** | user 11-14; built (ASSUMED −2.69 m) |
| `raritan_mouth_fix_v4` / `greategg_plug_fix_v4` on the 2026 bed | **IN** | marked BOTH beds in the catalog |
| modern deck pass re-run on THIS bed | deferred | needs the built nj2 2026 bed. The v4 deck sweep has 1 way in the new area: re-run the sweep (job step C is the locator) and add a `deck_fix_nj2_2026:min` if it finds dams |
| M537 / M271 full carves | deferred | need a site polygon plus a depth decision. M537 −7.2 m (user 11-05), M271 to the eHydro channel. Both are partial in `deck_fix_modern_b`; ~1 h as one small `:min` raster before the build |
| Sedge Island #11 OPEN today | deferred | a quick 15 m look at modern b did not settle where "the mouth" is. Check it on the nj2 2026 bed with the user's coordinates (needs an eye check), and carve to the bay channel if still closed |
| bridge rule (S12) in the new area | deferred | the deck-sweep corridors stop at v4. The NYC 2017 bare earth has no decks over the East River / Hudson spans, so there is little to lose |
| sweep fixes 5 / 7 / 8 | deferred | after this build, as in round b |

## Catalog snippets (for the catalog owner; NOT applied)

```yaml
modern_land_paint_nj2:
  data_type: RasterDataset
  uri: elevation_modern_2026/nj2/modern_land_paint_nj2.tif
  driver: {name: rasterio, options: {}}
  metadata: {category: topography, crs: 32618, unit: m+NAVD88, source: >-
    2.0 2026 BED. modern_land_paint_2026b's rule (logs/modern_bed_b_2026-11-06/split_modern_land.py) on modern land
    judged against the nj2 2012 bed (scripts/build_modern_land.py --bed); logs/nj2_bed2026_2026-11-14/ P1-P2.}
modern_land_lower_nj2:
  data_type: RasterDataset
  uri: elevation_modern_2026/nj2/modern_land_lower_nj2.tif
  driver: {name: rasterio, options: {}}
  metadata: {category: topography, crs: 32618, unit: m+NAVD88, source: >-
    2.0 2026 BED. LOWER-ONLY half of the split (apply :min). logs/nj2_bed2026_2026-11-14/ P2.}
bluetopo_newer_nj2:
  data_type: RasterDataset
  uri: elevation_modern_2026/nj2/bluetopo_newer/bluetopo_newer_2026.vrt
  driver: {name: rasterio, options: {}}
  metadata: {category: topography, crs: 26918, unit: m+NAVD88, source: >-
    2.0 2026 BED. bluetopo_newer_2026's rule + MLLW fix inside the nj2 ring, not under the nj2 modern land.
    logs/nj2_bed2026_2026-11-14/build_bluetopo_newer_nj2.py (P3).}
bed_buildings_hybrid_cap10_nj2:
  data_type: RasterDataset
  uri: elevation_modern_2026/nj2/bed_buildings_hybrid_cap10_nj2.tif
  driver: {name: rasterio, options: {}}
  metadata: {category: topography, crs: 32618, unit: m+NAVD88, source: >-
    2.0 2026 BED. footprints_hybrid_nj2 (USA Structures 2025 + Microsoft release 2, NJ only, asset guard except
    on OSM solar plants other than CCMUA and Jersey City DWP; ODbL
    attribution on the public gallery) burned at the no-buildings nj2 2026 bed + 10 m, not where ground < 0 m.
    OVERLAY; replaces bed_buildings_v4_cap10 in the 2026 recipe. logs/nj2_bed2026_2026-11-14/ P4-P5.}
gowanus_upper_v2_2026:
  data_type: RasterDataset
  uri: elevation_nj2/v2/carves/gowanus_upper_v2_2026.tif
  driver: {name: rasterio, options: {}}
  metadata: {category: topography, crs: 32618, unit: m+NAVD88, source: >-
    2.0 2026 BED. ASSUMED upper Gowanus Canal carve (user 11-12 / 11-14): GC_01_GCK_20200512's last section median
    -2.69 m carried to the Butler St head, on cells carve_v2_2026 does not hold. Apply :min after carve_v2_2026.
    logs/nj2_bed2026_2026-11-14/build_gowanus_upper.py. md5 e5dd87de529fe968c0d61567ab0f178d}
gowanus_upper_v2:   # the 2012 bed's key as j2_freeze_nj2.slurm spells it
  data_type: RasterDataset
  uri: elevation_nj2/v2/carves/gowanus_upper_v2_2012.tif
  driver: {name: rasterio, options: {}}
  metadata: {category: topography, crs: 32618, unit: m+NAVD88, source: >-
    2.0 2012 BED. As gowanus_upper_v2_2026, on cells carve_v2_2012 does not hold (the 2013 survey reaches further).
    md5 04b5828ec36c0e290bced1cd7c11869b}
piers_v2_2026:
  data_type: RasterDataset
  uri: elevation_nj2/v2/carves/piers_v2_2026.tif
  driver: {name: rasterio, options: {}}
  metadata: {category: topography, crs: 32618, unit: m+NAVD88, source: >-
    2.0 2026 BED. Pile-supported pier carve (user 11-14): carve_2026 units + the 11-12 eye check's piles with a
    2026 deck (62 units), each to the median water bed (< -0.5 m) 5-40 m around it (ehydro_latest_2026 else CUDEM).
    Apply :min. logs/nj2_bed2026_2026-11-14/build_pier_carves.py. md5 16a59926221809f990b0f788176ce026}
manning_nlcd_2025_v4:
  data_type: RasterDataset
  uri: /scratch/tpj8/nj_bight_sfincs_data/modern_2026/derived/round_c/manning_nlcd_2025_v4.tif
  driver: {name: rasterio, options: {}}
  metadata: {category: roughness, unit: s m-1/3, source: >-
    MODERN BED. hydromt's NLCD_CONUS_mapping reclass of NLCD 2025 C1V2 on nlcd_2012_v4's grid (NaN = NoData).
    --manning-overlay FIRST = a 2025 base n. logs/modern_round_c_2026-11-12/build_manning_2025.py.}
```

Also needed (drafted in `logs/modern_round_c_2026-11-12/README.md`): `manning_developed_2025_v4`, `cn_2025_v4`
(and `nlcd_2025_v4` if the domain route is taken).

## The job: `build_nj2_2026.slurm` (DRAFT, not submitted)

- **Shape:** one `nonpre` job, 32 cores / 180 G, every step skip-if-done.
- **Steps:**
  - P1 modern land (~5 min)
  - P2 split (~7 min, 41 G)
  - P3 BlueTopo (~1 min)
  - P4 no-buildings bed (~30 min)
  - P5 burn (~5 min); the ground bed is then deleted
  - A the bed (~30 min)
  - A2 recipe check
  - B summary vs the 2012 bed
  - C sweep (~40 min, WARN only)
- **Refuses** before any work if a catalog key or input is missing, if the nj2 template or the 2012 bed is absent,
  or if its ~115 G peak would come within 150 G of the 2 T hard limit.
- **Realistic time once the mesh and the 2012 bed exist: about 2 h of compute** (~1 h 20 min without the sweep),
  plus queue time.
- **Then by hand:** register `nj2_bed2026` and run `setup_face_z.py` (~1 min).
- **Submit:** see the header. `md5_files.txt` lists the guarded files, including `data/data_catalog.yml` and
  `nj_sfincs/domain.py`, so submit after the catalog keys land.
- `split_modern_land_nj2.py` and `build_bluetopo_newer_nj2.py` are copies of round b's scripts. The only change:
  paths come from `NJ2_*` environment variables, which the pool workers see. Unset, they are round b's.

## Files

- **Code (git add):** `scripts/build_modern_land.py`, `tests/test_build_modern_land.py`, `scripts/README.md` (row).
- **This directory:**
  - scripts: `hybrid_footprints_nj2.py` (+ `hybrid_nj2.slurm`, `hybrid_expected.md5`), `build_pier_carves.py`,
    `build_gowanus_upper.py`, `split_modern_land_nj2.py`, `build_bluetopo_newer_nj2.py`, `head_equivalence.py`,
    `build_nj2_2026.slurm`, `md5_files.txt`;
  - outputs: `head_equivalence.txt`, `hybrid_nj2.log`, `hybrid_nj2_summary.txt`, `hybrid_nj2_by_municipality.csv`,
    `hybrid_nj2_power_assets.csv`, `pier_carves.txt`, `gowanus_upper.txt`.
- **Scratch (new files only):**
  - `modern_2026/derived/round_c/footprints_hybrid_nj2.gpkg`;
  - `v2/carves/{piers_v2_2026.tif,.csv, gowanus_upper_v2_2012.tif, gowanus_upper_v2_2026.tif}`.
- ⚠️ `tests/test_repo_hygiene` fails on `scripts/build_refinement_nj2.py` (another agent's, not yet in
  `scripts/README.md`).

## Jersey City DWP — imagery read (user 11-14)
13 Linden Ave (the city's Public Works yard; EIA 63530, 1 MW, in service Dec 2019, Onyx). User's imagery check: warehouse
roofs PLUS solar CARPORT canopies over parking, open beneath (cars / trucks under them). Rule: the warehouses are buildings,
the canopies are NOT (water passes under, as with ground solar arrays). The guarded share 0.35 keeps a pre-2019 USA roof
(1,947 m²) — which predates the canopies, so it is a real building — and drops the Microsoft polygons it half-covers;
the unguarded 0.62 likely counts canopy outlines as roofs. To do before the 2026-bed build (Tue/Wed): check each kept /
dropped polygon at this site by source + vintage (pre-2019 = building; a polygon only in post-2019 imagery over the parking
= canopy → drop); expect a share near 0.35, not 0.62.

## Gowanus — EPA Record of Decision (Sept 2013; `data/docs/gowanus_superfund_rod_2013.pdf`, user 11-14)
- USACE Jan 2010 survey: north of Hamilton Ave (canal ~1.7 km × 30 m) bottom −0.13 to ~−18 ft NAVD88 (−0.04 to −5.5 m);
  max ~15 ft water at low tide; "sediment surface at the head of the canal and in the eastern ends of many of the turning
  basins is exposed at low tide"; 1–3 ft deposited between 3rd and Sackett Sts 2003–2010 (ROD §5, PDF ~p. 13–17).
- 2012 bed: the ASSUMED −2.69 m flat carve covers only the last 1.55 ha to Butler St; the ROD says that head was ~2 m
  shallower (exposed at low tide). Kept (dead end, submerged at Sandy's peak, storage below low tide is depth-independent);
  optional: ramp the head to ~−0.5 m.
- 2026 bed: the ROD's remedy dredges the upper canal's soft sediment (RTA 1 native surface −11.8 to −25.6 ft NAVD88 =
  −3.6 to −7.8 m) and caps it; done ~2020–2024. GC_01_GCK_20200512 likely PREDATES that, so −2.69 m is probably too
  shallow for 2026 — look for a post-remedy survey (EPA / NYC DEP) before the 2026 build.
