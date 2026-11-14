#!/usr/bin/env python
"""Write data/nj2_design/region_nj2_vertices.csv: the 2.0 ring with its NOTES restored.

    python -I logs/nj2_freeze_2026-11-14/make_ring.py      (from the repo root)

The vertex list is `logs/v2_prep_2026-11-04/ring_new_full_v2edit.csv` VERBATIM (name, lon,
lat — asserted equal, same order): v4_hot_plus's ring with hudson_route_03..21 + narrows_w /
narrows_e replaced by the Manhattan / Queens / Brooklyn legs of
`ring_recommended_v2edit.csv` (hudson_w 45 m W, astoria 100 m inland, user 11-03/11-04).
That splice dropped the `note` column; this puts it back (v4_hot_plus's note on every kept
vertex, ring_recommended_v2edit's kind + note on every new one) and writes the header.
Refuses if any coordinate or the order would change.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

ROOT = Path.cwd()
SPLICED = ROOT / "logs/v2_prep_2026-11-04/ring_new_full_v2edit.csv"
HOT_PLUS = ROOT / "data/v4_design/region_v4_hot_plus_vertices.csv"
NEW_LEGS = ROOT / "logs/v2_prep_2026-11-04/ring_recommended_v2edit.csv"
OUT = ROOT / "data/nj2_design/region_nj2_vertices.csv"

HEADER = """\
# nj2 (Model 2.0) region ring: NAMED vertices joined by straight lines (the polygon closes itself). SOURCE OF TRUTH.
# Derived copy: data/region_nj2.geojson (scripts/ring_to_geojson.py; records this file's sha256 — re-run after any edit).
# = v4_hot_plus's ring (data/v4_design/region_v4_hot_plus_vertices.csv: v4's 09-25 trace, hand edits, A+ river cuts at
#   today's head of tide) with hudson_route_03..21 + narrows_w / narrows_e REPLACED by the Hudson + Upper Bay legs:
#   palisades_ec -> [hudson_w -> hudson_e: FORCED, the Hudson at 40.860] -> the Manhattan spine -> e88 ->
#   [hellgate_w -> hellgate_e: FORCED, the East River at Hell Gate] -> Astoria -> the Queens / Brooklyn moraine -> bk_bensonhurst.
#   Design: logs/hudson_design_2026-11-02/README.md (decisions user 11-03); edits: logs/v2_prep_2026-11-04/README.md §3
#   (hudson_w 45 m W, astoria 100 m inland; user 11-03/11-04); walked at 10 m and 1 m on 1/9" CUDEM against 6.44 m
#   (Battery crest + 3 m): 0.300 km of ring ground below 6.44 m is reached from inside, all of it the declared Hell Gate
#   east wall (hellgate_e -> astoria, 0-300 m). The e88 -> hellgate_w low run (385-644 m, 3.22 m) is a declared wall too
#   (user 11-03 decision 5). Upper Bay, the Kill van Kull, the Hudson to 40.860 and the East River to Hell Gate are COMPUTED.
# The Lewes edge (v4_refreeze) is in Domain.waterlevel_line_sea_closure_ll, not here. Assembled 2026-11-14 by
# logs/nj2_freeze_2026-11-14/make_ring.py (coordinates = logs/v2_prep_2026-11-04/ring_new_full_v2edit.csv, asserted).
# NOT audited by scripts/audit_region_v4.py (it hard-codes v4's neighbour basins and writes over the v4 record).
"""


def rows(path: Path) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(ln for ln in f if not ln.startswith("#")))


def main() -> int:
    spliced = rows(SPLICED)
    hot = {r["name"]: r for r in rows(HOT_PLUS)}
    new = {r["name"]: r for r in rows(NEW_LEGS)}
    out = []
    for r in spliced:
        n = r["name"]
        h = hot.get(n)
        if h is not None:  # a kept v4_hot_plus vertex: its own note
            assert (float(h["lon"]), float(h["lat"])) == (
                float(r["lon"]),
                float(r["lat"]),
            ), n
            out.append((n, r["lon"], r["lat"], h.get("note") or ""))
            continue
        nw = new.get(n)
        assert nw is not None, f"{n}: in neither v4_hot_plus nor the new legs"
        assert (float(nw["lon"]), float(nw["lat"])) == (
            float(r["lon"]),
            float(r["lat"]),
        ), n
        kind = nw["kind"]
        note = nw["note"]
        if kind == "forced":
            note = f"FORCED ({'hudson' if n.startswith('hudson') else 'hell_gate'} arm): {note}"
        out.append((n, r["lon"], r["lat"], f"nj2 ({kind}): {note}"))
    assert [o[0] for o in out] == [r["name"] for r in spliced]
    dropped = sorted(set(hot) - {o[0] for o in out})
    print(f"{len(out)} vertices; dropped from v4_hot_plus: {dropped}")
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["name", "lon", "lat", "note"])
    for o in out:
        w.writerow(o)
    OUT.write_text(HEADER + buf.getvalue())
    # round trip: the coordinates the polygon is built from are the spliced file's, exactly
    back = rows(OUT)
    assert [(b["name"], b["lon"], b["lat"]) for b in back] == [
        (r["name"], r["lon"], r["lat"]) for r in spliced
    ]
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
