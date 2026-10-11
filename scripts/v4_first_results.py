#!/usr/bin/env python
"""The first waves-on v4 read, turnkey: setup, scores, paired marks, figures, summary.

WHAT IT WRITES (under ``--out``, default ``reports/v4_first_results_<preset date>/``)
-----------------------------------------------------------------------------------
``setup.csv``        per run: domain, arm, fingerprint, engine, waves, dtwave, subgrid,
                     rain / infiltration, solve wall time (sacct), node(s), the audit.
``headline.csv``     straight from each run's ``metrics.csv`` row: HWM n / bias / RMSE on
                     the ``_scored`` keys WITH ``hwm_estimator`` + ``hwm_radius_m``; MOTF
                     CSI / POD / FAR with ``extent_admissible`` and
                     ``motf_km2_excluded_boxes`` beside them.
``basins.csv``       the per-basin ``hwm_*_scored_<basin>`` keys, one block per run.
``gauges.csv``       per-gauge peak obs / model / error (``prefail`` pair where the gauge
                     died mid-storm).
``marks/<label>.csv`` per-mark residuals, one per run, computed by
                     ``scripts/paired_hwm_bootstrap.residuals`` (the authority) under the
                     run's OWN domain, and self-checked against its metrics row.
``paired.csv``       every pair: ALL + ``BASIN_GROUPS`` + per basin, joined on ``hwm_id``
                     over marks scored in BOTH runs, bootstrapped with
                     ``paired_hwm_bootstrap._boot``. A same-domain pair reproduces the
                     script's own ``--by-basin`` output digit for digit (same seed, same
                     mark order); a cross-domain pair (v4 vs v3) is read on the marks the
                     two SHARE.
``zsmax/``           per same-mesh pair: face-by-face zsmax A − B map (+ peak Hm0 of a
                     waves-on A) and per-basin stats. Read from ``sfincs_map.nc`` faces —
                     no raster, so the rotated-raster trap (CLAUDE.md §5) cannot apply.
``fig_*.png``        gauges (obs vs model per run; error table), HWM residual maps per pair.
``summary.md``       the brief skeleton: tables filled, prose marked ``TODO``.

STAGES (each is a subcommand; ``submit`` queues them all)
--------------------------------------------------------
``plan``       READ-ONLY: what is there (audit, metrics row, floodmap cache) + the jobs.
``residuals``  ONE run, heavy: a v4 run peaks ~210 GB (logs/audit_v4_hot_plus_2026-10-05/
               v4_vs_v3_deficit: maxRSS 211 GiB), v3 ~90 GB. One run per process, one
               process per job, so nothing accumulates (CLAUDE.md §5).
``zsmax``      ONE same-mesh pair, ~15 GB.
``report``     light: tables, paired bootstrap, figures, summary. Re-runnable any time;
               missing inputs are listed in the summary instead of failing.
``submit``     sbatch one ``residuals`` job per run, one ``zsmax`` job per same-mesh pair,
               then ``report`` (afterany). ``--after <jobids>`` chains it behind the
               validate jobs; ``--dry-run`` writes the job scripts and prints the sbatch
               lines without submitting. Each job checks an md5 of this script and of
               paired_hwm_bootstrap.py first (the halk late-write trap, CLAUDE.md §5).

GUARDS
------
* A run whose output is not WHOLE (``premier.output_complete``) is never scored.
* Nothing is written under ``experiments/``. A run whose floodmap cache is STALE is read
  through a shadow dir of symlinks on /scratch, so the downscale lands there.
* HWM numbers always carry estimator + radius (median, 50 m = the metrics.csv rows).
* A waves-off CSI is reported with ``extent_admissible=False`` beside it; a CSI is never
  shown without ``motf_km2_excluded_boxes`` (v3 and v4 score different MOTF rasters).

Usage::

    # Wednesday (or tonight, chained behind the validate jobs):
    python scripts/v4_first_results.py plan   --preset wednesday
    python scripts/v4_first_results.py submit --preset wednesday [--after 6228xxxx,...]
    # the test on the runs that exist now:
    python scripts/v4_first_results.py submit --preset test
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = "/home/tpj8/nj_sandy_sfincs/micromamba/envs/sfincs"
SHADOW_ROOT = Path("/scratch/tpj8/v4_first_results_shadow")
ESTIMATOR, RADIUS_M = "median", 50.0  # = the metrics.csv rows (hwm_estimator/radius)
SEED, N_BOOT = 20261007, 200_000  # = paired_hwm_bootstrap.py defaults

#: label -> path (repo-relative). ``role`` is free text for the setup table.
PRESETS: dict[str, dict] = {
    "wednesday": dict(
        date="2026-10-07",
        runs=[
            (
                "A_on",
                "experiments/v4_hot_plus/bed-buildings+bed-channels+naccs-premier",
                "run A, waves ON",
            ),
            (
                "A_off",
                "experiments/v4_hot_plus/bed-buildings+bed-channels+naccs-nowaves",
                "run A's waves-off twin",
            ),
            ("B_on", "experiments/v4_hot_plus_walls/naccs-premier", "run B, waves ON"),
            (
                "B_off",
                "experiments/v4_hot_plus_walls/naccs-nowaves",
                "run B's waves-off twin",
            ),
            (
                "Aplus_base",
                "experiments/v4_hot_plus/naccs-nowaves",
                "A+ waves-off on the template bed (dam crest)",
            ),
            (
                "harbour",
                "experiments/v4_hot_plus/bed-harbour+naccs-nowaves",
                "A+ waves-off + the harbour trench surveys only",
            ),
            ("v3", "experiments/v3/naccs-premier", "v3 reference (FINDINGS §50)"),
            ("v3_off", "experiments/v3/naccs-nowaves", "v3 waves-off"),
            ("v3_dt3600", "experiments/v3/wave-dt3600", "v3 hourly waves, old bed"),
            (
                "v3fix_on",
                "experiments/v3/bed-v4fixes+wave-dt3600",
                "v3 re-run: the shared bed fixes, hourly waves",
            ),
            (
                "v3fix_off",
                "experiments/v3/bed-v4fixes+naccs-nowaves",
                "v3 re-run's waves-off twin",
            ),
        ],
        pairs=[
            ("A_on", "A_off", "wave contribution, run A"),
            ("B_on", "B_off", "wave contribution, run B"),
            ("B_on", "A_on", "run B vs run A, waves on (walls + inflows + full bed)"),
            ("B_off", "A_off", "run B vs run A, waves off"),
            ("A_off", "Aplus_base", "the 10-05 bed alone (waves off)"),
            ("A_on", "v3", "v4 (A) vs v3 premier, shared marks"),
            ("B_on", "v3", "v4 (B) vs v3 premier, shared marks"),
            ("v3", "v3_off", "v3's own wave contribution (reference)"),
            ("harbour", "Aplus_base", "the harbour trench alone (waves off)"),
            ("harbour", "v3_off", "v4 harbour test vs v3, waves off (the Raritan gap)"),
            ("v3fix_on", "v3_dt3600", "the shared bed fixes on v3, hourly waves"),
            ("v3fix_off", "v3_off", "the shared bed fixes on v3, waves off"),
            ("v3fix_on", "v3fix_off", "v3 wave contribution on the fixed bed"),
            (
                "B_on",
                "v3fix_on",
                "v4 (B) vs v3, both on the shared fixes, hourly waves",
            ),
            ("B_off", "v3fix_off", "v4 (B) vs v3, both on the shared fixes, waves off"),
        ],
    ),
    # 2026-10-09: the re-frozen v4 (v4_refreeze) — its first scores, the NACCS-wind pairs,
    # and what the re-freeze changed against run B. B_* / v3fix_* marks are copied from
    # the 10-07 read (same runs, unchanged), not recomputed.
    # Paths updated 2026-10-11 for the re-baseline (the runs moved, not changed): the ERA5
    # pair is parked in _pre_rebaseline_2026-10-11/, the NACCS pair renamed into place.
    "refreeze": dict(
        date="2026-10-09",
        runs=[
            (
                "rf_on",
                "experiments/v4_refreeze/_pre_rebaseline_2026-10-11/naccs-premier",
                "v4 re-freeze, waves ON",
            ),
            (
                "rf_off",
                "experiments/v4_refreeze/_pre_rebaseline_2026-10-11/naccs-nowaves",
                "v4 re-freeze, waves-off twin",
            ),
            (
                "rfw_on",
                "experiments/v4_refreeze/naccs-premier",
                "v4 re-freeze, NACCS-blend wind, waves ON",
            ),
            (
                "rfw_off",
                "experiments/v4_refreeze/naccs-nowaves",
                "v4 re-freeze, NACCS-blend wind, waves off",
            ),
            ("B_on", "experiments/v4_hot_plus_walls/naccs-premier", "run B, waves ON"),
            (
                "B_off",
                "experiments/v4_hot_plus_walls/naccs-nowaves",
                "run B's waves-off twin",
            ),
            (
                "v3fix_on",
                "experiments/v3/bed-v4fixes+wave-dt3600",
                "v3 re-run: the shared bed fixes, hourly waves",
            ),
            (
                "v3fix_off",
                "experiments/v3/bed-v4fixes+naccs-nowaves",
                "v3 re-run's waves-off twin",
            ),
        ],
        pairs=[
            ("rf_on", "rf_off", "wave contribution, re-freeze"),
            ("rfw_off", "rf_off", "NACCS-blend wind vs ERA5, waves off"),
            ("rfw_on", "rf_on", "NACCS-blend wind vs ERA5, waves on"),
            (
                "rf_on",
                "B_on",
                "re-freeze vs run B, waves on (weir, meteo corner, Lewes)",
            ),
            ("rf_off", "B_off", "re-freeze vs run B, waves off"),
            ("rf_on", "v3fix_on", "v4 re-freeze vs v3, shared fixes, hourly waves"),
            ("rf_off", "v3fix_off", "v4 re-freeze vs v3, shared fixes, waves off"),
        ],
    ),
    # (the `_pre_damcrest` run this preset also paired was deleted 2026-10-11 —
    # reports/cleanup/deletion_manifest_2026-10-11.md; its row stays in metrics.csv)
    "test": dict(
        date="test",
        runs=[
            ("hp", "experiments/v4_hot_plus/naccs-nowaves", "A+ waves-off, dam crest"),
            ("v4", "experiments/v4/naccs-nowaves", "v4 waves-off"),
            ("v3", "experiments/v3/naccs-premier", "v3 reference (FINDINGS §50)"),
            ("v3_off", "experiments/v3/naccs-nowaves", "v3 waves-off"),
        ],
        pairs=[
            ("hp", "v4", "A+ vs v4 (head-of-tide trim)"),
            ("hp", "v3", "v4 family vs v3 premier, shared marks"),
            ("v3", "v3_off", "v3's wave contribution (tests the twin path)"),
        ],
    ),
}

#: Zoom windows for the zsmax maps, UTM 18N (x0, x1, y0, y1).
ZOOMS = {
    "NY bays / Raritan": (548_000, 600_000, 4_462_000, 4_500_000),
    "Barnegat Bay": (555_000, 592_000, 4_390_000, 4_440_000),
    "Great Bay / Atlantic City": (535_000, 575_000, 4_350_000, 4_392_000),
    "Cape May / Delaware Bay mouth": (480_000, 535_000, 4_292_000, 4_345_000),
}

INK, INK2, GRID = "#0b0b0b", "#52514e", "#d9d8d4"
SERIES1 = "#2a78d6"


# ── run description ─────────────────────────────────────────────────────────────────────


@dataclass
class Run:
    label: str
    path: Path
    role: str = ""

    @property
    def arm(self) -> str:
        return self.path.name

    @property
    def domain(self) -> str:
        prov = self.path / "provenance.txt"
        if prov.is_file():
            m = re.search(r"^\s*name\s+(\S+)\s+<- NJ_DOMAIN", prov.read_text(), re.M)
            if m:
                return m.group(1)
        # experiments/ is a symlink to /scratch: try the path as given, then resolved
        for p, base in (
            (self.path, ROOT / "experiments"),
            (self.path.resolve(), (ROOT / "experiments").resolve()),
        ):
            try:
                return p.relative_to(base).parts[0]
            except ValueError:
                continue
        return "?"

    @property
    def faces(self) -> int | None:
        prov = self.path / "provenance.txt"
        if prov.is_file():
            m = re.search(r"^\s*faces\s+([\d,]+)", prov.read_text(), re.M)
            if m:
                return int(m.group(1).replace(",", ""))
        return None

    @property
    def metrics_csv(self) -> Path:
        return self.path.parent / "metrics.csv"


def same_mesh(a: Run, b: Run) -> bool:
    """Same faces? From provenance when both runs exist, else the registry's mesh_key
    (so ``submit --after`` can plan the zsmax jobs before the runs are staged)."""
    if a.faces and b.faces:
        return a.faces == b.faces
    from nj_sfincs import domain as _domain

    def key(r):
        d = _domain.DOMAINS.get(r.domain)
        return (d.mesh_key or d.name) if d else None

    return key(a) is not None and key(a) == key(b)


def resolve(args) -> tuple[list[Run], list[tuple[str, str, str]], Path]:
    pre = PRESETS[args.preset] if args.preset else dict(date=str(date.today()))
    runs = {lab: Run(lab, ROOT / p, role) for lab, p, role in pre.get("runs", [])}
    for spec in args.run or []:
        lab, _, p = spec.partition("=")
        runs[lab] = Run(
            lab, (ROOT / p).resolve() if not Path(p).is_absolute() else Path(p)
        )
    pairs = list(pre.get("pairs", []))
    for spec in args.pair or []:
        a, b, *why = spec.split(":")
        pairs.append((a, b, why[0] if why else ""))
    for a, b, _ in pairs:
        for lab in (a, b):
            if lab not in runs:
                raise SystemExit(f"pair names an unknown run label {lab!r}")
    out = (
        Path(args.out)
        if args.out
        else ROOT / "reports" / f"v4_first_results_{pre['date']}"
    )
    return list(runs.values()), pairs, out


def inp(run: Run) -> dict[str, str]:
    f = run.path / "sfincs.inp"
    if not f.is_file():
        return {}
    out = {}
    for line in f.read_text().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def kv_file(p: Path) -> dict[str, str]:
    if not p.is_file():
        return {}
    out = {}
    for line in p.read_text().splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2:
            out[parts[0]] = parts[1].strip()
    return out


_METRICS: dict = {}


def metrics_row(run: Run) -> dict | None:
    f = run.metrics_csv
    if not f.is_file():
        return None
    key = (f, f.stat().st_mtime)
    if key not in _METRICS:
        _METRICS[key] = pd.read_csv(f, index_col=0, low_memory=False)
    df = _METRICS[key]
    if run.arm not in df.index:
        return None
    return df.loc[run.arm].to_dict()


def floodmap_fresh(run: Run) -> bool:
    fm, mp = run.path / "floodmap_hmax_lev3.tif", run.path / "sfincs_map.nc"
    dep = run.path / "subgrid" / "dep_subgrid_merged.tif"
    if not dep.is_file():
        dep = run.path / "subgrid" / "dep_subgrid_lev3.tif"
    if not (fm.is_file() and mp.is_file() and dep.is_file()):
        return False
    return (
        fm.stat().st_mtime >= mp.stat().st_mtime
        and fm.stat().st_mtime >= dep.stat().st_mtime
    )


def with_domain(name: str):
    os.environ["NJ_DOMAIN"] = name


def audit(run: Run) -> tuple[bool | None, str]:
    """(output whole?, one-line description) — premier's own audit, under the run's domain."""
    if not (run.path / "sfincs.nc").is_file():
        return None, "no run dir / sfincs.nc"
    with_domain(run.domain)
    from nj_sfincs import premier

    whole, gaps = premier.output_complete(run.path)
    try:
        fp = premier.domain_fingerprint(run.path)
        label = premier.KNOWN.get(fp, "UNRECOGNISED")
        sealed = (
            "sealed" if fp == premier.expected() else "NOT the domain's current seal"
        )
        fps = f"{fp.n_faces} faces, sha {fp.sha_z_mask}"
    except Exception as e:  # noqa: BLE001
        label, sealed, fps = "?", f"fingerprint error {e}", "?"
    state = {None: "no output", True: "output WHOLE"}.get(whole, "OUTPUT TRUNCATED")
    desc = f"{state}; {fps}; {sealed}; {label}" + "".join(f"; {g}" for g in gaps)
    return whole, desc


def sacct_info(job: str) -> dict:
    if not job or job == "none":
        return {}
    try:
        txt = subprocess.run(
            [
                "sacct",
                "-D",
                "-X",
                "-n",
                "-P",
                "-j",
                str(job),
                "--format=JobID,Elapsed,NodeList,State,Constraints",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return {}
    secs, nodes, states, cons = 0, [], [], set()
    for line in txt.strip().splitlines():
        f = line.split("|")
        if len(f) < 5:
            continue
        d, _, hms = f[1].rpartition("-")
        h, m, s = (int(x) for x in hms.split(":"))
        secs += int(d or 0) * 86400 + h * 3600 + m * 60 + s
        nodes.append(f[2])
        states.append(f[3])
        if f[4]:
            cons.add(f[4])
    return dict(
        wall_h=secs / 3600,
        nodes=",".join(nodes),
        states=",".join(states),
        constraint=",".join(sorted(cons)),
        attempts=len(states),
    )


def setup_row(run: Run) -> dict:
    i, eng = inp(run), kv_file(run.path / "engine.txt")
    m = metrics_row(run) or {}
    log = run.path / "sfincs.log"
    tot = None
    if log.is_file():
        mm = re.findall(r"Total time\s*:\s*([\d.]+)", log.read_text(errors="replace"))
        tot = float(mm[-1]) / 3600 if mm else None
    sa = sacct_info(eng.get("job_id", ""))
    whole, desc = audit(run)
    waves = i.get("snapwave", "0") == "1"
    span_h = 72.0
    wall = sa.get("wall_h")
    return {
        "label": run.label,
        "role": run.role,
        "domain": run.domain,
        "arm": run.arm,
        "path": str(run.path.relative_to(ROOT))
        if run.path.is_relative_to(ROOT)
        else str(run.path),
        "audit": desc.split("; ")[0],
        "seal": "; ".join(desc.split("; ")[1:3]),
        "audit_full": desc,
        "engine": eng.get("label") or m.get("engine", ""),
        "waves": "ON" if waves else "off",
        "dtwave_s": i.get("dtwave", "") if waves else "",
        "dtheta_deg": i.get("snapwave_dtheta", "") if waves else "",
        "ig": i.get("snapwave_igwaves", "") if waves else "",
        "snapwave_direction": m.get("snapwave_direction", ""),
        "rain": "on" if i.get("netamprfile") else "off",
        "infiltration": i.get("infiltration_type", "")
        or ("qinf" if i.get("qinf") else "none"),
        "subgrid": m.get("subgrid", ""),
        "solve_wall_h": round(wall, 2) if wall else "",
        "sim_h_per_wall_h": round(span_h / wall, 2) if wall else "",
        "sfincs_log_total_h": round(tot, 2) if tot else "",
        "nodes": sa.get("nodes", eng.get("host", "")),
        "constraint": sa.get("constraint", ""),
        "job_id": eng.get("job_id", ""),
        "attempts": sa.get("attempts", ""),
        "restart_count": eng.get("restart_count", ""),
        "metrics_row": "yes" if m else "MISSING",
        "floodmap_cache": "fresh" if floodmap_fresh(run) else "stale/missing",
    }


# ── headline / basins / gauges straight from metrics.csv ───────────────────────────────


HEADLINE_KEYS = [
    "hwm_estimator",
    "hwm_radius_m",
    "hwm_n_scored",
    "hwm_n_dry_scored",
    "hwm_bias_scored_m",
    "hwm_rmse_scored_m",
    "hwm_within0.5_scored",
    "motf_csi",
    "motf_pod",
    "motf_far",
    "extent_admissible",
    "motf_km2_excluded_boxes",
    "motf_km2_excluded_invalid",
    "motf_csi_connected",
    "motf_far_connected",
]


def headline(runs: list[Run]) -> pd.DataFrame:
    rows = []
    for r in runs:
        m = metrics_row(r) or {}
        row = {"label": r.label, "domain": r.domain, "arm": r.arm}
        row.update({k: m.get(k, np.nan) for k in HEADLINE_KEYS})
        rows.append(row)
    return pd.DataFrame(rows)


def basins(runs: list[Run]) -> pd.DataFrame:
    rows = []
    for r in runs:
        m = metrics_row(r) or {}
        names = sorted(
            k[len("hwm_n_scored_") :] for k in m if k.startswith("hwm_n_scored_")
        )
        for b in names:
            n = m.get(f"hwm_n_scored_{b}")
            if not n or pd.isna(n) or float(n) == 0:
                continue
            rows.append(
                dict(
                    label=r.label,
                    basin=b,
                    n_scored=int(float(n)),
                    n_dry=m.get(f"hwm_n_dry_{b}"),
                    bias_scored_m=m.get(f"hwm_bias_scored_{b}_m"),
                    rmse_scored_m=m.get(f"hwm_rmse_scored_{b}_m"),
                )
            )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.pivot(
        index="basin",
        columns="label",
        values=["n_scored", "bias_scored_m", "rmse_scored_m"],
    )


def gauges(runs: list[Run]) -> pd.DataFrame:
    rows = []
    for r in runs:
        m = metrics_row(r) or {}
        for k in m:
            g = re.fullmatch(r"peak_obs_(.+)_m", k)
            if not g:
                continue
            name = g.group(1)
            obs = m.get(k)
            pre = m.get(f"peak_err_prefail_{name}_m")
            prefail = pre is not None and not pd.isna(pre)
            mod = m.get(
                f"peak_mod_prefail_{name}_m" if prefail else f"peak_mod_full_{name}_m"
            )
            err = pre if prefail else m.get(f"peak_err_{name}_m")
            if obs is None or pd.isna(obs):
                continue
            rows.append(
                dict(
                    gauge=name,
                    label=r.label,
                    obs_m=float(obs),
                    mod_m=float(mod)
                    if mod is not None and not pd.isna(mod)
                    else np.nan,
                    err_m=float(err)
                    if err is not None and not pd.isna(err)
                    else np.nan,
                    prefail=prefail,
                    record_ends=m.get(f"peak_record_ends_{name}", "")
                    if prefail
                    else "",
                    lag_min=m.get(f"peak_lag_{name}_min", np.nan),
                )
            )
    return pd.DataFrame(rows)


# ── residuals (heavy, one run per process) ─────────────────────────────────────────────


def load_pb():
    spec = importlib.util.spec_from_file_location(
        "paired_hwm_bootstrap", ROOT / "scripts" / "paired_hwm_bootstrap.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def shadow_dir(run: Run) -> Path:
    """Symlink farm on /scratch so a stale floodmap's re-downscale lands outside
    experiments/ (the same trick as logs/audit_v4_hot_plus_2026-10-05)."""
    d = SHADOW_ROOT / f"{run.domain}__{run.arm}"
    d.mkdir(parents=True, exist_ok=True)
    for p in run.path.iterdir():
        if p.name in ("floodmap_hmax_lev3.tif", ".floodmap_hmax_lev3.partial.tif"):
            continue
        link = d / p.name
        if not link.exists() and not link.is_symlink():
            link.symlink_to(p)
    return d


def cmd_residuals(args) -> int:
    runs, _, out = resolve(args)
    run = {r.label: r for r in runs}[args.label]
    whole, desc = audit(run)
    print(f"[{run.label}] {run.path}\n  audit: {desc}", flush=True)
    if whole is not True:
        print("  🔴 output is not WHOLE — not scoring this run (CLAUDE.md §5)")
        return 3
    with_domain(run.domain)
    import nj_sfincs  # noqa: F401 — pyproj before hydromt
    from nj_sfincs import validate

    target = run.path if floodmap_fresh(run) else shadow_dir(run)
    if target != run.path:
        print(f"  ⚠️ floodmap cache stale/missing — downscaling in shadow {target}")
    pb = load_pb()
    # prime the memo WITHOUT the 21 s / tens-of-GB SfincsModel open; residuals() then hits
    # the same memo entry (key = dir + floodmap mtime).
    if target == run.path:
        validate.load_floodmap(target, need_model=False)
    scored, res = pb.residuals(target, ESTIMATOR, RADIUS_M)
    hwm = pb.scored_marks()
    if len(hwm) != len(scored):
        raise SystemExit("scored_marks() and residuals() disagree in length")
    df = pd.DataFrame(
        dict(
            hwm_id=hwm["hwm_id"].astype(str).values,
            lon=hwm["lon"].values,
            lat=hwm["lat"].values,
            x=hwm.geometry.x.values,
            y=hwm.geometry.y.values,
            basin=hwm["basin"].values,
            quality=hwm["quality"].astype(float).values,
            elev_m=hwm["elev_m"].values,
            scored=scored,
            resid_m=res,
        )
    )
    df["domain"], df["arm"] = run.domain, run.arm
    (out / "marks").mkdir(parents=True, exist_ok=True)
    dst = out / "marks" / f"{run.label}.csv"
    tmp = dst.with_suffix(".partial.csv")
    df.to_csv(tmp, index=False)
    os.replace(tmp, dst)
    s = df[df.scored]
    chk = dict(
        label=run.label,
        n=int(len(s)),
        rmse=float(np.sqrt((s.resid_m**2).mean())),
        bias=float(s.resid_m.mean()),
    )
    m = metrics_row(run) or {}
    chk.update(
        metrics_n=m.get("hwm_n_scored"),
        metrics_rmse=m.get("hwm_rmse_scored_m"),
        metrics_bias=m.get("hwm_bias_scored_m"),
        metrics_estimator=m.get("hwm_estimator"),
        metrics_radius=m.get("hwm_radius_m"),
    )
    try:
        chk["reproduces_metrics_4dp"] = bool(
            int(chk["metrics_n"]) == chk["n"]
            and abs(float(chk["metrics_rmse"]) - chk["rmse"]) < 5e-5
            and abs(float(chk["metrics_bias"]) - chk["bias"]) < 5e-5
        )
    except (TypeError, ValueError):
        chk["reproduces_metrics_4dp"] = None
    (out / "marks" / f"{run.label}.check.json").write_text(json.dumps(chk, indent=1))
    print(f"  wrote {dst}\n  self-check: {chk}", flush=True)
    validate.cache_clear()
    return 0


# ── zsmax difference (one same-mesh pair) ─────────────────────────────────────────────


def _faces(run: Run, centroids: bool):
    import xarray as xr

    with xr.open_dataset(run.path / "sfincs_map.nc", mask_and_scale=False) as ds:
        z = np.asarray(ds["zsmax"].values, dtype="float32")
        z = np.where(z > -9e3, z, np.nan).astype("float32")
        with np.errstate(all="ignore"):
            zsmax = np.nanmax(z, axis=0)
        del z
        out = dict(
            zsmax=zsmax,
            zb=np.asarray(ds["zb"].values, "float32"),
            msk=np.asarray(ds["msk"].values),
        )
        if "hm0" in ds.variables:
            h = np.asarray(ds["hm0"].values, dtype="float32")
            h = np.where(h > -9e3, h, np.nan)
            with np.errstate(all="ignore"):
                out["hm0max"] = np.nanmax(h, axis=0)
            del h
        if centroids:
            fn = np.asarray(ds["mesh2d_face_nodes"].values)
            fn0 = (fn - 1 if np.nanmin(fn) == 1 else fn).astype("int64")
            nx_ = np.asarray(ds["mesh2d_node_x"].values)
            ny_ = np.asarray(ds["mesh2d_node_y"].values)
            out["x"] = nx_[fn0].mean(1)
            out["y"] = ny_[fn0].mean(1)
    return out


def _binned(x, y, v, extent, res):
    x0, x1, y0, y1 = extent
    nx_, ny_ = int(np.ceil((x1 - x0) / res)), int(np.ceil((y1 - y0) / res))
    ok = np.isfinite(v) & (x >= x0) & (x < x1) & (y >= y0) & (y < y1)
    # clip: a centre exactly on y0 (quadtree centres are round numbers) floors to ny_
    ix = np.clip(((x[ok] - x0) // res).astype(int), 0, nx_ - 1)
    iy = np.clip(((y1 - y[ok]) // res).astype(int), 0, ny_ - 1)
    k = iy * nx_ + ix
    s = np.bincount(k, weights=v[ok], minlength=nx_ * ny_)
    n = np.bincount(k, minlength=nx_ * ny_)
    with np.errstate(all="ignore"):
        g = (s / n).reshape(ny_, nx_)
    g[n.reshape(ny_, nx_) == 0] = np.nan
    return g


def _outline(ax, domain_name: str):
    import geopandas as gpd

    with_domain(domain_name)
    from nj_sfincs import domain as _domain

    try:
        reg = gpd.read_file(str(_domain.active().region)).to_crs(32618)
        reg.boundary.plot(ax=ax, color=INK2, lw=0.4)
    except Exception:  # noqa: BLE001
        pass
    try:
        from nj_sfincs.plots import state_outline

        state_outline(
            32618, ("New Jersey", "New York", "Pennsylvania", "Delaware")
        ).plot(ax=ax, color=GRID, lw=0.5)
    except Exception:  # noqa: BLE001
        pass


def cmd_zsmax(args) -> int:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    runs, _, out = resolve(args)
    by = {r.label: r for r in runs}
    a, b = by[args.a], by[args.b]
    for r in (a, b):
        whole, desc = audit(r)
        print(f"[{r.label}] {desc}", flush=True)
        if whole is not True:
            print(f"  🔴 {r.label} output is not WHOLE — no map")
            return 3
    A, B = _faces(a, True), _faces(b, False)
    if len(A["zsmax"]) != len(B["zsmax"]):
        print(
            "  meshes differ (face counts) — a face-by-face zsmax difference is undefined"
        )
        return 4
    with_domain(a.domain)
    from nj_sfincs import domain as _domain
    from nj_sfincs.validate import DEPTH_MIN

    both = (
        (A["msk"] > 0)
        & (B["msk"] > 0)
        & np.isfinite(A["zsmax"])
        & np.isfinite(B["zsmax"])
    )
    wet = ((A["zsmax"] - A["zb"]) >= DEPTH_MIN) | ((B["zsmax"] - B["zb"]) >= DEPTH_MIN)
    sel = both & wet
    d = np.where(sel, A["zsmax"] - B["zsmax"], np.nan)
    x, y = A["x"], A["y"]

    # stats per HWM basin (face centroids classified by the domain's own rules)
    basin = np.asarray(_domain.classify_hwm_basin(x[sel], y[sel]))
    dv = d[sel]
    rows = [dict(basin="ALL wet faces", n_faces=int(sel.sum()), **_pct(dv))]
    for bn in sorted(set(basin)):
        rows.append(
            dict(basin=bn, n_faces=int((basin == bn).sum()), **_pct(dv[basin == bn]))
        )
    rows.append(
        dict(
            basin="(active in only one run)",
            n_faces=int(((A["msk"] > 0) ^ (B["msk"] > 0)).sum()),
            **_pct(np.array([])),
        )
    )
    zdir = out / "zsmax"
    zdir.mkdir(parents=True, exist_ok=True)
    tag = f"{a.label}_minus_{b.label}"
    pd.DataFrame(rows).to_csv(zdir / f"{tag}_stats.csv", index=False)

    lim = float(np.nanpercentile(np.abs(dv), 98)) if dv.size else 0.1
    lim = max(0.05, min(1.0, np.ceil(lim * 20) / 20))
    has_hm0 = "hm0max" in A
    from nj_sfincs import domain as _d

    pw = _d.active().plot_window
    full = (pw[0], pw[1], pw[2], pw[3])
    panels = [("all", full, 400.0)] + [(k, v, 100.0) for k, v in ZOOMS.items()]
    ncol = 3
    nrow = int(np.ceil((len(panels) + has_hm0) / ncol))
    fig, axs = plt.subplots(
        nrow,
        ncol,
        figsize=(5.0 * ncol, 5.4 * nrow),
        squeeze=False,
        layout="constrained",
    )
    cmap = plt.get_cmap("RdBu_r").copy()
    cmap.set_bad(GRID)
    im = None
    for ax, (name, ext, res) in zip(axs.flat, panels):
        g = _binned(x, y, d, ext, res)
        im = ax.imshow(
            g, extent=ext, cmap=cmap, vmin=-lim, vmax=lim, interpolation="nearest"
        )
        _outline(ax, a.domain)
        ax.set_xlim(ext[0], ext[1])
        ax.set_ylim(ext[2], ext[3])
        ax.set_title(f"{name}  (mean per {res:.0f} m bin)", fontsize=9, color=INK)
        ax.set_xticks([])
        ax.set_yticks([])
    if has_hm0:
        ax = axs.flat[len(panels)]
        h = np.where(A["msk"] > 0, A["hm0max"], np.nan)
        g = _binned(x, y, h, full, 400.0)
        hmax_ = float(np.nanpercentile(g, 99)) if np.isfinite(g).any() else 1.0
        hm = ax.imshow(
            g, extent=full, cmap="Blues", vmin=0, vmax=hmax_, interpolation="nearest"
        )
        _outline(ax, a.domain)
        ax.set_xlim(full[0], full[1])
        ax.set_ylim(full[2], full[3])
        ax.set_title(f"peak Hm0, {a.label} (m)", fontsize=9, color=INK)
        ax.set_xticks([])
        ax.set_yticks([])
        fig.colorbar(hm, ax=ax, shrink=0.7, label="m (400 m bin mean)")
    for ax in list(axs.flat)[len(panels) + has_hm0 :]:
        ax.axis("off")
    fig.colorbar(
        im,
        ax=axs.ravel().tolist(),
        shrink=0.6,
        label=f"zsmax {a.label} − {b.label} (m)",
    )
    fig.suptitle(
        f"Peak water level difference, {a.label} − {b.label} (faces active in both, wet "
        f"≥ {DEPTH_MIN} m in either; grey = no data)",
        fontsize=11,
        color=INK,
    )
    fig.savefig(zdir / f"fig_zsmax_{tag}.png", dpi=130, bbox_inches="tight")
    print(f"  wrote {zdir / f'fig_zsmax_{tag}.png'}")
    print(pd.DataFrame(rows).round(3).to_string(index=False))
    return 0


def _pct(v):
    v = v[np.isfinite(v)] if v.size else v
    if not v.size:
        return dict(
            median_m=np.nan, mean_m=np.nan, p05_m=np.nan, p95_m=np.nan, max_abs_m=np.nan
        )
    p = np.percentile(v, [5, 50, 95])
    return dict(
        median_m=p[1],
        mean_m=v.mean(),
        p05_m=p[0],
        p95_m=p[2],
        max_abs_m=np.abs(v).max(),
    )


# ── paired bootstrap from the per-mark CSVs ────────────────────────────────────────────


def paired(runs, pairs, out) -> tuple[pd.DataFrame, list[str], dict]:
    pb = load_pb()
    marks = {}
    for r in runs:
        f = out / "marks" / f"{r.label}.csv"
        if f.is_file():
            marks[r.label] = pd.read_csv(f, dtype={"hwm_id": str})
    rows, missing, joined = [], [], {}
    for a, b, why in pairs:
        if a not in marks or b not in marks:
            missing.append(
                f"{a} − {b}: per-mark residuals missing for "
                + ", ".join(x for x in (a, b) if x not in marks)
            )
            continue
        A, B = marks[a], marks[b]
        A = A[A.scored].drop_duplicates("hwm_id")
        Bi = B[B.scored].drop_duplicates("hwm_id").set_index("hwm_id")
        A = A[A.hwm_id.isin(Bi.index)]  # A's (geojson) order: same-domain = the CLI's
        Bm = Bi.loc[A.hwm_id]
        elev_bad = np.abs(A.elev_m.values - Bm.elev_m.values) > 1e-6
        basin_dis = int((A.basin.values != Bm.basin.values).sum())
        A, Bm = A[~elev_bad], Bm[~elev_bad]
        ra, rb = A.resid_m.values, Bm.resid_m.values
        n = len(ra)
        cross = A.domain.iloc[0] != Bm.domain.iloc[0]
        base = dict(
            pair=f"{a} − {b}",
            why=why,
            a=a,
            b=b,
            domains=f"{A.domain.iloc[0]} / {Bm.domain.iloc[0]}",
            cross_domain=cross,
            estimator=ESTIMATOR,
            radius_m=RADIUS_M,
            n_scored_a=int(marks[a].scored.sum()),
            n_scored_b=int(marks[b].scored.sum()),
            n_elev_mismatch=int(elev_bad.sum()),
            n_basin_disagree=basin_dis,
        )
        # ALL: exactly paired_hwm_bootstrap.main() — same seed, same draw, same order
        rng = np.random.default_rng(SEED)
        draws = rng.integers(0, n, size=(N_BOOT, n))
        dd = np.sqrt((ra[draws] ** 2).mean(1)) - np.sqrt((rb[draws] ** 2).mean(1))
        lo, hi = np.percentile(dd, [2.5, 97.5])
        p_better = float(np.mean(dd < 0))
        del draws, dd
        rows.append(
            dict(
                base,
                unit="ALL",
                n=n,
                drmse_m=np.sqrt((ra**2).mean()) - np.sqrt((rb**2).mean()),
                drmse_lo=lo,
                drmse_hi=hi,
                p_a_better=p_better,
                rmse_a=np.sqrt((ra**2).mean()),
                rmse_b=np.sqrt((rb**2).mean()),
                bias_a=ra.mean(),
                bias_b=rb.mean(),
                dmean_m=(ra - rb).mean(),
                dmedian_m=np.median(ra - rb),
            )
        )
        # groups + basins, with the CLI's rng state (it bootstraps groups after ALL)
        basins_ = A.basin.values
        allsel = np.ones(n, bool)
        for label, names in pb.BASIN_GROUPS.items():
            sel = allsel & np.isin(basins_, names)
            if sel.sum() < 2:
                continue
            rows.append(_boot_row(pb, base, f"[{label}]", ra, rb, sel, rng))
        for bn in sorted(set(basins_)):
            sel = basins_ == bn
            if sel.sum() < 2:
                d = ra[sel] - rb[sel]
                rows.append(
                    dict(
                        base,
                        unit=bn,
                        n=int(sel.sum()),
                        dmean_m=d.mean(),
                        dmedian_m=np.median(d),
                        bias_a=ra[sel].mean(),
                        bias_b=rb[sel].mean(),
                    )
                )
                continue
            rows.append(
                _boot_row(pb, base, bn, ra, rb, sel, np.random.default_rng(SEED))
            )
        joined[(a, b)] = pd.DataFrame(
            dict(
                hwm_id=A.hwm_id.values,
                lon=A.lon.values,
                lat=A.lat.values,
                x=A.x.values,
                y=A.y.values,
                basin=basins_,
                elev_m=A.elev_m.values,
                resid_a=ra,
                resid_b=rb,
                delta=ra - rb,
            )
        )
    return pd.DataFrame(rows), missing, joined


def _boot_row(pb, base, unit, ra, rb, sel, rng):
    r = pb._boot(ra, rb, sel, rng, N_BOOT)
    return dict(
        base,
        unit=unit,
        n=r["n"],
        drmse_m=r["rmse_a"] - r["rmse_b"],
        drmse_lo=r["drmse_ci"][0],
        drmse_hi=r["drmse_ci"][1],
        rmse_a=r["rmse_a"],
        rmse_b=r["rmse_b"],
        bias_a=r["bias_a"],
        bias_b=r["bias_b"],
        dmean_m=r["mean"],
        dmean_lo=r["mean_ci"][0],
        dmean_hi=r["mean_ci"][1],
        dmedian_m=r["med"],
        dmedian_lo=r["med_ci"][0],
        dmedian_hi=r["med_ci"][1],
        n_up=r["n_up"],
        n_absgt05=r["n_gt05"],
    )


# ── figures ─────────────────────────────────────────────────────────────────────────────


def fig_gauges(g: pd.DataFrame, runs: list[Run], out: Path) -> list[Path]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import TwoSlopeNorm

    if g.empty:
        return []
    labs = [r.label for r in runs if r.label in set(g.label)]
    paths = []
    # (1) obs vs model, one panel per run, shared axes
    ncol = min(4, len(labs))
    nrow = int(np.ceil(len(labs) / ncol))
    fig, axs = plt.subplots(
        nrow,
        ncol,
        figsize=(3.6 * ncol, 3.7 * nrow),
        squeeze=False,
        sharex=True,
        sharey=True,
    )
    lo = np.nanmin([g.obs_m.min(), g.mod_m.min()]) - 0.2
    hi = np.nanmax([g.obs_m.max(), g.mod_m.max()]) + 0.2
    for ax, lab in zip(axs.flat, labs):
        s = g[g.label == lab]
        ax.plot([lo, hi], [lo, hi], color=GRID, lw=1, zorder=0)
        full, pre = s[~s.prefail], s[s.prefail]
        ax.scatter(
            full.obs_m,
            full.mod_m,
            s=22,
            color=SERIES1,
            edgecolor="white",
            lw=0.6,
            label="full storm",
        )
        ax.scatter(
            pre.obs_m,
            pre.mod_m,
            s=22,
            facecolor="none",
            edgecolor=SERIES1,
            lw=1,
            label="gauge died: compared to its last sample",
        )
        e = s.err_m.dropna()
        ax.set_title(
            f"{lab}  n={len(e)}  mean err {e.mean():+.2f}  |err| {e.abs().mean():.2f} m",
            fontsize=8.5,
            color=INK,
        )
        ax.grid(color=GRID, lw=0.5)
        ax.set_xlim(lo, hi)
        ax.set_ylim(lo, hi)
    for ax in list(axs.flat)[len(labs) :]:
        ax.axis("off")
    axs.flat[0].legend(fontsize=7, frameon=False, loc="upper left")
    fig.supxlabel("observed peak (m NAVD88)", fontsize=9, color=INK2)
    fig.supylabel("modelled peak (m NAVD88)", fontsize=9, color=INK2)
    fig.suptitle(
        "Gauge peaks, observed vs modelled (metrics.csv)", fontsize=11, color=INK
    )
    p = out / "fig_gauges_obs_vs_model.png"
    fig.savefig(p, dpi=130, bbox_inches="tight")
    plt.close(fig)
    paths.append(p)

    # (2) the error table: gauge × run, diverging, numbers printed
    piv = g.pivot_table(index="gauge", columns="label", values="err_m").reindex(
        columns=labs
    )
    pre = g[g.prefail].gauge.unique()
    order = (
        g.drop_duplicates("gauge").set_index("gauge").obs_m.sort_values(ascending=False)
    )
    piv = piv.reindex([x for x in order.index if x in piv.index])
    fig, ax = plt.subplots(figsize=(1.2 * len(labs) + 3.4, 0.24 * len(piv) + 1.4))
    lim = 0.75
    ax.imshow(piv.values, cmap="RdBu_r", norm=TwoSlopeNorm(0, -lim, lim), aspect="auto")
    for (i, j), v in np.ndenumerate(piv.values):
        if np.isfinite(v):
            ax.text(
                j,
                i,
                f"{v:+.2f}",
                ha="center",
                va="center",
                fontsize=6.5,
                color="white" if abs(v) > 0.5 else INK,
            )
    ax.set_xticks(range(len(labs)), labs, fontsize=8)
    ax.set_yticks(
        range(len(piv)), [f"{x} †" if x in pre else x for x in piv.index], fontsize=6.5
    )
    ax.xaxis.tick_top()
    ax.set_title(
        "Peak error, model − obs (m); † = gauge died, compared to its last sample;"
        " rows by observed peak",
        fontsize=8.5,
        color=INK,
        pad=24,
    )
    p = out / "fig_gauges_peak_error.png"
    fig.savefig(p, dpi=130, bbox_inches="tight")
    plt.close(fig)
    paths.append(p)
    return paths


def fig_hwm_pairs(joined: dict, runs: list[Run], out: Path) -> list[Path]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    by = {r.label: r for r in runs}
    paths = []
    for (a, b), j in joined.items():
        if j.empty:
            continue
        fig, axs = plt.subplots(1, 3, figsize=(15, 6.2))
        x0, x1 = j.x.min() - 8000, j.x.max() + 8000
        y0, y1 = j.y.min() - 8000, j.y.max() + 8000
        dl = max(
            0.05, min(1.0, np.ceil(np.nanpercentile(np.abs(j.delta), 95) * 20) / 20)
        )
        for ax, col, title, lim in (
            (axs[0], "resid_a", f"{a}: model − obs", 1.0),
            (axs[1], "resid_b", f"{b}: model − obs", 1.0),
            (axs[2], "delta", f"{a} − {b}: change in modelled level", dl),
        ):
            _outline(ax, by[a].domain)
            sc = ax.scatter(
                j.x,
                j.y,
                c=j[col],
                cmap="RdBu_r",
                vmin=-lim,
                vmax=lim,
                s=26,
                edgecolor=INK2,
                lw=0.4,
                zorder=3,
            )
            ax.set_xlim(x0, x1)
            ax.set_ylim(y0, y1)
            ax.set_aspect("equal")
            ax.set_xticks([])
            ax.set_yticks([])
            v = j[col]
            ax.set_title(
                f"{title}\nmean {v.mean():+.3f}  RMS {np.sqrt((v**2).mean()):.3f} m",
                fontsize=9,
                color=INK,
            )
            fig.colorbar(sc, ax=ax, shrink=0.6, label="m")
        fig.suptitle(
            f"HWM residuals on the {len(j)} marks scored in both "
            f"(estimator {ESTIMATOR}, radius {RADIUS_M:g} m, q ≤ 2, dry marks vs "
            "ground)",
            fontsize=10,
            color=INK,
        )
        p = out / f"fig_hwm_{a}_vs_{b}.png"
        fig.savefig(p, dpi=120, bbox_inches="tight")
        plt.close(fig)
        paths.append(p)
    return paths


# ── report ─────────────────────────────────────────────────────────────────────────────


def md_table(df: pd.DataFrame, floatfmt: str = "{:.3f}", index: bool = False) -> str:
    if df is None or df.empty:
        return "_(no rows)_\n"
    d = df.reset_index() if index else df
    cols = [
        str(c) if not isinstance(c, tuple) else " ".join(map(str, c)) for c in d.columns
    ]

    def f(v):
        if isinstance(v, (float, np.floating)):
            return "" if np.isnan(v) else floatfmt.format(v)
        return str(v).replace("|", "/")

    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += [
        "| " + " | ".join(f(v) for v in row) + " |" for row in d.itertuples(index=False)
    ]
    return "\n".join(lines) + "\n"


def cmd_report(args) -> int:
    runs, pairs, out = resolve(args)
    out.mkdir(parents=True, exist_ok=True)
    setup = pd.DataFrame([setup_row(r) for r in runs])
    setup.to_csv(out / "setup.csv", index=False)
    head = headline(runs)
    head.to_csv(out / "headline.csv", index=False)
    bas = basins(runs)
    bas.to_csv(out / "basins.csv")
    g = gauges(runs)
    g.to_csv(out / "gauges.csv", index=False)
    figs = fig_gauges(g, runs, out)
    pr, missing, joined = paired(runs, pairs, out)
    pr.to_csv(out / "paired.csv", index=False)
    for (a, b), j in joined.items():
        j.to_csv(out / "marks" / f"joined_{a}_vs_{b}.csv", index=False)
    figs += fig_hwm_pairs(joined, runs, out)
    zfigs = (
        sorted((out / "zsmax").glob("fig_zsmax_*.png"))
        if (out / "zsmax").is_dir()
        else []
    )
    checks = (
        [
            json.loads(p.read_text())
            for p in sorted((out / "marks").glob("*.check.json"))
        ]
        if (out / "marks").is_dir()
        else []
    )
    gp = gauge_pairs(g, pairs)
    gp.to_csv(out / "gauges_paired.csv")
    zs = zsmax_stats(out, pairs)
    write_summary(
        out,
        runs,
        pairs,
        setup,
        head,
        bas,
        g,
        pr,
        missing,
        figs + zfigs,
        checks,
        extra=_extra_sections(gp, zs),
    )
    print(f"wrote {out}/summary.md (+ csv, png)")
    for m in missing:
        print("  missing:", m)
    return 0


def gauge_pairs(g: pd.DataFrame, pairs) -> pd.DataFrame:
    """Per gauge, modelled peak A − B for every pair (the wave lift at a gauge for a twin
    pair). Obs cancels, so a died-gauge's prefail pair is used on both sides alike."""
    if g.empty:
        return pd.DataFrame()
    mod = g.pivot_table(index="gauge", columns="label", values="mod_m")
    cols = {}
    for a, b, _ in pairs:
        if a in mod and b in mod:
            cols[f"{a} − {b}"] = mod[a] - mod[b]
    df = pd.DataFrame(cols)
    return df.dropna(how="all")


def zsmax_stats(out: Path, pairs) -> pd.DataFrame:
    rows = []
    for a, b, _ in pairs:
        f = out / "zsmax" / f"{a}_minus_{b}_stats.csv"
        if f.is_file():
            rows.append(pd.read_csv(f).assign(pair=f"{a} − {b}"))
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows)


def _extra_sections(gp: pd.DataFrame, zs: pd.DataFrame) -> str:
    S = [
        "\n## Gauge peaks, paired (modelled A − B, m)\n",
        "Obs cancels: this is how much each pair's change moves the modelled peak.\n\n",
    ]
    S.append(md_table(gp, "{:+.3f}", index=True) if not gp.empty else "_(none)_\n")
    S.append("\n## Peak water level, face by face (zsmax A − B, m)\n")
    S.append(
        "Faces active in both runs and wet ≥ 0.15 m in either; basins = the domain's "
        "HWM basin rules applied to face centres. Maps: `zsmax/fig_zsmax_*.png`.\n\n"
    )
    if zs.empty:
        S.append("_(no zsmax stats yet)_\n")
    else:
        piv = zs.pivot_table(
            index="basin", columns="pair", values="median_m", sort=False
        )
        S.append("Median Δ per basin:\n\n" + md_table(piv, "{:+.3f}", index=True))
        p95 = zs.pivot_table(index="basin", columns="pair", values="p95_m", sort=False)
        S.append(
            "\n95th percentile Δ per basin:\n\n" + md_table(p95, "{:+.3f}", index=True)
        )
    S.append("\nTODO — where the waves raise the peak, in words.\n")
    return "\n".join(S)


def write_summary(
    out, runs, pairs, setup, head, bas, g, pr, missing, figs, checks, extra=""
):
    S = []
    w = S.append
    w(f"# First waves-on v4 results — {out.name.removeprefix('v4_first_results_')}\n")
    w(
        "_Generated by `scripts/v4_first_results.py report`; tables are auto-filled, every "
        "**TODO** is prose for the main session. HWM numbers: estimator **median**, radius "
        "**50 m**, q ≤ 2, dry marks scored against ground (the `_scored` keys)._\n"
    )
    w(
        "## The short version\n\nTODO — two or three plain sentences: did the waves help the "
        "marks, where, and by how much (paired, with the CI); anything that looks wrong.\n"
    )
    w("## What ran\n")
    cols = [
        "label",
        "role",
        "domain",
        "arm",
        "engine",
        "waves",
        "dtwave_s",
        "dtheta_deg",
        "ig",
        "rain",
        "infiltration",
        "subgrid",
        "solve_wall_h",
        "sim_h_per_wall_h",
        "nodes",
        "constraint",
        "audit",
        "seal",
    ]
    w(md_table(setup[[c for c in cols if c in setup]], "{:.2f}"))
    bad = setup[~setup.audit.str.startswith("output WHOLE")]
    if len(bad):
        w("\n🔴 **Not scorable (audit not WHOLE):** " + ", ".join(bad.label) + "\n")
    nom = setup[setup.metrics_row != "yes"]
    if len(nom):
        w(
            "\n⚠️ **No metrics.csv row yet:** "
            + ", ".join(nom.label)
            + " (validate not run?)\n"
        )
    w("\n## Headline scores (metrics.csv)\n")
    w(
        "HWM on the `_scored` keys; MOTF CSI/POD/FAR with `extent_admissible` (False = "
        "waves-off: keep, do not rank against waves-on) and `motf_km2_excluded_boxes` "
        "(v3 and v4 score DIFFERENT MOTF rasters — CSI is not comparable across domains).\n"
    )
    w(md_table(head, "{:.3f}"))
    w("\nTODO — one paragraph reading the table.\n")
    w("\n## Paired comparisons (per-mark, bootstrap)\n")
    w(
        "Δ = A − B. ΔRMSE < 0 means A fits the marks better. Δ mean / Δ median = change in "
        "modelled level at the marks (positive = A higher). ALL row = `paired_hwm_bootstrap.py` "
        "main read (B = 200 000, seed 20261007); groups = its `--by-basin` read. Cross-domain "
        "pairs are joined on `hwm_id` over the marks scored in both (v3's area).\n"
    )
    if not pr.empty:
        allr = pr[pr.unit == "ALL"][
            [
                "pair",
                "why",
                "domains",
                "n",
                "rmse_a",
                "rmse_b",
                "drmse_m",
                "drmse_lo",
                "drmse_hi",
                "p_a_better",
                "bias_a",
                "bias_b",
                "dmean_m",
                "dmedian_m",
            ]
        ]
        w(md_table(allr, "{:+.4f}"))
        grp = pr[pr.unit.str.startswith("[")][
            [
                "pair",
                "unit",
                "n",
                "drmse_m",
                "drmse_lo",
                "drmse_hi",
                "dmean_m",
                "dmean_lo",
                "dmean_hi",
                "dmedian_m",
                "bias_a",
                "bias_b",
            ]
        ]
        w("\n### By basin group\n")
        w(md_table(grp, "{:+.3f}"))
        w("\nPer-basin rows: `paired.csv`.\n")
    for m in missing:
        w(f"\n- ⚠️ not computed: {m}\n")
    w(
        "\nTODO — the wave contribution in plain words (which basins move, how much), run B vs "
        "A, and v4 vs v3 on the shared marks.\n"
    )
    if checks:
        w("\n### Residual self-check (per-mark recompute vs the metrics.csv row)\n")
        w(md_table(pd.DataFrame(checks), "{:.4f}"))
    w("\n## Gauges (peak, model − obs, m)\n")
    if not g.empty:
        piv = g.pivot_table(index="gauge", columns="label", values="err_m")
        piv = piv.reindex(columns=[r.label for r in runs if r.label in piv.columns])
        pre = set(g[g.prefail].gauge)
        piv.index = [f"{x} †" if x in pre else x for x in piv.index]
        obs = g.drop_duplicates("gauge").set_index("gauge").obs_m
        piv.insert(0, "obs_peak", [obs.get(x.rstrip(" †"), np.nan) for x in piv.index])
        w("† = the gauge died mid-storm; model compared to its last good sample.\n\n")
        w(md_table(piv, "{:+.2f}", index=True))
    w("\nTODO — which gauges the waves move, and the worst misses.\n")
    w("\n## HWM by basin (metrics.csv, `_scored` keys)\n")
    if not bas.empty:
        w(md_table(bas, "{:+.3f}", index=True))
    w(extra)
    w("\n## Figures\n")
    for p in figs:
        w(f"\n![{p.stem}]({p.relative_to(out)})\n")
    w("\n## What is running\n\n```\n" + _squeue() + "```\n")
    w(
        "\n## Caveats\n\nTODO — imperfect-by-design list (reports/v4_refreeze_list_2026-10-05.md),"
        " anything flagged above.\n"
    )
    w("\n## Reproduce\n\n```bash\n" + "\n".join(_cli_lines(runs, pairs)) + "\n```\n")
    (out / "summary.md").write_text("\n".join(S))


def _squeue() -> str:
    try:
        return subprocess.run(
            [
                "squeue",
                "-u",
                os.environ.get("USER", "tpj8"),
                "-o",
                "%.10i %.24j %.9T %.10M %.11l %R",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return "(squeue unavailable)\n"


def _cli_lines(runs, pairs) -> list[str]:
    """The canonical CLI cross-check for each SAME-domain pair (needs ~2x the memory of
    one run — v4 ~210 GB — run one at a time)."""
    by = {r.label: r for r in runs}
    lines = [
        "# canonical paired_hwm_bootstrap.py reads (same-domain pairs; one at a time):"
    ]
    for a, b, _ in pairs:
        ra, rb = by[a], by[b]
        if ra.domain == rb.domain:
            lines.append(
                f"NJ_DOMAIN={ra.domain} python scripts/paired_hwm_bootstrap.py "
                f"{ra.path} {rb.path} --by-basin"
            )
    return lines


# ── submit / plan ──────────────────────────────────────────────────────────────────────


def _md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def job_script(
    out: Path, name: str, body: str, mem: str, time: str, cpus: int = 4
) -> Path:
    jd = out / "jobs"
    jd.mkdir(parents=True, exist_ok=True)
    md5f = jd / "expected.md5"
    s = f"""#!/bin/bash
#SBATCH -J v4fr_{name}
#SBATCH -p main
#SBATCH --exclude=halk[0001-0159]
#SBATCH -c {cpus}
#SBATCH --mem={mem}
#SBATCH -t {time}
#SBATCH -o {jd}/{name}_%j.out
set -eo pipefail
cd {ROOT}
export PATH={ENV_PATH}/bin:$PATH PYTHONPATH={ROOT}
export PROJ_DATA={ENV_PATH}/share/proj
echo "host=$(hostname) job=$SLURM_JOB_ID $(date)"
# halk late-write trap (CLAUDE.md §5): wait for the files we were submitted with.
for i in $(seq 1 30); do md5sum -c --quiet {md5f} && break; sleep 10; done
md5sum -c {md5f}
/usr/bin/time -f "%e s  maxRSS %M KB" {body} 2>&1 | grep -v -i "warning"
echo "== done $(date)"
"""
    p = jd / f"{name}.sh"
    p.write_text(s)
    return p


def _argv_common(args) -> str:
    s = f"--preset {args.preset}" if args.preset else ""
    s += f" --out {args.out}" if args.out else ""
    for r in args.run or []:
        s += f" --run {r}"
    for p in args.pair or []:
        s += f" --pair '{p}'"
    return s.strip()


def plan_jobs(args, runs, pairs, out):
    common = _argv_common(args)
    me = f"python -u {ROOT / 'scripts' / 'v4_first_results.py'}"
    jobs = []
    for r in runs:
        csv = out / "marks" / f"{r.label}.csv"
        mp = r.path / "sfincs_map.nc"
        if (
            csv.is_file()
            and mp.is_file()
            and csv.stat().st_mtime > mp.stat().st_mtime
            and not args.redo
        ):
            continue
        mem = args.mem_v3 if r.domain == "v3" else args.mem_v4
        jobs.append(
            (
                f"res_{r.label}",
                f"{me} residuals --label {r.label} {common}",
                mem,
                "03:00:00",
            )
        )
    by = {r.label: r for r in runs}
    for a, b, _ in pairs:
        if same_mesh(by[a], by[b]):  # face-by-face map
            f = out / "zsmax" / f"fig_zsmax_{a}_minus_{b}.png"
            if f.is_file() and not args.redo:
                continue
            jobs.append(
                (
                    f"zs_{a}_{b}",
                    f"{me} zsmax --a {a} --b {b} {common}",
                    "48G",
                    "01:00:00",
                )
            )
    return jobs, f"{me} report {common}"


def cmd_plan(args) -> int:
    runs, pairs, out = resolve(args)
    print(f"out: {out}\n")
    for r in runs:
        whole, desc = audit(r)
        m = metrics_row(r)
        print(
            f"{r.label:11s} {r.domain:18s} {r.arm}\n    {desc}\n    metrics row: "
            f"{'yes' if m else 'MISSING'}   floodmap cache: "
            f"{'fresh' if floodmap_fresh(r) else 'stale/missing'}"
        )
    print("\npairs:")
    for a, b, why in pairs:
        print(f"  {a} − {b}: {why}")
    jobs, rep = plan_jobs(args, runs, pairs, out)
    print("\njobs:")
    for name, cmd, mem, t in jobs:
        print(f"  [{name}] mem={mem} t={t}\n      {cmd}")
    print(f"  [report] (afterany on all)\n      {rep}")
    print("\n" + "\n".join(_cli_lines(runs, pairs)))
    return 0


def cmd_submit(args) -> int:
    runs, pairs, out = resolve(args)
    out.mkdir(parents=True, exist_ok=True)
    jd = out / "jobs"
    jd.mkdir(exist_ok=True)
    files = [
        ROOT / "scripts" / "v4_first_results.py",
        ROOT / "scripts" / "paired_hwm_bootstrap.py",
    ]
    (jd / "expected.md5").write_text("".join(f"{_md5(f)}  {f}\n" for f in files))
    jobs, rep = plan_jobs(args, runs, pairs, out)
    dep = f"--dependency=afterok:{args.after.replace(',', ':')}" if args.after else ""
    ids = []
    for name, cmd, mem, t in jobs:
        sh = job_script(out, name, cmd, mem, t)
        line = ["sbatch", "--parsable"] + ([dep] if dep else []) + [str(sh)]
        ids.append(_sbatch(line, args.dry_run))
    sh = job_script(out, "report", rep, "32G", "01:00:00")
    deps = [i for i in ids if i]
    line = ["sbatch", "--parsable"]
    if deps:
        line.append("--dependency=afterany:" + ":".join(deps))
    elif dep:
        line.append(dep.replace("afterok", "afterany"))
    line.append(str(sh))
    rid = _sbatch(line, args.dry_run)
    print(f"\njob scripts in {jd}; report job {rid or '(dry run)'}")
    return 0


def _sbatch(line, dry) -> str | None:
    print(" ".join(line))
    if dry:
        return None
    r = subprocess.run(line, capture_output=True, text=True, check=False)
    if r.returncode:
        raise SystemExit(f"sbatch failed: {r.stderr}")
    jid = r.stdout.strip().split(";")[0]
    print(f"   -> {jid}")
    return jid


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--preset", choices=sorted(PRESETS))
        sp.add_argument(
            "--out", help="output dir (default reports/v4_first_results_<date>)"
        )
        sp.add_argument(
            "--run",
            action="append",
            metavar="LABEL=PATH",
            help="add/override a run (repo-relative or absolute path)",
        )
        sp.add_argument(
            "--pair",
            action="append",
            metavar="A:B[:why]",
            help="add a pair (labels); delta = A - B",
        )
        return sp

    common(sub.add_parser("plan", help="read-only: what is there + the jobs"))
    sp = common(
        sub.add_parser("residuals", help="per-mark residuals for ONE run (heavy)")
    )
    sp.add_argument("--label", required=True)
    sp = common(
        sub.add_parser("zsmax", help="face zsmax A - B map for ONE same-mesh pair")
    )
    sp.add_argument("--a", required=True)
    sp.add_argument("--b", required=True)
    common(sub.add_parser("report", help="tables, paired bootstrap, figures, summary"))
    sp = common(sub.add_parser("submit", help="sbatch residuals + zsmax, then report"))
    sp.add_argument("--after", help="comma-separated job ids to wait for (afterok)")
    sp.add_argument(
        "--dry-run", action="store_true", help="write job scripts, print sbatch"
    )
    for s in (sp, sub.choices["plan"]):
        s.add_argument("--redo", action="store_true", help="recompute existing outputs")
        s.add_argument("--mem-v4", default="236G", help="residuals job memory, v4 runs")
        s.add_argument("--mem-v3", default="160G", help="residuals job memory, v3 runs")
    a = p.parse_args(argv)
    return dict(
        plan=cmd_plan,
        residuals=cmd_residuals,
        zsmax=cmd_zsmax,
        report=cmd_report,
        submit=cmd_submit,
    )[a.cmd](a)


if __name__ == "__main__":
    with contextlib.suppress(BrokenPipeError):
        raise SystemExit(main())
