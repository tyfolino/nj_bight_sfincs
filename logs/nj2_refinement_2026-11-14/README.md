# nj2 (Model 2.0.0) refinement, 2026-11-14

## In plain words

- **The 2.0.0 recipe (user, 11-14 10:00)** = v4's refinement, unchanged, plus three new 25 m bands,
  minus v4's `narrows_cut`. File: `data/nj2_design/refinement_nj2.geojson`.
- **v4 comes over intact.** 24 of v4's 25 polygons are in the file under the same names, levels and
  depth gates. The 25th, `narrows_cut`, is dropped on purpose (below). 19 keep v4's exact shape.
  - The three ring-wide ones (`shelf_shoaling`, `inland_floodplain`, `low_water`) are redrawn on
    the nj2 ring. That gives the new Hudson / Upper Bay / East River area v4's 50 / 100 / 200 m
    rule.
  - `narrow_channels` (161.8 → 159.8 km²) and `river_channels_above_tide` (9.2 → 5.7 km²) shrink
    only because the nj2 ring cuts rivers at today's head of tide (A+). Their shapes are v4's.
  - Proof that nothing is lost in the carry-over: a probe of v4's own file on v4's ring today gives
    **4,881,654 faces, level for level identical to the frozen v4 mesh**.
- **The new bands.**
  - `hudson_waterfront` and `newark_meadowlands`: 25 m on NJ ground from −1 to +5 m. Sandy's marks
    reach 3.4–3.9 m around Newark Bay; v4's `bay_fringe` stopped at +2 m and never reached Newark
    Bay at all.
  - `capemay_inlets`: 25 m at every depth over the five inlets and their ebb shoals.
- **Cape May inlets: they were already 25 m.** That holds over every throat and ebb shoal down to
  −8 m (`surf_dune_*`). The new band only fills the deeper delta front and channel faces still at
  50 m (+11 k faces).
  - A truly finer mesh (12.5 m, a fifth level) cuts the whole model's time step from 0.68 s to
    0.44 s, because the Cape May Inlet channel is 20 m deep. That makes every run ~50 % slower.
  - It is also unlikely to move the back-bay deficit, which points at missing set-up physics,
    not at resolution.
  - The user chose to keep the 25 m band and not add the 12.5 m level. The 12.5 m file is kept
    as the record.
- **The Narrows sets the time step for the whole model.** SFINCS uses one time step everywhere,
  set by the slowest cell. Today that cell is in the Narrows: 25 m cells over 33 m of water.
  - The estimate is 0.684 s, against the 1.1.0 premier's logged average of 0.689 s.
  - In nj2 the Narrows is interior water, no longer a forced cut. Dropping `narrows_cut` lets
    those cells go to 50 m. The limit moves to the Cape May Inlet channel at 0.83 s, with 21 %
    fewer flow steps.
  - Flow is ~70 % of a run on the production engine, so the whole run is ~13 % faster even with
    +5 % faces.

## Probe results (v4 ring + v4 coarse bed: everything except the Hudson strip)

Jobs 63918124 / 63918132 / 63918218, hal038x (no halk). Each probe took ~22 min, 13 GB, on one
core. `summary_v4ring_r2.txt`, `summary_v4ring_r3.txt`.

| file (v4 ring) | faces | vs v4 | min dt (s), where | runtime, 72 h waves-on, 64 thr |
|---|---|---|---|---|
| v4's own (control, `p0_v4`) | 4,881,654 | 0 | 0.684, the Narrows | 2.51 h (FINDINGS §20: 9,052 s) |
| with `narrows_cut` (`p1r2`, pre-decision) | 5,139,027 | +257,373 (+5.3 %) | 0.684, the Narrows | ~2.67 h |
| **2.0.0 final, inlets clear of the line (`p4r3`)** | **5,127,339** | **+245,685 (+5.0 %)** | **0.830**, Cape May Inlet jetty channel (−22 m, 25 m) | **~2.33 h** |
| final, before the line clearance (`p2r2`) | 5,129,757 | +248,103 (+5.1 %) | 0.830, Cape May Inlet channel (−22 m, 25 m) | ~2.33 h |
| record: + 12.5 m inlets (`p3r2`, with `narrows_cut`) | 5,277,153 | +395,499 (+8.1 %) | **0.441**, Cape May Inlet channel at 12.5 m | ~3.83 h |

**Faces added per band** (inside the band + 300 m, variant minus control):

| band | faces |
|---|---|
| `newark_meadowlands` | **+244,996** (final; 117,479 → 362,475) |
| `capemay_inlets` (25 m) | +9,936 (final, 400 m clear of the forced line; `ocean` arm back to v4's 3,372 cells) |
| `narrows_cut` dropped | −9,268 |
| `hudson_waterfront` | +1,238 on v4's ring (only its ridge edge is inside). **The real number needs the nj2 probe.** The memo's estimate (hudson_design §2) is ~+118 k for the whole strip under option B, ~64 k of it the 25 m NJ band |
| `capemay_ebb_12m` (record) | +138 k more than the 25 m band (184,168 faces at 12.5 m) |

**Expected 2.0.0 total:** ~5.13 M (v4 ring) + ~0.12 M (Hudson strip) − the river reaches the A+
ring cuts (unmeasured; the v4_hot_plus mask variants never changed the mesh). That is
**~5.2 M faces, ~2.4 h** for the 72 h waves-on premier on 64 threads. The nj2 probe replaces this
guess.

**How the runtime is estimated** (`summarise.py`):
- Flow-type work (momentum, continuity, meteo, infiltration, wave maker, boundaries) is 70 % of
  the 1.1.0 premier's log. It scales with active faces ÷ time step.
- SnapWave (28 %) and I/O (2 %) scale with faces. They run hourly, so they do not depend on the
  time step.
- The time step is estimated per face as 0.5 · dx / √(g (1 m − z_zmin)), using the lowest
  subgrid pixel of today's faces.
- A guess, not a measurement. The first nj2 run's `Average time step` checks it.

## The Cape May inlets

**Today (1.1.0 mesh, `mesh_now.txt`).** Active faces inside each inlet's rectangle, by bed depth:

| inlet | throat (60 m of the 11-09 line) | rectangle: bed −8…+1 m | rectangle: deeper than −8 m |
|---|---|---|---|
| Great Egg | 25 m (8 of 365 faces at 50 m) | all 25 m | 602 × 25 m, 989 × 50 m |
| Corson | all 25 m | all 25 m | 205 × 25 m, 330 × 50 m |
| Townsends | 25 m (2 at 50 m) | all 25 m | 467 × 25 m, 76 × 50 m |
| Hereford | 25 m (2 at 50 m) | all 25 m | 766 × 25 m, 782 × 50 m |
| Cape May Inlet | 25 m (3 at 50 m) | all 25 m | 732 × 25 m, 1,620 × 50 m |

**The band.** `capemay_inlets` uses one coast-aligned rectangle per inlet (azimuth 35°), with
named corners printed by the script. Each rectangle is centred on the inlet: ±1.3–2 km along the
coast, 0.6 km landward, 1.8–3.2 km seaward. Its gate is L3, any depth up to +3 m. Each patch
stops 400 m short of the forced sea line. The first draft reached it at Cape May Inlet / Hereford /
Great Egg and added 93 forced `ocean` cells (3,372 → 3,465), so the boundary would no longer have
been v4's.

**Expected effect on the deficit: small.** The bay crests are 0.13–0.42 m low and the quiet-window
lift is 0.2–0.35 m short.
- The breaking zone over every ebb shoal is already 40–120 cells across at 25 m.
- The faces this band adds are deeper than −8 m. Waves there are not breaking in the quiet window
  (Hs ~2–3 m breaks at ~3–4 m depth).
- So the band pins today's resolution into 2.0.0 and evens out the channels. It should not be
  expected to make set-up.
- 12.5 m would sharpen the bar / trough relief SnapWave sees, since face depth is the mean ground.
  My guess is a few cm of set-up at most, against 0.2–0.35 m missing.
- The evidence points elsewhere: READ.md mechanism 1. SnapWave has no roller and no wave–current
  interaction, and ebb currents over the shoal are what make inlet set-up in the literature.
- That is testable on the 1.1.0 mesh with a short waves-on `engine_gate.py` window. No new mesh is
  needed.

**The 12.5 m record (`refinement_nj2_inlets12.geojson`, not taken).**
- Adds ~138 k faces.
- Becomes the global time-step limiter (0.441 s, Cape May Inlet channel margins at −19.5 m). That
  is ~1.5× runtime.
- Would be the mesh's first fifth level. `build_merged_subgrid_dep.py` hard-codes `LEVELS = (3, 2,
  1, 0)` and the floodmap tools read `*_lev3.tif`, so they would silently miss the 12.5 m bed.
- A whole-rectangle `dep_subgrid_lev4.tif` at 0.78 m pixels is 239,648 × 321,312 px per bed.

## The Narrows

- Today: `narrows_cut` (L3, −40…+2 m, v3 verbatim, v4-clipped, 12.4 km²) puts 25 m faces on
  33 m of water. These are the slowest faces in the domain: 0.684 s at +1 m water, 0.665 s at
  +3 m.
- Dropped: −9,268 faces. The Narrows' deep channel goes to 50 m (dt ~1.3 s). The banks stay
  25 m wherever `bay_fringe` (−1…+2 m) reaches them.
- The next limiter is the Cape May Inlet jetty channel at 0.83 s. The one after that is ~0.86–0.90 s
  (the Barnegat / Absecon / Townsends throats).
- On v4's ring the drop moves the v4 `narrows` arm from 59 to 30 forced cells, outside its
  [45, 75] bracket. That is irrelevant to nj2, which has no Narrows arm, but it is why the v4-ring
  probe printed an invariant failure.

## Bands: definitions (straight lines between named vertices; printed in `build_provisional.txt`)

- `hudson_waterfront` (L3, −1…+5 m). The nj2 ring north end runs `hudson_route_02` → `palisades_ec`
  → `hudson_w` (40.860). The NJ/NY line is drawn mid-river: `state_hudson_860/800/750/710`,
  `state_upper_bay_695/670`, `robbins_reef`, `state_kvk_east`. The band then returns north along
  v4's retired ridge vertices `hudson_route_17` → `02`. Ellis / Liberty fall on the NJ side.
- `newark_meadowlands` (L3, −1…+5 m). It shares the ridge edge (`hudson_route_17` → `01`), then
  runs `ne_corner` (−73.96, 41.00) → `nw_corner` (−74.35, 41.00) → `sw_corner` (−74.35, 40.575).
  It closes along the Arthur Kill / Kill van Kull mid-channel: `ak_carteret` → `ak_goethals` →
  `kvk_bergen_point` → `kvk_bayonne_bridge`. NJ only; Staten Island is out.
- `capemay_inlets`: above.

## The nj2 probe: DONE (J1b 63918563, 11-14) — read `logs/nj2_freeze_2026-11-14/README.md` "Where it stands"

2.0.0 on the nj2 ring: **5,181,372 faces** (+6.14 % vs v4), min dt 0.830 s (Cape May Inlet jetty channel), ~2.37 h.
Since then `narrow_channels` also carries v4's rule on the new ground (+1,584 faces; Gowanus, the Newtown Creek
system, the Lewes canal), and the coarse bed is v4's verbatim. J1 (63918506) failed its invariants on a hole-fill
bug (`model._inactive_components`, fixed). The block below is the original plan, kept as the record.

## (record) Waiting on the domain agent: the nj2 probe

Once `nj2` is registered (with `refinement` = `data/nj2_design/refinement_nj2.geojson`) and its
coarse bed exists, run from the repo root:

```
PYTHONPATH=$PWD NJ_DOMAIN=nj2 python scripts/build_refinement_nj2.py   # re-clip on the REGISTERED ring + line
L=logs/nj2_refinement_2026-11-14
md5sum $L/probe.slurm $L/probe_variant.py data/nj2_design/refinement_nj2.geojson data/nj2_design/refinement_nj2_v4only.geojson nj_sfincs/model.py nj_sfincs/config.py nj_sfincs/domain.py data/data_catalog.yml data/region_nj2.geojson data/nj2_design/waterlevel_line_nj2.csv > $L/probe_nj2_expected.md5
env EXPECT_MD5=$L/probe_nj2_expected.md5 PROBE_DOMAIN=nj2 PROBE_SET="n0_v4only=data/nj2_design/refinement_nj2_v4only.geojson n1_final=data/nj2_design/refinement_nj2.geojson" sbatch -J nj2_probe_nj2 $L/probe.slurm
# then (light, ~1 min):
P=/scratch/tpj8/nj2_refinement_probe/nj2; python $L/summarise.py $P $P/n0_v4only/domain_dryrun.npz <mesh_now_cache.npz> data/nj2_design/refinement_nj2.geojson n0_v4only n1_final
```

(`mesh_now_cache.npz` is rebuilt by the first block of `mesh_now.py`. The nj2 control is v4's
recipe on the nj2 ring, so `hudson_waterfront`'s count is option B minus option A.) If the
domain's own `refinement` field already points at the final file, `build_static` reads the same
file. `probe_variant.py` just makes it explicit.

## Notes

- Scratch: the probes left ~0.8 GB of npz under `/scratch/tpj8/nj2_refinement_probe/`. Remove
  them after the nj2 probe (`rm -rf /scratch/tpj8/nj2_refinement_probe`).
- `probe_inputs_r3/` holds the v4-ring inputs of the final probe. The r1 / r2 inputs were deleted.
  The r1 inlet quadrilaterals were wrong: Hereford's line runs along the coast. They were
  superseded by the rectangles; their job 63918124 counts are not quoted and their probe logs + npz were deleted (that job's `p0_v4` control is kept).
- No `docs/` file was edited. Nothing was committed.
