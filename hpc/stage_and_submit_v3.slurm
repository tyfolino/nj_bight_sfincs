#!/bin/bash
# Stage the three v3 arms on a hal node (never the halk vscode node — CLAUDE.md §5),
# hard-link the duplicated inputs, then submit each solve through hpc/sfincs_run.slurm
# with the sealed engine passed explicitly. 2026-08-26.
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
ARMS="naccs-premier,wave-stwave,naccs-nowaves"
# stage only (--no-run rmtrees + re-stages each arm dir). A sealed template refuses
# --rebuild-template by design; when the frozen mesh changes (2026-08-26: it gained
# sfincs.obs + sfincs.weir, and add_forcing gained source snapping) DELETE
# experiments/v3/_template_sealed deliberately first and this rebuilds it.
python run_experiments.py --experiments "$ARMS" --no-run
python scripts/dedupe_experiment_inputs.py --apply
/usr/lpp/mmfs/bin/mmlsquota -u $USER --block-size auto cache | tail -1 || true
python - <<'PY'
from nj_sfincs import run
from nj_sfincs.config import BaseConfig, exp_root
base = BaseConfig()
for arm in ["naccs-premier", "wave-stwave", "naccs-nowaves"]:
    d = exp_root() / arm
    job = run.submit_slurm(d, sif=str(base.container_sif),
                           extra_args=["--time=30:00:00", "--mem=180G", "-J", f"v3_{arm}"])
    print(f"[submit] {arm} -> job {job}", flush=True)
PY
date
