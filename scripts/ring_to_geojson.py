#!/usr/bin/env python
"""Write a domain's region GeoJSON FROM its named-vertex CSV — the CSV stays the source.

    python scripts/ring_to_geojson.py data/v4_design/region_v4_vertices.csv data/region_v4.geojson

WHY THIS EXISTS. Since 2026-09-25 a ring is a hand-edited list of named straight-line
vertices (`name, lon, lat, note`), because a list is readable and a generated polygon is
not. But ~28 readers (the mask builder, the downloaders, the scorers) take ``Domain.region``
as a polygon FILE. So the GeoJSON is a derived copy, and a derived copy is only safe if
it cannot silently fall behind: the output records ``source_sha256`` of the CSV it was
written from, and ``domain.region_source_mismatch`` / ``assert_buildable`` refuse to build
on a GeoJSON whose recorded hash no longer matches the CSV. Edit the CSV, re-run this.

The polygon is the vertices in file order joined by straight lines, closed — the same
construction ``scripts/audit_region_v4.py --ring <csv>`` audits. An invalid polygon
(self-intersecting) is refused, never repaired: a repair would move the edge.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def csv_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "csv", type=Path, help="named-vertex ring CSV (name, lon, lat, ...)"
    )
    ap.add_argument("out", type=Path, help="GeoJSON to write (atomically)")
    args = ap.parse_args()

    import pandas as pd
    from shapely.geometry import Polygon, mapping

    v = pd.read_csv(args.csv, comment="#")
    if v["name"].duplicated().any():
        raise SystemExit(
            f"duplicate vertex names: {sorted(v.name[v.name.duplicated()])}"
        )
    poly = Polygon(zip(v.lon, v.lat))
    if not poly.is_valid:
        from shapely.validation import explain_validity

        raise SystemExit(f"ring is not a valid polygon: {explain_validity(poly)}")

    src = args.csv.resolve()
    rel = src.relative_to(ROOT) if src.is_relative_to(ROOT) else src
    gj = {
        "type": "FeatureCollection",
        "name": args.out.stem,
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"},
        },
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "name": args.out.stem,
                    "source": str(rel),
                    "source_sha256": csv_sha256(args.csv),
                    "n_vertices": len(v),
                    "note": "DERIVED — edit the source CSV and re-run "
                    "scripts/ring_to_geojson.py; never edit this file.",
                },
                "geometry": mapping(poly),
            }
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=args.out.parent, suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(gj, f, indent=1)
        f.write("\n")
    os.replace(tmp, args.out)
    print(
        f"{args.out}: {len(v)} vertices from {rel} "
        f"(sha256 {gj['features'][0]['properties']['source_sha256'][:16]})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
