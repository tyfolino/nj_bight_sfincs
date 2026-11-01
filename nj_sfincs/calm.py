"""Calm runs: only the sea moves. Still water on the sloped MHHW surface, and the tidal twin.

The collaborator's comparison (user 2026-10-28/29/30, ``logs/modern_bed_2026-11-01/README.md``).
:func:`apply` runs LAST on a staged arm. Wind, pressure, rain and discharge come out, so the
solver is never handed them; the boundary and the window are replaced; the start is written.

WHAT IS DIFFERENT FROM ``sea_level.py``
---------------------------------------
Same binary file and the same idea (water only where the sea reaches through the subgrid
sills), plus three things a calm start needs:

* **A level per face.** Still water sits on VDatum MHHW + s, about 0.8 m at the mouth and
  1.5 m at Trenton, not on one number.
* **Weirs block.** ``sfincs.weir`` is invisible to the subgrid sills, so a scalar fill walks
  straight under the Keansburg levee and the Overpeck dam. A uv point the engine would turn
  into a structure (polyline crosses the centre-to-centre link, crest above ``uv_zmin``:
  ``sfincs_structures.f90``) is closed while its crest is above the level.
* **The Overpeck pool stays.** Faces of the template's regional start that the sea does not
  reach keep their pool level; everything else unreached starts dry.

🔴 A SLOPED SURFACE IS NOT AN EQUILIBRIUM. Nothing in a calm run holds up the slope: the upper
Delaware drains toward the mouth's level and the back bays, whose MHHW is well below the
ocean's, fill through their inlets. ``zsmax`` of a long enough still run therefore holds water
that neither surface ever had. Read the first output block, or the start itself, for the
sloped-surface map, and keep the window short.

``tspinup`` is 0 on a still arm: during spin-up the engine blends the boundary with the single
number ``zsini`` (``sfincs_boundaries.f90``), which a sloped boundary would feel as a ramp.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from . import model as _model
from . import normal_surface, sea_level
from .config import CalmForcing

#: The template's start for the Overpeck pool (hand step, CLAUDE.md §5).
REGIONAL_INI = "sfincs_ini_regional.bin"
#: inp keys and files a calm arm must not carry.
_DROP_KEYS = ("netamuamvfile", "netampfile", "netamprfile", "netsrcdisfile", "dtwnd")
_DROP_FILES = (
    "sfincs_netamuv.nc",
    "sfincs_netamp.nc",
    "sfincs_netampr.nc",
    "sfincs_netsrcdisfile.nc",
    REGIONAL_INI,
    "sfincs_ini_regional.json",
)
BND_FILE = "sfincs_netbndbzsbzifile.nc"


def read_weirs(path: Path | str) -> list[np.ndarray]:
    """Polylines of a tekal ``sfincs.weir``: one ``(n, 3)`` array of x, y, crest each."""
    lines = [ln.split() for ln in Path(path).read_text().splitlines() if ln.strip()]
    out, i = [], 0
    while i < len(lines):
        nrow = int(lines[i + 1][0])
        out.append(np.array(lines[i + 2 : i + 2 + nrow], dtype=float)[:, :3])
        i += 2 + nrow
    return out


def _cross(ax, ay, bx, by, cx, cy, dx, dy) -> np.ndarray:
    """Do segments a-b and c-d cross? Strict: a touching end does not count."""

    def side(px, py, qx, qy, rx, ry):
        return (qx - px) * (ry - py) - (qy - py) * (rx - px)

    return (side(ax, ay, bx, by, cx, cy) * side(ax, ay, bx, by, dx, dy) < 0) & (
        side(cx, cy, dx, dy, ax, ay) * side(cx, cy, dx, dy, bx, by) < 0
    )


def weir_crests(x, y, uv_nm, uv_nmu, act, weirs, reach: float = 2000.0) -> np.ndarray:
    """Crest per uv point, NaN where no weir crosses (``max`` of the crossings, as the engine).

    ``x``, ``y``: face centres. Only uv points between two active faces can be structures.
    ``reach`` bounds the search around a segment; the coarsest mesh link is far below it.
    """
    from scipy.spatial import cKDTree

    crest = np.full(len(uv_nm), np.nan)
    live = np.flatnonzero(act[uv_nm] & act[uv_nmu])
    if not weirs or live.size == 0:
        return crest
    xm = 0.5 * (x[uv_nm[live]] + x[uv_nmu[live]])
    ym = 0.5 * (y[uv_nm[live]] + y[uv_nmu[live]])
    allv = np.vstack(weirs)
    near = (
        (xm > allv[:, 0].min() - reach)
        & (xm < allv[:, 0].max() + reach)
        & (ym > allv[:, 1].min() - reach)
        & (ym < allv[:, 1].max() + reach)
    )
    live, xm, ym = live[near], xm[near], ym[near]
    if live.size == 0:
        return crest
    tree = cKDTree(np.c_[xm, ym])
    for w in weirs:
        for (ax, ay, az), (bx, by, bz) in zip(w[:-1], w[1:]):
            mid = (0.5 * (ax + bx), 0.5 * (ay + by))
            r = 0.5 * np.hypot(bx - ax, by - ay) + reach
            cand = np.asarray(tree.query_ball_point(mid, r), dtype=np.int64)
            if cand.size == 0:
                continue
            ip = live[cand]
            hit = _cross(
                ax, ay, bx, by, x[uv_nm[ip]], y[uv_nm[ip]], x[uv_nmu[ip]], y[uv_nmu[ip]]
            )
            if not hit.any():
                continue
            ip, xc, yc = ip[hit], xm[cand[hit]], ym[cand[hit]]
            d1, d2 = np.hypot(xc - ax, yc - ay), np.hypot(xc - bx, yc - by)
            h = az + (bz - az) * d1 / np.maximum(d1 + d2, 1e-9)
            crest[ip] = np.fmax(crest[ip], h)
    return crest


def connected_start(
    level,
    mask: np.ndarray,
    z_zmin: np.ndarray,
    uv_nm: np.ndarray,
    uv_nmu: np.ndarray,
    uv_zmin: np.ndarray,
    crest: np.ndarray | None = None,
) -> np.ndarray:
    """``level`` (scalar or per face) where the sea reaches, ``sea_level.DRY`` elsewhere.

    Seeds: forced faces below their level. A link is open when its sill is below the lower
    of its two faces' levels and no closed weir sits on it.
    """
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    n = len(mask)
    lev = np.broadcast_to(np.asarray(level, dtype="f8"), (n,))
    act = mask > 0
    wet = act & np.isfinite(z_zmin) & (z_zmin < lev)
    low = np.minimum(lev[uv_nm], lev[uv_nmu])
    link = wet[uv_nm] & wet[uv_nmu] & np.isfinite(uv_zmin) & (uv_zmin < low)
    if crest is not None:
        # the engine keeps a structure only where its crest is above the sill
        closed = np.isfinite(crest) & (crest > uv_zmin) & (crest >= low)
        link &= ~closed
    a, b = uv_nm[link], uv_nmu[link]
    graph = coo_matrix((np.ones(len(a), np.int8), (a, b)), shape=(n, n))
    _, lab = connected_components(graph, directed=False)
    reached = np.isin(lab, np.unique(lab[wet & (mask == 2)])) & wet
    return np.where(reached, lev, sea_level.DRY).astype(np.float32)


def mhhw_at(x, y) -> tuple[np.ndarray, dict]:
    """VDatum MHHW at points; a point off the raster takes its nearest valid neighbour."""
    from scipy.spatial import cKDTree

    v = normal_surface.sample_raster(normal_surface.mhhw_path(), x, y)
    ok = np.isfinite(v)
    info = {"points": int(v.size), "off_raster": int((~ok).sum()), "fill_max_km": 0.0}
    if (~ok).any():
        d, i = cKDTree(np.c_[x[ok], y[ok]]).query(np.c_[x[~ok], y[~ok]])
        v[~ok] = v[ok][i]
        info["fill_max_km"] = round(float(d.max()) / 1000.0, 2)
    return v, info


def write_start(
    model_dir: Path | str, level, boundary_offset_m: float, regional: np.ndarray | None
) -> dict:
    """Write ``sea_level.INI_FILE`` + its sidecar. ``regional``: the template's start, one
    value per active face; its non-zero faces keep their pool where the sea does not reach."""
    import xarray as xr

    d = Path(model_dir)
    with xr.open_dataset(d / "sfincs.nc") as g:
        mask = g["mask"].values.astype(int)
        mu, nu = g["mu"].values.astype(int), g["nu"].values.astype(int)
        mu1, mu2, nu1, nu2 = (
            g[k].values.astype(np.int64) - 1 for k in ("mu1", "mu2", "nu1", "nu2")
        )
        x, y = g["mesh2d_face_x"].values, g["mesh2d_face_y"].values
    with xr.open_dataset(d / "sfincs_subgrid.nc") as s:
        z_zmin, uv_zmin = s["z_zmin"].values, s["uv_zmin"].values
    uv_nm, uv_nmu = sea_level.uv_pairs(mu, mu1, mu2, nu, nu1, nu2)
    if len(uv_nm) != len(uv_zmin):
        raise RuntimeError(
            "uv order changed: the sills would be read on the wrong links"
        )
    act = mask > 0
    weirs = read_weirs(d / "sfincs.weir") if (d / "sfincs.weir").exists() else []
    crest = weir_crests(x, y, uv_nm, uv_nmu, act, weirs)
    zs = connected_start(level, mask, z_zmin, uv_nm, uv_nmu, uv_zmin, crest)
    wet = zs > sea_level.DRY
    lev = np.broadcast_to(np.asarray(level, dtype="f8"), mask.shape)
    n_pool = 0
    if regional is not None:
        full = np.zeros(mask.shape, np.float32)
        full[act] = regional
        pool = (full != 0) & ~wet
        zs[pool] = full[pool]
        n_pool = int(pool.sum())
    tmp = d / (sea_level.INI_FILE + ".tmp")
    zs[act].astype("<f4").tofile(tmp)
    tmp.replace(d / sea_level.INI_FILE)
    floodable = act & (z_zmin < lev)
    struct = np.isfinite(crest) & (crest > uv_zmin)
    meta = {
        "level_min": float(lev[act].min()),
        "level_max": float(lev[act].max()),
        "boundary_offset_m": float(boundary_offset_m),
        "active_points": int(act.sum()),
        "wet_cells": int(wet.sum()),
        "floodable_cells": int(floodable.sum()),
        "disconnected_dry_cells": int((floodable & ~wet).sum()),
        "structure_uv_points": int(struct.sum()),
        "structure_uv_closed_at_start": int(
            (struct & (crest >= np.minimum(lev[uv_nm], lev[uv_nmu]))).sum()
        ),
        "pool_faces_kept": n_pool,
    }
    (d / sea_level.INI_META).write_text(json.dumps(meta, indent=1) + "\n")
    return meta


def write_mhhw_boundary(
    model_dir: Path | str, offset_m: float, cfg: CalmForcing
) -> dict:
    """Replace the staged boundary with MHHW + offset, constant in time, same stations."""
    import pandas as pd
    import xarray as xr

    d = Path(model_dir)
    f = d / BND_FILE
    with xr.open_dataset(f, decode_times=False) as opened:
        src = opened.load()
    z, info = mhhw_at(src.x.values.astype("f8"), src.y.values.astype("f8"))
    t0 = pd.Timestamp(cfg.tstart)
    minutes = np.array([0.0, (pd.Timestamp(cfg.tstop) - t0).total_seconds() / 60.0])
    zs = np.tile(z + offset_m, (2, 1))
    ds = xr.Dataset(
        {
            "zs": (("time", "stations"), zs, {"coordinates": "spatial_ref x y"}),
            "spatial_ref": src.spatial_ref,
            "x": src.x,
            "y": src.y,
        },
        coords={
            "time": (
                "time",
                minutes,
                {
                    "units": f"minutes since {t0:%Y-%m-%d %H:%M:%S}",
                    "calendar": "proleptic_gregorian",
                },
            ),
            "stations": src.stations,
        },
        attrs={"source": f"VDatum MHHW (normal_surface) + {offset_m} m, constant"},
    )
    tmp = d / (BND_FILE + ".tmp")
    fill = {"dtype": "float64", "_FillValue": np.nan}
    ds.to_netcdf(
        tmp,
        encoding={
            "time": fill,
            "zs": fill,
            "x": fill,
            "y": fill,
            "stations": {"dtype": "int64"},
        },
    )
    f.unlink()
    tmp.replace(f)
    info.update(zs_min=float(zs.min()), zs_max=float(zs.max()))
    return info


def install_tide_boundary(
    model_dir: Path | str, src: Path | str, cfg: CalmForcing
) -> dict:
    """Copy an engine-format boundary in, refusing other stations or a short window."""
    import shutil

    import pandas as pd
    import xarray as xr

    d = Path(model_dir)
    f = d / BND_FILE
    with (
        xr.open_dataset(f, decode_times=False) as a,
        xr.open_dataset(src, decode_times=False) as b,
    ):
        if not (
            np.array_equal(a.stations.values, b.stations.values)
            and np.array_equal(a.x.values, b.x.values)
            and np.array_equal(a.y.values, b.y.values)
        ):
            raise SystemExit(f"{src}: other stations than the staged boundary")
        t = pd.to_datetime(
            b.time.values, unit="m", origin=b.time.units.split("since ")[1]
        )
        if t[0] > pd.Timestamp(cfg.tstart) or t[-1] < pd.Timestamp(cfg.tstop):
            raise SystemExit(f"{src}: {t[0]}..{t[-1]} does not cover the window")
        if not np.isfinite(b.zs.values).all():
            raise SystemExit(f"{src}: non-finite water levels")
        info = {"zs_min": float(b.zs.min()), "zs_max": float(b.zs.max())}
    tmp = d / (BND_FILE + ".tmp")
    shutil.copy2(src, tmp)
    f.unlink()
    tmp.replace(f)
    return info


def _set_inp(inp: Path, kv: dict, drop=()) -> None:
    lines = [
        ln
        for ln in inp.read_text().splitlines()
        if ln.split("=")[0].strip() not in set(drop)
    ]
    inp.write_text("\n".join(lines) + "\n")
    _model.set_inp_keys(inp, kv)


def inp_keys(cfg: CalmForcing, zsini: float, still: bool) -> dict:
    """The ``sfincs.inp`` values a calm arm sets. ``dtrstout`` stays a multiple of dtmaxout."""
    if _model.RESTART_DT_S % cfg.dtmaxout:
        raise ValueError(f"dtmaxout {cfg.dtmaxout} must divide {_model.RESTART_DT_S}")
    return {
        "tref": cfg.tstart,
        "tstart": cfg.tstart,
        "tstop": cfg.tstop,
        "tspinup": "0.0" if still else "3600.0",
        "dtmapout": f"{cfg.dtmapout:.1f}",
        "dtmaxout": f"{cfg.dtmaxout:.1f}",
        "dtrstout": f"{_model.RESTART_DT_S:.1f}",
        "baro": "0",
        "storevel": "0",
        "storefw": "0",
        "storecumprcp": "0",
        "zsini": f"{zsini:.4f}",
        "inifile": sea_level.INI_FILE,
    }


def apply(model_dir: Path | str, cfg: CalmForcing) -> dict:
    """Turn a staged waves-off, rain-off arm into a calm one. Returns the sidecar's contents."""
    import xarray as xr

    d = Path(model_dir)
    inp = d / "sfincs.inp"
    if "snapwave             = 0" not in inp.read_text():
        raise SystemExit(f"{d}: a calm arm must be waves-off")
    _model.break_hardlinks(d, names=("sfincs.inp", BND_FILE))
    regional = None
    if (d / REGIONAL_INI).exists():
        regional = np.fromfile(d / REGIONAL_INI, dtype="<f4")
    still = cfg.boundary == "mhhw"
    if still:
        with xr.open_dataset(d / "sfincs.nc") as g:
            act = g["mask"].values > 0
            x, y = g["mesh2d_face_x"].values, g["mesh2d_face_y"].values
        lev = np.full(act.shape, np.nan)
        z, face_info = mhhw_at(x[act], y[act])
        lev[act] = z + cfg.offset_m
        lev[~act] = cfg.offset_m
        bnd = write_mhhw_boundary(d, cfg.offset_m, cfg)
        zsini = float(np.median(lev[act]))
        meta = write_start(d, lev, cfg.offset_m, regional)
        meta["mhhw_faces"] = face_info
    else:
        if cfg.level_m is None:
            raise SystemExit("a tide arm needs level_m")
        bnd = install_tide_boundary(d, cfg.boundary, cfg)
        zsini = float(cfg.level_m)
        meta = write_start(d, zsini, cfg.offset_m, regional)
    meta["boundary"] = bnd
    meta["boundary_source"] = cfg.boundary
    (d / sea_level.INI_META).write_text(json.dumps(meta, indent=1) + "\n")
    for name in _DROP_FILES:
        (d / name).unlink(missing_ok=True)
    _set_inp(inp, inp_keys(cfg, zsini, still), drop=_DROP_KEYS)
    print(
        f"[calm] {d.name}: {meta['wet_cells']:,} faces start wet, "
        f"{meta['disconnected_dry_cells']:,} below their level start dry, "
        f"{meta['structure_uv_closed_at_start']:,} of {meta['structure_uv_points']:,} "
        f"weir uv points closed; boundary {bnd['zs_min']:+.3f}..{bnd['zs_max']:+.3f} m",
        flush=True,
    )
    return meta
