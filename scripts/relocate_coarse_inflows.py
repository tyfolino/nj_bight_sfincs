#!/usr/bin/env python
"""Find river inflows that pile up on a COARSE face, and move each one down its creek.

    NJ_DOMAIN=v4_refreeze python scripts/relocate_coarse_inflows.py screen [--ref ARM]
    NJ_DOMAIN=v4_refreeze python scripts/relocate_coarse_inflows.py write  OUT.nc [--ref ARM]
    NJ_DOMAIN=v4_refreeze python scripts/relocate_coarse_inflows.py apply  RUN_DIR [--ref ARM]

Found 2026-10-11 on the v4 status notebook's peak map (FINDINGS part 4, "Still open"): a
source on a 100–200 m face over a narrow creek valley (``z_zmax`` 10–33 m) cannot pass its
discharge through the face's subgrid conveyance, so the water stands 2–3.5 m above the tidal
water ~2 km downstream — on the rain-off arm, i.e. on river flow alone. A source on a 25 m
wet face (the Maurice) stays flat. The level of a river flowing on a 4–8 m bed is NOT this:
there the bed rises with the water, so the screen asks for DEPTH at the source, not level.

SCREEN (read-only; the reference arm is waves off, rain off, so river flow is all there is):
  source face size > ``--coarse`` (50 m)
  AND reference peak − ``z_zmin`` at the source > ``--min-depth`` (2 m; river stage on these
      creeks reads 0.3–1.9 m, the pile-ups 2.8–5.6 m)
  AND the peak falls > 1 m within ``--drop-within`` (4 km of path over wet faces; a deep
      coarse face in open tidal water does not fall, a pile-up does).

MOVE: walk from the source face over faces wet in the reference arm (``mesh2d_face_faces``,
shortest path by centre distance) to the first face with size ≤ ``--coarse``, ``z_zmin`` < 0
(a channel below MSL) and mask == 1. That face's centre is the new point.

🔴 THE INFLOW WALLS STAY WHERE THEY ARE. Staging walls the outflow edge within 500 m of each
source (``Domain.wall_outflow_near_sources_m``), from ``Domain.discharge_geodataset``, so that
field defines the MASK: re-staging with moved points would re-open the old crossings (where
the tide can then drain) and change the fingerprint. ``apply`` therefore rewrites only the
SOURCE points of a staged dir (``sfincs_netsrcdisfile.nc``), leaving its mask as it is; ``write``
produces the geodataset for a registry change that must keep the walls on the OLD points.

``apply`` replaces the file by a new inode (write + ``os.replace``), so a hard-linked staged
input is never written through (CLAUDE.md §5).
"""

from __future__ import annotations

import argparse
import heapq
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import xarray as xr  # noqa: E402
from pyproj import Transformer  # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402

import nj_sfincs  # noqa: F401,E402 — pyproj before hydromt
from nj_sfincs import domain as _domain  # noqa: E402
from nj_sfincs.config import exp_root  # noqa: E402

DATA = ROOT / "data"


def downstream_walk(start, wet, ff, fx, fy, accept, max_m=8000.0):
    """Shortest path (by centre distance) from ``start`` over ``wet`` faces; return the
    first face where ``accept`` holds, its path length, and every face reached with its
    distance. ``ff`` is ``mesh2d_face_faces`` (−1 = none)."""
    dist = {int(start): 0.0}
    heap = [(0.0, int(start))]
    done = set()
    while heap:
        d, f = heapq.heappop(heap)
        if f in done:
            continue
        done.add(f)
        if f != start and accept(f):
            return f, d, dist
        if d > max_m:
            break
        for g in ff[f]:
            if g < 0 or not wet[g] or g in done:
                continue
            nd = d + float(np.hypot(fx[g] - fx[f], fy[g] - fy[f]))
            if nd < dist.get(int(g), np.inf):
                dist[int(g)] = nd
                heapq.heappush(heap, (nd, int(g)))
    return None, np.nan, dist


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("mode", choices=("screen", "write", "apply"))
    ap.add_argument("target", nargs="?", help="OUT.nc (write) or RUN_DIR (apply)")
    ap.add_argument("--ref", default="naccs-nowaves+rain-off+slr-0m")
    ap.add_argument("--coarse", type=float, default=50.0)
    ap.add_argument("--min-depth", type=float, default=2.0)
    ap.add_argument("--drop-within", type=float, default=4000.0, help="path m")
    a = ap.parse_args(argv)
    if a.mode != "screen" and not a.target:
        ap.error(f"{a.mode} needs a target")

    dom = _domain.active()
    exp = exp_root()
    g = xr.open_dataset(exp / "_template_sealed" / "sfincs.nc", mask_and_scale=False)
    fx, fy = g["mesh2d_face_x"].values, g["mesh2d_face_y"].values
    mask = g["mask"].values
    size = np.round(float(g.attrs["dx"]) / 2.0 ** (g["level"].values - 1))
    ff = g["mesh2d_face_faces"].values
    ref = exp / a.ref
    with xr.open_dataset(ref / "sfincs_subgrid.nc") as s:
        zmin = s["z_zmin"].values
    with xr.open_dataset(ref / "sfincs_map.nc", decode_times=False) as m:
        pk = m["zsmax"].max("timemax").values
    wet = (mask > 0) & np.isfinite(pk) & (pk - zmin > 0.10)

    gds_path = DATA / "discharge_v4" / f"{dom.discharge_geodataset}.nc"
    gds = xr.open_dataset(gds_path)
    to_utm = Transformer.from_crs(4326, dom.epsg, always_xy=True)
    to_ll = Transformer.from_crs(dom.epsg, 4326, always_xy=True)
    sx, sy = to_utm.transform(gds["lon"].values, gds["lat"].values)
    act = np.flatnonzero(mask > 0)
    _, j = cKDTree(np.c_[fx[act], fy[act]]).query(np.c_[sx, sy])
    src_face = act[j]

    def accept(f):
        return size[f] <= a.coarse and zmin[f] < 0.0 and mask[f] == 1

    print(f"{dom.name}: {len(sx)} sources from {gds_path.name}; reference {a.ref}")
    print(
        "  idx  gauge     size  zmin   peak  dropdn | → new: path_m  size  zmin   peak"
        "   lon       lat"
    )
    moves = {}
    for k, f in enumerate(src_face):
        p0 = pk[f] if wet[f] else np.nan
        _, _, reach = downstream_walk(
            f, wet, ff, fx, fy, lambda _f: False, a.drop_within
        )
        near = [h for h, d in reach.items() if d <= a.drop_within and wet[h]]
        drop = p0 - np.nanmin(pk[near]) if near and np.isfinite(p0) else np.nan
        flag = size[f] > a.coarse and (p0 - zmin[f]) > a.min_depth and drop > 1.0
        line = (
            f"  {k:3d}  {int(gds['index'].values[k]):08d} {size[f]:4.0f} {zmin[f]:6.2f} "
            f"{p0:6.2f} {drop:6.2f}"
        )
        if not flag:
            if np.isfinite(drop) and drop > 1.0:
                print(line + "  (drop > 1 m, not flagged: fine face or shallow)")
            continue
        t, d, _ = downstream_walk(f, wet, ff, fx, fy, accept)
        if t is None:
            print(line + " | 🔴 no ≤ coarse channel face within 8 km — NOT moved")
            continue
        lon, lat = to_ll.transform(fx[t], fy[t])
        moves[k] = (lon, lat)
        print(
            line + f" | {d:7.0f} {size[t]:4.0f} {zmin[t]:6.2f} {pk[t]:6.2f}  "
            f"{lon:.5f} {lat:.5f}"
        )
    print(f"{len(moves)} sources to move")

    if a.mode == "write":
        out = gds.copy(deep=True)
        lon, lat = out["lon"].values.copy(), out["lat"].values.copy()
        notes = []
        for k, (x, y) in moves.items():
            notes.append(
                f"{int(out['index'].values[k]):08d} ({lon[k]:.5f}, {lat[k]:.5f}) -> "
                f"({x:.5f}, {y:.5f})"
            )
            lon[k], lat[k] = x, y
        out = out.assign_coords(lon=("index", lon), lat=("index", lat))
        out.attrs["note"] = (
            gds.attrs.get("note", "")
            + " | 2026-10-11 coarse-face inflows moved down their creeks onto the first"
            " <= 50 m channel face (scripts/relocate_coarse_inflows.py; the inflow WALLS"
            " stay on the old points): " + "; ".join(notes)
        )
        tmp = Path(a.target).with_suffix(".partial.nc")
        out.to_netcdf(tmp)
        os.replace(tmp, a.target)
        print(f"wrote {a.target}")
    elif a.mode == "apply":
        p = Path(a.target) / "sfincs_netsrcdisfile.nc"
        with xr.open_dataset(p) as src:
            s = src.load()
        x, y = s["x"].values.copy(), s["y"].values.copy()
        for k, (lon, lat) in moves.items():
            # the staged file and the geodataset list the sources in the same order;
            # check by position before moving (snap distance ≤ 300 m, model._snap…)
            if np.hypot(x[k] - sx[k], y[k] - sy[k]) > 300.0:
                raise SystemExit(f"station {k} of {p} is not geodataset source {k}")
            x[k], y[k] = to_utm.transform(lon, lat)
        s = s.assign_coords(x=("stations", x), y=("stations", y))
        s.attrs["relocated"] = (
            f"{len(moves)} sources moved (relocate_coarse_inflows.py)"
        )
        tmp = p.with_name(".sfincs_netsrcdisfile.partial.nc")
        s.to_netcdf(tmp)
        os.replace(tmp, p)  # a NEW inode: never writes through a hard link
        print(f"rewrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
