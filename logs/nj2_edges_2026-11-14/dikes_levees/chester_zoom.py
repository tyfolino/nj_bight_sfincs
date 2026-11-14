"""Zoom on the Chester levee loop: CUDEM 1/9in in UTM (reprojected window), weir line(s), NLD route/leveed area, faces
coloured by z_zmin (1.1.0 subgrid). Args: <weirfile> [<weirfile2>]. Writes <stem>_zoom.png here. Read-only."""
import sys
from pathlib import Path
import numpy as np, geopandas as gpd, rasterio, netCDF4
from rasterio.warp import reproject, Resampling
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
R = Path("/cache/home/tpj8/nj_bight_sfincs"); H = Path(__file__).resolve().parent
sys.path.insert(0, str(R / "logs/refreeze_2026-10-06/structures")); from weir_on_mesh import read_weir
RUN = R / "experiments/v4_refreeze_swz_v11/p4-premier+weir-elizabeth-rahway"
X0, X1, Y0, Y1 = 467900, 469300, 4410900, 4411900
res = 3.0
nx, ny = int((X1 - X0) / res), int((Y1 - Y0) / res)
dst = np.full((ny, nx), np.nan, np.float32)
from affine import Affine
dt = Affine(res, 0, X0, 0, -res, Y1)
with rasterio.open(R / "data/elevation_v4/cudem_delaware_v4.vrt") as r:
    reproject(rasterio.band(r, 1), dst, dst_transform=dt, dst_crs="EPSG:32618", resampling=Resampling.bilinear, dst_nodata=np.nan)
np.save(H / "chester_cudem_utm3m.npy", dst)
fig, ax = plt.subplots(figsize=(13, 10))
im = ax.imshow(dst, extent=(X0, X1, Y0, Y1), cmap="terrain", vmin=-3, vmax=8); plt.colorbar(im, shrink=.6, label="CUDEM 1/9in m NAVD88")
cs = ax.contour(np.linspace(X0, X1, nx), np.linspace(Y1, Y0, ny), dst, levels=[0, 2, 4.5], colors=["c", "orange", "r"], linewidths=.7)
nc = netCDF4.Dataset(RUN / "sfincs.nc"); fx, fy, msk = (np.asarray(nc[k][:]) for k in ["mesh2d_face_x", "mesh2d_face_y", "mask"]); nc.close()
s = (fx > X0) & (fx < X1) & (fy > Y0) & (fy < Y1)
ax.scatter(fx[s], fy[s], s=3, c="k", alpha=.4)
la = gpd.read_file(R / "logs/walls_inventory_2026-11-04/walls_inventory.gpkg", layer="nld_leveed_areas").to_crs(32618)
for g in la[la.SYSTEM_ID == 4805000005].geometry:
    for p in getattr(g, "geoms", [g]): ax.plot(*np.array(p.exterior.coords)[:, :2].T, "y--", lw=2, label="NLD leveed area")
import xarray as xr
sx = xr.open_dataset(RUN / "sfincs_netsrcdisfile.nc")
cols = ["b", "m"]
for i, wf in enumerate(sys.argv[1:]):
    for name, rows in read_weir(wf):
        ax.plot(rows[:, 0], rows[:, 1], "-", c=cols[i], lw=2.5, label=Path(wf).name)
        ax.plot(rows[0, 0], rows[0, 1], "o", c=cols[i])
        for k in range(0, len(rows), 10): ax.annotate(f"{rows[k,2]:.1f}", rows[k, :2], fontsize=7, color=cols[i])
ax.set_xlim(X0, X1); ax.set_ylim(Y0, Y1); h, lb = ax.get_legend_handles_labels(); u = dict(zip(lb, h)); ax.legend(u.values(), u.keys(), loc="lower left")
ax.set_title("Chester: contours 0 (cyan) / 2 (orange) / 4.5 m (red)")
out = H / (Path(sys.argv[-1]).stem + "_zoom.png"); fig.savefig(out, dpi=100, bbox_inches="tight"); print(out)
