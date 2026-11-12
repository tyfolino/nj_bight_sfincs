# Poster text: DRAFT (2026-11-12, for the Rutgers climate poster, 11-13)

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
93 % within half a metre) and matches 80 % of FEMA's mapped surge extent (critical success
index 0.80). We then re-ran Sandy on today's ground, with post-2012 elevation surveys and
flood defences, and asked which of today's electric substations and power plants it would
flood: [N] of [M] New Jersey assets. [one-sentence result from fig 4]

## Figure captions

**Fig 1. The model.** The model grid, shaded by cell size (25–200 m: finest along shores and
channels). Storm tide enters along the orange ocean boundary; 61 rivers flow in at the green
triangles. Checked against 46 tide gauges inside the model and 119 USGS high-water marks
(pink).

**Fig 2. Peak water at Sandy's high-water marks.** Each point is one USGS high-water mark
(quality excellent or good). The model value is the median peak water level of flooded ground
within 50 m of the mark, on the 3.125 m flood map. Grey band = within ±0.5 m. The few large
misses are marks behind coastal lakes (Deal Lake, Wreck Pond) whose outlets the model's ground
holds shut; without those five, RMSE is 0.24 m (n = 114).

**Fig 3. Flood extent vs FEMA's mapped Sandy surge.** Blue: both flooded; orange: FEMA flooded,
model dry; pink: model flooded, FEMA dry. Scored on New Jersey land only (FEMA's map stops at
the state line). [Rain-off run: CSI / POD / FAR from tonight's figure; the stand-in, with rain
on, reads 0.80 / 0.87 / 0.09.] Rain is switched off for this comparison because FEMA mapped the
surge, and rain ponding inland would otherwise count as false alarms.

**Fig 4. If Sandy hit today.** Sandy's 2012 storm (same tide, winds, waves, rain and rivers) on
today's ground: post-2012 elevation and channel surveys, today's levees and tide gates
(Elizabeth, Rahway, Port Monmouth). Substations and power plants that flood are in [colour].
Preliminary: the 2026 ground is new and not yet validated, and building footprints and land
cover are still 2012's. Sea level is Sandy's, so this isolates what the changed ground and
defences do. [Counts: wet / dry / outside the model, 2012 vs today.]

## Three takeaways

1. **Compound matters.** Surge alone does not explain Sandy's flooding. Waves, rain and rivers
   change peak water by tens of centimetres in the back bays and up the rivers.
   [Optional: a number from the waves-on vs waves-off pair, e.g. the wavemaker's effect on the
   open-coast marks.]
2. **It is checked against what Sandy left behind:** 119 high-water marks, within 0.35 m, and
   FEMA's mapped extent, CSI 0.80. Good enough to ask "what floods" at the scale of a single
   substation.
3. **Today's coast is not 2012's.** New levees, gates, dunes and dredged channels change where
   the same storm would go. [Fig 4 result.] Next: future sea level and other storms on
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
cells, finishes in **about 2.5 hours on one 64-core node** (about 5.4 h on 16 cores). Waves-off variants run in under
2 h. That is what lets us run dozens of what-if tests (bed fixes, levees, gates, today's ground, sea-level offsets) in
a week.

Comparison claim: SFINCS's reduced physics reaches accuracy similar to Delft3D at roughly **two orders of magnitude**
less compute. Source: Leijnse's 2018 TU Delft thesis (Hurricane Irma, Jacksonville):
https://repository.tudelft.nl/record/uuid:53037d4d-d7a9-4f71-9b22-8c329f2b384c . The 2021 SFINCS paper
(Leijnse et al., Coastal Engineering, doi 10.1016/j.coastaleng.2020.103796) positions it between bathtub models and
Delft3D / XBeach. Check its full text for a runtime number before quoting "100×" from the paper rather than the thesis.
Poster wording (safe): "A 72-hour storm on 4 million cells runs in ~2.5 hours on a single compute node: fast enough
to test dozens of scenarios, where full hydrodynamic models such as Delft3D typically take one to two orders of
magnitude longer."

## Methods box (if there is room)

- SFINCS v2.3.3 (Deltares), built with HydroMT-SFINCS; subgrid tables on a 3.125 m ground model.
- 72-hour run, 28–31 Oct 2012; about 2.5 h on 64 cores.
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
