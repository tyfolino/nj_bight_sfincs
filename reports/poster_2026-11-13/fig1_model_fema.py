"""Poster v4 Figure 1: (a) the NJ-SFINCS model and (b) its Sandy flood extent vs FEMA, same extent.

    python reports/poster_2026-11-13/fig1_model_fema.py      (plotting only; reads cached inputs)

(a) the model grid by cell size, the drawn ocean boundary, river inflows, levees and water-level gauges
    (``fig1_data.npz`` / ``fig1_inflows.csv`` / ``fig1_gauges.csv`` / ``fig1_weirs.csv`` and
    ``data/v4_design/waterlevel_line_v4.csv``, the same inputs as fig1_model.py), warped to UTM 18N.
(b) Model 1.1.0 (rain ON, ``p4-premier+weir-elizabeth-rahway``) vs FEMA MOTF: the cached class raster made
    by fig3_motf.py (scorer rules; 15 m cells), the overview decimated 8x with fig3_motf.decimate, three
    insets at full 15 m with their local CSI, and the domain-wide CSI / POD / FAR, which must equal the
    published row (printed self-check).

Drawn at print size (18.5 in wide), so every font size here is the printed size.
"""

import sys
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
from fig3_motf import (  # noqa: E402
    DRY,
    EXCL,
    FALSE,
    HIT,
    MISS,
    NOTMODEL,
    OUTSIDE,
    WATER,
    counts,
    decimate,
    lonlat_box_to_rc,
)
from poster_style import C, apply, save  # noqa: E402

#: zoom insets (label, title, lon0, lon1, lat0, lat1). v5 (user 11-13): C = Atlantic City (Absecon Island
#: city blocks) instead of Cape May; A and B as in fig3_motf.INSETS.
INSETS = [
    ("A", "Hoboken, Jersey City, Newark Bay", -74.175, -74.015, 40.655, 40.765),
    ("B", "Barnegat Bay and Long Beach Island", -74.27, -74.07, 39.62, 39.80),
    ("C", "Atlantic City", -74.475, -74.405, 39.337, 39.383),
]
CLS = Path("/scratch/tpj8/poster_2026-11-13/fig3/"
           "v4_refreeze_swz_v11__p4-premier+weir-elizabeth-rahway__motf_classes.tif")
ROW = REPO / "logs/floodmap_fix_2026-11-12/rows/v4_refreeze_swz_v11__p4-premier+weir-elizabeth-rahway.csv"
NE = Path.home() / ".local/share/cartopy/shapefiles/natural_earth"
RES = [200, 100, 50, 25]
RES_COL = ["#C6DBEF", "#6BAED6", "#2171B5", "#08306B"]
FS = 16  # legend / label size (pt, printed)
FIG_W, FIG_H = 18.5, 8.3


def main():
    import rasterio
    from pyproj import Transformer
    from rasterio.transform import from_origin
    from rasterio.warp import Resampling, reproject

    apply()
    with rasterio.open(CLS) as r:
        cls = r.read(1)
        tr = r.transform
        epsg = r.crs.to_epsg()
    assert tr.b == 0 and tr.d == 0, "class raster expected north-up"
    st = counts(cls, abs(tr.a * tr.e) / 1e6)
    row = pd.read_csv(ROW).iloc[-1]
    d = max(abs(st[k] - float(row[f"motf_{k}"])) for k in ("csi", "pod", "far"))
    print(f"CSI {st['csi']:.6f} POD {st['pod']:.6f} FAR {st['far']:.6f} | row {row['motf_csi']:.6f} "
          f"{row['motf_pod']:.6f} {row['motf_far']:.6f} | max diff {d:.1e} {'OK' if d < 5e-4 else 'MISMATCH'}")
    print(f"km2 hit {st['km2_hit']:.1f} miss {st['km2_miss']:.1f} false {st['km2_false']:.1f}")

    # common extent (pixel window of the scored area + margin), as UTM coordinates
    scored = (cls >= DRY) | (cls == EXCL)
    rows = np.where(scored.any(1))[0]
    cols = np.where(scored.any(0))[0]
    pad = 320
    r0, r1 = max(rows[0] - pad, 0), min(rows[-1] + pad, cls.shape[0])
    c0, c1 = max(cols[0] - pad, 0), min(cols[-1] + pad, cls.shape[1])
    f = 8
    ov = decimate(cls[r0:r1, c0:c1], f)
    x0, y1 = tr * (c0, r0)
    x1 = x0 + ov.shape[1] * f * tr.a
    y0 = y1 + ov.shape[0] * f * tr.e
    ext = (x0, x1, y0, y1)
    aspect = (x1 - x0) / (y1 - y0)

    # ---- layout in inches ------------------------------------------------------------------------
    fig = plt.figure(figsize=(FIG_W, FIG_H))
    top_pad = 0.42
    mh = FIG_H - top_pad - 0.05
    mw = mh * aspect

    def axes_in(x, y, w, h):
        return fig.add_axes([x / FIG_W, y / FIG_H, w / FIG_W, h / FIG_H])

    axa = axes_in(0.02, 0.05, mw, mh)
    axb = axes_in(0.02 + mw + 0.25, 0.05, mw, mh)
    xi = 0.02 + 2 * mw + 0.55

    # ---- (a) model ---------------------------------------------------------------------------------
    z = np.load(HERE / "fig1_data.npz")
    grid = z["grid"]
    lon0, lat0, dlon, dlat = (float(z[k]) for k in ("lon0", "lat0", "dlon", "dlat"))
    ny, nx = grid.shape
    src = np.ascontiguousarray(grid[::-1].astype("float32"))
    res = 120.0
    dst = np.full((int(round((y1 - y0) / res)), int(round((x1 - x0) / res))), np.nan, "float32")
    reproject(src, dst, src_transform=from_origin(lon0, lat0 + ny * dlat, dlon, dlat), src_crs=4326,
              dst_transform=from_origin(x0, y1, res, res), dst_crs=epsg, resampling=Resampling.nearest,
              src_nodata=np.nan, dst_nodata=np.nan)
    to_utm = Transformer.from_crs(4326, epsg, always_xy=True)
    lonb, latb = to_utm.transform([x0, x1], [y0, y1], direction="INVERSE")
    from shapely.geometry import box
    bb = box(min(lonb) - 0.3, min(latb) - 0.3, max(lonb) + 0.3, max(latb) + 0.3)
    land = gpd.read_file(NE / "physical/ne_10m_land.shp", bbox=bb).clip(bb).to_crs(epsg)
    states = gpd.read_file(NE / "cultural/ne_10m_admin_1_states_provinces_lakes.shp", bbox=bb)
    states = states.clip(bb).to_crs(epsg)
    axa.set_facecolor("#EEF1F4")
    land.plot(ax=axa, color=C["land"], edgecolor="0.6", lw=0.4, zorder=1)
    states.boundary.plot(ax=axa, color="0.65", lw=0.6, zorder=1.5)
    cmap = ListedColormap(RES_COL[::-1])
    norm = BoundaryNorm([0, 37.5, 75, 150, 300], cmap.N)
    axa.imshow(np.ma.masked_invalid(dst), extent=ext, cmap=cmap, norm=norm, interpolation="nearest",
               zorder=2, alpha=0.95)
    line = pd.read_csv(REPO / "data/v4_design/waterlevel_line_v4.csv", comment="#")
    lx, ly = to_utm.transform(line.lon.values, line.lat.values)
    axa.plot(lx, ly, color=C["boundary"], lw=3.0, zorder=5, solid_capstyle="round")
    fx, fy = to_utm.transform(z["forced_lon"], z["forced_lat"])
    axa.scatter(fx, fy, s=2, color=C["boundary"], lw=0, zorder=5)
    weirs = pd.read_csv(HERE / "fig1_weirs.csv")
    for _, w in weirs.groupby("line"):
        wx, wy = to_utm.transform(w.lon.values, w.lat.values)
        axa.plot(wx, wy, color="black", lw=2.0, zorder=6)
    gauges = pd.read_csv(HERE / "fig1_gauges.csv")
    n_check = int((~gauges.name.isin(["sss_narrows_si", "sss_narrows_bkln"])).sum())
    gx, gy = to_utm.transform(gauges.lon.values, gauges.lat.values)
    axa.scatter(gx, gy, s=40, marker="s", facecolor="white", edgecolor="black", lw=1.1, zorder=8)
    inflow = pd.read_csv(HERE / "fig1_inflows.csv")
    ix, iy = to_utm.transform(inflow.lon.values, inflow.lat.values)
    axa.scatter(ix, iy, s=55, marker="v", facecolor=C["accent"], edgecolor="black", lw=0.6, zorder=9)
    axa.set_xlim(x0, x1)
    axa.set_ylim(y0, y1)
    axa.set_aspect("equal")
    for ax in (axa, axb):
        ax.set_xticks([])
        ax.set_yticks([])
        ax.minorticks_off()
    axa.set_title("a   The model", loc="left", fontsize=FS + 2, fontweight="bold", pad=6)
    km = 1000.0
    xb, yb = x0 + 0.06 * (x1 - x0), y0 + 0.04 * (y1 - y0)
    axa.plot([xb, xb + 20 * km], [yb, yb], color="k", lw=4, solid_capstyle="butt", zorder=10)
    axa.text(xb + 10 * km, yb + 0.012 * (y1 - y0), "20 km", ha="center", va="bottom", fontsize=FS - 2,
             zorder=10)

    # ---- (b) flood extent vs FEMA -------------------------------------------------------------------
    grey = "#BDBDBD"
    colours = {OUTSIDE: "#FFFFFF", WATER: C["water"], NOTMODEL: "#FFFFFF", EXCL: grey, DRY: "#E9E4D8",
               HIT: C["hit"], MISS: C["miss"], FALSE: C["false"]}
    ccm = ListedColormap([colours[k] for k in range(8)])
    kw = dict(cmap=ccm, vmin=-0.5, vmax=7.5, interpolation="nearest")
    axb.imshow(ov, extent=ext, **kw)
    axb.set_xlim(x0, x1)
    axb.set_ylim(y0, y1)
    axb.set_aspect("equal")
    axb.set_title("b   Flood extent vs FEMA", loc="left", fontsize=FS + 2, fontweight="bold", pad=6)

    # insets, stacked to the right of (b)
    boxes = [lonlat_box_to_rc(tr, lo0, lo1, la0, la1, epsg) for _, _, lo0, lo1, la0, la1 in INSETS]
    gap_t = 0.38
    avail = FIG_H - 0.1 - len(INSETS) * gap_t - 0.15 * (len(INSETS) - 1)
    hs = avail / len(INSETS)
    wi_max = 0.0
    yy = FIG_H - 0.05
    for (lab, title, *_), (rr0, rr1, cc0, cc1) in zip(INSETS, boxes):
        bx0, by1 = tr * (cc0, rr0)
        bx1, by0 = tr * (cc1, rr1)
        axb.add_patch(Rectangle((bx0, by0), bx1 - bx0, by1 - by0, fill=False, ec="k", lw=1.6, zorder=5))
        axb.text(bx1 + 1500, by1, lab, fontsize=FS + 2, fontweight="bold", va="top", ha="left", zorder=5)
        wi = hs * (cc1 - cc0) / (rr1 - rr0)
        wi_max = max(wi_max, wi)
        yy -= gap_t + hs
        ax = axes_in(xi, yy, wi, hs)
        sub = cls[rr0:rr1, cc0:cc1]
        ax.imshow(sub, extent=(bx0, bx1, by0, by1), **kw)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.minorticks_off()
        short = {"A": "Newark Bay, Jersey City", "B": "Barnegat Bay, LBI", "C": "Atlantic City"}[lab]
        ax.set_title(f"{lab}  {short}", fontsize=FS - 1, loc="left", pad=4)
        n = np.bincount(sub.ravel(), minlength=8)
        nh, nm, nf = n[HIT], n[MISS], n[FALSE]
        csi_i = nh / (nh + nm + nf)
        print(f"inset {lab}: CSI {csi_i:.3f}")
        ax.text(0.03, 0.04, f"CSI {csi_i:.2f}", transform=ax.transAxes, fontsize=FS - 2, va="bottom",
                ha="left", bbox=dict(boxstyle="square,pad=0.2", fc="white", ec="none", alpha=0.85))
        yy -= 0.15

    # ---- legends + scores column ---------------------------------------------------------------------
    xl = xi + wi_max + 0.35
    wl = FIG_W - xl - 0.02
    lg = axes_in(xl, 0.05, wl, FIG_H - 0.1)
    lg.axis("off")
    h_a = [Patch(color=c, label=f"{r_} m") for r_, c in zip(RES[::-1], RES_COL[::-1])]
    l1 = lg.legend(handles=h_a, title="a: grid cell size", loc="upper left", ncol=2, fontsize=FS,
                   title_fontsize=FS, frameon=False, handlelength=1.1, columnspacing=0.8,
                   borderaxespad=0.0, alignment="left")
    lg.add_artist(l1)
    h_a2 = [
        Line2D([], [], color=C["boundary"], lw=3, label="Ocean boundary (storm tide in)"),
        Line2D([], [], color=C["accent"], marker="v", ls="", ms=10, mec="black", mew=0.6,
               label=f"River inflows ({len(inflow)})"),
        Line2D([], [], color="black", lw=2, label="Levees and dams"),
        Line2D([], [], marker="s", ls="", ms=9, mfc="white", mec="black", mew=1.1,
               label=f"Water-level gauges ({n_check} + 2)"),
    ]
    l2 = lg.legend(handles=h_a2, loc="upper left", bbox_to_anchor=(0.0, 0.79), fontsize=FS,
                   frameon=False, handlelength=1.5, borderaxespad=0.0, labelspacing=0.3)
    lg.add_artist(l2)
    h_b = [
        Patch(fc=C["hit"], label="Both flooded"),
        Patch(fc=C["miss"], label="FEMA flooded, model dry"),
        Patch(fc=C["false"], label="Model flooded, FEMA dry"),
        Patch(fc="#E9E4D8", ec="#999999", lw=0.5, label="Dry in both"),
        Patch(fc=C["water"], label="Open water"),
        Patch(fc=grey, label="Not scored (outside NJ)"),
        Patch(fc="#FFFFFF", ec="#999999", lw=0.5, label="Outside the model"),
    ]
    lg.legend(handles=h_b, title="b: model vs FEMA", loc="upper left", bbox_to_anchor=(0.0, 0.47),
              fontsize=FS, title_fontsize=FS, frameon=False, handlelength=1.3, borderaxespad=0.0,
              labelspacing=0.3, alignment="left")
    for j, (k, v) in enumerate((("CSI", st["csi"]), ("POD", st["pod"]), ("FAR", st["far"]))):
        x = 0.0 + j * 0.34
        lg.text(x, 0.075, k, fontsize=FS, va="bottom", ha="left", transform=lg.transAxes)
        lg.text(x, 0.0, f"{v:.2f}", fontsize=30, fontweight="bold", va="bottom", ha="left",
                transform=lg.transAxes)

    save(fig, "fig1_model_fema")


if __name__ == "__main__":
    main()
