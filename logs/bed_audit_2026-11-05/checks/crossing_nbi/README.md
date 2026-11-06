# crossing_nbi

Every FHWA National Bridge Inventory structure inside the model (3,522; 2025 submission, NJ / DE / PA / NY; public domain,
"Federal Highway Administration, National Bridge Inventory, 2025"), matched to its OSM bridge line. The check tests
whether the bed lets water through the opening at the level of what passes under it (road / rail / path / waterway).
The method, thresholds (open ≤ 0.30 m, blocked > 0.50 m, DECK-IN-BED = the bed at ≥ 0.6 × the NBI 54B deck height),
coverage limits, calibration against the user's eye checks and known cases are in
**`logs/nbi_crossings_2026-11-05/README.md`**. This folder only adapts that code (`nbi_check.py`, imported) to the
audit CLI and exceptions columns.

Raw data: `/scratch/tpj8/nj_bight_sfincs_data/nbi/` (20 MB, four delimited files). The parse and OSM match are bed-independent
and cached in `logs/nbi_crossings_2026-11-05/out/`.

```
python -I check.py --bed experiments/v4_refreeze_swz/_subgrid_v1_1b --label v1_1b --out out/v1_1b/crossing_nbi.csv
python -I check.py --bed experiments/v4_refreeze_swz/_subgrid_v1_1 --label v1_1b --overlay-min deck_fix_v4b --out ...   # stand-in (run 11-05)
python -I check.py --bed experiments/v4_refreeze_swz/_subgrid_modern2026 --label modern --overlay-min deck_fix_v4 --out out/modern/crossing_nbi.csv
```

Exceptions = every structure not OPEN.
- **Severity:**
  - **high:** DECK-IN-BED or a BLOCKED water opening holding back ≥ 0.25 m of 1.0.0's Sandy water nearby. ⚠️ On
    inland streams that water can be river or rain.
  - **medium:** the same faults with less water, or FILL? / OBSTRUCTED / PARTIAL with ≥ 0.25 m.
  - **low:** the rest, plus `undecidable_*`.
- **Kinds:** `deck_in_bed_over_road_or_rail`, `waterway_opening_blocked`, `water_surface_as_bed_under_bridge`,
  `obstruction_under_bridge_below_deck_level` (the review queue), `opening_narrower_than_structure`,
  `marginal_within_lidar_accuracy`, `culvert_*`, `undecidable_no_osm_bridge_match`,
  `undecidable_no_under_feature_in_osm`.
- **Extra columns:** `held_m` (bed in the opening minus the under-feature level) and `held_sandy_m`.

Run 11-05: v1_1b (stand-in) 1,484 exceptions (high 89 / medium 239 / low 1,156); modern 1,275 (high 82 / medium 195 /
low 998). Not covered (not in the NBI): railroad bridges, footbridges, piers, private bridges. Those stay on the OSM + bed
sweeps.

**Evidence column (11-05):** `measured (NBI 54B underclearance)` only for road / rail crossings judged against the NBI
deck height; every water / culvert row is `inferred (our bed vs the water / street either side)`. The NBI records no
underclearance over water, so it proves only that a bridge exists, its length and roughly where it is. The verified
tidal-water subset and the `nbi_open_v4` overlay built from it are in `logs/nbi_crossings_2026-11-05/README.md`.

## NOAA ENC charted clearances + piers (2026-11-06, `enc.py`)

**Source:** NOAA ENC Direct to GIS, S-57 objects in the harbour + approach usage bands, pulled 2026-11-06 into
`/scratch/tpj8/nj_bight_sfincs_data/audit/levee_enc_2026-11-06/enc/`. Box: −75.72, 38.73, −73.55, 40.99. Public
domain.
- **BRIDGE:** 1,216 lines + areas. VERCLR (fixed) / VERCCL (movable, closed) vertical clearance and HORCLR. The
  clearances are in m above the cell datum, which on US charts is MHW; the crossing's MHHW stands in for it.
- **PYLONS:** 207 bridge supports (points + areas).
- **PILPNT:** 2,904 piles.

The coastal service was down, and berthing has none of these objects here.

**Matching:**
- **Bridge:** each exception row is matched to the best ENC bridge within 100 m of its water-crossing point (else the
  NBI point). A charted clearance wins first, then harbour before approach, then the nearest.
- **Piers:** charted piers are the PYLONS + PILPNT inside the matched ENC bridge + 20 m, or the OSM bridge line +
  15 m, or the point + 40 m.

**Extra columns:**
- **ENC bridge:** `enc_d_m`, `enc_catbrg`, `enc_clear_m`, `enc_horclr_m`, `enc_cell`, `enc_soffit_m` (MHHW +
  clearance).
- **Chart verdict:** `enc_verdict`.
- **Piers:** `piers_source` (ENC charted / NBI estimate), `piers_charted_n`, `piers_charted_pos` (lon lat; …),
  `piers_nbi_est`, `pier_spacing_m`, `piers_in_channel_est`, `channel_width_m`, `blockage_frac`, `blockage_basis`.
- **Tidal flag:** `tidal_water` (the channel either side is below MHHW).

**`enc_verdict` on a water fault (BLOCKED / FILL?):**
- **CONFIRMED (measured):** the chart has a navigable opening, but the LOWEST bed under the whole deck is at or above
  MHHW. A charted opening cannot be dry, so the fault is measured, not inferred.
- **SOFTENED:** the bed in the opening is water, and the model's open width is at least half the charted HORCLR. That
  makes it a constriction, not a block.
- **constriction:** a charted opening exists and the bed under the deck is below MHHW, but the opening is narrower or
  higher than the channel either side. The chart cannot settle it.

**NBI pier estimate (where the chart has none):**
- piers ≈ main (item 45) + approach (item 46) spans − 1;
- spacing ≈ L49 / spans;
- piers in the channel ≈ channel width / spacing − 1, capped at the total;
- **blockage ≈ piers in the channel × 1.5 m ÷ channel width.** The 1.5 m is an ASSUMED typical pier or pile-bent width
  across the flow; charted PYLONS areas use their own short side.
- Channel width = the rule's `water_expect_len` (the water stretch judged), else L49.

**Results (11-06).** "Tidal-water faults" = water rows (BLOCKED / FILL?, culverts included) whose channel either side
is below MHHW (`tidal_water`).
- **v1_1c:** 122 of them. The 11-05 "103" was the v1.1 stand-in under an earlier cut.
- **modern:** 138.

| | v1_1c | modern |
|---|---|---|
| tidal-water faults | 122 | 138 |
| an ENC bridge within 100 m | **50** (41 %) | 51 (37 %) |
| … with a charted vertical clearance | 12 | 11 |
| CONFIRMED (measured: charted opening, lowest bed under the deck ≥ MHHW) | **1** (NJ 1515150, lowest bed 0.29 m, MHHW 0.08) | 2 (DE 1386 002; DE 3717 257, 0.6 m charted clearance, bed 1.31 m) |
| WIDTH OK (FILL? rows: the model's opening is ≥ half the charted HORCLR; the depth stays open) | 10 | 9 |
| constriction (charted opening, our lowest bed below MHHW but the opening narrower / higher than the channel) | 39 | 40 |
| no chart match (mostly small creeks off the charts) | 72 | 87 |

- **No BLOCKED verdict flips to open.** Where a chart exists, the BLOCKED faults read as constrictions (the bed under
  the deck is water but sits above the channel either side) or are confirmed.
- **The chart does not reach the faults that matter most.** Of the 7 high-severity tidal faults on v1_1c, 3 are
  charted.
- **Piers:**
  - v1_1c: charted supports (PYLONS / PILPNT) on **35 of 1,488** rows, 3 of them tidal-water faults. The other 1,453
    rows carry only the NBI estimate.
  - modern: 38 of 1,276, 3 of them tidal-water faults.
  - The estimated blockage is 0 on almost every water fault (median 0, p90 0; 4 rows above 10 %): these are short
    spans, and the channel at the crossing is narrower than one span, so no pier stands in it. The pier term matters
    on the long multi-span crossings, which the chart covers better.

## What the NBI does not list, counted in OSM (`osm_vs_nbi.py` → `osm_vs_nbi.csv` / `.md`)

| area | NBI records | OSM road bridge | OSM road bridge NOT in NBI | OSM rail bridge | OSM rail bridge NOT in NBI | OSM foot / path bridge | OSM foot / path bridge NOT in NBI | OSM other bridge | OSM other bridge NOT in NBI | OSM underpass ways with maxheight |
|---|---|---|---|---|---|---|---|---|---|---|
| v4 ring (1.x) | 3695 | 5424 | 1060 | 2363 | 2177 | 3177 | 2101 | 531 | 437 | 1406 |
| 2.0 ring | 4187 | 6341 | 1945 | 2665 | 2479 | 4144 | 3063 | 607 | 513 | 1771 |
| 2.0 new area only | 492 | 917 | 885 | 302 | 302 | 967 | 962 | 76 | 76 | 365 |

- **NBI records** = rows of `nbi_domain.csv` in the area.
- **"NOT in NBI"** = an OSM bridge way that is neither an NBI match nor within 25 m of one. In the 2.0 new area the NBI
  match was never run (it covered the v4 model only), so there that column is an upper bound.
- **Reading:**
  - Inside the v4 ring, OSM already holds the structures the NBI skips: 2,177 rail bridges, 2,101 foot / path bridges
    and 437 others with no NBI record, plus 1,406 road ways with a posted `maxheight` (the underpass slot depth).
  - The 2.0 new area adds ~300 rail and ~960 path bridges and 365 `maxheight` ways.
- **Commercial data (TomTom / HERE):** not worth buying for this.
  - Their bridge and tunnel flags and truck clearances cover the same public road and rail network OSM maps here, and
    they carry no clearance over WATER either.
  - The remaining gaps are (a) the depth under a span on a water surface (the FILL? rows), which needs surveys or
    eHydro, and (b) the true height of private / rail decks.
  - Neither product supplies those.
