#!/usr/bin/env python
"""Rewrite the x / y of a staged dir's gridded meteo files to the ENGINE's convention.

SFINCS v2.3.3 reads the first x / y of ``sfincs_netamuv.nc`` / ``sfincs_netamp.nc`` /
``sfincs_netampr.nc`` as a cell CORNER; hydromt writes CENTRES, so every model point
samples wind, pressure and rain half a cell W and N of itself (12.5 km + 12.5 km on
ERA5). The fix writes ``centre - signed step/2`` (nj_sfincs/meteo_grid.py; data
untouched, idempotent, atomic). ``model.finalize`` applies it on every staging since
2026-10-06; this applies it to a template or staged dir that predates that, because arm
staging COPIES the template's forcing.

    python scripts/fix_meteo_grid_origin.py --check <dir>...   # READ-ONLY; exit 1 if any
                                                             #   file still needs the fix
    python scripts/fix_meteo_grid_origin.py <dir>...           # fix (no-op when done)
    python scripts/fix_meteo_grid_origin.py --era5-bilinear <dir>...
        # ALSO rewrite wind + pressure from native ERA5 by bilinear interpolation in
        # lon/lat on a --res (5000 m) UTM grid instead of hydromt's nearest-cell copy
        # (logs/raritan_2026-10-06/meteo_fix/README.md). Refuses a wind_scale arm.

Never point it at a run dir with output you mean to keep comparable: it changes the
forcing the solver reads.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nj_sfincs import meteo_grid  # noqa: E402


def _era5_path() -> Path:
    import yaml

    cat = yaml.safe_load((ROOT / "data" / "data_catalog.yml").read_text())
    return ROOT / "data" / cat["era5_nj"]["uri"]


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("dirs", nargs="+", type=Path)
    ap.add_argument("--check", action="store_true", help="read-only report")
    ap.add_argument(
        "--era5-bilinear",
        action="store_true",
        help="rewrite netamuv + netamp from native ERA5 (bilinear in lon/lat)",
    )
    ap.add_argument(
        "--res", type=float, default=5000.0, help="--era5-bilinear grid (m)"
    )
    ap.add_argument("--era5", type=Path, default=None, help="default: catalog era5_nj")
    a = ap.parse_args()
    if a.check and a.era5_bilinear:
        ap.error("--check is read-only; drop --era5-bilinear")

    need = 0
    for d in a.dirs:
        if not (d / "sfincs.inp").is_file():
            print(f"{d}: no sfincs.inp — not a model dir", file=sys.stderr)
            return 2
        print(f"== {d}")
        if a.era5_bilinear:
            era5 = a.era5 or _era5_path()
            info = meteo_grid.write_era5_bilinear(d, era5, res_m=a.res)
            print(
                f"  ERA5 bilinear -> {info['nx']}x{info['ny']} @ {info['res_m']:.0f} m, "
                f"x {info['x'][0]:.0f}..{info['x'][1]:.0f}, "
                f"y {info['y'][0]:.0f}..{info['y'][1]:.0f}; source: {info['source_check']}"
            )
        states = meteo_grid.fix_meteo_grid_origin(d, check=a.check)
        if not states:
            print("  no gridded meteo files")
        print(meteo_grid.describe(states))
        need += sum(s["action"] == "NEEDS FIX" for s in states)
        for f, (bad, n) in meteo_grid.active_faces_outside_band(d).items():
            flag = "  ⚠️ the engine ZEROES these" if bad else ""
            print(
                f"  {f:<20} active faces outside the engine's band: {bad:,} of {n:,}{flag}"
            )
    if a.check and need:
        print(f"{need} file(s) NEED the fix")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
