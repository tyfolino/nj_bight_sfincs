"""``Experiment.weir_from`` (2026-11-03): an arm's weir file replaces the template's, byte for byte.

The Overpeck dam bracket (logs/ironbound_overpeck_2026-11-03/) is the first use: two arms that
differ from ``p4-nowaves`` only in ``sfincs.weir``.
"""

from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path

from nj_sfincs import model, provenance
from nj_sfincs.config import Experiment

GOOD = (
    b"dam_a\n2 4\n0.0 0.0 1.74 0.6\n10.0 0.0 1.74 0.6\nsill_b\n1 4\n5.0 5.0 1.57 0.6\n"
)


class TestWeirFrom(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.d = Path(self._td.name)
        self.addCleanup(self._td.cleanup)

    def test_default_is_the_template(self):
        import dataclasses

        f = {x.name: x for x in dataclasses.fields(Experiment)}["weir_from"]
        self.assertIsNone(f.default)

    def test_good_file_read_byte_for_byte(self):
        f = self.d / "arm.weir"
        f.write_bytes(GOOD)
        self.assertEqual(model.read_weir_from(f), GOOD)

    def test_malformed_refused(self):
        for bad in (
            b"",
            b"dam\n2 4\n0 0 1.7 0.6\n",
            b"dam\n1 3\n0 0 1.7\n",
            b"dam\nx 4\n",
        ):
            f = self.d / "bad.weir"
            f.write_bytes(bad)
            with self.assertRaises(SystemExit, msg=bad):
                model.read_weir_from(f)
        with self.assertRaises(SystemExit):
            model.read_weir_from(self.d / "missing.weir")

    def test_lands_after_the_write_through_restore(self):
        """The arm's bytes replace the captured template bytes before sf.write(), so
        restore_weir (after the write) puts the ARM's file down as a new inode."""
        src = inspect.getsource(model.finalize)
        i_read = src.index("_weir_bytes = _read_weir(model_dir)")
        i_arm = src.index("_weir_bytes = read_weir_from(weir_from)")
        i_write = src.index("sf.write()", i_arm)
        self.assertLess(i_read, i_arm)
        self.assertLess(i_arm, i_write)
        staged = self.d / "sfincs.weir"
        staged.write_bytes(b"template\n1 4\n0 0 9 0.6\n")
        f = self.d / "arm.weir"
        f.write_bytes(GOOD)
        self.assertTrue(model.restore_weir(self.d, model.read_weir_from(f)))
        self.assertEqual(staged.read_bytes(), GOOD)

    def test_label_names_the_staged_polylines(self):
        self.assertEqual(provenance.weir_label(self.d), "none")
        (self.d / "sfincs.weir").write_bytes(GOOD)
        lab = provenance.weir_label(self.d)
        self.assertTrue(lab.startswith("md5:"))
        self.assertTrue(lab.endswith(" dam_a sill_b"))


if __name__ == "__main__":
    unittest.main()
