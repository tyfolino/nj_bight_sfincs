"""Apply check.py's current set-A severity rule to an existing CSV (no recomputation): link >= SURGE_CAP -> low."""
import sys
import pandas as pd
sys.path.insert(0, "/cache/home/tpj8/nj_bight_sfincs/logs/bed_audit_2026-11-05/checks/impoundment")
from check import SURGE_CAP
for f in sys.argv[1:]:
    d = pd.read_csv(f)
    k = (d.kind == "impounded_lake_tidal_link") & (d.severity == "medium") & (d.value >= SURGE_CAP)
    d.loc[k, "severity"] = "low"
    d.to_csv(f, index=False)
    print(f, "medium -> low:", int(k.sum()))
