# STATUS — live campaign state

**Edit this file in place.** Git has the history. This replaces the previous project's
12 KB "current state" memory file and its 26 reverse-chronological campaign logs; the point
of the format is that a reader gets the current state without replaying how it was reached.

Last updated: **2026-08-13**

📋 The original plan this work follows is frozen at
[docs/plan_v1_5_original.md](plan_v1_5_original.md) (Phases 1–4 and 6 are done; 5 and 7 are
live). **This file is authoritative for what remains** — the plan is the record of what was
intended, not of where things stand.

---

## Where we are

The repo has been stood up and the code ported from `~/nj_coast_sfincs`
(commit `21e28f2`, see [ARCHIVE.md](../ARCHIVE.md)). **The port gate passes.** The v1.5
domain is **not yet registered** — it is blocked on two manual facts, below.

### ✅ Port verification — PASSED 2026-08-13

`scripts/verify_port.py`, tier 1 (rescore, no solver) and tier 2 (fingerprint + obs points
on the archived template). Tolerance is **bit-for-bit** (`places=9`): same input, same code
path, deterministic arithmetic, so any drift is a bug, not a tolerance.

Baseline: `experiments/v1_monmouth/metrics.csv` **as regenerated 2026-08-12** — NOT the
older July `_rescored.csv`, which is `hwm_n_scored=19` with no estimator column and would
fail on `n` alone, reading as a port bug that is not there.

| metric | archive | ported |
|---|---|---|
| `hwm_bias_scored_m` | −0.363105931 | −0.363105931 |
| `hwm_rmse_scored_m` | 0.570499300 | 0.570499300 |
| `hwm_n_scored` | 38 | 38 |
| `motf_csi` / `pod` / `far` | 0.637834 / 0.766245 / 0.208073 | identical |
| `phase_lag_sandy_hook_min` | 17.6 | 17.6 |
| `gauge_peak_err_prefail_m` | −0.311681898 | −0.311681898 |

Per-basin marks reproduce too (they depend on first-match-wins over `hwm_rules` IN ORDER,
so a reorder shows up here): `south_coast` 4 · `sandy_hook_bay` 21 · `atlantic_oceanfront`
3 · `shrewsbury_navesink` 10 · `shark_river` 0 — total 38.

**One key renamed by the port**, listed in `RENAMES` in the gate rather than hidden behind
an alias: `gauge_peak_err_prefail_m` → `peak_err_prefail_sandy_hook_m`. The archive had one
function per named place, so `gauge_*` needed no gauge in it; the port drives everything off
the domain registry. Phase-lag keys are now the registry gauge name (`sandy_hook` is
unchanged, which is why it is the pinned one).

**One real bug the gate caught:** a `round(..., 6)` inside the peak metric differed from the
archive at 1e-7. Rounding inside a metric is a silent lossy step that makes a CSV
non-reproducible — it now rounds nothing, and rounding happens in the report.

---

## 🔴 BLOCKED: the two gates before any v1.5 polygon is drawn

Two manual facts can kill the design. Confirm both **before** drawing a region polygon —
neither is expensive, and both are cheaper than a mesh.

### Gate 1 — NACCS coverage at both cuts

Does the CHS/NACCS save-point set have a **wet** point within 2.0 km of the mask==2 cells at
the **Verrazzano Narrows**, the **Arthur Kill**, and along the **Sandy Hook → Rockaway
Point** cut?

`scripts/build_naccs_boundary.py` now reports coverage **per arm**, because aggregate
coverage hides "0 points on Arthur Kill" — which on a domain whose entire claim is that two
short cross-sections carry the exchange is the single most important thing to know before
the run rather than after it.

> **Fallback if an arm comes back empty:** 1-node-per-arm gauge forcing — the Battery
> (8518750) for the Narrows, Bergen Point West Reach (8519483) for Arthur Kill. Defensible
> for two ~1 km cuts, unlike a 123 km gauge desert.

#### 🟢 Indicatively CLEARED on all three arms, 2026-08-13 — no further download needed

Sampled every 250 m along the sketched arms (`scripts/naccs_coverage_map.py`), against
ADCIRC points only:

| arm | median | max | within 2 km |
|---|---|---|---|
| ocean arm — Rockaway extension | 0.85 km | 1.85 km | **100%** |
| Verrazzano Narrows cut | 0.37 km | 0.68 km | **100%** |
| Arthur Kill cut (MOUTH) | 0.55 km | 0.87 km | **100%** |

And against v1's **real** `mask==2` cells (1,669, read off the frozen mesh, measured per
cell rather than as a polyline) — the Atlantic side v1.5 inherits unchanged: median
**0.46 km**, max **2.77 km**, **95.5%** within 2 km.

⚠️ Still not gate 1. These are the SKETCH, not `mask==2` on a mesh that does not exist, and
they ignore the dry and depth screens — so every number is an **upper bound** on the support
that will survive `build_naccs_boundary.py`. The gauge fallback is no longer needed on any
arm. **No further CHS download is required for the premier.**

#### 🟡 Indicative coverage, 2026-08-13 — encouraging, NOT the gate passing

9 CHS zips in `data/NACCS/`. **532 ADCIRC save points and 193 STWAVE save points**, spanning
lat 39.976–40.619, lon −74.326 to −73.877. Regenerate with
`python scripts/naccs_coverage_map.py` → `reports/naccs/` (CSV + map).

🔴 **The two products ship in the SAME zip and have DISJOINT save-point ID spaces** — zero
collisions across the 532 and the 193, while STWAVE `SP0089` and ADCIRC `SP03584` are the
same physical point. **Join on coordinates, never on id**, and with a tolerance: exact float
matching reported 85 "STWAVE-only" points, 83 of which sit 0 m from an ADCIRC point and
differ only in trailing precision. At 50 m the real figure is 2.

Counted in **rough indicative lon/lat boxes** (module constants in
`scripts/naccs_coverage_map.py`; they OVERLAP by design and are not the arms):

| zone | pts | ADCIRC+STWAVE | ADCIRC only |
|---|---|---|---|
| Verrazzano Narrows | 27 | **27** | 0 |
| Kill Van Kull | 0 | — | — |
| Arthur Kill | 54 | 23 | 31 |
| Raritan Bay | 156 | 54 | 102 |
| Lower Bay | 85 | 62 | 23 |
| Sandy Hook Bay | 60 | **2** | 58 |
| Sandy Hook → Rockaway cut | 90 | 64 | 26 |
| Atlantic shelf | 198 | **2** | 194 |

⚠️ **This is not gate 1.** The real screen is "within 2.0 km of a `mask==2` cell", which
needs the frozen mesh, and these boxes are not the arms. Read it as: the Narrows is
comfortably covered on both products; **Arthur Kill is the thin arm to watch**; and wave
coverage is a northern crescent — Sandy Hook Bay and the Atlantic shelf are ADCIRC-only.

#### ✅ STWAVE HAS ARRIVED — and the ADCIRC-only claim was wrong

The 2026-08-13 zips are **mixed**: `..._ADCIRC01_Timeseries.csv` *and*
`..._STWAVE07_Timeseries.csv` members side by side. The earlier "ADCIRC only, zero wave
parameters" reading came from inspecting ADCIRC-named members only, while the 695 count it
sat beside had already swallowed STWAVE members as save points (532 + 193 − 30 new in the
ninth zip = 695 exactly). **Per-zip verdicts on product are invalid; the product is a
per-MEMBER fact.**

STWAVE columns: `alpham`, `TM`, `Tp`, `DADD`, `UDIR`, `U`, `Hmo` — and the records are
**30-minute**, where ADCIRC is 15-minute.

✅ **`build_naccs_boundary.py` FIXED 2026-08-13 and verified on the mixed directory.**
It selected members on `CSV/…Timeseries.csv` with no product filter and took water level
from **hardcoded column index 9** — `ET00` water elevation in ADCIRC, **`TM` mean wave
period in STWAVE**. It never silently corrupted (the 30-vs-15-minute step tripped the
`times_ref` guard) but it exited blaming timestamps. Two changes:

1. Members are filtered on `ADCIRC_MEMBER = "_ADCIRC01_"`, and the skipped count is
   printed per zip so the STWAVE members are visibly excluded rather than silently.
2. The water-level column is looked up **by code (`ET00`) in header row 1**, not by
   position, and a member without it is a loud exit. A column-order change is now a
   failure, not a wrong variable.

Verified `--report-only --no-cache` on `v1_monmouth`: 532 unique ADCIRC points (177
duplicate files, values agree), Sandy window 2012-10-11 12:15 → 2012-11-01 00:00 at 15 min,
532 → 151 within 2 km → 92 kept after the dry (−23) and open-coast depth (−36) screens.
Coverage **max gap 2.76 km, 95.6% within 2 km**, support sha16 `21f967f9798a6945` — which
independently reproduces the 2.77 km / 95.5% measured off the mesh by
`naccs_coverage_map.py`.

⏳ STWAVE still has no reader; it needs its own, for its own column layout and 30-minute
step. Not on the premier's path.

#### Where the zips go

`~/nj_bight_sfincs/data/NACCS/` — a real local directory (the builder reads
`ROOT/data/NACCS`). **Point the browser here.** ⚠️ Two zips from 2026-08-13 originally
landed in the **archive's** `data/NACCS/`, which the freeze then made read-only; they were
moved across (sha256-verified identical, then deleted from the archive, which was re-frozen).
The archive's NACCS dir is back to the 6 zips it held before the restart, which is what it
should contain — those two were never part of its record.

✅ **`_sandy_parsed.npz` is present and is SAFE.** An earlier note here claimed the parse
cache was "keyed to nothing" and would never notice a new zip. That is wrong:
`read_zips` stamps `st_mtime_ns` for every zip and invalidates unless both the **count and
every mtime** match (`build_naccs_boundary.py:206-209`), so adding, re-downloading or
touching a zip is a cache miss. `--no-cache` remains available and is still the right
reflex after any change you are unsure about.

⏳ **STWAVE is partially in** — 193 points against ADCIRC's 532, concentrated north of Sandy
Hook. See the coverage table above. ⚠️ STWAVE-vs-CORA is a **deliberately withheld
single-variable arm** (FINDINGS §1.21, and "Open, deliberately not decided" below); CORA is
the adopted wave boundary. Completing STWAVE coverage is not on the v1.5 critical path.

### 🟢 12 more HWMs are available in the target basin, and they are SAFE to add

Same STN query. In the Raritan Bay + Lower Bay box (−74.32…−74.00, 40.40…40.60) — the water
v1.5 exists to test — STN holds **45** marks with an elevation against our local file's
**33**. The **12** we do not have are all `Coastal`; by *vertical* quality, 6 Excellent
(±0.05 ft), 3 Fair, 3 Poor.

⭐ **None of the 12 falls inside v1_monmouth's footprint**, so adding them **cannot** move
the port fixture's pinned `hwm_n_scored=38`. That was the risk worth checking before
touching `sandy_hwms.geojson` (finding 6: a changed scored-mark count invalidates a
comparison), and it does not bite.

⚠️ `hwmQualityName` is **VERTICAL** accuracy only. It says nothing about where the mark is,
which is the uncertainty that forces the radius-and-estimator choice (finding 1). Do not
read "6 Excellent" as 6 well-located marks.

⏳ Not yet integrated: v1.5 needs its own `hwm_rules` basin classification, which does not
exist until the domain is registered. Add the marks and the rules together.

### ✅ Gate 2 — PASSED 2026-08-13. Two interior holdouts survive the crest.

The whole claim is "Raritan Bay is COMPUTED, not forced". If nothing inside can be scored,
the claim is untestable. Sandy Hook (8531680) dies mid-storm — 48 of 96 hours NaN — and
cannot be the answer alone.

**It does not have to be.** USGS deployed rapid-deployment storm-tide sensors (SSS) across
Raritan Bay for Sandy and they all survived. Found via `Instruments/{id}/Files.json` →
`Files/{file_id}/item` on STN event 24 — *not* the bulk `Instruments.json`, whose
`data_files` is empty for every one of them (`download_sandy_storm_tide_sensors.py`
already documents that quirk).

Distances are to the **v1.5** arms. ⚠️ Computing them against v1's `mask==2` is wrong and
inverts the answer: 511 of v1's 1,669 boundary cells are its north edge (lat 40.5202) and
west edge (lon −74.28), **both of which run through Raritan Bay and both of which v1.5
deletes**. v1.5 inherits the 1,158 Atlantic-facing cells only.

| instrument | where | record | peak m NAVD88 | to nearest arm | role |
|---|---|---|---|---|---|
| **2255** `SSS-NJ-MID-001WL` | S Raritan Bay, NJ shore | 10-28 10:00 → 11-02 | 3.57 | 4.67 km | ✅ **holdout** |
| **2295** `SSS-NY-RIC-004WL` | Great Kills | 10-29 07:00 → 11-01 | 4.03 | 8.85 km | ✅ **holdout** |
| 2294 `SSS-NY-RIC-003WL` | Arthur Kill mouth | 10-28 06:00 → 11-01 | 4.88 | 1.67 km | ⚠️ forcing-adjacent |
| 2291 `SSS-NY-RIC-001WL` | Narrows, SI side | 10-28 06:00 → 11-01 | 4.58 | 0.87 km | ⚠️ forcing-adjacent |
| 2270 `SSS-NY-KIN-001WL` | Narrows, Brooklyn | 10-28 06:00 → 11-01 | 4.06 | 3.46 km | ~ marginal |
| 2265 `SSS-NJ-UNI-002WL` | up Arthur Kill | 10-28 10:00 → 10-31 | 3.84 | — | out of domain |

🔴 **THESE SENSORS ARE MOUNTED ABOVE NORMAL WATER. A long record is not a usable record.**
Each has a "lowest recordable water elevation"; below it the unit reads its own floor, and
`download_sandy_storm_tide_sensors.py` masks that to NaN. The fraction of each raw record
actually above its floor:

| inst | floor m NAVD88 | above floor | usable |
|---|---|---|---|
| 2255 | 1.75 | **1.9%** | ❌ **NO** — 28 six-min points, a 2 h blip at the crest |
| 2295 | 1.97 | 13.7% | ~ 112 points, high water only |
| 2291 | 1.28 | 19.8% | ~ 204 points |
| 2270 | 0.62 | 48.4% | ✅ 524 points |
| 2294 | 0.54 | 57.5% | ✅ 614 points |

⚠️ **So "record starts 10-28" does NOT mean "1.5 days of pre-storm tide".** 2255 spans the
period but was dry for 98% of it, and its 30-min still-water mean is not a water level at a
site that only briefly floods. **2255 is not a quantitative holdout** — at best a peak bound.

#### 🔴 Why 2255 is wonky — DIAGNOSED, and it is not a product error

**The sensor is sited on ground that is above normal water.** CUDEM under it reads
**+1.45 m** NAVD88 at the point and a **+1.78 m median within 150 m** — the whole
neighbourhood is dry land at ordinary tide, which is exactly why its recordable floor is
1.75 m and only 1.9% of the record clears it. Contrast 2294, whose 150 m median bed is
**−0.07 m**: real water at the sensor.

So 2255 is functionally **an HWM with a clock**, not a tide gauge: it answers "did water
reach here, when, and how deep", and its 30-min still-water mean averages across a window
that is partly *dry*, which is not a water level at all.

Its NACCS counterpart node sits in **2.86 m of open bay 0.88 km away**. Open-bay level
against shoreline overtopping depth is a category mismatch, so the +1.665 m "peak error" is
an artefact of the pairing, not a NACCS deficiency. ⚠️ **Drop 2255 from quantitative
scoring**; keep it only as a peak bound (water reached ≥3.57 m raw there) and score it as an
HWM, which is what it physically is.

⭐ **What IS testable: tidal HIGH WATER, not tidal RANGE.** Every sensor's troughs sit below
its floor, so peak-to-trough range is unmeasurable everywhere. But at 2294 and 2270 the
floors are low enough (0.54 / 0.62 m) that the tidal *peaks* clear them, and those peaks are
resolved in both level and timing. High-water amplitude and phase are therefore available;
full M2 range is not. ⚠️ Statistics computed on retained points are **high-water
statistics** — the clipping is not missing-at-random.

✅ **Ingested** to `data/gtsm/sandy_storm_tide_raritan.nc` via
`download_sandy_storm_tide_sensors.py --set raritan`. Deliberately a SECOND file:
`sandy_storm_tide_nj.nc` feeds `_SSS_SEA_BRIGHT` (2258) in the frozen v1_monmouth registry
and the port fixture is pinned against it. Register as `ObsGauge`s when `v1_5_raritan` is.

### 🟡 NACCS vs those sensors — the forcing product is good at the straits, LOW in the bay

`scripts/check_naccs_vs_sensors.py` → `reports/naccs/naccs_vs_sensors.{csv,png}`.
🔴 **A FORCING-PRODUCT diagnostic, never a model diagnostic** — no SFINCS run is involved.
The NACCS nodes used are INTERIOR nodes that on v1.5 force nothing; they stand in for "what
does the source product think the interior does".

| inst | role | node dist | bias | RMSE | peak err | lag |
|---|---|---|---|---|---|---|
| 2294 | forcing-adj, 1.67 km | 0.47 km | **−0.007** | 0.168 | +0.168 | +12 min |
| 2270 | marginal, 3.46 km | 0.24 km | −0.067 | 0.173 | +0.058 | +48 min |
| 2291 | forcing-adj, 0.87 km | 0.29 km | −0.092 | 0.178 | +0.001 | +54 min |
| **2295** | **holdout, 8.85 km** | 0.70 km | **−0.389** | 0.410 | **−0.350** | +18 min |
| 2255 | unusable (n=28) | 0.88 km | +1.234 | 1.315 | +1.665 | +66 min |

⭐ **The result that licenses the build: at the three places NACCS actually FORCES v1.5 —
the ocean arm, the Narrows, the Arthur Kill mouth — it is excellent.** Bias ≤0.09 m, RMSE
~0.17 m, tidal peaks tracked in both level and phase across the whole record.

At Great Kills it runs 0.35–0.39 m low. **Do not read a mechanism into that.** It is one
high-water-only comparison (n=112; everything below the sensor's 1.97 m floor is clipped
away) of one model against another model. Checked and ruled out: the node is *inside* the
harbour — bed along the 0.70 km line to it is water for 59 of 60 samples, to −9 m in the
dredged channel — and 8 save points sit within 2.1 km, so neither density nor a land block
explains it. **More NACCS points there would buy nothing.**

🔴 **And it does not propagate.** Great Kills is **8.85 km from the nearest arm**: on v1.5 it
is interior water that SFINCS COMPUTES. NACCS forces only the three arms, so a NACCS error
in the middle of the bay never enters the model. Not inheriting it is exactly what moving
the boundary out buys — under the old design, with the boundary through the bay, it would
have been a source term.

⚠️ **Pick the NACCS node by DEPTH, not distance alone.** NACCS ships save points with
negative depth (above datum — marsh/bank). The nearest node to 2255 is at −1.25 m and read
as a +1.7 m product error that was really a node-choice error; the script now requires
`depth >= 0.5 m`.

⏳ **The M2 amplification claim still has no direct time-series test.** The cleanest route
does not need 2012 data at all: run the model, extract its harmonic constituents at Port
Reading / Keasbey / South Amboy / Great Kills and compare against the NOAA published
`harcon` values already tabulated in FINDINGS §2.

---

## 🔵 LIVE — Phase 5b in progress, 2026-08-13. Pick up here.

### The mesh is SIZED and the geometry is DRAWN

`scripts/probe_mesh_size.py` on `v1_5_raritan`: **684,842 faces, 408,729 active, ×1.25 v1
(547,408), projected SnapWave ~3.8 h** — comfortably inside a 12 h batch. Boundary as built:
1,396 water-level cells (ocean 1,202 / narrows 153 / arthur_kill 41), 320 outflow, all
invariants passing. That run predates the drawn polygon below.

🔴 **`data/region_v1_5_raritan_edited.geojson` IS THE REGION.** Hand-drawn in QGIS by the
user, 2026-08-13, over Esri imagery + CUDEM: 40 vertices, valid, CCW, 2,284 km². It
supersedes the generated `region_v1_5_raritan.geojson`.
⚠️ **`scripts/build_region_v1_5.py` still WRITES that path and will clobber the drawn file.
Do not run it until its write path is retired** (queued below).

Validated on the drawn polygon — four water crossings, every one inside the 2 km rule, so
**no gauge fallback is needed anywhere**:

| crossing | length | nearest ADCIRC |
|---|---|---|
| ocean closure (isobath turn → Rockaway Pt) | 11.13 km | 0.92 km |
| Verrazzano Narrows | 2.66 km | 0.72 km |
| Arthur Kill mouth | 1.06 km | 0.38 km |
| **Raritan River** | 1.79 km | 0.88 km |

All five obs gauges fall INSIDE, including `sss_great_kills` — the ring goes around the
landward side of the harbour, so the only true interior holdout survives.

### ⭐ What fixed the boundary, after three wrong attempts

The water-level boundary was a tangle looping through Lower Bay. **It was never the region
outline.** `create_boundary` puts `mask==2` on the outermost active WET cells, and the
active/inactive interface is set by `create_active(zmin=mask_zmin)` *before* the region clip.
In Lower Bay that deactivated the dredged channels (Ambrose −27 m, Chapel Hill, Raritan
Reach); they stay CONNECTED to the sea through the bay mouth so `_fill_inactive_holes` cannot
reach them (finding 9, verbatim), and every channel got ringed with imposed ocean level.

The fix is one declared `always_active_boxes_ll` entry over **Raritan + Lower + Sandy Hook
Bay** — "bay water is in the domain at any depth". Ocean arm 2,398 → 1,202 cells and one
continuous run; detached islands 25/41,478 cells → 5/169. ⚠️ Moving the closure, tightening
the isobath and patching individual channels all failed first. Do not re-try them.

### Queued, in order

1. **Retire `build_region_v1_5.py`'s write path** → make it a VALIDATOR over the drawn
   polygon (closure, CCW, crossing lengths, cut brackets). Record provenance.
2. **Tag the 40 segments** (ocean / land / narrows / arthur_kill / raritan / inland); declare
   the Raritan cut; **tighten all four arm boxes and their cell brackets**. ⚠️ The current
   `arthur_kill` box runs to lon −74.280 and was silently ADOPTING THE RARITAN RIVER — 41
   cells in two fragments passed a `[15..300]` bracket doing no work.
3. **Raritan discharge** (user approved): add `01403060` *Raritan R below Calco Dam at Bound
   Brook* (−74.5483, 40.5511) to `SITES` in `download_usgs_sandy_discharge.py`; inflow point
   at the crossing midpoint (−74.2920, 40.4905). Add a `no_waterlevel_box` over the cut — an
   imposed ocean level across a tidal river PUMPS it, the mirror of the Navesink drain.
   ⚠️ `01403060` is a LOWER BOUND: Lawrence Brook and the South River join below it. Check
   for a South River gauge rather than accept the deficit silently.
4. **Re-probe, re-plot** (`scripts/plot_waterlevel_boundary.py`). Then verify Great Kills is
   hydraulically CONNECTED (a coarse cell across the entrance would seal it — the dammed-inlet
   failure) and that `point_zb` at 2295 is not dry (else `series_source="map"`).
5. **Then** the three bootstrap items: `n_waterlevel_support` (from the builder's screen on
   the real mesh), `hwm_rules` for v1.5 basins, and the fingerprint in `premier.EXPECTED`.
   Until all three land, 5 tests stay red BY DESIGN and nothing may be frozen or run.

### Two known defects I introduced, still open

- **`_drop_detached_active_islands` can eat cut cells.** It cost `narrows` 229→113 and
  `arthur_kill` 177→92 before the bay box. Keeping only the largest component is too blunt
  near a 1 km cut.
- **Its log line is structurally wrong**: it reports "N of them were water-level BC cells",
  but it runs BEFORE `create_boundary`, so that count is always 0. Report bed range instead.

---

## Then: the build sequence (Phase 5b)

1. **Region polygon** — `scripts/build_region_v1_5.py`, named lon/lat vertices as module
   constants. Ring segments tagged `ocean` / `land` / `narrows` / `arthur_kill`.

   ⭐ **TWO GEOMETRY DECISIONS TAKEN 2026-08-13** — these SUPERSEDE
   [plan_v1_5_original.md](plan_v1_5_original.md) lines 168 and 31. Indicative vertices
   are in `scripts/naccs_coverage_map.py`; see `reports/naccs/coverage_map.png`.

   **(a) Arthur Kill is cut at its MOUTH** (Perth Amboy / Ward Point), not at the Kill
   Van Kull junction. The whole kill is OUT of the domain. The plan's north cut had **no
   NACCS support at all** — nearest save point 9.56 km, 0% within 2 km — and would have
   needed the 1-node Bergen Point gauge fallback. The mouth cut forces straight from
   NACCS: nearest point **0.21–0.87 km**, 16–19 points within 2 km.

   ⚠️ **What this costs, stated plainly.** It walls off the Raritan Bay ↔ Newark Bay
   exchange, and it puts a forced level on ~1 km of the Raritan shoreline that v1.5
   otherwise computes. That is a *much* milder version of the defect v1.5 exists to fix
   — a dense product across a 1 km cut, not a 2-node interpolation across 123 km — but
   it is the same kind, so say so rather than claiming the interior is wholly computed.
   The Narrows still carries the Upper Bay + Hudson prism and stays open.

   ✅ **RESOLVED against USGS STN 2026-08-13 — the mouth cut costs 8 marks.** Queried
   `stn.wim.usgs.gov/STNServices/HWMs/FilteredHWMs.json?Event=24` (Sandy is event **24**;
   910 marks nationally). The Arthur Kill limb — Carteret / Woodbridge / Elizabeth, box
   (−74.30…−74.15, 40.52…40.68) — holds **8** marks in the FULL STN set. Our local file's
   zero was indeed its lat-40.515 clip, but "HWM-rich ground" was an overstatement
   regardless. 8 marks, on ground deliberately out of scope, is a price worth paying for
   an arm that forces from NACCS at 0.21 km instead of needing a gauge fallback at
   9.56 km. **Scope call, 2026-08-13: the goal is "can we force Raritan Bay correctly",
   not the limb. Extending north is possible future work.**

   **(b) The ocean arm is v1's trace extended ~3.3 km STRAIGHT north to Rockaway Point**
   — not a diagonal across the Lower Bay mouth. Measured off the frozen mesh: v1's
   ocean-side `mask==2` already runs at lon −73.936…−73.947 from lat 40.44 to its north
   edge at 40.5202, and in the 40.46–40.47 band its easternmost cell is at −73.9364,
   Rockaway Point's own longitude. The arm is a continuation, not new geometry.
2. **Refinement** — a NEW `refinement_v1_5_raritan.geojson`. Neither existing recipe is
   usable: a refinement recipe is not portable, and a level gate written for one basin will
   refine another basin's open water to its finest level. L3/L4 on the two cuts and their
   approaches, L3 Sandy Hook Bay + Shrewsbury/Navesink, L2 Raritan open water, L0/L1 shelf.
   **Size it with `scripts/probe_mesh_size.py` BEFORE building** — SnapWave is 90–95% of
   runtime and scales with the mesh.
3. **Subgrid + freeze** — the expensive irreversible step. Do the elevation check first:
   `nj_10ft_dem` is NJ-only, so Staten Island, the Rockaway shore and the Narrows fall
   through to CUDEM/3DEP. `build_static` now asserts no active cell has NoData in the merged
   bed, which turns a silent hole into a build error.
4. **Mask + boundary** — declare `boundary_arms` (ocean / narrows / arthur_kill) and
   `land_boxes` (Staten Island south shore, Jamaica Bay). The whitelist replaces the
   half-plane `MaskOverride` patches; the type no longer has an unbounded side, so the
   defect class is unrepresentable.
5. **Flux cross-sections** — `sfincs.crs` observation lines just *inside* each arm. SFINCS
   writes `crosssection_discharge` every 10 min. ⭐ **This is what makes the relocation
   auditable**: the Narrows carries the Upper Bay + Hudson tidal prism, and a tidal prism is
   comparable against literature. Without it the new boundary is asserted, not measured.
6. **NACCS forcing** — `build_naccs_boundary.py`, with the depth screen applied **seaward of
   `open_coast_max_y` only**. Declare the resulting count as
   `Experiment.n_waterlevel_support`, never by relaxing the domain value.
7. **Register the fingerprint** in `premier.EXPECTED` + `KNOWN` **before** running anything.

---

## The four seeded arms

Already in `nj_sfincs/experiments.py` under `v1_5_raritan`:

| arm | what it is |
|---|---|
| `naccs-premier` | the premier: relocated boundary + CORA per-support-point waves |
| `naccs-nowaves` | same boundary, SnapWave off — cheap, levels + phase only |
| `noaa-2node` | the incumbent 2-node interpolant, kept only to show what relocation bought |
| `naccs-premier-z15` | −15 m boundary: **a different DOMAIN**, `mesh_key` sibling |

---

## Open, deliberately not decided

- **STWAVE vs CORA waves.** A single-variable arm, withheld to avoid moving two variables at
  once. Same logic says do not bundle it with a domain move. CORA-as-wave-boundary is
  *adopted* settled physics (admissible at 7/7 support points vs ERA5's 0/7).
- **The +0.027 m setup problem.** The reference configuration generates only +0.027 m of
  setup from the −10 m boundary to shore with waves ON — far too small, and an open thread.
  It bears directly on whether a deeper boundary buys anything, which is why
  `naccs-premier-z15` exists.
- **−2 m boundary: DROPPED, not deferred.** Setup-at-the-boundary XOR SnapWave, never both
  (Leijnse et al. 2025 §4.4). At −2 m the embedded setup in NACCS is the whole signal, so
  SnapWave would have to be off — the branch measured to overestimate max water depth by
  ~1 m.
- **`south_coast` marks.** 4 of 38 are hydraulically disconnected from the water-level
  boundary in the model: they move by 0.0005 m across four different boundaries, including
  one that adds +0.115 m uniformly to every boundary cell. They contribute a fixed −0.53
  bias / 0.785 RMSE to every arm and dilute any pooled score. Flagged **before** the results
  landed, so excluding them is a pre-flagged re-analysis, not a post-hoc one.

---

## Known gaps in this repo

- **The archive is not yet read-only on disk.** Run, once:
  `cd ~/nj_coast_sfincs && chmod -R a-w nj_sfincs scripts docs reports tests data *.md *.py`
  (undo with `u+w`). Leave `experiments/` writable — the port fixture is copied out of it.
- **`ruff` is not installed anywhere on this machine**, so the tree has not been formatted.
  It is written to the 88-column style by hand. Run `ruff format . && ruff check .` once,
  in its own commit, before any logic edits — that is the only moment it is free.
- **`nj_sfincs/plots.py` is untested at runtime.** It imports cleanly, but no figure has
  been drawn since the port.
- **No `notebooks/`.** Deliberate; add one when there is something to look at.
