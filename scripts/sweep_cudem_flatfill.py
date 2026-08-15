#!/usr/bin/env python
"""Find PHANTOM WATER: ground the elevation stack calls water and CoNED calls land.

    NJ_DOMAIN=v1_5_raritan python scripts/sweep_cudem_flatfill.py [--plot]

WHY
---
`cudem_nj` is missing the Ward Point headland — its land stops at lat 40.49982 in every
column across ~800 m and the missing ~230 m of New York State is backfilled as −3 to −5.5 m
of bay (see `scripts/plot_ward_point_bed.py`). That was found BY EYE, on one figure, after
every domain invariant had come back green.

🔴 That is the part worth generalising. `build_static` asserts no active cell has NoData in
the merged bed, and this defect sails through it: the bed is not missing, it is PRESENT AND
WRONG. Any check phrased as "is there data here" is blind to a fill. And a validator that
reads the same stack the model reads (`validate_region_v1_5.py`) cannot help either, because
it inherits the same hole.

So the only thing that can find the next Ward Point is an INDEPENDENT product. This script
diffs the merged stack against USGS CoNED NJ/DE topobathy (1 m) and reports every contiguous
patch where the stack says water and CoNED says land.

⚠️ This is a DISAGREEMENT map, not a truth map. CoNED is another model of the ground, built
from lidar of a particular date. A patch here is a place to LOOK, not automatically a defect;
the Ward Point patch earned its verdict from the straight-line land edge, which is a
signature no real coast has. The `flatness` column is there to help make that call: a fill
has a near-constant value, real bathymetry does not.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
import yaml
from rasterio.features import rasterize
from rasterio.warp import Resampling, reproject

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CONED_DIR = ROOT / "data" / "elevation_v1_5" / "coned"
REGION = ROOT / "data" / "region_v1_5_raritan_edited.geojson"
OUT = ROOT / "reports" / "coned"

#: Analysis resolution. CoNED is 1 m and CUDEM ~3 m; 10 m is fine for finding PATCHES and
#: keeps a 5-tile sweep in memory.
RES_M = 10.0

#: Report patches at least this large. 0.005 km2 = 50 cells at 10 m — below that a
#: disagreement is a shoreline-registration difference between two products, not a hole.
MIN_PATCH_KM2 = 0.005

#: "Water" and "land". The gap is deliberate: cells between these are the intertidal fringe
#: where two products legitimately disagree and nothing useful is learned.
WATER_Z = -0.5
LAND_Z = 0.5


def merged_stack_on(grid_transform, shape, crs):
    """The bed exactly as build_static sees it, resampled onto one CoNED tile's grid.

    Mirrors the top-wins merge and the per-tier zmin screen. Kept in this script rather
    than imported so the sweep still runs if the model package is mid-edit.
    """
    from nj_sfincs.config import BaseConfig

    catalog = yaml.safe_load((ROOT / "data" / "data_catalog.yml").read_text())
    out = np.full(shape, np.nan, dtype="float32")
    for tier in BaseConfig().elevation():
        name = tier.get("elevation") or tier.get("elevtn")
        entry = catalog.get(name)
        if entry is None:
            continue
        path = ROOT / "data" / entry["uri"]
        if not path.exists():
            continue
        if "coned" in name:  # never diff CoNED against itself
            continue
        with rasterio.open(path) as src:
            buf = np.full(shape, np.nan, dtype="float32")
            reproject(
                source=rasterio.band(src, 1),
                destination=buf,
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=grid_transform,
                dst_crs=crs,
                resampling=Resampling.bilinear,
                src_nodata=src.nodata,
                dst_nodata=np.nan,
            )
        buf[buf < -9000] = np.nan
        zmin = tier.get("zmin")
        if zmin is not None:
            buf[buf < zmin] = np.nan
        take = np.isnan(out) & np.isfinite(buf)
        out[take] = buf[take]
    return out


def sweep(plot: bool = False) -> int:
    from scipy import ndimage
    from shapely.geometry import shape as shp_shape
    from shapely.ops import transform as shp_transform

    tiles = sorted(CONED_DIR.glob("NJ_DE_Topobathy_DEM_v2_*.tif"))
    if not tiles:
        print(f"no CoNED tiles in {CONED_DIR} — nothing to sweep")
        return 1
    # ⚠️ COVERAGE IS WHATEVER IS ON DISK, and a partial sweep looks exactly like a clean
    # one. The 2026-08-14 full sweep used 6 tiles (Ward Point -> the Narrows -> Rockaway);
    # 5 were deleted afterwards for disk quota and are re-downloadable from the NOAA bulk
    # store. Say the coverage out loud so "0 patches" is never read as "nothing wrong".
    if len(tiles) < 6:
        print(f"⚠️  only {len(tiles)} tile(s) present — this is a PARTIAL sweep.")
        print("    The full frontage needs 09_21 09_22 09_23 10_20 10_21 10_22 from")
        print("    https://noaa-nos-coastal-lidar-pds.s3.amazonaws.com/dem/"
              "NewJersey_Delaware_Coned_Topobathy_DEM_2015_5040/")
        print(f"    have: {', '.join(t.name[-9:-4] for t in tiles)}\n")
    print(f"sweeping {len(tiles)} CoNED tile(s) at {RES_M:.0f} m\n")

    region = shp_shape(json.loads(REGION.read_text())["features"][0]["geometry"])
    patches = []
    for tp in tiles:
        with rasterio.open(tp) as src:
            sf = RES_M / abs(src.transform.a)
            h, w = int(src.height / sf), int(src.width / sf)
            coned = src.read(1, out_shape=(h, w), resampling=Resampling.average).astype(
                "float32"
            )
            coned[coned < -9000] = np.nan
            t = src.transform * src.transform.scale(src.width / w, src.height / h)
            crs = src.crs
        stack = merged_stack_on(t, (h, w), crs)

        from pyproj import Transformer

        fwd = Transformer.from_crs(4326, crs, always_xy=True)
        reg_p = shp_transform(lambda x, y: fwd.transform(x, y), region)
        inside = rasterize(
            [(reg_p, 1)], out_shape=(h, w), transform=t, fill=0, dtype="uint8"
        ).astype(bool)

        phantom = inside & (stack < WATER_Z) & (coned > LAND_Z)
        n_cmp = int((inside & np.isfinite(stack) & np.isfinite(coned)).sum())
        lab, n = ndimage.label(phantom)
        cell_km2 = (RES_M * RES_M) / 1e6
        print(f"{tp.name}: {n_cmp} comparable cells in-region, {phantom.sum()} phantom "
              f"({phantom.sum()*cell_km2:.3f} km2) in {n} patch(es)")
        inv = Transformer.from_crs(crs, 4326, always_xy=True)
        for i in range(1, n + 1):
            sel = lab == i
            a = sel.sum() * cell_km2
            if a < MIN_PATCH_KM2:
                continue
            rows, cols = np.nonzero(sel)
            xs, ys = rasterio.transform.xy(t, rows, cols)
            lo, la = inv.transform(np.asarray(xs), np.asarray(ys))
            patches.append(
                dict(
                    tile=tp.name,
                    area_km2=round(float(a), 4),
                    lon_min=round(float(lo.min()), 4), lon_max=round(float(lo.max()), 4),
                    lat_min=round(float(la.min()), 4), lat_max=round(float(la.max()), 4),
                    stack_median=round(float(np.nanmedian(stack[sel])), 2),
                    stack_std=round(float(np.nanstd(stack[sel])), 3),
                    coned_median=round(float(np.nanmedian(coned[sel])), 2),
                )
            )

    patches.sort(key=lambda p: -p["area_km2"])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "phantom_water_patches.json").write_text(json.dumps(patches, indent=1))
    print(f"\n{len(patches)} patch(es) >= {MIN_PATCH_KM2} km2 — "
          f"'flatness' = stack std, LOW means a fill\n")
    hdr = f"{'area km2':>9} {'lon range':>19} {'lat range':>19} {'stack z':>8} {'flat':>6} {'CoNED z':>8}"
    print(hdr)
    print("-" * len(hdr))
    for p in patches:
        print(f"{p['area_km2']:9.4f} {p['lon_min']:9.4f}..{p['lon_max']:8.4f} "
              f"{p['lat_min']:9.4f}..{p['lat_max']:8.4f} {p['stack_median']:8.2f} "
              f"{p['stack_std']:6.3f} {p['coned_median']:8.2f}")
    print(f"\ntotal phantom water: {sum(p['area_km2'] for p in patches):.3f} km2")
    print(f"wrote {OUT/'phantom_water_patches.json'}")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plot", action="store_true")
    a = ap.parse_args()
    raise SystemExit(sweep(a.plot))


if __name__ == "__main__":
    main()
