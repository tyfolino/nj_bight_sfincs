"""Data for poster Figure 1 (the model domain), Model 1.1.0. Writes ``fig1_data.npz`` + CSVs.

    NJ_DOMAIN=v4_refreeze_swz_v11 python reports/poster_2026-11-13/fig1_prep.py   (via srun)

Reads the 1.1.0 run dir (read-only): ``sfincs.nc`` (face centres, ``level``, ``mask``),
``sfincs_netsrcdisfile.nc`` (61 inflows), ``sfincs.obs`` (48 gauge points), ``sfincs.weir``
(the structure lines). The active faces are binned onto a ~100 m lon/lat grid holding the
FINEST resolution present in each bin (a picture of the mesh, not the mesh itself).
"""

from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from pyproj import Transformer

import nj_sfincs  # noqa: F401
from nj_sfincs import premier
from nj_sfincs.config import exp_root

HERE = Path(__file__).resolve().parent
ARM = "p4-premier+weir-elizabeth-rahway"
LON = (-75.75, -73.70)
LAT = (38.70, 41.00)
DLON, DLAT = 0.0012, 0.0009  # ~100 m


def main():
    run = exp_root() / ARM
    fp = premier.fingerprint(run) if hasattr(premier, "fingerprint") else None
    print("fingerprint", fp)
    ds = xr.open_dataset(run / "sfincs.nc")
    x = ds["mesh2d_face_x"].values
    y = ds["mesh2d_face_y"].values
    lev = ds["level"].values
    msk = ds["mask"].values
    print("faces", x.size, "levels", np.unique(lev), "mask", np.unique(msk, return_counts=True))
    print("dx base", ds.attrs["dx"])
    act = msk > 0
    res = ds.attrs["dx"] / 2.0 ** (lev - 1)
    for L in np.unique(lev):
        print(f"  level {L}: {res[lev == L][0]:.0f} m, active {(act & (lev == L)).sum()}")
    tr = Transformer.from_crs(32618, 4326, always_xy=True)
    lon, lat = tr.transform(x[act], y[act])
    nx = int(round((LON[1] - LON[0]) / DLON))
    ny = int(round((LAT[1] - LAT[0]) / DLAT))
    ix = ((lon - LON[0]) / DLON).astype(int)
    iy = ((lat - LAT[0]) / DLAT).astype(int)
    ok = (ix >= 0) & (ix < nx) & (iy >= 0) & (iy < ny)
    grid = np.full((ny, nx), np.inf, dtype="float32")
    np.minimum.at(grid, (iy[ok], ix[ok]), res[act][ok].astype("float32"))
    grid[~np.isfinite(grid)] = np.nan
    forced = msk[act] == 2
    np.savez_compressed(
        HERE / "fig1_data.npz",
        grid=grid, lon0=LON[0], lat0=LAT[0], dlon=DLON, dlat=DLAT,
        forced_lon=np.asarray(lon)[forced], forced_lat=np.asarray(lat)[forced],
        n_faces=x.size, n_active=int(act.sum()),
        n_forced=int((msk == 2).sum()), n_outflow=int((msk == 3).sum()),
    )
    # inflows
    s = xr.open_dataset(run / "sfincs_netsrcdisfile.nc")
    slon, slat = tr.transform(s.x.values, s.y.values)
    pd.DataFrame(dict(lon=slon, lat=slat, qmax=s.discharge.max("time").values)).to_csv(
        HERE / "fig1_inflows.csv", index=False
    )
    # gauges
    obs = []
    for line in (run / "sfincs.obs").read_text().splitlines():
        p = line.split()
        if len(p) >= 3:
            gx, gy = float(p[0]), float(p[1])
            glon, glat = tr.transform(gx, gy)
            obs.append((" ".join(p[2:]).strip('"'), glon, glat))
    pd.DataFrame(obs, columns=["name", "lon", "lat"]).to_csv(
        HERE / "fig1_gauges.csv", index=False
    )
    # weir lines (tekal blocks: name / nrows ncols / rows of x y z ...)
    lines = (run / "sfincs.weir").read_text().splitlines()
    rows, i, k = [], 0, 0
    while i < len(lines):
        name = lines[i].strip()
        nr = int(lines[i + 1].split()[0])
        for j in range(nr):
            p = lines[i + 2 + j].split()
            wlon, wlat = tr.transform(float(p[0]), float(p[1]))
            rows.append((k, name, wlon, wlat))
        i += 2 + nr
        k += 1
    pd.DataFrame(rows, columns=["line", "name", "lon", "lat"]).to_csv(
        HERE / "fig1_weirs.csv", index=False
    )
    print("weir lines", k, "inflows", len(slon), "gauges", len(obs))


if __name__ == "__main__":
    main()
