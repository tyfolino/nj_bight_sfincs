#!/bin/bash
# Model 2.0.0's 2026 (estimated, "today's") bed on the nj2 mesh — ONE chained job, every step skip-if-done.
# DRAFT — NOT SUBMITTED. Waits for: the nj2 freeze + its 2012 bed (logs/nj2_freeze_2026-11-14/j2_freeze_nj2.slurm
# pass 2: experiments/nj2/_template_sealed sealed, experiments/nj2/_subgrid_nj2_2012 built), the catalog keys below
# (snippets: logs/nj2_bed2026_2026-11-14/README.md "Catalog"), and the user's go. Record + recipe: that README.
#   P1  modern land against the nj2 2012 bed           scripts/build_modern_land.py --bed --out   (~5 min, 16 w)
#   P2  split -> paint / lower-only layers             split_modern_land_nj2.py                    (~7 min, 41 G)
#   P3  BlueTopo newer-than-CUDEM inside the nj2 ring   build_bluetopo_newer_nj2.py                 (~1 min)
#   P4  NO-BUILDINGS 2026 bed (the burn's ground)       rebuild_subgrid_parallel.py, list minus the burn (~30 min)
#   P5  burn the hybrid footprints at ground + 10 m     logs/modern_round_c_2026-11-12/burn_hybrid.py (~5 min)
#       then the no-buildings bed is deleted (its merged dep is the burn's only use)
#   A   THE 2026 bed _subgrid_nj2_2026                  rebuild_subgrid_parallel.py                 (~30 min, 21 G)
#   A2  recipe check: the 2012 bed's base tiers + EXACTLY the list below + the 2025 Manning list + nj2's mesh
#   B   bed summary vs the nj2 2012 bed (z_volmax first: CLAUDE.md §5)
#   C   merged-bed sweep (bed_audit, WARN only)                                                       (~40 min)
# Budget: ~2 h on 32 cores (round b measured: split 418 s, rebuild 1,591 s at 16 w; nj2 is +2.5 % faces).
# Scratch: +~4 G modern land, +~4 G split, ~35 G no-buildings bed (removed after P5), ~35 G bed, ~35 G checkpoints
# (removed at the end): peak ~+115 G, net ~+45 G. Refuses within 150 G of the 2 T hard limit.
# Then by hand (GATE, ~1 min): register Domain nj2_bed2026 (face_z_from="_subgrid_nj2_2026", cn_dataset="cn_2025_v4",
#   mesh_key nj2), NJ_DOMAIN=nj2_bed2026 python scripts/setup_face_z.py --from nj2 --bed _subgrid_nj2_2026, register the sha.
# Submit from the repo root:
#   md5sum $(cat logs/nj2_bed2026_2026-11-14/md5_files.txt) > logs/nj2_bed2026_2026-11-14/expected.md5
#   EXPECT_MD5=logs/nj2_bed2026_2026-11-14/expected.md5 sbatch logs/nj2_bed2026_2026-11-14/build_nj2_2026.slurm
#SBATCH -J nj2_bed2026
#SBATCH -p nonpre
#SBATCH --exclude=halk[0001-0159]
#SBATCH -N 1
#SBATCH -c 32
#SBATCH --mem=180G
#SBATCH -t 8:00:00
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH -o /cache/home/tpj8/nj_bight_sfincs/logs/nj2_bed2026_2026-11-14/build_%j.out
set -uo pipefail
REPO=/cache/home/tpj8/nj_bight_sfincs
cd $REPO
ENV=${NJ_TOOLCHAIN:-$HOME/nj_sandy_sfincs}/micromamba/envs/sfincs
export PATH=$ENV/bin:$PATH PYTHONPATH=$REPO NJ_ROOT=$REPO NJ_DOMAIN=nj2
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

L=logs/nj2_bed2026_2026-11-14
EXP=experiments/nj2
REF=_subgrid_nj2_2012            # the 2012 bed on the same mesh (its base tiers + its merged bed = "the current bed")
NOB=_subgrid_nj2_2026_nobuildings
DST=_subgrid_nj2_2026
M=/scratch/tpj8/nj_bight_sfincs_data/elevation_modern_2026/nj2
RC=/scratch/tpj8/nj_bight_sfincs_data/modern_2026/derived/round_c
RING=logs/v2_prep_2026-11-04/ring_new_full_v2edit.csv
CHECKS=$L/CHECKS.txt
note() { echo "$*" | tee -a $CHECKS; }
die() { note "🔴 REFUSING: $*"; exit 4; }
step() { note "== $1 $(date '+%F %T')"; /usr/bin/time -f "   $1: %e s  maxRSS %M KB" "${@:2}"; local rc=$?; [ $rc -eq 0 ] || note "🔴 $1 exit $rc"; return $rc; }

# ── the 2026 recipe (README "Recipe"). Round b's list with: modern land / BlueTopo / buildings re-made for nj2,
#    the two BOTH-bed v1.2a fixes, and 2.0's 2026 carves. Paint order = list order; :min = lower-only.
OVERLAYS=(
  modern_land_paint_nj2 modern_land_lower_nj2:min
  riverbeds_v4 shrewsbury_ehydro_2015 ehydro_south ehydro_nj ehydro_raritan_ak ehydro_south_v3 ehydro_hackensack_v4 ehydro_passaic_v4
  bed_buildings_hybrid_cap10_nj2 inland_water_bed_v4 alloway_pool_v4 silver_pool_v4 usace_unpave_v4
  ehydro_harbour_v4 ehydro_refreeze_cenan_v4 usace_unpave_backbay_v4 riverbed_sayreville_v4 littleegg_channel_v4 riverbeds_hierarchy_v4e
  bluetopo_newer_nj2 ehydro_latest_2026
  lake_fix_v4:min creek_bed_nj10ft_v4:min
  deck_fix_v4b_modern:min nbi_open_v4:min deck_fix_modern_b:min
  raritan_mouth_fix_v4:min greategg_plug_fix_v4:min
  carve_v2_2026:min gowanus_upper_v2_2026:min piers_v2_2026:min
)
# Manning: the base reclass stays the template's (NLCD 2012); manning_nlcd_2025_v4 = the SAME reclass of NLCD 2025,
# painted first over it, so the base n is 2025's wherever NLCD 2025 has data (all of it); then round c's developed
# overlay (2025, NJ only) and v1.1c's water / channel overlays.
MANNING=(manning_nlcd_2025_v4 manning_developed_2025_v4 manning_water_v4 manning_channel_v4e)

# ── preflight ────────────────────────────────────────────────────────────────────────────────
[ -d $EXP/_template_sealed ] || die "$EXP/_template_sealed missing (nj2 not frozen / staged)"
[ -f $EXP/$REF/provenance.txt ] && [ -s $EXP/$REF/subgrid/dep_subgrid_merged.tif ] || die "$EXP/$REF not built (the 2012 bed)"
for o in "${OVERLAYS[@]}" "${MANNING[@]}"; do k=${o%%:min}; grep -q "^$k:" data/data_catalog.yml || die "catalog key $k missing"; done
for f in $RC/footprints_hybrid_nj2.gpkg data/elevation_nj2/v2/carves/gowanus_upper_v2_2026.tif data/elevation_nj2/v2/carves/piers_v2_2026.tif \
         data/elevation_nj2/v2/carves/carve_v2_2026.tif $RC/manning_nlcd_2025_v4.tif $RC/manning_developed_2025_v4.tif; do
  [ -s $f ] || die "input missing: $f"; done
/usr/lpp/mmfs/bin/mmlsquota -u tpj8 --block-size G scratch 2>/dev/null | tail -1 | \
  awk '{u=$4+0; printf "scratch: %s G used, soft %s G, hard %s G\n", u, $5, $6; if (u + 115 + 150 > $6) exit 1}' \
  || die "scratch: this job's ~115 G peak would come within 150 G of the hard limit"

# ── P1 modern land against the nj2 2012 bed (accept() reads water vs land off it; the burn there sits only on
#    ground >= 0, so a building pixel never reads as water: the rasters equal a no-buildings bed's; the report's
#    medians on land are biased low by the roofs) ──────────────────────────────────────────────────────────
if [ -s $M/modern_land_2026.tif ] && [ -s $L/modern_land/modern_land_sources.json ]; then note "== P1 done — skipped"
else step P1_modern_land python -u scripts/build_modern_land.py --workers 16 --report $L/modern_land \
       --bed $EXP/$REF/subgrid/dep_subgrid_merged.tif --out $M > $L/modern_land.log 2>&1 || { tail -20 $L/modern_land.log; die P1; }
fi
# ── P2 split (round b's rules; the 2012 bed = the nj2 one) ─────────────────────────────────────────────────
export NJ2_HERE=$L NJ2_MLAND=$M/modern_land_2026.tif NJ2_B12=$EXP/$REF/subgrid/dep_subgrid_merged.tif NJ2_OUT=$M NJ2_SUFFIX=_nj2
if [ -s $M/modern_land_lower_nj2.tif ] && [ -s $L/split_summary_nj2.json ]; then note "== P2 done — skipped"
else step P2_split python -u $L/split_modern_land_nj2.py --workers 32 > $L/split.log 2>&1 || { tail -20 $L/split.log; die P2; }
fi
# ── P3 BlueTopo newer-than-CUDEM, inside the nj2 ring, not under the nj2 modern land ───────────────────────
export NJ2_BT_OUT=$M/bluetopo_newer NJ2_RING_CSV=$RING
if [ -s $M/bluetopo_newer/bluetopo_newer_2026.vrt ] && [ -s $L/bluetopo_newer_summary.json ]; then note "== P3 done — skipped"
else step P3_bluetopo python -u $L/build_bluetopo_newer_nj2.py --workers 16 > $L/bluetopo.log 2>&1 || { tail -20 $L/bluetopo.log; die P3; }
fi
# ── P4 + P5 the burn's ground (the full list WITHOUT the burn), the burn, then drop the ground bed ──────────
BURN=$M/bed_buildings_hybrid_cap10_nj2.tif
if [ -s $BURN ] && [ -s ${BURN%.tif}.json ]; then note "== P4/P5 done — skipped"
else
  if ! [ -f $EXP/$NOB/provenance.txt ]; then
    OVA=(); for o in "${OVERLAYS[@]}"; do [ "$o" = bed_buildings_hybrid_cap10_nj2 ] || OVA+=(--overlay "$o"); done
    step P4_nobuildings python -u scripts/rebuild_subgrid_parallel.py --workers 16 --dst $NOB --force "${OVA[@]}" \
      > $L/rebuild_nobuildings.log 2>&1 || { tail -20 $L/rebuild_nobuildings.log; die P4; }
  fi
  step P5_burn python -u logs/modern_round_c_2026-11-12/burn_hybrid.py --ground $EXP/$NOB/subgrid/dep_subgrid_merged.tif \
    --footprints $RC/footprints_hybrid_nj2.gpkg --out $BURN > $L/burn.log 2>&1 || { tail -20 $L/burn.log; die P5; }
  tail -4 $L/burn.log | tee -a $CHECKS
  rm -rf $EXP/$NOB /scratch/tpj8/nj_bight_sfincs/subgrid_par_work/nj2/$NOB && note "removed $NOB + its checkpoints (burn ground only)"
fi
# ── A the 2026 bed ───────────────────────────────────────────────────────────────────────────────────────
if [ -f $EXP/$DST/subgrid_diff.json ] && [ -f $EXP/$DST/provenance.txt ]; then note "== A: $DST built — skipped"
else
  OVA=(); for o in "${OVERLAYS[@]}"; do OVA+=(--overlay "$o"); done
  MNA=(); for m in "${MANNING[@]}"; do MNA+=(--manning-overlay "$m"); done
  step A_rebuild python -u scripts/rebuild_subgrid_parallel.py --workers 16 --dst $DST --force "${OVA[@]}" "${MNA[@]}" \
    > $L/rebuild_nj2_2026.log 2>&1 || { tail -20 $L/rebuild_nj2_2026.log; die A; }
fi
# ── A2 recipe check ──────────────────────────────────────────────────────────────────────────────────────
python - "$EXP/$REF/provenance.txt" "$EXP/$DST/provenance.txt" "${#OVERLAYS[@]}" "${OVERLAYS[@]}" "${MANNING[@]}" <<'PY' | tee -a $CHECKS || die "A2 recipe"
import json, sys
dec = json.JSONDecoder()
ref, new = (dec.raw_decode(open(p).read())[0] for p in sys.argv[1:3])
n = int(sys.argv[3]); want, man = sys.argv[4:4 + n], sys.argv[4 + n:]
base = [e for e in ref["elevation_list"] if "merge_method" not in e]
el = base + [{"elevation": o.split(":")[0], "merge_method": "overlay_min" if o.endswith(":min") else "overlay"} for o in want]
ok = {"base tiers = the 2012 bed's": [e for e in new["elevation_list"] if "merge_method" not in e] == base,
      "elevation_list = base + the 2026 list": new["elevation_list"] == el,
      "overlay_tiers = the 2026 list": new["overlay_tiers"] == want,
      "manning overlays = the 2025 list": new.get("manning_overlay_tiers") == man,
      "same mesh as the 2012 bed": new["fingerprint"] == ref["fingerprint"]}
for k in ("prepended_tiers", "reproj_method", "nr_subgrid_pixels", "nr_levels"):
    ok[f"{k} = the 2012 bed's"] = new.get(k) == ref.get(k)
for k, v in ok.items():
    print(f"  {'OK ' if v else 'BAD'} {k}")
sys.exit(0 if all(ok.values()) else 1)
PY
# ── B where it moved vs the nj2 2012 bed (same faces) ─────────────────────────────────────────────────────
note "== B_bed_summary $(date '+%F %T')"
python - "$EXP/$REF/sfincs_subgrid.nc" "$EXP/$DST/sfincs_subgrid.nc" <<'PY' | tee $L/bed_summary_nj2_2026.txt
import sys, numpy as np, xarray as xr
ref, new = (xr.open_dataset(p) for p in sys.argv[1:3])
print("nj2 2026 bed vs nj2 2012 bed (same mesh)")
for v in ("z_volmax", "z_zmin", "z_zmax", "uv_zmin", "uv_havg", "uv_navg"):
    if v not in ref or v not in new:
        continue
    x, y = ref[v].values, new[v].values
    d = np.isfinite(x) & np.isfinite(y) & (x != y)
    dd = (y - x)[d]
    q = np.percentile(dd, [5, 50, 95]) if dd.size else [0, 0, 0]
    print(f"  {v:9s} changed {int(d.sum()):>9,d}  Δ p5 {q[0]:+9.3f} p50 {q[1]:+8.3f} p95 {q[2]:+9.3f}  "
          f"up>0.05 {int((dd > 0.05).sum()):>8,d}  down<-0.05 {int((dd < -0.05).sum()):>8,d}")
PY
# ── C sweep (a locator, not a gate) ───────────────────────────────────────────────────────────────────────
if [ -f logs/bed_audit_2026-11-05/out/nj2_2026/AUDIT.md ]; then note "== C: sweep done — skipped"
else
  export AUDIT_CPUS=${SLURM_CPUS_PER_TASK:-32}
  step C_sweep python -u scripts/bed_audit.py --bed $EXP/$DST --label nj2_2026 > $L/bed_audit_nj2_2026.log 2>&1 \
    || note "⚠️ bed_audit exit != 0 (several checks hard-code the v4 ring; read $L/bed_audit_nj2_2026.log)"
fi
W=/scratch/tpj8/nj_bight_sfincs/subgrid_par_work/nj2/$DST
[ -f $EXP/$DST/provenance.txt ] && [ -d "$W" ] && rm -rf "$W" && note "removed checkpoint dir $W"
/usr/lpp/mmfs/bin/mmlsquota -u tpj8 --block-size G scratch 2>/dev/null | tail -1 | tee -a $CHECKS
note "✅ nj2 2026 bed DONE $(date). GATE (by hand): register Domain nj2_bed2026 (face_z_from=\"$DST\", cn_dataset=\"cn_2025_v4\"),"
note "    NJ_DOMAIN=nj2_bed2026 python scripts/setup_face_z.py --from nj2 --bed $DST, register the sha it prints."
