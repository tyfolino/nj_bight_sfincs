# A+ (`v4_hot_plus`) re-freeze list — draft 2026-10-05

Everything the 10-05 pre-freeze audit found, grouped by what fixing it costs. Evidence for
every line is under `logs/audit_v4_hot_plus_2026-10-05/` and `logs/raritan_2026-10-05/`;
STATUS ("Pre-freeze audit of A+", "Raritan Bay / harbour low in v4") has the reads.
**Open:** see §5 (status of every item, 10-05 evening). The dredged-channel + 3DEP sweep is DONE
(`logs/audit_v4_hot_plus_2026-10-05/channels_and_3dep/README.md`) and is folded into §2.

Decided on 10-05: the river cut is **A+**; the cheap wave setting is **5° bins, hourly
updates** (`dtwave` 3600). The Maurice cut is already on the Union Lake dam crest
(fingerprint `e5e9d8668fe29292`).

---

## 1. Mask-only fixes — wall boxes, ring edits, inflow moves (no subgrid rebuild)

A mask change moves the fingerprint, so these are batched into ONE restage.

**Real leaks (≥ 10 cm on a free-outflow cell at +3 m)** — `edge_crossings/README.md` §A

| # | site | lon, lat | when it leaks | fix |
|---|---|---|---|---|
| A1 | Breezy Point tip | −73.909, 40.560 | +0, +2, +3 m; ~1,160 m³/s at +3 m (drain census) | wall the dry tip |
| A2 | Leipsic River millpond (DE) | −75.554, 39.189 | all levels — the river inflow ponds and spills | ring edit around the pond, or move the inflow below it |
| A3 | Tuckahoe head | −74.778, 39.519 | all levels — the inflow ponds to 8.4–9.4 m past its 500 m wall | ring edit / wall; see also §2 (the Tuckahoe GMRT hole) |
| A4 | Toms River tributary at `nj_atlantic_n_05` | −74.253, 39.967 | +3 m | wall |
| A5 | Mile Run (Raritan side), Franklin Twp | −74.487, 40.508 | +2, +3 m | wall |
| A6 | Broadkill headwater, near Milton DE | −75.341, 38.774 | +3 m | wall |

**Marginal (< 10 cm now; cheap to wall)** — §B: Silver Lake Dover (−75.539, 39.125);
Pennsauken Creek (−74.862, 39.962); creek at `nj_burlington_09` (−74.953, 39.940); Bergen
Hill rail cut (−74.063, 40.741); Swimming River inflow pond (−74.124, 40.312); the Cape
Henlopen wall gap (lower `wall_henlopen_atlantic` y0 4,287,000 → 4,286,700).

**Inflows on a bank or island → move into the channel** — `moved_inflows/`, `all_inflows/`

| gauge | Qmax | now | fix |
|---|---|---|---|
| 01463500 Delaware at Trenton | 808 m³/s | on an island mid-river (7 m ground) | into the main channel |
| 01479000 White Clay Creek | 69 m³/s | on the bank, 4 m above the channel | into the channel |
| 01395000 Rahway River | 4 m³/s | inner bank of a meander | into the channel |
| 01377000 + 01377500 Hackensack / Pascack | 3.8 m³/s | 4.7 m bank, 27 m off the channel | into the channel |

Rule change worth making at the same time: place inflows from NHD + lidar (the channel),
not "the lowest-bed face" — that rule picks banks wherever the bed is a flat fill.

## 2. Bed fixes — need a SUBGRID rebuild (the re-freeze proper)

| item | where | what is wrong | fix material | status |
|---|---|---|---|---|
| Harbour channels | Kill van Kull, Newark Bay main, Port Elizabeth / Newark / S. Elizabeth, Arthur Kill (Sewaren, Elizabethport) | 4–16 m too shallow (CUDEM has no dredged trench; Sewaren falls through to 3DEP's −0.8 m surface); ~56 Mm³ missing | `ehydro_harbour_v4` (6 surveys, built 10-05) | **test running** (`bed-harbour+naccs-nowaves`) |
| …plus 2 reaches the preset misses | South of Shooters Island (1.7 km, ~6 m shallow), Woodbridge Creek | same | NJ_07_SSI 2014, NJ_20_WBC 2015 → `ehydro_refreeze_cenan_v4` | **built 10-05**; in the `bed-channels` test |
| USACE 2010 lidar paving deep water | **Great Egg Harbor Inlet**, Longport → Ocean City (−74.565…−74.527, 39.292…39.316): a 3.3 km × 300 m band at −0.4 m across the 8 m inlet channel; **Inside Thorofare** (IW_10, ~2.5 km, 4.7 m shallow — the gauge's +3.47 m face); **Compton Creek / Shoal Harbor** (0.6 km, 4.5 m) | `usace_nj_2010_v3` outranks CUDEM and returns a flat surface over deep water | `usace_unpave_v4`: CUDEM painted back in three declared boxes where the 2010 lidar > −0.8 m over CUDEM < −1 m (1.08 / 0.24 / 0.04 km²; Compton also gets its survey) | **built 10-05**; in the `bed-channels` test. 🔴 **In v3 too** (same tier; v3's bed shows the band). ~15 smaller patches Ocean City → Wildwood are unconfirmed causeway candidates |
| 3DEP water surface as bed | 4.1 km², all in the Raritan corner: **South River + Washington Canal** (8.25 km at −1.13 m vs −4.5 m surveyed; HWMs 6107–6109 near), Sewaren, Cheesequake Creek, Raritan side channels, Rahway mouth | no CUDEM 1/9″ tile, CoNED clipped | `ehydro_refreeze_cenan_v4`: NJ_21_WSR, NJ_20_WBC, NJ_19_CQC 2015 (CoNED is NO help — its source there is topographic lidar too) | **built 10-05**; in the `bed-channels` test. Left on 3DEP: the Sayreville side channels (0.53 km², only the 1934 NOS H05647) and the Rahway mouth (0.20 km², nothing found yet). (The catalog's "3DEP blanks tidal water" note is not implemented) |
| CUDEM ~0 m water surface on tidal rivers | **Cohansey** (whole length, incl. the Greenwich gauge); Matawan Ck, Tuckerton Ck (by its gauge), Lewes Canal, Little River DE | flat fill | Cohansey: **no measured bed exists above the mouth** (NOS D00081 1987 stops at 39.348, ENC has only a 0–1.8 m band, no eHydro; `logs/bedfix_2026-10-05/cohansey/`) → user 10-05: a stated depth is fine → `riverbed_cohansey_v4`, 1.2 m below MLLW (−2.14 m), 6.49 km²; others: 2019–25 surveys | Cohansey **built 10-05**, in the `bed-channels` test; others: to build |
| GMRT fall-through | Maurice (Mauricetown → Millville, 3.9 km²), Mullica above ~−74.46 (5.1 km²), Tuckahoe (0.7 km²), Rancocas (1.0 km²) | channel takes GMRT land heights, +1–5 m; blocks the tide (the Maurice "blockage") | `build_riverbeds_v4.py` reaches, or surveys if any exist | to build |
| Main federal channels | Delaware (mouth → Trenton), C&D, Schuylkill, Wilmington, Raritan, Raritan Bay, Sandy Hook / Ambrose, surveyed inlets, most of the ICW | **fine**: CUDEM within ±0.2 m of eHydro, 96–100 % of each section kept | — | **no action**; the unused `ehydro_delaware_v4` tier is not needed |
| Fake lakes (§54) | 87 lakes (5.55 km², Manor Lake 1.78) + 7 river stretches (1.06 km²) inside A+ | CUDEM's ~0 m fill under non-tidal water | `build_inland_water_v4.py` | **needs your 09-29 decisions** (see §4) |

## 3. Not a fix yet — open or watch

- **Raritan / Newark Bay low** (−0.4 to −0.7 m): the working chain is the choked Kill van
  Kull → low Newark Bay → the Arthur Kill drains western Raritan Bay. The channel test decides
  it; if it does not close the gap, an Arthur-Kill-walled bracket run is next.
- **Schuylkill backing up** below the Fairmount Dam (6.8 m vs ~3 m observed) — the box-mean
  Manning in narrow urban channels (untested).
- **Christina** inflow ponds +0.9 m — the channel is ~20 m, narrower than the face.
- **Unresolved bed candidates** (`blocked_low_ground/`): Cape May Point marsh (USACE 2010
  layer high), a CUDEM 6 m crossing south of Trenton, a 10 m CUDEM ridge at the C&D Canal,
  3DEP vs CUDEM ~4 m apart on the DE side, inactive faces walling water at Lewes (+3 m) and
  Paerdegat Basin.
- **Two "tidal" gauges on high faces:** Absecon Creek (+2.92 m) and Inside Thorofare
  (+3.47 m) can only record the crest — in v3 too. Inside Thorofare is explained (the 2010
  lidar paving, §2).
- **Little Egg Harbor:** the 2024 survey reads 4–9 m deeper than the model over 5.5 km — but
  12 years after Sandy. Check pre-Sandy charts before touching it.
- **SnapWave boundary:** 53 cells shallower than −20 m (to −12 m) on the southern step —
  check depth-limited breaking before the first waves-on run.

## 4. Decisions (user, 2026-10-05) — all taken

1. **Building cap: +10 m** → `bed_buildings_v4_cap10` (re-burned 10-05, job 62282126).
2. **§54 inland water: the four recommendations** (`logs/inland_water_2026-10-05/DECISIONS.md`):
   clamp on; the tidal Christina at Newport, Big Timber, St Jones + four small items OUT (they
   get a carved channel instead — in progress); Manor Lake CLOSED at 1.84 m; 43 low-surface lakes
   kept → `inland_water_bed_v4` (bed only; n 0.02 needs the roughness route — in progress).
3. **v3: re-run now** with the shared fixes and hourly waves (`bed-v4fixes+wave-dt3600` / `+naccs-nowaves`).
4. **Standing rules → A+ wording** (memory + CLAUDE.md, done). **Frozen v4 = `v4_hot_plus_walls`.**
5. **Depth rule where no bed was ever measured: 1.2 m below MLLW** (Cohansey, then the four
   GMRT reaches; "if we have to assume a fixed depth, that's okay").

## 5. Status of every item (2026-10-05 evening)

- §1 mask fixes: **DONE** in `v4_hot_plus_walls` (11 walls, B6 gap, 4 inflows — own discharge file).
- §2 bed fixes: **built** — harbour + 2 missed reaches, the 2010-lidar sills (3 boxes), the Raritan
  corner surveys, the Cohansey, the GMRT reaches, the lakes; all in run B's bed. **In progress:**
  the back-bay sill candidates, Sayreville / Rahway, the tidal carves, the Maurice section, the
  roughness route (+ the Schuylkill). Left: Tuckerton / Matawan / Lewes canal / Little River
  (2019–25 surveys exist), Little Egg Harbor (verdict pending).
- §3 open: the harbour test is queued; the rest as listed, being worked by the subagents.
- Next: final overlay list → rebuild on `v4_hot_plus_walls` → re-baseline its premier (STATUS).
