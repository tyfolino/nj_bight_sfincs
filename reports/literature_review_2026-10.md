# Literature review — river boundaries, wave setup, and SnapWave cost (2026-09-30)

Written for the river / wave rethink (STATUS "Now"). It answers three questions:

- **A.** Where do compound-flood modellers end their rivers, and what do they put there?
- **B.** How is wave setup represented without running a wave solver everywhere?
- **C.** How is SnapWave configured in practice, and why does ours cost so much more?

The detail — verbatim quotes, page numbers and read status for about 110 sources — is in three
appendices under [`literature_review_2026-10/`](literature_review_2026-10/). This page is the
synthesis. It supersedes `v4_design_literature_review_2026-09-24.md`, whose table is carried
into §D below.

**How to trust it.** Each appendix tags every source FULL TEXT READ, PARTIAL (which parts) or
ABSTRACT ONLY, and keeps unverifiable claims in a separate list. The claims the conclusions
lean on were re-checked by hand against the source (§E). A statement marked *[inference]* is
ours, not a source's.

---

## The short version

1. **The North Carolina group did not model whole watersheds to the divides.** Grimley et al.
   cut their Carolinas SFINCS domain "downstream of large reservoirs" and fed it from nine
   USGS gauges. Upstream of that line the Upper Pee Dee enters as a gauge inflow. That is a
   cut-at-a-gauge model moved upstream, with rain on the grid below it. Its motivating storm
   (Florence) flooded 79 % of its area by runoff; Sandy in New Jersey was the opposite, and
   USGS says so: "widespread river flooding was not documented".
2. **Whole-watershed and far-inland models are consistently much worse inland than at the
   coast:** about 0.1 m at the coast against 0.6–0.9 m at inland high-water marks (Grimley,
   Nederhoff, Ye). Every group names the same cause — **river channel beds nobody surveyed** —
   which is exactly the problem v4's long river reaches have run into.
3. **Cutting at the head of tide (a dam, falls or weir) is the most common choice in estuary
   and surge studies,** including the Delaware (to Trenton) and the Hudson (to the Troy dam).
   Where it was tested in surge-dominated conditions, removing river flow moved coastal gauges
   by a few centimetres or ~2 %; the effect grows upriver. **Nobody has published a domain
   drawn from a future water level** the way v4 was, and nobody moved a river cut upstream for
   sea-level-rise runs — every SLR study reused its present-day domain. The SLR-ready norm is a
   **+10 m NAVD88 contour** with point inflows where rivers cross it.
4. **Wave setup added at the offshore boundary lifts everything** — the open-coast gauges and
   the bays alike. Our own Stockdon trial did that, and so did Leijnse et al. (2025, Florence)
   and Nederhoff et al. (2024, Duck +25 cm). Only setup generated *inside* the model, landward
   of the gauges, reaches the bays without lifting the coast. The "20 % of offshore Hs" rule is
   the worst on record (Florence back-bay bias +0.96 m) and misapplies a breaking-height ratio.
5. **NACCS already carries wave setup** (ADCIRC coupled to STWAVE by radiation stress, 200 m
   STWAVE grids), including in the NJ back bays (10–30 % of still-water level at NJ Back Bays
   save points, per ERDC TR-25-18 — not re-checked by me). No setup treatment should be
   expected to close the observed 0.2–0.55 m back-bay superelevation: along-bay wind setup
   and overwash are the published mechanisms for Sandy.
6. **Our SnapWave cost is configuration, not physics.** Leijnse's 13 % (vs our 97 %) came from
   ~18 direction bins over 180°, no wind growth, a warm start and 1.4 M nodes; we run 72 bins
   over 360°, wind growth, a cold start every call and 2.9 M nodes. Nobody runs the SnapWave
   sweep in parallel. Deltares' own practice with wind is 360°, so the sector should stay; the
   direction resolution, update interval and shelf-band resolution are the levers.

---

## A. Where rivers end

### What the field does

| rule | who | notes |
|---|---|---|
| **Elevation contour**, rivers enter as point inflows where they cross it | Nederhoff 2024 (SFINCS, +10 m NAVD88), Ye 2021 & NOAA STOFS-3D (SCHISM, 10 m), FEMA Region II ADCIRC (25 ft) | the usual "SLR-ready" shape; justified by present-day backwater reach |
| **Head of tide** (dam, falls, weir) | Yin 2021 & Deb 2025 (Delaware → Trenton), Orton 2020 (Hudson → Troy dam), Kumbier 2018 | the modal estuary choice; the Delaware's head of tide is a bedrock "weir" ~2.7 km below the Trenton gauge (Zhang 2020) |
| **A stream gauge** | Harrison 2022, Lyddon 2024, Loveland 2021, Bilskie 2021, Muñoz 2024 | often well above the tidal limit |
| **Below the last regulating reservoir**, watershed below it rain-on-grid | Grimley 2024/2025 (the NC group), Sebastian 2021 (Houston) | "SFINCS cannot directly represent reservoir management" |
| **HUC unit or drainage connectivity** | Sebastian 2021, Eilander 2023, the Gloucester City NJ SFINCS papers (2026) | Gloucester City forces the Delaware from the Philadelphia gauge |

**At the cut:** gauge discharge (most), gauge flow scaled by drainage area to an ungauged cut
(Orton 2020 / the Stevens NYHOPS system on our own harbour — the closest analogue to v4's
area scaling), a hydrological model (NWM, CaMa-Flood, DHSVM), or rain on the grid for
everything inside. Deb 2025 dropped every stream below a p99.5 peak of 100 m³/s outright.

### Does the cut's position matter?

Thinly tested. Zhang 2020 (Delaware, SCHISM, boundary at 10 m) found surge backwater reached
the boundary, but the effect was "a few centimeters in most places", tens of cm in isolated
spots. Loveland 2021 chose its inflow by a sensitivity test and reported only the rule.
River on vs off: a few cm at the coastal gauge in surge-dominated cases (Kumbier; Orton 2012:
2 % at the Battery, 9 % 14 km up the Hudson), growing upriver; upriver flood extent can
change by 30 % (Kumbier). **No Sandy river-on/off study exists for the Raritan, Passaic or
Hackensack.** USGS (Suro et al. 2016, re-checked): the rain "did not cause major inland
riverine flooding"; storm totals 1.60 in at Bound Brook, 1.33 in at Little Falls; Trenton
peaked near 800 m³/s against 4,000–5,500 for Irene and Lee (Xiao 2021). The surge "forced
water up the Raritan River" into Sayreville (NHC).

### River beds where nobody surveyed

Power-law hydraulic geometry burned as a rectangle (Eilander), gradually-varied-flow inversion
(Neal 2021, Bates 2021), lidar minus a constant (Grimley SC: −2 m; Harrison: −3 m with
"glass walls" on the banks — the closest precedent to v4's walled cuts), **hand-calibrating
the bed against stage gauges because lidar reads flat water** (Lyddon 2024 — our CUDEM
problem exactly), or HEC-RAS geometry from existing state models (Grimley NC, the best
performer; whether NJ has equivalents for the Raritan / Passaic / Millstone is unverified).
Measured sensitivity: removing channels cost 0.19 m of peak error (Grimley, re-checked);
river depth ±50 % left CSI unchanged in extreme floods (Eilander) — depth matters most at
low-to-moderate flows, which is Sandy's case.

### Outflow edges

SFINCS outflow cells hold depth at zero: a perfect sink. The NC, Eilander and Gloucester City
models use them at their inland edges; nobody reports how much water they remove. **A leak
budget like ours (FINDINGS §50: ~40,000 m³/s out of v3's edge at the peak) is not in the
literature.**

### Sea-level rise

Every study read ran SLR on its present-day domain (Nederhoff to +3 m, Grimley +1.12 m,
Goulart, Orton, Harrison, Santiago-Collazo). Warnings that this can bite are indirect: a fixed
boundary stops the transition zone moving inland (Santiago-Collazo 2021); under SLR water
arrives over land "not presently included in some fluvial flood models" (Mita 2023);
deepening moves the river/sea crossover upstream (Familkhalili 2022). Where the head of tide
is bedrock or a dam (Trenton, Troy), SLR moves it little; Orton 2020 find SLR damped 30–60 %
near Albany in wet storms.

### What it implies (neutral)

- **Head-of-tide cut** has the most precedent for a surge-dominated estuary and removes most of
  v4's bed-data problem (above head of tide is where the beds are unsurveyed). Cost: whatever
  the +3 m water does above today's head of tide is not computed.
- **Whole watersheds** buy rain-driven attribution, which Sandy does not need, at the price of
  inland errors the literature puts at 0.6–0.9 m. Even the NC group stopped at the reservoirs.
- **Middle paths with precedent:** (i) a +10 m contour domain with point inflows (SLR-ready by
  construction; channels still needed to the contour); (ii) a head-of-tide cut plus a cheap
  walled corridor above it where SLR needs room (Harrison's glass walls; Zhang extended only
  the Delaware); (iii) a head-of-tide domain for Sandy and a separate, extended SLR domain —
  no published instance, and no evidence either way that it is needed where the head of tide
  is structural.
- **Silent in the literature:** a leak budget for outflow edges; a domain drawn from a future
  water level; the sensitivity of estuary levels to where a gauge inflow is placed.

---

## B. Wave setup without a wave solver

| treatment | what it gets right | what it gets wrong | evidence |
|---|---|---|---|
| **SnapWave (a stationary solver in the flow model)** | setup where it is made and its export through inlets; bay wind-sea | cost (ours) | Florence back bays R² 0.75, RMSE 0.24 m, bias −0.07 (Leijnse 2025, re-checked) |
| **Stockdon (2006) at the offshore boundary** | order of magnitude at beaches | lifts the whole domain: Florence depth errors +1 / −0.5 m by region; our trial lifted the Atlantic City pier 0.3 m | Leijnse 2025; our `BRACKET+setup-stockdon` (FINDINGS §57) |
| **0.2 × offshore Hs** | nothing on a wide shelf | Florence back-bay bias +0.96 m, levels "by 2 m" too high (re-checked); a breaking-height ratio applied to offshore Hs | Leijnse 2025; FEMA 2015 |
| **Parametric inlet setup** (Hanslow & Nielsen; Tanaka & Tinh; Irish & Cañizares 2009 for Long Island) | the right size: deep, jettied entrances pass 0.2–4 % of offshore H; our +0.11 m bay lift is ~1 % of Sandy's Hs *[inference]* | one number per inlet; nowhere natural to inject it in SFINCS | appendix B |
| **Regression of setup from coupled runs** (Treloar 2011; ERDC TR-25-18 on NACCS) | cheap corrections, R² > 0.96 | a post-run point correction; no flooding dynamics | appendix B |
| **1D transects** (FEMA DIM, CoSMoS XBeach) | open beaches | cannot represent inlets or export into bays | FEMA 2015; USGS DR 1184 |
| **Nearshore line forced with a setup series** (SFINCS wavemaker `wstfile`) | setup only landward of the line, so offshore and pier levels untouched | no radiation stress on ebb shoals or in inlet throats; no bay wind-sea; **no published test of this use** | SFINCS source; Leijnse 2025 App. B |
| **Ignore setup** | — | ~0.1–0.15 m low in bays (Florence −0.15 m; our 0.11 m lift) | Leijnse 2025; FINDINGS §48 |

**Setup in back bays.** The mechanism is breaking over ebb shoals raising the lagoon (Dodet
2013; Idier 2019): 7–15 % of offshore H in shallow narrow inlets, far less in deep trained ones.
For **Sandy in NJ/NY back bays** the published drivers are different: along-bay wind setup
("largest influence" in Great South Bay, Bennett 2018; > 0.2 m in Barnegat, Aretxabaleta 2019)
and overwash (≈ the inlet inflow in Great South Bay; about 1 ft in Barnegat per a local
technical note). **No setup treatment should be expected to close the 0.2–0.55 m back-bay
superelevation** (FINDINGS §57).

**Sandy's wave contribution overall:** 0.1–0.3 m (5–10 %) at the Battery, largest in Newark
Bay, the upper harbour and Jamaica Bay (Liu 2020, which counts wave-dependent wind and bottom
stress too); setup < 17 % of peak storm tide in the most extreme events (Marsooli & Lin 2018,
abstract only).

**NACCS.** Its ADCIRC is coupled two-way to STWAVE (200 m grids, which its report says resolve
the surf zone; ADCIRC 70–200 m at the NJ inlets). With Hs ~9–10 m at the buoys, breaking near
−10 m is plausible, so our boundary likely already carries some setup *[inference]*. A NACCS
waves-off Sandy run, if one exists, would measure it.

---

## C. SnapWave in practice

| | Leijnse 2025 (Florence) | ours (v3 premier) |
|---|---|---|
| engine | v2.1.1 | v2.3.3 + our direction patch |
| wave nodes | 1.4 M (1,600 m offshore → 25 m) | 2.89 M (1.12 M SnapWave-only shelf cells, 74 % at 50 m) |
| direction bins | not stated; the v2.1.1 source fixes the sector at 180° → 18 bins at the 10° default | 72 (5° over 360°) |
| wind growth | none possible in v2.1.1 | on |
| start of each call | warm (previous field) | cold (reset every call) |
| update | 30 min | 30 min |
| per call | 5–10 s | median 453 s |
| share of run | 13.3 % | 97 % |

Roelvink et al. (2025) give ~0.15–0.3 µs per node, direction bin and wave condition (cold
start, no wind, no IG), converging in 4–6 iterations; they found wave height "little sensitive"
to direction resolution and used 10° (360° at Ameland). Their paper excludes wind growth ("in a
forthcoming paper"), so **no published convergence cost for wind growth exists**. Upstream has
no parallel SnapWave sweep in any version, and no issue or PR proposing one. On our open issue
(#362) a SFINCS developer wrote that with wind on "we always set … 360 instead of 180 degrees";
a PR opened 2026-09-30 (#371) carries our direction fix. HydroMT's description of
`snapwave_nrsweeps` does not match the engine.

**Levers, ranked by the literature and our log (FINDINGS §20):** direction bins 5° → 10° with
360° kept (~2×); `dtwave` 3600 s (~2×; no published sensitivity through a peak); a coarser
SnapWave-only shelf band (~1.5×; a domain change); IG off (small; a null without a wavemaker);
several arms per node at fewer threads (throughput); v2.4.x's warm start (1.2–2× estimated, but a
breaking-physics epoch, FINDINGS §47). Not recommended for Sandy: a 180° sector (clips energy
more than 90° from the domain-mean wind, which rotates across the domain). Not a lever: the
iteration cap. Rejected: wind off (removes the 0.2–0.5 m bay fetch waves) — though it is worth
measuring what it costs on the fixed engine, which is why it is among the cost tests.
**Alternatives** (HurryWave, offline SWAN forces, XBeach transects, look-up tables): none is a
drop-in; SFINCS has no input for an external wave-force field.

---

## D. Carried from the 2026-09-24 v4 design review

| who | model / grid | inland limit | waves | SLR / cost |
|---|---|---|---|---|
| Nederhoff et al. 2024, *Nat. Hazards* 120:8779 (SE US; USGS CoSMoS Atlantic) | SFINCS 200 m + 1 m subgrid | "typically reaches +10 m NAVD88" | parametric setup; dynamic waves "computationally prohibitive" | 0–3 m; 7-day event ≈ 41 min on one core |
| Leijnse et al. 2025, *Coastal Eng.* 199:104726; thesis 2025 | SFINCS quadtree + SnapWave | — | SnapWave + IG, 13.3 % | "30× faster than a traditional model covering 7 km" |
| Roelvink et al. 2025, *GMD* 18:9469 | SnapWave | — | cost ∝ nodes × bins × conditions; 100 m enough for boundary supply | — |
| van Ormondt et al. 2025, *GMD* 18:843 | subgrid 5–500 m | — | — | subgrid 100 m ≈ regular 25 m; **cell ≤ channel width** |
| USGS CoSMoS S. California / Salish Sea | Delft3D → XBeach → SFINCS | the 10 m contour, exceptions for long channels; "data near any model boundary are always suspect" | XBeach profiles | 0–2 m + 5 m |
| Goulart et al. 2024, *NHESS* 24:29 (NYC Sandy storylines) | SFINCS 50 m | — | — | +0.71 / +1.01 m → flood volume ×3 / ×4.2 |
| Grimley et al. 2024, *npj Nat. Hazards* 1:45 (Carolinas) | SFINCS 200 m + subgrid | below reservoirs, rain-on-grid | none | SLR +1.12 m → exposed area +119 % |
| Xu et al. 2021; Xiao 2021; Deb 2025 (PNNL FVCOM, Delaware) | FVCOM | tidal limit ~2.7 km below the Trenton gauge | — | M2 0.69 m at Lewes → 0.94 m at Newbold |
| Gloucester City NJ, *NHESS* 26:571 / *HESS* 30:401 (2026) | SFINCS 10 m + 1 m subgrid, GPU | HUC-14, outflow edges | — | forced at the Philadelphia gauge |
| NJ STAP 2025 (Rutgers) | — | — | — | 2100 likely 1.8–3.3 ft (low) … 2.6–4.3 ft (high) |
| Eilander et al. 2023, *NHESS* 23:823 | HydroMT-SFINCS 100 m | connectivity; inflow where rivers ≥ 100 km² cross the edge | 0.2 Hs at the boundary | — |

---

## E. What was re-checked against the source by hand (2026-09-30)

| claim | source | how |
|---|---|---|
| NC domain cut "downstream of large reservoirs"; outflow cells "where inter-basin flow might occur"; SC beds = lidar − 2.0 m | Grimley et al. 2025, SI §S1 (local `refs/`) | text of the .docx |
| removing channels "increases the average peak error by 0.19 m"; 78,007 km² | Grimley et al. 2025 (local PDF) | text, pp. 2, 12, 14 |
| 13.3 % of 6.12 h on 16 vCPU; 5–10 s per solve; back-bay R² 0.75 / RMSE 0.24 m; 20 %-Hs levels "by 2 m" too high; "to avoid double counting" | Leijnse et al. 2025 (local PDF) | text, pp. 12–13 |
| "did not cause major inland riverine flooding"; "widespread river flooding was not documented" | Suro et al. 2016, USGS SIR 2016-5085 | downloaded PDF, pp. 16–17 |
| v2.1.1 sector fixed at 180°, no wind term; v2.3.3 resets the field every call; `main` warm-starts; no OpenMP / OpenACC in the v2.3.3 SnapWave solver | SFINCS source trees | read directly |
| NJ back-bay setup 10–30 % of SWL in NACCS | ERDC TR-25-18 | **not re-checked** (landing page is script-only) — as reported by appendix B |

Everything else is as reported in the appendices, with their read-status tags. Their
"not verified" lists (Saleh 2017 on the Passaic / Hackensack in Sandy; the NACCS mesh's inland
extent; the "Nederhoff 2024b" inlet relation, which could not be found in print; head-of-tide
dam crests on the Raritan / Passaic / Hackensack) are the open reading list.
