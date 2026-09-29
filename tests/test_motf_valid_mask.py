"""``Domain.motf_valid_tif``: score the MOTF sheet only where it can adjudicate.

v4 (2026-09-29) scores the NJ-only sheet on NJ land alone — a validity raster on the
MOTF grid instead of lon/lat boxes, because the DE / PA border is a diagonal river. Pins
that the raster joins the boxes in ``motf_exclude_mask`` (so every consumer — the score,
the FA decomposition, the plots — sees one screen), and that a raster on any other grid
is REFUSED rather than silently shifting the scored footprint.
"""

from __future__ import annotations

import dataclasses
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import rasterio
from rasterio.transform import from_origin

from nj_sfincs import domain
from nj_sfincs.validate import metrics

T = from_origin(500_000.0, 4_400_000.0, 15.0, 15.0)


def _write(p: Path, a: np.ndarray, transform=T) -> Path:
    with rasterio.open(
        p,
        "w",
        driver="GTiff",
        width=a.shape[1],
        height=a.shape[0],
        count=1,
        dtype="uint8",
        crs="EPSG:32618",
        transform=transform,
    ) as d:
        d.write(a.astype("uint8"), 1)
    return p


class TestMotfValidMask(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.valid = np.zeros((6, 8), dtype="uint8")
        self.valid[:, :5] = 1  # "NJ" is the west five columns

    def tearDown(self):
        self.tmp.cleanup()

    def _dom(self, valid_tif, boxes=()):
        d = dataclasses.replace(
            domain.DOMAINS["v4"],
            motf_valid_tif=valid_tif,
            motf_exclude_boxes_ll=boxes,
        )
        return mock.patch.object(domain, "active", return_value=d)

    def test_no_raster_no_boxes_is_no_screen(self):
        with self._dom(None):
            self.assertIsNone(metrics.motf_exclude_mask((6, 8), T))

    def test_raster_screens_what_it_marks_invalid(self):
        f = _write(self.dir / "valid.tif", self.valid)
        with self._dom(f):
            ex = metrics.motf_exclude_mask((6, 8), T)
        np.testing.assert_array_equal(ex, self.valid != 1)

    def test_raster_and_boxes_are_one_screen(self):
        f = _write(self.dir / "valid.tif", self.valid)
        # a box over the top-left cell only (UTM 18N → lon/lat at the cell centre)
        from pyproj import Transformer

        lon, lat = Transformer.from_crs(32618, 4326, always_xy=True).transform(
            500_007.5, 4_399_992.5
        )
        box = (("corner", (lon - 1e-5, lat - 1e-5, lon + 1e-5, lat + 1e-5), "test"),)
        with self._dom(f, box):
            ex = metrics.motf_exclude_mask((6, 8), T)
        want = self.valid != 1
        want[0, 0] = True
        np.testing.assert_array_equal(ex, want)

    def test_raster_on_another_grid_is_refused(self):
        shifted = from_origin(500_015.0, 4_400_000.0, 15.0, 15.0)
        f = _write(self.dir / "valid.tif", self.valid, shifted)
        with self._dom(f), self.assertRaises(ValueError):
            metrics.motf_exclude_mask((6, 8), T)
        g = _write(self.dir / "small.tif", self.valid[:5])
        with self._dom(g), self.assertRaises(ValueError):
            metrics.motf_exclude_mask((6, 8), T)


if __name__ == "__main__":
    unittest.main()
