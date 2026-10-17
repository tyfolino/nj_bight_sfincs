"""Rebuild ONLY the subgrid tables on the sealed template's frozen mesh, with extra
elevation tiers PREPENDED, into ``experiments/<domain>/<dst>``.

This is the tool for every ``bed-*`` arm. ``build_static`` copies the frozen mesh and
returns early, so a bed edit routed through it produces a NO-OP template (CLAUDE.md §5);
and the mesh itself must not be rebuilt (environment-sensitive, ~18-cell drift → breaks
every A/B). So: copy the sealed template's ``sfincs.nc`` + ``sfincs.inp``, read the
grid, regenerate ``sfincs_subgrid.nc`` and ``subgrid/*.tif`` with
``elevation_list = [tiers...] + Domain.elevation_list``, the SAME roughness recipe,
pixels and level count as the premier, and diff the result against the template's
tables. Nothing else in the output dir is a model input: an arm consumes it through
``Experiment.subgrid_from`` (run_experiments.prepare_experiment), which swaps the two
subgrid products into a normally staged copy of the sealed template.

The fingerprint is unchanged by construction — ``sfincs.nc`` is the template's byte for
byte — and ``premier.assert_sealed_domain`` is run on the output to prove it. A
subgrid built on any other mesh is refused at staging.

**Diff the right key** (CLAUDE.md §5, FINDINGS §55): for a CARVE diff ``z_volmax``; for a
footprint BURN read ``z_level`` — the burn RAISES ``z_volmax`` (storage up to ``z_zmax``;
p50 +2,461 m³ on v3) while the storage it removes is at a given water level. ``z_zmin``
moves wherever a cell's LOWEST pixel is under a building (11,995 faces on v3), not only in
the 849 fully covered ones. ``subgrid_diff.json``
carries both, plus ``uv_zmax`` and the uv level spacing, since a building cap raises the
equal-depth uv tables' ceiling.

🔴 **``--overlay`` vs ``--tier`` (measured 2026-09-04, one 25 m block, STATUS 09-04).**
hydromt's ``merge_multi_dataarrays`` has two properties that make "prepend the tier"
the WRONG way to burn a footprint raster:

* a tier that is not FIRST has its ``reproj_method`` silently replaced by bilinear
  (``workflows/merge.py``: ``if reproj_method is None: ... else: reproj_method =
  "bilinear"``), and bilinear over a NoData-edged raster grows every footprint by up to
  a pixel with full building height;
* a tier that IS first defines the lattice every later tier is regridded onto, so the
  premier's own pixels move: 89% of NON-footprint pixels changed by ~1 mm, 101 of
  124k by > 0.5 m (up to 8 m on channel banks), and 1.25 M faces got a new ``z_zmin``.

``--overlay`` sidesteps both: the premier's merge runs UNTOUCHED (bit-identical
elevation everywhere the tier is NoData), then the tier is nearest-resampled onto the
merged block and painted where valid. Implemented by wrapping the builder's merge
call, not by editing the toolchain; a ``merge_method: overlay`` marker rides through
hydromt's ``_parse_datasets_elevation`` (which copies ``merge_method``) to the wrapper.
``--tier`` (plain prepend) is kept for tiers that are meant to be merged, e.g. a
bathymetry survey, and is the trapped path for a burn.

**``--overlay <key>:min`` (2026-10-17): LOWER-ONLY paint.** The same nearest paint, but
each pixel becomes ``min(merged bed, overlay)`` where the overlay is valid — the bed is
never RAISED (a merged pixel that is NoData takes the overlay, as in a plain paint).
Needed because "lower-only" on an overlay's OWN lattice is not lower-only after the
nearest resample onto the subgrid's rotated lattice: ``lake_fix_v4`` (3 m, rule "lidar
where lidar < merged bed") painted plain raised ``z_zmin`` on 112 of 2,952 changed faces
(max +1.35 m, ``_subgrid_refreeze_lakes`` vs ``_subgrid_refreeze``, 2026-10-16); a
post-storm-lidar breach overlay (reads the water SURFACE) needs the same rule. The
suffix rides in the one ``--overlay`` list, so its position in the paint ORDER is kept
(later wins, whatever the mode): ``--overlay a --overlay b:min`` paints ``a``, then
lowers to ``b``. It becomes ``merge_method: "overlay_min"`` in the elevation list (and
hence in ``provenance.txt``, whose ``overlay_tiers`` keeps the raw ``:min`` tokens).
Without a suffix every list, the wrapper's arithmetic and the provenance are the
pre-flag script's, byte for byte. Bed only: ``--manning-overlay`` refuses a suffix.

**``--manning-overlay`` (2026-10-05): the same paint, on ROUGHNESS.** hydromt builds the
uv-point Manning block with the same ``merge_multi_dataarrays`` call (``roughness_list``
→ the NLCD reclass), and ``_parse_roughness_list`` copies ``merge_method`` too, so a
``{"manning": <key>, "merge_method": "overlay"}`` entry appended to the roughness list
rides through to the same wrapper: the NLCD merge runs untouched, then the raster's n is
nearest-painted where valid, BEFORE hydromt's land/water NaN fill and before the uv
tables are built. The cell-centre (``z_*``) tables never read Manning; the uv tables
that do are ``uv_nrep`` (the conveyance-weighted n per level), ``uv_navg`` (the box-mean
n of one side, which SFINCS relaxes toward above ``uv_zmax``) and ``uv_ffit`` (that
relaxation's rate) — and, under the default ``weight_option="min"``, ``uv_havg`` where n
flips which side carries the lower flux. ``subgrid_diff.json`` gets those keys when the
flag is given. The ``manningfile`` (``roughness.nc``) in ``sfincs.inp`` is NOT a route:
SFINCS ignores it when a subgrid file is present (``sfincs_domain.f90``). Without the
flag nothing changes: the roughness list, the wrapper, the diff and the provenance are
the pre-flag script's, byte for byte.

    sbatch hpc/rebuild_subgrid.slurm --dst _subgrid_x --overlay <bed> --manning-overlay manning_water_v4

The output dir also gets ``subgrid/dep_subgrid_merged.tif`` (built by
``build_merged_subgrid_dep``), the all-level bed the floodmap downscale prefers —
staging REFUSES a source without it when the template has one, because the scorer's
lev3 fallback is silent.

Cost on v3: ~47 min, ~20 GB RSS (SLURM 61230804), plus the merge. Submit
``hpc/rebuild_subgrid.slurm``
rather than running on a login node:

    sbatch hpc/rebuild_subgrid.slurm --dst _subgrid_buildings --overlay bed_buildings_v3
    sbatch hpc/rebuild_subgrid.slurm --dst _subgrid_x --overlay <burn> --overlay <lake>:min
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pyproj  # noqa: F401,E402  (before hydromt_sfincs: native double-free)
import xarray as xr  # noqa: E402
from build_merged_subgrid_dep import build_merged  # noqa: E402

from hydromt_sfincs import SfincsModel  # noqa: E402
from nj_sfincs import domain as _domain  # noqa: E402
from nj_sfincs import premier  # noqa: E402
from nj_sfincs.config import BaseConfig, exp_root  # noqa: E402


def _pct(a):
    a = np.asarray(a, dtype=float)
    a = a[np.isfinite(a)]
    if a.size == 0:
        return {}
    return {
        "n": int(a.size),
        "min": float(a.min()),
        "p50": float(np.percentile(a, 50)),
        "p90": float(np.percentile(a, 90)),
        "p99": float(np.percentile(a, 99)),
        "max": float(a.max()),
        "sum": float(a.sum()),
    }


# --overlay <key>[:<mode>] → the merge_method marker the wrapper reads. "" = plain paint.
OVERLAY_MODES = {"": "overlay", "min": "overlay_min"}
OVERLAY_METHODS = frozenset(OVERLAY_MODES.values())


def parse_overlay(token: str) -> tuple[str, str]:
    """``"key"`` → ``("key", "overlay")``; ``"key:min"`` → ``("key", "overlay_min")``.

    Catalog keys carry no ``:`` (data/data_catalog.yml), so the suffix is unambiguous;
    an unknown suffix is refused rather than read as part of a key."""
    key, sep, mode = token.rpartition(":")
    if not sep:
        return token, OVERLAY_MODES[""]
    if not key or mode not in OVERLAY_MODES or not mode:
        raise SystemExit(
            f"--overlay {token!r}: unknown mode {mode!r} "
            f"(valid: '<key>' or '<key>:min')"
        )
    return key, OVERLAY_MODES[mode]


def install_overlay_merge() -> None:
    """Wrap the quadtree builder's ``merge_multi_dataarrays`` so that entries marked
    ``merge_method == "overlay"`` are removed from hydromt's merge and painted on the
    merged block afterwards with NEAREST resampling where valid.

    Everything hydromt does for the other entries is untouched (same function, same
    arguments, same lattice), so pixels the overlay does not cover are bit-identical to
    a build without it. Applies to every call the builder makes — the cell-centre block,
    the uv-point block and the Manning block (which carries overlay entries only under
    ``--manning-overlay``; otherwise it passes straight through).

    ``merge_method == "overlay_min"`` (``--overlay <key>:min``) paints only where the
    overlay is LOWER than the block so far (or the block is NoData): the result is
    ``min(block, overlay)`` where the overlay is valid. Overlays are applied in list
    order, each on the result of the previous one, so a later entry wins either way.
    """
    from hydromt_sfincs.components.quadtree import (
        subgrid_quadtree_builder as bld,  # noqa: PLC0415
    )

    orig = bld.merge_multi_dataarrays

    def merge_with_overlay(da_list, gdf_list=[], da_like=None, **kw):  # noqa: B006
        overlays = [d for d in da_list if d.get("merge_method") in OVERLAY_METHODS]
        rest = [d for d in da_list if d.get("merge_method") not in OVERLAY_METHODS]
        out = orig(da_list=rest, gdf_list=gdf_list, da_like=da_like, **kw)
        for d in overlays:
            da = d["da"]
            bb = out.raster.transform_bounds(da.raster.crs)
            try:
                clip = da.raster.clip_bbox(bb, buffer=2)
            except (ValueError, IndexError):
                continue
            if np.any(np.array(clip.shape) <= 2):
                continue
            ov = clip.load().raster.reproject_like(out, method="nearest")
            ov = ov.raster.mask_nodata()
            valid = np.isfinite(ov.values)
            if not valid.any():
                continue
            nodata = out.raster.nodata
            if d.get("merge_method") == "overlay_min":
                # never raise: paint only where the overlay is lower, or where the
                # block has no value (NaN / its nodata) — i.e. min(block, overlay)
                cur = out.values
                have = np.isfinite(cur)
                if nodata is not None and np.isfinite(nodata):
                    have &= cur != nodata
                valid &= ~have | (ov.values < cur)
            out = out.where(~valid, ov)
            out.raster.set_nodata(nodata)
        return out

    bld.merge_multi_dataarrays = merge_with_overlay
    print("    overlay merge installed (nearest paint after hydromt's merge)")


def diff_subgrid(new: Path, old: Path, grid: Path, manning: bool = False) -> dict:
    """Per-face and per-uv diff of two subgrid tables built on the same mesh.

    ``manning=True`` adds the Manning-bearing uv tables (``--manning-overlay``)."""
    a = xr.open_dataset(new / "sfincs_subgrid.nc")
    b = xr.open_dataset(old / "sfincs_subgrid.nc")
    g = xr.open_dataset(grid)
    assert a.sizes == b.sizes, (dict(a.sizes), dict(b.sizes))
    msk = g["mask"].values
    act = msk > 0
    bnd = msk == 2
    out = {
        "np": int(a.sizes["np"]),
        "npuv": int(a.sizes["npuv"]),
        "levels": int(a.sizes["levels"]),
    }
    for k in ("z_zmin", "z_zmax", "z_volmax"):
        d = a[k].values - b[k].values
        ch = np.isfinite(d) & (np.abs(d) > 1e-6)
        out[k] = {
            "n_changed": int(ch.sum()),
            "n_changed_active": int((ch & act).sum()),
            "n_changed_boundary": int((ch & bnd).sum()),
            "delta": _pct(d[ch]),
        }
    for k in ("uv_zmin", "uv_zmax"):
        d = a[k].values - b[k].values
        ch = np.isfinite(d) & (np.abs(d) > 1e-6)
        out[k] = {"n_changed": int(ch.sum()), "delta": _pct(d[ch])}
    if manning:
        # the uv tables that carry n (only under --manning-overlay, so a bed-only
        # rebuild's diff file keeps its pre-flag keys)
        for k in ("uv_navg", "uv_ffit"):
            d = a[k].values - b[k].values
            ch = np.isfinite(d) & (np.abs(d) > 1e-7)
            out[k] = {"n_changed": int(ch.sum()), "delta": _pct(d[ch])}
        for k in ("uv_nrep", "uv_havg", "uv_pwet"):
            d = (a[k] - b[k]).transpose("levels", "npuv").values
            ch = np.isfinite(d) & (np.abs(d) > 1e-7)
            out[k] = {
                "n_uv_changed": int(ch.any(axis=0).sum()),
                "delta_top_level": _pct(d[-1][ch[-1]]),
            }
    nl = out["levels"]
    for tag, ds in (("new", a), ("old", b)):
        zmin, zmax = ds.uv_zmin.values, ds.uv_zmax.values
        land = np.isfinite(zmin) & (zmin > 0.5)
        out[f"uv_dlevel_land_{tag}"] = _pct((zmax[land] - zmin[land]) / (nl - 1))
    # a cell whose z_zmin rose above its old z_zmax is fully blocked
    full = np.isfinite(a.z_zmin.values) & (a.z_zmin.values > b.z_zmax.values + 1e-6)
    out["n_fully_blocked_active_cells"] = int((full & act).sum())
    out["n_fully_blocked_boundary_cells"] = int((full & bnd).sum())
    return out


def input_lists(args, base, validate_only=False) -> tuple[list[dict], list[dict]]:
    """The hydromt ``elevation_list`` and ``roughness_list`` for this rebuild.

    Overlays go LAST in each list so hydromt's own merge (which the wrapper runs on the
    non-overlay entries) sees exactly the premier's tiers in the premier's order; the
    NLCD reclass stays FIRST and untouched in the roughness list. Without
    ``--manning-overlay`` the roughness list is the premier's one-entry list.
    ``--overlay <key>:min`` gives ``merge_method: "overlay_min"`` in the same slot.
    """
    for t in args.manning_overlay:
        if ":" in t:
            raise SystemExit(
                f"--manning-overlay {t!r}: modes apply to bed overlays only"
            )
    overlays = [parse_overlay(t) for t in args.overlay]
    if validate_only:
        return [], []
    elevation_list = (
        [{"elevation": t, "reproj_method": args.reproj_method} for t in args.tier]
        + base.elevation()
        + [{"elevation": k, "merge_method": m} for k, m in overlays]
    )
    roughness_list = [
        {"lulc": base.roughness_lulc, "reclass_table": str(base.reclass_table)}
    ] + [{"manning": t, "merge_method": "overlay"} for t in args.manning_overlay]
    return elevation_list, roughness_list


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument(
        "--dst",
        required=True,
        help="dir name under experiments/<domain>/ (convention: _subgrid_<what>)",
    )
    ap.add_argument(
        "--overlay",
        action="append",
        default=[],
        help="data-catalog source(s) painted ON TOP of the premier's merged "
        "elevation with nearest resampling where valid, in the order given "
        "(later wins; the burn path). '<key>:min' = LOWER-ONLY: the pixel "
        "becomes min(bed so far, overlay), never raised (see the module "
        "docstring)",
    )
    ap.add_argument(
        "--tier",
        action="append",
        default=[],
        help="data-catalog elevation source(s) to PREPEND to the merge, top "
        "first (for a survey meant to be merged; 🔴 NOT for a footprint burn)",
    )
    ap.add_argument(
        "--manning-overlay",
        action="append",
        default=[],
        help="data-catalog Manning-n raster(s) painted ON TOP of the NLCD "
        "roughness merge with nearest resampling where valid (the same "
        "wrapper as --overlay; see the module docstring)",
    )
    ap.add_argument(
        "--reproj-method",
        default="nearest",
        help="hydromt reproj_method for --tier entries (honoured only on the "
        "first tier — hydromt forces bilinear on the rest)",
    )
    ap.add_argument(
        "--nr-levels", type=int, default=10, help="hydromt default 10 = premier"
    )
    ap.add_argument("--force", action="store_true", help="overwrite an existing --dst")
    args = ap.parse_args(argv)
    # refuse a bad ':mode' BEFORE --force removes the dst
    input_lists(args, None, validate_only=True)

    dom = _domain.active()
    base = BaseConfig()
    template = premier.sealed_template()
    dst = exp_root() / args.dst
    if not args.dst.startswith("_subgrid_"):
        raise SystemExit("--dst must start with '_subgrid_' (it is not a run dir)")
    if dst.exists():
        if not args.force:
            raise SystemExit(f"{dst} exists; pass --force to rebuild it")
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    t0 = time.time()

    # The mesh, byte for byte. A COPY, not a hard link: hydromt truncates in place on
    # write, and a link would let a stray write reach the sealed template.
    for f in ("sfincs.nc", "sfincs.inp"):
        shutil.copy2(template / f, dst / f)
    premier.assert_sealed_domain(dst, context=f"rebuild_subgrid --dst {args.dst}")

    if not args.overlay and not args.tier and not args.manning_overlay:
        raise SystemExit(
            "nothing to do: pass --overlay, --tier and/or --manning-overlay"
        )
    elevation_list, roughness_list = input_lists(args, base)
    print(f"[rebuild_subgrid] {dom.name} → {dst}")
    for e in elevation_list:
        print("   ", e)
    if args.manning_overlay:
        for r in roughness_list:
            print("    roughness:", r)
    print(f"    nr_subgrid_pixels={base.nr_subgrid_pixels} nr_levels={args.nr_levels}")
    if args.overlay or args.manning_overlay:
        install_overlay_merge()

    sf = SfincsModel(root=str(dst), data_libs=base.data_libs, mode="r+")
    sf.quadtree_grid.read()
    nf = sf.quadtree_grid.data.sizes.get("mesh2d_nFaces")
    print(f"    grid read: {nf} faces in {time.time() - t0:.0f}s", flush=True)

    t1 = time.time()
    sf.quadtree_subgrid.create(
        elevation_list=elevation_list,
        roughness_list=roughness_list,
        nr_subgrid_pixels=base.nr_subgrid_pixels,
        nr_levels=args.nr_levels,
        nrmax=2000,  # DO NOT lower — smaller explodes the block loop (model.py)
        write_dep_tif=True,
        write_man_tif=True,
    )
    sf.quadtree_subgrid.write()
    print(f"    subgrid built + written in {time.time() - t1:.0f}s", flush=True)
    del sf

    # The all-level bed the floodmap downscale needs. hydromt writes only the per-level
    # tifs; without this the scorer falls back to lev3 SILENTLY and scores the arm on
    # the finest-level faces alone (STATUS 2026-09-08: bed-buildings, row voided).
    t2 = time.time()
    build_merged(dst / "subgrid")  # lattice: Domain.merged_dep_base_level
    print(f"    dep_subgrid_merged.tif built in {time.time() - t2:.0f}s", flush=True)

    premier.assert_sealed_domain(dst, context="rebuild_subgrid output")
    diff = diff_subgrid(
        dst, template, dst / "sfincs.nc", manning=bool(args.manning_overlay)
    )
    (dst / "subgrid_diff.json").write_text(json.dumps(diff, indent=2))
    prov = {
        "built": datetime.now().isoformat(timespec="seconds"),
        "domain": dom.name,
        "template": str(template),
        "fingerprint": str(premier.domain_fingerprint(dst)),
        "prepended_tiers": args.tier,
        "overlay_tiers": args.overlay,
        "reproj_method": args.reproj_method,
        "elevation_list": elevation_list,
        "roughness_list": roughness_list,
        "nr_subgrid_pixels": base.nr_subgrid_pixels,
        "nr_levels": args.nr_levels,
        "seconds": round(time.time() - t0),
    }
    if args.manning_overlay:
        prov["manning_overlay_tiers"] = args.manning_overlay
    (dst / "provenance.txt").write_text(json.dumps(prov, indent=2))
    print(json.dumps(diff, indent=2))
    print(f"[rebuild_subgrid] DONE {dst} in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
