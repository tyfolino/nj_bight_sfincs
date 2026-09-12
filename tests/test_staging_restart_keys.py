"""Every staged arm carries the restart hook, whatever the template's vintage.

2026-09-12: the sealed v3 template was built on 08-31, before ``dtrstout`` existed in
``add_forcing``; staging copies its ``sfincs.inp`` and re-writes it through hydromt, so
the F.4 arm was submitted for 40 h on ``main`` with no restart file. The per-arm restore
step is the one place every staging path passes through, so the keys live there.
"""

import tempfile
import unittest
from pathlib import Path

from nj_sfincs import model, restart


class TestStagedArmCarriesRestartKeys(unittest.TestCase):
    def _staged_inp(self, text: str) -> str:
        with tempfile.TemporaryDirectory() as d:
            inp = Path(d) / "sfincs.inp"
            inp.write_text(text)
            model.restore_diagnostics(Path(d))
            return inp.read_text()

    def test_pre_hook_template_inp_gains_both_keys(self):
        out = self._staged_inp(
            "mmax                 = 10\n"
            "dtmaxout             = 86400.0\n"
            "trstout              = -999.0\n"
            "obsfile              = sfincs.obs\n"
        )
        self.assertEqual(restart.inp_get(out, "dtrstout"), "21600.0")
        self.assertEqual(restart.inp_get(out, "dtmaxout"), "21600.0")
        self.assertEqual(out.count("dtmaxout"), 1, "overwrite, never duplicate")

    def test_one_lattice_dtmaxout_divides_dtrstout(self):
        out = self._staged_inp("dtmaxout             = 86400.0\n")
        dtmax = float(restart.inp_get(out, "dtmaxout"))
        dtrst = float(restart.inp_get(out, "dtrstout"))
        self.assertEqual(dtrst % dtmax, 0.0)
        self.assertEqual(dtrst, model.RESTART_DT_S)

    def test_add_forcing_and_staging_share_the_constant(self):
        src = Path(model.__file__).read_text()
        self.assertNotIn('"dtrstout": 21600.0', src)
        self.assertIn('"dtrstout": RESTART_DT_S', src)


if __name__ == "__main__":
    unittest.main()
