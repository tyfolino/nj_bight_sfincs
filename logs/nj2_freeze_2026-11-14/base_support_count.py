#!/usr/bin/env python
"""PREVIEW of ``Domain.n_waterlevel_support`` on a frozen mesh, with hydromt's OWN selection.

    NJ_DOMAIN=nj2 python logs/nj2_freeze_2026-11-14/base_support_count.py <frozen_mesh_dir>

🔴 WHICH NUMBER THIS IS. ``Domain.n_waterlevel_support`` is the support count of the BASE
water-level source, ``BaseConfig.waterlevel_geodataset`` (``noaa_sandy_nj``: three NOAA gauges
in the file; v4 / 1.x selected all 3). The template build (J2 step 5,
``model.add_forcing`` -> ``check_waterlevel_support``) is the first place it is ASSERTED — its
``[bnd] N water-level support point(s)`` line in ``template_nj2.log``. It is NOT the NACCS count
J2 step 4 prints (that one is ``experiments._NJ2_NACCS_SUPPORT``, set on the ARMS).

This runs the template build's selection without the template: the frozen mask's ``mask == 2``
faces -> ``hydromt_sfincs.utils.get_bounds_vector`` (what ``water_level.create`` clips with) ->
``DataCatalog.get_geodataset(<base source>, geom=…, buffer=Domain.waterlevel_buffer,
variables=["waterlevel"], time_range=BaseConfig window)``. Read-only. Prints one machine line
``[base-bnd] N`` last.
"""

from __future__ import annotations

import sys
from pathlib import Path

import nj_sfincs  # noqa: F401  (PROJ primer — must precede hydromt_sfincs)


def main(mesh_dir: str) -> int:
    import xugrid as xu
    from hydromt import DataCatalog
    from pyproj import CRS

    from hydromt_sfincs import utils
    from nj_sfincs import domain as D
    from nj_sfincs.config import BaseConfig

    dom, base = D.active(), BaseConfig()
    ds = xu.open_dataset(Path(mesh_dir) / "sfincs.nc")
    crs = CRS.from_wkt(ds["crs"].attrs["crs_wkt"])
    da = ds["mask"].load()
    da.grid.set_crs(crs)
    region = utils.get_bounds_vector(da)
    region = region[region["value"] == 2]
    cat = DataCatalog(data_libs=base.data_libs)
    sel = cat.get_geodataset(
        base.waterlevel_geodataset,
        geom=region,
        buffer=dom.waterlevel_buffer,
        variables=["waterlevel"],
        time_range=(base.tstart, base.tstop),
    )
    gdf = sel.vector.to_gdf()
    print(
        f"source {base.waterlevel_geodataset}  buffer {dom.waterlevel_buffer:,} m  "
        f"forced lines {len(region)}  selected: {list(map(str, gdf.index))}"
    )
    print(f"[base-bnd] {len(gdf)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:]))
