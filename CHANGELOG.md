# Changelog

Model versions (CLAUDE.md §6): 1.0.0 = the frozen swz premier; 1.x = fixes that keep the mesh and name a
fingerprint; 2.0 = a new mesh. The model card is [docs/MODEL.md](docs/MODEL.md).

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

**Scores (median estimator, 50 m):** HWM 1.x file RMSE 0.355 / bias −0.072 m (n 119); paired vs 1.0.0 ΔRMSE −0.069
[−0.158, −0.007] (1.x file, n 119), −0.072 [−0.165, −0.006] (v4 file, n 110); MOTF CSI 0.795 (POD 0.859, FAR 0.086;
excluded boxes 2,412.8 km²). Upper Delaware gauges read 0.05–0.07 m lower than 1.0.0.

## 1.0.0 — 2026-11-01

`p4-premier` on `v4_refreeze_swz` / `90cc7468614a5814`, job 63181564. HWM RMSE 0.439 / bias −0.128 m (median, 50 m,
n 110); MOTF CSI 0.784. See the `v1.0.0` tag's `docs/MODEL.md`.
