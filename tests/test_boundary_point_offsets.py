"""``Experiment.boundary_point_offsets`` (2026-11-24): a per-SUPPORT-POINT constant on the forced water level.

Uses: per-gauge SLR (logs/slr_spatial_2026-11-24/) and the pre-storm diagnostic that ``boundary_arm_offsets`` refused
(logs/csi_dip_design_2026-11-22/README.md). Points are matched by COORDINATE: the staged file's ``stations`` is only
0..n-1, and Sandy's / Irene's NACCS lines have 244 / 240 points.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import xarray as xr
from pyproj import CRS, Transformer

from nj_sfincs import boundary_points as bp
from nj_sfincs.config import BoundaryPointOffsets, Experiment

UTM = CRS.from_epsg(32618)
# four support points ~10 km apart along the coast (UTM 18N)
PX = np.array([580_000.0, 582_000.0, 584_000.0, 586_000.0])
PY = np.array([4_440_000.0, 4_450_000.0, 4_460_000.0, 4_470_000.0])
NT = 7


def _write_bnd(d: Path) -> Path:
    """A boundary file in the staged layout (calm.write_mhhw_boundary's encoding)."""
    zs = np.linspace(0.0, 1.0, NT)[:, None] + np.arange(PX.size)[None, :] * 0.1
    ds = xr.Dataset(
        {
            "zs": (("time", "stations"), zs, {"coordinates": "spatial_ref x y"}),
            "spatial_ref": ((), 0, {"crs_wkt": UTM.to_wkt()}),
            "x": ("stations", PX),
            "y": ("stations", PY),
        },
        coords={
            "time": (
                "time",
                np.arange(NT) * 60.0,
                {"units": "minutes since 2012-10-28 00:00:00"},
            ),
            "stations": np.arange(PX.size),
        },
    )
    f = d / bp.BND_FILE
    fill = {"dtype": "float64", "_FillValue": np.nan}
    ds.to_netcdf(
        f,
        encoding={
            "time": fill,
            "zs": fill,
            "x": fill,
            "y": fill,
            "stations": {"dtype": "int64"},
        },
    )
    return f


def _lonlat(x, y):
    tr = Transformer.from_crs(UTM, 4326, always_xy=True)
    return tr.transform(x, y)


def _table(d: Path, offsets, order=None, extra=None, name="t.csv") -> Path:
    """lon / lat table, rows in ``order`` (default: REVERSED, so position never lines up)."""
    order = list(range(PX.size))[::-1] if order is None else order
    lon, lat = _lonlat(PX[order], PY[order])
    t = pd.DataFrame(
        {
            "sp": [1000 + i for i in order],
            "arm": "ocean",
            "lon": lon,
            "lat": lat,
            "off": np.asarray(offsets)[order],
        }
    )
    if extra is not None:
        t = pd.concat([t, pd.DataFrame([extra])], ignore_index=True)
    p = d / name
    t.to_csv(p, index=False)
    return p


def _zs(f: Path) -> np.ndarray:
    with xr.open_dataset(f, decode_times=False) as ds:
        return ds["zs"].values.copy()


class TestApply(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.d = Path(self._td.name)
        self.f = _write_bnd(self.d)
        (self.d / "provenance.txt").write_text("staged\n")
        self.before = _zs(self.f)

    def tearDown(self):
        self._td.cleanup()

    def test_offsets_land_on_their_points(self):
        off = np.array([0.0, -0.02, -0.06, 0.15])
        rec = bp.apply(self.d, BoundaryPointOffsets(str(_table(self.d, off)), "off"))
        np.testing.assert_allclose(
            _zs(self.f) - self.before, np.tile(off, (NT, 1)), atol=1e-12
        )
        self.assertEqual(rec["offsets_m"], off.tolist())
        self.assertEqual([p["sp"] for p in rec["points"]], [1000, 1001, 1002, 1003])
        self.assertTrue(rec["boundary_file_changed"])
        with xr.open_dataset(self.f, decode_times=False) as ds:  # nothing else moved
            np.testing.assert_array_equal(ds.x.values, PX)
            np.testing.assert_array_equal(ds.y.values, PY)
            np.testing.assert_array_equal(ds.time.values, np.arange(NT) * 60.0)
            self.assertIn("crs_wkt", ds.spatial_ref.attrs)

    def test_xy_table(self):
        t = pd.DataFrame(
            {"x": PX[::-1] + 1.0, "y": PY[::-1], "off": [4.0, 3.0, 2.0, 1.0]}
        )
        t.to_csv(self.d / "xy.csv", index=False)
        bp.apply(self.d, BoundaryPointOffsets(str(self.d / "xy.csv"), "off"))
        np.testing.assert_allclose((_zs(self.f) - self.before)[0], [1.0, 2.0, 3.0, 4.0])

    def test_zero_table_is_byte_identical(self):
        md5 = hashlib.md5(self.f.read_bytes()).hexdigest()
        rec = bp.apply(
            self.d, BoundaryPointOffsets(str(_table(self.d, np.zeros(4))), "off")
        )
        self.assertEqual(hashlib.md5(self.f.read_bytes()).hexdigest(), md5)
        self.assertFalse(rec["boundary_file_changed"])
        self.assertTrue((self.d / bp.META).exists())

    def test_sidecar_and_provenance(self):
        tab = _table(self.d, [0.1, 0.0, 0.0, -0.1])
        bp.apply(self.d, BoundaryPointOffsets(str(tab), "off"))
        rec = json.loads((self.d / bp.META).read_text())
        self.assertEqual(rec["column"], "off")
        self.assertEqual(rec["table_md5"], hashlib.md5(tab.read_bytes()).hexdigest())
        self.assertEqual(rec["n_points"], 4)
        self.assertEqual(rec["all"]["min_m"], -0.1)
        prov = (self.d / "provenance.txt").read_text()
        self.assertTrue(prov.startswith("staged\n"))
        self.assertIn("boundary_point_offsets = t.csv:off", prov)

    def test_count_mismatch_refuses(self):
        # a table for another line (one point more: Sandy's 244 on Irene's 240) ...
        far = dict(
            zip(("lon", "lat"), _lonlat(600_000.0, 4_500_000.0)), sp=9, arm="x", off=0.0
        )
        big = _table(self.d, np.zeros(4), extra=far, name="big.csv")
        with self.assertRaises(SystemExit) as cm:
            bp.apply(self.d, BoundaryPointOffsets(str(big), "off"))
        self.assertIn("5 rows", str(cm.exception))
        # ... unless declared a superset (every point still matched)
        rec = bp.apply(
            self.d, BoundaryPointOffsets(str(big), "off", extra_rows_ok=True)
        )
        self.assertEqual(rec["n_table_rows"], 5)
        # one point fewer: refused even with extra_rows_ok
        small = _table(self.d, np.zeros(4), order=[0, 1, 2], name="small.csv")
        for ok in (False, True):
            with self.assertRaises(SystemExit):
                bp.apply(
                    self.d, BoundaryPointOffsets(str(small), "off", extra_rows_ok=ok)
                )
        np.testing.assert_array_equal(_zs(self.f), self.before)

    def test_moved_point_refuses(self):
        t = pd.DataFrame({"x": PX + [0, 0, 50.0, 0], "y": PY, "off": 0.1})
        t.to_csv(self.d / "m.csv", index=False)
        with self.assertRaises(SystemExit) as cm:
            bp.apply(self.d, BoundaryPointOffsets(str(self.d / "m.csv"), "off"))
        self.assertIn("point 2", str(cm.exception))
        np.testing.assert_array_equal(_zs(self.f), self.before)

    def test_bad_tables_refuse(self):
        for off, col in (([0.0, np.nan, 0.0, 0.0], "off"), ([0.0] * 4, "nope")):
            with self.assertRaises(SystemExit):
                bp.apply(self.d, BoundaryPointOffsets(str(_table(self.d, off)), col))
        with self.assertRaises(SystemExit):
            bp.apply(self.d, BoundaryPointOffsets(str(self.d / "missing.csv"), "off"))


class _Arm:
    def __init__(self, name, ymin, ymax):
        self.name, self.btype, self.y = name, "waterlevel", (ymin, ymax)

    def contains(self, x, y):
        return (np.asarray(y) >= self.y[0]) & (np.asarray(y) < self.y[1])


class TestArms(unittest.TestCase):
    def test_point_arms_records_a_shared_point(self):
        cx = np.array([0.0, 100.0, 1000.0])
        arm = np.array(["a", "a", "b"], object)
        got = bp.point_arms(
            cx, np.zeros(3), arm, np.array([0.0, 100.0, 1100.0]), np.zeros(3)
        )
        self.assertEqual(got, [["a"], ["a", "b"], ["b"]])

    def test_staged_record_by_arm(self):
        from nj_sfincs import domain

        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _write_bnd(d)
            # one boundary cell at each support point; arm "south" below y 4,455,000, "north" above
            fx = np.r_[PX, 0.0]
            fy = np.r_[PY, 0.0]
            xr.Dataset(
                {
                    "mask": ("f", np.r_[np.full(4, 2), 1]),
                    "mesh2d_face_x": ("f", fx),
                    "mesh2d_face_y": ("f", fy),
                }
            ).to_netcdf(d / "sfincs.nc")
            act = domain.active
            domain.active = lambda: SimpleNamespace(
                boundary_arms=(
                    _Arm("south", 0.0, 4_455_000.0),
                    _Arm("north", 4_455_000.0, 9e9),
                )
            )
            try:
                rec = bp.apply(
                    d,
                    BoundaryPointOffsets(
                        str(_table(d, [0.0, -0.1, -0.2, -0.3])), "off"
                    ),
                )
            finally:
                domain.active = act
            self.assertEqual(rec["points"][0]["read_by_arms"], ["south"])
            self.assertEqual(
                rec["points"][1]["read_by_arms"], ["north", "south"]
            )  # the leak, recorded
            self.assertEqual(
                rec["by_arm"]["north"],
                {"n": 3, "min_m": -0.3, "max_m": -0.1, "mean_m": -0.2},
            )


class TestRegistry(unittest.TestCase):
    def test_field_default_and_repr(self):
        f = {x.name: x for x in dataclasses.fields(Experiment)}[
            "boundary_point_offsets"
        ]
        self.assertIsNone(f.default)
        self.assertFalse(f.repr)

    def test_pergauge_slr_arms(self):
        from nj_sfincs.experiments import EXPERIMENTS_BY_DOMAIN, SLR_POINT_TABLE_NJ2

        xs = EXPERIMENTS_BY_DOMAIN["nj2w_bed2026"]
        for tag, col in (
            ("stap2050", "delta_2050_m"),
            ("stap2100ssp245", "delta_2100_ssp245_m"),
        ):
            u = xs[f"tide-{tag}+weir-normalweather"]
            a = xs[f"tide-{tag}-pergauge+weir-normalweather"]
            changed = {
                f.name
                for f in dataclasses.fields(a)
                if f.name not in ("name", "description")
                and getattr(a, f.name) != getattr(u, f.name)
            }
            self.assertEqual(changed, {"boundary_point_offsets"})
            self.assertEqual(a.boundary_point_offsets.column, col)
            self.assertEqual(Path(a.boundary_point_offsets.table), SLR_POINT_TABLE_NJ2)
        t = pd.read_csv(SLR_POINT_TABLE_NJ2)
        self.assertEqual(len(t), 244)
        self.assertEqual(t["sp"].nunique(), 244)
        for col in ("delta_2050_m", "delta_2100_ssp245_m"):
            self.assertTrue(t[col].between(-0.1, 0.0).all(), col)
        # only these two arms carry a table
        for d, arms in EXPERIMENTS_BY_DOMAIN.items():
            for k, e in arms.items():
                if e.boundary_point_offsets is not None:
                    self.assertTrue(
                        k.endswith("-pergauge+weir-normalweather")
                        and d == "nj2w_bed2026",
                        (d, k),
                    )


class TestStagingOrder(unittest.TestCase):
    def test_applied_last_on_the_written_file(self):
        text = (
            Path(bp.__file__).resolve().parents[1] / "run_experiments.py"
        ).read_text()
        src = text[text.index("def prepare_experiment(") :]
        src = src[: src.index("\ndef ", 1)]
        i_fin = src.index("model.finalize(")
        i_calm = src.index("calm.apply(exp_dir, exp.calm)")
        i_cold = src.index("model.apply_cold_start(exp_dir, exp.cold_start)")
        i_pt = src.index("boundary_points.apply(exp_dir, exp.boundary_point_offsets)")
        self.assertLess(i_fin, i_pt)
        self.assertLess(i_calm, i_pt)
        self.assertLess(i_cold, i_pt)
        # calm + per-ARM offsets (applied in memory, then overwritten by calm) refuses before anything is removed
        i_guard = src.index("if exp.boundary_arm_offsets and exp.calm is not None:")
        self.assertLess(i_guard, src.index("shutil.rmtree(exp_dir)"))


if __name__ == "__main__":
    unittest.main()
