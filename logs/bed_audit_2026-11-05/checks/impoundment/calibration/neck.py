"""Where does a polygon's link run? Prints the neck cells (bed within 3 cm of LINK in the seed-joined component)."""
import sys
sys.path.insert(0, "/cache/home/tpj8/nj_bight_sfincs/logs/bed_audit_2026-11-05/checks/impoundment")
import check, numpy as np
from scipy import ndimage
from rasterio import features
from shapely.geometry import Point
E, lon, lat = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
ov = [x for x in sys.argv[4:] if not x.startswith("min:")]
ovm = [x[4:] for x in sys.argv[4:] if x.startswith("min:")]
bed = check.BedReader(E, ov, ovm)
seed = check.build_seeds(bed, check.RAW / f"seeds_{E.rstrip('/').split('/')[-1]}.npz")
nwi = check.load_nwi()
p = Point(*check.TO_UTM(lon, lat))
g = sorted([r.geom for r in nwi.itertuples() if r.geom.distance(p) < 20], key=lambda q: -q.area)[0]
L, info = check.link_level(bed, seed, g, 1500, hi=3.0, own_seeds=False)
print("link", L, info)
x0, y0, x1, y1 = g.bounds
w = bed.window_for(x0 - 1500, y0 - 1500, x1 + 1500, y1 + 1500)
a, tr = bed.read(w)
pm = features.rasterize([(g.buffer(-5), 1)], out_shape=a.shape, transform=tr, fill=0).astype(bool)
rr = np.clip((np.arange(a.shape[0]) + w.row_off) // 4, 0, seed.shape[0] - 1)
cc = np.clip((np.arange(a.shape[1]) + w.col_off) // 4, 0, seed.shape[1] - 1)
near = features.rasterize([(g.buffer(30), 1)], out_shape=a.shape, transform=tr, fill=0).astype(bool)
sd = seed[np.ix_(rr, cc)] & (a <= -0.5) & ~near
lab, _ = ndimage.label(np.isfinite(a) & (a <= L + 0.005))
j = np.intersect1d(np.unique(lab[sd]), np.unique(lab[pm & (a <= L + 0.005)]))
comp = np.isin(lab, j[j > 0])
r, c = np.nonzero(pm & comp)
xs, ys = tr * (c + 0.5, r + 0.5)
print("polygon px reached:", len(r), "bed there min/p50", np.round(np.min(a[r, c]), 2) if len(r) else None, np.round(np.median(a[r, c]), 2) if len(r) else None)
for k in np.argsort(a[r, c])[:4]:
    print("  reached px", [round(v, 5) for v in check.TO_LL(xs[k], ys[k])], round(float(a[r[k], c[k]]), 2))
neck = comp & (a > L - 0.04)
r, c = np.nonzero(neck)
xs, ys = tr * (c + 0.5, r + 0.5)
for k in range(min(6, len(r))):
    print("  neck", [round(v, 5) for v in check.TO_LL(xs[k], ys[k])], round(float(a[r[k], c[k]]), 2))
