#!/usr/bin/env python
"""The 2012-bed PILE-PIER carve for nj2 (user 2026-11-14: pile-supported piers are CARVED open).

    python -I logs/nj2_freeze_2026-11-14/build_piers_2012.py      (repo root, sfincs env, PROJ_DATA set)

Units — the SAME rule as the 2026 bed (logs/nj2_bed2026_2026-11-14/build_pier_carves.py; coordinator
11-14: both beds share one classification): `logs/v2_piers_2026-11-06/piers.gpkg` rows with
`carve_2012` True (PILE class whose 2012 bed reads as a deck, p50 > MHHW + 0.5 = 1.2 m) unless the
user's 11-12 eye check (picker/user_decisions_2026-11-12.csv) called them `fill`, PLUS the eye check's
`pile` units that have a deck in the 2012 bed (`deck_in_bed_2012`). Solid-fill piers stay solid.
(First build 11-14 used `carve_2012` alone: 22 units.)

Depth rule (the 11-06 README's "carve to the bed under it"; no source sees under a deck): each
unit's value = the MEDIAN of the 2012 bed's WATER pixels (< -0.5 m) in a ring 5-40 m outside the
unit, minus nothing; the 2012 bed here = HD_HUD 2012 where it has data, else CUDEM 1/9"
(cudem_nj_v3), i.e. the tiers the 2012 subgrid reads at these places. A unit with < 20 such
pixels is SKIPPED and listed (no evidence of the water beside it). Written on a 5 m UTM 18N
grid (the carve rasters' convention), NoData elsewhere; apply as `piers_v2_2012:min` (lower only).
Outputs: /scratch/tpj8/nj_bight_sfincs_data/v2/carves/piers_v2_2012.tif (+ .csv per unit).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

ROOT = Path.cwd()
OUT = Path("/scratch/tpj8/nj_bight_sfincs_data/v2/carves/piers_v2_2012.tif")
RES = 5.0
NODATA = -9999.0


def main() -> int:
    import geopandas as gpd
    import rasterio
    from rasterio.features import rasterize
    from rasterio.transform import from_origin
    from rasterio.warp import Resampling, reproject

    import pandas as pd

    g = gpd.read_file(ROOT / "logs/v2_piers_2026-11-06/piers.gpkg")
    dec = pd.read_csv(ROOT / "logs/v2_piers_2026-11-06/picker/user_decisions_2026-11-12.csv")
    g["user"] = g.osm_id.map(dec.set_index("osm_id").decision).fillna("")
    rule = g["carve_2012"].astype(bool) & (g.user != "fill")
    eye = g["deck_in_bed_2012"].astype(bool) & (g.user == "pile") & ~g["carve_2012"].astype(bool)
    print(f"carve_2012 {int(g.carve_2012.astype(bool).sum())}; of those user fill "
          f"{int((g.carve_2012.astype(bool) & (g.user == 'fill')).sum())}; added by the eye check {int(eye.sum())}")
    g["why"] = np.where(rule, "carve_2012 (PILE + deck)", "user eye check: pile + deck")
    g = g[rule | eye].to_crs(32618).reset_index(drop=True)
    print(f"{len(g)} carve_2012 units, {g.area.sum() / 1e4:.1f} ha")
    x0, y0, x1, y1 = g.buffer(60).total_bounds
    x0, y0 = np.floor(x0 / 100) * 100, np.floor(y0 / 100) * 100
    x1, y1 = np.ceil(x1 / 100) * 100, np.ceil(y1 / 100) * 100
    W, H = int((x1 - x0) / RES), int((y1 - y0) / RES)
    tf = from_origin(x0, y1, RES, RES)

    def warp(path):
        dst = np.full((H, W), np.nan, "f4")
        with rasterio.open(path) as s:
            reproject(
                rasterio.band(s, 1), dst, dst_transform=tf, dst_crs="EPSG:32618",
                dst_nodata=np.nan, resampling=Resampling.bilinear,
            )
        return dst

    cudem = warp(ROOT / "data/elevation_v3/cudem_nj_v3.vrt")
    hud = warp(ROOT / "data/elevation_nj2/v2/ehydro_hud_2012/hd_hud_2012_5m.tif")
    bed = np.where(np.isfinite(hud) & (hud > -1000), hud, cudem)
    bed[bed < -1000] = np.nan

    out = np.full((H, W), NODATA, "f4")
    rows = []
    for i, r in g.iterrows():
        unit = rasterize([(r.geometry, 1)], (H, W), transform=tf, fill=0).astype(bool)
        ring_geom = r.geometry.buffer(40).difference(r.geometry.buffer(5))
        ring = rasterize([(ring_geom, 1)], (H, W), transform=tf, fill=0).astype(bool)
        water = ring & np.isfinite(bed) & (bed < -0.5)
        nwat = int(water.sum())
        under = bed[unit & np.isfinite(bed)]
        p50_under = float(np.median(under)) if under.size else np.nan
        if nwat < 20:
            target = np.nan
        else:
            target = float(np.median(bed[water]))
            out[unit] = np.minimum(np.where(out[unit] == NODATA, np.inf, out[unit]), target)
        rows.append(
            dict(osm_id=r.osm_id, name=r["name"], why=r.why, reach=r.reach, area_m2=round(r.geometry.area),
                 bed_unit_p50=round(p50_under, 2), ring_water_px=nwat,
                 target=round(target, 2) if np.isfinite(target) else None,
                 lon=r.lon, lat=r.lat)
        )
    import pandas as pd

    df = pd.DataFrame(rows)
    print(df.to_string())
    skipped = df[df.target.isna()]
    print(f"carved {len(df) - len(skipped)} units; skipped (no water beside): {skipped.osm_id.tolist()}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".tmp.tif")
    with rasterio.open(
        tmp, "w", driver="GTiff", width=W, height=H, count=1, dtype="float32", crs="EPSG:32618",
        transform=tf, nodata=NODATA, compress="deflate", tiled=True,
    ) as d:
        d.write(out, 1)
        d.update_tags(
            apply="piers_v2_2012:min (lower only)",
            units="carve_2012 (minus user fill) + user eye-check piles with a 2012 deck",
            rule="median 2012-bed water (<-0.5 m) in a 5-40 m ring; bed = HD_HUD 2012 else CUDEM 1/9",
            source="logs/nj2_freeze_2026-11-14/build_piers_2012.py",
        )
    tmp.replace(OUT)
    df.to_csv(OUT.with_suffix(".csv"), index=False)
    print(f"wrote {OUT} ({int((out != NODATA).sum())} px, {(out != NODATA).sum() * RES * RES / 1e4:.1f} ha)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
