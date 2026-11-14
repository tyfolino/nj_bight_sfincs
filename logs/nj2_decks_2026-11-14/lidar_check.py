"""Re-run the WATER rule on the NYC 2017 bare-earth lidar (independent) and on CUDEM 1/9" alone, for the
sweep's DAM rows and PARTIAL rows with a sill above 0 m. Writes lidar_check.csv."""
from pathlib import Path
import geopandas as gpd, numpy as np, pandas as pd, rasterio
from pyproj import Transformer
from sweep import Lidar, profile, judge, width_of
L = Path(__file__).parent
R = pd.read_csv(L / "osm_crossings_planned2012.csv")
S = R[(R.cls == "DAM") | ((R.cls == "PARTIAL") & (R.sill > 0))].copy()
br = gpd.read_file("/scratch/tpj8/nj_bight_sfincs_data/decks_2026-11-04/bridges.gpkg", bbox=(-74.12, 40.6, -73.9, 40.89)).to_crs(32618)
br = br[br.osm_id.isin(S.osm_id.astype(str)) | br.osm_id.isin(S.osm_id)].explode(index_parts=False)
li = Lidar()
cu = rasterio.open("/cache/home/tpj8/nj_bight_sfincs/data/elevation_v3/cudem_nj_v3.vrt")
tc = Transformer.from_crs(32618, 4269, always_xy=True).transform
def cud(x, y):
    shp = np.shape(x); X, Y = tc(np.ravel(x), np.ravel(y))
    v = np.array([q[0] for q in cu.sample(zip(X, Y), masked=False)], np.float32); v[v < -1e4] = np.nan
    return v.reshape(shp)
out = []
for _, s in S.iterrows():
    g = br[br.osm_id.astype(str) == str(s.osm_id)]
    if not len(g):
        continue
    r = g.iloc[0]
    hw = s.hw
    jl = judge(profile(r.geometry, hw, li))
    jc = judge(profile(r.geometry, hw, cud))
    out.append(dict(osm_id=s.osm_id, name=s["name"], highway=s.highway, cls=s.cls, sill=s.sill, chan=s.chan, span_m=s.span_m,
                    lidar_cls=jl.get("cls"), lidar_sill=jl.get("sill"), lidar_chan=jl.get("chan"),
                    cudem_cls=jc.get("cls"), cudem_sill=jc.get("sill"), lat=round(s.sill_lat, 5), lon=round(s.sill_lon, 5)))
O = pd.DataFrame(out); O.to_csv(L / "lidar_check.csv", index=False)
pd.set_option("display.width", 250); print(O.to_string())
