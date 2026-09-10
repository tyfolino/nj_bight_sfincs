#!/usr/bin/env python
"""Resume / finish a preempted SFINCS solve.  See nj_sfincs/restart.py for the why.

    python scripts/sfincs_restart.py plan    <run_dir>   # read-only: fresh | resume | finish
    python scripts/sfincs_restart.py prepare <run_dir>   # retire outputs, rewrite sfincs.inp
    python scripts/sfincs_restart.py finish  <run_dir>   # stitch segments, restore inp, drop rst
    python scripts/sfincs_restart.py enable  <run_dir>   # add dtrstout/dtmaxout to a staged inp

``prepare`` prints the action word on its LAST line, so a batch script can read it:
``hpc/sfincs_run.slurm`` skips the solver on ``finish`` (the run had already reached
tstop when it was requeued mid-stitch).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nj_sfincs import restart  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("cmd", choices=["plan", "prepare", "finish", "enable"])
    ap.add_argument("run_dir", type=Path)
    ap.add_argument(
        "--dt", type=float, default=21600.0, help="enable: restart cadence (s)"
    )
    a = ap.parse_args()
    d = a.run_dir
    if a.cmd == "enable":
        inp = d / "sfincs.inp"
        inp.write_text(restart.add_restart_output(inp.read_text(), a.dt))
        print(f"dtrstout = dtmaxout = {a.dt:.0f} s written to {inp}")
        return 0
    if a.cmd == "finish":
        rep = restart.finish(d)
        print(f"finish: {rep}")
        return 0
    pl = restart.plan(d) if a.cmd == "plan" else restart.prepare(d)
    extra = f" at {pl.t_resume:%Y-%m-%d %H:%M}" if pl.t_resume else ""
    print(f"{a.cmd}: {pl.reason}{extra}", file=sys.stderr)
    print(pl.action)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
