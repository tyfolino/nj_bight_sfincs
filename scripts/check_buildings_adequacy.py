"""Adequacy checks BEFORE burning building footprints into the v3 subgrid.

Four questions, each answered with a number the STATUS entry can quote:

1. **Where do the scored HWMs sit?** Share of scored (q<=2, in-region) marks whose nearest
   active face is 25 m vs 50 m vs coarser. Buildings enter the model as subgrid porosity,
   so a mark in a 25 m cell sees 3.125 m pixels and one in a 50 m cell sees 6.25 m pixels.
2. **How deep did the premier get over land?** Percentiles of the premier's downscaled
   hmax on ground above ~MHW. The building-height cap must clear the water everywhere
   that matters, and no more: the uv conveyance tables are spaced by EQUAL DEPTH between
   the cell's zmin and zmax (hydromt workflows/subgrid.py), so every metre of cap above
   the water coarsens the table where the flow actually is.
3. **Does the pixel burn keep the buildings?** For a random sample of active cells in
   each band that intersect >=1 footprint: exact vector coverage fraction vs the fraction
   of subgrid pixels a pixel-centre rasterisation marks as building. The burn is done
   at 3.125 m (the lev-3 lattice, `subgrid/dep_subgrid_merged.tif`) and the 50 m band's
   6.25 m pixels are that lattice subsampled, so both are emulated.
4. **What is the uv level spacing today?** (uv_zmax - uv_zmin)/(nr_levels-1) on land
   uv points, so the cost of a cap H (~H/9 per level at 10 levels) has a baseline.

Read-only. Writes `data/buildings_v3/adequacy_<date>.json` and prints a summary.

    NJ_DOMAIN=v3 PYTHONPATH=$PWD python scripts/check_buildings_adequacy.py
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pyproj  # noqa: F401,E402  (before hydromt_sfincs / rasterio: native double-free)
import geopandas as gpd  # noqa: E402
import rasterio  # noqa: E402
import xarray as xr  # noqa: E402
from rasterio import features  # noqa: E402
from rasterio.enums import Resampling  # noqa: E402
from rasterio.transform import from_origin  # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402
from shapely.geometry import box  # noqa: E402

from nj_sfincs import domain as _domain  # noqa: E402
from nj_sfincs import premier  # noqa: E402
from nj_sfincs.config import DATA, exp_root  # noqa: E402

BASE_RES = 200.0  # level-1 cell size [m]; levels are 1-based in sfincs.nc
NR_PIX = 8  # nr_subgrid_pixels on every v3 template
NR_LEVELS = 10


def _pct(a, q=(50, 90, 99, 99.9)):
    a = np.asarray(a, dtype=float)
    a = a[np.isfinite(a)]
    if a.size == 0:
        return {}
    out = {f"p{p}": float(np.percentile(a, p)) for p in q}
    out["max"] = float(a.max())
    out["n"] = int(a.size)
    return out


def check_hwm_cells(template: Path, dom) -> dict:
    ds = xr.open_dataset(template / "sfincs.nc")
    fx = ds.mesh2d_face_x.values
    fy = ds.mesh2d_face_y.values
    lev = ds.level.values
    msk = ds["mask"].values
    act = msk > 0
    size = BASE_RES / 2 ** (lev - 1)
    tree = cKDTree(np.c_[fx[act], fy[act]])
    size_act = size[act]

    hwm = gpd.read_file(str(dom.hwm_geojson))
    reg = gpd.read_file(str(dom.region)).to_crs(hwm.crs)
    geom = reg.union_all() if hasattr(reg, "union_all") else reg.unary_union
    hwm = hwm[(hwm["quality"] <= 2) & hwm.geometry.within(geom)].to_crs(dom.epsg)
    d, idx = tree.query(np.c_[hwm.geometry.x.values, hwm.geometry.y.values])
    cell = size_act[idx]
    on_grid = d <= cell  # nearest active face centre within one cell size
    basin = np.asarray(
        _domain.classify_hwm_basin(hwm.geometry.x.values, hwm.geometry.y.values, dom)
    )
    out = {
        "n_q2_in_region": int(len(hwm)),
        "n_on_grid": int(on_grid.sum()),
        "by_cell_size_m": {
            f"{int(s)}": int(((cell == s) & on_grid).sum()) for s in np.unique(cell)
        },
        "by_basin": {},
    }
    for b in np.unique(basin):
        m = (basin == b) & on_grid
        out["by_basin"][str(b)] = {
            f"{int(s)}": int((m & (cell == s)).sum()) for s in np.unique(cell[m])
        }
    return out


def check_land_depth(template: Path, premier_dir: Path, ground_min=0.7) -> dict:
    """Premier hmax on ground above `ground_min` m NAVD88, read at the 12.5 m overview."""
    with rasterio.open(premier_dir / "floodmap_hmax_lev3.tif") as fm:
        shp = (fm.height // 2, fm.width // 2)
        h = fm.read(1, out_shape=shp, resampling=Resampling.nearest)
        fm_bounds = fm.bounds
    with rasterio.open(template / "subgrid" / "dep_subgrid_merged.tif") as dm:
        assert dm.bounds == fm_bounds, (dm.bounds, fm_bounds)
        g = dm.read(1, out_shape=shp, resampling=Resampling.nearest)
    land = np.isfinite(g) & (g > ground_min) & np.isfinite(h) & (h > 0)
    d = h[land]
    out = {"ground_min_navd88_m": ground_min, "depth_over_land": _pct(d)}
    out["depth_over_land"]["n_gt_2m"] = int((d > 2).sum())
    out["depth_over_land"]["n_gt_3m"] = int((d > 3).sum())
    out["depth_over_land"]["n_gt_4m"] = int((d > 4).sum())
    out["depth_over_land"]["n_gt_5m"] = int((d > 5).sum())
    out["pixel_m"] = 12.5
    return out


def _cell_fractions(cells: gpd.GeoDataFrame, bld: gpd.GeoDataFrame, size: float) -> dict:
    """Exact coverage vs pixel-centre burn for every cell polygon in `cells`."""
    sidx = bld.sindex
    exact, px_band, px_fine_sub = [], [], []
    pix = size / NR_PIX  # the band's own subgrid pixel
    for geom in cells.geometry.values:
        hits = bld.iloc[sidx.query(geom, predicate="intersects")]
        if len(hits) == 0:
            continue
        inter = hits.geometry.intersection(geom)
        exact.append(float(inter.area.sum()) / geom.area)
        x0, y0, x1, y1 = geom.bounds
        # (a) burn at this band's pixel size, pixel-centre rule
        t = from_origin(x0, y1, pix, pix)
        r = features.rasterize(
            ((g, 1) for g in hits.geometry.values), out_shape=(NR_PIX, NR_PIX),
            transform=t, fill=0, all_touched=False, dtype="uint8",
        )
        px_band.append(r.mean())
        # (b) burn at 3.125 m (the lattice the tier is written on), then take every
        #     other pixel — what nearest-resampling onto a 6.25 m pixel does
        k = int(round(size / 3.125))
        t3 = from_origin(x0, y1, 3.125, 3.125)
        r3 = features.rasterize(
            ((g, 1) for g in hits.geometry.values), out_shape=(k, k),
            transform=t3, fill=0, all_touched=False, dtype="uint8",
        )
        step = k // NR_PIX
        px_fine_sub.append(r3[::step, ::step].mean())
    exact = np.array(exact)
    px_band = np.array(px_band)
    px_fine_sub = np.array(px_fine_sub)

    def _stats(px):
        e = px - exact
        return {
            "mean_exact": float(exact.mean()),
            "mean_burned": float(px.mean()),
            "bias": float(e.mean()),
            "mae": float(np.abs(e).mean()),
            "rmse": float(np.sqrt((e**2).mean())),
            "r": float(np.corrcoef(exact, px)[0, 1]),
            "n_cells": int(exact.size),
            "n_lost_cells": int(((exact > 0) & (px == 0)).sum()),
            "lost_area_frac": float(exact[(px == 0)].sum() / exact.sum()),
            "n_fully_covered_burn": int((px >= 1.0).sum()),
            "n_fully_covered_exact": int((exact >= 0.999).sum()),
        }

    return {
        "cell_m": size,
        "pixel_m": pix,
        "burn_at_band_pixel": _stats(px_band),
        "burn_at_3p125_then_subsample": _stats(px_fine_sub),
        "exact_frac_pct": _pct(exact),
    }


def check_pixel_fractions(template: Path, dom, n_per_band=3000, seed=0) -> dict:
    t0 = time.time()
    bld = gpd.read_file(DATA / "buildings_v3" / "njdep_footprints.gpkg")
    print(f"  footprints read: {len(bld)} in {time.time() - t0:.0f}s", flush=True)
    assert bld.crs.to_epsg() == dom.epsg
    ds = xr.open_dataset(template / "sfincs.nc")
    fx = ds.mesh2d_face_x.values
    fy = ds.mesh2d_face_y.values
    lev = ds.level.values
    act = ds["mask"].values > 0
    rng = np.random.default_rng(seed)
    out = {}
    bx0, by0, bx1, by1 = bld.total_bounds
    for L, size in ((4, 25.0), (3, 50.0)):
        cand = np.flatnonzero(act & (lev == L))
        # cheap pre-screen: cells inside the footprint layer's bbox
        cx, cy = fx[cand], fy[cand]
        inb = (cx > bx0) & (cx < bx1) & (cy > by0) & (cy < by1)
        cand = cand[inb]
        rng.shuffle(cand)
        # bulk sindex query on a generous pool, keep cells with >= 1 footprint
        pool = cand[: n_per_band * 12]
        half = size / 2
        boxes = [box(x - half, y - half, x + half, y + half) for x, y in zip(fx[pool], fy[pool])]
        cells = gpd.GeoDataFrame(geometry=boxes, crs=bld.crs)
        hit = np.unique(bld.sindex.query(cells.geometry.values, predicate="intersects")[0])
        cells = cells.iloc[hit[:n_per_band]]
        print(f"  band {int(size)} m: {len(cells)} cells with buildings out of {len(pool)} "
              f"sampled ({100 * len(hit) / len(pool):.1f}% touch a footprint)", flush=True)
        r = _cell_fractions(cells, bld, size)
        r["share_of_sampled_cells_touching_footprint"] = float(len(hit) / len(pool))
        out[f"band_{int(size)}m"] = r
    return out


def check_uv_spacing(template: Path, ground_min=0.5) -> dict:
    ds = xr.open_dataset(template / "sfincs_subgrid.nc")
    zmin = ds.uv_zmin.values
    zmax = ds.uv_zmax.values
    nlev = ds.sizes["levels"]
    land = np.isfinite(zmin) & (zmin > ground_min)
    dl = (zmax[land] - zmin[land]) / (nlev - 1)
    return {
        "nr_levels": int(nlev),
        "uv_land_points": int(land.sum()),
        "dlevel_m": _pct(dl),
        "note": "uv tables are EQUAL-DEPTH between zmin+huthresh and zmax; a cap H raises "
        "zmax on every uv point touching a footprint, so dlevel -> ~H/(nr_levels-1).",
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--premier", default="naccs-premier")
    ap.add_argument("--n-per-band", type=int, default=3000)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    dom = _domain.active()
    template = premier.sealed_template()
    premier_dir = exp_root() / args.premier
    out = {"domain": dom.name, "template": str(template), "date": str(date.today())}

    print("[1/4] scored HWMs by cell size", flush=True)
    out["hwm_cells"] = check_hwm_cells(template, dom)
    print("   ", out["hwm_cells"]["by_cell_size_m"], "of", out["hwm_cells"]["n_on_grid"])

    print("[2/4] premier depth over land", flush=True)
    out["land_depth"] = check_land_depth(template, premier_dir)
    print("   ", out["land_depth"]["depth_over_land"])

    print("[4/4 first — cheap] uv level spacing", flush=True)
    out["uv_spacing"] = check_uv_spacing(template)
    print("   ", out["uv_spacing"]["dlevel_m"])

    print("[3/4] exact vs burned footprint fraction per cell", flush=True)
    out["pixel_fractions"] = check_pixel_fractions(template, dom, args.n_per_band)
    for k, v in out["pixel_fractions"].items():
        print("   ", k, "band-pixel:", {a: round(b, 4) for a, b in v["burn_at_band_pixel"].items()})
        print("   ", k, "3.125-sub :", {a: round(b, 4) for a, b in v["burn_at_3p125_then_subsample"].items()})

    dst = Path(args.out) if args.out else DATA / "buildings_v3" / f"adequacy_{date.today()}.json"
    tmp = dst.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, indent=2))
    tmp.replace(dst)
    print("wrote", dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
