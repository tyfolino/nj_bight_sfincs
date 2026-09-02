#!/bin/bash
# Run the full wave-sensitivity sweep on a compute node: build the static model +
# forcing template ONCE, then build/run/validate every experiment and write
# experiments/metrics.csv + report.html. Self-contained — submit it and let your
# interactive node expire; this job stands on its own.
#
#   sbatch hpc/run_experiments.slurm                     # all 6 experiments
#   sbatch hpc/run_experiments.slurm --experiments igwaves,wavemaker
#   sbatch hpc/run_experiments.slurm --experiments baseline_no_waves --tstop 2012-10-29
#
# Any args after the script name pass straight through to run_experiments.py.
# Target `main` (main-redhat was merged INTO it 2026-08-20; submitting to main-redhat now
# fails outright) and exclude the halk* nodes, which cannot write /cache/home and whose
# late flushes clobber good runs (CLAUDE.md §5). Also used as the dependent VALIDATION job
# by hpc/stage_and_submit_v3.slurm (`--validate-only`, 128 G).
#SBATCH -p main
#SBATCH --exclude=halk[0001-0159]
#SBATCH -c 32
#SBATCH --mem=100G
#SBATCH -t 12:00:00
#SBATCH -J nj_sweep
#SBATCH -o logs/sweep_%j.out
#SBATCH -e logs/sweep_%j.out

set -euo pipefail
# Repo root is ALWAYS the submit dir — never an inherited $PROJ. See hpc/sfincs_run.slurm
# for why (the login profile exports PROJ=$HOME/nj_sandy_sfincs, the toolchain dir).
cd "${SLURM_SUBMIT_DIR:-$PWD}"
REPO="$PWD"
# The toolchain lives in the TOOLCHAIN repo, not this one (memory: reference_repo_layout).
TOOLCHAIN="${NJ_TOOLCHAIN:-$HOME/nj_sandy_sfincs}"
MM="$TOOLCHAIN/micromamba/bin/micromamba"
ENV="$TOOLCHAIN/micromamba/envs/sfincs"
export PYTHONPATH="$REPO" NJ_ROOT="$REPO"
# NJ_DOMAIN is inherited from the submitter's environment (sbatch exports it); default
# to the domain this script is used for when it is not set.
export NJ_DOMAIN="${NJ_DOMAIN:-v3}"

# All cores for SnapWave (it scales across both sockets; run_sfincs interleaves
# memory). PROJ/GDAL data dirs for the GeoTIFF read/write in build + downscale.
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-1}"
export PROJ_LIB="$ENV/share/proj" PROJ_DATA="$ENV/share/proj" GDAL_DATA="$ENV/share/gdal"

echo "host=$(hostname)  job=${SLURM_JOB_ID:-none}  threads=$OMP_NUM_THREADS"
echo "args: $*"

# run_experiments.py runs each SFINCS solve locally via Singularity here (no
# nested sbatch), sequentially, then aggregates. Runs from the repo root so
# NJ_ROOT resolves and experiments/ lands next to model/.
echo "domain=$NJ_DOMAIN"
"$MM" run -n sfincs python run_experiments.py "$@"

echo "done — see experiments/metrics.csv and experiments/report.html"
