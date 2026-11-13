"""Export a share-ready maximum-flood-depth GeoTIFF for an external collaborator.

WHY THIS EXISTS — neither run artifact is the right file to hand out
--------------------------------------------------------------------
* ``experiments/<domain>/<arm>/floodmap_hmax_lev3.tif`` is UNMASKED (the full water
  column of the bay and ocean — a damage model pointed at it computes losses across
  the Atlantic) and it is on the ROTATED quadtree frame (CLAUDE.md §5: ``x0 + col*res``
  is wrong by up to 3 km).
* ``experiments/<domain>/floodmaps/<arm>_hmax_lev3.tif`` (the gallery tif written by
  ``validate.evaluate``) is north-up and has permanent water dropped, but it is
  uncompressed (2.5 GB), leaves ``nodata`` UNTAGGED, and still carries the
  ``downscale_floodmap`` BLEED — water painted onto low ground under faces the solver
  never simulated (FINDINGS §37).

This script starts from the gallery tif and additionally:
  * drops the bleed with ``validate.simulated_mask`` (the run's own ``msk``),
  * tags ``nodata`` explicitly, DEFLATE-compresses, tiles, builds overviews,
  * writes a README beside it recording CRS, units, thresholds, the scored bias
    (with its estimator and radius — never without) and the model's caveats.

``--ground <subgrid dir>`` (2026-10-29, for FIAT): measure depth from BARE ground. The
run's own bed raises every building footprint 4 m (FINDINGS §55), so its depth map is NaN
on every building, and a damage model that reads depth AT a building (FIAT, centroid or
footprint) scores it undamaged — the v3 export biased the student's damages low. With
``--ground`` the run's face ``zsmax`` (the water in the streets around the buildings) is
downscaled onto that dir's ``subgrid/dep_subgrid_merged.tif`` instead — the same bed
recipe without the burn, on the same lattice (asserted) — so a footprint carries the
depth against its building. The hydrodynamics stay the run's, buildings included. On v4:
    --ground experiments/v4_refreeze/_subgrid_refreeze_lakes_min_nobuildings_creeks_cohansey
v4's merged bed is ~4x v3's pixels: give it a big-memory node. Since 2026-11-13 the
downscale and every bed read are on the bed's BASE band (3.125 m on v4;
``validate.core.downscale_floodmap_native``): hydromt's path-mode downscale and a
rasterio overview-level-0 read both use the FIRST OVERVIEW (6.25 m), which averages
buildings into the streets beside them (``logs/floodmap_fix_2026-11-12/README.md``).
The de-rotation goes onto an EXPLICIT north-up lattice (``north_up_grid``): the bed's
own pixel size (3.125 m on v4), on absolute multiples of it, over the bounding box of the
run's ACTIVE faces — i.e. a sub-window of ``bed_buildings_v4_cap10``'s lattice. Until
2026-11-13 ``rio.reproject(crs)`` chose the grid itself: it kept the rotated raster's
SHAPE and top-left corner, so it clipped a wedge off the west and north edges (176 active
v4 faces) and its pixel was not exactly the bed's. FIAT export: logs/fiat_geotiffs_2026-11-13/.

The CRS stays the model's native UTM 18N (metres). Reproject downstream if degrees are
needed; doing it here would resample depths for no reason.

Run on a compute node (the raster is 620 M px; ~6 GB RSS), e.g.
    NJ_DOMAIN=v3 PYTHONPATH=$PWD python scripts/export_share_floodmap.py \
        --arm mask-drain-edge+naccs-premier
"""

from __future__ import annotations

import argparse
import math
import os
from datetime import date
from pathlib import Path

import netCDF4
import numpy as np
import pandas as pd
import rasterio
import rioxarray
import xarray as xr
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject, transform_bounds
from rasterio.windows import Window
from scipy.spatial import cKDTree

import nj_sfincs  # noqa: F401  (PROJ primer — must precede hydromt_sfincs)
from nj_sfincs import domain, validate
from nj_sfincs.config import ROOT, exp_root
from nj_sfincs.validate.core import downscale_floodmap_native, open_run

DEFAULT_OUT = ROOT / "share"
HMIN = 0.05  # the downscale floor, as validate.load_floodmap
# A building-heavy face is roof rain, not flood, when its water stands this far above the open
# ground around it (bare_ground_hmax; 2026-10-30, logs/fiat_export_2026-10-30/).
ROOF_COVER, OPEN_COVER, ALL_ROOF_COVER = 0.25, 0.25, 0.9
ROOF_EXCESS_M, OPEN_RADIUS_M = 1.0, 100.0


def roof_rain_faces(
    model_dir: Path, ground: Path, zsmax: np.ndarray, wet: np.ndarray
) -> np.ndarray:
    """Faces whose ``zsmax`` is rain held by a building, not water from outside it.

    A face a building ALMOST covers keeps a sliver of low ground, so its lowest pixel looks
    like street and the fully-covered test misses it; the rain on its roof area drains into
    that sliver and fills it towards roof height (Atlantic City, 2026-10-30: 11.76 m NAVD88
    with 0.5 m in the streets). Cover = the burn's rise in mean ground / the roof's rise in top
    ground. Dropped: cover >= ``ROOF_COVER`` with water > ``ROOF_EXCESS_M`` above the median of
    the wet open faces (cover < ``OPEN_COVER``) within ``OPEN_RADIUS_M``, and cover >=
    ``ALL_ROOF_COVER`` with no open face that close to compare against.
    """
    with netCDF4.Dataset(model_dir / "sfincs.nc") as m:
        dx = float(m.getncattr("dx"))
        area = (dx / 2.0 ** (m["level"][:].filled(1) - 1)) ** 2
    tab = {}
    for k, p in (("own", model_dir), ("bare", Path(ground))):
        with netCDF4.Dataset(p / "sfincs_subgrid.nc") as n:
            zmax = np.ma.filled(n["z_zmax"][:], np.nan)
            tab[k] = zmax, zmax - np.ma.filled(n["z_volmax"][:], np.nan) / area
    roof = tab["own"][0] - tab["bare"][0]
    cover = np.where(
        roof > 0.5,
        np.clip((tab["own"][1] - tab["bare"][1]) / np.maximum(roof, 0.5), 0, 1),
        0.0,
    )
    with netCDF4.Dataset(model_dir / "sfincs_map.nc") as m:
        fn = m["mesh2d_face_nodes"]
        nodes = np.ma.filled(fn[:], -1).astype("int64") - int(
            getattr(fn, "start_index", 0)
        )
        x = np.ma.filled(m["mesh2d_node_x"][:], np.nan)[nodes].mean(axis=1)
        y = np.ma.filled(m["mesh2d_node_y"][:], np.nan)[nodes].mean(axis=1)
    open_ = np.flatnonzero(wet & (cover < OPEN_COVER))
    cand = np.flatnonzero(wet & (cover >= ROOF_COVER))
    near = cKDTree(np.c_[x[open_], y[open_]]).query_ball_point(
        np.c_[x[cand], y[cand]], r=OPEN_RADIUS_M
    )
    drop = np.zeros(zsmax.shape, bool)
    for f, i in zip(cand, near):
        if i:
            drop[f] = zsmax[f] - np.median(zsmax[open_[i]]) > ROOF_EXCESS_M
        else:
            drop[f] = cover[f] >= ALL_ROOF_COVER
    return drop


def snap_grid(bounds, res: float):
    """North-up lattice on ABSOLUTE multiples of ``res`` covering ``bounds`` (l, b, r, t).

    Returns ``(transform, (height, width))``. On v4 at 3.125 m this is the lattice of
    ``bed_buildings_v4_cap10`` (origin 434912.5 / 4539271.875), so every export lines up
    pixel for pixel with the building burn and with each other.
    """
    left, bottom, right, top = bounds
    x0, x1 = math.floor(left / res) * res, math.ceil(right / res) * res
    y0, y1 = math.floor(bottom / res) * res, math.ceil(top / res) * res
    width, height = int(round((x1 - x0) / res)), int(round((y1 - y0) / res))
    return from_origin(x0, y1, res, res), (height, width)


def lattice_res(transform) -> float:
    """Pixel size of a (possibly rotated) lattice, rounded to the millimetre (3.125 on v4)."""
    return round(math.hypot(transform.a, transform.d), 3)


def active_bounds(model_dir: Path) -> tuple[float, float, float, float]:
    """Bounding box of the run's ACTIVE faces (``msk > 0``, node geometry of the map)."""
    with netCDF4.Dataset(Path(model_dir) / "sfincs_map.nc") as m:
        msk = np.ma.filled(m["msk"][:], 0)
        fn = m["mesh2d_face_nodes"]
        nodes = np.ma.filled(fn[np.flatnonzero(msk > 0)], -1).astype("int64") - int(
            getattr(fn, "start_index", 0)
        )
        nx = np.ma.filled(m["mesh2d_node_x"][:], np.nan)
        ny = np.ma.filled(m["mesh2d_node_y"][:], np.nan)
    nodes = np.unique(nodes[nodes >= 0])
    return (
        float(np.nanmin(nx[nodes])),
        float(np.nanmin(ny[nodes])),
        float(np.nanmax(nx[nodes])),
        float(np.nanmax(ny[nodes])),
    )


def north_up_grid(model_dir: Path, bed: Path):
    """The export lattice: the bed's pixel size, absolute multiples, active-face bbox."""
    with rasterio.open(bed) as b:
        res = lattice_res(b.transform)
    return snap_grid(active_bounds(model_dir), res)


def derotate(fn: Path, transform, shape, threads: int | None = None) -> xr.DataArray:
    """De-rotate ``fn`` (NEAREST, NaN nodata) onto the north-up ``transform`` / ``shape``.

    GDAL warps straight from the file band, so only the destination is held in memory
    (v4: ~16 GB at 3.125 m), not the rotated source as well.
    """
    dst = np.full(shape, np.nan, dtype="float32")
    with rasterio.open(fn) as src:
        crs = src.crs
        reproject(
            source=rasterio.band(src, 1),
            destination=dst,
            src_nodata=np.nan,
            dst_transform=transform,
            dst_crs=crs,
            dst_nodata=np.nan,
            resampling=Resampling.nearest,
            num_threads=threads or len(os.sched_getaffinity(0)),
            warp_mem_limit=2048,
        )
    h, w = shape
    x = transform.c + (np.arange(w) + 0.5) * transform.a
    y = transform.f + (np.arange(h) + 0.5) * transform.e
    da = xr.DataArray(dst, dims=("y", "x"), coords={"y": y, "x": x})
    return da.rio.write_crs(crs).rio.write_transform(transform)


def bare_ground_hmax(model_dir: Path, ground: Path) -> tuple[xr.DataArray, dict]:
    """North-up peak depth from BARE ground (module docstring, ``--ground``), with
    permanent water dropped as the gallery tif does, plus a footprint count.

    Everything is on the beds' BASE band (2026-11-13): the downscale is
    ``downscale_floodmap_native`` (hydromt's block loop and arithmetic on the full-resolution
    bed), and the water mask and the footprint count read the base band too, strip by strip
    on the rotated lattice (asserted), before one de-rotation onto ``north_up_grid``
    (``derotate``: only the destination in memory). Until 2026-11-13 all three used the bed's first
    OVERVIEW (6.25 m on v4); reading the two 3.125 m beds whole was OOM-killed at 250 G (job
    63237278, 2026-10-29), hence the strips. The downscale is cached atomically beside the
    gallery tifs (scratch) and reused while newer than the run and the bed; the cache name
    carries ``_native`` so a pre-fix 6.25 m cache is never reused, and the ground dir's
    name, so a second bare bed for the same arm never reads the first one's map.
    """
    own = model_dir / "subgrid" / "dep_subgrid_merged.tif"
    bare = Path(ground) / "subgrid" / "dep_subgrid_merged.tif"
    with rasterio.open(own) as o, rasterio.open(bare) as b:
        if (o.shape, o.transform, o.crs) != (b.shape, b.transform, b.crs):
            raise SystemExit(f"{bare} is not on the run's subgrid lattice ({own})")
    # on scratch, not beside the share file: the rotated raster is GBs and home is GPFS-tight
    cache = (
        exp_root()
        / "floodmaps"
        / f".{model_dir.name}_bare_{Path(ground).name}_hmax_native.tif"
    )
    newest = max((model_dir / "sfincs_map.nc").stat().st_mtime, bare.stat().st_mtime)
    if not (cache.is_file() and cache.stat().st_mtime >= newest):
        zsmax = open_run(model_dir).output.data["zsmax"].max(dim="timemax")
        # Two kinds of face have no street-level water to measure a building against, and
        # read as PHANTOM depth on bare ground (2026-10-29: 9.5 m on Atlantic City / Newark
        # roofs): a face the burn covers ENTIRELY (its lowest pixel = a roof, ~10 m above the
        # bare bed; its zsmax = rain on that roof), and a face that never got wet (zsmax
        # within hmin of its lowest pixel; the gallery tif is blank there anyway). Both are
        # dropped before the downscale, so a fully covered building stays blank.
        zmin = {}
        for k, p in (("own", model_dir), ("bare", Path(ground))):
            with netCDF4.Dataset(p / "sfincs_subgrid.nc") as n:
                zmin[k] = np.ma.filled(n["z_zmin"][:], np.nan)
        if zmin["own"].shape != zsmax.shape:
            raise SystemExit("sfincs_subgrid.nc is not in the map's face order")
        covered = (zmin["own"] - zmin["bare"]) > 0.5
        dry = ~((zsmax.values - zmin["own"]) >= HMIN)
        roof_rain = roof_rain_faces(model_dir, ground, zsmax.values, ~covered & ~dry)
        print(
            f"[bare ground] faces dropped: {int(covered.sum())} fully covered by buildings "
            f"({int((covered & ~dry).sum())} with water on the roof), "
            f"{int((dry & ~covered).sum())} dry, {int(roof_rain.sum())} holding roof rain",
            flush=True,
        )
        zsmax = zsmax.where(~covered & ~dry & ~roof_rain)
        tmp = cache.with_name(
            f"{cache.stem}.partial.{os.getpid()}.tif"
        )  # .tif: build_overviews asserts it; pid: two exports never share a temp
        cache.parent.mkdir(parents=True, exist_ok=True)
        downscale_floodmap_native(zsmax, bare, tmp, hmin=HMIN, nrmax=1000)
        os.replace(
            tmp, cache
        )  # atomic: a truncated depth map reads back clean (CLAUDE §5)
    # permanent water out + the footprint count, strip by strip on the base band
    masked = cache.with_name(f"{cache.stem}.masked.{os.getpid()}.tif")
    n_fp = n_fp_wet = 0
    with (
        rasterio.open(cache) as h,
        rasterio.open(bare) as b,
        rasterio.open(own) as o,
    ):
        same = h.shape == b.shape and np.allclose(
            tuple(h.transform), tuple(b.transform), rtol=0, atol=1e-6
        )
        if not same:
            raise SystemExit(f"{cache} is not on {bare}'s base lattice")
        prof = h.profile | dict(
            nodata=np.nan, compress="DEFLATE", BIGTIFF="YES", tiled=True
        )
        with rasterio.open(masked, "w", **prof) as dst:
            step = 2048
            for r0 in range(0, h.height, step):
                w = Window(0, r0, h.width, min(step, h.height - r0))
                a = h.read(1, window=w, masked=True).filled(np.nan)
                dep_b = b.read(1, window=w, masked=True).filled(np.nan)
                # footprint = where the burn raised the bed (the recipes differ only there)
                fp = (o.read(1, window=w, masked=True).filled(np.nan) - dep_b) > 0.5
                a[~(dep_b > -0.5)] = np.nan  # drop deep ocean, as load_floodmap does
                n_fp += int(fp.sum())
                n_fp_wet += int((fp & (a >= validate.DEPTH_MIN)).sum())
                dst.write(a.astype("float32"), 1, window=w)
    stats = dict(n_footprint=n_fp, n_footprint_wet=n_fp_wet)
    try:
        # de-rotate to north-up (CLAUDE.md §5), on the explicit lattice
        da = derotate(masked, *north_up_grid(model_dir, bare))
    finally:
        masked.unlink(missing_ok=True)
    return da, stats


def export(arm: str, out_tif: Path, ground: Path | None = None) -> dict:
    root = exp_root()
    gallery = root / "floodmaps" / f"{arm}_hmax_lev3.tif"
    model_dir = root / arm
    if not (model_dir / "sfincs_map.nc").is_file():
        raise SystemExit(f"no sfincs_map.nc under {model_dir}")
    fp_stats = {}
    if ground is None:
        if not gallery.is_file():
            raise SystemExit(f"no gallery tif for {arm!r}: {gallery}")
        da = rioxarray.open_rasterio(gallery, masked=True).squeeze(drop=True).load()
        bed = model_dir / "subgrid" / "dep_subgrid_merged.tif"
        if bed.is_file():
            with rasterio.open(bed) as b:
                coarse = abs(da.rio.resolution()[0]) > 1.5 * abs(b.res[0])
            if coarse:  # warn, never gate: a pre-2026-11-12 gallery tif
                print(
                    f"WARNING: {gallery.name} is {abs(da.rio.resolution()[0]):.3f} m, the "
                    f"bed {abs(b.res[0]):.3f} m: a first-overview floodmap (pre-11-12); "
                    "re-validate the arm for the native map",
                    flush=True,
                )
    else:
        da, fp_stats = bare_ground_hmax(model_dir, ground)
    a = da.values.astype("float32", copy=False)
    n_before = int(np.isfinite(a).sum())

    # The bleed: keep only cells under faces the solver integrated.
    sim = validate.simulated_mask(model_dir, a.shape, da.rio.transform())
    a[~sim] = np.nan
    n_after = int(np.isfinite(a).sum())
    px_km2 = abs(da.rio.resolution()[0] * da.rio.resolution()[1]) / 1e6
    da.values = a

    da = da.rio.write_nodata(np.nan, encoded=False)
    da.name = "max_flood_depth_m"
    da.attrs.update(
        long_name="Maximum flood depth over the simulation",
        units="m",
        note="permanent water (subgrid bed <= -0.5 m) and unsimulated ground masked; "
        "NaN = dry / no data",
        ground="bare earth (buildings not burned)" if ground else "model bed",
    )

    out_tif.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_tif.with_name(f".{out_tif.name}.partial.tif")
    da.rio.to_raster(
        tmp,
        driver="GTiff",
        dtype="float32",
        compress="DEFLATE",
        # horizontal differencing: lossless on float32 and read by every GDAL / libtiff;
        # the float predictor (3) compresses a little better but older readers refuse it
        predictor=2,
        zlevel=6,
        tiled=True,
        blockxsize=512,
        blockysize=512,
        BIGTIFF="YES",
        NUM_THREADS="ALL_CPUS",
    )
    with rasterio.open(tmp, "r+") as ds:
        ds.build_overviews([2, 4, 8, 16, 32, 64], Resampling.average)
        ds.update_tags(ns="rio_overview", resampling="average")
    os.replace(tmp, out_tif)  # atomic: the share file is absent or complete

    fin = a[np.isfinite(a)]
    wet = fin[fin >= validate.DEPTH_MIN]
    with rasterio.open(out_tif) as ds:
        b = ds.bounds
        ll = transform_bounds(ds.crs, "EPSG:4326", *b)
        stats = dict(
            crs=str(ds.crs),
            epsg=ds.crs.to_epsg(),
            width=ds.width,
            height=ds.height,
            res=ds.res[0],
            nodata=ds.nodata,
            bounds=tuple(round(v, 1) for v in b),
            lonlat=tuple(round(v, 4) for v in ll),
            mb=out_tif.stat().st_size / 1e6,
            n_finite=int(fin.size),
            pct_finite=100 * fin.size / a.size,
            km2_finite=fin.size * px_km2,
            km2_bleed=(n_before - n_after) * px_km2,
            dmin=float(fin.min()),
            dmax=float(fin.max()),
            n_ge_015=int(wet.size),
            km2_ge_015=wet.size * px_km2,
            p50=float(np.percentile(wet, 50)),
            p99=float(np.percentile(wet, 99)),
            **fp_stats,
        )
    return stats


def score_row(arm: str) -> dict:
    """The arm's scored row — bias WITH estimator and radius, never without."""
    csv = exp_root() / "metrics.csv"
    m = pd.read_csv(csv, index_col=0)
    if arm not in m.index:
        return {}
    r = m.loc[arm]
    return dict(
        hwm_bias=float(r["hwm_bias_scored_m"]),
        hwm_rmse=float(r["hwm_rmse_scored_m"]),
        hwm_n=int(r["hwm_n_scored"]),
        hwm_estimator=str(r["hwm_estimator"]),
        hwm_radius=float(r["hwm_radius_m"]),
        motf_csi=float(r["motf_csi"]),
        motf_pod=float(r["motf_pod"]),
        motf_far=float(r["motf_far"]),
        motf_excl=float(r.get("motf_km2_excluded_boxes", float("nan"))),
        engine=str(r["engine"]),
        waves="on" if bool(r["extent_admissible"]) else "off",
    )


README = """# {title} — New Jersey coast, model {domain}

`{fname}`

Modelled maximum water depth during {event} over {scope}
{event_text} **This is a PRELIMINARY working dataset from a model still under
development, not a validated hazard layer** — read the caveats before drawing any
conclusion from it.

Model run: domain `{domain}`, experiment `{arm}`, exported {today}.

| | |
|---|---|
| Model version | {model_version} |
| Ground (terrain) | {ground_desc} |
| Depth measured from | {depth_from} |
| Resolution | {res:.3f} m, the model's native sub-grid terrain pixel (north-up, not rotated) |
| NaN means | dry, permanent water, or ground the model did not simulate |
| Status | **Preliminary** |
{supersedes}
## Reading the file

| | |
|---|---|
| Format | GeoTIFF, single band, float32, DEFLATE-compressed, tiled, with overviews |
| **CRS** | **EPSG:{epsg}** — UTM zone 18N, coordinates in **metres**, *not* degrees |
| Resolution | {res:.3f} m |
| Size | {width} x {height} px, {mb:.0f} MB |
| NoData | NaN (tagged in the header) — dry land, permanent water, and ground outside the model |
| Units | metres of water depth above the ground surface |

The CRS is the one thing most likely to trip you up. Opening this expecting lat/lon
gives corner coordinates like `501136, 4497255`; that is not corruption, it is UTM in
metres. QGIS, ArcGIS and rasterio all reproject on the fly. If you need degrees
(EPSG:4326) say so and I will ship a reprojected copy — better that than resampling
depths yourself.

Extent: `{bounds}` in UTM, which is `{lonlat}` as (west, south, east, north) in degrees.

```python
import rioxarray
da = rioxarray.open_rasterio("{fname}", masked=True).squeeze()
da = da.where(da >= 0.15)          # see "wet threshold" below
# da.rio.reproject("EPSG:4326")    # only if you actually need degrees
```

The file has overviews, so it opens instantly in QGIS at any zoom. Reading the full
band into memory takes about {gb:.1f} GB.

## What the values mean

- **Depth above ground**, not water-surface elevation. No datum conversion needed to
  use it as depth; it is already ground-relative.
- **Maximum over the whole storm**, not a snapshot. Different cells peak at different
  times, so the map is not a state the system was ever in at one instant. That is
  normally what a damage model wants, but it is worth knowing.
- **Permanent water is masked out.** Bay, river and ocean cells are NaN, so the raster
  shows flooding on land rather than the full water column.
- **Only ground the model actually simulated is kept.** The downscaling step paints
  water onto low ground just outside the model's active cells; those cells
  ({km2_bleed:.1f} km²) have been removed.

Wet cells: {n_finite:,} ({km2_finite:.0f} km², {pct_finite:.2f}% of the grid rectangle);
depth range {dmin:.2f} to {dmax:.2f} m. At or above the 0.15 m threshold:
{n_ge_015:,} cells ({km2_ge_015:.0f} km²), median depth {p50:.2f} m, 99th percentile
{p99:.2f} m.

### Wet threshold

The raster floor is **0.05 m** (an artifact of how the downscale is built). Our own
scoring treats a cell as wet only at **>= 0.15 m**. Below that you are looking at
numerical damp rather than flooding, and most damage curves will happily assign losses
to it. **Threshold at 0.15 m** unless you have a specific reason not to. The 0.05 m
values are left in rather than silently deleted, so the choice stays yours.

## How good is it?

{score_block}

## Caveats — please read before trusting a number

{event_caveats}
{regional}
5. **Depth only.** No velocity, no duration, no wave runup on the beach face, no
   debris — all of which matter for real damage estimation.
6. {buildings_note}

Off building footprints the ground is the model's own, so there the depths are the
model's normal flood map, pixel for pixel; only the footprints differ.

Questions to Ty.
"""


SANDY_TITLE = "Hurricane Sandy (2012) maximum flood depth"
SANDY_EVENT = "Hurricane Sandy (28–31 Oct 2012)"
SANDY_TEXT = """SFINCS compound-flood hindcast: storm surge, wave setup, wind, rain and river
discharge together."""
SANDY_CAVEATS = """1. **Known low bias.** Against surveyed USGS high-water marks this run reads low on
   average (numbers above). Damages computed from it will be *under*-estimates, and
   non-linearly so, because damage curves are steep near the low end.
2. **Hindcast, not a design event.** This is one storm reconstructed after the fact.
   It is not a return-period product and must not be read as one."""


# What the map covers and where it is weak: a per-MESH fact (v3 vs v4), keyed on the domain
# name's prefix. The v4 weak spots are the swz premier's marks (FINDINGS §63, 2026-10-29).
SCOPE = {
    "v3": dict(
        scope="""the whole
New Jersey ocean coast — Cape May to Raritan Bay and the Verrazzano Narrows, including
the back bays, the Delaware Bay shore near Cape May, and the Staten Island shore of
Lower Bay.""",
        regional="""3. **Model still in development, and lowest in the NY bays.** Raritan Bay, Sandy Hook
   Bay and the Arthur Kill still read about 0.1–0.2 m low against surveyed marks —
   more than the coast-wide figure above. Treat depths north of Sandy Hook as a floor.
   South of Sandy Hook the ocean coast and back bays are the better-scored part of the
   map.
4. **New York land is out of scope.** The Staten Island and Brooklyn shorelines are
   in the grid only as the model's northern edge; do not read flooding there as a
   result. Jamaica Bay and Manhattan are not modelled at all.""",
    ),
    "v4": dict(
        scope="""the New
Jersey coast and its tidal waters — the ocean coast from Cape May to the Verrazzano
Narrows with its back bays; Lower, Raritan and Sandy Hook Bays; the Arthur Kill and
Newark Bay; the tidal Raritan; and Delaware Bay with the tidal Delaware River. The far
shores (Delaware, Pennsylvania, Staten Island) are computed as part of those waters.""",
        regional="""3. **Where it is weakest.** A few places are known to read low against surveyed marks:
   the Monmouth County coastal lakes (Deal Lake, Wreck Pond and their neighbours) by
   about 0.7–2.3 m — in Sandy they filled through dune breaches and overwash that the
   model reproduces only in part, so treat depths around them as a floor — and Cape
   May's back bays by about 0.3 m. Delaware Bay and the tidal Delaware are checked
   against only three marks: the least-tested part of the map. Raritan Bay, Sandy Hook
   Bay and the Arthur Kill, weak in earlier versions, now score like the ocean coast.
4. **Outside New Jersey, and upriver, is out of scope.** The Staten Island, Brooklyn,
   Delaware and Pennsylvania shores are in the grid so the bays and rivers behave
   correctly, but the FEMA extent the model is scored against is New Jersey only, so
   flooding there is unchecked. Each river stops at its present-day head of tide (the
   Cohansey and Neshaminy reach a little further); ground upstream is not modelled.
   **The Hudson waterfront and the Upper Bay shore are outside the model:** Hoboken, the
   east side of Jersey City and Bayonne's Upper Bay side are blank because they were not
   simulated, NOT because they stayed dry. Sandy flooded them badly, so exclude them from
   any damage total rather than counting them as undamaged.""",
    ),
}


def _score_block(s: dict) -> str:
    if not s:
        return "(no scored row found for this arm in metrics.csv)"
    return (
        f"- **High-water marks:** {s['hwm_n']} USGS marks scored; bias "
        f"**{s['hwm_bias']:+.2f} m**, RMSE {s['hwm_rmse']:.2f} m "
        f"({s['hwm_estimator']} estimator, {s['hwm_radius']:.0f} m search radius — "
        "the bias depends on both, so always quote them with it).\n"
        f"- **FEMA flood extent (MOTF):** critical success index {s['motf_csi']:.2f}, "
        f"probability of detection {s['motf_pod']:.2f}, false-alarm ratio "
        f"{s['motf_far']:.2f}. The FEMA layer covers New Jersey only; "
        f"{s['motf_excl']:.0f} km² of New York shore is excluded from the score.\n"
        f"- Waves {s['waves']}; solver build `{s['engine']}`."
    )


BUILDINGS_BED = """**Buildings are burned into the terrain** (footprints raised), so depths inside
   footprints are NaN or shallow by construction; read depth at the building's
   perimeter, not its centroid. **A FIAT run reading depth at the building will score
   most flooded buildings as undamaged** (footprints are mostly blank here), so a damage drop against that map is mostly this blank-map effect.
   Both maps share one water surface: comparing them does not test a change to the model's
   bed; that takes two runs with different beds, read with the same depth method. A few cells beside large buildings are too deep: rain on
   a roof drains into the sliver of ground left in that model cell (up to ~15 m near Port
   Newark, ~10 m in Atlantic City). They are kept here as the model has them; the bare-ground map drops them."""

BUILDINGS_BARE = """**Depth is measured from the BARE ground, buildings included.** The model
   represents buildings as raised ground that water flows around; this map takes the
   peak water level around each building and subtracts the bare ground under it, so a
   footprint carries the depth of water against that building — read it at the
   centroid or over the footprint, and subtract the first-floor height as usual.
   {n_footprint_wet:,} of {n_footprint:,} footprint pixels are wet (>= 0.15 m). A
   building large enough to fill a whole model cell can still read dry, and so can one
   that fills most of a cell where the only water in the model is rain off its own roof.
   For a damage model use the companion `..._buildings_...` GeoTIFF and per-building
   table when they ship beside this file (`scripts/fiat_building_depth.py`): they give
   every footprint the median water level of the streets within 50 m."""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--arm", required=True, help="experiment name on the active domain")
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--stem", default=None, help="default sandy_hmax_<domain>_<arm>")
    ap.add_argument(
        "--ground",
        type=Path,
        default=None,
        help="subgrid dir of the bare-earth bed: depth from bare ground (for FIAT)",
    )
    # README wording (defaults = the Sandy hindcast). A text value starting with @ is read
    # from that file.
    ap.add_argument("--model-version", default="not stated", help="e.g. 1.1.0")
    ap.add_argument(
        "--ground-desc",
        default=None,
        help="the terrain, e.g. '2012 (the Sandy-era bed)' (default: from --ground)",
    )
    ap.add_argument("--title", default=SANDY_TITLE)
    ap.add_argument("--event", default=SANDY_EVENT, help="'... during <event> over'")
    ap.add_argument("--event-text", default=SANDY_TEXT, help="what was modelled")
    ap.add_argument("--event-caveats", default=SANDY_CAVEATS, help="caveats 1-2")
    ap.add_argument("--supersedes", default="", help="file name(s) this one replaces")
    a = ap.parse_args()
    for k in (
        "model_version",
        "ground_desc",
        "title",
        "event",
        "event_text",
        "event_caveats",
    ):
        v = getattr(a, k)
        if isinstance(v, str) and v.startswith("@"):
            setattr(a, k, Path(v[1:]).read_text().strip())

    dom = domain.active().name
    stem = a.stem or (
        f"sandy_hmax_{dom}_{a.arm.replace('+', '_')}" + ("_bareground" * bool(a.ground))
    )
    out_tif = a.out_dir / f"{stem}_EPSG32618.tif"
    print(f"domain : {dom}\narm    : {a.arm}\ntarget : {out_tif}", flush=True)

    st = export(a.arm, out_tif, a.ground)
    sc = score_row(a.arm)

    readme = a.out_dir / f"{stem}_README.md"
    readme.write_text(
        README.format(
            fname=out_tif.name,
            domain=dom,
            arm=a.arm,
            today=date.today().isoformat(),
            score_block=_score_block(sc),
            title=a.title,
            event=a.event,
            event_text=a.event_text,
            event_caveats=a.event_caveats,
            model_version=a.model_version,
            ground_desc=a.ground_desc
            or (
                f"bare earth from `{a.ground.name}` (the run's terrain recipe without "
                "the building burn)"
                if a.ground
                else "the run's own terrain (buildings raised)"
            ),
            depth_from=(
                "**bare ground** (buildings removed) — read at a building's centroid"
                if a.ground
                else "the model's terrain, buildings raised (blank on most footprints)"
            ),
            supersedes=(
                f"\nSupersedes `{a.supersedes}` (older model / coarser pixels).\n"
                if a.supersedes
                else ""
            ),
            buildings_note=(BUILDINGS_BARE.format(**st) if a.ground else BUILDINGS_BED),
            gb=st["width"] * st["height"] * 4 / 1e9,
            **SCOPE[dom[:2]],
            **st,
        )
    )

    print("\n=== written ===")
    for k, v in {**st, **sc}.items():
        print(f"  {k:14s} {v}")
    print(f"\n  {out_tif}\n  {readme}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
