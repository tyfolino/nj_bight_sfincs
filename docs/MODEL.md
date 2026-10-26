# MODEL — the v4 premier (model card)

**DRAFT 2026-10-26.** Describes the Phase 4 candidate `p4-premier` on `v4_refreeze` (job 63094139,
STATUS "Phase 4"). After the Phase 4 read the winner is renamed into place as `naccs-premier` and the
user tags the commit. Every `⟨P4⟩` is a number that only the Phase 4 read can supply. Evidence lives in
[FINDINGS.md](FINDINGS.md) (cited as §n, or "part 4 (x)" for the v4 design record); this card
states what the model IS, not how it got there.

**What it is.** A SFINCS (v2.3.3, patched) compound-flood hindcast of Hurricane Sandy, 28–31 Oct
2012, on the New Jersey coast from Cape May to the Narrows plus Delaware Bay and the tidal Delaware,
the Raritan, Newark Bay and the Arthur Kill, with the far banks (DE / PA / Staten Island) computed.
Compound = NACCS storm tide at a drawn sea boundary + SnapWave waves with a wavemaker (IG in the
water) + wind + pressure + rain with curve-number infiltration + 61 river inflows, together in one
run. Validated against USGS high-water marks, NOAA / USGS gauges and the FEMA MOTF surge extent.

## 1. Identity

| | |
|---|---|
| domain | `v4_refreeze` — `faces=4881654 boundary_edges=4388 sha(z,mask)=378014e154b4ff41` (`nj_sfincs/premier.py`) |
| arm | `p4-premier` (`nj_sfincs/experiments.py`, `_p4`) → `naccs-premier` after the read |
| engine | `bin:v2.3.3-winddir-igk-igseed-wmseed-1-gf11`, upstream commit `091f531a` (tag v2.3.3) + 4 patches (§3); md5 `cbf497dc4a7683a261d8e2fb3ed75868`; written to each run's `engine.txt` |
| bed | `_subgrid_refreeze_lakes_min_creeks_cohansey` (built 2026-10-23; recipe in its `subgrid_provenance.txt`) |
| window | `tstart` 2012-10-28 00:00 → `tstop` 2012-10-31 00:00 (72 h), `tspinup` 3600 s |
| CRS / datum | EPSG:32618 (UTM 18N); elevations and water levels m NAVD88 |
| output | his 600 s (48 obs points + cross-sections), map 3600 s, `zsmax` every 21600 s, restart every 21600 s |

## 2. What is IN

### Domain and mesh
- **Ring:** `data/v4_design/region_v4_vertices.csv` (194 named vertices, edited by hand, checked by
  `scripts/audit_region_v4.py`); rule: contains the NACCS Sandy peak + 3 m, connected from the ocean
  (part 4). **Rivers cut at today's head of tide**; the Cohansey and Neshaminy keep the +3 m reach
  (A+, user 2026-10-05). Upriver of a cut is out of scope by design.
- **Sea boundary:** a DRAWN line through NACCS save points, Cape Henlopen → Brooklyn
  (`data/v4_design/waterlevel_line_v4.csv`, 99 vertices, 241 km, 7 arms + boxes at the Narrows, Kill
  van Kull east and the C&D canal). Landward of it the ring is active at any depth. Lower, Raritan and
  Sandy Hook Bays are COMPUTED — the founding structural argument (CLAUDE.md §1, FINDINGS part 2).
- **Quadtree** (4 levels, base 200 m, rotation 0.925°): 25 m 1.42 M faces, 50 m 2.25 M, 100 m 0.26 M,
  200 m 0.95 M (the Track C coarse shelf); 3.97 M active. 25 m within 50 m of every channel narrower
  than 50 m (`narrow_channels`, +254 k active). 16 subgrid pixels per cell, 10 levels.
- **Walls / leak closures:** 11 leak walls, the Cape Henlopen gap, the Lewes edge, Darby Creek,
  forced-line-end walls (`wall_outflow_near_forced_m` 500); the SLR gate (+0/+2/+3 m, rain off)
  wets no outflow edge cell (part 4 (g)).

### Bed (one source hierarchy for every channel, user 2026-10-05)
Base merge, top tier wins: USACE eHydro channel surveys (7 sets) → river beds → 2010 USACE NCMP
topobathy lidar → USGS CoNED (SW Raritan) → NOAA CUDEM 1/9″ (NJ, Delaware) → NJ 10 ft lidar DEM →
CUDEM 1/3″ → USGS 3DEP (PA/DE/NY land) → GMRT. Then overlays, painted in order: buildings → inland
lakes (85 lakes + 2 rivers) → USACE "unpave" (2010-lidar sills undone, ocean side and back bays) →
harbour + Raritan-corner eHydro → Sayreville → Little Egg channel → **`riverbeds_hierarchy_v4c`**
(eHydro → CUDEM where it is a real bed → NOS / ENC soundings → a shaped sloping section to 1.2 m
below MLLW at the head of tide; on the Cohansey also tide-reduced crowdsourced soundings + NOS
D00081) → `lake_fix_v4` and the creek beds, both LOWER-ONLY (`:min`). §54, part 4 (h).
- **Buildings:** NJDEP footprints burned at ground + 10 m (subgrid porosity, §55: for Sandy they
  barely matter).
- **Assumed beds, flagged:** the creek beds sit at ≈ MLW where no survey exists (Salem River and
  Mannington Creek left out); the Sluice Creek pool is painted at −0.24 m; the Cohansey above 3.6 km
  is still a slope guess (STATUS).

### Forcing and physics

| process | how | source |
|---|---|---|
| storm tide | NACCS / CHS ADCIRC+STWAVE storm 001, 241 support points, 15-min, at the drawn line (`netbndbzsbzifile`); INCLUDES offshore wave setup, nested one-way (§22–23) | `naccs_sandy_v4`, part 3 |
| wind | NACCS save-point wind (1,901 points) blended into ERA5, 500 m grid, 30 min, 15 km taper (`netamuv`); drag `cdnrb` 3, `cdwnd` 0/28/50 m/s → `cdval` 0.001/0.0025/0.0025 | `data/wind_v4/naccs_blend_p_era5/`, part 4 (g) |
| pressure | ERA5 inside the blend (`netamp`, `baro` 1) | same |
| rain | NOAA AORC v1.1 hourly, 1 km (`netampr`) | `aorc_sandy_v4` |
| infiltration | `cnb` (curve number with recovery), AMC factor 1.5; CN from NLCD 2012 × SSURGO HSG (water CN 100), ksat from SSURGO surface horizon; 1,992,347 of 3,965,303 active points infiltrate | `cn_v4`, `ksat_v4_refreeze`, §59 |
| rivers | 61 inflows, USGS daily mean discharge (approved), area-scaled, placed in their channels (12 moved 10-15; 0 of 193 marks within 500 m of a source) | `usgs_sandy_discharge_v4_refreeze`, §40 |
| waves | SnapWave: 5° bins over 360°, updated hourly (`dtwave` 3600, §61), wind growth on, `gamma` 0.78, `fw` 0.01 (§56), `niter` 200; boundary = NOAA CORA SWAN at 69 support points (§21); SnapWave domain `v4_shelf_steps` | `data/waves_v4/cora_waves_v4.nc` |
| infragravity | `snapwave_igwaves` 1 **and** a wavemaker line (`wvmfile`, 8 pieces, 157.7 km, snapped seaward of the beach) — IG is IN THE WATER, unlike every earlier premier (§45, §62) | `data/wavemakers_v4/v4_wavemaker_5m_mhw_snapbeach.geojson` |
| structures | 7 weirs, 412 engine points: Keansburg levee system on the USACE NLD centreline (Waackaack gate, Thornes reach, west tie, bayfront dune), the Pews levee gap closed, Overpeck tidal dam + bypass sill. Assumed: stop logs in, gates held (§38) | `data/structures_v4/sfincs.weir` |
| roughness | Manning from NLCD 2012 (`NLCD_CONUS_mapping.csv`); `manning_water_v4` overlay: 0.02 on lakes / non-tidal rivers, marsh n kept on tidal water | `nlcd_2012_v4` |
| start | `zsini` 0 + a binary regional start (`sfincs_ini_regional.bin`: the Overpeck pool), §51 | template |
| flow | advection, Coriolis (lat 39.86), viscosity 0.01, `alpha` 0.5, `huthresh` 0.01, `rhoa` 1.25, `rhow` 1024 | `sfincs.inp` |

## 3. Engine

Upstream SFINCS v2.3.3 ("Faber"), built natively with `hpc/build_sfincs_native.sh` (host gfortran
11.5, `-fopenmp -O3 -fallow-argument-mismatch -w`, OpenACC off), with four patches
(`hpc/patches/snapwave_igseed_wmseed_v2.3.3.patch` carries all four):

| patch | fixes | § |
|---|---|---|
| `nj-winddir-fix-1` | with `snapwave_wind = 1` the boundary spectrum was rotated to the domain-mean WIND direction (matched the imposed direction 0 of 73 h, worst 170°); spectra now built after the final theta grid, centred on the imposed mean direction. No-op with wind off | §43 |
| `nj-igk-fix-1` | v2.4.0 backports: IG wavenumber from `sigm_ig`; `wavemaker_angfac = max(−sin φ, 0)` (unpatched v2.3.3 injects nothing for a line with land on the right) | §47, §49 |
| `nj-igseed-1` | the Herbers IG draw used unseeded `RANDOM_NUMBER`: IG-on runs never repeated. Fixed seed, re-set every call | §44 (a)–(d) |
| `nj-wmseed-1` | fixed seed for the wavemaker phases + phase in closed form from model time (real*8), so a resume sees the same IG forcing | §44 (j) |

v2.4.x (Galibier) was gated and refused (§47). Upstream: issue #362 / PR #363 (wind direction) open,
unreviewed; Deltares PR #371 includes the #363 fix. **Not yet filed:** the IG seed issue (draft
`docs/upstream/snapwave_igseed_issue.md`), the wavemaker phase fix, the dead-corner rule (§52), the
wavemaker IG frequency shift (`dphi = 2π·1e-6/f`). The run reads a patched hydromt-sfincs too
(`hpc/patches/quadtree_mixin_pad2.patch`, one-cell sliver padding).

## 4. What is OUT (or crude)

| not represented | what it costs | evidence |
|---|---|---|
| **morphology: dune erosion, breaching, overwash** (fixed bed) | Wreck Pond (6130) and Deal Lake (6122) read −2.34 / −2.37 m: in Sandy the dune breached at Wreck Pond and the sea overwashed into Deal Lake; in the model the sea never enters either (lowest connections 2.82 / 3.11 m vs a local sea peak 2.78–2.80 m). The breach arms bracket it as an upper bound; the post-Sandy dune bed (`bed-postsandy`) is deferred by the user | part 4 (h), §49, Closed |
| **wave run-up, splash, overtopping** (still-water model) | marks 6121 / 6398 / 6188 are upper bounds the model cannot reach; offline EurOtop overtopping fills Deal Lake 0.29 of the 1.78 Mm³ needed — "the reach is there, the volume is not" (`src-deal-overtop` arm) | part 4 (h) |
| **storm drains, outfalls, culverts** | closed-basin lakes fill by rain and drain nowhere; infiltration acts on rain, never on standing water | §59, part 4 (h) |
| **structure failure** | weirs hold all run; the Keansburg pocket is watertight and fills by rain only (6133 / 6155 / 6156 noted `leak`, they do not test the levees) | §38 |
| **wave diffraction; per-point boundary direction** | SnapWave v2.3.3 has neither: one mean boundary direction per call collapses CORA's alongshore spread; bays sit 0.24–0.69 m under CORA's SWAN at the peak | §43, §48 |
| **rivers above today's head of tide** | out by design (A+); no measured bed exists above the Trenton falls | part 4 |
| **bay-scale wind** | no gridded product resolves the bays | part 4 (e) |

Literature for the coupling route (`reports/literature_review_2026-10.md`): Leijnse et al. 2025
(Coastal Eng. 199, 104726; SFINCS vs XBeach-SurfBeat), Barnard et al. 2019 (Sci. Rep. 9, 4309; CoSMoS
XBeach profiles), Storlazzi et al. 2024 (USGS DR 1184), McCall et al. 2024 (BEWARE-2, NHESS 24, 3597);
breaching: Hegermiller et al. 2022 (JGR-ES; COAWST, Sandy at Fire Island), Jeffries et al. 2025 (NHESS
25, 3125); back bays: Defne, Ganju & Moriarty 2019 (JGR Oceans; Barnegat Bay); overwash: Bennett et
al. 2018, Kobayashi & Zhu 2017. No published COAWST study of the Mantoloking breach was found.

## 5. Behaviours a user must know

- **A resumed run is not the run.** A restart file holds `zs`, `q` and the boundary `uvmean` only.
  Waves-on: SnapWave starts cold, so a resume differs (v4 calm window: up to 1.99 m at
  `sss_narrows_si`) — read it against an uninterrupted twin or re-run (§44 (j)). Rain-on with `cna`:
  the soil restarts empty (`cnb`'s state survives, §59). Check `restart_history.txt` before pairing.
- **Waves-on runs carry a noise band.** Seeded runs repeat bit for bit, but a null input change
  (`rhoa` × 1.00008) moves 7 of 48 points > 10 cm within 6 h; waves-off zsmax p99 0.18 mm. The band
  through the peak is ⟨P4⟩ (the two `rhoa` null copies). A waves-on arm Δ of a few cm in the bays is
  inside it (§44 (e)); the NY-bay crest also carries a ±0.1–0.15 m seiche phase (§61 (g)).
- **Rain ponding depends on the window.** Closed coastal lakes still rise at `tstop`; a later stop
  scores them higher (part 4 (g)). `--tstop` cannot run on a sealed template — use
  `scripts/engine_gate.py make … --hours H`.
- **Meteo files are in the engine's corner convention** (`nj_sfincs/meteo_grid.py`); reading one
  with `xr.interp` is half a cell off — use `meteo_grid.true_centres` (part 4 (e)).
- **Maps:** "flood depth" is water above the PIXEL ground on normally-dry land only; peak water
  level (`zsmax`) is a separate map (CLAUDE.md §6). The floodmap bleeds onto inactive ground — screen
  with `validate.simulated_mask` (§37).

## 6. Validation (what is scored, and how)

Scores go to `experiments/v4_refreeze/metrics.csv`; every row carries `engine`, `engine_seed`,
`meteo`, `infiltration`, `subgrid`. Arms are compared PAIRED (`scripts/paired_hwm_bootstrap.py`).

| target | scored as | p4-premier |
|---|---|---|
| USGS HWMs (STN event 24) | RMSE / bias, **median estimator, 50 m radius** (`_scored` keys), n 110; noted marks (run-up, `leak`, questioned) drawn hollow, `hwm_*_scored_excl_noted` beside the headline | ⟨P4⟩ |
| NOAA CO-OPS gauges (6-min), USGS tidal gauges, STN storm-tide sensors | peak error, timing; published crests where USGS's archive has the storm-day hole (`peak_err_pub_*`, §60 (f)); Great Kills corrected −0.34 m (§50) | ⟨P4⟩ |
| FEMA MOTF extent (NJ only) | CSI / POD / FAR inside the validity mask; quote `motf_km2_excluded_boxes` (incl. `salem_marshes`, 418 km²) beside any CSI | ⟨P4⟩ |
| uncertainty | bootstrap CIs (B 200 000), noise band, infiltration bracket (`cnb` 1.0 / 2.38), breach bracket, rain-off split | ⟨P4⟩ |

For reference, the premier it replaces (10-11, unseeded engine, no wavemaker): RMSE 0.436 / bias
−0.110 (median, 50 m, n 110), CSI 0.780; without 6122 and 6130 0.301 (n 108) — part 4 (h).

## 7. Cost

| | |
|---|---|
| solve | v4 waves-on ≈ 10.1 h at 64 threads (62328438), ≈ 13 h at 16 threads (4 per node); waves-off 2.2 h. SnapWave is ~97 % of a waves-on solve and its node sweep is SERIAL (64-thread solves use ~6 effective cores, §20). Seeded premier: ⟨P4⟩ |
| nodes | `emeraldrapids` for waves-on (CLAUDE.md §5: ~3× the pace of `icelake`); exclude `halk*` |
| disk per run | ~10.9 GB unique (`sfincs_map.nc` 9.75 GB, floodmap 0.80 GB) + ~5.6 GB hard-linked inputs; staging needs ~25 GB free |
| scoring memory | v4 validate ~200 G (3.125 m scoring bed); paired bootstrap ~85–90 G per process — run pairs serially |
| build | mesh freeze 4 h 39 / 72 GB; a subgrid rebuild ~6.8 h (24,605 s for this bed) |

## 8. Reproduce

1. **Environment:** `env/sfincs-linux-64.lock.txt` (explicit, md5, 2026-10-17) + `env/pip-extra.txt`
   (hydromt-sfincs editable at `d8514d64` + `quadtree_mixin_pad2.patch`). ⚠️ `hpc/environment.yml`
   (hydromt 1.3.1) disagrees with the lock — the lock wins.
2. **Engine:** `hpc/build_sfincs_native.sh <variant>` + `hpc/patches/`; check `BUILD_INFO` against
   the md5 in §1. Jobs refuse to run unless exactly one of `SFINCS_BIN` / `SFINCS_SIF` is set.
3. **Data:** `data/data_catalog.yml` (+ per-folder `PROVENANCE.md`); bulk data on `/scratch` (not
   backed up; 90-day purge) with a desktop pull (`scripts/desktop_pull_backup.sh`).
4. **Stage + run:** `NJ_DOMAIN=v4_refreeze`; staging copies the sealed template, checks the
   fingerprint on the copy, swaps in the bed and applies the arm. Commands in §9.
5. **Check:** `python -m nj_sfincs.premier` (fingerprint + `output WHOLE`) before reading anything.

## 9. Starting a new experiment from the premier

An arm is a delta of the premier in the registry (`EXPERIMENTS_BY_DOMAIN["v4_refreeze"]`):

```python
"p4-premier+wave-nowavemaker": _p4_arm(
    "p4-premier+wave-nowavemaker", "what it changes and what it pairs with",
    waves=replace(_P4_WAVES, wavemaker=False),
),
```

Fields an arm may change (`Experiment`, `nj_sfincs/config.py`): `waves`, `subgrid_from`, `meteo_from`,
`rain`, `infiltration`, `cnb_effective`, `extra_discharge`, `rhoa`, `wind_scale`,
`sea_level_offset_m`, `waterlevel_geodataset`, `n_waterlevel_support`, `bracket`. Name it the
premier + `wave-` / `tide-` / `solver-` / `mask-` / `bed-` deltas, unions joined by `+` in
alphabetical order, `BRACKET+` for a deliberately inadmissible bound (CLAUDE.md §6).
- A **mask or boundary-depth** change is a new DOMAIN, not an arm (CLAUDE.md §2).
- A **bed or roughness** change needs a new `_subgrid_*` (`scripts/rebuild_subgrid.py --overlay`).
- A **discharge or template-file** change reaches no run until the template is re-staged (CLAUDE.md §5).

```bash
export PATH=$HOME/nj_sandy_sfincs/micromamba/envs/sfincs/bin:$PATH PYTHONPATH=$PWD NJ_DOMAIN=v4_refreeze
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
| CORA SWAN waves | NOAA NOS (`noaa-nos-cora-pds`) | wave boundary | US federal |
| AORC v1.1 | NOAA NWS / OWP | rain | US federal |
| USGS daily discharge; STN HWMs + storm-tide sensors; tidal gauges; 3DEP; CoNED | USGS | rivers, validation, bed | US federal |
| CO-OPS water levels; CUDEM; NOS surveys / ENC; crowdsourced bathymetry (CSB) | NOAA | validation, bed | US federal (CSB: per contributor) |
| eHydro surveys; 2010 NCMP lidar; National Levee Database | USACE | bed, weirs | US federal |
| NLCD 2012 | USGS / MRLC | roughness, CN | US federal |
| SSURGO | USDA NRCS | CN, ksat | US federal |
| NHD | USGS | lakes, water roughness | US federal |
| NJ 10 ft lidar DEM; building footprints | NJ OGIS / NJDEP | bed, buildings | NJ terms |
| GMRT | Lamont-Doherty (IEDA) | deep bed fallback | CC BY 4.0 |
| MOTF extent | FEMA (via Rutgers) | extent validation | US federal |

**Still to pin for a citable release:** the NACCS / CHS release version, the CORA product version,
the NLD access date, the HWM pull date, and the NJ 10 ft DEM vintage (the catalog says both 2021 and
2014–2019). ⚠️ `nj_sfincs/provenance.py` still labels v4 forcing with v3 names (`cora_waves_nj`,
`era5_nj`, `aorc_sandy_nj`, water level `gtsm/noaa_sandy_nj.nc`): trust `sfincs.inp` and the arm,
not those labels, until it is fixed.
