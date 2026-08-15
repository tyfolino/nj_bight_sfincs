#!/usr/bin/env python
"""Clip USGS CoNED NJ/DE topobathy to the southwest-Raritan box → one elevation tier.

    python scripts/build_coned_sw_raritan.py [--force]

WHAT THIS FIXES
---------------
`cudem_nj` is missing the Ward Point headland: its land stops at lat 40.49982 in every
column across ~800 m and backfills the missing ~230 m of New York State as −3 to −5.5 m of
bay. West of lon −74.2504 it has no tile at all, so Conference House Park — dry parkland —
falls through every tier to 50 m GMRT and reads −0.06 m. `nj_10ft_dem` cannot help: it is
NEW-JERSEY-ONLY and Staten Island is New York.

🔴 THIS TIER MUST SIT ABOVE ``cudem_nj``. The phantom water is a VALUE, not NoData, so a
tier placed below CUDEM changes nothing at Ward Point. It sits BELOW the eHydro tiers:
eHydro is the surveyed dredged channel and is deeper at both forced cuts (−13.56 vs −9.81 m
at the Arthur Kill mouth; −9.85 vs −2.08 m in the Raritan), and its Raritan survey is 95
days pre-Sandy.

🔴 WHY IT IS CLIPPED TO A BOX RATHER THAN ADDED WHOLE
-----------------------------------------------------
CoNED NJ/DE is compiled 2015 from sources through 2014, so on Staten Island its lidar is
**after** the storm this model hindcasts. On bedrock upland that does not matter — Ward
Point did not appear between 2012 and 2014. On erodible beach, dune and berm it matters a
lot, and post-Sandy topography is the WRONG bed for a Sandy hindcast. The sweep
(`scripts/sweep_cudem_flatfill.py`) found exactly that at Oakwood Beach, lon −74.133, where
CUDEM reads −4.08 m and CoNED +0.93 m on ground that saw post-storm berm and buyout work.
There the OLDER bed is the more correct one.

So the box takes CoNED only where CUDEM is structurally broken, and leaves every erodible
shoreline on its pre-storm bed. 93.5% of all phantom water on the Staten Island + Rockaway
frontage is inside it.

THE SEAM WAS MEASURED BEFORE THE BOX WAS ADOPTED
------------------------------------------------
CoNED − merged stack along each edge, median: east +0.012, west −0.004, north +0.000,
south +0.016 m. A hard box edge therefore introduces a step of centimetres. (One 14.44 m
outlier on the north edge is a building seen by 1 m lidar and not by 3 m CUDEM, on inland
Staten Island, which the region excludes anyway.)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SRC = ROOT / "data" / "elevation_v1_5" / "coned" / "NJ_DE_Topobathy_DEM_v2_10_20.tif"
DST = ROOT / "data" / "elevation_v1_5" / "coned_sw_raritan.tif"

#: 🔴 THE DECLARED BOX (lon_min, lat_min, lon_max, lat_max). A coordinate box, not an
#: auto-derived polygon, on purpose — see the repo conventions. It covers:
#:   * the CUDEM hole      lon -74.2991..-74.2505, lat 40.4800..40.5115  (+33.28 km2 of bed)
#:   * the Ward Point patch lon -74.2537..-74.2372, lat 40.4961..40.5012 (0.187 km2)
#:   * the Perth Amboy patch lon -74.2552..-74.2542, lat 40.5021..40.5039
#: and deliberately EXCLUDES Oakwood Beach (lon -74.133), which is a real post-Sandy change.
BOX = (-74.3120, 40.4640, -74.2320, 40.5340)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="overwrite an existing output")
    a = ap.parse_args()

    if not SRC.exists():
        print(f"missing {SRC}\n  fetch it from the NOAA bulk store, e.g.\n"
              "  curl -O https://noaa-nos-coastal-lidar-pds.s3.amazonaws.com/dem/"
              "NewJersey_Delaware_Coned_Topobathy_DEM_2015_5040/"
              "NJ_DE_Topobathy_DEM_v2_10_20.tif")
        return 1
    if DST.exists() and not a.force:
        print(f"{DST} exists — pass --force to rebuild")
        return 0

    with rasterio.open(SRC) as src:
        fwd = Transformer.from_crs(4326, src.crs, always_xy=True)
        xs, ys = fwd.transform(
            [BOX[0], BOX[2], BOX[0], BOX[2]], [BOX[1], BOX[1], BOX[3], BOX[3]]
        )
        win = from_bounds(min(xs), min(ys), max(xs), max(ys), src.transform).round_offsets(
        ).round_lengths()
        arr = src.read(1, window=win).astype("float32")
        t = src.window_transform(win)
        prof = src.profile.copy()
        nodata = src.nodata if src.nodata is not None else -3.4028234663852886e38

        # The declared box is in LON/LAT, so a UTM-rectangular window is not the box.
        # NoData everything outside the true box, or the tier would quietly extend past
        # its declaration at the corners.
        nr, nc = arr.shape
        cx = t.c + (np.arange(nc) + 0.5) * t.a
        cy = t.f + (np.arange(nr) + 0.5) * t.e
        X, Y = np.meshgrid(cx, cy)
        inv = Transformer.from_crs(src.crs, 4326, always_xy=True)
        LO, LA = inv.transform(X.ravel(), Y.ravel())
        LO = LO.reshape(nr, nc)
        LA = LA.reshape(nr, nc)
        outside = (LO < BOX[0]) | (LO > BOX[2]) | (LA < BOX[1]) | (LA > BOX[3])
        arr[outside] = nodata
        arr[arr < -9000] = nodata

    prof.update(
        height=nr, width=nc, transform=t, dtype="float32", nodata=nodata,
        compress="deflate", predictor=2, tiled=True, blockxsize=512, blockysize=512,
        BIGTIFF="IF_SAFER",
    )
    DST.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(DST, "w", **prof) as dst:
        dst.write(arr, 1)

    valid = arr[arr > -9000]
    print(f"wrote {DST}")
    print(f"  {nc} x {nr} @ 1 m, crs {prof['crs']}")
    print(f"  box  lon {BOX[0]}..{BOX[2]}  lat {BOX[1]}..{BOX[3]}")
    print(f"  valid cells {valid.size:,} ({100*valid.size/arr.size:.1f}%)  "
          f"z {valid.min():.2f} .. {valid.max():.2f} m NAVD88")
    print(f"  land (>0) {100*(valid > 0).mean():.1f}%   water {100*(valid <= 0).mean():.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
