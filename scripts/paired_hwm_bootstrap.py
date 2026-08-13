#!/usr/bin/env python
"""Paired bootstrap on HWM residuals — compare two arms on the SAME marks.

WHY THIS EXISTS (2026-08-07)
----------------------------
Two arms that differ in one input and share mark set, mesh and domain are a **paired**
comparison. Scoring them with an unpaired standard error --- roughly ``RMSE/sqrt(2n)``,
about 0.075 m at n=38 --- overstates the spread by ~7x and will call a real effect noise.

That happened: ``tide-anchor`` - ``tide-shift`` = +0.056 m HWM RMSE was dismissed as
"inside the noise". Paired, the 95% CI is [+0.034, +0.076] --- it excludes zero, and
P(the arm fails its +0.01 m pass criterion) = 1.000. The effect was never marginal; only
its crossing of a separate 0.05 m threshold was (P = 0.735).

⚠️ This reports a DIFFERENCE OF RMSEs, not a p-value for "is arm A good". It answers
"given these marks, how sure are we that A is worse/better than B" --- nothing else.

WHAT IT MIRRORS
---------------
Per-mark residuals reproduce ``validate.hwm_metrics`` exactly: same estimator (default
``median``), same ``radius_m`` (50), same ``DEPTH_MIN``, same ``GROUND_CAP``, q<=2 only,
dry marks scored against the lowest nearby ground rather than dropped. It re-derives that
function's published RMSEs to 4 dp; if it ever stops doing so, this script is stale and
``hwm_metrics`` is the authority.

⚠️ Only marks scored in EVERY arm are used, so all arms are compared on one common set.
A differing mark count between arms is a different measurement --- see the ``hwm_metrics``
docstring.

Usage:
    PYTHONPATH=$PWD python scripts/paired_hwm_bootstrap.py \
        faber-nowaves+tide-anchor faber-nowaves+tide-shift
    PYTHONPATH=$PWD python scripts/paired_hwm_bootstrap.py A B --thresholds 0.01 0.05
"""
from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import numpy as np

import nj_sfincs  # noqa: F401 — pins the pyproj-before-hydromt import order
from nj_sfincs import validate
from nj_sfincs.config import exp_root
from nj_sfincs.config import DATA
from nj_sfincs.validate import DEPTH_MIN

GROUND_CAP = 0.5  # m; matches hwm_metrics


def residuals(model_dir: Path, estimator: str, radius_m: float):
    """Per-mark (mask, residual) for one run. Mirrors validate.hwm_metrics."""
    _mod, da_hmax, da_dep = validate.load_floodmap(model_dir)
    hwm = gpd.read_file(str(DATA / "validation" / "sandy_hwms.geojson")).to_crs(
        da_dep.rio.crs
    )
    depth, dep_arr, wse = da_hmax.values, da_dep.values, (da_dep + da_hmax).values
    if depth.ndim == 3:
        depth, wse, dep_arr = depth[0], wse[0], dep_arr[0]
    T = da_dep.rio.transform()
    ny, nx = wse.shape
    rad = int(round(radius_m / abs(T.a)))

    obs = hwm["elev_m"].values
    qual = hwm["quality"].values.astype(float)
    mod_wse = np.full(len(obs), np.nan)
    mod_ground = np.full(len(obs), np.nan)
    for k, (X, Y) in enumerate(zip(hwm.geometry.x.values, hwm.geometry.y.values)):
        col, row = int((X - T.c) / T.a), int((Y - T.f) / T.e)
        if not (0 <= row < ny and 0 <= col < nx):
            continue
        r0, c0 = max(0, row - rad), max(0, col - rad)
        sl = (slice(r0, row + rad + 1), slice(c0, col + rad + 1))
        ws, hh, dd = wse[sl], depth[sl], dep_arr[sl]
        if np.isfinite(dd).any():
            mod_ground[k] = np.nanmin(dd)
        flooded = (hh >= DEPTH_MIN) & (dd <= obs[k] + GROUND_CAP)
        if flooded.any():
            vals = ws[flooded]
            mod_wse[k] = np.nanmax(vals) if estimator == "max" else np.nanmedian(vals)

    mod_scored = np.where(np.isfinite(mod_wse), mod_wse, mod_ground)
    scored = np.isfinite(mod_scored) & (qual <= 2)
    return scored, mod_scored - obs


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("arm_a")
    p.add_argument("arm_b", help="the incumbent / bar; the reported delta is A - B")
    p.add_argument("--estimator", default="median", choices=["median", "max"],
                   help="must match the runs being compared (default: median)")
    p.add_argument("--radius-m", type=float, default=50.0)
    p.add_argument("--n-boot", type=int, default=200_000)
    p.add_argument("--seed", type=int, default=20261007)
    p.add_argument("--thresholds", type=float, nargs="*", default=[0.0, 0.01, 0.05],
                   help="report P(delta > t) for each; use your PRE-REGISTERED lines")
    a = p.parse_args()

    root = exp_root()
    masks, res = {}, {}
    for arm in (a.arm_a, a.arm_b):
        d = root / arm
        if not (d / "sfincs_map.nc").exists():
            raise SystemExit(f"no sfincs_map.nc in {d}")
        m, r = residuals(d, a.estimator, a.radius_m)
        masks[arm], res[arm] = m, r
        print(f"{arm:<32} n={m.sum():3d}  RMSE={np.sqrt((r[m] ** 2).mean()):.4f}  "
              f"bias={r[m].mean():+.4f}")
        validate.load_floodmap_cache_clear()

    common = masks[a.arm_a] & masks[a.arm_b]
    idx = np.nonzero(common)[0]
    for arm in (a.arm_a, a.arm_b):
        dropped = int(masks[arm].sum() - common.sum())
        if dropped:
            print(f"⚠️  {arm}: {dropped} mark(s) scored here but not in the other arm — "
                  "excluded so both are measured on one common set")
    print(f"\ncommon scored marks: {common.sum()}   "
          f"(estimator={a.estimator}, radius={a.radius_m:g} m)")

    ra, rb = res[a.arm_a][idx], res[a.arm_b][idx]
    point = np.sqrt((ra ** 2).mean()) - np.sqrt((rb ** 2).mean())
    rng = np.random.default_rng(a.seed)
    draws = rng.integers(0, len(idx), size=(a.n_boot, len(idx)))
    d = np.sqrt((ra[draws] ** 2).mean(1)) - np.sqrt((rb[draws] ** 2).mean(1))
    lo, hi = np.percentile(d, [2.5, 97.5])

    print(f"\ndelta RMSE ({a.arm_a} - {a.arm_b}) = {point:+.4f} m")
    print(f"   95% CI [{lo:+.4f}, {hi:+.4f}]   B={a.n_boot}")
    print(f"   P(delta < 0, i.e. A better) = {np.mean(d < 0):.3f}")
    for t in a.thresholds:
        print(f"   P(delta > {t:+.3f} m) = {np.mean(d > t):.3f}")
    print("\nReport the CI and the threshold probabilities together. A CI that excludes "
          "zero\nmeans the difference is real; whether it clears a PRE-REGISTERED line is "
          "a separate\nquestion with its own probability.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
