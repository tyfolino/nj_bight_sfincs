"""scripts/engine_gate.py `make` is safe before it is useful.

Pins the two things that would silently corrupt a scored run: a gate dir must never
HARD-LINK an output (SFINCS truncates map/his/upw on create, and a linked inode is the
source's file), and a source whose map is still being written must be refused.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

from nj_sfincs.config import ROOT


def _load():
    spec = importlib.util.spec_from_file_location(
        "engine_gate", ROOT / "scripts" / "engine_gate.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


INP = (
    "tref                 = 20121028 000000\n"
    "tstart               = 20121028 000000\n"
    "tstop                = 20121031 000000\n"
    "dtmaxout             = 21600.0\n"
    "dtrstout             = 21600.0\n"
    "rstfile              = sfincs.20121028.060000.rst\n"
    "qtrfile              = sfincs.nc\n"
    "snapwave_bndfile     = snapwave.bnd\n"
)


def _run_dir(td: str, map_age_s: float) -> Path:
    d = Path(td) / "arm"
    (d / "subgrid").mkdir(parents=True)
    (d / "sfincs.inp").write_text(INP)
    for name in (
        "sfincs.nc",
        "sfincs_subgrid.nc",
        "roughness.nc",
        "sfincs_netamuv.nc",
        "snapwave.bnd",
        "snapwave.bhs",
        "sfincs.obs",
        "sfincs_map.nc",
        "sfincs_his.nc",
        "snapwave.upw",
        "sfincs.log",
        "sfincs.20121028.060000.rst",
        "floodmap_hmax_lev3.tif",
    ):
        (d / name).write_bytes(b"x" * 16)
    (d / "subgrid" / "z_zmin.tif").write_bytes(b"y" * 16)
    old = time.time() - map_age_s
    os.utime(d / "sfincs_map.nc", (old, old))
    return d


class TestMakeIsSafe(unittest.TestCase):
    def test_outputs_are_never_staged_and_inputs_are_linked(self):
        G = _load()
        with tempfile.TemporaryDirectory() as td:
            src = _run_dir(td, map_age_s=3600)
            dst = Path(td) / "gate"
            G.make(src, dst, hours=12)
            names = {p.name for p in dst.iterdir()}
            for out in (
                "sfincs_map.nc",
                "sfincs_his.nc",
                "snapwave.upw",
                "sfincs.log",
                "sfincs.20121028.060000.rst",
                "floodmap_hmax_lev3.tif",
            ):
                self.assertNotIn(out, names, f"{out} must never be staged")
            for inp in (
                "sfincs.nc",
                "sfincs_subgrid.nc",
                "roughness.nc",
                "sfincs_netamuv.nc",
                "snapwave.bnd",
                "sfincs.obs",
            ):
                self.assertIn(inp, names)
                self.assertEqual(
                    (dst / inp).stat().st_ino,
                    (src / inp).stat().st_ino,
                    f"{inp} should be hard-linked on the same filesystem",
                )
            self.assertTrue((dst / "subgrid" / "z_zmin.tif").exists())
            # sfincs.inp is a COPY (rewritten), never a link
            self.assertNotEqual(
                (dst / "sfincs.inp").stat().st_ino, (src / "sfincs.inp").stat().st_ino
            )
            text = (dst / "sfincs.inp").read_text()
            self.assertIn("tstop                = 20121028 120000", text)
            self.assertNotIn("dtrstout", text)
            self.assertNotIn("rstfile", text)
            self.assertIn("dtmaxout", text)
            self.assertEqual(
                src.joinpath("sfincs.inp").read_text(), INP, "source untouched"
            )

    def test_refuses_a_live_source(self):
        G = _load()
        with tempfile.TemporaryDirectory() as td:
            src = _run_dir(td, map_age_s=60)
            with self.assertRaises(SystemExit) as cm:
                G.make(src, Path(td) / "gate", hours=12)
            self.assertIn("REFUSING", str(cm.exception))
            self.assertFalse((Path(td) / "gate" / "sfincs.inp").exists())

    def test_refuses_a_nonempty_destination(self):
        G = _load()
        with tempfile.TemporaryDirectory() as td:
            src = _run_dir(td, map_age_s=3600)
            dst = Path(td) / "gate"
            dst.mkdir()
            (dst / "leftover").write_text("")
            with self.assertRaises(SystemExit):
                G.make(src, dst, hours=12)

    def test_full_window_keeps_tstop(self):
        G = _load()
        with tempfile.TemporaryDirectory() as td:
            src = _run_dir(td, map_age_s=3600)
            dst = Path(td) / "gate"
            G.make(src, dst, hours=None)
            self.assertIn(
                "tstop                = 20121031 000000",
                (dst / "sfincs.inp").read_text(),
            )


if __name__ == "__main__":
    unittest.main()
