#!/usr/bin/env python
"""Power sites in water at a tidal high water, read from a PER-FACE level at the site pixels. 2026-11-23.

    NJ_DOMAIN=<domain> python scripts/tide_assets.py <run_dir> <surface.nc> <tag>
        [--kinds mhh max] [--raw] [--noisy <fT.npy>] [--out DIR]
        -> <out>/<tag>_<kind>_assets.csv + _summary.json + _summary.txt

``surface.nc`` is a ``nj_sfincs/tide_surface.py`` output (the DE-NOISED ``mean_higher_high`` / ``max_month``;
``--raw`` reads its ``*_raw`` twins) or an old ``mhhw_maps.py`` ``*_tide_stats.nc`` (raw by construction).

WHAT IT REPRODUCES. The count of ``logs/slr_assets_2026-11-13/slr_assets.py`` on a
``logs/mhhw_v2_2026-11-12/mhhw_maps.py tide`` depth product, without drawing the 4.8 G-pixel map: for each
site the product's OWN north-up 3.125 m pixels (``power_exposure.pixels`` on the lattice ``mhhw_maps.derotate``
writes, ``rioxarray``'s ``_make_dst_affine`` of the bed), and for each pixel the value the product would hold
there: the nearest pixel of the ROTATED bed lattice (through the affine, CLAUDE.md §5), the level of the
quadtree face holding THAT pixel's centre, depth = level - pixel ground (float32, as the product), drawn
where > 0 and normally dry at that centre (CLAUDE.md §6). Then the slr_assets rules, unchanged:

* active = the north-up pixel centre's face is active and has ground; water = ``normal_surface.normally_wet``
  there (not land); wet = a land pixel with depth >= 0.15 m (``power_exposure.WET_M``);
* "touched" = state ``wet`` (``power_exposure.asset_state``); "at least half wet" = wet share >= 0.5;
* the universe: the 253 NJ records of ``reports/poster_2026-11-13/exposure/v11_modernb_2026bed_assets.csv``
  not out of the model; "the 182" = those the 1.1.0 2026-bed Sandy run computes.

Drawn faces as the products: mhh on faces wet >= half the tidal days, max on faces wet >= 1 day; ``--noisy``
blanks a legacy active-face list (the 11-02 ``fT``) as ``mhhw_maps.py --noisy`` did (only to reproduce old
counts; the de-noised surface replaces it).

LADDER-READY. ``SitePixels`` does the geometry once (the slow part: footprints, ground, water); ``score(level)``
then takes ANY per-face level array in a second, so a threshold ladder (water level at a reference gauge ->
the run / level at which a site is first wet) is a loop of ``score`` over rungs. ``rise_to_touch(level)`` gives
the still-water shortcut: the uniform rise of a given surface that first puts 0.15 m on a land pixel.

Depth is not failure: floor heights, walls and site protection are unknown.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import netCDF4
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import Window

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

import power_exposure as pe  # noqa: E402

import nj_sfincs  # noqa: E402,F401  (PROJ primer, before geopandas)
from nj_sfincs import normal_surface  # noqa: E402

pe.OUT = ROOT / "logs" / "power_exposure_v11_2026-11-09"  # the Census zips live there
ASSET_LIST = ROOT / "reports/poster_2026-11-13/exposure/v11_modernb_2026bed_assets.csv"
COMPUTED = ("wet", "dry", "on_water")
KINDS = {"mhh": "mean_higher_high", "max": "max_month"}


class FaceLocator:
    """Point -> quadtree face whose square holds it (``slr_assets.Faces``, copied), + the active mask."""

    def __init__(self, nc: Path):
        with netCDF4.Dataset(nc) as d:
            self.x0, self.y0 = float(d.x0), float(d.y0)
            self.dx, rot = float(d.dx), np.deg2rad(float(d.rotation))
            self.n = d["n"][:].astype(np.int64)
            self.m = d["m"][:].astype(np.int64)
            self.lev = d["level"][:].astype(np.int64)
            self.active = np.asarray(np.ma.filled(d["mask"][:], 0)) > 0
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


def north_up_lattice(dep: Path):
    """(affine, width, height) of the north-up grid ``mhhw_maps.derotate`` writes for this bed."""
    import rioxarray
    from rioxarray.raster_array import _make_dst_affine

    with rioxarray.open_rasterio(
        dep, masked=True, cache=False, parse_coordinates=False
    ) as lazy:
        crs = lazy.rio.crs
        return _make_dst_affine(
            src_data_array=lazy.squeeze(drop=True), src_crs=crs, dst_crs=crs
        )


def read_cells(ds, rows, cols) -> np.ndarray:
    """Base band at integer (rows, cols) through one window; NaN off the raster / nodata (float32)."""
    out = np.full(rows.shape, np.nan, np.float32)
    ok = (cols >= 0) & (rows >= 0) & (cols < ds.width) & (rows < ds.height)
    if not ok.any():
        return out
    r0, c0 = int(rows[ok].min()), int(cols[ok].min())
    w = Window(c0, r0, int(cols[ok].max()) - c0 + 1, int(rows[ok].max()) - r0 + 1)
    a = ds.read(1, window=w, masked=True).filled(np.nan).astype(np.float32)
    out[ok] = a[rows[ok] - r0, cols[ok] - c0]
    return out


def product_depth(level, face, ground, drawable):
    """Depth the mhhw_maps product holds at pixels: float32(level[face] - ground) where > 0 and drawable."""
    lev = np.asarray(level, np.float32).astype(np.float64)
    z = np.where(face >= 0, lev[np.maximum(face, 0)], np.nan)
    h = (z - ground).astype(np.float32)
    with np.errstate(invalid="ignore"):
        return np.where((h > 0.0) & drawable, h, np.float32(np.nan))


class SitePixels:
    """Every site's product pixels, ground, land / water and the face each pixel reads (module docstring)."""

    def __init__(self, run_dir: Path, geoms: pd.Series, dom: str):
        run_dir = Path(run_dir)
        dep = run_dir / "subgrid" / "dep_subgrid_merged.tif"
        self.faces = FaceLocator(run_dir / "sfincs.nc")
        self.affine, w, h = north_up_lattice(dep)
        self.shape = (h, w)
        keys = ("row", "col", "x", "y", "face", "ground", "drawable", "land", "water")
        parts = {k: [] for k in keys}
        self.sites, self.n_px, self.off = list(geoms.index), [], [0]
        with rasterio.open(dep) as bed:
            T = bed.transform
            self.bed_res_m = round(float(np.hypot(T.a, T.d)), 4)
            for g in geoms.values:
                rows, cols, n_off = pe.pixels(g, self.affine, self.shape)
                self.n_px.append(rows.size + n_off)
                x, y = self.affine * (cols + 0.5, rows + 0.5)
                x, y = np.asarray(x, "f8"), np.asarray(y, "f8")
                # slr_assets.read_one at the north-up centre: active, ground, water, land
                fn = self.faces.lookup(x, y)
                active = (fn >= 0) & self.faces.active[np.maximum(fn, 0)]
                c, r = ~T * (x, y)
                c, r = np.floor(c).astype(np.int64), np.floor(r).astype(np.int64)
                ground = read_cells(bed, r, c)  # the rotated pixel the product reads
                active &= np.isfinite(ground)
                water = (
                    normal_surface.normally_wet(x, y, ground.astype("f8"), dom) & active
                    if rows.size
                    else np.zeros(0, bool)
                )
                # the product at that rotated pixel: its centre's face, normally dry there
                xr_, yr_ = T * (c + 0.5, r + 0.5)
                xr_, yr_ = np.asarray(xr_, "f8"), np.asarray(yr_, "f8")
                fr = self.faces.lookup(xr_, yr_)
                drawable = (
                    normal_surface.normally_dry(xr_, yr_, ground, dom)
                    if rows.size
                    else np.zeros(0, bool)
                )
                for k, v in (
                    ("face", fr),
                    ("ground", ground),
                    ("drawable", drawable),
                    ("land", active & ~water),
                    ("water", water),
                    ("row", rows),
                    ("col", cols),
                    ("x", x),
                    ("y", y),
                ):
                    parts[k].append(v)
                self.off.append(self.off[-1] + rows.size)
        for k, v in parts.items():
            setattr(self, k, np.concatenate(v) if v else np.zeros(0))
        self.face = self.face.astype(np.int64)
        self.land, self.water = self.land.astype(bool), self.water.astype(bool)
        self.drawable = self.drawable.astype(bool)

    def depth(self, level) -> np.ndarray:
        return product_depth(level, self.face, self.ground, self.drawable)

    def score(self, level) -> pd.DataFrame:
        """slr_assets.read_one's row per site for a per-face level (NaN = face not drawn)."""
        d = self.depth(level)
        with np.errstate(invalid="ignore"):
            wet = self.land & (d >= pe.WET_M)
        rows = []
        for i, aid in enumerate(self.sites):
            a, b = self.off[i], self.off[i + 1]
            n_px = self.n_px[i]
            land, w, dd = self.land[a:b], wet[a:b], d[a:b]
            n_land, n_wet = int(land.sum()), int(w.sum())
            rows.append(
                dict(
                    asset=aid,
                    n_px=n_px,
                    covered_frac=round(
                        int((self.land[a:b] | self.water[a:b]).sum()) / n_px, 4
                    )
                    if n_px
                    else 0.0,
                    n_land=n_land,
                    n_water=int(self.water[a:b].sum()),
                    n_wet=n_wet,
                    wet_share=round(n_wet / n_land, 4) if n_land else np.nan,
                    depth_max=round(float(dd[w].max()), 3) if n_wet else np.nan,
                    depth_median=round(float(np.median(dd[w])), 3) if n_wet else np.nan,
                    ground_median=round(float(np.nanmedian(self.ground[a:b][land])), 3)
                    if n_land
                    else np.nan,
                    n_drawn_off_land=int((np.isfinite(dd) & ~land).sum()),
                )
            )
        return pd.DataFrame(rows).set_index("asset")

    def rise_to_touch(self, level) -> pd.Series:
        """Per site: the uniform rise of ``level`` (on its drawn faces) that first puts >= 0.15 m on a land
        pixel (<= 0: already touched; NaN: no land pixel on a drawn face). A still-water shortcut for a
        ladder; the solved answer is ``score`` on each rung's own run."""
        lev = np.asarray(level, np.float32).astype(np.float64)
        z = np.where(self.face >= 0, lev[np.maximum(self.face, 0)], np.nan)
        need = np.where(
            self.land & self.drawable & np.isfinite(z),
            self.ground + pe.WET_M - z,
            np.nan,
        )
        out = []
        for a, b in zip(self.off[:-1], self.off[1:]):
            v = need[a:b]
            out.append(float(np.nanmin(v)) if np.isfinite(v).any() else np.nan)
        return pd.Series(out, index=self.sites, name="rise_to_touch_m")


def surface_level(nc, kind, *, raw=False, noisy=None, active=None):
    """Per-face level the products draw: NaN off the drawn faces (mhh: wet >= half the days; max: >= 1)."""
    import xarray as xr

    with xr.open_dataset(nc) as t:
        var = KINDS[kind] + ("_raw" if raw else "")
        if var not in t:
            raise SystemExit(
                f"{nc}: no {var} (an mhhw_maps tide_stats file is raw: drop --raw)"
            )
        v = t[var].values.astype("f4")
        days, nd = t.days_wet.values, int(t.attrs["ndays"])
    need = (nd + 1) // 2 if kind == "mhh" else 1
    keep = np.isfinite(v) & (days >= need)
    if active is not None:
        keep &= active
    if noisy is not None:
        fT = np.load(noisy)
        if active is None or fT.size != int(active.sum()):
            raise SystemExit(f"{noisy}: {fT.size} values, not one per active face")
        bl = np.zeros(v.size, bool)
        bl[active] = fT
        keep &= ~bl
    return np.where(keep, v, np.float32(np.nan))


def load_universe():
    lst = pd.read_csv(ASSET_LIST, index_col="asset")
    lst = lst[(lst.us_state == "NJ") & (lst.state != "out_of_model")]
    assets = pe.load_assets().set_index("asset")
    missing = lst.index.difference(assets.index)
    if len(missing):
        raise SystemExit(
            f"{len(missing)} listed assets not in load_assets: {missing[:5]}"
        )
    return lst, assets.loc[lst.index]


def table(sp: SitePixels, level, lst) -> pd.DataFrame:
    df = sp.score(level)
    df["state"] = [
        pe.asset_state(r, float(lst.dist_to_model_km[a])) for a, r in df.iterrows()
    ]
    keep = ["klass", "name", "county", "kv_max", "mw", "fuel", "x", "y"]
    return lst[keep].join(lst.state.rename("sandy2026_state")).join(df)


def summarise(df, tag, meta):
    c182 = df[df.sandy2026_state.isin(COMPUTED)]
    wet = c182[c182.state == "wet"]
    half = wet[wet.wet_share >= 0.5]
    js = dict(
        tag=tag,
        **meta,
        computed_182=len(c182),
        wet_of_182=len(wet),
        wet_of_182_ge_half=len(half),
        wet_of_182_by_class=wet.klass.value_counts().to_dict(),
        wet_of_182_ge_half_by_class=half.klass.value_counts().to_dict(),
        states_of_182=c182.state.value_counts().to_dict(),
        wet_outside_182=df.index[
            ~df.sandy2026_state.isin(COMPUTED) & (df.state == "wet")
        ].tolist(),
        wet_sites=wet.sort_values("wet_share", ascending=False).index.tolist(),
    )
    lines = [
        f"{tag}: NJ power sites with depth >= {pe.WET_M} m on normally-dry land",
        f"surface: {meta['surface']} ({meta['variable']})",
        f"TOUCHED: {len(wet)} of {len(c182)}; AT LEAST HALF WET: {len(half)}",
        "",
    ]
    for a, r in wet.sort_values("wet_share", ascending=False).iterrows():
        nm = (
            r["name"]
            if isinstance(r["name"], str) and r["name"].strip()
            else "(unnamed)"
        )
        lines.append(
            f"  {a:8s} {r.klass:10s} {nm[:40]:40s} {r.county:12s} wet {r.wet_share:6.1%}"
            f" ({r.n_wet} px)  max {r.depth_max:5.2f} m"
        )
    lines += [
        "",
        "Depth is not failure: floor heights, walls and site protection are unknown.",
    ]
    return "\n".join(lines) + "\n", js


def write_atomic(p: Path, text: str):
    tmp = p.with_name(f".{p.name}.{os.getpid()}.tmp")
    tmp.write_text(text)
    os.replace(tmp, p)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("run_dir", type=Path)
    ap.add_argument(
        "surface", type=Path, help="tide_surface.py output (or a tide_stats.nc)"
    )
    ap.add_argument("tag")
    ap.add_argument("--kinds", nargs="+", default=["mhh", "max"], choices=list(KINDS))
    ap.add_argument(
        "--raw", action="store_true", help="read the *_raw (not de-noised) fields"
    )
    ap.add_argument(
        "--noisy", help="legacy active-face blank list (fT.npy), as mhhw_maps --noisy"
    )
    ap.add_argument("--out", type=Path, default=Path.cwd())
    a = ap.parse_args(argv)
    dom = os.environ.get("NJ_DOMAIN") or sys.exit(
        "set NJ_DOMAIN (no default, CLAUDE.md §2)"
    )
    t0 = time.time()
    a.out.mkdir(parents=True, exist_ok=True)
    lst, assets = load_universe()
    sp = SitePixels(a.run_dir, assets.geometry, dom)
    print(
        f"site pixels: {sp.face.size} in {len(sp.sites)} sites, {time.time() - t0:.0f} s",
        flush=True,
    )
    for kind in a.kinds:
        level = surface_level(
            a.surface, kind, raw=a.raw, noisy=a.noisy, active=sp.faces.active
        )
        df = table(sp, level, lst)
        meta = dict(
            surface=str(a.surface),
            variable=KINDS[kind] + ("_raw" if a.raw else ""),
            noisy=a.noisy,
            run_dir=str(a.run_dir),
            domain=dom,
            bed_res_m=sp.bed_res_m,
            wet_m=pe.WET_M,
            asset_list=str(ASSET_LIST),
        )
        txt, js = summarise(df, f"{a.tag}_{kind}", meta)
        tmp = a.out / f".{a.tag}_{kind}_assets.csv.{os.getpid()}.tmp"
        df.to_csv(tmp)
        os.replace(tmp, a.out / f"{a.tag}_{kind}_assets.csv")
        write_atomic(
            a.out / f"{a.tag}_{kind}_summary.json",
            json.dumps(js, indent=1, default=str) + "\n",
        )
        write_atomic(a.out / f"{a.tag}_{kind}_summary.txt", txt)
        print(txt, flush=True)


if __name__ == "__main__":
    main()
