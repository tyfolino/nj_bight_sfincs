"""``lake_outlet_blocked``: marks in a basin whose outlet the MODEL holds shut.

WHY THIS EXISTS (2026-10-15, user decision)
-------------------------------------------
On the v4 premier two marks carry a third of the HWM error: 6122 (Deal Lake) and 6130
(Wreck Pond) read ~ −2.3 m because the sea never enters either lake in the model. The
lowest ocean–lake connection on the bed (3.10 m Wreck Pond, 3.62 m Deal) stands above
the modelled sea-side peak (2.81–3.01 m). In 2012 Sandy breached the dune at Wreck Pond
and overwashed Ocean Ave into Deal Lake — dune erosion and run-up, which a fixed-bed
SFINCS without a wavemaker does not have. The user chose a RULE-BASED flag: headline
metrics reported WITH and WITHOUT the flagged marks; a mark is NEVER dropped.

THE RULE
--------
For every mark, three numbers off the finished run and its staged inputs:

``lake_sea_peak_m`` (P) — the local sea-side peak: the MEDIAN ``zsmax`` over the
    "sea" faces within ``SEA_BAND_M`` of the sea face nearest the mark. A "sea" face is
    one the forced boundary reaches through the subgrid sills at the run's own starting
    level ``zsini`` — the normally-wet ocean, bays and tidal channels. Median, not max,
    for the reason the HWM estimator is a median: a max over a window grows with the
    window and would let one surf-zone or injection spike decide the flag.
``lake_connect_level_m`` (C) — the lowest water level at which the sea reaches the mark:
    the minimum, over the faces within the scorer's radius of the mark (at least the
    nearest face), of each face's SEA-CONNECTION LEVEL — the lowest level at which
    ``sea_level.connected_initial_zs`` would reach that face (the minimax path from the
    ``mask == 2`` cells through ``z_zmin`` and the uv sills ``uv_zmin``).
``lake_floor_m`` (F) — the lowest ``z_zmin`` in the same window.

``lake_outlet_blocked = F < P <= C``: there is ground at the mark below the local sea
peak, and the sea cannot reach it at that peak. In words: the bathtub filled to the
sea-side peak would put water at this mark, but the model's bed holds the basin's outlet
closed above that level.

What it is NOT: it does not read the observation (no selection on the outcome), and a
mark standing ABOVE the sea peak on open ground (F >= P: a run-up / wave mark) is not
flagged — that is a different shortfall.

⚠️ Weirs (``sfincs.weir``, e.g. the Keansburg levee) are NOT in the sill graph, so a basin
held shut only by a weir reads as connected (under-flags, never over-flags).
⚠️ A basin the sea legitimately does not reach (a real dike that held, a rain pond behind
a road embankment) is flagged too whenever its floor is below the local sea peak — the flag
is a statement about the MODEL's outlet, not about what happened in 2012. Read the
per-mark columns before excluding a mark.

MEASURED (v4_refreeze ``naccs-premier``, 2026-10-17; ``scripts/lake_outlet_blocked.py``):
5 scored marks flagged — 6121, 6122, 6124 (``south_coast``), 6129 (``shark_river``), 6130
(``barnegat_bay``) — plus q>2 marks 6119, 6120, 6126; the SAME set at bands 500 / 1000 /
2000 m. ⚠️ 6129 and 6130 are flagged by 2–5 cm (C 2.819 by some route other than the
3.10 m beach sill, P 2.77–2.81), inside the 5–14 cm waves-on run-to-run noise: the flag
can flip between arms, so a PAIRED comparison of ``*_excl_lake_blocked`` should hold one
mark set (the reference run's ``hwm_lake_outlet_blocked_ids``) on both sides.

Same graph as ``sea_level`` (the connected start), so the sill reading cannot drift
between the two; the connection level is computed for every face in one pass (a
minimum spanning tree + pointer jumping), and ``connection_level(...) < L`` reproduces
``connected_initial_zs(L, ...) > DRY`` exactly (``tests/test_lake_flag.py``).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ..sea_level import uv_pairs

#: The sea-side window: sea faces within this distance BEYOND the nearest sea face.
SEA_BAND_M = 1000.0

#: Stamped beside every count so a row says which rule produced it.
RULE_LABEL = "F<P<=C;P=median_sea_zsmax_band{band:g}m;window{radius:g}m"

#: Per-mark columns, in order.
COLUMNS = (
    "lake_outlet_blocked",
    "lake_sea_peak_m",
    "lake_connect_level_m",
    "lake_floor_m",
    "lake_sea_dist_m",
    "lake_n_window_faces",
)


def connection_level(
    mask: np.ndarray,
    z_zmin: np.ndarray,
    uv_nm: np.ndarray,
    uv_nmu: np.ndarray,
    uv_zmin: np.ndarray,
) -> np.ndarray:
    """Per face: the lowest water level at which the forced boundary reaches it.

    ``+inf`` for inactive faces and faces no path reaches. Exactly the threshold of
    ``sea_level.connected_initial_zs``: a face is reached at level ``L`` there iff
    ``connection_level(...) < L`` here. A path's level is the max of every ``z_zmin`` on
    it and every sill ``uv_zmin`` it crosses; this is the minimum over paths (the
    bottleneck path, which lies on the minimum spanning tree).
    """
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import breadth_first_order, minimum_spanning_tree

    n = len(mask)
    z = np.asarray(z_zmin, dtype=np.float64)
    act = (np.asarray(mask) > 0) & np.isfinite(z)
    uv_nm, uv_nmu = np.asarray(uv_nm), np.asarray(uv_nmu)
    uvz = np.asarray(uv_zmin, dtype=np.float64)
    ok = act[uv_nm] & act[uv_nmu] & np.isfinite(uvz)
    a, b = uv_nm[ok], uv_nmu[ok]
    w = np.maximum(uvz[ok], np.maximum(z[a], z[b]))
    seeds = np.flatnonzero(act & (np.asarray(mask) == 2))
    src = n  # a super-source tied to every forced cell at that cell's own floor
    a = np.r_[a, np.full(len(seeds), src)]
    b = np.r_[b, seeds]
    w = np.r_[w, z[seeds]]
    lo, hi = np.minimum(a, b).astype(np.int64), np.maximum(a, b).astype(np.int64)
    keep = lo != hi
    lo, hi, w = lo[keep], hi[keep], w[keep]
    # one edge per pair, the lowest (a coo -> csr conversion would SUM duplicates)
    order = np.lexsort((w, hi, lo))
    lo, hi, w = lo[order], hi[order], w[order]
    first = np.r_[True, (lo[1:] != lo[:-1]) | (hi[1:] != hi[:-1])]
    lo, hi, w = lo[first], hi[first], w[first]
    out = np.full(n, np.inf)
    if len(seeds) == 0 or len(w) == 0:
        return out
    key = lo * (n + 1) + hi  # ascending: sorted by (lo, hi)
    # scipy reads a zero weight as "no edge": shift to >= 1 for the tree only
    g = coo_matrix((w - w.min() + 1.0, (lo, hi)), shape=(n + 1, n + 1)).tocsr()
    mst = minimum_spanning_tree(g).tocoo()
    _, pred = breadth_first_order(mst, src, directed=False, return_predecessors=True)
    i, j = mst.row.astype(np.int64), mst.col.astype(np.int64)
    # the exact (unshifted) weight of each tree edge, looked up by its pair
    k = np.minimum(i, j) * (n + 1) + np.maximum(i, j)
    w_tree = w[np.searchsorted(key, k)]
    child = np.where(pred[j] == i, j, np.where(pred[i] == j, i, -1))
    on = child >= 0
    m_up = np.full(n + 1, np.inf)  # max edge weight from a node up to p_up
    p_up = np.arange(n + 1)  # unreached nodes point at themselves (stay +inf)
    m_up[child[on]] = w_tree[on]
    p_up[child[on]] = pred[child[on]]
    m_up[src] = -np.inf
    p_up[src] = src
    for _ in range(64):  # pointer jumping: log2(depth) rounds
        m_up = np.maximum(m_up, m_up[p_up])
        nxt = p_up[p_up]
        if np.array_equal(nxt, p_up):
            break
        p_up = nxt
    out[:] = m_up[:n]
    return out


def flags(
    mark_x: np.ndarray,
    mark_y: np.ndarray,
    face_x: np.ndarray,
    face_y: np.ndarray,
    mask: np.ndarray,
    z_zmin: np.ndarray,
    conn: np.ndarray,
    zsmax: np.ndarray,
    sea_level0: float,
    radius_m: float,
    sea_band_m: float = SEA_BAND_M,
) -> pd.DataFrame:
    """The rule on arrays (one row per mark, ``COLUMNS``). See the module docstring."""
    from scipy.spatial import cKDTree

    act = np.flatnonzero(np.asarray(mask) > 0)
    sea = act[(conn[act] <= sea_level0) & np.isfinite(zsmax[act])]
    pts = np.c_[np.asarray(mark_x, float), np.asarray(mark_y, float)]
    rows = {c: [] for c in COLUMNS}
    if len(act) == 0:
        return pd.DataFrame(rows)
    t_act = cKDTree(np.c_[face_x[act], face_y[act]])
    t_sea = cKDTree(np.c_[face_x[sea], face_y[sea]]) if len(sea) else None
    for p in pts:
        d0, k0 = t_act.query(p)
        win = act[t_act.query_ball_point(p, max(radius_m, d0))]
        if len(win) == 0:
            win = act[[k0]]
        floor = float(np.nanmin(z_zmin[win]))
        c = float(np.min(conn[win]))
        if t_sea is not None:
            ds, _ = t_sea.query(p)
            band = sea[t_sea.query_ball_point(p, ds + sea_band_m)]
            peak = float(np.median(zsmax[band]))
        else:
            ds, peak = np.inf, np.nan
        blocked = bool(np.isfinite(peak) and floor < peak <= c)
        for col, v in zip(COLUMNS, (blocked, peak, c, floor, float(ds), len(win))):
            rows[col].append(v)
    return pd.DataFrame(rows)


def load_run(model_dir: Path | str) -> dict:
    """The arrays ``flags`` needs, from a finished run dir + its staged inputs.

    Reads only what it needs (~1 GB peak on v4's 4.9 M faces): the staged ``mask`` and
    neighbour arrays (``sfincs.nc``), ``z_zmin`` / ``uv_zmin`` (``sfincs_subgrid.nc``),
    ``zsmax`` reduced over its blocks one at a time (``sfincs_map.nc``) and ``zsini``.
    """
    import xarray as xr

    from .core import inp_value

    model_dir = Path(model_dir)
    with xr.open_dataset(model_dir / "sfincs.nc") as g:
        mask = g["mask"].values.astype(np.int8)
        fx, fy = g["mesh2d_face_x"].values, g["mesh2d_face_y"].values
        mu, nu = g["mu"].values.astype(np.int8), g["nu"].values.astype(np.int8)
        mu1, mu2, nu1, nu2 = (
            g[k].values.astype(np.int64) - 1 for k in ("mu1", "mu2", "nu1", "nu2")
        )
    with xr.open_dataset(model_dir / "sfincs_subgrid.nc") as s:
        z_zmin = s["z_zmin"].values
        uv_zmin = s["uv_zmin"].values
        npuv = s.sizes["npuv"]
    uv_nm, uv_nmu = uv_pairs(mu, mu1, mu2, nu, nu1, nu2)
    del mu1, mu2, nu1, nu2
    if len(uv_nm) != npuv:
        raise RuntimeError(
            f"rebuilt {len(uv_nm)} uv points but the subgrid has {npuv}: hydromt's uv "
            "order changed — the sills would be read against the wrong cell pairs."
        )
    with xr.open_dataset(model_dir / "sfincs_map.nc") as m:
        v = m["zsmax"]
        if "timemax" in v.dims:
            zsmax = np.full(v.sizes["nmesh2d_face"], -np.inf, np.float32)
            for t in range(v.sizes["timemax"]):
                zsmax = np.fmax(zsmax, v.isel(timemax=t).values)
        else:
            zsmax = v.values
    zsmax = np.where(np.isfinite(zsmax) & (zsmax > -999), zsmax, np.nan)
    try:
        zsini = float(inp_value(model_dir / "sfincs.inp", "zsini"))
    except (KeyError, ValueError):  # SFINCS's own default
        zsini = 0.0
    conn = connection_level(mask, z_zmin, uv_nm, uv_nmu, uv_zmin)
    return dict(
        face_x=fx,
        face_y=fy,
        mask=mask,
        z_zmin=z_zmin,
        conn=conn,
        zsmax=zsmax,
        sea_level0=zsini,
    )


def lake_outlet_blocked(
    model_dir: Path | str,
    mark_x: np.ndarray,
    mark_y: np.ndarray,
    radius_m: float,
    sea_band_m: float = SEA_BAND_M,
    run: dict | None = None,
) -> pd.DataFrame:
    """Per-mark flag + diagnostics for a finished run (marks in the MODEL's CRS)."""
    run = load_run(model_dir) if run is None else run
    return flags(mark_x, mark_y, radius_m=radius_m, sea_band_m=sea_band_m, **run)


def rule_label(radius_m: float, sea_band_m: float = SEA_BAND_M) -> str:
    return RULE_LABEL.format(band=sea_band_m, radius=radius_m)
