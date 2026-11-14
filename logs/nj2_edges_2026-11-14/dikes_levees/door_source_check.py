"""Static door check of a weir set, WITH the discharge-source check (user 11-14; the class of error behind Chester).

    source logs/weirs_dikes_levees_2026-11-12/env.sh
    python -I logs/nj2_edges_2026-11-14/dikes_levees/door_source_check.py [--run <rundir>] \
        --base <premier weir> --set NAME=<combined weir> [--set NAME2=<combined weir 2>] [--radius 3000] [--rise 0.25]

Every weir file is reduced to the links the ENGINE keeps (engine_count.py, the float32 rule) and their crests; the
still-water level at which each face joins the forced boundary is the minimax path value on the mesh
(levee_continuity lib.Mesh.minimax, as s7_recommended.py). Read for each set against the base:

* SOURCES (new): every staged discharge source (sfincs_netsrcdisfile.nc) within --radius of any line ADDED by the set:
  the level at which the source's face joins the boundary, base vs set. A rise > --rise m means the line has put the
  source inside a closed ring (its inflow can only leave over a crest): flagged ENCLOSED. Chester's 11-12 line reads
  that way; this is the check that would have caught it before a run. Static: no inflow volume, no duration.
* REGIONS: the 21 over-reach regions of doors_regions.csv (spill = median face level; closed = level > MHHW + 0.10).
* LEVEES: the 2 % door of the four NLD leveed areas (shrunk 20 m), all faces and leveed ground only (z_zmin >= 1).
Writes door_source_<set>.csv / regions_<set>.csv / levees.csv here.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd
import shapely
import xarray as xr

R = Path("/cache/home/tpj8/nj_bight_sfincs")
H = Path(__file__).resolve().parent
SRC = R / "logs/weirs_dikes_levees_2026-11-12"
sys.path.insert(0, str(R / "logs/bed_audit_2026-11-05/checks/levee_continuity"))
import lib as Lb  # noqa: E402
from weir_on_mesh import read_weir  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--run", default=str(R / "experiments/v4_refreeze_swz_v11/p4-premier+weir-elizabeth-rahway"))
ap.add_argument("--base", required=True)
ap.add_argument("--set", action="append", required=True)
ap.add_argument("--radius", type=float, default=3000.0)
ap.add_argument("--rise", type=float, default=0.25)
a = ap.parse_args()
ENG = H / "engine"
ENG.mkdir(exist_ok=True)


def crests(wf):
    out = ENG / (Path(wf).name + ".crests.npz")
    if not out.exists() or out.stat().st_mtime < Path(wf).stat().st_mtime:
        r = subprocess.run([sys.executable, "-I", str(SRC / "engine_count.py"), a.run, str(Path(wf).resolve())],
                           cwd=ENG, capture_output=True, text=True, check=True)
        print("  ", [s for s in r.stdout.splitlines() if "ENGINE" in s][0].split("{")[0])
    d = np.load(out)
    return dict(zip(d["eu"].tolist(), d["eh"].tolist()))


mesh = Lb.Mesh(a.run)
base_k = crests(a.base)
print(f"base {Path(a.base).name}: {len(base_k)} engine u/v")
t0 = mesh.thresholds(base_k)
l0, _ = mesh.minimax(t0)
base_names = {n for n, _ in read_weir(a.base)}

s = xr.open_dataset(Path(a.run) / "sfincs_netsrcdisfile.nc")
sx, sy = s.x.values.astype(float), s.y.values.astype(float)
q = s.discharge.max("time").values
act = np.where(mesh.active)[0]
from scipy.spatial import cKDTree  # noqa: E402

_, j = cKDTree(np.c_[mesh.fx[act], mesh.fy[act]]).query(np.c_[sx, sy])
sface = act[j]

regp = gpd.read_file(R / "logs/tidal_reach_2026-11-09/out/regions.gpkg", layer="region_polygons")
regp = regp[(regp.bed == "12") & (regp.kind == "over")].to_crs(32618)
regc = pd.read_csv(R / "logs/tidal_reach_2026-11-09/out/regions.csv")
regc = regc[(regc.bed.astype(str) == "12") & (regc.kind == "over")].set_index("region_id")
la = gpd.read_file(R / "logs/walls_inventory_2026-11-04/walls_inventory.gpkg", layer="nld_leveed_areas").to_crs(32618)


def faces_in(g):
    x0, y0, x1, y1 = g.bounds
    idx = np.where(mesh.active & (mesh.fx > x0) & (mesh.fx < x1) & (mesh.fy > y0) & (mesh.fy < y1))[0]
    return idx[shapely.contains_xy(g, mesh.fx[idx], mesh.fy[idx])]


lev_rows = {}
for spec in a.set:
    name, wf = spec.split("=", 1)
    k = crests(wf)
    added = [(n, r) for n, r in read_weir(wf) if n not in base_names]
    print(f"set {name}: {len(k)} engine u/v ({len(k) - len(base_k):+d} vs base); {len(added)} added lines")
    l1, _ = mesh.minimax(mesh.thresholds(k))
    geoms = [(n, shapely.LineString(r[:, :2])) for n, r in added]
    rows = []
    for i in range(sx.size):
        p = shapely.Point(sx[i], sy[i])
        dn, dl = min(((n, g.distance(p)) for n, g in geoms), key=lambda t: t[1])
        if dl > a.radius:
            continue
        f = sface[i]
        rise = float(l1[f] - l0[f])
        rows.append(dict(source=i, qmax_m3s=round(float(q[i]), 2), x=round(sx[i], 1), y=round(sy[i], 1),
                         nearest_line=dn, d_line_m=round(dl), face=int(f), level_base=round(float(l0[f]), 2),
                         level_set=round(float(l1[f]), 2), rise_m=round(rise, 2),
                         flag="ENCLOSED: the source's inflow can only leave over a crest" if rise > a.rise else ""))
    src = pd.DataFrame(rows)
    src.to_csv(H / f"door_source_{name}.csv", index=False)
    print(src.to_string() if len(src) else "  no source within radius")
    rr = []
    for rid in pd.read_csv(SRC / "doors_regions.csv").region:
        f = faces_in(shapely.unary_union(list(regp[regp.region_id == rid].geometry)))
        ar = mesh.area[f]
        mh = regc.loc[rid].mhhw
        rr.append(dict(region=rid, km2=round(ar.sum() / 1e6, 3), mhhw=round(mh, 2),
                       spill_base=round(float(np.median(l0[f])), 2), spill_set=round(float(np.median(l1[f])), 2),
                       closed_set=round(float(np.sum(ar * (l1[f] > mh + 0.1)) / ar.sum()), 3)))
    rr = pd.DataFrame(rr)
    rr.to_csv(H / f"regions_{name}.csv", index=False)
    print(rr.to_string())
    print(f"  km2 closed (> MHHW+0.1): {float((rr.km2 * rr.closed_set).sum()):.2f} of {rr.km2.sum():.2f}")
    for sid in [1305000013, 4805000005, 1205000139, 1205000140]:
        f = faces_in(shapely.unary_union(list(la[la.SYSTEM_ID == sid].geometry)).buffer(-20))
        ar = mesh.area[f]

        def door(lv):
            o = np.argsort(lv[f])
            c = np.cumsum(ar[o]) / ar.sum()
            return round(float(lv[f][o][np.searchsorted(c, 0.02)]), 2)

        r_ = lev_rows.setdefault(sid, {"system": sid, "door_base": door(l0)})
        r_[f"door_{name}"] = door(l1)
        # the same door on the leveed GROUND only (z_zmin >= 1 m): a creek face inside the NLD polygon is not the
        # leveed area (Chester: 8 creek faces sit inside the shrunk polygon and read the creek's own level)
        g = f[mesh.z_zmin[f] >= 1.0]
        if g.size:
            o = np.argsort(l1[g])
            c = np.cumsum(mesh.area[g][o]) / mesh.area[g].sum()
            r_[f"door_ground_{name}"] = round(float(l1[g][o][np.searchsorted(c, 0.02)]), 2)
            r_[f"ground_min_{name}"] = round(float(l1[g].min()), 2)
lv = pd.DataFrame(lev_rows.values())
lv.to_csv(H / "levees.csv", index=False)
print(lv.to_string())
json.dump(dict(base=a.base, sets=a.set, radius=a.radius, rise=a.rise), open(H / "door_source_args.json", "w"))
