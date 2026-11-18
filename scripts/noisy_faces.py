#!/usr/bin/env python
"""Per-bed, per-water-level list of NOISY bank faces, from a tide run's own output.

    python scripts/noisy_faces.py <run_dir> --bed <label> [--run NAME] [--out DIR] [--q 0.2]
    python scripts/noisy_faces.py --union <out.npy> <a_noisy.npz> <b_noisy.npz> ...

Some bank faces (mostly land, a sliver of deep channel inside the face) ring in the 6 h ``zs`` snapshots
and every 3 h ``zsmax`` block catches the crest, so their tidal mean higher-high reads 0.1-0.9 m above the
water around them (logs/bank_face_sweep_2026-11-15/README.md; mechanism OPEN, ROOT_CAUSE.md). Which faces
do it moves with the BED (11-02: Jaccard 0.07 between beds) and with the WATER LEVEL (11-15: 36 of 920 deep
flags shared between today and +4 ft), so the list is made per run, from that run's ``sfincs_map.nc``.
It replaces the static 11-02 ``fT`` list (made on ``v4_refreeze_swz``).

Rule (ROOT_CAUSE.md "Proposal"; ``sweep.py``'s, which reproduces the tide products to 1e-6 m):
  * daily higher-high from the 3 h ``zsmax`` blocks after a 2.5 d spin-up, 24.84 h tidal days; a face is
    WET when it is wet on >= half the days (the mhh product's drawing rule); mhh = mean daily higher-high.
  * DEEP:  mhh - z_zmin >= 0.10 m (drops the film faces, ~95 % of raw flags; they cannot reach 0.15 m depth).
  * HIGH:  mhh - ref > 0.10 m, ref = the --q quantile (default 0.2, the stricter one) of the mhh of the
    SUBMERGED other wet faces (z_zmax < their own mhh) whose centres lie within max(150 m, 1.5 dx); fall back
    to all wet neighbours where fewer than 4 are submerged; no reference with < 4 neighbours.
  * flagged = DEEP and HIGH. Each flagged face is CLASSED by the std of r = zs - median(zs of its wet
    neighbours) over the post-spin-up snapshots: ``noisy`` (std > 0.05 m) or ``quiet`` (a real gradient
    behind a sill is possible). Both stay listed; ``cls`` records which.

Outputs in --out (default ``logs/noisy_faces/``), stem ``<bed>_<run>``:
  ``_noisy.npz``  face (0-based face index), mhh, ref, excess, snap_std, snap_n, cls (1 noisy, 2 quiet,
                  0 too few snapshots), n_active, and the rule's parameters;
  ``_noisy.npy``  bool over ACTIVE faces in face order, the format ``logs/mhhw_v2_2026-11-12/mhhw_maps.py
                  --noisy`` reads (blank these in tide-statistic products only; never in Sandy peak maps);
  ``_noisy.json`` counts.
``--union`` ORs several runs' ``_noisy.npz`` (same mesh) into one active-face ``.npy`` for a product drawn
across water levels. Peak memory ~10 GB and a few minutes on a full nj2 tide run; run it via srun.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
import nj_sfincs  # noqa: E402,F401  (pyproj before anything native)

SPINUP_D, DAY_H = 2.5, 24.84
MIN_NB = 4
CLS_NONE, CLS_NOISY, CLS_QUIET = 0, 1, 2


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


# ---------------------------------------------------------------- pure array core (tested)
def neighbours(x, y, R, k=128, workers=8):
    """(n, k) indices of the other points within R (per point); n = missing."""
    from scipy.spatial import cKDTree

    tree = cKDTree(np.c_[x, y])
    out = np.full((x.size, k), x.size, np.int32)
    for Rv in np.unique(R):
        sel = np.flatnonzero(R == Rv)
        for a in range(0, sel.size, 200_000):
            s = sel[a : a + 200_000]
            kk = min(k + 1, x.size)
            _, ii = tree.query(
                np.c_[x[s], y[s]], k=kk, distance_upper_bound=Rv, workers=workers
            )
            ii = ii.reshape(s.size, kk)
            ii[ii == s[:, None]] = x.size  # drop self
            ii = np.sort(ii, axis=1)[:, :k]
            out[s, : ii.shape[1]] = ii
    return out


def local_quantile(v, nb, q, minn=MIN_NB, workers=8):
    """q-quantile of v over each row of neighbour indices (NaN where < minn finite values)."""
    vv = np.append(v, np.nan).astype(np.float32)
    out = np.full(nb.shape[0], np.nan, np.float32)
    cnt = np.zeros(nb.shape[0], np.int16)
    ed = np.linspace(0, nb.shape[0], max(workers * 8, 1) + 1).astype(int)

    def job(i):
        a, b = ed[i], ed[i + 1]
        if a == b:
            return
        s = vv[nb[a:b]]
        c = np.isfinite(s).sum(1)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if q == 0.5:
                m = np.nanmedian(s, axis=1)
            else:
                m = np.nanquantile(s, q, axis=1, method="lower")
        m[c < minn] = np.nan
        out[a:b], cnt[a:b] = m, c

    with ThreadPoolExecutor(workers) as p:
        list(p.map(job, range(len(ed) - 1)))
    return out, cnt


def flag(x, y, dx, mhh, z_zmin, z_zmax, q=0.2, deep=0.10, high=0.10, workers=8):
    """The rule on the WET faces' arrays. Returns dict of per-face arrays (same order) + nb."""
    R = np.maximum(150.0, 1.5 * dx)
    nb = neighbours(x, y, R, workers=workers)
    ref_all, _ = local_quantile(mhh, nb, q, workers=workers)
    subm = z_zmax < mhh
    ref_sub, _ = local_quantile(np.where(subm, mhh, np.nan), nb, q, workers=workers)
    use_sub = np.isfinite(ref_sub)
    ref = np.where(use_sub, ref_sub, ref_all)
    excess = mhh - ref
    is_deep = (mhh - z_zmin) >= deep
    is_high = np.nan_to_num(excess, nan=-9.0) > high
    return dict(
        ref=ref,
        excess=excess,
        ref_is_submerged=use_sub,
        deep=is_deep,
        flagged=is_deep & is_high,
        nb=nb,
    )


def snapshot_residual_std(zs_snaps, faces, nb_faces, minn=MIN_NB):
    """std over snapshots of r = zs[face] - median(zs[wet neighbours]) (NaN = dry).

    ``zs_snaps`` yields 1-D arrays over ALL faces with dry faces NaN; ``nb_faces`` is (len(faces), k) of
    full face indices, -1 = none. Returns (std, n_snapshots_used).
    """
    acc = np.zeros(faces.size)
    acc2 = np.zeros(faces.size)
    n = np.zeros(faces.size, np.int32)
    for z in zs_snaps:
        v = np.append(z, np.nan)
        s = v[np.where(nb_faces >= 0, nb_faces, v.size - 1)]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            med = np.nanmedian(s, axis=1)
        r = z[faces] - med
        ok = np.isfinite(r) & (np.isfinite(s).sum(1) >= minn)
        acc[ok] += r[ok]
        acc2[ok] += r[ok] ** 2
        n[ok] += 1
    with np.errstate(all="ignore"):
        mean = acc / n
        std = np.sqrt(np.maximum(acc2 / n - mean**2, 0))
    return std, n


def classify(snap_std, snap_n, noisy_std=0.05, min_snaps=4):
    cls = np.where(snap_std > noisy_std, CLS_NOISY, CLS_QUIET).astype(np.int8)
    cls[(snap_n < min_snaps) | ~np.isfinite(snap_std)] = CLS_NONE
    return cls


# ---------------------------------------------------------------- run I/O
def read_inp(d: Path) -> dict:
    return {
        ln.split("=")[0].strip(): ln.split("=", 1)[1].strip()
        for ln in (d / "sfincs.inp").read_text().splitlines()
        if "=" in ln
    }


def tide_stats(d: Path, spinup_d=SPINUP_D, day_h=DAY_H):
    """mhh, days_wet, n_days and post-spin-up snapshot indices from a run's sfincs_map.nc."""
    import netCDF4
    import pandas as pd

    t0 = pd.to_datetime(read_inp(d)["tref"], format="%Y%m%d %H%M%S")
    an = t0 + pd.Timedelta(days=spinup_d)
    with netCDF4.Dataset(d / "sfincs_map.nc") as m:
        m.set_auto_mask(False)
        tm = np.asarray(m["timemax"][:], float)
        hours = np.asarray(
            ((t0 + pd.to_timedelta(tm, unit="s")) - an) / pd.Timedelta(hours=1), float
        )
        day = np.floor((hours - 1e-6) / day_h).astype(int)
        nd = int(np.floor(hours.max() / day_h))
        if nd < 1:
            raise SystemExit(f"{d}: no whole tidal day after a {spinup_d} d spin-up")
        nf = m.dimensions["nmesh2d_face"].size
        HH = np.full((nd, nf), np.nan, np.float32)
        for i in range(tm.size):
            if hours[i] <= 0 or day[i] >= nd:
                continue
            z = m["zsmax"][i].astype(np.float32)
            z[z < -1000] = np.nan
            HH[day[i]] = np.fmax(HH[day[i]], z)
        ts = np.asarray(m["time"][:], float)
        th = np.asarray(
            ((t0 + pd.to_timedelta(ts, unit="s")) - an) / pd.Timedelta(hours=1), float
        )
        snap = np.flatnonzero(th > 0)
    days = np.isfinite(HH).sum(0).astype(np.int16)
    with np.errstate(all="ignore"):
        mhh = np.where(days > 0, np.nansum(HH, 0) / np.maximum(days, 1), np.nan).astype(
            np.float32
        )
    log(
        f"zsmax: {tm.size} blocks, {nd} tidal days; {snap.size} zs snapshots after {an}"
    )
    return mhh, days, nd, snap


def load_mesh(d: Path):
    import netCDF4

    with netCDF4.Dataset(d / "sfincs.nc") as g:
        g.set_auto_mask(False)
        G = {k: g[k][:] for k in ("level", "mask")}
        G["x"], G["y"] = g["mesh2d_face_x"][:], g["mesh2d_face_y"][:]
        dx0 = float(g.dx)
    G["dx"] = dx0 / 2.0 ** (G["level"] - 1)
    with netCDF4.Dataset(d / "sfincs_subgrid.nc") as s:
        s.set_auto_mask(False)
        G["z_zmin"], G["z_zmax"] = s["z_zmin"][:], s["z_zmax"][:]
    return G


def run(
    d: Path,
    bed: str,
    name: str,
    out: Path,
    q,
    deep,
    high,
    noisy_std,
    workers,
    spinup_d=SPINUP_D,
    day_h=DAY_H,
):
    import netCDF4

    t00 = time.time()
    G = load_mesh(d)
    act = G["mask"] > 0
    mhh, days, nd, snap = tide_stats(d, spinup_d, day_h)
    wet = act & (days >= (nd + 1) // 2) & np.isfinite(mhh)
    W = np.flatnonzero(wet)
    log(f"{act.sum()} active, {W.size} wet (>= {(nd + 1) // 2} of {nd} days)")
    r = flag(
        G["x"][W],
        G["y"][W],
        G["dx"][W],
        mhh[W],
        G["z_zmin"][W],
        G["z_zmax"][W],
        q=q,
        deep=deep,
        high=high,
        workers=workers,
    )
    sel = np.flatnonzero(r["flagged"])
    F = W[sel]
    nbW = r["nb"][sel]
    nb_faces = np.where(nbW < W.size, W[np.minimum(nbW, W.size - 1)], -1)
    log(f"flagged {F.size} (deep {int(r['deep'].sum())})")

    def snaps():
        with netCDF4.Dataset(d / "sfincs_map.nc") as m:
            m.set_auto_mask(False)
            zb = m["zb"][:]
            for i in snap:
                z = m["zs"][i].astype(np.float32)
                yield np.where((z > -1000) & (z - zb > 0.01), z, np.nan)

    sstd, sn = snapshot_residual_std(snaps(), F, nb_faces)
    cls = classify(sstd, sn, noisy_std)
    stem = f"{bed}_{name}"
    out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out / f"{stem}_noisy.npz",
        face=F.astype(np.int32),
        mhh=mhh[F],
        ref=r["ref"][sel],
        excess=r["excess"][sel].astype(np.float32),
        snap_std=sstd.astype(np.float32),
        snap_n=sn,
        cls=cls,
        n_faces=np.int64(act.size),
        n_active=np.int64(act.sum()),
        q=q,
        deep=deep,
        high=high,
        noisy_std=noisy_std,
        run_dir=str(d),
        bed=bed,
    )
    full = np.zeros(act.size, bool)
    full[F] = True
    np.save(out / f"{stem}_noisy.npy", full[act])
    ex = r["excess"][sel]
    summ = dict(
        run_dir=str(d),
        bed=bed,
        run=name,
        q=q,
        deep_m=deep,
        high_m=high,
        noisy_std_m=noisy_std,
        tidal_days=nd,
        snapshots=int(snap.size),
        active=int(act.sum()),
        wet=int(W.size),
        wet_with_ref=int(np.isfinite(r["ref"]).sum()),
        ref_from_submerged=int(r["ref_is_submerged"].sum()),
        flagged=int(F.size),
        flagged_gt025=int((ex > 0.25).sum()),
        noisy=int((cls == CLS_NOISY).sum()),
        quiet=int((cls == CLS_QUIET).sum()),
        unclassed=int((cls == CLS_NONE).sum()),
        km2_flagged=round(float((G["dx"][F] ** 2).sum() / 1e6), 3),
        minutes=round((time.time() - t00) / 60, 1),
    )
    (out / f"{stem}_noisy.json").write_text(json.dumps(summ, indent=1) + "\n")
    log(json.dumps(summ))
    return summ


def union(out_npy: Path, npzs: list[Path], mesh_dir: Path | None = None):
    """OR several runs' lists (same mesh) into one active-face bool array."""
    fulls, n_act = [], set()
    for p in npzs:
        z = np.load(p)
        full = np.zeros(int(z["n_faces"]), bool)
        full[z["face"]] = True
        fulls.append(full)
        n_act.add(int(z["n_active"]))
    if len({f.size for f in fulls}) != 1 or len(n_act) != 1:
        raise SystemExit("--union: the lists come from different meshes / masks")
    u = np.logical_or.reduce(fulls)
    # active-face order needs the mask: take it from the first list's run dir
    import netCDF4

    rd = Path(mesh_dir) if mesh_dir else Path(str(np.load(npzs[0])["run_dir"]))
    with netCDF4.Dataset(rd / "sfincs.nc") as g:
        act = g["mask"][:] > 0
    if int(act.sum()) != n_act.pop():
        raise SystemExit(f"--union: {rd} mask does not match the lists' active count")
    np.save(out_npy, u[act])
    log(f"union of {len(npzs)} lists: {int(u.sum())} faces -> {out_npy}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("run_dir", nargs="?", help="a finished tide run (sfincs_map.nc)")
    ap.add_argument("--bed", help="bed label for the file stem (e.g. nj2_bed2012)")
    ap.add_argument("--run", help="run label for the stem (default: the run dir name)")
    ap.add_argument("--out", default=str(REPO / "logs" / "noisy_faces"))
    ap.add_argument(
        "--q", type=float, default=0.2, help="neighbour quantile (0.5 = median)"
    )
    ap.add_argument("--deep", type=float, default=0.10, help="min mhh - z_zmin (m)")
    ap.add_argument("--high", type=float, default=0.10, help="min excess over ref (m)")
    ap.add_argument(
        "--noisy-std", type=float, default=0.05, help="snapshot residual std (m)"
    )
    ap.add_argument("--spinup-days", type=float, default=SPINUP_D)
    ap.add_argument("--day-hours", type=float, default=DAY_H)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--union", metavar="OUT_NPY", help="OR the given _noisy.npz lists")
    ap.add_argument("lists", nargs="*", help="with --union: the _noisy.npz files")
    a = ap.parse_args(argv)
    if a.union:
        npzs = ([a.run_dir] if a.run_dir else []) + a.lists
        if not npzs:
            ap.error("--union needs at least one _noisy.npz")
        union(Path(a.union), [Path(p) for p in npzs])
        return
    if not a.run_dir or not a.bed:
        ap.error("need <run_dir> and --bed")
    d = Path(a.run_dir).resolve()
    run(
        d,
        a.bed,
        a.run or d.name,
        Path(a.out),
        a.q,
        a.deep,
        a.high,
        a.noisy_std,
        a.workers,
        a.spinup_days,
        a.day_hours,
    )


if __name__ == "__main__":
    main()
