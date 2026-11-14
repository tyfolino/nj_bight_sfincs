#!/usr/bin/env python
"""Write Model 2.0.0's (`nj2`) quadtree refinement polygons: v4's recipe, unchanged, plus
three new bands, minus v4's `narrows_cut`; records of the alternatives. Diff every file BY NAME against v4's. Read-only on every
input.

    PYTHONPATH=$PWD python scripts/build_refinement_nj2.py                # domain nj2
    PYTHONPATH=$PWD python scripts/build_refinement_nj2.py --domain v4 \
        --out-dir logs/nj2_refinement_2026-11-14/probe_inputs            # probe on v4's ring
    PYTHONPATH=$PWD python scripts/build_refinement_nj2.py --ring-csv <ring.csv> ...  # provisional

Writes, in ``--out-dir`` (default ``data/nj2_design``):

* ``refinement_nj2.geojson``            **2.0.0 (user 2026-11-14)**: v4 + ``hudson_waterfront``
                                        + ``newark_meadowlands`` + ``capemay_inlets``, and
                                        v4's ``narrows_cut`` DELIBERATELY DROPPED (the Narrows is
                                        no longer a forced cut in nj2; its 25 m cells over 33 m
                                        of water held the whole model's time step)
* ``refinement_nj2_narrows25.geojson``  RECORD: the same WITH ``narrows_cut`` (the pre-decision
                                        proposal)
* ``refinement_nj2_inlets12.geojson``   RECORD, not a candidate (user: no 12.5 m level): the
                                        2.0.0 file PLUS ``capemay_ebb_12m`` (a level-4 patch)
* ``refinement_nj2_v4only.geojson``     v4's recipe alone on this ring (narrows_cut kept, NO
                                        new-ground narrow channels): the CONTROL a probe needs
                                        to attribute faces to the bands

``--no-narrow-ext`` writes the same set WITHOUT the new-ground narrow channels (for a probe's
attribution; point ``--out-dir`` at scratch). ``--fetch-nhd`` (network) fills the NHD cache
the new-ground rule reads, ``data/nj2_design/nhd_new_area/``; a plain run never fetches.

Levels: 0 = base_res 200 m (not listed), 1 = 100 m, 2 = 50 m, 3 = 25 m, 4 = 12.5 m. hydromt
refines a cell when it lies in a polygon AND the cell's coarse-bed [min, max] OVERLAPS the
polygon's [zmin, zmax] (`quadtree_builder.py`, `zmax > poly.zmin and zmin < poly.zmax`).

HOW V4 IS CARRIED (CLAUDE.md §5 trap #1: diff the lists by NAME). v4's polygons are read from
the file the frozen v4 mesh was built from (`data/quadtree/refinement_v4.geojson`, md5
709af1eb…, = `logs/slurm/2026-09/v4_freeze_expected.md5`), not re-derived:
* the three RING-WIDE polygons of v4's recipe (`shelf_shoaling`, `inland_floodplain`,
  `low_water`: "landward" in `build_refinement_v4.RECIPE`) are re-made on THIS domain's
  landward ring, so the new Hudson / Upper Bay / East River area gets v4's 50 / 100 / 200 m
  rule (memo option A, the NY "far bank" rule);
* every other v4 polygon keeps its v4 GEOMETRY exactly, clipped to this landward ring. So
  `narrows_cut`, `bay_fringe`, `narrow_channels` etc. do NOT grow into the new area (v3's
  `narrows_cut` / `bay_fringe` reach past v4's Narrows cut into NY ground; v4's clip is kept).
The diff prints each v4 name as carried / CHANGED (area) / DROPPED and each new name.

NARROW CHANNELS ON THE NEW GROUND (user 2026-11-14): `narrow_channels` = v4's geometry (as
above) PLUS v4's rule (`build_refinement_v4.narrow_from`, same 50 m width / 50 m buffer / 25 m
step, same L3 and -ANY..+3 m gate) applied to the new ground only (this landward ring minus
v4's), so the old ground stays v4's polygon to the vertex. One change of SOURCE, not of rule:
v4 read NHD StreamRiver areas (ftype 460) and NAMED ArtificialPaths; in New York NHD maps the
tidal creeks as part of the Estuary waterbody (493; Gowanus, Newtown Creek, English / Dutch
Kills) and Gowanus's centreline carries no name, so v4's source finds none of them. The new
ground reads 460 + CanalDitch 336 + BayInlet 312 areas + Estuary 493 waterbodies, and every
ArtificialPath (558), named or not.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.parse
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from nj_sfincs import domain as D

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_refinement_v4 as V4R  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
V4_FILE = ROOT / "data" / "quadtree" / "refinement_v4.geojson"
V4_MD5 = "709af1ebc208fc113b9848eda444913e"  # the freeze's (v4_freeze_expected.md5)
OUT_DIR = ROOT / "data" / "nj2_design"
CRS = 32618
ANY = 100.0
#: v4 names that `build_refinement_v4.RECIPE` builds on the WHOLE landward ring.
RINGWIDE = ("shelf_shoaling", "inland_floodplain", "low_water")
#: v4's narrow-channel rule, read from v4's recipe (not retyped): ("narrow", max_w, buf_m)
NARROW_SPEC = next(r[4] for r in V4R.RECIPE if r[0] == "narrow_channels")
#: NHD cache for the NEW ground (`--fetch-nhd`); 0.1-degree tiles over each new piece
NHD_NEW = ROOT / "data" / "nj2_design" / "nhd_new_area"
NHD_URL = "https://hydro.nationalmap.gov/arcgis/rest/services/nhd/MapServer"
NHD_LAYERS = (  # (kind, layer, where): Area - Large Scale, Waterbody - LS, Flowline - LS
    ("area", 9, "ftype IN (460, 336, 312)"),
    ("wb", 12, "ftype = 493"),
    ("path", 6, "ftype = 558"),
)
NHD_TILE = 0.1

# ── The new bands. Vertices are (name, lon, lat), straight lines between them. ──────────
# Shared edge of the two north-Jersey bands: v4's own ring vertices along the Palisades /
# Bergen Hill ridge (data/v4_design/region_v4_vertices.csv), which nj2 retires as a ring
# edge. West of it = Newark Bay / Meadowlands (already in v4), east = the new Hudson strip.
_RIDGE = (
    ("hudson_route_17", -74.090, 40.644),  # mid Kill van Kull, off Bayonne
    ("hudson_route_16", -74.090, 40.6545),
    ("hudson_route_15", -74.100, 40.660),
    ("hudson_route_14", -74.114, 40.668),
    ("hudson_route_13", -74.106, 40.679),
    ("hudson_route_12", -74.100, 40.690),
    ("hudson_route_11", -74.096, 40.700),
    ("hudson_route_10", -74.086, 40.708),
    ("hudson_route_09", -74.076, 40.724),
    ("hudson_route_08", -74.056, 40.748),
    ("hudson_route_07", -74.0382, 40.7592),
    ("hudson_route_06", -74.0146, 40.790),
    ("hudson_route_05", -74.012, 40.804),
    ("hudson_route_04", -73.995, 40.828),
    ("hudson_route_03", -73.9856, 40.8393),
    ("hudson_route_02", -73.9661, 40.8834),
)

HUDSON_WATERFRONT = (
    # north end: the nj2 ring's own vertices down to the Hudson cut (hudson_design §1)
    ("hudson_route_02", -73.9661, 40.8834),
    ("palisades_ec", -73.9600, 40.8680),
    ("hudson_w", -73.95753, 40.8600),
    # the NJ / NY line, drawn mid-river (NJ shore ~ -73.952 / -73.990 / -74.020 / -74.033
    # at 40.86 / 40.80 / 40.75 / 40.71; Manhattan ~ -73.938 / -73.972 / -74.007 / -74.017):
    # +-200 m does not matter, the gate keeps the deep river at 50 m and NY is >= 0.6 km off
    ("state_hudson_860", -73.9455, 40.8600),
    ("state_hudson_800", -73.9800, 40.8000),
    ("state_hudson_750", -74.0130, 40.7500),
    ("state_hudson_710", -74.0250, 40.7100),
    ("state_upper_bay_695", -74.0300, 40.6950),  # leaves Ellis / Liberty on the NJ side
    ("state_upper_bay_670", -74.0450, 40.6700),
    ("robbins_reef", -74.0655, 40.6575),
    ("state_kvk_east", -74.0750, 40.6455),
    *_RIDGE,  # back north along the old ring edge (hudson_route_17 -> 02)
)

NEWARK_MEADOWLANDS = (
    # the shared ridge edge, south -> north
    *_RIDGE,
    ("hudson_route_01", -73.9641, 40.8916),
    # north and west: past the ring (the clip trims it): the Hackensack to New Milford,
    # the Passaic to the Dundee Dam, the Rahway / Elizabeth rivers
    ("ne_corner", -73.9600, 41.0000),
    ("nw_corner", -74.3500, 41.0000),
    ("sw_corner", -74.3500, 40.5750),
    # the NJ / NY line up the Arthur Kill and along the Kill van Kull, mid-channel
    ("ak_carteret", -74.2090, 40.5750),
    ("ak_goethals", -74.1970, 40.6355),
    ("kvk_bergen_point", -74.1650, 40.6400),
    ("kvk_bayonne_bridge", -74.1420, 40.6415),
)

#: The five Cape May County - Great Egg inlets: the 11-09 inlet line (A, B), UTM 18N,
#: `logs/capemay_tests_2026-11-09/out/inlet_lines.csv` (A = bay-on-left start).
INLETS = {
    "great_egg": ((538445.0, 4349625.0), (540040.0, 4350747.0)),
    "corson": ((530046.0, 4339283.0), (530616.0, 4340195.0)),
    "townsends": ((524535.0, 4329839.0), (524567.0, 4330193.0)),
    "hereford": ((517725.0, 4319209.0), (519579.0, 4320393.0)),
    "cape_may_inlet": ((510906.0, 4310813.0), (511575.0, 4311185.0)),
}
#: Each patch is a COAST-ALIGNED RECTANGLE centred on its inlet line's midpoint: +-ALONG m
#: along the coast (azimuth COAST_AZ, Cape May Inlet -> Great Egg), BACK m landward of the
#: centre, SEA m seaward. Sizes read off fig/inlets.png so the rectangle holds the throat and
#: the whole ebb delta out past its -8 m front. Hereford's centre is its main channel, not the
#: island-to-island line's midpoint.
COAST_AZ = 35.0
#: The inlet patches stop this far landward of the forced sea line (a 25 m face there would
#: change the forced boundary itself; it stays v4's).
LINE_CLEARANCE_M = 400.0
PATCH = {  # name: (centre x, centre y, ALONG, BACK, SEA)
    "great_egg": (539240.0, 4350190.0, 2000.0, 600.0, 3200.0),
    "corson": (530330.0, 4339740.0, 1300.0, 600.0, 1800.0),
    "townsends": (524550.0, 4330015.0, 1500.0, 600.0, 2200.0),
    "hereford": (518300.0, 4319500.0, 2000.0, 600.0, 3000.0),
    "cape_may_inlet": (511240.0, 4310999.0, 1500.0, 600.0, 3000.0),
}


def _inlet_quad(name: str) -> list[tuple[str, float, float]]:
    """Four named corners (lon, lat) of the inlet's coast-aligned rectangle."""
    from pyproj import Transformer

    cx, cy, along, back, sea = PATCH[name]
    az = np.radians(COAST_AZ)
    c = np.array([np.sin(az), np.cos(az)])  # alongshore, to the NE
    n = np.array([np.cos(az), -np.sin(az)])  # seaward, to the SE
    o = np.array([cx, cy])
    pts = (
        ("back_sw", o - along * c - back * n),
        ("back_ne", o + along * c - back * n),
        ("sea_ne", o + along * c + sea * n),
        ("sea_sw", o - along * c + sea * n),
    )
    t = Transformer.from_crs(CRS, 4326, always_xy=True)
    out = []
    for k, (x, y) in pts:
        lo, la = t.transform(x, y)
        out.append((f"{name}_{k}", round(lo, 5), round(la, 5)))
    return out


#: ``EBB[name] = (lon/lat vertex list, named vertices)`` for the readers (mesh_now.py).
EBB = {n: ([(lo, la) for _v, lo, la in _inlet_quad(n)], _inlet_quad(n)) for n in INLETS}

# (name, level, zmin, zmax, vertices-or-key, why)
NEW_BANDS = [
    (
        "hudson_waterfront",
        3,
        -1.0,
        5.0,
        HUDSON_WATERFRONT,
        "Hudson memo option B (logs/hudson_design_2026-11-02/README.md §2): NJ ground "
        "-1..+5 m at 25 m from Bayonne (Kill van Kull) to the Hudson cut at 40.860 N, "
        "between the retired v4 ridge edge and the NJ/NY line mid-river. Sandy's marks reach "
        "3.4-3.9 m here (STN), `bay_fringe`'s +2 m would stop short. NY side stays v4's "
        "far-bank rule (memo B).",
    ),
    (
        "newark_meadowlands",
        3,
        -1.0,
        5.0,
        NEWARK_MEADOWLANDS,
        "The same rule on Newark Bay, the tidal Passaic / Hackensack / Meadowlands, "
        "Elizabeth and the Rahway mouth, NJ side of the Arthur Kill / KvK line. v4 had "
        "them at 50 m below +3 m and 100 m above; STN marks 3.4-3.9 m around Newark Bay, "
        "2.3-2.8 m in the Meadowlands. Edge with `hudson_waterfront`: v4's ridge vertices.",
    ),
    (
        "capemay_inlets",
        3,
        -ANY,
        3.0,
        "inlets",
        "25 m over the whole throat + ebb delta of Great Egg, Corson, Townsends, Hereford "
        "and Cape May Inlet AT ANY DEPTH (a coast-aligned rectangle on each inlet: the "
        "throat and the whole ebb delta, 1.8-3.2 km seaward). v4 already has 25 m there down to -8 m "
        "(`surf_dune_*`); this fills the deeper throat / delta-front faces still at 50 m.",
    ),
]
#: The level-4 RECORD (file `_inlets12`; user 11-14: not taken): ebb-shoal crests and surf.
EBB_12M = (
    "capemay_ebb_12m",
    4,
    -6.0,
    1.0,
    "inlets",
    "12.5 m (a FIFTH level) on the same five patches, gated to bed -6..+1 m: the ebb-delta "
    "crests, swash bars and channel margins where the waves break — the 11-14 READ's "
    "mechanism 1 (too little set-up at the mouths). Costs a global time step (see README).",
)


def _ll_poly(verts) -> shapely.Geometry:
    g = gpd.GeoSeries([shapely.Polygon([(lo, la) for _n, lo, la in verts])], crs=4326)
    p = g.to_crs(CRS).iloc[0]
    if not p.is_valid:
        raise ValueError(
            f"self-intersecting band: {shapely.validation.explain_validity(p)}"
        )
    return p


def landward(dom: D.Domain | None, ring_csv: Path | None) -> shapely.Geometry:
    """The ring minus the sea seaward of the drawn water-level line (as in v4)."""
    if ring_csv is not None:
        v = pd.read_csv(ring_csv, comment="#")
        ring = (
            gpd.GeoSeries([shapely.Polygon(zip(v.lon, v.lat))], crs=4326)
            .to_crs(CRS)
            .iloc[0]
        )
        sea_dom = D.DOMAINS["v4"]  # PROVISIONAL: assumes nj2 keeps v4's sea line
    else:
        ring = gpd.read_file(dom.region).to_crs(CRS).geometry.iloc[0]
        sea_dom = dom
    sea = D.sea_polygon(sea_dom)
    if sea is None:
        return ring
    sea = gpd.GeoSeries([shapely.Polygon(sea[1])], crs=4326).to_crs(CRS).iloc[0]
    return ring.difference(sea)


def forced_line_of(dom: D.Domain | None) -> shapely.Geometry:
    """The drawn water-level line (UTM), this domain's or (provisional ring) v4's."""
    path = (
        dom if dom is not None and dom.waterlevel_line else D.DOMAINS["v4"]
    ).waterlevel_line
    v = D.read_waterlevel_line(path)
    ln = gpd.GeoSeries([shapely.LineString([(lo, la) for _n, lo, la in v])], crs=4326)
    return ln.to_crs(CRS).iloc[0]


def new_ground(land: shapely.Geometry) -> shapely.Geometry:
    """This landward ring minus v4's (empty on v4's own ring)."""
    return land.difference(V4R.landward())


def _nhd_tiles(new: shapely.Geometry):
    """(tag, lon/lat box) of every NHD_TILE tile touching a piece of the new ground."""
    ll = gpd.GeoSeries([new], crs=CRS).to_crs(4326).iloc[0]
    out = {}
    for piece in getattr(ll, "geoms", [ll]):
        x0, y0, x1, y1 = piece.bounds
        for lo in np.arange(np.floor(x0 / NHD_TILE) * NHD_TILE, x1, NHD_TILE):
            for la in np.arange(np.floor(y0 / NHD_TILE) * NHD_TILE, y1, NHD_TILE):
                box = (lo, la, lo + NHD_TILE, la + NHD_TILE)
                if piece.intersects(shapely.box(*box)):
                    out[f"{lo:+.2f}_{la:+.2f}"] = box
    return out


def fetch_nhd(new: shapely.Geometry) -> None:
    """Cache the NHD layers over the new ground (skip-if-present, atomic per file)."""
    sys.path.insert(0, str(ROOT / "logs" / "v4_design_2026-09-27"))
    from river_widths import _get  # v4's fetch helper (retries)

    NHD_NEW.mkdir(parents=True, exist_ok=True)
    for tag, box in _nhd_tiles(new).items():
        for kind, layer, where in NHD_LAYERS:
            f = NHD_NEW / f"{kind}_{tag}.geojson"
            if f.exists():
                continue
            feats, off = [], 0
            while True:
                q = {
                    "where": where,
                    "geometry": ",".join(f"{v:.4f}" for v in box),
                    "geometryType": "esriGeometryEnvelope",
                    "inSR": 4326,
                    "spatialRel": "esriSpatialRelIntersects",
                    "outFields": "gnis_name,ftype,permanent_identifier",
                    "outSR": 4326,
                    "f": "geojson",
                    "resultOffset": off,
                    "resultRecordCount": 1000,
                }
                got = _get(f"{NHD_URL}/{layer}/query?" + urllib.parse.urlencode(q))
                got = got.get("features", [])
                feats += got
                if len(got) < 1000:
                    break
                off += len(got)
            tmp = f.with_suffix(".tmp")
            tmp.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
            tmp.replace(f)
            print(f"  nhd {kind} {tag}: {len(feats)}")


def _read_nhd(kind: str) -> gpd.GeoDataFrame:
    parts = [gpd.read_file(f) for f in sorted(NHD_NEW.glob(f"{kind}_*.geojson"))]
    parts = [p for p in parts if len(p)]
    if not parts:
        return gpd.GeoDataFrame(geometry=[], crs=CRS)
    g = pd.concat(parts, ignore_index=True)
    g.columns = [c if c == "geometry" else c.lower() for c in g.columns]
    g = g.drop_duplicates(
        "permanent_identifier"
    )  # a feature crossing tiles comes twice
    return (
        gpd.GeoDataFrame(g, geometry="geometry")
        .set_crs(4326, allow_override=True)
        .to_crs(CRS)
    )


def narrow_new_ground(new: shapely.Geometry) -> shapely.Geometry:
    """v4's narrow-channel rule on the new ground (the widened NHD source), with a report."""
    missing = [
        f"{kind}_{tag}"
        for tag in _nhd_tiles(new)
        for kind, _l, _w in NHD_LAYERS
        if not (NHD_NEW / f"{kind}_{tag}.geojson").exists()
    ]
    if missing:
        raise SystemExit(
            f"NHD cache {NHD_NEW} lacks {len(missing)} tile files ({missing[:3]} ...): "
            "run once with --fetch-nhd"
        )
    _kind, max_w, buf_m = NARROW_SPEC
    water = pd.concat([_read_nhd("area"), _read_nhd("wb")], ignore_index=True)
    path = _read_nhd("path")
    # only centrelines that reach the new ground (the rule itself is per centreline)
    path = path[path.intersects(new.buffer(max_w + buf_m))]
    _g, pts, wid = V4R.narrow_from(water, path, max_w, buf_m, with_points=True)
    near = shapely.intersects(shapely.buffer(pts, buf_m), new)
    pts, wid = pts[near], wid[near]
    g = shapely.union_all(shapely.buffer(pts, buf_m)).intersection(new)
    # report: each kept sample named by its NHD centreline, grouped by ~1 km cell
    t = gpd.GeoDataFrame({"w": wid}, geometry=pts, crs=CRS)
    nm = gpd.sjoin_nearest(t, path[["gnis_name", "geometry"]], max_distance=5.0)
    nm = nm[~nm.index.duplicated()]
    ll = t.to_crs(4326).geometry
    rep = pd.DataFrame(
        {
            "name": nm.gnis_name.reindex(t.index).fillna("(unnamed)"),
            "w": wid,
            "lon": ll.x.values,
            "lat": ll.y.values,
        }
    )
    rep["cell"] = (
        (rep.lon * 100).round().astype(int).astype(str)
        + "_"
        + (rep.lat * 100).round().astype(int).astype(str)
    )
    print(
        f"\nnarrow channels on the NEW ground ({new.area / 1e6:,.1f} km2): {len(pts)} "
        f"samples under {max_w:g} m, buffered {buf_m:g} m -> {g.area / 1e6:.3f} km2 in "
        f"{len(getattr(g, 'geoms', [g]))} piece(s); by centreline name and ~1 km cell:"
    )
    with pd.option_context("display.width", 160):
        print(
            rep.groupby(["name", "cell"])
            .agg(
                samples=("w", "size"),
                w_median=("w", "median"),
                lon=("lon", "median"),
                lat=("lat", "median"),
                lat_max=("lat", "max"),
            )
            .round({"w_median": 1, "lon": 4, "lat": 4, "lat_max": 4})
            .to_string()
        )
    return g


def v4_polygons() -> gpd.GeoDataFrame:
    md5 = hashlib.md5(V4_FILE.read_bytes()).hexdigest()
    if md5 != V4_MD5:
        raise RuntimeError(
            f"{V4_FILE} md5 {md5} is not the frozen v4 mesh's ({V4_MD5}): v4's record moved"
        )
    g = gpd.read_file(V4_FILE).to_crs(CRS)
    meta = g.drop(columns="geometry").groupby("name", sort=False).first()
    geom = g.groupby("name", sort=False).geometry.apply(shapely.union_all)
    return gpd.GeoDataFrame(meta, geometry=geom.reindex(meta.index), crs=CRS)


def build(
    land,
    v4: gpd.GeoDataFrame,
    variant: str,
    forced_line: shapely.Geometry,
    narrow_ext: shapely.Geometry | None = None,
) -> gpd.GeoDataFrame:
    rows, geoms = [], []
    for name, r in v4.iterrows():
        if variant in ("final", "inlets12") and name == "narrows_cut":
            continue
        g = land if name in RINGWIDE else r.geometry.intersection(land)
        why = r.get("why") or ""
        why = (
            "v4 recipe, re-made on the nj2 landward ring. "
            if name in RINGWIDE
            else "v4 geometry verbatim, clipped to the nj2 landward ring. "
        ) + str(why)
        if name == "narrow_channels" and narrow_ext is not None and variant != "v4only":
            g = g.union(narrow_ext)
            why = (
                "nj2: PLUS v4's same rule on the new ground (nj2 ring minus v4's), NHD "
                "460/336/312 areas + 493 estuary + every 558 path (user 2026-11-14). "
            ) + why
        rows.append(
            dict(
                name=name,
                refinement_level=int(r.refinement_level),
                zmin=float(r.zmin),
                zmax=float(r.zmax),
                why=why,
            )
        )
        geoms.append(g)
    if variant == "v4only":
        bands = []
    else:
        bands = list(NEW_BANDS) + ([EBB_12M] if variant == "inlets12" else [])
    for name, lev, zmin, zmax, spec, why in bands:
        if spec == "inlets":
            g = shapely.union_all([_ll_poly(_inlet_quad(n)) for n in INLETS])
            # keep the forced line exactly v4's: the Cape May Inlet / Hereford / Great Egg
            # rectangles reach the ~10 m line, and refining there added 93 forced `ocean`
            # cells on the v4-ring probe (3,372 -> 3,465, 63918132)
            g = g.difference(forced_line.buffer(LINE_CLEARANCE_M))
        else:
            g = _ll_poly(spec)
        rows.append(
            dict(name=name, refinement_level=lev, zmin=zmin, zmax=zmax, why=why)
        )
        geoms.append(g.intersection(land))
    out = gpd.GeoDataFrame(rows, geometry=geoms, crs=CRS)
    if out.name.duplicated().any():
        raise ValueError("duplicate polygon names")
    return out


def diff(v4: gpd.GeoDataFrame, out: gpd.GeoDataFrame, label: str) -> None:
    print(
        f"\n{label}: refinement v4 ({len(v4)} names) -> nj2 ({len(out)} names), by NAME:"
    )
    o = out.set_index("name")
    for name in v4.index:
        if name not in o.index:
            print(f"  🔴 DROPPED  {name}  (L{v4.refinement_level[name]})")
            continue
        a, b = v4.loc[name], o.loc[name]
        ch = [
            f"{k} {a[k]:g} -> {b[k]:g}"
            for k in ("refinement_level", "zmin", "zmax")
            if float(a[k]) != float(b[k])
        ]
        a_km2, b_km2 = a.geometry.area / 1e6, b.geometry.area / 1e6
        same = abs(b_km2 - a_km2) <= 0.005 * max(a_km2, 1)
        geo = (
            f"area {b_km2:,.1f} km2 (same)"
            if same
            else f"area {a_km2:,.1f} -> {b_km2:,.1f} km2"
        )
        tag = "CHANGED " if ch or not same else "carried "
        print(
            f"  {tag} {name:26s} L{b.refinement_level}  {'; '.join(ch) or '-'}  {geo}"
        )
    for name in o.index.difference(v4.index, sort=False):
        b = o.loc[name]
        print(
            f"  NEW      {name:26s} L{b.refinement_level}  z {b.zmin:g}..{b.zmax:g}  "
            f"area {b.geometry.area / 1e6:,.1f} km2"
        )


def write(out: gpd.GeoDataFrame, path: Path) -> None:
    # hydromt's `refine_in_polygon` reads `.exterior`: one ROW PER PIECE (as v4).
    parts = out.explode(index_parts=False).reset_index(drop=True)
    parts = parts[parts.geom_type.eq("Polygon") & (parts.geometry.area > 0)]
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.geojson")
    parts.to_file(tmp, driver="GeoJSON")
    tmp.replace(path)
    print(
        f"  wrote {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}: "
        f"{len(parts)} rows"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", default="nj2")
    ap.add_argument(
        "--ring-csv",
        type=Path,
        default=None,
        help="PROVISIONAL ring (named vertices), with v4's sea line",
    )
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    ap.add_argument("--prefix", default="refinement_nj2")
    ap.add_argument(
        "--no-narrow-ext",
        action="store_true",
        help="no new-ground narrow channels (probe attribution; write to scratch)",
    )
    ap.add_argument(
        "--fetch-nhd", action="store_true", help="fill the new-ground NHD cache first"
    )
    args = ap.parse_args()

    dom = None
    if args.ring_csv is None:
        if args.domain not in D.DOMAINS:
            raise SystemExit(
                f"domain {args.domain!r} is not registered; pass --ring-csv for a "
                "provisional ring"
            )
        dom = D.DOMAINS[args.domain]
    land = landward(dom, args.ring_csv)
    forced_line = forced_line_of(dom)
    print(f"ring: {args.ring_csv or dom.region}; landward {land.area / 1e6:,.0f} km2")
    v4 = v4_polygons()
    new = new_ground(land)
    print(f"new ground (this landward ring minus v4's): {new.area / 1e6:,.1f} km2")
    if args.fetch_nhd:
        fetch_nhd(new)
    narrow_ext = None
    if args.no_narrow_ext:
        print("--no-narrow-ext: narrow_channels = v4's geometry only")
    elif new.area > 0:
        narrow_ext = narrow_new_ground(new)

    print("\nnew-band vertices (lon, lat):")
    for name, lev, zmin, zmax, spec, _why in NEW_BANDS + [EBB_12M]:
        verts = (
            [v for n in INLETS for v in _inlet_quad(n)] if spec == "inlets" else spec
        )
        print(f"  {name} (L{lev}, z {zmin:g}..{zmax:g}):")
        for vn, lo, la in verts:
            print(f"     {vn:22s} {lo:10.5f} {la:9.5f}")

    for variant, suffix in (
        ("final", ""),
        ("narrows25", "_narrows25"),
        ("inlets12", "_inlets12"),
        ("v4only", "_v4only"),
    ):
        out = build(land, v4, variant, forced_line, narrow_ext)
        diff(v4, out, f"[{variant}]")
        write(out, args.out_dir / f"{args.prefix}{suffix}.geojson")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
