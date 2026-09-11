"""Run SFINCS locally (container or native binary) or submit it to SLURM.

``run_sfincs`` began as notebooks/sfincs-nj-sandy.ipynb cell 56 (the auto-detecting
container runner with numactl + OMP thread handling); since 2026-09-11 it also runs a
native binary (``binary=``) and REQUIRES exactly one engine — no fallback. Every finished
run is stamped with ``engine.txt`` (``provenance.write_engine``). ``submit_slurm`` wraps
hpc/sfincs_run.slurm and exports the chosen engine as SFINCS_SIF or SFINCS_BIN.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from .config import ROOT


def _pick_engine(sif: str | None, binary: str | None) -> tuple[str, Path]:
    """Exactly one engine, and it must exist. Raised BEFORE anything touches the model
    dir or looks for sbatch, so the refusal is testable off-cluster.

    🔴 There is no fallback (2026-09-11). The old default — SFINCS_SIF from the
    environment, else ``sfincs-cpu.sif`` — is how the 2026-07-20 phaselag runs ended up
    on Galibier (v2.4.0) instead of the sealed premier's Faber (v2.3.3), and it is how a
    patched native build could silently NOT be the engine of a run that claims it.
    """
    if sif is not None and binary is not None:
        raise RuntimeError("exactly one of sif= / binary= — not both")
    if sif is None and binary is None:
        raise RuntimeError(
            "REFUSING: no engine — pass sif=<image.sif> or binary=<sfincs binary>. "
            "(No SFINCS_SIF / sfincs-cpu.sif fallback since 2026-09-11.)"
        )
    if sif is not None:
        p = Path(sif).resolve()
        if not p.is_file():
            raise FileNotFoundError(f"container image not found: {p}")
        return "sif", p
    p = Path(binary).resolve()
    if not p.is_file():
        raise FileNotFoundError(f"native binary not found: {p}")
    if not os.access(p, os.X_OK):
        raise RuntimeError(f"native binary is not executable: {p}")
    return "bin", p


def _record_engine(model_abs: Path, kind: str, engine: Path) -> None:
    try:
        from . import provenance

        provenance.write_engine(model_abs, kind, engine)
    except Exception as e:  # noqa: BLE001 — the solve is done; never lose it over the stamp
        print(f"[warn] engine record not written: {e}")


def run_sfincs(model_root, sif: str | None = None, binary: str | None = None):
    """Run SFINCS locally: in a Singularity/Docker container (``sif``) or as a native
    binary (``binary``, from ``hpc/build_sfincs_native.sh``). Exactly one. The run dir
    gets ``engine.txt`` afterwards (``provenance.write_engine``)."""
    model_abs = Path(model_root).resolve()
    log_path = model_abs / "sfincs_log.txt"
    threads = os.environ.get("OMP_NUM_THREADS") or str(os.cpu_count() or 1)
    kind, engine = _pick_engine(sif, binary)

    # Clear stale outputs first — a held-open sfincs_map.nc/his.nc triggers HDF5
    # file-locking that makes SFINCS silently write ZERO output.
    for stale in ("sfincs_map.nc", "sfincs_his.nc"):
        try:
            (model_abs / stale).unlink()
        except FileNotFoundError:
            pass

    numa = ["numactl", "--interleave=all"] if shutil.which("numactl") else []
    if kind == "bin":
        # Same environment the container path gets (and hpc/sfincs_run.slurm sets):
        # thread count, thread placement, 1 G worker stacks, unlimited main stack.
        env = {
            **os.environ,
            "OMP_NUM_THREADS": threads,
            "OMP_PROC_BIND": os.environ.get("OMP_PROC_BIND", "spread"),
            "OMP_PLACES": os.environ.get("OMP_PLACES", "cores"),
            "OMP_STACKSIZE": os.environ.get("OMP_STACKSIZE", "1G"),
        }
        libdir = os.environ.get("SFINCS_BIN_LIBDIR")
        if libdir:
            env["LD_LIBRARY_PATH"] = libdir + ":" + env.get("LD_LIBRARY_PATH", "")

        def _unlimit_stack():
            try:
                import resource

                hard = resource.getrlimit(resource.RLIMIT_STACK)[1]
                resource.setrlimit(resource.RLIMIT_STACK, (hard, hard))
            except (ValueError, OSError, ImportError):
                pass

        print(
            f"Running SFINCS natively ({engine.parent.parent.name}) "
            f"[OMP={threads}{', mem-interleaved' if numa else ''}] ..."
        )
        with open(log_path, "w") as lf:
            result = subprocess.run(
                numa + [str(engine)],
                cwd=str(model_abs),
                stdout=lf,
                stderr=subprocess.STDOUT,
                env=env,
                preexec_fn=_unlimit_stack,
                check=False,
            )
        _record_engine(model_abs, kind, engine)
        return result

    if shutil.which("singularity"):
        sif_abs = engine
        # With SnapWave on, the solver scales across BOTH sockets; interleave
        # memory pages so neither socket starves on remote bandwidth.
        bind = os.environ.get("OMP_PROC_BIND", "spread")
        places = os.environ.get("OMP_PLACES", "cores")
        env = {
            **os.environ,
            "OMP_NUM_THREADS": threads,
            "OMP_PROC_BIND": bind,
            "OMP_PLACES": places,
            "SINGULARITYENV_OMP_NUM_THREADS": threads,
            "SINGULARITYENV_OMP_PROC_BIND": bind,
            "SINGULARITYENV_OMP_PLACES": places,
            "APPTAINERENV_OMP_NUM_THREADS": threads,
            "APPTAINERENV_OMP_PROC_BIND": bind,
            "APPTAINERENV_OMP_PLACES": places,
        }
        print(
            f"Running SFINCS via Singularity ({sif_abs.name}) "
            f"[OMP={threads}{', mem-interleaved' if numa else ''}] ..."
        )
        with open(log_path, "w") as lf:
            result = subprocess.run(
                numa
                + [
                    "singularity",
                    "run",
                    "--bind",
                    f"{model_abs}:/data",
                    "--pwd",
                    "/data",
                    str(sif_abs),
                ],
                stdout=lf,
                stderr=subprocess.STDOUT,
                env=env,
                check=False,
            )
        _record_engine(model_abs, kind, engine)
        return result
    if shutil.which("docker"):
        print(f"Running SFINCS via Docker [OMP={threads}] ...")
        subprocess.run(  # clear root-owned stale outputs from a prior Docker run
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{model_abs}:/data",
                "--entrypoint",
                "/bin/sh",
                "deltares/sfincs-cpu:latest",
                "-c",
                "rm -f /data/sfincs_map.nc /data/sfincs_his.nc",
            ],
            capture_output=True,
            check=False,
        )
        with open(log_path, "w") as lf:
            return subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "-v",
                    f"{model_abs}:/data",
                    "deltares/sfincs-cpu:latest",
                ],
                stdout=lf,
                stderr=subprocess.STDOUT,
                check=False,
            )
    raise RuntimeError("Neither 'singularity' nor 'docker' on PATH.")


def submit_slurm(
    model_dir,
    sif: str | None = None,
    binary: str | None = None,
    slurm_script: Path | None = None,
    extra_args: list[str] | None = None,
) -> str | None:
    """Submit one SFINCS solve via ``sbatch hpc/sfincs_run.slurm <model_dir>``.

    The batch script runs relative to the submit dir (= repo root), so we sbatch
    from ROOT and pass the model dir as a path relative to it. Returns the job id.

    Exactly one of ``sif`` (exported as SFINCS_SIF) or ``binary`` (SFINCS_BIN) picks the
    engine; the batch script refuses a job with neither or both. The engine is validated
    BEFORE the sbatch check so the refusal is testable off-cluster. There is no fallback
    (see ``_pick_engine``).
    """
    kind, engine = _pick_engine(sif, binary)
    if slurm_script is None:
        slurm_script = ROOT / "hpc" / "sfincs_run.slurm"
    if not shutil.which("sbatch"):
        raise RuntimeError("'sbatch' not on PATH — not on a SLURM cluster?")

    env = dict(os.environ)
    env.pop(
        "SFINCS_SIF", None
    )  # never let a stale export ride along as the other engine
    env.pop("SFINCS_BIN", None)
    env["SFINCS_SIF" if kind == "sif" else "SFINCS_BIN"] = str(engine)
    print(f"[slurm] engine = {kind}:{engine}")

    model_abs = Path(model_dir).resolve()
    try:
        model_arg = str(model_abs.relative_to(ROOT))
    except ValueError:
        model_arg = str(model_abs)

    # sbatch CLI flags override the #SBATCH directives in the script, so this is the
    # way to give one job a longer wall clock (e.g. ["--time=06:00:00"]) without
    # editing the shared batch script for every future run.
    cmd = ["sbatch", *(extra_args or []), str(slurm_script), model_arg]
    if extra_args:
        print(f"[slurm] sbatch overrides: {' '.join(extra_args)}")
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    print(proc.stdout.strip() or proc.stderr.strip())
    if proc.returncode != 0:
        raise RuntimeError(f"sbatch failed: {proc.stderr.strip()}")
    m = re.search(r"Submitted batch job (\d+)", proc.stdout)
    return m.group(1) if m else None
