"""Deck / causeway DAM sweep over the nj2 NEW AREA on the planned 2012 bed (planned_bed.py).

Candidates: every OSM bridge line (decks_2026-11-04/bridges.gpkg: highway, railway, footway, ...)
touching the new area, plus every FHWA NBI record (2025) with water under it (item 42B 5-9) within
150 m of the new area, matched to the nearest OSM bridge line (<= 120 m).

Per bridge line (the nbi_check WATER rule, tuned to a 2.5 m grid): stations every 2.5 m along the
line; across the line at each station
    under = max bed |a| <= hw            (hw = max(width/2, 5) m: the deck footprint)
    up/dn = median bed at hw+5 .. hw+30 m on each side;  ref = max(up, dn)
A station is OVER WATER when up < MHHW and dn < MHHW (water on both sides, MHHW = 0.70 m NAVD88).
Per line:  sill = min(under) over the water stations (the lowest way through under the deck);
           chan = median(ref) over them;  span = their length;  held = sill - chan.
  DAM      sill > MHHW                       (no way through under the deck below MHHW)
  PARTIAL  sill <= MHHW, but > 50 % of the water span has under - ref > 0.30 m
  OPEN     otherwise
Each line is also run on the BASE (v1.1c, before 2.0's tiers) to say whether a 2.0 carve already
cut it, and on the NYC 2017 bare-earth lidar (independent; NaN where it has no tile).
"""
import re
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer

REPO = Path("/cache/home/tpj8/nj_bight_sfincs")
L = REPO / "logs/nj2_decks_2026-11-14"
D = Path("/scratch/tpj8/tmp/nj2_decks_2026-11-14")
MHHW = 0.70
X = 0.30


class Grid:
    def __init__(self, p):
        with rasterio.open(p) as s:
            self.a = s.read(1)
            self.T = s.transform

    def __call__(self, x, y):
        c = np.floor((np.asarray(x) - self.T.c) / self.T.a).astype(int)
        r = np.floor((np.asarray(y) - self.T.f) / self.T.e).astype(int)
        ok = (c >= 0) & (c < self.a.shape[1]) & (r >= 0) & (r < self.a.shape[0])
        v = np.full(np.shape(x), np.nan, np.float32)
        v[ok] = self.a[r[ok], c[ok]]
        return v


class Lidar:
    """NYC 2017 bare earth (EPSG:6539 ft grid, m values via the VRT's ScaleRatio)."""

    def __init__(self):
        self.s = rasterio.open(REPO / "data/elevation_nj2/v2/vrt/nyc_topobathy_2017_m.vrt")
        self.tr = Transformer.from_crs(32618, 6539, always_xy=True).transform

    def __call__(self, x, y):
        shp = np.shape(x)
        X, Y = self.tr(np.ravel(x), np.ravel(y))
        v = np.array([q[0] for q in self.s.sample(zip(X, Y), masked=False)], np.float32)
        nd = self.s.nodata
        if nd is not None:
            v[np.isclose(v, nd * 0.3048006096012192) | np.isclose(v, nd)] = np.nan
        v[(v < -500) | (v > 500)] = np.nan
        return v.reshape(shp)


def width_of(r):
    w = r.get("width")
    try:
        w = float(re.findall(r"[\d.]+", str(w))[0]) if w else np.nan
    except IndexError:
        w = np.nan
    if np.isfinite(w) and 2 <= w <= 80:
        return w
    h, rw = r.get("highway"), r.get("railway")
    if h in ("motorway", "trunk", "primary"):
        return 20.0
    if h in ("secondary", "tertiary", "residential", "unclassified", "service", "motorway_link", "trunk_link",
             "primary_link", "secondary_link"):
        return 14.0
    if rw:
        return 10.0
    return 6.0


def profile(line, hw, samp, step=2.5):
    L_ = line.length
    s = np.arange(step / 2, L_, step)
    if len(s) == 0:
        return None
    P = np.array([line.interpolate(t).coords[0] for t in s])
    P2 = np.array([line.interpolate(min(t + 1, L_)).coords[0] for t in s])
    P1 = np.array([line.interpolate(max(t - 1, 0)).coords[0] for t in s])
    tvec = P2 - P1
    tvec /= np.maximum(np.hypot(tvec[:, 0], tvec[:, 1]), 1e-9)[:, None]
    n = np.c_[-tvec[:, 1], tvec[:, 0]]
    au = np.arange(-hw, hw + 0.01, 1.25)
    asd = np.arange(hw + 5, hw + 30.01, 2.5)
    U = samp(P[:, 0, None] + n[:, 0, None] * au, P[:, 1, None] + n[:, 1, None] * au)
    up = samp(P[:, 0, None] + n[:, 0, None] * asd, P[:, 1, None] + n[:, 1, None] * asd)
    dn = samp(P[:, 0, None] - n[:, 0, None] * asd, P[:, 1, None] - n[:, 1, None] * asd)
    with np.errstate(all="ignore"):
        return dict(s=s, P=P, under=np.nanmax(U, 1), up=np.nanmedian(up, 1), dn=np.nanmedian(dn, 1))


def judge(pr, mhhw=MHHW):
    if pr is None:
        return dict(cls="NONE")
    w = (pr["up"] < mhhw) & (pr["dn"] < mhhw)
    if not w.any():
        return dict(cls="NOT-WATER", n_water=0)
    under, ref = pr["under"][w], np.fmax(pr["up"][w], pr["dn"][w])
    held = under - ref
    i = int(np.nanargmin(under))
    sill = float(under[i])
    cls = "DAM" if sill > mhhw else ("PARTIAL" if np.nanmean(held > X) > 0.5 else "OPEN")
    k = np.where(w)[0][i]
    return dict(cls=cls, n_water=int(w.sum()), span_m=float(w.sum() * 2.5), sill=round(sill, 2),
                chan=round(float(np.nanmedian(ref)), 2), chan_min=round(float(np.nanmin(np.fmin(pr["up"][w], pr["dn"][w]))), 2),
                held_p50=round(float(np.nanmedian(held)), 2), frac_deck=round(float(np.nanmean(held > X)), 2),
                under_p50=round(float(np.nanmedian(under)), 2), sill_x=float(pr["P"][k, 0]), sill_y=float(pr["P"][k, 1]))


def main():
    a = gpd.read_file(REPO / "data/region_nj2.geojson").to_crs(32618).geometry.iloc[0]
    b = gpd.read_file(REPO / "data/region_v4_hot_plus.geojson").to_crs(32618).geometry.iloc[0]
    new = a.difference(b)
    ll = gpd.GeoSeries([new.buffer(150)], crs=32618).to_crs(4326).total_bounds
    br = gpd.read_file("/scratch/tpj8/nj_bight_sfincs_data/decks_2026-11-04/bridges.gpkg", bbox=tuple(ll)).to_crs(32618)
    br = br[br.intersects(new.buffer(20))].copy()
    br = br[~br.geom_type.isin(["Point"])]
    br = br.explode(index_parts=False).reset_index(drop=True)
    print("OSM bridge lines touching the new area:", len(br))
    plan, base = Grid(D / "planned_2012.tif"), Grid(D / "base_v11c.tif")
    tag = Grid(D / "planned_2012_tag.tif")
    rows = []
    for i, r in br.iterrows():
        hw = max(width_of(r) / 2, 5.0)
        pr = profile(r.geometry, hw, plan)
        j = judge(pr)
        if j["cls"] in ("NONE", "NOT-WATER"):
            continue
        jb = judge(profile(r.geometry, hw, base))
        c = r.geometry.interpolate(0.5, normalized=True)
        t = int(tag(np.array([j["sill_x"]]), np.array([j["sill_y"]]))[0]) if "sill_x" in j else 0
        rows.append(dict(osm_id=r.osm_id, name=r["name"], highway=r.highway, railway=r.railway, man_made=r.man_made,
                         bridge=r.bridge, len_m=round(r.geometry.length, 1), hw=hw, x=c.x, y=c.y, **j,
                         base_cls=jb.get("cls"), base_sill=jb.get("sill"), sill_tier=t))
    R = pd.DataFrame(rows)
    tr = Transformer.from_crs(32618, 4326, always_xy=True)
    R["lon"], R["lat"] = tr.transform(R.x.values, R.y.values)
    R["sill_lon"], R["sill_lat"] = tr.transform(R.sill_x.values, R.sill_y.values)
    # NBI: water crossings near the new area
    N = pd.read_csv(REPO / "logs/nbi_crossings_2026-11-05/out/nbi_domain.csv", dtype={"struct": str, "und": str, "type43": str})
    N = N[N.und.astype(str).str.strip().isin(list("56789"))].copy()
    nb = gpd.GeoDataFrame(N, geometry=gpd.points_from_xy(N.x, N.y), crs=32618)
    nb = nb[nb.distance(new) <= 150].copy()
    print("NBI water crossings within 150 m of the new area:", len(nb))
    lines = gpd.GeoDataFrame(br[["osm_id", "name", "highway", "railway"]], geometry=br.geometry, crs=32618)
    tested = set(R.osm_id)
    out = []
    for _, n in nb.iterrows():
        d = lines.distance(n.geometry)
        cand = d[d <= 120].sort_values()
        hit = [lines.osm_id[k] for k in cand.index if lines.osm_id[k] in tested]
        out.append(dict(state=n.state, struct=n.struct, feat=n.feat, carried=n.carried, und_txt=n.und_txt,
                        type_txt=n.type_txt, len49=n.len49, deckw52=n.deckw52, vclr54b=n.vclr54b, lon=n.lon, lat=n.lat,
                        osm_near=",".join(str(lines.osm_id[k]) for k in cand.index[:6]),
                        osm_tested=",".join(str(h) for h in hit[:6])))
    NB = pd.DataFrame(out)
    NB.to_csv(L / "nbi_new_area.csv", index=False)
    R.to_csv(L / "osm_crossings_planned2012.csv", index=False)
    print(R.cls.value_counts().to_string())
    print(NB[["struct", "feat", "carried", "lat", "lon", "osm_tested"]].to_string())


if __name__ == "__main__":
    main()
