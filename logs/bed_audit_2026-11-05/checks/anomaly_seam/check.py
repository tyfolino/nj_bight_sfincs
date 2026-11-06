"""anomaly_seam — steps in the bed along the boundary between two of its sources (a merge seam).

Rule (on the 25 m context grid). Which source wins each cell is rebuilt from the bed's OWN recipe
(`provenance.txt` elevation_list): the base tiers in priority order (first with data wins), then every plain
`overlay` painted on top (last wins; `modern_land_2026` is split by WHICH lidar won, from its source raster);
lower-only `overlay_min` tiers and the building burn are not sources here. Tier coverage comes from
`_anomaly/tiers.py` (each tier resampled nearest onto the grid). For every pair of neighbouring cells won by
different sources, the step = the difference of the two cells' MEAN bed; a pair is a seam when
|step| > max(0.5 m, 4 x the roughness between same-source neighbours of either cell). Seam cells are joined into
8-connected lines; lines >= 4 cells (~100 m) are reported:
  high    the step lies across water (>= 80 % of its cells below MHHW, touching mapped water) and is > 1.0 m:
          a sill or a trench made by the merge (the Christina plug sat on such a seam)
  medium  the same with 0.5–1.0 m, or any seam with >= half its cells inside 1.0.0's Sandy footprint
  low     the rest, reported only when > 1.5 m
Real steps at a source edge (a dredged channel's wall where a survey meets the shoal) fire too: the reviewer
decides; the source pair is in the note.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_anomaly"))
import common as C  # noqa: E402

CHECK = "anomaly_seam"
SKIP = {"bed_buildings_v4_cap10"}
MSRC = ["usgs_nj_ne6county_2024", "pa_17county_2024", "usgs_de_statewide_2023", "philadelphia_2022",
        "usace_ncmp_2022", "usgs_ny_se4county_2022", "usace_capemay_ac_2020", "usace_nan_2020",
        "usgs_south_nj_fema_2019", "usgs_south_nj_2019", "usace_ncmp_2017", "nyc_2017", "usgs_nw_nj_2017",
        "usgs_dvrpc_2015"]


def source_map(a, shape):
    prov = json.JSONDecoder().raw_decode(open(a.bed / "provenance.txt").read())[0]
    lst = [(e["elevation"], e.get("merge_method", "")) for e in prov["elevation_list"] if e["elevation"] not in SKIP]
    lst += [(k, "overlay") for k in a.overlay]
    names, win = ["(none)"], np.zeros(shape, np.int16)
    for k, mm in lst:
        if mm == "overlay_min":
            continue
        t = C.tier(k)
        if t is None:
            print(f"  (no tier raster for {k}; run _anomaly/tiers.py)")
            continue
        if k == "modern_land_2026":
            for i, nm in enumerate(MSRC, start=1):
                names.append(f"modern:{nm}")
                win[t == i] = len(names) - 1
            continue
        names.append(k)
        has = np.isfinite(t)
        if mm == "":
            win[has & (win == 0)] = len(names) - 1
        else:
            win[has] = len(names) - 1
    return win, names


def main():
    a = C.parse_args(__doc__)
    tr, H, W = C.g25_meta()
    m = C.g25_bed_mean(a)
    win, names = source_map(a, (H, W))
    G = C.g25()
    act = np.asarray(G["active"]) > 0
    mh = np.asarray(G["mhhw"], float)
    mh = np.where(np.isfinite(mh), mh, 0.8)
    water = np.asarray(G["water"]) == 1
    zs = np.asarray(G["zsmax"], float)
    ok = act & np.isfinite(m) & (win > 0)
    rs = np.zeros((H, W))
    rn = np.zeros((H, W))
    pairs = []
    for dr, dc in [(0, 1), (1, 0)]:
        a1 = (slice(0, H - dr), slice(0, W - dc))
        a2 = (slice(dr, H), slice(dc, W))
        both = ok[a1] & ok[a2]
        dz = np.where(both, m[a2] - m[a1], 0.0)
        same = both & (win[a1] == win[a2])
        for s_ in (a1, a2):
            rs[s_] += np.where(same, np.abs(dz), 0)
            rn[s_] += same
        pairs.append((a1, a2, both & (win[a1] != win[a2]), dz))
    rough = np.where(rn > 0, rs / np.maximum(rn, 1), 0.0)
    seam = np.zeros((H, W), bool)
    step = np.zeros((H, W))
    pa = np.zeros((H, W), np.int32)
    pb = np.zeros((H, W), np.int32)
    for a1, a2, diff, dz in pairs:
        thr = np.maximum(0.5, 4 * np.maximum(rough[a1], rough[a2]))
        f = diff & (np.abs(dz) > thr)
        for s_ in (a1, a2):
            upd = f & (np.abs(dz) > np.abs(step[s_]))
            seam[s_] |= f
            step[s_] = np.where(upd, dz, step[s_])
            pa[s_] = np.where(f, win[a1], pa[s_])
            pb[s_] = np.where(f, win[a2], pb[s_])
    del pairs
    lab, n = ndimage.label(seam, structure=np.ones((3, 3), bool))
    rows = []
    print(f"  {int(seam.sum())} seam cells in {n} lines")
    if n:
        idx = np.arange(1, n + 1)
        cnt = ndimage.sum(seam, lab, idx)
        medstep = ndimage.median(np.abs(step), lab, idx)
        wet = ndimage.mean(m < mh, lab, idx)
        onw = ndimage.mean(water, lab, idx)
        insandy = ndimage.mean(np.isfinite(zs) & (m < zs), lab, idx)
        com = ndimage.center_of_mass(seam, lab, idx)
        objs = ndimage.find_objects(lab)
        for j in range(n):
            if cnt[j] < 4:
                continue
            if wet[j] >= 0.8 and onw[j] > 0 and medstep[j] > 1.0:
                sev = "high"
            elif (wet[j] >= 0.8 and onw[j] > 0) or insandy[j] >= 0.5:
                sev = "medium"
            elif medstep[j] > 1.5:
                sev = "low"
            else:
                continue
            sl = objs[j]
            sub = lab[sl] == j + 1
            pr = pd.Series([tuple(sorted((names[p], names[q]))) for p, q in zip(pa[sl][sub], pb[sl][sub])]).mode()[0]
            r, c = com[j]
            x, y = C.g25_xy(r, c)
            kind = "seam_in_water" if wet[j] >= 0.8 else ("seam_land_water" if wet[j] > 0.2 else "seam_on_land")
            rows.append(dict(x=float(x), y=float(y), id=f"S{int(x)}_{int(y)}", severity=sev, kind=kind,
                             metric="step_m", value=round(float(medstep[j]), 2), expected="",
                             units="m (median |step|)", area_m2=round(float(cnt[j]) * 625),
                             note=f"{pr[0]} | {pr[1]}: {medstep[j]:.2f} m step along ~{cnt[j] * 25:.0f} m of their "
                                  "boundary", fix=""))
    df = C.finish(pd.DataFrame(rows), CHECK, C.bed_label_source(a) + "; tier coverage on G25 (_anomaly/tiers.py)")
    if len(df):
        df = df.sort_values(["severity", "value"], key=lambda s: s.map(C.SEV_RANK) if s.name == "severity" else -s)
    C.write(df, a.out)


if __name__ == "__main__":
    main()
