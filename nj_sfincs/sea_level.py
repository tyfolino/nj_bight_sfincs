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

WEIRS (2026-11-14): a sill is not the only thing that holds water back. A link the ENGINE
puts a weir on (``sfincs.weir``: the Keansburg, Elizabeth and Rahway levees, a dike set)
passes no water below its crest, so a connected start that ignores it fills the protected
side at +2 / +3 m and the overflow test reads that as a leak. When the staged dir holds a
``sfincs.weir``, :func:`weir_uv_crests` finds the links the engine snaps it to — the
ENGINE's rule in float32 (``sfincs_quadtree.F90::find_uv_points_intersected_by_polyline``,
``sfincs_structures.f90::read_structure_file``; reproduces every logged u/v count:
logs/walls_elizabeth_rahway_2026-11-05/weircount_819.md, ``engine_snap_f32.py``) — and
the connectivity drops every such link whose crest is at or above the start level. With no
weir file the start is bit-identical to the sill-only rule.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

#: Written to cells the connected sea does not reach; SFINCS takes max(z_zmin, this).
DRY = -9999.0
INI_FILE = "sfincs_ini_sealevel.bin"
INI_META = "sfincs_ini_sealevel.json"
WEIR_FILE = "sfincs.weir"


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
    uv_crest: np.ndarray | None = None,
) -> np.ndarray:
    """Initial ``zs`` per face: ``level`` where the sea reaches, ``DRY`` elsewhere.

    Seeds: forced cells (``mask == 2``) whose ``z_zmin`` is below ``level``. Links: uv
    points between two ACTIVE cells whose sill ``uv_zmin`` is below ``level`` and, when
    ``uv_crest`` is given (per uv point, NaN = no weir; :func:`weir_uv_crests`), whose weir
    crest is below ``level``. ``uv_crest=None`` is the sill-only rule, unchanged.
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
    if (
        uv_crest is not None
    ):  # a weir at or above the level closes its link (NaN = none)
        link &= ~(np.asarray(uv_crest) >= level)
    a, b = uv_nm[link], uv_nmu[link]
    graph = coo_matrix((np.ones(len(a), np.int8), (a, b)), shape=(n, n))
    _, lab = connected_components(graph, directed=False)
    seeds = wet_cell & (mask == 2)
    reached = np.isin(lab, np.unique(lab[seeds])) & wet_cell
    return np.where(reached, level, DRY).astype(np.float32)


def read_weir_polylines(path: Path | str) -> list[tuple[str, np.ndarray]]:
    """``(name, rows)`` per polyline of a SFINCS weir file: a name line, ``<n> <ncol>``,
    then n rows of ``x y crest Cd``."""
    lines = [ln.strip() for ln in Path(path).read_text().splitlines() if ln.strip()]
    out, i = [], 0
    while i < len(lines):
        nrows = int(lines[i + 1].split()[0])
        rows = np.array(
            [[float(v) for v in ln.split()] for ln in lines[i + 2 : i + 2 + nrows]]
        )
        out.append((lines[i], rows))
        i += 2 + nrows
    return out


def _uv_slots(mu, mu1, mu2, nu, nu1, nu2) -> tuple[np.ndarray, np.ndarray]:
    """``slot[face, k]`` = the uv index of the face's k-th link (mu1, mu2, nu1, nu2; -1 =
    none) and the direction of every uv point (0 = u, 1 = v), in :func:`uv_pairs` order."""
    ok = np.stack(
        [
            np.asarray(mu1) >= 0,
            (np.asarray(mu) > 0) & (np.asarray(mu2) >= 0),
            np.asarray(nu1) >= 0,
            (np.asarray(nu) > 0) & (np.asarray(nu2) >= 0),
        ],
        axis=1,
    )
    slot = np.full(ok.shape, -1, np.int64)
    fi, si = np.nonzero(ok)  # row-major = the uv order
    slot[fi, si] = np.arange(fi.size)
    return slot, (si >= 2).astype(np.int8)


def weir_uv_crests(
    polylines: list[tuple[str, np.ndarray]],
    grid: dict,
    mask: np.ndarray,
    z_zmin: np.ndarray,
    uv_nm: np.ndarray,
    uv_nmu: np.ndarray,
    uv_zmin: np.ndarray,
    slot: np.ndarray,
    uv_dir: np.ndarray,
) -> np.ndarray:
    """Per uv point, the crest of the weir the ENGINE puts there (float32), NaN where none.

    A float32 port of ``engine_snap_f32.py`` (logs/walls_elizabeth_rahway_2026-11-05), which
    reproduces every count the engine has logged (819, 412, 415, 408): face centres
    recomputed from ``n`` / ``m`` / ``level`` and the grid attributes in single precision; a
    segment crosses a link when the face-centre pair straddles it, a centre within 1e-6 of
    the segment counting as straddling (so it can mark all of that face's links); the
    LAST segment of a polyline that hits a link sets its crest, interpolated at the uv
    point; over polylines the highest crest wins; a link is kept only when its crest
    exceeds ``max(uv_zmin, z_zmin of both faces)``.

    ``grid``: ``x0 y0 dx dy rotation nr_levels`` (sfincs.nc attributes) and the 1-based
    ``n``, ``m``, ``level`` face arrays.
    """
    f4 = np.float32
    act = np.asarray(mask) > 0
    nm, nmu = np.asarray(uv_nm), np.asarray(uv_nmu)
    zz = np.asarray(z_zmin, dtype=f4)
    uvz = np.maximum(np.asarray(uv_zmin, dtype=f4), np.maximum(zz[nm], zz[nmu]))
    act_uv = act[nm] & act[nmu]
    x0, y0, dx, dy = (f4(grid[k]) for k in ("x0", "y0", "dx", "dy"))
    pi = f4(np.pi)
    rot = f4(f4(grid["rotation"]) * pi / f4(180))
    cosr, sinr = f4(np.cos(rot)), f4(np.sin(rot))
    nref = int(grid["nr_levels"])
    dxr = np.array([dx / f4(2**i) for i in range(nref)], f4)
    dyr = np.array([dy / f4(2**i) for i in range(nref)], f4)
    lev = np.asarray(grid["level"]).astype(np.int64)
    n_ = np.asarray(grid["n"]).astype(np.int64)
    m_ = np.asarray(grid["m"]).astype(np.int64)
    mm, nn = (m_ - 0.5).astype(f4), (n_ - 0.5).astype(f4)
    xz = (x0 + cosr * mm * dxr[lev - 1]) - sinr * nn * dyr[lev - 1]
    yz = (y0 + sinr * mm * dxr[lev - 1]) + cosr * nn * dyr[lev - 1]
    key = lev * 10**12 + m_ * 10**6 + n_
    order = np.argsort(key)
    skey = key[order]

    def lookup(iref, ns, ms):
        k = iref * 10**12 + ms * 10**6 + ns
        j = np.clip(np.searchsorted(skey, k), 0, skey.size - 1)
        return order[j[skey[j] == k]]

    def direction(ax, ay, bx, by, cx, cy):
        val = (by - ay) * (cx - bx) - (bx - ax) * (cy - by)
        return np.where(val < f4(-1e-6), -1, np.where(val > f4(1e-6), 1, 0))

    def cross(xa, ya, xb, yb, xc, yc, xd, yd):
        d1, d2 = direction(xa, ya, xb, yb, xc, yc), direction(xa, ya, xb, yb, xd, yd)
        d3, d4 = direction(xc, yc, xd, yd, xa, ya), direction(xc, yc, xd, yd, xb, yb)
        return (d1 != d2) & (d3 != d4)

    height: dict[int, np.float32] = {}
    for _name, rows in polylines:
        xp, yp, zp = (rows[:, k].astype(f4) for k in (0, 1, 2))
        hit: dict[int, int] = {}
        for ip in range(len(xp) - 1):
            xa, ya, xb, yb = xp[ip], yp[ip], xp[ip + 1], yp[ip + 1]
            xta = cosr * (xa - x0) + sinr * (ya - y0)
            yta = -sinr * (xa - x0) + cosr * (ya - y0)
            xtb = cosr * (xb - x0) + sinr * (yb - y0)
            ytb = -sinr * (xb - x0) + cosr * (yb - y0)
            for iref in range(nref, 0, -1):
                na, ma = int(yta / dyr[iref - 1]) + 1, int(xta / dxr[iref - 1]) + 1
                nb, mb = int(ytb / dyr[iref - 1]) + 1, int(xtb / dxr[iref - 1]) + 1
                NN, MM = np.meshgrid(
                    np.arange(min(na, nb) - 1, max(na, nb) + 2),
                    np.arange(min(ma, mb) - 1, max(ma, mb) + 2),
                )
                faces = lookup(iref, NN.ravel(), MM.ravel())
                faces = faces[act[faces]]
                uvs = slot[faces].ravel()
                uvs = uvs[uvs >= 0]
                uvs = uvs[act_uv[uvs]]
                if uvs.size == 0:
                    continue
                ok = cross(
                    xa, ya, xb, yb, xz[nm[uvs]], yz[nm[uvs]], xz[nmu[uvs]], yz[nmu[uvs]]
                )
                for u in uvs[ok]:
                    hit[int(u)] = ip  # the last segment wins
        for u, irow in hit.items():
            a, b = nm[u], nmu[u]
            idir = uv_dir[u]
            iref = max(lev[a], lev[b])
            half = f4(0.5) * (dyr[iref - 1] if idir == 0 else dxr[iref - 1])
            if lev[a] >= lev[b]:
                ang, base = (rot if idir == 0 else f4(rot + f4(0.5) * pi)), a
            else:
                ang, base = (f4(rot - pi) if idir == 0 else f4(rot - f4(0.5) * pi)), b
            xuv = xz[base] + half * f4(np.cos(ang))
            yuv = yz[base] + half * f4(np.sin(ang))
            d1 = f4(np.sqrt((xuv - xp[irow]) ** 2 + (yuv - yp[irow]) ** 2))
            d2 = f4(np.sqrt((xuv - xp[irow + 1]) ** 2 + (yuv - yp[irow + 1]) ** 2))
            w = d1 / (d1 + d2)
            h = zp[irow] * (f4(1) - w) + zp[irow + 1] * w
            height[u] = max(height.get(u, f4(-9999)), h)
    crest = np.full(len(nm), np.nan, f4)
    for u, h in height.items():
        if h > uvz[u]:
            crest[u] = h
    return crest


def write_connected_ini(
    model_dir: Path | str, level: float, boundary_offset_m: float = float("nan")
) -> dict:
    """Write ``INI_FILE`` (+ ``INI_META``) for ``level`` from the staged mesh + subgrid.

    ``boundary_offset_m`` (the boundary shift measured at staging) goes in the sidecar for
    ``provenance.sea_level_offset_label``. Returns the sidecar's contents.

    When ``model_dir`` holds a ``sfincs.weir`` (the engine reads it: finalize keeps the
    ``weirfile`` key whenever the file is there), links the engine puts a weir on whose crest
    is at or above ``level`` are closed (:func:`weir_uv_crests`); the sidecar then also
    records the weir u/v count, how many crests sit at / above the level, and how many cells
    the weirs keep dry. Without the file the output is byte-identical to the sill-only rule.
    """
    import json

    import xarray as xr

    model_dir = Path(model_dir)
    weir = model_dir / WEIR_FILE
    with xr.open_dataset(model_dir / "sfincs.nc") as g:
        mask = g["mask"].values.astype(int)
        mu, nu = g["mu"].values.astype(int), g["nu"].values.astype(int)
        mu1, mu2, nu1, nu2 = (
            g[k].values.astype(np.int64) - 1 for k in ("mu1", "mu2", "nu1", "nu2")
        )
        if weir.is_file():
            grid = {k: g.attrs[k] for k in ("x0", "y0", "dx", "dy", "rotation")}
            grid["nr_levels"] = g.attrs["nr_levels"]
            grid.update({k: g[k].values for k in ("n", "m", "level")})
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
    crest = None
    if weir.is_file():
        slot, uv_dir = _uv_slots(mu, mu1, mu2, nu, nu1, nu2)
        crest = weir_uv_crests(
            read_weir_polylines(weir),
            grid,
            mask,
            z_zmin,
            uv_nm,
            uv_nmu,
            uv_zmin,
            slot,
            uv_dir,
        )
    zs = connected_initial_zs(level, mask, z_zmin, uv_nm, uv_nmu, uv_zmin, crest)
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
    if crest is not None:
        sill_only = connected_initial_zs(level, mask, z_zmin, uv_nm, uv_nmu, uv_zmin)
        meta.update(
            {
                "weir_file": WEIR_FILE,
                "weir_uv_points": int(np.isfinite(crest).sum()),
                "weir_uv_at_or_above_level": int((crest >= level).sum()),
                "cells_kept_dry_by_weirs": int(((sill_only > DRY) & ~wet).sum()),
            }
        )
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
