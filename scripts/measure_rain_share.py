"""Ground-truth the FA rain classifier against the rain-off diagnostic run.

`validate/fa_decomp.py` labels a false-alarm pixel "disconnected" when its ever-wet
component never touches tidal water, and reads that as rain/runoff. The label is a
heuristic; `diag-premier-norain` — a byte-identical staging of `naccs-premier` minus
the `netamprfile` line — is its empirical check. A pixel wet in premier and dry in
norain got its water from rain (directly or as the trigger); one wet in both did not
need rain. The fa_decomp docstring promises this check.

PRE-REGISTERED DIAGNOSTIC (declared 2026-08-21, before the numbers were computed):

* Population: the false-alarm pixels of `naccs-premier` on the MOTF grid, under the
  same screens as `motf_metrics` (MOTF-valid AND model land AND simulated in BOTH
  runs AND outside the NJ-validity exclude boxes).
* Ground truth field: ``rain_true`` = dry in norain (``hmax < DEPTH_MIN`` or
  non-finite at the MOTF cell centre).
* Headline fields, named before computing:
  1. ``fa_rain_share``       — km² of FA with rain_true / km² of FA. This is "the
     measured rain share" FINDINGS §38-adjacent text will quote.
  2. ``disc_precision``      — P(rain_true | classifier says disconnected).
  3. ``disc_recall``         — P(classifier says disconnected | rain_true).
* The classifier is judged useful for its stated purpose (excusing rain FAs the
  reference cannot contain) primarily on ``disc_precision``; ``disc_recall`` low
  would mean it is conservative, which is the direction fa_decomp already claims.

⚠️ Wet/dry at DEPTH_MIN is a threshold on `zsmax`-derived depth; pixels within a few
cm of the threshold can flip for sub-hourly-sampling reasons unrelated to rain
(STATUS: the Raritan Bay `zsmax` band). Both runs here are waves-on premier physics,
so the band is expected to be far smaller than the premier-vs-nowaves case, but the
count of flip-marginal pixels is reported so the reader can see the exposure.

Usage:
    python scripts/measure_rain_share.py            # -> reports/rain/rain_share_<NJ_DOMAIN>.csv
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("NJ_DOMAIN", "v1_5_raritan")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import rasterio  # noqa: E402

from nj_sfincs.config import exp_root  # noqa: E402
from nj_sfincs.validate import DEPTH_MIN, load_floodmap, simulated_mask  # noqa: E402
from nj_sfincs.validate.fa_decomp import sea_connected  # noqa: E402
from nj_sfincs.validate.metrics import DATA, motf_exclude_mask, motf_path  # noqa: E402

PREMIER = "naccs-premier"
NORAIN = "diag-premier-norain"
#: |depth - DEPTH_MIN| below this counts as flip-marginal (reported, not screened).
MARGIN_M = 0.05


def _gather(da, rr, cc):
    a = da.values
    return (a[0] if a.ndim == 3 else a)[rr, cc]


def main() -> int:
    root = exp_root()
    with rasterio.open(str(motf_path(DATA))) as r:
        motf, mtf, m_nd = r.read(1), r.transform, r.nodata
    mh, mw = motf.shape
    Xc = mtf.c + (np.arange(mw) + 0.5) * mtf.a
    Yc = mtf.f + (np.arange(mh) + 0.5) * mtf.e

    hm = {}
    dep = None
    for name in (PREMIER, NORAIN):
        # load_floodmap builds the downscaled cache on first call (the "build the
        # norain floodmap cache" step) — atomic write, mtime-invalidated.
        _, hmax, d = load_floodmap(root / name, need_model=False, data_dir=DATA)
        if dep is None:
            dep = d
            mod_t = d.rio.transform()
            mc = np.clip(((Xc - mod_t.c) / mod_t.a).astype(int), 0, d.shape[-1] - 1)
            mr = np.clip(((Yc - mod_t.f) / mod_t.e).astype(int), 0, d.shape[-2] - 1)
            rr, cc = np.meshgrid(mr, mc, indexing="ij")
        hm[name] = _gather(hmax, rr, cc)

    dep_at = _gather(dep, rr, cc)
    wet_p = (hm[PREMIER] >= DEPTH_MIN) & np.isfinite(hm[PREMIER])
    wet_n = (hm[NORAIN] >= DEPTH_MIN) & np.isfinite(hm[NORAIN])

    land_in = (motf != m_nd) & (dep_at > 0.0)
    land_in &= simulated_mask(root / PREMIER, motf.shape, mtf)
    land_in &= simulated_mask(root / NORAIN, motf.shape, mtf)
    excl = motf_exclude_mask(motf.shape, mtf)
    if excl is not None:
        land_in &= ~excl

    motf_wet = motf == 1
    fa = ~motf_wet & wet_p & land_in
    rain_true = fa & ~wet_n
    disc = fa & ~sea_connected(wet_p, dep_at)

    km2 = abs(mtf.a * mtf.e) / 1e6
    n_fa, n_rt, n_d = int(fa.sum()), int(rain_true.sum()), int(disc.sum())
    n_d_rt = int((disc & rain_true).sum())
    # flip-marginal exposure: FA pixels whose premier depth sits within MARGIN_M of
    # the wet threshold — where sub-hourly sampling alone could flip wet/dry.
    n_marg = int((fa & (np.abs(hm[PREMIER] - DEPTH_MIN) < MARGIN_M)).sum())
    # rain share of the whole premier wet extent, for context beside the FA share
    wet_all = wet_p & land_in
    n_wet, n_wet_rain = int(wet_all.sum()), int((wet_all & ~wet_n).sum())

    out = {
        "fa_km2": n_fa * km2,
        "fa_rain_share": n_rt / n_fa if n_fa else float("nan"),
        "fa_rain_km2": n_rt * km2,
        "disc_precision": n_d_rt / n_d if n_d else float("nan"),
        "disc_recall": n_d_rt / n_rt if n_rt else float("nan"),
        "disc_km2": n_d * km2,
        "fa_flip_marginal_km2": n_marg * km2,
        "extent_km2": n_wet * km2,
        "extent_rain_share": n_wet_rain / n_wet if n_wet else float("nan"),
    }
    df = pd.DataFrame([out])
    # one file per domain (2026-09-03): the v3 run used to overwrite the v1.5 row
    dst = ROOT / "reports" / "rain" / f"rain_share_{os.environ['NJ_DOMAIN']}.csv"
    dst.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(dst, index=False)
    print(df.T.rename(columns={0: "value"}).to_string())
    print(f"\nwrote {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
