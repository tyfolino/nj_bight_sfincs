# NLCD → Manning's n reclass for Atlantic-coast storm surge

Used here in place of the hydromt-sfincs default `NLCD_SFBD_mapping.csv`
(SF-Bay-Delta-tuned, marsh-heavy). Base values follow **Bunya et al. (2010)**
and **Atkinson et al. (2011)** — the de-facto storm-surge CONUS table used in
ADCIRC studies and the FEMA NACCS post-Sandy reanalysis — with two NJ-specific
refinements (classes 23 and 24, see below).

Key differences vs the shipped SFBD table:

- **Developed classes (21–24):** LOWER n (0.030–0.130 vs 0.070–0.140) — more
  realistic urban flood conveyance for East-Coast coastal cities.
- **Forest classes (41–43):** HIGHER n (0.160–0.180 vs 0.120–0.150) — denser
  East-Coast canopy / understory.
- **Woody Wetlands (90):** HIGHER n (0.140 vs 0.100).
- **Shrub/Scrub (52):** added; SFBD omitted it entirely.

## Per-class values and source

| NLCD | class | n | source |
|------|-------|---|--------|
| 11 | Open Water | 0.020 | Bunya/Atkinson |
| 21 | Developed - Open Space | 0.030 | Bunya/Atkinson |
| 22 | Developed - Low Intensity | 0.050 | Bunya/Atkinson |
| **23** | **Developed - Medium Intensity** | **0.100** | **Bunya (raised from Atkinson 0.080)** |
| **24** | **Developed - High Intensity** | **0.130** | **NJ-tuned (between Bunya 0.150 and Atkinson 0.120)** |
| 31 | Barren Land | 0.040 | Bunya/Atkinson |
| 41 | Deciduous Forest | 0.160 | Bunya/Atkinson |
| 42 | Evergreen Forest | 0.180 | Bunya/Atkinson |
| 43 | Mixed Forest | 0.170 | Bunya/Atkinson |
| 52 | Shrub/Scrub | 0.070 | Bunya/Atkinson |
| 71 | Grassland/Herbaceous | 0.035 | Bunya/Atkinson |
| 81 | Pasture/Hay | 0.033 | Bunya/Atkinson |
| 82 | Cultivated Crops | 0.040 | Bunya/Atkinson |
| 90 | Woody Wetlands | 0.140 | Bunya/Atkinson |
| 95 | Emergent Herbaceous Wetlands | 0.045 | Bunya/Atkinson |

## Why classes 23 and 24 were tuned

A first-pass Sandy run with pure Atkinson values (23=0.080, 24=0.120) produced
a small CSI gain overall but visible over-flooding in residential Asbury Park /
Shark River. Per-cell NLCD diagnostic (2026-05-25): of 12 708 new false-alarm
cells, **55 % were class 23 and 16 % class 24**, with an FA/HIT ratio of 2.5×
and 1.9× respectively — clear signal both classes were too low. Atkinson (2011)
adopted Bunya's framework but with reduced developed-class values for the Gulf
coast; Bunya (2010)'s original 0.10 for class 23 is closer to what other
sources cite for medium-intensity NJ/Mid-Atlantic suburban land cover. We adopt
Bunya's 0.10 for class 23, and split the difference (0.13) for class 24.

## CSV formatting gotcha

The companion CSV is kept bare (no comment lines) because the hydromt
PandasDriver calls `pd.read_csv` without `comment="#"`, and any leading `#`
lines crash the parse.

## References

- Bunya, S., et al. (2010). A high-resolution coupled riverine flow, tide,
  wind, wind wave, and storm surge model for southern Louisiana and
  Mississippi. *Monthly Weather Review*, 138(2), 345–377.
- Atkinson, J., et al. (2011). Hurricane storm surge and tide models for the
  Gulf coast. (Adopts Bunya's framework with reduced developed-class n.)
- USACE / FEMA Region II NACCS (North Atlantic Coast Comprehensive Study) —
  post-Sandy reanalysis using values in this family.
