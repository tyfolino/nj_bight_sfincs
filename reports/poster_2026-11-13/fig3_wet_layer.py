"""Fig 3's water layer on Fig 1b's definition: model-wet / dry / open water at the MOTF 15 m cells.

    NJ_DOMAIN=v4_refreeze_swz_v11 python reports/poster_2026-11-13/fig3_wet_layer.py <arm> [<floodmap>]

Fig 1b's class raster (fig3_motf.classify, = metrics.motf_metrics) samples the run's NATIVE 3.125 m floodmap
and subgrid DEM at every MOTF 15 m cell centre and calls a cell

* model wet  : peak depth (above the pixel's own ground) >= DEPTH_MIN (0.15 m),
* open water : not land, i.e. MOTF nodata or subgrid bed <= 0 m (the scorer's ``footprint``),
* in the model: ``validate.simulated_mask`` (the run's own active faces; downscale_floodmap bleeds).

classify() de-rotates both 60k x 80k rasters in memory (~100 GB). This does the SAME sampling block-wise,
straight off the ROTATED rasters through their affine (~T * (x, y) -> col, row; nearest = the pixel that
contains the cell centre), reading only a (non-boundless) window per block of MOTF rows: peak a few GB. It
differs from classify only in skipping the intermediate north-up 3.125 m grid (sub-pixel), so the cell
classes agree almost everywhere; the 2012-ground self-check against Fig 1b's cached class raster measures it.

Unlike Fig 1b it keeps ALL land inside the model (no NJ-only exclusion: the power map shows DE / PA too).
Output (uint8, MOTF grid, codes below): /scratch/tpj8/poster_2026-11-13/fig3/<domain>__<arm>__wet15.tif.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import numpy as np

# GDAL's default block cache (5 % of RAM) took the 2012 run to 30 GB RSS; 512 MB -> 7.4 GB peak.
os.environ.setdefault("GDAL_CACHEMAX", "512")

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
CACHE = Path("/scratch/tpj8/poster_2026-11-13/fig3")
FM_ROOT = Path("/scratch/tpj8/floodmap_fix_2026-11-12")
OUTSIDE, WATER, NOTMODEL, DRY, WET = 0, 1, 2, 3, 4  # NOTMODEL = land outside the run's active faces


def pick_floodmap(dom, arm, run):
    from nj_sfincs.validate import core

    for fm in (FM_ROOT / dom / arm / "floodmap_hmax_native.tif", run / "floodmap_hmax_lev3.tif"):
        if fm.is_file() and core.floodmap_cache_fresh(run, fm):
            return fm
    sys.exit(f"no native, fresh floodmap for {arm}")


def build(dom: str, arm: str, fm: Path | None = None, rows_per_block: int = 384) -> Path:
    import rasterio
    from rasterio.windows import Window

    import nj_sfincs  # noqa: F401  (pyproj before hydromt_sfincs)
    from nj_sfincs import premier
    from nj_sfincs.config import exp_root
    from nj_sfincs.validate import core
    from nj_sfincs.validate.metrics import DATA, DEPTH_MIN, motf_path

    run = exp_root() / arm
    whole, why = premier.output_complete(run)
    if whole is not True:
        sys.exit(f"{run}: output not WHOLE ({whole}: {why})")
    fm = Path(fm) if fm else pick_floodmap(dom, arm, run)
    assert core.floodmap_cache_fresh(run, fm), fm
    dep_p = core.subgrid_dep(run)
    out = CACHE / f"{dom}__{arm}__wet15.tif"
    print(f"[wet15] {arm}\n  floodmap {fm}\n  dep      {dep_p}", flush=True)
    t0 = time.time()

    with rasterio.open(str(motf_path(DATA))) as r:
        motf, mtf, m_nd, prof = r.read(1), r.transform, r.nodata, r.profile
    mh, mw = motf.shape
    sim = core.simulated_mask(run, motf.shape, mtf)
    cls = np.full(motf.shape, OUTSIDE, np.uint8)
    Xc = mtf.c + (np.arange(mw) + 0.5) * mtf.a

    with rasterio.open(str(fm)) as fh, rasterio.open(str(dep_p)) as fd:
        assert fh.transform == fd.transform and fh.shape == fd.shape, "floodmap / dep lattices differ"
        inv = ~fh.transform
        H, W = fh.shape
        for r0 in range(0, mh, rows_per_block):
            r1 = min(r0 + rows_per_block, mh)
            Yc = mtf.f + (np.arange(r0, r1) + 0.5) * mtf.e
            X, Y = np.meshgrid(Xc, Yc)
            cf, rf = inv * (X, Y)
            del X, Y
            ci, ri = np.floor(cf).astype(np.int64), np.floor(rf).astype(np.int64)
            del cf, rf
            ok = (ci >= 0) & (ci < W) & (ri >= 0) & (ri < H)
            blk = cls[r0:r1]
            if not ok.any():
                continue
            c_lo, c_hi = int(ci[ok].min()), int(ci[ok].max()) + 1
            r_lo, r_hi = int(ri[ok].min()), int(ri[ok].max()) + 1
            win = Window(c_lo, r_lo, c_hi - c_lo, r_hi - r_lo)
            hv = fh.read(1, window=win, masked=True).filled(np.nan)
            dv = fd.read(1, window=win, masked=True).filled(np.nan)
            li, lj = (ri - r_lo)[ok], (ci - c_lo)[ok]
            h_at = np.full(ok.shape, np.nan, np.float32)
            d_at = np.full(ok.shape, np.nan, np.float32)
            h_at[ok] = hv[li, lj]
            d_at[ok] = dv[li, lj]
            del hv, dv, li, lj
            m = motf[r0:r1]
            s = sim[r0:r1]
            land = (m != m_nd) & (d_at > 0.0)          # the scorer's footprint
            wet = (h_at >= DEPTH_MIN) & np.isfinite(h_at)
            blk[ok] = WATER
            blk[land & ~s] = NOTMODEL
            blk[land & s] = DRY
            blk[land & s & wet] = WET
            if (r0 // rows_per_block) % 8 == 0:
                print(f"  rows {r0}-{r1} of {mh}  window {win.height}x{win.width}  "
                      f"{time.time() - t0:.0f} s", flush=True)

    out.parent.mkdir(parents=True, exist_ok=True)
    prof.update(dtype="uint8", nodata=None, compress="deflate", tiled=True, count=1,
                blockxsize=256, blockysize=256)
    tmp = out.with_name(f".{out.stem}.partial.{os.getpid()}.tif")
    with rasterio.open(tmp, "w", **prof) as w:
        w.write(cls, 1)
        w.update_tags(arm=arm, domain=dom, floodmap=str(fm), dep=str(dep_p), depth_min=str(DEPTH_MIN),
                      codes="0 outside 1 open water 2 land outside the model 3 dry 4 wet",
                      made_by=Path(__file__).name)
    os.replace(tmp, out)
    km2 = abs(mtf.a * mtf.e) / 1e6
    n = np.bincount(cls.ravel(), minlength=5)
    print(f"[wet15] wrote {out} in {time.time() - t0:.0f} s; km2 wet {n[WET] * km2:.1f} dry {n[DRY] * km2:.1f}"
          f" water {n[WATER] * km2:.1f} not-model {n[NOTMODEL] * km2:.1f}", flush=True)
    return out


def self_check(dom: str, arm: str, wet_tif: Path) -> None:
    """Compare with Fig 1b's cached class raster for the same arm, inside the scored NJ area."""
    import rasterio
    from fig3_motf import CACHE as C1
    from fig3_motf import DRY as D1
    from fig3_motf import FALSE, HIT, MISS

    with rasterio.open(C1 / f"{dom}__{arm}__motf_classes.tif") as r:
        c1 = r.read(1)
        km2 = abs(r.transform.a * r.transform.e) / 1e6
    with rasterio.open(wet_tif) as r:
        c2 = r.read(1)
    scored = np.isin(c1, [D1, HIT, MISS, FALSE])
    w1 = np.isin(c1, [HIT, FALSE])
    w2 = c2 == WET
    a1, a2 = w1.sum() * km2, (w2 & scored).sum() * km2
    both = (w1 & w2).sum() * km2
    only1, only2 = (w1 & ~w2).sum() * km2, (w2 & scored & ~w1).sum() * km2
    agree = ((w1 == w2) | ~scored).sum() / c1.size
    print(f"[self-check] scored NJ area {scored.sum() * km2:.1f} km2: model wet Fig 1b {a1:.1f} km2 "
          f"(hit+false), this layer {a2:.1f} km2 ({100 * (a2 - a1) / a1:+.2f} %); both {both:.1f}, "
          f"Fig1b-only {only1:.1f}, layer-only {only2:.1f}; cell agreement {100 * agree:.3f} %")
    land2 = np.isin(c2, [DRY, WET])
    print(f"[self-check] scored cells the layer calls not-land/not-model: "
          f"{(scored & ~land2).sum() * km2:.2f} km2")


if __name__ == "__main__":
    from nj_sfincs import domain

    dom = domain.active().name
    arm = sys.argv[1]
    t = build(dom, arm, sys.argv[2] if len(sys.argv) > 2 else None)
    if (CACHE / f"{dom}__{arm}__motf_classes.tif").is_file():
        sys.path.insert(0, str(HERE))
        self_check(dom, arm, t)
