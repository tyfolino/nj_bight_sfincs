"""Upper Gowanus Canal carve, ASSUMED depth, both 2.0 beds (user 11-12 CARVE; 11-14: carry the 2020 section up).

    python -I logs/nj2_bed2026_2026-11-14/build_gowanus_upper.py      (repo root, sfincs env; < 1 min, < 1 GB)

No survey covers the canal from the end of eHydro GC_01_GCK_20200512 (~40.676 N) to its head at Butler St
(logs/v2_prep_2026-11-04/README.md §2 and §5: EPA / NYC DEP / USACE / BlueTopo checked, nothing). The user's call
(11-12, 11-14): carve it, both beds, depth = the 2020 survey's last section carried up the arm, labelled ASSUMED.

  CANAL  NYC 2017 topobathy (the 21-tile metre VRT; v2/vrt/nyc_topobathy_2017_m.vrt), AVERAGED onto the carve
         rasters' own 5 m lattice: the canal reads as a flat ~0.2 m water surface between 2-4 m banks. Canal = pixels
         < CANAL_MAX, the 8-connected component that touches the 2020 survey's main-channel end, north of LAT0.
  DEPTH  one number: the median of the GC_01_GCK_20200512 cells (source code 3 of carve_v2_2026_source.tif) in the
         main channel's last surveyed section (SECTION box). Carried flat to the head: no slope is assumed.
  OUT    gowanus_upper_v2_<bed>.tif = DEPTH on CANAL pixels that the bed's own carve (carve_v2_<bed>.tif) does not
         already hold (2012: the 2013 survey reaches further up, so its arm is shorter). Apply as min(bed, layer),
         AFTER carve_v2_<bed>:min. EPSG:32618, 5 m, the carve lattice (cropped), nodata -9999, m NAVD88.
Writes /scratch/tpj8/nj_bight_sfincs_data/v2/carves/gowanus_upper_v2_{2012,2026}.tif (new) + gowanus_upper.txt here.
"""
from pathlib import Path

import numpy as np
import pyproj  # noqa: F401
import rasterio
from pyproj import Transformer
from rasterio.warp import Resampling, reproject
from rasterio.windows import Window
from scipy import ndimage

REPO = Path("/cache/home/tpj8/nj_bight_sfincs")
HERE = REPO / "logs/nj2_bed2026_2026-11-14"
CV = Path("/scratch/tpj8/nj_bight_sfincs_data/v2/carves")
NYC = Path("/scratch/tpj8/nj_bight_sfincs_data/v2/vrt/nyc_topobathy_2017_m.vrt")
BOX = (-73.9960, 40.6740, -73.9850, 40.6845)  # lon0, lat0, lon1, lat1: the upper canal to Butler St
SECTION = (-73.9915, 40.6752, -73.9885, 40.6762)  # the 2020 survey's last main-channel section
LAT0 = 40.6755
CANAL_MAX = 0.6  # m NAVD88: water surface ~0.2, banks 2-4 m
ND = -9999.0
L = []


def p(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    L.append(s)


T = Transformer.from_crs(4326, 32618, always_xy=True)
Ti = Transformer.from_crs(32618, 4326, always_xy=True)
with rasterio.open(CV / "carve_v2_2026.tif") as d:
    full_t, prof = d.transform, d.profile
    xs, ys = T.transform([BOX[0], BOX[2]], [BOX[1], BOX[3]])
    c0, r0 = (int(v) for v in ~full_t * (min(xs), max(ys)))
    c1, r1 = (int(np.ceil(v)) for v in ~full_t * (max(xs), min(ys)))
    win = Window(c0, r0, c1 - c0, r1 - r0)
    tr = d.window_transform(win)
    z26 = d.read(1, window=win)
with rasterio.open(CV / "carve_v2_2026_source.tif") as d:
    s26 = d.read(1, window=win)
with rasterio.open(CV / "carve_v2_2012.tif") as d:
    assert d.transform == full_t
    z12 = d.read(1, window=win)
H, W = z26.shape
rr, cc = np.mgrid[0:H, 0:W]
X, Y = tr * (cc + 0.5, rr + 0.5)
LON, LAT = Ti.transform(X, Y)

sec = (s26 == 3) & (LON >= SECTION[0]) & (LON <= SECTION[2]) & (LAT >= SECTION[1]) & (LAT <= SECTION[3]) & (z26 != ND)
depth = float(np.median(z26[sec]))
p(f"2020 section (GC_01_GCK_20200512, {int(sec.sum())} cells in {SECTION}): p10 {np.percentile(z26[sec], 10):.2f} "
  f"p50 {depth:.2f} p90 {np.percentile(z26[sec], 90):.2f} m NAVD88 -> ASSUMED depth {depth:.2f} m")

ny = np.full((H, W), np.nan, "float32")
with rasterio.open(NYC) as s:
    reproject(rasterio.band(s, 1), ny, dst_transform=tr, dst_crs="EPSG:32618", dst_nodata=np.nan,
              resampling=Resampling.average)
low = np.isfinite(ny) & (ny < CANAL_MAX) & (LAT >= LAT0)
lab, n = ndimage.label(low, structure=np.ones((3, 3)))
seed_ids = np.unique(lab[sec & low])
seed_ids = seed_ids[seed_ids > 0]
canal = np.isin(lab, seed_ids)
p(f"NYC 2017 < {CANAL_MAX} m north of {LAT0}: {n} components; the one(s) at the section: {seed_ids.tolist()}, "
  f"{int(canal.sum())} px ({canal.sum() * 25 / 1e4:.2f} ha), lat {LAT[canal].min():.5f}..{LAT[canal].max():.5f}; "
  f"lidar there p50 {np.nanmedian(ny[canal]):.2f} m")

prof.update(width=W, height=H, transform=tr, nodata=ND, dtype="float32", compress="deflate")
for bed, zc in (("2012", z12), ("2026", z26)):
    have = zc != ND
    out = np.where(canal & ~have, np.float32(depth), np.float32(ND))
    k = out != ND
    f = CV / f"gowanus_upper_v2_{bed}.tif"
    tmp = f.with_suffix(".partial.tif")
    with rasterio.open(tmp, "w", **prof) as dst:
        dst.write(out, 1)
        dst.update_tags(bed=bed, status="ASSUMED depth (no survey; user 11-12 / 11-14)",
                        rule=f"canal = NYC 2017 lidar < {CANAL_MAX} m connected to the GCK 2020 section; z = that "
                             f"section's median {depth:.2f} m; apply as min(bed, layer) AFTER carve_v2_{bed}:min",
                        made_by="logs/nj2_bed2026_2026-11-14/build_gowanus_upper.py", units="m NAVD88")
    tmp.replace(f)
    p(f"{bed}: {int(k.sum())} px ({k.sum() * 25 / 1e4:.2f} ha) beyond carve_v2_{bed}, lat {LAT[k].min():.5f}.."
      f"{LAT[k].max():.5f}; the bed's carve already holds {int((canal & have).sum())} canal px -> {f}")
(HERE / "gowanus_upper.txt").write_text("\n".join(L) + "\n")
