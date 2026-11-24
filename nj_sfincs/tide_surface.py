"""De-noised tidal high water for the calm (no-storm) tide runs. 2026-11-23.

    NJ_DOMAIN=<domain> python -m nj_sfincs.tide_surface <run_dir> <out.nc> [--check <tide_stats.nc>]

WHY. Some thin "bank faces" (mostly land, a sliver of deep channel inside the square) ring at 10-60 s
periods. Every 3 h ``zsmax`` block catches a crest, so the mean higher-high computed from ``zsmax`` comes out
0.1-0.9 m too high on them (Sewaren face 4365180: mean zs -0.02 m against its neighbours but mhh 1.93 m; the
channel 0.94 m). ``logs/bank_face_sweep_2026-11-15/README.md`` (size, sites) and ``ROOT_CAUSE.md`` (a lightly
damped resonator in the subgrid tables). The user decided (2026-11-23) to de-noise the water SURFACE before
any scoring: a face whose high water is rectified noise gets the high water of its quiet open-water
neighbours. Everything else keeps its own.

PER FACE, from the run's own ``sfincs_map.nc``:

* daily higher-high ``HH[d]`` = max of the 3 h ``zsmax`` blocks in tidal day d (24.84 h) after a 2.5 d
  spin-up; ``mean_higher_high`` = mean over the days the face was wet (MHHW of the run), ``max_month`` =
  the highest, ``days_wet`` = days with a finite HH. Bit-identical to ``logs/mhhw_v2_2026-11-12/mhhw_maps.py
  tide_stats`` (same order of summation, float64 accumulator). A face is DRAWN (wet) when ``days_wet`` >=
  half the days, the products' own rule.
* REFERENCE (``logs/bank_face_sweep_2026-11-15/sweep.py`` with ``--q 0.2``): the 0.2 quantile of the mhh of
  the SUBMERGED other drawn faces (``z_zmax`` < their own mhh: open water, which a bank face never is) whose
  centres lie within max(150 m, 1.5 dx); all drawn neighbours where fewer than 4 are submerged; none (class
  ``no_ref``) where fewer than 4 exist. The low quantile because noise can only RAISE a maximum: even
  submerged faces next to a ringing bank read high. ``ref_max`` is the same for the month max.
* FLAGGED: ``excess`` = mhh - ref > 0.10 m.
* TOLD APART with the 6 h ``zs`` snapshots (the sweep only described this; here it decides). For each flagged
  face and each post-spin-up snapshot where the face is wet (h > 0.01 m): r = zs - median zs of its
  REFERENCE WATER, the neighbours whose own mhh sets the reference (within 0.05 m of it, at least the 4
  lowest; ``reference_rows``), >= 4 of them wet. Same water body as the high-water test: quiet open water
  beside a ringing bank, the LOWER pool beside a sill (a plain median of all neighbours would sit in the upper
  pool and call a real step noise; a low quantile of instantaneous levels would be biased low wherever the
  neighbours ring, and call noise held). A snapshot is an unbiased sample of the instantaneous surface,
  so water that really stands higher (behind a sill, a culvert, a marsh lip) shows up as a POSITIVE MEAN r,
  comparable to the excess. A rectified oscillation does not: its r averages to about zero, whatever its
  spread (an oscillation that only rings near high water shows little spread in 6-hourly samples, so spread
  is reported but does not decide). The mean over the HIGH-WATER snapshots (the reference water's median in
  its top quartile for that face) DECIDES: the higher-high describes high water, and water a sliver holds at
  low tide (draining slowly) does not raise it. The all-snapshot mean is reported.

  - ``noise``        high-water mean r < 0.5 x excess, with >= 8 wet snapshots and >= 4 at high water:
                     REPLACED, mhh := min(raw, ref + step), the max := min(raw, ref_max + step), step =
                     max(0, high-water mean r - 2 standard errors): the reference water's high water plus
                     whatever the face really stands above it at high water (~0 for a rectified face).
  - ``held_mild``    high-water mean r >= 0.5 x excess and excess <= 0.25 m: KEPT, reported (the sweep's
                     "mild class", positive mean residual).
  - ``held_strong``  the same with excess > 0.25 m: KEPT, reported.
  - ``untested``     flagged but too few wet snapshots (mostly the "film" faces, whose water is a cm-thin
                     film over their lowest pixel; mhh - z_zmin < 0.10 m, so they can never reach the 0.15 m
                     site rule): KEPT, reported.

  The 0.5 is a judgement, not a gap: on the 1.1.0 runs the high-water r / excess of the deep tested faces
  piles up at <= 0 and >= 1 but spreads in between (~20-25 % of faces in 0.25-0.75). The standing step makes
  a mid-range call cheap: a noise face keeps the part it really stands higher. 0.25 and 0.75 give the same
  site counts (logs/denoised_mhhw_2026-11-23/README.md).

OUTPUT (netCDF, atomic write): ``mean_higher_high``, ``max_month`` (DE-NOISED), ``days_wet`` and attr
``ndays`` under the names ``mhhw_maps.py`` reads, so ``mhhw_maps.py tide <arm> <s> <prefix> --tide-stats
<out.nc> --noisy none`` draws the de-noised maps with no code change; plus ``*_raw``, ``ref_mhh``,
``ref_max``, ``excess``, ``denoise_class`` (flag_values / flag_meanings), ``film``, ``ref_from_submerged``
and the snapshot statistics. A ``<out>.json`` summary sits beside it.

The mechanism is OPEN (ROOT_CAUSE.md): this is a read-side correction of a model artefact, not a fix of
the solve. It never touches the storm (Sandy) peaks.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

SPINUP_D = 2.5  # days skipped before the analysis window
DAY_H = 24.84  # tidal day (h)
MIN_NB = 4  # neighbours needed for a reference / a snapshot residual
REF_Q = 0.2  # neighbour quantile of the reference
RADIUS_M = 150.0  # neighbour radius: max(RADIUS_M, RADIUS_DX * dx)
RADIUS_DX = 1.5
K_NB = 128  # most neighbours kept per face
HIGH_M = 0.10  # flag: excess over the reference
MILD_TOP_M = 0.25  # held_mild / held_strong split
FILM_M = 0.10  # film face: mhh - z_zmin below this (cannot reach the 0.15 m site rule)
HELD_FRAC = 0.5  # held when a mean snapshot residual >= HELD_FRAC x excess
MIN_SNAPS = 8  # wet snapshots needed to test a face
MIN_HW_SNAPS = 4  # ... of which at high water
HW_Q = 0.75  # high-water snapshots: reference-water median zs at or above this quantile (per face)
REF_TOL_M = (
    0.05  # reference water: neighbours whose mhh is within this of the reference
)
DRY_H = 0.01  # a snapshot face is wet when zs - zb > DRY_H (huthresh)

NOT_DRAWN, OK, NO_REF, NOISE, HELD_MILD, HELD_STRONG, UNTESTED = -1, 0, 1, 2, 3, 4, 5
CLASS_NAMES = {
    NOT_DRAWN: "not_drawn",
    OK: "ok",
    NO_REF: "no_ref",
    NOISE: "noise",
    HELD_MILD: "held_mild",
    HELD_STRONG: "held_strong",
    UNTESTED: "untested",
}


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


# ---------------------------------------------------------------- daily high water (pure)
def tidal_days(hours, day_h=DAY_H):
    """Per zsmax block (hours after the analysis start, at the block's END): its tidal day, the number
    of whole tidal days, and whether the block is used."""
    hours = np.asarray(hours, float)
    day = np.floor((hours - 1e-6) / day_h).astype(int)
    nd = int(np.floor(hours.max() / day_h)) if hours.size else 0
    use = (hours > 0) & (day < nd)
    return day, nd, use


def daily_higher_high(read, hours, nf, day_h=DAY_H):
    """(n_days, nf) float32 daily maxima of the zsmax blocks; ``read(i)`` returns block i (fill < -1000)."""
    day, nd, use = tidal_days(hours, day_h)
    if nd < 1:
        raise ValueError("no whole tidal day after the spin-up")
    HH = np.full((nd, nf), np.nan, np.float32)
    for i in np.flatnonzero(use):
        z = np.asarray(read(i), np.float32)
        HH[day[i]] = np.fmax(HH[day[i]], np.where(z < -1000, np.float32(np.nan), z))
    return HH


def day_statistics(HH):
    """mean higher-high (float32), month max (float32), days wet (int16): mhhw_maps.tide_stats' arithmetic."""
    nf = HH.shape[1]
    total, count = np.zeros(nf), np.zeros(nf, np.int16)
    peak = np.full(nf, np.nan, np.float32)
    for hh in HH:
        ok = np.isfinite(hh)
        total[ok] += hh[ok]
        count[ok] += 1
        peak = np.fmax(peak, hh)
    mhh = np.where(count > 0, total / np.maximum(count, 1), np.nan).astype(np.float32)
    return mhh, peak, count


# ---------------------------------------------------------------- the local reference (pure)
def neighbours(x, y, R, k=K_NB, workers=8):
    """(n, k) indices of the OTHER points within R (per point, sorted); n = none."""
    from scipy.spatial import cKDTree

    x, y, R = np.asarray(x, float), np.asarray(y, float), np.asarray(R, float)
    tree = cKDTree(np.c_[x, y])
    out = np.full((x.size, k), x.size, np.int32)
    kk = min(k + 1, x.size)
    for Rv in np.unique(R):
        sel = np.flatnonzero(R == Rv)
        for a in range(0, sel.size, 200_000):
            s = sel[a : a + 200_000]
            _, ii = tree.query(
                np.c_[x[s], y[s]], k=kk, distance_upper_bound=Rv, workers=workers
            )
            ii = ii.reshape(s.size, kk)
            ii[ii == s[:, None]] = x.size  # drop self
            ii = np.sort(ii, axis=1)[:, :k]
            out[s, : ii.shape[1]] = ii
    return out


def local_quantile(v, nb, q, minn=MIN_NB, workers=8):
    """q-quantile ("lower") of v over each row of neighbour indices; NaN where < minn finite values."""
    vv = np.append(np.asarray(v, np.float32), np.float32(np.nan))
    out = np.full(nb.shape[0], np.nan, np.float32)
    cnt = np.zeros(nb.shape[0], np.int16)
    ed = np.linspace(0, nb.shape[0], max(workers * 8, 1) + 1).astype(int)

    def job(i):
        a, b = ed[i], ed[i + 1]
        if a == b:
            return
        s = vv[nb[a:b]]
        c = np.isfinite(s).sum(1)
        m = np.full(b - a, np.nan, np.float32)
        r = c >= max(
            minn, 1
        )  # no all-NaN row reaches nanquantile (its warning is per thread)
        if r.any():
            if q == 0.5:
                m[r] = np.nanmedian(s[r], axis=1)
            else:
                m[r] = np.nanquantile(s[r], q, axis=1, method="lower")
        out[a:b], cnt[a:b] = m, c

    with ThreadPoolExecutor(workers) as p:
        list(p.map(job, range(len(ed) - 1)))
    return out, cnt


def local_reference(x, y, dx, mhh, mx, z_zmax, q=REF_Q, workers=8, k=K_NB):
    """Reference high water per drawn face (arrays over the drawn faces only). Returns a dict with
    ``ref``, ``ref_max``, ``ref_from_submerged``, ``submerged`` and ``nb`` ((n, k) neighbour rows)."""
    R = np.maximum(RADIUS_M, RADIUS_DX * np.asarray(dx, float))
    nb = neighbours(x, y, R, k=k, workers=workers)
    subm = np.asarray(z_zmax) < mhh
    ref, _ = local_quantile(np.where(subm, mhh, np.nan), nb, q, workers=workers)
    ref_max, _ = local_quantile(np.where(subm, mx, np.nan), nb, q, workers=workers)
    use_sub = np.isfinite(ref)
    fb = np.flatnonzero(~use_sub)  # fall back to every drawn neighbour
    if fb.size:
        ref[fb], _ = local_quantile(mhh, nb[fb], q, workers=workers)
        ref_max[fb], _ = local_quantile(mx, nb[fb], q, workers=workers)
    return dict(
        ref=ref, ref_max=ref_max, ref_from_submerged=use_sub, submerged=subm, nb=nb
    )


def reference_rows(
    nb_rows, W, submerged, use_sub, mhh_W, ref, tol=REF_TOL_M, nmin=MIN_NB
):
    """The REFERENCE WATER of each flagged face, as FULL face indices (n, k), -1 = none: of the neighbours
    the reference was taken from (the submerged ones, or all drawn ones on the fallback), those whose own mhh
    is within ``tol`` of the reference (at least the ``nmin`` lowest). These are the faces whose high water
    SETS the reference: quiet open water beside a ringing bank, the lower pool beside a sill. Their median zs
    is the snapshot reference, so the instantaneous test compares the face with the same water body as the
    high-water test, without the low bias a low quantile of noisy instantaneous levels would carry.
    ``nb_rows`` index the drawn faces (``W``); ``submerged`` / ``mhh_W`` are over the drawn faces; ``use_sub``
    and ``ref`` over the rows."""
    n = W.size
    ok = nb_rows < n
    safe = np.minimum(nb_rows, n - 1)
    elig = ok & (submerged[safe] | ~use_sub[:, None]) & np.isfinite(mhh_W[safe])
    v = np.where(elig, mhh_W[safe], np.inf)
    rank = np.argsort(np.argsort(v, axis=1, kind="stable"), axis=1, kind="stable")
    keep = elig & ((v <= ref[:, None] + tol) | (rank < nmin))
    return np.where(keep, W[safe], -1)


# ---------------------------------------------------------------- snapshot residuals (pure)
def snapshot_residuals(snaps, faces, nb_faces, q=0.5, minn=MIN_NB):
    """For each snapshot (1-D zs over ALL faces, NaN = dry): r = zs[face] - the q-quantile (median by
    default; "lower" otherwise) of zs over the wet faces of ``nb_faces`` (the reference water,
    ``reference_rows``). Returns (R, REF), float32 (n_snapshots, n_faces), NaN where undefined (the face dry,
    or < minn reference faces wet)."""
    Rs, REFs = [], []
    idx = None
    for z in snaps:
        v = np.append(np.asarray(z, np.float32), np.float32(np.nan))
        if idx is None:
            idx = np.where(nb_faces >= 0, nb_faces, v.size - 1)
        s = v[idx]
        ok = np.isfinite(s).sum(1) >= max(minn, 1)
        ref = np.full(s.shape[0], np.nan, np.float32)
        if ok.any():
            if q == 0.5:
                ref[ok] = np.nanmedian(s[ok], axis=1)
            else:
                ref[ok] = np.nanquantile(s[ok], q, axis=1, method="lower")
        REFs.append(ref)
        Rs.append((v[faces] - ref).astype(np.float32))
    shape = (0, len(faces))
    R = np.array(Rs, np.float32) if Rs else np.zeros(shape, np.float32)
    REF = np.array(REFs, np.float32) if REFs else np.zeros(shape, np.float32)
    return R, REF


def residual_stats(R, REF, hw_q=HW_Q):
    """Per face: wet snapshots n, mean, std of r; high-water snapshots (the neighbours' quantile at or above its
    hw_q quantile over the snapshots where the neighbours are defined) n_hw, mean_hw, std_hw."""
    ok = np.isfinite(R)
    n = ok.sum(0).astype(np.int16)
    with warnings.catch_warnings(), np.errstate(all="ignore"):
        warnings.simplefilter("ignore")
        mean = np.nanmean(R, 0)
        std = np.nanstd(R, 0)
        thr = (
            np.nanquantile(REF, hw_q, axis=0)
            if REF.shape[0]
            else np.full(R.shape[1], np.nan)
        )
        hw = ok & (REF >= thr[None, :])
        n_hw = hw.sum(0).astype(np.int16)
        mean_hw = np.where(
            n_hw > 0, np.where(hw, R, 0).sum(0) / np.maximum(n_hw, 1), np.nan
        )
        var_hw = np.where(hw, (R - mean_hw[None, :]) ** 2, 0).sum(0) / np.maximum(
            n_hw, 1
        )
        std_hw = np.where(n_hw > 0, np.sqrt(var_hw), np.nan)
    return dict(
        n=n,
        mean=mean.astype(np.float32),
        std=std.astype(np.float32),
        n_hw=n_hw,
        mean_hw=mean_hw.astype(np.float32),
        std_hw=std_hw.astype(np.float32),
    )


# ---------------------------------------------------------------- decision (pure)
def classify(
    excess,
    snap_n,
    snap_mean,
    snap_n_hw,
    snap_mean_hw,
    high=HIGH_M,
    mild_top=MILD_TOP_M,
    held_frac=HELD_FRAC,
    min_snaps=MIN_SNAPS,
    min_hw=MIN_HW_SNAPS,
):
    """Class per drawn face (module docstring). Snapshot arrays may be NaN / 0 off the flagged faces.
    The decision rests on the HIGH-WATER mean residual: the higher-high describes high water, and water a face
    holds at LOW tide (a sliver draining slowly) does not make its high water higher. ``snap_mean`` (all wet
    snapshots) is accepted for the record and does not decide."""
    e = np.asarray(excess, float)
    flagged = np.nan_to_num(e, nan=-9.0) > high
    cls = np.full(e.shape, OK, np.int8)
    cls[~np.isfinite(e)] = NO_REF
    tested = (
        flagged & (np.asarray(snap_n) >= min_snaps) & (np.asarray(snap_n_hw) >= min_hw)
    )
    with np.errstate(invalid="ignore"):
        lim = held_frac * e
        held = tested & (np.nan_to_num(snap_mean_hw, nan=-np.inf) >= lim)
    cls[flagged] = UNTESTED
    cls[tested & ~held] = NOISE
    cls[held & (e <= mild_top)] = HELD_MILD
    cls[held & (e > mild_top)] = HELD_STRONG
    return cls


def standing_step(mean_hw, std_hw, n_hw, k=2.0):
    """The step a face really stands above its reference water at high water: the high-water mean residual
    less ``k`` standard errors, floored at 0 (a ringing face's mean is mostly sampling noise; a standing step
    has little spread and survives)."""
    with np.errstate(all="ignore"):
        se = np.asarray(std_hw, float) / np.sqrt(np.maximum(np.asarray(n_hw, float), 1))
        return np.maximum(
            np.nan_to_num(np.asarray(mean_hw, float) - k * se, nan=0.0), 0.0
        )


def denoise(mhh, mx, ref, ref_max, cls, step=None):
    """NOISE faces: high water := reference + the face's STANDING step at high water (``step``, from
    ``standing_step``; 0 when not given), never above the raw value. A rectified
    face has step ~0 and takes its reference water's high water; a face that stands partly higher keeps that
    part. Returns (mhh, max), float32."""
    rep = np.asarray(cls) == NOISE
    st = 0.0 if step is None else np.maximum(np.nan_to_num(step, nan=0.0), 0.0)
    mhh_dn = np.where(rep, np.fmin(mhh, ref + st), mhh).astype(np.float32)
    mx_dn = np.where(rep & np.isfinite(ref_max), np.fmin(mx, ref_max + st), mx).astype(
        np.float32
    )
    return mhh_dn, mx_dn


# ---------------------------------------------------------------- run I/O
def read_inp(d: Path) -> dict:
    return {
        ln.split("=")[0].strip(): ln.split("=", 1)[1].strip()
        for ln in (Path(d) / "sfincs.inp").read_text().splitlines()
        if "=" in ln
    }


def load_mesh(d: Path) -> dict:
    import netCDF4

    d = Path(d)
    with netCDF4.Dataset(d / "sfincs.nc") as g:
        g.set_auto_mask(False)
        G = {k: g[k][:] for k in ("level", "mask")}
        G["x"], G["y"] = g["mesh2d_face_x"][:], g["mesh2d_face_y"][:]
        dx0 = float(g.dx)
    G["dx"] = dx0 / 2.0 ** (G["level"] - 1)
    with netCDF4.Dataset(d / "sfincs_subgrid.nc") as s:
        s.set_auto_mask(False)
        G["z_zmin"], G["z_zmax"] = s["z_zmin"][:], s["z_zmax"][:]
    return G


def _hours(t0, an, secs):
    import pandas as pd

    t = t0 + pd.to_timedelta(np.asarray(secs, float), unit="s")
    return np.asarray((t - an) / pd.Timedelta(hours=1), float)


def build(
    run_dir,
    out_nc,
    *,
    q=REF_Q,
    high=HIGH_M,
    held_frac=HELD_FRAC,
    spinup_d=SPINUP_D,
    day_h=DAY_H,
    workers=8,
    check=None,
):
    """De-noise one calm tide run (module docstring). Writes ``out_nc`` + ``<out_nc>.json``; returns the summary."""
    import netCDF4
    import pandas as pd

    t00 = time.time()
    d = Path(run_dir).resolve()
    out_nc = Path(out_nc)
    G = load_mesh(d)
    act = G["mask"] > 0
    nf = act.size
    inp = read_inp(d)
    t0 = pd.Timestamp(pd.to_datetime(inp["tref"], format="%Y%m%d %H%M%S"))
    an = t0 + pd.Timedelta(days=spinup_d)
    with netCDF4.Dataset(d / "sfincs_map.nc") as m:
        m.set_auto_mask(False)
        if m.dimensions["nmesh2d_face"].size != nf:
            raise SystemExit(
                f"{d}: sfincs_map.nc and sfincs.nc disagree on the face count"
            )
        hmax = _hours(t0, an, m["timemax"][:])
        blk = float(np.median(np.diff(hmax)))
        if abs(blk - 3.0) > 1e-6:
            log(f"WARNING: zsmax block is {blk} h, not 3 h")
        HH = daily_higher_high(lambda i: m["zsmax"][i], hmax, nf, day_h)
        snap = np.flatnonzero(_hours(t0, an, m["time"][:]) > 0)
    nd = HH.shape[0]
    mhh, mx, days = day_statistics(HH)
    del HH
    log(f"{d.name}: {nd} tidal days from {an}, {snap.size} zs snapshots after it")
    chk = {}
    if check:
        import xarray as xr

        with xr.open_dataset(check) as t:
            chk = dict(
                tide_stats=str(check),
                mhh_absdiff_max=float(
                    np.nanmax(np.abs(mhh - t.mean_higher_high.values))
                ),
                max_absdiff_max=float(np.nanmax(np.abs(mx - t.max_month.values))),
                days_equal=bool((days == t.days_wet.values).all()),
                ndays_equal=int(t.attrs["ndays"]) == nd,
            )
        log("vs existing tide_stats", chk)
    need = (nd + 1) // 2
    drawn = act & (days >= need) & np.isfinite(mhh)
    W = np.flatnonzero(drawn)
    log(f"{int(act.sum())} active, {W.size} drawn (wet >= {need} of {nd} days)")
    r = local_reference(
        G["x"][W],
        G["y"][W],
        G["dx"][W],
        mhh[W],
        mx[W],
        G["z_zmax"][W],
        q=q,
        workers=workers,
    )
    excess = mhh[W] - r["ref"]
    cand = np.flatnonzero(np.nan_to_num(excess, nan=-9.0) > high)
    F = W[cand]
    nbF = reference_rows(
        r["nb"][cand],
        W,
        r["submerged"],
        r["ref_from_submerged"][cand],
        mhh[W],
        r["ref"][cand],
    )
    log(f"flagged {F.size} (> {high} m over the q{q:g} reference); reading snapshots")
    with netCDF4.Dataset(d / "sfincs_map.nc") as m:
        m.set_auto_mask(False)
        zb = np.asarray(m["zb"][:], np.float32)

        def snaps():
            for i in snap:
                z = np.asarray(m["zs"][i], np.float32)
                yield np.where((z > -1000) & (z - zb > DRY_H), z, np.float32(np.nan))

        R, REF = snapshot_residuals(snaps(), F, nbF, q=0.5)
    st = residual_stats(R, REF)
    del R, REF
    nW = W.size
    sn, sm, ss = (
        np.zeros(nW, np.int16),
        np.full(nW, np.nan, np.float32),
        np.full(nW, np.nan, np.float32),
    )
    shn, shm = np.zeros(nW, np.int16), np.full(nW, np.nan, np.float32)
    shs = np.full(nW, np.nan, np.float32)
    sn[cand], sm[cand], ss[cand], shn[cand], shm[cand], shs[cand] = (
        st["n"],
        st["mean"],
        st["std"],
        st["n_hw"],
        st["mean_hw"],
        st["std_hw"],
    )
    cW = classify(excess, sn, sm, shn, shm, high=high, held_frac=held_frac)
    step = standing_step(shm, shs, shn)
    mhh_dn_W, mx_dn_W = denoise(mhh[W], mx[W], r["ref"], r["ref_max"], cW, step=step)

    def full(vals, fill, dtype):
        a = np.full(nf, fill, dtype)
        a[W] = vals
        return a

    cls = full(cW, NOT_DRAWN, np.int8)
    mhh_dn, mx_dn = mhh.copy(), mx.copy()
    mhh_dn[W], mx_dn[W] = mhh_dn_W, mx_dn_W
    film = full((mhh[W] - G["z_zmin"][W]) < FILM_M, 0, np.int8)
    rep = cls == NOISE
    dmhh = (mhh - mhh_dn)[rep]
    dmax = (mx - mx_dn)[rep]

    counts = {CLASS_NAMES[k]: int((cls == k).sum()) for k in CLASS_NAMES}
    fl = cls >= NOISE
    summ = dict(
        run_dir=str(d),
        out=str(out_nc),
        tidal_days=nd,
        analysis_start=str(an),
        snapshots=int(snap.size),
        active=int(act.sum()),
        drawn=int(W.size),
        ref_from_submerged=int(r["ref_from_submerged"].sum()),
        flagged=int(F.size),
        classes=counts,
        flagged_film=int((fl & (film == 1)).sum()),
        classes_deep={
            CLASS_NAMES[k]: int(((cls == k) & (film == 0)).sum())
            for k in (NOISE, HELD_MILD, HELD_STRONG, UNTESTED)
        },
        classes_gt025={
            CLASS_NAMES[k]: int(
                ((cls == k) & (full(excess, np.nan, np.float32) > 0.25)).sum()
            )
            for k in (NOISE, HELD_MILD, HELD_STRONG, UNTESTED)
        },
        replaced=int(rep.sum()),
        replaced_deep=int((rep & (film == 0)).sum()),
        km2_replaced=round(float((G["dx"][rep] ** 2).sum() / 1e6), 3),
        mhh_lowered_m_p50_p90_max=[
            round(float(v), 3) for v in np.percentile(dmhh, [50, 90, 100])
        ]
        if dmhh.size
        else None,
        max_lowered_m_p50_p90_max=[
            round(float(v), 3) for v in np.percentile(dmax, [50, 90, 100])
        ]
        if dmax.size
        else None,
        check=chk,
        params=dict(
            q=q,
            ref_tol_m=REF_TOL_M,
            high_m=high,
            mild_top_m=MILD_TOP_M,
            film_m=FILM_M,
            held_frac=held_frac,
            min_snaps=MIN_SNAPS,
            min_hw_snaps=MIN_HW_SNAPS,
            hw_q=HW_Q,
            dry_h=DRY_H,
            radius_m=RADIUS_M,
            radius_dx=RADIUS_DX,
            k_nb=K_NB,
            min_nb=MIN_NB,
            spinup_d=spinup_d,
            day_h=day_h,
        ),
    )
    write(
        out_nc,
        d,
        an,
        nd,
        day_h,
        summ,
        dict(
            mean_higher_high=mhh_dn,
            max_month=mx_dn,
            days_wet=days,
            mean_higher_high_raw=mhh,
            max_month_raw=mx,
            ref_mhh=full(r["ref"], np.nan, np.float32),
            ref_max=full(r["ref_max"], np.nan, np.float32),
            excess=full(excess, np.nan, np.float32),
            denoise_class=cls,
            film=film,
            ref_from_submerged=full(r["ref_from_submerged"], 0, np.int8),
            snap_n=full(sn, 0, np.int16),
            snap_mean=full(sm, np.nan, np.float32),
            snap_std=full(ss, np.nan, np.float32),
            snap_hw_n=full(shn, 0, np.int16),
            snap_hw_mean=full(shm, np.nan, np.float32),
            snap_hw_std=full(shs, np.nan, np.float32),
            standing_step=full(np.where(cW == NOISE, step, np.nan), np.nan, np.float32),
        ),
    )
    summ["minutes"] = round((time.time() - t00) / 60, 1)
    tmp = Path(str(out_nc) + f".json.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(summ, indent=1, default=str) + "\n")
    os.replace(tmp, Path(str(out_nc) + ".json"))
    log(json.dumps(summ, default=str))
    return summ


VAR_ATTRS = {
    "mean_higher_high": "DE-NOISED mean higher-high water (m NAVD88): the raw value except on class noise",
    "max_month": "DE-NOISED month max water (m NAVD88): min(raw, ref_max) on class noise",
    "days_wet": "tidal days with a finite daily higher-high",
    "mean_higher_high_raw": "mean of the daily higher-highs from the 3 h zsmax blocks (mhhw_maps tide_stats)",
    "max_month_raw": "highest daily higher-high (mhhw_maps tide_stats)",
    "ref_mhh": "local reference: quantile q of the submerged drawn neighbours' mhh (fallback: all drawn)",
    "ref_max": "the same reference for the month max",
    "excess": "mean_higher_high_raw - ref_mhh",
    "film": "1 = mhh_raw - z_zmin < film_m: a film over the face's lowest pixel (cannot reach 0.15 m)",
    "ref_from_submerged": "1 = the reference came from submerged neighbours",
    "snap_n": "flagged faces: wet 6 h zs snapshots with a neighbour reference",
    "snap_mean": "flagged faces: mean of r = zs - median zs of the reference water (m)",
    "snap_std": "flagged faces: std of r (m)",
    "snap_hw_n": "flagged faces: high-water snapshots used",
    "snap_hw_mean": "flagged faces: mean of r at high water (m)",
    "snap_hw_std": "flagged faces: std of r at high water (m)",
    "standing_step": "noise faces: max(0, snap_hw_mean - 2 standard errors), added to the reference (m)",
}


def write(out_nc, d, an, nd, day_h, summ, arrays):
    """Atomic write of the per-face fields (tmp file + os.replace)."""
    import xarray as xr

    out_nc = Path(out_nc)
    out_nc.parent.mkdir(parents=True, exist_ok=True)
    ds = xr.Dataset({k: ("nmesh2d_face", v) for k, v in arrays.items()})
    for k, txt in VAR_ATTRS.items():
        ds[k].attrs["long_name"] = txt
    keys = sorted(k for k in CLASS_NAMES)
    ds["denoise_class"].attrs.update(
        long_name="de-noise class (nj_sfincs/tide_surface.py)",
        flag_values=np.array(keys, np.int8),
        flag_meanings=" ".join(CLASS_NAMES[k] for k in keys),
    )
    ds.attrs.update(
        ndays=nd,
        analysis_start=str(an),
        tidal_day_h=day_h,
        datum="NAVD88",
        run_dir=str(d),
        made_by="nj_sfincs/tide_surface.py",
        created=time.strftime("%Y-%m-%d %H:%M:%S"),
        summary=json.dumps(
            {k: summ[k] for k in ("flagged", "classes", "replaced", "params")}
        ),
    )
    enc = {k: {"zlib": True, "complevel": 4} for k in ds.data_vars}
    tmp = Path(str(out_nc) + f".{os.getpid()}.tmp")
    ds.to_netcdf(tmp, encoding=enc)
    os.replace(tmp, out_nc)
    log("written", out_nc)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument(
        "run_dir",
        help="a finished calm tide run (sfincs_map.nc, sfincs.nc, sfincs_subgrid.nc)",
    )
    ap.add_argument("out_nc")
    ap.add_argument(
        "--check", help="an existing *_tide_stats.nc the raw fields must reproduce"
    )
    ap.add_argument("--q", type=float, default=REF_Q)
    ap.add_argument("--high", type=float, default=HIGH_M)
    ap.add_argument("--held-frac", type=float, default=HELD_FRAC)
    ap.add_argument("--spinup-days", type=float, default=SPINUP_D)
    ap.add_argument("--day-hours", type=float, default=DAY_H)
    ap.add_argument(
        "--workers", type=int, default=int(os.environ.get("SLURM_CPUS_PER_TASK", "8"))
    )
    a = ap.parse_args(argv)
    build(
        a.run_dir,
        a.out_nc,
        q=a.q,
        high=a.high,
        held_frac=a.held_frac,
        spinup_d=a.spinup_days,
        day_h=a.day_hours,
        workers=a.workers,
        check=a.check,
    )


if __name__ == "__main__":
    main()
