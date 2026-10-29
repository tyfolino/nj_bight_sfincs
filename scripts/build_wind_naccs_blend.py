"""Build a NACCS -> ERA5 blended wind + pressure forcing (``sfincs_netamuv.nc`` /
``sfincs_netamp.nc``) for a quadtree template (default v4_hot_plus_walls).

NACCS ADCIRC save-point u, v, p interpolated linearly on a Delaunay triangulation (long
triangles dropped) onto a regular UTM grid that covers every active AND SnapWave face,
tapered into ERA5 (bilinear in lon/lat at true positions) over ``--taper-km`` outside the
covered zone. Written in hydromt's format with the engine's corner convention + marker
(``nj_sfincs.meteo_grid``), so ``model.finalize`` sees it as already fixed. Method and
choices: ``nj_sfincs/meteo_blend.py`` and ``logs/wind_naccs_blend_2026-10-06/README.md``.

The template is READ ONLY (sfincs.inp, sfincs.nc, the existing netamuv's time units).
More CHS save points (e.g. the validation / shelf points of
``logs/wind_products_2026-10-06/naccs_fetch_list.csv``) are added with ``--extra-dir``;
the taper and coverage are re-derived from whatever points are read.

Usage (compute node):
    python scripts/build_wind_naccs_blend.py [--naccs-dir ZIP_OR_DIR] [--extra-dir DIR]
        [--out data/wind_v4/naccs_blend] [--taper-km 15] [--dx 500]
        [--max-edge-km 20] [--short-edge-km 5] [--land-z 2] [--max-land-frac 0.5]
        [--dt-min 30] [--min-depth 0] [--pad-km 5]
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nj_sfincs import meteo_blend as mb  # noqa: E402
from nj_sfincs import meteo_grid  # noqa: E402

# v4_hot_plus_walls' template (the 10-06 build's) was removed 2026-10-28; same mesh.
DEF_TEMPLATE = ROOT / "experiments/v4_refreeze/_template_sealed"
DEF_NACCS = ROOT / "data/NACCS/naccs_repack_ADCIRC01.zip"
DEF_ERA5 = ROOT / "data/era5/era5_nj_sandy_2012_10_28_31.nc"
DEF_POS = ROOT / "logs/wind_products_2026-10-06/naccs_savepoints_all.csv"
DEF_OUT = ROOT / "data/wind_v4/naccs_blend"


def read_inp(model_dir: Path) -> dict:
    out = {}
    for ln in (model_dir / "sfincs.inp").read_text().splitlines():
        k, _, v = ln.partition("=")
        out[k.strip()] = v.strip()
    return out


def inp_time(s: str) -> np.datetime64:
    d, t = s.split()
    return np.datetime64(f"{d[:4]}-{d[4:6]}-{d[6:8]}T{t[:2]}:{t[2:4]}", "m")


def model_faces(model_dir: Path):
    """(x, y, is_active) of every face that is SFINCS-active OR SnapWave-active, and
    (x, y, z) of ALL faces (the bed, for the land test)."""
    import netCDF4

    with netCDF4.Dataset(model_dir / "sfincs.nc") as nc:
        m = np.asarray(nc.variables["mask"][:]) > 0
        s = (
            np.asarray(nc.variables["snapwave_mask"][:]) > 0
            if "snapwave_mask" in nc.variables
            else np.zeros_like(m)
        )
        keep = m | s
        ax = np.asarray(nc.variables["mesh2d_face_x"][:], "f8")
        ay = np.asarray(nc.variables["mesh2d_face_y"][:], "f8")
        az = np.asarray(nc.variables["z"][:], "f8")
    return ax[keep], ay[keep], m[keep], (ax, ay, az)


def md5(p: Path, n=1 << 22) -> str:
    h = hashlib.md5()
    with open(p, "rb") as fh:
        while b := fh.read(n):
            h.update(b)
    return h.hexdigest()


def src_label(p: Path) -> str:
    p = Path(p)
    return f"`{p}` (md5 {md5(p)})" if p.is_file() else f"`{p}` (directory)"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument(
        "--naccs-dir",
        action="append",
        type=Path,
        default=None,
        help="repack zip or directory of CHS ADCIRC time-series files "
        f"(repeatable; default {DEF_NACCS.relative_to(ROOT)})",
    )
    ap.add_argument(
        "--extra-dir",
        action="append",
        type=Path,
        default=[],
        help="more CHS save points (csv / h5 / zip), read after --naccs-dir; "
        "a save point already read is skipped",
    )
    ap.add_argument(
        "--positions",
        type=Path,
        default=DEF_POS,
        help="sp,lat,lon table for .h5 files without position attributes",
    )
    ap.add_argument(
        "--template",
        type=Path,
        default=DEF_TEMPLATE,
        help="model dir (read-only): grid extent, epsg, window, time units",
    )
    ap.add_argument("--era5", type=Path, default=DEF_ERA5)
    ap.add_argument("--out", type=Path, default=DEF_OUT)
    ap.add_argument("--taper-km", type=float, default=15.0)
    ap.add_argument("--dx", type=float, default=500.0, help="grid step (m)")
    ap.add_argument(
        "--max-edge-km",
        type=float,
        default=20.0,
        help="drop Delaunay triangles with any edge longer than this",
    )
    ap.add_argument(
        "--short-edge-km",
        type=float,
        default=5.0,
        help="triangles whose edges are all <= this are kept without the land test",
    )
    ap.add_argument(
        "--land-z",
        type=float,
        default=2.0,
        help="a grid cell is LAND when the bed (template sfincs.nc z, "
        "nearest face) is above this (m NAVD88)",
    )
    ap.add_argument(
        "--max-land-frac",
        type=float,
        default=0.5,
        help="drop a triangle longer than --short-edge-km with more than "
        "this share of land cells (1 = no land test)",
    )
    ap.add_argument(
        "--pressure",
        choices=("blend", "era5"),
        default="blend",
        help="blend = NACCS pressure blended like the wind (default); era5 = ERA5 "
        "bilinear pressure everywhere (NACCS reads 3-9 hPa high at the buoys)",
    )
    ap.add_argument(
        "--dt-min",
        type=int,
        default=30,
        help="output time step (min); 30 = the engine's dtwnd 1800 s",
    )
    ap.add_argument(
        "--min-depth",
        type=float,
        default=0.0,
        help="exclude save points with Save Point Depth below this (m; "
        "negative = above MSL = land, where ADCIRC's wind is land-reduced)",
    )
    ap.add_argument(
        "--pad-km",
        type=float,
        default=5.0,
        help="grid margin beyond the active + SnapWave faces",
    )
    ap.add_argument(
        "--extent",
        type=float,
        nargs=4,
        default=None,
        metavar=("XMIN", "XMAX", "YMIN", "YMAX"),
        help="override the grid box (model CRS, m); for scoring builds only",
    )
    a = ap.parse_args(argv)
    sources = a.naccs_dir or [DEF_NACCS]

    inp = read_inp(a.template)
    epsg = int(float(inp["epsg"]))
    t0, t1 = inp_time(inp["tstart"]), inp_time(inp["tstop"])
    tref = inp_time(inp["tref"])
    times = np.arange(t0, t1 + np.timedelta64(1, "m"), np.timedelta64(a.dt_min, "m"))
    if times[-1] != t1:
        raise SystemExit(f"--dt-min {a.dt_min} does not divide the window {t0}..{t1}")
    tu_src = a.template / "sfincs_netamuv.nc"
    time_units = f"minutes since {str(tref)[:10]}"
    if tu_src.is_file():
        import netCDF4

        with netCDF4.Dataset(tu_src) as nc:
            time_units = nc.variables["time"].getncattr("units")
    print(
        f"[blend] window {t0} .. {t1} every {a.dt_min} min ({times.size} steps); "
        f"time units {time_units!r}; EPSG:{epsg}",
        flush=True,
    )

    positions = mb.read_positions_csv(a.positions) if a.positions.is_file() else None
    pts_all = mb.load_save_points(list(sources) + list(a.extra_dir), times, positions)
    land = ~(pts_all.depth >= a.min_depth)  # NaN depth counts as land
    dead = mb.dead_wind(pts_all)
    reason = np.where(land, "land", np.where(dead, "dead wind (all zero)", ""))
    use = reason == ""
    pts = pts_all.subset(use)
    print(
        f"[blend] {len(pts_all)} save points read, {land.sum()} excluded as land "
        f"(depth < {a.min_depth} m), {int((dead & ~land).sum())} more as dead wind "
        f"(exactly 0 m/s at every step), {len(pts)} used",
        flush=True,
    )

    fx, fy, is_act, (ax, ay, az) = model_faces(a.template)
    if a.extent:
        xmin, xmax, ymin, ymax = a.extent
    else:
        xmin, xmax, ymin, ymax = fx.min(), fx.max(), fy.min(), fy.max()
    xc, yc = mb.target_grid(xmin, xmax, ymin, ymax, a.dx, a.pad_km * 1e3)
    print(
        f"[blend] grid {xc.size} x {yc.size} at {a.dx:.0f} m: x {xc[0]:.0f}..{xc[-1]:.0f}"
        f" y {yc[0]:.0f}..{yc[-1]:.0f}",
        flush=True,
    )

    X, Y = np.meshgrid(xc, yc)
    land2d = mb.land_mask_from_faces(ax, ay, az, X, Y, a.land_z, max(2000.0, 2 * a.dx))
    del ax, ay, az
    res = mb.build_blend(
        pts,
        a.era5,
        xc,
        yc,
        epsg,
        a.max_edge_km * 1e3,
        a.taper_km * 1e3,
        land2d=land2d,
        max_land_frac=a.max_land_frac,
        short_edge_m=a.short_edge_km * 1e3,
    )
    print(
        f"[blend] triangles: {res['keep'].size} total, {res['n_tri_long']} dropped as "
        f"long (> {a.max_edge_km:g} km), {res['n_tri_land']} as land (> "
        f"{a.max_land_frac:g} of cells above {a.land_z:g} m), {int(res['keep'].sum())} "
        f"kept; covered cells {int(res['covered'].sum())}",
        flush=True,
    )

    stamp = (
        f"NACCS ADCIRC01 save-point wind+pressure ({len(pts)} pts, depth >= "
        f"{a.min_depth} m) linear-Delaunay (max edge {a.max_edge_km:g} km; over "
        f"{a.short_edge_km:g} km only if land share <= {a.max_land_frac:g} above "
        f"{a.land_z:g} m) blended into "
        f"ERA5 bilinear (true positions) with a {a.taper_km:g} km half-cosine taper "
        f"(pressure: {a.pressure}); "
        f"{a.dx:.0f} m EPSG:{epsg} grid, {a.dt_min} min "
        "(nj_sfincs.meteo_blend, scripts/build_wind_naccs_blend.py)"
    )
    a.out.mkdir(parents=True, exist_ok=True)
    p_out = res["p"] if a.pressure == "blend" else res["era5"]["p"]
    states = mb.write_meteo_files(
        a.out,
        xc,
        yc,
        times,
        res["u"],
        res["v"],
        p_out,
        epsg,
        stamp,
        time_units=time_units,
    )
    print(meteo_grid.describe(states), flush=True)

    # the weight / coverage on the grid, for figures and the record
    import xarray as xr

    xr.Dataset(
        {
            "w": (("y", "x"), res["w"].astype("f4")),
            "covered": (("y", "x"), res["covered"].astype("i1")),
            "dist_m": (("y", "x"), res["dist"].astype("f4")),
            "land": (("y", "x"), land2d.astype("i1")),
        },
        coords={"y": yc, "x": xc},
        attrs={
            mb.BLEND_ATTR: stamp,
            "note": "TRUE cell centres (not the engine convention); w = NACCS weight",
        },
    ).to_netcdf(a.out / "blend_weight.nc")
    with open(a.out / "points.csv", "w", newline="") as fh:
        wr = csv.writer(fh)
        wr.writerow(["sp", "lon", "lat", "depth_m", "used", "excluded", "source"])
        for i in range(len(pts_all)):
            wr.writerow(
                [
                    pts_all.sp[i],
                    f"{pts_all.lon[i]:.6f}",
                    f"{pts_all.lat[i]:.6f}",
                    f"{pts_all.depth[i]:.3f}",
                    int(use[i]),
                    reason[i],
                    pts_all.source[i],
                ]
            )

    # the band check the engine needs: every active / SnapWave face inside
    xw, yw = meteo_grid.engine_coords(xc, yc)
    b = meteo_grid.engine_accepted_band(xw, yw)
    out_band = int(
        (
            (fx < b["x_min"])
            | (fx >= b["x_max"])
            | (fy <= b["y_min"])
            | (fy >= b["y_max"])
        ).sum()
    )
    if out_band and not a.extent:
        raise SystemExit(f"{out_band} model faces outside the engine band")
    cov_faces = None
    if not a.extent:
        W, cov = mb.interp_weights(res["tri"], res["keep"], fx[is_act], fy[is_act])
        cov_faces = float(cov.mean())

    try:
        head = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            check=False,
            text=True,
        ).stdout.strip()
    except OSError:
        head = "?"
    lines = [
        "# NACCS -> ERA5 blended wind + pressure (PROVENANCE)",
        "",
        f"Written {dt.datetime.now().isoformat(timespec='seconds')} by "
        f"`scripts/build_wind_naccs_blend.py` (git HEAD {head}, working tree may differ).",
        "Method, checks and scores: `logs/wind_naccs_blend_2026-10-06/README.md`.",
        "",
        "Command:",
        "",
        "```",
        "python " + " ".join([str(Path(sys.argv[0]).as_posix())] + sys.argv[1:]),
        "```",
        "",
        "| item | value |",
        "|---|---|",
        f"| template (read-only) | `{a.template}` |",
        f"| NACCS sources | {', '.join(src_label(s) for s in sources)} |",
        f"| extra sources | {', '.join(src_label(s) for s in a.extra_dir) or 'none'} |",
        f"| ERA5 | `{a.era5}` (md5 {md5(a.era5)}) |",
        f"| save points | {len(pts_all)} read, {int(land.sum())} land (depth < "
        f"{a.min_depth} m) and {int((dead & ~land).sum())} dead-wind (all 0 m/s) "
        f"excluded, {len(pts)} used (`points.csv`) |",
        f"| window | {t0} .. {t1}, {a.dt_min} min, {times.size} steps, `{time_units}` |",
        f"| grid | {xc.size} x {yc.size}, {a.dx:.0f} m, EPSG:{epsg}, true centres x "
        f"{xc[0]:.0f}..{xc[-1]:.0f}, y {yc[0]:.0f}..{yc[-1]:.0f} (y descending) |",
        f"| triangulation | linear barycentric on u, v, p separately; of "
        f"{res['keep'].size} triangles, {res['n_tri_long']} dropped with an edge > "
        f"{a.max_edge_km:g} km, {res['n_tri_land']} longer than {a.short_edge_km:g} km "
        f"dropped as land (> "
        f"{a.max_land_frac:g} of their grid cells have bed > {a.land_z:g} m at the "
        f"nearest template face), {int(res['keep'].sum())} kept |",
        f"| taper | half-cosine over {a.taper_km:g} km from the covered zone; "
        f"anomaly (NACCS - ERA5) extended by harmonic (Laplace) interpolation from the zone edge |",
        f"| pressure | {a.pressure} |",
        f"| covered grid cells | {int(res['covered'].sum())} of {res['covered'].size} |",
    ]
    if cov_faces is not None:
        lines.append(f"| active faces inside the covered zone | {cov_faces:.3f} |")
    lines += [
        f"| faces outside the engine band | {out_band} |",
        "| coordinates | engine corner convention (`nj_sfincs.meteo_grid`), marker "
        f"`{meteo_grid.ORIGIN_ATTR}` on x, y and global |",
        "",
        "| file | bytes | md5 |",
        "|---|---|---|",
    ]
    for f in ("sfincs_netamuv.nc", "sfincs_netamp.nc", "blend_weight.nc", "points.csv"):
        p = a.out / f
        lines.append(f"| `{f}` | {p.stat().st_size:,} | {md5(p)} |")
    (a.out / "PROVENANCE.md").write_text("\n".join(lines) + "\n")
    print(f"[blend] wrote {a.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
