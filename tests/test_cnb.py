"""``cnb`` staging (curve number WITH recovery, nj_sfincs/infiltration.py, 2026-10-15)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np


def _toy_dir(td: Path) -> tuple[Path, Path]:
    """A qtrfile with 5 faces (face 2 inactive) + a 3 x 3 ksat raster in EPSG:32618."""
    import rasterio
    import xarray as xr
    from rasterio.transform import from_origin

    d = td / "run"
    d.mkdir()
    xr.Dataset(
        {
            "mask": ("nf", np.array([1, 1, 0, 2, 1], dtype="i1")),
            "scs": ("nf", np.array([1.0, 2.0, 9.0, 0.0, np.nan])),
            "mesh2d_face_x": ("nf", np.array([5.0, 15.0, 25.0, 25.0, 99.0])),
            "mesh2d_face_y": ("nf", np.array([25.0, 15.0, 5.0, 25.0, 99.0])),
        }
    ).to_netcdf(d / "sfincs.nc")
    ks = np.array([[1.0, 2.0, 3.0], [4.0, 500.0, 6.0], [7.0, 8.0, -9999.0]], "f4")
    tif = td / "ksat.tif"
    with rasterio.open(
        tif,
        "w",
        driver="GTiff",
        width=3,
        height=3,
        count=1,
        dtype="float32",
        crs="EPSG:32618",
        transform=from_origin(0, 30, 10, 10),
        nodata=-9999.0,
    ) as dst:
        dst.write(ks, 1)
    return d, tif


class TestCnbArrays(unittest.TestCase):
    def test_dry_start_raises_smax_with_seff(self):
        from nj_sfincs.infiltration import cnb_arrays

        smax, seff, ks = cnb_arrays(
            np.array([1.0, 0.0, np.nan]), np.array([10.0, 500.0, np.nan]), 1.5
        )
        np.testing.assert_allclose(smax, [1.5 * 0.0254, 0, 0], rtol=1e-6)
        np.testing.assert_allclose(seff, [1.5 * 0.0254, 0, 0], rtol=1e-6)
        np.testing.assert_allclose(ks, [36.0, 360.0, 0.0], rtol=1e-6)  # cap 100 µm/s
        self.assertEqual(smax.dtype, np.dtype("<f4"))

    def test_wet_start_keeps_smax_at_s2(self):
        from nj_sfincs.infiltration import cnb_arrays

        smax, seff, _ = cnb_arrays(np.array([2.0]), np.array([1.0]), 0.435)
        np.testing.assert_allclose(smax, [2 * 0.0254], rtol=1e-6)
        np.testing.assert_allclose(seff, [0.435 * 2 * 0.0254], rtol=1e-6)

    def test_refuses_nonpositive_effective(self):
        from nj_sfincs.infiltration import cnb_arrays

        with self.assertRaises(ValueError):
            cnb_arrays(np.array([1.0]), np.array([1.0]), 0.0)


class TestCnbFiles(unittest.TestCase):
    def test_netcdf_is_every_face_zero_where_inactive(self):
        # the engine (quadtree) reads smax / seff / ks on mesh2d_nFaces, ALL faces, and
        # stops at startup on the binary smaxfile / sefffile / ksfile (2026-10-23)
        import xarray as xr

        from nj_sfincs import infiltration as inf

        with tempfile.TemporaryDirectory() as t:
            d, tif = _toy_dir(Path(t))
            meta = inf.write_cnb_inputs(d, 1.0, tif, 32618, "sfincs.nc")
            with xr.open_dataset(d / inf.CNB_NC) as nc:
                self.assertEqual(set(nc.data_vars), {"smax", "seff", "ks"})
                self.assertEqual(nc["smax"].dims, ("mesh2d_nFaces",))
                self.assertEqual(nc["smax"].dtype, np.float32)
                self.assertNotIn("_FillValue", nc["smax"].encoding)
                smax, ks = nc["smax"].values, nc["ks"].values
        # faces 0, 1, 3, 4 active (mask > 0); face 2 inactive -> 0
        np.testing.assert_allclose(smax, [0.0254, 0.0508, 0.0, 0.0, 0.0], rtol=1e-6)
        # face 0 -> pixel (row 0, col 0) = 1; face 1 -> (1, 1) = 500 -> cap 100;
        # face 3 -> (0, 2) = 3; face 4 off the raster -> 0
        np.testing.assert_allclose(ks, [3.6, 360.0, 0.0, 10.8, 0.0], rtol=1e-6)
        self.assertEqual(meta["active_points"], 4)
        self.assertEqual(meta["infiltrating_points"], 2)


class TestCnbInpKeys(unittest.TestCase):
    def test_cnb_replaces_cna_keys(self):
        from nj_sfincs import model, provenance

        inp = (
            "qtrfile              = sfincs.nc\n"
            "netamprfile          = sfincs_netampr.nc\n"
            "infiltration_file    = infiltration.nc\n"
            "infiltration_type    = cna\n"
            "scsfile              = x\n"
        )
        with tempfile.TemporaryDirectory() as t:
            d, tif = _toy_dir(Path(t))
            dom = SimpleNamespace(
                name="toy", ksat_dataset="ksat_toy", epsg=32618, infiltration=True
            )
            with (
                mock.patch.object(model._domain, "active", return_value=dom),
                mock.patch.object(provenance, "catalog_uri", return_value=str(tif)),
            ):
                out = model._infiltration_keys(inp, d, on=True, cnb_effective=1.5)
            keys = {
                ln.split("=")[0].strip(): ln.split("=")[1].strip()
                for ln in out.splitlines()
            }
            (d / "sfincs.inp").write_text(out)
            label = provenance.infiltration_label(d)
        for gone in ("scsfile", "smaxfile", "sefffile", "ksfile"):
            self.assertNotIn(gone, keys)
        self.assertEqual(keys["infiltration_file"], "sfincs_cnb.nc")
        self.assertEqual(keys["infiltration_type"], "cnb")
        self.assertEqual(keys["storecumprcp"], "1")
        self.assertEqual(label, "cnb:e1.5")

    def test_default_is_still_cna(self):
        from nj_sfincs import model

        inp = "qtrfile = sfincs.nc\nnetamprfile = sfincs_netampr.nc\n"
        with tempfile.TemporaryDirectory() as t:
            d, _ = _toy_dir(Path(t))
            out = model._infiltration_keys(inp, d, on=True)
        self.assertIn("infiltration_type    = cna", out)
        self.assertNotIn("sefffile", out)


if __name__ == "__main__":
    unittest.main()
