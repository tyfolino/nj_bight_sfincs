"""Repo-level invariants: the archive rule, the $PROJ trap, the estimator default.

These are cheap greps over the tree, and each of them pins something that has already gone
wrong once in a way no runtime check would have caught.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from nj_sfincs.config import ROOT

CODE_DIRS = ("nj_sfincs", "scripts", "hpc")
ARCHIVE_NAMES = ("nj_coast_sfincs", "nj_sandy_sfincs")

#: What "referencing the archive" actually means. Naming it in prose is fine and often
#: necessary — ARCHIVE.md, this module, and several docstrings do — so the test looks for
#: the name being USED: imported, put on the path, opened, or executed.
_USE = re.compile(
    r"\b(import|from|sys\.path|PYTHONPATH|NJ_ROOT|exec|eval|open|Path|subprocess|"
    r"copytree|symlink|cd)\b"
)
#: The toolchain lives behind symlinks into the other repo by design (CLAUDE.md).
_SANCTIONED = re.compile(r"micromamba|envs/sfincs|\.sif\b|hydromt_sfincs")


def _code_files():
    for d in CODE_DIRS:
        for p in (ROOT / d).rglob("*"):
            if p.is_file() and p.suffix in (".py", ".sh", ".slurm"):
                yield p
    for p in ROOT.glob("*.py"):
        yield p


class TestArchiveIsDataOnly(unittest.TestCase):
    """⭐ The archive is referenced for DATA and DOCS only. NEVER for code.

    ``data/`` symlinks into the archive for the read-only bulk, which is the whole point of
    keeping it. What must never happen is code reaching across: an import, a ``sys.path``
    insert, or an exec. Two copies of a module is how you end up running the one you did not
    edit — the same rule ``CLAUDE.md`` applies to the toolchain repo, for the same reason.
    """

    def test_no_code_references_the_archive(self):
        """NAMING the archive is fine; USING it is not.

        The distinction matters, because the honest documentation of this rule has to say
        which repo it is talking about. So the test flags a line only when an archive name
        appears together with something that would actually reach into it — an import, a
        path construction, a ``sys.path`` insert, an exec.
        """
        offenders = []
        for p in _code_files():
            for i, line in enumerate(p.read_text(errors="ignore").splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith(("#", "*", '"""', "'''", "#:")):
                    continue
                if not any(n in line for n in ARCHIVE_NAMES):
                    continue
                if _SANCTIONED.search(line):
                    continue  # the toolchain symlinks, by design
                if _USE.search(line):
                    offenders.append(f"{p.relative_to(ROOT)}:{i}: {stripped[:90]}")
        self.assertEqual(
            offenders,
            [],
            "code REACHES INTO the archive repo:\n  " + "\n  ".join(offenders) + "\n"
            "  The archive is for DATA and DOCS. Copy what you need, or symlink it under "
            "data/ — never import from it. Two copies of a module is how you end up "
            "running the one you did not edit.",
        )

    #: The only top-level symlinks that are allowed to exist, and why.
    #:   toolchain — the conda env bakes its absolute prefix into ~79 shebangs and into the
    #:               PROJ/GDAL data paths, so it cannot be moved, only linked to.
    #:   refs      — the cited papers. DOCS, which the archive rule permits.
    #: Anything else is a code path reaching out of the repo and must be justified here
    #: before it is added, not discovered later.
    ALLOWED_TOP_LEVEL_LINKS = {
        "micromamba",
        "hydromt_sfincs",
        "sfincs-cpu.sif",
        "sfincs-desktop.sif",
        "refs",
        # 2026-09-03: run dirs live on /scratch/tpj8 (1 TB tier); the target is checked by
        # test_experiments_is_writable_and_not_in_the_archive below.
        "experiments",
    }

    def test_top_level_symlinks_are_declared(self):
        """A symlink is fine under data/ and for the declared set; nothing else."""
        for p in ROOT.glob("*"):
            if p.is_symlink() and p.name not in self.ALLOWED_TOP_LEVEL_LINKS:
                self.fail(
                    f"undeclared top-level symlink {p.name} -> {p.readlink()}. Add it to "
                    "ALLOWED_TOP_LEVEL_LINKS with a reason, or put it under data/."
                )

    def test_experiments_is_writable_and_not_in_the_archive(self):
        """experiments/ may be a symlink (2026-09-03: it points at /scratch, the 1 TB
        tier), but its TARGET must be a writable directory outside the read-only archive.
        The floodmap cache, metrics.csv and every staged model are WRITES into it."""
        import os

        exp = ROOT / "experiments"
        if not exp.exists():
            return
        target = exp.resolve()
        self.assertTrue(target.is_dir(), f"experiments/ resolves to a non-directory: {target}")
        self.assertTrue(
            os.access(target, os.W_OK),
            f"experiments/ resolves to a read-only location: {target}",
        )
        for name in ARCHIVE_NAMES:
            self.assertNotIn(
                name,
                target.parts,
                f"experiments/ resolves INTO the archive ({name}): {target}",
            )


class TestNoProjEnvInHpc(unittest.TestCase):
    """⭐ ``$PROJ`` must never be read as the repo root.

    The login profile on this account exports ``PROJ=$HOME/nj_sandy_sfincs`` — the TOOLCHAIN
    directory, not a repo — and the batch scripts used to do ``PROJ="${PROJ:-$PWD}"``
    followed by ``export NJ_ROOT="$PROJ"``. Whenever the variable was already set (on an
    interactive node it always is) that pointed NJ_ROOT and PYTHONPATH at another tree
    entirely, silently, with everything still resolving.

    ``PROJ`` is also not read by the PROJ library — that is ``PROJ_LIB`` / ``PROJ_DATA`` —
    so the export never did any work in the first place.
    """

    def test_no_proj_env_in_hpc(self):
        offenders = []
        pat = re.compile(r"\$\{?PROJ\}?[^_A-Z]|(?<![_A-Z])PROJ=")
        for p in sorted((ROOT / "hpc").rglob("*")):
            if not p.is_file() or p.suffix not in (".sh", ".slurm"):
                continue
            for i, line in enumerate(p.read_text(errors="ignore").splitlines(), 1):
                code = line.split("#", 1)[0]  # comments may DISCUSS the trap
                if not code.strip():
                    continue
                if "PROJ_LIB" in code or "PROJ_DATA" in code:
                    continue
                if pat.search(code + " "):
                    offenders.append(f"{p.relative_to(ROOT)}:{i}: {line.strip()[:90]}")
        self.assertEqual(
            offenders,
            [],
            "hpc scripts use a $PROJ shell variable:\n  " + "\n  ".join(offenders) + "\n"
            "  Locate the repo instead: in a .slurm, `cd \"${SLURM_SUBMIT_DIR:-$PWD}\"` "
            "then `REPO=\"$PWD\"` (sbatch copies the script to the spool dir, so "
            "BASH_SOURCE is wrong there); in a .sh, "
            "`REPO=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")/..\" && pwd)\"`.",
        )

    def test_package_asserts_nj_root(self):
        """The runtime half of the same guard."""
        src = (ROOT / "nj_sfincs" / "__init__.py").read_text()
        self.assertIn("NJ_ROOT", src)
        self.assertIn("raise RuntimeError", src)


class TestGitignore(unittest.TestCase):
    def test_gitignore_does_not_ignore_itself(self):
        """The previous repo carried a bare ``.gitignore`` line, so a fresh clone got NO
        ignore rules at all and every staged model, raster and log showed up untracked."""
        gi = ROOT / ".gitignore"
        if not gi.exists():
            self.skipTest("no .gitignore")
        lines = [ln.strip() for ln in gi.read_text().splitlines()]
        self.assertNotIn(".gitignore", lines)

    def test_experiments_and_data_bulk_are_ignored(self):
        gi = (ROOT / ".gitignore").read_text()
        # No trailing slash: experiments/ is a symlink to /scratch (2026-09-03), and a
        # `dir/` pattern never matches a symlink.
        self.assertRegex(gi, r"(?m)^experiments$")
        self.assertIn("data/*", gi)


class TestEstimatorDefault(unittest.TestCase):
    """🔴 The HWM estimator decides the SIGN of the bias, and therefore every ranking.

    Under ``max`` one reference arm is +0.32 m (too wet) and arms that remove water win;
    under ``median`` it is −0.21 m and the same arms lose. ``max`` is also unbounded in the
    radius — adding candidates can only push it up, so it has no converged value, and its
    argmax sat on the search window's OUTER RING for essentially every mark.
    """

    def test_hwm_estimator_default_is_median(self):
        from nj_sfincs.validate import HWM_ESTIMATOR_DEFAULT, HWM_ESTIMATORS

        self.assertEqual(HWM_ESTIMATOR_DEFAULT, "median")
        self.assertIn("max", HWM_ESTIMATORS, "max stays available for diagnosis")

    def test_every_hwm_row_is_stamped(self):
        """A bias with no estimator and radius beside it is not comparable to anything."""
        import inspect

        from nj_sfincs.validate import metrics

        src = inspect.getsource(metrics.hwm_metrics)
        self.assertIn('"hwm_estimator": estimator', src)
        self.assertIn('"hwm_radius_m": float(radius_m)', src)

    def test_unknown_estimator_raises(self):
        import numpy as np

        from nj_sfincs.validate import hwm_metrics

        with self.assertRaises(ValueError):
            hwm_metrics(np.zeros((2, 2)), np.zeros((2, 2)), estimator="mean")


class TestProvenanceIsWiredIn(unittest.TestCase):
    """An UNCALLED provenance module reads like coverage and provides none.

    If this ever fails, the honest fix is to delete ``provenance.py``, not to silence it.
    """

    def test_finalize_writes_a_manifest(self):
        import inspect

        from nj_sfincs import model

        src = inspect.getsource(model.finalize)
        self.assertIn("provenance", src)
        self.assertIn("provenance.txt", src)


if __name__ == "__main__":
    unittest.main()
