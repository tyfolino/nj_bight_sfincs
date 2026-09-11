#!/usr/bin/env python
"""Does a native SFINCS binary reproduce the container? Cut, run, compare.

    python scripts/engine_gate.py make    <src_run> <dst> [--hours H]
    python scripts/engine_gate.py run     <dir> (--sif X.sif | --bin sfincs) [--threads N]
    python scripts/engine_gate.py compare <a> <b> [--json out.json]

Written 2026-09-11 (plan Phase 1a). The three gate cases are G1 (the hydromt
`sfincs_compound` example, no SnapWave, full window), G2 (`v1_monmouth/faber-waves-premier`,
12 h, SnapWave) and G3 (a v3 wind-on cut, 12 h) — each run once on the container and once
on the native build, then `compare`d.

`make` builds a gate dir from a finished run: every INPUT is hard-linked (same filesystem)
or copied, `sfincs.inp` is copied with `tstop = tstart + H hours` and the restart keys
dropped. 🔴 Outputs are NEVER linked — SFINCS truncates `sfincs_map.nc` / `sfincs_his.nc` /
`snapwave.upw` on create, so a linked output would clobber the source run's file through
the shared inode. `make` also refuses a source whose map is younger than 30 minutes (a job
may still be writing it). Gate dirs belong under `/scratch/tpj8/engine_gate/`, OUTSIDE
`experiments/`, so the premier audit, dedupe and backup never see them.

`run` executes the engine with the SAME environment `hpc/sfincs_run.slurm` uses (stack
unlimited, `OMP_STACKSIZE=1G`, `OMP_NUM_THREADS`, `OMP_PROC_BIND=spread`, `OMP_PLACES=cores`,
`numactl --interleave=all`), so the only difference between the two runs is the binary.
It writes `gate_run.txt` (engine path + sha256, host, threads, wall seconds).

`compare` reads both `sfincs_map.nc` (and `sfincs.log` for the SnapWave iteration counts)
and prints |Δ| statistics. Verdict and exit code:

    STRICT (0)  zs, zsmax max|Δ| ≤ 1e-6 m; hm0 max|Δ| ≤ 1e-4 m; boundary wavdir identical;
                per-call iteration counts identical
    ACCEPT (1)  zs p90 ≤ 0.2 mm and max ≤ 8 mm (the measured restart-noise scale, STATUS
                09-10); hm0 p99 ≤ 1 cm and max ≤ 5 cm; wavdir ≤ 0.5°; iterations ±1
    FAIL   (2)  anything worse — do NOT patch on a FAIL; try the other compiler first

`hm0` / `wavdir` are compared on cells finite in BOTH runs (`zb` and the wave fields are
NaN off their masks, FINDINGS §37). Regular-grid (2-D) and quadtree (1-D) maps both work —
everything is flattened.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import resource
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

STALE_MIN = 30
#: inputs, by glob, relative to the run dir. Anything not matched is NOT staged.
INPUT_GLOBS = (
    "sfincs.nc",
    "sfincs_subgrid.nc",
    "roughness.nc",
    "sfincs_net*.nc",
    "snapwave.b*",
    "sfincs.obs",
    "sfincs.weir",
    "sfincs.crs",
    "sfincs.thd",
    "sfincs.drn",
    # regular-grid (binary-input) models, e.g. the hydromt example
    "sfincs.dep",
    "sfincs.msk",
    "sfincs.ind",
    "sfincs.manning",
    "sfincs.bnd",
    "sfincs.bzs",
    "sfincs.src",
    "sfincs.dis",
    "sfincs.wnd",
    "sfincs.prcp",
    "sfincs.spw",
    "sfincs.sbg",
    "sfincs.qtr",
    "sfincs.rgh",
    "sfincs.wvm",
)
INPUT_DIRS = ("subgrid",)
#: never staged, never linked — the solver (re)creates these
OUTPUT_NAMES = {
    "sfincs_map.nc",
    "sfincs_his.nc",
    "snapwave.upw",
    "sfincs.log",
    "sfincs_log.txt",
    "restart_history.txt",
}
DROP_KEYS = ("dtrstout", "rstfile", "trstout")


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _parse_t(s: str):
    s = s.strip().strip("'\"")
    m = re.match(r"(\d{4})(\d{2})(\d{2})\s+(\d{2})(\d{2})(\d{2})", s)
    if not m:
        raise SystemExit(f"cannot parse time {s!r}")
    y, mo, d, h, mi, se = m.groups()
    return np.datetime64(f"{y}-{mo}-{d}T{h}:{mi}:{se}")


def _fmt_t(t: np.datetime64) -> str:
    s = str(t.astype("datetime64[s]"))
    return s[:4] + s[5:7] + s[8:10] + " " + s[11:13] + s[14:16] + s[17:19]


def _link_or_copy(src: Path, dst: Path) -> str:
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(src, dst)
        return "linked"
    except OSError:
        shutil.copy2(src, dst)
        return "copied"


# ── make ──────────────────────────────────────────────────────────────────────────


def make(src: Path, dst: Path, hours: float | None) -> None:
    src, dst = Path(src).resolve(), Path(dst).resolve()
    inp = src / "sfincs.inp"
    if not inp.is_file():
        raise SystemExit(f"{src}: no sfincs.inp")
    mp = src / "sfincs_map.nc"
    if mp.exists():
        age_min = (time.time() - mp.stat().st_mtime) / 60
        if age_min < STALE_MIN:
            raise SystemExit(
                f"REFUSING: {mp} is {age_min:.0f} min old (< {STALE_MIN}) — a job may still "
                f"be writing it. Cut a finished run."
            )
    if dst.exists() and any(dst.iterdir()):
        raise SystemExit(f"REFUSING: {dst} exists and is not empty")
    dst.mkdir(parents=True, exist_ok=True)

    n_link = n_copy = 0
    staged: list[str] = []
    for pat in INPUT_GLOBS:
        for p in sorted(src.glob(pat)):
            if not p.is_file() or p.name in OUTPUT_NAMES:
                continue
            how = _link_or_copy(p, dst / p.name)
            n_link += how == "linked"
            n_copy += how == "copied"
            staged.append(p.name)
    for d in INPUT_DIRS:
        sd = src / d
        if sd.is_dir():
            for p in sorted(sd.rglob("*")):
                if p.is_file():
                    how = _link_or_copy(p, dst / p.relative_to(src))
                    n_link += how == "linked"
                    n_copy += how == "copied"
            staged.append(d + "/")

    text = inp.read_text()
    keys = {}
    for ln in text.splitlines():
        if "=" in ln:
            k, _, v = ln.partition("=")
            keys[k.strip()] = v.strip()
    out = []
    for ln in text.splitlines():
        k = ln.partition("=")[0].strip()
        if k in DROP_KEYS:
            continue
        line = ln
        if hours is not None and k == "tstop":
            tstop = _parse_t(keys["tstart"]) + np.timedelta64(
                int(round(hours * 3600)), "s"
            )
            line = f"{'tstop':<20} = {_fmt_t(tstop)}"
        out.append(line)
    (dst / "sfincs.inp").write_text("\n".join(out) + "\n")
    (dst / "gate_source.txt").write_text(
        f"source  {src}\nhours   {hours if hours is not None else 'full'}\n"
        f"staged  {' '.join(staged)}\nlinked  {n_link}\ncopied  {n_copy}\n"
    )
    print(
        f"{dst}: {n_link} linked, {n_copy} copied, tstop → "
        f"{keys['tstop'] if hours is None else _fmt_t(tstop)}; dropped {DROP_KEYS}"
    )


# ── run ───────────────────────────────────────────────────────────────────────────


def run(d: Path, sif: Path | None, binary: Path | None, threads: int | None) -> int:
    d = Path(d).resolve()
    if (sif is None) == (binary is None):
        raise SystemExit("exactly one of --sif / --bin")
    engine = Path(sif or binary).resolve()
    if not engine.exists():
        raise SystemExit(f"no engine at {engine}")
    if binary is not None and not os.access(engine, os.X_OK):
        raise SystemExit(f"{engine} is not executable")
    for stale in ("sfincs_map.nc", "sfincs_his.nc"):
        (d / stale).unlink(missing_ok=True)
    n = str(
        threads
        or os.environ.get("SLURM_CPUS_PER_TASK")
        or os.environ.get("OMP_NUM_THREADS")
        or os.cpu_count()
        or 1
    )
    env = {
        **os.environ,
        "OMP_NUM_THREADS": n,
        "OMP_STACKSIZE": "1G",
        "OMP_PROC_BIND": "spread",
        "OMP_PLACES": "cores",
    }
    for pfx in ("SINGULARITYENV_", "APPTAINERENV_"):
        for k in ("OMP_NUM_THREADS", "OMP_STACKSIZE", "OMP_PROC_BIND", "OMP_PLACES"):
            env[pfx + k] = env[k]
    libdir = os.environ.get("SFINCS_BIN_LIBDIR")
    if binary is not None and libdir:
        env["LD_LIBRARY_PATH"] = libdir + ":" + env.get("LD_LIBRARY_PATH", "")
    numa = ["numactl", "--interleave=all"] if shutil.which("numactl") else []
    if sif is not None:
        cmd = numa + [
            "singularity",
            "run",
            "--bind",
            f"{d}:/data",
            "--pwd",
            "/data",
            str(engine),
        ]
    else:
        cmd = numa + [str(engine)]

    def _unlimit():
        try:
            hard = resource.getrlimit(resource.RLIMIT_STACK)[1]
            resource.setrlimit(resource.RLIMIT_STACK, (hard, hard))
        except (ValueError, OSError):
            pass

    print(f"[gate] {'sif' if sif else 'bin'}={engine}  threads={n}  cwd={d}")
    t0 = time.time()
    with open(d / "sfincs_log.txt", "w") as lf:
        rc = subprocess.run(
            cmd,
            cwd=str(d),
            stdout=lf,
            stderr=subprocess.STDOUT,
            env=env,
            preexec_fn=_unlimit,
            check=False,
        ).returncode
    wall = time.time() - t0
    (d / "gate_run.txt").write_text(
        f"engine   {'sif' if sif else 'bin'}:{engine}\nsha256   {_sha256(engine)}\n"
        f"host     {os.uname().nodename}\nthreads  {n}\nwall_s   {wall:.1f}\n"
        f"exit     {rc}\nnumactl  {bool(numa)}\n"
    )
    print(f"[gate] exit {rc} after {wall:.0f} s")
    return rc


# ── compare ───────────────────────────────────────────────────────────────────────

_ITER = re.compile(r"\s*iteration\s+(\d+)\s+error =")


def _iterations(log: Path) -> list[int]:
    calls, cur = [], None
    if not log.is_file():
        return calls
    for line in open(log, errors="ignore"):
        m = _ITER.match(line)
        if not m:
            continue
        it = int(m.group(1))
        if it == 1 and cur is not None:
            calls.append(cur)
        cur = it
    if cur is not None:
        calls.append(cur)
    return calls


def _wall(d: Path) -> float | None:
    f = d / "gate_run.txt"
    if f.is_file():
        for ln in f.read_text().splitlines():
            if ln.startswith("wall_s"):
                return float(ln.split()[1])
    return None


def _stats(a: np.ndarray, b: np.ndarray) -> dict:
    a, b = np.asarray(a, float).ravel(), np.asarray(b, float).ravel()
    ok = np.isfinite(a) & np.isfinite(b)
    if a.shape != b.shape:
        return {"n": 0, "shape_mismatch": [list(a.shape), list(b.shape)]}
    d = np.abs(a[ok] - b[ok])
    if d.size == 0:
        return {"n": 0}
    return {
        "n": int(d.size),
        "max": float(d.max()),
        "p99": float(np.percentile(d, 99)),
        "p90": float(np.percentile(d, 90)),
        "p50": float(np.median(d)),
        "n_finite_only_a": int((np.isfinite(a) & ~np.isfinite(b)).sum()),
        "n_finite_only_b": int((np.isfinite(b) & ~np.isfinite(a)).sum()),
    }


def compare(a: Path, b: Path, json_out: Path | None) -> int:
    import xarray as xr

    a, b = Path(a), Path(b)
    ma = xr.open_dataset(a / "sfincs_map.nc", decode_times=False)
    mb = xr.open_dataset(b / "sfincs_map.nc", decode_times=False)
    res: dict = {"a": str(a), "b": str(b), "fields": {}}
    for v in ("zs", "zsmax", "h", "hm0", "tp", "hm0ig"):
        if v in ma and v in mb:
            res["fields"][v] = _stats(ma[v].values, mb[v].values)
    if "wavdir" in ma and "wavdir" in mb:
        wa, wb = ma["wavdir"].values.astype(float), mb["wavdir"].values.astype(float)
        ok = np.isfinite(wa) & np.isfinite(wb) & (wa < 360) & (wb < 360)
        dd = np.abs((wa[ok] - wb[ok] + 180.0) % 360.0 - 180.0)
        res["fields"]["wavdir"] = {
            "n": int(dd.size),
            "max": float(dd.max()) if dd.size else 0.0,
            "p99": float(np.percentile(dd, 99)) if dd.size else 0.0,
        }
        if "snapwavemsk" in ma:
            bnd = np.broadcast_to(ma["snapwavemsk"].values == 2, wa.shape)
            okb = ok & bnd
            db = np.abs((wa[okb] - wb[okb] + 180.0) % 360.0 - 180.0)
            res["fields"]["wavdir_boundary"] = {
                "n": int(db.size),
                "max": float(db.max()) if db.size else 0.0,
            }
    ia, ib = _iterations(a / "sfincs.log"), _iterations(b / "sfincs.log")
    res["iterations"] = {
        "a": ia,
        "b": ib,
        "n_calls": [len(ia), len(ib)],
        "max_abs_diff": (
            max(abs(x - y) for x, y in zip(ia, ib))
            if ia and ib and len(ia) == len(ib)
            else None
        ),
    }
    res["wall_s"] = {"a": _wall(a), "b": _wall(b)}
    res["time_steps"] = [int(ma.sizes.get("time", 0)), int(mb.sizes.get("time", 0))]

    f = res["fields"]

    def g(v, k, default=0.0):
        return f.get(v, {}).get(k, default)

    zs_max = max(g("zs", "max"), g("zsmax", "max"))
    zs_p90 = max(g("zs", "p90"), g("zsmax", "p90"))
    it_same = res["iterations"]["max_abs_diff"]
    strict = (
        zs_max <= 1e-6
        and g("hm0", "max") <= 1e-4
        and g("wavdir_boundary", "max") == 0.0
        and (it_same is None or it_same == 0)
        and res["time_steps"][0] == res["time_steps"][1]
    )
    accept = (
        zs_p90 <= 2e-4
        and zs_max <= 8e-3
        and g("hm0", "p99") <= 1e-2
        and g("hm0", "max") <= 5e-2
        and g("wavdir_boundary", "max") <= 0.5
        and (it_same is None or it_same <= 1)
        and res["time_steps"][0] == res["time_steps"][1]
    )
    verdict = "STRICT" if strict else ("ACCEPT" if accept else "FAIL")
    res["verdict"] = verdict

    print(f"engine gate: {a.name}  vs  {b.name}")
    print(
        f"{'field':<16}{'n':>10}{'max':>12}{'p99':>12}{'p90':>12}{'p50':>12}  only-a/only-b"
    )
    for v, s in f.items():
        if "max" in s:
            print(
                f"{v:<16}{s['n']:>10}{s['max']:>12.3e}{s.get('p99', 0):>12.3e}"
                f"{s.get('p90', 0):>12.3e}{s.get('p50', 0):>12.3e}  "
                f"{s.get('n_finite_only_a', 0)}/{s.get('n_finite_only_b', 0)}"
            )
        else:
            print(f"{v:<16}{s}")
    print(f"time steps      {res['time_steps']}")
    print(
        f"SnapWave calls  {res['iterations']['n_calls']}  max |Δiter| "
        f"{res['iterations']['max_abs_diff']}"
    )
    print(f"wall s          {res['wall_s']}")
    print(f"VERDICT         {verdict}")
    if json_out:
        Path(json_out).write_text(json.dumps(res, indent=2))
        print(f"wrote {json_out}")
    return {"STRICT": 0, "ACCEPT": 1, "FAIL": 2}[verdict]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__.split("\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("make")
    m.add_argument("src", type=Path)
    m.add_argument("dst", type=Path)
    m.add_argument(
        "--hours", type=float, default=None, help="window from tstart (default full)"
    )
    r = sub.add_parser("run")
    r.add_argument("dir", type=Path)
    r.add_argument("--sif", type=Path, default=None)
    r.add_argument("--bin", type=Path, default=None)
    r.add_argument("--threads", type=int, default=None)
    c = sub.add_parser("compare")
    c.add_argument("a", type=Path)
    c.add_argument("b", type=Path)
    c.add_argument("--json", type=Path, default=None)
    a = ap.parse_args(argv)
    if a.cmd == "make":
        make(a.src, a.dst, a.hours)
        return 0
    if a.cmd == "run":
        return run(a.dir, a.sif, a.bin, a.threads)
    return compare(a.a, a.b, a.json)


if __name__ == "__main__":
    sys.exit(main())
