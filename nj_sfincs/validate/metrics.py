"""The metrics. Registry-driven: what gets scored comes from ``domain.Domain``.

WHY REGISTRY-DRIVEN. The previous version had one function per named place —
``shrewsbury_gauge_peak``, ``sandy_hook_bay_hm0``, an ``INTERIOR_GAUGES`` dict of Barnegat
Bay stations, a ``gauges`` dict inside ``tidal_range_metric``. Every one of them had to be
found and edited to move the model, and any that was missed silently scored nothing (one
of them did exactly that for weeks: the station id was ``None``, so the point was written
into ``sfincs.obs``, appeared on every figure, and was compared against nothing at all).

Now a gauge is an entry in ``Domain.obs_gauges`` and the metric functions loop over it.

🔴 TWO RULES FOR ANY NUMBER OUT OF THIS MODULE
----------------------------------------------
**Never quote an HWM bias without its estimator and radius.** The estimator alone flips the
sign of the bias, and therefore the ranking of every arm. Every row carries
``hwm_estimator`` and ``hwm_radius_m`` so a CSV always says which measurement it is.

**Waves off ⇒ CSI / POD / FAR / n_dry are INADMISSIBLE.** Waves contribute ~+0.34 m of
setup on the open coast and wetting is threshold-nonlinear, so an extent metric computed
with SnapWave off is not a weaker version of the same number, it is a different one. Score
levels and phase on a waves-off arm and nothing else.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import xarray as xr

from .. import domain as _domain
from ..config import DATA
from .core import (
    DEPTH_MIN,
    aligned_pair,
    his_bed,
    his_series,
    peak_after_floor,
    prestorm_window,
    tidal_signal,
    uniform_series,
    wet_channel_cells,
    xcorr_lag_minutes,
    zs_at_faces,
)


def _obs_series(g, data_dir: Path = DATA):
    """(times, values) for a gauge's OBSERVED record, or None."""
    if not g.obs_file or g.obs_station is None:
        return None
    p = Path(data_dir) / g.obs_file
    if not p.is_file():
        return None
    ds = xr.open_dataset(str(p))
    var = g.obs_var or "waterlevel"
    if var not in ds:
        return None
    stations = set(np.asarray(ds["stations"].values).tolist())
    if g.obs_station not in stations:
        return None
    o = ds[var].sel(stations=g.obs_station)
    return o["time"].values, np.asarray(o.values, float).ravel()


def _model_series(mod, model_dir: Path, g, dom):
    """(times, values) for a gauge's MODELLED series, per ``ObsGauge.series_source``."""
    if g.series_source == "his":
        # `mod` is optional here, so open the run when the caller only had a path.
        from .core import open_run

        return his_series(mod if mod is not None else open_run(model_dir), g.name)
    cells = wet_channel_cells(model_dir, g.lon, g.lat, dom.epsg)
    if cells is None:
        return None
    idx, _, _ = cells
    zsw = zs_at_faces(model_dir, idx)
    full = np.isfinite(zsw).all(axis=0)
    if not full.any():
        return None
    from .core import map_times as _mt

    return _mt(model_dir), np.median(zsw[:, full], axis=1)


# ── peaks ────────────────────────────────────────────────────────────────────


def gauge_peak_metrics(mod, model_dir: Path, data_dir: Path = DATA) -> dict:
    """Modelled vs observed peak level and timing at every scoreable gauge.

    Replaces the per-place ``gauge_peak_error`` / ``shrewsbury_gauge_peak`` /
    ``interior_gauge_metrics`` peak block.

    ⚠️ A GAUGE THAT DIED GETS A PRE-FAILURE COMPARISON. ``ObsGauge.record_ends`` truncates
    BOTH sides to the gauge's last good instant. Comparing a full model peak against a
    truncated observed one understates the model by exactly whatever the gauge missed, and
    then reads as a model error. The model's true full-window peak is reported separately
    (``*_mod_peak_full_m``) and must never be differenced against the truncated observation.

    ⚠️ NEVER RANK A TIMING-SHIFTED ARM ON A PRE-FAILURE PEAK. An arm that crests earlier
    lands more of its crest before the gauge died, so it scores better on this number while
    having the LOWEST true peak of the set. That has happened, and it made the worst arm in
    a campaign look like the best on one column.

    Peaks come from the his point even where the tide does not: at the crest the water
    surface is locally continuous, so a bank cell and the channel beside it share a ``zs``,
    and his is 10-min where the map would alias.
    """
    dom = _domain.active()
    out: dict = {}
    for g in dom.obs_gauges:
        obs = _obs_series(g, data_dir)
        if obs is None:
            continue
        ot, ov = obs
        mser = his_series(mod, g.name)
        if mser is None:
            continue
        mt, mv = mser[0], np.asarray(mser[1], float).ravel()

        n = g.name
        out[f"peak_zb_{n}_m"] = his_bed(mod, g.name)

        # ⚠️ NOTHING HERE IS ROUNDED, deliberately. Rounding inside a metric is a silent
        # lossy step that makes a CSV non-reproducible — the port gate caught exactly that
        # (a `round(..., 6)` here differed from the archive at 1e-7 and read as a port
        # bug). Round for display, in the report, not in the emitter.
        o_peak, o_time = peak_after_floor(ot, ov)
        m_full, m_full_t = peak_after_floor(mt, mv)
        out[f"peak_obs_{n}_m"] = o_peak
        out[f"peak_obs_time_{n}"] = str(o_time)[:16] if o_time is not None else ""
        out[f"peak_mod_full_{n}_m"] = m_full
        out[f"peak_mod_full_time_{n}"] = str(m_full_t)[:16] if m_full_t is not None else ""

        if g.record_ends:
            end = np.datetime64(pd.Timestamp(g.record_ends))
            o_cmp = float(np.nanmax(ov[np.isfinite(ov) & (ot <= end)])) if ov.size else np.nan
            m_cmp = float(np.nanmax(mv[np.isfinite(mv) & (mt <= end)])) if mv.size else np.nan
            out[f"peak_mod_prefail_{n}_m"] = m_cmp
            out[f"peak_err_prefail_{n}_m"] = m_cmp - o_cmp
            out[f"peak_record_ends_{n}"] = g.record_ends
        else:
            out[f"peak_err_{n}_m"] = m_full - o_peak
            if m_full_t is not None and o_time is not None:
                out[f"peak_lag_{n}_min"] = float(
                    (m_full_t - o_time) / np.timedelta64(1, "m")
                )
    return out


# ── pre-storm tide: range and phase ──────────────────────────────────────────


def tide_metrics(mod, model_dir: Path, data_dir: Path = DATA, hours: float = 24.0) -> dict:
    """Pre-storm tidal RANGE and PHASE LAG per gauge (minutes, + = model LATE).

    Both are measured over the same clean window (see ``core.prestorm_window``), on the
    DETRENDED series, and a range is refused outright for a series that never turns
    around — that is a drain, or a dead basin, not a tide. ``*_is_tidal`` says so
    explicitly rather than leaving a fabricated number to be read as one.

    The modelled series comes from ``ObsGauge.series_source``: his where the obs point is
    wet, the map at wet channel cells where it snapped to a bank.
    """
    dom = _domain.active()
    from .core import map_times as _mt

    mt_all = _mt(model_dir)
    t0, t1 = prestorm_window(mt_all, hours)
    out: dict = {}

    for g in dom.obs_gauges:
        obs = _obs_series(g, data_dir)
        if obs is None:
            continue
        ot, ov = obs
        n = g.name

        ow = ov[(ot >= t0) & (ot <= t1)]
        ow = ow[np.isfinite(ow)]
        obs_range = float(ow.max() - ow.min()) if ow.size else float("nan")
        out[f"tide_obs_range_{n}_m"] = round(obs_range, 3)

        mser = _model_series(mod, model_dir, g, dom)
        mod_range, drift, frac, is_tidal, lag = (
            float("nan"),
            float("nan"),
            float("nan"),
            False,
            float("nan"),
        )
        if mser is not None:
            mt, mv = mser
            sel = (mt >= t0) & (mt <= t1)
            series = np.asarray(mv, float).ravel()[sel]
            if series.size >= 4:
                sig = tidal_signal(series)
                drift, frac, is_tidal = sig["drift_m"], sig["frac_rising"], sig["is_tidal"]
                mod_range = sig["range_m"] if is_tidal else float("nan")
                if is_tidal:
                    # dt matched to the source's own cadence: his is 10-min, the map hourly.
                    dt_s = 600.0 if g.series_source == "his" else 3600.0
                    m = uniform_series(mt[sel], series, t0, t1, dt_s)
                    o = uniform_series(ot, ov, t0, t1, dt_s)
                    if m is not None and o is not None:
                        lag = xcorr_lag_minutes(m, o, dt_s)

        out[f"tide_mod_range_{n}_m"] = round(mod_range, 3)
        out[f"tide_mod_drift_{n}_m"] = round(drift, 3)
        out[f"tide_mod_frac_rising_{n}"] = round(frac, 3)
        out[f"tide_mod_is_tidal_{n}"] = is_tidal
        out[f"tide_range_damping_{n}_m"] = round(obs_range - mod_range, 3)
        out[f"phase_lag_{n}_min"] = round(lag, 1)
    return out


# ── paired interior gauges: volume vs tilt ───────────────────────────────────


def gauge_series_frame(
    model_dir: Path, gauge_name: str, mod=None, data_dir: Path = DATA
) -> pd.DataFrame:
    """Observed + modelled level and error at one gauge, on ONE clock.

    Indexed by the MODEL clock with columns ``obs``, ``mod``, ``err`` (= mod − obs).
    Observations are interpolated onto that clock and are NaN outside their own coverage —
    never extrapolated.
    """
    dom = _domain.active()
    g = next((x for x in dom.obs_gauges if x.name == gauge_name), None)
    if g is None:
        raise KeyError(
            f"unknown gauge {gauge_name!r} on domain {dom.name!r}; known: "
            f"{[x.name for x in dom.obs_gauges]}"
        )
    mser = _model_series(mod, Path(model_dir), g, dom)
    if mser is None:
        return pd.DataFrame(columns=["obs", "mod", "err"])
    mt, mv = mser[0], np.asarray(mser[1], float).ravel()

    obs = np.full(mt.shape, np.nan)
    o = _obs_series(g, data_dir)
    if o is not None:
        ot, ov = o
        ok = np.isfinite(ov)
        if ok.sum() >= 2:
            t0 = ot[ok][0]
            xs = (ot[ok] - t0) / np.timedelta64(1, "s")
            xt = (mt - t0) / np.timedelta64(1, "s")
            obs = np.interp(xt, xs, ov[ok], left=np.nan, right=np.nan)

    df = pd.DataFrame({"obs": obs, "mod": mv}, index=pd.to_datetime(mt))
    df["err"] = df["mod"] - df["obs"]
    return df


def basin_error_decomposition(
    model_dir: Path, north: str, south: str, window, mod=None, data_dir: Path = DATA
) -> dict:
    """Split a basin's error into a VOLUME term and a TILT term.

        volume = mean(err_north, err_south)   -> exchange / connection / boundary
        tilt   = err_north - err_south        -> wind stress / friction / conveyance

    ⚠️ WHY THIS EXISTS, AND THE MISTAKE IT REPLACES. The obvious statistic — the along-basin
    gradient as peak-minus-peak — compares the two gauges AT DIFFERENT INSTANTS. On a basin
    whose ends peak ~6 h apart it therefore reported an INVERTED gradient and sent a whole
    day's diagnosis after a "conveyance defect" that does not exist. At MATCHED instants the
    model reproduced the gradient's sign, its sign-flip time, and ~61% of its magnitude; the
    real defect was a cumulative VOLUME deficit. ``alongbasin_matched_m`` here is the
    matched-instant quantity and must NEVER be reported under the same name as a
    peak-to-peak one.

    THIS COSTS NO SOLVER TIME and is the intended gate on the expensive arms:
      * a TILT-dominated error whose sign flip tracks a wind reversal points at the WIND
        forcing;
      * a VOLUME-dominated error with no wind-reversal signature points at a missing water
        source — a connection walled off by the domain edge.
    """
    a = gauge_series_frame(model_dir, north, mod, data_dir)
    b = gauge_series_frame(model_dir, south, mod, data_dir)
    if a.empty or b.empty:
        return {}

    t0, t1 = np.datetime64(window[0]), np.datetime64(window[1])
    j = a.join(b, lsuffix="_n", rsuffix="_s").loc[str(t0) : str(t1)]
    j = j[np.isfinite(j[["obs_n", "obs_s", "mod_n", "mod_s"]]).all(axis=1)]
    if len(j) < 3:
        return {}

    err_n, err_s = j["err_n"].to_numpy(), j["err_s"].to_numpy()
    volume = 0.5 * (err_n + err_s)
    tilt = err_n - err_s
    obs_tilt = (j["obs_n"] - j["obs_s"]).to_numpy()
    mod_tilt = (j["mod_n"] - j["mod_s"]).to_numpy()
    times = j.index.to_numpy()

    def _cross(v):
        """First time the series changes sign (or "") — the discriminator."""
        s = np.sign(v)
        k = np.where(np.diff(s) != 0)[0]
        return str(times[k[0] + 1])[:16] if k.size else ""

    i = int(np.argmax(obs_tilt))  # evaluate where the OBSERVED tilt is largest
    return {
        "basin_n_gauge": north,
        "basin_s_gauge": south,
        "basin_n": len(j),
        "basin_window": f"{str(t0)[:16]}..{str(t1)[:16]}",
        "basin_volume_err_mean_m": round(float(volume.mean()), 3),
        "basin_volume_err_final_m": round(float(volume[-1]), 3),
        "basin_volume_err_absmax_m": round(float(volume[np.argmax(np.abs(volume))]), 3),
        "basin_tilt_err_mean_m": round(float(tilt.mean()), 3),
        "basin_tilt_err_final_m": round(float(tilt[-1]), 3),
        "basin_tilt_err_absmax_m": round(float(tilt[np.argmax(np.abs(tilt))]), 3),
        "basin_dominant_term": (
            "tilt" if np.abs(tilt).mean() > np.abs(volume).mean() else "volume"
        ),
        "basin_tilt_over_volume": round(
            float(np.abs(tilt).mean() / max(np.abs(volume).mean(), 1e-9)), 2
        ),
        "alongbasin_obs_max_m": round(float(obs_tilt[i]), 3),
        "alongbasin_matched_m": round(float(mod_tilt[i]), 3),
        "alongbasin_matched_ratio": (
            round(float(mod_tilt[i] / obs_tilt[i]), 3)
            if abs(obs_tilt[i]) > 1e-9
            else float("nan")
        ),
        "alongbasin_at": str(times[i])[:16],
        "alongbasin_obs_flip": _cross(obs_tilt),
        "alongbasin_mod_flip": _cross(mod_tilt),
        "basin_err_n_flip": _cross(err_n),
    }


# ── high-water marks ─────────────────────────────────────────────────────────

#: How a mark's modelled water level is reduced from the cells in its search window.
#: This is a load-bearing PHYSICAL choice, not a formatting one — see ``hwm_metrics``.
HWM_ESTIMATORS = ("median", "max", "nearest")
HWM_ESTIMATOR_DEFAULT = "median"
HWM_RADIUS_M = 50.0



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

    from .. import domain as _domain  # noqa: PLC0415

    rel = _domain.active().hwm_geojson
    return Path(data_dir) / rel.parent.name / rel.name


def _clip_to_region(hwm):
    """Drop marks outside the ACTIVE domain's region polygon.

    🔴 WITHOUT THIS, A MARK THE MODEL NEVER SIMULATED SCORES AS "DRY", NOT AS ABSENT.
    The dry-mark path is deliberately generous: a mark the model leaves dry is scored
    against ``nanmin`` of the nearby BED rather than dropped, so "the model says water
    never got above this ground" still counts against it. That is right for a mark inside
    the domain and catastrophic for one outside it, because ``da_dep`` is the downscaled
    subgrid DEM — it carries valid bed values across the whole grid RECTANGLE, including
    every cell the region clip made inactive. So an out-of-domain mark finds finite ground,
    never finds water, and books a residual of (bare earth − observed flood elevation).

    Measured on ``v1_5_raritan`` when this was found (2026-08-17): 7 of 53 scored marks sat
    outside the region, ALL 7 dry, ALL 7 of the domain's dry marks. They carried bias
    −2.788 m / RMSE 3.165 m and dragged the headline from 0.402 m to 1.210 m — a number
    that was three quarters an artefact of scoring Staten Island against a model that
    never included it.

    ⚠️ This is the SAME confusion as ``_fill_inactive_holes`` (STATUS, 2026-08-14): once a
    region clip has run, "outside the domain" and "inside the domain" are indistinguishable
    to anything reading only a raster. Every piece of code that reasons about cells beyond
    the mask has to be told which is which.

    ⭐ Safe for the port fixture BY MEASUREMENT, not by argument: ``v1_monmouth`` has 0
    scored marks outside its region and 0 dry marks, so ``hwm_n_scored`` stays 38 and
    ``scripts/verify_port.py`` still passes bit-for-bit. ``tests/test_hwm_region_clip.py``
    pins both that and the v1.5 drop.
    """
    import geopandas as _gpd  # noqa: PLC0415

    from .. import domain as _domain  # noqa: PLC0415

    region = _domain.active().region
    if region is None:
        return hwm
    reg = _gpd.read_file(str(region)).to_crs(hwm.crs)
    geom = reg.union_all() if hasattr(reg, "union_all") else reg.unary_union
    keep = hwm.geometry.within(geom).values
    if not keep.all():
        print(
            f"[hwm] region clip: {len(hwm) - int(keep.sum())} of {len(hwm)} marks are "
            "outside the domain region and are NOT scored (they would otherwise score "
            "as dry against bare earth)"
        )
    return hwm[keep].reset_index(drop=True)


def hwm_metrics(
    da_hmax,
    da_dep,
    data_dir: Path = DATA,
    hwm_ids: "set | list | None" = None,
    estimator: str = HWM_ESTIMATOR_DEFAULT,
    radius_m: float = HWM_RADIUS_M,
) -> dict:
    """USGS High Water Mark residuals: RMSE / bias / within-0.5 m (headline q<=2).

    Two families of keys are returned, and the difference between them matters:

    ``*_scored`` (USE THESE)
        Every q<=2 mark is scored. A mark the model leaves DRY is not dropped — it is
        scored against the model's GROUND elevation there, i.e. "the model says the water
        never got above this bed". That is the most generous reading available (an upper
        bound on the model's skill at that mark), and it is still a large negative residual
        whenever the observations say metres of water stood there.

    ``hwm_bias_m`` / ``hwm_rmse_m`` (LEGACY, wet-only)
        The historical definition: ``wet & (qual <= 2)``. Kept so old numbers stay
        comparable — NOT to be led with.

    WHY. The wet-only metric **structurally rewards failing to flood**: the worse the model
    under-floods, the more marks fall out of the average, and the better the remaining
    average looks. It hid a real defect for months — an inlet was dammed shut in the DEM,
    so marks sat in water the model never wetted, silently vanished, and their basin
    reported a near-perfect −0.055 m bias while the river behind it was bone dry.

    This is the mirror image of the FEMA-MOTF POD flaw (which rewards OVER-flooding). Never
    lead with either alone. Always read ``hwm_n_dry`` alongside any bias, and treat a
    CHANGE in the scored-mark count between two runs as invalidating the comparison.

    ``hwm_ids`` — THE BRIDGE RESCORE. Restrict scoring to these ``hwm_id`` values. A number
    computed over a different mark set is not the same measurement, however similar the
    model; going from one domain's marks to another's is that, at the largest scale it
    happens. A partial bridge is refused outright — it would be a third mark set,
    comparable to neither side.

    ``estimator`` — HOW THE WINDOW IS REDUCED. 🔴 THIS DECIDES THE SIGN OF THE BIAS.
        A mark is scored against the cells within ``radius_m``, because the mark's
        COORDINATE is uncertain: 94 of 95 Sandy marks (and all 64 q<=2 ones) were located
        by *"Map (digital or paper)"*, the lowest-accuracy horizontal method USGS STN
        records. (``quality`` is the VERTICAL accuracy, ±0.05 ft at q=1; it says nothing
        about where the mark is.) So a window is justified.

        What is NOT justified is reducing that window with ``max``, which was the default
        until it was measured. A maximum is one-sided: adding candidates can only push it
        up, so it is **unbounded in the radius** and has no converged value. On 19 q<=2
        marks::

            radius   0 m   12.5    25     50     75    100    150
            max    -0.134 +0.007 +0.09  +0.318 +0.51 +0.69  +1.09
            median -0.134 -0.147 -0.147 -0.214 -0.21 -0.21  -0.20

        50 m was simply where the loop stopped, and the argmax sat on the window's OUTER
        RING for essentially every mark — it was finding a ditch 50 m away, not the wall
        the mud line is on. Worse, ``max`` makes worse positional accuracy produce a
        WETTER-looking model, which is backwards.

        Given "the mark is somewhere in this box", the defensible reduction is a CENTRAL
        statistic: ``median``. It is radius-stable (≤0.07 m of swing vs ``max``'s 1.10 m)
        and it makes the mark types cohere physically — mud lines −0.19, seed −0.20, debris
        −0.46, the last carrying the wave runup a stillwater ``zsmax`` cannot reproduce.
        Under ``max`` even mud lines, the cleanest stillwater indicator, read +0.59 m.

        ``nearest`` is offered for diagnosis but is NOT defensible: it trusts the coordinate
        to one 6.25 m cell, which the survey method says you cannot do.

        ⚠️ Every level arm removes water, so the SIGN of the bias decides the ranking
        outright. Under ``max`` one reference arm is +0.32 (too wet) and arms that remove
        water win; under ``median`` it is −0.21 (slightly dry) and the same arms lose. The
        ranking inverts exactly. The emitted ``hwm_estimator`` / ``hwm_radius_m`` keys exist
        so a CSV always says which.
    """
    if estimator not in HWM_ESTIMATORS:
        raise ValueError(
            f"unknown HWM estimator {estimator!r}; expected one of {HWM_ESTIMATORS}. "
            "This is not a cosmetic argument — it decides the SIGN of the bias."
        )
    GROUND_CAP = 0.5
    hwm = gpd.read_file(str(_hwm_path(data_dir))).to_crs(da_dep.rio.crs)
    hwm = _clip_to_region(hwm)
    if hwm_ids is not None:
        want = {str(i) for i in hwm_ids}
        before = len(hwm)
        hwm = hwm[hwm["hwm_id"].astype(str).isin(want)].reset_index(drop=True)
        missing = want - set(hwm["hwm_id"].astype(str))
        if missing:
            raise ValueError(
                f"bridge rescore asked for {len(want)} hwm_ids but "
                f"{len(missing)} are absent from this domain's mark file: "
                f"{sorted(missing)[:10]}. A partial bridge is not a bridge — it is a "
                "third mark set, comparable to neither side."
            )
        print(f"[hwm] BRIDGE RESCORE: restricted {before} -> {len(hwm)} marks")

    depth, dep_arr, wse = da_hmax.values, da_dep.values, (da_dep + da_hmax).values
    if depth.ndim == 3:
        depth, wse, dep_arr = depth[0], wse[0], dep_arr[0]
    T = da_dep.rio.transform()
    ny, nx = wse.shape
    rad = int(round(radius_m / abs(T.a)))

    obs = hwm["elev_m"].values
    qual = hwm["quality"].values.astype(float)
    mod_wse = np.full(len(obs), np.nan)  # wet-only (NaN where the model is dry)
    mod_ground = np.full(len(obs), np.nan)  # lowest ground in the window -> dry-mark score
    for k, (X, Y) in enumerate(zip(hwm.geometry.x.values, hwm.geometry.y.values)):
        col, row = int((X - T.c) / T.a), int((Y - T.f) / T.e)
        if 0 <= row < ny and 0 <= col < nx:
            r0, c0 = max(0, row - rad), max(0, col - rad)
            sl = (slice(r0, row + rad + 1), slice(c0, col + rad + 1))
            ws, hh, dd = wse[sl], depth[sl], dep_arr[sl]
            if np.isfinite(dd).any():
                mod_ground[k] = np.nanmin(dd)  # most generous: the lowest bed nearby
            flooded = (hh >= DEPTH_MIN) & (dd <= obs[k] + GROUND_CAP)
            if flooded.any():
                vals = ws[flooded]
                if estimator == "median":
                    mod_wse[k] = np.nanmedian(vals)
                elif estimator == "max":
                    mod_wse[k] = np.nanmax(vals)
                else:  # "nearest" — the wet cell closest to the mark's own pixel
                    rr, cc = np.nonzero(flooded)
                    j = int(np.argmin((rr - (row - r0)) ** 2 + (cc - (col - c0)) ** 2))
                    mod_wse[k] = ws[rr[j], cc[j]]

    wet = np.isfinite(mod_wse)
    resid = mod_wse - obs
    head = wet & (qual <= 2)
    r = resid[head]

    # --- the honest metric: dry marks scored at ground level, never dropped ----
    mod_scored = np.where(wet, mod_wse, mod_ground)
    resid_s = mod_scored - obs
    head_s = np.isfinite(mod_scored) & (qual <= 2)  # only truly off-grid marks drop out
    rs = resid_s[head_s]

    result = {
        # WHICH measurement this row is. Never compare a bias across differing values of
        # these two — the estimator alone flips the sign.
        "hwm_estimator": estimator,
        "hwm_radius_m": float(radius_m),
        # headline (scored): every q<=2 mark on the grid counts
        "hwm_n_scored": int(head_s.sum()),
        "hwm_n_dry_scored": int((head_s & ~wet).sum()),
        "hwm_rmse_scored_m": float(np.sqrt((rs**2).mean())) if head_s.any() else float("nan"),
        "hwm_bias_scored_m": float(rs.mean()) if head_s.any() else float("nan"),
        "hwm_within0.5_scored": (
            float(np.mean(np.abs(rs) < 0.5)) if head_s.any() else float("nan")
        ),
        # legacy (wet-only) — kept for continuity with existing reports
        "hwm_n_wet": int(wet.sum()),
        "hwm_n_dry": int((~wet).sum()),
        "hwm_rmse_m": float(np.sqrt((r**2).mean())) if head.any() else float("nan"),
        "hwm_bias_m": float(r.mean()) if head.any() else float("nan"),
        "hwm_within0.5": float(np.mean(np.abs(r) < 0.5)) if head.any() else float("nan"),
    }

    # Per-basin residuals. A pooled bias near zero hides that the ocean-front basin
    # validates while a behind-barrier basin under-fills; this partition is the real
    # conveyance verdict. ⚠️ Depends on first-match-wins over Domain.hwm_rules IN ORDER.
    basin = _domain.classify_hwm_basin(hwm.geometry.x.values, hwm.geometry.y.values)
    for b in _domain.hwm_basin_names():
        m = head & (basin == b)
        rb = resid[m]
        result[f"hwm_n_{b}"] = int(m.sum())
        result[f"hwm_bias_{b}_m"] = float(rb.mean()) if m.any() else float("nan")
        result[f"hwm_rmse_{b}_m"] = (
            float(np.sqrt((rb**2).mean())) if m.any() else float("nan")
        )

        ms = head_s & (basin == b)
        rbs = resid_s[ms]
        result[f"hwm_n_scored_{b}"] = int(ms.sum())
        result[f"hwm_n_dry_{b}"] = int((ms & ~wet).sum())
        result[f"hwm_bias_scored_{b}_m"] = float(rbs.mean()) if ms.any() else float("nan")
        result[f"hwm_rmse_scored_{b}_m"] = (
            float(np.sqrt((rbs**2).mean())) if ms.any() else float("nan")
        )
    n_unassigned = int((basin == "unassigned").sum())
    if n_unassigned:
        result["hwm_n_unassigned"] = n_unassigned
    return result


def motf_metrics(da_hmax, da_dep, data_dir: Path = DATA) -> dict:
    """FEMA MOTF extent: CSI / POD / FAR from hits / miss / false-alarm pixels.

    🔴 INADMISSIBLE ON A WAVES-OFF ARM. Wetting is threshold-nonlinear and waves are worth
    ~+0.34 m of setup on the open coast, so these are a different measurement with SnapWave
    off, not a weaker one.

    ⚠️ POD rewards OVER-flooding, exactly as the wet-only HWM metric rewards under-flooding.
    Read CSI, and read it beside the HWM residuals rather than instead of them.
    """
    with rasterio.open(str(Path(data_dir) / "validation" / "sandy_motf_extent.tif")) as r:
        motf, mtf, m_nd = r.read(1), r.transform, r.nodata
    mod_t = da_dep.rio.transform()
    mh, mw = motf.shape

    Xc = mtf.c + (np.arange(mw) + 0.5) * mtf.a
    Yc = mtf.f + (np.arange(mh) + 0.5) * mtf.e
    mc = np.clip(((Xc - mod_t.c) / mod_t.a).astype(int), 0, da_dep.shape[-1] - 1)
    mr = np.clip(((Yc - mod_t.f) / mod_t.e).astype(int), 0, da_dep.shape[-2] - 1)
    rr, cc = np.meshgrid(mr, mc, indexing="ij")

    def _2d(a):
        return a[0] if a.ndim == 3 else a

    dep_at, h_at = _2d(da_dep.values)[rr, cc], _2d(da_hmax.values)[rr, cc]

    motf_wet = motf == 1
    mod_wet = (h_at >= DEPTH_MIN) & np.isfinite(h_at)
    land_in = (motf != m_nd) & (dep_at > 0.0)
    nh = int((motf_wet & mod_wet & land_in).sum())
    nm = int((motf_wet & ~mod_wet & land_in).sum())
    nf = int((~motf_wet & mod_wet & land_in).sum())
    return {
        "motf_csi": nh / (nh + nm + nf) if (nh + nm + nf) else float("nan"),
        "motf_pod": nh / (nh + nm) if (nh + nm) else float("nan"),
        "motf_far": nf / (nh + nf) if (nh + nf) else float("nan"),
    }


# ── forcing-product diagnostics (no run needed) ──────────────────────────────


def source_phase_lag(
    geodataset: str,
    ref_lonlat: tuple[float, float],
    ref_obs: tuple[str, int],
    data_dir: Path = DATA,
    hours: float = 24.0,
) -> float:
    """Phase lag (minutes, + = source later) of a FORCING SOURCE vs an observed tide.

    No SFINCS run needed — the cheap offshore-phase ranking that lets candidate boundary
    products be compared before deciding what to run. The source's station nearest
    ``ref_lonlat`` is compared against ``ref_obs`` = (file relative to data/, station id).

    ⚠️ THIS COMPARES A PRODUCT TO A GAUGE, NOT A MODEL TO A GAUGE. The flanking gauges used
    for it usually sit OUTSIDE the model domain, so it is never a model diagnostic. Report
    it alongside the incumbent interpolant and argue relative to that, rather than against
    invented thresholds.
    """
    import yaml

    cat = yaml.safe_load((Path(data_dir) / "data_catalog.yml").read_text()) or {}
    entry = cat.get(geodataset)
    if not entry or "uri" not in entry:
        return float("nan")
    uri = Path(data_dir) / entry["uri"]
    if not uri.exists():
        return float("nan")
    ds = xr.open_dataset(str(uri))
    if "waterlevel" not in ds:
        return float("nan")
    wl = ds["waterlevel"]
    if "stations" in wl.dims and "lon" in ds and "lat" in ds:
        d = np.hypot(ds["lon"].values - ref_lonlat[0], ds["lat"].values - ref_lonlat[1])
        wl = wl.isel(stations=int(np.argmin(d)))
    elif "stations" in wl.dims:
        wl = wl.isel(stations=0)

    obs_file, obs_station = ref_obs
    obs = xr.open_dataset(str(Path(data_dir) / obs_file))
    o = obs["waterlevel"].sel(stations=obs_station)

    t0 = np.datetime64(pd.Timestamp("2012-10-28"))
    t1 = t0 + np.timedelta64(int(hours * 3600), "s")
    dt_s = 600.0
    a = uniform_series(wl["time"].values, wl.values, t0, t1, dt_s)
    b = uniform_series(o["time"].values, o.values, t0, t1, dt_s)
    if a is None or b is None:
        return float("nan")
    return round(xcorr_lag_minutes(a, b, dt_s), 1)


# ── the row ──────────────────────────────────────────────────────────────────


def evaluate(
    model_dir: Path,
    data_dir: Path = DATA,
    gallery_tif: Path | None = None,
    hwm_ids: "set | list | None" = None,
    hwm_estimator: str = HWM_ESTIMATOR_DEFAULT,
) -> dict:
    """Full metric row for one run. Robust: a failing metric yields an ``*_error`` key
    rather than aborting the row.

    If ``gallery_tif`` is given, the *masked* (permanent water dropped, north-up)
    ``da_hmax`` is written there — so the figure shows flooding on land, not the full water
    column of the bay/ocean. The raw ``floodmap_hmax_lev3.tif`` in the run dir stays
    unmasked.
    """
    from .core import load_floodmap

    row: dict = {}
    mod, da_hmax, da_dep = load_floodmap(model_dir, data_dir=data_dir)

    if gallery_tif is not None:
        Path(gallery_tif).parent.mkdir(parents=True, exist_ok=True)
        da_hmax.rio.to_raster(gallery_tif)

    for fn, args in [
        (gauge_peak_metrics, (mod, model_dir, data_dir)),
        (tide_metrics, (mod, model_dir, data_dir)),
        (hwm_metrics, (da_hmax, da_dep, data_dir, hwm_ids, hwm_estimator)),
        (motf_metrics, (da_hmax, da_dep, data_dir)),
    ]:
        try:
            row.update(fn(*args))
        except Exception as e:  # noqa: BLE001 — keep the row, note the failure
            row[f"{fn.__name__}_error"] = str(e)
    return row
