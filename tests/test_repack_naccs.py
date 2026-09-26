"""The NACCS repack may replace an H5-converted member with the webtool's own CSV only
when the two carry the same values; any real disagreement must still abort."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from repack_naccs_zips import _values_agree  # noqa: E402

HEAD = b"Save Point ID,Storm Name,Water Elevation\nSP,SN,ET00\n-,-,m\n"
WEBTOOL = HEAD + b'5347,"Sandy",1.2345678901\n5347,"Sandy",-0.5\n' + b"\x00" * 64
CONVERTED = HEAD + b'5347,"Sandy",1.23456789010000004\n5347,"Sandy",-0.50\n'


class ValuesAgree(unittest.TestCase):
    def test_formatting_and_nul_padding_agree(self):
        self.assertTrue(_values_agree(WEBTOOL, CONVERTED))

    def test_changed_value_disagrees(self):
        self.assertFalse(_values_agree(WEBTOOL, CONVERTED.replace(b"-0.50", b"-0.51")))

    def test_changed_text_disagrees(self):
        self.assertFalse(_values_agree(WEBTOOL, CONVERTED.replace(b"Sandy", b"Irene")))

    def test_row_count_disagrees(self):
        self.assertFalse(_values_agree(WEBTOOL, CONVERTED + b'5347,"Sandy",0.1\n'))


if __name__ == "__main__":
    unittest.main()
