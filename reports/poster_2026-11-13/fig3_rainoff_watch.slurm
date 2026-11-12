#!/bin/bash
# Poster Figure 3 for the RAIN-OFF twin of Model 1.1.0, made as soon as job 63843110 has scored it.
#
# Waits (polling every 10 min) for logs/capemay_tests_2026-11-09/out/$ARM/scored_ok, then runs
# reports/poster_2026-11-13/fig3_motf.py --arm $ARM --stem fig3_motf. Gives up on FAILED, or when
# 63843110 has left the queue without a marker. Submit from the repo root:
#   md5sum reports/poster_2026-11-13/fig3_motf.py > reports/poster_2026-11-13/logs/fig3_watch_expected.md5
#   EXPECT_MD5=reports/poster_2026-11-13/logs/fig3_watch_expected.md5 sbatch --begin=19:00 reports/poster_2026-11-13/fig3_rainoff_watch.slurm
# Memory: the 1.1.0 stand-in peaked at 97.5 GB MaxRSS (logs/fig3_standin_v110.log), 6 min 20 s on 16 cores.
#SBATCH -J fig3_roff
#SBATCH -p main
#SBATCH --exclude=halk[0001-0159]
#SBATCH -N 1
#SBATCH -c 8
#SBATCH --mem=128G
#SBATCH -t 14:00:00
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH -o /cache/home/tpj8/nj_bight_sfincs/reports/poster_2026-11-13/logs/fig3_rainoff_watch_%j.out
set -uo pipefail
REPO=/cache/home/tpj8/nj_bight_sfincs
cd $REPO
ENV=${NJ_TOOLCHAIN:-$HOME/nj_sandy_sfincs}/micromamba/envs/sfincs
export PATH=$ENV/bin:$PATH PYTHONPATH=$REPO NJ_ROOT=$REPO NJ_DOMAIN=v4_refreeze_swz_v11 OMP_NUM_THREADS=8
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

ARM=p4-premier+rain-off+weir-elizabeth-rahway
M=logs/capemay_tests_2026-11-09/out/$ARM
WATCHED=63843110
while [ ! -f "$M/scored_ok" ]; do
  if [ -f "$M/FAILED" ]; then echo "🔴 $ARM FAILED in $WATCHED — no figure:"; cat "$M/FAILED"; exit 1; fi
  if ! squeue -h -j $WATCHED 2>/dev/null | grep -q .; then
    [ -f "$M/scored_ok" ] && break
    echo "🔴 job $WATCHED is gone and $ARM has no scored_ok — no figure"; exit 1
  fi
  echo "   $(date '+%F %T') waiting for $M/scored_ok"
  sleep 600
done
echo "== $ARM scored ($(cat $M/scored_ok)); making fig3_motf $(date)"
/usr/bin/time -v python -u reports/poster_2026-11-13/fig3_motf.py --arm "$ARM" --stem fig3_motf
rc=$?
echo "== done rc=$rc $(date)"
exit $rc
