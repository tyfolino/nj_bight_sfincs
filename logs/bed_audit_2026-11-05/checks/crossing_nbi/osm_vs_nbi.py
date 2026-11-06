"""What the public NBI does not list, counted in OSM (2026-11-06): railway bridges, foot / path bridges, other bridges
with no NBI match, and road underpasses carrying a posted `maxheight` (the slot depth an underpass check needs).
Areas: the v4 ring (`region_v4_hot_plus_vertices.csv`, 1.x), the 2.0 ring (`ring_new_full.csv`) and 2.0's NEW area
(2.0 minus v4). One table: out/osm_vs_nbi.csv + .md here. No purchase: the point is to judge whether TomTom / HERE
would add structures OSM lacks.

OSM bridges: /scratch/.../decks_2026-11-04/bridges.gpkg (the 11-04 extract the NBI match used; bridge=* ways).
Underpasses with maxheight: Overpass (kumi.systems mirror), `way[highway][maxheight]` centres, pulled now into
ENC's sibling dir. An OSM bridge counts as NBI-covered when its id is an NBI match or it lies within 25 m of one
(OSM splits one structure into several ways).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path("/cache/home/tpj8/nj_bight_sfincs")
HERE = Path(__file__).resolve().parent
DL = Path("/scratch/tpj8/nj_bight_sfincs_data/audit/levee_enc_2026-11-06/osm")
BR = Path("/scratch/tpj8/nj_bight_sfincs_data/decks_2026-11-04/bridges.gpkg")
PATHS = {"footway", "path", "cycleway", "pedestrian", "steps", "bridleway", "track"}


def ring(csv):
    from shapely.geometry import Polygon
    d = pd.read_csv(csv, comment="#")
    return Polygon(np.c_[d.lon.values, d.lat.values])


def overpass_maxheight(box, out):
    if out.exists() and out.stat().st_size > 100:
        return json.loads(out.read_text())
    q = f'[out:json][timeout:300];way["highway"]["maxheight"]({box[1]},{box[0]},{box[3]},{box[2]});out center tags;'
    for ep in ("https://overpass.kumi.systems/api/interpreter", "https://overpass.private.coffee/api/interpreter",
               "https://overpass-api.de/api/interpreter"):
        r = subprocess.run(["curl", "-s", "-m", "400", "-A", "nj-sfincs-audit/1.0 (research)", "--data-urlencode",
                            f"data={q}", ep], capture_output=True, text=True)
        try:
            d = json.loads(r.stdout)
            out.write_text(r.stdout)
            return d
        except json.JSONDecodeError:
            continue
    raise RuntimeError("overpass failed on every mirror")


def main():
    import geopandas as gpd
    from shapely import contains_xy
    DL.mkdir(parents=True, exist_ok=True)
    v4 = ring(REPO / "data/v4_design/region_v4_hot_plus_vertices.csv")
    v20 = ring(REPO / "logs/hudson_design_2026-11-02/ring_new_full.csv")
    new = v20.difference(v4)
    areas = {"v4 ring (1.x)": v4, "2.0 ring": v20, "2.0 new area only": new}
    br = gpd.read_file(BR, layer="bridges")
    br = br[br.geometry.notna()].drop_duplicates("osm_id").reset_index(drop=True)
    M = pd.read_parquet(REPO / "logs/nbi_crossings_2026-11-05/out/nbi_matched.parquet")
    ids = set(M.osm_bridge.dropna().astype(str).str.split(",").explode().str.strip())
    brm = br.to_crs(32618)
    isid = brm.osm_id.astype(str).isin(ids).values
    near = np.zeros(len(brm), bool)
    if isid.any():
        mb = brm.geometry[isid].buffer(25.0)
        hit = mb.sindex.query(brm.geometry, predicate="intersects")   # (input i, tree j)
        near[np.unique(hit[0])] = True
    br["nbi"] = isid | near
    hw, rw = br.get("highway"), br.get("railway")
    br["kind"] = np.where(rw.notna() & ~rw.isin(["abandoned", "disused", "razed", "proposed"]), "rail bridge",
                          np.where(hw.isin(PATHS), "foot / path bridge",
                                   np.where(hw.notna(), "road bridge", "other bridge")))
    c = br.geometry.representative_point()
    bx, by = c.x.values, c.y.values
    xmin, ymin, xmax, ymax = v20.union(v4).bounds
    mh = overpass_maxheight((xmin, ymin, xmax, ymax), DL / "maxheight_ways.json")
    el = [e for e in mh.get("elements", []) if "center" in e]
    hx = np.array([e["center"]["lon"] for e in el])
    hy = np.array([e["center"]["lat"] for e in el])
    D = pd.read_csv(REPO / "logs/nbi_crossings_2026-11-05/out/nbi_domain.csv", usecols=["lon", "lat"])
    rows = []
    for an, A in areas.items():
        ins = contains_xy(A, bx, by)
        r = {"area": an, "NBI records": int(contains_xy(A, D.lon.values, D.lat.values).sum())}
        for k in ("road bridge", "rail bridge", "foot / path bridge", "other bridge"):
            sel = ins & (br.kind.values == k)
            r[f"OSM {k}"] = int(sel.sum())
            r[f"  of which NOT in NBI"] = None
            r[f"OSM {k} NOT in NBI"] = int((sel & ~br.nbi.values).sum())
        r.pop("  of which NOT in NBI")
        r["OSM underpass ways with maxheight"] = int(contains_xy(A, hx, hy).sum()) if hx.size else 0
        rows.append(r)
    T = pd.DataFrame(rows)
    T.to_csv(HERE / "osm_vs_nbi.csv", index=False)
    md = ["| " + " | ".join(T.columns) + " |", "|" + "---|" * len(T.columns)]
    md += ["| " + " | ".join(str(v) for v in row) + " |" for row in T.itertuples(index=False)]
    (HERE / "osm_vs_nbi.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
