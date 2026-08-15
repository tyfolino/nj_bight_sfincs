#!/usr/bin/env python
"""Ward Point / Tottenville: the drawn ring against CUDEM and against CoNED.

    python scripts/plot_ward_point_bed.py       # -> reports/figures/ward_point_ring_vs_cudem.png

WHY THIS EXISTS
---------------
On 2026-08-13 the `arthur_kill` arm came out as two disconnected runs and the cause was
recorded as "the ring cuts a corner across open water south of Ward Point", with an
instruction to drag three hand-drawn vertices north onto the shore. **That was wrong.**
`cudem_nj` is MISSING the Ward Point headland: its southernmost land cell sits at lat
40.49982 in every column across ~800 m — a straight line of constant latitude, which is not
a thing coastlines do — and it backfills the missing ~230 m of New York State as −3 to
−5.5 m of bay. Ward Point is the southernmost point of NY at ~40.4961 N.

Nothing asserted this. Every domain invariant was green. It was caught by putting the ring
on top of the bed and LOOKING, which is why this script is in the repo rather than in a
scratch directory: the figure is cited from docs/STATUS.md and has to stay regenerable.

🔴 The lesson generalises past this one headland. A wet-reach validator that reads the same
elevation stack the model reads cannot corroborate the model's bed — it inherits the same
hole. Only an INDEPENDENT product can, which is what the CoNED panel is.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import rasterio  # noqa: E402
import yaml  # noqa: E402
from rasterio.windows import from_bounds  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from validate_region_v1_5 import load_ring  # noqa: E402

#: The box is deliberately a coordinate literal, not derived from the ring: the point is to
#: show ground the ring does NOT cover.
LON0, LON1 = -74.268, -74.222
LAT0, LAT1 = 40.489, 40.512

CONED = ROOT / "data" / "elevation_v1_5" / "coned" / "NJ_DE_Topobathy_DEM_v2_10_20.tif"
OUT = ROOT / "reports" / "figures" / "ward_point_ring_vs_cudem.png"


def _grid_from(src, lons, lats):
    """Sample `src` on a lon/lat mesh, reprojecting the query points if it is not
    geographic. Returns NaN outside coverage."""
    from pyproj import Transformer

    lo, la = np.meshgrid(lons, lats)
    pts = np.c_[lo.ravel(), la.ravel()]
    epsg = src.crs.to_epsg() if src.crs is not None else None
    if epsg not in (4326, 4269, 5498, None):
        t = Transformer.from_crs(4326, src.crs, always_xy=True)
        x, y = t.transform(pts[:, 0], pts[:, 1])
        pts = np.c_[x, y]
    z = np.array([v[0] for v in src.sample([tuple(p) for p in pts])], dtype="float64")
    z[(z < -9000) | ~np.isfinite(z)] = np.nan
    return z.reshape(len(lats), len(lons))


def _panel(ax, lons, lats, z, ring, title):
    land = np.where(z > 0, z, np.nan)
    water = np.where(z <= 0, z, np.nan)
    ax.pcolormesh(lons, lats, water, cmap="Blues_r", vmin=-12, vmax=0, shading="nearest")
    ax.pcolormesh(lons, lats, land, cmap="terrain", vmin=-5, vmax=40, shading="nearest")
    if np.isfinite(z).any():
        ax.contour(lons, lats, np.nan_to_num(z, nan=-999), levels=[0.0], colors="white",
                   linewidths=1.6)
    ax.plot(ring[:, 0], ring[:, 1], "-", color="red", lw=2.2)
    for i in range(24, min(37, len(ring))):
        lo, la = ring[i]
        if LON0 < lo < LON1 and LAT0 < la < LAT1:
            ax.plot(lo, la, "o", ms=5, mfc="red", mec="k", mew=0.6)
            ax.annotate(f"v{i}", (lo, la), textcoords="offset points", xytext=(5, -10),
                        color="red", fontsize=8, weight="bold")
    ax.set_xlim(LON0, LON1)
    ax.set_ylim(LAT0, LAT1)
    ax.set_title(title, fontsize=10)
    ax.set_xlabel("lon")


def main() -> int:
    catalog = yaml.safe_load((ROOT / "data" / "data_catalog.yml").read_text())
    cud = rasterio.open(ROOT / "data" / catalog["cudem_nj"]["uri"])
    win = from_bounds(LON0, LAT0, LON1, LAT1, cud.transform)
    zc = cud.read(1, window=win, masked=True).astype("float64").filled(np.nan)
    t = cud.window_transform(win)
    nr, nc = zc.shape
    lons = t.c + (np.arange(nc) + 0.5) * t.a
    lats = t.f + (np.arange(nr) + 0.5) * t.e
    ring = np.asarray(load_ring())

    have_coned = CONED.exists()
    fig, axes = plt.subplots(1, 2 if have_coned else 1, figsize=(17 if have_coned else 11, 7),
                             dpi=140, squeeze=False)
    _panel(axes[0][0], lons, lats, zc, ring,
           'cudem_nj (1/9") — land STOPS at lat 40.49982 in every column, and there is\n'
           "no data at all west of lon -74.2504. The headland is missing.")
    axes[0][0].set_ylabel("lat")
    if have_coned:
        zn = _grid_from(rasterio.open(CONED), lons, lats)
        _panel(axes[0][1], lons, lats, zn, ring,
               "USGS CoNED NJ/DE topobathy (1 m) — the real Ward Point headland.\n"
               "The drawn ring runs on LAND here; v30/v31 read +2.33 / +2.89 m.")
    else:
        print(f"[warn] {CONED} absent — CUDEM panel only")
    fig.suptitle("Ward Point / Tottenville — the drawn v1.5 ring over two beds", fontsize=12)
    fig.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT)
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
