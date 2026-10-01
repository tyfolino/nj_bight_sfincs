#!/bin/bash
# Stage one or more v3 arms on a hal node (never the halk vscode node — CLAUDE.md §5),
# hard-link the duplicated inputs, submit each solve through hpc/sfincs_run.slurm with
# the sealed engine passed explicitly, then queue ONE dependent validation job that
# scores the arms once every solve has finished. 2026-08-26; generalised 2026-09-02.
#
#   NJ_DOMAIN=v3 sbatch hpc/stage_and_submit_v3.slurm naccs-premier,naccs-nowaves  # comma-separated
#   NJ_DOMAIN=v3 SOLVE_TIME=08:00:00 SOLVE_MEM=64G sbatch hpc/stage_and_submit_v3.slurm wave-noig
#   NJ_DOMAIN=v4 VALIDATE=0 sbatch hpc/stage_and_submit_v3.slurm naccs-nowaves
#
# NJ_DOMAIN is REQUIRED (2026-10-01), like the arm list. The arm list is REQUIRED (2026-09-30): the old default named a retired arm and the v3
# reference run dir, which staging would destroy and re-stage.
#
# 🔴 DISK FIRST. Staging copies the 9.9 G template per arm BEFORE dedupe hard-links it
# back, the solve writes ~2.5 G of snapwave.upw + ~5 G of output, and validation adds a
# 2.4 G gallery floodmap — and the quota never says "quota", it truncates the write
# (STATUS 08-27: a 2.5 G floodmap cut off at 1.35 G, `sacct` COMPLETED). So refuse to
# stage with less than MIN_FREE_G of headroom to the HARD limit of the fileset that
# experiments/ resolves to (home 110 G; scratch 2 T since the 2026-09-03 move).
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
# 2026-09-28: any domain (the name stays). NJ_DOMAIN is required (2026-10-01).
export PYTHONPATH=$PWD NJ_ROOT=$PWD NJ_DOMAIN="${NJ_DOMAIN:?set NJ_DOMAIN in the submitting shell}"
echo "domain $NJ_DOMAIN"
hostname; date
# EXPECT_MD5=<file of `md5sum` lines, written at submit time> makes the job refuse to
# stage from files that still read STALE on this node (the halk write lag, CLAUDE.md §5).
if [ -n "${EXPECT_MD5:-}" ]; then md5sum -c "$EXPECT_MD5" || { echo "STALE FILES — refusing"; exit 3; }; fi
ARMS="${1:?give the arms to stage, comma-separated (no default since 2026-09-30)}"
# Measured 2026-09-01 on the rebuilt mesh: wave arms 5:10-5:17 wall, MaxRSS 12.8 G;
# waves-off 0:40 / 1.3 G. 12 h / 64 G is ~2x the worst case on both axes.
SOLVE_TIME="${SOLVE_TIME:-12:00:00}"
SOLVE_MEM="${SOLVE_MEM:-64G}"
# 2026-09-12: the patched wind-on engine runs ~1 sim-h per wall-h on icelake nodes and
# ~2.5 on emeraldrapids (STATUS 09-12 PM) — a 73 h window needs the fast nodes to fit 40 h.
# Set SOLVE_CONSTRAINT=emeraldrapids (sbatch --constraint) for any full wave arm.
SOLVE_CONSTRAINT="${SOLVE_CONSTRAINT:-}"
# The scorer downscales onto the finest subgrid DEM: v3 fits 128 G / 6 h; v4 (16 px, a
# 12.6 G lev3 raster) needs more — override per domain.
VALIDATE_MEM="${VALIDATE_MEM:-128G}"
VALIDATE_TIME="${VALIDATE_TIME:-06:00:00}"
MIN_FREE_G="${MIN_FREE_G:-15}"

# 2026-09-03: experiments/ is a symlink to /scratch (1 TB soft / 2 TB hard), so the
# guard checks whichever GPFS fileset the run dirs actually land on. The scratch row
# of mmlsquota has an extra "Fileset" column, so the used-blocks field is found by
# position relative to "USR", not by column number.
EXP_TARGET=$(realpath experiments)
case "$EXP_TARGET" in
    /scratch/*) QFS=scratch; HARD_G=2048 ;;
    *)          QFS=cache;   HARD_G=110 ;;
esac
USED_G=$(/usr/lpp/mmfs/bin/mmlsquota -u "$USER" --block-size G "$QFS" \
    | awk '{for (i = 1; i <= NF; i++) if ($i == "USR") {v = $(i+1); gsub("G", "", v); print int(v)}}')
FREE_G=$(( HARD_G - USED_G ))
echo "quota[$QFS] (experiments -> $EXP_TARGET): ${USED_G} G used of ${HARD_G} G hard -> ${FREE_G} G headroom (need ${MIN_FREE_G})"
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
/usr/lpp/mmfs/bin/mmlsquota -u $USER --block-size auto "$QFS" | tail -1 || true
JOBFILE="logs/stage_v3_${SLURM_JOB_ID:-local}.jobs"
ARMS="$ARMS" SOLVE_TIME="$SOLVE_TIME" SOLVE_MEM="$SOLVE_MEM" SOLVE_CONSTRAINT="$SOLVE_CONSTRAINT" JOBFILE="$JOBFILE" python - <<'PY'
import os
from nj_sfincs import run
from nj_sfincs.config import BaseConfig, exp_root
base = BaseConfig()
# SFINCS_BIN in the environment = the native engine (plan Phase 1b); else the container.
binary = os.environ.get("SFINCS_BIN") or None
sif = None if binary else str(base.container_sif)
print(f"[engine] {'bin:' + binary if binary else 'sif:' + sif}", flush=True)
ids = []
for arm in os.environ["ARMS"].split(","):
    d = exp_root() / arm
    extra = [f"--time={os.environ['SOLVE_TIME']}", f"--mem={os.environ['SOLVE_MEM']}"]
    if os.environ.get("SOLVE_CONSTRAINT"):
        extra.append(f"--constraint={os.environ['SOLVE_CONSTRAINT']}")
    job = run.submit_slurm(d, sif=sif, binary=binary, extra_args=extra + ["-J", f"{os.environ['NJ_DOMAIN']}_{arm}"])
    print(f"[submit] {arm} -> job {job}", flush=True)
    ids.append(str(job))
open(os.environ["JOBFILE"], "w").write(":".join(ids) + "\n")
PY
JOBS=$(cat "$JOBFILE")
echo "solve jobs: $JOBS"
# VALIDATE=0: solves only (2026-09-29: v4's validate OOMs at 400 G until the floodmap
# downscale is tiled — queuing it would only burn a big-memory node).
if [ "${VALIDATE:-1}" = "0" ]; then echo "validate: SKIPPED (VALIDATE=0)"; date; exit 0; fi
# One validation job for ALL the arms staged here, after every solve exits 0. ⚠️ The
# scorer's rasters ACCUMULATE across arms in one process: three v3 wave arms OOM'd at
# 128 G (MaxRSS 114 G, 2 h 12, nothing written) while one arm fits in 128 G. For 2+ arms
# raise VALIDATE_MEM (200 G) or validate one arm per job; v4 needs ~200 G for ONE arm.
# afterok means a failed or timed-out solve leaves this job pending forever — squeue
# shows it as DependencyNeverSatisfied; scancel it and read the solve log.
VJOB=$(sbatch --parsable --dependency=afterok:"$JOBS" --mem="$VALIDATE_MEM" --time="$VALIDATE_TIME" \
       -J "${NJ_DOMAIN}_validate" hpc/run_experiments.slurm --experiments "$ARMS" --validate-only)
echo "validate job: $VJOB (afterok:$JOBS)"
date
