"""Poster Figure 1: what the model is (Model 1.1.0 domain, drivers, validation data).

    python reports/poster_2026-11-13/fig1_model.py     (after fig1_prep.py; plotting only)

Inputs (all beside this script): ``fig1_data.npz`` / ``fig1_inflows.csv`` /
``fig1_gauges.csv`` / ``fig1_weirs.csv`` (``fig1_prep.py``, from the 1.1.0 run dir),
``hwm_per_mark_v110_native.csv`` (the 119 scored marks), and the drawn sea boundary
``data/v4_design/waterlevel_line_v4.csv``. Numbers in the side panel: docs/MODEL.md +
``fig1_prep.py``'s printout (README_fig1_fig2.md).
"""

import sys
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import patheffects as pe
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from shapely.geometry import box

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
from poster_style import C, apply, save  # noqa: E402

NE = Path.home() / ".local/share/cartopy/shapefiles/natural_earth"
EXTENT = (-75.76, -73.72, 38.70, 40.97)
#: mesh resolution, finest darkest (one hue, light -> dark)
RES = [200, 100, 50, 25]
RES_COL = ["#C6DBEF", "#6BAED6", "#2171B5", "#08306B"]

PLACES = [  # (label, lon, lat, ha, va)
    ("Cape May", -74.95, 38.99, "right", "center"),
    ("Atlantic City", -74.33, 39.33, "left", "center"),
    ("Philadelphia", -75.20, 40.00, "right", "bottom"),
    ("Long Beach\nIsland", -74.06, 39.62, "left", "center"),
    ("Sandy Hook", -73.95, 40.37, "left", "center"),
    ("Newark", -74.20, 40.75, "right", "center"),
    ("Delaware\nBay", -75.17, 39.15, "center", "center"),
]


def main():
    apply()
    z = np.load(HERE / "fig1_data.npz")
    grid = z["grid"]
    lon0, lat0, dlon, dlat = (float(z[k]) for k in ("lon0", "lat0", "dlon", "dlat"))
    ny, nx = grid.shape
    ext = (lon0, lon0 + nx * dlon, lat0, lat0 + ny * dlat)
    inflow = pd.read_csv(HERE / "fig1_inflows.csv")
    gauges = pd.read_csv(HERE / "fig1_gauges.csv")
    # The Narrows pair sits on the forced boundary: a forcing input, not a check (CLAUDE.md §6).
    n_check = int((~gauges.name.isin(["sss_narrows_si", "sss_narrows_bkln"])).sum())
    weirs = pd.read_csv(HERE / "fig1_weirs.csv")
    hwm = pd.read_csv(HERE / "hwm_per_mark_v110_native.csv")
    hwm = hwm[hwm.scored]
    line = pd.read_csv(REPO / "data/v4_design/waterlevel_line_v4.csv", comment="#")

    # Map only (user 11-12: the poster text describes the model). SIDE=True restores the panel.
    SIDE = False
    fig = plt.figure(figsize=(12.5, 9.6) if SIDE else (7.0, 9.6))
    ax = fig.add_axes([0.0, 0.0, 0.56, 1.0] if SIDE else [0.0, 0.0, 1.0, 1.0])
    if SIDE:
        side = fig.add_axes([0.575, 0.0, 0.425, 1.0])
        side.axis("off")

    bb = box(EXTENT[0], EXTENT[2], EXTENT[1], EXTENT[3])
    land = gpd.read_file(NE / "physical/ne_10m_land.shp", bbox=bb).clip(bb)
    states = gpd.read_file(
        NE / "cultural/ne_10m_admin_1_states_provinces_lakes.shp", bbox=bb
    )
    ax.set_facecolor("#EEF1F4")
    land.plot(ax=ax, color=C["land"], edgecolor="0.6", lw=0.4, zorder=1)
    states.boundary.clip(bb).plot(ax=ax, color="0.65", lw=0.6, zorder=1.5)

    cmap = ListedColormap(RES_COL[::-1])  # index 0 = 25 m
    norm = BoundaryNorm([0, 37.5, 75, 150, 300], cmap.N)
    ax.imshow(
        np.ma.masked_invalid(grid), origin="lower", extent=ext, cmap=cmap, norm=norm,
        interpolation="nearest", zorder=2, alpha=0.95,
    )
    ax.plot(line.lon, line.lat, color=C["boundary"], lw=3.2, zorder=5,
            solid_capstyle="round")
    ax.scatter(z["forced_lon"], z["forced_lat"], s=2, color=C["boundary"], lw=0,
               zorder=5)
    for _, w in weirs.groupby("line"):
        ax.plot(w.lon, w.lat, color="black", lw=2.0, zorder=6)
    ax.scatter(hwm.lon, hwm.lat, s=16, marker="o", facecolor="#CC79A7",
               edgecolor="white", lw=0.4, zorder=7)
    ax.scatter(gauges.lon, gauges.lat, s=46, marker="s", facecolor="white",
               edgecolor="black", lw=1.2, zorder=8)
    ax.scatter(inflow.lon, inflow.lat, s=60, marker="v", facecolor=C["accent"],
               edgecolor="black", lw=0.6, zorder=9)
    for lab, x, y, ha, va in PLACES:
        ax.text(x, y, lab, fontsize=13, ha=ha, va=va, color="0.1", zorder=10,
                style="italic",
                path_effects=[pe.withStroke(linewidth=3.5, foreground="white")])
    ax.text(-73.87, 39.85, "Atlantic\nOcean", fontsize=15, ha="center", color="0.45",
            style="italic", zorder=3)
    for name, x, y in [("NJ", -74.55, 40.25), ("PA", -75.6, 40.3), ("DE", -75.62, 39.05),
                       ("NY", -73.85, 40.88)]:
        ax.text(x, y, name, fontsize=14, color="0.5", ha="center", style="italic",
                zorder=3)
    ax.set_xlim(EXTENT[0], EXTENT[1])
    ax.set_ylim(EXTENT[2], EXTENT[3])
    ax.set_aspect(1 / np.cos(np.deg2rad(39.85)))
    ax.set_xticks([])
    ax.set_yticks([])
    ax.minorticks_off()
    # 20 km scale bar
    km_deg = 20 / (111.32 * np.cos(np.deg2rad(38.85)))
    x0, y0 = -75.70, 38.76
    ax.plot([x0, x0 + km_deg], [y0, y0], color="black", lw=3, zorder=10)
    ax.text(x0 + km_deg / 2, y0 + 0.02, "20 km", ha="center", va="bottom",
            fontsize=12.5, zorder=10)

    handles = [Patch(color=c, label=f"{r} m") for r, c in zip(RES[::-1], RES_COL[::-1])]
    leg1 = ax.legend(handles=handles, title="Model grid cell size", loc="upper left",
                     fontsize=12.5, title_fontsize=13, frameon=True, framealpha=0.92,
                     edgecolor="none", handlelength=1.2, borderaxespad=0.4)
    ax.add_artist(leg1)
    h2 = [
        Line2D([], [], color=C["boundary"], lw=3.2, label="Ocean boundary (storm tide in)"),
        Line2D([], [], color=C["accent"], marker="v", ls="", ms=9, mec="black", mew=0.6,
               label=f"River inflows ({len(inflow)})"),
        Line2D([], [], color="black", lw=2.0, label="Levees and dams"),
        Line2D([], [], marker="s", ls="", ms=8, mfc="white", mec="black", mew=1.2,
               label=f"Tide gauges ({n_check} + 2 at the boundary)"),
        Line2D([], [], marker="o", ls="", ms=6, mfc="#CC79A7", mec="white", mew=0.4,
               label=f"High-water marks ({len(hwm)})"),
    ]
    ax.legend(handles=h2, loc="lower right", fontsize=12.5, frameon=True,
              framealpha=0.92, edgecolor="none", borderaxespad=0.4, handlelength=1.6)

    if SIDE:
        # ---- side panel -----------------------------------------------------------------
        n_act = int(z["n_active"])
        y = 0.985
        side.text(0.0, y, "A compound-flood model\nof Hurricane Sandy", fontsize=22,
                  fontweight="bold", va="top", linespacing=1.1)
        y -= 0.115
        side.text(0.0, y, "SFINCS, 28-31 Oct 2012 (72 h), Cape May to\nthe Narrows, "
                  "Delaware Bay and River,\nRaritan River and Newark Bay",
                  fontsize=14.5, va="top", color="0.2", linespacing=1.2)
        y -= 0.125
        side.text(0.0, y, f"{n_act / 1e6:.2f} million active cells\n"
                  "25 m cells along shores and channels\nflood map on a 3.125 m ground model",
                  fontsize=14.5, va="top", fontweight="bold", linespacing=1.25)
        y -= 0.125
        side.text(0.0, y, "Everything acting together:", fontsize=16, va="top",
                  fontweight="bold")
        y -= 0.045
        drivers = [
            ("Storm tide", "surge + tide at the ocean boundary,\n"
                           "USACE NACCS Sandy simulation"),
            ("Waves", "SnapWave, incl. long (infragravity)\nwaves; NOAA CORA offshore"),
            ("Wind, pressure", "NACCS winds blended into ERA5"),
            ("Rain", "NOAA AORC hourly; soil soaks\nup part of it"),
            ("Rivers", f"{len(inflow)} inflows, USGS discharge"),
            ("Buildings", "NJ footprints block the flow"),
            ("Levees, dams", "Keansburg, Elizabeth, Rahway\n(USACE levee database)"),
        ]
        for head, body in drivers:
            side.text(0.0, y, head, fontsize=14.5, va="top", fontweight="bold", color="0.1")
            side.text(0.37, y, body, fontsize=14, va="top", color="0.2", linespacing=1.15)
            y -= 0.027 * (body.count("\n") + 1) + 0.02
        y -= 0.005
        side.text(0.0, y, "Checked against:", fontsize=16, va="top", fontweight="bold")
        y -= 0.045
        side.text(0.0, y, f"{len(hwm)} USGS high-water marks,\n{n_check} NOAA / USGS tide "
                  "gauges inside the model,\nFEMA's mapped Sandy flood extent", fontsize=14, va="top",
                  color="0.2", linespacing=1.2)

    save(fig, "fig1_model")


if __name__ == "__main__":
    main()
