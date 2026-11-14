"""Shoreline (shape) check on the spit + the one figure.
python logs/sandy_hook_motf_2026-11-14/shape_and_figure.py"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os

import numpy as np
from matplotlib.colors import ListedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle
from scipy import ndimage

HERE = Path(__file__).resolve().parent
KM2 = 15 * 15 / 1e6
TAG = os.environ.get("TAG", "v11")
z = np.load(HERE / ("sh_window.npz" if TAG == "v11" else f"sh_window_{TAG}.npz"))
c, lon, lat, bed = z["cls"], z["lon"], z["lat"], z["bed"]
cz, ep, mo = z["czmil_2012_11_16"], z["eaarl_pre_2012_10_26"], z["motf"]
valid = z["valid"]

# the spit = the bed-land component through the Hook, grown 300 m (20 px) to take in
# the shoreface on both sides; cut at the Gateway line 40.393
land = np.isfinite(bed) & (bed > 0)
lab, _ = ndimage.label(land, structure=np.ones((3, 3)))
i = np.unravel_index(np.argmin((lat - 40.455) ** 2 + ((lon + 73.995) * 0.76) ** 2), lat.shape)
spit = ndimage.binary_dilation(lab == lab[i], iterations=20) & (lat >= 40.393)
spit &= ~((lon < -73.9805) & (lat < 40.412))  # keep Highlands out
both = spit & np.isfinite(cz) & np.isfinite(bed)
print(f"spit zone {spit.sum()*KM2:.2f} km2; CZMIL covers {both.sum()/spit.sum():.0%}")
gain = both & (bed > 0) & (cz <= 0)
loss = both & (bed <= 0) & (cz > 0)
print(f"bed LAND where CZMIL 2012-11-16 is water (<=0 m): {gain.sum()*KM2:.3f} km2; classes "
      + ", ".join(f"{n} {int((c[gain]==k).sum())*KM2:.3f}" for k, n in ((1,'hit'),(2,'miss'),(3,'FA'),(4,'dry'),(5,'invalid'))))
print(f"bed WATER where CZMIL 2012-11-16 is land (>0 m): {loss.sum()*KM2:.3f} km2; MOTF wet there "
      f"{int((mo[loss]==1).sum())*KM2:.3f} km2 (unscored: bed <= 0)")
be = spit & np.isfinite(ep) & np.isfinite(bed)
g2 = be & (bed > 0) & (ep <= 0)
l2 = be & (bed <= 0) & (ep > 0)
print(f"vs EAARL pre 2012-10-26 (first surface, covers {be.sum()/spit.sum():.0%}): bed land/EAARL water "
      f"{g2.sum()*KM2:.3f} km2 (FA {int((c[g2]==3).sum())*KM2:.3f}); bed water/EAARL land {l2.sum()*KM2:.3f} km2")
# MOTF wet over ground the bed calls water (the MOTF polygon's own 2012-ish shoreline)
mw = spit & (mo == 1) & np.isfinite(bed) & (bed <= 0)
print(f"MOTF wet but bed <= 0 (not scored): {mw.sum()*KM2:.3f} km2; of it CZMIL>0 {int((mw & (cz>0)).sum())*KM2:.3f}")
for k, n in ((3, "FA"), (2, "miss")):
    s = spit & (c == k)
    print(f"{n} on spit zone {s.sum()*KM2:.3f} km2: bed p50 {np.nanmedian(bed[s]):.2f}; "
          f"tip (lat>40.476) {int((s & (lat > 40.476)).sum())*KM2:.3f}; "
          f"within 60 m of the bed's 0 m line {int((s & ndimage.binary_dilation(~land, iterations=4)).sum())*KM2:.3f}")

# ---- figure
fig, ax = plt.subplots(figsize=(7.5, 9.5), dpi=150)
cols = ["white", "#2b8cbe", "#fdae61", "#d7191c", "#d9d9d9", "#9e9ac8", "white"]
show = np.where(lat >= 40.385, c, 0)
ext = [z["X"].min() - 7.5, z["X"].max() + 7.5, z["Y"].min() - 7.5, z["Y"].max() + 7.5]
ax.imshow(show, cmap=ListedColormap(cols), vmin=-0.5, vmax=6.5, extent=ext, interpolation="nearest")
X, Y = z["X"], z["Y"]
for arr, col, ls, lw in ((bed, "k", "-", 0.8), (cz, "#00a650", "-", 0.8)):
    a = np.where(np.isfinite(arr), arr, -5)
    ax.contour(X, Y, a, levels=[0.0], colors=col, linestyles=ls, linewidths=lw)
    ax.contour(X, Y, a, levels=[0.6], colors=col, linestyles=":", linewidths=lw)
ax.contour(X, Y, np.where(valid == 1, 1, 0), levels=[0.5], colors="#7a0177", linewidths=0.6, linestyles="--")
ax.set_xlim(582800, 588200); ax.set_ylim(4471300, 4482000)
ax.set_xlabel("UTM 18N easting, m"); ax.set_ylabel("northing, m")
ax.set_title({"v11": "Sandy Hook: MOTF classes, 1.1.0 (2012 bed, native floodmap)", "bed2026": "Sandy Hook: MOTF classes, Sandy on the 2026 bed (bed-modernb premier)"}[TAG], fontsize=10)
h = [Patch(color=cols[1], label="hit"), Patch(color=cols[2], label="miss"),
     Patch(color=cols[3], label="false alarm"), Patch(color=cols[4], label="correct dry"),
     Patch(color=cols[5], label="off MOTF validity raster"),
     Line2D([], [], color="k", lw=0.8, label="model bed (scoring raster) 0 m / 0.6 m dotted"),
     Line2D([], [], color="#00a650", lw=0.8, label="CZMIL 2012-11-16 0 m / 0.6 m"),
     Line2D([], [], color="#7a0177", lw=0.6, ls="--", label="validity raster edge")]
ax.legend(handles=h, loc="upper right", fontsize=7, framealpha=0.9)
ax.tick_params(labelsize=7)
fig.tight_layout()
fig.savefig(HERE / f"sandy_hook_motf_classes_{TAG}.png")
print("figure", HERE / f"sandy_hook_motf_classes_{TAG}.png")
