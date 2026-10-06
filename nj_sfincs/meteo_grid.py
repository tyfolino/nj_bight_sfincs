"""Gridded meteo files (``netamuv`` / ``netamp`` / ``netampr``) as the ENGINE reads them.

🔴 **SFINCS v2.3.3 reads the first ``x`` / ``y`` value of these files as a cell CORNER;
hydromt writes cell CENTRES.** ``sfincs_ncinput.F90`` (l.493–497, 607–611, 725–729) sets
``x_llcorner = x(1)``, ``y_llcorner = y(1)``, ``dx = x(2) - x(1)``, ``dy = y(2) - y(1)``
(SIGNED), flips the file rows (engine row 1 = LAST file row), and ``sfincs_meteo.f90``
(l.843–844, 1019–1020, 1156–1157) places engine row 1 / column 1 at::

    yul = y_llcorner + (nrows - 1)*dy + 0.5*dy
    xll = x_llcorner + 0.5*dx

Written centres therefore put every value half a step away from where it belongs, and
every model point samples the field from ``x - dx/2`` and ``y - dy/2`` (signed ``dy``):
with hydromt's DESCENDING ``y`` (``dy < 0``) that is ½ cell WEST and ½ cell NORTH — on
the 25 km ERA5 grid 12.5 km W and 12.5 km N (the toy probe measured x −12 516 m,
y +12 518 m; logs/raritan_2026-10-06/wind_setup_toy/README.md). With ascending ``y`` the
y-shift would be southward.

**The fix is on the data side** (the engine of record stays untouched): write each
coordinate as ``centre - step/2`` with the SIGNED step of that axis::

    x_written = x_centre - dx/2            (dx > 0)
    y_written = y_centre - dy/2            (dy signed: descending y -> + |dy|/2)

Then ``xll`` and ``yul`` land exactly on the first column / last file row's centre and
the engine's bilinear interpolation returns the field at the true point. Only the
coordinate VALUES change; the data, dims and encodings are untouched. A file carries
``ORIGIN_ATTR`` (global, and on ``x`` / ``y``) once fixed, so the fix is never applied
twice — hydromt's read → write round trip in ``finalize`` keeps those attributes, and
``finalize`` calls :func:`fix_meteo_grid_origin` after every ``sf.write()``.

⚠️ A reader that wants the TRUE centres of a fixed file uses :func:`true_centres`;
``xr.open_dataset(...).interp(x=, y=)`` on a fixed file is half a cell off the other way.

Also here: :func:`engine_sample` (a numpy port of the engine's ``update_amuv_data``
interpolation, out-of-grid zeroing included) and :func:`write_era5_bilinear` (rewrite the
wind + pressure files from native ERA5 by bilinear interpolation in lon/lat onto a fine
UTM grid, instead of hydromt's nearest-neighbour copy; logs/raritan_2026-10-06/meteo_fix).

Import-safe: numpy / xarray / netCDF4 only at module level.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import numpy as np

#: The gridded meteo files the engine reads with the corner convention.
METEO_GRID_FILES = ("sfincs_netamuv.nc", "sfincs_netamp.nc", "sfincs_netampr.nc")
#: Set (global + on x and y) once a file's coordinates carry the engine's convention.
ORIGIN_ATTR = "nj_sfincs_grid_origin"
ORIGIN_VALUE = (
    "engine-corner: written x/y = cell centre - signed step/2 "
    "(SFINCS v2.3.3 reads x(1), y(1) as the lower-left corner; nj_sfincs.meteo_grid)"
)
#: On x / y: the first TRUE cell centre, for the record.
CENTRE0_ATTR = "nj_sfincs_first_cell_centre"
#: Set by write_era5_bilinear.
REGRID_ATTR = "nj_sfincs_regrid"


# ── the convention ────────────────────────────────────────────────────────────


def signed_step(c) -> float:
    """``c[1] - c[0]`` of a 1-D regular axis; raises on < 2 points or uneven spacing."""
    c = np.asarray(c, dtype="f8")
    if c.ndim != 1 or c.size < 2:
        raise ValueError(f"meteo axis needs >= 2 points, got shape {c.shape}")
    d = np.diff(c)
    step = float(d[0])
    if step == 0 or not np.allclose(d, step, rtol=1e-6, atol=1e-6 * abs(step)):
        raise ValueError(
            f"meteo axis is not regular (steps {d.min():.6f}..{d.max():.6f}); the "
            "engine assumes a rectilinear grid with a constant step"
        )
    return step


def engine_coords(xc, yc) -> tuple[np.ndarray, np.ndarray]:
    """True cell centres -> the coordinate values to WRITE (``centre - signed step/2``)."""
    xc = np.asarray(xc, dtype="f8")
    yc = np.asarray(yc, dtype="f8")
    dx, dy = signed_step(xc), signed_step(yc)
    if dx < 0:
        raise ValueError(
            "descending x: the engine's column search assumes dx > 0; write x ascending"
        )
    return xc - 0.5 * dx, yc - 0.5 * dy


def centres_from_engine_coords(xw, yw) -> tuple[np.ndarray, np.ndarray]:
    """Inverse of :func:`engine_coords`."""
    xw = np.asarray(xw, dtype="f8")
    yw = np.asarray(yw, dtype="f8")
    return xw + 0.5 * signed_step(xw), yw + 0.5 * signed_step(yw)


def engine_sample(xq, yq, xw, yw, F, f32: bool = False) -> np.ndarray:
    """What SFINCS v2.3.3 applies at points (xq, yq) from a file with coordinate VALUES
    ``xw``, ``yw`` and field ``F[y, x]`` in FILE order.

    A line-for-line port of the reader (``sfincs_ncinput.F90`` l.466–497: llcorner =
    first value, signed steps, rows flipped) and of ``update_amuv_data`` (``sfincs_meteo
    .f90`` l.843–900; ``update_amp_data`` and the ampr block use the same lines). Points
    the engine rejects (``iy<=1 .or. iy>=nrows .or. ix<=0 .or. ix>=ncols``) get 0, as in
    the engine. ``f32=True`` does the corner / step arithmetic in single precision like
    the engine's ``real*4`` (≈ 0.5 m at UTM northings).
    """
    xq = np.asarray(xq, dtype="f8")
    yq = np.asarray(yq, dtype="f8")
    F = np.asarray(F, dtype="f8")
    nrows, ncols = len(yw), len(xw)
    cast = np.float32 if f32 else np.float64
    x_ll, y_ll = cast(xw[0]), cast(yw[0])
    dx, dy = cast(xw[1]) - cast(xw[0]), cast(yw[1]) - cast(yw[0])
    A = F[::-1, :]  # engine row 1 = LAST file row
    yul = float(y_ll + (nrows - 1) * dy + cast(0.5) * dy)
    xll = float(x_ll + cast(0.5) * dx)
    dx, dy = float(dx), float(dy)
    iy = np.trunc((yul - yq) / dy).astype(int) + 1  # Fortran int() truncates
    dj = (yul - (iy - 1) * dy - yq) / dy
    ix = np.trunc((xq - xll) / dx).astype(int) + 1
    di = (xq - (xll + (ix - 1) * dx)) / dx
    bad = (iy <= 1) | (iy >= nrows) | (ix <= 0) | (ix >= ncols)
    iyc, ixc = np.clip(iy, 1, nrows - 1), np.clip(ix, 1, ncols - 1)

    def a(r, c):  # 1-based like the Fortran
        return A[r - 1, c - 1]

    out = (
        (1 - di) * (1 - dj) * a(iyc, ixc)
        + di * (1 - dj) * a(iyc, ixc + 1)
        + di * dj * a(iyc + 1, ixc + 1)
        + (1 - di) * dj * a(iyc + 1, ixc)
    )
    return np.where(bad, 0.0, out)


def engine_accepted_band(xw, yw) -> dict:
    """The rectangle (true coordinates) where the engine does NOT zero the field.

    ``x`` in [first column centre, last column centre). In ``y`` the engine's ``iy <= 1``
    test rejects the whole cell next to its row 1 = the LAST file row: with descending y
    that is the bottom cell, with ascending y the top one. So ``y`` lies strictly between
    the centres of file rows ``-2`` and ``0``.
    """
    xc, yc = centres_from_engine_coords(xw, yw)
    lo, hi = sorted((float(yc[-2]), float(yc[0])))
    return {"x_min": float(xc[0]), "x_max": float(xc[-1]), "y_min": lo, "y_max": hi}


# ── files ─────────────────────────────────────────────────────────────────────


def _is_fixed(nc) -> bool:
    if ORIGIN_ATTR in nc.ncattrs():
        return True
    return any(
        v in nc.variables and ORIGIN_ATTR in nc.variables[v].ncattrs()
        for v in ("x", "y")
    )


def file_state(path: Path) -> dict:
    """Read-only: is this file fixed, its grid, and the TRUE first centres."""
    import netCDF4

    path = Path(path)
    with netCDF4.Dataset(path, "r") as nc:
        x = np.asarray(nc.variables["x"][:], dtype="f8")
        y = np.asarray(nc.variables["y"][:], dtype="f8")
        fixed = _is_fixed(nc)
        regrid = None
        for obj in (nc, nc.variables["x"]):
            if REGRID_ATTR in obj.ncattrs():
                regrid = obj.getncattr(REGRID_ATTR)
    dx, dy = signed_step(x), signed_step(y)
    xc, yc = centres_from_engine_coords(x, y) if fixed else (x, y)
    return {
        "file": path.name,
        "fixed": fixed,
        "nx": x.size,
        "ny": y.size,
        "dx": dx,
        "dy": dy,
        "x_centre0": float(xc[0]),
        "y_centre0": float(yc[0]),
        "x_written0": float(x[0]),
        "y_written0": float(y[0]),
        "regrid": regrid,
    }


def true_centres(path_or_ds) -> tuple[np.ndarray, np.ndarray]:
    """TRUE cell centres of a meteo file (or an open xarray Dataset), fixed or not."""
    import xarray as xr

    if isinstance(path_or_ds, (str, Path)):
        with xr.open_dataset(path_or_ds) as ds:
            return true_centres(ds.load())
    ds = path_or_ds
    x = np.asarray(ds["x"].values, dtype="f8")
    y = np.asarray(ds["y"].values, dtype="f8")
    fixed = ORIGIN_ATTR in ds.attrs or any(
        ORIGIN_ATTR in ds[v].attrs for v in ("x", "y")
    )
    return centres_from_engine_coords(x, y) if fixed else (x, y)


def _fix_one(path: Path) -> dict:
    """Rewrite x / y of one file to the engine convention. Copy → edit → atomic replace:
    the original inode (and any hard link to it) is never written."""
    import netCDF4

    path = Path(path)
    tmp = path.with_name(f".{path.name}.origin_tmp")
    shutil.copy2(path, tmp)
    try:
        with netCDF4.Dataset(tmp, "r+") as nc:
            if _is_fixed(nc):  # raced or already fixed: leave the original alone
                raise FileExistsError
            xv, yv = nc.variables["x"], nc.variables["y"]
            xc = np.asarray(xv[:], dtype="f8")
            yc = np.asarray(yv[:], dtype="f8")
            xw, yw = engine_coords(xc, yc)
            xv[:] = xw
            yv[:] = yw
            for v, c0 in ((xv, xc[0]), (yv, yc[0])):
                v.setncattr(ORIGIN_ATTR, ORIGIN_VALUE)
                v.setncattr(CENTRE0_ATTR, float(c0))
            nc.setncattr(ORIGIN_ATTR, ORIGIN_VALUE)
            nc.sync()
        with open(tmp, "rb") as fh:
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except FileExistsError:
        tmp.unlink(missing_ok=True)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return file_state(path)


#: sfincs.inp keys naming the gridded meteo files.
INP_KEYS = ("netamuamvfile", "netampfile", "netamprfile")


def meteo_files(model_dir: Path) -> tuple[str, ...]:
    """The gridded meteo files of a model dir: the defaults plus whatever ``sfincs.inp``
    names under ``INP_KEYS`` (a renamed file must not be skipped silently)."""
    names = list(METEO_GRID_FILES)
    inp = Path(model_dir) / "sfincs.inp"
    if inp.is_file():
        for ln in inp.read_text().splitlines():
            k, _, v = ln.partition("=")
            if k.strip() in INP_KEYS and v.strip():
                name = Path(v.strip()).name
                if name not in names:
                    names.append(name)
    return tuple(names)


def marked_in_memory(sf) -> set[str]:
    """File names whose IN-MEMORY hydromt meteo component already carries the marker
    (it was read from a fixed file). ``finalize`` passes this as ``expect_fixed``, so a
    future hydromt that dropped coordinate attributes on write would raise instead of
    shifting the grid a second time."""
    out = set()
    for comp, key in (
        ("wind", "netamuamvfile"),
        ("pressure", "netampfile"),
        ("precipitation", "netamprfile"),
    ):
        try:
            data = getattr(getattr(sf, comp), "_data", None)
            if data is None or "x" not in data.coords:
                continue
            if ORIGIN_ATTR in data["x"].attrs or ORIGIN_ATTR in data.attrs:
                name = sf.config.get(key)
                if name:
                    out.add(Path(str(name)).name)
        except Exception:  # noqa: BLE001 — a component with no data is not an error
            continue
    return out


def fix_meteo_grid_origin(
    model_dir: Path,
    check: bool = False,
    files=None,
    expect_fixed=(),
) -> list[dict]:
    """Make every gridded meteo file in ``model_dir`` carry the coordinates the engine
    interprets correctly (module docstring). IDEMPOTENT: a file already carrying
    ``ORIGIN_ATTR`` is left alone. ``check=True`` writes nothing. Missing files (rain-off
    arms) are skipped. ``files`` defaults to :func:`meteo_files`. A file named in
    ``expect_fixed`` that is NOT marked raises (its marker was lost, so its coordinates
    are already shifted and a second shift would be silent). Returns one
    :func:`file_state` dict per file present, with ``"action"`` = ``fixed`` /
    ``already`` / ``NEEDS FIX`` (check mode).
    """
    model_dir = Path(model_dir)
    files = tuple(files) if files is not None else meteo_files(model_dir)
    present = [f for f in files if (model_dir / f).is_file()]
    out = []
    todo = []
    for f in present:
        st = file_state(model_dir / f)
        if not st["fixed"] and f in set(expect_fixed):
            raise RuntimeError(
                f"{model_dir / f}: was read from a FIXED meteo file but was written "
                "without the grid-origin marker — refusing to shift it a second time "
                "(did hydromt stop carrying coordinate attributes?)"
            )
        if st["fixed"]:
            st["action"] = "already"
            out.append(st)
        elif check:
            st["action"] = "NEEDS FIX"
            out.append(st)
        else:
            todo.append(f)
    if todo:
        # CLAUDE.md §5: never write THROUGH a hard link. _fix_one replaces the inode
        # anyway; this is the belt to that brace, limited to the files we touch (a
        # whole-dir break would copy the GB-sized subgrid / roughness tables).
        from .model import break_hardlinks

        break_hardlinks(model_dir, names=todo)
        for f in todo:
            st = _fix_one(model_dir / f)
            st["action"] = "fixed"
            out.append(st)
    order = {f: i for i, f in enumerate(files)}
    return sorted(out, key=lambda st: order[st["file"]])


def describe(states: list[dict]) -> str:
    lines = []
    for s in states:
        lines.append(
            f"  {s['file']:<20} {s['action']:<9} {s['nx']}x{s['ny']} "
            f"dx {s['dx']:+.1f} dy {s['dy']:+.1f}  first centre "
            f"({s['x_centre0']:.1f}, {s['y_centre0']:.1f})  written "
            f"({s['x_written0']:.1f}, {s['y_written0']:.1f})"
            + (f"  [{s['regrid']}]" if s.get("regrid") else "")
        )
    return "\n".join(lines)


# ── ERA5 written by bilinear interpolation (logs/raritan_2026-10-06/meteo_fix) ──


def write_era5_bilinear(
    model_dir: Path,
    era5,
    res_m: float = 5000.0,
    epsg: int | None = None,
) -> dict:
    """Rewrite ``sfincs_netamuv.nc`` and ``sfincs_netamp.nc`` from NATIVE ERA5.

    hydromt's ``wind.create`` / ``pressure.create`` warp the 0.25° grid onto a ~25 km UTM
    grid by GDAL NEAREST (its ``method="nearest_index"`` default is built but never
    passed): every UTM cell is a copy of one native cell whose centre is up to ~17 km
    away, and the grid's origin depends on the model bbox, so two domains read the same
    ERA5 differently (v3 vs v4 Raritan Bay, ~1.4 m/s at the crest). ERA5's native
    centres cannot be written as-is — the engine wants a rectilinear grid in the model
    CRS — so this samples ERA5 by bilinear interpolation IN LON/LAT at the centres of a
    ``res_m`` UTM grid; the engine's own bilinear step on that fine grid then reproduces
    the native bilinear field to within a few cm/s.

    ``era5``: a path or Dataset with ``wind10_u``, ``wind10_v``, ``press_msl`` on
    ``x`` (lon) / ``y`` (lat) / ``time`` (the ``era5_nj`` catalog file). The target grid
    covers the existing file's extent, shrunk to where native ERA5 has four
    neighbours; times are the existing file's. Refuses unless the existing wind IS this
    ERA5 unscaled (every nonzero cell an exact copy of a native cell — hydromt's nearest
    warp — or, for a file this function wrote, the bilinear field again): a
    ``wind_scale`` arm or another product would otherwise be silently undone. The written files
    carry the engine convention (:func:`fix_meteo_grid_origin`) and ``REGRID_ATTR``.
    """
    import xarray as xr
    from pyproj import Transformer

    model_dir = Path(model_dir)
    if epsg is None:
        epsg = _inp_epsg(model_dir)
    f_uv = model_dir / "sfincs_netamuv.nc"
    f_p = model_dir / "sfincs_netamp.nc"
    for f in (f_uv, f_p):
        if not f.is_file():
            raise FileNotFoundError(f)

    old = xr.load_dataset(f_uv)
    xc_old, yc_old = true_centres(old)
    times = old["time"].values

    nat = xr.open_dataset(era5) if isinstance(era5, (str, Path)) else era5
    nat = nat[["wind10_u", "wind10_v", "press_msl"]].sel(time=times).load()
    lon, lat = nat["x"].values, nat["y"].values

    to_ll = Transformer.from_crs(int(epsg), 4326, always_xy=True)
    # snapped to whole multiples of res_m: every coordinate (and the written
    # centre - step/2) is then exact in the engine's real*4, so its step dy = y(2) - y(1)
    # carries no rounding drift (hydromt's 829.095 m rain step drifts ~30 m over 310
    # rows in real*4; logs/raritan_2026-10-06/meteo_fix/probe_fix_results.txt)
    x = np.arange(np.ceil(xc_old.min() / res_m), np.floor(xc_old.max() / res_m) + 1)
    y = np.arange(np.floor(yc_old.max() / res_m), np.ceil(yc_old.min() / res_m) - 1, -1)
    x, y = x * res_m, y * res_m  # y descending, like hydromt
    X, Y = np.meshgrid(x, y)
    LON, LAT = to_ll.transform(X, Y)
    inside = (
        (LON >= lon.min())
        & (LON <= lon.max())
        & (LAT >= lat.min())
        & (LAT <= lat.max())
    )
    # trim the outermost row / column with the most points outside the native grid
    # until none is left (UTM rows are not parallels: a whole-row test would drop the
    # northern rows because their west end crosses ERA5's west edge)
    r0, r1, c0, c1 = 0, inside.shape[0], 0, inside.shape[1]
    while not inside[r0:r1, c0:c1].all():
        if r1 - r0 < 2 or c1 - c0 < 2:
            raise ValueError("the native ERA5 grid does not cover the meteo extent")
        sub = ~inside[r0:r1, c0:c1]
        edge = {
            "r0": sub[0].sum(),
            "r1": sub[-1].sum(),
            "c0": sub[:, 0].sum(),
            "c1": sub[:, -1].sum(),
        }
        k = max(edge, key=edge.get)
        r0, r1 = r0 + (k == "r0"), r1 - (k == "r1")
        c0, c1 = c0 + (k == "c0"), c1 - (k == "c1")
    x, y = x[c0:c1], y[r0:r1]
    LON, LAT = LON[r0:r1, c0:c1], LAT[r0:r1, c0:c1]
    out_band = _faces_outside(model_dir, *engine_coords(x, y))
    if out_band:
        raise ValueError(
            f"{out_band:,} active faces fall outside the engine's band of the new "
            f"{res_m:.0f} m grid (ERA5 does not reach far enough) — nothing written"
        )
    tgt = dict(
        x=xr.DataArray(LON, dims=("y", "x")),
        y=xr.DataArray(LAT, dims=("y", "x")),
    )
    new = nat.interp(**tgt, method="linear")
    if any(bool(new[v].isnull().any()) for v in new.data_vars):
        raise ValueError("bilinear ERA5 has NaN inside the target grid")

    ok, detail = _is_unscaled_copy(old, nat, xc_old, yc_old, to_ll)
    if not ok:
        raise ValueError(
            f"the existing sfincs_netamuv.nc is not an unscaled copy of this ERA5 "
            f"({detail}): a wind_scale arm or another product — refusing to overwrite it"
        )

    units = old["time"].encoding.get("units")  # hydromt: minutes since tref
    enc_t = {"units": units, "dtype": "float64"} if units else {}
    stamp = (
        f"ERA5 0.25deg bilinear in lon/lat at the centres of a {res_m:.0f} m "
        f"EPSG:{epsg} grid (nj_sfincs.meteo_grid.write_era5_bilinear)"
    )
    coords = {"time": times, "y": y, "x": x}
    xattrs = {"standard_name": "projection_x_coordinate", "units": "metre", "axis": "X"}
    yattrs = {"standard_name": "projection_y_coordinate", "units": "metre", "axis": "Y"}
    dsets = {
        f_uv: xr.Dataset(
            {
                "eastward_wind": (
                    ("time", "y", "x"),
                    new["wind10_u"].values.astype("f4"),
                ),
                "northward_wind": (
                    ("time", "y", "x"),
                    new["wind10_v"].values.astype("f4"),
                ),
            },
            coords=coords,
        ),
        f_p: xr.Dataset(
            {
                "barometric_pressure": (
                    ("time", "y", "x"),
                    new["press_msl"].values.astype("f4"),
                )
            },
            coords=coords,
        ),
    }
    from .model import break_hardlinks

    break_hardlinks(model_dir, names=[f.name for f in dsets])
    for f, ds in dsets.items():
        # on x / y too: hydromt's read -> write round trip (arm staging) keeps
        # coordinate attributes but drops the global ones
        ds["x"].attrs.update(xattrs, **{REGRID_ATTR: stamp})
        ds["y"].attrs.update(yattrs, **{REGRID_ATTR: stamp})
        ds.attrs[REGRID_ATTR] = stamp
        tmp = f.with_name(f".{f.name}.regrid_tmp")
        ds.to_netcdf(tmp, encoding={"time": enc_t} if enc_t else None)
        os.replace(tmp, f)  # centres, unmarked: a consistent state if we stop here
    states = fix_meteo_grid_origin(model_dir, files=tuple(f.name for f in dsets))
    return {
        "nx": x.size,
        "ny": y.size,
        "res_m": res_m,
        "x": (float(x[0]), float(x[-1])),
        "y": (float(y[0]), float(y[-1])),
        "source_check": detail,
        "states": states,
    }


def _is_unscaled_copy(old, nat, xc, yc, to_ll) -> tuple[bool, str]:
    """Is the existing wind file this ERA5, unscaled? hydromt's warp is a nearest COPY,
    so every nonzero cell's whole series equals one native cell's; a file written by
    :func:`write_era5_bilinear` equals the bilinear field at its own centres."""
    import xarray as xr

    u_old = old["eastward_wind"].values.astype("f8")  # t, y, x
    if REGRID_ATTR in old.attrs or REGRID_ATTR in old["x"].attrs:
        X, Y = np.meshgrid(xc, yc)
        lo, la = to_ll.transform(X, Y)
        b = nat["wind10_u"].interp(
            x=xr.DataArray(lo, dims=("y", "x")),
            y=xr.DataArray(la, dims=("y", "x")),
        )
        err = float(np.nanmax(np.abs(b.values - u_old)))
        return err < 0.05, f"bilinear re-check, max |du| {err:.3f} m/s"
    nat_u = nat["wind10_u"].values.astype("f8").reshape(len(nat["time"]), -1)  # t, n
    cells = u_old.reshape(u_old.shape[0], -1)
    live = np.where(np.any(cells != 0, axis=0))[0]
    if live.size == 0:
        return False, "no nonzero wind cells"
    d = np.abs(cells[:, live][:, :, None] - nat_u[:, None, :]).max(axis=0)
    matched = int((d.min(axis=1) < 1e-4).sum())
    return matched == live.size, (
        f"{matched} of {live.size} nonzero cells are exact copies of native cells"
    )


def _inp_epsg(model_dir: Path) -> int:
    for ln in (Path(model_dir) / "sfincs.inp").read_text().splitlines():
        k, _, v = ln.partition("=")
        if k.strip() == "epsg":
            return int(float(v))
    raise ValueError(f"no epsg in {model_dir}/sfincs.inp")


def _active_xy(model_dir: Path):
    """Active face centres of a quadtree model (``sfincs.nc``), or None."""
    import netCDF4

    qtr = Path(model_dir) / "sfincs.nc"
    if not qtr.is_file():
        return None
    with netCDF4.Dataset(qtr) as nc:
        if "mesh2d_face_x" not in nc.variables or "mask" not in nc.variables:
            return None
        m = np.asarray(nc.variables["mask"][:]) > 0
        fx = np.asarray(nc.variables["mesh2d_face_x"][:], dtype="f8")[m]
        fy = np.asarray(nc.variables["mesh2d_face_y"][:], dtype="f8")[m]
    return fx, fy


def _faces_outside(model_dir: Path, xw, yw, xy=None) -> int:
    """Active faces the engine would ZERO for a file with written coords xw, yw."""
    xy = _active_xy(model_dir) if xy is None else xy
    if xy is None:
        return 0
    fx, fy = xy
    b = engine_accepted_band(xw, yw)
    bad = (fx < b["x_min"]) | (fx >= b["x_max"]) | (fy <= b["y_min"])
    bad |= fy >= b["y_max"]
    return int(bad.sum())


def active_faces_outside_band(
    model_dir: Path, files=None
) -> dict[str, tuple[int, int]]:
    """Per meteo file: (active faces the engine would ZERO, active faces) once the file is
    read with the engine convention. Quadtree models only (``sfincs.nc`` with
    ``mesh2d_face_x``); {} otherwise. Read-only."""
    model_dir = Path(model_dir)
    xy = _active_xy(model_dir)
    if xy is None:
        return {}
    out = {}
    for f in files if files is not None else meteo_files(model_dir):
        p = model_dir / f
        if not p.is_file():
            continue
        st = file_state(p)
        xc = st["x_centre0"] + st["dx"] * np.arange(st["nx"])
        yc = st["y_centre0"] + st["dy"] * np.arange(st["ny"])
        out[f] = (_faces_outside(model_dir, *engine_coords(xc, yc), xy=xy), xy[0].size)
    return out
