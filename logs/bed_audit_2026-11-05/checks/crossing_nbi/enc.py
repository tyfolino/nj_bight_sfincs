"""NOAA ENC bridge objects for crossing_nbi (2026-11-06).

Source: NOAA ENC Direct to GIS (https://encdirect.noaa.gov/arcgis/rest/services/encdirect/), the S-57 BRIDGE object
(OBJL 11) as Bridge_line / Bridge_area in the harbour (layers 87 / 141) and approach (91 / 146) usage bands, pulled
2026-11-06 over -75.72,38.73,-73.55,40.99 into ENC_DIR (public domain, US Government). Berthing has none here; the
coastal service was down (it would only repeat approach-scale bridges).

Attributes used: VERCLR (vertical clearance, fixed bridge), VERCCL (closed clearance, movable bridge), VERCOP (open
clearance), HORCLR (horizontal clearance), CATBRG, OBJNAM, DSNM (the cell). S-57 clearances are in metres above the
cell's vertical datum for heights, which on US charts is MEAN HIGH WATER (VERDAT is blank on all of these, = the cell
default). MHW is taken as the crossing's MHHW (`water_mhhw`, VDatum) minus nothing: on this coast MHHW - MHW is
0.05-0.15 m, inside the lidar accuracy the NBI thresholds already carry.

What a chart adds: a charted BRIDGE with a clearance is a navigable opening over water — so the bed in its opening
must be water (below MHW). That is a MEASURED fact about the opening (the NBI has 54B = 0 over water).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

ENC_DIR = Path("/scratch/tpj8/nj_bight_sfincs_data/audit/levee_enc_2026-11-06/enc")
FILES = {"harbour": ["enc_harbour_87_0.geojson", "enc_harbour_141_0.geojson"],
         "approach": ["enc_approach_91_0.geojson", "enc_approach_146_0.geojson"]}
MATCH_M = 100.0
SOURCE = "NOAA ENC Direct (S-57 BRIDGE, harbour + approach bands, pulled 2026-11-06)"


def load():
    import geopandas as gpd
    import pandas as pd
    parts = []
    for band, fs in FILES.items():
        for f in fs:
            p = ENC_DIR / f
            if not p.exists():
                continue
            d = json.loads(p.read_text())
            if not d.get("features"):
                continue
            g = gpd.GeoDataFrame.from_features(d["features"], crs=4326)
            g["band"] = band
            parts.append(g)
    E = pd.concat(parts, ignore_index=True)
    E = gpd.GeoDataFrame(E, geometry="geometry", crs=4326).to_crs(32618)
    for k in ("VERCLR", "VERCCL", "VERCOP", "HORCLR"):
        E[k] = pd.to_numeric(E.get(k), errors="coerce")
    E["clear_m"] = E.VERCLR.fillna(E.VERCCL)
    E["rank"] = E.band.map({"harbour": 0, "approach": 1}) + np.where(E.clear_m.notna(), 0, 10)
    return E.reset_index(drop=True)


def match(E, x, y):
    """For each point: the best ENC bridge within MATCH_M (a clearance first, harbour before approach, then nearest)."""
    from shapely import points
    sidx = E.sindex
    P = points(x, y)
    out = []
    for k, p in enumerate(P):
        if not np.isfinite(x[k]):
            out.append(None)
            continue
        cand = sidx.query(p.buffer(MATCH_M))
        if cand.size == 0:
            out.append(None)
            continue
        d = E.geometry.values[cand].distance(p)
        sub = E.iloc[cand].assign(d=d)
        sub = sub[sub.d <= MATCH_M].sort_values(["rank", "d"])
        out.append(None if sub.empty else sub.iloc[0])
    return out


# ---------------------------------------------------------------- piers (coordinator 11-06)
PIER_W = 1.5     # m: ASSUMED typical pier / pile-bent width across the flow where the chart gives no shape
PYLON_FILES = ["enc_harbour_28_0.geojson", "enc_harbour_149_0.geojson", "enc_approach_30_0.geojson",
               "enc_approach_154_0.geojson"]
PILE_GLOB = "enc_harbour_58_*.geojson"


def load_supports():
    """Charted bridge supports: S-57 PYLONS (point + area) and PILPNT (pile points), UTM. Area pylons carry their
    width across = the short side of their minimum rotated rectangle."""
    import geopandas as gpd
    import pandas as pd
    parts = []
    for f in PYLON_FILES + sorted(p.name for p in ENC_DIR.glob(PILE_GLOB)):
        p = ENC_DIR / f
        if not p.exists():
            continue
        d = json.loads(p.read_text())
        if not d.get("features"):
            continue
        g = gpd.GeoDataFrame.from_features(d["features"], crs=4326)
        g["obj"] = "PILPNT" if "_58_" in f else "PYLONS"
        parts.append(g[["geometry", "obj", "DSNM"]] if "DSNM" in g else g[["geometry", "obj"]])
    S = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), geometry="geometry", crs=4326).to_crs(32618)

    def width(geom):
        if geom.geom_type in ("Polygon", "MultiPolygon"):
            mrr = geom.minimum_rotated_rectangle
            xs, ys = mrr.exterior.coords.xy
            e = [np.hypot(xs[i + 1] - xs[i], ys[i + 1] - ys[i]) for i in range(2)]
            return float(min(e))
        return PIER_W
    S["w_m"] = [width(g) for g in S.geometry]
    S["pt"] = S.geometry.representative_point()
    return S.reset_index(drop=True)


def charted_piers(S, search):
    """Supports inside `search` (a buffered bridge geometry, UTM): count, total width, positions (lon lat; ...)."""
    from pyproj import Transformer
    if search is None or search.is_empty:
        return 0, 0.0, ""
    pts = S.pt
    idx = pts.sindex.query(search, predicate="intersects")
    if idx.size == 0:
        return 0, 0.0, ""
    sub = S.iloc[idx]
    to = Transformer.from_crs(32618, 4326, always_xy=True)
    lo, la = to.transform(sub.pt.x.values, sub.pt.y.values)
    pos = "; ".join(f"{a:.5f} {b:.5f}" for a, b in zip(lo[:12], la[:12])) + ("; ..." if len(sub) > 12 else "")
    return int(len(sub)), float(sub.w_m.sum()), pos


def nbi_piers(spans45, spans46, len49, maxspan48, width):
    """NBI estimate: piers ~ main + approach spans - 1; spacing ~ len49 / spans (max span 48 reported beside it);
    piers IN the channel ~ the channel width / spacing - 1, capped at the total; blockage = that x PIER_W / width."""
    n = (spans45 if np.isfinite(spans45) else 0) + (spans46 if np.isfinite(spans46) else 0)
    if n <= 0:
        return np.nan, np.nan, np.nan, np.nan
    piers = max(n - 1, 0)
    spacing = len49 / n if np.isfinite(len49) and n > 0 else (maxspan48 if np.isfinite(maxspan48) else np.nan)
    if not (np.isfinite(width) and width > 0 and np.isfinite(spacing) and spacing > 0):
        return piers, spacing, np.nan, np.nan
    in_ch = int(min(piers, max(round(width / spacing) - 1, 0)))
    return piers, spacing, in_ch, min(1.0, in_ch * PIER_W / width)
