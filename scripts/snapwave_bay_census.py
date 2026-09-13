#!/usr/bin/env python
"""Per map hour: bay wind sea, spike cells, IG ratio, and CORA-in-the-bay — one table.

    PYTHONPATH=$PWD python scripts/snapwave_bay_census.py <run> [--hours ...] [--csv out]

Promoted 2026-09-13 from the 09-12 AM scratch read (STATUS 09-12) so the period-floor
cuts, the IG cut and the Phase 4 arms are censused by ONE definition:

  bnd_max     max hm0 on the SnapWave boundary cells (snapwavemsk == 2)
  n_spike     SnapWave-active cells with hm0 > 1.2 x bnd_max  (the 09-12 spike census)
  n_gt6/gt8   cells with hm0 > 6 / 8 m; field_max the largest hm0 anywhere
  bay_med/p99 hm0 on SFINCS-active cells in the Lower + Raritan Bay box
              (-74.32..-74.00, 40.40..40.60 — STATUS 09-12; pre-registered 0.2-0.5 m)
  pocket / raritan_s / lower_n   hm0 medians in the three D2 boxes (Phase 4b D2):
              Sandy Hook Bay pocket (-74.10..-73.99, 40.40..40.48), Raritan Bay south of
              40.48 (-74.32..-74.10, 40.40..40.48), Lower Bay north of 40.48
              (-74.25..-73.95, 40.48..40.60) — coordinate boxes, not derived polygons
  cora_*      the median CORA SWAN `hs` over the CORA nodes inside the same boxes at the
              nearest CORA time (D2 criterion: |model - CORA| <= 0.3 m)
  ig_ratio_p99, ig_max, n_ig_gt1   when the map carries `hm0ig` (Phase 8 IG criteria:
              hm0ig/hm0 p99 <= 0.5 on cells deeper than 5 m, no cell hm0ig > 1.0 m)

Bay cells are SFINCS-active (`msk == 1`) AND subtidal (mesh z < -0.5 m); the spike census runs over every SnapWave-active
cell (`snapwavemsk > 0`), i.e. the offshore band included. Depth for the IG ratio is the
mesh `z` in sfincs.nc (NOT the map's `zb`, which is NaN on inactive faces, FINDINGS §37).
Partial-map safe (reuses `snapwave_direction_check.load_run`).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from pyproj import CRS, Transformer

sys.path.insert(0, str(Path(__file__).resolve().parent))
from snapwave_direction_check import load_run  # noqa: E402

import nj_sfincs  # noqa: E402,F401
from nj_sfincs import domain as _domain  # noqa: E402

BAY = (-74.32, 40.40, -74.00, 40.60)
D2 = {
    "pocket": (-74.10, 40.40, -73.99, 40.48),
    "raritan_s": (-74.32, 40.40, -74.10, 40.48),
    "lower_n": (-74.25, 40.48, -73.95, 40.60),
}
SPIKE_FACTOR = 1.2
WATER_ZMAX = -0.5  # m, mesh z: box statistics use subtidal water cells only


def _inbox(lon, lat, box):
    x0, y0, x1, y1 = box
    return (lon >= x0) & (lon <= x1) & (lat >= y0) & (lat <= y1)


def census(
    run_dir: Path, hours: list[str] | None, cora_path: Path | None
) -> pd.DataFrame:
    run = load_run(run_dir)
    mesh = xr.open_dataset(run_dir / "sfincs.nc", decode_times=False)
    crs = CRS.from_wkt(mesh["crs"].attrs["crs_wkt"])
    to_ll = Transformer.from_crs(crs, 4326, always_xy=True)
    lon, lat = to_ll.transform(
        mesh["mesh2d_face_x"].values, mesh["mesh2d_face_y"].values
    )
    # subtidal water only: a marsh cell is msk 1 and dry, and would drag the median to 0
    active = (run.msk == 1) & (run.z < WATER_ZMAX)
    swact = run.swm > 0
    bay = active & _inbox(lon, lat, BAY)
    d2 = {k: active & _inbox(lon, lat, b) for k, b in D2.items()}
    deep = swact & (run.z < -5.0)
    cora = xr.open_dataset(cora_path) if cora_path else None
    if cora is not None:
        cl, ca = cora["lon"].values, cora["lat"].values
        cnodes = {k: _inbox(cl, ca, b) for k, b in D2.items()}
    times = run.times if not hours else np.array([np.datetime64(h) for h in hours])
    rows = []
    for t in times:
        ds = run.at(t)
        if ds is None:
            continue
        hm0 = ds["hm0"].values.astype(float)
        bmax = float(np.nanmax(hm0[run.bnd]))
        r = dict(
            time=pd.Timestamp(t),
            bnd_max=round(bmax, 2),
            n_spike=int(np.nansum(swact & (hm0 > SPIKE_FACTOR * bmax))),
            n_gt6=int(np.nansum(swact & (hm0 > 6.0))),
            n_gt8=int(np.nansum(swact & (hm0 > 8.0))),
            field_max=round(float(np.nanmax(hm0[swact])), 2),
            bay_med=round(float(np.nanmedian(hm0[bay])), 3),
            bay_p99=round(float(np.nanpercentile(hm0[bay], 99)), 2),
        )
        for k, m in d2.items():
            r[k] = round(float(np.nanmedian(hm0[m])), 3)
        if cora is not None:
            hs = cora["hs"].sel(time=t, method="nearest").values
            for k, m in cnodes.items():
                r[f"cora_{k}"] = round(float(np.nanmedian(hs[m])), 3)
                r[f"d_{k}"] = round(r[k] - r[f"cora_{k}"], 3)
        if "hm0ig" in ds:
            ig = ds["hm0ig"].values.astype(float)
            sel = deep & (hm0 > 0.05)
            r["ig_ratio_p99"] = round(
                float(np.nanpercentile(ig[sel] / hm0[sel], 99)), 3
            )
            r["ig_max"] = round(float(np.nanmax(ig[swact])), 3)
            r["n_ig_gt1"] = int(np.nansum(swact & (ig > 1.0)))
        rows.append(r)
    return pd.DataFrame(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("run", type=Path)
    ap.add_argument("--hours", nargs="*")
    ap.add_argument("--no-cora", action="store_true")
    ap.add_argument("--csv", type=Path)
    a = ap.parse_args(argv)
    cora = None if a.no_cora else Path(_domain.active().cora_waves)
    df = census(a.run, a.hours, cora)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    print(f"{a.run.name}: {len(df)} hours; boxes BAY={BAY} D2={D2}")
    print(df.to_string(index=False))
    if a.csv:
        df.to_csv(a.csv, index=False)
        print(f"wrote {a.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
