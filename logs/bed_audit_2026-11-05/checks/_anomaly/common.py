"""Shared machinery for the generic "seems funky" anomaly checks (logs/bed_audit_2026-11-05/SCHEMA.md).

Not a check itself (the runner skips folders starting with "_"). Provides:

* the CONTEXT grid (G25): the 25 m north-up EPSG:32618 grid of data/normal_surface_v4/ (MHHW, its source,
  the mapped-water mask, non-tidal lake pools) plus, rasterised once onto it and cached in
  /scratch/.../audit/_anomaly_context/: Model 1.0.0's ACTIVE faces (msk > 0) and its Sandy peak (zsmax, max
  over the run) from experiments/v4_refreeze_swz/p4-premier/sfincs_map.nc;
* a tiled reader of a bed (`subgrid/dep_subgrid_merged.tif`, ROTATED: every pixel's coordinates go through the
  affine), with optional lower-only / replace overlays applied per pixel, tiles skipped where no active face is;
* a building mask (bed_buildings_v4_cap10, north-up 3.125 m) sampled per pixel;
* exception rows in the schema's columns, with lon/lat, the Sandy peak and the nearest power asset filled in.
"""

from __future__ import annotations

import argparse
import os
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from rasterio.windows import Window

REPO = Path("/cache/home/tpj8/nj_bight_sfincs")
AUD = REPO / "logs/bed_audit_2026-11-05"
SCR = Path("/scratch/tpj8/nj_bight_sfincs_data/audit")
CTX = SCR / "_anomaly_context"
NS = REPO / "data/normal_surface_v4"
PREMIER = REPO / "experiments/v4_refreeze_swz/p4-premier"
DATA = REPO / "data"
BUILDINGS = DATA / "elevation_v4/bed_buildings_v4_cap10.tif"
V11_DECK_NPZ = REPO / "logs/decks_2026-11-04/out/overlay_pixels.npz"  # v1.1's deck_fix_v4 pixel set (1.5 m)
TO_LL = Transformer.from_crs(32618, 4326, always_xy=True).transform
TO_UTM = Transformer.from_crs(4326, 32618, always_xy=True).transform

COLS = ["check", "id", "lon", "lat", "severity", "kind", "metric", "value", "expected", "units", "area_m2",
        "sandy_peak_m", "near_asset", "asset_km", "source", "note", "fix"]
SEV_RANK = {"high": 0, "medium": 1, "low": 2}
TILE = 2048
TIDAL_SRC = set(range(1, 7)) | set(range(11, 17)) | {21}  # mhhw_source_v4: VDatum water (+ edge) and tidal reaches


def ncpu():
    return int(os.environ.get("SLURM_CPUS_PER_TASK") or os.environ.get("AUDIT_CPUS") or 16)


# ----------------------------------------------------------------------------------------------- catalog
@lru_cache(None)
def catalog():
    import yaml  # noqa: PLC0415

    return yaml.safe_load(open(DATA / "data_catalog.yml"))


def cat_path(key):
    return DATA / catalog()[key]["uri"]


# ----------------------------------------------------------------------------------------------- G25 context
G25_REF = NS / "mhhw_navd88_v4.tif"


@lru_cache(None)
def g25_meta():
    with rasterio.open(G25_REF) as s:
        return s.transform, s.height, s.width


def build_context(force=False):
    """Rasterise the premier's active faces and Sandy peak onto G25 (cached as .npy)."""
    import xarray as xr  # noqa: PLC0415
    from rasterio.features import rasterize  # noqa: PLC0415

    CTX.mkdir(parents=True, exist_ok=True)
    tr, h, w = g25_meta()
    if not force and (CTX / "active.npy").exists() and (CTX / "zsmax.npy").exists():
        return
    with xr.open_dataset(PREMIER / "sfincs_map.nc") as ds:
        msk = ds["msk"].values
        fn = ds["mesh2d_face_nodes"].values
        nx, ny = ds["mesh2d_node_x"].values, ds["mesh2d_node_y"].values
        zsmax = ds["zsmax"].max("timemax").values.astype("float32")
    fn0 = (fn - 1 if np.nanmin(fn) == 1 else fn).astype("int64")
    act = np.where(msk > 0)[0]
    xs, ys = nx[fn0[act]], ny[fn0[act]]

    def shapes(vals):
        for i in range(xs.shape[0]):
            ring = [(xs[i, k], ys[i, k]) for k in (0, 1, 2, 3, 0)]
            yield {"type": "Polygon", "coordinates": [ring]}, vals[i]

    a = rasterize(shapes(np.ones(len(act), "uint8")), out_shape=(h, w), transform=tr, fill=0, dtype="uint8")
    z = rasterize(shapes(zsmax[act]), out_shape=(h, w), transform=tr, fill=np.nan, dtype="float32")
    np.save(CTX / "active.npy", a)
    np.save(CTX / "zsmax.npy", z)


@lru_cache(None)
def g25():
    """dict of G25 arrays (memory-mapped where cached): active, zsmax, mhhw, mhhw_src, water, pool."""
    build_context()
    out = {"active": np.load(CTX / "active.npy", mmap_mode="r"), "zsmax": np.load(CTX / "zsmax.npy", mmap_mode="r")}
    for k, f in [("mhhw", "mhhw_navd88_v4.tif"), ("mhhw_src", "mhhw_source_v4.tif"), ("water", "water_mask_v4.tif"),
                 ("pool", "lake_pool_v4.tif")]:
        with rasterio.open(NS / f) as s:
            a = s.read(1)
            if s.nodata is not None and a.dtype.kind == "f":
                a = np.where(a == s.nodata, np.nan, a)
            out[k] = a
    return out


def g25_index(x, y):
    """(row, col, inside) of UTM points on G25."""
    tr, h, w = g25_meta()
    c = np.floor((np.asarray(x) - tr.c) / tr.a).astype(np.int64)
    r = np.floor((np.asarray(y) - tr.f) / tr.e).astype(np.int64)
    ok = (r >= 0) & (r < h) & (c >= 0) & (c < w)
    return np.clip(r, 0, h - 1), np.clip(c, 0, w - 1), ok


def g25_xy(r, c):
    tr, _, _ = g25_meta()
    return tr.c + (np.asarray(c) + 0.5) * tr.a, tr.f + (np.asarray(r) + 0.5) * tr.e


def g25_sample(name, x, y, nan_radius=0):
    """Value of a G25 layer at UTM points; with nan_radius > 0, NaNs are filled from the nearest valid
    cell within that many cells (used for the Sandy peak next to dry ground)."""
    G = g25()[name]
    r, c, ok = g25_index(x, y)
    v = np.asarray(G[r, c], dtype="float64")
    v[~ok] = np.nan
    if nan_radius:
        for i in np.where(np.isnan(v) & ok)[0]:
            r0, r1 = max(r[i] - nan_radius, 0), r[i] + nan_radius + 1
            c0, c1 = max(c[i] - nan_radius, 0), c[i] + nan_radius + 1
            blk = np.asarray(G[r0:r1, c0:c1], dtype="float64")
            if np.isfinite(blk).any():
                rr, cc = np.nonzero(np.isfinite(blk))
                k = np.argmin((rr + r0 - r[i]) ** 2 + (cc + c0 - c[i]) ** 2)
                v[i] = blk[rr[k], cc[k]]
    return v


# ----------------------------------------------------------------------------------------------- rasters by window
class WinSampler:
    """Nearest-pixel sampler for a NORTH-UP raster: reads the window covering a batch of points once."""

    def __init__(self, path):
        self.src = rasterio.open(path)
        self.inv = ~self.src.transform
        self.nd = self.src.nodata

    def sample(self, x, y):
        c, r = self.inv * (np.asarray(x, float), np.asarray(y, float))
        c, r = np.floor(c).astype(np.int64), np.floor(r).astype(np.int64)
        out = np.full(np.shape(x), np.nan, np.float32)
        ok = (c >= 0) & (c < self.src.width) & (r >= 0) & (r < self.src.height)
        if not ok.any():
            return out
        c0, c1, r0, r1 = c[ok].min(), c[ok].max() + 1, r[ok].min(), r[ok].max() + 1
        a = self.src.read(1, window=Window(c0, r0, c1 - c0, r1 - r0)).astype(np.float32)
        if self.nd is not None:
            a[a == self.nd] = np.nan
        a[(a < -1e4) | (a > 1e4)] = np.nan
        out[ok] = a[r[ok] - r0, c[ok] - c0]
        return out


class NpzOverlay:
    """v1.1's deck overlay as a sparse 1.5 m pixel set (s5_overlay.py convention)."""

    def __init__(self, path=V11_DECK_NPZ):
        d = np.load(path)
        k = d["key"].astype(np.int64)
        code = k[:, 0] * 10_000_000 + k[:, 1]
        o = np.argsort(code)
        self.code, self.val = code[o], d["val"][o].astype(np.float32)

    def sample(self, x, y):
        c = np.floor(np.asarray(x) / 1.5).astype(np.int64) * 10_000_000 + np.floor(np.asarray(y) / 1.5).astype(np.int64)
        p = np.clip(np.searchsorted(self.code, c), 0, len(self.code) - 1)
        return np.where(self.code[p] == c, self.val[p], np.nan).astype(np.float32)


def overlay_sampler(spec):
    return NpzOverlay() if spec == "v11_deck_npz" else WinSampler(cat_path(spec) if not Path(spec).exists() else spec)


# ----------------------------------------------------------------------------------------------- the bed, by tiles
class Bed:
    """A subgrid dir's merged bed (rotated), with optional post-hoc overlays:
    overlay_min = lower-only (min), overlay = replace where valid (applied after the mins)."""

    def __init__(self, bed_dir, overlay_min=(), overlay=()):
        self.dir = Path(bed_dir)
        self.path = self.dir / "subgrid/dep_subgrid_merged.tif"
        self.ovmin, self.ov = list(overlay_min), list(overlay)
        with rasterio.open(self.path) as s:
            self.T, self.H, self.W = s.transform, s.height, s.width
        self._src = None
        self._samp = None

    def _open(self):
        if self._src is None:
            self._src = rasterio.open(self.path)
            self._samp = ([overlay_sampler(k) for k in self.ovmin], [overlay_sampler(k) for k in self.ov])
            self._bld = WinSampler(BUILDINGS)

    def tiles(self, halo=0, tile=TILE):
        """Tiles (r0, c0, h, w) that contain at least one active G25 cell."""
        G = g25()["active"]
        out = []
        box = os.environ.get("AUDIT_BBOX")  # "lon0,lat0,lon1,lat1": test on a sub-area only
        if box:
            lo0, la0, lo1, la1 = map(float, box.split(","))
            bx, by = TO_UTM(np.array([lo0, lo1, lo0, lo1]), np.array([la0, la0, la1, la1]))
        for r0 in range(0, self.H, tile):
            for c0 in range(0, self.W, tile):
                h, w = min(tile, self.H - r0), min(tile, self.W - c0)
                cs = np.array([c0, c0 + w, c0, c0 + w]) + 0.5
                rs = np.array([r0, r0, r0 + h, r0 + h]) + 0.5
                x, y = self.T * (cs, rs)
                if box and (x.max() < bx.min() or x.min() > bx.max() or y.max() < by.min() or y.min() > by.max()):
                    continue
                gr, gc, _ = g25_index(x, y)
                if np.asarray(G[gr.min():gr.max() + 1, gc.min():gc.max() + 1]).any():
                    out.append((r0, c0, h, w))
        return out

    def xy(self, r0, c0, h, w):
        rr, cc = np.mgrid[r0:r0 + h, c0:c0 + w]
        return self.T * (cc + 0.5, rr + 0.5)

    def read(self, r0, c0, h, w, halo=0, buildings=False):
        """z (float32, NaN = nodata) for the tile + halo (clipped at the raster edge), its (R0, C0) origin,
        and optionally the building mask on the same pixels."""
        self._open()
        R0, C0 = max(r0 - halo, 0), max(c0 - halo, 0)
        R1, C1 = min(r0 + h + halo, self.H), min(c0 + w + halo, self.W)
        z = self._src.read(1, window=Window(C0, R0, C1 - C0, R1 - R0)).astype(np.float32)
        z[(z < -1e4) | (z > 1e4)] = np.nan
        X = Y = None
        if self._samp[0] or self._samp[1] or buildings:
            X, Y = self.xy(R0, C0, R1 - R0, C1 - C0)
        for s in self._samp[0]:
            o = s.sample(X, Y)
            z = np.where(np.isfinite(o), np.fmin(z, o), z)
        for s in self._samp[1]:
            o = s.sample(X, Y)
            z = np.where(np.isfinite(o), o, z)
        b = None
        if buildings:
            b = np.isfinite(self._bld.sample(X, Y))
        return z, R0, C0, b

    def pix_xy(self, r, c):
        return self.T * (np.asarray(c) + 0.5, np.asarray(r) + 0.5)


# ----------------------------------------------------------------------------------------------- rows
@lru_cache(None)
def _assets():
    import geopandas as gpd  # noqa: PLC0415

    rows = []
    for f, kind in [("substation_polygons.geojson", "substation"), ("plant_polygons.geojson", "plant")]:
        g = gpd.read_file(DATA / "power_infra" / f)
        x, y = TO_UTM(g["lon"].values.astype(float), g["lat"].values.astype(float))
        nm = g["name"].fillna("").astype(str).values
        rows.append(pd.DataFrame({"x": x, "y": y, "name": [n if n else f"({kind})" for n in nm]}))
    a = pd.concat(rows, ignore_index=True)
    from scipy.spatial import cKDTree  # noqa: PLC0415

    return cKDTree(a[["x", "y"]].values), a["name"].values


def finish(df, check, source):
    """Fill lon/lat, Sandy peak, nearest asset; order columns; df needs x, y (UTM) + the check's fields."""
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=COLS)
    df = df.copy()
    df["check"] = check
    df["source"] = source
    lon, lat = TO_LL(df["x"].values, df["y"].values)
    df["lon"], df["lat"] = np.round(lon, 6), np.round(lat, 6)
    if "sandy_peak_m" not in df:
        df["sandy_peak_m"] = np.round(g25_sample("zsmax", df["x"].values, df["y"].values, nan_radius=4), 2)
    tree, names = _assets()
    d, i = tree.query(df[["x", "y"]].values)
    near = d <= 2000
    df["near_asset"] = np.where(near, names[i], "")
    df["asset_km"] = np.where(near, np.round(d / 1000, 2), np.nan)
    for c in COLS:
        if c not in df:
            df[c] = ""
    return df[COLS]


def parse_args(doc, extra=None):
    ap = argparse.ArgumentParser(description=doc.strip().splitlines()[0])
    ap.add_argument("--bed", required=True, type=Path)
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--overlay-min", action="append", default=[], help="catalog key, file, or v11_deck_npz")
    ap.add_argument("--overlay", action="append", default=[], help="catalog key / file, replaces where valid")
    ap.add_argument("--cpus", type=int, default=ncpu())
    if extra:
        extra(ap)
    a = ap.parse_args()
    if a.out is None:
        a.out = AUD / "out" / a.label / f"{Path(sys.argv[0]).resolve().parent.name}.csv"
    a.out.parent.mkdir(parents=True, exist_ok=True)
    return a


def write(df, out):
    tmp = Path(str(out) + ".tmp")
    df.to_csv(tmp, index=False)
    tmp.replace(out)
    sev = df["severity"].value_counts().to_dict() if len(df) else {}
    print(f"wrote {out}: {len(df)} exceptions {sev}")


def components_2d(mask, structure8=True):
    from scipy import ndimage  # noqa: PLC0415

    st = np.ones((3, 3), bool) if structure8 else None
    return ndimage.label(mask, structure=st)


# ----------------------------------------------------------------------------------------------- parallel tile pass
_W = {}


def _init(bed_args, fn):
    _W["bed"] = Bed(*bed_args)
    _W["fn"] = fn


def _call(t):
    return _W["fn"](_W["bed"], t)


def run_tiles(args, fn, tiles=None, extra_beds=()):
    """fn(bed, (r0, c0, h, w)) -> result, over every active tile, in a process pool. Returns the list."""
    import multiprocessing as mp  # noqa: PLC0415
    import time  # noqa: PLC0415

    bed_args = (args.bed, tuple(args.overlay_min), tuple(args.overlay))
    if tiles is None:
        tiles = Bed(*bed_args).tiles()
    t0 = time.time()
    ctx = mp.get_context("fork")
    with ctx.Pool(args.cpus, initializer=_init, initargs=(bed_args, fn)) as pool:
        res = []
        for i, r in enumerate(pool.imap_unordered(_call, tiles, chunksize=1)):
            res.append(r)
            if (i + 1) % 100 == 0:
                print(f"  {i + 1}/{len(tiles)} tiles, {time.time() - t0:.0f} s", flush=True)
    print(f"  {len(tiles)} tiles in {time.time() - t0:.0f} s", flush=True)
    return res


def bed_label_source(args):
    s = f"bed {args.bed.name}"
    if args.overlay_min:
        s += " + min(" + ", ".join(args.overlay_min) + ")"
    if args.overlay:
        s += " + overlay(" + ", ".join(args.overlay) + ")"
    return s


# ----------------------------------------------------------------------------------------------- bed means on G25
def _mean_fn(bed, t):
    r0, c0, h, w = t
    z, _, _, _ = bed.read(r0, c0, h, w)
    X, Y = bed.xy(r0, c0, h, w)
    gr, gc, ok = g25_index(X, Y)
    _, _, W25 = g25_meta()
    v = ok & np.isfinite(z)
    if not v.any():
        return None
    u, inv = np.unique((gr * W25 + gc)[v], return_inverse=True)
    return u, np.bincount(inv), np.bincount(inv, weights=z[v])


def g25_bed_mean(args):
    """Mean bed per G25 cell (NaN where no pixel)."""
    _, H, W = g25_meta()
    n = np.zeros(H * W, np.int32)
    s = np.zeros(H * W, np.float64)
    for r in run_tiles(args, _mean_fn):
        if r is None:
            continue
        u, c, sm = r
        np.add.at(n, u, c)
        np.add.at(s, u, sm)
    return np.where(n > 0, s / np.maximum(n, 1), np.nan).reshape(H, W)


def tier(key):
    p = CTX / "tiers" / f"{key}.tif"
    if not p.exists():
        return None
    with rasterio.open(p) as s:
        a = s.read(1).astype("float32")
        if key == "modern_land_2026":
            a = np.where(a > 0, a, np.nan)
        return a
