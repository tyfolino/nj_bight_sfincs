# Deletion manifest — 2026-09-20 (end of the wavemaker / wind-arm day)

⏳ **NOT EXECUTED. The user ticks; nothing here is deleted until then.** Precedent:
`deletion_manifest_2026-08.md`. Inventory: every script with last-commit date and reference
counts, every run dir with TRUE reclaim (`logs/retire_manifest_2026-09-20.txt`, the retire
tool's own read-only manifest), notebooks / reports / data by git tracking. Scratch is at
**107 G of 1 T** — nothing below is forced by disk; it is about not leaving a stale artifact
that outlives its replacement (memory: clean as you go).

Rules applied: a script is a candidate only if NO code, test or hpc file references it and
its purpose is a retired arm, a closed sweep, a one-off migration, or a v1.5/v2-only build
step; a `download_*` script that produced data still on disk is KEPT as that data's
provenance; anything the v4 (Delaware Bay) build will need is KEPT. Git keeps every deleted
file's history, so a STATUS/FINDINGS mention of a deleted script still resolves.

## A. Run directories — `scripts/retire_arm.py … --apply` (keeps the small record, deletes the bulk)

The five old-band arms are the 09-13/14 fixed-engine runs on the Sandy-Hook-cut band,
superseded by the apex premier (paired ΔRMSE +0.0145 m [+0.0053, +0.0249], FINDINGS §46);
their `metrics.csv` rows stay. `wave-nowind+wave-shelf-steps` is the wind-off half of the
§43 direction diagnosis (misdirected-engine era). TRUE reclaim from the tool:

- [ ] `wave-band-sandy-hook` — 23.74 G
- [ ] `wave-band-sandy-hook+wave-fw02` — 23.73 G
- [ ] `wave-band-sandy-hook+wave-noig` — 23.19 G
- [ ] `bed-nobuildings+wave-band-sandy-hook` — 23.73 G
- [ ] `bed-nobuildings+wave-band-sandy-hook+wave-fw02+wave-noig` — 23.17 G
- [ ] `wave-nowind+wave-shelf-steps` — 22.42 G
- [ ] their five/six `experiments/v3/floodmaps/<arm>_hmax_lev3.tif` (the gallery; the retire tool refuses `floodmaps`, so `rm` by hand AFTER the arms are retired) — ~2.4 G each

  Total ≈ **140 G**. ⚠️ Retiring them removes them from the 09-14 six-arm notebook's
  candidate list at next render (it filters on `sfincs_map.nc`); the rendered 09-14 file
  is unaffected. Command (one line, after ticking):
  `NJ_DOMAIN=v3 PYTHONPATH=$PWD python scripts/retire_arm.py <arms…> --reason "old-band epoch superseded by the apex premier (FINDINGS §46); wind-off half of §43" --apply`

- [ ] `experiments/v1_5_raritan/{naccs-premier,naccs-nowaves}` — 1.9 G each, Sep 2 re-stages of the frozen v1.5 domain (its scored record is `experiments/v1_5_raritan/metrics.csv` + the archive). `rm -r` by hand; the retire tool is v3-rooted.
- [ ] `experiments/v2_barnegat/` — 0 G (empty shell of the archive's domain). `rmdir`.
- KEEP: `naccs-premier`, `wave-wavemaker`, `wave-wavemaker+wind-x110` (running), `naccs-nowaves`, `_template_sealed`, `_subgrid_buildings`, `_retired/` (already trimmed to 0.03 G each), `v1_monmouth` (the port fixture, 582 M), the five `metrics_*_rebaseline.csv` snapshots (tiny, referenced by STATUS).

## B. Scripts — `git rm` (history keeps them)

Retired-arm / closed-sweep tooling, zero code references:
- [ ] `scripts/build_stockdon_boundary.py` — built `BRACKET+setup-stockdon` (retired 09-18)
- [ ] `scripts/build_naccs_stwave_waves.py` — built `wave-stwave` (retired 09-18)
- [ ] `scripts/measure_rain_share.py` — `diag-premier-norain` read (retired; FINDINGS §39 holds it); its `reports/rain/*.csv` go with it
- [ ] `scripts/sweep_bed_dams.py` + `scripts/plot_bed_dam_candidates.py` — the bridge-as-dam sweep, closed 08-26 ("no carve"); `reports/bed_dams_v3.csv` + `reports/figures/bed_dam*.png` go with them
- [ ] `scripts/stamp_metrics_epoch.py` — one-off 09-11 migration, done
- [ ] `scripts/town_floodmap_diff.py` + `scripts/motf_csi_buildings_masked.py` — the 09-08 buildings read, closed (`experiments/v3/motf_csi_buildings_masked.csv` stays as the record)
- [ ] `scripts/wave_boundary_ring.py` — the 09-08 "boundary not transmitting" diagnosis; the defect is fixed and the ring is in FINDINGS
- [ ] `scripts/score_bracket.py` + `scripts/score_v2_barnegat.py` — v2 Manahawkin bracket / archived v2 runs (⚠️ `v2_barnegat` still has 32 code references, mostly `domain.py` comments — check `grep -rn v2_barnegat nj_sfincs` before removing anything BUT these two scripts)
- [ ] `scripts/download_era5_waves_cds.py` — ERA5 waves are inadmissible (FINDINGS §21); its output is not used

v1.5-only build steps (v1.5 is FROZEN; the mesh + data stay for the registry):
- [ ] `scripts/build_refinement_v1_5.py`, `scripts/validate_region_v1_5.py`
- [ ] `scripts/build_coned_sw_raritan.py`, `scripts/plot_ward_point_bed.py` — the Ward Point / CoNED tier decision (08-15), settled
- [ ] `scripts/diagnose_keansburg.py` — the Keansburg overshoot → the weir (FINDINGS §38); `reports/keansburg/` (9 tracked files) goes with it
- [ ] `scripts/sweep_cudem_flatfill.py`, `scripts/audit_paved_channels.py` — v1.5 bed workstreams; `reports/coned/phantom_water_patches.json` goes with the first
- [ ] `scripts/rebuild_subgrid_h.py` — superseded by `scripts/rebuild_subgrid.py` (which has the `--overlay` path CLAUDE.md §5 requires)

KEEP (v4 will need them, or they are provenance): every other `download_*` (they made the data on disk — `download_sandy_winds.py` is the tool I should have used today instead of `curl`), `freeze_mesh.py`, `probe_mesh_size.py`, `validate_domain.py`, `accept_domain.py`, `setup_boundary_depth.py`, `build_naccs_boundary.py`, `build_cora_waves.py`, `check_naccs_vs_sensors.py` (the forcing-product diagnostic the wind question needs), `stockdon_envelope.py` (a scoring diagnostic; today's desk check could have reused it), `naccs_coverage_map.py`, `make_flux_crosssections.py`, `sync_obs_points.py`, `plot_waterlevel_boundary.py`, all engine-gate / restart / retire / dedupe / notebook tooling, everything in `hpc/`.

## C. Notebooks and reports — `git rm`

- [ ] `notebooks/v3/sandy-v3-viz-2026-08-29.ipynb` (12 M) — renders the three 08-27 v3 arms that were **VOIDED** on 08-31 (the dropped refinement bands, CLAUDE.md §5). A rendered notebook of void runs is the textbook stale artifact.
- [ ] `notebooks/v3/sandy-v3-winddir-fix-2026-09-13.ipynb` (21 M) — the bug-era vs fixed-engine comparison; FINDINGS §43 and the 09-14 notebook carry the result
- [ ] `notebooks/v1_5_raritan/` (2 files, 6 M) — the frozen predecessor's viz
- [ ] `reports/snapwave_parameters_naccs-premier.docx` (13 K) — superseded by `reports/snapwave_parameters.html` + `docs/snapwave_parameters.md`
- KEEP: `sandy-v3-build-qc-2026-08-25` (domain QC), `sandy-v3-viz-2026-09-14` (the six-arm fixed-engine epoch), `sandy-v3-viz-2026-09-20` (the wavemaker), `reports/weekly_*`, `reports/naccs/`, `reports/seiche/`, `reports/figures/` (gitignored), `reports/cleanup/`.

## D. Data — nothing

`data/*v1_5*` (303 M, the frozen v1.5 mesh the registry still names), `data/v2_barnegat_runs`
(8 K), `data/validation_v3/{ndbc,coops_wind,usgs_sandline}` (new today, 8 M, re-downloadable)
all stay. Raw roots under `~/sfincs_data` are load-bearing (memory: never flag for deletion).

## Execution order, after ticking

1. Section A via `retire_arm.py --apply` (manifest-first, moves the keeps before any unlink), then the gallery tifs by hand, then `python -m nj_sfincs.premier` (retired arms show as `RET`).
2. Sections B–C via `git rm`, then `python -m unittest discover -s tests` (`test_repo_hygiene` walks the tree) and `ruff check` on nothing new.
3. Regenerate nothing: the 09-14 and 09-20 notebooks keep their rendered outputs.
