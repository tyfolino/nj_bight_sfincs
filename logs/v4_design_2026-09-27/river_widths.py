#!/usr/bin/env python
"""River channel widths inside v4's landward ring, vs the refinement recipe's cell sizes.

van Ormondt et al. 2025 (GMD 18:843): grid spacing must not exceed channel width; past it
the meander flux error grows ~ sinuosity^1.5. So: for every NAMED river NHD maps as an
area (StreamRiver, ftype 460), sample its centreline (ArtificialPath, ftype 558) every
50 m and take width = 2 x distance to the bank (the inscribed circle at the centreline),
then summarise per river. Sinuosity = path length / straight distance over 2 km windows.

    PYTHONPATH=$PWD python logs/v4_design_2026-09-27/river_widths.py fetch
    PYTHONPATH=$PWD python logs/v4_design_2026-09-27/river_widths.py report

Fetch caches NHD tiles under data/v4_design/nhd_rivers/ (gitignored data dir).
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from nj_sfincs import domain as D

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "v4_design" / "nhd_rivers"
NHD = "https://hydro.nationalmap.gov/arcgis/rest/services/nhd/MapServer"
CRS = 32618
STEP = 50.0
TILE = 0.2  # degrees


def _get(url: str, tries: int = 5) -> dict:
    for k in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=180) as r:
                return json.loads(r.read())
        except Exception as e:  # noqa: BLE001
            if k == tries - 1:
                raise
            print(f"    retry {k + 1} ({e})")


def _query(layer: int, where: str, box) -> list:
    feats, off = [], 0
    while True:
        q = {
            "where": where,
            "geometry": ",".join(f"{v:.4f}" for v in box),
            "geometryType": "esriGeometryEnvelope",
            "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "gnis_name,ftype",
            "outSR": 4326,
            "f": "geojson",
            "resultOffset": off,
            "resultRecordCount": 1000,
        }
        js = _get(f"{NHD}/{layer}/query?" + urllib.parse.urlencode(q))
        got = js.get("features", [])
        feats += got
        if len(got) < 1000:
            return feats
        off += len(got)


def landward() -> shapely.Geometry:
    v4 = D.DOMAINS["v4"]
    ring = gpd.read_file(v4.region).to_crs(4326).geometry.iloc[0]
    return ring.difference(shapely.Polygon(D.sea_polygon(v4)[1]))


def fetch() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    land = landward()
    x0, y0, x1, y1 = land.bounds
    for lo in np.arange(x0, x1, TILE):
        for la in np.arange(y0, y1, TILE):
            box = (lo, la, lo + TILE, la + TILE)
            if not land.intersects(shapely.box(*box)):
                continue
            tag = f"{lo:+.2f}_{la:+.2f}"
            for kind, layer, where in (
                ("area", 9, "ftype=460"),
                ("path", 6, "ftype=558 AND gnis_name IS NOT NULL"),
            ):
                f = CACHE / f"{kind}_{tag}.geojson"
                if f.exists():
                    continue
                feats = _query(layer, where, box)
                tmp = f.with_suffix(".tmp")
                tmp.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
                tmp.replace(f)
                print(f"{kind} {tag}: {len(feats)}")


def _read(kind: str) -> gpd.GeoDataFrame:
    parts = [gpd.read_file(f) for f in sorted(CACHE.glob(f"{kind}_*.geojson"))]
    parts = [p for p in parts if len(p)]
    g = pd.concat(parts, ignore_index=True).set_crs(4326, allow_override=True)
    return g.to_crs(CRS)


def report() -> None:
    land = gpd.GeoSeries([landward()], crs=4326).to_crs(CRS).iloc[0]
    area = _read("area")
    water = shapely.union_all(area.geometry.make_valid().values).intersection(land)
    bank = water.boundary
    path = _read("path")
    path = path[path.intersects(land)]
    rows = []
    for name, g in path.groupby("gnis_name"):
        ln = shapely.line_merge(shapely.union_all(g.geometry.values)).intersection(land)
        segs = list(getattr(ln, "geoms", [ln]))
        w_all, sin_all, L = [], [], 0.0
        for s in segs:
            if s.length < STEP:
                continue
            L += s.length
            d = np.arange(0, s.length, STEP)
            p = shapely.line_interpolate_point(s, d)
            inside = shapely.contains(water, p)
            w = 2 * shapely.distance(bank, p)
            w_all.append(np.where(inside, w, np.nan))
            # sinuosity over 2 km windows
            for a in np.arange(0, s.length - 2000, 1000):
                pa, pb = s.interpolate(a), s.interpolate(a + 2000)
                sin_all.append(2000 / max(pa.distance(pb), 1.0))
        if not w_all or L < 2000:
            continue
        w = np.concatenate(w_all)
        w = w[np.isfinite(w)]
        if len(w) < 20:
            continue
        rows.append(
            dict(
                river=name,
                km=round(L / 1e3, 1),
                w_p10=round(np.percentile(w, 10)),
                w_p50=round(np.percentile(w, 50)),
                w_p90=round(np.percentile(w, 90)),
                km_lt50=round((w < 50).sum() * STEP / 1e3, 1),
                km_lt25=round((w < 25).sum() * STEP / 1e3, 1),
                sinuosity_p50=round(float(np.median(sin_all)), 2) if sin_all else np.nan,
                sinuosity_p90=round(float(np.percentile(sin_all, 90)), 2)
                if sin_all
                else np.nan,
            )
        )
    t = pd.DataFrame(rows).sort_values("km_lt50", ascending=False)
    out = ROOT / "data" / "v4_design" / "river_widths_v4.csv"
    t.to_csv(out, index=False)
    with pd.option_context("display.width", 200, "display.max_rows", 200):
        print(t.to_string(index=False))
    print(
        f"\n{len(t)} named rivers; centreline narrower than 50 m: {t.km_lt50.sum():.0f} km "
        f"(< 25 m: {t.km_lt25.sum():.0f} km) of {t.km.sum():.0f} km. Wrote {out}"
    )


if __name__ == "__main__":
    {"fetch": fetch, "report": report}[sys.argv[1]]()
