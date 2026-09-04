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

**Diff ``z_volmax``, not ``z_zmin``** (CLAUDE.md §5): a footprint burn restores sub-cell
relief, and ``z_zmin`` moves only where a cell is FULLY covered. ``subgrid_diff.json``
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

Cost on v3: ~47 min, ~20 GB RSS (SLURM 61230804). Submit ``hpc/rebuild_subgrid.slurm``
rather than running on a login node:

    sbatch hpc/rebuild_subgrid.slurm --dst _subgrid_buildings --overlay bed_buildings_v3
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

import pyproj  # noqa: F401,E402  (before hydromt_sfincs: native double-free)
import xarray as xr  # noqa: E402
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


def install_overlay_merge() -> None:
    """Wrap the quadtree builder's ``merge_multi_dataarrays`` so that entries marked
    ``merge_method == "overlay"`` are removed from hydromt's merge and painted on the
    merged block afterwards with NEAREST resampling where valid.

    Everything hydromt does for the other entries is untouched (same function, same
    arguments, same lattice), so pixels the overlay does not cover are bit-identical to
    a build without it. Applies to every call the builder makes — the cell-centre block,
    the uv-point block and the Manning block (which carries no overlay entries and
    passes straight through).
    """
    from hydromt_sfincs.components.quadtree import subgrid_quadtree_builder as bld  # noqa: PLC0415

    orig = bld.merge_multi_dataarrays

    def merge_with_overlay(da_list, gdf_list=[], da_like=None, **kw):  # noqa: B006
        overlays = [d for d in da_list if d.get("merge_method") == "overlay"]
        rest = [d for d in da_list if d.get("merge_method") != "overlay"]
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
            out = out.where(~valid, ov)
            out.raster.set_nodata(nodata)
        return out

    bld.merge_multi_dataarrays = merge_with_overlay
    print("    overlay merge installed (nearest paint after hydromt's merge)")


def diff_subgrid(new: Path, old: Path, grid: Path) -> dict:
    """Per-face and per-uv diff of two subgrid tables built on the same mesh."""
    a = xr.open_dataset(new / "sfincs_subgrid.nc")
    b = xr.open_dataset(old / "sfincs_subgrid.nc")
    g = xr.open_dataset(grid)
    assert a.sizes == b.sizes, (dict(a.sizes), dict(b.sizes))
    msk = g["mask"].values
    act = msk > 0
    bnd = msk == 2
    out = {"np": int(a.sizes["np"]), "npuv": int(a.sizes["npuv"]),
           "levels": int(a.sizes["levels"])}
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dst", required=True,
                    help="dir name under experiments/<domain>/ (convention: _subgrid_<what>)")
    ap.add_argument("--overlay", action="append", default=[],
                    help="data-catalog source(s) painted ON TOP of the premier's merged "
                    "elevation with nearest resampling where valid (the burn path; "
                    "see the module docstring)")
    ap.add_argument("--tier", action="append", default=[],
                    help="data-catalog elevation source(s) to PREPEND to the merge, top "
                    "first (for a survey meant to be merged; 🔴 NOT for a footprint burn)")
    ap.add_argument("--reproj-method", default="nearest",
                    help="hydromt reproj_method for --tier entries (honoured only on the "
                    "first tier — hydromt forces bilinear on the rest)")
    ap.add_argument("--nr-levels", type=int, default=10, help="hydromt default 10 = premier")
    ap.add_argument("--force", action="store_true", help="overwrite an existing --dst")
    args = ap.parse_args(argv)

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

    if not args.overlay and not args.tier:
        raise SystemExit("nothing to do: pass --overlay and/or --tier")
    # Overlays go LAST in the list so hydromt's own merge (which the wrapper runs on the
    # non-overlay entries) sees exactly the premier's tiers in the premier's order.
    elevation_list = (
        [{"elevation": t, "reproj_method": args.reproj_method} for t in args.tier]
        + base.elevation()
        + [{"elevation": t, "merge_method": "overlay"} for t in args.overlay]
    )
    roughness_list = [
        {"lulc": base.roughness_lulc, "reclass_table": str(base.reclass_table)}
    ]
    print(f"[rebuild_subgrid] {dom.name} → {dst}")
    for e in elevation_list:
        print("   ", e)
    print(f"    nr_subgrid_pixels={base.nr_subgrid_pixels} nr_levels={args.nr_levels}")
    if args.overlay:
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

    premier.assert_sealed_domain(dst, context="rebuild_subgrid output")
    diff = diff_subgrid(dst, template, dst / "sfincs.nc")
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
    (dst / "provenance.txt").write_text(json.dumps(prov, indent=2))
    print(json.dumps(diff, indent=2))
    print(f"[rebuild_subgrid] DONE {dst} in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
