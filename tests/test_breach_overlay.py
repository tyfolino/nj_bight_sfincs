"""``scripts/build_breach_overlay_v4.py``: the breach polygons → overlay values.

Pins the rules the two breach arms rest on: the Wreck polygon carries ONE stated value,
the Mantoloking polygons carry the post-storm surface (its holes stay NoData, so the bed
is kept there), everything else is NoData; the variant key spells the value in cm; and
the lowering report counts only pixels where ``min(bed, overlay)`` actually moves.
Synthetic arrays only; no raster is read.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

from nj_sfincs.config import ROOT


def _load():
    spec = importlib.util.spec_from_file_location(
        "build_breach_overlay_v4", ROOT / "scripts" / "build_breach_overlay_v4.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


B = _load()


class TestBreachOverlay(unittest.TestCase):
    def test_variant_tag(self):
        self.assertEqual(B.variant_tag(0.0), "0")
        self.assertEqual(B.variant_tag(1.65), "165")

    def test_load_polygons_named_vertices(self):
        txt = (
            "# comment\npolygon,name,lon,lat\n"
            "wreck_a,w1,0,0\nwreck_a,w2,1,0\nwreck_a,w3,1,1\n"
            "manto_a,m1,5,5\nmanto_a,m2,6,5\nmanto_a,m3,6,6\nmanto_a,m4,5,6\n"
        )
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "p.csv"
            p.write_text(txt)
            polys = B.load_polygons(p)
            self.assertEqual(list(polys), ["wreck_a", "manto_a"])
            self.assertEqual(
                list(polys["wreck_a"].exterior.coords)[:3], [(0, 0), (1, 0), (1, 1)]
            )
            p.write_text("polygon,name,lon,lat\nx,a,0,0\nx,b,1,1\nx,c,1,0\nx,d,0,1\n")
            with self.assertRaises(SystemExit):  # a bow-tie ring
                B.load_polygons(p)

    def test_paint(self):
        m_w = np.zeros((3, 4), bool)
        m_w[0, :2] = True
        m_m = np.zeros((3, 4), bool)
        m_m[2, :] = True
        post = np.arange(12, dtype="float32").reshape(3, 4)
        post[2, 3] = np.nan  # a lidar hole
        ov = B.paint((3, 4), {"wreck_a": m_w, "manto_a": m_m}, 1.65, post)
        np.testing.assert_allclose(ov[0, :2], [1.65, 1.65], rtol=1e-6)
        np.testing.assert_array_equal(ov[2, :3], [8, 9, 10])
        self.assertTrue(np.isnan(ov[2, 3]))
        self.assertTrue(np.isnan(ov[1]).all() and np.isnan(ov[0, 2:]).all())
        with self.assertRaises(SystemExit):
            B.paint((3, 4), {"deal_a": m_w}, 0.0, post)

    def test_lowering_counts_only_what_min_moves(self):
        ins = np.ones((1, 4), bool)
        ins[0, 3] = False
        ov = np.array([[0.0, 0.0, 0.0, 0.0]], dtype="float32")
        bed = np.array([[2.0, -1.0, 0.5, 9.0]], dtype="float32")
        r = B.lowering(ov, bed, ins, 9.0)
        self.assertEqual(r["lowered_m2"], 18.0)  # 2.0 and 0.5; -1.0 already lower
        self.assertEqual(r["already_lower_m2"], 9.0)
        self.assertEqual(r["lowered_gt1m_m2"], 9.0)
        self.assertAlmostEqual(r["drop_mean"], 1.25)
        self.assertEqual(r["drop_max"], 2.0)
        self.assertEqual(r["volume_removed_m3"], round(2.5 * 9))

    def test_lowered_union_is_what_min_changes_in_any_variant(self):
        bed = np.array([[2.0, 1.0, -1.0, np.nan, 5.0]], dtype="float32")
        nan = np.nan
        ov0 = np.array([[0.0, 0.0, 0.0, 0.0, nan]], dtype="float32")
        ov165 = np.array([[1.65, 1.65, 1.65, nan, nan]], dtype="float32")
        np.testing.assert_array_equal(
            B.lowered_union([ov165], bed), [[True, False, False, False, False]]
        )
        # 1.0 is lowered only by the 0.0 variant; -1.0 by neither; a NaN bed takes
        # the overlay (as :min paints it); NoData overlay never counts
        np.testing.assert_array_equal(
            B.lowered_union([ov0, ov165], bed), [[True, True, False, True, False]]
        )


if __name__ == "__main__":
    unittest.main()
