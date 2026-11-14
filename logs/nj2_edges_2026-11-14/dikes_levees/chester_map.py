"""Chester (PA) levee: the 11-12 candidate line, the NLD route + leveed area, discharge source 26 (Chester Creek), the
1.1.0 mesh faces, on 1/9" CUDEM. Read-only. Writes chester_map.png + chester_context.json here.
    source logs/weirs_dikes_levees_2026-11-12/env.sh; python -I logs/nj2_edges_2026-11-14/dikes_levees/chester_map.py"""
import json
import sys
from pathlib import Path

import numpy as np
import geopandas as gpd
import xarray as xr
import rasterio
import pyproj
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

R = Path("/cache/home/tpj8/nj_bight_sfincs")
H = Path(__file__).resolve().parent
RUN = R / "experiments/v4_refreeze_swz_v11/p4-premier+weir-elizabeth-rahway"
sys.path.insert(0, str(R / "logs/refreeze_2026-10-06/structures"))
from weir_on_mesh import read_weir  # noqa: E402

T = pyproj.Transformer.from_crs(32618, 4326, always_xy=True)
wf = sys.argv[1] if len(sys.argv) > 1 else str(R / "logs/weirs_dikes_levees_2026-11-12/cand_chester.weir")
lines = read_weir(wf)
s = xr.open_dataset(RUN / "sfincs_netsrcdisfile.nc")
sx, sy = s.x.values, s.y.values
qmax = s.discharge.max("time").values
routes = gpd.read_file(R / "logs/walls_inventory_2026-11-04/walls_inventory.gpkg", layer="nld_routes")
rt = routes[routes.system_id.astype(str).str.startswith("4805000005")].to_crs(32618)
la = gpd.read_file(R / "logs/walls_inventory_2026-11-04/walls_inventory.gpkg", layer="nld_leveed_areas").to_crs(32618)
la = la[la.SYSTEM_ID == 4805000005]
allxy = np.vstack([np.asarray(l[1])[:, :2] for l in lines])
x0, y0 = allxy.min(0) - 900
x1, y1 = allxy.max(0) + 900
x0 = min(x0, sx[26] - 300)
y1 = max(y1, sy[26] + 300)
lon0, lat0 = T.transform(x0, y0)
lon1, lat1 = T.transform(x1, y1)
with rasterio.open(R / "data/elevation_v4/cudem_delaware_v4.vrt") as r:
    w = rasterio.windows.from_bounds(min(lon0, lon1), min(lat0, lat1), max(lon0, lon1), max(lat0, lat1), r.transform)
    z = r.read(1, window=w, masked=True)
    tr = r.window_transform(w)
import netCDF4  # noqa: E402

nc = netCDF4.Dataset(RUN / "sfincs.nc")
fx, fy, msk, lev = (np.asarray(nc[k][:]) for k in ["mesh2d_face_x", "mesh2d_face_y", "mask", "level"])
nc.close()
sel = (fx > x0) & (fx < x1) & (fy > y0) & (fy < y1)
Tf = pyproj.Transformer.from_crs(32618, 4326, always_xy=True)
flo, fla = Tf.transform(fx[sel], fy[sel])
fig, ax = plt.subplots(figsize=(11, 11))
ext = (tr.c, tr.c + tr.a * z.shape[1], tr.f + tr.e * z.shape[0], tr.f)
im = ax.imshow(z, extent=ext, cmap="terrain", vmin=-4, vmax=8)
plt.colorbar(im, ax=ax, shrink=0.6, label="CUDEM 1/9in, m NAVD88")
ax.scatter(flo, fla, s=2, c=np.where(msk[sel] > 0, "k", "r"), alpha=0.3)
for g in rt.geometry.explode():
    lo, la_ = Tf.transform(*np.array(g.coords)[:, :2].T)
    ax.plot(lo, la_, "m-", lw=4, alpha=0.5, label="NLD route")
for g in la.geometry:
    for p in getattr(g, "geoms", [g]):
        lo, la_ = Tf.transform(*np.array(p.exterior.coords)[:, :2].T)
        ax.plot(lo, la_, "y--", lw=1.5, label="NLD leveed area")
for l in lines:
    xy = np.asarray(l[1])
    lo, la_ = Tf.transform(xy[:, 0], xy[:, 1])
    ax.plot(lo, la_, "b-", lw=2, label="weir line")
    ax.plot(lo[0], la_[0], "bo")
near = np.flatnonzero(np.hypot(sx - sx[26], sy - sy[26]) < 4000)
for k in near:
    lo, la_ = Tf.transform(sx[k], sy[k])
    ax.plot(lo, la_, "r*", ms=16)
    ax.annotate(f"src {k} Q {qmax[k]:.1f}", (lo, la_), color="r", fontsize=10)
ax.set_xlim(min(lon0, lon1), max(lon0, lon1))
ax.set_ylim(min(lat0, lat1), max(lat0, lat1))
h, lb = ax.get_legend_handles_labels()
u = dict(zip(lb, h))
ax.legend(u.values(), u.keys(), loc="lower right")
ax.set_title(Path(wf).name)
out = H / (Path(wf).stem + "_map.png")
fig.savefig(out, dpi=110, bbox_inches="tight")
print(out)
json.dump(dict(src26=[float(sx[26]), float(sy[26])], src26_lonlat=Tf.transform(sx[26], sy[26]), q26=float(qmax[26]),
               near_sources=[int(k) for k in near],
               route=[np.round(np.array(g.coords)[:, :2], 1).tolist() for g in rt.geometry.explode()],
               leveed_area_km2=float(la.area.sum() / 1e6)), open(H / "chester_context.json", "w"))
