"""``scripts/retire_arm.py`` must be safe before it is destructive.

Pattern of ``tests/test_domain_and_staging.py::TestStagingIsSafeBeforeItIsDestructive``:
a SYNTHETIC experiment root, canary keeps, a hard-linked input pair, and SPIES on
``os.replace`` / ``os.unlink`` so the ORDER is what the test asserts — every move precedes
the first unlink, a verify failure yields zero unlinks, and the manifest run is byte-identical.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import retire_arm as ra  # noqa: E402


def _hash_tree(root: Path) -> dict[str, tuple[int, int]]:
    return {
        str(p.relative_to(root)): (p.stat().st_size, p.stat().st_ino)
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def _make_root(tmp: Path, arm: str = "wave-probe") -> Path:
    root = tmp / "experiments"
    tpl = root / "_template_sealed"
    tpl.mkdir(parents=True)
    (tpl / "sfincs.nc").write_bytes(b"m" * 4096)
    (tpl / "sfincs_subgrid.nc").write_bytes(b"s" * 2048)
    run = root / arm
    (run / "gis").mkdir(parents=True)
    (run / "subgrid").mkdir()
    # hard-linked inputs (free nothing) + one private input (frees)
    os.link(tpl / "sfincs.nc", run / "sfincs.nc")
    os.link(tpl / "sfincs_subgrid.nc", run / "sfincs_subgrid.nc")
    (run / "roughness.nc").write_bytes(b"r" * 1024)
    (run / "subgrid" / "dep_0.tif").write_bytes(b"d" * 512)
    (run / "sfincs_map.nc").write_bytes(b"MAP" * 3000)
    (run / "floodmap_hmax_lev3.tif").write_bytes(b"F" * 700)
    (run / "sfincs.20121029.000000.rst").write_bytes(b"R" * 300)
    (run / "snapwave.upw").write_bytes(b"u" * 100)
    # keeps (canaries)
    (run / "sfincs.inp").write_text("tstop = canary\n")
    (run / "sfincs.log").write_text("log canary\n")
    (run / "sfincs_his.nc").write_bytes(b"HIS" * 200)
    (run / "provenance.txt").write_text("prov canary\n")
    (run / "engine.txt").write_text("bin:canary\n")
    (run / "snapwave.bnd").write_text("bnd\n")
    (run / "snapwave.bhs").write_text("bhs\n")
    (run / "sfincs_netamp.nc").write_bytes(b"N" * 50)
    (run / "subgrid_subgrid_diff.json").write_text("{}\n")
    (run / ".window").write_text("w\n")
    (run / "gis" / "obs.geojson").write_text("{}\n")
    gal = root / "floodmaps"
    gal.mkdir()
    (gal / f"{arm}_hmax_lev3.tif").write_bytes(b"G" * 900)
    old = time.time() - 3600
    for p in root.rglob("*"):
        os.utime(p, (old, old))
    return root


class TestRetireIsSafeBeforeItIsDestructive(unittest.TestCase):
    def test_plan_classifies_everything_and_counts_true_reclaim_on_singletons(self):
        with tempfile.TemporaryDirectory() as td:
            root = _make_root(Path(td))
            p = ra.plan("wave-probe", root, check_queue=False)
            acts = {e.rel: e.action for e in p.entries}
            self.assertEqual(acts["sfincs.inp"], "KEEP")
            self.assertEqual(acts["gis"], "KEEP")
            self.assertEqual(acts["subgrid"], "DELETE")
            self.assertEqual(acts["sfincs.20121029.000000.rst"], "DELETE")
            self.assertEqual(acts["floodmaps/wave-probe_hmax_lev3.tif"], "DELETE")
            # hard-linked sfincs.nc (4096) + sfincs_subgrid.nc (2048) are APPARENT only
            self.assertEqual(p.apparent_reclaim - p.true_reclaim, 4096 + 2048)
            self.assertEqual(p.true_reclaim, 1024 + 512 + 9000 + 700 + 300 + 100 + 900)

    def test_manifest_run_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as td:
            root = _make_root(Path(td))
            before = _hash_tree(root)
            with mock.patch.object(ra, "_jobs_named", return_value=[]):
                rc = ra.main(["wave-probe", "--root", str(root)])
            self.assertEqual(rc, 0)
            self.assertEqual(_hash_tree(root), before)
            self.assertFalse((root / "_retired").exists())

    def test_refusals(self):
        with tempfile.TemporaryDirectory() as td:
            root = _make_root(Path(td))
            (root / "_subgrid_buildings").mkdir()
            for bad in (
                "_template_sealed",
                "_subgrid_buildings",
                "_retired",
                "floodmaps",
            ):
                with self.assertRaises(ra.Refused):
                    ra.plan(bad, root, check_queue=False)
            (root / "wave-probe" / "restart_segments").mkdir()
            with self.assertRaises(ra.Refused):
                ra.plan("wave-probe", root, check_queue=False)
            (root / "wave-probe" / "restart_segments").rmdir()
            (root / "wave-probe" / "mystery.bin").write_bytes(b"?")
            with self.assertRaisesRegex(ra.Refused, "unclassified.*mystery.bin"):
                ra.plan("wave-probe", root, check_queue=False)
            (root / "wave-probe" / "mystery.bin").unlink()
            os.utime(root / "wave-probe" / "sfincs_map.nc")  # fresh = still running
            with self.assertRaisesRegex(ra.Refused, "30 min"):
                ra.plan("wave-probe", root, check_queue=False)
            with mock.patch.object(ra, "_jobs_named", return_value=["1 v3_wave-probe"]):
                old = time.time() - 3600
                os.utime(root / "wave-probe" / "sfincs_map.nc", (old, old))
                with self.assertRaisesRegex(ra.Refused, "job"):
                    ra.plan("wave-probe", root)
            (root / "_retired" / "wave-probe").mkdir(parents=True)
            with self.assertRaisesRegex(ra.Refused, "one-way"):
                ra.plan("wave-probe", root, check_queue=False)

    def test_every_move_precedes_the_first_unlink(self):
        with tempfile.TemporaryDirectory() as td:
            root = _make_root(Path(td))
            p = ra.plan("wave-probe", root, "test", check_queue=False)
            events: list[str] = []
            real_replace, real_unlink = os.replace, os.unlink

            def spy_replace(src, dst):
                events.append("move")
                return real_replace(src, dst)

            def spy_unlink(path):
                events.append("unlink")
                return real_unlink(path)

            with (
                mock.patch.object(os, "replace", spy_replace),
                mock.patch.object(os, "unlink", spy_unlink),
            ):
                rec = ra.apply(p)
            n_keep = len(p.keeps)
            self.assertEqual(events[:n_keep], ["move"] * n_keep)
            self.assertNotIn("move", events[n_keep:])
            self.assertGreater(events.count("unlink"), 0)
            ret = root / "_retired" / "wave-probe"
            self.assertEqual((ret / "sfincs.inp").read_text(), "tstop = canary\n")
            self.assertEqual((ret / "gis" / "obs.geojson").read_text(), "{}\n")
            self.assertFalse((root / "wave-probe").exists())
            self.assertFalse((root / "floodmaps" / "wave-probe_hmax_lev3.tif").exists())
            self.assertTrue((root / "_template_sealed" / "sfincs.nc").exists())
            self.assertEqual(
                (root / "_template_sealed" / "sfincs.nc").stat().st_nlink, 1
            )
            got = json.loads((ret / ".retired").read_text())
            self.assertEqual(got["reason"], "test")
            self.assertEqual(sorted(got["kept"]), sorted(e.rel for e in p.keeps))
            self.assertEqual(rec["true_reclaim_bytes"], p.true_reclaim)
            self.assertIn(
                "`wave-probe`", (root / "_retired" / "MANIFEST.md").read_text()
            )

    def test_verify_failure_means_zero_unlinks(self):
        with tempfile.TemporaryDirectory() as td:
            root = _make_root(Path(td))
            p = ra.plan("wave-probe", root, "test", check_queue=False)
            unlinks: list[str] = []
            with (
                mock.patch.object(
                    ra,
                    "_verify_moved",
                    side_effect=RuntimeError("simulated short move"),
                ),
                mock.patch.object(os, "unlink", lambda x: unlinks.append(str(x))),
            ):
                with self.assertRaises(RuntimeError):
                    ra.apply(p)
            self.assertEqual(unlinks, [])
            self.assertTrue((root / "wave-probe" / "sfincs_map.nc").exists())
            self.assertFalse((root / "_retired" / "wave-probe" / ".retired").exists())


if __name__ == "__main__":
    unittest.main()
