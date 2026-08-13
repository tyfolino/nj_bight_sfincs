"""Locate GDAL command-line tools belonging to the RUNNING interpreter.

Scripts here shell out to ``gdalwarp`` / ``gdal_translate`` / ``gdalbuildvrt``.
Bare ``subprocess.run(["gdalwarp", ...])`` only works if the conda env happens to
be on ``PATH``, which it is in an activated shell and is NOT when the script is
launched by absolute interpreter path — the normal way it gets run here:

    micromamba/envs/sfincs/bin/python scripts/download_pre_sandy_topobathy.py

That combination fails with ``FileNotFoundError: 'gdalwarp'``. Resolving the tool
next to ``sys.executable`` makes the interpreter the single source of truth: the
gdal you get is always the one from the same environment as the Python you ran.

Import ``nj_sfincs`` before calling these — the package sets ``PROJ_DATA``, and
without it every GDAL CRS lookup fails with "Invalid SRS".
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def gdal_bin(name: str) -> str:
    """Absolute path to a GDAL CLI tool, preferring the interpreter's own env."""
    local = Path(sys.executable).resolve().parent / name
    if local.exists():
        return str(local)
    found = shutil.which(name)
    if found:
        return found
    raise FileNotFoundError(
        f"{name} not found next to {sys.executable} nor on PATH. "
        f"Install gdal into the environment, or activate it before running."
    )


def run_gdal(name: str, args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a GDAL CLI tool and raise on failure.

    ``check=True`` matters more than usual here: gdalwarp reports an unusable
    ``-t_srs`` by printing a usage block and exiting non-zero, which is easy to
    miss when the calling script's own progress prints are buffered and land
    *after* the error in a redirected log.
    """
    cmd = [gdal_bin(name), *args]
    proc = subprocess.run(cmd)
    if check and proc.returncode != 0:
        raise RuntimeError(f"{name} failed (exit {proc.returncode}): {' '.join(cmd)}")
    return proc
