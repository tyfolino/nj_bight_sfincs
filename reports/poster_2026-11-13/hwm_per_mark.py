"""Per-mark HWM residuals for Model 1.1.0 on the NATIVE 3.125 m floodmap (low memory).

    NJ_DOMAIN=v4_refreeze_swz_v11 python reports/poster_2026-11-13/hwm_per_mark.py

The 11-12 re-score (``logs/floodmap_fix_2026-11-12/rescore.py``, job 63843110) wrote only
the aggregate row, not per-mark values. ``validate.load_floodmap`` would rebuild them but
de-rotates the whole 4.8 G-pixel map (~130 GiB). This reproduces ``hwm_metrics`` mark by
mark instead: for each mark it de-rotates only the small window it needs, onto the SAME
north-up pixels the full reproject would make (rioxarray's own destination affine,
nearest resampling), then applies ``hwm_metrics``'s rule (median of flooded pixels within
50 m; a dry mark scores at the lowest ground in the window; quality <= 2).

Self-check: the pooled RMSE / bias / n must match the re-score row. Writes
``hwm_per_mark_v110_native.csv`` beside this script. Read-only everywhere else.
"""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import rioxarray
from rasterio.warp import Resampling, reproject
from rasterio.windows import Window
from rioxarray._spatial_utils import _make_dst_affine

import nj_sfincs  # noqa: F401  (pyproj first)
from nj_sfincs import domain
from nj_sfincs.config import DATA, exp_root
from nj_sfincs.validate.core import DEPTH_MIN, subgrid_dep
from nj_sfincs.validate.metrics import _clip_to_region, _hwm_path

HERE = Path(__file__).resolve().parent
ARM = "p4-premier+weir-elizabeth-rahway"
FM = Path(
    "/scratch/tpj8/floodmap_fix_2026-11-12/v4_refreeze_swz_v11/"
    f"{ARM}/floodmap_hmax_native.tif"
)
ROW = Path(
    "logs/floodmap_fix_2026-11-12/rows/"
    f"v4_refreeze_swz_v11__{ARM}.csv"
)
RADIUS = 50.0
GROUND_CAP = 0.5


def dst_grid(fn):
    lazy = rioxarray.open_rasterio(
        str(fn), masked=True, cache=False, parse_coordinates=False
    ).squeeze(drop=True)
    aff, w, h = _make_dst_affine(
        src_data_array=lazy, src_crs=lazy.rio.crs, dst_crs=lazy.rio.crs
    )
    return aff, int(w), int(h)


def warp_window(src, dst_aff, r0, r1, c0, c1):
    """Nearest-warp the rotated ``src`` onto dst rows r0:r1, cols c0:c1 (north-up)."""
    win_aff = dst_aff * dst_aff.translation(c0, r0)
    nr, nc = r1 - r0, c1 - c0
    # source pixel bbox covering the destination window, padded
    corners = [win_aff * (x, y) for x in (0, nc) for y in (0, nr)]
    inv = ~src.transform
    cr = [inv * xy for xy in corners]
    cs = [p[0] for p in cr]
    rs = [p[1] for p in cr]
    sc0 = max(0, int(np.floor(min(cs))) - 4)
    sc1 = min(src.width, int(np.ceil(max(cs))) + 4)
    sr0 = max(0, int(np.floor(min(rs))) - 4)
    sr1 = min(src.height, int(np.ceil(max(rs))) + 4)
    win = Window(sc0, sr0, sc1 - sc0, sr1 - sr0)
    data = src.read(1, window=win, masked=True).astype("float32").filled(np.nan)
    out = np.full((nr, nc), np.nan, dtype="float32")
    reproject(
        source=data,
        destination=out,
        src_transform=src.window_transform(win),
        src_crs=src.crs,
        src_nodata=np.nan,
        dst_transform=win_aff,
        dst_crs=src.crs,
        dst_nodata=np.nan,
        resampling=Resampling.nearest,
    )
    return out


def main():
    dom = domain.active()
    run = exp_root() / ARM
    dep_p = subgrid_dep(run)
    aff, W, H = dst_grid(FM)
    print("north-up grid", W, H, aff)
    hwm = gpd.read_file(str(_hwm_path(DATA))).to_crs(f"EPSG:{dom.epsg}")
    hwm = _clip_to_region(hwm)
    ll = hwm.to_crs("EPSG:4326")
    basin = np.asarray(domain.classify_hwm_basin(hwm.geometry.x.values, hwm.geometry.y.values))
    rad = int(round(RADIUS / abs(aff.a)))
    obs = hwm["elev_m"].values
    qual = hwm["quality"].values.astype(float)
    mod_wse = np.full(len(obs), np.nan)
    mod_ground = np.full(len(obs), np.nan)
    with rasterio.open(FM) as sh, rasterio.open(dep_p) as sd:
        for k, (X, Y) in enumerate(zip(hwm.geometry.x.values, hwm.geometry.y.values)):
            col, row = int((X - aff.c) / aff.a), int((Y - aff.f) / aff.e)
            if not (0 <= row < H and 0 <= col < W):
                continue
            r0, c0 = max(0, row - rad), max(0, col - rad)
            r1, c1 = min(H, row + rad + 1), min(W, col + rad + 1)
            hh = warp_window(sh, aff, r0, r1, c0, c1)
            dd = warp_window(sd, aff, r0, r1, c0, c1)
            hh = np.where(dd > -0.5, hh, np.nan)  # load_floodmap: drop deep ocean
            ws = dd + hh
            if np.isfinite(dd).any():
                mod_ground[k] = np.nanmin(dd)
            flooded = (hh >= DEPTH_MIN) & (dd <= obs[k] + GROUND_CAP)
            if flooded.any():
                mod_wse[k] = np.nanmedian(ws[flooded])
    wet = np.isfinite(mod_wse)
    mod_scored = np.where(wet, mod_wse, mod_ground)
    scored = np.isfinite(mod_scored) & (qual <= 2)
    df = pd.DataFrame(
        dict(
            hwm_id=hwm["hwm_id"].astype(str).values,
            lon=ll.geometry.x.values,
            lat=ll.geometry.y.values,
            basin=basin,
            quality=qual,
            obs_m=obs,
            model_m=mod_scored,
            wet=wet,
            scored=scored,
            resid_m=mod_scored - obs,
        )
    )
    out = HERE / "hwm_per_mark_v110_native.csv"
    df.to_csv(out, index=False)
    rs = df.loc[df.scored, "resid_m"].values
    mine = dict(
        n=len(rs),
        rmse=float(np.sqrt((rs**2).mean())),
        bias=float(rs.mean()),
        within05=float(np.mean(np.abs(rs) < 0.5)),
        n_dry=int((df.scored & ~df.wet).sum()),
    )
    ref = pd.read_csv(ROW).iloc[0]
    print("mine     ", mine)
    print(
        "re-score  n", ref.hwm_n_scored, "rmse", ref.hwm_rmse_scored_m,
        "bias", ref.hwm_bias_scored_m, "within0.5", ref["hwm_within0.5_scored"],
        "floodmap", ref.floodmap,
    )
    print("wrote", out)


if __name__ == "__main__":
    main()
