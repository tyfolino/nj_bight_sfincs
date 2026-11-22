#!/usr/bin/env python
"""Rewrite a sealed template's curve-number retention (``scs`` in ``sfincs.nc``) from another
CN dataset, after proving the method reproduces the template's current ``scs`` exactly.

WHY. The CN a run uses is the ``scs`` variable INSIDE the template's quadtree file (hydromt
``create_cn``, written once at the template build); staging copies it and ``nj_sfincs/infiltration.py``
(cnb) reads it. ``Domain.cn_dataset`` alone changes nothing on a domain staged by
``setup_face_z.py`` / ``setup_boundary_depth.py``, which copy their source template's file. First
use: ``nj2w_bed2026`` (2026-11-18), which carried the 2012 CN (``cn_v4``) instead of ``cn_2025_v4``.

HOW. The body of hydromt_sfincs ``SfincsQuadtreeInfiltration.create_cn`` (antecedent_moisture
None, reproj_method "med", nrmax 2000, as ``model.add_forcing`` calls it), run through the
component's own ``compute_quadtree`` on the template, read-only. It REFUSES to write unless the
same code with ``--check-from`` (the dataset the template was built from) reproduces the stored
``scs`` bit for bit. Only ``scs`` and two attributes change; ``z`` and ``mask`` (the fingerprint)
are untouched. The file is written IN PLACE, so every hard link to it changes too: it refuses
when a link lies outside the template's own domain dir (``--allow-shared`` overrides).

    NJ_DOMAIN=nj2w_bed2026 python scripts/set_template_cn.py \\
        experiments/nj2w_bed2026/_template_sealed --check-from cn_v4 --cn cn_2025_v4          # dry run
    ... --apply                                                                              # write

Heavy-ish (reprojects a 0.5 GB raster onto 5 M faces): run on a compute node.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def compute_scs(sf, cn: str, nrmax: int = 2000):
    """hydromt create_cn's arithmetic, without set(): S [in] per face, NaN on active → 100."""
    import numpy as np
    import xarray as xr

    from hydromt_sfincs import workflows

    comp = sf.quadtree_infiltration
    da_org = sf.data_catalog.get_rasterdataset(cn, bbox=sf.bbox, buffer=10)
    if isinstance(da_org, xr.Dataset):
        da_org = da_org["cn"]
    scs = np.full(sf.quadtree_grid.data.grid.n_face, np.nan)

    def compute_cn_infiltration(da_like, ilev=None):
        da_cn = da_org.raster.reproject_like(da_like, method="med")
        return workflows.cn_to_s(da_cn).round(3)

    comp.compute_quadtree(compute_cn_infiltration, scs, nrmax=nrmax)
    mask = np.asarray(comp.mask)
    scs = np.where(np.isnan(scs) & (mask >= 1), 100, scs)
    return scs, mask


def links(path: Path, search: Path) -> list[Path]:
    out = subprocess.run(
        ["find", str(search), "-samefile", str(path)],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.split()
    return [Path(p) for p in out]


def main(argv=None) -> int:
    import netCDF4
    import numpy as np

    from hydromt_sfincs import SfincsModel
    from nj_sfincs.config import BaseConfig

    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("template", type=Path)
    p.add_argument(
        "--check-from", required=True, help="dataset the template was built from"
    )
    p.add_argument("--cn", required=True, help="the CN dataset to write")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--allow-shared", action="store_true")
    a = p.parse_args(argv)
    tpl = a.template.resolve()
    nc = tpl / "sfincs.nc"
    report = {"template": str(tpl), "check_from": a.check_from, "cn": a.cn}

    with netCDF4.Dataset(nc) as d:
        stored = np.asarray(d["scs"][:].filled(np.nan), dtype="f8")
        report["stored_cn_source_attr"] = getattr(d["scs"], "cn_source", None)

    sf = SfincsModel(str(tpl), data_libs=BaseConfig().data_libs, mode="r")
    ref, mask = compute_scs(sf, a.check_from)
    same = bool(np.array_equal(ref, stored, equal_nan=True))
    nd = int((~((ref == stored) | (np.isnan(ref) & np.isnan(stored)))).sum())
    report["reproduces_stored"] = same
    report["n_faces_differ_from_stored"] = nd
    print(f"[cn] {a.check_from} reproduces the stored scs: {same} ({nd} faces differ)")
    if not same:
        print(
            "[cn] REFUSING: the method does not reproduce the template; nothing written"
        )
        print(json.dumps(report, indent=1))
        return 3

    new, _ = compute_scs(sf, a.cn)
    act = mask > 0
    dif = act & ~((new == stored) | (np.isnan(new) & np.isnan(stored)))
    d_s = (new - stored)[dif]
    report.update(
        n_active=int(act.sum()),
        n_active_changed=int(dif.sum()),
        mean_active_scs_in_before=float(np.nanmean(stored[act])),
        mean_active_scs_in_after=float(np.nanmean(new[act])),
        changed_dscs_in_p1_p50_p99=[float(np.percentile(d_s, q)) for q in (1, 50, 99)]
        if d_s.size
        else None,
        n_active_to_water=int((act & (stored > 0) & (new == 0)).sum()),
        n_active_from_water=int((act & (stored == 0) & (new > 0)).sum()),
    )
    print(json.dumps(report, indent=1))
    if not a.apply:
        print("[cn] dry run: nothing written (--apply to write)")
        return 0

    dom_dir = Path(os.path.realpath(tpl.parent))
    exp = Path(os.path.realpath(ROOT / "experiments"))
    shared = [q for q in links(nc, exp) if dom_dir not in q.parents]
    if shared and not a.allow_shared:
        print(f"[cn] REFUSING: {nc} is hard-linked outside {dom_dir}: {shared}")
        return 4
    with netCDF4.Dataset(nc, "r+") as d:
        v = d["scs"]
        v[:] = new
        v.setncattr("cn_source", a.cn)
        v.setncattr("cn_source_previous", a.check_from)
    with netCDF4.Dataset(nc) as d:
        back = np.asarray(d["scs"][:].filled(np.nan), dtype="f8")
    ok = bool(np.array_equal(back, new, equal_nan=True))
    report["written_and_read_back"] = ok
    report["when"] = datetime.now().isoformat(timespec="seconds")
    (tpl / "cn_rewrite.json").write_text(json.dumps(report, indent=1) + "\n")
    prov = tpl / "provenance.txt"
    if prov.exists():
        text = prov.read_text()
        prov.unlink()  # a fresh inode: provenance may be hard-linked to a sibling's
        prov.write_text(
            text + f"\n{report['when']} scs rewritten from {a.cn} (was {a.check_from}, "
            f"reproduced bit for bit) by scripts/set_template_cn.py; cn_rewrite.json\n"
        )
    print(f"[cn] written; read back equal: {ok}")
    return 0 if ok else 5


if __name__ == "__main__":
    raise SystemExit(main())
