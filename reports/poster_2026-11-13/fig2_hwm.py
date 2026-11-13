"""Poster Figure 2: modelled vs observed peak water at the USGS high-water marks (Model 1.1.0).

    python reports/poster_2026-11-13/fig2_hwm.py      (login node is fine: reads a CSV)

Per-mark values: ``hwm_per_mark_v110_native.csv`` (``hwm_per_mark.py``: the native 3.125 m
floodmap of the 11-12 re-score, job 63843110; pooled numbers reproduce that row exactly).
Estimator: median of the modelled water level over flooded pixels within 50 m of the mark.
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from poster_style import apply, save  # noqa: E402

NE = Path.home() / ".local/share/cartopy/shapefiles/natural_earth"

#: scorer basins (Domain.hwm_rules names) -> six poster regions, south to north
REGION = {
    "delaware_river": "Delaware Bay & River",
    "delaware_river_upper": "Delaware Bay & River",
    "delaware_bay_de": "Delaware Bay & River",
    "delaware_bay_nj_upper": "Delaware Bay & River",
    "delaware_bay_shore": "Delaware Bay & River",
    "cape_may": "Cape May to Atlantic City",
    "cape_may_back_bays": "Cape May to Atlantic City",
    "great_egg": "Cape May to Atlantic City",
    "absecon_atlantic_city": "Cape May to Atlantic City",
    "great_bay_mullica": "Mullica to Barnegat Bay",
    "lbi_barrier": "Mullica to Barnegat Bay",
    "barnegat_barrier": "Mullica to Barnegat Bay",
    "barnegat_bay": "Mullica to Barnegat Bay",
    "manasquan": "North Jersey Shore",
    "shark_river": "North Jersey Shore",
    "south_coast": "North Jersey Shore",
    "atlantic_oceanfront": "North Jersey Shore",
    "shrewsbury_navesink": "North Jersey Shore",
    "sandy_hook_bay": "Raritan Bay & Staten Island",
    "raritan_bay": "Raritan Bay & Staten Island",
    "raritan_river": "Raritan Bay & Staten Island",
    "lower_bay_si_shore": "Raritan Bay & Staten Island",
    "brooklyn_breezy": "Raritan Bay & Staten Island",
    "arthur_kill_nj": "Newark Bay & Arthur Kill",
    "newark_bay": "Newark Bay & Arthur Kill",
}
#: Okabe-Ito, fixed order; a marker shape per region so identity is not colour alone
STYLE = {
    "Delaware Bay & River": ("#CC79A7", "D"),
    "Cape May to Atlantic City": ("#E69F00", "s"),
    "Mullica to Barnegat Bay": ("#009E73", "^"),
    "North Jersey Shore": ("#56B4E9", "o"),
    "Raritan Bay & Staten Island": ("#0072B2", "v"),
    "Newark Bay & Arthur Kill": ("#D55E00", "P"),
}
EXTENT = (-75.65, -73.75, 38.75, 40.95)


def main():
    d = pd.read_csv(HERE / "hwm_per_mark_v110_native.csv", dtype={"hwm_id": str})
    d = d[d.scored].copy()
    d["region"] = d.basin.map(REGION)
    # 6130 is Wreck Pond (Spring Lake), mislabelled barnegat_bay by the v1 basin box
    # (FINDINGS: "6130 (Wreck Pond, mislabelled by the v1 basin box)"): place it by latitude
    d.loc[(d.basin == "barnegat_bay") & (d.lat > 40.1), "region"] = "North Jersey Shore"
    assert d.region.notna().all(), d.loc[d.region.isna(), "basin"].unique()
    r = d.resid_m.values
    n = len(r)
    rmse, bias = float(np.sqrt(np.mean(r**2))), float(np.mean(r))
    within = float(np.mean(np.abs(r) < 0.5))
    print(f"n {n} RMSE {rmse:.4f} bias {bias:+.4f} within0.5 {within:.4f}")

    apply()
    # Scatter only (user 11-12: the residual map read as "doing terribly"; the poster text
    # carries the description and the caption lives in README_fig1_fig2.md).
    # v4 poster: printed ~7.8 in wide in the Methods column, so these are printed sizes (user 11-13:
    # legend readable at print size)
    plt.rcParams.update({"xtick.labelsize": 17, "ytick.labelsize": 17, "axes.labelsize": 19})
    fig, ax = plt.subplots(figsize=(7.8, 9.4))

    # ---- (a) scatter --------------------------------------------------------------
    lo, hi = 0.5, 4.75
    ax.fill_between(
        [lo, hi], [lo - 0.5, hi - 0.5], [lo + 0.5, hi + 0.5],
        color="0.88", lw=0, zorder=0, label=r"within $\pm$0.5 m",
    )
    ax.plot([lo, hi], [lo, hi], color="0.25", lw=1.5, zorder=1, label="perfect (1:1)")
    for reg, (col, mk) in STYLE.items():
        s = d[d.region == reg]
        ax.scatter(
            s.obs_m, s.model_m, s=70, marker=mk, c=col, edgecolors="white",
            linewidths=0.8, zorder=3, label=f"{reg} ({len(s)})",
        )
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_aspect("equal")
    ax.set_xlabel("Observed high-water mark (m NAVD88)")
    ax.set_ylabel("Model peak water level (m NAVD88)")
    ax.text(
        0.04, 0.96,
        f"RMSE {rmse:.2f} m\nbias {bias:+.2f} m\n"
        f"{within * 100:.0f}% within $\\pm$0.5 m\nn = {n} marks".replace("-", "\u2212"),
        transform=ax.transAxes, va="top", ha="left", fontsize=21, fontweight="bold",
        linespacing=1.25,
    )
    ax.legend(
        loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2, fontsize=16,
        handletextpad=0.25, columnspacing=0.7, labelspacing=0.35, frameon=False,
    )

    save(fig, "fig2_hwm")


if __name__ == "__main__":
    main()
