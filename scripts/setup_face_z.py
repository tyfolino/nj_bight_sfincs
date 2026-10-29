#!/usr/bin/env python
"""Stage a FACE-Z-VARIANT domain: a sealed template whose mesh ``z`` follows a subgrid bed.

FINDINGS §63: SnapWave takes its WHOLE bed from the mesh's face ``z``, never from the
subgrid, so every subgrid-only bed fix reaches the flow but not the waves. This script
gives SnapWave the bed the flow already uses: on every ACTIVE face, face ``z`` becomes the
subgrid's MEAN ground (``z_zmax − z_volmax / area``, CLAUDE.md §6), taken from ``--bed``.

    NJ_DOMAIN=<target> python scripts/setup_face_z.py --from v4_refreeze \\
        --bed _subgrid_refreeze_lakes_min_creeks_cohansey

Writes ``experiments/<target>/_template_sealed`` and ``experiments/<target>/<bed>``. Both are
HARD-LINK copies of the source domain's dirs except ``sfincs.nc`` (one fresh file, the two
dirs share it) and its ``snapwave.upw`` (the cached face-``z`` bed slopes,
``snapwave_domain.f90:220-238``, read back unchecked — dropped, so each run rebuilds it).

🔴 ``z`` IS HALF THE FINGERPRINT (``premier.domain_fingerprint``), so this is a DOMAIN, not an
arm: same mesh, same mask, same counts, a new sha. Register the sha it prints in
``premier.EXPECTED`` before staging anything on it.

Kept as they are: faces whose subgrid volume table is floored at −20 m (hydromt
``workflows/subgrid.py:58``; mean ground there reads −20 while face ``z`` holds the true
depth), inactive faces, and faces with no finite mean ground. Every other variable in
``sfincs.nc`` is checked byte-identical to the source. The SnapWave mask and wave-boundary
support points are re-derived from face ``z`` at ARM staging (``model.add_waves``), so read
an arm's staging log for how they moved.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

import netCDF4
import numpy as np

import nj_sfincs  # noqa: F401  (PROJ primer — must precede hydromt_sfincs)
from nj_sfincs import domain as _domain
from nj_sfincs import premier
from nj_sfincs.config import exp_root

#: Faces whose subgrid z_zmax sits on hydromt's −20 m volume floor.
VOLUME_FLOOR = -19.99
DROP = {"sfincs.nc", "snapwave.upw", ".subgrid_sha256"}


def link_tree(src: Path, dst: Path) -> None:
    """Hard-link copy of ``src`` into a new ``dst`` (copy fallback), skipping ``DROP``."""
    dst.mkdir(parents=True)
    for p in sorted(src.iterdir()):
        if p.name in DROP:
            continue
        q = dst / p.name
        if p.is_dir():
            link_tree(p, q)
        else:
            try:
                os.link(p, q)
            except OSError:
                shutil.copy2(p, q)


def mean_ground(nc: Path, subgrid: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    with netCDF4.Dataset(nc) as m, netCDF4.Dataset(subgrid) as s:
        z = m["z"][:].filled(np.nan)
        mask = m["mask"][:].filled(0)
        lev = m["level"][:].filled(1)
        dx = float(m.getncattr("dx"))
        zmax = s["z_zmax"][:].filled(np.nan)
        vol = s["z_volmax"][:].filled(np.nan)
    area = (dx / 2.0 ** (lev - 1)) ** 2
    return z, mask, zmax - vol / area, zmax


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--from", dest="src_domain", required=True)
    ap.add_argument(
        "--bed", required=True, help="subgrid_from dir of the source domain"
    )
    a = ap.parse_args(argv)

    dom = _domain.active()
    if dom.face_z_from != a.bed:
        sys.exit(
            f"domain {dom.name!r} declares face_z_from={dom.face_z_from!r}, not {a.bed!r} "
            "— declare the bed on the Domain first (nj_sfincs/domain.py)"
        )
    if dom.name == a.src_domain:
        sys.exit("NJ_DOMAIN must be the TARGET domain, not the source")
    src_root = exp_root().parent / a.src_domain
    dst_root = exp_root()
    src_t, src_b = src_root / premier.TEMPLATE_NAME, src_root / a.bed
    dst_t, dst_b = dst_root / premier.TEMPLATE_NAME, dst_root / a.bed
    for d in (dst_t, dst_b):
        if d.exists():
            sys.exit(f"{d} exists — move it aside first; this script never overwrites")
    for d in (src_t, src_b):
        if not (d / "sfincs.nc").exists():
            sys.exit(f"no sfincs.nc in {d}")
    fp_src = premier.domain_fingerprint(src_t)
    if (
        fp_src != premier.EXPECTED[a.src_domain]
        or premier.domain_fingerprint(src_b) != fp_src
    ):
        sys.exit(
            f"source template / bed not on the sealed {a.src_domain} mesh ({fp_src})"
        )

    z, mask, zmean, zmax = mean_ground(src_t / "sfincs.nc", src_b / "sfincs_subgrid.nc")
    take = (mask > 0) & np.isfinite(zmean) & (zmax > VOLUME_FLOOR)
    new = z.copy()
    new[take] = zmean[take]
    d = new - z
    changed = take & (d != 0)
    print(
        f"faces {z.size:,}; active {int((mask > 0).sum()):,}; set from mean ground "
        f"{int(take.sum()):,} (kept: {int(((mask > 0) & ~take).sum()):,} active faces on the "
        f"−20 m floor or without a finite mean); changed {int(changed.sum()):,}"
    )
    q = np.percentile(d[changed], [1, 5, 50, 95, 99]) if changed.any() else []
    print("new − old z on changed faces, p1/p5/p50/p95/p99:", np.round(q, 3))

    dst_root.mkdir(parents=True, exist_ok=True)
    link_tree(src_t, dst_t)
    shutil.copyfile(src_t / "sfincs.nc", dst_t / "sfincs.nc")  # a FRESH inode
    assert os.stat(dst_t / "sfincs.nc").st_nlink == 1
    with netCDF4.Dataset(dst_t / "sfincs.nc", "r+") as m:
        assert m["z"].shape == new.shape
        m["z"][:] = new
    # every other variable must be byte-identical to the source mesh
    with (
        netCDF4.Dataset(src_t / "sfincs.nc") as s0,
        netCDF4.Dataset(dst_t / "sfincs.nc") as s1,
    ):
        for v in s0.variables:
            if v == "z":
                continue
            a0, a1 = s0[v][:], s1[v][:]
            if not np.array_equal(np.ma.getdata(a0), np.ma.getdata(a1)):
                sys.exit(
                    f"🔴 {v} differs after the z write — refusing ({dst_t} left for inspection)"
                )
    link_tree(src_b, dst_b)
    os.link(dst_t / "sfincs.nc", dst_b / "sfincs.nc")
    fp = premier.domain_fingerprint(dst_t)
    if (fp.n_faces, fp.n_boundary_edges) != (fp_src.n_faces, fp_src.n_boundary_edges):
        sys.exit(f"🔴 counts moved: {fp} vs {fp_src}")
    note = (
        f"\n# setup_face_z.py: face z = subgrid mean ground of {a.bed} on {int(take.sum()):,} "
        f"active faces ({int(changed.sum()):,} changed); source {a.src_domain} {fp_src}; "
        f"→ {dom.name} {fp}; snapwave.upw dropped\n"
    )
    for d_ in (dst_t, dst_b):
        prov = d_ / "provenance.txt"
        text = prov.read_text() if prov.exists() else ""
        prov.unlink(missing_ok=True)  # break the hard link before writing
        prov.write_text(text + note)
    rep = {
        "source_domain": a.src_domain,
        "source_fingerprint": str(fp_src),
        "target_domain": dom.name,
        "target_fingerprint": str(fp),
        "sha": fp.sha_z_mask,
        "bed": a.bed,
        "faces_set": int(take.sum()),
        "faces_changed": int(changed.sum()),
        "delta_p1_p5_p50_p95_p99": [float(x) for x in q],
    }
    (dst_t / "face_z_report.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))
    print(
        f"\nRegister in premier.EXPECTED: {dom.name!r}: DomainFingerprint"
        f"({fp.n_faces}, {fp.n_boundary_edges}, {fp.sha_z_mask!r})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
