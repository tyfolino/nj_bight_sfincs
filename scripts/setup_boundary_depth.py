#!/usr/bin/env python
"""Stage a BOUNDARY-DEPTH domain from its `mesh_key` sibling. No rebuild.

    NJ_DOMAIN=<deep domain> python scripts/setup_boundary_depth.py [template_dir]

🔴 BOUNDARY DEPTH IS A DOMAIN AXIS, NOT AN ARM AXIS. ``mask_zmin`` is half of
``sha(z, mask)`` — the domain fingerprint — so an "arm" that changed it would fail
``premier.assert_sealed_domain`` on its own staged copy. That is the guard working
correctly and the arm being the wrong shape. A −10 m and a −15 m boundary are two
registered DOMAINS sharing one ``mesh_key``, and this script is how the second one comes
into existence.

⚠️ THEIR FINGERPRINTS DIFFER ONLY IN THE SHA. Identical ``n_faces``, identical
``n_boundary_edges``, different ``sha_z_mask`` — the same trap a mask repair set once
before. You cannot tell them apart by counting anything. That is exactly why the
fingerprint hashes the mask and not the cell counts, and why ``tests/`` asserts the
property.

WHY THIS NEEDS NO SUBGRID REBUILD — the whole point
---------------------------------------------------
The frozen mesh reaches far seaward and **every one of its faces already carries subgrid
tables**. The subgrid is computed per face from elevation + roughness and is INDEPENDENT
of the mask, so a deeper ``mask_zmin`` only ACTIVATES faces that already have tables. This
is a mask + boundary + forcing re-derivation on a COPY, not a rebuild:

  1. copy the shared frozen mesh -> the new template
  2. re-run ``model.apply_mask_and_boundary`` at the new zmin — THE SAME CODE the ordinary
     build uses, with only ``mask_zmin`` different, so anything that changes here is purely
     the intended seaward extension
  3. re-run ``add_forcing`` (the water-level boundary is interpolated onto ``mask==2``
     cells, which moved) and ``add_waves`` (SnapWave support points are the deep,
     open-Atlantic ``mask==2`` edge, which also moved seaward)
  4. ``finalize`` + ``restore_diagnostics``

⚠️ ``add_waves`` READS ``mask_zmin`` TOO, for the SnapWave seaward band, so it follows
automatically. A boundary-depth domain does not need a second knob set — and must not have
one set, or the two would drift.

WHAT TO EXPECT, written before looking
--------------------------------------
* A deeper boundary should not move the sheltered interior basins much — they are far
  inland of the contour. If it does, the contour is coupling to the interior, and that is a
  red flag about the contour, not a result.
* The open-coast gauges and the offshore zs ring are where a deeper boundary should act.
* ⚠️ ``create_active(zmin)`` is a GLOBAL cut. Going too shallow deactivates carved interior
  channels; going deeper is safe in that direction but reaches further through any inlet
  gorge, which is what the ``NoWaterLevelBox`` / ``BoundaryArm`` declarations are for. Read
  the per-arm boundary census this prints.
"""

from __future__ import annotations

import gc
import shutil
import sys
from pathlib import Path

from hydromt_sfincs import SfincsModel

import nj_sfincs  # noqa: F401  (PROJ primer — must precede hydromt_sfincs)
from nj_sfincs import domain as _domain
from nj_sfincs import model, premier
from nj_sfincs.config import BaseConfig, exp_root
from nj_sfincs.experiments import experiments


def main(argv: list[str] | None = None) -> int:
    dom = _domain.active()
    dst = Path(argv[0]) if argv else exp_root() / premier.TEMPLATE_NAME

    if dom.frozen:
        sys.exit(f"domain {dom.name!r} is frozen — nothing may be staged onto it.")
    if dom.mesh_key is None:
        sys.exit(
            f"domain {dom.name!r} declares no mesh_key, so it does not SHARE a mesh with "
            "anything and this script has nothing to stage from. Either give it a "
            "mesh_key pointing at its sibling, or build it with scripts/freeze_mesh.py."
        )

    siblings = [
        d
        for d in _domain.DOMAINS.values()
        if d.mesh_key == dom.mesh_key and d.name != dom.name
    ]
    if not siblings:
        sys.exit(f"no other domain shares mesh_key {dom.mesh_key!r}.")
    if any(s.mask_zmin == dom.mask_zmin for s in siblings):
        sys.exit(
            f"a domain sharing mesh_key {dom.mesh_key!r} has the SAME mask_zmin "
            f"({dom.mask_zmin}). Sharing a mesh is only legitimate when the mask differs; "
            "otherwise the two are the same domain under two names."
        )

    frozen = dom.frozen_mesh_dir()
    if not (frozen / "sfincs_subgrid.nc").exists():
        sys.exit(f"no subgrid in {frozen} — build the shared mesh first.")

    base = BaseConfig()
    assert base.mask_zmin == dom.mask_zmin, "BaseConfig is not reading the domain"

    arms = experiments()
    if not arms:
        sys.exit(f"domain {dom.name!r} has no arms in nj_sfincs/experiments.py")
    # Waves come from the arms' shared config; every arm on a boundary-depth domain is the
    # same physics at a different boundary, so take the premier's.
    wcfg = arms[premier.PREMIER_NAME].waves if premier.PREMIER_NAME in arms else None
    if wcfg is None:
        sys.exit(
            f"domain {dom.name!r} has no arm named {premier.PREMIER_NAME!r}; the template "
            "needs one wave configuration and there is no unambiguous choice."
        )

    if dst.exists():
        print(f"[stage] removing {dst}")
        shutil.rmtree(dst)
    print(f"[stage] copying {frozen} -> {dst}  (subgrid REUSED, not rebuilt)")
    shutil.copytree(frozen, dst)

    sf = SfincsModel(str(dst), data_libs=base.data_libs, mode="r+")
    n_before = int((sf.quadtree_grid.data["mask"].values > 0).sum())
    sibling_zmin = ", ".join(f"{s.name}={s.mask_zmin:+.0f}" for s in siblings)
    print(
        f"[stage] re-deriving mask/boundary at mask_zmin={dom.mask_zmin:+.1f} m "
        f"(siblings: {sibling_zmin})"
    )
    model.apply_mask_and_boundary(base, sf)
    n_after = int((sf.quadtree_grid.data["mask"].values > 0).sum())
    print(f"[stage] active cells {n_before:,} -> {n_after:,} ({n_after - n_before:+,})")

    print("[stage] forcing + waves")
    model.add_forcing(base, sf)
    sw = model.add_waves(wcfg, base, sf)
    model.finalize(wcfg, base, sf, dst, sw)
    model.restore_diagnostics(dst)
    del sf
    gc.collect()

    for stale in ("sfincs_his.nc", "sfincs_map.nc", "snapwave.upw", "sfincs.log"):
        (dst / stale).unlink(missing_ok=True)

    fp = premier.domain_fingerprint(dst)
    print(f"\n[stage] staged domain fingerprint: {fp}")
    want = premier.EXPECTED.get(dom.name)
    if want is None:
        print(
            f"⚠️  domain {dom.name!r} has NO registered fingerprint yet. Register\n"
            f"      {dom.name!r}: DomainFingerprint({fp.n_faces}, {fp.n_boundary_edges}, "
            f'"{fp.sha_z_mask}")\n'
            "    in nj_sfincs/premier.py EXPECTED (and a KNOWN label) BEFORE running "
            "anything on it.\n"
            "    An unregistered domain cannot be told apart from a corrupted one."
        )
        return 1
    if fp != want:
        print(f"🔴 fingerprint MISMATCH — registered {want}, staged {fp}")
        return 1
    for s in siblings:
        sib = premier.EXPECTED.get(s.name)
        if sib and (sib.n_faces, sib.n_boundary_edges) == (
            fp.n_faces,
            fp.n_boundary_edges,
        ):
            print(
                f"    note: {s.name} has IDENTICAL face and boundary-edge counts and "
                f"differs only in the sha — as designed. Never identify these by counting."
            )
    print("✅ staged and fingerprint matches the registry.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
