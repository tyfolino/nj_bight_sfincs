#!/bin/bash
# Burn building footprints into an overlay elevation tier (scripts/burn_building_footprints.py)
# for the active domain; the subgrid rebuild (hpc/rebuild_subgrid.slurm --overlay) reads it.
#   NJ_DOMAIN=v4 sbatch hpc/burn_buildings.slurm --footprints <fgb> --out <tif>
# v3's burn took 144 s by hand; v4 reads the 2.9 M-footprint statewide layer.
#SBATCH -p main
# 🔴 halk* nodes cannot write to /cache/home and fail silently — see hpc/sfincs_run.slurm.
#SBATCH --exclude=halk[0001-0159]
#SBATCH -c 4
#SBATCH --mem=64G
#SBATCH -t 03:00:00
#SBATCH -J burn_bld
#SBATCH -o logs/burn_buildings_%j.out
set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
export PATH=${NJ_TOOLCHAIN:-$HOME/nj_sandy_sfincs}/micromamba/envs/sfincs/bin:$PATH
export PYTHONPATH=$PWD NJ_ROOT=$PWD
export NJ_DOMAIN="${NJ_DOMAIN:?set NJ_DOMAIN in the submitting shell}"
export PROJ_DATA=${NJ_TOOLCHAIN:-$HOME/nj_sandy_sfincs}/micromamba/envs/sfincs/share/proj
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
/usr/bin/time -v python scripts/burn_building_footprints.py "$@"
date
