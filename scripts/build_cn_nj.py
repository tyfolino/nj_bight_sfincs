"""
Build an NRCS Curve Number (CN) raster for the NJ model domain from SSURGO
hydrologic soil groups x NLCD 2012 land cover, for SFINCS CN infiltration.

CN = f(land cover, hydrologic soil group). We use the curve-number lookup
shipped with hydromt_sfincs (`DATADIR/lulc/NLCD_HSG.csv`), whose columns are
HSG *integer codes* and rows are NLCD classes. Decoded from its CN values
(which must rise A<B<C<D): column 1=A, 6=B, 5=C, and 3/2/7/8 are all the
D-equivalent value (the table lumps group D and the dual A/D,B/D,C/D,D/D groups
together at the undrained/worst-case D curve number). Column 4 is nodata.

Soil groups come from USDA SSURGO via the public Soil Data Access (SDA) REST
API (no auth) — dominant-component `hydgrp` per map-unit polygon, clipped to the
domain bbox. HYSOGs250m would be an alternative but is Earthdata-gated.

Output: data/infiltration/cn_nj.nc  (RasterDataset, var `cn`, on the NLCD grid)
Then:   sf.infiltration.create_cn(cn="cn_nj", antecedent_moisture=None)
"""
import os
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
import xarray as xr
from rasterio.features import rasterize
from shapely import wkt as shapely_wkt
from shapely.geometry import box

from hydromt_sfincs import DATADIR

ROOT = Path(os.environ.get("NJ_ROOT", Path(__file__).resolve().parents[1]))
# Region comes from the ACTIVE DOMAIN registry, so this script follows the
# domain being built instead of a fixed filename. (nj_sfincs/domain.py)
from nj_sfincs import domain as _domain  # noqa: E402
_DOM = _domain.active()
REGION = _DOM.region
NLCD = ROOT / "data/roughness/nlcd_2012.tif"
# 🔴 Per-domain output, same guard family as download_sandy_hwms.py: the archived
# `data/infiltration/cn_nj.nc` (read-only symlink) stops at lat 39.556 and is what
# the frozen domains were built with. A new domain gets its own dir + catalog key.
# Ported from the archive 2026-08-20 — the catalog named this script but the port
# had left it behind.
if _DOM.frozen or _DOM.name in ("v1_monmouth", "v1_5_raritan"):
    raise SystemExit(
        f"refusing to build a CN raster for frozen/built domain {_DOM.name!r}: its "
        "tier is the archived data/infiltration/cn_nj.nc. Run under the NEW domain "
        "being assembled (e.g. NJ_DOMAIN=v3)."
    )
OUT_DIR = ROOT / f"data/infiltration_{_DOM.name}"
OUT = OUT_DIR / f"cn_{_DOM.name}.nc"

SDA = "https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest"
# HSG letter -> integer code expected by NLCD_HSG.csv (see module docstring).
# D and all dual groups collapse to code 3 (identical CN in the table).
HSG_CODE = {"A": 1, "B": 6, "C": 5, "D": 3,
            "A/D": 2, "B/D": 7, "C/D": 8, "D/D": 3}
DEFAULT_HSG_CODE = 3  # land with no SSURGO HSG -> treat as D (conservative)


def fetch_hsg_polygons(bbox, tile_deg=0.25):
    """SSURGO map units intersecting bbox, fetched in tiles.

    SDA answers a single v1-sized box but returns HTTP 413 on the v3 bbox (1.4 x 1.8
    deg, 2026-08-24). Tiles of `tile_deg` are each well under the limit; a polygon that
    straddles two tiles comes back twice and is deduplicated on (mukey, wkt).
    """
    import itertools

    w, s, e, n = bbox
    xs = list(np.arange(w, e, tile_deg)) + [e]
    ys = list(np.arange(s, n, tile_deg)) + [n]
    seen, parts = set(), []
    for (x0, x1), (y0, y1) in itertools.product(zip(xs[:-1], xs[1:]), zip(ys[:-1], ys[1:])):
        g = _fetch_hsg_tile((x0, y0, x1, y1))
        for mukey, hsg, wkt in g:
            if (mukey, wkt) in seen:
                continue
            seen.add((mukey, wkt))
            parts.append((mukey, hsg, wkt))
    print(f"  SSURGO: {len(parts)} unique map-unit polygons from "
          f"{(len(xs)-1)*(len(ys)-1)} tiles")
    geoms = [shapely_wkt.loads(wk) for _m, _h, wk in parts]
    codes = [HSG_CODE.get(h, DEFAULT_HSG_CODE) for _m, h, _w in parts]
    return gpd.GeoDataFrame({"hsg_code": codes}, geometry=geoms, crs="EPSG:4326")


def _fetch_hsg_tile(bbox):
    w, s, e, n = bbox
    poly = f"POLYGON(({w} {s}, {e} {s}, {e} {n}, {w} {n}, {w} {s}))"
    sql = (
        "SELECT mu.mukey, "
        "(SELECT TOP 1 hydgrp FROM component c WHERE c.mukey=mu.mukey "
        " AND hydgrp IS NOT NULL ORDER BY comppct_r DESC) AS hsg, "
        "g.mupolygongeo.STAsText() AS wkt "
        "FROM mupolygon g JOIN mapunit mu ON g.mukey=mu.mukey "
        f"WHERE g.mupolygongeo.STIntersects(geometry::STGeomFromText('{poly}',4326))=1"
    )
    r = requests.post(SDA, json={"format": "JSON", "query": sql}, timeout=300)
    r.raise_for_status()
    rows = r.json().get("Table", [])
    return [(mukey, hsg, wk) for mukey, hsg, wk in rows if wk is not None]


def main():
    import rioxarray  # noqa: F401

    bbox = tuple(gpd.read_file(REGION).to_crs(4326).total_bounds)
    print(f"domain bbox: {tuple(round(b, 3) for b in bbox)}")

    # NLCD on its native grid, clipped to the domain (+ small buffer)
    nlcd = (
        __import__("rioxarray").open_rasterio(NLCD, masked=False).squeeze("band", drop=True)
    )
    bx = gpd.GeoDataFrame(geometry=[box(*bbox)], crs=4326).to_crs(nlcd.rio.crs)
    nlcd = nlcd.rio.clip_box(*bx.total_bounds)
    print(f"NLCD grid: {nlcd.shape}, crs {nlcd.rio.crs}, res {nlcd.rio.resolution()}")

    # SSURGO HSG polygons -> rasterize onto the NLCD grid
    gdf = fetch_hsg_polygons(bbox).to_crs(nlcd.rio.crs)
    print(f"SSURGO polygons: {len(gdf)}  HSG-code counts: "
          f"{gdf['hsg_code'].value_counts().sort_index().to_dict()}")
    transform = nlcd.rio.transform()
    hsg = rasterize(
        ((g, c) for g, c in zip(gdf.geometry, gdf["hsg_code"])),
        out_shape=nlcd.shape, transform=transform, fill=DEFAULT_HSG_CODE,
        dtype="int16",
    )

    # CN lookup table (NLCD class x HSG integer code)
    tbl = pd.read_csv(os.path.join(DATADIR, "lulc", "NLCD_HSG.csv"), index_col=0)
    tbl.columns = [int(c) for c in tbl.columns]
    nlcd_v = nlcd.values
    cn = np.full(nlcd_v.shape, np.nan, dtype="float32")
    for cls in np.unique(nlcd_v):
        if cls not in tbl.index:
            continue
        cls_mask = nlcd_v == cls
        for code in np.unique(hsg[cls_mask]):
            if code not in tbl.columns:
                continue
            val = tbl.loc[cls, code]
            if val == -9999:
                continue
            cn[cls_mask & (hsg == code)] = val

    # NaN cells are NLCD nodata (250) = open ocean beyond the land grid. SFINCS
    # needs a value on every active cell, so fill with 0 — the table's water CN.
    # (SCS infiltration only consumes rainfall, so this never touches the surge.)
    n_ocean = int((~np.isfinite(cn)).sum())
    cn = np.where(np.isfinite(cn), cn, 0.0).astype("float32")

    da = xr.DataArray(cn, coords=nlcd.coords, dims=nlcd.dims, name="cn")
    da = da.rio.write_crs(nlcd.rio.crs).rio.write_nodata(-9999.0)
    land = cn > 0
    print(f"CN: land cells {int(land.sum())}, ocean/water filled 0 ({n_ocean})  "
          f"land CN range {cn[land].min():.0f}-{cn[land].max():.0f}  "
          f"land mean {cn[land].mean():.1f}")

    # NLCD's CRS is a non-standard Albers/WGS84 (no EPSG) — reproject to EPSG:4326
    # so the data catalog + create_cn get a clean, unambiguous CRS.
    da = da.rio.reproject("EPSG:4326")
    da = da.where(da != -9999.0)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(OUT.suffix + ".tmp")
    da.to_dataset().to_netcdf(tmp)
    os.replace(tmp, OUT)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()