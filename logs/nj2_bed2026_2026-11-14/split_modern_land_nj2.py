"""Split modern_land_2026 into a PAINT layer and a LOWER-ONLY layer (modern bed round b, 2026-11-06).

    python -I logs/modern_bed_b_2026-11-06/split_modern_land.py --workers 16

Implements the 11-04 sweep fixes 2 and 6 (logs/modern_sweeps_2026-11-04/README.md "Fixes for the
modern recipe") plus a bridge rule for S12 (user picker 11-06), on modern_land's own 3 m lattice:

  W      "water in either epoch": water_mask_v4 == 1 (NHD river / canal / lake polygons) OR the 2012
         bed (v1.1c merged, read through GDAL warp: the subgrid raster is ROTATED) below MHHW.
  LAKE   lake_pool_v4 is finite (a non-tidal pool): EXEMPT, the lidar pool surface stays (user 11-05,
         E3 / E4: the 2026 pools are right; alloway / silver pool overlays repaint after anyway).
  rule 2 (water surfaces lower, never raise): W & ~LAKE & modern < MHHW + 0.5 (tidal), or W & ~LAKE
         on mapped water with no MHHW (non-tidal river): -> LOWER-ONLY layer (overlay_min: the build
         takes min(2012 stack, modern) there).
  rule B (decks over water, S12): within a bridge corridor (the modern deck sweep's stations of
         every OSM bridge way, embankment / culvert ways excluded; radius by way class) AND the 2012
         bed below MHHW AND ~LAKE -> LOWER-ONLY, whatever the modern value (a deck in the lidar over
         2012 water; a real new pier is a negligible blockage, user 11-06 discussion).
  rule 6 (dry-dock cap): not W, modern < -3 m, 2012 bed >= -0.25 m -> DROPPED (the 2012 stack shows).
  else   -> PAINT layer (overlay, as modern_land was).

Outputs (EPSG:32618, modern_land's grid, nodata -9999, deflate, 512 tiles) in
/scratch/tpj8/nj_bight_sfincs_data/elevation_modern_2026/b/:
  modern_land_paint_2026b.tif, modern_land_lower_2026b.tif, modern_land_rule_2026b.tif (uint8:
  1 paint, 2 rule 2, 3 rule B, 4 rule 6 drop, 0 no modern data) + split_summary.json here.
"""

# nj2 COPY (2026-11-14) of logs/modern_bed_b_2026-11-06/split_modern_land.py: identical rules; only the paths come from the environment so the
# process-pool workers (forkserver on Python 3.14 re-imports this module) see them. Unset = round b's values.
#   NJ2_HERE (summary dir), NJ2_MLAND (modern_land tif), NJ2_B12 (the 2012 merged bed), NJ2_OUT, NJ2_SUFFIX (file suffix)

from __future__ import annotations

import argparse
import json
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

os.environ.setdefault("PROJ_DATA", "/home/tpj8/nj_sandy_sfincs/micromamba/envs/sfincs/share/proj")
import pyproj  # noqa: E402,F401
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import rasterio  # noqa: E402
from rasterio.features import rasterize  # noqa: E402
from rasterio.warp import Resampling, reproject  # noqa: E402
from rasterio.windows import Window  # noqa: E402
from rasterio.windows import transform as wtransform  # noqa: E402
from shapely.geometry import Point  # noqa: E402
from shapely.strtree import STRtree  # noqa: E402

REPO = Path("/cache/home/tpj8/nj_bight_sfincs")
HERE = Path(os.environ.get("NJ2_HERE", REPO / "logs/modern_bed_b_2026-11-06"))
MLAND = Path(os.environ.get("NJ2_MLAND", REPO / "data/elevation_modern_2026/modern_land_2026.tif"))
B12 = Path(os.environ.get("NJ2_B12", REPO / "experiments/v4_refreeze_swz/_subgrid_v1_1c/subgrid/dep_subgrid_merged.tif"))
NS = REPO / "data/normal_surface_v4"
DECKS = REPO / "logs/modern_decks_2026-11-04/out/modern"
OUT = Path(os.environ.get("NJ2_OUT", "/scratch/tpj8/nj_bight_sfincs_data/elevation_modern_2026/b"))
SFX = os.environ.get("NJ2_SUFFIX", "_2026b")
ND = -9999.0
BLK = 512


def radius(kind: str) -> float:
    k = str(kind)
    if any(s in k for s in ("motorway", "trunk", "rail:")):
        return 15.0
    if any(s in k for s in ("primary", "secondary", "tertiary", "motorway_link", "subway")):
        return 10.0
    return 6.0


def corridors():
    w = pd.read_csv(DECKS / "sweep_ways.csv", low_memory=False, dtype={"bridge": str, "embankment": str})
    keep = (w.embankment.fillna("") != "yes") & (w.bridge.fillna("") != "culvert")
    w = w[keep]
    s = pd.read_parquet(DECKS / "sweep_stations.parquet", columns=["way", "x", "y"])
    s = s.merge(w[["way", "kind"]], on="way")
    geoms = [Point(x, y).buffer(radius(k), 8) for x, y, k in zip(s.x, s.y, s.kind)]
    return geoms


G = None
T = None


def init():
    global G, T
    G = corridors()
    T = STRtree(G)


def work(job):
    r0, c0, h, w = job
    win = Window(c0, r0, w, h)
    with rasterio.open(MLAND) as src:
        m = src.read(1, window=win)
        tr = wtransform(win, src.transform)
        crs = src.crs
    valid = m != ND
    cls = np.zeros((h, w), "uint8")
    paint = np.full((h, w), ND, "float32")
    lower = np.full((h, w), ND, "float32")
    if not valid.any():
        return r0, c0, cls, paint, lower
    b12 = np.full((h, w), np.nan, "float32")
    with rasterio.open(B12) as s12:
        reproject(rasterio.band(s12, 1), b12, dst_transform=tr, dst_crs=crs, resampling=Resampling.nearest,
                  src_nodata=s12.nodata, dst_nodata=np.nan)
    mh = np.full((h, w), np.nan, "float32")
    wm = np.zeros((h, w), "uint8")
    lp = np.full((h, w), np.nan, "float32")
    for f, arr, rs, nd in ((NS / "mhhw_navd88_v4.tif", mh, Resampling.bilinear, np.nan),
                           (NS / "water_mask_v4.tif", wm, Resampling.nearest, 0),
                           (NS / "lake_pool_v4.tif", lp, Resampling.nearest, np.nan)):
        with rasterio.open(f) as s:
            reproject(rasterio.band(s, 1), arr, dst_transform=tr, dst_crs=crs, resampling=rs,
                      src_nodata=s.nodata if s.nodata is not None else nd, dst_nodata=nd)
    l, b = tr * (0, h)
    rr, t = tr * (w, 0)
    from shapely.geometry import box
    idx = T.query(box(l, b, rr, t))
    bridge = np.zeros((h, w), bool)
    if len(idx):
        bridge = rasterize([(G[i], 1) for i in idx], out_shape=(h, w), transform=tr, fill=0,
                           dtype="uint8").astype(bool)
    lake = np.isfinite(lp)
    w12 = np.isfinite(b12) & np.isfinite(mh) & (b12 < mh)
    W = (wm == 1) | w12
    with np.errstate(invalid="ignore"):
        tidal = np.isfinite(mh) & (m < mh + 0.5)
        r2 = valid & W & ~lake & (tidal | (~np.isfinite(mh) & (wm == 1)))
        rb = valid & bridge & w12 & ~lake & ~r2
        r6 = valid & ~W & ~r2 & ~rb & (m < -3.0) & np.isfinite(b12) & (b12 >= -0.25)
    dry = valid & ~r2 & ~rb & ~r6
    cls[dry], cls[r2], cls[rb], cls[r6] = 1, 2, 3, 4
    paint[dry] = m[dry]
    lw = r2 | rb
    lower[lw] = m[lw]
    return r0, c0, cls, paint, lower


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=16)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    with rasterio.open(MLAND) as src:
        prof = src.profile.copy()
        H, W_ = src.height, src.width
    prof.update(compress="deflate", tiled=True, blockxsize=BLK, blockysize=BLK, nodata=ND, dtype="float32",
                BIGTIFF="YES", predictor=3)
    pc = dict(prof, dtype="uint8", nodata=0, predictor=2)
    names = {"paint": OUT / f"modern_land_paint{SFX}.tif", "lower": OUT / f"modern_land_lower{SFX}.tif",
             "cls": OUT / f"modern_land_rule{SFX}.tif"}
    tmp = {k: v.with_suffix(".tmp.tif") for k, v in names.items()}
    jobs = [(r, c, min(BLK, H - r), min(BLK, W_ - c)) for r in range(0, H, BLK) for c in range(0, W_, BLK)]
    px = np.zeros(5, "int64")
    with rasterio.open(tmp["paint"], "w", **prof) as dp, rasterio.open(tmp["lower"], "w", **prof) as dl, \
            rasterio.open(tmp["cls"], "w", **pc) as dc, ProcessPoolExecutor(a.workers, initializer=init) as ex:
        for i, (r0, c0, cls, paint, lower) in enumerate(ex.map(work, jobs, chunksize=8)):
            win = Window(c0, r0, cls.shape[1], cls.shape[0])
            dc.write(cls, 1, window=win)
            dp.write(paint, 1, window=win)
            dl.write(lower, 1, window=win)
            px += np.bincount(cls.ravel(), minlength=5)
            if i % 2000 == 0:
                print(f"  {i}/{len(jobs)}", flush=True)
    for k in names:
        os.replace(tmp[k], names[k])
    km2 = {lab: float(px[k] * 9 / 1e6) for k, lab in enumerate(
        ["no_modern", "paint", "rule2_water_lower", "ruleB_bridge_lower", "rule6_dock_dropped"])}
    (HERE / f"split_summary{SFX}.json").write_text(json.dumps(km2, indent=1))
    print("km2:", json.dumps(km2))


if __name__ == "__main__":
    main()
