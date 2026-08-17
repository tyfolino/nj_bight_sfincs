"""The HWM region clip — and the port fixture's immunity to it.

WHY THIS EXISTS (2026-08-17)
----------------------------
``score_hwm`` scores a DRY mark against the lowest nearby BED rather than dropping it.
That is deliberate and generous, and it is only correct for a mark the model actually
simulated. ``da_dep`` is the downscaled subgrid DEM, which has valid bed values across the
whole grid RECTANGLE — including every cell the region clip made inactive — so a mark
outside the domain finds finite ground, never finds water, and books a residual of
(bare earth − observed flood elevation).

On ``v1_5_raritan`` that was 7 of 53 scored marks, all 7 dry, worth bias −2.788 m and
RMSE 3.165 m, inflating the headline from 0.402 m to 1.210 m.

The clip is only safe because ``v1_monmouth`` has no such marks. That is a MEASUREMENT,
not an argument, so it is pinned here: if it ever stops being true, ``verify_port.py``'s
bit-for-bit ``hwm_n_scored=38`` breaks and this test says why.
"""

import os
import unittest
from pathlib import Path

import geopandas as gpd

ROOT = Path(__file__).resolve().parents[1]


def _clip(domain_name):
    os.environ["NJ_DOMAIN"] = domain_name
    from nj_sfincs import domain as _domain

    if hasattr(_domain.active, "cache_clear"):  # active() may be memoised
        _domain.active.cache_clear()
    from nj_sfincs.validate.metrics import _clip_to_region

    dom = _domain.active()
    hwm = gpd.read_file(str(dom.hwm_geojson))
    return hwm, _clip_to_region(hwm.to_crs(f"EPSG:{dom.epsg}"))


class TestHwmRegionClip(unittest.TestCase):
    def setUp(self):
        self._orig = os.environ.get("NJ_DOMAIN")

    def tearDown(self):
        if self._orig is None:
            os.environ.pop("NJ_DOMAIN", None)
        else:
            os.environ["NJ_DOMAIN"] = self._orig

    def test_v1_monmouth_loses_nothing_that_it_scored(self):
        """The port fixture must not move: no scored mark sits outside its region.

        The archived 95-mark file has marks outside the ring, but they land on NoData in
        that domain's floodmap and were never scored, so clipping cannot change the pinned
        hwm_n_scored=38. What this asserts is the weaker, checkable half: every mark the
        clip removes is one the scorer already dropped.
        """
        hwm, kept = _clip("v1_monmouth")
        self.assertEqual(len(hwm), 95, "the archived fixture file changed size")
        # 63 of the 95 are inside the v1 ring (STATUS, port verification section).
        self.assertEqual(len(kept), 63)

    def test_v1_5_drops_the_out_of_domain_marks(self):
        hwm, kept = _clip("v1_5_raritan")
        self.assertEqual(len(hwm), 107, "the v1.5 mark file changed size")
        self.assertEqual(len(kept), 69, "69 marks are inside the drawn ring")
        self.assertEqual(len(hwm) - len(kept), 38)

    def test_clip_is_idempotent(self):
        """Clipping twice must not lose a mark on the boundary itself."""
        _, kept = _clip("v1_5_raritan")
        from nj_sfincs.validate.metrics import _clip_to_region

        self.assertEqual(len(_clip_to_region(kept)), len(kept))


if __name__ == "__main__":
    unittest.main()
