"""The SnapWave direction-bug reproducer writes a complete, self-consistent case."""

import importlib.util
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "make_snapwave_reproducer", ROOT / "scripts" / "make_snapwave_reproducer.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestReproducerCase(unittest.TestCase):
    def test_bed_is_a_plane_from_deep_to_dry(self):
        m = _load()
        y0, y1 = m.Y0, m.Y0 + m.NY * m.DX
        self.assertAlmostEqual(m._bed(np.array([m.X0]), np.array([y0]))[0], m.Z_OFFSHORE)
        self.assertAlmostEqual(m._bed(np.array([m.X0]), np.array([y1]))[0], m.Z_BEACH)
        self.assertLess(m.Z_OFFSHORE, -10.0)  # deep enough that the swell is not breaking
        self.assertGreater(m.Z_BEACH, 0.0)  # and there is dry land to stop it

    def test_swell_and_wind_are_far_apart(self):
        """The case only discriminates if the two directions differ by a lot more than
        one directional bin; 135° is unmistakable at dtheta 10."""
        m = _load()
        self.assertGreaterEqual(abs(m.WD - m.WIND_FROM), 90.0)

    def test_forcing_writes_every_file_and_the_wave_keys(self):
        m = _load()
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "sfincs.inp").write_text(
                "qtrfile              = sfincs.nc\n"
                "tref                 = 19990101 000000\n"  # must be replaced
                "sbgfile              = sfincs_subgrid.nc\n"  # must be dropped (no subgrid)
                "alpha                = 0.5\n"
            )
            pts = np.array([[m.X0 + 100.0, m.Y0 + 50.0], [m.X0 + 5000.0, m.Y0 + 50.0]])
            t = np.array([0.0, float(m.DURATION_S)])
            m._write_forcing(d, pts, t, wind=1)
            for fn in (
                "snapwave.bnd", "snapwave.bhs", "snapwave.btp", "snapwave.bwd",
                "snapwave.bds", "sfincs.bnd", "sfincs.bzs", "sfincs.wnd",
            ):
                self.assertTrue((d / fn).exists(), fn)
            inp = {
                ln.split("=")[0].strip(): ln.split("=", 1)[1].strip()
                for ln in (d / "sfincs.inp").read_text().splitlines()
                if "=" in ln
            }
            self.assertEqual(inp["snapwave"], "1")
            self.assertEqual(inp["snapwave_wind"], "1")
            self.assertEqual(inp["snapwave_sector"], "360")
            self.assertEqual(inp["storewavdir"], "1")
            self.assertEqual(inp["tref"], m.TREF)
            self.assertEqual(inp["qtrfile"], "sfincs.nc")
            self.assertNotIn("sbgfile", inp)
            self.assertEqual(inp["alpha"], "0.5")  # untouched keys survive
            bwd = np.loadtxt(d / "snapwave.bwd")
            self.assertEqual(bwd.shape, (2, 1 + len(pts)))
            self.assertTrue(np.all(bwd[:, 1:] == m.WD))
            wnd = np.loadtxt(d / "sfincs.wnd")
            self.assertTrue(np.all(wnd[:, 1] == m.WIND_SPEED))
            self.assertTrue(np.all(wnd[:, 2] == m.WIND_FROM))


if __name__ == "__main__":
    unittest.main()
