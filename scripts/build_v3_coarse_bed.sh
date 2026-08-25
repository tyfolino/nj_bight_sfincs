#!/usr/bin/env bash
# The v3 COARSE bed: every tier of V3_ELEVATION_LIST warped to 25 m / EPSG:32618 and
# stacked in list order (last = highest priority), with 50/100/200 m overviews.
# Used ONLY for quadtree refinement gating and the face elevation z (Domain.
# coarse_elevation_list); the subgrid samples the native tiers. Base tiers are
# resampled BILINEAR (hydromt's own face method); CARVING tiers (eHydro / Shrewsbury /
# CoNED-free surveys) are resampled MIN so a 5 m channel narrower than a 25 m cell keeps
# its depth — bilinear at 25 m paved 69 Shark-inlet faces and failed the paved-channel
# invariant (2026-08-24). Needs PROJ_DATA/GDAL_DATA in the env (see nj_sfincs/__init__).
set -e
cd "$(dirname "$0")/.."
W=${TMPDIR:-/tmp}/v3_coarse_bed; mkdir -p "$W"
TE="499000 4298500 634000 4500500"
i=0; LIST=""
while read -r f r; do
  i=$((i+1)); gdalwarp -q -overwrite -t_srs EPSG:32618 -te $TE -tr 25 25 -r $r -dstnodata -99999 \
    -of GTiff -co COMPRESS=DEFLATE -co TILED=YES -wo NUM_THREADS=4 -multi "data/$f" "$W/t$i.tif"
  if [ "$f" = "elevation_v3/nj_10ft_dem_v3.tif" ]; then
    # 🔴 The NJ lidar reads 0.0 (NOT NoData) over water and its raster rectangle covers
    # the whole shelf. The model applies zmin=0.001 to it (config.py); without the same
    # threshold here the first coarse bed paved 817,718 offshore faces to z=0 (2026-08-24).
    python - "$W/t$i.tif" <<'PY'
import sys, rasterio, numpy as np
f = sys.argv[1]
with rasterio.open(f) as src:
    a = src.read(1); prof = src.profile
a[(a <= 0.001) | (a == src.nodata)] = -99999
prof.update(nodata=-99999, compress="deflate", tiled=True)
with rasterio.open(f, "w", **prof) as dst:
    dst.write(a, 1)
PY
    echo "  nj_10ft: values <= 0.001 -> NoData"
  fi
  LIST="$LIST $W/t$i.tif"; echo "warped $f ($r)"
done <<'TIERS'
elevation_v3/gmrt_v3.tif bilinear
elevation_v3/nj_10ft_dem_v3.tif bilinear
elevation_v3/cudem13_v3.vrt bilinear
elevation_v3/cudem_nj_v3.vrt bilinear
elevation_v1_5/coned_sw_raritan.tif bilinear
elevation_v3/usace_nj_2010_topobathy_v3.tif bilinear
elevation/shrewsbury_ehydro_2015.tif min
elevation/ehydro_south.tif min
elevation/ehydro_nj.tif min
elevation_v1_5/ehydro_raritan_ak.tif min
elevation_v3/ehydro_south_v3.tif min
TIERS
gdalbuildvrt -overwrite -srcnodata -99999 "$W/stack.vrt" $LIST
gdal_translate -q -of GTiff -co COMPRESS=DEFLATE -co TILED=YES -a_nodata -99999 "$W/stack.vrt" data/elevation_v3/bed_v3_coarse_25m.tif
gdaladdo -q -r average data/elevation_v3/bed_v3_coarse_25m.tif 2 4 8
gdalinfo -stats data/elevation_v3/bed_v3_coarse_25m.tif | grep -E "Size is|STATISTICS_(MIN|MAX)"
rm -rf "$W"; echo DONE
