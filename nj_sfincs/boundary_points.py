"""Per-SUPPORT-POINT water-level boundary offsets (``Experiment.boundary_point_offsets``, 2026-11-24).

A CONSTANT (m, whole series) added to each support point of the forced water-level line, read from a CSV with one
row per point. It generalises ``Experiment.boundary_arm_offsets`` (one constant per arm, ``model.py``), which REFUSES
whenever a point also forces another arm's cells; on nj2 that is every sea arm (logs/csi_dip_design_2026-11-22/
README.md "Pre-storm offset arm"). Here a point's offset is whatever the table says, so a smooth along-line profile
(an SLR gradient, a gauge-bias profile) needs no arm bookkeeping. Which arms read each moved point (the engine's
two-nearest rule) is RECORDED in the sidecar, not refused: a leak into a neighbouring arm's cells is deliberate.

Uses: per-gauge SLR (``logs/slr_spatial_2026-11-24/``: the STAP gauge projections vs Atlantic City, interpolated
along the line) and the pre-storm diagnostic (offset = the observed − forced quiet-window mean, per point).

THE TABLE (CSV, one row per support point):

* coordinates: ``lon`` + ``lat`` (EPSG:4326), or ``x`` + ``y`` in the boundary file's CRS. Points are matched by
  COORDINATE (nearest row within ``tol_m``), never by position or by the file's ``stations`` index, which is just
  0..n-1: Sandy's NACCS line has 244 points on nj2, Irene's 240.
* the offset column named by the arm (metres; several columns may sit side by side, e.g. 2050 and 2100).
* optional ``sp`` (the NACCS save-point id) and ``arm``: copied into the record, not used for matching.

REFUSES (``SystemExit``): a boundary point with no row within ``tol_m``; two points on one row; a non-finite or
missing offset; table rows left over (a different line) unless the arm declares ``extra_rows_ok``. A table of zeros
leaves the boundary file untouched (byte-identical) and still writes the sidecar.

Applied LAST to the WRITTEN ``sfincs_netbndbzsbzifile.nc`` (``run_experiments.prepare_experiment``), after
``finalize``, ``calm.apply`` (which replaces the boundary of a calm arm) and ``apply_cold_start``, so it sits on top of
``boundary_arm_offsets`` and of a calm arm's tide file. The start is NOT changed: a calm tide arm keeps its
connected start at ``level_m`` (a cm-level table against a 2.5-day spin-up).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

import numpy as np

from .config import BoundaryPointOffsets

BND_FILE = "sfincs_netbndbzsbzifile.nc"
#: The sidecar written into the staged dir (scripts/retire_arm.py KEEP_FILES).
META = "boundary_point_offsets.json"


def _file_crs(nc) -> "object | None":
    """The boundary file's CRS (its ``spatial_ref`` grid-mapping variable), or None."""
    from pyproj import CRS

    if "spatial_ref" not in nc.variables:
        return None
    v = nc["spatial_ref"]
    for key in ("crs_wkt", "spatial_ref"):
        if key in v.ncattrs():
            return CRS.from_wkt(v.getncattr(key))
    return None


def read_table(spec: BoundaryPointOffsets, crs) -> dict:
    """The table's points in ``crs`` + the offset column. Refuses a missing column or a non-finite offset."""
    import pandas as pd

    path = Path(spec.table)
    if not path.is_file():
        raise SystemExit(f"boundary_point_offsets: no table at {path}")
    t = pd.read_csv(path)
    if spec.column not in t:
        raise SystemExit(
            f"boundary_point_offsets: {path.name} has no column '{spec.column}' ({list(t.columns)})"
        )
    off = pd.to_numeric(t[spec.column], errors="coerce").to_numpy(float)
    if not np.isfinite(off).all():
        bad = np.flatnonzero(~np.isfinite(off))[:10].tolist()
        raise SystemExit(
            f"boundary_point_offsets: {path.name} column '{spec.column}' is not finite on rows {bad}"
        )
    if {"x", "y"} <= set(t.columns):
        tx, ty = t["x"].to_numpy(float), t["y"].to_numpy(float)
    elif {"lon", "lat"} <= set(t.columns):
        if crs is None:
            raise SystemExit(
                "boundary_point_offsets: lon / lat table but the boundary file carries no CRS"
            )
        from pyproj import Transformer

        tr = Transformer.from_crs(4326, crs, always_xy=True)
        tx, ty = tr.transform(t["lon"].to_numpy(float), t["lat"].to_numpy(float))
        tx, ty = np.asarray(tx, float), np.asarray(ty, float)
    else:
        raise SystemExit(
            f"boundary_point_offsets: {path.name} needs lon + lat (EPSG:4326) or x + y (model CRS) columns"
        )
    return {
        "x": tx,
        "y": ty,
        "offset": off,
        "sp": t["sp"].tolist() if "sp" in t else [None] * len(t),
        "arm": t["arm"].astype(str).tolist() if "arm" in t else [None] * len(t),
        "md5": hashlib.md5(path.read_bytes()).hexdigest(),
    }


def match_points(
    px, py, tx, ty, tol_m: float, extra_rows_ok: bool = False
) -> np.ndarray:
    """Row of the table for each support point, by nearest coordinate. Refuses loudly (see the module doc)."""
    px, py = np.asarray(px, float), np.asarray(py, float)
    tx, ty = np.asarray(tx, float), np.asarray(ty, float)
    if tx.size == 0:
        raise SystemExit("boundary_point_offsets: empty table")
    if tx.size != px.size and not extra_rows_ok:
        raise SystemExit(
            f"boundary_point_offsets: the table has {tx.size} rows, the staged boundary {px.size} support "
            "points — a table for ANOTHER forced line (Sandy's nj2 NACCS line has 244 points, Irene's 240). "
            "Build a table for this line, or declare extra_rows_ok=True if it is a deliberate superset."
        )
    d = np.hypot(px[:, None] - tx[None, :], py[:, None] - ty[None, :])
    row = np.argmin(d, axis=1)
    dist = d[np.arange(px.size), row]
    far = np.flatnonzero(dist > tol_m)
    if far.size:
        raise SystemExit(
            f"boundary_point_offsets: {far.size} of {px.size} support point(s) have no table row within "
            f"{tol_m} m (first: point {int(far[0])} at ({px[far[0]]:.1f}, {py[far[0]]:.1f}), nearest row "
            f"{dist[far[0]]:.1f} m away)"
        )
    u, n = np.unique(row, return_counts=True)
    if (n > 1).any():
        raise SystemExit(
            f"boundary_point_offsets: table row(s) {u[n > 1].tolist()} match more than one support point"
        )
    if tx.size != px.size:
        print(
            f"[bnd] boundary_point_offsets: {tx.size - px.size} table row(s) unused (extra_rows_ok)",
            flush=True,
        )
    return row


def point_arms(cell_x, cell_y, cell_arm, pt_x, pt_y) -> list[list[str]]:
    """For each support point, the arms whose ``mask==2`` cells read it (the engine's two-nearest rule,
    ``model.boundary_arm_support_points``). ``[]`` = a point no cell reads."""
    cell_x, cell_y = np.asarray(cell_x, float), np.asarray(cell_y, float)
    cell_arm = np.asarray(cell_arm, object)
    pt_x, pt_y = np.asarray(pt_x, float), np.asarray(pt_y, float)
    out: list[set] = [set() for _ in range(pt_x.size)]
    if cell_x.size == 0 or pt_x.size == 0:
        return [[] for _ in range(pt_x.size)]
    k = min(2, pt_x.size)
    d = np.hypot(cell_x[:, None] - pt_x[None, :], cell_y[:, None] - pt_y[None, :])
    two = np.argsort(d, axis=1, kind="stable")[:, :k]
    for c in range(cell_x.size):
        for p in two[c]:
            out[int(p)].add(str(cell_arm[c]) or "(no arm)")
    return [sorted(s) for s in out]


def _staged_point_arms(model_dir: Path, px, py) -> list[list[str]] | None:
    """:func:`point_arms` on a staged dir (``sfincs.nc`` mask + face centres, ``Domain.boundary_arms``); None when
    the dir has no ``sfincs.nc`` or no domain is active."""
    import netCDF4

    from . import domain as _domain

    f = Path(model_dir) / "sfincs.nc"
    if not f.exists():
        return None
    try:
        arms = [a for a in _domain.active().boundary_arms if a.btype == "waterlevel"]
    except Exception:  # noqa: BLE001  (no NJ_DOMAIN: the record just lacks arms)
        return None
    with netCDF4.Dataset(f) as s:
        mask = np.asarray(s["mask"][:])
        b = np.flatnonzero(mask == 2)
        cx = np.asarray(s["mesh2d_face_x"][:])[b]
        cy = np.asarray(s["mesh2d_face_y"][:])[b]
    cell_arm = np.full(b.size, "", object)
    for a in arms:
        cell_arm[a.contains(cx, cy)] = a.name
    return point_arms(cx, cy, cell_arm, px, py)


def _summary(vals: np.ndarray) -> dict:
    return {
        "n": int(vals.size),
        "min_m": round(float(vals.min()), 4),
        "max_m": round(float(vals.max()), 4),
        "mean_m": round(float(vals.mean()), 4),
    }


def apply(model_dir: Path | str, spec: BoundaryPointOffsets) -> dict:
    """Add the table's offsets to the staged boundary file (atomic: copy, edit ``zs``, replace), write the
    sidecar + a ``provenance.txt`` line. Returns the record."""
    import netCDF4

    d = Path(model_dir)
    f = d / BND_FILE
    if not f.exists():
        raise SystemExit(
            f"boundary_point_offsets set but {d.name} has no {BND_FILE} (no water-level boundary)"
        )
    with netCDF4.Dataset(f) as nc:
        if "zs" not in nc.variables or nc["zs"].dimensions[-1] != "stations":
            raise SystemExit(f"boundary_point_offsets: unexpected {BND_FILE} layout")
        px = np.asarray(nc["x"][:], float)
        py = np.asarray(nc["y"][:], float)
        crs = _file_crs(nc)
        before = np.asarray(nc["zs"][:], float)
    tab = read_table(spec, crs)
    row = match_points(px, py, tab["x"], tab["y"], spec.tol_m, spec.extra_rows_ok)
    add = tab["offset"][row]
    moved = bool(np.any(add != 0.0))
    if moved:
        # Copy -> edit the copy's zs in place -> replace: every other byte (time, x, y, stations, attrs) stays,
        # a hard link to the template's file is broken, and a kill leaves the old file whole.
        tmp = f.with_name(f".{f.name}.pointoffsets")
        shutil.copy2(f, tmp)
        with netCDF4.Dataset(tmp, "r+") as nc:
            nc["zs"][:] = before + add[None, :]
        os.replace(tmp, f)
    arms = _staged_point_arms(d, px, py)
    pts = []
    for i in range(px.size):
        r = int(row[i])
        pts.append(
            {
                "index": i,
                "xy": [round(float(px[i]), 1), round(float(py[i]), 1)],
                "sp": tab["sp"][r],
                "table_row": r,
                "table_arm": tab["arm"][r],
                "read_by_arms": None if arms is None else arms[i],
                "offset_m": float(add[i]),
            }
        )
    by_arm = {}
    if arms is not None:
        for name in sorted({a for p in arms for a in p}):
            sel = np.array([name in p for p in arms])
            by_arm[name] = _summary(add[sel])
    rec = {
        "table": str(Path(spec.table).resolve()),
        "table_md5": tab["md5"],
        "column": spec.column,
        "tol_m": spec.tol_m,
        "extra_rows_ok": spec.extra_rows_ok,
        "n_points": int(px.size),
        "n_table_rows": int(tab["x"].size),
        "boundary_file_changed": moved,
        "all": _summary(add),
        "by_arm": by_arm,
        "mean_before_m": round(float(np.nanmean(before)), 4),
        "mean_after_m": round(float(np.nanmean(before + add[None, :])), 4),
        #: positional, in the staged file's station order: the check is ``zs_arm − zs_ref == offsets_m``.
        "offsets_m": [float(v) for v in add],
        "points": pts,
    }
    (d / META).write_text(json.dumps(rec, indent=1) + "\n")
    line = (
        f"boundary_point_offsets = {Path(spec.table).name}:{spec.column} (md5 {tab['md5'][:8]}) on "
        f"{px.size} points, {rec['all']['min_m']:+.3f}..{rec['all']['max_m']:+.3f} m "
        f"(mean {rec['all']['mean_m']:+.4f})"
        + ("" if moved else "; all zero, file untouched")
    )
    prov = d / "provenance.txt"
    text = prov.read_text() if prov.exists() else ""
    prov.unlink(missing_ok=True)
    prov.write_text(
        text + ("" if text.endswith("\n") or not text else "\n") + line + "\n"
    )
    print(f"[bnd] {line}", flush=True)
    return rec
