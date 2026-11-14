"""Harbour connectivity of the planned 2012 bed in the nj2 new area (2026-11-14).

fill(p) = the lowest water level at which pixel p joins the open harbour (an Upper Bay seed) through
pixels inside the nj2 ring, on the 2.5 m planned bed (and on the v1.1c base, for comparison).
Computed by labelling bed < h for h = -3.0 .. +4.0 m in 0.1 m steps (8-connected).

A pixel whose own bed is WATER (bed < 0.0 m NAVD88, i.e. below mean tide) but whose fill is above MHHW
(0.70 m) sits in a basin a ridge cuts off from the harbour: a candidate dam (a deck, a causeway, a fill
surface, or a genuinely separate pond — Central Park, Prospect Park). Clusters of those are written to
blocked_<label>.csv with area, own-bed median and fill (= the sill height).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from scipy import ndimage as ndi

D = Path("/scratch/tpj8/tmp/nj2_decks_2026-11-14")
L = Path("/cache/home/tpj8/nj_bight_sfincs/logs/nj2_decks_2026-11-14")
MHHW = 0.70
SEED_LL = (-74.040, 40.670)  # Upper Bay, ~ -15 m


def fill_level(z, inside, seed_rc, levels):
    F = np.full(z.shape, np.float32(np.inf), np.float32)
    st = np.ones((3, 3), bool)
    for h in levels:
        m = inside & (z < h)
        lab, _ = ndi.label(m, structure=st)
        k = lab[seed_rc]
        if k == 0:
            continue
        sel = (lab == k) & np.isinf(F)
        F[sel] = h
    return F


def main(label):
    with rasterio.open(D / f"{label}.tif") as s:
        z = s.read(1)
        T = s.transform
        prof = s.profile
    with rasterio.open(D / "area_mask.tif") as s:
        am = s.read(1)
    inside = am >= 1
    x, y = Transformer.from_crs(4326, 32618, always_xy=True).transform(*SEED_LL)
    rc = (int((y - T.f) / T.e), int((x - T.c) / T.a))
    print("seed bed", z[rc])
    levels = np.round(np.arange(-3.0, 4.01, 0.1), 2)
    F = fill_level(np.nan_to_num(z, nan=99.0), inside, rc, levels)
    with rasterio.open(D / f"fill_{label}.tif", "w", **dict(prof, nodata=np.inf)) as d:
        d.write(F, 1)
    blocked = (am == 1) & (z < 0.0) & (F > MHHW)
    lab, n = ndi.label(blocked, structure=np.ones((3, 3), bool))
    print("blocked water px (new area)", int(blocked.sum()), "clusters", n)
    idx = np.arange(1, n + 1)
    area = ndi.sum(np.ones_like(z), lab, idx) * T.a * -T.e
    zmed = ndi.median(z, lab, idx)
    fmin = ndi.minimum(np.where(np.isinf(F), 99, F), lab, idx)
    com = ndi.center_of_mass(blocked, lab, idx)
    tr = Transformer.from_crs(32618, 4326, always_xy=True)
    rows = []
    for k, a, zm, f, (r, c) in zip(idx, area, zmed, fmin, com):
        if a < 200:  # < 32 px
            continue
        lon, lat = tr.transform(T.c + (c + 0.5) * T.a, T.f + (r + 0.5) * T.e)
        rows.append(dict(cluster=k, area_m2=round(a), bed_p50=round(float(zm), 2), fill=round(float(f), 2), lat=round(lat, 5), lon=round(lon, 5)))
    B = pd.DataFrame(rows).sort_values("area_m2", ascending=False)
    B.to_csv(L / f"blocked_{label}.csv", index=False)
    print(B.head(40).to_string())


if __name__ == "__main__":
    main(sys.argv[1])
