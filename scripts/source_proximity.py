"""Which HWMs and gauges sit close enough to a river inflow to read the INJECTION?

CLAUDE.md §5 / FINDINGS §40: a station or mark within ~500 m of a discharge source reads
the source, not the basin (v1.5's `rb_axis_559k`, 253 m from the Raritan source, carried a
single-face 1.33 m `zsmax` spike its neighbours did not share). It is a PER-DOMAIN fact,
so it is re-measured on every new domain — v3 (08-27, by hand): 1 of 185 marks, HWM 6044,
49 m from the Absecon Creek source.

Reads the STAGED sources (``sfincs_netsrcdisfile.nc`` — the positions after snapping,
which is where the water enters), names them by the nearest point of the domain's
discharge dataset, and measures every in-region HWM and every ``sfincs.obs`` gauge
against them. A flag column, never a filter: the user judges what to do with a mark.

    NJ_DOMAIN=v4 PYTHONPATH=$PWD python scripts/source_proximity.py \
        [--run experiments/v4/_template_sealed] [--radius 500]
    -> reports/source_proximity_<domain>.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import geopandas as gpd  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import xarray as xr  # noqa: E402
import yaml  # noqa: E402
from pyproj import Transformer  # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402

import nj_sfincs  # noqa: F401,E402 — pyproj before hydromt
from nj_sfincs import domain as _domain  # noqa: E402
from nj_sfincs.config import BaseConfig, exp_root  # noqa: E402

SRC_RADIUS_M = 500.0  # CLAUDE.md §5, FINDINGS §40


def staged_sources(run: Path, dom) -> pd.DataFrame:
    """Staged source positions, peak Q over the file, and the USGS id of each."""
    with xr.open_dataset(run / "sfincs_netsrcdisfile.nc") as s:
        x, y = s["x"].values, s["y"].values
        qmax = s["discharge"].max("time").values
    cat = yaml.safe_load((ROOT / "data" / "data_catalog.yml").read_text())
    with xr.open_dataset(ROOT / "data" / cat[dom.discharge_geodataset]["uri"]) as d:
        ids = d["index"].values
        X, Y = Transformer.from_crs(4326, dom.epsg, always_xy=True).transform(
            d["lon"].values, d["lat"].values
        )
    snap, k = cKDTree(np.c_[X, Y]).query(np.c_[x, y])
    return pd.DataFrame(
        {"x": x, "y": y, "qmax": qmax, "usgs_id": ids[k], "snap_m": snap.round(1)}
    )


def measure(px, py, src: pd.DataFrame, radius: float) -> pd.DataFrame:
    d, k = cKDTree(src[["x", "y"]].to_numpy()).query(np.c_[px, py])
    near = src.iloc[k].reset_index(drop=True)
    return pd.DataFrame(
        {
            "dist_nearest_src_m": d.round(1),
            "nearest_src_usgs": near["usgs_id"].astype(str).str.zfill(8),
            "nearest_src_qmax_m3s": near["qmax"].round(1),
            "src_contaminated": d < radius,
        }
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--run",
        type=Path,
        default=None,
        help="a STAGED dir (default: the active domain's template)",
    )
    ap.add_argument("--radius", type=float, default=SRC_RADIUS_M)
    args = ap.parse_args()

    dom = _domain.active()
    run = args.run or exp_root() / "_template_sealed"
    src = staged_sources(run, dom)
    print(
        f"{dom.name}: {len(src)} staged sources from {run}; matched to the discharge "
        f"dataset within {src.snap_m.max():.0f} m (max)"
    )

    hwm = gpd.read_file(dom.hwm_geojson).to_crs(dom.epsg)
    reg = gpd.read_file(BaseConfig().region).to_crs(dom.epsg).geometry.iloc[0]
    hwm = hwm[hwm.geometry.within(reg)].reset_index(drop=True)
    hx, hy = hwm.geometry.x.values, hwm.geometry.y.values
    h = pd.concat(
        [
            pd.DataFrame(
                {
                    "kind": "hwm",
                    "name": hwm["hwm_id"].astype(str),
                    "quality": hwm["quality"],
                    "basin": _domain.classify_hwm_basin(hx, hy),
                    "x": hx,
                    "y": hy,
                }
            ),
            measure(hx, hy, src, args.radius),
        ],
        axis=1,
    )

    obs = pd.read_csv(
        run / "sfincs.obs",
        sep=r"\s+",
        header=None,
        names=["x", "y", "name"],
        quotechar='"',
    )
    g = pd.concat(
        [
            obs.assign(kind="gauge", quality=np.nan, basin="")[
                ["kind", "name", "quality", "basin", "x", "y"]
            ],
            measure(obs.x.values, obs.y.values, src, args.radius),
        ],
        axis=1,
    )

    out = pd.concat([h, g], ignore_index=True).sort_values("dist_nearest_src_m")
    lon, lat = Transformer.from_crs(dom.epsg, 4326, always_xy=True).transform(
        out.x.values, out.y.values
    )
    out.insert(4, "lon", np.round(lon, 5))
    out.insert(5, "lat", np.round(lat, 5))
    dst = ROOT / "reports" / f"source_proximity_{dom.name}.csv"
    out.drop(columns=["x", "y"]).to_csv(dst, index=False)

    for kind, n in (("hwm", len(h)), ("gauge", len(g))):
        sub = out[out.kind == kind]
        hit = sub[sub.src_contaminated]
        print(f"\n{kind}s: {len(hit)} of {n} within {args.radius:.0f} m of a source")
        cols = [
            "name",
            "quality",
            "basin",
            "lon",
            "lat",
            "dist_nearest_src_m",
            "nearest_src_usgs",
            "nearest_src_qmax_m3s",
        ]
        print(sub.head(max(len(hit), 5))[cols].to_string(index=False))
    print(f"\nwrote {dst}")


if __name__ == "__main__":
    main()
