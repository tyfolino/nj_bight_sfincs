#!/usr/bin/env python
"""Write v4's quadtree refinement polygons from the readable RECIPE below, and diff them by
NAME against v3's. Read-only on every input.

    PYTHONPATH=$PWD python scripts/build_refinement_v4.py [--out data/quadtree/refinement_v4.geojson]

Levels: 0 = base_res 200 m (not listed), 1 = 100 m, 2 = 50 m, 3 = 25 m; a face takes the
HIGHEST level of any polygon it is in whose [zmin, zmax] its coarse bed falls in
(`Domain.coarse_elevation_list`).

🔴 WHY A DIFF BY NAME (CLAUDE.md §5): v3's first recipe silently dropped three of v1.5's
polygons and three runs were voided; every guard passed, because a fingerprint seals the
mesh you built, not the one you meant. So this prints every v3 name as carried / changed /
dropped, and every v4-only name as new.

Every polygon is CLIPPED TO THE LANDWARD RING — the ring minus the sea seaward of the drawn
water-level line (`Domain.waterlevel_line`, user 2026-09-27). Seaward stays at 200 m: that is
Track C (the shelf is SnapWave-only, and SnapWave is ~95 % of wall clock). It is also why
the depth gates that only kept v3's recipe OFF the shelf (`low_water` zmin −20,
`shelf_shoaling` −30) open up: landward of the line all water is computed, at any depth.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from nj_sfincs import domain as D

ROOT = Path(__file__).resolve().parents[1]
V3 = ROOT / "data" / "quadtree" / "refinement_v3.geojson"
OUT = ROOT / "data" / "quadtree" / "refinement_v4.geojson"
RIVERBEDS = ROOT / "data" / "elevation_v4" / "riverbeds"
#: NHD StreamRiver areas + their named centrelines over the landward ring, fetched by
#: `logs/v4_design_2026-09-27/river_widths.py fetch` (the width survey behind the rule).
NHD_RIVERS = ROOT / "data" / "v4_design" / "nhd_rivers"
CRS = 32618
ANY = 100.0  # "no gate": beyond every ring bed (deepest -47.8 m)

# (name, level, zmin, zmax, geometry, why). geometry:
#   "landward"            the whole landward ring
#   ("v3", name)          v3's polygon of that name (then clipped)
#   ("river", reach, m)   the NHD centreline of a riverbed reach, buffered m metres
RECIPE: list[tuple[str, int, float, float, object, str]] = [
    (
        "shelf_shoaling",
        1,
        -ANY,
        -8.0,
        "landward",
        "100 m on water deeper than -8 m landward of the line: the strip between the "
        "surf band and the line, and the deep bay / channel water that `low_water` then "
        "lifts to 50 m. v3: zmin -30 kept it off the deep shelf; the line does that now.",
    ),
    (
        "inland_floodplain",
        1,
        0.0,
        10.0,
        "landward",
        "100 m on land 0..+10 m (v3: 0..+6). v4 design rule 09-24: MOTF-wet land p95 "
        "4.3 m, p99 7.6 m, and the +3 m SLR target — the far banks (DE / PA / Staten "
        "Island) are computed at 100 / 200 m only.",
    ),
    (
        "low_water",
        2,
        -ANY,
        3.0,
        "landward",
        "50 m on every water body landward of the line AT ANY DEPTH (v3: zmin -20) — the "
        "Delaware ship channel to -47.8 m, KvK -16, Ambrose, the C&D — plus land below "
        "+3 m that flooded. The user's rule of 09-27 applied to resolution as well as to "
        "the mask. v3's `low_water`, ring-wide.",
    ),
    (
        "narrow_channels",
        3,
        -ANY,
        3.0,
        ("narrow", 50.0, 50.0),
        "25 m within 50 m of every named NHD centreline where the channel is NARROWER "
        "than 50 m (width = 2 x centreline-to-bank distance, every 25 m), gated to bed "
        "< +3 m — the tidal / flooded reach. van Ormondt 2025: cell spacing must not "
        "exceed channel width (meander flux error ~ sinuosity^1.5); the 09-27 survey "
        "(`data/v4_design/river_widths_v4.csv`) found 1,349 km of named channel under "
        "50 m, 521 km of it 25-50 m (met at 25 m), many marsh creeks at sinuosity "
        "1.5-3. Under 25 m (827 km) only the subgrid helps.",
    ),
    (
        "river_channels_above_tide",
        2,
        -ANY,
        ANY,
        ("river", ("delaware_above_falls", "raritan_above_new_brunswick"), 150.0),
        "50 m along the two reaches whose BED sits above +3 m (Delaware falls -> "
        "Washington Crossing -0.8..+6.5, Raritan New Brunswick -> Manville -1.4..+7.7; "
        "`riverbeds_v4`), which `low_water`'s +3 m gate would leave at 100 m — one face "
        "across a 60-100 m Raritan. NHD centreline + 150 m, ungated.",
    ),
    ("narrows_cut", 3, -40.0, 2.0, ("v3", "narrows_cut"), "v3 verbatim."),
    ("arthur_kill_cut", 3, -40.0, 2.0, ("v3", "arthur_kill_cut"), "v3 verbatim."),
    ("cape_may_canal", 3, -40.0, 2.0, ("v3", "cape_may_canal"), "v3 verbatim."),
    *(
        (
            f"surf_dune_{i:02d}",
            3,
            -8.0,
            3.0,
            ("v3", f"surf_dune_{i:02d}"),
            "v3 verbatim.",
        )
        for i in range(14)
    ),
    ("coastal_corridor", 2, -20.0, 5.0, ("v3", "coastal_corridor"), "v3 verbatim."),
    (
        "shrewsbury_navesink",
        3,
        -8.0,
        3.0,
        ("v3", "shrewsbury_navesink"),
        "v3 verbatim.",
    ),
    ("bay_fringe", 3, -1.0, 2.0, ("v3", "bay_fringe"), "v3 verbatim."),
]


def landward() -> shapely.Geometry:
    v4 = D.DOMAINS["v4"]
    ring = gpd.read_file(v4.region).to_crs(CRS).geometry.iloc[0]
    sea = gpd.GeoSeries([shapely.Polygon(D.sea_polygon(v4)[1])], crs=4326)
    return ring.difference(sea.to_crs(CRS).iloc[0])


def river(reaches, buf_m) -> shapely.Geometry:
    lines = [
        gpd.read_file(RIVERBEDS / f"nhd_flowline_{r}.geojson").to_crs(CRS).union_all()
        for r in reaches
    ]
    return shapely.union_all(lines).buffer(buf_m)


def narrow(max_w: float, buf_m: float, step: float = 25.0) -> shapely.Geometry:
    """Where named NHD centrelines run through channel narrower than ``max_w``, buffered."""

    def read(kind):
        parts = [gpd.read_file(f) for f in sorted(NHD_RIVERS.glob(f"{kind}_*.geojson"))]
        g = pd.concat([p for p in parts if len(p)], ignore_index=True)
        return g.set_crs(4326, allow_override=True).to_crs(CRS)

    area, path = read("area"), read("path")
    polys = area.geometry.make_valid().values
    tree = shapely.STRtree(polys)
    lines = shapely.line_merge(shapely.union_all(path.geometry.values))
    pts = []
    for ln in getattr(lines, "geoms", [lines]):
        if ln.length < step:
            continue
        # only the channel polygons near THIS centreline: a state-wide outline makes
        # every distance query walk every bank in the ring
        near = polys[tree.query(ln.buffer(max_w))]
        if not len(near):
            continue
        water = shapely.union_all(near)
        p = shapely.line_interpolate_point(ln, np.arange(0.0, ln.length, step))
        keep = shapely.contains(water, p) & (
            2 * shapely.distance(water.boundary, p) < max_w
        )
        pts.append(p[keep])
    return shapely.union_all(shapely.buffer(np.concatenate(pts), buf_m))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    land = landward()
    v3 = gpd.read_file(V3).to_crs(CRS).set_index("name")
    rows, geoms = [], []
    for name, lev, zmin, zmax, spec, why in RECIPE:
        if spec == "landward":
            g = land
        elif spec[0] == "v3":
            g = v3.geometry[spec[1]]
        elif spec[0] == "narrow":
            g = narrow(spec[1], spec[2])
        elif spec[0] == "river":
            g = river(spec[1], spec[2])
        else:
            raise ValueError(spec)
        g = g.intersection(land)
        rows.append(
            dict(name=name, refinement_level=lev, zmin=zmin, zmax=zmax, why=why)
        )
        geoms.append(g)
    out = gpd.GeoDataFrame(rows, geometry=geoms, crs=CRS)
    if out.name.duplicated().any():
        raise ValueError("duplicate polygon names")

    # ── the diff BY NAME against v3 ────────────────────────────────────────────────
    print(f"refinement v3 ({len(v3)}) -> v4 ({len(out)}), by NAME:")
    o = out.set_index("name")
    for name in v3.index:
        if name not in o.index:
            print(f"  🔴 DROPPED  {name}  (L{v3.refinement_level[name]})")
            continue
        a, b = v3.loc[name], o.loc[name]
        ch = [
            f"{k} {a[k]:g} -> {b[k]:g}"
            for k in ("refinement_level", "zmin", "zmax")
            if float(a[k]) != float(b[k])
        ]
        a_km2, b_km2 = a.geometry.area / 1e6, b.geometry.area / 1e6
        geo = (
            f"area {a_km2:,.1f} -> {b_km2:,.1f} km2"
            if abs(b_km2 - a_km2) > 0.01 * max(a_km2, 1)
            else f"area {b_km2:,.1f} km2 (same)"
        )
        tag = "CHANGED " if ch or "same" not in geo else "carried "
        print(
            f"  {tag} {name:22s} L{b.refinement_level}  {'; '.join(ch) or '-'}  {geo}"
        )
    for name in o.index.difference(v3.index):
        b = o.loc[name]
        print(
            f"  NEW      {name:22s} L{b.refinement_level}  z {b.zmin:g}..{b.zmax:g}  "
            f"area {b.geometry.area / 1e6:,.1f} km2"
        )
    # hydromt's `refine_in_polygon` reads `.exterior`, so a MultiPolygon (a band the
    # clip cut in two at an inlet) must go in as one ROW PER PIECE, same name, same gates.
    parts = out.explode(index_parts=False).reset_index(drop=True)
    parts = parts[parts.geometry.area > 0]
    split = parts.name.value_counts()
    split = split[split > 1]
    print(
        f"\nlandward ring {land.area / 1e6:,.0f} km2; wrote {args.out}: {len(parts)} rows "
        f"({len(out)} named polygons"
        + (
            f"; split by the clip: {', '.join(f'{n} x{k}' for n, k in split.items())}"
            if len(split)
            else ""
        )
        + ")"
    )

    tmp = args.out.with_suffix(".tmp.geojson")
    parts.to_file(tmp, driver="GeoJSON")
    tmp.replace(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
