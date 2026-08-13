#!/usr/bin/env python3
"""
Download NOAA NCEI 1/3 arc-second (~10 m) CUDEM tiles for the active domain and
build a VRT mosaic.  This is a FILL TIER between the 1/9" `cudem_nj` and the
~50 m `gmrt_nj` bottom layer.

WHY THIS TIER EXISTS
    The 1/9" product (`NCEI_ninth_Topobathy_2014_8483`) simply does not tile the
    nearshore ocean here.  Checked against that dataset's own authoritative
    urllist (942 URLs, every collection): there is NO 1/9" tile east of -74.00
    south of 40.25, and none east of -73.75 anywhere on this coast.  It is a gap
    in the product, not a download anyone skipped.

    Without this tier, the strip from the surf zone out to the shelf falls
    straight through to GMRT at ~50 m.  That strip is exactly where SnapWave does
    its shoaling and refraction, and coarse offshore bathymetry filling nearshore
    NoData is the known cause of the surf-zone hm0 spikes (GEBCO's integer
    quantisation produced cliffs there; GMRT is float and finer, but 50 m is
    still 5x coarser than the 1/9" it is standing in for).

    The 1/3" sibling dataset DOES cover it.  10 m is coarser than 3 m but it is
    real topobathy on the same NAVD88 vertical datum, so it slots cleanly between
    the two existing tiers.

MERGE POSITION (data_catalog.yml / config.DEFAULT_ELEVATION_LIST):
    ... cudem_nj (1/9", 3 m)  ->  cudem13_nj (1/3", 10 m)  ->  gmrt_nj (50 m)
    Strictly below the 1/9" tier, so it only ever supplies pixels the finer
    product does not have.

Tile selection is driven by the ACTIVE DOMAIN's region bbox, so pushing the
domain south picks up the new tiles automatically.

Usage:
    NJ_ROOT=$PWD PYTHONPATH=$PWD python scripts/download_cudem13.py [--force]

Output:
    data/elevation/cudem13/raw/ncei13_*.tif
    data/elevation/cudem13_nj.vrt
"""

from __future__ import annotations

import re
import sys
import urllib.request
from pathlib import Path

import nj_sfincs  # noqa: F401  (PROJ primer + PROJ_DATA export)
from nj_sfincs import domain as _domain
from nj_sfincs.gdaltools import gdal_bin, run_gdal

URLLIST = (
    "https://noaa-nos-coastal-lidar-pds.s3.amazonaws.com/dem/"
    "NCEI_third_Topobathy_2014_8580/urllist8580.txt"
)

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "elevation" / "cudem13" / "raw"
VRT_OUT = ROOT / "data" / "elevation" / "cudem13_nj.vrt"

# ncei13_n40x00_w074x00_2014v1.tif -> NORTH edge 40.00, WEST edge -74.00, 0.25 deg
TILE_RE = re.compile(r"ncei13_n(\d+)x(\d+)_w(\d+)x(\d+)_[0-9]+v[0-9]+\.tif$")
TILE_DEG = 0.25


def tile_bounds(name: str) -> tuple[float, float, float, float] | None:
    """(west, south, east, north) for a tile filename, or None if unparseable."""
    m = TILE_RE.search(name)
    if not m:
        return None
    north = float(m.group(1)) + float(m.group(2)) / 100
    west = -(float(m.group(3)) + float(m.group(4)) / 100)
    return (west, north - TILE_DEG, west + TILE_DEG, north)


def intersects(a, b) -> bool:
    return not (a[2] <= b[0] or a[0] >= b[2] or a[3] <= b[1] or a[1] >= b[3])


def main(force: bool = False) -> None:
    dom = _domain.active()
    bbox = dom.bbox_ll(buffer_deg=0.05)
    print(f"domain {dom.name}: bbox {bbox}")

    print(f"fetching tile index: {URLLIST}")
    with urllib.request.urlopen(URLLIST, timeout=180) as resp:
        urls = resp.read().decode().split()

    wanted = []
    for u in urls:
        if not u.endswith(".tif"):
            continue
        tb = tile_bounds(u.rsplit("/", 1)[-1])
        if tb and intersects(tb, bbox):
            wanted.append(u)
    wanted = sorted(set(wanted))
    print(f"{len(wanted)} tiles intersect the domain")
    if not wanted:
        sys.exit("no 1/3\" tiles intersect the domain — check the region polygon")

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    for u in wanted:
        dest = RAW_DIR / u.rsplit("/", 1)[-1]
        if dest.exists() and not force:
            print(f"  skip (cached)  {dest.name}")
        else:
            print(f"  downloading    {dest.name}", flush=True)
            tmp = dest.with_suffix(".part")
            urllib.request.urlretrieve(u, tmp)
            tmp.replace(dest)  # atomic: a truncated tile must never look cached
        paths.append(str(dest))

    print(f"building {VRT_OUT}")
    # -allow_projection_difference: these tiles carry a compound CRS (EPSG:5498)
    # whose horizontal part is identical across tiles; gdalbuildvrt otherwise
    # refuses the mosaic over a vertical-datum string mismatch.
    run_gdal("gdalbuildvrt", ["-overwrite", "-allow_projection_difference",
                             str(VRT_OUT), *paths])
    print(f"done — {gdal_bin('gdalbuildvrt')}")


if __name__ == "__main__":
    main(force="--force" in sys.argv)
