"""The 2026-bed PILE-PIER carve for nj2 (user 2026-11-14: pile-supported piers are CARVED open; fill stays solid).

    python -I logs/nj2_bed2026_2026-11-14/build_pier_carves.py      (repo root, sfincs env, PROJ_DATA set; ~15 s)

The 2026 twin of logs/nj2_freeze_2026-11-14/build_piers_2012.py, SAME depth rule so the two beds differ only in
which units and which water bed:
  depth = per unit, the MEDIAN of the bed's WATER pixels (< -0.5 m) in a ring 5-40 m outside the unit; a unit with
          < 20 such pixels is SKIPPED and listed. 5 m UTM 18N grid, NoData elsewhere; apply piers_v2_2026:min.
  bed   = ehydro_latest_2026 (the 2026 bed's channel tier, incl. the 2023-26 HUD surveys) where it has data, else
          CUDEM 1/9" (cudem_nj_v3) — the 2026 twin of the 2012 builder's HD_HUD 2012 -> CUDEM.
  units = logs/v2_piers_2026-11-06/piers.gpkg `carve_2026` (PILE class with a deck in the 2026 bed, p50 > 1.2 m:
          53 units) PLUS the user's eye check (picker/user_decisions_2026-11-12.csv): an UNKNOWN unit the user called
          `pile` that has a deck in the 2026 bed is carved too; one called `fill` never is. Column `why` says which.
          Edgewater w538964866 / w538964867 = PILE (user 11-12): 867 carries a deck in the 2026 bed and is carved;
          866 has no 2026 bed value under it (deck_in_bed False) and is not.
Output: /scratch/tpj8/nj_bight_sfincs_data/v2/carves/piers_v2_2026.tif (+ .csv per unit); pier_carves.txt here.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

ROOT = Path.cwd()
HERE = ROOT / "logs/nj2_bed2026_2026-11-14"
OUT = Path("/scratch/tpj8/nj_bight_sfincs_data/v2/carves/piers_v2_2026.tif")
RES = 5.0
NODATA = -9999.0


def main() -> int:
    import geopandas as gpd
    import pandas as pd
    import rasterio
    from rasterio.features import rasterize
    from rasterio.transform import from_origin
    from rasterio.warp import Resampling, reproject

    log = []

    def p(s):
        print(s, flush=True)
        log.append(s)

    g = gpd.read_file(ROOT / "logs/v2_piers_2026-11-06/piers.gpkg")
    dec = pd.read_csv(ROOT / "logs/v2_piers_2026-11-06/picker/user_decisions_2026-11-12.csv")
    dec = dec.set_index("osm_id").decision
    g["user"] = g.osm_id.map(dec).fillna("")
    deck = g["deck_in_bed_2026"].astype(bool)
    rule = g["carve_2026"].astype(bool) & (g.user != "fill")
    eye = deck & (g.user == "pile") & ~g["carve_2026"].astype(bool)
    g["why"] = np.where(rule, "carve_2026 (PILE + deck)", np.where(eye, "user eye check: pile + deck", ""))
    p(f"carve_2026 units {int(g.carve_2026.astype(bool).sum())}; of those user-decided fill {int((g.carve_2026.astype(bool) & (g.user == 'fill')).sum())}; "
      f"added by the eye check {int(eye.sum())}")
    g = g[rule | eye].to_crs(32618).reset_index(drop=True)
    p(f"{len(g)} units to carve, {g.area.sum() / 1e4:.1f} ha")
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
            )  # fmt: skip
        return dst

    cudem = warp(ROOT / "data/elevation_v3/cudem_nj_v3.vrt")
    ehl = warp(ROOT / "data/elevation_modern_2026/ehydro_latest_2026.tif")
    bed = np.where(np.isfinite(ehl) & (ehl > -1000), ehl, cudem)
    bed[bed < -1000] = np.nan

    out = np.full((H, W), NODATA, "f4")
    rows = []
    for _, r in g.iterrows():
        unit = rasterize([(r.geometry, 1)], (H, W), transform=tf, fill=0).astype(bool)
        ring_geom = r.geometry.buffer(40).difference(r.geometry.buffer(5))
        ring = rasterize([(ring_geom, 1)], (H, W), transform=tf, fill=0).astype(bool)
        water = ring & np.isfinite(bed) & (bed < -0.5)
        nwat = int(water.sum())
        n_ehl = int((water & np.isfinite(ehl) & (ehl > -1000)).sum())
        if nwat < 20:
            target = np.nan
        else:
            target = float(np.median(bed[water]))
            out[unit] = np.minimum(np.where(out[unit] == NODATA, np.inf, out[unit]), target)
        rows.append(
            dict(osm_id=r.osm_id, name=r["name"], reach=r.reach, why=r.why, area_m2=round(r.geometry.area),
                 deck_p50_2026=round(float(r.bed2026_p50), 2), ring_water_px=nwat, ring_px_ehydro_latest=n_ehl,
                 target=round(target, 2) if np.isfinite(target) else None, lon=r.lon, lat=r.lat)
        )  # fmt: skip
    df = pd.DataFrame(rows)
    sk = df[df.target.isna()]
    p(f"carved {len(df) - len(sk)} units; skipped (no water beside): {len(sk)}")
    if len(sk):
        p(sk[["osm_id", "name", "reach", "area_m2", "ring_water_px"]].to_string(index=False))
    p(f"target p10/p50/p90 {np.nanpercentile(df.target.astype(float), [10, 50, 90]).round(2).tolist()} m NAVD88; "
      f"rings reading ehydro_latest_2026: {int((df.ring_px_ehydro_latest > 0).sum())} units")
    p("by reach (units): " + repr(df.groupby("reach").size().to_dict()))
    tmp = OUT.with_suffix(".tmp.tif")
    with rasterio.open(
        tmp, "w", driver="GTiff", width=W, height=H, count=1, dtype="float32", crs="EPSG:32618",
        transform=tf, nodata=NODATA, compress="deflate", tiled=True,
    ) as d:  # fmt: skip
        d.write(out, 1)
        d.update_tags(
            apply="piers_v2_2026:min (lower only)",
            rule="median 2026-bed water (<-0.5 m) in a 5-40 m ring; bed = ehydro_latest_2026 else CUDEM 1/9",
            units_rule="carve_2026 + user eye-check piles with a 2026 deck; eye-check fill never",
            source="logs/nj2_bed2026_2026-11-14/build_pier_carves.py",
        )
    tmp.replace(OUT)
    df.to_csv(OUT.with_suffix(".csv"), index=False)
    p(f"wrote {OUT} ({int((out != NODATA).sum())} px, {(out != NODATA).sum() * RES * RES / 1e4:.1f} ha)")
    (HERE / "pier_carves.txt").write_text("\n".join(log) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
