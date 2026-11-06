# Bed audit check: `impoundment` (2026-11-05)

**Question.** Does the bed treat **impounded (non-tidal) water as tidal**, or **tidal water as cut off**?
The case that motivated it: Alloway Lake and Silver Lake (deck short list E3 / E4), lakes behind dams whose beds
were CUDEM's flat ~0 m fill, so the model tied them to the tide below their pools (Alloway at −0.36 m under a
1.61 m pool). Format, beds and calibration: [../../SCHEMA.md](../../SCHEMA.md).

## Sources (all public, US federal or state; cite as below)

| layer | what it gives | where |
|---|---|---|
| **NWI**, USFWS National Wetlands Inventory (Wetlands MapServer layer 0, queried 2026-11-05) | the Cowardin code per polygon: system (L lacustrine, P palustrine, E estuarine, R riverine), class, **water regime** (tidal: L M N P salt, R S T V fresh; non-tidal: A–K …) and the **special modifier `h` = diked / impounded** | `fetch.py` → `/scratch/tpj8/nj_bight_sfincs_data/audit/impoundment/nwi_*.geojson` (lakes `L%`, ponds `PUB%` / `PAB%` / `PUS%`, tidal water `E1UB%` / `E1AB%` / `R1%`) |
| **NID**, USACE National Inventory of Dams (the 10-05 §54 pull, 796 dams in the v4 box) | dam id, name, height, type, purpose | `nid_dams.geojson` |
| **Lake pool** | the lidar water surface, p50 of ~120 interior points: the NJ 10 ft DEM (NJDEP, hydro-flattened), else USGS 3DEP 1/3″ | `logs/decks_2026-11-04/common.py` `TIERS` |
| **MHHW** | NOAA VDatum MHHW in NAVD88 (the domain's 25 m surface, `data/normal_surface_v4/`), nearest finite cell for inland lakes | `nj_sfincs/normal_surface.py` |

## The rule

**LINK** = the lowest still-water level at which the bed joins a polygon to ocean-connected tidal water: a minimax
over the bed (4-connected, the native 3.125 m pixels, in a window around the polygon), by bisection to 0.02 m.
**Tidal seed water** = cells with bed ≤ −0.5 m in a component of {4×4-block-min bed ≤ −0.5 m} of ≥ 20 km² (the
ocean, the bays, the tidal rivers).

| set | which polygons | flag | severity |
|---|---|---|---|
| **A impounded** | NWI lacustrine (all), and palustrine open water ≥ 1 ha or with `h` or within 300 m of an NID dam; non-tidal regime; ≥ 0.2 ha; POOL > MHHW + 0.15 m | `impounded_lake_tidal_link`: LINK < POOL − 0.30 m | high if LINK < MHHW (the tide gets in every day), else medium |
| | | `flat_fill_below_pool`: bed p50 < POOL − 1.0 m and bed IQR < 0.2 m (a flat fill, not bathymetry) | medium with a tidal link, else low |
| **B tidal** | NWI `E1UB` / `E1AB` / `R1*` with a tidal regime, ≥ 0.5 ha | `tidal_water_cut_off`: LINK > MHHW + 0.10 m | high if > MHHW + 0.3 m and ≥ 1 ha, else medium |

**Why these thresholds.**
- **Seed at −0.5 m, ≥ 20 km².** −0.5 m NAVD88 is below mean tide on this coast (MLW −0.6 to −0.9 m), so a seed is
  water at every stage of the tide. CUDEM's fake fills sit at ~0 m, so they can never seed. 20 km² keeps the ocean,
  the bays and the tidal rivers, and drops deep inland pits and quarry lakes (all < 3 km² here).
- **0.30 m under the pool.** The lidar water surface varies ±0.1 m, pools ride ±0.1–0.2 m with season and flow, and
  a spillway notch or flashboard sits a little under the normal pool. A link more than 0.3 m under the pool is a path
  the real control (dam crest, spillway) does not have.
- **Pool > MHHW + 0.15 m.** A "pool" at tide level is a tidal or tide-gated lagoon; its link cannot be called wrong
  from the bed alone.
- **Flat fill.** A real lake bottom slopes; a flat surface (IQR < 0.2 m) a metre under the pool is a fill (§54).
- **B, MHHW + 0.1 / 0.3 m.** NWI tidal water is wet at high tide by definition; a bed that joins it to the sea only
  above MHHW has a ridge, plug or fill on the way (the Christina plug class).

## What the check cannot see (read every exception with these in mind)

- **The window.** A path that leaves the window (box + 1.5 km; 3.5 km when no seed is inside) and comes back is not
  seen, so LINK reads HIGH: set A can miss a leak but cannot invent one; set B can invent a cut-off, so every B
  exception is re-tested with the 3.5 km window before it is written.
- **Structures are not in the bed.** A pool held by a weir (`sfincs.weir`: Keansburg, Overpeck) or a tide gate reads
  only its bed path. The check reports the bed, not the model with its weirs.
- **Seeds come from the base bed** (no overlays), at 12.5 m blocks: a wall thinner than ~12 m can let a seed
  component through. Windows apply the overlays at native resolution.
- **NWI vintage.** The polygons are NWI's current mapping (mostly 2000s–2010s imagery in NJ). A pond dug or filled
  since then is wrong in NWI, not in the bed.
- **No eye.** It cannot say whether a culvert or tide gate really joins a pond to a creek. It flags the pond; the
  reviewer says which.

## Run

```
python -I fetch.py                                   # once (cached)
python check.py --bed experiments/v4_refreeze_swz/_subgrid_v1_1b --label v1_1b --out ../../out/v1_1b/impoundment.csv
python check.py --bed experiments/v4_refreeze_swz/_subgrid_modern2026 --label modern --overlay-min-v11npz \
                --out ../../out/modern/impoundment.csv
```

## Results

### Set A — impounded water tied to the tide (final, 2026-11-05)

1,601 impounded NWI water bodies in the ring and simulated by 1.0.0 (481 more sit at tide level, ~230–410 have no
tidal water within 3.5 km and cannot be tied to it). Exceptions, by bed:

| bed | tidal link HIGH (< MHHW) | tidal link MEDIUM (MHHW … 4 m) | tidal link LOW (≥ 4 m) | flat fill (med / low) |
|---|---|---|---|---|
| `p100` (Model 1.0.0) | 7 | 21 | 25 | 8 / 27 |
| `v1_1b` (stand-in) | 5 | 24 | 26 | 8 / 27 |
| `modern` (2026 lidar) | 1 | 10 | 17 | 0 / 3 |

**High, v1.1b bed** (the tide reaches these pools every day through the bed):
1. **Noxontown Pond**, Middletown DE (NID DE00050, 66 ha): link 0.62 m under a 1.30 m pool — the E4 case.
2. **Christiana Lake**, DE (DE00048, 7 ha): link 0.01 m under 1.33 m; flat CUDEM fill (bed 0.00).
3. PABHh pond 3.2 ha at −74.394, 39.591 (Barnegat Bay mainland): link 0.48 under 1.10 (MHHW 0.54).
4. PUBHh pond 0.8 ha at −75.606, 39.494 (DE): link −0.05 under 1.26.
5. L2EM2Fh fringe of Noxontown at −75.695, 39.412: same path as 1.

**Alloway Lake** is HIGH on 1.0.0's bed (0.41 m under 1.61) and passes on v1.1b: `alloway_pool_v4` works.

**Modern bed:** the 2026 lidar fixes Noxontown, Christiana and the others (its lakes carry their own surfaces) but
makes **Bayway Refinery No. 2 Dam's lake** (NJ01046, 34 ha) HIGH: link 0.34 m under a 1.32 m pool, against 0.99 m on
v1.1b — next to the Bayway 345 kV substation and the Elizabeth / Rahway levee work.

**Medium worth a look first** (link under Sandy's reach, big pools): Silver / Haven / Griffith Lakes, Milford DE
(50 ha, link 2.13 vs 4.10 m pool; 1.76 on the modern bed); Shallcross Lake DE (17 ha, 2.02 vs 2.44); Silver Lake PA
(Tullytown, 7.6 ha, 3.88 vs 4.74); a 5.4 ha pond SE of Alloway (pool 3.96 m) that `alloway_pool_v4` painted at the
lake's 1.61 m.

**Flat fills (fake storage, no tidal tie):** 35 pools on the 2012 beds hold a flat bed a metre or more under their
lidar surface — the §54 class the inland-water overlay was built for, missed where NWI maps a pool §54 did not list
(e.g. Silver Lake Middletown, 16 ha, bed 0.00 under 2.55 m).

### Set B — tidal water cut off from the sea (final rule, run 15:27–15:53)

1,807 NWI tidal-water polygons (E1UB / E1AB / R1, not diked `h`, ≥ 0.5 ha, simulated). Flag = joined to the sea only
above MHHW + 0.5 m (8 km re-test for anything unjoined).

| bed | HIGH (> MHHW + 1 m, ≥ 1 ha) | MEDIUM | of which never joined below MHHW + 1.5 m | area |
|---|---|---|---|---|
| `p100` | 118 | 252 | 219 | 870 ha |
| `v1_1b` | 116 | 244 | 218 | 705 ha |
| `modern` | 115 | 202 | 212 | 581 ha |

**Read this set as a SCREEN, not a fix list.** Calibration is thin (only the St Jones, now passing, and four
15-km-stable cut-offs were tested by hand), and two things inflate it: (1) NWI maps many managed impoundments
as tidal water WITHOUT the `h` modifier (the Delaware Bay refuge pools: Prime Hook −75.216, 38.821, 38 ha, link 1.75 m
vs MHHW 0.69, is one), and (2) excavated (`x`) lagoons and borrow pits behind fill. Largest high on v1.1b that look like
real bed plugs worth an eye: R1UBV 28 ha at −75.287, 38.783 (Broadkill River reach, link 1.81 m vs MHHW 0.67);
E1UBL 10 ha at −75.096, 39.234 (NJ bayshore, never joins below 2.4 m); E1UBL6 10 ha at −74.873, 39.002 (Cape May,
never joins); E1UBLx 17 ha at −74.170, 40.680 (Newark Bay shore, never joins); E1UBL 8 ha at −75.581, 39.711
(Christina / Wilmington marsh, never joins). The modern bed has ~40 fewer cut-offs (its lidar opens marsh creeks
CUDEM filled) and 27 of its own.

## What the check does and does not catch (summary)

- ✅ **Catches:** an impounded lake tied to the tide through a fake fill (Alloway, Noxontown = E4, Christiana), a
  lake sitting as a flat fake pit (Silver Lake Middletown + 34 more), and passes the §54 painted pools and the fixed
  Alloway. ✅ Drops un-simulated water (Union Lake).
- ⚠️ **Misses by design:** pools held by structures that are not in the bed (weirs, tide gates) — it audits the bed.
- ⚠️ **Over-flags:** set B, wherever NWI calls a diked pool "tidal" without the `h` modifier.

## State at handoff (2026-11-05 ~15:00; VS Code node 63568301 ends ~16:05) — COMPLETED 15:55, all runs final

**Link definition settled.** LINK = the lowest still-water level at which tidal seed water reaches a REAL SHARE of
the polygon: ≥ max(20 px, 2 % of the polygon's pixels), counting pixel CENTRES inside the polygon shrunk 5 m
(native 3.125 m bed, 4-connected, bisection 0.02 m). Seeds = bed ≤ −0.5 m inside the one ocean-connected
coarse (4×4 block-min) component ≥ 20 km² (it is a single 17,250–17,360 km² component on all three beds). For set A,
seed cells inside the polygon or within 30 m of it are DROPPED (a coarse block can merge a deep lake with the tidal
river through its dam: Duhernal / Bayway read a fake −0.50 m before this). Candidates must be in the v4 ring AND
contain (or lie within 30 m of) an active face of 1.0.0's `sfincs_map.nc` (finite zsmax) — this drops Union Lake and
other un-simulated water. Sandy peak = max zsmax of the active faces inside the polygon, else the nearest within
200 m. Replace overlays are applied with NEAREST resampling (max resampling had lowered banks by up to 12.6 m).

**Calibration (set A, `calibration/cal_{p100,v11b}.csv`, `cal.sh`):**

| case | 1.0.0 bed (`p100`) | v1.1b stand-in |
|---|---|---|
| Alloway Lake (NJ00038) | ✅ caught: HIGH, link 0.41 m vs pool 1.61 (MHHW 0.96) | ✅ passes (alloway_pool_v4) |
| Noxontown Pond (DE00050) = the E4 "2012 bed tied at 0.59" case | ✅ caught: HIGH, link 0.62 vs pool 1.30 | ✅ caught (unchanged) |
| Silver Lake, Middletown (DE00051, 16 ha) | flat fake pit (bed 0.00 under a 2.55 m pool), no tidal link | same |
| Manor Lake, McColley Pond (§54 painted pools) | ✅ pass | ✅ pass |
| Duhernal Lake (false −0.50 before the seed fix) | ✅ pass | ✅ pass |
| Union Lake | dropped (not simulated: Maurice cut on the dam crest) | dropped |

New, not yet eye-checked: Christiana Lake DE00048 (PUBHh 7 ha) HIGH link 0.01 vs pool 1.33; Bayway Refinery No. 2
Dam lake (NJ01046) medium 0.99 vs 1.32 (MHHW 0.78); Island Farm Weir pool (Raritan, L1UBK) medium 4.82 vs 9.35
(the weir crest is not in the bed: riverbeds_v4's sloped Raritan carve runs through it); a 5.4 ha pond SE of
Alloway (PUBHh, lidar pool 3.96 m) painted at 1.61 by alloway_pool_v4.

**Full-run outputs that exist** (`out/<bed>/impoundment.csv`, logs `impoundment_AB.log`), from the run BEFORE the set-B
change below — set A rows are final, set B rows are NOT:

| bed | set A: impounded tidal link (high / medium) · flat fill | set B rows (superseded) |
|---|---|---|
| `p100` (1.0.0) | see CSV (7 high) · 27 low | 630 at MHHW + 0.1 |
| `v1_1b` stand-in (`_subgrid_v1_1` + `--overlay alloway_pool_v4 --overlay-min deck_fix_v4b`; the real `_subgrid_v1_1b` was never built — job 63577223 was replaced by `v1_1c_bed`) | 5 high · 27 low | 610 |
| `modern` (`_subgrid_modern2026` + v1.1 deck npz) | 1 high · 3 low | 515 |

**Set B change made after those runs (in `check.py`, not yet re-run):** NWI tidal water with the `h` (diked)
modifier is excluded (refuge pools are cut off by design); the flag threshold is MHHW + 0.5 m (`B_MARGIN`; at
+0.1 m it flagged ~630 marsh-platform ponds that only spring tides reach); high = > MHHW + 1.0 m and ≥ 1 ha.

**Window re-test DONE (`calibration/pad_test.py`, 1.0.0 bed):** the St Jones (R1UBV, 70 ha) was a window artifact —
unjoined at 3.5 km, joined at −0.16 m with 8 and 15 km; four others are stable to 15 km (real cut-offs or NWI tidal
water that is diked): Cape May E1UBL6 10 ha at −74.873, 39.002 (link 2.31 m, MHHW 0.70); Delaware Bay shore E1UBL
10 ha at −75.096, 39.234 (unjoined below 3.0); E1UBL 2.9 ha at −74.100, 40.021 (unjoined); E1UBLx 145 ha at −74.420,
39.454 (link 1.81 m, MHHW 0.55). `check.py` now re-tests an unjoined set-B polygon at 8 km. **Set B: the ~15:15 re-run
applied h-exclusion + MHHW + 0.5 but NOT the 8 km step (that edit had not saved), so its outputs (358 / 320 / 367
cut-offs on v1_1b / modern / p100) still carry window artifacts like the St Jones. Re-run with the 8 km step STARTED
15:27 (check.py md5 d941b4def021…): `cd logs/bed_audit_2026-11-05/checks/impoundment && SETS=B srun -p main
--exclude=halk[0001-0159] -c 4 --mem=120G -t 2:00:00 ./run_all.sh`. If `out/*/impoundment_B.log` does not end in
`[done]` with a later time than 15:27, re-run exactly that.**

**Set A severity also changed (applied to the existing CSVs by `reclassify.py`, same rule now in `check.py`):** a link
at or above `SURGE_CAP` = 4.0 m NAVD88 (about the highest Sandy water level in the domain) is LOW, not medium — no
surge here would use that bed path (Robinson's Branch Reservoir links at 12.3 m).

**Was outstanding (kept for the record):** (1) the window re-test of 'never joined' tidal polygons (223 on p100; is it a window artifact or
real plugs, e.g. the St Jones R1UBV 70 ha at −75.513, 39.147):
```
cd logs/bed_audit_2026-11-05/checks/impoundment
srun -p main --exclude=halk[0001-0159] -c 1 --mem=60G -t 0:45:00 python calibration/pad_test.py \
  /cache/home/tpj8/nj_bight_sfincs/experiments/v4_refreeze_swz/_subgrid_refreeze_lakes_min_creeks_cohansey \
  -75.512969,39.146773 -74.873324,39.002036 -75.095589,39.234267 -74.100424,40.020907 -74.420082,39.454083
```
If larger pads (8 / 15 km) join them, raise the set-B re-test pad in `check.py` (the `3500.0` in set B) to 8000.
(2) Then re-run set B only, merging into the existing CSVs: `SETS=B srun -p main --exclude=halk[0001-0159] -c 4
--mem=80G -t 3:00:00 ./run_all.sh`. (3) Fill the Results section.
