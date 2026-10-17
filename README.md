# nj_bight_sfincs

A SFINCS compound-flood hindcast of **Hurricane Sandy (28–31 October 2012)** on the New
Jersey coast, built with HydroMT-SFINCS. Compound means surge, wave setup, wind, rain and
river discharge together, validated against NOAA and USGS gauges, USGS high-water marks, and
the FEMA MOTF surge extent.

The model is built domain by domain. **v3** (Cape May to the Narrows, with Lower, Raritan and
Sandy Hook Bays computed rather than forced) is the finished reference. **v4** adds Delaware
Bay and river, the Raritan to Manville and Newark Bay; its current form is the registered
domain `v4_refreeze` (rivers cut at today's head of tide, SnapWave waves), on its way to a
declared premier. See [CLAUDE.md](CLAUDE.md) §1–§2.

## Start here

| | |
|---|---|
| [CLAUDE.md](CLAUDE.md) | the entry point: what this is for, the domain trap, how to run things |
| [docs/STATUS.md](docs/STATUS.md) | what is happening right now, and what is open |
| [docs/FINDINGS.md](docs/FINDINGS.md) | what is believed true now — no history, no retractions |
| [scripts/README.md](scripts/README.md) | every script, grouped by purpose, with its status |
| [ARCHIVE.md](ARCHIVE.md) | the frozen predecessor repo and an index of its campaign logs |

## Quick start

```bash
export PATH=$HOME/nj_sandy_sfincs/micromamba/envs/sfincs/bin:$PATH
export PYTHONPATH=$PWD

python -m unittest discover -s tests    # ~300 tests, a few minutes on a compute node, no solver
python scripts/verify_port.py           # rescore an archived run, bit for bit
NJ_DOMAIN=v3 python -m nj_sfincs.premier  # audit every run dir on that domain
```

On Amarel, run anything heavier than a quick read on a compute node (`srun`), not the
login node.

The environment lives in `~/nj_sandy_sfincs` (micromamba, the `hydromt_sfincs` checkout and
the Singularity images), symlinked in. That directory is **toolchain only** — never point
`NJ_ROOT` or `PYTHONPATH` at it; `nj_sfincs/__init__.py` refuses if you do.

## Reproducing the toolchain

| piece | where it is pinned |
|---|---|
| Python env (conda) | [env/sfincs-linux-64.lock.txt](env/sfincs-linux-64.lock.txt) — explicit, with md5s: `micromamba create -n sfincs --file env/sfincs-linux-64.lock.txt` |
| pip extras | [env/pip-extra.txt](env/pip-extra.txt) — `pip install --no-deps -r env/pip-extra.txt` |
| hydromt_sfincs | an EDITABLE install at commit `d8514d6` **plus a local fix** ([hpc/patches/quadtree_mixin_pad2.patch](hpc/patches/quadtree_mixin_pad2.patch): pads 1-cell quadtree slivers in the subgrid merge); steps in `env/pip-extra.txt` |
| SFINCS engine | native builds from [hpc/build_sfincs_native.sh](hpc/build_sfincs_native.sh) (gfortran 11.5) into `~/nj_sandy_sfincs/sfincs-native/<variant>/`; patches in `hpc/patches/` and [docs/upstream/](docs/upstream/). Every run records its engine in `engine.txt` and `metrics.csv` |

[environment.yml](environment.yml) is the loose, human-readable spec the env was first solved
from; the lock file is what reproduces it.

## Layout

```
nj_sfincs/     the package — domain registry, fingerprints, build, validation, plots
scripts/       flat; indexed in scripts/README.md
tests/         stdlib unittest (pytest is deliberately not in the pinned env)
hpc/           SLURM batch scripts + the Amarel bootstrap
data/          symlinks into the archive for bulk; NACCS/ gtsm/ quadtree/ are local
experiments/   run dirs, gitignored; a symlink to /scratch/tpj8 (not backed up, 90-day purge)
logs/          gitignored; dated campaign dirs, SLURM stdout under logs/slurm/<yyyy-mm>/
notebooks/     rendered notebooks, committed with their outputs
reports/       figures (gitignored), cleanup manifests, literature reviews
```
