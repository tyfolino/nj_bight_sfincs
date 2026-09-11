#!/usr/bin/env python
"""Stamp a run dir with the engine that solved it: ``engine.txt`` + ``[engine]`` in provenance.

    python scripts/record_engine.py <model_dir> (--sif X.sif | --bin /path/to/sfincs)

Called by ``hpc/sfincs_run.slurm`` after the solve (and after the restart stitch), and by
``nj_sfincs.run.run_sfincs`` for local runs. Reads SLURM_JOB_ID / SLURM_RESTART_COUNT /
OMP_NUM_THREADS from the environment. Safe to re-run; it replaces the previous record.
Written 2026-09-11 (plan Phase 1b) — see ``nj_sfincs.provenance.engine_record``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from nj_sfincs import provenance


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("model_dir", type=Path)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--sif", type=Path)
    g.add_argument("--bin", type=Path)
    a = ap.parse_args(argv)
    kind, path = ("sif", a.sif) if a.sif else ("bin", a.bin)
    out = provenance.write_engine(a.model_dir, kind, path)
    rec = provenance.read_engine(a.model_dir) or {}
    print(
        f"[engine] {rec.get('label')}  direction={provenance.snapwave_direction(a.model_dir)}"
        f"  -> {out}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
