"""``premier.output_complete`` reads output times as seconds since TREF (2026-11-24).

SFINCS writes ``time`` since ``tref``, not ``tstart``; a spin-up arm (tstart > tref) ends
at ``tstop - tref``. The old check compared against ``tstop - tstart``.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import xarray as xr

from nj_sfincs import premier

H = 3600.0


def _run(tref, tstart, tstop, last, *, his_last=None, fill=False):
    d = Path(tempfile.mkdtemp())
    lines = [f"tstart = {tstart}", f"tstop = {tstop}", "dtmapout = 3600"]
    lines.append("dthisout = 600")
    if tref:
        lines.append(f"tref = {tref}")
    (d / "sfincs.inp").write_text("\n".join(lines) + "\n")
    t = np.arange(0, last + 1, H)
    zs = np.full((2, 2), -99999.0 if fill else 1.0)
    xr.Dataset({"zsmax": (("n", "m"), zs)}, coords={"time": t}).to_netcdf(
        d / "sfincs_map.nc"
    )
    th = np.arange(0, (his_last if his_last is not None else last) + 1, 600.0)
    xr.Dataset(coords={"time": th}).to_netcdf(d / "sfincs_his.nc")
    return d


class TestOutputComplete(unittest.TestCase):
    def test_tref_equals_tstart_whole(self):
        d = _run("20121028 000000", "20121028 000000", "20121029 000000", 24 * H)
        self.assertEqual(premier.output_complete(d), (True, []))

    def test_missing_tref_means_tstart(self):
        d = _run(None, "20121028 000000", "20121029 000000", 24 * H)
        self.assertTrue(premier.output_complete(d)[0])

    def test_spinup_whole(self):
        # tstart 6 h after tref: output runs to tstop - tref = 24 h
        d = _run("20121028 000000", "20121028 060000", "20121029 000000", 24 * H)
        self.assertEqual(premier.output_complete(d), (True, []))

    def test_spinup_truncated(self):
        # ends at 20 h: the old (tstop - tstart = 18 h) rule called this whole
        d = _run("20121028 000000", "20121028 060000", "20121029 000000", 20 * H)
        ok, problems = premier.output_complete(d)
        self.assertFalse(ok)
        self.assertTrue(any("sfincs_map.nc" in p for p in problems))

    def test_spinup_his_truncated(self):
        d = _run(
            "20121028 000000",
            "20121028 060000",
            "20121029 000000",
            24 * H,
            his_last=20 * H,
        )
        ok, problems = premier.output_complete(d)
        self.assertFalse(ok)
        self.assertTrue(any("sfincs_his.nc" in p for p in problems))

    def test_all_fill_zsmax(self):
        d = _run(
            "20121028 000000", "20121028 000000", "20121029 000000", 24 * H, fill=True
        )
        self.assertFalse(premier.output_complete(d)[0])


if __name__ == "__main__":
    unittest.main()
