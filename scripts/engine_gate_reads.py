"""Read a set of short engine-gate cuts against a control: setup, shelf, spikes, gauges.

    python scripts/engine_gate_reads.py --control G5_v233 --cuts G5_main_gammax2 D4_bds60 \
        [--root /scratch/tpj8/engine_gate] [--logs logs/engine_gate_2026-09-17] [--last-hours 6]

Promoted 2026-09-18 from the scratch reader of the G5 Galibier gate and the D4 spread cut
(STATUS 2026-09-18). Every cut must share the control's mesh and map time axis. Prints:

1. SHORELINE SETUP per shelf site (`wave_shelf_reference.SITES`): mean `zs` over the last
   N hours on SFINCS-active faces with mesh z in (-2, 0) m in an 8 km-wide strip, and the
   proxy setup = that minus the mean over the -9.8..-8.5 m shelf of the same strip (the
   tide and surge cancel; what is left is the breaking-driven lift).
2. WHERE IT GOES: the same shore-band mean `zs`, cut minus control, per HWM basin.
3. SHELF BAND |dhm0| per map hour on the open-coast -9 m band (SnapWave-interior faces,
   mesh z -9.8..-8.5, y <= 4,480,000, x >= 520,000, outside the NY bay box), with the
   cap-hit-free hours marked from `<logs>/convergence_<run>.csv` when present (the
   `snapwave_direction_check.py convergence` output; map hour h = SnapWave call 2h at
   the 30-min coupling), and a summary over the hours clean in BOTH runs. ⚠️ The p99 of
   |dhm0| is dominated by the control's own spikes even for a same-engine cut (1.5 m on
   D4); read the median and p50, and the per-site ratios from wave_shelf_reference.py.
4. SPIKES: max |dzs| vs the control, in the open ocean (z < -5, open-coast basins) and
   over all active faces, with the basins that carry |dzs| > 1 m.
5. GAUGES: `point_zs` cut minus control at every his station, last N hours and whole
   window.

🔴 `zb` is NaN on inactive faces and `da_dep` covers the whole rectangle (FINDINGS §37):
every selection here is on the mesh `z` from `sfincs.nc` and the map's own `msk`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from pyproj import Transformer

import nj_sfincs  # noqa: F401
from nj_sfincs import domain as _domain

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wave_shelf_reference import SITES, _strip  # noqa: E402

BAY_LL = (-74.32, -73.95, 40.40, 40.60)  # lon_min, lon_max, lat_min, lat_max
OPEN_COAST_BASINS = (
    "atlantic_oceanfront",
    "south_coast",
    "absecon_atlantic_city",
    "lbi_barrier",
    "cape_may",
    "great_egg",
    "barnegat_barrier",
    "manasquan",
    "shark_river",
)
KW = {"decode_times": {"timemax": False}}


def capfree_hours(logs: Path, run: str, n_hours: int) -> set[int]:
    """Map hours whose SnapWave call did not hit the iteration cap; all if no table."""
    f = logs / f"convergence_{run}.csv"
    if not f.exists():
        return set(range(n_hours))
    t = pd.read_csv(f)
    hit = t["cap_hit"].astype(str).str.lower().eq("true").values
    return {h for h in range(n_hours) if 2 * h < len(hit) and not hit[2 * h]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--control", required=True)
    ap.add_argument("--cuts", nargs="+", required=True)
    ap.add_argument("--root", type=Path, default=Path("/scratch/tpj8/engine_gate"))
    ap.add_argument("--logs", type=Path, default=None)
    ap.add_argument("--last-hours", type=float, default=6.0)
    a = ap.parse_args(argv)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 60)
    runs = [a.control] + list(a.cuts)
    dom = _domain.active()
    T = Transformer.from_crs(4326, dom.epsg, always_xy=True)
    Ti = Transformer.from_crs(dom.epsg, 4326, always_xy=True)
    mesh = xr.open_dataset(a.root / a.control / "sfincs.nc")
    z = mesh["z"].values.astype(float)
    fx, fy = mesh["mesh2d_face_x"].values, mesh["mesh2d_face_y"].values
    lon, lat = Ti.transform(fx, fy)
    maps = {r: xr.open_dataset(a.root / r / "sfincs_map.nc", **KW) for r in runs}
    times = maps[a.control]["time"].values
    for r in runs:
        if not (maps[r]["time"].values == times).all():
            raise SystemExit(f"{r}: map time axis differs from {a.control}")
    last = times >= times[-1] - np.timedelta64(int(a.last_hours * 3600), "s")
    msk = {r: maps[r]["msk"].values for r in runs}
    swm = maps[a.control]["snapwavemsk"].values
    active_all = np.all([msk[r] > 0 for r in runs], axis=0)
    basin = np.asarray(_domain.classify_hwm_basin(fx, fy, dom)).astype(str)
    bay = (lon > BAY_LL[0]) & (lon < BAY_LL[1]) & (lat > BAY_LL[2]) & (lat < BAY_LL[3])
    shore = active_all & (z > -2) & (z < 0)
    zs_last = {
        r: maps[r]["zs"].isel(time=np.where(last)[0]).mean("time").values for r in runs
    }
    print(
        f"=== 1. SHORELINE SETUP: mean zs over the last {a.last_hours:g} h "
        f"({str(times[last][0])[:16]} -> {str(times[-1])[:16]}), active faces z (-2,0);"
        " proxy setup = shore band - (-9.8..-8.5) shelf, same 8 km strip"
    )
    rows = []
    for name, (lo, la, az) in SITES.items():
        sel, _ = _strip(fx, fy, T, lo, la, az, length=80_000.0, half=4000.0)
        sh = sel & shore
        shelf = sel & active_all & (z < -8.5) & (z > -9.8)
        row = dict(site=name, n_shore=int(sh.sum()), n_shelf=int(shelf.sum()))
        for r in runs:
            m1, m2 = np.nanmean(zs_last[r][sh]), np.nanmean(zs_last[r][shelf])
            row[f"zs_{r}"] = round(m1, 3)
            row[f"setup_{r}"] = round(m1 - m2, 3)
        rows.append(row)
    print(pd.DataFrame(rows).to_string(index=False))

    print("\n=== 2. WHERE IT GOES: shore-band mean zs per HWM basin; d = cut - control")
    rows = []
    for b in sorted(set(basin[shore])):
        sh = shore & (basin == b)
        row = dict(
            basin=b,
            n=int(sh.sum()),
            zs_ctl=round(np.nanmean(zs_last[a.control][sh]), 3),
        )
        for r in a.cuts:
            d = zs_last[r][sh] - zs_last[a.control][sh]
            row[f"d_{r}"] = round(np.nanmean(d), 3)
            row[f"d_p90_{r}"] = round(np.nanpercentile(np.abs(d), 90), 3)
        rows.append(row)
    print(pd.DataFrame(rows).to_string(index=False))

    print(
        "\n=== 3. SHELF BAND |dhm0| per hour, open-coast -9 m band; ok = cap-hit-free in both"
    )
    band = (
        (swm == 1)
        & (z < -8.5)
        & (z > -9.8)
        & ~bay
        & (fx >= 520_000)
        & (fy <= 4_480_000)
    )
    print("n band faces", int(band.sum()))
    logs = a.logs or Path(".")
    free = {r: capfree_hours(logs, r, len(times)) for r in runs}
    h0 = {r: maps[r]["hm0"].values[:, band] for r in runs}
    rows = []
    for i, t in enumerate(times):
        row = dict(
            hour=i, t=str(t)[5:16], hm0_ctl=round(np.nanmedian(h0[a.control][i]), 3)
        )
        for r in a.cuts:
            d = h0[r][i] - h0[a.control][i]
            row[f"{r}_med"] = round(np.nanmedian(d), 3)
            row[f"{r}_p99abs"] = round(np.nanpercentile(np.abs(d), 99), 3)
            row[f"{r}_ok"] = (i in free[a.control]) and (i in free[r])
        rows.append(row)
    print(pd.DataFrame(rows).to_string(index=False))
    for r in a.cuts:
        hrs = sorted(free[a.control] & free[r])
        if not hrs:
            print(f"{r}: no hour clean in both")
            continue
        d = np.concatenate([h0[r][i] - h0[a.control][i] for i in hrs])
        d = d[np.isfinite(d)]
        ad = np.abs(d)
        print(
            f"{r}: clean hours {hrs}: median d {np.median(d):+.3f}, |d| p50 "
            f"{np.percentile(ad, 50):.3f} p90 {np.percentile(ad, 90):.3f} p99 "
            f"{np.percentile(ad, 99):.3f}, frac |d|>0.05: {(ad > 0.05).mean():.2f}"
        )

    print("\n=== 4. SPIKES: |dzs| vs control (all hours)")
    ocean = active_all & (z < -5) & ~bay & np.isin(basin, OPEN_COAST_BASINS)
    zs_ctl = maps[a.control]["zs"].values
    for r in a.cuts:
        d = np.abs(maps[r]["zs"].values - zs_ctl)
        d[:, ~active_all] = np.nan
        k = np.unravel_index(np.nanargmax(d), d.shape)
        j = k[1]
        print(
            f"{r}: max|dzs| {np.nanmax(d):.2f} m at hour {k[0]} lon {lon[j]:.4f} lat "
            f"{lat[j]:.4f} z {z[j]:.1f} basin {basin[j]}; all active n>1.0 "
            f"{int(np.nansum(d > 1.0))} n>0.5 {int(np.nansum(d > 0.5))}"
        )
        o = d[:, ocean]
        print(
            f"   open ocean (n {int(ocean.sum())}): max {np.nanmax(o):.2f}, n>0.5 "
            f"{int(np.nansum(o > 0.5))} cell-h, n>1.0 {int(np.nansum(o > 1.0))}, "
            f"p99 {np.nanpercentile(o, 99):.3f}"
        )
        big = np.nansum(d > 1.0, axis=0) > 0
        if big.any():
            vc = pd.Series(basin[big]).value_counts().head(6)
            print("   faces with |dzs|>1 at any hour, by basin:", dict(vc))

    print(
        f"\n=== 5. GAUGES: point_zs cut - control, last {a.last_hours:g} h and whole window"
    )
    his = {r: xr.open_dataset(a.root / r / "sfincs_his.nc", **KW) for r in runs}
    names = [
        str(n.decode() if isinstance(n, bytes) else n).strip()
        for n in his[a.control]["station_name"].values
    ]
    th = his[a.control]["time"].values
    lh = th >= th[-1] - np.timedelta64(int(a.last_hours * 3600), "s")
    rows = []
    for si, n in enumerate(names):
        c = his[a.control]["point_zs"].values[:, si]
        row = dict(station=n, zs_ctl_last=round(np.nanmean(c[lh]), 3))
        for r in a.cuts:
            d = his[r]["point_zs"].values[:, si] - c
            row[f"{r}_mean"] = round(np.nanmean(d[lh]), 3)
            row[f"{r}_maxabs"] = round(np.nanmax(np.abs(d[lh])), 3)
            row[f"{r}_maxall"] = round(np.nanmax(np.abs(d)), 3)
        rows.append(row)
    print(pd.DataFrame(rows).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
