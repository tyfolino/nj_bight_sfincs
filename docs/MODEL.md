# MODEL — the v4 premier (model card)

**Version 1.1.0 (user 2026-11-09; git tag `v1.1.0`).** Describes arm
`p4-premier+weir-elizabeth-rahway` on domain `v4_refreeze_swz_v11` as run (job 63617802). Same mesh,
forcing and engine physics as 1.0.0 (`v4_refreeze_swz` / `p4-premier`, job 63181564, tag `v1.0.0`); the
changes are the flow bed, the wave bed that follows it, the weir file and the mark file ("Changes from
1.0.0", §2). Everything not listed there is 1.0.0's and is described below as written for 1.0.0. Evidence
lives in [FINDINGS.md](FINDINGS.md) (cited as §n, or "part 4 (x)" for the v4 design record) and the v1.1
read (`logs/v1_1_read_2026-11-06/READ.md`); this card states what the model IS, not how it got there.

**What it is.** A SFINCS (v2.3.3, patched) compound-flood hindcast of Hurricane Sandy, 28–31 Oct
2012, on the New Jersey coast from Cape May to the Narrows plus Delaware Bay and the tidal Delaware,
the Raritan, Newark Bay and the Arthur Kill, with the far banks (DE / PA / Staten Island) computed.
Compound = NACCS storm tide at a drawn sea boundary + SnapWave waves with a wavemaker (IG in the
water) + wind + pressure + rain with curve-number infiltration + 61 river inflows, together in one
run. Validated against USGS high-water marks, NOAA / USGS gauges and the FEMA MOTF surge extent.

## 1. Identity

| | |
|---|---|
| domain | `v4_refreeze_swz_v11` — `faces=4881654 boundary_edges=4388 sha(z,mask)=4bc97aae885f0aa4` (`nj_sfincs/premier.py`); same mesh and mask as 1.0.0 (`v4_refreeze_swz`, `90cc7468614a5814`), face `z` moved on 15,746 faces |
| arm | `p4-premier+weir-elizabeth-rahway` (`nj_sfincs/experiments.py`, block `v4_refreeze_swz_v11`): 1.0.0's `p4-premier` with `subgrid_from="_subgrid_v1_1c"` and `weir_from=data/structures_v4/sfincs_overpeck_open_elizabeth_rahway_ground.weir` (md5 `e11966fcab8b91f2e22583c8733a4dbf`), nothing else |
| engine | `bin:v2.3.3-winddir-igk-igseed-wmseed-swomp-2-gf11@dd78d82a` = `hpc/production_engine.txt` (user 2026-11-02), upstream commit `091f531a` (tag v2.3.3) + 6 patches (`hpc/patches/`, fork branch `nj/v2.3.3-swomp-2`); sha256 `dd78d82a40480c6ef5fe0a8bbb8cd77df2cfbc336c77c37d9662e48eb1560fa7`. Bit-identical to 1.0.0's `…wmseed-1-gf11@e15ed916` on the full storm (FINDINGS §20); written to each run's `engine.txt` |
| flow bed | `_subgrid_v1_1c` (built 2026-11-06, job 63578834; recipe in its `provenance.txt`). 1.0.0: `_subgrid_refreeze_lakes_min_creeks_cohansey` (built 2026-10-23, `…@34ba916d`) |
| wave bed | mesh face `z` = the flow bed's subgrid mean ground, buildings included (`scripts/setup_face_z.py --from v4_refreeze_swz --bed _subgrid_v1_1c`; §2) |
| weirs | 819 engine structure u/v points (1.0.0: 412): the Overpeck dam removed, the Elizabeth / Rahway levees added. The engine snaps in float32 and counts a centre lying on a line as crossing every link of its face, so it reads 819 where `weir_on_mesh.snap` + 1 predicted 817 (`logs/walls_elizabeth_rahway_2026-11-05/weircount_819.md`) |
| run | job 63617802, `hal0383`, 32 threads, `restart_count 0`: uninterrupted, seeded. SLURM says FAILED: the job's own weir-count check refused to score (819 ≠ 817) after the solve had finished; scored by 63666636 |
| window, CRS | `tstart` 2012-10-28 00:00 → `tstop` 2012-10-31 00:00 (72 h), `tspinup` 3600 s; EPSG:32618 (UTM 18N), elevations and water levels m NAVD88 |
| output | his 600 s (48 obs points + cross-sections), map 3600 s, `zsmax` every 21600 s, restart every 21600 s (the restart files are removed when a run finishes) |

**Verify the fingerprint** (reads `z` and `mask` from the run's `sfincs.nc`, checks obs points and output):

```bash
NJ_DOMAIN=v4_refreeze_swz_v11 python -m nj_sfincs.premier experiments/v4_refreeze_swz_v11/p4-premier+weir-elizabeth-rahway
# OK  experiments/v4_refreeze_swz_v11/p4-premier+weir-elizabeth-rahway  v4_refreeze_swz_v11 STAGED 2026-11-06 …  obs OK  output WHOLE
```

With no path it audits every run dir on the domain. Trust neither the name nor the counts: sibling domains on
this mesh share face and edge counts, and only the sha tells them apart. Read nothing before `output WHOLE`.

## 2. What is IN

### Changes from 1.0.0 (1.1.0; everything else in this section is 1.0.0's)

| what | 1.0.0 | 1.1.0 | evidence (waves-off pair vs `p4-nowaves`, median 50 m, n 110, unless stated) |
|---|---|---|---|
| river beds | `riverbeds_hierarchy_v4c` | `riverbeds_hierarchy_v4e`: lower Mullica + Tuckahoe, Toms, Cedar Ck, Westecunk, Raccoon, Mantua from charts / surveys (v4d) + the Christina plug removed (v4e) | v4d kept, all 7 reaches (`logs/mullica_bed_2026-11-03/READ.md`); v4d + v4e + channel n ΔRMSE −0.0021 [−0.0089, +0.0029]; Newport tide range 0.62 → 0.95 of observed |
| bridge decks in the bed | none removed | `deck_fix_v4b:min` (deck pixels only, each to its own bank; 588 of 597 wet crossings open) | decks ΔRMSE −0.0010 [−0.0021, −0.0003]; Sea Isle tide range 0.687 → 0.818 (`logs/decks_2026-11-04/`); FINDINGS part 4 (m) |
| NBI water crossings | — | `nbi_open_v4:min` (8 verified + 18 over federal channels; `logs/nbi_crossings_2026-11-05/`) | built into v1.1c; no separate pair |
| eHydro channels | 2012 survey tiers only | + `ehydro_fill_v4:min` (9 survey tiles, 2.04 km², lower-only; `logs/ehydro_inventory_2026-11-05/`) | built into v1.1c; lower-only; reconnects the Broadkill / Lewes–Rehoboth canal (`logs/bed_audit_2026-11-05/out/TRIAGE_v1_1c.md`) |
| impounded lakes | CUDEM ~0 m fills under Alloway and Silver Lakes | `alloway_pool_v4` (0.388 km² at 1.61 m) + `silver_pool_v4` (0.174 km² at 2.55 m), raise-only | FINDINGS part 4 (m)(4) |
| Manning, developed land | NLCD 22–24 → 0.10 / 0.13 (tuned 2026-05 on a model WITHOUT buildings: a double count with the burn) | `manning_developed_v4`: 0.04 in NJ only (where footprints are burned); PA / DE / Staten Island keep NLCD n | ΔRMSE −0.0033 [−0.0058, −0.0014]; MOTF CSI 0.771 → 0.779 (`logs/developed_manning_2026-11-03/`) |
| Manning, channels | marsh / NLCD n on tidal channels | `manning_channel_v4e`: 0.02 in the surveyed channels | with v4e (above) |
| Little Egg channel | `littleegg_channel_v4` | kept (18-day tide test: a tie; `logs/barnegat_tide_2026-11-04/READ.md`, `GAUGES.md`) | — |
| Overpeck tidal dam | weir line in (dam closed) | removed (open; Keansburg system + bypass sill kept) | valley peak 0.93 → 2.37–2.44 m (NACCS 2.25); 23 independent marks ΔRMSE −0.009 [−0.020, +0.002] |
| Elizabeth / Rahway levees | not in | in: USACE Elizabeth River South (Right + Left Bank) and Rahway South Branch (Right Bank) at the NLD crest, the 85 m Bayway wall, 3 tie-ins and 11 ground guards (lidar ridge where the mesh averaged a rise away); gates closed (`logs/walls_elizabeth_rahway_2026-11-05/`) | waves-off pair 63612303: ΔRMSE +0.0000 [−0.0000, +0.0000]. The 15 independent Newark marks scored ONE-SIDED (only water on the mark's side of a levee line; waves-off): only the two marks within 15 m of a levee move (001WL +0.01 → −0.07, HWM-208 +0.21 → +0.09 m); Elizabeth RMSE 0.149 → 0.119 (n 4), all 15 0.154 → 0.147. Bayway 345 kV substation dry (97 % wet, median 0.79 m, without). **No observation inside the leveed areas**: that it stayed dry is the model's, untested. MOTF cannot judge (a bathtub surface with no levees) |
| validation marks | v4 file, 193 marks (110 scored) | 1.x file `data/validation_v4/sandy_hwms_v4_1x.geojson` (md5 `1919eba410d3c7c7d2ce8ca328be4a9f`): + 13 marks the v4 pull missed (Newark Bay / Hackensack / Overpeck), 206 marks (119 scored); 1.0.0 scores 119 on it too | a deliberate re-baseline (`logs/v2_validation_2026-11-03/`) |
| Christina gauges | Newport 01480065 / Wilmington 01480120 read as NAVD88 (were NGVD29) | re-datumed −0.326 / −0.314 m (`data/gtsm/usgs_sandy_tidal_v4.nc`, 11-05) | a measurement fix: compare gauges by re-baselining, not by delta |

### Domain and mesh
- **Ring:** `data/region_v4_hot_plus.geojson`, from `data/v4_design/region_v4_hot_plus_vertices.csv` (198 named
  vertices, hand-edited, checked by `scripts/audit_region_v4.py`); rule: contains the NACCS Sandy peak + 3 m,
  connected from the ocean (part 4). **Rivers cut at today's head of tide**; the Cohansey and Neshaminy keep
  the +3 m reach. Upriver of a cut is out of scope by design.
- **Sea boundary:** a DRAWN line through NACCS save points, Cape Henlopen → Brooklyn
  (`data/v4_design/waterlevel_line_v4.csv`, 99 vertices, 241 km, 7 arms + boxes at the Narrows, Kill
  van Kull east and the C&D canal). Landward of it the ring is active at any depth. Lower, Raritan and
  Sandy Hook Bays are COMPUTED: an interpolation between gauges outside Raritan Bay cannot produce its
  interior tidal maximum (FINDINGS part 2). The Upper Bay and the Hudson are not computed (§4).
- **Quadtree** (4 levels, base 200 m, rotation 0.925°): 25 m 1.42 M faces, 50 m 2.25 M, 100 m 0.26 M,
  200 m 0.95 M (the Track C coarse shelf); 3,965,303 active (`mask` 1: 3,956,544; forced, `mask` 2:
  4,482; outflow, `mask` 3: 4,277). 25 m within 50 m of every channel narrower than 50 m
  (`narrow_channels`, +254 k active). 16 subgrid pixels per cell, 10 levels.
- **Walls / leak closures:** 11 leak walls, the Cape Henlopen gap, the Lewes edge, Darby Creek, forced-line-end
  walls (`wall_outflow_near_forced_m` 500); the SLR gate (+0/+2/+3 m, rain off) wets no outflow edge cell (part 4 (g)).

### Bed (one source hierarchy for every channel, user 2026-10-05)
Base merge, top tier wins: USACE eHydro channel surveys (7 sets) → river beds → 2010 USACE NCMP
topobathy lidar → USGS CoNED (SW Raritan) → NOAA CUDEM 1/9″ (NJ, Delaware) → NJ 10 ft lidar DEM →
CUDEM 1/3″ → USGS 3DEP (PA/DE/NY land) → GMRT. Then overlays, painted in order: buildings → inland
lakes (85 lakes + 2 rivers) → USACE "unpave" (2010-lidar sills undone, ocean side and back bays) →
harbour + Raritan-corner eHydro → Sayreville → Little Egg channel → **`riverbeds_hierarchy_v4c`**
(eHydro → CUDEM where it is a real bed → NOS / ENC soundings → a shaped sloping section to 1.2 m
below MLLW at the head of tide; on the Cohansey also tide-reduced crowdsourced soundings + NOS
D00081) → `lake_fix_v4` and the creek beds, both LOWER-ONLY (`:min`). §54, part 4 (h).
- **Buildings:** NJDEP footprints (NJ only; the far banks have none) burned at local ground + 10 m
  (`bed_buildings_v4_cap10`), acting as subgrid porosity. In the FLOW close to neutral for Sandy: `bed-nobuildings`
  − premier ΔRMSE −0.003 [−0.057, +0.039] (median, 50 m, n 110, paired; §55, with no buildings in the waves).
- **Wave bed (SnapWave's bed):** SnapWave never reads the subgrid; its whole bed
  is the mesh's face `z`, and the flow never reads face `z` (§63 (a)–(b)). Here face `z` = the flow bed's
  subgrid mean ground (`z_zmax − z_volmax / area`, `scripts/setup_face_z.py`) on 3,936,632 active faces;
  28,671 active faces on hydromt's −20 m volume floor keep their old `z`, as do inactive faces. That
  mean ground includes the building burn, so waves over developed ground see it: between the Monmouth
  lakes and the beach crest face `z` sits ~1.2 m higher than bare ground, +1.13 m of it the burn (at
  marks 6124 and 6129, §63 (h)). Buildings in the waves have not been measured against bare ground.
- **Assumed beds, flagged:** creek beds at ≈ MLW where no survey exists (Salem River and Mannington Creek left
  out); the Sluice Creek pool painted at −0.24 m; the Cohansey above 3.6 km is still a slope guess.

### Forcing and physics

| process | how | source |
|---|---|---|
| storm tide | NACCS / CHS ADCIRC+STWAVE storm 001, 241 support points, 15-min, at the drawn line (`netbndbzsbzifile`); INCLUDES offshore wave setup, nested one-way (§22–23) | `naccs_sandy_v4`, part 3 |
| wind, pressure | NACCS save-point wind (1,901 points) blended into ERA5, 500 m grid, 30 min, 15 km taper (`netamuv`); pressure is ERA5 inside the blend (`netamp`, `baro` 1); drag `cdnrb` 3, `cdwnd` 0/28/50 m/s → `cdval` 0.001/0.0025/0.0025 | `data/wind_v4/naccs_blend_p_era5/`, part 4 (g) |
| rain | NOAA AORC v1.1 hourly, on an ~830 m grid as staged (`netampr`) | `aorc_sandy_v4` |
| infiltration | `cnb` (curve number with recovery), AMC factor 1.5; CN from NLCD 2012 × SSURGO HSG (water CN 100), ksat from SSURGO surface horizon; 1,992,347 of 3,965,303 active points infiltrate | `cn_v4`, `ksat_v4_refreeze`, §59 |
| rivers | 61 inflows, USGS daily mean discharge (approved), area-scaled, placed in their channels (0 of 193 marks within 500 m of a source) | `usgs_sandy_discharge_v4_refreeze`, §40 |
| waves | SnapWave: 5° bins over 360°, updated hourly (`dtwave` 3600, §61), wind growth on, `gamma` 0.78, `alpha` 1, `fw` 0.01 (§56), `niter` 200; boundary = NOAA CORA SWAN at 69 support points (§21); SnapWave domain `v4_shelf_steps` (about 3.38 M active nodes), on the wave bed above | `data/waves_v4/cora_waves_v4.nc` |
| infragravity | **This model has a wavemaker, so IG is in the water.** `snapwave_igwaves = 1` alone would not do that: it only computes IG inside SnapWave and takes the energy from the incident waves (§45). The water gets IG through the wavemaker line: `wvmfile = sfincs.wvm`, 8 pieces, 157.7 km, 7,940 u/v points, snapped seaward of the beach (§62) | `data/wavemakers_v4/v4_wavemaker_5m_mhw_snapbeach.geojson` |
| structures | 7 weirs, 412 engine points, weir coefficient 0.6: Keansburg levee system on the USACE NLD centreline (Waackaack gate, Thornes reach, west tie, bayfront dune), the Pews levee gap closed, Overpeck tidal dam + bypass sill. Assumed: stop logs in, gates held (§38) | `data/structures_v4/sfincs.weir` |
| roughness | Manning from NLCD 2012 (`NLCD_CONUS_mapping.csv`); `manning_water_v4` overlay: 0.02 on lakes / non-tidal rivers, marsh n kept on tidal water | `nlcd_2012_v4` |
| start | `zsini` 0 + a binary regional start (`sfincs_ini_regional.bin`: the Overpeck pool at −1.005 m, 3,313 faces), §51 | template |
| flow | advection, Coriolis (lat 39.86), viscosity 0.01, `alpha` 0.5, `huthresh` 0.01, `rhoa` 1.25, `rhow` 1024 | `sfincs.inp` |

## 3. Engine

Upstream SFINCS v2.3.3 ("Faber"), built natively with `hpc/build_sfincs_native.sh` (host gfortran
11.5, `-fopenmp -O3 -fallow-argument-mismatch -w`, OpenACC off), with four patches
(`hpc/patches/snapwave_igseed_wmseed_v2.3.3.patch` carries all four; `metrics.csv` records
`engine_seed = fixed`, `snapwave_direction = imposed`):

| patch | fixes | § |
|---|---|---|
| `nj-winddir-fix-1` | with `snapwave_wind = 1` the boundary spectrum was rotated to the domain-mean WIND direction (matched the imposed direction 0 of 73 h, worst 170°); spectra now built after the final theta grid, centred on the imposed mean direction. No-op with wind off | §43 |
| `nj-igk-fix-1` | v2.4.0 backports: IG wavenumber from `sigm_ig`; `wavemaker_angfac = max(−sin φ, 0)` (unpatched v2.3.3 injects nothing for a line with land on the right) | §47, §49 |
| `nj-igseed-1` | the Herbers IG draw used unseeded `RANDOM_NUMBER`: IG-on runs never repeated. Fixed seed, re-set every call | §44 (a)–(d) |
| `nj-wmseed-1` | fixed seed for the wavemaker phases + phase in closed form from model time (real*8), so a resume sees the same IG forcing | §44 (j) |

To get it, from a v2.3.3 checkout (a preamble in the patch file is ignored by `git apply`):

```bash
git checkout 091f531a && git apply <repo>/hpc/patches/snapwave_igseed_wmseed_v2.3.3.patch
hpc/build_sfincs_native.sh v2.3.3-winddir-igk-igseed-wmseed-1-gf11 --src <checkout>
```

**New runs use a faster build of the same physics** (`…swomp-2-gf11@dd78d82a`, §7; results bit-identical on this run, §20).
Two more patches, on the same checkout (a fresh apply reproduced the production source tree exactly, 2026-11-02):

```bash
cd source
patch -p1 < <repo>/hpc/patches/snapwave_swomp_v2.3.3.patch
patch -p0 < <repo>/hpc/patches/snapwave_swomp2_on_swomp1_v2.3.3.patch
cd .. && <repo>/hpc/build_sfincs_native.sh v2.3.3-winddir-igk-igseed-wmseed-swomp-2-gf11 --src <checkout>
```

A rebuild under another name or path changes the whole-file sha256 but not the machine code: compare
`objcopy -O binary --only-section=.text`, sha256 `b08b73ea03e6…` (a fresh rebuild matched, 2026-11-02). The source
folder and the variant name must differ: the script builds in `/scratch/tpj8/sfincs-build/<variant>` with `rsync --delete`.

Check the sha256 in the `BUILD_INFO` beside the binary against §1; netCDF-C came from the `sfincs-build` env (4.10.1).
A different compiler or library gives a different binary, a new engine label: re-baseline.

Upstream: the wind-direction bug (issue #362) is fixed in Deltares PR #371 (merged 2026-10-08). **Not yet filed:** the
IG seed + wavemaker phase issue and the wavemaker IG frequency shift (drafts in `docs/upstream/`), the dead-corner rule
(§52). The run also reads a patched hydromt-sfincs (`hpc/patches/quadtree_mixin_pad2.patch`, one-cell sliver padding).

## 4. Known limits, and what is OUT

Mark residuals here are model − observed, **median estimator, 50 m radius**; `metrics.csv` or §63 (g).

- **Monmouth coastal lakes.** The five `lake_outlet_blocked` marks read 6121 −2.03, 6122 −2.27, 6124 −0.69, 6129 −0.05,
  6130 −2.09 m and set the headline RMSE (§6). Side runs (part 4 (j)): a Wreck Pond breach takes 6130 to +0.48 / +0.74 m but 6129 to +0.41 / +0.67; Deal overtopping takes 6122 to −1.80; 6124 and 6129 lean on the wavemaker (−1.99, −0.66 without it); 6121 moves only with no buildings at all. Do not use these lakes' peaks.
- **Peak wave heights are not all physical.** `hm0` reaches 27.55 m at the Narrows (40.606 N, −74.045) at hour 11 of the run, well before the storm, against 9.98 m at the wave boundary; 3,131 faces reach ≥ 12 m, 2,765 of them at the Delaware Bay mouth. On the previous wave bed: 26.67 m, 5,974 faces, so it did not come with this bed. The Narrows and Sandy Hook cells are the SnapWave limit cycle (FINDINGS §44 (g)); the Delaware mouth is unexplained. Its effect on water level is unmeasured. Do not publish a peak-`hm0` map unclipped.
- **Delaware: low water, and few marks.** The storm low misses by −0.36 m at Lewes, −0.6…−0.7 m Ship John → Philadelphia,
  −0.7…−1.0 m at Newbold (rough high/low pick on the previous wave bed). At the mouth it is the NACCS forcing; the growth
  upriver is unexplained. Peaks are better (§6); the Christina gauges read −0.47 m Newport, −0.23 m Wilmington since their observed
  series was re-datumed NGVD29 → NAVD88 (11-05; re-scored 11-07, job 63666636 — before the fix −0.80 / −0.54).
  Only 3 marks are scored in the Delaware basins (2 river, 1 NJ bay shore).
- **Cape May back bays.** Bias −0.288, RMSE 0.317 m (median, 50 m, n 4); published-crest gauge errors −0.305 m
  Sea Isle, −0.252 m Stone Harbor, −0.190 m Avalon. Open (§57).
- **Inflow pile-ups on coarse faces.** Ridley, Chester, Frankford, Red Clay, White Clay, Christina and **Salem R. at
  Woodstown** (peak / bed 4.38 / 0.01 m) enter on 100–200 m faces and stand metres above a ~0 m bed (measured on an
  earlier configuration of this mesh, not re-read on this run). Do not read depths there; the fix needs a new mesh.
- **Building cap under sea-level rise.** A ground + 4 m cap is overtopped at +3 m SLR (4.6 % of in-model buildings stood
  in deeper water), hence this bed's ground + 10 m. Overtopping of the 10 m burn is uncounted; check before SLR use.
- **Building drag is counted twice on developed land (found 2026-11-03; FIXED in v1.1).** NLCD developed n 0.10 / 0.13
  (classes 23 / 24) were tuned on a model without buildings to stand in for them, and this bed burns the buildings in
  as well. Overland flow through built-up land is too slow: the likely cause of the South Ironbound and Newark-airfield
  misses (water reaches the area, then falls 3.66 → 2.4–2.55 m on the way). Read inland urban depths as low.
- **Newark Bay / Hackensack / Overpeck carry no HWMs in this model's mark file** (pulled on a box that stopped at
  40.617 N): 13 marks inside the ring, 9 headline, join the mark file in v1.1.
- **Hudson waterfront and Upper Bay shore: NOT in the model.** Hoboken, east Jersey City (Exchange Place, Liberty State
  Park) and Bayonne's Upper Bay side are outside the active mask (`mask` 0, nearest active face ~1–3.6 km; confirmed
  2026-10-30). Blank there means not computed, never dry. Interior Bayonne and its Newark Bay side are active.
- **A resumed run is a different run** (§5). This run was not resumed; read one that is against an uninterrupted twin.

| not represented | what it costs | evidence |
|---|---|---|
| **morphology: dune erosion, breaching, overwash** (fixed bed) | In Sandy the dune breached at Wreck Pond and the sea overwashed into Deal Lake; in the model the sea does not get in (lowest connections 2.82 / 3.11 m vs a local sea peak 2.78–2.80 m; traced on the earlier unseeded configuration, part 4 (h)). A breach reaches 6130 and overshoots 6129 on this wave bed (part 4 (j)); the post-Sandy dune bed (`bed-postsandy`) is deferred by the user | part 4 (h), §49, Closed |
| **wave run-up, splash, overtopping** (still-water model) | marks 6121 / 6398 / 6188 are upper bounds the model cannot reach; offline EurOtop overtopping fills Deal Lake 0.29 of the 1.78 Mm³ needed — "the reach is there, the volume is not" (wave input from the earlier unseeded configuration; the `src-deal-overtop` arm on this wave bed lifts 6122 by 0.46 m, part 4 (j)) | part 4 (h) |
| **storm drains, outfalls, culverts** | closed-basin lakes fill by rain and drain nowhere; infiltration acts on rain, never on standing water | §59, part 4 (h) |
| **structure failure** | weirs hold all run; the Keansburg pocket is watertight and fills by rain only (6133 / 6155 / 6156 noted `leak`, they do not test the levees) | §38 |
| **wave diffraction; per-point boundary direction** | SnapWave v2.3.3 has neither: one mean boundary direction per call collapses CORA's alongshore spread; bays sit 0.24–0.69 m under CORA's SWAN at the peak | §43, §48 |
| **rivers above today's head of tide** | out by design (A+); no measured bed exists above the Trenton falls | part 4 |
| **bay-scale wind** | no gridded product resolves the bays | part 4 (e) |

Coupling, breaching and back-bay literature: `reports/literature_review_2026-10.md`.

## 5. Behaviours a user must know

- **A resumed run is not the run.** A restart file holds `zs`, `q` and the boundary `uvmean` only.
  Waves-on: SnapWave starts cold, so a resume differs (v4 calm window: up to 1.99 m at
  `sss_narrows_si`) — read it against an uninterrupted twin or re-run (§44 (j)). Rain-on with `cna`:
  the soil restarts empty (`cnb`'s state survives, §59). Check `restart_history.txt` before pairing.
- **Waves-on runs carry a noise band.** Seeded runs repeat bit for bit (§44 (d); this domain's repeat is bit-identical), but a null input change (`rhoa` × 1.00008) moves 7 of 48 points > 10 cm within 6 h; waves-off zsmax
  p99 0.18 mm. Through the peak, on this domain (two `rhoa` null copies, part 4 (j)): gauge peak band median 2.1 cm, max 10.4 cm (Marcus Hook;
  Raritan / Lower Bay / Sandy Hook 1–9 cm, Delaware 1–10 cm, Barnegat and Great Bay ≤ 2 mm); per-mark median 1.4 cm, p90 8.3 cm, max 18 cm; wet-face `zsmax` band 0.083 m; whole series up to 0.3 m on the bays and 1.8 m at Delaware River gauges.
  The NY-bay crest also carries a ±0.1–0.15 m seiche phase (§61 (g)). A capped SnapWave call can put a pulse into the
  Delaware River (§44 (h)): 26 of 73 calls capped on the previous wave bed, not recounted here.
- **Rain ponding depends on the window.** Closed coastal lakes still rise at `tstop`; a later stop scores them higher
  (part 4 (g)). `--tstop` cannot run on a sealed template: use `scripts/engine_gate.py make … --hours H`.
- **Meteo files are in the engine's corner convention** (`nj_sfincs/meteo_grid.py`); reading one
  with `xr.interp` is half a cell off — use `meteo_grid.true_centres` (part 4 (e)).
- **Maps:** "flood depth" is water above the PIXEL ground on normally-dry land only; peak water level (`zsmax`) is a
  separate map (CLAUDE.md §6). The floodmap bleeds onto inactive ground: screen with `validate.simulated_mask` (§37).

## 6. Validation (what is scored, and how)

Scores go to `experiments/v4_refreeze_swz_v11/metrics.csv` (1.0.0: `experiments/v4_refreeze_swz/metrics.csv`);
every row carries `engine`, `engine_seed`, `meteo`, `infiltration`, `subgrid`. Arms are compared PAIRED
(`scripts/paired_hwm_bootstrap.py`). 1.1.0 is scored on the 1.x mark file, 1.0.0 on the v4 file: compare them on
the PAIRED rows, which put both on one mark set. A bare-ground wave bed scores the same (ΔRMSE −0.000
[−0.004, +0.004], part 4 (j), on 1.0.0). **HWM and MOTF scores are on the NATIVE 3.125 m floodmap** (re-scored
2026-11-12/13, `logs/floodmap_fix_2026-11-12/`, `logs/native_rescore_2026-11-13/`, job 63894123): every floodmap
before 2026-11-12 was read on the bed's first overview (6.25 m; FINDINGS §37). That is a map-resolution fix, not a
model change; the 6.25 m numbers are kept below, labelled. `metrics.csv` still holds 1.1.0's 6.25 m row; the native
rows are in `logs/floodmap_fix_2026-11-12/rows/`. Gauge keys do not depend on the floodmap.

| target | scored as | 1.1.0 (`p4-premier+weir-elizabeth-rahway`) | 1.0.0 (`p4-premier`) |
|---|---|---|---|
| USGS HWMs (STN event 24), all | RMSE / bias, **median estimator, 50 m radius** (`_scored` keys), native 3.125 m floodmap | 1.x file: **RMSE 0.348, bias −0.067 m**, n 119, 0 dry, 93.3 % within ±0.5 m (6.25 m: 0.355 / −0.072, 1 dry) | v4 file: RMSE 0.435, bias −0.125 m, n 110, 0 dry, 90.9 % within ±0.5 m (6.25 m: 0.439 / −0.128, 1 dry, 91.8 %) |
| paired, 1.1.0 − 1.0.0 | ΔRMSE [95 % CI], B 200 000, seed 20261007, same estimator and radius, native | 1.x file (n 119): 0.348 vs 0.421, **−0.072 [−0.166, −0.007]**; v4 file (n 110): 0.360 vs 0.435, −0.075 [−0.174, −0.007]. By basin (1.x): open coast −0.221 [−0.575, +0.017], NJ back bays −0.055 [−0.092, −0.008], inlets / NY bays / rivers within ±0.015. (6.25 m, 11-07: −0.069 [−0.158, −0.007] / −0.072 [−0.165, −0.006]) | — |
| HWMs without the `lake_outlet_blocked` marks | same estimator and radius (`_excl_lake_blocked`), native | RMSE 0.240, bias −0.029 m, n 114, 94.7 % within ±0.5 m (6.25 m: 0.249 / −0.033) | RMSE 0.250, bias −0.062 m, n 105, 94.3 % within ±0.5 m (6.25 m: 0.259 / −0.066) |
| HWMs without the 6 noted marks (6121, 6155, 6169, 6188, 6202, 6398: run-up, `leak`, questioned; drawn hollow) | same estimator and radius (`_excl_noted`), native | RMSE 0.310, bias −0.049 m, n 113, 97.3 % within ±0.5 m (6.25 m: 0.312 / −0.051) | RMSE 0.352, bias −0.091 m, n 104, 96.2 % within ±0.5 m (6.25 m: 0.354 / −0.093) |
| NOAA CO-OPS gauges (6-min) | peak error, m | Atlantic City +0.50, Cape May +0.00, Lewes −0.17, Ship John −0.05, Reedy Point −0.11, Delaware City −0.24, Marcus Hook −0.21, Philadelphia −0.18, Burlington −0.17, Newbold −0.19; Sandy Hook −0.30 before the gauge failed. The upper Delaware reads 0.05–0.07 m lower than 1.0.0 | Atlantic City +0.494 (the NACCS forcing, local to there; part 4 (h)), Cape May −0.101, Lewes −0.191, Ship John −0.068, Reedy Point −0.110, Delaware City −0.189, Marcus Hook −0.142, Philadelphia −0.120, Burlington −0.116, Newbold −0.138; Sandy Hook −0.321 before the gauge failed |
| all gauges with a full peak record (NOAA, USGS tidal, STN storm-tide sensors) | peak error; Great Kills corrected −0.34 m (§50); published crests where USGS's archive has the storm-day hole (`peak_err_pub_*`, §60 (f)) | per gauge in `logs/v1_1_read_2026-11-06/READ.md` §5; Christina gauges re-datumed (re-baseline, no delta). Same 27-gauge recipe: median \|error\| 0.117 m, median −0.067 m | median \|error\| 0.110 m, median −0.068 m (27 gauges) |
| the 40 "fair" gauges | peak error, the scorer's keys: the 48 gauges minus 3 dead before the crest with no published crest (Sandy Hook, Brandywine Shoal, New Castle) and 5 that read the forcing (2 Narrows sensors, Lewes, Sea Bright beach sensor, Atlantic City); full record (22), published crest (15) or pre-failure crest (3) (`logs/poster_diagnostics_2026-11-13/README.md` §1) | **RMSE 0.226 m, bias −0.103 m, 85 % within ±0.25 m**, 92.5 % within ±0.5 m, median \|lag\| 34 min; NJ (29) 0.229 / −0.088 / 86 %; without the Cape May storm-tide sensor (−0.61 m) 0.208 m (n 39) | — |
| FEMA MOTF extent (NJ only) | CSI / POD / FAR inside the validity mask, footprints not masked (§55), native 3.125 m floodmap | **CSI 0.802, POD 0.868, FAR 0.086**; `motf_km2_excluded_boxes` 2,412.7 km²; false alarms 42.2 km² connected, 71.1 km² disconnected (6.25 m: CSI 0.795, POD 0.859, FAR 0.086) | CSI 0.791, POD 0.855, FAR 0.087; `motf_km2_excluded_boxes` 2,412.6 km² (incl. `salem_marshes`, 418 km²); false alarms 40.1 km² connected, 72.2 km² disconnected (6.25 m: CSI 0.784, POD 0.846, FAR 0.086) |
| FEMA MOTF extent, rain-off twin (the MOTF standard since 11-09) | as above, `p4-premier+rain-off+weir-elizabeth-rahway`, native | CSI 0.821, POD 0.845, FAR 0.034; FA 30.9 / 10.8 km² connected / disconnected. Rain off trades −72 km² of false alarm for +31 km² of misses (FINDINGS part 4 (o)) | — |
| 15 independent Newark-window marks (SIR 2016-5085 / OFR 2013-1043) | one-sided (no pixel across a levee line), median, 50 m, waves-off pair | levees vs none: all 15 RMSE 0.147 vs 0.154; Elizabeth (n 4) 0.119 vs 0.149 (`logs/walls_elizabeth_rahway_2026-11-05/README.md` "One-sided mark read") | — |

The levee arm and the Overpeck-only arm (`p4-premier` on this domain) tie on the marks: ΔRMSE −0.0001
[−0.0034, +0.0031], n 119; MOTF CSI 0.7947 vs 0.7942. The levees were chosen because they are mapped flood-control
structures (NLD) and scoring them one-sided hurts no mark, not because the scores separate the arms (user 2026-11-09).
(Those two figures are 6.25 m; the Overpeck-only arm was not re-scored natively.)

**Sensitivities (1.1.0)** (median, 50 m, 1.x file, n 119, paired, B 200 000, native 3.125 m; FINDINGS part 4 (n)):

| what | result |
|---|---|
| waves on vs off (job 63895426; the waves-off arm is this domain's `p4-nowaves`, Overpeck-only weirs, no levees) | −0.186 [−0.317, −0.072]; RMSE 0.348 vs 0.534. Open coast −0.459 [−0.883, −0.120], inlets −0.124 [−0.166, −0.074], NJ back bays −0.146 [−0.252, −0.006], NY bays −0.022 [−0.059, +0.008], rivers −0.007 [−0.020, +0.006]. Without the lake marks (unpaired) 0.240 vs 0.298. 40 fair gauge peaks: RMSE 0.226 vs 0.274 m, every crest higher with waves (median +0.09 m) |
| rain on vs off (job 63894123) | −0.017 [−0.028, −0.007] (0.348 vs 0.365); extent: rain off CSI 0.821 / POD 0.845 / FAR 0.034 vs 0.802 / 0.868 / 0.086 |

**Sensitivities (1.0.0)** (ΔRMSE of `p4-premier` − the arm, median, 50 m, n 110, paired, B 200 000, 95 % CI;
parts 4 (i)–(j); 6.25 m overview floodmaps); only waves and rain were re-run on 1.1.0 (above). Rain and soil were measured on the previous wave bed; non-lake effects should carry over.

| what | result |
|---|---|
| waves on vs off | −0.150 [−0.244, −0.070]; marks rise +0.32 m open coast, +0.20 NJ back bays, +0.19 inlets, +0.13 NY bays, +0.06 rivers. This domain, unpaired: RMSE 0.558 waves-off → 0.439 |
| wavemaker on vs off (this domain) | −0.077 [−0.145, −0.021]; without the 5 lake marks −0.005; open coast −0.174 [−0.379, −0.019] |
| rain on vs off | +0.0005 [−0.019, +0.033] on the marks; without rain FAR 0.084 → 0.035, CSI 0.785 → 0.798 |
| soil (`cnb` factor), arm − premier | 1.0: −0.022 [−0.046, −0.004], FAR 0.098, CSI 0.779; 2.38: +0.007 [+0.002, +0.011]. A trade-off; not re-run on this wave bed, so its effect at the lakes is unmeasured here |
| wave bed, this model vs the previous one | all marks 0.408 → 0.439, ΔRMSE +0.031 [−0.002, +0.075]; the 105 non-lake marks 0.261 → 0.259, ΔRMSE −0.003 [−0.009, +0.005] (§63 (g)) |
| buildings: bare wave bed; none in the flow either (this domain) | −0.000 [−0.004, +0.004]; −0.019 [−0.109, +0.049], and +0.027 [−0.001, +0.077] without the 6 noted marks. Masked CSI 0.8046, 0.8041, 0.8123 (premier, bare, none) |
| Arthur Kill sill carved, waves off (this domain) | 0.000: marks ≤ 3 mm, gauges ≤ 1 mm |
| Deal overtopping (this domain) | −0.022 [−0.059, +0.000]; without the lake marks −0.003 |
| Wreck Pond breach, 0 m / 1.65 m (this domain) | −0.043 [−0.144, +0.007] / −0.036 [−0.128, +0.016]; without the lake marks +0.001 / +0.000 |

## 7. Cost

| | |
|---|---|
| solve, 1.1.0 | 4.09 h (14,714 s) at 32 threads on `hal0383`, production engine; momentum 49.2 %, SnapWave 28.0 % of simulation time |
| solve, 1.0.0 | 12.99 h (46,766 s) at 16 threads on `emeraldrapids`; SnapWave 65.9 % and momentum 25.5 % of simulation time. Its waves-off twin 3.93 h. On that engine SnapWave's node sweep is SERIAL (§20), so more threads bought little |
| production engine for NEW runs (user 2026-11-02) | `bin:v2.3.3-winddir-igk-igseed-wmseed-swomp-2-gf11@dd78d82a`: this same run bit-identical in 5.44 h on 16 threads (SnapWave 1.44 h) and 2.51 h on 64 (0.72 h) (§20). 1.0.0 itself was solved on `…wmseed-1-gf11@e15ed916` and stays recorded that way |
| disk per run | `sfincs_map.nc` 10.5 GB, floodmap 0.79 GB, + ~5.6 GB hard-linked inputs; staging needs ~25 GB free |
| scoring memory | v4 validate ~200 G (3.125 m scoring bed); paired bootstrap ~85–90 G per process — run pairs serially |
| build | mesh freeze 4 h 39 / 72 GB; a subgrid rebuild ~6.8 h (24,605 s for this bed) |

## 8. Reproduce

1. **Environment:** `env/sfincs-linux-64.lock.txt` (explicit, md5, 2026-10-17) + `env/pip-extra.txt` (hydromt-sfincs
   editable at `d8514d64` + `quadtree_mixin_pad2.patch`). ⚠️ `hpc/environment.yml` (hydromt 1.3.1) disagrees with the lock (1.4.1): the lock wins.
2. **Engine:** §3. Jobs refuse to run unless exactly one of `SFINCS_BIN` / `SFINCS_SIF` is set.
3. **Data:** `data/data_catalog.yml` (+ per-folder `PROVENANCE.md`); bulk data on `/scratch` (not backed up; 90-day purge)
   with a desktop pull (`scripts/desktop_pull_backup.sh`). The frozen mesh, sealed template and bed are data, not rebuilt
   by one command; the `v4_refreeze` template carries hand steps (the meteo, an obs nudge, the Overpeck start; CLAUDE.md §5).
4. **Wave bed:** 1.1.0: `NJ_DOMAIN=v4_refreeze_swz_v11 python scripts/setup_face_z.py --from v4_refreeze_swz --bed
   _subgrid_v1_1c` (`logs/v1_1_premier_2026-11-06/README.md`). 1.0.0: `NJ_DOMAIN=v4_refreeze_swz python scripts/setup_face_z.py
   --from v4_refreeze --bed _subgrid_refreeze_lakes_min_creeks_cohansey`.
5. **Stage + run:** arm `p4-premier+weir-elizabeth-rahway`, commands in §9; staging copies the sealed template, checks the
   fingerprint on the copy, swaps in the bed and applies the arm. This run's job: `logs/v1_1_premier_2026-11-06/v11_premier.slurm`
   (`WEIRS=levees`); 1.0.0's: `logs/snapwave_bed_2026-10-28/swz_test.slurm`. 🔴 Staging (and
   `--no-run`, `--inputs-only`) deletes an existing run dir of that name; only `--check` is read-only.
6. **Check:** the audit in §1; `restart_history.txt` must show no resume. Same engine and inputs should repeat bit for bit (§5).

## 9. Starting a new experiment from the premier

An arm is a delta of the premier in the registry. For 1.1.0, add it to the `"v4_refreeze_swz_v11"` block of
`nj_sfincs/experiments.py` (built on that domain's `p4-premier+weir-elizabeth-rahway`) and run with
`NJ_DOMAIN=v4_refreeze_swz_v11`; for 1.0.0, define it in `_V4_REFREEZE` with `_p4_arm(name, description, **changes)`
and add its name to `EXPERIMENTS_BY_DOMAIN["v4_refreeze_swz"]`. Changeable fields:
`Experiment`, `nj_sfincs/config.py`. Name it the premier + `wave-` / `tide-` / `solver-` / `mask-` / `bed-` deltas, unions
joined by `+` in alphabetical order, `BRACKET+` for a deliberately inadmissible bound (CLAUDE.md §6).
- A **mask or boundary-depth** change is a new DOMAIN, not an arm (CLAUDE.md §2).
- A **bed or roughness** change needs a new `_subgrid_*` (`scripts/rebuild_subgrid.py --overlay`). With
  waves on, a bed change also needs a new face `z`, and so a new domain (`scripts/setup_face_z.py`, §63 (f)).
- A **discharge or template-file** change reaches no run until the template is re-staged (CLAUDE.md §5).

```bash
export PATH=$HOME/nj_sandy_sfincs/micromamba/envs/sfincs/bin:$PATH PYTHONPATH=$PWD NJ_DOMAIN=v4_refreeze_swz
python run_experiments.py --experiments <arm> --check            # the ONLY read-only mode
SFINCS_BIN=<seeded engine> python run_experiments.py --experiments <arm> --slurm \
    --slurm-args "--time=20:00:00 --constraint=emeraldrapids"
python -m nj_sfincs.premier                                      # wait for "output WHOLE"
python run_experiments.py --experiments <arm> --validate-only
python scripts/paired_hwm_bootstrap.py …                         # vs the premier, paired
```

## 10. Data sources and attribution

Licences are **not recorded in the repo** (only the unused Microsoft footprints carry ODbL); the
terms column is the publisher's general policy and must be checked before publication.

| data | publisher | used for | terms (verify) |
|---|---|---|---|
| NACCS / CHS storm 001 | USACE ERDC (Coastal Hazards System) | storm tide boundary, wind | US federal |
| ERA5 single levels | ECMWF / Copernicus C3S (doi 10.24381/cds.adbb2d47) | wind background, pressure | Copernicus licence, attribution required |
| USGS daily discharge; STN HWMs + storm-tide sensors; tidal gauges; 3DEP; CoNED | USGS | rivers, validation, bed | US federal |
| CO-OPS water levels; CUDEM; NOS surveys / ENC; crowdsourced bathymetry (CSB); CORA SWAN (`noaa-nos-cora-pds`); AORC v1.1 | NOAA | validation, bed, wave boundary, rain | US federal (CSB: per contributor) |
| eHydro surveys; 2010 NCMP lidar; National Levee Database | USACE | bed, weirs | US federal |
| NLCD 2012 (USGS / MRLC); SSURGO (USDA NRCS); NHD (USGS) | as listed | roughness, CN, ksat, lakes | US federal |
| NJ 10 ft lidar DEM; building footprints | NJ OGIS / NJDEP | bed, buildings | NJ terms |
| GMRT | Lamont-Doherty (IEDA) | deep bed fallback | CC BY 4.0 |
| MOTF extent | FEMA (via Rutgers) | extent validation | US federal |

**Still to pin for a citable release:** the NACCS / CHS release version, the CORA product version,
the NLD access date, the HWM pull date, and the NJ 10 ft DEM vintage (the catalog says both 2021 and
2014–2019). ⚠️ This run's `provenance.txt` still carries older forcing labels (`cora_waves_nj`, `precip/aorc_sandy_nj.nc`,
wind `data/wind_v4/naccs_blend`): trust `sfincs.inp`, the arm and the forcing files' own attributes.
