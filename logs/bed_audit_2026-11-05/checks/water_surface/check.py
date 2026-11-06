"""Bed audit check `water_surface`: where does the bed hold a WATER SURFACE instead of the bottom?

Two signatures, one method (logs/bed_audit_2026-11-05/SCHEMA.md; README.md here):

  1. lidar hydro-flattening: the bare-earth DEM is flattened to the water level on the day of the flight
     (lakes, rivers, bays, and the shadow under bridge decks); CONFIRMED where a 3DEP breakline polygon covers the
     patch and the patch level matches the polygon's Z (USGS Lidar Base Specification deliverable, downloaded by
     fetch_breaklines.py);
  2. CUDEM's flat ~0 m fill under lakes and rivers (FINDINGS §54), and any other exactly-flat patch in water.

A pixel is FLAT when the bed's range over a 5 x 5 window of 3 m samples (15 m) is <= FLAT_TOL (5 mm): measured
beds (surveys, lidar ground, GMRT) are never that flat over 15 m; flattened water and constant fills are. Flat
pixels that are WET (NHD water, a breakline water polygon, or below local MHHW + 0.3 m) and connected over
>= MIN_AREA are one patch. Each patch is then classed by what the water is (NOAA VDatum MHHW defined = tidal;
data/normal_surface_v4 lake_pool = an impounded / non-tidal lake held at its pool, which is INTENDED and not
flagged) and by its hydraulic signature (the ring of bed around it: deeper water on two separate sides = a SILL).

Usage (SCHEMA CLI):
  python check.py --bed experiments/v4_refreeze_swz/_subgrid_v1_1 --label v1_1b \
      --overlay-min deck_fix_v4b --out ../../out/v1_1b/water_surface.csv [--workers 16]
  python check.py --bed modern --label modern --out ../../out/modern/water_surface.csv
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")
REPO = Path("/cache/home/tpj8/nj_bight_sfincs")
sys.path.insert(0, str(REPO / "logs/decks_2026-11-04"))
sys.path.insert(0, str(REPO / "logs/modern_decks_2026-11-04"))

BL_DIR = Path("/scratch/tpj8/nj_bight_sfincs_data/audit/water_surface/breaklines")
CACHE = Path("/scratch/tpj8/nj_bight_sfincs_data/audit/water_surface/cache")
NS = REPO / "data/normal_surface_v4"
REGION = REPO / "data/region_v4_hot_plus.geojson"
MAP = REPO / "experiments/v4_refreeze_swz/p4-premier/sfincs_map.nc"
ASSETS = [REPO / "data/power_infra/plant_polygons.geojson", REPO / "data/power_infra/substation_polygons.geojson"]

STEP = 3.0          # m, sampling lattice (the merged beds are ~1.56 m pixels)
TILE = 2400.0       # m, tile side (800 x 800 samples)
FLAT_TOL = 0.005    # m, max range over a 5 x 5 window for "flat"
MIN_AREA = 200.0    # m2, smallest patch reported
RING = 5            # samples (15 m) of ring around a patch to read its hydraulic signature
WET_ABOVE_MHHW = 0.3
BELOW_MHHW_MAX = 3.0  # m: a water surface in tidal water lies above MHHW - 3 m

WATER_LAYERS = ("water", "lake", "ocean", "river", "polygonz")  # breakline polygon layers holding a water surface


# ---------------------------------------------------------------- breaklines → one EPSG:32618 table (cached)
def _z_factor(crs_wkt: str, layer_crs_name: str) -> float:
    import pyproj

    c = pyproj.CRS(crs_wkt)
    if c.is_compound:
        v = [s for s in c.sub_crs_list if s.is_vertical][0]
        u = v.axis_info[0].unit_name
    else:
        u = c.axis_info[0].unit_name if c.axis_info else "metre"
    return 1200.0 / 3937.0 if "US survey foot" in u else (0.3048 if "foot" in u else 1.0)


def breaklines():
    """All breakline WATER polygons, EPSG:32618, with zmin / zmax in m NAVD88 (from the vertices' Z)."""
    out = CACHE / "breakline_water_32618.gpkg"
    import geopandas as gpd
    import pandas as pd
    import pyogrio

    if out.exists():
        return gpd.read_file(out)
    CACHE.mkdir(parents=True, exist_ok=True)
    srcs = sorted(set(glob.glob(str(BL_DIR / "*/*/*.gdb")) + glob.glob(str(BL_DIR / "*/*/*.gpkg"))
                      + glob.glob(str(BL_DIR / "NJ_New_Jersey_SANDY_LiDAR_15/*/PolygonZ.shp"))
                      + glob.glob(str(BL_DIR / "NY_SouthEast4County_A22/*/*.gdb"))))
    parts = []
    for s in srcs:
        for name, gt in pyogrio.list_layers(s):
            if gt is None or "Polygon" not in str(gt) or not any(k in name.lower() for k in WATER_LAYERS):
                continue
            if "other" in name.lower():
                continue
            info = pyogrio.read_info(s, layer=name)
            fz = _z_factor(info["crs"], name)
            g = gpd.read_file(s, layer=name)
            if g.empty:
                continue
            zmin, zmax = [], []
            for geom in g.geometry.values:
                try:
                    cs = np.concatenate([np.asarray(r.coords) for p in getattr(geom, "geoms", [geom])
                                         for r in [p.exterior]])
                    z = cs[:, 2] * fz if cs.shape[1] > 2 else np.array([np.nan])
                except Exception:  # noqa: BLE001
                    z = np.array([np.nan])
                zmin.append(np.nanmin(z))
                zmax.append(np.nanmax(z))
            g = g.set_geometry(g.geometry.force_2d()).to_crs(32618)
            proj = Path(s).relative_to(BL_DIR).parts[0]
            kind = ("lake" if any(k in name.lower() for k in ("lake", "waterbod", "pond")) else
                    "ocean" if "ocean" in name.lower() else "river" if "river" in name.lower() else "polygon")
            parts.append(gpd.GeoDataFrame(dict(project=proj, layer=name, kind=kind, zmin=zmin, zmax=zmax,
                                               zfactor=fz), geometry=g.geometry.values, crs=32618))
    bl = pd.concat(parts, ignore_index=True)
    bl = gpd.GeoDataFrame(bl, geometry="geometry", crs=32618)
    bl["bl_id"] = np.arange(len(bl))
    bl.to_file(out, driver="GPKG")
    return bl


# ---------------------------------------------------------------- beds
class NorthUp:
    """Window sampler for a north-up raster in EPSG:32618 (nearest pixel; NaN outside / nodata)."""

    def __init__(self, path):
        import rasterio

        self.src = rasterio.open(path)
        self.inv = ~self.src.transform
        self.nd = self.src.nodata

    def sample(self, x, y):
        from rasterio.windows import Window

        c, r = self.inv * (np.asarray(x, float), np.asarray(y, float))
        c, r = np.floor(c).astype(np.int64), np.floor(r).astype(np.int64)
        out = np.full(np.shape(x), np.nan, np.float32)
        ok = (c >= 0) & (c < self.src.width) & (r >= 0) & (r < self.src.height)
        if not ok.any():
            return out
        c0, c1, r0, r1 = c[ok].min(), c[ok].max() + 1, r[ok].min(), r[ok].max() + 1
        a = self.src.read(1, window=Window(c0, r0, c1 - c0, r1 - r0), boundless=False).astype(np.float32)
        v = a[r[ok] - r0, c[ok] - c0]
        if self.nd is not None:
            v[v == self.nd] = np.nan
        v[(v < -1e4) | (v > 1e4)] = np.nan
        out[ok] = v
        return out


class MinBed:
    def __init__(self, base, overlays):
        self.base, self.ov = base, overlays

    def sample(self, x, y):
        z = self.base.sample(x, y)
        for o in self.ov:
            v = o.sample(x, y)
            z = np.where(np.isfinite(v), np.fmin(z, v), z)
        return z.astype(np.float32)


def make_bed(bed: str, overlay_min: list[str]):
    from common import Bed  # logs/decks_2026-11-04/common.py (rotated-raster sampler)

    if bed == "modern":
        from common_m import BED_MOD, EffBed, Overlay

        return EffBed(BED_MOD, Overlay()), f"{BED_MOD} + deck_fix_v4 (v1.1 pixels) as min"
    p = Path(bed)
    p = p if p.is_absolute() else REPO / p
    tif = p / "subgrid" / "dep_subgrid_merged.tif"
    ovs = []
    for k in overlay_min:
        uri = {"deck_fix_v4b": REPO / "data/elevation_v4/deck_fix/deck_fix_v4b.vrt"}.get(k)
        if uri is None:
            raise SystemExit(f"unknown --overlay-min {k}")
        ovs.append(NorthUp(uri))
    return MinBed(Bed(tif), ovs), f"{tif}" + "".join(f" + {k} as min" for k in overlay_min)


# ---------------------------------------------------------------- context grids (25 m, north-up)
class Ctx:
    def __init__(self):
        self.mhhw = NorthUp(NS / "mhhw_navd88_v4.tif")
        self.msrc = NorthUp(NS / "mhhw_source_v4.tif")
        self.water = NorthUp(NS / "water_mask_v4.tif")
        self.pool = NorthUp(NS / "lake_pool_v4.tif")


def _patches(lab, n, tier, zz, X, Y, mh, tidal, pool, wet25, bl, min_area):
    from scipy import ndimage as ndi

    out = []
    sizes = ndi.sum(np.ones_like(lab), lab, index=np.arange(1, n + 1))
    for i, sl in enumerate(ndi.find_objects(lab), start=1):
        npx = int(sizes[i - 1])
        if npx * STEP * STEP < min_area:
            continue
        r0, r1 = max(sl[0].start - RING - 1, 0), min(sl[0].stop + RING + 1, lab.shape[0])
        c0, c1 = max(sl[1].start - RING - 1, 0), min(sl[1].stop + RING + 1, lab.shape[1])
        m = lab[r0:r1, c0:c1] == i
        zl = zz[r0:r1, c0:c1]
        vals = zl[m]
        level = float(np.nanmedian(vals))
        mode_share = float((np.abs(vals - level) <= 0.002).mean())
        sides, drop = 0, 0.0
        for it in (3, RING):
            ring = ndi.binary_dilation(m, iterations=it) & ~m & np.isfinite(zl)
            deeper = ring & (zl < level - 0.5)
            dl, nd = ndi.label(deeper, structure=np.ones((3, 3)))
            sd = int(sum(1 for k in range(1, nd + 1) if (dl == k).sum() >= 3))
            if sd > sides or (sd == sides and deeper.any()):
                sides, drop = sd, (float(level - np.nanmedian(zl[deeper])) if deeper.any() else 0.0)
        rr, cc = np.nonzero(m)
        k = len(rr) // 2
        xc, yc = float(X[r0 + rr[k], c0 + cc[k]]), float(Y[r0 + rr[k], c0 + cc[k]])
        mh_l, tid_l = mh[r0:r1, c0:c1][m], tidal[r0:r1, c0:c1][m]
        pool_l, bl_l = pool[r0:r1, c0:c1][m], bl[r0:r1, c0:c1][m]
        bl_ids = np.unique(bl_l[bl_l >= 0])
        out.append(dict(tier=tier, x=xc, y=yc, npx=npx, area_m2=npx * STEP * STEP, level=level,
                        std=float(np.nanstd(vals)), mode_share=mode_share, sides=sides, drop=drop,
                        mhhw=float(np.nanmedian(mh_l)) if np.isfinite(mh_l).any() else np.nan,
                        tidal_share=float(tid_l.mean()),
                        pool=float(np.nanmedian(pool_l)) if np.isfinite(pool_l).any() else np.nan,
                        pool_share=float(np.isfinite(pool_l).mean()),
                        nhd_share=float((wet25[r0:r1, c0:c1][m] == 1).mean()),
                        bl_share=float((bl_l >= 0).mean()), bl_ids=",".join(str(int(b)) for b in bl_ids[:8])))
    return out


# ---------------------------------------------------------------- one tile
def run_tile(args):
    """Tier A: EXACTLY flat (5 x 5 range <= 5 mm: hydro-flattened water, constant fills). Tier B: NEAR-flat
    (3 x 3 range <= 0.15 m: lidar water-surface returns / shadow fills under decks in topobathy, which carry cm
    noise), kept only with the sill signature (deeper bed >= 1 m below on >= 2 separate sides)."""
    (x0, y0), bed_spec = args
    from scipy import ndimage as ndi

    t = np.arange(0, TILE, STEP) + STEP / 2
    X, Y = np.meshgrid(x0 + t, y0 + TILE - t)  # row 0 = north
    wet25 = _CTX.water.sample(X, Y)
    mh = _CTX.mhhw.sample(X, Y)
    src = _CTX.msrc.sample(X, Y)
    tidal = np.isfinite(mh) & (((src >= 1) & (src <= 16)) | (src == 21))  # VDatum or along a tidal reach, not land ext.
    pool = _CTX.pool.sample(X, Y)
    bl = _BL_RASTER(X, Y)
    z = _BED.sample(X, Y)
    fin = np.isfinite(z)
    if fin.sum() < 50:
        return []
    zz = np.where(fin, z, np.nan)
    big, small = np.where(fin, z, -1e9), np.where(fin, z, 1e9)
    wet = (wet25 == 1) | (bl >= 0) | (tidal & (z < mh + WET_ABOVE_MHHW)) | np.isfinite(pool)
    rngA = ndi.maximum_filter(big, 5) - ndi.minimum_filter(small, 5)
    labA, nA = ndi.label(fin & (rngA <= FLAT_TOL) & wet, structure=np.ones((3, 3)))
    out = _patches(labA, nA, "A", zz, X, Y, mh, tidal, pool, wet25, bl, MIN_AREA) if nA else []
    rngB = ndi.maximum_filter(big, 3) - ndi.minimum_filter(small, 3)
    flatB = fin & (rngB <= 0.15) & wet & tidal & ~(labA > 0)
    labB, nB = ndi.label(flatB, structure=np.ones((3, 3)))
    if nB:
        for p in _patches(labB, nB, "B", zz, X, Y, mh, tidal, pool, wet25, bl, 90.0):
            if p["sides"] >= 2 and p["drop"] >= 1.0 and p["std"] <= 0.08 and p["area_m2"] <= 20000:
                out.append(p)
    return out


_BED = _CTX = None
_BL_RASTER = None


def _init(bed_spec, overlay_min):
    global _BED, _CTX, _BL_RASTER
    _BED, _ = make_bed(bed_spec, overlay_min)
    _CTX = Ctx()
    _BL_RASTER = BLRaster()


class BLRaster:
    """Breakline water-polygon ids rasterised per tile (3 m, all_touched=False) through a spatial index."""

    def __init__(self):
        self.bl = breaklines()
        self.sidx = self.bl.sindex

    def __call__(self, X, Y):
        from rasterio.features import rasterize
        from rasterio.transform import from_origin
        from shapely.geometry import box

        x0, x1 = float(X.min()) - STEP / 2, float(X.max()) + STEP / 2
        y0, y1 = float(Y.min()) - STEP / 2, float(Y.max()) + STEP / 2
        idx = self.sidx.query(box(x0, y0, x1, y1))
        if len(idx) == 0:
            return np.full(X.shape, -1, np.int64)
        sub = self.bl.iloc[idx]
        arr = rasterize(((g, int(i)) for g, i in zip(sub.geometry.values, sub.bl_id.values)), out_shape=X.shape,
                        transform=from_origin(x0, y1, STEP, STEP), fill=-1, dtype="int32", all_touched=False)
        return arr.astype(np.int64)


def build_bl_raster(bl):
    return  # per-tile rasterisation (BLRaster); a domain-wide 3 m raster would be ~21 GB


def tiles():
    """2.4 km tiles inside the region ring that hold any water (NHD mask, MHHW-defined, or a breakline polygon)."""
    import geopandas as gpd
    import rasterio
    from shapely.geometry import box

    ring = gpd.read_file(REGION).to_crs(32618).geometry.union_all()
    with rasterio.open(NS / "water_mask_v4.tif") as a, rasterio.open(NS / "mhhw_navd88_v4.tif") as b:
        wm, mh, tr = a.read(1), b.read(1), a.transform
    any_w = (wm == 1) | np.isfinite(mh)
    x0, y0, x1, y1 = ring.bounds
    out = []
    for xx in np.arange(np.floor(x0 / TILE) * TILE, x1, TILE):
        for yy in np.arange(np.floor(y0 / TILE) * TILE, y1, TILE):
            if not ring.intersects(box(xx, yy, xx + TILE, yy + TILE)):
                continue
            c0, r1 = ~tr * (xx, yy)
            c1, r0 = ~tr * (xx + TILE, yy + TILE)
            r0, r1, c0, c1 = int(max(r0, 0)), int(max(r1, 0)), int(max(c0, 0)), int(max(c1, 0))
            if r1 > r0 and c1 > c0 and any_w[r0:r1, c0:c1].any():
                out.append((float(xx), float(yy)))
    return out, ring


# ---------------------------------------------------------------- classification → SCHEMA rows
def classify(p, bl):
    """kind, severity, note, fix, source for one patch (dict from run_tile + breakline match); kind None = drop."""
    tidal = p["tidal_share"] >= 0.5 and p["pool_share"] < 0.5
    lvl = p["level"]
    sill = p["sides"] >= 2 and p["drop"] >= 1.0
    edge = p["sides"] >= 1 and p["drop"] >= 0.5
    conf = bool(p["bl_match"])
    src = (f"3DEP breakline {p['bl_project']}/{p['bl_layer']} (Z {p['bl_zmin']:.2f}..{p['bl_zmax']:.2f} m)" if conf
           else "flat-patch signature (no breakline)")
    if p["tier"] == "A" and not conf and p["mode_share"] < 0.5 and abs(lvl) > 0.02:
        return None, None, "", "", src  # smooth (interpolated) surface, not a flattened one
    if tidal and not conf and lvl < p["mhhw"] - BELOW_MHHW_MAX:
        # deeper than any low tide here (largest tidal range ~2.6 m, Trenton): not a water surface. These are the
        # constant blocks of coarse tiers (GMRT 50 m, CUDEM 1/3") sampled nearest; channel depth is another check.
        return None, None, "", "", src
    if p["pool_share"] >= 0.5 and np.isfinite(p["pool"]):
        if abs(lvl - p["pool"]) <= 0.3:
            return "intended_pool", None, "impounded / non-tidal lake held at its pool (intended)", "", src
        if abs(lvl) <= 0.02:
            return ("cudem_fill_under_lake", "medium",
                    f"CUDEM flat 0 m fill under a lake whose normal pool is {p['pool']:+.2f} m: a fake pit "
                    "(can fill from the tide if connected below the pool; see the impoundment check)",
                    "raise to the pool (max(bed, pool)) upstream of the dam", src)
        return ("lake_surface_mismatch", "low",
                f"lake surface {lvl:+.2f} m differs from its normal pool {p['pool']:+.2f} by > 0.3 m", "", src)
    if p["tier"] == "B" and np.isfinite(p["mhhw"]) and lvl > p["mhhw"] + 0.3:
        kind = "structure_over_water"  # a pier / deck / causeway strip, above any normal water level
    elif p["tier"] == "B":
        kind = "near_flat_sill"
    elif abs(lvl) <= 0.02 and not conf:
        kind = "cudem_flat_fill"
    else:
        kind = "water_surface_as_bed"
    mapped = p["nhd_share"] >= 0.5 or p["bl_share"] >= 0.5  # inside an NHD river / lake area or a breakline water polygon
    if p["tier"] == "B" and not mapped:
        if kind == "structure_over_water":
            return (kind, "medium", f"a near-flat strip at {lvl:+.2f} m between deeper beds outside mapped water "
                    "(a causeway / road over marsh?)", "", src)
        return ("near_flat_sill", "low", f"near-flat {lvl:+.2f} m between deeper beds outside mapped water: most "
                "likely a marsh platform between creeks (real ground)", "", src)
    if tidal:
        if sill and kind == "structure_over_water":
            sev = "high"
            note = (f"a near-flat strip at {lvl:+.2f} m (above MHHW {p['mhhw']:+.2f}) across tidal water, deeper bed on "
                    f"{p['sides']} sides ({p['drop']:.1f} m below): a deck / pier / causeway in the bed (crossing check)")
        elif sill:
            sev = "high"
            note = (f"{'near-' if p['tier'] == 'B' else ''}flat {lvl:+.2f} m across tidal water, deeper bed on "
                    f"{p['sides']} sides ({p['drop']:.1f} m below): a SILL that is a water surface / under-deck fill, "
                    "not the bottom")
        elif lvl >= p["mhhw"] - 0.1 and p["area_m2"] >= 1000:
            sev = "high"
            note = (f"tidal water stored as a flat {lvl:+.2f} m surface, at or above MHHW {p['mhhw']:+.2f}: "
                    "normal tides cannot enter it")
        elif edge:
            sev = "medium"
            note = f"flat {lvl:+.2f} m in tidal water beside deeper bed ({p['drop']:.1f} m): holds the channel shallow"
        elif conf and (p["nhd_share"] >= 0.5 or any(k in str(p["bl_layer"]).lower() for k in ("ocean", "river"))):
            sev = "medium"
            note = (f"a mapped tidal channel held at the lidar's water surface {lvl:+.2f} m (MHHW {p['mhhw']:+.2f}): "
                    "the bottom is missing, the channel is too shallow by its unknown depth")
        else:
            sev = "medium" if (p["area_m2"] >= 5000 and lvl > p["mhhw"] - 1.5) else "low"
            note = f"flat {lvl:+.2f} m patch in tidal water (MHHW {p['mhhw']:+.2f}); the bottom is unknown"
    else:
        sev = "medium" if sill else "low"
        note = f"flat {lvl:+.2f} m in non-tidal water" + (" forming a sill" if sill else "")
    fix = ("lower to the channel either side (survey / chart where available)" if sev in ("high", "medium")
           and (sill or edge) else "replace with a surveyed / assumed bottom (min of beds on mapped water)"
           if sev != "low" else "")
    if conf:
        note += "; confirmed by the lidar project's breakline"
    return kind, sev, note, fix, src


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bed", required=True, help="subgrid dir, or 'modern'")
    ap.add_argument("--label", required=True)
    ap.add_argument("--overlay-min", nargs="*", default=[])
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0, help="debug: only N tiles")
    ap.add_argument("--box", type=float, nargs=4, default=None, help="debug: lon0 lat0 lon1 lat1")
    a = ap.parse_args()

    import geopandas as gpd
    import pandas as pd
    from pyproj import Transformer

    bl = breaklines()
    build_bl_raster(bl)
    T, ring = tiles()
    to_ll = Transformer.from_crs(32618, 4326, always_xy=True).transform
    if a.box:
        to_utm = Transformer.from_crs(4326, 32618, always_xy=True).transform
        bx0, by0 = to_utm(a.box[0], a.box[1])
        bx1, by1 = to_utm(a.box[2], a.box[3])
        T = [t for t in T if t[0] + TILE > bx0 and t[0] < bx1 and t[1] + TILE > by0 and t[1] < by1]
    if a.limit:
        T = T[: a.limit]
    print(f"[water_surface] bed={a.bed} label={a.label} tiles={len(T)} breakline polygons={len(bl)}", flush=True)
    from multiprocessing import Pool

    with Pool(a.workers, initializer=_init, initargs=(a.bed, a.overlay_min)) as pool:
        res = []
        for k, r in enumerate(pool.imap_unordered(run_tile, [(t, a.bed) for t in T], chunksize=4)):
            res.extend(r)
            if k % 200 == 0:
                print(f"  {k}/{len(T)} tiles, {len(res)} patches", flush=True)
    P = pd.DataFrame(res)
    if P.empty:
        print("no patches")
        return
    # keep patches inside the ring; de-duplicate patches cut by tile edges (same level, < 10 m apart is rare: keep)
    pts = gpd.GeoSeries(gpd.points_from_xy(P.x, P.y), crs=32618)
    P = P[pts.within(ring).values].reset_index(drop=True)
    # breakline match: the patch level within the polygon's Z range (+-0.15 m)
    bl_i = bl.set_index("bl_id")
    m_ok, m_proj, m_lay, m_z0, m_z1 = [], [], [], [], []
    for _, p in P.iterrows():
        ok = False
        best = None
        for s in [b for b in str(p.bl_ids).split(",") if b]:
            r = bl_i.loc[int(s)]
            if np.isfinite(r.zmin) and r.zmin - 0.15 <= p.level <= r.zmax + 0.15:
                ok, best = True, r
                break
            best = best if best is not None else r
        m_ok.append(ok)
        m_proj.append(best.project if best is not None else "")
        m_lay.append(best.layer if best is not None else "")
        m_z0.append(float(best.zmin) if best is not None else np.nan)
        m_z1.append(float(best.zmax) if best is not None else np.nan)
    P["bl_match"], P["bl_project"], P["bl_layer"], P["bl_zmin"], P["bl_zmax"] = m_ok, m_proj, m_lay, m_z0, m_z1
    rows = []
    n_dropped = 0
    for _, p in P.iterrows():
        kind, sev, note, fix, src = classify(p, bl)
        if kind is None:
            n_dropped += 1
            continue
        lon, lat = to_ll(p.x, p.y)
        rows.append(dict(check="water_surface", id=f"WS_{int(round(p.x))}_{int(round(p.y))}", lon=round(lon, 6),
                         lat=round(lat, 6), severity=sev, kind=kind, metric="flat patch level (m NAVD88)",
                         value=round(p.level, 3), expected=(round(p.mhhw, 3) if np.isfinite(p.mhhw) else ""),
                         units="m", area_m2=round(p.area_m2), sides=p.sides, drop_m=round(p["drop"], 2),
                         breakline=("yes" if p.bl_match else "no"), tier=p.tier, source=src, note=note, fix=fix,
                         x=p.x, y=p.y))
    R = pd.DataFrame(rows)
    n_pool = int((R.kind == "intended_pool").sum())
    R = R[R.kind != "intended_pool"].copy()
    add_context(R)
    order = {"high": 0, "medium": 1, "low": 2}
    R["_o"] = R.severity.map(order)
    R = R.sort_values(["_o", "area_m2"], ascending=[True, False]).drop(columns=["_o", "x", "y"])
    cols = ["check", "id", "lon", "lat", "severity", "kind", "metric", "value", "expected", "units", "area_m2",
            "sandy_peak_m", "near_asset", "asset_km", "source", "note", "fix", "sides", "drop_m", "breakline", "tier"]
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    R[cols].to_csv(out, index=False)
    summ = dict(label=a.label, bed=a.bed, overlay_min=a.overlay_min, tiles=len(T), intended_pools=n_pool, dropped_not_water_surface=n_dropped,
                by_severity=R.severity.value_counts().to_dict(), by_kind=R.kind.value_counts().to_dict(),
                breakline_confirmed=int((R.breakline == "yes").sum()))
    out.with_suffix(".summary.json").write_text(json.dumps(summ, indent=1))
    print(json.dumps(summ, indent=1))


def add_context(R):
    """sandy_peak_m (1.0.0's zsmax at the nearest face within 300 m) and the nearest power asset within 2 km."""
    import geopandas as gpd
    from scipy.spatial import cKDTree

    fc = CACHE / "p4_premier_face_xy_zsmax.npz"
    if not fc.exists():
        import xarray as xr

        d = xr.open_dataset(MAP)
        nx, ny = d.mesh2d_node_x.values, d.mesh2d_node_y.values
        fn = d.mesh2d_face_nodes.values
        fn = np.where(np.isfinite(fn), fn, fn[:, :1]).astype(np.int64)
        fn = fn - (1 if fn.min() >= 1 and fn.max() >= len(nx) else 0)
        fx, fy = nx[fn].mean(1), ny[fn].mean(1)
        zs = d.zsmax.max("timemax").values
        np.savez(fc, fx=fx, fy=fy, zs=zs)
    f = np.load(fc)
    ok = np.isfinite(f["zs"])
    tr = cKDTree(np.c_[f["fx"][ok], f["fy"][ok]])
    dd, ii = tr.query(np.c_[R.x.values, R.y.values], distance_upper_bound=300)
    zs = f["zs"][ok]
    R["sandy_peak_m"] = [round(float(zs[i]), 2) if np.isfinite(d_) else "" for d_, i in zip(dd, ii)]
    A = []
    for p in ASSETS:
        g = gpd.read_file(p).to_crs(32618)
        name = next((c for c in ("name", "Name", "NAME", "facility", "substation") if c in g.columns), None)
        A.append(gpd.GeoDataFrame(dict(nm=g[name].astype(str) if name else p.stem), geometry=g.geometry.centroid))
    import pandas as pd

    A = pd.concat(A, ignore_index=True)
    ta = cKDTree(np.c_[A.geometry.x, A.geometry.y])
    da, ia = ta.query(np.c_[R.x.values, R.y.values], distance_upper_bound=2000)
    R["near_asset"] = [A.nm.values[i] if np.isfinite(d_) else "" for d_, i in zip(da, ia)]
    R["asset_km"] = [round(d_ / 1000, 2) if np.isfinite(d_) else "" for d_ in da]


if __name__ == "__main__":
    main()
