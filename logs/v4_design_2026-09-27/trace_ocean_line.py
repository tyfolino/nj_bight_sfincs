#!/usr/bin/env python
"""Trace a DRAFT v4 ocean water-level line through NACCS save points — ONCE.

    python logs/v4_design_2026-09-27/trace_ocean_line.py
      -> data/v4_design/ocean_line_v4.csv   (named vertices; then edited BY HAND)

User 2026-09-27: "form that boundary by connecting node to node" instead of the jagged
-10 m isobath. As with the ring (09-25), an algorithm draws the FIRST draft only; the CSV
is the source of truth from then on, hand-edited, and `scripts/audit_ocean_line_v4.py`
checks it. This file is kept for the record of how the draft was made.

RULE
  * GUIDE: a coarse NJ ocean shoreline of named points (below), used only for
    along-coast / offshore coordinates.
  * CANDIDATES: ADCIRC save points wet through the padded Sandy window (10-24..11-01, the
    boundary builder's own screen), SEAWARD of the guide, ≤ 15 km offshore, ADCIRC depth
    10–15 m (FINDINGS §22–23: NACCS carries its own setup, so a node much shallower than
    the -10 m design depth double-counts what SnapWave adds shoreward). Where a 2.5 km
    stretch has none, 8–18 m.
  * SELECTION: every 2.5 km along the guide, the candidate closest to the running median
    (±7.5 km) of the 10–15 m candidates' offshore distance — a smooth line, not a zig-zag
    between every node. All wet nodes within 2 km still FORCE it (the builder's support
    screen); the vertices only fix the geometry.
  * ENDS: south on Cape May Point's meridian (-74.96, the `delaware_sea` polygon's east
    edge) at the first node's latitude; north at the ring's Lower Bay closure vertex
    `ocean_rockaway_s` (-73.94, 40.45), where v1.5's forced closure line starts.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import shapely
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[2]
#: The draft this wrote was hand-extended the same day into data/v4_design/waterlevel_line_v4.csv
#: (the whole forced sea line); re-running would recreate the superseded coast-only draft.
OUT = ROOT / "data" / "v4_design" / "ocean_line_v4.csv"

GUIDE = (  # the NJ ocean shoreline, south → north (lon, lat)
    ("g_cape_may_point", -74.960, 38.930),
    ("g_wildwood", -74.800, 39.000),
    ("g_ocean_city", -74.570, 39.260),
    ("g_atlantic_city", -74.420, 39.360),
    ("g_brigantine", -74.330, 39.430),
    ("g_holgate", -74.270, 39.520),
    ("g_barnegat_light", -74.100, 39.760),
    ("g_seaside", -74.070, 39.950),
    ("g_manasquan", -74.030, 40.100),
    ("g_long_branch", -73.980, 40.300),
    ("g_sandy_hook", -73.990, 40.460),
)
STEP = 2500.0
SMOOTH = 7500.0
MAX_OFF = 15000.0
BAND, WIDE = (10.0, 15.0), (8.0, 18.0)
START_LON = -74.960
END = ("end_lower_bay_closure", -73.940, 40.450)

T = Transformer.from_crs(4326, 32618, always_xy=True)
TI = Transformer.from_crs(32618, 4326, always_xy=True)


def main() -> None:
    c = np.load(ROOT / "data" / "NACCS" / "_sandy_parsed.npz", allow_pickle=True)
    t = np.array([dt.datetime.strptime(str(s), "%Y%m%d%H%M") for s in c["times"]])
    win = (t >= dt.datetime(2012, 10, 24)) & (t <= dt.datetime(2012, 11, 1))
    wl = c["wl"][:, win]
    wet = (wl > -9000).all(axis=1)
    peak = np.where(wl > -9000, wl, np.nan).max(axis=1)
    x, y = T.transform(c["lon"], c["lat"])

    gx, gy = T.transform([g[1] for g in GUIDE], [g[2] for g in GUIDE])
    guide = shapely.LineString(np.c_[gx, gy])
    pts = shapely.points(x, y)
    along = shapely.line_locate_point(guide, pts)
    foot = shapely.line_interpolate_point(guide, along)
    ahead = shapely.line_interpolate_point(guide, np.minimum(along + 10, guide.length))
    back = shapely.line_interpolate_point(guide, np.maximum(along - 10, 0))
    tx, ty = shapely.get_x(ahead) - shapely.get_x(back), shapely.get_y(ahead) - shapely.get_y(back)
    vx, vy = x - shapely.get_x(foot), y - shapely.get_y(foot)
    off = np.hypot(vx, vy) * np.where(tx * vy - ty * vx < 0, 1.0, -1.0)  # + = seaward
    dep = c["depth"]
    base = wet & (off > 0) & (off <= MAX_OFF) & (along > 0) & (along < guide.length)
    band = base & (dep >= BAND[0]) & (dep <= BAND[1])
    wide = base & (dep >= WIDE[0]) & (dep <= WIDE[1])
    print(f"candidates: {band.sum()} at {BAND} m, {wide.sum()} at {WIDE} m")

    ib = np.flatnonzero(band)
    rows = []
    for s0 in np.arange(0.0, guide.length, STEP):
        near = np.abs(along[ib] - (s0 + STEP / 2)) <= SMOOTH
        if not near.any():
            continue
        target = np.median(off[ib][near])
        pool = np.flatnonzero(band & (along >= s0) & (along < s0 + STEP))
        tag = "10-15 m"
        if pool.size == 0:
            pool = np.flatnonzero(wide & (along >= s0) & (along < s0 + STEP))
            tag = "8-18 m (gap fill)"
        if pool.size == 0:
            continue
        k = pool[np.argmin(np.abs(off[pool] - target))]
        rows.append((along[k], k, tag, target))

    lines = [
        "# v4 OCEAN water-level line: NAMED vertices joined by straight lines, south → north. SOURCE OF TRUTH once edited.",
        "# DRAFT traced 2026-09-27 by logs/v4_design_2026-09-27/trace_ocean_line.py (rule in its docstring): NACCS",
        "# ADCIRC save points wet through Sandy at 10-15 m, one per 2.5 km of coast, nearest the smoothed offshore distance.",
        "# Edit BY HAND (move / drop / add a vertex); check with scripts/audit_ocean_line_v4.py --line <this csv> [--maps].",
        "# Columns: name, lon, lat, sp (NACCS save point id, blank for a non-node vertex), naccs_depth_m (ADCIRC, +down),",
        "# sandy_peak_msl_m (NACCS max over 10-24..11-01, MSL 1992), note.",
        "name,lon,lat,sp,naccs_depth_m,sandy_peak_msl_m,note",
    ]
    first = rows[0][1]
    lines.append(
        f"start_cape_may_meridian,{START_LON:.5f},{c['lat'][first]:.5f},,,,"
        "on the delaware_sea polygon's east edge at the first node's latitude"
    )
    for _, k, tag, target in rows:
        lines.append(
            f"sp_{int(c['sp'][k])},{c['lon'][k]:.5f},{c['lat'][k]:.5f},{int(c['sp'][k])},"
            f"{dep[k]:.2f},{peak[k]:.3f},{tag}; {off[k] / 1000:.1f} km offshore (target {target / 1000:.1f})"
        )
    lines.append(f"{END[0]},{END[1]:.5f},{END[2]:.5f},,,,ring vertex ocean_rockaway_s: v1.5's closure starts here")
    OUT.write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT}: {len(rows) + 2} vertices ({len(rows)} nodes)")


if __name__ == "__main__":
    main()
