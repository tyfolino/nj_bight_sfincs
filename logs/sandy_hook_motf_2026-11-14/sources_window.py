"""Sample every bed source and the 2012 surveys at MOTF pixel centres on Sandy Hook.

    python logs/sandy_hook_motf_2026-11-14/sources_window.py

Window: lon -74.035..-73.955, lat 40.385..40.485 on the MOTF grid. Writes
``sh_window.npz`` (class, bed, h, motf, valid, lon, lat, and one array per source) for
``analyse.py`` / ``figure.py``. Windowed reads, affine sampling (all sources north-up).
"""

from pathlib import Path

import numpy as np

import nj_sfincs  # noqa: F401
import rasterio
from pyproj import Transformer
from rasterio.windows import from_bounds, Window

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
D = REPO / "data"
BOX = (-74.035, 40.385, -73.955, 40.485)

SOURCES = {
    # name: (path(s), nodata test)
    "usace2010": [D / "elevation_v3/usace_nj_2010_topobathy_v3.tif"],
    "cudem": [D / "elevation_v3/cudem_nj_v3.vrt"],
    "nj10ft": [D / "elevation_v3/nj_10ft_dem_v3.tif"],
    "czmil_2012_11_16": [D / "elevation/raw/usace_post_sandy_2012_9012/usace_post_sandy_2012_nj.vrt"],
    "eaarl_pre_2012_10_26": sorted((D / "elevation/raw/usgs_eaarlb_ds767/pre").glob("pre_e58*_n44[789]0_18.tif")),
    "eaarl_post_2012_11": sorted((D / "elevation/raw/usgs_eaarlb_ds767/post").glob("post_e58*_n44[789]0_18.tif")),
}


def sample(paths, lon, lat):
    out = np.full(lon.shape, np.nan, np.float32)
    for p in paths:
        with rasterio.open(p) as r:
            epsg = r.crs.to_epsg()
            tr = Transformer.from_crs(4326, epsg, always_xy=True)
            x, y = tr.transform(lon, lat)
            col, row = ~r.transform * (x, y)
            col = np.floor(col).astype(np.int64)
            row = np.floor(row).astype(np.int64)
            ok = (col >= 0) & (col < r.width) & (row >= 0) & (row < r.height)
            if not ok.any():
                continue
            c0, c1, q0, q1 = col[ok].min(), col[ok].max() + 1, row[ok].min(), row[ok].max() + 1
            a = r.read(1, window=Window(c0, q0, c1 - c0, q1 - q0)).astype(np.float32)
            nd = r.nodata
            v = a[row[ok] - q0, col[ok] - c0]
            bad = ~np.isfinite(v) | (v <= -1000) | (v > 1000)
            if nd is not None:
                bad |= v == np.float32(nd)
            v[bad] = np.nan
            o = out[ok]
            fill = np.isnan(o) & ~np.isnan(v)
            o[fill] = v[fill]
            out[ok] = o
    return out


def main():
    to = Transformer.from_crs(4326, 32618, always_xy=True)
    ti = Transformer.from_crs(32618, 4326, always_xy=True)
    xs, ys = zip(*[to.transform(a, b) for a in BOX[::2] for b in BOX[1::2]])
    res = {}
    import os
    tag = os.environ.get("TAG", "v11")
    for name, f in (("motf", D / "validation_v4/sandy_motf_extent_v4.tif"),
                    ("valid", D / "validation_v4/sandy_motf_valid_nj_v4.tif"),
                    ("cls", HERE / f"motf_class_{tag}.tif"),
                    ("bed", HERE / f"motf_bed_{tag}.tif"),
                    ("h", HERE / f"motf_h_{tag}.tif")):
        with rasterio.open(f) as r:
            w = from_bounds(min(xs), min(ys), max(xs), max(ys), r.transform)
            w = w.round_offsets().round_lengths()
            res[name] = r.read(1, window=w)
            wt = r.window_transform(w)
    h, wd = res["motf"].shape
    X = wt.c + (np.arange(wd) + 0.5) * wt.a
    Y = wt.f + (np.arange(h) + 0.5) * wt.e
    XX, YY = np.meshgrid(X, Y)
    lon, lat = ti.transform(XX, YY)
    res.update(lon=lon, lat=lat, X=XX, Y=YY, transform=np.array(tuple(wt)[:6]))
    for name, paths in SOURCES.items():
        print(name, [p.name for p in paths], flush=True)
        res[name] = sample(paths, lon.ravel(), lat.ravel()).reshape(lon.shape)
    np.savez_compressed(HERE / ("sh_window.npz" if tag == "v11" else f"sh_window_{tag}.npz"), **res)


if __name__ == "__main__":
    main()
