"""
Download the FEMA Modeling Task Force (MOTF) Hurricane Sandy storm-surge EXTENT
for the NJ model domain and write a georeferenced binary flood mask (GeoTIFF),
for SPATIAL (extent) validation of the SFINCS flood map.

Source: Rutgers ArcGIS MapServer, layer 0 "Sandy Surge Extent" — FEMA MOTF
"Final Field-Verified High Resolution" footprint, built by interpolating a water
surface from USGS HWMs + storm-tide sensors over the 3 m DEM (best estimate as of
11 Nov 2012). https://njmaps1.rad.rutgers.edu/arcgis/rest/services/CoastalFlooding/StormSurge/MapServer

CAVEATS:
  - The NJ statewide extent is a SINGLE polygon feature too large for the service
    to return as vector (geometry comes back null even with maxAllowableOffset).
    We use the service's `export` (render) op: draw layer 0 over the domain at
    ~RES m and treat non-transparent pixels as flooded. Fine vs a 50 m model.
  - The MOTF surface is HWM/sensor-interpolated over lidar (a static "bathtub"
    surface, not a hydrodynamic run), sharing provenance with our HWMs. Treat
    this as an extent CONSISTENCY check, not independent validation.
  - Output covers the full (rotated) domain bbox; restrict to model land/active
    cells when scoring (the validation cell does this).

RUNTIME REQUIREMENT: this env's GDAL can't find proj.db on its own and aborts on
CRS write. Invoke with the data dirs exported in the shell:
    PROJ_LIB=$CONDA_PREFIX/share/proj PROJ_DATA=$CONDA_PREFIX/share/proj \\
    GDAL_DATA=$CONDA_PREFIX/share/gdal python scripts/download_sandy_motf_extent.py
(In-script os.environ assignment is too late — the GDAL shared lib has already
initialised by the time Python runs the assignment.)

Output: the active domain's `motf_tif` (uint8, 1=flooded, 0=dry; EPSG:32618).
"""
import io
import os
from pathlib import Path

# Import order matters with this env's GDAL: requests/geopandas/PIL must come
# before rasterio, or the GeoTIFF write aborts ("double free or corruption").
import requests
import numpy as np
import geopandas as gpd
from PIL import Image
import rasterio
from rasterio.transform import from_origin

ROOT = Path(os.environ.get("NJ_ROOT", Path(__file__).resolve().parents[1]))
# Region comes from the ACTIVE DOMAIN registry, so this script follows the
# domain being built instead of a fixed filename. (nj_sfincs/domain.py)
from nj_sfincs import domain as _domain  # noqa: E402
REGION = _domain.active().region
# 🔴 The output path is a DOMAIN fact (`Domain.motf_tif`), and this script REFUSES to
# write the archived one — the same guard, for the same reason, as
# download_sandy_hwms.py: `data/validation` is the frozen archive, the port fixture
# pins `motf_csi=0.637834` against that exact raster, and the render covers the ACTIVE
# region's bbox, so running under a bigger domain would silently rewrite the fixture's
# sheet (and pull more NY land in as fake-dry). A new domain gets its own `motf_tif`.
OUT = _domain.active().motf_tif
if "validation/" in str(OUT).replace("\\", "/") and OUT.name == "sandy_motf_extent.tif":
    raise SystemExit(
        f"refusing to write {OUT}: that is the FROZEN archive raster the port fixture "
        f"is pinned to. Give this domain its own `motf_tif` in nj_sfincs/domain.py first."
    )
EXPORT = ("https://njmaps1.rad.rutgers.edu/arcgis/rest/services/"
          "CoastalFlooding/StormSurge/MapServer/export")
EPSG = 32618
RES = 15.0   # m/pixel (export render resolution)

dom = gpd.read_file(REGION).to_crs(EPSG)
w, s, e, n = dom.total_bounds
W, H = int(round((e - w) / RES)), int(round((n - s) / RES))
print(f"domain bbox (EPSG:{EPSG}): {w:.0f},{s:.0f},{e:.0f},{n:.0f}  -> {W}x{H} @ {RES} m")

# ⚠️ The service caps a single export at maxImageWidth/Height = 4096 px (its own
# service JSON). v1.5's bbox fit in one call; v3's superset rectangle is ~9,300 x 13,100
# at 15 m, so the render is TILED: each tile is requested on its own exact bbox and
# pasted into the full array. Tile edges are pixel-aligned, so no seam and no resampling.
TILE = 4000
flooded = np.zeros((H, W), dtype="uint8")
ntile = 0
for r0 in range(0, H, TILE):
    for c0 in range(0, W, TILE):
        r1, c1 = min(r0 + TILE, H), min(c0 + TILE, W)
        tw, th = c1 - c0, r1 - r0
        tb = (w + c0 * RES, n - r1 * RES, w + c1 * RES, n - r0 * RES)
        r = requests.get(EXPORT, params={
            "bbox": ",".join(f"{v:.3f}" for v in tb), "bboxSR": str(EPSG),
            "imageSR": str(EPSG), "size": f"{tw},{th}", "layers": "show:0",
            "format": "png32", "transparent": "true", "f": "image",
        }, timeout=300)
        r.raise_for_status()
        rgba = np.array(Image.open(io.BytesIO(r.content)).convert("RGBA"))
        if rgba.shape[:2] != (th, tw):
            raise SystemExit(f"tile {ntile}: server returned {rgba.shape[:2]}, "
                             f"asked {(th, tw)} -- refusing to resample an extent mask")
        flooded[r0:r1, c0:c1] = (rgba[..., 3] > 10)   # non-transparent = surge extent
        ntile += 1
print(f"{ntile} tiles of <= {TILE} px")
print(f"rendered flooded pixels: {flooded.sum()} ({flooded.mean() * 100:.1f}%) "
      f"= {flooded.sum() * RES * RES / 1e6:.1f} km2")

OUT.parent.mkdir(parents=True, exist_ok=True)
tmp = OUT.with_suffix(OUT.suffix + ".tmp")
with rasterio.open(tmp, "w", driver="GTiff", height=H, width=W, count=1,
                   dtype="uint8", crs=f"EPSG:{EPSG}",
                   transform=from_origin(w, n, RES, RES),
                   nodata=255, compress="deflate") as dst:
    dst.write(flooded, 1)
os.replace(tmp, OUT)
print(f"Wrote {OUT}")
