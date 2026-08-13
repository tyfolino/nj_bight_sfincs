"""Build the quadtree SFINCS model, in pure functions.

* ``build_static``  — grid, elevation, mask, boundary, obs points, roughness, subgrid,
  written once into a template dir.
* ``add_forcing``   — window + physics flags and every compound forcing (no waves).
* ``add_waves``     — the SnapWave block.
* ``finalize``      — release handles, write, patch sfincs.inp, write the ASCII forcing.

Everything geographic comes from the DOMAIN REGISTRY (``domain.py``). Nothing in this
module is a coordinate literal; what is left here is domain-INDEPENDENT and stays right
wherever the domain moves.
"""

from __future__ import annotations

import gc
import os
import shutil
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
import xarray as xr
from hydromt import log
from hydromt_sfincs import SfincsModel
from shapely.geometry import Point

from . import domain as _domain
from .config import ROOT, BaseConfig, WaveConfig

# HDF5/netCDF file locking off before any netCDF-backed write on /cache (a failed lock
# surfaces as a misleading "NetCDF: Permission denied").
os.environ.setdefault("HDF5_USE_FILE_LOCKING", "FALSE")

# Thickness of the seaward ring promoted to SnapWave boundary when the wave domain is
# decoupled: cells within this many metres of the deep cut become msk==2. Wide enough to
# give a contiguous ring on a 200 m quadtree edge.
SNAPWAVE_BND_RING = 5.0

# A free-outflow (Neumann) BC on water deeper than this is a DRAIN, not a boundary.
OUTFLOW_MAX_DEPTH = -1.0

# ⭐ THE TOP OF THE OUTFLOW GATE. Every DRY edge cell becomes a free-outflow boundary,
# however high it sits.
#
# This used to be +2 m, and that left the domain edge DISJOINTED: measured along the
# 21.5 km Staten Island shore, only 42% of the edge cells fell in the -1..+2 m window,
# so 209 of 411 stayed mask==1 and the boundary came out as a dashed line through ground
# that had been drawn as one clean shoreline. The bed there runs to +26 m; the inland
# limits run to +80 m.
#
# Raising it is safe in the one direction that has ever bitten: the drain. `zmin` is
# still OUTFLOW_MAX_DEPTH, and 5c re-seals any outflow cell that lands on water, so the
# Navesink failure mode cannot return. On genuinely dry ground a Neumann face is inert
# until water reaches it, and when water DOES reach it, letting the flood leave is more
# physical than ponding it against an artificial wall — which on Staten Island's south
# shore would push water back into the Raritan Bay lobe this domain exists to measure.
OUTFLOW_MAX_BED = 1.0e4
# A cell the model calls (near-)land while a real survey says there is water this deep
# beneath it has been PAVED OVER by a failed lidar return.
PAVED_BED_LAND = -0.5
PAVED_SURVEY_WATER = -2.0

# Latitude band width for the water-level boundary profile. 0.05 deg (~5.6 km) is short
# enough to read at a glance and fine enough that a 2–3 km intrusion lands in its own band
# instead of being averaged into 40 km of open coast.
BC_REPORT_BAND_DEG = 0.05


def _open_coast_max_y() -> float:
    """Northing above which the coast is no longer open Atlantic.

    Incident SnapWave energy must only enter along the open-ocean edge. North of a spit
    tip the "boundary" wraps into an enclosed harbour corner, and leaving boundary cells
    there lets waves run away into it — the ~1e13 blow-up. Support points are likewise
    taken only from below this line.

    ``inf`` means the whole seaward edge is open coast.
    """
    y = _domain.active().open_coast_max_y
    return float("inf") if y is None else y


def _face_xy(sf):
    return sf.quadtree_grid.data.grid.face_coordinates.T


def _inactive_components(sf, mask):
    """Split the inactive cells into (ocean-connected mass, interior holes).

    "Ocean-connected" is just the LARGEST connected component of ``mask == 0``. That
    single blob is the shelf plus all the dry land, which wrap round each other
    continuously. Anything else is an inactive island sitting inside the model.

    Returns ``(ocean, hole)`` boolean arrays over faces.
    """
    from scipy.sparse.csgraph import connected_components

    inactive = mask == 0
    if not inactive.any():
        z = np.zeros(len(mask), dtype=bool)
        return z, z
    adj = sf.quadtree_grid.data.grid.face_face_connectivity
    idx = np.flatnonzero(inactive)
    _, lab = connected_components(adj[inactive][:, inactive], directed=False)
    labels, counts = np.unique(lab, return_counts=True)
    main = labels[np.argmax(counts)]
    ocean = np.zeros(len(mask), dtype=bool)
    hole = np.zeros(len(mask), dtype=bool)
    ocean[idx[lab == main]] = True
    hole[idx[lab != main]] = True
    return ocean, hole


def _fill_inactive_holes(sf, mask, zb) -> np.ndarray:
    """Activate any inactive island that is not connected to the ocean/land mass.

    A depth threshold is a statement about ELEVATION, but the mask it produces is a
    statement about TOPOLOGY, and the two disagree wherever the isobath reaches inside the
    model. Measured once at ``mask_zmin = -10``: 153 such cells, 145 of them in an inlet
    throat scoured to −14.78 m. They do two things, both bad. As islands they block
    conveyance through the one cross-section that matters. As mask edges they make
    ``create_boundary`` impose the open-ocean water level AROUND them, kilometres inside
    an inlet.

    So: fill them. This is deliberately topological rather than geometric — it needs no
    hand-drawn box, and it therefore keeps working when the domain moves, when a carve
    deepens a channel, or when ``mask_zmin`` changes. It cannot on its own fix an
    intrusion that stays CONNECTED to the sea (a scoured inlet gorge is the case in
    point); that is what ``always_active_boxes_ll`` is for, and the two are used together.

    Runs BEFORE ``create_boundary`` — filling afterwards would leave the boundary cells
    the holes had already spawned.
    """
    _, hole = _inactive_components(sf, mask)
    n = int(hole.sum())
    if not n:
        print("[mask] no interior inactive holes")
        return mask
    fx, fy = _face_xy(sf)
    mask = mask.copy()
    mask[hole] = 1
    print(
        f"[mask] filled {n} interior inactive cells (deepest {zb[hole].min():+.2f} m; "
        f"x {fx[hole].min():.0f}-{fx[hole].max():.0f}, "
        f"y {fy[hole].min():.0f}-{fy[hole].max():.0f}) — an inactive island inside "
        f"the model blocks conveyance AND spawns a water-level BC around itself"
    )
    return mask


def _drop_detached_active_islands(sf, mask, zb) -> np.ndarray:
    """Deactivate ACTIVE patches not connected to the main domain.

    ── THE MIRROR OF ``_fill_inactive_holes`` ────────────────────────────────────
    That function fixes an INACTIVE island inside active water. This fixes an ACTIVE
    island inside inactive water — an offshore shoal that rises above ``mask_zmin``
    while everything around it is deeper, so ``create_active`` leaves a detached
    patch floating in the sea.

    ``create_boundary`` then rings each one with ``mask==2``, and the result is a
    closed loop of imposed ocean water level with **no hydraulic connection to the
    model at all**. It cannot influence the solution, it inflates the boundary-cell
    count, and — the real cost — it makes the boundary set look wrong in exactly the
    way a genuine intrusion looks wrong, so the one alarm that matters gets ignored.

    Found on v1.5 as two floating rings, off Long Branch and off Sandy Hook. They
    passed every existing invariant: each cell was wet, and each sat inside a declared
    arm box, because an arm box is a rectangle and a shoal 3 km offshore is still
    inside it. **Geometry could not catch this; topology can.**

    ⚠️ Keeps the LARGEST active component only. That is right for a single-basin
    coastal domain and would be wrong for one that legitimately contains two
    disconnected water bodies — if such a domain is ever added, this needs a declared
    component count rather than an argmax.
    """
    active = mask > 0
    if not active.any():
        return mask
    from scipy.sparse.csgraph import connected_components

    adj = sf.quadtree_grid.data.grid.face_face_connectivity
    idx = np.flatnonzero(active)
    _, lab = connected_components(adj[active][:, active], directed=False)
    labels, counts = np.unique(lab, return_counts=True)
    if len(labels) == 1:
        print("[mask] active domain is a single connected component")
        return mask
    main = labels[np.argmax(counts)]
    detached = np.zeros(len(mask), dtype=bool)
    detached[idx[lab != main]] = True
    fx, fy = _face_xy(sf)
    n_bc = int((mask[detached] == 2).sum())
    print(
        f"[mask] DROPPED {int(detached.sum())} active cells in "
        f"{len(labels) - 1} detached island(s) — {n_bc} of them were water-level BC "
        f"cells forming closed rings with no connection to the domain. "
        f"Largest kept component: {counts.max():,} cells."
    )
    for lb, ct in zip(labels, counts):
        if lb == main:
            continue
        sel = np.zeros(len(mask), dtype=bool)
        sel[idx[lab == lb]] = True
        print(f"       island {ct:>5} cells at x {fx[sel].mean():.0f} "
              f"y {fy[sel].mean():.0f}, bed {zb[sel].min():+.2f}..{zb[sel].max():+.2f} m")
    mask = mask.copy()
    mask[detached] = 0
    return mask


def _assert_boundary_is_continuous(sf, mask, dom) -> None:
    """A water-level boundary should be a few continuous runs, not confetti.

    ⚠️ MEASURED BY PROXIMITY, NOT BY EDGE-ADJACENCY. The first version of this used
    ``connected_components`` on ``face_face_connectivity`` and reported **887**
    components over a boundary that is visibly a handful of runs. The reason is
    geometric, not physical: the ocean arm follows a rugged isobath diagonally across
    a quadtree, so it climbs as a STAIRCASE, and staircase cells touch at CORNERS.
    Corner contact is not edge adjacency, so every diagonal step severed the run.

    Clustering on distance instead is immune to that: two boundary cells belong to the
    same run if they are within a few cell widths of each other, however they touch.
    """
    import numpy as np
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    from scipy.spatial import cKDTree

    bc = mask == 2
    if not bc.any():
        return
    fx, fy = _face_xy(sf)
    pts = np.c_[fx[bc], fy[bc]]

    # Link radius from the ACTUAL local spacing, so this works at any refinement:
    # the median nearest-neighbour distance among boundary cells, x2.5 for the
    # diagonal-plus-one-level-change case. Not a knife edge -- anything from ~1.6x
    # to ~4x gives the same component count here.
    tree = cKDTree(pts)
    d1, _ = tree.query(pts, k=min(2, len(pts)))
    step = float(np.median(d1[:, -1])) if pts.shape[0] > 1 else 1.0
    radius = 2.5 * step

    pairs = np.array(list(tree.query_pairs(radius))) if len(pts) > 1 else np.empty((0, 2), int)
    if len(pairs):
        g = coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])),
                       shape=(len(pts), len(pts)))
        n_comp, lab = connected_components(g, directed=False)
    else:
        n_comp, lab = len(pts), np.arange(len(pts))
    counts = np.bincount(lab)
    n_arms = max(1, len([a for a in dom.boundary_arms if a.btype == "waterlevel"]))
    ceiling = 4 * n_arms
    biggest = ", ".join(f"{c:,}" for c in sorted(counts)[::-1][:6])
    print(f"[bc] continuity: {n_comp} run(s) over {n_arms} declared arm(s) "
          f"(link radius {radius:.0f} m); largest: {biggest}")
    if n_comp > ceiling:
        raise AssertionError(
            f"water-level boundary fragmented into {n_comp} runs over {n_arms} "
            f"declared arm(s) (ceiling {ceiling}). A boundary that is not a few "
            f"continuous runs is tracing something -- a shoal rim, a dredged channel, "
            f"or a bay mouth it should have cut straight across. Plot it with "
            f"scripts/plot_waterlevel_boundary.py before changing this number."
        )


def _report_waterlevel_boundary(sf, mask, zb) -> None:
    """Print the ENTIRE water-level boundary, as latitude bands, on every build.

    ── WHY THIS IS A REPORT AND NOT AN ASSERT ───────────────────────────────
    Three times the water-level BC landed somewhere it had no business being: a Navesink
    cut face, a Manahawkin bay cross-section, and 2.6 km inside the Barnegat Inlet throat.
    Each was found months later by chasing a bad number downstream. The obvious response
    is a predicate that catches the CLASS. Every candidate was tried and none works —
    recorded here so they are not re-attempted:

      predicate                       why it fails
      -----------------------------   -----------------------------------------
      y < open_coast_max_y            a LATITUDE cut. Catches a northern corner only;
                                      an inlet gorge far to the south passes clean.
      seaward of the barrier axis     an inlet IS the gap in the barrier, so the gorge
                                      cells straddle the axis by definition. Ambiguous
                                      exactly where it must discriminate.
      near the region edge            no — the legitimate BC line is the mask_zmin
                                      isobath, which lies well INSIDE the region.
      detached connected component    no — a scoured gorge intrusion stays CONNECTED
                                      to the sea (see _fill_inactive_holes).
      cell count vs a baseline        detects CHANGE, not WRONGNESS. The gorge was
                                      present in every run for a month and the mesh
                                      fingerprint was stable throughout.
                                      Stable-and-wrong is invisible to a baseline.

    "Inside an inlet" is precisely where geometry stops discriminating. What all three
    defects DID share is that nobody ever looked at the BC set as a whole. So: display it,
    every build, and let a person read it. Visibility, not validation.

    ⚠️ A DOMAIN THAT DECLARES ``boundary_arms`` GETS BOTH. The whitelist is the assert
    this function could never be; this stays because a cell can be inside its arm box and
    still be in the wrong place within it.

    ── HOW TO READ THE OUTPUT ───────────────────────────────────────────────
    One row per band of latitude, north to south. **The W-edge column is the whole point.**
    The legitimate boundary is an isobath running alongshore, so on the open coast the
    west edge barely moves from band to band. An intrusion — an inlet throat, a dredged
    channel, a bay deeper than ``mask_zmin`` — shows up as a band whose west edge jumps
    INLAND of its neighbours. Read the jump, not the cell count: 193 cells is small beside
    a 2,000-cell arc and still invalidated a whole campaign.

    ⚠️ dW is a FIRST DIFFERENCE against the band to the north, so an intruded band
    distorts its neighbour's number too. Treat a jump as "look here", not as a
    measurement, and expect one intrusion to perturb two rows.

    ⚠️ Do not "improve" this by grouping cells with ``connected_components`` on the mesh
    ``face_face_connectivity`` — tried, and it fragments the boundary into hundreds of
    single-cell groups. The BC line is one cell wide and ragged, so consecutive cells
    frequently touch only at a CORNER and are not edge-adjacent.
    """
    import pyproj

    bc = mask == 2
    n = int(bc.sum())
    if not n:
        print("[bc] no water-level boundary cells")
        return

    fx, fy = _face_xy(sf)
    tf = pyproj.Transformer.from_crs(sf.crs, 4326, always_xy=True)
    lon, lat = tf.transform(fx[bc], fy[bc])
    z = zb[bc]

    band = np.floor(lat / BC_REPORT_BAND_DEG).astype(int)
    print(
        f"[bc] {n} water-level boundary cells, alongshore profile "
        f"({BC_REPORT_BAND_DEG:g} deg bands, north to south). READ THE W-EDGE COLUMN: "
        f"a band whose west edge jumps inland of its neighbours is an intrusion "
        f"(see _report_waterlevel_boundary)."
    )
    print(
        f"     {'lat band':<14} {'cells':>6}  {'W edge':>9} {'E edge':>9}  "
        f"{'dW km':>7}  {'z range':>15}"
    )
    prev_w = None
    for b in sorted(set(band.tolist()), reverse=True):
        s = band == b
        w, e = float(lon[s].min()), float(lon[s].max())
        dw = (
            ""
            if prev_w is None
            else f"{(w - prev_w) * 111_320 * np.cos(np.radians(lat[s].mean())) / 1e3:+7.2f}"
        )
        prev_w = w
        print(
            f"     {b * BC_REPORT_BAND_DEG:6.2f}-{(b + 1) * BC_REPORT_BAND_DEG:6.2f} "
            f"{int(s.sum()):6d}  {w:9.4f} {e:9.4f}  {dw:>7}  "
            f"{z[s].min():+7.2f}..{z[s].max():+6.2f}"
        )


def _report_boundary_arms(sf, mask, zb) -> None:
    """Per-arm boundary-condition census. Prints even when the whitelist passes.

    Aggregate coverage hides "0 cells on Arthur Kill" — the failure mode that matters most
    on a domain whose entire claim is that two short cross-sections carry the exchange.
    """
    arms = _domain.active().boundary_arms
    if not arms:
        return
    fx, fy = _face_xy(sf)
    print(f"[bc] {len(arms)} declared boundary arm(s):")
    for arm in arms:
        code = 2 if arm.btype == "waterlevel" else 3
        xmin, ymin, xmax, ymax = arm.box
        sel = (mask == code) & (fx > xmin) & (fx < xmax) & (fy > ymin) & (fy < ymax)
        n = int(sel.sum())
        zr = f"{zb[sel].min():+.2f}..{zb[sel].max():+.2f}" if n else "—"
        print(
            f"     {arm.name:<16} {arm.btype:<10} {n:6d} cells "
            f"[{arm.min_cells}..{arm.max_cells}]   z {zr}"
        )


def _check_domain_invariants(
    sf, mask, zb, *, allow_waterlevel_zones: "frozenset[str]" = frozenset()
) -> None:
    """Refuse to ship a domain carrying any of the defects below.

    All of these were INFRASTRUCTURE, not physics — a region polygon, an elevation tier, a
    depth threshold — which is exactly why an exhaustive elimination of every *physical*
    lever (wind, friction, mesh resolution, wave convergence, channel dredging) came back
    null for weeks. Nobody suspects a boundary condition. So we assert them instead.

    1. NO FREE-OUTFLOW BC ON OPEN WATER. A region polygon chopped the Navesink in half
       mid-channel and hydromt put a free-outflow BC on the 5 m-deep cut face. The model
       drained 92.5% of the estuary's entire inflow out of that hole, one-way, in 100% of
       timesteps, from the first hour. THIS ONE CHECK WOULD HAVE CAUGHT IT ON DAY ONE.

    2. NO PAVED-OVER CHANNELS. Green lidar returns the WATER SURFACE in turbid water,
       which looks like land; ranked above the real bed it sealed Shark River Inlet, and
       the whole estuary behind it sat at exactly +0.00 m through Hurricane Sandy while
       the ocean 1.8 km away reached +2.9 m. Checked against the eHydro survey wherever
       that survey has data.

    3. NO INTERIOR INACTIVE ISLANDS. The post-condition on ``_fill_inactive_holes``.
       Cheap, and it fails loudly if the fill is ever removed or outrun.

    4. NO IMPOSED OCEAN LEVEL WHERE THE DOMAIN DECLARES THERE MUST NOT BE ONE. See
       ``domain.NoWaterLevelBox``.

    5. THE BOUNDARY-ARM WHITELIST. Every ``mask==2`` cell inside exactly one declared arm;
       every one of them WET; per-arm counts inside their declared bracket. This is the
       one invariant that catches the class rather than the instance — see
       ``domain.BoundaryArm``.

    6. NO NODATA UNDER AN ACTIVE CELL. A merged bed with a hole in it is not a shallow
       cell, it is an undefined one, and the elevation stack has NJ-only tiers that any
       domain reaching across a state line falls straight through.

    7. NO ACTIVE CELL IN A DECLARED LAND BOX.
    """
    import rasterio

    from .config import DATA

    dom = _domain.active()
    fx, fy = _face_xy(sf)
    fail = []

    n_wet_out = int(((mask == 3) & (zb < OUTFLOW_MAX_DEPTH)).sum())
    if n_wet_out:
        fail.append(
            f"{n_wet_out} free-outflow cells (mask=3) sit on water below "
            f"{OUTFLOW_MAX_DEPTH} m. That is a DRAIN, not a boundary — it is the bug "
            f"that emptied the Navesink."
        )

    _, hole = _inactive_components(sf, mask)
    if hole.any():
        fail.append(
            f"{int(hole.sum())} inactive cells form islands INSIDE the model "
            f"(deepest {zb[hole].min():+.2f} m, around x {fx[hole].mean():.0f} "
            f"y {fy[hole].mean():.0f}). They block conveyance and make "
            f"create_boundary impose an open-ocean level around them."
        )

    # --- 6. NoData under an active cell --------------------------------------
    active_cells = mask > 0
    nodata = active_cells & ~np.isfinite(zb)
    if nodata.any():
        fail.append(
            f"{int(nodata.sum())} ACTIVE cells have no bed elevation at all (NoData in "
            f"the merged DEM), around x {fx[nodata].mean():.0f} y {fy[nodata].mean():.0f}. "
            f"The elevation stack has NJ-only tiers (`nj_10ft_dem`); a domain reaching "
            f"across the state line falls through them to CUDEM/3DEP, and where that has "
            f"no coverage either the cell is undefined rather than shallow."
        )

    # --- 7. land boxes -------------------------------------------------------
    for name, (xmin, ymin, xmax, ymax), why in dom.land_boxes:
        sel = active_cells & (fx > xmin) & (fx < xmax) & (fy > ymin) & (fy < ymax)
        if sel.any():
            fail.append(
                f"{int(sel.sum())} cells are ACTIVE inside the declared land box "
                f"'{name}'. {why}"
            )

    # --- 4. no-waterlevel zones ----------------------------------------------
    for zone in dom.no_waterlevel_boxes:
        xmin, ymin, xmax, ymax = zone.box
        sel = (mask == 2) & (fx > xmin) & (fx < xmax) & (fy > ymin) & (fy < ymax)
        if zone.name in allow_waterlevel_zones:
            # A WAIVED INVARIANT MUST SHOUT. Silence here would recreate exactly the
            # condition this alarm exists to catch, with no trace in the build log.
            print("=" * 78)
            print(f"!! INVARIANT WAIVED: no-waterlevel zone '{zone.name}'")
            print(f"!! {int(sel.sum())} water-level BC cells are being ALLOWED inside it.")
            print(f"!! {zone.why}")
            print("!! This is only legitimate for a DELIBERATE bracketing experiment.")
            print("!! The result is an INADMISSIBLE boundary condition and must never")
            print("!! be reported as a candidate configuration.")
            print("=" * 78)
            continue
        if sel.any():
            fail.append(
                f"{int(sel.sum())} water-level BC cells (mask=2) fall inside the "
                f"no-waterlevel zone '{zone.name}' (deepest {zb[sel].min():+.2f} m). "
                f"{zone.why}"
            )

    # --- 5. the boundary-arm whitelist ---------------------------------------
    if dom.boundary_arms:
        claimed = np.zeros(len(mask), dtype=int)
        for arm in dom.boundary_arms:
            code = 2 if arm.btype == "waterlevel" else 3
            xmin, ymin, xmax, ymax = arm.box
            inbox = (fx > xmin) & (fx < xmax) & (fy > ymin) & (fy < ymax)
            sel = (mask == code) & inbox
            claimed += sel.astype(int)
            n = int(sel.sum())
            if not (arm.min_cells <= n <= arm.max_cells):
                fail.append(
                    f"boundary arm '{arm.name}' has {n} {arm.btype} cells, outside its "
                    f"declared [{arm.min_cells}, {arm.max_cells}]. A count that moves is "
                    f"a different boundary wearing the same arm's name. {arm.why}"
                )
            wet_fail = sel & ~(zb <= arm.max_bed_m)
            if wet_fail.any():
                fail.append(
                    f"boundary arm '{arm.name}': {int(wet_fail.sum())} BC cells sit on "
                    f"bed above {arm.max_bed_m} m (highest {zb[wet_fail].max():+.2f} m). "
                    f"A boundary condition on dry ground is a source term, not a boundary."
                )
        orphan = (mask == 2) & (claimed == 0)
        if orphan.any():
            fail.append(
                f"{int(orphan.sum())} water-level BC cells (mask=2) fall OUTSIDE every "
                f"declared boundary arm, around x {fx[orphan].mean():.0f} "
                f"y {fy[orphan].mean():.0f} (deepest {zb[orphan].min():+.2f} m). The "
                f"boundary must be DECLARED before it can exist — see domain.BoundaryArm."
            )
        overlap = claimed > 1
        if overlap.any():
            fail.append(
                f"{int(overlap.sum())} BC cells fall inside MORE THAN ONE boundary arm "
                f"box. Arms must be disjoint or a per-arm count means nothing."
            )

    # --- 2. paved-over surveyed channels -------------------------------------
    tif = DATA / "elevation" / "ehydro_nj.tif"
    if tif.exists():
        act = mask > 0
        with rasterio.open(tif) as d:
            v = np.array(
                [r[0] for r in d.sample(zip(fx[act].tolist(), fy[act].tolist()))],
                dtype="float64",
            )
            if d.nodata is not None:
                v[v == d.nodata] = np.nan
        v[v < -1e5] = np.nan
        paved = (zb[act] >= PAVED_BED_LAND) & (v < PAVED_SURVEY_WATER)
        if paved.any():
            fail.append(
                f"{int(paved.sum())} active cells are (near-)land in the model "
                f"(bed >= {PAVED_BED_LAND} m) where the eHydro survey sounded water "
                f"below {PAVED_SURVEY_WATER} m. A channel is still paved over."
            )

    if fail:
        raise RuntimeError(
            "[build_static] DOMAIN INVARIANTS FAILED:\n  - " + "\n  - ".join(fail)
        )
    # Do NOT claim the zone invariant held when it was waived — a build log that says "OK"
    # over a deliberately inadmissible domain is how a bracket gets mistaken for a
    # candidate six weeks later.
    zone_claim = (
        "no imposed ocean level in a declared no-waterlevel zone"
        if not allow_waterlevel_zones
        else f"⚠️ ZONE INVARIANT WAIVED for {sorted(allow_waterlevel_zones)} — "
        "THIS DOMAIN IS INADMISSIBLE BY CONSTRUCTION"
    )
    arm_claim = (
        f"every mask==2 cell inside exactly one of {len(dom.boundary_arms)} declared "
        "arms, all wet, counts in range"
        if dom.boundary_arms
        else "no boundary arms declared (whitelist not enforced on this domain)"
    )
    print(
        "[build_static] domain invariants OK (no outflow BC on water; no paved-over "
        "surveyed channel; no interior inactive islands; no NoData under an active cell; "
        f"no active cell in a land box; {arm_claim}; {zone_claim})"
    )


def apply_mask_and_boundary(
    base: BaseConfig,
    sf: SfincsModel,
    *,
    skip_overrides: "frozenset[str]" = frozenset(),
    allow_waterlevel_zones: "frozenset[str]" = frozenset(),
) -> None:
    """Build the active mask + water-level/outflow boundaries and enforce the invariants.

    ONE source of truth: ``build_static`` calls it on a freshly-built grid, and
    ``scripts/setup_boundary_depth.py`` calls it on a COPY of the frozen mesh to re-derive
    the mask at a different ``mask_zmin`` — a pure mask/boundary change that reuses the
    frozen subgrid tables (every face already has them), so no rebuild.

    THE ORDER BELOW IS THE DESIGN, not an implementation detail:

        create_active  →  region clip  →  land_boxes → 0  →  fill inactive holes
        →  create_boundary  →  demote every mask==2 outside an arm  →  seal wet outflow

    ``land_boxes`` come before the hole fill because they CREATE inactive ground, and the
    fill must see it. The arm demotion comes after ``create_boundary`` because that is
    what produces the cells being filtered. The wet-outflow seal comes last so it also
    catches anything the demotion turned into an edge.

    ``skip_overrides`` / ``allow_waterlevel_zones`` — BRACKETING ONLY. Both default to
    empty. They exist to build a deliberately-inadmissible bound. Skipping an override
    without also waiving the matching zone will simply fail the invariant, which is
    correct: the two must be waived together and on purpose.
    """
    dom = _domain.active()

    # 4. Active mask ----------------------------------------------------------
    _boxes = dom.always_active_boxes_ll
    bay_include = (
        gpd.GeoDataFrame(geometry=[shapely.box(*b) for b in _boxes], crs=4326)
        if _boxes
        else None
    )
    sf.quadtree_mask.create_active(zmin=base.mask_zmin, include_polygon=bay_include)

    # Clip the active mask to the region polygon (the rotated grid fills the L's bounding
    # box; drop the dry inland cells in the concave notch). Mask-only.
    _region = gpd.read_file(base.region).to_crs(sf.crs).geometry.iloc[0]
    fx, fy = _face_xy(sf)
    _outside = ~shapely.contains_xy(_region, fx, fy)
    mask = sf.quadtree_grid.data["mask"].values.copy()
    mask[_outside] = 0

    # 4a. Declared land -------------------------------------------------------
    # A hard bank the DEM does not reproduce. Declared, not depth-derived: a threshold is
    # a statement about elevation and the mask it produces is a statement about topology.
    for name, (xmin, ymin, xmax, ymax), why in dom.land_boxes:
        sel = (mask > 0) & (fx > xmin) & (fx < xmax) & (fy > ymin) & (fy < ymax)
        n = int(sel.sum())
        if n:
            print(f"[mask] land box {name}: {n} cells -> inactive  ({why})")
        mask[sel] = 0

    # 4b. Fill inactive islands ----------------------------------------------
    # MUST come after the region clip and the land boxes (both create their own inactive
    # ground) and BEFORE create_boundary, which is what turns an island into a ring of
    # imposed open-ocean level.
    mask = _fill_inactive_holes(sf, mask, sf.quadtree_grid.data["z"].values)
    # Mirror image, same place in the order: an ACTIVE island detached from the
    # domain must go before create_boundary, or it gets ringed with mask==2.
    mask = _drop_detached_active_islands(sf, mask, sf.quadtree_grid.data["z"].values)
    sf.quadtree_grid.data["mask"] = sf.quadtree_grid.data["mask"].copy(data=mask)

    # 5. Boundary cells -------------------------------------------------------
    sf.quadtree_mask.create_boundary(btype="waterlevel", zmax=-1, reset_bounds=True)
    sf.quadtree_mask.create_boundary(
        btype="outflow", zmin=OUTFLOW_MAX_DEPTH, zmax=OUTFLOW_MAX_BED, reset_bounds=False
    )

    mask = sf.quadtree_grid.data["mask"].values.copy()
    fx, fy = _face_xy(sf)

    # 5a. THE ARM WHITELIST ---------------------------------------------------
    # Everything create_boundary produced that is not inside a declared arm goes back to
    # ordinary active interior. This REPLACES the half-plane MaskOverride patches: those
    # were a blacklist, so they could only remove wrongness someone had already noticed.
    if dom.boundary_arms:
        keep = np.zeros(len(mask), dtype=bool)
        for arm in dom.boundary_arms:
            if arm.btype != "waterlevel":
                continue
            xmin, ymin, xmax, ymax = arm.box
            keep |= (fx > xmin) & (fx < xmax) & (fy > ymin) & (fy < ymax)
        demote = (mask == 2) & ~keep
        n = int(demote.sum())
        if n:
            print(
                f"[mask] arm whitelist: {n} water-level BC cells outside every declared "
                f"arm demoted 2 -> 1 (interior). The invariants below then assert that "
                f"NONE remain."
            )
        mask[demote] = 1

    # 5b. Region-specific mask corrections, from the DOMAIN REGISTRY ----------
    # Every box is fully bounded — the type has no `None` side. Two of the three overrides
    # in the previous repo had unbounded sides, which made them silently domain-dependent.
    for ov in dom.mask_overrides:
        if ov.name in skip_overrides:
            print(f"!! mask override '{ov.name}' SKIPPED (bracketing experiment)")
            continue
        xmin, ymin, xmax, ymax = ov.box
        sel = (
            (mask == ov.frm) & (fx > xmin) & (fx < xmax) & (fy > ymin) & (fy < ymax)
        )
        n = int(sel.sum())
        if n:
            print(f"[mask] override {ov.name}: {n} cells {ov.frm} → {ov.to}  ({ov.why})")
        mask[sel] = ov.to

    # 5c. SEAL ANY FREE-OUTFLOW BC THAT LANDS ON OPEN WATER -------------------
    # A free-outflow (Neumann) boundary is the condition you use where water may leave and
    # never return. On a DEEP CROSS-SECTION OF A TIDAL RIVER it is not a boundary, it is a
    # DRAIN — and that is precisely the bug that cost two months. hydromt put mask=3 on a
    # 5 m-deep cut face across the Navesink; the model ran that face at -0.82 m/s OUT of
    # the domain in 100% of timesteps, never once reversing, and 92.5% of everything
    # entering the estuary vanished. The estuary was a pipe, not a bathtub, and every
    # "null result" in that campaign was a bucket with a hole in it.
    #
    # A wet outflow cell becomes an ordinary active cell (mask=1); the inactive ground
    # beyond it is then SFINCS's default closed wall. Dry outflow cells are left alone:
    # they legitimately let overland flood water leave instead of ponding against the edge.
    zb = sf.quadtree_grid.data["z"].values
    wet_outflow = (mask == 3) & (zb < OUTFLOW_MAX_DEPTH)
    if wet_outflow.any():
        print(
            f"[mask] sealing {int(wet_outflow.sum())} free-outflow cells that sit on "
            f"water (deepest {zb[wet_outflow].min():+.2f} m) — an outflow BC on open "
            f"water is a drain, not a boundary"
        )
        mask[wet_outflow] = 1
    sf.quadtree_grid.data["mask"] = sf.quadtree_grid.data["mask"].copy(data=mask)

    # Display the whole BC set BEFORE the invariants run, so it is on the log even when
    # the build then fails — the intrusion is usually what caused the failure.
    _report_waterlevel_boundary(sf, mask, zb)
    _assert_boundary_is_continuous(sf, mask, dom)
    _report_boundary_arms(sf, mask, zb)
    _check_domain_invariants(
        sf, mask, zb, allow_waterlevel_zones=allow_waterlevel_zones
    )


def build_static(base: BaseConfig, template_dir: Path, skip_subgrid: bool = False) -> None:
    """Build grid/elevation/mask/subgrid and write to ``template_dir``.

    Forcing-independent, so it runs once; ``add_forcing`` reopens from disk.
    """
    template_dir = Path(template_dir)
    dom = _domain.active()

    if dom.frozen:
        raise RuntimeError(
            f"domain '{dom.name}' is FROZEN and cannot be built. It is registered so "
            "archived runs can be staged and scored, not so they can be reproduced — its "
            "build-time geography is deliberately not carried in the registry (see "
            "domain.py and ARCHIVE.md)."
        )

    template_dir.mkdir(parents=True, exist_ok=True)

    # Reproducibility short-circuit: the quadtree grid+subgrid build is
    # environment-sensitive — two builds of identical code/config can differ by ~18 cells,
    # which shifts CSI ~0.04. If a frozen static mesh is provided, copy it verbatim so
    # every run shares ONE identical grid. Freeze once with scripts/freeze_mesh.py.
    #
    # ⚠️ THIS RETURNS EARLY. A roughness or elevation change therefore produces a silent
    # NO-OP template — the copy has the old subgrid. Any bed or roughness edit needs a
    # SUBGRID REBUILD on the frozen mesh (scripts/rebuild_subgrid.py), not a run through
    # here. A MASK change is the opposite: no subgrid rebuild, but the fingerprint moves.
    if base.frozen_mesh is not None:
        frozen = Path(base.frozen_mesh)
        if not (frozen / "sfincs.inp").exists():
            raise FileNotFoundError(
                f"BaseConfig.frozen_mesh={frozen} has no sfincs.inp — "
                f"build it first with scripts/freeze_mesh.py"
            )
        print(f"[build_static] reusing frozen mesh from {frozen} (no rebuild)")
        shutil.copytree(frozen, template_dir, dirs_exist_ok=True)
        return

    if base.refinement is None:
        raise ValueError(
            f"domain '{dom.name}' declares no refinement polygons and no frozen mesh. A "
            "refinement recipe is not portable between domains — a level gate written for "
            "one basin will refine another basin's open water to its finest level. Write "
            "one for this domain and size it with scripts/probe_mesh_size.py FIRST."
        )

    log.initialize_logging()
    log.set_log_level(log_level=30)  # warnings + errors only (quiet build)
    log.to_file(template_dir / "hydromt_sfincs.log", append=False)

    sf = SfincsModel(
        data_libs=base.data_libs, root=str(template_dir), mode="w+", write_gis=True
    )

    # 2. Quadtree grid --------------------------------------------------------
    refinement_gdf = gpd.read_file(base.refinement)
    sf.quadtree_grid.create_from_region(
        region={"geom": str(base.region)},
        res=base.base_res,
        rotated=base.rotated,
        crs=base.crs,
        refinement_polygons=refinement_gdf,
        elevation_list=base.elevation(),
    )

    # 3. Elevation ------------------------------------------------------------
    sf.quadtree_elevation.create(elevation_list=base.elevation(), buffer_cells=0, nrmax=2000)

    # 4-5. Active mask + boundary cells --------------------------------------
    apply_mask_and_boundary(base, sf)

    # 6. Observation points (validation gauges only) --------------------------
    # From the domain registry. Names must stay stable: every his-based metric matches its
    # station by substring on this name, and premier.obs_points_ok asserts the coordinates
    # against this same registry.
    gauges = dom.obs_gauges
    val_gauges = gpd.GeoDataFrame(
        {"name": [g.name for g in gauges]},
        geometry=[Point(g.lon, g.lat) for g in gauges],
        crs="EPSG:4326",
    )
    print(f"[obs] {len(gauges)} observation points: {', '.join(g.name for g in gauges)}")
    n_crest = sum(g.survives_crest for g in gauges)
    print(f"[obs] {n_crest} of them survive the storm crest")
    sf.observation_points.create(locations=val_gauges, merge=False)

    # 7. Roughness + subgrid (memory/CPU peak) --------------------------------
    if skip_subgrid:
        # Domain-geometry dry run: everything the invariants need (grid, elevation, mask,
        # boundaries) is already built, and the subgrid is by far the most expensive step.
        # Used by scripts/validate_domain.py to PROVE a region/elevation change is right
        # BEFORE paying for a full rebuild.
        print("[build_static] skip_subgrid=True — stopping after mask/boundary (no subgrid)")
        fx, fy = _face_xy(sf)
        np.savez(
            template_dir / "domain_dryrun.npz",
            x=fx,
            y=fy,
            z=sf.quadtree_grid.data["z"].values,
            mask=sf.quadtree_grid.data["mask"].values,
        )
        del sf
        gc.collect()
        return

    for src in list(sf.data_catalog.sources):
        s = sf.data_catalog.get_source(src)
        if hasattr(s, "_data"):
            s._data = None
    gc.collect()

    roughness_list = [
        {"lulc": base.roughness_lulc, "reclass_table": str(base.reclass_table)}
    ]
    sf.quadtree_roughness.create(roughness_list=roughness_list, nrmax=200)
    sf.quadtree_subgrid.create(
        elevation_list=base.elevation(),
        roughness_list=roughness_list,
        nr_subgrid_pixels=base.nr_subgrid_pixels,
        nrmax=2000,  # DO NOT lower — smaller explodes the block loop
        write_dep_tif=True,  # per-level subgrid DEMs (flood-map downscale)
        write_man_tif=True,
    )

    # 8. Write ----------------------------------------------------------------
    sf.write()
    del sf
    gc.collect()


def check_waterlevel_support(sf: SfincsModel, expect: int | None = None) -> int:
    """Assert hydromt selected the number of water-level support points we expect.

    Which gauges force the open boundary is decided by BUFFERING the region, so it is a
    property of the DOMAIN, not of the forcing file. `noaa_sandy_nj.nc` holds three
    gauges; pushing a domain 0.45 deg south dropped one of them from 150.7 km to 99.1 km
    — inside a 100 km buffer by 0.9 km. Nothing downstream notices: the run completes, the
    boundary is smooth, and the arm is simply no longer the 2-node construction everything
    was measured against.

    Inserting a support point is not a cosmetic change. It cost one retired arm +0.18 m of
    HWM bias, and the failure mode is silent by nature, so this is checked rather than
    remembered. Returns the count.

    ``expect`` overrides the domain's count FOR ONE ARM ONLY
    (``Experiment.n_waterlevel_support``). ⚠️ It exists so such an arm must DECLARE its
    count where a reader sees it next to the description. Do NOT instead relax
    ``Domain.n_waterlevel_support``: that is the invariant protecting every other arm on
    the domain, and loosening it would let an unintended node slip into all of them.
    """
    want = expect if expect is not None else _domain.active().n_waterlevel_support
    data = getattr(sf.water_level, "data", None)
    if data is None or "bzs" not in data:
        raise RuntimeError(
            "water_level.create wrote no 'bzs' forcing "
            f"(water_level.data = {data!r}). Refusing to continue: the support-point "
            "count is exactly the thing that must not change silently between domains."
        )
    da = data["bzs"]
    dims = [d for d in da.dims if d != "time"]
    got = int(np.prod([da.sizes[d] for d in dims])) if dims else 1
    where = ""
    for cx, cy in (("x", "y"), ("lon", "lat")):
        if cx in data.coords and cy in data.coords:
            xs = np.atleast_1d(data[cx].values)
            ys = np.atleast_1d(data[cy].values)
            # A 112- or 400-point NACCS boundary would print a screenful; the count and
            # the extremes are what a build log needs.
            if xs.size <= 8:
                where = "  " + ", ".join(f"({a:.1f},{b:.1f})" for a, b in zip(xs, ys))
            else:
                where = (
                    f"  x {xs.min():.0f}..{xs.max():.0f}  y {ys.min():.0f}..{ys.max():.0f}"
                )
            break
    print(f"[bnd] {got} water-level support point(s){where}")
    if want is not None and got != want:
        raise RuntimeError(
            f"water-level boundary has {got} support points, expected {want} for "
            f"domain '{_domain.active().name}'.{where}\n"
            "  hydromt selects gauges by buffering the region, so extending the "
            "domain can pull an extra gauge in (or drop one) with no other symptom.\n"
            "  If this is INTENDED, change Domain.waterlevel_buffer and "
            "Domain.n_waterlevel_support together in nj_sfincs/domain.py and "
            "re-baseline — an inserted node is a forcing change, not a free one.\n"
            "  If instead ONE ARM deliberately forces from a different number of "
            "nodes, set Experiment.n_waterlevel_support on that arm — do NOT relax "
            "the domain value, which guards every other arm."
        )
    return got


def add_forcing(base: BaseConfig, sf: SfincsModel) -> None:
    """Window + physics flags and every compound forcing (no waves)."""
    sf.config.update(
        {
            "tref": base.tref,
            "tstart": base.tstart,
            "tstop": base.tstop,
            "tspinup": 3600.0,
            "coriolis": 1,
            "latitude": base.latitude,
            "advection": 1,
            "dtmapout": 3600.0,  # map output every hour
            "dtmaxout": 86400.0,  # one zsmax over the whole run
            "dthisout": 600.0,  # his output every 10 min
        }
    )

    sf.water_level.create(
        geodataset=base.waterlevel_geodataset,
        buffer=base.waterlevel_buffer,
        merge=False,
    )
    check_waterlevel_support(sf)
    sf.wind.create(wind="era5_nj")
    sf.pressure.create(press="era5_nj")
    sf.precipitation.create(precip="aorc_sandy_nj", cumulative_input=True, aggregate=False)
    sf.discharge_points.create(geodataset="usgs_sandy_discharge", merge=False)
    sf.quadtree_infiltration.create_cn(cn="cn_nj", antecedent_moisture=None, nrmax=2000)


def _point_wave_bnd(wcfg: WaveConfig, base: BaseConfig, sf: SfincsModel, pts):
    """Per-support-point wave forcing from an unstructured (time, node) point file.

    Returns ``(t, hs, tp, wd, ds)`` where every array except ``t`` is shaped
    ``(ntime, npoints)`` — one column per SnapWave support point, taken from that point's
    NEAREST source node.

    Two things here are load-bearing and neither is obvious:

    **The clock is referenced to ``base.tref``, not to the file's first timestamp.** The
    ERA5 path computes ``t - t[0]`` and gets away with it only because its file happens to
    start exactly at tref. A source padded earlier — CORA is built with a day of lead-in so
    interpolation never extrapolates at an endpoint — would silently shift the entire wave
    forcing by that pad. A 24 h offset on a storm whose peak is the whole point would not
    announce itself; it would just score badly.

    **Nearest-node lookup is checked, not trusted.** The distance to each chosen node and
    its source depth are printed and asserted, because a lookup that quietly lands on an
    estuarine or dry node produces a plausible-looking boundary file.
    """
    import pyproj

    path = Path(wcfg.wave_point_dataset)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise FileNotFoundError(
            f"wave_point_dataset {path} not found — build it with "
            "scripts/build_cora_waves.py"
        )
    ds = xr.open_dataset(path)

    # Source nodes are lon/lat; support points are in the model's projected CRS.
    epsg = _domain.active().epsg
    tf = pyproj.Transformer.from_crs(epsg, 4326, always_xy=True)
    plon, plat = tf.transform(pts[:, 0], pts[:, 1])

    slon = np.asarray(ds["lon"].values, float)
    slat = np.asarray(ds["lat"].values, float)
    sdep = np.asarray(ds["depth"].values, float) if "depth" in ds else None

    idx, dist = [], []
    for lo, la in zip(plon, plat):
        # Local-scale planar distance is plenty at <1 km and avoids a geodesic call per
        # node; cos(lat) keeps the longitude degree honest.
        d = np.hypot((slon - lo) * np.cos(np.deg2rad(la)), slat - la) * 111_000.0
        j = int(np.argmin(d))
        idx.append(j)
        dist.append(d[j])
    idx = np.asarray(idx)
    dist = np.asarray(dist)

    print(
        f"[waves] point forcing from {path.name}: {ds.sizes['node']} source nodes, "
        f"{len(idx)} support points"
    )
    for k, (lo, la, j, dk) in enumerate(zip(plon, plat, idx, dist)):
        dep = f"{sdep[j]:6.1f} m" if sdep is not None else "   n/a"
        print(
            f"[waves]   pt {k}: lon {lo:8.4f} lat {la:7.4f} -> node {j:6d} "
            f"({dk / 1000:5.2f} km, source depth {dep})"
        )
    if dist.max() > 5_000.0:
        raise RuntimeError(
            f"nearest source node is {dist.max() / 1000:.1f} km from a support point "
            "(limit 5 km). The wave file does not cover this boundary; extend the "
            "search box in scripts/build_cora_waves.py rather than accepting it."
        )

    # Clip to the run window. Starting at tref keeps every emitted time >= 0, and the pad
    # before tref exists only so the source brackets the window.
    times = pd.to_datetime(ds["time"].values)
    keep = times >= pd.Timestamp(base.tref)
    if not keep.any():
        raise RuntimeError(f"{path.name} has no samples at/after tref {base.tref}")
    times = times[keep]
    t = (times - pd.Timestamp(base.tref)).total_seconds().to_numpy(float)

    out = []
    for var in ("hs", "tp", "wd"):
        a = np.asarray(ds[var].values, float)[np.asarray(keep)][:, idx]
        if not np.isfinite(a).all():
            raise RuntimeError(
                f"non-finite {var} in the selected {path.name} nodes — the builder is "
                "supposed to drop those; do not write NaN into a SnapWave boundary."
            )
        out.append(a)
    hs, tp, wd = out
    dspread = np.full_like(hs, 30.0)

    print(
        f"[waves] window {times[0]} .. {times[-1]}  (t = {t[0]:.0f} .. {t[-1]:.0f} s "
        f"from tref {base.tref})"
    )
    print(
        "[waves] peak Hs per point: "
        + ", ".join(f"{v:.2f}" for v in hs.max(axis=0))
        + f"   alongshore spread {np.ptp(hs.max(axis=0)):.2f} m"
    )
    return t, hs, tp, wd, dspread


def add_waves(wcfg: WaveConfig, base: BaseConfig, sf: SfincsModel) -> dict:
    """The SnapWave block. Returns the ASCII boundary arrays.

    Adds the tuned physics params when ``wcfg.tune_physics`` and the ocean-side wavemaker
    when ``wcfg.wavemaker`` (both no-ops otherwise).
    """
    if wcfg.decouple_snapwave:
        # DECOUPLED: the wave solver gets its own, DEEPER domain. The SFINCS mask (and
        # with it the water-level boundary) is left untouched, so tide/surge forcing stays
        # at the coast while waves are imposed out on the shelf.
        sf.quadtree_snapwave_mask.create_active(
            zmin=wcfg.snapwave_mask_zmin, copy_sfincsmask=False
        )
        # ...but `zmin` alone is NOT the seaward extension we want. create_active rebuilds
        # from scratch and admits EVERY cell above the threshold inside the region, so
        # -30 m also sweeps in inland HIGH GROUND (measured once: 10,431 cells up to
        # +106 m) that the SFINCS mask excludes by its own criteria. Those are
        # SnapWave-active but SFINCS-INACTIVE and dry — precisely the runaway geometry (a
        # wave cell where SFINCS computes no zs). So take the union actually meant:
        # everything the coupled config had, PLUS only the genuinely submerged band down
        # to snapwave_mask_zmin.
        _sm = sf.quadtree_grid.data["mask"].values
        _zz = sf.quadtree_grid.data["z"].values
        _band = (
            (sf.quadtree_grid.data["snapwave_mask"].values > 0)
            & (_sm == 0)
            & np.isfinite(_zz)
            & (_zz <= base.mask_zmin)
        )
        # Interior is uniformly active (1); create_boundary below promotes the seaward rim
        # to 2. Copying the SFINCS codes verbatim would import mask==2/3 (the
        # water-level/outflow boundary at the COAST) as wave-boundary cells, which is the
        # coupling this arm exists to remove.
        sf.quadtree_grid.data["snapwave_mask"] = sf.quadtree_grid.data[
            "snapwave_mask"
        ].copy(data=np.where((_sm > 0) | _band, 1, 0).astype(_sm.dtype))
        # Wave boundary = the new SEAWARD edge, not the inherited SFINCS mask==2.
        # btype="waves" is snapwave's own vocabulary ("waterlevel" is SFINCS-only and
        # raises here). create_boundary picks cells on the ACTIVE-DOMAIN EDGE that also
        # satisfy zmax, so this ring is the seaward rim only.
        sf.quadtree_snapwave_mask.create_boundary(
            btype="waves", zmax=wcfg.snapwave_mask_zmin + SNAPWAVE_BND_RING
        )
    else:
        # COUPLED: the wave solver shares the SFINCS mesh. Overwrite the fresh
        # snapwave_mask with the SFINCS mask so waves + hydrodynamics use one mesh.
        sf.quadtree_snapwave_mask.create_active(zmin=base.mask_zmin)
        sf.quadtree_grid.data["snapwave_mask"] = sf.quadtree_grid.data[
            "snapwave_mask"
        ].copy(data=sf.quadtree_grid.data["mask"].values.copy())

    # Incident-wave boundary = the OPEN-ATLANTIC edge only. Demote every snapwave boundary
    # cell north of the open-coast limit back to active interior, so incident waves don't
    # run away into an enclosed corner (the ~1e13 blow-up).
    _swm = sf.quadtree_grid.data["snapwave_mask"].values.copy()
    _swfy = sf.quadtree_grid.data.grid.face_coordinates[:, 1]
    _demote = (_swm == 2) & (_swfy >= _open_coast_max_y())
    _swm[_demote] = 1
    sf.quadtree_grid.data["snapwave_mask"] = sf.quadtree_grid.data["snapwave_mask"].copy(
        data=_swm
    )

    # Support points = the DEEP (z<-5), open-Atlantic (y<limit) stretch of the boundary,
    # binned by northing, easternmost (seaward) cell per bin. Decoupled: read the SNAPWAVE
    # boundary (out on the shelf). Coupled: the SFINCS mask==2 boundary.
    N = wcfg.wave_n_support
    _fc = sf.quadtree_grid.data.grid.face_coordinates
    _z = sf.quadtree_grid.data["z"].values
    _bnd_src = "snapwave_mask" if wcfg.decouple_snapwave else "mask"
    _atl = (
        (sf.quadtree_grid.data[_bnd_src].values == 2)
        & np.isfinite(_z)
        & (_z < -5.0)
        & (_fc[:, 1] < _open_coast_max_y())
    )
    _bxy = _fc[_atl]
    if not len(_bxy):
        raise RuntimeError(
            "no open-coast wave-boundary cells found (deep, below open_coast_max_y). "
            "Check Domain.open_coast_max_y against this domain's geometry — on a domain "
            "whose ocean arm wraps around a spit it is what separates the open Atlantic "
            "edge from the enclosed corner."
        )
    _ybins = np.linspace(_bxy[:, 1].min(), _bxy[:, 1].max(), N + 1)
    snapwave_pts = np.array(
        [
            grp[np.argmax(grp[:, 0])]
            for k in range(N)
            for grp in [_bxy[(_bxy[:, 1] >= _ybins[k]) & (_bxy[:, 1] <= _ybins[k + 1])]]
            if len(grp)
        ]
    )

    if wcfg.wave_point_dataset is not None:
        snapwave_t, snapwave_hs, snapwave_tp, snapwave_wd, snapwave_ds = _point_wave_bnd(
            wcfg, base, sf, snapwave_pts
        )
    else:
        # Uniform alongshore forcing from the nearest valid ERA5 wave node.
        # ⚠️ This path CANNOT express alongshore structure and is inadmissible at the
        # boundary depth — see WaveConfig.wave_point_dataset. Kept for reproducing an
        # ERA5 diagnostic, not for a candidate arm.
        _ew = sf.data_catalog.get_rasterdataset(wcfg.wave_geodataset)
        _node = _ew.sel(
            x=wcfg.wave_era5_node[0], y=wcfg.wave_era5_node[1], method="nearest"
        )
        snapwave_t = (_node["time"].values - _node["time"].values[0]) / np.timedelta64(
            1, "s"
        )
        snapwave_hs = _node["hs"].values
        snapwave_tp = _node["tp"].values
        snapwave_wd = _node["wd"].values
        snapwave_ds = np.full_like(snapwave_hs, 30.0)  # ERA5 has no spreading; 30 deg

    # Optional ocean-side wavemaker (native hydromt call; writes sfincs.wvm).
    if wcfg.wavemaker:
        sf.wave_makers.create(str(wcfg.wavemaker_line), merge=False)

    cfg = {
        "snapwave": 1,
        "snapwave_igwaves": int(wcfg.wave_igwaves),
        "snapwave_wind": int(wcfg.wave_wind),
        "snapwave_sector": wcfg.sector(),
        "dtwave": wcfg.dtwave,
        "storewavdir": 1,
    }
    if wcfg.tune_physics:
        cfg.update(
            {
                "snapwave_alpha": wcfg.snapwave_alpha,
                "snapwave_gamma": wcfg.snapwave_gamma,
                "snapwave_hmin": wcfg.snapwave_hmin,
                "snapwave_dtheta": wcfg.snapwave_dtheta,
                "snapwave_fw": wcfg.snapwave_fw,
                "snapwave_niter": wcfg.snapwave_niter,
                "storefw": wcfg.storefw,
            }
        )
    sf.config.update(cfg)

    return {
        "pts": snapwave_pts,
        "t": snapwave_t,
        "hs": snapwave_hs,
        "tp": snapwave_tp,
        "wd": snapwave_wd,
        "ds": snapwave_ds,
    }


def set_inp_keys(inp: Path, kv: dict) -> None:
    """Set/overwrite ``key = value`` lines in a sfincs.inp, appending any that are absent."""
    lines = Path(inp).read_text().splitlines()
    have = {ln.split("=")[0].strip() for ln in lines if "=" in ln}
    out = [
        f"{ln.split('=')[0].strip():<20} = {kv[ln.split('=')[0].strip()]}"
        if "=" in ln and ln.split("=")[0].strip() in kv
        else ln
        for ln in lines
    ]
    out += [f"{k:<20} = {v}" for k, v in kv.items() if k not in have]
    Path(inp).write_text("\n".join(out) + "\n")


def restore_diagnostics(model_dir: Path) -> None:
    """Re-enable the flux/mass-budget diagnostics that ``sf.write()`` drops.

    hydromt's writer knows nothing about ``crsfile`` (cross-sections) or ``storevel``, so a
    freshly staged experiment silently comes back with no cross-sections and
    ``storevel = 0`` — i.e. no mass budget, and an inp that differs from the reference's
    for reasons that have nothing to do with the experiment.

    ⭐ ON THIS DOMAIN THE CROSS-SECTIONS ARE NOT A DIAGNOSTIC, THEY ARE THE RESULT. SFINCS
    writes ``crosssection_discharge`` every 10 min, so observation lines just inside the
    Narrows and Arthur Kill arms give Q(t) through each cut — and the Narrows carries the
    Upper Bay + Hudson tidal prism, which is comparable against published values. That is
    what makes the relocated boundary auditable rather than merely asserted. Losing
    ``crsfile`` here loses the headline measurement.

    Call this after :func:`finalize` on every staging path.
    """
    model_dir = Path(model_dir)
    crs_src = ROOT / "data" / "flux_crosssections.crs"
    kv = {"storevel": "1"}
    if crs_src.exists():
        shutil.copy2(crs_src, model_dir / "sfincs.crs")
        kv["crsfile"] = "sfincs.crs"
    else:  # never point crsfile at a file the solver cannot open
        print(f"[warn] {crs_src} missing — staging without cross-sections")
    set_inp_keys(model_dir / "sfincs.inp", kv)


def finalize(
    wcfg: WaveConfig,
    base: BaseConfig,
    sf: SfincsModel,
    model_dir: Path,
    sw: dict | None,
) -> None:
    """Release handles, write, patch sfincs.inp, write the SnapWave ASCII forcing.

    Called for EVERY experiment (waves or not). When ``wcfg.wavemaker`` the ``wvmfile``
    key + ``sfincs.wvm`` are preserved — do NOT strip them.
    """
    model_dir = Path(model_dir)

    # Materialize forcing in memory, drop xarray's open-file cache, so every handle closes
    # before write (avoids Errno 13 on /cache when re-writing a file this kernel still
    # holds open).
    for _c in (
        sf.water_level,
        sf.discharge_points,
        sf.wind,
        sf.pressure,
        sf.precipitation,
    ):
        try:
            if _c.data is not None:
                _c.data.load()
        except Exception:  # noqa: BLE001 — a component with no data is not an error here
            pass
    xr.backends.file_manager.FILE_CACHE.clear()
    gc.collect()

    sf.write()

    inp = model_dir / "sfincs.inp"
    text = inp.read_text()

    # (a) latitude — dropped on write, so Coriolis silently disables without it.
    if "\nlatitude" not in text:
        text = text.replace(
            "coriolis             = 1",
            f"coriolis             = 1\nlatitude             = {base.latitude}",
        )

    # (b) strip orphan infiltration keys (component sets key but writes no file).
    text = (
        "\n".join(
            ln
            for ln in text.splitlines()
            if not ln.strip().startswith(
                ("infiltration_file", "infiltration_type", "scsfile")
            )
        )
        + "\n"
    )

    # (c) waves: ensure SnapWave keys + write the ASCII boundary forcing.
    if wcfg.use_waves:
        if not wcfg.wavemaker:
            text = (
                "\n".join(
                    ln for ln in text.splitlines() if not ln.strip().startswith("wvmfile")
                )
                + "\n"
            )
        sw_keys = {
            "snapwave": "1",
            "snapwave_igwaves": str(int(wcfg.wave_igwaves)),
            "snapwave_wind": str(int(wcfg.wave_wind)),
            "snapwave_sector": str(wcfg.sector()),
            "dtwave": str(wcfg.dtwave),
            "storewavdir": "1",
            "snapwave_bndfile": "snapwave.bnd",
            "snapwave_bhsfile": "snapwave.bhs",
            "snapwave_btpfile": "snapwave.btp",
            "snapwave_bwdfile": "snapwave.bwd",
            "snapwave_bdsfile": "snapwave.bds",
        }
        if wcfg.tune_physics:
            sw_keys.update(
                {
                    "snapwave_alpha": str(wcfg.snapwave_alpha),
                    "snapwave_gamma": str(wcfg.snapwave_gamma),
                    "snapwave_hmin": str(wcfg.snapwave_hmin),
                    "snapwave_dtheta": str(wcfg.snapwave_dtheta),
                    "snapwave_fw": str(wcfg.snapwave_fw),
                    "snapwave_niter": str(wcfg.snapwave_niter),
                    "storefw": str(wcfg.storefw),
                }
            )
        present = {ln.split("=")[0].strip() for ln in text.splitlines() if "=" in ln}
        for k, v in sw_keys.items():
            if k not in present:
                text += f"{k:<20} = {v}\n"

        # Remove stale files keyed to an old config (would crash the solver).
        for stale in ("snapwave.upw", "snapwave.nc"):
            (model_dir / stale).unlink(missing_ok=True)
        if not wcfg.wavemaker:
            (model_dir / "sfincs.wvm").unlink(missing_ok=True)

        pts = sw["pts"]
        np.savetxt(model_dir / "snapwave.bnd", pts, fmt="%.3f")
        for fn, series in [
            ("snapwave.bhs", sw["hs"]),
            ("snapwave.btp", sw["tp"]),
            ("snapwave.bwd", sw["wd"]),
            ("snapwave.bds", sw["ds"]),
        ]:
            arr = np.asarray(series)
            # 1-D => one series broadcast to every support point (the ERA5 path, whose
            # 31 km cell cannot resolve the boundary anyway). 2-D => already one column
            # PER POINT, so it must NOT be tiled — tiling a 2-D array here would silently
            # emit a garbage-shaped boundary file.
            if arr.ndim == 1:
                block = np.tile(arr[:, None], (1, len(pts)))
            elif arr.shape == (len(sw["t"]), len(pts)):
                block = arr
            else:
                raise ValueError(
                    f"{fn}: wave series has shape {arr.shape}, expected "
                    f"({len(sw['t'])},) or ({len(sw['t'])}, {len(pts)})"
                )
            np.savetxt(
                model_dir / fn,
                np.column_stack([sw["t"], block]),
                fmt=["%11.1f"] + ["%11.3f"] * len(pts),
            )
    else:
        # 🔴 WAVES OFF MUST BE WRITTEN, NOT MERELY NOT-WRITTEN.
        # `prepare_experiment` copies a template that has waves ON. Before this branch
        # existed, `use_waves=False` only meant "skip add_waves" — so the copied
        # `snapwave = 1` and the five snapwave.* ASCII files survived untouched and the arm
        # ran WITH SnapWave anyway. It is silent: the run completes, the numbers are
        # plausible, and the only tell is ~10x runtime. It got as far as four submitted
        # SLURM jobs whose "nowaves" arm would have written a waves-ON row under a
        # waves-OFF name.
        text = (
            "\n".join(
                ln
                for ln in text.splitlines()
                if not ln.strip().startswith(
                    ("snapwave", "dtwave", "storewavdir", "wvmfile")
                )
            )
            + "\n"
        )
        text += f"{'snapwave':<20} = 0\n"  # explicit, so an inp-diff is honest
        for stale in (
            "snapwave.bnd",
            "snapwave.bhs",
            "snapwave.btp",
            "snapwave.bwd",
            "snapwave.bds",
            "snapwave.upw",
            "snapwave.nc",
            "sfincs.wvm",
        ):
            (model_dir / stale).unlink(missing_ok=True)

    inp.write_text(text)

    # ── WRITE THE PROVENANCE MANIFEST ────────────────────────────────────────
    # Every staged run gets a plain-text record of what it was actually made of, read back
    # OFF DISK (see provenance.py: config says what the builder intended, sfincs.inp and
    # the files beside it say what the solver was handed, and those two have diverged
    # before). It costs milliseconds and it is the artefact that answers "which planet was
    # this measured on" without needing the person who ran it.
    #
    # ⚠️ WIRED IN DELIBERATELY. An uncalled provenance module reads like coverage and
    # provides none; if this call is ever removed, delete the module with it.
    try:
        from . import provenance

        (model_dir / "provenance.txt").write_text(provenance.summary(model_dir))
    except Exception as e:  # noqa: BLE001 — a manifest must never fail a build
        print(f"[warn] provenance manifest not written: {e}")
