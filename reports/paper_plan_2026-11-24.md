# Paper plan: NJ-SFINCS 2.0.0 (2026-11-24)

Maps each planned figure / table to what exists and what is missing. Shape agreed 11-23 (STATUS "Paper"):
**validation** = modern tides on the 2026 bed (MHHW error at assets matters most) + Sandy on the 2012 bed (+ Irene,
Nor'Ida on the 2012 bed and the 23 Dec 2022 nor'easter on the 2026 bed, decided 11-24); **application** = SLR
(STAP) → first sunny-day flood + flood days per year at NJ power assets. Model = **2.0.0** (`nj2` mesh; domains
`nj2w_bed2012` `0f87265091209585`, `nj2w_bed2026` `f63e8ff0a984c598`). HWM numbers are **median estimator, 50 m
radius, native 3.125 m floodmap, `_scored` keys** throughout. Paths are relative to the repo root; every one
listed was checked to exist on 11-24 unless marked *(OneDrive)* or *(to build)*.

---

## 0. Before any paper run: freeze 2.0.x

Every 2026-bed product below (tide skill, ladder, SLR, Dec 2022) is invalidated by a later bed or structure change on
that bed (a bed change is a new fingerprint → re-run). Settle these first, in this order:

| item | state 11-24 | consequence for the paper |
|---|---|---|
| NY-cut boundary: arm B (NOAA tide at the Hudson / Hell Gate cuts, long-period terms kept) | read 11-24 (`logs/noaa_cuts_2026-11-23/README.md` "Read"); B adopted; its 32-day run not done | B moves NJ-asset high water ≤ 1.8 cm, but "B and A runs must not be mixed in one ladder": every 2026-bed calm run used in the paper should be on B (§2 F2, F8–F11) |
| Hackensack bed above lat 40.751 (H03725 1915 overlay, central vs 11-ft cap) | tide test **64338392 running**; 2012-bed Sandy check after | if adopted: new `_subgrid_nj2_2026*` (+ 2012 twin) → new fingerprints → re-run the 2026-bed tide / SLR set and the Sandy premier |
| Sea Bright seawall as a weir line | scored (`experiments/nj2w_bed2012/p4-premier+rain-off+…+weir-seabright`), read pending; `nj2_sb_checks` 64341533 pending | adopt = 2.0.x structures on both beds (2026 bed needs its own crest read + engine u/v count) |
| 2026-bed leftover notches (Brigantine 39.41, Wildwood 38.988, Cape May Pt), M537 / M271 carves | open (STATUS "Next") | only if near an asset (BED_QUALITY: fix what changes who floods) |
| `premier.py` `output WHOLE` for late-start runs | ✅ FIXED 11-24 (`tstop − tref`; `tests/test_output_complete.py`) | — |

**Proposed version label for the paper: 2.0.1** = 2.0.0 + whichever of the above is adopted. Re-run the two Sandy
premiers (2.5 h each, 64 threads) and the 2026-bed calm set once, on the frozen 2.0.1.

---

## 1. Proposed outline (8 sections, 10 figures, 4 tables + supplement)

| § | section | figures / tables |
|---|---|---|
| 1 | Introduction (compound flooding, power assets, need for fast models; first SFINCS model of the whole NJ coast) | — |
| 2 | Model: domain, mesh, two beds, forcing, engine | **F1** domain + mesh + forcing; **T1** setup |
| 3 | Bed construction and observation-led QA (2012 vs 2026) | **T2** bed sources + fixes |
| 4 | Validation I: modern tides on the 2026 bed | **F2** tide skill at gauges; **F3** tidal reach |
| 5 | Validation II: Sandy on the 2012 bed | **F4** HWM residuals; **F5** MOTF extent; **F6** gauge hydrographs; **T3** scores + sensitivities |
| 6 | Validation III: Irene, Nor'Ida (2012 bed), Dec 2022 (2026 bed) | **F7** + **T4** peak / mark errors |
| 7 | Application: SLR → sunny-day flooding at power assets | **F8** threshold ladder; **F9** flood days per year; **F10** bathtub vs dynamic |
| 8 | Discussion: limits, speed, operational use | (risks table §4) |
| S | Supplement | S1 spin-up; S2 waves-on noise band; S3 NY-cut A/B; S4 de-noised tide surface; S5 SLR maps (STAP); S6 Sandy-today asset exposure (optional) |

---

## 2. Figure / table map

Status: **have** = data and figure exist on the current model; **partly** = data exist, figure or a piece missing;
**need** = runs or code missing.

| # | purpose (one line) | what it shows | runs / products it uses | status | work to get there (size) |
|---|---|---|---|---|---|
| **F1** | Show what is modelled | ring + forced line + 2 NY cuts, quadtree levels, 61 inflows, 55 obs points, weirs / dikes, wavemaker line, gauges, marks | `experiments/nj2w_bed2012/p4-premier+struct-cohansey-checkvalve+weir-dikes-levees/` (sfincs.nc, obs, weir); `data/nj2_design/structures/`; script to adapt `reports/poster_2026-11-13/fig1_model.py` (draws 1.1.0 / v4 mesh) | partly | redraw on nj2 (add Upper Bay / Hudson / East River, two cuts); ~½ day, light |
| **T1** | Reproducible setup | mesh, beds, forcing sources, physics, engine + patches, cost | `docs/MODEL.md` §1–3, §7 | partly | condense MODEL.md into one table; note 2.0.1 deltas; pin NACCS / CORA versions, NLD / HWM pull dates, licences (MODEL.md §10 "still to pin") |
| **T2** | Defend the bed | tier hierarchy; 2012 vs 2026 differences; every fix with its independent source (BED_QUALITY "fix table") | `_subgrid_nj2_2012/provenance.txt`, `_subgrid_nj2_2026/provenance.txt` (under `experiments/nj2w*/`); `logs/modern_bed_2026-10-28/cudem_survey_dates.md`; `logs/deck_carve_audit_2026-11-05/`; `logs/hackensack_fable_2026-11-23/bed/README.md` | partly | compile the one fix table BED_QUALITY §2 asks for (not compiled anywhere); ~1 day, light |
| **F2** | Headline modern-tide skill (MHHW error at assets) | per station: MHHW / MHW error vs NOAA datums, M2 amp ratio + phase lag; map + bar | **A (EC2015) 32 d:** `experiments/nj2w_bed2026/tide-0ft+weir-normalweather/` (1983–2001 epoch, uninterrupted, WHOLE) and `…/tide-0ft-msl2026+weir-normalweather/`; spring A/B (4.5 d, 12 harbour stations, both **resumed**): `logs/noaa_cuts_2026-11-23/read_1124/gauge_vs_noaa.csv`, `subordinate_vs_battery.csv`, `gauge_residuals.png` | partly | (1) **B 32-day `tide-0ft` run** (file `…/nj2_noaacuts/…_p000.nc` built; register + run, ~13–17 h at 64 threads, ~3.2 G map); (2) harmonic / datum read at ALL NOAA + USGS tidal stations in the domain incl. Delaware, back bays, Hackensack subordinates (script: extend `gauge_vs_noaa.py`; light) |
| **F3** | Where the tide reaches vs where it should | model MHHW-wet area vs VDatum MHHW surface + NWI tidal wetlands; held-behind-a-crest areas | `experiments/nj2w_bed2026/tide-0ft-msl2026+weir-normalweather/`; `logs/tidal_reach_2026-11-24/` (started today: audit + de-noise log only) | need (running) | finish the BED_QUALITY B check (class table + map); ~½ day after the job |
| **F4** | Sandy peak accuracy | HWM residual map + obs-vs-model scatter, by basin; noted / lake marks hollow | premier `experiments/nj2w_bed2012/p4-premier+struct-cohansey-checkvalve+weir-dikes-levees/` (job 64003605, uninterrupted); `logs/runs_2_0_twin_2026-11-22/out/read/per_mark.csv`; marks `data/validation_nj2/sandy_hwms_nj2.geojson`; script `reports/poster_2026-11-13/fig2_hwm.py` (1.1.0) | partly | redraw on 2.0 per-mark table; flag marks ≤ 50 m from a weir (CLAUDE.md §5); light |
| **F5** | Sandy extent vs FEMA MOTF | hit / miss / false alarm, insets (Newark, Meadowlands, Barnegat); excluded boxes drawn | rain-off twin `experiments/nj2w_bed2012/p4-premier+rain-off+struct-cohansey-checkvalve+weir-dikes-levees/` (MOTF reference since 11-09) + premier; `experiments/nj2w_bed2012/floodmaps/*_hmax_lev3.tif`; `logs/csi_dip_2026-11-18/README.md`; script `reports/poster_2026-11-13/fig1_model_fema.py` | partly | redraw on 2.0; ~200 G scoring node for the class raster; light otherwise |
| **F6** | Time behaviour, not just peaks | 8–10 hydrographs (Sandy Hook pre-failure, Battery, Bergen Pt, Atlantic City, Barnegat, Cape May, Lewes, Philadelphia, a Meadowlands sensor); peak table for the 40 "fair" gauges | premier `sfincs_his.nc`; gauge keys in `experiments/nj2w_bed2012/metrics.csv`; scripts `reports/poster_2026-11-13/fig_hydrographs.py`, `logs/poster_diagnostics_2026-11-13/gauge_peaks.py` | partly | re-run the fair-gauge summary on 2.0 (it exists for 1.1.0 only); add Battery + Bergen Point (new in 2.0); light |
| **T3** | Sandy scores + what each process is worth | premier, rain-off, waves-off, 2026 bed, dike set, Hell Gate test; paired ΔRMSE + CI; CSI / POD / FAR | `experiments/nj2w_bed2012/metrics.csv` (6 rows), `experiments/nj2w_bed2026/metrics.csv`; `logs/runs_2_0_twin_2026-11-22/out/T/hwm_pair_vs_premier.txt`; J3 `logs/nj2_freeze_2026-11-14/README.md`; Hell Gate test *(OneDrive, retired 11-24; row kept in metrics.csv)* | have (core) | optional: wavemaker on/off on 2.0 (only on 1.0.0, *(OneDrive)* `v4_refreeze_swz/p4-premier+wave-nowavemaker`); 1 run 2.5 h + pair |
| **F7 / T4** | Skill holds beyond Sandy (holdout storms) | per storm: gauge peak error + timing; HWM residuals where marks exist; Dec 2022 HRRR vs ERA5 wind | nothing run. On disk: NACCS TH 002 (Irene) at all 244 points, XH 89 (Nor'Ida, 2009-11-13) at 243 (`logs/naccs_storms_2026-11-22/`); CORA trust test `logs/cora_check_2026-11-24/README.md` | need | see §3 (code + forcing + 4–5 runs) |
| **F8** | Per-asset first-flood level | for each of the 182 sites: the boundary offset (and the level at its reference gauge) at which it first gets ≥ 0.15 m; ranked chart + map | rung 0 template: `experiments/nj2w_bed2026/tide-0ft-msl2026-spring6d+weir-normalweather/` (A, resumed) and `…-noaacuts-spring6d…` (B, resumed); scorer `scripts/tide_assets.py` / `SitePixels.score` (ladder-ready); de-noise `nj_sfincs/tide_surface.py` | need | register rungs on B: offset 0 → +1.5 m step 0.10 (16 rungs, 6.5 d spring window, uninterrupted); ~3.5 h each at 64 threads ≈ 55 node-h, ~2.5 G each (~40 G scratch); ONE job script (few-jobs rule); de-noise + score ~10 min per rung |
| **F9** | Flood days per year at assets | days/yr ≥ threshold vs year 2026–2100 under STAP central / SSP2-4.5 (and high), per county / asset class | F8 thresholds + NOAA harmonic predictions per year at reference gauges (Sandy Hook, Battery, Bergen Pt, Atlantic City, Cape May, Lewes, Philadelphia) + STAP trajectories (`logs/slr_stap_2026-11-15/README.md`) | need | python only (NOAA 6-min predictions per year via CO-OPS API, or `tidelib` from harcons); decide whether "sunny-day" = astronomical only or adds the observed non-tidal residual distribution (NOAA HTF practice); ~1–2 days |
| **F10** | Why a dynamic model (vs bathtub) | +2 / +4 ft: still-water (VDatum MHHW + s, sea-connected) vs tidal mean higher-high vs month max; area and site counts; maps of the difference (Delaware River, Newark Bay, back bays) | still: `experiments/nj2w_bed2026/floodmaps/slr_2_0/mhhw_plus{2,4}ft_stillwater_nj2bed2026_depth.tif`; tidal: `…/mhhw_plus{2,4}ft_tidal_nj2bed2026_{mhh,max}_depth.tif`; counts `logs/slr_2_0_2026-11-22/results/nj2bed2026_plus{2,4}ft_{still,mhh,max}_summary.txt` | partly | redo on B + de-noised; figure (template: `logs/tide_maps_2026-11-03/compare_still.png` on 1.1.0); light |
| S1 | Cold-start lead needed | ΔHWM RMSE and Δzsmax area vs lead (6 / 12 / 24 / 36 h vs 49 h) | `logs/spinup_test_2026-11-23/README.md` "Read", `read_1124/zsmax_domain_by_lead.csv`, `out/read/` (runs retired 11-24 *(OneDrive)*) | have | figure from the csv; light |
| S2 | Size of waves-on run-to-run noise | gauge / mark / face bands from two `rhoa` null copies | measured on 1.0.0 / v4 mesh only (MODEL.md §5, FINDINGS part 4 (j)) | partly | one null pair on 2.0 (2 × 2.5 h, 64 threads) so the paper's paired Δs in the bays sit against this mesh's band |
| S3 | NY cut forcing choice | A vs B at 12 harbour stations, reach of the change, long-period terms | `logs/noaa_cuts_2026-11-23/README.md` (Read + Long-period), `read_1124/`, `longperiod_1124/` | have | — (32-day B run is F2's) |
| S4 | De-noised tide surface | bank-face flag, replaced area, unchanged site counts | `logs/denoised_mhhw_2026-11-23/README.md` (1.1.0 validation); nj2 run in progress (`logs/tidal_reach_2026-11-24/denoise_run_nj2.out`, `experiments/nj2w_bed2026/floodmaps/denoised_mhhw/` empty) | partly | finish `run_nj2.sh` on all 6 arms (~9 min each) |
| S5 | SLR exposure today → 2100 | STAP maps + site counts, typical high and month max | 6 arms `experiments/nj2w_bed2026/tide-*+weir-normalweather/` (all uninterrupted, WHOLE by audit for 2 so far), maps `experiments/nj2w_bed2026/floodmaps/slr_2_0/`, counts `logs/slr_2_0_2026-11-22/results/` (raw, not de-noised) | partly | de-noise (S4) + re-run on B; counts read by the user (not yet) |
| S6 | "If Sandy happened today" (optional) | site counts on the 2026 bed | `experiments/nj2w_bed2026/p4-premier+struct-cohansey-checkvalve+weir-dikes-levees/` (uninterrupted); poster's 1.1.0 count `reports/poster_2026-11-13/exposure/v11_modernb_2026bed_assets.csv` (its run *(OneDrive)*, Tier 2 retired 11-17) | partly | run `reports/poster_2026-11-13/exposure_poster.py` on the 2.0 run; light |

**Count (main body F1–F10 + T1–T4, 14 items): have 1 (T3) · partly 8 (F1, T1, T2, F2, F4, F5, F6, F10) · need 5
(F3 running, F7, T4, F8, F9).** Supplement S1–S6: have 2, partly 4.

---

## 3. Extra storms (F7 / T4): what each needs

| | Irene, Aug 2011 | Nor'Ida, Nov 2009 | 23 Dec 2022 nor'easter |
|---|---|---|---|
| bed / domain | 2012 (`nj2w_bed2012`) | 2012 | 2026 (`nj2w_bed2026`) |
| boundary | NACCS TH 002, on disk, all 244 pts; record ends 08-30 00:00 → window 08-26 12:00 → 08-29 12:00 | NACCS XH 89 (2009111302), on disk at **243 / 244**: **SP19080 (a Hell Gate cut point) has no XH file** → fill the cut (neighbour 11877, or NOAA tide + Battery residual) | **CORA** water level (1979–2022, hourly, MSL datum): fetch at 244 pts + VDatum offset + a **gauge-anchored constant** (CORA reads +0.06…+0.14 m at gauges: epoch) |
| wind / pressure | NACCS–ERA5 blend: NACCS wind on disk ("Irene"), ERA5 request (minutes) | NACCS–ERA5: **XH wind NOT fetched** (~1,900 pts × 6.2 MB ≈ 12 GB) | **HRRR** 3 km (no loader in repo; source in `logs/ops_data_2026-11-23/DATA_LIST.md`) + ERA5-wind twin |
| waves | CORA 2011 (dated copy of `scripts/build_cora_waves.py`) | CORA 2009 | CORA 2022; use the v1.1.1 (Jun 2026) waves |
| rain / rivers | AORC 2011 (wet antecedent soil: cnb factor decision); 58 / 61 gauges | AORC 2009; rivers to check | AORC 2022; rivers to check |
| validation | CO-OPS (complete), USGS tidal, **Irene HWMs: browser-only** (STN refuses scripts), OFR 2012-1022 sensors | CO-OPS + USGS tidal; HWMs: check STN in the browser (likely few) | CO-OPS + USGS tidal; no HWMs / extent expected; peaks below NWS moderate everywhere |
| shared code | **`StormForcing` override** (proposed text in `logs/naccs_storms_2026-11-22/README.md` §6; not written); storm-keyed gauge + mark files; ~~`premier.py` WHOLE fix~~ (done 11-24) | same | same + CORA boundary builder + HRRR meteo builder (engine corner convention, `nj_sfincs/meteo_grid.py`) |
| runs | 1 waves-on (≈2.5 h, 64 threads, ~11 G map) + optional waves-off twin | 1 (+ twin) | 2 (HRRR, ERA5) |

Effort: code + forcing ~3–4 days; compute ~15 node-h; scoring ~200 G node per storm; scratch ~60 G.

---

## 4. Key numbers in hand (current model, post-repair)

| quantity | value | conditions / source |
|---|---|---|
| Sandy HWMs, 2.0.0 2012 bed | RMSE **0.322**, bias **−0.032 m**, 94 % within ±0.5 m | median, 50 m, n 163, native; job 64003605 uninterrupted; FINDINGS part 4 (p) |
| … without the 6 noted marks | 0.291 / −0.017 m | median, 50 m, n 157 |
| … vs 1.1.0 on the 1.x marks | ΔRMSE −0.002 [−0.007, +0.005] (0.346 vs 0.348) | median, 50 m, n 119, paired, B 200 000 |
| MOTF extent (NJ) | CSI 0.795 / POD 0.859 / FAR 0.085; rain-off twin CSI 0.811 / POD 0.834 / FAR 0.033 | native, excluded boxes 2,534 km²; `experiments/nj2w_bed2012/metrics.csv` |
| Rain-off twin HWMs | 0.331 / −0.046 m | median, 50 m, n 163 |
| Waves worth (waves-off − on) | ΔRMSE **+0.149** [+0.054, +0.252]; waves-off 0.470 / −0.186 m | median, 50 m, n 163, paired; `logs/runs_2_0_twin_2026-11-22/` |
| 2026 bed − 2012 bed, Sandy | ΔRMSE +0.044 [−0.003, +0.123]; 2026 bed 0.366 / −0.019 m, CSI 0.798; Barnegat Bay +0.10 m (today's inlet) | median, 50 m, n 163; excluded boxes differ (2,505 vs 2,534 km²) |
| Dike / levee set | ΔRMSE −0.0003 [−0.0007, +0.0001]; CSI 0.787 → 0.785 | waves-off, +0, median, 50 m, n 163 |
| Hell Gate −0.25 m test (not adopted) | `east_river` bias +0.106 → +0.022; headline ΔRMSE −0.0024 [−0.0066, +0.0009] | median, 50 m, n 163 |
| Modern tide, NY harbour (spring, 4.5 d) | mean \|HHW error\| at 12 independent stations 4.9 cm (A) → 3.7 cm (B); harbour HW 2–5 cm low in both; Hackensack range 0.65× Battery vs NOAA 1.33× | 2026 bed, resumed runs, own mean removed; `logs/noaa_cuts_2026-11-23/` |
| Spin-up | 36 h lead: HWM ΔRMSE +0.0005; 24 h +0.0028; 12 h +0.044; 6 h +0.106 | waves-off, 2026 bed, median, 50 m, n 163, vs 49 h |
| SLR site counts, 2.0 2026 bed (raw, A boundary, not de-noised) | typical high: today 1 / 0, STAP 2050 8 / 0, + 2 ft 11 / 0, STAP 2100 SSP2-4.5 17 / 1, + 4 ft 21 / 2 (touched / ≥ half wet, of 182); month max 6 / 0, 11 / 0, 15 / 0, 19 / 1, 28 / 6 | ≥ 0.15 m on normally-dry land; `logs/slr_2_0_2026-11-22/results/`; 1.1.0 de-noised: 1/0, 8/0, 10/0, 17/1, 22/3 |
| Speed | 2.4 h per 72 h waves-on storm (8,566 s, 64 threads) | production engine `…swomp-2-gf11@dd78d82a` |

**Poster (printed 11-16) quoted 1.1.0:** RMSE 0.35 m (n 119), CSI 0.80, 40 gauges RMSE 0.23 m, 52 / 182 sites in
Sandy-today, 22 / 182 at + 4 ft. The paper's 2.0 numbers differ (more marks, NY basins, 2.0 CSI 0.795). Say once that
the poster was 1.1.0; do not mix the two.

---

## 5. Open risks a reviewer would hit

| risk | what we know | handling in the paper |
|---|---|---|
| **Hell Gate forcing** | NACCS at the cut peaks 3.60 vs Battery 3.44 m; `east_river` bias +0.106 (median, 50 m, n 13); harbour + Raritan feel it ~3 cm | known limit; show the −0.25 m test as sensitivity; the fix (cut into Long Island Sound) is 2.1 |
| **Hackensack bed** | flat 1915 / chart bed above 40.751; tide range 0.65× vs NOAA 1.33×; upper Meadowlands 0.1–0.3 m low in Sandy; ~60 % of the 2.0 CSI dip | test 64338392 running; adopt before F2 / F8; otherwise mask Meadowlands sites in the ladder |
| **IG wavemaker size** | shoreline IG std ~0.28 m, `hm0ig` 2–3× Leijnse's (FINDINGS §45, §49); wavemaker carries the Monmouth lake marks | report with / without the 5 lake marks; wavemaker on/off sensitivity (T3 optional) |
| **Monmouth lakes / no morphology** | 5 `lake_outlet_blocked` marks −0.7…−2.3 m set the headline; dune breach + overwash not modelled | quote `_excl_lake_blocked` beside the headline; dune breach = out of scope |
| **CUDEM vintage ("2012 bed")** | where CUDEM sets the bed: 61 % pre-Sandy, 36 % 2014 on; the back bays are Nov 2013 – Jun 2014 topobathy | call it "circa-2012"; table of tier vintages in T2 |
| **2026 bed is estimated** | no modern flood to score; tidal reach is the only observational check; Dec 2022 is the one storm test | F2 + F3 + Dec 2022 (T4) |
| **Waves-on noise** | band median 2.1 cm, max 10.4 cm at gauges; per mark p90 8.3 cm (measured on 1.0.0's mesh) | S2 on nj2; never quote bay Δs below the band |
| **Bank-face noise in tide runs** | sliver faces ring, MHHW 0.1–0.9 m high there; cause open | de-noised read (S4); site counts unchanged on 1.1.0 |
| **MOTF not independent** | HWM-interpolated bathtub; NJ only; excluded boxes 2,534 km² | quote as a consistency check, beside the marks |
| **Bed fixes found from the same observations** | BED_QUALITY: FIND from MOTF / tidal reach, FIX from independent sources, JUDGE on marks / gauges | state the rule; the holdout storms (T4) answer circularity |
| **Delaware** | storm low −0.36 (Lewes) → −0.7…−1.0 m (Newbold); 3 scored marks; NACCS deficit at the mouth | state as limit; Delaware not a focus |
| **Cape May back bays** | bias −0.232 m (median, 50 m, n 4) | known limit |
| **Peak `hm0` not physical** | 27.55 m at the Narrows; 3,131 faces ≥ 12 m | never publish an unclipped `hm0` map |
| **NY harbour coarser** | no NY buildings, SnapWave off over Upper Bay / Hudson / East River | state scope |
| **Patched engine** | 4 physics patches + 2 speed patches, not upstream | MODEL.md §3 recipe in a data / code statement; file the drafted upstream issues |
| **Resumed runs** | A/B spring arms resumed; a resumed waves-on run is a different run | paper runs uninterrupted (check `restart_history.txt`) |
| **Asset definition** | today's OSM list (182 in model); "flooded" = ≥ 0.15 m on any part | define once; give ≥ half-wet beside touched |
| **CORA wave version** | v1.1.1 (Jun 2026) re-computed GEC waves; Sandy's `data/waves_v4/cora_waves_v4.nc` is dated 09-29 | confirm it read v1.1.1 before quoting; rebuild if not |

---

## 6. Order of work (proposed)

1. Read 64338392 (Hackensack tide) + Sea Bright read → freeze **2.0.1** (§0); (`premier.py` WHOLE fixed 11-24).
2. One job on the frozen 2026 bed: B `tide-0ft` 32 d (F2) + the 6 SLR arms on B (S5, F10) + 16 ladder rungs (F8);
   ~150 node-h, ~60 G scratch (scratch ~931 G of 1 T: retire first). Re-run the 2 Sandy premiers if the bed moved.
3. In parallel (light): F1, T1, T2, F4–F6 redraws on 2.0; F3 from today's tidal-reach job; F9 pipeline.
4. Storms: `StormForcing` code → Irene (marks by browser) → Nor'Ida (XH wind fetch, SP19080 fill) → Dec 2022 (CORA +
   HRRR builders).
5. S2 null pair on nj2; independent (Fable) audit of the numbers before submission.
