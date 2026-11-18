# Changelog

Model versions (CLAUDE.md §6): 1.0.0 = the frozen swz premier; 1.x = fixes that keep the mesh and name a
fingerprint; 2.0 = a new mesh. The model card is [docs/MODEL.md](docs/MODEL.md).

## 2.0.0, 2012 bed — 2026-11-18

New mesh (`nj2`, frozen 2026-11-15) + the J3 leak walls: domain `nj2w_bed2012` / `0f87265091209585` (`faces=5181372
boundary_edges=4367`). Arm `p4-premier+struct-cohansey-checkvalve+weir-dikes-levees`, job 64003605 (hal0432,
uninterrupted, 2 h 23 solve); rain-off twin `p4-premier+rain-off+struct-cohansey-checkvalve+weir-dikes-levees`, job
64003606. Engine = `hpc/production_engine.txt` (as 1.1.0). The 2026-bed option (`nj2w_bed2026`) is registered
separately and not yet run. Design + freeze: `logs/nj2_freeze_2026-11-14/README.md`; run prep:
`logs/nj2_waveson_prep_2026-11-16/README.md`.

**Domain:** the Upper Bay, Kill van Kull, the Hudson to 40.860 N and the East River to Hell Gate COMPUTED; two short
forced cuts (Hudson, Hell Gate) replace the Narrows / KvK arms; NACCS at 244 support points (`naccs_sandy_nj2`); NY
narrow channels at 25 m; SnapWave off over the Upper Bay / Hudson / East River. J3 walls: Astoria Park (5 faces) and
Millville-east (6 faces) outflow → closed (leaks only at +2 / +3 m SLR).

**Bed (`_subgrid_nj2_2012`):** v1.1c's tiers + `ehydro_hud_2012_v2` (Hudson, PAINT) + the v1.2a five + Brooklyn creek
(Newtown, Gowanus; upper Gowanus = GCK 2020 section, ASSUMED) and pile-pier carves (29 units). NJ buildings only.

**Structures:** 1.1.0's weirs + the Delaware-bayshore dikes-and-levees set (26 polylines; Chester redrawn off the
creek, Port Penn r1054 gate open) + the Cohansey Bacons Neck tide gate as a check valve (`sfincs.drn`). Engine weir
u/v 3578 on this bed. Waves-off paired (J3, +0): HWM ΔRMSE −0.0003 m [−0.0007, +0.0001], CSI 0.787 → 0.785.
Wavemaker redrawn on the 2012 bed (7934 engine u/v; ~200 links move vs 1.1.0's line).

**Scores (median, 50 m; native 3.125 m floodmap; 2.0 mark file `data/validation_nj2/sandy_hwms_nj2.geojson`):** HWM
RMSE 0.322 / bias −0.032 m (n 163; ±0.5 m 94 %). Paired vs 1.1.0 on the 1.x mark file (n 119): ΔRMSE −0.002
[−0.007, +0.005] (2.0 0.346 / −0.052 vs 1.1.0 0.348 / −0.067); rain-off twins −0.007 [−0.012, −0.003]. MOTF CSI
0.795 (POD 0.859, FAR 0.085; excluded boxes 2,534 km²) vs 1.1.0's 0.803 (11-15 boxes); rain-off twin 0.811 (POD
0.834, FAR 0.033) vs 0.822 (11-15 boxes). Like for like (common footprint 4,837 km²): CSI 0.797 vs 0.803 rain-on,
0.813 vs 0.822 rain-off; FAR flat, the loss is POD: net +9.7 km² new misses rain-on, ~60 % Hackensack Meadowlands +
Newark Bay (bed and structures unchanged there; peak −0.15 m in the Meadowlands; likely the computed harbour vs
1.1.0's forced Narrows / KvK, untested), ~16 % within 1 km of the new dikes (`logs/csi_dip_2026-11-18/README.md`).

## 1.1.0 — 2026-11-09

Same mesh as 1.0.0; new fingerprint `v4_refreeze_swz_v11` / `4bc97aae885f0aa4`. Arm
`p4-premier+weir-elizabeth-rahway`, job 63617802 (32 threads, uninterrupted), engine
`bin:v2.3.3-winddir-igk-igseed-wmseed-swomp-2-gf11@dd78d82a` (= `hpc/production_engine.txt`).

**Bed (flow, `_subgrid_v1_1c`; the wave bed follows it):**
- River beds v4c → **v4e**: lower Mullica + Tuckahoe, Toms, Cedar Creek, Westecunk, Raccoon, Mantua from charts /
  surveys; the Christina plug removed.
- **Bridge decks removed from the bed** (`deck_fix_v4b`), plus **8 verified + 18 federal-channel NBI crossings**
  opened (`nbi_open_v4`).
- **eHydro channel fill** (`ehydro_fill_v4`, 9 survey tiles, lower-only).
- **Alloway and Silver Lakes** held at their pools (they were CUDEM ~0 m fills tied to the tide).
- **Manning:** developed land 0.04 in NJ (the double count with burned buildings removed); surveyed channels 0.02.
- Little Egg channel overlay kept.

**Structures:** Overpeck tidal dam weir removed (open). Elizabeth River South (Right + Left Bank) and Rahway South
Branch levees added at the NLD crest, with the Bayway wall, 3 tie-ins and 11 ground guards (819 engine u/v points).
The levee arm and the Overpeck-only arm tie on the marks; the levees were chosen as mapped flood-control structures
(user 2026-11-09). No observation lies inside the leveed areas, so the Bayway substation staying dry is untested.

**Validation inputs:** the 1.x mark file (+13 Newark Bay / Hackensack / Overpeck marks, 206); the Christina
USGS gauges re-datumed NGVD29 → NAVD88. Scores before 2026-11-05 carry the old gauge numbers: re-baseline.

**Scores (median estimator, 50 m; native 3.125 m floodmap, re-scored 2026-11-12/13, job 63894123):** HWM 1.x file
RMSE 0.348 / bias −0.067 m (n 119); paired vs 1.0.0 ΔRMSE −0.072 [−0.166, −0.007] (1.x file, n 119), −0.075
[−0.174, −0.007] (v4 file, n 110); MOTF CSI 0.802 (POD 0.868, FAR 0.086; excluded boxes 2,412.7 km²); rain-off twin
CSI 0.821 (POD 0.845, FAR 0.034). As first published on the 6.25 m overview floodmap: HWM 0.355 / −0.072; ΔRMSE −0.069
[−0.158, −0.007] / −0.072 [−0.165, −0.006]; CSI 0.795 (POD 0.859). Upper Delaware gauges read 0.05–0.07 m lower than
1.0.0. 40 "fair" gauge peaks (MODEL.md §6): RMSE 0.226 m, bias −0.103 m, 85 % within ±0.25 m.

**Not a version change, 2026-11-12:** every floodmap had been downscaled on the bed's first overview (6.25 m), not its
native 3.125 m (`logs/floodmap_fix_2026-11-12/README.md`). The model is unchanged; HWM and MOTF scores of both
versions moved, gauge scores did not.

## 1.0.0 — 2026-11-01

`p4-premier` on `v4_refreeze_swz` / `90cc7468614a5814`, job 63181564. HWM RMSE 0.435 / bias −0.125 m (median, 50 m,
n 110, native 3.125 m floodmap); MOTF CSI 0.791 (as published on the 6.25 m overview: 0.439 / −0.128, CSI 0.784). See the `v1.0.0` tag's `docs/MODEL.md`.
