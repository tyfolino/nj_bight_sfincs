#!/usr/bin/env python
"""The tidal Cohansey's bed at a STATED depth below MLLW → one overlay tier.

    python scripts/build_riverbed_cohansey_v4.py      # network: NHD + VDatum (cached)

WHY. CUDEM holds a flat ~0 m NAVD88 water surface as the Cohansey's bed from lat 39.36 to
Bridgeton (the 10-05 channel sweep, rank 6), and NO measured bed exists above the first
~0.5 km: NOS D00081 (1987) stops at 39.348, the ENC cells carry one sounding at the mouth
and a single 0–1.8 m depth band above it, there is no eHydro survey and the 1840s smooth
sheets are not digital (``logs/bedfix_2026-10-05/cohansey/README.md``). The river has
changed a lot since then anyway (dikes, tide gates).

DECISION (user, 2026-10-05): a fixed depth is acceptable. ``DEPTH_BELOW_MLLW_M`` = 1.2 m:
inside the chart's own 0–1.8 m depth band, and the depth the Passaic and Hackensack carry
above their last sounding (``build_riverbeds_v4.py`` ``tail_mllw_m``).

HOW. ``build_riverbeds_v4.py``'s machinery (NHD StreamRiver polygon the centreline runs
through, capped at 300 m from it; bed a function of distance along the centreline, flat
across), with bed = MLLW − 1.2 m. MLLW − NAVD88 = −0.94 m, constant: the VDatum API
returns error 412 all along this shore (as for the CENAP surveys south of Barnegat), and
the two CO-OPS stations publishing both datums bracket the river — 8536931 Fortescue
Creek −0.982 (20 km SE), 8551910 Reedy Point −0.905 (30 km NW); Ship John Shoal, nearer,
publishes no NAVD88. ±0.04 m is small beside the stated depth. The CENTRELINE is
traced through the NHD polygon itself (least-cost path from the mouth to Bridgeton on
1/(distance to bank + 1)², the channel sweep's method): the NHD flowline service timed out
on 10-05. Painted ONLY where
CUDEM is shallower than that bed, so the mouth's real scour hole keeps CUDEM.

🔴 A SEPARATE file. It is not one of ``build_riverbeds_v4.REACHES`` and never enters
``riverbeds_v4.vrt``, which is a tier of the frozen premier bed list. Output:
data/elevation_v4/riverbeds/riverbed_cohansey_v4.tif (+ ``_profile.csv``), painted by
``rebuild_subgrid.py --overlay riverbed_cohansey_v4``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_riverbeds_v4 as rb  # noqa: E402

DEPTH_BELOW_MLLW_M = 1.2
MLLW_NAVD88_M = -0.94  # mean of Fortescue Creek -0.982 and Reedy Point -0.905

MOUTH = (-75.372, 39.345)
TRACE_RES = 10.0

REACH = rb.Reach(
    "cohansey",
    (-75.385, 39.335, -75.205, 39.455),
    "Cohansey River",
    (-75.234, 39.432),  # Bridgeton, the upstream end
    "soundings",  # nominal: the profile is MLLW − DEPTH_BELOW_MLLW_M, built below
    tail_mllw_m=DEPTH_BELOW_MLLW_M,
    why=f"User 10-05: no measured bed above the mouth; {DEPTH_BELOW_MLLW_M} m below "
    "MLLW (CO-OPS, -0.94 m NAVD88), painted only where CUDEM is shallower.",
)


def trace_centreline(r):
    """Least-cost path mouth → head through the NHD StreamRiver polygons (UTM)."""
    import geopandas as gpd
    import shapely
    from rasterio import features
    from rasterio.transform import from_origin

    g = gpd.read_file(rb.RB / f"nhd_area_{r.name}.geojson").to_crs(rb.EPSG)
    poly = shapely.union_all(g.geometry.values)
    x0, y0, x1, y1 = poly.bounds
    nx, ny = int((x1 - x0) / TRACE_RES) + 1, int((y1 - y0) / TRACE_RES) + 1
    T = from_origin(x0, y1, TRACE_RES, TRACE_RES)
    inside = features.rasterize([(poly, 1)], out_shape=(ny, nx), transform=T) > 0
    dist = ndimage.distance_transform_edt(inside) * TRACE_RES
    cost = 1.0 / (dist + 1.0) ** 2
    ids = -np.ones(inside.shape, np.int64)
    iy, ix = np.nonzero(inside)
    ids[iy, ix] = np.arange(len(iy))
    rows, cols, w = [], [], []
    for dy, dx in ((0, 1), (1, 0), (1, 1), (1, -1)):
        a = ids[0 : ny - dy, max(0, -dx) : nx - max(0, dx)]
        b = ids[dy:ny, max(0, dx) : nx - max(0, -dx)]
        ok = (a >= 0) & (b >= 0)
        ca, cb = a[ok], b[ok]
        ww = np.hypot(dy, dx) * 0.5 * (cost[iy[ca], ix[ca]] + cost[iy[cb], ix[cb]])
        rows += [ca, cb]
        cols += [cb, ca]
        w += [ww, ww]
    n = len(iy)
    G = coo_matrix(
        (np.concatenate(w), (np.concatenate(rows), np.concatenate(cols))), (n, n)
    ).tocsr()
    px = x0 + (ix + 0.5) * TRACE_RES
    py = y1 - (iy + 0.5) * TRACE_RES
    ends = gpd.GeoSeries(
        [shapely.Point(MOUTH), shapely.Point(r.head)], crs=4326
    ).to_crs(rb.EPSG)
    a, b = (int(np.argmin(np.hypot(px - p.x, py - p.y))) for p in ends)
    d, pred = dijkstra(G, indices=a, return_predecessors=True)
    if not np.isfinite(d[b]):
        raise SystemExit("mouth and head are not connected through the NHD polygon")
    path = [b]
    while path[-1] != a:
        path.append(pred[path[-1]])
    path = path[::-1]  # station 0 = the mouth (downstream), as rb._centreline
    line = shapely.LineString(np.column_stack([px[path], py[path]])).simplify(10.0)
    return line


def main() -> int:
    import rasterio

    r = REACH
    a = rb.RB / f"nhd_area_{r.name}.geojson"
    if not a.exists():
        rb._atomic_bytes(a, rb._nhd(9, "ftype=460", r.box))
    line = trace_centreline(r)
    chan = rb._channel(r, line)
    grid = np.arange(0.0, line.length + 25.0, 25.0)
    prof = np.full(grid.shape, MLLW_NAVD88_M - DEPTH_BELOW_MLLW_M)
    print(
        f"{r.name}: centreline {line.length / 1000:.1f} km, channel "
        f"{chan.area / 1e6:.2f} km²; MLLW−NAVD88 {MLLW_NAVD88_M:+.3f} m; "
        f"bed {np.nanmin(prof):+.2f}..{np.nanmax(prof):+.2f} m"
    )
    out = rb.paint(r, line, chan, grid, prof)

    # deepen only: drop every painted pixel where CUDEM is already at or below it
    with rasterio.open(out) as s:
        z = s.read(1).astype("float64")
        T, prof_ = s.transform, s.profile
    rr, cc = np.nonzero(z != rb.NODATA)
    px = T.c + (cc + 0.5) * T.a
    py = T.f + (rr + 0.5) * T.e
    cz = rb._sample(rb.CUDEM, px, py)
    keep = ~(np.isfinite(cz) & (cz <= z[rr, cc]))
    z[rr[~keep], cc[~keep]] = rb.NODATA
    tmp = out.with_name(f".{out.name}.deepen.tif")
    with rasterio.open(tmp, "w", **prof_) as d:
        d.write(z.astype("float32"), 1)
        d.update_tags(reach=r.name, why=r.why)
    os.replace(tmp, out)
    lift = z[rr[keep], cc[keep]] - cz[keep]
    print(
        f"  deepen-only: kept {keep.sum()} of {keep.size} px "
        f"({keep.sum() * rb.RES**2 / 1e6:.2f} km²), CUDEM there p50 "
        f"{np.nanmedian(cz[keep]):+.2f} m, change p50 {np.nanmedian(lift):+.2f} m"
    )
    rows = ["station_m,bed_navd88_m"] + [f"{s:.0f},{v:.3f}" for s, v in zip(grid, prof)]
    rb._atomic_bytes(
        rb.RB / f"riverbed_{r.name}_v4_profile.csv", ("\n".join(rows) + "\n").encode()
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
