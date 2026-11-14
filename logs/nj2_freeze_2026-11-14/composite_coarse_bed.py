#!/usr/bin/env python
"""nj2's coarse bed = v4's coarse bed WHEREVER v4 HAS A PIXEL, the nj2 warp only elsewhere.

    python logs/nj2_freeze_2026-11-14/composite_coarse_bed.py <nj2_warp.tif> <v4.tif> <out.tif>

Why (user 2026-11-14): the coarse bed gates the refinement (each polygon's zmin / zmax) and sets
face z, so nj2's faces on the old ground can only equal v4's if its coarse bed does. J1's warp
(`build_coarse_bed.py`, NJ_DOMAIN=nj2, same 16 tiers, same lattice) differed from v4's on
292,857 px by > 1 mm (max 4.61 m, 7 px > 0.3 m): `gdalwarp` output is not independent of the
output EXTENT — the same tier warped today on v4's and on nj2's box differs on 78,687 px (max
1.3 cm), with or without the approximate transformer (-et 0 identical), i.e. the per-chunk
resampling (the chunking follows the extent); steep pixels (jetties, channel walls) and the MIN
carving tiers turn that into decimetres-metres. Not chased further.

Writes on the UNION of the two boxes (both are whole-km 25 m windows of one lattice: asserted),
tiled DEFLATE, NoData -99999, 50 / 100 / 200 m `average` overviews like the builder, atomically,
plus ``<out>.composite.txt`` (inputs' md5, pixel sources). Checks: composite == v4 on every v4
pixel (exact), overviews == v4's on the shared blocks, no NoData inside the active domain's ring.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin
from rasterio.windows import Window

import nj_sfincs  # noqa: F401
from nj_sfincs import domain as D

NODATA = -99999.0


def _md5(p: Path) -> str:
    h = hashlib.md5()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 24), b""):
            h.update(b)
    return h.hexdigest()


def _win(src, x0, y1):
    """The integer window of ``src`` whose top-left corner is (x0, y1)."""
    c = (src.transform.c - x0) / 25.0
    r = (y1 - src.transform.f) / 25.0
    assert c == int(c) and r == int(r), (c, r)
    return int(r), int(c)


def main(warp: str, v4: str, out: str) -> int:
    warp_p, v4_p, out_p = Path(warp), Path(v4), Path(out)
    with rasterio.open(warp_p) as w, rasterio.open(v4_p) as o:
        for s in (w, o):
            assert s.res == (25.0, 25.0), s.res
            assert s.transform.c % 1000 == 0 and s.transform.f % 1000 == 0
            assert s.crs.to_epsg() == 32618
        x0 = min(w.bounds.left, o.bounds.left)
        x1 = max(w.bounds.right, o.bounds.right)
        y0 = min(w.bounds.bottom, o.bounds.bottom)
        y1 = max(w.bounds.top, o.bounds.top)
        W, H = int((x1 - x0) / 25), int((y1 - y0) / 25)
        a = np.full((H, W), NODATA, dtype="float32")
        rw, cw = _win(w, x0, y1)
        aw = w.read(1)
        a[rw : rw + w.height, cw : cw + w.width] = np.where(aw != w.nodata, aw, NODATA)
        ro, co = _win(o, x0, y1)
        ao = o.read(1)
        sub = a[ro : ro + o.height, co : co + o.width]
        v4ok = ao != o.nodata
        n_v4 = int(v4ok.sum())
        sub[v4ok] = ao[v4ok]
        n_warp = int((a != NODATA).sum()) - n_v4
        prof = o.profile.copy()
    prof.update(
        width=W,
        height=H,
        transform=from_origin(x0, y1, 25.0, 25.0),
        nodata=NODATA,
        dtype="float32",
        compress="DEFLATE",
        tiled=True,
        blockxsize=256,
        blockysize=256,
    )
    tmp = out_p.with_name(f".{out_p.name}.tmp.tif")
    with rasterio.open(tmp, "w", **prof) as d:
        d.write(a, 1)
    subprocess.run(
        ["gdaladdo", "-q", "-r", "average", str(tmp), "2", "4", "8"], check=True
    )

    # ── checks (on the written file) ─────────────────────────────────────────────
    with rasterio.open(tmp) as d, rasterio.open(v4_p) as o:
        r0, c0 = _win(o, x0, y1)
        b = d.read(1, window=Window(c0, r0, o.width, o.height))
        ao = o.read(1)
        ok = ao != o.nodata
        assert np.array_equal(b[ok], ao[ok]), "composite != v4 on a v4 pixel"
        for f in (2, 4, 8):  # the overviews (hydromt may read them), block-aligned
            assert r0 % f == 0 and c0 % f == 0, "overview blocks not aligned"
            hd, wd = d.height // f, d.width // f
            ho, wo = o.height // f, o.width // f
            sd = d.read(1, out_shape=(hd, wd))[
                r0 // f : r0 // f + ho, c0 // f : c0 // f + wo
            ]
            so = o.read(1, out_shape=(ho, wo))
            m = so != o.nodata
            dd = float(np.abs(sd[m] - so[m]).max()) if m.any() else 0.0
            print(f"  overview /{f}: max |composite - v4| {dd:.6f} m")
            assert dd == 0.0, f"overview /{f} differs from v4's"
        dom = D.active()
        import geopandas as gpd
        from rasterio.features import geometry_mask

        ring = gpd.read_file(dom.region).to_crs(32618).geometry.iloc[0]
        a2 = d.read(1)
        inside = ~geometry_mask([ring], a2.shape, d.transform)
        hole = int((inside & (a2 == NODATA)).sum())
        assert hole == 0, f"{hole} ring px with NoData"
    os.replace(tmp, out_p)
    side = out_p.with_name(out_p.name + ".composite.txt")
    side.write_text(
        f"composite {out_p.name}: {W} x {H} px, origin {x0:.0f},{y1:.0f}, 25 m\n"
        f"  v4   {v4_p} md5 {_md5(v4_p)}: {n_v4:,} px (every v4 pixel, exact)\n"
        f"  warp {warp_p} md5 {_md5(warp_p)}: {n_warp:,} px (only where v4 has none)\n"
        f"  out md5 {_md5(out_p)}; ring ({dom.name}) NoData px 0\n"
    )
    print(side.read_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:]))
