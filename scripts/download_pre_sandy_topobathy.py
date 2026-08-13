#!/usr/bin/env python3
"""
Download the 2010 USACE NCMP Topobathy LiDAR DEM for NJ Atlantic Coast,
clipped to the model bbox.  This is the canonical PRE-Hurricane-Sandy
1 m topobathy product: collected in 2010, NAD83, true topobathy
(LiDAR + nearshore bathy fused).

Why this dataset (and not the 2022 USACE or NJ/Delaware CoNED):
    Sandy made landfall 2012-10-29.  Post-storm products bake in
    ~$1B+ of NJ beach replenishment + engineered dunes that did not
    exist during the storm — using them would systematically
    under-predict overtopping in a hindcast.  The 2010 NCMP product
    is ~2 years pre-storm — close enough that the beach state is
    representative without contamination from post-Sandy works.

Source : s3://noaa-nos-coastal-lidar-pds/dem/USACE_NJ_DEM_2010_9456/
NOAA ID: 9456     Whole-mosaic VRT (EPSG:4269) is provided.
Total raw dataset: ~721 MB (41 tiles).  We clip via /vsicurl/ so
only the bytes covering the bbox are fetched.

Usage:
    conda run -n sfincs python scripts/download_pre_sandy_topobathy.py

Output:
    data/elevation/usace_nj_2010_topobathy_clip.tif
"""

import subprocess
import sys
from pathlib import Path

# Clip extent comes from the ACTIVE DOMAIN's region polygon, not a literal. The
# old repo hardcoded (-74.06, 40.14, -73.84, 40.51) under a comment reading
# "update this if region.geojson changes" — which is precisely the kind of
# instruction that gets missed on the second domain, and would silently clip the
# pre-Sandy topobathy to the old footprint while everything else grew.
#
# The source VRT spans lon -74.97..-73.97, lat 38.93..40.48 — the whole NJ
# Atlantic coast past Cape May — so it already covers every planned increment;
# only this bbox has to move. gdalwarp intersects with the source extent, so
# asking for more than the VRT holds is harmless.
#
# On memory: the old comment warned this raster is ~20 GB in RAM at a large bbox
# and OOMed the elevation merge. That was a desktop constraint. On Amarel the
# build runs under hpc/build_mesh.slurm (--mem=150G), so size the clip to the
# domain and let the scheduler carry it.
from nj_sfincs import domain as _domain  # noqa: E402
from nj_sfincs.gdaltools import run_gdal  # noqa: E402

BBOX_WGS84 = _domain.active().bbox_ll(buffer_deg=0.02)  # west, south, east, north

VRT_URL = (
    "/vsicurl/https://noaa-nos-coastal-lidar-pds.s3.amazonaws.com/"
    "dem/USACE_NJ_DEM_2010_9456/USACE_NJ_DEM_2010_m9456_EPSG-4269.vrt"
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "elevation" / "usace_nj_2010_topobathy_clip.tif"


def _clamp_to_source(bbox: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    """Intersect the requested bbox with the source VRT's own extent.

    The 2010 NCMP survey is a COASTAL STRIP (lon -74.97..-73.97), while the model
    region now runs ~50 km further offshore to -73.45. Warping to the full region
    box produces a grid that is mostly NoData: 98,897 x 95,563 px, of which the
    eastern ~60% has nothing in it. It costs nothing in correctness — NoData just
    falls through to the next elevation tier — but it is a needlessly large raster
    to carry through the merge, and it grows every time the domain steps south.

    Clamping is safe precisely BECAUSE the merge is ordered: this tier only ever
    supplies data where it has data.
    """
    import rasterio
    from rasterio.warp import transform_bounds

    w, s, e, n = bbox
    with rasterio.open(VRT_URL) as src:
        sw, ss, se, sn = transform_bounds(src.crs, "EPSG:4326", *src.bounds)
    out = (max(w, sw), max(s, ss), min(e, se), min(n, sn))
    if out != bbox:
        print(f"  clamped to source extent: {tuple(round(v, 4) for v in out)}")
    return out


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    west, south, east, north = _clamp_to_source(BBOX_WGS84)
    args = [
        "-overwrite",
        "-t_srs", "EPSG:4326",
        "-te", str(west), str(south), str(east), str(north),
        "-te_srs", "EPSG:4326",
        "-r", "bilinear",
        "-of", "GTiff",
        "-co", "COMPRESS=DEFLATE",
        "-co", "TILED=YES",
        "-co", "BLOCKXSIZE=512",
        "-co", "BLOCKYSIZE=512",
        "-co", "BIGTIFF=IF_SAFER",
        "--config", "GDAL_HTTP_UNSAFESSL", "YES",
        "--config", "VSI_CACHE", "TRUE",
        "--config", "GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR",
        VRT_URL,
        str(OUTPUT),
    ]
    print(f"Clipping 2010 USACE NJ topobathy to bbox {BBOX_WGS84} ...", flush=True)
    print(f"  → {OUTPUT}", flush=True)
    run_gdal("gdalwarp", args)  # raises on non-zero exit
    print("Done.")


if __name__ == "__main__":
    main()
