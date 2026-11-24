"""SnapWave boundary forcing from a REGULAR lon/lat wave grid (GFS-Wave ``atlocn.0p16``).

The hindcast reads its wave boundary from CORA, an unstructured SWAN mesh, by NEAREST
node with a 5 km guard (``model._point_wave_bnd``). That cannot work on a 1/6° grid
(~14 x 18 km cells): most support points are > 5 km from every cell centre, and the
points near the coast have land (missing) cells among their neighbours. This module is
the regular-grid path:

* :func:`point_weights` — per support point, the cells and weights to use:

  1. **bilinear** over the 4 surrounding cells, using only WET corners (finite in every
     variable at every time) and renormalising their weights. ``method`` is
     ``"bilinear"`` when all 4 are wet, ``"partial"`` when 1–3 are;
  2. if no wet corner carries weight (all land, or the point is off the grid),
     **inverse-distance** (power 2) over the ``k`` nearest wet cells within
     ``max_dist_m`` (default 30 km) — ``"idw"``;
  3. if no wet cell is that close, :class:`ValueError` naming the point.

* :func:`interp_points` — apply those weights to ``hs`` / ``tp`` / ``wd``. Hs and Tp
  are linear in the weights. Direction is averaged as UNIT VECTORS, weighted by
  ``weight x Hs`` by default (``dir_weighting="hs"``): the direction of the sea that
  carries the energy wins over a sheltered low-Hs corner, and it reduces to the plain
  weighted vector mean when the corners' Hs are equal. ``"plain"`` uses the weights
  alone. The result is put back on 0 <= wd < 360, so 350° and 10° average to 0°, never
  180°. Nautical "coming from" in = nautical "coming from" out: the average is of
  angles, so the convention passes through unchanged.

* :func:`read_gfswave` — GFS-Wave GRIB2 files -> the canonical dataset this module
  takes: ``hs`` / ``tp`` / ``wd`` on ``(time, lat, lon)``, lon in -180..180, lat
  ascending, ``time`` = VALID time (UTC). ``HTSGW`` -> ``hs`` (m), ``PERPW`` -> ``tp``
  (s), ``DIRPW`` -> ``wd`` (deg, nautical from). ⚠️ Those are PEAK period and PEAK
  (primary-wave) direction; CORA's are SWAN ``TPS`` (smoothed peak) and ``DIR`` (MEAN
  direction). Same units and convention, not quite the same statistic.

The model side (``model._grid_wave_bnd``) clips to ``tref`` exactly as the CORA path
does, so ``t`` is seconds from ``BaseConfig.tref``.

Run as a script to build the canonical NetCDF from GRIB files and print, per support
point, the method and the distance it reached::

    python -m nj_sfincs.wave_grid <gribs...> --points <lon,lat csv> -o waves.nc
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

R_EARTH = 6_371_000.0
VARS = ("hs", "tp", "wd")

#: GFS-Wave GRIB2 name -> (cfgrib shortName, canonical name).
GFSWAVE_VARS = {
    "HTSGW": ("swh", "hs"),
    "PERPW": ("perpw", "tp"),
    "DIRPW": ("dirpw", "wd"),
}


@dataclass(frozen=True)
class PointWeights:
    """Cells and weights for one support point (indices into the (lat, lon) grid)."""

    ilat: np.ndarray
    ilon: np.ndarray
    w: np.ndarray  # sums to 1
    method: str  # "bilinear" | "partial" | "idw"
    dist_m: float  # distance to the farthest cell carrying weight


def _haversine(lon0, lat0, lon, lat):
    p0, p = np.deg2rad(lat0), np.deg2rad(lat)
    a = (
        np.sin((p - p0) / 2) ** 2
        + np.cos(p0) * np.cos(p) * np.sin(np.deg2rad(lon - lon0) / 2) ** 2
    )
    return 2 * R_EARTH * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def _bracket(c: np.ndarray, v: float):
    """``(i, frac)`` with ``c[i] <= v <= c[i+1]`` on ascending ``c``; None off-grid."""
    if v < c[0] or v > c[-1]:
        return None
    i = int(np.clip(np.searchsorted(c, v, side="right") - 1, 0, len(c) - 2))
    return i, (v - c[i]) / (c[i + 1] - c[i])


def wet_mask(ds: xr.Dataset) -> np.ndarray:
    """(lat, lon) bool: ``hs`` finite at every time (land = missing).

    From Hs ALONE (audit 11-23): a wave product may leave period / direction undefined
    in a calm at a sea cell; that must not turn the cell into land for every time step.
    ``interp_points`` renormalises over the corners where tp / wd are defined.
    """
    a = ds["hs"].transpose(..., "lat", "lon").values
    return np.isfinite(a).reshape(-1, ds.sizes["lat"], ds.sizes["lon"]).all(axis=0)


def point_weights(
    glon,
    glat,
    wet: np.ndarray,
    plon,
    plat,
    *,
    k: int = 4,
    max_dist_m: float = 30_000.0,
) -> list[PointWeights]:
    """Interpolation weights for each point; see the module docstring for the rules.

    ``glon`` / ``glat`` are the grid's 1-D ascending axes (same lon convention as
    ``plon``), ``wet`` is ``(lat, lon)``.
    """
    glon = np.asarray(glon, float)
    glat = np.asarray(glat, float)
    if np.any(np.diff(glon) <= 0) or np.any(np.diff(glat) <= 0):
        raise ValueError("grid axes must be strictly ascending (see read_gfswave)")
    wj, wi = np.nonzero(wet)  # lat idx, lon idx of every wet cell
    if not len(wj):
        raise ValueError("the wave grid has no wet cell")
    out = []
    for n, (lo, la) in enumerate(zip(np.asarray(plon, float), np.asarray(plat, float))):
        bx, by = _bracket(glon, lo), _bracket(glat, la)
        if bx is not None and by is not None:
            (i, fx), (j, fy) = bx, by
            jj = np.array([j, j, j + 1, j + 1])
            ii = np.array([i, i + 1, i, i + 1])
            w = np.array([(1 - fx) * (1 - fy), fx * (1 - fy), (1 - fx) * fy, fx * fy])
            ok = wet[jj, ii] & (w > 0)
            # the distance cap holds here too (audit 11-23): a wet corner beyond
            # max_dist_m is not used; with none left, the IDW branch decides / raises
            ok &= _haversine(lo, la, glon[ii], glat[jj]) <= max_dist_m
            if ok.any():
                d = _haversine(lo, la, glon[ii[ok]], glat[jj[ok]])
                method = "bilinear" if wet[jj, ii].all() else "partial"
                out.append(
                    PointWeights(jj[ok], ii[ok], w[ok] / w[ok].sum(), method, d.max())
                )
                continue
        d = _haversine(lo, la, glon[wi], glat[wj])
        near = np.argsort(d)[:k]
        near = near[d[near] <= max_dist_m]
        if not len(near):
            raise ValueError(
                f"wave support point {n} (lon {lo:.5f}, lat {la:.5f}): nearest wet "
                f"grid cell is {d.min() / 1000:.1f} km away (limit "
                f"{max_dist_m / 1000:.0f} km). The wave grid does not cover this point."
            )
        dn = np.maximum(d[near], 1.0)  # a point ON a wet centre takes that cell
        w = 1.0 / dn**2
        out.append(PointWeights(wj[near], wi[near], w / w.sum(), "idw", d[near].max()))
    return out


def _circmean(wd_deg: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Weighted vector mean of ``wd_deg`` (time, cells) -> (time,), on [0, 360).

    ``w`` is (time, cells). Where the resultant vanishes (opposite directions, or all
    weight zero) the direction of the heaviest cell is taken.
    """
    r = np.deg2rad(wd_deg)
    s = (w * np.sin(r)).sum(axis=-1)
    c = (w * np.cos(r)).sum(axis=-1)
    out = np.rad2deg(np.arctan2(s, c))
    bad = np.hypot(s, c) <= 1e-9 * np.maximum(np.abs(w).sum(axis=-1), 1e-300)
    if bad.any():
        heavy = np.take_along_axis(wd_deg, np.argmax(w, axis=-1)[:, None], -1)[:, 0]
        out = np.where(bad, heavy, out)
    out = np.mod(out, 360.0)
    return np.where(out >= 360.0, out - 360.0, out)


def interp_points(
    ds: xr.Dataset,
    plon,
    plat,
    *,
    k: int = 4,
    max_dist_m: float = 30_000.0,
    dir_weighting: str = "hs",
):
    """Per-point ``hs`` / ``tp`` / ``wd`` series from a canonical wave grid.

    ``ds`` has ``hs`` / ``tp`` / ``wd`` on ``(time, lat, lon)`` (any time axis; extra
    dims are not allowed), ascending axes. ``plon`` may be -180..180 or 0..360: it is
    put on the grid's convention. Returns ``(out, weights)``, ``out`` a dict of
    ``(ntime, npoints)`` float64 arrays.
    """
    if dir_weighting not in ("hs", "plain"):
        raise ValueError(
            f"dir_weighting must be 'hs' or 'plain', not {dir_weighting!r}"
        )
    ds = ds.transpose("time", "lat", "lon")
    glon = np.asarray(ds["lon"].values, float)
    plon = np.asarray(plon, float)
    plon = np.mod(plon, 360.0) if glon.max() > 180.0 else ((plon + 180) % 360) - 180
    weights = point_weights(
        glon, ds["lat"].values, wet_mask(ds), plon, plat, k=k, max_dist_m=max_dist_m
    )
    arr = {v: np.asarray(ds[v].values, float) for v in VARS}
    out = {v: np.empty((ds.sizes["time"], len(weights))) for v in VARS}
    for n, pw in enumerate(weights):
        hs = arr["hs"][:, pw.ilat, pw.ilon]
        out["hs"][:, n] = hs @ pw.w
        # tp / wd may be undefined (NaN) at a wet corner in a calm: renormalise over the
        # corners where they are defined; all undefined -> NaN (the caller refuses it)
        tpc = arr["tp"][:, pw.ilat, pw.ilon]
        wtp = np.where(np.isfinite(tpc), pw.w[None, :], 0.0)
        with np.errstate(invalid="ignore", divide="ignore"):
            out["tp"][:, n] = np.where(
                wtp.sum(1) > 0, np.nansum(tpc * wtp, 1) / wtp.sum(1), np.nan
            )
        wdc = arr["wd"][:, pw.ilat, pw.ilon]
        wdir = np.where(np.isfinite(wdc), pw.w[None, :], 0.0)
        hs = np.where(np.isfinite(hs), hs, 0.0)
        if dir_weighting == "hs":
            whs = wdir * hs
            # a flat calm (Hs 0 at every corner) has no energy to weight by
            wdir = np.where(whs.sum(axis=1, keepdims=True) > 0, whs, wdir)
        wd = _circmean(np.where(np.isfinite(wdc), wdc, 0.0), wdir)
        out["wd"][:, n] = np.where(np.isfinite(wdc).any(1), wd, np.nan)
    return out, weights


def canonical(ds: xr.Dataset) -> xr.Dataset:
    """Rename lon/lat/time axes to ``lon`` / ``lat`` / ``time``, lon to -180..180,
    both ascending. Accepts cfgrib's ``longitude`` / ``latitude`` / ``valid_time``."""
    ren = {a: b for a, b in (("longitude", "lon"), ("latitude", "lat")) if a in ds.dims}
    ds = ds.rename(ren)
    lon = np.asarray(ds["lon"].values, float)
    ds = ds.assign_coords(lon=((lon + 180.0) % 360.0) - 180.0)
    return ds.sortby("lon").sortby("lat")


def read_gfswave(paths, bbox=None) -> xr.Dataset:
    """GFS-Wave GRIB2 file(s) -> the canonical ``(time, lat, lon)`` dataset.

    One file per forecast hour (``gfswave.tCCz.atlocn.0p16.fFFF.grib2``); ``time`` is
    each message's VALID time. Where two files give the same valid time (chaining
    ``f000``–``f005`` of successive cycles), the LATER cycle wins. ``bbox`` = (W, S, E,
    N) in -180..180 cuts the grid after reading. Needs ``cfgrib`` (eccodes); no index
    files are written beside the GRIB.
    """
    frames = []
    for p in sorted(Path(x) for x in np.atleast_1d(paths)):
        g = xr.open_dataset(
            p,
            engine="cfgrib",
            backend_kwargs={
                "indexpath": "",
                "filter_by_keys": {"typeOfLevel": "surface"},
            },
        )
        missing = [s for s, _ in GFSWAVE_VARS.values() if s not in g]
        if missing:
            raise KeyError(f"{p.name}: no {missing} (HTSGW/PERPW/DIRPW) in the file")
        d = g[[s for s, _ in GFSWAVE_VARS.values()]].rename(
            {s: c for s, c in GFSWAVE_VARS.values()}
        )
        d = d.load()
        cycle = pd.Timestamp(g["time"].values)
        d = d.drop_vars([c for c in d.coords if c not in ("latitude", "longitude")])
        d = d.expand_dims(time=[pd.Timestamp(g["valid_time"].values)])
        d = d.assign_coords(cycle=("time", [cycle]))
        frames.append(d)
        g.close()
    ds = xr.concat(frames, dim="time")
    order = np.lexsort((ds["cycle"].values, ds["time"].values))
    ds = ds.isel(time=order)
    t = pd.DatetimeIndex(ds["time"].values)
    last = ~t.duplicated(keep="last")  # same valid time: keep the latest cycle
    ds = canonical(ds.isel(time=np.flatnonzero(last)))
    if bbox is not None:
        w, s, e, n = bbox
        ds = ds.sel(lon=slice(w, e), lat=slice(s, n))
    units = {"hs": "m", "tp": "s", "wd": "degrees (nautical, coming from)"}
    for v, (gname, _) in zip(VARS, GFSWAVE_VARS.items()):
        ds[v].attrs = {"units": units[v], "source": f"GFS-Wave {gname}"}
    ds.attrs = {
        "source": "NOAA GFS-Wave (WAVEWATCH III) atlocn.0p16",
        "time": "valid, UTC",
    }
    return ds


def _main(argv=None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("gribs", nargs="+", type=Path)
    ap.add_argument("--points", type=Path, help="CSV with lon,lat columns")
    ap.add_argument("-o", "--out", type=Path, help="write the canonical NetCDF here")
    ap.add_argument("--max-dist-km", type=float, default=30.0)
    ap.add_argument("--pad-deg", type=float, default=1.0)
    a = ap.parse_args(argv)

    pts = pd.read_csv(a.points) if a.points else None
    bbox = None
    if pts is not None:
        p = a.pad_deg
        bbox = (
            pts.lon.min() - p,
            pts.lat.min() - p,
            pts.lon.max() + p,
            pts.lat.max() + p,
        )
    ds = read_gfswave(a.gribs, bbox=bbox)
    print(
        f"grid {ds.sizes['lat']} x {ds.sizes['lon']}, {ds.sizes['time']} times "
        f"{pd.Timestamp(ds.time.values[0])} .. {pd.Timestamp(ds.time.values[-1])}"
    )
    if a.out:
        tmp = a.out.with_suffix(".nc.tmp")
        ds.to_netcdf(tmp)
        tmp.replace(a.out)
        print(f"wrote {a.out}")
    if pts is not None:
        out, wts = interp_points(ds, pts.lon, pts.lat, max_dist_m=a.max_dist_km * 1e3)
        meth = pd.Series([w.method for w in wts])
        print(meth.value_counts().to_string())
        for n, w in enumerate(wts):
            print(
                f"pt {n:3d} lon {pts.lon[n]:9.4f} lat {pts.lat[n]:8.4f} {w.method:8s} "
                f"{len(w.w)} cells, farthest {w.dist_m / 1000:5.1f} km   "
                f"Hs {out['hs'][0, n]:5.2f}  Tp {out['tp'][0, n]:5.2f}  "
                f"Dir {out['wd'][0, n]:6.1f}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
