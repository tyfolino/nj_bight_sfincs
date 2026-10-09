#!/bin/bash
# The 10-09 read in ONE job (few-jobs rule, 10-07): the re-frozen v4's first scores, the
# NACCS-wind pairs, re-freeze vs run B, v4 vs v3 on the shared fixes, and the SLR
# containment gate. B_* / v3fix_* marks were copied from the 10-07 read (same runs).
# Steps run serially; a failed step is logged and the next one runs.
#SBATCH -J v4rf_read
#SBATCH -p main
#SBATCH --exclude=halk[0001-0159]
#SBATCH -c 16
#SBATCH --mem=240G
#SBATCH -t 03:00:00
#SBATCH -o /cache/home/tpj8/nj_bight_sfincs/reports/v4_first_results_2026-10-09/jobs/combined_%j.out
set -o pipefail
REPO=/cache/home/tpj8/nj_bight_sfincs
JOBS=$REPO/reports/v4_first_results_2026-10-09/jobs
ENV=/home/tpj8/nj_sandy_sfincs/micromamba/envs/sfincs
cd $REPO
export PATH=$ENV/bin:$PATH PYTHONPATH=$REPO NJ_ROOT=$REPO
export PROJ_LIB=$ENV/share/proj PROJ_DATA=$ENV/share/proj GDAL_DATA=$ENV/share/gdal
export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-1}
echo "host=$(hostname) job=$SLURM_JOB_ID $(date)"
for i in $(seq 1 30); do md5sum -c --quiet $JOBS/expected.md5 && break; sleep 10; done
md5sum -c $JOBS/expected.md5 || { echo "STALE FILES — refusing"; exit 1; }

FAILED=()
step() {  # step <name> <cmd...>
    echo "== $1 $(date)"
    /usr/bin/time -f "%e s  maxRSS %M KB" "${@:2}" 2>&1 | grep -v -i "warning"
    local rc=${PIPESTATUS[0]}
    [ "$rc" -eq 0 ] || { echo "🔴 $1 exit $rc"; FAILED+=("$1"); }
}
P="--preset refreeze"

# 1. residuals for the four re-freeze runs (B_* / v3fix_* copied)
for lab in rf_on rf_off rfw_on rfw_off; do
    step res_$lab python -u scripts/v4_first_results.py residuals --label $lab $P
done

# 2. zsmax pairs (same mesh only: everything but the v3 pairs)
for pair in "rf_on rf_off" "rfw_off rf_off" "rfw_on rf_on" "rf_on B_on" "rf_off B_off"; do
    set -- $pair
    step zs_${1}_$2 python -u scripts/v4_first_results.py zsmax --a $1 --b $2 $P
done

# 3. report (tables, paired bootstrap, figures, summary)
step report python -u scripts/v4_first_results.py report $P

# 4. SLR containment gate: where the +2 / +3 m peak reaches the ring, vs +0 m
S=experiments/v4_refreeze/naccs-nowaves+rain-off+slr
NJ_DOMAIN=v4_refreeze step overflow python -u scripts/overflow_check.py \
    ${S}-0m ${S}-2m ${S}-3m --map --compare ${S}-0m

echo "== done $(date); failed steps: ${FAILED[*]:-none}"
[ ${#FAILED[@]} -eq 0 ]
