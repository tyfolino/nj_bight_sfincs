#!/bin/bash
# Poster Figure 4, Sandy on the 2026 bed = Model 1.1.0's twin (2026-11-12, user: base on 1.1.0). ONE job: check the staged dir -> solve (production engine)
# -> weir / drain counts -> audit WHOLE -> native exposure read -> fig4_power_2026bed -> native floodmap (last).
# The arm was staged by hand on 11-12 (reports/poster_2026-11-13/job/stage_v11.log); if it is not staged, this job
# stages it. main PREEMPTS: on a requeue the arm is RE-STAGED FRESH and solved from the start, never resumed (a
# resumed waves-on / rain-on run is a different run, CLAUDE.md §4/§5).
#
#   cd ~/nj_bight_sfincs
#   md5sum <the files in reports/poster_2026-11-13/job/expected.md5> > reports/poster_2026-11-13/job/expected.md5
#   env EXPECT_MD5=reports/poster_2026-11-13/job/expected.md5 sbatch reports/poster_2026-11-13/run_fig4_2026bed.slurm
#SBATCH -J fig4_2026bed
#SBATCH -p main
#SBATCH --exclude=halk[0001-0159]
#SBATCH -N 1
#SBATCH -c 64
#SBATCH --mem=150G
#SBATCH -t 12:00:00
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH -o /cache/home/tpj8/nj_bight_sfincs/reports/poster_2026-11-13/job/run_fig4_2026bed_%j.out
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
    md5sum -c --quiet "$EXPECT_MD5" >/dev/null 2>&1 || { echo "⚠️ requeue: guarded files changed since submit — continuing:"; md5sum -c "$EXPECT_MD5" 2>&1 | grep -v ': OK$' || true; }
  else
    for i in $(seq 1 30); do md5sum -c --quiet "$EXPECT_MD5" && break; sleep 10; done
    md5sum -c --quiet "$EXPECT_MD5" || { md5sum -c "$EXPECT_MD5" | grep -v OK || true; echo "STALE FILES — refusing"; exit 3; }
  fi
else
  echo "🔴 no EXPECT_MD5 — refusing (the VS Code node's writes can read stale here)"; exit 3
fi

P=reports/poster_2026-11-13
ARM="bed-modernb+p4-premier+struct-pews-checkvalve+weir-elizabeth-rahway+weir-portmonmouth"
PAIR="p4-premier+weir-elizabeth-rahway"      # Model 1.1.0
export NJ_DOMAIN=v4_refreeze_swz_v11 SLURM_SUBMIT_DIR=$REPO
V=experiments/$NJ_DOMAIN; R=$V/$ARM; SG=_subgrid_modern2026b
WEIR=data/structures_v4/sfincs_modern_overpeck_open_elizabeth_rahway_portmonmouth_ground.weir
DRN=data/structures_v4/portmonmouth_pews_gate_checkvalve.drn
NWEIR=${NWEIR:?set NWEIR (the engine weir u/v count expected)}
export SFINCS_BIN=$(cat $REPO/hpc/production_engine.txt); unset SFINCS_SIF
[ -x "$SFINCS_BIN" ] || { echo "🔴 SFINCS_BIN=$SFINCS_BIN not executable"; exit 2; }
THREADS=${SLURM_CPUS_PER_TASK:-64}
step() { echo "== $1 $(date)"; /usr/bin/time -f "   $1: %e s  maxRSS %M KB" "${@:2}"; local rc=$?; [ "$rc" -eq 0 ] || echo "🔴 $1 exit $rc"; return $rc; }

whole() { python -m nj_sfincs.premier "$R" 2>/dev/null | grep -q "output WHOLE"; }
clean() { [ -f "$R/engine.txt" ] && [ ! -d "$R/restart_segments" ] && { [ ! -f "$R/restart_history.txt" ] || ! grep -q "resume from" "$R/restart_history.txt"; }; }

# ── 1. stage (only if needed) + checks ─────────────────────────────────────────────────────────────────────────
if whole && clean; then
  echo "== $ARM already solved WHOLE and clean — skipping to the read"
else
  if [ "${SLURM_RESTART_COUNT:-0}" -gt 0 ] || [ ! -f "$R/.staged_ok" ] || [ -f "$R/engine.txt" ] || [ -d "$R/restart_segments" ]; then
    rm -f "$R/.staged_ok"
    echo "== staging $ARM fresh"
    step stage python - "$ARM" > $P/job/stage_job.log 2>&1 <<'PY' || { tail -30 $P/job/stage_job.log; exit 8; }
import sys
from nj_sfincs.config import BaseConfig
import run_experiments as rx
print("staged", rx.prepare_experiment(sys.argv[1], BaseConfig()))
PY
  fi
  ok=1
  grep -qE "^dtrstout *= *21600" $R/sfincs.inp || { echo "🔴 dtrstout"; ok=0; }
  grep -qE "^snapwave *= *1" $R/sfincs.inp || { echo "🔴 not waves-on"; ok=0; }
  grep -qE "^netamprfile" $R/sfincs.inp || { echo "🔴 no rain"; ok=0; }
  grep -qE "^drnfile *= *sfincs.drn" $R/sfincs.inp || { echo "🔴 no drnfile key"; ok=0; }
  cmp -s $R/sfincs.weir $WEIR || { echo "🔴 weir != $WEIR"; ok=0; }
  cmp -s $R/sfincs.drn $DRN || { echo "🔴 drn != $DRN"; ok=0; }
  cmp -s $R/sfincs_subgrid.nc $V/$SG/sfincs_subgrid.nc || { echo "🔴 subgrid table != $SG's"; ok=0; }
  cmp -s $R/sfincs.nc $V/_template_sealed/sfincs.nc || { echo "🔴 sfincs.nc != the template's"; ok=0; }
  for f in sfincs_netamp.nc sfincs_netampr.nc sfincs_netamuv.nc sfincs_netbndbzsbzifile.nc sfincs_netsrcdisfile.nc \
           snapwave.bhs snapwave.btp snapwave.bwd snapwave.bds snapwave.bnd sfincs.wvm sfincs.obs \
           sfincs_ini_regional.bin roughness.nc sfincs_cnb.nc; do
    cmp -s $R/$f $V/$PAIR/$f || { echo "🔴 $f differs from 1.1.0's ($V/$PAIR)"; ok=0; }
  done
  d=$(diff <(grep = $V/$PAIR/sfincs.inp) <(grep = $R/sfincs.inp) | grep '^[<>]' | grep -v 'drnfile\|storeqdrain' || true)
  [ -z "$d" ] || { echo "🔴 sfincs.inp differs from 1.1.0's beyond drnfile / storeqdrain: $d"; ok=0; }
  [ "$ok" = 1 ] || { echo "🔴 staging checks failed — not solving"; exit 8; }
  date > $R/.staged_ok
  # ── 2. solve ─────────────────────────────────────────────────────────────────────────────────────────────────
  step solve env SLURM_CPUS_PER_TASK=$THREADS bash hpc/sfincs_run.slurm $R > $P/job/solve.log 2>&1 || { tail -30 $P/job/solve.log; exit 9; }
  tail -3 $P/job/solve.log
fi

# ── 3. counts + audit ─────────────────────────────────────────────────────────────────────────────────────────
grep -h "structure u/v points\|drainage points\|no matching active grid cell" $R/sfincs.log | tr -s ' ' | tee $P/job/structures.txt
n=$(grep -h "structure u/v points found" $R/sfincs.log | awk '{print $3}' | tail -1)
[ "${n:-x}" = "$NWEIR" ] && echo "   weir u/v $n = expected" || echo "🔴 weir u/v ${n:-none} != expected $NWEIR — READ WITH CARE (figure still made, flagged)"
grep -q "(1 drainage points found)" $R/sfincs.log && echo "   drainage: 1 point (the Pews check valve)" || echo "🔴 the drain point was not read as 1 point"
python -m nj_sfincs.premier $R | tee $P/job/audit.txt | tail -3
grep -q "output WHOLE" $P/job/audit.txt || { echo "🔴 not WHOLE — not reading"; exit 10; }
clean || { echo "🔴 resumed or unrecorded solve (CLAUDE.md §4/§5: a different run) — not reading"; cat $R/restart_history.txt; exit 11; }

# ── 4. exposure (native 3.125 m, pixels under each asset) + the figure ───────────────────────────────────────
step exposure python -u $P/exposure_poster.py $R $NJ_DOMAIN v11_modernb_2026bed > $P/exposure_2026.log 2>&1 || { tail -20 $P/exposure_2026.log; exit 12; }
tail -2 $P/exposure_2026.log
step figure python $P/fig4_power.py 2026 > $P/job/fig.log 2>&1 || { tail -20 $P/job/fig.log; exit 13; }
step compare python $P/compare_2012_2026.py > $P/exposure/changes_2012_vs_2026.txt 2>&1 || true
cat $P/exposure/changes_2012_vs_2026.txt

# ── 5. native floodmap of the whole run (last; the figure does not need it) ──────────────────────────────────
step floodmap python - "$R" <<'PY' || echo "⚠️ native floodmap failed (the figure is made; re-run by hand)"
import sys
from pathlib import Path
import nj_sfincs  # noqa: F401
from nj_sfincs.validate import core
core.load_floodmap(Path(sys.argv[1]))
print("native floodmap:", Path(sys.argv[1]) / "floodmap_hmax_lev3.tif")
PY
echo "== done $(date)"
