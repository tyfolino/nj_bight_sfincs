#!/bin/bash
# Build subgrid/dep_subgrid_merged.tif for ONE subgrid dir (scripts/build_merged_subgrid_dep.py)
# and hard-link it into every run dir named after it, so the floodmap downscale sees the
# all-level bed. Exists because a `bed-*` arm scored on the lev3-only raster once
# (STATUS 2026-09-08): the fallback in validate.load_floodmap is silent by design.
#   NJ_DOMAIN=v3 sbatch hpc/merge_subgrid_dep.slurm experiments/v3/_subgrid_buildings experiments/v3/bed-buildings
# Block-streamed, so memory is small; the premier's merge ran in well under an hour.
#SBATCH -p main
# 🔴 halk* nodes cannot write to /cache/home and fail silently — see hpc/sfincs_run.slurm.
#SBATCH --exclude=halk[0001-0159]
#SBATCH -c 4
#SBATCH --mem=32G
#SBATCH -t 03:00:00
#SBATCH -J merge_dep
#SBATCH -o logs/merge_dep_%j.out
set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
export PATH=$HOME/nj_sandy_sfincs/micromamba/envs/sfincs/bin:$PATH
export PYTHONPATH=$PWD NJ_ROOT=$PWD
export NJ_DOMAIN="${NJ_DOMAIN:?set NJ_DOMAIN in the submitting shell}"
export PROJ_DATA=/home/tpj8/nj_sandy_sfincs/micromamba/envs/sfincs/share/proj
SRC="$1"; shift
hostname; date; echo "NJ_DOMAIN=$NJ_DOMAIN src=$SRC link into: $*"
/usr/bin/time -v python scripts/build_merged_subgrid_dep.py --subgrid-dir "$SRC/subgrid"
for d in "$@"; do
  ln -f "$SRC/subgrid/dep_subgrid_merged.tif" "$d/subgrid/dep_subgrid_merged.tif"
  echo "linked -> $d/subgrid/dep_subgrid_merged.tif"
done
ls -li "$SRC/subgrid/dep_subgrid_merged.tif" "$@"/subgrid/dep_subgrid_merged.tif 2>/dev/null || true
date
