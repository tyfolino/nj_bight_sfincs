#!/usr/bin/env bash
# desktop_pull_backup.sh — run this ON THE DESKTOP (the 1 TB HDD), not on Amarel.
#
# Pulls, over SSH + rsync, the two things that cannot be regenerated from git:
#
#   TIER 1  irreplaceable INPUTS. ~/nj_bight_sfincs/data/ itself holds mostly SYMLINKS, and
#           rsync copies those as links, so the bulk behind them is pulled separately:
#           /scratch/tpj8/nj_bight_sfincs_data/        (~82 G, NOT backed up by OARC since the
#           10-05 move: frozen meshes, elevation_v3/v4, the modern land, NACCS, buildings,
#           infiltration. modern_2026/raw (106 G, public downloads) only with --with-raw)
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
#           provenance.txt, floodmap_hmax_lev3.tif, tide_stats.nc, the small forcing files and gis/;
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
#   bash desktop_pull_backup.sh --with-raw             # ... plus modern_2026/raw (106 G)
#   bash desktop_pull_backup.sh --only inputs|archive|runs
#   DEST=/media/ty/backup/amarel bash desktop_pull_backup.sh
#
# ARCHIVE mode (2026-11-04, logs/scratch_survey_2026-11-04/): copy named run units off scratch before
# they are deleted there, e.g. into a OneDrive-synced folder:
#   DEST=~/OneDrive/amarel_archive bash desktop_pull_backup.sh --units v4_refreeze_swz_wk0,v4_refreeze_swz/p4-premier+src-deal-overtop
#   A unit is a path under experiments/ (a domain or one arm). Each arm keeps everything tier 2 keeps PLUS
#   sfincs_map.nc, sfincs_subgrid.nc and sfincs.nc (so it can be re-scored); subgrid/*.tif, roughness.nc,
#   snapwave.upw and _template_sealed/ stay out (rebuildable from tier 1 + the recipe in provenance.txt).
#   Afterwards it checks every file against the md5 list written ON AMAREL by
#   `bash scripts/desktop_pull_backup.sh --manifest <units>` (into $SCRATCH_R/archive_manifests/) and
#   prints VERIFIED / FAILED per unit. Delete on scratch only after VERIFIED, and only on the user's say-so.
#
# Copy this file to the desktop once (scp tpj8@amarel.rutgers.edu:nj_bight_sfincs/scripts/desktop_pull_backup.sh .)
# — or keep the repo cloned there and run it from scripts/.
set -euo pipefail

REMOTE="${REMOTE:-tpj8@amarel.rutgers.edu}"
DEST="${DEST:-$HOME/amarel_backup}"
HOME_R="/cache/home/tpj8"
SCRATCH_R="/scratch/tpj8/nj_bight_sfincs"
SCRATCH_DATA_R="/scratch/tpj8/nj_bight_sfincs_data"

DRY=""
WITH_MAPS=0
WITH_RAW=0
ONLY="all"
LIST=0
UNITS=""
MANIFEST=0
for a in "$@"; do
  if [ "${NEXT_UNITS:-0}" = 1 ]; then UNITS="$a"; ONLY=units; NEXT_UNITS=0; continue; fi
  if [ "${MANIFEST:-0}" = 1 ] && [ "${a#-}" = "$a" ]; then UNITS="${UNITS:+$UNITS,}$a"; continue; fi
  case "$a" in
    -n|--dry-run) DRY="-n" ;;
    --with-maps) WITH_MAPS=1 ;;
    --with-raw) WITH_RAW=1 ;;
    --only) ;;
    inputs|archive|runs) ONLY="$a" ;;
    --list) LIST=1 ;;
    --units=*) UNITS="${a#--units=}"; ONLY=units ;;
    --units) NEXT_UNITS=1 ;;
    --manifest) MANIFEST=1 ;;
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
  --include='provenance*.txt'
  --include='engine.txt'
  --include='MANIFEST.md'
  --include='.retired'
  --include='floodmap_hmax_lev3.tif'
  --include='tide_stats.nc'
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
# ARCHIVE filter (--units / --manifest): tier 2's keep-list + the three files a re-score needs.
ARCH_FILTER=(
  --exclude='_template_sealed/' --exclude='floodmaps/' --exclude='subgrid/' --exclude='snapwave.upw'
  --exclude='roughness.nc' --exclude='rst/' --exclude='*.rst'
  --include='*/'
  --include='sfincs_map.nc' --include='sfincs_subgrid.nc' --include='sfincs.nc'
  --include='restart_history.txt' --include='*.md' --include='*.json' --include='*.txt'
)
for f in "${RUN_FILTER[@]}"; do case "$f" in --include=*) ARCH_FILTER+=("$f") ;; esac; done
ARCH_FILTER+=(--exclude='*' --prune-empty-dirs)
DATA_FILTER=()
if [ "$WITH_RAW" = 0 ]; then DATA_FILTER+=(--exclude='/modern_2026/raw/'); fi

manifest() {
  cat <<EOF
remote : $REMOTE
dest   : $DEST
tier 1 : $HOME_R/nj_bight_sfincs/data/   -> $DEST/nj_bight_sfincs/data/
         $SCRATCH_DATA_R/                -> $DEST/nj_bight_sfincs_data/  (modern_2026/raw only with --with-raw)
         $HOME_R/sfincs_data/            -> $DEST/sfincs_data/
         $HOME_R/nj_coast_sfincs/        -> $DEST/nj_coast_sfincs/
tier 2 : $SCRATCH_R/experiments/         -> $DEST/nj_bight_sfincs/experiments/
         keep: metrics*.csv report.html sfincs_his.nc sfincs.log sfincs.inp provenance*.txt engine.txt .retired MANIFEST.md
               floodmap_hmax_lev3.tif .window sfincs.obs sfincs.weir sfincs.crs snapwave.b* sfincs_net*.nc gis/
         drop: _template_sealed/ floodmaps/ subgrid/ snapwave.upw roughness.nc sfincs.nc sfincs_subgrid.nc
               sfincs_map.nc (kept only with --with-maps)
no --delete: removals on Amarel are never propagated.
EOF
}

if [ "$MANIFEST" = 1 ]; then  # ON AMAREL: md5 of exactly what --units will copy
  [ -n "$UNITS" ] || { echo "--manifest needs units" >&2; exit 2; }
  OUT="$SCRATCH_R/archive_manifests"; mkdir -p "$OUT"; EMPTY=$(mktemp -d)
  IFS=, read -ra US <<< "$UNITS"
  for u in "${US[@]}"; do
    u="${u%/}"; [ -d "$SCRATCH_R/experiments/$u" ] || { echo "no such unit: $u" >&2; exit 2; }
    m="$OUT/$(echo "$u" | tr '/+' '__').md5"
    ( cd "$SCRATCH_R/experiments" && rsync -aHn --out-format='%n' "${ARCH_FILTER[@]}" "$u/" "$EMPTY/" \
        | grep -v '/$' | sed "s|^|$u/|" | grep -v "^$u/\.\?$" | tr '\n' '\0' | xargs -0 md5sum ) > "$m.partial"
    mv "$m.partial" "$m"
    echo "$u: $(wc -l < "$m") files, $(cd "$SCRATCH_R/experiments" && cut -c35- "$m" | tr '\n' '\0' | du -ch --files0-from=- 2>/dev/null | tail -1 | cut -f1) -> $m"
  done
  rmdir "$EMPTY"; exit 0
fi
if [ "$ONLY" = units ]; then  # ON THE DESKTOP: copy each unit, then verify against Amarel's md5 list
  [ -n "$UNITS" ] || { echo "--units needs a list" >&2; exit 2; }
  A="$DEST/nj_bight_sfincs/experiments"; mkdir -p "$A"
  IFS=, read -ra US <<< "$UNITS"; RESULT=()
  for u in "${US[@]}"; do
    u="${u%/}"; m="$(echo "$u" | tr '/+' '__').md5"
    echo "== archive $u"
    mkdir -p "$A/$u"
    "${RSYNC[@]}" "${ARCH_FILTER[@]}" "$REMOTE:$SCRATCH_R/experiments/$u/" "$A/$u/"
    [ -n "$DRY" ] && continue
    if rsync -a "$REMOTE:$SCRATCH_R/archive_manifests/$m" "$A/.$m" 2>/dev/null; then
      if ( cd "$A" && md5sum -c --quiet ".$m" ); then RESULT+=("VERIFIED  $u ($(wc -l < "$A/.$m") files)")
      else RESULT+=("FAILED    $u (see md5sum output above)"); fi
    else RESULT+=("UNCHECKED $u (no manifest on Amarel: run --manifest there first)"); fi
  done
  printf '%s\n' "${RESULT[@]}" | tee -a "$DEST/pull_log.txt"
  date "+%F %T  archive done" | tee -a "$DEST/pull_log.txt"; exit 0
fi
if [ "$LIST" = 1 ]; then manifest; exit 0; fi
manifest
mkdir -p "$DEST/nj_bight_sfincs"

if [ "$ONLY" = all ] || [ "$ONLY" = inputs ]; then
  echo "== tier 1: inputs"
  "${RSYNC[@]}" "$REMOTE:$HOME_R/nj_bight_sfincs/data/" "$DEST/nj_bight_sfincs/data/"
  "${RSYNC[@]}" ${DATA_FILTER[@]+"${DATA_FILTER[@]}"} "$REMOTE:$SCRATCH_DATA_R/" "$DEST/nj_bight_sfincs_data/"
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
