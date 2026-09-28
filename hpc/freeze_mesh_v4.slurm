#!/bin/bash
# Build and FREEZE the v4 static mesh (grid + mask + subgrid) on scratch, then link it
# where BaseConfig.frozen_mesh looks (data/frozen_mesh_v4). 2026-09-28.
#
#   md5sum <inputs> > logs/<name>_expected.md5
#   EXPECT_MD5=logs/<name>_expected.md5 sbatch hpc/freeze_mesh_v4.slurm
#
# Sized on the 09-27 trial build (61932061, hal0398 emeraldrapids): 4 h 24, MaxRSS 89.8 G,
# 32 G written (subgrid/ 28 G). The output goes to SCRATCH — home is GPFS 100 G soft and
# a 32 G mesh there would fill it. freeze_mesh.py refuses to overwrite an existing mesh,
# so a requeued attempt clears its own partial output first.
#SBATCH -p main
#SBATCH --exclude=halk[0001-0159]
#SBATCH --constraint=emeraldrapids
#SBATCH -c 16
#SBATCH --mem=200G
#SBATCH -t 12:00:00
#SBATCH -J v4_freeze
#SBATCH -o logs/v4_freeze_%j.out
set -uo pipefail
cd "$SLURM_SUBMIT_DIR"
hostname; date
# Stale reads from the VS Code (halk) node — CLAUDE.md §5.
if [ -n "${EXPECT_MD5:-}" ]; then md5sum -c "$EXPECT_MD5" || { echo "STALE FILES — refusing"; exit 3; }; fi
export PATH=$HOME/nj_sandy_sfincs/micromamba/envs/sfincs/bin:$PATH
export PYTHONPATH=$PWD NJ_ROOT=$PWD NJ_DOMAIN=v4
export PROJ_DATA=/home/tpj8/nj_sandy_sfincs/micromamba/envs/sfincs/share/proj
export HDF5_USE_FILE_LOCKING=FALSE
OUT=/scratch/tpj8/nj_bight_sfincs_data/frozen_mesh_v4
LINK=data/frozen_mesh_v4
if [ -e "$LINK" ] && [ ! -L "$LINK" ]; then echo "$LINK exists and is not a symlink — refusing"; exit 4; fi
if [ -e "$OUT" ]; then echo "[requeue] clearing partial output at $OUT"; rm -rf "$OUT"; fi

/usr/bin/time -v python -u scripts/freeze_mesh.py "$OUT"
st=$?
du -sh "$OUT" "$OUT/subgrid" "$OUT/sfincs_subgrid.nc" 2>/dev/null
if [ $st -eq 0 ] && [ -f "$OUT/sfincs.inp" ]; then
    ln -sfn "$OUT" "$LINK"
    ls -la "$LINK"
    python - <<'PY'
from nj_sfincs import premier
fp = premier.domain_fingerprint("data/frozen_mesh_v4")
print(f"[fingerprint] v4 frozen mesh: {fp}")
ok, problems = premier.obs_points_ok("data/frozen_mesh_v4")
print(f"[obs] match registry: {ok} {problems}")
PY
fi
date
exit $st
