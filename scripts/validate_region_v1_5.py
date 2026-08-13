#!/usr/bin/env python
"""Validate the HAND-DRAWN v1_5_raritan region polygon. Writes nothing, ever.

    python scripts/validate_region_v1_5.py            # the gate
    python scripts/validate_region_v1_5.py --plot     # + a figure to reports/figures/
    python scripts/validate_region_v1_5.py --verbose  # per-reach sample dumps

🔴 **THE DRAWN FILE IS THE AUTHORITY.** `data/region_v1_5_raritan_edited.geojson` was drawn
by hand in QGIS over Esri imagery + CUDEM. This script READS it. It has no write path and
must never grow one: the predecessor of this file *generated* the polygon from 16 named
vertices, and once the ring was redrawn to 40 vertices that generator became a loaded gun
pointed at the only copy of the real geometry.

WHY A VALIDATOR AT ALL, AND WHY IT CHECKS *WET REACHES* RATHER THAN SEGMENTS
---------------------------------------------------------------------------

The region is NOT the boundary. `build_static` runs

    create_active(zmin=mask_zmin)  →  region clip  →  land_boxes → 0
    →  _fill_inactive_holes  →  create_boundary  →  demote mask==2 outside every arm

so what actually decides where a water-level BC can appear is: **wherever the ring crosses
water**. `create_boundary` puts `mask==2` on the outermost active WET cells, and every one
of those that is not inside a declared arm has to be demoted. A wet ring crossing you did
not declare is therefore not cosmetic — it is imposed ocean level somewhere you never
looked.

⚠️ **Ring VERTICES are not hydrography.** A hand-drawn vertex lands where the cursor landed;
the water it crosses does not care. Tagging *segments* (what the generator did) attributes a
crossing to whichever vertex pair happens to straddle it, which is how a 1.79 km segment of
dry ground came to be recorded as "the Raritan River cut" while the real 0.48 km river
crossing sat unnamed inside its 2.39 km neighbour. So this script ignores the segment
structure entirely: it walks the ring at a fixed ground step, reads the SAME elevation stack
`build_static` will read, and finds contiguous runs of bed below `WET_Z`. Those runs — not
the segments — are the objects that must each be declared.

WHAT A DECLARATION MEANS
------------------------

Every wet reach must fall inside exactly one box in `CROSSINGS`, and each box says whether
that crossing is `forced` (it will carry `mask==2` and must have NACCS support) or `closed`
(it will be demoted to land, and the exchange through it is deliberately outside the model).
An undeclared wet reach is a FAILURE, not a warning — that is the whole point.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DRAWN = ROOT / "data" / "region_v1_5_raritan_edited.geojson"
SUPPORT = ROOT / "data" / "naccs_support_points.geojson"
FIG = ROOT / "reports" / "figures"

#: Ground step along the ring, metres. 50 m is finer than the finest planned cell, so a
#: crossing cannot hide between two samples.
STEP_M = 50.0

#: Bed below this is "wet". Not 0.0: a metre of slack keeps the intertidal fringe of a
#: long land segment from registering as a crossing.
WET_Z = -0.5

#: A wet run shorter than this is not a crossing — it is a sample or two of ditch. One
#: fine cell is ~100 m, so a reach below that cannot open a channel.
MIN_REACH_KM = 0.10

#: The boundary isobath. 🔴 This is a DOMAIN axis, not an arm axis — it is half of the
#: premier fingerprint, and a -10 m and a -15 m boundary are two registered domains
#: sharing one mesh_key. Keep it in step with the domain being validated.
MASK_ZMIN = -10.0

#: The support screen. ⚠️ NOT "max gap <= 2.0 km": the inherited Atlantic arm measures max
#: 2.76 km / 95.6% within 2 km on the real mesh and is the adopted boundary, so a bare
#: maximum test would reject the premier's own geometry. The fraction is the gate; the
#: maximum is a ceiling that catches a genuinely unsupported limb.
SUPPORT_RADIUS_KM = 2.0
SUPPORT_MIN_FRAC = 0.95
SUPPORT_MAX_GAP_KM = 3.0



@dataclass(frozen=True)
class Crossing:
    """A declared place where the ring is allowed to cross water.

    ``box`` is (lon_min, lat_min, lon_max, lat_max) — a coordinate box, per the project
    convention, never an auto-derived polygon. ``kind`` is 'forced' (carries mask==2, needs
    NACCS support) or 'closed' (demoted to land; the exchange is outside the model).
    ``km_bracket`` is a sanity bracket on the WET length, not on the segment length: a
    crossing far outside it is a redraw or a typo, not a design change.
    """

    name: str
    kind: str
    box: tuple[float, float, float, float]
    km_bracket: tuple[float, float]
    why: str
    #: A support figure already measured against `mask==2` cells on a REAL mesh. When
    #: present it SUPERSEDES the sketch screen below, which is only ever an upper bound:
    #: the sketch samples the drawn ring, while the boundary actually lands inboard at the
    #: isobath. Do not let the weaker proxy overrule the stronger measurement in hand.
    measured_on_mesh: str | None = None


# ═══════════════════════════════════════════════════════════════════════════════
# THE DECLARED CROSSINGS. Every wet reach of the ring must land in exactly one.
# ═══════════════════════════════════════════════════════════════════════════════
CROSSINGS: tuple[Crossing, ...] = (
    Crossing(
        "ocean", "forced", (-74.11, 40.140, -73.44, 40.560), (125.0, 145.0),
        "The whole Atlantic side as ONE reach: the southern limit (lat 40.150), the eastern "
        "limit (lon -73.45) and the northern limit (lat 40.45) carried verbatim from v1, "
        "running straight into ⭐ THE closure — the -10 m isobath's easternmost point in "
        "the Sandy Hook section, north to Rockaway Point. ⚠️ These are NOT separable "
        "declarations: the ring is continuously below -0.5 m from the south-west corner "
        "round to Rockaway Point, so any attempt to box the closure on its own leaves a "
        "reach straddling two boxes. Most of this length is not load-bearing — "
        "create_active(zmin=mask_zmin) trims the domain at the -10 m isobath long before "
        "the region is applied — but the closure at its north end is, which is why the cut "
        "is AT the isobath's turn: closing before it let create_boundary trace the isobath "
        "north-west into Lower Bay, the exact tangle v1.5 exists to remove.",
        measured_on_mesh="build_naccs_boundary.py --report-only on the frozen v1 mesh: "
        "532 ADCIRC points → 151 within 2 km → 92 after the dry and open-coast depth "
        "screens; max gap 2.76 km, 95.6% within 2 km, support sha16 21f967f9798a6945. "
        "v1.5 inherits this arm unchanged, so the mesh figure stands and the ring-sampled "
        "one below is only an upper bound on it.",
    ),
    Crossing(
        "rockaway_inlet", "closed", (-73.990, 40.540, -73.925, 40.590), (2.0, 4.0),
        "Rockaway Inlet — the entrance to Jamaica Bay. CLOSED, which is how 'Jamaica Bay is "
        "excluded' is actually implemented. ⚠️ This walls off the Jamaica Bay tidal prism. "
        "Defensible because that prism exchanges with the OCEAN through this inlet, not "
        "with Lower Bay, so it is not part of the water v1.5 is about — but it is a real "
        "cut through 3 km of -10 m water and must be demoted explicitly, not overlooked.",
    ),
    Crossing(
        "narrows", "forced", (-74.065, 40.596, -74.024, 40.615), (1.0, 3.0),
        "⭐ FORCED CUT. Verrazzano Narrows — carries the Upper Bay + Hudson tidal prism, "
        "which is why the flux cross-section just inside it is what makes the relocation "
        "auditable against literature rather than merely asserted.",
    ),
    Crossing(
        "arthur_kill", "forced", (-74.272, 40.492, -74.228, 40.512), (1.0, 3.0),
        "⭐ FORCED CUT at the Arthur Kill MOUTH (Ward Point / Perth Amboy). ⚠️ The wet ring "
        "here spans SEVERAL segments, not the one labelled 'arthur_kill' — the drawn ring "
        "runs through water from the Ward Point shore round to the Perth Amboy side.",
    ),
    Crossing(
        "raritan", "discharge", (-74.308, 40.500, -74.292, 40.518), (0.3, 1.2),
        "The tidal Raritan River, cut at the domain's west limit. 🔴 'discharge', NOT "
        "'forced': this cut takes a river inflow and must be covered by a "
        "no_waterlevel_box, because an imposed ocean level across a tidal river PUMPS it "
        "— the mirror of the Navesink drain. It therefore carries no NACCS requirement. "
        "⚠️ This is the crossing previously mis-recorded as the 1.79 km segment to its "
        "south, which is dry ground (+5.8 to +22 m) from end to end; the inflow point "
        "derived from that segment's midpoint (-74.2920, 40.4905) sits at +8.9 m on land.",
    ),
)

#: Vertices v1.5 inherits VERBATIM from region_v1_monmouth.geojson. A moved vertex here
#: makes v1 and v1.5 incomparable on the open coast for no gain, so they are pinned.
V1_INHERITED = {
    "A_sw_south_limb": (-74.09596, 40.15037),
    "B_se_corner": (-73.45000, 40.15000),
    "O_w_limit_south": (-74.28000, 40.38000),
    "P_notch_east": (-74.09289, 40.38034),
}

#: v1's southern limit. v1.5 keeps it, so the two domains share a southern boundary.
SOUTH_LIMIT_LAT = 40.150


# ── geometry helpers ────────────────────────────────────────────────────────────


def _km(p, q) -> float:
    return math.hypot(
        (q[1] - p[1]) * 111.320,
        (q[0] - p[0]) * 111.320 * math.cos(math.radians((p[1] + q[1]) / 2)),
    )


def _in_box(lon, lat, box) -> bool:
    return box[0] <= lon <= box[2] and box[1] <= lat <= box[3]


def load_ring() -> list[tuple[float, float]]:
    """The drawn ring, WITHOUT the repeated closing vertex."""
    d = json.loads(DRAWN.read_text())
    feats = d["features"]
    if len(feats) != 1:
        raise SystemExit(f"🔴 {DRAWN.name} holds {len(feats)} features; expected exactly 1")
    geom = feats[0]["geometry"]
    if geom["type"] != "Polygon":
        raise SystemExit(f"🔴 geometry is {geom['type']}, expected Polygon")
    if len(geom["coordinates"]) != 1:
        raise SystemExit("🔴 polygon has interior rings; the region must be simply connected")
    ring = [tuple(c) for c in geom["coordinates"][0]]
    return ring


# ── the elevation stack, exactly as build_static will read it ───────────────────


def open_stack():
    """(name, reader, zmin) per tier, top wins — resolved from the SAME declarations
    build_static uses, so this cannot drift from the model's own bed."""
    import rasterio
    import yaml

    from nj_sfincs.config import BaseConfig

    catalog = yaml.safe_load((ROOT / "data" / "data_catalog.yml").read_text())
    stack = []
    for tier in BaseConfig().elevation():
        name = tier.get("elevation") or tier.get("elevtn")
        entry = catalog.get(name)
        if entry is None:
            print(f"[warn] '{name}' is not in data_catalog.yml — tier skipped")
            continue
        path = ROOT / "data" / entry["uri"]
        if not path.exists():
            print(f"[warn] '{name}' -> {path} is missing — tier skipped")
            continue
        stack.append((name, rasterio.open(path), tier.get("zmin")))
    return stack


def sample_bed(stack, lon, lat) -> tuple[float, str]:
    """Bed elevation and the tier that supplied it. Mirrors hydromt's top-wins merge,
    including the per-tier `zmin` screen (which is why nj_10ft_dem cannot supply a bed
    below +0.001 m even where it is the only source with data)."""
    from rasterio.warp import transform as warp_transform

    for name, src, zmin in stack:
        x, y = lon, lat
        if src.crs is not None and src.crs.to_epsg() not in (4326, 4269, None):
            xs, ys = warp_transform("EPSG:4326", src.crs, [lon], [lat])
            x, y = xs[0], ys[0]
        try:
            v = next(src.sample([(x, y)]))[0]
        except (StopIteration, ValueError, IndexError):
            continue
        if v is None or not np.isfinite(v) or v < -9000:
            continue
        v = float(v)
        if zmin is not None and v < zmin:
            continue
        return v, name
    return float("nan"), "NONE"


def walk_ring(ring, stack):
    """Sample the closed ring at ~STEP_M. Returns (lon, lat, z, source) per sample."""
    out = []
    for i in range(len(ring) - 1):
        p, q = ring[i], ring[i + 1]
        seg_km = _km(p, q)
        n = max(2, int(round(seg_km * 1000.0 / STEP_M)))
        for k in range(n):  # right-open: the next segment supplies the shared vertex
            t = k / n
            lon = p[0] + (q[0] - p[0]) * t
            lat = p[1] + (q[1] - p[1]) * t
            z, src = sample_bed(stack, lon, lat)
            out.append((lon, lat, z, src))
    return out


def wet_reaches(samples):
    """Contiguous runs of bed < WET_Z, wrapping around the closed ring."""
    n = len(samples)
    wet = [np.isfinite(s[2]) and s[2] < WET_Z for s in samples]
    if all(wet):
        return [list(range(n))]
    start = next(i for i in range(n) if not wet[i])
    reaches, cur = [], []
    for j in range(n):
        i = (start + j) % n
        if wet[i]:
            cur.append(i)
        elif cur:
            reaches.append(cur)
            cur = []
    if cur:
        reaches.append(cur)
    return reaches


def load_bearing(samples, idx) -> list[int]:
    """The samples of a reach where the RING ITSELF will be the boundary.

    ⭐ `create_active(zmin=MASK_ZMIN)` deactivates everything deeper than the boundary
    isobath BEFORE the region clip, so where the ring runs over water deeper than
    MASK_ZMIN it decides nothing — the isobath got there first, and the domain edge sits
    inboard of the drawn line. Only the band MASK_ZMIN <= z < WET_Z is load-bearing.

    This is why the 134 km Atlantic limit needs no NACCS support along most of its length,
    and why applying the 2 km rule to the whole wet ring reports a 41 km "gap" out in
    water the model will never contain.
    """
    return [i for i in idx if MASK_ZMIN <= samples[i][2] < WET_Z]


def reach_km(samples, idx) -> float:
    if len(idx) < 2:
        return STEP_M / 1000.0
    return sum(
        _km(samples[idx[k]][:2], samples[idx[k + 1]][:2]) for k in range(len(idx) - 1)
    )


# ── NACCS support ───────────────────────────────────────────────────────────────


def load_support():
    if not SUPPORT.exists():
        return None
    d = json.loads(SUPPORT.read_text())
    return [
        (f["geometry"]["coordinates"][0], f["geometry"]["coordinates"][1],
         f["properties"].get("depth_m"))
        for f in d["features"]
    ]


def nearest_support(pts, lon, lat):
    if not pts:
        return None
    return min(_km((lon, lat), (x, y)) for x, y, _ in pts)


def support_coverage(pts, samples, idx):
    """(fraction within SUPPORT_RADIUS_KM, worst gap in km) along a reach.

    ⚠️ Measured over the reach, not at its centroid: gate 1 is "a support point within
    2.0 km of every mask==2 cell", so the object of interest is the worst point — and on
    a 134 km ocean limit a centroid is not even on the reach.

    ⭐ Reported as a FRACTION as well as a maximum because that is the standard the project
    actually accepts. `build_naccs_boundary.py` measured the inherited Atlantic arm at max
    gap 2.76 km with 95.6% within 2 km, and that arm is adopted. A bare "max <= 2.0 km"
    test would reject the boundary the premier is built on.
    """
    if not pts:
        return None, None
    step = max(1, len(idx) // 400)
    gaps = [nearest_support(pts, samples[i][0], samples[i][1]) for i in idx[::step]]
    within = sum(1 for g in gaps if g <= SUPPORT_RADIUS_KM) / len(gaps)
    return within, max(gaps)


# ── the checks ──────────────────────────────────────────────────────────────────


def check_structure(ring) -> list[str]:
    from shapely.geometry import Polygon

    bad = []
    if ring[0] != ring[-1]:
        bad.append("ring is not closed (first vertex != last)")
    pts = ring[:-1]
    poly = Polygon(pts)
    if not poly.is_valid:
        bad.append("polygon is INVALID (self-intersecting) — hydromt mangles this silently")
    if not poly.exterior.is_ccw:
        bad.append("ring is CLOCKWISE; the project convention is counter-clockwise")
    dupes = [i for i in range(len(pts)) if _km(pts[i], pts[(i + 1) % len(pts)]) < 0.001]
    if dupes:
        bad.append(f"{len(dupes)} zero-length segment(s) at vertex index {dupes}")

    for name, (lon, lat) in V1_INHERITED.items():
        if not any(abs(p[0] - lon) < 1e-5 and abs(p[1] - lat) < 1e-5 for p in pts):
            bad.append(f"v1-inherited vertex {name} {(lon, lat)} is NOT in the drawn ring")

    south = min(p[1] for p in pts)
    if abs(south - SOUTH_LIMIT_LAT) > 0.001:
        bad.append(
            f"southern limit is lat {south:.5f}, not v1's {SOUTH_LIMIT_LAT} — v1.5 is "
            f"supposed to keep it so the two domains share a southern boundary"
        )

    props = json.loads(DRAWN.read_text())["features"][0]["properties"]
    tags = props.get("segments")
    if isinstance(tags, dict) and len(tags) != len(pts):
        bad.append(
            f"the 'segments' property carries {len(tags)} tags for a {len(pts)}-vertex "
            f"ring — STALE, inherited from the generator. Segment tags are not how "
            f"crossings are declared any more (see the module docstring); delete the "
            f"property rather than repairing it."
        )
    return bad


def audit(verbose: bool = False) -> int:
    ring = load_ring()
    pts = ring[:-1]
    print(f"drawn region : {DRAWN.relative_to(ROOT)}")
    print(f"vertices     : {len(pts)}")

    fail = list(check_structure(ring))

    stack = open_stack()
    print(f"bed stack    : {' → '.join(n for n, _, _ in stack)}")
    print(f"walking the ring at {STEP_M:.0f} m …")
    samples = walk_ring(ring, stack)
    perim = sum(_km(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts)))
    print(f"perimeter    : {perim:.2f} km  ({len(samples)} samples)")

    nodata = [s for s in samples if not np.isfinite(s[2])]
    if nodata:
        fail.append(
            f"{len(nodata)} of {len(samples)} ring samples have NO bed in ANY tier of the "
            f"stack. build_static asserts no ACTIVE cell has NoData in the merged bed, so "
            f"this is a build error waiting to happen."
        )

    support = load_support()
    reaches = wet_reaches(samples)
    kept = [r for r in reaches if reach_km(samples, r) >= MIN_REACH_KM]
    dropped = len(reaches) - len(kept)
    print(f"wet reaches  : {len(kept)} at or above {MIN_REACH_KM:.2f} km"
          f"  ({dropped} shorter, ignored)\n")

    hdr = (f"{'wet reach':>9} {'km':>6} {'min z':>7} {'declared as':<15} {'kind':<7} "
           f"{'NACCSmax':>8}  bed source(s)")
    print(hdr)
    print("─" * len(hdr))

    claimed: dict[str, list] = {c.name: [] for c in CROSSINGS}
    for r in kept:
        lo = [samples[i][0] for i in r]
        la = [samples[i][1] for i in r]
        zs = [samples[i][2] for i in r]
        srcs = sorted({samples[i][3] for i in r})
        km = reach_km(samples, r)
        mid = (float(np.mean(lo)), float(np.mean(la)))

        hits = [c for c in CROSSINGS
                if all(_in_box(x, y, c.box) for x, y in zip(lo, la))]
        loose = [c for c in CROSSINGS if _in_box(mid[0], mid[1], c.box)]

        # ⚠️ Reported over the LOAD-BEARING band only — see load_bearing(). The gap out in
        # water deeper than MASK_ZMIN is not a gap in anything the model will contain.
        lb_idx = load_bearing(samples, r)
        _, d_naccs = support_coverage(support, samples, lb_idx) if lb_idx else (None, None)
        naccs = f"{d_naccs:.2f}" if d_naccs is not None else "     —"

        if len(hits) == 1:
            c = hits[0]
            claimed[c.name].append(km)
            name, kind = c.name, c.kind
        elif len(hits) > 1:
            name, kind = "AMBIGUOUS", "🔴"
            fail.append(
                f"a {km:.2f} km wet reach near {mid[0]:.4f},{mid[1]:.4f} falls inside "
                f"{len(hits)} declared boxes ({', '.join(c.name for c in hits)}) — the "
                f"boxes overlap and the crossing cannot be attributed"
            )
        else:
            name, kind = ("PARTIAL" if loose else "UNDECLARED"), "🔴"
            fail.append(
                f"UNDECLARED water crossing: {km:.2f} km of ring below {WET_Z} m centred "
                f"on {mid[0]:.4f},{mid[1]:.4f} (min bed {np.nanmin(zs):+.2f} m, bed from "
                f"{'+'.join(srcs)}), nearest NACCS {naccs} km. "
                + (f"It STRADDLES the '{loose[0].name}' box rather than sitting inside it — "
                   f"widen that box, do not delete this check. "
                   if loose else
                   "create_boundary will put mask==2 here and nothing will demote it. ")
                + "Declare it in CROSSINGS as 'forced' or 'closed'."
            )

        print(f"{km:9.2f} {km:6.2f} {np.nanmin(zs):+7.2f} {name:<15} {kind:<7} "
              f"{naccs:>8}  {'+'.join(srcs)}")

        if verbose:
            for i in r[:: max(1, len(r) // 8)]:
                s = samples[i]
                print(f"            {s[0]:9.5f},{s[1]:8.5f}  {s[2]:+7.2f}  {s[3]}")

    print()
    for c in CROSSINGS:
        got = sum(claimed[c.name])
        lo, hi = c.km_bracket
        mark = "✅" if lo <= got <= hi else "🔴"
        n = len(claimed[c.name])
        print(f"{mark} {c.name:<15} {c.kind:<7} {got:6.2f} km wet "
              f"in {n} reach(es), bracket [{lo}, {hi}]")
        if not lo <= got <= hi:
            fail.append(
                f"declared crossing '{c.name}' has {got:.2f} km of wet ring, outside its "
                f"bracket [{lo}, {hi}] km. Either the ring moved or the bracket is wrong — "
                f"decide which, do not widen the bracket reflexively."
            )

    # ── what a forced cut is actually built on, per reach ────────────────────────
    print()
    for r in kept:
        srcs = {samples[i][3] for i in r}
        lo = [samples[i][0] for i in r]
        la = [samples[i][1] for i in r]
        km = reach_km(samples, r)
        c = next((c for c in CROSSINGS
                  if all(_in_box(x, y, c.box) for x, y in zip(lo, la))
                  and c.kind in ("forced", "discharge")), None)
        if c is None:
            continue
        where = f"{float(np.mean(lo)):.4f},{float(np.mean(la)):.4f}"

        if srcs <= {"gmrt_nj"}:
            fail.append(
                f"{c.kind} crossing '{c.name}': a {km:.2f} km reach at {where} gets its bed "
                f"ONLY from gmrt_nj — the ~50 m offshore tail, the coarsest tier in the "
                f"stack. Every tier above it is NoData there. A forced cut is where the "
                f"whole domain's exchange is imposed; it is the last place a 50 m bed "
                f"belongs."
            )

        if c.kind == "discharge":
            print(f"[note] discharge crossing '{c.name}': no NACCS requirement — it takes "
                  f"a river inflow, and a no_waterlevel_box must cover it so no ocean "
                  f"level is imposed across the river.")
            continue
        lb = load_bearing(samples, r)
        if not lb:
            print(f"[note] forced crossing '{c.name}': the {km:.2f} km reach at {where} is "
                  f"entirely deeper than {MASK_ZMIN} m — create_active trims it before the "
                  f"region applies, so it carries no support requirement.")
            continue
        frac, gap = support_coverage(support, samples, lb)
        if frac is None:
            continue
        print(f"[support] {c.name:<15} {reach_km(samples, lb):6.2f} km load-bearing  "
              f"{frac * 100:5.1f}% within {SUPPORT_RADIUS_KM} km  max {gap:.2f} km")
        if frac < SUPPORT_MIN_FRAC or gap > SUPPORT_MAX_GAP_KM:
            if c.measured_on_mesh:
                print(f"[note] '{c.name}' misses the SKETCH screen "
                      f"({frac * 100:.1f}% within {SUPPORT_RADIUS_KM} km) but has a real "
                      f"mesh measurement, which supersedes it: {c.measured_on_mesh}")
                continue
            fail.append(
                f"forced crossing '{c.name}': of the {reach_km(samples, lb):.2f} km that "
                f"is load-bearing, {frac * 100:.1f}% is within {SUPPORT_RADIUS_KM} km of a "
                f"NACCS save point (need {SUPPORT_MIN_FRAC * 100:.0f}%) and the worst gap "
                f"is {gap:.2f} km (ceiling {SUPPORT_MAX_GAP_KM} km). "
                f"⚠️ This is the SKETCH screen, NOT gate 1 — the real one is measured "
                f"against mask==2 cells on a built mesh — so read it as an upper bound on "
                f"the support that will survive build_naccs_boundary.py. A failure here "
                f"is a failure there too."
            )

    print()
    if fail:
        print("🔴 PROBLEMS:")
        for b in fail:
            print(f"   - {b}")
        return 1
    print("✅ the drawn region passes: closed, valid, CCW, v1 anchors intact, and every "
          "wet crossing is declared.")
    return 0


def plot() -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import rasterio
    from matplotlib.patches import Rectangle
    from rasterio.windows import from_bounds

    ring = load_ring()
    stack = open_stack()
    samples = walk_ring(ring, stack)

    bounds = (-74.36, 40.05, -73.40, 40.66)
    fig, ax = plt.subplots(figsize=(13, 9), dpi=160)
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#eef3f7")

    vrt = ROOT / "data" / "elevation" / "cudem_nj.vrt"
    if vrt.exists():
        with rasterio.open(vrt) as s:
            win = from_bounds(*bounds, transform=s.transform)
            z = s.read(1, window=win, out_shape=(1200, 1800), masked=True).filled(np.nan)
        dlon = np.linspace(bounds[0], bounds[2], z.shape[1])
        dlat = np.linspace(bounds[3], bounds[1], z.shape[0])
        ax.contour(dlon, dlat, z, levels=[0], colors=["#a8a496"], linewidths=0.6, zorder=2)
        ax.contour(dlon, dlat, z, levels=[-10], colors=["#4a3aa7"], linewidths=0.7, zorder=2)

    wet = np.array([np.isfinite(s[2]) and s[2] < WET_Z for s in samples])
    lo = np.array([s[0] for s in samples])
    la = np.array([s[1] for s in samples])
    ax.plot(np.append(lo, lo[0]), np.append(la, la[0]), color="#0b0b0b", lw=1.4,
            zorder=4, label="region ring (dry)")
    ax.scatter(lo[wet], la[wet], s=6, color="#2a78d6", zorder=5, label="ring over water")

    for c in CROSSINGS:
        if c.name == "ocean_limits":
            continue
        col = "#e34948" if c.kind == "forced" else "#8a8980"
        ax.add_patch(Rectangle((c.box[0], c.box[1]), c.box[2] - c.box[0],
                               c.box[3] - c.box[1], fill=False, ec=col, lw=1.6,
                               zorder=6))
        ax.annotate(f"{c.name} ({c.kind})", (c.box[0], c.box[3]), fontsize=7,
                    color=col, textcoords="offset points", xytext=(2, 3), zorder=6)

    ax.set_xlim(bounds[0], bounds[2])
    ax.set_ylim(bounds[1], bounds[3])
    ax.set_aspect(1.0 / math.cos(math.radians(40.4)))
    ax.set_title("v1_5_raritan — the DRAWN ring, its wet reaches, and the declared "
                 "crossings", fontsize=12, loc="left", pad=10)
    ax.set_xlabel("longitude", fontsize=9, color="#52514e")
    ax.set_ylabel("latitude", fontsize=9, color="#52514e")
    for s in ax.spines.values():
        s.set_color("#d5d4cc")
    ax.tick_params(colors="#52514e", labelsize=8)
    ax.legend(loc="lower left", frameon=True, facecolor="#fcfcfb", edgecolor="#d5d4cc",
              fontsize=8.5)
    FIG.mkdir(parents=True, exist_ok=True)
    p = FIG / "region_v1_5_raritan.png"
    fig.savefig(p, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"[plot] {p}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--plot", action="store_true")
    ap.add_argument("--verbose", action="store_true", help="dump samples per wet reach")
    args = ap.parse_args()

    rc = audit(verbose=args.verbose)
    if args.plot:
        plot()
    raise SystemExit(rc)


if __name__ == "__main__":
    main()
