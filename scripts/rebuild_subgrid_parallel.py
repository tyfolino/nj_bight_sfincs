"""``scripts/rebuild_subgrid.py``, but the subgrid blocks run in a PROCESS POOL and every
finished block is CHECKPOINTED — same inputs, same outputs, bit for bit.

Same CLI as ``rebuild_subgrid.py`` (``--dst``, ``--overlay [key[:min]]``, ``--tier``,
``--manning-overlay``, ``--reproj-method``, ``--nr-levels``, ``--force``) plus:

* ``--workers N`` — pool size (default: the CPUs SLURM gave the job). Memory is per
  worker; see ``logs/subgrid_parallel_2026-11-04/README.md`` for the measured peak.
* ``--work-dir`` — the checkpoint dir (default
  ``<scratch>/nj_bight_sfincs/subgrid_par_work/<domain>/<dst>``, on the same filesystem as
  ``experiments/`` so the finished tifs are hard-linked, not copied). One small file per
  finished block (zstd pickle) plus the raster blocks until the tifs are written.
  ``manifest.json`` there records the mesh sha, the lists, the builder's and the overlay
  wrapper's sha and the catalog sha; a rerun with anything different is REFUSED.
* RESUME after a preemption / timeout: run the SAME command again with ``--force`` (the
  dst is rebuilt from the template as always; the finished blocks are not). ``--fresh``
  discards the checkpoints.
* ``--dst-root`` — put ``--dst`` somewhere other than ``experiments/<domain>/`` (tests).

The per-block code is the serial builder's (``nj_sfincs/subgrid_parallel.py``), the
``--overlay`` wrapper is ``rebuild_subgrid.install_overlay_merge`` itself, and the rest of
the pipeline (template copy, fingerprint asserts, ``dep_subgrid_merged.tif``,
``subgrid_diff.json``, ``provenance.txt``) calls ``rebuild_subgrid``'s functions; the
provenance gains ``builder`` / ``workers`` keys.

    NJ_DOMAIN=v4_refreeze_swz python scripts/rebuild_subgrid_parallel.py --workers 16 \\
        --dst _subgrid_x --overlay <bed> --overlay <lake>:min --manning-overlay manning_water_v4
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pyproj  # noqa: F401,E402  (before hydromt_sfincs: native double-free)
from rebuild_subgrid import diff_subgrid, input_lists  # noqa: E402

from nj_sfincs import domain as _domain  # noqa: E402
from nj_sfincs import premier  # noqa: E402
from nj_sfincs import subgrid_parallel as sp  # noqa: E402
from nj_sfincs.config import BaseConfig, exp_root  # noqa: E402

TIF_NAMES = ("dep_subgrid_lev{}.tif", "manning_subgrid_lev{}.tif")


def _default_workers() -> int:
    for k in ("SLURM_CPUS_PER_TASK", "SLURM_CPUS_ON_NODE"):
        if os.environ.get(k, "").isdigit():
            return int(os.environ[k])
    return len(os.sched_getaffinity(0))


def _link_or_copy(src: Path, dst: Path) -> None:
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument(
        "--dst", required=True, help="dir name (convention: _subgrid_<what>)"
    )
    ap.add_argument(
        "--overlay", action="append", default=[], help="as rebuild_subgrid.py"
    )
    ap.add_argument("--tier", action="append", default=[], help="as rebuild_subgrid.py")
    ap.add_argument(
        "--manning-overlay", action="append", default=[], help="as rebuild_subgrid.py"
    )
    ap.add_argument("--reproj-method", default="nearest", help="as rebuild_subgrid.py")
    ap.add_argument("--nr-levels", type=int, default=10, help="hydromt default 10")
    ap.add_argument("--force", action="store_true", help="overwrite an existing --dst")
    ap.add_argument("--workers", type=int, default=None, help="pool size")
    ap.add_argument("--work-dir", default=None, help="checkpoint dir (see docstring)")
    ap.add_argument(
        "--dst-root", default=None, help="parent of --dst (default exp_root)"
    )
    ap.add_argument("--fresh", action="store_true", help="discard existing checkpoints")
    ap.add_argument(
        "--keep-work", action="store_true", help="keep the checkpoint dir after success"
    )
    ap.add_argument("--gdal-cachemax", type=int, default=512, help="MB per worker")
    ap.add_argument(
        "--tif-threads", type=int, default=8, help="GDAL threads per tif written"
    )
    ap.add_argument(
        "--heavy-cap",
        type=int,
        default=None,
        help="max lev0 blocks in flight at once (default workers//4, min 2): bounds "
        "the memory peak",
    )
    ap.add_argument(
        "--max-tasks-per-child",
        type=int,
        default=None,
        help="recycle a worker after N blocks (bounds memory creep)",
    )
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    input_lists(args, None, validate_only=True)  # refuse a bad ':mode' first

    dom = _domain.active()
    base = BaseConfig()
    template = premier.sealed_template()
    if not args.dst.startswith("_subgrid_"):
        raise SystemExit("--dst must start with '_subgrid_' (it is not a run dir)")
    dst = (Path(args.dst_root) if args.dst_root else exp_root()) / args.dst
    if not args.overlay and not args.tier and not args.manning_overlay:
        raise SystemExit(
            "nothing to do: pass --overlay, --tier and/or --manning-overlay"
        )
    work = (
        Path(args.work_dir)
        if args.work_dir
        else exp_root().resolve().parents[1] / "subgrid_par_work" / dom.name / args.dst
    )
    workers = args.workers or _default_workers()

    if dst.exists():
        if not args.force:
            raise SystemExit(
                f"{dst} exists; pass --force to rebuild it (checkpoints in {work} "
                "are reused when their manifest matches)"
            )
        shutil.rmtree(dst)
    if args.fresh and work.exists():
        shutil.rmtree(work)
    dst.mkdir(parents=True)
    t0 = time.time()
    # The mesh, byte for byte (a COPY: hydromt truncates in place on write).
    for f in ("sfincs.nc", "sfincs.inp"):
        shutil.copy2(template / f, dst / f)
    premier.assert_sealed_domain(
        dst, context=f"rebuild_subgrid_parallel --dst {args.dst}"
    )

    elevation_list, roughness_list = input_lists(args, base)
    print(f"[rebuild_subgrid_parallel] {dom.name} → {dst}  ({workers} workers)")
    print(f"    checkpoints: {work}")
    for e in elevation_list:
        print("   ", e)
    if args.manning_overlay:
        for r in roughness_list:
            print("    roughness:", r)
    print(f"    nr_subgrid_pixels={base.nr_subgrid_pixels} nr_levels={args.nr_levels}")

    params = sp.BuildParams(
        nr_levels=args.nr_levels, nr_subgrid_pixels=base.nr_subgrid_pixels
    )
    builder = sp.ParallelSubgridBuilder(
        root=dst,
        data_libs=base.data_libs,
        elevation_list=elevation_list,
        roughness_list=roughness_list,
        params=params,
        work_dir=work,
        workers=workers,
        install_overlay=bool(args.overlay or args.manning_overlay),
        gdal_cachemax_mb=args.gdal_cachemax,
        max_tasks_per_child=args.max_tasks_per_child,
        tif_threads=args.tif_threads,
        heavy_cap=args.heavy_cap,
    )
    sf = builder.open_model()
    nf = sf.quadtree_grid.data.sizes.get("mesh2d_nFaces")
    print(f"    grid read: {nf} faces in {time.time() - t0:.0f}s", flush=True)

    t1 = time.time()
    arr = builder.build(sf)
    print(f"    blocks done in {time.time() - t1:.0f}s {builder.timings}", flush=True)

    print(f"    tifs: {builder.tif_results}", flush=True)
    (dst / "subgrid").mkdir(exist_ok=True)
    for li in builder.geo.levels:
        if li is None:
            continue
        for name in TIF_NAMES:
            src = work / "subgrid" / name.format(li.ilev)
            if src.exists():
                _link_or_copy(src, dst / "subgrid" / src.name)

    t3 = time.time()
    sf.quadtree_subgrid._data = builder.dataset(arr)
    sf.quadtree_subgrid.write()
    print(f"    sfincs_subgrid.nc written in {time.time() - t3:.0f}s", flush=True)
    print(f"    subgrid built + written in {time.time() - t1:.0f}s", flush=True)
    del sf, arr

    t4 = time.time()
    sp.build_merged_parallel(dst / "subgrid", workers=workers, threads=args.tif_threads)
    print(f"    dep_subgrid_merged.tif built in {time.time() - t4:.0f}s", flush=True)

    premier.assert_sealed_domain(dst, context="rebuild_subgrid_parallel output")
    diff = diff_subgrid(
        dst, template, dst / "sfincs.nc", manning=bool(args.manning_overlay)
    )
    (dst / "subgrid_diff.json").write_text(json.dumps(diff, indent=2))
    summary = sp.summarize_stats(builder.stats)
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
    prov["builder"] = "nj_sfincs.subgrid_parallel (scripts/rebuild_subgrid_parallel.py)"
    prov["workers"] = workers
    (dst / "provenance.txt").write_text(json.dumps(prov, indent=2))
    print(json.dumps(diff, indent=2))
    print("[block stats]", json.dumps(summary, indent=1))
    if args.keep_work:
        (work / "block_stats.json").write_text(json.dumps(builder.stats))
    else:
        builder.cleanup()
    print(f"[rebuild_subgrid_parallel] DONE {dst} in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
