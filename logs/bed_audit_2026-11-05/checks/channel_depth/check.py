"""Bed audit check `channel_depth`: the bed vs the USACE National Channel Framework (2026-11-05).

Every federal navigation channel reach in the domain carries an authorized / maintained depth (feet below
MLLW). Inside each reach polygon that the model simulates, the bed is sampled on a grid and compared with
  * the AUTHORIZED bottom   z_auth = MLLW(NAVD88, nearest NOAA CO-OPS station) − depth_ft·0.3048
  * the SURVEY reference    the recipe's own survey / stated-depth tiers (eHydro, NOS / ENC beds, river beds),
                            first available in the recipe's precedence; for the modern bed the 10-30
                            `ehydro_latest_2026` comes first (the "2026 as built" channels).
Exception kinds (README has the reasoning for every threshold):
  bed_above_survey            bed > survey + 0.5 m        (a merge / overlay lost the survey)
  bed_above_latest_survey     same, against ehydro_latest_2026 (modern only)
  unsurveyed_fill_in_channel  no survey and bed > z_auth + 1.0 m   (CUDEM fill / GMRT / lidar water surface)
  shoaled_per_survey          survey agrees with the bed and both stand > z_auth + 1.0 m (real shoaling; info)
  over_deep                   bed < z_auth − 0.61 − 3.0 m and (no survey, or bed < survey − 1.0 m)
  assumed_bed_no_survey       ≥ 50 % of a reach's simulated points have no survey (the bed there is an assumption)
Blocking components are graded by how much of the channel WIDTH they fill at their worst station:
  ≥ 90 % = high (a sill: the channel is closed across), ≥ 50 % = medium, else low.

Usage (repo root, sfincs env):
  python logs/bed_audit_2026-11-05/checks/channel_depth/check.py --bed experiments/v4_refreeze_swz/_subgrid_v1_1 \
     --label v1_1b --overlay-min deck_fix_v4b --out logs/bed_audit_2026-11-05/out/v1_1b/channel_depth.csv
  add --modern for the modern bed (adds ehydro_latest_2026 to the reference and the v1.1 deck overlay).
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from pyproj import Transformer
from scipy import ndimage
from scipy.spatial import cKDTree

REPO = Path("/cache/home/tpj8/nj_bight_sfincs")
sys.path.insert(0, str(REPO / "logs/decks_2026-11-04"))
sys.path.insert(0, str(REPO / "logs/modern_decks_2026-11-04"))
from common import Bed, Tier  # noqa: E402
from common_m import Overlay  # noqa: E402

RAW = Path("/scratch/tpj8/nj_bight_sfincs_data/audit/channel_depth/raw")
D = REPO / "data"
FT = 0.3048
T_SHOAL = (
    1.0  # m above the authorized bottom before a bed counts as shallow (see README)
)
T_SURVEY = 0.5  # m above the survey before the bed counts as having lost it
ALLOW = 2 * FT  # required + allowable overdepth, 1 ft + 1 ft
T_CHOKE = 1.0  # m: a sill is tide-choking (high) when less than this covers it at MLLW
T_DEEP = 3.0  # m below (authorized − allowance) before a bed counts as over-deep
TO_LL = Transformer.from_crs(32618, 4326, always_xy=True).transform
TO_UTM = Transformer.from_crs(4326, 32618, always_xy=True).transform

#: the recipe's survey / stated tiers, highest precedence first (overlays painted later win)
REF_2012 = [
    (
        "riverbeds_hierarchy_v4e",
        D / "elevation_v4/riverbeds/riverbeds_hierarchy_v4e.vrt",
    ),
    (
        "littleegg_channel_v4",
        D / "elevation_v4/littleegg_channel/littleegg_channel_v4.tif",
    ),
    (
        "riverbed_sayreville_v4",
        D / "elevation_v4/riverbed_margins/riverbed_sayreville_v4.tif",
    ),
    (
        "ehydro_refreeze_cenan_v4",
        D / "elevation_v4/ehydro/ehydro_refreeze_cenan_v4.tif",
    ),
    ("ehydro_harbour_v4", D / "elevation_v4/ehydro/ehydro_harbour_v4.tif"),
    ("ehydro_passaic_v4", D / "elevation_v4/ehydro/ehydro_passaic_v4.tif"),
    ("ehydro_hackensack_v4", D / "elevation_v4/ehydro/ehydro_hackensack_v4.tif"),
    ("ehydro_south_v3", D / "elevation_v3/ehydro_south_v3.tif"),
    ("ehydro_raritan_ak", D / "elevation_v1_5/ehydro_raritan_ak.tif"),
    ("ehydro_nj", D / "elevation/ehydro_nj.tif"),
    ("ehydro_south", D / "elevation/ehydro_south.tif"),
    ("shrewsbury_ehydro_2015", D / "elevation/shrewsbury_ehydro_2015.tif"),
    ("riverbeds_v4", D / "elevation_v4/riverbeds/riverbeds_v4.vrt"),
    ("coned_sw_raritan", D / "elevation_v1_5/coned_sw_raritan.tif"),
]
LATEST = (
    "ehydro_latest_2026",
    Path(
        "/scratch/tpj8/nj_bight_sfincs_data/modern_2026/derived/ehydro_latest_2026.tif"
    ),
)
#: base tiers, in the recipe's priority, to label what an UNSURVEYED channel pixel is made of
BASE = [
    ("usace_nj_2010_v3", D / "elevation_v3/usace_nj_2010_topobathy_v3.tif"),
    ("cudem_nj_v3", D / "elevation_v3/cudem_nj_v3.vrt"),
    ("cudem_delaware_v4", D / "elevation_v4/cudem_delaware_v4.vrt"),
    ("nj_10ft_dem_v4", D / "elevation_v4/nj_10ft_dem_v4.tif"),
    ("cudem13_v3", D / "elevation_v3/cudem13_v3.vrt"),
    ("dep3_v4", D / "elevation_v4/dep3_v4.vrt"),
    ("gmrt_v4", D / "elevation_v4/gmrt_v4.tif"),
]
OVERLAYS = {
    "deck_fix_v4b": D / "elevation_v4/deck_fix/deck_fix_v4b.vrt",
    "deck_fix_v4": D / "elevation_v4/deck_fix/deck_fix_v4.vrt",
    "alloway_pool_v4": D / "elevation_v4/inland_water/alloway_pool_v4.vrt",
}
COLS = [
    "check",
    "id",
    "lon",
    "lat",
    "severity",
    "kind",
    "metric",
    "value",
    "expected",
    "units",
    "area_m2",
    "sandy_peak_m",
    "near_asset",
    "asset_km",
    "source",
    "note",
    "fix",
]
BLOCKING = ("bed_above_survey", "bed_above_latest_survey", "unsurveyed_fill_in_channel")


class Ref:
    """First-available sampler over a precedence list of tiers (NaN where none has data)."""

    def __init__(self, tiers):
        self.t = []
        for name, p in tiers:
            if Path(p).exists():
                self.t.append((name, Tier(p)))
            else:
                print(f"  ⚠️ reference tier missing, skipped: {name} ({p})", flush=True)

    def sample(self, x, y):
        z = np.full(x.shape, np.nan, np.float32)
        src = np.full(x.shape, -1, np.int16)
        for i, (_, t) in enumerate(self.t):
            todo = ~np.isfinite(z)
            if not todo.any():
                break
            v = t.sample(x[todo], y[todo])
            ok = np.isfinite(v)
            idx = np.flatnonzero(todo)[ok]
            z[idx], src[idx] = v[ok], i
        return z, src


_G: dict = {}


def _init(bed_path, overlay_keys, modern):
    _G["bed"] = Bed(bed_path)
    _G["ov"] = [Tier(OVERLAYS[k]) for k in overlay_keys]
    _G["v11ov"] = Overlay() if modern else None
    refs = ([LATEST] if modern else []) + REF_2012
    _G["ref"] = Ref(refs)
    _G["ref_names"] = [n for n, _ in _G["ref"].t]
    _G["base"] = Ref(BASE)
    _G["base_names"] = [n for n, _ in _G["base"].t]


def bed_sample(x, y):
    out = np.full(x.shape, np.nan, np.float32)
    # chunk by 2 km cells so a long diagonal reach never reads one huge window
    key = np.floor(x / 2000).astype(np.int64) * 100000 + np.floor(y / 2000).astype(
        np.int64
    )
    for k in np.unique(key):
        m = key == k
        z = _G["bed"].sample(x[m], y[m])
        for t in _G["ov"]:
            o = t.sample(x[m], y[m])
            z = np.where(np.isfinite(o), np.fmin(z, o), z)
        if _G["v11ov"] is not None:
            o = _G["v11ov"].sample(x[m], y[m])
            z = np.where(np.isfinite(o), np.fmin(z, o), z)
        out[m] = z
    return out


def reach_points(geom, s):
    x0, y0, x1, y1 = geom.bounds
    xs = np.arange(x0 + s / 2, x1, s)
    ys = np.arange(y0 + s / 2, y1, s)
    if not len(xs) or not len(ys):
        return None
    X, Y = np.meshgrid(xs, ys)
    inside = shapely.contains_xy(geom, X, Y)
    return X, Y, inside


def axis_frames(geom, X, Y):
    """(along, across) coordinates on the reach's long axis (its minimum rotated rectangle)."""
    r = geom.minimum_rotated_rectangle
    c = np.asarray(r.exterior.coords)[:4]
    e = [c[1] - c[0], c[2] - c[1]]
    u = e[0] if np.hypot(*e[0]) >= np.hypot(*e[1]) else e[1]
    u = u / np.hypot(*u)
    v = np.array([-u[1], u[0]])
    P = np.stack([X - c[0][0], Y - c[0][1]], -1)
    return P @ u, P @ v


def crest_level(Z, ok, a_end, b_end, step=0.05):
    """Lowest level L at which the cells with Z <= L (4-connected, inside `ok`) join an a_end cell to a
    b_end cell: the channel's sill / minimax crest. NaN when the ends never connect."""
    vals = np.unique(np.round(Z[ok] / step) * step)
    if not vals.size:
        return np.nan, None
    four = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]])

    def joined(L):
        lab, _ = ndimage.label(ok & (Z <= L + 1e-6), structure=four)
        a = set(np.unique(lab[a_end & (lab > 0)]))
        b = set(np.unique(lab[b_end & (lab > 0)]))
        common = a & b
        return (lab, common) if common else (None, None)

    lo, hi = 0, len(vals) - 1
    if joined(vals[hi])[0] is None:
        return np.nan, None
    while lo < hi:
        mid = (lo + hi) // 2
        if joined(vals[mid])[0] is None:
            lo = mid + 1
        else:
            hi = mid
    lab, common = joined(vals[lo])
    return float(vals[lo]), np.isin(lab, list(common))


def run_reach(args):
    rid, geom_wkb, z_auth, width_m, name, s, mllw = args
    geom = shapely.from_wkb(geom_wkb)
    rp = reach_points(geom, s)
    if rp is None:
        return dict(rid=rid, n=0)
    X, Y, inside = rp
    sim = inside.copy()
    xi, yi = X[inside], Y[inside]
    d, f = _G["tree"].query(np.c_[xi, yi])
    ok = (d <= 0.75 * _G["fsize"][f]) & _G["active"][f]
    sim[inside] = ok
    n_sim = int(sim.sum())
    if n_sim == 0:
        return dict(rid=rid, n=0, n_in=int(inside.sum()))
    xs, ys = X[sim], Y[sim]
    zb = bed_sample(xs, ys)
    zr, src = _G["ref"].sample(xs, ys)
    has = np.isfinite(zr)
    kinds = np.full(xs.shape, "", object)
    shallow = zb > z_auth + T_SHOAL
    lost = has & (zb > zr + T_SURVEY)
    latest = src == (
        0 if _G["ref_names"] and _G["ref_names"][0] == "ehydro_latest_2026" else -99
    )
    kinds[lost & latest] = "bed_above_latest_survey"
    kinds[lost & ~latest] = "bed_above_survey"
    kinds[~has & shallow] = "unsurveyed_fill_in_channel"
    kinds[has & ~lost & shallow] = "shoaled_per_survey"
    deep = (zb < z_auth - ALLOW - T_DEEP) & (~has | (zb < zr - 1.0))
    kinds[deep & (kinds == "")] = "over_deep"
    G = np.full(X.shape, "", object)
    G[sim] = kinds
    idx = np.full(X.shape, -1, np.int64)
    idx[sim] = np.arange(n_sim)
    along, across = axis_frames(geom, X, Y)
    bins = np.floor(along / (2 * s)).astype(np.int64)
    rows = []
    block = np.isin(G, BLOCKING)
    # width fraction per along-bin over the simulated cells
    simb = sim & np.isfinite(along)
    tot = pd.Series(1, index=bins[simb]).groupby(level=0).sum()
    blk = (
        pd.Series(1, index=bins[block]).groupby(level=0).sum()
        if block.any()
        else pd.Series(dtype=float)
    )
    frac = (blk.reindex(tot.index).fillna(0) / tot).to_dict()
    boundary = geom.boundary
    zbG = np.full(X.shape, np.nan, np.float32)
    zbG[sim] = zb
    zrG = np.full(X.shape, np.nan, np.float32)
    zrG[sim] = zr
    for kind in BLOCKING + ("over_deep",):
        m = G == kind
        if not m.any():
            continue
        lab, nl = ndimage.label(m, structure=np.ones((3, 3)))
        for k in range(1, nl + 1):
            cm = lab == k
            npx = int(cm.sum())
            area = npx * s * s
            if area < 4 * s * s and kind != "over_deep":
                continue  # a lone pixel or two: below the grid's resolving power
            if kind == "over_deep":
                # natural deep water (an offshore bar channel, a scour hole) is not an error: keep only what
                # no independent base tier explains, i.e. a CARVE (ours) at least 1 m below the base surface
                bz, _ = _G["base"].sample(X[cm][:300], Y[cm][:300])
                dz = zbG[cm][:300] - bz
                if not np.isfinite(dz).any() or np.nanmedian(dz) > -1.0:
                    continue
            cx, cy = float(X[cm].mean()), float(Y[cm].mean())
            if kind.startswith("bed_above"):
                excess = zbG[cm] - zrG[cm]
            elif kind == "over_deep":
                excess = zbG[cm] - (z_auth - ALLOW)
            else:
                excess = zbG[cm] - z_auth
            wf = (
                max(frac.get(b, 0.0) for b in np.unique(bins[cm]))
                if kind in BLOCKING
                else 0.0
            )
            edge = boundary.distance(shapely.Point(cx, cy)) < 2 * s
            if kind in BLOCKING:
                sev = "medium" if wf >= 0.5 else "low"
                if (
                    kind.startswith("bed_above")
                    and np.nanmax(zbG[cm] - z_auth) <= T_SHOAL
                ):
                    sev = "low"  # lost the survey but still deeper than the authorized bottom + tolerance
            else:
                sev = "medium" if not np.isfinite(zrG[cm]).any() else "low"
            srcname = ""
            if kind == "unsurveyed_fill_in_channel":
                bz, bs = _G["base"].sample(X[cm][:200], Y[cm][:200])
                if (bs >= 0).any():
                    vals, cnt = np.unique(bs[bs >= 0], return_counts=True)
                    srcname = _G["base_names"][int(vals[cnt.argmax()])]
            elif kind.startswith("bed_above"):
                ss = src[idx[cm]]
                ss = ss[ss >= 0]
                if ss.size:
                    vals, cnt = np.unique(ss, return_counts=True)
                    srcname = _G["ref_names"][int(vals[cnt.argmax()])]
            lon, lat = TO_LL(cx, cy)
            v = (
                float(np.nanmax(excess))
                if kind != "over_deep"
                else float(np.nanmin(excess))
            )
            rows.append(
                dict(
                    rid=rid,
                    name=name,
                    kind=kind,
                    severity=sev,
                    x=cx,
                    y=cy,
                    lon=lon,
                    lat=lat,
                    area=area,
                    width_frac=round(wf, 2),
                    edge=bool(edge),
                    z_bed_max=float(np.nanmax(zbG[cm])),
                    z_bed_min=float(np.nanmin(zbG[cm])),
                    z_auth=z_auth,
                    z_ref_med=float(np.nanmedian(zrG[cm]))
                    if np.isfinite(zrG[cm]).any()
                    else np.nan,
                    value=v,
                    srcname=srcname,
                )
            )
    # the sill test: do the reach's two ends connect within tolerance of the authorized bottom?
    r_ = geom.minimum_rotated_rectangle
    cc = np.asarray(r_.exterior.coords)[:4]
    L1, L2 = sorted([np.hypot(*(cc[1] - cc[0])), np.hypot(*(cc[2] - cc[1]))])
    crest = np.nan
    if L2 >= 3 * L1 and n_sim >= 20:
        al = np.where(sim, along, np.nan)
        a_end = sim & (al <= np.nanmin(al) + 3 * s)
        b_end = sim & (al >= np.nanmax(al) - 3 * s)
        crest, conn = crest_level(np.where(sim, zbG, np.inf), sim, a_end, b_end)
        if np.isfinite(crest) and crest > z_auth + T_SHOAL and conn is not None:
            ccells = conn & (zbG >= crest - 0.1)
            ck = G[ccells]
            ck = ck[ck != ""]
            kind = (
                pd.Series(ck).mode().iat[0] if ck.size else "unsurveyed_fill_in_channel"
            )
            cx, cy = float(X[ccells].mean()), float(Y[ccells].mean())
            lon, lat = TO_LL(cx, cy)
            choke = crest >= mllw - T_CHOKE
            sev = (
                "high"
                if choke
                and kind not in ("shoaled_per_survey", "bed_above_latest_survey")
                else "medium"
            )
            rows.append(
                dict(
                    rid=rid,
                    name=name,
                    kind=kind,
                    severity=sev,
                    x=cx,
                    y=cy,
                    lon=lon,
                    lat=lat,
                    area=float(ccells.sum() * s * s),
                    width_frac=1.0,
                    edge=False,
                    z_bed_max=crest,
                    z_bed_min=crest,
                    z_auth=z_auth,
                    z_ref_med=float(np.nanmedian(zrG[ccells]))
                    if np.isfinite(zrG[ccells]).any()
                    else np.nan,
                    value=crest - z_auth,
                    srcname="",
                    sill=True,
                )
            )
    # per-reach aggregates
    sh = G == "shoaled_per_survey"
    agg = dict(
        rid=rid,
        n=n_sim,
        n_in=int(inside.sum()),
        frac_surveyed=float(has.mean()),
        crest=crest,
        shoaled_area=float(sh.sum() * s * s),
        shoaled_max=float(np.nanmax(zbG[sh] - z_auth)) if sh.any() else np.nan,
        zb_p50=float(np.nanmedian(zb)),
        name=name,
    )
    if has.mean() < 0.5:
        bz, bs = _G["base"].sample(xs[~has][:400], ys[~has][:400])
        names = [_G["base_names"][i] for i in bs[bs >= 0]]
        agg["base_mode"] = max(set(names), key=names.count) if names else ""
    agg["rows"] = rows
    return agg


def _init_all(bed_path, overlay_keys, modern, tree_data):
    _init(bed_path, overlay_keys, modern)
    _G["tree"] = cKDTree(tree_data["xy"])
    _G["fsize"] = tree_data["fsize"]
    _G["active"] = tree_data["active"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bed", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--overlay-min", action="append", default=[])
    ap.add_argument("--modern", action="store_true")
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--only", default="", help="regex on reach name (testing)")
    a = ap.parse_args()
    bed = Path(a.bed) / "subgrid/dep_subgrid_merged.tif"
    assert bed.exists(), bed

    reaches = gpd.read_file(RAW / "layer2_0.geojson").to_crs(32618)
    reaches["geometry"] = reaches.geometry.make_valid()
    if a.only:
        reaches = reaches[
            reaches.sdsfeaturename.str.contains(a.only, case=False, regex=True)
        ]
    st = pd.DataFrame(json.load(open(RAW / "stations_mllw_navd88.json")))
    sx, sy = TO_UTM(st.lon.values, st.lat.values)
    stree = cKDTree(np.c_[sx, sy])
    cen = np.c_[reaches.geometry.centroid.x, reaches.geometry.centroid.y]
    dd, si = stree.query(cen)
    reaches["mllw_navd88"] = st.mllw_navd88.values[si]
    reaches["station"] = st.id.values[si]
    reaches["station_km"] = dd / 1000
    reaches["z_auth"] = reaches.mllw_navd88 - reaches.depthmaintained * FT
    reaches["width_m"] = reaches.widthfrom * FT

    import xarray as xr

    t = xr.open_dataset(REPO / "experiments/v4_refreeze_swz/_template_sealed/sfincs.nc")
    fx, fy = t.mesh2d_face_x.values, t.mesh2d_face_y.values
    fn = t.mesh2d_face_nodes.values
    nx = t.mesh2d_node_x.values
    good = np.isfinite(fn)
    fnn = np.where(good, fn, 0).astype(np.int64)
    xs_ = np.where(good, nx[fnn], np.nan)
    fsize = np.nanmax(xs_, 1) - np.nanmin(xs_, 1)
    active = t["mask"].values > 0
    tree_data = dict(
        xy=np.c_[fx, fy][active],
        fsize=fsize[active],
        active=np.ones(int(active.sum()), bool),
    )
    m = xr.open_dataset(REPO / "experiments/v4_refreeze_swz/p4-premier/sfincs_map.nc")
    zsmax = np.nanmax(m.zsmax.values, 0)
    ftree = cKDTree(np.c_[fx, fy])

    plants = gpd.read_file(D / "power_infra/plant_polygons.geojson").to_crs(32618)
    subs = gpd.read_file(D / "power_infra/substation_polygons.geojson").to_crs(32618)
    assets = pd.concat(
        [plants.assign(kind="plant"), subs.assign(kind="substation")], ignore_index=True
    )
    anames = (
        assets.get("name", pd.Series([""] * len(assets))).fillna("").astype(str).values
    )
    atree = cKDTree(np.c_[assets.geometry.centroid.x, assets.geometry.centroid.y])

    jobs = []
    for r in reaches.itertuples():
        s = 6.25 if r.width_m < 100 else 12.5
        jobs.append(
            (
                str(r.channelreachidpk),
                shapely.to_wkb(r.geometry),
                float(r.z_auth),
                float(r.width_m),
                str(r.sdsfeaturename).strip(),
                s,
                float(r.mllw_navd88),
            )
        )
    print(f"[channel_depth] {a.label}: {len(jobs)} NCF reaches, bed {bed}", flush=True)
    with ProcessPoolExecutor(
        a.workers,
        initializer=_init_all,
        initargs=(str(bed), a.overlay_min, a.modern, tree_data),
    ) as ex:
        res = list(ex.map(run_reach, jobs, chunksize=1))

    meta = reaches.set_index(reaches.channelreachidpk.astype(str))
    rows, cov = [], []
    for r in res:
        mm = meta.loc[r["rid"]]
        cov.append(
            dict(
                reach=r["rid"],
                name=mm.sdsfeaturename.strip(),
                district=mm.usacedistrictcode,
                depth_ft=mm.depthmaintained,
                z_auth=round(mm.z_auth, 2),
                station=mm.station,
                station_km=round(mm.station_km, 1),
                n_points=r.get("n", 0),
                n_in_polygon=r.get("n_in", 0),
                frac_surveyed=round(r.get("frac_surveyed", np.nan), 3),
                zb_p50=round(r.get("zb_p50", np.nan), 2),
                shoaled_area_m2=round(r.get("shoaled_area", 0.0)),
                base_mode=r.get("base_mode", ""),
                sill_crest=round(r.get("crest", np.nan), 2),
            )
        )
        if not r.get("n"):
            continue
        src_auth = (
            f"USACE NCF {mm.usacedistrictcode} reach {r['rid']} '{mm.sdsfeaturename.strip()}' "
            f"{mm.depthmaintained} ft MLLW; MLLW→NAVD88 {mm.mllw_navd88:+.3f} m from CO-OPS {mm.station} "
            f"({mm.station_km:.1f} km)"
        )
        for e in r["rows"]:
            d, fi = ftree.query([e["x"], e["y"]])
            pk = float(zsmax[fi]) if d < 300 else np.nan
            ad, ai = atree.query([e["x"], e["y"]])
            notes = {
                "unsurveyed_fill_in_channel": f"no survey; bed up to {e['value']:+.2f} m above the authorized bottom "
                f"({e['z_auth']:.2f}); bed from {e['srcname'] or '?'}; fills {e['width_frac']:.0%} of the width at worst",
                "bed_above_survey": f"bed stands up to {e['value']:.2f} m above the recipe's own survey ({e['srcname']}, median {e['z_ref_med']:.2f}) "
                f"— a merge or later overlay lost it; {e['width_frac']:.0%} of the width at worst",
                "bed_above_latest_survey": f"bed above ehydro_latest_2026 (median {e['z_ref_med']:.2f}); expected until the "
                f"2026 rebuild carries it; {e['width_frac']:.0%} of the width at worst",
                "over_deep": f"bed {e['z_bed_min']:.2f} m, more than {T_DEEP:.0f} m below authorized − allowance and ≥ 1 m below every base tier (a carve, not natural) "
                f"({e['z_auth'] - ALLOW:.2f}) and not confirmed by a survey",
            }
            fixes = {
                "unsurveyed_fill_in_channel": "get a survey; else a stated-depth bed at the authorized depth (lower-only)",
                "bed_above_survey": "check the recipe order / overlays over this survey; paint the survey lower-only",
                "bed_above_latest_survey": "include ehydro_latest_2026 in the modern recipe",
                "over_deep": "clamp to the survey or to authorized − allowance (raise-only, local)",
            }
            if e.get("sill"):
                metric = "sill crest − authorized bottom"
                note = (
                    f"SILL ({'tide-choking: < 1 m of water over it at MLLW' if e['severity'] == 'high' else 'conveyance loss'}): "
                    f"the reach's two ends connect only at {e['z_bed_max']:.2f} m, {e['value']:+.2f} m above the "
                    f"authorized bottom ({e['z_auth']:.2f}); crest cells are mostly '{e['kind']}'"
                )
                expected = f"≤ {T_SHOAL:.1f}"
            elif e["kind"].startswith("bed_above"):
                metric, note, expected = (
                    "bed − survey (max)",
                    notes[e["kind"]],
                    f"≤ {T_SURVEY:.1f}",
                )
            elif e["kind"] == "over_deep":
                metric, note, expected = (
                    "bed − (authorized − allowance) (min)",
                    notes[e["kind"]],
                    f"≥ −{T_DEEP:.1f}",
                )
            else:
                metric, note, expected = (
                    "bed − authorized bottom (max)",
                    notes[e["kind"]],
                    f"≤ {T_SHOAL:.1f}",
                )
            rows.append(
                dict(
                    check="channel_depth",
                    id=f"{r['rid']}:{'sill' if e.get('sill') else e['kind']}:{int(e['x'])}:{int(e['y'])}",
                    lon=round(e["lon"], 6),
                    lat=round(e["lat"], 6),
                    severity=e["severity"],
                    kind=e["kind"],
                    metric=metric,
                    value=round(e["value"], 2),
                    expected=expected,
                    units="m",
                    area_m2=round(e["area"]),
                    sandy_peak_m=round(pk, 2) if np.isfinite(pk) else "",
                    near_asset=anames[ai] if ad <= 2000 else "",
                    asset_km=round(ad / 1000, 2) if ad <= 2000 else "",
                    source=src_auth,
                    note=note,
                    fix=fixes[e["kind"]] if e["kind"] in fixes else "",
                )
            )
        if r.get("frac_surveyed", 1) < 0.5:
            c = mm.geometry.representative_point()
            lon, lat = TO_LL(c.x, c.y)
            base = r.get("base_mode", "")
            rows.append(
                dict(
                    check="channel_depth",
                    id=f"{r['rid']}:assumed",
                    lon=round(lon, 6),
                    lat=round(lat, 6),
                    severity="medium" if base == "gmrt_v4" else "low",
                    kind="assumed_bed_no_survey",
                    metric="share of simulated reach points with a survey / stated bed",
                    value=round(r["frac_surveyed"], 2),
                    expected="≥ 0.5",
                    units="fraction",
                    area_m2=round(mm.geometry.area),
                    sandy_peak_m="",
                    near_asset="",
                    asset_km="",
                    source=src_auth,
                    note=f"the bed in this federal channel is mostly {base or 'a base tier'}, not a survey",
                    fix="get the reach's eHydro survey; else a stated-depth decision",
                )
            )
        if r.get("shoaled_area", 0) > 0:
            c = mm.geometry.representative_point()
            lon, lat = TO_LL(c.x, c.y)
            rows.append(
                dict(
                    check="channel_depth",
                    id=f"{r['rid']}:shoaled",
                    lon=round(lon, 6),
                    lat=round(lat, 6),
                    severity="low",
                    kind="shoaled_per_survey",
                    metric="bed − authorized bottom (max), survey agrees",
                    value=round(r["shoaled_max"], 2),
                    expected=f"≤ {T_SHOAL:.1f}",
                    units="m",
                    area_m2=round(r["shoaled_area"]),
                    sandy_peak_m="",
                    near_asset="",
                    asset_km="",
                    source=src_auth,
                    note="the survey itself shows the channel shallower than authorized: real shoaling, not a bed error",
                    fix="",
                )
            )
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows, columns=COLS)
    order = {"high": 0, "medium": 1, "low": 2}
    df = df.sort_values(
        ["severity", "area_m2"],
        key=lambda c: c.map(order) if c.name == "severity" else -c,
    )
    df.to_csv(out, index=False)
    pd.DataFrame(cov).to_csv(out.with_name(out.stem + "_coverage.csv"), index=False)
    print(f"[channel_depth] {a.label}: {len(df)} exceptions → {out}")
    print(df.groupby(["kind", "severity"]).size().to_string())


if __name__ == "__main__":
    main()
