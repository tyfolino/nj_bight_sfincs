"""``Experiment.meteo_from`` (2026-10-06): a wind-* arm's wind + pressure files are
REPLACED after the write by a pre-built engine-ready pair (the NACCS blend), byte for
byte, as fresh inodes — and refused when the pair lacks the corner marker, leaves an
active face outside the grid, or meets ``wind_scale``.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import numpy as np
import xarray as xr

from nj_sfincs import meteo_grid as mg
from nj_sfincs import model

FILES = model.METEO_FROM_FILES


def _write_meteo(d: Path, xc, yc, value: float, mark: bool = True) -> None:
    d.mkdir(parents=True, exist_ok=True)
    X, _ = np.meshgrid(xc, yc)
    for f, var in zip(FILES, ("eastward_wind", "barometric_pressure")):
        xr.Dataset(
            {var: (("time", "y", "x"), np.full((2, *X.shape), value))},
            coords={
                "time": np.datetime64("2012-10-28")
                + np.arange(2) * np.timedelta64(1, "h"),
                "y": yc,
                "x": xc,
            },
        ).to_netcdf(d / f)
    if mark:
        mg.fix_meteo_grid_origin(d)


def _write_mesh(d: Path, fx, fy) -> None:
    xr.Dataset(
        {
            "mesh2d_face_x": ("mesh2d_nFaces", np.asarray(fx, "f8")),
            "mesh2d_face_y": ("mesh2d_nFaces", np.asarray(fy, "f8")),
            "mask": ("mesh2d_nFaces", np.ones(len(fx), "u1")),
        }
    ).to_netcdf(d / "sfincs.nc")


XC = 500_000.0 + 1000.0 * np.arange(10)
YC = (4_400_000.0 + 1000.0 * np.arange(10))[::-1]
INSIDE = ([503_000.0, 505_500.0], [4_403_000.0, 4_405_500.0])


class TestMeteoFrom(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        root = Path(self._td.name)
        self.src, self.arm, self.other = root / "src", root / "arm", root / "other"
        _write_meteo(self.src, XC, YC, 7.0)
        _write_meteo(self.arm, XC, YC, 1.0)  # the template's (ERA5) copy
        _write_mesh(self.arm, *INSIDE)

    def test_copies_byte_for_byte_as_new_inodes(self):
        # a hard link into the arm must NOT be written through
        self.other.mkdir()
        os.link(self.arm / FILES[0], self.other / FILES[0])
        before = (self.other / FILES[0]).read_bytes()
        model.replace_meteo_from(self.arm, self.src)
        for f in FILES:
            self.assertEqual((self.arm / f).read_bytes(), (self.src / f).read_bytes())
            self.assertEqual((self.arm / f).stat().st_nlink, 1)
            self.assertNotEqual(
                (self.arm / f).stat().st_ino, (self.src / f).stat().st_ino
            )
        self.assertEqual((self.other / FILES[0]).read_bytes(), before)
        self.assertEqual(
            sorted(p.name for p in self.arm.iterdir()), sorted([*FILES, "sfincs.nc"])
        )

    def test_refuses_an_unmarked_source_and_leaves_the_arm_alone(self):
        _write_meteo(self.src, XC, YC, 7.0, mark=False)
        before = (self.arm / FILES[0]).read_bytes()
        with self.assertRaises(SystemExit):
            model.replace_meteo_from(self.arm, self.src)
        self.assertEqual((self.arm / FILES[0]).read_bytes(), before)

    def test_refuses_a_missing_file(self):
        (self.src / FILES[1]).unlink()
        with self.assertRaises(SystemExit):
            model.replace_meteo_from(self.arm, self.src)

    def test_refuses_active_faces_outside_the_grid(self):
        _write_mesh(self.arm, [503_000.0, 520_000.0], [4_403_000.0, 4_405_000.0])
        with self.assertRaises(SystemExit):
            model.replace_meteo_from(self.arm, self.src)

    def test_finalize_refuses_meteo_from_with_wind_scale(self):
        from nj_sfincs.config import BaseConfig, WaveConfig

        with self.assertRaises(SystemExit):
            model.finalize(
                WaveConfig(use_waves=False),
                BaseConfig.__new__(BaseConfig),
                None,
                self.arm,
                None,
                wind_scale=1.2,
                meteo_from=self.src,
            )

    def test_finalize_calls_it_after_the_corner_fix(self):
        import inspect

        src = inspect.getsource(model.finalize)
        self.assertLess(
            src.index("meteo_grid.fix_meteo_grid_origin(model_dir, expect_fixed"),
            src.index("replace_meteo_from(model_dir, meteo_from)"),
        )

    def test_prepare_experiment_passes_it(self):
        from nj_sfincs.config import ROOT

        text = (ROOT / "run_experiments.py").read_text()
        self.assertIn("meteo_from=exp.meteo_from", text)

    def test_default_is_none(self):
        from nj_sfincs.config import Experiment, WaveConfig

        self.assertIsNone(Experiment("x", WaveConfig(use_waves=False)).meteo_from)


if __name__ == "__main__":
    unittest.main()
