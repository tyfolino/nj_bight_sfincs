"""nj2 (Model 2.0.0) edge + hand-placed-input checks, before the freeze. Read-only on every input.

    cd ~/nj_bight_sfincs && PATH=$HOME/nj_sandy_sfincs/micromamba/envs/sfincs/bin:$PATH \
        python -I logs/nj2_edges_2026-11-14/edges_nj2.py

Writes (only):
  logs/nj2_edges_2026-11-14/naccs_cuts_nj2.csv       NACCS save points within 2 km of each new cut
  logs/nj2_edges_2026-11-14/structures_carryover.csv every weir polyline / wavemaker piece / drn pair / pool polygon
  logs/nj2_edges_2026-11-14/snapwave_footprint_check.txt
  data/nj2_design/obs_nj2.csv, data/nj2_design/obs_nj2.obs, data/nj2_design/obs_nj2_bergen_point_6min.nc
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(HERE))

import pyproj  # noqa: E402  (before hydromt)
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import shapely  # noqa: E402
import geopandas as gpd  # noqa: E402
import xarray as xr  # noqa: E402

import build_naccs_boundary_nj2 as W  # noqa: E402  (patches the builder's NACCS paths)

B = W.B
NJ2 = ROOT / "data" / "nj2_design"
PREMIER = ROOT / "experiments/v4_refreeze_swz_v11/p4-premier+weir-elizabeth-rahway"
T = pyproj.Transformer.from_crs(4326, 32618, always_xy=True)
TI = pyproj.Transformer.from_crs(32618, 4326, always_xy=True)


def ring(path, lonc="lon", latc="lat"):
    r = pd.read_csv(path, comment="#")
    x, y = T.transform(r[lonc].values, r[latc].values)
    return shapely.Polygon(np.c_[x, y]).buffer(0)


def line_csv(path):
    r = pd.read_csv(path, comment="#")
    x, y = T.transform(r.lon.values, r.lat.values)
    return shapely.LineString(np.c_[x, y])


RING_NJ2 = ring(ROOT / "data/nj2_design/region_nj2_vertices.csv")  # the registered nj2 ring (domain agent 11-14)
RING_V4 = gpd.read_file(ROOT / "data/region_v4_hot_plus.geojson").to_crs(32618).union_all()
NEW_AREA = RING_NJ2.difference(RING_V4)
FORCED = {
    "sea_line (delaware_mouth/ocean/lower_bay_entrance/rockaway_inlet)": line_csv(NJ2 / "waterlevel_line_nj2.csv"),
    "cd_canal (box arm, kept)": shapely.box(439_600, 4_376_600, 440_300, 4_378_300),
    "hudson (new cut)": line_csv(NJ2 / "cut_hudson_nj2.csv"),
    "hell_gate (new cut)": line_csv(NJ2 / "cut_hell_gate_nj2.csv"),
}
REMOVED = {
    "narrows (v4 arm, dropped)": shapely.box(579_600, 4_494_800, 582_500, 4_496_400),
    "kvk_east (v4 arm, dropped)": shapely.box(576_600, 4_499_400, 577_300, 4_501_200),
}


def nearest(geoms: dict, x, y):
    p = shapely.Point(x, y)
    d = {k: g.distance(p) for k, g in geoms.items()}
    k = min(d, key=d.get)
    return k, d[k]


# ───────────────────────────── 1. NACCS at the cuts ─────────────────────────────
def naccs_cuts():
    pts = B.read_zips(use_cache=True)
    pts.pop("_times")
    sp = np.array(sorted(pts))
    lon = np.array([pts[s]["lon"] for s in sp])
    lat = np.array([pts[s]["lat"] for s in sp])
    x, y = T.transform(lon, lat)
    P = shapely.points(x, y)
    rows = []
    for arm in ("hudson (new cut)", "hell_gate (new cut)"):
        ln = FORCED[arm]
        d = shapely.distance(ln, P)
        for k in np.flatnonzero(d <= B.DEFAULT_MAX_DIST):
            w = pts[int(sp[k])]["wl"]
            dry = int((w < B.DRY).sum())
            s = shapely.line_locate_point(ln, P[k])
            rows.append(dict(arm=arm.split()[0], sp=int(sp[k]), lon=lon[k], lat=lat[k], d_line_m=round(d[k]),
                             along_m=round(s), past_end=bool(s <= 0 or s >= ln.length),
                             in_nj2_ring=bool(RING_NJ2.contains(P[k])), depth_m=pts[int(sp[k])]["depth"],
                             dry_steps=dry, kept_by_builder=dry == 0,
                             peak_msl_m=float(np.nanmax(np.where(w < B.DRY, np.nan, w)))))
    df = pd.DataFrame(rows).sort_values(["arm", "d_line_m"])
    off, src = B._grid_offsets(df.lon.values, df.lat.values)
    df["msl_to_navd88_m"], df["datum_src"] = np.round(off, 4), src
    df["peak_navd88_m"] = np.round(df.peak_msl_m + off, 3)
    df.to_csv(HERE / "naccs_cuts_nj2.csv", index=False, float_format="%.5f")
    for a, g in df.groupby("arm"):
        k = g[g.kept_by_builder]
        print(f"[naccs] {a}: {len(g)} points within 2 km, {len(k)} wet all window; within 1 km and wet: "
              f"{list(k[k.d_line_m <= 1000].sp)}; datum grids: {sorted(set(g.datum_src))}")
    return df


# ───────────────────────────── 2. hand-placed structures ─────────────────────────
def read_polyfile(path, ncol_min=2):
    """SFINCS weir / wavemaker polyline file: name, 'nrows ncols', rows."""
    out, ln = [], [s for s in Path(path).read_text().splitlines() if s.strip()]
    i = 0
    while i < len(ln):
        name = ln[i].strip()
        nr, _nc = map(int, ln[i + 1].split()[:2])
        xy = np.array([list(map(float, s.split()[:2])) for s in ln[i + 2:i + 2 + nr]])
        out.append((name, xy))
        i += 2 + nr
    return out


def structures():
    rows = []
    files = {
        "weir: 1.1.0 premier (DEFAULT)": NJ2 / "structures/sfincs_overpeck_open_elizabeth_rahway_ground.weir",
        "wvm: 1.1.0 premier": NJ2 / "structures/v4_wavemaker_5m_mhw_snapbeach.wvm",
    }
    for kind, f in files.items():
        for name, xy in read_polyfile(f):
            g = shapely.LineString(xy) if len(xy) > 1 else shapely.Point(xy[0])
            k, d = nearest(FORCED, *g.centroid.coords[0])
            rows.append(dict(kind=kind, file=f.name, piece=name, n_vertices=len(xy), length_m=round(g.length),
                             in_new_area=bool(g.intersects(NEW_AREA)), d_new_area_m=round(g.distance(NEW_AREA)),
                             inside_nj2_ring=bool(RING_NJ2.contains(g)),
                             frac_inside_nj2_ring=round(g.intersection(RING_NJ2).length / max(g.length, 1e-9), 4),
                             nearest_forced=k, d_forced_m=round(min(v.distance(g) for v in FORCED.values()))))
    for f in sorted((NJ2 / "structures").glob("*.drn")):
        for j, s in enumerate(Path(f).read_text().split("\n")):
            if not s.strip():
                continue
            v = list(map(float, s.split()))
            g = shapely.LineString([(v[0], v[1]), (v[2], v[3])])
            rows.append(dict(kind="drn: 1.x side arm (NOT in 1.1.0)", file=f.name, piece=f"pair{j}", n_vertices=2,
                             length_m=round(g.length), in_new_area=bool(g.intersects(NEW_AREA)),
                             d_new_area_m=round(g.distance(NEW_AREA)), inside_nj2_ring=bool(RING_NJ2.contains(g)),
                             frac_inside_nj2_ring=1.0 if RING_NJ2.contains(g) else 0.0,
                             nearest_forced=nearest(FORCED, v[0], v[1])[0],
                             d_forced_m=round(min(q.distance(g) for q in FORCED.values()))))
    pool = gpd.read_file(NJ2 / "structures/overpeck_pool.geojson").to_crs(32618).union_all()
    rows.append(dict(kind="ini region: Overpeck pool", file="overpeck_pool.geojson", piece="overpeck_pool",
                     n_vertices=len(shapely.get_coordinates(pool)), length_m=round(pool.length),
                     in_new_area=bool(pool.intersects(NEW_AREA)), d_new_area_m=round(pool.distance(NEW_AREA)),
                     inside_nj2_ring=bool(RING_NJ2.contains(pool)), frac_inside_nj2_ring=1.0,
                     nearest_forced=nearest(FORCED, *pool.centroid.coords[0])[0],
                     d_forced_m=round(min(q.distance(pool) for q in FORCED.values()))))
    df = pd.DataFrame(rows)
    df.to_csv(HERE / "structures_carryover.csv", index=False)
    print(df.groupby("kind").agg(n=("piece", "size"), in_new_area=("in_new_area", "sum"),
                                 min_d_new_area_m=("d_new_area_m", "min"),
                                 min_frac_inside=("frac_inside_nj2_ring", "min")).to_string())
    return df


# ───────────────────────────── 3. SnapWave footprint ────────────────────────────
def snapwave_check():
    sys.path.insert(0, str(ROOT))
    v3 = gpd.read_file(ROOT / "data/region_v3_EDITED_inland.geojson").to_crs(32618).union_all()
    de = [(-75.585, 39.405), (-75.500, 39.460), (-74.850, 39.460), (-74.850, 38.600), (-76.000, 38.600),
          (-76.000, 39.405)]
    deb = shapely.Polygon(np.c_[T.transform(*np.array(de).T)])
    fp = v3.union(deb)
    ov = NEW_AREA.intersection(fp)
    names = {"Battery": (-74.0142, 40.7006), "Robbins Reef": (-74.0653, 40.6575), "Kill van Kull": (-74.11, 40.645),
             "Bergen Point": (-74.1463, 40.6391), "Hoboken": (-74.023, 40.744), "Hudson cut": (-73.946, 40.859),
             "Hell Gate cut": (-73.938, 40.776), "Gowanus": (-73.9898, 40.6769), "Bay Ridge": (-74.035, 40.63),
             "Narrows (old forced line, mid)": (-74.044, 40.606), "Lower Bay N": (-74.03, 40.56)}
    lines = [f"new area (nj2 ring minus v4_hot_plus ring): {NEW_AREA.area / 1e6:.1f} km2",
             f"of it inside v4's snapwave_footprint_ll (v3 region U delaware_bay): {ov.area / 1e6:.3f} km2",
             f"v3 region's northern limit: lat {gpd.GeoSeries([v3], crs=32618).to_crs(4326).total_bounds[3]:.4f}"]
    for k, (lo, la) in names.items():
        p = shapely.Point(T.transform(lo, la))
        lines.append(f"  {k:<32} in footprint: {fp.contains(p)!s:<5}  in nj2 ring: {RING_NJ2.contains(p)}")
    (HERE / "snapwave_footprint_check.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


# ───────────────────────────── 4. observation points ─────────────────────────────
ADDED = [
    # name, lon, lat, kind, obs_file (rel. data/), obs_var, station, survives, datum, source, note
    ("noaa_battery", -74.0142, 40.7006, "surge", "gtsm/noaa_sandy_validation_6min.nc", "waterlevel", 8518750, True,
     "NAVD88 (CO-OPS published NAVD88 tie; 6-min verified)",
     "NOAA CO-OPS 8518750 The Battery",
     "INTERIOR in nj2 (10.4 km from Hell Gate, 18.3 km from the Hudson cut): an independent holdout OF THE MODEL "
     "once the Narrows is no longer forced. NOT independent of the boundary PRODUCT: NACCS was presumably validated "
     "against it (NACCS - obs peak -0.03 m). Peak 3.44 m NAVD88 10-30 01:24 UTC. On v1.5 / v3 / v4 it was a "
     "forcing INPUT or outside the domain; it is still in noaa_sandy_validation(_6min).nc and still a BASE "
     "gauge-forcing support point for any non-NACCS arm (n_waterlevel_support)."),
    ("noaa_bergen_point", -74.1463, 40.6391, "surge", "nj2_design/obs_nj2_bergen_point_6min.nc", "waterlevel",
     8519483, True,
     "NAVD88 DERIVED: MLLW - 0.846 (station MSL-MLLW, 1983-2001) + VDatum LMSL->NAVD88 at the point (grid); "
     "no published NAVD88 tie at this station",
     "NOAA CO-OPS 8519483 Bergen Point West Reach (6-min verified, fetched in MLLW 2026-11-02)",
     "KvK west mouth / Newark Bay. Was inside v4 too but unscored (no NAVD88). Far from every nj2 forced line: "
     "an interior holdout. NACCS - obs peak -0.23 m (+36 min) at SP3510. Peak 3.54 m NAVD88 (derived) 10-30 01:24."
     " Position from the CO-OPS API metadata (-74.1463); the design memo used -74.1422 (~350 m E)."),
    ("sss_gowanus", -73.98984, 40.67688, "surge", None, None, None, False,
     "NAVD88 (STN peak 11.08 ft)",
     "USGS STN storm-tide sensor SSS-NY-KIN (Gowanus); OFR 2013-1043",
     "MODEL-ONLY until the series is pulled (STN instrument id not resolved here). Published peak 3.38 m NAVD88 "
     "(NACCS +0.05 m). 1.45 km from the nearest NACCS point. Interior holdout in nj2."),
    ("sss_hoboken", -74.0232, 40.7439, "surge", None, None, None, False,
     "n/a (sensor damaged, no peak)",
     "USGS STN SSS-NJ-HUD-001WL (Hoboken); SIR 2016-5085 Table 4",
     "MODEL-ONLY: the sensor was DAMAGED, no record. Kept as an output point at Hoboken (the new NJ area's "
     "headline community)."),
    ("sss_hackensack_hud002", -74.0661, 40.7998, "surge", None, None, None, False,
     "NAVD88 (SIR 2016-5085 Table 4 peak 8.8 ft)",
     "USGS STN SSS-NJ-HUD-002WL; SIR 2016-5085 Table 4",
     "MODEL-ONLY (peak only, 2.68 m NAVD88; series not pulled). Hackensack side, inside v4 too; 180 m from mark "
     "6095 (2.53 m), backs it to 0.15 m."),
    ("bc_hudson_cut", -73.9460, 40.8590, "surge", None, None, None, False, "model only",
     "nj2 boundary diagnostic", "MODEL-ONLY, ~110 m inside the hudson forced line: reads the imposed NACCS level. "
     "A FORCING diagnostic, never a holdout."),
    ("bc_hell_gate", -73.9385, 40.7760, "surge", None, None, None, False, "model only",
     "nj2 boundary diagnostic", "MODEL-ONLY, ~110 m inside the hell_gate forced line (the ~0.2 m NACCS question, "
     "hudson_design §6 / Decision 6). A FORCING diagnostic, never a holdout."),
]
NOT_ADDED = [
    ("Spuyten Duyvil sensor (SSS-NY-NEW)", "-73.92633, 40.87757", "OUTSIDE nj2 (Harlem / Hudson above the cut)"),
    ("Kings Point 8516945", "-73.7655, 40.8103", "OUTSIDE nj2 (Long Island Sound side of Hell Gate)"),
    ("Hudson stage gauges (Hastings, Alpine)", "", "no Sandy record (hudson_design §1) and above the cut"),
]


def staged_sources():
    d = xr.open_dataset(PREMIER / "sfincs_netsrcdisfile.nc")
    x = np.asarray(d["x"].values, float)
    y = np.asarray(d["y"].values, float)
    q = d["discharge"].max("time").values if "discharge" in d else np.full(x.size, np.nan)
    return x, y, q


def bergen_series():
    raw = json.loads((ROOT / "logs/hudson_design_2026-11-02/forcing_test/dl/wl_8519483_MLLW.json").read_text())
    dat = json.loads((ROOT / "logs/hudson_design_2026-11-02/forcing_test/dl/datums_8519483.json").read_text())
    dv = {r["name"]: r["value"] for r in dat["datums"]}
    lon, lat = float(raw["metadata"]["lon"]), float(raw["metadata"]["lat"])
    off, src = B._grid_offsets(np.array([lon]), np.array([lat]))
    msl_mllw = dv["MSL"] - dv["MLLW"]
    shift = -msl_mllw + float(off[0])  # NAVD88 = MLLW - (MSL-MLLW) + (MSL in NAVD88)
    t = pd.to_datetime([r["t"] for r in raw["data"]])
    v = np.array([float(r["v"]) if r["v"] not in ("", None) else np.nan for r in raw["data"]]) + shift
    ds = xr.Dataset({"waterlevel": (("time", "stations"), v[:, None])},
                    coords={"time": t, "stations": [8519483], "lon": ("stations", [lon]), "lat": ("stations", [lat])})
    ds.attrs = dict(title="NOAA CO-OPS 8519483 Bergen Point West Reach, 6-min verified water level, NAVD88 DERIVED",
                    source="https://api.tidesandcurrents.noaa.gov (product=water_level, datum=MLLW, units=metric, "
                           "time_zone=gmt), fetched 2026-11-02 (logs/hudson_design_2026-11-02/forcing_test/dl/)",
                    datum="NAVD88", units="m",
                    datum_chain=f"NAVD88 = MLLW - {msl_mllw:.3f} (station MSL - MLLW, epoch 1983-2001, CO-OPS datums) "
                                f"{float(off[0]):+.4f} (VDatum LMSL->NAVD88 at the station, {src[0]}); total "
                                f"{shift:+.4f} m. CO-OPS publishes no NAVD88 tie at this station.",
                    built_by="logs/nj2_edges_2026-11-14/edges_nj2.py")
    ds["waterlevel"].attrs = dict(units="m", datum="NAVD88")
    out = NJ2 / "obs_nj2_bergen_point_6min.nc"
    tmp = out.with_suffix(".nc.tmp")
    ds.to_netcdf(tmp)
    tmp.rename(out)
    print(f"[obs] Bergen Point: shift {shift:+.4f} m, peak {np.nanmax(v):.3f} m NAVD88 at {t[np.nanargmax(v)]}; "
          f"{out.relative_to(ROOT)}")


def obs():
    base = []
    for s in (PREMIER / "sfincs.obs").read_text().splitlines():
        if '"' in s:
            x, y = map(float, s.split('"')[0].split())
            base.append((s.split('"')[1], x, y))
    sx, sy, sq = staged_sources()
    rows = []
    for name, x, y in base:
        lo, la = TI.transform(x, y)
        rows.append(dict(name=name, lon=round(lo, 6), lat=round(la, 6), x=x, y=y, origin="1.1.0 premier sfincs.obs",
                         kind="", obs_file="(registry: unchanged from v4_refreeze)", obs_var="", obs_station="",
                         datum="as registered (NAVD88)", source="v4_refreeze obs_gauges", note=""))
    for (name, lo, la, kind, f, var, st, surv, datum, src, note) in ADDED:
        x, y = T.transform(lo, la)
        rows.append(dict(name=name, lon=lo, lat=la, x=round(x, 1), y=round(y, 1), origin="nj2 ADDED", kind=kind,
                         obs_file=f or "", obs_var=var or "", obs_station=st or "", datum=datum, source=src,
                         note=note))
    df = pd.DataFrame(rows)
    flags, dfl, nfl, dsr, qsr, drm = [], [], [], [], [], []
    for r in df.itertuples():
        k, d = nearest(FORCED, r.x, r.y)
        kr, d_r = nearest(REMOVED, r.x, r.y)
        j = int(np.argmin(np.hypot(sx - r.x, sy - r.y)))
        ds_ = float(np.hypot(sx[j] - r.x, sy[j] - r.y))
        f = []
        if d < 500:
            f.append("FORCED<500m")
        elif d < 3000:
            f.append("forced<3km (forcing-adjacent)")
        if ds_ < 500:
            f.append("SOURCE<500m")
        if not RING_NJ2.contains(shapely.Point(r.x, r.y)):
            f.append("OUTSIDE nj2 ring")
        if d_r < 3000 and d >= 3000:
            f.append(f"was {d_r / 1e3:.1f} km from {kr.split()[0]}: now interior")
        flags.append("; ".join(f))
        dfl.append(round(d))
        nfl.append(k.split()[0])
        dsr.append(round(ds_))
        qsr.append(round(float(sq[j]), 1))
        drm.append(f"{kr.split()[0]} {d_r / 1e3:.2f} km")
    df["d_forced_m"], df["nearest_forced"], df["d_source_m"], df["source_qmax_m3s"] = dfl, nfl, dsr, qsr
    df["v4_removed_arm_dist"], df["flags"] = drm, flags
    df.to_csv(NJ2 / "obs_nj2.csv", index=False)
    txt = "".join(f'{r.x:11.1f} {r.y:11.1f} "{r.name}"\n' for r in df.itertuples())
    (NJ2 / "obs_nj2.obs").write_text(txt)
    print(df[["name", "origin", "d_forced_m", "nearest_forced", "d_source_m", "flags"]]
          [(df.flags != "") | (df.origin != "1.1.0 premier sfincs.obs")].to_string())
    print(f"[obs] {len(df)} points ({len(base)} from 1.1.0 + {len(ADDED)} added) -> data/nj2_design/obs_nj2.csv/.obs;"
          f" not added: {[n for n, *_ in NOT_ADDED]}")


if __name__ == "__main__":
    print(f"[area] new area {NEW_AREA.area / 1e6:.1f} km2")
    naccs_cuts()
    structures()
    snapwave_check()
    bergen_series()
    obs()
