#!/usr/bin/env python
"""What does SnapWave cost in this run, and where does the time go?

    python scripts/snapwave_cost.py <run_dir_or_sfincs.log> [more ...] [--csv out.csv]

Reads ``sfincs.log`` only. Per SnapWave call it records the model time, the logged wall
time (``took``), the iteration count, whether it converged, and the %ok trajectory
(the share of nodes already converged after each iteration).

🔴 A call over 999.99 s logs ``took ****** seconds`` (Fortran overflow), so summing the
``took`` field silently drops the SLOWEST calls. This script fits

    took ≈ a + b · iterations + c · W,   W = Σ_iterations (1 − %ok_before / 100)

on the calls that did print a time (W counts full-domain-equivalent sweeps: iteration 1
touches every node, later ones only the unconverged share), imputes the overflowed calls
from the fit, and checks the result against the log's own ``Time in SnapWave`` line.

Written 2026-09-30 for the wave cost tests (plan Phase 3), from the 21-line
``logs/snapwave_diag_scratch_2026-09-10/convergence.py`` and the 09-29 reads in
``logs/wave_boundary_v4_2026-09-29/convergence_*.txt``.

Per run it prints: calls, cap-hits, non-converged calls, per-call median/p90, the fit,
SnapWave total (logged, and fit-imputed), the solver's own time split, and the share of
node-work in iterations 1, 1–5 and 26+ (where the time actually goes, which decides
whether an iteration cap or a convergence tolerance can buy anything).
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd

_ITER = re.compile(r"^\s*iteration\s+(\d+)\s+error =\s+(\S+)\s+%ok =\s+([\d.]+)")
_CONV = re.compile(r"^\s*converged at iteration\s+(\d+)")
_TOOK = re.compile(r"Computing SnapWave at t =\s+([\d.]+) s took\s+(\S+) seconds")
_TIMES = re.compile(r"^\s*(Total time|Time in [\w ]+?)\s*:\s+([\d.]+)")


def parse(log: Path) -> tuple[pd.DataFrame, dict]:
    calls, cur, times = [], None, {}
    for line in log.read_text(errors="ignore").splitlines():
        m = _ITER.match(line)
        if m:
            # the error field overflows too (`**********`, wind-off logs, 2026-10-01)
            err = float(m[2]) if re.fullmatch(r"[\d.eE+-]+", m[2]) else np.nan
            it, ok = int(m[1]), float(m[3])
            if it == 1 or cur is None:
                cur = {"ok": [], "err": [], "converged": False}
            cur["ok"].append(ok)
            cur["err"].append(err)
            continue
        if _CONV.match(line) and cur is not None:
            cur["converged"] = True
            continue
        m = _TOOK.search(line)
        if m and cur is not None:
            took = float(m[2]) if re.fullmatch(r"[\d.]+", m[2]) else np.nan
            calls.append({**cur, "t_s": float(m[1]), "took_s": took})
            cur = None
            continue
        m = _TIMES.match(line)
        if m:
            times[m[1].strip()] = float(m[2])
    rows = []
    for c in calls:
        ok = np.asarray(c["ok"])
        before = np.concatenate([[0.0], ok[:-1]]) / 100.0
        rows.append(
            {
                "t_h": c["t_s"] / 3600.0,
                "took_s": c["took_s"],
                "iterations": len(ok),
                "converged": c["converged"],
                "err_final": c["err"][-1],
                "pct_ok_final": ok[-1],
                "work_W": float((1.0 - before).sum()),
                "work_by_iter": 1.0 - before,
            }
        )
    return pd.DataFrame(rows), times


def fit(df: pd.DataFrame):
    t = df[np.isfinite(df.took_s)]
    if len(t) < 5:
        return None
    X = np.column_stack([np.ones(len(t)), t.iterations, t.work_W])
    coef, *_ = np.linalg.lstsq(X, t.took_s.values, rcond=None)
    pred = X @ coef
    ss = ((t.took_s - pred) ** 2).sum()
    r2 = 1 - ss / ((t.took_s - t.took_s.mean()) ** 2).sum()
    return coef, float(r2)


def report(src: Path, csv: Path | None) -> pd.DataFrame:
    log = src / "sfincs.log" if src.is_dir() else src
    if src.is_dir() and (src / "restart_segments").exists():
        print(f"⚠️  {src} has restart_segments/: this reads only the LAST segment's log")
    df, times = parse(log)
    print(f"\n== {log}")
    if df.empty:
        print("   no SnapWave calls found")
        return df
    cap = int(df.iterations.max())
    capped = (~df.converged) & (df.iterations == cap)
    timed = np.isfinite(df.took_s)
    print(
        f"   calls {len(df)}   cap {cap} iterations   cap-hits {int(capped.sum())}   "
        f"non-converged {int((~df.converged).sum())}   untimed (******) "
        f"{int((~timed).sum())}"
    )
    print(
        f"   per call (timed only): median {df.took_s[timed].median():.0f} s   "
        f"p90 {df.took_s[timed].quantile(0.9):.0f} s   max {df.took_s[timed].max():.0f} s"
    )
    f = fit(df)
    if f is not None:
        (a, b, c), r2 = f
        est = np.where(timed, df.took_s, a + b * df.iterations + c * df.work_W)
        df["took_est_s"] = est
        print(
            f"   fit: took ≈ {a:.0f} + {b:.2f}·iterations + {c:.0f}·W   (R² {r2:.3f}, "
            f"{int(timed.sum())} timed calls)"
        )
        print(
            f"   SnapWave total: logged calls {df.took_s[timed].sum() / 3600:.2f} h, "
            f"with imputed overflow {est.sum() / 3600:.2f} h"
        )
        print(f"   median W (full-domain-equivalent sweeps) {df.work_W.median():.2f}")
    if times:
        tot = times.get("Total time", np.nan)
        sw = times.get("Time in SnapWave", np.nan)
        inp = times.get("Time in input", np.nan)
        # The solver's own "(96.9%)" is of SIMULATION time, which excludes input; the
        # premier's 84-min input is itself a SnapWave cost (the nearest-point search for
        # SnapWave-only shelf nodes), so both shares are printed.
        print(
            f"   solver says: total {tot / 3600:.2f} h, SnapWave {sw / 3600:.2f} h "
            f"({100 * sw / (tot - inp):.1f}% of simulation, {100 * sw / tot:.1f}% of "
            f"wall), input {inp / 60:.1f} min, flow+rest {(tot - sw - inp) / 60:.1f} min"
        )
    # Where the node-work sits, by iteration index, summed over calls.
    w = np.zeros(cap)
    for arr in df.work_by_iter:
        w[: len(arr)] += arr
    w /= w.sum()
    print(
        f"   node-work share: iteration 1 {100 * w[:1].sum():.0f}%, 1–5 "
        f"{100 * w[:5].sum():.0f}%, 26+ {100 * w[25:].sum():.0f}%"
    )
    if csv is not None:
        out = df.drop(columns="work_by_iter").assign(run=str(src))
        header = not csv.exists()
        out.to_csv(csv, mode="a", header=header, index=False)
    return df


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("runs", nargs="+", type=Path, help="run dirs or sfincs.log files")
    p.add_argument("--csv", type=Path, help="append per-call rows here")
    a = p.parse_args()
    for r in a.runs:
        report(r, a.csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
