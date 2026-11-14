# nj2 new area: deck / causeway dam sweep of the PLANNED 2012 bed (2026-11-14)

The question: before J2 step 6 builds `_subgrid_nj2_2012`, does any bridge deck, causeway, or other ridge
DAM a wet channel in the area nj2 adds (the nj2 ring minus v4_hot_plus's ring, 245 km²)?

**Answer: no.** After 2.0's planned `:min` tiers there is **no dam** across a tidal channel in the new area,
so **no carve was built and nothing changes in the catalog or in J2.** Every creek deck that the base bed
holds (CUDEM 1/9″ through v1.1c's merge) is already cut by `carve_v2_2012` or `gowanus_upper_v2`.

## How the check worked (read-only; nothing submitted)

| step | script | what it does |
|---|---|---|
| 1 | `planned_bed.py` | Builds a north-up 2.5 m grid of the bed J2 will produce in the new area. It starts from v1.1c's merged scoring bed. That bed is rotated, so it is read through the inverse affine on a plain window, with no boundless read. The subgrid covers the whole rectangle, and the nj2 base list and plain overlays are v1.1c's, so this is nj2's starting bed on another lattice. Then it paints `ehydro_hud_2012_v2` and applies `carve_v2_2012`, `gowanus_upper_v2` and `piers_v2_2012` with `:min`. The v1.2a five are NJ-only. Scratch outputs go to `/scratch/tpj8/tmp/nj2_decks_2026-11-14/` (`planned_2012.tif`, `base_v11c.tif`, `_tag.tif`, `area_mask.tif`). As a check, it matches CUDEM within 0.3 m on 89% of random new-area points; the rest is the building burn. |
| 2 | `sweep.py` | Takes every OSM bridge line touching the new area (2,296 lines, including rail, subway, footway and movable bridges) plus the 39 FHWA NBI 2025 water crossings within 150 m of the area. It applies the `nbi_check` WATER rule across each deck. 386 lines cross water: `osm_crossings_planned2012.csv`, `nbi_new_area.csv`. |
| 3 | `connect.py` | The **decisive test**. For each pixel it finds the lowest water level at which that pixel connects to the Upper Bay (labels of bed < h, from −3 to +4 m in 0.1 m steps). In a "blocked" pixel the bed is below 0 m but it only connects above MHHW (0.70 m). |
| 4 | `waterway_axes.py` | Walks every OSM waterway axis in the area (Newtown, Dutch Kills, English Kills, Maspeth, Whale Creek, Gowanus and its basins, East River, Hudson, KvK, the Bayonne channels) and records the highest bed along each axis. |
| 5 | `lidar_check.py` | Re-runs the sweep's flagged rows on the NYC 2017 bare earth (independent) and on CUDEM alone. |
| 6 | `fig_site.py` | Draws the panels in `fig/`. |

## Results

- **Blocked water** (bed < 0 m in the new area, connecting only above MHHW):

  | bed | km² |
  |---|---|
  | base (v1.1c, before 2.0's tiers) | 0.42 |
  | planned 2012 bed | 0.11 |

  The base's blocked clusters include the upper Gowanus north of 3rd St (sill +1.0, at the Carroll / Union / 3rd St decks) and the 4th St basin. Water connecting only between 0 and MHHW (a sill under the low tide) drops from 0.68 to 0.07 km², which is mainly the Newtown sill.

  The 0.11 km² left in the planned bed are **not channels**. They are below-grade pits and cuts, all confirmed in panels:
  - Hudson Yards (−4.4 m)
  - Sunnyside / LIRR cuts (fill never reaches)
  - the BQE trench
  - the Battery and Midtown tunnel portals
  - Jersey City / Hoboken excavations (`fig/_nj_side_blocked.png`)
  - a Jersey City cut
  - an inland pond near Liberty State Park
- **Creek crossings on the planned bed:**

  | crossing | sill (m) | channel (m) | base sill before the carve (m) |
  |---|---|---|---|
  | Hamilton Ave | −3.7 to −4.3 | | |
  | 9th St / Culver viaduct | −3.6 | | |
  | 3rd St | −2.7 | | 1.44 |
  | Carroll St | −3.0 | | 0.65 |
  | Union St, west half | −1.6 | | 0.78 |
  | Union St, east half | 0.64 | −2.7 | |
  | Metropolitan / Grand St over English Kills | −3.3 to −5.1 | | 4.32 |
  | Grand St over the East Branch | −1.7 | | |
  | Kosciuszko / BQE | −5.8 to −6.1 | | |
  | Greenpoint Ave | −6.1 | | |
  | Pulaski | −4.3 to −7.6 | | |
  | Borden Ave (Dutch Kills) | −1.0 | | |
  | Hunters Point Ave (Dutch Kills) | −0.8 to −1.2 | | |
  | Montauk Cutoff / C Secondary rail | −0.7 to −1.4 | | |

  The Union St east half sits on the bank: the carve is narrower than the canal, so the flow passes through the centre and west half. Every waterway axis stays below MHHW from mouth to head. Gowanus's highest point along its axis is −1.5 m on the planned bed (+1.0 on the base). No ridge run was found (`waterway_ridges.csv` is empty).
- **East River / Hudson spans** (Brooklyn, Manhattan, Williamsburg, Queensboro, Roosevelt Island, GWB): open, with sills at −3 to −12 m.
- **The sweep's 20 "DAM" rows are not dams.** Water goes around the ends, or there is no channel. They are:
  - footways to piers or slips: Governors Island N landing (40.6921, −74.0133), Battery Maritime slips (40.7030, −74.0063), Seaport (40.7047, −74.0023), Pier I (40.7756, −73.9923)
  - the FDR on its shore platform at E 34th St (40.7443, −73.9713; lidar sees land west of it)
  - Navy Yard footways that are 0.1–0.2 m above a 0.7 m surface

## Minor, below MHHW (no fix proposed)

- The Gowanus 6th / 7th St basin mouths have CUDEM sills at +0.1 to +0.3.
- The Navy Yard dry docks (−13 m) connect at +0.4, through their caissons. That is real.

Neither matters at Sandy's peak of about 3.4 m.

## Proposed catalog / J2 diff

**None.**

## After the build

J2 step 7 (`bed_audit`) hard-codes the v4 ring. To re-check the bed J2 actually built:

```
python planned_bed.py --built experiments/nj2/_subgrid_nj2_2012/subgrid/dep_subgrid_merged.tif
python connect.py built_2012
```

## Not covered

- **NJ-side independent check:** the NYC lidar does not reach Jersey City or Bayonne, so those sites were checked on CUDEM only.
- **Conveyance of decks that sit below MHHW:** not measured. Only the PARTIAL list flags them.
- **The v4-ring seam:** not checked.
- **Culverts and tide gates:** none are in NBI here.

## User imagery reads (11-14)
- Governors Island "N landing" footway (OSM 1006719172, 85 m) is the link to the Brooklyn-Battery Tunnel ventilation
  building: SOLID. No change (a spur, water goes round both ends).
- Pier I footway (40.7756, −73.9923): open beneath (concrete columns, not timber piles). The pier itself already reads as
  water in the planned bed; only the 19 m shore link (OSM 1556697243, sill +1.65) holds deck. No change (water goes round).
- Union St, east half (40.6795, −73.9883): canal shallow, sediment building on both sides of the bulkheads; buoys, not
  fenders. Planned bed under the east half: sill +0.64, under-deck p50 +1.99 (likely some deck residue; the real mud is
  probably nearer 0 m). No change: the centre / west half is open at −1.6 m and Sandy's ~3.4 m peak overtops it.
- Riverside Park pile fields (old rail / shipping pier stubs): unresolved by the bed (open water) — correct to first
  order; their only effect is a little bank friction.
- Union St, user's side-on photo (11-14): open water bulkhead to bulkhead under the whole span; pile-cluster dolphins
  (fender piles) at both bulkheads (the "buoys" seen from above); deck ~1–2 m over the water. So the east-half +0.64 /
  +1.99 is DECK residue, not bank. Still no change by the bed-fix rule (does not block: centre / west open at −1.6 m;
  the deck was under water at Sandy's peak); an optional small carve under the span at −1.6 m is offered to the user.
