#!/bin/bash
# Run a SFINCS solve in the Singularity container as a batch job.
#   sbatch hpc/sfincs_run.slurm [model_dir]   (default: model_quadtree)
# Target partition is `main`. ⚠️ CHANGED 2026-08-20: Amarel consolidated `main-redhat`
# INTO `main`, and submitting to `main-redhat` now fails outright with "invalid partition
# specified". The old warning that `main` was CentOS 7 (glibc 2.17) no longer holds — the
# hal[0097-0446] / halk[0001-0159] RHEL 9.6 nodes are what `main` now contains (verified:
# this repo's own session runs on hal0339 under 5.14.0-570.30.1.el9_6).
# 🔴 The halk exclusion below matters MORE after this change, not less: all 159 halk nodes
# now sit in the DEFAULT partition. See hpc/amarel_bootstrap.md and CLAUDE.md §5.
#SBATCH -p main
# 🔴 THE halk* NODES CANNOT WRITE TO /cache/home — AND THEY FAIL SILENTLY.
# A job landing there is allocated, runs, and exits `COMPLETED 0:0` having produced NOTHING:
# no sfincs_map.nc, no sfincs_his.nc, and not even its own SLURM stdout file, so there is no
# error message anywhere to find. `sacct` says COMPLETED and the run dir just still holds
# its inputs. On 2026-08-14 this ate five submissions before the node column was noticed;
# a 2 GB `--wrap 'hostname; touch ...'` probe pinned to halk0064 returned COMPLETED 0:0 in
# 8 s with no output file and no marker, while the same probe on hal0338 worked.
# 154 of the 494 nodes in main-redhat are halk*, so ~31% of submissions hit this by chance.
# Evidence is 5/5 halk failures vs 3/3 hal successes — the whole class is excluded until
# someone demonstrates otherwise. Re-check with the probe above before removing this line.
#SBATCH --exclude=halk[0001-0159]
#SBATCH -c 64
#SBATCH --mem=64G
# Wave-enabled (SnapWave) solves of the 3-day Sandy window take 1:40-2:05 wall; the old
# 1 h limit silently TIMEOUTed the 2026-07-20 phaselag runs at ~80% of the window. A v3
# SnapWave band solve is 6-30 h — pass --time explicitly (run.submit_slurm extra_args).
# Since 2026-09-10 a run staged with `dtrstout` resumes from its newest restart file on a
# requeue (see below), so a TIMEOUT or preemption costs at most one restart interval.
#SBATCH -t 03:00:00
#SBATCH -J sfincs
#SBATCH -o logs/sfincs_%j.out
#SBATCH -e logs/sfincs_%j.out
# The `main` partition PREEMPTS (2026-09-10: two 40 h solves thrown off hal0351/hal0346 in
# the same second, 21 h and 19 h in). --requeue lets SLURM put a preempted/node-failed job
# back in the queue automatically instead of killing it. On the requeue this script asks
# nj_sfincs/restart.py what to do: a run staged with `dtrstout` (every arm since 09-10)
# RESUMES from its newest restart file — the earlier output is parked in restart_segments/
# and stitched back into ONE sfincs_map.nc / sfincs_his.nc after the solve — and a run
# without one re-runs from scratch as before. SLURM_RESTART_COUNT counts the requeues.
#SBATCH --requeue

set -euo pipefail

# The repo root is ALWAYS the submit dir. Do NOT read an inherited $PROJ: this account's
# login profile exports PROJ=$HOME/nj_sandy_sfincs (the TOOLCHAIN dir), so the old
# `PROJ="${PROJ:-$PWD}"` idiom resolved to the wrong repo whenever the variable happened to
# be set — which on an interactive node it always is. It also did no real work: the PROJ
# library reads PROJ_LIB / PROJ_DATA, never PROJ.
#
# ⚠️ NOT `dirname "${BASH_SOURCE[0]}"` here. sbatch copies the batch script into the slurmd
# spool directory and runs it from there, so BASH_SOURCE points at /var/spool/... — the
# self-location idiom is right for hpc/*.sh but wrong for a .slurm file.
cd "${SLURM_SUBMIT_DIR:-$PWD}"
REPO="$PWD"

MODEL="${1:-model_quadtree}"
# 🔴 THE ENGINE IS ALWAYS EXPLICIT (2026-09-11, plan Phase 1b). Exactly one of
#   SFINCS_SIF=/path/to/image.sif   (container)  or
#   SFINCS_BIN=/path/to/sfincs      (native build, hpc/build_sfincs_native.sh)
# must be exported by the submitter — nj_sfincs.run.submit_slurm does. The old fallback
# to a hard-coded image in the repo (Galibier, v2.4.0) silently ran a DIFFERENT engine than the
# sealed premier's (Faber, v2.3.3, sfincs-desktop.sif) and is gone: a job with no engine,
# or two, exits 2 here, before it touches the model dir.
SIF="${SFINCS_SIF:-}"
BIN="${SFINCS_BIN:-}"
if [ -n "$SIF" ] && [ -n "$BIN" ]; then
    echo "REFUSING: both SFINCS_SIF and SFINCS_BIN are set — pick one engine" >&2; exit 2
fi
if [ -z "$SIF" ] && [ -z "$BIN" ]; then
    echo "REFUSING: no engine — export SFINCS_SIF=<image.sif> or SFINCS_BIN=<sfincs binary>" >&2; exit 2
fi
if [ -n "$SIF" ] && [ ! -f "$SIF" ]; then echo "REFUSING: SFINCS_SIF=$SIF not found" >&2; exit 2; fi
if [ -n "$BIN" ] && [ ! -x "$BIN" ]; then echo "REFUSING: SFINCS_BIN=$BIN is not executable" >&2; exit 2; fi
# A native binary carries its netCDF rpath (build_sfincs_native.sh); SFINCS_BIN_LIBDIR is
# the override for a binary that does not.
if [ -n "$BIN" ] && [ -n "${SFINCS_BIN_LIBDIR:-}" ]; then
    export LD_LIBRARY_PATH="$SFINCS_BIN_LIBDIR:${LD_LIBRARY_PATH:-}"
fi
ENGINE="${SIF:+sif:$SIF}${BIN:+bin:$BIN}"

export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-1}"
# 🔴 STACK. SFINCS/SnapWave size Fortran automatic arrays by the face count. At v1.5's
# 696k faces one such array is 5.6 MB and fits the 8 MB default stack; at v3's 3.31 M
# faces it is 26 MB and the solver SIGSEGVs at start-up (2026-08-26: all three v3 arms,
# the waves-off one in 14 s with an EMPTY sfincs.log, the wave arms right after the
# SnapWave banner at 11 GB RSS — nowhere near the 180 G allocation). Singularity
# inherits the caller's rlimits; OMP_STACKSIZE covers the worker threads' own stacks.
ulimit -s unlimited || ulimit -s $(ulimit -H -s)
export OMP_STACKSIZE="${OMP_STACKSIZE:-1G}"
echo "stack: ulimit -s $(ulimit -s)  OMP_STACKSIZE=$OMP_STACKSIZE"

echo "host=$(hostname)  job=${SLURM_JOB_ID:-none}  threads=$OMP_NUM_THREADS"
echo "model=$MODEL  engine=$ENGINE"
# Resume support (nj_sfincs/restart.py). `prepare` is a no-op on a fresh run; on a requeue
# it retires the partial output and rewrites sfincs.inp to start from the newest restart
# file; `finish` stitches the pieces back and restores the inp. Both are safe to run on a
# dir that needs neither. The host env python is used — the container only has SFINCS.
PY="${NJ_PYTHON:-$HOME/nj_sandy_sfincs/micromamba/envs/sfincs/bin/python}"
export PYTHONPATH="$REPO"
if [ "${SLURM_RESTART_COUNT:-0}" -gt 0 ]; then
    echo "NOTE: this job was requeued (restart #${SLURM_RESTART_COUNT})."
fi
ACTION=$("$PY" "$REPO/scripts/sfincs_restart.py" prepare "$MODEL" | tail -n 1)
# "finish" means the map already reaches tstop. On a REQUEUE (or with segments parked) that
# is a job that died mid-stitch, so only the stitch is owed. On a first attempt it is a
# deliberate re-run of a completed dir — solve again, as before.
if [ "$ACTION" = "finish" ] && [ "${SLURM_RESTART_COUNT:-0}" -eq 0 ] && [ ! -d "$MODEL/restart_segments" ]; then
    ACTION=fresh
fi
echo "restart plan: $ACTION"

# Singularity runs as the calling user, so no root-owned-output cleanup is needed
# (unlike the old Docker workflow).
# Dual-socket nodes: interleave memory across both NUMA domains so the SnapWave solver
# (which scales with cores, ~1.6x at 48 vs 16) isn't bottlenecked on one socket's memory.
NUMA=""
command -v numactl >/dev/null 2>&1 && NUMA="numactl --interleave=all"
if [ "$ACTION" != "finish" ]; then
    if [ -n "$BIN" ]; then
        # Same rlimits / OMP env as the container path; SFINCS writes sfincs.log in cwd.
        ( cd "$MODEL" && $NUMA "$BIN" )
    else
        $NUMA singularity run --bind "$(realpath "$MODEL")":/data --pwd /data "$SIF"
    fi
else
    echo "solve already reached tstop before this requeue — stitching only."
fi
"$PY" "$REPO/scripts/sfincs_restart.py" finish "$MODEL"
# The engine record: engine.txt + an [engine] block in provenance.txt (label, sha256,
# Build-Revision, host, job, restart count). collect_metrics stamps it onto the row.
if [ -n "$BIN" ]; then
    "$PY" "$REPO/scripts/record_engine.py" "$MODEL" --bin "$BIN"
else
    "$PY" "$REPO/scripts/record_engine.py" "$MODEL" --sif "$SIF"
fi
