"""anomaly_flat — flat patches of bed at a suspicious level (a water SURFACE or a fill stored as bed).

Rule. A pixel is FLAT when the 3x3 range of the bed around it is <= 5 mm (real ground and real bathymetry are
never that flat over 9 m; CUDEM's ~0 m water fill and hydro-flattened lidar water surfaces are). Building
footprints are excluded (their burned tops are flat by construction). Flat pixels are pooled on the 25 m context
grid; a cell is flat when >= half its bed pixels are; flat cells are classed by their level and context, joined
into 8-connected patches per class, and patches >= 2,000 / 5,000 / 10,000 m2 (high / medium / low) are reported:

  lake_floor_below_pool     flat floor >= 0.5 m under the pool of an adjoining non-tidal NHD lake (CUDEM's fake
                            pit; the Alloway / Silver Lake signature)  -> high
  zero_fill                 flat at |z| < 5 cm on mapped water or below MHHW (CUDEM fill) -> medium
  water_surface_above_mhhw  flat on mapped / tidal water ABOVE MHHW + 0.3 (blocks the tide unless an impounded
                            pool) -> high on tidal water, medium otherwise
  water_surface_in_tide_band  flat on mapped water between -1.6 m and MHHW + 0.3 (lidar water surface at the
                            flight's tide: the "flat sill" under decks) -> medium
  flat_below_mhhw_on_land   flat below MHHW - 0.3 off mapped water (an unmapped pond surface, or fill behind a
                            dike) -> low
Mapped non-tidal lakes flat AT their pool (+-0.5 m) are the §54 design and are not reported.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_anomaly"))
import common as C  # noqa: E402

CHECK = "anomaly_flat"
RANGE_MM = 5.0
MIN_AREA = {"high": 2000.0, "medium": 5000.0, "low": 10000.0}  # m2 per severity


def tile_fn(bed, t):
    r0, c0, h, w = t
    z, R0, C0, b = bed.read(r0, c0, h, w, halo=1, buildings=True)
    valid = np.isfinite(z)
    zz = np.where(valid, z, 0)
    mx = ndimage.maximum_filter(np.where(valid, z, -1e9), 3)
    mn = ndimage.minimum_filter(np.where(valid, z, 1e9), 3)
    flat = valid & ((mx - mn) <= RANGE_MM / 1000.0) & ~b
    sl = (slice(r0 - R0, r0 - R0 + h), slice(c0 - C0, c0 - C0 + w))
    valid, flat, zz = valid[sl], flat[sl], zz[sl]
    X, Y = bed.xy(r0, c0, h, w)
    gr, gc, ok = C.g25_index(X, Y)
    _, _, W25 = C.g25_meta()
    key = (gr * W25 + gc)[ok & valid]
    f = flat[ok & valid]
    zv = zz[ok & valid]
    if key.size == 0:
        return None
    u, inv = np.unique(key, return_inverse=True)
    nval = np.bincount(inv)
    nflat = np.bincount(inv, weights=f)
    sflat = np.bincount(inv, weights=np.where(f, zv, 0.0))
    return u, nval.astype(np.int32), nflat.astype(np.int32), sflat


def main():
    a = C.parse_args(__doc__)
    tr, H, W = C.g25_meta()
    res = C.run_tiles(a, tile_fn)
    nval = np.zeros(H * W, np.int32)
    nflat = np.zeros(H * W, np.int32)
    sflat = np.zeros(H * W, np.float64)
    for r in res:
        if r is None:
            continue
        u, nv, nf, sf = r
        np.add.at(nval, u, nv)
        np.add.at(nflat, u, nf)
        np.add.at(sflat, u, sf)
    G = C.g25()
    act = np.asarray(G["active"]).ravel() > 0
    fl = act & (nval > 0) & (nflat >= 0.5 * np.maximum(nval, 1))
    lev = np.where(nflat > 0, sflat / np.maximum(nflat, 1), np.nan)
    mh = np.asarray(G["mhhw"], float).ravel()
    water = np.asarray(G["water"]).ravel() == 1
    pool = np.asarray(G["pool"], float).ravel()
    src = np.asarray(G["mhhw_src"]).ravel()
    tidal = np.isin(src, list(C.TIDAL_SRC))
    lake = np.isfinite(pool)
    mhv = np.where(np.isfinite(mh), mh, 0.8)

    cls = np.zeros(H * W, np.int8)
    on_pool = lake & (np.abs(lev - pool) <= 0.5)
    k_lake = fl & lake & (pool - lev > 0.5)
    k_zero = fl & ~lake & (np.abs(lev) < 0.05) & (water | (lev < mhv))
    k_above = fl & ~lake & (water | tidal) & (lev > mhv + 0.3) & (lev < mhv + 3.0)
    k_band = fl & ~lake & water & ~k_zero & (lev >= -1.6) & (lev <= mhv + 0.3)
    k_land = fl & ~lake & ~water & ~k_zero & (lev < mhv - 0.3)
    for i, k in enumerate([k_lake, k_zero, k_above, k_band, k_land], start=1):
        cls[k & (cls == 0)] = i
    cls[on_pool] = 0
    # a zero / low-land flat patch touching a lake whose pool stands >= 0.5 m above it is a fake lake floor
    pool2 = ndimage.grey_dilation(np.where(lake, pool, -999).reshape(H, W), size=5).ravel()
    lift = ((cls == 2) | (cls == 5)) & (pool2 > lev + 0.5)
    cls[lift] = 1
    names = {1: "lake_floor_below_pool", 2: "zero_fill", 3: "water_surface_above_mhhw",
             4: "water_surface_in_tide_band", 5: "flat_below_mhhw_on_land"}
    rows = []
    cls2 = cls.reshape(H, W)
    for i, nm in names.items():
        lab, n = C.components_2d(cls2 == i)
        if n == 0:
            continue
        li = lab.ravel()
        sel = li > 0
        idx = li[sel]
        cnt = np.bincount(idx, minlength=n + 1)
        area = np.bincount(idx, weights=nflat[sel] * (3.125 ** 2), minlength=n + 1)
        rr, cc = np.divmod(np.nonzero(sel)[0], W)
        cr = np.bincount(idx, weights=rr, minlength=n + 1) / np.maximum(cnt, 1)
        ccm = np.bincount(idx, weights=cc, minlength=n + 1) / np.maximum(cnt, 1)
        levm = np.bincount(idx, weights=np.nan_to_num(lev[sel]), minlength=n + 1) / np.maximum(cnt, 1)
        mhm = np.bincount(idx, weights=mhv[sel], minlength=n + 1) / np.maximum(cnt, 1)
        tid = np.bincount(idx, weights=tidal[sel], minlength=n + 1) / np.maximum(cnt, 1)
        plm = np.bincount(idx, weights=np.where(np.isfinite(pool2[sel]) & (pool2[sel] > -900), pool2[sel], 0),
                          minlength=n + 1) / np.maximum(cnt, 1)
        for j in range(1, n + 1):
            # representative point: the component cell nearest its centroid
            x, y = C.g25_xy(cr[j], ccm[j])
            if nm == "lake_floor_below_pool":
                sev = "high"
                note = (f"flat bed at {levm[j]:.2f} m under/next to a lake pooled at ~{plm[j]:.2f} m: "
                        "a fake pit (CUDEM fill) that can tie the lake to the tide")
                exp_, fix = round(plm[j], 2), "raise to the pool (as alloway_pool_v4), or check the dam/outlet"
            elif nm == "zero_fill":
                sev = "medium"
                note = f"flat at {levm[j]:.2f} m on water: CUDEM's ~0 m fill, not a surveyed bed"
                exp_, fix = "", "survey / chart / stated-depth bed"
            elif nm == "water_surface_above_mhhw":
                sev = "high" if tid[j] >= 0.5 else "medium"
                note = (f"flat at {levm[j]:.2f} m, {levm[j] - mhm[j]:+.2f} m vs MHHW, on "
                        f"{'tidal' if tid[j] >= 0.5 else 'mapped'} water: a lidar water surface that blocks the "
                        "tide (unless an impounded pool)")
                exp_, fix = round(mhm[j], 2), "min(2012, modern) on mapped water, or a survey; keep if impounded"
            elif nm == "water_surface_in_tide_band":
                sev = "medium"
                note = (f"flat at {levm[j]:.2f} m on mapped water (MHHW {mhm[j]:.2f}): a lidar water surface "
                        "at the flight's tide (the 'flat sill' signature)")
                exp_, fix = "", "channel survey / profile under it"
            else:
                sev = "low"
                note = f"flat at {levm[j]:.2f} m off mapped water, below MHHW {mhm[j]:.2f}: unmapped pond or fill"
                exp_, fix = round(mhm[j], 2), ""
            if area[j] < MIN_AREA[sev]:
                continue
            rows.append(dict(x=float(x), y=float(y), id=f"F{nm[:4]}{int(x)}_{int(y)}", severity=sev, kind=nm,
                             metric="flat_level_m", value=round(levm[j], 2), expected=exp_, units="m NAVD88",
                             area_m2=round(area[j]), note=note, fix=fix))
    df = C.finish(pd.DataFrame(rows), CHECK, C.bed_label_source(a) + "; NHD lakes (lake_pool_v4), VDatum MHHW")
    df = df.sort_values(["severity", "area_m2"], key=lambda s: s.map(C.SEV_RANK) if s.name == "severity" else -s)
    C.write(df, a.out)


if __name__ == "__main__":
    main()
