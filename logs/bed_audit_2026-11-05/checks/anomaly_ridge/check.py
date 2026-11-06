"""anomaly_ridge — thin ridges that stand across a low path (a deck, a sliver, a wall or a lidar artifact).

Rule (morphological opening on the bed, per tile, buildings excluded):
  thin_ridge        bed − opening(bed, 5x5 px = 15.6 m) > 0.5 m: a ridge 1–4 px (3–12 m) wide with LOWER ground on
                    both sides (an opening removes only bright features narrower than its window, so a bank or a
                    bulkhead with high land behind it is NOT a ridge). >= 5 px and >= 15 m long.
  deck_scale_ridge  bed − opening(bed, 11x11 px = 34 m) > 1.0 m, not already a thin ridge, standing over ground
                    below MHHW (a deck or causeway across water). >= 10 px.
"Ground without the ridge" = the opening's level under it. Severity:
  high    the ridge sits on MAPPED water (NHD river / lake area, or a lake pool +1 cell), its ground is a channel
          (< MHHW - 0.3 m, and not CUDEM's exact ~0 m fill outside a lake) and its crest stands > MHHW + 0.3 (blocks a normally-wet path)
  medium  the same with a submerged sill >= 2 m high (1–2 m: low; mostly natural bars)
  low     (thin ridges, >= 50 m long) a wall >= 1.5 m above both MHHW and the ground on low land inside 1.0.0's Sandy
          footprint: mostly real walls / berms (the first full run put ~8,000 per bed here as medium)
  (nothing else is reported: ridges over the marsh platform, ~MHHW, are mostly real marsh strips between creeks —
  the first calibration run flagged 8,751 in one 30-tile box before this rule)
Every reported ridge must also stand >= 0.5 m above the MEDIAN bed within ~50 m (a marsh strip between
creeks does not; a deck, a sliver in a flat valley or a wall does), except submerged sills.
Real thin walls (bulkheads standing alone, floodwalls, Jersey barriers in the bare-earth product) fire too: that
is the point — each is a wall the model sees, and the reviewer says whether it is real.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_anomaly"))
import common as C  # noqa: E402

CHECK = "anomaly_ridge"
HALO = 8


def comps(mask, z, zo, h_arr, bed, R0, C0, sl, kind, min_px):
    lab, n = ndimage.label(mask, structure=np.ones((3, 3), bool))
    if n == 0:
        return []
    objs = ndimage.find_objects(lab)
    idx = np.arange(1, n + 1)
    npx = ndimage.sum(np.ones_like(z), lab, idx)
    crest = ndimage.maximum(z, lab, idx)
    hmax = ndimage.maximum(h_arr, lab, idx)
    ground = ndimage.median(zo, lab, idx)
    com = ndimage.center_of_mass(mask, lab, idx)
    out = []
    for j in range(n):
        if npx[j] < min_px:
            continue
        s = objs[j]
        length = 3.125 * float(np.hypot(s[0].stop - s[0].start, s[1].stop - s[1].start))
        if kind == "thin_ridge" and length < 15:
            continue
        r, c = com[j]
        # keep only components whose centre lies in the tile proper (halo = the neighbour's job)
        if not (sl[0].start <= r < sl[0].stop and sl[1].start <= c < sl[1].stop):
            continue
        ri, ci = int(r), int(c)
        win = z[max(ri - 16, 0):ri + 17, max(ci - 16, 0):ci + 17]
        reg = float(np.median(win[win > -49]))  # the local terrain within ~50 m (ridge included)
        x, y = bed.pix_xy(R0 + r, C0 + c)
        out.append((float(x), float(y), kind, int(npx[j]), float(crest[j]), float(hmax[j]), float(ground[j]), length,
                    reg))
    return out


def tile_fn(bed, t):
    r0, c0, h, w = t
    z, R0, C0, b = bed.read(r0, c0, h, w, halo=HALO, buildings=True)
    valid = np.isfinite(z)
    if valid.sum() < 100:
        return []
    zf = np.where(valid, z, -50.0)
    bad = ndimage.binary_dilation(~valid, iterations=6)
    bld = ndimage.binary_dilation(b, iterations=2)
    o5 = ndimage.grey_opening(zf, size=(5, 5))
    h5 = zf - o5
    thin = (h5 > 0.5) & ~bad & ~bld
    o11 = ndimage.grey_opening(zf, size=(11, 11))
    h11 = zf - o11
    wide = (h11 > 1.0) & ~bad & ~bld & ~ndimage.binary_dilation(thin, iterations=1)
    sl = (slice(r0 - R0, r0 - R0 + h), slice(c0 - C0, c0 - C0 + w))
    out = comps(thin, zf, o5, h5, bed, R0, C0, sl, "thin_ridge", 5)
    out += comps(wide, zf, o11, h11, bed, R0, C0, sl, "deck_scale_ridge", 10)
    return out


def main():
    a = C.parse_args(__doc__)
    res = C.run_tiles(a, tile_fn)
    rows = [r for t in res for r in t]
    if not rows:
        C.write(C.finish(None, CHECK, ""), a.out)
        return
    d = pd.DataFrame(rows, columns=["x", "y", "kind", "npx", "crest", "hmax", "ground", "length", "reg"])
    mh = C.g25_sample("mhhw", d.x.values, d.y.values, nan_radius=4)
    mh = np.where(np.isfinite(mh), mh, 0.8)
    zs = C.g25_sample("zsmax", d.x.values, d.y.values, nan_radius=4)
    sev = np.full(len(d), "", object)
    g, cr, hm = d.ground.values, d.crest.values, d.hmax.values
    # on MAPPED water (NHD river / lake area or a lake pool, widened by one 25 m cell): marsh strips between
    # creeks are not in it; decks over rivers and slivers in lake outlines are
    Gw = C.g25()
    lakep = ndimage.binary_dilation(np.isfinite(np.asarray(Gw["pool"])), iterations=1)
    rr, cc, ok = C.g25_index(d.x.values, d.y.values)
    onlake = lakep[rr, cc] & ok
    onw = ((np.asarray(Gw["water"])[rr, cc] == 1) & ok) | onlake
    # a ridge whose "ground" is CUDEM's exact ~0 m fill is a marsh strip over a fake creek bed: the fill is
    # anomaly_flat's finding, so it is not repeated here — except inside a lake (Alloway's sliver)
    zero = (np.abs(g) < 0.05) & ~onlake
    chan = onw & (g < mh - 0.3) & ~zero  # a real channel under the ridge, not the marsh platform (~MHHW)
    above = cr > d.reg.values + 0.5  # stands above the local terrain, not just above the creek beside it
    blocks = chan & (cr > mh + 0.3) & above
    sub = chan & (cr <= mh + 0.3) & (hm >= 1.0)
    tall = ((d.kind.values == "thin_ridge") & ~chan & np.isfinite(zs) & (g < zs) & (cr > np.maximum(mh + 1.5, g + 1.5))
            & (d.length.values >= 30) & above)
    sev[blocks] = "high"
    sev[(sev == "") & sub & (hm >= 2.0)] = "medium"
    sev[(sev == "") & sub] = "low"
    sev[(sev == "") & tall & (d.length.values >= 50)] = "low"
    keep = sev != ""
    d = d[keep].copy()
    d["severity"] = sev[keep]
    mhk, zsk = mh[keep], zs[keep]
    d["metric"] = "ridge_height_m"
    d["value"] = d.hmax.round(2)
    d["expected"] = d.ground.round(2)
    d["units"] = "m above the ground either side"
    d["area_m2"] = (d.npx * 3.125 ** 2).round()
    d["id"] = ["R" + k[0] + f"{int(x)}_{int(y)}" for k, x, y in zip(d.kind, d.x, d.y)]
    d["note"] = [f"{'thin' if k == 'thin_ridge' else 'deck-scale'} ridge, crest {c:.2f} m over ground {g:.2f} m "
                 f"(MHHW {m:.2f}{'' if not np.isfinite(z) else f', Sandy {z:.2f}'}), ~{L:.0f} m long"
                 for k, c, g, m, z, L in zip(d.kind, d.crest, d.ground, mhk, zsk, d.length)]
    d["fix"] = ""
    df = C.finish(d, CHECK, C.bed_label_source(a))
    df = df.sort_values(["severity", "value"], key=lambda s: s.map(C.SEV_RANK) if s.name == "severity" else -s)
    C.write(df, a.out)


if __name__ == "__main__":
    main()
