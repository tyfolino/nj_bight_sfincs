"""anomaly_profile — sills and plugs along tidal creeks and rivers (the bed profile along every NHD flowline).

Paths: every NHD HR flowline (HU4 0203 + 0204, layer NHDFlowline) in the domain box, sampled every 6 m; a point is
TIDAL where the MHHW surface comes from VDatum water, its edge, or a tidal-reach fill (`mhhw_source_v4` 1–6, 11–16,
21 — not the 2 km land extension), and a line is profiled when >= half its points are tidal. The bed at a point is
the MINIMUM over the 3x3 bed pixels around it (~9 m: the thalweg, not the bank, when the line is a little off).
Two signatures:
  sill_above_mhhw  a run of points above MHHW + 0.1 m, <= 600 m long, with tidal points below MHHW on BOTH sides:
                   the tide cannot pass at normal high water. high when it stands >= 0.3 m above MHHW, else medium.
  channel_plug     a run <= 150 m long, below MHHW, standing > 2 m above the DEEPER-than-it channel on both sides
                   within 150 m (bed − max(min upstream, min downstream)): a submerged plug that halves the tide
                   (the Christina plug, the Grays Ferry lidar water surface). high >= 3 m, medium 2–3 m.
NHD lines end at junctions, so a plug exactly at a junction is seen from one side only and can be missed.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("PROJ_DATA", "/home/tpj8/nj_sandy_sfincs/micromamba/envs/sfincs/share/proj")
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import ndimage  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_anomaly"))
import common as C  # noqa: E402

CHECK = "anomaly_profile"
GDBS = [C.REPO / "data/normal_surface_v4/downloads/nhd_0203/NHD_H_0203_HU4_GDB.gdb",
        C.SCR / "anomaly_profile/NHD_H_0204_HU4_GDB.gdb"]
STEP = 6.0
CACHE = C.CTX / "nhd_tidal_points.npz"


def load_points():
    """(x, y, line_id, s) of every 6 m point on tidal-majority flowlines; cached."""
    if CACHE.exists():
        d = np.load(CACHE, allow_pickle=True)
        return d["x"], d["y"], d["lid"], d["s"], d["names"]
    import pyogrio  # noqa: PLC0415

    xs, ys, ls, ss, names = [], [], [], [], []
    lid = 0
    for g in GDBS:
        df = pyogrio.read_dataframe(g, layer="NHDFlowline", bbox=(-75.75, 38.70, -73.55, 41.0),
                                    columns=["gnis_name"])
        for geom, nm in zip(df.geometry.values, df.gnis_name.values):
            parts = geom.geoms if geom.geom_type.startswith("Multi") else [geom]
            for p in parts:
                co = np.asarray(p.coords)[:, :2]
                if len(co) < 2:
                    continue
                x, y = C.TO_UTM(co[:, 0], co[:, 1])
                seg = np.hypot(np.diff(x), np.diff(y))
                cs = np.r_[0, np.cumsum(seg)]
                if cs[-1] < 30:
                    continue
                s = np.arange(0, cs[-1], STEP)
                px, py = np.interp(s, cs, x), np.interp(s, cs, y)
                src = C.g25_sample("mhhw_src", px, py)
                if np.mean(np.isin(src, list(C.TIDAL_SRC))) < 0.5:
                    continue
                xs.append(px)
                ys.append(py)
                ls.append(np.full(len(s), lid, np.int32))
                ss.append(s)
                names.append(nm if isinstance(nm, str) else "")
                lid += 1
    x, y, lids, s = np.concatenate(xs), np.concatenate(ys), np.concatenate(ls), np.concatenate(ss)
    names = np.array(names, object)
    np.savez(CACHE, x=x, y=y, lid=lids, s=s, names=names)
    return x, y, lids, s, names


def tile_fn(bed, t):
    r0, c0, h, w, pi, rr, cc = t
    z, R0, C0, _ = bed.read(r0, c0, h, w, halo=1)
    zm = ndimage.minimum_filter(np.where(np.isfinite(z), z, 1e9), 3)
    v = zm[rr - R0, cc - C0]
    return pi, np.where(v > 1e8, np.nan, v)


def runs(mask):
    """(start, stop) of each True run."""
    d = np.diff(np.r_[0, mask.astype(np.int8), 0])
    return list(zip(np.where(d == 1)[0], np.where(d == -1)[0]))


def main():
    a = C.parse_args(__doc__)
    x, y, lid, s, names = load_points()
    print(f"  {len(x):,} points on {lid.max() + 1:,} tidal flowlines")
    bed = C.Bed(a.bed, a.overlay_min, a.overlay)
    c, r = (~bed.T) * (x, y)
    r, c = np.floor(r).astype(np.int64), np.floor(c).astype(np.int64)
    inside = (r >= 1) & (r < bed.H - 1) & (c >= 1) & (c < bed.W - 1)
    tid = (r // C.TILE) * 10_000 + (c // C.TILE)
    tiles = []
    for k in np.unique(tid[inside]):
        sel = np.where(inside & (tid == k))[0]
        tr_, tc_ = divmod(int(k), 10_000)
        r0, c0 = tr_ * C.TILE, tc_ * C.TILE
        tiles.append((r0, c0, min(C.TILE, bed.H - r0), min(C.TILE, bed.W - c0), sel, r[sel], c[sel]))
    zb = np.full(len(x), np.nan)
    for pi, v in C.run_tiles(a, tile_fn, tiles=tiles):
        zb[pi] = v
    mh = C.g25_sample("mhhw", x, y)
    tidal = np.isin(C.g25_sample("mhhw_src", x, y), list(C.TIDAL_SRC))
    act = C.g25_sample("active", x, y) > 0
    rows = []
    order = np.lexsort((s, lid))
    bounds = np.r_[0, np.where(np.diff(lid[order]) != 0)[0] + 1, len(order)]
    K = int(150 / STEP)
    for b0, b1 in zip(bounds[:-1], bounds[1:]):
        o = order[b0:b1]
        z, m, t, ac = zb[o], mh[o], tidal[o], act[o]
        if np.isfinite(z).sum() < 10:
            continue
        mm = np.where(np.isfinite(m), m, np.nanmedian(m) if np.isfinite(m).any() else 0.8)
        # sills above MHHW
        above = np.isfinite(z) & (z > mm + 0.1) & ac
        for i0, i1 in runs(above):
            L = (i1 - i0) * STEP
            if L > 600 or i0 == 0 or i1 >= len(z):
                continue
            lo_l = np.any((z[max(i0 - K, 0):i0] < mm[max(i0 - K, 0):i0]) & t[max(i0 - K, 0):i0])
            lo_r = np.any((z[i1:i1 + K] < mm[i1:i1 + K]) & t[i1:i1 + K])
            if not (lo_l and lo_r):
                continue
            k = i0 + int(np.nanargmax(z[i0:i1]))
            hgt = z[k] - mm[k]
            rows.append(dict(x=x[o][k], y=y[o][k], kind="sill_above_mhhw", severity="high" if hgt >= 0.3 else "medium",
                             metric="sill_above_mhhw_m", value=round(float(hgt), 2), expected=round(float(mm[k]), 2),
                             length=L, name=names[lid[o][0]], crest=z[k]))
        # submerged plugs
        zz = np.where(np.isfinite(z), z, np.inf)
        n = len(zz)
        lmin = np.array([zz[max(i - K, 0):i].min() if i > 0 else np.inf for i in range(n)])
        rmin = np.array([zz[i + 1:i + 1 + K].min() if i < n - 1 else np.inf for i in range(n)])
        side = np.maximum(lmin, rmin)
        plug = np.where(np.isfinite(side) & np.isfinite(z), z - side, 0)
        pm = (plug > 2.0) & (z < mm) & ac
        for i0, i1 in runs(pm):
            L = (i1 - i0) * STEP
            if L > 150:
                continue
            k = i0 + int(np.argmax(plug[i0:i1]))
            rows.append(dict(x=x[o][k], y=y[o][k], kind="channel_plug", severity="high" if plug[k] >= 3 else "medium",
                             metric="plug_height_m", value=round(float(plug[k]), 2), expected=round(float(side[k]), 2),
                             length=max(L, STEP), name=names[lid[o][0]], crest=z[k]))
    d = pd.DataFrame(rows)
    if len(d):
        d["units"] = np.where(d.kind == "sill_above_mhhw", "m above MHHW", "m above the channel both sides")
        d["area_m2"] = ""
        d["id"] = ["Q" + k[0] + f"{int(xx)}_{int(yy)}" for k, xx, yy in zip(d.kind, d.x, d.y)]
        d["note"] = [(f"{nm or 'creek'}: bed {cr:.2f} m stands {v:.2f} m above MHHW over ~{L:.0f} m with tidal water "
                      "below MHHW on both sides" if k == "sill_above_mhhw" else
                      f"{nm or 'creek'}: a {L:.0f} m plug at {cr:.2f} m, {v:.2f} m above the channel on both sides "
                      f"(deeper side {e:.2f} m)")
                     for k, nm, cr, v, L, e in zip(d.kind, d.name, d.crest, d.value, d.length, d.expected)]
        d["fix"] = ""
    df = C.finish(d if len(d) else None, CHECK, C.bed_label_source(a) + "; NHD HR flowlines HU4 0203+0204; VDatum MHHW")
    if len(df):
        df = df.sort_values(["severity", "value"], key=lambda s_: s_.map(C.SEV_RANK) if s_.name == "severity" else -s_)
    C.write(df, a.out)


if __name__ == "__main__":
    main()
