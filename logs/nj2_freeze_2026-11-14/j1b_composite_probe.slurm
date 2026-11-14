#!/bin/bash
# J1b (nj2, 2026-11-14): after J1 (63918506), whose nj2-ring probes FAILED the domain invariants
# (the hole fill re-activated the declared sea; fixed in nj_sfincs/model.py `_inactive_components`).
#   1. the COMPOSITE coarse bed: bed_v4_coarse_25m wherever v4 has a pixel, J1's warp elsewhere
#      (composite_coarse_bed.py; J1's warp kept as bed_nj2_coarse_25m_warp.tif until the end), then
#      J1's check_coarse_bed.py, which must now read max |nj2 - v4| 0;
#   2. the refinement rebuild WITH the new-ground narrow channels (scripts/build_refinement_nj2.py,
#      reads the NHD cache data/nj2_design/nhd_new_area/, no network) + the same set WITHOUT them
#      into the probe dir (attribution);
#   3. three nj2 probes in parallel: c0_v4only (control: v4's recipe on the nj2 ring), f1_final
#      (the 2.0.0 file), f2_noext (2.0.0 minus the new-ground narrow channels). 🔴 FATAL on any
#      probe exception / missing "domain invariants OK" (probe_variant.py only PRINTS them);
#   4. summarise.py (faces per band, dt limiter, runtime) + j1b_compare.py (narrow-channel faces,
#      old-ground identity vs v4's frozen mesh, per-arm census).
# One job (few SLURM jobs), every step skip-if-done.
#   md5sum $(cat logs/nj2_freeze_2026-11-14/j1b_md5_files.txt) > logs/nj2_freeze_2026-11-14/j1b_expected.md5
#   NJ_DOMAIN=nj2 EXPECT_MD5=logs/nj2_freeze_2026-11-14/j1b_expected.md5 sbatch logs/nj2_freeze_2026-11-14/j1b_composite_probe.slurm
#SBATCH -J nj2_j1b
#SBATCH -p main
#SBATCH --exclude=halk[0001-0159]
#SBATCH -N 1
#SBATCH -c 4
#SBATCH --mem=80G
#SBATCH -t 2:00:00
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH -o /cache/home/tpj8/nj_bight_sfincs/logs/nj2_freeze_2026-11-14/j1b_composite_probe_%j.out
set -uo pipefail
REPO=/cache/home/tpj8/nj_bight_sfincs
cd $REPO
ENV=${NJ_TOOLCHAIN:-$HOME/nj_sandy_sfincs}/micromamba/envs/sfincs
export PATH=$ENV/bin:$PATH PYTHONPATH=$REPO NJ_ROOT=$REPO
export PROJ_LIB=$ENV/share/proj PROJ_DATA=$ENV/share/proj GDAL_DATA=$ENV/share/gdal
export GDAL_CACHEMAX=4096 TMPDIR=/scratch/tpj8/tmp; mkdir -p "$TMPDIR"
export NJ_DOMAIN="${NJ_DOMAIN:?set NJ_DOMAIN=nj2}"
[ "$NJ_DOMAIN" = nj2 ] || { echo "🔴 NJ_DOMAIN=$NJ_DOMAIN, this job is for nj2"; exit 3; }
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
L=logs/nj2_freeze_2026-11-14
R=logs/nj2_refinement_2026-11-14
SCR=/scratch/tpj8/nj_bight_sfincs_data/elevation_nj2
F=bed_nj2_coarse_25m.tif; WARP=bed_nj2_coarse_25m_warp.tif
J1_WARP_MD5=8dd909a1c0068b031bff0964966eddbc
P=/scratch/tpj8/nj2_refinement_probe/nj2_j1b; mkdir -p $P/inputs
OLD=/scratch/tpj8/nj2_refinement_probe/nj2

# 1. composite coarse bed ------------------------------------------------------------------
if [ -s $SCR/$F.composite.txt ] && [ -s $SCR/$F ]; then
  echo "== 1: composite exists — skipped"; cat $SCR/$F.composite.txt
else
  if [ ! -s $SCR/$WARP ]; then
    got=$(md5sum < $SCR/$F | cut -d' ' -f1)
    [ "$got" = "$J1_WARP_MD5" ] || { echo "🔴 $SCR/$F md5 $got is not J1's warp — refusing to move it"; exit 4; }
    mv $SCR/$F $SCR/$WARP
  fi
  python -u $L/composite_coarse_bed.py $SCR/$WARP data/elevation_v4/bed_v4_coarse_25m.tif $SCR/$F \
    || { echo "🔴 composite failed"; exit 4; }
fi
ls -lL data/elevation_nj2/$F
python -u $L/check_coarse_bed.py | tee $L/j1b_check_coarse_bed.txt || { echo "🔴 check failed"; exit 4; }
grep -q "max |nj2 - v4| 0.0000 m, n > 1 mm 0" $L/j1b_check_coarse_bed.txt || { echo "🔴 composite != v4 on the overlap"; exit 4; }

# 2. refinement: the 2.0.0 set (with the new-ground narrow channels) + the no-ext set -------
python -u scripts/build_refinement_nj2.py > $L/j1b_build_refinement.log 2>&1 || { tail -20 $L/j1b_build_refinement.log; echo "🔴 refinement build"; exit 5; }
python -u scripts/build_refinement_nj2.py --no-narrow-ext --out-dir $P/inputs > $L/j1b_build_refinement_noext.log 2>&1 || { tail -20 $L/j1b_build_refinement_noext.log; echo "🔴 no-ext build"; exit 5; }
sed -n '/narrow channels on the NEW ground/,/^new-band/p' $L/j1b_build_refinement.log
grep -E "narrow_channels|DROPPED|wrote" $L/j1b_build_refinement.log | head -12
md5sum data/nj2_design/refinement_nj2*.geojson $P/inputs/refinement_nj2.geojson

# 3. probes (parallel, single-threaded, ~22 min / ~13 G each) -----------------------------------
pids=()
for item in c0_v4only=data/nj2_design/refinement_nj2_v4only.geojson f1_final=data/nj2_design/refinement_nj2.geojson f2_noext=$P/inputs/refinement_nj2.geojson; do
  name=${item%%=*}; ref=${item#*=}
  if [ -s $P/$name/domain_dryrun.npz ] && grep -q "domain invariants OK" $L/j1b_probe_${name}.txt 2>/dev/null; then
    echo "== probe $name done — skipped"; continue
  fi
  rm -rf $P/$name
  ( /usr/bin/time -v python -u $R/probe_variant.py $ref $P/$name > $L/j1b_probe_${name}.txt 2>&1 ) &
  pids+=($!)
done
rc=0; for p in "${pids[@]}"; do wait $p || rc=1; done
bad=0
for name in c0_v4only f1_final f2_noext; do
  f=$L/j1b_probe_${name}.txt
  echo "== probe $name"
  grep -E "^\[probe\]|\[mask\] (inactive polygon|filled|no interior|region re-clip)|declared boundary arm|waterlevel +[0-9]+ cells|invariants|Elapsed|Maximum resident" $f | head -40
  if grep -qE "raised|Traceback|Error" $f || ! grep -q "domain invariants OK" $f || [ ! -s $P/$name/domain_dryrun.npz ]; then
    echo "🔴 probe $name: exception or no 'domain invariants OK'"; grep -E -A12 "raised|Traceback" $f | head -40; bad=1
  fi
done
[ $rc -eq 0 ] && [ $bad -eq 0 ] || { echo "🔴 a probe failed — stopping before the read-out"; exit 6; }

# 4. read-out -----------------------------------------------------------------------------------
C=$P/mesh_now_cache.npz
[ -s $C ] || cp $OLD/mesh_now_cache.npz $C 2>/dev/null || python - <<PY || { echo "🔴 mesh_now cache"; exit 7; }
import sys; from pathlib import Path
sys.path.insert(0, "$R"); import mesh_now; mesh_now.load(Path("$C"))
PY
python -u $R/summarise.py $P $P/c0_v4only/domain_dryrun.npz $C data/nj2_design/refinement_nj2.geojson c0_v4only f1_final f2_noext \
  > $L/j1b_probe_summary.txt 2>&1 || { cat $L/j1b_probe_summary.txt; echo "🔴 summarise"; exit 7; }
cat $L/j1b_probe_summary.txt
python -u $L/j1b_compare.py $P $C $P/inputs/refinement_nj2.geojson > $L/j1b_compare.txt 2>&1 || { cat $L/j1b_compare.txt; echo "🔴 compare"; exit 7; }
cat $L/j1b_compare.txt

# 5. clean as you go: J1's superseded warp + its failed probes (logs keep the record) ------------
rm -f $SCR/$WARP
rm -rf $OLD/n0_v4only $OLD/n1_final
echo "== done $(date)"
