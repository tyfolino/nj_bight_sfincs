"""Figures. Generic panel machinery, parameterised on the DOMAIN.

WHAT IS DELIBERATELY NOT HERE. The previous version of this module was 1,545 lines, and
most of that was one figure per named place: a Shrewsbury window, a Sandy Hook Bay box, a
Barnegat gauge dict, a hand-written per-gauge label table. Every one of them had to be
found and edited to move the model, and any that was missed produced a figure of the wrong
place with a confident title.

So: the window comes from ``Domain.plot_window`` or ``Domain.map_windows``, the gauges come
from ``Domain.obs_gauges``, the basins come from ``Domain.hwm_rules``, and there are no
place names in this file.

⭐ THE SAMPLER IS SHARED WITH THE SCORER. ``_sample_hwm`` defers to ``validate`` for the
estimator, the radius and the wet threshold. It used to be an independent copy, which meant
a figure and the CSV beside it could silently disagree about what a mark's modelled level
even is.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import xarray as xr
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch

import rioxarray  # noqa: F401  (registers .rio)

from . import domain as _domain
from .config import DATA, exp_root



def _hwm_path(data_dir):
    """The HWM file for the ACTIVE domain, under `data_dir`.

    🔴 Domain-dependent on purpose. `v1_monmouth` scores against the archived 95-mark
    file (38 scored) and the port fixture is pinned to it; `v1_5_raritan` reaches into
    Raritan Bay and is entitled to the marks there. Resolving by name alone would have
    silently rescored the port fixture the moment a bigger file appeared.

    `data_dir` is honoured so a run dir carrying its own copy still works; only the
    filename comes from the registry.
    """
    from pathlib import Path

    from . import domain as _domain  # noqa: PLC0415

    rel = _domain.active().hwm_geojson
    return Path(data_dir) / rel.parent.name / rel.name

def _run_dir(run, root=None) -> Path:
    """Accept an experiment NAME or an explicit path."""
    p = Path(run)
    if p.is_dir() and (p / "sfincs.inp").is_file():
        return p
    return (Path(root) if root else exp_root()) / str(run)


def _runs_dict(runs, root):
    return runs if isinstance(runs, dict) else {r: r for r in runs}


def _window(window):
    """Resolve a window name / tuple / None to a tuple, defaulting to the domain's."""
    dom = _domain.active()
    if window is None:
        return dom.plot_window
    if isinstance(window, str):
        if window not in dom.map_windows:
            raise KeyError(
                f"domain {dom.name!r} has no map window {window!r}; "
                f"known: {sorted(dom.map_windows)}. Add it to Domain.map_windows."
            )
        return dom.map_windows[window]
    return window


# ── rasters ──────────────────────────────────────────────────────────────────


def load_cached_floodmap(run_dir, window=None):
    """Read the flood-depth raster ``validate.load_floodmap`` already wrote to disk.

    ``load_floodmap`` caches ``floodmap_hmax_lev3.tif`` in the run dir but writes it in the
    model's ROTATED frame; the de-rotation and the deep-ocean mask happen afterwards, in
    memory. So repeat that tail here rather than reading the tif raw, or panels will not
    line up with each other.

    CLIP BEFORE REPROJECTING. The L3 raster is thousands of pixels on a side at 6.25 m, and
    de-rotating the whole thing costs minutes per run; clipping to ``window`` first drops it
    to ~0.3 s. The rotation is <1 degree, so a CRS bbox clip in the rotated frame is a cheap
    window read that comfortably contains the target area.

    Returns ``(da_hmax, da_dep)``, or ``(None, None)`` if the run has not been downscaled
    yet — a missing tif is an expected state, not an error.

    ⚠️ A tif that EXISTS is trusted here, which is only safe because ``load_floodmap``
    writes the cache ATOMICALLY (temp file + os.replace). Before it did, a write interrupted
    mid-flight left a short raster that read back WITHOUT ERROR and scored the model bone
    DRY — CSI 0.00, every HWM "dry": a spectacular physics result that was really a broken
    file. Do not weaken that write.

    ⚠️ Do NOT try to catch stubs by file size here. A healthy floodmap is only 0.11–0.16x
    its dep raster — it is sparse, mostly nodata off the flooded area — and no size band
    separates "sparse because the coast barely flooded" from "sparse because the write
    died". Atomicity at the write is the check; there is no reliable one at the read.
    """
    run_dir = Path(run_dir)
    tif = run_dir / "floodmap_hmax_lev3.tif"
    # Same preference as validate.load_floodmap: the merged all-level DEM when it
    # exists, the finest-level raster otherwise (STATUS 2026-08-29).
    dep_fn = run_dir / "subgrid" / "dep_subgrid_merged.tif"
    if not dep_fn.exists():
        dep_fn = run_dir / "subgrid" / "dep_subgrid_lev3.tif"
    if not tif.exists() or not dep_fn.exists():
        return None, None
    hmax = rioxarray.open_rasterio(tif, masked=True).squeeze(drop=True)
    dep = rioxarray.open_rasterio(dep_fn, masked=True).squeeze(drop=True)
    window = _window(window)
    if window is not None:
        x0, x1, y0, y1 = window
        hmax = hmax.rio.clip_box(x0, y0, x1, y1)
        dep = dep.rio.clip_box(x0, y0, x1, y1)
    hmax = hmax.rio.reproject(hmax.rio.crs)  # de-rotate to north-up
    dep = dep.rio.reproject_match(hmax)
    hmax = hmax.where(dep.values > -0.5)  # drop the deep ocean
    hmax.name = "hmax"
    return hmax, dep


def _extent(da):
    """(left, right, bottom, top) for imshow, from a north-up raster."""
    x, y = da["x"].values, da["y"].values
    dx = abs(float(x[1] - x[0])) / 2 if x.size > 1 else 0.0
    dy = abs(float(y[1] - y[0])) / 2 if y.size > 1 else 0.0
    return (
        float(x.min()) - dx,
        float(x.max()) + dx,
        float(y.min()) - dy,
        float(y.max()) + dy,
    )


#: Roughly how many pixels a panel is actually drawn at. Feeding imshow much more than this
#: is pure waste — matplotlib resamples it all down to the same figure.
_DISPLAY_PX = 1600


def _for_display(da, window=None, max_px: int = _DISPLAY_PX):
    """Crop a raster to ``window`` and decimate it to display resolution.

    ⚡ WHY. A de-rotated raster is ~171 Mpx. The panel plotters were handing the WHOLE array
    to ``imshow`` and then cropping with ``set_xlim``, so matplotlib resampled 171 Mpx per
    panel — three panels = 513 Mpx — to fill a figure about 1600 px wide. That is ~10^5x
    oversampling and it was the reason an HWM panel took minutes.

    Cropping first and striding to ~``max_px`` is visually identical at figure resolution
    (the decimation factor is chosen so the result is still >= the drawn pixel count).
    Only the BACKDROP goes through here; marks are always sampled at full resolution, so no
    number on any figure changes.
    """
    x, y = da["x"].values, da["y"].values
    if window is not None:
        xmin, xmax, ymin, ymax = window
        ix = np.where((x >= xmin) & (x <= xmax))[0]
        iy = np.where((y >= ymin) & (y <= ymax))[0]
        if ix.size and iy.size:
            da = da.isel(
                x=slice(int(ix[0]), int(ix[-1]) + 1), y=slice(int(iy[0]), int(iy[-1]) + 1)
            )
    v = da.values
    v = v[0] if v.ndim == 3 else v
    step = max(1, int(np.ceil(max(v.shape) / max_px)))
    if step > 1:
        v = v[::step, ::step]
        da = da.isel(y=slice(None, None, step), x=slice(None, None, step))
    return v, _extent(da)


# ── high-water marks ─────────────────────────────────────────────────────────


def _sample_hwm(da_hmax, da_dep, data_dir=DATA, estimator=None, scored_only=False):
    """Shared HWM sampling for the scatter + residual figures.

    ⚠️ This defers to ``validate`` for the estimator, the radius and the wet threshold. It
    USED to be an independent copy of the scorer's sampler, which meant the figures and the
    scored CSV could silently disagree about what a mark's modelled level even is.

    ``scored_only`` — restrict to the marks the scorer actually SCORES (on this model's
    grid, so a dry mark can still be scored at ground level; quality <= 2).

    ⭐ WHY ``scored_only`` EXISTS. The mark file spans the FULL coast, not one domain, so
    marks outside the mesh read back exactly like dry ones: ``mod_wse`` stays NaN and
    ``wet`` is False. Residual panels were captioning runs "40 dry" when the scored dry
    count was **0** — the marks were absent, not dry, and the figure was reporting the size
    of the HWM file rather than a model failure.
    """
    from .validate import DEPTH_MIN, HWM_ESTIMATOR_DEFAULT, HWM_RADIUS_M
    from .validate.metrics import _clip_to_region

    estimator = estimator or HWM_ESTIMATOR_DEFAULT
    GROUND_CAP = 0.5
    # Same region screen as the scorer, or the panels plot marks the CSV never scored.
    hwm = _clip_to_region(gpd.read_file(str(_hwm_path(data_dir))).to_crs(da_dep.rio.crs))
    depth, dep_arr, wse = da_hmax.values, da_dep.values, (da_dep + da_hmax).values
    if depth.ndim == 3:
        depth, wse, dep_arr = depth[0], wse[0], dep_arr[0]
    T = da_dep.rio.transform()
    ny, nx = wse.shape
    rad = int(round(HWM_RADIUS_M / abs(T.a)))
    obs = hwm["elev_m"].values
    qual = hwm["quality"].values.astype(float)
    mod_wse = np.full(len(obs), np.nan)
    # The lowest bed near the mark. Finite <=> the mark is ON this model's grid, which is
    # how the scorer separates "the model ran dry here" from "this mark is not in this
    # domain".
    mod_ground = np.full(len(obs), np.nan)
    for k, (X, Y) in enumerate(zip(hwm.geometry.x.values, hwm.geometry.y.values)):
        col, row = int((X - T.c) / T.a), int((Y - T.f) / T.e)
        if 0 <= row < ny and 0 <= col < nx:
            r0, c0 = max(0, row - rad), max(0, col - rad)
            sl = (slice(r0, row + rad + 1), slice(c0, col + rad + 1))
            ws, hh, dd = wse[sl], depth[sl], dep_arr[sl]
            if np.isfinite(dd).any():
                mod_ground[k] = np.nanmin(dd)
            flooded = (hh >= DEPTH_MIN) & (dd <= obs[k] + GROUND_CAP)
            if flooded.any():
                vals = ws[flooded]
                if estimator == "median":
                    mod_wse[k] = np.nanmedian(vals)
                elif estimator == "max":
                    mod_wse[k] = np.nanmax(vals)
                else:
                    rr, cc = np.nonzero(flooded)
                    j = int(np.argmin((rr - (row - r0)) ** 2 + (cc - (col - c0)) ** 2))
                    mod_wse[k] = ws[rr[j], cc[j]]
    wet = np.isfinite(mod_wse)
    if scored_only:
        keep = np.isfinite(np.where(wet, mod_wse, mod_ground)) & (qual <= 2)
        hwm, obs = hwm.loc[keep].copy(), obs[keep]
        mod_wse, wet, qual = mod_wse[keep], wet[keep], qual[keep]
    return hwm, obs, mod_wse, mod_wse - obs, wet, qual


def plot_hwm_scatter(da_hmax, da_dep, data_dir=DATA):
    """Modelled still-water WSE vs USGS HWMs, 1:1 scatter, coloured by mark quality.

    ⚠️ ``quality`` is the VERTICAL accuracy. It says nothing about WHERE the mark is —
    almost every Sandy mark was located by "Map (digital or paper)", the lowest-accuracy
    horizontal method USGS records, which is the entire justification for scoring against a
    window rather than a cell.
    """
    import matplotlib.pyplot as plt

    _, obs, mod_wse, _, wet, qual = _sample_hwm(da_hmax, da_dep, data_dir)
    q2 = qual <= 2
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(
        obs[wet & ~q2], mod_wse[wet & ~q2], facecolor="none", edgecolor="grey",
        s=55, lw=0.8, label="q3-4",
    )
    sc = ax.scatter(
        obs[wet & q2], mod_wse[wet & q2], c=qual[wet & q2], cmap="viridis_r",
        s=60, edgecolor="k", lw=0.4, vmin=1, vmax=5, label="q1-2 (headline)",
    )
    finite = np.isfinite(obs) & np.isfinite(mod_wse)
    lo = float(np.floor(min(obs[finite].min(), mod_wse[finite].min()) * 2) / 2)
    hi = float(np.ceil(max(obs[finite].max(), mod_wse[finite].max()) * 2) / 2)
    lim = [lo, hi]
    ax.plot(lim, lim, "k--", lw=1, label="1:1")
    ax.fill_between(
        lim, [x - 0.5 for x in lim], [x + 0.5 for x in lim], color="grey", alpha=0.15
    )
    ax.set_xlim(lim)
    ax.set_ylim(lim)
    ax.set_aspect("equal")
    ax.set_xlabel("Observed HWM [m NAVD88]")
    ax.set_ylabel("Modelled still-water WSE [m NAVD88]")
    ax.set_title("Modelled still-water vs USGS HWMs")
    fig.colorbar(sc, ax=ax, shrink=0.8, label="HWM quality (1=best)")
    ax.legend(loc="upper left")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    return fig, ax


def plot_hwm_residual_panels(runs, root=None, data_dir=DATA, ncol=2):
    """HWM residuals (model − obs) for several runs side by side.

    Red = model too high, blue = too low, black ✕ = model dry where a mark says wet.
    Runs without a downscaled flood map are skipped rather than erroring.

    The window comes from the marks THIS DOMAIN SCORES, taken once from the first run and
    then shared, so the panels are directly comparable and none of them spends half its
    height on ground the model does not cover.
    """
    import matplotlib.pyplot as plt

    from .validate import load_floodmap

    root = Path(root) if root else exp_root()
    runs = _runs_dict(runs, root)
    runs = {k: v for k, v in runs.items() if (root / v / "sfincs_map.nc").exists()}
    if not runs:
        raise SystemExit("no finished runs among those given")

    _first = next(iter(runs.values()))
    _, _h0, _d0 = load_floodmap(root / _first, need_model=False, data_dir=data_dir)
    hwm0 = _sample_hwm(_h0, _d0, data_dir, scored_only=True)[0]
    if not len(hwm0):
        raise SystemExit("no scored HWMs on this domain — nothing to draw")
    margin = 2000.0
    xs, ys = hwm0.geometry.x, hwm0.geometry.y
    win = (xs.min() - margin, xs.max() + margin, ys.min() - margin, ys.max() + margin)
    aspect = (win[1] - win[0]) / (win[3] - win[2])

    n = len(runs)
    ncol = min(ncol, n)
    nrow = int(np.ceil(n / ncol))
    fig, axes = plt.subplots(
        nrow, ncol, figsize=(6.5 * aspect * ncol + 1.6, 6.5 * nrow),
        squeeze=False, constrained_layout=True,
    )

    sc = None
    for ax, (label, name) in zip(axes.ravel(), runs.items()):
        # need_model=False skips a 21 s SfincsModel open per run; only the rasters are used.
        _, hmax, dep = load_floodmap(root / name, need_model=False, data_dir=data_dir)
        hwm, _obs, _mw, resid, wet, _q = _sample_hwm(
            hmax, dep, data_dir, scored_only=True
        )
        bg, ext = _for_display(dep, window=win)
        ax.imshow(
            bg, extent=ext, origin="upper", cmap="Greys_r",
            vmin=-15, vmax=25, alpha=0.55, interpolation="nearest",
        )
        hx, hy = hwm.geometry.x.values, hwm.geometry.y.values
        sc = ax.scatter(
            hx[wet], hy[wet], c=resid[wet], cmap="RdBu_r", vmin=-1.5, vmax=1.5,
            s=55, edgecolor="k", lw=0.5, zorder=5,
        )
        ax.scatter(
            hx[~wet], hy[~wet], marker="x", color="k", s=55, lw=1.4, zorder=6,
            label=f"model dry ({int((~wet).sum())})",
        )
        med = np.nanmedian(resid[wet]) if wet.any() else np.nan
        # n and the dry count are over the SCORED marks, so this caption is readable
        # against hwm_n_scored / hwm_n_dry_scored in the CSV and cannot drift from it.
        ax.set_title(
            f"{label}\nmedian {med:+.2f} m · {int((~wet).sum())} dry of {len(wet)} scored",
            fontsize=9,
        )
        ax.set_xlim(win[0], win[1])
        ax.set_ylim(win[2], win[3])
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.legend(loc="upper right", fontsize=8)

    for ax in axes.ravel()[n:]:
        ax.axis("off")
    if sc is not None:
        fig.colorbar(sc, ax=axes, shrink=0.55).set_label("HWM residual: model − obs [m]")
    fig.suptitle("HWM residuals — red = model high, blue = low", fontsize=11)
    return fig, axes


# ── flood extent ─────────────────────────────────────────────────────────────


#: (run dir, map mtime) -> bool. Trivial, but the probe opens a netCDF per panel.
_WAVES_OFF_MEMO: dict[tuple, bool] = {}


def _waves_off(model_dir) -> bool:
    """Did this run have SnapWave OFF? Read from the RUN, not the arm registry.

    A run dir is not always a registered arm — a staged copy, a bracket, or something a
    collaborator handed over all score fine and none of them resolve in ``EXPERIMENTS``.
    The output file always knows: with SnapWave off, SFINCS writes no wave variables at
    all (measured on ``naccs-nowaves``: no ``hm0``, ``snapwavemsk``, ``tp``/``wavdir``).
    """
    import xarray as xr  # noqa: PLC0415

    mp = Path(model_dir) / "sfincs_map.nc"
    key = (str(mp), mp.stat().st_mtime if mp.is_file() else None)
    if key not in _WAVES_OFF_MEMO:
        with xr.open_dataset(mp) as ds:
            _WAVES_OFF_MEMO[key] = not any(
                v in ds.variables for v in ("hm0", "snapwavemsk")
            )
    return _WAVES_OFF_MEMO[key]


def _motf_window(dep, motf, m_nd, Xc, Yc, _2d, sim, margin: float = 2000.0):
    """Bounding box of the ground the MOTF comparison actually scores, plus a margin.

    That ground is ``MOTF valid AND model land AND actually simulated`` — the same
    ``land_in`` screen the
    panels use — so the view is the CSI's own support and nothing scored falls outside
    it. The MOTF sheet covers the whole NY Bight; a single domain covers a fraction of
    it, and drawing the sheet's full extent left the comparison a smudge in one corner.

    Derived from ONE run and shared by every panel, so the panels stay comparable. Cheap
    (~0.2 s): it re-gathers dep at MOTF centres, which ``np.ix_`` broadcasts rather than
    materialising the two 240 MB index grids ``meshgrid`` would.
    """
    mod_t = dep.rio.transform()
    mc = np.clip(((Xc - mod_t.c) / mod_t.a).astype(int), 0, dep.shape[-1] - 1)
    mr = np.clip(((Yc - mod_t.f) / mod_t.e).astype(int), 0, dep.shape[-2] - 1)
    land = (motf != m_nd) & (_2d(dep.values)[np.ix_(mr, mc)] > 0.0) & sim
    rows, cols = np.where(land.any(axis=1))[0], np.where(land.any(axis=0))[0]
    if not rows.size or not cols.size:  # no overlap — fall back to the full sheet
        return (Xc.min(), Xc.max(), Yc.min(), Yc.max())
    xs, ys = Xc[cols], Yc[rows]
    return (
        float(xs.min() - margin),
        float(xs.max() + margin),
        float(ys.min() - margin),
        float(ys.max() + margin),
    )


def plot_motf_panels(runs, root=None, data_dir=DATA, ncol=2, window=None, split_fa=False):
    """Modelled flood vs FEMA MOTF — hit / miss / false alarm — for several runs.

    ⚠️ READ THE CSI, NOT THE POD. FEMA MOTF is a HWM/sensor-interpolated *bathtub* surface
    that shares provenance with our own high-water marks (a flat 3.4 m fill reproduces it at
    IoU 0.906), so it is an extent CONSISTENCY check, not an independent observation. And
    its POD structurally REWARDS OVER-FLOODING: flood everything and you score a perfect
    POD. It is the mirror image of the wet-only HWM flaw, which rewards under-flooding. Use
    this to see WHERE the extent differs, not to rank runs.

    ⚠️ A WAVES-OFF PANEL IS DRAWN AND LABELLED, not withheld. Waves-off is a valid
    configuration (FINDINGS §4), so its CSI is real; it is just not on the same footing
    as a waves-on one — SnapWave is worth ΔCSI 0.018 here against ΔCSI 0.011 between the
    two waves-on arms. Such a panel is tagged **waves OFF** in its title, read off the
    run's own output, so a pair reads as two measurements rather than as a ranking.

    ``window`` — ``(xmin, xmax, ymin, ymax)`` in the model CRS. Default is the bounding
    box of the ground the CSI is actually computed over (MOTF valid AND model land),
    taken once from the first run and shared, so the panels stay directly comparable.
    The MOTF raster spans far more ground than any one domain covers, and drawing its
    full extent put the whole comparison in a corner of the axes.

    ⭐ THE WINDOW IS A VIEW, NOT A SCREEN. Every count, area and score below is computed
    over the FULL arrays; cropping happens only on the way to ``imshow``. Narrowing the
    window can never move a number on this figure.

    ``split_fa`` — draw false alarms in TWO colours by ``fa_decomp.sea_connected``:
    red for surge-plausible (the component touches tidal water), tan for
    never-sea-connected (rain / local runoff — water MOTF structurally cannot contain,
    FINDINGS §38). The headline CSI/POD/FAR are UNCHANGED; the connected-only
    ``CSIc``/``FARc`` are printed beside them, never instead (the fa_decomp convention).
    """
    import matplotlib.pyplot as plt
    import rasterio

    from .validate import DEPTH_MIN, load_floodmap, simulated_mask
    from .validate.metrics import motf_exclude_mask, motf_path

    root = Path(root) if root else exp_root()
    runs = _runs_dict(runs, root)
    runs = {k: v for k, v in runs.items() if (root / v / "sfincs_map.nc").exists()}
    if not runs:
        raise SystemExit("no finished runs among those given")

    with rasterio.open(str(motf_path(data_dir))) as r:
        motf, mtf, m_nd = r.read(1), r.transform, r.nodata
    mh, mw = motf.shape
    motf_wet = motf == 1
    # Domain-declared sheet-invalid ground (e.g. NY land on the NJ-only render) —
    # the SAME screen motf_metrics applies, or the panel and the CSV disagree.
    _excl = motf_exclude_mask(motf.shape, mtf)
    _valid = ~_excl if _excl is not None else np.ones(motf.shape, dtype=bool)

    # MOTF cell CENTRES. Run-independent, so they are built once.
    Xc = mtf.c + (np.arange(mw) + 0.5) * mtf.a
    Yc = mtf.f + (np.arange(mh) + 0.5) * mtf.e

    def _2d(a):
        return a[0] if a.ndim == 3 else a

    if window is None:
        _first = root / next(iter(runs.values()))
        window = _motf_window(
            load_floodmap(_first, need_model=False, data_dir=data_dir)[2],
            motf, m_nd, Xc, Yc, _2d,
            simulated_mask(_first, motf.shape, mtf) & _valid,
        )
    # Display slices: which MOTF rows/cols are inside the window. Used to CROP the drawn
    # rasters — a plain slice, no decimation, so every visible category pixel is still
    # drawn at full 15 m resolution and no isolated hit/miss can vanish into a stride.
    cs = np.where((Xc >= window[0]) & (Xc <= window[1]))[0]
    rs = np.where((Yc >= window[2]) & (Yc <= window[3]))[0]
    csl = slice(int(cs[0]), int(cs[-1]) + 1) if cs.size else slice(None)
    rsl = slice(int(rs[0]), int(rs[-1]) + 1) if rs.size else slice(None)
    cat_ext = [
        float(Xc[csl][0] - mtf.a / 2),
        float(Xc[csl][-1] + mtf.a / 2),
        float(Yc[rsl][-1] + mtf.e / 2),
        float(Yc[rsl][0] - mtf.e / 2),
    ]

    n = len(runs)
    ncol = min(ncol, n)
    nrow = int(np.ceil(n / ncol))
    # Size the figure to the WINDOW's aspect, as the HWM residual panel does. The old
    # hardcoded 5.4x8.6 was the MOTF sheet's shape and letterboxes any other window.
    aspect = (window[1] - window[0]) / (window[3] - window[2])
    fig, axes = plt.subplots(
        nrow, ncol, figsize=(max(3.6, 7.4 * aspect) * ncol, 7.4 * nrow), squeeze=False
    )
    cmap = ListedColormap(
        [(1, 1, 1, 0), (0.2, 0.6, 0.3, 1), (0.2, 0.4, 0.85, 1), (0.85, 0.2, 0.2, 1),
         (0.87, 0.66, 0.34, 1)]  # 4 = FA never sea-connected (split_fa only)
    )

    for ax, (label, name) in zip(axes.ravel(), runs.items()):
        _, hmax, dep = load_floodmap(root / name, need_model=False, data_dir=data_dir)
        mod_t = dep.rio.transform()
        mc = np.clip(((Xc - mod_t.c) / mod_t.a).astype(int), 0, dep.shape[-1] - 1)
        mr = np.clip(((Yc - mod_t.f) / mod_t.e).astype(int), 0, dep.shape[-2] - 1)
        rr, cc = np.meshgrid(mr, mc, indexing="ij")
        dep_at, h_at = _2d(dep.values)[rr, cc], _2d(hmax.values)[rr, cc]

        mod_wet = (h_at >= DEPTH_MIN) & np.isfinite(h_at)
        # ⚠️ THE SAME SCREEN motf_metrics USES, or the panel and the CSV disagree about
        # what was even compared. Cells the solver never ran are excluded in BOTH
        # directions — unreachable MOTF wet, and downscale bleed onto inactive faces.
        land_in = (motf != m_nd) & (dep_at > 0.0) & simulated_mask(
            root / name, motf.shape, mtf
        ) & _valid
        hits = motf_wet & mod_wet & land_in
        miss = motf_wet & ~mod_wet & land_in
        fa = ~motf_wet & mod_wet & land_in
        nh, nm_, nf = int(hits.sum()), int(miss.sum()), int(fa.sum())
        PIX = mtf.a * abs(mtf.e) / 1e6
        csi = nh / (nh + nm_ + nf) if (nh + nm_ + nf) else np.nan
        pod = nh / (nh + nm_) if (nh + nm_) else 0.0
        far = nf / (nh + nf) if (nh + nf) else 0.0

        cat = np.zeros_like(motf, dtype="uint8")
        cat[hits], cat[miss], cat[fa] = 1, 2, 3
        conn_line = ""
        if split_fa:
            from .validate.fa_decomp import sea_connected  # noqa: PLC0415

            fa_disc = fa & ~sea_connected(mod_wet, dep_at)
            cat[fa_disc] = 4
            nfd = int(fa_disc.sum())
            nfc = nf - nfd
            csi_c = nh / (nh + nm_ + nfc) if (nh + nm_ + nfc) else np.nan
            far_c = nfc / (nh + nfc) if (nh + nfc) else 0.0
            conn_line = f"\nsea-connected only: CSIc={csi_c:.2f}  FARc={far_c:.2f}"
        # ⚡ Crop + decimate the backdrop BEFORE imshow — see _for_display. This panel
        # used to hand matplotlib the whole 95 Mpx de-rotated dep and then crop with
        # set_xlim, resampling ~4 s per panel to fill a figure ~1600 px wide. The HWM
        # residual panel was fixed in that pass; this one was missed. Backdrop only —
        # every hit / miss / false-alarm count is sampled at full resolution below.
        bg, bg_ext = _for_display(dep, window=window)
        ax.imshow(
            bg, extent=bg_ext, cmap="Greys", vmin=-5, vmax=20,
            alpha=0.45, origin="upper",
        )
        ax.imshow(
            cat[rsl, csl], cmap=cmap, vmin=0, vmax=4, extent=cat_ext, origin="upper",
            interpolation="nearest",
        )
        ax.set_aspect("equal")
        ax.set_xlim(window[0], window[1])
        ax.set_ylim(window[2], window[3])
        # Tag the panel from the RUN's own output rather than leaving the reader to
        # remember which arm had SnapWave off. FINDINGS §4.
        tag = "  ·  waves OFF" if _waves_off(root / name) else ""
        ax.set_title(
            f"{label}{tag}\nCSI={csi:.2f}  POD={pod:.2f}  FAR={far:.2f}{conn_line}",
            fontsize=10,
            color="#8a4500" if tag else "black",
        )
        if split_fa:
            fa_handles = [
                Patch(color=cmap(3), label=f"false alarm, sea-connected ({nfc * PIX:.1f} km²)"),
                Patch(color=cmap(4), label=f"false alarm, never connected ({nfd * PIX:.1f} km²)"),
            ]
        else:
            fa_handles = [Patch(color=cmap(3), label=f"false alarm ({nf * PIX:.1f} km²)")]
        ax.legend(
            handles=[
                Patch(color=cmap(1), label=f"hit ({nh * PIX:.1f} km²)"),
                Patch(color=cmap(2), label=f"miss ({nm_ * PIX:.1f} km²)"),
                *fa_handles,
            ],
            loc="upper right",
            fontsize=7,
        )

    for ax in axes.ravel()[len(runs) :]:
        ax.axis("off")
    fig.tight_layout()
    return fig, axes


def plot_depth_panels(
    runs, root=None, window=None, vmax=3.0, hwm=True, ncol=None, panel_h=7.0,
    data_dir=DATA,
):
    """Max flood depth for several runs side by side, over the domain's plot window.

    Reads the cached tifs, so it is seconds rather than the minutes a re-downscale costs.

    ⚠️ HWMs are drawn as LOCATION markers only, deliberately uncoloured: ``elev_m`` is a
    water-surface ELEVATION while the raster is a DEPTH, so putting them on one colour
    scale would look meaningful and mean nothing. For the signed residual use
    ``plot_hwm_residual_panels``.
    """
    import matplotlib.pyplot as plt

    root = Path(root) if root else exp_root()
    runs = _runs_dict(runs, root)
    window = _window(window)
    if window is None:
        raise ValueError(
            f"domain {_domain.active().name!r} declares no plot_window and none was "
            "given. Set Domain.plot_window, or pass window=(x0, x1, y0, y1)."
        )
    n = len(runs)
    ncol = ncol or min(4, n)
    nrow = int(np.ceil(n / ncol))
    # Size each panel to the window's aspect, otherwise most of the figure is whitespace.
    aspect = (window[1] - window[0]) / (window[3] - window[2])
    fig, axes = plt.subplots(
        nrow, ncol, figsize=(panel_h * aspect * ncol + 1.6, panel_h * nrow),
        squeeze=False, constrained_layout=True,
    )

    pts = None
    if hwm:
        f = _hwm_path(data_dir)
        if f.exists():
            from .validate.metrics import _clip_to_region

            pts = gpd.read_file(str(f)).to_crs(f"EPSG:{_domain.active().epsg}")
            pts = _clip_to_region(pts)
            pts = pts[pts["quality"].astype(float) <= 2]

    im = None
    for ax, (title, run) in zip(axes.ravel(), runs.items()):
        hmax, dep = load_cached_floodmap(root / run, window=window)
        if hmax is None:
            ax.text(
                0.5, 0.5, f"{run}\n\nnot downscaled yet", ha="center", va="center",
                transform=ax.transAxes, fontsize=10, color="0.4",
            )
            ax.set_xticks([])
            ax.set_yticks([])
            continue
        ext = _extent(hmax)
        # land/water context so dry ground is legible instead of blank white
        ax.imshow(
            dep.values, extent=ext, origin="upper", cmap="Greys_r",
            vmin=-15, vmax=25, alpha=0.55, interpolation="nearest",
        )
        im = ax.imshow(
            np.where(hmax.values > 0.05, hmax.values, np.nan), extent=ext,
            origin="upper", cmap="Blues", vmin=0, vmax=vmax, interpolation="nearest",
        )
        if pts is not None:
            ax.scatter(
                pts.geometry.x, pts.geometry.y, facecolor="none", edgecolor="red",
                s=30, linewidth=0.8, zorder=5,
            )
        ax.set_title(title, fontsize=10)
        ax.set_xlim(window[0], window[1])
        ax.set_ylim(window[2], window[3])
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])

    for ax in axes.ravel()[n:]:
        ax.axis("off")
    if im is not None:
        fig.colorbar(im, ax=axes, shrink=0.55, anchor=(0, 0.5)).set_label(
            "max flood depth [m]"
        )
    fig.suptitle(
        "Max flood depth (red circles = USGS high-water-mark locations, quality ≤ 2)",
        fontsize=12,
    )
    return fig, axes


def plot_depth_difference(
    run_a, run_b, root=None, window=None, vlim=1.5, label_a=None, label_b=None
):
    """Depth difference b − a: WHERE one run puts water the other does not.

    Both runs must sit on the same mesh, so the cached rasters share a grid and subtract
    cleanly. ⚠️ A cell dry in one run and wet in the other is the whole point, so dry is
    treated as depth 0 rather than NaN; masking only where BOTH are dry keeps those cells
    in. Masking either would erase exactly the difference being looked for.
    """
    import matplotlib.pyplot as plt

    root = Path(root) if root else exp_root()
    window = _window(window)
    ha, dep = load_cached_floodmap(root / run_a, window=window)
    hb, _ = load_cached_floodmap(root / run_b, window=window)
    if ha is None or hb is None:
        raise FileNotFoundError(
            f"missing cached floodmap for {run_a if ha is None else run_b} — "
            "run validate.load_floodmap() on it first"
        )
    hb = hb.rio.reproject_match(ha)
    a = np.where(np.isfinite(ha.values), ha.values, 0.0)
    b = np.where(np.isfinite(hb.values), hb.values, 0.0)
    diff = np.where((a > 0.05) | (b > 0.05), b - a, np.nan)

    ext = _extent(ha)
    fig, ax = plt.subplots(figsize=(9.5, 8.4), constrained_layout=True)
    ax.imshow(
        dep.values, extent=ext, origin="upper", cmap="Greys_r",
        vmin=-15, vmax=25, alpha=0.55, interpolation="nearest",
    )
    im = ax.imshow(
        diff, extent=ext, origin="upper", cmap="RdBu_r", vmin=-vlim, vmax=vlim,
        interpolation="nearest",
    )
    fig.colorbar(im, ax=ax, shrink=0.7).set_label("Δ max flood depth [m]")
    if window is not None:
        ax.set_xlim(window[0], window[1])
        ax.set_ylim(window[2], window[3])
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    lb, la = label_b or run_b, label_a or run_a
    ax.set_title(
        f"{lb}  −  {la}\nred = deeper in {lb}   ·   blue = deeper in {la}", fontsize=11
    )
    return fig, ax


# ── the boundary itself ──────────────────────────────────────────────────────


def plot_waterlevel_boundary_panels(runs, root=None, region=None, ncol=2, pad=3000.0):
    """WHERE each run's water-level boundary support points are, and how high they peak.

    One map per run, reading ``sfincs_netbndbzsbzifile.nc`` — the boundary file the solver
    was actually handed, not the catalogue source it came from. Points are coloured by peak
    zs on ONE shared scale so the panels are directly comparable, over the domain outline.

    ⭐ THIS IS THE FIGURE THE WHOLE DOMAIN ARGUMENT TURNS ON, so read the frame carefully.
    Some support points sit OUTSIDE it, and that is not a rendering accident. A two-node
    gauge boundary's support points can be tens of kilometres north and south of the mesh —
    SFINCS interpolates ALONG the boundary between them, so the domain contains none of its
    own boundary information, and a linear interpolation between two exterior points cannot
    produce an interior maximum however good those two points are. A dense ADCIRC product
    puts its points inside the frame instead. Letting the axes grow to fit the far anchors
    would put most of every panel on empty ocean and hide exactly that contrast, so
    out-of-frame points are counted in the title and listed with their peaks.

    ``runs``: {label: experiment_dir_name_or_path}, or a list of names.
    """
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
    import matplotlib.pyplot as plt

    dom = _domain.active()
    root = Path(root) if root else exp_root()
    runs = _runs_dict(runs, root)

    bnd = {}
    for label, name in runs.items():
        p = root / name / "sfincs_netbndbzsbzifile.nc"
        if not p.exists():
            continue
        ds = xr.open_dataset(p)
        # The cells SFINCS actually forces (mask == 2), read PER RUN rather than assumed
        # shared: two arms differing in their mask is exactly the kind of thing this
        # figure should show rather than hide.
        #
        # ⚡ Straight xarray on sfincs.nc, NOT SfincsModel.quadtree_grid — the mask and
        # face coordinates are plain arrays and open in ~1 s. The ~17 s that read costs
        # elsewhere is hydromt re-deriving edge connectivity, which nothing here needs.
        g = root / name / "sfincs.nc"
        cells = None
        if g.exists():
            q = xr.open_dataset(g)
            sel = q["mask"].values == 2
            cells = (q["mesh2d_face_x"].values[sel], q["mesh2d_face_y"].values[sel])
        bnd[label] = (ds.x.values, ds.y.values, ds["zs"].max("time").values, cells)
    if not bnd:
        raise SystemExit("no sfincs_netbndbzsbzifile.nc among the runs given")

    reg = gpd.read_file(str(region or dom.region)).to_crs(f"EPSG:{dom.epsg}")
    minx, miny, maxx, maxy = reg.total_bounds
    ext = [minx - pad, maxx + pad, miny - pad, maxy + pad]
    # Shared colour scale over the points that are actually DRAWN. Including far-field
    # anchors would stretch it over coast the domain cannot see.
    vis = [
        pk[(x >= ext[0]) & (x <= ext[1]) & (y >= ext[2]) & (y <= ext[3])]
        for x, y, pk, _ in bnd.values()
    ]
    vis = np.concatenate([v for v in vis if v.size]) if any(v.size for v in vis) else None
    vmin, vmax = (float(vis.min()), float(vis.max())) if vis is not None else (0.0, 1.0)

    proj = ccrs.epsg(dom.epsg)
    n = len(bnd)
    ncol = min(ncol, n)
    nrow = int(np.ceil(n / ncol))
    # Size each panel to the DOMAIN's aspect. Cartopy holds the map aspect fixed, so a
    # figure shaped to anything else just pads the difference with whitespace.
    aspect = (ext[1] - ext[0]) / (ext[3] - ext[2])
    pw = 6.4
    fig, axes = plt.subplots(
        nrow, ncol, figsize=(pw * ncol, (pw / aspect) * nrow + 1.0), squeeze=False,
        subplot_kw={"projection": proj}, constrained_layout=True,
    )

    sc = None
    for ax, (label, (x, y, pk, cells)) in zip(axes.ravel(), bnd.items()):
        ax.add_feature(cfeature.OCEAN.with_scale("10m"), facecolor="#dbeaf3", zorder=0)
        ax.add_feature(cfeature.LAND.with_scale("10m"), facecolor="#f2efe9", zorder=0)
        ax.coastlines("10m", linewidth=0.6, color="0.4")
        ax.add_feature(cfeature.STATES.with_scale("10m"), linewidth=0.5, edgecolor="0.55")
        for geom in reg.geometry:
            for pg in geom.geoms if geom.geom_type == "MultiPolygon" else [geom]:
                ax.plot(*pg.exterior.xy, color="red", lw=1.4, transform=proj, zorder=3)

        n_forced = 0
        if cells is not None:
            n_forced = len(cells[0])
            ax.scatter(
                cells[0], cells[1], c="0.45", s=1.2, marker="s", transform=proj,
                zorder=2, label=f"forced cells ({n_forced:,})",
            )
        inside = (x >= ext[0]) & (x <= ext[1]) & (y >= ext[2]) & (y <= ext[3])
        if inside.any():
            sc = ax.scatter(
                x[inside], y[inside], c=pk[inside], cmap="viridis", vmin=vmin, vmax=vmax,
                s=34, edgecolor="k", lw=0.3, transform=proj, zorder=5,
            )
        ax.set_extent(ext, crs=proj)
        ax.set_title(
            f"{label}\n{int(inside.sum())} of {len(x)} support points inside "
            f"the domain → {n_forced:,} forced cells",
            fontsize=10,
        )
        if n_forced:
            ax.legend(loc="upper right", fontsize=7.5, markerscale=4, framealpha=0.9)
        if (~inside).any():
            off = "\n".join(
                f"{v:+.2f} m @ {'N' if yy > (miny + maxy) / 2 else 'S'}"
                for yy, v in zip(y[~inside], pk[~inside])
            )
            ax.text(
                0.02, 0.02, f"off-frame anchors\n{off}", transform=ax.transAxes,
                fontsize=7.5, va="bottom", ha="left",
                bbox=dict(fc="white", alpha=0.85, ec="0.6", lw=0.5), zorder=6,
            )

    for ax in axes.ravel()[n:]:
        ax.axis("off")
    if sc is not None:
        fig.colorbar(sc, ax=axes, shrink=0.7).set_label(
            "peak water level on the boundary [m NAVD88]"
        )
    fig.suptitle(
        f"Water-level boundary as staged — support points inside {dom.name}", fontsize=11
    )
    return fig, axes


# ── gauges ───────────────────────────────────────────────────────────────────


def plot_gauge_verification(runs, root=None, data_dir=DATA, ncol=2):
    """Observed vs modelled water level at every scoreable gauge on the ACTIVE domain.

    One panel per ``Domain.obs_gauges`` entry that has an observation source, driven off
    the registry rather than a hand-written table — so a domain move re-targets it for free
    and cannot leave a figure of a gauge the model never placed.

    HOW TO READ A PANEL, which depends on the gauge and is marked on it:

    * ``survives_crest=True`` — the trace runs through the peak. Compare the CREST.
    * ``record_ends`` set — the gauge DIED mid-storm. Everything right of the dashed line
      is model-only; the top of the observed trace is a FLOOR, not the crest, and
      differencing a full model peak against it understates the model by whatever the gauge
      missed.
    * ``kind="tide"`` — read the PRE-STORM TIDE, left of the line. This is the right
      instrument for a conveyance defect: a drained estuary falls monotonically from a flat
      start instead of oscillating, and a basin cut off from the ocean has no tide at all.
      Neither shows up in a peak.

    ⚠️ A gauge whose ``series_source`` is ``"map"`` is drawn from wet channel cells, not the
    SFINCS observation point, because that point snapped to a dry bank. It is hourly, so
    its crest is aliased slightly low.
    """
    import matplotlib.pyplot as plt

    from .validate import gauge_series_frame

    dom = _domain.active()
    root = Path(root) if root else exp_root()
    runs = _runs_dict(runs, root)
    gauges = [g for g in dom.obs_gauges if g.obs_file and g.obs_station is not None]
    if not gauges:
        raise SystemExit(f"domain {dom.name!r} declares no scoreable gauges")

    n = len(gauges)
    ncol = min(ncol, n)
    nrow = int(np.ceil(n / ncol))
    fig, axes = plt.subplots(
        nrow, ncol, figsize=(7.2 * ncol, 3.4 * nrow), squeeze=False,
        constrained_layout=True,
    )

    for ax, g in zip(axes.ravel(), gauges):
        drew_obs = False
        for label, name in runs.items():
            rd = root / name
            if not (rd / "sfincs_map.nc").exists():
                continue
            try:
                df = gauge_series_frame(rd, g.name, data_dir=data_dir)
            except Exception as e:  # noqa: BLE001 — one bad gauge must not kill the figure
                ax.text(0.5, 0.5, f"{g.name}\n{e}", transform=ax.transAxes,
                        ha="center", va="center", fontsize=8, color="0.4")
                break
            if df.empty:
                continue
            if not drew_obs:
                ax.plot(df.index, df["obs"], color="k", lw=1.6, label="observed", zorder=5)
                drew_obs = True
            ax.plot(df.index, df["mod"], lw=1.2, label=label)
        if g.record_ends:
            import pandas as pd

            ax.axvline(
                pd.Timestamp(g.record_ends), color="0.5", ls="--", lw=1.0, zorder=1
            )
            ax.text(
                pd.Timestamp(g.record_ends), ax.get_ylim()[1], " gauge died ",
                fontsize=7, va="top", ha="left", color="0.4",
            )
        crest = "crest OK" if g.survives_crest else "no crest"
        ax.set_title(
            f"{g.name}  ({g.kind}, {g.series_source}, {crest})", fontsize=9
        )
        ax.set_ylabel("water level [m NAVD88]")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=7, loc="upper left")
        for lbl in ax.get_xticklabels():
            lbl.set_rotation(20)
            lbl.set_horizontalalignment("right")

    for ax in axes.ravel()[n:]:
        ax.axis("off")
    fig.suptitle(f"Gauge verification — {dom.name}", fontsize=12)
    return fig, axes


def plot_experiment_comparison(metrics_df, floodmap_dir):
    """Side-by-side max-depth flood maps for every experiment (small multiples).

    ``metrics_df`` indexed by experiment name; ``floodmap_dir`` holds
    ``<name>_hmax_lev3.tif`` copied out by the runner.
    """
    import matplotlib.pyplot as plt

    floodmap_dir = Path(floodmap_dir)
    names = list(metrics_df.index)
    n = len(names)
    ncol = min(3, n)
    nrow = int(np.ceil(n / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(5.2 * ncol, 4.6 * nrow), squeeze=False)
    for ax in axes.ravel():
        ax.axis("off")
    for k, name in enumerate(names):
        ax = axes.ravel()[k]
        tif = floodmap_dir / f"{name}_hmax_lev3.tif"
        if tif.exists():
            da = rioxarray.open_rasterio(tif, masked=True).squeeze(drop=True)
            da.where(da > 0.05).plot.imshow(
                ax=ax, vmin=0, vmax=5, cmap="viridis", add_colorbar=False
            )
        row = metrics_df.loc[name]
        csi = row.get("motf_csi", float("nan"))
        bias = row.get("hwm_bias_scored_m", float("nan"))
        # A waves-off arm's CSI is now KEPT and flagged rather than dropped, so label it
        # instead of hiding it — the row's extent_admissible carries the caveat.
        adm = row.get("extent_admissible", True)
        csi_s = (
            "CSI n/a" if csi != csi
            else f"CSI={csi:.2f}" + ("" if adm else " (waves off)")
        )
        ax.set_title(f"{name}\n{csi_s}  HWM bias={bias:+.2f} m", fontsize=9)
        ax.set_aspect("equal")
    fig.suptitle("Experiment comparison — max flood depth [m]", y=1.02)
    fig.tight_layout()
    return fig, axes
