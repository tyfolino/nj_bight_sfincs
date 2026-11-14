# Poster text: DRAFT (2026-11-12, for the Rutgers climate poster, 11-13; user's 8 text decisions applied 11-13)

A draft to edit, not to paste whole. [Brackets] = numbers still coming tonight or a
choice for you. Every number below has its source in the figure READMEs beside this file.

---

## Title (pick one)

1. **Rebuilding Hurricane Sandy's compound flood across the New Jersey coast**
2. **Surge, waves, rain and rivers together: a validated Sandy flood model for New Jersey**
3. **If Sandy hit today: a compound-flood model of the New Jersey coast and its power grid**

## Abstract (~150 words)

Hurricane Sandy (October 2012) flooded the New Jersey coast through several processes at once:
storm surge and tide, breaking waves, wind, rain and swollen rivers. Building on the USACE NACCS
Sandy simulation, we built a compound-flood model that runs all of them together, from Cape May to New York Harbor and up Delaware Bay,
the Raritan and Newark Bay. It uses SFINCS, a fast reduced-physics flood model, on a grid of
about 4 million cells that reaches 25 m along shorelines and channels, with ground elevations
resolved at 3 m. It also represents building footprints and the major levees. The model
reproduces Sandy's peak water level at 119 USGS high-water marks to within 0.35 m (RMSE;
93 % within half a metre) and matches 85 % of FEMA's flooded area (critical success
index, CSI, 0.82, rain off). We then re-ran Sandy on today's ground, with post-2012 elevation surveys and
flood defences, and asked which of today's electric substations and power plants it would
flood: 52 of the 182 New Jersey sites the model covers (60 on 2012 ground). [one-sentence result from fig 4 — your words]

## Figure captions

**Fig 1. The model.** The model grid, shaded by cell size (25–200 m: finest along shores and
channels). Storm tide enters along the orange ocean boundary; 61 rivers flow in at the green
triangles. Checked against 46 water-level gauges inside the model and 119 USGS high-water marks
(pink).

**Fig 2. Peak water at Sandy's high-water marks.** Each point is one USGS high-water mark
(quality excellent or good). The model value is the median peak water level of flooded ground
within 50 m of the mark, on the 3.125 m flood map. Grey band = within ±0.5 m. The few large
misses are marks behind coastal lakes (Deal Lake, Wreck Pond) whose outlets the model's ground
holds shut; without those five, RMSE is 0.24 m (n = 114). Scores from Model 1.1.0 (rain on): RMSE 0.35 m,
bias −0.07 m, 93 % within ±0.5 m (n = 119; median within 50 m).

**Fig 3. Flood extent vs FEMA's mapped Sandy surge.** Blue: both flooded; orange: FEMA flooded,
model dry; pink: model flooded, FEMA dry. Scored on New Jersey land only (FEMA's map stops at
the state line) and only on land the model computes; open water and ground outside the model are not
scored. Scores from the rain-off twin of Model 1.1.0: CSI 0.82, POD 0.85, FAR 0.03 (model flooded = peak
depth ≥ 0.15 m on the 3.125 m flood map, scored on 15 m cells; 2,413 km² of non-NJ land not scored; Model 1.1.0
with rain on: 0.80 / 0.87 / 0.09). Rain is switched off for this comparison because FEMA mapped the
surge, and rain ponding inland would otherwise count as false alarms, at the cost of some hits in Cape May.

**Fig 4. If Sandy hit today.** Sandy's 2012 storm (same tide, winds, waves, rain and rivers) on
today's ground: post-2012 elevation and channel surveys, today's levees and tide gates
(Elizabeth, Rahway, Port Monmouth, and the Pews Creek gate). Substations and power plants that flood are in orange.
Preliminary: the 2026 ground is new and not yet validated, and building footprints and land
cover are still 2012's. Sea level is Sandy's, so this isolates what the changed ground and
defences do. Of the 182 New Jersey plants and substations the model covers, 52 flood and 130 stay
dry (on 2012 ground, 60 / 122); 71 more of the 253 in the region sit at the model's edge and are not
computed. Ten sites change (ringed): nine go dry, one goes wet.

## Three takeaways

1. **Compound matters.** Surge alone does not explain Sandy's flooding. Waves, rain and rivers
   change peak water by tens of centimetres in the back bays and up the rivers.
   [Optional: a number from the waves-on vs waves-off pair, e.g. the wavemaker's effect on the
   open-coast marks.]
2. **It is checked against what Sandy left behind:** 119 high-water marks, within 0.35 m, and
   FEMA's mapped extent, CSI 0.82 (rain off). Good enough to ask "what floods" at the scale of a single
   substation.
3. **Today's coast is not 2012's.** New levees, gates, dunes and dredged channels change where
   the same storm would go. [Fig 4 result, your words: 52 of the 182 sites the model covers flood on today's ground vs 60
   on 2012's; 10 change, 9 of them to dry.] Next: future sea level and other storms on
   today's ground.

## Novelty line (from `lit_check.md`, 11-12)

"One of the first Sandy hindcasts" is NOT defensible: Sandy has been modelled in NY/NJ 15+ times,
and NACCS (whose storm tide we use at the boundary) already had surge, tide, waves, wind and
rivers coast-wide. What holds, with "to our knowledge", is the COMBINATION:

> To our knowledge, the first hindcast of Sandy across the New Jersey coast that runs storm tide,
> waves (including infragravity), wind, rain and rivers together and checks the result against
> both USGS high-water marks and FEMA's mapped flood extent.

Safer, no priority claim: "…builds on the USACE NACCS Sandy simulation, adding waves with
infragravity, rain and rivers at 25 m…" Traps: say "New Jersey coast", not "statewide" (the
Hudson waterfront is not in 1.1.0); the marks and the FEMA extent are not independent checks
(FEMA interpolated those marks onto terrain); credit NACCS.

## Speed (user 11-12: sell it)

Our own numbers (CLAUDE.md §4 / FINDINGS §20, production engine): the full 72-hour Sandy run, waves on, ~4 million
cells, finishes in **about 3 hours on one 64-core computer** (about 5.4 h on 16 cores). Waves-off variants run in under
2 h. That is what lets us run dozens of what-if tests (bed fixes, levees, gates, today's ground, sea-level offsets) in
a week.

Comparison claim: SFINCS's reduced physics reaches accuracy similar to Delft3D at roughly **two orders of magnitude**
less compute. Source: Leijnse's 2018 TU Delft thesis (Hurricane Irma, Jacksonville):
https://repository.tudelft.nl/record/uuid:53037d4d-d7a9-4f71-9b22-8c329f2b384c . The 2021 SFINCS paper
(Leijnse et al., Coastal Engineering, doi 10.1016/j.coastaleng.2020.103796) positions it between bathtub models and
Delft3D / XBeach. Check its full text for a runtime number before quoting "100×" from the paper rather than the thesis.
Poster wording (safe): "A 72-hour storm on 4 million cells runs in about 3 hours on one 64-core computer: fast enough
to test dozens of scenarios, where full hydrodynamic models such as Delft3D typically take one to two orders of
magnitude longer."

## Methods box (if there is room)

- SFINCS v2.3.3 (Deltares), built with HydroMT-SFINCS; subgrid tables on a 3.125 m ground model.
- 72-hour run, 28–31 Oct 2012; about 3 hours on one 64-core computer.
- Storm tide: USACE NACCS Sandy simulation along a drawn ocean boundary.
- Waves: SnapWave, NOAA CORA offshore, with long (infragravity) waves.
- Wind: NACCS winds blended into ERA5. Rain: NOAA AORC.
- Rivers: USGS discharge at 61 inflows.
- Levees: USACE National Levee Database.

## Data credits

USACE (NACCS / Coastal Hazards System, eHydro, National Levee Database, NCMP lidar) · NOAA
(CO-OPS gauges, CUDEM, CORA, AORC, NOS surveys) · USGS (high-water marks and storm-tide sensors,
discharge, 3DEP, CoNED) · ECMWF / Copernicus (ERA5) · FEMA (MOTF surge extent) · NJ OGIS /
NJDEP (lidar DEM, building footprints) · USDA NRCS (SSURGO) · MRLC (NLCD) · GMRT (CC BY 4.0) · power plant and substation outlines © OpenStreetMap contributors (ODbL).
Computing: Rutgers Amarel (OARC).

---

## Poster v2 sections (2026-11-13, user asked for Abstract / Introduction / Methods / Results / Conclusions / References)

Numbers unchanged from above. These are the texts in `poster_draft_2026-11-13.pptx`; v1 (figure panels) is
`poster_draft_2026-11-13_v1.pptx`.

### Introduction

Coastal New Jersey floods from several directions at once: storm tide and waves from the ocean, rain on the
land, and rivers running into the bays. Hurricane Sandy (October 2012) brought all of them together (Blake et
al. 2013; Suro et al. 2016). Earlier Sandy models either covered the whole coast without rain, notably the
USACE NACCS simulation (storm tide, waves, wind and rivers) whose storm tide we use at our ocean boundary
(Cialone et al. 2015), or added rain and rivers for a single bay or city. Our aim: one fast model of the New
Jersey coast that runs all the drivers together, checked against what Sandy left behind, and then used to ask
which of today's power assets the same storm would flood. **To our knowledge, the first hindcast of Sandy
across the New Jersey coast that runs storm tide, waves (including infragravity), wind, rain and rivers
together and checks the result against both USGS high-water marks and FEMA's mapped flood extent.**

### Methods bullets (beside Fig 1 and the setup table)

- **High-water marks:** 119 USGS marks (McCallum et al. 2013). Model value = median peak water level of flooded
  ground within 50 m of each mark, on the 3.125 m flood map.
- **Flood extent:** FEMA MOTF Sandy surge extent (FEMA 2012), New Jersey land, 15 m cells; flooded = peak
  depth ≥ 0.15 m; CSI, POD, FAR from the rain-off twin, because FEMA mapped the surge.
- **Today's ground:** the same 2012 storm on post-2012 elevation and channel surveys with today's levees and
  tide gates; a site floods at ≥ 0.15 m on site.

### Conclusions / Future work

1. **Compound matters.** Waves, rain and rivers change peak water by tens of centimetres in the back bays and up the rivers.
2. **Checked against what Sandy left behind:** 119 high-water marks within 0.35 m; FEMA's extent, CSI 0.82 (rain off). Good enough to ask "what floods" at the scale of a single substation.
3. **Today's coast is not 2012's.** 52 of the 182 sites the model covers flood on today's ground, vs 60 on 2012's.

Future work: Model 2.0 with the Hudson waterfront and the Upper Bay · finer inlets in Cape May, where the back
bays read ~0.2 m low · future sea levels and other storms on today's ground · MHHW + 2 ft and + 4 ft maps for
the climate hazard team.

### References (only what the repo's own files confirm; [verify] = detail not confirmed there)

- Blake, E.S., Kimberlain, T.B., Berg, R.J., Cangialosi, J.P., Beven, J.L. II (2013). Tropical Cyclone Report: Hurricane Sandy (AL182012). NOAA National Hurricane Center. (`reports/literature_review_2026-10/A_river_boundaries.md` #33)
- Cialone, M.A., et al. (2015). NACCS Coastal Storm Model Simulations: Waves and Water Levels. USACE ERDC/CHL TR-15-14. (`…/B_wave_setup_without_a_solver.md` #21)
- Copernicus Climate Change Service (C3S). ERA5 hourly data on single levels. doi:10.24381/cds.adbb2d47. (`docs/MODEL.md` data table)
- Eilander, D., et al. (2023). A globally applicable framework for compound flood hazard modeling. NHESS 23, 823–846. doi:10.5194/nhess-23-823-2023. (`…/A_river_boundaries.md` #7)
- FEMA Modeling Task Force (MOTF) (2012). Hurricane Sandy storm-surge extent, final field-verified (11 Nov 2012). (`scripts/download_sandy_motf_extent.py`)
- Leijnse, T.W.B., et al. (2021). Coastal Engineering 163, 103796. doi:10.1016/j.coastaleng.2020.103796. [verify title] (`…/A_river_boundaries.md`, abstract-only)
- McCallum et al. (2013). USGS Open-File Report 2013-1043 (Hurricane Sandy storm-tide data). [verify title, authors] (`…/B_wave_setup_without_a_solver.md` #42)
- Roelvink, D., et al. (2025). SnapWave: fast, implicit wave transformation from offshore to nearshore. GMD 18, 9469–9495. doi:10.5194/gmd-18-9469-2025. (`…/C_snapwave_in_practice.md`)
- Suro, T.P., Deetz, A., Hearn, P. (2016). Documentation and hydrologic analysis of Hurricane Sandy in New Jersey, October 29–30, 2012. USGS SIR 2016-5085. doi:10.3133/sir20165085. (`…/A_river_boundaries.md` #32)

---

## Poster v3 changes (2026-11-13: "what are the sites?", one figure fewer, explain what we show)

v2 is kept as `poster_draft_2026-11-13_v2.pptx`. Figures renumbered: **Fig 1 = model map + HWM inset
(`fig1_model_hwm.png`, script `fig1_model_hwm.py`), Fig 2 = FEMA extent (`fig3_motf.png`), Fig 3 = power
plants and substations (`fig4_power_2026bed.png`).** Wherever "sites" stood alone in the abstract, takeaway 3
and the Fig 3 caption, it now reads "power plants and substations".

NACCS in the Introduction stays "(storm tide, waves, wind and rivers)": `lit_check.md` row 1 quotes the NACCS
report, "River inflow and wave forcing were also included in the validation simulations", and its verdict
says NACCS "already had surge, tide, waves with setup, wind and rivers".

**Fig 1 caption.** *The model and its check against high-water marks.* (a) The model grid, shaded by cell size
(25–200 m: finest along shores and channels). Storm tide enters along the orange ocean boundary; 61 rivers flow
in at the green triangles; 46 water-level gauges inside the model; 119 USGS high-water marks (pink). (b) Model
peak water vs each high-water mark (Model 1.1.0, rain on); grey band = within ±0.5 m. The few large misses are
marks behind coastal lakes (Deal Lake, Wreck Pond) whose outlets the model's ground holds shut; without those
five, RMSE is 0.24 m (n = 114).

**Fig 3 caption** (was Fig 4). *If Sandy hit today (preliminary).* Sandy's 2012 storm on today's ground and
defences (Elizabeth, Rahway, Port Monmouth, and the Pews Creek gate). Orange: power plants and substations that
flood; rings: the ten that change from 2012 ground (nine go dry, one goes wet). The 2026 ground is not yet
validated; buildings and land cover are still 2012's; sea level is Sandy's. 71 of the 253 power plants and
substations in the region sit at the model's edge and are not computed.

**Methods bullets (shortened; the plain explanation moved to Results).**
- Marks: median peak water of flooded ground within 50 m of each mark, on the 3.125 m flood map (Model 1.1.0, rain on).
- Extent: model flooded = peak depth ≥ 0.15 m; 15 m cells, New Jersey land only; scored on the rain-off twin of Model 1.1.0.

**What the figures show** (Results box).
- **High-water marks (Fig 1b):** water and debris lines USGS surveyed after Sandy; 119 are scored, each against
  the model's peak water level at that spot.
- **FEMA's surge map (Fig 2):** FEMA's mapped extent of Sandy's surge flooding in New Jersey (MOTF). CSI = overlap
  of the two flooded areas (1 = perfect); POD = share of FEMA's flooded land the model also floods; FAR = share of
  the model's flooded land that FEMA saw dry.
- **The sites (Fig 3):** New Jersey's electric power plants and substations (outlines from OpenStreetMap): 253 in
  the region, 182 inside the model. A site "floods" when Sandy's peak water stands ≥ 0.15 m deep on it.
- **Today's ground (Fig 3):** the same 2012 storm re-run on an estimate of 2026 ground: post-2012 elevation and
  channel surveys plus today's levees and tide gates (Elizabeth, Rahway, Port Monmouth, Pews Creek). Sea level
  and buildings as in 2012; preliminary.

Headline box: "52 of 182 — power plants & substations flood on today's ground (60 on 2012's)".

---

## Poster v4 (2026-11-13): NJ-SFINCS reframe, rain-on scores, FIAT placeholder

Follows `poster_review_2026-11-13.md` (incl. its addendum) and the user's decisions. v3 is kept as
`poster_draft_2026-11-13_v3.pptx`. **This section supersedes every earlier section where they differ.** Red
"[ … ]" on the poster = stubs to fill.

**Title.** NJ-SFINCS: A compound flood model for coastal New Jersey for power-grid and community risk

**Authors.** Tyler P. Janoski¹, **Nithila Darmeshwaran¹** (presenting; bold), James B. Shope¹, Robert Mieth²,
Terence Ahn³ — ¹Department of Environmental Sciences, ²Department of Industrial and Systems Engineering,
³Department of Electrical and Computer Engineering, Rutgers University

**Abstract** (submitted text; 0.36 → 0.35 m, "(60 of 182)", "about 30 … (still-water estimate)").
Coastal flooding in New Jersey often comes from multiple sources, including storm surge, waves, rainfall, and
river flow. Here, we present NJ-SFINCS, a high-resolution compound flood model for the New Jersey coast, built
on the computationally efficient SFINCS flood model. NJ-SFINCS covers the coast from the Verrazzano Narrows to
Cape May and extends up the Delaware Bay and River, with a maximum resolution of 25 m over a 3 m sub-grid
topography. We test the model using Hurricane Sandy (2012): simulated peak water levels have an RMSE of 0.35 m
relative to 119 USGS high-water marks, and NJ-SFINCS reproduces more than 86% of FEMA's mapped surge extent. We
also overlay present-day substations and power plants, finding that one-third of New Jersey assets in the domain
are flooded by Sandy's floodwater (60 of 182), while an estimated present-day coastline with 1.2 m of sea-level
rise alone would flood about 30 assets at high tide (still-water estimate). Additionally, we couple these flood
depths with an impact model to estimate damage to individual buildings, linking storm and sea-level rise
scenarios to neighborhood-scale impacts.

**Introduction.** New Jersey's coast floods from the ocean, the bays, the rivers and the sky, and Hurricane
Sandy (2012) showed what that costs homes and the power grid (Blake et al. 2013; Suro et al. 2016). Planning for
the next storm, and for higher seas, means running many "what if" cases, not one. Detailed coastal models are
accurate but slow, which limits how many cases can be run. SFINCS is a fast flood model that keeps the physics
that matters for flooding and has been used along other U.S. coasts (Leijnse et al. 2021). NJ-SFINCS brings it
to the whole New Jersey coast: a 72-hour storm on about 4 million cells runs in about 3 hours on one 64-core
computer, with surge, waves, rain and rivers all included. We check it against Hurricane Sandy, then use it to
ask which power plants, substations and buildings flood. **(red)** To our knowledge, NJ-SFINCS is the first
SFINCS model to cover the New Jersey coast as a whole, from the Narrows to Cape May and up Delaware Bay.

**Methods table:** Speed (bold, top) · Model "NJ-SFINCS (Model 1.1.0): SFINCS v2.3.3 (Leijnse et al. 2021), built
with HydroMT-SFINCS (Eilander et al. 2023)" · Grid · Storm tide (NACCS, Cialone et al. 2015) · Waves (SnapWave
incl. infragravity, Roelvink et al. 2025; CORA) · Wind, rain, rivers (NACCS winds + ERA5 (C3S); AORC; USGS at 61
inflows) · Impact model "Delft-FIAT (Deltares); [inventory]". (The "Storm" row was folded away for space.)

**Methods bullets.** Marks: median peak water of flooded ground within 50 m of each mark, on the 3 m flood map. ·
Extent: flooded = peak depth ≥ 0.15 m; 15 m cells; New Jersey land inside the model. CSI = overlap of the
model's and FEMA's flooded areas (1 = perfect). Both checks: Model 1.1.0, all forcing on. · Power sites: New
Jersey power plants and substations (OpenStreetMap outlines), 253 in the region, 182 inside the model; a site
floods when any part of it is under ≥ 0.15 m. · Today's ground: post-2012 elevation and channel surveys plus
today's levees and tide gates; sea level and buildings as in 2012.

**Figures.** Fig 1 = `fig1_model_fema.png` ((a) model grid / boundary / inflows / levees / gauges; (b) Model
1.1.0 RAIN-ON flood extent vs FEMA, insets A 0.70, B 0.87, C 0.69, CSI 0.80 / POD 0.87 / FAR 0.09, self-check
vs the row OK). Fig 2 = `fig2_hwm.png` (re-rendered with 16 pt legend). Fig 3 = `fig3_power_compact.png` (today's
ground, 2012 in brackets, rings = 10 changes; Newark Bay inset dropped). Fig 4 = dashed Delft-FIAT placeholder.

**Captions.** Fig 1. NJ-SFINCS and its Sandy flood extent. (a) The model grid by cell size, the ocean boundary
where storm tide enters, 61 river inflows, levees and 46 water-level gauges. (b) Peak flood extent vs FEMA's
mapped Sandy surge, New Jersey land only (FEMA's map stops at the state line); insets A–C at full 15 m with their
local CSI. · Fig 2. Peak water at Sandy's high-water marks. Each point is one USGS mark, coloured by region; grey
band = within ±0.5 m. Without the five marks behind Deal Lake and Wreck Pond, whose outlets the model's ground
holds shut, RMSE is 0.24 m (n = 114). · Fig 3. Power plants and substations that flood in Sandy, today's ground
(2012 ground in brackets). Preliminary; rings mark the ten sites that change. · Fig 4. Building damage from
Sandy's flood depths (Delft-FIAT). [caption: preliminary; flood map used]

**Results tiles (one row).** ~3 hours per 72-hour storm on one 64-core computer · 0.35 m RMSE at 119
high-water marks · > 86 % of FEMA's mapped surge extent reproduced · 60 of 182 power plants & substations flood
in Sandy (52 on today's ground, preliminary) · [FIAT number] [what it counts]

**Results bullets** (review addendum 1, 2, 4, 5, 6, 7 + stub; bullet 3, the lake marks, lives in the Fig 2
caption; bullet 5 carries the rain-off CSI instead of the Fig 1 caption).
1. Fast. A 72-hour storm on 3.97 million cells runs in about 3 hours on one 64-core computer (2.5 h measured on
   64 cores for the previous version, same grid and forcing; 4.1 h on 32 cores for this one).
2. Peak water levels match the marks. RMSE 0.35 m and bias −0.07 m at 119 USGS high-water marks; 93 % are within
   ±0.5 m (Fig 2).
3. The model reproduces 87 % of FEMA's mapped surge extent: 1,201 of 1,385 km² (CSI 0.80, FAR 0.09; Fig 1b).
4. Most false alarms are rain, not surge. 71 of the 113 km² the model floods and FEMA does not are rain ponds with
   no path to the sea; FEMA mapped surge only (without rain, CSI 0.82).
5. One-third of the power sites flood in Sandy: 60 of the 182 New Jersey power plants and substations the model
   covers (34 plants, 26 substations).
6. On today's ground and flood defences, 52 of 182 flood (preliminary; ten sites change, nine of them to dry;
   Fig 3). With no storm at all, 1.2 m of sea-level rise puts about 30 in water at high tide (still-water
   estimate on an earlier estimate of today's ground).
7. [FIAT finding + number]

**Conclusions.** 1. NJ-SFINCS is fast. A 72-hour storm on about 4 million cells runs in about 3 hours on one
computer, so dozens of storm and sea-level cases are practical. 2. It reproduces Sandy. Peak water within 0.35 m
(RMSE) at 119 high-water marks, and more than 86 % of FEMA's mapped surge extent. 3. It turns floods into risk.
One-third of the power plants and substations it covers flood in Sandy (60 of 182; 52 on today's ground and
defences), and the same depths feed building-by-building damage estimates. [add the impact number]

**Future work.** More storms and sea-level-rise cases on today's ground; 1.2 m of sea-level rise alone already
puts about 30 power sites in water at high tide (still-water estimate, preliminary). · Building-level damage for
each scenario with the impact model. · Model 2.0: add the Hudson waterfront and the Upper Bay. · Finer inlets in
Cape May, where the back bays read about 0.2 m low.

**References** (9; the two former [verify] entries replaced by the review's web-checked citations):
- Leijnse, T., van Ormondt, M., Nederhoff, K., van Dongeren, A. (2021). Modeling compound flooding in coastal
  systems using a computationally efficient reduced-physics solver. Coastal Engineering 163, 103796.
  doi:10.1016/j.coastaleng.2020.103796. (Subtitle after the colon dropped: not confirmed.)
- McCallum, B.E., Wicklein, S., Reiser, R.G., Busciolano, R., Morrison, J., Verdi, R.J., Painter, J.A., Frantz,
  E.R., Gotvald, A.J. (2013). Monitoring storm tide and flooding from Hurricane Sandy along the Atlantic coast of
  the United States, October 2012. USGS Open-File Report 2013-1043. doi:10.3133/ofr20131043. (Author ORDER: copy
  from pubs.usgs.gov/publication/ofr20131043 to be sure.)
- Unchanged: Blake 2013; Cialone 2015; C3S ERA5; Eilander 2023; FEMA MOTF 2012; Roelvink 2025; Suro 2016.

Cut in v4 (review §4 "cut" list): the old title; "Compound matters … tens of centimetres"; the "first hindcast" and
"Earlier Sandy models…" paragraphs; "Building on the USACE NACCS…" in the abstract; every "(rain off)"; the
MHHW-for-the-climate-team bullet; "What the figures show".

### v5 (2026-11-13): Fig 1b insets

Inset C is now **Atlantic City** (Absecon Island, 74.475–74.405 W, 39.337–39.383 N; local CSI 0.77, read from the
rain-on class raster), replacing Cape May. Insets A 0.70 and B 0.87 are unchanged, and so are all the scores. Fig 1 caption now ends:
"…insets A–C (Newark Bay, Barnegat Bay, Atlantic City) at full 15 m with their local CSI. FEMA's map ends abruptly
around Jersey City and Bayonne, so model flooding there scores as a false alarm." v4 is kept as `poster_draft_2026-11-13_v4.pptx`.

## Poster v6 (2026-11-13): de-cluttered (body text 1,147 → 869 words incl. headings, tiles and red stubs)

v5 kept as `poster_draft_2026-11-13_v5.pptx`. Supersedes v4/v5 text where different.

**Abstract (3 sentences).** We present NJ-SFINCS, a high-resolution compound flood model for the New Jersey coast,
built on the computationally efficient SFINCS flood model: it covers the coast from the Verrazzano Narrows to Cape
May and extends up the Delaware Bay and River, with a maximum resolution of 25 m over a 3 m sub-grid topography. We
test the model using Hurricane Sandy (2012): simulated peak water levels have an RMSE of 0.35 m relative to 119
USGS high-water marks, and NJ-SFINCS reproduces more than 86% of FEMA's mapped surge extent. Overlaying present-day
substations and power plants, we find that one-third of New Jersey assets in the domain are flooded by Sandy's
floodwater (60 of 182), while 1.2 m of sea-level rise alone would flood about 30 at high tide (still-water
estimate); we also couple these flood depths with an impact model to estimate damage to individual buildings.

**Methods table (5 rows).** Speed · Model · Grid ("~4 million cells, 25–200 m; 3 m subgrid ground; building
footprints; levees") · Forcing ("storm tide: USACE NACCS (Cialone et al. 2015); waves: SnapWave (Roelvink et al.
2025); wind: NACCS / ERA5; rain: NOAA AORC; rivers: USGS, 61 inflows") · Impact model ("Delft-FIAT (Deltares);
[inventory]"). **Methods lines:** "Flooded = peak depth ≥ 0.15 m; a power site floods if any part of it does." /
"CSI = overlap of the model's and FEMA's flooded areas (1 = perfect); marks scored as the median peak water within
50 m." ("Today's ground" is now defined once, in the Fig 3 caption.)

**Results bullets (3).** Most false alarms are rain ponds, not surge: 71 of the 113 km² have no path to the sea, and
FEMA mapped surge only (without rain, CSI 0.82). · On today's ground and defences, 52 of 182 flood, vs 60 on 2012
ground (preliminary; nine small sites go dry, one goes wet; Fig 3). · [FIAT finding + number]

**Captions.** Fig 1: (a) The model: grid cell size, ocean boundary, river inflows, levees and gauges. (b) Peak flood
extent vs FEMA's mapped Sandy surge, New Jersey land only; insets at full 15 m with their local CSI. The orange rows
in C are building footprints, which the model treats as solid blocks. FEMA's map ends abruptly around Jersey City
and Bayonne, so model flooding there scores as a false alarm. · Fig 2: One point per USGS mark, coloured by region;
grey band = within ±0.5 m. Without five marks behind Deal Lake and Wreck Pond, whose outlets the model's ground
holds shut, RMSE is 0.24 m (n = 114). · Fig 3: Power plants and substations that flood in Sandy on today's ground
(2012 ground in brackets; preliminary): post-2012 elevation and channel surveys plus today's levees and tide gates,
with sea level and buildings as in 2012. Rings mark the ten sites that change; B = Newark Bay.

**Conclusions.** 1. NJ-SFINCS is fast. A 72-hour storm runs in about 3 hours on one computer, so dozens of storm and
sea-level cases are practical. 2. It reproduces Sandy: 0.35 m RMSE at 119 high-water marks, and more than 86 % of
FEMA's mapped surge extent. 3. It turns floods into risk: one-third of the power plants and substations it covers
flood in Sandy, and the same depths feed building-level damage estimates. [add the impact number]
**Future work:** More storms and sea-level-rise cases on today's ground · Building-level damage for each scenario
with the impact model · Model 2.0: add the Hudson waterfront and the Upper Bay · Finer inlets in Cape May, where the
back bays read about 0.2 m low.

`fig3_power_compact.py` now draws the Newark Bay inset (panel B) beside the state map; printed 16.0 × 7.2 in.

## Poster v7 (2026-11-13): two experiments, no stat tiles, figures in reading order

v6 kept as `poster_draft_2026-11-13_v6.pptx`. Supersedes earlier sections where different. Layout: left column =
Abstract (v6 text), Introduction (shortened), Methods (table + two experiment paragraphs); right = "Results 1: Sandy
test case" (Fig 1, Fig 2, findings), "Results 2: Power grid and buildings" (Fig 3, Fig 4 placeholder, findings),
then Conclusions / Future Work and References side by side. The stat tiles are gone.

**Introduction.** New Jersey's coast floods from the ocean, the bays, the rivers and the sky, and Hurricane Sandy
(2012) showed what that costs homes and the power grid (Blake et al. 2013; Suro et al. 2016). Planning for the next
storm and for higher seas means running many "what if" cases, and detailed coastal models are too slow for that.
SFINCS is a fast flood model that keeps the physics that matters for flooding (Leijnse et al. 2021). NJ-SFINCS
brings it to the whole New Jersey coast, with surge, waves, rain and rivers all included. We check it against
Hurricane Sandy, then use it to ask which power plants, substations and buildings flood. **(red)** To our
knowledge, NJ-SFINCS is the first SFINCS model to cover the New Jersey coast as a whole, from the Narrows to Cape
May and up Delaware Bay.

**Methods table:** Model (NJ-SFINCS 1.1.0: SFINCS v2.3.3 (Leijnse et al. 2021) via HydroMT-SFINCS (Eilander et al.
2023)) · Grid · Forcing · Speed (about 3 hours per 72-hour storm on one 64-core computer) · Impact model
(Delft-FIAT (Deltares); [inventory]).
**Experiment 1: Sandy test.** Sandy (28–31 Oct 2012) on 2012 ground, all forcing on. Scored against 119 USGS
high-water marks (median model peak water within 50 m of each mark) and FEMA's mapped surge extent on New Jersey
land (flooded = peak depth ≥ 0.15 m; CSI = overlap of the two flooded areas, 1 = perfect).
**Experiment 2: power grid and buildings.** Today's New Jersey power plants and substations (OpenStreetMap outlines;
182 inside the model) in three cases: Sandy on 2012 ground; Sandy on today's ground (post-2012 elevation surveys,
levees and tide gates; 2012 sea level and buildings); and 1.2 m of sea-level rise at high tide (still water). A
site floods if any part of it is under ≥ 0.15 m. Delft-FIAT turns the same depths into building damage.

**Results 1 findings.** High-water marks: NJ-SFINCS's peak water levels are within 0.35 m (RMSE; bias −0.07 m) of
119 USGS marks; 93 % of the marks within ±0.5 m (Fig 2). · FEMA's surge map: NJ-SFINCS floods more than 86 % of
the New Jersey land FEMA mapped as flooded by Sandy's surge (CSI 0.80, FAR 0.09; Fig 1b). · False alarms: 71 of
the 113 km² the model floods and FEMA does not are rain ponds cut off from the sea; without rain, CSI is 0.82.
**Fig 1.** NJ-SFINCS and its Sandy flood extent. (a) The model grid and its inputs. (b) Peak flood extent vs
FEMA's mapped surge, New Jersey land only; insets at full 15 m with local CSI. Orange rows in C are building
footprints, which the model treats as solid blocks. FEMA's map ends abruptly around Jersey City and Bayonne, so
model flooding there scores as a false alarm. **Fig 2.** Peak water at Sandy's high-water marks; grey band =
±0.5 m. The big misses are five marks behind Deal Lake and Wreck Pond, whose outlets the model holds shut (RMSE
0.24 m without them).

**Results 2 findings.** Sandy on 2012 ground: 60 of the 182 New Jersey power plants and substations in the model
flood (34 plants, 26 substations). · Sandy on today's ground and defences (preliminary): 52 of the 182 flood; nine
small sites go dry and one goes wet (Fig 3). · 1.2 m of sea-level rise, no storm: about 30 of the 182 sit in water
at high tide (still-water estimate, preliminary). · [FIAT finding + number]
**Fig 3.** New Jersey power plants and substations in Sandy on today's ground (preliminary; counts on 2012 ground
in brackets). Rings: the ten sites that change. B = Newark Bay. **Fig 4.** Building damage from Sandy's flood
depths (Delft-FIAT). [caption: preliminary; flood map used]

**Conclusions.** 1. NJ-SFINCS is fast: a 72-hour storm in about 3 hours on one computer makes dozens of cases
practical. 2. It reproduces Sandy (Experiment 1): 0.35 m RMSE at the marks; more than 86 % of FEMA's surge
extent. 3. It turns floods into risk (Experiment 2): one-third of New Jersey's power plants and substations in the
model flood in Sandy, and the same depths feed building damage estimates. [add the impact number]
**Future work:** more storms and sea-level-rise cases on today's ground; building damage for each scenario;
Model 2.0 with the Hudson waterfront and the Upper Bay; finer Cape May inlets, where the back bays read about
0.2 m low.

## Poster v8 (2026-11-13): Fig 3 water layer on Fig 1b's definition

v7 kept as `poster_draft_2026-11-13_v7.pptx`; the old Fig 3 PNG/PDF as `fig3_power_compact_v6.*`. Fig 3's blue layer
is now peak depth ≥ 0.15 m on the native 3.125 m floodmap, all land inside the model, open water = bed ≤ 0 m
(`fig3_wet_layer.py` → `/scratch/tpj8/poster_2026-11-13/fig3/<domain>__<arm>__wet15.tif`), legend "Sandy's flood
extent (≥ 0.15 m)". Self-check on 2012 ground vs Fig 1b's class raster (scored NJ area 4,845 km²): model wet 1,307.7
vs 1,314.6 km² (−0.5 %), cell agreement 99.93 %. Asset dots and counts unchanged. Fig 3 caption gains "Blue: flood
extent as in Fig 1b."

## Poster v9 (2026-11-13): user's Introduction; today's-ground asset results only

v8 kept as `poster_draft_2026-11-13_v8.pptx`; old Fig 3 as `fig3_power_compact_v8.*`. No 2012-ground asset numbers
anywhere (the asset list is today's). Fig 3: 2012 counts and "changes vs 2012" rings removed.

**Introduction** (user, verbatim) + red bold line "NJ-SFINCS is the first SFINCS model to cover the New Jersey coast
as a whole, from the Narrows to Cape May and up Delaware Bay."
**Abstract:** "…we find that nearly one-third of New Jersey assets in the domain (52 of 182) would flood if Sandy
struck today's coast, while 1.2 m of sea-level rise alone…" (rest unchanged).
**Experiment 2:** two cases (Sandy on today's ground and defences; 1.2 m SLR at high tide, still water) + Delft-FIAT.
**Results 2** (recomputed from `exposure/v11_modernb_2026bed_assets.csv`, NJ, 182 computed):
- Sandy on today's ground and defences (preliminary): 52 of the 182 New Jersey power plants and substations in the
  model flood (≥ 0.15 m on any part of the site); 26 of them have water over at least half their ground.
- Newark Bay: half of the flooded sites (26 of 52) are in Hudson, Bergen, Union and Essex counties.
- Substations and big plants: 23 of the 27 flooded substations are high-voltage (230 kV and above). Four large
  gas-fired plants on the Hackensack, Arthur Kill and Raritan (Kearny, Linden, Sewaren, Sayreville) have water over
  two-thirds or more of their ground (68–87 %), a median 1.3–2.2 m deep. [Sewaren is 68 %, so "more than 80 %" was
  not true for all four.]
- 1.2 m of sea-level rise, no storm: about 30 of the 182 sit in water at high tide (still-water estimate, preliminary).
- [FIAT finding + number]
**Fig 3 caption:** New Jersey power plants and substations in Sandy on today's ground (preliminary): a site counts as
flooded if any part has ≥ 0.15 m; blue = flood extent as in Fig 1b. B = Newark Bay.
**Conclusion 3:** It turns floods into risk (Experiment 2): nearly one-third of New Jersey's power plants and
substations in the model (52 of 182) would flood if Sandy struck today's coast, and the same depths feed building
damage estimates. [add the impact number]

## Poster v10 changes (2026-11-14; `build_v10.py` on v9, v9 kept in `drafts/`)

- **Results 1** (now 26 pt, as Results 2), two bullets added (`logs/poster_diagnostics_2026-11-13/README.md`):
  - **Tide gauges:** at 40 gauges, Newark Bay to Cape May and up the Delaware to Philadelphia, the peak is within
    0.25 m at 85 % (RMSE 0.23 m, 0.10 m low), timed to about half an hour. (40 = the fair set: 46 placed minus 3 dead
    before the crest and 3 that read the forcing.)
  - **Waves matter:** without them the peak drops about 0.2 m on the ocean coast, at the inlets and in the NJ back
    bays; the error at the marks grows from 0.35 to 0.53 m (0.24 to 0.30 m without the five lake marks, where waves
    wash over the beach). (Job 63895426, median 50 m, n 119 / 114 `_excl_lake_blocked`, native 3.125 m; user 11-14:
    quote both, since the five Deal Lake / Wreck Pond marks carry most of the all-mark gain.)
- **SLR count "about 30 (still water, first 2026 ground)" → 22** of the 182 on a typical high tide: the + 4 ft
  (1.22 m) tidal run's mean higher-high, on today's ground estimate (`_subgrid_modern2026b`, Model 1.1.0 domain), 15
  plants / 7 substations, 3 with ≥ half their land wet (`logs/slr_assets_2026-11-13/results/v11modernb_tidal4ft_mhh_summary.txt`).
  Changed in the Abstract, Methods (Experiment 2) and Results 2.
- Not done: the hydrograph panel (no room without shrinking Fig 1); the FIAT box and its red stubs are unchanged.
- ⚠️ The waves-off twin (`p4-nowaves`) also lacks the Elizabeth / Rahway levees (Overpeck-only weir file), so the
  waves pair differs by the levees too (found 11-14, FINDINGS part 4 (n)). The levees alone leave the 119-mark RMSE
  unchanged (0.355 vs 0.355, `logs/v1_1_read_2026-11-06/READ.md`), and the waves effect sits on the open coast,
  inlets and NJ back bays, far from them (rivers / Newark Bay group Δ −0.007). The bullet stands as written.
