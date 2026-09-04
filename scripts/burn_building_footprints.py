"""Burn building footprints into a "Building Block" elevation tier for the subgrid.

Writes ``data/elevation_v3/bed_buildings_v3.tif``: inside every NJDEP footprint the value
is **local ground + H**, everywhere else NoData, so that prepended to the v3 elevation
list it raises the subgrid pixels under buildings and touches nothing else. The 25/50 m
solver then sees buildings as POROSITY — less storage, narrower wet cross-sections, a
fully covered small cell goes dry — which is Schubert & Sanders' (2012) Building Block
method applied on the subgrid (Sanders & Schubert 2019, PRIMo). Not mask holes, not
roughness (STATUS 09-03).

**Grid.** An AXIS-ALIGNED 3.125 m EPSG:32618 lattice over the bounding box of the sealed
template's ``subgrid/dep_subgrid_merged.tif``. The template's own lattice is rotated with
the quadtree (~0.8°), and a rotated tier is a risk in hydromt's raster stack, so the tier
is written unrotated and hydromt's ``reproj_method: nearest`` maps it onto the subgrid
pixels. ``scripts/check_buildings_adequacy.py`` measured that step: per-cell burned
fraction vs exact vector coverage is unbiased (bias < 0.001, r 0.99) in both bands.

**Ground.** The template's merged subgrid bed (nearest-resampled onto this lattice), i.e.
exactly the ground the model runs on wherever the footprint is, whichever tier won there
— not the 10 ft DEM alone, which is BELOW several carving tiers in V3_ELEVATION_LIST.

**Height.** A constant cap ``--height`` (default 4 m; see STATUS 09-04). The NJDEP layer
carries no heights, and the cap only has to clear the water: the premier's hmax over
land is 3.2 m at the 99.9th percentile, and every metre above the water coarsens the
equal-depth uv conveyance tables (hydromt spaces them (zmax - zmin)/(nr_levels-1)).

**Screens.** Footprint pixels whose ground is below ``--min-ground`` m NAVD88 (default
0.0, ~MSL) are NOT burned — piers, docks and boathouses over subtidal bed are impervious
surfaces in the source but not walls to a surge. Counted and reported.

Atomic: writes ``<out>.tmp`` then renames. Overviews are NEAREST (a pure subsample) so
that hydromt reading an overview for the 50/100/200 m bands cannot dilate a footprint.

    NJ_DOMAIN=v3 PYTHONPATH=$PWD python scripts/burn_building_footprints.py [--height 4]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pyproj  # noqa: F401,E402
import geopandas as gpd  # noqa: E402
import rasterio  # noqa: E402
from rasterio import features  # noqa: E402
from rasterio.enums import Resampling  # noqa: E402
from rasterio.transform import from_origin  # noqa: E402
from rasterio.vrt import WarpedVRT  # noqa: E402
from rasterio.windows import Window  # noqa: E402
from shapely.geometry import box  # noqa: E402

from nj_sfincs import domain as _domain  # noqa: E402
from nj_sfincs import premier  # noqa: E402
from nj_sfincs.config import DATA  # noqa: E202,E402

NODATA = -9999.0
PIX = 3.125  # the lev-3 (25 m band) subgrid pixel; the 50 m band is this subsampled 2x


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--height", type=float, default=4.0, help="cap above local ground [m]")
    ap.add_argument("--min-ground", type=float, default=0.0,
                    help="do not burn where ground < this [m NAVD88]")
    ap.add_argument("--footprints", default=str(DATA / "buildings_v3" / "njdep_footprints.gpkg"))
    ap.add_argument("--out", default=str(DATA / "elevation_v3" / "bed_buildings_v3.tif"))
    ap.add_argument("--block", type=int, default=2048)
    args = ap.parse_args(argv)

    dom = _domain.active()
    template = premier.sealed_template()
    ground_src = template / "subgrid" / "dep_subgrid_merged.tif"
    out = Path(args.out)
    tmp = out.with_name(out.name + ".tmp")
    t0 = time.time()

    bld = gpd.read_file(args.footprints)
    assert bld.crs.to_epsg() == dom.epsg, bld.crs
    sidx = bld.sindex
    print(f"footprints: {len(bld)} ({bld.area.sum() / 1e6:.1f} km²) in {time.time() - t0:.0f}s",
          flush=True)

    with rasterio.open(ground_src) as g:
        assert g.crs.to_epsg() == dom.epsg
        gb = g.bounds  # rotated raster -> bounds of the rotated rectangle
        x0 = np.floor(gb.left / PIX) * PIX
        y1 = np.ceil(gb.top / PIX) * PIX
        width = int(np.ceil((gb.right - x0) / PIX))
        height = int(np.ceil((y1 - gb.bottom) / PIX))
        transform = from_origin(x0, y1, PIX, PIX)
        profile = dict(
            driver="GTiff", dtype="float32", count=1, width=width, height=height,
            crs=g.crs, transform=transform, nodata=NODATA, tiled=True,
            blockxsize=512, blockysize=512, compress="deflate", predictor=3,
            zlevel=6, sparse_ok=True, bigtiff="yes",
        )
        print(f"output grid {width} x {height} @ {PIX} m, origin ({x0:.1f}, {y1:.1f})", flush=True)

        vrt = WarpedVRT(g, crs=g.crs, transform=transform, width=width, height=height,
                        resampling=Resampling.nearest, nodata=np.nan)
        n_burn = n_low = n_nan = 0
        n_win = n_win_hit = 0
        tmp.unlink(missing_ok=True)
        with rasterio.open(tmp, "w", **profile) as dst:
            B = args.block
            for row in range(0, height, B):
                for col in range(0, width, B):
                    n_win += 1
                    w = Window(col, row, min(B, width - col), min(B, height - row))
                    wt = rasterio.windows.transform(w, transform)
                    wb = rasterio.windows.bounds(w, transform)
                    hits = sidx.query(box(*wb), predicate="intersects")
                    if hits.size == 0:
                        continue
                    mask = features.rasterize(
                        ((geom, 1) for geom in bld.geometry.values[hits]),
                        out_shape=(int(w.height), int(w.width)), transform=wt,
                        fill=0, all_touched=False, dtype="uint8",
                    ).astype(bool)
                    if not mask.any():
                        continue
                    n_win_hit += 1
                    ground = vrt.read(1, window=w)
                    ok = mask & np.isfinite(ground)
                    n_nan += int((mask & ~np.isfinite(ground)).sum())
                    low = ok & (ground < args.min_ground)
                    n_low += int(low.sum())
                    ok &= ~low
                    n_burn += int(ok.sum())
                    arr = np.full(mask.shape, NODATA, dtype="float32")
                    arr[ok] = ground[ok] + args.height
                    dst.write(arr, 1, window=w)
                if (row // B) % 5 == 0:
                    print(f"  row {row}/{height}  windows {n_win} ({n_win_hit} with buildings)  "
                          f"burned px {n_burn}  {time.time() - t0:.0f}s", flush=True)
        vrt.close()

    print("building overviews (nearest) ...", flush=True)
    subprocess.run(
        ["gdaladdo", "-r", "nearest", "--config", "COMPRESS_OVERVIEW", "DEFLATE",
         "--config", "SPARSE_OK_OVERVIEW", "YES", str(tmp), "2", "4", "8", "16", "32"],
        check=True,
    )
    tmp.replace(out)

    prov = {
        "date": str(date.today()),
        "domain": dom.name,
        "template": str(template),
        "template_fingerprint": str(premier.domain_fingerprint(template)),
        "ground": str(ground_src),
        "footprints": args.footprints,
        "n_footprints": int(len(bld)),
        "height_cap_m": args.height,
        "min_ground_navd88_m": args.min_ground,
        "pixel_m": PIX,
        "grid": {"width": width, "height": height, "x0": float(x0), "y1": float(y1)},
        "burned_pixels": n_burn,
        "burned_area_km2": n_burn * PIX * PIX / 1e6,
        "skipped_low_ground_pixels": n_low,
        "skipped_low_ground_km2": n_low * PIX * PIX / 1e6,
        "skipped_nan_ground_pixels": n_nan,
        "nodata": NODATA,
        "overviews": "nearest 2..32 (pure subsample; no dilation at 50/100/200 m)",
        "seconds": round(time.time() - t0),
    }
    out.with_suffix(".json").write_text(json.dumps(prov, indent=2))
    print(json.dumps(prov, indent=2))
    print(f"wrote {out}  ({out.stat().st_size / 1e6:.0f} MB) in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
