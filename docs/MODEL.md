# MODEL — the v4 premier (model card)

**DRAFT 2026-10-30. Version / tag: `[VERSION — placeholder, set at tagging]`.** Describes arm
`p4-premier` on domain `v4_refreeze_swz` as run (job 63181564). Evidence lives in
[FINDINGS.md](FINDINGS.md) (cited as §n, or "part 4 (x)" for the v4 design record); this card
states what the model IS, not how it got there.

**Two open reads.** `[PENDING swz_bare]` marks anything that changes if SnapWave's bed changes (a
bare-ground wave bed is being run). `[PENDING swz_band]` marks anything that depends on the noise
band and the lake side arms, still scoring on this domain. Neither set has been read for this card.

**What it is.** A SFINCS (v2.3.3, patched) compound-flood hindcast of Hurricane Sandy, 28–31 Oct
2012, on the New Jersey coast from Cape May to the Narrows plus Delaware Bay and the tidal Delaware,
the Raritan, Newark Bay and the Arthur Kill, with the far banks (DE / PA / Staten Island) computed.
Compound = NACCS storm tide at a drawn sea boundary + SnapWave waves with a wavemaker (IG in the
water) + wind + pressure + rain with curve-number infiltration + 61 river inflows, together in one
run. Validated against USGS high-water marks, NOAA / USGS gauges and the FEMA MOTF surge extent.

## 1. Identity

| | |
|---|---|
| domain | `v4_refreeze_swz` — `faces=4881654 boundary_edges=4388 sha(z,mask)=90cc7468614a5814` (`nj_sfincs/premier.py`) `[PENDING swz_bare]` |
| arm | `p4-premier` (`nj_sfincs/experiments.py`, `_p4`), the name it was run and scored under. `premier.PREMIER_NAME` still reads `naccs-premier` until the tagging step moves it, so the audit's `PREMIER =` line does not name this arm yet |
| engine | `bin:v2.3.3-winddir-igk-igseed-wmseed-1-gf11@e15ed916`, upstream commit `091f531a` (tag v2.3.3) + 4 patches (§3); sha256 `e15ed9161a499960017bc8b3a44d41c1a05d123d429e8f4e93ba67bdfdb8a248`, md5 `cbf497dc4a7683a261d8e2fb3ed75868`; written to each run's `engine.txt` |
| flow bed | `_subgrid_refreeze_lakes_min_creeks_cohansey` (built 2026-10-23; recipe in its `subgrid_provenance.txt`; `metrics.csv` label `…@34ba916d`) |
| wave bed | mesh face `z` = the flow bed's subgrid mean ground (§2) `[PENDING swz_bare]` |
| run | job 63181564, `hal0391` (`emeraldrapids`), 16 threads, `restart_count 0`: uninterrupted, seeded |
| window, CRS | `tstart` 2012-10-28 00:00 → `tstop` 2012-10-31 00:00 (72 h), `tspinup` 3600 s; EPSG:32618 (UTM 18N), elevations and water levels m NAVD88 |
| output | his 600 s (48 obs points + cross-sections), map 3600 s, `zsmax` every 21600 s, restart every 21600 s (the restart files are removed when a run finishes) |

**Verify the fingerprint** (reads `z` and `mask` from the run's `sfincs.nc`, checks obs points and output):

```bash
NJ_DOMAIN=v4_refreeze_swz python -m nj_sfincs.premier experiments/v4_refreeze_swz/p4-premier
# OK  experiments/v4_refreeze_swz/p4-premier  v4_refreeze_swz STAGED 2026-10-28 …  obs OK  output WHOLE
```

With no path it audits every run dir on the domain. Trust neither the name nor the counts: sibling domains on
this mesh share face and edge counts, and only the sha tells them apart. Read nothing before `output WHOLE`.

## 2. What is IN

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
- **Wave bed (SnapWave's bed)** `[PENDING swz_bare]`**:** SnapWave never reads the subgrid; its whole bed
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
| waves | SnapWave: 5° bins over 360°, updated hourly (`dtwave` 3600, §61), wind growth on, `gamma` 0.78, `alpha` 1, `fw` 0.01 (§56), `niter` 200; boundary = NOAA CORA SWAN at 69 support points (§21); SnapWave domain `v4_shelf_steps` (about 3.38 M active nodes), on the wave bed above `[PENDING swz_bare]` | `data/waves_v4/cora_waves_v4.nc` |
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

Check the sha256 in the `BUILD_INFO` beside the binary against §1; netCDF-C came from the `sfincs-build` env (4.10.1).
A different compiler or library gives a different binary, a new engine label: re-baseline.

Upstream: the wind-direction bug (issue #362) is fixed in Deltares PR #371 (merged 2026-10-08). **Not yet filed:** the
IG seed + wavemaker phase issue and the wavemaker IG frequency shift (drafts in `docs/upstream/`), the dead-corner rule
(§52). The run also reads a patched hydromt-sfincs (`hpc/patches/quadtree_mixin_pad2.patch`, one-cell sliver padding).

## 4. Known limits, and what is OUT

Mark residuals here are model − observed, **median estimator, 50 m radius**; `metrics.csv` or §63 (g).

- **Monmouth coastal lakes.** The five `lake_outlet_blocked` marks read 6121 −2.03, 6122 −2.27, 6124 −0.69, 6129 −0.05,
  6130 −2.09 m and set the headline RMSE (§6) `[PENDING swz_bare]` `[PENDING swz_band]`. Do not use these lakes' peaks.
- **Delaware: low water, and few marks.** The storm low misses by −0.36 m at Lewes, −0.6…−0.7 m Ship John → Philadelphia,
  −0.7…−1.0 m at Newbold (rough high/low pick on the previous wave bed). At the mouth it is the NACCS forcing; the growth
  upriver is unexplained. Peaks are better (§6), bar the Christina gauges (−0.80 m Newport, −0.54 m Wilmington).
  Only 3 marks are scored in the Delaware basins (2 river, 1 NJ bay shore).
- **Cape May back bays.** Bias −0.288, RMSE 0.317 m (median, 50 m, n 4) `[PENDING swz_bare]`; published-crest gauge errors −0.305 m
  Sea Isle, −0.252 m Stone Harbor, −0.190 m Avalon. Open (§57).
- **Inflow pile-ups on coarse faces.** Ridley, Chester, Frankford, Red Clay, White Clay, Christina and **Salem R. at
  Woodstown** (peak / bed 4.38 / 0.01 m) enter on 100–200 m faces and stand metres above a ~0 m bed (measured on an
  earlier configuration of this mesh, not re-read on this run). Do not read depths there; the fix needs a new mesh.
- **Building cap under sea-level rise.** A ground + 4 m cap is overtopped at +3 m SLR (4.6 % of in-model buildings stood
  in deeper water), hence this bed's ground + 10 m. Overtopping of the 10 m burn is uncounted; check before SLR use.
- **Hudson waterfront and Upper Bay shore: NOT in the model.** Hoboken, east Jersey City (Exchange Place, Liberty State
  Park) and Bayonne's Upper Bay side are outside the active mask (`mask` 0, nearest active face ~1–3.6 km; confirmed
  2026-10-30). Blank there means not computed, never dry. Interior Bayonne and its Newark Bay side are active.
- **A resumed run is a different run** (§5). This run was not resumed; read one that is against an uninterrupted twin.

| not represented | what it costs | evidence |
|---|---|---|
| **morphology: dune erosion, breaching, overwash** (fixed bed) | In Sandy the dune breached at Wreck Pond and the sea overwashed into Deal Lake; in the model the sea does not get in (lowest connections 2.82 / 3.11 m vs a local sea peak 2.78–2.80 m; traced on the earlier unseeded configuration, part 4 (h)). What the breach arms say on this wave bed is `[PENDING swz_band]`; the post-Sandy dune bed (`bed-postsandy`) is deferred by the user | part 4 (h), §49, Closed |
| **wave run-up, splash, overtopping** (still-water model) | marks 6121 / 6398 / 6188 are upper bounds the model cannot reach; offline EurOtop overtopping fills Deal Lake 0.29 of the 1.78 Mm³ needed — "the reach is there, the volume is not" (wave input from the earlier unseeded configuration; the `src-deal-overtop` arm on this wave bed is `[PENDING swz_band]`) | part 4 (h) |
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
- **Waves-on runs carry a noise band.** Seeded runs repeat bit for bit (§44 (d); this domain's repeat check
  `[PENDING swz_band]`), but a null input change (`rhoa` × 1.00008) moves 7 of 48 points > 10 cm within 6 h; waves-off zsmax
  p99 0.18 mm. Through the peak, on the previous wave bed (two `rhoa` null copies, §44 (e)) `[PENDING swz_band]`: gauge peak
  band median 1.4 cm, max 9.5 cm (Lower Bay / Raritan / Sandy Hook 6–9 cm, Delaware 2–6 cm, open coast and NJ back bays
  ≤ 2 mm); a NY-bay mark shift under ~8 cm is noise; face `zsmax` p05–p95 band 0.081 m; whole series up to 0.3 m mid-storm.
  The NY-bay crest also carries a ±0.1–0.15 m seiche phase (§61 (g)). A capped SnapWave call can put a pulse into the
  Delaware River (§44 (h)): 26 of 73 calls capped on the previous wave bed, not recounted here.
- **Rain ponding depends on the window.** Closed coastal lakes still rise at `tstop`; a later stop scores them higher
  (part 4 (g)). `--tstop` cannot run on a sealed template: use `scripts/engine_gate.py make … --hours H`.
- **Meteo files are in the engine's corner convention** (`nj_sfincs/meteo_grid.py`); reading one
  with `xr.interp` is half a cell off — use `meteo_grid.true_centres` (part 4 (e)).
- **Maps:** "flood depth" is water above the PIXEL ground on normally-dry land only; peak water level (`zsmax`) is a
  separate map (CLAUDE.md §6). The floodmap bleeds onto inactive ground: screen with `validate.simulated_mask` (§37).

## 6. Validation (what is scored, and how)

Scores go to `experiments/v4_refreeze_swz/metrics.csv`; every row carries `engine`, `engine_seed`,
`meteo`, `infiltration`, `subgrid`. Arms are compared PAIRED (`scripts/paired_hwm_bootstrap.py`).
Every number in this table depends on the wave bed: `[PENDING swz_bare]`.

| target | scored as | p4-premier |
|---|---|---|
| USGS HWMs (STN event 24), all | RMSE / bias, **median estimator, 50 m radius** (`_scored` keys) | RMSE 0.439, bias −0.128 m, n 110, 1 dry, 91.8 % within ±0.5 m |
| HWMs without the 5 `lake_outlet_blocked` marks | same estimator and radius (`_excl_lake_blocked`) | RMSE 0.259, bias −0.066 m, n 105, 95.2 % within ±0.5 m |
| HWMs without the 6 noted marks (6121, 6155, 6169, 6188, 6202, 6398: run-up, `leak`, questioned; drawn hollow) | same estimator and radius (`_excl_noted`) | RMSE 0.354, bias −0.093 m, n 104, 97.1 % within ±0.5 m |
| NOAA CO-OPS gauges (6-min) | peak error, m | Atlantic City +0.494 (the NACCS forcing, local to there; part 4 (h)), Cape May −0.101, Lewes −0.191, Ship John −0.068, Reedy Point −0.110, Delaware City −0.189, Marcus Hook −0.142, Philadelphia −0.120, Burlington −0.116, Newbold −0.138; Sandy Hook −0.321 before the gauge failed |
| all 27 gauges with a full peak record (NOAA, USGS tidal, STN storm-tide sensors) | peak error; Great Kills corrected −0.34 m (§50); other gauges use published crests where USGS's archive has the storm-day hole (`peak_err_pub_*`, §60 (f)) | median \|error\| 0.110 m, median −0.068 m |
| FEMA MOTF extent (NJ only) | CSI / POD / FAR inside the validity mask, footprints not masked (§55) | CSI 0.784, POD 0.846, FAR 0.086; `motf_km2_excluded_boxes` 2,412.8 km² (incl. `salem_marshes`, 418 km²); false alarms 39.8 km² connected, 70.6 km² disconnected |

**Sensitivities** (ΔRMSE of `p4-premier` − the arm, median, 50 m, n 110, paired, B 200 000, 95 % CI;
part 4 (i)). Measured on the previous wave bed unless marked; non-lake effects should carry over.

| what | result |
|---|---|
| waves on vs off | −0.150 [−0.244, −0.070]; marks rise +0.32 m open coast, +0.20 NJ back bays, +0.19 inlets, +0.13 NY bays, +0.06 rivers. This domain, unpaired: RMSE 0.558 waves-off → 0.439 `[PENDING swz_bare]` |
| wavemaker on vs off | −0.108 [−0.193, −0.022], nearly all at the lake marks; open-coast median +0.02 m `[PENDING swz_band]` |
| rain on vs off | +0.0005 [−0.019, +0.033] on the marks; without rain FAR 0.084 → 0.035, CSI 0.785 → 0.798 |
| soil (`cnb` factor), arm − premier | 1.0: −0.022 [−0.046, −0.004], FAR 0.098, CSI 0.779; 2.38: +0.007 [+0.002, +0.011]. A trade-off; the part at the lakes `[PENDING swz_band]` |
| wave bed, this model vs the previous one | all marks 0.408 → 0.439, ΔRMSE +0.031 [−0.002, +0.075]; the 105 non-lake marks 0.261 → 0.259, ΔRMSE −0.003 [−0.009, +0.005] (§63 (g)) `[PENDING swz_bare]` |
| breach bracket | on this wave bed `[PENDING swz_band]` |

## 7. Cost

| | |
|---|---|
| solve | this run 12.99 h (46,766 s) at 16 threads on `emeraldrapids`; SnapWave 65.9 % and momentum 25.5 % of simulation time. Its waves-off twin 3.93 h. SnapWave's node sweep is SERIAL (§20), so more threads buy little |
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
4. **Wave bed** `[PENDING swz_bare]`**:** `NJ_DOMAIN=v4_refreeze_swz python scripts/setup_face_z.py --from v4_refreeze --bed
   _subgrid_refreeze_lakes_min_creeks_cohansey` writes this domain's template and bed from `v4_refreeze`'s.
5. **Stage + run:** arm `p4-premier`, commands in §9; staging copies the sealed template, checks the fingerprint on the copy,
   swaps in the bed and applies the arm. This run's job: `logs/snapwave_bed_2026-10-28/swz_test.slurm`. 🔴 Staging (and
   `--no-run`, `--inputs-only`) deletes an existing run dir of that name; only `--check` is read-only.
6. **Check:** the audit in §1; `restart_history.txt` must show no resume. Same engine and inputs should repeat bit for bit (§5).

## 9. Starting a new experiment from the premier

An arm is a delta of the premier in the registry: define it in `_V4_REFREEZE` with `_p4_arm(name, description, **changes)`,
then add its name to `EXPERIMENTS_BY_DOMAIN["v4_refreeze_swz"]`, which selects arms from `_V4_REFREEZE`. Changeable fields:
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
