"""Re-test 'never joined' tidal polygons with bigger windows: a real plug stays unjoined, a window artifact joins."""
import sys
sys.path.insert(0, "/cache/home/tpj8/nj_bight_sfincs/logs/bed_audit_2026-11-05/checks/impoundment")
import check
from shapely.geometry import Point
E = sys.argv[1]
bed = check.BedReader(E)
seed = check.build_seeds(bed, check.RAW / f"seeds_{E.rstrip('/').split('/')[-1]}.npz")
nwi = check.load_nwi()
for s in sys.argv[2:]:
    lon, lat = map(float, s.split(","))
    p = Point(*check.TO_UTM(lon, lat))
    g = sorted([r for r in nwi.itertuples() if r.file.startswith("nwi_tidal") and r.geom.distance(p) < 30], key=lambda q: -q.area_m2)[0]
    for pad in (3500, 8000, 15000):
        L, info = check.link_level(bed, seed, g.geom, pad, hi=3.0)
        print(s, g.code, round(g.area_m2), pad, L, info.get("why"), info.get("n_seed"), flush=True)
