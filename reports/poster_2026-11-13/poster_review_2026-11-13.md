# Poster review, 2026-11-13 (independent, read-only)

Reviewed: `reports/poster_2026-11-13/poster_draft_2026-11-13.pptx` (via its preview png), `poster_text.md`,
`lit_check.md`, the three figure READMEs, `docs/MODEL.md`, `logs/floodmap_fix_2026-11-12/`,
`logs/motf_classify_v11_2026-11-12/READ.md`, `logs/power_exposure_2026-11-02/README.md`, `docs/STATUS.md`,
plus a web check. Folded in: the two user decisions (FEMA scores = rain ON; impact-model figure is coming)
and the layout correction (map + FEMA in one figure; HWM scatter on its own).

## Three things to act on before printing

1. **"First SFINCS implementation for coastal New Jersey" is NOT defensible as worded.** Published SFINCS
   models already exist inside New Jersey (Hoboken; Gloucester City; and NYC-metro "including parts of New
   Jersey"). `lit_check.md`'s line "No SFINCS model of New Jersey turned up in any search" is now wrong.
   What holds is the SCALE: no coast-wide SFINCS model of New Jersey was found. Wording in section 3.
2. **The abstract's "30 assets at 1.2 m of sea-level rise" is from an older bed and an older model than
   everything else on the poster**, and it is a still-water (bathtub-style) fill, not a model run. It can
   stay, but label it. Details in section 1.
3. **Placeholders still on the poster:** "Ty Janoski and [co-authors]", "[Department]", and two red
   "[verify …]" tags in References. Confirmed citations in section 5.

---

## 1. Numbers in the submitted abstract

| abstract says | current value | source and conditions | action |
|---|---|---|---|
| "Verrazzano Narrows to Cape May and extends up the Delaware Bay and River" | True, incomplete. Model also computes the Raritan (to head of tide), Newark Bay, the Arthur Kill. Delaware is the TIDAL river (cut at head of tide, Trenton). Hudson waterfront and Upper Bay are NOT in the model. | `docs/MODEL.md` lines 12–13, 64, 70, 183 | Optional: "…up Delaware Bay and the tidal Delaware River, the Raritan and Newark Bay". Never say "entire coast" or "statewide". |
| "maximum resolution of 25 m" | 25 m finest cells (25 / 50 / 100 / 200 m quadtree); 3,965,303 active cells ("about 4 million") | `docs/MODEL.md` l. 71–72; `README_fig1_fig2.md` | OK. "finest resolution" reads better than "maximum". |
| "3 m sub-grid topography" | 3.125 m | `docs/MODEL.md`; `logs/floodmap_fix_2026-11-12/README.md` | "about 3 m" or "3 m" is fine in an abstract; the Methods table already says 3.125 m. |
| "RMSE of 0.36 m relative to 119 USGS high-water marks" | **0.348 m → "0.35 m"**; bias −0.07 m; 93 % within ±0.5 m; n 119, 0 dry | `logs/floodmap_fix_2026-11-12/rows/v4_refreeze_swz_v11__p4-premier+weir-elizabeth-rahway.csv` (`hwm_rmse_scored_m` 0.34845). Estimator: median of flooded pixels within 50 m, native 3.125 m map, Model 1.1.0 rain on, 1.x mark file | Change 0.36 → 0.35. |
| "reproduces more than 86 % of FEMA's mapped surge extent" | **POD 0.868** (rain on); CSI 0.802, FAR 0.086. Hit 1,201 / miss 183 / false alarm 113 km² | same row; reproduced to 1e-9 by job 63851106 (`logs/motf_classify_v11_2026-11-12/READ.md` self-check table). NJ land only, inside the model; 2,412.7 km² of non-NJ land not scored | Wording stands. User decision: the poster's FEMA figure, tiles and captions switch to this run (see below). |
| "one-third of New Jersey assets in the domain are flooded by Sandy's floodwater" | **60 of 182 = 33 %** on 2012 ground, Model 1.1.0 (34 plants, 26 substations). On the estimated 2026 ground: **52 of 182 = 29 %**. | `reports/poster_2026-11-13/exposure_v110.log`, `exposure/changes_2012_vs_2026.txt`, `README_fig4.md`. "Flooded" = any normally-dry pixel on the site ≥ 0.15 m, native 3.125 m, buildings burned | "One-third" is right for 2012 ground. Say which ground. 182 = sites the model computes; 71 more of the 253 in the region are at the model's edge and unknown, not dry. README says quote 60 as "about 60". |
| "an estimated present-day coastline with 1.2 m of sea-level rise alone would flood 30 assets at high tide" | **30 of 182 NJ sites wet** (19 plants, 11 substations); only 6 are wet on half their land or more | `logs/power_exposure_2026-11-02/README.md` (table "+ 4 ft, all"), `docs/STATUS.md` l. 60, 65 | See the note below: keep, but label it. |

**What "30 at high tide" actually is.** Still water at VDatum MHHW (mean higher high water, which varies
along the coast) + 4 ft = 1.22 m, spread over land that connects to the sea through the model's sills and
levees. No storm, no waves, no model solve. The ground is the FIRST 2026 estimate (`bed-modern`, on the
Model 1.0.0 domain `v4_refreeze_swz`, read 11-03). That is not the 2026 ground behind the poster's
"52 of 182" (`_subgrid_modern2026b` on the 1.1.0 domain, with the Elizabeth / Rahway / Port Monmouth
defences). **No newer number exists:** the re-issue on the current 2026 ground
(`bed-modernb+still-4ft+weir-normalweather`, job 63853850, `logs/mhhw_v2_2026-11-12/`) started 11-13 05:08
and has not finished. Also on record: the hydrodynamic tide version of the same maps floods LESS along the
Delaware River and some back bays (high tide reads 0.1–0.45 m below VDatum there, STATUS l. 61), and its
asset count has not been read. So:

- Safe abstract wording: "…while 1.2 m of sea-level rise alone would put about 30 of them in water at high
  tide (still-water estimate on a first estimate of today's ground; preliminary)."
- Don't put "30" in a headline box. One line in Results or Future Work is enough.
- "High tide" = mean higher high water. Fine for this audience.

**FEMA scores: switch to rain ON everywhere (user decision).** One run now carries both checks, which is
the cleanest story: Model 1.1.0, rain on, RMSE 0.35 m and POD 0.87 / CSI 0.80 / FAR 0.09. Every place the
current poster says otherwise:

- Abstract box: "matches 85 % of FEMA's flooded area (critical success index, CSI, 0.82, rain off)" → use
  the submitted sentence ("more than 86 %").
- Fig 2 score strip: 0.82 / 0.85 / 0.03 → **0.80 / 0.87 / 0.09**.
- Fig 2 caption: "(rain-off twin of Model 1.1.0)… With rain on: …" → reverse it.
- Methods bullet "scored on the rain-off twin" → "Model 1.1.0".
- Conclusion 2 "CSI 0.82 (rain off)" and the tile "0.82 CSI (rain off)".
- The FEMA map itself must be re-drawn from the rain-on classes: the cached raster exists
  (`/scratch/tpj8/poster_2026-11-13/fig3/v4_refreeze_swz_v11__p4-premier+weir-elizabeth-rahway__motf_classes.tif`,
  11-12 14:22), and `fig3_motf_standin_v110.png` is already that figure in the old layout. Inset CSIs change
  too (the stand-in had Hoboken / Newark Bay 0.70, Barnegat 0.87): re-read them from the re-draw, don't
  copy the rain-off insets (0.70 / 0.88 / 0.66).
- My call on the rain-off aside: keep ONE caption clause, because it explains the pink: "About 60 % of the
  false alarms are rain ponds with no path to the sea; FEMA mapped surge only. Without rain: CSI 0.82,
  POD 0.85." (71.1 of 113.3 km² are disconnected, READ.md self-check table.) Drop it if space is tight.
- `logs/motf_classify_v11_2026-11-12/READ.md` l. 229 flags a stale "CSI 0.80" in takeaway 2. With the
  switch back to rain on, 0.80 is right again.

Other numbers on the poster I checked and found consistent with their sources: 61 inflows, 46 gauges,
RMSE 0.24 m without the five lake marks (n 114), 2012 → 2026 changes (10 sites: 9 go dry, 1 goes wet;
plants 34 → 25, substations 26 → 27), 253 / 182 / 71.

## 2. The impact-model claim

**Nothing in the repo backs it.** A search of `docs/`, `logs/`, `share/`, `scripts/` and `reports/` for
FIAT / damage finds only: `docs/STATUS.md` l. 67 ("Later — FIAT output (user 11-05)": the depth must be
interpolated to each building's centroid; "still to do when FIAT comes back"), `scripts/export_share_floodmap.py`
(the bare-ground depth export made for it) and `share/sandy_hmax_v4_refreeze_swz_p4-premier_bareground_*`
(a Model 1.0.0 depth map sent out). No damage numbers, no figure, no FIAT config. As of this review no new
file has landed in `reports/poster_2026-11-13/`.

The user says they have the results and will drop them in. Then the abstract sentence stays. Three checks
when the figure arrives, because I can't make them:

- **Which flood map fed it?** The only depth product the repo shows going out is Model **1.0.0**
  (`v4_refreeze_swz` / `p4-premier`, bare ground). If the damages come from that, the caption must say
  "Model 1.0.0 depths" (1.0.0 scores RMSE 0.435 m on its own mark file, vs 0.35 for 1.1.0), or the poster
  will imply 1.1.0.
- **Depth at buildings.** STATUS l. 67 says the centroid interpolation is not built; on the buildings-burned
  map a footprint reads dry or shallow. Ask whether depths were taken from the bare-ground map.
- **Credit and scope.** Name the impact model and who ran it; say what is counted (which towns, which
  building inventory, 2012 or today's buildings). Give 1–2 numbers only, labelled preliminary.

If the figure does not arrive in time: keep the abstract sentence but soften to "We are also coupling…",
and put it under Future Work as "in progress with [collaborators]". Don't print a damage number that has
no file behind it.

## 3. Novelty

**Prior SFINCS work in or next to New Jersey (all found and opened today):**

| study | what | where | overlap with us |
|---|---|---|---|
| Amini, Marsooli, Orton, Kasaei & Hajj (2026), *Urban Climate* 65, 102771, doi:10.1016/j.uclim.2026.102771 | SFINCS at 1.5 m, compound flooding with sea-level rise and heavier rain; checked against Ida (2021) flood reports | **Hoboken, NJ** (Stevens) | A SFINCS model on the NJ coast, in the one stretch (Hudson waterfront) that ours does not cover. Read: publisher record + abstract only. |
| Maduwantha, Wahl, Santamaria-Aguilar, Jane, Dangendorf, Kim & Villarini (2026), *HESS* 30, 401–420, doi:10.5194/hess-30-401-2026 | SFINCS (10 m, 1 m subgrid) driven by statistical compound events; qualitative check only | **Gloucester City, NJ** (tidal Delaware; Newton and Little Timber Creeks) | A SFINCS model inside our domain. The model setup is credited to Pollack et al. (2025), which I did not open. |
| Goulart et al. (2024), *NHESS* 24, 29–45, doi:10.5194/nhess-24-29-2024 | SFINCS at 50 m, **Hurricane Sandy** storylines, tide + surge + rain; flood output not validated in the text read | NYC metro "including parts of New Jersey and Connecticut" | A SFINCS Sandy run touching NJ. Already row 17 in `lit_check.md`. |
| Jane, Wahl, Maduwantha & Villarini (2026 preprint), EGUsphere-2026-5872 | Rainfall–surge statistics; names SFINCS as the kind of model the boundary conditions are for | Mullica River Basin, NJ | **Not a SFINCS model** in the first 8 pages I read. Don't cite it as one. |
| Leijnse et al. (2025) *Coastal Eng.* 199; Grimley et al. (2025) *WRR*; Nederhoff et al. (2024) *Nat. Hazards* | Regional SFINCS models (Carolinas; Virginia to Florida) | not NJ | Show that coast-scale SFINCS is established elsewhere. From `lit_check.md`; not re-opened today. |

Not found: any SFINCS model covering the New Jersey coast as a whole, the Atlantic shore and back bays, or
Delaware Bay. Searches covered SFINCS with New Jersey / Sandy / Barnegat / Delaware Bay / Atlantic City /
New York Bight / USGS / Deltares / NOAA. This was a web search, not a database search; conference abstracts
and agency grey literature are not covered, and an unpublished Deltares / USGS / Stevens / Princeton model
is the likeliest unknown.

**Verdict.** "First SFINCS implementation for coastal New Jersey": no. "First coast-wide SFINCS model of
New Jersey", with "to our knowledge": yes, as far as I could find.

**Recommended novelty sentence (use this):**

> To our knowledge, NJ-SFINCS is the first SFINCS model to cover the New Jersey coast as a whole, from the
> Narrows to Cape May and up Delaware Bay; earlier SFINCS studies in the state model a single city.

Safer still, no priority claim: "NJ-SFINCS brings the SFINCS flood model, so far used in New Jersey for
single cities, to the whole New Jersey coast."

Keep from the old traps: "New Jersey coast", not "statewide" (a Stevens reader will know Hoboken is not in
it); credit NACCS for the ocean boundary.

## 4. Reframe: section by section

**Layout (same three columns, four figures as the user set them).**

- Left column: Abstract (submitted text, about the same length as now), Introduction (shorter than now),
  Conclusions / Future Work.
- Middle column, Methods: the setup table, then **Fig 2 = HWM scatter on its own** (`fig2_hwm.png` already
  exists as a standalone, 11-12; check it still reads 0.35 / −0.07 / 93 % / n 119), then the two scoring
  bullets and credits. The map leaves this column, which pays for the scatter.
- Right block, Results: top row **Fig 1 = (a) model grid, boundary, inflows, gauges + (b) flood extent vs
  FEMA, rain on, with zoom insets**, full width of the block, score strip under (b). Bottom row: **Fig 3 =
  power plants and substations** (drop its Newark Bay inset if width is short; keep the 52 / 130 / 71
  counts) beside **Fig 4 = the impact figure**, each with a two-line caption.
- To make room: cut the "What the figures show" box to three one-line definitions (CSI / POD / FAR; "floods"
  = ≥ 0.15 m on site; "today's ground") folded into the captions, and shrink the four tiles to one row.
- Fig 1 caveat for whoever draws it: panel (a) and (b) need the same map extent and the high-water marks can
  come off (a), since Fig 2 shows them.

**Title** (submitted): *NJ-SFINCS: A compound flood model for coastal New Jersey for power-grid and
community risk*. Fill in co-authors and department.

**Abstract** (submitted text, numbers updated, two clauses tightened; changes in bold):

> Coastal flooding in New Jersey often comes from multiple sources, including storm surge, waves, rainfall,
> and river flow. Here, we present NJ-SFINCS, a high-resolution compound flood model for the New Jersey
> coast, built on the computationally efficient SFINCS flood model. NJ-SFINCS covers the coast from the
> Verrazzano Narrows to Cape May and extends up the Delaware Bay and River, with a maximum resolution of
> 25 m over a 3 m sub-grid topography. We test the model using Hurricane Sandy (2012): simulated peak water
> levels have an RMSE of **0.35 m** relative to 119 USGS high-water marks, and NJ-SFINCS reproduces more
> than 86% of FEMA's mapped surge extent. We also overlay present-day substations and power plants, finding
> that one-third of New Jersey assets in the domain are flooded by Sandy's floodwater **(60 of 182)**, while
> an estimated present-day coastline with 1.2 m of sea-level rise alone would flood **about 30** assets at
> high tide **(still-water estimate)**. Additionally, we couple these flood depths with an impact model to
> estimate damage to individual buildings, linking storm and sea-level rise scenarios to neighborhood-scale
> impacts.

**Introduction** (6 sentences):

> New Jersey's coast floods from the ocean, the bays, the rivers and the sky, and Hurricane Sandy (2012)
> showed what that costs homes and the power grid (Blake et al. 2013; Suro et al. 2016). Planning for the
> next storm, and for higher seas, means running many "what if" cases, not one. Detailed coastal models are
> accurate but slow, which limits how many cases can be run. SFINCS is a fast flood model that keeps the
> physics that matters for flooding and has been used along other U.S. coasts (Leijnse et al. 2021).
> NJ-SFINCS brings it to the whole New Jersey coast: a 72-hour storm on about 4 million cells runs in about
> 3 hours on one 64-core computer, with surge, waves, rain and rivers all included. We check it against
> Hurricane Sandy, then use it to ask which power plants, substations and buildings flood.

Followed by the novelty sentence from section 3 in red, replacing the current red paragraph.

Speed claim: 2.51 h on 64 threads (5.44 h on 16) for the full waves-on run of Model 1.0.0 on the production
engine; 1.1.0 itself took 4.09 h on 32 threads (`docs/MODEL.md` §7). "About 3 hours" is safe; see section 5. Don't print "100× faster than Delft3D": the repo's own
note says that figure is from a thesis and the paper's number is unchecked.

**Methods.** Keep the table. Change the "Model" row to "NJ-SFINCS: SFINCS v2.3.3 …", and move "Speed" to
the top row or bold it. Bullets:

- Marks: median peak water of flooded ground within 50 m of each mark, on the 3 m flood map.
- Extent: model flooded = peak depth ≥ 0.15 m; 15 m cells; New Jersey land inside the model.
- Both scores are from the same run (Model 1.1.0, all forcing on).

**Results headline tiles** (one row): "**~3 hours** per 72-hour storm, one 64-core computer" (first) ·
"**0.35 m** RMSE at 119 high-water marks" · "**86 %** of FEMA's mapped surge extent reproduced" ·
"**60 of 182** power plants and substations flood in Sandy (52 on today's ground)" · one impact number when
it arrives.

**Conclusions (3):**

1. **NJ-SFINCS is fast.** A 72-hour storm on about 4 million cells runs in about 3 hours on one computer,
   so dozens of storm and sea-level cases are practical.
2. **It reproduces Sandy.** Peak water within 0.35 m (RMSE) at 119 high-water marks, and more than 86 % of
   FEMA's mapped surge extent.
3. **It turns floods into risk.** One-third of the power plants and substations it covers flood in Sandy
   (60 of 182; 52 on today's ground and defences), and the same depths feed building-by-building damage
   estimates. [add the impact number]

**Future work:**

- More storms and sea-level-rise cases on today's ground; 1.2 m of sea-level rise alone already puts about
  30 power sites in water at high tide (still-water estimate, preliminary).
- Building-level damage for each scenario with the impact model.
- Model 2.0: add the Hudson waterfront and the Upper Bay.
- Finer inlets in Cape May, where the back bays read about 0.2 m low.

**Cut from the current poster:**

- The title "Surge, waves, rain and rivers together: a validated Sandy flood model…".
- Conclusion 1 "Compound matters… tens of centimetres in the back bays and up the rivers". It is the old
  headline, and the repo only half supports it: waves are worth +0.2 to +0.3 m at the marks, but rain on
  vs off moves the marks by +0.0005 m (`docs/MODEL.md` l. 246–248) and no river-off pair is quoted. If a
  compound line is wanted, say only "waves add 0.2–0.3 m to peak water at the marks".
- The red "first hindcast of Sandy…" paragraph and the "Earlier Sandy models either…" paragraph.
- "Building on the USACE NACCS Sandy simulation" in the abstract box (keep NACCS in the Methods table).
- "(rain off)" everywhere; the "MHHW + 2 ft and + 4 ft maps for the climate hazard team" bullet (internal).
- "Model 1.1.0" in tiles and captions can become "NJ-SFINCS"; keep the version once, in Methods.

## 5. Other risks, and the two references

**Confirmed citations (web-checked today):**

- Leijnse, T., van Ormondt, M., Nederhoff, K., van Dongeren, A. (2021). Modeling compound flooding in
  coastal systems using a computationally efficient reduced-physics solver: Including fluvial, pluvial,
  tidal, wind- and wave-driven processes. *Coastal Engineering* 163, 103796.
  doi:10.1016/j.coastaleng.2020.103796. Main title, authors, volume and article number are confirmed
  against the VU Amsterdam record and Deltares' SFINCS documentation. The subtitle after the colon is from
  my memory of the paper, not from today's search output: check it against the DOI page or drop it.
- McCallum, B.E., Wicklein, S.M., Reiser, R.G., Busciolano, R., Morrison, J., Verdi, R.J., Painter, J.A.,
  Frantz, E.R., Gotvald, A.J. (2013). Monitoring storm tide and flooding from Hurricane Sandy along the
  Atlantic coast of the United States, October 2012. U.S. Geological Survey Open-File Report 2013–1043.
  doi:10.3133/ofr20131043. Title, report number, DOI and the nine surnames are confirmed on the USGS
  publications page; the search returned "Wicklein, S." so the middle initial M. is mine, and sources vary
  slightly on author order. Copy the author line from pubs.usgs.gov/publication/ofr20131043.

**Risks:**

- **Marks and FEMA's map are not independent.** FEMA built its extent from the same USGS marks and sensors
  (`lit_check.md`). "Checked against both" is fine; never "two independent datasets".
- **"Flood" for a power site is generous:** one pixel ≥ 0.15 m counts. Under Model 1.0.0, 27 of 59 wet
  sites were wet on half their land; 24 of the wet sites were solar. The caption should say "any part of
  the site under ≥ 0.15 m of water". Don't quote megawatts flooded.
- **Site data:** outlines are today's OpenStreetMap sites, not a 2012 list. "Present-day" in the abstract
  covers it; keep the ODbL credit.
- **Fig 3 (today's ground) is two changes at once:** new ground AND today's levees and gates, with 2012
  buildings and land cover, on an unvalidated bed. The caption says preliminary; keep that word. All nine
  sites that go dry are small solar / wastewater sites (≤ 8.5 MW); the one that goes wet (Churchtown
  230 kV substation) is 0.18 m deep on 0.07 % of its land. So "today's coast floods fewer sites" is a weak
  result; "60 vs 52" is fine as a parenthesis, not as a conclusion of its own.
- **Infragravity waves:** the Methods table says "SnapWave incl. infragravity". True for 1.1.0 (it has a
  wavemaker, `docs/MODEL.md` l. 110). No change needed.
- **Fig 1 caption "46 water-level gauges inside the model"** while the legend says "46 + 2 at boundary".
  Consistent; keep both.
- **Lake marks footnote** (RMSE 0.24 m without five marks behind Deal Lake and Wreck Pond) is honest and
  useful; keep it with the scatter.
- **NJ only for the FEMA score:** 2,412.7 km² of Delaware / Pennsylvania / New York land is not scored.
  The caption's "(FEMA's map stops at the state line)" covers it.
- **Speed: the "about 3 hours on 64 cores" figure was measured on Model 1.0.0's run**, re-solved on the
  production engine: 2.51 h on 64 threads, 5.44 h on 16 (`docs/MODEL.md` §7). **Model 1.1.0's own solve
  took 4.09 h on 32 threads** (same table). Same mesh and forcing, so "about 3 hours on one 64-core
  computer" is fair, but no 64-thread timing of 1.1.0 itself is on file. If asked, the honest answer is
  "2.5 h on 64 cores for the previous version, 4 h on 32 cores for this one".

## Not checked

- I did not open the .pptx itself, only its preview image and `poster_text.md`.
- The impact results (not in the repo).
- Full texts of Amini et al. 2026 and Pollack et al. 2025; the rest of the Jane et al. preprint.
- Whether `fig2_hwm.png` (made 11-12 14:15) still matches the current style; its numbers do match.

## Sources (web)

- https://researchwith.stevens.edu/en/publications/high-resolution-simulation-of-urban-compound-flooding-under-clima/
- https://hess.copernicus.org/articles/30/401/2026/
- https://egusphere.copernicus.org/preprints/2025/egusphere-2025-1557/
- https://egusphere.copernicus.org/preprints/2026/egusphere-2026-5872/egusphere-2026-5872.pdf
- https://nhess.copernicus.org/articles/24/29/2024/
- https://research.vu.nl/en/publications/modeling-compound-flooding-in-coastal-systems-using-a-computation/
- https://sfincs.readthedocs.io/en/latest/overview.html
- https://pubs.usgs.gov/publication/ofr20131043

---

## Addendum (user decisions, later on 11-13): FIAT placeholder and bullet-point Results

These replace the matching parts of sections 2 and 4 above.

### Results = findings, as bullets

Drop the "What the figures show" panel. Use these (7; cut 3 or 7 first if space is short). Every number is
Model 1.1.0 with all forcing on unless the bullet says otherwise.

1. **Fast.** A 72-hour storm on 3.97 million cells runs in about 3 hours on one 64-core computer
   (2.5 h measured on 64 cores for the previous version, same grid and forcing; 4.1 h on 32 cores for this
   one; `docs/MODEL.md` §7).
2. **Peak water levels match the marks.** RMSE 0.35 m and bias −0.07 m at 119 USGS high-water marks;
   93 % are within ±0.5 m (Fig 2).
3. **The largest misses are five marks behind coastal lakes** (Deal Lake, Wreck Pond). Without them RMSE is
   0.24 m (n = 114).
4. **The model reproduces 87 % of FEMA's mapped surge extent**: 1,201 of 1,385 km² (CSI 0.80, FAR 0.09;
   Fig 1b).
5. **Most false alarms are rain, not surge.** 71 of the 113 km² the model floods and FEMA does not are
   rain ponds with no path to the sea; FEMA mapped surge only.
6. **One-third of the power sites flood in Sandy.** 60 of the 182 New Jersey power plants and substations
   the model covers (34 plants, 26 substations; Fig 3).
7. **On today's ground and flood defences, 52 of 182 flood** (preliminary; ten sites change, nine of them
   to dry). With no storm at all, 1.2 m of sea-level rise puts about 30 in water at high tide
   (still-water estimate on an earlier estimate of today's ground).

Sources: bullets 2–3 `logs/floodmap_fix_2026-11-12/rows/v4_refreeze_swz_v11__p4-premier+weir-elizabeth-rahway.csv`;
4–5 the same row and `logs/motf_classify_v11_2026-11-12/READ.md` (hit 1,201.35 + miss 183.39 = 1,384.7 km²;
false alarm 113.27 = 42.16 connected + 71.11 disconnected); 6–7 `exposure/changes_2012_vs_2026.txt` and
`logs/power_exposure_2026-11-02/README.md`.

Not offered as a bullet: "waves add 0.2–0.3 m". That pair was measured on Model 1.0.0 (n 110), not on
this run, so it would be the one Results number from a different model.

### Definitions that move

- **Methods bullets** (now four):
  - Marks: median peak water of flooded ground within 50 m of each mark, on the 3 m flood map.
  - Extent: flooded = peak depth ≥ 0.15 m; 15 m cells; New Jersey land inside the model. CSI = overlap of
    the model's and FEMA's flooded areas (1 = perfect).
  - Power sites: New Jersey power plants and substations (OpenStreetMap outlines), 253 in the region,
    182 inside the model; a site floods when any part of it is under ≥ 0.15 m.
  - Today's ground: post-2012 elevation and channel surveys plus today's levees and tide gates; sea level
    and buildings as in 2012.
- **Captions** carry the colour keys only. POD and FAR need no definition if bullet 4 and 5 are worded as
  above ("reproduces 87 %", "floods and FEMA does not").

### FIAT placeholder

- Box in the bottom-right of Results, beside the power figure, the same height as it. Dashed outline,
  grey text: **"Delft-FIAT building-damage results — [to be added]"**, with a figure area on top (about
  two-thirds of the box) and room for two bullets below. Give it the caption stub "Fig 4. Building damage
  from Sandy's flood depths (Delft-FIAT)." so the figure numbering is already right.
- Leave matching stubs so the undergrad fills three places, not one: Results bullet 8 "[FIAT finding +
  number]", the fifth tile "[FIAT number]", and Conclusion 3's "[add the impact number]".
- Add "Delft-FIAT (Deltares)" to the Methods table as a row "Impact model", with the building inventory
  left as "[inventory]".
- Risk to pass on: the checks in section 2 still apply to whoever fills the box (which flood map fed
  FIAT; depths from the bare-ground map; label preliminary). And if the box is still empty at print time,
  delete it and widen the power figure, and change the abstract's last sentence to "We are also
  coupling…". A printed "[to be added]" is worse than no box.

### Layout after these changes

- Left: Abstract, Introduction, Conclusions / Future Work (unchanged).
- Middle (Methods): setup table (with the Impact model row), Fig 2 HWM scatter, four Methods bullets, credits.
- Right (Results): Fig 1 (a) model + (b) FEMA extent across the top; under it the 7–8 result bullets on
  the left and the tile row on the right; bottom row Fig 3 power sites beside the FIAT placeholder.
- Space check: the bullets above are about 150 words against about 190 in the panel they replace, so the
  Results block gets no taller.
