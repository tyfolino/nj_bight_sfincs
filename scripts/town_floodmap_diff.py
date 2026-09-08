"""Town-scale floodmap difference panels + wet-area numbers for two arms (item 4 of the
bed-buildings pre-registration, STATUS 2026-09-04/09-08). Windows are EPSG:32618 boxes
around Seaside Heights/Ortley, Ocean City and Absecon Island.

    NJ_DOMAIN=v3 PYTHONPATH=$PWD python scripts/town_floodmap_diff.py naccs-premier bed-buildings reports/figures/buildings
"""
import sys
import numpy as np
import matplotlib; matplotlib.use("Agg")
from nj_sfincs import plots
from nj_sfincs.plots import load_cached_floodmap
from nj_sfincs.config import exp_root
A, B, out = sys.argv[1], sys.argv[2], sys.argv[3]
root = exp_root()
WIN = {
  "seaside_ortley": (575_000, 583_000, 4_417_000, 4_426_000),
  "ocean_city":     (532_000, 541_000, 4_343_000, 4_352_000),
  "absecon_island": (542_000, 554_000, 4_350_000, 4_360_000),
}
for name, w in WIN.items():
    ha, dep = load_cached_floodmap(root / A, window=w)
    hb, _ = load_cached_floodmap(root / B, window=w)
    hb = hb.rio.reproject_match(ha)
    a = np.isfinite(ha.values) & (ha.values > 0.05)
    b = np.isfinite(hb.values) & (hb.values > 0.05)
    px = abs(ha.rio.resolution()[0] * ha.rio.resolution()[1]) / 1e6
    print(f"{name:16s} wet A {a.sum()*px:7.3f} km²  B {b.sum()*px:7.3f} km²  "
          f"only-A {(a&~b).sum()*px:6.3f}  only-B {(b&~a).sum()*px:6.3f}  "
          f"Δdepth(both wet) p50 {np.nanmedian((hb.values-ha.values)[a&b]):+.3f} m")
    fig, ax = plots.plot_depth_difference(A, B, window=w, vlim=0.5)
    fig.savefig(f"{out}/item4_{name}.png", dpi=130); print("  wrote", f"{out}/item4_{name}.png")
