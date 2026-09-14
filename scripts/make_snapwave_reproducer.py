#!/usr/bin/env python
"""Minimal, self-contained reproducer for the SnapWave wind-mode direction bug.

The bug (FINDINGS §43, Deltares issue draft ``docs/upstream/snapwave_winddir_issue.md``):
with ``snapwave_wind = 1`` the imposed wave boundary spectrum is launched in the
domain-mean WIND direction instead of the direction in the ``.bwd`` file. This script
builds a tiny plane-beach quadtree model with a swell from the south and a wind from the
north-east, runs it on one or more SFINCS engines, and prints the boundary-cell mean
wave direction per output step. A correct engine prints ~180°; the bug prints ~45°.

    python scripts/make_snapwave_reproducer.py build  <dir>            # hydromt-sfincs
    python scripts/make_snapwave_reproducer.py run    <dir> --bin BIN  # or --sif IMG
    python scripts/make_snapwave_reproducer.py compare <dir> [<dir> ...]

``build`` writes two run directories under ``<dir>``: ``wind_on`` (the bug) and
``wind_off`` (the control, same waves, no wind term). ``run`` runs one of them in place
with the engine given; ``compare`` reads ``sfincs_map.nc`` from each directory given.

Everything a maintainer needs to run this without our data catalog is generated here:
the bed is an analytic plane, the wind is a uniform ASCII ``wndfile``, the water level
is a constant ASCII ``bzsfile``. Only hydromt-sfincs (for the quadtree file) and the
SFINCS engine are required.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

# ── the case ────────────────────────────────────────────────────────────────────────────
EPSG = 32618  # any projected CRS; the case is analytic
X0, Y0 = 500_000.0, 4_400_000.0
DX = 100.0  # m
NX, NY = 60, 40  # 6 km alongshore (x) × 4 km cross-shore (y)
Z_OFFSHORE, Z_BEACH = -15.0, 3.0  # plane from the south edge (deep) to the north (dry)
HS, TP, WD, DS = 2.0, 10.0, 180.0, 30.0  # swell FROM the south, 30° spread
WIND_SPEED, WIND_FROM = 15.0, 45.0  # wind FROM the north-east: 135° off the swell
DURATION_S = 3 * 3600
TREF = "20200101 000000"


def _bed(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Plane beach: z rises linearly from Z_OFFSHORE at y=Y0 to Z_BEACH at the north edge."""
    frac = (y - Y0) / (NY * DX)
    return Z_OFFSHORE + (Z_BEACH - Z_OFFSHORE) * frac


def _write_bed_tif(path: Path) -> None:
    import rasterio
    from rasterio.transform import from_origin

    # Finer than the grid so hydromt averages it; 25 m pixels, 1 km margin all round.
    res, margin = 25.0, 1000.0
    nx = int((NX * DX + 2 * margin) / res)
    ny = int((NY * DX + 2 * margin) / res)
    xs = X0 - margin + res * (np.arange(nx) + 0.5)
    ys = Y0 + NY * DX + margin - res * (np.arange(ny) + 0.5)  # north-up
    xx, yy = np.meshgrid(xs, ys)
    z = _bed(xx, yy).astype("float32")
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=ny,
        width=nx,
        count=1,
        dtype="float32",
        crs=f"EPSG:{EPSG}",
        transform=from_origin(X0 - margin, Y0 + NY * DX + margin, res, res),
        nodata=-9999.0,
    ) as dst:
        dst.write(z, 1)


def _south_strip():
    import geopandas as gpd
    import shapely

    # The deep row of cells along the south edge, generously buffered: the water-level
    # AND the wave boundary.
    geom = shapely.box(X0 - DX, Y0 - DX, X0 + NX * DX + DX, Y0 + 1.5 * DX)
    return gpd.GeoDataFrame(geometry=[geom], crs=f"EPSG:{EPSG}")


def _surf_zone_refinement():
    import geopandas as gpd
    import shapely

    # The band where the plane crosses −5..0 m, refined once (50 m cells).
    y_lo = Y0 + NY * DX * (-5.0 - Z_OFFSHORE) / (Z_BEACH - Z_OFFSHORE)
    y_hi = Y0 + NY * DX * (0.0 - Z_OFFSHORE) / (Z_BEACH - Z_OFFSHORE)
    geom = shapely.box(X0, y_lo, X0 + NX * DX, y_hi)
    return gpd.GeoDataFrame({"refinement_level": [1]}, geometry=[geom], crs=f"EPSG:{EPSG}")


def build(root: Path) -> None:
    import pyproj  # noqa: F401  (import before hydromt_sfincs — CLAUDE.md §5)
    from hydromt_sfincs import SfincsModel

    root.mkdir(parents=True, exist_ok=True)
    base = root / "_base"
    if base.exists():
        shutil.rmtree(base)
    bed = root / "bed.tif"
    _write_bed_tif(bed)

    sf = SfincsModel(root=str(base), mode="w+", write_gis=False)
    # One refinement level in the surf zone. Not for accuracy: SFINCS writes a
    # single-level quadtree with its REGULAR map writer, which has no `wavdir`
    # variable; the quadtree writer (any mesh with ≥ 2 levels) does.
    sf.quadtree_grid.create(
        x0=X0,
        y0=Y0,
        nmax=NY,
        mmax=NX,
        dx=DX,
        dy=DX,
        rotation=0.0,
        epsg=EPSG,
        refinement_polygons=_surf_zone_refinement(),
    )
    sf.quadtree_elevation.create(elevation_list=[{"elevation": str(bed)}], buffer_cells=0)
    strip = _south_strip()
    sf.quadtree_mask.create_active(zmin=-100.0, zmax=2.0)
    sf.quadtree_mask.create_boundary(btype="waterlevel", include_polygon=strip)
    sf.quadtree_snapwave_mask.create_active(zmin=-100.0, zmax=2.0)
    sf.quadtree_snapwave_mask.create_boundary(btype="waves", include_polygon=strip)
    sf.write()

    msk = sf.quadtree_grid.data["mask"].values
    swm = sf.quadtree_grid.data["snapwave_mask"].values
    print(
        f"[build] faces {msk.size}: sfincs active {int((msk == 1).sum())} "
        f"wl-boundary {int((msk == 2).sum())}; snapwave active {int((swm == 1).sum())} "
        f"wave-boundary {int((swm == 2).sum())}"
    )
    if (swm == 2).sum() == 0 or (msk == 2).sum() == 0:
        raise SystemExit("no boundary cells — the south strip missed the grid")

    # Support points: three along the south edge, in the deep row.
    pts = np.array([[X0 + f * NX * DX, Y0 + 0.5 * DX] for f in (0.1, 0.5, 0.9)])
    t = np.array([0.0, DURATION_S])
    for name, wind in (("wind_on", 1), ("wind_off", 0)):
        d = root / name
        if d.exists():
            shutil.rmtree(d)
        shutil.copytree(base, d)
        _write_forcing(d, pts, t, wind)
        print(f"[build] wrote {d}")


def _write_forcing(d: Path, pts: np.ndarray, t: np.ndarray, wind: int) -> None:
    np.savetxt(d / "snapwave.bnd", pts, fmt="%.3f")
    for fn, val in (
        ("snapwave.bhs", HS),
        ("snapwave.btp", TP),
        ("snapwave.bwd", WD),
        ("snapwave.bds", DS),
    ):
        block = np.full((len(t), len(pts)), val)
        np.savetxt(
            d / fn,
            np.column_stack([t, block]),
            fmt=["%11.1f"] + ["%11.3f"] * len(pts),
        )
    # Water level: two points on the south edge, 0.0 m throughout.
    np.savetxt(
        d / "sfincs.bnd",
        np.array([[X0, Y0 + 0.5 * DX], [X0 + NX * DX, Y0 + 0.5 * DX]]),
        fmt="%.3f",
    )
    np.savetxt(
        d / "sfincs.bzs", np.column_stack([t, np.zeros((2, 2))]), fmt="%11.1f"
    )
    # Uniform wind: t, speed, direction FROM (nautical).
    np.savetxt(
        d / "sfincs.wnd",
        np.column_stack([t, [WIND_SPEED] * 2, [WIND_FROM] * 2]),
        fmt="%11.1f",
    )

    inp = d / "sfincs.inp"
    keep = []
    drop = ("tref", "tstart", "tstop", "dtout", "dtmapout", "dthisout", "dtmaxout",
            "snapwave", "dtwave", "storewavdir", "bndfile", "bzsfile", "wndfile",
            "depfile", "mskfile", "indexfile", "sbgfile", "manningfile", "inputformat")
    for ln in inp.read_text().splitlines():
        key = ln.split("=")[0].strip()
        if key and not key.startswith(drop):
            keep.append(ln)
    keys = {
        "tref": TREF,
        "tstart": TREF,
        "tstop": "20200101 030000",
        "dtmapout": "1800.0",
        "dthisout": "600.0",
        "dtmaxout": str(DURATION_S) + ".0",
        "bndfile": "sfincs.bnd",
        "bzsfile": "sfincs.bzs",
        "wndfile": "sfincs.wnd",
        "manning": "0.02",
        "snapwave": "1",
        "snapwave_wind": str(wind),
        "snapwave_igwaves": "0",
        "snapwave_sector": "360",
        "snapwave_dtheta": "10",
        "snapwave_niter": "100",
        "dtwave": "1800.0",
        "storewavdir": "1",
        "snapwave_bndfile": "snapwave.bnd",
        "snapwave_bhsfile": "snapwave.bhs",
        "snapwave_btpfile": "snapwave.btp",
        "snapwave_bwdfile": "snapwave.bwd",
        "snapwave_bdsfile": "snapwave.bds",
    }
    text = "\n".join(keep) + "\n" + "".join(f"{k:<20} = {v}\n" for k, v in keys.items())
    inp.write_text(text)


def run(d: Path, binary: str | None, sif: str | None, threads: int) -> None:
    if bool(binary) == bool(sif):
        raise SystemExit("pass exactly one of --bin / --sif")
    env = dict(os.environ, OMP_NUM_THREADS=str(threads), OMP_STACKSIZE="1G")
    if binary:
        cmd = [str(Path(binary).resolve())]
    else:
        cmd = ["singularity", "run", "-B", f"{d.resolve()}:/data", "--pwd", "/data", sif]
    print(f"[run] {d}: {' '.join(cmd)}  (OMP_NUM_THREADS={threads})")
    with open(d / "sfincs_stdout.txt", "w") as out:
        rc = subprocess.run(cmd, cwd=d, env=env, stdout=out, stderr=subprocess.STDOUT).returncode
    print(f"[run] return code {rc}; log {d / 'sfincs.log'}")
    if rc != 0:
        raise SystemExit(rc)


def compare(dirs: list[Path]) -> None:
    import xarray as xr

    print(
        f"imposed: Hs {HS} m, Tp {TP} s, from {WD:.0f}°, spread {DS:.0f}°; "
        f"wind {WIND_SPEED} m/s from {WIND_FROM:.0f}°\n"
    )
    print(f"{'run':40s} {'step':>4s} {'bnd wavdir':>11s} {'interior wavdir':>16s} {'bnd hm0':>8s} {'engine'}")
    for d in dirs:
        mp = xr.open_dataset(d / "sfincs_map.nc", decode_times=False)
        if "snapwavemsk" not in mp or "wavdir" not in mp:
            print(f"{str(d):40s}  no snapwavemsk/wavdir in sfincs_map.nc (SnapWave off?)")
            continue
        swm = mp["snapwavemsk"].values.ravel()
        rev = ""
        log = d / "sfincs.log"
        if log.exists():
            for ln in log.read_text(errors="replace").splitlines():
                if "Build-Revision" in ln:
                    rev = ln.split(":", 1)[-1].strip().strip("$")
                    break
        for it in range(mp.sizes["time"]):
            wd = mp["wavdir"].isel(time=it).values.ravel()
            h = mp["hm0"].isel(time=it).values.ravel()
            row = []
            for sel in (swm == 2, swm == 1):
                m = sel & np.isfinite(wd) & np.isfinite(h) & (h > 0.05)
                if m.sum() == 0:
                    row.append(np.nan)
                    continue
                th = np.deg2rad(wd[m])
                w = h[m] ** 2
                row.append(np.rad2deg(np.arctan2((w * np.sin(th)).sum(), (w * np.cos(th)).sum())) % 360)
            hb = np.nanmedian(h[(swm == 2) & np.isfinite(h)]) if (swm == 2).any() else np.nan
            print(f"{str(d):40s} {it:4d} {row[0]:11.1f} {row[1]:16.1f} {hb:8.2f} {rev}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("dir", type=Path)
    r = sub.add_parser("run")
    r.add_argument("dir", type=Path)
    r.add_argument("--bin")
    r.add_argument("--sif")
    r.add_argument("--threads", type=int, default=2)
    c = sub.add_parser("compare")
    c.add_argument("dirs", type=Path, nargs="+")
    a = ap.parse_args(argv)
    if a.cmd == "build":
        build(a.dir)
    elif a.cmd == "run":
        run(a.dir, a.bin, a.sif, a.threads)
    else:
        compare(a.dirs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
