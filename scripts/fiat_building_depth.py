"""Flood depth AT EACH BUILDING for Delft-FIAT: the 11-05 centroid rule (STATUS "FIAT output").

The bare-ground export (``export_share_floodmap.py --ground``) already measures depth from
bare earth, but a building that fills a whole model face still reads dry there even when
the streets around it flood (the face is dropped: its lowest pixel is a roof). This step
gives every footprint the water of the streets around it:

    level(b) = MEDIAN peak water LEVEL (bare ground + depth, m NAVD88) of the WET
               (depth >= 0.15 m) NON-building pixels within 50 m of footprint b
               — the HWM scorer's estimator: median over a +-50 m square window
               (``validate.metrics``: ``rad = round(50 / pixel)``), here around the
               whole footprint instead of a point;
    depth(b) = level(b) - bare ground at the centroid (and per pixel inside the footprint).

Outputs, on the plain bare-ground tif's own north-up lattice:
  * ``--out-tif``: the plain tif with every footprint pixel (and each centroid's pixel)
    replaced by ``level - bare ground`` where that exceeds the 0.05 m floor, else NaN;
    pixels outside footprints are copied unchanged (counted, must be 0 changed).
  * ``--out-csv`` / ``--out-gpkg`` (centroid POINTS): building id, source, centroid x/y,
    level, bare ground at the centroid, the footprint's median bare ground, depth, n wet
    pixels used, flag (``wet`` depth >= 0.05 m / ``dry`` / ``no_wet_neighbour``: no wet
    pixel within 50 m, depth NaN), and the plain tif's value at the centroid.
  * ``--json``: counts (wet / dry / no-neighbour, changed vs the plain tif).

Bare ground is the no-buildings subgrid bed (rotated, CLAUDE.md §5) warped onto the plain
tif's lattice with GDAL NEAREST through a WarpedVRT — the same warp that de-rotated the
depth, so level = bare + depth reproduces each pixel's face ``zsmax``. Base band only
(no overview read). Memory: tile-sized windows (``--tile`` px); RSS a few GB.

    NJ_DOMAIN=v4_refreeze_swz_v11 PYTHONPATH=$PWD python scripts/fiat_building_depth.py \\
        --depth share/<stem>_EPSG32618.tif \\
        --bare experiments/v4_refreeze_swz/<nobuildings dir>/subgrid/dep_subgrid_merged.tif \\
        --footprints <gpkg|fgb> --source hybrid --out-tif ... --out-csv ... --out-gpkg ...
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import geopandas as gpd  # noqa: E402
import pandas as pd  # noqa: E402
import pyogrio  # noqa: E402
import pyproj  # noqa: F401,E402  (before anything that may pull hydromt)
import rasterio  # noqa: E402
from rasterio import features  # noqa: E402
from rasterio.enums import Resampling  # noqa: E402
from rasterio.vrt import WarpedVRT  # noqa: E402
from rasterio.windows import Window  # noqa: E402
from scipy import ndimage  # noqa: E402

WET = 0.15  # validate.DEPTH_MIN: the scorer's wet threshold
HMIN = 0.05  # the downscale floor: below it a pixel is NaN in the depth tifs


def read_footprints(path: str, bounds) -> gpd.GeoDataFrame:
    info = pyogrio.read_info(path)
    crs = info["crs"]
    b = bounds
    if crs and crs != "EPSG:32618":
        from rasterio.warp import transform_bounds  # noqa: PLC0415

        b = transform_bounds("EPSG:32618", crs, *bounds, densify_pts=21)
    g = pyogrio.read_dataframe(path, bbox=b, fid_as_index=True)
    if g.crs is not None and g.crs.to_epsg() != 32618:
        g = g.to_crs(32618)
    g = g[g.geometry.notna() & ~g.geometry.is_empty]
    if "objectid" in g.columns:
        bid = g["objectid"].astype("int64").to_numpy()
    else:
        bid = np.asarray(g.index, dtype="int64")
    out = gpd.GeoDataFrame({"building_id": bid}, geometry=g.geometry.values, crs=32618)
    c = out.geometry.centroid
    out["xc"], out["yc"] = c.x.to_numpy(), c.y.to_numpy()
    left, bottom, right, top = bounds
    inside = (
        (out["xc"] >= left)
        & (out["xc"] < right)
        & (out["yc"] > bottom)
        & (out["yc"] <= top)
    )
    return out[inside].reset_index(drop=True)


def tiles(h: int, w: int, t: int):
    for r0 in range(0, h, t):
        for c0 in range(0, w, t):
            yield Window(c0, r0, min(t, w - c0), min(t, h - r0))


def _window_bounds(win: Window, T):
    left, top = T * (win.col_off, win.row_off)
    right, bottom = T * (win.col_off + win.width, win.row_off + win.height)
    return left, bottom, right, top


def _rasterize_ids(g, sidx, win, T, idx_offset=1):
    """Footprint index (+1) per pixel centre in ``win``; 0 = not a building."""
    from shapely.geometry import box  # noqa: PLC0415

    b = _window_bounds(win, T)
    cand = sidx.query(box(*b), predicate="intersects")
    shape = (int(win.height), int(win.width))
    if cand.size == 0:
        return np.zeros(shape, "int32"), cand
    wt = rasterio.windows.transform(win, T)
    ids = features.rasterize(
        zip(g.geometry.values[cand], cand.astype("int64") + idx_offset),
        out_shape=shape,
        transform=wt,
        fill=0,
        dtype="int32",
        all_touched=False,
    )
    return ids, cand


def pass1_levels(g, depth_src, bare_vrt, tile, rad, log_every=60):
    """Per building: level, n wet, bare at centroid, footprint median bare."""
    T = depth_src.transform
    H, W = depth_src.shape
    n = len(g)
    level = np.full(n, np.nan)
    n_wet = np.zeros(n, "int32")
    bare_c = np.full(n, np.nan)
    bare_fp = np.full(n, np.nan)
    plain_c = np.full(n, np.nan)
    inv = ~T
    col, row = inv * (g["xc"].to_numpy(), g["yc"].to_numpy())
    col, row = np.floor(col).astype("int64"), np.floor(row).astype("int64")
    tr, tc = row // tile, col // tile
    order = np.lexsort((tc, tr))
    key = tr[order] * (W // tile + 2) + tc[order]
    starts = np.flatnonzero(np.r_[True, key[1:] != key[:-1]])
    ends = np.r_[starts[1:], order.size]
    bnds = g.geometry.bounds.to_numpy()  # minx, miny, maxx, maxy
    # footprint bbox in pixel space (north-up lattice)
    pc0 = np.floor((bnds[:, 0] - T.c) / T.a).astype("int64")
    pc1 = np.floor((bnds[:, 2] - T.c) / T.a).astype("int64") + 1
    pr0 = np.floor((bnds[:, 3] - T.f) / T.e).astype("int64")
    pr1 = np.floor((bnds[:, 1] - T.f) / T.e).astype("int64") + 1
    sidx = g.sindex
    t0 = last = time.time()
    for k, (s, e) in enumerate(zip(starts, ends)):
        sel = order[s:e]
        r0 = max(0, int(min(pr0[sel].min(), row[sel].min())) - rad - 1)
        r1 = min(H, int(max(pr1[sel].max(), row[sel].max() + 1)) + rad + 1)
        c0 = max(0, int(min(pc0[sel].min(), col[sel].min())) - rad - 1)
        c1 = min(W, int(max(pc1[sel].max(), col[sel].max() + 1)) + rad + 1)
        win = Window(c0, r0, c1 - c0, r1 - r0)
        d = depth_src.read(1, window=win, masked=True).filled(np.nan)
        z = bare_vrt.read(1, window=win, masked=True).filled(np.nan).astype("float64")
        ids, _ = _rasterize_ids(g, sidx, win, T)
        lr, lc = row[sel] - r0, col[sel] - c0
        bare_c[sel] = z[lr, lc]
        plain_c[sel] = d[lr, lc]
        wse = np.where((d >= WET) & (ids == 0) & np.isfinite(z), z + d, np.nan)
        any_wet = np.isfinite(wse).any()
        for j, b in enumerate(sel):
            a0, a1 = max(0, pr0[b] - r0), min(win.height, pr1[b] - r0)
            b0, b1 = max(0, pc0[b] - c0), min(win.width, pc1[b] - c0)
            fp_sl = ids[a0:a1, b0:b1] == (b + 1)
            fz = z[a0:a1, b0:b1][fp_sl]
            bare_fp[b] = np.nanmedian(fz) if np.isfinite(fz).any() else bare_c[b]
            if not any_wet:
                continue
            s0, s1 = max(0, a0 - rad), min(win.height, a1 + rad)
            q0, q1 = max(0, b0 - rad), min(win.width, b1 + rad)
            fp = np.zeros((s1 - s0, q1 - q0), bool)
            fp[a0 - s0 : a1 - s0, b0 - q0 : b1 - q0] = fp_sl
            fp[lr[j] - s0, lc[j] - q0] = True  # the centroid's pixel belongs to it
            near = ndimage.maximum_filter(fp, size=2 * rad + 1, mode="constant")
            v = wse[s0:s1, q0:q1][near]
            v = v[np.isfinite(v)]
            n_wet[b] = v.size
            if v.size:
                level[b] = np.median(v)
        if time.time() - last > log_every:
            last = time.time()
            print(
                f"  pass1 tile group {k + 1}/{starts.size}  buildings {e}/{n}  "
                f"{last - t0:.0f} s",
                flush=True,
            )
    return dict(
        level=level, n_wet=n_wet, bare_c=bare_c, bare_fp=bare_fp, plain_c=plain_c,
        row=row, col=col,
    )  # fmt: skip


def pass2_fill(g, res, depth_src, bare_vrt, out_tif, tile):
    """Write the filled tif: footprint (+ centroid) pixels = level - bare (> HMIN)."""
    T = depth_src.transform
    H, W = depth_src.shape
    prof = depth_src.profile | dict(
        driver="GTiff", dtype="float32", nodata=np.nan, compress="DEFLATE",
        predictor=2, zlevel=6, tiled=True, blockxsize=512, blockysize=512,
        BIGTIFF="YES", NUM_THREADS="ALL_CPUS",
    )  # fmt: skip
    sidx = g.sindex
    level = res["level"]
    lvl = np.r_[np.nan, level]  # index 0 = not a building
    row, col = res["row"], res["col"]
    tmp = out_tif.with_name(f".{out_tif.name}.partial.{os.getpid()}.tif")
    n_fp_px = n_changed_in_fp = n_changed_outside = 0
    with rasterio.open(tmp, "w", **prof) as dst:
        for win in tiles(H, W, tile):
            d = depth_src.read(1, window=win, masked=True).filled(np.nan)
            ids, cand = _rasterize_ids(g, sidx, win, T)
            if cand.size:
                r0, c0 = int(win.row_off), int(win.col_off)
                inw = (
                    (row[cand] >= r0) & (row[cand] < r0 + win.height)
                    & (col[cand] >= c0) & (col[cand] < c0 + win.width)
                )  # fmt: skip
                cc = cand[inw]
                ids[row[cc] - r0, col[cc] - c0] = cc + 1
            fpm = ids > 0
            out = d.copy()
            if fpm.any():
                z = bare_vrt.read(1, window=win, masked=True).filled(np.nan)
                v = (lvl[ids] - z).astype("float32")
                with np.errstate(invalid="ignore"):
                    v = np.where(v > HMIN, v, np.float32(np.nan))
                out[fpm] = v[fpm]
                n_fp_px += int(fpm.sum())
                same = (out == d) | (np.isnan(out) & np.isnan(d))
                n_changed_in_fp += int((~same & fpm).sum())
            same = (out == d) | (np.isnan(out) & np.isnan(d))
            n_changed_outside += int((~same & ~fpm).sum())
            dst.write(out.astype("float32"), 1, window=win)
        dst.update_tags(
            ground="bare earth (buildings not burned)",
            buildings="footprint pixels = median wet street level within 50 m "
            "- bare ground (scripts/fiat_building_depth.py)",
        )
    with rasterio.open(tmp, "r+") as ds:
        ds.build_overviews([2, 4, 8, 16, 32, 64], Resampling.average)
        ds.update_tags(ns="rio_overview", resampling="average")
    os.replace(tmp, out_tif)
    return dict(
        footprint_pixels=n_fp_px,
        footprint_pixels_changed=n_changed_in_fp,
        pixels_changed_outside_footprints=n_changed_outside,
    )


README = """# Flood depth AT EACH BUILDING (for Delft-FIAT) — `{a.out_tif.name}`

**Preliminary.** Built from the plain bare-ground depth map `{a.depth.name}` (read its
README, `{a.plain_readme}`, for the model run, version, terrain year, CRS, scores and
caveats — all of it applies here) by `scripts/fiat_building_depth.py`.

## Why this file exists

The plain map measures depth from bare ground, but a building big enough to fill a whole
model cell still reads dry there even when the streets around it flood (the model has no
street-level water inside that cell). Here every building footprint gets the water of the
streets around it.

## The rule

- **Water level at a building** = the MEDIAN peak water level (m NAVD88) of the wet
  (depth >= 0.15 m) non-building pixels within 50 m of its footprint ({s[window_px]}
  pixels: a square window, the same median / 50 m estimator our high-water-mark scoring
  uses).
- **Depth** = that level − the bare ground (m NAVD88) at the building's centroid.
- In the GeoTIFF, every pixel inside a footprint (and each centroid's own pixel) holds
  level − bare ground at that pixel where that is above 0.05 m, else NaN (dry). **Pixels
  outside footprints are copied unchanged** from the plain map
  ({s[pixels_changed_outside_footprints]} pixels differ there).
- Footprints: **{a.source}** (`{a.footprints}`), {s[n_buildings]:,} buildings with a
  centroid in the grid.

## Files

| file | what |
|---|---|
| `{a.out_tif.name}` | the plain map with footprints filled — sample it at each building's centroid |
| `{a.out_csv.name}` | one row per building (below) |
| `{a.out_gpkg.name}` | the same table as centroid POINTS (EPSG:32618), for GIS |

Columns: `building_id` (the source's id: NJDEP `objectid`, or the hybrid layer's row id
`fid`), `source`, `x_utm18n` / `y_utm18n` (centroid, EPSG:32618 m), `level_m_navd88`,
`bare_ground_centroid_m`, `bare_ground_footprint_median_m`, `depth_m` (level − ground at
the centroid; negative = the street water stayed below this building's ground),
`n_wet_pixels` (how many street pixels the median used), `flag`, and the depth at the
centroid in the plain and the filled GeoTIFF.

`flag`: **wet** (depth >= 0.05 m), **dry** (street water within 50 m, but below the
building's ground), **no_wet_neighbour** (no wet street pixel within 50 m: depth NaN).

## Counts

| | buildings |
|---|---|
| wet (depth >= 0.05 m) | {s[n_wet]:,} (of which >= 0.15 m: {s[n_wet_ge_015]:,}) |
| dry | {s[n_dry]:,} |
| no wet street pixel within 50 m | {s[n_no_wet_neighbour]:,} |

Against the plain map at the centroid: {cv[nan_to_finite]:,} buildings went from blank to a
depth, {cv[finite_to_nan]:,} from a depth to blank, {cv[value_changed_gt_1cm]:,} changed by
more than 1 cm, {cv[unchanged]:,} unchanged. Median depth of the wet buildings:
{med}.

Questions to Ty.
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--depth", required=True, type=Path, help="plain bare-ground tif")
    ap.add_argument("--bare", required=True, type=Path, help="no-buildings merged bed")
    ap.add_argument("--footprints", required=True)
    ap.add_argument("--source", required=True, help="label for the footprint set")
    ap.add_argument("--out-tif", required=True, type=Path)
    ap.add_argument("--out-csv", required=True, type=Path)
    ap.add_argument("--out-gpkg", required=True, type=Path)
    ap.add_argument("--json", required=True, type=Path)
    ap.add_argument("--radius", type=float, default=50.0)
    ap.add_argument("--tile", type=int, default=2048)
    ap.add_argument("--readme", type=Path, default=None, help="write a README here")
    ap.add_argument(
        "--plain-readme", default="", help="name of the plain tif's README (linked)"
    )
    a = ap.parse_args(argv)

    t0 = time.time()
    with rasterio.open(a.depth) as src, rasterio.open(a.bare) as bsrc:
        T = src.transform
        if T.b != 0 or T.d != 0:
            raise SystemExit(f"{a.depth} is rotated: expected the north-up export")
        rad = int(round(a.radius / abs(T.a)))
        g = read_footprints(a.footprints, tuple(src.bounds))
        print(f"[{a.source}] {len(g):,} footprints with a centroid in the grid; "
              f"window +-{rad} px ({rad * abs(T.a):.2f} m)", flush=True)  # fmt: skip
        with WarpedVRT(
            bsrc, crs=src.crs, transform=T, width=src.width, height=src.height,
            resampling=Resampling.nearest, src_nodata=np.nan, nodata=np.nan,
        ) as vrt:  # fmt: skip
            res = pass1_levels(g, src, vrt, a.tile, rad)
            print(f"  pass1 done {time.time() - t0:.0f} s", flush=True)
            a.out_tif.parent.mkdir(parents=True, exist_ok=True)
            px = pass2_fill(g, res, src, vrt, a.out_tif, a.tile)
            print(f"  pass2 done {time.time() - t0:.0f} s  {px}", flush=True)

    depth = res["level"] - res["bare_c"]
    flag = np.where(
        res["n_wet"] == 0, "no_wet_neighbour", np.where(depth >= HMIN, "wet", "dry")
    )
    with rasterio.open(a.out_tif) as f:
        filled_c = np.array(
            [v[0] for v in f.sample(zip(g["xc"].to_numpy(), g["yc"].to_numpy()))], float
        )
    tab = pd.DataFrame(
        dict(
            building_id=g.building_id.to_numpy(),
            source=a.source,
            x_utm18n=g["xc"].round(2).to_numpy(),
            y_utm18n=g["yc"].round(2).to_numpy(),
            level_m_navd88=np.round(res["level"], 3),
            bare_ground_centroid_m=np.round(res["bare_c"], 3),
            bare_ground_footprint_median_m=np.round(res["bare_fp"], 3),
            depth_m=np.round(np.where(res["n_wet"] > 0, depth, np.nan), 3),
            n_wet_pixels=res["n_wet"],
            flag=flag,
            plain_tif_depth_at_centroid_m=np.round(res["plain_c"], 3),
            filled_tif_depth_at_centroid_m=np.round(filled_c, 3),
        )
    )
    for p in (a.out_csv, a.out_gpkg):
        p.parent.mkdir(parents=True, exist_ok=True)
    tmp = a.out_csv.with_name(f".{a.out_csv.name}.partial")
    tab.to_csv(tmp, index=False)
    os.replace(tmp, a.out_csv)
    gp = gpd.GeoDataFrame(
        tab, geometry=gpd.points_from_xy(g["xc"], g["yc"]), crs="EPSG:32618"
    )
    tmp = a.out_gpkg.with_name(f".{a.out_gpkg.name}.partial.gpkg")
    gp.to_file(tmp, layer="buildings", driver="GPKG", engine="pyogrio")
    os.replace(tmp, a.out_gpkg)

    pf, ff = np.isfinite(res["plain_c"]), np.isfinite(filled_c)
    with np.errstate(invalid="ignore"):
        changed_val = pf & ff & (np.abs(filled_c - res["plain_c"]) > 0.01)
    summary = dict(
        source=a.source,
        footprints=a.footprints,
        n_buildings=int(len(g)),
        n_wet=int((flag == "wet").sum()),
        n_wet_ge_015=int(((flag == "wet") & (depth >= WET)).sum()),
        n_dry=int((flag == "dry").sum()),
        n_no_wet_neighbour=int((flag == "no_wet_neighbour").sum()),
        centroid_vs_plain=dict(
            nan_to_finite=int((~pf & ff).sum()),
            finite_to_nan=int((pf & ~ff).sum()),
            value_changed_gt_1cm=int(changed_val.sum()),
            unchanged=int(
                len(g) - (~pf & ff).sum() - (pf & ~ff).sum() - changed_val.sum()
            ),
        ),
        median_depth_wet_m=float(np.nanmedian(depth[flag == "wet"]))
        if (flag == "wet").any()
        else None,
        **px,
        radius_m=a.radius,
        window_px=rad,
        seconds=round(time.time() - t0),
    )
    summary["pass_open_ground_unchanged"] = px["pixels_changed_outside_footprints"] == 0
    a.json.write_text(json.dumps(summary, indent=2))
    if a.readme:
        m = summary["median_depth_wet_m"]
        med = "n/a" if m is None else f"{m:.2f} m"
        a.readme.write_text(
            README.format(a=a, s=summary, cv=summary["centroid_vs_plain"], med=med)
        )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
