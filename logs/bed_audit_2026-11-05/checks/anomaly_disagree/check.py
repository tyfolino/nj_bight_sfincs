"""anomaly_disagree — where two beds, or two independent sources, disagree by more than 1 m.

A. 2012 vs modern (pixel by pixel, both beds share one lattice). Pixels with |modern − 2012| > 1 m are pooled on
   the 25 m context grid; cells where >= a quarter of the pixels disagree are joined into 8-connected patches,
   patches >= 0.5 ha reported, classed by where they are:
     water_closed     on water (2012 bed below MHHW) and the modern bed > 1 m HIGHER: a lidar water surface or a
                      fill that closes water (the 11-04 sweep's "135 km2 opened / 23 km2 closed") -> high if it rises
                      above MHHW, else medium
     water_deepened   on water and the modern bed LOWER: dredging / a newer survey (expected) -> low
     land_raised / land_lowered  on land inside 1.0.0's Sandy footprint -> medium (development, fill, a dune, an
                      artifact); outside it -> not reported
   The same patches are written for either bed's label (the comparison is symmetric); --other-bed names the bed to
   compare against (default: the modern bed for a 2012 label, the v1.1 stand-in for a modern label).
B. CUDEM vs lidar (bed-independent; both on the 25 m grid from `_anomaly/tiers.py`, nearest): CUDEM 1/9" (NJ or
   Delaware) vs the NJ 10 ft lidar DEM (or 3DEP where it has none), on land (both above MHHW + 0.5 m) disagreeing by
   > 1 m -> `cudem_vs_lidar_land`, LOW (a source-level note: the bed may not use CUDEM there), >= 8 cells (0.5 ha)
   inside the Sandy footprint, >= 100 cells (6 ha) outside. Both products' vintages differ (development between them fires too).
Known change (dredging, beach fill, development) is not subtracted — the class and the sign say which it likely is.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_anomaly"))
import common as C  # noqa: E402

CHECK = "anomaly_disagree"
V = C.REPO / "experiments/v4_refreeze_swz"


def extra(ap):
    ap.add_argument("--other-bed", type=Path)
    ap.add_argument("--other-overlay-min", action="append", default=None)
    ap.add_argument("--other-overlay", action="append", default=None)


_O = {}


def tile_fn(bed, t):
    r0, c0, h, w = t
    z, _, _, b = bed.read(r0, c0, h, w, buildings=True)
    zo, _, _, _ = _O["bed"].read(r0, c0, h, w)
    dz = zo - z  # other − this
    X, Y = bed.xy(r0, c0, h, w)
    gr, gc, ok = C.g25_index(X, Y)
    _, _, W25 = C.g25_meta()
    v = ok & np.isfinite(dz) & ~b
    if not v.any():
        return None
    u, inv = np.unique((gr * W25 + gc)[v], return_inverse=True)
    big = np.abs(dz[v]) > 1.0
    return (u, np.bincount(inv), np.bincount(inv, weights=big), np.bincount(inv, weights=np.where(big, dz[v], 0)),
            np.bincount(inv, weights=z[v]))


def main():
    a = C.parse_args(__doc__, extra)
    modern_label = "modern" in a.label
    if a.other_bed is None:
        if modern_label:
            v1b = V / "_subgrid_v1_1b"
            a.other_bed = v1b if (v1b / "subgrid/dep_subgrid_merged.tif").exists() else V / "_subgrid_v1_1"
            if a.other_bed.name == "_subgrid_v1_1":
                a.other_overlay_min = a.other_overlay_min or ["deck_fix_v4b"]
                a.other_overlay = a.other_overlay or ["alloway_pool_v4"]
        else:
            a.other_bed = V / "_subgrid_modern2026"
            a.other_overlay_min = a.other_overlay_min or ["v11_deck_npz"]
    other = (a.other_bed, tuple(a.other_overlay_min or ()), tuple(a.other_overlay or ()))
    _O["bed"] = C.Bed(*other)
    print(f"  other bed: {other}")
    tr, H, W = C.g25_meta()
    n = np.zeros(H * W, np.int32)
    nb = np.zeros(H * W, np.int32)
    sd = np.zeros(H * W)
    sz = np.zeros(H * W)
    for r in C.run_tiles(a, tile_fn):
        if r is None:
            continue
        u, c_, b_, d_, z_ = r
        np.add.at(n, u, c_)
        np.add.at(nb, u, b_.astype(np.int32))
        np.add.at(sd, u, d_)
        np.add.at(sz, u, z_)
    G = C.g25()
    act = np.asarray(G["active"]).ravel() > 0
    mh = np.asarray(G["mhhw"], float).ravel()
    mh = np.where(np.isfinite(mh), mh, 0.8)
    zs = np.asarray(G["zsmax"], float).ravel()
    zmean = np.where(n > 0, sz / np.maximum(n, 1), np.nan)
    dmean = np.where(nb > 0, sd / np.maximum(nb, 1), 0)
    flag = act & (n > 0) & (nb >= 0.25 * n)
    # sign / place, from the 2012 side: for a modern label `this` is modern and `other` is 2012
    d26 = -dmean if modern_label else dmean  # modern − 2012
    z12 = zmean + dmean if modern_label else zmean
    wet = z12 < mh
    insandy = np.isfinite(zs) & (z12 < zs)
    cls = np.zeros(H * W, np.int8)
    cls[flag & wet & (d26 > 0)] = 1
    cls[flag & wet & (d26 < 0)] = 2
    cls[flag & ~wet & insandy & (d26 > 0)] = 3
    cls[flag & ~wet & insandy & (d26 < 0)] = 4
    names = {1: "water_closed", 2: "water_deepened", 3: "land_raised", 4: "land_lowered"}
    rows = []
    for i, nm in names.items():
        lab, k = ndimage.label((cls == i).reshape(H, W), structure=np.ones((3, 3), bool))
        if not k:
            continue
        idx = np.arange(1, k + 1)
        nbr = nb.reshape(H, W)
        area = ndimage.sum(nbr, lab, idx) * (3.125 ** 2)
        dm = ndimage.mean(d26.reshape(H, W), lab, idx)
        z1 = ndimage.mean(np.nan_to_num(z12).reshape(H, W), lab, idx)
        mhm = ndimage.mean(mh.reshape(H, W), lab, idx)
        com = ndimage.center_of_mass(cls.reshape(H, W) == i, lab, idx)
        for j in range(k):
            if area[j] < 5000:
                continue
            if nm == "water_closed":
                sev = "high" if z1[j] + dm[j] > mhm[j] else "medium"
            elif nm == "water_deepened":
                sev = "low"
            else:
                sev = "medium"
            x, y = C.g25_xy(*com[j])
            rows.append(dict(x=float(x), y=float(y), id=f"D{nm[:3]}{int(x)}_{int(y)}", severity=sev, kind=nm,
                             metric="modern_minus_2012_m", value=round(float(dm[j]), 2), expected=0, units="m",
                             area_m2=round(float(area[j])),
                             note=f"modern bed {dm[j]:+.2f} m vs 2012 ({z1[j]:.2f} m) over {area[j] / 1e4:.1f} ha; "
                                  f"MHHW {mhm[j]:.2f}",
                             fix="min(2012, modern) on mapped water" if nm == "water_closed" else ""))
    # B. CUDEM vs lidar on land
    cud = C.tier("cudem_nj_v3")
    cde = C.tier("cudem_delaware_v4")
    cud = np.where(np.isfinite(cud), cud, cde)
    lid = C.tier("nj_10ft_dem_v4")
    d3 = C.tier("dep3_v4")
    lid = np.where(np.isfinite(lid), lid, d3)
    mh2 = mh.reshape(H, W)
    land = (cud > mh2 + 0.5) & (lid > mh2 + 0.5) & act.reshape(H, W)
    dd = np.where(land, cud - lid, 0)
    lab, k = ndimage.label(land & (np.abs(dd) > 1.0), structure=np.ones((3, 3), bool))
    if k:
        idx = np.arange(1, k + 1)
        cnt = ndimage.sum(np.ones((H, W)), lab, idx)
        dm = ndimage.mean(dd, lab, idx)
        zsm = ndimage.mean(np.where(np.isfinite(zs.reshape(H, W)), zs.reshape(H, W), -99), lab, idx)
        lm = ndimage.mean(np.nan_to_num(lid), lab, idx)
        com = ndimage.center_of_mass(lab > 0, lab, idx)
        for j in range(k):
            sev = "low"  # a source disagreement, not necessarily in the bed (the bed may not use CUDEM here)
            if cnt[j] < (8 if lm[j] < zsm[j] else 100):
                continue
            x, y = C.g25_xy(*com[j])
            rows.append(dict(x=float(x), y=float(y), id=f"Dcl{int(x)}_{int(y)}", severity=sev,
                             kind="cudem_vs_lidar_land", metric="cudem_minus_lidar_m", value=round(float(dm[j]), 2),
                             expected=0, units="m", area_m2=round(float(cnt[j]) * 625),
                             note=f"CUDEM {dm[j]:+.2f} m vs the lidar DEM over {cnt[j] * 625 / 1e4:.1f} ha of land "
                                  f"(lidar {lm[j]:.2f} m): one of them is wrong here", fix=""))
    df = C.finish(pd.DataFrame(rows), CHECK, C.bed_label_source(a) + f" vs {other[0].name}; CUDEM vs NJ 10 ft / 3DEP")
    if len(df):
        df = df.sort_values(["severity", "area_m2"], key=lambda s: s.map(C.SEV_RANK) if s.name == "severity" else -s)
    C.write(df, a.out)


if __name__ == "__main__":
    main()
