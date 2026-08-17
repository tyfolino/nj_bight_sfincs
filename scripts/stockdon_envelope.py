#!/usr/bin/env python
"""Stockdon (2006) runup envelope on a STILL-WATER run — a scoring diagnostic, not an arm.

WHY THIS IS A POST-HOC ENVELOPE AND NOT A FORCING TERM
------------------------------------------------------
🔴 FINDINGS §22: **setup at the boundary XOR SnapWave — never both.** That is the SFINCS
authors' own rule (Leijnse et al. 2025, §4.4), and their measured cost of breaking it is a
max-water-depth overestimate of **~1 m**. 🔴 FINDINGS §23: **NACCS water level ALREADY
INCLUDES wave setup** (CSTORM-MS, ADCIRC coupled to STWAVE via radiation stress). So adding
a parametric setup term on top of a NACCS boundary would stack a third wave contribution on
a product that already carries one.

Nothing here enters the solver. This reads a finished still-water run (`naccs-nowaves`) and
brackets each HWM by ``[still water, still water + R2%]``. No double counting is possible
because no water level is modified.

TWO NUMBERS, AND THE DIFFERENCE IS THE WHOLE POINT
--------------------------------------------------
Stockdon decomposes runup into setup plus swash::

    eta  = 0.35 * bf * sqrt(H0 * L0)                      <- SETUP: a raised water LEVEL
    S    = sqrt( (0.75*bf*sqrt(H0*L0))**2                 <- SWASH: an EXCURSION, not a level
                 + (0.06*sqrt(H0*L0))**2 )
    R2   = 1.1 * (eta + S/2)

⭐ **`eta` is the quantity SnapWave computes** — it raises `zs`, so it is what a parametric
replacement would have to reproduce. **`S` is not a water level at all**; it is swash
run-up-and-down the foreshore. An HWM on an exposed beach records the top of that excursion,
which is why R2 brackets marks a still-water model can never reach. Judge "could this
replace SnapWave?" on `eta`. Judge "does this bracket the HWMs?" on R2.

⚠️ **R2 IS AN UPPER ENVELOPE, NOT A PREDICTOR.** The archive measured exactly this: 81% of
marks fell inside, but it overshoots moderate marks and only the most exposed ones reach the
top. Do not difference against R2 and call it a bias.

🔴 **STOCKDON IS A BEACH FORMULA AND IS INVALID IN SHELTERED WATER.** It is calibrated on
open foreshores. The archive measured it running too HIGH in sheltered spots (Sandy Hook
ocean +0.67 m, Shark inlet +0.94 m) and too LOW at the high-energy beachfront. So marks are
split by `Domain.hwm_rules` basin and only the open-coast basins are scored by default;
the sheltered ones are reported separately and labelled INVALID, never pooled.

H0 — WHY CORA IS REVERSE-SHOALED
--------------------------------
Stockdon's `H0` is the DEEP-WATER significant height. CORA is a shelf product: its deepest
node here is 68.9 m, so its `hs` has already shoaled. Linear theory undoes it::

    Cg0 = g*T/(4*pi);  Cg = n*C;  n = 0.5*(1 + 2kh/sinh(2kh));  H0 = H * sqrt(Cg/Cg0)

`L0 = g*T**2/(2*pi)` needs no correction — it is built from the period, which shoaling
conserves. ⚠️ ERA5 is deliberately NOT used: FINDINGS §21 rules it inadmissible as a
NEARSHORE boundary (γ 0.86–0.89 in 9.9 m of water). That is a statement about the 10 m
contour, not about deep water, but CORA is the adopted product and keeping one source is
cleaner than defending two.

Usage:
    PYTHONPATH=$PWD python scripts/stockdon_envelope.py
    PYTHONPATH=$PWD python scripts/stockdon_envelope.py --arm naccs-nowaves --beta-f 0.05
    PYTHONPATH=$PWD python scripts/stockdon_envelope.py --all-basins
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import xarray as xr

import nj_sfincs  # noqa: F401 — pins the pyproj-before-hydromt import order
from nj_sfincs import domain as _domain
from nj_sfincs import validate
from nj_sfincs.config import DATA, exp_root
from nj_sfincs.validate import DEPTH_MIN
from nj_sfincs.validate.metrics import _clip_to_region, _hwm_path

G = 9.81
GROUND_CAP = 0.5

#: Basins where an open-foreshore runup formula is physically meaningful. Everything else is
#: reported but never pooled — see the module docstring.
OPEN_COAST_BASINS = ("atlantic_oceanfront", "south_coast")

#: CORA nodes at least this deep stand in for "offshore"; shallower ones are already inside
#: the surf zone, where Stockdon's H0 is undefined.
MIN_NODE_DEPTH_M = 30.0


def wave_number(T: float, h: float) -> float:
    """Solve the linear dispersion relation for k by Newton iteration."""
    if not np.isfinite(T) or T <= 0 or h <= 0:
        return float("nan")
    omega = 2 * math.pi / T
    k = omega**2 / G  # deep-water seed
    for _ in range(60):
        tanh_kh = math.tanh(k * h)
        f = G * k * tanh_kh - omega**2
        df = G * tanh_kh + G * k * h * (1 - tanh_kh**2)
        if df == 0:
            break
        step = f / df
        k -= step
        if abs(step) < 1e-12:
            break
    return k


def deshoal(H: float, T: float, h: float) -> float:
    """Reverse-shoal a height measured in depth ``h`` back to deep water."""
    k = wave_number(T, h)
    if not np.isfinite(k) or k <= 0:
        return float("nan")
    kh = k * h
    n = 0.5 * (1 + 2 * kh / math.sinh(2 * kh)) if kh < 350 else 0.5
    C = (2 * math.pi / T) / k
    Cg = n * C
    Cg0 = G * T / (4 * math.pi)
    return H * math.sqrt(Cg / Cg0)


def stockdon(H0: float, T: float, bf: float) -> tuple[float, float, float]:
    """Return (eta setup, S swash, R2% runup) in metres."""
    if not np.isfinite(H0) or not np.isfinite(T) or H0 <= 0 or T <= 0:
        return (float("nan"),) * 3
    L0 = G * T * T / (2 * math.pi)
    root = math.sqrt(H0 * L0)
    eta = 0.35 * bf * root
    S = math.hypot(0.75 * bf * root, 0.06 * root)
    return eta, S, 1.1 * (eta + S / 2)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--arm", default="naccs-nowaves",
                   help="a STILL-WATER run (waves off). Default: naccs-nowaves")
    p.add_argument("--beta-f", type=float, default=0.05,
                   help="foreshore slope; the archive used 0.05")
    p.add_argument("--radius-m", type=float, default=50.0)
    p.add_argument("--all-basins", action="store_true",
                   help="also POOL the sheltered basins (physically invalid — see docstring)")
    p.add_argument("--max-quality", type=float, default=2.0,
                   help="survey-quality cut. ⚠️ DEFAULT 2 MATCHES THE HEADLINE SCORER; any "
                        "other value is a STANDALONE diagnostic and its numbers are NOT "
                        "comparable with metrics.csv (FINDINGS §6: a changed scored-mark "
                        "count invalidates a comparison). Raising it to 3 roughly doubles "
                        "the open-coast sample and reintroduces the high runup marks the "
                        "q<=2 cut removes — which is the tail this diagnostic is about.")
    a = p.parse_args()

    dom = _domain.active()
    run = exp_root() / a.arm
    if not (run / "sfincs_map.nc").exists():
        raise SystemExit(f"no sfincs_map.nc in {run}")

    print(f"domain {dom.name} · arm {a.arm} · beta_f {a.beta_f} · q<={a.max_quality:g}")
    if a.max_quality != 2.0:
        print("⚠️  NON-DEFAULT QUALITY CUT — standalone diagnostic, NOT comparable\n    with metrics.csv or any other arm (FINDINGS §6).")

    # ---- model still water at each mark, exactly as score_hwm reads it ----------
    _m, hmax, dep = validate.load_floodmap(run)
    hwm = _clip_to_region(gpd.read_file(str(_hwm_path(DATA))).to_crs(dep.rio.crs))
    depth, dep_a, wse = hmax.values, dep.values, (dep + hmax).values
    if depth.ndim == 3:
        depth, wse, dep_a = depth[0], wse[0], dep_a[0]
    T_ = dep.rio.transform()
    ny, nx = wse.shape
    rad = int(round(a.radius_m / abs(T_.a)))
    obs = hwm["elev_m"].values
    qual = hwm["quality"].values.astype(float)
    still = np.full(len(obs), np.nan)
    for k, (X, Y) in enumerate(zip(hwm.geometry.x.values, hwm.geometry.y.values)):
        c, r = int((X - T_.c) / T_.a), int((Y - T_.f) / T_.e)
        if not (0 <= r < ny and 0 <= c < nx):
            continue
        r0, c0 = max(0, r - rad), max(0, c - rad)
        sl = (slice(r0, r + rad + 1), slice(c0, c + rad + 1))
        ws, hh, dd = wse[sl], depth[sl], dep_a[sl]
        flooded = (hh >= DEPTH_MIN) & (dd <= obs[k] + GROUND_CAP)
        if flooded.any():
            still[k] = np.nanmedian(ws[flooded])
        elif np.isfinite(dd).any():
            still[k] = np.nanmin(dd)  # dry: the model's ground, as score_hwm does

    # ---- Stockdon from CORA, reverse-shoaled ------------------------------------
    cw = xr.open_dataset(DATA / "waves" / "cora_waves_nj.nc")
    cdep = cw["depth"].values
    deep = np.nonzero(cdep >= MIN_NODE_DEPTH_M)[0]
    print(f"[cora] {len(deep)} node(s) at depth >= {MIN_NODE_DEPTH_M:g} m "
          f"(max depth in product {np.nanmax(cdep):.1f} m)")
    hs_all, tp_all = cw["hs"].values, cw["tp"].values
    # storm-peak sea state per node, which is what an HWM is a record of
    pk = np.nanargmax(np.nanmax(hs_all[:, deep], axis=1))
    print(f"[cora] storm peak at {cw.time.values[pk]}")
    hs_pk, tp_pk = hs_all[pk, deep], tp_all[pk, deep]
    clon, clat = cw["lon"].values[deep], cw["lat"].values[deep]
    cdd = cdep[deep]

    marks = gpd.GeoDataFrame(geometry=hwm.geometry, crs=hwm.crs).to_crs(4326)
    eta = np.full(len(obs), np.nan)
    R2 = np.full(len(obs), np.nan)
    H0s = np.full(len(obs), np.nan)
    for k, (lo, la) in enumerate(zip(marks.geometry.x.values, marks.geometry.y.values)):
        d = np.hypot((clon - lo) * math.cos(math.radians(la)), clat - la)
        j = int(np.argmin(d))
        H0 = deshoal(float(hs_pk[j]), float(tp_pk[j]), float(cdd[j]))
        H0s[k] = H0
        e, _s, r2 = stockdon(H0, float(tp_pk[j]), a.beta_f)
        eta[k], R2[k] = e, r2

    # ---- basin split, first-match-wins over the registry rules ------------------
    basin = np.array(["unclassified"] * len(obs), dtype=object)
    xs, ys = hwm.geometry.x.values, hwm.geometry.y.values
    for i in range(len(obs)):
        for rule in dom.hwm_rules:
            if rule.matches(xs[i], ys[i]):
                basin[i] = rule.name
                break

    ok = np.isfinite(still) & np.isfinite(R2) & (qual <= a.max_quality)
    inside = ok & (obs >= still) & (obs <= still + R2)
    below = ok & (obs < still)               # model already at or above the mark
    above = ok & (obs > still + R2)          # envelope cannot reach it

    print(f"\nbeta_f={a.beta_f}  H0 (deshoaled) median {np.nanmedian(H0s[ok]):.2f} m  "
          f"eta median {np.nanmedian(eta[ok]):.2f} m  R2 median {np.nanmedian(R2[ok]):.2f} m")
    hdr = (f"\n{'basin':24s} {'n':>3s} {'eta':>6s} {'R2':>6s} "
           f"{'inside':>7s} {'below':>6s} {'above':>6s}   verdict")
    print(hdr)
    print("-" * len(hdr))
    for b in [r.name for r in dom.hwm_rules]:
        s = ok & (basin == b)
        if not s.any():
            continue
        tag = "open coast" if b in OPEN_COAST_BASINS else "SHELTERED — INVALID"
        print(f"{b:24s} {s.sum():3d} {np.nanmedian(eta[s]):6.2f} {np.nanmedian(R2[s]):6.2f} "
              f"{100 * inside[s].sum() / s.sum():6.0f}% {100 * below[s].sum() / s.sum():5.0f}% "
              f"{100 * above[s].sum() / s.sum():5.0f}%   {tag}")

    sel = ok & np.isin(basin, OPEN_COAST_BASINS)
    print(f"\nOPEN COAST POOLED  n={sel.sum()}  inside envelope "
          f"{100 * inside[sel].sum() / max(sel.sum(), 1):.0f}%  "
          f"(below {100 * below[sel].sum() / max(sel.sum(), 1):.0f}%, "
          f"above {100 * above[sel].sum() / max(sel.sum(), 1):.0f}%)")
    print(f"⭐ SETUP-ONLY (the SnapWave-comparable term): median eta = "
          f"{np.nanmedian(eta[sel]):.3f} m on the open coast")
    if a.all_basins:
        print(f"\n⚠️  ALL BASINS POOLED (physically invalid, requested): n={ok.sum()}  "
              f"inside {100 * inside[ok].sum() / ok.sum():.0f}%")
    # ---- the question the envelope cannot answer --------------------------------
    # "Inside the envelope" is nearly vacuous: R2 is ~3 m tall, so it brackets every mark
    # at every beta_f tested. What actually decides whether a parametric SETUP term could
    # stand in for SnapWave is how much extra water each mark needs above still water —
    # `need` — measured against `eta`, the only part of Stockdon that is a water level.
    need = obs - still
    print("\nHOW MUCH WATER EACH MARK ACTUALLY NEEDS ABOVE STILL WATER")
    print("  need = obs - still_water.  Compare against eta (a LEVEL), not R2 (an envelope).")
    hdr = (f"\n{'basin':24s} {'n':>3s} {'need_med':>9s} {'eta':>6s} "
           f"{'need>eta':>9s} {'need<=0':>8s}")
    print(hdr)
    print("-" * len(hdr))
    for b in [r.name for r in dom.hwm_rules]:
        s = ok & (basin == b)
        if not s.any():
            continue
        print(f"{b:24s} {s.sum():3d} {np.nanmedian(need[s]):9.2f} "
              f"{np.nanmedian(eta[s]):6.2f} "
              f"{100 * (need[s] > eta[s]).sum() / s.sum():8.0f}% "
              f"{100 * (need[s] <= 0).sum() / s.sum():7.0f}%")
    if sel.any():
        print(f"\nOPEN COAST  need median {np.nanmedian(need[sel]):.2f} m  vs  eta "
              f"{np.nanmedian(eta[sel]):.2f} m   -> ratio {np.nanmedian(need[sel]) / np.nanmedian(eta[sel]):.2f}")
    print("\n⚠️  R2 is an UPPER ENVELOPE, not a predictor — do not difference against it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
