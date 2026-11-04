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
# EXPECT_MD5=<md5sum file written at submit time>: refuse to run stale copies (CLAUDE.md §5).
# A REQUEUE (preemption) re-runs this check: there it WARNS and continues (2026-11-04).
if [ -n "${EXPECT_MD5:-}" ]; then
  if [ "${SLURM_RESTART_COUNT:-0}" -gt 0 ]; then
    md5sum -c --quiet "$EXPECT_MD5" >/dev/null 2>&1 || { echo "⚠️ requeue (restart=$SLURM_RESTART_COUNT): guarded files changed since submit — continuing:"; md5sum -c "$EXPECT_MD5" 2>&1 | grep -v ': OK$' || true; }
  else
    md5sum -c "$EXPECT_MD5" || { echo "STALE FILES — refusing"; exit 3; }
  fi
fi
hostname; date; echo "NJ_DOMAIN=$NJ_DOMAIN args: $*"
/usr/bin/time -v python scripts/rebuild_subgrid.py "$@"
date
