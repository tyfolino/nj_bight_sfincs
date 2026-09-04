"""MOTF CSI / POD / FAR with BUILDING FOOTPRINT pixels masked out of BOTH rasters.

Why this exists (STATUS 09-04, pre-registration item 3): a ``bed-*`` arm with footprints
burned into its subgrid is DRY on every footprint pixel of its downscaled floodmap (the
bed there is ground + 4 m), while the FEMA MOTF sheet is an HWM surface interpolated
over bare earth and paints those same pixels WET. So the raw CSI of a buildings arm
drops by construction — a POD loss the size of the footprint share of the wet land —
and says nothing about whether the water went to the right streets. The fair extent
comparison removes footprint pixels from the scored set for EVERY arm, including the
premier, and is quoted BESIDE the raw number, never instead of it (CLAUDE.md §6: flag,
never delete a computed number).

The screen is the tier itself (``bed_buildings_v3``, valid = footprint) sampled at the
MOTF pixel centres, so "footprint" here means exactly the pixels the buildings arm
raised. Everything else replicates ``validate.metrics.motf_metrics`` — same floodmap
sampling, ``simulated_mask``, ``motf_exclude_mask`` and ``DEPTH_MIN`` — and the raw
column is asserted to reproduce ``metrics.csv`` to 4 places, so a drift in either is
caught.

    NJ_DOMAIN=v3 PYTHONPATH=$PWD python scripts/motf_csi_buildings_masked.py \
        naccs-premier bed-buildings [--out experiments/v3/motf_csi_buildings_masked.csv]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pyproj  # noqa: F401,E402
import rasterio  # noqa: E402
from rasterio.enums import Resampling  # noqa: E402
from rasterio.vrt import WarpedVRT  # noqa: E402

from nj_sfincs import domain as _domain  # noqa: E402
from nj_sfincs.config import DATA, exp_root  # noqa: E402
from nj_sfincs.validate.core import load_floodmap, simulated_mask  # noqa: E402
from nj_sfincs.validate.metrics import (  # noqa: E402
    DEPTH_MIN,
    motf_exclude_mask,
    motf_path,
)

TIER = DATA / "elevation_v3" / "bed_buildings_v3.tif"


def footprint_on_motf(motf_shape, mtf, crs) -> np.ndarray:
    """True where the building tier is valid at the MOTF pixel centre (nearest)."""
    with rasterio.open(TIER) as t:
        with WarpedVRT(t, crs=crs, transform=mtf, width=motf_shape[1],
                       height=motf_shape[0], resampling=Resampling.nearest) as v:
            a = v.read(1)
        return (a != t.nodata) & np.isfinite(a)


def _rates(nh, nm, nf):
    return {
        "csi": nh / (nh + nm + nf) if (nh + nm + nf) else float("nan"),
        "pod": nh / (nh + nm) if (nh + nm) else float("nan"),
        "far": nf / (nh + nf) if (nh + nf) else float("nan"),
        "n_hit": nh, "n_miss": nm, "n_fa": nf,
    }


def score(arm: str, motf, mtf, m_nd, crs, fp) -> dict:
    model_dir = exp_root() / arm
    _, da_hmax, da_dep = load_floodmap(model_dir, data_dir=DATA)
    mod_t = da_dep.rio.transform()
    mh, mw = motf.shape
    Xc = mtf.c + (np.arange(mw) + 0.5) * mtf.a
    Yc = mtf.f + (np.arange(mh) + 0.5) * mtf.e
    mc = np.clip(((Xc - mod_t.c) / mod_t.a).astype(int), 0, da_dep.shape[-1] - 1)
    mr = np.clip(((Yc - mod_t.f) / mod_t.e).astype(int), 0, da_dep.shape[-2] - 1)
    rr, cc = np.meshgrid(mr, mc, indexing="ij")

    def _2d(a):
        return a[0] if a.ndim == 3 else a

    dep_at, h_at = _2d(da_dep.values)[rr, cc], _2d(da_hmax.values)[rr, cc]
    motf_wet = motf == 1
    mod_wet = (h_at >= DEPTH_MIN) & np.isfinite(h_at)
    land_in = (motf != m_nd) & (dep_at > 0.0) & simulated_mask(model_dir, motf.shape, mtf)
    excl = motf_exclude_mask(motf.shape, mtf)
    if excl is not None:
        land_in &= ~excl
    km2 = abs(mtf.a * mtf.e) / 1e6

    raw = _rates(int((motf_wet & mod_wet & land_in).sum()),
                 int((motf_wet & ~mod_wet & land_in).sum()),
                 int((~motf_wet & mod_wet & land_in).sum()))
    keep = land_in & ~fp
    msk = _rates(int((motf_wet & mod_wet & keep).sum()),
                 int((motf_wet & ~mod_wet & keep).sum()),
                 int((~motf_wet & mod_wet & keep).sum()))
    row = {"arm": arm}
    row.update({f"raw_{k}": v for k, v in raw.items()})
    row.update({f"masked_{k}": v for k, v in msk.items()})
    row["footprint_km2_in_scored_land"] = float((land_in & fp).sum() * km2)
    row["footprint_share_of_scored_land"] = float((land_in & fp).sum() / land_in.sum())
    row["footprint_share_of_motf_wet_land"] = float(
        (land_in & fp & motf_wet).sum() / (land_in & motf_wet).sum()
    )
    row["footprint_motfwet_modeldry_km2"] = float((land_in & fp & motf_wet & ~mod_wet).sum() * km2)
    return row


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("arms", nargs="+")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    dom = _domain.active()
    with rasterio.open(str(motf_path(DATA))) as r:
        motf, mtf, m_nd, crs = r.read(1), r.transform, r.nodata, r.crs
    fp = footprint_on_motf(motf.shape, mtf, crs)
    print(f"[{dom.name}] MOTF grid {motf.shape} @ {abs(mtf.a):.2f} m; footprint pixels "
          f"{int(fp.sum())} = {fp.sum() * abs(mtf.a * mtf.e) / 1e6:.1f} km²")

    rows = [score(a, motf, mtf, m_nd, crs, fp) for a in args.arms]
    df = pd.DataFrame(rows).set_index("arm")
    # consistency with the scorer's own column
    mcsv = exp_root() / "metrics.csv"
    if mcsv.exists():
        m = pd.read_csv(mcsv, index_col=0)
        for a in df.index:
            if a in m.index and np.isfinite(m.loc[a, "motf_csi"]):
                d = abs(float(m.loc[a, "motf_csi"]) - df.loc[a, "raw_csi"])
                flag = "" if d < 5e-4 else "   ** DIFFERS FROM metrics.csv **"
                print(f"  {a}: raw CSI {df.loc[a, 'raw_csi']:.4f} vs metrics.csv "
                      f"{m.loc[a, 'motf_csi']:.4f}{flag}")
    cols = ["raw_csi", "raw_pod", "raw_far", "masked_csi", "masked_pod", "masked_far",
            "footprint_share_of_scored_land", "footprint_share_of_motf_wet_land",
            "footprint_motfwet_modeldry_km2"]
    print(df[cols].round(4).to_string())
    out = Path(args.out) if args.out else exp_root() / "motf_csi_buildings_masked.csv"
    df.to_csv(out)
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
