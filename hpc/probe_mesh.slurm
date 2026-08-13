#!/bin/bash
# Cell-count probe for a candidate refinement recipe.
#
#   sbatch hpc/probe_mesh.slurm [out_dir]
#
# Runs build_static(skip_subgrid=True): grid + elevation + mask + boundaries, but
# NOT the subgrid. That is the whole point — the face count is decided by the
# grid and mask, while the subgrid is the expensive step. So a refinement recipe
# can be measured in minutes and tuned, and the full freeze paid for once.
#
# Lighter than hpc/build_mesh.slurm precisely because the subgrid (the memory
# peak) is skipped, but the elevation merge still reads every tier across the
# whole domain, so this is not a toy allocation.
#
#SBATCH -p main-redhat
#SBATCH -c 16
#SBATCH --mem=120G
#SBATCH -t 03:00:00
#SBATCH -J njprobe
#SBATCH -o logs/probe_%j.out
#SBATCH -e logs/probe_%j.out

set -euo pipefail

cd "${SLURM_SUBMIT_DIR:-$PWD}"
# Repo root is ALWAYS the submit dir. Do NOT reuse an inherited variable here:
# this account exports PROJ=/home/tpj8/nj_sandy_sfincs (the TOOLCHAIN dir) in its shell
# profile, so the `PROJ="${PROJ:-$PWD}"` idiom silently pointed
# PYTHONPATH at the OTHER repo and imported the wrong nj_sfincs package.
REPO="$PWD"
OUT="${1:-data/probe_mesh}"

PY="$REPO/micromamba/envs/sfincs/bin/python"
export NJ_ROOT="$REPO"
export PYTHONPATH="$REPO"
export NJ_DOMAIN="${NJ_DOMAIN:-v2_barnegat}"
export HDF5_USE_FILE_LOCKING=FALSE
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-1}"

echo "host=$(hostname)  job=${SLURM_JOB_ID:-none}  domain=$NJ_DOMAIN  repo=$REPO  cpus=$OMP_NUM_THREADS"
echo

time "$PY" scripts/probe_mesh_size.py "$OUT"
