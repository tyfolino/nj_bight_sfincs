"""The run gallery (``nj_sfincs/gallery.py``) and its site (``scripts/publish_gallery.py``).

Pins: the flag logic (warn, never gate — a flag for every condition the user named), the
restart-history parse, the manifest shape and figure order, the exact quadtree face
lookup the maps are painted with, the mean-ground wet mask, and that the publisher writes
an index, an arm page per arm and a compare page from synthetic galleries. No run dir,
no raster, no heavy data.
"""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from nj_sfincs import gallery as G

ROOT = Path(__file__).resolve().parents[1]

CLEAN = {
    "audit_whole": True,
    "sealed": True,
    "waves_on": True,
    "rain_on": True,
    "resumes": 0,
    "soil_reset": False,
    "engine_seed": "fixed",
    "engine": "bin:x@1234",
    "snapwave_direction": "imposed",
    "extent_admissible": True,
    "has_metrics_row": True,
    "hwm_n_scored": 110,
    "ref_hwm_n_scored": 110,
    "ref_arm": "naccs-premier",
    "floodmap_fresh": True,
}


def codes(facts):
    return {f["code"]: f["level"] for f in G.compute_flags({**CLEAN, **facts})}


class TestFlags(unittest.TestCase):
    def test_clean_run_has_no_warning(self):
        self.assertEqual(codes({}), {})

    def test_resumed_waves_on_is_a_caution(self):
        self.assertEqual(codes({"resumes": 2})["resumed_waves_on"], "caution")

    def test_resumed_waves_off_is_only_info(self):
        c = codes({"resumes": 1, "waves_on": False, "extent_admissible": False})
        self.assertEqual(c["resumed"], "info")
        self.assertNotIn("resumed_waves_on", c)

    def test_soil_reset_on_a_rain_arm(self):
        self.assertEqual(codes({"soil_reset": True})["soil_reset"], "caution")
        self.assertNotIn("soil_reset", codes({"soil_reset": True, "rain_on": False}))

    def test_unseeded_engine(self):
        self.assertIn("unseeded_engine", codes({"engine_seed": "os-random"}))
        self.assertIn("unseeded_engine", codes({"engine_seed": "os-random:wavemaker"}))
        self.assertNotIn("unseeded_engine", codes({"engine_seed": "n/a:no-snapwave"}))

    def test_waves_off_extent_flagged_not_hidden(self):
        c = codes({"extent_admissible": False, "waves_on": False})
        self.assertEqual(c["waves_off_extent"], "caution")

    def test_audit_not_whole_is_serious(self):
        c = codes({"audit_whole": False, "audit_problems": ["zsmax all fill"]})
        self.assertEqual(c["audit_not_whole"], "serious")
        self.assertEqual(codes({"audit_whole": None})["no_output"], "serious")

    def test_other_guards(self):
        self.assertEqual(codes({"sealed": False})["not_sealed"], "serious")
        self.assertEqual(
            codes({"snapwave_direction": "wind"})["snapwave_wind_direction"], "serious"
        )
        self.assertIn("hwm_count_mismatch", codes({"hwm_n_scored": 94}))
        self.assertIn("no_metrics_row", codes({"has_metrics_row": False}))
        self.assertIn("floodmap_stale", codes({"floodmap_fresh": False}))

    def test_every_flag_has_text(self):
        facts = {
            "audit_whole": False,
            "resumes": 1,
            "soil_reset": True,
            "engine_seed": "os-random",
            "extent_admissible": False,
        }
        for f in G.compute_flags({**CLEAN, **facts}):
            self.assertIn(f["level"], ("serious", "caution", "info"))
            self.assertTrue(f["text"])


class TestRestartHistory(unittest.TestCase):
    TEXT = (
        "2026-10-09 04:18:43 resume from sfincs.20121029.120000.rst: segment seg00 "
        "retired (started 2012-10-28 00:00)\n"
        "  ⚠️ cna infiltration: soil state RESET at 2012-10-29 12:00 (not in the "
        "restart file) — over-infiltrates if it rained after this\n"
        "2026-10-09 09:50:27 finish: {'segments': 1}\n"
    )

    def test_parse(self):
        r = G.parse_restart_history(self.TEXT)
        self.assertEqual(r["resumes"], 1)
        self.assertEqual(r["resumed_from"], ["sfincs.20121029.120000.rst"])
        self.assertTrue(r["soil_reset"])
        self.assertTrue(r["finished"])

    def test_uninterrupted(self):
        r = G.parse_restart_history("2026-10-09 01:33:59 finish: {'segments': 0}\n")
        self.assertEqual((r["resumes"], r["soil_reset"]), (0, False))
        self.assertEqual(G.parse_restart_history("")["resumes"], 0)


class TestManifest(unittest.TestCase):
    def test_shape_and_order(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            (out / "zsmax.png").write_bytes(b"png")
            (out / "motf.png").write_bytes(b"png")
            entries = {
                "motf": {"caption": "m", "selfcheck": {"reproduces_row_4dp": False}},
                "zsmax": {"caption": "z"},
                "dzsmax": {"skipped": "this IS the reference arm"},
                "hm0": {"error": "KeyError: hm0"},
            }
            old = {"gauges": {"key": "gauges", "title": "g", "file": "gauges.png"}}
            m = G.assemble_manifest(
                "v4_refreeze",
                "naccs-premier",
                "naccs-premier",
                {"labels": {}},
                CLEAN,
                entries,
                {"hwm_n_scored": np.int64(110)},
                out,
                old=old,
                windows=[("domain", (0, 1, 0, 1))],
            )
        json.dumps(m)  # serialisable as written
        keys = [f["key"] for f in m["figures"]]
        order = [k for k, _ in G.FIGURES]
        self.assertEqual(keys, [k for k in order if k in keys])
        self.assertEqual(set(keys), {"zsmax", "dzsmax", "motf", "gauges", "hm0"})
        by = {f["key"]: f for f in m["figures"]}
        self.assertEqual(by["zsmax"]["file"], "zsmax.png")
        self.assertNotIn("file", by["dzsmax"])
        self.assertNotIn("file", by["hm0"])
        self.assertEqual(by["gauges"]["file"], "gauges.png")  # carried forward
        codes_ = {f["code"] for f in m["flags"]}
        self.assertIn("selfcheck_motf", codes_)
        self.assertIn("figure_failed_hm0", codes_)
        for k in (
            "schema",
            "domain",
            "arm",
            "reference_arm",
            "card",
            "flags",
            "figures",
            "metrics_row",
            "scales",
            "windows",
            "peak_rss_gb",
        ):
            self.assertIn(k, m)
        self.assertEqual(m["metrics_row"]["hwm_n_scored"], 110)

    def test_headline_carries_the_measure(self):
        h = G.headline(
            {
                "hwm_estimator": "median",
                "hwm_radius_m": 50.0,
                "hwm_bias_scored_m": float("nan"),
                "motf_csi": 0.78,
            }
        )
        self.assertEqual(h["hwm_estimator"], "median")
        self.assertIsNone(h["hwm_bias_scored_m"])


@mock.patch.dict(os.environ, {"NJ_DOMAIN": "v4_refreeze"})
class TestWindows(unittest.TestCase):
    def test_domain_first_then_the_fixed_zooms(self):
        from nj_sfincs import domain

        for name in ("v3", "v4_refreeze"):
            dom = domain.DOMAINS[name]
            w = G.gallery_windows(dom)
            self.assertEqual(w[0][0], "domain")
            want = dom.gallery_windows or tuple(
                k for k, v in dom.map_windows.items() if v is not None
            )
            self.assertEqual([n for n, _ in w[1:]], list(want))
            for _, (x0, x1, y0, y1) in w:
                self.assertLess(x0, x1)
                self.assertLess(y0, y1)


def _toy_run(d: Path, rotation: float = 0.0) -> None:
    """A 2-level quadtree: one 200 m face + four 100 m faces, on a rotated frame."""
    import xarray as xr

    th = np.deg2rad(rotation)
    x0, y0 = 1000.0, 2000.0

    def xy(u, v):
        return x0 + u * np.cos(th) - v * np.sin(th), y0 + u * np.sin(th) + v * np.cos(
            th
        )

    squares = [(0, 0, 200)] + [(200 + i, j, 100) for i in (0, 100) for j in (0, 100)]
    nodes, faces = [], []
    for u, v, s in squares:
        k = len(nodes)
        nodes += [xy(u, v), xy(u + s, v), xy(u + s, v + s), xy(u, v + s)]
        faces.append([k + 1, k + 2, k + 3, k + 4])  # 1-based like SFINCS
    nodes = np.array(nodes)
    n = len(faces)
    zs = np.array([[1.0, 2.0, 3.0, 4.0, -99999.0]], "float32")
    xr.Dataset(
        {
            "mesh2d_node_x": ("nmesh2d_node", nodes[:, 0]),
            "mesh2d_node_y": ("nmesh2d_node", nodes[:, 1]),
            "mesh2d_face_nodes": (
                ("nmesh2d_face", "max_nmesh2d_face_nodes"),
                np.array(faces, "int32"),
            ),
            "zb": ("nmesh2d_face", np.array([0.5, 0.0, 2.95, 0.0, 0.0], "float32")),
            "msk": ("nmesh2d_face", np.array([1, 1, 1, 0, 1], "int32")),
            "zsmax": (("timemax", "nmesh2d_face"), zs),
        }
    ).to_netcdf(d / "sfincs_map.nc")
    (d / "sfincs.inp").write_text(f"x0 = {x0}\ny0 = {y0}\nrotation = {rotation}\n")
    assert n == 5


class TestFaces(unittest.TestCase):
    def check(self, rotation):
        with tempfile.TemporaryDirectory() as d:
            _toy_run(Path(d), rotation)
            F = G.Faces(Path(d))
        th = np.deg2rad(rotation)
        # pixel centres at known (u, v) → expected face
        cases = [
            ((50, 50), 0),
            ((150, 190), 0),
            ((250, 50), 1),
            ((250, 150), 2),
            ((350, 50), 3),
            ((350, 150), 4),
            ((450, 50), -1),
            ((-10, 10), -1),
        ]
        for (u, v), want in cases:
            x = 1000.0 + u * np.cos(th) - v * np.sin(th)
            y = 2000.0 + u * np.sin(th) + v * np.cos(th)
            pm = F.pixel_map((x - 0.5, x + 0.5, y - 0.5, y + 0.5), (1, 1))
            self.assertEqual(int(pm[0, 0]), want, f"rotation {rotation} at {(u, v)}")
        return F

    def test_lookup_north_up(self):
        self.check(0.0)

    def test_lookup_rotated(self):
        """v3's frame is rotated 359.183° (CLAUDE.md §5); pixels go through the frame."""
        self.check(359.183)
        self.check(30.0)

    def test_wet_mask_falls_back_to_zb_and_drops_fill(self):
        with tempfile.TemporaryDirectory() as d:
            _toy_run(Path(d))
            F = G.Faces(Path(d))
        self.assertIsNone(F.zmean)  # no sfincs_subgrid.nc in the toy
        wet = G.wet_faces(F)
        # face 2: 3.0 vs zb 2.95 (< 0.10 above); face 3 inactive; face 4 fill
        self.assertEqual(wet.tolist(), [True, True, False, False, False])
        F.zmean = np.array([0.95, 1.95, 0.0, 0.0, 0.0], "float32")
        self.assertEqual(G.wet_faces(F).tolist(), [False, False, True, False, False])


def _load_publish():
    spec = importlib.util.spec_from_file_location(
        "publish_gallery", ROOT / "scripts" / "publish_gallery.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestPublish(unittest.TestCase):
    def test_site_from_synthetic_galleries(self):
        pub = _load_publish()
        with tempfile.TemporaryDirectory() as d:
            exp, site = Path(d) / "experiments", Path(d) / "site"
            dom = exp / "v4_refreeze"
            arms = ("naccs-premier", "naccs-nowaves+rain-off+slr-2m")
            (dom).mkdir(parents=True)
            (dom / "metrics.csv").write_text(
                ",hwm_estimator,hwm_radius_m,hwm_n_scored,hwm_rmse_scored_m,"
                "hwm_bias_scored_m,motf_csi,motf_km2_excluded_boxes,extent_admissible,"
                "engine_seed\n"
                f"{arms[0]},median,50.0,110,0.436,-0.110,0.780,2413.6,True,os-random\n"
                f"{arms[1]},median,50.0,110,0.500,-0.200,0.700,2413.6,False,"
                "n/a:no-snapwave\n"
                "no-gallery-arm,median,50.0,110,0.6,0.1,0.6,2413.6,True,fixed\n"
            )
            for arm in arms:
                g = dom / arm / "gallery"
                g.mkdir(parents=True)
                (g / "zsmax.png").write_bytes(b"\x89PNG fake")
                man = G.assemble_manifest(
                    "v4_refreeze",
                    arm,
                    "naccs-premier",
                    {
                        "labels": {"engine_seed": "fixed"},
                        "fingerprint": {"sha": "378014e154b4ff41"},
                        "config": {"waves_on": arm == arms[0]},
                    },
                    CLEAN,
                    {"zsmax": {"caption": "peak water level"}},
                    {"hwm_n_scored": 110},
                    g,
                    windows=[("domain", (0, 1, 0, 1))],
                )
                (g / "manifest.json").write_text(json.dumps(man))
            # a stale figure in the site must be removed on re-publish
            stale = site / "v4_refreeze" / pub.slug(arms[0]) / "old.png"
            stale.parent.mkdir(parents=True)
            stale.write_bytes(b"x")
            with (
                mock.patch("shutil.which", return_value=None),
                mock.patch("subprocess.run"),
            ):
                pub.main(
                    [
                        "--site",
                        str(site),
                        "--exp-root",
                        str(exp),
                        "--domains",
                        "v4_refreeze",
                    ]
                )
            self.assertTrue((site / "index.html").is_file())
            self.assertTrue((site / ".nojekyll").is_file())
            ddir = site / "v4_refreeze"
            idx = (ddir / "index.html").read_text()
            for arm in (*arms, "no-gallery-arm"):
                self.assertIn(arm, idx)
                self.assertTrue((ddir / pub.slug(arm) / "index.html").is_file())
            self.assertIn("no_gallery", idx)
            self.assertIn("Preliminary research diagnostics", idx)
            self.assertIn("median · 50 m", idx)
            self.assertTrue((ddir / pub.slug(arms[1]) / "zsmax.png").is_file())
            self.assertFalse(stale.exists())
            cmp_ = (ddir / "compare.html").read_text()
            self.assertIn('id="armA"', cmp_)
            self.assertIn('id="armB"', cmp_)
            js = (ddir / "data.js").read_text()
            prefix = "window.GALLERY_DATA = "
            self.assertTrue(js.startswith(prefix))
            data = json.loads(js[len(prefix) :].rstrip().rstrip(";"))
            self.assertEqual(set(data["arms"]), {*arms, "no-gallery-arm"})
            self.assertEqual(data["arms"][arms[1]]["figures"][0]["file"], "zsmax.png")
            self.assertEqual(data["fig_order"][0], "zsmax")
            self.assertTrue((site / "assets" / "compare.js").is_file())
            arm_html = (ddir / pub.slug(arms[0]) / "index.html").read_text()
            self.assertIn("estimator median", arm_html)

    def test_slug_is_path_safe_and_distinct(self):
        pub = _load_publish()
        self.assertEqual(pub.slug("a+b-c.d_e"), "a_b-c.d_e")
        self.assertNotIn("+", pub.slug("naccs-nowaves+rain-off+slr-2m"))


if __name__ == "__main__":
    unittest.main()
