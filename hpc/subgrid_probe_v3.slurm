#!/bin/bash
# Measure the v3 SUBGRID build (peak RSS, wall, sfincs.sbg size) on a hal* node.
# One-off probe, 2026-08-26. Result belongs in docs/STATUS.md.
#SBATCH -p main
#SBATCH --exclude=halk[0001-0159]
#SBATCH -c 8
#SBATCH --mem=64G
#SBATCH -t 12:00:00
#SBATCH -J sbg_probe_v3
#SBATCH -o logs/subgrid_probe_v3_%j.out
set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
export PATH=$HOME/nj_sandy_sfincs/micromamba/envs/sfincs/bin:$PATH
export PYTHONPATH=$PWD NJ_ROOT=$PWD NJ_DOMAIN=v3
hostname; date
/usr/bin/time -v python -c "
from dataclasses import replace; import nj_sfincs
from nj_sfincs import model; from nj_sfincs.config import ROOT, BaseConfig
model.build_static(replace(BaseConfig(), frozen_mesh=None), ROOT/'experiments/v3/_subgrid_probe')
"
date; ls -l experiments/v3/_subgrid_probe/*.nc || true
