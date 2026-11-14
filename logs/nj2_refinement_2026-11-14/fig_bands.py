"""Eye-check figures of the new bands over the CURRENT (v4 / 1.1.0) mesh: fig/bands_north.png, fig/inlets.png."""

import sys
from pathlib import Path

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pyproj import Transformer

R = Path(__file__).resolve().parents[2]
L = Path(__file__).parent
(L / "fig").mkdir(exist_ok=True)
d = np.load(sys.argv[1])
x, y, lev, m, z = (d[k] for k in "x y level mask z".split())
g = gpd.read_file(R / "data/nj2_design/refinement_nj2_inlets12.geojson").dissolve(
    "name"
)
ring = pd.read_csv(R / "data/nj2_design/region_nj2_vertices.csv", comment="#")
T = Transformer.from_crs(4326, 32618, always_xy=True)
rx, ry = T.transform(ring.lon.values, ring.lat.values)


def draw(ax, names, cols):
    for n, c in zip(names, cols):
        geom = g.geometry[n]
        for p in getattr(geom, "geoms", [geom]):
            ax.plot(*p.exterior.xy, c, lw=1.2)
        ax.plot([], [], c, label=n)


# north
x0, y0 = T.transform(-74.36, 40.56)
x1, y1 = T.transform(-73.90, 40.99)
s = (x > x0) & (x < x1) & (y > y0) & (y < y1) & (m > 0)
fig, axs = plt.subplots(1, 2, figsize=(22, 14))
sc = axs[0].scatter(
    x[s], y[s], c=np.clip(z[s], -2, 8), s=0.2, cmap="terrain", vmin=-6, vmax=8
)
plt.colorbar(sc, ax=axs[0], shrink=0.6, label="face z (m NAVD88), v1.1.0 mesh")
sc = axs[1].scatter(
    x[s], y[s], c=200 / 2 ** (lev[s] - 1), s=0.2, cmap="viridis_r", vmin=25, vmax=200
)
plt.colorbar(sc, ax=axs[1], shrink=0.6, label="cell size today (m)")
for ax in axs:
    ax.plot(rx, ry, "k-", lw=0.8, label="provisional nj2 ring")
    draw(
        ax,
        ["hudson_waterfront", "newark_meadowlands", "narrows_cut", "bay_fringe"],
        ["r", "m", "c", "orange"],
    )
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    ax.legend(loc="lower right")
axs[0].set_title(
    "new north bands (25 m on ground -1..+5 m) — Hudson strip has no faces yet (outside v4)"
)
plt.tight_layout()
plt.savefig(L / "fig/bands_north.png", dpi=60)
plt.close()
# inlets
lines = pd.read_csv(R / "logs/capemay_tests_2026-11-09/out/inlet_lines.csv")
fig, axs = plt.subplots(2, 5, figsize=(30, 12))
for j, (_, r) in enumerate(lines.iterrows()):
    cx, cy = (r.xa + r.xb) / 2, (r.ya + r.yb) / 2
    W = 4000
    s = (abs(x - cx) < W) & (abs(y - cy) < W) & (m > 0)
    for i, (val, cm, lo, hi, lab) in enumerate(
        (
            (z, "terrain", -12, 6, "face z"),
            (200 / 2 ** (lev - 1), "viridis_r", 25, 100, "cell size today"),
        )
    ):
        ax = axs[i, j]
        sc = ax.scatter(x[s], y[s], c=val[s], s=1.2, cmap=cm, vmin=lo, vmax=hi)
        plt.colorbar(sc, ax=ax, shrink=0.7)
        ax.tricontour(
            x[s],
            y[s],
            z[s],
            levels=[-8, -6, -2],
            colors=["k", "b", "m"],
            linewidths=0.5,
        )
        ax.plot([r.xa, r.xb], [r.ya, r.yb], "r-", lw=2)
        draw(ax, ["capemay_inlets"], ["r--"])
        ax.set_title(f"{r.inlet}: {lab}  (contours -8 k, -6 b, -2 m)")
        ax.set_aspect("equal")
        ax.set_xlim(cx - W, cx + W)
        ax.set_ylim(cy - W, cy + W)
plt.tight_layout()
plt.savefig(L / "fig/inlets.png", dpi=55)
