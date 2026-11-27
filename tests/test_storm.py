"""``Experiment.storm`` (2026-11-24, Irene on Model 2.0.0): another storm on the template's domain.

Pinned here: the Irene arms differ from the 2.0 premier / its waves-off twin ONLY in the storm (and the Sandy
forcing fields the storm clears), declare 240 support points, and carry the Irene window; ``verify_staged`` refuses
a staged dir whose window is not the storm's, whose forcing does not cover it, or which still holds a template
(Sandy) forcing file; the scorer sees Irene's records, marks and peak floor, never Sandy's record facts. Nothing
here runs SFINCS or hydromt. The real-input checks skip when ``data/irene_2011`` is not reachable.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from dataclasses import fields, replace
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import xarray as xr

from nj_sfincs import domain, model, storm
from nj_sfincs.config import BaseConfig, Experiment, StormValidation, WaveConfig
from nj_sfincs.experiments import EXPERIMENTS_BY_DOMAIN
from nj_sfincs.validate import core, metrics

DOM = "nj2w_bed2012"
PREMIER = "p4-premier+struct-cohansey-checkvalve+weir-dikes-levees"
NOWAVES = "p4-nowaves+struct-cohansey-checkvalve+weir-dikes-levees"
IRENE = "p4-premier+storm-irene2011+struct-cohansey-checkvalve+weir-dikes-levees"
IRENE_NW = "p4-nowaves+storm-irene2011+struct-cohansey-checkvalve+weir-dikes-levees"
ST = storm.IRENE_2011


class _Env(unittest.TestCase):
    def setUp(self) -> None:
        self._saved = os.environ.get("NJ_DOMAIN")
        os.environ["NJ_DOMAIN"] = DOM

    def tearDown(self) -> None:
        if self._saved is None:
            os.environ.pop("NJ_DOMAIN", None)
        else:
            os.environ["NJ_DOMAIN"] = self._saved


class TestIreneArms(_Env):
    def test_registered_on_the_2012_bed_only(self):
        x = EXPERIMENTS_BY_DOMAIN[DOM]
        self.assertIn(IRENE, x)
        self.assertIn(IRENE_NW, x)
        for d, arms in EXPERIMENTS_BY_DOMAIN.items():
            if d != DOM:
                self.assertFalse([a for a in arms if "storm-irene" in a], d)

    def test_differs_from_its_base_only_in_the_storm(self):
        x = EXPERIMENTS_BY_DOMAIN[DOM]
        for arm, base in ((IRENE, PREMIER), (IRENE_NW, NOWAVES)):
            e, b = x[arm], x[base]
            diff = {
                f.name
                for f in fields(Experiment)
                if f.name not in ("name", "description")
                and getattr(e, f.name) != getattr(b, f.name)
            }
            self.assertEqual(
                diff,
                {
                    "storm",
                    "waterlevel_geodataset",
                    "meteo_from",
                    "n_waterlevel_support",
                },
                arm,
            )
            self.assertIs(e.storm, ST)
            self.assertIsNone(e.waterlevel_geodataset)
            self.assertIsNone(e.meteo_from)
            # the structures, bed and engine-facing physics are the premier's
            self.assertEqual(e.weir_from, b.weir_from)
            self.assertEqual(e.drn_from, b.drn_from)
            self.assertEqual(e.subgrid_from, b.subgrid_from)
            self.assertEqual(e.cnb_effective, b.cnb_effective)
            self.assertEqual(e.waves, b.waves)
            self.assertEqual(storm.conflicts(e), [])

    def test_240_support_points_are_declared(self):
        for arm in (IRENE, IRENE_NW):
            self.assertEqual(EXPERIMENTS_BY_DOMAIN[DOM][arm].n_waterlevel_support, 240)
        # the domain value is NOT relaxed for it
        self.assertEqual(EXPERIMENTS_BY_DOMAIN[DOM][PREMIER].n_waterlevel_support, 244)

    def test_the_declared_count_is_what_staging_asserts(self):
        def fake_sf(n):
            ds = xr.Dataset(
                {"bzs": (("time", "index"), np.zeros((2, n)))},
                coords={
                    "x": ("index", np.arange(n) * 1.0),
                    "y": ("index", np.zeros(n)),
                },
            )
            return SimpleNamespace(water_level=SimpleNamespace(data=ds))

        want = EXPERIMENTS_BY_DOMAIN[DOM][IRENE].n_waterlevel_support
        self.assertEqual(model.check_waterlevel_support(fake_sf(240), expect=want), 240)
        with self.assertRaises(RuntimeError):
            model.check_waterlevel_support(fake_sf(244), expect=want)

    def test_support_reference_is_the_premiers_boundary(self):
        # the template carries noaa_sandy_nj (3 gauges); the subset check must read the premier's NACCS set
        self.assertEqual(
            ST.support_reference,
            EXPERIMENTS_BY_DOMAIN[DOM][PREMIER].waterlevel_geodataset,
        )

    def test_window(self):
        t0, t1 = storm.window(ST)
        self.assertEqual(
            (t0, t1), (datetime(2011, 8, 25, 21), datetime(2011, 8, 29, 12))
        )
        self.assertEqual((t1 - t0).total_seconds() / 3600, 87)
        self.assertLessEqual(t1, datetime(2011, 8, 30))  # the NACCS record ends there
        b = storm.storm_base(BaseConfig(), ST)
        self.assertEqual((b.tref, b.tstart, b.tstop), (t0, t0, t1))
        self.assertEqual(
            BaseConfig().tstart, datetime(2012, 10, 28)
        )  # the template's stays Sandy

    def test_waves_take_the_storm_file(self):
        e = EXPERIMENTS_BY_DOMAIN[DOM][IRENE]
        w = storm.storm_waves(e.waves, ST)
        self.assertEqual(w.wave_point_dataset, Path(ST.wave_point_dataset))
        self.assertEqual(
            replace(w, wave_point_dataset=e.waves.wave_point_dataset), e.waves
        )
        nw = WaveConfig(use_waves=False)
        self.assertIs(storm.storm_waves(nw, ST), nw)

    def test_meteo_is_the_premiers_recipe(self):
        # the 2.0 premier = blend wind + ERA5 pressure (naccs_blend_p_era5); Irene must match it
        prem = EXPERIMENTS_BY_DOMAIN[DOM][PREMIER].meteo_from
        self.assertTrue(prem.name.endswith("_p_era5"))
        self.assertTrue(Path(ST.meteo_from).name.endswith("_p_era5"))

    def test_existing_reprs_unchanged(self):
        self.assertNotIn("storm=", repr(EXPERIMENTS_BY_DOMAIN[DOM][PREMIER]))

    def test_conflicts_are_refused(self):
        e = EXPERIMENTS_BY_DOMAIN[DOM][IRENE]
        self.assertIn("meteo_from", storm.conflicts(replace(e, meteo_from=Path("x"))))
        self.assertIn(
            "waterlevel_geodataset",
            storm.conflicts(replace(e, waterlevel_geodataset="naccs_sandy_nj2")),
        )
        self.assertTrue(
            storm.conflicts(replace(e, storm=replace(ST, precip_dataset=None)))
        )
        self.assertEqual(
            storm.conflicts(
                replace(e, rain=False, storm=replace(ST, precip_dataset=None))
            ),
            [],
        )
        self.assertTrue(
            storm.conflicts(replace(e, storm=replace(ST, wave_point_dataset=None)))
        )


class TestPoints(unittest.TestCase):
    def test_subset(self):
        old = np.array([[0.0, 0.0], [10.0, 0.0], [20.0, 0.0]])
        self.assertEqual(storm.unmatched(old[:2] + 0.5, old).tolist(), [])
        self.assertEqual(
            storm.unmatched(np.array([[0.0, 0.0], [5.0, 0.0]]), old).tolist(), [1]
        )


def _write_nc(path: Path, t0: str, t1: str, units: str, freq: str = "1h") -> None:
    t = pd.date_range(t0, t1, freq=freq)
    xr.Dataset(
        {"v": (("time",), np.arange(len(t), dtype=float))}, coords={"time": t}
    ).to_netcdf(path, encoding={"time": {"units": units, "dtype": "float64"}})


def _write_ascii(path: Path, t_end_s: float) -> None:
    t = np.arange(0.0, t_end_s + 1, 3600.0)
    np.savetxt(path, np.c_[t, np.ones((len(t), 2))], fmt="%11.1f")


class TestVerifyStaged(_Env):
    """A synthetic staged dir: the window, the coverage, and 'no template forcing file survives'."""

    def setUp(self) -> None:
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.d, self.tpl = root / "arm", root / "template"
        self.d.mkdir()
        self.tpl.mkdir()
        units = "minutes since 2011-08-25 21:00:00"
        for f in storm.NC_FORCING:
            _write_nc(self.d / f, "2011-08-25 21:00", "2011-08-29 12:00", units)
            _write_nc(
                self.tpl / f,
                "2012-10-28",
                "2012-10-31",
                "minutes since 2012-10-28 00:00:00",
            )
        # rivers padded a day each side, meteo from its own earlier origin
        _write_nc(
            self.d / "sfincs_netsrcdisfile.nc", "2011-08-25", "2011-08-30", units, "1D"
        )
        _write_nc(
            self.d / "sfincs_netamuv.nc",
            "2011-08-24",
            "2011-08-30",
            "minutes since 2011-08-24 00:00:00",
            "30min",
        )
        for f in storm.WAVE_FORCING:
            _write_ascii(self.d / f, 87 * 3600.0)
        (self.d / "sfincs.inp").write_text(
            "tref                 = 20110825 210000\n"
            "tstart               = 20110825 210000\n"
            "tstop                = 20110829 120000\n"
            "dtmaxout             = 21600.0\n"
            "dtrstout             = 21600.0\n"
            "snapwave             = 1\n"
            "netamprfile          = sfincs_netampr.nc\n"
        )
        (self.d / "sfincs.obs").write_text('   584004.7   4480052.1 "sandy_hook"\n')
        (self.d / storm.SIDECAR).write_text(
            json.dumps(
                {
                    "storm": ST.name,
                    "tstart": ST.tstart,
                    "tstop": ST.tstop,
                    "run_hours": 87.0,
                    "n_waterlevel_support": 240,
                    "n_inflows": 58,
                    "sources": {
                        "waterlevel": {"catalog": "naccs_irene_nj2"},
                        "discharge": {"catalog": "usgs_irene_discharge_nj2"},
                        "meteo": {"path": str(ST.meteo_from)},
                    },
                }
            )
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()
        super().tearDown()

    def test_a_clean_storm_dir_passes_and_gets_its_gauges(self):
        rec = storm.verify_staged(self.d, ST, template_dir=self.tpl)
        self.assertEqual(len(rec["obs_added"]), len(ST.validation.extra_gauges))
        names = [
            ln.split('"')[1] for ln in (self.d / "sfincs.obs").read_text().splitlines()
        ]
        self.assertEqual(names[0], "sandy_hook")
        self.assertEqual(len(names), 1 + len(ST.validation.extra_gauges))
        self.assertIn("storm = irene2011", (self.d / "provenance.txt").read_text())
        self.assertEqual(storm.label(self.d), "irene2011")
        self.assertIn("verified", storm.read_sidecar(self.d))

    def test_the_sandy_window_is_refused(self):
        inp = self.d / "sfincs.inp"
        inp.write_text(inp.read_text().replace("20110825 210000", "20121028 000000"))
        with self.assertRaisesRegex(SystemExit, "tref"):
            storm.verify_staged(self.d, ST, template_dir=self.tpl)

    def test_a_surviving_template_file_is_refused(self):
        f = "sfincs_netampr.nc"
        (self.d / f).write_bytes((self.tpl / f).read_bytes())
        with self.assertRaisesRegex(SystemExit, "byte-identical|covers"):
            storm.verify_staged(self.d, ST, template_dir=self.tpl)

    def test_identical_bytes_alone_are_refused(self):
        # same bytes, and those bytes DO cover the storm window: only the md5 rule can catch it
        f = "sfincs_netbndbzsbzifile.nc"
        (self.tpl / f).write_bytes((self.d / f).read_bytes())
        with self.assertRaisesRegex(SystemExit, "byte-identical"):
            storm.verify_staged(self.d, ST, template_dir=self.tpl)

    def test_sandy_dated_forcing_is_refused(self):
        _write_nc(
            self.d / "sfincs_netamp.nc",
            "2012-10-28",
            "2012-10-31",
            "minutes since 2011-08-25 21:00:00",
        )
        with self.assertRaisesRegex(SystemExit, "sfincs_netamp.nc covers"):
            storm.verify_staged(self.d, ST)

    def test_short_river_series_is_refused(self):
        _write_nc(
            self.d / "sfincs_netsrcdisfile.nc",
            "2011-08-26",
            "2011-08-29",
            "minutes since 2011-08-25 21:00:00",
            "1D",
        )
        with self.assertRaisesRegex(SystemExit, "netsrcdisfile.nc covers"):
            storm.verify_staged(self.d, ST)

    def test_short_wave_series_is_refused(self):
        _write_ascii(self.d / "snapwave.bhs", 72 * 3600.0)
        with self.assertRaisesRegex(SystemExit, "snapwave.bhs covers"):
            storm.verify_staged(self.d, ST)

    def test_rain_reindexed_to_nan_is_refused(self):
        # hydromt's meteo set() MERGES into the read-back Sandy field: the storm's rain reindexed onto
        # Sandy's clock is all NaN (caught by the 11-24 test staging; storm.apply_in_memory clears first)
        t = pd.date_range("2011-08-25 21:00", "2011-08-29 12:00", freq="1h")
        xr.Dataset(
            {"precip": (("time",), np.full(len(t), np.nan))}, coords={"time": t}
        ).to_netcdf(
            self.d / "sfincs_netampr.nc",
            encoding={
                "time": {
                    "units": "minutes since 2011-08-25 21:00:00",
                    "dtype": "float64",
                }
            },
        )
        with self.assertRaisesRegex(SystemExit, "no rain anywhere"):
            storm.verify_staged(self.d, ST)

    def test_missing_rain_is_refused(self):
        (self.d / "sfincs_netampr.nc").unlink()
        with self.assertRaisesRegex(SystemExit, "sfincs_netampr.nc is missing"):
            storm.verify_staged(self.d, ST)

    def test_no_sidecar_is_refused(self):
        (self.d / storm.SIDECAR).unlink()
        with self.assertRaisesRegex(SystemExit, "apply_in_memory"):
            storm.verify_staged(self.d, ST)

    def test_an_obs_name_clash_is_refused(self):
        g = ST.validation.extra_gauges[0]
        with self.assertRaisesRegex(SystemExit, "clashes"):
            storm.append_obs(self.d, (g, replace(g, name=g.name + "_x")), 32618)


class TestScoringView(_Env):
    def test_view_replaces_the_sandy_sets(self):
        dom = domain.active()
        view = storm.scoring_domain(ST)
        n_dom, n_extra = len(dom.obs_gauges), len(ST.validation.extra_gauges)
        self.assertEqual(len(view.obs_gauges), n_dom + n_extra)
        self.assertEqual(n_extra, 16)  # 15 STN sensors + Tacony-Palmyra
        for g in view.obs_gauges[:n_dom]:
            self.assertIsNone(g.record_ends)
            self.assertIsNone(g.published_peak)
            self.assertEqual(g.obs_offset_m, 0.0)
            self.assertFalse(g.survives_crest)
            if g.obs_file:
                self.assertTrue(g.obs_file.startswith("irene_2011/"), g.name)
        self.assertEqual(Path(view.hwm_geojson).name, "irene_hwms_nj2.geojson")
        # geography untouched
        self.assertEqual(view.name, dom.name)
        self.assertEqual(view.region, dom.region)
        self.assertEqual(view.boundary_arms, dom.boundary_arms)

    def test_only_sandy_sensor_files_are_left_unmapped(self):
        dom = domain.active()
        mapped = dict(ST.validation.obs_files)
        unmapped = {
            g.obs_file
            for g in dom.obs_gauges
            if g.obs_file and g.obs_file not in mapped
        }
        self.assertTrue(all("storm_tide" in f for f in unmapped), unmapped)

    def test_gauge_names_stay_unique_under_substring_matching(self):
        names = [g.name for g in storm.scoring_domain(ST).obs_gauges]
        self.assertEqual(len(names), len(set(names)))
        for n in names:
            clash = [m for m in names if m != n and n in m]
            self.assertEqual(clash, [], n)

    def test_scoring_view_is_scoped(self):
        dom = domain.active()
        view = storm.scoring_domain(ST)
        with domain.scoring_view(view):
            self.assertIs(domain.active(), view)
            self.assertTrue(
                str(metrics._hwm_path(Path("/D"))).endswith(
                    "irene_2011/validation/irene_hwms_nj2.geojson"
                )
            )
        self.assertIs(domain.active(), dom)
        self.assertEqual(
            str(metrics._hwm_path(Path("/D"))),
            "/D/validation_nj2/sandy_hwms_nj2.geojson",
        )
        with self.assertRaises(ValueError):
            with domain.scoring_view(replace(view, name="v3")):
                pass

    def test_peak_floor(self):
        t = np.array(
            ["2011-08-26T12:00", "2011-08-28T00:00", "2012-10-30T00:00"],
            dtype="datetime64[m]",
        )
        v = np.array([5.0, 2.0, 1.0])
        self.assertEqual(
            core.peak_after_floor(t, v)[0], 1.0
        )  # Sandy's floor: only the 2012 sample
        self.assertEqual(
            core.peak_after_floor(t, v, storm.peak_floor(ST))[0], 2.0
        )  # spin-up spike skipped

    def test_gap_near_the_crest(self):
        t = pd.date_range("2011-08-28 00:00", "2011-08-28 12:00", freq="6min").values
        v = np.ones(len(t))
        self.assertAlmostEqual(metrics._gap_near_h(t, v, t[60], 3.0), 0.1)
        v[50:70] = np.nan
        self.assertGreater(metrics._gap_near_h(t, v, t[60], 3.0), 2.0)

    def test_label_and_unknown_storm(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(storm.label(d), storm.TEMPLATE_STORM)
            self.assertIsNone(storm.storm_of(d))
            (Path(d) / storm.SIDECAR).write_text(json.dumps({"storm": "nope1999"}))
            with self.assertRaises(KeyError):
                storm.storm_of(d)

    def test_hwm_count_mismatch_skips_another_storm(self):
        import run_experiments as rx

        df = pd.DataFrame(
            {
                "hwm_n_scored": [300, 4, 290],
                "storm": ["sandy2012", "irene2011", np.nan],
            },
            index=["ref", "irene", "old"],
        )
        out = rx.hwm_count_mismatches(df, ref="ref")
        self.assertEqual(len(out), 1)
        self.assertIn("old", out[0])


class TestValidationDefaults(unittest.TestCase):
    def test_no_extent_for_irene(self):
        self.assertFalse(ST.validation.extent)
        self.assertIsInstance(ST.validation, StormValidation)


class TestIreneInputs(_Env):
    """The real files (skipped where ``data/irene_2011`` is not reachable): what the arm declares is what they hold."""

    def setUp(self) -> None:
        super().setUp()
        if not (Path(ST.meteo_from) / "sfincs_netamuv.nc").is_file():
            self.skipTest("data/irene_2011 not reachable")

    def test_boundary_has_240_points_and_covers_the_window(self):
        from nj_sfincs.config import DATA
        from nj_sfincs.provenance import catalog_uri

        with xr.open_dataset(DATA / catalog_uri(ST.waterlevel_geodataset)) as ds:
            dims = [d for d in ds["waterlevel"].dims if d != "time"]
            self.assertEqual(ds.sizes[dims[0]], 240)
            t = pd.to_datetime(ds.time.values)
        t0, t1 = storm.window(ST)
        self.assertLessEqual(t[0], t0)
        self.assertGreaterEqual(t[-1], t1)

    def test_boundary_points_are_a_subset_of_the_premiers(self):
        from nj_sfincs.config import DATA
        from nj_sfincs.provenance import catalog_uri

        def lonlat(key):
            with xr.open_dataset(DATA / catalog_uri(key)) as ds:
                return np.c_[ds["lon"].values, ds["lat"].values]

        new, ref = lonlat(ST.waterlevel_geodataset), lonlat(ST.support_reference)
        self.assertEqual((len(new), len(ref)), (240, 244))
        # ~1 m in degrees
        self.assertEqual(storm.unmatched(new, ref, tol=1e-5).tolist(), [])

    def test_rivers_bracket_the_padded_window(self):
        from nj_sfincs.config import DATA
        from nj_sfincs.provenance import catalog_uri

        with xr.open_dataset(DATA / catalog_uri(ST.discharge_geodataset)) as ds:
            t = pd.to_datetime(ds.time.values)
            n = ds.sizes[[d for d in ds["discharge"].dims if d != "time"][0]]
        t0, t1 = storm.window(ST)
        self.assertEqual(n, 58)
        self.assertLessEqual(t[0], t0 - storm.DISCHARGE_PAD)
        self.assertGreaterEqual(t[-1], t1 + storm.DISCHARGE_PAD)

    def test_meteo_pair_is_engine_convention_and_covers(self):
        from nj_sfincs import meteo_grid

        t0, t1 = storm.window(ST)
        for f in model.METEO_FROM_FILES:
            p = Path(ST.meteo_from) / f
            self.assertTrue(meteo_grid.file_state(p)["fixed"], f)
            a, b = storm._abs_times(p)
            self.assertLessEqual(a, t0)
            self.assertGreaterEqual(b, t1)

    def test_validation_files_hold_the_stations(self):
        from nj_sfincs.config import DATA

        view = storm.scoring_domain(ST)
        missing = []
        for g in view.obs_gauges:
            if not g.obs_file:
                continue
            with xr.open_dataset(DATA / g.obs_file) as ds:
                if g.obs_station not in set(ds["stations"].values.tolist()):
                    missing.append(g.name)
        # New Castle 01482170 is in the file (all NaN); Rockaway Inlet is not a domain gauge
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
