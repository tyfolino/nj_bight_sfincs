#!/usr/bin/env python
"""Read-only checks on bed_nj2_coarse_25m against bed_v4_coarse_25m (run by j1_coarse_bed.slurm).

    NJ_DOMAIN=nj2 python logs/nj2_freeze_2026-11-14/check_coarse_bed.py

1. Lattice: both 25 m, origins on whole km -> the nj2 grid is a window of v4's (asserted).
2. Where both have data: max |nj2 - v4| (same tier list, same warp -> expect 0; reported).
3. Inside the nj2 ring: NoData count (must be 0), and over the NEW ground (nj2 ring minus the
   v1.1.0 ring) the z distribution, the area below -1 m (water, where create_boundary may put
   mask 2) and the wet fraction at the two forced cuts.
4. The two forced cuts: bed along hudson_w -> hudson_e and hellgate_w -> hellgate_e every 25 m —
   how many 25 m samples are below -1 m (create_boundary's waterlevel zmax) and -0.5 m
   (BoundaryArm.max_bed_m). A wet cut is what makes the arms exist at all.
"""

from __future__ import annotations

import numpy as np

import nj_sfincs  # noqa: F401
from nj_sfincs import domain as D


def main() -> int:
    import geopandas as gpd
    import rasterio
    import shapely
    from rasterio.features import geometry_mask
    from rasterio.windows import from_bounds

    dom = D.active()
    assert dom.name == "nj2", dom.name
    new_p = D.DATA / "elevation_nj2" / "bed_nj2_coarse_25m.tif"
    old_p = D.DATA / "elevation_v4" / "bed_v4_coarse_25m.tif"
    with rasterio.open(new_p) as n, rasterio.open(old_p) as o:
        print(f"nj2 {n.width}x{n.height} {n.transform.c:.0f},{n.transform.f:.0f}  res {n.res}")
        print(f"v4  {o.width}x{o.height} {o.transform.c:.0f},{o.transform.f:.0f}  res {o.res}")
        assert n.res == o.res == (25.0, 25.0)
        assert n.transform.c % 1000 == 0 and n.transform.f % 1000 == 0
        a = n.read(1)
        nod = n.nodata
        # 2. overlap
        b = n.bounds
        ob = o.bounds
        ib = (max(b.left, ob.left), max(b.bottom, ob.bottom), min(b.right, ob.right), min(b.top, ob.top))
        wn = from_bounds(*ib, n.transform).round_offsets().round_lengths()
        wo = from_bounds(*ib, o.transform).round_offsets().round_lengths()
        an = n.read(1, window=wn)
        ao = o.read(1, window=wo)
        both = (an != nod) & (ao != o.nodata)
        d = np.abs(an[both].astype("f8") - ao[both])
        print(f"overlap {both.sum():,} px: max |nj2 - v4| {d.max():.4f} m, n > 1 mm {int((d > 1e-3).sum()):,}")
        # 3. ring
        ring = gpd.read_file(dom.region).to_crs(dom.epsg).geometry.iloc[0]
        old_ring = gpd.read_file(D.V4_REFREEZE_SWZ_V11.region).to_crs(dom.epsg).geometry.iloc[0]
        inside = ~geometry_mask([ring], a.shape, n.transform)
        print(f"nj2 ring: {inside.sum() * 625 / 1e6:,.1f} km², NoData inside {int((inside & (a == nod)).sum())}")
        newg = ring.difference(old_ring)
        lost = old_ring.difference(ring)
        print(f"new ground {newg.area / 1e6:.1f} km²; v1.1.0 ground no longer inside {lost.area / 1e6:.2f} km²")
        m = ~geometry_mask([newg], a.shape, n.transform) & (a != nod)
        z = a[m]
        q = np.percentile(z, [1, 5, 25, 50, 75, 95, 99])
        print(f"new ground z p1/5/25/50/75/95/99: {np.round(q, 2).tolist()}")
        for thr in (-1.0, 0.0, 3.0, 6.44):
            print(f"  below {thr:+.2f} m: {(z < thr).sum() * 625 / 1e6:.1f} km²")
        # 4. the cuts
        cuts = {
            "hudson": ((-73.95753, 40.8600), (-73.9345, 40.8600)),
            "hell_gate": ((-73.9425, 40.7765), (-73.9345, 40.7775)),
        }
        from pyproj import Transformer

        t = Transformer.from_crs(4326, dom.epsg, always_xy=True)
        for name, (p0, p1) in cuts.items():
            ln = shapely.LineString([t.transform(*p0), t.transform(*p1)])
            s = np.arange(0, ln.length, 25.0)
            pts = [ln.interpolate(v) for v in s]
            zz = np.array([v[0] for v in n.sample([(p.x, p.y) for p in pts])])
            zz = np.where(zz == nod, np.nan, zz)
            print(
                f"cut {name}: {ln.length:.0f} m, {len(s)} samples; < -1 m: {int((zz < -1).sum())}, "
                f"< -0.5 m: {int((zz < -0.5).sum())}; min {np.nanmin(zz):+.2f}, max {np.nanmax(zz):+.2f}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
