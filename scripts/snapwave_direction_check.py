#!/usr/bin/env python
"""Did SnapWave launch the waves we imposed, and did they reach the shelf?

    python scripts/snapwave_direction_check.py direction   <run> [--ref <run>]
    python scripts/snapwave_direction_check.py bands       <run> [--ref <run>]
    python scripts/snapwave_direction_check.py breaking    <run> --hours 2012-10-29T12 ...
    python scripts/snapwave_direction_check.py convergence <run | sfincs.log>
    python scripts/snapwave_direction_check.py force       <run> [--ref <run>]
    ... [--csv out.csv]

Promoted 2026-09-11 from the four scratch diagnostics that found the wind-direction bug
(`logs/snapwave_diag_scratch_2026-09-10/`, STATUS 09-10 PM, FINDINGS §43).

`direction` is the pass/fail table for any arm on a fixed engine: per map hour, the
energy-weighted mean `wavdir` on the BOUNDARY cells (`snapwavemsk == 2`) against the
imposed `.bwd` (both the plain median and the Hs-weighted circular mean the engine itself
forms) and the ERA5 wind (the vector mean of `sfincs_netamuv.nc`, which is the
speed-weighted mean direction the engine forms). `ok` = |wavdir − imposed| ≤ `dtheta`.

`bands` is the transmission read: median hm0 / imposed median in the entry band (mesh
z < −25 m), the mid band (−20..−15 m) and the −9 m SFINCS-active shelf (−9.8..−8.5 m).
🔴 Bins are on the mesh `z` in `sfincs.nc`, NEVER on the map's `zb`: `zb` is NaN on every
SFINCS-inactive face (FINDINGS §37), and the wave band is almost entirely SFINCS-inactive,
so binning on `zb` silently drops it (the first pass did, and saw 9 k cells of 1.1 M).

`breaking` reconstructs Baldock per depth bin from `hm0 / tp / snapwavedepth` with the
engine's own forms (`Hmax = γ·h`, `baldock_opt 1`) and the run's `snapwave_gamma / alpha /
fw`, falling back to the v2.3.3 engine defaults for absent keys. `convergence` counts
cap-hits per SnapWave call; the log's `iteration` counter tests every 4th sweep, so the cap
is `snapwave_niter / 4`. `force` is the wave-force direction on the −9 m shelf.

Partial-map safe: nothing is time-decoded by xarray; the map time base is read from the
variable's own `units` (falling back to `tref` in `sfincs.inp`), and hours the map does not
hold yet are simply absent from the table. Nothing here is domain-specific: the depth
bands are the pre-registered ones from STATUS 09-08 and are CLI-overridable.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

import nj_sfincs  # noqa: F401  (PROJ primer)
from nj_sfincs.provenance import read_inp
from nj_sfincs.snapwave_params import ENGINE_DEFAULTS_V233

G = 9.81
RHO = 1025.0
SHELF = (-9.8, -8.5)
ENTRY_ZMAX = -25.0
MID = (-20.0, -15.0)
BINS = [
    (-40, -30),
    (-30, -25),
    (-25, -20),
    (-20, -15),
    (-15, -12),
    (-12, -10),
    (-10, -8),
    (-8, -5),
]


# ── loading ──────────────────────────────────────────────────────────────────────


def _parse_tref(inp: dict) -> np.datetime64:
    s = inp.get("tref", "").replace("'", "").strip()
    m = re.match(r"(\d{4})(\d{2})(\d{2})\s+(\d{2})(\d{2})(\d{2})", s)
    if not m:
        raise SystemExit(f"cannot parse tref={s!r} from sfincs.inp")
    y, mo, d, h, mi, se = m.groups()
    return np.datetime64(f"{y}-{mo}-{d}T{h}:{mi}:{se}")


def _time_axis(var: xr.DataArray, tref: np.datetime64) -> np.ndarray:
    """Decode a raw time axis: unit + base from `units`, base falling back to tref."""
    units = str(var.attrs.get("units", "seconds"))
    m = re.match(r"\s*(\w+)\s+since\s+(.+)", units)
    if m:
        unit, base = (
            m.group(1).lower(),
            np.datetime64(m.group(2).strip().replace(" ", "T")),
        )
    else:
        unit, base = units.strip().lower(), tref
    scale = {
        "seconds": 1e3,
        "second": 1e3,
        "minutes": 60e3,
        "minute": 60e3,
        "hours": 3600e3,
        "hour": 3600e3,
    }[unit]
    return base + (var.values.astype(float) * scale).astype("timedelta64[ms]")


@dataclass
class Run:
    path: Path
    inp: dict
    tref: np.datetime64
    z: np.ndarray  # mesh bed, every face (sfincs.nc), NaN nowhere
    msk: np.ndarray  # SFINCS mask on the map
    swm: np.ndarray  # snapwavemsk: 0 off, 1 interior, 2 boundary
    map: xr.Dataset
    times: np.ndarray  # decoded map times

    @property
    def band(self) -> np.ndarray:
        """SnapWave-active, SFINCS-inactive: the offshore wave band."""
        return (self.swm == 1) & (self.msk == 0)

    @property
    def bnd(self) -> np.ndarray:
        return self.swm == 2

    def at(self, t: np.datetime64) -> xr.Dataset | None:
        i = np.where(self.times == t)[0]
        return None if i.size == 0 else self.map.isel(time=int(i[0]))

    def param(self, key: str) -> float:
        v = self.inp.get(key)
        return float(v) if v is not None else float(ENGINE_DEFAULTS_V233[key])


def load_run(path: Path) -> Run:
    path = Path(path)
    inp = read_inp(path)
    if not inp:
        raise SystemExit(f"{path}: no sfincs.inp")
    tref = _parse_tref(inp)
    mesh = xr.open_dataset(path / "sfincs.nc", decode_times=False)
    mp = xr.open_dataset(path / "sfincs_map.nc", decode_times=False)
    if "snapwavemsk" not in mp:
        raise SystemExit(f"{path}: sfincs_map.nc has no snapwavemsk — SnapWave was off")
    return Run(
        path=path,
        inp=inp,
        tref=tref,
        z=mesh["z"].values.astype(float),
        msk=mp["msk"].values,
        swm=mp["snapwavemsk"].values,
        map=mp,
        times=_time_axis(mp["time"], tref),
    )


def _circ_mean_deg(deg: np.ndarray, w: np.ndarray | None = None) -> float:
    deg = np.asarray(deg, float)
    ok = np.isfinite(deg) & (deg < 360.0) & (deg >= 0.0)
    if w is None:
        w = np.ones_like(deg)
    ok &= np.isfinite(w)
    if not ok.any():
        return np.nan
    r = np.radians(deg[ok])
    return float(
        np.degrees(np.arctan2(np.sum(w[ok] * np.sin(r)), np.sum(w[ok] * np.cos(r))))
        % 360.0
    )


def _angdiff(a: float, b: float) -> float:
    return float(abs((a - b + 180.0) % 360.0 - 180.0))


def _read_bnd_series(run: Run, key: str) -> tuple[np.ndarray, np.ndarray]:
    """A SnapWave boundary time series file: col 0 = seconds since tref, then one
    column per support point. Returns (decoded times, values[nt, npts])."""
    name = run.inp.get(key)
    if not name:
        return np.array([], dtype="datetime64[ms]"), np.zeros((0, 0))
    a = np.loadtxt(run.path / name, ndmin=2)
    t = run.tref + (a[:, 0] * 1e3).astype("timedelta64[ms]")
    return t, a[:, 1:]


def _nearest_row(t_series: np.ndarray, vals: np.ndarray, t: np.datetime64):
    if t_series.size == 0:
        return None
    i = int(np.argmin(np.abs((t_series - t).astype("timedelta64[s]").astype(float))))
    return vals[i]


def _wind_from(run: Run) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Domain-mean ERA5 wind: (times, from-direction deg, speed). The vector mean of the
    field is the speed-weighted mean direction the engine forms
    (`u10dmean = atan2(Σ sin(dir)·u10, Σ cos(dir)·u10)`), over the file's grid rather than
    the wave nodes — a few degrees at most."""
    name = run.inp.get("netamuamvfile") or run.inp.get("netamuvfile")
    if not name or not (run.path / name).exists():
        return (np.array([], dtype="datetime64[ms]"), np.array([]), np.array([]))
    w = xr.open_dataset(run.path / name, decode_times=False)
    uu = w["eastward_wind"].mean(
        dim=[d for d in w["eastward_wind"].dims if d != "time"]
    )
    vv = w["northward_wind"].mean(
        dim=[d for d in w["northward_wind"].dims if d != "time"]
    )
    u, v = uu.values.astype(float), vv.values.astype(float)
    return (
        _time_axis(w["time"], run.tref),
        np.degrees(np.arctan2(-u, -v)) % 360,
        np.hypot(u, v),
    )


# ── subcommands ──────────────────────────────────────────────────────────────────


def direction_table(run: Run) -> pd.DataFrame:
    dtheta = run.param("snapwave_dtheta")
    tb, bwd = _read_bnd_series(run, "snapwave_bwdfile")
    th, bhs = _read_bnd_series(run, "snapwave_bhsfile")
    tw, wfrom, wspd = _wind_from(run)
    rows = []
    for t in run.times:
        d = run.at(t)
        wd = d["wavdir"].values[run.bnd]
        hm = d["hm0"].values[run.bnd]
        model = _circ_mean_deg(wd, w=np.square(hm))
        imp = _nearest_row(tb, bwd, t)
        hs = _nearest_row(th, bhs, t)
        imp_med = float(np.nanmedian(imp)) if imp is not None else np.nan
        imp_engine = (
            _circ_mean_deg(imp, w=hs)
            if imp is not None and hs is not None
            else (_circ_mean_deg(imp) if imp is not None else np.nan)
        )
        iw = (
            int(np.argmin(np.abs((tw - t).astype("timedelta64[s]").astype(float))))
            if tw.size
            else None
        )
        delta = (
            _angdiff(model, imp_engine)
            if np.isfinite(model) and np.isfinite(imp_engine)
            else np.nan
        )
        rows.append(
            {
                "time": pd.Timestamp(t),
                "imposed_bwd_median": round(imp_med, 1),
                "imposed_bwd_hs_mean": round(imp_engine, 1),
                "model_wavdir_bnd": round(model, 1),
                "wind_from": round(float(wfrom[iw]), 1) if iw is not None else np.nan,
                "wind_speed": round(float(wspd[iw]), 1) if iw is not None else np.nan,
                "delta_deg": round(delta, 1),
                "dtheta": dtheta,
                "ok": bool(delta <= dtheta) if np.isfinite(delta) else None,
            }
        )
    return pd.DataFrame(rows)


def bands_table(run: Run, entry_zmax=ENTRY_ZMAX, mid=MID, shelf=SHELF) -> pd.DataFrame:
    z = run.z
    band = run.band
    sel = {
        "entry": band & (z < entry_zmax),
        "mid": band & (z >= mid[0]) & (z < mid[1]),
        "shelf9m": (run.msk == 1) & (z >= shelf[0]) & (z <= shelf[1]),
    }
    rows = []
    for t in run.times:
        d = run.at(t)
        h = d["hm0"].values
        tp = d["tp"].values
        imp = float(np.nanmedian(h[run.bnd]))
        r = {
            "time": pd.Timestamp(t),
            "imposed_hm0": round(imp, 2),
            "tp_band": round(float(np.nanmedian(tp[band])), 1),
        }
        for k, s in sel.items():
            r[k] = (
                round(float(np.nanmedian(h[s]) / imp), 3)
                if s.any() and imp > 0
                else np.nan
            )
        r["n_blowup"] = int(np.sum((h[run.swm == 1] > 1.2 * np.nanmax(h[run.bnd]))))
        rows.append(r)
    df = pd.DataFrame(rows)
    df.attrs["n"] = {k: int(s.sum()) for k, s in sel.items()}
    return df


def _wavenumber(T, h):
    om = 2 * np.pi / T
    k = om**2 / G
    for _ in range(30):
        f = G * k * np.tanh(k * h) - om**2
        df = G * np.tanh(k * h) + G * k * h / np.cosh(k * h) ** 2
        k = k - f / df
    return k


def breaking_table(run: Run, hours: list[str], bins=BINS) -> pd.DataFrame:
    gamma, alpha, fw = (
        run.param(k) for k in ("snapwave_gamma", "snapwave_alpha", "snapwave_fw")
    )
    ratio = run.param("snapwave_baldock_ratio")
    rows = []
    for hr in hours:
        t = np.datetime64(hr)
        d = run.at(t)
        if d is None:
            print(f"  {hr}: not in the map (yet)", file=sys.stderr)
            continue
        hm0, tp, h = d["hm0"].values, d["tp"].values, d["snapwavedepth"].values
        ok = (
            (run.swm == 1)
            & np.isfinite(hm0)
            & np.isfinite(tp)
            & (tp > 0.5)
            & np.isfinite(h)
            & (h > 0.1)
        )
        for lo, hi in bins:
            for where, s0 in (("band", run.band), ("active", run.msk == 1)):
                s = ok & s0 & (run.z >= lo) & (run.z < hi)
                if s.sum() < 50:
                    continue
                Hrms = hm0[s] / np.sqrt(2.0)
                T, hh = tp[s], h[s]
                k = _wavenumber(T, hh)
                Hmax = gamma * hh
                Qb = np.exp(-((Hmax / np.maximum(Hrms, 1e-6)) ** 2))
                Dw = np.where(
                    Hrms > ratio * Hmax,
                    0.28 * alpha * RHO * G / T * Qb * (Hmax**2 + Hrms**2),
                    0.0,
                )
                uorb = 0.5 * (2 * np.pi / T) * Hrms / np.sinh(k * hh)
                Df = 0.28 * RHO * fw * uorb**3
                rows.append(
                    {
                        "time": pd.Timestamp(t),
                        "z_bin": f"[{lo},{hi})",
                        "where": where,
                        "n": int(s.sum()),
                        "hm0_med": round(float(np.median(hm0[s])), 2),
                        "tp_med": round(float(np.median(T)), 1),
                        "depth_med": round(float(np.median(hh)), 1),
                        "Qb_med": round(float(np.median(Qb)), 4),
                        "Qb_p90": round(float(np.percentile(Qb, 90)), 4),
                        "Dbrk_med_Wm2": round(float(np.median(Dw)), 2),
                        "Dfric_med_Wm2": round(float(np.median(Df)), 2),
                    }
                )
    df = pd.DataFrame(rows)
    df.attrs["params"] = {
        "gamma": gamma,
        "alpha": alpha,
        "fw": fw,
        "baldock_ratio": ratio,
    }
    return df


_ITER = re.compile(r"\s*iteration\s+(\d+)\s+error =\s+([0-9.E+-]+)\s+%ok =\s+([0-9.]+)")


def convergence_table(log: Path, niter: int | None) -> pd.DataFrame:
    calls, cur = [], None
    for line in open(log, errors="ignore"):
        m = _ITER.match(line)
        if not m:
            continue
        it, err, ok = int(m.group(1)), float(m.group(2)), float(m.group(3))
        if it == 1 and cur is not None:
            calls.append(cur)
        cur = [it, err, ok]
    if cur is not None:
        calls.append(cur)
    cap = niter // 4 if niter else max((c[0] for c in calls), default=0)
    df = pd.DataFrame(calls, columns=["iterations", "error_final", "pct_ok"])
    df.insert(0, "call", np.arange(len(df)))
    df["cap_hit"] = df["iterations"] >= cap
    df.attrs["cap"] = cap
    df.attrs["cap_source"] = "snapwave_niter/4" if niter else "max seen in log"
    return df


def force_table(run: Run, shelf=SHELF) -> pd.DataFrame:
    if "fwx" not in run.map:
        raise SystemExit(f"{run.path}: no fwx/fwy in the map (storefw was 0)")
    s = (run.msk == 1) & (run.z >= shelf[0]) & (run.z <= shelf[1])
    rows = []
    for t in run.times:
        d = run.at(t)
        fx, fy = d["fwx"].values[s], d["fwy"].values[s]
        ok = np.isfinite(fx) & np.isfinite(fy)
        # Direction of the MEAN force vector: a component-wise median of small, noisy
        # forces collapses to (0, 0) and its arctan is noise.
        mx, my = float(np.mean(fx[ok])), float(np.mean(fy[ok]))
        cart = np.degrees(np.arctan2(my, mx)) % 360
        rows.append(
            {
                "time": pd.Timestamp(t),
                "n": int(ok.sum()),
                "F_mean": float(np.hypot(mx, my)),
                "F_med": float(np.median(np.hypot(fx[ok], fy[ok]))),
                "dir_cartesian_deg": round(cart, 0),
                "dir_nautical_towards": round((90.0 - cart) % 360, 0),
            }
        )
    return pd.DataFrame(rows)


# ── CLI ──────────────────────────────────────────────────────────────────────────


def _side_by_side(a: pd.DataFrame, b: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    b = b[["time"] + cols].rename(columns={c: f"ref_{c}" for c in cols})
    return a.merge(b, on="time", how="left")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__.split("\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument(
        "cmd", choices=["direction", "bands", "breaking", "convergence", "force"]
    )
    ap.add_argument("run", type=Path, help="run dir (or sfincs.log for `convergence`)")
    ap.add_argument("--ref", type=Path, default=None, help="reference run, same mesh")
    ap.add_argument(
        "--hours", nargs="*", default=["2012-10-29T12:00", "2012-10-30T00:00"]
    )
    ap.add_argument("--shelf", nargs=2, type=float, default=list(SHELF), metavar="Z")
    ap.add_argument("--csv", type=Path, default=None)
    a = ap.parse_args(argv)
    pd.set_option(
        "display.width", 200, "display.max_rows", 500, "display.max_columns", 30
    )

    if a.cmd == "convergence":
        if a.run.is_dir():
            log, inp = a.run / "sfincs.log", read_inp(a.run)
        else:
            log, inp = a.run, read_inp(a.run.parent)
        niter = int(float(inp["snapwave_niter"])) if "snapwave_niter" in inp else None
        df = convergence_table(log, niter)
        hits = int(df["cap_hit"].sum())
        print(
            f"{log}: {len(df)} SnapWave calls, cap {df.attrs['cap']} "
            f"({df.attrs['cap_source']}) — {hits} of {len(df)} cap-hits"
        )
        print(df.to_string(index=False))
    else:
        run = load_run(a.run)
        ref = load_run(a.ref) if a.ref else None
        if a.cmd == "direction":
            df = direction_table(run)
            if ref is not None:
                df = _side_by_side(
                    df, direction_table(ref), ["model_wavdir_bnd", "delta_deg"]
                )
            n_ok, n = int(df["ok"].fillna(False).sum()), int(df["ok"].notna().sum())
            worst = df["delta_deg"].max()
            print(
                f"{run.path.name}: boundary wavdir within dtheta={df['dtheta'].iloc[0]:g}° "
                f"of the Hs-weighted imposed direction on {n_ok} of {n} hours; "
                f"worst |Δ| = {worst:.0f}° → "
                f"{'PASS' if n_ok == n else 'FAIL'}"
            )
        elif a.cmd == "bands":
            shelf = tuple(a.shelf)
            df = bands_table(run, shelf=shelf)
            n_cells = df.attrs["n"]  # _side_by_side returns a new frame without attrs
            if ref is not None:
                df = _side_by_side(
                    df, bands_table(ref, shelf=shelf), ["entry", "mid", "shelf9m"]
                )
            print(
                f"{run.path.name}: cells entry/mid/shelf9m = {n_cells}; "
                f"ratios are median hm0 / imposed median on the boundary cells; "
                f"shelf band z in {shelf}"
            )
        elif a.cmd == "breaking":
            df = breaking_table(run, a.hours)
            print(
                f"{run.path.name}: Baldock with {df.attrs['params']} "
                f"(Hmax = γ·h, opt 1); Hrms = hm0/√2"
            )
        else:
            df = force_table(run, shelf=tuple(a.shelf))
            if ref is not None:
                df = _side_by_side(
                    df,
                    force_table(ref, shelf=tuple(a.shelf)),
                    ["F_mean", "dir_cartesian_deg"],
                )
            pd.set_option("display.float_format", "{:.5g}".format)
        print(df.to_string(index=False))
    if a.csv:
        df.to_csv(a.csv, index=False)
        print(f"wrote {a.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
