"""Bed / fill-to-harbour / tier panels around a site (planned 2012 bed, 2.5 m). usage: fig_site.py name lon lat half_m"""
import sys
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, numpy as np, rasterio
from pyproj import Transformer
D = Path("/scratch/tpj8/tmp/nj2_decks_2026-11-14"); L = Path(__file__).parent / "fig"; L.mkdir(exist_ok=True)
name, lon, lat, H = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
x, y = Transformer.from_crs(4326, 32618, always_xy=True).transform(lon, lat)
def win(p):
    with rasterio.open(p) as s:
        T = s.transform; c0 = int((x - H - T.c) / 2.5); r0 = int((T.f - y - H) / 2.5); n = int(2 * H / 2.5)
        return s.read(1, window=((r0, r0 + n), (c0, c0 + n))).astype("f4")
z, zb, F = win(D / "planned_2012.tif"), win(D / "base_v11c.tif"), win(D / "fill_planned_2012.tif")
F[np.isinf(F)] = np.nan
ext = (-H, H, -H, H)
fig, ax = plt.subplots(1, 3, figsize=(18, 6), constrained_layout=True)
for a, A, t, kw in ((ax[0], zb, "base v1.1c bed (m NAVD88)", dict(cmap="terrain", vmin=-6, vmax=6)),
                    (ax[1], z, "planned 2012 bed", dict(cmap="terrain", vmin=-6, vmax=6)),
                    (ax[2], F, "fill level to harbour (m)", dict(cmap="magma", vmin=-2, vmax=3))):
    im = a.imshow(A, extent=ext, **kw); a.set_title(t); fig.colorbar(im, ax=a, shrink=0.8)
    a.contour(np.flipud(z), levels=[0.7], colors="c", linewidths=0.6, extent=ext)
fig.suptitle(f"{name}  ({lat:.5f}, {lon:.5f})  cyan = 0.70 m (MHHW) on the planned bed; axes m from centre")
fig.savefig(L / f"{name}.png", dpi=70)
