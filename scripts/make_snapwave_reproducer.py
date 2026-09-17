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

The IG / wavemaker cases (2026-09-17, FINDINGS §45): ``build --ig`` writes three wind-OFF
cases instead — ``ig_nowm`` (snapwave_igwaves 1, no wavemaker: the premier's situation),
``ig_wm`` (plus a wavemaker line at the −4 m contour, inside the surf-zone refinement band
as v2.4.0 warns it must be) and ``ig_wm_g07`` (the same with snapwave_gammaig 0.7, the
v2.4.0 default; v2.3.3's is 0.2) — with observation points on a cross-shore transect and
``dthisout 2 s`` so the injected IG signal is visible. ``compare-ig`` prints per run the
cross-shore hm0 / hm0ig profile at the last map step and, per station, the IG amplitude
(std of zs over the last hour) and the max water level.

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
    return gpd.GeoDataFrame(
        {"refinement_level": [1]}, geometry=[geom], crs=f"EPSG:{EPSG}"
    )


def _wavemaker_line(z_line: float = -4.0):
    """One straight wavemaker along the z_line depth contour, west→east.

    The reference notebook's rule: looking north, click left to right to generate
    northward — here the beach is north, so the line runs from the west edge to the east
    edge. −4 m keeps it inside the −5..0 m refinement band (a wavemaker point ON a
    quadtree refinement boundary draws a warning in v2.4.0).
    """
    y = Y0 + NY * DX * (z_line - Z_OFFSHORE) / (Z_BEACH - Z_OFFSHORE)
    return [
        {"name": "wm01", "x": [X0 + 0.5 * DX, X0 + NX * DX - 0.5 * DX], "y": [y, y]}
    ]


def _transect_obs():
    """Cross-shore observation points at fixed bed levels, mid-domain."""
    x = X0 + 0.5 * NX * DX
    pts = []
    for z in (-8.0, -4.0, -2.0, -1.0, -0.5, 0.0, 0.5):
        y = Y0 + NY * DX * (z - Z_OFFSHORE) / (Z_BEACH - Z_OFFSHORE)
        pts.append(
            (x, y, f"z{z:+.1f}".replace("+", "p").replace("-", "m").replace(".", "_"))
        )
    return pts


IG_CASES = {
    "ig_nowm": {"snapwave_igwaves": "1"},
    "ig_wm": {"snapwave_igwaves": "1", "wvmfile": "sfincs.wvm"},
    "ig_wm_g07": {
        "snapwave_igwaves": "1",
        "wvmfile": "sfincs.wvm",
        "snapwave_gammaig": "0.7",
    },
}


def build(root: Path, ig: bool = False) -> None:
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
    sf.quadtree_elevation.create(
        elevation_list=[{"elevation": str(bed)}], buffer_cells=0
    )
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
    cases = (
        {k: (0, v) for k, v in IG_CASES.items()}
        if ig
        else {"wind_on": (1, {}), "wind_off": (0, {})}
    )
    for name, (wind, extra) in cases.items():
        d = root / name
        if d.exists():
            shutil.rmtree(d)
        shutil.copytree(base, d)
        _write_forcing(d, pts, t, wind, extra=extra)
        print(f"[build] wrote {d}")


def _write_forcing(
    d: Path, pts: np.ndarray, t: np.ndarray, wind: int, extra: dict | None = None
) -> None:
    extra = dict(extra or {})
    if "wvmfile" in extra:
        from hydromt_sfincs.utils import write_geoms

        write_geoms(d / extra["wvmfile"], _wavemaker_line(), stype="wvm")
    if extra:
        # A transect of observation points and a 2 s his interval: the IG signal has
        # periods of 25–250 s, invisible at the default 600 s.
        with open(d / "sfincs.obs", "w") as f:
            for x, y, nm in _transect_obs():
                f.write(f"{x:.1f} {y:.1f} {nm}\n")
        extra.setdefault("obsfile", "sfincs.obs")
        extra.setdefault("dthisout", "2.0")
        extra.setdefault("storefw", "1")
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
    np.savetxt(d / "sfincs.bzs", np.column_stack([t, np.zeros((2, 2))]), fmt="%11.1f")
    # Uniform wind: t, speed, direction FROM (nautical).
    np.savetxt(
        d / "sfincs.wnd",
        np.column_stack([t, [WIND_SPEED] * 2, [WIND_FROM] * 2]),
        fmt="%11.1f",
    )

    inp = d / "sfincs.inp"
    keep = []
    drop = (
        "tref",
        "tstart",
        "tstop",
        "dtout",
        "dtmapout",
        "dthisout",
        "dtmaxout",
        "snapwave",
        "dtwave",
        "storewavdir",
        "bndfile",
        "bzsfile",
        "wndfile",
        "depfile",
        "mskfile",
        "indexfile",
        "sbgfile",
        "manningfile",
        "inputformat",
    )
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
    keys.update(extra)
    text = "\n".join(keep) + "\n" + "".join(f"{k:<20} = {v}\n" for k, v in keys.items())
    inp.write_text(text)


def run(d: Path, binary: str | None, sif: str | None, threads: int) -> None:
    if bool(binary) == bool(sif):
        raise SystemExit("pass exactly one of --bin / --sif")
    env = dict(os.environ, OMP_NUM_THREADS=str(threads), OMP_STACKSIZE="1G")
    if binary:
        cmd = [str(Path(binary).resolve())]
    else:
        cmd = [
            "singularity",
            "run",
            "-B",
            f"{d.resolve()}:/data",
            "--pwd",
            "/data",
            sif,
        ]
    print(f"[run] {d}: {' '.join(cmd)}  (OMP_NUM_THREADS={threads})")
    with open(d / "sfincs_stdout.txt", "w") as out:
        rc = subprocess.run(
            cmd, cwd=d, env=env, stdout=out, stderr=subprocess.STDOUT
        ).returncode
    print(f"[run] return code {rc}; log {d / 'sfincs.log'}")
    if rc != 0:
        raise SystemExit(rc)


def compare(dirs: list[Path]) -> None:
    import xarray as xr

    print(
        f"imposed: Hs {HS} m, Tp {TP} s, from {WD:.0f}°, spread {DS:.0f}°; "
        f"wind {WIND_SPEED} m/s from {WIND_FROM:.0f}°\n"
    )
    print(
        f"{'run':40s} {'step':>4s} {'bnd wavdir':>11s} {'interior wavdir':>16s} {'bnd hm0':>8s} {'engine'}"
    )
    for d in dirs:
        mp = xr.open_dataset(d / "sfincs_map.nc", decode_times=False)
        if "snapwavemsk" not in mp or "wavdir" not in mp:
            print(
                f"{str(d):40s}  no snapwavemsk/wavdir in sfincs_map.nc (SnapWave off?)"
            )
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
                row.append(
                    np.rad2deg(
                        np.arctan2((w * np.sin(th)).sum(), (w * np.cos(th)).sum())
                    )
                    % 360
                )
            hb = (
                np.nanmedian(h[(swm == 2) & np.isfinite(h)])
                if (swm == 2).any()
                else np.nan
            )
            print(f"{str(d):40s} {it:4d} {row[0]:11.1f} {row[1]:16.1f} {hb:8.2f} {rev}")


def compare_ig(dirs: list[Path]) -> None:
    import xarray as xr

    zbins = [-14.0, -10.0, -6.0, -4.0, -2.0, -1.0, 0.0, 1.0]
    for d in dirs:
        mp = xr.open_dataset(d / "sfincs_map.nc", decode_times=False)
        rev = ""
        log = d / "sfincs.log"
        if log.exists():
            for ln in log.read_text(errors="replace").splitlines():
                if "Build-Revision" in ln:
                    rev = ln.split(":", 1)[-1].strip().strip("$")
                    break
        zb = mp["zb"].values.ravel()
        h = mp["hm0"].isel(time=-1).values.ravel()
        hig = (
            mp["hm0ig"].isel(time=-1).values.ravel()
            if "hm0ig" in mp
            else np.full_like(h, np.nan)
        )
        print(f"\n{d}  [{rev}]")
        print(
            f"  {'bed z bin':>14s} {'hm0':>6s} {'hm0ig':>6s}  (medians over the bin, last map step)"
        )
        for lo, hi in zip(zbins[:-1], zbins[1:]):
            m = (zb >= lo) & (zb < hi) & np.isfinite(h)
            if m.sum() == 0:
                continue
            print(
                f"  {lo:6.1f}..{hi:5.1f} {np.nanmedian(h[m]):6.2f} {np.nanmedian(hig[m]):6.2f}"
            )
        his = d / "sfincs_his.nc"
        if not his.exists():
            continue
        hs = xr.open_dataset(his, decode_times=False)
        zs = hs["point_zs"].values  # (time, station)
        tt = hs["time"].values
        # The his file names stations station_001..; label them by the transect's
        # bed level instead (same order as sfincs.obs).
        names = [nm for _, _, nm in _transect_obs()][: zs.shape[1]]
        last = tt >= tt[-1] - 3600.0
        print(
            f"  {'station':>10s} {'zs std 1h':>9s} {'zs max':>7s} {'zs mean 1h':>10s}  (m)"
        )
        for j, nm in enumerate(names):
            z = zs[last, j]
            z = z[np.isfinite(z)]
            if z.size == 0:
                print(f"  {nm:>10s} {'dry':>9s}")
                continue
            print(
                f"  {nm:>10s} {z.std():9.3f} {np.nanmax(zs[:, j]):7.3f} {z.mean():10.3f}"
            )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("dir", type=Path)
    b.add_argument("--ig", action="store_true", help="the IG / wavemaker cases instead")
    r = sub.add_parser("run")
    r.add_argument("dir", type=Path)
    r.add_argument("--bin")
    r.add_argument("--sif")
    r.add_argument("--threads", type=int, default=2)
    c = sub.add_parser("compare")
    c.add_argument("dirs", type=Path, nargs="+")
    ci = sub.add_parser("compare-ig")
    ci.add_argument("dirs", type=Path, nargs="+")
    a = ap.parse_args(argv)
    if a.cmd == "build":
        build(a.dir, ig=a.ig)
    elif a.cmd == "run":
        run(a.dir, a.bin, a.sif, a.threads)
    elif a.cmd == "compare-ig":
        compare_ig(a.dirs)
    else:
        compare(a.dirs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
