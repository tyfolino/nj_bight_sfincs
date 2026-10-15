#!/usr/bin/env python
"""Build the coastal-lake bed fix: a LOWER-ONLY overlay for ``rebuild_subgrid.py --overlay``.

Found 2026-10-15 (logs/lake_audit_2026-10-15/, STATUS): inside 15 Monmouth / north Ocean
coastal-lake outlines the merged v4 bed sits > 1 m above the NJ 10 ft lidar, and in every
one the raised bed is the USACE 2010 tier (``usace_nj_2010_v3``) — interpolated across the
water from the banks (Wesley Lake 2.2 m on a 0.61 m flattened surface), plus outlet
crossings and a filled lagoon canal. The user's per-lake calls are in ``--decisions``
(``fix`` / ``keep``).

For every ``fix`` lake, inside its NHD outline, on a 3 m UTM grid:
    value = 10 ft lidar   where lidar < merged premier bed   (bed = min(bed, lidar))
    NoData                everywhere else (the overlay leaves those pixels alone)
so the lake goes back to its lidar water surface (zero depth — the 09-29 inland-lake rule)
and nothing is ever raised. Lakes are matched to NHD polygons by the scan's centroid.

    python scripts/build_lake_fix_overlay.py \
        --decisions logs/lake_audit_2026-10-15/decisions_2026-10-15.csv \
        --out data/elevation_v4/lake_fix/lake_fix_v4.tif
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT
from rasterio.warp import Resampling

ROOT = Path(__file__).resolve().parents[1]
DEF_MERGED = (
    ROOT / "experiments/v4_refreeze/_subgrid_refreeze/subgrid/dep_subgrid_merged.tif"
)
DEF_LIDAR = ROOT / "data/elevation_v4/nj_10ft_dem_v4.tif"
DEF_NHD = ROOT / "data/elevation_v4/inland_water/nhd_lake_v4.gpkg"
EPSG = 32618
RES = 3.0


def warp(path, tr, w, h):
    with (
        rasterio.open(path) as src,
        WarpedVRT(
            src,
            crs=f"EPSG:{EPSG}",
            transform=tr,
            width=w,
            height=h,
            resampling=Resampling.nearest,
            nodata=np.nan,
            src_nodata=src.nodata,
        ) as v,
    ):
        a = v.read(1, masked=True).filled(np.nan).astype("float32")
    a[(a < -50) | (a > 300)] = np.nan
    return a


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--decisions", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--merged", type=Path, default=DEF_MERGED)
    ap.add_argument("--lidar", type=Path, default=DEF_LIDAR)
    ap.add_argument("--nhd", type=Path, default=DEF_NHD)
    a = ap.parse_args(argv)

    dec = pd.read_csv(a.decisions)
    fix = dec[dec.decision.str.strip() == "fix"]
    nhd = gpd.read_file(a.nhd).to_crs(4326)
    cen = np.c_[
        [g.centroid.x for g in nhd.geometry], [g.centroid.y for g in nhd.geometry]
    ]
    polys, report = [], []
    for r in fix.itertuples():
        d = np.hypot(cen[:, 0] - r.lon, cen[:, 1] - r.lat)
        i = int(np.argmin(d))
        if d[i] > 1e-4:  # ~10 m: the scan's lon/lat IS the NHD centroid
            raise SystemExit(
                f"{r.key} {r.name}: no NHD centroid within 10 m ({d[i]:.5f}°)"
            )
        polys.append((r.key, r.name, nhd.geometry.iloc[i]))
    gs = gpd.GeoSeries([p for _, _, p in polys], crs=4326).to_crs(EPSG)

    x0, y0, x1, y1 = gs.total_bounds
    x0, y0 = np.floor(x0 / RES) * RES - 30, np.floor(y0 / RES) * RES - 30
    x1, y1 = np.ceil(x1 / RES) * RES + 30, np.ceil(y1 / RES) * RES + 30
    w, h = int(round((x1 - x0) / RES)), int(round((y1 - y0) / RES))
    tr = from_origin(x0, y1, RES, RES)
    bed, lid = warp(a.merged, tr, w, h), warp(a.lidar, tr, w, h)
    out = np.full((h, w), np.nan, dtype="float32")
    for (key, name, _), g in zip(polys, gs):
        ins = ~geometry_mask([g], out_shape=(h, w), transform=tr)
        low = ins & np.isfinite(lid) & np.isfinite(bed) & (lid < bed)
        out[low] = lid[low]
        dz = (bed - lid)[low]
        report.append(
            dict(
                key=key,
                name=name,
                outline_m2=float(ins.sum() * RES**2),
                lowered_m2=float(low.sum() * RES**2),
                lowered_gt1m_m2=float((dz > 1).sum() * RES**2),
                drop_p50=round(float(np.median(dz)), 3) if dz.size else 0.0,
                drop_max=round(float(dz.max()), 3) if dz.size else 0.0,
                volume_removed_m3=round(float(dz.sum() * RES**2)),
            )
        )
    a.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = a.out.with_suffix(".tmp.tif")
    with rasterio.open(
        tmp,
        "w",
        driver="GTiff",
        width=w,
        height=h,
        count=1,
        dtype="float32",
        crs=f"EPSG:{EPSG}",
        transform=tr,
        nodata=-9999.0,
        compress="deflate",
    ) as dst:
        dst.write(np.where(np.isfinite(out), out, -9999.0).astype("float32"), 1)
    os.replace(tmp, a.out)
    rep = pd.DataFrame(report)
    print(rep.to_string(index=False))
    meta = dict(
        decisions=str(a.decisions),
        merged=str(a.merged),
        lidar=str(a.lidar),
        rule="inside each fix lake's NHD outline: lidar where lidar < merged bed",
        lakes=report,
    )
    a.out.with_suffix(".json").write_text(json.dumps(meta, indent=1) + "\n")
    print(f"wrote {a.out} ({w} x {h} at {RES:.0f} m)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
