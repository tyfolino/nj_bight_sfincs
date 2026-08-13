"""Build a CORA SWAN wave-boundary forcing file for the SnapWave support points.

WHY THIS EXISTS
---------------
The premier feeds SnapWave from ERA5, and that has two observation-confirmed defects
(see project memory / project_cora_evaluation):

1. **No shelf transformation.** The support points sit at z ~ -10 m, but ERA5 is a
   deep-water product. At Sandy's peak (2012-10-30 00:00) NDBC 44025 measured 7.80 m
   in 36 m of water while ERA5 imposes 7.82 m in 10 m of water — the same sea state,
   26 m of depth too shallow. CORA's SWAN resolves the shelf and says 5.07-6.02 m there.
2. **No alongshore structure.** ERA5's 31 km cell cannot resolve a 25 km boundary, so
   `add_waves` takes ONE node and hands byte-identical Hs to all 7 support points. CORA
   carries up to 1.38 m of alongshore spread (Sandy Hook / Long Island shadowing).

This script writes `data/waves/cora_waves_nj.nc` as an UNSTRUCTURED POINT dataset —
(time, node) with lon/lat coords — covering the offshore edge of the active domain, so
`model.add_waves` can give every support point its own nearest CORA node.

WHAT THIS DOES NOT DO
---------------------
It does NOT touch water levels. CORA was evaluated as a water-level source and REJECTED
(tide late by +6..+24 min, levels 0.14-0.31 m low). This is the wave boundary only.

Access is anonymous kerchunk-over-S3: each `*_map.zarr` is a single ~400 KB reference
JSON pointing at the real chunks, so it must be opened through fsspec's `reference`
filesystem, NOT as a plain zarr store (which fails with GroupNotFoundError). Both
`asynchronous=True` flags are required or zarr3 raises "Reference-FS's target filesystem
must have same value of asynchronous".

Run:
    NJ_ROOT=$PWD NJ_DOMAIN=v2_barnegat PYTHONPATH=$PWD \
        micromamba/envs/sfincs/bin/python scripts/build_cora_waves.py
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

import nj_sfincs  # noqa: F401  (PROJ primer — must precede any geo import)
from nj_sfincs import domain as _domain

S3_BASE = "s3://noaa-nos-cora-pds/cora_gec/native_grid/waves/zarr"
YEAR = 2012

#: CORA variable -> the name SnapWave forcing uses. `swan_TPS` is the smoothed peak
#: period (SWAN's TPS output), `swan_DIR` the mean wave direction in nautical degrees,
#: which is the same convention snapwave.bwd expects.
VARS = {"swan_HS": "hs", "swan_TPS": "tp", "swan_DIR": "wd"}

#: Window: the run is 10-28 -> 10-31, padded a day either side so interpolation onto
#: the model clock never has to extrapolate at an endpoint.
T0 = datetime(2012, 10, 27)
T1 = datetime(2012, 11, 1)

#: How far offshore of the domain to keep CORA nodes. The support points sit ON the
#: domain's seaward edge, so a modest pad is enough to guarantee every one of them has
#: a CORA node seaward of it as well as landward.
PAD_DEG = 0.35


def open_ref(url: str):
    """Open one CORA kerchunk reference store as an xarray Dataset."""
    import fsspec
    import xarray as xr

    fs = fsspec.filesystem(
        "reference",
        fo=url,
        remote_protocol="s3",
        asynchronous=True,
        remote_options={"anon": True, "asynchronous": True},
        target_options={"anon": True},
    )
    return xr.open_dataset(
        fs.get_mapper(""), engine="zarr",
        backend_kwargs={"consolidated": False}, chunks={},
    )


def main() -> int:
    import xarray as xr

    dom = _domain.active()
    w, s, e, n = dom.bbox_ll()
    # Only pad SEAWARD (east) and alongshore (n/s). Padding west would pull in nodes up
    # rivers and inside the bays, where CORA's own coastal resolution is poor and a
    # nearest-node lookup could hand a support point an estuarine sea state.
    box = (w, s - PAD_DEG, e + PAD_DEG, n + PAD_DEG)
    print(f"domain {dom.name}  bbox {dom.bbox_ll()}")
    print(f"CORA node search box (W,S,E,N) = {box}")

    out = _domain.DATA / "waves" / "cora_waves_nj.nc"

    # ── locate the nodes once, from the cheap coordinate arrays ──────────────
    print(f"\nopening {S3_BASE}/swan_HS.63_{YEAR}_map.zarr ...")
    ds0 = open_ref(f"{S3_BASE}/swan_HS.63_{YEAR}_map.zarr")
    x = np.asarray(ds0["x"].values, float)
    y = np.asarray(ds0["y"].values, float)
    x = np.where(x > 180, x - 360, x)
    depth = np.asarray(ds0["depth"].values, float)
    print(f"  mesh: {x.size:,} nodes, {ds0.sizes['time']:,} timesteps")

    inbox = (x >= box[0]) & (x <= box[2]) & (y >= box[1]) & (y <= box[3])
    # SnapWave support points are offshore and submerged; a node that CORA has dry or
    # nearly so would inject a meaningless sea state. Positive `depth` is below datum
    # in the ADCIRC convention.
    wet = depth > 2.0
    keep = np.flatnonzero(inbox & wet)
    print(f"  in box: {inbox.sum():,}   in box AND depth>2 m: {keep.size:,}")
    if keep.size == 0:
        print("!! no CORA nodes selected — check the box/convention", file=sys.stderr)
        return 1
    print(f"  kept-node depth  min {depth[keep].min():.1f} m  "
          f"max {depth[keep].max():.1f} m  median {np.median(depth[keep]):.1f} m")

    tsel = slice(np.datetime64(T0), np.datetime64(T1))

    data = {}
    for cora_var, short in VARS.items():
        url = f"{S3_BASE}/{cora_var}.63_{YEAR}_map.zarr"
        print(f"\npulling {cora_var} ...")
        ds = ds0 if cora_var == "swan_HS" else open_ref(url)
        da = ds[cora_var].sel(time=tsel).isel(node=keep)
        arr = np.asarray(da.values, np.float32)
        print(f"  {cora_var}: shape {arr.shape}  "
              f"finite {np.isfinite(arr).sum():,}/{arr.size:,}  "
              f"min {np.nanmin(arr):.2f}  max {np.nanmax(arr):.2f}")
        data[short] = arr
        if cora_var == "swan_HS":
            times = da["time"].values

    # Drop any node that is not finite at EVERY timestep in every variable. SnapWave
    # forcing is looked up by nearest node, and a nearest-node lookup has no way to
    # notice it landed on a NaN — it would write NaN into snapwave.bhs and the solver
    # would take it. Cheaper to make the file incapable of expressing the problem.
    good = np.ones(data["hs"].shape[1], bool)
    for short, arr in data.items():
        good &= np.isfinite(arr).all(axis=0)
    if not good.all():
        print(f"\ndropping {int((~good).sum())} node(s) with any non-finite value "
              f"({int(good.sum())} kept)")
        keep = keep[good]
        data = {k: v[:, good] for k, v in data.items()}

    ds_out = xr.Dataset(
        {k: (("time", "node"), v) for k, v in data.items()},
        coords={
            "time": times,
            "lon": ("node", x[keep].astype("float64")),
            "lat": ("node", y[keep].astype("float64")),
            "depth": ("node", depth[keep].astype("float32")),
        },
        attrs={
            "title": "NOAA CORA (NOMAD v1e) SWAN wave parameters — SnapWave boundary forcing",
            "source": f"{S3_BASE} ({YEAR} map files, kerchunk/zarr, anonymous S3)",
            "mesh": str(ds0.attrs.get("agrid", "NOMAD v1e")),
            "domain": dom.name,
            "note": (
                "Wave boundary ONLY. CORA was evaluated and REJECTED as a water-level "
                "forcing source (tide late +6..+24 min, levels 0.14-0.31 m low); it is "
                "used here because its SWAN resolves the shelf that ERA5 does not."
            ),
            "created_by": "scripts/build_cora_waves.py",
        },
    )
    for v, u, ln in (("hs", "m", "significant wave height"),
                     ("tp", "s", "smoothed peak period (SWAN TPS)"),
                     ("wd", "degrees", "mean wave direction (nautical)")):
        ds_out[v].attrs = {"units": u, "long_name": ln}

    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".nc.tmp")
    ds_out.to_netcdf(tmp)
    os.replace(tmp, out)  # atomic: a truncated forcing file reads back CLEAN
    print(f"\nwrote {out}  ({out.stat().st_size/1e6:.1f} MB, "
          f"{ds_out.sizes['node']} nodes x {ds_out.sizes['time']} times)")

    print("\npeak Hs by node (top 5):")
    pk = np.nanmax(data["hs"], axis=0)
    for i in np.argsort(pk)[-5:][::-1]:
        print(f"  lon {x[keep][i]:8.3f} lat {y[keep][i]:7.3f} "
              f"depth {depth[keep][i]:6.1f} m  peak Hs {pk[i]:.2f} m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
