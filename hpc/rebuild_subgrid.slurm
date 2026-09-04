#!/bin/bash
# Rebuild the subgrid on the sealed template's frozen mesh with tiers prepended
# (scripts/rebuild_subgrid.py — every bed-* arm). Same footprint as the 08-26 probe:
# ~55 min, ~30 GB RSS on v3 for 10 levels; 20 levels roughly doubles the table.
#   NJ_DOMAIN=v3 sbatch hpc/rebuild_subgrid.slurm --dst _subgrid_buildings --tier bed_buildings_v3
#SBATCH -p main
# 🔴 halk* nodes cannot write to /cache/home and fail silently — see hpc/sfincs_run.slurm.
#SBATCH --exclude=halk[0001-0159]
#SBATCH -c 8
#SBATCH --mem=64G
#SBATCH -t 06:00:00
#SBATCH -J rebuild_sbg
#SBATCH -o logs/rebuild_subgrid_%j.out
set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
export PATH=$HOME/nj_sandy_sfincs/micromamba/envs/sfincs/bin:$PATH
export PYTHONPATH=$PWD NJ_ROOT=$PWD
export NJ_DOMAIN="${NJ_DOMAIN:?set NJ_DOMAIN in the submitting shell}"
export PROJ_DATA=/home/tpj8/nj_sandy_sfincs/micromamba/envs/sfincs/share/proj
hostname; date; echo "NJ_DOMAIN=$NJ_DOMAIN args: $*"
/usr/bin/time -v python scripts/rebuild_subgrid.py "$@"
date
