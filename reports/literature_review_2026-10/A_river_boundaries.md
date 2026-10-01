> **Appendix to [../literature_review_2026-10.md](../literature_review_2026-10.md)** — the research notes as written on 2026-09-30, kept for their verbatim quotes, page numbers and read-status tags. Paths to scratch extracts (`*.txt`, `up/`, `gh/`) did not survive the session; the sources are cited in full at the end.

# Literature review A — where compound-flood modellers end their rivers, and what they put there

Prepared 2026-09-30 for the `nj_bight_sfincs` v4 design question (cut rivers at gauge / head of tide vs. whole watersheds vs. a middle path). Research only; nothing in the repo was touched.

## How this was done (read this before trusting a quote)

- PDFs were downloaded and converted to text with `pypdf`; every quote below was copied from that text, not remembered. PDF ligatures (ﬂ, ﬁ) are written as "fl", "fi". Page numbers are **PDF page numbers** ("PDF p.N"), not journal page numbers, unless marked otherwise.
- Status tags: **FULL TEXT READ** = whole paper read. **PARTIAL (…)** = the full text was open and I read the sections named plus a keyword search of the rest. **ABSTRACT ONLY** = only the publisher abstract (via Crossref, OpenAlex or Semantic Scholar) was available.
- Blocked: AGU/Wiley PDFs (HTTP 403), ScienceDirect (403), NOAA IR through curl (Akamai), ResearchGate, ADS, ESSOAr and DTIC. So several key AGU papers are ABSTRACT ONLY. They are marked, and nothing is claimed for them beyond the abstract.
- 38 sources were opened. 31 had full text available and were read (1 in full, 30 in the sections named); 7 were abstract only. Section (d) lists what could not be verified.

---

## (a) Comparison table

Key: **WL** = water level. **Q** = discharge. **HoT** = head of tide. **SLR** = sea-level rise. **"Same domain for SLR"** means the authors ran SLR scenarios on the present-day domain without moving any boundary.

| # | Study (model, grid) | Area | Where rivers end, and why | What is imposed there | Ungauged tributaries | River bed where no survey | SLR handling | Read status |
|---|---|---|---|---|---|---|---|---|
| 1 | **Grimley et al. 2025 WRR** — SFINCS 200 m, 5 m subgrid, 1.95 M cells | Carolinas, 5 HUC6 basins, 78,007 km² | Watersheds are modelled whole, **but cut just below large reservoirs** ("SFINCS cannot directly represent reservoir management"). The Upper Pee Dee enters as a gauge inflow. Outflow cells are placed where inter-basin flow can occur | 9 USGS 15-min gauge hydrographs at the "upstream boundary"; ADCIRC WL at ~−15 m | Rain-on-grid with Curve Number infiltration (baseflow neglected, which the authors flag) | NC: HEC-RAS TINs, plus the maximum cross-section depth burned as a 5 m-wide rectangle. SC: DEM −2 m inside NHD Area polygons | Not in this paper (see #2) | FULL TEXT READ (paper + SI) |
| 2 | **Grimley et al. 2024 npj Nat. Hazards** — the same SFINCS model | Carolinas, ~77,600 km² | Same as #1: inflows "just downstream of managed reservoirs" | 9 USGS gauges (6 for Floyd) | Rain-on-grid | As in #1 | SLR (mean 1.12 m) added to the ADCIRC WL; **same domain for SLR**. Compound zone "moving upriver" | PARTIAL (methods, results, discussion) |
| 3 | **Nederhoff et al. 2024 Nat. Hazards** — SFINCS 200 m, 1 m subgrid, 5 overlapping domains | US SE Atlantic, FL–VA | Landward extent "manually determined to allow for minimal inflow boundary locations", typically +10 m NAVD88, ~100 km inland | NWM retrospective Q at 74 point sources; projected Q from a precipitation regression | Rain-on-grid + Curve Number | Not described (the tidal underestimate is blamed on 200 m resolution and land roughness in channels) | 0–3 m SLR on the **same +10 m domain** | PARTIAL (methods, validation, discussion) |
| 4 | **Leijnse et al. 2025 Coastal Eng.** — SFINCS+SnapWave quadtree, 25–200 m, 5 M cells, no subgrid | Carolinas coast | Same domain logic as #3, but quoted as "typically reaches +20 m+NAVD88" (#3 says +10 m) | NWM retrospective Q | Rain (NLDAS); no infiltration | Not described | None | PARTIAL (setup §2) |
| 5 | **Goulart et al. 2024 NHESS** — SFINCS 50 m | NYC, Sandy storylines | No river inflow is described; forcing is rain plus GTSM WL | — | Rain-on-grid (GCN250 infiltration) | Not described | SLR +71 / +101 cm on the same domain | PARTIAL (methods, discussion) |
| 6 | **Sebastian et al. 2021 Nat. Hazards** — SFINCS 25 m, 4.09 M cells | Houston, Harvey | Domain = one HUC-8 watershed. Rivers enter at **reservoir outlets** (Addicks, Barker, Lake Houston) | Observed reservoir releases as point inflows; Morgan's Point WL | Rain-on-grid | Channels "burned into the DEM", manual fixes at bridges | None | PARTIAL (setup, limitations) |
| 7 | **Eilander et al. 2023a NHESS** — SFINCS 100 m (global framework, HydroMT) | Sofala, Mozambique | Domain = cells hydrologically connected to the two basins. **Inflow points where rivers ≥100 km² and ≥10 km long cross the domain edge**; zero-depth outflow cells where rivers leave | CaMa-Flood Q, matched by upstream area | Rain-on-grid | Burned rectangle: width from GRWL / Lin et al., bank from a low HAND percentile, depth h = 0.27 Q^0.30 (Andreadis) | None | PARTIAL (§3.2, sensitivity, discussion) |
| 8 | **Eilander et al. 2023b NHESS** — same framework, 100 m | Sofala | As #7 | Q at "locations where the Buzi and Pungwe rivers enter the model domain" | Rain | Bed from a gradually-varied-flow solver (Neal et al. 2021) | None | PARTIAL (setup, discussion) |
| 9 | **Ye et al. 2021 NHESS** — SCHISM 3D creek-to-ocean, 2.2 M nodes, ~1 m finest | NC/SC, Florence | **Land boundary at the +10 m NAVD88 contour**, "deemed sufficient to capture most backwater effects" | NWM Q at 6,752 points where NWM reaches cross the 10 m contour | Rain-on-mesh inside the domain; no infiltration | NWM thalwegs built into the mesh; "CUDEM may underestimate the depth of coastal streams" | None | PARTIAL (setup, results §5, conclusions) |
| 10 | **Zhang et al. 2020 Ocean Dyn.** — SCHISM | Delaware Bay/River, Irene | 10 m above MSL, **except the Delaware, extended to the Riegelsville gauge (~40 m)**. The head of tide is a bedrock "weir" ~2.7 km below the Trenton gauge | NWM Q at the 10 m contour intersections | NWM + optional rain | DEM only; uncertainty above Trenton (Stockton ~1 m high) | None, but surge **backwater reached the 10 m boundary** | PARTIAL (§1, §3, §4, conclusions) |
| 11 | **STOFS-3D-Atlantic (NOAA)** — SCHISM, 8 m river resolution | US Atlantic/Gulf | Land boundary at the 10 m contour (above xGEOID20B) | NWM + Canadian gauges | NWM | ≥3 nodes across each river | Operational; n/a | PARTIAL (AWS registry page) |
| 12 | **Yin et al. 2021 JAWRA** — D-Flow FM 2D, 6 m–1.2 km | Delaware Estuary, Isabel | Mouth to **Trenton, the head of tide** | NWM Q at 11 inputs "along the boundary"; ADCIRC at the ocean | NWM (Noah-MP infiltration outside the domain) | Not described | None | PARTIAL (accepted ms, §1–2) |
| 13 | **Bakhtyar et al. 2020 JGR Oceans** — NWM → HEC-RAS 1D or D-Flow FM 1D/2D → ADCIRC/WW3 | Delaware basin; Isabel, Irene, **Sandy** | Not verifiable from the abstract (a 1D link between NWM and ADCIRC) | NWM Q | NWM | 1D HEC-RAS geometry | None | ABSTRACT ONLY |
| 14 | **Xiao et al. 2021 Front. Mar. Sci.** — FVCOM | Delaware; Isabel, Irene, Lee, **Sandy** | ~240 km up from the mouth (the tidal limit is ~2.7 km below Trenton); floodplain cut at +3 m MSL | "River flows collected at 23 USGS river gauges" (PDF p.4) | Only gauged inputs | Not described | None | PARTIAL (§2–3) |
| 15 | **Deb et al. 2025 Sci. Data** — DHSVM (90 m) → FVCOM | Delaware Bay/River, 1980–2019 | ~215 km up to the "river flow boundary" near Trenton; floodplain edge +3 m NAVD88 | DHSVM Q for **13 streams with p99.5 Q > 100 m³/s only** | Dropped (to keep the time step) | — | Historical sea-level trend only | PARTIAL (setup) |
| 16 | **Sun et al. (preprint) "Mapping Philadelphia's Floodscape"** — DHSVM → FVCOM → RIFT 10 m | Philadelphia HUC12 | RIFT domain is one HUC12; Schuylkill forced from DHSVM; Fairmount Dam is the tidal barrier | DHSVM Q + FVCOM WL | DHSVM | 3DEP + CUDEM with the dam "burned" | — | PARTIAL (§2) |
| 17 | **Santamaria-Aguilar et al. 2026 NHESS / Maduwantha et al. 2026 HESS** — SFINCS 10 m / 1 m subgrid, GPU | Gloucester City NJ | Domain = the HUC-14s of two ungauged creeks; **inland edges = outflow**; WL on the Delaware from the Philadelphia gauge | Philadelphia tide-gauge WL | Rain-on-grid (no infiltration) | CoNED as is; creek depth "limited", which likely over-deepens creek margins | Stochastic mean sea level, no SLR domain change | PARTIAL (setup, limitations) |
| 18 | **Bilskie & Hagen 2018 GRL** — ADCIRC+SWAN | Lake Maurepas/Amite, LA | Mesh fixed. Rainfall excess entered as an **initial condition** from FEMA depth grids, not as inflow | — | — | — | Mentioned as future work | PARTIAL (§3–5) |
| 19 | **Bilskie et al. 2021 Front. Water** — ADCIRC rain-on-mesh, 1.45 M vertices | Barataria, Maurepas | **Northern mesh boundary = Interstate-10**; the Amite is inserted up to I-10 at ~40 m resolution; gauge inflow at Denham Springs (at I-10) | USGS Q | Rain-on-mesh inside only (27% of the Maurepas basin is inside) | Amite channel "depths of 4 m NAVD88" | None | PARTIAL (setup, validation, limitations) |
| 20 | **Santiago-Collazo et al. 2021 Front. Clim.** — the same ADCIRC framework | Same LA basins, 1890–2090 eras | Same I-10 boundary for all eras | — | Rain-on-mesh | — | SLR eras on the **same mesh extent**; the transition zone "cannot extend further inland" | PARTIAL (setup, SLR results) |
| 21 | **Loveland et al. 2021 Front. Clim.** — ADCIRC (9.2 M elements) vs HEC-RAS 2D | Neches/Sabine, Harvey | Inflow "as far upstream … as possible but where there is still high enough mesh refinement", set by a sensitivity test; HEC-RAS domain starts at the Salt Water Barrier gauge | USGS Q at the gauge (HEC-HMS as fallback) | — | Trapezoidal channel burned below the water surface | None | PARTIAL (§2–3 results) |
| 22 | **Orton et al. 2020 Nat. Hazards** — sECOM (NYHOPS grid) | Hudson, NYC to Troy | Tidal Hudson to the **Federal Dam at Troy** (HoT at a lock/spillway) | Gauged Q; TC hydrographs from a Bayesian model for 5 tributaries | **52 inputs; ungauged ones scaled from similar-sized gauged watersheds by area** | — | SLR superposed; upriver SLR effect damped by 30–60% | PARTIAL (§2–3, §5) |
| 23 | **Orton et al. 2012 JGR Oceans** — NYHOPS | NYC estuaries, Irene | — | — | — | — | — | ABSTRACT ONLY |
| 24 | **Kumbier et al. 2018 NHESS** — Delft3D 25 m | Shoalhaven, AU | **Tidal limit at Burrier, "where the bathymetric data coverage ends"**; dam Q shifted 25 km downstream | Dam Q, rating extrapolated past the instrument limit | — | Survey only | None | PARTIAL (setup, results) |
| 25 | **Harrison et al. 2022 Estuaries & Coasts** — CAESAR-Lisflood <50 m | Humber, Dyfi, UK | DEM **trimmed at river gauges** (Humber: far above the tidal limit) | Gauge Q | — | **Constant −3 m ODN bed burned; "glass walls" along banks** where the bed is unknown | SLR scenarios, same domain | PARTIAL (setup, abstract) |
| 26 | **Lyddon et al. 2024 NHESS** — CAESAR-Lisflood | Conwy, UK | Just downstream of the Cwmlanerch gauge | Gauge Q | — | **Lidar-wrong bed hand-adjusted until 3 stage gauges matched** | Discussed | PARTIAL (§2.4) |
| 27 | **Bates et al. 2021 WRR (Fathom-US)** — LISFLOOD-FP 30 m | CONUS | Reach-by-reach domains; catchments ≥50 km² get fluvial boundaries | Regional flood-frequency Q + normal-depth outflow; coastal catchments use the coastal WL downstream | Rain-on-grid (IDF) | Large rivers burned; small rivers subgrid; depth from a 1D gradually-varied-flow solver | 2035/2050 | PARTIAL (§2) |
| 28 | **Muñoz et al. 2024 HESS** — Delft3D-FM / HEC-RAS | Galveston Bay, Harvey | 12 USGS gauges as upstream boundaries; Lake Houston dam flow = the sum of inflows to the lake | Gauge Q | — | — | — | PARTIAL (§1–2) |
| 29 | **FEMA Region II Storm Surge Project — Mesh Development (2014)** — ADCIRC | NJ/NY incl. Hudson to Troy | Inland extent from the **25-ft NAVD88 contour**; river arcs coarsened landward of the 15-ft contour | — | — | — | — | PARTIAL (§2.1, §4) |
| 30 | **Mita et al. 2023 Water** — HEC-RAS 1D-2D | Eastwick, Philadelphia | — | — | — | — | Under SLR, water enters "over a land area not presently included in some fluvial flood models" | ABSTRACT ONLY |

Process papers also used in the prose: Familkhalili et al. 2022 (analytical estuary model); Suro et al. 2016 (USGS, Sandy in NJ); NHC Sandy TCR (Blake et al. 2013); Jafarzadegan et al. 2023 (review); Green et al. 2025 (review); Tehranirad et al. 2020 (abstract); Neal et al. 2021 (abstract); Leijnse et al. 2021 (abstract); Santiago-Collazo et al. 2019 and 2024 (abstracts); Bao et al. 2024 (abstract); Deb et al. 2023 (abstract); the SFINCS manual; the HydroMT-SFINCS source.

---

## (b) Answers to questions 1–7

### Q1. Where does the river end?

The field uses about five rules, often combined. None of the papers I read chose the cut to match a future-water-level target the way v4 does ("where Sandy +3 m ends").

**1. An elevation contour, with rivers crossing it as point inflows.** This is the most common rule for large coastal domains.
- Nederhoff et al. 2024 (SFINCS): "The model landward extent was manually determined to allow for minimal inflow boundary locations and typically reaches + 10 m elevation relative to NAVD88" (PDF p.7), "about 100 km inland" (Fig. 1 caption, PDF p.4).
- Leijnse et al. 2025 describes the same domains as "typically reaches +20 m+NAVD88 (Nederhoff et al., 2024b)" (§2.4, PDF p.4). The two papers disagree on the number.
- Ye et al. 2021 (SCHISM): "the spatial domain's landward boundary is set at 10 m above the NAVD88 datum, which is deemed sufficient to capture most backwater effects (Zhang et al., 2020)" (§2, PDF p.2).
- STOFS-3D-Atlantic, NOAA's operational version: "the land boundary of the domain aligns with the 10-m contour above xGEOID20B" (AWS registry page).
- FEMA Region II ADCIRC mesh, which covers our NJ/NY area: "The inland extent of the ADCIRC mesh was developed from the 25-foot NAVD88 contour" (§2.1.1, PDF p.9). Wide valleys cut by the coarse boundary were added back: "If these areas were wider than 250 feet, the boundary was adjusted to include these areas" (PDF p.10).
- PNNL FVCOM Delaware models stop the floodplain much lower: "floodplain boundary of 3 m elevation above … NAVD88" (Deb et al. 2025, PDF p.5); "cut off at 3 m above the mean sea level" (Xiao et al. 2021, PDF p.4).

**2. The head of tide, or the first dam or spillway.**
- Yin et al. 2021 (D-Flow FM): the estuary "extends from the river mouth at Cape May all the way upstream to the head of the tide at Trenton" (PDF p.4); the mesh "extends from the estuary mouth all the way to Trenton" (PDF p.7).
- Deb et al. 2025 go "~215 km from the Delaware Bay mouth to the river flow boundary" (PDF p.5).
- Orton et al. 2020: the tidal Hudson "stretches 225 km from the Battery … to the Federal Dam at Troy … the head of tide at Troy is at a lock/spillway system" (PDF p.4).
- Kumbier et al. 2018: the grid "extended from the estuary's entrance … upstream to the tidal limit at Burrier, where the bathymetric data coverage ends" (PDF p.5). The data limit and the tidal limit coincided.
- Sun et al. (PNNL preprint) on the Schuylkill: "The dam acts as a barrier to tidal influence … two distinct hydrological regimes" (PDF p.4).

**3. A stream gauge.**
- Harrison et al. 2022: "The upper extent of the fluvial region of the Humber DEM was trimmed according to the river gauge stations" (PDF p.5). The Humber tidal limit is 147 km up the Trent, so these gauges sit well inland.
- Lyddon et al. 2024: the domain is "downstream of the Cwmlanerch river gauge" (PDF p.6).
- Loveland et al. 2021: the HEC-RAS domain starts at the Salt Water Barrier gauge. The ADCIRC inflow sits "as far upstream in the Neches River as possible but where there is still high enough mesh refinement to describe the river feature" (PDF p.4).
- Bilskie et al. 2021: the ADCIRC mesh stops at Interstate-10, where the Denham Springs gauge happens to sit: "The Amite River from Lake Maurepas to Interstate-10 (which is the northern mesh boundary)" (PDF p.4), with inflow "prescribed by USGS gage 07380120 located in Denham Springs (near Interstate 10)" (PDF p.9).

**4. Below the last regulating reservoir, with the watershed below it modelled whole.** This is what the North Carolina group did.
- Grimley et al. 2025 SI §S1: "SFINCS cannot directly represent reservoir management, so the upstream boundary of the model was placed downstream of large reservoirs."
- Grimley et al. 2024 npj: "These inflows are located just downstream of managed reservoirs" (PDF p.8).
- Sebastian et al. 2021 used the same rule for Houston: releases "modeled as point inflows to the model near the outlets of Addicks and Barker Dams, as well as near the outlet of Lake Houston" (PDF p.7).

**5. A hydrological unit boundary (a HUC) or drainage connectivity.**
- Sebastian et al. 2021: the mask "was derived using the USGS watershed delineation for the Buffalo-San Jacinto HUC-8" (PDF p.6).
- Santamaria-Aguilar et al. 2026: domain = the creeks' "14-digit hydrologic units" (PDF p.6).
- Eilander et al. 2023a: "Cells that are not connected to the Buzi or Pungwe floodplains and drain into adjacent basins are excluded from the model domain" (PDF p.5).

**Two clarifications about the "North Carolina group" (Grimley, Sebastian, Leijnse, Eilander, Luettich).**
- Their models are *not* whole watersheds to the divide. They are the parts of five HUC6 basins that lie below the big reservoirs. The Upper Pee Dee, which drains into the Lower Pee Dee, enters as a gauge inflow (WRR Fig. 1 caption: "The relative size of the Upper Pee Dee (UPD) basin which drains into the LPD is shown").
- The npj paper gives ~77.6 thousand km², 200 m cells and a 5 m subgrid; the WRR paper gives 78,007 km² and 1.95 M cells.

**Is the domain ever shaped by SLR?** I found no paper that set the river cut from a future water level. The 10 m contour rule (Ye, Zhang, STOFS) is justified by *present-day backwater reach*. Zhang et al. 2020 then show it was not quite enough (Q3).

### Q2. What is imposed at the upstream boundary?

**Gauge discharge at the gauge.** Used by Grimley 2024/2025 (9 USGS gauges below reservoirs), Loveland 2021, Bilskie 2021, Kumbier 2018, Harrison 2022, Lyddon 2024 and Muñoz 2024 (12 USGS gauges). Muñoz fills a missing gauge by mass balance: "due to the lack of available river-gauge stations located immediately downstream of Lake Houston dam, river flow … is estimated as the sum of upstream freshwater input to the lake" (PDF p.6).

**Gauge discharge moved or scaled to an ungauged cut.**
- Kumbier moved it: "the discharge measurements that originate from Tallowa dam were shifted approximately 25 km downstream to Burrier" (PDF p.5–6).
- Orton 2020 / NYHOPS scale by area: "ungaged or unmodeled small-to-medium tributaries (the remainder of a total of 52 Hudson River and NYH freshwater inputs to the model) are estimated using the standard NYHOPS system of estimating streamflows based on nearest similar-sized watersheds and scaled by watershed area" (PDF p.9). This is the closest published analogue to our scheme of gauges scaled to 61 sources, and it is the operational practice on our own harbour.

**A hydrological model supplying inflow.**
- NWM: Nederhoff 2024 (74 rivers), Leijnse 2025, Ye 2021 (6,752 points), Zhang 2020, Yin 2021 (11 inputs), Bakhtyar 2020.
- CaMa-Flood: Eilander 2023a, matching the source cell by "the smallest difference in the upstream area" within limits of "5 % and … 100 km²" (PDF p.8).
- DHSVM: Deb 2025 and Sun (preprint).
- HEC-HMS: Saleh 2017 (unverified), and Loveland 2021 as a fallback.
- Ye 2021 on the division of labour: "the river flows injected at the land boundary have indirectly incorporated the precipitation that occurred outside (but not inside) the model domain, and therefore, the addition of direct precipitation onto the model domain is appropriate" (PDF p.6).

**Rain-on-grid over the domain.** SFINCS studies (Grimley, Nederhoff, Sebastian, Eilander, Goulart, Santamaria-Aguilar) and ADCIRC rain-on-mesh (Bilskie 2021). Ungauged tributaries *inside* the domain are handled by rain-on-grid in all of these. Grimley notes a cost: "neglecting baseflow in the tributaries whose watersheds are fully contained within the model domain may also contribute to negative bias" (PDF p.12).

**Dropping small inputs deliberately.** Deb 2025 "picked 13 major streams with a 99.5th percentile of peak flow above 100 m³/s … Limiting the number of narrow streams that require much higher resolution helped increase the model external time-stepping" (PDF p.5).

**Reported data problems.**
- *Daily means only:* Orton 2020: "Where only daily data were available (typically prior to 1990), the USGS peak flow estimates for major flood events were inserted into the time series on the day of the peak, to avoid underestimating peak flows during the storms" (PDF p.9).
- *Rating / instrument limits:* Kumbier 2018: data "are subject to uncertainty during peak discharge, because the discharge volume was too high to be recorded … the device stopped recording at 2566 m³ s⁻¹", so the authors hand-modified the hydrograph until upstream stages matched (PDF p.4).
- *Rating and bathymetry mismatch:* Grimley SI, Fig. S3 caption: "The offset between the observed and modeled can stem from issues with bathymetry in SFINCS but error in the USGS stage-discharge rating curve."
- *Hydrological-model bias:* Nederhoff 2024 attribute a 91 cm HWM bias at riverine points (30 cm at coastal points) to "a difference in modeled (input) and actual precipitation and river discharge" (PDF p.19).

### Q3. Sensitivity to the upstream boundary and to river flow; the transition zone; Sandy

**Measured sensitivity to boundary position.** This is thin in the literature.
- Loveland 2021 ran "a sensitivity analysis … to determine the location of the internal time-dependent flux boundary conditions" and settled on "as far upstream … as possible but where there is still high enough mesh refinement" (PDF p.4). Only the rule is reported, not the magnitudes.
- Zhang 2020 is the clearest test of a *too-low* boundary. "despite that fact that we have placed the boundary at 10 m above sea level, the backwater effect can still propagate far upstream and reach the boundary of our study domain" (PDF p.2). But "The elevation differences are generally small in the watershed, about a few centimeters in most places for this event, although 10 s of centimeters or larger differences are also observed in isolated areas" (PDF p.18). On extending the domain instead: "this approach may be impractical, especially for flat plain areas where the backwater effect can propagate far inland" (PDF p.19).
- Santiago-Collazo et al. 2024 WRR (abstract only) propose a "moving coupling node approach". This shows the coupling point is treated as a research variable, not a settled choice.

**River on vs. off.**
- *Delaware, Irene (a very wet storm):* at the most upstream NOAA station "the storm-induced surge is smaller than that from the river flood" (Zhang 2020, PDF p.15). Rivers raise maximum levels mainly "upstream of Marcus Hook" (PDF p.15).
- *Delaware, Isabel:* rivers' contribution "is mainly restricted to the upper part of the estuary upstream of Schuylkill River" (Yin 2021, abstract).
- *Delaware, all storms:* Xiao 2021: "The transition zone of damping and enhancing effects shifted downstream as the river flow rate increased" (abstract, PDF p.1).
- *Shoalhaven:* peak WL at the coastal station "only varied by a few centimetres" with or without river flow, while flood extent without river would have been underestimated "by 30 %" (Kumbier 2018, PDF p.8 and abstract). The coastal gauge was insensitive but the upriver floodplain was not.
- *Neches/Sabine, Harvey:* "the simulation with riverine flow had much higher peak WSEs" (Loveland 2021, PDF p.9).
- *Hudson/NYC, Irene:* "Neglecting freshwater inputs to the model domain led to reductions of 2% at the Battery and 9% at Piermont, 14 km up the Hudson" (Orton 2012, abstract).
- *Humber, UK:* "extreme fluvial inputs during a compound hazard actually reduced maximum water depths in the outer estuary" and "Increased fluvial volumes were the weakest driver of estuarine flooding" (Harrison 2022, abstract).
- *Bakhtyar 2020 (Delaware incl. Sandy):* "hydrodynamic predictions, especially upstream, are highly dependent on the streamflow discharges" (abstract). I could not read which storm drove that result.

**The transition-zone concept and its upstream limit.**
- Bilskie & Hagen 2018 define zones from three runs: rain only (R), surge only (S), both (RS). "the transition zone is defined as ηR > ηS and ηRS > ηR … The coastal zone is defined as ηS > ηR and the hydrologic zone as ηR > ηS" (PDF p.7). So the upstream limit is where the rain-only peak equals the combined peak.
- Grimley 2025 use a 0.05 m threshold on the compound-vs-maximum-single difference. They note "The compound extent we identify might be slightly larger than the 'transition zone' which Bilskie and Hagen (2018) defines" (PDF p.5).
- Ye 2021 use an 80% "dominance" rule: "a factor is deemed dominant if it explains at least 80 % of the total disturbance" (PDF p.14).
- Familkhalili et al. 2022 give an analytical "crossover point, which we define as the location in which river flow effects on HTWL are larger than marine effects" (PDF p.16). "As a channel is deepened, this cross-over point moves progressively upstream" (abstract). This is the published mechanism by which SLR would pull the transition zone inland.
- All of these limits are **event-dependent**. None is a fixed geographic line.

**Sandy specifically.** No published modelling study was found that quantifies river-discharge sensitivity during Sandy on the Raritan, Passaic or Hackensack. What exists:
- *NJ overall (USGS Suro et al. 2016):* "the heavy rain did not cause major inland riverine flooding" (PDF p.16). "Although rainfall totals generally ranged from 2 to 5 inches across New Jersey, widespread river flooding was not documented" (PDF p.17). "Hurricane Irene produced major widespread flooding throughout New Jersey, whereas Hurricane Sandy produced extensive coastal storm-surge flooding and damage" (PDF p.30). Table 2 lists storm rainfall of **1.60 in at Bound Brook** (Raritan) and **1.33 in at Little Falls** (Passaic) (PDF p.20–21).
- *NHC TCR (Blake et al. 2013):* "Although this rain caused rivers in the mid-Atlantic region to rise, only minor damage was reported due to this flooding. Rainfall did contribute, along with storm surge, to the flooding in New York and New Jersey adjacent to the Hudson River" (PDF p.13).
- *Raritan:* "The surge into Raritan Bay forced water up the Raritan River that resulted in flooding in nearby Sayreville" (PDF p.17).
- *Passaic and Hackensack:* "sea water piled up within the Hudson River and the coastal waterways and wetlands of northeastern New Jersey, including Newark Bay, the Passaic and Hackensack Rivers, Kill Van Kull, and Arthur Kill" (PDF p.10).
- *Hudson:* flooding "due to storm surge (with some contribution from rainfall) … as far north as Albany" (PDF p.9). Sandy surge reached the Troy head of tide.
- *NYC:* "Most of the flooding was caused by a high storm surge, but inland precipitation also modestly contributed to the flooding" (Goulart et al. 2024, PDF p.2).
- *Delaware:* peak flow at Trenton during Sandy was "800 m³/s", against 4,000–5,500 m³/s for Irene and Lee (Xiao 2021, PDF p.6). Xiao validated the Sandy period with river forcing but reports no Sandy river-off run.
- *NHC, Delaware:* "the Delaware River swelled to record levels" (PDF p.16). This sits in the Virginia/Maryland/Delaware/Pennsylvania paragraph and does not separate surge from flow.
- *Passaic/Hackensack (Saleh et al. 2017):* by a search-engine summary of its abstract, it simulated Irene and Sandy "where coastal storm surge was the dominant component" for Sandy. **Not verified** (publisher abstract unavailable).

### Q4. Riverbed where there is no bathymetry

**What people actually do.**

1. *Power-law hydraulic geometry burned as a rectangle.*
   - Eilander 2023a: "The riverine depth h (m) is estimated from the bankfull discharge Q … h = aQ^b, where the default values for a (0.27) and b (0.30) are based on Andreadis et al. (2013)". Bankfull Q is the 2-year flow; the bank comes from "a low percentile of height above the nearest river" of neighbouring cells; the bed "is burned into the river center cells and spread … to burn a rectangular river profile" (PDF p.6).
   - The installed HydroMT-SFINCS 2.0.0-rc2 `burn_river_rect` does *not* estimate depth itself. It needs user-supplied `rivwth` and `rivdph`/`rivbed` and estimates the bank from a DEM quantile (`riv_bank_q`) (source docstring, `workflows/bathymetry.py`).
2. *Gradually-varied-flow (GVF) inversion.*
   - Neal et al. 2021 (abstract): uniform-flow methods "are only accurate for kinematic water surface profiles", while the GVF method "reduced model error compared to a target water surface profile by 66% and eliminated bias due to backwater effects". Used by Bates 2021 (Fathom-US) and Eilander 2023b.
   - Bates 2021 on why: using Manning's equation "fails to account for backwater effects … too much water can be transferred to floodplain sections" (PDF p.9).
3. *Lidar surface minus a constant.* Grimley 2025 in South Carolina: "2.0 m was subtracted from the CoNED and NED datasets in the major channels and estuaries using the NHD Area polygon" (SI). Tested at 1 m vs 2 m; 2 m "reduced peak errors the most".
4. *Constant bed elevation plus walls.* Harrison 2022 (Humber): "a constant river bed elevation of −3 m ODN was burnt into the DEM … 'Glass walls' were built along the banks of the rivers where the bathymetry was unknown thus channelling fluvial discharges directly to the estuary" (PDF p.5).
5. *Hand-calibrating the bed against stage gauges.* Lyddon 2024: "Initially the DEM had incorrect channel bed elevations due to the lidar shortcomings for inundated areas … We approximated the correct channel bathymetry by manually adjusting the channel bed elevations, re-running the simulation, and comparing simulated and observed water levels" (PDF p.6). **This is exactly the flat-lidar-water problem we have.**
6. *Borrowing 1D model geometry.* Grimley in North Carolina: "over 100 interpolated triangular irregular networks (TINs) from HEC-RAS models" (SI). Bakhtyar 2020 used a 1D HEC-RAS link.
7. *Burning a trapezoid or a fixed depth.* Loveland 2021: "An approximate trapezoidal channel … was burned into the terrain below the water surface" (PDF p.4). Bilskie 2021: the Amite was inserted "with a local resolution of ∼40 m and depths of 4 m NAVD88" (PDF p.4).
8. *Leaving the DEM as is.*
   - Ye 2021: "no manipulation or smoothing of bathymetry … CUDEM may underestimate the depth of coastal streams" (PDF p.5).
   - Zhang 2020 above Trenton: "the model uncertainty becomes larger, mainly due to the uncertainty in the DEM … computed surface elevation at this gauge [Stockton] is ~1 m higher than the observation" (PDF p.16).
   - Santamaria-Aguilar 2026: "The limited depth representation of creek channels … likely results in an overestimation of floodwater depths along the margins of the creeks" (PDF p.12).
9. *Stopping where bathymetry stops.* Kumbier 2018 (above).

**Measured sensitivity.**
- Grimley 2025: removing channels "increases the average peak error by 0.19 m" (PDF p.14). Constant-width rectangles over-convey at low flow, giving "low in-channel water levels" (PDF p.12). Resolution 200 m → 100 m cost ×8.5 runtime "without significantly improving the model performance" (SI Table S3).
- Eilander 2023a: skill "is not very sensitive to the river depth". In Table 5, river depth at 50% and 150% leaves SFINCS CSI unchanged (0.00) for both events; the largest change in any score is 0.04 (CaMa-Flood). The authors attribute this "to the extremeness of the fluvial driver … the river conveyance capacity was small compared to the total discharge" (PDF p.10).
- Eilander 2023b: "with a deeper estuary the transition zone … extends further inland, but this change is relatively small" (PDF p.11).
- Neal 2021 (abstract): uniform-flow channels produced a wet bias; GVF "reduced flood extents by 40%".
- Reading across these: channel depth matters most at **low-to-moderate flows**, which is our situation, and least in extreme overbank floods.

### Q5. The whole-watershed approach (Carolinas SFINCS, SCHISM creek-to-ocean)

**Grid and size.**
- Grimley: 200 m, 5 m subgrid, 1.95 M cells, 78,007 km² (PDF p.3).
- Nederhoff: 200 m, 1 m subgrid, 5 overlapping domains, ~100 km inland.
- Ye 2021: 2.2 M nodes, "river channels and creeks have about 300 m along-channel resolution", ~1 m finest (PDF p.5).

**Runtime.**
- Nederhoff: "a 7-day simulation … took about 41 min on a single core" (PDF p.13).
- Grimley: absolute runtime not reported; 100 m cost ×8.5.
- Ye 2021: "the real time to simulation time ratio is 80 with 1440 cores" (PDF p.6).
- Deb 2025 (FVCOM, 40 yr): "~1.1 × 10⁶ CPU hours" (PDF p.5).

**Rivers.** Subgrid plus burned channels (Grimley, Nederhoff); NWM thalwegs meshed explicitly (Ye). Grimley's reasoning: "Incorporating channels helps to route flow across watersheds, while neglecting to represent channels explicitly will displace flow into the floodplains, leading to an overestimate of peak inundation" (PDF p.12).

**Infiltration.** Curve Number with recovery (Grimley; Nederhoff; initial soil moisture tuned 75% vs 50%). None in Ye 2021, Leijnse 2025 or Santamaria-Aguilar 2026.

**Validation, inland vs coast.**
- Grimley: peak error 0.11 m, RMSE 0.92 m over 89 gauges and 763 HWMs, from 0 to 200 m NAVD88. Hydrograph bias −0.32 m, worse inland.
- Nederhoff: tide MAE ~8 cm and storm MAE ~12 cm at the coast, against a Florence HWM MAE of 63 cm; "the model error increased farther inland due to less well-resolved hydrological processes such as rainfall, infiltration, and riverine flow" (PDF p.29).
- Ye 2021: MAE "11 cm for coastal elevation and 72 cm for high water marks" (PDF p.15).
- The pattern holds in all three: coastal skill ≈ 0.1 m, inland ≈ 0.6–0.9 m.

**What the authors say it buys.**
- Attribution of rain-driven flooding. For Florence, runoff was 79.2% of flooded area, coastal 5.9% and compound 15.3% (PDF p.7). Compound processes were 31% of exposed buildings.
- Grimley: "summing the depths generated by the individual processes is not a substitution for simulating their interactions" (PDF p.14).
- Grimley 2024: compound flooding "moving upriver and beyond the existing floodplain" under warming and SLR (PDF p.5).
- The motivating storms were rain-dominated (Florence 254–913 mm, WRR PDF p.2). Sandy in NJ was 1.3–1.6 in at the Raritan and Passaic gauges (Suro 2016).

**Stated weaknesses.**
- Channel bathymetry is the main limit ("there remains very limited readily accessible information on data on river bathymetry", Grimley, PDF p.14).
- Rectangular constant-width channels bias low-flow stages low. Baseflow is neglected.
- Rating-curve error at inflows.
- "we did not explicitly account for streamflow obstructions, such as small weirs/dams or bridge piers" (PDF p.14).
- Reservoir operations cannot be represented, which is why the domain is cut below them.
- Ye: no infiltration or urban drainage.
- Nederhoff: groundwater and managed drainage are not included.

### Q6. Open or outflow landward edges

**SFINCS semantics.** The manual: "At outflow cells (msk=3), the water level is not forced, but water depth at that cell is artificially kept at zero (no water)." An outflow edge is therefore a perfect sink. It drains anything that reaches it and cannot reflect.

**Published practice.**
- Grimley SI §S1: "Where inter-basin flow might occur, outflow boundary cells – cells that allow water to drain from the model where it might otherwise unrealistically pool at the boundary – were designated … Outflow can occur when extreme water levels flow between watershed boundaries, especially in low-gradient areas at the coast."
- Eilander 2023a: "In the absence of water level forcing of rivers leaving the model domain … and to avoid water building up within the model domain, open boundary cells with a zero water depth are set" (PDF p.6). Default edges are closed walls.
- Gloucester City: "The inland boundaries of the model domain are defined as 'outflow' to allow any water flow to exit the domain" (NHESS PDF p.7).
- Nederhoff: "The five computational SFINCS domains overlap to overcome any possible boundary effects" (PDF p.10).
- Harrison 2022 did the opposite in the channel ("glass walls").
- Lyddon 2024 used a floodplain water-loss term "to avoid water accumulation behind flood defences" (PDF p.6).

**Artificial drainage or reflection.**
- None of the SFINCS papers quantify how much water the outflow cells remove.
- The only explicit reflection discussion is analytical. Familkhalili 2022 extended a channel "upstream for 100 km to enable the tide wave to dissipate and prevent reflection off an upstream boundary" (PDF p.3).
- Zhang 2020 is the only measurement of a closed-ish land boundary being reached by surge backwater (cm-scale, locally tens of cm).
- **This is a gap.** Nobody reports a leak budget like ours.

### Q7. Practice for SLR runs

**Everyone I could read ran SLR on the present-day domain.**
- Nederhoff (0–3 m on the +10 m domains).
- Grimley 2024 (mean +1.12 m).
- Goulart (+0.71 / +1.01 m).
- Harrison 2022.
- Orton 2020 (Hudson, head of tide fixed by the Troy dam).
- Santiago-Collazo 2021 (fixed I-10 mesh).
- **No paper moved a river boundary upstream for SLR.**

**Evidence that a fixed domain can bite under SLR.**
- Santiago-Collazo 2021: as the coastal zone grows, the transition zone must shrink "because it cannot extend further inland and gain area from the hydrologic flood zone" (PDF p.10). This is partly a statement about the fixed northern boundary.
- Mita et al. 2023 (abstract): under SLR "the coastal flood water enters Eastwick through a different pathway, over a land area not presently included in some fluvial flood models."
- Familkhalili 2022: deepening, and by extension SLR, moves the river/marine crossover "progressively upstream".
- Zhang 2020: present-day surge backwater already touches a 10 m boundary.

**Where the head of tide is structurally fixed, SLR cannot move it far.**
- Delaware: "An abrupt transition in bathymetry that resembles a weir is located ~2.7 km downstream of the Trenton gauge … roughly represents the head of tide, as the tides are effectively damped out a short distance (~0.5 km) upstream of the weir" (Zhang 2020, PDF p.16).
- Hudson: the Troy spillway (Orton 2020).
- Orton 2020 also show SLR is *damped* upriver: "a 30–60% mitigation of sea level rise" near Albany in wet storms, because a deeper channel conveys floodwater more easily (PDF p.24).

**How SLR-ready domains are sized.**
- By contour: +10 m (Nederhoff, Ye, STOFS), 25 ft (FEMA R2), and per the brief, CoSMoS to the 10 m contour.
- The only explicit rationale I found is "sufficient to capture most backwater effects" (Ye 2021), a present-day argument.
- No paper stated its contour was chosen to hold +3 m SLR, although +10 m NAVD88 obviously does.

---

## (c) What this implies for us (neutral)

**Option 1 — cut at the gauge or head of tide. What supports it:**
- It is the *modal* choice for estuary and surge studies: Yin 2021 and Deb 2025 (Delaware, to Trenton), Orton 2020 (Hudson, Troy dam), Kumbier, Lyddon, Harrison, Loveland, Muñoz.
- For Sandy specifically, primary sources agree rivers were a minor term in NJ. USGS: "widespread river flooding was not documented"; basin rain was 1.3–1.6 in; Trenton peaked at ~800 m³/s against 4,000–5,500 m³/s for Irene/Lee.
- Where river-off tests exist for surge-dominated conditions, the **coastal-gauge** effect is a few cm to 2% (Kumbier, Orton 2012 at the Battery). The effect grows upriver (9% at Piermont; Delaware effects confined above Marcus Hook or the Schuylkill).
- The structural heads of tide on our biggest rivers bound the surge reach: the Trenton bedrock "weir" and the Troy dam. The Passaic (Dundee) and Hackensack (Oradell) also end at dams — **not verified** here.

What argues against it:
- Zhang 2020 is the warning. Even a boundary placed well inland was reached by backwater, though only by cm in most places.
- Kumbier's and Loveland's results show upriver floodplains *do* change when river flow is added.
- Cutting at the gauge also imports the rating and daily-mean problems (Orton 2020, Kumbier).

**Option 2 — whole watersheds with rain-on-grid (the NC approach). What supports it:**
- It is validated for rain-dominated TCs, and it makes attribution and SLR-driven "upriver" compound shifts computable (Grimley 2024).

What argues against it for us:
- (i) Its benefit is shown for storms whose flooding was 79% runoff. Sandy is the opposite case.
- (ii) Even the NC group did not go to the divides. They cut below reservoirs and fed gauges, so it is option 1 moved upstream.
- (iii) Inland error is 0.6–0.9 m HWM MAE in every whole-watershed study, dominated by channel bathymetry and rain/Q error — our own current pain points, multiplied.
- (iv) The domain would roughly double the channel-bathymetry problem (Grimley SI, Lyddon).
- The literature's own verdict is that channel bathymetry, not solver cost, is the limit. That matches our experience.

**Middle paths with published precedent:**
1. **Contour-bounded domain with point inflows where rivers cross it** (Nederhoff +10 m; Ye/STOFS 10 m; FEMA R2 25 ft). This is the standard "SLR-ready" shape. For a +3 m target, a +10 m NAVD88 contour gives margin by construction. It still requires channels up to the contour.
2. **Head-of-tide cut, plus a walled low-cost corridor above it.** Harrison 2022's "glass walls" and a constant burned bed carried discharge from gauges well above the tidal limit to the estuary. The Delaware model of Zhang 2020 extended one river (to Riegelsville, ~40 m) while the rest stopped at 10 m. Neither paper tested whether the corridor changed estuary levels.
3. **Head-of-tide cut today, with the domain extension saved for SLR runs.** I found **no published instance** of moving river cuts upstream for SLR. Everyone reuses the present-day domain. The evidence that this can be wrong is indirect (Santiago-Collazo 2021; Mita 2023; the Familkhalili crossover shift). Where the head of tide is bedrock or a dam (Trenton, Troy, probably Dundee and Oradell), SLR moves it little (Zhang 2020; Orton 2020). Where it is a soft tidal limit on a low-gradient river (Raritan above New Brunswick? not verified), it can move.
4. **Bed treatment where the lidar shows flat water.** The literature offers a calibrated bed against stage gauges (Lyddon), GVF inversion (Neal, Bates, Eilander 2023b), a constant offset (Grimley SC −2 m, Harrison −3 m ODN), or 1D geometry from existing HEC-RAS models (Grimley NC; Bakhtyar). For NJ, FEMA/NJDEP HEC-RAS models likely exist for the Raritan, Passaic and Millstone. That is the NC group's best-performing option, but its NJ availability is **not verified**.

**Where the literature is silent:**
- A quantified leak or drainage budget for SFINCS outflow edges.
- Any study choosing the domain from a future water-level footprint.
- Any Sandy river-on/off sensitivity for the Raritan, Passaic or Hackensack.
- Sensitivity of estuary levels to *where* a gauge inflow is placed, beyond Loveland's unreported test.
- How many of 50+ small tributaries matter. Deb 2025 simply dropped all streams below p99.5 Q = 100 m³/s.

---

## (d) Not verified — cited by others or found but not opened

- **USACE NACCS ADCIRC mesh (Cialone et al. 2015, ERDC/CHL TR-15-14, DTIC ADA621343):** its inland extent and river treatment. DTIC returned 403. Important because it is our forcing, so check whether its rivers stop at the heads of tide.
- **Saleh et al. 2017, Adv. Water Resour. 110:371–386, doi:10.1016/j.advwatres.2017.10.026:** Passaic/Hackensack/Newark Bay, NYHOPS + HEC-HMS + HEC-RAS 2D, Irene and Sandy. Only a search-engine summary was seen, stating Sandy was surge-dominated. No publisher abstract available.
- **Saleh et al. 2016** (Hudson Irene streamflow ensemble) and the **2016 AGU abstract on Sandy in the Passaic/Hackensack**: not opened.
- **Gori, Lin & Smith 2020 WRR** (doi:10.1029/2019WR026788) and **Gori, Lin & Xi 2020 Earth's Future** (doi:10.1029/2020EF001660): abstracts only. The model chain (ADCIRC + HEC-RAS + a high-resolution rainfall-runoff model) and the upstream boundaries are not verified.
- **Leijnse et al. 2021 Coastal Eng. 163:103796:** abstract only ("driven by … upstream river discharges"). The Jacksonville inflow placement is not verified.
- **Santiago-Collazo et al. 2019 EMS 119:166–181:** abstract only. Its coupling taxonomy is quoted second-hand via Jafarzadegan 2023.
- **Santiago-Collazo et al. 2024 WRR** ("moving coupling node"): abstract only.
- **Neal et al. 2021 WRR:** abstract only (figures quoted from the abstract).
- **Deb et al. 2023 Earth's Future** (Delaware Irene, SLR vs river flood): abstract only. Its domain and SLR design are not verified.
- **Bao et al. 2024 WRR** (WRF-Hydro–ocean dynamic coupling, Cape Fear): abstract only.
- **Muñoz et al. 2022 JAWRA** (Delft3D-FM vs HEC-RAS 2D, Delaware Bay, Sandy and Isabel): abstract only; its upstream boundary is not verified.
- **"Accumulating climate change influences … upper transition zone" (J. Hydrol. 2025, Eastwick):** search summary only.
- **Mita et al. 2023 Water:** abstract only.
- **Hoitink & Jay 2016 Rev. Geophys.:** abstract only; tidal-limit definitions not quoted.
- **Tehranirad et al. 2020 Water:** abstract only (Hydro-CoSMoS SF Bay river on/off).
- **Grimley et al. 2026 Earth's Future** and **Garcia et al. 2025 Earth's Future** (NC SFINCS follow-ups): not opened (ESSOAr/AGU blocked).
- **Dresback et al. 2013 (ASGS-STORM)** and **Bacopoulos et al. 2017 (SWAT+ADCIRC)**: known only second-hand via Yin 2021.
- **Yin et al. 2016 WRR** (coupled NYC Sandy), **Blumberg et al. 2015** (Hudson waterfront Sandy, NJDEP report), **Georgas et al. 2014/2016** (NYHOPS / SFAS): not opened. Whether NYHOPS carries the Passaic to Dundee Dam and the Hackensack to Oradell is not verified.
- **Head-of-tide locations and dam crest heights** for the Raritan (New Brunswick), Passaic (Dundee Dam) and Hackensack (Oradell): not verified. They matter for whether +3 m SLR overtops a structural head of tide.
- **Carried over from the brief, not re-verified this session:** CoSMoS 10 m contour rule; Xu et al. 2021 (PNNL FVCOM tidal limit), which is consistent with Zhang 2020 and Xiao 2021 quoting ~2.7 km below Trenton; van Ormondt et al. 2025 GMD (grid spacing vs channel width); Eilander 2023 HydroMT framework (opened here as #7).
- **Green et al. 2025 NHESS review (doi:10.5194/nhess-25-747-2025)** and **Jafarzadegan et al. 2023** were opened and searched. Neither gives guidance on *where* to place upstream boundaries. Jafarzadegan says only that at "the interface of a hydrologic and hydrodynamics model (i.e. upstream boundary condition of an estuary) coupled modeling is inevitable" (PDF p.27).

---

## Source catalogue (citations, DOI/URL, status)

1. Grimley, L.E., Sebastian, A., Leijnse, T., Eilander, D., Ratcliff, J., Luettich, R. (2025). Determining the relative contributions of runoff, coastal, and compound processes to flood exposure across the Carolinas during Hurricane Florence. *WRR* 61, e2023WR036727. doi:10.1029/2023WR036727. SFINCS, Carolinas. **FULL TEXT READ** (local PDF + SI docx).
2. Grimley, L.E., Hollinger Beatty, K.E., Sebastian, A., Bunya, S., Lackmann, G.M. (2024). Climate change exacerbates compound flooding from recent tropical cyclones. *npj Natural Hazards* 1:45. doi:10.1038/s44304-024-00046-3. SFINCS+ADCIRC, Carolinas. **PARTIAL** (methods, results, discussion).
3. Nederhoff, K., Leijnse, T.W.B., Parker, K., Thomas, J., O'Neill, A., van Ormondt, M., McCall, R., Erikson, L., Barnard, P.L., Foxgrover, A., Klessens, W., Nadal-Caraballo, N.C., Massey, T.C. (2024). Tropical or extratropical cyclones: what drives the compound flood hazard, impact, and risk for the United States Southeast Atlantic coast? *Nat. Hazards* 120:8779–8825. doi:10.1007/s11069-024-06552-x. SFINCS (CoSMoS-SEUS). **PARTIAL** (§3, §4.1, discussion).
4. Leijnse, T.W.B., van Dongeren, A., van Ormondt, M., de Goede, R., Aerts, J.C.J.H. (2025). The importance of waves in large-scale coastal compound flooding: A case study of Hurricane Florence (2018). *Coastal Eng.* 199, 104726. doi:10.1016/j.coastaleng.2025.104726. SFINCS+SnapWave. **PARTIAL** (§2.4–2.5, conclusions; local PDF).
5. Goulart, H.M.D., Benito Lazaro, I., van Garderen, L., van der Wiel, K., Le Bars, D., Koks, E., van den Hurk, B. (2024). Compound flood impacts from Hurricane Sandy on New York City in climate-driven storylines. *NHESS* 24, 29–45. doi:10.5194/nhess-24-29-2024. SFINCS 50 m, NYC. **PARTIAL** (§2, discussion, conclusions).
6. Sebastian, A., Bader, D.J., Nederhoff, C.M., Leijnse, T.W.B., Bricker, J.D., Aarninkhof, S.G.J. (2021). Hindcast of pluvial, fluvial, and coastal flood damage in Houston, Texas during Hurricane Harvey (2017) using SFINCS. *Nat. Hazards* 109:2343–2362. doi:10.1007/s11069-021-04922-3. **PARTIAL** (§3.2, limitations).
7. Eilander, D., Couasnon, A., Leijnse, T., Ikeuchi, H., Yamazaki, D., Muis, S., Dullaart, J., Haag, A., Winsemius, H.C., Ward, P.J. (2023). A globally applicable framework for compound flood hazard modeling. *NHESS* 23, 823–846. doi:10.5194/nhess-23-823-2023. **PARTIAL** (§3.2, sensitivity, discussion).
8. Eilander, D., Couasnon, A., Sperna Weiland, F.C., Ligtvoet, W., Bouwman, A., Winsemius, H.C., Ward, P.J. (2023). Modeling compound flood risk and risk reduction using a globally applicable framework: a pilot in the Sofala province of Mozambique. *NHESS* 23, 2251–2272. doi:10.5194/nhess-23-2251-2023. **PARTIAL** (§2.3, discussion).
9. Ye, F., Huang, W., Zhang, Y.J., Moghimi, S., Myers, E., Pe'eri, S., Yu, H.-C. (2021). A cross-scale study for compound flooding processes during Hurricane Florence. *NHESS* 21, 1703–1719. doi:10.5194/nhess-21-1703-2021. SCHISM. **PARTIAL** (§2–3, §5–6).
10. Zhang, Y.J., Ye, F., Yu, H., Sun, W., Moghimi, S., Myers, E., et al. (2020). Simulating compound flooding events in a hurricane. *Ocean Dynamics* 70, 621–640. doi:10.1007/s10236-020-01351-x (revised-proofs PDF at ccrm.vims.edu). SCHISM, Delaware. **PARTIAL** (§1, §3, §4, §5).
11. NOAA STOFS-3D-Atlantic, Registry of Open Data on AWS: https://registry.opendata.aws/noaa-nos-stofs3d/. **PARTIAL** (web page).
12. Yin, D., Muñoz, D.F., Bakhtyar, R., Xue, Z.G., Moftakhari, H., Ferreira, C., Mandli, K. (2021). Extreme water level simulation and component analysis in Delaware Estuary during Hurricane Isabel. *JAWRA*. doi:10.1111/1752-1688.12947 (accepted manuscript via NOAA IR 55143). **PARTIAL** (§1–2).
13. Bakhtyar, R., Maitaria, K., Velissariou, P., Trimble, B., Mashriqui, H., Moghimi, S., Abdolali, A., Van der Westhuysen, A.J., et al. (2020). A new 1D/2D coupled modeling approach for a riverine-estuarine system under storm events: Application to Delaware River Basin. *JGR Oceans* 125. doi:10.1029/2019JC015822. **ABSTRACT ONLY**.
14. Xiao, Z., Yang, Z., Wang, T., Sun, N., Wigmosta, M., Judi, D. (2021). Characterizing the non-linear interactions between tide, storm surge, and river flow in the Delaware Bay Estuary, United States. *Front. Mar. Sci.* 8:715557. doi:10.3389/fmars.2021.715557. FVCOM. **PARTIAL** (§2–3).
15. Deb, M., Sun, N., Yang, Z., Wang, T., Judi, D., Cooper, M.G., Wigmosta, M.S. (2025). Extreme flood return levels in a U.S. mid-Atlantic estuary using 40-year fluvial-coastal model simulations. *Scientific Data* 12:1459. doi:10.1038/s41597-025-05566-9. DHSVM+FVCOM. **PARTIAL** (methods, validation).
16. Sun, N., Son, Y., Reesman, C., Li, X., Deb, M., Perkins, W., Yang, Z., Balaguru, K., Judi, D. (preprint, submitted to *Earth's Future*). Mapping Philadelphia's floodscape: a 35-year analysis of coastal urban flood hazards and drivers. OSTI https://www.osti.gov/pages/servlets/purl/3366548. **PARTIAL** (§2). Unrefereed.
17. Santamaria-Aguilar, S., Maduwantha, P., Enriquez, A.R., Wahl, T. (2026). Large discrepancies between event- and response-based compound flood hazard estimates. *NHESS* 26, 571–586. doi:10.5194/nhess-26-571-2026. And Maduwantha, P., Wahl, T., Santamaria-Aguilar, S., Jane, R., Dangendorf, S., Kim, H., Villarini, G. (2026). Generating boundary conditions for compound flood modeling in a probabilistic framework. *HESS* 30, 401–420. doi:10.5194/hess-30-401-2026. SFINCS, Gloucester City NJ. **PARTIAL** (setup, limitations).
18. Bilskie, M.V., Hagen, S.C. (2018). Defining flood zone transitions in low-gradient coastal regions. *GRL* 45, 2761–2770. doi:10.1002/2018GL077524 (PDF via lacoast.gov). **PARTIAL** (§3–5).
19. Bilskie, M.V., Zhao, H., Resio, D., Atkinson, J., Cobell, Z., Hagen, S.C. (2021). Enhancing flood hazard assessments in coastal Louisiana through coupled hydrologic and surge processes. *Front. Water* 3:609231. doi:10.3389/frwa.2021.609231. **PARTIAL** (setup, validation, limitations).
20. Santiago-Collazo, F.L., Bilskie, M.V., Bacopoulos, P., Hagen, S.C. (2021). An examination of compound flood hazard zones for past, present, and future low-gradient coastal land-margins. *Front. Clim.* 3:684035. doi:10.3389/fclim.2021.684035. **PARTIAL** (setup, SLR results).
21. Loveland, M., Kiaghadi, A., Dawson, C.N., Rifai, H.S., Misra, S., Mosser, H., Parola, A. (2021). Developing a modeling framework to simulate compound flooding: when storm surge interacts with riverine flow. *Front. Clim.* 2:609610. doi:10.3389/fclim.2020.609610. **PARTIAL** (§2, results §3).
22. Orton, P.M., Conticello, F.R., Cioffi, F., Hall, T.M., Georgas, N., Lall, U., Blumberg, A.F., MacManus, K. (2020). Flood hazard assessment from storm tides, rain and sea level rise for a tidal river estuary. *Nat. Hazards* 102, 729–757. doi:10.1007/s11069-018-3251-x (author PDF, philiporton.com). **PARTIAL** (§1–3, §5).
23. Orton, P., Georgas, N., Blumberg, A., Pullen, J. (2012). Detailed modeling of recent severe storm tides in estuaries of the New York City region. *JGR Oceans* 117. doi:10.1029/2012JC008220. **ABSTRACT ONLY** (via Crossref).
24. Kumbier, K., Carvalho, R.C., Vafeidis, A.T., Woodroffe, C.D. (2018). Investigating compound flooding in an estuary using hydrodynamic modelling: a case study from the Shoalhaven River, Australia. *NHESS* 18, 463–477. doi:10.5194/nhess-18-463-2018. Delft3D. **PARTIAL** (§2–4).
25. Harrison, L.M., Coulthard, T.J., Robins, P.E., Lewis, M.J. (2022). Sensitivity of estuaries to compound flooding. *Estuaries and Coasts* 45, 1250–1269. doi:10.1007/s12237-021-00996-1. CAESAR-Lisflood. **PARTIAL** (abstract, methods).
26. Lyddon, C., Chien, N., Vasilopoulos, G., Ridgill, M., Moradian, S., Olbert, A., Coulthard, T., Barkwith, A., Robins, P. (2024). Thresholds for estuarine compound flooding using a combined hydrodynamic–statistical modelling approach. *NHESS* 24, 973–997. doi:10.5194/nhess-24-973-2024. **PARTIAL** (§2.4).
27. Bates, P.D., Quinn, N., Sampson, C., Smith, A., Wing, O., Sosa, J., et al. (2021). Combined modeling of US fluvial, pluvial, and coastal flood hazard under current and future climates. *WRR* 57, e2020WR028673. doi:10.1029/2020WR028673 (PDF via texmex.mit.edu). LISFLOOD-FP. **PARTIAL** (§2).
28. Muñoz, D.F., Moftakhari, H., Moradkhani, H. (2024). Quantifying cascading uncertainty in compound flood modeling with linked process-based and machine learning models. *HESS* 28, 2531–2553. doi:10.5194/hess-28-2531-2024. **PARTIAL** (§1–2).
29. FEMA / RAMPP (Sept. 2014). *Region II Storm Surge Project — Mesh Development*. https://feedback.region2coastal.com/…/R2_Mesh_Development.pdf. ADCIRC. **PARTIAL** (§2.1, §4). The title-page header oddly reads "Dallas County, Arkansas", a template artefact.
30. Mita, K.S., Orton, P.M., Montalto, F.A., Saleh, F., Rockwell, J. (2023). Sea level rise-induced transition from rare fluvial extremes to chronic and compound floods. *Water* 15(14), 2671. doi:10.3390/w15142671. HEC-RAS 1D-2D. **ABSTRACT ONLY** (via OpenAlex).
31. Familkhalili, R., Talke, S.A., Jay, D.A. (2022). Compound flooding in convergent estuaries: insights from an analytical model. *Ocean Sci.* 18, 1203–1220. doi:10.5194/os-18-1203-2022. **PARTIAL** (abstract, §2, discussion).
32. Suro, T.P., Deetz, A., Hearn, P. (2016). Documentation and hydrologic analysis of Hurricane Sandy in New Jersey, October 29–30, 2012. USGS SIR 2016–5085. doi:10.3133/sir20165085. **PARTIAL** (storm description, rainfall table, comparison with Irene).
33. Blake, E.S., Kimberlain, T.B., Berg, R.J., Cangialosi, J.P., Beven, J.L. II (2013). Tropical Cyclone Report: Hurricane Sandy (AL182012). NOAA/NHC. https://www.nhc.noaa.gov/data/tcr/AL182012_Sandy.pdf. **PARTIAL** (storm surge, rainfall, impacts). Authors checked on the PDF title page (dated 12 February 2013).
34. Jafarzadegan, K., Moradkhani, H., Pappenberger, F., et al. (2023). Recent advances and new frontiers in riverine and coastal flood modeling. *Rev. Geophys.* 61, e2022RG000788. doi:10.1029/2022RG000788 (CentAUR PDF). **PARTIAL** (§4.3, keyword search).
35. Green, J., Haigh, I.D., Quinn, N., Neal, J., Wahl, T., Wood, M., Eilander, D., de Ruiter, M., Ward, P., Camus, P. (2025). Review article: A comprehensive review of compound flooding literature with a focus on coastal and estuarine regions. *NHESS* 25, 747–. doi:10.5194/nhess-25-747-2025. **PARTIAL** (keyword search only; silent on boundary placement).
36. Kasaei, S., Orton, P.M., Ralston, D.K., Warner, J.C. (2025). Pluvial and potential compound flooding in a coupled coastal modeling framework: New York City during post-tropical Cyclone Ida (2021). *HESS* 29, 2043–2058. doi:10.5194/hess-29-2043-2025. COAWST. **PARTIAL** (§2.2). No river-boundary content, so it was not used in the prose.
37. SFINCS user manual, input page: https://sfincs.readthedocs.io/en/latest/input.html. **PARTIAL** (mask definition).
38. HydroMT-SFINCS 2.0.0-rc2, `workflows/bathymetry.py::burn_river_rect` docstring (installed at `~/nj_sandy_sfincs/hydromt_sfincs`). **Read.**

Abstract-only sources cited in the prose: Neal et al. 2021 WRR (doi:10.1029/2020WR028301); Leijnse et al. 2021 Coastal Eng. (doi:10.1016/j.coastaleng.2020.103796); Santiago-Collazo et al. 2019 EMS (doi:10.1016/j.envsoft.2019.06.002) and 2024 WRR (doi:10.1029/2023WR035718); Bao et al. 2024 WRR (doi:10.1029/2023WR036455); Deb et al. 2023 Earth's Future (doi:10.1029/2022EF002947); Tehranirad et al. 2020 Water (doi:10.3390/w12092481); Gori et al. 2020 WRR and EF; Hoitink & Jay 2016 (doi:10.1002/2015RG000507); Muñoz et al. 2022 JAWRA (doi:10.1111/1752-1688.12952).
