"""Wave boundary forcing from a regular lon/lat grid (GFS-Wave), and the CORA pin."""

from __future__ import annotations

import contextlib
import hashlib
import io
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np
import pandas as pd
import xarray as xr

from nj_sfincs import wave_grid as wg

#: Nodes each synthetic support point is placed next to (by construction its nearest).
_CORA_PICK = np.array([3, 17, 0, 29, 11, 22])

#: sha256 of ``_point_wave_bnd``'s float64 outputs on ``_cora_case``, recorded from the
#: code BEFORE the regular-grid path was added (2026-11-23). The CORA path must not move.
_CORA_SHA = "70129c65c716a4389f583967f76a886eed00824715b371a23a275fdf97f12114"


def _cora_case(td: Path):
    """A synthetic CORA-shaped (time, node) file padded a day before tref.

    Returns ``(path, pts_utm, ds)``; support point k sits ~150 m from node
    ``_CORA_PICK[k]``.
    """
    import pyproj

    rng = np.random.default_rng(20261123)
    nn = 30
    lon = np.linspace(-74.05, -73.70, nn) + rng.uniform(-0.01, 0.01, nn)
    lat = np.linspace(39.40, 40.30, nn)
    times = pd.date_range("2012-10-27 00:00", "2012-10-29 00:00", freq="1h")
    nt = len(times)
    ds = xr.Dataset(
        {
            "hs": (("time", "node"), rng.uniform(0.5, 7.0, (nt, nn)).astype("f4")),
            "tp": (("time", "node"), rng.uniform(5.0, 16.0, (nt, nn)).astype("f4")),
            "wd": (("time", "node"), rng.uniform(0.0, 360.0, (nt, nn)).astype("f4")),
        },
        coords={
            "time": times,
            "lon": ("node", lon),
            "lat": ("node", lat),
            "depth": ("node", rng.uniform(5.0, 40.0, nn).astype("f4")),
        },
    )
    path = td / "cora_synth.nc"
    ds.to_netcdf(path)
    tf = pyproj.Transformer.from_crs(4326, 32618, always_xy=True)
    x, y = tf.transform(lon[_CORA_PICK] + 0.0015, lat[_CORA_PICK] + 0.0007)
    return path, np.c_[x, y], ds


def _grid(nt=3, land=None):
    """A canonical (time, lat, lon) grid on 1/6° spacing; ``land`` = bool (lat, lon).

    Hs and Tp are LINEAR in lon/lat (bilinear interpolation is exact on them).
    """
    lon = -75.0 + np.arange(8) / 6.0
    lat = 38.5 + np.arange(7) / 6.0
    LON, LAT = np.meshgrid(lon, lat)
    hs = np.stack(
        [2.0 + 0.7 * (LON + 75) - 0.4 * (LAT - 38.5) + 0.1 * t for t in range(nt)]
    )
    tp = np.stack([8.0 + 2.0 * (LON + 75) + 1.5 * (LAT - 38.5) + t for t in range(nt)])
    wd = np.stack([np.full_like(LON, 120.0) + t for t in range(nt)])
    if land is not None:
        for a in (hs, tp, wd):
            a[:, land] = np.nan
    times = pd.date_range("2026-11-22 00:00", periods=nt, freq="1h")
    return xr.Dataset(
        {
            v: (("time", "lat", "lon"), a)
            for v, a in zip(("hs", "tp", "wd"), (hs, tp, wd))
        },
        coords={"time": times, "lat": lat, "lon": lon},
    )


class TestBilinear(unittest.TestCase):
    def test_exact_on_linear_field(self):
        ds = _grid()
        plon, plat = np.array([-74.71, -74.12, -73.9]), np.array([38.62, 39.3, 39.01])
        out, wts = wg.interp_points(ds, plon, plat)
        self.assertEqual({w.method for w in wts}, {"bilinear"})
        for t in range(3):
            np.testing.assert_allclose(
                out["hs"][t],
                2.0 + 0.7 * (plon + 75) - 0.4 * (plat - 38.5) + 0.1 * t,
                rtol=0,
                atol=1e-12,
            )
            np.testing.assert_allclose(
                out["tp"][t],
                8.0 + 2.0 * (plon + 75) + 1.5 * (plat - 38.5) + t,
                rtol=0,
                atol=1e-12,
            )
            np.testing.assert_allclose(out["wd"][t], 120.0 + t, atol=1e-9)

    def test_0_360_points_and_descending_grid(self):
        ds = _grid()
        flipped = (
            ds.isel(lat=slice(None, None, -1))
            .assign_coords(lon=ds.lon.values + 360.0)
            .rename(lon="longitude", lat="latitude")
        )
        a, _ = wg.interp_points(ds, [-74.5], [39.0])
        b, _ = wg.interp_points(wg.canonical(flipped), [285.5], [39.0])
        np.testing.assert_allclose(a["hs"], b["hs"], atol=1e-12)

    def test_wet_only_renormalisation(self):
        land = np.zeros((7, 8), bool)
        land[3, 3] = True  # one corner of the cell around the point is land
        ds = _grid(land=land)
        lon, lat = ds.lon.values, ds.lat.values
        plon = lon[2] + 0.3 * (lon[3] - lon[2])
        plat = lat[2] + 0.6 * (lat[3] - lat[2])
        out, (pw,) = wg.interp_points(ds, [plon], [plat])
        self.assertEqual(pw.method, "partial")
        self.assertEqual(len(pw.w), 3)
        fx, fy = 0.3, 0.6
        w = np.array([(1 - fx) * (1 - fy), fx * (1 - fy), (1 - fx) * fy])
        w /= w.sum()
        hs0 = ds.hs.values[0]
        expect = w @ np.array([hs0[2, 2], hs0[2, 3], hs0[3, 2]])
        self.assertAlmostEqual(out["hs"][0, 0], expect, places=12)
        self.assertAlmostEqual(pw.w.sum(), 1.0, places=14)


class TestFallback(unittest.TestCase):
    def test_idw_when_all_corners_land(self):
        land = np.zeros((7, 8), bool)
        land[:, :4] = True  # the western half is land
        ds = _grid(land=land)
        lon, lat = ds.lon.values, ds.lat.values
        plon, plat = 0.5 * (lon[1] + lon[2]), 0.5 * (lat[3] + lat[4])
        out, (pw,) = wg.interp_points(ds, [plon], [plat], max_dist_m=60_000)
        self.assertEqual(pw.method, "idw")
        self.assertTrue((pw.ilon >= 4).all())
        self.assertLessEqual(pw.dist_m, 60_000)
        d = wg._haversine(plon, plat, lon[pw.ilon], lat[pw.ilat])
        w = 1 / d**2
        w /= w.sum()
        expect = w @ ds.hs.values[0][pw.ilat, pw.ilon]
        self.assertAlmostEqual(out["hs"][0, 0], expect, places=12)

    def test_raise_beyond_max_distance_names_point(self):
        land = np.zeros((7, 8), bool)
        land[:, :6] = True
        ds = _grid(land=land)
        with self.assertRaisesRegex(ValueError, r"support point 1 \(lon -74\.90000"):
            wg.interp_points(ds, [-73.9, -74.9], [39.0, 39.0])

    def test_off_grid_point_uses_idw(self):
        ds = _grid()
        _, (pw,) = wg.interp_points(ds, [-75.05], [39.0])
        self.assertEqual(pw.method, "idw")


class TestDirection(unittest.TestCase):
    def test_wrap_350_and_10_average_to_0(self):
        ds = _grid(nt=1)
        wd = ds.wd.values.copy()
        wd[0, :, 0::2] = 350.0
        wd[0, :, 1::2] = 10.0
        ds["wd"] = (("time", "lat", "lon"), wd)
        ds["hs"] = xr.full_like(ds.hs, 2.0)  # equal Hs: the two weightings agree
        lon = ds.lon.values
        for weighting in ("plain", "hs"):
            out, _ = wg.interp_points(
                ds, [0.5 * (lon[2] + lon[3])], [39.0], dir_weighting=weighting
            )
            got = out["wd"][0, 0]
            self.assertLess(min(got, 360.0 - got), 1e-9, (weighting, got))
            self.assertTrue(0.0 <= got < 360.0)

    def test_hs_weighting_pulls_toward_energetic_corner(self):
        ds = _grid(nt=1)
        wd = np.full_like(ds.wd.values, 90.0)
        hs = np.full_like(ds.hs.values, 1.0)
        wd[0, :, 3], hs[0, :, 3] = 180.0, 4.0
        ds["wd"] = (("time", "lat", "lon"), wd)
        ds["hs"] = (("time", "lat", "lon"), hs)
        lon = ds.lon.values
        x = [0.5 * (lon[2] + lon[3])]
        plain, _ = wg.interp_points(ds, x, [39.0], dir_weighting="plain")
        hsw, _ = wg.interp_points(ds, x, [39.0], dir_weighting="hs")
        self.assertAlmostEqual(plain["wd"][0, 0], 135.0, places=9)
        self.assertGreater(hsw["wd"][0, 0], 160.0)


class TestCoraPathUnchanged(unittest.TestCase):
    def _run(self):
        from nj_sfincs import model
        from nj_sfincs.config import WaveConfig

        with tempfile.TemporaryDirectory() as td:
            path, pts, ds = _cora_case(Path(td))
            w = WaveConfig(use_waves=True, wave_point_dataset=path)
            base = SimpleNamespace(tref=datetime(2012, 10, 28))
            with (
                mock.patch.object(
                    model._domain, "active", return_value=SimpleNamespace(epsg=32618)
                ),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                out = model._point_wave_bnd(w, base, None, pts)
            return out, ds.load()

    def test_byte_identical(self):
        out, _ = self._run()
        h = hashlib.sha256()
        for a in out:
            h.update(np.ascontiguousarray(np.asarray(a, "f8")).tobytes())
        self.assertEqual(h.hexdigest(), _CORA_SHA)

    def test_nearest_node_and_tref_clock(self):
        (t, hs, tp, wd, dspread), ds = self._run()
        keep = pd.to_datetime(ds.time.values) >= pd.Timestamp("2012-10-28")
        self.assertEqual(t[0], 0.0)
        np.testing.assert_array_equal(np.diff(t), 3600.0)
        for v, got in (("hs", hs), ("tp", tp), ("wd", wd)):
            np.testing.assert_array_equal(
                got, ds[v].values.astype(float)[keep][:, _CORA_PICK]
            )
        np.testing.assert_array_equal(dspread, 30.0)


class TestGridPathInModel(unittest.TestCase):
    def test_grid_wave_bnd_clock_and_values(self):
        import pyproj

        from nj_sfincs import model
        from nj_sfincs.config import WaveConfig

        ds = _grid(nt=4)
        plon, plat = np.array([-74.4, -74.1]), np.array([39.1, 39.4])
        tf = pyproj.Transformer.from_crs(4326, 32618, always_xy=True)
        pts = np.c_[tf.transform(plon, plat)]
        base = SimpleNamespace(
            tref=datetime(2026, 11, 22, 1), tstop=datetime(2026, 11, 22, 3)
        )
        w = WaveConfig(use_waves=True, wave_grid_dataset=Path("unused.nc"))
        with (
            mock.patch.object(
                model._domain, "active", return_value=SimpleNamespace(epsg=32618)
            ),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            t, hs, tp, wd, dsp = model._grid_wave_bnd(w, base, pts, ds=ds)
        np.testing.assert_array_equal(t, [0.0, 3600.0, 7200.0])
        self.assertEqual(hs.shape, (3, 2))
        np.testing.assert_allclose(
            hs[0], 2.0 + 0.7 * (plon + 75) - 0.4 * (plat - 38.5) + 0.1, atol=1e-6
        )
        np.testing.assert_array_equal(dsp, 30.0)


class TestAudit1123(unittest.TestCase):
    """The 2026-11-23 audit fixes: Hs-only wet mask, distance cap on the bilinear
    branch, coverage refusal, repr."""

    def _run(self, ds, base):
        import pyproj

        from nj_sfincs import model
        from nj_sfincs.config import WaveConfig

        plon, plat = np.array([-74.4]), np.array([39.1])
        tf = pyproj.Transformer.from_crs(4326, 32618, always_xy=True)
        pts = np.c_[tf.transform(plon, plat)]
        w = WaveConfig(use_waves=True, wave_grid_dataset=Path("unused.nc"))
        with (
            mock.patch.object(
                model._domain, "active", return_value=SimpleNamespace(epsg=32618)
            ),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            return model._grid_wave_bnd(w, base, pts, ds=ds)

    def test_calm_nan_direction_does_not_make_land(self):
        ds = _grid()
        ds["wd"][1, 3, 3] = np.nan  # undefined direction at ONE sea cell, one time
        ds["tp"][1, 3, 3] = np.nan
        self.assertTrue(wg.wet_mask(ds)[3, 3])
        lon, lat = float(ds.lon[3]) + 0.05, float(ds.lat[3]) + 0.05
        out, wts = wg.interp_points(ds, [lon], [lat])
        self.assertEqual(wts[0].method, "bilinear")
        self.assertTrue(np.isfinite(out["tp"]).all() and np.isfinite(out["wd"]).all())
        np.testing.assert_allclose(out["wd"][1, 0], 121.0, atol=1e-9)

    def test_distance_cap_applies_to_bilinear_corners(self):
        ds = _grid()
        lon, lat = float(ds.lon[3]) + 0.08, float(ds.lat[3]) + 0.08
        with self.assertRaises(ValueError):
            wg.interp_points(ds, [lon], [lat], max_dist_m=1_000.0)

    def test_refuses_short_coverage(self):
        base = SimpleNamespace(
            tref=datetime(2026, 11, 22, 0), tstop=datetime(2026, 11, 22, 5)
        )
        with self.assertRaisesRegex(RuntimeError, "not the run window"):
            self._run(_grid(nt=4), base)

    def test_refuses_missing_forecast_hour(self):
        ds = _grid(nt=6).isel(time=[0, 1, 2, 4, 5])
        base = SimpleNamespace(
            tref=datetime(2026, 11, 22, 0), tstop=datetime(2026, 11, 22, 5)
        )
        with self.assertRaisesRegex(RuntimeError, "gap"):
            self._run(ds, base)

    def test_dataset_path_not_in_repr(self):
        from nj_sfincs.config import WaveConfig

        self.assertNotIn("wave_grid_dataset", repr(WaveConfig()))


if __name__ == "__main__":
    unittest.main()
