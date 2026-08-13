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

### 🔴 READ FIRST — three boundary defects found by LOOKING at the map, 2026-08-13

The build reported *every invariant green* while the boundary was wrong in three places.
All three were caught by plotting the BC set and comparing it against what the user drew —
not by any assert. `scripts/plot_waterlevel_boundary.py <probe_dir>` after every mesh
change; the invariants do not check that the boundary is where you MEANT it.

**⚠️ A stale figure is worse than none.** The plot that exposed this was two builds old and
its counts (ocean 1,202 / narrows 153 / arthur_kill 41 / outflow 320) belonged to the
retired 16-vertex polygon. Regenerate before reading.

#### 1. ✅ FIXED — the Narrows arm was tracing the ALWAYS-ACTIVE BOX, not the drawn cut

The `narrows` arm came out as an **L**: a ~3 km limb along lat 40.6005 plus a stub of the
real cut, **209 cells**, sitting ~670 m south of the Verrazzano Bridge the user drew the cut
on (`v9 (-74.02941, 40.61090) → v10 (-74.05864, 40.60208)`, midpoint −74.044, 40.6065 — the
bridge).

**Cause: the bay `always_active_boxes_ll` entry ended at lat 40.60**, which is *inside* the
Narrows approach. The Narrows is ~30 m deep, so above the box `create_active(zmin=-10)`
deactivated the channel and `create_boundary` traced the box edge instead. Active cells in
the corridor collapsed across it: 2,779 (below 40.60) → 887 → 336 → **0** above 40.61.

**Fix: north edge 40.60 → 40.6125.** The ring's northernmost vertex is 40.61090, and the
region clip runs after `create_active`, so extending cannot pull in anything outside the
ring. Result: **209 → 61 cells, one continuous run, bed −29.57 m** — the real channel.

#### 2. ✅ FIXED (but see 2b) — the edge was DISJOINTED: the outflow gate stopped at +2 m

`create_boundary(btype="outflow", zmin=-1, zmax=2)` only made a cell free-outflow if its bed
sat between −1 m and **+2 m**. Measured along the 21.5 km Staten Island shore, only 42% of
edge cells fell in that window, so **209 of 411 stayed mask==1** and a cleanly-drawn
shoreline came out as a dashed line. Bed there reaches +26 m; the inland limits reach +80 m.

**Fix: `OUTFLOW_MAX_BED = 1.0e4` in `model.py` — every DRY edge cell is now outflow.**
Safe in the only direction that has ever bitten: `zmin` is still `OUTFLOW_MAX_DEPTH`, and
step 5c still re-seals any outflow cell landing on water, so the Navesink drain cannot
return (`free-outflow BC on water: 0` still holds). On dry ground a Neumann face is inert
until water reaches it, and then letting flood water leave beats ponding it against an
artificial wall — which on SI's south shore would push water back into the Raritan lobe.

| ring stretch | closed (mask 1) BEFORE | AFTER |
|---|---|---|
| Staten Island shore (411 edge cells) | 209 (51%) | **7 (2%)** |
| Rockaway → Narrows (207) | 119 (70%) | **34 (16%)** |
| NJ shore + west limit (318) | 281 (88%) | 234 (74%) |

Outflow total **240 → 957**.

⚠️ **The NJ/west limit stays mostly closed and that is FINE, not a fourth defect.** Those
234 cells have median bed **+19.7 m** (max +89 m); only 12 sit below 0 m. Nine are within
300 m of the grid's own west edge (x=559,113), where there is no neighbouring cell for
hydromt to flag against, so SFINCS treats them as a closed wall by default. High dry inland
ground never floods, so mask 1 vs 3 is immaterial there.

#### 2b. 🔴 OPEN — the built domain EXTENDS BEYOND the drawn region (found by fixing #2)

Raising the outflow gate made this visible: the boundary in the new figure runs down the
**grid rectangle's** west and south edges, not the drawn ring. Measured on
`data/probe_mesh_v1_5_fix2`:

| mask | cells | inside the drawn region | OUTSIDE it |
|---|---|---|---|
| 2 waterlevel | 1,307 | 1,307 | **0** ✅ |
| 3 outflow | 957 | 668 | **289** 🔴 |
| 1 active interior | 426,399 | 412,258 | **14,141** 🔴 |

The 14,141 sit at lon −74.30…−74.10, lat 40.15…40.50, bed **+3.7 … +58.3 m** — i.e. the
**dry inland notch** of the L that the region clip is supposed to remove.

⚠️ **PRE-EXISTING, not caused by the outflow change.** The gate only decides mask 3 vs 1;
it cannot make a cell active. Raising it merely put 289 BC cells on ground that was already
wrongly active, which is what made it visible. `base.region` resolves correctly to the drawn
polygon, and the clip at `model.py` (`mask[_outside] = 0`) is applied.

**Hypothesis, untested:** `_fill_inactive_holes` runs AFTER the region clip and re-activates
the clipped notch as an "inactive island". It is the only step between the clip and
`create_boundary` that can turn a 0 back into a 1 (`_drop_detached_active_islands` only
removes). **Cheap test: disable the fill, re-probe, see if the 14,141 vanish.**

🔴 **Do not "fix" this blind.** The mask is half the premier fingerprint, and
`_fill_inactive_holes` exists for a documented reason (finding 9 — it is what stops
`create_boundary` ringing scoured inlet throats with ocean level). If the fill is the cause,
the fix is to re-apply the region clip AFTER it, not to remove it.

**Impact if left:** ~3% more active cells (compute only) and a boundary that plots along the
grid edge. All of it is dry ground +3.7 m and up that ocean water never reaches, and no
`mask==2` cell is outside the region, so **no water-level forcing is misplaced.** It is a
correctness/"what did I actually build" issue, not a physics error.

#### 3. ⏳ OPEN — `arthur_kill` is TWO runs, and it needs a POLYGON edit (user)

The arm is legitimately one cut, but the build gives **two disconnected runs**:

| run | where | bed | what it is |
|---|---|---|---|
| 24 cells | lon −74.2617…−74.2549, lat 40.5038…40.5052 | −13.71…−1.38 | ✅ the real mouth cut (the eHydro-carved channel) |
| 35 cells | lon −74.2501…−74.2404, lat 40.4971…40.4996 | −5.68…−3.02 | 🔴 spurious |

**The ring cuts a corner across open water south of Ward Point instead of following the
shore around it.** Vertices **v29 (−74.24054, 40.49962), v30 (−74.24734, 40.49728),
v31 (−74.24923, 40.49817)** sit in water; `validate_region_v1_5.py` already reports segments
28–33 as wet. Pull those three vertices NORTH onto the Tottenville/Ward Point shoreline and
the arm becomes one run.

⚠️ Do NOT "fix" this by shrinking the `arthur_kill` arm box — that would leave a 1 km closed
wall standing across open water near Ward Point, which is worse than the current state.

#### 4. ⏳ OPEN — the Raritan discharge is genuinely MISSING

Correct observation: there is no discharge yet. The Raritan cut currently has its `mask==2`
demoted and a `raritan_cut` no-waterlevel zone asserting clean, so it is a **closed wall**.
It needs step 4 of the queue below (USGS `01403060` + an inflow point at −74.2997, 40.5090).

---

### ✅ The mesh is SIZED ON THE DRAWN POLYGON and every invariant is green

`scripts/probe_mesh_size.py` → `data/probe_mesh_v1_5_drawn`, 2026-08-13, on the hand-drawn
region with the eHydro tier in the stack:

**698,969 faces · 428,663 active · ×1.28 v1 (547,408) · projected SnapWave ~3.8 h** —
comfortably inside a 12 h batch. Boundary: **1,307** water-level cells, **957** outflow.
Latest probe dir: `data/probe_mesh_v1_5_fix2` (both boundary fixes above applied).

| arm | cells | runs | bracket | z range |
|---|---|---|---|---|
| ocean | 1,187 | 2 (1,170 + 17) | [200..4000] | −26.95 … −1.35 |
| narrows | 61 | **1** ✅ | [20..400] | −29.57 … −1.18 |
| arthur_kill | 59 | **2** 🔴 see defect 3 | [15..300] | −13.71 … −1.38 |

⭐ **`mask==2` cells outside every declared arm are demoted** — Rockaway Inlet and the
Raritan cut, exactly the two crossings `validate_region_v1_5.py` predicted would need it.
The `raritan_cut` no-waterlevel zone asserts clean, so the discharge cut carries no imposed
level.

All invariants pass: no outflow BC on water · no paved-over surveyed channel · no interior
inactive islands · **no NoData under an active cell** (the eHydro tier closed that) · no
active cell in a land box · every `mask==2` inside exactly one arm, all wet, counts in
range · no imposed level in a no-waterlevel zone.

⚠️ `arthur_kill` at 59 cells sits in the lower third of its `[15..300]` bracket, and 35 of
those 59 are the SPURIOUS run (defect 3). The real cut is 24 cells. Re-bracket only after
the polygon is fixed.

### The geometry as drawn

🔴 **`data/region_v1_5_raritan_edited.geojson` IS THE REGION.** Hand-drawn in QGIS by the
user, 2026-08-13, over Esri imagery + CUDEM: 40 vertices, valid, CCW, 2,281 km².
`nj_sfincs/domain.py` now points at it (it had been left on the superseded generated
polygon, which has been deleted).

✅ **The generator is retired.** `scripts/build_region_v1_5.py` →
`scripts/validate_region_v1_5.py`: it READS the drawn file and has no write path. Run it as
the gate — `python scripts/validate_region_v1_5.py [--plot]`.

⭐ **It declares CROSSINGS, not segment tags, and that change caught two errors.** A
hand-drawn vertex lands where the cursor landed, so attributing a crossing to a vertex pair
is unsound. The validator walks the ring at 50 m through the *same* elevation stack
`build_static` reads, finds contiguous reaches below −0.5 m, and requires each to sit inside
exactly one declared coordinate box. An undeclared wet reach is a failure — it is imposed
ocean level somewhere nobody looked.

🔴 **The crossing table below REPLACES the earlier one, which was wrong in two places.**
"nearest ADCIRC" is now the WORST gap along the reach, and only over the **load-bearing**
band (−10 m ≤ z < −0.5 m): where the ring runs deeper than `mask_zmin`, `create_active`
trimmed first and the ring decides nothing.

| crossing | kind | wet length | worst NACCS gap | bed source |
|---|---|---|---|---|
| ocean (limits + closure, one reach) | forced | 134.42 km (44.63 load-bearing) | 2.58 km | CUDEM |
| **Rockaway Inlet** | **closed** | 2.99 km | — | CUDEM |
| Verrazzano Narrows | forced | 1.55 km | 0.32 km | CUDEM |
| Arthur Kill mouth | forced | 1.53 km, **2 reaches** | 0.76 km | CUDEM + **GMRT** |
| Raritan River | **discharge** | 0.45 km | — | **GMRT** |

**Error 1 — the Raritan cut was mis-located.** It was recorded as a 1.79 km segment which is
**dry ground from end to end** (+5.8 to +22 m in both `nj_10ft_dem` and GMRT). The real
crossing is a **0.45 km** wet reach at **lon −74.2997, lat ~40.5065–40.5115**, inside the
*neighbouring* 2.39 km segment. ⚠️ The queued inflow point (−74.2920, 40.4905) derives from
the wrong segment's midpoint and sits at **+8.9 m on land**; use ≈(−74.2997, 40.5090).

**Error 2 — Rockaway Inlet was never listed.** The ring closes across **2.99 km of water
reaching −10 m** between Rockaway Point and Coney Island. That is *how* "Jamaica Bay is
excluded" is implemented, and it is fine — that prism exchanges with the ocean through this
inlet, not with Lower Bay — but it is a third wet cut and `create_boundary` will raise
`mask==2` along it, to be demoted. It is now declared `closed`.

Also: the Arthur Kill crossing is **two** reaches spanning several segments, not the single
1.06 km segment labelled `arthur_kill` — the ring runs through water from the Ward Point
shore round to Perth Amboy.

All five obs gauges fall INSIDE, including `sss_great_kills` — the ring goes around the
landward side of the harbour, so the only true interior holdout survives.

### ✅ RESOLVED 2026-08-13 — the two western cuts now have real soundings

**Decision (user, 2026-08-13): one near-Sandy eHydro survey per cut, GMRT for the rest,
and move on.** Built by `python scripts/download_ehydro_nj.py --set raritan` →
`data/elevation_v1_5/ehydro_raritan_ak.tif` (5 m, UTM18N, NAVD88, **187,138 carved
cells**), catalogued as `ehydro_raritan_ak` and now the **TOP tier** of
`DEFAULT_ELEVATION_LIST`.

| cut | survey | vs Sandy | min bed GMRT → eHydro |
|---|---|---|---|
| Arthur Kill mouth | `NJ_03_SWO_20140814_CS_4160_45X` | +654 d | −8.98 → **−13.56 m** |
| Raritan River | `RR_01_RAR_20120726_CS_3844_15X` | **−95 d** | −4.94 → **−9.85 m** |

⭐ **GMRT was under-cutting both channels by ~5 m.** That is the number that justifies the
detour: a 50 m bed does not resolve a dredged channel, and both of these cuts are where the
domain's exchange is imposed.

⚠️ **Accepted, not fixed:** eHydro surveys navigation channels, so it reaches ~37% of the
Arthur Kill cut's wet width and ~14% of the Raritan's; the flanks and the remaining
~5.5 km² of the CUDEM hole stay on GMRT **by decision**. `validate_region_v1_5.py` now
passes.

🔴 **`data/elevation` is a symlink into the FROZEN archive and is read-only**, so the new
tier lives in `data/elevation_v1_5/`. `download_ehydro_nj.py` grew a `--set` preset
(`nj` | `raritan`) and now refuses to run the `nj` preset at all, since that would rewrite
the archived tier.

⚠️ Two things the build had to handle, recorded so they are not rediscovered: the two
surveys are on **different reduction planes** (`NJ_03_SWO` on C.O.E. Mean Low Water, 3.5 ft
below NAVD88; `RR_01_RAR` on MLLW, 2.9–3.0 ft below), so the builder now reads each survey's
stated plane from its own header rather than assuming MLLW and querying VDatum — that
assumption would have put ~0.17 m of systematic error into the Arthur Kill. And newer eHydro
XYZ files ship a metadata header and a lowercase `.xyz` extension, so the reader is
header-tolerant and the globs are case-insensitive.

<details><summary>The gap this replaced (kept for the record)</summary>

### ~~🔴 BLOCKER — the two western cuts have NO real bathymetry~~

`validate_region_v1_5.py` fails on this, and it is a genuine data gap, not a threshold to
relax. **CUDEM has no tile west of lon −74.25** in this latitude band — a clean vertical
edge — so at the Arthur Kill mouth, the Perth Amboy waterfront and the Raritan River the
merged bed falls all the way through the stack to **`gmrt_nj`, the ~50 m offshore tail**.
Every tier above it is NoData there:

| point | only tier with data |
|---|---|
| Arthur Kill mid-channel (−74.2599, 40.5049) | `gmrt_nj` (−8.14 m) |
| Raritan R channel (−74.2997, 40.5090) | `gmrt_nj` (−3.15 m) |
| Perth Amboy waterfront (−74.2650, 40.5000) | `gmrt_nj` (−0.76 m) |
| Narrows mid-channel | ✅ `cudem_nj` (−29.47 m) |

⚠️ `nj_10ft_dem` *does* cover this ground, but its `zmin: 0.001` screen is there precisely
because it is a lidar topo product — it cannot supply a bed below the waterline, and it
reads +9 m across the (dry) mis-located Raritan segment.

🔴 **Confirmed NOT a download-script omission.** The `northeast_sandy` 1/9″ collection has no
`w074x50` tile at `n40x50` or `n40x75` (directory listing checked; the column stops at
`n39x75`), and the 1/3″ `NCEI_third_Topobathy` urllist has nothing north of `n40x00` in the
w074 column either. Adding tiles to `download_cudem.py` will not fix it.

**This is the elevation check that build sequence step 3 says to do before paying for the
subgrid, and it fails.** A forced cut is where the whole domain's exchange is imposed; a
50 m bed there sets the conveyance of the boundary the domain exists to test.

#### ✅ eHydro CHECKED 2026-08-13 — it is a real partial fix, not a dead end

134 surveys intersect the box (−74.34…−74.20, 40.46…40.54), **all CENAN** (New York
district), queried from the USACE eHydro FeatureServer. Measured against the WET part of
each cut, not the segment:

| cut | wet length | best single survey | union of all |
|---|---|---|---|
| Arthur Kill mouth | 0.684 km | 0.282 km (41%) `NJ_03_SWO_20160426` | **0.478 km — 70%** |
| Raritan River | 0.342 km | 0.058 km (17%) `RR_01_RAR_20140124` | **0.058 km — 17%** |

⭐ **A pre-Sandy Raritan survey exists**: `RR_01_RAR_20120726_CS_3844_15X`, **95 days
before** the storm — but it reaches only 14% of the cut.

🔴 **NO pre-Sandy survey covers the Arthur Kill MOUTH, and the naming is a trap.** The
surveys actually called *"Arthur Kill"* (`NJ_04_AKS_*`, including one from 2012-06-20) start
at **lat 40.521 — north of our cut at 40.504** and never touch it. The mouth is covered by
*"Seguin Pt.-Ward Pt.-Outerbridge"* (`NJ_03_SWO_*`, from 2014-08-14) and *"Perth Amboy Anch
& 2nd Chnl"* (`NJ_02_PAA_*`, from 2013-05-02). Selecting on the channel name would have
carved the wrong reach and reported success.

**What eHydro does NOT fix.** It surveys dredged channels, so the flanks stay on GMRT. Over
the whole CUDEM hole inside the region: **8.34 km² of water** (29% of the region's western
water), of which eHydro footprints reach **2.88 km² (35%)** — **5.45 km² stays on GMRT**
whatever we do.

**Verdict: worth doing for the Arthur Kill** (70% of a *forced* cut, and the covered part is
the dredged high-conveyance core that sets the exchange), **marginal for the Raritan** (17%,
and that cut is a discharge BC, where the cross-section bed matters less). The machinery
already exists — `download_ehydro_nj.py` is a carving tier with a water-only clip, VDatum
MLLW→NAVD88 offset field and a mask to each survey's `Bathymetry_Vector`. Adding surveys to
its `SURVEYS` list is the whole change.

⚠️ Two things to verify before trusting the output: `EPSG_SRC = 3424` (NJ State Plane) is
**hardcoded** and must be confirmed per survey rather than assumed; and the district sign
convention — all of these are CENAN, the same district as the Shark River survey the script
already handles, so the existing handling should carry, but check the sounding range.

Still open as alternatives for the 5.45 km² eHydro cannot reach: NOAA NOS hydrographic
surveys / BAG, or an NCEI CoNED NY–NJ harbor topobathy DEM.

</details>

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

1. ✅ **DONE — `build_region_v1_5.py` retired** to `scripts/validate_region_v1_5.py`, no
   write path, provenance recorded in the geojson's properties. The stale 16-tag `segments`
   property was stripped from the drawn file (geometry sha verified unchanged) — those tags
   are what produced the mis-located Raritan cut.
2. ✅ **DONE — the bed under the two western cuts** (eHydro tier, above).

2b. 🔴 **Test the hypothesis in defect 2b** (disable `_fill_inactive_holes`, re-probe,
   see whether the 14,141 out-of-region active cells vanish). Cheap, and it decides whether
   the built domain is the drawn domain.

2c. 🔴 **THE USER'S: move ring vertices v29/v30/v31 onto the Ward Point
   shore** so `arthur_kill` becomes one run (defect 3 above). Everything after this bakes
   the geometry in, so do it before the freeze. Then re-run, in order:
   `python scripts/validate_region_v1_5.py` →
   `NJ_DOMAIN=v1_5_raritan python scripts/probe_mesh_size.py data/probe_mesh_v1_5_fix3` →
   `NJ_DOMAIN=v1_5_raritan python scripts/plot_waterlevel_boundary.py data/probe_mesh_v1_5_fix3`
   and LOOK at the figure before freezing.
3. **Declare a `raritan` boundary arm** in `domain.py` (there are only three: ocean, narrows,
   arthur_kill) and **tighten all four arm boxes and their cell brackets**. ⚠️ The current
   `arthur_kill` box runs to lon −74.280 and was silently ADOPTING THE RARITAN RIVER — 41
   cells in two fragments passed a `[15..300]` bracket doing no work. ⚠️ The bay
   `always_active_box` west edge is lon −74.30, which clips the Raritan crossing at
   −74.2993…−74.3004 almost exactly; give it slack.
4. **Raritan discharge** (user approved): add `01403060` *Raritan R below Calco Dam at Bound
   Brook* (−74.5483, 40.5511) to `SITES` in `download_usgs_sandy_discharge.py`; inflow point
   ≈**(−74.2997, 40.5090)** — 🔴 **NOT** the previously queued (−74.2920, 40.4905), which is
   +8.9 m of dry land. Add a `no_waterlevel_box` over the cut — an imposed ocean level
   across a tidal river PUMPS it, the mirror of the Navesink drain.
   ⚠️ `01403060` is a LOWER BOUND: Lawrence Brook and the South River join below it. Check
   for a South River gauge rather than accept the deficit silently.
4. **Re-probe, re-plot** (`scripts/plot_waterlevel_boundary.py`). Then verify Great Kills is
   hydraulically CONNECTED (a coarse cell across the entrance would seal it — the dammed-inlet
   failure) and that `point_zb` at 2295 is not dry (else `series_source="map"`).
5. **Then** the three bootstrap items: `n_waterlevel_support` (from the builder's screen on
   the real mesh), `hwm_rules` for v1.5 basins, and the fingerprint in `premier.EXPECTED`.
   Until all three land, 5 tests stay red BY DESIGN and nothing may be frozen or run.

### ⚠️ The freeze was STARTED and DELIBERATELY KILLED, 2026-08-13

`scripts/freeze_mesh.py` ran for ~4 minutes before the Narrows defect was spotted; it was
killed and `data/frozen_mesh_v1_5_raritan_z10` deleted. **There is no frozen mesh.** Do not
restart it until defect 3 is fixed — freezing bakes in the mask, and the fingerprint is
computed from it.

### Two known defects I introduced, still open

- **`_drop_detached_active_islands` can eat cut cells.** It cost `narrows` 229→113 and
  `arthur_kill` 177→92 before the bay box. Keeping only the largest component is too blunt
  near a 1 km cut.
- **Its log line is structurally wrong**: it reports "N of them were water-level BC cells",
  but it runs BEFORE `create_boundary`, so that count is always 0. Report bed range instead.

---

## Then: the build sequence (Phase 5b)

1. ✅ **Region polygon — DONE.** Hand-drawn, not generated:
   `data/region_v1_5_raritan_edited.geojson`, gated by `scripts/validate_region_v1_5.py`.
   ⚠️ The "ring segments tagged ocean/land/narrows/arthur_kill" design described below was
   tried and **abandoned** — see the crossing declarations above for why.

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
