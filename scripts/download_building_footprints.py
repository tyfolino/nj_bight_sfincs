"""
Download building footprints for the ACTIVE domain from two independent sources and
write one GeoPackage per source, clipped to the domain's region bbox, plus a manifest.

Why two sources
---------------
* **NJDEP "Statewide Building Footprints derived from Impervious Surfaces of NJ"** —
  the state's own layer, extracted from LiDAR point clouds + orthoimagery by NJDEP/NJOGIS.
  Every polygon carries `project` / `year`, i.e. the LiDAR campaign it came from. On the
  coast that is mostly the 2014 post-Sandy LiDAR (`NOAA Post Sandy Topobathy`,
  `Post Sandy Supplemental`) and the 2010 `Atlantic, Ocean, Southern Monmouth` flight —
  the SAME campaigns the bed DEM is built from, so footprint and terrain vintages agree.
  ⚠️ 2014 is AFTER Sandy: houses destroyed in the storm and not rebuilt by then are
  absent, and raised/rebuilt houses have their post-storm footprint. That is a real,
  bounded caveat for a 2012 hindcast; the 2010 sub-set is pre-storm.
  Service: https://mapsdep.nj.gov/arcgis/rest/services/Features/Structures/MapServer/8
  Hub item: https://www.arcgis.com/home/item.html?id=e349222dba754b1ab77eb6fd0e8b562c
* **Microsoft US Building Footprints v2** — ML extraction from 2019–2020 imagery,
  ODbL. The source the Stevens Hoboken SFINCS study used, so it is the like-for-like
  comparison layer. Seven years after the storm and imagery-derived, so it is the
  secondary source here, kept for cross-checking coverage and as a fallback where the
  NJDEP layer is thin.
  Zip: https://minedbuildings.z5.web.core.windows.net/legacy/usbuildings-v2/NewJersey.geojson.zip
  (the old `usbuildingdata.blob.core.windows.net` host now returns 409 — do not use it.)

How the NJDEP pull works (and why it looks odd)
-----------------------------------------------
The NJDEP MapServer layer IGNORES spatial filters: an envelope query returns
``{"count": 0}`` whether the geometry is sent in EPSG:4326 or 3857, as a plain string or
JSON, by GET or POST (tested 2026-09-03). ``where objectid BETWEEN a AND b`` works, so
the whole statewide layer (~2.89 M polygons) is pulled in object-id pages of
``PAGE`` rows, in parallel, and clipped LOCALLY to the domain bbox. Geometry is
requested straight in EPSG:32618 at 1 cm precision. The full statewide pull is kept as
a FlatGeobuf under ``data/buildings/raw/`` so the next domain (v4 Delaware Bay) clips
from disk instead of re-pulling. Integrity: the number of features received must equal
the server's own ``returnCountOnly`` count, or the script fails loudly — a silently short
pull would be a silently under-built town.

Outputs (per domain, EPSG:32618, atomic writes)
-----------------------------------------------
    data/buildings/raw/NewJersey.geojson.zip                 Microsoft statewide (as shipped)
    data/buildings/raw/njdep_building_footprints_nj.fgb      NJDEP statewide (our pull)
    data/buildings_<domain>/njdep_footprints.gpkg            clipped: objectid, project, year
    data/buildings_<domain>/microsoft_footprints.gpkg        clipped: release, capture_dates_range
    data/buildings_<domain>/manifest.json                    counts, vintages, bbox, URLs, date

Usage (from the repo root, sfincs env on PATH, PYTHONPATH=$PWD):
    NJ_DOMAIN=v3 python scripts/download_building_footprints.py            # both sources
    NJ_DOMAIN=v3 python scripts/download_building_footprints.py --source njdep
    NJ_DOMAIN=v3 python scripts/download_building_footprints.py --reuse-raw # clip only
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

# Region + PROJ pinning come from the package (`nj_sfincs/__init__.py` primes pyproj and
# PROJ_DATA before geopandas/pyogrio load). Keep this import FIRST.
from nj_sfincs import domain as _domain  # noqa: E402

import geopandas as gpd  # noqa: E402
import pandas as pd  # noqa: E402
import pyogrio  # noqa: E402
import requests  # noqa: E402
from shapely.geometry import box  # noqa: E402

ROOT = Path(os.environ.get("NJ_ROOT", Path(__file__).resolve().parents[1]))
DATA = ROOT / "data"
RAW = DATA / "buildings" / "raw"
EPSG = 32618

NJDEP_LAYER = (
    "https://mapsdep.nj.gov/arcgis/rest/services/Features/Structures/MapServer/8"
)
NJDEP_FGB = RAW / "njdep_building_footprints_nj.fgb"
MS_URL = (
    "https://minedbuildings.z5.web.core.windows.net/legacy/usbuildings-v2/"
    "NewJersey.geojson.zip"
)
MS_ZIP = RAW / "NewJersey.geojson.zip"
MS_GEOJSON = RAW / "NewJersey.geojson"

PAGE = 2000  # the layer's maxRecordCount
# A little margin around the region: the subgrid DEM covers the whole grid RECTANGLE,
# and the quadtree can grow a few cells past the region ring (CLAUDE.md §5).
BUFFER_DEG = 0.02


# ── helpers ────────────────────────────────────────────────────────────────────
def atomic_write_gpkg(gdf: gpd.GeoDataFrame, out: Path, layer: str) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp.gpkg")
    if tmp.exists():
        tmp.unlink()
    gdf.to_file(tmp, layer=layer, driver="GPKG")
    os.replace(tmp, out)


def domain_bbox_utm() -> tuple[float, float, float, float]:
    """(w, s, e, n) in EPSG:32618 of the active region, padded by BUFFER_DEG."""
    w, s, e, n = _domain.active().bbox_ll(BUFFER_DEG)
    return tuple(gpd.GeoSeries([box(w, s, e, n)], crs=4326).to_crs(EPSG).total_bounds)


def clip_bbox(gdf: gpd.GeoDataFrame, b: tuple[float, float, float, float]):
    w, s, e, n = b
    return gdf.cx[w:e, s:n].copy()


# ── NJDEP ──────────────────────────────────────────────────────────────────────
def njdep_server_count(session: requests.Session) -> int:
    r = session.get(
        f"{NJDEP_LAYER}/query",
        params={"where": "1=1", "returnCountOnly": "true", "f": "json"},
        timeout=120,
    )
    r.raise_for_status()
    return int(r.json()["count"])


def njdep_oid_range(session: requests.Session) -> tuple[int, int]:
    stats = [
        {"statisticType": "min", "onStatisticField": "objectid",
         "outStatisticFieldName": "mn"},
        {"statisticType": "max", "onStatisticField": "objectid",
         "outStatisticFieldName": "mx"},
    ]
    r = session.get(
        f"{NJDEP_LAYER}/query",
        params={"where": "1=1", "outStatistics": json.dumps(stats), "f": "json"},
        timeout=120,
    )
    r.raise_for_status()
    a = r.json()["features"][0]["attributes"]
    return int(a["mn"]), int(a["mx"])


def njdep_fetch_page(lo: int, hi: int, tries: int = 5) -> list[dict]:
    """Features with lo <= objectid < hi, geometry in EPSG:32618, 1 cm precision."""
    params = {
        "where": f"objectid >= {lo} AND objectid < {hi}",
        "outFields": "objectid,project,year",
        "outSR": EPSG,
        "geometryPrecision": 2,
        "f": "geojson",
    }
    last = None
    for k in range(tries):
        try:
            r = requests.get(f"{NJDEP_LAYER}/query", params=params, timeout=180)
            r.raise_for_status()
            j = r.json()
            if "error" in j:
                raise RuntimeError(j["error"])
            if j.get("exceededTransferLimit"):
                raise RuntimeError(f"page [{lo},{hi}) exceeded transfer limit")
            return j.get("features", [])
        except Exception as exc:  # noqa: BLE001 — retried, re-raised below
            last = exc
            time.sleep(2.0 * (k + 1))
    raise RuntimeError(f"NJDEP page [{lo},{hi}) failed after {tries} tries: {last}")


def pull_njdep_statewide(workers: int) -> gpd.GeoDataFrame:
    with requests.Session() as s:
        expected = njdep_server_count(s)
        lo, hi = njdep_oid_range(s)
    starts = list(range(lo, hi + 1, PAGE))
    print(f"NJDEP: server reports {expected:,} features, objectid {lo}..{hi}, "
          f"{len(starts)} pages of {PAGE} on {workers} workers")
    frames: list[gpd.GeoDataFrame] = []
    got = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(njdep_fetch_page, a, a + PAGE): a for a in starts}
        for i, f in enumerate(as_completed(futs), 1):
            feats = f.result()  # raises on a failed page — do not swallow
            if feats:
                frames.append(gpd.GeoDataFrame.from_features(feats, crs=EPSG))
                got += len(feats)
            if i % 100 == 0 or i == len(starts):
                el = time.time() - t0
                print(f"  {i}/{len(starts)} pages, {got:,} features, {el:.0f}s",
                      flush=True)
    if got != expected:
        raise SystemExit(
            f"NJDEP pull is SHORT: received {got:,} features, server holds {expected:,}. "
            "Refusing to write a partial statewide layer."
        )
    gdf = pd.concat(frames, ignore_index=True)
    gdf = gpd.GeoDataFrame(gdf, geometry="geometry", crs=EPSG)
    return gdf[["objectid", "project", "year", "geometry"]]


def njdep(reuse_raw: bool, workers: int) -> gpd.GeoDataFrame:
    if reuse_raw and NJDEP_FGB.exists():
        print(f"NJDEP: reusing {NJDEP_FGB}")
    else:
        gdf = pull_njdep_statewide(workers)
        RAW.mkdir(parents=True, exist_ok=True)
        tmp = NJDEP_FGB.with_suffix(".tmp.fgb")
        gdf.to_file(tmp, driver="FlatGeobuf")
        os.replace(tmp, NJDEP_FGB)
        print(f"NJDEP: wrote statewide {NJDEP_FGB} ({len(gdf):,} features, "
              f"{NJDEP_FGB.stat().st_size / 1e6:.0f} MB)")
    b = domain_bbox_utm()
    # FlatGeobuf is spatially indexed, so the bbox read is cheap.
    clipped = pyogrio.read_dataframe(NJDEP_FGB, bbox=b)
    clipped = clip_bbox(clipped.set_crs(EPSG, allow_override=True), b)
    return clipped


# ── Microsoft ──────────────────────────────────────────────────────────────────
def microsoft(reuse_raw: bool) -> gpd.GeoDataFrame:
    RAW.mkdir(parents=True, exist_ok=True)
    if not (reuse_raw and MS_ZIP.exists()):
        print(f"Microsoft: downloading {MS_URL}")
        tmp = MS_ZIP.with_suffix(".zip.part")
        with requests.get(MS_URL, stream=True, timeout=900) as r:
            r.raise_for_status()
            with open(tmp, "wb") as fh:
                for chunk in r.iter_content(1 << 20):
                    fh.write(chunk)
        os.replace(tmp, MS_ZIP)
    if not MS_GEOJSON.exists():
        with zipfile.ZipFile(MS_ZIP) as z:
            z.extract(MS_GEOJSON.name, RAW)
    print(f"Microsoft: reading {MS_GEOJSON} ({MS_GEOJSON.stat().st_size / 1e6:.0f} MB) "
          "with a bbox filter — GDAL still scans the whole file, allow a few minutes")
    w, s, e, n = _domain.active().bbox_ll(BUFFER_DEG)
    gdf = pyogrio.read_dataframe(MS_GEOJSON, bbox=(w, s, e, n))
    gdf = gdf.set_crs(4326, allow_override=True).to_crs(EPSG)
    return clip_bbox(gdf, domain_bbox_utm())


# ── main ───────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--source", choices=["both", "njdep", "microsoft"], default="both")
    ap.add_argument("--reuse-raw", action="store_true",
                    help="do not re-download; clip from data/buildings/raw")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    # Line-buffer stdout so a `nohup ... > log` run shows progress as it happens.
    sys.stdout.reconfigure(line_buffering=True)

    dom = _domain.active()
    out_dir = DATA / f"buildings_{dom.name}"
    out_dir.mkdir(parents=True, exist_ok=True)
    b = domain_bbox_utm()
    print(f"domain {dom.name}: bbox EPSG:{EPSG} "
          f"{b[0]:.0f},{b[1]:.0f},{b[2]:.0f},{b[3]:.0f} (region + {BUFFER_DEG} deg)")

    manifest: dict = {
        "domain": dom.name,
        "region": str(dom.region.relative_to(ROOT)),
        "bbox_utm18": [round(x, 1) for x in b],
        "buffer_deg": BUFFER_DEG,
        "epsg": EPSG,
        "pulled": date.today().isoformat(),
        "sources": {},
    }

    if args.source in ("both", "njdep"):
        g = njdep(args.reuse_raw, args.workers)
        out = out_dir / "njdep_footprints.gpkg"
        atomic_write_gpkg(g, out, "njdep_footprints")
        by = (g.groupby(["project", "year"]).size().sort_values(ascending=False))
        print(f"NJDEP in domain: {len(g):,} footprints, "
              f"{g.area.sum() / 1e6:.1f} km2 -> {out}")
        print(by.to_string())
        manifest["sources"]["njdep"] = {
            "name": "NJDEP Statewide Building Footprints derived from Impervious "
                    "Surfaces of New Jersey",
            "service": NJDEP_LAYER,
            "statewide_raw": str(NJDEP_FGB.relative_to(ROOT)),
            "file": str(out.relative_to(ROOT)),
            "n": int(len(g)),
            "area_km2": round(float(g.area.sum() / 1e6), 3),
            "by_project_year": {f"{p} | {y}": int(n) for (p, y), n in by.items()},
            "vintage_note": "LiDAR campaign per polygon (project/year). Coast is mostly "
                            "2014 post-Sandy LiDAR + 2010 Atlantic/Ocean/S.Monmouth. "
                            "2014 is AFTER the storm: destroyed-and-not-rebuilt houses "
                            "are missing, rebuilt ones carry post-storm footprints.",
        }

    if args.source in ("both", "microsoft"):
        g = microsoft(args.reuse_raw)
        out = out_dir / "microsoft_footprints.gpkg"
        atomic_write_gpkg(g, out, "microsoft_footprints")
        print(f"Microsoft in domain: {len(g):,} footprints, "
              f"{g.area.sum() / 1e6:.1f} km2 -> {out}")
        manifest["sources"]["microsoft"] = {
            "name": "Microsoft US Building Footprints v2 (New Jersey)",
            "url": MS_URL,
            "license": "ODbL",
            "statewide_raw": str(MS_ZIP.relative_to(ROOT)),
            "file": str(out.relative_to(ROOT)),
            "n": int(len(g)),
            "area_km2": round(float(g.area.sum() / 1e6), 3),
            "vintage_note": "ML extraction from 2019-2020 imagery (README: focal-area "
                            "rerun); 7 years post-storm.",
        }

    mpath = out_dir / "manifest.json"
    tmp = mpath.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(manifest, indent=2))
    os.replace(tmp, mpath)
    print(f"wrote {mpath}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
