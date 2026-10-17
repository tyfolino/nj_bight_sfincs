#!/usr/bin/env python
"""EurOtop (2018) mean wave-OVERTOPPING discharge over a coastal front, from a finished run's
own toe conditions, written as a point discharge source an arm can ADD (``Experiment.
extra_discharge``) — a sensitivity forcing, not physics SFINCS computes.

WHY
---
SFINCS + SnapWave carries wave SETUP (a raised mean level) but not the short-wave run-up and
overtopping that throw water over a crest the mean level never reaches. Where a back-barrier
lake sits right behind a front (Deal Lake, Wreck Pond), the model's lake can stay at its rain
level while the real lake was filled over the front. This script estimates that inflow
empirically and hands it to the solver as a source behind the crest.

INPUTS (all from the run, except the crest)
------------------------------------------
For each alongshore SEGMENT (a row of ``--segments`` CSV: name, x, y = the crest point in the
model CRS, length_m, crest columns): the TOE is the most landward ACTIVE face along the
seaward bearing whose subgrid MEAN bed is at or below ``--toe-z`` (default -1 m NAVD88: the
seaward edge of the beach, ~3.9 m deep at a 2.9 m peak, where SnapWave's depth-limited Hm0
is the incident wave on the front). At that face, every map step: Hm0 = ``hm0``, Tm-1,0 = ``tp`` / 1.1 (EurOtop's
single-peaked-spectrum ratio), SWL = ``zs`` (includes SnapWave setup at the toe; the
``swl_offshore`` scenario uses ``zs`` at the first face below ``--offshore-z`` (mean bed) instead,
a setup-free bound), wave angle beta = |wavdir - seaward bearing| (wavdir read as nautical
coming-from). Rc = crest - SWL. Slope tan(alpha) = (crest - z_toe) / distance toe->crest
(EurOtop's average-slope idea for composite profiles, taken over the whole toe-to-crest
profile of a beach-fronted promenade).

FORMULAS (mean-value approach, EurOtop 2018)
--------------------------------------------
sloping, Rc > 0   (eqs 5.10 / 5.11)::
    q/sqrt(g Hm0^3) = min( 0.023/sqrt(tan a) gb xi exp(-(2.7 Rc/(xi Hm0 gb gf gbeta gv))^1.3),
                           0.09 exp(-(1.5 Rc/(Hm0 gf gbeta g*))^1.3) )
sloping, Rc <= 0  (eqs 5.15-5.17, zero / negative freeboard)::
    q = 0.54 sqrt(g |Rc|^3) + 0.0537 xi sqrt(g Hm0^3)       (xi < 2; else 0.136 - 0.226/xi^3)
    — floored at the Rc -> 0+ value of 5.10/5.11 so q never rises with Rc.
vertical wall (eq 7.1 non-impulsive; zero freeboard 0.062; weir term below SWL)::
    q/sqrt(g Hm0^3) = 0.047 exp(-(2.35 Rc/Hm0)^1.3)
    with Hm0 = the broken wave at the wall FOOT (segments column ``z_foot``):
    min(toe Hm0, 0.5 (SWL - z_foot)), zero when the foot is dry.
xi = tan a / sqrt(Hm0 / L), L = g Tm-1,0^2 / (2 pi); gamma_beta = 1 - 0.0063 min(|beta|, 80).
Q(t) = sum over segments of q_i(t) * length_i.

⚠️ An ENVELOPE-grade estimate: EurOtop's spread is a factor ~3 either way at a given Rc/Hm0
(the mean-value approach), the toe sits in the surf zone where the short-wave Tp
understates the IG-dominated Tm-1,0, and the crest moved during the storm. The scenario
table brackets crest (pre / post / +-0.5 m), Hm0 (+-20 %), SWL (toe / offshore) and the
structure type (sloping / vertical) so the arm can be read as a bound, not a prediction.

Stockdon (2006) R2% (``stockdon_envelope.stockdon``) is printed as a sanity read: is the
crest within the run-up envelope at all?

Usage (on a compute node; reads ~5 GB of the map lazily, only the faces near the segments)::

    NJ_DOMAIN=v4_refreeze python scripts/eurotop_overtopping.py \\
        --run experiments/v4_refreeze/naccs-premier \\
        --segments logs/overtopping_2026-10-17/deal_front_segments.csv \\
        --crest-col crest_post_usace2012 --pre-crest-col crest_pre_bed2010 \\
        --seaward-bearing 102 --source-xy 585150 4453800 --source-name deal_lake_overtopping \\
        --mark 6122 --out logs/overtopping_2026-10-17
"""
from __future__ import annotations

import argparse
import hashlib
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

G = 9.81
SCRIPTS = Path(__file__).resolve().parent


# ── formulas ────────────────────────────────────────────────────────────────────────────
def gamma_beta(beta_deg):
    """EurOtop 2018 eq 5.29: obliquity factor for overtopping, |beta| capped at 80 deg."""
    b = np.minimum(np.abs(np.asarray(beta_deg, float)), 80.0)
    return 1.0 - 0.0063 * b


def xi_m10(hm0, tm10, tan_a):
    """Breaker parameter on the spectral period Tm-1,0 (deep-water wavelength)."""
    hm0, tm10 = np.asarray(hm0, float), np.asarray(tm10, float)
    L = G * tm10**2 / (2 * math.pi)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.asarray(tan_a, float) / np.sqrt(hm0 / L)


def q_sloping(hm0, tm10, tan_a, rc, gf=1.0, gbeta=1.0, gb=1.0, gv=1.0, gstar=1.0):
    """Mean overtopping discharge (m3/s per m) over a smooth impermeable slope, EurOtop 2018
    mean-value approach (eqs 5.10/5.11 for Rc > 0, 5.15-5.17 for Rc <= 0). Vectorised; 0
    where Hm0 or Tm-1,0 is not positive / finite."""
    hm0, tm10, tan_a, rc = np.broadcast_arrays(*(np.asarray(a, float) for a in (hm0, tm10, tan_a, rc)))
    gbeta = np.broadcast_to(np.asarray(gbeta, float), hm0.shape)
    ok = np.isfinite(hm0) & np.isfinite(tm10) & np.isfinite(rc) & (hm0 > 0) & (tm10 > 0)
    out = np.zeros(hm0.shape)
    h, t, ta, r, gbt = hm0[ok], tm10[ok], tan_a[ok], rc[ok], gbeta[ok]
    xi = xi_m10(h, t, ta)
    s = np.sqrt(G * h**3)

    def pos(rr):
        a = 0.023 / np.sqrt(ta) * gb * xi * np.exp(-((2.7 * rr / (xi * h * gb * gf * gbt * gv)) ** 1.3))
        b = 0.09 * np.exp(-((1.5 * rr / (h * gf * gbt * gstar)) ** 1.3))
        return np.minimum(a, b) * s

    q = pos(np.maximum(r, 0.0))
    neg = r <= 0
    if neg.any():
        x = xi[neg]
        q0 = np.where(x < 2.0, 0.0537 * x, 0.136 - 0.226 / x**3) * s[neg]
        weir = 0.54 * np.sqrt(G * np.abs(r[neg]) ** 3)
        q[neg] = np.maximum(weir + q0, q[neg])
    out[ok] = q
    return out


def q_vertical(hm0, rc):
    """Mean overtopping (m3/s per m) at a plain vertical wall, non-impulsive (EurOtop 2018
    eq 7.1, mean value); zero freeboard 0.062 sqrt(g Hm0^3) plus a weir term below SWL."""
    hm0, rc = np.broadcast_arrays(np.asarray(hm0, float), np.asarray(rc, float))
    ok = np.isfinite(hm0) & np.isfinite(rc) & (hm0 > 0)
    out = np.zeros(hm0.shape)
    h, r = hm0[ok], rc[ok]
    s = np.sqrt(G * h**3)
    q = 0.047 * np.exp(-((2.35 * np.maximum(r, 0.0) / h) ** 1.3)) * s
    neg = r <= 0
    q[neg] = np.maximum(q[neg], 0.062 * s[neg] + 0.54 * np.sqrt(G * np.abs(r[neg]) ** 3))
    out[ok] = q
    return out


# ── the run ─────────────────────────────────────────────────────────────────────────────
def find_toes(fx, fy, mask, zmin, zmax, seg, bearing_deg, toe_z, offshore_z, halfwidth, reach=600.0,
              offshore_reach=2500.0):
    """Per segment: (toe face, distance crest->toe, offshore face), local indices.

    The toe is the most landward active face in the corridor (``halfwidth`` either side of the
    seaward ray from the crest point) whose subgrid MEAN bed 0.5 (z_zmin + z_zmax) is at or
    below ``toe_z``; the offshore face is the first one at or below ``offshore_z``."""
    e = np.array([math.sin(math.radians(bearing_deg)), math.cos(math.radians(bearing_deg))])
    rows = []
    for _, r in seg.iterrows():
        dx, dy = fx - r.x, fy - r.y
        s = dx * e[0] + dy * e[1]
        n = -dx * e[1] + dy * e[0]
        zmean = 0.5 * (zmin + zmax)
        cand = (s > 0) & (np.abs(n) <= halfwidth) & (mask > 0)
        toe = np.flatnonzero(cand & (s <= reach) & (zmean <= toe_z))
        off = np.flatnonzero(cand & (s <= offshore_reach) & (zmean <= offshore_z))
        if not toe.size:
            raise SystemExit(f"segment {r['name']}: no active face with mean bed <= {toe_z} m within {reach} m")
        it = toe[np.argmin(s[toe])]
        io = off[np.argmin(s[off])] if off.size else -1
        rows.append((it, float(s[it]), io))
    return rows


def read_run(run: Path, seg: pd.DataFrame, bearing, toe_z, offshore_z, halfwidth):
    import xarray as xr

    with xr.open_dataset(run / "sfincs.nc") as g:
        fx, fy = g["mesh2d_face_x"].values, g["mesh2d_face_y"].values
        mask = g["mask"].values
    near = (np.abs(fx - seg.x.mean()) < 3500) & (np.abs(fy - seg.y.mean()) < 3500)
    idx = np.flatnonzero(near)
    with xr.open_dataset(run / "sfincs_subgrid.nc") as s:
        zmin = s["z_zmin"].values[idx]
        zmax = s["z_zmax"].values[idx]
    toes = find_toes(fx[idx], fy[idx], mask[idx], zmin, zmax, seg, bearing, toe_z, offshore_z, halfwidth)
    loc = {"toe": [idx[t[0]] for t in toes], "off": [idx[t[2]] if t[2] >= 0 else -1 for t in toes]}
    faces = sorted({f for f in loc["toe"] + loc["off"] if f >= 0})
    lo, hi = faces[0], faces[-1] + 1
    rel = np.array(faces) - lo
    ser = {}
    with xr.open_dataset(run / "sfincs_map.nc") as m:
        time = m["time"].values
        for v in ("zs", "hm0", "tp", "wavdir"):
            ser[v] = m[v].isel(nmesh2d_face=slice(lo, hi)).values[:, rel].astype(float)
    col = {f: k for k, f in enumerate(faces)}
    zi = {f: (zmin[np.searchsorted(idx, f)], zmax[np.searchsorted(idx, f)]) for f in faces}
    return dict(time=time, ser=ser, col=col, zi=zi, toes=toes, loc=loc, fx=fx, fy=fy, mask=mask)


def segment_inputs(R, seg, bearing, swl="toe"):
    """Arrays (time, segment) of Hm0, Tm-1,0, SWL, gamma_beta at the toe + per-segment z_toe, dist."""
    nt = len(R["time"])
    H, T, S, GB = (np.full((nt, len(seg)), np.nan) for _ in range(4))
    ztoe, dist = np.zeros(len(seg)), np.zeros(len(seg))
    for k in range(len(seg)):
        f = R["loc"]["toe"][k]
        c = R["col"][f]
        zmn, zmx = R["zi"][f]
        ztoe[k], dist[k] = 0.5 * (zmn + zmx), R["toes"][k][1]
        zs = R["ser"]["zs"][:, c]
        wet = np.isfinite(zs) & (zs - zmn > 0.05)
        H[:, k] = np.where(wet, R["ser"]["hm0"][:, c], np.nan)
        T[:, k] = np.where(wet, R["ser"]["tp"][:, c] / 1.1, np.nan)
        if swl == "offshore" and R["loc"]["off"][k] >= 0:
            zs = R["ser"]["zs"][:, R["col"][R["loc"]["off"][k]]]
        S[:, k] = zs
        beta = (R["ser"]["wavdir"][:, c] - bearing + 180.0) % 360.0 - 180.0
        GB[:, k] = gamma_beta(np.where(np.isfinite(beta), beta, 0.0))
    return H, T, S, GB, ztoe, dist


def overtopping(seg, crest, H, T, S, GB, ztoe, dist, formula="sloping", hm0_scale=1.0, z_foot=None,
                foot_ratio=0.5):
    """q (time, segment) in m3/s/m and Q(t) = sum q * length.

    ``vertical`` treats the steep face at the crest as a wall standing on the beach at
    ``z_foot``: its incident Hm0 is the broken-wave height there, ``foot_ratio`` x the depth
    at the foot (inner-surf saturation, Hm0/h ~ 0.4-0.6), capped by the toe Hm0 — zero when
    the SWL is below the foot (then only run-up reaches it, and ``sloping`` is the formula)."""
    Hs = H * hm0_scale
    rc = crest[None, :] - S
    if formula == "sloping":
        tan_a = (crest - ztoe) / dist
        q = q_sloping(Hs, T, tan_a[None, :], rc, gbeta=GB)
    else:
        if z_foot is None:
            raise ValueError("vertical needs z_foot (the beach level at the wall foot)")
        Hs = np.minimum(Hs, foot_ratio * np.maximum(S - np.asarray(z_foot, float)[None, :], 0.0))
        Hs = np.where(Hs > 0, Hs, np.nan)
        q = q_vertical(Hs, rc)
    q = np.where(np.isfinite(Hs), q, 0.0)
    return q, q @ seg["length_m"].to_numpy(float)


def write_source_nc(path: Path, name: str, lon: float, lat: float, time, Q, note: str = "") -> None:
    """One-point discharge GeoDataset in the catalog's format (time, index; lon/lat; m3/s)."""
    import xarray as xr

    ds = xr.Dataset(
        {"discharge": (("time", "index"), np.asarray(Q, float)[:, None])},
        coords={
            "time": np.asarray(time, "datetime64[ns]"),
            "index": [0],
            "lon": ("index", [float(lon)]),
            "lat": ("index", [float(lat)]),
            "area_scale": ("index", [1.0]),
            "name": ("index", [name]),
        },
        attrs={"units": "m3/s", "title": f"empirical wave-overtopping inflow: {name}", "note": note},
    )
    ds["discharge"].attrs = {"units": "m3/s", "long_name": "wave overtopping discharge"}
    tmp = path.with_name(path.name + ".tmp")
    ds.to_netcdf(tmp)
    tmp.replace(path)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run", required=True, type=Path)
    p.add_argument("--segments", required=True, type=Path)
    p.add_argument("--crest-col", required=True, help="recommended crest column")
    p.add_argument("--pre-crest-col", default=None, help="the other crest (scenario)")
    p.add_argument("--seaward-bearing", type=float, required=True, help="deg nautical, crest -> sea")
    p.add_argument("--toe-z", type=float, default=-1.0, help="toe = first face with mean bed <= this")
    p.add_argument("--offshore-z", type=float, default=-8.0, help="setup-free SWL face: mean bed <= this")
    p.add_argument("--halfwidth", type=float, default=13.0, help="corridor half-width (m)")
    p.add_argument("--stockdon-buoy", type=float, nargs=2, default=(9.65, 14.8), metavar=("H0", "T"),
                   help="a buoy H0 / period for the second Stockdon read (NDBC 44025 Sandy max, §49)")
    p.add_argument("--formula", choices=("sloping", "vertical"), default="sloping")
    p.add_argument("--source-xy", type=float, nargs=2, required=True, help="target point, model CRS")
    p.add_argument("--source-zmax", type=float, default=1.0, help="source face must lie wholly below")
    p.add_argument("--source-name", default="overtopping")
    p.add_argument("--mark", default=None, help="HWM id to report the source distance to")
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args(argv)

    import pyproj
    import xarray as xr

    sys.path.insert(0, str(SCRIPTS))
    from stockdon_envelope import deshoal, stockdon  # noqa: E402

    a.out.mkdir(parents=True, exist_ok=True)
    seg = pd.read_csv(a.segments)
    R = read_run(a.run, seg, a.seaward_bearing, a.toe_z, a.offshore_z, a.halfwidth)
    time = R["time"]
    epsg = 32618
    to_ll = pyproj.Transformer.from_crs(epsg, 4326, always_xy=True)

    # toe table
    H, T, S, GB, ztoe, dist = segment_inputs(R, seg, a.seaward_bearing)
    _, _, S_off, _, _, _ = segment_inputs(R, seg, a.seaward_bearing, swl="offshore")
    toe_rows = []
    for k, (_, r) in enumerate(seg.iterrows()):
        f = R["loc"]["toe"][k]
        lon, lat = to_ll.transform(R["fx"][f], R["fy"][f])
        it = int(np.nanargmax(np.where(np.isfinite(S[:, k]), S[:, k], -9)))
        toe_rows.append(dict(name=r["name"], toe_face=f, toe_lon=round(lon, 5), toe_lat=round(lat, 5),
                             z_toe=round(ztoe[k], 2), dist_m=round(dist[k], 1),
                             tan_a=round((r[a.crest_col] - ztoe[k]) / dist[k], 4),
                             peak_time=str(time[it])[:16], swl_peak=round(S[it, k], 3),
                             swl_off_peak=round(np.nanmax(S_off[:, k]), 3),
                             hm0_at_peak=round(H[it, k], 2), tm10_at_peak=round(T[it, k], 2),
                             gbeta_at_peak=round(GB[it, k], 3)))
    toe_df = pd.DataFrame(toe_rows)
    toe_df.to_csv(a.out / "toe_faces.csv", index=False)
    print(toe_df.to_string(index=False))

    # scenarios
    crest0 = seg[a.crest_col].to_numpy(float)
    sc = [("RECOMMENDED", a.crest_col, 0.0, 1.0, "toe", a.formula)]
    for dz in (-0.5, 0.5):
        sc.append((f"crest{dz:+.1f}", a.crest_col, dz, 1.0, "toe", a.formula))
    for f in (0.8, 1.2):
        sc.append((f"hm0x{f:.1f}", a.crest_col, 0.0, f, "toe", a.formula))
    if a.pre_crest_col:
        sc.append(("pre_crest", a.pre_crest_col, 0.0, 1.0, "toe", a.formula))
    sc.append(("swl_offshore", a.crest_col, 0.0, 1.0, "offshore", a.formula))
    other = "vertical" if a.formula == "sloping" else "sloping"
    if other == "sloping" or "z_foot" in seg:
        sc.append((f"formula_{other}", a.crest_col, 0.0, 1.0, "toe", other))
    zfoot = seg["z_foot"].to_numpy(float) if "z_foot" in seg else None
    dt = np.diff(time).astype("timedelta64[s]").astype(float)
    summ, Qs = [], {}
    for lab, ccol, dz, hs, swl, form in sc:
        crest = seg[ccol].to_numpy(float) + dz
        Sx = S if swl == "toe" else S_off
        q, Q = overtopping(seg, crest, H, T, Sx, GB, ztoe, dist, formula=form, hm0_scale=hs, z_foot=zfoot)
        vol = float(np.sum(0.5 * (Q[1:] + Q[:-1]) * dt))  # trapezoid = what SFINCS integrates
        hrs = float(np.sum(Q > 0.01) * np.median(dt) / 3600.0)
        summ.append(dict(scenario=lab, crest=ccol, crest_dz=dz, hm0_scale=hs, swl=swl, formula=form,
                         q_peak_max_seg=round(float(q.max()), 4), Q_peak=round(float(Q.max()), 3),
                         Q_peak_time=str(time[int(np.argmax(Q))])[:16], volume_m3=round(vol),
                         hours_Q_gt_0p01=hrs, n_seg_q_gt_1lps=int((q.max(axis=0) > 0.001).sum())))
        Qs[lab] = Q
        if lab == "RECOMMENDED":
            qdf = pd.DataFrame(q, columns=seg["name"], index=pd.DatetimeIndex(time, name="time"))
            qdf.insert(0, "Q_m3s", Q)
            qdf.round(5).to_csv(a.out / "q_segments_recommended.csv")
    sdf = pd.DataFrame(summ)
    sdf.to_csv(a.out / "scenarios.csv", index=False)
    pd.DataFrame(Qs, index=pd.DatetimeIndex(time, name="time")).round(4).to_csv(a.out / "Q_scenarios.csv")
    print(sdf.to_string(index=False))

    # Stockdon (2006) sanity read, every map step at the first segment's offshore face: H0 by
    # reverse-shoaling the model's own Hm0 there, beta_f = the segments' median beach slope;
    # plus one read with a buoy's Sandy maximum at the SWL peak. R2% is an UPPER envelope
    # (stockdon_envelope.py docstring), compared with the crest, not differenced against it.
    ko = next((R["loc"]["off"][k] for k in range(len(seg)) if R["loc"]["off"][k] >= 0), -1)
    lines = []
    if ko >= 0:
        c = R["col"][ko]
        zb_off = 0.5 * sum(R["zi"][ko])
        zs, hm, tp = (R["ser"][v][:, c] for v in ("zs", "hm0", "tp"))
        bfs = {"post": float(seg["beach_slope"].median())} if "beach_slope" in seg else {"default": 0.03}
        if "beach_slope_pre" in seg:
            bfs["pre"] = float(seg["beach_slope_pre"].median())
        isw = int(np.nanargmax(zs))
        for lab, bf in bfs.items():
            r2 = np.full(len(time), np.nan)
            for t in range(len(time)):
                if np.isfinite(hm[t]) and hm[t] > 0 and np.isfinite(zs[t]):
                    r2[t] = stockdon(deshoal(hm[t], tp[t], zs[t] - zb_off), tp[t], bf)[2]
            el = zs + r2
            it = int(np.nanargmax(el))
            lines.append(f"model H0, beta_f {lab} {bf:.3f}: max SWL+R2% {el[it]:.2f} m at {str(time[it])[:16]} "
                         f"(SWL {zs[it]:.2f}, Hm0 {hm[it]:.2f} at {zs[it] - zb_off:.1f} m depth, Tp {tp[it]:.1f}, "
                         f"R2 {r2[it]:.2f}); at the SWL peak {str(time[isw])[:16]}: {zs[isw]:.2f} + {r2[isw]:.2f} "
                         f"= {el[isw]:.2f} m")
            H0b, Tb = a.stockdon_buoy
            eta, Ssw, R2b = stockdon(H0b, Tb, bf)
            lines.append(f"buoy H0 {H0b} T {Tb}, beta_f {lab} {bf:.3f}: setup {eta:.2f} swash {Ssw:.2f} R2% {R2b:.2f}"
                         f" -> {zs[isw]:.2f} + {R2b:.2f} = {zs[isw] + R2b:.2f} m at the SWL peak")
        lines.append(f"crest {a.crest_col} {np.nanmin(crest0):.2f}..{np.nanmax(crest0):.2f} m"
                     + (f"; {a.pre_crest_col} {seg[a.pre_crest_col].min():.2f}..{seg[a.pre_crest_col].max():.2f}"
                        if a.pre_crest_col else ""))
        print("\n[stockdon] offshore face", ko, "\n  " + "\n  ".join(lines))
        (a.out / "stockdon_check.txt").write_text("\n".join(lines) + "\n")

    # source face: nearest active face wholly below --source-zmax to the target point
    fx, fy, mask = R["fx"], R["fy"], R["mask"]
    d2 = (fx - a.source_xy[0]) ** 2 + (fy - a.source_xy[1]) ** 2
    cand = np.flatnonzero((d2 < 300.0**2) & (mask > 0))
    with xr.open_dataset(a.run / "sfincs_subgrid.nc") as s:
        czmax = s["z_zmax"].values[cand]
    ok = cand[czmax <= a.source_zmax]
    if not ok.size:
        raise SystemExit("no active lake face wholly below --source-zmax within 300 m of --source-xy")
    fsrc = ok[np.argmin(d2[ok])]
    sx, sy = float(fx[fsrc]), float(fy[fsrc])
    slon, slat = to_ll.transform(sx, sy)
    msg = f"source face {fsrc} at ({sx:.1f}, {sy:.1f}) = ({slon:.5f}, {slat:.5f})"
    if a.mark:
        import geopandas as gpd

        from nj_sfincs import domain as _domain

        hw = gpd.read_file(_domain.active().hwm_geojson)
        hw = hw[hw["hwm_id"].astype(str) == str(a.mark)].to_crs(epsg)
        dm = float(np.hypot(hw.geometry.x.iloc[0] - sx, hw.geometry.y.iloc[0] - sy))
        msg += f"; {dm:.0f} m from mark {a.mark}" + ("" if dm > 500 else "  ⚠️ < 500 m (injection trap)")
    print("\n[source] " + msg)
    nc = a.out / f"{a.source_name}.nc"
    note = (f"EurOtop 2018 {a.formula} mean-value q x segment length, summed; run {a.run}; segments "
            f"{a.segments.name} crest {a.crest_col}; toe mean bed <= {a.toe_z} m; " + msg)
    write_source_nc(nc, a.source_name, slon, slat, time, Qs["RECOMMENDED"], note)
    print(f"[source] wrote {nc}  sha256 {hashlib.sha256(nc.read_bytes()).hexdigest()[:16]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
