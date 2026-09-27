#!/usr/bin/env python
"""The COARSE bed for a domain: its elevation list, warped to 25 m UTM and stacked.

    NJ_DOMAIN=v4 python scripts/build_coarse_bed.py        (hpc/build_coarse_bed.slurm)

Used ONLY for quadtree refinement gating and the face elevation ``z``
(``Domain.coarse_elevation_list``); the subgrid samples the native tiers. Why it exists
at all: hydromt's refine_in_polygon merges EVERY tier onto the polygon's bbox at each
level, and on v3's bbox that reached 164 GB RSS in two minutes (2026-08-24).

Generalises ``scripts/build_v3_coarse_bed.sh`` with ONE change of substance: the tier
order is READ from ``Domain.elevation_list`` (and each file from the data catalog) instead
of being typed a second time. The v3 script's hand list had drifted — it stacks
``cudem13_v3`` ABOVE ``nj_10ft_dem_v3``, the reverse of V3_ELEVATION_LIST (v3's coarse
bed only; its subgrid follows the list). Rules carried over from v3:

  * base tiers resample BILINEAR (hydromt's own face method);
  * CARVING tiers (``ehydro*``, ``shrewsbury*``, ``riverbeds*``) resample MIN, so a 5 m
    channel narrower than a 25 m cell keeps its depth (bilinear paved 69 Shark-inlet
    faces on v3 and failed the paved-channel invariant);
  * a tier's ``zmin`` masks values ≤ zmin to NoData first (the NJ lidar reads 0.0 over
    water and its rectangle covers the whole shelf — without it v3's first coarse bed
    paved 817,718 offshore faces to z = 0).

Output: data/elevation_<dom>/bed_<dom>_coarse_25m.tif (+ 50/100/200 m overviews), with a
report of any ground INSIDE the ring that no tier covers.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nj_sfincs import domain as _domain  # noqa: E402

RES = 25.0
NODATA = -99999.0
CARVING = ("ehydro", "shrewsbury", "riverbeds")


def _uri(key: str) -> Path:
    import yaml

    cat = yaml.safe_load((ROOT / "data" / "data_catalog.yml").read_text())
    return ROOT / "data" / cat[key]["uri"]


def main() -> int:
    import geopandas as gpd
    import rasterio
    import shapely
    from rasterio.features import geometry_mask

    dom = _domain.active()
    if not dom.elevation_list:
        raise SystemExit(f"{dom.name}: no elevation_list")
    ring = gpd.read_file(dom.region).to_crs(dom.epsg).geometry.iloc[0]
    bx0, by0, bx1, by1 = ring.bounds  # snapped outward to whole km
    x0, y0 = np.floor(bx0 / 1000) * 1000, np.floor(by0 / 1000) * 1000
    x1, y1 = np.ceil(bx1 / 1000) * 1000, np.ceil(by1 / 1000) * 1000
    te = [str(int(v)) for v in (x0, y0, x1, y1)]
    out = (
        ROOT / "data" / f"elevation_{dom.name}" / f"bed_{dom.name}_coarse_25m.tif"
    ).resolve()
    work = Path(
        tempfile.mkdtemp(prefix=f"coarse_{dom.name}_", dir=os.environ.get("TMPDIR"))
    )
    print(
        f"{dom.name}: {len(dom.elevation_list)} tiers, -te {' '.join(te)} @ {RES:.0f} m -> {out}"
    )

    layers = []  # bottom first, for the last-wins VRT
    for k, entry in enumerate(reversed(dom.elevation_list)):
        key = entry["elevation"]
        src = _uri(key)
        how = "min" if key.startswith(CARVING) else "bilinear"
        dst = work / f"t{k:02d}_{key}.tif"
        subprocess.run(
            [
                "gdalwarp",
                "-q",
                "-overwrite",
                "-t_srs",
                f"EPSG:{dom.epsg}",
                "-te",
                *te,
                "-tr",
                str(RES),
                str(RES),
                "-r",
                how,
                "-dstnodata",
                str(NODATA),
                "-of",
                "GTiff",
                "-co",
                "COMPRESS=DEFLATE",
                "-co",
                "TILED=YES",
                "-wo",
                "NUM_THREADS=4",
                "-multi",
                str(src),
                str(dst),
            ],
            check=True,
        )
        with rasterio.open(dst, "r+") as d:
            a = d.read(1)
            valid = a != NODATA
            if "zmin" in entry:
                cut = valid & (a <= entry["zmin"])
                a[cut] = NODATA
                d.write(a, 1)
                valid &= ~cut
            print(
                f"  {key:26s} {how:8s} {valid.mean():6.1%} of the box"
                + (f"  (≤ {entry['zmin']} → NoData)" if "zmin" in entry else "")
            )
        layers.append(str(dst))

    vrt = work / "stack.vrt"
    subprocess.run(
        [
            "gdalbuildvrt",
            "-q",
            "-overwrite",
            "-srcnodata",
            str(NODATA),
            str(vrt),
            *layers,
        ],
        check=True,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(f".{out.name}.tmp.tif")
    subprocess.run(
        [
            "gdal_translate",
            "-q",
            "-of",
            "GTiff",
            "-co",
            "COMPRESS=DEFLATE",
            "-co",
            "TILED=YES",
            "-a_nodata",
            str(NODATA),
            str(vrt),
            str(tmp),
        ],
        check=True,
    )
    subprocess.run(
        ["gdaladdo", "-q", "-r", "average", str(tmp), "2", "4", "8"], check=True
    )
    os.replace(tmp, out)

    with rasterio.open(out) as d:
        a = d.read(1)
        inside = ~geometry_mask([ring], a.shape, d.transform)
    hole = inside & (a == NODATA)
    print(
        f"wrote {out}: {a.shape[1]} x {a.shape[0]}, "
        f"z {a[a != NODATA].min():+.1f}..{a[a != NODATA].max():+.1f} m"
    )
    print(
        f"ring cells with NO tier: {int(hole.sum())} ({hole.sum() * RES * RES / 1e6:.2f} km²)"
    )
    if hole.any():
        rr, cc = np.nonzero(hole)
        xs, ys = rasterio.transform.xy(d.transform, rr, cc)
        pts = gpd.GeoSeries(shapely.points(xs, ys), crs=dom.epsg).to_crs(4326)
        print(
            f"  lon {pts.x.min():.3f}..{pts.x.max():.3f} lat {pts.y.min():.3f}..{pts.y.max():.3f}"
        )
    subprocess.run(["rm", "-rf", str(work)], check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
