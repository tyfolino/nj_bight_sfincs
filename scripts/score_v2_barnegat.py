"""Score the archived v2_barnegat runs to a CSV — so their maps become trimmable.

WHY (2026-08-20). The archive keeps five v2_barnegat `sfincs_map.nc` (8.79 GB) and
there is NO metrics.csv anywhere for them — their scores exist only as prose in the
archived campaign logs. Deleting the maps would make those five runs unre-scorable
forever (STATUS flagged this before the 2026-08-15 archive trim). Decision (user,
2026-08-20): score them to a CSV with the CURRENT scorer, bank it, then the maps go
on the deletion manifest.

WHAT IT DOES. Runs `validate.evaluate()` over each archived run dir IN PLACE
(`~/nj_coast_sfincs/experiments/v2_barnegat/…` — that tree is deliberately writable,
so the floodmap cache lands beside each map exactly as it would for a local run) and
writes `experiments/v2_barnegat/metrics.csv` LOCALLY. Nothing is staged, nothing
runs; the domain is registered `frozen=True` and build refuses it.

READ THE CSV WITH THESE IN MIND:
- Scored with the 2026-08-20 scorer: active-mask screen (FINDINGS §37), the
  `_scored` HWM keys, and the FA decomposition. The archived campaign prose was
  scored by the ARCHIVE's scorer — numbers are NOT expected to match it, and the
  current scorer is the one this CSV records.
- The five arms sit on THREE different fingerprints (pre-repair mask, post-repair
  mask, bed-ehydro carve) — the audit labels each; compare arms only within a
  fingerprint, and treat `BRACKET+…` as deliberately inadmissible (bracket=True).
- v2's MOTF sheet and 95-mark HWM file are the ARCHIVED defaults — both were built
  on the v2 bbox, so no per-domain override is needed (that is also why v1_monmouth
  could always score against them).

Usage:  NJ_DOMAIN=v2_barnegat python scripts/score_v2_barnegat.py
        (data/v2_barnegat_runs must be a gitignored link into the archive:
         `ln -s ../../nj_coast_sfincs/experiments/v2_barnegat data/v2_barnegat_runs`)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("NJ_DOMAIN", "v2_barnegat")

import pandas as pd  # noqa: E402

import nj_sfincs  # noqa: F401,E402 — pyproj-before-hydromt import order
from nj_sfincs import validate  # noqa: E402
from nj_sfincs.premier import BRACKET_PREFIX  # noqa: E402

# The archived runs, reached through a data/ symlink — the sanctioned route for
# archive material (tests/test_repo_hygiene.py). NOT experiments/<domain>: that tree
# is "LOCAL, never a symlink" by CLAUDE.md; these dirs are archive data now.
ARCHIVE_RUNS = ROOT / "data" / "v2_barnegat_runs"
OUT = ROOT / "experiments" / "v2_barnegat" / "metrics.csv"


def main() -> int:
    if os.environ.get("NJ_DOMAIN") != "v2_barnegat":
        sys.exit("run with NJ_DOMAIN=v2_barnegat")
    runs = sorted(
        d for d in ARCHIVE_RUNS.iterdir()
        if d.is_dir() and (d / "sfincs_map.nc").exists()
    )
    if not runs:
        sys.exit(f"no finished runs under {ARCHIVE_RUNS}")
    print(f"[score] {len(runs)} archived runs")

    rows = {}
    for d in runs:
        print(f"[score] {d.name} ...")
        row = validate.evaluate(d)
        row["domain"] = "v2_barnegat"
        row["archived_run_dir"] = str(d)
        # BRACKET+ arms are deliberately inadmissible bounds — kept and labeled,
        # never ranked against admissible arms (CLAUDE.md §6).
        row["bracket"] = d.name.startswith(BRACKET_PREFIX)
        rows[d.name] = row
        validate.cache_clear()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame.from_dict(rows, orient="index")
    tmp = OUT.with_suffix(".csv.tmp")
    df.to_csv(tmp)
    os.replace(tmp, OUT)
    print(f"[score] wrote {OUT} ({len(df)} rows, {len(df.columns)} keys)")
    cols = [c for c in ("hwm_rmse_scored_m", "hwm_bias_scored_m", "hwm_n_scored",
                        "motf_csi", "motf_pod", "motf_far", "bracket") if c in df]
    print(df[cols].to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
