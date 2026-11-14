#!/bin/bash
# J2 (nj2 = Model 2.0, 2026-11-14): the freeze chain, ONE nonpre job, every step skip-if-done.
# DRAFT — NOT SUBMITTED. Submission waits for: the refinement decided (data/nj2_design/
# refinement_nj2.geojson), the boundary agent's sea line (data/nj2_design/waterlevel_line_nj2.csv
# wired into nj2), the 2012-bed inputs (pier + upper-Gowanus carves in the catalog), a Fable audit
# of this packet, and the user's go. Record: logs/nj2_freeze_2026-11-14/README.md.
#
# It runs in TWO passes, split by the one step no job may do — registering a fingerprint:
#   pass 1 (overnight): 0 preconditions (REFUSES unbracketed hudson / hell_gate arms and a base grid
#                       != v4's) -> 1 freeze (+ base-grid assert) -> 2 obs check -> 3 hand-placed files
#                       + ls diff vs frozen_mesh_v4 -> 4 NACCS boundary on the frozen mask -> 4b the BASE
#                       support-count preview -> GATE 1 (stops cleanly, exit 0, until registered)
#   register (a person / Claude, ~15 min): premier.EXPECTED["nj2"] = the fingerprint in
#                       $L/fingerprint_nj2.txt; nj2 building=False; n_waterlevel_support = the
#                       [base-bnd] N in $L/base_support_nj2.txt (the BASE noaa_sandy_nj count, NOT
#                       step 4's NACCS count). A registered-but-MISMATCHED state REFUSES (exit 4).
#   pass 2 (same command): 5 base template + its hand steps -> 6 the 2012 bed (parallel builder)
#                       -> 7 merged-bed sweep (bed_audit, WARN only) -> 7b deck / connectivity
#                       re-check of the built bed (WARN only) -> done
#   then by hand (34 s): register Domain nj2_bed2012, setup_face_z.py, register its sha (GATE 2).
#
# Budget (v4 measured; nj2 is +2.5 % faces): pass 1 ~6-9 h (v4 freeze 4 h 39 on emeraldrapids, 72-90 G
# RSS; nonpre is skylake — slower, serial subgrid), ~40 G written; pass 2 ~3-4 h (template ~20 min,
# 2012 bed 7,494 s at 16 workers for v1.1c, sweep <= 1 h), ~40 G template (a copy of the
# frozen mesh) + ~35 G bed + ~35 G checkpoint work dir (removed at the end).
# Peak scratch +~150 G; net +~115 G after the work-dir removal (frozen mesh 40 + template 40 + bed 35;
# dedupe_experiment_inputs links within experiments/ only, scripts/dedupe_home.py can link the
# template to the frozen mesh afterwards). Scratch was 1,008 G of the
# 1 T soft quota on 11-14: pass 1 alone crosses the soft quota (grace period, not a failure);
# refuses within 200 G of the 2 T hard limit.
#
# Submit (from the repo root; both passes):
#   md5sum $(cat logs/nj2_freeze_2026-11-14/j2_md5_files.txt) > logs/nj2_freeze_2026-11-14/j2_expected.md5
#   NJ_DOMAIN=nj2 EXPECT_MD5=logs/nj2_freeze_2026-11-14/j2_expected.md5 \
#       sbatch logs/nj2_freeze_2026-11-14/j2_freeze_nj2.slurm
#SBATCH -J nj2_freeze
#SBATCH -p nonpre
#SBATCH --exclude=halk[0001-0159]
#SBATCH -N 1
#SBATCH -c 32
#SBATCH --mem=180G
#SBATCH -t 30:00:00
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH -o /cache/home/tpj8/nj_bight_sfincs/logs/nj2_freeze_2026-11-14/j2_%j.out
set -uo pipefail
REPO=/cache/home/tpj8/nj_bight_sfincs
cd $REPO
ENV=${NJ_TOOLCHAIN:-$HOME/nj_sandy_sfincs}/micromamba/envs/sfincs
export PATH=$ENV/bin:$PATH PYTHONPATH=$REPO NJ_ROOT=$REPO
export PROJ_LIB=$ENV/share/proj PROJ_DATA=$ENV/share/proj GDAL_DATA=$ENV/share/gdal
export HDF5_USE_FILE_LOCKING=FALSE TMPDIR=/scratch/tpj8/tmp; mkdir -p "$TMPDIR"
export NJ_DOMAIN="${NJ_DOMAIN:?set NJ_DOMAIN=nj2}"
[ "$NJ_DOMAIN" = nj2 ] || { echo "🔴 NJ_DOMAIN=$NJ_DOMAIN — this chain freezes nj2"; exit 3; }
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
OUT=/scratch/tpj8/nj_bight_sfincs_data/frozen_mesh_nj2
LINK=data/frozen_mesh_nj2
EXP=experiments/nj2
T=$EXP/_template_sealed
BED=_subgrid_nj2_2012
#: the frozen mesh's default weir = Model 1.1.0's premier file (Overpeck open, Elizabeth / Rahway
#: levees, Keansburg; user default 11-14). The structures agent's file replaces it via NJ2_WEIR.
WEIR=${NJ2_WEIR:-data/structures_v4/sfincs_overpeck_open_elizabeth_rahway_ground.weir}
CHECKS=$L/J2_CHECKS.txt
note() { echo "$*" | tee -a $CHECKS; }
die() { note "🔴 REFUSING: $*"; exit 4; }
step() { note "== $1 $(date '+%F %T')"; /usr/bin/time -f "   $1: %e s  maxRSS %M KB" "${@:2}"; local rc=$?; [ $rc -eq 0 ] || note "🔴 $1 exit $rc"; return $rc; }
note "==== J2 job ${SLURM_JOB_ID:-none} restart ${SLURM_RESTART_COUNT:-0} $(date)"

# ── 0. preconditions (inputs the other agents deliver; real guards, not reading rules) ─────────
python - <<'PY' || die "preconditions (above)"
import sys
from nj_sfincs import domain as D
d = D.active(); D.assert_buildable(d)  # ring GeoJSON == its CSV
bad = []
if d.waterlevel_line is None or d.waterlevel_line.name != "waterlevel_line_nj2.csv":
    bad.append(f"waterlevel_line is still {d.waterlevel_line} (the v4 PLACEHOLDER) — wire data/nj2_design/waterlevel_line_nj2.csv")
if d.refinement is None or not d.refinement.exists():
    bad.append(f"refinement {d.refinement} missing — the refinement agent's file")
if not (D.DATA / "elevation_nj2" / "bed_nj2_coarse_25m.tif").exists():
    bad.append("bed_nj2_coarse_25m.tif missing — J1")
arms = {a.name: a for a in d.boundary_arms}
for n in ("hudson", "hell_gate"):
    if n not in arms: bad.append(f"arm {n} not declared")
    elif (arms[n].min_cells, arms[n].max_cells) == (1, 10_000):
        bad.append(f"arm {n} still UNBRACKETED (1..10,000): tighten it from the mesh probe — the "
                   "freeze accepts any count inside the bracket, and a frozen count is a new mesh to undo")
for n in ("narrows", "kvk_east"):
    if n in arms: bad.append(f"arm {n} should be dropped")
# The base grid (x0, y0, rotation, dx) must be v4's: `v4_shelf_steps` (the SnapWave band) is in
# level-1 INDEX space. Predicted here from the ring with hydromt's own rotated-rectangle fit (the
# freeze's create_from_region), so a mismatch costs seconds, not the freeze; re-asserted on the
# frozen file after step 1. (2026-11-14 prediction: identical; nmax 1230 vs v4's 1255.)
import netCDF4
from hydromt import DataCatalog
from hydromt.model.processes.grid import create_grid_from_region
from nj_sfincs.config import BaseConfig
b = BaseConfig()
g = create_grid_from_region(region={"geom": str(d.region)}, data_catalog=DataCatalog(), res=b.base_res,
                            crs=b.crs, region_crs=4326, rotated=b.rotated, add_mask=False)
if g.raster.res[1] < 0: g = g.raster.flipud()
with netCDF4.Dataset(D.DATA / "frozen_mesh_v4" / "sfincs.nc") as v4:
    want = {k: float(v4.getncattr(k)) for k in ("x0", "y0", "dx", "dy", "rotation")}
got = dict(zip(("x0", "y0"), map(float, g.raster.origin)))
got.update(dx=float(g.raster.res[0]), dy=float(abs(g.raster.res[1])), rotation=float(g.raster.rotation))
print(f"[grid] predicted nj2 base grid {got} shape {g.raster.shape}; v4 {want}")
off = {k: (got[k], want[k]) for k in want if abs(got[k] - want[k]) > (1e-9 if k == "rotation" else 1e-6)}
if off: bad.append(f"predicted base grid != v4's {off}: v4_shelf_steps' level-1 indices would land elsewhere")
print("\n".join("🔴 " + b for b in bad) or "preconditions OK")
sys.exit(1 if bad else 0)
PY
/usr/lpp/mmfs/bin/mmlsquota -u tpj8 --block-size G scratch 2>/dev/null | tail -1 | \
  awk '{u=$4+0; printf "scratch: %s G used, soft %s, hard %s\n", u, $5, $6; if (u + 200 > $6+0) exit 1; if (u + 150 > $5+0) print "⚠️  this chain takes scratch over the soft quota (grace period)"}' \
  | tee -a $CHECKS || die "scratch within 200 G of the hard limit"

# ── 1. freeze (the CPU peak; freeze_mesh.py refuses to overwrite a complete mesh) ─────────────
if [ -f $OUT/sfincs.inp ]; then note "== 1: $OUT complete — skipped"
else
  [ -e "$OUT" ] && { note "[requeue] clearing PARTIAL freeze output $OUT"; rm -rf "$OUT"; }
  step 1_freeze python -u scripts/freeze_mesh.py "$OUT" > $L/freeze_nj2.log 2>&1 \
    || { tail -40 $L/freeze_nj2.log; die "freeze failed (log $L/freeze_nj2.log)"; }
fi
[ -e "$LINK" ] && [ ! -L "$LINK" ] && die "$LINK exists and is not a symlink"
ln -sfn "$OUT" "$LINK"
# the frozen base grid == v4's (x0, y0, rotation, dx, dy): v4_shelf_steps is in level-1 INDEX space
python - <<PY | tee -a $CHECKS || die "frozen base grid != v4's (above): v4_shelf_steps would be misplaced"
import netCDF4
from nj_sfincs import domain as D
def attrs(p):
    with netCDF4.Dataset(p) as g:
        return {k: float(g.getncattr(k)) for k in ("x0", "y0", "dx", "dy", "rotation", "nmax", "mmax")}
a, v = attrs("$LINK/sfincs.nc"), attrs(D.DATA / "frozen_mesh_v4" / "sfincs.nc")
off = {k: (a[k], v[k]) for k in ("x0", "y0", "dx", "dy", "rotation") if abs(a[k] - v[k]) > (1e-9 if k == "rotation" else 1e-6)}
s = D.SNAPWAVE_STEPS["v4_shelf_steps"]
fits = s.n_top <= a["nmax"] and max(m for *_, m in s.steps) <= a["mmax"]
print(f"[grid] nj2 frozen {a}\n[grid] v4        {v}\n[grid] origin/rotation/dx equal: {not off} {off or ''}; "
      f"v4_shelf_steps (n_top {s.n_top}, m <= {max(m for *_, m in s.steps)}) inside nmax x mmax: {fits}")
raise SystemExit(0 if not off and fits else 1)
PY
grep -E "\[mask\]|arm |structure|invariant|dry-land|⚠️" $L/freeze_nj2.log | tail -80 >> $CHECKS
python - <<PY | tee $L/fingerprint_nj2.txt | tee -a $CHECKS
from nj_sfincs import premier
fp = premier.domain_fingerprint("$LINK")
print(f"[fingerprint] nj2 frozen mesh: {fp}")
print(f"register: 'nj2': DomainFingerprint({fp.n_faces}, {fp.n_boundary_edges}, '{fp.sha_z_mask}')")
PY

# ── 2. obs: build_static wrote sfincs.obs from Domain.obs_gauges; assert it matches ────────────
python - <<PY | tee -a $CHECKS || die "obs points do not match the registry"
from nj_sfincs import premier
ok, problems = premier.obs_points_ok("$LINK")
print(f"[obs] match registry: {ok} {problems}")
raise SystemExit(0 if ok else 1)
PY

# ── 3. hand-placed frozen-mesh files (CLAUDE.md §5: a freeze silently drops them) ─────────────
[ -f "$WEIR" ] || die "weir file $WEIR missing"
if [ -f $OUT/sfincs.weir ] && cmp -s "$WEIR" $OUT/sfincs.weir; then note "== 3: sfincs.weir in place"
else cp --preserve=timestamps "$WEIR" $OUT/sfincs.weir.tmp && mv $OUT/sfincs.weir.tmp $OUT/sfincs.weir; note "== 3: sfincs.weir <- $WEIR"
fi
md5sum "$WEIR" $OUT/sfincs.weir | tee -a $CHECKS
note "-- ls diff frozen_mesh_v4 vs frozen_mesh_nj2 (expect no lines):"
diff <(ls data/frozen_mesh_v4) <(ls $LINK) | tee -a $CHECKS
note "-- weir u/v the ENGINE will find on the freeze's base bed (float32 rule; WARN only; v4 / v1.1c: 819 and 3551):"
python -I logs/walls_elizabeth_rahway_2026-11-05/engine_snap_f32.py $LINK $OUT/sfincs.weir \
  data/nj2_design/structures/sfincs_overpeck_open_elizabeth_rahway_dikes_levees_cohansey_nj2.weir 2>&1 | tail -6 | tee -a $CHECKS || true

# ── 4. NACCS boundary on the frozen mask (the boundary agent's wrapper; v4's cache untouched) ───
if [ -s data/gtsm/naccs_sandy_nj2.nc ]; then note "== 4: data/gtsm/naccs_sandy_nj2.nc exists — skipped"
else
  step 4_naccs python -u logs/nj2_edges_2026-11-14/build_naccs_boundary_nj2.py > $L/naccs_nj2.log 2>&1 \
    || { tail -40 $L/naccs_nj2.log; die "NACCS boundary failed"; }
  tail -30 $L/naccs_nj2.log >> $CHECKS
fi

# ── 4b. the BASE support count, PREVIEWED with hydromt's own selection (WARN only) ──────────────
# Domain.n_waterlevel_support = the support count of the BASE source BaseConfig.waterlevel_geodataset
# (noaa_sandy_nj: 3 gauges in the file, v4 / 1.x = 3). The freeze never runs add_forcing, so no freeze
# log line carries it; step 5's template build ASSERTS it ([bnd] line in template_nj2.log). This runs
# that selection (mask==2 lines of the frozen mask, Domain.waterlevel_buffer) without the template.
# 🔴 NOT step 4's NACCS count: that one is experiments._NJ2_NACCS_SUPPORT, on the ARMS.
if grep -q "^\[base-bnd\] [0-9]" $L/base_support_nj2.txt 2>/dev/null; then note "== 4b: base support preview done — skipped"
else
  python -u $L/base_support_count.py $LINK > $L/base_support_nj2.txt.tmp 2>&1 && mv $L/base_support_nj2.txt.tmp $L/base_support_nj2.txt \
    || note "⚠️ base support preview failed ($L/base_support_nj2.txt.tmp) — step 5 still asserts the count"
fi
grep -E "^(source|\[base-bnd\])" $L/base_support_nj2.txt 2>/dev/null | tee -a $CHECKS

# ── GATE 1: nothing below may run on an unregistered domain (premier refuses it anyway) ────────
# exit 10 = not registered yet (pass 1 done, stop cleanly); 0 = registered and consistent;
# anything else = registered but WRONG (fingerprint mismatch, half-registered, a NACCS count) -> refuse.
python - "$L/base_support_nj2.txt" <<'PY' 2>&1 | tee -a $CHECKS
import re, sys
from pathlib import Path
from nj_sfincs import domain as D, premier
d = D.active()
reg = "nj2" in premier.EXPECTED
if not reg and d.building:
    print("GATE 1: nj2 not registered (no premier.EXPECTED['nj2'], Domain still BUILDING)"); sys.exit(10)
bad = []
if not reg: bad.append("Domain nj2 is no longer BUILDING but premier.EXPECTED has no 'nj2'")
if d.building: bad.append("premier.EXPECTED['nj2'] is set but Domain nj2 is still building=True")
if d.n_waterlevel_support is None: bad.append("Domain nj2 n_waterlevel_support is still None")
if reg:
    fp = premier.domain_fingerprint(d.frozen_mesh_dir())
    print(f"GATE 1: registered {premier.EXPECTED['nj2']}\nGATE 1: frozen mesh {fp}")
    if fp != premier.EXPECTED["nj2"]:
        bad.append("fingerprint MISMATCH: the registered fingerprint is not this frozen mesh's "
                   "(re-copy it from fingerprint_nj2.txt, or the mesh changed under the registration)")
pv = Path(sys.argv[1])
m = re.findall(r"^\[base-bnd\] (\d+)", pv.read_text(), re.M) if pv.exists() else []
if m and d.n_waterlevel_support is not None and int(m[-1]) != d.n_waterlevel_support:
    bad.append(f"n_waterlevel_support = {d.n_waterlevel_support}, but the BASE noaa_sandy_nj selection on "
               f"this mask is {m[-1]} ({pv}). It is the base count, not step 4's NACCS count "
               "(experiments._NJ2_NACCS_SUPPORT); step 5's template build would refuse it")
for b in bad: print("🔴 GATE 1:", b)
sys.exit(1 if bad else 0)
PY
G1=${PIPESTATUS[0]}
if [ "$G1" -eq 10 ]; then
  note "⏸  GATE 1 — pass 1 DONE. Register nj2: premier.EXPECTED['nj2'] = the line in $L/fingerprint_nj2.txt;"
  note "    domain.py: building=False, n_waterlevel_support = the [base-bnd] N in $L/base_support_nj2.txt"
  note "    (the BASE noaa_sandy_nj count, v4: 3 — step 5's [bnd] line asserts it; NOT step 4's NACCS count,"
  note "    which goes to experiments._NJ2_NACCS_SUPPORT). Re-write $L/j2_expected.md5, resubmit THIS script."
  exit 0
elif [ "$G1" -ne 0 ]; then
  die "GATE 1: nj2 is registered but inconsistent (🔴 lines above) — fix the registration, do not run pass 2"
fi

# ── 5. base template + its hand steps (1.1.0's: ERA5-bilinear meteo, Overpeck pool start) ─────
mkdir -p $EXP
INI_KEY='^inifile *= *sfincs_ini_regional\.bin *$'   # 1.1.0's template: "inifile              = sfincs_ini_regional.bin"
if python -c "from nj_sfincs import premier; import sys; sys.exit(0 if premier.is_sealed('$T') else 1)" \
   && [ -f $T/sfincs_ini_regional.bin ] && grep -q "$INI_KEY" $T/sfincs.inp; then
  note "== 5: $T sealed + hand steps done — skipped"
else
  if ! python -c "from nj_sfincs import premier; import sys; sys.exit(0 if premier.is_sealed('$T') else 1)"; then
    # build_template rmtree's its target: here only a PARTIAL (unsealed) dir can exist
    step 5_template python -u - > $L/template_nj2.log 2>&1 <<'PY' || { tail -40 $L/template_nj2.log; die "template build"; }
import run_experiments as R
from nj_sfincs.config import BaseConfig
print("template ->", R.TEMPLATE)
R.build_template(BaseConfig())
PY
  fi
  step 5b_meteo python scripts/fix_meteo_grid_origin.py --era5-bilinear $T >> $L/template_nj2.log 2>&1 || die "meteo --era5-bilinear"
  python scripts/fix_meteo_grid_origin.py --check $T > $L/template_meteo_check.txt 2>&1 || die "meteo --check"
  step 5c_pool python -I logs/refreeze_2026-10-06/structures/pool_ini.py $T \
      --region data/nj2_design/structures/overpeck_pool.geojson --out $T \
      --check data/nj2_design/structures/sfincs_overpeck_open_elizabeth_rahway_ground.weir > $L/template_pool_ini.log 2>&1 \
    || die "pool ini (log $L/template_pool_ini.log)"
  python - <<PY || die "inifile key"
import sys; sys.path.insert(0, "logs/refreeze_2026-10-06/structures")
from pathlib import Path
import pool_ini
p = Path("$T/sfincs.inp"); p.write_text(pool_ini.regional_ini_keys(p.read_text()))
PY
fi
grep -E "^(weirfile|inifile|dtrstout|dtmaxout|latitude)" $T/sfincs.inp | tee -a $CHECKS
grep -q "$INI_KEY" $T/sfincs.inp || die "template inp has no 'inifile = sfincs_ini_regional.bin' (a death between pool_ini and the key edit?) — rerun re-does the hand steps"
cmp -s $T/sfincs.weir $OUT/sfincs.weir || die "template sfincs.weir != the frozen mesh's"
grep -E "CHECK|CHANGED" $L/template_pool_ini.log | tee -a $CHECKS
python - <<PY | tee -a $CHECKS || die "regional ini size != 4 x active faces"
import os, netCDF4, numpy as np
with netCDF4.Dataset("$T/sfincs.nc") as g: n = int((np.asarray(g["mask"][:]) > 0).sum())
sz = os.path.getsize("$T/sfincs_ini_regional.bin")
print(f"ini size {sz} = 4 x {n} active: {sz == 4 * n}"); raise SystemExit(0 if sz == 4 * n else 1)
PY
python -m nj_sfincs.premier $T 2>&1 | tail -5 | tee -a $CHECKS
python logs/restage_2026-10-17/compare_templates.py $T experiments/v4_refreeze_swz_v11/_template_sealed > $L/compare_vs_v11_template.txt 2>&1 \
  || die "compare_templates.py failed ($L/compare_vs_v11_template.txt)"
# Files only in 1.1.0's template that a build_template-built MESH template lacks BY DESIGN:
#   face_z_report.json          setup_face_z (GATE 2, on nj2_bed2012 — not this template)
#   snapwave.{bnd,bhs,btp,bwd,bds}  1.1.0's was staged WITH waves (setup_boundary_depth); build_template
#                               is NO_WAVES and every waves-on arm writes its own at staging
#   sfincs.crs                  restore_diagnostics runs at ARM staging (Domain.flux_crosssections)
#   subgrid/dep_subgrid_merged.tif  the scoring bed comes from _subgrid_nj2_2012 (step 6) via setup_face_z
#   .subgrid_sha256             a cache, written on first use
# Anything else refuses. Override for one named file after reading it: J2_ALLOW_ONLY_OLD="<rel path> ...".
python - "$L/compare_vs_v11_template.txt" <<'PY' 2>&1 | tee -a $CHECKS
import ast, os, sys
lines = open(sys.argv[1]).read().splitlines()
def only(tag):
    hit = [l for l in lines if l.startswith(tag)]
    if not hit: print(f"🔴 no '{tag}' line: compare_templates output incomplete"); sys.exit(2)
    return set(ast.literal_eval(hit[0].split(":", 1)[1].strip()))
old, new = only("only in OLD:"), only("only in NEW:")
expect = {"face_z_report.json", "sfincs.crs", ".subgrid_sha256", "subgrid/dep_subgrid_merged.tif"}
expect |= {f"snapwave.{e}" for e in ("bnd", "bhs", "btp", "bwd", "bds")}
expect |= set(os.environ.get("J2_ALLOW_ONLY_OLD", "").split())
print(f"[compare] only in 1.1.0's template: {sorted(old)}")
print(f"[compare] only in nj2's template:   {sorted(new)}")
bad = sorted(old - expect)
print("[compare] unexpected only-in-1.1.0:", bad or "none")
sys.exit(1 if bad else 0)
PY
[ "${PIPESTATUS[0]}" -eq 0 ] || die "template vs 1.1.0's: unexpected files only in 1.1.0's template (above; $L/compare_vs_v11_template.txt)"
sed -n '/^DIFF  sfincs.inp/,/^[A-Z]/p' $L/compare_vs_v11_template.txt | head -40 | tee -a $CHECKS

# ── 6. the 2012 bed: 1.1.0's v1.1c recipe + the v1.2a five + 2.0's 2012 tiers ────────────────
# Plain paints in v1.1c's order, then HD_HUD (PAINT, user 11-09: after the last plain overlay,
# before the :min group), then v1.1c's :min group, the v1.2a five (:min), and 2.0's :min carves
# (Brooklyn creeks; upper Gowanus ASSUMED; pile piers, user 11-14). Manning: v1.1c's.
NEW_MIN="raritan_mouth_fix_v4 gmrt_gap_fix_v4 nj36_deck_recut_v4 greategg_plug_fix_v4 barnegat_flat_fix_v4 carve_v2_2012 gowanus_upper_v2 piers_v2_2012"
for k in ehydro_hud_2012_v2 $NEW_MIN; do grep -q "^$k:" data/data_catalog.yml || die "catalog key $k missing"; done
if [ -f $EXP/$BED/subgrid_diff.json ] && [ -f $EXP/$BED/provenance.txt ]; then note "== 6: $BED built — skipped"
else
  OV=""; for k in $NEW_MIN; do OV="$OV --overlay $k:min"; done
  step 6_bed python -u scripts/rebuild_subgrid_parallel.py --workers 16 --dst $BED --force \
    --overlay bed_buildings_v4_cap10 --overlay inland_water_bed_v4 --overlay alloway_pool_v4 --overlay silver_pool_v4 --overlay usace_unpave_v4 \
    --overlay ehydro_harbour_v4 --overlay ehydro_refreeze_cenan_v4 --overlay usace_unpave_backbay_v4 \
    --overlay riverbed_sayreville_v4 --overlay littleegg_channel_v4 --overlay riverbeds_hierarchy_v4e \
    --overlay ehydro_hud_2012_v2 \
    --overlay lake_fix_v4:min --overlay creek_bed_nj10ft_v4:min --overlay deck_fix_v4b:min --overlay ehydro_fill_v4:min --overlay nbi_open_v4:min \
    $OV \
    --manning-overlay manning_developed_v4 --manning-overlay manning_water_v4 --manning-overlay manning_channel_v4e \
    > $L/rebuild_subgrid_nj2_2012.log 2>&1 || { tail -30 $L/rebuild_subgrid_nj2_2012.log; die "2012 bed build"; }
fi
python - <<PY | tee -a $CHECKS || die "2012 bed recipe != v1.1c + v1.2a + 2.0's tiers"
import json
v11 = json.load(open("experiments/v4_refreeze_swz/_subgrid_v1_1c/provenance.txt"))
b = json.load(open("$EXP/$BED/provenance.txt"))
o = v11["overlay_tiers"]; i = o.index("lake_fix_v4:min")
want = o[:i] + ["ehydro_hud_2012_v2"] + o[i:] + [f"{k}:min" for k in "$NEW_MIN".split()]
# elevation_list in provenance = the base tiers + the overlays (with merge_method): compare the BASE part
base = lambda L: [e for e in L if "merge_method" not in e]
checks = {
    "overlays as intended": b["overlay_tiers"] == want,
    "base list = v1.1c's": base(b["elevation_list"]) == base(v11["elevation_list"]),
    "no prepended tiers, as v1.1c": b.get("prepended_tiers") == v11.get("prepended_tiers"),
    "manning = v1.1c's": b.get("manning_overlay_tiers") == v11.get("manning_overlay_tiers"),
}
for k, v in checks.items(): print(f"{k}: {v}")
raise SystemExit(0 if all(checks.values()) else 1)
PY
ls $EXP/$BED/subgrid/dep_subgrid_merged.tif >/dev/null || die "no merged scoring bed in $BED"
note "-- weir u/v on the 2012 bed (engine float32 rule; WARN only — the staged sfincs.log is the truth):"
python -I logs/walls_elizabeth_rahway_2026-11-05/engine_snap_f32.py $EXP/$BED \
  data/nj2_design/structures/sfincs_overpeck_open_elizabeth_rahway_ground.weir \
  data/nj2_design/structures/sfincs_overpeck_open_elizabeth_rahway_dikes_levees_cohansey_nj2.weir 2>&1 | tail -6 | tee -a $CHECKS || true
# wavemaker re-snap check on the nj2 2012 bed (WARN only; the 1.1.0 line is far from the new area)
WM=/scratch/tpj8/tmp/nj2_wavemaker_2012.geojson
if [ ! -s $WM ]; then
  python scripts/build_wavemaker_line.py --dep $EXP/$BED/subgrid/dep_subgrid_lev0.tif --mesh $T/sfincs.nc \
    --window 495000 4285000 605000 4492000 --contour-stride 2 --float32-weights --snap-seaward-of-beach \
    --out $WM > $L/wavemaker_nj2_2012.log 2>&1 || note "⚠️ wavemaker rebuild exit != 0 ($L/wavemaker_nj2_2012.log)"
fi
[ -s $WM ] && { cmp -s $WM data/nj2_design/structures/v4_wavemaker_5m_mhw_snapbeach.geojson \
  && note "   wavemaker: identical to 1.1.0's line" || note "⚠️ wavemaker differs from 1.1.0's line: diff $WM before a waves-on arm"; }

# ── 7. merged-bed sweep: ridges / decks across wet channels, seams, NBI crossings (WARN only) ───
if [ -f logs/bed_audit_2026-11-05/out/nj2_2012/AUDIT.md ]; then note "== 7: sweep done — skipped"
else
  step 7_sweep python -u scripts/bed_audit.py --bed $EXP/$BED --label nj2_2012 > $L/bed_audit_nj2_2012.log 2>&1 \
    || note "⚠️ bed_audit exit != 0 (several checks hard-code the v4 ring; read $L/bed_audit_nj2_2012.log)"
fi
note "   sweep: logs/bed_audit_2026-11-05/out/nj2_2012/AUDIT.md (a LOCATOR, not a gate; the NY ground is new to it)"

# ── 7b. deck / connectivity re-check of the BUILT 2012 bed in the new area (WARN only) ─────────
# logs/nj2_decks_2026-11-14/README.md "After the build": found no dams in the PLANNED bed; re-run on
# the bed step 6 wrote. connect.py needs area_mask.tif from a planned_bed.py run (scratch/tmp: made
# again if purged). ~5 min, a few G (measured 11-14: planned_bed ~1 min, connect ~3 min).
K=logs/nj2_decks_2026-11-14; KD=/scratch/tpj8/tmp/nj2_decks_2026-11-14
if [ -f $K/blocked_built_2012.csv ] && [ $K/blocked_built_2012.csv -nt $EXP/$BED/subgrid/dep_subgrid_merged.tif ]; then note "== 7b: decks re-check done — skipped"
else
  note "== 7b decks re-check $(date '+%F %T')"
  { [ -f $KD/area_mask.tif ] || python -u $K/planned_bed.py; } > $L/decks_built_2012.log 2>&1
  python -u $K/planned_bed.py --built $EXP/$BED/subgrid/dep_subgrid_merged.tif >> $L/decks_built_2012.log 2>&1 \
    && python -u $K/connect.py built_2012 >> $L/decks_built_2012.log 2>&1 \
    || note "⚠️ decks re-check exit != 0 (WARN only; $L/decks_built_2012.log)"
fi
grep -E "^(seed bed|blocked water px)" $L/decks_built_2012.log 2>/dev/null | sed 's/^/   decks: /' | tee -a $CHECKS
note "   decks: clusters >= 200 m2 -> $K/blocked_built_2012.csv (planned bed: blocked_planned_2012.csv; README)"

# ── tidy: the template's copies -> hard links within the domain; the builder's checkpoints ───
python scripts/dedupe_experiment_inputs.py --apply >> $L/dedupe.log 2>&1 || note "⚠️ dedupe exit != 0 ($L/dedupe.log)"
W=/scratch/tpj8/nj_bight_sfincs/subgrid_par_work/nj2/$BED
[ -f $EXP/$BED/provenance.txt ] && [ -d "$W" ] && rm -rf "$W" && note "removed checkpoint dir $W"
/usr/lpp/mmfs/bin/mmlsquota -u tpj8 --block-size G scratch 2>/dev/null | tail -1 | tee -a $CHECKS
note "✅ J2 pass 2 DONE $(date). GATE 2 (by hand): register Domain nj2_bed2012 (face_z_from=\"$BED\", mesh_key nj2),"
note "    NJ_DOMAIN=nj2_bed2012 python scripts/setup_face_z.py --from nj2 --bed $BED, register the sha it prints."
