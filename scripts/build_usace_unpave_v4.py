#!/usr/bin/env python
"""Undo the 2010 USACE topobathy lidar where it paves deep water → one overlay tier.

    python scripts/build_usace_unpave_v4.py

WHAT THIS FIXES. ``usace_nj_2010_v3`` (2010 NCMP topobathy lidar) outranks CUDEM in the v3
and v4 bed lists because it is the PRE-Sandy beach and nearshore. Where the green laser did
not reach the bottom it returns a flat surface near 0 m, and that surface wins over CUDEM's
real bed. The 10-05 channel sweep (``logs/audit_v4_hot_plus_2026-10-05/channels_and_3dep/``,
class F4) confirmed three sites against eHydro soundings:

* **Great Egg Harbor Inlet**, Longport → Ocean City: a 3.3 km × 300 m band at −0.41 m
  straight across the 8 m inlet channel (IW_12 soundings on it: 9.2 m deeper).
* **Inside Thorofare**, Atlantic City / Ventnor (NJIWW IW_10): +0.1..+0.2 m against −4 m
  surveyed; the ``usgs_tidal_inside_thorofare`` gauge sits on it.
* **Shoal Harbor / Compton Creek**: +0.34 m against −4.1 m (NJ_15_SHC, also in
  ``ehydro_refreeze_cenan_v4``, which outranks this tier).

RULE, inside the declared boxes only (coordinate boxes, not a derived polygon): at each
2010-lidar pixel, take CUDEM 1/9″ (bilinear) when

    usace > −0.8 m   (the lidar returned a near-surface value)
    cudem < −1.0 m   (CUDEM sees water deeper than a metre)
    usace − cudem > 1.0 m

and NoData everywhere else. Elsewhere — the open beach strip especially, where the 2010 and
CUDEM beds differ because of Sandy itself and the PRE-storm one is right — nothing changes.
The ~15 smaller back-bay patches Ocean City → Wildwood the sweep found are causeway
CANDIDATES, not confirmed, and are deliberately not boxed.

Output: data/elevation_v4/usace_unpave/usace_unpave_<site>_v4.tif (EPSG:4326, the 2010
lidar's own lattice, NoData −9999, m NAVD88) + usace_unpave_v4.vrt. Painted by
``rebuild_subgrid.py --overlay usace_unpave_v4``. 🔴 v3 has the same tier and the same
defect; this file does not touch v3.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[1]
USACE = ROOT / "data" / "elevation_v3" / "usace_nj_2010_topobathy_v3.tif"
CUDEM = ROOT / "data" / "elevation_v3" / "cudem_nj_v3.vrt"
OUT = ROOT / "data" / "elevation_v4" / "usace_unpave"
SCRATCH = Path("/scratch/tpj8/nj_bight_sfincs_data/elevation_v4/usace_unpave")
NODATA = -9999.0

#: (lon_min, lat_min, lon_max, lat_max) — the sweep's F4 clusters padded by ~300 m.
BOXES: dict[str, tuple[float, float, float, float]] = {
    "great_egg_inlet": (-74.5690, 39.2895, -74.5230, 39.3185),
    "inside_thorofare": (-74.4850, 39.3360, -74.4560, 39.3580),
    "compton_creek": (-74.0870, 40.4290, -74.0790, 40.4370),
}
USACE_MIN = -0.8
CUDEM_MAX = -1.0
GAP = 1.0


def build_site(name: str, box: tuple[float, float, float, float]) -> Path:
    with rasterio.open(USACE) as us:
        win = from_bounds(*box, transform=us.transform).round_offsets().round_lengths()
        u = us.read(1, window=win, masked=True).astype("float64").filled(np.nan)
        tr = us.window_transform(win)
        h, w = u.shape
    with (
        rasterio.open(CUDEM) as cu,
        WarpedVRT(
            cu,
            crs="EPSG:4326",
            transform=tr,
            width=w,
            height=h,
            resampling=Resampling.bilinear,
            nodata=-9999.0,
        ) as v,
    ):
        c = v.read(1).astype("float64")
    c[c <= -9998] = np.nan
    hit = (
        np.isfinite(u)
        & np.isfinite(c)
        & (u > USACE_MIN)
        & (c < CUDEM_MAX)
        & (u - c > GAP)
    )
    out = np.where(hit, c, NODATA).astype("float32")
    px = (
        abs(tr.a)
        * 111_320
        * np.cos(np.radians((box[1] + box[3]) / 2))
        * abs(tr.e)
        * 110_570
    )
    print(
        f"  {name}: {w}x{h} px, {hit.sum()} painted ({hit.sum() * px / 1e6:.3f} km²); "
        f"usace p50 {np.nanmedian(u[hit]):+.2f} → cudem p50 {np.nanmedian(c[hit]):+.2f}, "
        f"p10 {np.nanpercentile(c[hit], 10):+.2f} m"
    )
    dst = OUT / f"usace_unpave_{name}_v4.tif"
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
            source=f"CUDEM 1/9in where usace_nj_2010 > {USACE_MIN} over CUDEM < {CUDEM_MAX} "
            f"by > {GAP} m, box {box}",
            units="m NAVD88",
        )
    os.chmod(tmp, 0o644)
    os.replace(tmp, dst)
    return dst


def main() -> int:
    if not OUT.exists():
        SCRATCH.mkdir(parents=True, exist_ok=True)
        OUT.symlink_to(SCRATCH)
    tifs = [build_site(n, b) for n, b in BOXES.items()]
    vrt = OUT / "usace_unpave_v4.vrt"
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
    print(f"  wrote {vrt.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
