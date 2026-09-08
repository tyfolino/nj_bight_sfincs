"""Is the SnapWave boundary TRANSMITTING the waves we impose on it?

Written 2026-09-08 after the open-coast / back-bay low-bias review (STATUS 09-08). The
imposed boundary Hs sits on the ``snapwavemsk == 2`` cells; this script asks what the
cells immediately INSIDE that line carry. Three tables, all off ``sfincs_map.nc``:

1. **The dead ring.** Every interior cell (``snapwavemsk == 1``) that touches a boundary
   cell, and how many of them have hm0 == 0 AND zero wave force AND a fill-value
   direction — i.e. no wave state at all, on two independent fields. Split north/south
   of v1.5's southern limit, and by how many boundary neighbours the cell has (the
   staircase-corner signature: dead cells touch ~2 boundary cells, live ones ~1).
2. **First-interior / imposed ratio**, domain-wide and per named site: mean hm0 on the
   shelf cells 100–300 m inside the boundary (zb −9.8..−8.5) over mean hm0 on the
   boundary cells of the same shore-normal strip. Nothing physical (Baldock breaking at
   Hs/h ≈ 0.45 gives Qb ≈ 0.005; fw = 0.02 friction over 300 m is ≪ 10 %) can take more
   than a few percent off in that distance, so a ratio well below 1 is transmission loss.
3. **Cross-shore setup transects** (optional, ``--setup``, needs the paired waves-off
   arm): premier − nowaves zs and hm0 in 200 m bins from 4 km offshore to the beach,
   pre-storm and at the peak. This is the number the boundary defect ultimately costs.

Usage::

    NJ_DOMAIN=v3 python scripts/wave_boundary_ring.py experiments/v3/naccs-premier
    NJ_DOMAIN=v3 python scripts/wave_boundary_ring.py experiments/v3/naccs-premier \
        --setup experiments/v3/naccs-nowaves

Pre-registered success for any boundary fix (STATUS 09-08): dead-ring fraction → ≈0,
first-interior ratio ≥ 0.85 at every site and time, and only THEN read the setup table.

⚠️ ``zb`` is NaN on SFINCS-inactive faces (FINDINGS §37); every selection here screens on
``snapwavemsk`` first and ``np.isfinite(zb)`` second, never on ``zb`` alone.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from pyproj import Transformer

import nj_sfincs  # noqa: F401  (pyproj-before-hydromt import order)
from nj_sfincs.validate import core as C

#: v1.5's southern limit (lat 40.150 in UTM 18N): everything south is v3's new coast.
V1_5_SOUTH_LIMIT_Y = 4_443_729

#: Beach points (lon, lat) and the LANDWARD azimuth of a shore-normal line there.
SITES = {
    "sea_bright": (-73.9735, 40.3600, 270),
    "atlantic_city": (-74.4300, 39.3550, 315),
    "ocean_city": (-74.5650, 39.2750, 315),
    "sea_isle": (-74.6900, 39.1500, 315),
}
TIMES = ("2012-10-28T12:00", "2012-10-29T00:00", "2012-10-29T12:00", "2012-10-30T00:00")
PRE = (np.datetime64("2012-10-28T06:00"), np.datetime64("2012-10-29T12:00"))
PEAK = (np.datetime64("2012-10-29T21:00"), np.datetime64("2012-10-30T03:00"))

_T = Transformer.from_crs(4326, 32618, always_xy=True)


def _strip(fx, fy, lon, lat, az, length=4800.0, half_width=150.0):
    """Face indices and along-line distance for a shore-normal strip.

    The line starts 4 km seaward of the beach point and runs landward; ``s`` is the
    distance from that offshore start.
    """
    x0, y0 = _T.transform(lon, lat)
    a = np.radians(az)
    ux, uy = np.sin(a), np.cos(a)
    xs, ys = x0 - 4000 * ux, y0 - 4000 * uy
    dx, dy = fx - xs, fy - ys
    s = dx * ux + dy * uy
    n = -dx * uy + dy * ux
    sel = (s > 0) & (s < length) & (np.abs(n) < half_width)
    return sel, s


def dead_ring(mesh: xr.Dataset, mp: xr.Dataset, when: str) -> pd.DataFrame:
    """Table 1: interior cells touching the wave boundary, and which carry no waves."""
    ff = mesh["mesh2d_face_faces"].values
    fy = mesh["mesh2d_face_y"].values
    swm = mp["snapwavemsk"].values
    bnd = np.where(swm == 2)[0]
    ring: dict[int, int] = {}
    for row in ff[bnd]:
        for k in row[np.isfinite(row)].astype(int):
            if swm[k] == 1:
                ring[k] = ring.get(k, 0) + 1  # number of boundary neighbours
    idx = np.array(sorted(ring))
    nbnd = np.array([ring[k] for k in idx])
    it = int(np.argmin(np.abs(mp["time"].values - np.datetime64(when))))
    h = mp["hm0"].isel(time=it).values[idx]
    f = np.hypot(mp["fwx"].isel(time=it).values[idx], mp["fwy"].isel(time=it).values[idx])
    dead = (h < 0.05) & (f < 1e-6)
    df = pd.DataFrame(
        {
            "region": np.where(fy[idx] < V1_5_SOUTH_LIMIT_Y, "south (v3 coast)", "north (v1.5 arms)"),
            "dead": dead,
            "n_boundary_neighbours": nbnd,
        }
    )
    out = df.groupby("region").agg(
        ring_cells=("dead", "size"),
        dead_cells=("dead", "sum"),
        dead_frac=("dead", "mean"),
        bnd_nbrs_dead=("n_boundary_neighbours", lambda v: v[df.loc[v.index, "dead"]].mean()),
        bnd_nbrs_live=("n_boundary_neighbours", lambda v: v[~df.loc[v.index, "dead"]].mean()),
    )
    out.loc["ALL"] = [
        len(df),
        int(df.dead.sum()),
        df.dead.mean(),
        df.n_boundary_neighbours[df.dead].mean(),
        df.n_boundary_neighbours[~df.dead].mean(),
    ]
    return out.round(3)


def transmission(mesh: xr.Dataset, mp: xr.Dataset) -> pd.DataFrame:
    """Table 2: first-interior shelf hm0 over imposed boundary hm0, per site and time."""
    fx, fy = mesh["mesh2d_face_x"].values, mesh["mesh2d_face_y"].values
    zb, swm, mt = mp["zb"].values, mp["snapwavemsk"].values, mp["time"].values
    rows = []
    for name, (lon, lat, az) in SITES.items():
        sel, _ = _strip(fx, fy, lon, lat, az)
        bnd = np.where(sel & (swm == 2))[0]
        inner = np.where(sel & (swm == 1) & np.isfinite(zb) & (zb < -8.5) & (zb > -9.8))[0]
        for tt in TIMES:
            it = int(np.argmin(np.abs(mt - np.datetime64(tt))))
            h = mp["hm0"].isel(time=it).values
            hb = float(np.nanmean(h[bnd])) if len(bnd) else np.nan
            hi = float(np.nanmean(h[inner])) if len(inner) else np.nan
            rows.append(
                dict(site=name, time=tt[5:16], n_bnd=len(bnd), n_inner=len(inner),
                     hm0_imposed=hb, hm0_inner=hi, ratio=hi / hb)
            )
    return pd.DataFrame(rows).round(2)


def setup_transects(mesh, mp_on, arm_on: Path, arm_off: Path) -> dict[str, pd.DataFrame]:
    """Table 3: waves-on minus waves-off water level along each transect."""
    fx, fy = mesh["mesh2d_face_x"].values, mesh["mesh2d_face_y"].values
    zb, mt = mp_on["zb"].values, mp_on["time"].values
    pre = (mt >= PRE[0]) & (mt <= PRE[1])
    pk = (mt >= PEAK[0]) & (mt <= PEAK[1])
    strips = {}
    for name, (lon, lat, az) in SITES.items():
        sel, s = _strip(fx, fy, lon, lat, az, half_width=100.0)
        idx = np.where(sel & np.isfinite(zb))[0]
        strips[name] = (idx, s[idx])
    allidx = np.unique(np.concatenate([v[0] for v in strips.values()]))
    z_on = C.zs_at_faces(arm_on, allidx)
    z_off = C.zs_at_faces(arm_off, allidx)
    hm0 = C.zs_at_faces(arm_on, allidx, var="hm0")
    pos = {f: i for i, f in enumerate(allidx)}
    out = {}
    for name, (idx, s) in strips.items():
        j = np.array([pos[f] for f in idx], dtype=int)
        with np.errstate(all="ignore"):
            df = pd.DataFrame(
                {
                    "bin_m": (s // 200 * 200).astype(int),
                    "zb": zb[idx],
                    "pre_setup": np.nanmean(z_on[pre][:, j] - z_off[pre][:, j], axis=0),
                    "peak_setup": np.nanmean(z_on[pk][:, j] - z_off[pk][:, j], axis=0),
                    "pre_hm0": np.nanmean(hm0[pre][:, j], axis=0),
                    "peak_hm0": np.nanmean(hm0[pk][:, j], axis=0),
                    "peak_wet": np.mean(np.isfinite(z_on[pk][:, j]), axis=0),
                }
            )
        g = df.groupby("bin_m").mean(numeric_only=True)
        out[name] = g[g.peak_wet > 0.05].round(3)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("run", type=Path, help="a waves-on run dir")
    ap.add_argument("--setup", type=Path, default=None,
                    help="the paired waves-off run dir; adds the cross-shore setup table")
    ap.add_argument("--ring-time", default="2012-10-30T00:00")
    args = ap.parse_args()
    pd.set_option("display.width", 200)
    pd.set_option("display.max_rows", 200)

    mesh = xr.open_dataset(args.run / "sfincs.nc")
    mp = xr.open_dataset(args.run / "sfincs_map.nc")

    print(f"== 1. DEAD RING at {args.ring_time} — interior cells touching the wave boundary "
          "with no hm0, no wave force")
    print(dead_ring(mesh, mp, args.ring_time).to_string())

    print("\n== 2. TRANSMISSION — shelf hm0 100–300 m inside the boundary / imposed hm0")
    print(transmission(mesh, mp).to_string(index=False))

    if args.setup is not None:
        print("\n== 3. SETUP TRANSECTS — waves-on minus waves-off zs (m), 200 m bins from 4 km "
              "offshore; pre-storm 10-28 06:00–10-29 12:00, peak 10-29 21:00–10-30 03:00")
        for name, df in setup_transects(mesh, mp, args.run, args.setup).items():
            print(f"\n-- {name}")
            print(df.to_string())


if __name__ == "__main__":
    main()
