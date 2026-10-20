"""Build v4's usual-surface rasters: VDatum MHHW (m NAVD88) and non-tidal lake pools.

Writes into ``data/normal_surface_v4/`` (``nj_sfincs/normal_surface.py`` reads them):

* ``mhhw_navd88_v4.tif``  float32, EPSG:32618, 25 m, NaN = none. MHHW = ``mhhw.gtx`` −
  ``tss.gtx`` from NOAA VDatum's regional grids (``mhhw.gtx`` = MHHW − LMSL, ``tss.gtx`` =
  NAVD88 − LMSL, the "topography of the sea surface"), bilinear over the valid grid nodes,
  then nearest-neighbour ≤ ``EXT_M`` onto land.
* ``mhhw_source_v4.tif``  uint8: 1–6 = VDatum region (``GRIDS`` order) whose nearest node is
  valid, 11–16 = that region by bilinear edge weights only, 21 = along-water fill up a
  tidal reach VDatum stops short of, 20 = land extension, 0 = none.
* ``lake_pool_v4.tif``    float32: the pool of every NON-tidal NHD lake/pond, NaN elsewhere.
* ``water_mask_v4.tif``   uint8: 1 = an NHD river/stream/canal area or lake polygon.
* ``lakes_v4.csv``, ``station_check_v4.csv``, ``coverage_v4.json`` — the evidence.

Inputs (downloaded 2026-10-19, each in its own dir under ``downloads/``): the six VDatum
regional zips (``vdatum.noaa.gov/download/data/<region>.zip``), the CO-OPS datums +
station metadata JSONs; the NHD lakes ``data/elevation_v4/inland_water/nhd_lake_v4.gpkg``;
the NJ 10 ft lidar DEM and the 3DEP 1/3" VRT for the lake water surfaces.

    python scripts/build_normal_surface_v4.py --step all   # ~3–4 GB RAM
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data" / "normal_surface_v4"
DL = OUT / "downloads"
TEMPLATE = REPO / "experiments" / "v4_refreeze" / "_template_sealed" / "sfincs.nc"
LAKES = REPO / "data" / "elevation_v4" / "inland_water" / "nhd_lake_v4.gpkg"
LIDAR_NJ = REPO / "data" / "elevation_v4" / "nj_10ft_dem_v4.tif"
#: 3DEP 1/3" over the whole rectangle: the five tiles of data/elevation_v4/3dep/ plus
#: n40w075 + n39w075 (downloads/3dep_13_*), built by gdalbuildvrt (absolute paths)
LIDAR_3DEP = OUT / "3dep_13_v4.vrt"
RING = REPO / "data" / "region_v4_hot_plus.geojson"  # v4_refreeze's region
COARSE_BED = REPO / "data" / "elevation_v4" / "bed_v4_coarse_25m.tif"
RIVERS = REPO / "data" / "elevation_v4" / "inland_water" / "nhd_river_v4.gpkg"
WATER_BED_M = -0.2  # coarse bed below this = water for the along-river fill (CUDEM
#                     holds some non-tidal water as a flat ~0 m surface: stay below it)
#: CO-OPS tidal stations ABOVE VDatum's coverage, used as anchors of the along-river fill
#: (MHHW − NAVD88 from their published datums; station check table).
RIVER_ANCHORS = (8534691, 8535055)  # Great Egg Harbor River, Bivalve (Maurice)

#: Priority where region boundaries overlap: the fine embayment grids, the harbour, the
#: Delaware, the offshore Mid-Atlantic Bight last (the order build_naccs_boundary.py uses
#: for the same grids' tss).
GRIDS = (
    "NJncstemb11_8301",
    "NYNJhbr33_8301",
    "NJscstemb21_8301",
    "NJcstemb12_8301",
    "DEdelbay22_8301",
    "NJVAmab22_8301",
)
RES = 25.0
EPSG = 32618
EXT_M = 2000.0  # nearest-neighbour extension onto land
TIDAL_FRAC = 0.5  # a lake is tidal when ≥ this share of its pixels sit on VDatum nodes
DAM_M = 0.25  # ...unless its lidar surface stands this far above MHHW (a dammed lake;
#              tidal lakes' lidar surfaces sit at or below MHHW: median −0.14 m)

STATIONS = {
    # id: name — every in-domain CO-OPS station with published datums (07-19 query)
    8519050: "USCG Station NY (Narrows)",
    8519483: "Bergen Point West Reach",
    8531142: "Port Reading",
    8531680: "Sandy Hook",
    8533615: "Barnegat Inlet (inside)",
    8534319: "Great Bay, Shooting Thorofare",
    8534691: "Great Egg Harbor River",
    8534720: "Atlantic City",
    8535055: "Bivalve, Maurice River",
    8536110: "Cape May",
    8536581: "Bidwell Creek entrance",
    8536931: "Fortescue Creek",
    8537121: "Ship John Shoal",
    8538886: "Tacony-Palmyra Bridge",
    8539094: "Burlington",
    8540433: "Marcus Hook",
    8545240: "Philadelphia",
    8546252: "Bridesburg",
    8548989: "Newbold",
    8551762: "Delaware City",
    8551910: "Reedy Point",
    8555889: "Brandywine Shoal Light",
    8557380: "Lewes",
    8518750: "The Battery (outside the forced line)",
    # added 2026-10-19 (follow-up): the upper tidal Delaware and Raritan
    8539993: "Trenton Marine Terminal",
    8539487: "Fieldsboro",
    8531463: "New Brunswick, Raritan River",
    8531390: "Sayreville, Raritan River",
}


# ── VDatum grids ──────────────────────────────────────────────────────────────────────
def _bilinear(f, T, lon, lat):
    """Bilinear on a GTX lattice (GDAL: node = pixel CENTRE, lon 0..360), weights
    renormalised over the valid nodes; plus a nearest-node-valid flag."""
    h, w = f.shape
    c, r = ~T @ (np.asarray(lon, float) % 360.0, np.asarray(lat, float))
    c = c - 0.5
    r = r - 0.5
    c0 = np.floor(c).astype("int64")
    r0 = np.floor(r).astype("int64")
    fc, fr = c - c0, r - r0
    acc = np.zeros(c.shape)
    ws = np.zeros(c.shape)
    for dr, dc, wt in (
        (0, 0, (1 - fr) * (1 - fc)),
        (0, 1, (1 - fr) * fc),
        (1, 0, fr * (1 - fc)),
        (1, 1, fr * fc),
    ):
        rr, cc = r0 + dr, c0 + dc
        inb = (rr >= 0) & (rr < h) & (cc >= 0) & (cc < w)
        v = np.full(c.shape, np.nan)
        v[inb] = f[rr[inb], cc[inb]]
        g = np.isfinite(v)
        acc += np.where(g, wt * v, 0.0)
        ws += np.where(g, wt, 0.0)
    val = np.where(ws > 0, acc / np.where(ws > 0, ws, 1), np.nan)
    rn, cn = np.rint(r).astype("int64"), np.rint(c).astype("int64")
    inb = (rn >= 0) & (rn < h) & (cn >= 0) & (cn < w)
    core = np.zeros(c.shape, bool)
    core[inb] = np.isfinite(f[rn[inb], cn[inb]])
    return val, core


class VGrid:
    """One VDatum region. ``mhhw.gtx`` (MHHW − LMSL) and ``tss.gtx`` (NAVD88 − LMSL) sit
    on DIFFERENT lattices (tss is a shared regional field), so each is interpolated on its
    own and MHHW above NAVD88 = mhhw − tss at the point."""

    def __init__(self, name: str):
        import rasterio
        from shapely.geometry import Polygon

        d = DL / f"vdatum_{name}" / "vdatum" / name
        with rasterio.open(d / "mhhw.gtx") as s:
            m = s.read(1).astype("float64")
            self.Tm = s.transform
        with rasterio.open(d / "tss.gtx") as s:
            t = s.read(1).astype("float64")
            self.Tt = s.transform
        self.mhhw = np.where(m > -80, m, np.nan)  # -88.8888 = nodata
        # tss also carries 171 isolated junk nodes (|tss| 1–10 m, NYNJ/NJncst lattice,
        # all inland); the real field here spans -0.27..+0.16 m and is smooth to 0.05 m
        # node-to-node, so anything past 0.5 m is nodata.
        self.tss = np.where((t > -80) & (np.abs(t) <= 0.5), t, np.nan)
        self.name = name
        xy = np.loadtxt(d / f"{name}.bnd", usecols=(0, 1))
        self.bnd = Polygon(xy)

    def sample(self, lon, lat):
        """(MHHW−NAVD88, MHHW−LMSL, LMSL−NAVD88, nearest mhhw node valid)."""
        m, core = _bilinear(self.mhhw, self.Tm, lon, lat)
        t, _ = _bilinear(self.tss, self.Tt, lon, lat)
        return m - t, m, -t, core

    def nearest_node(self, lon, lat, max_cells=5):
        """(lon, lat, distance in cells) of the nearest valid MHHW node to one point."""
        c, r = ~self.Tm @ (lon % 360.0, lat)
        c, r = c - 0.5, r - 0.5
        ri, ci = int(round(r)), int(round(c))
        best = (np.nan, np.nan, np.inf)
        for dr in range(-max_cells, max_cells + 1):
            for dc in range(-max_cells, max_cells + 1):
                rr, cc = ri + dr, ci + dc
                if 0 <= rr < self.mhhw.shape[0] and 0 <= cc < self.mhhw.shape[1]:
                    if np.isfinite(self.mhhw[rr, cc]):
                        dd = np.hypot(rr - r, cc - c)
                        if dd < best[2]:
                            x, y = self.Tm @ (cc + 0.5, rr + 0.5)
                            best = (x - 360.0, y, dd)
        return best


def load_grids():
    return [VGrid(n) for n in GRIDS]


# ── target grid ───────────────────────────────────────────────────────────────────────
def target_grid():
    """25 m north-up EPSG:32618 grid covering the v4 model rectangle (mesh nodes)."""
    import xarray as xr
    from rasterio.transform import from_origin

    with xr.open_dataset(TEMPLATE) as ds:
        nx, ny = ds.mesh2d_node_x.values, ds.mesh2d_node_y.values
    x0 = np.floor(nx.min() / RES) * RES
    x1 = np.ceil(nx.max() / RES) * RES
    y0 = np.floor(ny.min() / RES) * RES
    y1 = np.ceil(ny.max() / RES) * RES
    w, h = int(round((x1 - x0) / RES)), int(round((y1 - y0) / RES))
    return from_origin(x0, y1, RES, RES), h, w


def write_tif(path: Path, a: np.ndarray, T, nodata, desc: str):
    import rasterio

    prof = dict(
        driver="GTiff",
        height=a.shape[0],
        width=a.shape[1],
        count=1,
        dtype=a.dtype,
        crs=f"EPSG:{EPSG}",
        transform=T,
        nodata=nodata,
        compress="deflate",
        tiled=True,
        blockxsize=512,
        blockysize=512,
        BIGTIFF="IF_SAFER",
    )
    if a.dtype.kind == "f":
        prof["predictor"] = 3
    tmp = path.with_suffix(".tmp.tif")
    with rasterio.open(tmp, "w", **prof) as dst:
        dst.write(a, 1)
        dst.update_tags(DESCRIPTION=desc, BUILT_BY="scripts/build_normal_surface_v4.py")
    tmp.replace(path)  # atomic


# ── step 1: the station check ─────────────────────────────────────────────────────────
def step_stations(grids):
    import pandas as pd

    rows = []
    for sid, label in STATIONS.items():
        dj = json.loads((DL / "coops_datums" / f"{sid}.json").read_text())
        mj = json.loads((DL / "coops_stations" / f"{sid}.json").read_text())
        st = mj["stations"][0]
        lon, lat = float(st["lng"]), float(st["lat"])
        v = {x["name"]: x["value"] for x in dj.get("datums") or []}
        navd = v.get("NAVD88")
        row = dict(
            station=sid,
            name=label,
            lon=lon,
            lat=lat,
            epoch=dj.get("epoch"),
            coops_mhhw_msl=v["MHHW"] - v["MSL"],
            coops_msl_navd=(v["MSL"] - navd) if navd is not None else np.nan,
            coops_mhhw_navd=(v["MHHW"] - navd) if navd is not None else np.nan,
        )
        for g in grids:  # first region (priority order) whose boundary holds it
            from shapely.geometry import Point

            if not g.bnd.contains(Point(lon, lat)):
                continue
            mn, ml, ln, core = g.sample([lon], [lat])
            dist = 0.0
            if not np.isfinite(ml[0]):  # station on a pier / bank: nearest wet node
                qlon, qlat, dist = g.nearest_node(lon, lat)
                if np.isfinite(qlon):
                    mn, ml, ln, core = g.sample([qlon], [qlat])
            if np.isfinite(mn[0]):
                cell_m = abs(g.Tm.a) * 111_000 * np.cos(np.deg2rad(lat))
                row.update(
                    region=g.name,
                    vd_mhhw_navd=mn[0],
                    vd_mhhw_msl=ml[0],
                    vd_msl_navd=ln[0],
                    node_offset_m=dist * cell_m,
                    on_grid=bool(core[0]) and dist == 0.0,
                )
                break
        rows.append(row)
    df = pd.DataFrame(rows)
    df["d_mhhw_navd"] = df.vd_mhhw_navd - df.coops_mhhw_navd
    df["d_mhhw_msl"] = df.vd_mhhw_msl - df.coops_mhhw_msl
    df["d_msl_navd"] = df.vd_msl_navd - df.coops_msl_navd
    df.round(4).to_csv(OUT / "station_check_v4.csv", index=False)
    with np.printoptions(precision=3):
        print(
            df[
                [
                    "station",
                    "name",
                    "region",
                    "coops_mhhw_navd",
                    "vd_mhhw_navd",
                    "d_mhhw_navd",
                    "coops_mhhw_msl",
                    "d_mhhw_msl",
                    "d_msl_navd",
                    "node_offset_m",
                ]
            ].to_string(index=False, float_format=lambda v: f"{v:+.3f}")
        )
    for k in ("d_mhhw_navd", "d_mhhw_msl", "d_msl_navd"):
        d = df[k].dropna()
        print(
            f"{k}: n={len(d)} mean {d.mean():+.3f} mean|.| {d.abs().mean():.3f} "
            f"max|.| {d.abs().max():.3f} m"
        )
    return df


# ── step 2: the MHHW raster ───────────────────────────────────────────────────────────
def _river_fill(mhhw, T, ring_utm):
    """Carry MHHW up the tidal reaches VDatum stops short of: every water pixel (coarse
    bed < WATER_BED_M, or an NHD river/canal polygon) inside the ring that is connected
    through water to a VDatum pixel takes an inverse-ALONG-WATER-distance blend of the
    nearest VDatum pixel and the nearest upriver CO-OPS anchor (``RIVER_ANCHORS``).
    Returns (filled values for the new pixels as a full array, mask of new pixels)."""
    import geopandas as gpd
    import rasterio
    from pyproj import Transformer
    from rasterio.features import rasterize
    from rasterio.warp import Resampling, reproject
    from scipy import ndimage, sparse
    from scipy.sparse.csgraph import dijkstra

    h, w = mhhw.shape
    raw = np.isfinite(mhhw)
    bed = np.full((h, w), np.nan, np.float32)
    with rasterio.open(COARSE_BED) as d:
        reproject(
            rasterio.band(d, 1),
            bed,
            dst_transform=T,
            dst_crs=f"EPSG:{EPSG}",
            dst_nodata=np.nan,
            resampling=Resampling.nearest,
        )
    rv = gpd.read_file(RIVERS).to_crs(EPSG)
    river = rasterize(
        [(g, 1) for g in rv.geometry], out_shape=(h, w), transform=T, dtype="uint8"
    ).astype(bool)
    inring = rasterize(
        [(ring_utm, 1)], out_shape=(h, w), transform=T, dtype="uint8"
    ).astype(bool)
    water = inring & ((bed < WATER_BED_M) | river)
    del bed, river
    unk = water & ~raw
    lab, n = ndimage.label(unk, structure=np.ones((3, 3)))
    touch = np.unique(lab[ndimage.binary_dilation(raw, np.ones((3, 3))) & (lab > 0)])
    keep = np.isin(lab, touch[touch > 0])
    del lab
    seeds = raw & ndimage.binary_dilation(keep, np.ones((3, 3)))
    nodes = keep | seeds
    idx = np.full((h, w), -1, np.int64)
    rr, cc = np.nonzero(nodes)
    idx[rr, cc] = np.arange(rr.size)
    print(
        f"[river] {int(keep.sum()):,} water px beyond VDatum, {int(seeds.sum()):,} seeds"
    )
    rows, cols, wts = [], [], []
    for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
        r2, c2 = rr + dr, cc + dc
        ok = (r2 >= 0) & (r2 < h) & (c2 >= 0) & (c2 < w)
        j = np.full(rr.size, -1, np.int64)
        j[ok] = idx[r2[ok], c2[ok]]
        ok = j >= 0
        # no edge between two seeds: the fill runs through unknown water only
        both_seed = seeds[rr[ok], cc[ok]] & seeds[r2[ok], c2[ok]]
        i0 = np.arange(rr.size)[ok][~both_seed]
        j0 = j[ok][~both_seed]
        rows.append(i0)
        cols.append(j0)
        wts.append(np.full(i0.size, RES * np.hypot(dr, dc)))
    G = sparse.coo_matrix(
        (np.concatenate(wts), (np.concatenate(rows), np.concatenate(cols))),
        shape=(rr.size, rr.size),
    ).tocsr()
    seed_i = idx[seeds]
    d1, _, src1 = dijkstra(
        G, directed=False, indices=seed_i, min_only=True, return_predecessors=True
    )
    v1 = np.where(
        src1 >= 0, mhhw[rr[np.maximum(src1, 0)], cc[np.maximum(src1, 0)]], np.nan
    )
    # anchors: the CO-OPS value at the water node nearest each station
    to_utm = Transformer.from_crs(4326, EPSG, always_xy=True)
    kr, kc = np.nonzero(keep)
    a_i, a_v = [], []
    for sid in RIVER_ANCHORS:
        dj = json.loads((DL / "coops_datums" / f"{sid}.json").read_text())
        st = json.loads((DL / "coops_stations" / f"{sid}.json").read_text())[
            "stations"
        ][0]
        v = {x["name"]: x["value"] for x in dj["datums"]}
        x, y = to_utm.transform(float(st["lng"]), float(st["lat"]))
        c, r = ~T @ (x, y)
        k = np.argmin((kr - r) ** 2 + (kc - c) ** 2)
        off = RES * np.hypot(kr[k] - r, kc[k] - c)
        print(
            f"[river] anchor {sid}: MHHW {v['MHHW'] - v['NAVD88']:+.3f} m NAVD88, "
            f"water node {off:.0f} m away"
        )
        if off < 500:
            a_i.append(idx[kr[k], kc[k]])
            a_v.append(v["MHHW"] - v["NAVD88"])
    val = v1
    if a_i:
        d2, _, src2 = dijkstra(
            G, directed=False, indices=a_i, min_only=True, return_predecessors=True
        )
        amap = dict(zip(a_i, a_v))
        v2 = np.array([amap.get(s, np.nan) for s in src2])
        w1 = 1.0 / np.maximum(d1, RES)
        w2 = 1.0 / np.maximum(d2, RES)
        both = np.isfinite(d1) & np.isfinite(d2)
        val = np.where(both, (v1 * w1 + v2 * w2) / (w1 + w2), v1)
    out = np.full((h, w), np.nan, np.float32)
    newp = keep & np.isfinite(val[np.maximum(idx, 0)]) & (idx >= 0)
    out[newp] = val[idx[newp]]
    return out, newp


def step_mhhw(grids):
    import geopandas as gpd
    from pyproj import Transformer
    from rasterio.features import rasterize
    from scipy import ndimage
    from shapely.ops import transform as stransform

    T, h, w = target_grid()
    print(f"[mhhw] grid {w} x {h} at {RES} m, origin {T.c:.0f} {T.f:.0f}")
    to_ll = Transformer.from_crs(EPSG, 4326, always_xy=True)
    to_utm = Transformer.from_crs(4326, EPSG, always_xy=True)
    # region boundaries on the target grid: bit k = inside region k
    inreg = np.zeros((h, w), np.uint8)
    for k, g in enumerate(grids):
        poly = stransform(to_utm.transform, g.bnd)
        inreg |= rasterize(
            [(poly, 1 << k)], out_shape=(h, w), transform=T, fill=0, dtype="uint8"
        )
    mhhw = np.full((h, w), np.nan, np.float32)
    src = np.zeros((h, w), np.uint8)
    overlap = []  # |Δ| where a second region also has a value
    xs = T.c + RES * (np.arange(w) + 0.5)
    step = 400
    for r0 in range(0, h, step):
        r1 = min(h, r0 + step)
        ys = T.f - RES * (np.arange(r0, r1) + 0.5)
        X, Y = np.meshgrid(xs, ys)
        lon, lat = to_ll.transform(X, Y)
        blk = mhhw[r0:r1]
        sblk = src[r0:r1]
        samples = []
        for k, g in enumerate(grids):
            inside = (inreg[r0:r1] & (1 << k)) > 0
            if inside.any():
                val, _, _, core = g.sample(lon[inside], lat[inside])
                samples.append((k, inside, val, core))
        # two passes: a pixel whose nearest node is valid in a region takes that region
        # (priority order) before any region reaching it only by edge weights — so an
        # ocean grid's bilinear bleed never beats a bay grid's own node
        for edge in (False, True):
            for k, inside, val, core in samples:
                ok = np.isfinite(val) & (core if not edge else True)
                have = np.isfinite(blk[inside])
                both = have & ok
                if both.any() and not edge:
                    overlap.append(np.abs(val[both] - blk[inside][both]))
                take = ~have & ok
                bi = blk[inside]
                si = sblk[inside]
                bi[take] = val[take]
                si[take] = k + 11 if edge else k + 1
                blk[inside] = bi
                sblk[inside] = si
    raw = np.isfinite(mhhw)
    print(f"[mhhw] VDatum pixels {raw.sum():,} ({raw.mean():.1%} of the rectangle)")
    if overlap:
        o = np.concatenate(overlap)
        print(
            f"[mhhw] region overlaps: {o.size:,} px, |Δ| median {np.median(o):.3f} "
            f"p99 {np.percentile(o, 99):.3f} max {o.max():.3f} m"
        )
    ring_utm = stransform(to_utm.transform, gpd.read_file(RING).union_all())
    fill, newp = _river_fill(mhhw, T, ring_utm)
    mhhw[newp] = fill[newp]
    src[newp] = 21
    del fill
    print(f"[mhhw] + along-water fill up the tidal reaches: {int(newp.sum()):,} px")
    raw = np.isfinite(mhhw)
    dist, (ir, ic) = ndimage.distance_transform_edt(
        ~raw, sampling=RES, return_indices=True
    )
    ext = (~raw) & (dist <= EXT_M)
    mhhw[ext] = mhhw[ir[ext], ic[ext]]
    src[ext] = 20
    del dist, ir, ic
    print(f"[mhhw] + land extension ≤ {EXT_M:.0f} m: {ext.sum():,} px")
    write_tif(
        OUT / "mhhw_navd88_v4.tif",
        mhhw,
        T,
        np.nan,
        "MHHW (NTDE 1983-2001) m NAVD88 from NOAA VDatum mhhw.gtx - tss.gtx; "
        f"nearest-neighbour <= {EXT_M:.0f} m onto land",
    )
    write_tif(
        OUT / "mhhw_source_v4.tif",
        src,
        T,
        0,
        "1-6 VDatum region (nearest node valid) in order "
        + ",".join(GRIDS)
        + "; 11-16 same region by bilinear edge weights; 21 along-water fill up tidal "
        "reaches; 20 land extension; 0 none",
    )
    return mhhw, src, T


# ── step 3: the lakes ─────────────────────────────────────────────────────────────────
def _lidar_stats(path, geom_ll, nodata_floor=-50.0):
    """Water-surface stats of one polygon on one DEM (EPSG:4326 rasters), 1-px eroded."""
    import rasterio
    from rasterio.features import geometry_mask
    from rasterio.windows import Window
    from scipy import ndimage

    with rasterio.open(path) as d:
        b = geom_ll.bounds
        L, B, R, Tp = d.bounds
        if b[2] < L or b[0] > R or b[3] < B or b[1] > Tp:
            return None
        c0, r0 = ~d.transform @ (b[0], b[3])
        c1, r1 = ~d.transform @ (b[2], b[1])
        c0, r0 = max(int(np.floor(c0)), 0), max(int(np.floor(r0)), 0)
        c1 = min(max(int(np.ceil(c1)), c0 + 1), d.width)
        r1 = min(max(int(np.ceil(r1)), r0 + 1), d.height)
        if c1 <= c0 or r1 <= r0:
            return None
        win = Window(c0, r0, c1 - c0, r1 - r0)
        a = d.read(1, window=win, masked=True).astype("float64").filled(np.nan)
        wt = d.window_transform(win)
    inside = ~geometry_mask([geom_ll], out_shape=a.shape, transform=wt)
    core = ndimage.binary_erosion(inside)
    if core.sum() >= 4:
        inside = core
    a[(a < nodata_floor) | (a > 300)] = np.nan
    v = a[inside]
    v = v[np.isfinite(v)]
    if inside.sum() == 0:
        return None
    return dict(
        n=int(v.size),
        cover=v.size / inside.sum(),
        med=float(np.median(v)) if v.size else np.nan,
        p10=float(np.percentile(v, 10)) if v.size else np.nan,
        p90=float(np.percentile(v, 90)) if v.size else np.nan,
    )


def _build_3dep_vrt():
    import subprocess

    tiles = sorted((REPO / "data" / "elevation_v4" / "3dep").glob("USGS_13_*.tif"))
    tiles += sorted(DL.glob("3dep_13_*/USGS_13_*.tif"))
    subprocess.run(
        ["gdalbuildvrt", "-q", str(LIDAR_3DEP), *map(str, tiles)], check=True
    )


def step_lakes(mhhw=None, src=None, T=None):
    import geopandas as gpd
    import pandas as pd
    import rasterio
    from rasterio.features import rasterize

    if mhhw is None:
        with rasterio.open(OUT / "mhhw_navd88_v4.tif") as d:
            mhhw, T = d.read(1), d.transform
        with rasterio.open(OUT / "mhhw_source_v4.tif") as d:
            src = d.read(1)
    h, w = mhhw.shape
    if not LIDAR_3DEP.exists():
        _build_3dep_vrt()
    lk = gpd.read_file(LAKES)
    ring = gpd.read_file(RING).to_crs(EPSG).buffer(500).union_all()
    lk_utm = lk.to_crs(EPSG)
    keep = lk_utm.intersects(ring).values
    lk, lk_utm = lk[keep].reset_index(drop=True), lk_utm[keep].reset_index(drop=True)
    lk = lk.to_crs(4326)
    print(f"[lakes] {len(lk)} NHD lakes/ponds/reservoirs touch the v4 ring (+500 m)")
    order = np.argsort(-lk_utm.area.values)  # big first; small ones paint over
    ids = rasterize(
        [(lk_utm.geometry[i], i + 1) for i in order],
        out_shape=(h, w),
        transform=T,
        fill=0,
        dtype="int32",
    )
    flat = ids.ravel()
    srcf = src.ravel()
    mf = mhhw.ravel()
    sel = flat > 0
    lid = flat[sel] - 1
    npx = np.bincount(lid, minlength=len(lk))

    def frac(mask):
        return np.bincount(lid, weights=mask, minlength=len(lk))

    s_ = srcf[sel]
    core = frac((s_ >= 1) & (s_ <= 6))
    anyv = frac((s_ >= 1) & (s_ <= 16))
    fill = frac(s_ == 21)
    msum = frac(np.nan_to_num(mf[sel]))
    mcnt = frac(np.isfinite(mf[sel]))
    empty = dict(n=0, cover=0.0, med=np.nan, p10=np.nan, p90=np.nan)
    rows = []
    for i in range(len(lk)):
        g = lk.geometry[i]
        # 3DEP 1/3" (USGS hydro-flattening) first; the NJ 10 ft DEM where 3DEP has none
        st3 = _lidar_stats(LIDAR_3DEP, g) or empty
        stn = _lidar_stats(LIDAR_NJ, g) or empty
        if st3["n"] and st3["cover"] >= 0.5:
            st, dem = st3, "3dep_13"
        elif stn["n"]:
            st, dem = stn, "nj_10ft"
        else:
            st, dem = st3, "3dep_13" if st3["n"] else ""
        rows.append(
            dict(
                lake=i + 1,
                nhd_id=lk.permanent_identifier[i],
                name=lk.gnis_name[i] if isinstance(lk.gnis_name[i], str) else "",
                ftype=int(lk.ftype[i]),
                lon=round(g.representative_point().x, 5),
                lat=round(g.representative_point().y, 5),
                area_m2=float(lk_utm.area[i]),
                px25=int(npx[i]),
                vd_core_frac=core[i] / npx[i] if npx[i] else np.nan,
                vd_any_frac=anyv[i] / npx[i] if npx[i] else np.nan,
                river_fill_frac=fill[i] / npx[i] if npx[i] else np.nan,
                mhhw=msum[i] / mcnt[i] if mcnt[i] else np.nan,
                dem=dem,
                surf_med=st["med"],
                surf_p10=st["p10"],
                surf_p90=st["p90"],
                dem_cover=st["cover"],
                surf_3dep=st3["med"],
                surf_nj10ft=stn["med"],
            )
        )
        if (i + 1) % 1000 == 0:
            print(f"[lakes]   {i + 1} / {len(lk)}")
    df = pd.DataFrame(rows)
    tidal = df.vd_core_frac >= TIDAL_FRAC
    dammed = tidal & (df.surf_med > df.mhhw + DAM_M)
    # not on VDatum, but joined at 25 m to tidal water through water pixels (bed below
    # WATER_BED_M) and its lidar surface below MHHW: a tidal lagoon / marsh pond
    lagoon = ~tidal & (df.river_fill_frac >= 0.5) & (df.surf_med < df.mhhw)
    df["class"] = np.where(
        dammed,
        "nontidal_dammed",
        np.where(tidal, "tidal", np.where(lagoon, "tidal_connected", "nontidal")),
    )
    nt = df["class"].str.startswith("nontidal")
    df["pool"] = np.where(nt, df.surf_med, np.nan)
    df["flags"] = ""
    spread = df.surf_p90 - df.surf_p10
    df.loc[nt & (spread > 0.3), "flags"] += "not_flat;"
    df.loc[nt & df.pool.isna(), "flags"] += "no_lidar;"
    df.loc[nt & (df.pool < df.mhhw - 0.3), "flags"] += "pool_below_mhhw;"
    df.loc[nt & df.mhhw.isna() & (df.pool <= 0.0), "flags"] += "inland_pool_le_0;"
    df.loc[nt & ((df.surf_3dep - df.surf_nj10ft).abs() > 0.3), "flags"] += (
        "dem_disagree;"
    )
    df.loc[nt & (df.river_fill_frac >= 0.5), "flags"] += "joined_to_tidal_water_25m;"
    df.loc[df.px25 == 0, "flags"] += "no_25m_pixel;"
    df.round(4).to_csv(OUT / "lakes_v4.csv", index=False)
    pv = np.full(len(lk) + 1, np.nan, np.float32)
    pv[1:] = df.pool.values
    pool = pv[ids]
    pool[ids == 0] = np.nan
    write_tif(
        OUT / "lake_pool_v4.tif",
        pool,
        T,
        np.nan,
        "Normal pool m NAVD88 of non-tidal NHD lakes (lidar water surface median); "
        "see lakes_v4.csv",
    )
    c = df["class"].value_counts()
    print(f"[lakes] classes: {c.to_dict()}")
    print(
        f"[lakes] non-tidal with a pool: {int((nt & df.pool.notna()).sum())}, "
        f"area {df.area_m2[nt & df.pool.notna()].sum() / 1e6:.1f} km²; "
        f"no 25 m pixel: {int((df.px25 == 0).sum())}"
    )
    return df, ids


# ── step 3b: the mapped-water mask ────────────────────────────────────────────────────
def step_water():
    """``water_mask_v4.tif``: 1 = an NHD river/stream/canal AREA polygon (ftype 460
    StreamRiver, 336 CanalDitch, 431 Rapids — the polygons of the along-water fill) or an
    NHD lake/pond/reservoir (every class: pool or tidal lake), all_touched=False.
    It catches channels whose DEM holds the lidar WATER SURFACE above MHHW (the
    Delaware above Trenton falls, the Raritan to Bound Brook), which "ground < MHHW"
    calls dry land."""
    import geopandas as gpd
    import rasterio
    from rasterio.features import rasterize

    with rasterio.open(OUT / "mhhw_navd88_v4.tif") as d:
        T, h, w = d.transform, d.height, d.width
    shapes = [
        (g, 1)
        for f in (RIVERS, LAKES)
        for g in gpd.read_file(f).to_crs(EPSG).geometry
        if g is not None and not g.is_empty
    ]
    wm = rasterize(
        shapes, out_shape=(h, w), transform=T, fill=0, dtype="uint8", all_touched=False
    )
    write_tif(
        OUT / "water_mask_v4.tif",
        wm,
        T,
        None,
        "1 = mapped water: NHD river/stream/canal area + NHD lake/pond/reservoir "
        "polygons (nhd_river_v4.gpkg, nhd_lake_v4.gpkg), all_touched=False",
    )
    ring = gpd.read_file(RING).to_crs(EPSG).union_all()
    inring = rasterize([(ring, 1)], out_shape=(h, w), transform=T, dtype="uint8")
    print(
        f"[water] {int(wm.sum()):,} px = {wm.sum() * RES**2 / 1e6:.1f} km² mapped water "
        f"({(wm & inring).sum() * RES**2 / 1e6:.1f} km² inside the ring)"
    )


# ── step 4: coverage of the model's normally-wet area ─────────────────────────────────
def step_coverage():
    import sys

    import rasterio
    import xarray as xr

    sys.path.insert(0, str(REPO))  # run with `python -I` (it reads downloaded data)
    from nj_sfincs import normal_surface as ns

    with xr.open_dataset(TEMPLATE) as ds:
        fx, fy = ds.mesh2d_face_x.values, ds.mesh2d_face_y.values
        m = ds.mask.values
        z = ds.z.values
        lev = ds.level.values.astype(int)
        fn = ds.mesh2d_face_nodes.values
        nx, ny = ds.mesh2d_node_x.values, ds.mesh2d_node_y.values
    # quadtree faces are squares: side = level-1 side / 2**(level-1); level-1 side from
    # the first two nodes of one level-1 face (start index taken from the node count)
    k = int(np.flatnonzero(lev == 1)[0])
    n0, n1 = (fn[k, :2] - (1 if np.nanmin(fn) >= 1 else 0)).astype(int)
    dx1 = float(np.hypot(nx[n1] - nx[n0], ny[n1] - ny[n0]))
    area = (dx1 / 2.0 ** (lev - 1)) ** 2
    print(f"[coverage] level-1 face {dx1:.1f} m")
    act = m > 0
    W = ns.usual_water_surface(fx, fy, "v4_refreeze")
    pool = ns.sample_raster(ns.pool_path("v4_refreeze"), fx, fy)
    srcv = ns.sample_raster(OUT / "mhhw_source_v4.tif", fx, fy)
    with rasterio.open(OUT / "mhhw_source_v4.tif") as d:
        nd = d.nodata
    srcv[srcv == nd] = 0
    srcv = np.nan_to_num(srcv)
    # lake membership (any class) on the 25 m lake-id grid is the pool raster OR a
    # tidal lake: reuse the CSV's tidal flag via the MHHW source (a tidal lake has VDatum)
    wet_bed = act & (z < 0.0)
    wet = wet_bed | (act & np.isfinite(pool))
    a = area
    out = {}

    def share(sel):
        return float(a[sel].sum() / a[wet].sum())

    out["active_km2"] = float(a[act].sum() / 1e6)
    out["wet_km2"] = float(a[wet].sum() / 1e6)
    out["wet_definition"] = (
        "active face with template z < 0 m NAVD88, or in a lake pool"
    )
    out["wet_share_vdatum"] = share(
        wet & (srcv >= 1) & (srcv <= 16) & ~np.isfinite(pool)
    )
    out["wet_share_river_fill"] = share(wet & (srcv == 21) & ~np.isfinite(pool))
    out["wet_share_extension"] = share(wet & (srcv == 20) & ~np.isfinite(pool))
    out["wet_share_pool"] = share(wet & np.isfinite(pool))
    out["wet_share_W"] = share(wet & np.isfinite(W))
    out["wet_share_none"] = share(wet & ~np.isfinite(W))
    out["active_share_W"] = float(a[act & np.isfinite(W)].sum() / a[act].sum())
    # land below MHHW inside the extension band (diked / protected ground the
    # nearest-neighbour fill calls normally wet)
    low_ext = act & (srcv == 20) & np.isfinite(W) & (z < W - 0.1) & ~np.isfinite(pool)
    out["ext_faces_bed_below_W_km2"] = float(a[low_ext].sum() / 1e6)
    miss = wet & ~np.isfinite(W)
    out["wet_none_km2"] = float(a[miss].sum() / 1e6)
    # where the misses are (5 km bins)
    if miss.any():
        kx = (fx[miss] // 5000).astype(int)
        ky = (fy[miss] // 5000).astype(int)
        key = kx * 10000 + ky
        u, inv = np.unique(key, return_inverse=True)
        s = np.bincount(inv, weights=a[miss])
        top = np.argsort(-s)[:12]
        from pyproj import Transformer

        tr = Transformer.from_crs(EPSG, 4326, always_xy=True)
        out["wet_none_top_5km_bins"] = []
        for t in top:
            cx, cy = (u[t] // 10000) * 5000 + 2500, (u[t] % 10000) * 5000 + 2500
            lo, la = tr.transform(cx, cy)
            out["wet_none_top_5km_bins"].append(
                dict(lon=round(lo, 3), lat=round(la, 3), km2=round(s[t] / 1e6, 3))
            )
    (OUT / "coverage_v4.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--step",
        choices=("stations", "mhhw", "lakes", "water", "coverage", "all"),
        default="all",
    )
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    grids = load_grids() if a.step in ("stations", "mhhw", "all") else None
    if a.step in ("stations", "all"):
        step_stations(grids)
    mh = src = T = None
    if a.step in ("mhhw", "all"):
        mh, src, T = step_mhhw(grids)
    if a.step in ("lakes", "all"):
        step_lakes(mh, src, T)
    if a.step in ("water", "all"):
        step_water()
    if a.step in ("coverage", "all"):
        step_coverage()


if __name__ == "__main__":
    main()
