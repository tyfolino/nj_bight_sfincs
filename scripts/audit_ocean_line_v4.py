#!/usr/bin/env python
"""Audit a v4 ocean water-level line (named-vertex CSV) against the bed and NACCS. Read-only.

    python scripts/audit_ocean_line_v4.py --line data/v4_design/ocean_line_v4.csv [--maps]

The line REPLACES the jagged -10 m isobath as v4's ocean arm (user 2026-09-27): cells
seaward of it become inactive, cells landward active at any depth, so the forced
water-level cells sit ON it. This checks what that would mean, before any mesh exists:

  A  geometry — length, vertex spacing, self-intersection, the two end vertices.
  B  the bed ALONG the line (bed_v4_coarse_25m, every 50 m): a forced cell must be wet
     (BoundaryArm.max_bed_m = -0.5); shallow stretches are listed with their place.
  C  the line vs the -10 m isobath it replaces: how far seaward / landward, and the area
     of water deeper than -10 m that becomes ACTIVE landward of the line (the cost).
  D  forcing support — every wet NACCS node within 2 km of the line (the builder's
     screen), and the largest along-line gap between them.
  E  setup double-counting (FINDINGS §22–23): Sandy peak vs ADCIRC depth over the line's
     own nodes. On the open coast shallow nodes ran ~+0.23 m above deep ones at the crest.

``--maps`` writes reports/figures/v4_ocean_line_{overview,profile,<zoom>}.png.
Prints, never gates.
"""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
import shapely
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[1]
BED = ROOT / "data" / "elevation_v4" / "bed_v4_coarse_25m.tif"
NACCS = ROOT / "data" / "NACCS" / "_sandy_parsed.npz"
FIG = ROOT / "reports" / "figures"
T = Transformer.from_crs(4326, 32618, always_xy=True)
TI = Transformer.from_crs(32618, 4326, always_xy=True)
STEP = 50.0
SUPPORT_M = 2000.0

# categorical slots 1–2 + text grey of the dataviz reference palette (light surface)
ORANGE, BLUE, GREY, INK = "#eb6834", "#2a78d6", "#52514e", "#0b0b0b"
ZOOMS = {  # lon0, lat0, lon1, lat1
    "cape_may": (-75.02, 38.82, -74.62, 39.12),
    "atlantic_city": (-74.62, 39.22, -74.18, 39.58),
    "barnegat": (-74.25, 39.62, -73.92, 40.02),
    "sandy_hook": (-74.12, 40.20, -73.86, 40.56),
}


def read_line(path: Path) -> tuple[pd.DataFrame, shapely.LineString]:
    v = pd.read_csv(path, comment="#")
    x, y = T.transform(v.lon.values, v.lat.values)
    v["x"], v["y"] = x, y
    return v, shapely.LineString(np.c_[x, y])


def bed_along(line) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    s = np.arange(0.0, line.length, STEP)
    p = shapely.line_interpolate_point(line, s)
    px, py = shapely.get_x(p), shapely.get_y(p)
    with rasterio.open(BED) as b:
        z = np.array([r[0] for r in b.sample(zip(px, py))], float)
        z[z == b.nodata] = np.nan
    return s, px, py, z


def runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """(start, stop) index pairs of True runs."""
    d = np.diff(np.r_[0, mask.astype(int), 0])
    return list(zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)))


def load_naccs():
    c = np.load(NACCS, allow_pickle=True)
    t = np.array([dt.datetime.strptime(str(s), "%Y%m%d%H%M") for s in c["times"]])
    win = (t >= dt.datetime(2012, 10, 24)) & (t <= dt.datetime(2012, 11, 1))
    wl = c["wl"][:, win]
    wet = (wl > -9000).all(axis=1)
    peak = np.where(wl > -9000, wl, np.nan).max(axis=1)
    x, y = T.transform(c["lon"], c["lat"])
    return dict(sp=c["sp"], lon=c["lon"], lat=c["lat"], x=x, y=y, depth=c["depth"], wet=wet, peak=peak)


def isobath_side(px, py, z):
    """Is the line seaward (bed < -10) of the isobath at each sample."""
    return z < -10.0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--line", type=Path, required=True)
    ap.add_argument("--maps", action="store_true")
    a = ap.parse_args()

    v, line = read_line(a.line)
    seg = np.hypot(np.diff(v.x), np.diff(v.y))
    print(f"A  {a.line.name}: {len(v)} vertices ({v.sp.notna().sum()} NACCS nodes), "
          f"{line.length / 1000:.1f} km; spacing median {np.median(seg) / 1000:.2f} km, "
          f"max {seg.max() / 1000:.2f} km ({v.name[np.argmax(seg)]} → {v.name[np.argmax(seg) + 1]}); "
          f"simple (no self-crossing): {line.is_simple}")
    turn = np.degrees(np.abs(np.diff(np.unwrap(np.arctan2(np.diff(v.y), np.diff(v.x))))))
    sharp = np.flatnonzero(turn > 60) + 1
    print(f"   turns > 60° at: {', '.join(f'{v.name[i]} ({turn[i - 1]:.0f}°)' for i in sharp) or 'none'}")

    s, px, py, z = bed_along(line)
    lon, lat = TI.transform(px, py)
    print(f"B  bed along the line (every {STEP:.0f} m): median {np.nanmedian(z):+.1f} m, "
          f"range {np.nanmin(z):+.1f}..{np.nanmax(z):+.1f}")
    for lim in (-0.5, -3.0, -5.0):
        m = z > lim
        print(f"   bed > {lim:+.1f} m: {m.sum() * STEP / 1000:.2f} km of the line")
    for i0, i1 in runs(z > -3.0):
        print(f"     shallow run {(i1 - i0) * STEP:.0f} m at ({lon[i0]:.4f}, {lat[i0]:.4f}), "
              f"bed max {np.nanmax(z[i0:i1]):+.1f}")

    sea = isobath_side(px, py, z)
    print(f"C  the line sits in water deeper than -10 m (i.e. SEAWARD of the isobath) on "
          f"{sea.mean():.0%} of its length; bed p10/p50/p90 {np.nanpercentile(z, 10):+.1f} / "
          f"{np.nanpercentile(z, 50):+.1f} / {np.nanpercentile(z, 90):+.1f} m")
    with rasterio.open(BED) as b:
        zb = b.read(1)
        from rasterio.features import geometry_mask

        # landward side = a 10 km strip on the line's LEFT (it runs south → north),
        # minus Delaware Bay (west of Cape May Point's meridian) — the bay's own deep
        # water is active through `always_active_boxes_ll` whatever this line does.
        strip = line.buffer(10000.0, single_sided=True)
        bay_x, _ = T.transform(-74.96, 38.9)
        strip = strip.difference(shapely.box(0, 0, bay_x, 1e7))
        inside = ~geometry_mask([strip], zb.shape, b.transform)
        deep = inside & (zb < -10.0) & (zb != b.nodata)
        print(f"   water deeper than -10 m in the 10 km LANDWARD of the line (becomes active): "
              f"{deep.sum() * 25 * 25 / 1e6:.1f} km² — cost, not error")

    n = load_naccs()
    d = shapely.distance(line, shapely.points(n["x"], n["y"]))
    sup = n["wet"] & (d <= SUPPORT_M)
    st = np.sort(shapely.line_locate_point(line, shapely.points(n["x"][sup], n["y"][sup])))
    gaps = np.diff(np.r_[0.0, st, line.length])
    print(f"D  wet NACCS nodes within {SUPPORT_M / 1000:.0f} km of the line: {sup.sum()}; along-line "
          f"gap median {np.median(gaps):.0f} m, max {gaps.max() / 1000:.2f} km "
          f"(at {np.argmax(gaps) and st[np.argmax(gaps) - 1] / 1000:.1f} km from the south end)")

    on = v.sp.notna()
    dep, pk = v.naccs_depth_m[on].values, v.sandy_peak_msl_m[on].values
    slope, icpt = np.polyfit(dep, pk, 1)
    r = np.corrcoef(dep, pk)[0, 1]
    print(f"E  the line's own nodes: depth {dep.min():.1f}..{dep.max():.1f} m; Sandy peak "
          f"{pk.min():.2f}..{pk.max():.2f} m MSL; peak-vs-depth slope {slope:+.4f} m/m (r {r:+.2f}) "
          f"— the 8–18 m gap fills vs 10–15: peak {np.mean(pk[(dep < 10) | (dep > 15)]):.2f} vs "
          f"{np.mean(pk[(dep >= 10) & (dep <= 15)]):.2f} m. A latitude trend (the storm's) is mixed in; "
          f"read with the map.")

    if a.maps:
        maps(v, line, s, lon, lat, z, n, sup)
    return 0


def maps(v, line, s, lon, lat, z, n, sup) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap
    from rasterio.warp import Resampling, calculate_default_transform, reproject

    FIG.mkdir(parents=True, exist_ok=True)
    # sequential blue ramp (reference palette steps 100 → 700) for water depth
    blues = LinearSegmentedColormap.from_list(
        "depth", ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
    )
    with rasterio.open(BED) as b:
        tr, w, h = calculate_default_transform(b.crs, "EPSG:4326", b.width // 4, b.height // 4, *b.bounds)
        zz = np.full((h, w), np.nan, "float32")
        reproject(b.read(1, out_shape=(b.height // 4, b.width // 4)), zz,
                  src_transform=b.transform * b.transform.scale(4, 4), src_crs=b.crs,
                  dst_transform=tr, dst_crs="EPSG:4326", resampling=Resampling.average,
                  src_nodata=b.nodata, dst_nodata=np.nan)
    ext = (tr.c, tr.c + w * tr.a, tr.f + h * tr.e, tr.f)

    def base(ax, box):
        water = np.where(zz < 0, -zz, np.nan)
        ax.imshow(np.where(zz >= 0, 1.0, np.nan), extent=ext, cmap="Greys", vmin=0, vmax=6, zorder=0)
        im = ax.imshow(water, extent=ext, cmap=blues, vmin=0, vmax=30, zorder=1)
        ax.contour(np.linspace(ext[0], ext[1], w), np.linspace(ext[3], ext[2], h), zz,
                   levels=[-10], colors=GREY, linewidths=0.8, zorder=2)
        ax.scatter(n["lon"][n["wet"]], n["lat"][n["wet"]], s=6, c="#a3a29c", lw=0, zorder=3)
        ax.plot(v.lon, v.lat, color=ORANGE, lw=2, zorder=4)
        node = v.sp.notna()
        ax.scatter(v.lon[node], v.lat[node], s=26, c=ORANGE, edgecolors="#fcfcfb", linewidths=1.2, zorder=5)
        ax.set_xlim(box[0], box[2])
        ax.set_ylim(box[1], box[3])
        ax.set_aspect(1 / np.cos(np.radians((box[1] + box[3]) / 2)))
        ax.tick_params(labelsize=8, colors=GREY)
        for sp_ in ax.spines.values():
            sp_.set_color("#d8d7d2")
        return im

    handles = [
        plt.Line2D([], [], color=ORANGE, lw=2, marker="o", mfc=ORANGE, mec="#fcfcfb", label="draft line + its NACCS nodes"),
        plt.Line2D([], [], color=GREY, lw=0.8, label="−10 m isobath (today's arm)"),
        plt.Line2D([], [], color="#a3a29c", lw=0, marker="o", ms=3, label="other wet NACCS nodes"),
    ]
    fig, ax = plt.subplots(figsize=(7.5, 10), facecolor="#fcfcfb")
    im = base(ax, (-75.1, 38.75, -73.8, 40.55))
    for k, bx in ZOOMS.items():
        ax.add_patch(plt.Rectangle(bx[:2], bx[2] - bx[0], bx[3] - bx[1], fill=False, ec=INK, lw=0.6, ls="--", zorder=6))
        ax.text(bx[0], bx[3], f" {k.replace('_', ' ')}", fontsize=8, color=INK, va="bottom", zorder=6)
    ax.legend(handles=handles, loc="lower right", fontsize=8, frameon=True, facecolor="#fcfcfb")
    fig.colorbar(im, ax=ax, shrink=0.5, label="water depth (m below NAVD88)")
    ax.set_title("Draft ocean water-level line through NACCS nodes", fontsize=11, color=INK, loc="left")
    fig.savefig(FIG / "v4_ocean_line_overview.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    for k, bx in ZOOMS.items():
        fig, ax = plt.subplots(figsize=(7, 7), facecolor="#fcfcfb")
        base(ax, bx)
        node = v.sp.notna()
        inbox = node & (v.lon > bx[0]) & (v.lon < bx[2]) & (v.lat > bx[1]) & (v.lat < bx[3])
        for _, r in v[inbox].iterrows():
            ax.annotate(f"{int(r.sp)}\n{r.naccs_depth_m:.0f} m", (r.lon, r.lat), xytext=(5, 3),
                        textcoords="offset points", fontsize=6.5, color=GREY, zorder=7)
        ax.legend(handles=handles, loc="lower right", fontsize=7, facecolor="#fcfcfb")
        ax.set_title(k.replace("_", " ").title(), fontsize=11, color=INK, loc="left")
        fig.savefig(FIG / f"v4_ocean_line_{k}.png", dpi=150, bbox_inches="tight")
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 3.2), facecolor="#fcfcfb")
    ax.plot(s / 1000, z, color=BLUE, lw=1.5)
    ax.axhline(-10, color=GREY, lw=0.8, ls="--")
    ax.axhline(-0.5, color="#d03b3b", lw=0.8, ls=":")
    ax.text(0.3, -10, " −10 m (today's arm)", fontsize=8, color=GREY, va="bottom")
    ax.text(0.3, -0.5, " −0.5 m: a forced cell must be wetter than this", fontsize=8, color="#d03b3b", va="bottom")
    ax.set_xlabel("distance along the line from Cape May (km)", fontsize=9, color=GREY)
    ax.set_ylabel("bed (m NAVD88)", fontsize=9, color=GREY)
    ax.set_title("Bed along the draft line", fontsize=11, color=INK, loc="left")
    ax.tick_params(labelsize=8, colors=GREY)
    ax.grid(axis="y", color="#e8e7e2", lw=0.6)
    for sp_ in ("top", "right"):
        ax.spines[sp_].set_visible(False)
    fig.savefig(FIG / "v4_ocean_line_profile.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"maps -> {FIG}/v4_ocean_line_*.png")


if __name__ == "__main__":
    raise SystemExit(main())
