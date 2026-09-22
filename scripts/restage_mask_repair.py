#!/usr/bin/env python
"""Stage a MASK REPAIR of the active domain from its frozen mesh, and show the diff.

    NJ_DOMAIN=v3 python scripts/restage_mask_repair.py [--dst DIR] [--force]
                                                      [--compare-idx walled.npy]

🔴 A mask change is a DOMAIN change. ``mask`` is half of ``sha(z, mask)``, so the
fingerprint moves and every arm on the domain re-baselines (STATUS 08-31 procedure).
This script therefore never writes to ``_template_sealed``: it stages to a SEPARATE dir
(default ``<exp_root>/_template_mask_repair``), diffs the new mask against the frozen
mesh's, and prints the fingerprint the registry needs. Adoption — banking
``metrics.csv``, updating ``premier.EXPECTED``, replacing the sealed template and the
frozen mesh's ``sfincs.nc`` — is a separate, deliberate step the user approves.

What it runs is ``model.restage_from_frozen_mesh``: THE SAME ``apply_mask_and_boundary``
the ordinary build uses, on a copy of the frozen mesh, with the domain's current
``mask_overrides`` and the wet-outflow seal. The subgrid is reused, not rebuilt — it is
independent of the mask. Forcing and waves are re-derived because the boundary line they
interpolate onto may have moved.

The diff it prints is the review artefact: how many faces changed and from what to
what, per declared override box, what changed OUTSIDE every box (the seal), their
elevation range and lon/lat extent, and — with ``--compare-idx`` — how the change lines
up with a hand-staged diagnostic's face list (the 09-21 wall test).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pyproj
import xarray as xr

import nj_sfincs  # noqa: F401  (PROJ primer — must precede hydromt_sfincs)
from nj_sfincs import domain as _domain
from nj_sfincs import model, premier
from nj_sfincs.config import BaseConfig, exp_root
from nj_sfincs.experiments import experiments

CODES = {0: "inactive", 1: "active", 2: "waterlevel", 3: "outflow"}


def _mask_and_z(
    model_dir: Path,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    with xr.open_dataset(model_dir / "sfincs.nc") as ds:
        mask = ds["mask"].values.astype(int)
        z = ds["z"].values.astype(float)
        x = ds["mesh2d_face_x"].values.astype(float)
        y = ds["mesh2d_face_y"].values.astype(float)
    return mask, z, x, y


def diff_masks(frozen: Path, dst: Path, compare_idx: Path | None = None) -> dict:
    dom = _domain.active()
    m0, z0, x, y = _mask_and_z(frozen)
    m1, z1, x1, y1 = _mask_and_z(dst)
    if m0.shape != m1.shape or not np.array_equal(x, x1) or not np.array_equal(y, y1):
        sys.exit(
            "🔴 the staged mesh is not the frozen mesh (face count or coordinates)"
        )
    if not np.array_equal(z0, z1):
        sys.exit(
            "🔴 the staged z differs from the frozen mesh — this is not a mask repair"
        )
    lon, lat = pyproj.Transformer.from_crs(dom.epsg, 4326, always_xy=True).transform(
        x, y
    )
    with xr.open_dataset(dst / "sfincs_subgrid.nc") as ds:
        zmin = ds["z_zmin"].values.astype(float)

    changed = m0 != m1
    out: dict = {
        "n_faces": int(m0.size),
        "n_changed": int(changed.sum()),
        "by_code": {},
    }
    print(f"\n[diff] {changed.sum():,} of {m0.size:,} faces changed mask code")
    for a in sorted(set(m0[changed])):
        for b in sorted(set(m1[changed & (m0 == a)])):
            n = int((changed & (m0 == a) & (m1 == b)).sum())
            out["by_code"][f"{a}->{b}"] = n
            print(f"    {CODES[a]:10s} -> {CODES[b]:10s} ({a}->{b}): {n:5d}")
    for code in (1, 2, 3):
        print(
            f"    mask=={code} ({CODES[code]:10s}): {int((m0 == code).sum()):9,} -> "
            f"{int((m1 == code).sum()):9,}"
        )

    covered = np.zeros(m0.shape, bool)
    out["overrides"] = {}
    for ov in dom.mask_overrides:
        xmin, ymin, xmax, ymax = ov.box
        inb = (x > xmin) & (x < xmax) & (y > ymin) & (y < ymax)
        covered |= inb
        sel = changed & inb & (m0 == ov.frm) & (m1 == ov.to)
        n = int(sel.sum())
        rec = {"n": n}
        if n:
            rec.update(
                lon=[float(lon[sel].min()), float(lon[sel].max())],
                lat=[float(lat[sel].min()), float(lat[sel].max())],
                z_mean_p5_p50_p95=[
                    float(v) for v in np.percentile(z0[sel], [5, 50, 95])
                ],
                z_zmin_min=float(np.nanmin(zmin[sel])),
                n_below_5m=int((z0[sel] < 5).sum()),
                n_wet_floor=int((zmin[sel] < model.OUTFLOW_MAX_DEPTH).sum()),
            )
            print(
                f"\n[diff] override {ov.name}: {n} faces {ov.frm}->{ov.to}; lon "
                f"{lon[sel].min():.4f}..{lon[sel].max():.4f} lat {lat[sel].min():.4f}.."
                f"{lat[sel].max():.4f}; z_mean p5/p50/p95 "
                f"{np.percentile(z0[sel], 5):+.1f}/{np.percentile(z0[sel], 50):+.1f}/"
                f"{np.percentile(z0[sel], 95):+.1f}; {rec['n_below_5m']} below +5 m; "
                f"{rec['n_wet_floor']} wet by the subgrid floor (deepest "
                f"{rec['z_zmin_min']:+.2f})"
            )
        else:
            print(f"\n[diff] override {ov.name}: 0 faces changed")
        out["overrides"][ov.name] = rec

    other = changed & ~covered
    out["outside_boxes"] = int(other.sum())
    print(f"\n[diff] changed OUTSIDE every override box: {int(other.sum())} faces")
    for i in np.where(other)[0]:
        print(
            f"    face {i:8d}  {CODES[m0[i]]}->{CODES[m1[i]]}  lon {lon[i]:.4f} "
            f"lat {lat[i]:.4f}  z_mean {z0[i]:+.2f}  z_zmin {zmin[i]:+.2f}"
        )

    if compare_idx is not None:
        walled = np.load(compare_idx)
        w = np.zeros(m0.shape, bool)
        w[walled] = True
        both, only_test, only_repair = w & changed, w & ~changed, changed & ~w
        out["compare"] = {
            "file": str(compare_idx),
            "n_test": int(w.sum()),
            "both": int(both.sum()),
            "test_only": int(only_test.sum()),
            "repair_only": int(only_repair.sum()),
        }
        print(
            f"\n[diff] vs {compare_idx.name}: test walled {w.sum()}, in both "
            f"{both.sum()}, test-only {only_test.sum()}, repair-only {only_repair.sum()}"
        )
        if only_test.any():
            print(
                f"    test-only faces: lon {lon[only_test].min():.4f}.."
                f"{lon[only_test].max():.4f} lat {lat[only_test].min():.4f}.."
                f"{lat[only_test].max():.4f}, z_mean p50 "
                f"{np.median(z0[only_test]):+.1f} (expected: the Raritan cut + high "
                f"NJ-bank faces, left outflow on purpose)"
            )
        if only_repair.any():
            print(
                f"    repair-only faces: lon {lon[only_repair].min():.4f}.."
                f"{lon[only_repair].max():.4f} lat {lat[only_repair].min():.4f}.."
                f"{lat[only_repair].max():.4f}, z_mean p50 "
                f"{np.median(z0[only_repair]):+.1f} (expected: faces above the "
                f"test's +5 m gate inside the boxes — no-ops until water is that high)"
            )

    np.save(dst / "mask_repair_changed_idx.npy", np.where(changed)[0])
    (dst / "mask_repair_diff.json").write_text(json.dumps(out, indent=2))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dst", type=Path, default=None)
    ap.add_argument("--force", action="store_true", help="remove --dst if it exists")
    ap.add_argument("--compare-idx", type=Path, default=None)
    ap.add_argument(
        "--diff-only",
        action="store_true",
        help="skip staging; diff an already-staged --dst against the frozen mesh",
    )
    a = ap.parse_args(argv)

    dom = _domain.active()
    if dom.frozen:
        sys.exit(f"domain {dom.name!r} is frozen — nothing may be staged onto it.")
    frozen = dom.frozen_mesh_dir()
    dst = a.dst or exp_root() / "_template_mask_repair"
    sealed = exp_root() / premier.TEMPLATE_NAME
    if dst.resolve() == sealed.resolve():
        sys.exit(
            f"refusing to stage into {sealed}: the sealed template is replaced at "
            "ADOPTION, after the diff is approved, not here."
        )
    if not dom.mask_overrides:
        print(
            f"⚠️  domain {dom.name!r} declares no mask_overrides — this stages a plain "
            "re-derivation (only the wet-outflow seal can differ)."
        )

    if not a.diff_only:
        base = BaseConfig()
        arms = experiments()
        if premier.PREMIER_NAME not in arms:
            sys.exit(f"domain {dom.name!r} has no arm named {premier.PREMIER_NAME!r}")
        wcfg = arms[premier.PREMIER_NAME].waves
        if dst.exists():
            if not a.force:
                sys.exit(f"{dst} exists — pass --force to remove it, or --diff-only")
            print(f"[stage] removing {dst}")
            shutil.rmtree(dst)
        model.restage_from_frozen_mesh(base, wcfg, dst, frozen)

    diff_masks(frozen, dst, a.compare_idx)

    fp = premier.domain_fingerprint(dst)
    want = premier.EXPECTED.get(dom.name)
    print(f"\n[stage] staged fingerprint:     {fp}")
    print(f"[stage] registered fingerprint: {want}")
    if want == fp:
        print("    identical to the registry — the repair changed nothing.")
        return 0
    print(
        "    the fingerprint MOVED, as a mask repair must. To adopt (user decision):\n"
        f"      1. bank experiments/<domain>/metrics.csv as metrics_<date>_pre_<why>_rebaseline.csv\n"
        f"      2. nj_sfincs/premier.py: {dom.name.upper()} = DomainFingerprint("
        f'{fp.n_faces}, {fp.n_boundary_edges}, "{fp.sha_z_mask}")  + KNOWN label\n'
        f"      3. replace {sealed} with {dst}\n"
        f"      4. copy {dst / 'sfincs.nc'} over {frozen / 'sfincs.nc'} (same z, new mask)\n"
        "      5. python -m nj_sfincs.premier  — every old run dir now reads UNRECOGNISED; "
        "re-run the arms"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
