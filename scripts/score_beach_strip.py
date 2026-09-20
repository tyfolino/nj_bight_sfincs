#!/usr/bin/env python
"""MOTF extent scored by DISTANCE FROM THE WAVEMAKER LINE — where infragravity acts.

Why (STATUS 2026-09-20): the wavemaker arm lifts the peak level by ~1 m on the beach face
and dune (0–400 m landward of the −5 m line) and by ~0 behind the dune, so the whole-domain
CSI / POD / FAR cannot see it. This partitions the SAME comparison ``motf_metrics`` makes
(same raster, ``DEPTH_MIN``, footprint, ``simulated_mask``, exclude boxes) into bands of
nearest-vertex distance from the line, on the ocean coast only, and reports per band per arm.
The bands plus the remainder must reproduce the ``metrics.csv`` row — that is the self-check.

    NJ_DOMAIN=v3 PYTHONPATH=$PWD python scripts/score_beach_strip.py naccs-premier wave-wavemaker
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import rasterio
from scipy.spatial import cKDTree

from nj_sfincs import domain as _domain
from nj_sfincs.config import exp_root
from nj_sfincs.validate.core import simulated_mask
from nj_sfincs.validate.metrics import DATA, DEPTH_MIN, motf_exclude_mask, motf_path

BANDS = [(0, 400), (400, 800), (800, 1500), (1500, 3000), (3000, 6000), (6000, 1e9)]
COAST_MAX_Y = 4_481_000.0  # north of this the line does not exist (Raritan / Lower Bay)
BAY_BOX = (4_467_000.0, 584_500.0)  # y > .. & x < .. = the bay system, excluded


def _line_points(path: Path, step: float = 20.0) -> np.ndarray:
    g = json.loads(Path(path).read_text())
    pts = []
    for f in g["features"]:
        c = np.asarray(f["geometry"]["coordinates"], dtype=float)
        for a, b in zip(c[:-1], c[1:]):
            n = max(2, int(np.hypot(*(b - a)) / step) + 1)
            pts.extend(a + (b - a) * s for s in np.linspace(0.0, 1.0, n))
    return np.asarray(pts)


def _floodmap(root: Path, arm: str):
    """The cached lev3 hmax floodmap and its transform (what ``motf_metrics`` scores)."""
    with rasterio.open(str(root / "floodmaps" / f"{arm}_hmax_lev3.tif")) as r:
        return r.read(1), r.transform, r.nodata


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("arms", nargs="+")
    ap.add_argument("--line", default=None, help="wavemaker geojson (EPSG:32618)")
    ap.add_argument("--csv", default=None)
    a = ap.parse_args()
    root = exp_root()
    dom = _domain.active()
    line = (
        Path(a.line)
        if a.line
        else DATA / "wavemakers_v3" / "v3_wavemaker_5m_mhw.geojson"
    )

    with rasterio.open(str(motf_path(DATA))) as r:
        motf, mtf, m_nd = r.read(1), r.transform, r.nodata
    mh, mw = motf.shape
    km2 = abs(mtf.a * mtf.e) / 1e6
    Xc = mtf.c + (np.arange(mw) + 0.5) * mtf.a
    Yc = mtf.f + (np.arange(mh) + 0.5) * mtf.e
    XX, YY = np.meshgrid(Xc, Yc)
    coast = (YY < COAST_MAX_Y) & ~((YY > BAY_BOX[0]) & (XX < BAY_BOX[1]))
    dist = np.full(motf.shape, np.inf)
    tree = cKDTree(_line_points(line))
    # only cells that could fall inside 6 km matter; query all coast cells in chunks
    idx = np.where(coast)
    for s in range(0, len(idx[0]), 2_000_000):
        sl = slice(s, s + 2_000_000)
        d, _ = tree.query(
            np.c_[XX[idx][sl], YY[idx][sl]], distance_upper_bound=20_000.0
        )
        dist[idx[0][sl], idx[1][sl]] = d
    excl = motf_exclude_mask(motf.shape, mtf)
    motf_wet = motf == 1

    # dep at MOTF cells: the subgrid DEM behind the floodmap, sampled as motf_metrics does
    first = a.arms[0]
    h0, ftf, _ = _floodmap(root, first)

    # 🔴 sample every raster through its INVERSE AFFINE: the v3 subgrid rasters are on
    # the rotated quadtree frame (CLAUDE.md §5), so x0 + col*res is wrong by up to 3 km.
    def _rc(transform, shape):
        cols, rows = (~transform) * (XX.ravel(), YY.ravel())
        rr = np.clip(np.floor(rows).astype(int), 0, shape[0] - 1).reshape(XX.shape)
        cc = np.clip(np.floor(cols).astype(int), 0, shape[1] - 1).reshape(XX.shape)
        return rr, cc

    rr, cc = _rc(ftf, h0.shape)

    rows = []
    wet = {}
    print(
        f"domain {dom.name}  raster {mw}x{mh}  cell {km2 * 1e6:.1f} m2  line {line.name}"
    )
    for arm in a.arms:
        h, tf, h_nd = _floodmap(root, arm)
        assert tf == ftf, "floodmap grids differ between arms"
        h_at = h[rr, cc].astype(float)
        h_at[h_at == h_nd] = np.nan
        # footprint exactly as motf_metrics: MOTF valid AND subgrid dep > 0 AND simulated
        sim = simulated_mask(root / arm, motf.shape, mtf)
        dep_p = root / arm / "subgrid" / "dep_subgrid_merged.tif"
        if not dep_p.is_file():
            dep_p = root / arm / "subgrid" / "dep_subgrid_lev3.tif"
        with rasterio.open(str(dep_p)) as r:
            dep = r.read(1)
            dr, dc = _rc(r.transform, dep.shape)
            dep_at = dep[dr, dc].astype(float)
            if r.nodata is not None:
                dep_at = np.where(dep_at == r.nodata, np.nan, dep_at)
        land_in = (motf != m_nd) & (dep_at > 0.0) & sim
        if excl is not None:
            land_in &= ~excl
        mod_wet = np.isfinite(h_at) & (h_at >= DEPTH_MIN)
        wet[arm] = mod_wet & land_in
        parts = [("ALL (self-check)", land_in)]
        parts += [
            (f"coast {lo:.0f}-{hi:.0f} m", land_in & coast & (dist >= lo) & (dist < hi))
            for lo, hi in BANDS
        ]
        parts += [("bay remainder", land_in & ~coast)]
        for name, sel in parts:
            nh = int((motf_wet & mod_wet & sel).sum())
            nm = int((motf_wet & ~mod_wet & sel).sum())
            nf = int((~motf_wet & mod_wet & sel).sum())
            row = dict(
                arm=arm,
                band=name,
                n_cells=int(sel.sum()),
                hit_km2=nh * km2,
                miss_km2=nm * km2,
                fa_km2=nf * km2,
                motf_wet_km2=(nh + nm) * km2,
                mod_wet_km2=(nh + nf) * km2,
                csi=nh / (nh + nm + nf) if nh + nm + nf else np.nan,
                pod=nh / (nh + nm) if nh + nm else np.nan,
                far=nf / (nh + nf) if nh + nf else np.nan,
            )
            rows.append(row)
    import pandas as pd

    df = pd.DataFrame(rows)
    if len(a.arms) == 2:
        A, B = a.arms
        newly = wet[B] & ~wet[A]
        lost = wet[A] & ~wet[B]
        for name, sel in (
            [("ALL (self-check)", np.ones_like(coast))]
            + [
                (f"coast {lo:.0f}-{hi:.0f} m", coast & (dist >= lo) & (dist < hi))
                for lo, hi in BANDS
            ]
            + [("bay remainder", ~coast)]
        ):
            m = (df.arm == B) & (df.band == name)
            df.loc[m, "newly_wet_km2"] = float((newly & sel).sum()) * km2
            df.loc[m, "newly_wet_in_motf_km2"] = (
                float((newly & sel & motf_wet).sum()) * km2
            )
            df.loc[m, "newly_dry_km2"] = float((lost & sel).sum()) * km2
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    print(df.round(4).to_string(index=False))
    if a.csv:
        df.to_csv(a.csv, index=False)


if __name__ == "__main__":
    main()
