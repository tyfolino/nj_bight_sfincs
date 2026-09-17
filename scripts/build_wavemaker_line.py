#!/usr/bin/env python
"""Build the SFINCS wavemaker line for a domain: the "5 m at high tide" contour, SMOOTHED.

    NJ_DOMAIN=v3 python scripts/build_wavemaker_line.py \\
        [--dep experiments/v3/_template_sealed/subgrid/dep_subgrid_lev0.tif] \\
        [--depth 5 --mhw 0.6 --sigma-m 400 --along-window-m 1000 --spacing-m 100] \\
        [--y-max 4480000 --x-min 520000] \\
        --out data/wavemakers_v3/v3_wavemaker_5m_mhw.geojson

WHY (STATUS 2026-09-17, FINDINGS §45): SnapWave's infragravity energy reaches SFINCS only
through a wavemaker (Leijnse et al. 2025, App. B), placed "at ~5 m depth at high tide" in the
surf zone. A raw −5 m contour of NJ bathymetry is jumpy (shoals, ebb deltas, borrow pits), and a
jumpy line is a bad absorbing-generating boundary. So:

1. The bed is Gaussian-smoothed with ``--sigma-m`` and contoured at MHW − depth. That contour
   decides WHERE ALONG THE COAST the line runs and where it breaks.
2. Each vertex is then snapped along its shore-normal onto the crossing of a LIGHTLY smoothed
   bed (``--sigma-light-m``): heavy smoothing drags a contour landward on a steep profile
   (Monmouth: the σ 400 m contour sat on the beach), so the heavy contour must not set the
   offshore distance.
3. The line is moving-averaged along its length (``--along-window-m`` before the snap,
   ``--snap-window-m`` after), simplified and resampled at ``--spacing-m``.

WHICH PIECES — the open Atlantic side only, decided per vertex on bed PROFILES along the
shore-normal, majority-smoothed along the line: the smoothed bed reaches ``--seaward-z``
somewhere between 2 km and ``--probe-sea-m`` seaward (a bay's −5 m contour has no shelf behind
it), AND the lightly smoothed bed reaches MHW somewhere within ``--probe-land-m`` landward (a
barrier island is dry land even when the bay starts 500 m behind it; an offshore shoal is not).
An inlet mouth fails the land test for a kilometre and breaks the line there. Plus two
coordinate gates: south of ``--y-max`` (the tip of Sandy Hook — nothing in Sandy Hook Bay,
Raritan Bay or Lower Bay: a wavemaker inside a bay is a trap, FINDINGS Closed) and east of
``--x-min`` (Delaware Bay). Thresholds, not derived polygons (CLAUDE.md §6).

ORIENTATION: the engine generates to the LEFT of the vertex order (plane-beach toy,
2026-09-17: a west→east line generated northward). Every piece is ordered with its landward
side on the left — south→north along the NJ oceanfront.

REFINEMENT CHECK: v2.4.0 warns against a wavemaker point on a quadtree refinement boundary.
With ``--mesh`` every vertex is checked: the nearest face's level must equal every face's level
within 1.5 cell sizes; the flagged count is a property of each piece.

Output: GeoJSON LineStrings (the raster's CRS) with per-piece properties, a CSV report beside
it, and the northing gaps with no line. hydromt loads it with ``sf.wave_makers.create(...)``.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np


# ── raster helpers ───────────────────────────────────────────────────────────
def smooth_nan(z: np.ndarray, sigma_px: float) -> np.ndarray:
    """Gaussian smoothing that ignores NaN (normalised convolution)."""
    from scipy.ndimage import gaussian_filter

    ok = np.isfinite(z)
    num = gaussian_filter(np.where(ok, z, 0.0), sigma_px, mode="nearest")
    den = gaussian_filter(ok.astype(float), sigma_px, mode="nearest")
    out = np.full_like(z, np.nan)
    m = den > 0.05
    out[m] = num[m] / den[m]
    return out


def contour_pieces(x, y, z, level):
    import contourpy

    cg = contourpy.contour_generator(x, y, np.where(np.isfinite(z), z, 99.0))
    return [np.asarray(ln) for ln in cg.lines(level) if len(ln) >= 2]


def sample_bed(zs, inv, _unused, res, px, py):
    """Nearest-pixel bed at map (px, py) through the raster's INVERSE affine; NaN outside.

    🔴 The v3 subgrid rasters are written on the ROTATED quadtree frame (rotation
    359.183°): their transform has b, d ≠ 0. Treating them as axis-aligned put the first
    version of this line up to 3 km off — on land, on the wrong side of the barrier
    islands (user, QGIS, 2026-09-17). Every pixel↔map conversion goes through the affine.
    """
    cc, rr = inv * (np.asarray(px, float), np.asarray(py, float))
    c = np.floor(cc).astype(int)
    r = np.floor(rr).astype(int)
    ok = (c >= 0) & (c < zs.shape[1]) & (r >= 0) & (r < zs.shape[0])
    out = np.full(len(px), np.nan)
    out[ok] = zs[r[ok], c[ok]]
    return out


def profiles(zs, x0, y0, res, xy, direction, dists):
    """Bed along ``direction`` from each vertex at ``dists`` → (n, len(dists))."""
    out = np.empty((len(xy), len(dists)))
    for j, d in enumerate(dists):
        p = xy + d * direction
        out[:, j] = sample_bed(zs, x0, y0, res, p[:, 0], p[:, 1])
    return out


# ── line helpers ─────────────────────────────────────────────────────────────
def resample(xy, spacing):
    seg = np.hypot(*np.diff(xy, axis=0).T)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    if s[-1] < spacing:
        return xy
    t = np.arange(0.0, s[-1], spacing)
    return np.column_stack([np.interp(t, s, xy[:, 0]), np.interp(t, s, xy[:, 1])])


def moving_average(xy, window_pts):
    if window_pts < 3 or len(xy) < window_pts:
        return xy
    k = np.ones(window_pts) / window_pts
    pad = window_pts // 2
    out = np.empty_like(xy)
    for j in range(2):
        col = np.pad(xy[:, j], pad, mode="edge")
        out[:, j] = np.convolve(col, k, mode="valid")[: len(xy)]
    return out


def _odd(window_m, res):
    return max(3, int(round(window_m / res)) | 1)


def _majority(v, k):
    """Moving majority of a 0/1/NaN series (NaN counts against)."""
    x = np.where(np.isfinite(v), v, 0.0).astype(float)
    pad = k // 2
    m = np.convolve(np.pad(x, pad, mode="edge"), np.ones(k) / k, mode="valid")[: len(x)]
    return m >= 0.5


def normals(xy):
    t = np.gradient(xy, axis=0)
    t /= np.maximum(np.hypot(t[:, 0], t[:, 1]), 1e-9)[:, None]
    return t, np.column_stack([-t[:, 1], t[:, 0]])  # tangent, left-hand normal


def _peel_turned_ends(xy, max_turn_deg):
    d = np.diff(xy, axis=0)
    head = np.degrees(np.arctan2(d[:, 1], d[:, 0]))
    med = np.median(head)
    dev = np.abs((head - med + 180.0) % 360.0 - 180.0)
    ok = dev <= max_turn_deg
    i0, i1 = 0, len(ok)
    while i0 < i1 and not ok[i0]:
        i0 += 1
    while i1 > i0 and not ok[i1 - 1]:
        i1 -= 1
    return xy[i0 : i1 + 1]


def runs(mask):
    out, start = [], None
    for i, m in enumerate(mask):
        if m and start is None:
            start = i
        if not m and start is not None:
            out.append((start, i))
            start = None
    if start is not None:
        out.append((start, len(mask)))
    return out


# ── the classification and the snap ──────────────────────────────────────────
def sea_side(xy, zs, x0, y0, res, k):
    """Per vertex, is the sea on the LEFT of the walk? Deeper side 2 km out, majority-smoothed."""
    _, left = normals(xy)
    zl = sample_bed(zs, x0, y0, res, *(xy + 2000.0 * left).T)
    zr = sample_bed(zs, x0, y0, res, *(xy - 2000.0 * left).T)
    raw = np.where(np.isfinite(zl) & np.isfinite(zr), zl < zr, np.nan)
    return _majority(raw, k)


def open_coast(xy, sea_left, zs, z_light, x0, y0, res, a, k):
    """Per vertex: shelf seaward (heavy bed) AND dry land landward (light bed)."""
    _, left = normals(xy)
    sea = np.where(sea_left, 1.0, -1.0)[:, None] * left
    d_sea = np.arange(2000.0, a.probe_sea_m + 1, 250.0)
    d_land = np.arange(0.0, a.probe_land_m + 1, 100.0)
    zs_sea = profiles(zs, x0, y0, res, xy, sea, d_sea)
    zs_land = profiles(z_light, x0, y0, res, xy, -sea, d_land)
    with np.errstate(invalid="ignore"):
        sea_ok = _majority(np.nanmin(zs_sea, axis=1) <= a.seaward_z, k)
        # a SHORT window for the land test, so a 500 m inlet mouth breaks the line
        land_ok = _majority(
            np.nanmax(zs_land, axis=1) >= a.mhw, _odd(a.land_window_m, res)
        )
    return sea_ok & land_ok


def snap_to_crossing(xy, sea_left, z_light, x0, y0, res, z_line, reach_m):
    """Move each vertex along its normal to the light bed's first land→water crossing of z_line."""
    _, left = normals(xy)
    sea = np.where(sea_left, 1.0, -1.0)[:, None] * left
    d = np.arange(-reach_m, reach_m + 1, res)
    prof = profiles(z_light, x0, y0, res, xy, sea, d)
    out = xy.copy()
    snapped = np.zeros(len(xy), dtype=bool)
    for i in range(len(xy)):
        z = prof[i]
        ok = np.isfinite(z)
        if ok.sum() < 3:
            continue
        zz, dd = z[ok], d[ok]
        cross = np.where((zz[:-1] > z_line) & (zz[1:] <= z_line))[0]
        if len(cross) == 0:
            continue
        j = cross[0]
        f = (zz[j] - z_line) / max(zz[j] - zz[j + 1], 1e-6)
        out[i] = xy[i] + (dd[j] + f * (dd[j + 1] - dd[j])) * sea[i]
        snapped[i] = True
    return out, snapped


def level_flags(xy, mesh: Path):
    """Per vertex: 1 if a face within 1.5 cell sizes of the nearest face has another level."""
    import netCDF4
    from scipy.spatial import cKDTree

    d = netCDF4.Dataset(mesh)
    fx = np.asarray(d.variables["mesh2d_face_x"][:])
    fy = np.asarray(d.variables["mesh2d_face_y"][:])
    lev = np.asarray(d.variables["level"][:])
    dx0 = float(d.getncattr("dx"))
    tree = cKDTree(np.column_stack([fx, fy]))
    _, i0 = tree.query(xy)
    out = np.zeros(len(xy), dtype=int)
    for n, (p, i) in enumerate(zip(xy, i0)):
        nb = tree.query_ball_point(p, 1.5 * dx0 / 2 ** (lev[i] - 1))
        out[n] = int(np.any(lev[nb] != lev[i]))
    return out


# ── main ─────────────────────────────────────────────────────────────────────
def build(a) -> int:
    import geopandas as gpd
    import rasterio
    from shapely.geometry import LineString

    with rasterio.open(a.dep) as r:
        z = r.read(1).astype("float32")
        if r.nodata is not None and np.isfinite(r.nodata):
            z[z == r.nodata] = np.nan
        res = float(r.res[0])
        T = r.transform
        crs = r.crs
    ny, nx = z.shape
    # pixel-centre map coordinates through the affine (rotation included)
    cc, rr = np.meshgrid(np.arange(nx) + 0.5, np.arange(ny) + 0.5)
    XX, YY = T * (cc, rr)
    x0, y0 = ~T, None  # sample_bed takes the INVERSE affine in the x0 slot
    z_line = a.mhw - a.depth
    print(
        f"[bed] {a.dep}: {nx}×{ny} @ {res:g} m; contour z = {z_line:+.2f} m "
        f"(MHW {a.mhw:+.2f} − {a.depth:g} m); σ {a.sigma_m:g} m, light σ {a.sigma_light_m:g} m"
    )
    zs = smooth_nan(z, a.sigma_m / res)
    z_light = smooth_nan(z, a.sigma_light_m / res)
    pieces = contour_pieces(XX, YY, zs, z_line)
    print(f"[contour] {len(pieces)} raw pieces")

    k = _odd(a.along_window_m, res)
    kept, rows = [], []
    for n, raw_xy in enumerate(pieces):
        xy = resample(raw_xy, res)
        length = np.hypot(*np.diff(xy, axis=0).T).sum()
        if length < a.min_length_km * 1e3:
            continue
        sea_left = sea_side(xy, zs, x0, y0, res, k)
        keep = open_coast(xy, sea_left, zs, z_light, x0, y0, res, a, k)
        keep &= (xy[:, 1] <= a.y_max) & (xy[:, 0] >= a.x_min)
        rr = runs(keep)
        rows.append((n, round(length / 1e3, 1), round(float(keep.mean()), 3), len(rr)))
        for i0, i1 in rr:
            seg, sl = xy[i0:i1], sea_left[i0:i1]
            if np.hypot(*np.diff(seg, axis=0).T).sum() < a.min_length_km * 1e3:
                continue
            seg = moving_average(seg, k)  # where along the coast
            seg, snapped = snap_to_crossing(
                seg, sl, z_light, x0, y0, res, z_line, a.snap_reach_m
            )
            # a vertex with no land→water crossing within reach is not on a beach
            # profile (ebb delta, channel, shoal): drop it and split the run there
            # …and a vertex whose (light) bed is > --max-off-m from the target depth
            # after the snap sits in a channel, on an ebb delta or on land (a jettied
            # inlet, a spit): drop it too. Both split the run.
            z_at = sample_bed(z_light, x0, y0, res, seg[:, 0], seg[:, 1])
            with np.errstate(invalid="ignore"):
                snapped &= np.abs(z_at - z_line) <= a.max_off_m
            for j0, j1 in runs(snapped):
                sub = seg[j0:j1]
                if np.hypot(*np.diff(sub, axis=0).T).sum() < a.min_length_km * 1e3:
                    continue
                sub = moving_average(sub, _odd(a.snap_window_m, res))  # snap jitter
                if sl[j0:j1].mean() > 0.5:  # land must be on the LEFT of the walk
                    sub = sub[::-1]
                sub = np.asarray(LineString(sub).simplify(a.simplify_m).coords)
                sub = resample(sub, a.spacing_m)
                # resampling interpolates straight between vertices, and a straight
                # segment can cut a jetty or a spit: check the depth again, split again
                z_fin = sample_bed(z_light, x0, y0, res, sub[:, 0], sub[:, 1])
                z_raw = sample_bed(z, x0, y0, res, sub[:, 0], sub[:, 1])
                with np.errstate(invalid="ignore"):
                    ok_fin = (
                        (np.abs(z_fin - z_line) <= a.max_off_m)
                        # and nothing emergent or channel-deep within one raw pixel:
                        # a groin, jetty or dredged channel right under the line
                        & (z_raw <= z_line + a.raw_shallow_m)
                        & (z_raw >= z_line - a.raw_deep_m)
                    )
                for q0, q1 in runs(ok_fin):
                    piece = sub[q0:q1]
                    if (
                        len(piece) >= 2
                        and np.hypot(*np.diff(piece, axis=0).T).sum()
                        >= a.min_length_km * 1e3
                    ):
                        kept.append((n, piece))
    # Set every piece back from its ends: each end borders an inlet (or a spit tip), and
    # the contour swings into the ebb delta over the last few hundred metres (Barnegat:
    # ~560 m, user 2026-09-17). The IG generation stops --end-trim-m short of the gap.
    if a.end_trim_m > 0:
        trimmed = []
        for n, xy in kept:
            # first, peel off end vertices whose heading turns > --end-turn-deg away
            # from the piece's median heading (the contour curling into an ebb delta)
            xy = _peel_turned_ends(xy, a.end_turn_deg)
            if len(xy) < 3:
                continue
            seg_len = np.hypot(*np.diff(xy, axis=0).T)
            s_ = np.concatenate([[0.0], np.cumsum(seg_len)])
            keep_v = (s_ >= a.end_trim_m) & (s_ <= s_[-1] - a.end_trim_m)
            if (
                keep_v.sum() >= 2
                and (s_[-1] - 2 * a.end_trim_m) >= a.min_length_km * 1e3
            ):
                trimmed.append((n, xy[keep_v]))
        kept = trimmed
    kept.sort(key=lambda t: t[1][:, 1].min())

    if not kept:
        print("no piece survived the filters", file=sys.stderr)
        return 2
    feats, flag_pts = [], []
    for pid, (n, xy) in enumerate(kept, 1):
        zr = sample_bed(z, x0, y0, res, xy[:, 0], xy[:, 1])
        flags = level_flags(xy, a.mesh) if a.mesh else np.zeros(len(xy), int)
        flag_pts += [
            (pid, float(px), float(py)) for (px, py), fl in zip(xy, flags) if fl
        ]
        feats.append(
            dict(
                geometry=LineString(xy),
                id=pid,
                raw_piece=n,
                length_km=round(float(np.hypot(*np.diff(xy, axis=0).T).sum() / 1e3), 2),
                n_vertices=len(xy),
                z_raw_median=round(float(np.nanmedian(zr)), 2),
                z_raw_min=round(float(np.nanmin(zr)), 2),
                z_raw_max=round(float(np.nanmax(zr)), 2),
                frac_off_by_1p5m=round(float(np.nanmean(np.abs(zr - z_line) > 1.5)), 3),
                n_level_flags=int(flags.sum()),
                y_south=round(float(xy[0, 1])),
                y_north=round(float(xy[-1, 1])),
            )
        )
    gdf = gpd.GeoDataFrame(feats, crs=crs)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(a.out, driver="GeoJSON")
    if flag_pts:
        from shapely.geometry import Point

        fp = a.out.with_name(a.out.stem + "_level_flags.geojson")
        gpd.GeoDataFrame(
            {"piece": [t[0] for t in flag_pts]},
            geometry=[Point(t[1], t[2]) for t in flag_pts],
            crs=crs,
        ).to_file(fp, driver="GeoJSON")
        print(f"[flags] {len(flag_pts)} vertices on a refinement boundary → {fp}")
        fy = np.array([t[2] for t in flag_pts])
        edges = np.arange(np.floor(fy.min() / 1e4) * 1e4, fy.max() + 1e4, 1e4)
        hist, _ = np.histogram(fy, edges)
        print(
            "        by northing (10 km bins): "
            + ", ".join(f"{e / 1e3:.0f}:{h}" for e, h in zip(edges[:-1], hist) if h)
        )
    rep = a.out.with_suffix(".report.csv")
    with open(rep, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["raw_piece", "length_km", "frac_open_coast", "n_runs"])
        w.writerows(rows)
    print(
        f"[out] {a.out}: {len(gdf)} pieces, {gdf.length_km.sum():.1f} km; report {rep}"
    )
    cols = [
        "id",
        "length_km",
        "n_vertices",
        "z_raw_median",
        "z_raw_min",
        "z_raw_max",
        "frac_off_by_1p5m",
        "n_level_flags",
        "y_south",
        "y_north",
    ]
    print(gdf[cols].to_string(index=False))
    yy = np.array([(f["y_south"], f["y_north"]) for f in feats])
    gaps = [
        (yy[i, 1], yy[i + 1, 0])
        for i in range(len(yy) - 1)
        if yy[i + 1, 0] - yy[i, 1] > 500
    ]
    print(
        "[gaps] northing ranges with no line (> 0.5 km): "
        + (", ".join(f"{g0 / 1e3:.0f}–{g1 / 1e3:.0f} km" for g0, g1 in gaps) or "none")
    )
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    add = ap.add_argument
    add(
        "--dep",
        type=Path,
        default=Path("experiments/v3/_template_sealed/subgrid/dep_subgrid_lev0.tif"),
    )
    add(
        "--mesh",
        type=Path,
        default=Path("experiments/v3/_template_sealed/sfincs.nc"),
        help="quadtree sfincs.nc for the refinement-boundary check ('' to skip)",
    )
    add("--depth", type=float, default=5.0, help="m below high water")
    add("--mhw", type=float, default=0.6, help="MHW above the bed datum (NAVD88), m")
    add(
        "--sigma-m", type=float, default=400.0, help="heavy bed smoothing (the contour)"
    )
    add(
        "--sigma-light-m",
        type=float,
        default=75.0,
        help="light bed smoothing (the snap)",
    )
    add("--along-window-m", type=float, default=1000.0)
    add("--snap-reach-m", type=float, default=1500.0)
    add("--snap-window-m", type=float, default=300.0)
    add(
        "--max-off-m",
        type=float,
        default=2.0,
        help="drop vertices further than this from the target depth",
    )
    add(
        "--raw-shallow-m",
        type=float,
        default=3.0,
        help="drop if the RAW bed is this much shallower",
    )
    add(
        "--raw-deep-m",
        type=float,
        default=6.0,
        help="drop if the RAW bed is this much deeper",
    )
    add("--simplify-m", type=float, default=20.0)
    add("--spacing-m", type=float, default=100.0)
    add("--min-length-km", type=float, default=3.0)
    add(
        "--end-trim-m",
        type=float,
        default=600.0,
        help="setback of every piece end from its inlet/gap",
    )
    add(
        "--end-turn-deg",
        type=float,
        default=35.0,
        help="peel end vertices turning more than this",
    )
    add(
        "--seaward-z",
        type=float,
        default=-8.0,
        help="the heavy bed must reach this between 2 km and --probe-sea-m seaward",
    )
    add("--probe-sea-m", type=float, default=6000.0)
    add(
        "--probe-land-m",
        type=float,
        default=1200.0,
        help="the light bed must reach MHW within this distance landward (beach scale)",
    )
    add("--land-window-m", type=float, default=300.0, help="majority window, land test")
    add("--y-max", type=float, default=4_480_000.0, help="tip of Sandy Hook (UTM 18N)")
    add("--x-min", type=float, default=520_000.0, help="east of Delaware Bay")
    add(
        "--out",
        type=Path,
        default=Path("data/wavemakers_v3/v3_wavemaker_5m_mhw.geojson"),
    )
    a = ap.parse_args(argv)
    if a.mesh is not None and str(a.mesh) in ("", "."):
        a.mesh = None
    return build(a)


if __name__ == "__main__":
    sys.exit(main())
