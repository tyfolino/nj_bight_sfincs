# Deletion manifest — 2026-08-20 campaign

✅ **EXECUTED 2026-08-21 on the user's sign-off** (quota 75.72 → **65.22 G**, verified
against `mmlsquota` either side): `diag-premier-norain/snapwave.upw` (unblock met —
run verified WHOLE and accepted), the premier arm's `snapwave.upw` (now the weir run
after the promotion renames; same regenerable class), `~/.apptainer`, and the five
archive v2_barnegat `sfincs_map.nc` (the 5 floodmap caches + 5 his files kept, so the
banked scores stay recomputable). **Kept by user decision:** `sfincs-env.tar.gz`
(rebuilt 2026-08-21), `~/.vscode-server` (live session), and the blocked 16.5 G
`.ige` (v3 not started). Three of the four flagged `snapwave.upw` were already absent
at execution time.

Nothing on this list is deleted without the user's sign-off, and every reclaim is
verified against `mmlsquota -u $USER --block-size auto cache` (never a script's own
summary; never probe headroom by writing). Quota at drafting: **73.88 G / 100 G soft**.

✅ Already executed this campaign (user pre-approved, verification passed first):
NACCS original zips — 24 zips (1.6 G) replaced by 5 CRC-verified canonical zips
(590 MB); parser reproduced the 1,287-point parse and the v1_monmouth support sha16
`21f967f9798a6945` before deletion. Net ~0.64 G back (five originals shared inodes
with the frozen archive, whose copies are untouched).

## Claude may delete on sign-off

| item | size | why safe | how regenerated |
|---|---|---|---|
| `experiments/v1_5_raritan/naccs-premier/snapwave.upw` | 597 M | runtime upwind table, NOT in `sfincs.inp` | solver rebuilds it on any re-run (archive trim precedent: 7 deleted 2026-08-15) |
| `experiments/v1_5_raritan/noaa-2node/snapwave.upw` | 597 M | same — and the arm is retired | same |
| `experiments/v1_monmouth/faber-waves-premier/snapwave.upw` | 573 M | same; the port fixture RESCORES output, never re-runs | same |
| `~/nj_coast_sfincs/sfincs-env.tar.gz` | 888 M | env export snapshot | `micromamba env export` / `environment.yml` |
| `~/nj_sandy_sfincs/sfincs-env.tar.gz` | 888 M | same (near-duplicate of the above, 17 KB apart) | same |

subtotal ≈ **3.5 G**

⚠️ NOT listed: `diag-premier-norain/snapwave.upw` — the job (60700612) is running and
has the file open. It joins the list once the run is verified WHOLE.

## User deletes (their tooling / their call)

| item | size | note |
|---|---|---|
| `~/.vscode-server` | 5.0 G | regenerated on next VS Code remote connect (extensions re-download) |
| `~/.apptainer` | 621 M | container build/pull cache |

subtotal ≈ **5.6 G**

## Blocked — do NOT delete yet, unblock condition stated

| item | size | unblock condition |
|---|---|---|
| `~/sfincs_data/elevation/raw/Rast_statewide_10ft_DEM.ige` (+.img header) | 16.5 G | 🔴 **only after v3's 3DEP re-clip is built and verified** — `download_3dep.py` re-clips from this raw, and `nj_10ft_dem` stops at lat 39.645 while v3 needs Cape May |
| archive `v2_barnegat` maps (5× `sfincs_map.nc`) | 8.79 G | ✅ **UNBLOCKED 2026-08-20** — `experiments/v2_barnegat/metrics.csv` banked (5 rows, 184 keys, current scorer; `scripts/score_v2_barnegat.py`). ⚠️ Keep the five `floodmap_hmax_lev3.tif` caches (~0.5 G, written beside the maps) — with the his files they keep HWM/MOTF/gauge metrics re-computable after the maps go. User deletes (archive). |

## Scripts (bytes, not gigabytes — repo hygiene, same sign-off)

| script | verdict |
|---|---|
| `scripts/download_ehydro_shrewsbury.py` | KEEP — sole provenance of the live `shrewsbury_ehydro_2015` tier (`data_catalog.yml:86`); "superseded by download_ehydro_nj.py" was wrong, that script builds a DIFFERENT tier |
| `scripts/rebuild_subgrid_h.py` | 🔴 KEEP — its target arm is gone but it is the only worked example of a subgrid rebuild on a frozen mesh, the pattern any Keansburg bed remedy would clone |
| `scripts/score_bracket.py` | v2_barnegat-only — KEEP until the v2 scoring lands (may be its scorer), then retire |
| `scripts/verify_port.py` | KEEP — still the gate every `validate/` edit runs |
| `scripts/build_cora_waves.py` | KEEP — CORA is the adopted wave boundary; domain-aware for v3 |

Everything else in `scripts/` is either a live acquisition script (sole provenance of a
catalogued tier) or a diagnostic with its artifact still current.
