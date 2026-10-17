"""Which HWMs sit in a basin whose outlet the model holds shut? (``lake_outlet_blocked``)

The rule is in ``nj_sfincs/validate/lake_flag.py`` (module docstring); the scorer carries
it as ``*_excl_lake_blocked`` keys beside the headline. This is the LIGHT per-mark read
(~2 GB, ~40 s on v4's 4.9 M faces — no floodmap): every in-region mark of the active
domain, with the sea-side peak, the mark's sea-connection level and floor. A flag
column, never a filter.

``--marks`` joins a per-mark residual CSV (``v4_first_results.py`` ``marks/<label>.csv``:
``hwm_id``, ``scored``, ``resid_m``) and prints the headline with and without the
flagged marks (median, 50 m — whatever that file was scored with).

    NJ_DOMAIN=v4_refreeze PYTHONPATH=$PWD python scripts/lake_outlet_blocked.py \\
        experiments/v4_refreeze/naccs-premier \\
        [--marks reports/v4_first_results_2026-10-09/marks/rfw_on.csv]
    -> reports/lake_outlet_blocked_<domain>_<arm>.csv
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

import nj_sfincs  # noqa: F401,E402 — pyproj before hydromt
from nj_sfincs import domain as _domain  # noqa: E402
from nj_sfincs.validate import lake_flag  # noqa: E402
from nj_sfincs.validate.core import inp_value  # noqa: E402
from nj_sfincs.validate.metrics import HWM_RADIUS_M, _clip_to_region  # noqa: E402


def _headline(r: pd.Series) -> str:
    return (
        f"n={len(r)} RMSE={np.sqrt((r**2).mean()):.3f} bias={r.mean():+.3f} "
        f"within0.5={(r.abs() < 0.5).mean():.3f}"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("run", type=Path, help="a finished run dir")
    ap.add_argument("--marks", type=Path, help="a per-mark residual CSV to join")
    ap.add_argument("--radius", type=float, default=HWM_RADIUS_M)
    ap.add_argument("--sea-band", type=float, default=lake_flag.SEA_BAND_M)
    args = ap.parse_args()

    dom = _domain.active()
    epsg = int(float(inp_value(args.run / "sfincs.inp", "epsg")))
    hwm = _clip_to_region(gpd.read_file(dom.hwm_geojson).to_crs(epsg))
    df = lake_flag.lake_outlet_blocked(
        args.run,
        hwm.geometry.x.values,
        hwm.geometry.y.values,
        args.radius,
        args.sea_band,
    )
    out = pd.concat(
        [
            pd.DataFrame(
                {
                    "hwm_id": hwm["hwm_id"].astype(str),
                    "quality": hwm["quality"],
                    "basin": _domain.classify_hwm_basin(
                        hwm.geometry.x.values, hwm.geometry.y.values
                    ),
                    "elev_m": hwm["elev_m"],
                }
            ),
            df,
        ],
        axis=1,
    )
    if args.marks:
        m = pd.read_csv(args.marks, dtype={"hwm_id": str})[
            ["hwm_id", "scored", "resid_m"]
        ]
        out = out.merge(m, on="hwm_id", how="left")
    print(
        f"{dom.name} {args.run}: rule {lake_flag.rule_label(args.radius, args.sea_band)}"
    )
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(out[out.lake_outlet_blocked].round(3).to_string(index=False))
    if args.marks:
        s = out[out.scored.fillna(False).astype(bool)]
        print(f"\nheadline, all scored marks : {_headline(s.resid_m)}")
        print(
            f"excl lake_outlet_blocked   : {_headline(s.resid_m[~s.lake_outlet_blocked])}"
        )
    dst = ROOT / "reports" / f"lake_outlet_blocked_{dom.name}_{args.run.name}.csv"
    out.round(4).to_csv(dst, index=False)
    print(f"\nwrote {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
