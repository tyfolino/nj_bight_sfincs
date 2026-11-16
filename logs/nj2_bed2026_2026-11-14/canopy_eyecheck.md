# Solar canopy eye check for the 2026 bed (2026-11-16)

**What this is.** On 11-14 you set a rule: at Jersey City DWP the warehouses count as buildings and the solar
**carports** do not, because water passes under a carport. This file lists the places where only your eye can apply
that rule. Everywhere else, two independent footprint products decided it.

- **The two products:** USA Structures with a 2013 image date, and NJDEP Post-Sandy footprints (2014). Both were
  mapped before any of these panels went up.
- **How each panel array was decided:** if either product shows a building under the array, the panels sit on a real
  roof and the polygon stays. If an array only has a polygon traced after 2019 under it, it could be a canopy or a
  new building, so it comes to you.
- **OSM tags were not used to decide anything.** OSM tags all 8 DWP arrays `location=roof`, including the two that
  neither 2013/2014 product shows a building under. Your 11-14 look found carports at this site, so the OSM tag
  misses them here.

**How to look.** Open the link, then turn on historical imagery (the clock icon) to compare years. Answer
**C** (canopy or carport, open underneath) or **B** (a roofed, walled building).

**If you don't answer:** nothing changes, and the 2026 build can go as it is.
- At JC DWP both arrays stay canopies. That is the current layer, with a building share of **0.35**, which is the
  share you expected.
- At the six other sites (rows 3–8) the polygons stay as buildings.

## Required: Jersey City DWP (13 Linden Ave E; EIA 63530, 1 MW, Dec 2019)

The site has 8 OSM panel arrays, 8,790 m² in all. **Six were decided automatically as roofs:** 944, 733, 494, 398,
355 and 323 m², 3,247 m² in total. Each sits on a building that both the 2013 USA layer and the 2014 NJDEP layer
contain. They stay buildings, and they are what gives the current share of 0.35. The 355 m² array is only half under
the 2013 USA polygon, so 176 m² of a real roof is not burned. That is too small to matter, and it is left as it is.

| # | site (OSM way, panel m²) | Google Earth | question | evidence | **C** (default) | **B** |
|---|---|---|---|---|---|---|
| 1 | DWP array A, the largest field (w1159802654, 4,044 m²) | [40.688516, −74.090317](https://earth.google.com/web/@40.688516,-74.090317,7a,250d,35y,0h,0t,0r) | Is the big panel field at this point a carport, open underneath with vehicles or parking below it, or panels on a walled building's roof? | No building in USA 2013 or NJDEP 2014. A Microsoft release-2 polygon (6,124 m², which covers 93% of the array) and a 2016 OSM building outline (w424974390) say there is one. | No change: the MS polygon stays dropped (share 0.35) | Add MS polygon `ms_r2` 6,124 m² to the burn: share 0.35 → **0.78** |
| 2 | DWP array B, west of A (w1159802653, 1,500 m²) | [40.688827, −74.090639](https://earth.google.com/web/@40.688827,-74.090639,7a,200d,35y,0h,0t,0r) | Same question for this smaller field. | No polygon in USA 2013, NJDEP 2014 or MS. Only a 2016 OSM outline (w424974481) covers it. | No change | Add the array outline as a building, from OSM because no other product traced it: share +0.17 (to 0.52, or **0.95** if row 1 is also B) |

**Hydraulic stakes are low.** Ground under the arrays is 6.5–6.9 m NAVD88: CUDEM reads 6.6–6.9 m and the modern
lidar 6.5–6.8 m. That is about 3 m above Sandy's harbour peak, so a burn here should not move water in the Sandy runs,
and probably not in the +3 m runs either (J3's +3 m map will confirm). Your answer changes the asset's building-share
statistic, not the flooding.

## Optional: the same rule at other solar plants in the nj2 area (rows 3–8)

**How these were found.** I screened 87 solar plants in OSM that touch the nj2 ring + 500 m. I kept the ones where
the nj2 footprint layer has polygons over the panels that neither product shows before 2015, and whose ground is
**below 7 m** (p20 of a 10 m grid inside the plant, outside buildings, read from the nj2 2012 bed). That is where a
false +10 m roof could block water. The full table is `canopy_check/solar_detail.csv`.

| # | site (OSM plant, start, MW) | Google Earth | question | evidence (polygons not in 2013/2014; ground p20) | **keep** (default) | **C**: drop them |
|---|---|---|---|---|---|---|
| 3 | Hudson County Solar (p170, 2022-06, 1.2 MW) | [40.726624, −74.106646](https://earth.google.com/web/@40.726624,-74.106646,2a,350d,35y,0h,0t,0r) | Are the seven similar long outlines here carport canopies over parking, or roofed buildings? | 7 USA polygons dated 2024, 860–1,080 m² each, 5,192 m² over panels; ground **1.9 m** | burned as buildings (share 0.78) | −5,192 m² of +10 m burn (share 0.78 → 0.12) |
| 4 | IFF Solar Farm, Union Beach (p267, 2019-06, 5.5 MW) | [40.444004, −74.155101](https://earth.google.com/web/@40.444004,-74.155101,4a,400d,35y,0h,0t,0r) | Are the outlined blocks inside the plant rows of ground panels (or carports), or roofed buildings? | 15 USA polygons dated 2024 (the largest 2,102 / 1,526 / 1,243 / 777 m²), 2,939 m² over panels; ground **3.4 m** (Sandy flooded Union Beach) | burned | −2,939 m² |
| 5 | DRPA Ferry Ave Station, Camden (p176, 2021-11, 3.2 MW) | [39.923256, −75.093668](https://earth.google.com/web/@39.923256,-75.093668,4a,300d,35y,0h,0t,0r) | Are the outlined pieces carport canopies over the PATCO parking, or small roofed buildings? | 3 USA polygons dated 2024 (380 / 270 / 43 m²), 691 m²; ground **3.4 m** | burned | −691 m² |
| 6 | CCUA Solar, Bridgeton (p981, 2021-07, 1.5 MW) | [39.413922, −75.235163](https://earth.google.com/web/@39.413922,-75.235163,2a,250d,35y,0h,0t,0r) | Is the outlined block a panel block or a roofed building? | 1 USA polygon dated 2019-10, 643 m² (411 m² on the panels); ground **1.9 m** | burned | −643 m² |
| 7 | Salvation Army Kroc Center, Camden (p177, 2022-04, 1.1 MW) | [39.953891, −75.103182](https://earth.google.com/web/@39.953891,-75.103182,2a,250d,35y,0h,0t,0r) | Are the outlined pieces carport canopies or roofed buildings? | 2 USA polygons dated 2024 (282 / 123 m²); ground **1.9 m** | burned | −405 m² |
| 8 | BNB Camden Solar (p436, 2017-12, 3.7 MW) | [39.937924, −75.102888](https://earth.google.com/web/@39.937924,-75.102888,5a,250d,35y,0h,0t,0r) | Is the outlined block a panel block or carport, or a roofed building? | 1 USA polygon dated 2019-11, 196 m²; ground **4.7 m** | burned | −196 m² |

### Decided without an eye check
- **The panels sit on a real roof, so the polygon stays:**
  - Everything on a 2013 or 2014 footprint. That covers the six DWP arrays above, all of CCMUA (the guard, share
    1.00, entirely on pre-2015 roofs), and the large rooftop sites: Goya, US Foods, Amazon, IOS-ERW9, DG Iron Mountain,
    Campus Drive and others.
  - **American Goldfinch ACY2** (one MS polygon of 95,305 m²) and **DG Camden Holtec** (one MS polygon of 32,785 m²).
    A single unbroken polygon of 33,000–95,000 m² is a warehouse or factory roof, not a carport. Both buildings
    post-date 2014, which is consistent with no 2013/2014 footprint under them.
- **Kept as built, because the ground is too high to matter** (p20 ≥ 11 m, above any water we model): Reeves Station
  (78 MS polygons, probably 2012 ground panel rows read as buildings), Pennsauken Solar, Samuel Mickle School,
  Cinnaminson Landfill, NJ Oak, Absegami and Trenton Solar Farm.
- **Kept as built because they are too small:** sites with less than 150 m² of unexplained polygon.

## What an answer means for the build

- **Every answer that differs from the default** (B at rows 1–2, C at rows 3–8) changes
  `footprints_hybrid_nj2.gpkg`. That means re-running `hybrid_footprints_nj2.py` with a small by-name add/drop list
  (about 4 min) **before** the 2026 build. Its P5 burn is skip-if-done, so the layer has to be right when the job
  starts.
- **With all defaults** the layer is final and the build can be submitted.

Provenance: `canopy_check/` has the scripts (`inv.py`, `parts.py`, `njdep.py`, `hist.py`, `screen.py`, `detail.py`),
the DWP polygon inventory (`inventory.csv`), the OSM extract (`osm_site.gpkg`) and the screen
(`solar_screen.csv`, `solar_detail.csv`).
- OSM data came from the OSM API map call and way history (`api.openstreetmap.org`, 11-16).
- The DWP building outlines w424974390 and w424974481 are version 1, 2016-06-14. The one node edit on w424974390
  (2023-04-05, gluing it to the panel ways) moved that node by 0.2 m.

## Answer (user, 2026-11-16)

**Rows 1 and 2: both C — open underneath** (user's oblique Google Earth view: vehicles parked under both fields;
which roof is which: `canopy_check/dwp_arrays_map.png`). = the default: no change to `footprints_hybrid_nj2.gpkg`,
the MS polygon `ms_r2` 6,124 m² and the 2016 OSM outline w424974481's canopy part stay OUT of the burn, JC DWP
building share **0.35**. Rows 3–8 (optional) not answered → default (polygons stay buildings). No re-run of
`hybrid_footprints_nj2.py` needed; the 2026 build can use the layer as is.

**Row 3 (user, 2026-11-16): C — open.** Hudson County Solar's 7 long outlines (USA 2024, 5,192 m² over panels,
ground 1.9 m) are carports → DROP them from `footprints_hybrid_nj2.gpkg` (share 0.78 → 0.12). To apply together with
row 4's answer in one `hybrid_footprints_nj2.py` re-run (by-name drop list), before the 2026 build.
**Row 4:** asked again block by block — `canopy_check/iff_blocks_map.png` + `iff_blocks.csv` (15 outlines; 1–4 =
2,102 / 1,526 / 1,243 / 777 m²; blocks 1–3 sit beside 2014 NJDEP fragments, so may be plant buildings).
**Row 4 (user, 2026-11-16): B — blocks 1–4 are real solid buildings** → default, all 15 IFF outlines stay.

**Applied 11-16 14:55:** `hybrid_footprints_nj2.py` re-run with `CANOPY_DROP = {"p170": Hudson County Solar}` (asserts
exactly 7): 7 post-2019 outlines (5,610 m² polygon area, 5,192 m² over panels) dropped; Hudson County Solar share
0.777 → **0.119**, JC DWP unchanged **0.349**. Layer total 1,179,022 polygons, 298.53 km². `footprints_hybrid_nj2.gpkg`
md5 eeb0e1a2… → **4b13c2bd5f7666753769560c528e99dc** (4 m 08 s). The 2026 build's md5 is written at submit, so nothing
else to update.
