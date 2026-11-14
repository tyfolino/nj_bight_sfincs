"""Re-create the published MOTF scorer's per-pixel classes, block by block (low RAM).

    NJ_DOMAIN=v4_refreeze_swz_v11 python logs/sandy_hook_motf_2026-11-14/classify_motf.py

Reproduces ``validate.metrics.motf_metrics`` on the native floodmap WITHOUT building the
two ~20 GB de-rotated grids: for each MOTF pixel centre it finds the de-rotated (north-up)
pixel the scorer's index arithmetic picks, then the ROTATED source pixel GDAL's nearest
warp puts there (floor of ~affine at the de-rotated centre). Affine throughout; windowed,
non-boundless reads clipped to the raster.

Writes ``motf_class_v11.tif`` on the MOTF grid (uint8):
  0 not scored, 1 hit, 2 miss, 3 false alarm, 4 correct-dry,
  5 excluded (validity raster / boxes), 6 unsimulated footprint
plus the bed (dep_at, float32, NaN off) ``motf_bed_v11.tif`` and hmax ``motf_h_v11.tif``.
Read-only on the repo / run dir.
"""

import sys
from pathlib import Path

import numpy as np

import nj_sfincs  # noqa: F401  (pyproj before hydromt)
import rasterio
import rioxarray
from rasterio.windows import Window
from rioxarray._spatial_utils import _make_dst_affine

from nj_sfincs.validate.core import DEPTH_MIN, simulated_mask
from nj_sfincs.validate.metrics import motf_exclude_mask, motf_invalid_mask

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
import os  # noqa: E402

# defaults = 1.1.0; RUN / FM env vars point it at another arm on the same mesh + mask
RUN = Path(os.environ.get(
    "RUN", REPO / "experiments/v4_refreeze_swz_v11/p4-premier+weir-elizabeth-rahway"))
FM = Path(os.environ.get(
    "FM",
    "/scratch/tpj8/floodmap_fix_2026-11-12/v4_refreeze_swz_v11/"
    "p4-premier+weir-elizabeth-rahway/floodmap_hmax_native.tif",
))
DEP = RUN / "subgrid" / "dep_subgrid_merged.tif"
MOTF = REPO / "data/validation_v4/sandy_motf_extent_v4.tif"
TAG = sys.argv[1] if len(sys.argv) > 1 else "v11"


def main():
    with rasterio.open(MOTF) as r:
        motf, mtf, m_nd, prof = r.read(1), r.transform, r.nodata, r.profile
    mh, mw = motf.shape
    print("motf", motf.shape, flush=True)
    simf = HERE / "sim_mask_v11.npy"  # msk on the MOTF grid (same mesh+msk: checked for 2026 bed)
    if simf.is_file():
        sim = np.load(simf)
    else:
        sim = simulated_mask(RUN, motf.shape, mtf)
        np.save(simf, sim)
    print("sim done", int(sim.sum()), flush=True)
    excl = motf_exclude_mask(motf.shape, mtf)
    invalid = motf_invalid_mask(motf.shape, mtf)
    assert excl is not None

    # the de-rotated grid _open_north_up builds (rio.reproject(src.rio.crs))
    src = rioxarray.open_rasterio(str(FM), masked=True, cache=False,
                                  parse_coordinates=False).squeeze(drop=True)
    D, dw, dh = _make_dst_affine(
        src_data_array=src, src_crs=src.rio.crs, dst_crs=src.rio.crs
    )
    del src
    print("de-rotated grid", dw, dh, D, flush=True)

    fh = rasterio.open(FM)
    fd = rasterio.open(DEP)
    R = fh.transform
    assert fd.transform == R and fd.shape == fh.shape
    Rinv = ~R
    H, W = fh.shape

    Xc = mtf.c + (np.arange(mw) + 0.5) * mtf.a
    cls = np.zeros(motf.shape, np.uint8)
    bed = np.full(motf.shape, np.nan, np.float32)
    hh = np.full(motf.shape, np.nan, np.float32)
    B = 256
    for r0 in range(0, mh, B):
        r1 = min(mh, r0 + B)
        Yc = mtf.f + (np.arange(r0, r1) + 0.5) * mtf.e
        cand = (motf[r0:r1] != m_nd) & sim[r0:r1]
        if not cand.any():
            continue
        rows, cols = np.nonzero(cand)
        X = Xc[cols]
        Y = Yc[rows]
        dc = np.clip(((X - D.c) / D.a).astype(int), 0, dw - 1)
        dr = np.clip(((Y - D.f) / D.e).astype(int), 0, dh - 1)
        xd = D.c + (dc + 0.5) * D.a
        yd = D.f + (dr + 0.5) * D.e
        sc, sr = Rinv * (xd, yd)
        sc = np.floor(sc).astype(np.int64)
        sr = np.floor(sr).astype(np.int64)
        ok = (sc >= 0) & (sc < W) & (sr >= 0) & (sr < H)
        hv = np.full(sc.shape, np.nan, np.float32)
        dv = np.full(sc.shape, np.nan, np.float32)
        if ok.any():
            c0, c1 = sc[ok].min(), sc[ok].max() + 1
            q0, q1 = sr[ok].min(), sr[ok].max() + 1
            win = Window(c0, q0, c1 - c0, q1 - q0)
            ha = fh.read(1, window=win, masked=True).filled(np.nan)
            da = fd.read(1, window=win, masked=True).filled(np.nan)
            hv[ok] = ha[sr[ok] - q0, sc[ok] - c0]
            dv[ok] = da[sr[ok] - q0, sc[ok] - c0]
            del ha, da
        hv = np.where(dv > -0.5, hv, np.nan)
        b = np.full(cand.shape, np.nan, np.float32)
        h2 = np.full(cand.shape, np.nan, np.float32)
        b[rows, cols] = dv
        h2[rows, cols] = hv
        bed[r0:r1] = b
        hh[r0:r1] = h2
        print(f"rows {r0}-{r1} n={rows.size}", flush=True)

    footprint = (motf != m_nd) & (bed > 0.0)
    land_in = footprint & sim
    motf_wet = motf == 1
    mod_wet = (hh >= DEPTH_MIN) & np.isfinite(hh)
    cls[footprint & ~sim] = 6
    cls[land_in & excl] = 5
    li = land_in & ~excl
    cls[li & motf_wet & mod_wet] = 1
    cls[li & motf_wet & ~mod_wet] = 2
    cls[li & ~motf_wet & mod_wet] = 3
    cls[li & ~motf_wet & ~mod_wet] = 4
    km2 = abs(mtf.a * mtf.e) / 1e6
    nh, nm, nf = [int((cls == k).sum()) for k in (1, 2, 3)]
    print(f"hits {nh*km2:.4f} miss {nm*km2:.4f} FA {nf*km2:.4f} km2")
    print(f"CSI {nh/(nh+nm+nf):.6f} POD {nh/(nh+nm):.6f} FAR {nf/(nh+nf):.6f}")
    print(f"excluded {int((cls==5).sum())*km2:.4f} unsim {int((cls==6).sum())*km2:.4f}")
    p = prof.copy()
    p.update(compress="deflate", tiled=True, blockxsize=256, blockysize=256,
             nodata=None, dtype="uint8", BIGTIFF="IF_SAFER")
    with rasterio.open(HERE / f"motf_class_{TAG}.tif", "w", **p) as o:
        o.write(cls, 1)
    p.update(dtype="float32", nodata=np.nan, predictor=3)
    for name, a in (("bed", bed), ("h", hh)):
        with rasterio.open(HERE / f"motf_{name}_{TAG}.tif", "w", **p) as o:
            o.write(a, 1)


if __name__ == "__main__":
    main()
