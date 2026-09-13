"""Pre-flight for a stepped SnapWave boundary: build it on the FROZEN mesh and look.

Run this before staging an arm that uses ``WaveConfig.snapwave_domain``. It builds the
SnapWave mask exactly as ``model.add_waves`` will, then prints what a solve would
otherwise reveal ten hours later:

* band / active / boundary cell counts and how many SFINCS-active cells poke through
  the band's seaward limit (must be 0 — otherwise the water-level and wave boundaries
  are not decoupled);
* per step segment: bed depth along the boundary cells (want 20–35 m: deep enough that
  the imposed Hs is not depth-limited, shallow enough that CORA has nodes within 5 km);
* the RING REPORT — active cells touching >= 2 boundary cells. Those are the cells
  SnapWave will zero (STATUS 09-08). Expect ≈ one per step; the isobath boundary had
  2,580;
* the support points ``add_waves`` will place, with the distance to the nearest CORA
  node (the sampler refuses > 5 km);
* optionally a GeoJSON of boundary cells + the polyline for QGIS.

Usage::

    NJ_DOMAIN=v3 python scripts/check_snapwave_domain.py v3_shelf_steps \
        [--mesh data/frozen_mesh_v3/sfincs.nc] [--waves data/waves_v3/cora_waves_v3.nc] \
        [--n-support 60] [--geojson reports/snapwave_domain_v3.geojson]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

import nj_sfincs  # noqa: F401
from nj_sfincs import domain as _domain
from nj_sfincs import snapwave_domain as sd


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("table", help="key in domain.SNAPWAVE_STEPS")
    ap.add_argument(
        "--mesh", type=Path, default=None, help="sfincs.nc (default: frozen mesh)"
    )
    ap.add_argument("--waves", type=Path, default=None, help="CORA/STWAVE point file")
    ap.add_argument("--n-support", type=int, default=60)
    ap.add_argument("--geojson", type=Path, default=None)
    ap.add_argument(
        "--open-coast-max-y",
        type=float,
        default=None,
        help="override Domain.open_coast_max_y as WaveConfig.open_coast_max_y "
        "does for one arm ('inf' = no demotion)",
    )
    args = ap.parse_args()
    pd.set_option("display.width", 200)

    dom = _domain.active()
    steps = _domain.SNAPWAVE_STEPS[args.table]
    mesh = args.mesh or (dom.frozen_mesh_dir() / "sfincs.nc")
    ds = xr.open_dataset(mesh)
    n, m, lev = ds["n"].values, ds["m"].values, ds["level"].values
    z, sm = ds["z"].values, ds["mask"].values
    attrs = {k: ds.attrs[k] for k in ("x0", "y0", "dx", "dy", "rotation")}
    fx, fy = ds["mesh2d_face_x"].values, ds["mesh2d_face_y"].values

    swm, info = sd.build_snapwave_mask(n, m, lev, z, sm, steps, dom.mask_zmin)
    print(f"== {steps.name} on {mesh}")
    for k, v in info.items():
        print(f"   {k:28s} {v}")
    if info["n_sfincs_outside_band"]:
        print(
            "   🔴 SFINCS-active cells lie EAST of the band limit — move that step seaward."
        )

    # Demotion north of the open coast, as add_waves does it.
    ocmy = (
        args.open_coast_max_y
        if args.open_coast_max_y is not None
        else dom.open_coast_max_y
    )
    demote = (swm == 2) & (fy >= (ocmy if ocmy is not None else np.inf))
    swm2 = swm.copy()
    swm2[demote] = 1
    print(f"   boundary cells demoted north of open_coast_max_y: {int(demote.sum())}")

    n1, m1 = sd.level1_index(n, m, lev)
    print("\n== boundary bed depth per segment (m NAVD88; want -20..-35)")
    rows = []
    for lo, hi, M in steps.steps:
        b = (swm2 == 2) & (n1 >= lo) & (n1 <= hi)
        col = b & (m1 == M)
        stp = b & (m1 < M)
        for lab, sel in (("N-S column", col), ("E-W step/bottom", stp)):
            if sel.any():
                rows.append(
                    dict(
                        rows=f"{lo}-{hi}",
                        M=M,
                        part=lab,
                        n=int(sel.sum()),
                        z_min=np.nanmin(z[sel]),
                        z_p5=np.nanpercentile(z[sel], 5),
                        z_med=np.nanmedian(z[sel]),
                        z_p95=np.nanpercentile(z[sel], 95),
                        z_max=np.nanmax(z[sel]),
                        levels=dict(
                            zip(
                                *[
                                    a.tolist()
                                    for a in np.unique(lev[sel], return_counts=True)
                                ]
                            )
                        ),
                        x_km=f"{fx[sel].min() / 1e3:.1f}-{fx[sel].max() / 1e3:.1f}",
                    )
                )
    print(pd.DataFrame(rows).round(1).to_string(index=False))

    print(
        "\n== ring report (active cells touching >= 2 boundary cells = predicted dead)"
    )
    rr = sd.ring_report(ds["mesh2d_face_faces"].values, swm2)
    print(
        f"   ring {rr['n_ring']}  one-neighbour {rr['n_one']}  two-plus {rr['n_two_plus']} "
        f"({rr['frac_two_plus']:.3%})"
    )
    if rr["n_two_plus"]:
        k = rr["two_plus_faces"]
        print("   two-plus cells (x km, y km, z, level):")
        for i in k[:20]:
            print(f"     {fx[i] / 1e3:8.2f} {fy[i] / 1e3:9.2f} {z[i]:7.1f} L{lev[i]}")

    # Support points as add_waves will place them.
    poly = sd.boundary_polyline(steps, attrs)
    bxy = np.c_[fx, fy][(swm2 == 2) & (z < -5.0)]
    pts = sd.support_points(poly, bxy, args.n_support)
    print(
        f"\n== {len(pts)} support points along the {np.sum(np.hypot(*np.diff(poly, axis=0).T)) / 1e3:.0f} km line"
    )
    if args.waves is not None:
        import pyproj

        w = xr.open_dataset(args.waves)
        tf = pyproj.Transformer.from_crs(dom.epsg, 4326, always_xy=True)
        plon, plat = tf.transform(pts[:, 0], pts[:, 1])
        slon, slat = w["lon"].values, w["lat"].values
        dep = w["depth"].values if "depth" in w else None
        d = np.array(
            [
                np.min(np.hypot((slon - lo) * np.cos(np.deg2rad(la)), slat - la))
                * 111_000
                for lo, la in zip(plon, plat)
            ]
        )
        j = np.array(
            [
                int(
                    np.argmin(np.hypot((slon - lo) * np.cos(np.deg2rad(la)), slat - la))
                )
                for lo, la in zip(plon, plat)
            ]
        )
        print(
            f"   nearest {args.waves.name} node: median {np.median(d) / 1e3:.2f} km, "
            f"max {d.max() / 1e3:.2f} km (limit 5 km)"
            + (
                f"; node depth {np.min(dep[j]):.1f}..{np.max(dep[j]):.1f} m"
                if dep is not None
                else ""
            )
        )
        if d.max() > 5000:
            print(
                "   🔴 a support point has no wave node within 5 km — add_waves will refuse."
            )

    if args.geojson is not None:
        import geopandas as gpd
        from shapely.geometry import LineString, Point

        cells = gpd.GeoDataFrame(
            {"z": z[swm2 == 2], "level": lev[swm2 == 2]},
            geometry=[Point(a, b) for a, b in zip(fx[swm2 == 2], fy[swm2 == 2])],
            crs=dom.epsg,
        )
        line = gpd.GeoDataFrame(
            {"name": [steps.name]}, geometry=[LineString(poly)], crs=dom.epsg
        )
        sp = gpd.GeoDataFrame(
            {"k": range(len(pts))}, geometry=[Point(a, b) for a, b in pts], crs=dom.epsg
        )
        args.geojson.parent.mkdir(parents=True, exist_ok=True)
        pd.concat(
            [
                cells.assign(kind="boundary_cell"),
                line.assign(kind="polyline"),
                sp.assign(kind="support_point"),
            ]
        ).to_file(args.geojson, driver="GeoJSON")
        print(f"   wrote {args.geojson}")


if __name__ == "__main__":
    main()
