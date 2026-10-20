#!/usr/bin/env python
"""Undo the 2010 USACE lidar's paving of back-bay CHANNELS → a second overlay tier.

    python scripts/build_usace_unpave_backbay_v4.py

The companion of ``build_usace_unpave_v4.py`` (Great Egg Inlet, Inside Thorofare, Compton
Creek), with the SAME rule in a NEW set of declared boxes, written to a NEW raster so the
first tier's output is untouched. Rule, inside each box only: at each 2010-lidar pixel take
CUDEM 1/9″ (bilinear) when

    usace > −0.8 m   and   cudem < −1.0 m   and   usace − cudem > 1.0 m

(constants imported from ``build_usace_unpave_v4``), NoData elsewhere.

WHICH BOXES. The 10-05 channel sweep's F4 class listed ~30 smaller clusters besides the
three confirmed sites (``logs/audit_v4_hot_plus_2026-10-05/channels_and_3dep/
fill_clusters.csv``). Each was mapped against orthoimagery, CUDEM, the model bed and the
National Bridge Inventory (``logs/refreeze_2026-10-05/bed_candidates/``):

* NONE is a bridge deck or causeway. No cluster is centred on an NBI bridge (nearest
  106–900 m from a cluster centre; ≤ 15 % of a cluster's pixels within 60 m); the
  paved values are flat at water level (p50 −0.4 … +0.3 m) or at marsh level where the
  product interpolated across a no-return gap (+0.7 … +1.2 m). It is the Great Egg
  failure (green laser not reaching the bottom of turbid water), not a structure.
* BOXED here (10): channels and basins that imagery shows as open water and CUDEM as a
  continuous channel; four are confirmed by eHydro soundings in the box (Townsends west
  −4.75 m, Sea Isle south −5.4 m, Little Egg north −6.4 m, Beach Haven −2.1 m, vs the 2010
  lidar's −0.3 … +1.1 m).
* NOT boxed: the ocean beach / swash strip (beach change between 2010 and CUDEM; the
  PRE-Sandy 2010 bed is the right one), inlet shoals and spits (Hereford, Corson's south
  spit, Brigantine, Little Egg / Holgate tips: erodible, pre-storm 2010 kept), and
  bulkhead-edge slivers along open bays (no channel blocked).

Output: data/elevation_v4/usace_unpave_backbay/usace_unpave_backbay_<site>_v4.tif
(EPSG:4326, the 2010 lidar's own lattice, NoData −9999, m NAVD88) +
usace_unpave_backbay_v4.vrt. Painted by ``rebuild_subgrid.py --overlay
usace_unpave_backbay_v4`` (after ``usace_unpave_v4``; the boxes do not overlap it).
🔴 v3 has the same tier and the same defect; this file does not touch v3.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from rasterio.windows import from_bounds

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_usace_unpave_v4 as first  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "elevation_v4" / "usace_unpave_backbay"
SCRATCH = Path("/scratch/tpj8/nj_bight_sfincs_data/elevation_v4/usace_unpave_backbay")
NODATA = first.NODATA

#: (lon_min, lat_min, lon_max, lat_max) → (box, the F4 cluster ids it covers, what it is)
BOXES: dict[str, tuple[tuple[float, float, float, float], str]] = {
    "grassy_sound": (
        (-74.8040, 39.0165, -74.7980, 39.0280),
        "4000094: Grassy Sound channel by the Ocean Drive bridge, lidar +0.73 over −1.9",
    ),
    "beach_creek_nwildwood": (
        (-74.8030, 39.0080, -74.7950, 39.0164),
        "Beach Creek, North Wildwood: lidar TIN +1.1 across the creek over CUDEM −1.7, a "
        "+0.85 m sill vs MHHW +0.65 (missed by the 10-05 F4 sweep; 2026-10-20 desk check "
        "site 16, logs/paved_channels_check_2026-10-20/); south of grassy_sound, no overlap",
    ),
    "sea_isle_south": (
        (-74.7225, 39.1080, -74.7130, 39.1160),
        "4000173: the channel round the marsh south of Sea Isle City (IW_14 −5.4 m)",
    ),
    "townsends_west": (
        (-74.7220, 39.1201, -74.7130, 39.1312),
        "4000195: Townsends Inlet, the marsh-side channel + bay edge (IW_14 −4.75 m); "
        "the inlet-mouth shoals south of 39.120 excluded",
    ),
    "strathmere_back": (
        (-74.6770, 39.1820, -74.6698, 39.1878),
        "4000238: the channel behind Strathmere, lidar −0.25 over −1.6 … −3.7",
    ),
    "corsons_inlet": (
        (-74.6640, 39.1975, -74.6528, 39.2085),
        "4000263/4000272: Corson's Inlet marsh-side channel, the bridge span and the "
        "flood-channel patch; the Strathmere spit east of −74.6525 excluded",
    ),
    "little_egg_north": (
        (-74.3078, 39.5028, -74.2985, 39.5072),
        "4000432: the marsh channel north of Little Egg Inlet (IW_08 −6.4 m), lidar "
        "−0.30 flat (IQR 0.07)",
    ),
    "ac_canal": (
        (-74.4228, 39.3712, -74.4182, 39.3755),
        "4000376: an Atlantic City marina canal, lidar +1.2 over −4.3; Absecon Inlet "
        "beach north of 39.3755 excluded",
    ),
    "beach_haven_marina": (
        (-74.2328, 39.5774, -74.2280, 39.5822),
        "4000494: Beach Haven bay-side marina basins (IW_07 −2.1 m), lidar +1.06",
    ),
    "waackaack_creek": (
        (-74.1480, 40.4456, -74.1405, 40.4495),
        "4000987: Waackaack Creek, Keansburg, lidar +0.02 over CUDEM −1.6 "
        "(usgs_tidal_keansburg nearby)",
    ),
    "pews_creek": (
        (-74.1046, 40.4395, -74.1013, 40.4432),
        "4000983: Pews Creek, Port Monmouth, lidar +0.48 over CUDEM −1.2",
    ),
}


def build_site(name: str, box: tuple[float, float, float, float]) -> tuple[Path, int]:
    with rasterio.open(first.USACE) as us:
        win = from_bounds(*box, transform=us.transform).round_offsets().round_lengths()
        u = us.read(1, window=win, masked=True).astype("float64").filled(np.nan)
        tr = us.window_transform(win)
        h, w = u.shape
    with (
        rasterio.open(first.CUDEM) as cu,
        WarpedVRT(
            cu,
            crs="EPSG:4326",
            transform=tr,
            width=w,
            height=h,
            resampling=Resampling.bilinear,
            nodata=NODATA,
        ) as v,
    ):
        c = v.read(1).astype("float64")
    c[c <= NODATA + 1] = np.nan
    hit = (
        np.isfinite(u)
        & np.isfinite(c)
        & (u > first.USACE_MIN)
        & (c < first.CUDEM_MAX)
        & (u - c > first.GAP)
    )
    out = np.where(hit, c, NODATA).astype("float32")
    px = (
        abs(tr.a)
        * 111_320
        * np.cos(np.radians((box[1] + box[3]) / 2))
        * abs(tr.e)
        * 110_570
    )
    if hit.any():
        print(
            f"  {name}: {w}x{h} px, {hit.sum()} painted ({hit.sum() * px / 1e6:.4f} km²); "
            f"usace p50 {np.nanmedian(u[hit]):+.2f} → cudem p50 "
            f"{np.nanmedian(c[hit]):+.2f}, p10 {np.nanpercentile(c[hit], 10):+.2f} m"
        )
    else:
        print(f"  {name}: nothing painted")
    dst = OUT / f"usace_unpave_backbay_{name}_v4.tif"
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
            source=f"CUDEM 1/9in where usace_nj_2010 > {first.USACE_MIN} over CUDEM < "
            f"{first.CUDEM_MAX} by > {first.GAP} m, box {box}",
            units="m NAVD88",
        )
    os.chmod(tmp, 0o644)
    os.replace(tmp, dst)
    return dst, int(hit.sum())


def main() -> int:
    if not OUT.exists():
        SCRATCH.mkdir(parents=True, exist_ok=True)
        OUT.symlink_to(SCRATCH)
    for a in BOXES.values():
        for b in first.BOXES.values():
            ax0, ay0, ax1, ay1 = a[0]
            if not (ax1 < b[0] or b[2] < ax0 or ay1 < b[1] or b[3] < ay0):
                raise SystemExit(f"box {a[0]} overlaps usace_unpave_v4's {b}")
    tifs = []
    for n, (box, _why) in BOXES.items():
        dst, n_hit = build_site(n, box)
        if n_hit:
            tifs.append(dst)
    vrt = OUT / "usace_unpave_backbay_v4.vrt"
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
