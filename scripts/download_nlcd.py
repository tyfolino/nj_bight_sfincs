#!/usr/bin/env python3
"""
Clip Annual NLCD Collection 1 Land Cover, year 2012 (CONUS, USGS/MRLC) to the active
domain, on the SOURCE's own 30 m Albers grid.

WHY
    The archived `data/roughness/nlcd_2012.tif` was a hand-made MRLC request clipped
    for the NJ domains. v4 reaches the Delaware west bank and Cape Henlopen, where
    that clip is NoData (250) on ~500 km² of land, so the Manning / CN tiers fall
    through to the default there. This re-pulls the SAME product for v4's extent.

SOURCE
    MRLC's data-bundle zip holds a Cloud-Optimised GeoTIFF (512 px tiles, deflate)
    stored uncompressed inside the zip, so GDAL reads just the tiles it needs over
    HTTP range requests (`/vsizip//vsicurl/`) — a v4-sized window is a few hundred
    tiles, not the 1.4 GB bundle. The old `.../Annual_NLCD_LndCov_2012_CU_C1V0.tif`
    path is gone (404); the current bundle is C1V1.

GRID
    No resampling. The bbox (region + `BUFFER_DEG`) is taken to the source CRS,
    snapped OUTWARD to the source's pixel lattice, intersected with the source extent
    in INTEGER pixel space, and read as that window — so every output pixel is a
    source pixel, and the transform is computed from the integer offsets, never from
    the requested edge (the rasterio truncation trap in scripts/download_3dep.py).
    Palette and NoData 250 are carried over.

Usage:
    NJ_DOMAIN=v4 PYTHONPATH=$PWD python scripts/download_nlcd.py [--force]

Output:
    data/roughness_<domain>/nlcd_2012_<domain>.tif   (catalog key nlcd_2012_<domain>)
"""

from __future__ import annotations

import argparse
import os
import tempfile
from math import ceil, floor

import rasterio
import rasterio.warp
from rasterio.transform import Affine
from rasterio.windows import Window

import nj_sfincs  # noqa: F401  (PROJ primer + PROJ_DATA export)
from nj_sfincs import domain as _domain

BUNDLE = (
    "https://www.mrlc.gov/downloads/sciweb1/shared/mrlc/data-bundles/"
    "Annual_NLCD_LndCov_2012_CU_C1V1.zip"
)
TIF = "Annual_NLCD_LndCov_2012_CU_C1V1.tif"
SRC = f"/vsizip//vsicurl/{BUNDLE}/{TIF}"

BUFFER_DEG = 0.05
NODATA = 250
ROW_BLOCK = 2048  # rows per read; a multiple of the source's 512 px tiles

#: Keep GDAL from listing the server directory and let it merge adjacent ranges.
GDAL_ENV = dict(
    GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
    CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".zip,.tif,.xml",
    GDAL_HTTP_MULTIRANGE="YES",
    GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES",
    GDAL_HTTP_MAX_RETRY="5",
    GDAL_HTTP_RETRY_DELAY="5",
    VSI_CACHE="TRUE",
)


def source_window(src, bbox_ll: tuple) -> Window:
    """bbox (lon/lat) → an integer window of ``src``, snapped outward, inside it."""
    left, bottom, right, top = rasterio.warp.transform_bounds(
        "EPSG:4326", src.crs, *bbox_ll, densify_pts=101
    )
    inv = ~src.transform
    c0, r0 = inv * (left, top)
    c1, r1 = inv * (right, bottom)
    c0, r0 = max(floor(c0), 0), max(floor(r0), 0)
    c1, r1 = min(ceil(c1), src.width), min(ceil(r1), src.height)
    if c1 <= c0 or r1 <= r0:
        raise SystemExit(f"bbox {bbox_ll} does not intersect {SRC}")
    return Window(c0, r0, c1 - c0, r1 - r0)


def clip(out_path, bbox_ll: tuple) -> None:
    with rasterio.Env(**GDAL_ENV), rasterio.open(SRC) as src:
        if src.nodata != NODATA:
            raise SystemExit(f"source NoData is {src.nodata}, expected {NODATA}")
        win = source_window(src, bbox_ll)
        col0, row0 = int(win.col_off), int(win.row_off)
        width, height = int(win.width), int(win.height)
        # From the INTEGER offsets, so a clamped edge moves the transform with it.
        transform = src.transform * Affine.translation(col0, row0)
        print(
            f"source {src.width} x {src.height} px; window col {col0} row {row0}, "
            f"{width} x {height} px; origin ({transform.c:.0f}, {transform.f:.0f})"
        )
        profile = dict(
            driver="GTiff",
            height=height,
            width=width,
            count=1,
            dtype="uint8",
            crs=src.crs,
            transform=transform,
            nodata=NODATA,
            compress="deflate",
            tiled=True,
            blockxsize=512,
            blockysize=512,
        )
        cmap = src.colormap(1)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=out_path.parent, suffix=".tmp.tif")
        os.close(fd)
        try:
            with rasterio.open(tmp, "w", **profile) as dst:
                dst.write_colormap(1, cmap)
                dst.update_tags(
                    SOURCE=BUNDLE,
                    SOURCE_FILE=TIF,
                    SOURCE_WINDOW=f"col {col0} row {row0} {width}x{height}",
                    BBOX_LL=",".join(f"{v:.6f}" for v in bbox_ll),
                    SCRIPT="scripts/download_nlcd.py",
                )
                for r in range(0, height, ROW_BLOCK):
                    n = min(ROW_BLOCK, height - r)
                    a = src.read(1, window=Window(col0, row0 + r, width, n))
                    if a.shape != (n, width):  # never trust a truncated read
                        raise SystemExit(f"short read {a.shape} != {(n, width)}")
                    dst.write(a, 1, window=Window(0, r, width, n))
                    print(f"  rows {r + n}/{height}", flush=True)
            os.replace(tmp, out_path)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
    print(f"Wrote {out_path} ({out_path.stat().st_size / 1e6:.1f} MB)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--force", action="store_true", help="overwrite an existing clip")
    args = ap.parse_args()

    dom = _domain.active()
    out = _domain.acquisition_dir("roughness", dom) / f"nlcd_2012_{dom.name}.tif"
    if out.exists() and not args.force:
        raise SystemExit(f"{out} exists; pass --force to re-clip")
    bbox = dom.bbox_ll(buffer_deg=BUFFER_DEG)
    print(f"domain {dom.name}: bbox {bbox} (region + {BUFFER_DEG} deg)")
    clip(out, bbox)


if __name__ == "__main__":
    main()
