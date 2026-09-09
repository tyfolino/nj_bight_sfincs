#!/usr/bin/env python
"""Build the `BRACKET+setup-stockdon` water-level boundary: NACCS + Stockdon SETUP.

    PYTHONPATH=$PWD python scripts/build_stockdon_boundary.py [--beta-f 0.03] [--domain v3]

🔴 THIS PRODUCES AN INADMISSIBLE FORCING, ON PURPOSE (STATUS 2026-09-09, plan Track B).
FINDINGS §22: setup at the boundary XOR SnapWave — never both. FINDINGS §23: the NACCS
water level already carries the setup that accumulated seaward of its −10 m support depth.
Adding the SURF-ZONE setup term at the −10 m boundary lifts the whole shelf, so the
Atlantic City pier (matched to 6 mm on the premier) reads high by construction. The file
exists to put a CEILING on how much of the southern back-bay / HWM low bias a supplied
mean level can buy, in a waves-OFF run, scored into its own CSV. Never a candidate.

WHICH STOCKDON TERM, AND WHY
----------------------------
Stockdon (2006) splits runup into a SETUP `eta` (a rise of the mean water level inside the
surf zone) and a SWASH `S` (an oscillation about that mean)::

    eta = 0.35 * beta_f * sqrt(H0 * L0)        <- added here
    S   = sqrt((0.75*beta_f*sqrt(H0*L0))**2 + (0.06*sqrt(H0*L0))**2)   <- NOT added
    R2  = 1.1 * (eta + S/2)

Only `eta` is a water level; it is what SnapWave computes and what a waves-off run lacks.
The bias this bracket bounds is a 30 h pre-storm MEAN at gauges that never see swash, and a
bay cannot be lifted by an oscillation. Runup is judged OFFLINE on the open-coast marks
(`scripts/stockdon_envelope.py`), never written into a boundary.

H0 is deep-water height: CORA `hs` at the nearest node is reverse-shoaled from that node's
depth with `stockdon_envelope.deshoal` (linear theory). `L0 = g T^2 / 2 pi` from CORA `tp`.
Nodes shallower than `MIN_NODE_DEPTH_M` are skipped in the nearest-node search — inside
the surf zone `hs` is a broken height and H0 is undefined. Interior support points (the
Narrows, Arthur Kill, the Delaware Bay wedge) get small `eta` because CORA's waves there
are small; that is the physically right answer, not a screen.

Output: `data/gtsm/naccs_sandy_<domain>_stockdon<beta>.nc`, the as-built NACCS file plus
`eta(time, stations)`, with the beta, node ids, node depths and per-point peak eta in the
attrs. Registered in `data/data_catalog.yml` as `naccs_sandy_v3_stockdon03`.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import nj_sfincs  # noqa: E402,F401  (pyproj-before-hydromt import order)
from nj_sfincs import domain as _domain  # noqa: E402
from nj_sfincs.config import DATA  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stockdon_envelope import G, deshoal  # noqa: E402

#: CORA nodes shallower than this are inside/near the surf zone: `hs` there is a broken
#: height and Stockdon's H0 is undefined. Deeper nodes are reverse-shoaled to deep water.
MIN_NODE_DEPTH_M = 8.0
#: Farthest a support point may reach for a CORA node (the wave-boundary sampler's limit).
MAX_NODE_DIST_M = 15_000.0


def nearest_nodes(lon, lat, nlon, nlat, ndepth, min_depth):
    ok = np.isfinite(ndepth) & (ndepth >= min_depth)
    cands = np.where(ok)[0]
    coslat = np.cos(np.radians(lat))
    j = np.empty(len(lon), dtype=int)
    d = np.empty(len(lon))
    for i, (lo, la, c) in enumerate(zip(lon, lat, coslat)):
        dd = np.hypot((nlon[cands] - lo) * c, nlat[cands] - la) * 111_000.0
        k = int(np.argmin(dd))
        j[i], d[i] = cands[k], dd[k]
    return j, d


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--domain", default=os.environ.get("NJ_DOMAIN"))
    ap.add_argument("--beta-f", type=float, default=0.03,
                    help="foreshore slope (default 0.03, the value STATUS 09-08 used for "
                         "the 0.2-0.35 m theory numbers); eta scales linearly with it")
    ap.add_argument("--naccs", type=Path, default=None,
                    help="as-built NACCS boundary file (default gtsm/naccs_sandy_<domain>.nc)")
    ap.add_argument("--cora", type=Path, default=None,
                    help="CORA point file (default Domain.cora_waves)")
    ap.add_argument("--min-node-depth", type=float, default=MIN_NODE_DEPTH_M)
    args = ap.parse_args()
    if args.domain:
        os.environ["NJ_DOMAIN"] = args.domain
    dom = _domain.active()
    naccs = args.naccs or DATA / "gtsm" / f"naccs_sandy_{dom.name}.nc"
    cora = args.cora or dom.cora_waves
    tag = f"{args.beta_f:.2f}".replace("0.", "")  # 0.03 -> "03"
    out = DATA / "gtsm" / f"naccs_sandy_{dom.name}_stockdon{tag}.nc"
    if out.exists():
        sys.exit(f"refusing to overwrite {out} — delete it deliberately first")

    ds = xr.open_dataset(naccs).load()
    cw = xr.open_dataset(cora).load()
    lon, lat = ds["lon"].values, ds["lat"].values
    j, dist = nearest_nodes(lon, lat, cw["lon"].values, cw["lat"].values,
                            cw["depth"].values, args.min_node_depth)
    if dist.max() > MAX_NODE_DIST_M:
        sys.exit(f"a support point is {dist.max():.0f} m from its nearest CORA node "
                 f"(limit {MAX_NODE_DIST_M:.0f})")
    depth = cw["depth"].values[j]
    hs = cw["hs"].values[:, j]                      # (tc, stations)
    tp = cw["tp"].values[:, j]
    eta_c = np.zeros_like(hs)
    for i in range(hs.shape[1]):
        for k in range(hs.shape[0]):
            H, T = float(hs[k, i]), float(tp[k, i])
            if not (np.isfinite(H) and np.isfinite(T)) or H <= 0 or T <= 0:
                continue
            H0 = deshoal(H, T, float(depth[i]))
            if not np.isfinite(H0):
                continue
            L0 = G * T * T / (2 * math.pi)
            eta_c[k, i] = 0.35 * args.beta_f * math.sqrt(H0 * L0)
    # onto the NACCS clock (15 min); CORA is hourly and shorter — hold the end values
    tc = cw["time"].values.astype("datetime64[s]").astype("int64")
    tn = ds["time"].values.astype("datetime64[s]").astype("int64")
    eta = np.column_stack([np.interp(tn, tc, eta_c[:, i]) for i in range(eta_c.shape[1])])

    ds["waterlevel"] = (("time", "stations"), ds["waterlevel"].values + eta)
    ds["eta"] = (("time", "stations"), eta)
    ds["eta"].attrs.update(units="m", long_name="Stockdon setup added to waterlevel",
                           beta_f=args.beta_f)
    ds["waterlevel"].attrs.update(units="m", datum="NAVD88")
    ds.attrs.update(
        title=ds.attrs.get("title", "") + " + Stockdon setup (BRACKET, inadmissible)",
        bracket="setup-stockdon",
        inadmissible_why=("FINDINGS §22/§23: surf-zone setup imposed at the -10 m water-"
                          "level boundary, on top of the setup NACCS already carries at "
                          "that depth; lifts the whole shelf. UPPER bound only."),
        stockdon=(f"eta = 0.35*beta_f*sqrt(H0*L0), beta_f={args.beta_f}, H0 = CORA hs at "
                  f"the nearest node deeper than {args.min_node_depth} m reverse-shoaled "
                  "to deep water (linear theory), L0 = g*tp^2/2pi. Setup only — the swash "
                  "term S is NOT added (an oscillation is not a level)."),
        stockdon_source=str(cora),
        stockdon_node_ids=json.dumps([int(x) for x in j]),
        stockdon_node_depth_m=json.dumps([round(float(x), 1) for x in depth]),
        stockdon_node_dist_m=json.dumps([round(float(x)) for x in dist]),
        stockdon_eta_peak_m=json.dumps([round(float(x), 3) for x in eta.max(axis=0)]),
        stockdon_built=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        base_file=str(naccs),
    )
    win = (ds["time"] >= np.datetime64("2012-10-28T06:00")) & (ds["time"] <= np.datetime64("2012-10-29T12:00"))
    print(f"[stockdon] beta_f {args.beta_f}: {len(j)} points, nearest CORA node dist "
          f"median {np.median(dist):.0f} m max {dist.max():.0f} m, node depth "
          f"p5/p50/p95 {np.percentile(depth, [5, 50, 95]).round(1)}")
    print(f"[stockdon] eta: pre-storm (10-28 06 -> 10-29 12) mean over points "
          f"{float(ds['eta'][win].mean()):.3f} m; peak per point median "
          f"{np.median(eta.max(axis=0)):.3f} max {eta.max():.3f} m")
    arms = json.loads(ds.attrs.get("per_arm_coverage", "{}"))
    print(f"[stockdon] arms in the base file: {list(arms)}")
    tmp = out.with_suffix(".nc.tmp")
    ds.to_netcdf(tmp)
    tmp.replace(out)
    print(f"[out] wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
