"""Where can the MOTF sheet adjudicate? A validity raster ON the active domain's MOTF grid.

The MOTF source layer is New Jersey only, and its render has no nodata: land it does not
cover reads as confidently DRY, so every model-wet pixel there books a false alarm the
sheet cannot judge. v1.5 / v3 cut the NY land out with lon/lat boxes; v4 computes the
DE / PA far banks too (~2,100 km² in the ring), along a diagonal river no box staircase
follows. So v4 is scored ONLY ON NJ LAND (user 2026-09-29) — where the NJ-only 10 ft DEM
has data, the discriminator v1.5's boxes were validated with, used directly.

Output: uint8 on exactly the ``Domain.motf_tif`` grid, 1 = valid (the source has data
there), 0 = not. ``validate.metrics.motf_invalid_mask`` refuses one on another grid.

    NJ_DOMAIN=v4 PYTHONPATH=$PWD python scripts/build_motf_valid_mask.py \
        --source data/elevation_v4/nj_10ft_dem_v4.tif
    -> Domain.motf_valid_tif
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from rasterio.warp import Resampling, reproject  # noqa: E402

import nj_sfincs  # noqa: F401,E402 — pyproj before hydromt
from nj_sfincs import domain as _domain  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--source",
        type=Path,
        required=True,
        help="a raster whose DATA EXTENT is where the sheet is valid",
    )
    args = ap.parse_args()

    dom = _domain.active()
    out = dom.motf_valid_tif
    if out is None:
        sys.exit(f"{dom.name} declares no motf_valid_tif — add it in domain.py first")
    with rasterio.open(dom.motf_tif) as m:
        prof, shape, T, crs = m.profile, m.shape, m.transform, m.crs

    has = np.zeros(shape, dtype=np.float32)
    with rasterio.open(args.source) as src:
        # nearest onto the 15 m cell centres; the data mask, not the values
        reproject(
            rasterio.band(src, 1),
            has,
            src_nodata=src.nodata,
            dst_transform=T,
            dst_crs=crs,
            dst_nodata=np.nan,
            resampling=Resampling.nearest,
        )
    valid = np.isfinite(has).astype("uint8")
    km2 = abs(T.a * T.e) / 1e6
    print(
        f"{dom.name}: {valid.sum() * km2:,.0f} km² valid of "
        f"{valid.size * km2:,.0f} km² on the MOTF grid ({shape[1]} x {shape[0]})"
    )

    prof.update(dtype="uint8", nodata=None, compress="deflate")
    tmp = out.with_name(f".{out.name}.partial.tif")
    with rasterio.open(tmp, "w", **prof) as dst:
        dst.write(valid, 1)
    os.replace(tmp, out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
