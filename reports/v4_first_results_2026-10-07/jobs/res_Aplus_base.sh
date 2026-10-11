#!/bin/bash
#SBATCH -J v4fr_res_Aplus_base
#SBATCH -p main
#SBATCH --exclude=halk[0001-0159]
#SBATCH -c 4
#SBATCH --mem=236G
#SBATCH -t 03:00:00
#SBATCH -o /cache/home/tpj8/nj_bight_sfincs/reports/v4_first_results_2026-10-07/jobs/res_Aplus_base_%j.out
set -eo pipefail
cd /cache/home/tpj8/nj_bight_sfincs
export PATH=/home/tpj8/nj_sandy_sfincs/micromamba/envs/sfincs/bin:$PATH PYTHONPATH=/cache/home/tpj8/nj_bight_sfincs
export PROJ_DATA=/home/tpj8/nj_sandy_sfincs/micromamba/envs/sfincs/share/proj
echo "host=$(hostname) job=$SLURM_JOB_ID $(date)"
# halk late-write trap (CLAUDE.md §5): wait for the files we were submitted with.
for i in $(seq 1 30); do md5sum -c --quiet /cache/home/tpj8/nj_bight_sfincs/reports/v4_first_results_2026-10-07/jobs/expected.md5 && break; sleep 10; done
md5sum -c /cache/home/tpj8/nj_bight_sfincs/reports/v4_first_results_2026-10-07/jobs/expected.md5
/usr/bin/time -f "%e s  maxRSS %M KB" python -u /cache/home/tpj8/nj_bight_sfincs/scripts/v4_first_results.py residuals --label Aplus_base --preset wednesday 2>&1 | grep -v -i "warning"
echo "== done $(date)"
