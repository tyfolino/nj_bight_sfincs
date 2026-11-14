"""Look at one dike site at 1/9in CUDEM: bed (UTM 3 m), the over-reach region outline, the weir lines in view with
their written crests, the links the engine blocks (crests.npz), mesh faces by z_zmin, and the leak point.

    python -I site_view.py <tag> <lon> <lat> <half_m> <crests.npz> <weirfile> [<weirfile2> ...]

Also writes <tag>_cudem_utm3m.npz (bed window + transform) for hand-picking. Read-only on inputs."""
import sys
from pathlib import Path

import numpy as np
import geopandas as gpd
import pyproj
import rasterio
from affine import Affine
from rasterio.warp import reproject, Resampling
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

R = Path("/cache/home/tpj8/nj_bight_sfincs")
H = Path(__file__).resolve().parent
sys.path.insert(0, str(R / "logs/bed_audit_2026-11-05/checks/levee_continuity"))
import lib as Lb  # noqa: E402
from weir_on_mesh import read_weir  # noqa: E402

RUN = R / "experiments/v4_refreeze_swz_v11/p4-premier+weir-elizabeth-rahway"
tag, lon, lat, half = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
npz, wfs = sys.argv[5], sys.argv[6:]
cx, cy = pyproj.Transformer.from_crs(4326, 32618, always_xy=True).transform(lon, lat)
X0, X1, Y0, Y1 = cx - half, cx + half, cy - half, cy + half
res = 3.0
nx, ny = int(2 * half / res), int(2 * half / res)
dst = np.full((ny, nx), np.nan, np.float32)
dt = Affine(res, 0, X0, 0, -res, Y1)
src = R / ("data/elevation_v4/cudem_delaware_v4.vrt" if lon < -75.0 else "data/elevation_v3/cudem_nj_v3.vrt")
with rasterio.open(src) as r:
    reproject(rasterio.band(r, 1), dst, dst_transform=dt, dst_crs="EPSG:32618", resampling=Resampling.bilinear,
              dst_nodata=np.nan)
np.savez_compressed(H / f"{tag}_cudem_utm3m.npz", z=dst, transform=np.array(dt)[:6])
mesh = Lb.Mesh(RUN)
fig, ax = plt.subplots(figsize=(13, 12))
im = ax.imshow(dst, extent=(X0, X1, Y0, Y1), cmap="terrain", vmin=-1.5, vmax=3.5)
plt.colorbar(im, shrink=.6, label=f"{src.name} m NAVD88")
ax.contour(np.linspace(X0, X1, nx), np.linspace(Y1, Y0, ny), dst, levels=[0.6, 1.5], colors=["c", "r"],
           linewidths=.6)
s = np.where((mesh.fx > X0) & (mesh.fx < X1) & (mesh.fy > Y0) & (mesh.fy < Y1) & mesh.active)[0]
ax.scatter(mesh.fx[s], mesh.fy[s], c=mesh.z_zmin[s], s=6, cmap="terrain", vmin=-1.5, vmax=3.5, edgecolors="k",
           linewidths=.3)
d = np.load(npz)
eu, eh = d["eu"], d["eh"]
mx = .5 * (mesh.fx[mesh.nm[eu]] + mesh.fx[mesh.nmu[eu]])
my = .5 * (mesh.fy[mesh.nm[eu]] + mesh.fy[mesh.nmu[eu]])
k = (mx > X0) & (mx < X1) & (my > Y0) & (my < Y1)
for u, h in zip(eu[k], eh[k]):
    a, b = mesh.nm[u], mesh.nmu[u]
    ax.plot([mesh.fx[a], mesh.fx[b]], [mesh.fy[a], mesh.fy[b]], "-", c="r" if h < 0.9 else "k", lw=1.2)
cols = ["b", "m", "orange"]
for i, wf in enumerate(wfs):
    for name, rows in read_weir(wf):
        inb = (rows[:, 0] > X0) & (rows[:, 0] < X1) & (rows[:, 1] > Y0) & (rows[:, 1] < Y1)
        if not inb.any():
            continue
        ax.plot(rows[:, 0], rows[:, 1], "-", c=cols[i % 3], lw=1.5, label=f"{Path(wf).name}:{name}")
        for j in np.flatnonzero(inb)[::4]:
            ax.annotate(f"{rows[j, 2]:.2f}", rows[j, :2], fontsize=6, color=cols[i % 3])
reg = gpd.read_file(R / "logs/tidal_reach_2026-11-09/out/regions.gpkg", layer="region_polygons")
reg = reg[(reg.bed == "12") & (reg.kind == "over")].to_crs(32618).cx[X0:X1, Y0:Y1]
for g in reg.geometry:
    for p in getattr(g, "geoms", [g]):
        ax.plot(*np.array(p.exterior.coords)[:, :2].T, "y--", lw=1)
ax.plot(cx, cy, "rX", ms=14, label="leak")
ax.set_xlim(X0, X1)
ax.set_ylim(Y0, Y1)
ax.set_aspect("equal")
ax.legend(loc="lower left", fontsize=7)
ax.set_title(f"{tag}: contours 0.6 (cyan) / 1.5 m (red); links red = crest < 0.9")
out = H / f"{tag}_view.png"
fig.savefig(out, dpi=100, bbox_inches="tight")
print(out)
