#!/usr/bin/env python
"""Little Egg Inlet's flood channels + the NJIWW behind Holgate → an OPTIONAL overlay tier.

    python scripts/build_littleegg_channel_v4.py

WHAT IS WRONG. Along the NJIWW reach IW_08_104 (lon −74.34 → −74.26, lat 39.50–39.56:
behind Long Beach Island's Holgate tip, then west from Little Egg Inlet's throat toward
Great Bay) CUDEM 1/9″ — and so the model — is a smooth ~−2 m surface. Three independent
surveys say the channel is far deeper (logs/refreeze_2026-10-05/bed_candidates/
littleegg_summary.txt, at the 13,317 soundings of the 2024 survey):
  * USACE eHydro IW_08_104_20240812_XC: p50 −5.7 m NAVD88 (model −2.0; d +3.3, p90 +7.2)
  * NOAA NOS H12597 (2014, multibeam + vertical beam BAGs, MLLW): the same channel, within
    +0.35 m (p50) of 2024 at 1,023 shared points; CUDEM matches H12597 to ±0.04 m
    everywhere ELSE (28,000 VB cells) — CUDEM ingested H12597 but not in this channel.
  * NOS H08220 / H08219 (1954): already 1.1–1.5 m deeper than CUDEM (p50), 1.4–2.6 m on
    the deep soundings — the channel is old and natural (tidal scour), not a dredge cut.
So it is not a datum or sign error in the 2024 survey; CUDEM is too shallow here.

⚠️ THE MATERIAL IS POST-SANDY (2014 and 2024). No pre-Sandy survey denser than the 1954
lead line exists. This tier is therefore OPTIONAL — the user decides whether to paint it
(FINDINGS: a post-storm product may override a pre-storm one only by decision). The 1954
survey says the channel was deep before Sandy too, which is why it is offered at all.

RULE, inside the declared box only, on a 5 m UTM 18N grid:
  * the H12597 multibeam (0.5 m) as 5 m medians (≥ 10 of 100 sub-cells), MLLW → NAVD88;
  * elsewhere within 40 m of a 2024 sounding: IDW (power 2, 8 nearest within 60 m) of the
    2024 soundings (CENAP gdb SurveyPoint.Z_use, POSITIVE ft below MLLW — sign checked);
  * PAINT only where that bed is deeper than CUDEM by > 1.0 m (CUDEM's smooth fill), else
    NoData. Plane: MLLW = −0.797 m NAVD88 (CO-OPS 8534720 Atlantic City, as the channel
    audit; no CO-OPS datum closer has both planes).

Output: data/elevation_v4/littleegg_channel/littleegg_channel_v4.tif (EPSG:32618, 5 m,
NoData −9999, m NAVD88). Painted by ``rebuild_subgrid.py --overlay littleegg_channel_v4``.
"""

from __future__ import annotations

import io
import os
import re
import tempfile
import urllib.request
import zipfile
from pathlib import Path

os.environ.setdefault(
    "PROJ_DATA", "/home/tpj8/nj_sandy_sfincs/micromamba/envs/sfincs/share/proj"
)

import netCDF4
import numpy as np
import pyproj
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data"
OUT = D / "elevation_v4" / "littleegg_channel"
SCRATCH = Path("/scratch/tpj8/nj_bight_sfincs_data/elevation_v4/littleegg_channel")
RAW = OUT / "raw"
DST = OUT / "littleegg_channel_v4.tif"
NODATA = -9999.0
RES = 5.0
EPSG = 32618
FT_TO_M = 0.3048006096012192
PLANE = -0.797  # MLLW in m NAVD88, CO-OPS 8534720 Atlantic City
BOX = (-74.345, 39.495, -74.255, 39.565)  # lon_min, lat_min, lon_max, lat_max
CUDEM = D / "elevation_v3" / "cudem_nj_v3.vrt"
SURVEY = "IW_08_104_20240812_XC"
SURVEY_URL = (
    "https://ehydroprod.blob.core.usgovcloudapi.net/ehydro-surveys/CENAP/"
    f"CENAP_DIS_{SURVEY}.ZIP"
)
BAG_URL = (
    "https://data.ngdc.noaa.gov/platforms/ocean/nos/coast/H12001-H14000/H12597/BAG/"
)
MB_BAG = "H12597_MB_50cm_MLLW_2of2.bag"
FOOTPRINT_M, RADIUS_M, K, POWER = 40.0, 60.0, 8, 2.0
MIN_GAIN = 1.0


def _get(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=600) as r:
        return r.read()


def fetch() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    gdb = RAW / f"{SURVEY}.gdb"
    if not gdb.exists():
        z = zipfile.ZipFile(io.BytesIO(_get(SURVEY_URL)))
        for n in z.namelist():
            if ".gdb/" in n:
                tail = n[n.index(".gdb/") + 5 :]
                if tail:
                    (gdb / tail).parent.mkdir(parents=True, exist_ok=True)
                    (gdb / tail).write_bytes(z.read(n))
        print(f"  fetched {SURVEY}")
    if not (RAW / MB_BAG).exists():
        (RAW / MB_BAG).write_bytes(_get(BAG_URL + MB_BAG))
        print(f"  fetched {MB_BAG}")


def survey_points() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    import geopandas as gpd

    sp = gpd.read_file(RAW / f"{SURVEY}.gdb", layer="SurveyPoint")
    if sp.crs is not None and sp.crs.to_epsg() != 3424:
        sp = sp.to_crs(3424)
    z = sp["Z_use"].astype(float).to_numpy()
    if (z < 0).mean() > 0.05:
        raise SystemExit(
            f"{SURVEY}: expected POSITIVE depths, {(z < 0).mean():.0%} < 0"
        )
    t = pyproj.Transformer.from_crs(3424, EPSG, always_xy=True)
    x, y = t.transform(sp.geometry.x.to_numpy(), sp.geometry.y.to_numpy())
    return np.asarray(x), np.asarray(y), -z * FT_TO_M + PLANE


def mb_medians(tr, nx, ny) -> np.ndarray:
    """H12597 multibeam (BAG, NAD83 UTM 18N, row 0 = SOUTH) as 5 m medians on the grid."""
    d = netCDF4.Dataset(RAW / MB_BAG)
    g = d.groups["BAG_root"]
    md = g.variables["metadata"][:]
    md = b"".join(np.asarray(md).astype("S1").ravel().tolist()).decode(errors="ignore")
    c = re.search(r"<gml:coordinates[^>]*>([^<]+)<", md).group(1).split()
    x0, y0 = map(float, c[0].split(","))
    res = float(re.search(r'<gco:Measure uom="m">([0-9.]+)<', md).group(1))
    e = g.variables["elevation"]
    k = int(round(RES / res))
    gx0, gy1 = tr.c, tr.f
    gy0 = gy1 - ny * RES
    c0 = int(round((gx0 - x0) / res))
    r0 = int(round((gy0 - y0) / res))
    blk = np.full((ny * k, nx * k), np.nan, "float32")
    rr0, rr1 = max(r0, 0), min(r0 + ny * k, e.shape[0])
    cc0, cc1 = max(c0, 0), min(c0 + nx * k, e.shape[1])
    if rr1 > rr0 and cc1 > cc0:
        blk[rr0 - r0 : rr1 - r0, cc0 - c0 : cc1 - c0] = e[rr0:rr1, cc0:cc1]
    d.close()
    blk[blk > 1e5] = np.nan
    b = blk.reshape(ny, k, nx, k).transpose(0, 2, 1, 3).reshape(ny, nx, k * k)
    n = np.isfinite(b).sum(2)
    with np.errstate(all="ignore"):
        med = np.nanmedian(b, axis=2) + PLANE
    med[n < 10] = np.nan
    return med[::-1]  # south-up → north-up


def main() -> int:
    if not OUT.exists():
        SCRATCH.mkdir(parents=True, exist_ok=True)
        OUT.symlink_to(SCRATCH)
    fetch()
    t = pyproj.Transformer.from_crs(4326, EPSG, always_xy=True)
    xs, ys = t.transform(
        [BOX[0], BOX[2], BOX[0], BOX[2]], [BOX[1], BOX[1], BOX[3], BOX[3]]
    )
    x0 = np.floor(min(xs) / RES) * RES
    y1 = np.ceil(max(ys) / RES) * RES
    nx = int(np.ceil((max(xs) - x0) / RES))
    ny = int(np.ceil((y1 - min(ys)) / RES))
    tr = from_origin(x0, y1, RES, RES)
    cu = np.full((ny, nx), np.nan, "float32")
    with rasterio.open(CUDEM) as src:
        reproject(
            source=rasterio.band(src, 1),
            destination=cu,
            dst_transform=tr,
            dst_crs=f"EPSG:{EPSG}",
            src_nodata=src.nodata,
            dst_nodata=np.nan,
            resampling=Resampling.bilinear,
        )
    sx, sy, sz = survey_points()
    print(f"  {SURVEY}: {len(sz)} soundings, z p50 {np.median(sz):+.2f} m NAVD88")
    X, Y = np.meshgrid(
        x0 + (np.arange(nx) + 0.5) * RES, y1 - (np.arange(ny) + 0.5) * RES
    )
    tree = cKDTree(np.column_stack([sx, sy]))
    pts = np.column_stack([X.ravel(), Y.ravel()])
    d1 = tree.query(pts, k=1)[0].reshape(ny, nx)
    dd, ii = tree.query(pts, k=K, distance_upper_bound=RADIUS_M)
    ok = np.isfinite(dd)
    w = np.where(ok, 1.0 / np.maximum(dd, 1.0) ** POWER, 0.0)
    zz = np.where(ok, sz[np.minimum(ii, len(sz) - 1)], 0.0)
    ws = w.sum(1)
    idw = np.where(ws > 0, (w * zz).sum(1) / np.where(ws > 0, ws, 1), np.nan)
    idw = idw.reshape(ny, nx)
    idw[d1 > FOOTPRINT_M] = np.nan
    mb = mb_medians(tr, nx, ny)
    bed = np.where(np.isfinite(mb), mb, idw)
    keep = np.isfinite(bed) & np.isfinite(cu) & (bed < cu - MIN_GAIN)
    out = np.where(keep, bed, NODATA).astype("float32")
    a = keep.sum() * RES**2 / 1e6
    print(
        f"  candidate cells {np.isfinite(bed).sum() * RES**2 / 1e6:.3f} km² "
        f"(H12597 MB {np.isfinite(mb).sum() * RES**2 / 1e6:.3f}); painted {a:.3f} km² "
        f"where > {MIN_GAIN} m deeper than CUDEM"
    )
    print(
        f"  CUDEM p50 {np.median(cu[keep]):+.2f} → bed p50 {np.median(bed[keep]):+.2f}, "
        f"p10 {np.percentile(bed[keep], 10):+.2f} m; from H12597 "
        f"{(keep & np.isfinite(mb)).sum() * RES**2 / 1e6:.3f} km²"
    )
    fd, tmp = tempfile.mkstemp(dir=OUT, prefix=f".{DST.name}.", suffix=".tif")
    os.close(fd)
    with rasterio.open(
        tmp,
        "w",
        driver="GTiff",
        height=ny,
        width=nx,
        count=1,
        dtype="float32",
        crs=f"EPSG:{EPSG}",
        transform=tr,
        nodata=NODATA,
        compress="DEFLATE",
        tiled=True,
        blockxsize=256,
        blockysize=256,
    ) as ds:
        ds.write(out, 1)
        ds.update_tags(
            source=f"NOS H12597 2014 MB (5 m medians), else IDW of eHydro {SURVEY}; "
            f"painted where > {MIN_GAIN} m deeper than CUDEM; box {BOX}. POST-SANDY "
            "material: optional tier",
            units="m NAVD88",
        )
    os.chmod(tmp, 0o644)
    os.replace(tmp, DST)
    print(f"  wrote {DST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
