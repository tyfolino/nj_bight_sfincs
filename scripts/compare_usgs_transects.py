#!/usr/bin/env python
"""Model beach runup level vs USGS per-transect Sandy TWL / dune crest / sandline movement.

Why (STATUS 2026-09-20 pre-registration, 14:35 addendum): the wavemaker arm's infragravity
crests stop at the dune, so the HWM/MOTF scores cannot see them; the USGS sandline-change
transects (doi:10.5066/F71Z42HN) carry Sandy's observed washover (``Sandline_HS_NSM``), the
lidar dune crest (``Z_Max``) and USGS's own Stockdon ``Runup`` / ``TWL``, which is where an
IG lever should show.

The USGS lines run ~19 km from far offshore (Start) to the bay side (End). Each is walked
at 25 m to the MODEL's shoreline (first sample whose nearest active face has zb >= -0.5 m
and stays land for 100 m); the beach reach is the ``--reach`` m beyond it. The model's beach
runup level = max whole-run ``zsmax`` on wet land faces within ``--radius`` of that reach.
Then (A) level - TWL per transect and (B) overwash occurrence (level > Z_Max) against
observed (sandline moved >= ``--washover`` m landward; DSAS sign: negative = landward).

    NJ_DOMAIN=v3 PYTHONPATH=$PWD python scripts/compare_usgs_transects.py naccs-premier wave-wavemaker
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd
import xarray as xr
from pyproj import Transformer
from scipy.spatial import cKDTree

from nj_sfincs.config import DATA, exp_root

USGS = DATA / "validation_v3" / "usgs_sandline" / "New_Jersey_Model_Variables.csv"
AREAS = (
    (38.8, 38.95, "Cape May"),
    (38.95, 39.15, "Wildwood/Avalon"),
    (39.15, 39.45, "Ocean City/Brigantine"),
    (39.45, 39.85, "LBI"),
    (39.85, 40.5, "Barnegat-Monmouth"),
)


def _faces(ds):
    fn = ds["mesh2d_face_nodes"].values.astype(int) - 1
    fx, fy = ds["mesh2d_node_x"].values, ds["mesh2d_node_y"].values
    return fx[fn].mean(1), fy[fn].mean(1)


def _table(h, ms, f):
    pod = h / (h + ms) if h + ms else np.nan
    far = f / (h + f) if h + f else np.nan
    csi = h / (h + ms + f) if h + ms + f else np.nan
    return pod, far, csi


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("arms", nargs="+")
    ap.add_argument("--radius", type=float, default=250.0)
    ap.add_argument("--reach", type=float, default=500.0)
    ap.add_argument("--washover", type=float, default=20.0)
    ap.add_argument("--csv", default=None)
    a = ap.parse_args()
    root = exp_root()
    t = pd.read_csv(USGS)
    tr = Transformer.from_crs(4326, 32618, always_xy=True)
    sx, sy = tr.transform(t.StartX.values, t.StartY.values)
    ex, ey = tr.transform(t.EndX.values, t.EndY.values)
    L = np.hypot(ex - sx, ey - sy)
    ux, uy = (ex - sx) / L, (ey - sy) / L
    steps = np.arange(0.0, 20_000.0 + 1e-6, 25.0)
    px = sx[:, None] + ux[:, None] * steps[None, :]
    py = sy[:, None] + uy[:, None] * steps[None, :]
    nreach = int(a.reach // 25.0) + 1

    cols = [
        "OBJECTID",
        "StartX",
        "StartY",
        "Z_Max",
        "Z_Mean",
        "Sandline_HS_NSM",
        "Frontshore_HS_NSM",
        "Surge",
        "Setup",
        "Runup",
        "TWL",
    ]
    out = t[cols].copy()
    for arm in a.arms:
        ds = xr.open_dataset(str(root / arm / "sfincs_map.nc"))
        cx, cy = _faces(ds)
        zb = ds["zb"].values
        act = (ds["msk"].values > 0) & np.isfinite(zb)
        zmax = np.nanmax(ds["zsmax"].values, axis=0)
        tree = cKDTree(np.c_[cx[act], cy[act]])
        zma, zba = zmax[act], zb[act]
        _, nearest = tree.query(
            np.c_[px.ravel(), py.ravel()], distance_upper_bound=60.0
        )
        nearest = nearest.reshape(px.shape)
        valid = nearest < len(zba)
        zline = np.where(valid, zba[np.minimum(nearest, len(zba) - 1)], np.nan)
        lvl = np.full(len(t), np.nan)
        zsea = np.full(len(t), np.nan)
        shore = np.full(len(t), np.nan)
        for i in range(len(t)):
            land = zline[i] >= -0.5
            ok = np.where(land[:-4] & land[1:-3] & land[2:-2] & land[3:-1] & land[4:])[
                0
            ]
            if len(ok) == 0:
                continue
            j0 = int(ok[0])
            shore[i] = steps[j0]
            near = set()
            for j in range(j0, min(j0 + nreach, len(steps))):
                near.update(tree.query_ball_point((px[i, j], py[i, j]), a.radius))
            if near:
                k = np.fromiter(near, int)
                wet = (zma[k] > zba[k] + 0.15) & (zba[k] > 0.0)
                if wet.any():
                    lvl[i] = np.nanmax(zma[k][wet])
            jsea = np.arange(max(0, j0 - 40), j0)
            ksea = np.unique(nearest[i, jsea][valid[i, jsea]])
            if len(ksea):
                deep = zba[ksea] < -1.0
                if deep.any():
                    zsea[i] = np.nanmax(zma[ksea][deep])
        out[f"shore_m_{arm}"] = shore
        out[f"lvl_{arm}"] = lvl
        out[f"sea_{arm}"] = zsea

    first = a.arms[0]
    ok = out.Runup.notna()
    print(
        f"transects {len(out)}, with USGS Runup {ok.sum()}, with a model shoreline "
        f"{out[f'shore_m_{first}'].notna().sum()} (p50 {out[f'shore_m_{first}'].median():.0f} m "
        f"along the line), with a model beach sample {out[f'lvl_{first}'].notna().sum()}"
    )
    obs_ow = out.Sandline_HS_NSM <= -a.washover
    print(
        f"observed overwash (sandline <= -{a.washover:.0f} m): {int(obs_ow.sum())} of "
        f"{int(out.Sandline_HS_NSM.notna().sum())} transects with a sandline value"
    )
    for arm in a.arms:
        lv = out[f"lvl_{arm}"]
        m = ok & lv.notna()
        d = (lv - out.TWL)[m]
        dsea = (out[f"sea_{arm}"] - out.Surge)[m]
        print(
            f"\n[{arm}] n={m.sum()}  beach level p50 {lv[m].median():.2f}  USGS TWL p50 "
            f"{out.TWL[m].median():.2f}  level-TWL p25 {d.quantile(0.25):+.2f} p50 {d.median():+.2f} "
            f"p75 {d.quantile(0.75):+.2f}  |  datum: model deep max - USGS Surge p50 "
            f"{dsea.median():+.2f} (IQR {dsea.quantile(0.25):+.2f}..{dsea.quantile(0.75):+.2f})"
        )
        pred = lv > out.Z_Max
        mm = lv.notna() & out.Z_Max.notna() & out.Sandline_HS_NSM.notna()
        h = int((pred & obs_ow & mm).sum())
        ms = int((~pred & obs_ow & mm).sum())
        f = int((pred & ~obs_ow & mm).sum())
        cn = int((~pred & ~obs_ow & mm).sum())
        pod, far, csi = _table(h, ms, f)
        print(
            f"   overwash (level > Z_Max) vs observed: hits {h} miss {ms} FA {f} correct-neg {cn}"
            f"  POD {pod:.3f} FAR {far:.3f} CSI {csi:.3f}  predicted rate {pred[mm].mean():.3f}"
            f" observed rate {obs_ow[mm].mean():.3f}"
        )
        for lo, hi, nm in AREAS:
            s = mm & (out.StartY >= lo) & (out.StartY < hi)
            if s.sum() < 20:
                continue
            h = int((pred & obs_ow & s).sum())
            ms = int((~pred & obs_ow & s).sum())
            f = int((pred & ~obs_ow & s).sum())
            pod, far, _ = _table(h, ms, f)
            dd = (lv - out.TWL)[s & ok]
            print(
                f"     {nm:22s} n={s.sum():4d}  obs rate {obs_ow[s].mean():.2f}  pred rate "
                f"{pred[s].mean():.2f}  POD {pod:.2f} FAR {far:.2f}  | level-TWL p50 "
                f"{dd.median() if len(dd) else np.nan:+.2f}  Z_Max p50 {out.Z_Max[s].median():.2f}"
                f"  level p50 {lv[s].median():.2f}  n(TWL) {len(dd)}"
            )
    if len(a.arms) == 2:
        A, B = a.arms
        d = out[f"lvl_{B}"] - out[f"lvl_{A}"]
        print(
            f"\nDelta beach level ({B} - {A}): p10 {d.quantile(0.1):+.2f} p50 {d.median():+.2f} "
            f"p90 {d.quantile(0.9):+.2f}  n {d.notna().sum()}"
        )
    if a.csv:
        out.to_csv(a.csv, index=False)


if __name__ == "__main__":
    main()
