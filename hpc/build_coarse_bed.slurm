#!/bin/bash
# The 25 m coarse bed for a domain (scripts/build_coarse_bed.py): refinement gating + face z.
#   NJ_DOMAIN=v4 sbatch hpc/build_coarse_bed.slurm
# Output is a SYMLINK into /scratch/tpj8/nj_bight_sfincs_data/elevation_<dom>/ (bulk lives on
# scratch); per-tier warps go to a scratch TMPDIR and are removed at the end.
#SBATCH -p main
# 🔴 halk* nodes cannot write to /cache/home and fail silently — see hpc/sfincs_run.slurm.
#SBATCH --exclude=halk[0001-0159]
#SBATCH -c 4
#SBATCH --mem=32G
#SBATCH -t 06:00:00
#SBATCH -J coarse_bed
#SBATCH -o logs/coarse_bed_%j.out
set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
export PATH=$HOME/nj_sandy_sfincs/micromamba/envs/sfincs/bin:$PATH
export PYTHONPATH=$PWD NJ_ROOT=$PWD
export NJ_DOMAIN="${NJ_DOMAIN:?set NJ_DOMAIN in the submitting shell}"
export PROJ_DATA=/home/tpj8/nj_sandy_sfincs/micromamba/envs/sfincs/share/proj
export GDAL_CACHEMAX=4096
export TMPDIR=/scratch/tpj8/tmp; mkdir -p "$TMPDIR"
hostname; date; echo "NJ_DOMAIN=$NJ_DOMAIN"
# 🔴 A file edited from the VS Code session (itself on a halk node) can read STALE or
# EMPTY on a compute node for a while — 2026-09-27 an empty script ran and exited 0.
# EXPECT_MD5=<file of `md5sum` lines, written at submit time> makes the job refuse.
if [ -n "${EXPECT_MD5:-}" ]; then md5sum -c "$EXPECT_MD5" || { echo "STALE FILES — refusing"; exit 3; }; fi
D=data/elevation_$NJ_DOMAIN; F=bed_${NJ_DOMAIN}_coarse_25m.tif
SCR=/scratch/tpj8/nj_bight_sfincs_data/elevation_$NJ_DOMAIN
mkdir -p "$SCR"
[ -e "$D/$F" ] || [ -L "$D/$F" ] || ln -s "$SCR/$F" "$D/$F"
/usr/bin/time -v python scripts/build_coarse_bed.py
ls -lL "$D/$F"
date
