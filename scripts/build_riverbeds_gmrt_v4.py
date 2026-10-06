#!/usr/bin/env python
"""Bed overlays for the A+ tidal reaches whose bed falls through to GMRT → one VRT.

    python scripts/build_riverbeds_gmrt_v4.py fetch   # network: NHD HU4 0204, ENC, NOS
    python scripts/build_riverbeds_gmrt_v4.py build   # rasters + VRT (no network)

WHY. In ``v4_hot_plus`` four tidal rivers have no CUDEM 1/9" tile, no 3DEP tile
(n40w075 / n39w075 are missing) and no lidar below the waterline (the NJ 10 ft DEM is
used only >= 0.001 m), so the merged bed falls through to GMRT, the last tier: LAND
heights of +1 to +5 m, or a flat 0 m, in the channel. The tide dies where each river
enters the hole (``logs/audit_v4_hot_plus_2026-10-05/blocked_low_ground`` lens 2;
``channels_and_3dep`` class F6): the Maurice (Mauricetown reach), the Mullica (Lower
Bank -> Batsto), the Tuckahoe (above Tuckahoe) and the Rancocas (both branches).

THE RULE (user, 2026-10-05; the Cohansey's, ``build_riverbed_cohansey_v4.py``):
  1. measured soundings where they exist FOR THAT REACH, as a 1-D along-channel profile
     (running median, ``build_riverbeds_v4`` mode "soundings"). No eHydro survey reaches
     any of the four (the Maurice federal channel ends at lat 39.21). The soundings are
     NOAA ENC SOUNDG (MLLW) or, where the chart has none and a digital NOS H-survey does,
     the H-survey (MLW, epoch-corrected as ``download_nos_hydro_v4.py`` does).
  2. elsewhere, and upstream of the last sounding: ``DEPTH_BELOW_MLLW_M`` (1.2 m) below
     MLLW, flat across the channel. MLLW - NAVD88 per reach from NOAA CO-OPS stations
     that publish BOTH datums (VDatum's API answers 412 on this coast): the station on the
     same river where one exists, else the mean of the two nearest (``REACHES``).
  3. DEEPEN ONLY: a pixel is painted only where the A+ template's merged bed
     (``dep_subgrid_merged.tif``, ROTATED: read through its inverse affine, self-checked
     against ``rasterio.sample``) is shallower than the new value.
  4. footprint: the NHD Area StreamRiver polygon (FType 460) the centreline runs through,
     capped at 300 m from it (``build_riverbeds_v4._channel``'s rule), and only between
     each branch's ``down`` and ``up`` points: from where the model's centreline bed is a
     real (sub-MLLW) bed again below the hole -- the ~0 m water surface that CUDEM holds
     just below the Mullica, Tuckahoe and Rancocas holes is painted too, else it stays a
     sill -- to the hole's upstream end (the Maurice: on to Millville, where CUDEM holds a
     ~0 m surface for 13 km). The hole's own extent marks the tidal water: the NJ DEM is
     hydro-flattened and falls through only where its water surface is below 0.001 m.
  NHD comes from the USGS staged HU4 0204 geodatabase (the NHD MapServer answered
  502 / timed out on 10-05); the centreline is the named river's NHD flowline.

🔴 SEPARATE files. Not part of ``riverbeds_v4.vrt`` (a tier of the frozen premier bed),
not ``build_riverbeds_v4.REACHES``. Output: data/elevation_v4/riverbeds/
riverbed_gmrt_<reach>_v4.tif (EPSG:32618, 5 m, NoData -9999, m NAVD88) +
riverbeds_gmrt_v4.vrt + riverbeds_gmrt_v4_profiles.csv; catalog key ``riverbeds_gmrt_v4``.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_riverbeds_v4 as rb  # noqa: E402
import download_nos_hydro_v4 as nos  # noqa: E402

#: bulk inputs (NHD geodatabase, ENC cells, NOS surveys): scratch, not home
SRC = Path("/scratch/tpj8/nj_bight_sfincs_data/elevation_v4/gmrt_reaches")
NHD_ZIP = (
    "https://prd-tnm.s3.amazonaws.com/StagedProducts/Hydrography/NHD/HU4/GDB/"
    "NHD_H_0204_HU4_GDB.zip"
)
NHD_GDB = SRC / "nhd_0204" / "NHD_H_0204_HU4_GDB.gdb"
ENC_URL = "https://charts.noaa.gov/ENCs/{cell}.zip"
ENC_CELLS = (
    "US4NJ1BB US4NJ1BC US4NJ1CB US4NJ1CC US4NJ1CD US5NJ1FD US5NJ1GD US5NJ1JG "
    "US5NJ1JH US5PHLDH"
).split()
ENC_ROOT = SRC / "enc" / "ENC_ROOT"
NOS_DIR = SRC / "nos"
MODEL_BED = (
    ROOT / "experiments/v4_hot_plus/_template_sealed/subgrid/dep_subgrid_merged.tif"
)
GMRT = ROOT / "data/elevation_v4/gmrt_v4.tif"

DEPTH_BELOW_MLLW_M = 1.2
NEAR_CHANNEL_M = 150.0  # soundings this close to the channel polygon count
WINDOW_M = 300.0  # running-median half window along the centreline
PAD_UP_M = 100.0  # paint this far past the upstream span point
GMRT_TOL_M = 0.1  # |model - GMRT| below this = "the bed is GMRT" (report only)


@dataclass(frozen=True)
class Branch:
    river: str  # NHD gnis_name of the flowline
    box: tuple[float, float, float, float]  # lon/lat clip for the flowline
    head: tuple[float, float]  # lon/lat near the UPSTREAM end (orients stations)
    down: tuple[float, float]  # paint from here (lon/lat, projected on the line) ...
    up: tuple[float, float]  # ... to here (+ PAD_UP_M)


@dataclass(frozen=True)
class GReach:
    name: str
    mllw_navd88_m: float
    mllw_note: str
    branches: tuple[Branch, ...]
    points: str  # "enc" | "nos"
    nos_surveys: tuple[tuple[str, str, int], ...] = ()  # (id, NCEI block, year)
    mlw_navd88_m: float | None = None  # nos: the survey plane, MLW - NAVD88
    why: str = ""


REACHES = (
    GReach(
        "maurice",
        -1.040,
        "CO-OPS 8535055 Bivalve, Maurice River (MLLW-NAVD88 -1.040; 8536931 "
        "Fortescue Creek -0.982 for comparison)",
        (
            Branch(
                "Maurice River",
                (-75.06, 39.20, -74.96, 39.41),
                (-75.04, 39.40),
                (-75.012, 39.247),
                (-75.048, 39.401),
            ),
        ),
        "enc",
        why="ENC SOUNDG (US4NJ1BB/BC/CB/CC, 1:90k) to lat 39.32 = the whole GMRT "
        "stretch; above it, to Millville, CUDEM holds a ~0 m water surface: 1.2 m "
        "below MLLW there.",
    ),
    GReach(
        "mullica",
        -0.522,
        "CO-OPS 8534212 Chestnut Neck Boat Yard, Mullica River (MLLW-NAVD88 -0.522); "
        "Atlantic City -0.797 is ocean-side and not used",
        (
            Branch(
                "Mullica River",
                (-74.70, 39.53, -74.44, 39.68),
                (-74.65, 39.64),
                (-74.471, 39.552),
                (-74.655, 39.631),
            ),
        ),
        "enc",
        why="ENC SOUNDG (US5NJ1JG/JH, 1:12k) stop at lon -74.498, the hole's "
        "downstream end; Lower Bank -> Batsto at 1.2 m below MLLW.",
    ),
    GReach(
        "tuckahoe",
        -0.684,
        "mean of CO-OPS 8534691 River Bend Marina, Great Egg Harbor R. (-0.645) and "
        "8535101 Middle Thorofare (-0.723); 8534883 Tuckahoe (no NAVD88) has "
        "MSL-MLLW 0.663 m, consistent",
        (
            Branch(
                "Tuckahoe River",
                (-74.86, 39.26, -74.66, 39.34),
                (-74.86, 39.32),
                (-74.706, 39.293),
                (-74.818, 39.306),
            ),
        ),
        "nos",
        nos_surveys=(
            ("H06254", "H06001-H08000", 1937),
            ("H06218", "H06001-H08000", 1937),
        ),
        mlw_navd88_m=-0.634,  # mean MLW-NAVD88 of the same two stations
        why="NOS H06254 + H06218 (1937 lead line, MLW, epoch-corrected) reach lon "
        "-74.758 (the chart, US5NJ1FD/GD, has no soundings here); 1.2 m below MLLW "
        "above.",
    ),
    GReach(
        "rancocas",
        -0.896,
        "mean of CO-OPS 8539058 Assiscunk Creek (-0.903) and 8538875 Pompeston Creek "
        "(-0.888)",
        (
            Branch(
                "Rancocas Creek",
                (-74.99, 39.97, -74.80, 40.06),
                (-74.861, 39.9965),
                (-74.977, 40.042),
                (-74.861, 39.9965),
            ),
            Branch(
                "North Branch Rancocas Creek",
                (-74.99, 39.97, -74.76, 40.06),
                (-74.76, 39.987),
                (-74.861, 39.9965),
                (-74.818, 39.998),
            ),
            Branch(
                "South Branch Rancocas Creek",
                (-74.99, 39.94, -74.76, 40.06),
                (-74.78, 39.94),
                (-74.861, 39.9965),
                (-74.802, 39.959),
            ),
        ),
        "enc",
        why="ENC SOUNDG (US5PHLDH, 1:12k) on the main stem to the fork (lon -74.857); "
        "both branches at 1.2 m below MLLW.",
    ),
)


# ── fetch ─────────────────────────────────────────────────────────────────────
def fetch() -> None:
    SRC.mkdir(parents=True, exist_ok=True)
    z = SRC / "NHD_H_0204_HU4_GDB.zip"
    if not NHD_GDB.exists():
        if not z.exists():
            rb._atomic_bytes(z, rb._get(NHD_ZIP))
        with zipfile.ZipFile(z) as f:
            f.extractall(SRC / "nhd_0204")
    (SRC / "enc").mkdir(exist_ok=True)
    for cell in ENC_CELLS:
        if not (ENC_ROOT / cell).exists():
            zz = SRC / "enc" / f"{cell}.zip"
            if not zz.exists():
                rb._atomic_bytes(zz, rb._get(ENC_URL.format(cell=cell)))
            with zipfile.ZipFile(zz) as f:
                f.extractall(SRC / "enc")
    for r in REACHES:
        for sid, blk, _ in r.nos_surveys:
            gz = NOS_DIR / f"{sid}.a93.gz"
            if not gz.exists():
                rb._atomic_bytes(gz, rb._get(nos.A93.format(blk=blk, sid=sid)))
    print(f"inputs cached under {SRC}")


# ── geometry ──────────────────────────────────────────────────────────────────
def _nhd(r: GReach):
    """(StreamRiver polygons, named flowlines) in UTM for the reach, cached as GeoJSON."""
    import geopandas as gpd
    import pyogrio

    box = (
        min(b.box[0] for b in r.branches),
        min(b.box[1] for b in r.branches),
        max(b.box[2] for b in r.branches),
        max(b.box[3] for b in r.branches),
    )
    fa, ff = SRC / f"nhd_area_{r.name}.geojson", SRC / f"nhd_flowline_{r.name}.geojson"
    if not (fa.exists() and ff.exists()):
        a = pyogrio.read_dataframe(NHD_GDB, layer="NHDArea", bbox=box)
        a = a[a.ftype == 460][["gnis_name", "ftype", "geometry"]]
        f = pyogrio.read_dataframe(
            NHD_GDB, layer="NHDFlowline", bbox=box, columns=["gnis_name", "ftype"]
        )
        f = f[f.gnis_name.isin({b.river for b in r.branches})]
        f = f.set_geometry(f.geometry.force_2d())
        for g, p in ((a, fa), (f, ff)):
            rb._atomic_bytes(p, g.to_crs(4326).to_json().encode())
    return gpd.read_file(fa).to_crs(rb.EPSG), gpd.read_file(ff).to_crs(rb.EPSG)


def _line(b: Branch, flow):
    """The branch's flowline in its box, merged, longest piece; station 0 downstream."""
    import geopandas as gpd
    import shapely
    from shapely.ops import linemerge

    box = gpd.GeoSeries([shapely.box(*b.box)], crs=4326).to_crs(rb.EPSG).iloc[0]
    g = flow[flow.gnis_name == b.river].clip(box)
    merged = linemerge(shapely.union_all(g.geometry.values))
    line = max(getattr(merged, "geoms", [merged]), key=lambda p: p.length)
    head = _utm(*b.head)
    if head.distance(shapely.Point(line.coords[0])) < head.distance(
        shapely.Point(line.coords[-1])
    ):
        line = shapely.reverse(line)
    return line


def _utm(lon: float, lat: float):
    import geopandas as gpd
    import shapely

    return gpd.GeoSeries([shapely.Point(lon, lat)], crs=4326).to_crs(rb.EPSG).iloc[0]


def _channel(area, line):
    """NHD StreamRiver polygons the centreline runs through, <= 300 m from it."""
    import shapely

    g = area[area.intersects(line.buffer(10.0))]
    return shapely.union_all(g.geometry.values).intersection(
        line.buffer(rb.MAX_HALFWIDTH_M)
    )


# ── soundings ─────────────────────────────────────────────────────────────────
def _soundings(r: GReach):
    """lon, lat, bed (m NAVD88), label: every sounding of the reach's source."""
    if r.points == "enc":
        lon, lat, dep = _enc_points(_reach_box(r))
        return lon, lat, r.mllw_navd88_m - dep, "ENC SOUNDG below MLLW"
    lon, lat, z = [], [], []
    for sid, _, year in r.nos_surveys:
        d = nos.read_a93(NOS_DIR / f"{sid}.a93.gz")  # (lat, lon, depth below MLW)
        epoch = -nos.SLR_M_PER_YR * (nos.EPOCH_MID - year)
        lat.append(d[:, 0])
        lon.append(d[:, 1])
        z.append(r.mlw_navd88_m + epoch - d[:, 2])
    ids = "+".join(s for s, _, _ in r.nos_surveys)
    return (
        np.concatenate(lon),
        np.concatenate(lat),
        np.concatenate(z),
        f"NOS {ids} below MLW (MLW-NAVD88 {r.mlw_navd88_m:+.3f}, epoch-corrected)",
    )


def _reach_box(r: GReach):
    return (
        min(b.box[0] for b in r.branches),
        min(b.box[1] for b in r.branches),
        max(b.box[2] for b in r.branches),
        max(b.box[3] for b in r.branches),
    )


def _enc_points(box):
    """ENC SOUNDG inside ``box`` from ``ENC_ROOT``: lon, lat, depth below MLLW (m)."""
    import warnings

    import geopandas as gpd
    import pyogrio
    import shapely

    warnings.filterwarnings("ignore")
    os.environ["OGR_S57_OPTIONS"] = "SPLIT_MULTIPOINT=ON,ADD_SOUNDG_DEPTH=ON"
    seen, out = set(), []
    for f in sorted(ENC_ROOT.glob("*/*.000")):
        if "SOUNDG" not in {n for n, _ in pyogrio.list_layers(f)}:
            continue
        g = gpd.read_file(f, layer="SOUNDG", engine="pyogrio")
        for p in g.geometry[g.geometry.within(shapely.box(*box))]:
            k = (round(p.x, 6), round(p.y, 6), p.z)
            if k not in seen:
                seen.add(k)
                out.append(k)
    a = np.array(out, dtype="float64").reshape(-1, 3)
    return a[:, 0], a[:, 1], a[:, 2]


def profile(r: GReach, line, chan, snd):
    """Bed (m NAVD88) and its source at 25 m stations along one branch."""
    import geopandas as gpd
    import shapely

    lon, lat, z, label = snd
    grid = np.arange(0.0, line.length + 25.0, 25.0)
    p = np.asarray(gpd.points_from_xy(lon, lat, crs=4326).to_crs(rb.EPSG))
    near = shapely.dwithin(chan, p, NEAR_CHANNEL_M)
    s = shapely.line_locate_point(line, p[near])
    prof = (
        rb._running_median(s, z[near], grid, WINDOW_M) if near.any() else grid * np.nan
    )
    ok = np.isfinite(prof)
    if ok.sum() >= 2:  # interior gaps between soundings: linear along the line
        inside = (grid >= grid[ok][0]) & (grid <= grid[ok][-1])
        prof[inside] = np.interp(grid[inside], grid[ok], prof[ok])
    src = np.where(np.isfinite(prof), "soundings", "stated")
    prof[~np.isfinite(prof)] = r.mllw_navd88_m - DEPTH_BELOW_MLLW_M
    note = f"{int(near.sum())} soundings ({label})" + (
        f", stations {s.min():.0f}..{s.max():.0f} m" if near.any() else ""
    )
    return grid, prof, src, note


# ── model bed (ROTATED raster) ────────────────────────────────────────────────
def sample_model_bed(x: np.ndarray, y: np.ndarray, path: Path = MODEL_BED):
    """Nearest pixel of the rotated merged bed at UTM (x, y), via the inverse affine and
    one plain (non-boundless) window. NaN off the raster / on NoData."""
    import rasterio
    from rasterio.windows import Window

    out = np.full(x.shape, np.nan)
    with rasterio.open(path) as s:
        inv = ~s.transform
        col = np.floor(inv.a * x + inv.b * y + inv.c).astype(np.int64)
        row = np.floor(inv.d * x + inv.e * y + inv.f).astype(np.int64)
        ok = (row >= 0) & (row < s.height) & (col >= 0) & (col < s.width)
        if not ok.any():
            return out
        r0, r1 = row[ok].min(), row[ok].max() + 1
        c0, c1 = col[ok].min(), col[ok].max() + 1
        a = s.read(1, window=Window(c0, r0, c1 - c0, r1 - r0)).astype("float64")
        if s.nodata is not None and np.isfinite(s.nodata):
            a[a == s.nodata] = np.nan
        out[ok] = a[row[ok] - r0, col[ok] - c0]
    return out


def _self_check(x, y, n=2000, seed=0) -> None:
    """The window sampler must equal ``rasterio.sample`` exactly (CLAUDE.md §5)."""
    import rasterio

    i = np.random.default_rng(seed).choice(len(x), min(n, len(x)), replace=False)
    a = sample_model_bed(x[i], y[i])
    with rasterio.open(MODEL_BED) as s:
        b = np.array([v[0] for v in s.sample(zip(x[i], y[i]))], dtype="float64")
        if s.nodata is not None and np.isfinite(s.nodata):
            b[b == s.nodata] = np.nan
    same = (a == b) | (np.isnan(a) & np.isnan(b))
    if not same.all():
        raise SystemExit(
            f"model-bed sampler disagrees with rasterio.sample: {(~same).sum()}"
        )


def sample_gmrt(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """GMRT bilinear at UTM (x, y) (hydromt merges it bilinearly)."""
    import rasterio
    from rasterio.warp import transform as warp_xy
    from scipy.ndimage import map_coordinates

    with rasterio.open(GMRT) as s:
        g = s.read(1).astype("float64")
        xx, yy = warp_xy(f"EPSG:{rb.EPSG}", s.crs, x.tolist(), y.tolist())
        inv = ~s.transform
        c = inv.a * np.asarray(xx) + inv.b * np.asarray(yy) + inv.c - 0.5
        r = inv.d * np.asarray(xx) + inv.e * np.asarray(yy) + inv.f - 0.5
    return map_coordinates(g, [r, c], order=1, mode="nearest")


# ── build ─────────────────────────────────────────────────────────────────────
def build_reach(r: GReach):
    """Paint one reach (all branches) → its tif; returns (path, profile rows, stats)."""
    import rasterio
    import shapely
    from rasterio.features import geometry_mask
    from rasterio.transform import from_origin

    area, flow = _nhd(r)
    snd = _soundings(r)
    parts, rows = [], []
    for b in r.branches:
        line = _line(b, flow)
        chan = _channel(area, line)
        grid, prof, src, note = profile(r, line, chan, snd)
        s_dn = line.project(_utm(*b.down))
        s_up = min(line.project(_utm(*b.up)) + PAD_UP_M, line.length)
        lo, hi = min(s_dn, s_up), max(s_dn, s_up)
        print(
            f"{r.name} / {b.river}: centreline {line.length / 1000:.1f} km, channel "
            f"{chan.area / 1e6:.2f} km²; {note}; painted span {lo:.0f}..{hi:.0f} m"
        )
        rows += [
            f"{r.name},{b.river},{s:.0f},{z:.3f},{c},{int(lo <= s <= hi)}"
            for s, z, c in zip(grid, prof, src)
        ]
        parts.append((line, chan, grid, prof, lo, hi))

    bounds = np.array([p[1].bounds for p in parts])
    x0 = np.floor(bounds[:, 0].min() / rb.RES) * rb.RES
    y1 = np.ceil(bounds[:, 3].max() / rb.RES) * rb.RES
    w = int(np.ceil((bounds[:, 2].max() - x0) / rb.RES))
    h = int(np.ceil((y1 - bounds[:, 1].min()) / rb.RES))
    T = from_origin(x0, y1, rb.RES, rb.RES)
    z = np.full((h, w), np.nan)
    for line, chan, grid, prof, lo, hi in parts:
        rr, cc = np.nonzero(~geometry_mask([chan], (h, w), T))
        px, py = x0 + (cc + 0.5) * rb.RES, y1 - (rr + 0.5) * rb.RES
        st = shapely.line_locate_point(line, shapely.points(px, py))
        on = (st >= lo) & (st <= hi)
        v = np.interp(st[on], grid, prof)
        z[rr[on], cc[on]] = np.fmin(z[rr[on], cc[on]], v)  # deepest where branches meet

    # deepen only, against the A+ template's merged bed (rotated: inverse affine)
    rr, cc = np.nonzero(np.isfinite(z))
    px, py = x0 + (cc + 0.5) * rb.RES, y1 - (rr + 0.5) * rb.RES
    _self_check(px, py)
    old = sample_model_bed(px, py)
    new = z[rr, cc]
    keep = ~(np.isfinite(old) & (old <= new))
    z[rr[~keep], cc[~keep]] = np.nan
    on_gmrt = np.abs(old - sample_gmrt(px, py)) < GMRT_TOL_M

    a = np.where(np.isfinite(z), z, rb.NODATA).astype("float32")
    out = rb.RB / f"riverbed_gmrt_{r.name}_v4.tif"
    fd, tmp = tempfile.mkstemp(dir=rb.RB, prefix=f".{out.name}.", suffix=".tif")
    os.close(fd)
    with rasterio.open(
        tmp,
        "w",
        driver="GTiff",
        height=h,
        width=w,
        count=1,
        dtype="float32",
        crs=f"EPSG:{rb.EPSG}",
        transform=T,
        nodata=rb.NODATA,
        compress="deflate",
        tiled=True,
    ) as d:
        d.write(a, 1)
        d.update_tags(reach=r.name, why=r.why, mllw_navd88=r.mllw_navd88_m)
    os.replace(tmp, out)
    px2 = rb.RES**2 / 1e6
    st = {
        "candidates_km2": keep.size * px2,
        "painted_km2": keep.sum() * px2,
        "painted_on_gmrt_km2": (keep & on_gmrt).sum() * px2,
        "old_p50": float(np.nanmedian(old[keep])),
        "new_p50": float(np.median(new[keep])),
        "new_p5": float(np.percentile(new[keep], 5)),
        "new_p95": float(np.percentile(new[keep], 95)),
        "lift_p50": float(np.nanmedian(new[keep] - old[keep])),
        "kept_old_km2": (~keep).sum() * px2,
    }
    print(
        f"  -> {out.name}: painted {st['painted_km2']:.2f} of {st['candidates_km2']:.2f}"
        f" km² ({st['painted_on_gmrt_km2']:.2f} on GMRT); old bed p50 "
        f"{st['old_p50']:+.2f} -> new p50 {st['new_p50']:+.2f} m "
        f"(p5..p95 {st['new_p5']:+.2f}..{st['new_p95']:+.2f})"
    )
    return out, rows, st


def build() -> None:
    outs, rows = [], ["reach,branch,station_m,bed_navd88_m,source,painted_span"]
    for r in REACHES:
        out, rr, _ = build_reach(r)
        outs.append(out)
        rows += rr
    rb._atomic_bytes(
        rb.RB / "riverbeds_gmrt_v4_profiles.csv", ("\n".join(rows) + "\n").encode()
    )
    vrt = rb.RB / "riverbeds_gmrt_v4.vrt"
    subprocess.run(
        [
            "gdalbuildvrt",
            "-overwrite",
            "-srcnodata",
            str(rb.NODATA),
            "-vrtnodata",
            str(rb.NODATA),
            str(vrt),
            *map(str, outs),
        ],
        check=True,
    )
    print(f"wrote {vrt}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("stage", choices=["fetch", "build"])
    a = ap.parse_args()
    fetch() if a.stage == "fetch" else build()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
