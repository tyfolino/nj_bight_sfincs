"""A SnapWave domain with a GRID-ALIGNED stepped seaward boundary.

Why this exists (STATUS 2026-09-08). SnapWave kills every interior cell that touches TWO
or more wave-boundary cells: measured on the v3 premier, 3,841 of 3,841 ring cells with
one boundary neighbour carry waves and 95–100 % of those with two or more carry nothing
(no hm0, no wave force, fill-value direction). A wave boundary that follows a depth
contour across an axis-aligned quadtree is a staircase, and every inner corner of a
staircase is such a cell — 43 % of the ring along the diagonal South Jersey coast. The
shelf then receives 15–60 % of the imposed wave height and the beaches get ~0.05 m of
setup where theory says 0.2–0.35 m.

The fix is geometric: draw the SnapWave boundary as a FEW long segments along quadtree
rows and columns, so the only inner corners are the handful of steps. Everything here is
in level-1 index space (``n1`` row, ``m1`` column of the 200 m base grid, 1-based as in
``sfincs.nc``), which is exact whatever the grid rotation — v3 is rotated 359.183°, so
"x = const" is NOT a column and a projected-coordinate polygon would re-introduce a
staircase.

The SFINCS mask (and the water-level boundary) is untouched: this only builds
``snapwave_mask``, which ``premier.py`` deliberately leaves out of the domain fingerprint.

Rules, per cell:

* band     = SFINCS-inactive, finite bed, bed <= ``mask_zmin``, ``m_west <= m1 <= M(n1)``,
  ``n1 <= n_top``.  ``M(n1)`` is the step table's max column for that row.
* active   = SFINCS-active OR band  (code 1)
* boundary = band cell whose EAST, SOUTH or NORTH level-1 neighbour is outside the band
  (or which sits on the bottom row), and whose bed is <= ``bnd_zmax``  (code 2).
  Only band cells: SFINCS-active cells are never wave-boundary cells here, which is the
  decoupling. No WEST rule on purpose — the west edge of the band in the southern rows
  is the Delaware Bay side, and an imposed-wave line inside a bay mouth is the archive's
  wavemaker-in-a-bay trap.

``model.add_waves`` still demotes boundary cells north of ``Domain.open_coast_max_y``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

#: Deepest bed a boundary cell may have (m NAVD88, negative down). Shallower edge cells
#: (a bottom-row cell on a shoal) are left as closed interior edge rather than forced.
BND_ZMAX = -12.0


@dataclass(frozen=True)
class SnapWaveSteps:
    """A stepped seaward boundary in level-1 quadtree index space.

    ``steps`` are ``(n1_lo, n1_hi, M)`` — inclusive row range and the max active column
    for those rows. Row ranges must tile ``1 .. n_top`` without gaps or overlap.
    """

    name: str
    steps: tuple[tuple[int, int, int], ...]
    m_west: int  #: westernmost band column (excludes the Delaware Bay side)
    n_top: int  #: northernmost band row
    why: str = ""

    def max_column(self, n1: np.ndarray) -> np.ndarray:
        """``M(n1)`` for an array of level-1 rows; 0 (nothing active) outside the table."""
        n1 = np.asarray(n1)
        out = np.zeros(n1.shape, dtype=np.int64)
        for lo, hi, M in self.steps:
            out[(n1 >= lo) & (n1 <= hi)] = M
        return out

    def validate(self) -> None:
        rows = sorted(self.steps)
        if not rows or rows[0][0] != 1:
            raise ValueError(f"{self.name}: steps must start at row 1")
        for (lo, hi, _), (lo2, _hi2, _) in zip(rows, rows[1:]):
            if lo > hi or lo2 != hi + 1:
                raise ValueError(f"{self.name}: step rows must tile without gaps: {rows}")
        if rows[-1][1] != self.n_top:
            raise ValueError(f"{self.name}: last step must end at n_top={self.n_top}")


def level1_index(n: np.ndarray, m: np.ndarray, level: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Level-1 (200 m) row/column of every face from its own-level ``n, m, level``.

    ``sfincs.nc`` indexes are 1-based at each level; level L has ``2**(L-1)`` cells per
    base cell, so ``n1 = (n - 1) // 2**(L-1) + 1``.
    """
    f = 2 ** (np.asarray(level).astype(np.int64) - 1)
    n1 = (np.asarray(n).astype(np.int64) - 1) // f + 1
    m1 = (np.asarray(m).astype(np.int64) - 1) // f + 1
    return n1, m1


def build_snapwave_mask(
    n: np.ndarray,
    m: np.ndarray,
    level: np.ndarray,
    z: np.ndarray,
    sfincs_mask: np.ndarray,
    steps: SnapWaveSteps,
    mask_zmin: float,
    bnd_zmax: float = BND_ZMAX,
) -> tuple[np.ndarray, dict]:
    """The SnapWave mask (0 inactive / 1 active / 2 wave boundary) and a summary dict."""
    steps.validate()
    n1, m1 = level1_index(n, m, level)
    M = steps.max_column(n1)
    z = np.asarray(z, float)
    sm = np.asarray(sfincs_mask)
    inside = (m1 <= M) & (m1 >= steps.m_west) & (n1 <= steps.n_top) & (M > 0)
    band = (sm == 0) & np.isfinite(z) & (z <= mask_zmin) & inside

    # Outside-ness of the level-1 neighbours, evaluated on the step table (not on the
    # band itself, so a shallow patch inside the band never manufactures a boundary).
    M_south = steps.max_column(n1 - 1)
    M_north = steps.max_column(n1 + 1)
    east_out = (m1 + 1) > M
    south_out = (n1 == 1) | (m1 > M_south)
    north_out = (n1 == steps.n_top) | (m1 > M_north)
    edge = band & (east_out | south_out | north_out) & (z <= bnd_zmax)

    swm = np.where((sm > 0) | band, 1, 0).astype(np.int8)
    swm[edge] = 2

    # The SFINCS active domain must sit strictly inside the band's seaward limit — if a
    # SFINCS cell is east of M(n1) the water-level boundary pokes through the wave
    # boundary and the two are no longer decoupled.
    poke = (sm > 0) & (M > 0) & (m1 > M)
    info = dict(
        n_band=int(band.sum()),
        n_active=int((swm > 0).sum()),
        n_boundary=int((swm == 2).sum()),
        n_sfincs_outside_band=int(poke.sum()),
        n_edge_too_shallow=int((band & (east_out | south_out | north_out) & (z > bnd_zmax)).sum()),
        boundary_z_min=float(np.nanmin(z[edge])) if edge.any() else float("nan"),
        boundary_z_max=float(np.nanmax(z[edge])) if edge.any() else float("nan"),
    )
    return swm, info


def ring_report(face_faces: np.ndarray, swm: np.ndarray) -> dict:
    """How many active cells touch >= 2 boundary cells — the predicted dead cells.

    ``face_faces`` is ``mesh2d_face_faces`` (NaN-padded neighbour ids, 0-based).
    """
    swm = np.asarray(swm)
    bnd = np.where(swm == 2)[0]
    counts: dict[int, int] = {}
    for row in face_faces[bnd]:
        for k in row[np.isfinite(row)].astype(int):
            if swm[k] == 1:
                counts[k] = counts.get(k, 0) + 1
    vals = np.array(list(counts.values()), dtype=int)
    return dict(
        n_ring=int(len(vals)),
        n_one=int((vals == 1).sum()),
        n_two_plus=int((vals >= 2).sum()),
        frac_two_plus=float((vals >= 2).mean()) if len(vals) else float("nan"),
        two_plus_faces=np.array([k for k, v in counts.items() if v >= 2], dtype=int),
    )


def face_xy(n: np.ndarray, m: np.ndarray, level: np.ndarray, attrs: dict) -> tuple[np.ndarray, np.ndarray]:
    """Projected centre of every face from its indices and the grid's ``x0 y0 dx dy rotation``."""
    f = 2 ** (np.asarray(level).astype(np.int64) - 1)
    lx = (np.asarray(m, float) - 0.5) * float(attrs["dx"]) / f
    ly = (np.asarray(n, float) - 0.5) * float(attrs["dy"]) / f
    th = np.deg2rad(float(attrs.get("rotation", 0.0)))
    x = float(attrs["x0"]) + lx * np.cos(th) - ly * np.sin(th)
    y = float(attrs["y0"]) + lx * np.sin(th) + ly * np.cos(th)
    return x, y


def boundary_polyline(steps: SnapWaveSteps, attrs: dict) -> np.ndarray:
    """The stepped boundary as an ordered polyline (projected), north end first.

    Vertices sit on level-1 cell EDGES: the east edge of column M is at local x = M*dx,
    a step at the boundary between rows hi and hi+1 is at local y = hi*dy. Runs from the
    top of the northernmost segment down the staircase to the bottom row, then west
    along the bottom edge to ``m_west``.
    """
    dx, dy = float(attrs["dx"]), float(attrs["dy"])
    rows = sorted(steps.steps, reverse=True)  # north first
    pts = []
    for k, (lo, hi, M) in enumerate(rows):
        y_top = hi * dy if k > 0 else steps.n_top * dy
        pts.append((M * dx, y_top))
        pts.append((M * dx, (lo - 1) * dy))
    pts.append(((steps.m_west - 1) * dx, 0.0))
    P = np.array(pts, float)
    th = np.deg2rad(float(attrs.get("rotation", 0.0)))
    x = float(attrs["x0"]) + P[:, 0] * np.cos(th) - P[:, 1] * np.sin(th)
    y = float(attrs["y0"]) + P[:, 0] * np.sin(th) + P[:, 1] * np.cos(th)
    return np.c_[x, y]


def support_points(polyline: np.ndarray, boundary_xy: np.ndarray, n: int) -> np.ndarray:
    """``n`` points equally spaced along ``polyline``, each snapped to the nearest
    boundary cell centre (duplicates dropped). Boundary cells north of the open-coast
    limit have already been demoted by the caller, so pass only the cells that remain."""
    seg = np.diff(polyline, axis=0)
    L = np.hypot(seg[:, 0], seg[:, 1])
    cum = np.r_[0.0, np.cumsum(L)]
    s = np.linspace(0.0, cum[-1], n + 2)[1:-1]  # avoid the two end vertices
    samples = np.empty((n, 2))
    for k, sk in enumerate(s):
        j = min(int(np.searchsorted(cum, sk, side="right") - 1), len(L) - 1)
        t = (sk - cum[j]) / L[j] if L[j] > 0 else 0.0
        samples[k] = polyline[j] + t * seg[j]
    bxy = np.asarray(boundary_xy, float)
    out, seen = [], set()
    for p in samples:
        i = int(np.argmin(np.hypot(bxy[:, 0] - p[0], bxy[:, 1] - p[1])))
        if i not in seen:
            seen.add(i)
            out.append(bxy[i])
    return np.array(out)
