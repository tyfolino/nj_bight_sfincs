# FINDINGS — what is believed true NOW

**Current state only. No history, no retractions.** If something here turns out to be
wrong, *change it* — the previous project kept 26 reverse-chronological campaign logs with
retractions stacked above the claims they retracted, and the reader's job became replaying
history to reconstruct the present. Those logs still exist, in the archive, indexed in
[ARCHIVE.md](../ARCHIVE.md). Read them as history, not as fact.

Live campaign state is in [STATUS.md](STATUS.md). This file is for what is settled.

---

## 1. General findings — these transfer to any domain on this coast

### Method

1. **The HWM estimator decides the SIGN of the bias, and therefore every ranking.** A mark
   is scored against the cells within a radius, because the mark's *coordinate* is
   uncertain — 94 of 95 Sandy marks (and all 64 at quality ≤ 2) were located by "Map
   (digital or paper)", the lowest-accuracy horizontal method USGS STN records. `quality`
   is the VERTICAL accuracy and says nothing about where the mark is. But reducing that
   window with `max` is not defensible: a maximum is one-sided, so it is **unbounded in the
   radius** and has no converged value, and its argmax sat on the window's OUTER RING for
   essentially every mark — finding a ditch 50 m away, not the wall the mud line is on.
   Measured on 19 marks: `max` swings +1.10 m from 0→150 m radius, `median` swings 0.07 m.
   Under `max` a reference arm reads +0.32 m (too wet) and every water-removing arm wins;
   under `median` it reads −0.21 m and the same arms lose. **The ranking inverts exactly.**
   `median` is the default; every row carries `hwm_estimator` and `hwm_radius_m`.

2. **The wet-only HWM metric structurally rewards failing to flood.** The worse the model
   under-floods, the more marks fall out of the average, and the better the remaining
   average looks. It hid a dammed inlet for months — the marks behind it were dry, silently
   dropped, and the basin reported a near-perfect −0.055 m bias while the river never wetted
   at all. Use the `_scored` keys, which score a dry mark against the model's ground
   elevation there (the most generous reading available, and still a large negative
   residual).

3. **FEMA MOTF POD rewards OVER-flooding** — the mirror image. Flood everything and POD is
   perfect. And MOTF is a HWM/sensor-interpolated *bathtub*: a flat 3.4 m fill reproduces it
   at IoU 0.906, so it shares provenance with our own marks and is an extent CONSISTENCY
   check, not an independent observation. Read CSI, beside the residuals.

4. 🔴 **Waves off ⇒ CSI / POD / FAR / n_dry are INADMISSIBLE.** Waves contribute ~+0.34 m of
   setup on the open coast and wetting is threshold-nonlinear, so an extent metric with
   SnapWave off is a *different* measurement, not a weaker one.

5. **Compare arms PAIRED.** Bootstrap the per-mark differences, not the two pooled
   statistics. Two arms can differ by more than either differs from the truth while the
   paired difference is indistinguishable from zero — which is exactly the situation the
   current boundary comparison is in (ΔRMSE −0.042 m, CI [−0.238, +0.137], P = 0.706).

6. **A change in the scored-mark count invalidates a comparison.** Restrict to a shared
   `hwm_id` set (the "bridge rescore"). A *partial* bridge is refused outright: it is a
   third mark set, comparable to neither side.

7. **Pre-register the diagnostic before you know which side it lands on.** A helpful
   practice, **not a gate** — never block a run on writing one.

8. **An HWM records that water ARRIVED, not which way it came in.**

### Domain construction

9. ⭐ **A depth threshold is a statement about ELEVATION; the mask it produces is a
   statement about TOPOLOGY.** They disagree wherever the isobath reaches inside the model.
   Four instances so far. `mask_zmin = -10` once left 153 inactive islands inside the
   domain, 145 of them in an inlet throat scoured to −14.78 m. As islands they blocked
   conveyance through the one cross-section that mattered; as mask edges they made
   `create_boundary` impose the open-ocean level AROUND them, 2.6 km inside the mouth,
   75 m from a gauge. The topological hole-fill (`_fill_inactive_holes`) needs no
   hand-drawn box and keeps working when the domain moves — but it cannot fix an intrusion
   that stays CONNECTED to the sea. That is what `always_active_boxes_ll` is for; use both.

10. ⭐ **A free-outflow (Neumann) BC on deep water is a DRAIN, not a boundary.** A region
    polygon once chopped a tidal river mid-channel and hydromt put mask=3 on the 5 m-deep
    cut face. The model ran that face outward in 100% of timesteps, never once reversing,
    and **92.5% of everything entering the estuary vanished**. The estuary was a pipe, not a
    bathtub, and every "null result" in that campaign was a bucket with a hole in it. Wet
    outflow cells are now sealed to ordinary interior and the invariant refuses to ship one.

11. **No geometric predicate catches "the boundary is inside an inlet".** Every candidate
    was tried and recorded in `model._report_waterlevel_boundary`: a latitude cut misses a
    southern gorge; the barrier axis is ambiguous exactly at an inlet, because an inlet IS
    the gap in the barrier; region-edge proximity is wrong because the legitimate BC line is
    an isobath well inside the region; a detached-component test fails because a scoured
    gorge stays connected to the sea; and a count-vs-baseline detects CHANGE, not WRONGNESS
    — the gorge was present in every run for a month with a stable fingerprint.
    **Stable-and-wrong is invisible to a baseline.** What all the defects shared is that
    nobody looked at the BC set as a whole, so the build now PRINTS it every time. The
    assert that geometry could not provide is the **arm whitelist**: declare the boundary
    before it can exist.

12. **An unbounded box is silently correct on the domain it was written for.** Two of three
    mask overrides in the previous repo had `None` sides; one of them flipped `3 → 2` north
    of a latitude with THREE unbounded sides and put 70 BC cells on dry land. Every box type
    here now requires four finite bounds.

13. **Green (bathymetric) lidar returns the WATER SURFACE in deep or turbid water**, which
    is indistinguishable from land. Ranked above the real bed it sealed an inlet shut (real
    bed −4.6 to −10.8 m; lidar +0.4 to +2.2 m) and left the entire estuary behind it at
    exactly +0.00 m — never flooding — while the ocean 1.8 km away reached +2.9 m. eHydro
    surveys go on TOP of the elevation stack, and the build asserts no surveyed channel is
    paved over.

14. **eHydro's sign convention flips by USACE district.** New York district ships negative
    elevations; Philadelphia ships positive depths. A hardcoded formula produces a silently
    *empty* raster on the wrong side.

15. **For any bed edit, diff `z_volmax`, not `z_zmin`.** A carve restores sub-cell relief;
    it is not a uniform lowering, so `z_zmin` shows ~nothing while the run changes.

16. **A frozen mesh short-circuits `build_static`.** A roughness or elevation change
    therefore produces a silent NO-OP template — it needs a subgrid rebuild. A *mask* change
    is the opposite: no rebuild, but the fingerprint moves.

17. **A third support point is not a free change.** Which gauges force the boundary is
    decided by BUFFERING the region, so it is a property of the DOMAIN, not the forcing
    file. Pushing a domain 0.45° south once dropped a third gauge from 150.7 km to 99.1 km —
    inside a 100 km buffer by 0.9 km — silently converting a 2-node boundary into a 3-node
    one, with no other symptom. An inserted node cost one arm +0.18 m of HWM bias. Choose
    the buffer with MARGIN and assert the count AFTER hydromt has selected.

18. **`nj_10ft_dem` is New-Jersey-only.** Any domain crossing the state line falls through
    to CUDEM/3DEP, and where that has no coverage the cell is *undefined*, not shallow.

19. ⚠️ **The Cape May trap: never tune a threshold to its knife edge.** Every box in the
    registry that was tuned by sweeping records the sweep and the margin chosen, not just
    the final number.

### Physics and forcing

20. **SnapWave is 90–95% of runtime** and scales per-iteration with the wave domain.

21. **ERA5 is inadmissible as a nearshore wave boundary.** Measured at 7 support points, it
    imposes 8.624 m in ~9.9 m of water — γ 0.86–0.89, ABOVE the 0.78 depth-limited breaking
    cap — at 7 of 7 points, with EXACTLY zero alongshore variation (a 31 km cell cannot
    resolve a 25 km boundary). CORA's shelf-resolving SWAN imposes 4.98–6.11 m there
    (γ 0.50–0.63) with 1.14 m of alongshore spread. **CORA is the adopted wave boundary.**
    ⚠️ CORA is not a gold standard — against NDBC 44025 at the buoy's own depth it runs
    +0.49 m high. That cuts in its favour: biased high offshore and still asking only
    ~5–6 m at the 10 m contour means the reduction is shelf transformation, not a low
    source. Quote the direction, not the value.

22. **Setup at the boundary XOR SnapWave — never both.** Stated outright by the SFINCS
    authors, in **Leijnse et al. 2025**, Coastal Engineering 199, 104726 (`refs/`), §4.4 —
    comparing SnapWave against two methods that ADD parametric setup at the offshore
    boundary: *"In these two additional simulations, the stationary wave solver and dynamic
    IG wave processes are **excluded to avoid double counting of the wave contributions**."*
    Their measured cost of getting it wrong: the boundary route **overestimated max water
    depth by ~1 m in some regions**. Grimley et al. 2025 take the other branch and obey the
    same rule — ADCIRC storm tide at the boundary and **no wave model in SFINCS at all**
    (verified by full-text grep: zero occurrences of "wave setup", "SWAN", "STWAVE",
    "SnapWave").
    🔑 **Proper NESTING is still legitimate and is not what the rule forbids**: a boundary
    carrying only what accumulated *seaward* of its contour, with SnapWave adding the surf
    zone shoreward, is the correct partition. The violation to avoid is narrow and specific
    — support points shallow enough to inject *surf-zone* setup AT the boundary (finding 23).

23. **NACCS water level INCLUDES wave setup.** Its README says so (CSTORM-MS: ADCIRC coupled
    to STWAVE via radiation stress). That is *not* double counting under one-way nesting —
    the product hands SFINCS the total level AT the boundary depth and SnapWave adds what
    develops shoreward. The defect is WHERE the support points sit: a distance-only screen
    admits points up to 2 km SHOREWARD of the boundary they are weighted onto. Measured, the
    WL-vs-depth slope on the open coast is −0.0047 m/m in the quiet window (corr −0.389) and
    −0.0327 m/m at the crest (corr −0.835) — so shallow points run **~+0.23 m above** deep
    ones, and only during the storm. ⚠️ Screen on depth **seaward of `open_coast_max_y`
    only**: inside a semi-enclosed bay the water is shallow everywhere, the waves are small,
    and those are exactly the points that fix an under-forced interior (corr −0.371 there).

24. **A linear interpolation between two exterior anchors cannot produce an interior
    maximum.** This is the whole reason for `v1_5_raritan`. NOAA harmonics put the Raritan
    interior tidal maximum at 0.732–0.761 m, above BOTH outside anchors, so a lobe forced
    that way is under-forced by construction. Forcing it harder closes the deficit and then
    overshoots, which is what over-forcing looks like when the real problem is being forced
    at all.

25. **Linear interpolation is NOT a meaningful error source on the OPEN COAST** — tested
    with a product against an interpolant built from that same product at the same two
    points, so its own bias cancels. ⚠️ That result does not extend to a semi-enclosed
    amplifying basin. Do not use it to defend an interior boundary.

26. **`zb` is NaN on SFINCS-inactive faces**, so any hm0 comparison must restrict to faces
    active in *both* runs.

27. **The tide/drain discriminator is the FRACTION OF TIME THE SERIES RISES.** `max - min`
    over a window reports a monotonic spin-up drawdown as a tide, and a de-trend leaves a
    bowed residual that still looks like a range while counting turning points is defeated
    by numerical wiggle. A tide floods and ebbs; a drain only ebbs. Discard the first 12 h of
    a run before measuring anything tidal — a window opening during spin-up inflated EVERY
    phase lag by ~13 min.

28. **Two of the interior obs points snap to DRY BANK cells** (`point_zb` +0.99, +1.14,
    +1.79 m). That does not invalidate the PEAK — at the crest the water surface is locally
    continuous, so a bank cell and the channel beside it share a `zs` — but it is fatal for
    the pre-storm tide, which never reaches such a cell at all. `ObsGauge.series_source`
    records which source is right per gauge.

29. **Never rank a timing-shifted arm on a pre-failure peak.** An arm that crests earlier
    lands more of its crest before a dead gauge's last reading, so it scores best on that
    column while having the LOWEST true peak of the set. That happened once and made the
    worst arm in a campaign look like the best.

30. **A basin's error splits into VOLUME and TILT with different causes.** volume =
    mean(err_north, err_south) → exchange / connection / boundary; tilt = err_north −
    err_south → wind stress / friction / conveyance. ⚠️ Evaluate the along-basin gradient at
    MATCHED INSTANTS. Peak-minus-peak on a basin whose ends peak ~6 h apart reported an
    INVERTED gradient and sent a whole day after a conveyance defect that did not exist; at
    matched instants the model reproduced the gradient's sign, its flip time and ~61% of its
    magnitude, and the real defect was a cumulative volume deficit.

### Operations

31. **Disk quota exhaustion never says "quota".** It SIGSEGVs jobs or silently truncates
    output maps while `sacct` reports COMPLETED.

32. **A truncated floodmap cache reads back clean and scores bone-dry** — CSI 0.00, every
    HWM "dry": a spectacular physics result that is really a broken file. Writes are atomic
    (temp + `os.replace`). ⚠️ Do not try to catch stubs by file size: a healthy floodmap is
    only 0.11–0.16× its dep raster because it is sparse, and no size band separates "sparse
    because the coast barely flooded" from "sparse because the write died".

33. **`$PROJ` is not read by the PROJ library** (that is `PROJ_LIB` / `PROJ_DATA`). This
    account's login profile exports `PROJ=$HOME/nj_sandy_sfincs` — the toolchain dir — and
    a batch script doing `NJ_ROOT="${PROJ:-$PWD}"` therefore pointed the model at another
    tree, silently, with everything still resolving. Both halves are now asserted.

34. **Import `pyproj` before `hydromt_sfincs`**, or `downscale_floodmap` can double-free.

35. **A memo one entry too small is worse than no memo, because it looks like it is
    working.** A 4-entry FIFO over 5 compared runs evicted the first while the fifth loaded,
    so every panel re-derived all five (~70 s each).

36. **Hardlinks defeat a path-keyed cache.** `Path.resolve()` collapses symlinks only, so
    a deduped subgrid tif gives every arm a distinct cache entry for one physical file.
    Key on `(st_dev, st_ino)`.

### Closed — do not re-open

Each of these cost a campaign and is settled. The evidence is in the archive's
`docs/campaigns/`, indexed in [ARCHIVE.md](../ARCHIVE.md).

- **Infragravity waves are a NULL LEVER, not an instability.** The old "IG caused blow-ups"
  verdict came from a pre-sealed run whose blow-up traced to a *solver* bug. On a sealed
  domain every metric moved ≤0.01 m.
- **SnapWave blow-ups (~1e13) are boundary points OUTSIDE the mesh** → depth 0 → runaway.
  Any SnapWave-active cell that is SFINCS-inactive and dry is a candidate.
- **Surf-zone hm0 spikes are GEBCO integer bathymetry** filling nearshore NoData; offshore
  zs spikes are the 2Δx boundary ring. Neither is physics.
- **A wavemaker INSIDE a bay is a trap** — ocean-side only.
- **Measure a channel sill as the MAX over along-channel slices of each slice's MINIMUM.**
  Any other reduction finds a hole beside the obstruction and reports the channel open.
- **CORA is rejected for WATER LEVEL** (tide late, levels 0.14–0.31 m low) and **adopted for
  WAVES**. ❌ "CORA runs low" does NOT extend to its waves. 🔑 Its `*_map.zarr` are kerchunk
  reference files, not real zarr stores.
- **The Galibier engine is retired.** Faber is the engine.

---

## 2. The v1.5 design record

**Why the boundary moves:** finding 24. **Why the margin is not the argument:** the paired
bootstrap does not separate the candidates (P = 0.706). The case is geometric.

### ⭐ The evidence, measured from NOAA harmonics — not from any model

M2 constituents from `/mdapi/prod/webapi/stations/<id>/harcon.json`, referenced to Sandy
Hook (amp 0.679 m, phase 5.60° GMT):

| station | lat | M2 amp | vs SH | lag vs SH |
|---|---|---|---|---|
| The Battery | 40.7006 | 0.671 | 0.99 | +26.1 min |
| **Port Reading** | 40.5550 | **0.761** | **1.12** | +11.0 min |
| **Keasbey, Raritan R** | 40.5083 | **0.752** | **1.11** | +11.8 min |
| Cheesequake Creek | 40.4533 | 0.732 | 1.08 | +13.7 min |
| South Amboy, Raritan R | 40.4917 | 0.723 | 1.06 | +11.0 min |
| Great Kills Harbor | 40.5433 | 0.715 | 1.05 | −2.1 min |
| Sandy Hook | 40.4669 | 0.679 | 1.00 | 0 (ref) |
| Red Bank, Navesink | 40.3550 | 0.513 | 0.76 | +96.7 min |

The two exterior anchors are the Battery (0.671) and Sandy Hook (0.679). **The interior
(0.732–0.761) exceeds both.** That is the whole argument, and it comes from published
harmonic constituents rather than from a model diagnostic, so it cannot be an artefact of
the thing it is being used to justify.

**The lobe is also mis-phased by BOTH previous options, in opposite directions.** True phase
is **+11 to +14 min** vs Sandy Hook. A Battery↔AC interpolant puts ≈+20 min there (6–9 min
too late); the phase-shifted variants impose ≈0 min (11–14 min too early). Relocating the
boundary removes the question rather than splitting the difference.

⚠️ **Do NOT reuse the tidal ratio for SURGE.** Everything above is tidal. Surge
amplification in that bay is **unobserved**, and a tidal amplification ratio is not evidence
about it.

⚠️ **An interior gauge is not automatically a good anchor — site it first.** The strongest
amplitudes are the worst sited: Keasbey and South Amboy are significantly up the Raritan
River, and Port Reading is on the Arthur Kill. Great Kills Harbor is the most open-bay of
the set and also the weakest signal. On v1.5 this matters less than it did — the interior is
computed rather than anchored — but the same siting caution applies to any gauge used as a
holdout.

### What the published studies actually do: they DRAW the boundary

- **Grimley et al. 2025** (Florence; WRR, PDFs + SI in `refs/`) specify BC cells "using a
  modified shapefile of the NHD Area". The −15 m contour is *where it lands on average, not
  the rule* — the opposite of a generative `mask_zmin`. 341 ADCIRC support points, nothing
  extrapolated past 2 km, and **outflow rather than an imposed level at lateral termini**.
- **Leijnse et al. 2025** force Parker-corrected GTSM at ~460 m spacing at −10 m.
  ⇒ **our boundary DEPTH is right; the support-point SPACING was the real gap** (two nodes
  39.6 km apart). That is what v1.5 and a dense product fix, and it is worth stating that
  way rather than as "we changed the depth".
- ⚠️ **No published study couples NACCS to SFINCS.** NACCS is used widely as a hazard
  resource and SFINCS is widely one-way coupled to ADCIRC, but this specific pairing appears
  to be new here — novel *and* unvetted. Say so in the paper.

### The Sandy Hook record gap

Gauge 8531680 stops at **2012-10-29 23:36 UTC**, on both products and both datums; GESLA-4
is dead for this. ⭐ **You do not have to validate a reconstruction AT Sandy Hook** — the
Battery and Atlantic City survived the crest and flank it at ~20 / ~40 km, so a forcing
product can be scored *there* on peak level, peak timing and tidal amplitude. That is the
independent constraint an earlier retirement argued did not exist.

⚠️ On v1.5 this changes meaning again: the Battery is ~10 km outside a forced boundary, so
it is a forcing INPUT, not a holdout. It is a **forcing-product diagnostic, and standard
practice rather than a gate** — report it alongside the incumbent interpolant's own numbers,
never against invented thresholds.

**The shape.** One ocean arm — v1's own Atlantic trace, **extended ~3.3 km straight north
to Rockaway Point** — plus two short forced cross-sections at Verrazzano Narrows and the
Arthur Kill MOUTH. Lower Bay, Raritan Bay and Sandy Hook Bay are computed. Staten Island's
south shore is a declared land boundary; Jamaica Bay is excluded; no NYC land in the model.
⭐ The ocean arm is a CONTINUATION, not new geometry: measured off the frozen mesh, v1's
ocean-side `mask==2` already runs at lon −73.936…−73.947 from lat 40.44 to its north edge at
40.5202, and one band sits exactly on Rockaway Point's longitude. v1.5 keeps v1's southern
limit (lat 40.150).

⚠️ **A −10 m isobath cannot BE the ocean arm** — contoured on CUDEM over this window it is a
**single 1,230 km path** threading the dredged channels straight into the bay. That is
finding 9 in picture form, and it is why the published practice (Grimley et al.) *draws* the
boundary and reports the contour as where it lands on average, not as the rule.

**Why a wall will not do at the NARROWS.** The omitted exchange is not bounded and local:
the Narrows carries the Upper Bay + Hudson tidal prism, drawn through Raritan Bay. The
domain must stay open there. ⚠️ Nor will a DISCHARGE boundary: a tidal strait's flux is a
*response* to the level difference across it, so prescribing Q over-determines it and kills
the feedback that computing Raritan Bay depends on — and it destroys the audit, since Q(t)
at the Narrows is the validation. Grimley's discharge inputs are NHD **rivers** (freshwater
inflow), an order of magnitude or two smaller and one-way; their free-outflow termini are
finding 10's drain. (Contrast a small bay cross-section, where a closed wall
omits a bounded local exchange and an imposed ocean level actively pumps the lagoon — there,
the wall is the honest choice.)

**Arthur Kill is cut at its MOUTH** (Perth Amboy / Ward Point) — the kill is OUT of the
domain. Decided 2026-08-13; it replaces an earlier north-end cut at the Kill Van Kull
junction, which had **zero** NACCS support within 9.56 km while the mouth has a point at
0.21 km. ⚠️ Cutting there walls off the Raritan Bay ↔ Newark Bay exchange and puts a forced
level on ~1 km of Raritan shoreline — a milder instance of the very defect v1.5 fixes, so
do not claim the interior is *wholly* computed. The Narrows carries the Upper Bay + Hudson
prism and stays open. ⚠️ The dropped rationale ("Carteret / Woodbridge are HWM-rich") is
**untested**: our HWM file has no marks there but is clipped at lat 40.515. See STATUS.

**What makes it auditable rather than asserted:** flux cross-sections just inside each arm.
SFINCS writes `crosssection_discharge` every 10 min, so Q(t) through the Narrows is the
Upper Bay + Hudson tidal prism — a number comparable against literature. Without it the
relocation is a claim.

⚠️ **The flanking-gauge convention changes meaning on this domain.** The Battery sits ~10 km
north of the Narrows — *immediately outside a forced boundary* — so it stops being an
independent holdout and becomes a forcing INPUT. Flanking gauges are a forcing-product
diagnostic only; the model holdouts are the interior Raritan gauges.

**Boundary depth is a DOMAIN axis.** `mask_zmin` is half of `sha(z, mask)`. −10 and −15 are
two registered domains sharing one `mesh_key`; −2 is dropped (finding 22).

---

## 3. NACCS boundary construction

The CHS portal grab is manual. **Record the query verbatim** so it is reproducible:
storm type `Tropical_Historical`, storm ID `001` (Sandy), the save points covering the
region, `SimB1HT` water level. Zips land in `data/NACCS/`.

**Parsing traps**, all handled in `scripts/build_naccs_boundary.py`:

1. **NUL padding.** Files are padded to a power-of-two size (4 MiB / 2 MiB). The content is
   complete — this is padding, not truncation — but `rstrip(b"\x00")` before decoding or the
   last record is garbage.
2. **Every file bundles all seven validation storms** (4,224 extratropical + 9,864 tropical
   rows). Sandy is `Tropical_Historical` **AND `Storm ID == 001`**. Type alone also gets
   Irene, Isabel, Josephine and Gloria.
3. **Dry flags** are `-99999`; anything below `-9000` is dry and must NEVER be interpolated
   across — doing so once produced a spurious ×0.613 range deficit. A point dry for even one
   step is DROPPED, not patched: SFINCS needs a complete series at every bnd node. The dry
   screen is evaluated only inside the padded window, so a point dry in mid-October but wet
   through the storm is perfectly usable.
4. **The records are 15-minute**, despite the readme saying "ADCIRC Record Interval: 10 min".
5. **The time pad.** Pad to 2012-10-24 … 2012-11-01, wider than the model window, so
   `np.interp` never extrapolates at `tstart`. A product starting exactly at `tstart` gets
   clamped flat and **fabricates both tidal range and lag**.

⭐ **How to confirm a file is ADCIRC and not STWAVE** — relevant now that STWAVE output is
being pulled alongside. The ADCIRC columns are `RMP00` pressure, **`ET00` water elevation**,
`UU00`/`VV00` velocity, `RMU00`/`RMV00` wind — and **no wave parameters at all**. That
absence is the check.

🔴 **The 2 km screen must live in the FILE**, not in a downstream selection.
`water_level.create` selects support points by buffering the **`mask==2` line** — not the
region — by `Domain.waterlevel_buffer`, which is 100 km. Ship an unscreened file and hydromt
takes every point, including ones deep inside the bay and up the Arthur Kill, and SFINCS
then weights interior water onto an open-ocean boundary. **Never retune the buffer for one
arm**; declare `n_waterlevel_support` on the arm.

⚠️ **SFINCS itself distance-weights the support points onto the boundary cells at runtime,
and that weighting scheme has NOT been verified here** — the solver is a compiled container.
The 2 km screen is what makes it not matter: with a support point within 2 km of nearly
every cell, the answer is insensitive to the weighting. If the screen is ever loosened, that
assumption goes with it.

**VDatum per point.** NACCS is MSL epoch 1992; convert LMSL → NAVD88 per save point via the
NOAA VDatum API (cached to `data/NACCS/vdatum_lmsl_navd88.csv`). ⚠️ **A scalar will not do**
— the separation drifts 0.065 m across the domain, **concentrated in the Raritan limb**,
which is exactly the water v1.5 is about. The script validates itself against an
independently known offset at Sandy Hook (−0.073 m, NOAA-published and reproduced by the
NACCS conversion key) and refuses to write past a 0.030 m disagreement; measured agreement
is 0.004 m, which also settles the *datum*-epoch worry (VDatum's LMSL is the 1983–2001
epoch). That is separate from the secular sea-level term below.

**Coverage arithmetic.** Walk candidate point sets computing the nearest-point distance from
every `mask==2` cell. There is a knee: past ~40 points you buy roughly 0.4 km of max gap per
36 further downloads. Density is the axis that matters — a previous candidate boundary had
**four** points on this coast and extrapolated a whole limb from >11 km away.

⚠️ **The frozen mesh's `crs` variable has no usable `epsg` attribute.** Read `crs_wkt` or
hardcode EPSG 32618; `pyproj.Transformer.from_crs(0, ...)` raises a confusing `CRSError`.
Cell coordinates are `mesh2d_face_x` / `mesh2d_face_y` and the mask variable is `mask`, not
`msk`.

**Steric is ALREADY APPLIED.** The CHS +0.155 m baroclinic adjustment for storm 001 is in
the released timeseries (measured +0.167 m quiet-window mean at a 22 m-depth save point).
Do **not** re-add it.

**The 1992 epoch term is REJECTED as an arm.** October 2012 water was not at the 1992 mean —
NOAA monthly MSL 1991–2012 gives 130 mm at Sandy Hook and 100 mm at the Battery, mean
0.115 m — but adding it scored worse at P = 1.000 against its pair, and it is an upward
correction on a boundary that waves already push up. The builder still supports
`--epoch-offset` so the question stays reproducible; do not put it in a candidate sweep.

**Depth screen: seaward only** — finding 23.

**Two things the builder now emits that it did not before:** per-arm coverage (aggregate
coverage hides an empty arm) and a **support-geometry sha16**, so a run can be traced to the
point set that forced it the way the domain fingerprint traces it to a mesh.
