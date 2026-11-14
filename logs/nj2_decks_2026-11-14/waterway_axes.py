"""Walk every OSM waterway axis in the nj2 new area on the planned 2012 bed (and the v1.1c base, and the
fill-to-harbour levels from connect.py): per axis, the highest point of the bed ALONG the axis (min within
r = 6 m of each 2.5 m station, i.e. the best way past each station) and its harbour fill level.
A ridge across a wet axis = the along-axis max far above its neighbours. Output waterway_axes.csv
(one row per axis piece) + waterway_ridges.csv (stations whose bed stands > MHHW with water both
ways along the axis within 60 m)."""
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


def load(p):
    with rasterio.open(p) as s:
        return s.read(1), s.transform


def main():
    z, T = load(D / "planned_2012.tif")
    zb, _ = load(D / "base_v11c.tif")
    F, _ = load(D / "fill_planned_2012.tif")
    a = gpd.read_file(REPO / "data/region_nj2.geojson").to_crs(32618).geometry.iloc[0]
    b = gpd.read_file(REPO / "data/region_v4_hot_plus.geojson").to_crs(32618).geometry.iloc[0]
    n = a.difference(b)
    w = gpd.read_file("/scratch/tpj8/nj_bight_sfincs_data/decks_2026-11-04/waterways.gpkg",
                      bbox=(-74.12, 40.60, -73.90, 40.89)).to_crs(32618)
    w = w[w.intersects(n) & (w.tunnel.fillna("no") == "no") & (w.culvert.fillna("no") == "no")]
    w = w.explode(index_parts=False)
    tr = Transformer.from_crs(32618, 4326, always_xy=True)
    off = [(dx, dy) for dx in np.arange(-5, 5.1, 2.5) for dy in np.arange(-5, 5.1, 2.5) if dx * dx + dy * dy <= 36]
    rows, ridges = [], []
    for _, r in w.iterrows():
        g = r.geometry.intersection(n.buffer(30))
        for line in getattr(g, "geoms", [g]):
            if line.length < 20 or line.geom_type != "LineString":
                continue
            s = np.arange(0, line.length, 2.5)
            P = np.array([line.interpolate(t).coords[0] for t in s])

            def samp(A, agg):
                vals = []
                for dx, dy in off:
                    c = np.floor((P[:, 0] + dx - T.c) / T.a).astype(int)
                    rr = np.floor((P[:, 1] + dy - T.f) / T.e).astype(int)
                    ok = (c >= 0) & (c < A.shape[1]) & (rr >= 0) & (rr < A.shape[0])
                    v = np.full(len(P), np.nan, np.float32)
                    v[ok] = A[rr[ok], c[ok]]
                    vals.append(v)
                return agg(np.array(vals), 0)

            zz = samp(z, np.nanmin)
            zzb = samp(zb, np.nanmin)
            ff = samp(np.where(np.isinf(F), 99, F), np.min)
            k = int(np.nanargmax(zz))
            lon, lat = tr.transform(*P[k])
            rows.append(dict(name=r["name"], waterway=r.waterway, osm_id=r.osm_id, len_m=round(line.length),
                             bed_p50=round(float(np.nanmedian(zz)), 2), bed_max=round(float(zz[k]), 2),
                             base_max=round(float(np.nanmax(zzb)), 2), fill_max=round(float(np.max(ff)), 2),
                             frac_above_mhhw=round(float(np.mean(zz > MHHW)), 3), max_lat=round(lat, 5), max_lon=round(lon, 5)))
            # ridge stations: bed > MHHW, and the axis is wet (< MHHW) within 60 m on BOTH sides
            wet = zz < MHHW
            for i in np.where(zz > MHHW)[0]:
                lo, hi = max(0, i - 24), min(len(zz), i + 25)
                if wet[lo:i].any() and wet[i + 1:hi].any():
                    lon, lat = tr.transform(*P[i])
                    ridges.append(dict(name=r["name"], waterway=r.waterway, osm_id=r.osm_id, s=s[i], bed=round(float(zz[i]), 2),
                                       base=round(float(zzb[i]), 2), fill=round(float(ff[i]), 2), lat=lat, lon=lon,
                                       x=P[i, 0], y=P[i, 1]))
    A = pd.DataFrame(rows).sort_values("bed_max", ascending=False)
    A.to_csv(L / "waterway_axes.csv", index=False)
    R = pd.DataFrame(ridges)
    R.to_csv(L / "waterway_ridges.csv", index=False)
    pd.set_option("display.width", 250)
    print(A.to_string())
    if len(R):
        # one row per ridge run
        R["run"] = (R.osm_id != R.osm_id.shift()) | (R.s.diff() > 3)
        R["run"] = R.run.cumsum()
        G = R.groupby("run").agg(name=("name", "first"), osm_id=("osm_id", "first"), n=("s", "size"), bed_max=("bed", "max"),
                                 base_max=("base", "max"), lat=("lat", "mean"), lon=("lon", "mean"))
        G["len_m"] = G.n * 2.5
        G.to_csv(L / "waterway_ridge_runs.csv")
        print(G.sort_values("bed_max", ascending=False).to_string())


if __name__ == "__main__":
    main()
