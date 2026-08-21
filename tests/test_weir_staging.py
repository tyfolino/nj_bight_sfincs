"""The weirfile key survives re-staging (FINDINGS §38 promotion, 2026-08-21).

The Keansburg protection line lives in the sealed template as ``sfincs.weir`` plus a
``weirfile`` key in ``sfincs.inp``. Arms inherit the FILE via ``copytree``, but
hydromt's writer drops keys it does not model, so ``finalize`` must repair the KEY —
the latitude failure shape. These tests watch the guard fire, and watch it stay quiet
when it must.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nj_sfincs.model import _ensure_weirfile_key

INP = "tref                 = 20121028 000000\nobsfile              = sfincs.obs\n"


class TestEnsureWeirfileKey(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.dir = Path(self._td.name)
        self.addCleanup(self._td.cleanup)

    def test_key_readded_when_file_staged(self):
        (self.dir / "sfincs.weir").write_text("x\n1 4\n0 0 2.9 0.6\n")
        out = _ensure_weirfile_key(INP, self.dir)
        self.assertIn("\nweirfile             = sfincs.weir", out)
        # inserted beside obsfile, not appended blindly
        self.assertLess(out.index("obsfile"), out.index("weirfile"))

    def test_no_file_no_key(self):
        """A domain without structures must not gain a dangling weirfile key."""
        self.assertEqual(_ensure_weirfile_key(INP, self.dir), INP)

    def test_idempotent(self):
        (self.dir / "sfincs.weir").write_text("x\n1 4\n0 0 2.9 0.6\n")
        once = _ensure_weirfile_key(INP, self.dir)
        self.assertEqual(_ensure_weirfile_key(once, self.dir), once)

    def test_missing_anchor_appends_rather_than_noop(self):
        """The characteristic failure of an anchored patch is a silent no-op."""
        (self.dir / "sfincs.weir").write_text("x\n1 4\n0 0 2.9 0.6\n")
        out = _ensure_weirfile_key("tref                 = 20121028 000000\n", self.dir)
        self.assertIn("weirfile             = sfincs.weir", out)

    def test_sealed_template_carries_both(self):
        """The promotion itself: template has the file, the key, and they match data/."""
        from nj_sfincs import domain

        if domain.active().name != "v1_5_raritan":
            self.skipTest("v1_5_raritan-specific")
        from nj_sfincs.config import ROOT

        tmpl = ROOT / "experiments" / "v1_5_raritan" / "_template_sealed"
        if not tmpl.is_dir():
            self.skipTest("no sealed template on this checkout")
        self.assertTrue((tmpl / "sfincs.weir").is_file())
        self.assertIn("\nweirfile", (tmpl / "sfincs.inp").read_text())
        banked = ROOT / "data" / "structures_v1_5" / "keansburg_weir.weir"
        self.assertEqual(
            (tmpl / "sfincs.weir").read_bytes(),
            banked.read_bytes(),
            "template sfincs.weir has drifted from the banked data/ copy",
        )


if __name__ == "__main__":
    unittest.main()
