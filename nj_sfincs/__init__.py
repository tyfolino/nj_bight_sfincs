"""nj_sfincs — build, run, validate and visualise the NJ Bight SFINCS model.

Submodules are intentionally independent so cheap imports stay cheap::

    from nj_sfincs.experiments import EXPERIMENTS   # no heavy deps
    from nj_sfincs import plots, validate           # matplotlib / hydromt

Every geographic fact lives in ``domain.py``, selected by the ``NJ_DOMAIN`` env var;
``premier.py`` holds the fingerprints that prove a run dir is on the domain it claims.
"""

# Prime PROJ/GEOS before hydromt_sfincs loads. In a bare (non-notebook) process,
# importing hydromt_sfincs.utils first and only later touching PROJ triggers a
# native "double free or corruption" inside utils.downscale_floodmap (a GEOS/PROJ
# load-order conflict). Importing pyproj here — before any submodule pulls in
# hydromt_sfincs — initializes PROJ first and makes the package safe from the CLI.
# The notebook never hit this because it imports the viz stack (which pulls
# pyproj) up top. Keep this import ahead of any hydromt_sfincs import.
import pyproj  # noqa: F401,E402  (PROJ primer — do not remove or reorder)

# Pin PROJ_DATA to the environment's own proj directory, and export it so GDAL
# COMMAND-LINE subprocesses inherit it.
#
# PROJ searches `~/.local/share/proj` before the env's `share/proj`. On this
# account that first path shadows the real one, so PROJ gives up and every CRS
# lookup fails. In-process that goes unnoticed — pyproj carries its own data — so
# the only symptom is a stray "proj_create_from_database: Open of ... failed" on
# stderr while results stay correct. The gdal CLI has no such fallback: it dies
# with "Invalid SRS for -t_srs" and gdalwarp exits non-zero. That silently killed
# a topobathy re-clip whose Python wrapper printed its progress lines happily
# either way, so the failure only showed up in the exit code.
#
# setdefault, so an explicit PROJ_DATA in the environment still wins.
import os as _os  # noqa: E402
from pathlib import Path as _Path  # noqa: E402

_proj_data = _Path(pyproj.datadir.get_data_dir())
if (_proj_data / "proj.db").exists():
    _os.environ.setdefault("PROJ_DATA", str(_proj_data))
    _os.environ.setdefault("PROJ_LIB", str(_proj_data))  # PROJ < 9.1 spelling


# ── NJ_ROOT MUST BE THIS PACKAGE'S OWN REPO ──────────────────────────────────
# 🔴 The failure this prevents, which has already happened once. The login profile
# on this account exports `PROJ=$HOME/nj_sandy_sfincs` — the TOOLCHAIN directory,
# not a repo — and the batch scripts used to do `PROJ="${PROJ:-$PWD}"` followed by
# `export NJ_ROOT="$PROJ"` / `export PYTHONPATH="$PROJ"`. Whenever the variable was
# already set (on an interactive node it always is) that pointed NJ_ROOT and the
# import path at the wrong directory entirely.
#
# It is silent by construction: paths still resolve, `data/` still exists, and the
# model still builds — just against another repo's inputs. So assert it. NJ_ROOT is
# still honoured (a deliberate out-of-tree checkout is legitimate); what is refused
# is NJ_ROOT pointing somewhere that is NOT the parent of the package actually
# imported, because that combination cannot be intentional.
_pkg_root = _Path(__file__).resolve().parents[1]
_env_root = _os.environ.get("NJ_ROOT")
if _env_root and _Path(_env_root).resolve() != _pkg_root:
    raise RuntimeError(
        f"NJ_ROOT={_env_root!r} resolves to {_Path(_env_root).resolve()}, but the "
        f"nj_sfincs package being imported lives in {_pkg_root}.\n"
        "  Those must be the same repo. This is the $PROJ trap: the login profile "
        "exports PROJ=$HOME/nj_sandy_sfincs (the toolchain dir), and a batch script "
        "that does NJ_ROOT=$PROJ silently points the model at another tree.\n"
        "  Set NJ_ROOT to the repo you are actually running from, or unset it — the "
        "package locates its own root by default."
    )

del _os, _Path, _proj_data, _pkg_root, _env_root

__all__ = [
    "config",
    "domain",
    "experiments",
    "model",
    "premier",
    "provenance",
    "run",
    "report",
    "validate",
    "plots",
    "animate",
]
