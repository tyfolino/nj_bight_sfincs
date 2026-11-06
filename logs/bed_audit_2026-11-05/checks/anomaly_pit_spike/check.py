"""anomaly_pit_spike — small isolated pits and spikes (a carve that over-reached, a burn or merge artifact).

Rule (per tile, morphological, buildings excluded):
  pit    closing(bed, 7x7 px = 22 m) − bed > 2.0 m over a compact patch of <= 40 px (~390 m2), >= 16 m from any
         building footprint (a street between burned buildings closes into a fake pit), whose surroundings
         (the closing) stand above MHHW, off mapped water: a hole in normally-dry ground. Real ones exist (basements
         in the bare earth, quarries are bigger); the model treats it as storage that fills first.
         Reported (medium) only when >= 4 m deep inside 1.0.0's Sandy footprint (surroundings below the Sandy peak).
  spike  bed − opening(bed, 7x7 px) > 2.0 m over <= 15 px (~150 m2: a post, not a pier) whose surroundings lie below MHHW: a post, a pier pile,
         a lidar return or a burn left standing in water. high if its top stands above MHHW (a block in a
         channel), medium if it is submerged.
Channels are not pits (they are long, and they sit below MHHW); spikes on land are vegetation / structures and are
not reported.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_anomaly"))
import common as C  # noqa: E402

CHECK = "anomaly_pit_spike"
HALO = 6
MAXPX = 40


def tile_fn(bed, t):
    r0, c0, h, w = t
    z, R0, C0, b = bed.read(r0, c0, h, w, halo=HALO, buildings=True)
    valid = np.isfinite(z)
    if valid.sum() < 100:
        return []
    bad = ndimage.binary_dilation(~valid, iterations=5)
    bld = ndimage.binary_dilation(b, iterations=3)
    bld5 = ndimage.binary_dilation(b, iterations=5)  # a street between burned buildings closes into a fake 'pit'
    zf = np.where(valid, z, np.nanmedian(z))
    cl = ndimage.grey_closing(zf, size=(7, 7))
    op = ndimage.grey_opening(zf, size=(7, 7))
    sl = (slice(r0 - R0, r0 - R0 + h), slice(c0 - C0, c0 - C0 + w))
    out = []
    for kind, m, ref, depth in [("pit", (cl - zf > 2.0) & ~bad & ~bld5, cl, cl - zf),
                                ("spike", (zf - op > 2.0) & ~bad & ~bld, op, zf - op)]:
        lab, n = ndimage.label(m, structure=np.ones((3, 3), bool))
        if n == 0:
            continue
        idx = np.arange(1, n + 1)
        npx = ndimage.sum(np.ones_like(zf), lab, idx)
        dmax = ndimage.maximum(depth, lab, idx)
        refm = ndimage.median(ref, lab, idx)
        ext = ndimage.minimum(zf, lab, idx) if kind == "pit" else ndimage.maximum(zf, lab, idx)
        com = ndimage.center_of_mass(m, lab, idx)
        for j in np.where(npx <= (MAXPX if kind == "pit" else 15))[0]:
            r, c = com[j]
            if not (sl[0].start <= r < sl[0].stop and sl[1].start <= c < sl[1].stop):
                continue
            x, y = bed.pix_xy(R0 + r, C0 + c)
            out.append((float(x), float(y), kind, int(npx[j]), float(dmax[j]), float(refm[j]), float(ext[j])))
    return out


def main():
    a = C.parse_args(__doc__)
    res = C.run_tiles(a, tile_fn)
    rows = [r for t in res for r in t]
    if not rows:
        C.write(C.finish(None, CHECK, ""), a.out)
        return
    d = pd.DataFrame(rows, columns=["x", "y", "kind", "npx", "dmax", "ref", "ext"])
    mh = C.g25_sample("mhhw", d.x.values, d.y.values, nan_radius=4)
    mh = np.where(np.isfinite(mh), mh, 0.8)
    zs = C.g25_sample("zsmax", d.x.values, d.y.values, nan_radius=4)
    rr, cc, ok = C.g25_index(d.x.values, d.y.values)
    water = (np.asarray(C.g25()["water"])[rr, cc] == 1) & ok
    sev = np.full(len(d), "", object)
    pit = ((d.kind.values == "pit") & (d.ref.values > mh) & ~water & np.isfinite(zs) & (d.ref.values < zs)
           & (d.dmax.values >= 4.0))
    spk = (d.kind.values == "spike") & (d.ref.values < mh) & water & (d.npx.values >= 3)
    sev[pit] = "medium"
    sev[spk & (d.ext.values > mh + 1.0)] = "high"
    sev[spk & (d.ext.values <= mh + 1.0)] = "medium"
    keep = sev != ""
    d = d[keep].copy()
    d["severity"] = sev[keep]
    mhk, zsk = mh[keep], zs[keep]
    d["kind"] = np.where(d.kind == "pit", "pit_on_dry_ground", "spike_in_water")
    d["metric"] = np.where(d.kind == "pit_on_dry_ground", "pit_depth_m", "spike_height_m")
    d["value"] = d.dmax.round(2)
    d["expected"] = d.ref.round(2)
    d["units"] = "m vs the surroundings"
    d["area_m2"] = (d.npx * 3.125 ** 2).round()
    d["id"] = ["P" + k[0] + f"{int(x)}_{int(y)}" for k, x, y in zip(d.kind, d.x, d.y)]
    d["note"] = [(f"pit to {e:.2f} m in ground at {r:.2f} m (Sandy {z:.2f}): storage the model fills first"
                  if k == "pit_on_dry_ground" else
                  f"spike to {e:.2f} m in water at {r:.2f} m (MHHW {m:.2f}): a post / pile / lidar return in the bed")
                 for k, e, r, z, m in zip(d.kind, d.ext, d.ref, zsk, mhk)]
    d["fix"] = ""
    df = C.finish(d, CHECK, C.bed_label_source(a))
    df = df.sort_values(["severity", "value"], key=lambda s: s.map(C.SEV_RANK) if s.name == "severity" else -s)
    C.write(df, a.out)


if __name__ == "__main__":
    main()
