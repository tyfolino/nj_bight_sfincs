"""``finalize`` keeps ``sfincs.weir`` byte for byte (2026-10-07): hydromt's ``sf.write()``
re-emits it through float32 at one decimal (the Overpeck dam 1.74 → 1.70 m), so the bytes
read before the write are put back after it, as a new inode.
"""

from __future__ import annotations

import inspect
import os
import tempfile
import unittest
from pathlib import Path

from nj_sfincs import model

SRC = b"overpeck_tidal_dam_NJ00799\n1 4\n586000.0 4523000.8 1.74 0.6\n"
ROUNDED = b"overpeck_tidal_dam_NJ00799\n1 4\n   586000.0   4523001.0 1.7 0.6\n"


class TestRestoreWeir(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_restores_rounded_file(self):
        f = self.d / "sfincs.weir"
        f.write_bytes(SRC)
        data = model._read_weir(self.d)
        f.write_bytes(ROUNDED)
        self.assertTrue(model.restore_weir(self.d, data))
        self.assertEqual(f.read_bytes(), SRC)

    def test_new_inode_never_writes_through_a_link(self):
        f = self.d / "sfincs.weir"
        other = self.d / "other_run.weir"
        f.write_bytes(ROUNDED)
        os.link(f, other)
        model.restore_weir(self.d, SRC)
        self.assertEqual(f.read_bytes(), SRC)
        self.assertEqual(other.read_bytes(), ROUNDED)

    def test_identical_file_untouched(self):
        f = self.d / "sfincs.weir"
        f.write_bytes(SRC)
        ino = f.stat().st_ino
        self.assertFalse(model.restore_weir(self.d, SRC))
        self.assertEqual(f.stat().st_ino, ino)

    def test_no_weir_no_file(self):
        self.assertIsNone(model._read_weir(self.d))
        self.assertFalse(model.restore_weir(self.d, None))
        self.assertFalse((self.d / "sfincs.weir").exists())

    def test_finalize_reads_before_and_restores_after_the_write(self):
        src = inspect.getsource(model.finalize)
        i_read = src.index("_weir_bytes = _read_weir(model_dir)")
        i_write = src.index("sf.write()", i_read)
        i_restore = src.index("restore_weir(model_dir, _weir_bytes)")
        self.assertLess(i_read, i_write)
        self.assertLess(i_write, i_restore)


if __name__ == "__main__":
    unittest.main()
