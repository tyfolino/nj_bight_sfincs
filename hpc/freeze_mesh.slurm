#!/bin/bash
# Build and FREEZE a domain's static mesh (grid + mask + subgrid) on scratch, then link it
# where BaseConfig.frozen_mesh looks (data/frozen_mesh_<domain>). Written for v4 on
# 2026-09-28 (as freeze_mesh_v4.slurm); domain-generic since 2026-09-30.
#
#   md5sum <inputs> > logs/<name>_expected.md5
#   NJ_DOMAIN=<domain> EXPECT_MD5=logs/<name>_expected.md5 sbatch hpc/freeze_mesh.slurm
#
# Sized on v4 (the 09-27 trial build, hal0398 emeraldrapids): 4 h 24, MaxRSS 89.8 G,
# 32 G written (subgrid/ 28 G); the real freeze took 4 h 39 / 72 G. The output goes to
# SCRATCH — home is GPFS 100 G soft and a 32 G mesh there would fill it.
# freeze_mesh.py refuses to overwrite an existing mesh. A REQUEUED attempt clears its own
# PARTIAL output (a dir with no sfincs.inp); a COMPLETE mesh is never removed here.
#SBATCH -p main
#SBATCH --exclude=halk[0001-0159]
#SBATCH --constraint=emeraldrapids
#SBATCH -c 16
#SBATCH --mem=200G
#SBATCH -t 12:00:00
#SBATCH -J freeze_mesh
#SBATCH -o logs/freeze_mesh_%j.out
set -uo pipefail
cd "$SLURM_SUBMIT_DIR"
hostname; date
: "${NJ_DOMAIN:?set NJ_DOMAIN — this script freezes one registered domain}"
echo "NJ_DOMAIN=$NJ_DOMAIN"
# Stale reads from the VS Code (halk) node — CLAUDE.md §5.
if [ -n "${EXPECT_MD5:-}" ]; then md5sum -c "$EXPECT_MD5" || { echo "STALE FILES — refusing"; exit 3; }; fi
export PATH=$HOME/nj_sandy_sfincs/micromamba/envs/sfincs/bin:$PATH
export PYTHONPATH=$PWD NJ_ROOT=$PWD NJ_DOMAIN
export PROJ_DATA=/home/tpj8/nj_sandy_sfincs/micromamba/envs/sfincs/share/proj
export HDF5_USE_FILE_LOCKING=FALSE
OUT=/scratch/tpj8/nj_bight_sfincs_data/frozen_mesh_${NJ_DOMAIN}
LINK=data/frozen_mesh_${NJ_DOMAIN}
if [ -e "$LINK" ] && [ ! -L "$LINK" ]; then echo "$LINK exists and is not a symlink — refusing"; exit 4; fi
if [ -e "$OUT/sfincs.inp" ]; then
    echo "$OUT already holds a complete mesh — refusing (move it aside deliberately to re-freeze)"
    exit 5
fi
if [ -e "$OUT" ]; then echo "[requeue] clearing PARTIAL output at $OUT"; rm -rf "$OUT"; fi

/usr/bin/time -v python -u scripts/freeze_mesh.py "$OUT"
st=$?
du -sh "$OUT" "$OUT/subgrid" "$OUT/sfincs_subgrid.nc" 2>/dev/null
if [ $st -eq 0 ] && [ -f "$OUT/sfincs.inp" ]; then
    ln -sfn "$OUT" "$LINK"
    ls -la "$LINK"
    LINK="$LINK" python - <<'PY'
import os

from nj_sfincs import premier
link = os.environ["LINK"]
fp = premier.domain_fingerprint(link)
print(f"[fingerprint] {os.environ['NJ_DOMAIN']} frozen mesh: {fp}")
ok, problems = premier.obs_points_ok(link)
print(f"[obs] match registry: {ok} {problems}")
PY
fi
date
exit $st
