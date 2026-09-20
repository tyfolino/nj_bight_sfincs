"""``provenance.wind_scale_label`` reads the MEASURED ratio from the files (2026-09-20)."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import xarray as xr

from nj_sfincs import provenance


def _wind(path: Path, scale: float) -> None:
    t = np.arange(3)
    u = np.full((3, 2, 2), 10.0) * scale
    v = np.full((3, 2, 2), -5.0) * scale
    xr.Dataset(
        {
            "eastward_wind": (("time", "y", "x"), u),
            "northward_wind": (("time", "y", "x"), v),
        },
        coords={"time": t, "y": [0.0, 1.0], "x": [0.0, 1.0]},
    ).to_netcdf(path)


class TestWindScaleLabel(unittest.TestCase):
    def test_ratio_is_measured_from_the_files(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "_template_sealed").mkdir()
            (root / "arm").mkdir()
            _wind(root / "_template_sealed" / "sfincs_netamuv.nc", 1.0)
            _wind(root / "arm" / "sfincs_netamuv.nc", 1.10)
            with mock.patch("nj_sfincs.config.exp_root", return_value=root):
                self.assertEqual(provenance.wind_scale_label(root / "arm"), "1.100")
                self.assertEqual(
                    provenance.wind_scale_label(root / "_template_sealed"), "1.000"
                )
            os.remove(root / "arm" / "sfincs_netamuv.nc")
            self.assertEqual(provenance.wind_scale_label(root / "arm"), "none")


if __name__ == "__main__":
    unittest.main()
