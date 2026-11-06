"""Fetch the impoundment check's authoritative layers (cached; run once, `python -I fetch.py`).

- NID dams (USACE National Inventory of Dams), the v4 box: reused from the 10-05 §54 pull
  (/scratch/tpj8/nj_bight_sfincs_data/inland_water_2026-10-05/nid_dams.geojson, 796 dams), copied here.
- NWI polygons (USFWS National Wetlands Inventory, Wetlands MapServer layer 0) in three classes, the v4 box,
  0.5 deg tiles, paged:
    lakes     ATTRIBUTE LIKE 'L%'                                   (lacustrine: never tidal)
    ponds     'PUB%' / 'PAB%' / 'PUS%'                              (palustrine open water / aquatic bed / shore)
    tidalwater 'E1UB%' / 'E1AB%' / 'R1%'                            (subtidal estuarine open water; tidal riverine)
  Raw GeoJSON is untrusted data: parsed with json only.
"""

from __future__ import annotations

import json
import shutil
import time
import urllib.parse
import urllib.request
from pathlib import Path

RAW = Path("/scratch/tpj8/nj_bight_sfincs_data/audit/impoundment")
RAW.mkdir(parents=True, exist_ok=True)
NWI = "https://fwspublicservices.wim.usgs.gov/wetlandsmapservice/rest/services/Wetlands/MapServer/0"
BOX = (-75.85, 38.6, -73.7, 40.95)
CLASSES = {
    "lakes": "ATTRIBUTE LIKE 'L%'",
    "ponds_ub": "ATTRIBUTE LIKE 'PUB%'",
    "ponds_ab": "ATTRIBUTE LIKE 'PAB%'",
    "ponds_us": "ATTRIBUTE LIKE 'PUS%'",
    "tidal_e1ub": "ATTRIBUTE LIKE 'E1UB%'",
    "tidal_e1ab": "ATTRIBUTE LIKE 'E1AB%'",
    "tidal_r1": "ATTRIBUTE LIKE 'R1%'",
}


def get(url, tries=6):
    for k in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=240) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            if k == tries - 1:
                raise
            print("   retry", k, e, flush=True)
            time.sleep(5 * (k + 1))


def query(where, box, page=500, simplify=None):
    feats, off = [], 0
    while True:
        q = {"where": where, "geometry": ",".join(map(str, box)), "geometryType": "esriGeometryEnvelope",
             "inSR": 4326, "spatialRel": "esriSpatialRelIntersects",
             "outFields": "ATTRIBUTE,WETLAND_TYPE,ACRES", "outSR": 4326,
             "geometryPrecision": 6, "f": "geojson", "resultOffset": off, "resultRecordCount": page}
        if simplify:
            q["maxAllowableOffset"] = simplify  # deg; ~3 m, for the huge bay polygons (500s otherwise)
        d = json.loads(get(f"{NWI}/query?" + urllib.parse.urlencode(q)))
        got = d.get("features", [])
        feats += got
        if not got or (len(got) < page and not d.get("properties", {}).get("exceededTransferLimit")):
            return feats
        off += len(got)


def tiles(step=0.5):
    x0, y0, x1, y1 = BOX
    x = x0
    while x < x1:
        y = y0
        while y < y1:
            yield (round(x, 4), round(y, 4), round(min(x + step, x1), 4), round(min(y + step, y1), 4))
            y += step
        x += step


if __name__ == "__main__":
    src = Path("/scratch/tpj8/nj_bight_sfincs_data/inland_water_2026-10-05/nid_dams.geojson")
    if not (RAW / "nid_dams.geojson").exists():
        shutil.copy2(src, RAW / "nid_dams.geojson")
    for name, where in CLASSES.items():
        out = RAW / f"nwi_{name}.geojson"
        if out.exists():
            print(name, "cached")
            continue
        seen, feats = set(), []
        tidal = name.startswith('tidal')
        for t in tiles(0.5 if name == 'lakes' else (0.1 if tidal else 0.2)):
            for f in query(where, t, page=100 if tidal else 500, simplify=0.00003 if tidal else None):
                g = json.dumps(f["geometry"], sort_keys=True)[:200] + str(f["properties"])
                if g in seen:  # a polygon crossing a tile edge comes back twice
                    continue
                seen.add(g)
                feats.append(f)
            print(f"  {name} {t}: {len(feats)}", flush=True)
        out.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
        print(name, len(feats))
