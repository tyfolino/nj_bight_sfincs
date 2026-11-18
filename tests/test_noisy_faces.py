"""``scripts/noisy_faces.py``: the bank-face flag rule on a synthetic patch.

A 25 m patch of open water at mhh 1.00 m (submerged faces), with:
  * a BANK face (mostly land, deep sliver) reading 1.50 m -> flagged;
  * a FILM face reading 0.40 m above the water but only 2 cm over its lowest pixel -> NOT flagged (not deep);
  * a face 5 cm high -> NOT flagged (under the 0.10 m cut).
Then the snapshot classifier: a face that rings against flat neighbours is ``noisy``, a steady offset is
``quiet``.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import noisy_faces as nf  # noqa: E402


def _patch():
    gx, gy = np.meshgrid(np.arange(15) * 25.0, np.arange(15) * 25.0)
    x, y = gx.ravel(), gy.ravel()
    n = x.size
    dx = np.full(n, 25.0)
    mhh = np.full(n, 1.00, np.float32)
    z_zmin = np.full(n, -3.0, np.float32)
    z_zmax = np.full(n, -1.0, np.float32)  # submerged open water
    c = 7 * 15 + 7  # centre
    bank, film, mild = c, c + 2, c - 2
    mhh[bank], z_zmin[bank], z_zmax[bank] = 1.50, -2.0, 4.0
    mhh[film], z_zmin[film], z_zmax[film] = 1.40, 1.38, 3.0
    mhh[mild], z_zmin[mild], z_zmax[mild] = 1.05, -2.0, 3.0
    return x, y, dx, mhh, z_zmin, z_zmax, bank, film, mild


class TestFlagRule(unittest.TestCase):
    def test_bank_flagged_film_and_mild_not(self):
        x, y, dx, mhh, zmin, zmax, bank, film, mild = _patch()
        r = nf.flag(x, y, dx, mhh, zmin, zmax, q=0.2, workers=2)
        self.assertEqual(np.flatnonzero(r["flagged"]).tolist(), [bank])
        self.assertAlmostEqual(float(r["excess"][bank]), 0.50, places=4)
        self.assertTrue(r["ref_is_submerged"][bank])
        self.assertFalse(r["deep"][film])
        self.assertLess(float(r["excess"][mild]), 0.10)

    def test_reference_ignores_a_bank_cluster(self):
        # a run of high non-submerged faces next to the bank must not raise its reference
        x, y, dx, mhh, zmin, zmax, bank, *_ = _patch()
        for k in (bank + 1, bank + 15, bank - 15):
            mhh[k], zmax[k] = 1.50, 4.0
        r = nf.flag(x, y, dx, mhh, zmin, zmax, q=0.5, workers=2)
        self.assertAlmostEqual(float(r["ref"][bank]), 1.00, places=4)
        self.assertTrue(r["flagged"][bank])


class TestSnapshotClass(unittest.TestCase):
    def test_ringing_is_noisy_steady_offset_is_quiet(self):
        n = 10
        faces = np.array([0, 9])
        nb = np.array([[1, 2, 3, 4, 5], [4, 5, 6, 7, 8]])  # flat faces 1..8
        snaps = []
        for t in range(12):
            z = np.full(n, 1.0)
            z[0] = 1.0 + 0.5 * (-1) ** t  # rings, mean 0 residual
            z[9] = 1.3  # steady 0.3 m above
            snaps.append(z)
        std, cnt = nf.snapshot_residual_std(iter(snaps), faces, nb)
        cls = nf.classify(std, cnt)
        self.assertEqual(cls.tolist(), [nf.CLS_NOISY, nf.CLS_QUIET])
        self.assertTrue((cnt == 12).all())

    def test_dry_neighbours_give_no_class(self):
        z = np.full(6, np.nan)
        z[0] = 1.0
        std, cnt = nf.snapshot_residual_std(
            iter([z] * 5), np.array([0]), np.array([[1, 2, 3, 4, 5]])
        )
        self.assertEqual(int(cnt[0]), 0)
        self.assertEqual(nf.classify(std, cnt).tolist(), [nf.CLS_NONE])


if __name__ == "__main__":
    unittest.main()
