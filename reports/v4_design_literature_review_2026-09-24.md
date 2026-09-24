# v4 design — literature review (2026-09-24)

What other groups do when they set up SFINCS (or a comparable compound-flood model) for
many storms and sea-level rise, read for three questions: where to put the inland edge,
how coarse the flow grid can be, and what makes the runs slow. The design rules drawn from
it are in STATUS PICK UP and `~/.claude/plans/hey-claude-we-are-goofy-reddy.md`.

| who | model / grid | inland limit | offshore | waves | SLR / cost |
|---|---|---|---|---|---|
| Nederhoff et al. 2024, *Nat. Hazards* 120:8779, doi:10.1007/s11069-024-06552-x — SE US Atlantic, Virginia → Florida; the USGS CoSMoS Atlantic release (doi:10.5066/P9BQQTCI) is its product | SFINCS **200 m** regular + 1 m subgrid, 5 domains, 10 m output | landward extent "manually determined to allow for minimal inflow boundary locations and typically reaches +10 m NAVD88" | ≈ −10 m NAVD88; water level imposed every ~500 m from a regional model | parametric setup; dynamic waves "computationally prohibitive" | 0/0.25/0.5/1/1.5/2/3 m; a 7-day event ≈ 41 min on one core; 80,000 events in 31 days |
| Leijnse 2025, PhD thesis VU Amsterdam "Riding the wave" (doi:10.5463/thesis.1031); Leijnse et al. 2025 *Coastal Eng.* (doi:10.1016/j.coastaleng.2025.xxxx, S0378383925000316) — Hurricane Florence, 1,000 km of the Carolinas | SFINCS **quadtree** (first use) + SnapWave | — | — | SnapWave + IG; "1.2 h per simulated day on 16 vCPU, 13.3 % in SnapWave, 1.5 % IG BC" | 1,000 km "30× faster than a traditional model covering 7 km" |
| Roelvink et al. 2025, *GMD* 18:9469 — SnapWave | cost ≈ 0.15–0.3 µs × nodes × directional bins × wave conditions; 4–6 iterations to converge | — | offshore ~800 m spacing is fine; nearshore 14–100 m; "for providing boundary conditions to coastline models typically a grid size of 100 m would be sufficient"; 40→10 m quadtree ≈ 1/6 the nodes of uniform fine | | Coast3D 340 k nodes: 1.9 s per wave field |
| van Ormondt et al. 2025, *GMD* 18:843 — subgrid corrections (the paper the user sent) | grids 5–500 m, subgrid 1 m, 20–100 vertical levels | — | — | — | subgrid 100 m ≈ regular 25 m (St. Johns M2 error 0.4 vs 2.6 cm; Harvey NSE 0.58 vs 0.35, "35 times faster"); **grid spacing must not exceed channel width** (meander flux error ∝ sinuosity^1.5); subgrid adds 38–128 % per cell but enables 35–50× coarser |
| USGS CoSMoS Southern California v3 (Barnard et al.) and Salish Sea 2024 (Water 16:346; pubs.usgs.gov/publication/70251492) | Delft3D → XBeach → SFINCS | Tier II grids "extend to the 10-m topographic contour; exceptions where channels … extend very far inland"; sub-domains overlap because "data near any model boundary are always suspect" | | XBeach profiles | 0–2 m in 0.25 m steps plus 5 m; Salish Sea: +1 m SLR takes Whatcom County annual extent 13 → 33 km² |
| Compound flood impacts from Hurricane Sandy on NYC in climate storylines, *NHESS* 24:29 (2024) | SFINCS 50 m, GTSM v4.1 forcing, NYC topobathy lidar + CUDEM + FABDEM + GEBCO | | | | +0.71 / +1.01 m added to the boundary → flood volume ×3 / ×4.2 |
| Climate change exacerbates compound flooding from recent tropical cyclones, *npj Nat. Hazards* (2024) — Floyd, Matthew, Florence | SFINCS 200 m + 5 m downscale, ADCIRC, 77,600 km² | HUC-based watersheds | | | SLR mean +1.12 m [0.68, 1.57] → exposed area **+119 %** (+1,651 ± 305 km²) |
| Xu et al. 2021 *Front. Mar. Sci.* 8:715557; *NHESS* 24:2461 (2024); *Sci. Data* 2025 (PNNL, FVCOM) — Delaware Bay estuary | FVCOM, 20 m tributaries – 100 m estuary – 25–40 km at the open boundary | **Trenton: "a hydraulic jump ~2.7 km downstream of the Trenton tidal gauge" marks the upstream limit of tidal intrusion** | 700–1,500 km offshore | | M2 amplitude 0.69 m at Lewes → 0.94 m at Newbold; tide–surge interaction +10–15 % on diurnals; river flow of 4–5.5 × 10³ m³/s damps semidiurnals up to 40 % upstream; favourable estuarine wind can double surge from the entrance to the upper estuary (~+2 m) |
| Gloucester City NJ / Delaware River, *NHESS* 26:571 and *HESS* 30:401 (2026) | SFINCS 10 m + 1 m subgrid, GPU (one RTX 4080), 5,000 runs | HUC-14 catchments; inland edges are outflow | forced at the **Philadelphia gauge**, i.e. an interior line — what v1.5 argued against for a converging estuary | | no SLR |
| NJ STAP 2025 (Rutgers NJ Climate Resource Center, Nov 2025 summary) | | | | | 2050: 0.9–1.7 ft (0.27–0.52 m); 2100 likely 1.8–3.3 ft low, 2.2–3.8 ft intermediate, 2.6–4.3 ft high; rapid ice loss extends to 3.7 / 4.5 / 5.2 ft (1.58 m). 2005 baseline. Philadelphia, Sandy Hook, Cape May in the appendices |
| Eilander et al. 2023, *NHESS* 23:823 — globally applicable compound flood framework (HydroMT-SFINCS) | 100 m, bounding box | | | | reproducible build from a config + data catalog |
| HydroMT-SFINCS quadtree builder (installed 2.0.0-rc2, `components/quadtree/quadtree_builder.py:287-309`) | refinement polygons × (zmin, zmax): a cell refines when its sub-cell elevation range intersects the gate | | | | so MOTF- or distance-to-water-driven refinement is a polygon *generator*, not a new mechanism |

## What the review settles

- **Inland edge ≈ +10 m NAVD88** is the standard for SLR-ready domains (CoSMoS, Nederhoff
  2024). Our own MOTF-wet land tops out at p99 7.6 m; Sandy + 2 m reaches ~10 m.
- **Coarse flow grid + fine subgrid** is the accepted trade (van Ormondt 2025), with one
  hard rule: cell ≤ channel width. Our FINDINGS §41 caveat is a *wave-setup* effect on
  bay margins, so 25 m survives only where SnapWave acts.
- **SnapWave cost = nodes × bins × iterations** (Roelvink 2025): the shelf band at 200 m
  and fewer directional bins are the levers; the bay adds flow cells only.
- **Delaware forced at the mouth, computed to Trenton**: the estuary amplifies tide and
  surge (PNNL), an interior boundary cannot produce that (the v1.5 argument).
- **Far banks computed, not walled**: nobody in the list walls a shoreline; CoSMoS
  explicitly distrusts data near any boundary. Marsh storage on the DE side and on
  Staten Island is what a wall would reflect, and the reflection grows with SLR.
- **SLR is a boundary offset** everywhere in the list, so the ring must already contain
  the future floodplain — hence the +10 m rule and the waves-off overflow test.
