"""Observed vs modelled water level at three interior gauges, 28-31 Oct 2012 (poster).

Model 1.1.0 (`p4-premier+weir-elizabeth-rahway` on `v4_refreeze_swz_v11`) from its
``sfincs_his.nc`` (10-min obs points), its waves-off twin `p4-nowaves` dashed, and the
observed series the scorer reads (``nj_sfincs.validate.metrics._obs_series``: same files,
same documented offsets). Observation gaps wider than the scorer's tolerance are left as
gaps, never bridged. Peak errors in the panel labels are the scorer's ``peak_err_*`` keys
from the native metrics rows (logs/floodmap_fix_2026-11-12/rows/), not recomputed.

Gauges: USGS 01408168 Barnegat Bay at Mantoloking, USGS 01392650 Newark Bay at PVSC,
NOAA 8545240 Philadelphia. NOAA Atlantic City was the first suggestion but is left out:
its open-ocean pier sits 4 km inside the forced boundary and its +0.5 m peak error is the
NACCS forcing (docs/FINDINGS.md), so it tests the boundary product, not the model.

Run from the repo root:
  NJ_DOMAIN=v4_refreeze_swz_v11 PYTHONPATH=$PWD python reports/poster_2026-11-13/fig_hydrographs.py
"""

import os
import sys
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from poster_style import C, apply, save  # noqa: E402

os.environ.setdefault("NJ_DOMAIN", "v4_refreeze_swz_v11")
from nj_sfincs import domain  # noqa: E402
from nj_sfincs.validate.metrics import _obs_series  # noqa: E402

EXP = Path("experiments/v4_refreeze_swz_v11")
RUN = EXP / "p4-premier+weir-elizabeth-rahway"
TWIN = EXP / "p4-nowaves"
ROW = Path(
    "logs/floodmap_fix_2026-11-12/rows/"
    "v4_refreeze_swz_v11__p4-premier+weir-elizabeth-rahway.csv"
)
GAUGES = [
    ("usgs_tidal_mantoloking", "Barnegat Bay at Mantoloking (USGS)"),
    ("usgs_tidal_newark_bay", "Newark Bay (USGS)"),
    ("noaa_philadelphia", "Delaware River at Philadelphia (NOAA)"),
]
# the run is 72 h from 10-28 00:00; its first ~12 h are spin-up (the rivers filling)
T0, T1 = pd.Timestamp("2012-10-28 12:00"), pd.Timestamp("2012-10-31 00:00")


def his(run: Path, name: str):
    h = xr.open_dataset(run / "sfincs_his.nc")
    names = [n.decode().strip() for n in h["station_name"].values]
    s = h["point_zs"].isel(stations=names.index(name))
    t = pd.to_datetime(h["time"].values)  # decoded from "seconds since 2012-10-28"
    return pd.Series(np.asarray(s.values, float), index=t)


def obs(name: str) -> pd.Series:
    g = next(x for x in domain.active().obs_gauges if x.name == name)
    t, v = _obs_series(g)
    s = pd.Series(v, index=pd.to_datetime(t)).dropna()
    s = s[(s.index >= T0) & (s.index <= T1)]
    # break the line across a gap (scorer's tolerance: max(3 x median step, 30 min))
    dt = s.index.to_series().diff().dt.total_seconds()
    tol = max(3 * float(np.nanmedian(dt)), 1800.0)
    gaps = s.index[dt > tol]
    if len(gaps):
        s = pd.concat([s, pd.Series(np.nan, index=gaps - pd.Timedelta(seconds=1))])
    return s.sort_index()


def main():
    apply()
    row = pd.read_csv(ROW).iloc[0]
    fig, axes = plt.subplots(3, 1, figsize=(11, 10), sharex=True)
    for ax, (n, label) in zip(axes, GAUGES):
        o = obs(n)
        m = his(RUN, n)
        w = his(TWIN, n)
        sel = (m.index >= T0) & (m.index <= T1)
        ax.plot(w.index[sel], w.values[sel], color="0.55", lw=1.6, ls="--",
                label="Model, no waves", zorder=2)
        ax.plot(m.index[sel], m.values[sel], color=C["model"], lw=2.4,
                label="Model", zorder=3)
        ax.plot(o.index, o.values, color=C["obs"], lw=1.8, label="Observed", zorder=4)
        err = float(row[f"peak_err_{n}_m"])
        ax.text(0.015, 0.94, label, transform=ax.transAxes, va="top", ha="left",
                fontsize=16, fontweight="bold")
        ax.text(0.015, 0.78, f"peak error {err:+.2f} m", transform=ax.transAxes,
                va="top", ha="left", fontsize=15)
        ax.set_ylabel("m NAVD88")
        ax.set_xlim(T0, T1)
        lo = np.nanmin(np.r_[o.values, m.values[sel]])
        hi = np.nanmax(np.r_[o.values, m.values[sel]])
        ax.set_ylim(np.floor(lo * 2) / 2, np.ceil(hi * 2) / 2 + 0.5)
    axes[0].legend(loc="upper right", frameon=False, ncol=3, fontsize=14)
    axes[-1].xaxis.set_major_locator(mdates.DayLocator())
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    axes[-1].xaxis.set_minor_locator(mdates.HourLocator(byhour=[6, 12, 18]))
    axes[-1].set_xlabel("2012 (UTC)")
    fig.align_ylabels(axes)
    fig.tight_layout(h_pad=0.6)
    save(fig, "fig_hydrographs")


if __name__ == "__main__":
    main()
