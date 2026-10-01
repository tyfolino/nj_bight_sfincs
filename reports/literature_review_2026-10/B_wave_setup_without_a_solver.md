> **Appendix to [../literature_review_2026-10.md](../literature_review_2026-10.md)** — the research notes as written on 2026-09-30, kept for their verbatim quotes, page numbers and read-status tags. Paths to scratch extracts (`*.txt`, `up/`, `gh/`) did not survive the session; the sources are cited in full at the end.

# Literature review B — representing wave setup without running a wave solver everywhere

Compiled 2026-09-30 for the `nj_bight_sfincs` Sandy hindcast (research only; nothing in the repo was modified).

## How to read this file

- **Tags.** `FULL TEXT READ` = I read the whole document or every section relevant here. `PARTIAL (…)` = I read the named parts; the rest is unread. `ABSTRACT ONLY` = only the abstract (from the publisher, USGS Pubs Warehouse, OpenAlex or Crossref). `SECONDARY` = the claim is quoted from another paper that cites it. The original was not opened.
- **Quotes.** Every quote was copied from text I extracted from the PDF or HTML (with `pypdf` or an HTML stripper). The PDF extractor dropped some spaces (Leijnse 2025 especially) and turned the Unicode minus into a NUL byte. In quotes I restored the spaces and wrote the minus as "−". **I restored the minus signs by inference.** The same NUL byte stands for "−" in Leijnse's equations A1 and A4, so I am confident, but I did not check them visually. The PDF renderer was not available.
- **Numbers.** No number in section (b) comes from memory. Anything I could not open is in section (d).
- **Inferences.** Where I apply a finding to our case, the sentence is marked **[inference]**.
- **Sources opened:** 41 documents at full or partial text, plus about 17 at abstract level (bibliography at the end).

---

## (a) Table of setup treatments

| # | Method | Inputs | Where applied | Cost | Reported accuracy (source) | Known failure / bias |
|---|---|---|---|---|---|---|
| 1 | **Full stationary wave solver coupled to flow**: SnapWave in SFINCS, STWAVE or SWAN in ADCIRC | Offshore spectrum (Hs, Tp, direction, spreading), bathymetry, wind for growth | Radiation-stress gradients everywhere in the wave grid. Setup and export through inlets come out of the flow solution. | Florence SFINCS: SnapWave was 13.3% of 6.12 h on 16 cores, and 5–10 s per call (Leijnse 2025 §4.5). **Ours: 97%.** | Florence back bays: R² 0.75, RMSE 0.24 m, bias −0.07 m. Open coast: R² 0.43, RMSE 0.38 m, bias +0.18 m (Leijnse 2025 §4.4) | Needs surf-zone resolution: ">two nodes across the surf-zone width" on gentle slopes and "about 10 grid points per surf-zone width" on steep ones (Al Azad & Marsooli 2026). Regional and local setup need "tens and few meters" (Idier 2019). SnapWave breaking differs from XBeach (Hs 2.45 vs 1.96 m) and its mean water level is slightly low (2.19 vs 2.33 m) (Leijnse 2025 §4.3). |
| 2 | **Empirical shoreline setup added at the OFFSHORE water-level boundary** (Stockdon 2006, after Parker 2023) | Deep-water H0 and L0, foreshore slope βf | Added uniformly to the boundary water level | Negligible | Florence back bays: R² 0.66, RMSE 0.31 m, bias 0.04 m. Open coast: R² 0.06, RMSE 0.43 m (Leijnse 2025) | Raises the whole domain, back bays and river mouths included. In Florence, depth errors ran from +1 m to −0.5 m by region. Duck gauge bias +25 cm, attributed to setup "not measured at the NOAA station" (Nederhoff 2024). Our own trial: +0.25–0.3 m everywhere. |
| 3 | **"20% of offshore Hs"** (US Army Corps of Engineers 2002, via Vousdoukas 2016 and Eilander 2023) | Offshore Hs only | Added at the boundary or tide points | Negligible | Florence back bays: bias **+0.96 m**. Open coast: RMSE 0.62 m, bias 0.46 m (Leijnse 2025) | Water levels "by 2 m" too high on the Outer Banks, and the excess "penetrates into river mouths and into the back bays" (Leijnse 2025). FEMA's 10–20% rule refers to the **breaking** wave height, not offshore Hs (FEMA 2015). |
| 4 | **Parametric inlet / river-mouth setup** (Hanslow & Nielsen 1993; Nguyen 2007; Tanaka & Tinh 2017; Dodet 2013; the "Nederhoff 2024b" relation cited by Leijnse 2025) | Offshore H (and T), inlet depth and width | Added to lagoon or bay water level | Negligible | In-inlet setup is 2–13% of offshore H over entrance depths of 1.1–6.5 m (Tanaka & Tinh 2017, abstract). It is 10–15% for shallow narrow entrances and 0.2–4% for deep wide ones (Treloar 2011, summarising Japanese data) and 7–15% at Albufeira (Dodet 2013). A trained entrance showed "less than 0.03 Horms" (Hanslow & Nielsen 1993). | Strongly geometry-dependent. Tidally modulated: larger at low tide (Dodet 2013; Treloar 2011; Idier 2019). The fitted relations come from single small systems. **I could not find the Nederhoff 2024b relation in print** (section d). |
| 5 | **Regression / look-up of setup built from coupled-model runs** (Treloar 2011 Moreton Bay; ERDC TR-25-18 NJ Back Bays; Anderson 2021 GP surrogate) | Offshore Hm0, Tm02, direction, tide phase, or without-wave water level | Added to water level at points or regions, usually after the run | A few full runs, then negligible | Moreton Bay: correlation >0.96 for all directions and tide levels. NJBB: with-waves vs without-waves NACCS SWL has R² 0.97–0.99 per save point (TR-25-18) | Point or region correction only: the flood dynamics are not re-run, and the FEMA volume limit (2015 §2.2.6.2) is ignored. Valid only inside the training envelope. |
| 6 | **1D transect models** (FEMA DIM; XBeach 1D in CoSMoS and USGS DR1184; HySwash) | Profile, offshore waves, still-water level | Setup along each transect. Either mapped by interpolation or used to force a 2D flood model at a nearshore boundary. | Per transect: cheap (DIM) to moderate (XBeach) | DIM static setup is "60 to 100 percent larger" than SPM and "less than 16 percent greater" than Goda (FEMA 2015). CoSMoS XBeach transects every 100–200 m (Barnard 2019). | Shore-normal assumption. Cannot represent inlets, alongshore gradients or export into bays (DR1184 lists 1D shore-normal limits). |
| 7 | **Nearshore boundary (SFINCS wavemaker or bzs/bzi) forced with mean level + IG from another model** | Time series of mean level (including setup) and IG waves at a line near the shoreline | Line in about 0.5–5 m depth. Water landward of it is driven by the imposed mean level. | Cheap once the time series exists | Hernani: "similar flood extent and depth" to XBeach-forced SFINCS (Leijnse et al. 2026 CD2025). DR1184: forced from XBeach at the 0.5 m contour. | **I found no publication that uses the `wstfile` setup channel alone on a sandy coast with inlets.** Setup would enter only where the line is. |
| 8 | **Ignore setup** (GTSR/GTSM, NHC P-Surge maps, TCWiSE Beira, Grimley 2025, Bates 2021 main text) | none | — | zero | Florence without waves: back-bay bias −0.15 m and open-coast R² 0.01 (Leijnse 2025). Sandy NY Harbor: waves worth 0.1–0.3 m (5–10%) (Liu 2020). | Systematically low. Kirezci 2020: leaving setup out gives "a consistent negative bias". |

---

## (b) Answers to questions 1–7

### Q1. Empirical setup formulas

**Theory: Longuet-Higgins & Stewart, and Bowen.** The standard explanation is that breaking reduces radiation stress, and a mean-level slope balances the reduction. Idier et al. (2019, §2) write: "The first theoretical explanation for the development of wave setup is due to Longuet-Higgins and Stewart (1964), who proposed that the divergence of the shortwave momentum flux associated with wave breaking acts as a horizontal pressure force that tilts the water level until an equilibrium is reached". Assuming a constant breaker index γb, Soomere et al. (2013, §3) give the maximum setup as "η̄max = 5/16 γb Hb" (Dean & Dalrymple 1991). For γb ≈ 0.78 that is about 0.24 × **breaking** height **[arithmetic mine]**. FEMA (2015, §1.0) says setup "can be on the order of 10 to 20 percent of the breaking wave height". Two caveats:
- The theory under-predicts at the shoreline. Hanslow & Nielsen (1993): "while the model of Bowen et al. (1968) tends to under-estimate the shoreline setup it over-estimates the setup across much of the surf zone." Raubenheimer et al. (2001, abstract): setup "is predicted accurately in the outer and middle surf zone, but is increasingly underpredicted as the shoreline is approached". Apotsos et al. (2007, abstract): "Neglecting bottom stress results in underprediction of the observed setup in all water depths".

**Stockdon et al. (2006).** From the abstract (USGS Pubs; ABSTRACT ONLY): "Setup at the shoreline was best parameterized using a dimensional form of the more common Iribarren-based setup expression that includes foreshore beach slope, offshore wave height, and deep-water wavelength." Also: "On infragravity-dominated dissipative beaches, the magnitudes of both setup and swash … are dependent only on offshore wave height and wavelength." For runup as a whole, the abstract reports "a − 17 cm bias and an rms error of 38 cm: the mean observed runup elevation for all experiments was 144 cm."
- The setup term, as reproduced by Dalinghaus et al. (2023, Table 3), is "0.35βf(Hs0L0)^0.5". The dissipative form used by Vitousek et al. (2017, eq. 5) is "Rsetup = 0.016 (H0 L0)^0.5".
- It predicts **shoreline maximum setup**, not setup across the surf zone.
- Setup error: USGS data release P9BQQTCI states that "Stockdon and others, (2006) assessed the accuracy of the utilized parameterization as having a root mean square error of 21 cm".
- Slope choice matters: "On intermediate and reflective beaches … the use of an alongshore-averaged beach slope … may result in a relative runup error equal to 51% of the fractional variability between the measured and the averaged slope" (abstract).

**The formulas compared on the Stockdon field data** (Dalinghaus et al. 2023, Table 3; PARTIAL). Table 3 lists r², R², d1, MAE and RMSE. The relevant rows are:

| Predictor | Form (as printed) | r² | MAE (m) | RMSE (m) |
|---|---|---|---|---|
| Guza & Thornton 1981 | "0.17Hs0" | 0.30 | 0.27 | 0.34 |
| Holman & Sallenger 1985 | "0.46ξ0Hs0" | 0.49 | 0.20 | 0.27 |
| Hanslow & Nielsen 1993 | "0.048Hrms0L0^0.5" | 0.38 | 0.22 | 0.27 |
| Stockdon 2006 | "0.35βf(Hs0L0)^0.5" | 0.49 | 0.15 | 0.21 |
| Ji 2018 | "0.220βs^0.538 Hs0 (Hs0/L0)^−0.371" | 0.58 | 0.13 | 0.19 |
| O'Grady 2019 | "0.92βfHs0(Hs0/L0)^−0.3" | 0.55 | 0.14 | 0.20 |
| Dalinghaus eq. 10 (genetic programming) | "0.355Hs0ξ0^0.5" | 0.58 | 0.13 | 0.19 |

Other points from Dalinghaus et al.:
- Guza & Thornton and Holman & Sallenger are SECONDARY via Dalinghaus.
- Slope choice is unsettled: "there is no consensus on which region to use to estimate the beach slope" (§4).
- O'Grady et al. (2019) found that "deep water wave height explains 30 % of setup variance, followed by an improvement of up to 12 % if beach slope is added … and a further 12 % when including wave steepness" (§1, SECONDARY).
- O'Grady 2019 itself (ABSTRACT ONLY) targets "extreme Mean Total Water Levels (MTWL, the mean height of the shoreline)" on "natural beaches exposed to open ocean wind waves".

**Hanslow & Nielsen (1993)** (FULL TEXT READ). Shoreline setup follows "Bs = 0.38 Ho, … with scatter between 0,2 Horms and 0.65 Horms", and "Bs = 0.048 (Horms Lo)^0.5". The river-entrance findings are under Q3.

**The "0.2·Hs" / 10–20% rule of thumb.**
- Vousdoukas et al. (2016, §2; PARTIAL): "ηW-SS = SSL + 0.2·Hs, … where 0.2Hs is considered to be a reliable approximation of the wave setup … (US Army Corps of Engineers, 2002)". They justify it this way: "information about the nearshore bathymetry and/or the slope is not available at European scale".
- Eilander et al. (2023, §3.1.1; PARTIAL): "We estimate the wave setup component based on 0.2 Hs, which is an often-used approximation for (large-scale) studies (Camus et al., 2021; Vousdoukas et al., 2016; US Army Corps of Engineers, 2002)".
- Leijnse et al. (2024, Frontiers, §1; PARTIAL) describe common practice as either neglecting waves, using "a static wave setup of 20% of the offshore wave height", or using Stockdon-type runup (Kirezci 2020).
- **Origin caveat [inference from FEMA 2015 and Soomere 2013]:** the physical 10–20% (≈5/16 γ) ratio is relative to **breaking** height. Applying it to offshore ERA5 Hs, as Vousdoukas and Eilander do, is a different and larger quantity on shelves where waves dissipate before breaking. I could not open the USACE Coastal Engineering Manual (EM 1110-2-1100) to confirm what it states.

**Global and SPM-type use.**
- Kirezci et al. (2020, Methods; PARTIAL): setup "was determined as a function of deep-water wave steepness (Hs0/L0) and bed slope using both the SPM graphical approach and Stockdon et al.", with "a value of 1/30 … finally adopted". They found that "if WS is not included, there is a consistent negative bias", and that including it cut "the mean absolute bias … by 88%".
- Melet et al. (2020) used Stockdon for global setup projections. This is from a search-engine summary only (section d).

**FEMA Direct Integration Method (FEMA 2015, Guidance Doc. 44; PARTIAL).**
- DIM "yields wave setup estimates at any point along a shore-normal transect", whereas SPM and Goda give setup "at the landward limit of flooding".
- Accuracy is stated only as a comparison: "DIM … yielded static wave setup values ranging from 60 to 100 percent larger than those from the SPM methodology … less than 16 percent greater than those predicted by Goda". "A reduction of up to 16 percent … may be applied to the DIM results if evidence suggests".

**Newer ML formulas.** Dalinghaus et al. (2023) report genetic-programming predictors (RMSE 0.19 and 0.17 m, the latter adding D50) that beat the older forms on the same data. They also caution that "an avenue for future research includes the validation of the GP predictors … by applying them to datasets not included in the training."

**Biases relevant to Sandy.** Every formula above was fitted on moderate field conditions: Hs0 up to about 4 m in the Stockdon compilation (Dalinghaus Table 1). All of them predict the shoreline maximum, not the value at a gauge or in a bay.

### Q2. How models without a wave solver include setup

- **Parker et al. 2023** (Natural Hazards 117:2219; PARTIAL §3.2, §4, discussion). Stockdon setup at 1 km transects from reverse-shoaled ERA5 at 10 m depth, averaged within 5 km of each GTSM point. Justification: "At the scale of this study, 1000 s of kilometers, a physical model capable of accurately resolving wave setup would be computationally prohibitive." Error: "Setup data for specific events should be treated as an order of magnitude estimate rather than an exact calculation." They also state that "tide gauges are generally considered to not contain wave setup signals … the mechanics and signal processing of tide gauges is designed to filter out wave setup signals (Sweet et al. 2015)" (a contested claim; see Q7 note).
- **Nederhoff et al. 2024** (Natural Hazards 120:8779; PARTIAL §3.2–3.4, validation, discussion).
  - Boundary = GTSM plus Stockdon setup for extratropical cyclones. **For tropical cyclones:** "water levels from the coupled numerical hydrodynamic and wave model setup (ADCIRC + STWAVE; see Massey et al. 2021), which includes tide, wind-driven surge, and wave-driven setup, were used."
  - Cost justification: "Incoming short and infragravity waves were not accounted for (except through statistical downscaling of wave setup …) since dynamically downscaling this was computationally prohibitive (increasing computation times ~ 1000-fold)". Footnote: the model runs at 200 m, IG waves would need 20 m, hence "100 × 10 = 1000x".
  - Error at Duck: "Duck, N.C. … has a median bias of + 25 cm … We hypothesize that Duck's overestimation is driven by the inclusion of an open-coast wave setup, which is not measured at the NOAA station".
  - Limitation: "the accuracy of this correction was not able to be assessed."
  - **The inlet relation that Leijnse 2025 attributes to this paper does not appear in its text** (I searched for inlet, channel depth, Hanslow, estuar* and river mouth). Nor is it in the EarthArXiv preprint or the USGS data-release metadata.
- **Leijnse et al. 2025** (Coastal Eng. 199:104726; local PDF; FULL TEXT READ of §1–5 and Appendices A–B). The requested numbers, exactly:
  - §4.4 method: "the SFINCS model is run with offshore drivers like tides and surge, to which either a) wave setup estimates from the Stockdon et al. (2006) formulation are added, or b) the rule-based '20% of the offshore significant wave height'-estimate … is applied." Also: "Wave setup in river mouths and in between barrier islands (as e.g. described in Hanslow and Nielsen, 1993), was accounted for in the subsequent study (Nederhoff et al., 2024b) using a parametric relation based on channel depth and offshore wave conditions". For the 20% case: "there is no wave setup reduction applied in between barrier islands, as is often not done". And: "the stationary wave solver and dynamic IG wave processes are excluded to avoid double counting".
  - §4.4 results (p. 13): "The modeled maximum water depths with the Stockdon method are overestimated compared to the extended SFINCS model simulation by about 1 m in some regions, while other regions showed an underestimation of 0.5 m." For the 20% rule: "Large offshore wave heights lead to a significant overestimation of the wave setup and thereby to the total water level by 2 m. This overestimated water level penetrates into river mouths and into the back bays".
  - Skill against 70 USGS rapid-deployment gauges (Fig. 14):

    | Run | Back bays | Open coast |
    |---|---|---|
    | Extended SFINCS (SnapWave) | R² 0.75, RMSE 0.24 m, MAE 0.20 m, bias −0.07 m, relative bias −6.9% | R² 0.43, RMSE 0.38 m, MAE 0.32 m, bias 0.18 m, relative bias 12.2% |
    | No waves | bias "increases to −0.15 m" | R² 0.01, RMSE 0.47 m |
    | Stockdon | R² 0.66, RMSE 0.31 m; "The bias is lower with 0.04 m, because the higher wave setup (partly) compensates for the generally underestimated storm surge in the input boundary conditions." | R² 0.06, RMSE 0.43 m |
    | 20% Hs | bias 0.96 m | R² 0.12, RMSE 0.62 m, bias 0.46 m |

  - Conclusion (§5): Stockdon gives flooding differences "in the order of 0.5–1 m over/underestimation depending on the region", and the 20% rule "shows major overestimations … in the order of meters". The extended model "makes it less arbitrary how to deal with nearshore wave conditions, coastal slopes and wave setup reduction in estuaries and in between barrier islands."
  - §4.5 cost: "The simulation of SFINCS with all processes turned on takes 1.2 h per simulated day and 6.12 h in total on 16 virtual CPU cores … Of this, 13.3% of the computation time was needed for the SnapWave solver and 1.5% by the IG wave boundary condition." Also: "one stationary timestep of the SnapWave wave solver takes 5–10 s". Section 5 adds: "the integration of the SnapWave solver in SFINCS only added 5–15% to the model runtime." Grid: "5 million active grid cells for SFINCS, of which 1.4 million are active grid cells of the wave solver". Surf zone at 25 m. "The stationary wave solver updates the incident and IG wave conditions every 30 min". §4.5 names "the non-parallelized SnapWave solver" as a possible GPU bottleneck.
  - Boundary: "the marine water levels including all components are forced in SFINCS at approximately −10 m+NAVD88". These are GTSM levels, which carry no wave effects, so **there is no setup in their boundary** (unlike NACCS).
- **Eilander et al. 2023** (NHESS 23:823; PARTIAL): 0.2 Hs is added to GTSM at the boundary. Justification: "justified by our aim to make the framework globally applicable". They report that the setup component "amounts to 24.4 % for Idai and 16.3 % for Eloise of total water levels, indicating that wave setup could not be ignored."
- **Vousdoukas et al. 2016** (NHESS 16:1841; PARTIAL): 0.2 Hs (quoted above). They add that "omitting the wave contribution in the extreme total water level (TWL) can result in a ∼60 % un[derestimation]" of the flooded area (abstract).
- **TCWiSE / Deltares forecasting (Nederhoff et al. 2024c, GMD 17:1789; PARTIAL):** Beira case: "the effects of waves (e.g., setup, run-up, overtopping) and morphological change were not considered."
- **Grimley et al. 2025** (WRR 61, e2023WR036727; local PDF; PARTIAL, searched for waves): SFINCS forced at the coast by "20‐min water levels (storm tide) simulated using a previously validated ADCIRC model". The limitations section (§5.4) does not mention waves. "Waves" appears only in the introduction's list of drivers.
- **USGS CoSMoS (California; Barnard et al. 2019, Sci. Rep. 9:4309; PARTIAL Methods):** "Along the exposed open coast, XBeach profile models, with a cross-shore resolution of 5 m at the shore, are applied every 100–200 m in the alongshore direction to simulate event-driven shoreline change, wave set-up, and swash". "Predicted flood levels are interpolated onto regularly-spaced grids".
- **USGS CoSMoS-SE / data releases (P9BQQTCI, P9W91314 metadata; FULL of the setup sections):** "Wave setup was calculated at each transect using the parametrization of Stockdon and others (2006) for every hourly timestep". Also: "A comprehensive accuracy assessment was not performed for the dataset due to a lack of wave setup observations along the coastline."
- **Pacific islands (Storlazzi et al. 2024, USGS DR 1184; PARTIAL): XBeach 1D transects forcing SFINCS.** "The SFINCS boundary conditions were determined from XBeach still water level (tides and surge). The XBeach time series outputs were extracted at the intersection between the transect and the 0.5-m bathymetric contour". Also: "The ramp-up goes from mean sea level to the average incoming water level calculated from XBeach" and "The wave time series were computed as a random signal with a random phase". **It is ambiguous whether the imposed mean level contains XBeach setup.** The text says both "still water level" and "average incoming water level".
- **Fathom / Bates et al. 2021** (WRR 57; PARTIAL §2.2.3): coastal boundary = NOAA gauge skew surge plus a GeoCLAW hurricane catalogue. No wave-setup term is described in the main-text method. "NOAA WAVEWATCH III hindcasts" appear only in the data-availability statement. I did not read the supporting information.
- **NOAA/NHC (inundation-map web page; PARTIAL):** "The Potential Storm Surge Flooding Map does not take into account: Wave action". I could not open the SLOSH and P-Surge pages.
- **GTSR (Muis et al. 2016, Nat. Commun. 7:11969; PARTIAL):** "the effects of waves … are not considered … Wave setup may increase total sea levels considerably near the coast with the largest contribution in regions with steep slopes."
- **USGS NJ flood-inundation scenarios (Suro et al. 2023, SIR 2023-5005; PARTIAL):** uses the FEMA Region II ADCIRC+unSWAN model. Also: "the model output used to generate inundation layers for this project does not include waves modeled on top of the still-water tidal elevations".
- **FEMA post-Sandy ABFE report (PARTIAL):** the stillwater levels came from the Region II study. "The draft preliminary SWELs do not include overland wave effects", so depth-limited wave heights were added on top. This concerns overland wave crests, not setup.

### Q3. Setup in inlets, lagoons and back bays

**The mechanism.** Idier et al. (2019, §2): "wave breaking over the ebb shoals of shallow inlets (Malhadas et al. 2009; Dodet et al. 2013) as well as large estuaries (Bertin et al. 2015; Fortunato et al. 2017) results in a setup that can propagate at the scale of the whole backbarrier lagoon or estuary. Local wave setup of several tens of centimeters up to about 1 m have been observed …, while regional wave setup can reach values of tens of centimeters (Bertin et al. 2015)." (The originals are SECONDARY.)

Tidal modulation (Idier §3.5.1): "wave breaking is more intense on ebb shoals at low tide so that the associated setup in the lagoon/estuary is higher at low tide." Tagus 1941 (SECONDARY): "a wave setup reaching up to 0.35 m at the scale of the whole estuary … ranged from 0.10 to 0.15 m at high tide … and 0.30–0.37 m at low tide."

**Magnitude and dependence on inlet depth and width**

- **Dodet et al. 2013** (JGR 118:1587; PARTIAL). Albufeira lagoon:
  - "The wave-induced setup inside the lagoon represented 7%–15% of the offshore significant wave height."
  - "On average, the maximum setup represented 11% of the offshore wave height, corroborating the 10–14% range estimated by Nguyen et al. [2007] for storm-induced setup at narrow and shallow inlet mouth". Also: "a shore-normal and deeper inlet morphology … produced lower maximum setups (7% …)". And: "the shallower the inlet, the higher the setup".
  - Absolute values at an offshore Hs of 1.17–1.72 m: 0.09–0.23 m.
- **Treloar et al. 2011** (ICCE 32, Moreton Bay; PARTIAL):
  - Summarising Japanese work: setup "could increase water levels inside entrances by 10% to 15% of the offshore wave height for shallow and narrow entrances, and 0.2% to 4% of the offshore wave height for deep and wide entrances."
  - Moreton Bay at offshore Hm0 7 m, easterly: regional setup "between 0.05 and 0.1m" near high tide and "approximately 0.3m" near low tide.
  - Mechanism: "largely due to a gradient in radiation stresses in Moreton Bay that acts against the ebb tide flow rather than a mass influx".
- **Tanaka & Tinh 2017** (Procedia IUTAM 25:10; ABSTRACT ONLY), six Japanese river mouths: "The wave set-up height attains from 2 to 13 percent of offshore wave height for the cases of average water depth at entrance ranging from 1.1 m to 6.5 m." Setup is "affected by the river discharge and river mouth morphology".
- **Hanslow & Nielsen 1993** (FULL TEXT READ), Brunswick River, a trained entrance with a 40 m channel and 4–5 m depth:
  - "very little setup occurring (less than 0.03 Horms) in the river entrance".
  - "At the same time the shoreline on the adjacent beach was consistently about 1m above the offshore water levels."
  - This "super-elevation of the beach shoreline level above the mean water level of the adjacent river … has been observed to result in large scour holes".
- **Irish & Cañizares 2009** (J. Waterway 135:52; ABSTRACT ONLY), **Long Island**: "Offshore wave setup generated by wave breaking during coastal storms can create significant flow through tidal inlets and increase bay flooding." They also report that "wave-induced flow contributions make up 15–35% of the total storm surge, where the wave-induced flow contribution increases with increased inlet efficiency". They introduce "an approach … for estimating wave-induced flow contributions to bay flooding as a function of inlet and storm characteristics, including tidal prism and wave conditions." **This is the closest published parameterisation to our geography. Only the abstract was available.**
- **Olabarrieta et al. 2011** (Willapa; not opened). SECONDARY via Wargula 2014: wave breaking over the shoals is "predicted to drive flows into the inlet, causing an 11.8% increase in bay volume".
- **Wargula et al. 2014** (JGR 119; PARTIAL), New River Inlet NC: "Onshore radiation-stress gradients owing to breaking waves enhance the flood flows into the inlet, especially during storms." On geometry: "New River Inlet is an open system, connected to other inlets via the ICW … The additional inlets along the ICW allow for water mass exchange and leakage."
- **Wargula et al. 2018** (JGR 123; PARTIAL): "breaking waves at the offshore edge of the ebb shoal induce setup and partially block the ebb jet …, which leads to … increased water levels inside the inlet mouth (nonlocal effects)."
- **Orescanin et al. 2014** (CSR 82:37; PARTIAL), Katama Bay, **including Hurricane Sandy**:
  - "During Hurricanes Irene and Sandy, when incident (12-m water depth) significant wave heights were greater than 5 m, breaking-wave … radiation stress gradients enhanced flows from the ocean into the bay during flood tides".
  - But: "Unlike previous numerical results (Olabarrieta et al., 2011; Dodet et al., 2013), the increase in the bay water level owing to wave forcing is relatively small, … likely because water flows out of the bay into Vineyard Sound … rather than accumulating in a closed basin."
- **Harvey et al. 2020** (Estuaries & Coasts; PARTIAL), 13 southern California estuaries. Intermittently closed estuaries show "a larger water level setup (as high as 0.2 m, but typically much smaller)", with estuary high water rising "0.07 m above that of the ocean for every 1 m increase in wave height". Perennially open estuaries "do not".

**New Jersey and New York back bays during Sandy**

- **Aretxabaleta et al. 2019** (NHESS 19:1823; PARTIAL):
  - "Water level in the bays is mainly driven by offshore sea level fluctuations with additional effects from local wind and wave setups."
  - Barnegat transfers "ranging from 50 %–100 %" in the storm band. "The wind setup effect can be comparable in magnitude to the offshore transfer forcing during intense storms."
  - Along-bay wind setup "over 0.2 m … for the 5 d period wind" at 0.1 Pa.
  - For Sandy they add "the frictional effect is enhanced … by the presence of wave-induced roughness."
  - **No wave-setup magnitude is given for Barnegat Bay.**
- **Aretxabaleta et al. 2014** (GRL 41:3163; ABSTRACT ONLY): the ocean-to-bay transfer in Barnegat Bay and Great South Bay was not changed by Sandy. "The post-Hurricane Sandy bay high water levels reflected offshore sea levels caused by winter storms, not by barrier island breaching".
- **Bennett et al. 2018** (CSR 161:1; ABSTRACT ONLY), Great South Bay, Delft3D-SWAN:
  - "strong local wind-driven storm surge along the bay axis had the largest influence on the total water level fluctuations during the hurricane"
  - "overwash of 7500–10,000 m³ s⁻¹ was approximately the same as the inflow from the ocean through the major existing inlet"
- **Unattributed technical note on Barnegat Bay during Sandy** (hosted by Berkeley Township NJ, about 2014; FULL TEXT READ; grey literature, data compilation only, "not a model"):
  - "The entire ocean to bay flooding across the barrier islands approximates an additional added foot of water elevation rise in the bay."
  - "Massive overwash between Bay Head and Ortley Beach added another 0.6 foot".
  - Before the breach: "80 MPH northeast winds blowing down the axis of Barnegat Bay pushing the shallow water column south".
- **ERDC TR-25-18 (Slusarczyk et al. 2025, NJ Back Bays; PARTIAL §2.4).** The NJBB ADCIRC runs were made without waves, so setup was restored by regression on NACCS "TC SWL results with and without waves" at each NJBB save point. The per-point intercepts are β0 = 0.096–0.266 m and the slopes β1 = 1.086–1.236 (R² 0.965–0.985). "At the save point locations evaluated in this study, the magnitude of the wave setup approximately ranged from 10% to 30% of the SWL." **This shows NACCS itself carries back-bay setup of 0.1–0.3 m or more.** I did not confirm where save points 2, 29, 36, 50 and 57 are.
- **FEMA 2015 §2.2.6.2**, a volume constraint for bays: "The volume of water that is required to 'fill' the potential wave setup across the large bay can be approximated as the average bay width times the bay length times the average wave setup height. This volume must be supplied by flow across the barrier or by other means … or the wave setup height will not be realized across the entire bay."
- Stevens (Georgas/Orton), Defne/Ganju (Barnegat COAWST wave setup), Miles, Sopkin (storm tide), Hu/Chen/Wang, Bertin 2009/2015/2019, Malhadas 2009, Fortunato 2017 and Lavaud 2020: see section (d). Sopkin et al. 2014 (OFR 2014-1088; PARTIAL) gives Sandy buoy data ("Hs of 9.9 m … at Buoy 44065") but **no setup analysis**.

### Q4. How large was the wave contribution to Sandy on the NJ/NY coast, and does NACCS resolve it?

- **Liu et al. 2020** (ECSS 233:106544; accepted manuscript via OSTI; PARTIAL), SCHISM + WWMIII:
  - "The maximum total water level at The Battery … was accurately simulated … which includes the effects on the order of 0.1–0.3 m (5–10%) from the coastal setup induced by the surface waves."
  - "The relatively larger wave setup was found to occur in the narrow, shallow estuaries, such as the upper New York Harbor and the Newark Bay, and the coastal bay such as Jamaica Bay. In much deeper water, such as in Long Island Sound, the effect of wave setup was relatively small."
  - **Caveat:** their "wave setup" is defined as coupled minus no-wave peak, so it includes wave-dependent wind stress (Janssen) and wave bottom stress, not only radiation stress.
- **Marsooli & Lin 2018** (JGR 123:3844; ABSTRACT ONLY), 1988–2015 tropical cyclones: "the maximum wave setup was relatively large (tens of cm) in most coastal regions, but it did not necessarily coincide with the peak storm tide. The contribution of wave setup to peak storm tides induced by the most extreme events was less than 17%." Al Azad & Marsooli (2026) cite this as "contributing up to 17% of peak storm tides".
- **NACCS itself (Cialone et al. 2015, ERDC/CHL TR-15-14; PARTIAL, chapters 3, 6, 7 and 8):**
  - Coupling: "tight two-way coupling between ADCIRC and STWAVE … STWAVE passes wave radiation stress gradients to ADCIRC to drive wave-induced water level changes (e.g., wave setup and setdown)."
  - The Sandy validation included waves: "River inflow and wave forcing were also included in the validation simulations."
  - STWAVE resolution: "A grid resolution of 200 m was selected for all of the grids except … Chesapeake Bay and Washington, DC … this resolution sufficiently resolved the surf zone to capture the wave breaking processes that drive wave radiation stresses and wave setup."
  - ADCIRC at NJ inlets: "The ADCIRC mesh resolution for these inlets ranges from 70–200 m."
  - Caveat noted in the report: "there is variable mesh resolution off the coast of New Jersey when transitioning from the FEMA Region III mesh to the FEMA Region II mesh … the nodal spacing normalized by the depth is also noticeably larger in this region".
  - Coupling rules: ADCIRC nodes outside STWAVE grids "receive a default value of zero for radiation stress gradients". STWAVE snaps are every 15–60 min for the synthetic storms.
  - Sandy at Atlantic City: "One noted exception is the overprediction of the storm peak at Atlantic City, NJ … the contention is that the discrepancy at this location is due to gage malfunction."
- **Is 200 m enough?**
  - Al Azad & Marsooli (2026, §2; PARTIAL), citing Nayak et al. 2012: "no significant differences in computed wave setup between coarse- and fine-resolution grids for gently sloping beaches". They select sites where "the model mesh consists of more than two nodes across the surf-zone width". Steep bathymetry "requires … about 10 grid points per surf-zone width".
  - Soomere et al. (2013): a coarse resolution "gives a fair estimate (about 90 % of the actual values) of wave set-up for gentle" slopes.
  - Idier et al. (2019, §5): "a resolution of few hundred meters … is not sufficient to capture regional and local wave setups, which, depending on the environment, require resolutions of tens and few meters".
  - **[inference]** For NJ's gentle open coast at Sandy's wave heights (a wide surf zone), NACCS at 200 m probably captures much of the open-coast setup. At 70–200 m it is unlikely to resolve inlet-throat and ebb-shoal setup, which Idier places at tens of metres. Our model finds setup generated "in the last 200–600 m", which is 1–3 NACCS cells.
- **Double counting at our boundary [inference].** NACCS water levels at a −10 m node already carry STWAVE radiation-stress effects there: setdown, or early setup if Sandy's waves were breaking at 10 m depth. With Hs of about 9–10 m at buoys 44065 and 44025 (Sopkin 2014), outer-surf-zone breaking near −10 m is plausible. The ERDC TR-25-18 regressions show NACCS *had* paired with-waves and without-waves synthetic TC runs. **If a waves-off NACCS Sandy exists, the difference at our boundary nodes would measure the setup we inherit.** I could not find whether one exists.
- **FEMA Region II (NJ/NYC) used ADCIRC + unSWAN** (Suro 2023, quoted above). I did not read the Region II reports themselves.

### Q5. Precomputed and surrogate approaches

- **Regression of setup from coupled runs, indexed by offshore waves (Treloar 2011; PARTIAL):** "The regional wave set-up (η) relationship for Moreton Bay has been developed into a simple linear regional model of the form … η = β0 + β1 (Hm0 × Tm02) … The correlation coefficient is greater than 0.96 for all wave directions and tide levels." Tide phase is handled by a factor: "Near high water … the magnitude of the regional wave set-up is generally 25% to 35% of the peak wave set-up which occurs near low water." It was used inside a 6,000-event Monte Carlo design study.
- **ERDC TR-25-18:** per-save-point linear regression of NACCS with-waves on without-waves water level (quoted in Q3). The TC surge itself was emulated with a "Gaussian Process Metamodel (GPM)".
- **Anderson et al. 2021** (Earth's Future; ABSTRACT ONLY): "A surrogate modeling framework of waves, winds, and tides is developed … to efficiently predict spatially varying nearshore and estuarine water levels contingent on any combination of offshore forcing conditions", using CoSMoS (Delft3D + XBeach) and "Gaussian process regression", validated "within San Diego Bay".
- **Hybrid downscaling chains (Ricondo et al. 2026, Coastal Dynamics 2025 vol. 2, pp. 3–7; local PDF; FULL TEXT READ):**
  - "pre-run libraries of a reduced number of simulations"
  - "BinWaves … based on SWAN simulations, is used for downscaling the offshore wave spectra"
  - "Surf-zone hydrodynamics are further downscaled along 1-D cross-shore profiles … using HySwash"
  - "HyFlood, a surrogate model of SFINCS"
  - BinWaves (Cagigal et al. 2024, ABSTRACT ONLY) "relies on the propagation of a reduced number of monochromatic wave systems and linear wave theory".
- **Reef metamodels:**
  - BEWARE (Pearson et al. 2017, ABSTRACT ONLY), built from a "large synthetic database" of XBeach Non-Hydrostatic runs.
  - BEWARE-2 (McCall et al. 2024, NHESS 24:3597; PARTIAL abstract and intro): "440 combinations of water level, wave height, and wave period with 195 representative reef profiles". Validation "relative root mean square error of 13 % and relative bias of 5 %" against XBeach runup, and "faster by 4–5 orders of magnitude".
  - HyCReWW (Rueda et al. 2019): metadata only.
- **Cost of a stationary solve, which sets the price of a look-up table** (Roelvink et al. 2025, SnapWave preprint; PARTIAL): "the number of nodes is around 250,000 and the run time per wave condition is around 2.5s, or approximately 10 microseconds per node and wave condition."
- **Reduced update frequency:** Leijnse 2025 updated SnapWave "every 30 min". NACCS STWAVE snaps were "every 60 min … every 30 min … every 15 min" depending on storm forward speed.
- **Applying a precomputed setup field inside SFINCS: what the code allows** (SFINCS source on GitHub, `sfincs_input.f90` and `sfincs_wavemaker.f90`, main branch as of 2026-09-29, and the `v2.3.0_mt_Faber_release` and `v2.3.3` tags; read directly):
  - There is **no input keyword for an external wave-force or radiation-stress field.** `storefw` only *writes* wave forces.
  - There is a multiplier: "Added input variable 'snapwave_waveforces_ratio' which you can set to 0 to turn off wave forces and thus incident wave setup" (SFINCS docs changelog, v2.4.0).
  - A precomputed wave-force look-up table would therefore need code or BMI changes **[inference; the docs list a BMI/XMI interface, which I did not test for writing force arrays]**.
- **I found no publication that applies a precomputed setup or radiation-stress field as forcing in SFINCS.** The closest precedents force SFINCS at a nearshore boundary with XBeach-derived mean level and IG time series (DR1184; Leijnse et al. 2026; Gaido-Lasserre 2024, which I did not open).

### Q6. One-dimensional transect approaches

- **FEMA DIM** (Q1): a 1D integration along "a shore-normal transect". Guidance on bays: "Two-dimensional effects should be considered" where only part of a barrier is overtopped, plus the volume constraint quoted in Q3.
- **CoSMoS XBeach profiles every 100–200 m** (Barnard 2019), then interpolated to grids.
- **DR1184** (Storlazzi 2024): XBeach "one-dimensional hydrostatic mode along the cross-shore transects, at a varying resolution between 10 m seawards and 1 m landwards". The output forces SFINCS at the 0.5 m contour. Limits it lists: "The modeling structure of one-dimensional nearshore XBeach transects assumes shore-normal wave and wave-driven water level processes", and "flooding is likely underrepresented around promontories".
- **HySwash** (1D SWASH surrogate; Ricondo 2026).
- **Parametric 1D setup on a 2D wave field (Soomere 2013; PARTIAL):** a WAM wave field at 470 m, then η̄max = 5/16 γb Hb per nearshore cell. Maxima are "up to 70–80 cm in selected locations".
- Accuracy of 1D radiation-stress setup integration against field data: good in the outer and middle surf zone, low at the shoreline unless rollers and bottom stress are included (Raubenheimer 2001; Apotsos 2007: "measured and modeled setups are correlated (squared correlation above 0.59) and agree within about 30%").
- **None of the 1D methods can represent export through inlets.** That is the point of FEMA's "two-dimensional effects" caveat.

### Q7. When is ignoring setup defensible?

- **Wide shelf, surge-dominated coasts:**
  - Marsooli & Lin 2018: setup <17% of peak storm tide in the most extreme events, and often not coincident with the peak.
  - Liu 2020, Sandy at the Battery: 5–10% (0.1–0.3 m).
  - Parker 2023: "the US Atlantic coastline is characterized by a broad continental shelf which limits the amount of wave energy that can penetrate to the coastline". Setup matters more "in the north and south" of the SE US study area.
  - Kirezci 2020 (global area flooded by 2100): "wave setup accounting for only approximately 5%".
- **Steep or narrow-shelf coasts:**
  - Al Azad & Marsooli (2026, citing Dean et al. 2005): "On narrow-shelf segments, wave setup can reach up to 50% of the total 100-year surge".
  - Soomere (2013, citing Dean & Bender 2006): "in Florida wave set-up can be 30 % to 60 % of the total 100 yr storm surge".
  - Parker 2023 and Leijnse 2025 (citing Vitousek 2017 and Sweet 2022): setup contributes "10–82% of water levels during extreme events" nationally (SECONDARY).
- **Back-barrier bays:**
  - NACCS-derived setup at NJBB save points is 10–30% of SWL (TR-25-18).
  - Irish & Cañizares 2009 (Long Island): wave-driven inlet flow is 15–35% of total bay surge.
  - Leijnse 2025: removing waves moved the back-bay bias from −0.07 m to −0.15 m.
  - **[inference]** In absolute terms, ignoring setup costs about 0.1 m in back-bay peaks. That matches our own +0.11 m lift and the Sandy-harbour 0.1–0.3 m.
- **The gauge caveat (conflicting sources):**
  - Parker 2023 and Suro 2023 say gauge stilling systems filter "the effects of wave action".
  - Kirezci 2020 found that adding setup *improved* agreement with tide-gauge extremes.
  - **[inference]** A stilling well filters wave oscillations, not a sustained mean-level rise. Whether a gauge "sees" setup depends on where it sits relative to the surf zone. For a pier-end gauge like Atlantic City that is a site fact, not a general rule.

---

## (c) What this implies for us: candidate treatments, ranked

Our setting: barrier coast with jettied inlets; the boundary at −10 m is forced by NACCS ADCIRC+STWAVE levels (which already carry some setup and setdown); we need setup in the back bays without lifting open-coast gauges; SnapWave costs 97% of wall time.

**Headline:**
- **Only methods that generate setup *inside* the domain, landward of the open-coast gauges, can export it into the bays without lifting those gauges.** These are SnapWave itself, and a nearshore line forcing inside the surf zone (candidate B).
- Anything added at the −10 m boundary lifts everything: Stockdon or 0.2 Hs at the boundary, and parametric offsets at the boundary. That is what we saw (+0.25–0.3 m), and what Leijnse (2025) and Nederhoff (2024, Duck +25 cm) report.

**A. Keep SnapWave, make it cheaper (not a literature method; ranked first because the evidence says our cost is atypical).**
- Leijnse (2025) reports SnapWave at 13.3% of run time, 5–10 s per call, 1.4 M wave cells, 30-min updates. Roelvink (2025) gives about 10 µs per node per condition. Our share is 97%.
- The repo's own `snapwave_params.py` lists SFINCS defaults of `snapwave_dtheta` 10° and `snapwave_niter` 10. The v3 premier `sfincs.inp` runs `snapwave_dtheta = 5.0` and `snapwave_niter = 200`, plus wind growth, IG and `dtwave = 1800`.
- The literature supports 30–60 min coupling (Leijnse; NACCS).
- **[inference]** The gap is more likely configuration (directions, sweeps, wave-grid extent, serial solver on 3.4 M faces) than a law of nature. This is not a published result; it is a flag.
- Right: everything SnapWave gets right today, including in-bay wind-wave setup (0.05–0.10 m) and inlet shoal forcing.
- Wrong: nothing new, but coarser settings must be checked against the premier run (paired, per mark).

**B. Time-series wavemaker carrying setup only (`wavemaker_wstfile`), placed along the surf zone, fed with setup from a precomputed source.**
- What exists: SFINCS reads `wavemaker_wfpfile/whifile/wtifile/wstfile` in v2.3.0 Faber (our engine) and later. In the code the setup enters as `zs0nmb = zs(nmb) + setup ! average water level inside model without waves`. A whi file is mandatory, so a setup-only use would need IG height set to 0 **[inference]**.
- Leijnse 2025 Appendix B defines the wavemaker's slowly varying level ζ0 as "the slowly-varying water level due to the tide, storm surge and mean incident-wave-induced setup". The docs say the model offshore boundary is usually "in about 2 meters water depth" for wave-driven cases.
- Possible setup sources:
  - per-segment regression on offshore Hs·Tp from a few full SnapWave runs (Treloar-style);
  - our own SnapWave hindcast (for Sandy only; circular for anything else);
  - Stockdon or Dalinghaus scaled to the line depth (formula error about 0.2 m RMSE).
- What the literature says it would get right:
  - Setup enters only landward of the line, so offshore and pier-seaward levels are untouched.
  - Export into bays is left to the flow solver. That is how the inlet dependence arises in the process studies: inlet efficiency (Irish & Cañizares), multi-inlet leakage (Orescanin; Wargula 2014), and the bay-filling volume limit (FEMA 2015 §2.2.6.2).
- What it would get wrong:
  - There is no radiation-stress forcing on the ebb shoals or in the inlet throats, where Dodet, Wargula and Treloar place the lagoon setup, unless the line crosses the inlet mouths.
  - There is no local in-bay wind-wave setup.
  - The tidal modulation (much smaller setup at high water: Treloar 25–35%, Dodet, Idier) must be carried in the input.
  - **I found no published test of a setup-only wavemaker on a sandy barrier coast with inlets.** The absorbing-generating boundary with a pure mean offset, and its `wavemaker_filter_time` smoothing, are untested for this use **[inference]**.

**C. Post-run regression correction of back-bay levels (the ERDC TR-25-18 approach).**
- Fit, per bay region, the premier-minus-waves-off difference against offshore wave parameters or the waves-off level, as ERDC did with NACCS pairs. Then add the fit to waves-off results.
- Right: cheap, and reproduces the premier's bay lift where it was trained (ERDC R² 0.97–0.99).
- Wrong: no flooding dynamics; inundation extent is not recomputed. It ignores the FEMA volume constraint. It is only valid inside the training envelope, and it inherits SnapWave's own biases.

**D. Parametric inlet setup (Hanslow-type; the "Nederhoff 2024b" relation; Tanaka & Tinh; Irish & Cañizares).**
- NJ inlets are jettied navigation channels. The literature puts deep and wide or trained entrances at the low end: 0.2–4% of offshore H (Treloar/Nguyen) and "less than 0.03 Horms" (Hanslow & Nielsen).
- **[arithmetic]** Our +0.11 m bay lift divided by Sandy's offshore Hs of about 9–10 m is about 1%, inside the deep-and-wide range. That is consistent, but not a validation.
- Right: the order of magnitude, and cheap.
- Wrong: a single number per inlet cannot distribute setup within a bay, and SFINCS has no natural place to inject it except a source term or a forced line. In Florence, Stockdon plus the inlet relation gave back-bay RMSE 0.31 m vs 0.24 m for SnapWave (Leijnse 2025).

**E. Stockdon (or any shoreline formula) at the offshore boundary.** Rejected by our own test and by the literature: it lifts open-coast gauges and bays alike (Leijnse 2025; Nederhoff 2024).

**F. 0.2 Hs at the boundary.** The worst on record: Florence back-bay bias +0.96 m (Leijnse 2025). It also misapplies a breaking-height ratio to offshore Hs (FEMA 2015; Soomere 2013).

**G. Waves off.**
- Defensible only if about 0.1–0.15 m of low bias in bays and at HWMs is acceptable. Our lift is 0.11 m; Florence no-wave back-bay bias was −0.15 m; Sandy harbour 0.1–0.3 m.
- NACCS's own inherited boundary setup stays either way.

**Do not expect any setup treatment to close the observed 0.2–0.55 m back-bay superelevation.** For Sandy in NJ and NY back bays, the literature points at mechanisms other than wave setup:
- local along-bay wind setup (Aretxabaleta 2019: >0.2 m for sustained wind; Bennett 2018: "largest influence" in Great South Bay);
- overwash and breaching (Bennett 2018: overwash ≈ inlet inflow; the Barnegat note: about 1 ft from cross-island flow);
- in shallow inlets, ebb-shoal setup that our 25–50 m bed may or may not resolve.

**[inference]** A pre-registration should say in advance which of these a setup treatment can and cannot fix.

**Double-counting check worth doing whatever the choice:** find out whether NACCS has a waves-off Sandy run, or use NACCS TC pairs as in TR-25-18, to size the setup already present at our −10 m boundary.

---

## (d) Not verified: could not open, or claim not found

- **"Nederhoff et al. 2024b" parametric inlet/between-barrier setup relation** (channel depth + offshore waves), as cited by Leijnse 2025 §4.4. Not found in the Natural Hazards paper (full text searched), the EarthArXiv preprint, or the USGS data-release metadata (P9BQQTCI, P9W91314). It may live in an unreleased dataset or in Barnard et al. 2024 supplementary material, which I did not locate.
- **US Army Corps of Engineers (2002) Coastal Engineering Manual:** the origin of the "0.2 Hs" rule. publications.usace.army.mil returned 403.
- **Dean & Walton (2009), Handbook of Coastal and Ocean Engineering, "Wave setup":** not opened.
- **Dean, Collins, Divoky, Hatheway & Scheffner (2005) FEMA Wave Setup Focused Study; Dean & Bender (2006):** seen only as citations (Al Azad & Marsooli 2026; Soomere 2013).
- **Guza & Thornton (1981); Holman & Sallenger (1985); Bowen, Inman & Simmons (1968); Longuet-Higgins & Stewart (1964); Ji et al. (2018):** formulas taken only from Dalinghaus 2023 Table 3, Soomere 2013 and Idier 2019.
- **Stockdon et al. (2006) full text:** abstract only. The setup-only RMSE of 21 cm is from the USGS data-release metadata.
- **Melet et al. 2018 (NCC) and 2020 (JGR):** search-engine summaries only (HAL and Wiley blocked).
- **Bertin et al. 2009 (CSR 29:819), 2015 (CSR 96:1), 2019; Malhadas et al. 2009; Fortunato et al. 2017; Olabarrieta et al. 2011; Lavaud et al. 2020 (Ocean Model. 156:101710):** not opened (HAL behind Anubis, WHOAS behind a captcha, Elsevier and Wiley blocked). Their findings appear here only through Idier 2019, Dodet 2013 and Wargula 2014. A search-engine summary of Lavaud 2020 said wave forces improve storm-surge predictions "by 50 to 60%" and that setup "substantially contributes … in sheltered areas". **That is not verified.**
- **Gaido-Lasserre et al. 2024** (Ocean Model. 189:102358): only a search-engine snippet ("SFINCS … by itself does not produce infragravity waves and setup … forced with time series of both water levels (slowly varying) and infragravity waves"). Not verified.
- **Leijnse et al. 2021** (SFINCS paper, Coastal Eng. 163:103796): not opened. Its XBeach-forced Hernani case is known only through Leijnse et al. 2026 (CD2025).
- **Marsooli & Lin 2018:** abstract only; I could not get its Sandy-specific setup values. **Marsooli et al. 2017** (sECOM-MDO, Jamaica Bay): not opened. **Orton et al. 2016** (JGR, NY Harbor hazard): PDF blocked, so whether sECOM included waves is not verified.
- **Defne & Ganju (Barnegat COAWST); Miles; Georgas (NYHOPS); Hu/Chen/Wang (Jamaica Bay); Chen et al. WRF-FVCOM Sandy** (search snippet: wave-current interaction added "approximately 8 cm" to the peak; NOAA repository blocked): not verified.
- **FEMA Region II NY/NJ coastal study reports:** not opened, only described through Suro 2023.
- **USACE NJ Back Bays feasibility-study engineering appendices:** nap.usace.army.mil returned 403. Only ERDC TR-25-18 was read.
- **Nguyen, Tanaka & Nagabayashi (2007):** only through Dodet 2013 and Treloar 2011.
- **CoDEC (Copernicus coastal data), LISFLOOD-FP coastal applications beyond Vousdoukas 2016, and the NWS SLOSH and P-Surge technical pages:** not opened. The NHC SLOSH and P-Surge URLs returned "File not found".
- **O'Neill et al. 2018** (CoSMoS 3.0, JMSE; MDPI blocked); **Nederhoff et al. 2024a** (Salish Sea, Water 16:346; MDPI blocked); **van Ormondt et al. 2021** (runup formula, JMSE).
- **Where NJBB save points 2, 29, 36, 50 and 57 are** (TR-25-18). Not established.

---

## Bibliography (all opened in this session; tag = what was read)

1. Leijnse, T.W.B., van Dongeren, A., van Ormondt, M., de Goede, R., Aerts, J.C.J.H. (2025). The importance of waves in large-scale coastal compound flooding: A case study of Hurricane Florence (2018). *Coastal Engineering* 199:104726. https://doi.org/10.1016/j.coastaleng.2025.104726 (local PDF `refs/1-s2.0-S0378383925000316-main.pdf`). **FULL TEXT READ** (§1–5, App. A–B).
2. Leijnse, T., van Dongeren, A., van Ormondt, M. (2026). Fast modelling of wave-driven flooding for sandy and coral reef-lined coasts. In *Coastal Dynamics 2025*, Coastal Research Library 42, pp. 155–160. https://doi.org/10.1007/978-3-032-15477-4_25 (local `refs/978-3-032-15477-4.pdf`). **FULL TEXT READ**.
3. Ricondo, A., et al. (2026). Advancing compound coastal flood modeling on Southern O'ahu, Hawai'i: a hybrid stochastic approach. *Coastal Dynamics 2025*, pp. 3–7. https://doi.org/10.1007/978-3-032-15477-4_1. **FULL TEXT READ**.
4. Grimley, L.E., Sebastian, A., Leijnse, T., Eilander, D., Ratcliff, J., Luettich, R. (2025). *Water Resources Research* 61, e2023WR036727. https://doi.org/10.1029/2023WR036727 (local PDF + SI docx). **PARTIAL** (searched for wave treatment; §3.2, §5.4).
5. Parker, K., Erikson, L., Thomas, J., Nederhoff, K., Barnard, P., Muis, S. (2023). *Natural Hazards* 117:2219–2248. https://doi.org/10.1007/s11069-023-05939-6. **PARTIAL** (§3.2, §4, §6).
6. Nederhoff, K., et al. (2024). Tropical or extratropical cyclones… *Natural Hazards* 120:8779–8825. https://doi.org/10.1007/s11069-024-06552-x. **PARTIAL** (§3.2–3.4, validation, discussion; full-text search for the inlet relation). Preprint: https://eartharxiv.org/repository/object/5123/download/10138/ (searched).
7. Parker, K.A., et al. (2023). Nearshore parametric wave setup hindcast data (1979–2019) for the U.S. Atlantic coast. USGS data release https://doi.org/10.5066/P9BQQTCI. **FULL** (metadata). Carolinas release P9W91314 metadata (FloodHazards, WaterElevation). **PARTIAL**.
8. Hanslow, D.J., Nielsen, P. (1993). Wave setup on beaches and in river entrances. *Coastal Engineering 1992*, 240–252. https://doi.org/10.1061/9780872629332.018. **FULL TEXT READ**.
9. FEMA (2015). Guidance for Flood Risk Analysis and Mapping: Coastal Wave Setup (Guidance Document 44). https://www.fema.gov/sites/default/files/2020-02/Coastal_Wave_Setup_Guidance_Nov_2015.pdf. **PARTIAL** (§1, §2.1, §2.2.6.2, §3.2.2).
10. Dalinghaus, C., Coco, G., Higuera, P. (2023). A predictive equation for wave setup using genetic programming. *NHESS* 23:2157–2169. https://doi.org/10.5194/nhess-23-2157-2023. **PARTIAL** (§1–2, Table 3, §4–5).
11. Vousdoukas, M.I., et al. (2016). Developments in large-scale coastal flood hazard mapping. *NHESS* 16:1841–1853. https://doi.org/10.5194/nhess-16-1841-2016. **PARTIAL** (§2).
12. Eilander, D., et al. (2023). A globally applicable framework for compound flood hazard modeling. *NHESS* 23:823–846. https://doi.org/10.5194/nhess-23-823-2023. **PARTIAL** (§3.1.1, discussion).
13. Idier, D., Bertin, X., Thompson, P., Pickering, M.D. (2019). *Surveys in Geophysics* 40:1603–1630. https://doi.org/10.1007/s10712-019-09549-5. **PARTIAL** (§2, §3.4–3.6, §5).
14. Dodet, G., Bertin, X., Bruneau, N., Fortunato, A.B., Nahon, A., Roland, A. (2013). Wave-current interactions in a wave-dominated tidal inlet. *JGR Oceans* 118:1587–1605. https://doi.org/10.1002/jgrc.20146 (NORA copy). **PARTIAL** (abstract, §4 setup, Table 4, conclusions).
15. Wargula, A., Raubenheimer, B., Elgar, S. (2014). Wave-driven along-channel subtidal flows in a well-mixed ocean inlet. *JGR Oceans* 119. https://doi.org/10.1002/2014JC009839 (WHOI copy). **PARTIAL**.
16. Wargula, A., et al. (2018). Tidal flow asymmetry owing to inertia and waves on an unstratified, shallow ebb shoal. *JGR Oceans* 123. https://doi.org/10.1029/2017JC013625. **PARTIAL**.
17. Orescanin, M., Raubenheimer, B., Elgar, S. (2014). Observations of wave effects on inlet circulation. *Continental Shelf Research* 82:37–42. https://doi.org/10.1016/j.csr.2014.04.010 (author copy, WHOI). **PARTIAL**.
18. Aretxabaleta, A.L., Ganju, N.K., Defne, Z., Signell, R.P. (2019). Spatial distribution of water level impacting back-barrier bays. *NHESS* 19:1823–1838. https://doi.org/10.5194/nhess-19-1823-2019. **PARTIAL**.
19. Anonymous (about 2014). Barnegat Bay storm surge elevations during Hurricane Sandy and sources of surge flooding within the bay. Hosted at https://www.berkeleytownship.org/DocumentCenter/View/417. **FULL TEXT READ** (grey literature).
20. Al Azad, A.A., Marsooli, R. (2026). Quantifying wave setup climatology along the U.S. East and Gulf coasts using a coupled hydrodynamic-wave model. *Ocean Dynamics* 76:72. https://doi.org/10.1007/s10236-026-01829-0. **PARTIAL** (§1–2, limitations).
21. Cialone, M.A., et al. (2015). NACCS Coastal Storm Model Simulations: Waves and Water Levels. ERDC/CHL TR-15-14. https://usace.contentdm.oclc.org/digital/collection/p266001coll1/id/3681/. **PARTIAL** (ch. 3, 6, 7, 8).
22. Slusarczyk, G., Cialone, M.A., Nadal-Caraballo, N.C., Hampson, R.W. (2025). Numerical storm surge modeling and probabilistic analysis for evaluating proposed New Jersey Back Bays inlet closures. ERDC/CHL TR-25-18. https://hdl.handle.net/11681/49980. **PARTIAL** (§2.3–2.4).
23. Liu, Z., Wang, H., Zhang, Y.J., Magnusson, L., Loftis, J.D., Forrest, D. (2020). Cross-scale modeling of storm surge, tide, and inundation in Mid-Atlantic Bight and New York City during Hurricane Sandy, 2012. *ECSS* 233:106544. https://doi.org/10.1016/j.ecss.2019.106544 (OSTI accepted manuscript). **PARTIAL**.
24. Treloar, P., Taylor, D., Prenzler, P. (2011). Investigation of wave induced storm surge within a large coastal embayment — Moreton Bay (Australia). *Coastal Engineering Proceedings* 32. https://doi.org/10.9753/icce.v32.currents.22. **PARTIAL** (intro, regional setup, parametric model).
25. Kirezci, E., et al. (2020). Projections of global-scale extreme sea levels… *Scientific Reports* 10:11629. https://doi.org/10.1038/s41598-020-67736-6. **PARTIAL** (Methods, validation).
26. Vitousek, S., et al. (2017). Doubling of coastal flooding frequency within decades due to sea-level rise. *Scientific Reports* 7:1399. https://doi.org/10.1038/s41598-017-01362-7. **PARTIAL** (Methods).
27. Barnard, P.L., et al. (2019). Dynamic flood modeling essential to assess the coastal impacts of climate change. *Scientific Reports* 9:4309. https://doi.org/10.1038/s41598-019-40742-z. **PARTIAL** (Methods).
28. Storlazzi, C.D., et al. (2024). Forecasting storm-induced coastal flooding… Hawaiian, Mariana, and American Samoan Islands. USGS Data Report 1184. https://doi.org/10.3133/dr1184. **PARTIAL**.
29. McCall, R., et al. (2024). BEWARE-2. *NHESS* 24:3597–3625. https://doi.org/10.5194/nhess-24-3597-2024. **PARTIAL** (abstract, intro).
30. Roelvink, D., van Ormondt, M., Reyns, J., van der Lugt, M. (2025). SnapWave: fast, implicit wave transformation from offshore to nearshore. EGUsphere preprint. https://doi.org/10.5194/egusphere-2025-492. **PARTIAL**.
31. Leijnse, T.W.B., et al. (2024). Estimating nearshore infragravity wave conditions at large spatial scales. *Frontiers in Marine Science* 11:1355095. https://doi.org/10.3389/fmars.2024.1355095. **PARTIAL** (intro).
32. Nederhoff, K., et al. (2024c). Accounting for uncertainties in forecasting tropical-cyclone-induced compound flooding. *GMD* 17:1789–1811. https://doi.org/10.5194/gmd-17-1789-2024. **PARTIAL** (searched; limitations).
33. Muis, S., et al. (2016). A global reanalysis of storm surges and extreme sea levels. *Nature Communications* 7:11969. https://doi.org/10.1038/ncomms11969. **PARTIAL** (discussion).
34. Bates, P.D., et al. (2021). Combined modeling of US fluvial, pluvial, and coastal flood hazard. *WRR* 57, e2020WR028673. https://doi.org/10.1029/2020WR028673 (MIT mirror). **PARTIAL** (§2.2.3).
35. Soomere, T., et al. (2013). Mapping wave set-up near a complex geometric urban coastline. *NHESS* 13:3049–3061. https://doi.org/10.5194/nhess-13-3049-2013. **PARTIAL**.
36. Harvey, M.E., et al. (2020). Effects of elevated sea levels and waves on Southern California estuaries during the 2015–2016 El Niño. *Estuaries and Coasts*. https://doi.org/10.1007/s12237-019-00676-1. **PARTIAL**.
37. Sopkin, K.L., et al. (2014). Hurricane Sandy: observations and analysis of coastal change. USGS OFR 2014-1088. https://pubs.usgs.gov/of/2014/1088/. **PARTIAL**.
38. Suro, T.P., Niemoczynski, M.J., Boetsma, A., Niemoczynski, L.M. (2023). USGS SIR 2023-5005. https://doi.org/10.3133/sir20235005. **PARTIAL**.
39. FEMA Region II (about 2013). New York/New Jersey Coastal Advisory Flood Hazard (ABFE) report. https://feedback.region2coastal.com/…/NJ_NY_ABFE_Report.pdf. **PARTIAL** (§3.1).
40. NOAA NHC, Potential Storm Surge Flooding Map page. https://www.nhc.noaa.gov/surge/inundation/. **PARTIAL**.
41. Deltares SFINCS documentation (overview; input forcing; developments/changelog v2.4.0), https://sfincs.readthedocs.io/en/latest/. SFINCS source `source/src/sfincs_wavemaker.f90` and `sfincs_input.f90` at https://github.com/Deltares/SFINCS (main branch; tags v2.3.0_mt_Faber_release, v2.3.3). **FULL** (relevant parts).
42. Also skimmed with no setup content: McCallum et al. 2013 (USGS OFR 2013-1043, Sandy storm tide); Qu et al. 2021 (*Nat. Hazards* 105:2697, Sandy bridges); Marsooli & Lin 2021 (*Climatic Change*, Jamaica Bay).

**ABSTRACT ONLY** (publisher, USGS, OpenAlex or Crossref):
- Stockdon et al. 2006, https://doi.org/10.1016/j.coastaleng.2005.12.005
- Marsooli & Lin 2018, https://doi.org/10.1029/2017JC013434
- Irish & Cañizares 2009, https://doi.org/10.1061/(ASCE)0733-950X(2009)135:2(52)
- Tanaka & Tinh 2017, https://doi.org/10.1016/j.piutam.2017.09.003
- Raubenheimer et al. 2001, https://doi.org/10.1029/2000JC000572
- Apotsos et al. 2007, https://doi.org/10.1029/2006JC003549
- Aretxabaleta et al. 2014, https://doi.org/10.1002/2014GL059957
- Bennett et al. 2018, https://doi.org/10.1016/j.csr.2018.04.003
- O'Grady et al. 2019, https://doi.org/10.1029/2018JC014871
- Pearson et al. 2017, https://doi.org/10.1002/2017JC013204
- Anderson et al. 2021, https://doi.org/10.1029/2021EF002285
- Cagigal et al. 2024, https://doi.org/10.1016/j.ocemod.2024.102346
- Dietrich et al. 2011, https://doi.org/10.1175/2011MWR3611.1
- Dietrich et al. 2010, https://doi.org/10.1175/2009MWR2907.1
- Hope et al. 2013, https://doi.org/10.1002/jgrc.20314
- Serafin et al. 2017, https://doi.org/10.1002/2016GL071020
- Marcos et al. 2019, https://doi.org/10.1029/2019GL082599

Of these, Dietrich 2010 and 2011 and Hope 2013 were opened only to confirm what they study and their mesh spacing. Dietrich 2011: "100–200 m in the wave-breaking zones". **They give no setup numbers in the abstract.**
