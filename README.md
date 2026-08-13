# nj_bight_sfincs

A SFINCS compound-flood hindcast of **Hurricane Sandy (28–31 October 2012)** on the New York
Bight, built with HydroMT-SFINCS. Compound means surge, wave setup, wind, rain and river
discharge together, validated against NOAA and USGS gauges, USGS high-water marks, and the
FEMA MOTF surge extent.

The model this repo exists to build, `v1_5_raritan`, **relocates the water-level boundary
out of Raritan Bay** so Lower Bay, Raritan Bay and Sandy Hook Bay are computed rather than
forced — one ocean arm around Sandy Hook plus two short forced cross-sections at the
Verrazzano Narrows and Arthur Kill.

## Start here

| | |
|---|---|
| [CLAUDE.md](CLAUDE.md) | the entry point: what this is for, the domain trap, how to run things |
| [docs/STATUS.md](docs/STATUS.md) | what is happening right now, and what is blocked |
| [docs/FINDINGS.md](docs/FINDINGS.md) | what is believed true now — no history, no retractions |
| [ARCHIVE.md](ARCHIVE.md) | the frozen predecessor repo and an index of its campaign logs |

## Quick start

```bash
export PATH=$HOME/nj_sandy_sfincs/micromamba/envs/sfincs/bin:$PATH
export PYTHONPATH=$PWD

python -m unittest discover -s tests    # 54 tests, ~2 s, no solver, no writes
python scripts/verify_port.py           # rescore an archived run, bit for bit
python -m nj_sfincs.premier             # audit every run dir on the active domain
```

The environment lives in `~/nj_sandy_sfincs` (micromamba, the `hydromt_sfincs` checkout and
the Singularity images), symlinked in. That directory is **toolchain only** — never point
`NJ_ROOT` or `PYTHONPATH` at it; `nj_sfincs/__init__.py` refuses if you do.

## Layout

```
nj_sfincs/     the package — domain registry, fingerprints, build, validation, plots
scripts/       data acquisition, staging, scoring, the port gate
tests/         stdlib unittest (pytest is deliberately not in the pinned env)
hpc/           SLURM batch scripts + the Amarel bootstrap
data/          symlinks into the archive for bulk; NACCS/ gtsm/ quadtree/ are local
experiments/   run dirs, gitignored, LOCAL — never a symlink
```
