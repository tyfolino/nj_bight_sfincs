# levee_continuity (2026-11-06)

**Question:** does each National Levee Database (NLD) levee / floodwall system keep water out of its leveed area in
the MODEL (the bed's flow tables + the run's weir file) as well as the real ground + the levee would?

The hand passes it automates: `logs/walls_elizabeth_rahway_2026-11-05/` (2012 bed) and
`logs/walls_elizabeth_rahway_modern_2026-11-06/` (2026 bed). The finding behind it is walls_inventory_2026-11-04 #1:
the bed never carries a levee crest (a 5 m embankment inside a 25–50 m cell is pooled with the ground beside it), so
a levee works in the model only through `sfincs.weir`.

## Sources

- NLD public FeatureServer, pulled 2026-11-04 (`logs/walls_inventory_2026-11-04/fetch_nld.sh` →
  `walls_inventory.gpkg`): routes (81 in the ring), floodwalls, closures, leveed areas. Z is US survey ft NAVD88
  (× 1200/3937). A vertex with Z ≤ 0.5 ft is unknown. Along a route, unknown vertices take the crest interpolated from
  the known ones, so the system is "as designed, gates CLOSED" (the 11-05 G-1 (a) default). A part with no known Z is
  not burned.
- 1.0.0's Sandy level along each line: `nld_ranked.csv` `sandy_level_med` (11-04; a model level in a run WITHOUT these
  structures).
- Power assets: `logs/power_exposure_2026-11-02/` (inside the leveed area, else within 2 km of the door).

## Rule

Two door levels per leveed area (polygon shrunk 20 m, as the hand passes):

- **Mesh door.** The still-water level at which the leveed area joins the open boundary (`mask == 2`) on the flow
  mesh. A link passes above `uv_zmin`, or above the weir crest where the engine KEEPS a weir on it
  (`weir_on_mesh.snap`, which reproduces the solver's logged counts to +1). It is computed for every face at once as a
  minimax path (the maximum edge on the minimum-spanning-tree path from a super-source tied to every boundary face).
  The link that sets it is tracked, and that is the `lon` / `lat` to look at. A whole bed + weir file takes about
  4 s.
- **Pixel door ("ground + levee").** The same on the bed's own 3.12 m pixel raster (the rotated
  `dep_subgrid_merged.tif`, read through the affine, no boundless read). The NLD routes, floodwalls and closures are
  burned in at their NLD Z. It is a 4-connected priority flood from seeds: pixels ≤ −0.5 m whose nearest face reaches
  the boundary below 0.0 m on the bed alone (tidal water). The window is the leveed area + 2 km.
- **The door is the 2 % level:** the level at which 2 % of the leveed area (face-area weighted on the mesh, pixel
  count on the raster) has joined open water. The very first water (`first_door_m`, reported) is often a stray
  creek or toe face that the NLD polygon takes in. Keansburg's leveed area includes the creek mouth seaward of its
  gate (first pixel door −1.62 m), and with its weir in, only 7 of its 5,345 faces sit low.
- **Flag** when the mesh door < min(pixel door, Sandy) − 0.20 m. The 0.20 m is the 2012 / 2026 hand passes'
  mesh-vs-lidar match (0.15–0.16 m).
  - **`levee_not_in_flow`:** the model carries the NLD crest (≥ min(crest, Sandy) − 0.20) on < 50 % of the route's
    crossed links. The levee is simply not a weir.
  - **`door_below_ground`:** the levee is in, but a gap, flank or tie leaves a lower door.
- **Severity:**
  - **low:** Sandy did not reach the mesh door.
  - **high:** a power asset is inside or within 1.5 km.
  - **medium:** the ground + levee would have HELD Sandy (Sandy < pixel door) and the model lets it in.
  - **low:** Sandy overtopped the real line too, so only timing and depth are at stake.
- **`weir_low_spot` (low)** is for an area that HOLDS in the model. It gives the lowest weir vertex on any weir line
  within 300 m: the place to eye-check that a ground line is right (a ditch or culvert under it?).
- **`undecidable_no_active_face_inside`:** no active face centre lies inside the shrunk area.

**Not seen:**
- duration, overtopping volume, rain, pipes and pumps (all static);
- water that routes round the 2 km pixel window;
- gates left open;
- bulkheads.
  - NJ: the 11-04 inventory found no public layer with crest heights (Atlantic City builds block by block, with no
    GIS).
  - NY (2.0 adds the Hudson / Upper Bay waterfront): not searched yet. Finding a bulkhead-height source is a 2.0
    task. Until then 2.0's bank cut skips NLD and bulkhead lines by design (STATUS 11-05).

`--overlay-min` / `--overlay` are accepted from the runner and ignored: the check reads the subgrid TABLES, which a
pixel overlay does not change.

## Weir file per label (`--weir`)

| label | default weir | why |
|---|---|---|
| `v1_1c` | `data/structures_v4/sfincs_overpeck_open.weir` | v1.1's `p4-premier` (Overpeck open, no levees) |
| anything else (`modern`, `p100`) | `data/structures_v4/sfincs.weir` | the template's file (Keansburg + Overpeck dam) |

`--extra-weir NAME=PATH` writes `calibration/<label>__<NAME>.csv` from the same mesh load and pixel pass (`none` =
bed only). Per-system tables (both doors, Sandy, share carried, area share below) are in
`summary/<label>__<name>_systems.csv`. Pixel doors are cached per bed in `cache/`.

## Calibration

Door = the 2 % level, m NAVD88 (first water in brackets). The hand passes' numbers are first doors.

| case | bed + weir file | mesh door | pixel door | verdict | hand pass |
|---|---|---|---|---|---|
| C1 Elizabeth RB / LB / Rahway, no levee weirs | v1_1c + template (`sfincs.weir`) | 0.87 (0.73) / 0.93 (0.49) / 1.68 (1.38) | 3.01 / 2.97 / 3.35 | **fires, high** ×3 (`levee_not_in_flow`; Bayway inside RB) | flow passes (11-04); mesh base RW 1.38 |
| C1′ the same with the 11-05 levee file | v1_1c + `…overpeck_open_elizabeth_rahway_ground.weir` | 3.14 / 2.82 / 3.37 | 3.01 / 2.97 / 3.35 | **quiet** | 3.14 / 2.82 / 3.38 (mesh), lidar 3.07 / 2.97 / 3.37 |
| C2 Right Bank, 2012-bed levee file on the 2026 bed | modern + the 11-05 file | **2.75** | 3.12 | **fires** (`door_below_ground`; 6 % of the area below 2.92) | 2.76 |
| C3 Right Bank, 2026-bed levee file | modern + `…modern_elizabeth_rahway_ground.weir` | 3.20 | 3.12 | **quiet**; `weir_low_spot` 0.08 m on `elizabeth_rb_south_bayway_gap_lidar_sill` at (−74.20011, 40.64252) = the Bayway toe ditch, within 1 m of the hand pass's point | 3.21; ditch 0.08 m at (567634, 4499382) |
| C4 Keansburg with its weir | v1_1c / modern + template | 3.28 (1.89) / 3.28 (2.67) | 0.77 / 0.49 | **quiet** (0 % of the area below the expected door) | weir watertight since 10-23 (FINDINGS §38) |
| C4′ Keansburg, weir lines removed | v1_1c / modern + `calibration/sfincs_no_keansburg.weir` | −0.09 / −0.47 | 0.77 / 0.49 | **fires, high** | the pocket filled before the weir |

- **Keansburg's pixel door is low (0.49–0.77 m) even with the NLD lines burned in at crest.** The published NLD line
  does not close the system: the inventory found its Pews Creek gap, and the 1.0.0 weir file carries a hand-made
  `pews_levee_gapclosed`. The 2 % level is that gap, not a flaw in the method. It also means "expected" = the NLD as
  published, so a hand-closed weir can only read higher than expected, never lower.
- **Edge case:** New Castle – Gambacorta (modern) sits 0.22 m under a pixel door of −0.25 m, a breached dike open to
  the tide. It is high only because an unnamed substation (`s1646`) lies 0.8 km away.

## Results (`out/<bed>/levee_continuity.csv`, 11-06)

| bed (weir) | rows | high | medium | low | kinds |
|---|---|---|---|---|---|
| v1_1c (`sfincs_overpeck_open.weir`) | 68 | 8 | 5 | 55 | 61 `levee_not_in_flow`, 2 `door_below_ground`, 5 undecidable |
| modern (`sfincs.weir`) | 63 | 9 | 5 | 49 | 55 / 3 / 5 |

**High on both beds** (a power asset inside or ≤ 1.5 km; none is a weir today):
- Elizabeth River RB and LB South (Bayway Substation);
- Rahway South Branch RB (Union County Resource Recovery);
- Rohm & Haas (China Substation);
- Pennsauken Creek and Pennsauken Creek 3 (Pennsauken Solar);
- Henby Creek (Chambers Co Generation Substation, inside);
- Chester (Chester Operations);
- modern only: New Castle – Gambacorta.

These are the 11-04 inventory's ranked list, now found by a rule.

**Medium** (the ground + levee would have held Sandy; the model lets it in):
- Mill Creek (Union Bank), Loatman Road, Browns Run, Tinicum Long Hook Creek 2 and 3, Tinicum Delaware River 1,
  Washington Point Neck.
- Most of these are small Delaware dikes that the 11-04 inventory kept as "note only".

## Run

```
python -I check.py --bed experiments/v4_refreeze_swz/_subgrid_v1_1c --label v1_1c --out out/v1_1c/levee_continuity.csv
```

Through the runner: `scripts/bed_audit.py --bed … --label … --checks levee_continuity`. Job 63614867
(`../../run_levee_enc.slurm`, log `../../run_levee_enc_63614867.out`) ran both beds and every calibration file. The
final outputs were re-run afterwards on allocation 63614117 (`calibration/rerun_*.log`), after one fix: a power asset
with no name had been read as NaN. Doors and severities are unchanged; only `near_asset` text changed.
