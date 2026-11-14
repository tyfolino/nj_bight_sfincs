"""Build the modern-bed tier bluetopo_newer_2026 (2026-11-06), with the MLLW -> NAVD88 fix applied.

    python -I logs/modern_bed_b_2026-11-06/build_bluetopo_newer.py --workers 16

Rule (logs/modern_inputs_2026-11-04/README.md section 2; user 11-04 decision 3): a BlueTopo pixel is
written when its contributor is a NAMED survey (not 0 / NBSGeneralization), the survey ends after
the source cut-off of the CUDEM 1/9" build under it (bluetopo_newer.py's per-pixel test, imported
unchanged), BlueTopo z < -1 m, inside region_v4, and modern_land_2026 has NO data there (BlueTopo
never overwrites the 1-3 m lidar / topobathy).

MLLW fix (logs/bluetopo_mllw_2026-11-06/README.md): for MLLW-native contributors (USACE district
eHydro surveys except JALBTCX lidar, and the Navy's E00214), at pixels whose VDatum code is NOT
core (edge-weighted 11-16 or filled 20), z += sep (sep < 0: deeper) — BlueTopo left those in MLLW.
sep from sep_lib.separation(..., "pooled_nearest") at the native pixel centres.

Native 4 / 8 / 16 m kept; one COG-style tile per BlueTopo tile (EPSG:26918, NAVD88 metres, nodata
-9999) + bluetopo_newer_2026.vrt, in
/scratch/tpj8/nj_bight_sfincs_data/elevation_modern_2026/b/bluetopo_newer/ ; summary json here.
"""

# nj2 COPY (2026-11-14) of logs/modern_bed_b_2026-11-06/build_bluetopo_newer.py: identical rules; only the paths come from the environment so the
# process-pool workers (forkserver on Python 3.14 re-imports this module) see them. Unset = round b's values.
#   NJ2_HERE (summary dir), NJ2_MLAND (modern_land tif), NJ2_BT_OUT, NJ2_RING_CSV (ring)

from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import os
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

os.environ.setdefault("PROJ_DATA", "/home/tpj8/nj_sandy_sfincs/micromamba/envs/sfincs/share/proj")
import pyproj  # noqa: E402
import numpy as np  # noqa: E402
import geopandas as gpd  # noqa: E402
import rasterio  # noqa: E402
from rasterio.features import rasterize  # noqa: E402
from rasterio.warp import Resampling, reproject  # noqa: E402
from shapely.geometry import box  # noqa: E402

REPO = Path("/cache/home/tpj8/nj_bight_sfincs")
HERE = Path(os.environ.get("NJ2_HERE", REPO / "logs/modern_bed_b_2026-11-06"))
RAW = Path("/scratch/tpj8/nj_bight_sfincs_data/modern_2026/raw/bluetopo")
MLAND = Path(os.environ.get("NJ2_MLAND", REPO / "data/elevation_modern_2026/modern_land_2026.tif"))
OUT = Path(os.environ.get("NJ2_BT_OUT", "/scratch/tpj8/nj_bight_sfincs_data/elevation_modern_2026/b/bluetopo_newer"))
RING = os.environ.get("NJ2_RING_CSV")  # a named-vertex ring CSV (name, lon, lat); unset = data/region_v4.geojson
ND = -9999.0
CORE = (1, 2, 3, 4, 5, 6)

_spec = importlib.util.spec_from_file_location("btn", REPO / "logs/modern_inputs_2026-11-04/bluetopo_newer.py")
BTN = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(BTN)  # its main() is __main__-guarded
sys.path.insert(0, str(REPO / "logs/bluetopo_mllw_2026-11-06"))
import sep_lib  # noqa: E402


def mllw_native(t):
    inst = t.source_institution.fillna("")
    sid = t.source_survey_id.fillna("")
    return (inst.str.contains("Corps of Engineers") & ~inst.str.contains("JALBTCX")) | sid.str.startswith("E00214")


def work(args):
    tif, ring_utm, cud = args
    tile = Path(tif).name.split("_")[1]
    with rasterio.open(tif) as src:
        z = src.read(1, masked=True)
        c = src.read(3)
        tr, shp, crs = src.transform, (src.height, src.width), src.crs
        res = src.res[0]
    valid = ~np.ma.getmaskarray(z)
    zz = np.where(valid, z.filled(np.nan), np.nan).astype("float32")
    inring = rasterize([(ring_utm, 1)], out_shape=shp, transform=tr, fill=0, dtype="uint8").astype(bool)
    if not (valid & inring).any():
        return dict(tile=tile, km2=0.0)
    vcode = rasterize(cud, out_shape=shp, transform=tr, fill=0, dtype="uint8")
    t = BTN.rat(tif + ".aux.xml")
    t["named"] = (t.value != 0) & ~t.source_survey_id.fillna("").str.contains("Generaliz", case=False)
    lut_end = dict(zip(t.value, t.survey_date_end.fillna("0000-00-00")))
    vals = np.unique(c)
    named = np.isin(c, t.value[t.named].values)
    cutv = {0: BTN.NONE_CUT, **{BTN.VCODE[k]: v for k, v in BTN.CUT.items()}}
    newer = np.zeros(shp, bool)
    for vc, cut in cutv.items():
        sel = [v for v in vals if lut_end.get(v, "0000") > cut]
        if sel:
            newer |= (vcode == vc) & np.isin(c, sel)
    keep = valid & inring & named & newer & (zz < -1)
    # not where modern_land has data
    ml = np.full(shp, ND, "float32")
    with rasterio.open(MLAND) as m:
        reproject(rasterio.band(m, 1), ml, dst_transform=tr, dst_crs=crs, resampling=Resampling.nearest,
                  src_nodata=ND, dst_nodata=ND)
    keep &= ml == ND
    if not keep.any():
        return dict(tile=tile, km2=0.0)
    out = np.full(shp, ND, "float32")
    out[keep] = zz[keep]
    # MLLW fix
    nat = set(t.value[mllw_native(t)].astype(int))
    cand = keep & np.isin(c, list(nat)) if nat else np.zeros(shp, bool)
    nfix = 0
    fix_sum = 0.0
    if cand.any():
        rr, cc = np.where(cand)
        xs, ys = rasterio.transform.xy(tr, rr, cc)
        lon, lat = pyproj.Transformer.from_crs(crs, 4326, always_xy=True).transform(np.array(xs), np.array(ys))
        sep, code = sep_lib.separation(lon, lat, "pooled_nearest")
        f = (code != 0) & ~np.isin(code, CORE) & np.isfinite(sep)
        out[rr[f], cc[f]] = zz[rr[f], cc[f]] + sep[f]
        nfix = int(f.sum())
        fix_sum = float(sep[f].sum()) if nfix else 0.0
    dst = OUT / f"bluetopo_newer_{tile}.tif"
    prof = dict(driver="GTiff", height=shp[0], width=shp[1], count=1, dtype="float32", crs=crs, transform=tr,
                nodata=ND, compress="deflate", tiled=True, blockxsize=256, blockysize=256, predictor=3)
    tmp = dst.with_suffix(".tmp.tif")
    with rasterio.open(tmp, "w", **prof) as d:
        d.write(out, 1)
    os.replace(tmp, dst)
    a = res * res / 1e6
    return dict(tile=tile, res=res, km2=float(keep.sum() * a), km2_mllw_fixed=float(nfix * a),
                fix_mean_m=(fix_sum / nfix if nfix else None), file=dst.name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=16)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("bluetopo_newer_*.tif"):
        f.unlink()
    if RING:
        import pandas as pd
        from shapely.geometry import Polygon
        rv = pd.read_csv(RING)
        ring_utm = gpd.GeoSeries([Polygon(zip(rv.lon, rv.lat))], crs=4326).to_crs(26918).iloc[0]
    else:
        ring_utm = gpd.read_file(REPO / "data/region_v4.geojson").to_crs(26918).union_all()
    tiles = BTN.cudem_tiles()
    cg = gpd.GeoDataFrame(dict(code=[BTN.VCODE[v] for v in tiles.values()]),
                          geometry=[box(w, n - 0.25, w + 0.25, n).segmentize(0.005) for (n, w) in tiles],
                          crs=4326).to_crs(26918)
    cud = list(zip(cg.geometry, cg.code))
    tifs = sorted(glob.glob(str(RAW / "BlueTopo_*.tiff")))
    print(f"{len(tifs)} BlueTopo tiles", flush=True)
    recs = []
    with ProcessPoolExecutor(a.workers) as ex:
        for i, r in enumerate(ex.map(work, [(t, ring_utm, cud) for t in tifs], chunksize=2)):
            recs.append(r)
            if i % 50 == 0:
                print(f"  {i}/{len(tifs)}", flush=True)
    files = sorted(str(p) for p in OUT.glob("bluetopo_newer_*.tif"))
    # finest resolution wins where tiles overlap: list coarse first so finer tiles paint last
    res_of = {r["file"]: r.get("res", 99) for r in recs if r.get("file")}
    files.sort(key=lambda p: -res_of.get(Path(p).name, 99))
    lst = OUT / "tiles.txt"
    lst.write_text("\n".join(Path(p).name for p in files) + "\n")
    vrt = OUT / "bluetopo_newer_2026.vrt"
    subprocess.run(["gdalbuildvrt", "-overwrite", "-srcnodata", str(ND), "-vrtnodata", str(ND),
                    "-resolution", "highest", "-input_file_list", lst.name, vrt.name], cwd=OUT, check=True)
    tot = dict(tiles_written=len(files), km2=round(sum(r.get("km2", 0) for r in recs), 2),
               km2_mllw_fixed=round(sum(r.get("km2_mllw_fixed", 0) or 0 for r in recs), 3))
    (HERE / "bluetopo_newer_summary.json").write_text(json.dumps(dict(total=tot, tiles=recs), indent=1))
    print("total:", tot)


if __name__ == "__main__":
    main()
