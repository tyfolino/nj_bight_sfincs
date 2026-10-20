#!/usr/bin/env python
"""Lower tidal-creek beds that CUDEM holds at the WATER SURFACE → an overlay tier (`:min`).

    python scripts/build_creek_bed_nj10ft_v4.py

WHY (2026-10-20). On the NJ Delaware Bay shore CUDEM 1/9″ holds narrow tidal creeks at the
water surface the lidar saw, not at the bed: upstream of ~4.5 km below USGS 01411435 (Sluice
Creek at South Dennis) the Dennis Creek bed rises smoothly −0.9 → +0.1 m and sits at
+0.5…+0.6 m under the gauge, so the gauge face reaches the sea only above +0.68 m (MHHW
+0.88) and the model has no tide there (observed range 1.06 m;
logs/sluice_creek_2026-10-20/). FINDINGS §54 is the same failure class elsewhere.

WHAT IS MEASURED AND WHAT IS ASSUMED. Measured: the NJ 10 ft DEM marks these creeks as
WATER (hydro-flattened), and CUDEM's smooth +0.1…+0.6 m creek "bed" is its water surface (a
creek carrying a 1.06 m tide with low water near −0.2 m cannot have a +0.6 m bed). ASSUMED:
the value painted. The NJ DEM flattens tidal water to a FILL CONSTANT, almost everywhere
−1.067 m = −3.5 ft NAVD88 (the USACE mean-low-water plane, ``download_ehydro_nj.py``), plus
local pool constants (−0.24 m at the Sluice gauge, origin unconfirmed). −1.067 is the same
number on ~119,000 water pixels around Sluice alone — a convention, NOT a survey of any
creek. Painting it with ``--overlay creek_bed_nj10ft_v4:min`` (lower-only) sets an ASSUMED
bed at about mean low water wherever the bed sits above it: plausible for a creek that is
wet at low tide, but a tide match it produces partly reflects the assumption.

THE RULE, inside each declared box only: an NJ 10 ft pixel is painted with its own value
when it is hydro-flat (identical to all 8 neighbours) AND within ``CORRIDOR_M`` of a flowline
of one of the box's NHD creek names, and NOT inside an NHD lake / pond polygon. NoData
elsewhere. The flat test confines the paint to
mapped water; the corridor confines it to the named creek; the lake exclusion keeps a DAMMED
pond on the creek out (Clint Millpond on Sluice Creek is flat at its +0.859 m pool — a held-up
non-tidal level, not a tide plane).

WHICH CREEKS. ``CREEKS`` below; each entry says why. Sluice / Dennis first, then the NJ
Delaware Bay shore sweep's qualifying creeks (55 found, ~123 km; Salem River + Mannington
Creek left out pending a gate check; logs/de_bay_creeks_2026-10-20/). Real structures (tide gates, dikes,
culverted road crossings) are NOT carved: a box is drawn short of them.

Output: data/elevation_v4/creek_bed_nj10ft/creek_bed_nj10ft_<site>_v4.tif (EPSG:4326, the NJ
10 ft lattice, NoData −9999, m NAVD88) + creek_bed_nj10ft_v4.vrt.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "elevation_v4" / "creek_bed_nj10ft"
SCRATCH = Path("/scratch/tpj8/nj_bight_sfincs_data/elevation_v4/creek_bed_nj10ft")
NJ10 = ROOT / "data" / "elevation_v4" / "nj_10ft_dem_v4.tif"
NHD = Path(
    "/scratch/tpj8/nj_bight_sfincs_data/elevation_v4/gmrt_reaches/nhd_0204/"
    "NHD_H_0204_HU4_GDB.gdb"
)
LAKES = ROOT / "data" / "elevation_v4" / "inland_water" / "nhd_lake_v4.gpkg"
NODATA = -9999.0
CORRIDOR_M = 40.0

#: site → ((lon_min, lat_min, lon_max, lat_max), NHD gnis names, why)
CREEKS: dict[str, tuple[tuple[float, float, float, float], tuple[str, ...], str]] = {
    "sluice_dennis": (
        (-74.8700, 39.1300, -74.8000, 39.1900),
        ("Sluice Creek", "Dennis Creek"),
        "USGS 01411435 Sluice Creek at South Dennis: CUDEM +0.5…+0.6 under the gauge, "
        "upper Dennis Creek −0.9 → +0.1; NJ 10 ft flat −1.067 (MLW) along both, −0.24 at "
        "the gauge pool. Lower Dennis (−3…−5 m) is below the paint, so :min leaves it.",
    ),
    # ── the NJ Delaware Bay shore sweep (2026-10-20, logs/de_bay_creeks_2026-10-20/
    # candidates.csv, every "yes" row; user 10-20: all qualifying EXCEPT the Salem River and
    # Mannington Creek, whose NJ 10 ft water steps (−0.822 / −0.411 / −0.111) may mark gates).
    # B = the lowest sea level reaching the reach (now -> estimated after).
    "hope_creek": (
        (-75.506, 39.4513, -75.4853, 39.4959),
        ("Hope Creek",),
        "DE Bay sweep 10-20: 7730 m, B +0.04 -> -1.07 (est.); OSM: bridge:unclassified Alloway Creek Neck Road",
    ),
    "oranoaken_creek": (
        (-75.1484, 39.2315, -75.1379, 39.276),
        ("Oranoaken Creek",),
        "DE Bay sweep 10-20: 7270 m, B +0.21 -> -1.07 (est.)",
    ),
    "mad_horse_creek": (
        (-75.4534, 39.4172, -75.4449, 39.4626),
        ("Mad Horse Creek",),
        "DE Bay sweep 10-20: 5620 m, B +0.13 -> -1.07 (est.)",
    ),
    "little_creek": (
        (-75.4469, 39.4341, -75.4255, 39.4635),
        ("Little Creek",),
        "DE Bay sweep 10-20: 5300 m, B +0.09 -> -1.07 (est.)",
    ),
    "cedar_creek": (
        (-75.2467, 39.3082, -75.2209, 39.321),
        ("Cedar Creek",),
        "DE Bay sweep 10-20: 4010 m, B +0.25 -> -1.07 (est.)",
    ),
    "stow_creek": (
        (-75.419, 39.4247, -75.4075, 39.4458),
        ("Stow Creek",),
        "DE Bay sweep 10-20: 3500 m, B +0.02 -> -1.07 (est.)",
    ),
    "eastern_cross": (
        (-75.2803, 39.3202, -75.2643, 39.3294),
        ("Eastern Cross",),
        "DE Bay sweep 10-20: 3460 m, B +0.04 -> -1.07 (est.)",
    ),
    "abbot_creek": (
        (-75.2853, 39.3382, -75.274, 39.356),
        ("Abbot Creek",),
        "DE Bay sweep 10-20: 3360 m, B +0.06 -> -1.07 (est.)",
    ),
    "crow_creek": (
        (-74.8653, 39.1575, -74.8425, 39.1745),
        ("Crow Creek",),
        "DE Bay sweep 10-20: 3330 m, B -0.00 -> -0.64 (est.)",
    ),
    "fishing_creek_7549": (
        (-75.4851, 39.4419, -75.4748, 39.4607),
        ("Fishing Creek",),
        "DE Bay sweep 10-20: 3030 m, B +0.05 -> -1.07 (est.)",
    ),
    "malapartis_creek": (
        (-75.4433, 39.4204, -75.4256, 39.4354),
        ("Malapartis Creek",),
        "DE Bay sweep 10-20: 2980 m, B +0.07 -> -1.07 (est.)",
    ),
    "bridges_sticks_creek": (
        (-75.2752, 39.3382, -75.2665, 39.3594),
        ("Bridges Sticks Creek",),
        "DE Bay sweep 10-20: 2880 m, B +0.05 -> -1.07 (est.)",
    ),
    "riggin_ditch": (
        (-74.9827, 39.2015, -74.9704, 39.222),
        ("Riggin Ditch",),
        "DE Bay sweep 10-20: 2760 m, B +0.28 -> -1.07 (est.)",
    ),
    "east_creek": (
        (-74.9006, 39.1737, -74.892, 39.1929),
        ("East Creek",),
        "DE Bay sweep 10-20: 2730 m, B -0.27 -> -1.02 (est.)",
    ),
    "roaring_ditch": (
        (-74.8932, 39.1725, -74.8776, 39.1919),
        ("Roaring Ditch",),
        "DE Bay sweep 10-20: 2640 m, B -0.14 -> -1.02 (est.)",
    ),
    "ogdens_creek": (
        (-75.1228, 39.2354, -75.1078, 39.2487),
        ("Ogdens Creek",),
        "DE Bay sweep 10-20: 2590 m, B +0.21 -> -1.07 (est.)",
    ),
    "new_england_creek": (
        (-75.0519, 39.2201, -75.0436, 39.2384),
        ("New England Creek",),
        "DE Bay sweep 10-20: 2490 m, B +0.10 -> -1.04 (est.)",
    ),
    "back_creek": (
        (-75.2806, 39.3217, -75.2709, 39.3392),
        ("Back Creek",),
        "DE Bay sweep 10-20: 2400 m, B -0.12 -> -1.07 (est.)",
    ),
    "turner_fork": (
        (-75.449, 39.4439, -75.4356, 39.4599),
        ("Turner Fork",),
        "DE Bay sweep 10-20: 2330 m, B +0.14 -> -1.07 (est.)",
    ),
    "cherry_tree_creek": (
        (-75.4393, 39.399, -75.418, 39.4051),
        ("Cherry Tree Creek",),
        "DE Bay sweep 10-20: 2260 m, B +0.08 -> -1.07 (est.)",
    ),
    "mill_creek_7554": (
        (-75.5354, 39.5905, -75.5173, 39.6078),
        ("Mill Creek",),
        "DE Bay sweep 10-20: 2220 m, B -0.00 -> -0.47 (est.)",
    ),
    "bear_swamp_creek": (
        (-75.2728, 39.333, -75.2535, 39.3372),
        ("Bear Swamp Creek",),
        "DE Bay sweep 10-20: 2140 m, B +0.03 -> -1.07 (est.)",
    ),
    "back_ditch": (
        (-75.5286, 39.5136, -75.5125, 39.5207),
        ("Back Ditch",),
        "DE Bay sweep 10-20: 1990 m, B -0.07 -> -1.07 (est.)",
    ),
    "bowers_creek": (
        (-75.2359, 39.3192, -75.2274, 39.3289),
        ("Bowers Creek",),
        "DE Bay sweep 10-20: 1970 m, B +0.25 -> -1.07 (est.)",
    ),
    "alloway_hope_halfway": (
        (-75.5115, 39.4764, -75.5043, 39.4912),
        ("Alloway Hope Halfway",),
        "DE Bay sweep 10-20: 1950 m, B +0.01 -> -1.07 (est.)",
    ),
    "solters_creek": (
        (-75.499, 39.4756, -75.481, 39.4808),
        ("Solters Creek",),
        "DE Bay sweep 10-20: 1880 m, B +0.05 -> -1.07 (est.)",
    ),
    "bidwell_creek": (
        (-74.8911, 39.1077, -74.8441, 39.1285),
        ("Bidwell Creek",),
        "DE Bay sweep 10-20: 1870 m, B +0.63 -> -0.13 (est.)",
    ),
    "weir_creek": (
        (-75.1382, 39.2462, -75.1216, 39.2521),
        ("Weir Creek",),
        "DE Bay sweep 10-20: 1770 m, B +0.17 -> -1.07 (est.); OSM: bridge:residential Turkey Point Road",
    ),
    "western_cross": (
        (-75.2914, 39.323, -75.2792, 39.3282),
        ("Western Cross",),
        "DE Bay sweep 10-20: 1690 m, B +0.03 -> -1.07 (est.)",
    ),
    "ware_creek": (
        (-75.0854, 39.2152, -75.0823, 39.2285),
        ("Ware Creek",),
        "DE Bay sweep 10-20: 1530 m, B -0.15 -> -0.81 (est.); partial (local pool)",
    ),
    "skeeter_island_creek": (
        (-74.8672, 39.1002, -74.8642, 39.1142),
        ("Skeeter Island Creek",),
        "DE Bay sweep 10-20: 1510 m, B +0.70 -> -1.07 (est.)",
    ),
    "hansey_creek": (
        (-75.103, 39.2374, -75.092, 39.2405),
        ("Hansey Creek",),
        "DE Bay sweep 10-20: 1450 m, B +0.22 -> -1.07 (est.)",
    ),
    "ogden_creek": (
        (-75.269, 39.3444, -75.2577, 39.3513),
        ("Ogden Creek",),
        "DE Bay sweep 10-20: 1240 m, B +0.02 -> -1.07 (est.)",
    ),
    "old_hatch_creek": (
        (-75.2816, 39.3293, -75.2778, 39.3365),
        ("Old Hatch Creek",),
        "DE Bay sweep 10-20: 1110 m, B +0.04 -> -1.07 (est.)",
    ),
    "baldridge_creek": (
        (-75.5143, 39.5793, -75.5106, 39.5901),
        ("Baldridge Creek",),
        "DE Bay sweep 10-20: 1090 m, B -0.37 -> -0.64 (est.)",
    ),
    "ponds_creek": (
        (-75.2164, 39.2785, -75.2108, 39.2847),
        ("Ponds Creek",),
        "DE Bay sweep 10-20: 1060 m, B -0.14 -> -1.07 (est.)",
    ),
    "phillips_creek": (
        (-75.4008, 39.3957, -75.3927, 39.4035),
        ("Phillips Creek",),
        "DE Bay sweep 10-20: 970 m, B +0.06 -> -1.07 (est.)",
    ),
    "straight_ditch": (
        (-75.5262, 39.5192, -75.517, 39.5238),
        ("Straight Ditch",),
        "DE Bay sweep 10-20: 890 m, B -0.28 -> -1.07 (est.)",
    ),
    "green_creek": (
        (-74.9216, 39.0603, -74.9118, 39.0651),
        ("Green Creek",),
        "DE Bay sweep 10-20: 850 m, B -0.57 -> -0.93 (est.)",
    ),
    "howells_creek": (
        (-75.2402, 39.3157, -75.2347, 39.3206),
        ("Howells Creek",),
        "DE Bay sweep 10-20: 830 m, B +0.25 -> -1.07 (est.)",
    ),
    "alloway_creek": (
        (-75.4492, 39.5266, -75.4422, 39.5316),
        ("Alloway Creek",),
        "DE Bay sweep 10-20: 810 m, B -0.01 -> -1.33 (est.)",
    ),
    "goshen_creek": (
        (-74.8749, 39.1359, -74.8623, 39.1404),
        ("Goshen Creek",),
        "DE Bay sweep 10-20: 690 m, B +0.11 -> -0.19 (est.)",
    ),
    "sheep_pen_creek": (
        (-75.2869, 39.3417, -75.2802, 39.3444),
        ("Sheep Pen Creek",),
        "DE Bay sweep 10-20: 660 m, B +0.04 -> -1.07 (est.)",
    ),
    "middle_brook": (
        (-75.1956, 39.2981, -75.1916, 39.3036),
        ("Middle Brook",),
        "DE Bay sweep 10-20: 510 m, B -0.21 -> -1.07 (est.)",
    ),
    "bucks_ditch": (
        (-75.4709, 39.4398, -75.4665, 39.444),
        ("Bucks Ditch",),
        "DE Bay sweep 10-20: 510 m, B +0.03 -> -0.71 (est.); partial (local pool)",
    ),
    "blews_run": (
        (-75.2591, 39.349, -75.2546, 39.351),
        ("Blews Run",),
        "DE Bay sweep 10-20: 500 m, B +0.03 -> -1.07 (est.)",
    ),
    "rock_creek": (
        (-75.2701, 39.3502, -75.2658, 39.3537),
        ("Rock Creek",),
        "DE Bay sweep 10-20: 440 m, B +0.04 -> -1.07 (est.)",
    ),
    "dias_creek": (
        (-74.9025, 39.0896, -74.8977, 39.093),
        ("Dias Creek",),
        "DE Bay sweep 10-20: 390 m, B -0.68 -> -1.07 (est.)",
    ),
    "old_robins_branch": (
        (-74.8776, 39.1737, -74.8755, 39.177),
        ("Old Robins Branch",),
        "DE Bay sweep 10-20: 360 m, B -0.23 -> -1.07 (est.)",
    ),
    "menantico_creek": (
        (-75.01, 39.3383, -75.0083, 39.3423),
        ("Menantico Creek",),
        "DE Bay sweep 10-20: 350 m, B +0.09 -> -0.42 (est.); partial (local pool)",
    ),
    "pages_run": (
        (-75.1924, 39.2969, -75.1873, 39.2991),
        ("Pages Run",),
        "DE Bay sweep 10-20: 350 m, B -0.10 -> -1.07 (est.)",
    ),
}


def build_site(name, box, gnis) -> tuple[Path | None, int]:
    with rasterio.open(NJ10) as src:
        win = from_bounds(*box, transform=src.transform).round_offsets().round_lengths()
        z = src.read(1, window=win).astype("float64")
        tr = src.window_transform(win)
        nd = src.nodata
    z[(z == nd) | ~np.isfinite(z) | (z < -1e30)] = np.nan
    h, w = z.shape
    # hydro-flat: identical to all 8 neighbours (edges never qualify)
    flat = np.zeros_like(z, bool)
    c = z[1:-1, 1:-1]
    ok = np.isfinite(c)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy or dx:
                ok &= z[1 + dy : h - 1 + dy, 1 + dx : w - 1 + dx] == c
    flat[1:-1, 1:-1] = ok
    lines = gpd.read_file(NHD, layer="NHDFlowline", bbox=box)
    lines = lines[lines.gnis_name.isin(gnis)].set_crs(4269, allow_override=True)
    corr = lines.to_crs(32618).buffer(CORRIDOR_M).to_crs(4326)
    inside = rasterize(
        [(g, 1) for g in corr if g is not None and not g.is_empty],
        out_shape=(h, w),
        transform=tr,
        fill=0,
        dtype="uint8",
    ).astype(bool)
    lakes = gpd.read_file(LAKES, bbox=box).to_crs(4326)
    in_lake = (
        rasterize(
            [(g, 1) for g in lakes.geometry if g is not None and not g.is_empty],
            out_shape=(h, w),
            transform=tr,
            fill=0,
            dtype="uint8",
        ).astype(bool)
        if len(lakes)
        else np.zeros((h, w), bool)
    )
    hit = flat & inside & ~in_lake
    out = np.where(hit, z, NODATA).astype("float32")
    if hit.any():
        vals, cnt = np.unique(np.round(z[hit], 3), return_counts=True)
        top = ", ".join(
            f"{v:+.3f} m × {n}"
            for v, n in sorted(zip(vals, cnt), key=lambda t: -t[1])[:3]
        )
        print(f"  {name}: {len(lines)} flowlines, {hit.sum()} px painted; values {top}")
    else:
        print(f"  {name}: nothing painted")
        return None, 0
    dst = OUT / f"creek_bed_nj10ft_{name}_v4.tif"
    fd, tmp = tempfile.mkstemp(dir=OUT, prefix=f".{dst.name}.", suffix=".tif")
    os.close(fd)
    with rasterio.open(
        tmp,
        "w",
        driver="GTiff",
        height=h,
        width=w,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=tr,
        nodata=NODATA,
        compress="DEFLATE",
        tiled=True,
        blockxsize=256,
        blockysize=256,
    ) as ds:
        ds.write(out, 1)
        ds.update_tags(
            source=f"NJ 10 ft DEM hydro-flat pixels within {CORRIDOR_M} m of NHD "
            f"{list(gnis)}, box {box}; paint with :min",
            units="m NAVD88",
        )
    os.chmod(tmp, 0o644)
    os.replace(tmp, dst)
    return dst, int(hit.sum())


def main() -> int:
    if not OUT.exists():
        SCRATCH.mkdir(parents=True, exist_ok=True)
        OUT.symlink_to(SCRATCH)
    tifs = []
    for n, (box, gnis, _why) in CREEKS.items():
        dst, n_hit = build_site(n, box, gnis)
        if n_hit:
            tifs.append(dst)
    vrt = OUT / "creek_bed_nj10ft_v4.vrt"
    subprocess.run(
        [
            "gdalbuildvrt",
            "-q",
            "-overwrite",
            "-srcnodata",
            str(NODATA),
            "-vrtnodata",
            str(NODATA),
            str(vrt),
            *map(str, tifs),
        ],
        check=True,
    )
    print(f"  wrote {vrt.relative_to(ROOT)} ({len(tifs)} sites)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
