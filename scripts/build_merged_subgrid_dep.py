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

``--base-level 2`` (v4, 2026-09-29): write the merged raster on the lev2 lattice instead,
each pixel the MEAN of the 2x2 lev3 pixels it covers (then lev2, lev1, lev0 as above).
v4's 16 px subgrid puts lev3 at 1.56 m — 119,824 x 160,656 px, 77 GB as float32 — and
the scorer holds and de-rotates the whole raster (v3: MaxRSS ~10x the raster), so its
validate was OOM-killed at 400 G. The scores cannot see 1.56 m (MOTF is a 15 m sheet, an
HWM is a 50 m-radius median), and 3.125 m is the pixel v3 is scored on. The SOLVER's
per-face tables are untouched; only the scoring map is coarser. Where a 2x2 block is
partly NaN (lev3 coverage edge) the mean is over its finite pixels, counted and printed.
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


def _check_aligned(base, src, lev: int, base_level: int = 3) -> None:
    """The fill below is exact ONLY if the grids nest. Abort loudly if they do not."""
    ratio = 2.0 ** (base_level - lev)
    for k in ("a", "b", "d", "e"):
        got = getattr(src.transform, k)
        want = getattr(base.transform, k) * ratio
        if not math.isclose(got, want, rel_tol=1e-6, abs_tol=1e-6):
            sys.exit(
                f"lev{lev} transform.{k}={got} is not lev{base_level}.{k}*{ratio} — "
                "grids do not nest, refusing to merge"
            )
    if src.crs != base.crs:
        sys.exit(f"lev{lev} CRS {src.crs} != lev{base_level} CRS {base.crs}")


def _finer_offset(base, fine, k: int) -> tuple[int, int]:
    """(row, col) of the base raster's origin in ``fine`` pixels — must be whole, or a
    base pixel does not cover exactly k x k fine pixels and the mean is not exact."""
    inv, x, y = ~fine.transform, base.transform.c, base.transform.f
    col, row = inv.a * x + inv.b * y + inv.c, inv.d * x + inv.e * y + inv.f
    rc, cc = round(row), round(col)
    if not (math.isclose(row, rc, abs_tol=1e-3) and math.isclose(col, cc, abs_tol=1e-3)):
        sys.exit(f"base origin at fine pixel ({row}, {col}) is not whole — refusing")
    return rc, cc


def _block_mean(fine, win: Window, k: int, off: tuple[int, int]):
    """Mean of each k x k block of ``fine`` under the base-pixel window ``win``.

    Returns (mean, n_partial): NaN where the whole block is NaN, the mean of the finite
    pixels where only some are (counted — they sit on the fine level's coverage edge).
    """
    h, w = int(win.height), int(win.width)
    fwin = Window(
        int(win.col_off) * k + off[1], int(win.row_off) * k + off[0], w * k, h * k
    )
    a = fine.read(1, window=fwin, boundless=True, fill_value=np.nan)
    a = a.reshape(h, k, w, k)
    n = np.isfinite(a).sum(axis=(1, 3))
    with np.errstate(invalid="ignore"):
        mean = np.nansum(a, axis=(1, 3)) / n
    mean[n == 0] = np.nan
    return mean.astype(np.float32), int(((n > 0) & (n < k * k)).sum())


def build_merged(
    sg: Path, out: Path | None = None, force: bool = False, base_level: int = 3
) -> Path:
    """Write ``<sg>/dep_subgrid_merged.tif`` (or ``out``) from ``dep_subgrid_lev*.tif``.

    ``base_level`` — the lattice the output is written on (3 = the finest, as before).
    Levels finer than it are block-MEANED onto it; coarser ones fill by nearest.

    Called by ``scripts/rebuild_subgrid.py`` on every rebuilt subgrid dir, so a
    ``bed-*`` arm can never be staged without the merged raster again (STATUS
    2026-09-08: one was, scored on the lev3-only bed, and every guard passed).
    """
    sg = Path(sg)
    out = Path(out) if out else sg / "dep_subgrid_merged.tif"
    if out.exists() and not force:
        sys.exit(f"{out} exists — pass --force to rebuild it")

    srcs = {}
    for lev in LEVELS:
        p = sg / f"dep_subgrid_lev{lev}.tif"
        if not p.is_file():
            sys.exit(f"missing {p}")
        srcs[lev] = rasterio.open(p)
    if base_level not in LEVELS:
        sys.exit(f"base level {base_level} not in {LEVELS}")
    base = srcs[base_level]
    finer = [lev for lev in LEVELS if lev > base_level]  # finest first
    coarser = [lev for lev in LEVELS if lev < base_level]
    for lev in finer + coarser:
        _check_aligned(base, srcs[lev], lev, base_level)
    fine_off = {
        lev: _finer_offset(base, srcs[lev], 2 ** (lev - base_level)) for lev in finer
    }
    partial = {lev: 0 for lev in finer}

    prof = base.profile.copy()
    prof.update(
        compress="deflate", predictor=3, tiled=True,
        blockxsize=512, blockysize=512, bigtiff="IF_SAFER", nodata=np.nan,
    )
    inv = {lev: ~srcs[lev].transform for lev in coarser}
    T = base.transform
    ny, nx = base.height, base.width
    filled = {lev: 0 for lev in LEVELS if lev != base_level}
    t0 = time.time()

    # Atomic-ish: write to a sibling and rename, so a killed build never leaves a
    # plausible-looking stub that load_floodmap would trust (the truncated-cache lesson).
    tmp = out.with_name(f".{out.name}.partial.tif")
    with rasterio.open(tmp, "w", **prof) as dst:
        for r0 in range(0, ny, BLOCK):
            for c0 in range(0, nx, BLOCK):
                h, w = min(BLOCK, ny - r0), min(BLOCK, nx - c0)
                win = Window(c0, r0, w, h)
                a = None
                for lev in finer:  # finest data first, meaned onto the base lattice
                    k = 2 ** (lev - base_level)
                    m, npart = _block_mean(srcs[lev], win, k, fine_off[lev])
                    partial[lev] += npart
                    if a is None:
                        a = m
                    else:
                        take = ~np.isfinite(a) & np.isfinite(m)
                        a[take] = m[take]
                    filled[lev] += int(np.isfinite(m).sum())
                b = base.read(1, window=win)
                if a is None:
                    a = b
                else:
                    take = ~np.isfinite(a) & np.isfinite(b)
                    a[take] = b[take]
                nan = ~np.isfinite(a)
                if nan.any():
                    rr, cc = np.nonzero(nan)
                    # pixel-CENTRE map coords of the holes, via the base affine
                    col, row = cc + c0 + 0.5, rr + r0 + 0.5
                    X = T.c + T.a * col + T.b * row
                    Y = T.f + T.d * col + T.e * row
                    for lev in coarser:
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
            got = "/".join(f"{filled[lev]:,}" for lev in sorted(filled, reverse=True))
            print(f"  row {r0 + h}/{ny}  base lev{base_level}; filled lev"
                  f"{'/'.join(str(v) for v in sorted(filled, reverse=True))} = {got}"
                  + (f"; partial fine blocks {partial}" if finer else "")
                  + f"  {time.time() - t0:.0f}s", flush=True)
    tmp.replace(out)

    # The downscale pipeline opens the dep by OVERVIEW level ("Cannot open overview
    # level 0" without them), so overviews are part of the product, not a nicety.
    # Same ladder as hydromt puts on the per-level tifs.
    from rasterio.enums import Resampling

    with rasterio.Env(COMPRESS_OVERVIEW="DEFLATE", PREDICTOR_OVERVIEW="3"):
        with rasterio.open(out, "r+") as r:
            ladder = (2, 4, 8, 16, 32, 64, 128, 254)
            ladder = [f for f in ladder if max(r.width, r.height) // f >= 2]
            r.build_overviews(ladder, Resampling.average)
    print(f"overviews built ({time.time() - t0:.0f}s)")

    with rasterio.open(out) as r:
        a = r.read(1, out_shape=(r.height // 16, r.width // 16))
    print(f"wrote {out} ({out.stat().st_size / 1e9:.2f} GB); "
          f"finite fraction at 16x: {np.isfinite(a).mean():.3f}")
    for s in srcs.values():
        s.close()
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--subgrid-dir", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=None,
                    help="default: <subgrid-dir>/dep_subgrid_merged.tif")
    ap.add_argument("--force", action="store_true",
                    help="overwrite an existing merged raster")
    ap.add_argument("--base-level", type=int, default=3, choices=LEVELS,
                    help="lattice of the output (default 3, the finest); v4 uses 2 — "
                    "lev3 block-meaned 2x2 onto 3.125 m")
    args = ap.parse_args()
    build_merged(args.subgrid_dir, args.out, args.force, args.base_level)


if __name__ == "__main__":
    main()
