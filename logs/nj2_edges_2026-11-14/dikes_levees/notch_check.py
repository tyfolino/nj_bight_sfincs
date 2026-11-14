"""Hand pass on the 6 structure notches (README Table 2, logs/weirs_dikes_levees_2026-11-12): lidar only, no imagery.
For each notch: the nearest line of the RECOMMENDED set and the crest written there; 1/9in CUDEM in a 100 m disc: the
lowest ground in the notch (15 m disc) and whether a channel below 0.0 m NAVD88 runs THROUGH the line (one connected
patch of < 0 m pixels touching both sides of the line within 60 m) - the signature of a creek / culvert / gate opening,
as opposed to a dip in the crest. Writes notch_check.csv. Read-only.
    source logs/weirs_dikes_levees_2026-11-12/env.sh; python -I logs/nj2_edges_2026-11-14/dikes_levees/notch_check.py"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyproj
import rasterio
import shapely
from affine import Affine
from rasterio.warp import reproject, Resampling
from scipy import ndimage

R = Path("/cache/home/tpj8/nj_bight_sfincs")
H = Path(__file__).resolve().parent
sys.path.insert(0, str(R / "logs/refreeze_2026-10-06/structures"))
from weir_on_mesh import read_weir  # noqa: E402

NOTCHES = [  # README Table 2: site, lon, lat, raw -> filled, distance to the tidal-reach sill, sill level
    ("Forsythe West Pool (NE dike)", -74.42625, 39.47277, "1.37 -> 2.31", 53, -0.03),
    ("r1054 DE New Castle", -75.57129, 39.52730, "2.21 -> 2.75", 68, -0.07),
    ("r1047 DE New Castle", -75.62163, 39.43131, "1.98 -> 2.46", 88, 0.25),
    ("r1069 Salem", -75.51741, 39.53994, "0.97 -> 1.50", 9, 0.38),
    ("r1078 Salem", -75.50805, 39.58976, "1.05 -> 2.02", 139, 0.74),
    ("r1139 DE Kent (r60 build)", -75.43930, 39.30729, "1.74 -> 2.04", 108, 0.47),
]
T = pyproj.Transformer.from_crs(4326, 32618, always_xy=True)
SET = sys.argv[1] if len(sys.argv) > 1 else str(R / "logs/weirs_dikes_levees_2026-11-12/cand_recommended.weir")
lines = read_weir(SET)
rows = []
for site, lon, lat, rf, dsill, sill in NOTCHES:
    x, y = T.transform(lon, lat)
    p = shapely.Point(x, y)
    best = min(lines, key=lambda nl: shapely.LineString(nl[1][:, :2]).distance(p))
    ln = shapely.LineString(best[1][:, :2])
    dline = ln.distance(p)
    s = ln.project(p)
    seg = np.asarray(best[1])
    cum = np.r_[0, np.cumsum(np.hypot(*np.diff(seg[:, :2], axis=0).T))]
    crest = float(np.interp(s, cum, seg[:, 2]))
    half, res = 100.0, 1.5
    n = int(2 * half / res)
    z = np.full((n, n), np.nan, np.float32)
    dt = Affine(res, 0, x - half, 0, -res, y + half)
    src = R / ("data/elevation_v4/cudem_delaware_v4.vrt" if lon < -75.0 else "data/elevation_v3/cudem_nj_v3.vrt")
    with rasterio.open(src) as r:
        reproject(rasterio.band(r, 1), z, dst_transform=dt, dst_crs="EPSG:32618", resampling=Resampling.bilinear,
                  dst_nodata=np.nan)
    cx = x - half + res * (np.arange(n) + .5)
    cy = y + half - res * (np.arange(n) + .5)
    X, Y = np.meshgrid(cx, cy)
    r_ = np.hypot(X - x, Y - y)
    notch_min = float(np.nanmin(np.where(r_ <= 15, z, np.nan)))
    # side of the line: sign of the cross product against the local segment direction
    a = np.asarray(ln.interpolate(max(s - 10, 0)).coords[0])
    b = np.asarray(ln.interpolate(min(s + 10, ln.length)).coords[0])
    side = np.sign((b[0] - a[0]) * (Y - a[1]) - (b[1] - a[1]) * (X - a[0]))
    lab, _ = ndimage.label((z < 0.0) & (r_ <= 60))
    through = False
    for k in np.unique(lab[(lab > 0) & (r_ <= 25)]):
        m = lab == k
        if (side[m] > 0).any() and (side[m] < 0).any():
            through = True
    wet = float(np.mean(z[r_ <= 60] < 0.0))
    rows.append(dict(site=site, lon=lon, lat=lat, readme_raw_to_filled=rf, readme_d_sill_m=dsill, sill_level=sill,
                     nearest_line=best[0], d_line_m=round(dline, 1), crest_written=round(crest, 2),
                     cudem_notch_min_15m=round(notch_min, 2), channel_below_0_through_line=through,
                     frac_below_0_r60=round(wet, 2),
                     read=("channel through the line: creek / culvert / gate opening in the lidar -> storm-SHUT kept; "
                           "needs imagery for a normal-weather drn" if through else
                           "dip in the crest only (no < 0 m channel through the line) -> filled, as built")))
df = pd.DataFrame(rows)
df.to_csv(H / "notch_check.csv", index=False)
print(df.drop(columns=["read"]).to_string())
