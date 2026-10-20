"""The MOTF false-alarm decomposition — and what it measured on v1.5.

WHY THIS EXISTS (2026-08-20)
----------------------------
MOTF is a surge-only bathtub and structurally cannot contain rain ponding, while our
runs force rain everywhere with infiltration effectively OFF. ``fa_decomposition``
splits the false alarms by whether the water ever had a wet surface path to tidal
water (``hmax`` is a running max, so its footprint is the union of everything that
was ever wet — a component that never touches the sea got its water from rain or
local runoff, not surge).

Measured on v1.5 premier against its own MOTF render + NJ screen: 7.96 of 11.40 km²
of false alarm — 70% — was DISCONNECTED on the pre-weir premier (connected 3.445425,
``motf_far_connected`` 0.061 vs ``motf_far`` 0.176, ``motf_csi_connected`` 0.795,
``motf_csi`` 0.7107507558045186). The labels were then VALIDATED against
``diag-premier-norain`` (FINDINGS §39: disc_precision 0.991).

RE-PINNED 2026-08-21 for the WEIR PROMOTION (FINDINGS §38, user decision):
``naccs-premier`` now includes the Keansburg protection line, which dries a
sea-connected FA pocket — connected drops to 2.580525 km² while disconnected moves
only 0.005 km² (7.9551 → 7.959825: rain barely cares about the weir, which
corroborates the classifier), CSI 0.7044218462614195. Both baselines are in this
docstring on purpose.

These keys are ADDITIVE — the headline motf_* keys must not move (verify_port.py is
the gate for that; this test pins the decomposition itself).
"""

import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestFaDecomposition(unittest.TestCase):
    def setUp(self):
        self._orig = os.environ.get("NJ_DOMAIN")
        os.environ["NJ_DOMAIN"] = "v1_5_raritan"
        from nj_sfincs import domain as _domain

        if hasattr(_domain.active, "cache_clear"):
            _domain.active.cache_clear()

    def tearDown(self):
        if self._orig is None:
            os.environ.pop("NJ_DOMAIN", None)
        else:
            os.environ["NJ_DOMAIN"] = self._orig

    def _decomp(self):
        from nj_sfincs.config import exp_root
        from nj_sfincs.validate import fa_decomposition, load_floodmap

        rd = exp_root() / "naccs-premier"
        if not (rd / "sfincs_map.nc").exists():
            self.skipTest(f"{rd} has no output on this machine")
        _, hmax, dep = load_floodmap(rd, need_model=False)
        return fa_decomposition(hmax, dep, rd)

    def test_disconnected_dominates_on_v1_5(self):
        """70% of the false alarm area has no wet path to the sea — the rain signal."""
        f = self._decomp()
        self.assertAlmostEqual(f["motf_km2_fa_connected"], 2.580525, places=6)
        self.assertAlmostEqual(f["motf_km2_fa_disconnected"], 7.959825, places=6)
        self.assertGreater(f["motf_km2_fa_disconnected"], f["motf_km2_fa_connected"])
        self.assertAlmostEqual(f["motf_far_connected"], 0.04716298349357261, places=9)
        self.assertAlmostEqual(f["motf_csi_connected"], 0.7893125038322921, places=9)

    def test_rainonly_key_is_retired(self):
        """``motf_km2_fa_rainonly`` was 0 by construction and is gone (2026-10-20)."""
        self.assertNotIn("motf_km2_fa_rainonly", self._decomp())

    def test_diagnostic_keys_do_not_touch_headline_keys(self):
        """The decomposition must be purely additive next to motf_metrics."""
        from nj_sfincs.config import exp_root
        from nj_sfincs.validate import load_floodmap, motf_metrics

        rd = exp_root() / "naccs-premier"
        if not (rd / "sfincs_map.nc").exists():
            self.skipTest("no output on this machine")
        _, hmax, dep = load_floodmap(rd, need_model=False)
        m = motf_metrics(hmax, dep, rd)
        self.assertAlmostEqual(m["motf_csi"], 0.7044218462614195, places=9)
        self.assertNotIn("motf_far_connected", m)


if __name__ == "__main__":
    unittest.main()
