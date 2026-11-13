# Can we say "one of the first"? A literature check for the poster and abstract (2026-11-12)

This extends `reports/literature_review_2026-10.md`, which covered rivers, wave setup and SnapWave,
not priority. Read status is given per source in the table: FULL / PARTIAL means text was read;
ABSTRACT means only an abstract or a search-engine summary was seen. Anything marked
**unverified** has not been checked against the source.

## Verdict

"One of the first Sandy hindcasts" is **not defensible**. Sandy has been hindcast in New York and New
Jersey at least 15 times since 2014, including a whole-coast USACE run (NACCS) that already had surge,
tide, waves with setup, wind and rivers. **What is defensible** is a hedged "to our knowledge, the first"
for a specific combination:

- New Jersey coast scale;
- all five drivers in one model (storm tide, waves with setup and IG, wind, rain, rivers);
- scored against both USGS HWMs and the FEMA MOTF extent.

Nothing found has all three. Each one on its own has been done before.

## Phrasings, from boldest-but-true to safe

**A. Boldest. Needs "to our knowledge".**
> "To our knowledge, the first Hurricane Sandy hindcast to model New Jersey's Atlantic shore, back
> bays, Delaware Bay and the Raritan–Newark Bay estuary in one model with all five flood drivers —
> storm tide, waves (including wave setup and infragravity waves), wind, rainfall and river flow — and
> to check it against both USGS high-water marks and FEMA's mapped surge extent."

**B. Medium. Contrasts us with earlier work instead of claiming a first.**
> "Earlier Sandy models covered the whole coast with surge and waves only (USACE NACCS, NWS SLOSH), or
> modelled one bay or city in detail. This model puts all five drivers into one state-scale model at
> street-scale resolution (25 m cells, 3 m subgrid terrain, building footprints, levees)."

You can attach "one of the first" to this one ("one of the first state-scale compound-flood
hindcasts of Sandy"). It is true in spirit: only a handful of Sandy studies include rain and rivers,
and all of them are local (Saleh 2017, Muñoz 2022, Goulart 2024).

**C. Safe. Makes no priority claim.**
> "A state-scale compound-flood hindcast of Hurricane Sandy for New Jersey that combines storm tide,
> waves, wind, rain and rivers. It matches 119 USGS high-water marks with an RMSE of 0.35 m and FEMA's
> surge extent with a CSI of 0.80."

For the numbers, use the estimator the repo uses (median, 50 m radius) from `docs/MODEL.md` §5:
RMSE 0.35 m, bias −0.07 m, n 119 (median within 50 m, native 3.125 m floodmap, re-scored 11-12); CSI 0.80 (1.1.0 rain on; NJ only, inside the validity mask; the rain-off figure lands tonight). The 0.355 / 0.795 in older docs are the 6.25 m-map scores.

### Wording traps, whichever phrasing you pick

- **Say "New Jersey coast", not "the whole state" or "entire coast".** The Hudson waterfront (Hoboken,
  east Jersey City) and the Upper Bay shore are **not computed** (`docs/MODEL.md` §4). The Delaware
  and other rivers are cut at head of tide. A Stevens reviewer would notice: their street-scale Hudson
  waterfront model (Blumberg 2015) covers exactly that gap.
- **Don't call the HWMs and the MOTF extent independent checks.** FEMA built the MOTF extent by
  interpolating USGS HWMs and sensor readings onto lidar terrain (as described in Liu et al. 2020 §2).
  "Checked against both" is fine; "two independent datasets" is not.
- **Don't claim the most marks or the best fit.** SLOSH compared 268 Sandy HWMs (95 in NJ), and Grimley
  2025 compared 763 for Florence. Liu 2020 reports NJ-coast RMSE 0.379 m and NYC 0.134 m, on different
  marks and estimators, so the scores cannot be compared.
- **IG waves in SFINCS are not new.** Leijnse et al. 2025 ran SFINCS + SnapWave + IG with rain and
  rivers for Florence along 950 km of the Carolinas. Our "first" is about Sandy and New Jersey, not the
  method.
- **Credit NACCS.** It is our ocean forcing and the earlier whole-coast multi-driver Sandy run. "Builds
  on the USACE NACCS storm-tide hindcast" is accurate and disarms the obvious objection.

## The closest prior work

Drivers: **T** = tide + surge, **Wv** = waves with setup (radiation stress), **IG** = infragravity,
**Wd** = wind / pressure, **R** = rain on the domain, **Q** = river inflow.

| # | Study | DOI / link | Model | Drivers | Extent | Finest resolution | Validation | Read |
|---|---|---|---|---|---|---|---|---|
| — | **This model (v1.1.0)** | `docs/MODEL.md` | SFINCS v2.3.3 + SnapWave + wavemaker | T Wv IG Wd R(+CN infiltration) Q(61) | NJ Atlantic shore + back bays, Delaware Bay + tidal river, Raritan, Newark Bay, Arthur Kill; far banks computed; Hudson waterfront NOT | 25 m cells, 3.125 m subgrid, building footprints, levees as weirs | 119 USGS HWMs RMSE 0.355 m (median, 50 m); MOTF CSI 0.795 (NJ) | — |
| 1 | Cialone et al. 2015 (NACCS) ERDC/CHL TR-15-14; Cialone et al. 2017 *JWPCOE* 143(5) | https://usace.contentdm.oclc.org/digital/collection/p266001coll1/id/3681/ ; doi:10.1061/(ASCE)WW.1943-5460.0000408 | ADCIRC + STWAVE (two-way) + WAM | T Wv Wd Q ("River inflow and wave forcing were also included in the validation simulations"); no R, no IG | Virginia → Maine, all of NJ + Delaware Bay | ADCIRC 3.1 M nodes, 70–200 m at NJ inlets; STWAVE 200 m | Historical storms incl. Sandy at gauges + buoys; **HWM statistics unverified** (DTIC 403); no extent score seen | PARTIAL (2026-10 review, ch. 3, 6–8) |
| 2 | Forbes et al. 2014, *JMSE* 2:437 | doi:10.3390/jmse2020437 | SLOSH (+ tides), ny3 basin | T Wd; no Wv, R, Q | NY Bight basin (NY/NJ/CT); other basins run, ny3 reported | 213 m | 268 USGS HWMs (95 NJ): 72 % within 20 %, 89 % within 30 % relative error; plus 145 USGS sensors and NOAA gauges | FULL (text extracted) |
| 3 | Liu et al. 2020, *ECSS* 233:106544 | doi:10.1016/j.ecss.2019.106544 (OSTI accepted manuscript) | SCHISM 3D + WWMIII → ELCIRC-Sub | T Wv Wd, Hudson flux; no R | Mid-Atlantic Bight; inundation NYC + NJ Hudson side | 200 m cells + 5 m subgrid | 80 non-wave-affected HWMs (NYC RMSE 0.134 m; NJ coast RMSE 0.379 m); **80 % hit rate vs FEMA MOTF extent** | PARTIAL |
| 4 | Wang et al. 2014, *JMSE* 2:226 | doi:10.3390/jmse2010226 ; arXiv:1412.0966 | SELFE + subgrid | T Wd | NYC | subgrid lidar | Compared to the USGS Sandy mapper (timing, extent, depth); 11 NJ marks (search summary) | ABSTRACT |
| 5 | Blumberg et al. 2015, *JTECH* 32:1486 | doi:10.1175/JTECH-D-14-00213.1 | sECOM nested in NYHOPS | T Wd Q (NYHOPS); no Wv / R in the summary | NJ Hudson waterfront | 3.1 m | 56 water marks (R² 0.92) + 16 edge marks (extent within ~20 m) | ABSTRACT |
| 6 | Stevens Barnegat Bay inundation model (Blumberg et al. 2014, cited in a township report) | https://cms6.revize.com/revize/berkeleynj/document_center/commission/Waterways/stevens%20report.pdf | sECOM nested in NYHOPS | T Wd Q | Barnegat Bay | 100 m | 6 USGS gauges; 71 % of HWMs within 0.63 ft (1 s.d.) | ABSTRACT (grey lit.) |
| 7 | Ding et al. 2014 (U. Mississippi NCCHE for NJIT / NJDEP), *Sandy Baseline Model* | https://www.nj.gov/dep/docs/flood/final-studies/njit-moonachie/njit-njdep-fmerc-finalrpt-appendixc-06182014.pdf | CCHE2D-Coast | T Wv Wd (regional); Q (Passaic, Hackensack) in the local model | US East Coast grid (1.0 M nodes), focus on NE New Jersey (Hackensack / Moonachie) | local grid < 1 m | NOAA gauges + NDBC buoys; USGS HWMs on the NY + NJ coasts, R² 0.729 (count not seen) | PARTIAL (grey lit.) |
| 8 | Saleh et al. 2017, *Adv. Water Resour.* 110:371 | doi:10.1016/j.advwatres.2017.10.026 | NYHOPS + hydrologic model + HEC-RAS 2D | T R(runoff) Q; ensemble (GEFS) | Passaic / Hackensack / Newark Bay | not seen | Inundation extent vs the USGS Sandy reanalysis (bracketed by the 50th–95th percentile) | ABSTRACT |
| 9 | Muñoz et al. 2022, *Coastal Eng.* 171:104057 | doi:10.1016/j.coastaleng.2021.104057 | Delft3D-FM + EnKF data assimilation | T (ADCIRC boundary) Wd R (ERA5) Q (5 gauges); no Wv | Delaware Bay, DE + NJ shores | 20 m urban, 1.4 km offshore | Gauges + **13** Sandy HWMs | FULL (sections) |
| 10 | Bakhtyar et al. 2020, *JGR Oceans* 125 | doi:10.1029/2019JC015822 | NWM + D-Flow FM / HEC-RAS + ADCIRC + WW3 | T Wd Q (NWM), waves in the ADCIRC/WW3 ocean part; **unverified** whether rain or waves reach the estuary model | Delaware River basin / estuary | not seen | Gauges, skill 0.79–0.91 (Isabel, Irene, Sandy); HWMs / extent not seen | ABSTRACT |
| 11 | Colle et al. 2015, *JMSE* 3:428 | doi:10.3390/jmse3020428 | WRF-ADCIRC (± SWAN) ensemble | T Wd (Wv tested) | NY Harbor / NYC | not seen | Gauges; inundation mapped by bathtub on ~1 m lidar | PARTIAL |
| 12 | Yin, Lin & Yu 2016, *WRR* 52:8685 | doi:10.1002/2016WR019102 | ADCIRC + FloodMap | T Wd | NYC | < 5 m | FEMA HWMs + planar-method extent (counts not seen) | ABSTRACT |
| 13 | Kress et al. 2016, *JCR* SI 76 | doi:10.2112/SI76-013 | ADCIRC + SWAN | T Wv Wd | Staten Island | not seen | Storm-tide observations | ABSTRACT |
| 14 | Hatzikyriakou & Lin 2017, *Nat. Hazards* | doi:10.1007/s11069-017-3001-5 | ADCIRC + SWAN + BOUSS1D | T Wv Wd | Ortley Beach, NJ | not seen | Building damage survey (HWM use not seen) | ABSTRACT |
| 15 | Qu et al. 2021, *Nat. Hazards* 105:2697 | doi:10.1007/s11069-020-04420-y | FVCOM-SWAVE | T Wv Wd | Mid-Atlantic Bight, NY/NJ bridges | not seen | Coastal stations | ABSTRACT |
| 16 | Defne, Ganju & Moriarty 2019, *JGR Oceans* | doi:10.1029/2019JC015238 ; data doi:10.5066/P99K85SW | COAWST (ROMS + SWAN) | T Wv Wd | Barnegat Bay–Little Egg Harbor | not seen | not seen | ABSTRACT (2026-10 review) |
| 17 | Goulart et al. 2024, *NHESS* 24:29 | doi:10.5194/nhess-24-29-2024 | GTSM → SFINCS | T (GTSM) R; no Wv, no Q | NYC metro incl. parts of NJ | 50 m | **No flood validation**: only the storm meteorology was compared to IBTrACS | PARTIAL |
| 18 | Sarhadi et al. 2024, *BAMS* 105:E337 | doi:10.1175/BAMS-D-23-0177.1 | Synthetic TCs → surge + rain flood models | T R | NYC | not seen | Not seen; probabilistic, Sandy-level return periods | ABSTRACT |
| 19 | Orton et al. 2016, *JGR Oceans* 121:8904 | doi:10.1002/2016JC011679 | sECOM (NYHOPS) | T Wd Q | NY Harbor | not seen | Hazard curves vs historical data | ABSTRACT |
| 20 | **Leijnse et al. 2025**, *Coastal Eng.* 199:104726 (Florence, not Sandy) | https://www.sciencedirect.com/science/article/pii/S0378383925000316 (DOI presumably 10.1016/j.coastaleng.2025.104726 by Elsevier's pattern; not printed in the PDF, so **unverified**) | SFINCS + SnapWave + IG | T (GTSM) Wv IG Wd R (NLDAS) Q (NWM): **all five** | 950 km of the Carolinas coast | 25 m at the coast, 200 m on land, no subgrid tables | 4 NOAA time series + 70 USGS sensors used as HWMs; no extent score seen | FULL (local `refs/`) |
| 21 | **Grimley et al. 2025**, *WRR* (Florence, not Sandy) | doi:10.1029/2023WR036727 | ADCIRC → SFINCS | T Wd R (MRMS) Q; no Wv | NC + SC, state scale | 200 m cells, 5 m subgrid | 89 gauges + **763 HWMs** + insured-damage records; POD / CSI defined | FULL (local `refs/`) |
| 22 | Nederhoff et al. 2024, *Nat. Hazards* 120:8779 (USGS CoSMoS-SEUS) | DOI not re-checked (per the 2026-10 review) | SFINCS | T Q (NWM), parametric wave setup | US SE Atlantic, not NJ | 200 m cells, 1 m subgrid | (2026-10 review) | 2026-10 review |

**New Jersey statewide tools are not hindcasts.**

- NJFloodMapper (Rutgers / JCNERR): a static total-water-level map, i.e. tide + sea-level rise + an
  event height on lidar terrain. https://mosaic.njaes.rutgers.edu/njfloodmapper
- USGS New Jersey coastal flood-inundation maps: made from the FEMA Region II ADCIRC + SWAN synthetic
  storm library, not a Sandy hindcast.
  https://www.usgs.gov/centers/new-jersey-water-science-center/science/new-jersey-coastal-flood-inundation-mapping
- Rutgers Barnegat Bay mitigation report (Guo et al. 2014, for NJDEP): uses FEMA still-water
  elevation (SWEL) grids, not a Sandy hindcast.
  https://www.nj.gov/dep/docs/flood/final-studies/rutgers-barnegat/barnegat-bay-study-area-flood-mitigation-final-report.pdf

No SFINCS model of New Jersey turned up in any search. **Correction (2026-11-13): wrong.** The 11-13 poster review (`poster_review_2026-11-13.md` §3, beside this file) found published SFINCS models inside New Jersey: Amini, Marsooli, Orton, Kasaei & Hajj (2026), *Urban Climate* 65, 102771, doi:10.1016/j.uclim.2026.102771 (Hoboken, 1.5 m); Maduwantha, Wahl, Santamaria-Aguilar, Jane, Dangendorf, Kim & Villarini (2026), *HESS* 30, 401–420, doi:10.5194/hess-30-401-2026 (Gloucester City, tidal Delaware); and Goulart et al. (2024, row 17) covers NYC metro "including parts of New Jersey". What still holds is the SCALE: no SFINCS model of the New Jersey coast as a whole was found. Poster v4 wording: "To our knowledge, NJ-SFINCS is the first SFINCS model to cover the New Jersey coast as a whole, from the Narrows to Cape May and up Delaware Bay." (The two 2026 papers are not cited on the poster.)

### What the table says

- **Whole NJ coast, multi-driver, Sandy:** only NACCS (#1). It has no rain, no IG, and is coarser
  (70–200 m). Its Sandy validation is at gauges; HWM numbers are not verified.
- **Sandy with rain and/or rivers ("compound"):** #8 Saleh, #9 Muñoz, #17 Goulart, #18 Sarhadi. All are
  local (one bay or city), none has waves, and only #9 scored HWMs (13 of them).
- **Sandy against both HWMs and the FEMA extent:** #3 Liu 2020 (80 HWMs + 80 % hit rate, NYC). Probably
  also #5 Blumberg (marks + edge marks) and #12 Yin (FEMA marks + planar extent). All are city-scale.
- **All five drivers including IG in SFINCS at regional scale:** #20 Leijnse 2025, for Florence in the
  Carolinas.

## What would falsify each phrasing

**A** is wrong if any one Sandy hindcast covers the NJ Atlantic shore and Delaware Bay and Raritan /
Newark Bay, has waves and rain and rivers, and is scored against HWMs and an extent. Places to look:

- **NACCS TR-15-14 §6.7 and the 2017 JWPCOE paper.** The likeliest falsifier on drivers and extent.
  Unread because DTIC and ASCE returned 403. A rain forcing or an extent score there would kill A.
  I found no sign of either.
- **USACE NJ Back Bays study (ERDC TR-25-18, 2025)** and its feasibility appendices
  (nap.usace.army.mil returned 403 in October). The ADCIRC runs were made without waves.
- **A FEMA Region II Sandy validation run** (ADCIRC + SWAN, NJ + NYC). None found.
- **Stevens NYHOPS / Stevens Flood Advisory System retrospective Sandy forecasts.** These cover the NJ
  coast with rivers, and were checked against sensors, HWMs and reanalysis extent per a 2018 AMS
  abstract. A paper showing statewide overland inundation with waves and rain would weaken A.
  Not found.
- **The Bakhtyar 2020 full text (#10).** If its D-Flow FM got rain on the grid and wave forcing, it is a
  five-driver Sandy model, but for Delaware only, so A would still stand on extent.
- **Conference abstracts** (AGU, AMS, ASCE, Coastal Sediments) and **USGS / Deltares grey literature**
  were not searched exhaustively. An unpublished SFINCS NJ model is the most plausible unknown.

**B** is wrong if several state-scale five-driver Sandy hindcasts already exist (none found), or if
NACCS's resolution at the shoreline is comparable to 25 m (it is 70–200 m at NJ inlets, so no).

**C** makes no priority claim, so only our own numbers can falsify it. Quote the estimator (median,
50 m) and the mark file (1.x, n 119) with them: another estimator changes the RMSE and can flip the bias.

## Not verified (do not quote)

- NACCS Sandy HWM count and statistics, and its finest mesh spacing outside NJ inlets.
- Ding et al. 2014: the HWM count behind R² 0.729, and whether its waves were coupled.
- Bakhtyar 2020: whether waves or rain reach the D-Flow FM estuary model.
- Marsooli & Lin 2018 (*JGR Oceans* 123:3844, doi:10.1029/2017JC013434): whether Sandy is among its
  1988–2015 storms, and whether it maps inundation. It was not used above.
- Georgas et al. 2014 (*J. Extreme Events*, doi:10.1142/S2345737614500067, seen only as a reference in
  Colle 2015): the domain and validation of its NYHOPS Sandy hindcast.
- Hatzikyriakou & Lin 2017 and Kress et al. 2016: their HWM use.
