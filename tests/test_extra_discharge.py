"""``Experiment.extra_discharge`` (2026-10-17): an arm ADDS point sources to the staged
``netsrcdisfile`` after the write — the template's sources keep exactly what SFINCS would
have read (linear interpolation onto the union time axis), the file gets a fresh inode
(a hard-linked staged file is never written through), and a source on an inactive face or a
series that does not cover the run window is refused. Plus the EurOtop formulas in
``scripts/eurotop_overtopping.py`` and the Deal Lake arm's registry entry.
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
import tempfile
import unittest
from dataclasses import fields
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from nj_sfincs import model
from nj_sfincs.config import ROOT

INP = """tref                 = 20121028 000000
tstart               = 20121028 000000
tstop                = 20121031 000000
epsg                 = 32618
netsrcdisfile        = sfincs_netsrcdisfile.nc
"""
FX = np.array([500_000.0, 500_100.0, 500_200.0, 500_300.0])
FY = np.full(4, 4_400_000.0)
MASK = np.array([1, 1, 0, 1], "u1")


def _stage(d: Path) -> None:
    (d / "sfincs.inp").write_text(INP)
    xr.Dataset(
        {
            "mesh2d_face_x": ("mesh2d_nFaces", FX),
            "mesh2d_face_y": ("mesh2d_nFaces", FY),
            "mask": ("mesh2d_nFaces", MASK),
        }
    ).to_netcdf(d / "sfincs.nc")
    t = pd.date_range("2012-10-28", "2012-10-31", freq="1D")
    xr.Dataset(
        {"discharge": (("time", "stations"), np.array([[1.0, 10.0], [2.0, 20.0], [5.0, 50.0], [3.0, 30.0]]))},
        coords={
            "time": t.values,
            "stations": [0, 1],
            "x": ("stations", FX[:2]),
            "y": ("stations", FY[:2]),
            "area_scale": ("stations", [3.0, 1.0]),
        },
    ).to_netcdf(
        d / "sfincs_netsrcdisfile.nc",
        encoding={"time": {"units": "minutes since 2012-10-28 00:00:00", "dtype": "float64"}},
    )


def _extra(p: Path, x=FX[3], start="2012-10-28", end="2012-10-31") -> np.ndarray:
    t = pd.date_range(start, end, freq="1h")
    q = np.sin(np.linspace(0, math.pi, len(t))) * 30.0
    xr.Dataset(
        {"discharge": (("time", "index"), q[:, None])},
        coords={"time": t.values, "index": [0], "x": ("index", [x]), "y": ("index", [FY[0]]),
                "name": ("index", ["deal_test"])},
    ).to_netcdf(p)
    return q


class TestAppendExtraDischarge(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.d = Path(self._td.name) / "arm"
        self.d.mkdir()
        _stage(self.d)
        self.src = Path(self._td.name) / "extra.nc"

    def test_appends_and_keeps_template_sources(self):
        q = _extra(self.src)
        link = Path(self._td.name) / "other_run_link.nc"
        os.link(self.d / "sfincs_netsrcdisfile.nc", link)
        before = link.read_bytes()
        rec = model.append_extra_discharge(self.d, self.src)
        self.assertEqual(link.read_bytes(), before, "wrote THROUGH a hard link")
        with xr.open_dataset(self.d / "sfincs_netsrcdisfile.nc", decode_times=False) as raw:
            # what hydromt writes too (the engine reads blanks after the date as 00:00:00)
            self.assertTrue(raw["time"].attrs["units"].startswith("minutes since 2012-10-28"))
            self.assertEqual(set(raw.dims), {"time", "stations"})
            for v in ("x", "y", "discharge", "time"):
                self.assertIn(v, raw.variables)
        with xr.open_dataset(self.d / "sfincs_netsrcdisfile.nc") as ds:
            self.assertEqual(ds.sizes["stations"], 3)
            self.assertEqual(ds.sizes["time"], 73)
            qq = ds["discharge"].values
            # template station 0 on the hourly axis = its own linear interpolation
            hrs = np.arange(73.0)
            np.testing.assert_allclose(qq[:, 0], np.interp(hrs, [0, 24, 48, 72], [1, 2, 5, 3]))
            np.testing.assert_allclose(qq[::24, 1], [10, 20, 50, 30])
            np.testing.assert_allclose(qq[:, 2], q)
            np.testing.assert_allclose(ds["x"].values, [FX[0], FX[1], FX[3]])
            np.testing.assert_allclose(ds["area_scale"].values, [3.0, 1.0, 1.0])
        self.assertEqual(rec["stations"], [2])
        self.assertEqual(rec["face"], [3])
        side = json.loads((self.d / model.EXTRA_DISCHARGE_META).read_text())
        self.assertEqual(side["names"], ["deal_test"])
        self.assertAlmostEqual(side["volume_m3"][0], float(np.sum(0.5 * (q[1:] + q[:-1]) * 3600)), delta=1)

    def test_refuses_inactive_face(self):
        _extra(self.src, x=FX[2])
        with self.assertRaises(SystemExit) as cm:
            model.append_extra_discharge(self.d, self.src)
        self.assertIn("INACTIVE", str(cm.exception))

    def test_refuses_short_series(self):
        _extra(self.src, start="2012-10-29")
        with self.assertRaises(SystemExit) as cm:
            model.append_extra_discharge(self.d, self.src)
        self.assertIn("does not cover", str(cm.exception))

    def test_refuses_without_netsrcdisfile(self):
        (self.d / "sfincs.inp").write_text(INP.replace("netsrcdisfile", "srcfile"))
        _extra(self.src)
        with self.assertRaises(SystemExit):
            model.append_extra_discharge(self.d, self.src)


def _eurotop():
    spec = importlib.util.spec_from_file_location(
        "eurotop_overtopping", ROOT / "scripts" / "eurotop_overtopping.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestEurotopFormulas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _eurotop()

    def test_sloping_matches_eq_5_10(self):
        H, T, ta, rc = 2.0, 10.0, 0.05, 1.0
        xi = ta / math.sqrt(H / (9.81 * T**2 / (2 * math.pi)))
        a = 0.023 / math.sqrt(ta) * xi * math.exp(-((2.7 * rc / (xi * H)) ** 1.3))
        b = 0.09 * math.exp(-((1.5 * rc / H) ** 1.3))
        want = min(a, b) * math.sqrt(9.81 * H**3)
        self.assertAlmostEqual(float(self.m.q_sloping(H, T, ta, rc)), want, places=10)
        self.assertAlmostEqual(want, 5.616e-3, delta=2e-5)

    def test_monotone_through_zero_freeboard(self):
        rc = np.linspace(-0.5, 2.0, 251)
        q = self.m.q_sloping(np.full_like(rc, 2.5), 12.0, 0.035, rc)
        self.assertTrue(np.all(np.diff(q) <= 1e-12), "q must not rise with freeboard")
        qv = self.m.q_vertical(np.full_like(rc, 1.0), rc)
        self.assertTrue(np.all(np.diff(qv) <= 1e-12))
        self.assertAlmostEqual(float(self.m.q_vertical(1.0, 0.0)), 0.062 * math.sqrt(9.81), places=6)

    def test_dry_toe_gives_zero(self):
        self.assertEqual(float(self.m.q_sloping(np.nan, 10.0, 0.05, 0.5)), 0.0)
        self.assertEqual(float(self.m.q_sloping(0.0, 10.0, 0.05, 0.5)), 0.0)

    def test_gamma_beta(self):
        np.testing.assert_allclose(self.m.gamma_beta([0, -30, 120]), [1.0, 1 - 0.189, 1 - 0.504])


class TestDealOvertoppingArm(unittest.TestCase):
    def test_arm_is_the_premier_plus_one_source(self):
        from nj_sfincs.experiments import EXPERIMENTS_BY_DOMAIN

        arms = EXPERIMENTS_BY_DOMAIN["v4_refreeze"]
        a, p = arms["naccs-premier+src-deal-overtop"], arms["naccs-premier"]
        self.assertIsNone(p.extra_discharge)
        self.assertEqual(a.extra_discharge.name, "deal_lake_overtopping_v4_refreeze.nc")
        diff = {f.name for f in fields(a) if getattr(a, f.name) != getattr(p, f.name)}
        self.assertEqual(diff, {"name", "description", "extra_discharge"})


if __name__ == "__main__":
    unittest.main()
