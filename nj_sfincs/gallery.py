"""The run gallery: one standard figure set per finished arm, the same for every arm.

``build_arm_figures(domain_name, arm)`` writes ``experiments/<domain>/<arm>/gallery/``:
PNGs plus ``manifest.json`` (the run card, the figure list with captions, the arm's
``metrics.csv`` row and its flags). ``scripts/publish_gallery.py`` collects every
domain's galleries into the static site (``~/sandy_flood_site``). The sweep driver calls
this after an arm is validated (``run_experiments.py``; ``--no-gallery`` skips it), in a
SUBPROCESS per arm, so the rasters die with the process.

WHAT THIS MODULE IS NOT. It scores nothing. Every number on a figure comes from the
scorer's own code path or from the arm's ``metrics.csv`` row:

* HWM residuals are ``plots._sample_hwm`` — the sampler that defers to ``validate`` for
  the estimator, the radius and the wet threshold — and the figure self-checks its RMSE /
  bias against the row (``selfcheck`` in the manifest). Every HWM caption names the
  estimator and the radius (CLAUDE.md §6).
* The MOTF categories use the scorer's screen (``motf_exclude_mask``,
  ``simulated_mask``, ``DEPTH_MIN``, ``dep > 0``) and self-check CSI / POD / FAR against
  the row; the caption carries ``motf_km2_excluded_boxes`` (CLAUDE.md §6).
* Gauge series are ``validate.gauge_series_frame``; peak and timing errors are read off
  the row (``peak_err_*`` / ``peak_lag_*``), never recomputed.

FLAGS WARN, THEY NEVER HIDE (user rule: warn, never gate; flag, never delete). A resumed
waves-on run, a soil-state reset on a rain-on arm, an unseeded engine, a waves-off extent
score, an audit that is not ``output WHOLE`` — each is a badge on the run card, and every
figure is still drawn.

GEOGRAPHY lives in ``domain.py``: the whole-domain frame is ``Domain.plot_window`` and
the zooms are ``Domain.gallery_windows`` (names in ``Domain.map_windows``). Fixed colour
scales (module constants below) keep every arm's figure on one scale.

⚠️ MEMORY. The HWM and MOTF figures need the scorer's full-resolution,
de-rotated rasters. ``validate.load_floodmap`` would hold them whole (a v4 validate needs
~200 G for one arm), so ``Rasters`` reads them in SLABS instead: the gallery tif that
``validate.evaluate`` wrote (that very array) plus a per-slab nearest warp of the rotated
bed; the self-checks against the metrics row prove the slabs equal the whole. Measured
peak per arm: ``manifest.json`` → ``peak_rss_gb``. A stale floodmap is NOT re-downscaled
here (that would write into the run dir): those figures are skipped with a flag.
"""

from __future__ import annotations

import json
import os
import re
import resource
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

import numpy as np

from . import domain as _domain
from .config import DATA, ROOT, exp_root

GALLERY = "gallery"
MANIFEST = "manifest.json"
SCHEMA = 1
DPI = 150

#: The fixed figure order. ``publish_gallery.py`` and the compare page key on these.
FIGURES = (
    ("zsmax", "Peak water level (m NAVD88)"),
    ("flood_depth", "Flood depth on normally-dry land"),
    ("dzsmax", "Peak water level minus the reference arm"),
    ("hwm_map", "High-water marks: residual map"),
    ("hwm_summary", "High-water marks: measured vs modelled, by basin"),
    ("motf", "FEMA MOTF extent agreement"),
    ("gauges", "Gauges: measured vs modelled water level"),
    ("gauge_peaks", "Gauges: peak and timing errors"),
    ("hm0", "Peak significant wave height"),
)

# ── fixed scales (identical for every arm, so the PNGs compare by eye) ──────────────
ZSMAX_RANGE = (0.0, 4.5)  # m NAVD88 (Sandy bay peaks ~3.5–4 m stay off the dark end)
#: m; a face shows a peak water level when zsmax is this far above the face's MEAN ground
#: (subgrid ``z_zmax − z_volmax / area``). NOT ``zb``: on a subgrid model zb is the face's
#: LOWEST pixel, so a few cm of rain in a ditch passed every upland face, whose zsmax is
#: then just its ground — 20 m bluffs at Sandy Hook painted as 5 m water (2026-10-19).
WET_ABOVE_MEAN_M = 0.10
DEPTH_RANGE = (0.0, 3.0)  # m above the usual surface (ground / MHHW / lake pool)
DZS_LIM = 0.5  # m, Δ zsmax diverging half-range
RESID_LIM = (
    1.5  # m, HWM residual diverging half-range (= plots.plot_hwm_residual_panels)
)
HM0_RANGE = (0.0, 8.0)  # m

# ── colours: paper sheet, one-hue sequential, two-hue + grey diverging ──────────────
PAPER = "#f4f2ee"
INK = "#1f2124"
INK2 = "#5a5852"
HAIR = "#b3aea4"
LAND = "#dcd8cf"
WATER_BG = "#c4ccd3"
#: below / too low = orange, above / too high = purple — the showcase site's convention
#: (``--under`` / ``--over`` in ~/sandy_flood_site), grey at zero.
DIVERGING = ("#7a3a06", "#d9822b", "#a29e97", "#8f78c4", "#3b1f6e")
#: hit / miss (model dry, MOTF wet) / false alarm (model wet, MOTF dry). Hit = blue
#: (agreement, water), miss = orange (too dry = too low), false alarm = purple (too wet).
MOTF_COLORS = ("#2f6db3", "#e0892c", "#8a5ac4")

#: Panel box (inches) and columns: fixed, so every arm's PNG has the same pixel size.
PANEL_W, PANEL_H, NCOL = 3.6, 4.0, 4
#: Sample pixels along a panel's long side.
PANEL_PX = 640


# ═════════════════════════════════════════════════════════════════════════════════════
# small pure helpers (unit-tested)
# ═════════════════════════════════════════════════════════════════════════════════════


def parse_restart_history(text: str) -> dict:
    """``restart_history.txt`` → ``{resumes, soil_reset, finished, lines}``.

    A resume line reads ``resume from sfincs.<t>.rst: …``; ``restart.prepare`` adds a
    ``soil state RESET`` line when a curve-number run resumed with an empty soil
    (FINDINGS §59). ``finished`` = a ``finish:`` line was written (the stitch ran)."""
    lines = [ln.rstrip() for ln in (text or "").splitlines() if ln.strip()]
    resumes = [ln for ln in lines if re.search(r"\bresume from\b", ln)]
    return {
        "resumes": len(resumes),
        "resumed_from": [
            m.group(1)
            for ln in resumes
            if (m := re.search(r"resume from (sfincs\.\S+?\.rst)", ln))
        ],
        "soil_reset": any("soil state RESET" in ln for ln in lines),
        "finished": any(" finish:" in ln for ln in lines),
        "lines": lines,
    }


def _flag(code: str, level: str, text: str) -> dict:
    return {"code": code, "level": level, "text": text}


def compute_flags(f: dict) -> list[dict]:
    """The run card's warnings, from a facts dict. PURE: no I/O, so it is testable.

    ``level`` is ``serious`` / ``caution`` / ``info``. A flag is a badge beside the
    numbers; nothing here removes a figure or a number. Facts (missing = unknown):
    ``audit_whole`` (True / False / None), ``audit_problems``, ``sealed``, ``waves_on``,
    ``rain_on``, ``resumes``, ``soil_reset``, ``engine_seed``, ``engine``,
    ``snapwave_direction``, ``extent_admissible``, ``has_metrics_row``,
    ``hwm_n_scored``, ``ref_arm``, ``ref_hwm_n_scored``, ``floodmap_fresh``.
    """
    out: list[dict] = []
    whole = f.get("audit_whole")
    if whole is None:
        out.append(_flag("no_output", "serious", "No solver output — nothing to draw."))
    elif whole is False:
        probs = "; ".join(f.get("audit_problems") or []) or "see premier audit"
        out.append(
            _flag(
                "audit_not_whole",
                "serious",
                f"Audit is NOT 'output WHOLE' ({probs}). A run read mid-write looks like a "
                "plausible catastrophe (CLAUDE.md §5) — figures drawn, do not read them.",
            )
        )
    if f.get("sealed") is False:
        out.append(
            _flag(
                "not_sealed",
                "serious",
                "Not on this domain's sealed fingerprint — not comparable with the other "
                "arms (nj_sfincs/premier.py).",
            )
        )
    if f.get("snapwave_direction") == "wind":
        out.append(
            _flag(
                "snapwave_wind_direction",
                "serious",
                "SnapWave launched the boundary waves in the WIND direction (unpatched "
                "engine, FINDINGS §43).",
            )
        )
    n_res = int(f.get("resumes") or 0)
    if n_res and f.get("waves_on"):
        out.append(
            _flag(
                "resumed_waves_on",
                "caution",
                f"Resumed {n_res}x from a restart file with waves ON: the restart holds no "
                "SnapWave field, advection velocities or wavemaker filter, so this is a "
                "different run from an uninterrupted one (FINDINGS §44 (j)). Read it "
                "against an uninterrupted twin.",
            )
        )
    elif n_res:
        out.append(
            _flag(
                "resumed",
                "info",
                f"Resumed {n_res}x from a restart file (waves off: the toy-model resume "
                "differs by <= 0.2 mm p90 from an uninterrupted run).",
            )
        )
    if f.get("soil_reset") and f.get("rain_on", True):
        out.append(
            _flag(
                "soil_reset",
                "caution",
                "Soil state RESET on resume (restart files carry no cumprcp / cuminf): "
                "the curve-number soil restarts empty and over-infiltrates any rain after "
                "the resume (FINDINGS §59). Rain-driven marks and ponding read low.",
            )
        )
    seed = str(f.get("engine_seed") or "")
    if seed.startswith("os-random"):
        out.append(
            _flag(
                "unseeded_engine",
                "caution",
                f"engine_seed = {seed}: the engine's random draw is unseeded, so this run "
                "does not repeat itself and a paired difference against another arm is "
                "partly a different random draw (FINDINGS §44).",
            )
        )
    elif seed in ("", "unknown"):
        out.append(_flag("seed_unknown", "info", "engine_seed unknown."))
    if str(f.get("engine") or "unknown").startswith("unknown"):
        out.append(
            _flag(
                "engine_unknown", "caution", f"Engine not recorded ({f.get('engine')})."
            )
        )
    if f.get("extent_admissible") is False or f.get("waves_on") is False:
        out.append(
            _flag(
                "waves_off_extent",
                "caution",
                "Waves OFF: CSI / POD / FAR are kept, flagged extent_admissible=False — "
                "a real measurement, not on the same footing as a waves-on CSI. Do not "
                "rank across the two (FINDINGS §4).",
            )
        )
    if f.get("has_metrics_row") is False:
        out.append(
            _flag(
                "no_metrics_row",
                "caution",
                "No metrics.csv row for this arm — run "
                "`run_experiments.py --experiments <arm> --validate-only`.",
            )
        )
    n, n_ref = f.get("hwm_n_scored"), f.get("ref_hwm_n_scored")
    if _finite(n) and _finite(n_ref) and int(n) != int(n_ref):
        out.append(
            _flag(
                "hwm_count_mismatch",
                "caution",
                f"Scores {int(n)} HWMs; the reference {f.get('ref_arm')} scores "
                f"{int(n_ref)} — the scorer saw a different grid; not comparable until "
                "explained.",
            )
        )
    if f.get("floodmap_fresh") is False:
        out.append(
            _flag(
                "floodmap_stale",
                "caution",
                "The floodmap cache is stale or missing: the HWM and MOTF "
                "figures skipped (re-run --validate-only to refresh it).",
            )
        )
    return out


def _finite(v) -> bool:
    try:
        return v is not None and np.isfinite(float(v))
    except (TypeError, ValueError):
        return False


def gallery_windows(dom=None) -> list[tuple[str, tuple]]:
    """``[(name, (x0, x1, y0, y1)), …]``: the whole domain first, then the zooms.

    The whole frame is ``Domain.plot_window``; the zooms are ``Domain.gallery_windows``
    (or every non-None ``map_windows`` entry when that is empty)."""
    dom = dom or _domain.active()
    wins: list[tuple[str, tuple]] = []
    if dom.plot_window is not None:
        wins.append(("domain", tuple(float(v) for v in dom.plot_window)))
    names = dom.gallery_windows or tuple(
        k for k, v in dom.map_windows.items() if v is not None
    )
    for k in names:
        v = dom.map_windows.get(k)
        if v is None:
            raise KeyError(
                f"domain {dom.name!r}: gallery window {k!r} is not a map_windows entry "
                "(or is None) — fix Domain.gallery_windows"
            )
        wins.append((k, tuple(float(x) for x in v)))
    return wins


def headline(row: dict | None) -> dict:
    """The headline numbers of a metrics row, with their measurement labels."""
    keys = (
        "hwm_estimator",
        "hwm_radius_m",
        "hwm_n_scored",
        "hwm_n_dry_scored",
        "hwm_rmse_scored_m",
        "hwm_bias_scored_m",
        "hwm_within0.5_scored",
        "hwm_n_scored_excl_lake_blocked",
        "hwm_rmse_scored_excl_lake_blocked_m",
        "hwm_bias_scored_excl_lake_blocked_m",
        "hwm_lake_outlet_blocked_ids",
        "hwm_n_scored_excl_noted",
        "hwm_rmse_scored_excl_noted_m",
        "hwm_bias_scored_excl_noted_m",
        "hwm_noted_ids",
        "motf_csi",
        "motf_pod",
        "motf_far",
        "motf_km2_excluded_boxes",
        "motf_csi_connected",
        "motf_far_connected",
        "extent_admissible",
    )
    row = row or {}
    return {k: _jsonable(row.get(k)) for k in keys if k in row}


def _jsonable(v):
    if v is None:
        return None
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        return None if not np.isfinite(v) else float(v)
    return v if isinstance(v, (int, str)) else str(v)


# ═════════════════════════════════════════════════════════════════════════════════════
# reading a run (cheap parts)
# ═════════════════════════════════════════════════════════════════════════════════════


def metrics_row(domain_name: str, arm: str) -> dict | None:
    """The arm's row of ``experiments/<domain>/metrics.csv``, or None."""
    import pandas as pd

    csv = ROOT / "experiments" / domain_name / "metrics.csv"
    if not csv.is_file():
        return None
    df = pd.read_csv(csv, index_col=0, low_memory=False)
    if arm not in df.index:
        return None
    return {k: _jsonable(v) for k, v in df.loc[arm].items()}


def reference_arm(domain_name: str, arm: str) -> str:
    """The arm this arm is paired against (``experiments.reference_arm``), falling back to
    the domain's premier name when the arm is unregistered or the registry will not
    import."""
    from .premier import PREMIER_NAME

    try:
        from .experiments import reference_arm as _ref

        return _ref(arm, domain_name) or PREMIER_NAME
    except Exception:  # noqa: BLE001 — the registry is edited live; the name is enough
        return PREMIER_NAME


def floodmap_fresh(run_dir: Path) -> bool:
    """``load_floodmap``'s own freshness rule: the cached tif is newer than both the map
    and the bed it was downscaled onto. False = loading would RE-downscale (and write)."""
    run_dir = Path(run_dir)
    fm, mp = run_dir / "floodmap_hmax_lev3.tif", run_dir / "sfincs_map.nc"
    dep = run_dir / "subgrid" / "dep_subgrid_merged.tif"
    if not dep.is_file():
        dep = run_dir / "subgrid" / "dep_subgrid_lev3.tif"
    if not (fm.is_file() and dep.is_file()):
        return False
    t = fm.stat().st_mtime
    return (not mp.is_file() or t >= mp.stat().st_mtime) and t >= dep.stat().st_mtime


def _log_wall(run_dir: Path) -> dict:
    """``Total time`` / ``Time in SnapWave`` (s) off the (last segment's) sfincs.log."""
    out = {}
    p = Path(run_dir) / "sfincs.log"
    if not p.is_file():
        return out
    with open(p, errors="replace") as fh:
        tail = fh.readlines()[-60:]
    for ln in tail:
        m = re.match(r"\s*(Total time|Time in SnapWave)\s*:\s*([\d.]+)", ln)
        if m:
            out[m.group(1).lower().replace(" ", "_") + "_s"] = float(m.group(2))
    return out


def _sacct(job: str | None) -> dict:
    """Elapsed / node / state of the solve job, if ``sacct`` answers within 20 s."""
    if not job or not str(job).strip().isdigit():
        return {}
    try:
        r = subprocess.run(
            [
                "sacct",
                "-j",
                str(job),
                "-X",
                "-n",
                "-P",
                "--format=Elapsed,NodeList,State,Partition",
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        first = r.stdout.strip().splitlines()[0].split("|")
        return dict(zip(("elapsed", "nodelist", "state", "partition"), first))
    except Exception:  # noqa: BLE001 — a missing accounting record is not an error
        return {}


def run_card(domain_name: str, arm: str, run_dir: Path, row: dict | None) -> dict:
    """Everything the site prints about a run besides its figures."""
    from . import premier, provenance
    from .plots import _waves_off

    run_dir = Path(run_dir)
    card: dict = {"domain": domain_name, "arm": arm, "run_dir": str(run_dir)}
    try:
        fp = premier.domain_fingerprint(run_dir)
        card["fingerprint"] = {
            "faces": fp.n_faces,
            "boundary_edges": fp.n_boundary_edges,
            "sha": fp.sha_z_mask,
            "label": premier.KNOWN.get(fp, "UNRECOGNISED"),
        }
        card["sealed"] = fp == premier.expected()
    except Exception as e:  # noqa: BLE001
        card["fingerprint"] = {"error": str(e)}
        card["sealed"] = False
    whole, problems = premier.output_complete(run_dir)
    card["audit"] = {
        "whole": whole,
        "problems": problems,
        "summary": {None: "no output", True: "output WHOLE"}.get(
            whole, "OUTPUT TRUNCATED"
        ),
    }
    eng = provenance.read_engine(run_dir) or {}
    card["engine"] = {
        k: eng.get(k)
        for k in (
            "label",
            "build_revision",
            "host",
            "job_id",
            "threads",
            "restart_count",
            "recorded",
            "build_branch",
        )
        if eng.get(k) is not None
    }
    labels = {}
    for key, fn in (
        ("engine", provenance.engine_label),
        ("snapwave_direction", provenance.snapwave_direction),
        ("engine_seed", provenance.engine_seed_label),
        ("meteo", provenance.meteo_label),
        ("infiltration", provenance.infiltration_label),
        ("subgrid", provenance.subgrid_label),
        ("wind_scale", provenance.wind_scale_label),
        ("sea_level_offset", provenance.sea_level_offset_label),
        ("extra_discharge", provenance.extra_discharge_label),
    ):
        try:
            labels[key] = fn(run_dir)
        except Exception as e:  # noqa: BLE001
            labels[key] = f"unavailable ({e})"
    row = row or {}
    if row.get("extent_admissible") is not None:
        labels["extent_admissible"] = row.get("extent_admissible")
    # the row's own copy of each label, where it disagrees with the live read
    card["labels"] = labels
    card["labels_row_differs"] = {
        k: row[k]
        for k in labels
        if k in row and row[k] is not None and str(row[k]) != str(labels[k])
    }
    try:
        waves_on = not _waves_off(run_dir)
    except Exception:  # noqa: BLE001
        waves_on = provenance.snapwave_direction(run_dir) != "off"
    inp = provenance.read_inp(run_dir)
    card["config"] = {
        "waves_on": waves_on,
        "rain_on": labels.get("infiltration") != "no-rain",
        "tstart": inp.get("tstart"),
        "tstop": inp.get("tstop"),
        "dtwave": inp.get("dtwave"),
        "snapwave_igwaves": inp.get("snapwave_igwaves"),
        "wavemaker": bool(str(inp.get("wvmfile", "")).strip()),
    }
    hist = run_dir / "restart_history.txt"
    card["restart"] = parse_restart_history(hist.read_text() if hist.is_file() else "")
    card["wall"] = {**_log_wall(run_dir), **_sacct(eng.get("job_id"))}
    card["metrics"] = headline(row)
    card["floodmap_fresh"] = floodmap_fresh(run_dir)
    return card


# ═════════════════════════════════════════════════════════════════════════════════════
# faces → display pixels (exact, quadtree-aware)
# ═════════════════════════════════════════════════════════════════════════════════════


class Faces:
    """A run's faces, enough to paint any face field onto any north-up display grid.

    ``pixel_map(window, shape)`` returns, per display pixel CENTRE, the index of the face
    containing it (-1 = none) — the same centre-in-polygon rule as ``rasterize`` in
    ``validate.simulated_mask``. Exact on a quadtree: faces are grouped by size, and each
    size class is a lattice in the grid's rotated frame (``x0``/``y0``/``rotation`` from
    sfincs.inp — v3's is 359.183°, CLAUDE.md §5), so containment is an integer lookup."""

    def __init__(self, run_dir: Path, need_hm0: bool = False):
        import xarray as xr

        from .provenance import read_inp

        run_dir = Path(run_dir)
        inp = read_inp(run_dir)
        self.x0 = float(inp.get("x0", 0.0))
        self.y0 = float(inp.get("y0", 0.0))
        th = np.deg2rad(float(inp.get("rotation", 0.0)))
        self.c, self.s = np.cos(th), np.sin(th)
        with xr.open_dataset(
            run_dir / "sfincs_map.nc", mask_and_scale=False, decode_times=False
        ) as ds:
            fn = np.asarray(ds["mesh2d_face_nodes"].values)
            fn0 = (fn - 1 if np.nanmin(fn) == 1 else fn).astype("int64")
            nx_ = np.asarray(ds["mesh2d_node_x"].values)
            ny_ = np.asarray(ds["mesh2d_node_y"].values)
            fx, fy = nx_[fn0], ny_[fn0]
            del nx_, ny_, fn, fn0
            self.n = fx.shape[0]
            self.xc, self.yc = fx.mean(1), fy.mean(1)
            size = np.hypot(fx[:, 1] - fx[:, 0], fy[:, 1] - fy[:, 0])
            del fx, fy
            self.area = (size.astype("float64") ** 2).astype("float32")
            self.zb = _fill(np.asarray(ds["zb"].values, "float32"))
            self.msk = np.asarray(ds["msk"].values)
            z = _fill(np.asarray(ds["zsmax"].values, "float32"))
            with np.errstate(all="ignore"), _quiet():
                self.zsmax = np.nanmax(z, axis=0) if z.ndim == 2 else z
            del z
            self.hm0max = None
            if need_hm0 and "hm0" in ds.variables:
                h = ds["hm0"]
                acc = np.full(self.n, np.nan, "float32")
                for i in range(
                    h.sizes["time"]
                ):  # one map at a time: 73 x 20 MB, not 1.4 G
                    v = _fill(np.asarray(h[i].values, "float32"))
                    acc = np.fmax(acc, v)
                self.hm0max = acc
        # size classes: round each face to the nearest power-of-two fraction of the
        # coarsest size, then index each class as a lattice in the rotated frame
        u, v = self._rot(self.xc, self.yc)
        big = float(np.nanmax(size))
        lev = np.clip(np.round(np.log2(big / size)), 0, 12).astype(int)
        # the face's MEAN ground from its own subgrid table (the run's, not the
        # template's — a subgrid_from arm solves on a different table)
        self.zmean = None
        sg = run_dir / "sfincs_subgrid.nc"
        if sg.is_file():
            with xr.open_dataset(sg) as g:
                if g.sizes.get("np") == self.n:
                    zmax = np.asarray(g["z_zmax"].values, "float32")
                    vmax = np.asarray(g["z_volmax"].values, "float32")
                    self.zmean = (zmax - vmax / self.area).astype("float32")
        self.levels = []
        for L in np.unique(lev):
            sel = np.where(lev == L)[0]
            d = big / 2.0**L
            i = np.floor(u[sel] / d).astype(np.int64)
            j = np.floor(v[sel] / d).astype(np.int64)
            key = i * 4_000_000 + j
            order = np.argsort(key)
            self.levels.append((d, key[order], sel[order]))

    def _rot(self, x, y):
        dx, dy = np.asarray(x) - self.x0, np.asarray(y) - self.y0
        return dx * self.c + dy * self.s, -dx * self.s + dy * self.c

    def pixel_map(self, window, shape) -> np.ndarray:
        x0, x1, y0, y1 = window
        ny, nx = shape
        xs = x0 + (np.arange(nx) + 0.5) * (x1 - x0) / nx
        ys = y1 - (np.arange(ny) + 0.5) * (y1 - y0) / ny
        X, Y = np.meshgrid(xs, ys)
        u, v = self._rot(X.ravel(), Y.ravel())
        out = np.full(u.shape, -1, dtype=np.int64)
        for d, keys, idx in self.levels:
            todo = out < 0
            if not todo.any():
                break
            k = np.floor(u[todo] / d).astype(np.int64) * 4_000_000 + np.floor(
                v[todo] / d
            ).astype(np.int64)
            pos = np.clip(np.searchsorted(keys, k), 0, keys.size - 1)
            hit = keys[pos] == k
            sub = np.where(todo)[0]
            out[sub[hit]] = idx[pos[hit]]
        return out.reshape(shape)


def wet_faces(F: "Faces") -> np.ndarray:
    """Active faces whose peak level stands >= WET_ABOVE_MEAN_M above the face's MEAN
    ground (subgrid), falling back to ``zb`` (lowest pixel) without a subgrid table."""
    ground = F.zmean if F.zmean is not None else F.zb
    with np.errstate(invalid="ignore"):
        return (
            (F.msk > 0)
            & np.isfinite(F.zsmax)
            & ((F.zsmax - ground) >= WET_ABOVE_MEAN_M)
        )


def _wet_caption(F: "Faces", rain_on: bool) -> str:
    g = (
        "the face's mean ground (subgrid z_zmax − z_volmax / area)"
        if (F.zmean is not None)
        else "the face's lowest bed zb (no subgrid table found)"
    )
    s = f"faces whose peak level is ≥ {WET_ABOVE_MEAN_M:g} m above {g}"
    if rain_on:
        s += (
            "; on this rain-on arm inland ponding from rain still appears where it "
            "genuinely stands above mean ground"
        )
    return s


def _fill(a):
    """SFINCS writes -99999 as fill (decode is off): NaN it."""
    a = np.asarray(a, "float32")
    return np.where(a > -9.0e3, a, np.nan).astype("float32")


def _shape_for(window, px: int = PANEL_PX) -> tuple[int, int]:
    x0, x1, y0, y1 = window
    w, h = x1 - x0, y1 - y0
    return (
        (px, max(1, int(round(px * w / h))))
        if h >= w
        else (max(1, int(round(px * h / w))), px)
    )


def _paint(field, pm):
    """Face field → display image through a pixel map (NaN where no face)."""
    img = np.full(pm.shape, np.nan, "float32")
    ok = pm >= 0
    img[ok] = field[pm[ok]]
    return img


# ═════════════════════════════════════════════════════════════════════════════════════
# figure scaffolding
# ═════════════════════════════════════════════════════════════════════════════════════


def _mpl():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "figure.facecolor": PAPER,
            "axes.facecolor": PAPER,
            "savefig.facecolor": PAPER,
            "axes.edgecolor": HAIR,
            "axes.labelcolor": INK2,
            "axes.titlecolor": INK,
            "xtick.color": INK2,
            "ytick.color": INK2,
            "text.color": INK,
            "font.size": 8.5,
            "axes.titlesize": 9,
            "axes.linewidth": 0.6,
            "grid.color": "#d9d5cc",
            "grid.linewidth": 0.5,
            "legend.frameon": False,
        }
    )
    return plt


def cmap_sequential(name: str = "water"):
    """One hue, light → dark."""
    from matplotlib.colors import LinearSegmentedColormap

    stops = {
        "water": ("#e6eef6", "#9cc0e2", "#3f7fbf", "#173f73", "#0a1f3d"),
        "wave": ("#efeaf5", "#c3b3dd", "#8a6dbd", "#553a8c", "#2a1650"),
    }[name]
    cm = LinearSegmentedColormap.from_list(f"gallery_{name}", stops)
    cm.set_bad((0, 0, 0, 0))
    return cm


def cmap_diverging():
    """Orange (below) → neutral grey → purple (above)."""
    from matplotlib.colors import LinearSegmentedColormap

    cm = LinearSegmentedColormap.from_list("gallery_div", DIVERGING)
    cm.set_bad((0, 0, 0, 0))
    return cm


class _Maps:
    """One small-multiples map figure: the whole domain + the fixed zooms, fixed size."""

    def __init__(self, plt, windows, title):
        n = len(windows)
        ncol = min(NCOL, n)
        nrow = int(np.ceil(n / ncol))
        self.fig, axs = plt.subplots(
            nrow,
            ncol,
            figsize=(PANEL_W * ncol + 1.1, PANEL_H * nrow + 0.5),
            squeeze=False,
            layout="constrained",
        )
        self.fig.suptitle(title, fontsize=10.5, color=INK, x=0.01, ha="left")
        self.axes = list(axs.ravel())
        for ax in self.axes[n:]:
            ax.axis("off")
        self.windows = windows

    def panels(self):
        return zip(self.axes, self.windows)

    def colorbar(self, mappable, label, extend="neither"):
        cb = self.fig.colorbar(
            mappable, ax=self.axes, shrink=0.55, aspect=30, extend=extend, pad=0.01
        )
        cb.set_label(label, color=INK2)
        cb.outline.set_edgecolor(HAIR)
        return cb


def _frame(ax, name, win, outline=None):
    x0, x1, y0, y1 = win
    if outline is not None:
        try:
            outline.plot(ax=ax, color="#8d887e", lw=0.45, zorder=6)
        except Exception:  # noqa: BLE001 — context only
            pass
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_edgecolor(HAIR)
    km = (x1 - x0) / 1000
    ax.set_title(
        f"{name.replace('_', ' ')}  ·  {km:.0f} km wide",
        fontsize=8.5,
        color=INK2,
        loc="left",
    )


def _backdrop(ax, F: Faces, pm, win):
    """Land / water from the run's own faces (zb, active only); outside = paper."""
    from matplotlib.colors import to_rgba

    zb = _paint(F.zb, pm)
    act = _paint((F.msk > 0).astype("float32"), pm) > 0
    rgba = np.zeros(pm.shape + (4,), "float32")
    rgba[act & (zb >= 0)] = to_rgba(LAND)
    rgba[act & (zb < 0)] = to_rgba(WATER_BG)
    ax.imshow(rgba, extent=win, origin="upper", interpolation="nearest", zorder=0)


def _outline(epsg):
    try:
        from .plots import state_outline

        return state_outline(
            epsg, ("New Jersey", "New York", "Pennsylvania", "Delaware", "Maryland")
        )
    except Exception:  # noqa: BLE001
        return None


def _save(fig, path: Path):
    import matplotlib.pyplot as plt

    tmp = path.with_suffix(".partial.png")
    fig.savefig(tmp, dpi=DPI)
    plt.close(fig)
    try:  # 256-colour palette PNG: ~3x smaller, keeps the site repo small
        from PIL import Image

        with Image.open(tmp) as im:
            q = im.convert("RGB").quantize(colors=256, method=Image.Quantize.MEDIANCUT)
        q.save(tmp, optimize=True)
    except Exception:  # noqa: BLE001 — the full-colour PNG is fine too
        pass
    os.replace(tmp, path)


# ═════════════════════════════════════════════════════════════════════════════════════
# the figures
# ═════════════════════════════════════════════════════════════════════════════════════


class _Ctx:
    """What every figure function gets."""

    def __init__(self, domain_name, arm, run_dir, out, row, card, ref, ref_dir):
        self.domain_name, self.arm, self.run_dir, self.out = (
            domain_name,
            arm,
            run_dir,
            out,
        )
        self.row, self.card, self.ref, self.ref_dir = row or {}, card, ref, ref_dir
        self.dom = _domain.active()
        self.windows = gallery_windows(self.dom)
        self.plt = _mpl()
        self.outline = _outline(self.dom.epsg)
        self._faces = None
        self._pm: dict = {}
        self.rasters = None  # (hmax, dep) from validate.load_floodmap

    @property
    def faces(self) -> Faces:
        if self._faces is None:
            self._faces = Faces(self.run_dir, need_hm0=self.card["config"]["waves_on"])
        return self._faces

    def pm(self, name, win):
        if name not in self._pm:
            self._pm[name] = self.faces.pixel_map(win, _shape_for(win))
        return self._pm[name]

    def title(self, key):
        return f"{self.arm}  ·  {dict(FIGURES)[key]}  ·  {self.domain_name}"


def fig_zsmax(c: _Ctx) -> dict:
    F = c.faces
    wet = wet_faces(F)
    field = np.where(wet, F.zsmax, np.nan).astype("float32")
    m = _Maps(c.plt, c.windows, c.title("zsmax"))
    im = None
    for ax, (name, win) in m.panels():
        pm = c.pm(name, win)
        _backdrop(ax, F, pm, win)
        im = ax.imshow(
            _paint(field, pm),
            extent=win,
            origin="upper",
            cmap=cmap_sequential(),
            vmin=ZSMAX_RANGE[0],
            vmax=ZSMAX_RANGE[1],
            interpolation="nearest",
            zorder=1,
        )
        _frame(ax, name, win, c.outline)
    m.colorbar(im, "peak water level zsmax [m NAVD88]", extend="both")
    _save(m.fig, c.out / "zsmax.png")
    v = field[np.isfinite(field)]
    return {
        "caption": (
            "Peak water LEVEL (m NAVD88; a level, not a depth — max of zsmax over the "
            "run) on "
            f"{_wet_caption(F, c.card['config']['rain_on'])}; fixed scale "
            f"{ZSMAX_RANGE[0]:g}–{ZSMAX_RANGE[1]:g} m NAVD88 for every arm. Faces painted "
            f"exactly at panel resolution. {v.size:,} wet faces; p50 {np.median(v):.2f} m, "
            f"p99 {np.percentile(v, 99):.2f} m (colour clipped at the top)."
            if v.size
            else "No wet faces."
        ),
    }


def fig_dzsmax(c: _Ctx) -> dict:
    from . import premier

    if c.arm == c.ref:
        return {
            "skipped": f"this IS the reference arm ({c.ref}) — no difference to draw"
        }
    if c.ref_dir is None or not (c.ref_dir / "sfincs_map.nc").is_file():
        return {"skipped": f"reference arm {c.ref} has no output on {c.domain_name}"}
    fa, fb = (
        premier.domain_fingerprint(c.run_dir),
        premier.domain_fingerprint(c.ref_dir),
    )
    if fa != fb:
        return {
            "skipped": (
                f"different fingerprint from the reference {c.ref} ({fa} vs {fb}) — a "
                "face-by-face difference is undefined; no Δ drawn"
            )
        }
    ref_whole, _ = premier.output_complete(c.ref_dir)
    F = c.faces
    R = Faces(c.ref_dir)
    both = (F.msk > 0) & (R.msk > 0) & np.isfinite(F.zsmax) & np.isfinite(R.zsmax)
    wet = wet_faces(F) | wet_faces(R)
    d = np.where(both & wet, F.zsmax - R.zsmax, np.nan).astype("float32")
    del R
    m = _Maps(
        c.plt,
        c.windows,
        f"{c.arm} − {c.ref}  ·  Δ peak water level  ·  {c.domain_name}",
    )
    im = None
    for ax, (name, win) in m.panels():
        pm = c.pm(name, win)
        _backdrop(ax, F, pm, win)
        im = ax.imshow(
            _paint(d, pm),
            extent=win,
            origin="upper",
            cmap=cmap_diverging(),
            vmin=-DZS_LIM,
            vmax=DZS_LIM,
            interpolation="nearest",
            zorder=1,
        )
        _frame(ax, name, win, c.outline)
    m.colorbar(im, f"zsmax {c.arm} − {c.ref} [m]", extend="both")
    _save(m.fig, c.out / "dzsmax.png")
    v = d[np.isfinite(d)]
    p5, p50, p95 = np.percentile(v, [5, 50, 95]) if v.size else (np.nan,) * 3
    warn = "" if ref_whole else " ⚠️ the reference's audit is NOT 'output WHOLE'."
    return {
        "caption": (
            f"zsmax of this arm minus the reference {c.ref} (same fingerprint {fa.sha_z_mask}), "
            "on faces active in both and, in either arm, "
            f"{_wet_caption(F, c.card['config']['rain_on'])}; fixed scale "
            f"±{DZS_LIM:g} m (orange = this arm lower, purple = higher). {v.size:,} faces: "
            f"p05 {p5:+.3f}, median {p50:+.3f}, p95 {p95:+.3f} m. A waves-on Δ of a few "
            "cm in the bays is inside the null-perturbation noise (CLAUDE.md §5)."
            + warn
        ),
        "stats": {
            "n_faces": int(v.size),
            "p05_m": _jsonable(p5),
            "median_m": _jsonable(p50),
            "p95_m": _jsonable(p95),
        },
    }


def fig_hm0(c: _Ctx) -> dict:
    if not c.card["config"]["waves_on"]:
        return {"skipped": "waves OFF — no SnapWave output"}
    F = c.faces
    if F.hm0max is None:
        return {"skipped": "no hm0 in sfincs_map.nc"}
    h = np.where(F.msk > 0, F.hm0max, np.nan).astype("float32")
    h[h <= 0.01] = np.nan
    m = _Maps(c.plt, c.windows, c.title("hm0"))
    im = None
    for ax, (name, win) in m.panels():
        pm = c.pm(name, win)
        _backdrop(ax, F, pm, win)
        im = ax.imshow(
            _paint(h, pm),
            extent=win,
            origin="upper",
            cmap=cmap_sequential("wave"),
            vmin=HM0_RANGE[0],
            vmax=HM0_RANGE[1],
            interpolation="nearest",
            zorder=1,
        )
        _frame(ax, name, win, c.outline)
    m.colorbar(im, "peak Hm0 [m] (max of the map output)", extend="max")
    _save(m.fig, c.out / "hm0.png")
    return {
        "caption": (
            "Peak significant wave height: the maximum over the run of SnapWave's hm0 "
            f"MAP output (written every dtmapout = "
            f"{c.card['config'].get('dtwave') or '?'} s wave update; the true peak can sit "
            f"between snapshots). Fixed scale {HM0_RANGE[0]:g}–{HM0_RANGE[1]:g} m. "
            "Incident band only (hm0, not hm0ig)."
        )
    }


# ── raster figures (one heavy load) ─────────────────────────────────────────────────


def _block(full_shape, T, win, shape, fn_vals, reduce="max"):
    """Reduce a north-up full-res array onto a display grid over ``win``.

    ``fn_vals(r0, r1, c0, c1)`` returns the full-res values of that slab (already masked);
    returns ``(image, extent)``. Strips of rows keep the temporaries small."""
    x0, x1, y0, y1 = win
    H, W = full_shape
    c0 = max(0, int(np.floor((x0 - T.c) / T.a)))
    c1 = min(W, int(np.ceil((x1 - T.c) / T.a)))
    r0 = max(0, int(np.floor((y1 - T.f) / T.e)))
    r1 = min(H, int(np.ceil((y0 - T.f) / T.e)))
    if c1 <= c0 or r1 <= r0:
        return None, None
    fy = max(1, int(np.ceil((r1 - r0) / shape[0])))
    fx = max(1, int(np.ceil((c1 - c0) / shape[1])))
    f = max(fx, fy)
    ny, nx = (r1 - r0) // f, (c1 - c0) // f
    if ny == 0 or nx == 0:
        return None, None
    img = np.full((ny, nx), np.nan, "float32")
    step = 64
    for by in range(0, ny, step):
        bys = min(step, ny - by)
        ra, rb = r0 + by * f, r0 + (by + bys) * f
        v = fn_vals(ra, rb, c0, c0 + nx * f).reshape(bys, f, nx, f)
        with np.errstate(all="ignore"), _quiet():
            img[by : by + bys] = (
                np.nanmax(v, axis=(1, 3)) if reduce == "max" else v.sum(axis=(1, 3))
            )
    ext = (
        T.c + c0 * T.a,
        T.c + (c0 + nx * f) * T.a,
        T.f + (r0 + ny * f) * T.e,
        T.f + r0 * T.e,
    )
    return img, ext


class _quiet:
    def __enter__(self):
        import warnings

        self._w = warnings.catch_warnings()
        self._w.__enter__()
        warnings.simplefilter("ignore", category=RuntimeWarning)

    def __exit__(self, *a):
        self._w.__exit__(*a)


class Rasters:
    """Strip-wise stand-in for ``validate.load_floodmap``'s ``(da_hmax, da_dep)``.

    ⚡ WHY. On ``v4_refreeze`` those two arrays are 1.2 G pixels each and the load that
    makes them pulls the 4.8 G-pixel rotated bed into memory (a v4 validate needs ~200 G
    for one arm). The gallery needs only slabs of them, so:

    * ``da_hmax`` IS the gallery tif ``experiments/<domain>/floodmaps/<arm>_hmax_lev3.tif``
      — ``validate.evaluate`` writes exactly that array there (de-rotated, deep ocean
      dropped), north-up, one strip per row, so a row slab is a cheap read;
    * ``da_dep`` is the scorer's ``reproject_match`` of the rotated bed onto that grid,
      nearest-neighbour — reproduced per slab by a GDAL warp of the SAME source onto the
      SAME target pixels through the dataset's affine (CLAUDE.md §5: rotated rasters only
      through the affine, never ``x0 + col*res``; a rotation-only affine has no
      approximation error in the warper).

    The figures self-check against the metrics row (HWM RMSE / bias, MOTF CSI / POD /
    FAR to 4 dp), so a drift here cannot pass silently."""

    def __init__(self, run_dir: Path, gallery_tif: Path | None):
        """``gallery_tif=None`` opens the bed only (``dep_on``)."""
        import rasterio

        self.run_dir = Path(run_dir)
        dep = self.run_dir / "subgrid" / "dep_subgrid_merged.tif"
        if not dep.is_file():
            dep = self.run_dir / "subgrid" / "dep_subgrid_lev3.tif"
        self.d = rasterio.open(str(dep))
        self.h = rasterio.open(str(gallery_tif)) if gallery_tif is not None else None
        if self.h is not None:
            self.T = self.h.transform
            self.shape = (self.h.height, self.h.width)
            self.crs = self.h.crs

    def close(self):
        if self.h is not None:
            self.h.close()
        self.d.close()

    def hmax(self, r0, r1, c0, c1) -> np.ndarray:
        from rasterio.windows import Window

        a = self.h.read(1, window=Window(c0, r0, c1 - c0, r1 - r0), masked=True)
        return np.ma.filled(a.astype("float32"), np.nan)

    def dep(self, r0, r1, c0, c1) -> np.ndarray:

        T = self.T
        return self.dep_on(T * T.translation(c0, r0), (r1 - r0, c1 - c0))

    def dep_on(self, dst_t, shape) -> np.ndarray:
        """The rotated bed, nearest-warped onto ANY north-up grid (``dst_t``, shape)."""
        from rasterio.warp import Resampling, reproject

        out = np.full(tuple(shape), np.nan, "float32")
        win, win_t = self._src_window(dst_t, out.shape)
        reproject(
            source=self.d.read(1, masked=False, window=win),
            destination=out,
            src_transform=win_t,
            src_crs=self.d.crs,
            src_nodata=self.d.nodata,
            dst_transform=dst_t,
            dst_crs=self.d.crs,
            dst_nodata=np.nan,
            resampling=Resampling.nearest,
        )
        return out

    def _src_window(self, dst_t, shape):
        """The source window (with a margin) covering a destination slab."""
        from rasterio.windows import Window

        h, w = shape
        xs = [dst_t.c, dst_t.c + w * dst_t.a]
        ys = [dst_t.f, dst_t.f + h * dst_t.e]
        inv = ~self.d.transform
        cols, rows = [], []
        for x in xs:
            for y in ys:
                cc, rr = inv * (x, y)
                cols.append(cc)
                rows.append(rr)
        pad = 4
        c0 = max(0, int(np.floor(min(cols))) - pad)
        r0 = max(0, int(np.floor(min(rows))) - pad)
        c1 = min(self.d.width, int(np.ceil(max(cols))) + pad)
        r1 = min(self.d.height, int(np.ceil(max(rows))) + pad)
        c1, r1 = max(c1, c0 + 1), max(r1, r0 + 1)
        win_t = self.d.transform * self.d.transform.translation(c0, r0)
        return Window(c0, r0, c1 - c0, r1 - r0), win_t

    def tile(self, r0, r1, c0, c1):
        """``(da_hmax, da_dep)`` DataArrays of one slab, for ``plots._sample_hwm``."""
        import rioxarray  # noqa: F401
        import xarray as xr

        T = self.T * self.T.translation(c0, r0)
        ys = T.f + (np.arange(r1 - r0) + 0.5) * T.e
        xs = T.c + (np.arange(c1 - c0) + 0.5) * T.a
        out = []
        for a in (self.hmax(r0, r1, c0, c1), self.dep(r0, r1, c0, c1)):
            da = xr.DataArray(a, coords={"y": ys, "x": xs}, dims=("y", "x"))
            out.append(da.rio.write_crs(self.crs).rio.write_transform(T))
        return out[0], out[1]


def gallery_tif(domain_name: str, arm: str) -> Path:
    return ROOT / "experiments" / domain_name / "floodmaps" / f"{arm}_hmax_lev3.tif"


def gallery_tif_fresh(run_dir: Path, tif: Path) -> bool:
    """The gallery tif exists and was written no earlier than the run-dir floodmap cache
    it was derived from (both by the same ``validate.evaluate``), which is itself fresh."""
    fm = Path(run_dir) / "floodmap_hmax_lev3.tif"
    return (
        tif.is_file()
        and floodmap_fresh(run_dir)
        and tif.stat().st_mtime >= fm.stat().st_mtime - 1.0
    )


#: Pixel size of the flood-depth computation (then block-MAX to the panel); the whole-domain
#: panel uses ~long side / 8000 so it stays ~30 m without a 100 M-pixel strip.
DEPTH_RES_M = 25.0


def fig_flood_depth(c: _Ctx) -> dict:
    """Flood depth on NORMALLY-DRY land only, pixel level (user 2026-10-19, NOAA/NHC style).

    A pixel is normally dry when ``nj_sfincs.normal_surface`` says so: no usual water
    surface there (``W`` NaN), or its ground stands at or above it (``ground >= W``, i.e.
    ``usual_surface == ground``); W = the non-tidal lake pool, else MHHW (NOAA VDatum).
    Depth = peak water level − pixel ground. Normally-wet pixels (ocean, bays, rivers,
    lakes, intertidal ground below MHHW) stay blank — the water-on-water view is the
    zsmax LEVEL map. Water level per pixel = zsmax of the ACTIVE face holding the pixel
    centre (exact quadtree lookup); ground = the run's merged subgrid bed, nearest-warped
    through its rotated affine (CLAUDE.md §5)."""
    try:
        from .normal_surface import (
            mhhw_path,
            pool_path,
            usual_water_surface,
        )

        need = [mhhw_path(c.domain_name), pool_path(c.domain_name)]
        try:  # the NHD water mask normally_wet reads (when that rule is present)
            from .normal_surface import water_mask_path

            need.append(water_mask_path(c.domain_name))
        except ImportError:
            pass
        missing = [p.name for p in need if not p.is_file()]
    except (ImportError, ValueError) as e:
        return {
            "skipped": f"no usual-surface reference for {c.domain_name} ({e}) — "
            "nj_sfincs.normal_surface / Domain.normal_surface_dir; re-render once built"
        }
    if missing:
        return {
            "skipped": f"usual-surface rasters not built yet ({', '.join(missing)}; "
            "scripts/build_normal_surface_v4.py) — re-render with --only flood_depth"
        }
    from rasterio.transform import from_origin

    try:  # THE one dry/wet rule for every figure, once normal_surface has it
        from .normal_surface import normally_wet
    except ImportError:
        # TODO(gallery): drop this fallback once normal_surface.normally_wet lands —
        # `ground >= W` misreads river channels whose DEM holds the lidar water surface
        # (the Delaware near Trenton) as flooded land.
        normally_wet = None
    F = c.faces
    bed = Rasters(c.run_dir, None)
    zs_face = np.where(F.msk > 0, F.zsmax, np.nan).astype("float32")
    m = _Maps(c.plt, c.windows, c.title("flood_depth"))
    im = None
    n_px = 0
    try:
        for ax, (name, win) in m.panels():
            _backdrop(ax, F, c.pm(name, win), win)
            x0, x1, y0, y1 = win
            res = max(DEPTH_RES_M, max(x1 - x0, y1 - y0) / 8000.0)
            shp = _shape_for(win)
            f = max(1, int(np.ceil(max((x1 - x0) / shp[1], (y1 - y0) / shp[0]) / res)))
            blk = res * f
            ny, nx = int((y1 - y0) // blk), int((x1 - x0) // blk)
            img = np.full((ny, nx), np.nan, "float32")
            step = max(1, min(ny, 2_000_000 // max(1, nx * f * f)))
            for by in range(0, ny, step):
                bys = min(step, ny - by)
                top = y1 - by * blk
                shape = (bys * f, nx * f)
                xs = x0 + (np.arange(shape[1]) + 0.5) * res
                ys = top - (np.arange(shape[0]) + 0.5) * res
                pm = F.pixel_map(
                    (x0, x0 + shape[1] * res, top - shape[0] * res, top), shape
                )
                zs = np.where(pm >= 0, zs_face[np.maximum(pm, 0)], np.nan)
                ground = bed.dep_on(from_origin(x0, top, res, res), shape)
                X, Y = np.meshgrid(xs, ys)
                with np.errstate(invalid="ignore"):
                    if normally_wet is not None:
                        dry = ~np.asarray(
                            normally_wet(
                                X.ravel(), Y.ravel(), ground.ravel(), c.domain_name
                            ),
                            bool,
                        ).reshape(shape)
                    else:
                        W = np.asarray(
                            usual_water_surface(X.ravel(), Y.ravel(), c.domain_name),
                            "float32",
                        ).reshape(shape)
                        dry = ~np.isfinite(W) | (ground >= W)  # usual_surface == ground
                    depth = np.where(dry, zs - ground, np.nan).astype("float32")
                    depth[~(depth >= WET_ABOVE_MEAN_M)] = np.nan
                n_px += int(np.isfinite(depth).sum())
                with np.errstate(all="ignore"), _quiet():
                    img[by : by + bys] = np.nanmax(
                        depth.reshape(bys, f, nx, f), axis=(1, 3)
                    )
            ext = (x0, x0 + nx * blk, y1 - ny * blk, y1)
            im = ax.imshow(
                img,
                extent=ext,
                origin="upper",
                cmap=cmap_sequential(),
                vmin=DEPTH_RANGE[0],
                vmax=DEPTH_RANGE[1],
                interpolation="nearest",
                zorder=1,
            )
            _frame(ax, name, win, c.outline)
    finally:
        bed.close()
    if im is not None:
        m.colorbar(im, "max flood depth above ground [m]", extend="max")
    _save(m.fig, c.out / "flood_depth.png")
    return {
        "caption": (
            "Maximum flood depth on NORMALLY-DRY land: peak water level (zsmax of the "
            "active face holding each pixel) minus the pixel's ground (the run's merged "
            "subgrid bed). "
            + (
                "A pixel counts as normally dry unless normal_surface.normally_wet says "
                "otherwise: mapped NHD river / lake water, a lake pool, ground below MHHW "
                "(NOAA VDatum), or — where no MHHW is defined — ground below 0 m NAVD88. "
                if normally_wet is not None
                else "A pixel counts as normally dry when its ground stands at or "
                "above the usual water surface there — the normal pool of a non-tidal "
                "lake where one is mapped, else MHHW from NOAA VDatum — or when neither "
                "is defined (nj_sfincs.normal_surface; interim rule: river channels whose "
                "DEM holds the lidar water surface can read as land). "
            )
            + "Normally-wet pixels (ocean, bays, rivers, "
            "lakes, intertidal ground below MHHW) are left blank; the water itself is in "
            "the peak water LEVEL map. "
            f"Computed on a {DEPTH_RES_M:g} m grid (~30 m on the whole-domain panel), "
            f"shown where ≥ {WET_ABOVE_MEAN_M:g} m; each display pixel is the MAX of its "
            f"block. Fixed scale {DEPTH_RANGE[0]:g}–{DEPTH_RANGE[1]:g} m. A display "
            "quantity — scoring (HWM / MOTF) uses levels and extents, unchanged. ⚠️ "
            "Diked land below MHHW within 2 km of the shore (Salem marshes, the "
            "Meadowlands, the Keansburg pocket) reads as normally WET (MHHW is extended "
            "onto land by nearest neighbour, not by connectivity), so its flooding is "
            "left blank here."
        ),
        "dry_rule": "normally_wet"
        if normally_wet is not None
        else "ground>=W (interim)",
    }


def _hwm_tiles(R: Rasters, tile_px: int = 640):
    """``plots._sample_hwm`` (the scorer's sampler) run tile by tile.

    Each mark is sampled in the ONE tile whose core holds its pixel; tiles carry a margin
    wider than the search radius, so every mark sees exactly the window it sees on the
    full raster (the slab is a sub-lattice of the full grid). Returns the SCORED marks
    (q <= 2, on the grid) as ``(hwm, obs, mod_wse, wet, ground)``."""
    import geopandas as gpd

    from .plots import _hwm_path, _sample_hwm
    from .validate import HWM_RADIUS_M
    from .validate.metrics import _clip_to_region

    hwm = _clip_to_region(gpd.read_file(str(_hwm_path(DATA))).to_crs(R.crs))
    n = len(hwm)
    T = R.T
    H, W = R.shape
    rad = int(round(HWM_RADIUS_M / abs(T.a)))
    margin = rad + 4
    obs = hwm["elev_m"].values
    qual = hwm["quality"].values.astype(float)
    mod = np.full(n, np.nan)
    ground = np.full(n, np.nan)
    col = ((hwm.geometry.x.values - T.c) / T.a).astype(int)
    row = ((hwm.geometry.y.values - T.f) / T.e).astype(int)
    on = (row >= 0) & (row < H) & (col >= 0) & (col < W)
    tiles: dict = {}
    for k in np.where(on)[0]:
        tiles.setdefault((row[k] // tile_px, col[k] // tile_px), []).append(k)
    for (tr, tc), ks in tiles.items():
        r0, c0 = max(0, tr * tile_px - margin), max(0, tc * tile_px - margin)
        r1, c1 = (
            min(H, (tr + 1) * tile_px + margin),
            min(W, (tc + 1) * tile_px + margin),
        )
        da_h, da_d = R.tile(r0, r1, c0, c1)
        _hw, _o, mw, _r, _w, _q, gr = _sample_hwm(
            da_h, da_d, DATA, scored_only=False, return_ground=True
        )
        if len(_hw) != n:
            raise RuntimeError("the sampler re-read a different mark set")
        mod[ks], ground[ks] = mw[ks], gr[ks]
    wet = np.isfinite(mod)
    keep = np.isfinite(np.where(wet, mod, ground)) & (
        qual <= 2
    )  # = hwm_metrics' head_s
    return (
        hwm.loc[keep].reset_index(drop=True),
        obs[keep],
        mod[keep],
        wet[keep],
        ground[keep],
    )


def fig_hwm(c: _Ctx) -> tuple[dict, dict]:
    """The residual map and the scatter + basin bars, from ONE sampling."""
    from matplotlib.lines import Line2D

    from .validate import HWM_ESTIMATOR_DEFAULT, HWM_RADIUS_M

    hwm, obs, mod, wet, ground = _hwm_tiles(c.rasters)
    scored = np.where(wet, mod, ground)
    res = scored - obs
    est, rad = HWM_ESTIMATOR_DEFAULT, HWM_RADIUS_M
    label = f"estimator {est}, radius {rad:g} m, q ≤ 2, dry marks scored at ground"
    n = int(len(res))
    rmse = float(np.sqrt(np.mean(res**2))) if n else float("nan")
    bias = float(np.mean(res)) if n else float("nan")
    row = c.row
    selfcheck = {
        "n": n,
        "rmse_m": _jsonable(rmse),
        "bias_m": _jsonable(bias),
        "row_n": row.get("hwm_n_scored"),
        "row_rmse_m": row.get("hwm_rmse_scored_m"),
        "row_bias_m": row.get("hwm_bias_scored_m"),
        "row_estimator": row.get("hwm_estimator"),
        "row_radius_m": row.get("hwm_radius_m"),
    }
    try:
        selfcheck["reproduces_row_4dp"] = bool(
            int(row["hwm_n_scored"]) == n
            and abs(float(row["hwm_rmse_scored_m"]) - rmse) < 5e-5
            and abs(float(row["hwm_bias_scored_m"]) - bias) < 5e-5
            and str(row.get("hwm_estimator")) == est
            and float(row.get("hwm_radius_m")) == float(rad)
        )
    except (KeyError, TypeError, ValueError):
        selfcheck["reproduces_row_4dp"] = None
    lake_ids = set(
        re.findall(
            r"[\w.-]+",
            str(row.get("hwm_lake_outlet_blocked_ids") or "")
            .strip("[]")
            .replace(";", " "),
        )
    )
    ids = hwm["hwm_id"].astype(str).values
    lake = np.isin(ids, list(lake_ids)) if lake_ids else np.zeros(n, bool)
    from .validate.metrics import HWM_MARK_NOTES

    kind = np.array([HWM_MARK_NOTES.get(i, ("", ""))[0] for i in ids])
    qn, ru = kind == "questioned", kind == "runup"
    noted = qn | ru
    keepn = ~noted
    r_ex = res[keepn]
    ex_line = (
        f"without the {int(noted.sum())} noted marks (hollow): n {int(keepn.sum())} · "
        f"RMSE {float(np.sqrt(np.mean(r_ex**2))):.3f} m · bias {float(np.mean(r_ex)):+.3f} m"
        if noted.any() and keepn.any()
        else ""
    )
    note_ids = (
        "questioned: " + ", ".join(sorted(ids[qn])) + "; " if qn.any() else ""
    ) + ("wave run-up (upper bound): " + ", ".join(sorted(ids[ru])) if ru.any() else "")
    _norm_col = cmap_diverging()

    def _rgba(v):
        return _norm_col(
            (np.clip(v, -RESID_LIM, RESID_LIM) + RESID_LIM) / (2 * RESID_LIM)
        )

    def _hollow(ax, x, y, v, k, s):
        for sel, mk in ((k & qn, "o"), (k & ru, "^")):
            if sel.any():
                ax.scatter(
                    x[sel],
                    y[sel],
                    s=s * 1.6,
                    marker=mk,
                    facecolor="none",
                    edgecolor=_rgba(v[sel]),
                    lw=1.6,
                    zorder=6,
                )

    hx, hy = hwm.geometry.x.values, hwm.geometry.y.values
    basin = np.asarray(_domain.classify_hwm_basin(hx, hy))

    # 1 — residual map
    m = _Maps(c.plt, c.windows, c.title("hwm_map"))
    sc = None
    for ax, (name, win) in m.panels():
        _backdrop(ax, c.faces, c.pm(name, win), win)
        x0, x1, y0, y1 = win
        inw = (hx >= x0) & (hx <= x1) & (hy >= y0) & (hy <= y1)
        big = name == "domain"
        s = 14 if big else 34
        _hollow(ax, hx, hy, res, inw, s)
        k = inw & wet & keepn
        sc = ax.scatter(
            hx[k],
            hy[k],
            c=res[k],
            cmap=cmap_diverging(),
            vmin=-RESID_LIM,
            vmax=RESID_LIM,
            s=s,
            edgecolor=INK,
            lw=0.35,
            zorder=5,
        )
        k = inw & ~wet & keepn
        ax.scatter(
            hx[k],
            hy[k],
            c=res[k],
            cmap=cmap_diverging(),
            vmin=-RESID_LIM,
            vmax=RESID_LIM,
            s=s * 1.3,
            marker="X",
            edgecolor=INK,
            lw=0.5,
            zorder=6,
        )
        k = inw & lake
        ax.scatter(
            hx[k], hy[k], s=s * 3.2, facecolor="none", edgecolor=INK, lw=0.8, zorder=7
        )
        _frame(ax, name, win, c.outline)
        ax.text(
            0.98,
            0.02,
            f"{int(inw.sum())} marks",
            transform=ax.transAxes,
            ha="right",
            va="bottom",
            fontsize=7.5,
            color=INK2,
        )
    if sc is not None:
        m.colorbar(sc, "HWM residual, model − measured [m]", extend="both")
    m.fig.legend(
        handles=[
            Line2D(
                [], [], marker="o", ls="", mfc=DIVERGING[2], mec=INK, label="wet mark"
            ),
            Line2D(
                [],
                [],
                marker="X",
                ls="",
                mfc=DIVERGING[2],
                mec=INK,
                label="model dry (scored at ground)",
            ),
            Line2D(
                [],
                [],
                marker="o",
                ls="",
                mfc="none",
                mec=INK,
                ms=9,
                label="lake_outlet_blocked",
            ),
            Line2D(
                [],
                [],
                marker="o",
                ls="",
                mfc="none",
                mec=INK,
                mew=1.4,
                label="questioned mark (hollow)",
            ),
            Line2D(
                [],
                [],
                marker="^",
                ls="",
                mfc="none",
                mec=INK,
                mew=1.4,
                label="wave run-up mark (upper bound)",
            ),
        ],
        loc="outside lower left",
        ncols=5,
        fontsize=8,
    )
    _save(m.fig, c.out / "hwm_map.png")
    cap_map = {
        "caption": (
            f"HWM residuals (model − measured) for the {n} scored marks — {label}; the "
            "sampler is the scorer's (plots._sample_hwm → validate). Orange = model low, "
            f"purple = high, fixed ±{RESID_LIM:g} m; ✕ = model dry at the mark; ring = "
            "flagged lake_outlet_blocked (FINDINGS part 4 (h)), never dropped; hollow = a "
            f"mark noted against its USGS STN record ({note_ids or 'none'}), kept in the "
            f"score. Pooled: RMSE {rmse:.3f} m, bias {bias:+.3f} m ({label})"
            + (f"; {ex_line}." if ex_line else ".")
        ),
        "selfcheck": selfcheck,
    }

    # 2 — scatter + basin bars
    plt = c.plt
    fig, (a1, a2) = plt.subplots(
        1,
        2,
        figsize=(14.5, 6.6),
        layout="constrained",
        gridspec_kw={"width_ratios": [1, 1.25]},
    )
    fig.suptitle(c.title("hwm_summary"), fontsize=10.5, x=0.01, ha="left")
    lo = float(np.nanmin(np.r_[obs, scored, 0.5])) - 0.2
    hi = float(np.nanmax(np.r_[obs, scored, 4.0])) + 0.2
    a1.plot([lo, hi], [lo, hi], color=HAIR, lw=0.8, zorder=1)
    for off in (-0.5, 0.5):
        a1.plot([lo, hi], [lo + off, hi + off], color=HAIR, lw=0.5, ls=":", zorder=1)
    _hollow(a1, obs, scored, res, np.ones(n, bool), 26)
    a1.scatter(
        obs[wet & keepn],
        scored[wet & keepn],
        c=res[wet & keepn],
        cmap=cmap_diverging(),
        vmin=-RESID_LIM,
        vmax=RESID_LIM,
        s=26,
        edgecolor=INK,
        lw=0.35,
        zorder=3,
    )
    a1.scatter(
        obs[~wet & keepn],
        scored[~wet & keepn],
        c=res[~wet & keepn],
        cmap=cmap_diverging(),
        vmin=-RESID_LIM,
        vmax=RESID_LIM,
        s=34,
        marker="X",
        edgecolor=INK,
        lw=0.5,
        zorder=4,
    )
    a1.scatter(
        obs[lake],
        scored[lake],
        s=110,
        facecolor="none",
        edgecolor=INK,
        lw=0.8,
        zorder=5,
    )
    a1.set_xlim(lo, hi)
    a1.set_ylim(lo, hi)
    a1.set_aspect("equal")
    a1.grid(True)
    a1.set_xlabel("measured HWM elevation [m NAVD88]")
    a1.set_ylabel("modelled level at the mark [m NAVD88]")
    a1.set_title(
        f"n {n} · RMSE {rmse:.3f} m · bias {bias:+.3f} m · within ±0.5 m "
        f"{np.mean(np.abs(res) < 0.5):.0%}\n{label}"
        + (f"\n{ex_line}" if ex_line else ""),
        fontsize=8.5,
        loc="left",
    )
    names = [b for b in _domain.hwm_basin_names() if (basin == b).any()]
    if (basin == "unassigned").any():
        names.append("unassigned")
    stats = []
    for b in names:
        r = res[basin == b]
        stats.append(
            (
                b,
                r.size,
                float(r.mean()),
                float(np.sqrt(np.mean(r**2))),
                int((~wet[basin == b]).sum()),
            )
        )
    stats.sort(key=lambda t: t[2])
    yy = np.arange(len(stats))
    biases = np.array([s[2] for s in stats])
    rmses = np.array([s[3] for s in stats])
    cols = [
        cmap_diverging()(
            (np.clip(v, -RESID_LIM, RESID_LIM) + RESID_LIM) / (2 * RESID_LIM)
        )
        for v in biases
    ]
    a2.barh(yy, biases, color=cols, height=0.62, edgecolor=PAPER, lw=1.0, zorder=3)
    a2.scatter(rmses, yy, marker="|", s=90, color=INK, zorder=4, label="RMSE")
    a2.axvline(0, color=INK2, lw=0.7)
    a2.set_yticks(
        yy,
        [
            f"{s[0].replace('_', ' ')}  (n {s[1]}"
            + (f", {s[4]} dry" if s[4] else "")
            + ")"
            for s in stats
        ],
        fontsize=7.5,
    )
    a2.set_xlabel("per-basin bias (bars) and RMSE (|) [m]")
    a2.grid(True, axis="x")
    lim = (
        max(1.0, float(np.nanmax(np.abs(np.r_[biases, rmses]))) * 1.08) if stats else 1
    )
    a2.set_xlim(-lim, lim)
    a2.legend(loc="lower right", fontsize=7.5)
    a2.set_title(f"by basin (Domain.hwm_rules) — {label}", fontsize=8.5, loc="left")
    _save(fig, c.out / "hwm_summary.png")
    cap_sum = {
        "caption": (
            f"Left: measured vs modelled level at each scored mark ({label}); dotted = "
            "±0.5 m; ✕ = model dry (scored at the lowest ground in the window); ring = "
            f"lake_outlet_blocked; hollow ○ questioned / △ wave run-up ({note_ids or 'none'})"
            ", kept in the score. Right: per-basin bias (bar) and RMSE (tick), basins "
            "from Domain.hwm_rules (first match wins), sorted by bias."
        ),
        "basins": [
            {"basin": s[0], "n": s[1], "bias_m": s[2], "rmse_m": s[3], "n_dry": s[4]}
            for s in stats
        ],
        "selfcheck": selfcheck,
    }
    return cap_map, cap_sum


def fig_motf(c: _Ctx) -> dict:
    import rasterio
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch

    from .validate import DEPTH_MIN, simulated_mask
    from .validate.metrics import motf_exclude_mask, motf_path

    R = c.rasters
    with rasterio.open(str(motf_path(DATA))) as r:
        motf, mtf, m_nd = r.read(1), r.transform, r.nodata
    mh, mw = motf.shape
    Xc = mtf.c + (np.arange(mw) + 0.5) * mtf.a
    Yc = mtf.f + (np.arange(mh) + 0.5) * mtf.e
    T = R.T
    H, W = R.shape
    mc = np.clip(((Xc - T.c) / T.a).astype(int), 0, W - 1)
    mr = np.clip(((Yc - T.f) / T.e).astype(int), 0, H - 1)
    # the scorer's nearest gather at MOTF centres, strip by strip of MOTF rows
    dep_at = np.empty(motf.shape, "float32")
    h_at = np.empty(motf.shape, "float32")
    c_lo, c_hi = int(mc.min()), int(mc.max()) + 1
    for i0 in range(0, mh, 256):
        rr = mr[i0 : i0 + 256]
        a, b = int(rr.min()), int(rr.max()) + 1
        ix = np.ix_(rr - a, mc - c_lo)
        h_at[i0 : i0 + 256] = R.hmax(a, b, c_lo, c_hi)[ix]
        dep_at[i0 : i0 + 256] = R.dep(a, b, c_lo, c_hi)[ix]
    motf_wet = motf == 1
    mod_wet = (h_at >= DEPTH_MIN) & np.isfinite(h_at)
    del h_at
    land_in = (
        (motf != m_nd) & (dep_at > 0.0) & simulated_mask(c.run_dir, motf.shape, mtf)
    )
    del dep_at
    excl = motf_exclude_mask(motf.shape, mtf)
    km2 = abs(mtf.a * mtf.e) / 1e6
    km2_excl = 0.0 if excl is None else float((land_in & excl).sum() * km2)
    if excl is not None:
        land_in &= ~excl
    cat = np.zeros(motf.shape, "uint8")
    cat[motf_wet & mod_wet & land_in] = 1
    cat[motf_wet & ~mod_wet & land_in] = 2
    cat[~motf_wet & mod_wet & land_in] = 3
    del mod_wet, land_in, motf_wet
    nh, nm, nf = (int((cat == k).sum()) for k in (1, 2, 3))
    csi = nh / (nh + nm + nf) if (nh + nm + nf) else float("nan")
    pod = nh / (nh + nm) if (nh + nm) else float("nan")
    far = nf / (nh + nf) if (nh + nf) else float("nan")
    row = c.row
    selfcheck = {
        "csi": csi,
        "pod": pod,
        "far": far,
        "km2_excluded": km2_excl,
        "row_csi": row.get("motf_csi"),
        "row_pod": row.get("motf_pod"),
        "row_far": row.get("motf_far"),
        "row_km2_excluded_boxes": row.get("motf_km2_excluded_boxes"),
    }
    try:
        selfcheck["reproduces_row_4dp"] = bool(
            abs(float(row["motf_csi"]) - csi) < 5e-5
            and abs(float(row["motf_pod"]) - pod) < 5e-5
            and abs(float(row["motf_far"]) - far) < 5e-5
        )
    except (KeyError, TypeError, ValueError):
        selfcheck["reproduces_row_4dp"] = None
    cmap = ListedColormap([(0, 0, 0, 0), *MOTF_COLORS])
    m = _Maps(c.plt, c.windows, c.title("motf"))
    for ax, (name, win) in m.panels():
        _backdrop(ax, c.faces, c.pm(name, win), win)
        img, ext = _majority(cat, mtf, win, _shape_for(win))
        if img is not None:
            ax.imshow(
                img,
                extent=ext,
                origin="upper",
                cmap=cmap,
                vmin=0,
                vmax=3,
                interpolation="nearest",
                zorder=1,
            )
        _frame(ax, name, win, c.outline)
    m.fig.legend(
        handles=[
            Patch(color=MOTF_COLORS[0], label=f"hit ({nh * km2:.1f} km²)"),
            Patch(
                color=MOTF_COLORS[1],
                label=f"miss: MOTF wet, model dry ({nm * km2:.1f} km²)",
            ),
            Patch(
                color=MOTF_COLORS[2],
                label=f"false alarm: model wet, MOTF dry ({nf * km2:.1f} km²)",
            ),
        ],
        loc="outside lower left",
        ncols=3,
        fontsize=8,
    )
    waves = (
        ""
        if c.card["config"]["waves_on"]
        else "  ·  waves OFF (extent_admissible=False)"
    )
    m.fig.suptitle(
        c.title("motf") + f"\nCSI {csi:.3f}  ·  POD {pod:.3f}  ·  FAR {far:.3f}  ·  "
        f"motf_km2_excluded_boxes "
        f"{float(row.get('motf_km2_excluded_boxes') or km2_excl):,.1f} km²{waves}",
        fontsize=10.5,
        color=INK,
        x=0.01,
        ha="left",
    )
    _save(m.fig, c.out / "motf.png")
    return {
        "caption": (
            f"Modelled flood (depth ≥ {DEPTH_MIN} m) vs the FEMA MOTF surge extent on "
            "normally-dry, simulated, sheet-valid land — the scorer's screen "
            "(motf_metrics). CSI {:.3f} · POD {:.3f} · FAR {:.3f}; "
            "motf_km2_excluded_boxes = {:,.1f} km² of land the sheet cannot adjudicate "
            "(quote it beside the CSI). Each display pixel is the majority category of "
            "its block of 15 m MOTF cells. ⚠️ MOTF shares provenance with the HWMs and "
            "POD rewards over-flooding: read the CSI, beside the HWM residuals.".format(
                csi, pod, far, float(row.get("motf_km2_excluded_boxes") or km2_excl)
            )
            + (
                ""
                if c.card["config"]["waves_on"]
                else " Waves OFF: kept, flagged extent_admissible=False (FINDINGS §4)."
            )
        ),
        "selfcheck": selfcheck,
    }


def _majority(cat, T, win, shape):
    """Majority non-zero category per display block (0 where a block has none)."""
    H, W = cat.shape
    counts = []
    img = None
    for k in (1, 2, 3):

        def vals(ra, rb, ca, cb, k=k):
            return (cat[ra:rb, ca:cb] == k).astype("float32")

        cnt, ext = _block((H, W), T, win, shape, vals, reduce="sum")
        if cnt is None:
            return None, None
        counts.append(cnt)
    st = np.stack(counts)
    img = np.where(st.max(0) > 0, st.argmax(0) + 1, 0).astype("uint8")
    return img, ext


def fig_gauges(c: _Ctx) -> tuple[dict, dict]:
    import pandas as pd

    from .validate import gauge_series_frame

    gauges = [g for g in c.dom.obs_gauges if g.obs_file and g.obs_station is not None]
    if not gauges:
        return ({"skipped": "the domain declares no scoreable gauges"},) * 2
    row = c.row
    plt = c.plt
    ncol = 5
    nrow = int(np.ceil(len(gauges) / ncol))
    fig, axs = plt.subplots(
        nrow,
        ncol,
        figsize=(15.5, 1.95 * nrow + 0.6),
        squeeze=False,
        layout="constrained",
        sharex=True,
    )
    fig.suptitle(c.title("gauges"), fontsize=10.5, x=0.01, ha="left")
    t0, t1 = pd.Timestamp("2012-10-28"), pd.Timestamp("2012-10-31")
    failures = []
    for ax, g in zip(axs.ravel(), gauges):
        try:
            df = gauge_series_frame(c.run_dir, g.name)
        except Exception as e:  # noqa: BLE001 — one bad gauge must not kill the figure
            df = None
            failures.append(f"{g.name}: {e}")
        if df is not None and not df.empty:
            ax.plot(df.index, df["obs"], color=INK, lw=1.1, label="measured")
            ax.plot(df.index, df["mod"], color=MOTF_COLORS[0], lw=1.0, label="model")
        if g.record_ends:
            ax.axvline(
                pd.Timestamp(g.record_ends), color=MOTF_COLORS[1], lw=0.8, ls="--"
            )
        n = g.name
        e = row.get(f"peak_err_{n}_m")
        lag = row.get(f"peak_lag_{n}_min")
        ep = row.get(f"peak_err_prefail_{n}_m")
        bits = []
        if _finite(e):
            bits.append(f"peak {float(e):+.2f} m")
        if _finite(lag):
            bits.append(f"lag {float(lag):+.0f} min")
        if _finite(ep):
            bits.append(f"pre-fail {float(ep):+.2f} m")
        ax.set_title(n.replace("_", " "), fontsize=7.5, loc="left", color=INK)
        ax.text(
            0.02,
            0.97,
            " · ".join(bits) or "no peak score",
            transform=ax.transAxes,
            fontsize=6.5,
            va="top",
            color=INK2,
        )
        ax.grid(True)
        ax.tick_params(labelsize=6.5)
        ax.set_xlim(t0, t1)
    for ax in axs.ravel()[len(gauges) :]:
        ax.axis("off")
    axs.ravel()[0].legend(fontsize=6.5, loc="lower left")
    for ax in axs[-1]:
        for lbl in ax.get_xticklabels():
            lbl.set_rotation(25)
            lbl.set_ha("right")
    _save(fig, c.out / "gauges.png")
    cap1 = {
        "caption": (
            "Measured (ink) vs modelled (blue) water level [m NAVD88] at every scoreable "
            "gauge in Domain.obs_gauges (validate.gauge_series_frame: obs interpolated "
            "onto the model clock, never across a gap). Dashed orange = the gauge died; "
            "right of it the trace is model-only and the measured top is a floor. Peak "
            "error / lag from metrics.csv (peak_err_* / peak_lag_*, peaks after "
            "2012-10-29); 'pre-fail' = both sides truncated at the failure."
        ),
        "failures": failures,
    }
    # peaks + timing
    rows = []
    for g in gauges:
        n = g.name
        e, ep = row.get(f"peak_err_{n}_m"), row.get(f"peak_err_prefail_{n}_m")
        lag = row.get(f"peak_lag_{n}_min")
        rows.append((n, e if _finite(e) else ep, _finite(ep) and not _finite(e), lag))
    fig, (a1, a2) = plt.subplots(
        1, 2, figsize=(13.5, 0.2 * len(rows) + 1.6), layout="constrained", sharey=True
    )
    fig.suptitle(c.title("gauge_peaks"), fontsize=10.5, x=0.01, ha="left")
    yy = np.arange(len(rows))[::-1]
    for y, (n, e, pre, lag) in zip(yy, rows):
        if _finite(e):
            a1.plot([0, float(e)], [y, y], color=HAIR, lw=0.8, zorder=1)
            a1.scatter(
                [float(e)],
                [y],
                s=26,
                zorder=3,
                facecolor="none" if pre else MOTF_COLORS[0],
                edgecolor=MOTF_COLORS[0],
                lw=1.0,
            )
        if _finite(lag):
            a2.plot([0, float(lag)], [y, y], color=HAIR, lw=0.8, zorder=1)
            a2.scatter([float(lag)], [y], s=26, color=MOTF_COLORS[0], zorder=3)
    a1.set_yticks(yy, [r[0].replace("_", " ") for r in rows], fontsize=7)
    a1.axvline(0, color=INK2, lw=0.7)
    a2.axvline(0, color=INK2, lw=0.7)
    a1.set_xlim(-1.5, 1.5)
    a2.set_xlim(-240, 240)
    a1.set_xlabel("peak error, model − measured [m]   (hollow = pre-failure peak)")
    a2.set_xlabel("peak timing, model − measured [min]   (+ = model late)")
    for a in (a1, a2):
        a.grid(True, axis="x")
    _save(fig, c.out / "gauge_peaks.png")
    cap2 = {
        "caption": (
            "Peak error and timing per gauge, read from metrics.csv (validate."
            "gauge_peak_metrics; peaks after 2012-10-29). Hollow = gauge died mid-storm: "
            "the PRE-FAILURE comparison, never ranked across a timing-shifted arm. "
            "Fixed axes ±1.5 m and ±240 min (off-scale values sit at the edge)."
        )
    }
    return cap1, cap2


# ═════════════════════════════════════════════════════════════════════════════════════
# the driver
# ═════════════════════════════════════════════════════════════════════════════════════


def _try(entries: dict, key: str, fn, *a):
    """Run one figure; a failure is recorded on its entry, never raised."""
    t = time.time()
    try:
        res = fn(*a)
    except Exception as e:  # noqa: BLE001 — one figure must not cost the others
        res = {
            "error": f"{type(e).__name__}: {e}",
            "traceback": traceback.format_exc()[-2000:],
        }
        print(f"[gallery] ⚠️ {key} failed: {res['error']}", flush=True)
    res = res if isinstance(res, tuple) else (res,)
    keys = {"hwm": ("hwm_map", "hwm_summary"), "gauges": ("gauges", "gauge_peaks")}.get(
        key, (key,)
    )
    for k, r in zip(keys, res * (len(keys) if len(res) == 1 else 1)):
        e = dict(r)
        e.setdefault("seconds", round(time.time() - t, 1))
        entries[k] = e
    print(f"[gallery] {key}: {time.time() - t:.0f} s", flush=True)


def build_arm_figures(
    domain_name: str,
    arm: str,
    out_dir: Path | None = None,
    only: tuple[str, ...] | None = None,
) -> Path:
    """The standard figure set for ONE finished arm → ``<run>/gallery/`` + manifest.

    Sets ``NJ_DOMAIN`` when it is unset, refuses when it names another domain. Returns
    the manifest path. A failing figure is recorded in the manifest and the rest are
    still drawn; only a missing run dir raises."""
    have = os.environ.get("NJ_DOMAIN")
    if have and have != domain_name:
        raise ValueError(f"NJ_DOMAIN={have!r} but asked for domain {domain_name!r}")
    os.environ["NJ_DOMAIN"] = domain_name
    import nj_sfincs  # noqa: F401 — pyproj before hydromt

    t_start = time.time()
    run_dir = exp_root() / arm
    if not (run_dir / "sfincs.inp").is_file():
        raise FileNotFoundError(f"no run dir {run_dir}")
    out = Path(out_dir) if out_dir else run_dir / GALLERY
    out.mkdir(parents=True, exist_ok=True)
    row = metrics_row(domain_name, arm)
    card = run_card(domain_name, arm, run_dir, row)
    ref = reference_arm(domain_name, arm)
    ref_dir = exp_root() / ref
    ref_row = metrics_row(domain_name, ref) if ref != arm else row
    facts = {
        "audit_whole": card["audit"]["whole"],
        "audit_problems": card["audit"]["problems"],
        "sealed": card["sealed"],
        "waves_on": card["config"]["waves_on"],
        "rain_on": card["config"]["rain_on"],
        "resumes": card["restart"]["resumes"],
        "soil_reset": card["restart"]["soil_reset"],
        "engine_seed": card["labels"].get("engine_seed"),
        "engine": card["labels"].get("engine"),
        "snapwave_direction": card["labels"].get("snapwave_direction"),
        "extent_admissible": (row or {}).get("extent_admissible"),
        "has_metrics_row": row is not None,
        "hwm_n_scored": (row or {}).get("hwm_n_scored"),
        "ref_arm": ref,
        "ref_hwm_n_scored": (ref_row or {}).get("hwm_n_scored"),
        "floodmap_fresh": gallery_tif_fresh(run_dir, gallery_tif(domain_name, arm)),
    }
    entries: dict = {}
    want = set(only) if only else {k for k, _ in FIGURES}

    def on(*keys):
        return any(k in want for k in keys)

    if card["audit"]["whole"] is not None:
        c = _Ctx(domain_name, arm, run_dir, out, row, card, ref, ref_dir)
        if on("zsmax"):
            _try(entries, "zsmax", fig_zsmax, c)
        if on("dzsmax"):
            _try(entries, "dzsmax", fig_dzsmax, c)
        if on("hm0"):
            _try(entries, "hm0", fig_hm0, c)
        if on("flood_depth"):
            _try(entries, "flood_depth", fig_flood_depth, c)
        if on("hwm_map", "hwm_summary", "motf"):
            gtif = gallery_tif(domain_name, arm)
            if not gallery_tif_fresh(run_dir, gtif):
                for k in ("hwm_map", "hwm_summary", "motf"):
                    entries[k] = {
                        "skipped": f"{gtif.name} missing or older than the run's "
                        "floodmap cache — run --validate-only (not re-downscaled here)"
                    }
            else:
                c.rasters = Rasters(run_dir, gtif)
                try:
                    if on("hwm_map", "hwm_summary"):
                        _try(entries, "hwm", fig_hwm, c)
                    if on("motf"):
                        _try(entries, "motf", fig_motf, c)
                finally:
                    c.rasters.close()
                    c.rasters = None
        if on("gauges", "gauge_peaks"):
            _try(entries, "gauges", fig_gauges, c)
    # manifest: figures in the fixed order; carry forward entries this call did not redo
    old = {}
    mp = out / MANIFEST
    if only and mp.is_file():
        try:
            old = {f["key"]: f for f in json.loads(mp.read_text()).get("figures", [])}
        except (OSError, ValueError):
            old = {}
    manifest = assemble_manifest(
        domain_name,
        arm,
        ref,
        card,
        facts,
        entries,
        row,
        out,
        old,
        seconds=time.time() - t_start,
    )
    figures, flags = manifest["figures"], manifest["flags"]
    # clean as you go: a PNG no figure refers to is a stale figure (with --only, the
    # carried-forward entries are in `figures`, so their PNGs are kept)
    keep = {f.get("file") for f in figures}
    for png in out.glob("*.png"):
        if png.name not in keep:
            png.unlink()
    tmp = mp.with_suffix(".partial.json")
    tmp.write_text(json.dumps(manifest, indent=1, default=str))
    os.replace(tmp, mp)
    print(
        f"[gallery] {domain_name}/{arm}: {len(figures)} figures, "
        f"{len(flags)} flags, {manifest['seconds']:.0f} s, peak RSS "
        f"{manifest['peak_rss_gb']} GB → {mp}",
        flush=True,
    )
    return mp


def assemble_manifest(
    domain_name: str,
    arm: str,
    ref: str,
    card: dict,
    facts: dict,
    entries: dict,
    row: dict | None,
    out: Path,
    old: dict | None = None,
    seconds: float = 0.0,
    windows: list | None = None,
) -> dict:
    """The manifest dict: figures in the fixed ``FIGURES`` order (``old`` entries carried
    forward for figures this call did not redraw), flags = ``compute_flags(facts)`` plus
    one per failed self-check / figure. ``file`` is set only where the PNG exists."""
    old = old or {}
    figures = []
    for key, title in FIGURES:
        e = entries.get(key)
        if e is None and key in old:
            figures.append(old[key])
            continue
        if e is None:
            continue
        f = {"key": key, "title": title, **{k: _jsonable_deep(v) for k, v in e.items()}}
        png = out / f"{key}.png"
        if "error" not in e and "skipped" not in e and png.is_file():
            f["file"] = png.name
        figures.append(f)
    flags = compute_flags(facts)
    for f in figures:
        sc = f.get("selfcheck") or {}
        if sc.get("reproduces_row_4dp") is False:
            flags.append(
                _flag(
                    f"selfcheck_{f['key']}",
                    "caution",
                    f"{f['title']}: the figure's own numbers do not reproduce the metrics.csv "
                    "row to 4 dp — the row may predate a re-score; the row is the authority.",
                )
            )
        if f.get("error"):
            flags.append(
                _flag(
                    f"figure_failed_{f['key']}",
                    "info",
                    f"{f['title']} failed to draw: {f['error']}",
                )
            )
    manifest = {
        "schema": SCHEMA,
        "domain": domain_name,
        "arm": arm,
        "reference_arm": ref,
        "built": datetime.now().isoformat(timespec="seconds"),
        "host": os.uname().nodename,
        "seconds": round(seconds, 1),
        "peak_rss_gb": round(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6, 2
        ),
        "windows": [
            {"name": n, "extent": list(w)} for n, w in (windows or gallery_windows())
        ],
        "scales": {
            "zsmax_m": ZSMAX_RANGE,
            "flood_depth_m": DEPTH_RANGE,
            "dzsmax_m": DZS_LIM,
            "hwm_resid_m": RESID_LIM,
            "hm0_m": HM0_RANGE,
        },
        "card": _jsonable_deep(card),
        "flags": flags,
        "figures": figures,
        "metrics_row": _jsonable_deep(row) if row else None,
    }
    return manifest


def _jsonable_deep(v):
    if isinstance(v, dict):
        return {str(k): _jsonable_deep(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable_deep(x) for x in v]
    return _jsonable(v)


def build_in_subprocess(
    domain_name: str,
    arm: str,
    timeout: float | None = None,
    extra: list[str] | None = None,
) -> int:
    """``python -m nj_sfincs.gallery <arm>`` in a child process (its rasters die with
    it). Returns the exit code; never raises on a figure failure."""
    env = dict(os.environ, NJ_DOMAIN=domain_name, PYTHONPATH=str(ROOT))
    cmd = [sys.executable, "-m", "nj_sfincs.gallery", arm, *(extra or [])]
    return subprocess.run(
        cmd, env=env, cwd=str(ROOT), timeout=timeout, check=False
    ).returncode


def _main(argv=None) -> int:
    import argparse

    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("arm")
    p.add_argument("--domain", default=os.environ.get("NJ_DOMAIN"))
    p.add_argument("--out", default=None, help="output dir (default <run>/gallery)")
    p.add_argument("--only", default=None, help="comma-separated figure keys")
    a = p.parse_args(argv)
    if not a.domain:
        p.error("set NJ_DOMAIN or pass --domain")
    only = tuple(s.strip() for s in a.only.split(",")) if a.only else None
    build_arm_figures(a.domain, a.arm, a.out, only=only)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
