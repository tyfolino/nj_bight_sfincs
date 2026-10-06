#!/usr/bin/env python
"""The Raritan's side channels and bank margins at Sayreville / Edison → one overlay tier.

    python scripts/build_riverbed_sayreville_v4.py

WHAT THIS FIXES. In the western Raritan Bay corner no CUDEM 1/9″ tile exists and CoNED is
clipped, so the bed falls through to 3DEP 1/3″, which holds the low-tide WATER SURFACE
(−0.55 … −0.67 m) as the bed (10-05 channel sweep, class F1). The main river here is
covered — the 2012 eHydro survey (`ehydro_raritan_ak`) in the dredged channel and the
`riverbeds_v4` H05647 profile across the NHD polygon — but the strips between that polygon
and the real shoreline, the channel behind the island at Edison and the creek mouths are
not: 0.50 km² on the 3DEP surface. The NOS H05647 soundings (1934) that fall on it read
−2.26 m (p50, 23 pts) and the ENC soundings −2.96 m (8 pts), 1.6–2.4 m below the model.

MATERIAL. The pre-Sandy USACE survey RR_01_RAR_20120726 (−95 d; the soundings behind
``ehydro_raritan_ak``, CENAN negative ft below its stated MLLW plane, −0.90 m NAVD88), whose
swaths reach past that tier's footprint into the channel-side margins; NOS H05647 (1934
lead line, MLW → NAVD88 by VDatum, epoch-corrected;
``data/elevation_v4/nos_hydro/nos_H05647_v4_points.csv``) plus NOAA ENC SOUNDG from cells
US5NYCAB / US5NYCAC / US5NYCBC (MLLW → NAVD88: the H05647 VDatum MLW plane − 0.07 m). ENC
soundings whose source date is 1934 are H05647 itself and are dropped. ⚠️ H05647 reads
~1.2 m SHALLOW against the 2012 survey in the DREDGED channel; these margins were never
dredged, so no correction is applied. Chart soundings are shoal-biased: if anything the bed
here is still high.

RULE, inside the declared box only, on a 3 m UTM 18N grid:
  * PAINT where 3DEP < −0.4 m (a water surface; land is above 0) AND every tier that
    outranks 3DEP in the merge and is plausible here is NoData: ``riverbeds_v4``,
    ``ehydro_raritan_ak``, ``ehydro_nj``, ``usace_nj_2010_v3``, ``coned_sw_raritan``, ``cudem_nj_v3`` and the
    ``ehydro_refreeze_cenan_v4`` overlay — so the 3DEP surface is what the model has;
  * the value is the inverse-distance (power 2) mean of the 8 nearest soundings within
    250 m — of the 2012 survey ALONE where a 2012 sounding lies within 30 m, else of all
    three sets — and only where it is deeper than the 3DEP surface by > 0.10 m. No
    sounding within 250 m → NoData (no extrapolation).

Output: data/elevation_v4/riverbed_margins/riverbed_sayreville_v4.tif (EPSG:32618, 3 m,
NoData −9999, m NAVD88). Painted by ``rebuild_subgrid.py --overlay riverbed_sayreville_v4``.
The Rahway mouth (the other 3DEP patch) has NO sounding of any kind (no ENC cell west of
lon −74.25, no NOS survey, no eHydro channel) and is not built here.
"""

from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path

os.environ.setdefault(
    "PROJ_DATA", "/home/tpj8/nj_sandy_sfincs/micromamba/envs/sfincs/share/proj"
)
os.environ["OGR_S57_OPTIONS"] = "SPLIT_MULTIPOINT=ON,ADD_SOUNDG_DEPTH=ON"

import numpy as np
import pandas as pd
import pyproj
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject
from scipy.interpolate import griddata
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data"
OUT = D / "elevation_v4" / "riverbed_margins"
SCRATCH = Path("/scratch/tpj8/nj_bight_sfincs_data/elevation_v4/riverbed_margins")
DST = OUT / "riverbed_sayreville_v4.tif"
NODATA = -9999.0
RES = 3.0
EPSG = 32618

BOX = (-74.350, 40.478, -74.300, 40.512)  # lon_min, lat_min, lon_max, lat_max
DEP3 = D / "elevation_v4" / "dep3_v4.vrt"
#: tiers that outrank 3DEP and could hold water here; 3DEP is the bed only where all are
#: NoData (nj_10ft_dem_v4 is masked below 0.001 m in the merge, so it never holds water).
ABOVE = {
    "riverbeds_v4": D / "elevation_v4" / "riverbeds" / "riverbeds_v4.vrt",
    "ehydro_raritan_ak": D / "elevation_v1_5" / "ehydro_raritan_ak.tif",
    "ehydro_nj": D / "elevation" / "ehydro_nj.tif",
    "usace_nj_2010_v3": D / "elevation_v3" / "usace_nj_2010_topobathy_v3.tif",
    "coned_sw_raritan": D / "elevation_v1_5" / "coned_sw_raritan.tif",
    "cudem_nj_v3": D / "elevation_v3" / "cudem_nj_v3.vrt",
    "ehydro_refreeze_cenan_v4": D
    / "elevation_v4"
    / "ehydro"
    / "ehydro_refreeze_cenan_v4.tif",
}
H05647 = D / "elevation_v4" / "nos_hydro" / "nos_H05647_v4_points.csv"
VDATUM_MLW = D / "elevation_v4" / "nos_hydro" / "raw" / "vdatum_mlw_H05647.csv"
MLW_MINUS_MLLW = 0.07  # m, Sandy Hook / Perth Amboy CO-OPS datums
ENC_URL = "https://charts.noaa.gov/ENCs/{cell}.zip"
#: US5NYCAB is already in the repo (riverbeds_v4); AC / BC are fetched into OUT/raw.
ENC = [
    D / "elevation_v4" / "enc" / "raw" / "US5NYCAB" / "US5NYCAB.000",
    OUT / "raw" / "US5NYCAC.000",
    OUT / "raw" / "US5NYCBC.000",
]
RR01 = D / "elevation_v1_5" / "ehydro" / "raw" / "RR_01_RAR_20120726_CS_3844_15X"
FT_TO_M = 0.3048006096012192
K, RADIUS, POWER, MIN_GAIN = 8, 250.0, 2.0, 0.10
R2012 = 30.0
SURFACE_MAX = -0.4


def grid():
    t = pyproj.Transformer.from_crs(4326, EPSG, always_xy=True)
    xs, ys = t.transform(
        [BOX[0], BOX[2], BOX[0], BOX[2]], [BOX[1], BOX[1], BOX[3], BOX[3]]
    )
    x0 = np.floor(min(xs) / RES) * RES
    y1 = np.ceil(max(ys) / RES) * RES
    nx = int(np.ceil((max(xs) - x0) / RES))
    ny = int(np.ceil((y1 - min(ys)) / RES))
    return from_origin(x0, y1, RES, RES), nx, ny


def warp(path: Path, tr, nx, ny) -> np.ndarray:
    out = np.full((ny, nx), np.nan, "float32")
    with rasterio.open(path) as src:
        reproject(
            source=rasterio.band(src, 1),
            destination=out,
            dst_transform=tr,
            dst_crs=f"EPSG:{EPSG}",
            src_nodata=src.nodata,
            dst_nodata=np.nan,
            resampling=Resampling.nearest,
        )
    out[np.abs(out) > 1e5] = np.nan
    return out


def fetch_enc() -> None:
    import urllib.request
    import zipfile

    for f in ENC:
        if f.exists():
            continue
        f.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(ENC_URL.format(cell=f.stem), timeout=180) as r:
            z = zipfile.ZipFile(io.BytesIO(r.read()))
        name = next(n for n in z.namelist() if n.endswith(f"{f.stem}.000"))
        f.write_bytes(z.read(name))
        print(f"  fetched {f.name}")


def soundings() -> pd.DataFrame:
    import geopandas as gpd
    import pyogrio

    h = pd.read_csv(H05647)[["lon", "lat", "z_navd88"]].assign(src="H05647")
    c = np.loadtxt(VDATUM_MLW, delimiter=",", skiprows=1)
    rows = []
    for f in ENC:
        if not f.exists() or "SOUNDG" not in {n for n, _ in pyogrio.list_layers(f)}:
            raise SystemExit(f"no SOUNDG in {f}")
        s = gpd.read_file(f, layer="SOUNDG", engine="pyogrio")
        s = s[~s["SORDAT"].fillna("").str.startswith("1934")]
        lon, lat = s.geometry.x.to_numpy(), s.geometry.y.to_numpy()
        plane = (
            griddata(c[:, :2], c[:, 2], (lon, lat), method="nearest") - MLW_MINUS_MLLW
        )
        rows.append(
            pd.DataFrame(
                {"lon": lon, "lat": lat, "z_navd88": -s["DEPTH"].to_numpy() + plane}
            ).assign(src=f"ENC {f.stem}")
        )
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    import download_ehydro_nj as ehnj

    f = ehnj._one(RR01, ".xyz")
    a = ehnj.read_xyz(f)
    if (a[:, 2] < 0).mean() < 0.5:
        raise SystemExit(f"{f.name}: CENAN expects negative elevations")
    plane = ehnj.stated_offset_m(f)
    lon, lat = pyproj.Transformer.from_crs(3424, 4326, always_xy=True).transform(
        a[:, 0], a[:, 1]
    )
    rows.append(
        pd.DataFrame(
            {"lon": lon, "lat": lat, "z_navd88": a[:, 2] * FT_TO_M + plane}
        ).assign(src="RR_01_2012")
    )
    d = pd.concat([h, *rows], ignore_index=True)
    pad = 0.01
    d = d[
        (d.lon > BOX[0] - pad)
        & (d.lon < BOX[2] + pad)
        & (d.lat > BOX[1] - pad)
        & (d.lat < BOX[3] + pad)
    ]
    return d.drop_duplicates(["lon", "lat", "z_navd88"]).reset_index(drop=True)


def main() -> int:
    if not OUT.exists():
        SCRATCH.mkdir(parents=True, exist_ok=True)
        OUT.symlink_to(SCRATCH)
    fetch_enc()
    tr, nx, ny = grid()
    d3 = warp(DEP3, tr, nx, ny)
    water = np.isfinite(d3) & (d3 < SURFACE_MAX)
    for k, p in ABOVE.items():
        v = warp(p, tr, nx, ny)
        n0 = water.sum()
        water &= ~np.isfinite(v)
        print(f"  {k}: removes {n0 - water.sum()} px")
    s = soundings()
    print(f"  soundings: {s.src.value_counts().to_dict()}")
    t = pyproj.Transformer.from_crs(4326, EPSG, always_xy=True)
    sx, sy = t.transform(s.lon.to_numpy(), s.lat.to_numpy())
    tree = cKDTree(np.column_stack([sx, sy]))
    rr, cc = np.nonzero(water)
    px = tr.c + (cc + 0.5) * RES
    py = tr.f - (rr + 0.5) * RES
    pts = np.column_stack([px, py])
    z = s.z_navd88.to_numpy()

    def idw(tree, zv, pts):
        dd, ii = tree.query(pts, k=K, distance_upper_bound=RADIUS)
        ok = np.isfinite(dd)
        w = np.where(ok, 1.0 / np.maximum(dd, 1.0) ** POWER, 0.0)
        zz = np.where(ok, zv[np.minimum(ii, len(zv) - 1)], 0.0)
        ws = w.sum(1)
        return np.where(ws > 0, (w * zz).sum(1) / np.where(ws > 0, ws, 1), np.nan)

    val = idw(tree, z, pts)
    new = (s.src == "RR_01_2012").to_numpy()
    t12 = cKDTree(np.column_stack([sx[new], sy[new]]))
    near12 = t12.query(pts, k=1, distance_upper_bound=R2012)[0] < np.inf
    val[near12] = idw(t12, z[new], pts[near12])
    print(f"  2012-survey-only pixels: {near12.sum() * RES**2 / 1e6:.3f} km²")
    keep = np.isfinite(val) & (val < d3[rr, cc] - MIN_GAIN)
    out = np.full((ny, nx), NODATA, "float32")
    out[rr[keep], cc[keep]] = val[keep]
    a = keep.sum() * RES**2 / 1e6
    print(
        f"  3DEP-surface water with no higher tier: {water.sum() * RES**2 / 1e6:.3f} km²; "
        f"painted {a:.3f} km² (no sounding ≤ {RADIUS:.0f} m: "
        f"{(~np.isfinite(val)).sum() * RES**2 / 1e6:.3f} km²)"
    )
    if keep.any():
        print(
            f"  3DEP p50 {np.nanmedian(d3[rr[keep], cc[keep]]):+.2f} → bed p50 "
            f"{np.median(val[keep]):+.2f}, p10 {np.percentile(val[keep], 10):+.2f}, "
            f"p90 {np.percentile(val[keep], 90):+.2f} m"
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
            source="IDW (k 8, r 250 m, p 2) of eHydro RR_01 2012 (alone within 30 m), NOS "
            "H05647 1934 + ENC soundings, where 3DEP "
            f"< {SURFACE_MAX} m is the bed (no higher tier), box {BOX}",
            units="m NAVD88",
        )
    os.chmod(tmp, 0o644)
    os.replace(tmp, DST)
    print(f"  wrote {DST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
