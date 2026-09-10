"""Resume-from-restart-file and stitch (nj_sfincs/restart.py, 2026-09-10).

A preempted solve must (a) pick the newest restart file INSIDE the window it already
wrote, on the zsmax lattice, (b) rewrite sfincs.inp so SFINCS starts there with no
spin-up ramp, and (c) after the resumed solve, stitch the segments into ONE map/his that
reads exactly like an uninterrupted run — with the original inp back in place.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import netCDF4
import numpy as np

from nj_sfincs import restart as R

INP = (
    "tref                 = 20121028 000000\n"
    "tstart               = 20121028 000000\n"
    "tstop                = 20121029 000000\n"
    "tspinup              = 3600.0\n"
    "dtmapout             = 3600.0\n"
    "dtmaxout             = 21600.0\n"
    "dtrstout             = 21600.0\n"
    "obsfile              = sfincs.obs\n"
)
NF = 4
H = 3600.0


def write_map(
    fn: Path, t_start_s: float, t_end_s: float, tmax: list[float], tag: float
):
    """A toy map: zs[t, f] = tag*1000 + t/3600 + f, zsmax[b, f] = tag*1000 + block end."""
    times = np.arange(t_start_s, t_end_s + 1, H)
    with netCDF4.Dataset(fn, "w") as ds:
        ds.createDimension("time", None)
        ds.createDimension("timemax", 4)  # SFINCS pre-sizes; unwritten blocks hold fill
        ds.createDimension("nmesh2d_face", NF)
        tv = ds.createVariable("time", "f4", ("time",))
        tv.units = "seconds since 2012-10-28 00:00:00"
        zs = ds.createVariable(
            "zs", "f4", ("time", "nmesh2d_face"), zlib=True, chunksizes=(1, NF)
        )
        tm = ds.createVariable("timemax", "f4", ("timemax",))
        zm = ds.createVariable("zsmax", "f4", ("timemax", "nmesh2d_face"))
        zb = ds.createVariable("zb", "f4", ("nmesh2d_face",))
        zb[:] = np.arange(NF) * -1.0
        for i, t in enumerate(times):
            tv[i] = t
            zs[i, :] = tag * 1000 + t / H + np.arange(NF)
        for b, te in enumerate(tmax):
            tm[b] = te
            zm[b, :] = tag * 1000 + te / H


def write_his(fn: Path, t_start_s: float, t_end_s: float, tag: float):
    times = np.arange(t_start_s, t_end_s + 1, 600.0)
    with netCDF4.Dataset(fn, "w") as ds:
        ds.createDimension("time", None)
        ds.createDimension("stations", 2)
        tv = ds.createVariable("time", "f4", ("time",))
        pz = ds.createVariable("point_zs", "f4", ("time", "stations"))
        name = ds.createVariable("station_x", "f4", ("stations",))
        name[:] = [1.0, 2.0]
        for i, t in enumerate(times):
            tv[i] = t
            pz[i, :] = tag * 1000 + t / H


class Base(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.d = Path(self._td.name)
        self.addCleanup(self._td.cleanup)
        (self.d / "sfincs.inp").write_text(INP)

    def rst(self, hh: int):
        day, hh = 28 + hh // 24, hh % 24
        (self.d / f"sfincs.201210{day}.{hh:02d}0000.rst").write_bytes(b"x")


class TestPlan(Base):
    def test_fresh_when_nothing_written(self):
        self.assertEqual(R.plan(self.d).action, "fresh")

    def test_resume_picks_newest_inside_written_window(self):
        write_map(self.d / "sfincs_map.nc", 0, 15 * H, [6 * H, 12 * H, 15 * H], tag=1)
        for hh in (6, 12, 18):  # 18 h is from an older, longer trajectory: NOT usable
            self.rst(hh)
        pl = R.plan(self.d)
        self.assertEqual(pl.action, "resume")
        self.assertEqual(pl.rst.name, "sfincs.20121028.120000.rst")

    def test_off_lattice_restart_refused(self):
        write_map(self.d / "sfincs_map.nc", 0, 15 * H, [6 * H, 12 * H], tag=1)
        (self.d / "sfincs.20121028.140000.rst").write_bytes(
            b"x"
        )  # inside a zsmax block
        self.assertEqual(R.plan(self.d).action, "fresh")

    def test_finish_when_map_complete(self):
        write_map(
            self.d / "sfincs_map.nc", 0, 24 * H, [6 * H, 12 * H, 18 * H, 24 * H], tag=1
        )
        self.rst(24)
        self.assertEqual(R.plan(self.d).action, "finish")


class TestPrepareAndFinish(Base):
    def _preempted_at_15h(self):
        write_map(self.d / "sfincs_map.nc", 0, 15 * H, [6 * H, 12 * H, 15 * H], tag=1)
        write_his(self.d / "sfincs_his.nc", 0, 15 * H, tag=1)
        (self.d / "sfincs.log").write_text("first segment\n")
        for hh in (6, 12):
            self.rst(hh)

    def test_prepare_rewrites_inp_and_retires_outputs(self):
        self._preempted_at_15h()
        pl = R.prepare(self.d)
        self.assertEqual(pl.action, "resume")
        text = (self.d / "sfincs.inp").read_text()
        self.assertEqual(R.inp_get(text, "tstart"), "20121028 120000")
        self.assertEqual(R.inp_get(text, "tspinup"), "0.0")
        self.assertEqual(R.inp_get(text, "rstfile"), "sfincs.20121028.120000.rst")
        self.assertEqual(R.inp_get(text, "tstop"), "20121029 000000")  # untouched
        self.assertEqual((self.d / R.ORIG_INP).read_text(), INP)
        self.assertFalse((self.d / "sfincs_map.nc").exists())
        segs = R.segments(self.d)
        self.assertEqual(len(segs), 1)
        self.assertTrue((segs[0] / "sfincs_map.nc").is_file())
        self.assertEqual(
            (segs[0] / "segment_start.txt").read_text().strip(), "20121028 000000"
        )
        # the restart file itself must stay where SFINCS will look for it
        self.assertTrue((self.d / "sfincs.20121028.120000.rst").is_file())

    def test_prepare_is_a_no_op_when_fresh(self):
        R.prepare(self.d)
        self.assertEqual((self.d / "sfincs.inp").read_text(), INP)
        self.assertFalse((self.d / R.SEG_DIR).exists())

    def test_finish_stitches_one_seamless_record(self):
        self._preempted_at_15h()
        R.prepare(self.d)
        # the resumed solve: starts at 12 h, runs to tstop, its own blocks end 18 h / 24 h
        write_map(self.d / "sfincs_map.nc", 12 * H, 24 * H, [18 * H, 24 * H], tag=2)
        write_his(self.d / "sfincs_his.nc", 12 * H, 24 * H, tag=2)
        (self.d / "sfincs.log").write_text("resumed segment\n")
        rep = R.finish(self.d)
        self.assertEqual(rep["segments"], 1)
        with netCDF4.Dataset(self.d / "sfincs_map.nc") as ds:
            t = ds.variables["time"][:]
            self.assertTrue(np.array_equal(t, np.arange(0, 24 * H + 1, H)))
            zs = ds.variables["zs"][:]
            # records before 12 h come from segment 1 (tag 1), from 12 h on from the resume
            self.assertTrue(np.all(zs[:12, 0] == 1000 + np.arange(12)))
            self.assertTrue(np.all(zs[12:, 0] == 2000 + np.arange(12, 25)))
            tm = ds.variables["timemax"][:]
            self.assertTrue(np.array_equal(tm, [6 * H, 12 * H, 18 * H, 24 * H]))
            zm = ds.variables["zsmax"][:, 0]
            self.assertEqual(
                list(zm), [1006, 1012, 2018, 2024]
            )  # 15 h partial block dropped
            self.assertEqual(float(ds.variables["zb"][1]), -1.0)  # static var kept
            self.assertEqual(ds.variables["zs"].chunking(), [1, NF])  # layout preserved
        with netCDF4.Dataset(self.d / "sfincs_his.nc") as ds:
            t = ds.variables["time"][:]
            self.assertTrue(np.array_equal(t, np.arange(0, 24 * H + 1, 600.0)))
            pz = ds.variables["point_zs"][:, 0]
            self.assertTrue(np.all(pz[t < 12 * H] < 1500))
            self.assertTrue(np.all(pz[t >= 12 * H] > 1500))
        # inp restored, rst files gone, segments gone, history kept, log in time order
        self.assertEqual((self.d / "sfincs.inp").read_text(), INP)
        self.assertFalse((self.d / R.ORIG_INP).exists())
        self.assertEqual(R.restart_files(self.d), [])
        self.assertFalse((self.d / R.SEG_DIR).exists())
        self.assertIn("resume from", (self.d / R.HISTORY).read_text())
        log = (self.d / "sfincs.log").read_text()
        self.assertLess(log.index("first segment"), log.index("resumed segment"))

    def test_finish_on_untouched_run_only_drops_rst(self):
        write_map(
            self.d / "sfincs_map.nc", 0, 24 * H, [6 * H, 12 * H, 18 * H, 24 * H], tag=1
        )
        self.rst(24)
        rep = R.finish(self.d)
        self.assertEqual(rep, {"segments": 0, "rst_removed": 1})
        self.assertEqual((self.d / "sfincs.inp").read_text(), INP)


class TestInpHelpers(unittest.TestCase):
    def test_set_replaces_and_appends_in_layout(self):
        out = R.inp_set(
            "tstart               = 1\n", {"tstart": "2", "rstfile": "f.rst"}
        )
        self.assertEqual(
            out, "tstart               = 2\nrstfile              = f.rst\n"
        )

    def test_add_restart_output_aligns_lattices(self):
        out = R.add_restart_output("dtmaxout             = 86400.0\n", 21600.0)
        self.assertEqual(R.inp_get(out, "dtmaxout"), "21600.0")
        self.assertEqual(R.inp_get(out, "dtrstout"), "21600.0")


if __name__ == "__main__":
    unittest.main()
