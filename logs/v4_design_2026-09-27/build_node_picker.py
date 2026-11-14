#!/usr/bin/env python
"""Build the interactive NACCS node picker (an HTML artifact) for choosing the forced line's
jumps across the Delaware mouth and the Lower Bay entrance (user, 2026-09-27).

    python logs/v4_design_2026-09-27/build_node_picker.py <out.html>

Every NACCS save point in each window (wet or not), the ring, the current forced line and
its anchor vertices, over the v4 coarse bed. Node → lon/lat/depth/Sandy peak from
data/NACCS/_sandy_parsed.npz. The page is self-contained (bathymetry as PNG data URIs).
"""

from __future__ import annotations

import base64
import datetime as dt
import io
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from PIL import Image
from rasterio.transform import from_bounds
from rasterio.warp import Resampling, reproject

ROOT = Path(__file__).resolve().parents[2]
REGIONS = {
    "delaware": ("Delaware mouth", (-75.17, 38.70, -74.78, 39.00)),
    "lowerbay": ("Lower Bay entrance", (-74.035, 40.40, -73.87, 40.61)),
}
WIDTH = 1600
#: Anchors that are not (yet) line vertices: where a path could run aground.
EXTRA_ANCHORS = {
    "delaware": [
        # the ring's south edge (ocean_sw → de_south_01, lat 38.725–38.7256) meets the
        # Rehoboth shoreline (first bed > 0 going west along 38.725, bed_v4_coarse_25m)
        dict(id="rehoboth_ring_edge", lon=-75.0770, lat=38.7254),
    ],
    "lowerbay": [],
}


def ramp(z: np.ndarray) -> np.ndarray:
    """RGB: land warm light grey; water a slate ramp by depth; the -10 m edge darkened."""
    h, w = z.shape
    rgb = np.zeros((h, w, 3), np.float32)
    land = ~(z < 0)
    d = np.clip(-z, 0, 30) / 30.0
    shallow, deep = np.array([222, 231, 236]), np.array([52, 76, 92])
    water = shallow[None, None] * (1 - d[..., None]) + deep[None, None] * d[..., None]
    rgb[:] = water
    rgb[land] = (238, 236, 230)
    rgb[np.isnan(z)] = (238, 236, 230)
    m = z < -10
    edge = np.zeros_like(m)
    edge[1:, :] |= m[1:, :] != m[:-1, :]
    edge[:, 1:] |= m[:, 1:] != m[:, :-1]
    rgb[edge] = rgb[edge] * 0.35 + np.array([20, 28, 34]) * 0.65
    return rgb.astype(np.uint8)


def region_image(box) -> tuple[str, int, int]:
    lon0, lat0, lon1, lat1 = box
    k = np.cos(np.radians((lat0 + lat1) / 2))
    w = WIDTH
    h = int(round(WIDTH * (lat1 - lat0) / ((lon1 - lon0) * k)))
    z = np.full((h, w), np.nan, np.float32)
    with rasterio.open(ROOT / "data" / "elevation_v4" / "bed_v4_coarse_25m.tif") as b:
        reproject(
            rasterio.band(b, 1), z, dst_transform=from_bounds(lon0, lat0, lon1, lat1, w, h),
            dst_crs="EPSG:4326", resampling=Resampling.bilinear, dst_nodata=np.nan,
        )
    buf = io.BytesIO()
    Image.fromarray(ramp(z)).save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode(), w, h


def main() -> None:
    out = Path(sys.argv[1])
    c = np.load(ROOT / "data" / "NACCS" / "_sandy_parsed.npz", allow_pickle=True)
    t = np.array([dt.datetime.strptime(str(s), "%Y%m%d%H%M") for s in c["times"]])
    win = (t >= dt.datetime(2012, 10, 24)) & (t <= dt.datetime(2012, 11, 1))
    wl = c["wl"][:, win]
    wet = (wl > -9000).all(axis=1)
    peak = np.where(wl > -9000, wl, np.nan).max(axis=1)
    ring = pd.read_csv(ROOT / "data" / "v4_design" / "region_v4_vertices.csv", comment="#")
    line = pd.read_csv(ROOT / "data" / "v4_design" / "waterlevel_line_v4.csv", comment="#")

    data = {}
    for key, (label, box) in REGIONS.items():
        lon0, lat0, lon1, lat1 = box
        img, w, h = region_image(box)
        pad = 0.02
        m = (c["lon"] > lon0 - pad) & (c["lon"] < lon1 + pad) & (c["lat"] > lat0 - pad) & (c["lat"] < lat1 + pad)
        nodes = [
            dict(
                id=int(c["sp"][i]), lon=round(float(c["lon"][i]), 5), lat=round(float(c["lat"][i]), 5),
                depth=round(float(c["depth"][i]), 1),
                peak=None if not np.isfinite(peak[i]) else round(float(peak[i]), 2),
                wet=bool(wet[i]),
            )
            for i in np.flatnonzero(m)
        ]
        anchors = [
            dict(id=r["name"], lon=float(r.lon), lat=float(r.lat))
            for _, r in line[line.sp.isna()].iterrows()
            if lon0 - pad < r.lon < lon1 + pad and lat0 - pad < r.lat < lat1 + pad
        ] + EXTRA_ANCHORS[key]
        data[key] = dict(
            label=label, box=box, img=img, w=w, h=h, nodes=nodes, anchors=anchors,
            ring=[[float(a), float(b)] for a, b in zip(ring.lon, ring.lat)] + [[float(ring.lon[0]), float(ring.lat[0])]],
            line=[[float(a), float(b)] for a, b in zip(line.lon, line.lat)],
            line_nodes=[int(s) for s in line.sp.dropna()],
        )
        print(f"{key}: {len(nodes)} nodes ({sum(n['wet'] for n in nodes)} wet), {len(anchors)} anchors, image {w}x{h}")

    html = (Path(__file__).with_name("node_picker_template.html").read_text()
            .replace("/*__DATA__*/null", json.dumps(data, separators=(",", ":"))))
    out.write_text(html)
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
