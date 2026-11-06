# The generic anomaly checks ("seems funky")

User 11-05: the bed audit should also "catch anything that seems funky to flag for manual review". The four
authoritative checks (impoundment, water_surface, channel_depth, crossing_nbi) compare the bed with an independent
dataset; these six compare it with what REAL ground and bathymetry do not do, and rank what they find by whether it
blocks the tide or a Sandy flow path.

| check | looks for | the signature it was built on |
|---|---|---|
| `anomaly_flat` | flat patches (3x3 range <= 5 mm) at a suspicious level: a fake floor under a lake pool, CUDEM's ~0 m fill, a lidar water surface above MHHW or in the tide band | Alloway Lake arm, Silver Lake (E4), the flat "sills" |
| `anomaly_ridge` | thin (<= 12 m) or deck-scale (<= 34 m) ridges standing over a CHANNEL on mapped water, or tall thin walls in the Sandy footprint | Alloway's 1.6 m sliver, decks, CR 581 |
| `anomaly_pit_spike` | compact pits in normally-dry ground (>= 16 m from buildings) inside the Sandy footprint; post-sized spikes in water | carve over-reach, piles, lidar returns |
| `anomaly_seam` | steps > 0.5 m along the boundary between two of the bed's own sources (its recipe, rebuilt on the 25 m grid) | the CR_02 / CUDEM seam |
| `anomaly_disagree` | 2012 vs modern > 1 m (water closed / deepened, land raised / lowered in the Sandy footprint); CUDEM vs lidar on land | the 11-04 modern sweep, Silver Lake |
| `anomaly_profile` | along every tidal NHD HR flowline: a sill above MHHW with tidal water below it on both sides, or a submerged plug > 2 m above the channel on both sides | the Christina plug, Grays Ferry |

## Files

| file | what |
|---|---|
| `common.py` | the 25 m context grid (MHHW, its source, NHD water / lakes from `data/normal_surface_v4/`; Model 1.0.0's active faces + Sandy peak rasterised from `p4-premier/sfincs_map.nc`, cached in `/scratch/tpj8/nj_bight_sfincs_data/audit/_anomaly_context/`), the tiled bed reader (ROTATED raster, through the affine; `--overlay-min` / `--overlay` for a stand-in bed; `AUDIT_BBOX=lon0,lat0,lon1,lat1` limits a test run), the exception rows (Sandy peak, nearest power asset) |
| `tiers.py` | every recipe tier resampled (nearest) onto the 25 m grid (for `anomaly_seam` / `anomaly_disagree`); ~1 min |
| `calibrate.py` | known cases + the user's eye checks → `out/calibration_anomaly.md` |
| `../../run_anomaly.sh` | `srun ... bash run_anomaly.sh LABEL BED [--overlay-min K] [--overlay K]`: the six checks through `scripts/bed_audit.py` |

## Run

```
python scripts/bed_audit.py --bed experiments/v4_refreeze_swz/_subgrid_v1_1b --label v1_1b       # every check present
python scripts/bed_audit.py --bed ... --label L --checks anomaly_flat,anomaly_profile              # some
python scripts/bed_audit.py --label L --collect-only                                               # re-merge
python scripts/bed_audit.py --compare p100 v1_1b                                                   # fixed / broken
```

## Calibration and false alarms (2026-11-05; `out/calibration_anomaly.md`)

Beds: `p100` = Model 1.0.0's bed; `v1_1b` = STAND-IN (`_subgrid_v1_1` + `deck_fix_v4b` as a min + `alloway_pool_v4`;
re-run on `_subgrid_v1_1b` once job 63577223 has built it); `modern` = `_subgrid_modern2026` + v1.1's deck overlay.

**Known cases: every one behaves as it should on every bed.**

| case | 1.0.0 | v1.1b | modern |
|---|---|---|---|
| Alloway arm fake floor + sliver | fires (ridge, high; flat 'lake_floor_below_pool' high) | silent (fixed) | silent (correct) |
| Silver Lake (E4) CUDEM floor under the pool | fires (flat high: 0.00 m under 2.55 m; disagree high) | fires | (modern is right; disagree says the beds differ) |
| Christina plug | fires (profile 'channel_plug' high, 48 m, 3.4 m) | silent (v4e) | fires (modern still has v4c) |
| Grays Ferry (M537) | fires (plug, 8.3 m) | fires | fires |
| Shark R. (M271), Cape May trestle (M181), harbour footway (M232), Penn's Landing (M562) | — | — | all fire high |

**The user's eye checks** (a 'hit' = an anomaly within 150 m, or 3 x sqrt(area) for patches):
modern bed: of the 13 deck short-list sites the user OPENED, 10 fire; of the 3 KEPT, M064 fires (its rail embankment
reads as a ridge) — 1 false alarm of 3. Underpasses (decks over streets) are NOT what these checks look for (they look
in channels): 2–3 of 11 fire; the NBI / OSM crossing check is the one for those.

**False alarms, honestly:** the counts are large (≈ 21,700 / 22,100 / 31,800 rows on 1.0.0 / v1.1b / modern), and most
are not errors a reviewer would fix. Where the noise is, from the tuning runs:
- `anomaly_ridge` in tidal marsh: the first rule flagged 8,751 in one 30-tile Salem box (marsh strips between
  creeks); restricting to MAPPED water, dropping ridges over CUDEM's exact 0 m fill and requiring the crest to clear the
  local median by 0.5 m cut it to ~800 in that box — still mostly marsh features there. Its `low` class (thin walls on
  land) is mostly real walls / berms.
- `anomaly_pit_spike` first flagged ~11,000 per bed (residential docks in the lagoons, street canyons between burned
  buildings); after the dock / building rules ~1,600.
- `anomaly_seam` on the modern bed (3,288 high) mostly traces `modern_land_2026`'s edges: the known 11-04 recipe bug
  (land lidar over the river beds) — expected to drop once the recipe fix lands.
- `anomaly_flat` low (2,559) = unmapped ponds and diked fill below MHHW: low by design.
Read the `high` rows first, and especially places where SEVERAL checks agree (`n_checks` in `exceptions.csv`, which
the ranking puts first within a severity). A spot check of the top of `out/<label>/AUDIT.md` is the right next step
before trusting any count.

`--compare p100 v1_1b` (anomaly checks only): 210 places gone — including the Christina plug (profile + ridge +
channel_depth agree) — and 476 new: those are what the v1.1b changes (corrected decks, Alloway raise, v4e, channel n)
put into the bed and are worth a look before the tag (`out/compare_p100_vs_v1_1b_subset.md`).
