# Tide twins at the 2025 NJ STAP central projections, 2026-11-15

**Why (user 11-15):** the poster's + 2 / + 4 ft (MHHW 1983–2001 + 0.61 / 1.22 m) are conventional planning levels;
the user asked where they sit in the 2025 NJ projections and chose to add runs at the STAP **central** values for
2050 and 2100 (intermediate emissions). Poster: keep the feet, add STAP context (`reports/poster_2026-11-13/build_v11.py`).

**Source:** Kopp et al. (2025), *New Jersey's Rising Seas and Changing Coastal Storms: Report of the 2025 STAP*
(Rutgers / NJDEP). Text extract: `logs/poster_audit_2026-11-15/stap2025_report_text.txt`. Projections are 19-yr
means, above the **1995–2014 mean ("2005")**. Atlantic City is the representative NJ station.

| case | STAP Table B2 (Atlantic City, m above 2005) | + NTDE → STAP baseline (Table 4, 0.059 m) | boundary offset on p000 | tag |
|---|---|---|---|---|
| 2050 central, all scenarios ("~50 % chance exceeds") | 0.40 | 0.459 | **+0.459 m** | `p046_stap2050` |
| 2100 central, intermediate (SSP2-4.5) | 0.88 | 0.939 | **+0.939 m** | `p094_stap2100` |

Uniform offset, like p061 / p122 (the other stations' central values differ by ≤ ~0.03 m; NTDE→STAP offsets 0.052–0.070 m).
Files: `make_tide_stap.py` → `/scratch/tpj8/nj_bight_sfincs_data/modern_2026/derived/tide/sfincs_netbndbzsbzifile_tide_ec2015_{p046_stap2050,p094_stap2100}.nc`
(checked: zs − p000 = offset everywhere; grid and times identical).

**Arms** (`nj_sfincs/experiments.py`, additive, swapped in atomically while J2 63919024 ran; every pre-existing arm's
`repr` byte-identical; v11 arms 22 → 24; registry tests 135 OK; `--check` 2/2 would stage):
`bed-modernb+tide-stap2050+weir-normalweather`, `bed-modernb+tide-stap2100ssp245+weir-normalweather` — the
`bed-modernb+tide-{2,4}ft+weir-normalweather` recipe (2026 bed, normal-weather weir, waves / wind / rain / rivers off,
EC2015 tide 10-12 → 11-13, 2.5 d spin-up) with only the boundary offset changed.

**Job 63941099** (`run_stap.slurm`, 2-task array, 64 cores each, 22 h limit): stage → checks → solve (~13 h) → weir
u/v = 862 → audit WHOLE → `mhhw_maps.py tide` (~45 min, products in `experiments/v4_refreeze_swz_v11/floodmaps/slr_stap/`)
→ `slr_assets.py` counts (mhh + max) into `logs/slr_assets_2026-11-13/results/v11modernb_stap{2050,2100ssp245}_*`.
EXPECT_MD5 guards only today's files (`md5_files.txt`: this script, `make_tide_stap.py`, `nj_sfincs/experiments.py`,
the two tide files, the weir, the engine pointer, `mhhw_maps.py`, `slr_assets.py`): 🔴 **do not edit
`nj_sfincs/experiments.py` (GATE 2's J3 arms) until both tasks have STARTED.** No dedupe in the job: run
`scripts/dedupe_experiment_inputs.py --apply` by hand afterwards.

**Where the existing runs sit** (from `logs/slr_assets_2026-11-13/README.md`): today ≈ 0.3 ft above 2005; + 2 ft run ≈
1.8 ft (the 2070 central estimate in every scenario); + 4 ft run ≈ 3.8 ft (top of the 2100 likely range, SSP2-4.5).

## Results (11-16)

**The runs.** Job 63941099 COMPLETED 11-16 ~06:00. Both tasks were preempted once and resumed from a restart file:

- **2050:** preempted 11-15 13:11, resumed from the 2012-10-15 12:00 restart.
- **2100:** preempted 14:13, resumed from the 2012-10-17 06:00 restart.

Both resumes fall inside the analysed month, after the 2.5 d spin-up. The 2100 resume is on the day of the month's spring-tide peak (10-17).

These runs have waves, rain and wind off. For such runs a resume is mm-level: the toy-model measurement in CLAUDE.md §4 is ≤ 0.2 mm (p90). The resumes are logged in each run dir's `restart_history.txt`. There is no uninterrupted twin to compare against.

One check was made on the stitched `sfincs_his.nc`. Across the 48 stations, the 10-min step at the seam is no larger than the steps around it:

- 2050: max |Δzs| 0.144 m across the seam, against 0.12–0.15 m for the neighbouring steps;
- 2100: 0.074 m, against 0.07–0.10 m.

The other checks also passed:

- the engine read 862 weir u/v (= expected);
- `premier` audit: `output WHOLE` for both (`job/audit_*.txt`).

**Engine:** `bin:v2.3.3-winddir-igk-igseed-wmseed-swomp-2-gf11@dd78d82a`.

**Bed and model.** The ground is today's (2026) estimate, `bed-modernb` (`_subgrid_modern2026b`). The domain is Model 1.1.0's `v4_refreeze_swz_v11`, with normal-weather structures (closures open, Overpeck dam shut). This is the same setup as the + 0 / + 2 / + 4 ft rows in `logs/slr_assets_2026-11-13/README.md`.

**Power sites.** These are NJ plants and substations with depth ≥ 0.15 m on any normally-dry part of the site, out of the 182 the model covers. "Typical high" is the mean higher-high: the mean of the tidal-day highs over the 28-day window. "Spring tide" is the month max: the 17 Oct 2012 new-moon spring tide. The read is `slr_assets.py`; its output is in `logs/slr_assets_2026-11-13/results/v11modernb_stap{2050,2100ssp245}_{mhh,max}_summary.{txt,json}` and agrees with the job `.out`.

| run (offset above 1983–2001 MHHW; ≈ above the STAP 2005 baseline) | typical high: touched / ≥ half wet | plants / substations (touched; ≥ half) | spring tide: touched / ≥ half wet | plants / substations (touched; ≥ half) |
|---|---|---|---|---|
| STAP 2050 central (+ 0.459 m; 1.3 ft) | **8 / 0** | 8 / 0; 0 / 0 | 11 / 0 | 9 / 2; 0 / 0 |
| STAP 2100 central, SSP2-4.5 (+ 0.939 m; 2.9 ft) | **17 / 1** | 14 / 3; 0 / 1 | 20 / 2 | 14 / 6; 0 / 2 |

**What is wet in 2050.** In 2050 every touched site is a sliver: at most 2.3 % of its land is wet (typical high ≤ 0.8 %). They are the same waterfront plants that + 2 ft touches: Linden Solar + Gen, Sayreville, Sewaren, Salem / Hope Creek, Covanta Essex, Kearny and Bergen. At the spring tide two substations are touched, Merion (Cape May, 0.5 %) and Raritan River (Sayreville, 0.1 %), and Burlington Gen is added.

**What is wet in 2100 (SSP2-4.5).** The site with ≥ half its land wet is **Merion Substation** (Cape May, 138 kV): 66 % at the typical high, 88 % at the spring tide. The spring tide adds an unnamed 230 kV Middlesex substation (`s3310`), which goes from 5 % to 100 %. The largest plant shares at the typical high are:

- Kearny 16 %;
- Seaside Heights 13 %;
- Sayreville 9 %.

**Every site wet in 2050 is also wet in 2100.** Both runs sit in order with the feet runs:

| | today | **2050** | + 2 ft | **2100 SSP2-4.5** | + 4 ft |
|---|---|---|---|---|---|
| typical high | 1 | **8** | 10 | **17** | 22 |
| spring tide | 6 | **11** | 14 | **20** | 27 |

**Normally-dry land in water.** These areas come from `floodmaps/slr_stap/*_stats.json`, with the + 2 / + 4 ft products of `floodmaps/mhhw_v2/` alongside for comparison. They cover the WHOLE model domain: NJ plus the computed DE / PA / Staten Island banks. They count normally-dry land only (`normal_surface`), at 3.125 m pixels.

| run | typical high: km² ≥ 0.15 m (any depth) | spring tide: km² ≥ 0.15 m (any depth) |
|---|---|---|
| today (`msl2026_plus0ft`) | 2.9 (98.5) | 132.5 (255.9) |
| **STAP 2050** (+ 0.459 m) | **206.6** (334.5) | **364.1** (448.0) |
| + 2 ft (+ 0.61 m) | 320.7 (432.2) | 455.0 (525.1) |
| **STAP 2100 SSP2-4.5** (+ 0.939 m) | **530.4** (607.6) | **630.3** (699.0) |
| + 4 ft (+ 1.22 m) | 681.2 (758.3) | 782.8 (852.9) |

Depth is not failure: floor heights, walls and site protection are unknown. The small-share "touched" sites are at least partly the bank-face artefact (`logs/bank_face_sweep_2026-11-15/README.md`), so quote the ≥ half column. On these two runs the artefact was not swept separately.
