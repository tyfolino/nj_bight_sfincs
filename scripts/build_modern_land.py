#!/usr/bin/env python
"""Build the MODERN land + beach overlay for a 2026 bed (user 2026-10-28/30).

One north-up 3 m raster, ``elevation_modern_2026/modern_land_2026.tif``, painted FIRST with
``rebuild_subgrid.py --overlay`` so the premier's merge, its channels and all its bed fixes
stay as they are (they paint after it). Newest survey wins, 2015 on; the 2013-14 sets are
already in CUDEM (logs/modern_bed_2026-10-28/cudem_survey_dates.md).

🔴 **Land lidar draws water as a flat surface.** Painted over a bay or a river it would erase the
bathymetry, so a survey pixel only counts where the current bed says it may (``accept``):
    land lidar   current bed >= ``LAND_MIN`` (not water today);
    topobathy    the same, or below it if within ``WATER_DELTA`` of the current bed or at
                 least ``NEW_GROUND`` high (a nourished beach). A topobathy product can also pave
                 deep water with an interpolated surface (usace_nj_2010, FINDINGS §54);
                 that reads low and far from the bed, and is refused.

The current bed is the premier's recipe without the building burn. 🔴 It is ROTATED; reading
goes through its affine via ``reproject``, never ``x0 + col*res`` (CLAUDE.md §5).

    python scripts/build_modern_land.py --workers 16

Writes the raster, ``modern_land_2026_source.tif`` (uint8, ``SOURCES`` index + 1) and, beside
``--report``, a per-source table + overview figure. Check the medians before building a bed:
a unit or datum slip shows up there.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject, transform_bounds
from rasterio.windows import Window

RAW = Path("/scratch/tpj8/nj_bight_sfincs_data/modern_2026/raw")
OUT = Path("/scratch/tpj8/nj_bight_sfincs_data/elevation_modern_2026")
REPO = Path(__file__).resolve().parents[1]
BED = (
    REPO / "experiments/v4_refreeze/_subgrid_refreeze_lakes_min_nobuildings_creeks_cohansey"
    "/subgrid/dep_subgrid_merged.tif"
)
CRS = "EPSG:32618"
RES, BLOCK, DECIMATE = 3.0, 6000, 20
LAND_MIN, WATER_DELTA, NEW_GROUND = -0.25, 2.0, 1.0
FT = 1200.0 / 3937.0  # US survey foot → m
NODATA = -9999.0


def _usgs(project: str) -> str:
    return str(RAW / f"usgs_3dep_1m/USGS_*_{project}*.tif")


#: Newest first: name, year, glob, z factor, topobathy?
SOURCES = [
    ("usgs_nj_ne6county", 2024, _usgs("NJ_NE6County_B23"), 1.0, False),
    ("pa_17county", 2024, str(RAW / "pa_17county_2024_5/*.tif"), 1.0, False),
    ("usgs_de_statewide", 2023, _usgs("DE_Statewide_B23"), 1.0, False),
    ("philadelphia", 2022, str(RAW / "philadelphia_2022/*.tif"), FT, False),
    ("usace_ncmp_2022", 2022, str(RAW / "usace_ncmp_2022/*.tif"), 1.0, True),
    ("usgs_ny_se4county", 2022, _usgs("NY_SouthEast4County_A22"), 1.0, False),
    ("usace_capemay_ac_2020", 2020, str(RAW / "usace_capemay_ac_2020/*.tif"), 1.0, True),
    ("usace_nan_2020", 2020, str(RAW / "usace_nan_2020/*.tif"), 1.0, True),
    ("usgs_south_nj_fema", 2019, _usgs("NJ_South_Jersey_Lidar_2018_B18_FEMA"), 1.0, False),
    ("usgs_south_nj", 2019, _usgs("NJ_South_Jersey_Lidar_2018_B18"), 1.0, False),
    ("usace_ncmp_2017", 2017, str(RAW / "usace_ncmp_2017/*.tif"), 1.0, True),
    ("nyc_2017", 2017, str(RAW / "nyc_topobathy_2017/*.tif"), FT, True),
    ("usgs_nw_nj", 2017, _usgs("NJ_NW_New_Jersey_6_County_Lidar_2017_B17"), 1.0, False),
    ("usgs_dvrpc_2015", 2015, _usgs("DE_Delaware*"), 1.0, False),
]
HIST_EDGES = np.arange(-5.0, 5.01, 0.05)


def build_vrts(vrt_dir: Path) -> list[dict]:
    """One VRT per source, with its footprint in the output CRS."""
    vrt_dir.mkdir(parents=True, exist_ok=True)
    out = []
    for name, year, pattern, factor, topobathy in SOURCES:
        files = sorted(glob.glob(pattern))
        if name == "usgs_south_nj":  # the glob also catches the _FEMA project
            files = [f for f in files if "_FEMA" not in f]
        if not files:
            raise SystemExit(f"no files for {name}: {pattern}")
        vrt = vrt_dir / f"{name}.vrt"
        lst = vrt_dir / f"{name}.txt"
        lst.write_text("\n".join(files) + "\n")
        subprocess.run(
            ["gdalbuildvrt", "-q", "-overwrite", "-vrtnodata", str(NODATA),
             "-input_file_list", str(lst), str(vrt)],
            check=True,
        )  # fmt: skip
        with rasterio.open(vrt) as ds:
            bounds = transform_bounds(ds.crs, CRS, *ds.bounds)
        out.append(
            dict(name=name, year=year, n=len(files), vrt=str(vrt), factor=factor,
                 topobathy=topobathy, bounds=bounds)
        )  # fmt: skip
        print(f"  {name}: {len(files)} tiles, bounds {np.round(bounds)}", flush=True)
    return out


def accept(new: np.ndarray, old: np.ndarray, topobathy: bool) -> np.ndarray:
    """May this survey's pixel replace the current bed? (module docstring). NaN ``old`` = yes."""
    with np.errstate(invalid="ignore"):
        land = ~(old < LAND_MIN)
        if not topobathy:
            return np.isfinite(new) & land
        return np.isfinite(new) & (
            land | (np.abs(new - old) <= WATER_DELTA) | (new >= NEW_GROUND)
        )


def _read(path, shape, transform, resampling, factor=1.0):
    arr = np.full(shape, np.nan, "float32")
    with rasterio.open(path) as src:
        reproject(
            rasterio.band(src, 1), arr, dst_transform=transform, dst_crs=CRS,
            dst_nodata=np.nan, resampling=resampling,
        )  # fmt: skip
    return arr * factor


def do_block(job):
    """Fill one block, newest source first. Returns the arrays and per-source tallies."""
    r0, c0, h, w, t0, sources = job
    tr = rasterio.Affine(t0.a, 0, t0.c + c0 * t0.a, 0, t0.e, t0.f + r0 * t0.e)
    x0, y1 = tr.c, tr.f
    x1, y0 = x0 + w * RES, y1 - h * RES
    near = [
        (i, s) for i, s in enumerate(sources)
        if s["bounds"][0] < x1 and s["bounds"][2] > x0
        and s["bounds"][1] < y1 and s["bounds"][3] > y0
    ]  # fmt: skip
    tally = {}
    if not near:
        return r0, c0, None, None, tally
    old = _read(BED, (h, w), tr, Resampling.nearest)
    z = np.full((h, w), np.nan, "float32")
    who = np.zeros((h, w), "uint8")
    for i, s in near:
        new = _read(s["vrt"], (h, w), tr, Resampling.bilinear, s["factor"])
        finite = np.isfinite(new)
        if not finite.any():
            continue
        ok = accept(new, old, s["topobathy"])
        take = ok & np.isnan(z)
        z[take] = new[take]
        who[take] = i + 1
        d = (new - old)[take & np.isfinite(old) & (old >= 0.5)]  # stable: land today
        tally[i] = dict(
            valid=int(finite.sum()),
            refused=int((finite & ~ok).sum()),
            taken=int(take.sum()),
            hist=np.histogram(d, HIST_EDGES)[0],
            beyond=int((np.abs(d) > 5).sum()),
        )
    if not (who > 0).any():
        return r0, c0, None, None, tally
    return r0, c0, z, who, tally


def _hist_pct(hist, q):
    c = np.cumsum(hist)
    return float(HIST_EDGES[np.searchsorted(c, q * c[-1]) + 1]) if c[-1] else float("nan")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--report", type=Path, required=True, help="dir for the table + figure")
    a = ap.parse_args()
    a.report.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    sources = build_vrts(OUT / "vrt")
    with rasterio.open(BED) as b:
        # rotated (CLAUDE.md §5): the bounding box of its four corners
        xs, ys = zip(*(b.transform * p for p in
                       ((0, 0), (b.width, 0), (0, b.height), (b.width, b.height))))  # fmt: skip
        bb = (min(xs), min(ys), max(xs), max(ys))
    x0, y1 = np.floor(bb[0] / RES) * RES, np.ceil(bb[3] / RES) * RES
    W = int(np.ceil((bb[2] - x0) / RES))
    H = int(np.ceil((y1 - bb[1]) / RES))
    T = from_origin(x0, y1, RES, RES)
    print(f"raster {W} x {H} px, {T}", flush=True)
    jobs = [
        (r, c, min(BLOCK, H - r), min(BLOCK, W - c), T, sources)
        for r in range(0, H, BLOCK)
        for c in range(0, W, BLOCK)
    ]
    prof = dict(
        driver="GTiff", width=W, height=H, count=1, crs=CRS, transform=T, tiled=True,
        blockxsize=512, blockysize=512, compress="DEFLATE", BIGTIFF="YES",
    )  # fmt: skip
    tif, stif = OUT / "modern_land_2026.tif", OUT / "modern_land_2026_source.tif"
    tmp, stmp = tif.with_suffix(".partial.tif"), stif.with_suffix(".partial.tif")
    totals = {
        i: dict(valid=0, refused=0, taken=0, beyond=0, hist=np.zeros(len(HIST_EDGES) - 1, "int64"))
        for i in range(len(sources))
    }
    small = np.zeros((H // DECIMATE + 1, W // DECIMATE + 1), "uint8")
    with (
        rasterio.open(tmp, "w", dtype="float32", nodata=NODATA, predictor=3, **prof) as dz,
        rasterio.open(stmp, "w", dtype="uint8", nodata=0, **prof) as ds,
        ProcessPoolExecutor(a.workers) as pool,
    ):
        for k, (r0, c0, z, who, tally) in enumerate(pool.map(do_block, jobs), 1):
            for i, t in tally.items():
                for key in ("valid", "refused", "taken", "beyond", "hist"):
                    totals[i][key] += t[key]
            if z is not None:
                win = Window(c0, r0, z.shape[1], z.shape[0])
                dz.write(np.nan_to_num(z, nan=NODATA), 1, window=win)
                ds.write(who, 1, window=win)
                sm = who[:: DECIMATE, :: DECIMATE]
                rr, cc = r0 // DECIMATE, c0 // DECIMATE
                small[rr : rr + sm.shape[0], cc : cc + sm.shape[1]] = sm[
                    : small.shape[0] - rr, : small.shape[1] - cc
                ]
            print(f"  block {k}/{len(jobs)}", flush=True)
    os.replace(tmp, tif)
    os.replace(stmp, stif)

    px = RES**2 / 1e6
    rows = []
    print(f"\n{'source':24s} {'year':>4s} {'taken km2':>10s} {'refused km2':>12s}"
          f" {'median':>7s} {'p5':>6s} {'p95':>6s}  (new − current bed, on land >= 0.5 m)")  # fmt: skip
    for i, s in enumerate(sources):
        t = totals[i]
        row = dict(
            name=s["name"], year=s["year"], tiles=s["n"], topobathy=s["topobathy"],
            taken_km2=t["taken"] * px, refused_km2=t["refused"] * px,
            median=_hist_pct(t["hist"], 0.5), p5=_hist_pct(t["hist"], 0.05),
            p95=_hist_pct(t["hist"], 0.95), beyond_5m=t["beyond"],
        )  # fmt: skip
        rows.append(row)
        print(f"{row['name']:24s} {row['year']:4d} {row['taken_km2']:10.1f} "
              f"{row['refused_km2']:12.1f} {row['median']:7.2f} {row['p5']:6.2f} {row['p95']:6.2f}")  # fmt: skip
    (a.report / "modern_land_sources.json").write_text(json.dumps(rows, indent=1))

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 11))
    m = np.ma.masked_equal(small, 0)
    im = ax.imshow(m, cmap="tab20", vmin=0.5, vmax=len(sources) + 0.5, interpolation="nearest")
    cb = fig.colorbar(im, ax=ax, ticks=range(1, len(sources) + 1), shrink=0.7)
    cb.ax.set_yticklabels([f"{s['name']} ({s['year']})" for s in sources], fontsize=7)
    ax.set_title("Which survey sets the modern land overlay")
    ax.set_xticks([])
    ax.set_yticks([])
    fig.savefig(a.report / "modern_land_sources.png", dpi=150, bbox_inches="tight")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
