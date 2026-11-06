# Bed audit check `channel_depth`: the bed vs federal navigation channels (2026-11-05)

Format: `../../SCHEMA.md`. Script: `check.py` (one CLI, any bed). Outputs: `../../out/<bed>/channel_depth.csv`
(the exceptions) and `../../out/<bed>/channel_depth_coverage.csv` (one row per NCF reach: authorized level, station,
share surveyed, the reach's sill crest).

## What it checks, in one line

Inside every federal navigation channel the model simulates, is the bed at least roughly as deep as the channel USACE
is authorized to keep, and where it is not, is that a real (surveyed) shoal or a bed error, and does it close the
channel?

## Sources

| source | what | version / access | licence |
|---|---|---|---|
| **USACE National Channel Framework** (NCF), layer `ChannelReach` | 384 reach polygons in the v4 box (CENAN 233, CENAP 150, CENAE 1), each with `depthauthorized` / `depthmaintained` (ft below MLLW; identical for every reach here), width, district, name | `services7.arcgis.com/n1YM8pTrFmm7L4hs/.../National_Channel_Framework/FeatureServer/2`, pulled 2026-11-05; raw in `/scratch/tpj8/nj_bight_sfincs_data/audit/channel_depth/raw/` | US Government work, public domain |
| **NOAA CO-OPS datums** | MLLW − NAVD88 at the 50 stations in the box that publish both (epoch per station; range −1.28 … −0.17 m — the −0.17 end is the micro-tidal back bays, which is why a single constant would be wrong) | `api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/<id>/datums.json`, `raw/stations_mllw_navd88.json` | public domain |
| the recipe's own survey / stated tiers | eHydro (`ehydro_*`, `shrewsbury_ehydro_2015`), `riverbeds_v4`, `riverbeds_hierarchy_v4e`, `coned_sw_raritan`, `ehydro_harbour_v4`, `ehydro_refreeze_cenan_v4`, `riverbed_sayreville_v4`, `littleegg_channel_v4`; for the modern bed `ehydro_latest_2026` first | `REF_2012` / `LATEST` in `check.py` | — |

**The authorized bottom** of a reach = MLLW at the nearest CO-OPS station (NAVD88) − depth × 0.3048. The station and its
distance are in every row's `source` and in the coverage table (`station_km`). VDatum was not used: its web API is
broken south of Barnegat (`scripts/download_ehydro_nj.py`), and a station plane is what eHydro surveys without a stated
plane were reduced with. Expect ~0.1–0.2 m of datum uncertainty in back bays far from a station.

BlueTopo is **not** used as a reference (it leaves MLLW unconverted outside VDatum, `logs/ehydro_datum_2026-11-05/`).

## The rule and its thresholds

The bed is sampled on a grid inside each reach polygon (6.25 m = 2 subgrid pixels where the channel is under 100 m
wide, else 12.5 m), only where an ACTIVE model face lies under the point (within 0.75 × its size): 255 of the 384
reaches are simulated; the 129 others are New York harbour, Long Island Sound, Jamaica Bay and the C&D Canal, outside
the model. The bed is read through the rotated rasters' affine (`logs/decks_2026-11-04/common.py` `Bed`).

| kind | rule | threshold and why |
|---|---|---|
| `unsurveyed_fill_in_channel` | no survey under the point and bed > authorized bottom + **1.0 m** | USACE keeps 1 ft required + 1 ft allowable overdepth and channels shoal 1–3 ft between dredgings; + ~0.2 m datum, + ~0.2–0.3 m of 3 m-pixel smoothing in narrow channels. 1.0 m (3.3 ft) is beyond routine shoaling + method error, so what is left is an anomaly. |
| `bed_above_survey` | a survey exists and the bed stands > **0.5 m** above it | the bed was painted FROM that survey; after the merge it should agree to pixel resampling (~0.1–0.3 m on slopes). More means a later tier or overlay overwrote it (the class behind modern land overwriting our river beds, 11-04). Demoted to `low` where the bed is still deeper than authorized + 1.0 m. |
| `bed_above_latest_survey` | same, against `ehydro_latest_2026` (modern bed only) | the modern recipe does not carry `ehydro_latest_2026` yet, so these 1,844 rows are EXPECTED today; they are the acceptance test for the 2026 rebuild (all should vanish). |
| `shoaled_per_survey` | survey and bed agree, both > authorized + 1.0 m | real shoaling, not a bed error: kept as information, `low` (one row per reach), `medium` only as a sill. |
| `over_deep` | bed < authorized − allowance − **3.0 m**, not confirmed by a survey (bed < survey − 1 m or no survey), AND ≥ **1 m below every base tier** (CUDEM / NJ 10 ft / 3DEP / GMRT) | the base-tier test removes natural deep water (offshore bar channels such as Ambrose, scour holes: 321 → 17 rows on 1.0.0's bed); what is left is deeper than anything an independent source shows, i.e. a carve over-reach (cf. the deck-carve trenches). |
| `assumed_bed_no_survey` | < 50 % of a reach's simulated points have a survey / stated bed | the bed there rests on a base tier (`base_mode`): needs a survey or a stated-depth decision. |

**Severity (the sill test, not a count).** For every reach longer than 3 × its width, the check finds the lowest level
at which the reach's two ends connect through the bed (4-connected minimax on the grid, as `s4_sills.py` did for the
Christina tide). If that crest is more than 1.0 m above the authorized bottom, the reach is CLOSED at that level:
`high` when less than **1.0 m of water covers the crest at MLLW** (tide-choking: a uv sill near MLLW halved the tide
at Newport, FINDINGS part 4 (l)), `medium` otherwise (conveyance loss) or when the crest is a surveyed shoal. Blocking
patches that do not close the reach are `medium` (≥ 50 % of the width at their worst station) or `low`; 1–3-cell
specks are dropped.

## Results

| bed | high | medium | low | reaches < 50 % surveyed |
|---|---|---|---|---|
| `p100` (Model 1.0.0) | 14 | 237 | 604 | 156 (all CUDEM-based) |
| `v1_1b` (emulated, see caveat) | 13 | 202 | 613 | 156 |
| `modern` | 3 | 327 | 1,894 (1,592 `bed_above_latest_survey`) | 10 |

⚠️ **`v1_1b` is emulated**: `_subgrid_v1_1b` (job 63577223) did not exist yet, so the run used `_subgrid_v1_1` with
`deck_fix_v4b` and `alloway_pool_v4` applied as minima. `_subgrid_v1_1` already CONTAINS the old `deck_fix_v4`, so the
emulation is min(v4, v4b): it opens at least as much as the real v1.1b. **Re-run on the real bed** (command below);
a crossing v4 opened and v4b left can only look worse there.

### Known cases

| case | p100 | v1_1b | modern | verdict |
|---|---|---|---|---|
| Christina, top federal reach (21 ft) | `bed_above_survey` medium, crest −3.10 m (CR_02 survey lost) | `shoaled_per_survey` medium (+2.0 m, the survey's own shoal) | `bed_above_latest_survey` medium | ✅ caught, and the v1.1 fix shows |
| the Christina **plug** (−75.5599, 39.7236) | — | — | — | ❌ outside coverage: 196 m above the federal project limit (mile 4.18). Owned by the water-surface / crossing checks. |
| Grays Ferry M537 (−75.196, 39.942) | — | — | `bed_above_latest_survey` medium nearby | ❌ in the 2012 beds: 118 m beyond the end of Schuylkill Ranges 30–38; the modern hit is the newest survey's edge |
| Shark River inlet M271 | passes (ehydro_nj) | passes | `bed_above_latest_survey` medium, bed up to +11.6 m above the survey (the −1.0 m lidar water surface + deck) | ✅ caught where it is wrong (modern only) |
| Toms River (v4d reach) | **high** sill, crest +0.85 m, survey lost | passes | medium (latest survey deeper) | ✅ caught; v1.1's v4d fix shows |
| Maurice GMRT fall-through | passes | passes | passes | ✅ fixed since 10-05; no simulated federal reach rests on GMRT any more (`base_mode` is CUDEM everywhere) |

### Top new findings (v1.1 bed unless noted; `out/v1_1b/channel_depth.csv`, severity high)

1. **ICW IW 10 under the Atlantic City Expressway + the Atlantic City Line (−74.4456, 39.3645).** 1.0.0's bed closes the
   waterway with a 13 m deck dam (crest +13.05 m); v1.1's deck overlay leaves a **+2.75 m** crest (authorized −2.6 m),
   above MHHW. Both are v1.1 deck sites (44, 112). Sandy peak there 2.26 m. Check the real v1.1b bed first.
2. **Cape May Canal (−74.920, 38.961)**: crest −0.85 m in both 2012 beds (authorized 12 ft ≈ −4.5 m; ~0 m of water
   at MLLW), **+1.40 m in the modern bed** (−74.906, 38.954: at the bridge crossings). The canal is the Delaware Bay
   ↔ Cape May Harbor link. CC_01 (restored to `ehydro_latest_2026` today) does not reach the crest.
3. **Cape May County ICW IW 13 / 14 / 15** (−74.650, 39.228; −74.700, 39.158; −74.770, 39.085): crests −1.40 / −1.25 /
   −0.85 m vs −2.6 m authorized, on CUDEM. In the modern check `ehydro_latest_2026` covers them and reads deeper:
   survey-confirmed fills in the 2012 bed.
4. **Raritan Bay small-craft channels**: Cheesequake Creek crest −0.60 m (Sandy peak 3.90), Woodbridge Creek +0.65 m
   (also high in modern; 1.8 km from US Foods Solar), Leonardo marina −0.15 m, Great Kills Harbor +2.00 m — all on CUDEM.
5. **Lewes & Rehoboth Canal, Roosevelt Inlet → Broadkill River** (−75.165, 38.791): crest −0.10 m, unsurveyed (LR_01–03
   were the surveys dropped 11-04 and restored 11-05).

Also: Coney Island Creek (NY, three crests −0.6 … +0.3 m); 6 `bed_above_survey` medium patches in v1.1 where an overlay
sits over a survey; 17 `over_deep` rows on 1.0.0's bed (carves below every base tier).

## Limits

- **Federal channels only.** Most of the tide-critical creeks (the Christina above mile 4.18, the Cohansey above the
  project, every non-federal thorofare) are not in the NCF; the water-surface and crossing checks cover those.
- **Authorized ≠ actual.** A flagged `unsurveyed_fill_in_channel` may be real shoaling (the NJ ICW is often shallower
  than authorized); the flag says the bed is an assumption that contradicts the authority by > 1 m, and needs a survey
  (or a stated-depth call) to settle. The modern reference shows which: where `ehydro_latest_2026` covers a 2012 flag
  and reads deeper, the 2012 bed is a fill.
- **Datum**: nearest-station MLLW, not VDatum (±0.1–0.2 m in back bays).
- **Grid**: 6.25–12.5 m points on 3.125 m pixels — a channel narrower than ~15 m is under-sampled.

## Re-run

```fish
cd ~/nj_bight_sfincs; set -x PATH ~/nj_sandy_sfincs/micromamba/envs/sfincs/bin $PATH
set C logs/bed_audit_2026-11-05/checks/channel_depth/check.py; set O logs/bed_audit_2026-11-05/out
python $C --bed experiments/v4_refreeze_swz/_subgrid_v1_1b --label v1_1b --out $O/v1_1b/channel_depth.csv   # the REAL v1.1b
python $C --bed experiments/v4_refreeze_swz/_subgrid_modern2026 --modern --label modern --out $O/modern/channel_depth.csv
python $C --bed experiments/v4_refreeze_swz/_subgrid_refreeze_lakes_min_creeks_cohansey --label p100 --out $O/p100/channel_depth.csv
```

~2–3 min per bed with 6 workers on the VS Code node, ~2–3 GB RAM. `--only <regex>` restricts to reach names (testing).
