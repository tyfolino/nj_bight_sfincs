"""NACCS -> ERA5 blended meteo forcing (``nj_sfincs.meteo_blend``, 2026-10-06).

Pins: the triangulation reproduces a field linear in x, y exactly and leaves gaps
(long or land triangles) uncovered; the taper weight is 1 / ½ / 0 at 0 / L/2 / L; the
blend is exactly NACCS inside the covered zone and exactly ERA5 beyond the taper; the CSV
reader takes columns by NAME, the storm by NAME, and checks the units row; and a written
pair of files carries the engine corner convention + marker, so ``meteo_grid`` sees it
as already fixed and the engine port returns the intended field at the TRUE points.
"""

from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np
import xarray as xr

from nj_sfincs import meteo_blend as mb
from nj_sfincs import meteo_grid as mg

A, B, C = 2.0e-4, -1.5e-4, 3.0


def _lin(x, y):
    return A * x + B * y + C


def _scatter(n=300, seed=1, x0=500_000.0, y0=4_400_000.0, size=20_000.0):
    rng = np.random.default_rng(seed)
    x = x0 + rng.uniform(0, size, n)
    y = y0 + rng.uniform(0, size, n)
    # the four corners so the hull is the square
    x = np.r_[x, x0, x0 + size, x0, x0 + size]
    y = np.r_[y, y0, y0, y0 + size, y0 + size]
    return x, y


class TestTriangulation(unittest.TestCase):
    def test_linear_field_is_reproduced_exactly(self):
        x, y = _scatter()
        tri, keep = mb.triangulate(x, y, 1e9)
        self.assertTrue(keep.all())
        rng = np.random.default_rng(2)
        xq = 500_000 + rng.uniform(100, 19_900, 400)
        yq = 4_400_000 + rng.uniform(100, 19_900, 400)
        W, cov = mb.interp_weights(tri, keep, xq, yq)
        self.assertTrue(cov.all())
        np.testing.assert_allclose(W @ _lin(x, y), _lin(xq, yq), rtol=0, atol=1e-9)
        # weights are a partition of unity
        np.testing.assert_allclose(np.asarray(W.sum(axis=1)).ravel(), 1.0, atol=1e-12)

    def test_long_triangles_leave_the_gap_uncovered(self):
        xa, ya = _scatter(150, 1, x0=500_000, size=5_000)
        xb, yb = _scatter(150, 2, x0=520_000, size=5_000)
        x, y = np.r_[xa, xb], np.r_[ya, yb]
        tri, keep = mb.triangulate(x, y, 3_000.0)
        self.assertFalse(keep.all())
        W, cov = mb.interp_weights(
            tri, keep, [502_500, 512_500, 522_500], [4_402_500] * 3
        )
        self.assertEqual(cov.tolist(), [True, False, True])
        self.assertEqual(W[1].nnz, 0)

    def test_land_test_drops_long_land_triangles_only(self):
        # two water clusters 8 km apart across a land strip; short triangles inside each
        # cluster sit over cells that are ALSO marked land (a narrow channel) and stay
        xa, ya = _scatter(120, 1, x0=500_000, size=4_000)
        xb, yb = _scatter(120, 2, x0=512_000, size=4_000)
        x, y = np.r_[xa, xb], np.r_[ya, yb]
        xc = np.arange(498_000, 518_001, 1000.0)
        yc = np.arange(4_406_000, 4_397_999, -1000.0)
        X, Y = np.meshgrid(xc, yc)
        land = (X > 504_500) & (X < 511_500)  # the strip
        land |= (X > 501_000) & (
            X < 502_000
        )  # "land" inside cluster a (a channel bank)
        tri, keep, n_long, n_land = mb.select_triangles(
            x, y, X, Y, 20_000.0, land, 0.5, 5_000.0
        )
        self.assertEqual(n_long, 0)
        self.assertGreater(n_land, 0)
        _, cov = mb.interp_weights(tri, keep, X, Y)
        cov = cov.reshape(X.shape)
        self.assertFalse(cov[land & (X > 504_500)].any(), "the land gap was bridged")
        self.assertTrue(
            cov[
                (X > 501_000) & (X < 502_000) & (Y > 4_400_500) & (Y < 4_403_500)
            ].all(),
            "a short triangle was dropped",
        )
        # without the land test the gap is bridged
        tri2, keep2, _, n2 = mb.select_triangles(x, y, X, Y, 20_000.0, None)
        self.assertEqual(n2, 0)
        _, cov2 = mb.interp_weights(tri2, keep2, X, Y)
        self.assertTrue(
            cov2.reshape(X.shape)[
                land & (X > 504_500) & (Y > 4_400_500) & (Y < 4_403_500)
            ].any()
        )


class TestDeadWind(unittest.TestCase):
    def test_all_zero_series_is_dead(self):
        t = np.arange(3).astype("datetime64[h]").astype("datetime64[m]")
        u = np.array([[0.0, 0.0, 0.0], [0.0, 1.0, 0.0], [3.0, 2.0, 1.0]])
        pts = mb.SavePoints(
            np.arange(3),
            np.zeros(3),
            np.zeros(3),
            np.ones(3),
            t,
            u,
            0 * u,
            1000 + 0 * u,
        )
        self.assertEqual(mb.dead_wind(pts).tolist(), [True, False, False])


class TestTaperAndBlend(unittest.TestCase):
    def test_taper_weight(self):
        w = mb.taper_weight([0.0, 5_000.0, 10_000.0, 25_000.0], 10_000.0)
        np.testing.assert_allclose(w, [1.0, 0.5, 0.0, 0.0], atol=1e-12)
        d = np.linspace(0, 12_000, 50)
        self.assertTrue(np.all(np.diff(mb.taper_weight(d, 10_000.0)) <= 0))
        np.testing.assert_array_equal(mb.taper_weight([0.0, 1.0], 0.0), [1.0, 0.0])

    def test_coverage_distance(self):
        cov = np.zeros((5, 7), bool)
        cov[2, 1] = True
        dist, ri, ci = mb.coverage_distance(cov, 1000.0, -1000.0)
        self.assertEqual(dist[2, 1], 0.0)
        self.assertAlmostEqual(dist[2, 6], 5000.0)
        self.assertAlmostEqual(dist[0, 1], 2000.0)
        self.assertTrue((ri == 2).all() and (ci == 1).all())
        with self.assertRaises(ValueError):
            mb.coverage_distance(np.zeros((3, 3), bool), 1000.0)

    def test_harmonic_extension(self):
        ny, nx = 30, 40
        cov = np.zeros((ny, nx), bool)
        cov[5:12, 3:15] = True
        cov[20:26, 25:35] = True
        ext = mb.HarmonicExtension(cov)
        # a constant is extended exactly
        f = np.where(cov, 2.5, np.nan)
        np.testing.assert_allclose(ext(f[None])[0], 2.5, atol=1e-12)
        # values on the zone untouched, the rest within [min, max] (maximum principle)
        # and harmonic (each free cell = the mean of its neighbours)
        rng = np.random.default_rng(5)
        g = np.where(cov, rng.normal(0, 3, cov.shape), np.nan)
        out = ext(np.stack([g, 2 * g]))
        np.testing.assert_array_equal(out[0][cov], g[cov])
        np.testing.assert_allclose(out[1], 2 * out[0], atol=1e-10)
        self.assertTrue(out[0].min() >= g[cov].min() - 1e-9)
        self.assertTrue(out[0].max() <= g[cov].max() + 1e-9)
        o = out[0]
        j, i = 16, 20  # an interior free cell
        self.assertAlmostEqual(
            o[j, i],
            (o[j - 1, i] + o[j + 1, i] + o[j, i - 1] + o[j, i + 1]) / 4,
            places=9,
        )
        with self.assertRaises(ValueError):
            mb.HarmonicExtension(np.zeros((3, 3), bool))

    def test_blend_is_naccs_inside_and_era5_beyond(self):
        ny, nx, nt = 6, 40, 2
        cov = np.zeros((ny, nx), bool)
        cov[:, :10] = True
        dist, _, _ = mb.coverage_distance(cov, 1000.0)
        w = mb.taper_weight(dist, 15_000.0)
        rng = np.random.default_rng(0)
        era5 = rng.normal(10, 2, (nt, ny, nx))
        naccs = np.full((nt, ny, nx), np.nan)
        naccs[:, cov] = rng.normal(15, 2, (nt, cov.sum()))
        out = mb.blend(naccs, era5, w, mb.HarmonicExtension(cov))
        np.testing.assert_array_equal(out[:, cov], naccs[:, cov])
        far = dist >= 15_000
        self.assertTrue(far.any())
        np.testing.assert_array_equal(out[:, far], era5[:, far])
        # continuous across the zone edge: the first cell outside differs from the edge
        # cell by no more than the ERA5 change plus the anomaly's change along the edge
        anom = naccs[:, :, 9] - era5[:, :, 9]
        step = np.abs(out[:, :, 10] - out[:, :, 9])
        bound = np.abs(era5[:, :, 10] - era5[:, :, 9]) + np.ptp(anom, axis=1)[:, None]
        self.assertTrue(np.all(step <= bound + 1e-9))


def _csv(rows, order="repack", units_p="hPa"):
    cols_repack = [
        "Save Point ID", "Save Point Latitude", "Save Point Longitude",
        "Save Point Depth", "Storm Name", "Storm ID", "Storm Type", "yyyymmddHHMM",
        "Atmospheric Pressure", "Water Elevation", "X Depth Averaged Velocity",
        "X Wind Velocity", "Y Depth Averaged Velocity", "Y Wind Velocity",
    ]  # fmt: skip
    units = {"yyyymmddHHMM": "yyyymmddHHMM", "Atmospheric Pressure": units_p,
             "Water Elevation": "m", "X Depth Averaged Velocity": "m/s",
             "X Wind Velocity": "m/s", "Y Depth Averaged Velocity": "m/s",
             "Y Wind Velocity": "m/s"}  # fmt: skip
    cols = cols_repack if order == "repack" else cols_repack[::-1]
    lines = [
        ",".join(f'"{c}"' for c in cols),
        ",".join('""' for _ in cols),
        ",".join(f'"{units.get(c, "")}"' for c in cols),
    ]
    for r in rows:
        lines.append(",".join(str(r[c]) for c in cols))
    return "\r\n".join(lines) + "\x00\x00"


def _rows(sp, lat, lon, depth, t0="201210272300", n=30, storm="Sandy", u0=5.0):
    out = []
    t = np.datetime64(f"{t0[:4]}-{t0[4:6]}-{t0[6:8]}T{t0[8:10]}:{t0[10:12]}", "m")
    for k in range(n):
        tt = (t + np.timedelta64(15 * k, "m")).astype(object)
        out.append({
            "Save Point ID": sp, "Save Point Latitude": lat, "Save Point Longitude": lon,
            "Save Point Depth": depth, "Storm Name": f'"{storm}"', "Storm ID": "001",
            "Storm Type": '"Tropical_Historical"', "yyyymmddHHMM": tt.strftime("%Y%m%d%H%M"),
            "Atmospheric Pressure": 1000.0 - k, "Water Elevation": -99999,
            "X Depth Averaged Velocity": 0.1, "X Wind Velocity": u0 + k,
            "Y Depth Averaged Velocity": 0.1, "Y Wind Velocity": -2.0,
        })  # fmt: skip
    return out


class TestReading(unittest.TestCase):
    def test_parse_by_name_and_storm(self):
        rows = _rows(3489, 40.5, -74.3, 2.2) + _rows(
            3489, 40.5, -74.3, 2.2, storm="Irene", u0=99.0
        )
        rows[3]["X Wind Velocity"] = -99999
        for order in ("repack", "reversed"):
            d = mb.parse_naccs_csv(_csv(rows, order))
            self.assertEqual(d["sp"], 3489)
            self.assertEqual(d["t"].size, 30)
            self.assertEqual(d["u"][0], 5.0)
            self.assertTrue(np.isnan(d["u"][3]) and np.isnan(d["v"][3]))
            self.assertEqual(d["p_hpa"][2], 998.0)
        self.assertIsNone(mb.parse_naccs_csv(_csv(rows), storm="Gloria"))
        with self.assertRaises(ValueError):
            mb.parse_naccs_csv(_csv(rows, units_p="Pa"))

    def test_load_zip_and_extra_dir(self):
        times = np.arange(
            np.datetime64("2012-10-28T00:00"),
            np.datetime64("2012-10-28T05:01"),
            np.timedelta64(30, "m"),
        )
        with tempfile.TemporaryDirectory() as tdn:
            td = Path(tdn)
            z = td / "naccs.zip"
            with zipfile.ZipFile(z, "w") as zf:
                for sp in (1, 2):
                    zf.writestr(
                        f"CSV/CHS-NA_Val_SimB1HT_Post0_SP{sp:05d}_ADCIRC01_Timeseries.csv",
                        _csv(_rows(sp, 40.0 + sp / 100, -74.0, 3.0)),
                    )
                zf.writestr(
                    "CSV/CHS-NA_Val_SimB1HT_Post0_SP00001_ADCIRC01_Peaks.csv", "x"
                )
            extra = td / "extra"
            extra.mkdir()
            # SP 2 again (must NOT override) + a new SP 7 + one too short for the window
            (
                extra / "CHS-NA_Val_SimB1HT_Post0_SP00002_ADCIRC01_Timeseries.csv"
            ).write_text(_csv(_rows(2, 41.0, -73.0, 3.0, u0=50.0)))
            (
                extra / "CHS-NA_Val_SimB1HT_Post0_SP00007_ADCIRC01_Timeseries.csv"
            ).write_text(_csv(_rows(7, 40.2, -73.5, 20.0)))
            (
                extra / "CHS-NA_Val_SimB1HT_Post0_SP00009_ADCIRC01_Timeseries.csv"
            ).write_text(_csv(_rows(9, 40.2, -73.5, 20.0, n=5)))
            pts = mb.load_save_points([z, extra], times, log=lambda *a: None)
        self.assertEqual(sorted(pts.sp.tolist()), [1, 2, 7])
        j = int(np.flatnonzero(pts.sp == 2)[0])
        self.assertAlmostEqual(pts.lat[j], 40.02)  # the archive's, not the extra's
        # 15-min series (u0 + k at 23:00 + 15k min) -> 00:00 is k = 4
        np.testing.assert_allclose(pts.u[j, :3], [9.0, 11.0, 13.0])
        self.assertEqual(pts.u.shape, (3, times.size))


def _era5_ds(times, fn_u, fn_v, fn_p):
    lon = np.arange(-76.0, -71.99, 0.25)
    lat = np.arange(42.0, 36.99, -0.25)
    LO, LA = np.meshgrid(lon, lat)
    nt = len(times)
    return xr.Dataset(
        {
            "wind10_u": (("time", "y", "x"), np.broadcast_to(fn_u(LO, LA), (nt, *LO.shape)).astype("f4")),
            "wind10_v": (("time", "y", "x"), np.broadcast_to(fn_v(LO, LA), (nt, *LO.shape)).astype("f4")),
            "press_msl": (("time", "y", "x"), np.broadcast_to(fn_p(LO, LA), (nt, *LO.shape)).astype("f4")),
        },
        coords={"time": times, "y": lat, "x": lon},
    )  # fmt: skip


class TestGridEra5AndWrite(unittest.TestCase):
    def test_target_grid(self):
        x, y = mb.target_grid(
            437_796.6, 601_830.2, 4_286_233.8, 4_533_566.9, 1000.0, 0.0
        )
        self.assertTrue(np.all(np.diff(x) == 1000.0) and np.all(np.diff(y) == -1000.0))
        self.assertTrue(np.all(x % 1000 == 0) and np.all(y % 1000 == 0))
        self.assertLessEqual(x[0], 437_796.6 - 2000)
        self.assertGreaterEqual(x[-1], 601_830.2 + 2000)
        self.assertGreaterEqual(y[0], 4_533_566.9 + 2000)
        self.assertLessEqual(y[-1], 4_286_233.8 - 2000)

    def test_era5_bilinear_linear_in_lonlat_and_time(self):
        t = np.arange(
            np.datetime64("2012-10-28T00"),
            np.datetime64("2012-10-28T04"),
            np.timedelta64(1, "h"),
        ).astype("datetime64[ns]")
        ds = _era5_ds(
            t,
            lambda lo, la: 3 * lo + la,
            lambda lo, la: -lo,
            lambda lo, la: 1e5 + 0 * lo,
        )
        ds["wind10_u"] = ds["wind10_u"] + xr.DataArray(np.arange(4.0), dims="time")
        lon = np.array([[-74.13, -73.9]])
        lat = np.array([[39.61, 40.2]])
        tq = np.array(["2012-10-28T00:30", "2012-10-28T02:00"], dtype="datetime64[m]")
        u, v, p = mb.era5_bilinear(ds, lon, lat, tq)
        np.testing.assert_allclose(
            u[:, 0], 3 * lon[0] + lat[0] + np.array([[0.5], [2.0]]), atol=2e-4
        )
        np.testing.assert_allclose(v[0, 0], -lon[0], atol=2e-5)
        with self.assertRaises(ValueError):
            mb.era5_bilinear(ds, np.array([[-80.0]]), np.array([[40.0]]), tq)

    def test_written_files_carry_the_engine_convention(self):
        xc = np.arange(500_000.0, 510_001.0, 1000.0)
        yc = np.arange(4_406_000.0, 4_399_999.0, -1000.0)
        X, Y = np.meshgrid(xc, yc)
        times = np.arange(
            np.datetime64("2012-10-28T00:00"),
            np.datetime64("2012-10-28T01:01"),
            np.timedelta64(30, "m"),
        )
        nt = times.size
        u = np.broadcast_to(_lin(X, Y), (nt, *X.shape))
        v = -u
        p = 1e5 + 0.01 * np.broadcast_to(X - Y, (nt, *X.shape))
        with tempfile.TemporaryDirectory() as td:
            states = mb.write_meteo_files(td, xc, yc, times, u, v, p, 32618, "test")
            self.assertEqual([s["action"] for s in states], ["fixed", "fixed"])
            again = mg.fix_meteo_grid_origin(
                Path(td), check=True, files=("sfincs_netamuv.nc", "sfincs_netamp.nc")
            )
            self.assertEqual([s["action"] for s in again], ["already", "already"])
            with xr.open_dataset(Path(td) / "sfincs_netamuv.nc") as ds:
                self.assertEqual(ds["eastward_wind"].dims, ("time", "y", "x"))
                self.assertIn("northward_wind", ds)
                self.assertEqual(ds["eastward_wind"].dtype, np.float32)
                self.assertEqual(
                    ds["time"].encoding["units"], "minutes since 2012-10-28"
                )
                np.testing.assert_allclose(
                    ds["time"].encoding.get("dtype", np.float64)
                    and ds["time"].values.astype("datetime64[m]").astype(int)
                    - times.astype(int),
                    0,
                )
                xt, yt = mg.true_centres(ds)
                xw, yw = ds["x"].values, ds["y"].values
                U = ds["eastward_wind"].values[1]
                self.assertIn(mg.ORIGIN_ATTR, ds["x"].attrs)
                self.assertIn(mb.BLEND_ATTR, ds["x"].attrs)
            np.testing.assert_array_equal(xt, xc)
            np.testing.assert_array_equal(yt, yc)
            with xr.open_dataset(Path(td) / "sfincs_netamp.nc") as ds:
                self.assertIn("barometric_pressure", ds)
                self.assertEqual(ds["barometric_pressure"].attrs["units"], "Pa")
                P = ds["barometric_pressure"].values[0]
        b = mg.engine_accepted_band(xw, yw)
        rng = np.random.default_rng(3)
        xq = rng.uniform(b["x_min"] + 1, b["x_max"] - 1, 300)
        yq = rng.uniform(b["y_min"] + 1, b["y_max"] - 1, 300)
        got = mg.engine_sample(xq, yq, xw, yw, U)
        np.testing.assert_allclose(got, _lin(xq, yq), atol=2e-5)  # float32 storage
        gp = mg.engine_sample(xq, yq, xw, yw, P)
        np.testing.assert_allclose(gp, 1e5 + 0.01 * (xq - yq), atol=0.02)


class TestBuildBlend(unittest.TestCase):
    def test_end_to_end_synthetic(self):
        from pyproj import Transformer

        to_ll = Transformer.from_crs(32618, 4326, always_xy=True)
        x, y = _scatter(250, 4, x0=540_000, y0=4_400_000, size=15_000)
        lon, lat = to_ll.transform(x, y)
        times = np.arange(
            np.datetime64("2012-10-28T00:00"),
            np.datetime64("2012-10-28T01:01"),
            np.timedelta64(30, "m"),
        )
        nt = times.size
        f = np.broadcast_to(_lin(x, y)[:, None], (x.size, nt)).copy()
        pts = mb.SavePoints(
            np.arange(x.size),
            np.asarray(lon),
            np.asarray(lat),
            np.full(x.size, 3.0),
            times,
            f,
            -f,
            1000.0 + 0 * f,
        )
        era = _era5_ds(
            np.arange(
                np.datetime64("2012-10-27T23"),
                np.datetime64("2012-10-28T03"),
                np.timedelta64(1, "h"),
            ).astype("datetime64[ns]"),
            lambda lo, la: 7.0 + 0 * lo,
            lambda lo, la: 1.0 + 0 * lo,
            lambda lo, la: 1.01e5 + 0 * lo,
        )
        xc, yc = mb.target_grid(520_000, 575_000, 4_390_000, 4_425_000, 1000.0)
        res = mb.build_blend(pts, era, xc, yc, 32618, 5_000.0, 10_000.0)
        X, Y = np.meshgrid(xc, yc)
        cov = res["covered"]
        self.assertTrue(cov.any() and (~cov).any())
        np.testing.assert_allclose(
            res["u"][:, cov],
            np.broadcast_to(_lin(X, Y)[cov], (nt, cov.sum())),
            atol=1e-9,
        )
        np.testing.assert_allclose(res["p"][:, cov], 1e5, atol=1e-6)  # hPa -> Pa
        far = res["dist"] >= 10_000
        np.testing.assert_allclose(res["u"][:, far], 7.0, atol=1e-4)
        np.testing.assert_allclose(res["p"][:, far], 1.01e5, atol=0.5)
        mid = (res["w"] > 0.2) & (res["w"] < 0.8)
        self.assertTrue(mid.any())


if __name__ == "__main__":
    unittest.main()
