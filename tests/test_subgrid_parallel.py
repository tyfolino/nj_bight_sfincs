"""nj_sfincs.subgrid_parallel: the vectorised index tables equal the serial loops."""

import unittest

import numpy as np

from nj_sfincs import subgrid_parallel as sp


def _random_tables(rng, nc):
    level = np.sort(rng.integers(0, 3, nc))
    mu = rng.integers(-1, 2, nc)
    nu = rng.integers(-1, 2, nc)
    # -1 = no neighbour; mu2/nu2 sometimes set even where mu <= 0 (the serial COUNT
    # still counts them, its fill loop skips them: trailing zero entries)
    mu1, mu2, nu1, nu2 = (rng.integers(-1, nc, nc) for _ in range(4))
    return level, nu, nu1, nu2, mu, mu1, mu2


class TestUvTables(unittest.TestCase):
    def test_matches_serial_loop(self):
        rng = np.random.default_rng(1)
        for nc in (1, 7, 500):
            args = _random_tables(rng, nc)
            n1, a = sp.uv_tables(*args)
            n2, b = sp.uv_tables_serial(*args)
            self.assertEqual(n1, n2)
            for k in b:
                np.testing.assert_array_equal(a[k], b[k], err_msg=k)


class TestGroupByBlock(unittest.TestCase):
    def test_serial_block_membership_and_order(self):
        rng = np.random.default_rng(2)
        li = sp.LevelInfo(
            ilev=0, n0=3, n1=40, m0=5, m1=33, dx=1.0, dy=1.0, dxp=0.1, dyp=0.1,
            nrcb=8, nrbn=5, nrbm=4,
        )  # fmt: skip
        nn = rng.integers(0, 45, 400)
        mm = rng.integers(0, 38, 400)
        idx = np.arange(400) * 3
        got = sp._group_by_block(li, nn, mm, idx)
        for ii in range(li.nrbm):
            for jj in range(li.nrbn):
                bn0, bn1, bm0, bm1 = sp._block_bounds(li, ii, jj)
                want = idx[(nn >= bn0) & (nn < bn1) & (mm >= bm0) & (mm < bm1)]
                have = got.get(ii * li.nrbn + jj, np.zeros(0, dtype=int))
                np.testing.assert_array_equal(have, want)


class TestShuffle(unittest.TestCase):
    def test_roundtrip_bits(self):
        a = np.array([[1.5, np.nan], [-0.0, 3e38]], dtype=np.float32)
        b = sp._unshuffle(sp._shuffle(a))
        self.assertEqual(b.dtype, a.dtype)
        np.testing.assert_array_equal(a.view(np.uint32), b.view(np.uint32))


if __name__ == "__main__":
    unittest.main()
