#!/usr/bin/env python
"""Score the NACCS forcing product against the interior USGS storm-tide sensors.

    python scripts/check_naccs_vs_sensors.py

WHAT THIS IS, AND WHAT IT IS NOT
--------------------------------

🔴 This is a **FORCING-PRODUCT DIAGNOSTIC, never a model diagnostic.** No SFINCS run is
involved. It asks one question: at the interior points where we have observations, does
the NACCS/CHS ADCIRC product itself reproduce the observed water level?

That matters *before* a mesh is built, because every arm inherits this product. If NACCS
cannot reproduce Raritan Bay's interior, no boundary placement will rescue it — and the
tidal-amplification argument in FINDINGS §2 would be resting on harmonics alone.

⚠️ **The NACCS nodes compared here are INTERIOR nodes, not boundary support points.** On
v1.5 this water is COMPUTED, so these nodes never force anything. They are being used as a
stand-in for "what does the source product think the interior does". A good score here does
NOT mean the boundary is right, and a bad one does not condemn it.

⚠️ Read this beside the sensor's distance to the nearest node. A 3 km separation inside a
bay with a real along-basin gradient is a genuine mismatch term, not model error.

Datum: NACCS is MSL(1992); sensors are NAVD88. Converted per node through the same
`_vdatum` path the builder uses, so this diagnostic and the forcing file cannot drift
apart. Steric is already applied in the released series — do not re-add it.
"""

from __future__ import annotations

import math
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_naccs_boundary import _vdatum, read_zips  # noqa: E402

SENSORS = ROOT / "data" / "gtsm" / "sandy_storm_tide_raritan.nc"
OUT = ROOT / "reports" / "naccs"
#: Figures go to reports/figures/ (gitignored); scored CSVs are tracked.
FIG = ROOT / "reports" / "figures"

#: Sandy's crest. Used only to split "peak" from "the rest", never to trim the series.
CREST = (pd.Timestamp("2012-10-29 12:00"), pd.Timestamp("2012-10-30 12:00"))

#: 🔴 A save point must be genuinely WET to stand in for open-bay water. NACCS ships
#: nodes with NEGATIVE depth (above datum — marsh, bank, dry). Chosen with margin, not
#: at a knife edge: the wet nodes near these sensors sit at 1.3-4.0 m, the rejected one
#: at -1.25 m, so anything from ~0.1 to ~1.0 m gives the same selection.
MIN_NODE_DEPTH_M = 0.5

#: dataviz categorical slots 1-2 (see references/palette.md).
C_OBS, C_MOD = "#2a78d6", "#eb6834"

ROLE = {
    2255: "holdout, 4.67 km from an arm",
    2295: "holdout, 8.85 km from an arm",
    2294: "forcing-adjacent, 1.67 km",
    2291: "forcing-adjacent, 0.87 km",
    2270: "marginal, 3.46 km",
}


def _m(lat1, lon1, lat2, lon2) -> float:
    return math.hypot((lat1 - lat2) * 111_320.0,
                      (lon1 - lon2) * 111_320.0 * math.cos(math.radians(lat1)))


def naccs_series(pts, times, sp) -> pd.Series:
    """One save point's Sandy series, MSL(1992) -> NAVD88, as a pandas Series."""
    rec = pts[sp]
    off = _vdatum(rec["lon"], rec["lat"])
    idx = pd.to_datetime([datetime.strptime(str(t), "%Y%m%d%H%M") for t in times])
    return pd.Series(np.asarray(rec["wl"], dtype="float64") + off, index=idx)


def main() -> None:
    print("[naccs] parsing save points ...")
    pts = read_zips(use_cache=True)
    times = pts.pop("_times")

    ds = xr.open_dataset(SENSORS)
    rows, panels = [], []

    for k, sid in enumerate(ds["stations"].values):
        slon = float(ds["lon"].values[k])
        slat = float(ds["lat"].values[k])
        obs = pd.Series(ds["stormtide_m"].values[:, k],
                        index=pd.to_datetime(ds["time"].values)).dropna()
        if obs.empty:
            continue

        # ⚠️ Nearest node is NOT good enough: NACCS carries save points with NEGATIVE
        # depth (above datum — marsh and bank nodes). The nearest node to 2255 is at
        # -1.25 m and behaves nothing like the open bay, which read as a +1.7 m model
        # error that was really a node-choice error. Require a genuinely wet node.
        wet = [p for p in pts if pts[p]["depth"] >= MIN_NODE_DEPTH_M]
        sp = min(wet, key=lambda p: _m(slat, slon, pts[p]["lat"], pts[p]["lon"]))
        dist = _m(slat, slon, pts[sp]["lat"], pts[sp]["lon"])
        raw = min(pts, key=lambda p: _m(slat, slon, pts[p]["lat"], pts[p]["lon"]))
        if raw != sp:
            print(f"  [{sid}] nearest node {raw} is {pts[raw]['depth']:+.2f} m deep "
                  f"— skipped for wet node {sp} ({pts[sp]['depth']:+.2f} m)")
        mod = naccs_series(pts, times, sp)

        # Compare on the OBSERVED clock: NACCS is 15-min, the sensors 6-min after the
        # downloader's resample. Interpolating the model onto the observation is the
        # honest direction -- it never invents an observation.
        both = pd.concat([obs.rename("obs"),
                          mod.reindex(obs.index.union(mod.index))
                             .interpolate("time").rename("mod")],
                         axis=1, sort=True).loc[obs.index]
        both = both.dropna()
        if both.empty:
            continue

        crest = both.loc[CREST[0]:CREST[1]]
        pk_o = crest["obs"].max() if not crest.empty else np.nan
        pk_m = crest["mod"].max() if not crest.empty else np.nan
        lag = ((crest["mod"].idxmax() - crest["obs"].idxmax()).total_seconds() / 60
               if not crest.empty else np.nan)
        # Range over the whole overlap: both series carry tide AND surge, so this is a
        # like-for-like comparison and needs no tide/surge separation.
        rows.append(dict(
            sid=int(sid), role=ROLE.get(int(sid), ""), node=sp,
            dist_km=dist / 1000, depth_m=pts[sp]["depth"],
            n=len(both), bias_m=(both["mod"] - both["obs"]).mean(),
            rmse_m=float(np.sqrt(((both["mod"] - both["obs"]) ** 2).mean())),
            peak_obs=pk_o, peak_mod=pk_m, peak_err=pk_m - pk_o, lag_min=lag,
            range_obs=both["obs"].max() - both["obs"].min(),
            range_mod=both["mod"].max() - both["mod"].min(),
        ))
        panels.append((int(sid), both, dist))

    df = pd.DataFrame(rows).sort_values("dist_km", ascending=False)
    pd.set_option("display.width", 200)
    print("\nNACCS interior nodes vs USGS storm-tide sensors (NAVD88, m):")
    print(df.to_string(index=False, float_format=lambda v: f"{v:7.3f}"))

    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / "naccs_vs_sensors.csv", index=False)
    print(f"\n[csv ] {OUT / 'naccs_vs_sensors.csv'}")
    plot(panels, df, FIG / "naccs_vs_sensors.png")


def plot(panels, df, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    n = len(panels)
    fig, axes = plt.subplots(n, 1, figsize=(11, 2.5 * n), dpi=160, sharex=True)
    fig.patch.set_facecolor("#fcfcfb")
    axes = np.atleast_1d(axes)

    for ax, (sid, both, dist) in zip(axes, panels):
        ax.set_facecolor("#fcfcfb")
        ax.plot(both.index, both["obs"], color=C_OBS, lw=2.0, label="USGS sensor")
        ax.plot(both.index, both["mod"], color=C_MOD, lw=2.0, label="NACCS node")
        r = df[df.sid == sid].iloc[0]
        ax.set_title(
            f"{sid} — {ROLE.get(sid, '')} · node {r.node} at {dist / 1000:.2f} km · "
            f"bias {r.bias_m:+.3f} m · peak err {r.peak_err:+.3f} m · lag {r.lag_min:+.0f} min",
            fontsize=9, loc="left", color="#0b0b0b")
        ax.grid(True, color="#e8e7e0", lw=0.6)
        for s in ax.spines.values():
            s.set_color("#d5d4cc")
        ax.tick_params(colors="#52514e", labelsize=8)
        ax.set_ylabel("m NAVD88", fontsize=8, color="#52514e")

    axes[0].legend(loc="upper left", frameon=True, facecolor="#fcfcfb",
                   edgecolor="#d5d4cc", fontsize=8)
    fig.suptitle("NACCS/CHS ADCIRC vs interior USGS storm-tide sensors — "
                 "a FORCING-product check, not a model check",
                 fontsize=12, color="#0b0b0b", x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.985))
    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"[plot] {path}")


if __name__ == "__main__":
    main()
