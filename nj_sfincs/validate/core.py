"""Reading a finished run: the flood map, its caches, and the series helpers.

Nothing in here knows what a metric is. It opens output, downscales it, samples it at
cells, and resamples series onto common clocks. ``metrics.py`` does the scoring.

⚠️ THE ARITHMETIC IN THIS MODULE IS PINNED. The port-verification gate
(``scripts/verify_port.py``) rescores an archived run and requires bit-for-bit agreement
with the number it produced in the previous repo. Restructure freely; do not change what
any of these functions COMPUTE without re-baselining that gate deliberately.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import xarray as xr
from pyproj import CRS, Transformer

import rioxarray  # noqa: F401  (registers .rio)
from hydromt_sfincs import SfincsModel, utils

from ..config import DATA

#: m; a cell counts as "wet" above this (HWM + MOTF).
DEPTH_MIN = 0.15

#: Peak searches are floored here. Before this instant the run is still draining its
#: initial condition, and a plain argmax over the full window picks the SPIN-UP TRANSIENT
#: rather than the storm — which silently turns a peak-timing metric into a measurement of
#: the initial condition.
PEAK_FLOOR = np.datetime64("2012-10-29")

# Hours of run time to discard before a "clean tidal window" starts. The model does not
# begin on the observed tide: it starts from a cold state and takes several hours to spin
# up, and that settling is a monotonic drift, not an oscillation.
#
# WHY THIS EXISTS. This window used to start at tstart, so it opened during spin-up and —
# for the Sandy window — closed exactly on a rising tide, with the window's own maximum
# sitting on its right-hand edge. Cross-correlating that against a clean observed tide is
# badly conditioned, and it inflated EVERY phase lag by ~13 min. Sensitivity at one gauge,
# in minutes:
#
#     window        battery  shblend  gtsm  PREMIER
#     +0h/24h          30.7     21.7  27.9     30.0   <- old behaviour
#     +6h/24h          16.9      8.3  21.1     17.2
#     +12h/24h         17.4      8.1   6.4     17.6   <- stable, and stable in length too
#
# 12 h clears spin-up while still ending before the surge ramp dominates. Any phase number
# from before this change reads ~13 min high — re-measure rather than comparing across it.
SPINUP_SKIP_H = 12.0

# A tide RISES about half the time. A drain never does. This is the discriminator:
# anything that spends less than this fraction of its samples going UP is not a tide.
# (A clean semidiurnal signal sampled hourly gives ~0.5; even a badly over-damped estuary
# gives >0.3. A monotonic spin-up drawdown gives ~0.0.)
TIDE_MIN_FRAC_RISING = 0.20
TIDE_NOISE_M = 0.005  # steps smaller than this are numerical wiggle, not motion

#: Search ±2 h for the phase lag; the real lags are 15–40 min.
PHASE_MAX_LAG_MIN = 120.0


# ── windows and series ───────────────────────────────────────────────────────


def prestorm_window(
    map_times: np.ndarray, hours: float = 24.0, skip_hours: float = SPINUP_SKIP_H
):
    """Clean tidal window: ``hours`` long, opening ``skip_hours`` after the run starts.

    Skipping the spin-up is not cosmetic — see SPINUP_SKIP_H. If the run is too short to
    afford the skip, fall back to starting at tstart rather than returning an empty window.
    """
    t0, tend = map_times.min(), map_times.max()
    start = t0 + np.timedelta64(int(skip_hours * 3600), "s")
    if start + np.timedelta64(int(hours * 3600), "s") > tend:
        start = t0  # short/smoke run — take what we can get
    return start, start + np.timedelta64(int(hours * 3600), "s")


def tidal_signal(series: np.ndarray) -> dict:
    """Decompose a water-level series into spin-up DRIFT and a true TIDAL range.

    WHY THIS EXISTS. The naive metric — ``max - min`` over the first 24 h — silently
    reported the model's monotonic SPIN-UP DRAWDOWN as if it were a tide. At one gauge the
    "tidal range" was 1.27 m, and the series behind that number was::

        +0.00 -0.63 -0.86 -0.99 -1.06 ... -1.27 -1.27 -1.27

    i.e. the model equilibrating from its flat initial condition, with ZERO tidal
    oscillation — because that basin's inlet was dammed shut in the DEM and it was
    hydraulically cut off from the ocean. ``max - min`` cannot tell a tide from a drain, so
    it produced a plausible-looking number for a basin that was not tidal at all, and the
    defect hid for months.

    Note the trap: that drawdown is an EXPONENTIAL decay, so simply de-trending it with a
    straight line leaves a big bowed residual (~1 m) that still looks like a range, and
    counting turning points is defeated by numerical wiggle. Neither is a safe test. The
    robust discriminator is the FRACTION OF TIME THE SERIES RISES: a tide floods and ebbs,
    a drain only ebbs.
    """
    s = np.asarray(series, float)
    s = s[np.isfinite(s)]
    if s.size < 4:
        return dict(
            range_m=float("nan"),
            drift_m=float("nan"),
            frac_rising=float("nan"),
            is_tidal=False,
        )
    d = np.diff(s)
    moving = np.abs(d) > TIDE_NOISE_M  # ignore numerical chatter
    frac_rising = float((d[moving] > 0).mean()) if moving.any() else 0.0
    is_tidal = bool(frac_rising >= TIDE_MIN_FRAC_RISING)

    # the tide itself: remove the spin-up drift, then measure what is left. Only meaningful
    # once is_tidal has established there IS a tide to measure.
    t = np.arange(s.size, dtype=float)
    detr = s - np.polyval(np.polyfit(t, s, 1), t)
    return dict(
        range_m=float(detr.max() - detr.min()),
        drift_m=float(s[-1] - s[0]),  # the spin-up (net drainage)
        frac_rising=frac_rising,
        is_tidal=is_tidal,
    )


def uniform_series(
    times: np.ndarray,
    values: np.ndarray,
    t0: np.datetime64,
    t1: np.datetime64,
    dt_s: float,
) -> np.ndarray | None:
    """Clip to [t0, t1], drop NaN, linearly resample onto a uniform dt_s grid.

    ⚠️ THIS CLIPS ITS GRID TO EACH SERIES' OWN COVERAGE and returns bare values with no
    time axis, so two series resampled through it are aligned BY INDEX 0 downstream. If
    they do not begin at the same instant inside [t0, t1], the reported lag is silently
    offset by that difference. Use :func:`aligned_pair` for anything new.

    It is kept, and kept in use for the gauges whose numbers are in the scored campaign,
    because changing the alignment would move published lags. Their windows are covered by
    both series, so they are correct in practice.
    """
    t = np.asarray(times)
    v = np.asarray(values, float).ravel()
    if t.shape[0] != v.shape[0]:
        return None
    ok = np.isfinite(v) & (t >= t0) & (t <= t1)
    if ok.sum() < 4:
        return None
    ts = (t[ok] - t0) / np.timedelta64(1, "s")
    order = np.argsort(ts)
    ts, vs = ts[order], v[ok][order]
    grid = np.arange(0.0, float((t1 - t0) / np.timedelta64(1, "s")) + dt_s, dt_s)
    grid = grid[(grid >= ts.min()) & (grid <= ts.max())]
    if grid.size < 6:
        return None
    return np.interp(grid, ts, vs)


def aligned_pair(tm, vm, to, vo, t0, t1, dt_s):
    """Resample model and obs onto ONE shared absolute time grid. Returns (m, o) or None.

    The safe counterpart to :func:`uniform_series`: both series are interpolated onto the
    SAME grid, spanning only the overlap both actually cover, so index 0 is one instant.
    Returns None if the overlap is too short to correlate.
    """

    def _clean(t, v):
        t = np.asarray(t)
        v = np.asarray(v, float).ravel()
        if t.shape[0] != v.shape[0]:
            return None
        ok = np.isfinite(v) & (t >= t0) & (t <= t1)
        if ok.sum() < 4:
            return None
        ts = (t[ok] - t0) / np.timedelta64(1, "s")
        order = np.argsort(ts)
        return ts[order], v[ok][order]

    a, b = _clean(tm, vm), _clean(to, vo)
    if a is None or b is None:
        return None
    lo = max(a[0].min(), b[0].min())  # common coverage only
    hi = min(a[0].max(), b[0].max())
    if hi - lo < 6 * dt_s:
        return None
    grid = np.arange(lo, hi + dt_s, dt_s)
    grid = grid[grid <= hi]
    if grid.size < 6:
        return None
    return np.interp(grid, a[0], a[1]), np.interp(grid, b[0], b[1])


def xcorr_lag_minutes(
    model: np.ndarray, obs: np.ndarray, dt_s: float, max_lag_min: float = PHASE_MAX_LAG_MIN
) -> float:
    """Lag (minutes, + = model LATER than obs) maximising detrended cross-correlation.

    Both series are linearly detrended (removes the surge ramp + mean, same idea as
    :func:`tidal_signal`) and normalised, then correlated over integer sample shifts. A
    parabolic fit around the peak refines the lag to sub-sample precision.
    """
    n = min(model.size, obs.size)
    if n < 6:
        return float("nan")
    a = np.asarray(model[:n], float)
    b = np.asarray(obs[:n], float)
    tt = np.arange(n, dtype=float)
    a = a - np.polyval(np.polyfit(tt, a, 1), tt)
    b = b - np.polyval(np.polyfit(tt, b, 1), tt)
    if a.std() < 1e-6 or b.std() < 1e-6:
        return float("nan")
    kmax = int(min(max_lag_min * 60.0 / dt_s, n - 3))
    if kmax < 1:
        return float("nan")
    min_overlap = max(6, n // 2)
    lags = np.arange(-kmax, kmax + 1)
    corr = np.full(lags.size, -np.inf)
    for i, k in enumerate(lags):
        # shift OBS later by k samples and overlap with model: if obs must move +k to line
        # up with the model, the model is k samples LATE → +lag.
        if k >= 0:
            aa, bb = a[k:], b[: n - k]
        else:
            aa, bb = a[: n + k], b[-k:]
        if aa.size < min_overlap:
            continue
        # normalised cross-correlation on the overlap (each window demeaned + scaled by its
        # own norm) — removes the shrinking-window / residual-trend bias a raw dot product
        # carries.
        aa = aa - aa.mean()
        bb = bb - bb.mean()
        denom = np.sqrt((aa * aa).sum() * (bb * bb).sum())
        if denom > 0:
            corr[i] = float((aa * bb).sum() / denom)
    j = int(np.argmax(corr))
    lag_samples = float(lags[j])
    if 0 < j < lags.size - 1:  # parabolic sub-sample refinement
        y0, y1, y2 = corr[j - 1], corr[j], corr[j + 1]
        denom = y0 - 2 * y1 + y2
        if abs(denom) > 1e-12:
            lag_samples += 0.5 * (y0 - y2) / denom
    return lag_samples * dt_s / 60.0


def peak_after_floor(times, values):
    """(peak value, peak time) over samples at/after PEAK_FLOOR; (nan, None) if none."""
    t = np.asarray(times)
    v = np.asarray(values, float).ravel()
    ok = np.isfinite(v) & (t >= PEAK_FLOOR)
    if not ok.any():
        return float("nan"), None
    i = int(np.nanargmax(v[ok]))
    return float(v[ok][i]), t[ok][i]


# ── sampling the model ───────────────────────────────────────────────────────


def wet_channel_cells(
    model_dir: Path, lon: float, lat: float, epsg: int, radius: float = 150.0,
    bed_max: float = -1.0,
):
    """Model face indices of wet channel cells within ``radius`` m of a gauge.

    SFINCS observation points snap to whatever cell contains them, and several gauges sit
    on DRY high ground (measured ``point_zb`` up to +2 m), so his-based interior series are
    dry-cell artifacts. Sample the map at genuine channel cells (bed < ``bed_max``) near
    the gauge's TRUE coordinate instead.

    ⚠️ THIS MATTERS FOR RANGE AND PHASE, NOT FOR THE PEAK. At the crest the local water
    surface is continuous, so a bank cell and the adjacent channel share the same ``zs``;
    but a pre-storm tide of ~0.7 m about NAVD88 0 never reaches a +0.99 m cell at all, and
    its "tide" is pure artifact.

    Returns ``(idx, dist, bed)`` or None.
    """
    grid = xr.open_dataset(Path(model_dir) / "sfincs.nc")
    fx = grid["mesh2d_face_x"].values
    fy = grid["mesh2d_face_y"].values
    z = grid["z"].values
    mask = grid["mask"].values
    gx, gy = Transformer.from_crs(4326, epsg, always_xy=True).transform(lon, lat)
    r = np.hypot(fx - gx, fy - gy)
    sel = (r < radius) & (mask > 0) & (z < bed_max)
    idx = np.where(sel)[0]
    if idx.size == 0:
        return None
    return idx, r[idx], z[idx]


def read_output(mod, lazy: bool = True) -> None:
    """Load sfincs_map.nc + sfincs_his.nc, tolerating BOTH SFINCS output conventions.

    ``hydromt_sfincs``' own ``output.read()`` does ``crs = ds["crs"].values`` on the map,
    which breaks on SFINCS v2.4.0 (Galibier) with ``KeyError: 'crs'``.

    The irony is that Galibier's file is the *more* correct one. It declares a CF-compliant
    ``grid_mapping = "crs"`` on its coordinate variables, so xugrid does the right thing:
    it folds ``crs`` into the grid object and drops it from ``data_vars``. v2.3.3 (Faber)
    omits ``grid_mapping``, leaving ``crs`` lying around as a loose variable — which is the
    only reason the upstream code works there.

    So take the CRS from wherever the engine actually put it: the grid object first
    (Galibier), then a loose variable (Faber), then ``epsg`` in sfincs.inp as a backstop.
    Without this, every spatial metric silently excludes the Galibier runs.

    ``lazy`` (default) opens the map instead of loading it. sfincs_map.nc is ~870 MB on
    disk and ~2.2 GB in memory, but every caller here wants a handful of slices. Eager
    loading cost ~40 s per run cold. Pass ``lazy=False`` only when reading a run that is
    about to be OVERWRITTEN — a lazy handle keeps reading the deleted inode.
    """
    import xugrid as xu

    root = Path(mod.root.path)
    mod.config.read()
    # ``output.set()`` lazily calls ``_initialize()``, which in read mode calls the very
    # ``read()`` we are replacing — so prime the store first or we trip the same KeyError.
    mod.output._initialize(skip_read=True)

    fn_map = root / "sfincs_map.nc"
    if fn_map.is_file():
        # 🔴 `timemax` IS NOT DECODED, AND THAT IS DELIBERATE. SFINCS declares it as
        # "seconds since <tref>" but writes one entry per `dtmaxout` block, and it gives
        # the variable NO `_FillValue`. A run whose output stopped early therefore leaves
        # unwritten blocks holding the raw netCDF float fill, 9.96921e+36 — which xarray
        # dutifully tries to read as ~3e29 years and raises
        #     ValueError: unable to decode time units ... Try ... installing cftime
        # a message that names the wrong cause entirely (cftime IS installed). That
        # exception comes out of `open_dataset`, so it takes the WHOLE run with it: every
        # gauge, every floodmap, not just zsmax.
        #
        # Leaving it raw costs nothing — no caller reads timemax's values, only its
        # length, as the dimension `zsmax` is stacked along. And it keeps the fill visible
        # instead of hiding it, which is the point: an all-fill timemax is how you SEE
        # that a run's max-water-level blocks were never written.
        kw = {"decode_times": {"timemax": False}}
        ds = xu.open_dataset(fn_map, **kw) if lazy else xu.load_dataset(fn_map, **kw)
        ds = ds.set_coords(["mesh2d_node_x", "mesh2d_node_y"])
        crs = ds.grid.crs  # Galibier: xugrid parsed it
        if crs is None:
            if "crs" in ds.variables:  # Faber: loose variable
                crs = CRS.from_user_input(int(ds["crs"].values))
            else:  # backstop: the run's own inp
                crs = CRS.from_user_input(int(inp_value(root / "sfincs.inp", "epsg")))
            ds.grid.set_crs(crs)
        ds = ds.drop_vars("crs", errors="ignore")
        mod.output.set(ds, split_dataset=True)

    fn_his = root / "sfincs_his.nc"
    if fn_his.is_file():
        mod.output.set(mod.output.read_his_file(fn_his=str(fn_his)), split_dataset=True)


def inp_value(inp: Path, key: str) -> str:
    for line in Path(inp).read_text().splitlines():
        if "=" in line and line.split("=")[0].strip() == key:
            return line.split("=", 1)[1].strip()
    raise KeyError(f"{key!r} not found in {inp}")


def his_series(mod, name_substr: str):
    """(times, values) for the his obs point whose station_name contains name_substr."""
    point_zs = mod.output.data["point_zs"]
    names = [
        n.decode() if isinstance(n, bytes) else str(n)
        for n in point_zs["station_name"].values
    ]
    i = next((k for k, n in enumerate(names) if name_substr in n), None)
    if i is None:
        return None
    s = point_zs.isel(stations=i)
    return s["time"].values, s.values


def his_bed(mod, name_substr: str) -> float:
    """``point_zb`` at a his obs point — how high the cell SFINCS snapped it to is."""
    point_zb = mod.output.data["point_zb"]
    names = [
        n.decode() if isinstance(n, bytes) else str(n)
        for n in mod.output.data["point_zs"]["station_name"].values
    ]
    i = next((k for k, n in enumerate(names) if name_substr in n), None)
    if i is None:
        return float("nan")
    return float(np.asarray(point_zb.isel(stations=i).values).item())


# ── caches ───────────────────────────────────────────────────────────────────
#
# Every cache here is bounded and keyed on an mtime, so a re-run self-invalidates. Two of
# them were sized wrong once and the symptom was the same both times: the thing looked
# like it was working and silently was not.

#: Full ``zs(time, face)`` arrays, keyed by (map realpath, mtime, var).
_ZS_MEMO: dict[tuple, object] = {}
_ZS_MEMO_MAX = 6

#: In-process memo for ``load_floodmap``, keyed by (run dir, floodmap tif mtime).
#:
#: ⚠️ THIS MUST BE >= THE NUMBER OF RUNS A NOTEBOOK COMPARES. It was 4, which was fine for
#: a 2-arm campaign and silently catastrophic at 5: the FIFO evicted the first arm while
#: the fifth loaded, so EVERY panel cell after the first re-derived all five from scratch
#: (~70 s each). A memo one entry too small is worse than no memo, because it looks like
#: it is working.
_FLOODMAP_MEMO: dict[tuple, tuple] = {}
_FLOODMAP_MEMO_MAX = 8

#: De-rotated subgrid DEM, keyed by (dep tif device+inode, mtime, target grid signature).
#: Separate from the floodmap memo because arms SHARE this file: on a frozen mesh a
#: roughness-only or forcing-only arm has a byte-identical dep_subgrid_lev3.tif.
_DEP_MEMO: dict[tuple, object] = {}
_DEP_MEMO_MAX = 3


#: Rasterised active-mask footprints, keyed by (run dir, map mtime, target grid).
#: Small (one bool array per target grid) and each rasterise is ~3.5 s.
_SIMMASK_MEMO: dict[tuple, object] = {}
_SIMMASK_MEMO_MAX = 8


#: Opened run handles, keyed by run dir. ``his_series`` needs a model whose output store
#: is populated, and the callers that only have a PATH (the plot helpers) would otherwise
#: pay the ~21 s SfincsModel open once per gauge per run.
_MODEL_MEMO: dict[Path, object] = {}


def open_run(model_dir: Path):
    """Open a run read-only with its output loaded, memoised on the run dir.

    🔴 EXISTS BECAUSE ``mod=None`` WAS AN UNIMPLEMENTED OPTION. ``gauge_series_frame``
    documents ``mod`` as optional and ``_model_series`` handed it straight to
    ``his_series``, which does ``mod.output`` — so every ``series_source="his"`` gauge
    raised ``AttributeError: 'NoneType' object has no attribute 'output'``. The only
    caller that passed no model was ``plots.plot_gauge_verification``, which catches per
    gauge and draws the exception into the panel, so the failure rendered as a FIGURE OF
    FIVE ERROR BOXES rather than as a traceback. An optional argument has to be optional.
    """
    model_dir = Path(model_dir).resolve()
    mod = _MODEL_MEMO.get(model_dir)
    if mod is None:
        mod = SfincsModel(
            str(model_dir), data_libs=[str(DATA / "data_catalog.yml")], mode="r"
        )
        read_output(mod)
        _MODEL_MEMO[model_dir] = mod
    return mod


def cache_clear():
    """Drop every in-process memo (frees the pinned rasters and zs arrays)."""
    _FLOODMAP_MEMO.clear()
    _DEP_MEMO.clear()
    _ZS_MEMO.clear()
    _SIMMASK_MEMO.clear()
    _MODEL_MEMO.clear()


def simulated_mask(model_dir: Path, shape, transform):
    """Which cells of a target raster the solver ACTUALLY SIMULATED.

    Rasterises the run's own active faces — ``msk > 0`` in ``sfincs_map.nc``, over the
    ``mesh2d`` node geometry stored beside it — onto ``shape``/``transform``. Returns a
    bool array: True where a face the solver integrated covers the cell.

    🔴 WHY THIS IS NOT THE REGION POLYGON. ``Domain.region`` is a BUILD INPUT. The active
    mask is region + ``mask_zmin`` + ``always_active_boxes``, and ``include_polygon``
    only ever ADDS cells, so the mask can and does extend beyond the polygon. Measured
    2026-08-20: on ``v1_monmouth`` the registry region is 2,494 km² against the run's
    own 2,909 km² — 415 km² apart. Whichever polygon you pick is wrong on one domain
    or the other. The mask read out of the run is wrong on neither, and it cannot go stale
    against the run because it IS the run.

    🔴 WHY ANY OF THIS IS NEEDED — ``downscale_floodmap`` BLEEDS. It paints zsmax onto
    the subgrid DEM by nearest active cell, so low ground under INACTIVE faces comes
    back holding water the solver never computed. On ``v1_monmouth`` that is 3.68 km² of
    phantom flood, up to 1.45 km outside the mask, median bed 1.00 m under median 0.36 m
    of water — and 3.15 km² of it was scoring as MOTF FALSE ALARMS. ``da_dep`` cannot
    catch this: the subgrid DEM carries valid bed across the whole grid RECTANGLE, so
    ``dep > 0`` is true on ground the model never had. Same confusion as
    ``_clip_to_region`` (metrics.py) and ``_fill_inactive_holes``, third instance.

    ⚠️ Read from ``sfincs_map.nc`` directly, NOT via ``SfincsModel`` — this is four
    variables and a 21 s model open would dwarf the 3.5 s rasterise.
    """
    from rasterio.features import rasterize  # noqa: PLC0415

    model_dir = Path(model_dir).resolve()
    mp = model_dir / "sfincs_map.nc"
    key = (
        model_dir,
        mp.stat().st_mtime if mp.is_file() else None,
        tuple(shape),
        tuple(transform)[:6],
    )
    hit = _SIMMASK_MEMO.get(key)
    if hit is not None:
        return hit

    with xr.open_dataset(mp) as ds:
        msk = ds["msk"].values
        fn = ds["mesh2d_face_nodes"].values
        node_x = ds["mesh2d_node_x"].values
        node_y = ds["mesh2d_node_y"].values
    # face_nodes is 1-based in the SFINCS/UGRID output; do not assume it.
    fn0 = fn - 1 if np.nanmin(fn) == 1 else fn
    idx = fn0[np.where(msk > 0)[0]].astype("int64")
    xs, ys = node_x[idx], node_y[idx]
    shapes = (
        (
            {
                "type": "Polygon",
                "coordinates": [
                    [
                        (xs[i, 0], ys[i, 0]),
                        (xs[i, 1], ys[i, 1]),
                        (xs[i, 2], ys[i, 2]),
                        (xs[i, 3], ys[i, 3]),
                        (xs[i, 0], ys[i, 0]),
                    ]
                ],
            },
            1,
        )
        for i in range(xs.shape[0])
    )
    out = rasterize(
        shapes, out_shape=tuple(shape), transform=transform,
        fill=0, default_value=1, dtype="uint8",
    ).astype(bool)
    if len(_SIMMASK_MEMO) >= _SIMMASK_MEMO_MAX:
        _SIMMASK_MEMO.pop(next(iter(_SIMMASK_MEMO)))
    _SIMMASK_MEMO[key] = out
    return out


def zs_at_faces(model_dir: Path, idx, var: str = "zs"):
    """``var[time, idx]`` from sfincs_map.nc via ONE contiguous read.

    ⚡ WHY THIS EXISTS. ``sfincs_map.nc`` stores zs with chunking ``(1, nface)`` — one chunk
    per timestep spanning every face. Indexing it the obvious way::

        mp["zs"].isel(nmesh2d_face=cells)      # cells = ~50 scattered face ids

    defeats that layout completely: the scattered index is applied per chunk, and a single
    gauge costs **~52 s**. Reading the whole variable contiguously and indexing in numpy
    costs **1.2 s** — 43x faster — because it is one sequential 667 MB read instead of 73
    strided ones. That one line was the dominant cost of a whole notebook.

    ⚠️ The cached array is SHARED, not copied — treat it as READ-ONLY.
    """
    model_dir = Path(model_dir).resolve()
    p = model_dir / "sfincs_map.nc"
    key = (p, p.stat().st_mtime, var)
    arr = _ZS_MEMO.get(key)
    if arr is None:
        with xr.open_dataset(p) as ds:
            arr = np.asarray(ds[var].values)  # one contiguous read
        if len(_ZS_MEMO) >= _ZS_MEMO_MAX:
            _ZS_MEMO.pop(next(iter(_ZS_MEMO)))
        _ZS_MEMO[key] = arr
    return arr[:, np.asarray(idx)]


def map_times(model_dir: Path):
    """The map's time axis, without paying for the data variables."""
    with xr.open_dataset(Path(model_dir) / "sfincs_map.nc") as ds:
        return ds["time"].values


#: Suffix a pre-fix (first-overview) floodmap cache is moved aside to, never deleted.
PRE_NATIVE_SUFFIX = ".pre_native.tif"


def floodmap_is_native(floodmap_fn, dep_fn) -> bool:
    """True when ``floodmap_fn`` sits on ``dep_fn``'s FULL-RESOLUTION lattice.

    Same width, height and affine as the DEM's base band. A floodmap written by hydromt's
    path-mode ``downscale_floodmap`` sits on the dep's FIRST OVERVIEW instead (half the
    width and height, twice the pixel; see ``downscale_floodmap_native``) and is NOT
    native — it must be re-downscaled, not trusted as a cache.
    """
    import rasterio  # noqa: PLC0415

    with rasterio.open(str(floodmap_fn)) as f, rasterio.open(str(dep_fn)) as d:
        return f.shape == d.shape and f.transform.almost_equals(
            d.transform, precision=1e-6
        )


def _hmax_block_locate(grid, zs_face, block, T, bm0, bm1, bn0, bn1, hmin):
    """One block of the downscale by direct point location — hydromt's arithmetic.

    hydromt's DataArray mode builds a UGRID topology of the block's pixels
    (``from_structured2d``: ~80 % of its time, an argsort over every edge) only to ask
    ``CentroidLocatorRegridder`` which source face holds each pixel's centroid. On a
    parallelogram lattice the centroid IS the pixel centre ``T * (col + .5, row + .5)``,
    so this locates the centres in the source mesh's celltree directly (built once per
    mesh) and does the rest exactly as hydromt does: the regrid is float64 with NaN off
    the mesh, ``hmax = (zs - dep).astype(float32)``, kept where ``hmax > hmin``.
    ``TestFloodmapNative`` pins equality with hydromt's own call, bit for bit.
    """
    cols, rows = np.meshgrid(np.arange(bm0, bm1), np.arange(bn0, bn1))
    xc, yc = T * (cols + 0.5, rows + 0.5)
    idx = grid.locate_points(np.column_stack([xc.ravel(), yc.ravel()]))
    zs = np.full(idx.shape, np.nan)  # float64, as xugrid's regrid output
    inside = idx != -1
    zs[inside] = zs_face[idx[inside]]
    h = (zs.reshape(block.shape) - block).astype(np.float32)
    with np.errstate(invalid="ignore"):
        return np.where(h > hmin, h, np.float32(np.nan))


def downscale_floodmap_native(
    zsmax,
    dep_fn,
    floodmap_fn,
    hmin: float = 0.05,
    nrmax: int = 1000,
    method: str = "locate",
) -> None:
    """hydromt's path-mode ``downscale_floodmap``, on the DEM's FULL-RESOLUTION band.

    🔴 WHY NOT ``utils.downscale_floodmap(dep=<path>)`` (confirmed 2026-11-09,
    ``logs/crests_2026-11-09/README.md``). Given the dep as a path, hydromt opens it with
    ``rasterio.open(dep, overview_level=0)`` and its comment says "use highest resolution
    by default". In rasterio / GDAL ``overview_level=0`` is the FIRST OVERVIEW, not the
    base band (that is ``overview_level=None``). Our subgrid DEMs carry ``average``
    overviews, so every floodmap was computed on a 2x-coarser bed whose pixels AVERAGE
    buildings into the streets beside them (v4: 6.25 m, not 3.125 m; Lavallette street
    pixels read 6.24 m of "ground" over a 1.25 m bed) — and every MOTF / HWM score read
    that floodmap.

    What is kept, deliberately identical to hydromt 2.0.0-rc2's path mode:

    * the same ``nrmax`` block loop over the dep (merged last row / column; all-NaN
      blocks skipped and left nodata);
    * per block, the same pixel-centre coordinates through the AFFINE (the subgrid
      rasters are rotated — CLAUDE.md §5; ``x0 + col*res`` is wrong by kilometres), and
      the same downscale arithmetic: hydromt's own DataArray-mode ``downscale_floodmap``
      (``zsmax`` regridded by ``CentroidLocatorRegridder`` on a rotated grid,
      ``rasterize_like`` on a north-up one; ``hmax = zsmax - dep``; ``hmax > hmin``);
    * the same output profile (float32, NaN nodata, 256 tiles, deflate + predictor 2,
      BIGTIFF) and ``nearest`` overviews.

    The band read is the difference that matters: the base band. Memory per block is
    unchanged (a block is ``nrmax``² pixels at either resolution); there are ~4x as many
    blocks, so ``method="locate"`` (the default, for a UGRID ``zsmax``) does each block by
    direct point location instead of hydromt's per-block topology build
    (``_hmax_block_locate``; same numbers, ~10x faster per block, measured on v4).
    ``method="hydromt"`` calls hydromt's DataArray-mode ``downscale_floodmap`` per block,
    the reference the tests compare against.
    ⚠️ The output does NOT bleed less than hydromt's: it still paints zsmax onto low
    ground under inactive faces — screen with ``simulated_mask`` as before.

    ``floodmap_fn`` must end in ``.tif`` (``build_overviews`` asserts it). The caller owns
    atomicity: write to a temp name and ``os.replace`` it.
    """
    import rasterio  # noqa: PLC0415
    from rasterio.windows import Window  # noqa: PLC0415

    if method not in ("locate", "hydromt"):
        raise ValueError(f"method {method!r}: expected 'locate' or 'hydromt'")
    grid = getattr(getattr(zsmax, "ugrid", None), "grid", None)
    if method == "locate" and grid is None:
        method = "hydromt"  # a regular-grid zsmax: hydromt's own reproject path
    if method == "locate":
        zs_face = np.asarray(zsmax.values, dtype=np.float64)
        if zs_face.shape != (grid.n_face,):
            raise ValueError(f"zsmax must be one value per face, got {zs_face.shape}")

    with rasterio.open(str(dep_fn)) as src:  # base band: NO overview_level
        n1, m1 = src.shape
        nrbn, nrbm = int(np.ceil(n1 / nrmax)), int(np.ceil(m1 / nrmax))
        merge_last_col = merge_last_row = False
        if m1 % nrmax == 1:  # avoid 1-pixel-wide blocks (hydromt's rule)
            nrbm -= 1
            merge_last_col = True
        if n1 % nrmax == 1:
            nrbn -= 1
            merge_last_row = True
        T = src.transform
        rotated = not (T.b == 0 and T.d == 0)
        epsg = src.crs.to_epsg()
        profile = dict(
            driver="GTiff",
            width=src.width,
            height=src.height,
            count=1,
            dtype=np.float32,
            crs=src.crs,
            transform=T,
            tiled=True,
            blockxsize=256,
            blockysize=256,
            compress="deflate",
            predictor=2,
            nodata=np.nan,
            BIGTIFF="YES",
        )
        with rasterio.open(str(floodmap_fn), "w", **profile) as dst:
            for ii in range(nrbm):
                bm0 = ii * nrmax
                bm1 = min(bm0 + nrmax, m1)
                if merge_last_col and ii == nrbm - 1:
                    bm1 += 1
                for jj in range(nrbn):
                    bn0 = jj * nrmax
                    bn1 = min(bn0 + nrmax, n1)
                    if merge_last_row and jj == nrbn - 1:
                        bn1 += 1
                    window = Window(bm0, bn0, bm1 - bm0, bn1 - bn0)
                    block = src.read(1, window=window)
                    if np.all(np.isnan(block)):
                        continue
                    if method == "locate":
                        h = _hmax_block_locate(
                            grid, zs_face, block, T, bm0, bm1, bn0, bn1, hmin
                        )
                        dst.write(h, 1, window=window)
                        continue
                    if not rotated:
                        x = T.c + (np.arange(bm0, bm1) + 0.5) * T.a
                        y = T.f + (np.arange(bn0, bn1) + 0.5) * T.e
                        coords = {"y": ("y", y), "x": ("x", x)}
                    else:
                        cols, rows = np.meshgrid(
                            np.arange(bm0, bm1), np.arange(bn0, bn1)
                        )
                        xc, yc = T * (cols + 0.5, rows + 0.5)
                        coords = {"yc": (("y", "x"), yc), "xc": (("y", "x"), xc)}
                    block_dep = xr.DataArray(block, dims=("y", "x"), coords=coords)
                    block_dep.raster.set_crs(epsg)
                    hmax = utils.downscale_floodmap(
                        zsmax=zsmax, dep=block_dep, hmin=hmin
                    )
                    dst.write(
                        np.asarray(hmax.values, dtype=np.float32), 1, window=window
                    )
    utils.build_overviews(fn=str(floodmap_fn), resample_method="nearest")


def _open_north_up(fn, match=None):
    """Read a ROTATED raster and de-rotate it to north-up (onto ``match``'s grid if given).

    Same values as ``open_rasterio(fn, masked=True).rio.reproject(crs)`` /
    ``.rio.reproject_match(match)`` — bit for bit (``logs/floodmap_fix_2026-11-12/``) —
    at about a third of the peak memory, which the native-resolution floodmap needs
    (v4: two ~60,000 x 80,000 grids where there was one 30,000 x 40,000):

    * ``parse_coordinates=False``: on a rotated raster rioxarray otherwise builds 2-D
      float64 ``xc`` / ``yc`` arrays, 16 bytes per pixel on a 4-byte band — the largest
      allocation of the whole load. The reprojection reads the GeoTransform, not them.
    * ``cache=False`` + ``del``: the rotated source is freed as soon as it is warped;
      cached, it stayed resident beside its north-up copy.

    Without parsed coordinates the warped array carries none, so its 1-D pixel-centre
    ``x`` / ``y`` are put back from its transform (``match``'s, for a matched read) —
    the scorers read ``rio.transform()`` off them.
    """
    import gc  # noqa: PLC0415

    # rioxarray's own coordinate builder, so the coords are the ones reproject makes
    from rioxarray._spatial_utils import _generate_spatial_coords  # noqa: PLC0415

    src = rioxarray.open_rasterio(
        str(fn), masked=True, cache=False, parse_coordinates=False
    ).squeeze(drop=True)
    if match is None:
        out = src.rio.reproject(src.rio.crs)
        dst_affine = out.rio.transform()
    else:
        out = src.rio.reproject_match(match)
        dst_affine = match.rio.transform()
    del src
    gc.collect()
    ny, nx = out.shape[-2:]
    return out.assign_coords(
        _generate_spatial_coords(affine=dst_affine, width=nx, height=ny)
    )


def subgrid_dep(model_dir: Path) -> Path:
    """The subgrid DEM a run's floodmap is downscaled onto.

    Prefer the ALL-LEVEL merged DEM (scripts/build_merged_subgrid_dep.py). The
    per-level lev3 raster covers only faces refined to the finest level; on v3 that
    silently classed 51 in-region HWMs — all on active faces — as off-grid, and left
    wet coarse faces unpainted in the MOTF extent (STATUS 2026-08-29). Falling back
    to lev3 keeps v1.5 (measured clean: 0 of 69 marks uncovered) bit-for-bit.
    """
    dep_p = Path(model_dir) / "subgrid" / "dep_subgrid_merged.tif"
    if not dep_p.is_file():
        dep_p = Path(model_dir) / "subgrid" / "dep_subgrid_lev3.tif"
    return dep_p


def floodmap_cache_fresh(model_dir: Path, fm: Path) -> bool:
    """Can ``fm`` be read as this run's floodmap without re-downscaling?

    Freshness is against BOTH inputs of the downscale: a re-run rewrites sfincs_map.nc,
    a rebuilt/merged dep must invalidate a cache computed on the old raster — and against
    the dep's LATTICE: a first-overview (pre-2026-11-12) floodmap is stale at any mtime.
    """
    model_dir, fm = Path(model_dir), Path(fm)
    dep_p, mp = subgrid_dep(model_dir), model_dir / "sfincs_map.nc"
    return (
        fm.is_file()
        and (not mp.is_file() or fm.stat().st_mtime >= mp.stat().st_mtime)
        and fm.stat().st_mtime >= dep_p.stat().st_mtime
        and floodmap_is_native(fm, dep_p)
    )


def floodmap_label(floodmap_fn, dep_fn) -> str:
    """``native 3.125 m`` / ``overview 6.25 m``: the metric row's ``floodmap`` column.

    Rows scored before 2026-11-12 have no such column: they were all on the dep's first
    overview. Never pool a row that has this label with one that has not.
    """
    import rasterio  # noqa: PLC0415

    with rasterio.open(str(floodmap_fn)) as f:
        px = float(np.hypot(f.transform.a, f.transform.d))
    kind = "native" if floodmap_is_native(floodmap_fn, dep_fn) else "overview"
    return f"{kind} {px:.4g} m"


def _move_aside_pre_native(fm: Path) -> Path:
    """Rename a first-overview floodmap to ``<stem>.pre_native.tif``; never overwrite one."""
    aside = fm.with_name(fm.stem + PRE_NATIVE_SUFFIX)
    if aside.exists():  # an earlier one is kept too: stamp this one with its mtime
        aside = fm.with_name(f"{fm.stem}.{int(fm.stat().st_mtime)}{PRE_NATIVE_SUFFIX}")
    os.rename(fm, aside)
    print(f"[floodmap] pre-fix (first-overview) cache kept as {aside.name}")
    return aside


def load_floodmap(
    model_dir: Path,
    force: bool = False,
    memo: bool = True,
    need_model: bool = True,
    data_dir: Path = DATA,
    floodmap_fn: Path | str | None = None,
):
    """Open the run read-only and downscale zsmax onto the subgrid DEM at its NATIVE res.

    Returns ``(mod, da_hmax, da_dep)`` — the model handle plus the north-up depth-max and
    subgrid-DEM rasters the spatial metrics sample.

    The downscale is CACHED as ``floodmap_hmax_lev3.tif`` in the run dir (or at
    ``floodmap_fn``, for a re-score that must not touch the run dir) and reused when it is
    newer than the run's sfincs_map.nc AND the dep, AND on the dep's full-resolution
    lattice. Staleness is the mtime comparison, not existence: a re-run of the same
    experiment rewrites sfincs_map.nc and must invalidate the tif.

    🔴 RESOLUTION (2026-11-12). Every floodmap before this date was computed on the dep's
    FIRST OVERVIEW (hydromt's ``overview_level=0``; see ``downscale_floodmap_native``):
    6.25 m on v4, buildings averaged into streets. Such a cache is STALE whatever its
    mtime; it is moved aside to ``<name>.pre_native.tif`` (never deleted) when its
    replacement is complete.

    ``memo`` — the in-process cache. The on-disk tif skips the *downscale*, but every call
    still pays to de-rotate the hmax raster and pull the dep raster onto it (both stored
    with ~0.8 deg of rotation). On v4 at 3.125 m that is two ~60,000 x 80,000 float32
    grids (~20 GB each). ⚠️ The cached arrays are SHARED, not copied. Callers must treat
    them as READ-ONLY.

    ``need_model`` — skip the 21 s SfincsModel open. The returned ``mod`` is only required
    to RE-DOWNSCALE a stale cache; callers that want the rasters alone should pass False
    and get ``mod is None``.
    """
    model_dir = Path(model_dir).resolve()
    fm = (
        Path(floodmap_fn).resolve()
        if floodmap_fn is not None
        else model_dir / "floodmap_hmax_lev3.tif"
    )
    key = None
    if memo and not force:
        # mtime in the key means a re-run (which rewrites the tif) self-invalidates.
        key = (model_dir, fm, fm.stat().st_mtime if fm.is_file() else None)
        if key in _FLOODMAP_MEMO:
            return _FLOODMAP_MEMO[key]
    dep_p = subgrid_dep(model_dir)
    depfile = str(dep_p)
    floodmap_fn = str(fm)
    fresh = floodmap_cache_fresh(model_dir, fm)

    mod = None
    if need_model or force or not fresh:
        mod = SfincsModel(
            str(model_dir), data_libs=[str(Path(data_dir) / "data_catalog.yml")], mode="r"
        )
        read_output(mod)

    if force or not fresh:
        da_zsmax = mod.output.data["zsmax"].max(dim="timemax")
        # Downscale to a temp file and os.replace() into position, so the cache is either
        # absent or COMPLETE — never a stub. This takes minutes; if it is interrupted
        # (Ctrl-C, kill, quota) a direct write leaves a short raster that reads back with
        # NO ERROR and scores the model bone DRY: CSI 0.00, every HWM "dry". That is a
        # broken file wearing the costume of a dramatic physics result, and it cost an
        # afternoon. os.replace is atomic within a filesystem, so the temp file sits
        # BESIDE the target.
        #
        # The temp name MUST keep the .tif extension: build_overviews asserts the
        # extension and dies on a .tmp suffix. It carries the PID: two processes
        # re-downscaling the same run at once (two agents' test suites on the port
        # fixture, 2026-11-12) shared one temp name, opened it "w" over each other and
        # left a 101 MB floodmap with no valid pixel. With a temp each, both are whole
        # and the last os.replace wins.
        fm.parent.mkdir(parents=True, exist_ok=True)
        tmp_fn = str(fm.parent / f".{fm.stem}.partial.{os.getpid()}.tif")
        downscale_floodmap_native(da_zsmax, depfile, tmp_fn, hmin=0.05, nrmax=1000)
        if not floodmap_is_native(tmp_fn, dep_p):  # cheap; guards the fix itself
            raise RuntimeError(f"{tmp_fn} is not on {dep_p}'s full-resolution lattice")
        if fm.is_file() and not floodmap_is_native(fm, dep_p):
            _move_aside_pre_native(fm)
        os.replace(tmp_fn, floodmap_fn)
    da_hmax = _open_north_up(floodmap_fn)  # de-rotate to north-up

    # ⚠️ Key on (device, inode), NOT on the path. `dedupe_experiment_inputs.py` HARDLINKS
    # identical subgrid tifs between arms, and Path.resolve() only collapses SYMlinks — so
    # a path key gives every arm a distinct entry for one physical file and the memo never
    # hits. (Measured: it silently did nothing until this changed.) The target grid is in
    # the key too, so a run whose de-rotated hmax grid differs can never silently receive
    # a mismatched dep.
    st = Path(depfile).stat()
    tgt = (da_hmax.rio.shape, tuple(da_hmax.rio.transform()), str(da_hmax.rio.crs))
    dkey = (st.st_dev, st.st_ino, st.st_mtime, tgt)
    da_dep = _DEP_MEMO.get(dkey)
    if da_dep is None:
        da_dep = _open_north_up(depfile, match=da_hmax)
        if len(_DEP_MEMO) >= _DEP_MEMO_MAX:
            _DEP_MEMO.pop(next(iter(_DEP_MEMO)))
        _DEP_MEMO[dkey] = da_dep

    da_hmax = da_hmax.where(da_dep.values > -0.5)  # drop deep ocean
    da_hmax.name = "hmax"
    # which floodmap this is, for the metric row (``evaluate`` stamps ``floodmap``)
    da_hmax.attrs["floodmap_fn"] = floodmap_fn
    da_hmax.attrs["floodmap"] = floodmap_label(floodmap_fn, dep_p)
    out = (mod, da_hmax, da_dep)
    if key is not None:
        if len(_FLOODMAP_MEMO) >= _FLOODMAP_MEMO_MAX:
            _FLOODMAP_MEMO.pop(next(iter(_FLOODMAP_MEMO)))  # FIFO, bounded memory
        _FLOODMAP_MEMO[key] = out
    return out
