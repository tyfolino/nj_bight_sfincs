#!/bin/bash
# Parallel, checkpointed subgrid rebuild (scripts/rebuild_subgrid_parallel.py) — the same
# arguments as hpc/rebuild_subgrid.slurm, bit-identical output, minutes instead of hours
# (logs/subgrid_parallel_2026-11-04/README.md). Workers = the CPUs below; memory ~8 GB
# per worker + ~20 GB on v4 (16 workers peaked at 140 GB), so 16 fit a 192 GB nonpre node.
#   NJ_DOMAIN=v4_refreeze_swz sbatch hpc/rebuild_subgrid_parallel.slurm --dst _subgrid_x --overlay <bed> ...
#   NJ_DOMAIN=v4_refreeze_swz sbatch -p main --requeue hpc/rebuild_subgrid_parallel.slurm ...   (preemptible is fine:
#   a requeue resumes from the per-block checkpoints; --force is added automatically on a restart)
#SBATCH -p nonpre
# 🔴 halk* nodes cannot write to /cache/home and fail silently — see hpc/sfincs_run.slurm.
#SBATCH --exclude=halk[0001-0159]
#SBATCH -c 16
#SBATCH --mem=170G
#SBATCH -t 03:00:00
#SBATCH -J rebuild_sbg_par
#SBATCH -o logs/rebuild_subgrid_par_%j.out
set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
export PATH=$HOME/nj_sandy_sfincs/micromamba/envs/sfincs/bin:$PATH
export PYTHONPATH=$PWD NJ_ROOT=$PWD
export NJ_DOMAIN="${NJ_DOMAIN:?set NJ_DOMAIN in the submitting shell}"
export PROJ_DATA=/home/tpj8/nj_sandy_sfincs/micromamba/envs/sfincs/share/proj
# EXPECT_MD5=<md5sum file written at submit time>: refuse to run stale copies (CLAUDE.md §5).
# A REQUEUE (preemption) re-runs this check: there it WARNS and continues.
EXTRA=()
if [ "${SLURM_RESTART_COUNT:-0}" -gt 0 ]; then
  EXTRA=(--force)  # resume: rebuild the dst from the template, reuse the finished blocks
fi
if [ -n "${EXPECT_MD5:-}" ]; then
  if [ "${SLURM_RESTART_COUNT:-0}" -gt 0 ]; then
    md5sum -c --quiet "$EXPECT_MD5" >/dev/null 2>&1 || { echo "⚠️ requeue (restart=$SLURM_RESTART_COUNT): guarded files changed since submit — continuing:"; md5sum -c "$EXPECT_MD5" 2>&1 | grep -v ': OK$' || true; }
  else
    md5sum -c "$EXPECT_MD5" || { echo "STALE FILES — refusing"; exit 3; }
  fi
fi
hostname; date; echo "NJ_DOMAIN=$NJ_DOMAIN args: $* ${EXTRA[*]}"
/usr/bin/time -v python -u scripts/rebuild_subgrid_parallel.py --workers "${SLURM_CPUS_PER_TASK:-16}" "$@" "${EXTRA[@]}"
date
