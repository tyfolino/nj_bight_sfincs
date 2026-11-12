"""Shared look for the Rutgers climate poster figures (2026-11-13).

Every figure script does ``from poster_style import apply, save, C`` and calls ``apply()``
before plotting and ``save(fig, "figN_name")`` at the end (300 dpi PNG + vector PDF).

Sizes assume each figure is printed ~10-12 in wide on the poster, read from ~1.5 m:
nothing below 14 pt.
"""

from pathlib import Path

import matplotlib as mpl

OUT = Path(__file__).resolve().parent

#: Colour-blind-safe (Okabe-Ito) roles, used the same way in every figure.
C = {
    "model": "#0072B2",  # blue: the model
    "obs": "#000000",  # black: observations
    "hit": "#0072B2",  # MOTF: both wet
    "miss": "#E69F00",  # MOTF: observed wet, model dry
    "false": "#CC79A7",  # MOTF: model wet, observed dry
    "wet": "#D55E00",  # an asset that floods
    "dry": "#999999",  # an asset that stays dry
    "accent": "#009E73",
    "land": "#F2F0EB",
    "water": "#DCE9F2",
    "boundary": "#D55E00",
    "grid": "#BBBBBB",
}


def apply():
    """SciencePlots' journal look (user 11-12: "just for the poster"), scaled up for a poster.

    ``science`` + ``no-latex`` (no LaTeX on the cluster): serif type, ticks in, minor ticks,
    all four spines. Its sizes are for a 3.5 in journal column, so the font sizes are
    overridden here; keep ``figsize`` explicit in each script (~10-12 in wide).
    """
    import matplotlib.pyplot as plt
    import scienceplots  # noqa: F401  (registers the styles; conda-forge, sfincs env)

    plt.style.use(["science", "no-latex"])
    mpl.rcParams.update(
        {
            "font.size": 16,
            "axes.titlesize": 20,
            "axes.labelsize": 17,
            "xtick.labelsize": 14,
            "ytick.labelsize": 14,
            "legend.fontsize": 14,
            "lines.linewidth": 2.0,
            "lines.markersize": 7,
            "axes.linewidth": 1.0,
            "xtick.major.size": 6,
            "ytick.major.size": 6,
            "xtick.minor.size": 3,
            "ytick.minor.size": 3,
            "figure.dpi": 100,
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
            "pdf.fonttype": 42,
        }
    )


def save(fig, stem):
    for ext in ("png", "pdf"):
        fig.savefig(OUT / f"{stem}.{ext}")
    print("wrote", OUT / f"{stem}.png")
