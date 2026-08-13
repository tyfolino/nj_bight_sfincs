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
# Target main-redhat (RHEL 9.6) — see hpc/amarel_bootstrap.md.
#SBATCH -p main-redhat
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
MM="$REPO/micromamba/bin/micromamba"
ENV="$REPO/micromamba/envs/sfincs"

# All cores for SnapWave (it scales across both sockets; run_sfincs interleaves
# memory). PROJ/GDAL data dirs for the GeoTIFF read/write in build + downscale.
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-1}"
export PROJ_LIB="$ENV/share/proj" PROJ_DATA="$ENV/share/proj" GDAL_DATA="$ENV/share/gdal"

echo "host=$(hostname)  job=${SLURM_JOB_ID:-none}  threads=$OMP_NUM_THREADS"
echo "args: $*"

# run_experiments.py runs each SFINCS solve locally via Singularity here (no
# nested sbatch), sequentially, then aggregates. Runs from the repo root so
# NJ_ROOT resolves and experiments/ lands next to model/.
"$MM" run -n sfincs python run_experiments.py "$@"

echo "done — see experiments/metrics.csv and experiments/report.html"
