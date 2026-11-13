"""Poster v4 Figure 3: power plants and substations that Sandy floods, today's ground vs 2012 (compact).

    python reports/poster_2026-11-13/fig3_power_compact.py

The 2026-ground panel of fig4_power.py ("2026" mode: same asset inputs and helpers, rings = sites whose
state differs from Model 1.1.0 on 2012 ground; v9: rings and 2012 counts removed), with a Newark Bay inset (B) and the counts beside the map.
Drawn at print size (about 16.3 x 7.2 in), so font sizes are printed sizes.

v8 (user 11-13, "do whatever we did for Fig 1b"): the blue water layer is no longer fig4_power.shade()
(faces judged on their MEAN ground, normally-dry land only, 300 m bins, 30 % cutoff), which looked far
sparser than Fig 1b. It is now Fig 1b's definition: peak depth >= 0.15 m on the native 3.125 m floodmap,
all land inside the model, open water = bed <= 0 m, from fig3_wet_layer.py's 15 m class raster (WET15).
Asset dots and counts are unchanged (exposure CSVs).
"""

import sys
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

HERE = Path(__file__).resolve().parent
WET15 = Path("/scratch/tpj8/poster_2026-11-13/fig3/v4_refreeze_swz_v11__bed-modernb+p4-premier+"
             "struct-pews-checkvalve+weir-elizabeth-rahway+weir-portmonmouth__wet15.tif")
sys.path.insert(0, str(HERE))
from fig4_power import (  # noqa: E402
    CENSUS,
    FLOOD,
    TAGS,
    ZOOM,
    assets,
    basemap,
    load,
    scalebar,
)
from matplotlib.patches import Rectangle  # noqa: E402
from poster_style import C, apply, save  # noqa: E402

FS = 16
G_MAIN, G_ZOOM = 8, 2  # display aggregation of the 15 m cells: 120 m (state map, as Fig 1b), 30 m (inset)


def load_wet():
    """The 2026-ground run's wet / dry / water classes on the MOTF 15 m grid (fig3_wet_layer.py)."""
    import rasterio

    with rasterio.open(WET15) as r:
        return r.read(1), r.transform


def shade15(ax, f, cls, tr, ext, k):
    """Sandy's flood extent on Fig 1b's definition (peak depth >= 0.15 m on the native 3.125 m floodmap,
    land inside the model), shown at k x 15 m: a block is blue when wet cells cover >= 25 % of it (the
    share Fig 1b's overview uses). Plus the edge of the model (the old shade()'s dashed contour)."""
    from matplotlib.colors import ListedColormap

    c0 = max(int((ext[0] - tr.c) / tr.a), 0)
    c1 = min(int(np.ceil((ext[1] - tr.c) / tr.a)), cls.shape[1])
    r0 = max(int((ext[3] - tr.f) / tr.e), 0)
    r1 = min(int(np.ceil((ext[2] - tr.f) / tr.e)), cls.shape[0])
    sub = cls[r0:r1, c0:c1] == 4
    Hh, Ww = (sub.shape[0] // k) * k, (sub.shape[1] // k) * k
    frac = sub[:Hh, :Ww].reshape(Hh // k, k, Ww // k, k).mean(axis=(1, 3))
    img = np.where(frac >= 0.25, 1.0, np.nan)
    x0, y0 = tr.c + c0 * tr.a, tr.f + r0 * tr.e
    ax.imshow(img, extent=(x0, x0 + Ww * tr.a, y0 + Hh * tr.e, y0), cmap=ListedColormap([FLOOD]),
              vmin=0, vmax=1, interpolation="nearest", zorder=1)
    BINc = 300.0
    xe = np.arange(ext[0], ext[1] + BINc, BINc)
    ye = np.arange(ext[2], ext[3] + BINc, BINc)
    area = lambda lev: (200.0 / 2.0 ** (lev.astype("f8") - 1)) ** 2  # noqa: E731
    act, _, _ = np.histogram2d(f["act_y"], f["act_x"], [ye, xe], weights=area(f["act_lev"]))
    xc, yc = 0.5 * (xe[1:] + xe[:-1]), 0.5 * (ye[1:] + ye[:-1])
    ax.contour(xc, yc, (act > 0.3 * BINc * BINc).astype(float), levels=[0.5], colors="#555555",
               linewidths=1.0, linestyles="--", zorder=2)


def main():
    apply()
    a, f = load(TAGS["2026"])
    # v9 (user 11-13): today's ground only. The asset list is TODAY's (substations have moved since 2012), so
    # no 2012-ground counts or "changes vs 2012" rings are shown.
    s26 = a.state.replace({"on_water": "dry"})
    c26 = s26.value_counts()
    print("2026:", dict(c26), "total", len(a))
    states = gpd.read_file(f"zip://{CENSUS / 'cb_2023_us_state_500k.zip'}").to_crs(32618)
    states = states[states.STUSPS.isin(["NJ", "NY", "PA", "DE", "MD", "CT"])]
    ext = (float(f["act_x"].min()) - 4e3, float(f["act_x"].max()) + 4e3,
           float(f["act_y"].min()) - 4e3, float(f["act_y"].max()) + 4e3)
    H = 7.2  # v6 poster: Newark Bay inset restored (panel B)
    mw = H * (ext[1] - ext[0]) / (ext[3] - ext[2])
    zw = H * (ZOOM[1] - ZOOM[0]) / (ZOOM[3] - ZOOM[2])
    gap = 0.25
    W = mw + gap + zw + 4.7
    fig = plt.figure(figsize=(W, H))
    ax = fig.add_axes([0, 0, mw / W, 1])
    basemap(ax, ext, states)
    cls, tr = load_wet()
    shade15(ax, f, cls, tr, ext, G_MAIN)
    assets(ax, a, 22)
    scalebar(ax, ext[0] + 8e3, ext[2] + 8e3, 25)
    ax.texts[-1].set_fontsize(FS - 2)
    ax.add_patch(Rectangle((ZOOM[0], ZOOM[2]), ZOOM[1] - ZOOM[0], ZOOM[3] - ZOOM[2], fill=False,
                           edgecolor="black", linewidth=1.5, zorder=8))
    ax.text(ZOOM[0] - 1500, ZOOM[3], "B", ha="right", va="top", fontsize=FS + 2, weight="bold", zorder=8)
    ax.text(0.03, 0.985, "A", transform=ax.transAxes, ha="left", va="top", fontsize=FS + 2, weight="bold",
            zorder=9)
    az = fig.add_axes([(mw + gap) / W, 0, zw / W, 1])
    basemap(az, ZOOM, states)
    shade15(az, f, cls, tr, ZOOM, G_ZOOM)
    assets(az, a, 60)
    scalebar(az, ZOOM[1] - 14e3, ZOOM[2] + 3e3, 10)
    az.texts[-1].set_fontsize(FS - 2)
    az.text(0.03, 0.985, "B  Newark Bay", transform=az.transAxes, ha="left", va="top", fontsize=FS + 2,
            weight="bold", zorder=9, bbox=dict(boxstyle="square,pad=0.2", fc="white", ec="none", alpha=0.85))

    x_at = mw + gap + zw + 0.3
    at = fig.add_axes([x_at / W, 0, (W - x_at) / W, 1])
    at.axis("off")
    rows = [("wet", "flood"), ("dry", "stay dry"), ("not_computed", "not computed")]
    at.text(0.0, 0.995, "Today's ground", fontsize=FS, va="top", transform=at.transAxes,
            color="#333333")
    for i, (k, lab) in enumerate(rows):
        yy = 0.86 - i * 0.135
        at.text(0.0, yy, f"{int(c26.get(k, 0))}", fontsize=34, weight="bold", va="center",
                transform=at.transAxes)
        at.text(0.30, yy, lab, fontsize=FS + 2, va="center",
                transform=at.transAxes)
    at.text(0.0, 0.47, f"of {len(a)} NJ power plants and\nsubstations in the region",
            fontsize=FS, va="center", transform=at.transAxes)
    handles = [
        Line2D([], [], marker="o", ls="", color=C["wet"], markeredgecolor="black", markersize=12,
               label="Floods (≥ 0.15 m)"),
        Line2D([], [], marker="o", ls="", color=C["dry"], markeredgecolor="white", markersize=12,
               label="Stays dry"),
        Line2D([], [], marker="x", ls="", color="#444444", markersize=10, markeredgewidth=1.5,
               label="Not computed (edge)"),
        Patch(facecolor=FLOOD, label="Sandy's flood extent (≥ 0.15 m)"),
        Line2D([], [], color="#555555", ls="--", lw=1.2, label="Edge of the model"),
    ]
    at.legend(handles=handles, loc="lower left", fontsize=FS, frameon=False, borderaxespad=0.0,
              labelspacing=0.35, handlelength=1.4, bbox_to_anchor=(0.0, 0.0))
    save(fig, "fig3_power_compact")


if __name__ == "__main__":
    main()
