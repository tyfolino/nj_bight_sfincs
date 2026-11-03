# The archives — `~/nj_coast_sfincs` and `~/nj_sandy_sfincs`

This repo is the only live one. Two predecessors stay on disk, frozen:

- **`~/nj_coast_sfincs`**: the predecessor project (code, data, docs, 26 campaign logs). Data and docs only.
- **`~/nj_sandy_sfincs`**: the first repo, demoted 2026-08-05 to the TOOLCHAIN's home (`micromamba/`, the
  `hydromt_sfincs` checkout, the engine builds and `.sif` images). It stays on disk because a conda env cannot
  move (its prefix is baked into scripts and data paths); as a repo it is retired.

**On GitHub** both are to be marked *archived* (read-only) by the user; checked 2026-11-03: no unpushed commits
in either, and the two hpc scripts edited in `nj_coast_sfincs`'s working tree are identical to this repo's copies.

## `~/nj_coast_sfincs`

Everything before this repo lives in **`~/nj_coast_sfincs`**, pinned at

```
commit 21e28f2197bdab39ec009ca5c660832e7d34e188
```

(working tree clean at the time of the freeze, 2026-08-13).

## The rule

> **The archive is referenced for DATA and DOCS only. Never for code.**

`data/` here symlinks into `~/nj_coast_sfincs/data/` for the read-only bulk (elevation,
roughness, waves, ERA5, precip, wind, discharge, validation, wavemakers) and, since
2026-10-05, into `/scratch/tpj8/nj_bight_sfincs_data/` for the v3 / v4 builds. Moving the
archive's share to a data directory this repo owns is plan Phase 1 step 2 (waits for an
empty queue: running jobs read through these links).
Nothing in `nj_sfincs/`, `scripts/`, `tests/` or `hpc/` may import from, exec, or add the
archive to `sys.path` — `tests/test_repo_hygiene.py` asserts this. The same rule
`CLAUDE.md` already applies to the toolchain repo, for the same reason: two copies of a
module is how you end up running the one you did not edit.

The archive should be **read-only on disk**. If it is not yet, make it so:

```bash
cd ~/nj_coast_sfincs && chmod -R a-w nj_sfincs scripts docs reports tests data *.md *.py
# to undo:  chmod -R u+w nj_sfincs scripts docs reports tests data *.md *.py
```

`experiments/` is deliberately left writable — the port verification in
`docs/STATUS.md` copies a run dir out of it, and the floodmap cache writes into whatever
directory it scores.

## What was NOT brought across

`data/frozen_mesh_v2_barnegat` (2.7 G) · `sfincs-env.tar.gz` (930 M) · `notebooks/` ·
`reports/` · `.git` (293 M for 11 commits, almost all of it committed notebook outputs).
`data/frozen_mesh_v1_monmouth` IS symlinked, for port verification only, and is dropped
when `v1_monmouth` is retired.

## Ported later

Scripts whose output is in Model 1.0.0's recipe, brought across with a note in their docstring:
`scripts/build_ehydro_south.py` (2026-11-03; `ehydro_south`, the Barnegat Bay channel carve). The other
builders the data catalog cites as "(archive; not ported)" build v1–v3 products 1.0.0 does not use
(the GTSM / NOAA tide corrections, the Barnegat bay-Manning test) and stay there.

## Index of the archived campaign logs

`~/nj_coast_sfincs/docs/campaigns/` holds 26 dated markdown files. **Read them as
history, not as fact** — they are reverse-chronological logs and several carry conclusions
that were later retracted, with the retraction sitting above the claim it retracts. What is
believed true *now* is in `docs/FINDINGS.md` here.

| file | what it investigated |
|---|---|
| `2026-06_bay_waves_plan.md` | how to get wave energy into the Sandy Hook Bay lee |
| `2026-06_bridge_dam.md` | the Rumson–Sea Bright bridge baked into the DEM as a dam |
| `2026-06_coned_upgrade.md` | ConEd wind/pressure forcing upgrade |
| `2026-06_hm0_spike_rootcause.md` | the SnapWave Hm0 spike |
| `2026-06_manning_nj.md` | NLCD → Manning reclass for NJ |
| `2026-06_snapwave_root_cause.md` | the first SnapWave blow-up (~1e13) |
| `2026-07_bay_tidal_amplification.md` | Raritan / Sandy Hook Bay tidal amplification |
| `2026-07_cora_evaluation.md` | CORA as a wave boundary vs ERA5 and NDBC 44025 |
| `2026-07_domain_expansion_v2.md` | building `v2_barnegat` |
| `2026-07_domain_rebuild.md` | the region fix + the sealed mesh |
| `2026-07_ehydro_carve_and_district_sign.md` | eHydro carves; the USACE district sign flip |
| `2026-07_hwm_estimator_artifact.md` | the `max`-over-window HWM estimator artefact |
| `2026-07_infragravity_closed.md` | infragravity waves — closed, null |
| `2026-07_inlet_waterlevel_clamp.md` | the ocean level imposed 2.6 km inside Barnegat Inlet |
| `2026-07_shrewsbury_reinvestigation.md` | the Shrewsbury mass leak (the biggest single file) |
| `2026-07_shrewsbury_underfill.md` | the behind-barrier estuary under-filling |
| `2026-07_snapwave_decoupling.md` | decoupling the SnapWave domain to −30 m |
| `2026-07_tidal_phase_lag.md` | the +18 min phase lag and its fixes |
| `2026-08_bay_volume_deficit.md` | Barnegat Bay: volume vs tilt decomposition |
| `2026-08_boundary_source_search.md` | GTSM / CoDEC / NACCS as water-level boundaries |
| `2026-08_bracket_manahawkin.md` | the deliberately inadmissible southern bracket |
| `2026-08_published_boundary_practice.md` | where published SFINCS studies draw the boundary |
| `2026-08_sandy_hook_gap.md` | the Sandy Hook gauge record gap |
| `2026-08_tide_anchor.md` | `tide-shift` vs `tide-anchor` vs `tide-gtsm` |
| `2026-08_usgs_bbleh_coawst.md` | the USGS BB-LEH COAWST model as a reference |
| `2026-08_wind_forcing.md` | ERA5 wind over the bay: land vs marine roughness |
| `README.md` | the campaign-log index |
| `_memory_archive/`, `retired_scripts/` | superseded memory files; retired one-off scripts |

Also in the archive and worth knowing about: `docs/naming.md` (the arm-naming convention
and the frozen v1 scoreboard — the scoreboard is **not** carried forward, it is n=19 under
the `max` estimator and comparable to nothing current) and `docs/roadmap.md`.
