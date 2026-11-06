"""Bed audit runner: run every check under logs/bed_audit_2026-11-05/checks/ on one bed, merge, rank, summarise.

Each check is `checks/<name>/check.py` (folders starting with "_" are helpers) and writes
`out/<label>/<name>.csv` in the shared columns of logs/bed_audit_2026-11-05/SCHEMA.md. This script runs them
(or only reads what is there with --collect-only), merges exceptions that point at the same place (within 30 m,
keeping every check's name), ranks them by severity, then by Sandy relevance (near a power asset, then the Sandy
peak), and writes `out/<label>/exceptions.csv` + a plain-English `out/<label>/AUDIT.md`.

    python scripts/bed_audit.py --bed experiments/v4_refreeze_swz/_subgrid_v1_1b --label v1_1b
    python scripts/bed_audit.py --bed experiments/v4_refreeze_swz/_subgrid_modern2026 --label modern \\
        --overlay-min v11_deck_npz
    python scripts/bed_audit.py --label v1_1b --collect-only            # re-merge without re-running
    python scripts/bed_audit.py --compare v1_1b modern                  # what is new / gone between two beds
    python scripts/bed_audit.py --compare p100 v1_1b --checks anomaly_flat,anomaly_profile   # ... for some checks

--checks a,b limits the run; --overlay-min / --overlay pass through to every check (a stand-in for a bed not
built yet). The bed rasters are ROTATED; every check samples them through the affine.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer

REPO = Path(__file__).resolve().parents[1]
AUD = REPO / "logs/bed_audit_2026-11-05"
SEV = {"high": 0, "medium": 1, "low": 2}
TO_UTM = Transformer.from_crs(4326, 32618, always_xy=True).transform
MERGE_M = 30.0


def md_table(df):
    """A small markdown table without the optional `tabulate` package."""
    if df is None or len(df) == 0:
        return "(none)"
    df = df.reset_index()
    head = "| " + " | ".join(map(str, df.columns)) + " |"
    rule = "|" + "---|" * len(df.columns)
    body = ["| " + " | ".join(map(str, r)) + " |" for r in df.itertuples(index=False)]
    return "\n".join([head, rule, *body])


def checks_present(only=None):
    out = sorted(p.parent.name for p in (AUD / "checks").glob("*/check.py") if not p.parent.name.startswith("_"))
    return [c for c in out if not only or c in only]


def run(a):
    names = checks_present(a.checks.split(",") if a.checks else None)
    (AUD / "out" / a.label).mkdir(parents=True, exist_ok=True)
    for nm in names:
        cmd = [sys.executable, str(AUD / "checks" / nm / "check.py"), "--bed", str(a.bed), "--label", a.label,
               "--out", str(AUD / "out" / a.label / f"{nm}.csv")]
        for k in a.overlay_min:
            cmd += ["--overlay-min", k]
        for k in a.overlay:
            cmd += ["--overlay", k]
        t0 = time.time()
        print(f"== {nm}", flush=True)
        r = subprocess.run(cmd, check=False)
        print(f"   {nm}: exit {r.returncode}, {time.time() - t0:.0f} s", flush=True)


def load(label):
    d = AUD / "out" / label
    frames = []
    for f in sorted(d.glob("*.csv")):
        if f.name == "exceptions.csv":
            continue
        try:
            x = pd.read_csv(f, dtype={"id": str})
        except pd.errors.EmptyDataError:
            continue
        miss = {"check", "lon", "lat", "severity"} - set(x.columns)
        if miss:
            print(f"  skipped {f.name}: not in SCHEMA.md's columns (missing {sorted(miss)})")
            continue
        if len(x):
            x["file"] = f.stem
            frames.append(x)
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    bad = ~(np.isfinite(pd.to_numeric(df.lon, errors="coerce")) & np.isfinite(pd.to_numeric(df.lat, errors="coerce")))
    if bad.any():
        print(f"  {int(bad.sum())} exceptions without coordinates dropped from the merge: "
              f"{df[bad].check.value_counts().to_dict()}")
    return df[~bad].astype({"lon": float, "lat": float})


def merge(df):
    """Union exceptions within MERGE_M of each other; keep the most severe row, list every check."""
    from scipy.sparse.csgraph import connected_components  # noqa: PLC0415
    from scipy.spatial import cKDTree  # noqa: PLC0415

    x, y = TO_UTM(df.lon.values, df.lat.values)
    pairs = cKDTree(np.c_[x, y]).query_pairs(MERGE_M, output_type="ndarray")
    from scipy.sparse import coo_matrix  # noqa: PLC0415

    n = len(df)
    g = coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(n, n)) if len(pairs) else coo_matrix((n, n))
    _, lab = connected_components(g, directed=False)
    df = df.assign(cluster=lab, _sev=df.severity.map(SEV).fillna(3),
                   _asset=pd.to_numeric(df.asset_km, errors="coerce").fillna(99),
                   _peak=pd.to_numeric(df.sandy_peak_m, errors="coerce").fillna(-99))
    df = df.sort_values(["_sev", "_asset", "_peak"], ascending=[True, True, False])
    agg = df.groupby("cluster").agg(checks=("check", lambda s: ";".join(sorted(set(s)))),
                                    kinds=("kind", lambda s: ";".join(sorted(set(s)))), n_rows=("check", "size"))
    top = df.drop_duplicates("cluster").set_index("cluster").join(agg).reset_index()
    top["n_checks"] = top.checks.str.count(";") + 1
    top = top.sort_values(["_sev", "n_checks", "_asset", "_peak"], ascending=[True, False, True, False])
    return top.drop(columns=["_sev", "_asset", "_peak", "file"], errors="ignore")


def collect(label):
    raw = load(label)
    d = AUD / "out" / label
    if raw.empty:
        print("no exceptions found")
        return
    top = merge(raw)
    top.to_csv(d / "exceptions.csv", index=False)
    ct = raw.pivot_table(index="check", columns="severity", values="id", aggfunc="count", fill_value=0)
    ct = ct.reindex(columns=[c for c in ["high", "medium", "low"] if c in ct.columns])
    lines = [f"# Bed audit: `{label}`", "",
             f"{len(raw):,} exceptions from {raw.check.nunique()} checks, {len(top):,} places after merging those "
             f"within {MERGE_M:.0f} m. Severity first; then places several checks agree on; then near a power asset; "
             "then the Sandy peak. Columns and rules: SCHEMA.md and each check's README / docstring.", "",
             "## Counts (check × severity, before merging)", "", md_table(ct), "",
             "## Top 30 places", "",
             "| # | sev | checks | where | what |", "|---|---|---|---|---|"]
    for i, r in enumerate(top.head(30).itertuples(), start=1):
        asset = f" · {r.near_asset} {r.asset_km} km" if isinstance(r.near_asset, str) and r.near_asset else ""
        lines.append(f"| {i} | {r.severity} | {r.checks} | {r.lon:.4f}, {r.lat:.4f}{asset} | {r.note} |")
    (d / "AUDIT.md").write_text("\n".join(lines) + "\n")
    print(f"wrote {d / 'exceptions.csv'} ({len(top):,} places) and {d / 'AUDIT.md'}")


def compare(la, lb, only=None):
    A = pd.read_csv(AUD / "out" / la / "exceptions.csv", low_memory=False)
    B = pd.read_csv(AUD / "out" / lb / "exceptions.csv", low_memory=False)
    if only:
        A, B = (d[d.checks.astype(str).apply(lambda c: bool(set(c.split(";")) & set(only)))] for d in (A, B))
    from scipy.spatial import cKDTree  # noqa: PLC0415

    def xy(d):
        return np.c_[TO_UTM(d.lon.values, d.lat.values)]

    def unmatched(P, Q):
        if len(Q) == 0:
            return np.ones(len(P), bool)
        dist, j = cKDTree(xy(Q)).query(xy(P), distance_upper_bound=MERGE_M)
        ok = np.isfinite(dist)
        same = np.zeros(len(P), bool)
        same[ok] = [bool(set(str(P.kinds.iloc[i]).split(";")) & set(str(Q.kinds.iloc[j[i]]).split(";")))
                    for i in np.where(ok)[0]]
        return ~same

    gone, new = A[unmatched(A, B)], B[unmatched(B, A)]
    out = AUD / "out" / (f"compare_{la}_vs_{lb}" + ("_" + "_".join(sorted(only)) if only and len(only) < 3 else
                                                    ("_subset" if only else "")))
    gone.assign(change="gone").to_csv(str(out) + "_gone.csv", index=False)
    new.assign(change="new").to_csv(str(out) + "_new.csv", index=False)
    lines = [f"# {la} → {lb}", "", f"{len(A):,} places in {la}, {len(B):,} in {lb}: **{len(gone):,} gone** "
             f"(in {la} only — fixed, or not found by {lb}'s checks) and **{len(new):,} new** (in {lb} only).", ""]
    for nm, d in (("gone", gone), ("new", new)):
        ct = d.groupby(["checks", "severity"]).size().unstack(fill_value=0) if len(d) else pd.DataFrame()
        lines += [f"## {nm}", "", md_table(ct), "", "Top 15:", ""]
        for r in d.head(15).itertuples():
            lines.append(f"- {r.severity} · {r.checks} · {r.lon:.4f}, {r.lat:.4f} · {r.note}")
        lines.append("")
    Path(str(out) + ".md").write_text("\n".join(lines))
    print(f"wrote {out}.md: {len(gone)} gone, {len(new)} new")


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--bed", type=Path)
    ap.add_argument("--label")
    ap.add_argument("--checks", help="comma-separated check names (default: all present)")
    ap.add_argument("--overlay-min", action="append", default=[])
    ap.add_argument("--overlay", action="append", default=[])
    ap.add_argument("--collect-only", action="store_true")
    ap.add_argument("--compare", nargs=2, metavar=("LABEL_A", "LABEL_B"))
    a = ap.parse_args()
    if a.compare:
        compare(*a.compare, only=a.checks.split(",") if a.checks else None)
        return
    if not a.label:
        ap.error("--label is required")
    if not a.collect_only:
        if a.bed is None:
            ap.error("--bed is required unless --collect-only / --compare")
        a.bed = a.bed if a.bed.is_absolute() else (REPO / a.bed)
        run(a)
    collect(a.label)


if __name__ == "__main__":
    main()
