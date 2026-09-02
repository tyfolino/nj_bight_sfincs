#!/bin/bash
# Stage one or more v3 arms on a hal node (never the halk vscode node — CLAUDE.md §5),
# hard-link the duplicated inputs, submit each solve through hpc/sfincs_run.slurm with
# the sealed engine passed explicitly, then queue ONE dependent validation job that
# scores the arms once every solve has finished. 2026-08-26; generalised 2026-09-02.
#
#   sbatch hpc/stage_and_submit_v3.slurm                       # the three 08-26 arms
#   sbatch hpc/stage_and_submit_v3.slurm diag-premier-norain   # one arm
#   SOLVE_TIME=08:00:00 SOLVE_MEM=64G sbatch hpc/stage_and_submit_v3.slurm wave-stwave
#
# 🔴 DISK FIRST. Staging copies the 9.9 G template per arm BEFORE dedupe hard-links it
# back, the solve writes ~2.5 G of snapwave.upw + ~5 G of output, and validation adds a
# 2.4 G gallery floodmap — and the quota never says "quota", it truncates the write
# (STATUS 08-27: a 2.5 G floodmap cut off at 1.35 G, `sacct` COMPLETED). So refuse to
# stage with less than MIN_FREE_G of headroom to the 110 G HARD limit.
#SBATCH -p main
#SBATCH --exclude=halk[0001-0159]
#SBATCH -c 8
#SBATCH --mem=64G
#SBATCH -t 04:00:00
#SBATCH -J stage_v3
#SBATCH -o logs/stage_v3_%j.out
set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
export PATH=$HOME/nj_sandy_sfincs/micromamba/envs/sfincs/bin:$PATH
export PYTHONPATH=$PWD NJ_ROOT=$PWD NJ_DOMAIN=v3
hostname; date
ARMS="${1:-naccs-premier,wave-stwave,naccs-nowaves}"
# Measured 2026-09-01 on the rebuilt mesh: wave arms 5:10-5:17 wall, MaxRSS 12.8 G;
# waves-off 0:40 / 1.3 G. 12 h / 64 G is ~2x the worst case on both axes.
SOLVE_TIME="${SOLVE_TIME:-12:00:00}"
SOLVE_MEM="${SOLVE_MEM:-64G}"
MIN_FREE_G="${MIN_FREE_G:-15}"

HARD_G=110
USED_G=$(/usr/lpp/mmfs/bin/mmlsquota -u "$USER" --block-size G cache | awk '/USR/ {gsub("G","",$3); print $3}')
FREE_G=$(( HARD_G - USED_G ))
echo "quota: ${USED_G} G used of ${HARD_G} G hard -> ${FREE_G} G headroom (need ${MIN_FREE_G})"
if [ "$FREE_G" -lt "$MIN_FREE_G" ]; then
    echo "REFUSING to stage: ${FREE_G} G headroom < ${MIN_FREE_G} G. Reclaim first" >&2
    echo "(scripts/dedupe_home.py --apply; regenerable experiments/v3/floodmaps/*.tif)." >&2
    exit 2
fi

# stage only (--no-run rmtrees + re-stages each arm dir). A sealed template refuses
# --rebuild-template by design; when the frozen mesh changes (2026-08-26: it gained
# sfincs.obs + sfincs.weir, and add_forcing gained source snapping) DELETE
# experiments/v3/_template_sealed deliberately first and this rebuilds it.
python run_experiments.py --experiments "$ARMS" --no-run
python scripts/dedupe_experiment_inputs.py --apply
/usr/lpp/mmfs/bin/mmlsquota -u $USER --block-size auto cache | tail -1 || true
JOBFILE="logs/stage_v3_${SLURM_JOB_ID:-local}.jobs"
ARMS="$ARMS" SOLVE_TIME="$SOLVE_TIME" SOLVE_MEM="$SOLVE_MEM" JOBFILE="$JOBFILE" python - <<'PY'
import os
from nj_sfincs import run
from nj_sfincs.config import BaseConfig, exp_root
base = BaseConfig()
ids = []
for arm in os.environ["ARMS"].split(","):
    d = exp_root() / arm
    job = run.submit_slurm(d, sif=str(base.container_sif),
                           extra_args=[f"--time={os.environ['SOLVE_TIME']}",
                                       f"--mem={os.environ['SOLVE_MEM']}", "-J", f"v3_{arm}"])
    print(f"[submit] {arm} -> job {job}", flush=True)
    ids.append(str(job))
open(os.environ["JOBFILE"], "w").write(":".join(ids) + "\n")
PY
JOBS=$(cat "$JOBFILE")
echo "solve jobs: $JOBS"
# One validation job for ALL the arms staged here, after every solve exits 0. The scorer
# unpacks ~60 G of rasters per arm, so one job, sequential, 128 G (STATUS 09-01 ops note).
# afterok means a failed or timed-out solve leaves this job pending forever — squeue
# shows it as DependencyNeverSatisfied; scancel it and read the solve log.
VJOB=$(sbatch --parsable --dependency=afterok:"$JOBS" --mem=128G --time=06:00:00 \
       -J "v3_validate" hpc/run_experiments.slurm --experiments "$ARMS" --validate-only)
echo "validate job: $VJOB (afterok:$JOBS)"
date
