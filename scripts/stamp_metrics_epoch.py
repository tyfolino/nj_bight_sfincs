#!/usr/bin/env python
"""Stamp the engine-epoch columns onto every EXISTING metrics row. Touches no number.

    NJ_DOMAIN=v3 python scripts/stamp_metrics_epoch.py            # dry run: prints the diff
    NJ_DOMAIN=v3 python scripts/stamp_metrics_epoch.py --apply    # writes, regenerates report

Written 2026-09-11 (plan Phase 3). ``run_experiments.collect_metrics`` stamps ``engine``,
``snapwave_direction`` and ``subgrid`` on every row it VALIDATES; rows scored before the
epoch have NaN there until this script fills them from the run dir (``engine.txt`` if
present, else the inp + ``sfincs.log`` Build-Revision, else ``_retired/<arm>`` once
``retire_arm.py`` exists). ``retired_to`` names the retired location when the arm dir is
gone. Every other column is asserted byte-identical before anything is written; the
dry run shows exactly which cells change.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import pandas as pd

from nj_sfincs import provenance
from nj_sfincs.config import exp_root

EPOCH_COLS = ("engine", "snapwave_direction", "subgrid", "retired_to")


def _arm_dir(root: Path, arm: str) -> tuple[Path | None, str]:
    d = root / arm
    if d.is_dir():
        return d, ""
    r = root / "_retired" / arm
    if r.is_dir():
        return r, f"_retired/{arm}"
    return None, ""


def stamp(df: pd.DataFrame, root: Path) -> pd.DataFrame:
    """Return a copy with the epoch columns filled for every row. Nothing else moves."""
    out = df.copy()
    for c in EPOCH_COLS:
        if c not in out.columns:
            out[c] = pd.NA
        out[c] = out[c].astype("object")
    for arm in out.index:
        d, retired = _arm_dir(root, str(arm))
        if d is None:
            out.loc[arm, "engine"] = "unknown (run dir gone)"
            out.loc[arm, "snapwave_direction"] = "unknown"
            out.loc[arm, "subgrid"] = "unknown"
            out.loc[arm, "retired_to"] = ""
            continue
        out.loc[arm, "engine"] = provenance.engine_label(d)
        out.loc[arm, "snapwave_direction"] = provenance.snapwave_direction(d)
        try:
            out.loc[arm, "subgrid"] = provenance.subgrid_label(d)
        except Exception as e:  # noqa: BLE001 — a label, never a blocker
            out.loc[arm, "subgrid"] = f"unavailable ({e})"
        out.loc[arm, "retired_to"] = retired
    return out


def diff(old: pd.DataFrame, new: pd.DataFrame) -> list[str]:
    """Human lines for every changed cell; raises if a NON-epoch cell changed."""
    lines = []
    for c in new.columns:
        if c in EPOCH_COLS:
            for arm in new.index:
                a = old[c][arm] if c in old.columns else None
                b = new[c][arm]
                a_na, b_na = bool(pd.isna(a)), bool(pd.isna(b))
                if (a_na and b_na) or (not a_na and not b_na and a == b):
                    continue
                lines.append(f"  {arm:<40} {c:<20} {a!r} -> {b!r}")
        else:
            if not old[c].equals(new[c]):
                raise AssertionError(f"non-epoch column {c!r} changed — refusing")
    return lines


def _text_diff(before: str, after: str) -> list[tuple[str, str]]:
    """(row, column) of every NON-epoch cell whose TEXT differs between two CSV bodies.
    Exact by construction: it compares the characters on disk, not parsed floats."""
    ra = list(csv.reader(before.splitlines()))
    rb = list(csv.reader(after.splitlines()))
    ha, hb = ra[0], rb[0]
    keep = [c for c in ha if c not in EPOCH_COLS]
    ia = {c: ha.index(c) for c in keep}
    ib = {c: hb.index(c) for c in keep}
    out = []
    for xa, xb in zip(ra[1:], rb[1:]):
        for c in keep:
            if xa[ia[c]] != xb[ib[c]]:
                out.append((xa[0], c))
    if len(ra) != len(rb):
        out.append(("<row count>", f"{len(ra)} vs {len(rb)}"))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument(
        "--root", type=Path, default=None, help="experiment root (default active)"
    )
    a = ap.parse_args(argv)
    root = a.root or exp_root()
    changed_any = False
    for name in ("metrics.csv", "bracket_metrics.csv"):
        csv = root / name
        if not csv.is_file():
            print(f"{csv}: absent, skipped")
            continue
        # round_trip: pandas' default fast float parser can be off by an ulp or two,
        # and to_csv then writes THAT value — a number changed by re-serialisation.
        old = pd.read_csv(csv, index_col=0, float_precision="round_trip")
        new = stamp(old, root)
        lines = diff(old, new)
        print(f"{csv}: {len(old)} rows, {len(lines)} cell(s) to stamp")
        for ln in lines:
            print(ln)
        if lines and a.apply:
            before = csv.read_text()
            tmp = csv.with_suffix(".csv.stamping")
            new.to_csv(tmp)
            bad = _text_diff(before, tmp.read_text())
            if bad:
                tmp.unlink()
                raise SystemExit(
                    f"REFUSING: re-serialisation changed non-epoch cell(s) {bad[:3]} — "
                    f"{csv} left untouched"
                )
            tmp.replace(csv)
            print(f"  wrote {csv} (every non-epoch cell byte-identical)")
            changed_any = changed_any or name == "metrics.csv"
    if a.apply and changed_any:
        from nj_sfincs import report

        df = pd.read_csv(root / "metrics.csv", index_col=0)
        out = report.generate_html_report(df, root)
        print(f"  regenerated {out}")
    elif not a.apply:
        print("dry run — pass --apply to write")
    return 0


if __name__ == "__main__":
    sys.exit(main())
