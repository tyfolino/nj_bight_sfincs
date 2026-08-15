"""The domain registry, its fingerprints, and the staging order.

Stdlib ``unittest`` — the env is pinned deliberately and pytest is not in it::

    PYTHONPATH=$PWD python -m unittest discover -s tests -v

Every test here corresponds to something that, when it broke, cost real work. The one
marked ⭐ is a regression test for a data-loss bug and asserts ORDERING, not end state.

Nothing here runs SFINCS, reads a run output, or writes into ``experiments/``.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

from nj_sfincs import domain, premier
from nj_sfincs.config import ROOT, exp_root
from nj_sfincs.experiments import EXPERIMENTS_BY_DOMAIN, experiments, sweepable


class _DomainEnv(unittest.TestCase):
    """Base that restores NJ_DOMAIN, which several tests set."""

    def setUp(self) -> None:
        self._saved = os.environ.get("NJ_DOMAIN")

    def tearDown(self) -> None:
        if self._saved is None:
            os.environ.pop("NJ_DOMAIN", None)
        else:
            os.environ["NJ_DOMAIN"] = self._saved


class TestDomainRegistry(_DomainEnv):
    def test_key_matches_name(self):
        for key, dom in domain.DOMAINS.items():
            self.assertEqual(key, dom.name, f"DOMAINS[{key!r}].name is {dom.name!r}")

    def test_default_domain_is_registered(self):
        self.assertIn(domain.DEFAULT_DOMAIN, domain.DOMAINS)

    def test_active_follows_env(self):
        for name in domain.DOMAINS:
            os.environ["NJ_DOMAIN"] = name
            self.assertEqual(domain.active().name, name)

    def test_active_is_read_at_call_time(self):
        """Not cached at import — the whole registry depends on this."""
        first = next(iter(domain.DOMAINS))
        os.environ["NJ_DOMAIN"] = first
        self.assertEqual(domain.active().name, first)
        os.environ["NJ_DOMAIN"] = "v9_atlantis"
        with self.assertRaises(KeyError):
            domain.active()

    def test_unknown_domain_raises(self):
        os.environ["NJ_DOMAIN"] = "v9_atlantis"
        with self.assertRaises(KeyError):
            domain.active()

    def test_basin_rules_are_named_and_unique(self):
        for name, dom in domain.DOMAINS.items():
            names = domain.hwm_basin_names(dom)
            self.assertTrue(names, f"{name} has no HWM basin rules")
            self.assertEqual(
                len(names), len(set(names)), f"{name} has duplicate basin names: {names}"
            )
            self.assertNotIn(
                "unassigned", names, "'unassigned' is the fallback bucket, not a rule name"
            )

    def test_waterlevel_support_is_declared(self):
        """A domain with no declared support count cannot have an inserted node caught."""
        for name, dom in domain.DOMAINS.items():
            self.assertIsNotNone(
                dom.n_waterlevel_support, f"{name} does not declare n_waterlevel_support"
            )

    def test_obs_gauge_names_are_unique_per_domain(self):
        """Every his-based metric matches its station by SUBSTRING on this name."""
        for name, dom in domain.DOMAINS.items():
            names = [g.name for g in dom.obs_gauges]
            self.assertEqual(len(names), len(set(names)), f"{name} has duplicate gauges")
            # substring matching means one name must not be contained in another
            for a in names:
                for b in names:
                    if a is not b:
                        self.assertNotIn(
                            a, b,
                            f"gauge {a!r} is a substring of {b!r} on {name}: his lookup "
                            "matches by substring and would return the wrong station",
                        )

    def test_obs_gauge_series_source_is_valid(self):
        for name, dom in domain.DOMAINS.items():
            for g in dom.obs_gauges:
                self.assertIn(
                    g.series_source, ("his", "map"),
                    f"{name}/{g.name} has series_source={g.series_source!r}",
                )


class TestBoxesAreFullyBounded(_DomainEnv):
    """⭐ The defect class made unrepresentable.

    Two of the previous repo's three mask overrides had UNBOUNDED sides, and one of them —
    a ``3 -> 2`` flip for everything north of a latitude, with three unbounded sides — put
    70 water-level boundary cells on dry land. An unbounded box is silently correct on the
    domain it was written for and silently wrong on the next.

    These assert the shape of the declarations, so the type cannot regress to accepting
    ``None``.
    """

    def _check(self, label, box):
        self.assertEqual(len(box), 4, f"{label}: box must be (xmin, ymin, xmax, ymax)")
        for i, v in enumerate(box):
            self.assertIsNotNone(v, f"{label}: bound {i} is None — no unbounded sides")
            self.assertTrue(
                isinstance(v, (int, float)) and v == v, f"{label}: bound {i} is {v!r}"
            )
        self.assertLess(box[0], box[2], f"{label}: xmin >= xmax")
        self.assertLess(box[1], box[3], f"{label}: ymin >= ymax")

    def test_mask_override_boxes_are_fully_bounded(self):
        for name, dom in domain.DOMAINS.items():
            for ov in dom.mask_overrides:
                self._check(f"{name}/mask_override {ov.name}", ov.box)

    def test_boundary_arms_are_fully_bounded(self):
        for name, dom in domain.DOMAINS.items():
            for arm in dom.boundary_arms:
                self._check(f"{name}/arm {arm.name}", arm.box)

    def test_no_waterlevel_boxes_are_fully_bounded(self):
        for name, dom in domain.DOMAINS.items():
            for z in dom.no_waterlevel_boxes:
                self._check(f"{name}/no_wl {z.name}", z.box)

    def test_land_boxes_are_declared_and_bounded(self):
        for name, dom in domain.DOMAINS.items():
            for lname, box, why in dom.land_boxes:
                self._check(f"{name}/land_box {lname}", box)
                self.assertTrue(why, f"{name}/land_box {lname} has no reason recorded")

    def test_boundary_arms_are_disjoint(self):
        """Overlapping arm boxes make a per-arm cell count meaningless."""
        for name, dom in domain.DOMAINS.items():
            arms = list(dom.boundary_arms)
            for i, a in enumerate(arms):
                for b in arms[i + 1 :]:
                    ax0, ay0, ax1, ay1 = a.box
                    bx0, by0, bx1, by1 = b.box
                    overlap = (ax0 < bx1 and bx0 < ax1) and (ay0 < by1 and by0 < ay1)
                    self.assertFalse(
                        overlap, f"{name}: arms {a.name!r} and {b.name!r} overlap"
                    )

    def test_boundary_arm_cell_bounds_are_sane(self):
        for name, dom in domain.DOMAINS.items():
            for arm in dom.boundary_arms:
                self.assertGreaterEqual(arm.min_cells, 1, f"{name}/{arm.name}")
                self.assertLess(arm.min_cells, arm.max_cells, f"{name}/{arm.name}")
                self.assertLess(
                    arm.max_bed_m, 0.0,
                    f"{name}/{arm.name}: max_bed_m >= 0 admits a BC on dry ground",
                )
                self.assertIn(arm.btype, ("waterlevel", "outflow"), f"{name}/{arm.name}")


class TestFingerprints(_DomainEnv):
    def test_every_domain_has_a_fingerprint(self):
        self.assertEqual(
            set(premier.EXPECTED),
            set(domain.DOMAINS),
            "a domain without a fingerprint audits UNRECOGNISED, which reads exactly "
            "like a real domain error and trains you to ignore the one alarm that matters",
        )

    def test_expected_resolves_per_domain(self):
        for name in domain.DOMAINS:
            os.environ["NJ_DOMAIN"] = name
            self.assertEqual(premier.expected(), premier.EXPECTED[name])

    def test_fingerprints_are_distinct(self):
        fps = list(premier.EXPECTED.values())
        self.assertEqual(len(fps), len(set(fps)), "two domains share a fingerprint")

    def test_brackets_are_not_in_expected(self):
        """A bracket in EXPECTED would make assert_sealed_domain PASS on it.

        Asserted even while BRACKETS is empty: the invariant has to be in place before the
        first bracket exists, not added alongside it.
        """
        expected_fps = set(premier.EXPECTED.values())
        for name, brk in premier.BRACKETS.items():
            self.assertNotIn(
                brk.fingerprint,
                expected_fps,
                f"bracket {name!r} is registered as a legitimate domain",
            )

    def test_bracket_base_domain_is_registered(self):
        for name, brk in premier.BRACKETS.items():
            self.assertIn(
                brk.base_domain, domain.DOMAINS, f"bracket {name!r} names an unknown base"
            )

    def test_known_covers_every_expected_fingerprint(self):
        """KNOWN is what turns a BAD line into a diagnosis instead of 'UNRECOGNISED'."""
        for name, fp in premier.EXPECTED.items():
            self.assertIn(fp, premier.KNOWN, f"{name}'s fingerprint has no KNOWN label")


class TestMeshKeySharing(_DomainEnv):
    """A shared ``mesh_key`` is for the boundary-depth pair ONLY.

    Replaces the previous repo's ``test_frozen_mesh_declared_per_domain``. Two domains may
    share a mesh precisely when they differ in ``mask_zmin`` and in nothing else that the
    mesh determines; anything looser turns ``mesh_key`` into a general escape hatch for
    "run this arm on that mesh", which is how a sweep ends up on the wrong domain.
    """

    def test_mesh_key_siblings_differ_in_mask_zmin(self):
        by_key: dict[str, list] = {}
        for dom in domain.DOMAINS.values():
            by_key.setdefault(dom.mesh_key or dom.name, []).append(dom)
        for key, doms in by_key.items():
            if len(doms) < 2:
                continue
            zmins = [d.mask_zmin for d in doms]
            self.assertEqual(
                len(set(zmins)),
                len(zmins),
                f"domains sharing mesh_key {key!r} have the same mask_zmin {zmins} — "
                "then they are the same domain under two names",
            )
            regions = {str(d.region) for d in doms}
            self.assertEqual(
                len(regions), 1,
                f"domains sharing mesh_key {key!r} have different regions {regions} — "
                "a shared mesh means a shared region polygon",
            )

    def test_frozen_mesh_dir_is_keyed(self):
        for name, dom in domain.DOMAINS.items():
            self.assertTrue(
                dom.frozen_mesh_dir().name.endswith(dom.mesh_key or name),
                f"{name}'s frozen mesh path is not keyed on its mesh_key — the path "
                "should make the wrong mesh impossible to pick by omission",
            )


class TestExperimentPaths(_DomainEnv):
    def test_exp_root_is_domain_scoped(self):
        seen = set()
        for name in domain.DOMAINS:
            os.environ["NJ_DOMAIN"] = name
            root = exp_root()
            self.assertEqual(root.name, name)
            self.assertEqual(root.parent, ROOT / "experiments")
            seen.add(root)
        self.assertEqual(
            len(seen),
            len(domain.DOMAINS),
            "exp_root() returned the same path for two domains — the same arm name on "
            "two domains would collide",
        )

    def test_sealed_template_lives_under_exp_root(self):
        for name in domain.DOMAINS:
            os.environ["NJ_DOMAIN"] = name
            self.assertEqual(premier.sealed_template().parent, exp_root())
            self.assertEqual(premier.sealed_template().name, premier.TEMPLATE_NAME)


class TestExperimentsAreDomainScoped(_DomainEnv):
    """``EXPERIMENTS`` used to be ONE FLAT DICT across every domain.

    By the end it held ~31 arms in one namespace, and ``--experiments all`` on a fresh
    domain meant "attempt every arm ever defined" — with forcing files, support-point
    counts and templates belonging somewhere else.
    """

    def test_experiments_are_keyed_by_domain(self):
        for dname, arms in EXPERIMENTS_BY_DOMAIN.items():
            for aname, exp in arms.items():
                self.assertEqual(
                    aname, exp.name, f"{dname}: key {aname!r} != Experiment.name {exp.name!r}"
                )

    def test_registered_domains_have_an_entry(self):
        for name in domain.DOMAINS:
            self.assertIn(
                name,
                EXPERIMENTS_BY_DOMAIN,
                f"domain {name!r} has no entry in EXPERIMENTS_BY_DOMAIN — even an empty "
                "dict is a statement; a missing key is an oversight",
            )

    def test_frozen_domains_have_no_arms(self):
        """A frozen domain is staged and scored, never built. An arm on it is a trap."""
        for name, dom in domain.DOMAINS.items():
            if dom.frozen:
                self.assertEqual(
                    experiments(name), {}, f"frozen domain {name!r} declares arms"
                )

    def test_sweepable_excludes_brackets(self):
        for dname in EXPERIMENTS_BY_DOMAIN:
            arms = experiments(dname)
            swept = sweepable(dname)
            for aname, exp in arms.items():
                if exp.bracket is not None:
                    self.assertNotIn(
                        aname, swept, f"{dname}: bracket {aname!r} is in the sweep set"
                    )

    def test_bracket_arms_name_a_registered_bracket(self):
        for dname, arms in EXPERIMENTS_BY_DOMAIN.items():
            for aname, exp in arms.items():
                if exp.bracket is not None:
                    self.assertIn(exp.bracket, premier.BRACKETS, f"{dname}/{aname}")

    def test_bracket_arms_carry_the_prefix(self):
        """Deliberately redundant with ``Experiment.bracket`` — belt and braces."""
        for dname, arms in EXPERIMENTS_BY_DOMAIN.items():
            for aname, exp in arms.items():
                if exp.bracket is not None:
                    self.assertTrue(
                        aname.startswith(premier.BRACKET_PREFIX),
                        f"{dname}/{aname} is a bracket but is not named "
                        f"{premier.BRACKET_PREFIX}...",
                    )


class TestWaterlevelSupportOverride(_DomainEnv):
    """``Experiment.n_waterlevel_support`` must be a DECLARATION, not a loophole.

    The failure it guards against is an arm quietly gaining a support point — which cost
    one retired arm +0.18 m of HWM bias. The temptation when the assertion fires is to
    relax ``Domain.n_waterlevel_support``, which would disable the check for EVERY arm on
    the domain.
    """

    def test_support_counts_match_pinned_table(self):
        """Replaces a test that asserted a CONSTANT where it meant STABILITY.

        The previous version asserted every domain expected exactly 2 support points. That
        is not the property — the property is that the number does not move without someone
        deciding it should. A dense ADCIRC boundary has hundreds, so the constant version
        would have to be deleted the moment it mattered, taking the guard with it.

        ⚠️ ``PINNED`` is written out by hand and NEVER computed from the Domain object.
        Deriving it would make the assertion tautological, which is what a relaxed
        assertion always becomes.
        """
        PINNED = {
            "v1_monmouth": 2,
            # The BASE (noaa_sandy_nj) selection, measured during the 2026-08-14
            # template build. ⚠️ NOT the NACCS count: the premier forces from 71 points,
            # declared on the ARM. Putting 71 here would disable the guard for every
            # other arm on the domain — see nj_sfincs/domain.py.
            "v1_5_raritan": 2,
        }
        self.assertEqual(
            set(PINNED),
            set(domain.DOMAINS),
            "a domain is missing from PINNED — add it here DELIBERATELY, with the count "
            "you intend, rather than letting the registry answer its own question",
        )
        for name, want in PINNED.items():
            self.assertEqual(
                domain.DOMAINS[name].n_waterlevel_support,
                want,
                f"{name} expects {domain.DOMAINS[name].n_waterlevel_support} support "
                f"points, pinned at {want}. If an ARM needs a different count, declare it "
                "on the Experiment — do NOT relax the domain value.",
            )

    def test_override_defaults_to_none(self):
        from nj_sfincs.config import Experiment, WaveConfig

        e = Experiment("x", WaveConfig(use_waves=False))
        self.assertIsNone(
            e.n_waterlevel_support, "the override must be opt-in; None = inherit the domain"
        )

    def test_only_declared_arms_override(self):
        """Every override must be justified in the arm's description."""
        for dname, arms in EXPERIMENTS_BY_DOMAIN.items():
            for name, exp in arms.items():
                if exp.n_waterlevel_support is None:
                    continue
                self.assertIsNotNone(
                    exp.waterlevel_geodataset,
                    f"{dname}/{name} overrides the support count but does not override "
                    "the forcing — that cannot be intentional",
                )
                self.assertGreater(
                    len(exp.description),
                    80,
                    f"{dname}/{name} overrides the support count without explaining why",
                )

    def test_check_uses_expect_over_domain(self):
        """The guard prefers an explicit expect, and still fires on a mismatch."""
        import numpy as np
        import xarray as xr

        from nj_sfincs import model

        class _FakeWL:
            def __init__(self, n):
                da = xr.DataArray(np.zeros((3, n)), dims=("time", "index"))
                self.data = xr.Dataset({"bzs": da})

        class _FakeSf:
            def __init__(self, n):
                self.water_level = _FakeWL(n)

        os.environ["NJ_DOMAIN"] = "v1_monmouth"
        self.assertEqual(model.check_waterlevel_support(_FakeSf(8), expect=8), 8)
        self.assertEqual(model.check_waterlevel_support(_FakeSf(2)), 2)
        with self.assertRaises(RuntimeError):
            model.check_waterlevel_support(_FakeSf(8))  # domain default = 2
        with self.assertRaises(RuntimeError):
            model.check_waterlevel_support(_FakeSf(7), expect=8)  # declared 8, got 7

    def test_missing_bzs_is_refused_not_defaulted(self):
        class _FakeSf:
            water_level = type("W", (), {"data": None})()

        from nj_sfincs import model

        with self.assertRaises(RuntimeError):
            model.check_waterlevel_support(_FakeSf())


class TestFrozenDomainCannotBeBuilt(_DomainEnv):
    def test_build_static_refuses_a_frozen_domain(self):
        import tempfile

        from nj_sfincs import model
        from nj_sfincs.config import BaseConfig

        frozen = [n for n, d in domain.DOMAINS.items() if d.frozen]
        if not frozen:
            self.skipTest("no frozen domain registered")
        os.environ["NJ_DOMAIN"] = frozen[0]
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                model.build_static(BaseConfig(), Path(tmp) / "out")


class TestWavesOffIsWrittenNotAssumed(_DomainEnv):
    """A ``use_waves=False`` arm must END UP with ``snapwave = 0`` in its sfincs.inp.

    Four arms were once submitted to SLURM running SnapWave despite declaring
    ``use_waves=False``: staging copies a template that has waves ON, and ``finalize`` only
    ADDED SnapWave keys when waves were on, doing nothing when they were off — so the
    copied ``snapwave = 1`` and the snapwave.* files survived. Entirely silent; the only
    tell is ~10x runtime.
    """

    def test_source_has_the_waves_off_branch(self):
        """Pin the branch itself — the bug was its ABSENCE, which nothing detected."""
        import inspect

        from nj_sfincs import model

        src = inspect.getsource(model.finalize)
        self.assertIn(
            "snapwave':<20} = 0",
            src.replace('"', "'"),
            "finalize() no longer writes snapwave = 0 for a waves-off arm; waves-off "
            "would silently inherit the template's waves",
        )

    def test_staged_nowaves_arms_have_snapwave_off(self):
        """The REAL check: any staged nowaves arm ON DISK must have snapwave = 0.

        Read-only, and skips arms that are not currently staged, so the suite still runs on
        a clean clone. This is what would have caught the bug, because it inspects what was
        actually written rather than what was intended.
        """
        checked = 0
        for dname in domain.DOMAINS:
            os.environ["NJ_DOMAIN"] = dname
            root = exp_root()
            for name, exp in experiments(dname).items():
                if exp.waves.use_waves:
                    continue
                inp = root / name / "sfincs.inp"
                if not inp.exists():
                    continue
                checked += 1
                keys = {
                    ln.split("=")[0].strip(): ln.split("=")[1].strip()
                    for ln in inp.read_text().splitlines()
                    if "=" in ln
                }
                self.assertEqual(
                    keys.get("snapwave", "1"),
                    "0",
                    f"{inp} has waves ON but '{name}' declares use_waves=False",
                )
                for stale in ("snapwave.bnd", "snapwave.bhs", "snapwave.btp"):
                    self.assertFalse(
                        (inp.parent / stale).exists(),
                        f"{stale} survived in a waves-off arm at {inp.parent}",
                    )
        if checked == 0:
            self.skipTest("no waves-off arms staged on any domain")

    def test_nowaves_arms_declare_use_waves_false(self):
        for dname, arms in EXPERIMENTS_BY_DOMAIN.items():
            for name, exp in arms.items():
                if "nowaves" in name:
                    self.assertFalse(
                        exp.waves.use_waves, f"{dname}/{name} is named 'nowaves' but has waves ON"
                    )


class TestStagingIsSafeBeforeItIsDestructive(_DomainEnv):
    """⭐ THE REGRESSION TEST FOR THE DATA-LOSS BUG.

    ``prepare_experiment`` used to ``rmtree`` the destination and ``copytree`` the template
    BEFORE asserting the domain, so a wrong-domain refusal could only ever be reported once
    the destination was already gone. That destroyed a run directory's 1.8 GB of solver
    output, from a command whose author believed it was read-only.

    The fix is ORDERING, so this test asserts ordering.
    """

    def test_domain_is_checked_before_anything_destructive(self):
        """Assert ORDERING, not just the end state.

        ``shutil.rmtree``/``copytree`` are SPIED rather than allowed to run: under the old
        ordering a real ``copytree`` would clone the multi-GB template into a temp dir
        before the test could catch anything. Spying records the sequence, which is the
        property actually under test — and it fails loudly on the old code, where 'rmtree'
        lands in the log before 'domain-check'.

        ⚠️ The arm is SYNTHETIC, deliberately. This must never skip just because the active
        domain happens to have no arms registered — the property under test belongs to
        ``prepare_experiment``, not to any particular experiment, and a data-loss
        regression test that quietly skips is worth nothing.
        """
        import shutil as _shutil
        import tempfile

        import run_experiments as rx
        from nj_sfincs.config import Experiment, WaveConfig

        name = "_synthetic_ordering_probe"
        events: list[str] = []

        def refuse(*_a, **_k):
            events.append("domain-check")
            raise premier.WrongDomainError("simulated wrong domain")

        with tempfile.TemporaryDirectory() as tmp:
            fake_root = Path(tmp) / "experiments"
            victim = fake_root / name
            victim.mkdir(parents=True)
            canary = victim / "sfincs_map.nc"
            canary.write_text("precious solver output")

            saved = (
                rx.EXP_ROOT,
                dict(rx.EXPERIMENTS),
                premier.assert_sealed_domain,
                premier.assert_bracket,
                _shutil.rmtree,
                _shutil.copytree,
            )
            rx.EXP_ROOT = fake_root
            rx.EXPERIMENTS[name] = Experiment(name, WaveConfig(use_waves=False), "probe")
            premier.assert_sealed_domain = refuse
            premier.assert_bracket = refuse
            _shutil.rmtree = lambda *a, **k: events.append("rmtree")
            _shutil.copytree = lambda *a, **k: events.append("copytree")
            try:
                with self.assertRaises(premier.WrongDomainError):
                    rx.prepare_experiment(name, object())
            finally:
                (
                    rx.EXP_ROOT,
                    _exps,
                    premier.assert_sealed_domain,
                    premier.assert_bracket,
                    _shutil.rmtree,
                    _shutil.copytree,
                ) = saved
                rx.EXPERIMENTS.clear()
                rx.EXPERIMENTS.update(_exps)

            self.assertEqual(
                events[0],
                "domain-check",
                f"the domain check must come FIRST; got {events}. This is the data-loss "
                "bug: a wrong-domain refusal that only fires after the destination is "
                "already destroyed.",
            )
            self.assertNotIn(
                "rmtree", events, f"nothing destructive may run after a refusal; got {events}"
            )
            self.assertTrue(canary.exists())
            self.assertEqual(canary.read_text(), "precious solver output")

    def test_check_template_domain_touches_nothing(self):
        """The read-only path must not create EXP_ROOT as a side effect."""
        import tempfile

        import run_experiments as rx
        from nj_sfincs.config import Experiment, WaveConfig

        name = "_synthetic_readonly_probe"
        with tempfile.TemporaryDirectory() as tmp:
            fake_root = Path(tmp) / "experiments"  # deliberately absent
            saved_root, saved_assert = rx.EXP_ROOT, premier.assert_sealed_domain
            premier.assert_sealed_domain = lambda *_a, **_k: None
            rx.EXP_ROOT = fake_root
            rx.EXPERIMENTS[name] = Experiment(name, WaveConfig(use_waves=False), "probe")
            try:
                rx.check_template_domain(name)
            finally:
                rx.EXP_ROOT, premier.assert_sealed_domain = saved_root, saved_assert
                rx.EXPERIMENTS.pop(name, None)
            self.assertFalse(fake_root.exists(), "check_template_domain created directories")

    def test_all_sweep_requires_confirmation(self):
        """``--experiments all`` rmtree's every destination. It must not be the default.

        The previous driver defaulted ``--experiments`` to ``"all"``, so a bare
        ``python run_experiments.py`` WAS a full destructive sweep — and its only
        confirmation was that you had typed the command.

        Two properties: omitting ``--experiments`` is an error, and ``all`` without a tty
        and without ``--yes`` is refused rather than assumed.
        """
        import run_experiments as rx
        from nj_sfincs.config import Experiment, WaveConfig

        name = "_synthetic_sweep_probe"
        rx.EXPERIMENTS[name] = Experiment(name, WaveConfig(use_waves=False), "probe")
        try:
            with self.assertRaises(SystemExit):
                rx.main([])  # no --experiments at all
            with self.assertRaises(SystemExit):
                rx.main(["--experiments", "all"])  # no tty, no --yes
        finally:
            rx.EXPERIMENTS.pop(name, None)


class TestDryLandBoxes(unittest.TestCase):
    """Invariant 8 — the POSITIVE bed check.

    🔴 Why this test exists: on 2026-08-14 `cudem_nj` was found to be missing the Ward
    Point headland, truncating New York State at lat 40.49982 and backfilling ~230 m of it
    as -3 to -5.5 m of bay, while Conference House Park read -0.06 m off 50 m GMRT.
    **Every domain invariant was green**, because the NoData check (invariant 6) asks only
    whether data exists, and a coarse fallback tier always has data. The defect was caught
    by eye, on a figure, after a mesh had already been built on it.

    So the replacement check has to be positive, and it has to be SEEN TO FAIL. An assert
    nobody has watched fire is a decoration.
    """

    #: A tiny synthetic grid in EPSG:26918 around Ward Point, so the test needs no raster.
    CRS = "EPSG:26918"

    def _grid(self):
        import numpy as np
        from pyproj import Transformer

        t = Transformer.from_crs(4326, self.CRS, always_xy=True)
        lons = np.linspace(-74.2490, -74.2468, 6)
        lats = np.linspace(40.4985, 40.4994, 5)
        lo, la = np.meshgrid(lons, lats)
        fx, fy = t.transform(lo.ravel(), la.ravel())
        return np.asarray(fx), np.asarray(fy)

    BOX = (
        "ward_point_headland",
        (-74.2492, 40.4983, -74.2465, 40.4996),
        0.5,
        "test box",
    )

    def test_passes_when_the_declared_land_is_land(self):
        import numpy as np

        from nj_sfincs.model import check_dry_land_boxes

        fx, fy = self._grid()
        zb = np.full(fx.shape, 2.5)  # what CoNED reports there
        self.assertEqual(check_dry_land_boxes((self.BOX,), self.CRS, fx, fy, zb), [])

    def test_FIRES_on_the_actual_cudem_bed(self):
        """The regression that motivated the check: CUDEM's phantom water at Ward Point."""
        import numpy as np

        from nj_sfincs.model import check_dry_land_boxes

        fx, fy = self._grid()
        zb = np.full(fx.shape, -4.96)  # what cudem_nj reports there
        fail = check_dry_land_boxes((self.BOX,), self.CRS, fx, fy, zb)
        self.assertEqual(len(fail), 1)
        self.assertIn("ward_point_headland", fail[0])
        self.assertIn("says WATER on ground declared to be LAND", fail[0])

    def test_FIRES_on_nodata(self):
        """NoData must fail too — `zb >= min_z` is False for NaN, and that is deliberate."""
        import numpy as np

        from nj_sfincs.model import check_dry_land_boxes

        fx, fy = self._grid()
        zb = np.full(fx.shape, np.nan)
        fail = check_dry_land_boxes((self.BOX,), self.CRS, fx, fy, zb)
        self.assertEqual(len(fail), 1)
        self.assertIn("NoData", fail[0])

    def test_FIRES_on_an_empty_box(self):
        """🔴 The characteristic failure of a positive check: a box with no faces in it
        asserts nothing and passes forever. It must be an error, not silence."""
        import numpy as np

        from nj_sfincs.model import check_dry_land_boxes

        fx, fy = self._grid()
        far = ("nowhere", (-70.0, 30.0, -69.99, 30.01), 0.5, "test box")
        fail = check_dry_land_boxes((far,), self.CRS, fx, fy, np.full(fx.shape, 5.0))
        self.assertEqual(len(fail), 1)
        self.assertIn("asserts nothing", fail[0])

    def test_the_registered_boxes_are_inside_the_coned_tier_box(self):
        """A dry-land box outside `coned_sw_raritan`'s clip would assert against ground
        the tier does not cover, which is a trap rather than a check."""
        from nj_sfincs import domain as _domain

        dom = _domain.DOMAINS["v1_5_raritan"]
        if not dom.dry_land_boxes_ll:
            self.skipTest("no dry-land boxes registered on v1_5_raritan")
        tier = (-74.3120, 40.4640, -74.2320, 40.5340)  # build_coned_sw_raritan.BOX
        for name, (lo0, la0, lo1, la1), _min_z, _why in dom.dry_land_boxes_ll:
            self.assertTrue(
                tier[0] <= lo0 and lo1 <= tier[2] and tier[1] <= la0 and la1 <= tier[3],
                f"dry-land box {name!r} is not inside the CoNED tier's clip box",
            )


if __name__ == "__main__":
    unittest.main()
