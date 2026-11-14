#!/bin/bash
# J3 (nj2 = Model 2.0, drafted 2026-11-14): the 2.0 DESIGN GATE on nj2_bed2012, as v4's first runs were —
# waves-off Sandy, rain off, at +0 / +2 / +3 m on the boundary, staged + solved + read in ONE job (few SLURM
# jobs), every step skip-if-done (a requeue resumes: waves-off / rain-off runs resume cleanly from their
# restart files, CLAUDE.md §4). DRAFT — NOT SUBMITTED. Runs after J2 pass 2 + GATE 2 (nj2_bed2012 registered
# with its sha) and once experiments._NJ2_NACCS_SUPPORT holds J2 step 4's count.
#   arms (nj_sfincs/experiments.py, EXPERIMENTS_BY_DOMAIN["nj2_bed2012"]), in run order:
#     p4-nowaves+rain-off+slr-0m          (1.1.0's premier weirs: the SMOKE run + the clean +0 BASELINE)
#     p4-nowaves+rain-off+slr-2m, …-3m    (1.1.0's weirs; the leak hunt, each --compare the clean +0)
#     p4-nowaves+rain-off+slr-0m+struct-cohansey-checkvalve+weir-dikes-levees   (the edges agent's fixed
#         dikes / levees set + the Cohansey check valve; read as a PAIRED comparison against the clean +0)
#   read: scripts/overflow_check.py <run> --map --compare <clean +0 run>  (edge categories, wet outflow /
#         walls, margins), premier audit (output WHOLE), weir u/v from sfincs.log, restart_history.
# Compute (measured on 1.1.0's mesh, production engine …swomp-2-gf11: waves-off 72 h Sandy = 5,705 s at 64
# threads, bed-v12a+p4-nowaves on hal0384; nj2 +2.5 % faces; +2 / +3 m wet more ground, assume x1.2 / x1.4):
#   ~1.7 + 2.0 + 2.3 + 1.7 h solve + 4 x ~15 min staging + ~25 min reads = ~9 h on an emeraldrapids 64-core
#   node; limit 16 h (~1.7 x). Memory: solver ~30-40 G (5 M faces), staging / overflow_check < 60 G -> 200 G.
# Disk: each staging copies the template (~40 G transient) and dedupe links it back (-> ~5 G); each run writes
#   ~8-11 G of map/his -> net +~55 G, peak +~95 G on scratch.
# Submit (repo root):
#   md5sum $(cat logs/nj2_freeze_2026-11-14/j3_md5_files.txt) > logs/nj2_freeze_2026-11-14/j3_expected.md5
#   NJ_DOMAIN=nj2_bed2012 EXPECT_MD5=logs/nj2_freeze_2026-11-14/j3_expected.md5 sbatch logs/nj2_freeze_2026-11-14/j3_gate_nj2.slurm
#SBATCH -J nj2_gate
#SBATCH -p main
#SBATCH --exclude=halk[0001-0159]
#SBATCH --constraint=emeraldrapids
#SBATCH -N 1
#SBATCH -c 64
#SBATCH --mem=200G
#SBATCH -t 16:00:00
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH -o /cache/home/tpj8/nj_bight_sfincs/logs/nj2_freeze_2026-11-14/j3_%j.out
set -uo pipefail
REPO=/cache/home/tpj8/nj_bight_sfincs
cd $REPO
ENV=${NJ_TOOLCHAIN:-$HOME/nj_sandy_sfincs}/micromamba/envs/sfincs
export PATH=$ENV/bin:$PATH PYTHONPATH=$REPO NJ_ROOT=$REPO
export PROJ_LIB=$ENV/share/proj PROJ_DATA=$ENV/share/proj GDAL_DATA=$ENV/share/gdal
export HDF5_USE_FILE_LOCKING=FALSE
export NJ_DOMAIN="${NJ_DOMAIN:?set NJ_DOMAIN=nj2_bed2012}"
[ "$NJ_DOMAIN" = nj2_bed2012 ] || { echo "🔴 NJ_DOMAIN=$NJ_DOMAIN — the gate runs on nj2_bed2012"; exit 3; }
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
export SFINCS_BIN=$(cat hpc/production_engine.txt)
unset SFINCS_SIF
L=logs/nj2_freeze_2026-11-14
EXP=experiments/nj2_bed2012
CHECKS=$L/J3_CHECKS.txt
note() { echo "$*" | tee -a $CHECKS; }
die() { note "🔴 REFUSING: $*"; exit 4; }
note "==== J3 job ${SLURM_JOB_ID:-none} restart ${SLURM_RESTART_COUNT:-0} $(date)  engine $SFINCS_BIN"
ARM0="p4-nowaves+rain-off+slr-0m"                       # clean +0: 1.1.0's premier weirs, the baseline
ARMD="p4-nowaves+rain-off+slr-0m+struct-cohansey-checkvalve+weir-dikes-levees"   # dike set, paired vs ARM0
ARMS="$ARM0 p4-nowaves+rain-off+slr-2m p4-nowaves+rain-off+slr-3m $ARMD"

python - <<'PY' || die "preconditions"
import sys
from nj_sfincs import domain as D, premier, experiments as X
d = D.active(); bad = []
if d.name not in premier.EXPECTED: bad.append("nj2_bed2012 has no fingerprint (GATE 2 not done)")
elif not premier.is_sealed(premier.sealed_template()): bad.append("template is not on the registered sha")
if X._NJ2_NACCS_SUPPORT is None: bad.append("experiments._NJ2_NACCS_SUPPORT is None (J2 step 4's count)")
for n, e in X.experiments().items():
    for f in (e.weir_from, e.drn_from):
        if f is not None and not f.exists(): bad.append(f"{n}: {f} missing")
print("\n".join("🔴 " + b for b in bad) or "preconditions OK")
sys.exit(1 if bad else 0)
PY
/usr/lpp/mmfs/bin/mmlsquota -u tpj8 --block-size G scratch 2>/dev/null | tail -1 | \
  awk '{u=$4+0; printf "scratch: %s G used, soft %s, hard %s\n", u, $5, $6; if (u + 150 > $6+0) exit 1}' \
  | tee -a $CHECKS || die "scratch within 150 G of the hard limit"

for A in $ARMS; do
  D=$EXP/$A
  # stage (prepare_experiment rmtree's the arm dir: only when it holds no solver output)
  if [ -f $D/sfincs.inp ] && [ -f $D/.j3_staged ]; then note "== $A: staged — skipped"
  else
    [ -e $D/sfincs_map.nc ] && die "$A: $D holds solver output but no .j3_staged marker — read it by hand"
    note "== stage $A $(date '+%T')"
    python -u - "$A" >> $L/j3_stage.log 2>&1 <<'PY' || die "staging $A ($L/j3_stage.log)"
import sys
import run_experiments as R
from nj_sfincs.config import BaseConfig
print("staged", R.prepare_experiment(sys.argv[1], BaseConfig()))
PY
    grep -q "^dtrstout" $D/sfincs.inp || die "$A: no dtrstout"
    grep -E "^(weirfile|drnfile|inifile|snapwave|precipfile|netamprfile)" $D/sfincs.inp | sed "s/^/   $A: /" | tee -a $CHECKS
    python -m nj_sfincs.premier $D 2>&1 | tail -2 | tee -a $CHECKS
    touch $D/.j3_staged
    python scripts/dedupe_experiment_inputs.py --apply >> $L/j3_dedupe.log 2>&1 || note "⚠️ dedupe exit != 0"
  fi
  # solve (resumable; skipped when the audit already reads the output WHOLE)
  # captured first, then grepped: `premier | grep -q` under pipefail can SIGPIPE premier and read a
  # finished run as not whole (a needless re-solve)
  AUD=$(python -m nj_sfincs.premier $D 2>&1)
  if grep -q "output WHOLE" <<< "$AUD"; then note "== $A: output WHOLE — skipped"
  else
    note "== solve $A $(date '+%T')"
    bash hpc/sfincs_run.slurm $D > $L/j3_solve_$(echo $A | tr '+' '_').log 2>&1 || die "solve $A"
  fi
  python -m nj_sfincs.premier $D 2>&1 | tail -2 | tee -a $CHECKS
  grep -h "structure u/v\|drainage" $D/sfincs.log | head -3 | sed "s/^/   $A: /" | tee -a $CHECKS
  grep -h "Total time" $D/sfincs.log | sed "s/^/   $A: /" | tee -a $CHECKS
  [ -f $D/restart_history.txt ] && tail -2 $D/restart_history.txt | sed "s/^/   $A: /" | tee -a $CHECKS
done

# the gate read (read-only on the runs; writes overflow_check.csv / .png into each). Every comparison is
# against the CLEAN +0 (1.1.0's weirs): +2 / +3 = what the sea level adds; the dike-set +0 = what the new
# weirs + check valve change at the same sea level (a paired comparison, same forcing).
python scripts/overflow_check.py $EXP/$ARM0 --map > $L/j3_overflow_0m.txt 2>&1 || note "⚠️ overflow_check +0 exit != 0"
for m in 2 3; do
  python scripts/overflow_check.py $EXP/p4-nowaves+rain-off+slr-${m}m --map --compare $EXP/$ARM0 \
    > $L/j3_overflow_${m}m.txt 2>&1 || note "⚠️ overflow_check +${m} exit != 0"
done
python scripts/overflow_check.py $EXP/$ARMD --map --compare $EXP/$ARM0 \
  > $L/j3_overflow_0m_dikes.txt 2>&1 || note "⚠️ overflow_check dike-set +0 exit != 0"
tail -25 $L/j3_overflow_*m.txt $L/j3_overflow_0m_dikes.txt >> $CHECKS
/usr/lpp/mmfs/bin/mmlsquota -u tpj8 --block-size G scratch 2>/dev/null | tail -1 | tee -a $CHECKS
note "✅ J3 done $(date): read $L/j3_overflow_{0,2,3}m.txt, j3_overflow_0m_dikes.txt + the maps (README §6: wet edges at Hell Gate at +3 m are expected). A leak = a mask change (setup_boundary_depth.py), not a new mesh."
