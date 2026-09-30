#!/usr/bin/env python
"""v4 inland water: CUDEM's 0 m fill under non-tidal water, and land roughness in channels.

    python scripts/build_inland_water_v4.py fetch       # network: NHD polygons
    python scripts/build_inland_water_v4.py depths      # network: USGS channel measurements
    python scripts/build_inland_water_v4.py inventory   # per-polygon stats + pit points
    python scripts/build_inland_water_v4.py review      # the list for the user (no network)

WHY (STATUS 2026-09-29 EVENING, B + C).
  * CUDEM (and CoNED — checked 09-29, same fill) holds NON-TIDAL water as a flat ~0 m
    NAVD88 fill, not a bed: Union Lake reads -0.2 m under a 7.56 m lake surface, the
    Fairmount pool 0.00 under 3.2 m, the Delaware above the Trenton falls 0.0 under
    0.9-4.8 m. The model starts every such pit EMPTY (the initial level fills only
    sea-connected cells) and spends the storm filling it: Union Lake reached 0.75 m by
    10-31 and swallowed the Maurice.
  * NLCD 30 m puts narrow channels in developed classes (n 0.10-0.13). Above a uv
    point's ``uv_zmax`` SFINCS uses the box-MEAN Manning, so a flooded pool behaves like
    a street: the Schuylkill backs up to 7-10 m through Philadelphia.

THE RULE (user, 2026-09-29):
  * LAKE (NHD Waterbody, LakePond / Reservoir): bed = the lidar water surface (zero
    depth). The lake then acts as if it starts full at its normal pool — the only storage
    a flood uses is above that pool — and needs no depth number.
  * RIVER (NHD Area, StreamRiver / CanalDitch / Rapids — dammed pools included, e.g.
    Fairmount): bed = lidar surface − the river's gauge-measured mean depth (area /
    width of the USGS channel measurements at flows p25-p75: the Trenton method, 1.20 m).
    A river must CONVEY, and a thin channel refills in hours.
  * ROUGHNESS: n = 0.02 (NLCD open water) on every polygon above, painted over the NLCD
    reclass — for all of them, flagged or not.
  * Only where the MODEL'S bed is a fake pit is the bed repainted: the polygon's lidar
    surface is ≥ ``SURFACE_MIN`` (non-tidal) and the model bed sits near sea level under
    it (``inventory`` shows both, per water body, for review — edit ``OVERRIDES``).
Datum m NAVD88. Outputs under data/elevation_v4/inland_water/.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "data" / "elevation_v4" / "inland_water"
NHD = "https://hydro.nationalmap.gov/arcgis/rest/services/nhd/MapServer"
USGS = "https://api.waterdata.usgs.gov/ogcapi/v0/collections"

#: (layer, kind, FTYPEs). Area: 460 StreamRiver, 336 CanalDitch, 431 Rapids (the
#: Trenton falls). Waterbody: 390 LakePond, 436 Reservoir. NOT 466 SwampMarsh (n 0.02
#: would be wrong on a marsh), 493 Estuary, 445 SeaOcean, 312 BayInlet (tidal: CUDEM's
#: bed is real there).
LAYERS = (
    (9, "river", (460, 336, 431)),
    (12, "lake", (390, 436)),
)
TILE_DEG = 0.25


def _get(url: str, tries: int = 5, timeout: int = 180) -> bytes:
    for k in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            if k == tries - 1:
                raise
            print(f"    retry {k + 1} ({e})", flush=True)
            time.sleep(5 * (k + 1))
    raise RuntimeError("unreachable")


def _atomic_write(path: Path, write) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=path.suffix)
    os.close(fd)
    try:
        write(tmp)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


# ── fetch ─────────────────────────────────────────────────────────────────────
def _nhd_tile(layer: int, ftypes, box) -> list[dict]:
    feats, off = [], 0
    while True:
        q = {
            "where": f"ftype IN ({','.join(map(str, ftypes))})",
            "geometry": ",".join(f"{v:.4f}" for v in box),
            "geometryType": "esriGeometryEnvelope",
            "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "permanent_identifier,gnis_name,ftype,areasqkm",
            "outSR": 4326,
            "f": "geojson",
            "resultOffset": off,
            "resultRecordCount": 1000,
            "orderByFields": "objectid",
        }
        d = json.loads(_get(f"{NHD}/{layer}/query?" + urllib.parse.urlencode(q)))
        got = d.get("features", [])
        feats += got
        if not got or not d.get("properties", {}).get("exceededTransferLimit", False):
            if len(got) < 1000:
                break
        off += len(got)
    return feats


def fetch() -> None:
    import geopandas as gpd
    import pandas as pd
    import shapely

    from nj_sfincs import domain as _domain

    ring = gpd.read_file(_domain.DOMAINS["v4"].region).to_crs(4326)
    shape = ring.union_all()
    x0, y0, x1, y1 = ring.total_bounds
    for layer, kind, ftypes in LAYERS:
        out = OUT / f"nhd_{kind}_v4.gpkg"
        if out.exists():
            print(f"{out.name} exists — delete it to re-fetch")
            continue
        feats = []
        xs = np.arange(x0, x1, TILE_DEG)
        ys = np.arange(y0, y1, TILE_DEG)
        for tx in xs:
            for ty in ys:
                box = (tx, ty, min(tx + TILE_DEG, x1), min(ty + TILE_DEG, y1))
                if not shapely.box(*box).intersects(shape):
                    continue
                # per-tile cache: the service 504s under load, so a re-run resumes
                c = OUT / "cache" / f"nhd{layer}_{tx:.2f}_{ty:.2f}.json"
                if not c.exists():
                    t = _nhd_tile(layer, ftypes, box)
                    _atomic_write(c, lambda p, t=t: Path(p).write_text(json.dumps(t)))
                feats += json.loads(c.read_text())
        g = gpd.GeoDataFrame.from_features(feats, crs=4326)
        g.columns = [c.lower() if c != "geometry" else c for c in g.columns]
        g = g.drop_duplicates("permanent_identifier")
        g = g[g.intersects(shape)]
        g["kind"] = kind
        _atomic_write(out, lambda p, g=g: g.to_file(p, driver="GPKG", layer="nhd"))
        n = pd.Series(g["ftype"]).value_counts().to_dict()
        print(f"{out.name}: {len(g)} polygons in the ring, by ftype {n}", flush=True)


# ── gauge depths ──────────────────────────────────────────────────────────────
def gauge_mean_depth(site: str, lo: float = 25, hi: float = 75) -> dict:
    """Median mean depth (channel_area / channel_width) of the USGS channel measurements
    at ``site`` whose flow lies in the site's own p``lo``-p``hi`` measured-flow band —
    the method behind the Trenton 1.20 m (STATUS 09-27, 296 measurements)."""
    rows, url = [], (
        f"{USGS}/channel-measurements/items?"
        + urllib.parse.urlencode(
            {"monitoring_location_id": f"USGS-{site}", "limit": 1000, "f": "json"}
        )
    )
    while url:
        d = json.loads(_get(url))
        rows += [f["properties"] for f in d.get("features", [])]
        url = next((lk["href"] for lk in d.get("links", []) if lk.get("rel") == "next"),
                   None)
    q, w, a = [], [], []
    for p in rows:
        try:
            qq, ww, aa = (float(p["channel_flow"]), float(p["channel_width"]),
                          float(p["channel_area"]))
        except (TypeError, ValueError):
            continue
        if ww > 0 and aa > 0 and qq > 0:
            q.append(qq), w.append(ww), a.append(aa)
    q, w, a = map(np.asarray, (q, w, a))
    if q.size == 0:
        return {"site": site, "n_all": len(rows), "n_band": 0}
    band = (q >= np.percentile(q, lo)) & (q <= np.percentile(q, hi))
    dep = a[band] / w[band] * 0.3048
    return {
        "site": site,
        "n_all": int(q.size),
        "n_band": int(band.sum()),
        "depth_m": round(float(np.median(dep)), 2),
        "depth_p10_m": round(float(np.percentile(dep, 10)), 2),
        "depth_p90_m": round(float(np.percentile(dep, 90)), 2),
        "width_m": round(float(np.median(w[band])) * 0.3048, 1),
        "flow_band_cms": [round(float(np.percentile(q, lo)) * 0.0283168, 1),
                          round(float(np.percentile(q, hi)) * 0.0283168, 1)],
    }


# ── inventory ─────────────────────────────────────────────────────────────────
#: Non-tidal: the lidar water surface (median over the polygon) is at least this high.
#: Lidar flown at high tide puts TIDAL water at 1.6-2.5 m in places (the 09-29 scan), so
#: a flag between 1.5 and ~2.5 m wants a look before it is believed.
SURFACE_MIN = 1.5
#: A fake pit: the model's bed (median) is near sea level AND this far below the surface.
PIT_BED_MAX = 1.0
PIT_DROP_MIN = 1.0
SAMPLE_M = 15.0  # point spacing inside a polygon
MAX_PTS = 4000


def _sample_points(geom, step=SAMPLE_M, cap=MAX_PTS):
    import shapely

    x0, y0, x1, y1 = geom.bounds
    s = step
    while ((x1 - x0) / s) * ((y1 - y0) / s) > cap * 4:
        s *= 1.5
    xs, ys = np.meshgrid(np.arange(x0 + s / 2, x1, s), np.arange(y0 + s / 2, y1, s))
    xs, ys = xs.ravel(), ys.ravel()
    ok = shapely.contains_xy(geom, xs, ys)
    xs, ys = xs[ok], ys[ok]
    if xs.size == 0:
        c = geom.representative_point()
        xs, ys = np.array([c.x]), np.array([c.y])
    if xs.size > cap:
        k = np.random.default_rng(0).choice(xs.size, cap, replace=False)
        xs, ys = xs[k], ys[k]
    return xs, ys


def _sampler(path):
    import rasterio
    from rasterio.warp import transform

    r = rasterio.open(path)

    def f(x, y, crs="EPSG:32618"):
        if str(r.crs) != crs:
            x, y = transform(crs, r.crs, list(x), list(y))
        v = np.array([p[0] for p in r.sample(zip(x, y))], dtype=float)
        if r.nodata is not None:
            v[np.isclose(v, r.nodata)] = np.nan
        v[~np.isfinite(v) | (v < -1e4)] = np.nan
        return v

    return f


def inventory() -> None:
    import geopandas as gpd
    import pandas as pd
    import xarray as xr
    import yaml
    from scipy.spatial import cKDTree

    from nj_sfincs import domain as _domain

    dom = _domain.DOMAINS["v4"]
    fm = dom.frozen_mesh_dir()
    g = xr.open_dataset(fm / "sfincs.nc")
    fx, fy = g["mesh2d_face_x"].values, g["mesh2d_face_y"].values
    half = np.round(float(g.attrs["dx"]) / 2.0 ** (g["level"].values - 1)) / 2
    act = g["mask"].values > 0
    tree = cKDTree(np.c_[fx, fy])

    cat = yaml.safe_load(open(ROOT / "data" / "data_catalog.yml"))
    bed = _sampler(fm / "subgrid" / "dep_subgrid_lev1.tif")
    nj10 = _sampler(ROOT / "data" / cat["nj_10ft_dem_v4"]["uri"])
    dep3 = _sampler(ROOT / "data" / cat["dep3_v4"]["uri"])
    man = _sampler(fm / "subgrid" / "manning_subgrid_lev1.tif")

    polys = pd.concat(
        [gpd.read_file(OUT / f"nhd_{k}_v4.gpkg") for _, k, _ in LAYERS]
    ).to_crs(32618)
    rows, pts = [], []
    for i, p in enumerate(polys.itertuples()):
        xs, ys = _sample_points(p.geometry)
        d, j = tree.query(np.c_[xs, ys])
        inside = act[j] & (np.abs(fx[j] - xs) <= half[j] + 0.5) & (
            np.abs(fy[j] - ys) <= half[j] + 0.5
        )
        if not inside.any():
            continue
        xs, ys = xs[inside], ys[inside]
        s = nj10(xs, ys)
        s = np.where(np.isfinite(s), s, dep3(xs, ys))
        b, n = bed(xs, ys), man(xs, ys)
        pit = (b <= PIT_BED_MAX) & (s - b >= PIT_DROP_MIN) & (s >= SURFACE_MIN)
        rows.append({
            "permanent_identifier": p.permanent_identifier,
            "kind": p.kind,
            "name": p.gnis_name or "",
            "ftype": int(p.ftype),
            "km2_in_model": round(p.geometry.area / 1e6 * inside.mean(), 4),
            "surface_p50": round(float(np.nanmedian(s)), 2) if np.isfinite(s).any() else np.nan,
            "bed_p50": round(float(np.nanmedian(b)), 2) if np.isfinite(b).any() else np.nan,
            "pit_frac": round(float(pit.mean()), 3),
            "n_p50": round(float(np.nanmedian(n)), 3) if np.isfinite(n).any() else np.nan,
            "n_ge_0.07_frac": round(float(np.nanmean(n >= 0.07)), 3),
            "x_utm": round(float(p.geometry.representative_point().x)),
            "y_utm": round(float(p.geometry.representative_point().y)),
        })
        if pit.any():
            pts.append(pd.DataFrame({
                "permanent_identifier": p.permanent_identifier, "kind": p.kind,
                "x": xs[pit].round(1), "y": ys[pit].round(1),
                "surface": s[pit].round(2), "bed": b[pit].round(2),
            }))
        if i % 500 == 0:
            print(f"  {i}/{len(polys)}", flush=True)
    df = pd.DataFrame(rows)
    df["flag_pit"] = (df.surface_p50 >= SURFACE_MIN) & (df.pit_frac >= 0.25)
    out = OUT / "inventory_polygons_v4.csv"
    _atomic_write(out, lambda p: df.to_csv(p, index=False))
    pp = pd.concat(pts) if pts else pd.DataFrame()
    _atomic_write(OUT / "pit_points_v4.csv", lambda p: pp.to_csv(p, index=False))
    print(f"pit_points_v4.csv: {len(pp)} sample points ({SAMPLE_M:.0f} m grid) on fake pits")
    print(f"{out.name}: {len(df)} polygons on active model cells, "
          f"{int(df.flag_pit.sum())} flagged as fake pits "
          f"({df.loc[df.flag_pit, 'km2_in_model'].sum():.2f} km2)")


# ── review list ───────────────────────────────────────────────────────────────
SITES = OUT / "cache" / "usgs_stream_sites_v4bbox.json"  # monitoring-locations, ST
CLUSTER_M = 300.0  # river pit points closer than this are one stretch (big
#: polygons are sampled coarser than SAMPLE_M, up to ~5x — see _sample_points)
GAUGE_KM = 8.0


def _clusters(x, y, link=CLUSTER_M):
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    from scipy.spatial import cKDTree

    pr = cKDTree(np.c_[x, y]).query_pairs(link, output_type="ndarray")
    n = len(x)
    a = coo_matrix((np.ones(len(pr)), (pr[:, 0], pr[:, 1])), shape=(n, n))
    return connected_components(a, directed=False)[1]


def review() -> None:
    import pandas as pd
    from pyproj import Transformer

    inv = pd.read_csv(OUT / "inventory_polygons_v4.csv")
    pts = pd.read_csv(OUT / "pit_points_v4.csv")
    tr = Transformer.from_crs(32618, 4326, always_xy=True)

    lakes = inv[(inv.kind == "lake") & inv.flag_pit].copy()
    lakes["rule"] = "lake: bed = surface"
    lakes["name"] = lakes["name"].fillna("(unnamed)")

    sites = json.loads(SITES.read_text())["features"]
    s_lon = np.array([f["geometry"]["coordinates"][0] for f in sites])
    s_lat = np.array([f["geometry"]["coordinates"][1] for f in sites])
    s_x, s_y = Transformer.from_crs(4326, 32618, always_xy=True).transform(s_lon, s_lat)
    s_no = [f["properties"]["monitoring_location_number"] for f in sites]
    s_nm = [f["properties"]["monitoring_location_name"] for f in sites]
    s_da = [f["properties"].get("drainage_area") for f in sites]

    rv = pts[pts.kind == "river"].reset_index(drop=True)
    # each point carries its polygon's pit area / its polygon's pit-point count
    w = inv.set_index("permanent_identifier")
    pit_km2 = (w.km2_in_model * w.pit_frac).reindex(rv.permanent_identifier).values
    rv["km2"] = pit_km2 / rv.groupby("permanent_identifier").x.transform("size").values
    rv["c"] = _clusters(rv.x.values, rv.y.values)
    rows = []
    for c, g in rv.groupby("c"):
        km2 = g.km2.sum()
        if km2 < 0.01:  # a bank sliver, not a stretch
            continue
        cx, cy = g.x.median(), g.y.median()
        d = np.hypot(s_x - cx, s_y - cy) / 1e3
        near = [i for i in np.argsort(d)[:6] if d[i] <= GAUGE_KM]
        lon, lat = tr.transform(cx, cy)
        rows.append({
            "stretch": int(c), "km2": round(km2, 3),
            "lon": round(lon, 4), "lat": round(lat, 4),
            "surface_min": round(g.surface.min(), 2), "surface_max": round(g.surface.max(), 2),
            "bed_p50": round(g.bed.median(), 2),
            "gauges_nearby": "; ".join(
                f"{s_no[i]} {s_nm[i]} ({d[i]:.1f} km, DA {s_da[i]})" for i in near
            ),
        })
    rivers = pd.DataFrame(rows).sort_values("km2", ascending=False)
    OUT.mkdir(parents=True, exist_ok=True)
    _atomic_write(OUT / "review_lakes_v4.csv", lambda p: lakes.to_csv(p, index=False))
    _atomic_write(OUT / "review_river_stretches_v4.csv",
                  lambda p: rivers.to_csv(p, index=False))
    print(f"lakes flagged: {len(lakes)} ({lakes.km2_in_model.sum():.2f} km2); "
          f"river stretches: {len(rivers)} ({rivers.km2.sum():.2f} km2)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("step", choices=("fetch", "depths", "inventory", "review"))
    ap.add_argument("--site", action="append", default=[],
                    help="depths: USGS site number(s) to measure")
    a = ap.parse_args()
    if a.step == "fetch":
        fetch()
    elif a.step == "depths":
        for s in a.site:
            print(json.dumps(gauge_mean_depth(s)), flush=True)
    elif a.step == "inventory":
        inventory()
    else:
        review()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
