#!/bin/bash
# Skeleton for a NEW job script (a campaign's logs/<campaign>/test.slurm): copy it, then
# fill in the steps. It carries the two guards every job here needs (CLAUDE.md §5):
#   - no halk node (late writes clobber good output);
#   - EXPECT_MD5: on the FIRST start, retry 5 min for the VS Code node's lagged writes, then
#     refuse on a mismatch; on a REQUEUE (preemption, SLURM_RESTART_COUNT > 0) check ONCE and
#     WARN-and-continue — an edit made while the job ran must not kill it (2026-11-04: job
#     63524748 lost 3.5 h to an additive edit). Keep both `|| true`s: under
#     `set -e` + pipefail a failing `md5sum -c | grep` exits the job before the next command.
# Inline this block; do not `source` it from a shared file — a sourced file is itself a
# lagged read, and an empty one skips the check silently.
# Submit from the repo root:
#   md5sum <every file the job reads> > logs/<campaign>/expected.md5
#   EXPECT_MD5=logs/<campaign>/expected.md5 sbatch logs/<campaign>/test.slurm
#SBATCH -J CHANGE_ME
#SBATCH -p main
#SBATCH --exclude=halk[0001-0159]
#SBATCH -N 1
#SBATCH -c 8
#SBATCH --mem=32G
#SBATCH -t 4:00:00
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH -o /cache/home/tpj8/nj_bight_sfincs/logs/CHANGE_ME/test_%j.out
set -uo pipefail
REPO=/cache/home/tpj8/nj_bight_sfincs
cd $REPO
ENV=${NJ_TOOLCHAIN:-$HOME/nj_sandy_sfincs}/micromamba/envs/sfincs
export PATH=$ENV/bin:$PATH PYTHONPATH=$REPO NJ_ROOT=$REPO
export PROJ_LIB=$ENV/share/proj PROJ_DATA=$ENV/share/proj GDAL_DATA=$ENV/share/gdal
echo "== job=${SLURM_JOB_ID:-none} restart=${SLURM_RESTART_COUNT:-0} host=$(hostname) $(date)"
case "$(hostname)" in halk*) echo "🔴 on a halk node — refusing (CLAUDE.md §5)"; exit 3 ;; esac
if [ -n "${EXPECT_MD5:-}" ]; then
  if [ "${SLURM_RESTART_COUNT:-0}" -gt 0 ]; then
    md5sum -c --quiet "$EXPECT_MD5" >/dev/null 2>&1 || { echo "⚠️ requeue (restart=$SLURM_RESTART_COUNT): guarded files changed since submit — continuing:"; md5sum -c "$EXPECT_MD5" 2>&1 | grep -v ': OK$' || true; }
  else
    for i in $(seq 1 30); do md5sum -c --quiet "$EXPECT_MD5" && break; sleep 10; done
    md5sum -c --quiet "$EXPECT_MD5" || { md5sum -c "$EXPECT_MD5" | grep -v OK || true; echo "STALE FILES — refusing"; exit 3; }
  fi
else
  echo "🔴 no EXPECT_MD5 — refusing (the VS Code node's writes can read stale here)"; exit 3
fi
# Steps go here. Make each one idempotent (skip when its output exists): a requeue re-runs
# the script from the top.
