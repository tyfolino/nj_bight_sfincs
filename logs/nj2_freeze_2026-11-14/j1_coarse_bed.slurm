#!/bin/bash
# J1 (nj2, 2026-11-14): the 25 m COARSE bed for the nj2 ring (refinement gating + face z), read-only
# checks against bed_v4_coarse_25m, then the refinement re-clip on the REGISTERED ring + line
# (scripts/build_refinement_nj2.py) and the nj2 MESH PROBE (the refinement agent's probe_variant.py,
# two variants in parallel: v4's recipe alone = the control, and the 2.0.0 file) + its summary.
# One job (few SLURM jobs), every step skip-if-done. Sized: coarse bed (v4, job 61926825) 1 min 50 s,
# 4.2 G; each probe ~22 min, ~13 G, single-threaded (logs/nj2_refinement_2026-11-14/ README).
# The probe's per-arm census brackets the hudson / hell_gate arms before the freeze.
#   md5sum <files> > logs/nj2_freeze_2026-11-14/j1_expected.md5
#   NJ_DOMAIN=nj2 EXPECT_MD5=logs/nj2_freeze_2026-11-14/j1_expected.md5 sbatch logs/nj2_freeze_2026-11-14/j1_coarse_bed.slurm
#SBATCH -J nj2_coarse
#SBATCH -p main
#SBATCH --exclude=halk[0001-0159]
#SBATCH -N 1
#SBATCH -c 4
#SBATCH --mem=64G
#SBATCH -t 3:00:00
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH -o /cache/home/tpj8/nj_bight_sfincs/logs/nj2_freeze_2026-11-14/j1_coarse_bed_%j.out
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
D=data/elevation_nj2; F=bed_nj2_coarse_25m.tif
SCR=/scratch/tpj8/nj_bight_sfincs_data/elevation_nj2
mkdir -p "$SCR"
[ -e "$D/$F" ] || [ -L "$D/$F" ] || ln -s "$SCR/$F" "$D/$F"
python - <<'PY' || { echo "🔴 nj2 not registered / ring stale"; exit 4; }
from nj_sfincs import domain as D
d = D.active(); D.assert_buildable(d)
assert d.coarse_elevation_list == ({"elevation": "bed_nj2_coarse_25m"},), d.coarse_elevation_list
assert d.elevation_list == D.V4_ELEVATION_LIST
print("nj2 registered, ring = its CSV, coarse key", d.coarse_elevation_list)
PY
# 1. the coarse bed (build_coarse_bed.py writes atomically: a .tmp then os.replace)
if [ -s "$SCR/$F" ]; then echo "== 1: $F exists — skipped"
else
  /usr/bin/time -v python -u scripts/build_coarse_bed.py || { echo "🔴 build_coarse_bed failed"; exit 5; }
fi
ls -lL "$D/$F"; md5sum "$SCR/$F"
# 2. checks (read-only)
python -u $L/check_coarse_bed.py || { echo "🔴 check failed"; exit 6; }
# 3. refinement re-clip on the registered ring + line (the refinement agent's builder; rewrites
#    data/nj2_design/refinement_nj2*.geojson — they are md5-guarded at submit, so a change shows here)
R=logs/nj2_refinement_2026-11-14
md5sum data/nj2_design/refinement_nj2.geojson data/nj2_design/refinement_nj2_v4only.geojson
python -u scripts/build_refinement_nj2.py > $L/j1_build_refinement.log 2>&1 || { tail -20 $L/j1_build_refinement.log; echo "🔴 refinement build"; exit 7; }
grep -E "DROPPED|CHANGED|NEW|added|narrows_cut" $L/j1_build_refinement.log | head -40
md5sum data/nj2_design/refinement_nj2.geojson data/nj2_design/refinement_nj2_v4only.geojson
# 4. the nj2 mesh probe: control (v4's recipe on the nj2 ring) and the 2.0.0 file, in parallel
P=/scratch/tpj8/nj2_refinement_probe/nj2; mkdir -p $P
pids=()
for item in n0_v4only=data/nj2_design/refinement_nj2_v4only.geojson n1_final=data/nj2_design/refinement_nj2.geojson; do
  name=${item%%=*}; ref=${item#*=}
  if [ -s $P/$name/domain_dryrun.npz ]; then echo "== probe $name done — skipped"; continue; fi
  ( /usr/bin/time -v python -u $R/probe_variant.py $ref $P/$name > $L/j1_probe_${name}.txt 2>&1 ) &
  pids+=($!)
done
rc=0; for p in "${pids[@]}"; do wait $p || rc=1; done
for name in n0_v4only n1_final; do
  echo "== probe $name"; grep -E "^\[probe\]|\[mask\]|arm |boundary|invariant|Maximum resident|Elapsed" $L/j1_probe_${name}.txt | head -60
done
[ $rc -eq 0 ] || { echo "🔴 a probe failed"; exit 8; }
# 5. summary (faces per band, global time step, runtime estimate)
C=$P/mesh_now_cache.npz
python - <<PY || echo "⚠️ mesh_now cache build failed"
import sys; from pathlib import Path
sys.path.insert(0, "$R"); import mesh_now; mesh_now.load(Path("$C"))
PY
python -u $R/summarise.py $P $P/n0_v4only/domain_dryrun.npz $C data/nj2_design/refinement_nj2.geojson n0_v4only n1_final \
  > $L/j1_probe_summary.txt 2>&1 || echo "⚠️ summarise exit != 0"
cat $L/j1_probe_summary.txt
# per-arm BC cell census on the 2.0.0 mesh (the brackets for hudson / hell_gate)
NPZ=$P/n1_final/domain_dryrun.npz python - <<'PY' | tee $L/j1_arm_census.txt
import os, numpy as np
from nj_sfincs import domain as D
d = np.load(os.environ["NPZ"]); dom = D.active()
m, x, y = d["mask"], d["x"], d["y"]
print(f"faces {m.size:,}; active {(m > 0).sum():,}; mask2 {(m == 2).sum():,}; mask3 {(m == 3).sum():,}")
claimed = np.zeros(m.size, bool)
for a in dom.boundary_arms:
    sel = a.contains(x, y) & (m == 2); claimed |= sel
    print(f"  arm {a.name:20s} {int(sel.sum()):6d}  (bracket {a.min_cells}..{a.max_cells})")
print(f"  mask2 outside every arm: {int(((m == 2) & ~claimed).sum())}")
for o in dom.mask_overrides:
    if o.name in ("wall_e88", "wall_hellgate_east"):
        x0, y0, x1, y1 = o.box; sel = (x > x0) & (x < x1) & (y > y0) & (y < y1) & (m > 0)
        print(f"  {o.name}: {int(sel.sum())} active faces in box, of them mask3 {int((sel & (m == 3)).sum())}")
PY
echo "== done $(date)"
