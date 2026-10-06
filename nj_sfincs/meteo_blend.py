"""NACCS save-point wind + pressure blended into ERA5, written as engine-ready meteo files.

Why (FINDINGS part 4 (e), ``logs/wind_products_2026-10-06/``): over the bays every gridded
product, ERA5 included, reads 0.6-0.8x the wind at the over-water lights, while the NACCS
ADCIRC save-point wind (Oceanweather's marine-exposure analysis, sampled at the save
points) matches them. Offshore ERA5 matches the buoys. So: NACCS inside its point cloud,
ERA5 (bilinear at TRUE positions) outside, joined by a smooth taper.

The recipe, in pure functions (``scripts/build_wind_naccs_blend.py`` is the CLI):

1. **Read** the save points (:func:`load_save_points`): the repack zip's CSVs, a directory
   of CHS CSVs, or CHS ``.h5`` files (h5py, best-effort); the storm is picked by name /
   ID or, for an ``.h5``, by the group whose times span the window. Components ``X`` /
   ``Y Wind Velocity`` are the vector the air moves TOWARD (east, north), m/s;
   ``Atmospheric Pressure`` is hPa (the CSV units row is checked).
2. **Triangulate** in the model CRS (:func:`triangulate`): linear barycentric
   interpolation on a Delaunay triangulation of u, v and p SEPARATELY (never speed /
   direction), triangles with any edge longer than ``max_edge_m`` dropped so a land gap
   between two water bodies is not bridged. The covered zone = cells inside a kept
   triangle (:func:`interp_weights` returns the sparse weight matrix, reused for every
   time step).
3. **Taper** (:func:`taper_weight`, :func:`blend`): ``w`` = 1 in the covered zone and
   falls as a half-cosine to 0 at ``taper_m`` from it (distance to the nearest covered
   cell). The ANOMALY ``NACCS - ERA5`` is carried outward by harmonic (Laplace)
   interpolation from the zone edge (:class:`HarmonicExtension`; smooth, no rays) and
   faded by ``w``::

       blended = ERA5 + w * (NACCS - ERA5)_extended

   which is exactly NACCS inside the zone and exactly ERA5 beyond the taper, and is
   ``w * NACCS_ext + (1 - w) * ERA5`` with ``NACCS_ext = ERA5 + anomaly``.
4. **Write** :func:`write_meteo_files`: ``sfincs_netamuv.nc`` / ``sfincs_netamp.nc`` with
   hydromt's variable names, dims and coordinate attributes, then
   :func:`nj_sfincs.meteo_grid.fix_meteo_grid_origin` on them, so the coordinates carry the
   engine's corner convention AND its marker (``finalize`` then sees ``already``).

Import-safe: numpy only at module level; scipy / xarray / pyproj / netCDF4 inside.
"""

from __future__ import annotations

import csv
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

#: The CHS ADCIRC CSV columns this module reads (header row 1), and their units (row 3).
COL_SP = "Save Point ID"
COL_LAT = "Save Point Latitude"
COL_LON = "Save Point Longitude"
COL_DEPTH = "Save Point Depth"
COL_NAME = "Storm Name"
COL_ID = "Storm ID"
COL_TIME = "yyyymmddHHMM"
COL_P = "Atmospheric Pressure"
COL_U = "X Wind Velocity"
COL_V = "Y Wind Velocity"
UNITS = {COL_P: "hPa", COL_U: "m/s", COL_V: "m/s"}

#: Stamped on the written files (global + x/y attrs).
BLEND_ATTR = "nj_sfincs_meteo_blend"

#: Times are read this far beyond the window so the time interpolation has neighbours.
_PAD = np.timedelta64(60, "m")


# ── reading ───────────────────────────────────────────────────────────────────


@dataclass
class SavePoints:
    """Save-point series on a common time axis. ``u``, ``v``, ``p_hpa``: (npts, nt)."""

    sp: np.ndarray
    lon: np.ndarray
    lat: np.ndarray
    depth: np.ndarray
    times: np.ndarray  # datetime64[m]
    u: np.ndarray
    v: np.ndarray
    p_hpa: np.ndarray
    source: np.ndarray = field(default_factory=lambda: np.array([], dtype=object))

    def __len__(self) -> int:
        return int(self.sp.size)

    def subset(self, keep) -> SavePoints:
        keep = np.asarray(keep)
        return SavePoints(
            self.sp[keep],
            self.lon[keep],
            self.lat[keep],
            self.depth[keep],
            self.times,
            self.u[keep],
            self.v[keep],
            self.p_hpa[keep],
            self.source[keep] if self.source.size else self.source,
        )


def _t64(stamp: str) -> np.datetime64:
    s = stamp.strip().strip('"')
    return np.datetime64(f"{s[:4]}-{s[4:6]}-{s[6:8]}T{s[8:10]}:{s[10:12]}", "m")


def parse_naccs_csv(text: str, storm: str = "Sandy") -> dict | None:
    """One CHS ADCIRC ``*_Timeseries.csv`` -> the chosen storm's raw series, or None.

    Columns are found BY NAME (the repack and the CHS download order them differently);
    the units row must say hPa / m/s. A row belongs to the storm when its ``Storm Name``
    is ``storm`` (case-insensitive; IDs are reused across storm types, names are not).
    Wind fill (|u| > 900) and pressure outside 800-1100 hPa become NaN.
    """
    text = text.rstrip("\x00")
    lines = text.splitlines()
    if len(lines) < 4:
        return None
    hdr = next(csv.reader([lines[0]]))
    unit_row = next(csv.reader([lines[2]]))
    idx = {}
    for col in (COL_SP, COL_LAT, COL_LON, COL_DEPTH, COL_NAME, COL_ID, COL_TIME):
        idx[col] = hdr.index(col)
    for col in (COL_P, COL_U, COL_V):
        idx[col] = hdr.index(col)
        got = unit_row[idx[col]].strip() if idx[col] < len(unit_row) else ""
        if got != UNITS[col]:
            raise ValueError(f"{col}: units row says {got!r}, expected {UNITS[col]!r}")
    name_tok = storm.lower()
    rows = []
    for ln in lines[3:]:
        if name_tok not in ln.lower():  # cheap pre-filter
            continue
        r = next(csv.reader([ln]))
        if (
            len(r) == len(hdr)
            and r[idx[COL_NAME]].strip().strip('"').lower() == name_tok
        ):
            rows.append(r)
    if not rows:
        return None
    r0 = rows[0]

    def col(c):
        return np.array([float(r[idx[c]]) for r in rows])

    u, v, p = col(COL_U), col(COL_V), col(COL_P)
    bad = (np.abs(u) > 900) | (np.abs(v) > 900)
    u[bad] = np.nan
    v[bad] = np.nan
    p[(p < 800) | (p > 1100)] = np.nan
    t = np.array([_t64(r[idx[COL_TIME]]) for r in rows])
    order = np.argsort(t, kind="stable")
    return {
        "sp": int(float(r0[idx[COL_SP]])),
        "lat": float(r0[idx[COL_LAT]]),
        "lon": float(r0[idx[COL_LON]]),
        "depth": float(r0[idx[COL_DEPTH]]),
        "t": t[order],
        "u": u[order],
        "v": v[order],
        "p_hpa": p[order],
    }


_SP_RE = re.compile(r"_SP0*(\d+)_")


def _sp_from_name(name: str) -> int | None:
    m = _SP_RE.search(Path(name).name)
    return int(m.group(1)) if m else None


def read_naccs_h5(path: Path, t0, t1, positions: dict | None = None) -> dict | None:
    """Best-effort reader for a CHS ADCIRC ``*_Timeseries.h5`` (needs h5py).

    Walks every group; a group holding datasets named like the CSV columns
    (``yyyymmddHHMM``, ``X Wind Velocity``, ``Y Wind Velocity``, ``Atmospheric Pressure``,
    matched case-insensitively) is a storm, and the one whose times span [t0, t1] is
    taken. Position from attributes named like ``Save Point Latitude/Longitude/Depth``
    anywhere in the file, else ``positions[sp] = (lat, lon, depth)``. ⚠️ Not yet run on
    a real CHS h5 (none on disk 2026-10-06): if it refuses, download the CSV form.
    """
    try:
        import h5py
    except ImportError as e:  # pragma: no cover — env-dependent
        raise ImportError(
            f"{path}: reading CHS .h5 needs h5py (not in the sfincs env 2026-10-06); "
            "download the CSV form from CHS or `micromamba install -n sfincs h5py`"
        ) from e

    want = {
        "t": "yyyymmddhhmm",
        "u": "x wind velocity",
        "v": "y wind velocity",
        "p": "atmospheric pressure",
    }
    groups: dict[str, dict] = {}
    attrs: dict[str, object] = {}

    def visit(name, obj):
        for k, val in obj.attrs.items():
            attrs.setdefault(k.lower(), val)
        if isinstance(obj, h5py.Dataset):
            leaf = name.rsplit("/", 1)[-1].lower()
            for key, label in want.items():
                if leaf == label:
                    groups.setdefault(
                        name.rsplit("/", 1)[0] if "/" in name else "", {}
                    )[key] = obj[()]

    with h5py.File(path, "r") as h:
        for k, val in h.attrs.items():
            attrs.setdefault(k.lower(), val)
        h.visititems(visit)
    t0, t1 = np.datetime64(t0, "m"), np.datetime64(t1, "m")
    for g in groups.values():
        if not all(k in g for k in want):
            continue
        raw_t = np.asarray(g["t"]).ravel()
        t = np.array(
            [
                _t64(x.decode() if isinstance(x, bytes) else f"{int(float(x)):012d}")
                for x in raw_t
            ]
        )
        if t.min() > t0 or t.max() < t1:
            continue
        u = np.asarray(g["u"], dtype="f8").ravel()
        v = np.asarray(g["v"], dtype="f8").ravel()
        p = np.asarray(g["p"], dtype="f8").ravel()
        bad = (np.abs(u) > 900) | (np.abs(v) > 900)
        u[bad] = np.nan
        v[bad] = np.nan
        p[(p < 800) | (p > 1100)] = np.nan
        sp = _sp_from_name(str(path))

        def attr(*names):
            for n in names:
                if n in attrs:
                    return float(np.asarray(attrs[n]).ravel()[0])
            return None

        lat = attr("save point latitude", "latitude", "lat")
        lon = attr("save point longitude", "longitude", "lon")
        dep = attr("save point depth", "depth")
        if (lat is None or lon is None) and positions and sp in positions:
            lat, lon, dep0 = positions[sp]
            dep = dep if dep is not None else dep0
        if lat is None or lon is None:
            raise ValueError(
                f"{path}: no save-point position (attrs or positions table)"
            )
        o = np.argsort(t, kind="stable")
        return {
            "sp": sp if sp is not None else -1,
            "lat": lat,
            "lon": lon,
            "depth": np.nan if dep is None else dep,
            "t": t[o],
            "u": u[o],
            "v": v[o],
            "p_hpa": p[o],
        }
    return None


def iter_raw_points(path: Path, t0, t1, positions: dict | None = None):
    """Yield ``(source, raw dict)`` for every ADCIRC time-series file under ``path``: a
    ``.zip`` (the repack), a directory (``*_Timeseries.csv`` / ``*_Timeseries.h5`` /
    nested ``.zip``), or one file."""
    path = Path(path)
    if path.is_dir():
        for f in sorted(path.rglob("*")):
            if f.is_file() and (
                f.suffix.lower() == ".zip"
                or (f.name.endswith("_Timeseries.csv") and "ADCIRC" in f.name)
                or (f.name.endswith("_Timeseries.h5") and "ADCIRC" in f.name)
            ):
                yield from iter_raw_points(f, t0, t1, positions)
        return
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as zf:
            for n in sorted(zf.namelist()):
                if n.endswith("_Timeseries.csv") and "ADCIRC" in n:
                    d = parse_naccs_csv(zf.read(n).decode("utf-8", "replace"))
                    if d is not None:
                        yield f"{path.name}:{Path(n).name}", d
                elif n.endswith("_Timeseries.h5") and "ADCIRC" in n:
                    raise ValueError(f"{path}: .h5 inside a zip — unzip it first")
        return
    if path.suffix.lower() == ".csv":
        d = parse_naccs_csv(path.read_text(errors="replace"))
    elif path.suffix.lower() == ".h5":
        d = read_naccs_h5(path, t0, t1, positions)
    else:
        return
    if d is not None:
        yield path.name, d


def load_save_points(
    sources,
    times,
    positions: dict | None = None,
    log=print,
) -> SavePoints:
    """Read every source (in order) and put each point on ``times`` (datetime64[m]) by
    linear interpolation. A save point already read (same ID) is skipped, so a later
    ``--extra-dir`` never overrides the archive. A point without finite u, v and p at
    every time is dropped (logged)."""
    times = np.asarray(times, dtype="datetime64[m]")
    t0, t1 = times[0], times[-1]
    tq = times.astype("int64").astype("f8")
    seen: dict[int, str] = {}
    out = {k: [] for k in ("sp", "lon", "lat", "depth", "u", "v", "p", "src")}
    dropped = []
    for src in sources:
        n_src = 0
        for name, d in iter_raw_points(Path(src), t0, t1, positions):
            if d["sp"] in seen:
                continue
            k = (d["t"] >= t0 - _PAD) & (d["t"] <= t1 + _PAD)
            ti = d["t"][k].astype("int64").astype("f8")
            if ti.size < 2 or ti[0] > tq[0] or ti[-1] < tq[-1]:
                dropped.append((d["sp"], "window not covered"))
                continue
            series = [np.interp(tq, ti, d[c][k]) for c in ("u", "v", "p_hpa")]
            if not all(np.isfinite(s).all() for s in series):
                dropped.append((d["sp"], "NaN in window"))
                continue
            seen[d["sp"]] = name
            out["sp"].append(d["sp"])
            out["lon"].append(d["lon"])
            out["lat"].append(d["lat"])
            out["depth"].append(d["depth"])
            out["u"].append(series[0])
            out["v"].append(series[1])
            out["p"].append(series[2])
            out["src"].append(name)
            n_src += 1
        log(f"[naccs] {src}: {n_src} save points")
    if dropped:
        log(f"[naccs] dropped {len(dropped)}: {dropped[:10]}")
    if not out["sp"]:
        raise ValueError("no NACCS save points with the storm in the window")
    return SavePoints(
        np.array(out["sp"]),
        np.array(out["lon"]),
        np.array(out["lat"]),
        np.array(out["depth"]),
        times,
        np.array(out["u"]),
        np.array(out["v"]),
        np.array(out["p"]),
        np.array(out["src"], dtype=object),
    )


def dead_wind(pts: SavePoints) -> np.ndarray:
    """Save points whose wind is exactly 0 at EVERY step of the window: ADCIRC wrote no
    wind there (9 of the 1,957 local points for Sandy, depths -1.2..9.5 m). Using them
    would paint a calm hole into the field."""
    return np.all((pts.u == 0) & (pts.v == 0), axis=1)


def read_positions_csv(path: Path) -> dict:
    """``sp,lat,lon[,kml_z|depth...]`` -> {sp: (lat, lon, depth)} (the CHS KML list made
    by ``logs/wind_products_2026-10-06/naccs_points.py``), for ``.h5`` files without
    position attributes."""
    out = {}
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            z = r.get("depth_m") or r.get("kml_z") or r.get("depth") or "nan"
            out[int(r["sp"])] = (float(r["lat"]), float(r["lon"]), float(z))
    return out


# ── geometry ─────────────────────────────────────────────────────────────────


def triangle_max_edge(tri) -> np.ndarray:
    """Longest edge (m) of every triangle."""
    pts, s = tri.points, tri.simplices
    e = np.stack(
        [
            np.hypot(*(pts[s[:, a]] - pts[s[:, b]]).T)
            for a, b in ((0, 1), (1, 2), (2, 0))
        ],
        axis=1,
    )
    return e.max(axis=1)


def triangulate(x, y, max_edge_m: float):
    """Delaunay triangulation of the points + a per-triangle KEEP flag (every edge <=
    ``max_edge_m``)."""
    from scipy.spatial import Delaunay

    tri = Delaunay(np.column_stack([np.asarray(x, "f8"), np.asarray(y, "f8")]))
    return tri, triangle_max_edge(tri) <= max_edge_m


def land_fraction(tri, xq, yq, is_land):
    """Per triangle: share of the query points inside it that are land, and how many
    query points it holds (0 -> fraction 0). ``is_land`` False also for "unknown"."""
    q = np.column_stack([np.ravel(xq), np.ravel(yq)]).astype("f8")
    simp = tri.find_simplex(q)
    ok = simp >= 0
    nt = tri.simplices.shape[0]
    count = np.bincount(simp[ok], minlength=nt)
    land = np.bincount(
        simp[ok], weights=np.ravel(is_land)[ok].astype("f8"), minlength=nt
    )
    frac = np.divide(land, count, out=np.zeros(nt), where=count > 0)
    return frac, count


def land_mask_from_faces(fx, fy, fz, X, Y, land_z: float, max_dist_m: float):
    """Grid cells whose NEAREST model face (within ``max_dist_m``) has bed ``fz`` above
    ``land_z``: land. Cells with no face that close are "unknown" -> False."""
    from scipy.spatial import cKDTree

    d, j = cKDTree(np.column_stack([fx, fy])).query(
        np.column_stack([np.ravel(X), np.ravel(Y)])
    )
    land = (np.asarray(fz)[j] > land_z) & (d <= max_dist_m)
    return land.reshape(np.shape(X))


def interp_weights(tri, keep, xq, yq):
    """Sparse (nq x npts) linear-barycentric weights and a ``covered`` flag per query:
    covered = inside a KEPT triangle. Uncovered rows are all zero."""
    from scipy import sparse

    q = np.column_stack([np.ravel(xq), np.ravel(yq)]).astype("f8")
    simp = tri.find_simplex(q)
    covered = simp >= 0
    covered[covered] = keep[simp[covered]]
    idx = np.flatnonzero(covered)
    T = tri.transform[simp[idx]]  # (n, 3, 2)
    b2 = np.einsum("nij,nj->ni", T[:, :2, :], q[idx] - T[:, 2, :])
    bary = np.column_stack([b2, 1.0 - b2.sum(axis=1)])
    bary = np.clip(bary, 0.0, 1.0)
    bary /= bary.sum(axis=1, keepdims=True)
    cols = tri.simplices[simp[idx]]
    W = sparse.csr_matrix(
        (bary.ravel(), (np.repeat(idx, 3), cols.ravel())),
        shape=(q.shape[0], tri.points.shape[0]),
    )
    return W, covered


def taper_weight(dist_m, taper_m: float):
    """Half-cosine: 1 at distance 0, 0 at ``taper_m`` and beyond (``taper_m`` = 0 ->
    a hard edge)."""
    d = np.asarray(dist_m, dtype="f8")
    if taper_m <= 0:
        return (d <= 0).astype("f8")
    s = np.clip(d / float(taper_m), 0.0, 1.0)
    return 0.5 * (1.0 + np.cos(np.pi * s))


def coverage_distance(covered2d, dx: float, dy: float | None = None):
    """Distance (m) from every cell to the nearest COVERED cell and that cell's (row,
    col) index arrays (scipy EDT). Covered cells: 0 and themselves."""
    from scipy.ndimage import distance_transform_edt

    covered2d = np.asarray(covered2d, bool)
    if not covered2d.any():
        raise ValueError("no covered cell: the NACCS points do not reach the grid")
    dy = abs(dx) if dy is None else abs(dy)
    dist, (ri, ci) = distance_transform_edt(
        ~covered2d, sampling=(dy, abs(dx)), return_indices=True
    )
    return dist, ri, ci


class HarmonicExtension:
    """Extend a field known on the COVERED cells to every other cell by discrete Laplace
    (harmonic) interpolation: each uncovered cell is the mean of its 4 neighbours,
    covered cells are fixed (Dirichlet), the grid edge is no-flux (a missing neighbour
    is left out). Continuous at the zone edge, smooth outside it, within the min / max
    of the edge values (maximum principle) — unlike a nearest-cell copy, which paints
    rays (Voronoi edges) wherever the edge values vary. The sparse LU factorisation is
    built once for the geometry and reused for every field and time step."""

    def __init__(self, covered2d):
        from scipy import sparse
        from scipy.ndimage import binary_dilation, label
        from scipy.sparse.linalg import splu

        cov = np.asarray(covered2d, bool)
        if not cov.any():
            raise ValueError("no covered cell: nothing to extend from")
        self.shape = cov.shape
        self.cov = cov
        ny, nx = cov.shape
        # uncovered components that touch no covered cell would make the system
        # singular: they get 0 (cannot happen while any cell is covered and the grid is
        # one piece, but kept as a guard)
        lab, n = label(~cov)
        touch = np.zeros(n + 1, bool)
        touch[np.unique(lab[binary_dilation(cov) & ~cov])] = True
        touch[0] = False
        self.free = (~cov) & touch[lab]
        self.dead = (~cov) & ~touch[lab]
        idx = -np.ones(cov.shape, int)
        idx[self.free] = np.arange(int(self.free.sum()))
        cidx = -np.ones(cov.shape, int)
        cidx[cov] = np.arange(int(cov.sum()))
        rows, cols, vals, brow, bcol = [], [], [], [], []
        jj, ii = np.nonzero(self.free)
        deg = np.zeros(jj.size)
        for dj, di in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            j2, i2 = jj + dj, ii + di
            ok = (j2 >= 0) & (j2 < ny) & (i2 >= 0) & (i2 < nx)
            deg += ok
            k = np.flatnonzero(ok)
            nb_free = idx[j2[k], i2[k]]
            nb_cov = cidx[j2[k], i2[k]]
            f = nb_free >= 0
            rows.append(idx[jj[k[f]], ii[k[f]]])
            cols.append(nb_free[f])
            vals.append(-np.ones(f.sum()))
            c = nb_cov >= 0
            brow.append(idx[jj[k[c]], ii[k[c]]])
            bcol.append(nb_cov[c])
        nfree = jj.size
        rows.append(np.arange(nfree))
        cols.append(np.arange(nfree))
        vals.append(deg)
        A = sparse.csc_matrix(
            (np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))),
            shape=(nfree, nfree),
        )
        br = np.concatenate(brow)
        self.B = sparse.csr_matrix(
            (np.ones(br.size), (br, np.concatenate(bcol))),
            shape=(nfree, int(cov.sum())),
        )
        self.lu = splu(A)

    def __call__(self, field):
        """``field`` (..., ny, nx), finite on covered cells -> filled everywhere."""
        f = np.asarray(field, dtype="f8")
        lead = f.shape[:-2]
        flat = f.reshape(-1, *self.shape)
        known = flat[:, self.cov].T  # (ncov, nslices)
        if not np.isfinite(known).all():
            raise ValueError("the field is not finite on every covered cell")
        sol = self.lu.solve(np.asarray(self.B @ known))  # (nfree, nslices)
        out = np.zeros_like(flat)
        out[:, self.cov] = known.T
        out[:, self.free] = sol.T
        return out.reshape(*lead, *self.shape)


def blend(naccs, era5, w, extend):
    """``era5 + w * A`` where ``A`` is the anomaly ``naccs - era5`` on the covered cells,
    extended outward by ``extend`` (a :class:`HarmonicExtension`). Arrays (nt, ny, nx);
    ``naccs`` is finite on the covered cells and NaN elsewhere. Exactly NACCS where it
    is defined (``era5 + 1 * (naccs - era5)`` is not, in floats)."""
    anom = np.where(extend.cov[None], naccs - era5, 0.0)
    ext = extend(anom)
    return np.where(np.isfinite(naccs), naccs, era5 + w[None] * ext)


# ── grid + ERA5 ──────────────────────────────────────────────────────────────


def target_grid(xmin, xmax, ymin, ymax, dx: float, margin_m: float = 0.0):
    """Cell centres on whole multiples of ``dx`` covering the box + margin: ``x``
    ascending, ``y`` DESCENDING (hydromt's order). Two extra cells each side keep every
    point inside the engine's accepted band (``meteo_grid.engine_accepted_band`` drops
    the cell next to the last file row)."""
    lo_x = (np.floor((xmin - margin_m) / dx) - 2) * dx
    hi_x = (np.ceil((xmax + margin_m) / dx) + 2) * dx
    lo_y = (np.floor((ymin - margin_m) / dx) - 2) * dx
    hi_y = (np.ceil((ymax + margin_m) / dx) + 2) * dx
    x = np.arange(round(lo_x / dx), round(hi_x / dx) + 1) * dx
    y = np.arange(round(hi_y / dx), round(lo_y / dx) - 1, -1) * dx
    return x.astype("f8"), y.astype("f8")


def era5_bilinear(era5, lon2d, lat2d, times):
    """Native ERA5 (``wind10_u``, ``wind10_v``, ``press_msl`` on lon ``x`` / lat ``y``)
    sampled bilinearly IN LON/LAT at the given points, then linearly in time onto
    ``times`` (hourly -> e.g. 30 min). Returns u, v, p_pa as (nt, *lon2d.shape)."""
    import xarray as xr

    nat = xr.open_dataset(era5) if isinstance(era5, (str, Path)) else era5
    nat = nat[["wind10_u", "wind10_v", "press_msl"]]
    tt = np.asarray(times, dtype="datetime64[ns]")
    tsel = nat["time"].values
    need = (tsel >= tt[0] - np.timedelta64(1, "h")) & (
        tsel <= tt[-1] + np.timedelta64(1, "h")
    )
    nat = nat.isel(time=np.flatnonzero(need)).load()
    if nat["time"].values[0] > tt[0] or nat["time"].values[-1] < tt[-1]:
        raise ValueError("ERA5 does not cover the requested times")
    lon, lat = nat["x"].values, nat["y"].values
    if (
        np.nanmin(lon2d) < lon.min()
        or np.nanmax(lon2d) > lon.max()
        or np.nanmin(lat2d) < lat.min()
        or np.nanmax(lat2d) > lat.max()
    ):
        raise ValueError("the target grid reaches outside native ERA5")
    sp = nat.interp(
        x=xr.DataArray(lon2d, dims=("j", "i")),
        y=xr.DataArray(lat2d, dims=("j", "i")),
        method="linear",
    )
    sp = sp.interp(time=tt, method="linear")
    out = [sp[v].transpose("time", "j", "i").values.astype("f8") for v in sp.data_vars]
    if any(np.isnan(a).any() for a in out):
        raise ValueError("NaN in bilinear ERA5")
    return tuple(out)


# ── the whole field ──────────────────────────────────────────────────────────


def select_triangles(
    px,
    py,
    X,
    Y,
    max_edge_m: float,
    land2d=None,
    max_land_frac: float = 1.0,
    short_edge_m: float = 0.0,
):
    """Triangulate the points and choose the triangles NACCS is interpolated on.

    Dropped: any triangle with an edge > ``max_edge_m``; and a triangle whose longest
    edge exceeds ``short_edge_m`` when more than ``max_land_frac`` of the grid cells
    (``X``, ``Y``) inside it are land (``land2d``; None = no land test). Short triangles
    (narrow channels, barrier islands) are always kept; long ones only over water
    (Delaware Bay yes; the Cape May peninsula or Staten Island no).
    Returns ``(tri, keep, n_long, n_land)``.
    """
    tri, keep = triangulate(px, py, max_edge_m)
    n_long = int((~keep).sum())
    n_land = 0
    if land2d is not None and max_land_frac < 1.0:
        frac, count = land_fraction(tri, X, Y, land2d)
        longish = triangle_max_edge(tri) > short_edge_m
        landy = keep & longish & (count > 0) & (frac > max_land_frac)
        n_land = int(landy.sum())
        keep = keep & ~landy
    return tri, keep, n_long, n_land


def build_blend(
    pts: SavePoints,
    era5,
    xc,
    yc,
    epsg: int,
    max_edge_m: float,
    taper_m: float,
    land2d=None,
    max_land_frac: float = 1.0,
    short_edge_m: float = 0.0,
):
    """Blended u, v, p (Pa) on the grid (``xc`` ascending, ``yc`` as given) at
    ``pts.times``; triangles chosen by :func:`select_triangles`. Returns a dict with the
    fields and the diagnostics (``w``, ``covered``, ``dist``, ERA5 and NACCS-on-grid
    fields, triangle counts)."""
    from pyproj import Transformer

    to_xy = Transformer.from_crs(4326, int(epsg), always_xy=True)
    to_ll = Transformer.from_crs(int(epsg), 4326, always_xy=True)
    px, py = to_xy.transform(pts.lon, pts.lat)
    X, Y = np.meshgrid(xc, yc)
    tri, keep, n_long, n_land = select_triangles(
        px, py, X, Y, max_edge_m, land2d, max_land_frac, short_edge_m
    )
    W, covered = interp_weights(tri, keep, X, Y)
    shape = X.shape
    nt = pts.times.size
    nac = {}
    for name, arr in (("u", pts.u), ("v", pts.v), ("p", pts.p_hpa * 100.0)):
        g = np.asarray(W @ arr)  # (ncell, nt)
        g = g.T.reshape(nt, *shape)
        g[:, ~covered.reshape(shape)] = np.nan
        nac[name] = g
    cov2 = covered.reshape(shape)
    dist, _, _ = coverage_distance(cov2, xc[1] - xc[0], yc[1] - yc[0])
    ext = HarmonicExtension(cov2)
    w = taper_weight(dist, taper_m)
    LON, LAT = to_ll.transform(X, Y)
    eu, ev, ep = era5_bilinear(era5, LON, LAT, pts.times)
    out = {
        "u": blend(nac["u"], eu, w, ext),
        "v": blend(nac["v"], ev, w, ext),
        "p": blend(nac["p"], ep, w, ext),
        "w": w,
        "covered": cov2,
        "dist": dist,
        "era5": {"u": eu, "v": ev, "p": ep},
        "naccs": nac,
        "pts_xy": (px, py),
        "tri": tri,
        "keep": keep,
        "n_tri_long": n_long,
        "n_tri_land": n_land,
    }
    for k in ("u", "v", "p"):
        if not np.isfinite(out[k]).all():
            raise ValueError(f"non-finite blended {k}")
    return out


# ── writing ──────────────────────────────────────────────────────────────────

_XATTRS = {
    "axis": "X",
    "long_name": "Easting",
    "standard_name": "projection_x_coordinate",
    "units": "metre",
}
_YATTRS = {
    "axis": "Y",
    "long_name": "Northing",
    "standard_name": "projection_y_coordinate",
    "units": "metre",
}


def write_meteo_files(
    out_dir: Path,
    xc,
    yc,
    times,
    u,
    v,
    p_pa,
    epsg: int,
    stamp: str,
    time_units: str = "minutes since 2012-10-28",
) -> list[dict]:
    """Write ``sfincs_netamuv.nc`` (``eastward_wind``, ``northward_wind``) and
    ``sfincs_netamp.nc`` (``barometric_pressure``, Pa) like hydromt does (dims ``time,
    y, x``; float32 data; double coords; ``spatial_ref``; time as double minutes since
    tref), with TRUE CENTRES, then apply ``meteo_grid.fix_meteo_grid_origin`` so the
    coordinates carry the engine's corner convention and its marker. Atomic per file.
    Returns the fix's per-file states."""
    import os

    import xarray as xr
    from pyproj import CRS

    from . import meteo_grid

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    crs = CRS.from_epsg(int(epsg))
    sref = xr.DataArray(0, attrs={**crs.to_cf(), "spatial_ref": crs.to_wkt()})
    coords = {
        "time": np.asarray(times, dtype="datetime64[ns]"),
        "y": np.asarray(yc, "f8"),
        "x": np.asarray(xc, "f8"),
    }

    def da(a, attrs):
        return xr.DataArray(
            np.asarray(a, dtype="f4"),
            dims=("time", "y", "x"),
            coords=coords,
            attrs={**attrs, "grid_mapping": "spatial_ref"},
        )

    files = {
        "sfincs_netamuv.nc": {
            "eastward_wind": da(
                u, {"long_name": "10 m eastward wind", "units": "m s-1"}
            ),
            "northward_wind": da(
                v, {"long_name": "10 m northward wind", "units": "m s-1"}
            ),
        },
        "sfincs_netamp.nc": {
            "barometric_pressure": da(
                p_pa,
                {
                    "long_name": "Mean sea level pressure",
                    "standard_name": "air_pressure_at_mean_sea_level",
                    "units": "Pa",
                },
            )
        },
    }
    for name, dvars in files.items():
        ds = xr.Dataset(dvars)
        ds["spatial_ref"] = sref
        ds["x"].attrs.update(_XATTRS, **{BLEND_ATTR: stamp})
        ds["y"].attrs.update(_YATTRS, **{BLEND_ATTR: stamp})
        ds.attrs[BLEND_ATTR] = stamp
        enc = {
            "time": {
                "units": time_units,
                "dtype": "float64",
                "calendar": "proleptic_gregorian",
            },
            "x": {"_FillValue": None},
            "y": {"_FillValue": None},
        }
        for vname in dvars:
            enc[vname] = {"_FillValue": None, "dtype": "float32"}
        f = out_dir / name
        tmp = f.with_name(f".{name}.blend_tmp")
        ds.to_netcdf(tmp, encoding=enc)
        os.replace(tmp, f)
    return meteo_grid.fix_meteo_grid_origin(out_dir, files=tuple(files))


def read_meteo_true(path: Path, var: str):
    """(x_centres, y_centres, times, F[t, y, x]) of a meteo file at its TRUE centres."""
    import xarray as xr

    from . import meteo_grid

    with xr.open_dataset(path) as src:
        ds = src.load()
    xc, yc = meteo_grid.true_centres(ds)
    return xc, yc, ds["time"].values, ds[var].values.astype("f8")
