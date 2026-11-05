"""Parallel, checkpointed quadtree subgrid builder — bit-identical to the serial one.

WHAT IT REPLACES. ``scripts/rebuild_subgrid.py`` calls hydromt_sfincs 2.0.0-rc2's
``SubgridTableQuadtree.build`` (``components/quadtree/subgrid_quadtree_builder.py``),
which walks every refinement level, every 2000-pixel block, twice (a cell-centre pass,
then a uv-point pass), single-threaded and with no checkpoint: 5.1 h on Model 1.0.0's
mesh (4.88 M faces, 4 levels, 5,232 blocks per pass), and a preemption loses it all.

HOW. The blocks are independent once the cell pass is done (a uv point reads the
``z_zmin`` of its two neighbour cells, which live at its own level or the next coarser
one). So:

* phase 1 — every CELL block of every level, in a process pool;
* phase 2 — every UV block of every level, in the same pool, after a barrier;
* each task writes its result to its own file in ``work_dir`` (zstd-compressed pickle,
  written to a temp name and renamed): the CHECKPOINT. A rerun with the same inputs
  (``manifest.json`` must match) skips every block whose file exists;
* the main process assembles the tables exactly as the serial builder lays them out,
  writes each ``dep/manning_subgrid_lev<L>.tif`` with the serial script's profile
  (blocks in the serial order, same windows) and overviews, and the dataset hydromt's
  ``SfincsQuadtreeSubgridTable.write`` writes.

Every per-block computation is the serial builder's own code path, copied line for line
(``utils.make_regular_grid``, the builder module's ``merge_multi_dataarrays`` — so the
``--overlay`` wrapper installed by ``rebuild_subgrid.install_overlay_merge`` applies —,
``interpolate_na(rio_idw)``, the numba ``process_block_cells`` /
``process_block_uv_points``). The only rewrites are the PURE-PYTHON index loops (which
uv points exist, which cells / uv points fall in a block), vectorised with numpy and
checked against the original loops by ``check_index_tables`` — they were also a large
share of the serial runtime (a Python loop over every cell of the level per block).

NOT done (it would not be bit-identical, see logs/subgrid_parallel_2026-11-04): reusing
the cell-pass DEM merge for the uv pass. The two lattices are the same pixel lattice
shifted by half a cell, but the coordinates are computed through different float
offsets and the merge clips / averages per window.

Workers are SPAWNED (GDAL / dask are not fork-safe), each re-parses the elevation and
roughness lists itself (lazy rasters, the model bbox computed once by the parent), with
``GDAL_CACHEMAX`` capped and dask on its synchronous scheduler so 32 workers do not
each start 32 threads. None of that changes a value.
"""

from __future__ import annotations

import hashlib
import json
import os
import pickle
import shutil
import sys
import time
import traceback
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass, field
from multiprocessing import get_context
from pathlib import Path

import numpy as np

try:  # Python >= 3.14
    from compression import zstd as _zstd

    def _compress(b: bytes) -> bytes:
        return _zstd.compress(b, level=3)

    def _decompress(b: bytes) -> bytes:
        return _zstd.decompress(b)

    _EXT = ".pkl.zst"
except ImportError:  # pragma: no cover - older interpreters
    import zlib

    def _compress(b: bytes) -> bytes:
        return zlib.compress(b, 1)

    def _decompress(b: bytes) -> bytes:
        return zlib.decompress(b)

    _EXT = ".pkl.z"


BUILDER_FILE = "hydromt_sfincs/components/quadtree/subgrid_quadtree_builder.py"


# --------------------------------------------------------------------------------------
# build parameters: the values scripts/rebuild_subgrid.py ends up passing to
# SubgridTableQuadtree.build (quadtree_subgrid.create's defaults where it passes none)
# --------------------------------------------------------------------------------------
@dataclass
class BuildParams:
    nr_levels: int = 10
    nr_subgrid_pixels: int = 16
    nrmax: int = 2000
    manning_land: float = 0.04  # create() default (build()'s own default is 0.06)
    manning_water: float = 0.020
    manning_level: float = 1.0
    max_gradient: float = 999.0
    depth_factor: float = 1.0
    huthresh: float = 0.01
    zmin: float = -999999.0
    zmax: float = 999999.0
    weight_option: str = "min"
    roughness_type: str = "manning"
    buffer_cells: int = 0
    interp_method: str = "linear"
    write_dep_tif: bool = True
    write_man_tif: bool = True

    def as_dict(self) -> dict:
        return dict(self.__dict__)


# --------------------------------------------------------------------------------------
# geometry: the index tables the serial builder derives from the grid
# --------------------------------------------------------------------------------------
@dataclass
class Geometry:
    attrs: dict
    level: np.ndarray
    n: np.ndarray
    m: np.ndarray
    yc: np.ndarray
    npuv: int
    uv_index_z_nm: np.ndarray
    uv_index_z_nmu: np.ndarray
    uv_flags_dir: np.ndarray
    uv_flags_level: np.ndarray
    uv_flags_type: np.ndarray
    ifirst: np.ndarray
    ilast: np.ndarray
    levels: list = field(default_factory=list)  # per refinement level: LevelInfo


@dataclass
class LevelInfo:
    ilev: int
    n0: int
    n1: int
    m0: int
    m1: int
    dx: float
    dy: float
    dxp: float
    dyp: float
    nrcb: int
    nrbn: int
    nrbm: int


def uv_tables(level, nu, nu1, nu2, mu, mu1, mu2):
    """Vectorised copy of the serial builder's uv-point enumeration.

    ``npuv`` is the serial COUNT (every non-negative mu1/mu2/nu1/nu2), the arrays are
    zero-filled to that length and filled in the serial order (per cell: x-mu1, x-mu2
    (finer to the right only), y-nu1, y-nu2 (finer above only)); entries the serial
    fill loop never reaches stay zero exactly as there.
    """
    nc = level.size
    npuv = int(
        (mu1 >= 0).sum() + (mu2 >= 0).sum() + (nu1 >= 0).sum() + (nu2 >= 0).sum()
    )
    fine_m = mu > 0
    fine_n = nu > 0
    valid = np.stack(
        [mu1 >= 0, fine_m & (mu2 >= 0), nu1 >= 0, fine_n & (nu2 >= 0)], axis=1
    )
    nmu = np.stack([mu1, mu2, nu1, nu2], axis=1)
    lev = np.stack(
        [
            np.where(fine_m, level + 1, level),
            level + 1,
            np.where(fine_n, level + 1, level),
            level + 1,
        ],
        axis=1,
    )
    typ = np.stack([mu, mu, nu, nu], axis=1)
    dirn = np.broadcast_to(np.array([0, 0, 1, 1]), (nc, 4))
    nm = np.broadcast_to(np.arange(nc)[:, None], (nc, 4))
    v = valid.ravel()
    k = int(v.sum())
    out = {}
    for name, src in (
        ("uv_index_z_nm", nm),
        ("uv_index_z_nmu", nmu),
        ("uv_flags_dir", dirn),
        ("uv_flags_level", lev),
        ("uv_flags_type", typ),
    ):
        a = np.zeros(npuv, dtype=int)
        a[:k] = np.asarray(src).ravel()[v]
        out[name] = a
    return npuv, out


def uv_tables_serial(level, nu, nu1, nu2, mu, mu1, mu2):
    """The serial builder's loops, verbatim (for ``check_index_tables``)."""
    nr_cells = level.size
    npuv = 0
    for ip in range(nr_cells):
        if mu1[ip] >= 0:
            npuv += 1
        if mu2[ip] >= 0:
            npuv += 1
        if nu1[ip] >= 0:
            npuv += 1
        if nu2[ip] >= 0:
            npuv += 1
    uv_index_z_nm = np.zeros(npuv, dtype=int)
    uv_index_z_nmu = np.zeros(npuv, dtype=int)
    uv_flags_dir = np.zeros(npuv, dtype=int)
    uv_flags_level = np.zeros(npuv, dtype=int)
    uv_flags_type = np.zeros(npuv, dtype=int)
    ip = -1
    for ic in range(nr_cells):
        if mu[ic] <= 0:
            if mu1[ic] >= 0:
                ip += 1
                uv_index_z_nm[ip] = ic
                uv_index_z_nmu[ip] = mu1[ic]
                uv_flags_dir[ip] = 0
                uv_flags_level[ip] = level[ic]
                uv_flags_type[ip] = mu[ic]
        else:
            if mu1[ic] >= 0:
                ip += 1
                uv_index_z_nm[ip] = ic
                uv_index_z_nmu[ip] = mu1[ic]
                uv_flags_dir[ip] = 0
                uv_flags_level[ip] = level[ic] + 1
                uv_flags_type[ip] = mu[ic]
            if mu2[ic] >= 0:
                ip += 1
                uv_index_z_nm[ip] = ic
                uv_index_z_nmu[ip] = mu2[ic]
                uv_flags_dir[ip] = 0
                uv_flags_level[ip] = level[ic] + 1
                uv_flags_type[ip] = mu[ic]
        if nu[ic] <= 0:
            if nu1[ic] >= 0:
                ip += 1
                uv_index_z_nm[ip] = ic
                uv_index_z_nmu[ip] = nu1[ic]
                uv_flags_dir[ip] = 1
                uv_flags_level[ip] = level[ic]
                uv_flags_type[ip] = nu[ic]
        else:
            if nu1[ic] >= 0:
                ip += 1
                uv_index_z_nm[ip] = ic
                uv_index_z_nmu[ip] = nu1[ic]
                uv_flags_dir[ip] = 1
                uv_flags_level[ip] = level[ic] + 1
                uv_flags_type[ip] = nu[ic]
            if nu2[ic] >= 0:
                ip += 1
                uv_index_z_nm[ip] = ic
                uv_index_z_nmu[ip] = nu2[ic]
                uv_flags_dir[ip] = 1
                uv_flags_level[ip] = level[ic] + 1
                uv_flags_type[ip] = nu[ic]
    return npuv, dict(
        uv_index_z_nm=uv_index_z_nm,
        uv_index_z_nmu=uv_index_z_nmu,
        uv_flags_dir=uv_flags_dir,
        uv_flags_level=uv_flags_level,
        uv_flags_type=uv_flags_type,
    )


def geometry_from_grid(grid, params: BuildParams) -> Geometry:
    """Everything the serial ``build`` derives from the grid before its level loop."""
    refi = params.nr_subgrid_pixels
    if refi % 2 != 0:
        raise ValueError("nr_subgrid_pixels must be an even number for subgrid table")
    nr_cells = grid.sizes["mesh2d_nFaces"]
    nr_ref_levs = grid.attrs["nr_levels"]
    level = grid["level"].values[:] - 1
    n = grid["n"].values[:] - 1
    m = grid["m"].values[:] - 1
    nu = grid["nu"].values[:]
    nu1 = grid["nu1"].values[:] - 1
    nu2 = grid["nu2"].values[:] - 1
    mu = grid["mu"].values[:]
    mu1 = grid["mu1"].values[:] - 1
    mu2 = grid["mu2"].values[:] - 1
    npuv, uv = uv_tables(level, nu, nu1, nu2, mu, mu1, mu2)
    yc = np.asarray(grid.grid.face_coordinates[:, 1])

    ifirst = np.zeros(nr_ref_levs, dtype=int)
    ilast = np.zeros(nr_ref_levs, dtype=int)
    ireflast = -1
    # vectorised copy of: for ic: if level[ic] > ireflast: ifirst[level]=ic; ireflast=..
    for ic in np.flatnonzero(np.diff(np.r_[-1, np.maximum.accumulate(level)]) > 0):
        if level[ic] > ireflast:
            ifirst[level[ic]] = ic
            ireflast = level[ic]
    for ilev in range(nr_ref_levs - 1):
        ilast[ilev] = ifirst[ilev + 1] - 1
    ilast[nr_ref_levs - 1] = nr_cells - 1

    attrs = {
        k: grid.attrs[k]
        for k in ("x0", "y0", "dx", "dy", "rotation", "mmax", "nmax", "nr_levels")
    }
    geo = Geometry(
        attrs=attrs,
        level=level,
        n=n,
        m=m,
        yc=yc,
        npuv=npuv,
        ifirst=ifirst,
        ilast=ilast,
        **uv,
    )
    for ilev in range(nr_ref_levs):
        sl = slice(ifirst[ilev], ilast[ilev] + 1)
        if ilast[ilev] - ifirst[ilev] + 1 <= 0:
            geo.levels.append(None)
            continue
        n0, n1 = int(np.min(n[sl])), int(np.max(n[sl]))
        m0, m1 = int(np.min(m[sl])), int(np.max(m[sl]))
        dx = grid.attrs["dx"] / 2**ilev
        dy = grid.attrs["dy"] / 2**ilev
        nrcb = int(np.floor(params.nrmax / refi))
        geo.levels.append(
            LevelInfo(
                ilev=ilev,
                n0=n0,
                n1=n1,
                m0=m0,
                m1=m1,
                dx=dx,
                dy=dy,
                dxp=dx / refi,
                dyp=dy / refi,
                nrcb=nrcb,
                nrbn=int(np.ceil((n1 - n0 + 1) / nrcb)),
                nrbm=int(np.ceil((m1 - m0 + 1) / nrcb)),
            )
        )
    return geo


def _block_bounds(li: LevelInfo, ii: int, jj: int):
    bn0 = li.n0 + jj * li.nrcb
    bn1 = min(bn0 + li.nrcb - 1, li.n1) + 1
    bm0 = li.m0 + ii * li.nrcb
    bm1 = min(bm0 + li.nrcb - 1, li.m1) + 1
    return bn0, bn1, bm0, bm1


def _group_by_block(li: LevelInfo, nn: np.ndarray, mm: np.ndarray, idx: np.ndarray):
    """{ib: idx[in block ib], ascending} for points with grid indices (nn, mm).

    Block membership is the serial test ``bn0 <= n < bn1 and bm0 <= m < bm1``; points
    in no block (outside [n0, n1] x [m0, m1]) are dropped, as there."""
    jj = np.floor_divide(nn - li.n0, li.nrcb)
    ii = np.floor_divide(mm - li.m0, li.nrcb)
    ok = (jj >= 0) & (jj < li.nrbn) & (ii >= 0) & (ii < li.nrbm)
    # the serial bounds clip the last block at n1 / m1 (+1); a point beyond is in none
    ok &= (nn <= li.n1) & (mm <= li.m1)
    ib = ii * li.nrbn + jj
    ib, sel = ib[ok], idx[ok]
    order = np.argsort(ib, kind="stable")  # stable: keeps ascending idx within a block
    ib, sel = ib[order], sel[order]
    cuts = np.flatnonzero(np.diff(ib)) + 1
    starts = np.r_[0, cuts]
    return {int(ib[s]): grp for s, grp in zip(starts, np.split(sel, cuts))}


def cell_blocks(geo: Geometry, ilev: int) -> dict:
    li = geo.levels[ilev]
    idx = np.arange(geo.ifirst[ilev], geo.ilast[ilev] + 1, dtype=int)
    return _group_by_block(li, geo.n[idx], geo.m[idx], idx)


def uv_blocks(geo: Geometry, ilev: int) -> dict:
    li = geo.levels[ilev]
    ip = np.flatnonzero(geo.uv_flags_level == ilev)
    ref = np.where(
        geo.uv_flags_type[ip] <= 0, geo.uv_index_z_nm[ip], geo.uv_index_z_nmu[ip]
    )
    return _group_by_block(li, geo.n[ref], geo.m[ref], ip)


def check_index_tables(grid, geo: Geometry, levels=None, max_blocks=None) -> dict:
    """Compare the vectorised index tables against the serial builder's loops."""
    level = grid["level"].values[:] - 1
    args = [
        level,
        grid["nu"].values[:],
        grid["nu1"].values[:] - 1,
        grid["nu2"].values[:] - 1,
        grid["mu"].values[:],
        grid["mu1"].values[:] - 1,
        grid["mu2"].values[:] - 1,
    ]
    npuv, uv = uv_tables_serial(*args)
    rep = {"npuv": npuv == geo.npuv}
    for k, v in uv.items():
        rep[k] = bool(np.array_equal(v, getattr(geo, k)))
    n, m = geo.n, geo.m
    for ilev in levels if levels is not None else range(len(geo.levels)):
        li = geo.levels[ilev]
        cb, ub = cell_blocks(geo, ilev), uv_blocks(geo, ilev)
        cells_lev = np.arange(geo.ifirst[ilev], geo.ilast[ilev] + 1)
        uv_lev = np.flatnonzero(geo.uv_flags_level == ilev)
        nb = 0
        for ii in range(li.nrbm):
            for jj in range(li.nrbn):
                ib = ii * li.nrbn + jj
                if max_blocks is not None and nb >= max_blocks:
                    break
                bn0, bn1, bm0, bm1 = _block_bounds(li, ii, jj)
                c = cells_lev[
                    (n[cells_lev] >= bn0)
                    & (n[cells_lev] < bn1)
                    & (m[cells_lev] >= bm0)
                    & (m[cells_lev] < bm1)
                ]
                got = cb.get(ib, np.zeros(0, dtype=int))
                ok_c = np.array_equal(c, got)
                ref = np.where(
                    geo.uv_flags_type[uv_lev] <= 0,
                    geo.uv_index_z_nm[uv_lev],
                    geo.uv_index_z_nmu[uv_lev],
                )
                u = uv_lev[
                    (n[ref] >= bn0) & (n[ref] < bn1) & (m[ref] >= bm0) & (m[ref] < bm1)
                ]
                ok_u = np.array_equal(u, ub.get(ib, np.zeros(0, dtype=int)))
                if not (ok_c and ok_u):
                    rep.setdefault("bad_blocks", []).append((ilev, ib, ok_c, ok_u))
                nb += 1
        rep[f"lev{ilev}_blocks_checked"] = nb
    return rep


# --------------------------------------------------------------------------------------
# workers
# --------------------------------------------------------------------------------------
_W: dict = {}


class _ParseSelf:
    """Stand-in ``self`` for ``SfincsModel._parse_datasets_elevation`` /
    ``_parse_roughness_list``: both read only ``self.data_catalog`` and ``self.bbox``.
    ``bbox`` is the parent's value (the model's WGS84 grid bounds, which hydromt
    recomputes from all 4.9 M faces on every call)."""

    def __init__(self, data_catalog, bbox):
        self.data_catalog = data_catalog
        self.bbox = bbox


def worker_init(spec: dict) -> None:
    """Spawned-worker initialiser: env, overlay wrapper, parsed elevation lists."""
    t0 = time.time()
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("NUMBA_NUM_THREADS", "1")
    os.environ["GDAL_CACHEMAX"] = str(spec.get("gdal_cachemax_mb", 512))
    for p in spec.get("sys_path", []):
        if p not in sys.path:
            sys.path.insert(0, p)
    import dask  # noqa: PLC0415
    import pyproj  # noqa: F401,PLC0415  (before hydromt_sfincs: native double-free)

    dask.config.set(scheduler="synchronous")
    from hydromt_sfincs.components.quadtree import (  # noqa: PLC0415
        subgrid_quadtree_builder as bld,
    )

    from hydromt_sfincs import SfincsModel  # noqa: PLC0415

    if spec.get("timing"):
        _install_merge_timer(bld)  # BEFORE the overlay wrapper captures the function
    if spec["install_overlay"]:
        import rebuild_subgrid  # noqa: PLC0415  (scripts/ is on sys_path)

        rebuild_subgrid.install_overlay_merge()

    sf = SfincsModel(root=spec["root"], data_libs=spec["data_libs"], mode="r+")
    ps = _ParseSelf(sf.data_catalog, spec["bbox"])
    elev = []
    for res_subgrid in spec["res_subgrid"]:
        elev.append(
            SfincsModel._parse_datasets_elevation(
                ps, spec["elevation_list"], res=res_subgrid
            )
        )
    rough = (
        SfincsModel._parse_roughness_list(ps, spec["roughness_list"])
        if spec["roughness_list"]
        else []
    )
    _W.update(
        bld=bld,
        elev=elev,
        rough=rough,
        crs=spec["crs"],
        attrs=spec["attrs"],
        params=BuildParams(**spec["params"]),
        levels=spec["levels"],
        work_dir=Path(spec["work_dir"]),
        timing=bool(spec.get("timing")),
        init_s=time.time() - t0,
        sf=sf,
    )


def _install_merge_timer(bld) -> None:
    """Time hydromt's own ``merge_multi_dataarrays`` (the tiers) apart from the overlay
    paint the ``--overlay`` wrapper adds around it: installed BEFORE that wrapper, so the
    wrapper's captured ``orig`` is this timed function. Timing only; values untouched."""
    inner = bld.merge_multi_dataarrays

    def timed(*a, **kw):
        t = time.perf_counter()
        try:
            return inner(*a, **kw)
        finally:
            _tick("hydromt_merge_" + _CUR[0], time.perf_counter() - t)

    bld.merge_multi_dataarrays = timed


_CUR = ["dep"]
_TIMERS: dict = {}


def _tick(key: str, dt: float) -> None:
    _TIMERS[key] = _TIMERS.get(key, 0.0) + dt


def _rss_gb() -> float:
    import resource  # noqa: PLC0415

    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6


def _cur_rss_gb() -> float:
    try:
        with open("/proc/self/statm") as f:
            return int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 1e9
    except OSError:
        return float("nan")


def _save(path: Path, obj) -> int:
    data = _compress(pickle.dumps(obj, protocol=5))
    tmp = path.with_name(path.name + f".tmp{os.getpid()}")
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    return len(data)


def _load(path: Path):
    with open(path, "rb") as f:
        return pickle.loads(_decompress(f.read()))


def _shuffle(a: np.ndarray) -> tuple:
    """(dtype, shape, byte-planes): a float raster compresses ~2x better this way."""
    a = np.ascontiguousarray(a)
    return (a.dtype.str, a.shape, a.view(np.uint8).reshape(-1, a.itemsize).T.tobytes())


def _unshuffle(t: tuple) -> np.ndarray:
    dt, shape, b = t
    dt = np.dtype(dt)
    planes = np.frombuffer(b, dtype=np.uint8).reshape(dt.itemsize, -1)
    return np.ascontiguousarray(planes.T).view(dt).reshape(shape)


def task_path(work_dir: Path, kind: str, ilev: int, ib: int) -> Path:
    return work_dir / f"lev{ilev}" / f"{kind}_{ib:05d}{_EXT}"


def raster_path(work_dir: Path, ilev: int, ib: int) -> Path:
    return work_dir / f"lev{ilev}" / f"ras_{ib:05d}{_EXT}"


def run_cell_task(task: dict) -> dict:
    """One cell-centre block: the serial builder's code, verbatim but for indices."""
    from hydromt_sfincs import utils  # noqa: PLC0415

    t0 = time.perf_counter()
    _TIMERS.clear()
    bld, p, a = _W["bld"], _W["params"], _W["attrs"]
    ilev, ib = task["ilev"], task["ib"]
    bn0, bn1, bm0, bm1 = task["bounds"]
    li = _W["levels"][ilev]
    idx = task["idx"]
    refi = p.nr_subgrid_pixels

    t = time.perf_counter()
    da_sbg = utils.make_regular_grid(
        x0=a["x0"],
        y0=a["y0"],
        dx=li["dx"],
        dy=li["dy"],
        mmax=bm1,
        nmax=bn1,
        rotation=a["rotation"],
        mmin=bm0,
        nmin=bn0,
        refi=refi,
        uv_points=False,
        crs=_W["crs"],
    )
    _tick("grid", time.perf_counter() - t)
    t = time.perf_counter()
    _CUR[0] = "dep"
    da_dep = bld.merge_multi_dataarrays(
        da_list=_W["elev"][ilev],
        da_like=da_sbg,
        buffer_cells=p.buffer_cells,
        interp_method=p.interp_method,
    )
    _tick("merge_dep", time.perf_counter() - t)
    t = time.perf_counter()
    nnan = int(np.sum(np.isnan(da_dep.values)))
    da_dep = da_dep.raster.interpolate_na(method="rio_idw", extrapolate=True)
    zg = da_dep.values
    zg = zg * p.depth_factor
    zg = np.maximum(zg, p.zmin)
    zg = np.minimum(zg, p.zmax)
    _tick("interp_na", time.perf_counter() - t)
    t = time.perf_counter()
    z_zmin, z_zmax, z_volmax, z_level = bld.process_block_cells(
        zg,
        idx.size,
        task["n"],
        task["m"],
        task["yc"],
        bn0,
        bm0,
        li["dxp"],
        li["dyp"],
        refi,
        p.nr_levels,
        p.max_gradient,
        _W["crs"].is_geographic,
    )
    _tick("kernel", time.perf_counter() - t)
    t = time.perf_counter()
    nbytes = _save(
        task_path(_W["work_dir"], "cells", ilev, ib),
        dict(idx=idx, z_zmin=z_zmin, z_zmax=z_zmax, z_volmax=z_volmax, z_level=z_level),
    )
    _tick("save", time.perf_counter() - t)
    return dict(
        kind="cells",
        ilev=ilev,
        ib=ib,
        n=int(idx.size),
        nan_px=nnan,
        wall=time.perf_counter() - t0,
        timers=dict(_TIMERS),
        maxrss_gb=_rss_gb(),
        rss_gb=_cur_rss_gb(),
        pid=os.getpid(),
        bytes=nbytes,
    )


def run_uv_task(task: dict) -> dict:
    """One uv-point block: the serial builder's code, verbatim but for indices."""
    import xarray as xr  # noqa: PLC0415

    from hydromt_sfincs import utils  # noqa: PLC0415

    t0 = time.perf_counter()
    _TIMERS.clear()
    bld, p, a = _W["bld"], _W["params"], _W["attrs"]
    ilev, ib = task["ilev"], task["ib"]
    bn0, bn1, bm0, bm1 = task["bounds"]
    li = _W["levels"][ilev]
    ipx = task["idx"]
    refi = p.nr_subgrid_pixels

    t = time.perf_counter()
    da_sbg_uv = utils.make_regular_grid(
        x0=a["x0"],
        y0=a["y0"],
        dx=li["dx"],
        dy=li["dy"],
        mmax=bm1,
        nmax=bn1,
        rotation=a["rotation"],
        mmin=bm0,
        nmin=bn0,
        refi=refi,
        uv_points=True,
        crs=_W["crs"],
    )
    _tick("grid", time.perf_counter() - t)
    t = time.perf_counter()
    _CUR[0] = "dep"
    da_dep = bld.merge_multi_dataarrays(
        da_list=_W["elev"][ilev],
        da_like=da_sbg_uv,
        buffer_cells=p.buffer_cells,
        interp_method=p.interp_method,
    )
    _tick("merge_dep", time.perf_counter() - t)
    t = time.perf_counter()
    nnan = int(np.sum(np.isnan(da_dep.values)))
    da_dep = da_dep.raster.interpolate_na(method="rio_idw", extrapolate=True)
    da_dep.values = da_dep.values * p.depth_factor
    da_dep = np.maximum(da_dep, p.zmin)
    da_dep = np.minimum(da_dep, p.zmax)
    zg = da_dep.values
    _tick("interp_na", time.perf_counter() - t)

    t = time.perf_counter()
    rough = _W["rough"]
    if len(rough) > 0:
        _CUR[0] = "man"
        da_man = bld.merge_multi_dataarrays(
            da_list=rough,
            da_like=da_sbg_uv,
            interp_method="linear",
            buffer_cells=p.buffer_cells,
        )
        da_man0 = xr.where(da_dep >= p.manning_level, p.manning_land, p.manning_water)
        da_man = da_man.where(~np.isnan(da_man), da_man0)
    else:
        da_man = xr.where(da_dep >= p.manning_level, p.manning_land, p.manning_water)
        da_man.raster.set_nodata(np.nan)
    manning_grid = da_man.values
    _tick("merge_man", time.perf_counter() - t)

    t = time.perf_counter()
    x_dim_dep, y_dim_dep = da_dep.raster.x_dim, da_dep.raster.y_dim
    win = (
        bm0 * p.nr_subgrid_pixels,
        bn0 * p.nr_subgrid_pixels,
        da_dep[:-refi, :-refi].sizes[x_dim_dep],
        da_dep[:-refi, :-refi].sizes[y_dim_dep],
    )
    # Stored as the tif's float32 via np.require — exactly the cast rasterio's
    # DatasetWriter.write applies to the serial builder's float64 block.
    ras = dict(window=win)
    if p.write_dep_tif:
        ras["dep"] = _shuffle(
            np.require(da_dep[:-refi, :-refi].values, np.float32, "C")
        )
    if p.write_man_tif:
        ras["man"] = _shuffle(
            np.require(da_man[:-refi, :-refi].values, np.float32, "C")
        )
    _tick("slice", time.perf_counter() - t)

    t = time.perf_counter()
    (uv_zmin, uv_zmax, uv_havg, uv_nrep, uv_pwet, uv_ffit, uv_navg) = (
        bld.process_block_uv_points(
            zg,
            manning_grid,
            ipx.size,
            task["n_nm"],
            task["m_nm"],
            task["n_nmu"],
            task["m_nmu"],
            task["z_zmin_nm"],
            task["z_zmin_nmu"],
            task["uv_flags_type"],
            task["uv_flags_dir"],
            bn0,
            bm0,
            refi,
            p.nr_levels,
            p.huthresh,
            p.weight_option,
            p.roughness_type,
        )
    )
    _tick("kernel", time.perf_counter() - t)
    t = time.perf_counter()
    rbytes = 0
    if p.write_dep_tif or p.write_man_tif:
        rbytes = _save(raster_path(_W["work_dir"], ilev, ib), ras)
    tbytes = _save(
        task_path(_W["work_dir"], "uv", ilev, ib),
        dict(
            idx=ipx,
            uv_zmin=uv_zmin,
            uv_zmax=uv_zmax,
            uv_havg=uv_havg,
            uv_nrep=uv_nrep,
            uv_pwet=uv_pwet,
            uv_ffit=uv_ffit,
            uv_navg=uv_navg,
        ),
    )
    _tick("save", time.perf_counter() - t)
    return dict(
        kind="uv",
        ilev=ilev,
        ib=ib,
        n=int(ipx.size),
        nan_px=nnan,
        wall=time.perf_counter() - t0,
        timers=dict(_TIMERS),
        maxrss_gb=_rss_gb(),
        rss_gb=_cur_rss_gb(),
        pid=os.getpid(),
        bytes=rbytes + tbytes,
    )


def run_task(task: dict) -> dict:
    try:
        if task["kind"] == "cells":
            return run_cell_task(task)
        return run_uv_task(task)
    except Exception:  # noqa: BLE001  (surface the worker traceback in the parent)
        raise RuntimeError(
            f"task {task['kind']} lev{task['ilev']} block {task['ib']}:\n"
            + traceback.format_exc()
        ) from None


TIF_NAMES = {"dep": "dep_subgrid_lev{}.tif", "man": "manning_subgrid_lev{}.tif"}


def write_tif_kind(spec: dict) -> dict:
    """One per-level tif (dep or manning), in a writer PROCESS: the serial profile
    (created empty exactly as the serial builder does), the serial windows in the
    serial block order, then hydromt's ``build_overviews``."""
    import logging  # noqa: PLC0415

    import rasterio  # noqa: PLC0415
    from rasterio.windows import Window  # noqa: PLC0415

    from hydromt_sfincs import utils  # noqa: PLC0415

    os.environ.setdefault("GDAL_CACHEMAX", "2048")  # before this process's 1st read
    t0 = time.time()
    fn, k, work = spec["fn"], spec["kind"], Path(spec["work_dir"])
    with rasterio.open(fn, "w", **spec["profile"]):
        pass
    with rasterio.Env(GDAL_NUM_THREADS=str(spec["threads"])):
        with rasterio.open(fn, "r+") as dst:
            for ib in spec["blocks"]:
                r = _load(raster_path(work, spec["ilev"], ib))
                dst.write(_unshuffle(r[k]), window=Window(*r["window"]), indexes=1)
        t1 = time.time()
        utils.build_overviews(
            fn=fn,
            resample_method="average",
            overviews="auto",
            logger=logging.getLogger("subgrid_parallel"),
        )
    return {"write_s": round(t1 - t0, 1), "overview_s": round(time.time() - t1, 1)}


# --------------------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------------------
def _file_sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def _level_dict(li: LevelInfo) -> dict:
    return dict(li.__dict__)


class ParallelSubgridBuilder:
    """Build the quadtree subgrid tables for the model at ``root`` in parallel.

    ``root`` must hold ``sfincs.nc`` + ``sfincs.inp`` (the frozen mesh). The result is
    written exactly where ``sf.quadtree_subgrid.create(...); .write()`` would put it:
    ``root/sfincs_subgrid.nc`` and ``root/subgrid/{dep,manning}_subgrid_lev<L>.tif``.
    """

    def __init__(
        self,
        root: Path,
        data_libs: list[str],
        elevation_list: list[dict],
        roughness_list: list[dict],
        params: BuildParams,
        work_dir: Path,
        workers: int = 8,
        install_overlay: bool = True,
        gdal_cachemax_mb: int = 512,
        max_tasks_per_child: int | None = None,
        timing: bool = True,
        tif_threads: int = 8,
        heavy_levels: tuple = (0,),
        heavy_cap: int | None = None,
        log=print,
    ):
        self.root = Path(root)
        self.data_libs = data_libs
        self.elevation_list = elevation_list
        self.roughness_list = roughness_list
        self.params = params
        self.work_dir = Path(work_dir)
        self.workers = workers
        self.install_overlay = install_overlay
        self.gdal_cachemax_mb = gdal_cachemax_mb
        self.max_tasks_per_child = max_tasks_per_child
        self.timing = timing
        self.tif_threads = tif_threads
        self.heavy_levels = set(heavy_levels)
        self.heavy_cap = heavy_cap
        self.log = log
        self.stats: list[dict] = []

    # -- setup -------------------------------------------------------------------------
    def open_model(self):
        import pyproj  # noqa: F401,PLC0415

        from hydromt_sfincs import SfincsModel  # noqa: PLC0415

        sf = SfincsModel(root=str(self.root), data_libs=self.data_libs, mode="r+")
        sf.quadtree_grid.read()
        return sf

    def manifest(self, sf) -> dict:
        import hydromt_sfincs  # noqa: PLC0415

        bfile = Path(hydromt_sfincs.__file__).parents[1] / BUILDER_FILE
        scripts = Path(__file__).resolve().parents[1] / "scripts" / "rebuild_subgrid.py"
        cats = {str(p): _file_sha(Path(p)) for p in self.data_libs if Path(p).is_file()}
        return {
            "mesh_sha256": _file_sha(self.root / "sfincs.nc"),
            "elevation_list": self.elevation_list,
            "roughness_list": self.roughness_list,
            "params": self.params.as_dict(),
            "builder_sha256": _file_sha(bfile),
            "overlay_wrapper_sha256": _file_sha(scripts),
            "install_overlay": self.install_overlay,
            "data_catalogs": cats,
        }

    def prepare(self, sf) -> None:
        self.grid = sf.quadtree_grid.data
        t = time.time()
        self.geo = geometry_from_grid(self.grid, self.params)
        self.log(f"    geometry: npuv={self.geo.npuv} in {time.time() - t:.1f}s")
        res = self.grid.attrs["dx"]
        if sf.crs.is_geographic:
            res = res * 111111.0
        self.res_subgrid = [
            res / (2**ilev) / self.params.nr_subgrid_pixels
            for ilev in range(self.grid.attrs["nr_levels"])
        ]
        t = time.time()
        self.bbox = tuple(float(v) for v in sf.bbox)
        self.log(f"    model bbox (WGS84) {self.bbox} in {time.time() - t:.1f}s")
        self.crs = self.grid.grid.crs

    def spec(self) -> dict:
        here = Path(__file__).resolve().parents[1]
        return dict(
            root=str(self.root),
            data_libs=self.data_libs,
            bbox=self.bbox,
            res_subgrid=self.res_subgrid,
            elevation_list=self.elevation_list,
            roughness_list=self.roughness_list,
            crs=self.crs,
            attrs=self.geo.attrs,
            params=self.params.as_dict(),
            levels=[_level_dict(li) if li else None for li in self.geo.levels],
            work_dir=str(self.work_dir),
            install_overlay=self.install_overlay,
            gdal_cachemax_mb=self.gdal_cachemax_mb,
            timing=self.timing,
            sys_path=[str(here), str(here / "scripts")],
        )

    # -- tasks -------------------------------------------------------------------------
    def cell_tasks(self, levels=None, blocks=None) -> list[dict]:
        geo, out = self.geo, []
        for ilev, li in enumerate(geo.levels):
            if li is None or (levels is not None and ilev not in levels):
                continue
            for ib, idx in sorted(cell_blocks(geo, ilev).items()):
                if blocks is not None and ib not in blocks.get(ilev, ()):
                    continue
                ii, jj = divmod(ib, li.nrbn)
                out.append(
                    dict(
                        kind="cells",
                        ilev=ilev,
                        ib=ib,
                        bounds=_block_bounds(li, ii, jj),
                        idx=idx,
                        n=geo.n[idx],
                        m=geo.m[idx],
                        yc=geo.yc[idx],
                    )
                )
        return out

    def uv_tasks(self, z_zmin: np.ndarray, levels=None, blocks=None) -> list[dict]:
        geo, out = self.geo, []
        for ilev, li in enumerate(geo.levels):
            if li is None or (levels is not None and ilev not in levels):
                continue
            for ib, ipx in sorted(uv_blocks(geo, ilev).items()):
                if blocks is not None and ib not in blocks.get(ilev, ()):
                    continue
                ii, jj = divmod(ib, li.nrbn)
                nm = geo.uv_index_z_nm[ipx]
                nmu = geo.uv_index_z_nmu[ipx]
                out.append(
                    dict(
                        kind="uv",
                        ilev=ilev,
                        ib=ib,
                        bounds=_block_bounds(li, ii, jj),
                        idx=ipx,
                        n_nm=geo.n[nm],
                        m_nm=geo.m[nm],
                        n_nmu=geo.n[nmu],
                        m_nmu=geo.m[nmu],
                        # serial: float64 arrays filled from the float32 table
                        z_zmin_nm=z_zmin[nm].astype(float),
                        z_zmin_nmu=z_zmin[nmu].astype(float),
                        uv_flags_type=geo.uv_flags_type[ipx],
                        uv_flags_dir=geo.uv_flags_dir[ipx],
                    )
                )
        return out

    def _pending(self, tasks: list[dict]) -> list[dict]:
        return [
            t
            for t in tasks
            if not task_path(self.work_dir, t["kind"], t["ilev"], t["ib"]).exists()
        ]

    def run_pool(
        self,
        tasks: list[dict],
        label: str,
        retries: int = 3,
        on_level_done=None,
        finest_first: bool = False,
    ) -> None:
        """Run ``tasks`` on the pool, at most ``workers`` in flight.

        Order: the HEAVY level (lev0: 25 x 25 km windows, ~7 s and up to ~18 GB per
        block) first but at most ``heavy_cap`` of them at once — all workers on lev0
        blocks together peaked at 163 GB with 16 workers — then the rest coarsest
        first, or with ``finest_first`` finest first (phase 2: lev3's big tifs are then
        written while the pool is still busy).

        ``on_level_done(ilev)`` is called (in this process) as soon as every task of a
        level has a result file — phase 2 uses it to write that level's tifs."""
        heavy = self.heavy_levels
        lev_key = (lambda L: -L) if finest_first else (lambda L: L)
        tasks = sorted(
            self._pending(tasks),
            key=lambda t: (t["ilev"] not in heavy, lev_key(t["ilev"]), t["ib"]),
        )
        if not tasks:
            self.log(f"    {label}: all blocks checkpointed")
            return
        cap = self.heavy_cap or max(2, self.workers // 4)
        spec = self.spec()
        for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
            os.environ.setdefault(k, "1")
        # glibc: a FIXED mmap threshold, so the per-block rasters (tens of MB) are
        # mmapped and handed back on free instead of fragmenting the heap. Read by the
        # spawned workers at start-up (GDAL_CACHEMAX is set in worker_init instead:
        # setting it here would also shrink THIS process's cache). Allocator only.
        os.environ.setdefault("MALLOC_MMAP_THRESHOLD_", str(1 << 20))
        attempt = 0
        while tasks:
            n = len(tasks)
            left: dict = {}
            for t in tasks:
                left[t["ilev"]] = left.get(t["ilev"], 0) + 1
            queue = list(tasks)
            t0 = time.time()
            self.log(
                f"    {label}: {n} blocks on {self.workers} workers "
                f"(<= {cap} lev{sorted(heavy)} blocks at once)",
                flush=True,
            )
            done = 0
            try:
                with ProcessPoolExecutor(
                    max_workers=self.workers,
                    mp_context=get_context("spawn"),
                    initializer=worker_init,
                    initargs=(spec,),
                    max_tasks_per_child=self.max_tasks_per_child,
                ) as ex:
                    inflight: dict = {}

                    def fill():
                        while len(inflight) < self.workers and queue:
                            nh = sum(t["ilev"] in heavy for t in inflight.values())
                            k = next(
                                (
                                    i
                                    for i, t in enumerate(queue)
                                    if t["ilev"] not in heavy or nh < cap
                                ),
                                None,
                            )
                            if k is None:
                                return
                            t = queue.pop(k)
                            inflight[ex.submit(run_task, t)] = t

                    fill()
                    last = time.time()
                    while inflight:
                        fin, _ = wait(set(inflight), return_when=FIRST_COMPLETED)
                        for f in fin:
                            inflight.pop(f)
                            r = f.result()
                            self.stats.append(r)
                            done += 1
                            left[r["ilev"]] -= 1
                            if left[r["ilev"]] == 0 and on_level_done is not None:
                                on_level_done(r["ilev"])
                        fill()
                        if time.time() - last > 60 or not inflight:
                            last = time.time()
                            rss = max(s["maxrss_gb"] for s in self.stats[-done:])
                            self.log(
                                f"      {label} {done}/{n} "
                                f"{time.time() - t0:.0f}s maxrss/worker {rss:.1f} GB",
                                flush=True,
                            )
            except BrokenProcessPool as e:
                attempt += 1
                tasks = self._pending(tasks)
                self.log(f"    {label}: pool broke ({e}); {len(tasks)} left")
                if attempt > retries:
                    raise
                continue
            tasks = self._pending(tasks)
            if tasks:
                raise RuntimeError(f"{label}: {len(tasks)} blocks have no result file")

    # -- assembly ----------------------------------------------------------------------
    def assemble(self, z: dict | None = None) -> dict:
        """The 11 tables, laid out as the serial builder's arrays (zero where it never
        writes). ``z`` = the cell tables already filled by ``fill_cells``."""
        p, geo = self.params, self.geo
        npuv, nl = geo.npuv, p.nr_levels
        if z is None:
            z = self.empty_cells()
            self.fill_cells(z)
        arr = dict(
            **z,
            uv_zmin=np.zeros(npuv, dtype=np.float32),
            uv_zmax=np.zeros(npuv, dtype=np.float32),
            uv_havg=np.zeros((nl, npuv), dtype=np.float32),
            uv_nrep=np.zeros((nl, npuv), dtype=np.float32),
            uv_pwet=np.zeros((nl, npuv), dtype=np.float32),
            uv_ffit=np.zeros(npuv, dtype=np.float32),
            uv_navg=np.zeros(npuv, dtype=np.float32),
        )
        for li in geo.levels:
            if li is None:
                continue
            for ib in sorted(uv_blocks(geo, li.ilev)):
                r = _load(task_path(self.work_dir, "uv", li.ilev, ib))
                i = r["idx"]
                for k in ("uv_zmin", "uv_zmax", "uv_ffit", "uv_navg"):
                    arr[k][i] = r[k]
                for k in ("uv_havg", "uv_nrep", "uv_pwet"):
                    arr[k][:, i] = r[k]
        return arr

    def empty_cells(self) -> dict:
        npc, nl = self.geo.level.size, self.params.nr_levels
        return dict(
            z_zmin=np.zeros(npc, dtype=np.float32),
            z_zmax=np.zeros(npc, dtype=np.float32),
            z_volmax=np.zeros(npc, dtype=np.float32),
            z_level=np.zeros((nl, npc), dtype=np.float32),
        )

    def fill_cells(self, arr: dict, levels=None) -> None:
        for t in self.cell_tasks(levels):
            r = _load(task_path(self.work_dir, "cells", t["ilev"], t["ib"]))
            i = r["idx"]
            arr["z_zmin"][i] = r["z_zmin"]
            arr["z_zmax"][i] = r["z_zmax"]
            arr["z_volmax"][i] = r["z_volmax"]
            arr["z_level"][:, i] = r["z_level"]

    @staticmethod
    def dataset(arr: dict):
        """The serial builder's ``self.ds``, verbatim."""
        import xarray as xr  # noqa: PLC0415

        ds = xr.Dataset()
        ds.attrs["version"] = "1.0"
        ds["z_zmin"] = xr.DataArray(arr["z_zmin"], dims=["np"])
        ds["z_zmax"] = xr.DataArray(arr["z_zmax"], dims=["np"])
        ds["z_volmax"] = xr.DataArray(arr["z_volmax"], dims=["np"])
        ds["z_level"] = xr.DataArray(
            np.transpose(arr["z_level"]), dims=["np", "levels"]
        )
        ds["uv_zmin"] = xr.DataArray(arr["uv_zmin"], dims=["npuv"])
        ds["uv_zmax"] = xr.DataArray(arr["uv_zmax"], dims=["npuv"])
        ds["uv_havg"] = xr.DataArray(
            np.transpose(arr["uv_havg"]), dims=["npuv", "levels"]
        )
        ds["uv_nrep"] = xr.DataArray(
            np.transpose(arr["uv_nrep"]), dims=["npuv", "levels"]
        )
        ds["uv_pwet"] = xr.DataArray(
            np.transpose(arr["uv_pwet"]), dims=["npuv", "levels"]
        )
        ds["uv_ffit"] = xr.DataArray(arr["uv_ffit"], dims=["npuv"])
        ds["uv_navg"] = xr.DataArray(arr["uv_navg"], dims=["npuv"])
        return ds

    def tif_profile(self, ilev: int) -> dict:
        """The serial builder's COG profile for level ``ilev``."""
        import rasterio  # noqa: F401,PLC0415

        from hydromt_sfincs import utils  # noqa: PLC0415

        a, refi = self.geo.attrs, self.params.nr_subgrid_pixels
        dx = a["dx"] / 2**ilev
        dy = a["dy"] / 2**ilev
        da_transform, da_width, da_height = utils.make_regular_grid_transform(
            x0=a["x0"],
            y0=a["y0"],
            dx=dx,
            dy=dy,
            mmax=(a["mmax"]) * 2**ilev,
            nmax=(a["nmax"]) * 2**ilev,
            rotation=a["rotation"],
            mmin=0,
            nmin=0,
            refi=refi,
            uv_points=True,
        )
        return dict(
            driver="GTiff",
            width=da_width,
            height=da_height,
            count=1,
            dtype=np.float32,
            crs=self.crs,
            transform=da_transform,
            tiled=True,
            blockxsize=256,
            blockysize=256,
            compress="deflate",
            predictor=2,
            profile="COG",
            nodata=np.nan,
            BIGTIFF="YES",
        )

    def submit_level_tifs(self, ilev: int, out_dir: Path, pool) -> dict | None:
        """Queue one level's dep + manning tifs on ``pool`` (a PROCESS pool:
        rasterio's ``build_overviews`` holds the GIL for minutes, which in a thread
        stalled this process's pool bookkeeping and so every worker). None if the
        level's tifs are already checkpointed (``.lev<L>.done``)."""
        p = self.params
        kinds = [
            k for k, on in (("dep", p.write_dep_tif), ("man", p.write_man_tif)) if on
        ]
        fns = {k: out_dir / TIF_NAMES[k].format(ilev) for k in kinds}
        marker = out_dir / f".lev{ilev}.done"
        if not kinds or (marker.exists() and all(f.exists() for f in fns.values())):
            return None
        out_dir.mkdir(parents=True, exist_ok=True)
        blocks = sorted(uv_blocks(self.geo, ilev))
        prof = self.tif_profile(ilev)
        return {
            k: pool.submit(
                write_tif_kind,
                dict(
                    fn=str(fns[k]),
                    profile=prof,
                    kind=k,
                    ilev=ilev,
                    blocks=blocks,
                    work_dir=str(self.work_dir),
                    threads=self.tif_threads,
                ),
            )
            for k in kinds
        }

    def finish_level_tifs(self, ilev: int, out_dir: Path, futs: dict | None) -> dict:
        """Wait for one level's tifs, then mark it done and drop its raster blocks."""
        if futs is None:
            return {"skipped": "checkpointed"}
        res = {}
        for k, f in futs.items():
            r = f.result()
            res[f"{k}_write_s"], res[f"{k}_overview_s"] = r["write_s"], r["overview_s"]
        blocks = sorted(uv_blocks(self.geo, ilev))
        (out_dir / f".lev{ilev}.done").write_text(json.dumps({"blocks": len(blocks)}))
        for ib in blocks:
            raster_path(self.work_dir, ilev, ib).unlink(missing_ok=True)
        res["blocks"] = len(blocks)
        self.log(f"    lev{ilev} tifs: {res}", flush=True)
        return res

    # -- top level ---------------------------------------------------------------------
    def build(self, sf=None, resume: bool = True) -> "object":
        """Run both phases, assemble, write tifs; return the xr.Dataset (not written)."""
        t0 = time.time()
        if sf is None:
            sf = self.open_model()
        self.prepare(sf)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        for li in self.geo.levels:
            if li is not None:
                (self.work_dir / f"lev{li.ilev}").mkdir(exist_ok=True)
        # half-written block files of a killed run (never renamed into place)
        for f in self.work_dir.glob("lev*/*.tmp*"):
            f.unlink(missing_ok=True)
        man = self.manifest(sf)
        mpath = self.work_dir / "manifest.json"
        if mpath.exists():
            old = json.loads(mpath.read_text())
            if old != json.loads(json.dumps(man)):
                if not resume:
                    raise SystemExit(f"{mpath}: different inputs; refusing to resume")
                raise SystemExit(
                    f"{mpath} records DIFFERENT inputs (mesh / lists / builder / "
                    "catalog) — refusing to mix checkpoints; pass --fresh to discard "
                    "them"
                )
            self.log(f"    resuming from {self.work_dir}")
        else:
            mpath.write_text(json.dumps(man, indent=2))

        ct = self.cell_tasks()
        self.log(
            f"    phase 1 (cells): {len(ct)} blocks "
            + str({li.ilev: (li.nrbm * li.nrbn) for li in self.geo.levels if li})
        )
        self.run_pool(ct, "cells")
        t1 = time.time()
        z = self.empty_cells()
        self.fill_cells(z)
        ut = self.uv_tasks(z["z_zmin"])
        self.log(f"    phase 2 (uv): {len(ut)} blocks")
        self.tif_results = {}
        tif_dir = self.work_dir / "subgrid"
        with ProcessPoolExecutor(
            max_workers=4, mp_context=get_context("spawn")
        ) as writer:
            futs = {}

            def level_done(ilev):
                futs[ilev] = self.submit_level_tifs(ilev, tif_dir, writer)

            # finest level first: lev3's tifs (the biggest, ~4 min) are then written
            # while the pool works through the coarser levels, not after it
            self.run_pool(ut, "uv", on_level_done=level_done, finest_first=True)
            t2 = time.time()
            # levels whose blocks were all checkpointed before this run (a resume)
            for li in self.geo.levels:
                if li is not None and li.ilev not in futs:
                    futs[li.ilev] = self.submit_level_tifs(li.ilev, tif_dir, writer)
            for ilev in sorted(futs, reverse=True):
                self.tif_results[ilev] = self.finish_level_tifs(
                    ilev, tif_dir, futs[ilev]
                )
        t4 = time.time()
        arr = self.assemble(z)
        self.timings = {
            "cells_s": round(t1 - t0),
            "uv_s": round(t2 - t1),
            "tif_tail_s": round(t4 - t2),
            "assemble_s": round(time.time() - t4),
        }
        return arr

    def cleanup(self) -> None:
        shutil.rmtree(self.work_dir, ignore_errors=True)


def summarize_stats(stats: list[dict]) -> dict:
    """Per (kind, level): blocks, wall, and the timer split, for the README."""
    out: dict = {}
    for s in stats:
        key = f"{s['kind']}_lev{s['ilev']}"
        o = out.setdefault(
            key, {"blocks": 0, "wall_s": 0.0, "max_rss_gb": 0.0, "bytes": 0}
        )
        o["blocks"] += 1
        o["wall_s"] += s["wall"]
        o["max_rss_gb"] = max(o["max_rss_gb"], s["maxrss_gb"])
        o["bytes"] += s.get("bytes", 0)
        for k, v in s["timers"].items():
            o[k] = o.get(k, 0.0) + v
    return out


# --------------------------------------------------------------------------------------
# dep_subgrid_merged.tif in parallel (scripts/build_merged_subgrid_dep.build_merged,
# tile loop copied verbatim; the checks, spot check and overviews are its own functions)
# --------------------------------------------------------------------------------------
_M: dict = {}


def _merged_init(spec: dict) -> None:
    os.environ["GDAL_CACHEMAX"] = "512"
    import rasterio  # noqa: PLC0415

    srcs = {lev: rasterio.open(p) for lev, p in spec["paths"].items()}
    _M.update(
        spec, srcs=srcs, inv={lev: ~srcs[lev].transform for lev in spec["coarser"]}
    )


def _merged_tile(r0: int, c0: int):
    """One BLOCK x BLOCK tile of build_merged's loop, verbatim."""
    from build_merged_subgrid_dep import _block_mean  # noqa: PLC0415
    from rasterio.windows import Window  # noqa: PLC0415

    srcs, base_level = _M["srcs"], _M["base_level"]
    finer, coarser, fine_off, inv = (
        _M["finer"],
        _M["coarser"],
        _M["fine_off"],
        _M["inv"],
    )
    base = srcs[base_level]
    T, ny, nx, BLOCK = base.transform, base.height, base.width, _M["block"]
    partial = {lev: 0 for lev in finer}
    filled = {lev: 0 for lev in srcs if lev != base_level}

    h, w = min(BLOCK, ny - r0), min(BLOCK, nx - c0)
    win = Window(c0, r0, w, h)
    a = None
    for lev in finer:  # finest data first, meaned onto the base lattice
        k = 2 ** (lev - base_level)
        m, npart = _block_mean(srcs[lev], win, k, fine_off[lev])
        partial[lev] += npart
        if a is None:
            a = m
        else:
            take = ~np.isfinite(a) & np.isfinite(m)
            a[take] = m[take]
        filled[lev] += int(np.isfinite(m).sum())
    b = base.read(1, window=win)
    if a is None:
        a = b
    else:
        take = ~np.isfinite(a) & np.isfinite(b)
        a[take] = b[take]
    nan = ~np.isfinite(a)
    if nan.any():
        rr, cc = np.nonzero(nan)
        # pixel-CENTRE map coords of the holes, via the base affine
        col, row = cc + c0 + 0.5, rr + r0 + 0.5
        X = T.c + T.a * col + T.b * row
        Y = T.f + T.d * col + T.e * row
        for lev in coarser:
            need = ~np.isfinite(a[rr, cc])
            if not need.any():
                break
            fc = inv[lev].a * X + inv[lev].b * Y + inv[lev].c
            fr = inv[lev].d * X + inv[lev].e * Y + inv[lev].f
            sc, sr = np.floor(fc).astype(int), np.floor(fr).astype(int)
            ok = (
                need
                & (sr >= 0)
                & (sr < srcs[lev].height)
                & (sc >= 0)
                & (sc < srcs[lev].width)
            )
            if not ok.any():
                continue
            swin = Window(
                sc[ok].min(),
                sr[ok].min(),
                sc[ok].max() - sc[ok].min() + 1,
                sr[ok].max() - sr[ok].min() + 1,
            )
            s = srcs[lev].read(1, window=swin)
            v = s[sr[ok] - sr[ok].min(), sc[ok] - sc[ok].min()]
            good = np.isfinite(v)
            idx = np.nonzero(ok)[0][good]
            a[rr[idx], cc[idx]] = v[good]
            filled[lev] += int(good.sum())
    return r0, c0, a, partial, filled


def build_merged_parallel(
    sg: Path,
    workers: int,
    out: Path | None = None,
    base_level: int | None = None,
    threads: int = 8,
    log=print,
) -> Path:
    """``build_merged(sg)`` with the tiles computed in a process pool and written by
    this process as they arrive (any order: the windows do not overlap, so every pixel
    is the serial one; the file's byte layout differs). Same profile, same spot check,
    same overviews, same atomic rename."""
    import build_merged_subgrid_dep as bm  # noqa: PLC0415
    import rasterio  # noqa: PLC0415
    from rasterio.enums import Resampling  # noqa: PLC0415
    from rasterio.windows import Window  # noqa: PLC0415

    if base_level is None:
        from nj_sfincs import domain as _domain  # noqa: PLC0415

        base_level = _domain.active().merged_dep_base_level
    sg = Path(sg)
    out = Path(out) if out else sg / "dep_subgrid_merged.tif"
    if out.exists():
        sys.exit(f"{out} exists")
    paths = {}
    for lev in bm.LEVELS:
        p = sg / f"dep_subgrid_lev{lev}.tif"
        if not p.is_file():
            sys.exit(f"missing {p}")
        paths[lev] = str(p)
    srcs = {lev: rasterio.open(p) for lev, p in paths.items()}
    if base_level not in bm.LEVELS:
        sys.exit(f"base level {base_level} not in {bm.LEVELS}")
    base = srcs[base_level]
    finer = [lev for lev in bm.LEVELS if lev > base_level]
    coarser = [lev for lev in bm.LEVELS if lev < base_level]
    for lev in finer + coarser:
        bm._check_aligned(base, srcs[lev], lev, base_level)
    fine_off = {
        lev: bm._finer_offset(base, srcs[lev], 2 ** (lev - base_level)) for lev in finer
    }
    prof = base.profile.copy()
    prof.update(
        compress="deflate",
        predictor=3,
        tiled=True,
        blockxsize=512,
        blockysize=512,
        bigtiff="IF_SAFER",
        nodata=np.nan,
    )
    ny, nx = base.height, base.width
    tiles = [(r0, c0) for r0 in range(0, ny, bm.BLOCK) for c0 in range(0, nx, bm.BLOCK)]
    partial = {lev: 0 for lev in finer}
    filled = {lev: 0 for lev in bm.LEVELS if lev != base_level}
    spec = dict(
        paths=paths,
        base_level=base_level,
        finer=finer,
        coarser=coarser,
        fine_off=fine_off,
        block=bm.BLOCK,
    )
    here = Path(__file__).resolve().parents[1] / "scripts"
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))
    t0 = time.time()
    tmp = out.with_name(f".{out.name}.partial.tif")
    with rasterio.Env(GDAL_NUM_THREADS=str(threads)):
        with rasterio.open(tmp, "w", **prof) as dst:
            with ProcessPoolExecutor(
                max_workers=workers,
                mp_context=get_context("spawn"),
                initializer=_merged_init,
                initargs=(spec,),
            ) as ex:
                it = iter(tiles)
                pending = set()
                done = 0
                last = time.time()
                while True:
                    while len(pending) < 3 * workers:
                        nxt = next(it, None)
                        if nxt is None:
                            break
                        pending.add(ex.submit(_merged_tile, *nxt))
                    if not pending:
                        break
                    fin, pending = wait(pending, return_when=FIRST_COMPLETED)
                    for f in fin:
                        r0, c0, a, pt, fl = f.result()
                        h, w = a.shape
                        dst.write(a, 1, window=Window(c0, r0, w, h))
                        for k, v in pt.items():
                            partial[k] += v
                        for k, v in fl.items():
                            filled[k] += v
                        done += 1
                    if time.time() - last > 60:
                        last = time.time()
                        log(
                            f"  merged: {done}/{len(tiles)} tiles {time.time() - t0:.0f}s",
                            flush=True,
                        )
    got = "/".join(f"{filled[lev]:,}" for lev in sorted(filled, reverse=True))
    log(
        f"  merged tiles {len(tiles)} base lev{base_level}; filled lev"
        f"{'/'.join(str(v) for v in sorted(filled, reverse=True))} = {got}"
        + (f"; partial fine blocks {partial}" if finer else "")
        + f"  {time.time() - t0:.0f}s",
        flush=True,
    )
    for lev in finer:
        bm._spot_check(tmp, srcs[lev], 2 ** (lev - base_level), fine_off[lev])
    tmp.replace(out)
    with rasterio.Env(
        COMPRESS_OVERVIEW="DEFLATE",
        PREDICTOR_OVERVIEW="3",
        GDAL_NUM_THREADS=str(threads),
    ):
        with rasterio.open(out, "r+") as r:
            ladder = (2, 4, 8, 16, 32, 64, 128, 254)
            ladder = [f for f in ladder if max(r.width, r.height) // f >= 2]
            r.build_overviews(ladder, Resampling.average)
    log(f"overviews built ({time.time() - t0:.0f}s)")
    with rasterio.open(out) as r:
        a = r.read(1, out_shape=(r.height // 16, r.width // 16))
    log(
        f"wrote {out} ({out.stat().st_size / 1e9:.2f} GB); "
        f"finite fraction at 16x: {np.isfinite(a).mean():.3f}"
    )
    for s in srcs.values():
        s.close()
    return out
