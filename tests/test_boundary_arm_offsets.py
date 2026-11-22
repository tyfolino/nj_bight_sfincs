"""``Experiment.boundary_arm_offsets`` (2026-11-18): a constant on the support points that force ONE boundary arm.

First use: the Hell Gate forcing test on nj2w_bed2012 (logs/runs_2_0_followup_2026-11-18/). The points are picked by
the engine's rule (each ``mask==2`` cell reads its two nearest support points, sfincs_boundaries.f90), and a point
that also forces another arm is refused.
"""

from __future__ import annotations

import dataclasses
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import xarray as xr

from nj_sfincs import model
from nj_sfincs.config import Experiment

# two arms 10 km apart: "west" cells at x 0..100, "east" cells at x 10,000..10,100 (y = 0)
CX = np.array([0.0, 50.0, 100.0, 10_000.0, 10_050.0, 10_100.0])
CY = np.zeros(6)
ARM = np.array(["west"] * 3 + ["east"] * 3, object)
# support points: two on the west cut, one 300 m off it, two on the east cut, one far away
PX = np.array([10.0, 90.0, 400.0, 10_020.0, 10_080.0, 50_000.0])
PY = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])


class TestSupportPoints(unittest.TestCase):
    def test_default_is_empty(self):
        f = {x.name: x for x in dataclasses.fields(Experiment)}["boundary_arm_offsets"]
        self.assertEqual(f.default, ())

    def test_engine_two_nearest(self):
        self.assertEqual(
            model.boundary_arm_support_points(CX, CY, ARM, PX, PY, "west").tolist(),
            [0, 1],
        )
        self.assertEqual(
            model.boundary_arm_support_points(CX, CY, ARM, PX, PY, "east").tolist(),
            [3, 4],
        )

    def test_shared_point_refused(self):
        # only one point near the east cut: its cells' 2nd nearest is a west point -> shared
        px = np.array([10.0, 90.0, 10_050.0])
        py = np.zeros(3)
        with self.assertRaises(SystemExit):
            model.boundary_arm_support_points(CX, CY, ARM, px, py, "east")
        with self.assertRaises(SystemExit):
            model.boundary_arm_support_points(CX, CY, ARM, px, py, "west")

    def test_unknown_arm_refused(self):
        with self.assertRaises(SystemExit):
            model.boundary_arm_support_points(CX, CY, ARM, PX, PY, "nowhere")


class _Arm:
    def __init__(self, name, xmin, xmax):
        self.name, self.btype, self.x = name, "waterlevel", (xmin, xmax)

    def contains(self, x, y):
        return (np.asarray(x) > self.x[0]) & (np.asarray(x) < self.x[1])


class TestApply(unittest.TestCase):
    def setUp(self):
        t = np.arange(5)
        self.bzs = np.tile(np.linspace(0.0, 1.0, 5)[:, None], (1, PX.size))
        wl = xr.Dataset(
            {"bzs": (("time", "index"), self.bzs.copy())},
            coords={
                "time": t,
                "index": np.arange(PX.size),
                "x": ("index", PX),
                "y": ("index", PY),
            },
        )
        # faces: the six boundary cells (mask 2) + two interior cells (mask 1)
        fx = np.r_[CX, 5_000.0, 6_000.0]
        fy = np.r_[CY, 1_000.0, 1_000.0]
        mask = np.r_[np.full(6, 2), 1, 1]
        self.sf = SimpleNamespace(
            water_level=SimpleNamespace(data=wl),
            quadtree_grid=SimpleNamespace(
                data={"mask": xr.DataArray(mask)},
            ),
        )
        self._face = model._face_xy
        model._face_xy = lambda sf: (fx, fy)
        self._active = model._domain.active
        model._domain.active = lambda: SimpleNamespace(
            name="toy",
            boundary_arms=(_Arm("west", -1, 500), _Arm("east", 9_000, 11_000)),
        )

    def tearDown(self):
        model._face_xy = self._face
        model._domain.active = self._active

    def test_offset_only_the_arm_points(self):
        rec = model.apply_boundary_arm_offsets(self.sf, (("east", -0.25),))
        got = self.sf.water_level.data["bzs"].values
        d = got - self.bzs
        np.testing.assert_allclose(d[:, [3, 4]], -0.25)
        np.testing.assert_allclose(d[:, [0, 1, 2, 5]], 0.0)
        self.assertEqual(rec[0]["points"], [3, 4])
        self.assertEqual(rec[0]["cells"], 3)
        self.assertAlmostEqual(rec[0]["mean_after_m"] - rec[0]["mean_before_m"], -0.25)

    def test_geometry_coords(self):
        """The staged in-memory form: a hydromt GeoDataset with shapely points, no x / y."""
        import shapely

        wl = self.sf.water_level.data.drop_vars(["x", "y"])
        wl = wl.assign_coords(geometry=("index", shapely.points(PX, PY)))
        self.sf.water_level.data = wl
        rec = model.apply_boundary_arm_offsets(self.sf, (("east", -0.25),))
        self.assertEqual(rec[0]["points"], [3, 4])
        d = self.sf.water_level.data["bzs"].values - self.bzs
        np.testing.assert_allclose(d[:, [3, 4]], -0.25)
        np.testing.assert_allclose(d[:, [0, 1, 2, 5]], 0.0)

    def test_empty_is_a_noop(self):
        self.assertEqual(model.apply_boundary_arm_offsets(self.sf, ()), [])
        np.testing.assert_array_equal(self.sf.water_level.data["bzs"].values, self.bzs)

    def test_bad_names_refused(self):
        for bad in ((("nowhere", 0.1),), (("east", 0.1), ("east", 0.2))):
            with self.assertRaises(SystemExit, msg=repr(bad)):
                model.apply_boundary_arm_offsets(self.sf, bad)

    def test_record(self):
        rec = model.apply_boundary_arm_offsets(self.sf, (("west", 0.1),))
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "provenance.txt").write_text("staged\n")
            model.record_boundary_arm_offsets(d, rec)
            self.assertEqual(
                json.loads((d / "boundary_arm_offsets.json").read_text())[0]["arm"],
                "west",
            )
            prov = (d / "provenance.txt").read_text()
            self.assertTrue(prov.startswith("staged\n"))
            self.assertIn("boundary_arm_offsets = west +0.100 m on pts [0, 1]", prov)


class TestStagingOrder(unittest.TestCase):
    def test_applied_after_the_swap_and_before_finalize(self):
        text = (
            Path(model.__file__).resolve().parents[1] / "run_experiments.py"
        ).read_text()
        src = text[text.index("def prepare_experiment(") :]
        src = src[: src.index("\ndef ", 1)]
        i_swap = src.index(
            "model.check_waterlevel_support(sf, expect=exp.n_waterlevel_support)"
        )
        i_off = src.index(
            "model.apply_boundary_arm_offsets(sf, exp.boundary_arm_offsets)"
        )
        i_fin = src.index("model.finalize(")
        i_diag = src.index("model.restore_diagnostics(exp_dir)")
        i_rec = src.index("model.record_boundary_arm_offsets(exp_dir, bnd_offsets)")
        self.assertLess(i_swap, i_off)
        self.assertLess(i_off, i_fin)
        self.assertLess(i_diag, i_rec)


if __name__ == "__main__":
    unittest.main()
