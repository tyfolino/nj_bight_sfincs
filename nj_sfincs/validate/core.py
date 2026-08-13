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
        ds = xu.open_dataset(fn_map) if lazy else xu.load_dataset(fn_map)
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


def cache_clear():
    """Drop every in-process memo (frees the pinned rasters and zs arrays)."""
    _FLOODMAP_MEMO.clear()
    _DEP_MEMO.clear()
    _ZS_MEMO.clear()


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


def load_floodmap(
    model_dir: Path,
    force: bool = False,
    memo: bool = True,
    need_model: bool = True,
    data_dir: Path = DATA,
):
    """Open the run read-only and downscale zsmax onto the L3 subgrid DEM.

    Returns ``(mod, da_hmax, da_dep)`` — the model handle plus the north-up depth-max and
    subgrid-DEM rasters the spatial metrics sample.

    The downscale is CACHED as ``floodmap_hmax_lev3.tif`` in the run dir and reused when it
    is newer than the run's sfincs_map.nc. Staleness is the mtime comparison, not existence:
    a re-run of the same experiment rewrites sfincs_map.nc and must invalidate the tif.

    ``memo`` — the in-process cache. The on-disk tif skips the *downscale*, but every call
    still pays to de-rotate a 14596x11684 hmax raster and pull a 29192x23368 3.125 m dep
    raster onto it (both are stored with ~0.76 deg of shear). That is ~2 min a call.
    ⚠️ The cached arrays are SHARED, not copied — copying would double ~2 GB per entry.
    Callers must treat them as READ-ONLY.

    ``need_model`` — skip the 21 s SfincsModel open. The returned ``mod`` is only required
    to RE-DOWNSCALE a stale cache; callers that want the rasters alone should pass False
    and get ``mod is None``.
    """
    model_dir = Path(model_dir).resolve()
    key = None
    if memo and not force:
        fm_p = model_dir / "floodmap_hmax_lev3.tif"
        # mtime in the key means a re-run (which rewrites the tif) self-invalidates.
        key = (model_dir, fm_p.stat().st_mtime if fm_p.is_file() else None)
        if key in _FLOODMAP_MEMO:
            return _FLOODMAP_MEMO[key]
    depfile = str(model_dir / "subgrid" / "dep_subgrid_lev3.tif")
    floodmap_fn = str(model_dir / "floodmap_hmax_lev3.tif")

    fm, mp = Path(floodmap_fn), model_dir / "sfincs_map.nc"
    fresh = fm.is_file() and (not mp.is_file() or fm.stat().st_mtime >= mp.stat().st_mtime)

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
        # afternoon. os.replace is atomic within a filesystem.
        #
        # The temp name MUST keep the .tif extension: downscale_floodmap calls
        # build_overviews, which asserts the extension and dies on a .tmp suffix.
        tmp_fn = str(model_dir / ".floodmap_hmax_lev3.partial.tif")
        utils.downscale_floodmap(
            zsmax=da_zsmax, dep=depfile, hmin=0.05, floodmap_fn=tmp_fn, nrmax=1000
        )
        os.replace(tmp_fn, floodmap_fn)
    da_hmax = rioxarray.open_rasterio(floodmap_fn, masked=True).squeeze(drop=True)
    da_hmax = da_hmax.rio.reproject(da_hmax.rio.crs)  # de-rotate to north-up

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
        da_dep = rioxarray.open_rasterio(depfile, masked=True).squeeze(drop=True)
        da_dep = da_dep.rio.reproject_match(da_hmax)
        if len(_DEP_MEMO) >= _DEP_MEMO_MAX:
            _DEP_MEMO.pop(next(iter(_DEP_MEMO)))
        _DEP_MEMO[dkey] = da_dep

    da_hmax = da_hmax.where(da_dep.values > -0.5)  # drop deep ocean
    da_hmax.name = "hmax"
    out = (mod, da_hmax, da_dep)
    if key is not None:
        if len(_FLOODMAP_MEMO) >= _FLOODMAP_MEMO_MAX:
            _FLOODMAP_MEMO.pop(next(iter(_FLOODMAP_MEMO)))  # FIFO, bounded memory
        _FLOODMAP_MEMO[key] = out
    return out
