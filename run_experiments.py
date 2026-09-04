#!/usr/bin/env python
"""Stage, run and score the experiment sweep for the ACTIVE domain.

The static build + base forcing live ONCE in ``experiments/<domain>/_template_sealed``;
each experiment copies the template, layers on its knobs, runs SFINCS, and is validated.
Metrics are aggregated into ``experiments/<domain>/metrics.csv`` and a self-contained
``report.html``.

🔴 ONLY ``--check`` IS READ-ONLY. ``--inputs-only`` / ``--no-run`` / the deprecated
``--dry-run`` all DESTROY and re-stage each experiment directory before skipping the
solver — "dry run" here never meant "touch nothing", and reading it that way cost a
premier's 1.8 GB of output once.

Examples
--------
    # Read-only: resolve paths, assert the template's domain, print the plan:
    python run_experiments.py --experiments naccs-premier --check

    # Cheap smoke test: one short-window run end-to-end:
    python run_experiments.py --experiments naccs-nowaves --tstop 2012-10-29

    # Submit to SLURM, then aggregate once the jobs finish:
    #   ⚠️ SnapWave is 90-95% of runtime; the 3 h batch default is NOT enough for a
    #   large domain or a deep boundary.
    python run_experiments.py --experiments naccs-premier --slurm \
        --slurm-args "--time=12:00:00"
    python run_experiments.py --validate-only

Run from the repo root.
"""

from __future__ import annotations

import argparse
import gc
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# Import the package first — its __init__ primes PROJ before hydromt_sfincs loads and
# asserts NJ_ROOT is this package's own repo. Keep this ahead of the hydromt_sfincs import.
from nj_sfincs import domain, model, premier, report, run, validate
from nj_sfincs.config import BaseConfig, WaveConfig, exp_root, with_window
from nj_sfincs.experiments import experiments

from hydromt_sfincs import SfincsModel

# Resolved once: a single invocation works on one domain, and NJ_DOMAIN is read at import
# exactly like NJ_TEMPLATE below.
EXP_ROOT = exp_root()
EXPERIMENTS = experiments()

# THE template every new experiment is staged from. Overridable via NJ_TEMPLATE for
# deliberate work on another template — the domain assert below still reports what you
# actually got.
TEMPLATE = Path(os.environ.get("NJ_TEMPLATE", premier.sealed_template()))
FLOODMAPS = EXP_ROOT / "floodmaps"
METRICS_CSV = EXP_ROOT / "metrics.csv"

NO_WAVES = WaveConfig(use_waves=False)
TEMPLATE_STAMP = TEMPLATE / ".window"


def build_template(base: BaseConfig) -> None:
    """Static build + base forcing → the template dir (written once).

    ⚠️ THIS FUNCTION rmtree's ITS TARGET. A sealed template is the base of every run staged
    from it and is NOT reproducible from BaseConfig alone (it is built against an explicit
    frozen mesh). Rebuilding it here would silently substitute a different domain under the
    same name — the exact class of failure ``premier.py`` exists to prevent.

    The guard below refuses when the template already IS the sealed domain. It does NOT
    catch a template whose fingerprint has drifted, so: do not run the sweep driver to
    "just rebuild" a template.
    """
    if premier.is_sealed(TEMPLATE):
        raise SystemExit(
            f"refusing to rebuild {TEMPLATE}: it is already the sealed template for "
            f"domain '{domain.active().name}' ({premier.expected()}).\n"
            "  Delete it deliberately if you really mean to rebuild, or point "
            "NJ_TEMPLATE somewhere else to build a scratch template."
        )
    print(f"[template] building static model + forcing in {TEMPLATE} ...")
    if TEMPLATE.exists():
        shutil.rmtree(TEMPLATE)
    model.build_static(base, TEMPLATE)

    sf = SfincsModel(str(TEMPLATE), data_libs=base.data_libs, mode="r+")
    model.add_forcing(base, sf)
    model.finalize(NO_WAVES, base, sf, TEMPLATE, None)
    del sf
    gc.collect()
    # Stamp the window so a later run with a different window rebuilds rather than
    # silently reusing a truncated (smoke-test) template.
    TEMPLATE_STAMP.write_text(base.tstop.isoformat())
    print("[template] done")


def template_matches(base: BaseConfig) -> bool:
    """True iff a built template exists for exactly this run window.

    The .window stamp is written by build_template. A sealed template built elsewhere
    carries no stamp, so fall back to its own sfincs.inp — otherwise it reads as stale and
    we would try to rebuild (and destroy) it on every invocation.
    """
    if not (TEMPLATE / "sfincs.inp").exists():
        return False
    if TEMPLATE_STAMP.exists():
        return TEMPLATE_STAMP.read_text().strip() == base.tstop.isoformat()
    return _inp_tstop(TEMPLATE) == base.tstop


def _inp_tstop(model_dir: Path) -> datetime | None:
    """Parse ``tstop`` out of a sfincs.inp (``YYYYMMDD HHMMSS``)."""
    for line in (model_dir / "sfincs.inp").read_text().splitlines():
        key, _, value = line.partition("=")
        if key.strip() == "tstop":
            try:
                return datetime.strptime(value.strip(), "%Y%m%d %H%M%S")
            except ValueError:
                return None
    return None


def check_template_domain(name: str) -> None:
    """Assert the TEMPLATE is on the domain `name` requires — WITHOUT touching anything.

    ⚠️ CALL THIS BEFORE ANY DESTRUCTIVE STEP. The staged arm's domain IS the template's
    domain (``copytree`` is exact), so checking the template is equivalent to checking the
    copy and costs nothing but the hash.

    This ordering is the whole point. The check used to run on the destination AFTER
    ``rmtree`` + ``copytree``, so a domain mismatch could only ever be reported once the
    destination had already been destroyed — which is exactly how a run directory's output
    was lost, to a command whose author believed it was read-only.
    """
    exp = EXPERIMENTS[name]
    # A BRACKET takes the opposite check: it is SUPPOSED to be an inadmissible domain, so
    # assert_sealed_domain would (correctly) refuse it. assert_bracket confirms it is the
    # bracket it claims to be AND that the caller passed NJ_ALLOW_BRACKET.
    if exp.bracket:
        premier.assert_bracket(
            TEMPLATE, exp.bracket, context=f"staging bracket '{name}' from {TEMPLATE.name}"
        )
        print(
            f"[{name}] *** INADMISSIBLE BRACKET '{exp.bracket}' "
            f"({premier.BRACKETS[exp.bracket].bound} bound) — bounds a quantity, "
            "is not a candidate configuration"
        )
    else:
        premier.assert_sealed_domain(
            TEMPLATE, context=f"staging '{name}' from {TEMPLATE.name}"
        )


def swap_subgrid(exp_dir: Path, src: Path, name: str) -> None:
    """Replace a staged arm's subgrid products with those of a ``rebuild_subgrid.py`` dir.

    The only way a bed/roughness edit reaches a run (see ``Experiment.subgrid_from``).
    Hard-links (same filesystem) with a copy fallback; the copytree'd originals are
    unlinked first, so nothing is written through to the template. Refuses a source
    built on any mesh but the sealed one — a subgrid table is only meaningful on the
    mesh it was cut for.
    """
    if not (src / "sfincs_subgrid.nc").exists() or not (src / "subgrid").is_dir():
        raise SystemExit(
            f"[{name}] subgrid_from={src.name}: no sfincs_subgrid.nc + subgrid/ there — "
            "build it with scripts/rebuild_subgrid.py first"
        )
    premier.assert_sealed_domain(src, context=f"subgrid_from '{src.name}' for '{name}'")
    prov = src / "provenance.txt"
    print(f"[{name}] subgrid ← {src}" + (f" ({prov.read_text()[:120]!r}...)" if prov.exists() else ""))

    def _link(a: Path, b: Path) -> None:
        b.unlink(missing_ok=True)
        try:
            os.link(a, b)
        except OSError:
            shutil.copy2(a, b)

    _link(src / "sfincs_subgrid.nc", exp_dir / "sfincs_subgrid.nc")
    shutil.rmtree(exp_dir / "subgrid", ignore_errors=True)
    (exp_dir / "subgrid").mkdir()
    for f in sorted((src / "subgrid").iterdir()):
        _link(f, exp_dir / "subgrid" / f.name)
    for f in ("subgrid_diff.json", "provenance.txt"):
        if (src / f).exists():
            shutil.copy2(src / f, exp_dir / f"subgrid_{f}")


def prepare_experiment(name: str, base: BaseConfig) -> Path:
    """Copy the template and apply the experiment's knobs. Returns the exp dir."""
    exp = EXPERIMENTS[name]
    exp_dir = EXP_ROOT / name
    # Domain check FIRST — nothing below this line is reversible.
    check_template_domain(name)
    print(f"[{name}] preparing ({exp.description})")
    if exp_dir.exists():
        shutil.rmtree(exp_dir)
    shutil.copytree(TEMPLATE, exp_dir)
    # Re-assert on the copy: cheap next to a solve, and it catches a truncated or
    # partially-written copytree that the template check cannot see.
    if exp.bracket:
        premier.assert_bracket(exp_dir, exp.bracket, context=f"staged bracket '{name}'")
    else:
        premier.assert_sealed_domain(exp_dir, context=f"staged '{name}'")
    if exp.subgrid_from:
        swap_subgrid(exp_dir, EXP_ROOT / exp.subgrid_from, name)

    sf = SfincsModel(str(exp_dir), data_libs=base.data_libs, mode="r+")
    sf.read()
    # Optional per-experiment water-level forcing swap (a forcing A/B). Re-runs
    # water_level.create on the boundary cells the template already carved; merge=False
    # REPLACES the template's forcing (merge=True would append and leave the stale bnd in
    # place). finalize() below loads + writes it.
    if exp.waterlevel_geodataset is not None:
        print(f"[{name}] overriding water-level forcing → {exp.waterlevel_geodataset}")
        sf.water_level.create(
            geodataset=exp.waterlevel_geodataset,
            buffer=base.waterlevel_buffer,
            merge=False,
        )
        # Same guard as the template build: a forcing swap RE-RUNS the buffered gauge
        # selection, so it is another place an extra support point can appear with no other
        # symptom. An arm whose whole point IS a different node count declares it on the
        # Experiment; everything else still gets the domain invariant.
        model.check_waterlevel_support(sf, expect=exp.n_waterlevel_support)
    sw = model.add_waves(exp.waves, base, sf) if exp.waves.use_waves else None
    model.finalize(exp.waves, base, sf, exp_dir, sw, rain=exp.rain)
    # hydromt's writer drops crsfile/storevel; put them back so a staged arm carries the
    # flux cross-sections — which on a relocated-boundary domain are the headline result,
    # not a diagnostic.
    model.restore_diagnostics(exp_dir)
    del sf
    gc.collect()
    return exp_dir


def collect_metrics(names: list[str]) -> pd.DataFrame:
    """Validate each existing experiment dir and aggregate to a DataFrame."""
    FLOODMAPS.mkdir(parents=True, exist_ok=True)
    rows = {}
    for name in names:
        exp_dir = EXP_ROOT / name
        if not (exp_dir / "sfincs_map.nc").exists():
            print(f"[{name}] no sfincs_map.nc — skipping validation")
            continue
        print(f"[{name}] validating ...")
        try:
            rows[name] = validate.evaluate(
                exp_dir, gallery_tif=FLOODMAPS / f"{name}_hmax_lev3.tif"
            )
        except Exception as e:  # noqa: BLE001
            print(f"[{name}] validation failed: {e}")
            rows[name] = {"error": str(e)}
        # Stamp the domain onto every row. A metrics table whose numbers do not say which
        # domain they came from is how a voided A/B got compared against a premier it never
        # shared a mesh with. Scoring an off-domain run stays legal — silently is not.
        exp = EXPERIMENTS.get(name)
        if exp is not None and exp.bracket:
            rows[name]["domain"] = f"BRACKET:{exp.bracket} INADMISSIBLE"
            print(f"[{name}] bracket row — writes to the bracket report, never metrics.csv")
            continue
        sealed = premier.is_sealed(exp_dir)
        dom = domain.active().name
        rows[name]["domain"] = dom if sealed else f"NOT-{dom}"
        # A waves-off arm's extent metrics are KEPT, and flagged. Scoring a waves-off run
        # against MOTF is a legitimate standalone measurement — Grimley et al. 2025 run
        # exactly that configuration (FINDINGS §22) — and the reader decides whether it
        # answers their question. `extent_admissible` carries the caveat; it used to also
        # DELETE the values, which threw away a real number to make a point.
        #
        # What the flag means: not "this run is wrong" but "this CSI is not on the same
        # footing as a waves-on CSI". Measured on v1.5 (2026-08-20), SnapWave is worth
        # ΔCSI 0.018 — against ΔCSI 0.011 between the two waves-on arms, so a mixed
        # ranking puts a bigger effect in the table than the one under test.
        if exp is not None and not exp.waves.use_waves:
            rows[name]["extent_admissible"] = False
            print(
                f"[{name}] waves OFF — CSI/POD/FAR kept, extent_admissible=False. "
                "Not on the same footing as a waves-on CSI; see FINDINGS §4."
            )
        else:
            rows[name]["extent_admissible"] = True
        if not sealed:
            print(
                f"[{name}] *** WARNING: not on domain '{dom}' "
                f"({premier.domain_fingerprint(exp_dir)}) — not comparable. "
                "See nj_sfincs/premier.py."
            )
    return pd.DataFrame.from_dict(rows, orient="index")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument(
        "--experiments",
        default=None,
        help="comma-separated arm names, or 'all'. No default: naming what you are "
        f"staging is cheap and a wrong sweep is not. Choices: {', '.join(EXPERIMENTS)}",
    )
    p.add_argument(
        "--yes",
        action="store_true",
        help="confirm '--experiments all' non-interactively (for a batch job).",
    )
    p.add_argument(
        "--rebuild-template", action="store_true", help="force-rebuild the template"
    )
    p.add_argument(
        "--no-run", action="store_true", help="build inputs but do not run the solver"
    )
    p.add_argument(
        "--inputs-only",
        action="store_true",
        help="WRITES INPUTS (destroys and re-stages each experiment dir), then skips "
        "solver AND validation. For a read-only check use --check.",
    )
    p.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="DEPRECATED alias for --inputs-only. It is NOT read-only — it rmtree's each "
        "experiment dir. Use --check instead.",
    )
    p.add_argument(
        "--check",
        action="store_true",
        help="read-only: resolve paths, assert the template's domain, print the plan. "
        "Writes and deletes NOTHING.",
    )
    p.add_argument(
        "--slurm",
        action="store_true",
        help="submit each experiment via hpc/sfincs_run.slurm instead of running locally "
        "(validate later with --validate-only)",
    )
    p.add_argument(
        "--slurm-args",
        default=None,
        # NB the doubled %% — argparse runs help through %-formatting, and a bare % here
        # raises "badly formed help string" at parse time, i.e. the CLI dies before doing
        # anything. Caught by tests/test_all_sweep_requires_confirmation.
        help="extra sbatch flags, space-separated, e.g. '--time=12:00:00 --mem=128G'. "
        "sbatch CLI flags beat the script's #SBATCH lines. ⚠️ The 3 h default is NOT "
        "enough for a large domain: SnapWave is 90-95%% of runtime.",
    )
    p.add_argument(
        "--validate-only",
        action="store_true",
        help="skip build/run; just (re)aggregate metrics + report",
    )
    p.add_argument(
        "--tstop",
        default=None,
        help="override the run end date (YYYY-MM-DD) for a short smoke test; forces a "
        "template rebuild",
    )
    args = p.parse_args(argv)

    if not EXPERIMENTS:
        p.error(
            f"domain '{domain.active().name}' has no experiments registered. See "
            "nj_sfincs/experiments.py — arms are per-domain, and an arm that has not been "
            "thought about for this domain deliberately does not exist."
        )
    if args.experiments is None:
        p.error(
            "--experiments is required. Name the arm(s), or pass 'all' with --yes. "
            f"Choices: {', '.join(EXPERIMENTS)}"
        )

    if args.experiments == "all":
        # 'all' must NEVER pick up a bracket: sweeping one would put a known-wrong domain
        # into a candidate table, which is the failure an inadmissible-but-good-scoring
        # boundary condition taught us to design against.
        # Derived from EXPERIMENTS, not from sweepable(), so the two cannot disagree about
        # WHY an arm was left out — "not in the sweep set" and "is a bracket" are different
        # statements and the message must not conflate them.
        names = [n for n, e in EXPERIMENTS.items() if e.bracket is None]
        skipped = [n for n, e in EXPERIMENTS.items() if e.bracket is not None]
        if skipped:
            print(f"[sweep] excluding {len(skipped)} bracket(s) from 'all': {skipped}")
        if not args.yes:
            # A sweep is hours of compute and it rmtree's every destination. Say what it
            # will do and make the caller agree.
            print(f"[sweep] '--experiments all' on domain '{domain.active().name}' would")
            print(f"        DESTROY and re-stage {len(names)} directories under {EXP_ROOT}:")
            for n in names:
                mark = "  (has output)" if (EXP_ROOT / n / "sfincs_map.nc").exists() else ""
                print(f"          {n}{mark}")
            if not sys.stdin.isatty():
                p.error("refusing '--experiments all' with no tty; pass --yes.")
            if input("        proceed? [y/N] ").strip().lower() not in ("y", "yes"):
                print("aborted.")
                return 1
    else:
        names = [n.strip() for n in args.experiments.split(",")]
    unknown = [n for n in names if n not in EXPERIMENTS]
    if unknown:
        p.error(f"unknown experiment(s): {unknown}. Choices: {list(EXPERIMENTS)}")

    if args.dry_run:
        print(
            "⚠️  --dry-run is DEPRECATED and is NOT read-only: it rmtree's each\n"
            "    experiment dir before re-staging it. Use --inputs-only if that is\n"
            "    what you meant, or --check for a genuinely read-only pass.",
            file=sys.stderr,
        )

    base = BaseConfig()
    if args.tstop:
        base = with_window(base, datetime.strptime(args.tstop, "%Y-%m-%d"))
        print(f"[window] short run: tstop = {base.tstop:%Y-%m-%d}")

    # ── check: read-only, must come BEFORE any mkdir/write ───────────────────
    if args.check:
        print(f"[check] NJ_DOMAIN   = {domain.active().name}")
        print(f"[check] expected    = {premier.expected()}")
        print(f"[check] EXP_ROOT    = {EXP_ROOT}")
        print(
            f"[check] TEMPLATE    = {TEMPLATE}"
            f"{'' if TEMPLATE.exists() else '   ** MISSING **'}"
        )
        stale = (
            ""
            if template_matches(base)
            else "   ** template window MISMATCH: a real run would REBUILD "
            "(rmtree) the template **"
        )
        print(f"[check] window ends = {base.tstop:%Y-%m-%d}{stale}")
        bad = 0
        for name in names:
            exp_dir = EXP_ROOT / name
            try:
                check_template_domain(name)
                verdict = "OK"
                sub = EXPERIMENTS[name].subgrid_from
                if sub and not (EXP_ROOT / sub / "sfincs_subgrid.nc").exists():
                    verdict = (
                        f"OK but subgrid_from={sub} is NOT BUILT — staging would refuse; "
                        "run scripts/rebuild_subgrid.py first"
                    )
            except Exception as e:  # noqa: BLE001 — report every arm, don't stop at one
                verdict, bad = f"REFUSED — {type(e).__name__}: {e}", bad + 1
            print(f"[check] {name}: {verdict}")
            if exp_dir.exists():
                print(f"          would DESTROY and re-stage {exp_dir}")
        print(
            f"\n[check] read-only; nothing written. {len(names) - bad}/{len(names)} "
            "would stage."
        )
        return 1 if bad else 0

    EXP_ROOT.mkdir(parents=True, exist_ok=True)

    # ── validate-only: just re-aggregate ─────────────────────────────────────
    if args.validate_only:
        _write_outputs(collect_metrics(names))
        return 0

    # ── build template (once) ────────────────────────────────────────────────
    if args.rebuild_template or not template_matches(base):
        build_template(base)
    else:
        print(
            f"[template] reusing existing {TEMPLATE} for window ending "
            f"{base.tstop:%Y-%m-%d} (pass --rebuild-template to force a rebuild)"
        )

    # ── per-experiment prepare + run ─────────────────────────────────────────
    submitted = {}
    for name in names:
        exp_dir = prepare_experiment(name, base)
        if args.inputs_only or args.dry_run or args.no_run:
            print(f"[{name}] inputs written to {exp_dir} (solver skipped)")
            continue
        if args.slurm:
            job = run.submit_slurm(
                exp_dir,
                sif=str(base.container_sif),
                extra_args=args.slurm_args.split() if args.slurm_args else None,
            )
            submitted[name] = job
            print(f"[{name}] submitted SLURM job {job}")
        else:
            result = run.run_sfincs(exp_dir, sif=str(base.container_sif))
            print(f"[{name}] solver return code {result.returncode}")

    if args.inputs_only or args.dry_run or args.no_run:
        print("Done (inputs only).")
        return 0
    if args.slurm:
        print("\nSubmitted:", submitted)
        print("When the jobs finish, run:  python run_experiments.py --validate-only")
        return 0

    # ── local: validate + aggregate ──────────────────────────────────────────
    _write_outputs(collect_metrics(names))
    return 0


def _merge_metrics(df: pd.DataFrame, csv: Path = None) -> pd.DataFrame:
    """Fold freshly validated rows INTO the existing metrics table.

    ``--validate-only --experiments X`` used to overwrite ``metrics.csv`` with X's row
    alone, silently dropping every other arm's scores from the table and the report.
    Re-scoring one arm should update one row. Rows for the arms just validated are
    replaced; every other arm's row is carried forward untouched (it was scored on the
    same domain — ``metrics.csv`` is domain-scoped under ``exp_root()``).
    """
    csv = METRICS_CSV if csv is None else csv
    if not Path(csv).exists():
        return df
    old = pd.read_csv(csv, index_col=0)
    old = old.drop(index=[n for n in df.index if n in old.index])
    if old.empty:
        return df
    return pd.concat([old, df], sort=False)


def _write_outputs(df: pd.DataFrame) -> None:
    if df.empty:
        print("No metrics to write (no completed runs found).")
        return
    df = _merge_metrics(df)
    df.to_csv(METRICS_CSV)
    print(f"\nwrote {METRICS_CSV}")
    try:
        rpt = report.generate_html_report(df, EXP_ROOT)
        print(f"wrote {rpt}")
    except Exception as e:  # noqa: BLE001
        print(f"(report generation skipped: {e})")
    with pd.option_context("display.width", 200, "display.max_columns", 50):
        print("\n" + df.to_string())


if __name__ == "__main__":
    sys.exit(main())
