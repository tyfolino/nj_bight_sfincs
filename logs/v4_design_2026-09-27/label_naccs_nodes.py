#!/usr/bin/env python
"""Labelled NACCS node maps for choosing the forced line's "jumps" by eye (user, 09-27).

    python logs/v4_design_2026-09-27/label_naccs_nodes.py
      -> reports/figures/v4_naccs_nodes_{delaware_mouth,lower_bay}.png

Every save point wet through the padded Sandy window, labelled "<sp> / <depth> m": filled
if ADCIRC depth ≥ 8 m, HOLLOW if shallower (FINDINGS §22–23 — a shallow node carries surf
setup that SnapWave would add again). The current line (orange), the ring (ink), and the
−10 m isobath (grey) for reference.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import rasterio  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from rasterio.warp import Resampling, reproject  # noqa: E402
from rasterio.transform import from_bounds  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIG = ROOT / "reports" / "figures"
ORANGE, INK, GREY = "#eb6834", "#0b0b0b", "#52514e"
BLUES = LinearSegmentedColormap.from_list(
    "depth", ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
)
BOXES = {  # lon0, lat0, lon1, lat1
    "delaware_mouth": (-75.16, 38.70, -74.80, 38.97),
    "lower_bay": (-74.02, 40.41, -73.88, 40.60),
}


def main() -> None:
    c = np.load(ROOT / "data" / "NACCS" / "_sandy_parsed.npz", allow_pickle=True)
    t = np.array([dt.datetime.strptime(str(s), "%Y%m%d%H%M") for s in c["times"]])
    win = (t >= dt.datetime(2012, 10, 24)) & (t <= dt.datetime(2012, 11, 1))
    wet = (c["wl"][:, win] > -9000).all(axis=1)
    line = pd.read_csv(ROOT / "data" / "v4_design" / "waterlevel_line_v4.csv", comment="#")
    ring = pd.read_csv(ROOT / "data" / "v4_design" / "region_v4_vertices.csv", comment="#")
    rx, ry = np.r_[ring.lon, ring.lon[:1]], np.r_[ring.lat, ring.lat[:1]]

    for name, (x0, y0, x1, y1) in BOXES.items():
        w, h = 900, int(900 * (y1 - y0) / ((x1 - x0) * np.cos(np.radians((y0 + y1) / 2))))
        tr = from_bounds(x0, y0, x1, y1, w, h)
        z = np.full((h, w), np.nan, "float32")
        with rasterio.open(ROOT / "data" / "elevation_v4" / "bed_v4_coarse_25m.tif") as b:
            reproject(rasterio.band(b, 1), z, dst_transform=tr, dst_crs="EPSG:4326",
                      resampling=Resampling.average, dst_nodata=np.nan)
        fig, ax = plt.subplots(figsize=(11, 11 * h / w), facecolor="#fcfcfb")
        ext = (x0, x1, y0, y1)
        ax.imshow(np.where(z >= 0, 1.0, np.nan), extent=ext, cmap="Greys", vmin=0, vmax=6)
        im = ax.imshow(np.where(z < 0, -z, np.nan), extent=ext, cmap=BLUES, vmin=0, vmax=30)
        ax.contour(np.linspace(x0, x1, w), np.linspace(y1, y0, h), z, levels=[-10],
                   colors=GREY, linewidths=0.7)
        ax.plot(rx, ry, color=INK, lw=1.2, ls="--", label="ring (model region)")
        ax.plot(line.lon, line.lat, color=ORANGE, lw=2, label="current forced line")
        m = wet & (c["lon"] > x0) & (c["lon"] < x1) & (c["lat"] > y0) & (c["lat"] < y1)
        seen = {}
        for i in np.flatnonzero(m):
            deep = c["depth"][i] >= 8.0
            ax.scatter(c["lon"][i], c["lat"][i], s=36, zorder=5,
                       c=INK if deep else "#fcfcfb", edgecolors=INK, linewidths=1.2)
            key = (round(c["lon"][i], 4), round(c["lat"][i], 4))
            k = seen.get(key, 0)
            seen[key] = k + 1
            ax.annotate(f"{int(c['sp'][i])} / {c['depth'][i]:.0f} m", (c["lon"][i], c["lat"][i]),
                        xytext=(5, 3 - 9 * k), textcoords="offset points", fontsize=7.5, color=INK,
                        zorder=6, bbox=dict(boxstyle="round,pad=0.1", fc="#fcfcfb", ec="none", alpha=0.7))
        ax.scatter([], [], s=36, c=INK, label="NACCS node ≥ 8 m deep")
        ax.scatter([], [], s=36, c="#fcfcfb", edgecolors=INK, label="NACCS node < 8 m (surf setup)")
        ax.plot([], [], color=GREY, lw=0.7, label="−10 m isobath")
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)
        ax.set_aspect(1 / np.cos(np.radians((y0 + y1) / 2)))
        ax.tick_params(labelsize=8, colors=GREY)
        ax.legend(loc="lower right", fontsize=8, facecolor="#fcfcfb")
        fig.colorbar(im, ax=ax, shrink=0.5, label="water depth (m)")
        ax.set_title(f"NACCS save points, {name.replace('_', ' ')} — label = node / ADCIRC depth",
                     fontsize=11, color=INK, loc="left")
        out = FIG / f"v4_naccs_nodes_{name}.png"
        fig.savefig(out, dpi=160, bbox_inches="tight")
        plt.close(fig)
        print(f"{out}: {m.sum()} wet nodes")


if __name__ == "__main__":
    main()
