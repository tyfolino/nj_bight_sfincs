"""Hybrid modern footprints for Model 2.0's ring (nj2), with the power-asset guard (2026-11-14).

    python -I logs/nj2_bed2026_2026-11-14/hybrid_footprints_nj2.py        (repo root, sfincs env, compute node)

= logs/modern_round_c_2026-11-12/hybrid_footprints.py's rule UNCHANGED (roles 1-4; read its docstring), on a new
area and with one addition the user asked for on 11-12 ("Round c: keep the 39 big pre-2019 roofs; add an asset guard
(Wheelabrator Gloucester, Camden Cogen) before the burn"):

  5 usa_asset_guard  a pre-2019 USA polygon the rule would SWAP is KEPT where it overlaps an NJ power-asset polygon
                     (data/power_infra/{plant,substation}_polygons.geojson) and Microsoft release-2 polygons cover
                     less than HALF of that overlap (Microsoft draws much less roof there: the 11-12 big-roof weakness
                     the 1 ha guard misses because the USA polygon touches SOME MS polygon). The MS candidates are then
                     chosen against the guarded set, as for every retained USA polygon.
                     NOT on solar sites (user 11-14: panels are not buildings): a plant whose OSM plant:source contains
                     "solar" gets no guard; the round c rule alone decides there. EXCEPT, by name, CCMUA and Jersey
                     City DWP (user 11-14: OSM tags them solar, but their real buildings keep the guard).

AREA = (ring_new_full_v2edit.csv buffered 500 m) x NJ. The v4 layer was clipped to region_v4 x NJ; round c's README
asked for ring + 500 m so edge faces whose subgrid pixels reach past the ring see the same buildings.
NJ ONLY (user 11-04: buildings + developed-n 0.04 stay NJ only): both sources are NJ state files (USA Structures
NJ deliverable, Microsoft NewJersey.geojson); a polygon is kept when its representative point lies in the Census
cb_2023 NJ state polygon buffered 250 m (the 1:500k shoreline cuts waterfront piers off; the Hudson is ~1.2 km wide)
AND in no other state's polygon (NY / PA / DE). Every polygon dropped by that test is counted by state in the summary.

Inputs re-read from the raw files (as logs/modern_inputs_2026-11-04/footprints_compare.py made the v4 parquets):
  modern_2026/buildings_usa_structures/Deliverable20250913NJ.zip   data/buildings/raw/NewJersey.geojson
Outputs (NEW files; the v4 ones are not touched):
  /scratch/tpj8/nj_bight_sfincs_data/modern_2026/derived/round_c/footprints_hybrid_nj2.gpkg  (layer footprints)
  here: hybrid_nj2_summary.txt, hybrid_nj2_by_municipality.csv, hybrid_nj2_power_assets.csv
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pyproj  # noqa: F401
import geopandas as gpd
import pyogrio
import shapely

REPO = Path("/cache/home/tpj8/nj_bight_sfincs")
HERE = REPO / "logs/nj2_bed2026_2026-11-14"
M26 = Path("/scratch/tpj8/nj_bight_sfincs_data/modern_2026")
RING = REPO / "logs/v2_prep_2026-11-04/ring_new_full_v2edit.csv"
STATES = REPO / "logs/power_exposure_2026-11-02/census/cb_2023_us_state_500k.zip"
V4HYB = M26 / "derived/round_c/footprints_hybrid_v4.gpkg"
OUT = M26 / "derived/round_c/footprints_hybrid_nj2.gpkg"
CUT = pd.Timestamp("2019-01-01", tz="UTC")
NEAR, BIG, RING_BUF, NJ_BUF = 100.0, 1e4, 500.0, 250.0
GUARD_COVER = 0.5
SOLAR_EXEMPT = {"CCMUA", "Jersey City DWP"}  # plant names (data/power_infra/plant_polygons.geojson), user 11-14
NAMES = {1: "usa_post2019", 2: "usa_pre2019_kept", 3: "ms_swap", 4: "usa_bigroof", 5: "usa_asset_guard"}
L = []


def p(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    L.append(s)


# ---- area and the NJ test
r = pd.read_csv(RING)
ring = gpd.GeoSeries([shapely.Polygon(zip(r.lon, r.lat))], crs=4326).to_crs(32618).iloc[0]
st = gpd.read_file(f"zip://{STATES}").to_crs(32618)
nj = st[st.STATEFP == "34"].union_all()
others = st[st.STATEFP.isin(["36", "42", "10"])][["STUSPS", "geometry"]].reset_index(drop=True)
area = ring.buffer(RING_BUF).intersection(nj.buffer(NJ_BUF))
b = area.bounds
b_ll = tuple(gpd.GeoSeries([shapely.box(*b)], crs=32618).to_crs(4326).total_bounds)
p(f"area = (nj2 ring + {RING_BUF:.0f} m) x (NJ + {NJ_BUF:.0f} m): {area.area / 1e6:.0f} km2")


def clip(g, name):
    g = g[g.geometry.notna()].copy()
    g = g.iloc[np.sort(g.sindex.query(area, predicate="intersects"))].copy()
    rp = g.geometry.representative_point()
    in_nj = rp.within(nj.buffer(NJ_BUF)).to_numpy()
    j = gpd.sjoin(gpd.GeoDataFrame(geometry=rp.values, crs=32618), others, predicate="within", how="left")
    j = j[~j.index.duplicated()]
    other = j.STUSPS.fillna("").to_numpy()
    keep = in_nj & (other == "")
    drop = pd.Series(np.where(~in_nj, "outside NJ+250m", other))[~keep].value_counts().to_dict()
    p(f"{name}: {len(g):,} touch the area; kept {int(keep.sum()):,}; dropped by the NJ test {drop}")
    g = g[keep].copy()
    g["a_m2"] = g.area
    return g.reset_index(drop=True)


usa = pyogrio.read_dataframe(f"/vsizip/{M26}/buildings_usa_structures/Deliverable20250913NJ.zip/NJ_Structures.gdb",
                             bbox=b_ll, columns=["IMAGE_DATE"]).to_crs(32618)
usa = clip(usa, "USA")
usa["IMAGE_DATE"] = pd.to_datetime(usa.IMAGE_DATE, utc=True, errors="coerce")
ms = pyogrio.read_dataframe(REPO / "data/buildings/raw/NewJersey.geojson", bbox=b_ll,
                            columns=["release"]).to_crs(32618)
ms = clip(ms, "MS")
pre = (usa.IMAGE_DATE < CUT).to_numpy()
p(f"USA {len(usa):,} ({usa.a_m2.sum() / 1e6:.1f} km2): pre-2019 {pre.sum():,} ({usa.a_m2[pre].sum() / 1e6:.1f} km2)")
p(f"MS  {len(ms):,}: release 2 {(ms.release == 2).sum():,}, release 1 {(ms.release == 1).sum():,}")

# ---- the round c rule (hybrid_footprints.py, unchanged)
u_pre = usa[pre]
j = gpd.sjoin_nearest(u_pre[["geometry"]], ms[["release", "geometry"]], how="left", max_distance=NEAR, distance_col="d")
r2near = j.groupby(level=0)["release"].apply(lambda s: bool((s == 2).any()))
swap = np.zeros(len(usa), bool)
swap[r2near.index[r2near.to_numpy()]] = True
hit_any = np.zeros(len(usa), bool)
hit_r2 = np.zeros(len(usa), bool)
qi, qj = ms.sindex.query(usa.geometry[swap].values, predicate="intersects")
sw_i = np.flatnonzero(swap)
hit_any[sw_i[np.unique(qi)]] = True
hit_r2[sw_i[np.unique(qi[(ms.release.to_numpy() == 2)[qj]])]] = True
own_r1 = swap & hit_any & ~hit_r2
swap &= ~own_r1
p(f"SWAPPED by the rule: {swap.sum():,} ({usa.a_m2[swap].sum() / 1e6:.1f} km2); own counterpart release-1 only "
  f"(not swapped): {own_r1.sum():,}")
big = swap & ~hit_any & (usa.a_m2.to_numpy() >= BIG)
p(f"big-roof guard (role 4): {big.sum():,} ({usa.a_m2[big].sum() / 1e6:.2f} km2)")

# ---- NEW: the power-asset guard (role 5)
pa = []
for klass, fn in (("p", "plant"), ("s", "substation")):
    g = gpd.read_file(REPO / f"data/power_infra/{fn}_polygons.geojson").to_crs(32618)
    g["asset"] = klass + g.id.astype(str)
    g["aname"] = g.get("name", pd.Series([""] * len(g))).fillna("")
    # user 11-14: solar arrays are NOT buildings -> no guard there (OSM plant:source contains "solar"; 677 plants)
    g["solar"] = g["plant_source"].fillna("").str.contains("solar", case=False) if "plant_source" in g else False
    # user 11-14: OSM tags these two as solar, but their real buildings keep the guard (exempt BY NAME)
    g.loc[g["aname"].isin(SOLAR_EXEMPT), "solar"] = False
    pa.append(g[["asset", "aname", "solar", "geometry"]])
pa = gpd.GeoDataFrame(pd.concat(pa, ignore_index=True), crs=32618)
pa["geometry"] = pa.geometry.make_valid()
pa = pa[pa.geometry.representative_point().within(nj) & pa.intersects(area)].reset_index(drop=True)
ms2 = ms[ms.release == 2].reset_index(drop=True)
guard = np.zeros(len(usa), bool)
grows = []
cand = np.flatnonzero(swap & ~big)
cidx = usa.iloc[cand].sindex
for a_i, geom in enumerate(pa.geometry.values):
    if pa.solar.iloc[a_i]:
        continue
    for k in cand[cidx.query(geom, predicate="intersects")]:
        ov = shapely.intersection(usa.geometry.values[k], geom)
        if ov.area <= 0:
            continue
        m = ms2.sindex.query(ov, predicate="intersects")
        cov = shapely.intersection(shapely.union_all(ms2.geometry.values[m]), ov).area / ov.area if len(m) else 0.0
        if cov < GUARD_COVER:
            guard[k] = True
            grows.append((pa.asset[a_i], pa.aname[a_i], round(ov.area), round(cov, 3)))
swap &= ~guard
p(f"asset guard skips {int(pa.solar.sum())} solar sites of {len(pa)} assets (user 11-14: panels are not buildings)")
p(f"asset guard (role 5): {guard.sum():,} pre-2019 USA polygons on {len({g[0] for g in grows})} assets kept "
  f"({usa.a_m2[guard].sum() / 1e6:.3f} km2): MS release 2 covers < {GUARD_COVER:.0%} of their overlap with the asset")

role = np.zeros(len(usa), "int8")
role[~pre] = 1
role[pre & ~swap] = 2
role[big] = 4
role[guard] = 5
keep_u = usa[role > 0].copy()
keep_u["role"] = role[role > 0]

qi, qj = keep_u.sindex.query(ms2.geometry.values, predicate="intersects")
ov = shapely.area(shapely.intersection(ms2.geometry.values[qi], keep_u.geometry.values[qj]))
free = np.bincount(qi, weights=ov, minlength=len(ms2)) < 0.5 * ms2.a_m2.to_numpy()
c = ms2[free]
jn = gpd.sjoin_nearest(c[["geometry"]], usa[["geometry"]], how="left", distance_col="d")
ok = jn.index_right.map(lambda i: bool(swap[int(i)]) and not big[int(i)]).groupby(level=0).any()
add = c.loc[ok.index[ok.to_numpy()]].copy()
add["role"] = 3

out = pd.concat([
    gpd.GeoDataFrame({"role": keep_u.role.values, "src": "usa",
                      "date": keep_u.IMAGE_DATE.dt.strftime("%Y-%m-%d").values, "a_m2": keep_u.a_m2.values},
                     geometry=keep_u.geometry.values, crs=32618),
    gpd.GeoDataFrame({"role": add.role.values, "src": "ms_r2", "date": "2019", "a_m2": add.a_m2.values},
                     geometry=add.geometry.values, crs=32618),
], ignore_index=True)
out["role_name"] = out.role.map(NAMES)
p("\nHybrid layer, nj2:")
for k, g in out.groupby("role"):
    p(f"  {k} {NAMES[k]:<18} {len(g):>9,}  {g.a_m2.sum() / 1e6:7.2f} km2")
p(f"  total               {len(out):>9,}  {out.a_m2.sum() / 1e6:7.2f} km2")

# ---- NJ-only check on the OUTPUT (independent of the clip): no kept polygon on another state's ground
rp = gpd.GeoDataFrame(geometry=out.geometry.representative_point().values, crs=32618)
bad = gpd.sjoin(rp, others, predicate="within")
p(f"NJ-only check: kept polygons with a representative point in NY / PA / DE: {len(bad)}; outside NJ + {NJ_BUF:.0f} m: "
  f"{int((~rp.within(nj.buffer(NJ_BUF))).sum())}; outside NJ itself (waterfront, cut by the 1:500k shoreline): "
  f"{int((~rp.within(nj)).sum())}")
assert len(bad) == 0

# ---- vs the v4 layer: the NEW area only, and the v4 area (rule + guard + edge)
v4 = gpd.read_file(V4HYB, layer="footprints", columns=["role", "a_m2"])
r4 = gpd.read_file(REPO / "data/region_v4.geojson").to_crs(32618).union_all()
in4 = rp.within(r4.intersection(nj)).to_numpy()
p(f"\nnj2 polygons in region_v4 x NJ: {in4.sum():,} ({out.a_m2[in4].sum() / 1e6:.2f} km2) vs the v4 layer "
  f"{len(v4):,} ({v4.a_m2.sum() / 1e6:.2f} km2); per role nj2 / v4:")
for k in NAMES:
    p(f"  {NAMES[k]:<18} {int(((out.role == k) & in4).sum()):>9,} / {int((v4.role == k).sum()):>9,}")
newa = ~in4
p(f"OUTSIDE region_v4 x NJ (the Hudson waterfront + the ring's 500 m margin): {newa.sum():,} polygons, "
  f"{out.a_m2[newa].sum() / 1e6:.2f} km2")

tmp = OUT.with_name(OUT.stem + ".tmp.gpkg")
tmp.unlink(missing_ok=True)
out.to_file(tmp, driver="GPKG", layer="footprints")
tmp.replace(OUT)
p(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.0f} MB)")

# ---- where: municipalities (the new area's towns first)
muni = gpd.read_file(f"zip://{M26}/census/cb_2023_34_cousub_500k.zip").to_crs(32618)
muni["NAME"] = muni.NAME + " (" + muni.COUNTYFP + ")"
s = gpd.sjoin(gpd.GeoDataFrame({"a": out.a_m2.values, "role": out.role.values, "new": newa}, geometry=rp.geometry.values,
                               crs=32618), muni[["NAME", "geometry"]], predicate="within", how="left")
s = s[~s.index.duplicated()]
s["NAME"] = s.NAME.fillna("(waterfront, outside the 1:500k shoreline)")
t = s.groupby("NAME").agg(n=("a", "size"), km2=("a", lambda v: v.sum() / 1e6), n_new_area=("new", "sum"),
                          km2_new_area=("a", lambda v: v[s.loc[v.index, "new"]].sum() / 1e6))
t = t.sort_values("km2_new_area", ascending=False)
t.to_csv(HERE / "hybrid_nj2_by_municipality.csv", float_format="%.4f")
p("\nTowns with buildings in the new area (km2 of footprint outside region_v4 x NJ):")
p(t[t.n_new_area > 0].head(20).to_string(float_format=lambda v: f"{v:.3f}"))

# ---- power assets: building share under the nj2 hybrid, beside the v4 hybrid / USA / NJDEP shares
prev = pd.read_csv(REPO / "logs/modern_round_c_2026-11-12/hybrid_power_assets.csv")
sh, roles = [], []
for geom in pa.geometry:
    i = out.sindex.query(geom, predicate="intersects")
    if len(i) == 0:
        sh.append(0.0)
        roles.append("")
        continue
    sh.append(shapely.intersection(shapely.union_all(out.geometry.values[i]), geom).area / geom.area)
    roles.append(",".join(sorted(set(out.role_name.values[i]))))
pa["bshare_hybrid_nj2"] = np.round(sh, 3)
pa["roles_nj2"] = roles
pt = pa[["asset", "aname", "bshare_hybrid_nj2", "roles_nj2"]].merge(
    prev[["asset", "bshare_njdep", "bshare_usa", "bshare_hybrid"]], on="asset", how="left")
pt["d_nj2_minus_v4hybrid"] = (pt.bshare_hybrid_nj2 - pt.bshare_hybrid).round(3)
pt = pt.sort_values("d_nj2_minus_v4hybrid", key=lambda v: v.abs().fillna(9), ascending=False)
pt.to_csv(HERE / "hybrid_nj2_power_assets.csv", index=False)
p(f"\nNJ power assets touching the area: {len(pt)}; in the v4 table: {pt.bshare_hybrid.notna().sum()}; "
  f"|nj2 - v4 hybrid| >= 0.10: {(pt.d_nj2_minus_v4hybrid.abs() >= 0.10).sum()}")
p(pt[(pt.d_nj2_minus_v4hybrid.abs() >= 0.05) | pt.bshare_hybrid.isna()].head(30).to_string(index=False))
p("\nGuarded overlaps (asset, name, overlap m2, MS release-2 cover):")
for g in grows:
    p("  ", g)
(HERE / "hybrid_nj2_summary.txt").write_text("\n".join(L) + "\n")
