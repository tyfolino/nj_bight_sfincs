#!/bin/bash
# Re-clip the NJ statewide 10-ft lidar DEM for a new domain, build overviews, and CHECK it.
#   NJ_DOMAIN=v4 sbatch hpc/clip_nj_dem.slurm
# Output: data/elevation_<dom>/nj_10ft_dem_<dom>.tif, a SYMLINK into
# /scratch/tpj8/nj_bight_sfincs_data/elevation_<dom>/ (bulk lives on scratch, as the 3DEP
# and CUDEM tiles do). The check compares it at random land points with the previous
# domain's clip (~0 m expected where they overlap) and with 3DEP 1/3" (~0.5 m) — the
# numbers that would have caught the 09-24 clip being georeferenced ~14 km west.
#SBATCH -p main
# 🔴 halk* nodes cannot write to /cache/home and fail silently — see hpc/sfincs_run.slurm.
#SBATCH --exclude=halk[0001-0159]
#SBATCH -c 4
#SBATCH --mem=48G
#SBATCH -t 06:00:00
#SBATCH -J clip_nj_dem
#SBATCH -o logs/clip_nj_dem_%j.out
set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
export PATH=$HOME/nj_sandy_sfincs/micromamba/envs/sfincs/bin:$PATH
export PYTHONPATH=$PWD NJ_ROOT=$PWD
export NJ_DOMAIN="${NJ_DOMAIN:?set NJ_DOMAIN in the submitting shell}"
export PROJ_DATA=/home/tpj8/nj_sandy_sfincs/micromamba/envs/sfincs/share/proj
export GDAL_CACHEMAX=4096
hostname; date; echo "NJ_DOMAIN=$NJ_DOMAIN"
# 🔴 A file edited from the VS Code session (itself on a halk node) can read STALE or
# EMPTY on a compute node for a while — 2026-09-27 an empty script ran and exited 0.
# EXPECT_MD5=<file of `md5sum` lines, written at submit time> makes the job refuse.
if [ -n "${EXPECT_MD5:-}" ]; then md5sum -c "$EXPECT_MD5" || { echo "STALE FILES — refusing"; exit 3; }; fi

D=data/elevation_$NJ_DOMAIN
F=nj_10ft_dem_$NJ_DOMAIN.tif
SCR=/scratch/tpj8/nj_bight_sfincs_data/elevation_$NJ_DOMAIN
mkdir -p "$SCR" "$D"
[ -e "$D/$F" ] || [ -L "$D/$F" ] || ln -s "$SCR/$F" "$D/$F"
ls -l "$D/$F"

/usr/bin/time -v python scripts/download_3dep.py
gdalinfo -nomd -norat -noct "$D/$F" | grep -E 'Size is|Pixel Size|Upper Left|Lower Right|NoData'

echo "== overviews"; date
gdaladdo -ro --config COMPRESS_OVERVIEW DEFLATE --config BIGTIFF_OVERVIEW YES -r average \
  "$D/$F" 2 4 8 16 32 64

echo "== check"; date
python scripts/check_dem_clip.py "$D/$F" \
  --ref data/elevation_v3/nj_10ft_dem_v3.tif \
  --ref-group 3dep_13 data/elevation_v4/3dep/*.tif
ls -lL "$D/$F" "$D/$F.ovr"
date
