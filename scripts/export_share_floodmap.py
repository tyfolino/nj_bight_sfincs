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

The CRS stays the model's native UTM 18N (metres). Reproject downstream if degrees are
needed; doing it here would resample depths for no reason.

Run on a compute node (the raster is 620 M px; ~6 GB RSS), e.g.
    NJ_DOMAIN=v3 PYTHONPATH=$PWD python scripts/export_share_floodmap.py \
        --arm mask-drain-edge+naccs-premier
"""

from __future__ import annotations

import argparse
import os
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
import rioxarray
from rasterio.enums import Resampling
from rasterio.warp import transform_bounds

import nj_sfincs  # noqa: F401  (PROJ primer — must precede hydromt_sfincs)
from nj_sfincs import domain, validate
from nj_sfincs.config import ROOT, exp_root

DEFAULT_OUT = ROOT / "share"


def export(arm: str, out_tif: Path) -> dict:
    root = exp_root()
    gallery = root / "floodmaps" / f"{arm}_hmax_lev3.tif"
    model_dir = root / arm
    if not gallery.is_file():
        raise SystemExit(f"no gallery tif for {arm!r}: {gallery}")
    if not (model_dir / "sfincs_map.nc").is_file():
        raise SystemExit(f"no sfincs_map.nc under {model_dir}")

    da = rioxarray.open_rasterio(gallery, masked=True).squeeze(drop=True).load()
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
    )

    out_tif.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_tif.with_name(f".{out_tif.name}.partial.tif")
    da.rio.to_raster(
        tmp,
        driver="GTiff",
        dtype="float32",
        compress="DEFLATE",
        predictor=3,  # float predictor — big win on smooth depth fields
        zlevel=6,
        tiled=True,
        blockxsize=512,
        blockysize=512,
        BIGTIFF="IF_SAFER",
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


README = """# Hurricane Sandy (2012) maximum flood depth — New Jersey coast, model v3

`{fname}`

Modelled maximum water depth during Hurricane Sandy (28–31 Oct 2012) over the whole
New Jersey ocean coast — Cape May to Raritan Bay and the Verrazzano Narrows, including
the back bays, the Delaware Bay shore near Cape May, and the Staten Island shore of
Lower Bay. SFINCS compound-flood hindcast: storm surge, wave setup, wind, rain and river
discharge together. **This is a working dataset from a model still under development,
not a validated hazard layer** — read the caveats before drawing any conclusion from it.

Model run: domain `{domain}`, experiment `{arm}`, exported {today}.

## Reading the file

| | |
|---|---|
| Format | GeoTIFF, single band, float32, DEFLATE-compressed, tiled, with overviews |
| **CRS** | **{crs} (EPSG:{epsg})** — UTM zone 18N, coordinates in **metres**, *not* degrees |
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
band into memory takes about 2.5 GB.

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

1. **Known low bias.** Against surveyed USGS high-water marks this run reads low on
   average (numbers above). Damages computed from it will be *under*-estimates, and
   non-linearly so, because damage curves are steep near the low end.
2. **Hindcast, not a design event.** This is one storm reconstructed after the fact.
   It is not a return-period product and must not be read as one.
3. **Model still in development.** A revised version of this run (a fix to how the
   model's northern edge on Staten Island drains) is finishing now and will raise
   depths around Raritan Bay and the Arthur Kill by roughly 0.1–0.3 m; the New Jersey
   ocean coast and back bays south of Sandy Hook are unaffected. Ask for the refreshed
   file if you are working north of Sandy Hook.
4. **New York land is out of scope.** The Staten Island and Brooklyn shorelines are
   in the grid only as the model's northern edge; do not read flooding there as a
   result. Jamaica Bay and Manhattan are not modelled at all.
5. **Depth only.** No velocity, no duration, no wave runup on the beach face, no
   debris — all of which matter for real damage estimation.
6. **Buildings are burned into the terrain** (footprints raised), so depths inside
   footprints are NaN or shallow by construction; read depth at the building's
   perimeter, not its centroid.

Questions to Ty.
"""


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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--arm", required=True, help="experiment name on the active domain")
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--stem", default=None, help="default sandy_hmax_<domain>_<arm>")
    a = ap.parse_args()

    dom = domain.active().name
    stem = a.stem or f"sandy_hmax_{dom}_{a.arm.replace('+', '_')}"
    out_tif = a.out_dir / f"{stem}_EPSG32618.tif"
    print(f"domain : {dom}\narm    : {a.arm}\ntarget : {out_tif}", flush=True)

    st = export(a.arm, out_tif)
    sc = score_row(a.arm)

    readme = a.out_dir / f"{stem}_README.md"
    readme.write_text(
        README.format(
            fname=out_tif.name,
            domain=dom,
            arm=a.arm,
            today=date.today().isoformat(),
            score_block=_score_block(sc),
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
