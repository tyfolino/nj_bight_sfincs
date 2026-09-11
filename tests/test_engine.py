"""The engine epoch (nj_sfincs/provenance.py engine helpers, nj_sfincs/run.py engine choice).

Pins: the SnapWave-direction truth table (FINDINGS §43) on synthetic inp + log; the label
inferred for pre-epoch runs; engine.txt round-trip; the subgrid sha cache; and that
``submit_slurm`` refuses no-engine / two-engines / a missing engine BEFORE it looks for
sbatch, so the refusal is testable off-cluster and a batch job can never start on a
fallback.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from nj_sfincs import provenance as P
from nj_sfincs import run as R

LOG_OLD = (
    "Build-Revision: $Rev: v2.3.3 mt. Faber+\nBuild-Date: $Date: 2025-05-12\n"
    "Build-Revision: $Rev: svn 197-branch:SnapWave_IG\n"
)
LOG_FIXED = "Build-Revision: $Rev: v2.3.3 mt. Faber+ nj-winddir-fix-1\n"
LOG_GALIBIER = "Build-Revision: $Rev: v2.4.0 Galibier Release\n"


def _dir(td, inp: str, log: str | None) -> Path:
    d = Path(td) / "arm"
    d.mkdir(exist_ok=True)
    (d / "sfincs.inp").write_text(inp)
    if log is not None:
        (d / "sfincs.log").write_text(log)
    return d


class TestSnapWaveDirection(unittest.TestCase):
    def test_truth_table(self):
        cases = [
            ("snapwave = 0\n", LOG_OLD, "off"),
            ("snapwave = 1\nsnapwave_wind = 0\n", LOG_OLD, "imposed"),
            ("snapwave = 1\nsnapwave_wind = 1\n", LOG_OLD, "wind"),
            ("snapwave = 1\nsnapwave_wind = 1\n", LOG_FIXED, "imposed"),
            (
                "snapwave = 1\nsnapwave_wind = 1\n",
                None,
                "wind",
            ),  # no log: assume unpatched
        ]
        for inp, log, want in cases:
            with tempfile.TemporaryDirectory() as td:
                self.assertEqual(
                    P.snapwave_direction(_dir(td, inp, log)), want, (inp, log)
                )

    def test_engine_txt_wins_over_the_log(self):
        """A patched-branch build recorded in engine.txt counts even if the log is old."""
        with tempfile.TemporaryDirectory() as td:
            d = _dir(td, "snapwave = 1\nsnapwave_wind = 1\n", LOG_OLD)
            (d / "engine.txt").write_text(
                "label  bin:x@0\nbuild_branch  nj/snapwave-winddir\n"
                "build_revision  v2.3.3 nj-winddir-fix-1\n"
            )
            self.assertEqual(P.snapwave_direction(d), "imposed")


class TestEngineLabel(unittest.TestCase):
    def test_inferred_labels(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(
                P.engine_label(_dir(td, "", LOG_OLD)),
                "container:v2.3.3-faber (inferred)",
            )
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(
                P.engine_label(_dir(td, "", LOG_GALIBIER)),
                "container:v2.4.0-galibier (inferred)",
            )
        with tempfile.TemporaryDirectory() as td:
            self.assertIn("not run", P.engine_label(_dir(td, "", None)))

    def test_write_and_read_engine(self):
        with tempfile.TemporaryDirectory() as td:
            d = _dir(td, "snapwave = 1\n", LOG_OLD)
            (d / "provenance.txt").write_text(
                "RUN PROVENANCE — arm\n\n[domain]\n  name  v3\n"
            )
            fake = Path(td) / "sfincs-native" / "v2.3.3-test" / "bin" / "sfincs"
            fake.parent.mkdir(parents=True)
            fake.write_bytes(b"\x7fELF-not-really")
            (fake.parent.parent / "BUILD_INFO").write_text(
                "commit    abc123\nbranch    nj/snapwave-winddir\nflags     -O3\n"
            )
            out = P.write_engine(d, "bin", fake, host="h", job_id="1", threads="4")
            self.assertTrue(out.is_file())
            rec = P.read_engine(d)
            self.assertEqual(rec["kind"], "bin")
            self.assertEqual(rec["label"], f"bin:v2.3.3-test@{rec['sha256'][:8]}")
            self.assertEqual(rec["build_commit"], "abc123")
            self.assertEqual(rec["build_branch"], "nj/snapwave-winddir")
            self.assertIn("Faber", rec["build_revision"])
            self.assertIn("SnapWave_IG", rec["snapwave_revision"])
            self.assertEqual(P.engine_label(d), rec["label"])
            prov = (d / "provenance.txt").read_text()
            self.assertEqual(prov.count("[engine]"), 1)
            self.assertIn("[domain]", prov)
            P.write_engine(d, "bin", fake, host="h", job_id="2", threads="4")
            self.assertEqual(
                (d / "provenance.txt").read_text().count("[engine]"),
                1,
                "re-recording replaces the block, never duplicates it",
            )
            self.assertEqual(P.read_engine(d)["job_id"], "2")

    def test_write_engine_refuses_missing_engine(self):
        with tempfile.TemporaryDirectory() as td:
            d = _dir(td, "", LOG_OLD)
            with self.assertRaises(FileNotFoundError):
                P.write_engine(d, "sif", Path(td) / "nope.sif")


class TestSubgridSha(unittest.TestCase):
    def test_cached_by_inode_size_mtime(self):
        with tempfile.TemporaryDirectory() as td:
            d = _dir(td, "", None)
            f = d / "sfincs_subgrid.nc"
            f.write_bytes(b"a" * 1000)
            s1 = P.subgrid_sha256(d)
            self.assertTrue((d / ".subgrid_sha256").is_file())
            (d / ".subgrid_sha256").write_text(
                "deadbeef " + (d / ".subgrid_sha256").read_text().split(" ", 1)[1]
            )
            self.assertEqual(
                P.subgrid_sha256(d),
                "deadbeef",
                "cache is trusted while the key matches",
            )
            f.write_bytes(b"b" * 2000)
            s2 = P.subgrid_sha256(d)
            self.assertNotEqual(s2, "deadbeef", "a changed file invalidates the cache")
            self.assertNotEqual(s1, s2)


class TestSubmitRefusesBeforeSbatch(unittest.TestCase):
    def test_no_engine(self):
        with self.assertRaises(RuntimeError) as cm:
            R.submit_slurm("/nonexistent", sif=None, binary=None)
        self.assertIn("no engine", str(cm.exception))

    def test_two_engines(self):
        with self.assertRaises(RuntimeError) as cm:
            R.submit_slurm("/nonexistent", sif="a.sif", binary="b")
        self.assertIn("exactly one", str(cm.exception))

    def test_missing_engine_file(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(FileNotFoundError):
                R.submit_slurm("/nonexistent", sif=str(Path(td) / "nope.sif"))
            with self.assertRaises(FileNotFoundError):
                R.submit_slurm("/nonexistent", binary=str(Path(td) / "nope"))

    def test_env_fallback_is_gone(self):
        """SFINCS_SIF in the environment must NOT silently pick the engine for run_sfincs."""
        env = dict(os.environ)
        os.environ.pop("SFINCS_SIF", None)
        os.environ.pop("SFINCS_BIN", None)
        try:
            with tempfile.TemporaryDirectory() as td:
                with self.assertRaises(RuntimeError) as cm:
                    R.run_sfincs(td)
                self.assertIn("no engine", str(cm.exception))
        finally:
            os.environ.clear()
            os.environ.update(env)


if __name__ == "__main__":
    unittest.main()
