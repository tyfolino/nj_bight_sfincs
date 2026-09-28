"""Sea-level offset runs: raise the boundary water level, start the model at the new level.

WHY THE INITIAL CONDITION IS NOT JUST ``zsini`` (2026-09-28)
------------------------------------------------------------
Adding a constant to the boundary water level is the whole forcing change. The catch is the
START: SFINCS sets ``zs = max(z_zmin, zsini)`` on EVERY active cell
(``sfincs_initial_conditions.F90``, v2.3.3), connected to the sea or not. At +2 or +3 m that
floods every diked marsh, impounded meadow and inland low spot below the offset at t = 0 —
exactly the ground an overflow test asks about. Leaving ``zsini`` at 0 instead makes the
boundary ramp 0 → offset over ``tspinup`` (1 h): a 3 m bore into Delaware Bay whose
transient lands in ``zsmax``.

So the start is a CONNECTED bathtub: ``offset`` on every cell the sea reaches at that level
through the subgrid SILLS (``uv_zmin``, the lowest level at which water crosses a uv point),
seeded from the forced ``mask == 2`` cells; everything else starts dry. It is written to an
``inifile`` and ``zsini = offset`` so the boundary ramp starts from the same level the
connected water sits at.

🔴 THE INIFILE IS BINARY, NOT NETCDF. v2.3.3 (and ``main``) choose the NetCDF reader with
``if (zsinifile(nchar - 1 : nchar) == 'nc')`` where ``nchar`` is declared and NEVER
ASSIGNED (``sfincs_initial_conditions.F90``). On our -O3 build a ``.nc`` file went down the
BINARY path, was read as raw floats, and the toy run hit the minimum time step at t = 0
(2026-09-28). The binary reader (``read_zsini_file``) takes a raw ``real*4`` stream, one
value per ACTIVE point in SFINCS order — ``msk > 0`` in quadtree face order
(``sfincs_domain.f90``: ``index_sfincs_in_quadtree``). Its log line "remake your inifile
containing zs as real*8" is wrong for this reader, which reads ``real*4``. The measured
boundary shift and the counts go in a JSON sidecar. A sill, not a cell minimum, because a 50 m
cell containing a dike has low pixels on both sides: its ``z_zmin`` says "floodable", its
uv sills say "not from here".

The uv-point order is hydromt's (``subgrid_quadtree_builder.py``): per cell, ``mu1``, then
``mu2`` when ``mu > 0``, then ``nu1``, then ``nu2`` when ``nu > 0``, skipping missing
neighbours. Verified on the sealed v3 template: 6,860,215 rebuilt = ``npuv`` in the file,
and every ``uv_zmin`` sits ≥ 0.01 m above the lower of its two cells' ``z_zmin``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

#: Written to cells the connected sea does not reach; SFINCS takes max(z_zmin, this).
DRY = -9999.0
INI_FILE = "sfincs_ini_sealevel.bin"
INI_META = "sfincs_ini_sealevel.json"


def uv_pairs(mu, mu1, mu2, nu, nu1, nu2) -> tuple[np.ndarray, np.ndarray]:
    """The (nm, nmu) cell pair of every uv point, in the subgrid table's order.

    Neighbour arrays are 0-based with -1 = none (sfincs.nc stores them 1-based, 0 = none).
    """
    mu, nu = np.asarray(mu), np.asarray(nu)
    cand = np.stack(
        [
            np.asarray(mu1),
            np.where(mu > 0, mu2, -1),
            np.asarray(nu1),
            np.where(nu > 0, nu2, -1),
        ],
        axis=1,
    )
    nm = np.broadcast_to(np.arange(len(mu))[:, None], cand.shape)
    keep = cand >= 0
    return nm[keep], cand[keep]


def connected_initial_zs(
    level: float,
    mask: np.ndarray,
    z_zmin: np.ndarray,
    uv_nm: np.ndarray,
    uv_nmu: np.ndarray,
    uv_zmin: np.ndarray,
) -> np.ndarray:
    """Initial ``zs`` per face: ``level`` where the sea reaches, ``DRY`` elsewhere.

    Seeds: forced cells (``mask == 2``) whose ``z_zmin`` is below ``level``. Links: uv
    points between two ACTIVE cells whose sill ``uv_zmin`` is below ``level``.
    """
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    n = len(mask)
    act = mask > 0
    wet_cell = act & np.isfinite(z_zmin) & (z_zmin < level)
    link = (
        act[uv_nm]
        & act[uv_nmu]
        & np.isfinite(uv_zmin)
        & (uv_zmin < level)
        & wet_cell[uv_nm]
        & wet_cell[uv_nmu]
    )
    a, b = uv_nm[link], uv_nmu[link]
    graph = coo_matrix((np.ones(len(a), np.int8), (a, b)), shape=(n, n))
    _, lab = connected_components(graph, directed=False)
    seeds = wet_cell & (mask == 2)
    reached = np.isin(lab, np.unique(lab[seeds])) & wet_cell
    return np.where(reached, level, DRY).astype(np.float32)


def write_connected_ini(
    model_dir: Path | str, level: float, boundary_offset_m: float = float("nan")
) -> dict:
    """Write ``INI_FILE`` (+ ``INI_META``) for ``level`` from the staged mesh + subgrid.

    ``boundary_offset_m`` (the boundary shift measured at staging) goes in the sidecar for
    ``provenance.sea_level_offset_label``. Returns the sidecar's contents.
    """
    import json

    import xarray as xr

    model_dir = Path(model_dir)
    with xr.open_dataset(model_dir / "sfincs.nc") as g:
        mask = g["mask"].values.astype(int)
        mu, nu = g["mu"].values.astype(int), g["nu"].values.astype(int)
        mu1, mu2, nu1, nu2 = (
            g[k].values.astype(np.int64) - 1 for k in ("mu1", "mu2", "nu1", "nu2")
        )
    with xr.open_dataset(model_dir / "sfincs_subgrid.nc") as s:
        z_zmin = s["z_zmin"].values
        uv_zmin = s["uv_zmin"].values
        npuv = s.sizes["npuv"]
    uv_nm, uv_nmu = uv_pairs(mu, mu1, mu2, nu, nu1, nu2)
    if len(uv_nm) != npuv:
        raise RuntimeError(
            f"rebuilt {len(uv_nm)} uv points but the subgrid has {npuv}: hydromt's uv "
            "order changed — the sills would be read against the wrong cell pairs."
        )
    zs = connected_initial_zs(level, mask, z_zmin, uv_nm, uv_nmu, uv_zmin)
    act = mask > 0
    floodable = act & (z_zmin < level)
    wet = zs > DRY
    tmp = model_dir / (INI_FILE + ".tmp")
    zs[act].astype("<f4").tofile(tmp)
    tmp.replace(model_dir / INI_FILE)
    meta = {
        "level": float(level),
        "boundary_offset_m": float(boundary_offset_m),
        "active_points": int(act.sum()),
        "wet_cells": int(wet.sum()),
        "floodable_cells": int(floodable.sum()),
        "disconnected_dry_cells": int((floodable & ~wet).sum()),
    }
    (model_dir / INI_META).write_text(json.dumps(meta, indent=1) + "\n")
    return meta


def read_ini(model_dir: Path | str) -> np.ndarray:
    """The written start, one value per ACTIVE point (SFINCS order)."""
    return np.fromfile(Path(model_dir) / INI_FILE, dtype="<f4")


def ini_keys(text: str, level: float) -> str:
    """Set ``zsini = level`` and ``inifile = INI_FILE`` in sfincs.inp text."""
    lines = [
        ln
        for ln in text.splitlines()
        if ln.split("=")[0].strip() not in ("zsini", "inifile")
    ]
    lines += [f"zsini                = {level}", f"inifile              = {INI_FILE}"]
    return "\n".join(lines) + "\n"
