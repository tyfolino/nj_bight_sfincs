"""Map the bed around each bridge-as-dam candidate from `sweep_bed_dams.py`.

One figure per body: the native NJ lidar (~3 m) beside the 25 m coarse bed the sweep
ran on, same window, same colour scale, the wall/crest contour at the sweep's wet
threshold (−1 m) and at 0 m drawn on both. Lon/lat axes so the frame can be typed into
Google Maps. Re-labels the wet bodies exactly as the sweep did, hatches the body's cells and draws
the wall segment (body cell nearest the ocean -> nearest ocean cell) so the crest the CSV
quotes is visible. Reads `reports/bed_dams_v3.csv`; writes `reports/figures/bed_dam_<body>.png`.

    python scripts/plot_bed_dam_candidates.py [--bodies 1450 980 62 157] [--half-km 1.5]
"""
import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.features import rasterize
from scipy import ndimage
from matplotlib.colors import TwoSlopeNorm
from pyproj import Transformer
from rasterio.warp import Resampling, reproject

ROOT = Path(__file__).resolve().parents[1]
COARSE = ROOT / "data/elevation_v3/bed_v3_coarse_25m.tif"
FINE = ROOT / "data/elevation_v3/nj_10ft_dem_v3.tif"
CSV = ROOT / "reports/bed_dams_v3.csv"
OUT = ROOT / "reports/figures"
WET_Z = -1.0


def label_bodies():
    """Same labelling as sweep_bed_dams.py: wet = z < WET_Z inside the ring, 4-connected."""
    import os
    os.environ.setdefault("NJ_DOMAIN", "v3")
    from nj_sfincs import domain as _domain
    with rasterio.open(COARSE) as src:
        z = src.read(1).astype("float32"); z[z == src.nodata] = np.nan
        tr, crs = src.transform, src.crs
    ring = gpd.read_file(_domain.active().region).to_crs(crs)
    inside = rasterize(((g, 1) for g in ring.geometry), out_shape=z.shape,
                       transform=tr, fill=0, dtype="uint8").astype(bool)
    wet = inside & (z < WET_Z)
    lab, n = ndimage.label(wet, structure=[[0, 1, 0], [1, 1, 1], [0, 1, 0]])
    sizes = ndimage.sum(wet, lab, index=np.arange(1, n + 1))
    ocean = int(np.argmax(sizes)) + 1
    _, (iy, ix) = ndimage.distance_transform_edt(lab != ocean, return_indices=True)
    return z, lab, ocean, iy, ix, tr


def window_arrays(x, y, half_m, fine_res=5.0):
    """Both rasters resampled onto one UTM grid centred on (x, y)."""
    left, bottom = x - half_m, y - half_m
    n = int(2 * half_m / fine_res)
    dst_tr = rasterio.transform.from_origin(left, y + half_m, fine_res, fine_res)
    out = {}
    for key, path, rs in (("fine", FINE, Resampling.bilinear),
                          ("coarse", COARSE, Resampling.nearest)):
        with rasterio.open(path) as src:
            dst = np.full((n, n), np.nan, dtype="float32")
            reproject(rasterio.band(src, 1), dst, dst_transform=dst_tr,
                      dst_crs="EPSG:32618", dst_nodata=np.nan, resampling=rs)
        if key == "fine":
            dst[dst == 0.0] = np.nan  # the lidar reads exactly 0 over water (STATUS §2)
        out[key] = dst
    return out, (left, x + half_m, bottom, y + half_m)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bodies", type=int, nargs="*")
    ap.add_argument("--half-km", type=float, default=0.75)
    ap.add_argument("--centre", type=float, nargs=2, metavar=("LON", "LAT"),
                    help="centre the window here instead of on the body's nearest-ocean cell")
    ap.add_argument("--suffix", default="")
    a = ap.parse_args()
    df = pd.read_csv(CSV)
    if a.bodies:
        df = df[df.body.isin(a.bodies)]
    z25, lab, ocean, iy, ix, tr25 = label_bodies()
    to_ll = Transformer.from_crs("EPSG:32618", "EPSG:4326", always_xy=True)
    OUT.mkdir(parents=True, exist_ok=True)
    for r in df.itertuples():
        cxm, cym = (Transformer.from_crs("EPSG:4326", "EPSG:32618", always_xy=True)
                    .transform(*a.centre) if a.centre else (r.x, r.y))
        arrs, ext = window_arrays(cxm, cym, a.half_km * 1000)
        cy, cx = ~tr25 * (r.x, r.y); cy, cx = int(cy), int(cx)  # noqa: E702 (col,row)
        cx, cy = cy, cx
        oy, ox = iy[cy, cx], ix[cy, cx]
        wx, wy = zip(*(tr25 * (c + 0.5, rr + 0.5) for rr, c in ((cy, cx), (oy, ox))))
        # body cells as a polygon outline on the fine grid
        n = arrs["fine"].shape[0]; fine_res = 2 * a.half_km * 1000 / n
        rows = np.arange(n); ys = ext[3] - (rows + 0.5) * fine_res; xs = ext[0] + (rows + 0.5) * fine_res
        cc = np.clip(((xs - tr25.c) / tr25.a).astype(int), 0, lab.shape[1] - 1)
        rr = np.clip(((ys - tr25.f) / tr25.e).astype(int), 0, lab.shape[0] - 1)
        body = (lab[np.ix_(rr, cc)] == r.body).astype(float)
        norm = TwoSlopeNorm(vmin=-8, vcenter=0, vmax=8)
        fig, axes = plt.subplots(1, 2, figsize=(14, 7), constrained_layout=True)
        for ax, key, title in zip(axes, ("fine", "coarse"),
                                  ("NJ lidar ~3 m (0 = water masked)", "bed_v3_coarse_25m (what the sweep saw)")):
            z = arrs[key]
            im = ax.imshow(z, extent=ext, origin="upper", cmap="RdBu_r", norm=norm)
            ax.contour(np.ma.masked_invalid(z), levels=[WET_Z, 0.0], colors=["k", "m"],
                       linewidths=0.6, extent=ext, origin="upper")
            ax.contour(body, levels=[0.5], colors="lime", linewidths=1.8, extent=ext, origin="upper")
            ax.plot(wx, wy, "-", color="yellow", lw=3, solid_capstyle="round", path_effects=None)
            ax.plot(wx, wy, "o", color="yellow", mec="k", ms=7)
            ax.set_title(title)
            ax.set_aspect("equal")
            # lon/lat ticks for Google Maps
            xt = np.linspace(ext[0], ext[1], 4); yt = np.linspace(ext[2], ext[3], 4)
            lon = [to_ll.transform(v, r.y)[0] for v in xt]
            lat = [to_ll.transform(r.x, v)[1] for v in yt]
            ax.set_xticks(xt); ax.set_xticklabels([f"{v:.4f}" for v in lon])
            ax.set_yticks(yt); ax.set_yticklabels([f"{v:.4f}" for v in lat])
        fig.colorbar(im, ax=axes, shrink=0.8, label="NAVD88 m")
        fig.suptitle(f"body {r.body}: {r.lat:.5f}, {r.lon:.5f}  |  crest {r.crest_m:+.2f} m "
                     f"(max {r.crest_max_m:+.2f}), wall {r.gap_m:.0f} m, area {r.area_km2:.2f} km², "
                     f"basin min {r.body_min_z:.1f} m   [black −1 m, magenta 0 m, green = body cells, yellow = wall segment]")
        p = OUT / f"bed_dam_{r.body}{a.suffix}.png"
        fig.savefig(p, dpi=130); plt.close(fig)
        print(p)


if __name__ == "__main__":
    main()
