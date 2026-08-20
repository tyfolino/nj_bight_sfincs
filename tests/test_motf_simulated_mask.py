"""The MOTF active-mask screen — and what it is worth on each domain.

WHY THIS EXISTS (2026-08-20)
----------------------------
``motf_metrics`` used to score over ``MOTF valid AND dep > 0``. ``da_dep`` is the
downscaled subgrid DEM, which carries valid bed across the whole grid RECTANGLE, so the
comparison ran on ground the solver never simulated — the third instance of the
confusion ``_clip_to_region`` and ``_fill_inactive_holes`` document, and it bit in BOTH
directions:

* MOTF wet where the domain does not reach books a MISS the model could not have hit.
* ``downscale_floodmap`` paints zsmax onto low ground under INACTIVE faces, so phantom
  water books a FALSE ALARM the solver never computed.

The screen is the run's OWN ``msk``, not a region polygon, because the active mask is
region + ``mask_zmin`` + always-active boxes and legitimately extends past the polygon:
on ``v1_monmouth`` the registry region is 2,494 km² against the run's own 2,909 km².

These are MEASUREMENTS, not arguments. ``verify_port.py`` pins the v1_monmouth scores
bit-for-bit; this test says WHY they are what they are if that gate ever moves.
"""

import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _fixture(domain_name, run):
    os.environ["NJ_DOMAIN"] = domain_name
    from nj_sfincs import domain as _domain

    if hasattr(_domain.active, "cache_clear"):
        _domain.active.cache_clear()
    from nj_sfincs.config import exp_root

    return exp_root() / run


class TestMotfSimulatedMask(unittest.TestCase):
    def setUp(self):
        self._orig = os.environ.get("NJ_DOMAIN")

    def tearDown(self):
        if self._orig is None:
            os.environ.pop("NJ_DOMAIN", None)
        else:
            os.environ["NJ_DOMAIN"] = self._orig

    def _score(self, domain_name, run):
        rd = _fixture(domain_name, run)
        if not (rd / "sfincs_map.nc").exists():
            self.skipTest(f"{rd} has no output on this machine")
        from nj_sfincs.validate import load_floodmap, motf_metrics

        _, hmax, dep = load_floodmap(rd, need_model=False)
        return motf_metrics(hmax, dep, rd)

    def test_v1_5_is_dominated_by_unreachable_motf_wet(self):
        """On v1.5 the correction is almost all MISSES the model could not have hit.

        Its mask reaches every low cell its own downscale could bleed into, so the bleed
        term is 0.0018 km² — 8 cells, three orders of magnitude under the 2.56 km² of
        unreachable MOTF wet. Asserted as a RATIO so the point survives a re-run: on
        this domain the screen removes misses, not false alarms. Contrast v1_monmouth.
        """
        m = self._score("v1_5_raritan", "naccs-premier")
        self.assertLess(m["motf_km2_unsim_modwet"], 0.01)
        self.assertGreater(m["motf_km2_unsim_motfwet"], 2.0)
        self.assertGreater(
            m["motf_km2_unsim_motfwet"], 100 * m["motf_km2_unsim_modwet"]
        )
        self.assertAlmostEqual(m["motf_csi"], 0.6845927101805489, places=9)
        self.assertAlmostEqual(m["motf_pod"], 0.8206884110516467, places=9)
        self.assertAlmostEqual(m["motf_far"], 0.19499823050607526, places=9)

    def test_v1_monmouth_removes_downscale_bleed_too(self):
        """The port fixture DOES bleed: phantom water under inactive faces was scoring.

        These three are the values verify_port.py pins. If this test moves, that gate
        moves with it, and the REBASELINED note there is the thing to read.
        """
        m = self._score("v1_monmouth", "faber-waves-premier")
        self.assertGreater(m["motf_km2_unsim_modwet"], 3.0)
        self.assertAlmostEqual(m["motf_csi"], 0.6841603512860266, places=9)
        self.assertAlmostEqual(m["motf_pod"], 0.7926427001558183, places=9)
        self.assertAlmostEqual(m["motf_far"], 0.1666966401075916, places=9)

    def test_mask_is_a_subset_of_the_grid_and_not_everything(self):
        """A mask that is all-True would silently restore the old behaviour."""
        import rasterio

        from nj_sfincs.config import DATA
        from nj_sfincs.validate import simulated_mask

        rd = _fixture("v1_5_raritan", "naccs-premier")
        if not (rd / "sfincs_map.nc").exists():
            self.skipTest("no output on this machine")
        tif = Path(DATA) / "validation" / "sandy_motf_extent.tif"
        with rasterio.open(str(tif)) as r:
            shape, transform = r.shape, r.transform
        sim = simulated_mask(rd, shape, transform)
        self.assertEqual(sim.shape, shape)
        self.assertTrue(sim.any(), "mask is empty — nothing would score")
        self.assertFalse(sim.all(), "mask covers the whole sheet — screen is a no-op")


if __name__ == "__main__":
    unittest.main()
