#!/bin/bash
# nj2 refinement: mesh-size probes, all variants in ONE job, in parallel (each ~20 min,
# ~13 G, single-threaded: v4's 09-27 probe 61932060). No subgrid, ~0.2 G of npz per probe.
#   PROBE_DOMAIN  v4 (default: the v4 ring + v4 coarse bed, everything but the Hudson strip)
#                 or nj2 (once registered with its coarse bed)
#   PROBE_SET     "name=refinement.geojson ..." (default: the v4-ring set below)
# Submit from the repo root:
#   md5sum <files> > logs/nj2_refinement_2026-11-14/probe_expected.md5
#   EXPECT_MD5=logs/nj2_refinement_2026-11-14/probe_expected.md5 sbatch logs/nj2_refinement_2026-11-14/probe.slurm
#SBATCH -J nj2_probe
#SBATCH -p main
#SBATCH --exclude=halk[0001-0159]
#SBATCH -N 1
#SBATCH -c 4
#SBATCH --mem=80G
#SBATCH -t 3:00:00
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH -o /cache/home/tpj8/nj_bight_sfincs/logs/nj2_refinement_2026-11-14/probe_%j.out
set -uo pipefail
REPO=/cache/home/tpj8/nj_bight_sfincs
cd $REPO
ENV=${NJ_TOOLCHAIN:-$HOME/nj_sandy_sfincs}/micromamba/envs/sfincs
export PATH=$ENV/bin:$PATH PYTHONPATH=$REPO NJ_ROOT=$REPO
export PROJ_LIB=$ENV/share/proj PROJ_DATA=$ENV/share/proj GDAL_DATA=$ENV/share/gdal
echo "== job=${SLURM_JOB_ID:-none} restart=${SLURM_RESTART_COUNT:-0} host=$(hostname) $(date)"
case "$(hostname)" in halk*) echo "🔴 on a halk node — refusing (CLAUDE.md §5)"; exit 3 ;; esac
if [ -n "${EXPECT_MD5:-}" ]; then
  if [ "${SLURM_RESTART_COUNT:-0}" -gt 0 ]; then
    md5sum -c --quiet "$EXPECT_MD5" >/dev/null 2>&1 || { echo "⚠️ requeue (restart=$SLURM_RESTART_COUNT): guarded files changed since submit — continuing:"; md5sum -c "$EXPECT_MD5" 2>&1 | grep -v ': OK$' || true; }
  else
    for i in $(seq 1 30); do md5sum -c --quiet "$EXPECT_MD5" && break; sleep 10; done
    md5sum -c --quiet "$EXPECT_MD5" || { md5sum -c "$EXPECT_MD5" | grep -v OK || true; echo "STALE FILES — refusing"; exit 3; }
  fi
else
  echo "🔴 no EXPECT_MD5 — refusing (the VS Code node's writes can read stale here)"; exit 3
fi

LOG=$REPO/logs/nj2_refinement_2026-11-14
export NJ_DOMAIN=${PROBE_DOMAIN:-v4}
OUT=/scratch/tpj8/nj2_refinement_probe/$NJ_DOMAIN
mkdir -p $OUT
SET=${PROBE_SET:-"p0_v4=data/quadtree/refinement_v4.geojson p1_base=$LOG/probe_inputs/v4ring.geojson p2_narrows50=$LOG/probe_inputs/v4ring_narrows50.geojson p3_inlets12=$LOG/probe_inputs/v4ring_inlets12.geojson"}
pids=()
for item in $SET; do
  name=${item%%=*}; ref=${item#*=}
  ( /usr/bin/time -v python -u $LOG/probe_variant.py $ref $OUT/$name > $LOG/probe_${NJ_DOMAIN}_${name}.txt 2>&1 ) &
  pids+=($!)
done
rc=0; for p in "${pids[@]}"; do wait $p || rc=1; done
for item in $SET; do name=${item%%=*}; echo "== $name"; grep "^\[probe\]" $LOG/probe_${NJ_DOMAIN}_${name}.txt; grep "Maximum resident\|Elapsed" $LOG/probe_${NJ_DOMAIN}_${name}.txt; done
echo "== done rc=$rc $(date)"
exit $rc
