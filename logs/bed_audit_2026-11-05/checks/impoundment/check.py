"""Bed audit check `impoundment` (2026-11-05; logs/bed_audit_2026-11-05/SCHEMA.md, README.md here).

Does the bed treat impounded (non-tidal) water as tidal, or tidal water as cut off?

  python check.py --bed <subgrid dir> --label <bed_label> [--overlay KEY ...] [--overlay-min KEY ...]
                  [--overlay-min-v11npz] --out ../../out/<bed_label>/impoundment.csv

Authoritative layers (fetch.py): NWI polygons (Cowardin code: system, class, WATER REGIME, special
modifier 'h' diked / impounded) and NID dams; lake pools from the hydro-flattened lidar (NJ 10 ft DEM,
3DEP 1/3"); MHHW from the domain's VDatum surface (data/normal_surface_v4/).

Rule, per water body (details + thresholds in README.md):
  LINK = the lowest still-water level at which the bed joins the polygon to ocean-connected tidal water
         (minimax over the bed, 4-connected, native 3.125 m pixels, inside a window around the polygon;
         bisection to 0.02 m). Tidal "seeds" = cells with bed <= -0.5 m in a component of
         {coarse bed <= -0.5 m} of area >= 20 km^2 (ocean, bays, tidal rivers), coarse = 4x4 block min.
  A) impounded set: NWI lacustrine (L*) polygons, and NWI palustrine open water (PUB/PAB/PUS) that is
     >= 1 ha, or carries 'h', or lies within 300 m of an NID dam; NON-tidal water regime; POOL (lidar
     water surface, p50 inside the polygon) > MHHW + 0.15 m.
       LINK < POOL - 0.30            -> impounded_lake_tidal_link   (high if LINK < MHHW, else medium)
       bed p50 < POOL - 1.0, bed flat (IQR < 0.2 m)
                                     -> flat_fill_below_pool        (medium with a tidal link, else low)
  B) tidal set: NWI E1UB / E1AB / R1* (tidal water regimes), >= 0.5 ha:
       LINK > MHHW + 0.10            -> tidal_water_cut_off         (high if > MHHW + 0.3 and >= 1 ha)
The window is the polygon's box + 1.5 km (3.5 km if no seed inside). A path that leaves the window and
comes back is not seen, so LINK can only read HIGH: (A) can miss a leak, never invent one; (B) can
invent a cut-off — every (B) exception is re-tested with the 3.5 km window before it is written.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio import features
from rasterio.enums import Resampling
from rasterio.warp import reproject
from rasterio.windows import Window
from scipy import ndimage
from shapely.geometry import Point, Polygon, shape
from shapely.ops import transform as stransform
from pyproj import Transformer

REPO = Path("/cache/home/tpj8/nj_bight_sfincs")
RAW = Path("/scratch/tpj8/nj_bight_sfincs_data/audit/impoundment")
TO_UTM = Transformer.from_crs(4326, 32618, always_xy=True).transform
TO_LL = Transformer.from_crs(32618, 4326, always_xy=True).transform
SEED_LEVEL = -0.5
SEED_MIN_KM2 = 20.0
BLOCK = 4
SURGE_CAP = 4.0  # m NAVD88 ~ the highest Sandy water level in the domain (Raritan Bay / Arthur Kill)
B_MARGIN = 0.5  # set B flags a tidal polygon joined to the sea only above MHHW + this
TIDAL_REGIMES = set("LMNPRSTV")
NONTIDAL_REGIMES = set("ABCDEFGHJKWYZU")
sys.path.insert(0, str(REPO / "logs/decks_2026-11-04"))
sys.path.insert(0, str(REPO / "logs/modern_decks_2026-11-04"))


# --------------------------------------------------------------------------- inputs
def catalog_uri(key):
    """data/<uri> for a catalog key (plain text parse; the catalog is not imported)."""
    txt = (REPO / "data/data_catalog.yml").read_text()
    m = re.search(rf"^{re.escape(key)}:\n(?:  .*\n)*?  uri: (\S+)", txt, re.M)
    if not m:
        raise SystemExit(f"catalog key {key!r} not found")
    return REPO / "data" / m.group(1)


def cowardin(code):
    """(system, regime, modifiers) from an NWI ATTRIBUTE such as 'L1UBHh', 'PEM1/UBF', 'R1UBV'."""
    code = code or ""
    m = re.match(r"^(L[12]|P|E[12]|R[1-5]|M[12])", code)
    system = m.group(1) if m else ""
    core = re.sub(r"[a-z0-9]+$", "", code)  # strip trailing modifiers
    mods = code[len(core):]
    up = [c for c in core[len(system):] if c.isupper()]
    regime = up[-1] if up else ""
    return system, regime, re.sub(r"\d", "", mods)


def load_nwi():
    rows = []
    for f in sorted(RAW.glob("nwi_*.geojson")):
        d = json.loads(f.read_text())
        for ft in d["features"]:
            p = ft["properties"]
            if not ft.get("geometry"):
                continue
            g = shape(ft["geometry"])
            if g.is_empty:
                continue
            sysm, reg, mods = cowardin(p.get("ATTRIBUTE"))
            rows.append(dict(file=f.stem, code=p.get("ATTRIBUTE"), wtype=p.get("WETLAND_TYPE"),
                             acres=p.get("ACRES") or 0.0, system=sysm, regime=reg, mods=mods, geom_ll=g))
    df = pd.DataFrame(rows)
    df["geom"] = [stransform(TO_UTM, g).buffer(0) for g in df.geom_ll]
    df["area_m2"] = [g.area for g in df.geom]
    return df


def load_nid():
    d = json.loads((RAW / "nid_dams.geojson").read_text())
    r = []
    for ft in d["features"]:
        p = ft["properties"]
        lon, lat = p.get("LONGITUDE"), p.get("LATITUDE")
        if lon is None or lat is None:
            continue
        x, y = TO_UTM(lon, lat)
        r.append(dict(nidid=p.get("NIDID"), name=p.get("NAME"), height_ft=p.get("NID_HEIGHT"),
                      dtype=p.get("PRIMARY_DAM_TYPE"), purpose=p.get("PRIMARY_PURPOSE"), x=x, y=y))
    return pd.DataFrame(r)


def keep(df, mask):
    """df rows where mask (a list of bools) holds; safe on an empty frame."""
    return df.iloc[np.asarray(list(mask), bool)] if len(df) else df


def load_ring():
    t = pd.read_csv(REPO / "data/v4_design/region_v4_vertices.csv", comment="#")
    return Polygon([TO_UTM(a, b) for a, b in zip(t.lon, t.lat)]).buffer(0)


# --------------------------------------------------------------------------- the bed
class BedReader:
    """Native-resolution windows of a (rotated) merged bed, with optional overlays applied the way the
    subgrid builder applies them: `overlay` replaces where valid, `overlay_min` takes the min."""

    def __init__(self, bed_dir, overlays=(), overlays_min=(), v11npz=False):
        self.src = rasterio.open(Path(bed_dir) / "subgrid/dep_subgrid_merged.tif")
        self.inv = ~self.src.transform
        self.ov = [rasterio.open(catalog_uri(k)) for k in overlays]
        self.ovm = [rasterio.open(catalog_uri(k)) for k in overlays_min]
        self.v11 = None
        if v11npz:
            from common_m import Overlay
            self.v11 = Overlay()

    def window_for(self, x0, y0, x1, y1):
        cs, rs = self.inv * (np.array([x0, x1, x0, x1]), np.array([y0, y0, y1, y1]))
        c0, c1 = int(max(np.floor(cs.min()), 0)), int(min(np.ceil(cs.max()), self.src.width))
        r0, r1 = int(max(np.floor(rs.min()), 0)), int(min(np.ceil(rs.max()), self.src.height))
        if c1 <= c0 or r1 <= r0:
            return None
        return Window(c0, r0, c1 - c0, r1 - r0)

    def read(self, win):
        a = self.src.read(1, window=win).astype("float32")
        tr = self.src.window_transform(win)
        for o, how in [(o, "rep") for o in self.ov] + [(o, "min") for o in self.ovm]:
            dst = np.full(a.shape, np.nan, "float32")
            reproject(source=rasterio.band(o, 1), destination=dst, dst_transform=tr, dst_crs=self.src.crs,
                      src_nodata=o.nodata, dst_nodata=np.nan,
                      resampling=Resampling.nearest if how == "rep" else Resampling.min)
            ok = np.isfinite(dst)
            a[ok] = dst[ok] if how == "rep" else np.fmin(a[ok], dst[ok])
        if self.v11 is not None:
            rr, cc = np.mgrid[0:a.shape[0], 0:a.shape[1]]
            xs, ys = tr * (cc + 0.5, rr + 0.5)
            o = self.v11.sample(xs.ravel(), ys.ravel()).reshape(a.shape)
            ok = np.isfinite(o)
            a[ok] = np.fmin(a[ok], o[ok])
        return a, tr


def build_seeds(bed: BedReader, cache: Path):
    """Coarse (BLOCK x BLOCK min, native frame) mask of ocean-connected tidal water at SEED_LEVEL."""
    if cache.exists():
        z = np.load(cache)
        return np.unpackbits(z["bits"])[: int(z["n"])].reshape(tuple(z["shape"])).astype(bool)
    H, W = bed.src.height // BLOCK, bed.src.width // BLOCK
    coarse = np.full((H, W), np.nan, "float32")
    step = 256
    for r in range(0, H, step):
        h = min(step, H - r)
        a = bed.src.read(1, window=Window(0, r * BLOCK, W * BLOCK, h * BLOCK)).astype("float32")
        a = a.reshape(h, BLOCK, W, BLOCK)
        with np.errstate(all="ignore"):
            coarse[r:r + h] = np.nanmin(np.nanmin(a, axis=3), axis=1)
    low = np.isfinite(coarse) & (coarse <= SEED_LEVEL)
    lab, n = ndimage.label(low)
    cell_km2 = (bed.src.res[0] * BLOCK) ** 2 / 1e6
    sizes = np.bincount(lab.ravel(), minlength=n + 1) * cell_km2
    keep = np.flatnonzero(sizes >= SEED_MIN_KM2)
    keep = keep[keep > 0]
    seed = np.isin(lab, keep)
    print(f"[seeds] {n} components at <= {SEED_LEVEL} m; kept {len(keep)} >= {SEED_MIN_KM2} km^2 "
          f"({sizes[keep].sum():.0f} km^2)", flush=True)
    bits = np.packbits(seed.ravel())
    np.savez_compressed(cache, bits=bits, n=seed.size, shape=np.array(seed.shape))
    return seed


# --------------------------------------------------------------------------- the link
def link_level(bed, seed, poly, pad, lo=-1.0, hi=6.0, tol=0.02, own_seeds=True):
    """Lowest level joining `poly` to tidal seed water inside the window; returns (link, info).
    own_seeds=False (set A): seed cells inside the polygon or within 30 m of it are dropped — a 12.5 m
    coarse block can merge a deep lake with the tidal river through its dam, so a 'seed' there proves nothing."""
    x0, y0, x1, y1 = poly.bounds
    win = bed.window_for(x0 - pad, y0 - pad, x1 + pad, y1 + pad)
    if win is None:
        return np.nan, dict(why="outside_bed")
    a, tr = bed.read(win)
    # pixel CENTRES inside the polygon shrunk 5 m: an all-touched edge pixel can belong to the creek below
    # the dam (Alloway's first calibration run linked through two such pixels at 0.25 m)
    inner = poly.buffer(-5.0)
    pm = np.zeros(a.shape, bool)
    if not inner.is_empty:
        pm = features.rasterize([(inner, 1)], out_shape=a.shape, transform=tr, fill=0).astype(bool)
    if not pm.any():
        pm = features.rasterize([(poly, 1)], out_shape=a.shape, transform=tr, fill=0).astype(bool)
    pm &= np.isfinite(a)
    if not pm.any():
        return np.nan, dict(why="no_bed_in_polygon")
    r0, c0 = win.row_off, win.col_off
    rr = (np.arange(a.shape[0]) + r0) // BLOCK
    cc = (np.arange(a.shape[1]) + c0) // BLOCK
    rr = np.clip(rr, 0, seed.shape[0] - 1)
    cc = np.clip(cc, 0, seed.shape[1] - 1)
    sd = seed[np.ix_(rr, cc)] & np.isfinite(a) & (a <= SEED_LEVEL)
    if not own_seeds:
        near = features.rasterize([(poly.buffer(30.0), 1)], out_shape=a.shape, transform=tr, fill=0,
                                  all_touched=True).astype(bool)
        sd &= ~near
    info = dict(bed_p50=float(np.nanmedian(a[pm])), bed_iqr=float(np.subtract(*np.nanpercentile(a[pm], [75, 25]))),
                n_seed=int(sd.sum()), win_px=int(a.size))
    if not sd.any():
        return np.nan, dict(info, why="no_seed_in_window")
    if own_seeds and (sd & pm).sum() >= max(20, int(0.02 * pm.sum())):
        return SEED_LEVEL, dict(info, why="seed_in_polygon")
    finite = np.isfinite(a)

    # "joined" = tidal water reaches a real share of the polygon (>= 20 px and >= 2 %), not a sliver: an NWI
    # outline can overlap the dam outlet, and 9 such px at 0 m once tied Alloway's fixed pool to the tide
    need = max(20, int(0.02 * pm.sum()))

    def joined(L):
        lab, _ = ndimage.label(finite & (a <= L))
        s = np.unique(lab[sd & (a <= L)])
        s = s[s > 0]
        if not s.size:
            return False
        return int(np.isin(lab[pm], s).sum()) >= need

    lo = max(lo, float(np.nanmin(a[pm])) - 0.01)
    if joined(lo):
        return lo, dict(info, why="joined_at_lo")
    if not joined(hi):
        return np.inf, dict(info, why=f"not_joined_below_{hi}")
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        if joined(mid):
            hi = mid
        else:
            lo = mid
    return round(hi, 2), dict(info, why="bisect")


# --------------------------------------------------------------------------- context
class Context:
    def __init__(self):
        from nj_sfincs import normal_surface as ns
        with rasterio.open(ns.mhhw_path("v4_refreeze_swz")) as s:
            m = s.read(1).astype("float32")
            self.mtr = s.transform
        bad = ~np.isfinite(m)
        idx = ndimage.distance_transform_edt(bad, return_distances=False, return_indices=True)
        self.mhhw = m[tuple(idx)]  # nearest finite MHHW everywhere (inland lakes take the nearest tide)
        from common import TIERS, Tier
        self.tiers = [Tier(TIERS["nj_10ft_dem_v4"]), Tier(TIERS["dep3_v4"])]
        a = pd.read_csv(REPO / "logs/power_exposure_2026-11-02/plants_exposure.csv",
                        usecols=["name", "klass", "x_utm", "y_utm"]).dropna(subset=["x_utm"])
        self.assets = a
        self._sandy = None

    def mhhw_at(self, x, y):
        c, r = ~self.mtr * (x, y)
        r = int(np.clip(r, 0, self.mhhw.shape[0] - 1))
        c = int(np.clip(c, 0, self.mhhw.shape[1] - 1))
        return float(self.mhhw[r, c])

    def pool(self, poly):
        inner = poly.buffer(-6.0)
        g = inner if (not inner.is_empty and inner.area > 0) else poly
        x0, y0, x1, y1 = g.bounds
        rng = np.random.default_rng(0)
        pts = []
        for _ in range(40):
            xs = rng.uniform(x0, x1, 200)
            ys = rng.uniform(y0, y1, 200)
            pts += [(x, y) for x, y in zip(xs, ys) if g.contains(Point(x, y))]
            if len(pts) >= 120:
                break
        if not pts:
            c = g.representative_point()
            pts = [(c.x, c.y)]
        x, y = np.array(pts[:120]).T
        for t, nm in zip(self.tiers, ("nj_10ft", "3dep")):
            v = t.sample(x, y)
            v = v[np.isfinite(v)]
            if v.size >= max(3, 0.5 * len(x)):
                return float(np.median(v)), float(np.subtract(*np.percentile(v, [90, 10]))), nm
        return np.nan, np.nan, "none"

    def _load_faces(self):
        if self._sandy is None:
            import xarray as xr
            ds = xr.open_dataset(REPO / "experiments/v4_refreeze_swz/p4-premier/sfincs_map.nc")
            nx, ny = ds["mesh2d_node_x"].values, ds["mesh2d_node_y"].values
            fnv = ds["mesh2d_face_nodes"]
            fn = fnv.values.astype("float64")
            fn = np.where(np.isfinite(fn) & (fn >= 0), fn, fn[:, :1]).astype("int64")
            fn -= int(fnv.attrs.get("start_index", 0))
            fx, fy = nx[fn].mean(1), ny[fn].mean(1)
            z = np.nanmax(ds["zsmax"].values, axis=0)
            from scipy.spatial import cKDTree
            ok = np.isfinite(z)  # zsmax is NaN on inactive faces: finite = simulated
            self._sandy = (cKDTree(np.c_[fx[ok], fy[ok]]), z[ok], fx[ok], fy[ok])
        return self._sandy

    def faces_in(self, g):
        """Indices of active (simulated) faces whose centre lies in polygon g."""
        import shapely
        tree, z, fx, fy = self._load_faces()
        c = g.centroid
        x0, y0, x1, y1 = g.bounds
        i = np.asarray(tree.query_ball_point([c.x, c.y], 0.5 * np.hypot(x1 - x0, y1 - y0) + 1.0), int)
        if not i.size:
            return i
        return i[shapely.contains_xy(g, fx[i], fy[i])]

    def in_model(self, g):
        if self.faces_in(g).size:
            return True
        tree, *_ = self._load_faces()
        c = g.representative_point()
        d, _ = tree.query([c.x, c.y])
        return bool(d <= 30.0)

    def sandy(self, g):
        """1.0.0's Sandy peak on the polygon: max zsmax of the active faces inside it, else the nearest
        active face within 200 m."""
        tree, z, fx, fy = self._load_faces()
        i = self.faces_in(g)
        if i.size:
            return float(np.nanmax(z[i]))
        c = g.representative_point()
        d, j = tree.query([c.x, c.y])
        return float(z[j]) if d <= 200.0 else np.nan

    def asset(self, x, y, within=2000.0):
        d = np.hypot(self.assets.x_utm - x, self.assets.y_utm - y)
        i = int(np.argmin(d.values))
        return (self.assets.name.iloc[i], round(float(d.iloc[i]) / 1000, 2)) if d.iloc[i] <= within else ("", np.nan)


# --------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bed", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--overlay", action="append", default=[], help="catalog key applied as a replace (raise) overlay")
    ap.add_argument("--overlay-min", action="append", default=[], help="catalog key applied as :min")
    ap.add_argument("--overlay-min-v11npz", action="store_true", help="v1.1's deck_fix_v4 pixels (common_m.Overlay) as :min")
    ap.add_argument("--out", required=True)
    ap.add_argument("--sets", default="AB", help="A = impounded set, B = tidal set; a run of one set MERGES into --out")
    ap.add_argument("--only", default=None, help="comma list of lon,lat;lon,lat to restrict to (calibration)")
    a = ap.parse_args()

    bed = BedReader(a.bed, a.overlay, a.overlay_min, a.overlay_min_v11npz)
    seed = build_seeds(bed, RAW / f"seeds_{Path(a.bed).name}.npz")
    ring = load_ring()
    nwi = load_nwi()
    nid = load_nid()
    ctx = Context()
    print(f"[inputs] NWI {len(nwi)} polygons, NID {len(nid)} dams", flush=True)

    nwi = nwi[[ring.contains(g.representative_point()) for g in nwi.geom]].copy()
    near_dam = np.zeros(len(nwi), bool)
    if len(nid):
        from shapely.strtree import STRtree
        pts = [Point(x, y) for x, y in zip(nid.x, nid.y)]
        tree = STRtree(pts)
        for k, g in enumerate(nwi.geom):
            near_dam[k] = len(tree.query(g, predicate="dwithin", distance=300.0)) > 0
    nwi["near_dam"] = near_dam
    is_lake = nwi.system.str.startswith("L")
    is_pond = nwi.file.str.startswith("nwi_ponds")
    nontidal = nwi.regime.isin(NONTIDAL_REGIMES)
    impound = nontidal & (is_lake | (is_pond & ((nwi.area_m2 >= 1e4) | nwi.mods.str.contains("h") | nwi.near_dam)))
    # 'h' (diked / impounded) tidal water is cut off BY DESIGN (the bayshore refuge pools): not set B
    tidal = (nwi.file.str.startswith("nwi_tidal") & nwi.regime.isin(TIDAL_REGIMES) & (nwi.area_m2 >= 5e3)
             & ~nwi.mods.str.contains("h"))
    A, B = nwi[impound & (nwi.area_m2 >= 2e3)], nwi[tidal]
    if "A" not in a.sets:
        A = A.iloc[:0]
    if "B" not in a.sets:
        B = B.iloc[:0]
    if a.only:
        pts = [Point(*TO_UTM(*map(float, s.split(",")))) for s in a.only.split(";")]
        A = keep(A, [any(g.distance(p) < 300 for p in pts) for g in A.geom])
        B = keep(B, [any(g.distance(p) < 300 for p in pts) for g in B.geom])
    nA, nB = len(A), len(B)
    A = keep(A, [ctx.in_model(g) for g in A.geom])
    B = keep(B, [ctx.in_model(g) for g in B.geom])
    print(f"[candidates] impounded {len(A)} of {nA}, tidal {len(B)} of {nB} (in ring AND simulated by 1.0.0)", flush=True)

    rows, stats = [], dict(pool_at_tide=0, no_seed=0, passed=0, flagged=0, tidal_ok=0, tidal_flag=0)

    def ctx_row(g):
        c = g.representative_point()
        lon, lat = TO_LL(c.x, c.y)
        nm, km = ctx.asset(c.x, c.y)
        return c, dict(lon=round(lon, 6), lat=round(lat, 6), sandy_peak_m=round(ctx.sandy(g), 2),
                       near_asset=nm, asset_km=km)

    for k, (i, r) in enumerate(A.iterrows()):
        g = r.geom
        c = g.representative_point()
        mh = ctx.mhhw_at(c.x, c.y)
        pool, spread, psrc = ctx.pool(g)
        if not np.isfinite(pool) or pool <= mh + 0.15:
            stats["pool_at_tide"] += 1
            continue
        link, info = link_level(bed, seed, g, 1500.0, hi=pool + 1.0, own_seeds=False)
        if info.get("why") == "no_seed_in_window":
            link, info = link_level(bed, seed, g, 3500.0, hi=pool + 1.0, own_seeds=False)
        if info.get("why") in ("no_seed_in_window", "outside_bed", "no_bed_in_polygon"):
            stats["no_seed"] += 1
            continue
        flags = []
        if np.isfinite(link) and link < pool - 0.30:
            # high: the tide gets in daily; medium: a surge below SURGE_CAP gets in below the pool; low: only a
            # level no storm here reaches would use the bed path
            flags.append(("impounded_lake_tidal_link", "high" if link < mh else ("medium" if link < SURGE_CAP else "low")))
        fill = info["bed_p50"] < pool - 1.0 and info["bed_iqr"] < 0.2
        if fill:
            flags.append(("flat_fill_below_pool", "medium" if flags else "low"))
        if not flags:
            stats["passed"] += 1
            continue
        stats["flagged"] += 1
        dams = []
        for _, d in nid.iterrows():
            if g.distance(Point(d.x, d.y)) <= 500:
                dams.append(f"{d.nidid} {d['name']} ({d.height_ft} ft)")
        _, base = ctx_row(g)
        for kind, sev in flags:
            if kind == "impounded_lake_tidal_link":
                metric, value, expected = "link_to_tide_m", link, pool
                note = (f"NWI {r.code} ({r.wtype}, {r.area_m2 / 1e4:.1f} ha) held at {pool:.2f} m by the {psrc} lidar, "
                        f"but the bed joins it to tidal water at {link:.2f} m (MHHW {mh:.2f})"
                        + (f"; dam: {'; '.join(dams)}" if dams else "; no NID dam within 500 m"))
                fix = f"raise the fill floor upstream of the control to the {pool:.2f} m pool (max(bed, pool)), as alloway_pool_v4"
            else:
                metric, value, expected = "bed_p50_in_pool_m", info["bed_p50"], pool
                note = (f"NWI {r.code}: bed inside is flat at {info['bed_p50']:.2f} m (IQR {info['bed_iqr']:.2f}), "
                        f"{pool - info['bed_p50']:.2f} m under the lidar pool {pool:.2f} m: a fill, fake storage")
                fix = "paint the pool (inland_water rule: bed = surface where no bathymetry)"
            rows.append(dict(check="impoundment", id="nwi_" + hashlib.md5(g.wkb).hexdigest()[:10], **base, severity=sev,
                             kind=kind, metric=metric, value=round(float(value), 2), expected=round(expected, 2),
                             units="m NAVD88", area_m2=round(r.area_m2), source="NWI (USFWS, 2026 service) + NID + NJ 10 ft / 3DEP lidar pool + VDatum MHHW",
                             note=note, fix=fix, mhhw_m=round(mh, 2), pool_m=round(pool, 2), pool_spread_m=round(spread, 2),
                             link_m=link, nwi_code=r.code, why=info.get("why"), dams="; ".join(dams)))
        if (k + 1) % 50 == 0:
            print(f"  A {k + 1}/{len(A)} {stats}", flush=True)

    for k, (i, r) in enumerate(B.iterrows()):
        g = r.geom
        c = g.representative_point()
        mh = ctx.mhhw_at(c.x, c.y)
        link, info = link_level(bed, seed, g, 1500.0, hi=mh + 1.5)
        if info.get("why") in ("no_seed_in_window",) or (np.isfinite(link) and link > mh + B_MARGIN) or link == np.inf:
            link, info = link_level(bed, seed, g, 3500.0, hi=mh + 1.5)
        if link == np.inf or info.get("why") == "no_seed_in_window":
            # a long river can need its mouth: the St Jones R1UBV (70 ha) joins at -0.16 m only with 8 km
            link, info = link_level(bed, seed, g, 8000.0, hi=mh + 1.5)
        if info.get("why") in ("no_seed_in_window", "outside_bed", "no_bed_in_polygon"):
            stats["no_seed"] += 1
            continue
        # MHHW + 0.5 m ~ the spring / perigean high water here: a marsh-platform pond that only the spring
        # tides reach is natural (the first run at MHHW + 0.1 flagged 630 such ponds)
        if not (link > mh + B_MARGIN):
            stats["tidal_ok"] += 1
            continue
        stats["tidal_flag"] += 1
        sev = "high" if (link > mh + 1.0 and r.area_m2 >= 1e4) else "medium"
        _, base = ctx_row(g)
        lk = "> %.2f" % (mh + 1.5) if link == np.inf else f"{link:.2f}"
        rows.append(dict(check="impoundment", id="nwi_" + hashlib.md5(g.wkb).hexdigest()[:10], **base, severity=sev,
                         kind="tidal_water_cut_off", metric="link_to_tide_m",
                         value=(round(float(link), 2) if np.isfinite(link) else 99.0), expected=round(mh, 2),
                         units="m NAVD88", area_m2=round(r.area_m2), source="NWI (USFWS) tidal water regime + VDatum MHHW",
                         note=(f"NWI {r.code} is TIDAL water ({r.area_m2 / 1e4:.1f} ha) but the bed joins it to the sea "
                               f"only at {lk} m, above MHHW {mh:.2f}: a ridge, plug or fill cuts it off"),
                         fix="find the sill on the link path (a deck, a fill, a CUDEM seam) and open it to the channel",
                         mhhw_m=round(mh, 2), pool_m=np.nan, pool_spread_m=np.nan, link_m=link, nwi_code=r.code,
                         why=info.get("why"), dams=""))
        if (k + 1) % 200 == 0:
            print(f"  B {k + 1}/{len(B)} {stats}", flush=True)

    cols = ["check", "id", "lon", "lat", "severity", "kind", "metric", "value", "expected", "units", "area_m2",
            "sandy_peak_m", "near_asset", "asset_km", "source", "note", "fix",
            "mhhw_m", "pool_m", "pool_spread_m", "link_m", "nwi_code", "why", "dams"]
    out = pd.DataFrame(rows, columns=cols)
    sev_rank = {"high": 0, "medium": 1, "low": 2}
    out = out.sort_values(["severity", "area_m2"], key=lambda s: s.map(sev_rank) if s.name == "severity" else -s)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    if a.sets != "AB" and Path(a.out).exists():  # keep the other set's rows from an earlier run
        old = pd.read_csv(a.out)
        mine = {"A": ["impounded_lake_tidal_link", "flat_fill_below_pool"], "B": ["tidal_water_cut_off"]}
        drop = [k for s_ in a.sets for k in mine[s_]]
        out = pd.concat([old[~old.kind.isin(drop)], out], ignore_index=True)
        out = out.sort_values(["severity", "area_m2"], key=lambda s: s.map(sev_rank) if s.name == "severity" else -s)
    out.to_csv(a.out, index=False)
    print(f"[done] {a.label}: {stats}; wrote {len(out)} exceptions -> {a.out}", flush=True)
    print(out.groupby(["kind", "severity"]).size().to_string() if len(out) else "(none)")


if __name__ == "__main__":
    main()
