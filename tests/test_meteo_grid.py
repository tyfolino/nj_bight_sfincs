"""The gridded meteo files carry the coordinates the ENGINE reads correctly (2026-10-06).

SFINCS v2.3.3 reads the first x / y of ``netamuv`` / ``netamp`` / ``netampr`` as a cell
CORNER; hydromt writes CENTRES, so every point sampled wind, pressure and rain half a
cell W and N of itself (the toy probe measured x -12 516 m, y +12 518 m on ERA5;
logs/raritan_2026-10-06/wind_setup_toy/README.md). ``meteo_grid.engine_sample`` ports the
engine's reader + ``update_amuv_data`` to numpy; these tests pin that a file written by
``fix_meteo_grid_origin`` is sampled at the TRUE point, for either y direction.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import xarray as xr

from nj_sfincs import meteo_grid as mg
from nj_sfincs.config import ROOT

A, B, C = (
    1.3e-4,
    -7.0e-5,
    4.0,
)  # a field linear in x, y: bilinear interpolation is exact


def _field(x, y):
    return A * x + B * y + C


def _write(path: Path, xc, yc, var="eastward_wind", nt=3, fn=_field):
    X, Y = np.meshgrid(xc, yc)
    F = np.broadcast_to(fn(X, Y), (nt, *X.shape)).astype("f8")
    xr.Dataset(
        {var: (("time", "y", "x"), F)},
        coords={
            "time": np.datetime64("2012-10-28")
            + np.arange(nt) * np.timedelta64(1, "h"),
            "y": yc,
            "x": xc,
        },
    ).to_netcdf(path)


def _grid(descending=True):
    xc = 500_000.0 + 1000.0 * np.arange(8)
    yc = 4_400_000.0 + 1500.0 * np.arange(7)
    return xc, (yc[::-1] if descending else yc)


def _interior_points(xc, yc, n=500, seed=0):
    """Points the engine does not zero (``meteo_grid.engine_accepted_band``): its
    ``iy <= 1`` test rejects the whole cell next to the LAST file row."""
    b = mg.engine_accepted_band(*mg.engine_coords(xc, yc))
    rng = np.random.default_rng(seed)
    xq = rng.uniform(b["x_min"] + 1, b["x_max"] - 1, n)
    yq = rng.uniform(b["y_min"] + 1, b["y_max"] - 1, n)
    return xq, yq


def _read(path: Path, var="eastward_wind"):
    with xr.open_dataset(path) as ds:
        return (
            ds["x"].values,
            ds["y"].values,
            ds[var].isel(time=0).values,
            dict(ds.attrs),
        )


class TestEngineConvention(unittest.TestCase):
    def test_unfixed_file_is_sampled_half_a_cell_away(self):
        """Pins the bug the fix answers: a CENTRES file is sampled at x - dx/2,
        y - dy/2 (signed dy: descending y -> NORTH), as the probe measured."""
        for desc in (True, False):
            xc, yc = _grid(desc)
            X, Y = np.meshgrid(xc, yc)
            F = _field(X, Y)
            xq, yq = _interior_points(xc, yc)
            # keep a cell clear of every edge so the shifted stencil is still inside
            ok = (xq > xc.min() + 1000) & (xq < xc.max() - 1000)
            ok &= (yq > yc.min() + 3000) & (yq < yc.max() - 3000)
            got = mg.engine_sample(xq[ok], yq[ok], xc, yc, F)
            dx, dy = mg.signed_step(xc), mg.signed_step(yc)
            want = _field(xq[ok] - dx / 2, yq[ok] - dy / 2)
            np.testing.assert_allclose(got, want, atol=1e-6)

    def test_probe_shift_is_reproduced_on_the_era5_grid(self):
        """The v4 ERA5 grid (dx 25 032.28 m, descending y), in the engine's real*4:
        sampled at x - 12 516, y + 12 516 (probe: -12 516 / +12 518 m)."""
        d = 25032.282330060203
        xc = 413910.51614088734 + d * np.arange(11)
        yc = 4569566.971649104 - d * np.arange(14)
        X, Y = np.meshgrid(xc, yc)
        F = 1e-4 * (X - 500e3)
        G = 1e-4 * (Y - 4400e3)
        xq, yq = np.array([560e3]), np.array([4.47e6])
        sx = 500e3 + mg.engine_sample(xq, yq, xc, yc, F, f32=True)[0] / 1e-4 - xq[0]
        sy = 4400e3 + mg.engine_sample(xq, yq, xc, yc, G, f32=True)[0] / 1e-4 - yq[0]
        self.assertAlmostEqual(sx, -d / 2, delta=3.0)
        self.assertAlmostEqual(sy, +d / 2, delta=3.0)

    def test_fixed_file_is_sampled_at_the_true_point(self):
        for desc in (True, False):
            with self.subTest(descending_y=desc), tempfile.TemporaryDirectory() as td:
                d = Path(td)
                xc, yc = _grid(desc)
                _write(d / "sfincs_netamuv.nc", xc, yc)
                st = mg.fix_meteo_grid_origin(d)
                self.assertEqual([s["action"] for s in st], ["fixed"])
                xw, yw, F, _ = _read(d / "sfincs_netamuv.nc")
                # the rule: centre - signed step / 2
                np.testing.assert_allclose(xw, xc - 500.0)
                np.testing.assert_allclose(yw, yc + (750.0 if desc else -750.0))
                xq, yq = _interior_points(xc, yc)
                got = mg.engine_sample(xq, yq, xw, yw, F)
                np.testing.assert_allclose(got, _field(xq, yq), atol=1e-6)
                # and at the centres themselves a NON-linear field comes back exactly
                X, Y = np.meshgrid(xc, yc)
                G = np.sin(X / 1e3) * np.cos(Y / 2e3)
                b = mg.engine_accepted_band(xw, yw)
                inner = (X >= b["x_min"]) & (X < b["x_max"])
                inner &= (Y > b["y_min"]) & (Y < b["y_max"])
                got = mg.engine_sample(X[inner], Y[inner], xw, yw, G)
                np.testing.assert_allclose(got, G[inner], atol=1e-9)
                np.testing.assert_allclose(
                    mg.true_centres(d / "sfincs_netamuv.nc")[0], xc
                )
                np.testing.assert_allclose(
                    mg.true_centres(d / "sfincs_netamuv.nc")[1], yc
                )

    def test_descending_x_is_refused(self):
        with self.assertRaises(ValueError):
            mg.engine_coords(np.array([3.0, 2.0, 1.0]), np.array([0.0, 1.0]))


class TestFixFiles(unittest.TestCase):
    def _three(self, d: Path, desc=True):
        xc, yc = _grid(desc)
        _write(d / "sfincs_netamuv.nc", xc, yc)
        _write(d / "sfincs_netamp.nc", xc, yc, var="barometric_pressure")
        _write(d / "sfincs_netampr.nc", xc[:5] * 1.0, yc[:6], var="Precipitation")
        (d / "sfincs.inp").write_text(
            "netamuamvfile = sfincs_netamuv.nc\nnetampfile = sfincs_netamp.nc\n"
            "netamprfile = sfincs_netampr.nc\nepsg = 32618\n"
        )
        return xc, yc

    def test_idempotent_and_data_untouched(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            self._three(d)
            before = {f: _read(d / f, v)[2] for f, v in self._vars()}
            first = mg.fix_meteo_grid_origin(d)
            self.assertEqual({s["action"] for s in first}, {"fixed"})
            self.assertEqual(len(first), 3)
            coords1 = {f: _read(d / f, v)[:2] for f, v in self._vars()}
            second = mg.fix_meteo_grid_origin(d)
            self.assertEqual({s["action"] for s in second}, {"already"})
            for f, v in self._vars():
                x, y, F, attrs = _read(d / f, v)
                np.testing.assert_array_equal(x, coords1[f][0])
                np.testing.assert_array_equal(y, coords1[f][1])
                np.testing.assert_array_equal(F, before[f])
                self.assertIn(mg.ORIGIN_ATTR, attrs)
            self.assertEqual(
                sorted(p.name for p in d.iterdir() if p.name[0] == "."), []
            )

    @staticmethod
    def _vars():
        return (
            ("sfincs_netamuv.nc", "eastward_wind"),
            ("sfincs_netamp.nc", "barometric_pressure"),
            ("sfincs_netampr.nc", "Precipitation"),
        )

    def test_check_writes_nothing_and_flags(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            self._three(d)
            raw = {p.name: p.read_bytes() for p in d.iterdir()}
            st = mg.fix_meteo_grid_origin(d, check=True)
            self.assertEqual({s["action"] for s in st}, {"NEEDS FIX"})
            self.assertEqual({p.name: p.read_bytes() for p in d.iterdir()}, raw)

    def test_cli_check_exit_codes(self):
        script = ROOT / "scripts" / "fix_meteo_grid_origin.py"
        env = dict(os.environ, PYTHONPATH=str(ROOT))
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            self._three(d)
            r = subprocess.run(
                [sys.executable, str(script), "--check", str(d)],
                capture_output=True,
                check=False,
                text=True,
                env=env,
            )
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("NEEDS FIX", r.stdout)
            r = subprocess.run(
                [sys.executable, str(script), str(d)],
                capture_output=True,
                check=False,
                text=True,
                env=env,
            )
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            r = subprocess.run(
                [sys.executable, str(script), "--check", str(d)],
                capture_output=True,
                check=False,
                text=True,
                env=env,
            )
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertNotIn("NEEDS FIX", r.stdout)

    def test_never_writes_through_a_hard_link(self):
        with tempfile.TemporaryDirectory() as td:
            src, arm = Path(td) / "src", Path(td) / "arm"
            src.mkdir()
            arm.mkdir()
            xc, yc = _grid()
            _write(src / "sfincs_netamuv.nc", xc, yc)
            os.link(src / "sfincs_netamuv.nc", arm / "sfincs_netamuv.nc")
            raw = (src / "sfincs_netamuv.nc").read_bytes()
            mg.fix_meteo_grid_origin(arm)
            self.assertEqual((src / "sfincs_netamuv.nc").read_bytes(), raw)
            self.assertEqual((arm / "sfincs_netamuv.nc").stat().st_nlink, 1)
            self.assertTrue(mg.file_state(arm / "sfincs_netamuv.nc")["fixed"])
            self.assertFalse(mg.file_state(src / "sfincs_netamuv.nc")["fixed"])

    def test_lost_marker_is_refused_not_shifted_twice(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            xc, yc = _grid()
            _write(d / "sfincs_netamuv.nc", xc, yc)
            mg.fix_meteo_grid_origin(d)
            ds = xr.load_dataset(d / "sfincs_netamuv.nc")
            for v in ("x", "y"):
                ds[v].attrs = {}
            ds.attrs = {}
            (d / "sfincs_netamuv.nc").unlink()
            ds.to_netcdf(d / "sfincs_netamuv.nc")
            with self.assertRaises(RuntimeError):
                mg.fix_meteo_grid_origin(d, expect_fixed={"sfincs_netamuv.nc"})

    def test_finalize_fixes_after_it_writes(self):
        import inspect

        from nj_sfincs import model

        src = inspect.getsource(model.finalize)
        i_write = src.index("\n    sf.write()\n")
        self.assertLess(src.index("marked_in_memory(sf)"), i_write)
        self.assertGreater(src.index("fix_meteo_grid_origin(model_dir"), i_write)
        self.assertLess(
            src.index("fix_meteo_grid_origin(model_dir"), src.index("(d) rain")
        )


class TestHydromtRoundTrip(unittest.TestCase):
    """Arm staging reads the template's (fixed) files with hydromt and writes them again:
    the coordinates and the marker on x / y must survive (the GLOBAL attribute does
    not), so the post-write fix in ``finalize`` is a no-op, not a second shift."""

    def test_marker_survives_read_write(self):
        import gc

        import nj_sfincs.model  # noqa: F401 — pyproj before hydromt_sfincs
        from hydromt_sfincs import SfincsModel

        with tempfile.TemporaryDirectory() as td:
            d = Path(td) / "m"
            sf = SfincsModel(root=str(d), mode="w+", write_gis=False)
            sf.grid.create(
                x0=500000, y0=4400000, dx=1000, dy=1000, nmax=4, mmax=5,
                rotation=0.0, epsg=32618,
            )  # fmt: skip
            for k in ("tref", "tstart"):
                sf.config.set(k, "20121028 000000")
            sf.config.set("tstop", "20121028 020000")
            sf.write()
            del sf
            xc, yc = _grid()
            _write(d / "u.nc", xc, yc)
            ds = xr.load_dataset(d / "u.nc")
            (d / "u.nc").unlink()
            ds["northward_wind"] = -ds["eastward_wind"]
            ds.to_netcdf(d / "sfincs_netamuv.nc")
            _write(d / "sfincs_netamp.nc", xc, yc, var="barometric_pressure")
            with open(d / "sfincs.inp", "a") as fh:
                fh.write(
                    "netamuamvfile        = sfincs_netamuv.nc\n"
                    "netampfile           = sfincs_netamp.nc\n"
                )
            mg.fix_meteo_grid_origin(d)
            coords = {f: _read(d / f, v)[:2] for f, v in TestFixFiles._vars()[:2]}

            # the component read/write sf.read() / sf.write() call (the grid is
            # left out: this toy has no index file)
            sf = SfincsModel(root=str(d), mode="r+")
            for c in (sf.wind, sf.pressure):
                c.read()
                c.data.load()
            marked = mg.marked_in_memory(sf)
            xr.backends.file_manager.FILE_CACHE.clear()
            gc.collect()
            for c in (sf.wind, sf.pressure):
                c.write()
            del sf
            gc.collect()
            self.assertEqual(marked, {"sfincs_netamuv.nc", "sfincs_netamp.nc"})
            st = mg.fix_meteo_grid_origin(d, expect_fixed=marked)
            self.assertEqual({s["action"] for s in st}, {"already"})
            for f, v in TestFixFiles._vars()[:2]:
                x, y, _, _ = _read(d / f, v)
                np.testing.assert_array_equal(x, coords[f][0])
                np.testing.assert_array_equal(y, coords[f][1])


class TestEra5Bilinear(unittest.TestCase):
    """``write_era5_bilinear``: native lon/lat ERA5 -> a fine UTM grid by bilinear in
    lon/lat; the engine reading it returns the native bilinear field at the point."""

    def _native(self, scale=1.0):
        lon = np.arange(-75.5, -73.49, 0.25)
        lat = np.arange(41.0, 39.49, -0.25)  # descending, like ERA5
        t = np.datetime64("2012-10-28") + np.arange(3) * np.timedelta64(1, "h")
        LO, LA = np.meshgrid(lon, lat)
        u = 5.0 + 2.0 * (LO + 74.5) - 3.0 * (LA - 40.2)
        v = -2.0 + 1.0 * (LA - 40.2)
        p = 100000.0 + 300.0 * (LO + 74.5)
        f = lambda a: np.broadcast_to(a, (3, *a.shape)).astype("f4")  # noqa: E731
        return xr.Dataset(
            {
                "wind10_u": (("time", "y", "x"), f(u) * scale),
                "wind10_v": (("time", "y", "x"), f(v) * scale),
                "press_msl": (("time", "y", "x"), f(p)),
            },
            coords={"time": t, "y": lat, "x": lon},
        )

    def _old(self, d: Path, nat: xr.Dataset, scale=1.0):
        """A hydromt-like nearest copy on a 25 km UTM grid (only extent/times are used,
        plus the mean-speed sanity check)."""
        from pyproj import Transformer

        tr = Transformer.from_crs(32618, 4326, always_xy=True)
        xc = 470_000.0 + 25_000.0 * np.arange(6)
        yc = 4_540_000.0 - 25_000.0 * np.arange(6)
        X, Y = np.meshgrid(xc, yc)
        LO, LA = tr.transform(X, Y)
        near = nat.sel(x=xr.DataArray(LO), y=xr.DataArray(LA), method="nearest")
        ds = xr.Dataset(
            {
                "eastward_wind": (("time", "y", "x"), near["wind10_u"].values * scale),
                "northward_wind": (("time", "y", "x"), near["wind10_v"].values * scale),
            },
            coords={"time": nat.time.values, "y": yc, "x": xc},
        )
        ds.to_netcdf(d / "sfincs_netamuv.nc")
        dp = xr.Dataset(
            {"barometric_pressure": (("time", "y", "x"), near["press_msl"].values)},
            coords={"time": nat.time.values, "y": yc, "x": xc},
        )
        dp.to_netcdf(d / "sfincs_netamp.nc")
        (d / "sfincs.inp").write_text("epsg = 32618\n")

    def test_engine_reads_native_bilinear(self):
        from pyproj import Transformer

        nat = self._native()
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            self._old(d, nat)
            info = mg.write_era5_bilinear(d, nat, res_m=5000.0)
            self.assertEqual({s["action"] for s in info["states"]}, {"fixed"})
            xw, yw, U, attrs = _read(d / "sfincs_netamuv.nc", "eastward_wind")
            self.assertIn(mg.REGRID_ATTR, attrs)
            xc, yc = mg.centres_from_engine_coords(xw, yw)
            # whole multiples of res: exact in the engine's real*4, so no step drift
            for c in (xc, yc, xw, yw):
                np.testing.assert_array_equal(c.astype("f4").astype("f8"), c)
            np.testing.assert_array_equal(xc % 5000.0, 0.0)
            xq, yq = _interior_points(xc, yc, n=300, seed=1)
            lo, la = Transformer.from_crs(32618, 4326, always_xy=True).transform(xq, yq)
            want = (
                nat["wind10_u"]
                .isel(time=0)
                .interp(x=xr.DataArray(lo), y=xr.DataArray(la))
            )
            got = mg.engine_sample(xq, yq, xw, yw, U)
            # linear in lon/lat; the UTM map is near-affine over 5 km -> ~1e-4 m/s
            np.testing.assert_allclose(got, want.values, atol=2e-3)
            _, _, P, _ = _read(d / "sfincs_netamp.nc", "barometric_pressure")
            wantp = (
                nat["press_msl"]
                .isel(time=0)
                .interp(x=xr.DataArray(lo), y=xr.DataArray(la))
            )
            np.testing.assert_allclose(
                mg.engine_sample(xq, yq, xw, yw, P), wantp.values, atol=0.5
            )

    def test_refuses_a_scaled_wind(self):
        nat = self._native()
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            self._old(d, nat, scale=1.10)
            raw = (d / "sfincs_netamuv.nc").read_bytes()
            with self.assertRaises(ValueError):
                mg.write_era5_bilinear(d, nat)
            self.assertEqual((d / "sfincs_netamuv.nc").read_bytes(), raw)


if __name__ == "__main__":
    unittest.main()
