#!/usr/bin/env python3
"""
Download the NJ OGIS statewide 10-ft (~3 m) LiDAR DEM from the njogis-elevation
S3 bucket, clip to a bbox of interest, reproject to WGS-84, and write a
compressed GeoTIFF for use in the hydromt data catalog.

Source: s3://njogis-elevation  (public, no credentials required)
Resolution: 10 ft (~3 m), EPSG:6527 (NJ State Plane 2011, US survey feet)
Coverage: full New Jersey statewide mosaic

Usage:
    conda run -n sfincs python scripts/download_3dep.py

Raw download (~16 GB, one-time):
    data/elevation/raw/Rast_statewide_10ft_DEM.img
    data/elevation/raw/Rast_statewide_10ft_DEM.ige

Output:
    data/elevation/nj_10ft_dem.tif   (clipped, WGS-84, deflate-compressed)
"""

from pathlib import Path

import boto3
import rasterio
import rasterio.warp
from botocore import UNSIGNED
from botocore.config import Config

# ── clip bbox (WGS-84) ────────────────────────────────────────────────────────
# From the ACTIVE DOMAIN's region polygon. The statewide source mosaic covers all
# of New Jersey, so every increment south is served by moving the region polygon
# alone — no new download, just a re-clip of the 16 GB raw .img/.ige already on
# disk under the shared data root.
from nj_sfincs import domain as _domain  # noqa: E402

BBOX_WGS84 = _domain.active().bbox_ll(buffer_deg=0.05)  # west, south, east, north

# ── paths ─────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
# RAW_DIR stays in the archive: the 16.5 GB statewide `.ige` mosaic already lives there
# and is READ-only, which is fine — this script only reads it. ⭐ It is STATEWIDE, so the
# southern extension is a local RE-CLIP, not a download.
RAW_DIR = ROOT / "data" / "elevation" / "raw"

# 🔴 PER-DOMAIN OUTPUT. The archived `nj_10ft_dem.tif` clip stops at lat 39.645 and is
# what the frozen domains were built against; a new domain gets its own, bigger clip.
from nj_sfincs import domain as _domain  # noqa: E402

OUTPUT = _domain.acquisition_dir("elevation") / f"nj_10ft_dem_{_domain.active().name}.tif"

# ── S3 source ─────────────────────────────────────────────────────────────────
BUCKET = "njogis-elevation"
S3_PREFIX = "derived_products/statewide_2021/Statewide_10ft_DEM_2021/Raster/"
FILES = ["Rast_statewide_10ft_DEM.img", "Rast_statewide_10ft_DEM.ige"]

SRC_CRS = "EPSG:6527"   # NJ State Plane 2011, US survey feet
DST_CRS = "EPSG:4326"   # WGS-84


def s3_client():
    return boto3.client("s3", config=Config(signature_version=UNSIGNED), region_name="us-west-2")


def download_raw(s3, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    for fname in FILES:
        dest = dest_dir / fname
        if dest.exists():
            print(f"  skip (cached)  {fname}")
            continue
        key = S3_PREFIX + fname
        size_mb = s3.head_object(Bucket=BUCKET, Key=key)["ContentLength"] / 1e6
        print(f"  downloading    {fname}  ({size_mb:.0f} MB)")
        s3.download_file(
            Bucket=BUCKET,
            Key=key,
            Filename=str(dest),
            Callback=_progress(size_mb),
        )
        print()


def _progress(total_mb: float):
    downloaded = [0.0]

    def cb(n_bytes):
        downloaded[0] += n_bytes / 1e6
        pct = min(downloaded[0] / total_mb * 100, 100)
        print(f"\r    {downloaded[0]:.0f} / {total_mb:.0f} MB  ({pct:.0f}%)", end="", flush=True)

    return cb


#: v3's output pixel (nj_10ft_dem_v3.tif), kept so the two clips are comparable.
RES_DEG = 0.000035050576912
#: US survey feet → m. v3's clip used 0.3048 (international foot; 2 ppm low, 0.06 mm per
#: 100 ft) — kept identical so a v3/v4 diff is zero where the clips overlap.
FT_TO_M = 0.3048


def clip_and_reproject(src_path: Path, dst_path: Path, bbox_wgs84: tuple) -> None:
    """Warp the statewide mosaic to WGS-84 over bbox ∩ the mosaic's own extent.

    🔴 REWRITTEN 2026-09-27. The old version read ``src.window(bbox)`` and georeferenced
    the result with ``src.window_transform(window)``. When the bbox starts WEST of (or
    north of) the raster, rasterio TRUNCATES the read to the raster but the window
    transform still starts at the requested edge — measured: 1,000 px asked from col −500
    returned 500 px labelled 5,000 ft too far west. v3's bbox started inside NJ and was
    fine; v4's starts at −75.77 against the mosaic's −75.60 and shifted the state ~14 km
    west ("> 5 m off 3DEP on 81 % of land", STATUS 09-25). Now: a WarpedVRT on an explicit
    output grid (every pixel georeferenced by construction), nodata honoured in the
    bilinear kernel, streamed in row blocks, written atomically.
    """
    import os
    import tempfile
    from math import ceil

    from rasterio.enums import Resampling
    from rasterio.transform import from_origin
    from rasterio.vrt import WarpedVRT
    from rasterio.windows import Window

    dst_path = Path(dst_path).resolve()  # write THROUGH a symlink to scratch
    with rasterio.open(src_path) as src:
        nodata = src.nodata if src.nodata is not None else -9999.0
        sw, ss, se, sn = rasterio.warp.transform_bounds(src.crs, DST_CRS, *src.bounds)
        west, south, east, north = bbox_wgs84
        west, south, east, north = max(west, sw), max(south, ss), min(east, se), min(north, sn)
        width = ceil((east - west) / RES_DEG)
        height = ceil((north - south) / RES_DEG)
        transform = from_origin(west, north, RES_DEG, RES_DEG)
        print(
            f"clip {SRC_CRS} → {DST_CRS}: lon {west:.4f}..{east:.4f} lat {south:.4f}..{north:.4f}"
            f" (bbox ∩ mosaic {sw:.3f}..{se:.3f} / {ss:.3f}..{sn:.3f}), {width} x {height} px"
        )
        profile = dict(
            driver="GTiff", height=height, width=width, count=1, dtype="float32",
            crs=DST_CRS, transform=transform, nodata=nodata, compress="deflate",
            tiled=True, blockxsize=512, blockysize=512, BIGTIFF="YES",
        )
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=dst_path.parent, suffix=".tmp.tif")
        os.close(fd)
        with WarpedVRT(
            src, crs=DST_CRS, transform=transform, width=width, height=height,
            resampling=Resampling.bilinear, src_nodata=nodata, nodata=nodata,
        ) as vrt, rasterio.open(tmp, "w", **profile) as dst:
            step = 4096
            for r0 in range(0, height, step):
                w = Window(0, r0, width, min(step, height - r0))
                a = vrt.read(1, window=w).astype("float32")
                valid = a != nodata
                a[valid] *= FT_TO_M
                dst.write(a, 1, window=w)
                print(f"  rows {r0 + w.height}/{height}", flush=True)
        os.replace(tmp, dst_path)
    print(f"Done: {dst_path}")


def main() -> None:
    s3 = s3_client()

    print("Downloading raw NJ 10-ft DEM from S3 (~16 GB total) ...")
    download_raw(s3, RAW_DIR)

    img_path = RAW_DIR / "Rast_statewide_10ft_DEM.img"
    clip_and_reproject(img_path, OUTPUT, BBOX_WGS84)


if __name__ == "__main__":
    main()
