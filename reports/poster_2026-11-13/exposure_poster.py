"""Poster Figure 4 input: which power assets a Sandy run floods, read on the NATIVE bed (3.125 m).

    python exposure_poster.py <run_dir> <domain> <tag>
        -> exposure/<tag>_assets.csv  (one row per asset, every state) + exposure/<tag>_faces.npz (map background)

Why not ``scripts/power_exposure.py`` / ``logs/power_exposure_v11_2026-11-09/exposure_v11.py``: both read the
6.25 m first OVERVIEW of the bed (``overview_level=0``, the floodmap bug fixed in
``validate.core.downscale_floodmap_native``). This script does the downscale only where it is needed, at the
pixels under each asset, on the base band:

* pixel centres on a local north-up 3.125 m lattice per footprint (``power_exposure.pixels``);
* ground = the run's OWN bed, base band (``subgrid/dep_subgrid_merged.tif``, rotated: read through its affine);
  buildings are burned in that bed (NJDEP footprints, ground + 10 m capped) in BOTH the 2012 and the 2026 bed,
  so a building pixel reads dry in both: this is the 11-09 "buildings burned" read, done natively;
* water level = the face's ``zsmax`` (max over the storm), the face found by its quadtree square; a face that
  never got ``HMIN`` of water over its lowest pixel paints nothing (hydromt's downscale rule);
* the face must be ACTIVE in the run (``msk``) — otherwise the pixel is NOT COMPUTED, never dry;
* flood depth only on NORMALLY-DRY ground (CLAUDE.md §6: ``normal_surface.normally_wet`` = mapped water, a lake
  pool, or ground below MHHW): normally-wet pixels are "water", not land;
* states as ``power_exposure.asset_state``: wet = any land pixel >= 0.15 m; dry needs half the footprint on
  active faces; NOT COMPUTED otherwise (within 5 km of the active mesh), out of model beyond.

Depth is not failure: floor heights, walls and site protection are unknown.
"""

from __future__ import annotations

import sys
from pathlib import Path

import netCDF4
import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import from_origin
from rasterio.windows import Window
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

import power_exposure as pe  # noqa: E402  (imported unchanged: assets, pixels, states)

import nj_sfincs  # noqa: E402,F401  (PROJ primer, before geopandas)
from nj_sfincs import normal_surface  # noqa: E402

pe.OUT = ROOT / "logs" / "power_exposure_v11_2026-11-09"  # the Census zips live there
OUT = HERE / "exposure"
RES = 3.125  # the subgrid base band
HMIN = 0.05
WET_M = pe.WET_M  # 0.15
PAD = 20.0


class Faces:
    """Point -> quadtree face (the face whose square holds the point). From exposure_v11.py (11-09)."""

    def __init__(self, nc: Path):
        with netCDF4.Dataset(nc) as d:
            self.x0, self.y0 = float(d.x0), float(d.y0)
            self.dx, rot = float(d.dx), np.deg2rad(float(d.rotation))
            self.n = d["n"][:].astype(np.int64)
            self.m = d["m"][:].astype(np.int64)
            self.lev = d["level"][:].astype(np.int64)
            self.fx = np.asarray(d["mesh2d_face_x"][:], "f8")
            self.fy = np.asarray(d["mesh2d_face_y"][:], "f8")
        self.c, self.s = np.cos(rot), np.sin(rot)
        self.N, self.M = int(self.n.max()) + 2, int(self.m.max()) + 2
        key = (self.lev * self.N + self.n) * self.M + self.m
        self.order = np.argsort(key)
        self.keys = key[self.order]

    def lookup(self, x, y) -> np.ndarray:
        u = self.c * (x - self.x0) + self.s * (y - self.y0)
        v = -self.s * (x - self.x0) + self.c * (y - self.y0)
        out = np.full(np.shape(x), -1, np.int64)
        for lev in np.unique(self.lev):
            size = self.dx / 2.0 ** (lev - 1)
            nn = (np.floor(v / size) + 1).astype(np.int64)
            mm = (np.floor(u / size) + 1).astype(np.int64)
            inside = (nn >= 1) & (mm >= 1) & (nn < self.N) & (mm < self.M)
            key = (lev * self.N + nn) * self.M + mm
            i = np.minimum(np.searchsorted(self.keys, key), self.keys.size - 1)
            hit = inside & (self.keys[i] == key) & (out < 0)
            out[hit] = self.order[i[hit]]
        return out


def read_at(ds, x, y) -> np.ndarray:
    """Base-band value at points through the (rotated) affine; NaN off the raster / nodata."""
    col, row = ~ds.transform * (np.asarray(x), np.asarray(y))
    col, row = np.floor(col).astype(np.int64), np.floor(row).astype(np.int64)
    out = np.full(col.shape, np.nan, "f8")
    ok = (col >= 0) & (row >= 0) & (col < ds.width) & (row < ds.height)
    if not ok.any():
        return out
    r0, c0 = int(row[ok].min()), int(col[ok].min())
    w = Window(c0, r0, int(col[ok].max()) - c0 + 1, int(row[ok].max()) - r0 + 1)
    a = ds.read(1, window=w).astype("f8")
    if ds.nodata is not None and np.isfinite(ds.nodata):
        a[a == ds.nodata] = np.nan
    out[ok] = a[row[ok] - r0, col[ok] - c0]
    return out


def run_tables(run: Path, faces: Faces) -> dict:
    with netCDF4.Dataset(run / "sfincs_map.nc") as d:
        zs = np.ma.filled(d["zsmax"][:].astype("f8"), np.nan)
        msk = np.asarray(d["msk"][:])
    zs[zs < -900] = np.nan
    with np.errstate(invalid="ignore"):
        zs = np.nanmax(zs, axis=0)
    with netCDF4.Dataset(run / "sfincs_subgrid.nc") as d:
        zmin = np.ma.filled(d["z_zmin"][:].astype("f8"), np.nan)
        zmax = np.ma.filled(d["z_zmax"][:].astype("f8"), np.nan)
        volmax = np.ma.filled(d["z_volmax"][:].astype("f8"), np.nan)
    area = (faces.dx / 2.0 ** (faces.lev - 1)) ** 2
    zmean = zmax - volmax / area  # the face's MEAN ground (CLAUDE.md §6)
    active = msk > 0
    with np.errstate(invalid="ignore"):
        facewet = active & ((zs - zmin) >= HMIN)
    return dict(zs=zs, zmin=zmin, zmean=zmean, active=active, facewet=facewet)


def read_one(geom, faces, tab, bed, domain_name):
    b = geom.buffer(PAD).bounds
    tf = from_origin(np.floor(b[0] / RES) * RES, np.ceil(b[3] / RES) * RES, RES, RES)
    shape = (
        int(np.ceil((tf.f - b[1]) / RES)) + 1,
        int(np.ceil((b[2] - tf.c) / RES)) + 1,
    )
    rows, cols, n_off = pe.pixels(geom, tf, shape)
    n_px = rows.size + n_off
    x, y = tf * (cols + 0.5, rows + 0.5)
    x, y = np.asarray(x, "f8"), np.asarray(y, "f8")
    f = faces.lookup(x, y)
    fv = np.where(f >= 0, f, 0)
    active = (f >= 0) & tab["active"][fv]
    ground = read_at(bed, x, y)
    active &= np.isfinite(ground)
    zs = np.where(active & tab["facewet"][fv], tab["zs"][fv], np.nan)
    with np.errstate(invalid="ignore"):
        d = zs - ground
        d = np.where(d > HMIN, d, np.nan)
    water = (
        normal_surface.normally_wet(x, y, ground, domain_name) & active
        if rows.size
        else np.zeros(0, bool)
    )
    land = active & ~water
    wet = land & (d >= WET_M)
    n_land, n_wet = int(land.sum()), int(wet.sum())
    lvl = tab["zs"][fv][active]
    return dict(
        n_px=n_px,
        covered_frac=round(active.sum() / n_px, 4) if n_px else 0.0,
        n_land=n_land,
        n_water=int(water.sum()),
        n_wet=n_wet,
        wet_share=round(n_wet / n_land, 4) if n_land else np.nan,
        depth_max=round(float(np.nanmax(d[wet])), 3) if n_wet else np.nan,
        depth_median=round(float(np.nanmedian(d[wet])), 3) if n_wet else np.nan,
        level_median=round(float(np.nanmedian(lvl)), 3)
        if np.isfinite(lvl).any()
        else np.nan,
        ground_median=round(float(np.nanmedian(ground[land])), 3)
        if n_land
        else np.nan,
    )


def main(run: Path, domain_name: str, tag: str) -> None:
    OUT.mkdir(exist_ok=True)
    faces = Faces(run / "sfincs.nc")
    tab = run_tables(run, faces)
    print(f"{tag}: tables read; active faces {tab['active'].sum()}", flush=True)
    assets = pe.load_assets()
    c = assets.representative_point()
    act = np.flatnonzero(tab["active"])
    tree = cKDTree(np.c_[faces.fx[act], faces.fy[act]])
    dist, _ = tree.query(np.c_[c.x.values, c.y.values])
    dist_km = dist / 1e3
    rows = []
    with rasterio.open(run / "subgrid" / "dep_subgrid_merged.tif") as bed:
        assert abs(abs(bed.transform.a) - RES) < 0.01, bed.transform
        for i in range(len(assets)):
            base = dict(
                asset=assets.asset.iloc[i], dist_to_model_km=round(float(dist_km[i]), 2)
            )
            if dist_km[i] > pe.NEAR_KM + 2.0:  # far from any active face: out of model
                r = dict(n_px=0, covered_frac=0.0, n_land=0, n_water=0, n_wet=0)
            else:
                r = read_one(assets.geometry.iloc[i], faces, tab, bed, domain_name)
            r["state"] = pe.asset_state(r, dist_km[i])
            rows.append(base | r)
            if (i + 1) % 500 == 0:
                print(f"  {i + 1}/{len(assets)}", flush=True)
    df = pd.DataFrame(rows).set_index("asset")
    meta = assets.set_index("asset")[
        ["klass", "name", "state", "county", "kv_max", "mw", "fuel"]
    ].rename(columns={"state": "us_state"})
    df = meta.join(df)
    rp = assets.set_index("asset").representative_point()
    df["x"], df["y"] = rp.x.round(1), rp.y.round(1)
    tmp = OUT / f".{tag}_assets.csv"
    df.to_csv(tmp)
    tmp.replace(OUT / f"{tag}_assets.csv")
    # map background: flooded faces on normally-dry ground (face mean ground), at face centres
    with np.errstate(invalid="ignore"):
        dep = tab["zs"] - tab["zmean"]
        fl = tab["facewet"] & (dep >= WET_M)
    idx = np.flatnonzero(fl)
    dry = ~normal_surface.normally_wet(
        faces.fx[idx], faces.fy[idx], tab["zmean"][idx], domain_name
    )
    idx = idx[dry]
    a = np.flatnonzero(tab["active"])
    np.savez_compressed(
        OUT / f"{tag}_faces.npz",
        act_x=faces.fx[a].astype("f4"),
        act_y=faces.fy[a].astype("f4"),
        act_lev=faces.lev[a].astype("i1"),
        fl_x=faces.fx[idx].astype("f4"),
        fl_y=faces.fy[idx].astype("f4"),
        fl_lev=faces.lev[idx].astype("i1"),
        fl_dep=dep[idx].astype("f4"),
    )
    nj = df[df.us_state == "NJ"]
    print(f"{tag}: NJ {nj.state.value_counts().to_dict()}", flush=True)
    print(f"{tag}: all {df.state.value_counts().to_dict()}", flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve(), sys.argv[2], sys.argv[3])
