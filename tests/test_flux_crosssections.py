"""Which cross-section file a staged arm gets (``Domain.flux_crosssections``, 2026-11-14).

nj2 adds sections just inside its two forced cuts and across the Narrows and the KvK; every
other domain must keep staging the one shared file, byte for byte, so no existing run changes.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from nj_sfincs import domain as D
from nj_sfincs import model

SHARED = D.DATA / "flux_crosssections.crs"


def read_crs(path: Path) -> dict[str, list[tuple[float, float]]]:
    lines = [ln.split() for ln in Path(path).read_text().splitlines() if ln.strip()]
    out, i = {}, 0
    while i < len(lines):
        name, n = lines[i][0], int(lines[i + 1][0])
        out[name] = [(float(x), float(y)) for x, y in lines[i + 2 : i + 2 + n]]
        i += 2 + n
    return out


class _Env:
    def __init__(self, name):
        self.name = name

    def __enter__(self):
        self.saved = os.environ.get("NJ_DOMAIN")
        if self.name is None:
            os.environ.pop("NJ_DOMAIN", None)
        else:
            os.environ["NJ_DOMAIN"] = self.name

    def __exit__(self, *a):
        if self.saved is None:
            os.environ.pop("NJ_DOMAIN", None)
        else:
            os.environ["NJ_DOMAIN"] = self.saved


class TestDomainField(unittest.TestCase):
    def test_every_pre_nj2_domain_keeps_the_shared_file(self):
        for name, dom in D.DOMAINS.items():
            if name.startswith("nj2"):
                continue
            self.assertEqual(dom.flux_crosssections, SHARED, name)

    def test_nj2_file_is_a_superset_of_the_shared_one(self):
        f = D.DOMAINS["nj2"].flux_crosssections
        self.assertTrue(f.is_file(), f)
        self.assertTrue(
            f.read_text().startswith(SHARED.read_text().rstrip("\n") + "\n")
        )
        secs = read_crs(f)
        self.assertEqual(
            list(secs),
            ["barrier", "throat", "hudson_cut", "hell_gate_cut", "narrows", "kvk"],
        )
        self.assertEqual({k: secs[k] for k in ("barrier", "throat")}, read_crs(SHARED))

    def test_cut_sections_sit_inside_the_cuts_through_the_obs_points(self):
        from pyproj import Transformer
        from shapely.geometry import LineString, Point

        t = Transformer.from_crs(4326, 32618, always_xy=True)
        dom = D.DOMAINS["nj2"]
        secs = read_crs(dom.flux_crosssections)
        obs = {g.name: g for g in dom.obs_gauges}
        cuts = {a.name: a for a in dom.boundary_arms}
        for sec, gauge, arm in (
            ("hudson_cut", "bc_hudson_cut", "hudson"),
            ("hell_gate_cut", "bc_hell_gate", "hell_gate"),
        ):
            line = LineString(secs[sec])
            o = Point(t.transform(obs[gauge].lon, obs[gauge].lat))
            self.assertLess(line.distance(o), 15.0, sec)
            cut = LineString(cuts[arm].line)  # the arm's forced line, EPSG:32618
            self.assertFalse(line.intersects(cut), sec)
            self.assertAlmostEqual(line.distance(cut), 110.0, delta=5.0)


class TestStagingCopiesTheDomainFile(unittest.TestCase):
    def _staged(self, domain):
        with _Env(domain), tempfile.TemporaryDirectory() as d:
            (Path(d) / "sfincs.inp").write_text("mmax                 = 10\n")
            model.restore_diagnostics(Path(d))
            return (Path(d) / "sfincs.crs").read_bytes(), (
                Path(d) / "sfincs.inp"
            ).read_text()

    def test_v4_premier_domain_unchanged(self):
        crs, inp = self._staged("v4_refreeze_swz_v11")
        self.assertEqual(crs, SHARED.read_bytes())
        self.assertIn("crsfile", inp)

    def test_no_domain_set_uses_the_shared_file(self):
        crs, _ = self._staged(None)
        self.assertEqual(crs, SHARED.read_bytes())

    def test_nj2_gets_its_own(self):
        crs, _ = self._staged("nj2")
        self.assertEqual(crs, D.DOMAINS["nj2"].flux_crosssections.read_bytes())


if __name__ == "__main__":
    unittest.main()
