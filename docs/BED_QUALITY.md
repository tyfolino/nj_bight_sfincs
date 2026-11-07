# Bed quality plan (revised 2026-11-07, user-approved direction)

**Goal (user 11-07):** a bed good enough for the definitive, fastest flood model of New Jersey, judged where the
model and reality disagree MOST (Model 1.0.0 missed whole neighbourhoods around Newark), with a method that is
defensible in a paper. Bathymetry data are imperfect and will stay so; we stop chasing every disparity between
sources and go after what changes flooding.

## What the week showed (why the plan changed)

- **Two kinds of bed error, very different in consequence.**
  - *Wrong depth in water that is already connected* (the Navy Yard reserve basin filled to 0 / −2 m over a 24–38 ft
    basin; Cherry Island Flats; the Excelsior Bar edge; chart check `logs/chart_check_2026-11-07/`). At Sandy's peak
    3–4 m of water stands over these; they change storage and, through constrictions, the tide — rarely who floods.
  - *Connectivity*: a path closed (deck dam, creek plug, a fill that cuts off tidal water) or opened (a levee, wall or
    dune smeared away). These decide whether a neighbourhood floods at all.
- **The audit cannot rank these by itself.** ~30,000 flags per bed; ~250 "FIX" sites; of the top 44 on the 2026 bed,
  30 were real features (`logs/modern_audit_triage_2026-11-07/`); its lists reshuffle on every rebuild.
- **Source-vs-source checks are partly circular.** The envelope detector (`logs/bed_envelope_2026-11-07/`) finds one
  type well (a survey deeper than the bed) but caught 4 of 11 settled cases and 2 of 11 of the user's "open" deck
  picks: most real blockages have no deeper source to compare against. Charts share survey ancestry with BlueTopo.
- **Even the biggest miss was not mostly a blockage.** Newark (`logs/newark_motf_2026-11-02/`): of 51.7 km² missed,
  15.3 km² under building footprints (largely a scoring artefact), 12.9 km² ground at or above the local water (MOTF
  wider than this water level allows), 23.4 km² below the water but dry — and of that only 4.3 km² behind a crest
  above the water (a blockage); 7.9 km² had a path below the water that the water did not travel in time.

## The method: observations FIND, independent sources FIX, held-out observations JUDGE

### 1. Find: classify every disagreement with an observation, largest first

**A. Sandy, 2012 bed: MOTF extent (NJ) + USGS high-water marks.** Statewide, the Newark method (`newark.py`): every
missed area (MOTF wet, model dry) and every false-alarm area (model wet, MOTF dry), as connected regions ranked by
area, put in exactly one class by a fixed decision tree:

| class | test (pre-registered, from the model's own peak and the pixel ground) | what it means |
|---|---|---|
| not simulated | outside the active mask / above a river cut | scope, not bed |
| under a footprint | inside a burned building footprint | scoring artefact (report, don't fix) |
| ground above the water | pixel ground ≥ the nearest modelled peak − 0.15 m | MOTF wider than this water level, or the water level is low (check marks) |
| path never travelled | ground below the water, a path below the water exists | friction / time / route (roughness, not bed) |
| **held behind a crest** | ground below the water, every path crosses a crest above the water | **a blockage: locate it** |
| false alarm: missing barrier | model wet, MOTF dry, the water entered across a line a levee / wall / dune / gate source puts higher | **an opening: locate it** |
| false alarm: ground too low / MOTF narrow | otherwise | ground or MOTF, not connectivity |

High-water mark residuals are mapped beside it (median estimator, 50 m radius, always quoted with both): a region of
large misses with marks agreeing on the water level points at ground or MOTF; marks too low point at a blockage
upstream.

**B. Daily tide, BOTH beds: tidal reach.** The model's tide (the 32-day tidal twin) against where the tide demonstrably
goes: VDatum's tidal surface and NWI tidal wetland codes. Tidal water the model never reaches is held behind a crest
by the same test; held-out tide gauges (amplitude, phase) judge. This is the only observation-based check for the
2026 bed, which has no flood to compare against.

### 2. Fix: only what an independent source documents

For each blockage or opening above a size threshold (set from the Newark distribution before the statewide run), the
audit is the LOCATOR: which feature is the crest (deck, plug, fill, a smeared levee). A fix is made only when a source
independent of the bed says what is really there — bridge records (NBI / OSM), a survey, the levee database (NLD),
lidar of the right era, or the user's eye on imagery — and is logged in one table: place, class, area behind it,
feature, source, fix, before / after. **No fix is made because it improves a score.**

**Depth in open water: one statewide rule, tested once.** Where the bed is a flat water surface and a credible survey
of the right era (BlueTopo classes 1–3, eHydro) is deeper, take the survey, lower-only, in water defined from the beds.
It fixes the Navy Yard basin, Cherry Island and the Shrewsbury shoulders in one pass. Not site by site, no pickers.

### 3. Judge: paired, with observations the fixes were not chosen from

- Fixes are FOUND from MOTF misses and tidal reach; they are JUDGED on the high-water marks, the tide gauges and the
  whole-domain MOTF scores, in a paired comparison (per-mark bootstrap; CSI / POD / FAR with the excluded boxes).
- The classification rules and the size threshold are written down before the statewide run (this file).
- Report: how much of the miss and false-alarm area each class explains, before and after; every fix in the table.

## The audit's role now

A locator for the crests the observations point to, and a pre-freeze sanity sweep read once per freeze. Its lists are
not a to-do list. The envelope detector stays as one locator.

## Done (per bed, per version)

1. The miss / false-alarm area is classified (target: every region above the threshold in one class).
2. Every blockage and opening above the threshold is fixed with a documented source, or recorded with why not.
3. The tidal-reach check finds no held tidal water above the threshold that a source says is open.
4. The paired comparison holds or improves on the marks, the gauges and MOTF.

## Order

1. Statewide MOTF / mark classification on Model 1.0.0 (and v1.1 once tagged) — the Newark method, everywhere.
2. Tidal reach from the existing tide runs, both beds.
3. Locate + fix the largest blockages / openings; the depth rule in the same rebuild.
4. One paired run per bed; then the residual review.
