"""Merge the per-level subgrid DEMs into one raster that covers EVERY active face.

WHY THIS EXISTS (STATUS 2026-08-29). hydromt writes ``subgrid/dep_subgrid_lev<L>.tif``
only under faces refined to level L, and the floodmap/HWM pipeline downscales onto the
FINEST level's raster alone. On v1.5 that was harmless — every scored mark sat over a
lev3 face (measured: 0 of 69 uncovered). On v3 the finest level is the surf band plus
the low-water pockets, 10% of the grid rectangle, and 51 of 140 in-region HWMs — all on
active, simulated faces — were silently classed "not on this model's grid". The MOTF
extent shared the exposure: a wet coarse face was never painted, so it scored model-dry.

The fix is one raster: lev3 where lev3 has data, else lev2, else lev1, else lev0, all
on the lev3 pixel grid. The four levels share one rotated lattice (pixel ratios exact
powers of two, origins offset by whole lev3 pixels — asserted below), so the fill is an
exact nearest-neighbour upsample, not an interpolation: every output pixel carries a
value hydromt itself computed for the face that covers it.

Run per subgrid dir (the template; hard-link the result into the arms so one inode
serves all four):

    NJ_DOMAIN=v3 python scripts/build_merged_subgrid_dep.py \
        --subgrid-dir experiments/v3/_template_sealed/subgrid

``validate.load_floodmap`` prefers ``dep_subgrid_merged.tif`` when it exists and falls
back to ``dep_subgrid_lev3.tif`` when it does not — so v1.5, where lev3 covers every
mark, keeps scoring bit-for-bit without a rebuild.
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window

BLOCK = 2048
LEVELS = (3, 2, 1, 0)  # finest first; 3 is the base, the rest fill


def _check_aligned(base, src, lev: int) -> None:
    """The fill below is exact ONLY if the grids nest. Abort loudly if they do not."""
    ratio = 2 ** (3 - lev)
    for k in ("a", "b", "d", "e"):
        got = getattr(src.transform, k)
        want = getattr(base.transform, k) * ratio
        if not math.isclose(got, want, rel_tol=1e-6, abs_tol=1e-6):
            sys.exit(
                f"lev{lev} transform.{k}={got} is not lev3.{k}*{ratio} — "
                "grids do not nest, refusing to merge"
            )
    if src.crs != base.crs:
        sys.exit(f"lev{lev} CRS {src.crs} != lev3 CRS {base.crs}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--subgrid-dir", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=None,
                    help="default: <subgrid-dir>/dep_subgrid_merged.tif")
    ap.add_argument("--force", action="store_true",
                    help="overwrite an existing merged raster")
    args = ap.parse_args()

    sg = args.subgrid_dir
    out = args.out or sg / "dep_subgrid_merged.tif"
    if out.exists() and not args.force:
        sys.exit(f"{out} exists — pass --force to rebuild it")

    srcs = {}
    for lev in LEVELS:
        p = sg / f"dep_subgrid_lev{lev}.tif"
        if not p.is_file():
            sys.exit(f"missing {p}")
        srcs[lev] = rasterio.open(p)
    base = srcs[3]
    for lev in (2, 1, 0):
        _check_aligned(base, srcs[lev], lev)

    prof = base.profile.copy()
    prof.update(
        compress="deflate", predictor=3, tiled=True,
        blockxsize=512, blockysize=512, bigtiff="IF_SAFER", nodata=np.nan,
    )
    inv = {lev: ~srcs[lev].transform for lev in (2, 1, 0)}
    T = base.transform
    ny, nx = base.height, base.width
    filled = {lev: 0 for lev in (2, 1, 0)}
    t0 = time.time()

    # Atomic-ish: write to a sibling and rename, so a killed build never leaves a
    # plausible-looking stub that load_floodmap would trust (the truncated-cache lesson).
    tmp = out.with_name(f".{out.name}.partial.tif")
    with rasterio.open(tmp, "w", **prof) as dst:
        for r0 in range(0, ny, BLOCK):
            for c0 in range(0, nx, BLOCK):
                h, w = min(BLOCK, ny - r0), min(BLOCK, nx - c0)
                win = Window(c0, r0, w, h)
                a = base.read(1, window=win)
                nan = ~np.isfinite(a)
                if nan.any():
                    rr, cc = np.nonzero(nan)
                    # pixel-CENTRE map coords of the holes, via the base affine
                    col, row = cc + c0 + 0.5, rr + r0 + 0.5
                    X = T.c + T.a * col + T.b * row
                    Y = T.f + T.d * col + T.e * row
                    for lev in (2, 1, 0):
                        need = ~np.isfinite(a[rr, cc])
                        if not need.any():
                            break
                        fc = inv[lev].a * X + inv[lev].b * Y + inv[lev].c
                        fr = inv[lev].d * X + inv[lev].e * Y + inv[lev].f
                        sc, sr = np.floor(fc).astype(int), np.floor(fr).astype(int)
                        ok = need & (sr >= 0) & (sr < srcs[lev].height) \
                            & (sc >= 0) & (sc < srcs[lev].width)
                        if not ok.any():
                            continue
                        swin = Window(
                            sc[ok].min(), sr[ok].min(),
                            sc[ok].max() - sc[ok].min() + 1,
                            sr[ok].max() - sr[ok].min() + 1,
                        )
                        s = srcs[lev].read(1, window=swin)
                        v = s[sr[ok] - sr[ok].min(), sc[ok] - sc[ok].min()]
                        good = np.isfinite(v)
                        idx = np.nonzero(ok)[0][good]
                        a[rr[idx], cc[idx]] = v[good]
                        filled[lev] += int(good.sum())
                dst.write(a, 1, window=win)
            print(f"  row {r0 + h}/{ny}  filled lev2/1/0 = "
                  f"{filled[2]:,}/{filled[1]:,}/{filled[0]:,}  "
                  f"{time.time() - t0:.0f}s", flush=True)
    tmp.replace(out)

    # The downscale pipeline opens the dep by OVERVIEW level ("Cannot open overview
    # level 0" without them), so overviews are part of the product, not a nicety.
    # Same ladder as hydromt puts on the per-level tifs.
    from rasterio.enums import Resampling

    with rasterio.Env(COMPRESS_OVERVIEW="DEFLATE", PREDICTOR_OVERVIEW="3"):
        with rasterio.open(out, "r+") as r:
            r.build_overviews((2, 4, 8, 16, 32, 64, 128, 254), Resampling.average)
    print(f"overviews built ({time.time() - t0:.0f}s)")

    with rasterio.open(out) as r:
        a = r.read(1, out_shape=(r.height // 16, r.width // 16))
    print(f"wrote {out} ({out.stat().st_size / 1e9:.2f} GB); "
          f"finite fraction at 16x: {np.isfinite(a).mean():.3f}")
    for s in srcs.values():
        s.close()


if __name__ == "__main__":
    main()
