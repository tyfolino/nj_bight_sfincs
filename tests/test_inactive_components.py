"""`model._inactive_components`: what counts as an interior hole (2026-11-14).

nj2's ring tops out on a flat cut that lies ON the grid rectangle's top edge, which split the
outside of the ring into two components; the old rule (exterior = the largest component only)
then called the smaller one, with the declared sea in it, a hole and re-activated it. The rule
now: exterior = the largest component plus every component that reaches outside the region.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

import nj_sfincs  # noqa: F401  (pyproj before hydromt)
from nj_sfincs import model

NX, NY, X0, Y0 = 9, 6, 500_000.0, 4_400_000.0


def _fake_sf():
    import scipy.sparse as sp

    ii, jj = np.meshgrid(np.arange(NX), np.arange(NY))  # col, row
    ii, jj = ii.ravel(), jj.ravel()
    xy = np.c_[X0 + ii + 0.5, Y0 + jj + 0.5]
    k = jj * NX + ii
    rows, cols = [], []
    for di, dj in ((1, 0), (0, 1)):
        ok = (ii + di < NX) & (jj + dj < NY)
        a, b = k[ok], (jj[ok] + dj) * NX + ii[ok] + di
        rows += [a, b]
        cols += [b, a]
    r, c = np.concatenate(rows), np.concatenate(cols)
    adj = sp.csr_matrix((np.ones(len(r)), (r, c)), shape=(NX * NY, NX * NY))
    grid = SimpleNamespace(face_face_connectivity=adj, face_coordinates=xy)
    return (
        SimpleNamespace(
            quadtree_grid=SimpleNamespace(data=SimpleNamespace(grid=grid)), crs=32618
        ),
        ii,
        jj,
    )


class TestInactiveComponents(unittest.TestCase):
    def setUp(self):
        import geopandas as gpd
        import shapely

        self.tmp = tempfile.TemporaryDirectory()
        # region = columns 3..6, full height: it touches the grid's top AND bottom edge, so
        # the outside is a west (cols 0-2, 18 faces, the largest) and an east (cols 7-8)
        self.region = Path(self.tmp.name) / "ring.geojson"
        gpd.GeoDataFrame(
            geometry=[shapely.box(X0 + 3, Y0, X0 + 7, Y0 + NY)], crs=32618
        ).to_file(self.region)
        self.sf, self.ii, self.jj = _fake_sf()
        inside = (self.ii >= 3) & (self.ii <= 6)
        self.mask = np.where(inside, 1, 0)
        # the declared sea: inside the ring, against the east outside
        self.sea = (self.ii == 6) & (self.jj <= 2)
        self.mask[self.sea] = 0
        # a true interior hole
        self.hole = (self.ii == 4) & (self.jj == 3)
        self.mask[self.hole] = 0

    def tearDown(self):
        self.tmp.cleanup()

    def test_only_the_interior_island_is_a_hole(self):
        ocean, hole = model._inactive_components(self.sf, self.mask, self.region)
        np.testing.assert_array_equal(hole, self.hole)
        self.assertTrue(ocean[self.sea].all())  # the sea is exterior, never filled
        self.assertTrue(ocean[self.ii >= 7].all() and ocean[self.ii <= 2].all())

    def test_fill_keeps_the_sea_inactive(self):
        out = model._fill_inactive_holes(
            self.sf, self.mask, np.zeros(len(self.mask)), self.region
        )
        self.assertTrue((out[self.hole] == 1).all())
        self.assertTrue((out[self.sea] == 0).all())
        self.assertTrue((out[(self.ii <= 2) | (self.ii >= 7)] == 0).all())


if __name__ == "__main__":
    unittest.main()
