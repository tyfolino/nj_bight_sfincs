#!/usr/bin/env python
"""Bridge-as-dam sweep on the merged bed, BEFORE the freeze.

Lidar puts a bridge deck on the bed and the solver reads a causeway as an earthen dam
(the Shrewsbury lesson). This finds every wet body that the bed disconnects from the
ocean and how thin the wall between them is: on a raster of the coarse bed, cells below
`--wet-z` are "wet", 4-connected components are labelled, the ocean component is the
largest, and every other component is reported with its area, the metres of not-wet
ground between it and the ocean component, and the lowest bed in that gap (the crest
the water would have to overtop). A back-bay behind a 25–75 m wall whose crest is above
the wet threshold is the signature of a bridge deck; a lake 2 km inland is a lake.

Reads, never writes anything but the CSV + figure. The user judges each row.

Usage:
    NJ_DOMAIN=v3 PYTHONPATH=$PWD python scripts/sweep_bed_dams.py \\
        [--wet-z -1.0] [--min-area-km2 0.02] [--max-gap-m 300]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

import nj_sfincs  # noqa: F401  (pyproj before hydromt_sfincs)
import geopandas as gpd  # noqa: E402
import pandas as pd  # noqa: E402
import pyproj  # noqa: E402
import rasterio  # noqa: E402
from rasterio.features import rasterize  # noqa: E402
from scipy import ndimage  # noqa: E402

from nj_sfincs import domain as _domain  # noqa: E402
from nj_sfincs.config import ROOT  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bed", default="data/elevation_v3/bed_v3_coarse_25m.tif")
    ap.add_argument("--wet-z", type=float, default=-1.0,
                    help="bed below this is wet (default -1 m, the STATUS rule)")
    ap.add_argument("--min-area-km2", type=float, default=0.02)
    ap.add_argument("--max-gap-m", type=float, default=300.0,
                    help="only report bodies whose wall to the ocean is thinner than this")
    ap.add_argument("--out", default="reports/bed_dams_v3.csv")
    args = ap.parse_args()

    dom = _domain.active()
    bed = Path(args.bed)
    if not bed.is_absolute():
        bed = ROOT / bed
    with rasterio.open(bed) as src:
        z = src.read(1).astype("float32")
        z[z == src.nodata] = np.nan
        tr, crs, res = src.transform, src.crs, src.res[0]
    ring = gpd.read_file(dom.region).to_crs(crs)
    inside = rasterize(((g, 1) for g in ring.geometry), out_shape=z.shape,
                       transform=tr, fill=0, dtype="uint8").astype(bool)
    wet = inside & (z < args.wet_z)
    lab, n = ndimage.label(wet, structure=[[0, 1, 0], [1, 1, 1], [0, 1, 0]])
    sizes = ndimage.sum(wet, lab, index=np.arange(1, n + 1))
    ocean = int(np.argmax(sizes)) + 1
    print(f"bed {bed.name}  {z.shape[1]}x{z.shape[0]} @ {res:.0f} m · wet (z < {args.wet_z}) "
          f"cells in ring {int(wet.sum()):,} in {n:,} bodies · ocean body "
          f"{sizes[ocean - 1] * res * res / 1e6:,.0f} km2")

    # metres from every cell to the ocean body, and the nearest ocean cell's index
    dist, (iy, ix) = ndimage.distance_transform_edt(lab != ocean, return_indices=True)
    dist *= res
    min_cells = int(args.min_area_km2 * 1e6 / (res * res))
    to_ll = pyproj.Transformer.from_crs(crs, "EPSG:4326", always_xy=True)

    rows = []
    for b in np.flatnonzero(sizes >= min_cells) + 1:
        if b == ocean:
            continue
        cells = lab == b
        gap = dist[cells]
        k = int(np.argmin(gap))
        if gap[k] > args.max_gap_m:
            continue
        cy, cx = np.flatnonzero(cells)[k] // z.shape[1], np.flatnonzero(cells)[k] % z.shape[1]
        oy, ox = iy[cy, cx], ix[cy, cx]
        # the wall: every not-wet cell touched by the straight line between the two
        # nearest wet cells (sampled at quarter-cell steps so a diagonal gap is seen)
        m = 4 * max(abs(oy - cy), abs(ox - cx), 1)
        ly = np.round(np.linspace(cy, oy, m + 1)).astype(int)
        lx = np.round(np.linspace(cx, ox, m + 1)).astype(int)
        wall = z[ly, lx]
        wall = wall[np.isfinite(wall) & (wall >= args.wet_z)]
        if not len(wall):  # diagonal one-cell gap: the two 4-neighbours are the wall
            wall = z[[cy, oy], [ox, cx]]
            wall = wall[np.isfinite(wall)]
        x, y = tr * (cx + 0.5, cy + 0.5)
        lon, lat = to_ll.transform(x, y)
        rows.append(dict(
            body=int(b), area_km2=round(sizes[b - 1] * res * res / 1e6, 3),
            gap_m=round(float(gap[k])), crest_m=round(float(wall.min()), 2) if len(wall) else np.nan,
            crest_max_m=round(float(wall.max()), 2) if len(wall) else np.nan,
            body_min_z=round(float(np.nanmin(z[cells])), 2),
            lon=round(lon, 5), lat=round(lat, 5), x=round(x), y=round(y),
        ))
    df = pd.DataFrame(rows).sort_values(["crest_m", "area_km2"], ascending=[False, False])
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 12), constrained_layout=True)
    ext = (tr.c, tr.c + z.shape[1] * res, tr.f + z.shape[0] * tr.e, tr.f)
    ax.imshow(np.where(lab == ocean, 1.0, np.nan), extent=ext, cmap="Blues", vmin=0,
              vmax=1.6, interpolation="nearest")
    ax.imshow(np.where(wet & (lab != ocean), 1.0, np.nan), extent=ext, cmap="Greys",
              vmin=0, vmax=1.4, interpolation="nearest")
    ring.boundary.plot(ax=ax, color="#52514e", lw=0.8)
    sc = ax.scatter(df.x, df.y, c=df.crest_m, s=18 + 40 * np.log10(df.area_km2 / args.min_area_km2),
                    cmap="YlOrRd", vmin=args.wet_z, vmax=2, edgecolor="k", lw=0.5, zorder=5)
    for _, r in df[df.crest_m > 0].iterrows():
        ax.annotate(f"{r.body}", (r.x, r.y), fontsize=7, xytext=(4, 3), textcoords="offset points")
    fig.colorbar(sc, ax=ax, shrink=0.5, label="lowest bed in the wall [m NAVD88]")
    ax.set_aspect("equal")
    ax.set_title(f"Wet bodies (z < {args.wet_z} m) cut off from the ocean by a wall under "
                 f"{args.max_gap_m:.0f} m — {len(df)} bodies; labelled = crest above 0 m",
                 fontsize=9.5, loc="left", wrap=True)
    png = out.parent / "figures" / out.with_suffix(".png").name
    png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png, dpi=130)
    pd.set_option("display.width", 200)
    print(f"\n{len(df)} disconnected wet bodies >= {args.min_area_km2} km2 within "
          f"{args.max_gap_m:.0f} m of the ocean body -> {out.relative_to(ROOT)}")
    print(df.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
