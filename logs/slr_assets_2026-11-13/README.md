# Power sites under 1.2 m of sea-level rise, on today's ground (2026-11-13)

## What

The poster says *"1.2 m of sea-level rise alone would flood about 30 of the 182 NJ power plants and substations
at high tide (still-water estimate)"*. That 30 came from `logs/power_exposure_2026-11-02/` (`still_4ft`):

- the still-water MHHW + 4 ft map;
- on the FIRST 2026-ground estimate (`bed-modern`, Model 1.0.0 domain `v4_refreeze_swz`);
- read with ground from the bed's first overview (6.25 m).

This dir re-counts it on **today's ground estimate**: `_subgrid_modern2026b`, the same 2026 ground as the poster's
Fig 3 storm run, on Model 1.1.0's domain `v4_refreeze_swz_v11`, with the normal-weather structures (closures open,
Overpeck dam shut). The count is made from the three + 4 ft (1.22 m) products of `logs/mhhw_v2_2026-11-12/`:

| tag | product (`experiments/v4_refreeze_swz_v11/floodmaps/mhhw_v2/`) | what it is |
|---|---|---|
| `v11modernb_tidal4ft_mhh` | `mhhw_plus4ft_tidal_v11modernb_mhh_depth.tif` | 32-day tide + 1.22 m: the **mean higher-high** (the typical daily high tide) |
| `v11modernb_tidal4ft_max` | `mhhw_plus4ft_tidal_v11modernb_max_depth.tif` | the same run: the month's highest water |
| `v11modernb_still4ft` | `mhhw_plus4ft_stillwater_v11modernb_depth.tif` | still water at VDatum MHHW + 1.22 m, wherever the sea connects (no solve) |

## How

`slr_assets.py <depth.tif> <arm dir> <tag>` uses the poster power figure's rules
(`reports/poster_2026-11-13/exposure_poster.py`).

- **The sites.** The 253 NJ records of `reports/poster_2026-11-13/exposure/v11_modernb_2026bed_assets.csv` that are
  not out of the model. **"The 182"** are the ones the poster's Sandy run on 2026 ground calls wet, dry or on water.
  The other 71 sit at the model's edge.
- **Pixels.** The product's own 3.125 m pixels under each footprint (`power_exposure.pixels`).
- **Active.** A pixel is active when its quadtree face is active in the arm's `sfincs.nc` and it has ground under it.
- **Ground.** Read from the arm's `subgrid/dep_subgrid_merged.tif` **base band**, through the affine.
- **Water.** `normal_surface.normally_wet` marks normally-wet pixels; those are not land.
- **Wet.** A site is **wet** when any land pixel has depth ≥ 0.15 m. Its state comes from `power_exposure.asset_state`.

Output goes to `results/<tag>_assets.csv` (one row per site, with `sandy2026_state` beside the new `state`) and
`results/<tag>_summary.{txt,json}`. The summary gives:

- the wet count out of 182;
- how many of those have ≥ half their land wet;
- the split by class (plant / substation) and by county;
- the list of wet sites;
- any wet site among the 71 edge sites (reported, not in the 182).

When all three are read, `results/ALL_summary.txt` lists them side by side.

The products carry depth only on normally-dry land, so a pixel is wet here only where `mhhw_maps.py` drew it.
Depth is not failure: floor heights, walls and site protection are unknown.

## The job

`watch_slr_assets.slurm` is **job 63895431** (hal0392; running since 11-13 16:17). Settings: `main`, no halk,
2 cores, 16 G, 48 h, `--requeue`. `EXPECT_MD5 = expected.md5` covers the job script, `slr_assets.py`,
`scripts/power_exposure.py` and the asset CSV.

How it runs:

- **Polling.** Every 10 min. A tide tif is read as soon as it appears; `mhhw_maps.py` `os.replace`s it in whole.
- **When a product counts as final.** A tide product is final once `<prefix>_stats.json` exists. The still product
  is final once `<prefix>_depth.json` exists.
- **Re-reads.** If a tif is replaced before its marker lands (the resume job re-making it), it is read again.
  `results/<tag>.done` holds the tif's mtime + size.
- **Exit.**
  - 0 when all three are final and read;
  - 1 when the producers (63853850, 63887750, per `sacct`) have left the queue with something missing;
  - otherwise it runs to the time limit.
- **Failed reads.** A read that fails is retried up to 3 times (`results/<tag>.log`).
- **Run time.** One read takes 30–60 s and ~1.2 GB.

**When results land.** Following `logs/mhhw_v2_2026-11-12/README.md`:

- **The tide + 4 ft products:** ~11-14 09:15–11:05 (job 63853850), so both tidal counts arrive within ~15 min of
  each tif.
- **Still + 4 ft:**
  - 63853850 makes it only if it reaches that step before its 11-14 11:08 limit.
  - Otherwise the resume job 63887750 makes it. It starts when 63853850 ends, if it gets a node. It does
    still + 2 ft first and then still + 4 ft (~0.5–0.75 h per map), so likely 11-14 early-to-mid afternoon.
  - If 63887750 waits in the queue, the still count waits with it.

Look at `watch_63895431.out` and `results/`.

## Self-check: the old "about 30", re-derived

**1. The fixed `scripts/power_exposure.py` on the 11-02 still + 4 ft map** (`selfcheck_pe.py` → `selfcheck_pe/`,
`selfcheck_pe_summary.csv`; the 11-02 tables are untouched; 60 s, 9.1 GB):

| NJ, still + 4 ft, Model 1.0.0 `bed-modern` | wet | ≥ half wet | plants / substations | dry | not computed | on water |
|---|---|---|---|---|---|---|
| 11-02 (bed read on the first overview) | **30** | 6 | 19 / 11 | 150 | 71 | 2 |
| fixed (bed base band) | **30** | 6 | 19 / 11 | 150 | 71 | 2 |

- **No site changes state.** 7 wet sites lose a few wet pixels: wet share −0.01 to −0.3 points, 57 pixels in all.
- **Why so little changes.** That map's DEPTH was computed on the 6.25 m overview and the fix cannot change it. The
  fix changes only which pixels count as normally-wet ground.
- **Where the overview error does matter.** The new mhhw_v2 products are native at 3.125 m, depth and ground both,
  so that error does not reach them.

**2. `slr_assets.py` on the same map** (`selfcheck_slr/`, NJ_DOMAIN `v4_refreeze_swz`, arm `bed-modern+still-4ft`):

- **The same 30**, 6 of them with ≥ half their land wet, 19 plants / 11 substations.
- **Per site, against the fixed `power_exposure`:** all 253 states identical and every `n_wet` identical.
- **Only difference:** 6 dry or wet sites show `covered_frac` 0.997–0.9999 against 1.0. That comes from the face
  lookup vs the rasterised mask at footprint edges.

The classifier therefore reproduces the poster's old number exactly.

**3. The same reader on the 11-03 tidal + 4 ft maps of the FIRST 2026 ground** (6.25 m products, for orientation
only):

| | wet of 182 | ≥ half wet | plants / substations |
|---|---|---|---|
| tidal mean higher-high | 20 | 3 | 14 / 6 |
| tidal month max | 25 | 5 | 17 / 8 |
| still water | 30 | 6 | 19 / 11 |

So on that ground the order was mean higher-high < month max < still water. Still water fills every low spot the
sea connects to at the full level. A real tide does not get through every culvert and marsh in one high water.

## Which number to quote on the poster

**Recommended: the tidal mean-higher-high count (`v11modernb_tidal4ft_mhh`).**

- **It matches the wording.** "At high tide" means the typical daily high water, which is exactly what that map is:
  the mean of the tidal-day highs over a month of real tide raised 1.22 m.
- **It is the more defensible map.** It is a solved hydrodynamic run on today's ground and structures.
- **Suggested wording:** "On today's ground, 1.2 m of sea-level rise alone would put N of the 182 sites in water at
  an ordinary high tide (M at the month's highest tide)." Drop "(still-water estimate)".

**Still water (`v11modernb_still4ft`) is the like-for-like successor of the old 30.** Use it if the sentence must stay
comparable with the abstract ("about 30 … still-water estimate"). It is an upper-end reading: every connected low
spot is filled to the full level.

Quote whichever is used with its definition: depth ≥ 0.15 m on any normally-dry part of the site, no storm, MHHW
(1983–2001 datum) + 1.22 m.

## Today's-tide baseline (11-15)

Same rules, run by hand on the vscode node (inputs md5 in `results/plus0ft_inputs.md5`; ~30–80 s, 1.3 GB each), on the
two no-rise tidal runs of `logs/mhhw_v2_2026-11-12/` (both `output WHOLE`; the 1983–2001 one was resumed once, from 2012-10-13 18:00, inside the 2.5 d spin-up — waves-off, rain-off, so mm-level; the msl2026 one ran unbroken). Guess written before the read: 2–4.

| tag | run | typical high (mhh) | month max |
|---|---|---|---|
| `v11modernb_tidal0ft_*` | EC2015 tide, 1983–2001 datum (`p000`) | **1** | 3 |
| `v11modernb_msl2026_0ft_*` | the same + the rise 1992 → 2026 (mean 0.148 m) | **1** | 6 |
| `v11modernb_tidal2ft_*` | + 0.61 m (counted 11-15; guess before the read: ~6) | 10 | 14 |
| `v11modernb_tidal4ft_*` | + 1.22 m (the poster's case) | 22 | 27 |

The 1 is PSEG Sewaren (0.1 % of its land, a waterfront sliver). The month-max 6 are all slivers ≤ 0.4 % (Sewaren,
Linden Gen + Solar, Sayreville, Salem / Hope Creek, Kearny); none is a substation. Both datums agree on the typical
high tide, so the poster says "22 … against 1 at today's high tide" (v11, both versions).

+ 2 ft: the 10 are all plants, each wet on ≤ 2 % of its land (edge slivers); no substation. + 4 ft adds the first
substations (7) and the first sites with ≥ half their land wet (3).

### Against the 2025 NJ STAP projections (11-15)

Source: *New Jersey's Rising Seas and Changing Coastal Storms*, 2025 STAP Report (Rutgers / NJDEP, Nov 2025), Table 5
(Atlantic City, ft above the 1995–2014 mean, "2005"; 19-yr means), Table 4 / C12 (baselines). Our offsets are above
MHHW of the 1983–2001 NTDE, whose MSL sits 0.19 ft (Atlantic City) / 0.22 ft (Sandy Hook) / 0.23 ft (Cape May) /
0.21 ft (Philadelphia) BELOW the STAP baseline. So, above the STAP 2005 baseline:

| run | above 2005 | where it sits in Table 5 (Atlantic City) | sites wet, typical high tide |
|---|---|---|---|
| today (`msl2026`) | ~0.3 ft (+0.148 m since 1992 − 0.06 m) | observed 2005–2020 ≈ 4 in | 1 |
| **STAP 2050 central** (`stap2050`, + 0.459 m) | 1.31 ft (0.40 m) | 2050: the central estimate, all scenarios | 8 |
| + 2 ft | ~1.8 ft | 2050: just above the likely range (0.9–1.7; < 5 % row 2.3). 2070: the central estimate in every scenario (1.8 / 1.9 / 2.0). 2100: ≥ 83 % chance exceeded under low emissions, ≥ 95 % under intermediate | 10 |
| **STAP 2100 central, SSP2-4.5** (`stap2100ssp245`, + 0.939 m) | 2.89 ft (0.88 m) | 2100: the central estimate under intermediate emissions | 17 |
| + 4 ft | ~3.8 ft | 2100: top of the likely range under intermediate emissions (SSP2-4.5, "< 17 % chance exceeds" = 3.8); inside the likely range under high (SSP3-7.0: 2.6–4.3, central 3.3) | 22 |

Sandy Hook's Table B5 is within ~0.1 ft of Atlantic City.

The two STAP central rows were run on 11-15/16 (job 63941099). They are tide-only twins of the + 2 / + 4 ft runs: same 2026 bed (`bed-modernb`), Model 1.1.0's domain `v4_refreeze_swz_v11` and normal-weather structures, with only the boundary offset changed. Each offset is STAP Table B2 (Atlantic City) plus the 0.059 m NTDE → STAP baseline. Both runs were preempted once and resumed inside the analysed month (waves-off, rain-off: mm-level). Details are in `logs/slr_stap_2026-11-15/README.md` "Results".

### Spring tide (the month max) vs the typical high tide (11-15, user: "spring tide = sunny-day flooding")

The `_max` products are each face's highest water over the modelled month (EC2015 astronomical tide, 10-12 → 11-13
2012, after a 2.5 d spin-up). At every boundary arm the month peak is the **17 Oct 2012 new-moon spring tide, 0.25–0.31 m
above the mean higher-high** (top-5 days +0.22–0.27 m; from `sfincs_netbndbzsbzifile_tide_ec2015_p000.nc`).

**Corrected 11-15 (NOAA CO-OPS predictions, hi/lo, datum MHHW, pulled 11-15):** month-to-month variation is large, and
this month is one of the year's HIGHEST, not a floor. Monthly max predicted high above MHHW, Sandy Hook 2012:
0.06 0.01 0.12 0.29 0.39 0.39 0.34 0.27 0.27 0.37 0.39 0.31 (2026: 0.17 0.06 0.09 0.26 0.34 0.35 0.32 0.28 0.21 0.30
0.29 0.23); Atlantic City alike. Our window's NOAA peak is 0.37 m (Sandy Hook 10-16) / 0.36 m (Atlantic City 10-17),
within 0.02 m of the 2012 annual max. Two causes: perigee / new-full-moon alignment, and the SEASONAL mean sea level
(late winter low, summer–fall high), which NOAA predictions carry (Sa / Ssa) and our EC2015 boundary does NOT
(`logs/modern_bed_2026-10-30/tide/README.md` l.11). So the model's spring peak (+0.25–0.31 m over the month's mean
higher-high) sits ~0.06–0.1 m below NOAA's predicted fall king tide: the spring-tide counts slightly UNDER-state a
fall king tide; they are close to the year's highest astronomical tide otherwise.

| run | typical high (mhh): touched / ≥ half wet | spring tide (max): touched / ≥ half wet |
|---|---|---|
| today (`msl2026_0ft`) | 1 / 0 | 6 / 0 |
| **STAP 2050 central** (`stap2050`, + 0.459 m) | 8 / 0 (all plants) | 11 / 0 (9 plants, 2 substations touched) |
| + 2 ft (`tidal2ft`) | 10 / 0 | 14 / 0 (2 substations touched) |
| **STAP 2100 central, SSP2-4.5** (`stap2100ssp245`, + 0.939 m) | 17 / 1 (14 plants, 3 substations touched; the ≥ half one is a substation) | 20 / 2 (14 plants, 6 substations touched; both ≥ half are substations) |
| + 4 ft (`tidal4ft`) | 22 / 3 | 27 / 6 (4 plants, 2 substations) |

All rows use the same 2026 bed (`bed-modernb`, `_subgrid_modern2026b`), Model 1.1.0's domain and normal-weather structures.

- **2050:** every touched site has ≤ 2.3 % of its land wet.
- **2100 SSP2-4.5:** the ≥ half sites are Merion Substation (Cape May, 66 % at the typical high, 88 % at the spring tide) and, at the spring tide only, the unnamed 230 kV Middlesex substation `s3310` (100 %).

The small-share "touched" sites are at least partly the bank-face artefact (Sewaren, above); quote the ≥ half column.

**Bank-face sweep (11-15, `logs/bank_face_sweep_2026-11-15/README.md`):** dropping pixels on faces flagged > 0.10 m
above a local open-water reference leaves every count above unchanged; Sewaren today (typical high) = 0–1 (18 of its
19 wet pixels flagged, the 19th at 0.0998 m). The sweep predates the two STAP runs and was not repeated on them.
