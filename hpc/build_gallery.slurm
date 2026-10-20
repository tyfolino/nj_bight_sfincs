#!/bin/bash
# Run-gallery figures for finished arms (scripts/build_gallery.py → nj_sfincs/gallery.py),
# one subprocess per arm, serially, then publish the static site (scripts/publish_gallery.py,
# default ~/sandy_flood_site — never committed here). ONE job for everything (few SLURM jobs).
# Measured 2026-10-19: ~17 G peak per v4_refreeze arm (the gauges' SfincsModel open).
#   GALLERY_DOMAINS="v4_refreeze v3" EXPECT_MD5=logs/<job>_expected.md5 sbatch hpc/build_gallery.slurm
#   GALLERY_ARMS_v3="naccs-premier,naccs-nowaves"   # optional per-domain arm list
#SBATCH -p main
# 🔴 halk* nodes cannot write to /cache/home and fail silently — see hpc/sfincs_run.slurm.
#SBATCH --exclude=halk[0001-0159]
#SBATCH -c 4
#SBATCH --mem=64G
#SBATCH -t 06:00:00
#SBATCH -J gallery
#SBATCH -o logs/slurm/%x_%j.out
set -uo pipefail
cd "$SLURM_SUBMIT_DIR"
export PATH=$HOME/nj_sandy_sfincs/micromamba/envs/sfincs/bin:$PATH
export PYTHONPATH=$PWD NJ_ROOT=$PWD
export PROJ_DATA=/home/tpj8/nj_sandy_sfincs/micromamba/envs/sfincs/share/proj
# EXPECT_MD5=<md5sum file written at submit time>: refuse to run stale copies (CLAUDE.md §5).
if [ -n "${EXPECT_MD5:-}" ]; then md5sum -c "$EXPECT_MD5" || { echo "STALE FILES — refusing"; exit 3; }; fi
hostname; date
rc=0
for d in ${GALLERY_DOMAINS:?set GALLERY_DOMAINS, e.g. "v4_refreeze v3"}; do
  var="GALLERY_ARMS_${d}"
  arms="${!var:-}"
  echo "=== domain $d arms=${arms:-<all finished>}"
  NJ_DOMAIN=$d /usr/bin/time -v python scripts/build_gallery.py ${arms:+--arms "$arms"} || rc=1
done
date
python scripts/publish_gallery.py || rc=1
date
exit $rc
