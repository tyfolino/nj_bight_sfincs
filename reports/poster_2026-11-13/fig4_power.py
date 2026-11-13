"""Poster Figure 4: New Jersey power plants and substations that Sandy floods.

    python fig4_power.py 2012   -> fig4_power_2012bed.{png,pdf}   Model 1.1.0 (2012 ground)
    python fig4_power.py 2026 [--no-title] -> fig4_power_2026bed.{png,pdf}   the same storm on 2026 ground (PRELIMINARY),
                                   with the sites that change against the 2012 ground ringed

Inputs: exposure/<tag>_assets.csv + exposure/<tag>_faces.npz from exposure_poster.py.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import ListedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from poster_style import C, apply, save  # noqa: E402

ROOT = HERE.parents[1]
EXP = HERE / "exposure"
CENSUS = ROOT / "logs" / "power_exposure_v11_2026-11-09" / "census"
TAGS = {"2012": "v110_2012bed", "2026": os.environ.get("FIG4_TAG26", "v11_modernb_2026bed")}
SUFFIX = os.environ.get("FIG4_SUFFIX", "")  # a test render goes beside, never over, the real one
ZOOM = (552_000, 600_000, 4_480_000, 4_532_000)  # Newark Bay / Meadowlands / Raritan (UTM 18N)
BIN = 300.0  # m, the flood-shading raster
FLOOD = "#3F8FCC"
NOTITLE = False  # set by --no-title


def load(tag):
    a = pd.read_csv(EXP / f"{tag}_assets.csv", index_col="asset")
    a = a[(a.us_state == "NJ") & (a.state != "out_of_model")]
    return a, np.load(EXP / f"{tag}_faces.npz")


def shade(ax, f, ext):
    """Sandy's water on normally-dry land (blue) over the model area (light grey), binned at BIN m."""
    xe = np.arange(ext[0], ext[1] + BIN, BIN)
    ye = np.arange(ext[2], ext[3] + BIN, BIN)
    area = lambda lev: (200.0 / 2.0 ** (lev.astype("f8") - 1)) ** 2  # noqa: E731
    act, _, _ = np.histogram2d(f["act_y"], f["act_x"], [ye, xe], weights=area(f["act_lev"]))
    fl, _, _ = np.histogram2d(f["fl_y"], f["fl_x"], [ye, xe], weights=area(f["fl_lev"]))
    a = BIN * BIN
    img = np.where(fl > 0.3 * a, 1.0, np.nan)
    ax.imshow(img, origin="lower", extent=(xe[0], xe[-1], ye[0], ye[-1]), cmap=ListedColormap([FLOOD]),
              vmin=0, vmax=1, interpolation="nearest", zorder=1)
    xc, yc = 0.5 * (xe[1:] + xe[:-1]), 0.5 * (ye[1:] + ye[:-1])
    ax.contour(xc, yc, (act > 0.3 * a).astype(float), levels=[0.5], colors="#555555",
               linewidths=1.0, linestyles="--", zorder=2)


def basemap(ax, ext, states):
    ax.set_facecolor(C["water"])
    states.plot(ax=ax, color=C["land"], edgecolor="#8C8C8C", linewidth=0.8, zorder=0)
    ax.set_xlim(ext[0], ext[1])
    ax.set_ylim(ext[2], ext[3])
    ax.set_aspect("equal")
    ax.tick_params(which="both", bottom=False, left=False, top=False, right=False,
                   labelbottom=False, labelleft=False)


def assets(ax, a, big, flips=None):
    size = lambda d: np.where(d.klass == "plant", 1.6, 1.0) * big  # noqa: E731
    nc = a[a.state == "not_computed"]
    ax.scatter(nc.x, nc.y, s=size(nc) * 0.8, marker="x", color="#444444", linewidths=1.2, zorder=3)
    dry = a[a.state.isin(["dry", "on_water"])]
    ax.scatter(dry.x, dry.y, s=size(dry), color=C["dry"], edgecolor="white", linewidth=0.6, zorder=4)
    wet = a[a.state == "wet"]
    ax.scatter(wet.x, wet.y, s=size(wet), color=C["wet"], edgecolor="black", linewidth=0.6, zorder=5)
    if flips is not None and len(flips):
        ax.scatter(flips.x, flips.y, s=size(flips) * 4.5, facecolor="none", edgecolor="black",
                   linewidth=2.0, zorder=6)


def scalebar(ax, x, y, km=20):
    ax.plot([x, x + km * 1e3], [y, y], color="black", linewidth=3, solid_capstyle="butt", zorder=7)
    ax.text(x + km * 500, y + 1500, f"{km} km", ha="center", va="bottom", fontsize=14, zorder=7)


def main(which: str) -> None:
    apply()
    a, f = load(TAGS[which])
    counts = a.state.replace({"on_water": "dry"}).value_counts()
    nwet, ndry, nnc = (int(counts.get(k, 0)) for k in ("wet", "dry", "not_computed"))
    flips = None
    if which == "2026":
        a12, _ = load(TAGS["2012"])
        s12 = a12.state.replace({"on_water": "dry"})
        s26 = a.state.replace({"on_water": "dry"})
        j = s26.to_frame("s26").join(s12.rename("s12"), how="inner")
        to_wet = j.index[(j.s26 == "wet") & (j.s12 == "dry")]
        to_dry = j.index[(j.s26 == "dry") & (j.s12 == "wet")]
        flips = a.loc[to_wet.union(to_dry)]
        c12 = s12.value_counts()
    states = gpd.read_file(f"zip://{CENSUS / 'cb_2023_us_state_500k.zip'}").to_crs(32618)
    states = states[states.STUSPS.isin(["NJ", "NY", "PA", "DE", "MD", "CT"])]

    ext = (float(f["act_x"].min()) - 4e3, float(f["act_x"].max()) + 4e3,
           float(f["act_y"].min()) - 4e3, float(f["act_y"].max()) + 4e3)
    fig = plt.figure(figsize=(12, 10.5))
    gs = fig.add_gridspec(2, 2, width_ratios=[1.0, 1.0], height_ratios=[1.15, 1.0],
                          wspace=0.06, hspace=0.12)
    ax = fig.add_subplot(gs[:, 0])
    basemap(ax, ext, states)
    shade(ax, f, ext)
    assets(ax, a, 26, flips)
    ax.add_patch(Rectangle((ZOOM[0], ZOOM[2]), ZOOM[1] - ZOOM[0], ZOOM[3] - ZOOM[2], fill=False,
                           edgecolor="black", linewidth=1.5, zorder=8))
    ax.text(ZOOM[0] - 1500, ZOOM[3], "B", ha="right", va="top", fontsize=18, weight="bold", zorder=8)
    scalebar(ax, ext[0] + 8e3, ext[2] + 8e3, 25)
    ax.set_title("A   New Jersey coast", loc="left", fontsize=17)
    for x, y, t in ((486_000, 4_322_000, "Delaware\nBay"), (603_000, 4_395_000, "Atlantic\nOcean")):
        if ext[0] < x < ext[1] and ext[2] < y < ext[3]:
            ax.text(x, y, t, ha="center", va="center", fontsize=14, style="italic", color="#4A6F8A")

    az = fig.add_subplot(gs[0, 1])
    basemap(az, ZOOM, states)
    shade(az, f, ZOOM)
    assets(az, a, 60, flips)
    scalebar(az, ZOOM[1] - 14e3, ZOOM[2] + 3e3, 10)
    az.set_title("B   Newark Bay and the Meadowlands", loc="left", fontsize=17)

    # the counts, large
    at = fig.add_subplot(gs[1, 1])
    at.axis("off")
    rows = [(nwet, "flood", C["wet"]), (ndry, "stay dry", C["dry"]), (nnc, "not computed", "#444444")]
    for i, (n, lab, col) in enumerate(rows):
        yy = 0.86 - i * 0.24
        at.text(0.02, yy, f"{n}", fontsize=46, weight="bold", color="black", va="center",
                transform=at.transAxes)
        at.text(0.30, yy, lab, fontsize=24, va="center", transform=at.transAxes)
        if which == "2026":
            k = {"flood": "wet", "stay dry": "dry", "not computed": "not_computed"}[lab]
            at.text(0.30, yy - 0.09, f"Model 1.1.0, 2012 ground: {int(c12.get(k, 0))}", fontsize=15,
                    color="#555555", va="center", transform=at.transAxes)
    at.text(0.02, 0.12, f"of {len(a)} New Jersey power plants and\nsubstations in the region; {len(a) - nnc} inside the model",
            fontsize=16, va="center", transform=at.transAxes)

    handles = [
        Line2D([], [], marker="o", ls="", color=C["wet"], markeredgecolor="black", markersize=12,
               label="Floods (≥ 0.15 m on site)"),
        Line2D([], [], marker="o", ls="", color=C["dry"], markeredgecolor="white", markersize=12,
               label="Stays dry"),
        Line2D([], [], marker="x", ls="", color="#444444", markersize=10, markeredgewidth=1.5,
               label="Not computed (edge of model)"),
        Patch(facecolor=FLOOD, label="Sandy's water on dry land"),
        Line2D([], [], color="#555555", ls="--", lw=1.2, label="Edge of the model"),
    ]
    if which == "2026":
        handles.insert(3, Line2D([], [], marker="o", ls="", markerfacecolor="none",
                                 markeredgecolor="black", markeredgewidth=2, markersize=16,
                                 label=f"Differs from Model 1.1.0 ({len(flips)})"))
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False, fontsize=14,
               bbox_to_anchor=(0.5, -0.02))

    if which == "2012":
        title = "Hurricane Sandy would flood today's power sites"
        cap = ("Model 1.1.0 hindcast of Sandy (2012 storm, 2012 ground and sea level) against today's plants and "
               "substations.\nLarger marks = power plants. Flooding means water on site, not failure: "
               "floor heights and site walls are unknown.")
    else:
        title = "Sandy on today's (2026) ground — PRELIMINARY"
        cap = ("Model 1.1.0's storm and 2012 sea level on 2026 ground (unvalidated bed; buildings and land cover still "
               "2012) with today's walls:\nElizabeth / Rahway levees re-tied, Port Monmouth floodwall + Pews Creek gate "
               "shut. Rings: sites where the two runs differ. Larger marks = power plants.")
    if NOTITLE:  # the poster prints without title + caption (the poster caption carries them)
        fig.subplots_adjust(top=0.96, bottom=0.10, left=0.02, right=0.98)
    else:
        fig.suptitle(title, x=0.02, ha="left", y=0.998, fontsize=24, weight="bold")
        fig.text(0.02, 0.952, cap, ha="left", va="top", fontsize=13, color="#333333")
        fig.subplots_adjust(top=0.865, bottom=0.10, left=0.02, right=0.98)
    save(fig, f"fig4_power_{which}bed{SUFFIX}")


if __name__ == "__main__":
    NOTITLE = "--no-title" in sys.argv[2:]
    main(sys.argv[1])
