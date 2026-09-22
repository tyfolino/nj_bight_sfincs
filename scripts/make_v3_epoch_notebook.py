#!/usr/bin/env python
"""Write notebooks/v3/sandy-v3-viz-<date>.ipynb for the fixed-engine (winddir-fix) epoch.

Headers-only layout (a `##` title and the plot), first used by the 08-29 notebook of the
voided runs (removed 2026-09-21, in git history),
plus ONE table cell naming what each arm changes. The arm list is filtered at run time to
the arms that have BOTH a map and a metrics row, so the same notebook can be re-executed
as more arms land (e.g. `wave-apex`) without editing.

    python scripts/make_v3_epoch_notebook.py            # writes the .ipynb (unexecuted)
    jupyter nbconvert --to notebook --execute --inplace notebooks/v3/sandy-v3-viz-2026-09-14.ipynb

Single-run variant (2026-09-20, the wavemaker premier candidate): ``--date`` names the
file, ``--arm LABEL=arm`` (repeatable) replaces the candidate list, ``--table`` a markdown
file whose text replaces the arms table, ``--anim-run`` the run the animations show.

    python scripts/make_v3_epoch_notebook.py --date 2026-09-20 \
        --arm "wave-wavemaker=wave-wavemaker" --table notebooks/v3/table_2026-09-20.md
"""

import argparse
from pathlib import Path

import nbformat as nbf

DATE = "2026-09-14"
NB_DIR = Path(__file__).resolve().parents[1] / "notebooks" / "v3"

SETUP = """import os
from pathlib import Path

os.environ["NJ_DOMAIN"] = "v3"  # must precede the nj_sfincs import

import sys

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "nj_sfincs").is_dir())
sys.path.insert(0, str(ROOT))

import pandas as pd
from IPython.display import Image, display

from nj_sfincs import animate, domain, plots

DOM = domain.active()
EXP = ROOT / "experiments" / DOM.name
FIGS = ROOT / "reports" / "figures"
TAG = "{DATE}"

# The fixed-engine epoch (native v2.3.3 + nj-winddir-fix-1). Keys are the panel labels.
# Filtered below to the arms that have both a map and a scored metrics row, so this
# notebook re-executes cleanly as later arms land.
CANDIDATES = {
{CANDIDATES}}
_m = pd.read_csv(EXP / "metrics.csv", index_col=0)
RUNS = {k: v for k, v in CANDIDATES.items()
        if (EXP / v / "sfincs_map.nc").exists() and v in _m.index}
NCOL = {NCOL}

print(DOM.name, "|", sorted(DOM.map_windows))
print("in this notebook:", list(RUNS))
print("not yet scored:", [k for k in CANDIDATES if k not in RUNS])
"""

ARMS_TABLE = """## Arms — every run in this notebook is on the fixed engine (`bin:v2.3.3-winddir-fix-1`, waves launched in the imposed direction); one row = one change from the premier

| arm | wind growth | `snapwave_fw` | IG waves | buildings in subgrid | SnapWave band | what it isolates |
|---|---|---|---|---|---|---|
| `naccs-premier` | on | 0.01 | on | yes | shelf-steps | the baseline |
| `wave-noig` | on | 0.01 | **off** | yes | shelf-steps | infragravity waves |
| `wave-fw02` | on | **0.02** | on | yes | shelf-steps | bottom friction (the old value) |
| `bed-nobuildings` | on | 0.01 | on | **no** | shelf-steps | the building-footprint tier |
| `naccs-nowaves` | – | – | – | yes | – | SnapWave altogether |
| `wave-apex` | on | 0.01 | on | yes | **extended north to Rockaway** | swell supply into Lower Bay |
| `wave-wavemaker` | on | 0.01 | on **+ injected at a −5 m wavemaker line** (build `igk-fix-1`) | yes | apex | the IG lever (FINDINGS §45/§49) |
"""

METRICS = """csv = EXP / "metrics.csv"
m = pd.read_csv(csv, index_col=0).loc[list(RUNS.values())]
HEADLINE = [
    "hwm_n_scored", "hwm_rmse_scored_m", "hwm_bias_scored_m",
    "hwm_within0.5_scored", "motf_csi", "motf_pod", "motf_far",
    "motf_far_connected", "motf_csi_connected", "motf_km2_excluded_boxes",
    "engine", "snapwave_direction", "subgrid",
]
display(m[[c for c in HEADLINE if c in m.columns]].round(3))
"""

GAUGE_METRICS = """m = pd.read_csv(EXP / "metrics.csv", index_col=0).loc[list(RUNS.values())]

COLS = {
    "peak_obs": "peak_obs_{n}_m",
    "peak_mod": "peak_mod_full_{n}_m",
    "peak_err": "peak_err_{n}_m",
    "peak_lag_min": "peak_lag_{n}_min",
    "tide_obs_rng": "tide_obs_range_{n}_m",
    "tide_mod_rng": "tide_mod_range_{n}_m",
    "tide_damping": "tide_range_damping_{n}_m",
    "phase_lag_min": "phase_lag_{n}_min",
}

rows = []
for arm in m.index:
    for g in DOM.obs_gauges:
        r = {"arm": arm, "gauge": g.name, "kind": g.kind,
             "crest": "survives" if g.survives_crest else "DIED"}
        for label, pat in COLS.items():
            k = pat.format(n=g.name)
            r[label] = m.loc[arm, k] if k in m.columns else float("nan")
        k = f"peak_err_prefail_{g.name}_m"
        if k in m.columns:
            r["peak_err"] = m.loc[arm, k]
            r["crest"] = "DIED (prefail)"
        rows.append(r)

gm = pd.DataFrame(rows).set_index(["gauge", "kind", "crest", "arm"]).round(3)
display(gm)
"""


def anim(run, var, window):
    return f'''anim = animate.animate_field("{run}", "{var}", window="{window}", fps=6)
p = FIGS / f"v3_{var}_{window}_{{TAG}}.gif"
anim.save(p, writer="pillow", fps=6, dpi=90)
display(Image(filename=str(p)))
'''


INTERACTIVE = """import holoviews as hv
import ipywidgets as widgets

hv.extension("bokeh")


@widgets.interact(
    run=list(RUNS.values()),
    var=["depth", "zs", "hm0", "tp"],
    window=sorted(DOM.map_windows),
)
def browse(run="{ANIM_RUN}", var="depth", window="absecon"):
    display(animate.explore_field(run, var=var, window=window))
"""


DEFAULT_CANDIDATES = {
    "naccs-premier (apex band)": "naccs-premier",
    # the four old-band arms were retired 2026-09-21 (maps gone) — the 09-17 render
    # that carried them is pushed; pass --arm to add any live arm
    "naccs-nowaves": "naccs-nowaves",
    "wavemaker (IG at the −5 m line)": "wave-wavemaker",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=DATE)
    ap.add_argument(
        "--arm", action="append", default=None, help="LABEL=arm (repeatable)"
    )
    ap.add_argument(
        "--table", default=None, help="markdown file replacing the arms table"
    )
    ap.add_argument("--anim-run", default="naccs-premier")
    ap.add_argument("--ncol", type=int, default=None)
    a = ap.parse_args()
    cands = (
        DEFAULT_CANDIDATES if a.arm is None else dict(x.split("=", 1) for x in a.arm)
    )
    ncol = a.ncol or (3 if len(cands) > 2 else len(cands))
    out = NB_DIR / f"sandy-v3-viz-{a.date}.ipynb"
    cand_lines = "".join(f'    "{k}": "{v}",\n' for k, v in cands.items())
    setup = (
        SETUP.replace("{CANDIDATES}", cand_lines)
        .replace("{NCOL}", str(ncol))
        .replace("{DATE}", a.date)
    )
    table = Path(a.table).read_text() if a.table else ARMS_TABLE
    single = len(cands) == 1
    nb = nbf.v4.new_notebook()
    c = nb.cells
    c.append(nbf.v4.new_code_cell(setup))
    c.append(nbf.v4.new_markdown_cell(table))
    first = next(iter(cands.values()))
    c.append(
        nbf.v4.new_markdown_cell(
            "## Water-level boundary — forced cells + NACCS support"
        )
    )
    c.append(
        nbf.v4.new_code_cell(
            f'plots.plot_waterlevel_boundary_panels({{"{first}": "{first}"}}, ncol=1);'
        )
    )
    c.append(nbf.v4.new_markdown_cell("## Metrics"))
    c.append(nbf.v4.new_code_cell(METRICS))
    c.append(
        nbf.v4.new_markdown_cell(
            "## Gauges — ⚠️ Ship Bottom · Sea Isle · Stone Harbor obs peaks are pre-storm gap artefacts; "
            "Sandy Hook died mid-storm (read its pre-failure peak)"
            + (
                "; the Sea Bright storm-tide sensor sits ON wavemaker piece 9 and reads the surf zone"
                if single
                else ""
            )
        )
    )
    c.append(nbf.v4.new_code_cell("plots.plot_gauge_verification(RUNS, ncol=NCOL);"))
    c.append(
        nbf.v4.new_markdown_cell(
            "## Gauge metrics — `tide` gauges: read range/phase. `surge` gauges: read peak."
        )
    )
    c.append(nbf.v4.new_code_cell(GAUGE_METRICS))
    c.append(
        nbf.v4.new_markdown_cell(
            "## HWM — ⚠️ bay marks carry ±0.3 m of seiche PHASE between arms (FINDINGS §40); "
            "compare arms PAIRED, never by pooled RMSE alone"
        )
    )
    c.append(nbf.v4.new_code_cell("plots.plot_hwm_residual_panels(RUNS, ncol=NCOL);"))
    c.append(
        nbf.v4.new_markdown_cell(
            "## MOTF — a storm-tide surface interpolated from marks, not a runup map: beach-face swash scores as a false alarm by construction"
            if single
            else "## MOTF — `naccs-nowaves` is a legitimate configuration but its extent is not ranked "
            "against waves-on arms; buildings arms dry their footprints (compare on the masked CSI)"
        )
    )
    c.append(
        nbf.v4.new_code_cell("plots.plot_motf_panels(RUNS, ncol=NCOL, split_fa=True);")
    )
    c.append(nbf.v4.new_markdown_cell(f"## Animations — `{a.anim_run}`"))
    c.append(nbf.v4.new_code_cell(anim(a.anim_run, "depth", "raritan")))
    c.append(nbf.v4.new_code_cell(anim(a.anim_run, "depth", "cape_may")))
    c.append(nbf.v4.new_code_cell(anim(a.anim_run, "hm0", "cape_may")))
    if a.anim_run != "naccs-premier":
        c.append(nbf.v4.new_code_cell(anim(a.anim_run, "depth", "sandy_hook")))
    c.append(nbf.v4.new_markdown_cell("## Interactive — pick a run, field, window"))
    c.append(nbf.v4.new_code_cell(INTERACTIVE.replace("{ANIM_RUN}", a.anim_run)))
    nb.metadata["kernelspec"] = {
        "name": "python3",
        "display_name": "Python 3",
        "language": "python",
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    nbf.write(nb, out)
    print(f"wrote {out} ({len(c)} cells)")


if __name__ == "__main__":
    main()
