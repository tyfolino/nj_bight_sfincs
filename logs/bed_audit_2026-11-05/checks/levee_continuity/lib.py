"""levee_continuity helpers (2026-11-06). Read-only on every input.

Two door levels per NLD leveed area, compared:

* MESH door: the lowest still-water level at which any face of the leveed area (centre inside the NLD polygon shrunk
  20 m) joins the open boundary (mask == 2) on the flow mesh, with every link passable above its threshold:
  `uv_zmin`, or the weir crest where the engine KEEPS a weir on that link (`weir_on_mesh.snap`, crest > uv_zmin).
  Computed for ALL faces at once as a minimax path value: the maximum edge on the minimum spanning tree path from a
  super-source tied to every boundary face. The link that sets it (the "door") is tracked along the tree.
* PIXEL door ("what the ground + the levee allow"): the same on the bed's own 3.12 m pixel raster (the rotated
  `dep_subgrid_merged.tif`, read through the affine), with the NLD routes, floodwalls and closures burned in at their
  NLD Z (US ft NAVD88 x 1200/3937; Z <= 0.5 ft = unknown, not burned), 4-connected priority flood from seeds = pixels
  <= -0.5 m whose nearest mesh face reaches the boundary below 0.0 m on the bed alone (tidal water). Window = the
  leveed area's bounding box + 2 km (water routing round the window is not seen; see README).

A levee works in the model only through a weir (walls_inventory_2026-11-04 #1: the bed never carries a crest). The check
flags a leveed area whose MESH door sits more than TOL below min(PIXEL door, 1.0.0's Sandy level there).
"""

from __future__ import annotations

import heapq  # noqa: F401  (used inside numba)
import sys
from pathlib import Path

import numpy as np

REPO = Path("/cache/home/tpj8/nj_bight_sfincs")
sys.path.insert(0, str(REPO / "logs/refreeze_2026-10-06/structures"))
from weir_on_mesh import load_mesh, read_weir, snap, uv_links  # noqa: E402

FT = 1200.0 / 3937.0
GPKG = REPO / "logs/walls_inventory_2026-11-04/walls_inventory.gpkg"
RANKED = REPO / "logs/walls_inventory_2026-11-04/nld_ranked.csv"
TOL = 0.20          # m: the 2012 / 2026 hand passes matched mesh to lidar within 0.15-0.16 m
SHRINK = 20.0       # m: as the hand passes
MARGIN = 2000.0     # m around the leveed area for the pixel window
SEED_Z = -0.5       # m NAVD88: pixel seeds at or below this ...
SEED_LEVEL = 0.0    # ... whose nearest face reaches the boundary below this on the bed alone
Q = 0.02            # the door = the level at which 2 % of the leveed area (shrunk) has joined open water: a stray
                    # creek / toe face the NLD polygon takes in (Keansburg's creek mouth) is not the door


# ---------------------------------------------------------------- mesh
class Mesh:
    def __init__(self, bed_dir):
        g, uv_zmin, z_zmin = load_mesh(str(bed_dir))
        self.fx = np.asarray(g["mesh2d_face_x"], "f8")
        self.fy = np.asarray(g["mesh2d_face_y"], "f8")
        self.mask = np.asarray(g["mask"])
        self.active = self.mask > 0
        nm, nmu, _ = uv_links(g)
        assert nm.size == uv_zmin.size, (nm.size, uv_zmin.size)
        self.nm, self.nmu, self.uv_zmin, self.z_zmin = nm, nmu, uv_zmin, z_zmin
        self.ok = self.active[nm] & self.active[nmu] & np.isfinite(uv_zmin)
        from scipy.spatial import cKDTree
        self.tree = cKDTree(np.c_[self.fx, self.fy])
        d, _ = self.tree.query(np.c_[self.fx, self.fy], k=2)
        self.area = d[:, 1] ** 2          # face area ~ spacing^2 (quadtree cells are square)

    def snap_weir(self, path):
        """{link: crest} the engine keeps, {link: crest} it crosses, and per-polyline rows (name, rows)."""
        kept, hit, polys = {}, {}, []
        if path is None:
            return kept, hit, polys
        mx, my = 0.5 * (self.fx[self.nm] + self.fx[self.nmu]), 0.5 * (self.fy[self.nm] + self.fy[self.nmu])
        for name, rows in read_weir(path):
            polys.append((name, rows))
            x0, x1 = rows[:, 0].min() - 600, rows[:, 0].max() + 600
            y0, y1 = rows[:, 1].min() - 600, rows[:, 1].max() + 600
            idx = np.where(self.ok & (mx > x0) & (mx < x1) & (my > y0) & (my < y1))[0]
            h, k = snap(rows, self.fx, self.fy, self.active, self.nm[idx], self.nmu[idx], self.uv_zmin[idx])
            for i, c in h.items():
                hit[int(idx[i])] = max(hit.get(int(idx[i]), -9999.0), c)
            for i, c in k.items():
                kept[int(idx[i])] = max(kept.get(int(idx[i]), -9999.0), c)
        return kept, hit, polys

    def thresholds(self, kept):
        thr = self.uv_zmin.copy()
        for i, c in kept.items():
            thr[i] = c
        return thr

    def minimax(self, thr):
        """level[f] = minimax still-water level at which face f joins the open boundary; door[f] = the link that sets it."""
        from scipy.sparse import coo_matrix
        from scipy.sparse.csgraph import breadth_first_order, minimum_spanning_tree
        n = self.fx.size
        sel = np.where(self.ok)[0]
        a, b = np.minimum(self.nm[sel], self.nmu[sel]), np.maximum(self.nm[sel], self.nmu[sel])
        w = thr[sel] + 200.0
        key = a.astype(np.int64) * (n + 1) + b
        o = np.lexsort((w, key))
        key, a, b, w, lid = key[o], a[o], b[o], w[o], sel[o]
        first = np.r_[True, key[1:] != key[:-1]]               # keep the cheapest link per face pair
        key, a, b, w, lid = key[first], a[first], b[first], w[first], lid[first]
        S = n
        bnd = np.where(self.mask == 2)[0]
        A = np.r_[a, np.full(bnd.size, S)]
        B = np.r_[b, bnd]
        W = np.r_[w, np.full(bnd.size, 1e-3)]
        G = coo_matrix((W, (A, B)), shape=(n + 1, n + 1)).tocsr()
        T = minimum_spanning_tree(G).tocoo()
        ta, tb, tw = T.row.astype(np.int64), T.col.astype(np.int64), T.data
        # lookup (parent, child) -> (weight, link id): both directions
        lk_key = np.minimum(ta, tb) * (n + 1) + np.maximum(ta, tb)
        lk_w = tw
        # map tree edges back to the original link id (super-source edges -> -1)
        pos = np.searchsorted(key, lk_key)
        pos = np.clip(pos, 0, key.size - 1)
        lk_lid = np.where(key[pos] == lk_key, lid[pos], -1)
        order, pred = breadth_first_order(T + T.T, S, directed=False, return_predecessors=True)
        child = order[1:]
        par = pred[child].astype(np.int64)
        ck = np.minimum(par, child) * (n + 1) + np.maximum(par, child)
        so = np.argsort(lk_key)
        p2 = so[np.searchsorted(lk_key[so], ck)]
        ew, el = lk_w[p2] - 200.0, lk_lid[p2]
        level = np.full(n + 1, np.inf)
        door = np.full(n + 1, -1, np.int64)
        level[S] = -1e9
        _propagate(order[1:].astype(np.int64), par, ew, el, level, door)
        return level[:n], door[:n]


def _propagate(child, par, ew, el, level, door):
    try:
        from numba import njit
    except ImportError:  # pragma: no cover
        njit = None
    if njit is not None:
        _prop_nb(child, par, ew, el, level, door)
    else:
        for k in range(child.size):
            v, p = child[k], par[k]
            if level[p] >= ew[k]:
                level[v], door[v] = level[p], door[p]
            else:
                level[v], door[v] = ew[k], el[k]


try:
    from numba import njit as _nj

    @_nj(cache=False)
    def _prop_nb(child, par, ew, el, level, door):
        for k in range(child.size):
            v = child[k]
            p = par[k]
            if level[p] >= ew[k]:
                level[v] = level[p]
                door[v] = door[p]
            else:
                level[v] = ew[k]
                door[v] = el[k]

    @_nj(cache=False)
    def priority_flood(elev, seeds):
        """4-connected minimax flood from the seed pixels; elev NaN = wall."""
        ny, nx = elev.shape
        F = np.full((ny, nx), np.inf)
        h = [(np.inf, np.int64(0))]
        h.pop()
        for i in range(ny):
            for j in range(nx):
                if seeds[i, j] and np.isfinite(elev[i, j]):
                    F[i, j] = elev[i, j]
                    heapq.heappush(h, (elev[i, j], np.int64(i * nx + j)))
        while len(h) > 0:
            lv, k = heapq.heappop(h)
            i = k // nx
            j = k - i * nx
            if lv > F[i, j]:
                continue
            for q in range(4):
                a = i + (1 if q == 0 else (-1 if q == 1 else 0))
                b = j + (1 if q == 2 else (-1 if q == 3 else 0))
                if a < 0 or a >= ny or b < 0 or b >= nx:
                    continue
                e = elev[a, b]
                if not np.isfinite(e):
                    continue
                nl = lv if lv > e else e
                if nl < F[a, b]:
                    F[a, b] = nl
                    heapq.heappush(h, (nl, np.int64(a * nx + b)))
        return F
except ImportError:  # pragma: no cover
    priority_flood = None


# ---------------------------------------------------------------- NLD
def load_nld():
    import geopandas as gpd
    out = {}
    for lyr in ("nld_routes", "nld_floodwalls", "nld_closures", "nld_leveed_areas"):
        out[lyr] = gpd.read_file(GPKG, layer=lyr).to_crs(32618)
    r = out["nld_routes"]
    r["sid"] = r["system_id"].astype(str)
    for k in ("nld_floodwalls", "nld_closures", "nld_leveed_areas"):
        out[k]["sid"] = out[k]["SYSTEM_ID"].astype(str)
    import pandas as pd
    rk = pd.read_csv(RANKED, dtype={"system_id": str})
    out["ranked"] = rk.set_index("system_id")
    return out


def lines_xyz(geom, fill=True):
    """UTM (x, y, z_m) arrays per part, Z converted from US ft; unknown (<= 0.5 ft) -> NaN, or (fill) interpolated
    along the part from its known vertices."""
    parts = list(geom.geoms) if geom.geom_type.startswith("Multi") else [geom]
    out = []
    for p in parts:
        c = np.asarray(p.coords, "f8")
        if c.shape[1] < 3:
            continue
        z = np.where(c[:, 2] > 0.5, c[:, 2] * FT, np.nan)
        if fill and np.isfinite(z).any() and not np.isfinite(z).all():
            # unknown vertices (often the gates / closures the route runs across) take the crest interpolated along
            # the line from the known ones: the system as designed, gates CLOSED (the 11-05 pass, G-1 (a))
            s = np.r_[0.0, np.cumsum(np.hypot(np.diff(c[:, 0]), np.diff(c[:, 1])))]
            k = np.isfinite(z)
            z = np.interp(s, s[k], z[k])
        out.append(np.c_[c[:, 0], c[:, 1], z])
    return out


# ---------------------------------------------------------------- pixel bed
class PixelBed:
    def __init__(self, bed_dir):
        import rasterio
        p = Path(bed_dir)
        self.path = p if p.suffix == ".tif" else p / "subgrid/dep_subgrid_merged.tif"
        self.src = rasterio.open(self.path)
        assert self.src.crs.to_epsg() == 32618, self.src.crs
        self.T = self.src.transform
        self.inv = ~self.T

    def window(self, x0, y0, x1, y1):
        from rasterio.windows import Window
        cs, rs = self.inv * (np.array([x0, x1, x0, x1]), np.array([y0, y0, y1, y1]))
        c0, c1 = int(max(0, np.floor(cs.min()))), int(min(self.src.width, np.ceil(cs.max())))
        r0, r1 = int(max(0, np.floor(rs.min()))), int(min(self.src.height, np.ceil(rs.max())))
        w = Window(c0, r0, c1 - c0, r1 - r0)
        a = self.src.read(1, window=w).astype("f8")       # no boundless read on a rotated raster (CLAUDE.md §5)
        a[(a < -1000) | (a > 1000)] = np.nan
        return a, self.src.window_transform(w)


def burn(a, t, lines):
    b = a.copy()
    inv = ~t
    for L in lines:
        for i in range(len(L) - 1):
            if not (np.isfinite(L[i, 2]) and np.isfinite(L[i + 1, 2])):
                continue
            n = max(2, int(np.hypot(*(L[i + 1, :2] - L[i, :2])) / 0.5) + 1)
            f = np.linspace(0, 1, n)
            x = L[i, 0] + f * (L[i + 1, 0] - L[i, 0])
            y = L[i, 1] + f * (L[i + 1, 1] - L[i, 1])
            z = L[i, 2] + f * (L[i + 1, 2] - L[i, 2])
            c, r = inv * (x, y)
            r, c = np.floor(r).astype(int), np.floor(c).astype(int)
            ok = (r >= 0) & (r < b.shape[0]) & (c >= 0) & (c < b.shape[1])
            r, c, z = r[ok], c[ok], z[ok]
            cur = b[r, c]
            b[r, c] = np.where(np.isnan(cur), z, np.maximum(cur, z))
            # 8-connected wall: also the pixel to the right, so a diagonal line holds against a 4-connected flood
            c2 = np.clip(c + 1, 0, b.shape[1] - 1)
            cur2 = b[r, c2]
            b[r, c2] = np.where(np.isnan(cur2), z, np.maximum(cur2, z))
    return b


def pixel_centres(shape, t):
    rr, cc = np.mgrid[0:shape[0], 0:shape[1]]
    x, y = t * (cc + 0.5, rr + 0.5)
    return x, y


def wquantile(v, w, q):
    o = np.argsort(v)
    c = np.cumsum(w[o]) / w.sum()
    k = int(np.searchsorted(c, q))
    return float(v[o][min(k, v.size - 1)]), int(o[min(k, v.size - 1)])
