"""Chester levee (NLD 4805000005) REDRAWN so Chester Creek keeps its channel (user 11-14).

What was wrong (READ.md §3): the 11-12 line is the NLD route, which runs ON the inner bank of the creek's meander
loop. On the 1.1.0 mesh the creek there is one 25-50 m face wide, so a line on the bank passes through the channel
faces and the engine blocks 18 creek-to-creek links (`cand_chester_links.png`): the creek is dammed and its 45.8 m3/s
inflow (source 26, 929 m upstream) ponds to 5.24 m.

The redraw keeps the NLD alignment's SIDE and crest but moves the line onto the mesh-cell edges between the leveed
ground and the creek, so it can only cross links from creek faces to leveed faces (the house method for impoundment
outlines, README "How the lines were made"): the line is the outline of the union of the leveed area's own cells
(face centre inside the NLD leveed-area polygon AND z_zmin >= CREEK_Z), cut to the stretch that faces the creek,
plus the two end ties into high ground. Crest at each vertex = the NLD crest of the nearest 11-12 vertex (the NLD
route Z, gates closed), so the line is the same levee at the same height, ~10-40 m landward, on the mesh's terms.

Read-only on every input. Writes chester_redraw.weir (+ _links.png via chester_links.py after engine_count.py).
    source logs/weirs_dikes_levees_2026-11-12/env.sh; python -I logs/nj2_edges_2026-11-14/dikes_levees/chester_redraw.py
"""
import sys
from pathlib import Path

import numpy as np
import geopandas as gpd
import shapely
import netCDF4

R = Path("/cache/home/tpj8/nj_bight_sfincs")
H = Path(__file__).resolve().parent
RUN = R / "experiments/v4_refreeze_swz_v11/p4-premier+weir-elizabeth-rahway"
sys.path.insert(0, str(R / "logs/refreeze_2026-10-06/structures"))
from weir_on_mesh import read_weir  # noqa: E402

CREEK_Z = 1.0  # m: faces below this (z_zmin) in the window are the creek; the leveed ground reads 2.5-4.5 m
X0, X1, Y0, Y1 = 467900, 469300, 4410900, 4411900

nc = netCDF4.Dataset(RUN / "sfincs.nc")
A = {k: float(nc.getncattr(k)) for k in ["x0", "y0", "dx", "dy", "rotation"]}
n, m, lev, msk = (np.asarray(nc[k][:]).astype(np.int64) for k in ["n", "m", "level", "mask"])
fx, fy = np.asarray(nc["mesh2d_face_x"][:]), np.asarray(nc["mesh2d_face_y"][:])
nc.close()
sg = netCDF4.Dataset(RUN / "sfincs_subgrid.nc")
z_zmin = np.asarray(sg["z_zmin"][:], "f8")
sg.close()
cr, sr = np.cos(np.deg2rad(A["rotation"])), np.sin(np.deg2rad(A["rotation"]))


def cell(i):
    d = A["dx"] / 2 ** (lev[i] - 1)
    e = A["dy"] / 2 ** (lev[i] - 1)
    u = np.array([m[i] - 1, m[i], m[i], m[i] - 1]) * d
    v = np.array([n[i] - 1, n[i] - 1, n[i], n[i]]) * e
    return shapely.Polygon(np.c_[A["x0"] + cr * u - sr * v, A["y0"] + sr * u + cr * v])


win = np.where((fx > X0) & (fx < X1) & (fy > Y0) & (fy < Y1) & (msk > 0))[0]
# self-check: the cell polygon's centroid is the face centre
c0 = cell(win[0]).centroid
assert abs(c0.x - fx[win[0]]) < 0.01 and abs(c0.y - fy[win[0]]) < 0.01, (c0, fx[win[0]], fy[win[0]])

la = gpd.read_file(R / "logs/walls_inventory_2026-11-04/walls_inventory.gpkg", layer="nld_leveed_areas").to_crs(32618)
lap = shapely.unary_union(list(la[la.SYSTEM_ID == 4805000005].geometry))
inside = shapely.contains_xy(lap, fx[win], fy[win])
pen = win[inside & (z_zmin[win] >= CREEK_Z)]
creek = win[z_zmin[win] < CREEK_Z]
print(f"leveed cells: {pen.size} (of {inside.sum()} face centres in the NLD polygon; "
      f"{int((inside & (z_zmin[win] < CREEK_Z)).sum())} creek faces inside it left OUT)")
P = shapely.unary_union([cell(i) for i in pen]).buffer(0.01).buffer(-0.01)
assert P.geom_type == "Polygon", P.geom_type
CR = shapely.unary_union([cell(i) for i in creek]).buffer(0.5)   # touches the shared edges

# Walk the outline from the NLD route's west end, keep the stretch that borders the creek + one cell edge beyond
ring = np.array(P.exterior.coords)[:-1]
ring = np.array(shapely.Polygon(ring).simplify(0.0).exterior.coords)[:-1]
segs = [shapely.LineString([ring[k], ring[(k + 1) % len(ring)]]) for k in range(len(ring))]
on_creek = np.array([CR.contains(s.interpolate(0.5, normalized=True)) for s in segs])
print(f"outline: {len(segs)} edges, {on_creek.sum()} face the creek")
# the longest circular run of creek-facing edges
k0 = int(np.argmin(on_creek)) if not on_creek.all() else 0
order = [(k0 + j) % len(segs) for j in range(len(segs))]
runs, cur = [], []
for k in order:
    if on_creek[k]:
        cur.append(k)
    elif cur:
        runs.append(cur)
        cur = []
if cur:
    runs.append(cur)
runs.sort(key=len, reverse=True)
print("creek-facing runs (edges):", [len(r) for r in runs])
main = runs[0]
# extend one edge each side (the tie into the leveed ground's landward edge)
first, last = (main[0] - 1) % len(segs), (main[-1] + 1) % len(segs)
ks = [first] + main + [last]
pts = [segs[ks[0]].coords[0]] + [segs[k].coords[1] for k in ks]
line = np.array(pts)
# crest: NLD crest of the nearest 11-12 vertex
old = read_weir(R / "logs/weirs_dikes_levees_2026-11-12/cand_chester.weir")[0][1]
from scipy.spatial import cKDTree  # noqa: E402

dd, ii = cKDTree(old[:, :2]).query(line)
crest = old[ii, 2]
print(f"new line: {len(line)} vertices, {shapely.LineString(line).length:.0f} m (11-12: "
      f"{shapely.LineString(old[:, :2]).length:.0f} m); offset from the 11-12 line p50/max {np.median(dd):.0f}/"
      f"{dd.max():.0f} m; crest {crest.min():.2f}/{np.median(crest):.2f}/{crest.max():.2f}")
others = [r for r in runs[1:]]
if others:
    print("⚠️ other creek-facing runs NOT covered (edges, first vertex):",
          [(len(r), tuple(np.round(segs[r[0]].coords[0], 1))) for r in others])
with open(H / "chester_redraw.weir", "w") as f:
    f.write("chester_nld4805000005_redraw_2026-11-14\n")
    f.write(f"{len(line)} 4\n")
    for (x, y), c in zip(line, crest):
        f.write(f"{x:.1f} {y:.1f} {c:.3f} 0.60\n")
print(H / "chester_redraw.weir")
