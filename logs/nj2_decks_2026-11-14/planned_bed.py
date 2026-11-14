"""The 2012 bed J2 step 6 will build in the nj2 NEW AREA (nj2 ring minus v4_hot_plus's), as a
north-up 2.5 m UTM18N grid, for the deck / dam sweep (2026-11-14). Read-only on every input.

  base   = v1.1c's merged scoring bed (experiments/v4_refreeze_swz/_subgrid_v1_1c/subgrid/
           dep_subgrid_merged.tif). The subgrid DEM covers the whole grid RECTANGLE (CLAUDE.md §5), and
           nj2's step-6 recipe = v1.1c's base list + v1.1c's overlays + 2.0's tiers, so in the new area
           it is exactly what the nj2 build starts from (on a different lattice). ROTATED raster: sampled
           through the inverse affine on a plain window read (no boundless read).
  paint  ehydro_hud_2012_v2 (PAINT)
  :min   carve_v2_2012, gowanus_upper_v2 (2012), piers_v2_2012          (the v1.2a five are NJ-only)

Writes $OUT/planned_2012.tif (+ base_v11c.tif = before 2.0's tiers, + area_mask.tif). Nearest everywhere.

After J2 builds the bed, re-check it directly (no overlays replayed):
  python planned_bed.py --built experiments/nj2/_subgrid_nj2_2012/subgrid/dep_subgrid_merged.tif
  -> $OUT/built_2012.tif ; then  python connect.py built_2012
"""
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.transform import from_origin
from rasterio.windows import Window
from shapely import contains_xy

REPO = Path("/cache/home/tpj8/nj_bight_sfincs")
OUT = Path("/scratch/tpj8/tmp/nj2_decks_2026-11-14")
OUT.mkdir(parents=True, exist_ok=True)
RES = 2.5
BUF = 300.0


def new_area():
    a = gpd.read_file(REPO / "data/region_nj2.geojson").to_crs(32618).geometry.iloc[0]
    b = gpd.read_file(REPO / "data/region_v4_hot_plus.geojson").to_crs(32618).geometry.iloc[0]
    return a, b, a.difference(b)


def grid():
    a, b, n = new_area()
    x0, y0, x1, y1 = n.buffer(BUF).bounds
    x0, y0 = np.floor(x0 / 5) * 5, np.floor(y0 / 5) * 5
    x1, y1 = np.ceil(x1 / 5) * 5, np.ceil(y1 / 5) * 5
    W, H = int(round((x1 - x0) / RES)), int(round((y1 - y0) / RES))
    return from_origin(x0, y1, RES, RES), W, H, a, b, n


def main():
    built = sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == "--built" else None
    T, W, H, a, b, n = grid()
    print("grid", W, H, T)
    src = rasterio.open(REPO / (built or "experiments/v4_refreeze_swz/_subgrid_v1_1c/subgrid/dep_subgrid_merged.tif"))
    inv = ~src.transform
    # pixel window of the bbox corners
    xs = [T.c, T.c + W * RES]
    ys = [T.f - H * RES, T.f]
    cc, rr = [], []
    for x in xs:
        for y in ys:
            c, r = inv * (x, y)
            cc.append(c)
            rr.append(r)
    c0, c1 = int(np.floor(min(cc))) - 2, int(np.ceil(max(cc))) + 2
    r0, r1 = int(np.floor(min(rr))) - 2, int(np.ceil(max(rr))) + 2
    c0, r0 = max(c0, 0), max(r0, 0)
    c1, r1 = min(c1, src.width), min(r1, src.height)
    A = src.read(1, window=Window(c0, r0, c1 - c0, r1 - r0))
    print("base window", A.shape)
    base = np.full((H, W), np.nan, np.float32)
    xc = T.c + (np.arange(W) + 0.5) * RES
    for i in range(0, H, 500):
        yc = T.f - (np.arange(i, min(i + 500, H)) + 0.5) * RES
        X, Y = np.meshgrid(xc, yc)
        c, r = inv * (X.ravel(), Y.ravel())
        c = np.floor(c).astype(np.int64) - c0
        r = np.floor(r).astype(np.int64) - r0
        ok = (c >= 0) & (c < A.shape[1]) & (r >= 0) & (r < A.shape[0])
        v = np.full(c.shape, np.nan, np.float32)
        v[ok] = A[r[ok], c[ok]]
        base[i:i + len(yc)] = v.reshape(len(yc), W)
    del A
    prof = dict(driver="GTiff", width=W, height=H, count=1, dtype="float32", crs=32618, transform=T,
                nodata=np.nan, compress="deflate", tiled=True, predictor=3)
    with rasterio.open(OUT / ("built_2012.tif" if built else "base_v11c.tif"), "w", **prof) as d:
        d.write(base, 1)
    if built:
        return
    bed = base.copy()

    def onto(path):
        with rasterio.open(path) as s:
            assert s.crs.to_epsg() == 32618 and s.transform.b == 0 and s.transform.d == 0
            v = np.full((H, W), np.nan, np.float32)
            # nearest: grid centre -> source pixel
            cs = np.floor((xc - s.transform.c) / s.transform.a).astype(int)
            for i in range(0, H, 2000):
                yc = T.f - (np.arange(i, min(i + 2000, H)) + 0.5) * RES
                rs = np.floor((yc - s.transform.f) / s.transform.e).astype(int)
                okc = (cs >= 0) & (cs < s.width)
                okr = (rs >= 0) & (rs < s.height)
                if not okc.any() or not okr.any():
                    continue
                cmin, cmax = cs[okc].min(), cs[okc].max()
                rmin, rmax = rs[okr].min(), rs[okr].max()
                a = s.read(1, window=Window(cmin, rmin, cmax - cmin + 1, rmax - rmin + 1)).astype(np.float32)
                if s.nodata is not None and not np.isnan(s.nodata):
                    a[a == s.nodata] = np.nan
                a[(a < -1e4) | (a > 1e4)] = np.nan
                blk = np.full((len(yc), W), np.nan, np.float32)
                ri = np.where(okr)[0]
                ci = np.where(okc)[0]
                blk[np.ix_(ri, ci)] = a[np.ix_(rs[okr] - rmin, cs[okc] - cmin)]
                v[i:i + len(yc)] = blk
            return v

    C = REPO / "data/elevation_nj2/v2"
    hud = onto(C / "ehydro_hud_2012/hd_hud_2012_5m.tif")
    m = ~np.isnan(hud)
    bed[m] = hud[m]
    print("hud painted px", int(m.sum()))
    tag = np.zeros((H, W), np.uint8)  # 1 hud, 2 carve, 3 gowanus_upper, 4 piers (which tier set the value last)
    tag[m] = 1
    for k, f in ((2, "carves/carve_v2_2012.tif"), (3, "carves/gowanus_upper_v2_2012.tif"), (4, "carves/piers_v2_2012.tif")):
        v = onto(C / f)
        m = ~np.isnan(v) & ((v < bed) | np.isnan(bed))
        bed[m] = v[m]
        tag[m] = k
        print(f, "lowered px", int(m.sum()))
    with rasterio.open(OUT / "planned_2012.tif", "w", **prof) as d:
        d.write(bed, 1)
    p2 = dict(prof, dtype="uint8", nodata=None, predictor=1)
    with rasterio.open(OUT / "planned_2012_tag.tif", "w", **p2) as d:
        d.write(tag, 1)
    # masks: 1 = new area, 2 = old (v4) area inside nj2, 0 outside nj2
    msk = np.zeros((H, W), np.uint8)
    for i in range(0, H, 1000):
        yc = T.f - (np.arange(i, min(i + 1000, H)) + 0.5) * RES
        X, Y = np.meshgrid(xc, yc)
        ina = contains_xy(a, X, Y)
        inb = contains_xy(b, X, Y)
        msk[i:i + len(yc)] = np.where(ina & ~inb, 1, np.where(ina & inb, 2, 0))
    with rasterio.open(OUT / "area_mask.tif", "w", **p2) as d:
        d.write(msk, 1)
    print("done", OUT)


if __name__ == "__main__":
    sys.exit(main())
