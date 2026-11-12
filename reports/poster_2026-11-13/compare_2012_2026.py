"""NJ power assets: Sandy on the 2012 bed (Model 1.1.0) vs the 2026 bed. Counts + every site that changes state.

    python compare_2012_2026.py    (reads exposure/v110_2012bed_assets.csv, exposure/v11_modernb_2026bed_assets.csv)
    -> stdout + exposure/changes_2012_vs_2026.csv
"""

from pathlib import Path

import pandas as pd

E = Path(__file__).resolve().parent / "exposure"
a = pd.read_csv(E / "v110_2012bed_assets.csv", index_col="asset")
b = pd.read_csv(E / "v11_modernb_2026bed_assets.csv", index_col="asset")
cols = ["state", "wet_share", "depth_median", "depth_max", "level_median", "ground_median"]
j = a[["klass", "name", "county", "us_state", "kv_max", "mw"] + cols].join(
    b[cols], lsuffix="_2012", rsuffix="_2026"
)
nj = j[j.us_state == "NJ"]
for k in ("2012", "2026"):
    s = nj[f"state_{k}"].replace({"on_water": "dry"})
    s = s[s != "out_of_model"]
    print(f"NJ {k} bed: {s.value_counts().to_dict()}  (n = {len(s)})")
for klass in ("plant", "substation"):
    t = nj[nj.klass == klass]
    print(
        f"  {klass}s wet: 2012 {int((t.state_2012 == 'wet').sum())} -> 2026 {int((t.state_2026 == 'wet').sum())}"
    )
s12 = nj.state_2012.replace({"on_water": "dry"})
s26 = nj.state_2026.replace({"on_water": "dry"})
ch = nj[s12 != s26].copy()
ch["dlevel"] = (ch.level_median_2026 - ch.level_median_2012).round(3)
ch["dground"] = (ch.ground_median_2026 - ch.ground_median_2012).round(3)
print(f"\nNJ sites that change state ({len(ch)}):")
with pd.option_context("display.width", 250, "display.max_columns", 30, "display.max_rows", 200):
    print(
        ch[["klass", "name", "county", "kv_max", "mw", "state_2012", "state_2026", "wet_share_2012",
            "wet_share_2026", "depth_max_2012", "depth_max_2026", "dlevel", "dground"]]
    )
both = nj[(s12 == "wet") & (s26 == "wet")]
d = (both.depth_median_2026 - both.depth_median_2012).dropna()
print(f"\nwet on both beds: {len(both)}; median-depth change: median {d.median():+.3f} m, "
      f"> +0.1 m at {int((d > 0.1).sum())}, < -0.1 m at {int((d < -0.1).sum())}")
j.to_csv(E / "changes_2012_vs_2026.csv")
