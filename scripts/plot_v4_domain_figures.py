"""v4 design figures: the SnapWave domain, and the MOTF extent as it is SCORED.

    NJ_DOMAIN=v4 PYTHONPATH=$PWD python scripts/plot_v4_domain_figures.py [snapwave|motf|all]
    -> reports/figures/v4_snapwave_domain.png, reports/figures/v4_motf_scored.png

Both read the FROZEN mesh and the domain registry, so they redraw what a build would use:
the SnapWave mask comes from ``snapwave_domain.build_snapwave_mask`` with the same
``domain_cell_sets`` inputs ``model.add_waves`` passes (STATUS 09-29), the MOTF screen
from ``validate.metrics.motf_exclude_mask`` — the scorer's own function. Faces are binned
onto a 250 m UTM raster (priority: boundary > band > waves > SFINCS-only) for the
overview; the insets are 100 m.

Colour: the dataviz reference palette's first three categorical slots (the all-pairs cap
for a map), neutral greys for context, ink for lines; text never wears a series colour.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import geopandas as gpd  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import rasterio  # noqa: E402
import xarray as xr  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from pyproj import Transformer  # noqa: E402

import nj_sfincs  # noqa: F401,E402 — pyproj before hydromt
from nj_sfincs import domain as _domain  # noqa: E402
from nj_sfincs import snapwave_domain as sd  # noqa: E402

FIG = ROOT / "reports" / "figures"
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"  # categorical slots 1-3
GREY = "#c9c8c3"  # context: computed, not the subject
GREY_LIGHT = "#ecebe7"

plt.rcParams.update(
    {
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "axes.edgecolor": INK_2,
        "axes.labelcolor": INK_2,
        "xtick.color": INK_2,
        "ytick.color": INK_2,
        "text.color": INK,
        "font.size": 9,
    }
)


def _lines(dom):
    """Ring and forced line in UTM."""
    ring = gpd.read_file(dom.region).to_crs(dom.epsg)
    fw = Transformer.from_crs(4326, dom.epsg, always_xy=True)
    ln = _domain.read_waterlevel_line(dom.waterlevel_line)
    lx, ly = fw.transform([p[1] for p in ln], [p[2] for p in ln])
    return ring, np.asarray(lx), np.asarray(ly)


def _bin(fx, fy, cat, win, res, size=None):
    """Face categories -> a raster over ``win`` (x0, x1, y0, y1); highest code wins.

    ``size`` (face edge length [m]) paints each face over its whole square, so a 200 m
    face on a 100 m raster fills 2 x 2 pixels instead of leaving a checkerboard.
    """
    x0, x1, y0, y1 = win
    nx, ny = int((x1 - x0) / res), int((y1 - y0) / res)
    img = np.zeros((ny, nx), np.int8)
    k = (
        np.ones(fx.shape, int)
        if size is None
        else np.maximum(1, (size / res).astype(int))
    )
    order = np.argsort(cat)  # write low codes first so high codes win
    for kk in np.unique(k):
        s = order[(k[order] == kk) & (cat[order] > 0)]
        c0 = ((fx[s] - x0) / res - kk / 2).round().astype(int)
        r0 = ((y1 - fy[s]) / res - kk / 2).round().astype(int)
        for dr in range(kk):
            for dc in range(kk):
                r, c = r0 + dr, c0 + dc
                ok = (c >= 0) & (c < nx) & (r >= 0) & (r < ny)
                img[r[ok], c[ok]] = cat[s][ok]
    return img


def _decorate(ax, dom, ring, lx, ly, win, title=None):
    ring.boundary.plot(ax=ax, color=INK_2, lw=0.6)
    ax.plot(lx, ly, color=INK, lw=1.1)
    ax.set_xlim(win[0], win[1])
    ax.set_ylim(win[2], win[3])
    ax.set_aspect(1)
    ax.set_xticks([])
    ax.set_yticks([])
    if title:
        ax.set_title(title, fontsize=9, color=INK, loc="left")


def snapwave(dom) -> Path:
    ds = xr.open_dataset(dom.frozen_mesh_dir() / "sfincs.nc")
    n, m, lev = ds["n"].values, ds["m"].values, ds["level"].values
    z, sm = ds["z"].values, ds["mask"].values
    fx, fy = ds["mesh2d_face_x"].values, ds["mesh2d_face_y"].values
    attrs = {k: float(ds.attrs[k]) for k in ("x0", "y0", "dx", "dy", "rotation")}
    size = attrs["dx"] / 2.0 ** (lev - 1)  # face edge [m]
    steps = _domain.SNAPWAVE_STEPS["v4_shelf_steps"]
    sea, fp = sd.domain_cell_sets(dom, f"EPSG:{dom.epsg}", fx, fy, z)
    swm, info = sd.build_snapwave_mask(
        n, m, lev, z, sm, steps, dom.mask_zmin, sea=sea, footprint=fp
    )
    # 1 SFINCS only (no waves), 2 waves on SFINCS, 3 SnapWave-only band, 4 boundary
    cat = np.zeros(z.shape, np.int8)
    cat[sm > 0] = 1
    cat[(sm > 0) & (swm > 0)] = 2
    cat[(sm == 0) & (swm == 1)] = 3
    cat[swm == 2] = 4
    cmap = ListedColormap([SURFACE, GREY, BLUE, AQUA, ORANGE])
    ring, lx, ly = _lines(dom)
    poly = sd.boundary_polyline(steps, attrs)
    bxy = np.c_[fx, fy][(swm == 2) & (z < -5.0)]
    pts = sd.support_points(poly, bxy, 63)

    fig = plt.figure(figsize=(12, 10.5))
    ax = fig.add_axes([0.02, 0.06, 0.55, 0.86])
    win = (434_000, 628_000, 4_283_000, 4_540_000)
    ax.imshow(
        _bin(fx, fy, cat, win, 250),
        extent=(win[0], win[1], win[2], win[3]),
        cmap=cmap,
        vmin=0,
        vmax=4,
        interpolation="nearest",
    )
    _decorate(ax, dom, ring, lx, ly, win)
    ax.plot(poly[:, 0], poly[:, 1], color=ORANGE, lw=1.2)
    ax.scatter(
        pts[:, 0], pts[:, 1], s=18, facecolor=SURFACE, edgecolor=INK, lw=0.8, zorder=5
    )
    head = [
        (v[1], v[2])
        for v in dict((f[0], f[1]) for f in dom.snapwave_footprint_ll)["delaware_bay"][
            :2
        ]
    ]
    hx, hy = Transformer.from_crs(4326, dom.epsg, always_xy=True).transform(*zip(*head))
    ax.plot(hx, hy, color=INK, lw=1.0, ls="--")
    for lab, (x, y) in {
        "Delaware Bay": (455_000, 4_345_000),
        "head of bay: Liston Pt – Hope Ck": (437_000, 4_374_000),
        "apron\n(outside\nthe ring)": (585_000, 4_505_000),
    }.items():
        ax.text(x, y, lab, fontsize=8, color=INK_2)

    for k, (w, t) in enumerate(
        [
            (
                (486_000, 524_000, 4_283_000, 4_318_000),
                "Delaware mouth — bottom row forced",
            ),
            (
                (575_000, 606_000, 4_470_000, 4_496_000),
                "NE: the apron leg to Long Beach NY",
            ),
        ]
    ):
        axi = fig.add_axes([0.60, 0.52 - k * 0.44, 0.38, 0.40])
        axi.imshow(
            _bin(fx, fy, cat, w, 100, size),
            extent=(w[0], w[1], w[2], w[3]),
            cmap=cmap,
            vmin=0,
            vmax=4,
            interpolation="nearest",
        )
        _decorate(axi, dom, ring, lx, ly, w, t)
        axi.scatter(
            pts[:, 0],
            pts[:, 1],
            s=26,
            facecolor=SURFACE,
            edgecolor=INK,
            lw=0.8,
            zorder=5,
        )
        for s in axi.spines.values():
            s.set_color(INK_2)
        ax.add_patch(
            plt.Rectangle(
                (w[0], w[2]), w[1] - w[0], w[3] - w[2], fill=False, ec=INK_2, lw=0.8
            )
        )

    handles = [
        Patch(
            color=BLUE,
            label=f"waves on the SFINCS domain ({(cat == 2).sum() / 1e6:.2f} M faces)",
        ),
        Patch(
            color=AQUA,
            label=f"SnapWave-only shelf band ({info['n_band'] / 1e3:.0f} k, 200 m)",
        ),
        Patch(
            color=ORANGE,
            label=f"wave boundary ({info['n_boundary']:,} cells, CORA-forced)",
        ),
        Patch(
            color=GREY,
            label=f"SFINCS only, no waves ({info['n_sfincs_without_waves'] / 1e3:.0f} k)",
        ),
        plt.Line2D([], [], color=INK, lw=1.1, label="forced water-level line"),
        plt.Line2D([], [], color=INK_2, lw=0.6, label="v4 ring"),
        plt.Line2D(
            [],
            [],
            ls="",
            marker="o",
            mfc=SURFACE,
            mec=INK,
            label="63 wave support points",
        ),
    ]
    ax.legend(
        handles=handles,
        loc="upper left",
        bbox_to_anchor=(0.005, 0.995),
        fontsize=8,
        frameon=True,
        facecolor=SURFACE,
        edgecolor=GREY_LIGHT,
    )
    fig.suptitle(
        "v4 SnapWave domain — v4_shelf_steps: v3's grid-aligned band redrawn on v4, "
        f"{info['n_active'] / 1e6:.2f} M wave cells (v3 2.89 M)",
        x=0.02,
        ha="left",
        fontsize=11,
        color=INK,
    )
    fig.text(
        0.02,
        0.02,
        "Waves on v3's area + Delaware Bay below the Liston Point – Hope Creek line (user "
        "09-29); predicted dead cells 7 of 1,541 (one per step corner). Frozen v4 mesh, "
        "premier.V4 23ea65f8.",
        fontsize=8,
        color=INK_2,
    )
    out = FIG / "v4_snapwave_domain.png"
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return out


def motf(dom) -> Path:
    from nj_sfincs.validate.metrics import motf_exclude_mask

    with rasterio.open(dom.motf_tif) as r:
        motf_a, T = r.read(1), r.transform
    excl = motf_exclude_mask(motf_a.shape, T)
    # land in the ring, from the coarse bed on the MOTF grid (the scorer screens on the
    # run's own dep > 0 and msk; this figure only needs where land is)
    from rasterio.warp import Resampling, reproject

    bed = np.full(motf_a.shape, np.nan, np.float32)
    with rasterio.open(_domain.DATA / "elevation_v4" / "bed_v4_coarse_25m.tif") as b:
        reproject(
            rasterio.band(b, 1),
            bed,
            dst_transform=T,
            dst_crs=f"EPSG:{dom.epsg}",
            dst_nodata=np.nan,
            resampling=Resampling.nearest,
        )
    from rasterio.features import rasterize

    ring, lx, ly = _lines(dom)
    inring = rasterize(
        [(g, 1) for g in ring.geometry], out_shape=motf_a.shape, transform=T, fill=0
    ).astype(bool)
    land = inring & (bed > 0)
    # 1 scored dry NJ land, 2 excluded (not NJ), 3 MOTF wet on scored land
    cat = np.zeros(motf_a.shape, np.int8)
    cat[land] = 1
    cat[land & excl] = 2
    cat[land & ~excl & (motf_a == 1)] = 3
    k = 8  # 120 m display pixels
    img = cat[::k, ::k]
    ext = (T.c, T.c + motf_a.shape[1] * T.a, T.f + motf_a.shape[0] * T.e, T.f)
    km2 = abs(T.a * T.e) / 1e6

    fig, ax = plt.subplots(figsize=(9.5, 12))
    ax.imshow(
        img,
        extent=ext,
        cmap=ListedColormap([SURFACE, GREY_LIGHT, GREY, BLUE]),
        vmin=0,
        vmax=3,
        interpolation="nearest",
    )
    _decorate(ax, dom, ring, lx, ly, (ext[0], ext[1], ext[2], ext[3]))
    fw = Transformer.from_crs(4326, dom.epsg, always_xy=True)
    xa, ya = fw.transform([-75.9, -73.4], [40.62, 40.62])
    ax.plot(xa, ya, color=INK_2, lw=0.8, ls="--")
    ax.text(
        xa[0] + 3000,
        ya[0] + 1500,
        "the 09-24 render stopped here (40.62 N)",
        fontsize=8,
        color=INK_2,
    )
    handles = [
        Patch(
            color=BLUE,
            label=f"MOTF flooded, scored ({(cat == 3).sum() * km2:,.0f} km²)",
        ),
        Patch(
            color=GREY_LIGHT,
            label=f"MOTF dry NJ land, scored ({(cat == 1).sum() * km2:,.0f} km²)",
        ),
        Patch(
            color=GREY, label=f"not NJ — excluded ({(cat == 2).sum() * km2:,.0f} km²)"
        ),
        plt.Line2D([], [], color=INK, lw=1.1, label="forced water-level line"),
        plt.Line2D([], [], color=INK_2, lw=0.6, label="v4 ring"),
    ]
    ax.legend(
        handles=handles,
        loc="lower right",
        fontsize=8,
        facecolor=SURFACE,
        edgecolor=GREY_LIGHT,
    )
    ax.set_title(
        "v4 FEMA MOTF extent as scored — re-rendered on the ring, NJ land only (09-29)",
        loc="left",
        fontsize=11,
        color=INK,
    )
    fig.text(
        0.02,
        0.015,
        "The MOTF layer is NJ-only and renders other states as dry; the scorer counts only "
        "pixels where the NJ 10 ft DEM has data (Domain.motf_valid_tif). Land = coarse bed "
        "> 0 inside the ring (display only).",
        fontsize=8,
        color=INK_2,
        wrap=True,
    )
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    out = FIG / "v4_motf_scored.png"
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return out


def main() -> None:
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    dom = _domain.active()
    if dom.name != "v4":
        sys.exit("NJ_DOMAIN=v4 only")
    if which in ("snapwave", "all"):
        print("wrote", snapwave(dom))
    if which in ("motf", "all"):
        print("wrote", motf(dom))


if __name__ == "__main__":
    main()
