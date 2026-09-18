#!/usr/bin/env python
"""How much of CORA's own wave height does a SnapWave arm deliver to the −9 m shelf?

    NJ_DOMAIN=v3 python scripts/wave_shelf_reference.py experiments/v3/<arm> \
        [--ref-mesh experiments/v3/_template_sealed/sfincs.nc] [--premier <old run>] [--times ...]

Written 2026-09-09 (STATUS 09-09). `scripts/wave_boundary_ring.py`'s table 2 divides the
−9 m shelf hm0 by the IMPOSED hm0 in the same 4 km strip — which is undefined once the
wave boundary sits 15–40 km offshore. This script uses CORA (SWAN on a shelf-resolving
mesh) as the reference instead, per site along a shore-normal line:

  cora_newbnd      CORA hs at the arm's own boundary cells on the line
  cora_old10m      CORA hs at the OLD −10 m line (the sealed template's snapwave_mask == 2;
                   the isobath band every pre-2026-09-11 arm ran on)
  SWAN keeps       cora_old10m / cora_newbnd — SWAN's own shelf transformation
  SnapWave keeps   arm hm0 at the old −10 m cells / cora_newbnd
  shelf9m/cora10m  arm hm0 on the −8.5..−9.8 m SFINCS-active shelf / cora_old10m — the
                   pre-registered transmission ratio (criterion >= 0.85, STATUS 09-08)
  premier column   the same ratio on a --premier run, when one is given (the old
                   naccs-premier is retired since 2026-09-11)

Works on a PARTIAL map (a timed-out or still-running solve): `timemax` is left undecoded
and times the map does not hold yet are reported as NaN. ⚠️ `zb` is NaN on SFINCS-inactive
faces (FINDINGS §37); the shelf strip is selected on the mesh's own `z`, not on `zb`.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from pyproj import Transformer
from scipy.spatial import cKDTree

import nj_sfincs  # noqa: F401
from nj_sfincs import domain as _domain

SITES = {
    "sea_bright": (-73.9735, 40.3600, 270),
    "atlantic_city": (-74.4300, 39.3550, 315),
    "ocean_city": (-74.5650, 39.2750, 315),
    "sea_isle": (-74.6900, 39.1500, 315),
}
DEFAULT_TIMES = (
    "2012-10-28T12:00",
    "2012-10-29T00:00",
    "2012-10-29T12:00",
    "2012-10-30T00:00",
)


def _strip(fx, fy, T, lon, lat, az, length=80_000.0, half=150.0):
    x0, y0 = T.transform(lon, lat)
    a = np.radians(az)
    ux, uy = np.sin(a), np.cos(a)
    dx, dy = fx - x0, fy - y0
    s = -(dx * ux + dy * uy)  # seaward distance from the beach point
    n = -dx * uy + dy * ux
    return (s > 0) & (s < length) & (np.abs(n) < half), s


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("run", type=Path)
    ap.add_argument(
        "--ref-mesh",
        type=Path,
        default=None,
        help="sfincs.nc whose snapwave_mask == 2 is the OLD −10 m isobath line "
        "(default exp_root()/_template_sealed/sfincs.nc)",
    )
    ap.add_argument(
        "--premier",
        type=Path,
        default=None,
        help="optional −10 m-boundary run for the paired premier column "
        "(the old naccs-premier is retired since 2026-09-11)",
    )
    ap.add_argument("--times", nargs="*", default=list(DEFAULT_TIMES))
    args = ap.parse_args()
    dom = _domain.active()
    # 2026-09-18: the sealed v3 template carries no SnapWave boundary, and the arm that
    # held the old -10 m line (`wave-stwave`) is on the retire list, so its mask alone is
    # kept under data/quadtree (3 MB, same face order). Preferred over the template.
    _kept = _domain.DATA / "quadtree" / "v3_snapwave_mask_10m_line_stwave.nc"
    ref_mesh = args.ref_mesh or (
        _kept if _kept.exists() else args.run.parent / "_template_sealed" / "sfincs.nc"
    )
    prem = args.premier
    T = Transformer.from_crs(4326, dom.epsg, always_xy=True)
    kw = {"decode_times": {"timemax": False}}

    cora = xr.open_dataset(dom.cora_waves)
    cx, cy = T.transform(cora["lon"].values, cora["lat"].values)
    ctree = cKDTree(np.c_[cx, cy])
    mesh = xr.open_dataset(args.run / "sfincs.nc")
    z = mesh["z"].values
    fx, fy = mesh["mesh2d_face_x"].values, mesh["mesh2d_face_y"].values
    mp = xr.open_dataset(args.run / "sfincs_map.nc", **kw)
    swm = mp["snapwavemsk"].values
    # The −10 m line: the sealed template's own SnapWave mask (the isobath band every
    # pre-2026-09-11 arm ran on). `snapwave_mask` on the mesh == `snapwavemsk` on a map.
    pswm = xr.open_dataset(ref_mesh)["snapwave_mask"].values
    if not (pswm == 2).any():
        # 2026-09-13: the sealed v3 template's mesh carries NO SnapWave boundary since
        # the wave boundary became a per-arm input; the default ref then yields all-NaN
        # columns with only a "Mean of empty slice" warning. Point --ref-mesh at an arm
        # that still holds the -10 m line, e.g. experiments/v3/wave-stwave/sfincs.nc.
        raise SystemExit(
            f"{ref_mesh}: snapwave_mask has no boundary (==2) cells; pass --ref-mesh "
            "<mesh with the old -10 m line>, e.g. data/quadtree/v3_snapwave_mask_10m_line_stwave.nc"
        )
    pm = xr.open_dataset(prem / "sfincs_map.nc", **kw) if prem is not None else None
    tlast = mp["time"].values.max()

    def cora_at(idx, ti):
        _, j = ctree.query(np.c_[fx[idx], fy[idx]])
        return float(cora["hs"].sel(time=ti, method="nearest").values[j].mean())

    rows = []
    for name, (lon, lat, az) in SITES.items():
        sel, s = _strip(fx, fy, T, lon, lat, az)
        newb = np.where(sel & (swm == 2))[0]
        oldb = np.where(sel & (pswm == 2))[0]
        shelf = np.where(sel & (swm == 1) & (z < -8.5) & (z > -9.8))[0]
        if not len(
            newb
        ):  # a stepped line can miss the strip: nearest boundary cell to its far end
            far = np.argmax(np.where(sel, s, -1))
            newb = np.array(
                [np.argmin(np.hypot(fx - fx[far], fy - fy[far]) + 1e9 * (swm != 2))]
            )
        for tt in args.times:
            ti = np.datetime64(tt)
            r = dict(
                site=name,
                time=tt[5:16],
                newbnd_km=round(float(s[newb].mean()) / 1e3, 1),
                newbnd_z=round(float(np.nanmedian(z[newb])), 0),
            )
            if ti > tlast:
                rows.append(r)
                continue
            hh = mp["hm0"].isel(time=int(np.argmin(np.abs(mp.time.values - ti)))).values
            cn, co = cora_at(newb, ti), cora_at(oldb, ti)
            r.update(
                cora_newbnd=cn,
                cora_old10m=co,
                SWAN_keeps=co / cn,
                SnapWave_keeps=float(np.nanmean(hh[oldb])) / cn,
                shelf9m_over_cora10m=float(np.nanmean(hh[shelf])) / co,
            )
            if pm is not None:
                ph = (
                    pm["hm0"]
                    .isel(time=int(np.argmin(np.abs(pm.time.values - ti))))
                    .values
                )
                r["premier_shelf9m_over_cora10m"] = float(np.nanmean(ph[shelf])) / co
            rows.append(r)
    pd.set_option("display.width", 220)
    df = pd.DataFrame(rows).round(2)
    print(
        f"arm {args.run.name} vs CORA (map ends {str(tlast)[:16]}); criterion: "
        "shelf9m_over_cora10m >= 0.85 at every site and time"
    )
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
