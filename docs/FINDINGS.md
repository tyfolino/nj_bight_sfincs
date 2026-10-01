# FINDINGS — what is believed true NOW

**Current state only. No history, no retractions.** If something here turns out to be
wrong, *change it* — the previous project kept 26 reverse-chronological campaign logs with
retractions stacked above the claims they retracted, and the reader's job became replaying
history to reconstruct the present. Those logs still exist, in the archive, indexed in
[ARCHIVE.md](../ARCHIVE.md). Read them as history, not as fact.

Live campaign state is in [STATUS.md](STATUS.md). This file is for what is settled.

📌 **Citations of the form "STATUS 09-22" or "STATUS L1946"** point at the campaign log as it
stood before the 2026-09-30 cleanup: `git show d70dd1e:docs/STATUS.md`. STATUS has held only
the live state since then; its durable facts were moved here (§53–§60 and part 4, the v4 design record) or into
CLAUDE.md §5.

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
   check, not an independent observation. Read CSI, beside the residuals — and only
   over ground the solver actually ran (finding 37).

4. ⚠️ **A waves-off CSI / POD / FAR is not on the same footing as a waves-on one — but it
   is a real number and the runner keeps it.** Waves-off is a legitimate configuration, not
   a broken one: Grimley et al. 2025 run exactly it (finding 22). The row carries
   `extent_admissible=False`; judging what that permits is the reader's call. Measured on
   v1.5, `naccs-premier` − `naccs-nowaves`, still-water level where both are wet
   (2026-08-20, off the verified-WHOLE runs):

   | region | mean | median | p90 | p99 | max |
   |---|---|---|---|---|---|
   | open coast | +0.088 | +0.084 | +0.198 | +0.830 | +3.743 |
   | estuary | +0.061 | +0.065 | +0.171 | +1.247 | +1.877 |

   🔴 **This finding used to assert "~+0.34 m of setup on the open coast". THAT NUMBER IS
   NOT REPRODUCIBLE on the verified-WHOLE runs, by any of three routes.** At the open-beach
   HWM marks — the population the claim is about — SnapWave delivers **+0.024 m** (scorer's
   own sampler and estimator, marks wet in both arms, n=7) or **+0.017 m** (50 m depth
   median, q≤3, n=12, the same n=12 the STATUS open-beach table uses). Over the whole
   open-coast MOTF footprint it is +0.084 m, and only 5.12% of those cells reach 0.34 m.
   The figure was quoted in six places and measured in none of them. Corrected 2026-08-20.

   🔴 **Consequence — the three-way agreement in STATUS is broken.** That passage reads
   "on the open beach three independent routes agree at ~0.35 m: marks need 0.37, SnapWave
   delivers ~0.34 (§4), Stockdon at β_f=0.02 gives 0.33." The first and third stand; the
   second was this finding's unmeasured assertion and is really ~+0.02 m. Two routes agree,
   SnapWave is not one of them, and β_f was already flagged there as calibrated to the
   target rather than validated against it.

   🔴 **RETRACTED WITHIN THE HOUR — the `raritan_bay` sign flip is a `zsmax` ARTEFACT, not
   dissipation.** It was reported here as measured dissipation on four lines of evidence.
   All four were computed from `zsmax`, and all four inherited the same bias. `zsmax` is a
   running max at the SOLVER timestep; the hourly `zs` field is not. Their gap differs by
   ARM, and it is not small:

   | region | premier excess | nowaves excess | **arm gap** | Δ via zsmax | Δ via hourly zs |
   |---|---|---|---|---|---|
   | open coast | 0.010 | 0.004 | +0.007 | +0.090 | **+0.089** |
   | Sandy Hook Bay | 0.194 | 0.166 | +0.028 | +0.117 | +0.162 |
   | Lower Bay / SI | 0.103 | 0.114 | −0.011 | +0.108 | +0.091 |
   | **Raritan Bay** | 0.255 | **0.431** | **−0.176** | **−0.129** | **+0.059** |

   The −0.176 m arm gap in Raritan Bay *is* the −0.129 m "damping". Measured on hourly `zs`
   over the same faces the sign REVERSES to +0.059, the crest-time water volume in the basin
   is **+0.8% HIGHER** in premier, and the 10-min station series at `sss_great_kills` and
   `sss_arthur_kill_mouth` differ by only −0.011 and −0.050 m — with premier showing MORE
   sub-hourly variance, not less. There is no surge-damping signal.

   ⭐ **What is real, and is a bigger problem than the thing it replaced:** in Raritan Bay
   the waves-off run carries **0.431 m** of sub-hourly excursion above its own hourly field,
   against premier's 0.255 m. Every spatial score in this project — HWM residuals, the
   floodmap, MOTF CSI — is computed from `zsmax`, so in that basin they all inherit a
   ~0.18 m arm-dependent difference. ✅ **Settled by §40:** the excursion is a real,
   coherent basin seiche, so a single arm's bay `zsmax` stands; what is fragile is its
   PHASE between arms, which is why bay arms are compared paired.

   ✅ **The open coast is CLEAN and the §4 correction above still stands**: excess 0.010 /
   0.004, arm gap +0.007, and zsmax (+0.090) agrees with hourly (+0.089) to 1 mm. The
   retraction of "~+0.34 m" is unaffected.

   What survives, and is the whole of the caution: wetting is threshold-nonlinear, so the
   effect is not only in level — **2.24 km² of open coast is premier-wet and nowaves-dry**.
   In extent terms SnapWave is worth **ΔCSI 0.018**, against **ΔCSI 0.011** between the two
   waves-on arms, so a table that ranks them together carries a confound larger than the
   signal under test. No scored mark changes wet/dry state between the arms. Conditions
   for the 0.018: v1_5_raritan, `naccs-premier` − `naccs-nowaves`, MOTF CSI over the
   simulated mask, 2026-08-20, container engine v2.3.3 with `snapwave_wind = 1` — i.e.
   waves imposed in the WIND direction (§43). It is the size of the waves-on/off confound
   on that engine, not a measurement of correctly directed setup. **Re-measured on the fixed
   engine (v3, repaired mask, `metrics.csv`, unpaired): premier CSI 0.706 / POD 0.880 /
   FAR 0.219 vs `naccs-nowaves` 0.697 / 0.853 / 0.207 — ΔCSI 0.009.**

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
    ⚠️ That seal only sees cells wet AT BUILD; high-ground outflow faces the surge tops later
    drain just as well (§50).

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
    ⚠️ For a RAISE (a building burn) read `z_level` instead: the burn raises `z_volmax`
    (storage up to `z_zmax`, p50 +2,461 m³ on v3) while the storage it removes sits at a
    given water level; `z_zmin` moves wherever a cell's lowest pixel is under a footprint
    (11,995 faces on v3, against 849 fully covered). §55.

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

20. **SnapWave is nearly all of the runtime, and our configuration, not the method, makes
    it so.** v3 premier: 96.9 % of simulation time, 23.4 h of a 25.5 h solve, against 46 min
    for the same mesh waves-off; its 84 min "Time in input" is also SnapWave (the
    nearest-point search for 1.12 M SnapWave-only band nodes; `wave-coupled` pays 45 s).
    `scripts/snapwave_cost.py <run>` reads it from the log (a call over 999.99 s logs
    `took ******`; the script imputes those — summing `took` drops the slowest 16 of 145).
    **Where the time goes** (premier log, 145 calls, fit R² 0.999): call ≈ 42 s +
    1.33 s·iterations + 103 s·W, W = full-domain-equivalent sweeps; median W 3.8; 56 % of
    node-work is in iterations 1–5 and 10 % in iterations 26+, so an iteration cap or a
    looser stop buys little (v2.4.x's "99 % converged" rule would save ~0.8 h). The
    per-call cost is nodes × direction bins × work per node × passes: 2.89 M nodes × 72
    bins (5° over 360°; engine default 10° over 180° = 18), wind growth on (a second
    tridiagonal solve per node; wind off was 4–5× cheaper per call), and v2.3.3 COLD-starts
    the energy field every call (`snapwave_solver.f90` L486–496; v2.4.x warm-starts).
    Leijnse et al. 2025 report 13.3 % of compute and 5–10 s per call on 1.4 M nodes on
    v2.1.1; the paper does not state its direction settings, but the v2.1.1 source fixes the
    sector at 180° (`ntheta = int(180.1/dtheta)`) and has no wind source term. 🔴 **The node sweep is SERIAL** in v2.3.3, v2.4.x
    and `main` (nodes walked in upwind order; no OpenMP around it, and no `!$acc` in
    `snapwave/*.f90`, so a GPU build speeds only the 3 % that is flow): every finished
    64-thread v3 solve used 5.9–6.8 effective cores. A SnapWave-only shelf band's cost is
    set by the REFINEMENT gate, not the SnapWave mask: v3's `low_water` gate (level 2,
    zmin −20) made 75 % of the 1.1 M band cells 50 m. Engine facts that bear on reading it:
    one period per cell, no frequency spectrum, no whitecapping (friction is the only
    distributed shelf sink), no diffraction; wind-off `tp` is constant (12.68 s everywhere
    on v3); no dissipation field is written (`hm0 tp wavdir hm0ig tpig snapwavedepth beta
    fwx fwy`; forces need `storefw = 1`); the log line about band nodes "using the nearest
    SFINCS point" means water level and wind, not the bed. STATUS 09-14, 09-29;
    `logs/wave_boundary_v4_2026-09-29/`.

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

37. 🔴 **Score only where the solver actually RAN — `da_dep` will not tell you where that
   is.** The subgrid DEM carries valid bed across the whole grid RECTANGLE, so `dep > 0` is
   true on ground the mask left inactive. Every metric that reads a raster has to be told
   which is which; this is now the third place it bit (after the HWM region clip and
   `_fill_inactive_holes`). MOTF was scoring unsimulated ground in **both** directions:
   unreachable MOTF-wet booked misses the model could not have hit, and — the one nobody
   was looking for — **`downscale_floodmap` bleeds**, painting zsmax onto low ground under
   INACTIVE faces, which booked FALSE ALARMS the solver never computed. Measured 2026-08-20:

   | | removed | of which MOTF-wet | of which model-wet (bleed) | CSI | POD | FAR |
   |---|---|---|---|---|---|---|
   | `v1_5_raritan` premier | 76.6 km² | 2.56 km² | 0.0018 km² | 0.662 → **0.685** | 0.789 → **0.821** | 0.195 → 0.195 |
   | `v1_monmouth` fixture | 30.9 km² | 2.78 km² | 3.68 km² | 0.638 → **0.684** | 0.766 → **0.793** | 0.208 → **0.167** |

   🔴 **The screen is the run's own `msk`, NOT a region polygon.** The active mask is region
   + `mask_zmin` + always-active boxes, and `include_polygon` only ever ADDS cells, so the
   mask legitimately extends past the polygon — on `v1_monmouth` the registry region is
   2,494 km² against the run's own 2,909 km², 415 km² apart, and the bleed sits up to
   1.45 km outside both. Either polygon is wrong on one domain or the other;
   `validate.simulated_mask` is wrong on neither and cannot go stale against the run.
   `motf_km2_unsimulated` reports what was removed — quote it beside the CSI.

   🔴 **The scoring BED must cover every active face.** hydromt writes
   `dep_subgrid_lev3.tif` only under the finest faces; a scorer on it treats every coarser
   face as off the grid. On v3 (08-29) lev3 covered 10 % of the rectangle; 51 of 140
   in-region HWMs (all on active faces, 49 wet) had no lev3 coverage — n 63 → 94 once the
   merged all-level `dep_subgrid_merged.tif` was used — and the truncated frame FLATTERED
   extent AND hid skill: CSI 0.83 → 0.70 on the full frame, hits 359 → 702 km². Never quote a
   lev3-only extent score beside a merged-frame one. v4 scores on the lev2 lattice (3.125 m,
   each pixel the mean of its 2×2 lev3 pixels): the 1.56 m bed is 77 GB as float32 and the
   validate peaks at ~10× its raster (v3 99 G; v4 191 G on 3.125 m). The NJ-only MOTF sheet
   reads NY land as confidently dry (pixels are only {0,1}); v4 screens with a validity
   raster where the NJ-only DEM has data (`Domain.motf_valid_tif`), because a box staircase
   cannot follow the DE/PA river border — the inherited `staten_island` box held 41 km² of NJ
   land on v4.

38. **The Keansburg overshoot is MISSING FLOOD PROTECTION, not bad elevation data — and
    MOTF makes the same error, so it cannot arbitrate it.** Diagnosed 2026-08-20,
    `scripts/diagnose_keansburg.py` → `reports/keansburg/` (both retired 2026-09-21, in git history). Three marks read obs
    ≈1.55 m against a modeled ~3.3 m (residuals +1.67…+1.77, the worst on the domain);
    every neighbour within 2 km (obs 3.6–4.4 m) validates to ±0.5 m.

    - **The bed is right.** On five shore-normal transects the model's subgrid crest
      matches USACE 2010 1 m lidar to ±0.05 m and CUDEM to ±0.3 m everywhere — the
      Keansburg beachfront dune stands 6.0 m in the model, exactly as surveyed. The
      earlier "the 100 m cells average the berm away" hypothesis is REFUTED at the
      dep level (the cell-EDGE flux tables remain unexamined).
    - **All three marks sit in the pocket BEHIND the USACE Keansburg protection**
      (levee + Waackaack Creek tide gates; 6155 is literally "upstream, right of
      wooden walkway bridge" — a creek mark). The corridor at lon −74.136 has no
      continuous barrier above ~2.9 m in ANY product, so with no structures in the
      build the pocket connects to the bay and equilibrates to bay level (~3.3 m).
      In reality the gates + levee throttled the inflow and the interior stopped at
      ~1.55 m. The marks are consistent with each other and almost certainly REAL.
    - **MOTF floods the pocket too** — wet at all three marks — because a bathtub has
      no structures either. So extent agreement is high exactly where the levels are
      most wrong: local CSI 0.768 (better than the 0.685 domain figure), model wet
      9.11 km² vs MOTF 7.86 km² in the Keansburg box, FA 1.74 km², miss 0.49 km².
      An extent product cannot see a volume-limited flood; only the marks can.
    - ⚠️ 6156/6133 are q3 (outside the q≤2 headline set); **6155 is q1 and IS in it**,
      contributing the largest single residual to `raritan_bay`'s RMSE 0.452.

    **Remedy adopted (user, 2026-08-20): the weir delta arm — and the smoke PASSED.**
    `sfincs.weir` = the protection line traced along the USACE-2010 lidar ridge (89
    vertices, lon −74.150..−74.128, crest = max(ridge, 2.9 m) — the 2.9 floor closes
    the Waackaack gate reach at the measured adjacent levee crest; cd 0.6; the line
    deliberately stops WEST of East Keansburg, which genuinely flooded to 3.57 m).
    No z/mask change — fingerprint UNMOVED, verified on the staged copy.
    - ⭐ **The quadtree Faber engine HONORS `weirfile`**: `diag-nowaves-keansburg-weir`
      logs `reading weir file` → `217 structure u/v points found`, output WHOLE.
      (Checked because of the obs-point silent-drop scar — an accepted-input log line
      is the only proof a staged file was read.)
    - **Effect at the pocket marks: 3.27–3.38 m → 2.48–2.49 m** (residual +1.7/+1.8 →
      **+0.9**). The pocket is now overtopping-limited instead of filling to bay
      level — half the error; the remainder says the real crest/gates outperform a
      2.9 m broad-crested weir at cd 0.6.
    - ⚠️ Marks 2–5 km WEST of the weir moved by −0.2..−0.3 m between the two nowaves
      runs. Do not attribute that to the weir: it is inside this basin's known
      arm-dependent seiche phase (§40). The local capping is 3–4× that band.
    - ✅ **The waves-on decision run agrees (2026-08-21,
      `diag-premier-keansburg-weir`; pre-reg
      `reports/keansburg/preregistration_weir_decision.md`).** Pocket marks
      3.27–3.38 → **2.45–2.46 m** (residual +0.87–0.91); Keansburg box
      (−74.155..−74.105, 40.425..40.455) CSI 0.761 → **0.783**, FA 1.28 →
      **0.52 km²**, miss 0.24 → 0.68 km² (MOTF floods the pocket too, so correctly
      drying it books misses against the reference's own error). Domain-wide: HWM
      Δ RMSE +0.007 m [−0.114, +0.120] paired n=46 — a wash inside the bay ringing
      band (§40); MOTF CSI 0.7108 → 0.7044
      with FAR improving 0.1764 → 0.1682. Promote-vs-delta is the user's decision.
    - ✅ **PROMOTED 2026-08-21 (user decision).** The weir is in the TEMPLATE so every
      arm inherits it; the verified weir runs were adopted as `naccs-premier` /
      `naccs-nowaves` (pre-weir runs banked as `preweir-*`;
      `metrics_2026-08-21_pre_weir_rebaseline.csv`). Headline now: HWM RMSE 0.4084 /
      bias −0.037, CSI 0.7044 / FAR 0.1682. Durable source
      `data/structures_v1_5/keansburg_weir.weir`; `model._ensure_weirfile_key` keeps
      the inp key alive across re-staging (`tests/test_weir_staging.py`).
    The nowaves weir run scores HWM RMSE 0.3867 (`extent_admissible=False`). The weir
    lives in the TEMPLATE, not in the premier alone, because a premier-only weir would
    confound premier-vs-nowaves forever.
    Not indicated: bed burn (the bed already matches the lidar — nothing to burn
    short of inventing a crest the survey does not show). ⏸️ Raising the `bay_fringe` gate
    past zmax 2.0 (which excludes every berm crest on this shore) is a deliberate future
    change, declined for now: the user kept 2.0 verbatim on v3 and v4 for parity with v1.5
    (2026-08-31).

39. **The FA "disconnected = rain" classifier is VALIDATED against a rain-off run —
    and the rain share was an undercount.** The classifier (`validate/fa_decomp.py`): each
    false-alarm pixel is split by whether its water EVER had a wet surface path to tidal
    water — `hmax` is a running max, so its footprint is the union of everything ever wet,
    and a wet component that never touches the sea got its water from rain or runoff. MOTF
    is a surge-only bathtub and cannot contain rain ponding. First read (v1.5 rebaselined
    premier, pre-weir): FA connected 3.45 km² (30 %), never connected 7.96 km² (70 %);
    `motf_far_connected` 0.061 vs `motf_far` 0.176; `motf_csi_connected` 0.795 vs 0.711;
    `naccs-nowaves` disconnected 7.49 km² (rain is arm-independent). Measured 2026-08-21,
    `scripts/measure_rain_share.py` (retired 2026-09-21, in git history; pre-registered in
    its docstring) → `reports/rain/rain_share_v1_5_raritan.csv` (also retired);
    `naccs-premier` vs `diag-premier-norain`
    (both PRE-weir; byte-identical staging minus `netamprfile`), on the MOTF grid under the
    `motf_metrics` screens ∧ simulated-in-both. Ground truth: wet-in-premier ∧
    dry-in-norain (`DEPTH_MIN` threshold).

    | field | value |
    |---|---|
    | FA total | 11.40 km² |
    | **FA rain share (ground truth)** | **75.7%** (8.62 km²) |
    | `disc_precision` — P(rain-true \| labelled disconnected) | **0.991** |
    | `disc_recall` | 0.914 |
    | FA within 5 cm of the wet threshold (flip-marginal) | 1.35 km² |
    | rain share of the WHOLE premier wet extent | 19.7% |

    So `fa_decomp`'s connectivity heuristic is a near-perfect rain detector here:
    99% of what it excuses is genuinely rain, and it misses 9% of the rain-true FA
    (conservative in its claimed direction — the 70 %-of-FA first read above was an
    undercount of the true 75.7%). The `motf_csi_connected` /
    `motf_far_connected` keys therefore mean what they say. ⚠️ Conditions: one
    domain, one storm, infiltration OFF (`model._infiltration_keys` strips hydromt's keys
    on every domain but v4, §59), and both runs share `zsmax` sub-hourly behaviour except where rain
    itself changes it. ⚠️ Runs accepted on the user's visual inspection + the
    `output WHOLE` audit, 2026-08-21, waiving the >26 h three-clock re-audit
    (neither diag run ever had a halk submission against its directory).

    **v3 (2026-09-03, same script, `NJ_DOMAIN=v3`, premier vs `diag-premier-norain`, solve
    61190532):** FA 202.5 km², rain share **93.7%** (189.7 km²), `disc_precision` 0.992,
    `disc_recall` **0.620**, flip-marginal 28.2 km², rain share of the whole wet extent
    27.1%; `motf_csi` 0.710 → 0.809, `motf_pod` 0.894 → 0.824. The PRECISION claim holds
    on both domains; the RECALL does not carry — on v3, 84 km² of rain-true FA is
    "connected" (rain-fed marsh and creek cells contiguous with the surge-wet body), so
    `motf_far_connected` still contains rain there. The script now writes
    `reports/rain/rain_share_<domain>.csv`, one file per domain. Rain-off also costs v3
    real flooding: `motf_pod` −0.07, because 7 % of the MOTF-wet area (marsh platforms) is
    reached only with rain on, and Monmouth's coastal-lake marks are rain-filled
    (`south_coast` 4 of 4 dry rain-off, bias −2.19; `hwm_rmse_scored` 0.384 → 0.754;
    `atlantic_oceanfront` unchanged). On v3 `motf_csi_connected` (0.807 premier / 0.811
    norain) is the fairer extent number for a compound run, with the recall-0.62 caveat.
    ⚠️ A rain-off run also **re-rings the
    Raritan Bay seiche (§40)**: with rain OFF the bay peaks moved +0.3–0.4 m (Great Kills
    3.68 → 4.02 m) while ocean stations did not move, and the his difference is a 40–60
    min oscillation present from hour 3 of the window, before any rain fell. Never read
    bay HWM deltas off a rain-on/off pair.

40. ⭐ **The Raritan Bay sub-hourly motion is a REAL, COHERENT basin oscillation — not
    numerical chatter. `zsmax` scoring in the bay STANDS; what is fragile is its PHASE
    between arms, not its envelope.** Measured 2026-08-21,
    `scripts/diagnose_bay_seiche.py`, pre-registered at
    `reports/seiche/preregistration_bay_seiche.md` (written before any number) →
    `reports/seiche/bay_seiche_{stations,pairs,windows}.csv`,
    `reports/figures/bay_seiche_diagnostic.png`. Read off `diag-nowaves-fasthis`
    (`dthisout=60 s`, 14 accepted obs points, six on the Raritan Bay deep axis over
    11.6 km; SLURM 60693810, hal0344, `output WHOLE`).

    **Primary field — where the excess lives in FREQUENCY.** No physical mode of a 12 km,
    6–16 m basin has a period under the 120 s Nyquist of a 60 s record, so if the
    `zsmax` excess is resolved at 60 s it cannot be sub-timestep noise:

    | | `zsmax` − hourly | 60 s max − hourly | `recovery_frac` |
    |---|---|---|---|
    | axis, median (5 clean pts) | — | — | **0.985** (min 0.950) |
    | `rb_axis_559k` ⚠️ | 1.867 m | 0.536 m | 0.287 |
    | open-coast control | 0.026–0.244 m | ≈ same | 0.98–1.00 |

    **≈ 98% of the excess is motion the record resolves.** The pre-registered threshold
    was 0.7.

    **Secondary — it is coherent, and organized at ALL times.** Magnitude-squared
    coherence between the axis ENDS (11.6 km apart) γ² = 0.934 at 10.4 min, band mean
    0.437 against a 95% noise floor of **0.084**. Split by window (post-hoc), every pair
    is coherent in the quiet pre-storm window as well as at the crest (band means
    0.48–0.80, floor 0.26) — so this is a persistent tidally-driven oscillation the storm
    amplifies 2–5×, not something the storm creates. Bay `hp_std` 0.067 m vs open-coast
    0.016 m, and 0.040 m in the bay even pre-storm (7× Shark River). Adjacent lags are
    **mixed-sign and only ~8% of a period**, i.e. quasi-standing rather than progressive;
    implied speeds 9.4–28.7 m/s straddle `sqrt(g·h)` = 11.7 m/s. Dominant periods 34–60
    min, 4 of 6 axis stations within ±20% of 40 min.

    🔴 **What this does and does not license.** It licenses reading a single arm's bay
    `zsmax` as real water. It does **not** retract the arm-comparison caution: a real
    seiche has a phase, `zsmax` is a running max that samples that phase, and a local
    perturbation re-rings the basin — which is exactly why instantaneous |Δzs| between
    two arms reaches 1.32 m while their crest PEAKS differ by only 0.03–0.15 m. **The
    envelope is robust; the phase is not.** Continue to compare bay arms paired and to
    treat a bay-wide Δ inside ±0.1–0.4 m as unattributable. The size of it, on v3 (pre-repair,
    container engine): Δpeak at the NY bay gauges for four single-flag perturbations —
    rain-off +0.27..+0.41, waves-off −0.18..−0.26, STWAVE for CORA −0.11..−0.26, buildings
    +0.15..+0.28 m. In the buildings pair the his difference exceeds 0.2 m from 44 h before
    the crest with mean Δ −0.005 m and an unchanged 3-h high-pass envelope.

    ⚠️ **`rb_axis_559k` is a discharge-injection artefact, flagged not dropped.** It sits
    **253 m** from the Raritan River source (Qmax 110 m³/s) and carries a single-face,
    sub-2-minute 1.33 m `zsmax` spike its own 60 s series never sees; neighbouring faces
    do not share it. ⭐ **No scored HWM mark is within 500 m of any discharge source**
    (closest 674 m, n=46), so this contaminates no score — but a station or mark inside an
    injection zone reads the source, not the basin.
    **Per domain** (`scripts/source_proximity.py`, staged sources, 500 m;
    `reports/source_proximity_<domain>.csv`): v1.5 0 of 46 (above); **v3 1 of 140
    in-region marks — HWM 6044, 49 m from the Absecon Creek source (01410500)**, 0 of 25
    gauges; **v4 0 of 166 marks, 0 of 48 gauges, closest mark 2.4 km** (6563, Darby
    Creek source 01475548) — v4 injects at the heads of tide where the ring cuts each
    river, so its Absecon source sits 3.2 km above 6044.

    ⚠️ Conditions: ONE arm (waves-off, PRE-weir), one storm. This establishes what the
    motion IS; it does not by itself explain why two arms ring differently. The axis
    follows the **dredged navigation channel** (10–16 m in a bay of ~6 m), so "coherent"
    is established along the channel — the flank points (Arthur Kill mouth, Great Kills)
    agree, which is the check that it is not channel-only. Peak-period resolution is
    limited by the 61-min high-pass: three stations peak at the 60-min band edge.
    ⚠️ The Merian consistency note in the script output (half-wave 33 min on the sampled
    channel vs observed 34.3 min) is **post-hoc with free parameters chosen after seeing
    the answer** — suggestive, never quotable as a match.

    ⚠️ **STATUS recorded that SFINCS silently dropped the six `rb_axis_*` points. That was
    wrong** — the run's own log lists `observation point 1..14` and `wc -l sfincs.obs` is
    14. The acceptance check (log lines vs `wc -l`) is still the right guard and now
    passes; no re-run was needed.

41. 🔴 **Bay-margin refinement is a WAVE-SETUP control, so a refinement change is a
    PHYSICS change — never just a sampling change.** When `refinement_v3.geojson`
    silently dropped v1.5's 25 m `bay_fringe` / `shrewsbury_navesink` /
    `coastal_corridor` bands (STATUS 08-31), SnapWave generated ~+0.5 m of setup at the
    peak inside the enclosed bays where v1.5 has ≈0 (Sandy Hook +0.51, Great Kills
    +0.52, premier − nowaves peak-to-peak) — waves breaking on a 50 m-resolved bay
    shore instead of 25 m. Restoring the bands VERBATIM and re-running (2026-09-01)
    **halved it** (0.19 / 0.26; open-coast control Sea Bright 0.14 → 0.13, unmoved —
    the pre-registered signature), pulled the spurious pre-storm tide-range deficit
    from −0.40 m to −0.04 m at Sandy Hook (setup was propping up the low waters), cut
    HWM RMSE ~0.03 m on every arm, and erased the systematic v3-above-v1.5 offset on
    the 46 shared marks (mean paired delta +0.122 → −0.065; Monmouth-side sign-test
    P 0.011 → 0.152). ⚠️ A residual ~+0.2 m of bay setup vs v1.5's ≈0 REMAINS,
    unattributed — candidates are the still-coarser bay interior (≈50 m vs ≈36 m mean
    face) and the 36-point wave boundary. Conditions: v3 vs v1_5_raritan, premier /
    nowaves arms, Sandy window, his-file peaks; STATUS 09-01. The operational rule this
    bought: **when a domain claims comparability with a predecessor, diff the two
    refinement polygon LISTS by name before freezing** (CLAUDE.md §5) — every
    fingerprint guard passed while the meshes disagreed, because the fingerprint seals
    the mesh you BUILT, not the one you meant.

42. **The two admissible wave sources are NOT separated on v3 HWM RMSE — the tie is
    paired-measured, not assumed.** CORA − STWAVE ΔRMSE −0.0156 m, 95% CI
    [−0.0407, +0.0107] on the 94 shared marks (B=200k,
    `logs/paired_bootstrap_v3_prem_stwave.log`, 2026-09-01): CORA leads every point
    estimate and the CI includes zero, the same shape as the v1.5 boundary comparison —
    quote the point estimate WITH the CI, argue any preference structurally. Where they
    DO differ is bias (−0.156 vs −0.218) and it is concentrated in the Raritan lobe
    (Great Kills peak err −0.07 CORA vs −0.60 STWAVE), consistent with STWAVE grid 07
    (NY Bight) running low against the other grids where they overlap: median max|ΔHs|
    2.5 m (02∩03), 2.6 m (02∩07), 3.7 m (03∩07); shared points took the grid whose centre
    they are nearest; `alpham` was read as nautical-FROM by inference (10-28 00:00: waves
    28°, wind 64°), not documentation. Both rows are CONTAINER-engine, waves misdirected (§43).
    Waves-on vs waves-OFF IS separated, on every engine: container (misdirected) ΔRMSE
    −0.0463 [−0.0718, −0.0170]; fixed engine, old band, IG off (`wave-noig` − nowaves)
    −0.051 [−0.073, −0.033]; fixed-engine premier, repaired mask −0.064 [−0.086, −0.042]
    (§48). Waves are real skill on this coast; which admissible product supplies them is
    not decidable from these marks.

43. 🔴 **SnapWave's wind mode REPLACES the imposed wave direction with the domain-mean
    wind direction** (SFINCS v2.3.3 through v2.4.1 and `main`; introduced by PR #194,
    2025-06-11, the one-day fix for issue #193). With `snapwave_wind = 1` the engine keeps
    the boundary Hs, Tp and spread we impose but launches the spectrum in the direction
    the WIND is blowing from. Measured on v3 (`wave-shelf-steps`, wind on, vs
    `wave-nowind+wave-shelf-steps`, same mesh, band and `.bwd`; energy-weighted mean of
    the boundary-cell `wavdir` vs the Hs-weighted mean of the imposed `.bwd`, ERA5 vector
    mean for the wind; `scripts/snapwave_direction_check.py direction`, 2026-09-11, full
    73-hour maps):

    | hour | imposed `.bwd` (from) | wind-ON `wavdir` | wind-OFF `wavdir` | ERA5 wind (from) |
    |---|---|---|---|---|
    | 10-28 06:00 | 155 | 45 | 155 | 52 |
    | 10-28 12:00 | 164 | 34 | 164 | 36 |
    | 10-29 00:00 | 175 | 35 | 175 | 40 |
    | 10-29 12:00 | 179 | **9** | 179 | 19 |
    | 10-30 00:00 | 167 | 97 | 167 | 145 |
    | 10-30 06:00 | 126 | 171 | 126 | 172 |
    | 10-30 12:00 | 116 | 176 | 116 | 179 |

    Wind-off matches the imposed direction to within the 5° bin on all 73 hours; wind-on
    matches it on 0 of 73 (worst |Δ| 170°) and tracks the wind instead. The wave FORCE on
    the −9 m shelf turns with it (wind-on alongshore, wind-off onshore), so the energy is
    rotated, not just the label. During Sandy's approach the swell came from the S–SSE and
    the wind from the NE, so wind-on sent the swell down the coast: entry-band transmission
    0.63–0.88 vs 0.82–0.99 wind-off, −9 m shelf 0.16–0.36 vs 0.22–0.44 of the imposed
    height; at landfall (wind and swell both from the SE) the two agree. Wind-on also hit
    the iteration cap on 36 of 145 SnapWave calls (8 wind-off) and carries hm0 blow-ups.
    The likely source (a hypothesis from reading the code, never tested): the interior
    solution is stored by bin index too, so a wind swing between calls rotates the
    previous solution used as the initial guess. The patched engine still caps (§44).

    **The mechanism** (`source/src/snapwave/snapwave_boundaries.f90`, tag `v2.3.3` =
    `091f531a`), in `update_boundary_conditions`: (a) `update_boundary_points` builds the
    per-support-point spectrum `eet_bwv` as a `cos^m` bump on a θ grid centred on the
    Hs-weighted imposed direction `wdmean_bwv`; (b) `update_wind_field` forms the
    speed-weighted mean wind direction `u10dmean`; (c) `if (wind) make_theta_grid(u10dmean)`
    re-labels the bins around the wind WITHOUT rebuilding `eet_bwv`; (d)
    `update_boundaries` copies the spectrum to the boundary cells BY BIN INDEX. Net: the
    imposed spectrum is rotated by `u10dmean − wdmean_bwv`. With `snapwave_sector = 360`
    nothing is clipped, only rotated; a narrower sector also clips swell more than
    sector/2 from the wind. There is no input-file workaround — the bump always lands on
    the grid centre whatever the `.bwd` says. Before PR #194 the guard was
    `if (ntwbnd > 0) make_theta_grid(wdmean_bwv)`, which was correct.

    **Breaking is NOT the sink and friction is unchanged**: Baldock reconstructed per
    depth bin from `hm0 / tp / snapwavedepth` with the engine's own `Hmax = γ·h` form
    gives Qb = 0.0000 (p90 ≤ 0.003) in every band bin in both runs, and the friction
    dissipation `0.28·ρ·fw·u_orb³` (0.6–12 W/m²) is identical between them. The
    wind-off run "won" on the shelf by getting the DIRECTION right, not by physics.

    **Consequence for the record**: every wind-on arm scored to 2026-09-10 — v1.5 and v3
    `naccs-premier`, `wave-stwave`, `bed-buildings`, `diag-premier-norain`,
    `wave-shelf-steps`, `wave-fw01+wave-shelf-steps` — imposed its waves in the ERA5
    domain-mean wind direction. Their numbers stay in the CSVs, flagged
    `snapwave_direction = wind`, and are re-baselined deliberately on the fixed engine
    (the native patched v2.3.3 build tagged `nj-winddir-fix-1` in its `Build-Revision`;
    STATUS 09-10 PM, the 09-10 evening plan). The §4 ΔCSI and every "waves-on" HWM
    number before that epoch are numbers for MISDIRECTED waves. Diagnostic:
    `scripts/snapwave_direction_check.py` (`direction` is the pass/fail table; `bands`,
    `breaking`, `convergence`, `force` are the supporting reads).

    **Measured effect of the fix (2026-09-13, `bed-nobuildings+wave-fw02+wave-noig` = the
    `wave-shelf-steps` configuration on the patched native build, full 73-hour window,
    STATUS 09-13):** direction 73 of 73 hours within 5° (worst 0.0°); the −9 m shelf at
    10-29 12:00 carries 1.01 / 0.83 / 0.70 / 0.64 of CORA's −10 m wave at Sea Bright /
    Atlantic City / Ocean City / Sea Isle against 0.48 / 0.47 / 0.36 / 0.34 unpatched and
    0.83 / 0.79 / 0.67 / 0.56 wind-off (`scripts/wave_shelf_reference.py`); spike
    cell-hours 63 k vs 599 k; cap-hits 55 of 145 (36 unpatched, 8 wind-off). The HWM score
    did NOT move: paired ΔRMSE +0.014 m [−0.006, +0.035] (n 94, median, 50 m). What moved
    is WHERE the water is: the NY bay gauge peaks (Great Kills, Arthur Kill mouth, the
    Narrows) drop back to the waves-off values and the open coast rises 0.03–0.09 m — the
    unpatched engine's 0.1–0.16 m bay-peak lift was the radiation-stress explosion of §44,
    not setup. In the bay the fixed engine still sits 0.24–0.69 m under CORA's SWAN at the
    peak (Lower Bay N, Sandy Hook Bay pocket, Raritan S; `scripts/snapwave_bay_census.py`
    boxes): SnapWave refracts but does not diffract, so little swell rounds Sandy Hook.

    **The patch** (`hpc/patches/snapwave_winddir_v2.3.3.patch`, engine lineage
    `nj-winddir-fix-1`, then `nj-winddir-igk-fix-1` for the wavemaker backport, §47)
    builds the boundary spectrum centred explicitly on the imposed mean direction, AFTER
    the final `make_theta_grid`, so PR #194's wind-centred grid is kept; a lobe outside a
    sector-limited grid gives zero energy, not NaN; a one-time WARNING fires for wind on
    with a sector under 360°. It is provably a no-op with wind OFF (G2w0: every field
    bit-identical over 5.14 M wave cells × 13 steps, 25/25 iteration counts). **Not fixed,
    on either engine, wind on or off:** each boundary point is launched in ONE mean
    direction (`thetamean`), not its own `wdt_bwv(ib)`, so CORA's along-boundary spread
    (≈140–182° at one hour) collapses to its mean — mild, but real. Filed upstream as
    Deltares/SFINCS issue #362 and PR #363 (2026-09-14; `docs/upstream/`). Bay wind-sea on
    the fixed engine is physically sized (Lower + Raritan Bay subtidal median hm0
    0.26–0.51 m, 0.65–0.68 once the wind passes 10 m/s; wind-off 0.06–0.10), and wind-off
    removes a real process: every back-bay gauge reads hm0 0.00–0.07 m against 0.2–0.5 m
    with wind (Sandy raised ~0.5 m fetch waves in Barnegat Bay).

44. 🔴 **The patched wind-on solve is DETERMINISTIC; the unpatched container-vs-native
    disagreement is compiler rounding amplified by the SnapWave limit cycle, not run-to-run
    noise.** `G3_patched_rep` (same binary, hal0384) vs `G3_patched` (hal0386), the 12-hour
    v3 wind-on cut: every field bit-identical — zs, zsmax, hm0, tp, hm0ig, wavdir max |Δ| 0
    over 15.6 M cell-hours, 25 of 25 SnapWave calls with |Δiter| 0 (`engine_gate.py
    compare`, VERDICT STRICT, 2026-09-13). The same cut on the container vs the unpatched
    native build (2026-09-12) differed by Δzs max 5.9 m, p99 36 cm, p90 8.6 cm, with 15–20 %
    of active cells > 5 cm apart from hour 1, traced to a 34,000 N/m² wave force under a
    spurious 20 m wave in Lower Bay (a physical force is O(1–10)). Consequence: a paired Δ
    between two arms run on ONE binary is an exact number; a Δ across binaries carries
    ~10 cm p90 in the bays and dm-scale transients at the bay gauges, and every pre-09-12
    wind-on row (container engine) is such a sample. Every `metrics.csv` row carries
    `engine`, so the binary is always known. The Sandy Hook limit cycle itself (STATUS
    09-12 AM: a few hundred cells at the period floor cycling with period 2–3) persists on
    the patched engine — 55 of 145 calls capped on the full run — and the period-floor
    lever `snapwave_sigmax` (2 s and 3 s cuts) does not remove it, it relocates the
    blow-ups onto the open shelf; the engine-side interior initial-guess remap is the open
    follow-up.

    **The native build reproduces the container** (2026-09-11, `scripts/engine_gate.py`):
    G1 (hydromt `sfincs_compound` example, no SnapWave) is STRICT — zs / zsmax / h max|Δ| 0
    on every cell and step, patched and unpatched alike — so waves-OFF numbers are
    bit-identical across container and native. G2 (`v1_monmouth`, 12 h, SnapWave) PASSES by
    user decision: zs p99 0.32 mm, zsmax max 5.4 mm, identical boundary `wavdir` and
    iteration counts; the 0.19 m max is three boundary-ring cells 112 m inside the forced
    boundary (53 of 395,574 cells ever exceed 8 mm). Half the bulk residual is glibc's libm
    (the same binary inside the container: p99 0.08 mm), the rest the compiler/runtime.
    `engine_gate.py`'s instantaneous-max bars stay as written and fail at threshold cells by
    design; the envelope, boundary direction and iteration counts are the evidence.
    **Reading the SnapWave log:** `error` is the single worst cell's change relative to the
    field max; `%ok` is CUMULATIVE within a call (a converged cell is skipped thereafter), so
    a capped call means a handful of cells never settle while the field is done. The logged
    cap is `snapwave_niter / 4` (niter 200 = 50 logged iterations); raising niter 100 → 200
    bought no convergence. The limit cycle: capped calls are periodic (period 2–3, identical
    to the last digit for 30+ iterations), on cells along the channel axis in the Sandy Hook
    shadow sitting at the period floor (`tp` 1.1–1.6 s, hm0 6–23 m) — a different few hundred
    cells each hour. On a capped hour the `tp` field is not trustworthy. On a wind-on field a
    shelf |Δhm0| p99 criterion is unmeetable (the control's own spikes give p99 1.57 m); use
    site medians on cap-hit-free hours.

45. 🔴 **`snapwave_igwaves = 1` does NOTHING to SFINCS water levels unless a WAVEMAKER is
    defined — every "IG" arm ever scored (v1.5 `wave-ig`, v3 premier vs `wave-noig`) was a
    null by construction.** The only quantity SnapWave hands the flow solver is the wave
    force, and `snapwave_solver.f90:908` builds it from the short-wave breaking dissipation
    alone (`F = Dw·k/σ/ρ/h`); the IG balance (§A2 of Leijnse et al. 2025, Coastal Eng.
    199:104726) runs beside it and its output `hm0ig`/`tpig` is consumed by exactly one
    module, `sfincs_wavemaker.f90` — the van Dongeren & Svendsen absorbing-generating
    boundary on a `wavemaker_wvmfile` polyline (~5 m depth at high tide), which takes
    `hm0ig` at its points and `tp_ig = snapwave_tpigmean` and injects a randomly phased
    long-crested signal landward of the line. No run in either repo carries a wavemaker on
    the premier lineage (`grep wvm experiments/*/*/sfincs.inp`). Measured on v3, 2026-09-17:
    premier (IG on) vs `wave-noig` (IG off), same binary, paired ΔRMSE +0.0005 m, 95 % CI
    [−0.0024, +0.0036] on 94 marks — identical to the millimetre, as it must be. IG on
    costs ~4 h of a 25 h solve for a field nobody reads. What IG WOULD inject is not yet
    credible either: at the surge peak 976,804 cells carry `hm0ig` > 1 m (215,992 of them
    SFINCS-active, median 1.24 m in the −10..−5 m band, max 2.0 m), against 0.67 m at the
    bar in Leijnse's SFINCS and 0.33 m in XBeach for a comparable storm. Any wavemaker arm
    is therefore two changes — the line AND the IG shoaling/breaking knobs
    (`snapwave_alphaigfac`, `snapwave_gammaig`, `snapwave_fwig`) — and the toy plane-beach
    case (`scripts/make_snapwave_reproducer.py`, ~1 s) is where the injected signal is read
    first. STATUS 2026-09-17.

46. ⭐ **Extending the SnapWave band north across the Sandy Hook–Rockaway apron to the Long
    Island shore is a real, one-flag HWM improvement on v3 and is the premier's boundary
    from 2026-09-17.** Paired against the Sandy-Hook-cut band on the same binary (94 marks,
    median, 50 m): ΔRMSE **−0.0145 m, 95 % CI [−0.0249, −0.0053]**, P 1.000; `sandy_hook_bay`
    bias −0.250 → −0.109, `raritan_bay` −0.296 → −0.234, `lower_bay_si_shore` −0.166 → −0.257
    (the one basin that worsens); Great Kills peak −0.56 → −0.43, Sandy Hook pre-fail −0.20 →
    −0.14; extent CSI unchanged (0.706). Mechanism: the apron (18–29 m deep, 1,671 CORA
    nodes) was wave-inactive, so nothing reached the Lower Bay entrance from the E–SE; with
    it active, Lower Bay N hm0 is +0.14 m on average over the window (≥ +0.1 m on 43 of 73
    hours, +0.3 m at 14:00/16:00 on 10-29) — but the bay still sits ~40 % under CORA at the
    surge peak (1.53 vs 2.67 m at 10-30 01:00), so the entrance is A supply path, not THE
    deficit. ⚠️ Two reads that looked like failures were the §44 limit cycle: the single
    pre-registered hour (10-29 12:00, Δ +0.05) is a trough of the hourly series, and the
    southern shelf sites differ by 0.2–0.4 in ratio only on hours where one arm had just hit
    the iteration cap — on cap-hit-free hours the four NJ sites agree to ±0.01. Any
    single-hour criterion on a wind-on SnapWave arm must name a cap-hit-free hour. The runs
    made on the old band are `wave-band-sandy-hook[+…]` in `metrics.csv`; the table before
    the rename is `metrics_2026-09-17_pre_apex_rebaseline.csv`. STATUS 2026-09-17.

47. **SFINCS v2.4.0 (Galibier) changes SHORT-WAVE BREAKING and shoreline setup far more than
    it changes IG.** On the plane-beach toy (Hs 2 m, Tp 10 s, shore-normal, wind off, IG off,
    identical `snapwave_gamma 0.7` / `alpha 1.0`), main (v2.4.2-alpha) keeps hm0 0.34 m in the
    last metre of depth where v2.3.3 keeps 0.22, and the mean water level at the shoreline is
    0.136 m against 0.026 m — five times the setup. Galibier's `snapwave_baldock_exponent`
    (default 2), `snapwave_gamma_fac_br` (0.45) and the RF-table solver are the candidates.
    Its IG-side changes (the IG wavenumber built from the short-wave frequency in v2.3.3,
    `snapwave_solver.f90:77`; `snapwave_gammaig` 0.2 → 0.7; the wavemaker orientation factor)
    move the toy by ≤ 0.02 m of hm0ig and 0.002 m of injected IG amplitude; the backport is
    `hpc/patches/snapwave_igk_wavemaker_v2.3.3.patch`, engine `v2.3.3-winddir-igk-fix-1-gf11`.
    The wavemaker itself behaves the same on both engines FOR A LINE WITH LAND ON ITS LEFT:
    nothing seaward of the line, an IG signal of ~0.3 m Hs-equivalent at −2 m from a 0.4 m
    `hm0ig` at the −4 m line. 🔴 **Orientation is the whole game, and the engines differ on a
    reversed line (2026-09-18):** land on the RIGHT of the vertex order makes unpatched v2.3.3
    inject NOTHING anywhere (a mis-oriented piece dies silently), while the backport and
    Galibier inject SEAWARD. The backport therefore carries upstream's semantics; the rule is
    "land on the LEFT", and every piece of a line must be checked against the bed
    (`logs/engine_gate_2026-09-18_wvm_orientation_v3_pieces.txt`: all 10 v3 pieces pass). Consequence:
    moving the premier to v2.4.x is a breaking/setup epoch, not an IG fix, and it must go
    through the 12 h G3 gate (`engine_gate.py`) before any score is compared across it.
    STATUS 2026-09-17, `logs/engine_gate_2026-09-17_igk_toy.txt`.
    **On v3 the epoch is REFUSED (the G5 gate, three 24 h cuts of the apex premier to 10-29 00:00,
    read 2026-09-18 against a pre-registration).** Unclamped main (`snapwave_gammax` 999) explodes at
    hour 1 with CORRECTLY directed swell — 440 k spike cells, hm0 to 38 km, |Δzs| > 1 m on 218 k
    open-ocean cell-hours, the back bays +2 m — so July's explosion was the missing clamp, not §43.
    Clamped main (`gammax 2`) is stable offshore (|Δzs| p99 0.07 m, no cell-hour > 1 m), holds the −9 m
    shelf within 0.03 of v2.3.3 at three of four sites, and lifts shoreline setup by only 1.1–1.4×
    (0.14–0.18 m against 0.13 at hour 24, Sea Bright / Atlantic City) — in the open-coast basins
    (+0.03..+0.10) and not the NY bays (−0.02..−0.10). It runs 1.7× faster with no cap-hits because
    it STOPS on `%ok ≥ 99` (`converged at iteration 3 error = 85`) where v2.3.3 iterates the error
    down, and its IG solve reports `%ok_ig 48` at "converged". The toy's 5× does not transfer to the
    real coast. v2.3.3 stays the premier engine; the wavemaker arm goes on it. STATUS 2026-09-18,
    `logs/engine_gate_2026-09-17/`.

48. **The Sandy Hook shadow marks feel the waves as much as the rest of the domain — and
    most of what they feel is OCEAN setup carried in through the entrance, not the bay wave
    field.** Paired per-mark Δ (modelled level, `naccs-premier` − `naccs-nowaves`, fixed
    engine, median estimator, 50 m, q ≤ 2) on the 28 scored marks in the zone box (lon
    −74.30..−73.95, lat 40.38..40.52): median **+0.113 m** [+0.079, +0.158], mean +0.121
    [+0.097, +0.145], all 28 positive; the 66 marks of the rest: median +0.113 [+0.102,
    +0.147]. By basin: Raritan Bay +0.08 (n 19), Sandy Hook Bay +0.21 (4), Shrewsbury–
    Navesink +0.18 (5); the two spit marks 6106 / 6140 are the largest, +0.27 / +0.24. The
    gauge series say where it comes from: over 10-29 12:00 → 10-30 06:00 the Δ at the NY bay
    gauges averages ~0 and swings ±0.4–0.8 m (the FINDINGS §40 seiche re-ring) but is
    +0.09..+0.19 at the peak hour at every one of them, matching the ocean-side lift at
    `usgs_stormtide_sea_bright` (+0.12 at peak, +0.15 mean); the back bays behind the
    barrier islands carry a PERSISTENT +0.10..+0.14 (never negative) — imported setup. So the
    zone's +0.11 is the domain-wide peak-hour lift with a local excess of ~+0.05–0.10 m in the
    pocket (`sandy_hook` +0.185 vs the oceanfront +0.118; spit marks +0.13 above the domain
    median). Consequence for Phase 4b: D3's pre-registered "< 0.05 m → drop D4/D5" line is
    NOT met, so the spread cut D4 stays on the list — but the number a diffraction fix can
    move is the local excess (≤ 0.1 m at the two spit marks and the pocket gauge), not the
    +0.11. Pooled: ΔRMSE −0.066 m [−0.087, −0.046] (waves are worth 7 cm of HWM RMSE on this
    engine). `logs/phase4b_2026-09-17/D3_paired_zone_premier_vs_nowaves.log`; STATUS.
    **On the repaired mask (§50; re-read 2026-09-30, `paired_hwm_bootstrap.py --by-basin`,
    94 marks, median, 50 m):** ΔRMSE **−0.064 m [−0.086, −0.042]** (0.329 vs 0.393); by group,
    Δ modelled level median / ΔRMSE: open coast (n 23) +0.137 / −0.082 [−0.139, −0.039];
    inlets (14) +0.134 / −0.089; NJ back bays (19) +0.133 / −0.075 [−0.124, −0.019]; NY bays
    (38) +0.048 / −0.035 [−0.067, −0.004]. The wave gain is as large in the NJ back bays as on
    the open coast — imported setup — and about half that in the NY bays.
    **The shadow is GEOMETRY-limited, not spread-limited (D4, 2026-09-18):** doubling the boundary
    directional spread (`snapwave.bds` 30° → 60°, one 24 h cut on the premier's engine) leaves the
    pocket's median hm0 unchanged (−0.005 m at the five swell hours cap-hit-free in both runs, no
    hour ≥ +0.10) while taking ~0.05 of the CORA ratio off the Atlantic City shelf. Only a diffraction
    term can fill the pocket, and §48's ceiling (≤ 0.1 m at the spit) is all it could be worth.
    Diffraction (Holthuijsen et al. 2003, as in SWAN) is therefore a POTENTIAL later engine fix, not a
    current need (user, 2026-09-21); SnapWave v2.3.3 has no diffraction term.

49. ⭐ **The IG lever, measured (v3 `wave-wavemaker`, 2026-09-20): a wavemaker on the MHW − 5 m
    contour injects ~1 m infragravity crests into the 100–400 m surf zone between the line and
    the beach, and an INTACT DUNE keeps them off the street — so the HWM and MOTF scores barely
    see it, and a line closer to shore is not a lever.** Setup: the apex premier + `wvmfile`
    (10 pieces, 142.8 km, 600 m inlet setback, land on the left; engine
    `v2.3.3-winddir-igk-fix-1-gf11`), full 73 h window, 0.96× the premier's wall. Paired against
    the premier (94 marks, median, 50 m, B 200 k): open-coast basins (n 23) paired median
    **+0.021 m [+0.006, +0.054]**, mean +0.084, 20 of 23 up — the CI excludes zero, the
    pre-registered +0.05 line is missed; the movers are BEACHFRONT marks 260–500 m from the line
    (`south_coast` +0.28, `atlantic_oceanfront` +0.10, `shark_river` +0.16, `manasquan` +0.06),
    every mark on a street behind a dune ≤ +0.03. NJ back bays +0.007 [+0.002, +0.014] (the
    setback holds); the NY seiche basins −0.049 [−0.078, −0.021] (every Raritan / Sandy Hook Bay
    mark down — the §40 re-ring, a 1–2 h oscillation with whole-window mean −0.007 m, not a
    shift); pooled ΔRMSE +0.002 [−0.020, +0.023]; MOTF POD +0.004. Mechanism, binned by DISTANCE
    from the line (binning by depth lumps the surf zone with the back bays and misreads it):
    landward the bed climbs −3.9 → −1.9 → +1.5 m over 0–400 m, and Δzsmax over the peak block is
    **+0.97 / +0.97 / +1.04 (p50, 0–200 m; p10 ≥ +0.63)**, +0.40 at 200–400 m, then +0.017 at
    400–800 m and +0.007 beyond; 9,686 dune-crest faces at 2.2–3.5 m are newly wet. The crest is
    the 6-h maximum of a random-phase signal of ~0.28 m std (the Sea Bright storm-tide sensor,
    170 m off piece 9: modelled peak 2.91 → 3.30 against 3.47 observed — a surf-zone sensor is
    the one gauge where IG is the right comparison). Seaward of the line, from 100 m out, zs and
    zsmax are unchanged (p50 ≤ +0.02, p90 ≤ +0.05). ⚠️ Three consequences. **The size of the
    injection is §45's open question, not answered here**: a 0.28 m std shoreline IG is the
    `hm0ig` already flagged as 2–3× Leijnse's, and the score cannot arbitrate because the dune
    hides it. **The physically important IG effect in Sandy — dune erosion and breaching that let
    the ocean into the back — is morphology SFINCS does not have**, so "IG reaches the streets"
    is a `bed-` lever (lower the dune where post-storm lidar says it failed), not a wave lever.
    And **the `igk-fix-1` build is not a no-op on the real shelf**: `hm0ig` +0.14..+0.23 m
    seaward of the line, whole-run max 6.2 vs 3.0 m, with `zs` unchanged there — invisible at the
    marks (§45, uncoupled), but the seiche trigger (line vs build) is not separable from this
    pair. **Size and consequence, measured the same day (steps 2 + 3, pre-registered):** the
    crest is the right ORDER and on the LOW side. Stockdon (2006) on NDBC 44025 / 44065's Sandy
    maxima (Hs 9.65 / 9.86 m, DPD 14.8 / 13.8 s; `data/validation_v3/ndbc/`) gives a dissipative
    beach (ξ0 0.11–0.12 with the model's 0.006–0.02 foreshore) with an IG 2 % swash excursion of
    1.8–2.0 m and R2 2.4–2.6 m; the USGS sandline-change transects (doi:10.5066/F71Z42HN,
    `data/validation_v3/usgs_sandline/`, 2,348 lines, USGS's own Stockdon Runup / TWL on 1,356)
    put Runup − Setup at 1.85 m (p50), and the wavemaker lifts the model's beach level by
    +1.00 m (p50) on the 1,007 transects with a line — **0.46× Stockdon's swash**, against a
    no-line control south of piece 1 that is identical between arms (Δ 0.00). The model sits
    −1.60 m (premier) → −0.64 m (wavemaker) under USGS TWL at the beach. Observed washover
    (sandline ≥ 20 m landward) on 49 % of transects; the model's beach level clears the transect
    maximum on 6 % → 10 % (POD 0.096 → 0.175, FAR 0.174 → 0.110). The MOTF sheet scored by
    distance from the line moves only within 1.5 km of it (0–400 m: POD 0.729 → 0.803, FAR
    0.114 → 0.214; ≥ 1.5 km unchanged) — and ⚠️ a storm-tide sheet interpolated from marks books
    beach-face swash as a false alarm by construction, so it cannot arbitrate the strip; the
    sandline can. So §45's "2–3× Leijnse" is
    reversed at the shoreline (an `alphaigfac` arm would be an INCREASE, not a cut), and the
    physically decisive step is still the fixed bed: half of Sandy's transects lost their
    sandline, which no wave setting can reproduce. ⚠️ On the Sandy Hook spit (lat > 40.41) the
    premier's 4–6 m "beach levels" are the §44 limit-cycle spikes, not runup — exclude them from
    any beach read. STATUS 2026-09-20, `logs/wavemaker_reads_2026-09-20/`.

50. ⭐ **An outflow edge on HIGH GROUND is a drain too, once the surge tops it — v3's NY edge
    was leaking the Raritan / Lower Bay surge, and walling it closes about half of the
    west-bay deficit.** v3 left 629 `mask==3` faces along the Staten Island and
    Brooklyn/Rockaway shores, the Arthur Kill corner and the Raritan River cut. Dry at build
    (p50 +2.4..+2.9 m), so §10's wet-cell seal never saw them; at the surge peak they carried
    **~40,000 m³/s** out of the model (gk11 edge-flux estimator, order of magnitude; the Raritan
    cut ~10,700 of it). The repair (`V3.mask_overrides`, four `3 → 1` boxes;
    `premier.V3 = 1596ce1ecc71b374`) makes them ordinary active cells; nothing else changes.
    Paired against the same arms on the old mask (`mask-drain-edge+…`; inputs byte-identical
    but `mask`, same engine), **three configurations agree** — waves-off / premier /
    wavemaker: Arthur Kill mouth Δpeak **+0.25 / +0.22 / +0.24 m**; open-water zsmax +0.2..+0.26
    at the west end of Raritan Bay; `raritan_bay` marks up in 16 of 19, scored bias −0.32 →
    −0.20 / −0.23 → −0.13 / −0.29 → −0.15 (median, 50 m); NY seiche-basin ΔRMSE **−0.11 / −0.09 /
    −0.11** (CI < 0 in all three); every basin south of Sandy Hook ≈ 0; lower Raritan
    +0.4..+0.7 m through the storm; HWM 6102 (1.07 km from the cut) +0.57..+0.66. The Raritan
    cut alone is ~1/5 of the Arthur Kill gain and all of the lower-Raritan gain (cut-split
    test, 09-22). **What it leaves:** the repaired premier's Arthur Kill mouth peak is −0.22 m
    against the gauge, Great Kills ~−0.25 (sensor-corrected; the raw −0.45 carries a ~+0.2 m
    datum-like sensor offset), and the EAST bay sits ~0.2 m low in all three repaired runs
    (`sandy_hook_bay` −0.21..−0.27). ⚠️ **The old premier's good east-bay score was not
    robust**: on the drained mask its Sandy Hook Bay sat ~0.15 m above every other run
    (Sandy Hook gauge 3.48 vs 3.31–3.37; `sandy_hook_bay` −0.11 vs −0.21..−0.31), so its pair
    reads as an east-bay DROP and a flat NY-bay median (−0.015) — a mix of 19 marks rising and
    16 falling, not a null. The §40 seiche phase is the candidate. ⚠️ Waves-on pairs are not
    bit-quiet far from a change (open water south of 40.0: p50 0.000, p1/p99 ±0.02..0.03 premier,
    wider with the wavemaker; Atlantic City +0.03) — that is SnapWave's iterative solve, not a
    second change. Unexplained, small, in every pair: the whole-window mean at Great Kills /
    Arthur Kill / Sandy Hook drops 1–3 cm with the wall, through ordinary tides too.
    STATUS 2026-09-22 → 09-24, `logs/mask_repair_2026-09-22/`.
    **The forcing is not what is low.** The Narrows arm forces 3.42 m, the observed
    `sss_narrows_si` peak; the Arthur Kill arm forces 4.04–4.11 m, ABOVE the AK-mouth gauge's
    3.81 m 1.5 km away. The drain flattened the along-bay tilt (model 0.12 m against ~0.3 m of
    steady wind tilt from ERA5 20–21 m/s over 8 m of water); walled, the tilt is 0.37 → 0.59 m
    against ~0.4–0.6 at the gauges. At Great Kills the wall is worth only +0.06 m (the entrance
    resupplies the central bay). **Why a wall and not a moved edge:** the MOTF raster cannot
    arbitrate (Staten Island is off the NJ-only sheet), 9 of the 17 HWMs in the SI window
    stand outside the model, and moving the edge inland puts NYC land in the model — a domain
    change. A wall ponds, so the walled run is the upper bound on the edge's worth and the
    drain the lower; the drain removed ~3 × 10⁸ m³ against ~2–3 × 10⁷ m³ of plausible SI storage.
    **The Great Kills sensor offset:** `sss_great_kills` (STN site 7560, a bulkhead inside
    Great Kills Harbor; no wave noise, surveyed 1.902 m and reads 1.893 dry) sits +0.25..+0.37 m
    above Sandy Hook / AK / the Battery at pre-storm slack high water on the upwind shore for
    3.5 h while those three agree to ~0.1; at the same site re-surveyed in 2015, during Jonas
    2016, it sits only +0.10..+0.17 above them. NACCS is 0.35–0.39 low at Great Kills and
    nowhere else in the bay, and the q1 HWM 6413 1.6 km away reads 3.81. Working value: treat
    the observed Great Kills peak as ~3.75–3.85 m, not 3.99 (cause unproven — flag, do not
    rewrite the file); Arthur Kill mouth is the cleaner number.

51. 🔴 **A NetCDF `inifile` is silently read as BINARY by SFINCS v2.3.3 (and `main`), and a
    `zsini` start floods every disconnected low spot — so a sea-level-offset run needs a
    BINARY, sea-connected start.** (1) `sfincs_initial_conditions.F90` picks the NetCDF
    reader with `if (zsinifile(nchar - 1 : nchar) == 'nc')`, where `nchar` is declared and
    never assigned; on the native -O3 build a `.nc` file went down the binary path and the toy
    model hit the minimum time step at t = 0 (2026-09-28). The binary reader takes a raw
    `real*4` stream, one value per ACTIVE point in quadtree face order (`msk > 0`,
    `sfincs_domain.f90`); verified on the toy: start +1.000 on every flagged-wet low cell,
    dry on every flagged-dry one, clean run. (2) `zsini` alone sets `zs = max(z_zmin, zsini)`
    on every active cell, connected or not. On v3 at +2 m that is 15,517 cells (1.0 % of the
    floodable ones) the sea cannot reach through the subgrid sills (`uv_zmin`) — the
    Keansburg levee, the Monmouth coastal lakes (Deal, Wesley, Como), Cape May's lakes —
    all starting flooded; 21,783 already do at +0 in every template start. The fix is
    `nj_sfincs/sea_level.py`: flood-fill from the forced cells across sills below the level,
    write that as the binary inifile, `zsini` = the level for the boundary ramp.

52. ⭐ **A SnapWave boundary that runs DIAGONALLY across the quadtree kills ~40 % of the
    cells inside it on the FIXED engine too — the dead ring is the staircase, not the §43
    bug — and that, not missing shelf, is why `wave-coupled` lost.** v3 `wave-coupled`
    (SnapWave on the SFINCS mask, boundary on the −10 m line, `winddir-fix-1`), at 10-29
    20:00: **2,607 of 6,848 cells touching the boundary dead (0.38; 0.43 on the south
    coast)**, dead cells touching 2.03 boundary cells vs 1.03 for live ones — the
    inner-corner signature, the same 39 % measured before the fix. The premier's
    grid-aligned stepped band: **0 of 2,466**. On the 19 map hours cap-hit-free in BOTH runs
    (§44), −9 m shelf hm0 / CORA at −10 m, median: Sea Bright **1.02 vs 0.59**, Atlantic
    City **0.95 vs 0.81**, Ocean City **0.93 vs 0.54**, Sea Isle **0.73 vs 0.56** (premier vs
    coupled). The coupled run imposes CORA AT −10 m and loses 20–45 % within ~300 m; the
    premier imposes CORA 14–41 km out at −22..−40 m and SnapWave's shelf transformation
    matches SWAN's (both keep ~0.75–0.8 across the band at Atlantic City). So the band's
    value is a boundary that FOLLOWS THE GRID, not shelf physics the −10 m line lacks — the
    measured cost is ΔRMSE +0.028 m [+0.015, +0.044] on 94 marks (STATUS 09-28). ⚠️ A drawn
    diagonal line (v4) inherits the same ring: v4's wave boundary must be stepped.
    `logs/wave_boundary_v4_2026-09-29/`. STATUS 09-29.
    The rule is in the source (v2.3.3): `inner(k) = .false.` for any direction that lacks an
    upwind pair, so a cell with boundary on two sides gets no wave state; the boundary
    spectrum is cut at ±90° around each point's mean direction; `snapwave.bds` is in degrees.
    Band-design facts: Sandy's imposed swell came from the SOUTH through the rise and peak
    (CORA median over the support points 146° → 181° at 10-29 12:00, 112° by 10-30 12:00), so
    a N–S coast band's supply edge is its BOTTOM edge until 10-30 06:00 — read the two halves
    of the window separately. CORA's own SWAN keeps 0.61–0.83 of Hs between v3's stepped line
    (−22..−40 m) and the −10 m line. An UNFORCED band edge drains (hm0 0.15–0.4 m in its first
    300 m). A stepped line hugging −13 m still leaves a 461 k-cell band 6.7 km wide on this flat
    shelf, with more friction loss per km, so pulling the boundary shoreward is not cheaper.
    Upstream has not been told about the corner rule (issue #362 covers only §43).

### Rivers, rings and inputs (harvested from the campaign log, 2026-09-30)

53. ⭐ **River cuts: what is settled.** (a) **A river takes a DISCHARGE, never an imposed
    level, and never free outflow.** An imposed ocean level across a tidal river PUMPS it;
    free outflow DRAINS it (§10: the Navesink lost 92.5 % of its inflow). `no_waterlevel_boxes`
    make an imposed level at a cut a build-time error. (b) **A DRY crossing is still an
    outflow edge** — every dry edge cell is (`OUTFLOW_MAX_BED`) — and drains once water
    reaches it (§50); v3 walled a Tuckahoe outflow cell at +1.22 m 480 m from its source, and
    v4 walls every outflow face within 500 m of a source (`wall_outflow_near_sources_m`;
    every v4 inflow sits 51–248 m from the ring edge). (c) **Sources exist so the model does
    not DRAIN the valleys, not because river flow floods them** in Sandy: peak daily-mean
    inflows on v3's southern rivers were 2.0–18.4 m³/s (Manasquan 18.4, W Br Wading 17.7,
    Toms 13.9 … E Br Bass 2.0); v4's 61 sources sum to 2,205 m³/s on 10-30 (Delaware at
    Trenton ~810, Schuylkill ~728), against ~40,000 m³/s through v3's edge drain and the
    4–5.5 × 10³ m³/s it takes to damp the Delaware tide (PNNL FVCOM). Discharge is daily-mean
    only (USGS archived nothing finer for these gauges in 2012). No discharge-off arm has ever
    been run. (d) **Gauged flow is a LOWER bound** wherever a tributary joins below the gauge
    (Toms/Wrangle Brook; Batsto R 01409500 has no Sandy record; Middle River on the Great Egg;
    the South River, 94.6 mi², ungauged for Sandy — scaling puts it near 13 m³/s against the
    Raritan's 110, deliberately not synthesised). v4 scales by drainage area outside the ring
    (ratio ≤ 1.5 → ratio; > 1.5 → ratio^0.8; a dam at the gauge → 1.0), 10-30 total 2,179 → 2,205 m³/s
    (`scripts/build_river_table_v4.py`, `AREA_SCALE_V4`). (e) **A source is a property of the
    RING, not the river**: 150 m inside the crossing, on the lowest bed within 100 m; verify it
    lands on a wet `mask == 1` face of the FINAL bed (a queued Raritan point once sat on +8.99 m
    dry land) and ≥ 500 m from any station or scored mark (§40). (f) **Placement, three rules
    used so far:** v1.5 cut the Raritan on tidal water (a `no_waterlevel_box`, source at the
    cut); v3 put the landward edge through the head-of-tide GAUGES of the southern rivers,
    where the DEM is ≥ +1 m (Tuckahoe 1.0 … W Br Wading 6.3), so every crossing is dry with the
    source inside; v4 cut each river where the Sandy +3 m water ENDS, walled, flow from the
    nearest gauge — heads of tide move UP at +3 m (Delaware → Washington Crossing, 4.7 km above
    the drowned Trenton falls; Raritan → Manville; Schuylkill → Manayunk; Hackensack above
    Oradell), while the Passaic stays at Dundee Dam (pool 7.4 m > the 6.4 m level). v4's gate
    confirms its cuts: peak rise +3 m vs +0 m ≤ 0.044 m at all 15 (the 16th, Darby Creek,
    was walled after the gate found it leaking, §58f). (g) **A cut does not sit
    where a HUC-12 boundary does:** HUC boundaries never fall at heads of tide (a watershed
    walker put the upper Neshaminy and the Millstone IN and the Assunpink and the Saddle OUT).
    (h) Hydrography traps: the Great Egg and the Tuckahoe are two rivers that do not combine
    above a ring at lat ~39.306 (two sources, Folsom 57.1 mi², Head of River 30.8 mi²); the
    Mullica cluster (4 gauges, ≈ 211 mi²) sits entirely above a cut at lat 39.55; the v4
    cut first named `raritan_manville` was on the Millstone; the Rahway and the Maurice each
    crossed the ring 3× at a meander until vertices moved.

54. 🔴 **Elevation products fail by FILLING, not by leaving holes — and a NoData assert passes
    on a fill forever.** Every one of these is a bed that is present and wrong: (a) **CUDEM
    holds NON-TIDAL water as a flat ~0 m NAVD88 surface** (Union Lake 3.5 km², bed −0.16 under
    a 7.56 m lake surface; the Delaware from the Trenton falls to Yardley, where z_zmin −0.2..
    −0.8 made a fake trench and the v4 peak level 2.3 → 6.4 m; 15.6 km² in v4 overall); CoNED
    carries the same fill. (b) **CUDEM holds the WATER SURFACE, not the bed, on the Passaic /
    Hackensack above lat ~40.72** (CUDEM − eHydro +3.7 m Passaic, +8.5 m Hackensack; NOS H03725
    of 1915 agrees), while from Philadelphia to Trenton CUDEM matches the surveys (median
    −0.09 m). (c) **CUDEM cuts off Ward Point in a razor-straight line and backfills ~230 m of
    headland as −3 to −5.5 m of bay**, and has no tile west of lon −74.25 in the Arthur Kill /
    Raritan band, where the bed falls to 50 m GMRT — ~5 m too shallow in both western channels
    (−8.98 vs −13.56 m; −4.94 vs −9.85 m). When the drawn ring disagrees with the bed and the
    imagery agrees with the ring, suspect the bed. (d) **No public measured bed exists on the
    Delaware above the Trenton falls** (eHydro stops at the head of navigation; CUDEM is flat
    −0.6..−0.9 m to 40.25, then absent) or on the Raritan above New Brunswick; NOS H05647 (1934)
    reads 1.17 m shallower than the 2012 survey in the dredged channel. v4 fills these reaches
    as lidar surface − a gauge mean depth (Trenton 1.20 m, Manville 0.55 m; the Schuylkill at
    Philadelphia is bimodal, 4.15 m pool vs 0.88 m riffle), shallow for pools by ±0.5 m.
    (e) A POSTSTORM product may override a pre-storm one only on non-erodible ground inside a
    declared box: CoNED (2015, post-Sandy) is clipped to `coned_sw_raritan` and excludes
    Oakwood Beach, where CUDEM's −4.08 m pre-storm bed is the right one. Tier ORDER is
    load-bearing: CoNED above `cudem_nj` (phantom water is a value, not NoData), below the
    eHydro carve. (f) Coverage edges: GMRT is required south of lat 39.6; the 1/3″ CUDEM has no
    tile west of lon −74.75; USACE 2010 lidar stops at Cape May Point; `nj_10ft_dem` is NJ-only
    and its `zmin 0.001` screen cannot supply a bed below the waterline. (g) eHydro survey
    NAMES and DATUMS vary per survey ("Arthur Kill" surveys never touch its mouth; `NJ_03_SWO`
    is on COE Mean Low Water, `RR_01_RAR` on MLLW, ~0.17 m apart); CENAP `.xyz` files of
    2013–2016 hold only 2–30 % of the soundings (read the gdb `SurveyPoint` layer); VDatum's web
    API returns HTTP 412 on the tidal Delaware. **The defence is a POSITIVE check:** declared
    dry-land boxes whose bed must read above a stated elevation (`check_dry_land_boxes`) —
    and such a check must be SEEN to fail once, and an empty box is an error.

55. **Buildings are subgrid POROSITY, and for Sandy they barely matter.** Decision in force
    (user + supervisor, 2026-09-03): footprints burned into the fine subgrid DEM (Building
    Block, Schubert & Sanders 2012), not mask holes (a lottery on 25 m cells) and not roughness
    (NLCD already carries developed n 0.10/0.13). NJDEP statewide footprints, NJ-only; 56 % of
    v3's are 2014 post-Sandy lidar vintage, so destroyed-and-not-rebuilt houses are absent.
    8 px per cell resolves them (exact coverage vs pixel burn: bias −0.0003, RMSE 0.017, r
    0.997 at 25 m). The height cap is ground + 4 m (clears 99.994 % of wet land pixels in
    Sandy; ⚠️ overtopped at +3 m SLR). hydromt spaces the uv tables by EQUAL DEPTH, so a cap
    stretches them: land uv `dlevel` p50 0.08 → 0.21 m at `nr_levels` 10. Score extent with
    footprints masked out of BOTH rasters (they are dry by construction in the model and wet
    in MOTF): v3 fixed engine, masked CSI 0.721 vs 0.723 without buildings. HWM:
    `bed-nobuildings` − premier ΔRMSE −0.021 [−0.048, +0.008] (fixed engine, old band; the
    only measurement — never re-run on the apex band); container-era, the whole effect sat in
    the Raritan seiche basins (Δbias +0.196) and was zero on the other 56 marks.

56. **SnapWave bottom friction: `fw` 0.01 is the premier's, and the engine's default.** Every
    arm before 2026-09-11 wrote 0.02, double the default. One-flag pair on the fixed engine
    (old band): `wave-fw02` − premier ΔRMSE +0.0095 [+0.0020, +0.0184], P(arm better) 0.006.
    In SnapWave's coefficient at Sandy's orbital velocities, SWAN's JONSWAP swell value ≈ 0.006,
    wind-sea ≈ 0.010, a 5 cm-ripple Madsen law ≈ 0.02. Friction is the only distributed shelf
    sink (`Dfk = 0.28·ρ·fw·u_orb³`; a 6 m / 13.6 s swell in 18 m keeps 0.87 of its height per
    10 km at 0.01, 0.77 at 0.02).

57. **The southern back-bay pre-storm deficit is bay-MINUS-ocean, and a uniform boundary lift
    cannot produce it.** Time-aligned obs − model over the quiet window 10-28 06:00 → 10-29
    12:00 (v3, 09-01 runs, container engine): Atlantic City NOAA pier **+0.006**, Sandy Hook
    +0.053, but Absecon Channel +0.246, Great Egg +0.397, Ocean City +0.554, Sea Isle +0.329,
    Stone Harbor +0.277, Tuckerton +0.227, Ship Bottom +0.179, with the tide range right to ~5 %.
    Observed bays sit 0.2–0.55 m ABOVE the ocean; model bays sit at it. Observed bay-minus-pier
    grows 0.3 → 0.5 m as boundary Hs grows 2.3 → 3.8 m and turns negative once the wind goes
    offshore — the wave-setup / lagoon-superelevation signature (Ocean City's size is also
    wind tilt, downwind end of Great Egg Harbor Bay). `BRACKET+setup-stockdon` (waves off,
    Stockdon η added at the boundary, β_f 0.03) lifts the bays by ≈ η AND the 7 m-deep pier 1:1
    (AC +0.006 → −0.320), so the mechanism must act between the pier and the bay; its scores
    (RMSE 0.358 / bias +0.074, CSI 0.763; paired vs premier −0.026 [−0.080, +0.027]) are the
    size of the prize for a mechanism inside the surf zone and inlets, never a candidate.
    ⚠️ The seven southern stations are one USGS network; a program-wide datum error is
    unlikely (sign and size agree with independent northern stations and with the wave
    dependence) but not excluded — the check is a calm month against the nearest NOAA gauge.

58. **Mask and ring construction — lessons with no other home.** (a) After a region clip,
    "outside" and "an inactive island inside" are topologically identical, so
    `_fill_inactive_holes` re-activates clipped ground (v1.5: 14,435 cells against 14,141
    outside); the clip is re-applied after the fill, and clip, re-clip and invariant share ONE
    `_outside_region` helper. (b) An always-active box EDGE across a deep channel becomes the
    boundary (v1.5's Narrows arm traced the box, 670 m south of the drawn cut). (c) A bracket
    wide enough to admit the defect it guards is not a bracket (`arthur_kill` passed [15..300]
    with 35 phantom cells; re-cut to [16..40]) — the mirror of §19. (d) Plot the built BC set
    against the drawn ring after EVERY mesh change; every invariant was green while the
    boundary was wrong in three places, and the figure that caught it was two builds stale.
    (e) Declare crossings as coordinate BOXES, never as ring-segment tags (the tagged Raritan
    segment was dry end to end; the real crossing was in the next segment). (f) 🔴 **A ring
    audit on a coarse bed cannot see a narrow channel:** a 75 m max-resampled walk missed a
    110 m-wide Cape May Canal crossing and a 54 m Metedeconk reach; v4's audit on the 25 m
    coarse bed missed Darby Creek, which leaked at +2/+3 m until walled. Walk any segment near
    a canal or creek at 10 m on 1/9″ CUDEM, and treat the SLR gate runs as the real sweep.
    (g) The quadtree builds the region's ROTATED BOUNDING BOX before the clip deactivates it
    (v1.5: 40.8 % of faces are `mask == 0`). (h) `_drop_detached_active_islands` keeps only the
    largest component and ate half of two narrow v1.5 cuts before the bay box; its log line
    counting BC cells always prints 0 (it runs before `create_boundary`). (i) Porting a domain
    drops more than refinement polygons: v3 silently lost v1.5's always-active / dry-land /
    no-water-level boxes (the Raritan lobe was severed), its two Raritan sources, and
    `open_coast_max_y` (the NY limb went under-supported) — diff the predecessor's Domain
    FIELDS and source list, not only its polygon list.

59. **Infiltration (v4 only, user 2026-09-28) has three traps.** (1) v2.3.3's `cna` accumulates
    `cumprcp` / `cuminf` only when `storecumprcp = 1`; otherwise every drop infiltrates — a
    silently rain-off model. (2) `NLCD_HSG.csv` gives open water CN 0, which hydromt clips to 1
    (S = 990 in) — rain on the bays vanishes; `build_cn_nj.py` sets water / NoData CN 100 and
    staging refuses any active face with S ≥ 900 in. (3) Restart files do not carry `cumprcp`
    / `cuminf`, so a solve resumed during the rain restarts with an empty soil (warned, not
    gated). `cna` only ever subtracts from RAIN, never from surge or river water. Check the log
    for "Curve Number method - A".

60. **Gauges, sensors and marks.** (a) USGS storm-tide sensors are mounted ABOVE normal water
    and read their own floor below it, so their statistics are HIGH-WATER statistics; tidal
    range is unmeasurable at every v1.5 sensor. A sensor on ground above normal water (2255,
    +1.45 m) is an HWM with a clock. (b) Pick a NACCS comparison node by DEPTH, not distance
    (a −1.25 m node produced a +1.7 m spurious "product error"). (c) Basin rules are per
    domain: v1's unbounded `sandy_hook_bay` swallowed all of Raritan Bay on v1.5, and
    `unclassified` must stay empty. (d) A mark the boundary cannot move is a constant, not a
    test: 4 `v1_monmouth` `south_coast` marks moved 0.0005 m under a +0.115 m uniform boundary
    offset — detect it with that offset. (e) The q ≤ 2 cut removes the tallest open-coast marks
    (the 5.79 m mark is q 3; q ≤ 2 tops out at 4.18 m on v1.5). (f) 🔶 12 USGS tidal gauges have
    NO data 2012-10-29 04:00 → 10-30 04:00 UTC in the published record (OGC `continuous`, all
    Approved) — likely a USGS day-block gap; `gauge_series_frame` now leaves gaps as NaN instead
    of bridging them (`_in_obs_gap`). (g) A gauge on a dry bank or an un-carved creek reads a
    flat, smoothed series (v4: Sluice Creek, Cohansey at Greenwich, Murderkill at Frederica,
    Christina at Newport — the creek channels are not in the bed).

### Closed — do not re-open

Each of these cost a campaign and is settled. The evidence is in the archive's
`docs/campaigns/`, indexed in [ARCHIVE.md](../ARCHIVE.md).

- **Infragravity waves at a −5 m wavemaker line are a SMALL lever, not a null — measured
  2026-09-20, §49.** The pre-09-17 "null lever" (every metric ≤ 0.01 m; v3 paired Δ +0.0005 m)
  was `snapwave_igwaves = 1` with NO wavemaker, a null by construction (§45). With the line
  (v3 `wave-wavemaker`) the open-coast paired median is +0.021 m [+0.006, +0.054] — real,
  under the +0.05 bar, and confined to beachfront marks: ~1 m crests fill the surf zone and
  the dune holds them. What stays closed: the "IG caused blow-ups" verdict (a pre-sealed
  solver bug), and a LINE CLOSER TO SHORE (the line is already 100–400 m from the beach).
  The injection's SIZE is settled the same day: 0.46× Stockdon's IG swash against buoy and
  USGS-transect checks (§49), so the IG knobs are not a reduction lever either. Open: dune
  failure as the route by which IG reached the streets in Sandy — a `bed-` lever, the
  user's call.
- **The Raritan / Lower Bay deficit is NOT wind-limited at ERA5's shortfall size — measured
  2026-09-22, `wave-wavemaker+wind-x110` paired against `wave-wavemaker` (v3, native
  igk-fix-1 engine, drain edge still open on both).** ERA5 × 1.10 (+21 % stress; bay
  wind-sea hm0 +8..+10 %, boundary hm0 unchanged) moves the Great Kills / Arthur Kill mouth
  peaks by **+0.017 / +0.021 m**, the NY-bay paired median by +0.012 [−0.003, +0.021] (n 38,
  50 m), the open coast by −0.002 (control): dη/dU in the bay is ~0.02 m per 10 % of wind,
  an order of magnitude short of the −0.44 (pre-repair) / ~−0.25 m deficit. ERA5 as applied
  (9 × 12-cell, ~25 km `netamuv` grid) is not low offshore — NDBC 44065 / 44025 22.3 / 22.2
  m/s at 5 m against ERA5 24.8 / 25.1 at 10 m, ≈ 1.0 after the height correction — and ~10 %
  low at the exposed coast (Robbins Reef 0.89, Cape May 0.90). Sheltered land stations
  (Bergen Point 0.59×, Kings Point 0.43×) are not over-water winds. The E wind steepens the
  along-bay tilt by ~0.04 m end to end (west +0.024, Sandy Hook pocket −0.019) and that is
  all of it. So a better wind product (H*Wind / RAP / GAHM) is NOT a bay lever; the deficit
  is supply-side (the edge drain — walled 2026-09-22, §50 — then the bay's wave/setup side). ⚠️ Read as a LOWER bound
  on dη/dU: both arms carried the NY edge drain at the downwind end. ⚠️ NOT a null on the NJ
  back bays: Barnegat Bay is wind-TILTED — Mantoloking (north end) sits −0.25 m for hours
  under the N/NE wind — so a mark's Δ there is set by which end of the bay it is on.
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
- **The Galibier engine is retired** — and re-tested on v3 2026-09-18 (§47: unclamped explodes, clamped buys 1.1–1.4× setup on a looser stop) and refused again. The Faber container (`sfincs-desktop.sif`, v2.3.3; the
  `sfincs-cpu.sif` image was Galibier v2.4.0, never an engine of record, deleted 2026-09-11) was
  the engine for every run to 2026-09-10; from the Phase-2 rebuild onward the engine is the
  native patched v2.3.3 build (the `nj-winddir-fix-1` lineage: `winddir-fix-1`, and
  `winddir-igk-fix-1` for wavemaker arms, §43/§47). Every metrics
  row carries an `engine` column from that epoch; do not compare across it without saying so.
- **The bridge-as-dam sweep on v3's premier bed found no dam — no carve** (2026-08-26,
  scripts retired). 47 wet bodies behind a wall < 300 m (43 with a crest in −1..0 m =
  shoals) and four crests above 0 m (Grassy Sound causeway, Brigantine/Absecon, Shrewsbury,
  Point Pleasant Canal) were all the −1 m threshold reading flats as a wall, or real land.
  CUDEM 1/9″ topobathy has no deck at any of 21 v4 bridges probed (2026-09-26). ⚠️ The sweep
  reports the body cell NEAREST the ocean, not the wall; on a long channel those differ.
  Re-run it on any new domain's merged bed before a freeze.

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
prism and stays open. The price: the full USGS STN set holds 8 marks in the Carteret /
Woodbridge / Elizabeth box (−74.30…−74.15, 40.52…40.68), judged acceptable for a domain whose
goal is forcing Raritan Bay correctly (2026-08-13). v4 computes that shore.

**Also recorded for v1.5** (frozen; details in `git show d70dd1e:docs/STATUS.md` L5498–6767):
dense NACCS forcing beats the 2-node NOAA interpolant on the marks — premier − `noaa-2node`
ΔRMSE **−0.0717 [−0.161, −0.013]** (n 46, pre-weir, container engine; a FORCING-DENSITY
result, not the boundary-move argument; 71 of 71 NACCS support points lie inside the domain
vs 0 of 2). Jamaica Bay's exclusion is a 1.20 km closed wall ON water (−4 to −7 m) that
removes its tidal prism by design; 17 forced cells in the Rockaway Inlet throat were kept
deliberately. v1.5's high-ground outflow edge is the §50 drain, never measured on v1.5 — every
v1.5 bay number carries it.

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

⭐ **How to confirm a MEMBER is ADCIRC and not STWAVE** — the CHS zips are mixed, ADCIRC
(`…_ADCIRC01_Timeseries.csv`, 15-min) and STWAVE (`…_STWAVE07_…`, 30-min) side by side, so
product is a per-MEMBER fact. The ADCIRC columns are `RMP00` pressure, **`ET00` water
elevation**, `UU00`/`VV00` velocity, `RMU00`/`RMV00` wind — and **no wave parameters at all**.
That absence is the check; the builder filters on `_ADCIRC01_` and looks `ET00` up by name
(column 9 is `TM` in STWAVE). The two products have DISJOINT save-point ID spaces (STWAVE
`SP0089` = ADCIRC `SP03584`): join on coordinates with a tolerance, never on id. After the
2026-09-26 merge, v3's NACCS boundary is byte-reproducible only from the pre-merge zips in
`data/NACCS/_originals_pending_delete/` — deleting them ends that.

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

**VDatum per point.** NACCS is MSL epoch 1992; convert LMSL → NAVD88 per save point from
NOAA's 2019 NAVD88 separation grids sampled OFFLINE (`data/NACCS/vdatum_grids/*_tss.gtx`,
offset = −tss), falling back grid → web API → station plane, with a per-row `source`. The web
service fails south of lat ~39.34–39.47 (NOAA's March-2024 grids, whose `tss` reads +0.44 m
at Atlantic City); grid − web = 0.0000 m mean / 0.0009 max over 144 v1.5 points; AC +0.120,
Cape May +0.137, Lewes +0.121 vs gauges 0.122 / 0.137 / 0.122. A station plane errs 2–3 cm on
the shelf and up to 8 cm in the bays. ⚠️ **A scalar will not do**
— the separation drifts 0.065 m across v1.5 (~0.09 m across v3), **concentrated in the Raritan limb**,
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

---

## 4. The v4 design record

v4 = v3 + Delaware Bay and the tidal Delaware, the Raritan to Manville, the Arthur Kill NJ
shore and Newark Bay, with the far banks (DE / PA / Staten Island) COMPUTED, not walled.
Frozen 2026-09-28; registered `premier.V4 = (4881654, 4388, "23ea65f8b81ee1bd")` after four
post-freeze mask patches on the same mesh (Elizabeth source faces, forced-line flanks + the
Henlopen Atlantic beach, Darby Creek). Only waves-off runs exist.

**The rule that drew it (user, 2026-09-25): the ring contains the NACCS Sandy peak + 3 m,
connected from the ocean;** the edge sits on ground ≥ that level + 2 m, ≥ 500 m from it, or on
a declared line; rivers are cut where the +3 m water ENDS (walled, flow from the nearest
gauge); the neighbour basins with their own inlets (NY Upper Bay / Hudson, Jamaica Bay,
Rehoboth Bay, the Chesapeake) are shut off. Traced once into
`data/v4_design/region_v4_vertices.csv` (194 named vertices, 22,860 km²) and edited by hand
since; `scripts/audit_region_v4.py` checks it (target land outside the ring 0.00 km²; MOTF
land inside 1.000 of 1,582 km²; 166 of 193 HWMs inside). Two generators (a rule-driven draft
and a HUC-12 walker) needed rule upon rule and still misplaced rivers, and were retired: an
algorithm CHECKS a ring, it does not make one.

**The forced sea line replaces the −10 m isobath** (user, 2026-09-27): one named-vertex line
node-to-node through NACCS save points, Cape Henlopen → Brooklyn
(`data/v4_design/waterlevel_line_v4.csv`, 99 vertices, 241 km); everything landward in the
ring is active at ANY depth (174 km² of water deeper than −10 m becomes active — the accepted
cost), arms are SECTIONS of the line plus three boxes (Narrows, Kill van Kull east, C&D
canal), 241 NACCS support points. The C&D canal carries a 0.6 m Sandy-peak gradient
(Reedy Point 1.76–1.83 → 1.15 m at Chesapeake City), so where its line sits matters.

**What a crossing needs:** a FORCED line needs NACCS nodes on it, a short crossing where the
level is uniform (a channel or mouth, never an amplifying basin), and both ends above the
forced level + SLR; a RIVER cut is §53; a LAND edge clears the +3 m target. Every DRY edge
cell is free outflow unless walled, so the gate (waves-off Sandy at +0 / +2 / +3 m,
`scripts/overflow_check.py … --compare`) is what finds leaks: it found the Lewes / Cape
Henlopen overflow (~120 outflow cells wet at +2/+3), outflow cells ON water at the ends of
the forced lines at every level (42 at +0), a +3 m-only numerical spike beside them on the
Narrows flank, and Darby Creek. Walls fixed each (`wall_outflow_near_forced_m = 500`,
`wall_henlopen_atlantic`, the `darby_creek` cut); the re-read left 8 / 8 / 12 wet outflow
cells at Breezy Point, overtopped land Sandy flooded. Walls standing in water rise with SLR
as designed (Bayonne +4.1, Jamaica Bay +3.1 m at +3).

**Cost.** 4.88 M faces, 3.97 M active (v3 3.41 M / 1.76 M): 1.90 M inside v3's ring + 1.78 M
Delaware bay / river / far banks + 0.20 M Newark Bay / Arthur Kill / new Raritan + 0.08 M
other; 25 m 1.42 M, 50 m 2.25 M, 100 m 0.26 M, 200 m 0.95 M (52 k active — the Track C coarse
shelf seaward of the line). `narrow_channels` (25 m within 50 m of any channel narrower than
50 m) costs +254 k active faces: 1,349 km of named channel is under 50 m wide, and a cell
wider than its channel mis-carries the flow (van Ormondt et al. 2025). 16 px subgrid
(`dep_subgrid_lev3.tif` 12.6 G). Freeze 4 h 39 / 72 GB; a waves-off solve 1 h 33 – 2 h 14;
the validate needs ~200 G on the 3.125 m scoring bed. **The river reaches are cheap in solver
time; their cost is bed data, mask patches and design effort** (§53, §54). Waves: the
SnapWave domain is v3's area + Delaware Bay below the Liston Point – Hope Creek line, with a
stepped band (`v4_shelf_steps`, 155,793 cells; 7 predicted dead corner cells) —
3.39 M SnapWave nodes, projected ~30 h at the v3 premier's settings; never run.

**First waves-off look (validate 62039939, 2026-09-29; rain on, infiltration on;
`extent_admissible=False`; before any inland-water fix):** HWM RMSE 0.577 / bias −0.408
(median, 50 m, n 110), CSI 0.684. Basins shared with v3 read much lower than v3's own
waves-off run (Barnegat Bay −0.84 vs −0.38; Raritan Bay −0.42 vs −0.20; south_coast −1.07
vs −0.49) — different forcing, mesh and rain treatment, not yet paired or explained.
Delaware gauge peaks run 0.23–0.57 m low (Lewes −0.23 … Marcus Hook −0.57), Newark Bay
−0.71, Christina at Wilmington −0.91.

**Open inland-water defects** (parked 2026-09-30 pending the river-policy decision): the
CUDEM ~0 m fill under lakes and non-tidal rivers (§54a); the Schuylkill backing up to
7–10 m NAVD88 through Philadelphia, attributed to the box-MEAN Manning above `uv_zmax`
(NLCD puts 29 % of its channel pixels in developed classes, n 0.10–0.13) — untested; creek
channels missing from the bed at four Delaware-tributary gauges (§60g); Union / Sunset Lake
dam crests unchecked; no measured bed above the Trenton falls (a DRBC request is out).
