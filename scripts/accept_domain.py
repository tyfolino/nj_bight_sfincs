#!/usr/bin/env python
"""ONE command that answers "is this domain fit to run?" — read-only, ~20 s.

    NJ_DOMAIN=v1_5_raritan python scripts/accept_domain.py
    NJ_DOMAIN=v1_5_raritan python scripts/accept_domain.py --figures   # + regenerate plots

Exit code 0 = every check passed. Non-zero = at least one FAILED. Nothing is written
except figures under `--figures`; no mesh is built, no run directory is touched.

WHY THIS EXISTS
---------------
On 2026-08-14 this domain was brought from "builds green" to "fit to freeze" — and every
real defect found that day was found by ME LOOKING, not by an assert:

  * `cudem_nj` was missing the Ward Point headland and backfilling it as bay water, which
    split the `arthur_kill` arm into two runs. Every invariant was green.
  * 14,141 active cells sat outside the drawn region. Every invariant was green.
  * The `arthur_kill` bracket was [15..300] while the arm was 59 cells and should have
    been 24, so the bracket admitted the defect it existed to catch.

Each of those became a permanent check (invariant 8, the region re-clip,
`sweep_cudem_flatfill.py`, tighter brackets). But they were still spread across six
commands and two figures that a person had to remember to run and read.

🔴 THAT is the failure this file addresses. A check nobody runs is worth nothing, and a
check that costs a day of a person's attention gets skipped exactly when the schedule is
tight — which is when it matters. So: one command, one table, one exit code.

WHAT IT DOES NOT DO
-------------------
It does not replace looking at the boundary figure before a freeze. It automates every
check that CAN be automated and tells you, explicitly, the one thing that still cannot be:
whether the boundary is where you MEANT it. `--figures` regenerates the plots so that
judgement is at least made against current output rather than a stale PNG.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import nj_sfincs  # noqa: F401,E402  (PROJ primer — must precede hydromt_sfincs)
from nj_sfincs import domain as _domain  # noqa: E402
from nj_sfincs import premier  # noqa: E402
from nj_sfincs.config import BaseConfig  # noqa: E402

PASS, FAIL, WARN, SKIP = "PASS", "FAIL", "WARN", "SKIP"

#: Bed above this and a gauge only wets near the crest. A note, not a defect — see
#: `check_obs`. Storm-tide sensors are deliberately mounted above normal water.
HIGH_GROUND_M = 1.0


class Report:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str]] = []

    def add(self, status: str, check: str, detail: str = "") -> None:
        self.rows.append((status, check, detail))
        mark = {PASS: "✅", FAIL: "🔴", WARN: "⚠️ ", SKIP: "· "}[status]
        print(f"  {mark} {check:38s} {detail}")

    @property
    def failed(self) -> int:
        return sum(1 for s, _, _ in self.rows if s == FAIL)


def _mesh_arrays(mesh_dir: Path):
    """(x, y, z, mask) from a frozen mesh, without instantiating a full SfincsModel."""
    import xarray as xr

    ds = xr.open_dataset(mesh_dir / "sfincs.nc")
    # UGRID naming: face centres are mesh2d_face_x/y, NOT x/y (which do not exist).
    x = np.asarray(ds["mesh2d_face_x"].values, float)
    y = np.asarray(ds["mesh2d_face_y"].values, float)
    z = np.asarray(ds["z"].values, float)
    mask = np.asarray(ds["mask"].values)
    ds.close()
    return x, y, z, mask


def check_fingerprint(rep: Report, dom, mesh_dir: Path) -> None:
    want = premier.EXPECTED.get(dom.name)
    if want is None:
        rep.add(FAIL, "fingerprint registered", f"{dom.name} not in premier.EXPECTED")
        return
    got = premier.domain_fingerprint(mesh_dir)
    if got == want:
        rep.add(PASS, "fingerprint matches EXPECTED", str(got))
    else:
        rep.add(FAIL, "fingerprint matches EXPECTED", f"got {got}, want {want}")
    label = premier.KNOWN.get(got)
    rep.add(PASS if label else FAIL, "fingerprint is in KNOWN",
            label or "UNRECOGNISED — audits will read as a real domain error")


def check_region_containment(rep: Report, x, y, mask) -> None:
    import geopandas as gpd
    import shapely

    reg = gpd.read_file(BaseConfig().region).to_crs(_domain.active().epsg)
    out = ~shapely.contains_xy(reg.geometry.iloc[0], x, y)
    bad = []
    for v, lbl in ((1, "active"), (2, "waterlevel BC"), (3, "outflow BC")):
        n = int(((mask == v) & out).sum())
        if n:
            bad.append(f"{lbl}={n}")
    if bad:
        rep.add(FAIL, "no mask outside the drawn region", ", ".join(bad))
    else:
        rep.add(PASS, "no mask outside the drawn region",
                f"{int((mask > 0).sum()):,} active cells, all inside")


def check_arms(rep: Report, dom, x, y, z, mask) -> None:
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    from scipy.spatial import cKDTree

    if not dom.boundary_arms:
        rep.add(SKIP, "boundary arms", "none declared")
        return
    claimed = np.zeros(len(mask), dtype=bool)
    for arm in dom.boundary_arms:
        x0, y0, x1, y1 = arm.box
        want = 2 if arm.btype == "waterlevel" else 3
        sel = (mask == want) & (x > x0) & (x < x1) & (y > y0) & (y < y1)
        claimed |= sel
        n = int(sel.sum())
        ok = arm.min_cells <= n <= arm.max_cells
        wet = float(np.nanmax(z[sel])) if n else float("nan")
        # how many disconnected runs?
        runs = 0
        if n:
            P = np.c_[x[sel], y[sel]]
            pr = cKDTree(P).query_pairs(125, output_type="ndarray")
            g = coo_matrix((np.ones(len(pr)), (pr[:, 0], pr[:, 1])), shape=(n, n))
            runs, _ = connected_components(g, directed=False)
        detail = (f"{n} cells [{arm.min_cells}..{arm.max_cells}], {runs} run(s), "
                  f"max bed {wet:+.2f}")
        rep.add(PASS if ok else FAIL, f"arm {arm.name}", detail)
        if n and wet > arm.max_bed_m:
            rep.add(FAIL, f"arm {arm.name} all wet",
                    f"max bed {wet:+.2f} > {arm.max_bed_m}")
    orphan = int(((mask == 2) & ~claimed).sum())
    rep.add(PASS if orphan == 0 else FAIL, "no mask==2 outside every arm", f"{orphan}")


def check_dry_land(rep: Report, dom, x, y, z) -> None:
    from nj_sfincs.model import check_dry_land_boxes

    if not dom.dry_land_boxes_ll:
        rep.add(WARN, "dry-land boxes", "none declared — bed correctness NOT checked")
        return
    fails = check_dry_land_boxes(dom.dry_land_boxes_ll, f"EPSG:{dom.epsg}", x, y, z)
    if fails:
        for f in fails:
            rep.add(FAIL, "dry-land box", f[:110])
    else:
        rep.add(PASS, "declared dry land IS dry",
                f"{len(dom.dry_land_boxes_ll)} box(es)")


def check_outflow(rep: Report, z, mask) -> None:
    from nj_sfincs.model import OUTFLOW_MAX_DEPTH

    o = mask == 3
    bad = int((o & (z < OUTFLOW_MAX_DEPTH)).sum())
    rep.add(PASS if bad == 0 else FAIL, "no free-outflow BC on water",
            f"{bad} of {int(o.sum())} below {OUTFLOW_MAX_DEPTH} m")


def check_support(rep: Report, dom) -> None:
    if dom.n_waterlevel_support is None:
        rep.add(FAIL, "n_waterlevel_support declared", "None")
        return
    rep.add(PASS, "n_waterlevel_support declared", f"{dom.n_waterlevel_support}")


def check_hwms(rep: Report, dom) -> None:
    import geopandas as gpd

    f = dom.hwm_geojson
    if not f.exists():
        rep.add(FAIL, "HWM file present", str(f))
        return
    g = gpd.read_file(f).to_crs(dom.epsg)
    reg = gpd.read_file(BaseConfig().region).to_crs(dom.epsg).geometry.iloc[0]
    g = g[g.geometry.within(reg)]
    if not dom.hwm_rules:
        rep.add(FAIL, "hwm_rules declared", "none")
        return
    basin = _domain.classify_hwm_basin(g.geometry.x.values, g.geometry.y.values)
    stray = int(np.sum((basin == "unassigned") | (basin == "unclassified")))
    rep.add(PASS if stray == 0 else FAIL, "every HWM lands in a declared basin",
            f"{len(g)} in-region marks, {stray} stray")
    names = _domain.hwm_basin_names()
    counts = {n: int((basin == n).sum()) for n in names}
    rep.add(PASS, "HWM basin split",
            " ".join(f"{k}={v}" for k, v in counts.items() if v))


def check_discharge(rep: Report, dom, x, y, z, mask) -> None:
    import xarray as xr
    import yaml
    from pyproj import Transformer
    from scipy.spatial import cKDTree

    cat = yaml.safe_load((ROOT / "data" / "data_catalog.yml").read_text())
    entry = cat.get(dom.discharge_geodataset)
    if entry is None:
        rep.add(FAIL, "discharge dataset in catalog", dom.discharge_geodataset)
        return
    p = ROOT / "data" / entry["uri"]
    if not p.exists():
        rep.add(FAIL, "discharge file present", str(p))
        return
    ds = xr.open_dataset(p)
    lon = np.atleast_1d(ds["lon"].values)
    lat = np.atleast_1d(ds["lat"].values)
    ds.close()
    fwd = Transformer.from_crs(4326, dom.epsg, always_xy=True)
    X, Y = fwd.transform(lon, lat)
    tree = cKDTree(np.c_[x, y])
    d, i = tree.query(np.c_[X, Y])

    # 🔴 SPLIT ON DISTANCE FIRST. The discharge file is shared across domains and carries
    # inflows for rivers this domain does not contain — Toms River is 22 km outside
    # v1_5_raritan. Judging every point against the mesh flags those as "dry ground",
    # which is true and meaningless, and a check that cries wolf gets ignored.
    NEAR_M = 500.0
    near = d <= NEAR_M
    n_far = int((~near).sum())

    dry = near & (mask[i] > 0) & (z[i] >= 0)
    inactive = near & (mask[i] == 0)
    if dry.any() or inactive.any():
        rep.add(FAIL, "discharge inflows are wet + active",
                f"{int(dry.sum())} on dry ground, {int(inactive.sum())} on inactive cells")
    else:
        rep.add(PASS, "discharge inflows are wet + active",
                f"{int(near.sum())} in-domain, bed {z[i][near].max():+.2f}..{z[i][near].min():+.2f}")

    # An out-of-domain point that still snaps onto a live cell is the injection risk:
    # a river this domain does not contain, delivered somewhere arbitrary near its edge.
    stray = (~near) & (mask[i] > 0)
    rep.add(WARN if stray.any() else PASS, "no out-of-domain inflow snaps onto a cell",
            f"{n_far} point(s) outside this domain"
            + (f"; {int(stray.sum())} SNAP onto live cells — verify hydromt drops them"
               if stray.any() else "; all land on inactive ground"))


def check_obs(rep: Report, dom, x, y, z, mask) -> None:
    from pyproj import Transformer
    from scipy.spatial import cKDTree

    gauges = getattr(dom, "obs_gauges", ()) or ()
    if not gauges:
        rep.add(SKIP, "observation points", "none declared")
        return
    fwd = Transformer.from_crs(4326, dom.epsg, always_xy=True)
    tree = cKDTree(np.c_[x, y])
    inactive, high = [], []
    for g in gauges:
        lo = getattr(g, "lon", None)
        la = getattr(g, "lat", None)
        if lo is None or la is None:
            continue
        X, Y = fwd.transform(lo, la)
        _, i = tree.query([X, Y])
        if mask[i] == 0:
            inactive.append(f"{g.name}(mask=0)")
        elif z[i] >= HIGH_GROUND_M:
            high.append(f"{g.name}(z={z[i]:+.2f})")
    # 🔴 THE TEST IS "ACTIVE", NOT "BELOW DATUM", and the difference is the whole point.
    # USGS rapid-deployment storm-tide sensors are MOUNTED ABOVE NORMAL WATER — that is
    # what they are for. Instrument 2255 in Raritan Bay sits on ground CUDEM puts at
    # +1.45 m and was above its own recordable floor for 1.9% of the record. A check
    # demanding z < 0 fails those by design, and it did: the first version of this
    # function flagged two working v1_monmouth gauges at +2.44 and +3.52 m as broken.
    # An inactive cell is a real defect (the gauge can never wet); high ground is a note.
    rep.add(FAIL if inactive else PASS, "obs gauges on ACTIVE cells",
            f"{len(gauges)} declared" + (f"; INACTIVE: {', '.join(inactive)}" if inactive
                                         else ""))
    if high:
        rep.add(WARN, "obs gauges on high ground",
                f"{', '.join(high)} — above {HIGH_GROUND_M:+.1f} m, so these wet only "
                f"near the crest (normal for storm-tide sensors)")


def check_tests(rep: Report) -> None:
    r = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
        cwd=ROOT, capture_output=True, text=True,
    )
    tail = [ln for ln in r.stderr.splitlines() if ln.startswith(("OK", "FAILED", "Ran"))]
    rep.add(PASS if r.returncode == 0 else FAIL, "unit tests", " ".join(tail))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--figures", action="store_true",
                    help="regenerate the boundary plots (so the one human check is "
                         "made against current output, not a stale PNG)")
    ap.add_argument("--mesh", default=None, help="mesh dir (default: the frozen mesh)")
    a = ap.parse_args()

    dom = _domain.active()
    mesh = Path(a.mesh) if a.mesh else BaseConfig().frozen_mesh
    print(f"\ndomain {dom.name!r}   mesh {mesh}\n")
    if mesh is None or not Path(mesh).exists():
        print(f"🔴 no frozen mesh at {mesh} — run scripts/freeze_mesh.py first")
        return 2

    x, y, z, mask = _mesh_arrays(Path(mesh))
    rep = Report()
    check_fingerprint(rep, dom, Path(mesh))
    check_region_containment(rep, x, y, mask)
    check_arms(rep, dom, x, y, z, mask)
    check_outflow(rep, z, mask)
    check_dry_land(rep, dom, x, y, z)
    check_support(rep, dom)
    check_hwms(rep, dom)
    check_discharge(rep, dom, x, y, z, mask)
    check_obs(rep, dom, x, y, z, mask)
    check_tests(rep)

    if a.figures:
        subprocess.run([sys.executable, "scripts/plot_waterlevel_boundary.py", str(mesh)],
                       cwd=ROOT)

    print()
    if rep.failed:
        print(f"🔴 {rep.failed} CHECK(S) FAILED — this domain is not fit to run.\n")
        return 1
    print("✅ ALL AUTOMATED CHECKS PASSED.\n")
    print("⚠️  The one check that is NOT automated: LOOK at")
    print("    reports/figures/waterlevel_boundary_*.png")
    print("    and confirm the boundary is where you MEANT it. Every invariant was green")
    print("    on 2026-08-13 while the Narrows arm was 670 m off the bridge it was drawn")
    print("    on, and no assert can know what you intended.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
