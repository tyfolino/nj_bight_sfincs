#!/usr/bin/env python
"""Build the breach bed overlays for the `bed-breach` sensitivity arms (LOWER-ONLY tiers).

User decisions 2026-10-15 / 10-17 (STATUS FINAL AUDIT Phase 3, FINDINGS part 4 (h)): the
polygons are the user's own, drawn in the Breach Picker
(``logs/breach_picker_2026-10-15/polygons_final_2026-10-15.csv``: named lon/lat vertices,
each polygon closes itself). On a 3 m EPSG:32618 grid:

    wreck_a            a STATED channel: one constant elevation (m NAVD88) per variant —
                       0.0 (the main breach arm) and 1.65 (the bracket: the lowest
                       post-storm crest there, USACE 2012). No survey shows the open
                       inlet (it healed within ~2 weeks), so the value is a statement.
    manto_a, manto_b   the POST-STORM surface: USGS DS767 EAARL-B first surface, flown
                       2012-11-01 / 11-05 (3-8 days after landfall). Not the USACE CZMIL
                       bare earth (2012-11-16): it has no return over the breach water
                       (holes on 34-67 % of the polygons) and stands ~1.5 m higher than
                       EAARL where both see the cut — the closure fill had begun. First
                       surface keeps the surviving houses, so the building burn there
                       survives a lower-only paint. Identical in every variant.
    elsewhere          NoData (the overlay leaves those pixels alone)

Paint it LAST with ``rebuild_subgrid.py --overlay <key>:min``: every pixel becomes
``min(bed, overlay)``, so the lidar's water SURFACE over the bay / ocean side never
raises the bed, and neither does the stated channel where the bed is already deeper.
The JSON sidecar reports, per polygon, how much of it the current merged premier bed
(rotated: sampled through its affine, spot-checked) would actually lower.

``breach_v4_manning.tif`` (user 10-17): constant n 0.025 (an open sand inlet) on the
UNION over all variants of the pixels each overlay actually lowers against the
lake-fixed bed (``min(merged, lake_fix_v4)``, the 10-17 recipe's bed), NoData elsewhere —
one roughness raster both arms share, so they differ only in the channel bottom. Paint
it with ``--manning-overlay manning_water_v4 --manning-overlay breach_v4_manning``.

    python scripts/build_breach_overlay_v4.py --out-dir data/elevation_v4/breach
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from rasterio.features import geometry_mask
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT
from rasterio.warp import Resampling
from shapely.geometry import Polygon
from shapely.ops import transform as shp_transform

ROOT = Path(__file__).resolve().parents[1]
DEF_POLYS = ROOT / "logs/breach_picker_2026-10-15/polygons_final_2026-10-15.csv"
DEF_MERGED = (
    ROOT / "experiments/v4_refreeze/_subgrid_refreeze/subgrid/dep_subgrid_merged.tif"
)
DEF_LAKE_FIX = ROOT / "data/elevation_v4/lake_fix/lake_fix_v4.tif"
RAW = ROOT / "data/elevation/raw"
DEF_POST = RAW / "usgs_eaarlb_ds767/post"  # post_<tile>_18.tif, EPSG:26918, 2.5 m
DEF_USACE = RAW / "usace_post_sandy_2012_9012/usace_post_sandy_2012_nj.vrt"
EAARL_FILL = -32767.0  # untagged in the DS767 tiles (PROVENANCE.md)
EPSG = 32618
RES = 3.0
PAD = 30.0  # m around the polygons' joint bounds
WRECK = ("wreck_a",)
MANTO = ("manto_a", "manto_b")
DEF_WRECK_VALUES = (0.0, 1.65)
CHANNEL_N = 0.025  # s m-1/3, open sand inlet (NLCD open water 0.020, barren 0.040)


def load_polygons(path: Path) -> dict[str, Polygon]:
    """``polygon,name,lon,lat`` rows (``#`` comments) → {polygon: lon/lat Polygon}, the
    vertices in file order. Refuses a polygon with fewer than 3 vertices or an invalid
    (self-crossing) ring."""
    df = pd.read_csv(path, comment="#")
    out = {}
    for key, g in df.groupby("polygon", sort=False):
        if len(g) < 3:
            raise SystemExit(f"{key}: {len(g)} vertices (need >= 3)")
        p = Polygon(list(zip(g.lon, g.lat)))
        if not p.is_valid:
            raise SystemExit(f"{key}: the ring crosses itself")
        out[str(key)] = p
    return out


def variant_tag(value: float) -> str:
    """0.0 → ``"0"``, 1.65 → ``"165"`` (centimetres): the ``breach_v4_wreck<tag>`` key."""
    return f"{int(round(value * 100))}"


def paint(
    shape: tuple[int, int],
    masks: dict[str, np.ndarray],
    wreck_value: float,
    post: np.ndarray,
) -> np.ndarray:
    """The overlay: ``wreck_value`` inside every WRECK polygon, the post-storm surface
    inside every MANTO polygon (NaN where it has no data), NaN elsewhere."""
    out = np.full(shape, np.nan, dtype="float32")
    for key, m in masks.items():
        if key in WRECK:
            out[m] = wreck_value
        elif key in MANTO:
            out[m] = post[m]
        else:
            raise SystemExit(
                f"polygon {key!r} is neither a Wreck nor a Mantoloking key"
            )
    return out


def _q(v: np.ndarray, f) -> float | None:
    return round(float(f(v)), 3) if v.size else None


def lowering(ov: np.ndarray, bed: np.ndarray, ins: np.ndarray, px_m2: float) -> dict:
    """What ``min(bed, ov)`` does inside ``ins``: area lowered (ov < bed), area already
    at or below the overlay (left alone), the drop there, the volume removed."""
    val = ins & np.isfinite(ov) & np.isfinite(bed)
    low = val & (ov < bed)
    dz = (bed - ov)[low]
    return dict(
        lowered_m2=float(low.sum() * px_m2),
        already_lower_m2=float((val & ~low).sum() * px_m2),
        lowered_gt1m_m2=float((dz > 1).sum() * px_m2),
        drop_mean=_q(dz, np.mean),
        drop_p50=_q(dz, np.median),
        drop_max=_q(dz, np.max),
        volume_removed_m3=round(float(dz.sum() * px_m2)),
    )


def lowered_union(overlays: list[np.ndarray], bed: np.ndarray) -> np.ndarray:
    """Pixels that ``--overlay <key>:min`` would change for ANY of ``overlays``: the
    overlay is valid and either below the bed or the bed has no value there."""
    out = np.zeros(bed.shape, dtype=bool)
    for ov in overlays:
        out |= np.isfinite(ov) & (~np.isfinite(bed) | (ov < bed))
    return out


def stats(v: np.ndarray) -> dict:
    v = v[np.isfinite(v)]
    return dict(min=_q(v, np.min), p50=_q(v, np.median), max=_q(v, np.max))


def warp(path, tr, w, h, src_nodata=None):
    """Nearest onto the 3 m UTM grid. GDAL's warper honours a rotated geotransform."""
    with rasterio.open(path) as src:
        nd = src.nodata if src_nodata is None else src_nodata
        with WarpedVRT(
            src,
            crs=f"EPSG:{EPSG}",
            transform=tr,
            width=w,
            height=h,
            resampling=Resampling.nearest,
            nodata=np.nan,
            src_nodata=nd,
        ) as v:
            a = v.read(1, masked=True).filled(np.nan).astype("float32")
    a[(a < -50) | (a > 300)] = np.nan
    return a


def post_mosaic(tile_dir: Path, tr, w, h) -> np.ndarray:
    """EAARL post tiles that touch the grid, warped and combined (tiles do not overlap)."""
    x0, y1 = tr.c, tr.f
    x1, y0 = x0 + w * RES, y1 - h * RES
    out = np.full((h, w), np.nan, dtype="float32")
    for p in sorted(tile_dir.glob("post_*_18.tif")):
        with rasterio.open(p) as s:
            b = s.bounds  # EPSG:26918, within ~1 m of EPSG:32618 here
        if b.left < x1 and b.right > x0 and b.bottom < y1 and b.top > y0:
            out = np.fmin(out, warp(p, tr, w, h, src_nodata=EAARL_FILL))
    return out


def spot_check(path: Path, bed: np.ndarray, tr, ins: np.ndarray, n=200, seed=0):
    """The rotated-raster trap (CLAUDE.md §5): compare the warped bed with
    ``rasterio.sample`` (the inverse affine) at random pixel centres inside the polygons."""
    rr, cc = np.nonzero(ins)
    i = np.random.default_rng(seed).choice(rr.size, min(n, rr.size), replace=False)
    xs, ys = rasterio.transform.xy(tr, rr[i], cc[i])
    with rasterio.open(path) as src:
        s = np.array([v[0] for v in src.sample(zip(xs, ys))], dtype="float32")
    w = bed[rr[i], cc[i]]
    ok = np.isclose(s, w, atol=1e-4) | (np.isnan(s) & np.isnan(w))
    if ok.mean() < 0.9:  # nearest picks can differ on a pixel edge, never wholesale
        raise SystemExit(
            f"merged-bed warp disagrees with rasterio.sample: {ok.mean():.2f}"
        )
    return float(ok.mean())


def write_tif(path: Path, a: np.ndarray, tr) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.tif")
    with rasterio.open(
        tmp,
        "w",
        driver="GTiff",
        width=a.shape[1],
        height=a.shape[0],
        count=1,
        dtype="float32",
        crs=f"EPSG:{EPSG}",
        transform=tr,
        nodata=-9999.0,
        compress="deflate",
    ) as dst:
        dst.write(np.where(np.isfinite(a), a, -9999.0).astype("float32"), 1)
    os.replace(tmp, path)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--polygons", type=Path, default=DEF_POLYS)
    ap.add_argument(
        "--wreck",
        type=float,
        action="append",
        help="Wreck channel elevation, m NAVD88 (repeat; default 0.0 and 1.65)",
    )
    ap.add_argument("--merged", type=Path, default=DEF_MERGED)
    ap.add_argument("--lake-fix", type=Path, default=DEF_LAKE_FIX)
    ap.add_argument("--post", type=Path, default=DEF_POST)
    ap.add_argument("--usace", type=Path, default=DEF_USACE)
    a = ap.parse_args(argv)
    wreck_values = a.wreck or list(DEF_WRECK_VALUES)

    polys = load_polygons(a.polygons)
    fwd = Transformer.from_crs(4326, EPSG, always_xy=True).transform
    utm = {k: shp_transform(fwd, p) for k, p in polys.items()}
    x0 = min(p.bounds[0] for p in utm.values())
    y0 = min(p.bounds[1] for p in utm.values())
    x1 = max(p.bounds[2] for p in utm.values())
    y1 = max(p.bounds[3] for p in utm.values())
    x0, y0 = np.floor(x0 / RES) * RES - PAD, np.floor(y0 / RES) * RES - PAD
    x1, y1 = np.ceil(x1 / RES) * RES + PAD, np.ceil(y1 / RES) * RES + PAD
    w, h = int(round((x1 - x0) / RES)), int(round((y1 - y0) / RES))
    tr = from_origin(x0, y1, RES, RES)
    masks = {
        k: ~geometry_mask([p], out_shape=(h, w), transform=tr) for k, p in utm.items()
    }
    any_in = np.logical_or.reduce(list(masks.values()))

    bed = warp(a.merged, tr, w, h)
    agree = spot_check(a.merged, bed, tr, any_in)
    lake = warp(a.lake_fix, tr, w, h) if a.lake_fix.is_file() else None
    bed_lk = bed if lake is None else np.fmin(bed, lake)  # the 10-17 recipe's bed
    post = post_mosaic(a.post, tr, w, h)
    usace = warp(a.usace, tr, w, h)
    px = RES**2
    overlays = []

    for wv in wreck_values:
        key = f"breach_v4_wreck{variant_tag(wv)}"
        ov = paint((h, w), masks, wv, post)
        overlays.append(ov)
        rows = []
        for k, m in masks.items():
            r = dict(
                polygon=k,
                vertices=len(polys[k].exterior.coords) - 1,
                area_m2=round(utm[k].area),
                pixels_m2=float(m.sum() * px),
                source="stated" if k in WRECK else "eaarl_post",
                overlay_nodata_m2=float((m & ~np.isfinite(ov)).sum() * px),
                overlay=stats(ov[m]),
                bed=stats(bed[m]),
                vs_bed=lowering(ov, bed, m, px),
            )
            if lake is not None:
                r["vs_bed_lake_fix"] = lowering(ov, bed_lk, m, px)
            if k in MANTO:
                hole = m & ~np.isfinite(post)
                both = m & np.isfinite(post) & np.isfinite(usace)
                r["usace2012"] = dict(
                    valid_frac=round(float(np.isfinite(usace[m]).mean()), 3),
                    stats=stats(usace[m]),
                    eaarl_minus_usace_p50=_q((post - usace)[both], np.median),
                    in_eaarl_holes=stats(usace[hole]),
                )
                r["bed_in_eaarl_holes"] = stats(bed[hole])
            rows.append(r)
        out = a.out_dir / f"{key}.tif"
        write_tif(out, ov, tr)
        meta = dict(
            key=key,
            polygons=str(a.polygons),
            merged=str(a.merged),
            lake_fix=str(a.lake_fix) if lake is not None else None,
            post=str(a.post),
            usace2012=str(a.usace),
            wreck_value_m_navd88=wv,
            grid=dict(epsg=EPSG, res=RES, width=w, height=h, origin=[x0, y1]),
            merged_warp_vs_sample_agree=round(agree, 3),
            rule=(
                f"wreck_a = {wv} m NAVD88 (stated); manto_a/b = USGS DS767 EAARL-B "
                "post-Sandy first surface (2012-11-01/05, NAVD88 GEOID12A, m); NoData "
                "elsewhere; paint with rebuild_subgrid.py --overlay <key>:min"
            ),
            polygons_report=rows,
        )
        out.with_suffix(".json").write_text(json.dumps(meta, indent=1) + "\n")
        print(f"== {key}: wrote {out} ({w} x {h} at {RES:.0f} m)")
        for r in rows:
            v, o = r["vs_bed"], r["overlay"]
            print(
                f"  {r['polygon']:8s} area {r['area_m2']:7,d} m2  overlay "
                f"min/p50/max {o['min']}/{o['p50']}/{o['max']}  nodata "
                f"{r['overlay_nodata_m2']:.0f} m2  lowered {v['lowered_m2']:.0f} m2 "
                f"(already lower {v['already_lower_m2']:.0f})  drop mean/p50/max "
                f"{v['drop_mean']}/{v['drop_p50']}/{v['drop_max']}  "
                f"vol {v['volume_removed_m3']} m3"
            )

    union = lowered_union(overlays, bed_lk)
    man = np.where(union, np.float32(CHANNEL_N), np.float32(np.nan))
    out = a.out_dir / "breach_v4_manning.tif"
    write_tif(out, man, tr)
    rows = [
        dict(
            polygon=k,
            lowered_union_m2=float((m & union).sum() * px),
            pixels_m2=float(m.sum() * px),
        )
        for k, m in masks.items()
    ]
    meta = dict(
        key="breach_v4_manning",
        manning_n=CHANNEL_N,
        unit="s m-1/3",
        mask=(
            "union over the variants "
            + ", ".join(f"breach_v4_wreck{variant_tag(v)}" for v in wreck_values)
            + " of pixels where the overlay is valid and below the bed (or the bed "
            "has no value) — the pixels --overlay <key>:min changes"
        ),
        bed=(
            "min(merged, lake_fix_v4) (the 10-17 recipe's bed)"
            if lake is not None
            else "merged only (lake_fix_v4 not found)"
        ),
        merged=str(a.merged),
        lake_fix=str(a.lake_fix) if lake is not None else None,
        polygons=str(a.polygons),
        grid=dict(epsg=EPSG, res=RES, width=w, height=h, origin=[x0, y1]),
        rule="paint with rebuild_subgrid.py --manning-overlay after manning_water_v4",
        polygons_report=rows,
    )
    out.with_suffix(".json").write_text(json.dumps(meta, indent=1) + "\n")
    print(f"== breach_v4_manning: wrote {out} (n {CHANNEL_N})")
    for r in rows:
        print(
            f"  {r['polygon']:8s} lowered-union {r['lowered_union_m2']:.0f} m2 "
            f"of {r['pixels_m2']:.0f} m2"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
