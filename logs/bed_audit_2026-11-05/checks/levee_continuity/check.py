"""Bed audit check `levee_continuity` (2026-11-06): does each NLD levee / floodwall system keep water out of its
leveed area in the MODEL (bed + weir file) as well as the ground + the levee would?

Rule and calibration: README.md here. The helpers are in lib.py.

  python -I check.py --bed experiments/v4_refreeze_swz/_subgrid_v1_1c --label v1_1c --out out/v1_1c/levee_continuity.csv
  python -I check.py --bed ... --label modern --weir data/structures_v4/sfincs.weir --out ...
  # extra weir files on the same bed (one mesh load, one pixel pass), written to calibration/<label>__<name>.csv:
  python -I check.py --bed ... --label modern --out ... --extra-weir er_rw_2012=<path> --extra-weir er_rw_2026=<path>

--weir: the weir file the bed's runs stage (default per label: v1_1c -> data/structures_v4/sfincs_overpeck_open.weir,
v1.1's premier; anything else -> data/structures_v4/sfincs.weir, the template's). `--weir none` = bed only.
--overlay-min / --overlay are accepted (the runner passes them) and IGNORED: this check reads the subgrid TABLES
(`uv_zmin`), which a pixel overlay does not change.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lib as Lb  # noqa: E402

REPO = Lb.REPO
S4 = REPO / "data/structures_v4"
DEFAULT_WEIR = {"v1_1c": S4 / "sfincs_overpeck_open.weir"}
SOURCE = ("USACE National Levee Database (public FeatureServer, pulled 2026-11-04: routes, floodwalls, closures, "
          "leveed areas; Z US ft NAVD88) vs the bed's mesh tables + weir file")
PE = REPO / "logs/power_exposure_2026-11-02"


def assets():
    A = pd.concat([pd.read_csv(PE / f) for f in ("substations_exposure.csv", "plants_exposure.csv")])
    A = A[np.isfinite(A.lon) & np.isfinite(A.lat)].reset_index(drop=True)
    A["name"] = A["name"].fillna("unnamed " + A["asset"].astype(str) + " " + A["id"].astype(str)).astype(str)
    from pyproj import Transformer
    x, y = Transformer.from_crs(4326, 32618, always_xy=True).transform(A.lon.values, A.lat.values)
    A["x"], A["y"] = x, y
    return A


def pixel_doors(bed_dir, mesh, level_bed, nld, log):
    """Per system: the pixel door (ground + NLD lines at NLD Z) and where it opens. Weir-independent."""
    from shapely import contains_xy
    pb = Lb.PixelBed(bed_dir)
    la = nld["nld_leveed_areas"]
    lines_by = {}
    for lyr in ("nld_routes", "nld_floodwalls", "nld_closures"):
        for r in nld[lyr].itertuples():
            lines_by.setdefault(r.sid, []).extend(Lb.lines_xyz(r.geometry))
    out = {}
    for r in la.itertuples():
        t0 = time.time()
        poly = r.geometry.buffer(-Lb.SHRINK)
        if poly.is_empty:
            out[r.sid] = dict(pixel_door=np.nan, why="area vanishes when shrunk 20 m")
            continue
        x0, y0, x1, y1 = r.geometry.bounds
        a, t = pb.window(x0 - Lb.MARGIN, y0 - Lb.MARGIN, x1 + Lb.MARGIN, y1 + Lb.MARGIN)
        if a.size == 0:
            out[r.sid] = dict(pixel_door=np.nan, why="outside the bed raster")
            continue
        b = Lb.burn(a, t, lines_by.get(r.sid, []))
        px, py = Lb.pixel_centres(a.shape, t)
        inside = contains_xy(poly, px, py)
        # seeds: tidal water = low pixels whose nearest face reaches the boundary below SEED_LEVEL on the bed alone
        cand = (a <= Lb.SEED_Z) & ~inside & np.isfinite(a)
        seeds = np.zeros(a.shape, bool)
        if cand.any():
            _, fi = mesh.tree.query(np.c_[px[cand], py[cand]])
            seeds[cand] = level_bed[fi] <= Lb.SEED_LEVEL
        if not seeds.any() or not inside.any():
            out[r.sid] = dict(pixel_door=np.nan, why="no tidal seed in the window" if not seeds.any() else "no pixel inside")
            continue
        F = Lb.priority_flood(b, seeds)
        fv = F[inside]
        dmin = float(fv.min())
        dq, j = Lb.wquantile(fv, np.ones(fv.size), Lb.Q)
        d = dq
        out[r.sid] = dict(pixel_door=d if np.isfinite(d) else np.nan, pixel_min=dmin if np.isfinite(dmin) else np.nan,
                          px_x=float(px[inside][j]), px_y=float(py[inside][j]),
                          n_seed=int(seeds.sum()), n_inside=int(inside.sum()), win=list(a.shape))
        log(f"  pixel {r.sid} {r.SYSTEM_NAME[:40]:40s} door {d:6.2f}  win {a.shape}  {time.time() - t0:5.1f} s")
    return out


def crest_share(mesh, thr, nld, sandy):
    """Per system: share of the NLD route's crossed links the model carries to min(NLD crest, Sandy) - TOL, and the
    lowest uncarried crossing."""
    from weir_on_mesh import snap
    out = {}
    mx = 0.5 * (mesh.fx[mesh.nm] + mesh.fx[mesh.nmu])
    my = 0.5 * (mesh.fy[mesh.nm] + mesh.fy[mesh.nmu])
    for r in nld["nld_routes"].itertuples():
        hit = {}
        for L in Lb.lines_xyz(r.geometry):
            L = L[np.isfinite(L[:, 2])]
            if len(L) < 2:
                continue
            idx = np.where(mesh.ok & (mx > L[:, 0].min() - 600) & (mx < L[:, 0].max() + 600)
                           & (my > L[:, 1].min() - 600) & (my < L[:, 1].max() + 600))[0]
            h, _ = snap(L, mesh.fx, mesh.fy, mesh.active, mesh.nm[idx], mesh.nmu[idx], mesh.uv_zmin[idx])
            for i, c in h.items():
                hit[int(idx[i])] = max(hit.get(int(idx[i]), -9999.0), c)
        if not hit:
            out[r.sid] = dict(n_cross=0)
            continue
        ids = np.array(list(hit))
        crest = np.array([hit[i] for i in ids])
        s = sandy.get(r.sid, np.nan)
        need = np.minimum(crest, s) if np.isfinite(s) else crest
        carried = thr[ids] >= need - Lb.TOL
        j = ids[~carried][np.argmin(thr[ids[~carried]])] if (~carried).any() else -1
        out[r.sid] = dict(n_cross=int(ids.size), share_carried=float(carried.mean()),
                          worst_link=int(j), worst_thr=float(thr[j]) if j >= 0 else np.nan,
                          worst_need=float(need[ids == j][0]) if j >= 0 else np.nan)
    return out


def low_spot(polys, area_geom):
    """Lowest weir vertex on any weir polyline within 300 m of the leveed area (the place a reviewer should look)."""
    from shapely.geometry import LineString
    near = area_geom.buffer(300.0)
    best = None
    for name, rows in polys:
        if len(rows) < 2 or not LineString(rows[:, :2]).intersects(near):
            continue
        from shapely import contains_xy
        ins = contains_xy(near, rows[:, 0], rows[:, 1])
        if not ins.any():
            continue
        k = np.where(ins)[0][np.argmin(rows[ins, 2])]
        if best is None or rows[k, 2] < best[3]:
            best = (name, float(rows[k, 0]), float(rows[k, 1]), float(rows[k, 2]))
    return best


def evaluate(label, mesh, nld, A, pix, weir, log):
    from pyproj import Transformer
    from shapely import contains_xy
    to_ll = Transformer.from_crs(32618, 4326, always_xy=True)
    kept, hit, polys = mesh.snap_weir(weir)
    thr = mesh.thresholds(kept)
    t0 = time.time()
    level, door = mesh.minimax(thr)
    log(f"  minimax ({len(kept)} kept weir links): {time.time() - t0:.0f} s")
    rk = nld["ranked"]
    sandy = {s: float(rk.loc[s, "sandy_level_med"]) for s in rk.index if np.isfinite(rk.loc[s, "sandy_level_med"])}
    cs = crest_share(mesh, thr, nld, sandy)
    rows, summary = [], []
    for r in nld["nld_leveed_areas"].itertuples():
        sid = r.sid
        poly = r.geometry.buffer(-Lb.SHRINK)
        fin = np.where(mesh.active & contains_xy(poly, mesh.fx, mesh.fy))[0] if not poly.is_empty else np.array([], int)
        nm_ = str(r.SYSTEM_NAME)
        area_km2 = float(r.LEVEED_AREA_SQ_MI) * 2.58999 if np.isfinite(r.LEVEED_AREA_SQ_MI) else r.geometry.area / 1e6
        s = sandy.get(sid, np.nan)
        p = pix.get(sid, {})
        pd_ = p.get("pixel_door", np.nan)
        c = cs.get(sid, {})
        share = c.get("share_carried", np.nan)
        base = dict(check="levee_continuity", id=f"NLD:{sid}", area_m2=round(area_km2 * 1e6),
                    sandy_peak_m=round(s, 2) if np.isfinite(s) else "", source=SOURCE)
        if fin.size == 0:
            cx, cy = r.geometry.representative_point().coords[0]
            lo, la_ = to_ll.transform(cx, cy)
            rows.append(dict(base, lon=round(lo, 6), lat=round(la_, 6), severity="low",
                             kind="undecidable_no_active_face_inside", metric="", value="", expected="", units="",
                             note=f"{nm_}: no active face centre inside the leveed area (shrunk 20 m)", fix=""))
            summary.append(dict(sid=sid, name=nm_, mesh_door=np.nan, pixel_door=pd_, sandy=s, share=share, flag=""))
            continue
        md_min = float(level[fin].min())
        md, j = Lb.wquantile(level[fin], mesh.area[fin], Lb.Q)
        k = fin[j]
        lk = int(door[k])
        if lk >= 0:
            dx = 0.5 * (mesh.fx[mesh.nm[lk]] + mesh.fx[mesh.nmu[lk]])
            dy = 0.5 * (mesh.fy[mesh.nm[lk]] + mesh.fy[mesh.nmu[lk]])
        else:
            dx, dy = mesh.fx[k], mesh.fy[k]
        lo, la_ = to_ll.transform(dx, dy)
        expd_parts = [v for v in (pd_, s) if np.isfinite(v)]
        expd = min(expd_parts) if expd_parts else np.nan
        # assets: inside the leveed area, else nearest to the door within 2 km
        ins_a = contains_xy(r.geometry, A.x.values, A.y.values)
        dA = np.hypot(A.x.values - dx, A.y.values - dy)
        if ins_a.any():
            near, akm = "; ".join(A.name.values[ins_a][:3]) + " (inside)", 0.0
        elif dA.min() <= 2000:
            near, akm = A.name.values[np.argmin(dA)], round(float(dA.min()) / 1000, 2)
        else:
            near, akm = "", ""
        flagged = np.isfinite(expd) and np.isfinite(md) and md < expd - Lb.TOL
        wet_share = float(mesh.area[fin][level[fin] < expd - Lb.TOL].sum() / mesh.area[fin].sum()) if np.isfinite(expd) else np.nan
        not_in_flow = not (np.isfinite(share) and share >= 0.5)
        summary.append(dict(sid=sid, name=nm_, mesh_door=round(md, 2) if np.isfinite(md) else np.nan,
                            pixel_door=round(pd_, 2) if np.isfinite(pd_) else np.nan, sandy=s,
                            share=round(share, 2) if np.isfinite(share) else np.nan, n_cross=c.get("n_cross", 0),
                            mesh_min=round(md_min, 2), pixel_min=round(p.get("pixel_min", np.nan), 2),
                            share_below=round(wet_share, 3) if np.isfinite(wet_share) else np.nan,
                            flag=("levee_not_in_flow" if not_in_flow else "door_below_ground") if flagged else "",
                            door_lon=round(lo, 5), door_lat=round(la_, 5)))
        if flagged:
            if np.isfinite(s) and s <= md:
                sev = "low"            # Sandy did not reach the model's door
            elif near and (ins_a.any() or akm <= 1.5):
                sev = "high"           # a power asset behind (or by) the levee
            elif np.isfinite(s) and np.isfinite(pd_) and s < pd_:
                sev = "medium"         # the levee + ground would have HELD Sandy; the model lets it in
            else:
                sev = "low"            # Sandy overtopped the real line too: timing / depth only
            kind = "levee_not_in_flow" if not_in_flow else "door_below_ground"
            how = ("the levee is not a weir here: the flow crosses its line at the bed's pooled level "
                   f"(carried on {share:.0%} of {c.get('n_cross', 0)} crossed links)" if not_in_flow else
                   "a gap / flank / door the weir lines leave open")
            rows.append(dict(base, lon=round(lo, 6), lat=round(la_, 6), severity=sev, kind=kind,
                             metric="mesh door: still-water level at which 2 % of the leveed area has joined open water (m)",
                             value=round(md, 2),
                             expected=f"{expd:.2f} = min(pixel door, NLD lines at crest, {pd_:.2f}; Sandy {s:.2f})",
                             units="m NAVD88", near_asset=near, asset_km=akm,
                             note=f"{nm_} ({area_km2:.2f} km2): {how}; first water in at {md_min:.2f} m (ground + levee: "
                                  f"{p.get('pixel_min', np.nan):.2f}); {wet_share:.0%} of the area joins below {expd - Lb.TOL:.2f} m",
                             fix="weir along the NLD line + tie-ins / ground guards (the 2026-11-05 Elizabeth pass)",
                             door_m=round(md, 2), pixel_door_m=round(pd_, 2) if np.isfinite(pd_) else "",
                             first_door_m=round(md_min, 2), area_share_below=round(wet_share, 3),
                             share_carried=round(share, 2) if np.isfinite(share) else ""))
        elif any(name for name, _ in polys) and np.isfinite(md):
            ls = low_spot(polys, r.geometry)
            if ls is not None and ls[3] < (expd if np.isfinite(expd) else md):
                llo, lla = to_ll.transform(ls[1], ls[2])
                rows.append(dict(base, lon=round(llo, 6), lat=round(lla, 6), severity="low", kind="weir_low_spot",
                                 metric="lowest weir vertex within 300 m of the leveed area (m)", value=round(ls[3], 2),
                                 expected=f"mesh door {md:.2f} holds (>= {expd:.2f} - {Lb.TOL})", units="m NAVD88",
                                 near_asset=near, asset_km=akm,
                                 note=f"{nm_}: the area holds in the model; its lowest weir vertex is on '{ls[0]}' — "
                                      "eye-check that the line is right there (a ditch / culvert under a ground line?)",
                                 fix="", door_m=round(md, 2), pixel_door_m=round(pd_, 2) if np.isfinite(pd_) else "",
                                 share_carried=round(share, 2) if np.isfinite(share) else ""))
    return pd.DataFrame(rows), pd.DataFrame(summary), dict(kept=len(kept), crossed=len(hit))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bed", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--weir", default=None)
    ap.add_argument("--extra-weir", action="append", default=[], help="NAME=PATH (or NAME=none)")
    ap.add_argument("--overlay-min", action="append", default=[])
    ap.add_argument("--overlay", action="append", default=[])
    a = ap.parse_args()
    bed = Path(a.bed) if Path(a.bed).is_absolute() else REPO / a.bed

    def log(m):
        print(m, flush=True)

    if a.overlay_min or a.overlay:
        log(f"  note: overlays {a.overlay_min + a.overlay} ignored (this check reads the subgrid tables)")
    weir = a.weir or str(DEFAULT_WEIR.get(a.label, S4 / "sfincs.weir"))
    weir = None if weir == "none" else weir
    t0 = time.time()
    mesh = Lb.Mesh(bed)
    log(f"  mesh {mesh.fx.size:,} faces, {mesh.ok.sum():,} active links: {time.time() - t0:.0f} s")
    nld = Lb.load_nld()
    A = assets()
    level_bed, _ = mesh.minimax(mesh.uv_zmin.copy())
    pcache = HERE / "cache" / f"pixel_doors_{bed.name}.json"
    if pcache.exists() and pcache.stat().st_mtime > (bed / "subgrid/dep_subgrid_merged.tif").stat().st_mtime:
        pix = json.loads(pcache.read_text())
        log(f"  pixel doors from {pcache}")
    else:
        pix = pixel_doors(bed, mesh, level_bed, nld, log)
        pcache.parent.mkdir(exist_ok=True)
        pcache.write_text(json.dumps(pix, indent=1))
    runs = [("main", weir, Path(a.out))] + [
        (k, None if v == "none" else v, HERE / "calibration" / f"{a.label}__{k}.csv")
        for k, v in (e.split("=", 1) for e in a.extra_weir)]
    for name, w, out in runs:
        log(f"== {a.label} / {name}: weir {w}")
        E, Ssum, info = evaluate(a.label, mesh, nld, A, pix, w, log)
        out.parent.mkdir(parents=True, exist_ok=True)
        if len(E):
            order = {"high": 0, "medium": 1, "low": 2}
            E = E.sort_values("severity", key=lambda c: c.map(order))
        E.to_csv(out, index=False)
        sp = HERE / "summary" / f"{a.label}__{name}_systems.csv"
        sp.parent.mkdir(exist_ok=True)
        Ssum.to_csv(sp, index=False)
        log(f"   {out}: {len(E)} rows {E.severity.value_counts().to_dict() if len(E) else {}} "
            f"{E.kind.value_counts().to_dict() if len(E) else {}}; weir links kept {info['kept']}")


if __name__ == "__main__":
    main()
