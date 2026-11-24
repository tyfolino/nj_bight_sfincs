"""nj_sfincs.tide_surface: de-noised tidal high water (2026-11-23).

A small synthetic run: a 20 x 20 patch of open-water faces carrying a smooth tide (high water 1.0 m), and
four special faces:

* NOISY  a sliver bank face that rings: zero-mean oscillation of 0.5 m on the tide, so every 3 h max
         catches a crest (mhh ~1.5 m) while its snapshots average to the channel -> must be REPLACED;
* RING   its 8 neighbours, bank faces ringing at 0.2 m (a ringing CLUSTER) -> all REPLACED;
* HELD   water held at 1.30 m behind a sill (a real gradient, positive mean residual) -> must be KEPT;
* MILD   water held at 1.15 m (excess 0.15 m) -> KEPT, class held_mild;
* POOL   the top two rows are a LOWER basin (level -0.7 m, behind a sill): the channel faces next to it see a
         0.2-quantile reference in the basin and are flagged, but their water is real -> must be KEPT;
* FILM   a bank face whose lowest pixel (1.25 m) is above the tide, wet only by a 2 cm film in the
         maxima, dry in every snapshot -> untested, KEPT.
"""

import os
import tempfile
import unittest
from pathlib import Path

import numpy as np

from nj_sfincs import tide_surface as ts

N = 20
DXF = 25.0
NOISY, HELD, MILD, FILM = 10 * N + 10, 5 * N + 5, 15 * N + 5, 5 * N + 15
J = np.tile(np.arange(N), N)  # row index j of face i * N + j
POOL = np.flatnonzero(J >= N - 2)
RING = np.array(
    [NOISY + di * N + dj for di in (-1, 0, 1) for dj in (-1, 0, 1) if di or dj]
)
T_TIDE = 12.42  # h
SPIN_H = ts.SPINUP_D * 24
NDAYS = 6
T_END = SPIN_H + NDAYS * ts.DAY_H + 1.0


def tide(t_h):
    return 0.2 + 0.8 * np.cos(2 * np.pi * np.asarray(t_h) / T_TIDE)


def surface(t_h, rng):
    """zs of every face at times t_h (h), shape (len(t), N*N)."""
    t = np.atleast_1d(np.asarray(t_h, float))
    z = np.repeat(tide(t)[:, None], N * N, axis=1)
    z[:, NOISY] += 0.5 * np.sin(
        rng.uniform(0, 2 * np.pi, t.size)
    )  # phase at a random instant
    z[:, HELD] = 1.30
    z[:, MILD] = np.maximum(tide(t), 1.15)
    z[:, POOL] = -0.7
    return z


def write_run(d: Path):
    import netCDF4

    rng = np.random.default_rng(1)
    jj, ii = np.meshgrid(np.arange(N), np.arange(N))
    x, y = (ii.ravel() + 0.5) * DXF, (jj.ravel() + 0.5) * DXF
    nf = N * N
    z_zmin = np.full(nf, -3.0, "f4")
    z_zmax = np.full(nf, 0.5, "f4")  # open water: submerged under the 1.0 m high water
    for f, zmin in ((NOISY, -2.0), (HELD, 0.9), (MILD, 0.9), (FILM, 1.25)):
        z_zmin[f], z_zmax[f] = zmin, 3.0  # bank faces: mostly land
    z_zmin[RING], z_zmax[RING] = -2.0, 3.0
    z_zmax[POOL] = -1.0  # the basin is open water too (submerged under its own -0.7 m)
    (d / "sfincs.inp").write_text("tref = 20121012 000000\nhuthresh = 0.01\n")
    with netCDF4.Dataset(d / "sfincs.nc", "w") as g:
        g.createDimension("mesh2d_nFaces", nf)
        g.dx = DXF
        for k, v, t in (
            ("level", np.ones(nf), "i4"),
            ("mask", np.ones(nf), "i1"),
            ("mesh2d_face_x", x, "f8"),
            ("mesh2d_face_y", y, "f8"),
        ):
            g.createVariable(k, t, ("mesh2d_nFaces",))[:] = v
    with netCDF4.Dataset(d / "sfincs_subgrid.nc", "w") as s:
        s.createDimension("np", nf)
        s.createVariable("z_zmin", "f4", ("np",))[:] = z_zmin
        s.createVariable("z_zmax", "f4", ("np",))[:] = z_zmax
    tmax = np.arange(3.0, T_END, 3.0)  # zsmax block ends (h)
    tsn = np.arange(0.0, T_END, 6.0)  # zs snapshots (h)
    zsmax = np.empty((tmax.size, nf), "f4")
    for k, te in enumerate(tmax):
        tt = np.linspace(te - 3.0, te, 181)
        zz = surface(tt, rng)
        zz[:, NOISY] = tide(tt) + 0.5  # every block catches a crest
        zz[:, RING] = tide(tt)[:, None] + 0.2
        zsmax[k] = zz.max(0)
    zsmax[:, FILM] = 1.27  # a film over the lowest pixel
    zs = surface(tsn, rng).astype("f4")
    zs[:, FILM] = z_zmin[FILM]  # dry in every snapshot
    with netCDF4.Dataset(d / "sfincs_map.nc", "w") as m:
        m.createDimension("nmesh2d_face", nf)
        m.createDimension("time", tsn.size)
        m.createDimension("timemax", tmax.size)
        m.createVariable("timemax", "f8", ("timemax",))[:] = tmax * 3600
        m.createVariable("time", "f8", ("time",))[:] = tsn * 3600
        m.createVariable("zsmax", "f4", ("timemax", "nmesh2d_face"))[:] = zsmax
        m.createVariable("zs", "f4", ("time", "nmesh2d_face"))[:] = zs
        m.createVariable("zb", "f4", ("nmesh2d_face",))[:] = z_zmin
    return zsmax, tmax


class TestPureCore(unittest.TestCase):
    def test_day_statistics_matches_hand(self):
        HH = np.array([[1.0, np.nan, 2.0], [3.0, np.nan, np.nan]], np.float32)
        mhh, mx, days = ts.day_statistics(HH)
        np.testing.assert_allclose(mhh, [2.0, np.nan, 2.0])
        np.testing.assert_allclose(mx, [3.0, np.nan, 2.0])
        np.testing.assert_array_equal(days, [2, 0, 1])

    def test_tidal_days_skip_spinup_and_partial_day(self):
        hours = np.array([-3.0, 0.0, 3.0, 24.84, 27.0, 49.68, 52.0])
        day, nd, use = ts.tidal_days(hours)
        self.assertEqual(nd, 2)
        np.testing.assert_array_equal(
            use, [False, False, True, True, True, True, False]
        )
        np.testing.assert_array_equal(day[use], [0, 0, 1, 1])

    def test_local_quantile_needs_minn(self):
        v = np.array([1.0, 2.0, 3.0, 4.0, np.nan])
        nb = np.array([[0, 1, 2, 3], [0, 1, 4, 5]])  # 5 = missing
        q, c = ts.local_quantile(v, nb, 0.5, minn=3, workers=1)
        self.assertAlmostEqual(float(q[0]), 2.5)
        self.assertTrue(np.isnan(q[1]))
        np.testing.assert_array_equal(c, [4, 2])

    def test_classify_rules(self):
        e = np.array([0.05, np.nan, 0.5, 0.5, 0.15, 0.4, 0.5])
        n = np.array([0, 0, 50, 50, 50, 50, 3])
        m = np.array([np.nan, np.nan, 0.01, 0.30, 0.10, -0.2, 0.0])  # does not decide
        nhw = np.array([0, 0, 12, 12, 12, 12, 1])
        mhw = np.array([np.nan, np.nan, 0.02, 0.3, 0.1, 0.25, 0.0])
        cls = ts.classify(e, n, m, nhw, mhw)
        self.assertEqual(
            [ts.CLASS_NAMES[c] for c in cls],
            [
                "ok",
                "no_ref",
                "noise",
                "held_strong",
                "held_mild",
                "held_strong",
                "untested",
            ],
        )

    def test_low_tide_water_alone_is_not_held(self):
        cls = ts.classify(np.array([0.4]), [50], [0.35], [12], [0.02])
        self.assertEqual(int(cls[0]), ts.NOISE)

    def test_denoise_keeps_a_standing_step(self):
        a, b = ts.denoise(
            np.array([1.6]), np.array([1.9]), np.array([1.0]), np.array([1.2]),
            np.array([ts.NOISE]), step=np.array([0.25]),
        )  # fmt: skip
        np.testing.assert_allclose(a, [1.25])
        np.testing.assert_allclose(b, [1.45])
        a, _ = ts.denoise(
            np.array([1.6]), np.array([1.9]), np.array([1.0]), np.array([1.2]),
            np.array([ts.NOISE]), step=np.array([-0.3]),
        )  # fmt: skip
        np.testing.assert_allclose(a, [1.0])

    def test_standing_step_survives_only_without_spread(self):
        st = ts.standing_step(
            np.array([0.30, 0.14]), np.array([0.02, 0.35]), np.array([30, 6])
        )
        self.assertAlmostEqual(float(st[0]), 0.30 - 2 * 0.02 / np.sqrt(30), places=5)
        self.assertEqual(float(st[1]), 0.0)

    def test_denoise_only_noise_and_never_raises(self):
        cls = np.array([ts.NOISE, ts.HELD_STRONG, ts.NOISE])
        mhh, mx = np.array([1.5, 1.3, 0.9]), np.array([1.8, 1.4, 1.0])
        ref, refmax = np.array([1.0, 1.0, 1.0]), np.array([1.2, 1.2, np.nan])
        a, b = ts.denoise(mhh, mx, ref, refmax, cls)
        np.testing.assert_allclose(a, [1.0, 1.3, 0.9])
        np.testing.assert_allclose(b, [1.2, 1.4, 1.0])


class TestSyntheticRun(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import xarray as xr

        cls.tmp = tempfile.TemporaryDirectory()
        d = Path(cls.tmp.name)
        cls.zsmax, cls.tmax = write_run(d)
        cls.out = d / "out" / "surface.nc"
        cls.summ = ts.build(d, cls.out, workers=2)
        with xr.open_dataset(cls.out) as o:
            cls.o = o.load()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def name(self, f):
        return ts.CLASS_NAMES[int(self.o.denoise_class[f])]

    def test_raw_is_the_mean_daily_max(self):
        hours = self.tmax - ts.SPINUP_D * 24
        day, nd, use = ts.tidal_days(hours)
        self.assertEqual(nd, NDAYS)
        hh = np.array([self.zsmax[use & (day == k)].max(0) for k in range(nd)])
        np.testing.assert_allclose(self.o.mean_higher_high_raw, hh.mean(0), atol=1e-5)
        np.testing.assert_allclose(self.o.max_month_raw, hh.max(0), atol=1e-6)

    def test_noisy_sliver_is_replaced_by_the_channel(self):
        self.assertEqual(self.name(NOISY), "noise")
        self.assertGreater(float(self.o.mean_higher_high_raw[NOISY]), 1.4)
        self.assertAlmostEqual(float(self.o.mean_higher_high[NOISY]), 1.0, delta=0.05)
        self.assertLess(float(self.o.max_month[NOISY]), 1.1)
        self.assertLess(abs(float(self.o.snap_mean[NOISY])), 0.25)

    def test_ringing_cluster_is_replaced(self):
        cls = self.o.denoise_class.values[RING]
        self.assertTrue((cls == ts.NOISE).all(), [ts.CLASS_NAMES[c] for c in cls])
        np.testing.assert_allclose(self.o.mean_higher_high.values[RING], 1.0, atol=0.05)

    def test_held_water_is_kept(self):
        self.assertEqual(self.name(HELD), "held_strong")
        self.assertEqual(self.name(MILD), "held_mild")
        for f in (HELD, MILD):
            self.assertEqual(
                float(self.o.mean_higher_high[f]), float(self.o.mean_higher_high_raw[f])
            )
            self.assertGreater(float(self.o.snap_mean[f]), 0.1)

    def test_film_face_untested_and_kept(self):
        self.assertEqual(self.name(FILM), "untested")
        self.assertEqual(int(self.o.film[FILM]), 1)
        self.assertEqual(
            float(self.o.mean_higher_high[FILM]),
            float(self.o.mean_higher_high_raw[FILM]),
        )

    def test_faces_beside_a_lower_pool_are_kept(self):
        near = np.flatnonzero((J >= N - 6) & (J < N - 2))
        cls = self.o.denoise_class.values[near]
        self.assertTrue(
            (self.o.excess.values[near] > 0.1).any()
        )  # the q20 reference falls in the pool
        self.assertFalse((cls == ts.NOISE).any())
        np.testing.assert_array_equal(
            self.o.mean_higher_high.values[near],
            self.o.mean_higher_high_raw.values[near],
        )

    def test_everything_else_untouched(self):
        far = np.flatnonzero(J < N - 8)
        rest = np.setdiff1d(far, np.r_[NOISY, HELD, MILD, FILM, RING])
        self.assertTrue((self.o.denoise_class.values[rest] == ts.OK).all())
        np.testing.assert_array_equal(
            self.o.mean_higher_high.values[rest],
            self.o.mean_higher_high_raw.values[rest],
        )
        self.assertEqual(self.summ["replaced"], 1 + RING.size)

    def test_mhhw_maps_names_and_atomic_write(self):
        for k in ("mean_higher_high", "max_month", "days_wet"):
            self.assertIn(k, self.o)
        self.assertEqual(int(self.o.attrs["ndays"]), NDAYS)
        left = [p for p in os.listdir(self.out.parent) if ".tmp" in p]
        self.assertEqual(left, [])
        self.assertTrue(Path(str(self.out) + ".json").is_file())


if __name__ == "__main__":
    unittest.main()
