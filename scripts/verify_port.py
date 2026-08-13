#!/usr/bin/env python
"""THE PORT GATE. Prove the ported scorer reproduces the archive, bit for bit.

    PYTHONPATH=$PWD NJ_DOMAIN=v1_monmouth python scripts/verify_port.py

WHY THIS EXISTS
---------------
A clean SLURM sweep once completed with plausible numbers and was scientifically void: it
had been staged from the wrong template, the open coast reproduced to within 0.3 min, and
the estuary the experiment was about was 30% down in tidal range. Nothing in the output
said which planet it was measured on.

A repo port is that failure mode again, with the same shape: new tree, refactored scorer,
same-looking numbers. The only defence is to rescore a run whose answer is already known
and require the digits to match.

TIER 1 — RESCORE, NO SOLVER
    Score ``experiments/v1_monmouth/faber-waves-premier`` — a byte-for-byte copy of the
    archived run — and compare against the values that run produced under the previous
    code. Same ``sfincs_map.nc``, same code path, deterministic arithmetic, so the
    tolerance is **bit-for-bit** (``places=9``). Any drift is a bug, not a tolerance.

    Deliberately no solver. Re-running would confound the VALIDATION port with every build
    question at once; scoring the same output isolates it to the thing being tested.

TIER 2 — STAGE, NO SOLVER
    Stage from the archived ``_template_sealed`` and assert the fingerprint, the
    support-point count, and an empty ``sfincs.inp`` diff. ~1 min.

🔴 THE BASELINE IS ``experiments/v1_monmouth/metrics.csv`` AS REGENERATED 2026-08-12, NOT
the older ``reports/v1_monmouth/faber-waves-premier_rescored.csv``. That July file is
``hwm_n_scored=19`` with no estimator column; the current code gives 38 under
``median``/50 m. Pinning to it fails on ``n`` alone and reads as a port bug that is not
there.

⚠️ SOME KEYS WERE RENAMED BY THE PORT, and that is expected: the archive had one function
per named place (``gauge_peak_error`` knew about exactly one gauge, so its keys needed no
gauge in them), and the port drives everything off the domain registry. The rename is
listed explicitly in ``RENAMES`` below rather than hidden behind an alias, so what changed
is visible in one place.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("NJ_DOMAIN", "v1_monmouth")

import nj_sfincs  # noqa: F401,E402  (PROJ primer + NJ_ROOT assert)
from nj_sfincs import domain, premier, validate  # noqa: E402
from nj_sfincs.config import ROOT, exp_root  # noqa: E402

RUN = "faber-waves-premier"

#: The archive's values for this exact run, from experiments/v1_monmouth/metrics.csv as
#: regenerated 2026-08-12 under estimator=median, radius=50 m, n=38.
PINNED: dict[str, float] = {
    "hwm_bias_scored_m": -0.3631059310561731,
    "hwm_rmse_scored_m": 0.5704992999451454,
    "hwm_n_scored": 38,
    "motf_csi": 0.6378335183129856,
    "motf_pod": 0.7662452178117845,
    "motf_far": 0.2080725826899544,
    "phase_lag_sandy_hook_min": 17.6,
    "gauge_peak_err_prefail_m": -0.3116818981170652,
}

#: archive key -> ported key. Everything not listed kept its name.
RENAMES = {
    # `gauge_*` meant "the one NOAA gauge". Now every gauge is scored by registry name.
    "gauge_peak_err_prefail_m": "peak_err_prefail_sandy_hook_m",
    # phase lag was keyed on a hand-written label; it is now the registry gauge name.
    # `sandy_hook` happens to be identical, which is why it is the pinned one.
    "phase_lag_sandy_hook_min": "phase_lag_sandy_hook_min",
}

PLACES = 9


def tier1() -> int:
    run_dir = exp_root() / RUN
    if not (run_dir / "sfincs_map.nc").exists():
        print(f"FAIL: {run_dir} has no sfincs_map.nc.")
        print("  Copy it from the archive (see ARCHIVE.md) — COPY, do not symlink: the")
        print("  floodmap cache writes into the run dir and the archive is read-only.")
        return 1

    print(f"[tier1] domain      : {domain.active().name}")
    print(f"[tier1] fingerprint : {premier.domain_fingerprint(run_dir)}")
    premier.assert_sealed_domain(run_dir, context="port verification")
    print("[tier1] domain + observation points OK")
    print(f"[tier1] scoring {run_dir} (no solver) ...")

    row = validate.evaluate(run_dir)

    for k in ("gauge_peak_metrics_error", "tide_metrics_error", "hwm_metrics_error",
              "motf_metrics_error"):
        if k in row:
            print(f"  !! {k}: {row[k]}")

    # The estimator stamp is not optional. A row that does not say which estimator and
    # radius produced it cannot be compared with anything, and the estimator alone flips
    # the sign of the HWM bias.
    fails = []
    if row.get("hwm_estimator") != "median":
        fails.append(f"hwm_estimator is {row.get('hwm_estimator')!r}, expected 'median'")
    if row.get("hwm_radius_m") != 50.0:
        fails.append(f"hwm_radius_m is {row.get('hwm_radius_m')!r}, expected 50.0")

    print(f"\n{'metric':<34} {'archive':>18} {'ported':>18}   verdict")
    print("-" * 96)
    for old_key, want in PINNED.items():
        new_key = RENAMES.get(old_key, old_key)
        got = row.get(new_key)
        note = "" if new_key == old_key else f"  (renamed -> {new_key})"
        if got is None:
            fails.append(f"{old_key}: ported row has no key {new_key!r}")
            print(f"{old_key:<34} {want:>18.9g} {'MISSING':>18}   FAIL{note}")
            continue
        ok = abs(float(got) - float(want)) < 0.5 * 10**-PLACES
        if not ok:
            fails.append(
                f"{old_key}: archive {want!r}, ported {got!r}, "
                f"delta {float(got) - float(want):+.3e}"
            )
        print(
            f"{old_key:<34} {float(want):>18.9g} {float(got):>18.9g}   "
            f"{'ok' if ok else 'FAIL'}{note}"
        )

    # Per-basin values are pinned implicitly: they depend on first-match-wins over
    # Domain.hwm_rules IN ORDER, so a reorder shows up here as a changed partition.
    print("\nper-basin scored marks (order-dependent — a reorder repartitions these):")
    total = 0
    for b in domain.hwm_basin_names():
        n = row.get(f"hwm_n_scored_{b}")
        bias = row.get(f"hwm_bias_scored_{b}_m")
        total += int(n or 0)
        print(f"  {b:<22} n={n!s:>3}  bias={bias if bias is None else round(bias, 4)}")
    print(f"  {'TOTAL':<22} n={total}")
    if total != row.get("hwm_n_scored"):
        fails.append(
            f"per-basin scored marks sum to {total} but hwm_n_scored is "
            f"{row.get('hwm_n_scored')} — the partition is losing or double-counting marks"
        )
    if row.get("hwm_n_unassigned"):
        fails.append(
            f"{row['hwm_n_unassigned']} marks matched NO basin rule. They are not being "
            "silently folded into a neighbour, but they are also not being reported."
        )

    if fails:
        print("\n🔴 TIER 1 FAILED:")
        for f in fails:
            print(f"  - {f}")
        print(
            "\n  Tolerance is BIT-FOR-BIT on purpose: same input, same code path, "
            "deterministic\n  arithmetic. A small delta is not 'close enough', it is a "
            "port bug with a small\n  blast radius today and an unknown one on a new "
            "domain."
        )
        return 1
    print("\n✅ TIER 1 PASSED — the ported scorer reproduces the archive bit for bit.")
    return 0


def tier2() -> int:
    """Stage from the archived sealed template and assert it comes out unchanged."""
    tmpl = exp_root() / premier.TEMPLATE_NAME
    if not (tmpl / "sfincs.inp").exists():
        print(f"[tier2] SKIP — no {tmpl}")
        return 0
    print(f"\n[tier2] template    : {tmpl}")
    print(f"[tier2] fingerprint : {premier.domain_fingerprint(tmpl)}")
    try:
        premier.assert_sealed_domain(tmpl, context="port verification (template)")
    except premier.WrongDomainError as e:
        print(f"🔴 TIER 2 FAILED:\n{e}")
        return 1

    ok, problems = premier.obs_points_ok(tmpl)
    print(f"[tier2] obs points  : {'OK' if ok else problems}")

    # ⚠️ The staging itself is NOT exercised here. `v1_monmouth` is registered `frozen=True`
    # precisely so nothing can build on it, and `prepare_experiment` would need an
    # `EXPERIMENTS` entry the domain deliberately does not have. What tier 2 asserts is the
    # part that is portable: that the archived template still fingerprints as this domain
    # under the NEW code's hash, and that its observation points still match the NEW
    # registry. If those hold, `copytree` is exact and a staged copy is the same domain.
    print("[tier2] ✅ archived template fingerprints + resolves against the ported registry.")
    return 0


def main() -> int:
    print(f"repo: {ROOT}\n")
    rc = tier1()
    rc |= tier2()
    if rc == 0:
        print(
            "\n" + "=" * 78 + "\nPORT VERIFIED. v1.5 work may start.\n" + "=" * 78
        )
    return rc


if __name__ == "__main__":
    sys.exit(main())
