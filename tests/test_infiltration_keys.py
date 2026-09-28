"""``model._infiltration_keys``: SCS curve-number infiltration keys in ``sfincs.inp``.

Both traps it closes run clean in SFINCS v2.3.3 and give a wrong model: ``cna`` with
``storecumprcp = 0`` infiltrates EVERY drop of rain, and a water CN of 0 (S = 990 in)
makes rain on the bays vanish. Nothing here runs SFINCS.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import numpy as np
import xarray as xr

from nj_sfincs import domain, model

INP = (
    "tref                 = 20121028 000000\n"
    "qtrfile              = sfincs.nc\n"
    "storecumprcp         = 0\n"
    "infiltration_file    = infiltration.nc\n"
    "infiltration_type    = cna\n"
)


def _keys(text: str) -> dict[str, str]:
    return {
        k.strip(): v.strip()
        for k, v in (ln.split("=", 1) for ln in text.splitlines() if "=" in ln)
    }


class InfiltrationKeys(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _qtr(self, scs, mask) -> None:
        xr.Dataset(
            {
                "scs": ("mesh2d_nFaces", np.asarray(scs, float)),
                "mask": ("mesh2d_nFaces", np.asarray(mask, "uint8")),
            }
        ).to_netcdf(self.dir / "sfincs.nc")

    def test_off_strips_hydromts_orphan_keys_and_leaves_storecumprcp(self) -> None:
        k = _keys(model._infiltration_keys(INP, self.dir, on=False))
        self.assertNotIn("infiltration_file", k)
        self.assertNotIn("infiltration_type", k)
        self.assertEqual(k["storecumprcp"], "0")

    def test_on_points_at_the_qtrfile_and_forces_storecumprcp(self) -> None:
        self._qtr([0.0, 1.8, 4.3], [1, 1, 2])
        text = model._infiltration_keys(INP, self.dir, on=True)
        k = _keys(text)
        self.assertEqual(k["infiltration_file"], "sfincs.nc")
        self.assertEqual(k["infiltration_type"], "cna")
        self.assertEqual(k["storecumprcp"], "1")
        self.assertEqual(text.count("storecumprcp"), 1)

    def test_on_refuses_water_cn_1_on_an_active_face(self) -> None:
        self._qtr([990.0, 1.8], [1, 1])
        with self.assertRaises(SystemExit):
            model._infiltration_keys(INP, self.dir, on=True)

    def test_on_ignores_water_cn_1_on_inactive_faces(self) -> None:
        self._qtr([990.0, 1.8], [0, 1])
        k = _keys(model._infiltration_keys(INP, self.dir, on=True))
        self.assertEqual(k["infiltration_type"], "cna")


class InfiltrationIsADomainFact(unittest.TestCase):
    def test_only_v4_has_it_on(self) -> None:
        saved = os.environ.get("NJ_DOMAIN")
        try:
            for name, on in (
                ("v1_monmouth", False),
                ("v1_5_raritan", False),
                ("v3", False),
                ("v4", True),
            ):
                os.environ["NJ_DOMAIN"] = name
                self.assertEqual(domain.active().infiltration, on, name)
        finally:
            if saved is None:
                os.environ.pop("NJ_DOMAIN", None)
            else:
                os.environ["NJ_DOMAIN"] = saved


if __name__ == "__main__":
    unittest.main()
