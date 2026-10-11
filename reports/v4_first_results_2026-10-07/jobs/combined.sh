#!/bin/bash
# The whole Wednesday read in ONE job (2026-10-07: Amarel flagged too many pending jobs).
# Replaces 62291413 (run B validate) + 62305002–62305023 (11 residuals, 10 zsmax, report).
# Steps run serially; a failed step is logged and the next one runs (the report lists what
# is missing), as the old afterany report did.
#SBATCH -J v4fr_combined
#SBATCH -p main
#SBATCH --exclude=halk[0001-0159]
#SBATCH -c 32
#SBATCH --mem=400G
#SBATCH -t 08:00:00
#SBATCH -o /cache/home/tpj8/nj_bight_sfincs/reports/v4_first_results_2026-10-07/jobs/combined_%j.out
set -o pipefail
REPO=/cache/home/tpj8/nj_bight_sfincs
JOBS=$REPO/reports/v4_first_results_2026-10-07/jobs
ENV=/home/tpj8/nj_sandy_sfincs/micromamba/envs/sfincs
cd $REPO
export PATH=$ENV/bin:$PATH PYTHONPATH=$REPO NJ_ROOT=$REPO
export PROJ_LIB=$ENV/share/proj PROJ_DATA=$ENV/share/proj GDAL_DATA=$ENV/share/gdal
export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-1}
echo "host=$(hostname) job=$SLURM_JOB_ID $(date)"
# halk late-write trap (CLAUDE.md §5): wait for the files we were submitted with.
for i in $(seq 1 30); do md5sum -c --quiet $JOBS/expected.md5 && break; sleep 10; done
md5sum -c $JOBS/expected.md5 || { echo "STALE FILES — refusing"; exit 1; }

FAILED=()
step() {  # step <name> <cmd...>
    echo "== $1 $(date)"
    /usr/bin/time -f "%e s  maxRSS %M KB" "${@:2}" 2>&1 | grep -v -i "warning"
    local rc=${PIPESTATUS[0]}
    [ "$rc" -eq 0 ] || { echo "🔴 $1 exit $rc"; FAILED+=("$1"); }
}

# 1. run B validate (was 62291413). Everything with B in it reads its output.
NJ_DOMAIN=v4_hot_plus_walls step validate_B \
    python -u run_experiments.py --experiments naccs-premier --validate-only

# 2. residuals (were 62305002–62305012)
for lab in A_on A_off B_on B_off Aplus_base harbour v3 v3_off v3_dt3600 v3fix_on v3fix_off; do
    step res_$lab python -u scripts/v4_first_results.py residuals --label $lab --preset wednesday
done

# 3. zsmax pairs (were 62305013–62305022)
for pair in "A_on A_off" "B_on B_off" "B_on A_on" "B_off A_off" "A_off Aplus_base" \
            "v3 v3_off" "harbour Aplus_base" "v3fix_on v3_dt3600" "v3fix_off v3_off" \
            "v3fix_on v3fix_off"; do
    set -- $pair
    step zs_${1}_$2 python -u scripts/v4_first_results.py zsmax --a $1 --b $2 --preset wednesday
done

# 4. report (was 62305023)
step report python -u scripts/v4_first_results.py report --preset wednesday

echo "== done $(date); failed steps: ${FAILED[*]:-none}"
[ ${#FAILED[@]} -eq 0 ]
