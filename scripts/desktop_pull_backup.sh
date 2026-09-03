#!/usr/bin/env bash
# desktop_pull_backup.sh — run this ON THE DESKTOP (the 1 TB HDD), not on Amarel.
#
# Pulls, over SSH + rsync, the two things that cannot be regenerated from git:
#
#   TIER 1  irreplaceable INPUTS, which live in Amarel HOME (backed up by OARC, but
#           quota-bound):  ~/nj_bight_sfincs/data/   (~13 G: elevation_v3, frozen
#           meshes, NACCS, infiltration, precip, waves, validation, discharge)
#           ~/sfincs_data/                             (~29 G: raw CUDEM/3DEP tiles that
#           the elevation VRTs READ, the 16 G statewide DEM kept for the v4 Delaware
#           Bay re-clip, and sfincs-env.tar.gz, the VSCode-node fast-deploy env)
#           ~/nj_coast_sfincs/                         (~12 G: the frozen predecessor —
#           data + 26 campaign logs; read-only, see ARCHIVE.md)
#
#   TIER 2  SCORED solver output, which lives on Amarel SCRATCH
#           (/scratch/tpj8/nj_bight_sfincs/experiments — 1 TB, NOT backed up, files
#           not accessed for 90 days are purged).  Per arm we keep what the numbers in
#           STATUS/FINDINGS were read from: sfincs_his.nc, sfincs.log, sfincs.inp,
#           provenance.txt, floodmap_hmax_lev3.tif, the small forcing files and gis/;
#           per domain metrics*.csv and report.html.  EXCLUDED because regenerable
#           from tier 1 + git: _template_sealed/, subgrid/, roughness.nc, sfincs.nc,
#           sfincs_subgrid.nc, snapwave.upw, floodmaps/ (gallery copies), and
#           sfincs_map.nc (5 G per waves-on arm) unless you pass --with-maps.
#
# Code, docs, notebooks: git (the user pushes). They are NOT mirrored here.
#
# This is a COPY, not an archive: there is deliberately no --delete, so a file removed
# on Amarel (by a purge, a quota accident, or a halk clobber) survives here until you
# remove it by hand. Re-run whenever an arm has been scored; each run is incremental.
#
# Usage (desktop):
#   VPN first if off campus.
#   bash desktop_pull_backup.sh --list                 # print what would be mirrored
#   bash desktop_pull_backup.sh -n                     # rsync dry run
#   bash desktop_pull_backup.sh                        # tiers 1 + 2
#   bash desktop_pull_backup.sh --with-maps            # ... plus sfincs_map.nc
#   bash desktop_pull_backup.sh --only inputs|archive|runs
#   DEST=/media/ty/backup/amarel bash desktop_pull_backup.sh
#
# Copy this file to the desktop once (scp tpj8@amarel.rutgers.edu:nj_bight_sfincs/scripts/desktop_pull_backup.sh .)
# — or keep the repo cloned there and run it from scripts/.
set -euo pipefail

REMOTE="${REMOTE:-tpj8@amarel.rutgers.edu}"
DEST="${DEST:-$HOME/amarel_backup}"
HOME_R="/cache/home/tpj8"
SCRATCH_R="/scratch/tpj8/nj_bight_sfincs"

DRY=""
WITH_MAPS=0
ONLY="all"
LIST=0
for a in "$@"; do
  case "$a" in
    -n|--dry-run) DRY="-n" ;;
    --with-maps) WITH_MAPS=1 ;;
    --only) ;;
    inputs|archive|runs) ONLY="$a" ;;
    --list) LIST=1 ;;
    -h|--help) sed -n '2,40p' "$0"; exit 0 ;;
    *) echo "unknown arg: $a" >&2; exit 2 ;;
  esac
done

# -a: perms/times/symlinks (data/ symlinks INTO the archive are kept AS symlinks — the
#     archive is mirrored separately, so nothing is duplicated)
# -H: preserve hard links (the arms share their template inputs by hard link)
# --partial --append-verify: a dropped VPN resumes a 5 G file instead of restarting it
RSYNC=(rsync -aH --partial --append-verify --info=progress2,stats1 $DRY)

# Tier-2 filter. Order matters: directory excludes first, then the keep-list, then
# everything else out. --prune-empty-dirs drops arms that contribute nothing.
RUN_FILTER=(
  --exclude='_template_sealed/'
  --exclude='floodmaps/'
  --exclude='subgrid/'
  --exclude='snapwave.upw'
  --exclude='roughness.nc'
  --exclude='sfincs.nc'
  --exclude='sfincs_subgrid.nc'
  --exclude='sfincs_netampr.nc'
  --include='*/'
  --include='metrics*.csv'
  --include='report.html'
  --include='sfincs_his.nc'
  --include='sfincs.log'
  --include='sfincs.inp'
  --include='provenance.txt'
  --include='floodmap_hmax_lev3.tif'
  --include='.window'
  --include='sfincs.obs'
  --include='sfincs.weir'
  --include='sfincs.crs'
  --include='snapwave.b*'
  --include='sfincs_net*.nc'
  --include='gis/**'
)
if [ "$WITH_MAPS" = 1 ]; then RUN_FILTER+=(--include='sfincs_map.nc'); fi
RUN_FILTER+=(--exclude='*' --prune-empty-dirs)

manifest() {
  cat <<EOF
remote : $REMOTE
dest   : $DEST
tier 1 : $HOME_R/nj_bight_sfincs/data/   -> $DEST/nj_bight_sfincs/data/
         $HOME_R/sfincs_data/            -> $DEST/sfincs_data/
         $HOME_R/nj_coast_sfincs/        -> $DEST/nj_coast_sfincs/
tier 2 : $SCRATCH_R/experiments/         -> $DEST/nj_bight_sfincs/experiments/
         keep: metrics*.csv report.html sfincs_his.nc sfincs.log sfincs.inp provenance.txt
               floodmap_hmax_lev3.tif .window sfincs.obs sfincs.weir sfincs.crs snapwave.b* sfincs_net*.nc gis/
         drop: _template_sealed/ floodmaps/ subgrid/ snapwave.upw roughness.nc sfincs.nc sfincs_subgrid.nc
               sfincs_map.nc (kept only with --with-maps)
no --delete: removals on Amarel are never propagated.
EOF
}

if [ "$LIST" = 1 ]; then manifest; exit 0; fi
manifest
mkdir -p "$DEST/nj_bight_sfincs"

if [ "$ONLY" = all ] || [ "$ONLY" = inputs ]; then
  echo "== tier 1: inputs"
  "${RSYNC[@]}" "$REMOTE:$HOME_R/nj_bight_sfincs/data/" "$DEST/nj_bight_sfincs/data/"
  "${RSYNC[@]}" "$REMOTE:$HOME_R/sfincs_data/" "$DEST/sfincs_data/"
fi
if [ "$ONLY" = all ] || [ "$ONLY" = archive ]; then
  echo "== tier 1: frozen archive"
  "${RSYNC[@]}" "$REMOTE:$HOME_R/nj_coast_sfincs/" "$DEST/nj_coast_sfincs/"
fi
if [ "$ONLY" = all ] || [ "$ONLY" = runs ]; then
  echo "== tier 2: scored runs (scratch)"
  "${RSYNC[@]}" "${RUN_FILTER[@]}" "$REMOTE:$SCRATCH_R/experiments/" "$DEST/nj_bight_sfincs/experiments/"
fi
date "+%F %T  done" | tee -a "$DEST/pull_log.txt"
