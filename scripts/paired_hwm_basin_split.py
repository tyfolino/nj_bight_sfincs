"""Paired HWM bootstrap SPLIT by basin: the Raritan/Lower Bay seiche system vs the rest.

Why (STATUS 2026-09-08): any perturbation re-rings Raritan Bay (FINDINGS §40), so the
38 marks in raritan_bay / sandy_hook_bay / lower_bay_si_shore / shrewsbury_navesink move
together by ±0.2-0.3 m between ANY two arms and dominate the pooled paired delta. The
split reports the seiche basins and the other 56 marks separately, at 25 m and 50 m.
Residuals mirror scripts/paired_hwm_bootstrap.py (median estimator).

    NJ_DOMAIN=v3 PYTHONPATH=$PWD python scripts/paired_hwm_basin_split.py bed-buildings naccs-premier
"""
import sys
sys.path.insert(0, "scripts")
import numpy as np, geopandas as gpd
from paired_hwm_bootstrap import residuals
from nj_sfincs import domain as _domain
from nj_sfincs.config import exp_root
from nj_sfincs.validate.metrics import _clip_to_region
root = exp_root()
SEICHE = {"raritan_bay", "sandy_hook_bay", "lower_bay_si_shore", "shrewsbury_navesink"}
rng = np.random.default_rng(20261007)
for radius in (25.0, 50.0):
    ma, ra = residuals(root / sys.argv[1], "median", radius)
    mb, rb = residuals(root / sys.argv[2], "median", radius)
    hwm = _clip_to_region(gpd.read_file(str(_domain.active().hwm_geojson)).to_crs("EPSG:32618"))
    basin = np.asarray(_domain.classify_hwm_basin(hwm.geometry.x.values, hwm.geometry.y.values))
    ok = ma & mb
    print(f"\n=== radius {radius:.0f} m, common marks {ok.sum()}")
    d = ra - rb  # per-mark change in residual (A − B)
    for b in sorted(set(basin[ok])):
        s = ok & (basin == b)
        print(f"  {b:24s} n={s.sum():2d}  mean Δres {d[s].mean():+.3f}  median {np.median(d[s]):+.3f}  n(up)={int((d[s]>0).sum())}")
    for label, sel in (("ALL", ok), ("seiche basins", ok & np.isin(basin, list(SEICHE))), ("non-seiche basins", ok & ~np.isin(basin, list(SEICHE)))):
        A, B = ra[sel], rb[sel]; n = sel.sum()
        rmse = lambda x: float(np.sqrt(np.mean(x**2)))
        idx = rng.integers(0, n, size=(200_000, n))
        drm = np.sqrt((A[idx]**2).mean(1)) - np.sqrt((B[idx]**2).mean(1))
        dbi = A[idx].mean(1) - B[idx].mean(1)
        print(f"  {label:18s} n={n:2d}  RMSE A {rmse(A):.3f} B {rmse(B):.3f}  ΔRMSE {rmse(A)-rmse(B):+.3f} [{np.percentile(drm,2.5):+.3f}, {np.percentile(drm,97.5):+.3f}]  "
              f"Δbias {A.mean()-B.mean():+.3f} [{np.percentile(dbi,2.5):+.3f}, {np.percentile(dbi,97.5):+.3f}]  P(ΔRMSE>0)={(drm>0).mean():.3f}")
