#!/usr/bin/env python
"""CLAUDE.md §5 check: Model 1.1.0's Domain (v4_refreeze_swz_v11) vs nj2, field by field.

    python logs/nj2_freeze_2026-11-14/domain_diff.py > logs/nj2_freeze_2026-11-14/domain_diff.txt

Every dataclass field; tuples of named things (arms, walls, boxes, gauges, rules) diffed BY NAME
(added / dropped / changed, with the changed values); the inflow list (discharge + wall-source
catalog keys, by point name); the refinement polygon lists by name (v4's vs nj2's file, when the
latter exists). Read-only.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from nj_sfincs import domain as D


def _name(x):
    if hasattr(x, "name"):
        return x.name
    if isinstance(x, tuple) and x and isinstance(x[0], str):
        return x[0]
    return None


def _short(v, n=140):
    s = repr(v)
    return s if len(s) <= n else s[: n - 3] + "..."


def diff_named(a, b):
    na = {_name(x): x for x in a}
    nb = {_name(x): x for x in b}
    out = []
    for k in na.keys() - nb.keys():
        out.append(f"    - DROPPED {k}")
    for k in nb.keys() - na.keys():
        x = nb[k]
        out.append(f"    + ADDED   {k}: {_short(getattr(x, 'box', x[1] if isinstance(x, tuple) else x))}")
    for k in sorted(na.keys() & nb.keys(), key=str):
        if na[k] != nb[k]:
            xa, xb = na[k], nb[k]
            if dataclasses.is_dataclass(xa):
                ch = [f.name for f in dataclasses.fields(xa) if getattr(xa, f.name) != getattr(xb, f.name)]
                out.append(f"    ~ CHANGED {k}: fields {ch}")
            else:
                out.append(f"    ~ CHANGED {k}: {_short(xa, 80)} -> {_short(xb, 80)}")
    if [_name(x) for x in a if _name(x) in nb] != [_name(x) for x in b if _name(x) in na]:
        out.append("    (order of the shared entries differs)")
    return out


def geodataset_names(key):
    import yaml

    cat = yaml.safe_load((D.DATA / "data_catalog.yml").read_text())
    p = D.DATA / cat[key]["uri"]
    try:
        import xarray as xr

        with xr.open_dataset(p) as ds:
            idx = [c for c in ds.coords if c not in ("time", "x", "y", "lon", "lat")]
            return p, [str(v) for v in ds[idx[0]].values] if idx else None
    except Exception as e:  # noqa: BLE001
        return p, f"unreadable: {e}"


def refinement_names(path: Path | None):
    if path is None or not Path(path).exists():
        return None
    gj = json.loads(Path(path).read_text())
    return [f["properties"].get("name") for f in gj["features"]]


def main() -> int:
    a, b = D.V4_REFREEZE_SWZ_V11, D.DOMAINS["nj2"]
    print(f"# {a.name} (Model 1.1.0) -> {b.name}\n")
    same = []
    for f in dataclasses.fields(a):
        va, vb = getattr(a, f.name), getattr(b, f.name)
        if va == vb:
            same.append(f.name)
            continue
        print(f"## {f.name}")
        if isinstance(va, tuple) and (va or vb) and all(_name(x) for x in (*va, *vb)):
            print("\n".join(diff_named(va, vb)) or "    (same names, same values; order differs)")
        elif isinstance(va, dict):
            for k in va.keys() | vb.keys():
                if va.get(k) != vb.get(k):
                    print(f"    {k}: {va.get(k)} -> {vb.get(k)}")
        else:
            print(f"    {_short(va)}\n -> {_short(vb)}")
    print(f"\n## UNCHANGED ({len(same)}): {', '.join(same)}")
    print("\n## inflows (catalog keys unchanged; points by name)")
    for key in {a.discharge_geodataset, a.wall_sources_geodataset} | {b.discharge_geodataset, b.wall_sources_geodataset}:
        p, names = geodataset_names(key)
        print(f"    {key}: {p.name}: {len(names) if isinstance(names, list) else names} points")
    print("\n## refinement polygons by name")
    ra, rb = refinement_names(a.refinement), refinement_names(b.refinement)
    print(f"    {a.name}: {a.refinement.name}: {len(ra) if ra else ra} polygons")
    if rb is None:
        print(f"    {b.name}: {b.refinement} NOT DELIVERED YET — re-run this script when it is")
    else:
        print(f"    {b.name}: {b.refinement.name}: {len(rb)} polygons")
        from collections import Counter

        ca, cb = Counter(ra), Counter(rb)
        print(f"    dropped names: {sorted(set(ra) - set(rb), key=str)}")
        print(f"    added names:   {sorted(set(rb) - set(ra), key=str)}")
        print("    count changed (name: v1.1.0 -> nj2): "
              + str({k: (ca[k], cb[k]) for k in ca.keys() & cb.keys() if ca[k] != cb[k]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
