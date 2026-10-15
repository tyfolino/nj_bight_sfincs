#!/bin/bash
# The 10-11 read in ONE job (few-jobs rule, 10-07): v4 vs the NACCS-wind v3 reference,
# like for like (v4 +rain-noinfil = v3 rain), plus the infiltration and wave pairs.
# pv4_* marks were copied from the 10-09 read (rfw_*, same runs renamed 10-11).
# Steps run serially; a failed step is logged and the next one runs.
#SBATCH -J v4_v3_read
#SBATCH -p main
#SBATCH --exclude=halk[0001-0159]
#SBATCH -c 16
#SBATCH --mem=240G
#SBATCH -t 03:00:00
#SBATCH -o /cache/home/tpj8/nj_bight_sfincs/reports/v4_first_results_2026-10-11/jobs/combined_%j.out
set -o pipefail
REPO=/cache/home/tpj8/nj_bight_sfincs
JOBS=$REPO/reports/v4_first_results_2026-10-11/jobs
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
P="--preset premier"

# 1. residuals for the four new runs (pv4_* copied)
for lab in ni_on ni_off v3n_on v3n_off; do
    step res_$lab python -u scripts/v4_first_results.py residuals --label $lab $P
done

# 2. zsmax pairs (same mesh only)
for pair in "ni_on pv4_on" "ni_off pv4_off" "ni_on ni_off" "v3n_on v3n_off"; do
    set -- $pair
    step zs_${1}_$2 python -u scripts/v4_first_results.py zsmax --a $1 --b $2 $P
done

# 3. report (tables, paired bootstrap, figures, summary)
step report python -u scripts/v4_first_results.py report $P


echo "== done $(date); failed steps: ${FAILED[*]:-none}"
[ ${#FAILED[@]} -eq 0 ]
