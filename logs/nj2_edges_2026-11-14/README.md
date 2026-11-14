# nj2 (Model 2.0.0): the model's edges and the hand-placed inputs, prepared before the freeze (2026-11-14)

**In plain words.** Model 2.0 opens the Upper Bay, the lower Hudson and the East River below Hell Gate. Its edges change
in only two places: the forced water level at the Narrows and the Kill van Kull goes away (both are inside the model
now), and two short new forced cuts appear, on the Hudson about 1 km above the George Washington Bridge and on the East
River at Hell Gate. Everything south of the Narrows is v4's edge, unchanged. NACCS has wet save points right on both new
cuts, so the boundary file can be built the night the mesh freezes, with one command that touches nothing of v4's. The
Battery is now INSIDE the model: for the first time it can test the model, not drive it. None of the hand-placed files
(levees, the Overpeck start, the wavemaker) lies in the new area, so they carry over; the ones tied to face order or
to the mesh's links (the Overpeck start file, the levee u/v counts) must be regenerated or re-counted on the frozen mesh.
SnapWave stays OFF over the whole new area (user 11-14), with no new code: v4's wave footprint already stops at the old
Narrows line. Separately (user scope addition 11-14), the Delaware-bayshore dikes-and-levees set is fixed and staged as
its own 2.0 arm file: the Chester levee no longer dams Chester Creek, the two leaks are closed by hand, and the door
check now flags any line that traps a river inflow.

Nothing in `nj_sfincs/`, `scripts/`, `hpc/`, `docs/`, `data/structures_v4/`, `data/NACCS/` or
`logs/weirs_dikes_levees_2026-11-12/` was edited. Nothing was submitted. Compute: this VS Code allocation (hal0404), < 3 GB.

## 1. The forced line (`data/nj2_design/`)

| arm | kind | nj2 | source |
|---|---|---|---|
| `delaware_mouth`, `ocean`, `lower_bay_entrance`, `rockaway_inlet` | sections of the drawn sea line | **kept, unchanged** | `waterlevel_line_nj2.csv` = v4's 122 vertices byte for byte under an nj2 header; sea closure = v4_refreeze's (+ the two Lewes vertices) |
| `cd_canal` | box arm | **kept** | v4's box |
| `narrows` | box arm | **DROPPED**: the Narrows is interior | — |
| `kvk_east` | box arm | **DROPPED**: the Kill van Kull is interior (`wall_bayonne` goes with it) | — |
| `hudson` | NEW, corridor arm | `hudson_w` (−73.95753, 40.8600) → `hudson_e` (−73.9345, 40.8600), 1.94 km (1.73 km of water, ~330 m low bank at the W end) | `cut_hudson_nj2.csv` |
| `hell_gate` | NEW, corridor arm | `hellgate_w` (−73.9425, 40.7765) → `hellgate_e` (−73.9345, 40.7775), 0.68 km | `cut_hell_gate_nj2.csv` |

The cut vertices are the `forced` vertices of `logs/v2_prep_2026-11-04/ring_recommended_v2edit.csv` and equal the
registered `data/nj2_design/region_nj2_vertices.csv` to the digit. **Why two separate files:** `Domain.waterlevel_line`
is ONE path that also closes the sea polygon, so the cuts cannot be appended to it. Build each with the existing
`waterlevel_line_arms(<cut csv>, 32618, ((name, first_vertex, why),), corridor_m=...)`: a two-vertex section with
FLAT ends, so the Hell Gate east wall (hellgate_e → astoria) and the Palisades leg are nobody's. Counts: unbracketed
(1..10,000) until the first mesh probe, as v4 did (rough expectation at 50 m water faces: ~35 hudson, ~13 hell_gate).
Low-bank faces on the lines are z > −1 m, so `create_boundary(zmax=−1)` leaves them out and
`wall_outflow_near_forced_m = 500` walls any outflow they produce.

## 2. NACCS at the new cuts (`data/nj2_design/naccs/`, `build_naccs_boundary_nj2.py`, `naccs_cuts_nj2.csv`)

**Verified:** the 8 Hudson-pull zips are in `data/NACCS/hudson_pull_2026-11-02/` (→ scratch), and the builder's glob
(`data/NACCS/*.zip`) does not see that sub-folder. Nothing was moved. `data/nj2_design/naccs/` holds SYMLINKS to the
7 zips in `data/NACCS/` + the 8 Hudson zips, and a copy of the datum cache.

**The parse runs clean on the combined set:** 2,493 unique save points, the builder's own rules (`read_zips`: every
duplicate asserted identical, one Sandy time base, 1,968 steps). Cache: `naccs/_sandy_parsed_nj2.npz` (39 MB); v4's
`_sandy_parsed.npz` and `vdatum_lmsl_navd88.csv` untouched.

| cut | wet all window, within 1 km of the line | dry-flagged nearby (the builder drops them) | datum |
|---|---|---|---|
| **hudson** | SP4481 0.30 km, SP4471 0.41 km, SP4487 0.64 km (peaks 2.73–2.78 m NAVD88) | 4466, 4489, 4465 | grid NJncstemb11, −0.028…−0.029 m |
| **hell_gate** | SP19080 **5 m** and SP11877 **15 m** ON the line (3.60 m), SP11892 0.33 km, + 7 more within 1 km | 13895, 4298, 13909, 4294 | grid, −0.002…−0.025 m |

**No gap** at either cut. The 2 km screen also keeps points past the cut ends (the Harlem 4470 / 11884 / 4479 read
~0.2 m higher than the Hudson; Hell Gate's east-of-the-step 11893 etc.). SFINCS forces each boundary cell from its
**two nearest** points (`sfincs_boundaries.f90`, `ind1/ind2_bnd_gbp`), and on both lines the nearest two are the on-line
points above (≤ 0.65 km against ≥ 1.2 km for the Harlem ones), so those extras should not reach a cell; read the
builder's per-arm table after the freeze to confirm. The Hell Gate "~0.2 m high" question stays the 2.1 note (Decision 6).

**Command for tonight, after the freeze** (needs only the registered domain and its frozen `sfincs.nc`):
```bash
cd ~/nj_bight_sfincs; export PATH=$HOME/nj_sandy_sfincs/micromamba/envs/sfincs/bin:$PATH
NJ_DOMAIN=<nj2 domain> python -I logs/nj2_edges_2026-11-14/build_naccs_boundary_nj2.py --report-only   # read per-arm coverage first
NJ_DOMAIN=<nj2 domain> python -I logs/nj2_edges_2026-11-14/build_naccs_boundary_nj2.py                 # -> data/gtsm/naccs_sandy_<domain>.nc
```
Same rules, three globals swapped (zip dir, parse cache, datum cache), nothing else. Both beds share the mask, so one
file serves both (name it after either; the catalog entry decides). Declare the printed support count as
`n_waterlevel_support` on the arm, as for v4.

## 3. Observation points (`data/nj2_design/obs_nj2.csv`, `obs_nj2.obs`: 55 points)

The 48 points of 1.1.0's staged `sfincs.obs` (v4_refreeze positions, nudges included) + 7:

| name | position | observed series / datum | standing in nj2 |
|---|---|---|---|
| `noaa_battery` | −74.0142, 40.7006 | `gtsm/noaa_sandy_validation_6min.nc` station 8518750, NAVD88 (CO-OPS tie), peak 3.44 m | **interior holdout of the MODEL** (10.4 km from Hell Gate, 18.3 km from the Hudson cut). On v1.5–v4 it was a forcing input or outside. Not independent of the boundary PRODUCT: NACCS was presumably validated against it (NACCS − obs peak −0.03 m). Still in the BASE gauge-forcing support set for any non-NACCS arm |
| `noaa_bergen_point` | −74.1463, 40.6391 (CO-OPS API; the memo used −74.1422) | **`nj2_design/obs_nj2_bergen_point_6min.nc`** (new): NAVD88 DERIVED = MLLW − 0.846 (station MSL−MLLW) − 0.054 (VDatum LMSL→NAVD88 grid) = MLLW − 0.8996; peak 3.54 m 10-30 01:24. No published NAVD88 tie | interior holdout (KvK west mouth; inside v4 too but unscored) |
| `sss_gowanus` | −73.98984, 40.67688 | model-only: STN sensor, peak 3.38 m NAVD88 (series not pulled; the STN instrument API moved and was not resolved) | interior holdout once pulled |
| `sss_hoboken` | −74.0232, 40.7439 | none: SSS-NJ-HUD-001WL was damaged | output point for Hoboken |
| `sss_hackensack_hud002` | −74.0661, 40.7998 | model-only: SIR 2016-5085 Table 4 peak 2.68 m NAVD88 | backs mark 6095 |
| `bc_hudson_cut`, `bc_hell_gate` | ~110 m inside each cut | none | **FORCED < 500 m by design**: they read the imposed level (the Hell Gate question). Forcing diagnostics, never holdouts |

Flags (`flags` column; a flag, never a filter): 0 points within 500 m of a staged discharge source; nearest source to the
new area is 8.5 km away, and none lies inside it. `sss_narrows_si` / `sss_narrows_bkln` were 0.7 / 2.4 km from the
`narrows` arm and are now **interior holdouts** (12.6 / 8.4 km from the sea line). Not added: Spuyten Duyvil sensor and
Kings Point (outside), Hudson stage gauges (no Sandy record, above the cut).
**After the freeze:** check each new point lands on a wet face (`point_zb`); nudge as v4_refreeze did if not.

## 4. Hand-placed files (`data/nj2_design/structures/`) — what 1.1.0 runs with and what each needs

The frozen mesh dir holds only `sfincs.weir` (the 10-06 file) and `sfincs.obs`; everything else 1.1.0 runs with arrives
by template hand steps or arm overrides (`diff <(ls data/frozen_mesh_v4) <(ls experiments/v4_refreeze_swz_v11/_template_sealed)`).

| file in the 1.1.0 run | source | in the new area? | nj2 needs | prepared |
|---|---|---|---|---|
| `sfincs.weir` (arm `weir_from`) | `data/structures_v4/sfincs_overpeck_open_elizabeth_rahway_ground.weir` md5 `e11966fc…`, 24 polylines, 819 u/v on v4 | no (nearest: the Overpeck bypass sill, 2.1 km) | **copy** (UTM coordinates, mesh-free) + **re-count** u/v on each bed (counts depend on `uv_zmin`) | copied byte for byte = the 2.0 premier default |
| `sfincs.drn` | 1.1.0 runs **none** | — | side arms only: copy; check both ends still sit on the intended faces (the Cohansey pair was placed on v4 face centres, `s8_cohansey_gate.py`) | `cohansey_bacons_neck_gate_checkvalve.drn`, `gloucester_culverts_v11.drn`, `portmonmouth_pews_gate_checkvalve.drn` (≥ 18 km from the new area) |
| `sfincs_ini_regional.bin` (+ `.json`) | template hand step: binary real*4 per ACTIVE face in face order; Overpeck pool −1.005 m, 3,313 faces (still in 1.1.0 with the dam open) | no (pool 0.96 km away) | **REGENERATE** on the nj2 mesh (face order and active count change) | `overpeck_pool.geojson` copied |
| `sfincs.wvm` | `data/wavemakers_v4/v4_wavemaker_5m_mhw_snapbeach.wvm` (8 pieces, 157.7 km; staging writes it from the geojson) | no (≥ 17 km; built with `--y-max 4480000`) | **re-snap check**: rebuild on the nj2 bed/mesh and diff; identical if the coast faces are | `.wvm` + `.geojson` copied |
| SnapWave mask (`snapwave_mask` in `sfincs.nc`) | built by `add_waves` from `snapwave_footprint_ll` + the stepped band `v4_shelf_steps` (level-1 index space) | **excluded** (below) | keep V4's footprint; the steps hold only if nj2 keeps v4's base grid (x0, y0, dx, rotation, mmax/nmax), else re-derive the columns | — |
| `snapwave.bnd/bhs/btp/bwd/bds` | `add_waves` from CORA at 69 support points | no | regenerated by staging | — |
| `sfincs_netamuv/netamp` | 1.1.0: NACCS-blend 500 m (x 431–608 km, y 4280–4540 km); template: ERA5-bilinear 5 km | covered (new area x ≤ 593 km, y ≤ 4523 km) | **re-cut, not extend**. The blend's NACCS wind came from v4's parse, so the Hudson points are not in it (optional rebuild from `_sandy_parsed_nj2.npz`) | — |
| `sfincs_netampr`, `sfincs_cnb.nc` | AORC (to x 627 km, y 4541 km); `cn_v4.nc` / `ksat_v4_refreeze.tif` | covered (CN 92–94 and ksat present at Hoboken, UWS, Red Hook, LIC) | re-cut | — |
| `sfincs_netbndbzsbzifile.nc` | `naccs_sandy_v4` | — | §2 | — |
| `sfincs_netsrcdisfile.nc` | 61 v4_refreeze inflows | none in the new area | carry (re-check `source_proximity.py`) | — |
| `sfincs.obs` | §3 | | | `obs_nj2.obs` |

**SnapWave OFF over the Upper Bay / lower Hudson (user 11-14), how:** set nj2's `snapwave_footprint_ll` to V4's
unchanged (`V3.region` ∪ the `delaware_bay` polygon). Newark Bay is "off" in 1.1.0 for exactly this reason: it lies
outside that footprint. The v3 region stops at the old Narrows line (lat 40.611), so **0.000 km² of the 245 km² new
area** is in it; the Battery, Robbins Reef, the KvK, Bergen Point, Hoboken, Gowanus, Bay Ridge and both cuts all test
outside (`snapwave_footprint_check.txt`). The SnapWave edge stays where it is (a closed wave edge at the Narrows, now
interior to SFINCS), so the Narrows `hm0` limit cycle cannot spread north. Do NOT add the new area to the footprint.
Check after staging: `scripts/check_snapwave_domain.py`; no face north of lat 40.62 should carry `snapwave_mask > 0`.

**After the freeze — u/v counts (the engine's float32 rule), per bed:**
```bash
source logs/weirs_dikes_levees_2026-11-12/env.sh
D=experiments/<nj2 domain>/_template_sealed        # any dir with the bed's sfincs.nc + sfincs_subgrid.nc
python -I logs/walls_elizabeth_rahway_2026-11-05/engine_snap_f32.py $D \
  data/nj2_design/structures/sfincs_overpeck_open_elizabeth_rahway_ground.weir \
  data/nj2_design/structures/sfincs_overpeck_open_elizabeth_rahway_dikes_levees_cohansey_nj2.weir
# (v4 mesh, v1.1c bed: 819 and 3551.) For the crests (door checks): cd <workdir> && python -I \
#   logs/weirs_dikes_levees_2026-11-12/engine_count.py $D <weirfile>   -> <weirfile>.crests.npz
```
**Overpeck start:** `python -I logs/refreeze_2026-10-06/structures/pool_ini.py $D --region
data/nj2_design/structures/overpeck_pool.geojson --out $D --check data/nj2_design/structures/sfincs_overpeck_open_elizabeth_rahway_ground.weir`;
size must be 4 × the active-face count; add `inifile = sfincs_ini_regional.bin`.
**Wavemaker:** `NJ_DOMAIN=<nj2> python scripts/build_wavemaker_line.py --dep <nj2 bed>/subgrid/dep_subgrid_lev0.tif --mesh
$D/sfincs.nc --window 495000 4285000 605000 4492000 --contour-stride 2 --float32-weights --snap-seaward-of-beach --out
<scratch>/nj2_wavemaker.geojson`, then diff against `structures/v4_wavemaker_5m_mhw_snapbeach.geojson`.

## 5. Dikes-and-levees set for 2.0, fixed (user scope addition 11-14; `dikes_levees/`)

**Files** (`data/nj2_design/structures/`): `dikes_levees_cohansey_set_nj2.weir` (the set alone, 25 polylines, md5
`0f78b694…`) and `sfincs_overpeck_open_elizabeth_rahway_dikes_levees_cohansey_nj2.weir` (= the premier file byte for byte
+ the set, 49 polylines, md5 `fc0c9cdf…`: the arm's `weir_from`), + `cohansey_bacons_neck_gate_checkvalve.drn` (`drn_from`).
Built by `dikes_levees/fix_set.py` from the 11-12 `cand_recommended.weir` + `cand_cohansey_gate.weir`; 22 of 25 lines byte for byte.
**Engine u/v on the v4 mesh / v1.1c bed: 3551** (= 819 + 2,732; the 11-13 set was 3571). Re-count on nj2.

| line | what changed | check (static door, 1.1.0 mesh) |
|---|---|---|
| **Chester** `chester_nld4805000005_redraw_2026-11-14` | The NLD route runs ON the creek's inner bank; on the mesh the creek is one 25–50 m face wide, so the 11-12 line blocked **18 creek-to-creek links** and dammed the creek (`cand_chester_links.png`). Redrawn on the cell edges between the leveed ground cells (face centre in the NLD leveed area AND `z_zmin` ≥ 1 m; 56 cells, 8 creek faces left out) and the creek: same side, NLD crest (4.56–5.80 m), 19 m median / 90 m max landward of the 11-12 line, 181 vertices (`chester_redraw.py`, `chester_redraw_links.png`) | **0** creek-to-creek links. Source 26 (Chester Creek, 45.8 m³/s, 1.0 km upstream) joins the boundary at −0.00 m (11-12 line: **3.41 m, ENCLOSED**). Leveed ground door **4.37 m** (11-12: 4.18; pixel door 4.49; Sandy 3.41): still holds |
| **Forsythe** `…r1303_p0_r60_sw_2026-11-14` | SW corner: the outline ran 40–70 m north of the dike and took 0.47–0.84 m crests. Vertices 587–594 → a detour onto the dike crest, traced on 1/9″ CUDEM between hand-picked ends (`ridge.py`; crest 1.97–2.20 m) | region 1303 spill 0.58 → **0.91 m**, closed share 0.00 → **1.00** (MHHW 0.55) |
| **Tuckahoe 1286** `…r1286_p0_r60_ridge_2026-11-14` | The outline went round a low-marsh triangle south of the pool, along the upland toe, where the lidar shows no dike (0.72–0.88 m at the leak). Vertices 257–376 → the pool's diagonal dike crest (1.34–1.53 m) | region spill 0.72 → **1.10 m**, closed 0.001 → **0.913**; the open 9 % (~0.08 km²) is the triangle, **left open on purpose** (no dike to close it) |
| 6 structure notches | **kept filled = storm-shut**, the user's tide-gate rule (11-12). Lidar pass (`notch_check.csv`): only **r1054** (New Castle) has a < 0 m channel running through the line (a creek, culvert or gate opening) → **needs the imagery eye check** before any normal-weather `drn`; the other five are dips in the crest (min ground 0.25–0.94 m), Forsythe's NE notch −0.04 m but no through-channel | — |

All other regions and the three other levees read exactly as in the 11-13 set (Rohm & Haas 3.57, Henby 1.26 / 1.26).
Closed outright: 12.2 of 20.2 km² of assessed over-reach (11-13: 7.8). 0 HWMs within 50 m of any line (nearest 2.1 km);
all 25 lines inside the nj2 ring.

**The new static check (`dikes_levees/door_source_check.py`):** every staged discharge source within 3 km of an ADDED
line gets the level at which its face joins the boundary, base vs set; a rise > 0.25 m = **ENCLOSED** (the inflow can
only leave over a crest). It reproduces the Chester failure on the 11-13 file (+3.41 m) and passes the fix (0.00);
only sources 26 and 27 are within 3 km of any line. It also prints the regions' spill/closed table and the levees'
2 % door, now also on leveed ground only (a creek face inside the NLD polygon is not the leveed area). Static only: no
inflow volume, so a pond below a crest is still possible where the rise is small; run it on nj2 after the freeze.
Still open (user): imagery eye check of the r1054 notch and of the Tuckahoe triangle; the Cohansey valve size is
assumed (6.2); the dikes are lidar-traced locators, not surveyed lines.

## Paths for the domain agent

- Sea line: `data/nj2_design/waterlevel_line_nj2.csv` (= v4's vertices; sections and counts as V4; sea closure as V4_REFREEZE).
- Cuts: `data/nj2_design/cut_hudson_nj2.csv` (arm `hudson`, first vertex `hudson_w`), `data/nj2_design/cut_hell_gate_nj2.csv`
  (arm `hell_gate`, first vertex `hellgate_w`), each via `waterlevel_line_arms(..., corridor_m=500)`; drop `narrows`,
  `kvk_east`, `wall_bayonne`; keep `cd_canal`. A wall box for the Hell Gate east wall (hellgate_e → astoria, 300 m)
  and the e88 → hellgate_w low run are the ring's (already noted in `region_nj2_vertices.csv`).
- NACCS: `logs/nj2_edges_2026-11-14/build_naccs_boundary_nj2.py`; catalog entry `naccs_sandy_<domain>: {data_type:
  GeoDataset, uri: gtsm/naccs_sandy_<domain>.nc}` as `naccs_sandy_v4`; arm `waterlevel_geodataset` to match.
- Obs: `data/nj2_design/obs_nj2.csv` (name, lon, lat, kind, obs_file, obs_var, obs_station, datum, source, note,
  flags) → `ObsGauge` entries; new series file `nj2_design/obs_nj2_bergen_point_6min.nc` (relative to `data/`, var
  `waterlevel`, station 8519483). Then `scripts/sync_obs_points.py`.
- Weirs: premier default `data/nj2_design/structures/sfincs_overpeck_open_elizabeth_rahway_ground.weir`; 2.0 arm
  `…_dikes_levees_cohansey_nj2.weir` + `cohansey_bacons_neck_gate_checkvalve.drn`; `EXPECT_NWEIR` from §4's command on
  each bed.
- SnapWave: `snapwave_footprint_ll = V4.snapwave_footprint_ll`, `snapwave_domain="v4_shelf_steps"` if the base grid is v4's.
- Overpeck start, wavemaker: §4 commands.

## Files here

`build_naccs_boundary_nj2.py` (wrapper; `--parse-only`), `edges_nj2.py` (NACCS-at-cuts, structures, SnapWave footprint,
obs; rerun: `python -I logs/nj2_edges_2026-11-14/edges_nj2.py`), `naccs_cuts_nj2.csv`, `structures_carryover.csv`,
`snapwave_footprint_check.txt`; `dikes_levees/`: `chester_redraw.py`, `chester_map.py`, `chester_zoom.py`,
`chester_links.py`, `site_view.py`, `ridge.py`, `notch_check.py`, `fix_set.py`, `door_source_check.py` + their outputs
(`*_links.png`, `*_view.png`, `regions_*.csv`, `door_source_*.csv`, `levees.csv`, `notch_check.csv`, `engine/`).
Bulk (not for git): `data/nj2_design/naccs/_sandy_parsed_nj2.npz`, the `*_cudem_utm3m.np[yz]` windows.
