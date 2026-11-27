"""nj2 (Model 2.0) as registered 2026-11-14 — what changed from Model 1.1.0's domain, and nothing else.

Stdlib unittest. Reads only the registry and the small design files (the ring CSV, the mark file);
nothing here builds, stages or runs. Record: logs/nj2_freeze_2026-11-14/README.md.
"""

from __future__ import annotations

import dataclasses
import unittest

from nj_sfincs import domain, premier

NJ2 = domain.DOMAINS["nj2"]
V11 = domain.V4_REFREEZE_SWZ_V11


class TestNJ2(unittest.TestCase):
    def test_only_the_intended_fields_differ_from_1_1_0(self):
        diff = {
            f.name
            for f in dataclasses.fields(NJ2)
            if getattr(NJ2, f.name) != getattr(V11, f.name)
        }
        self.assertEqual(
            diff,
            {
                "name",
                "region",
                "region_source",
                "refinement",
                "mesh_key",  # v11 borrows v4's mesh; nj2 has its own
                "face_z_from",
                # building / n_waterlevel_support: equal to 1.1.0's since the freeze
                # (False / 3, 2026-11-15) — they left this set at GATE 1
                "coarse_elevation_list",
                "boundary_arms",
                "mask_overrides",
                "dry_land_boxes_ll",
                "hwm_rules",
                "hwm_geojson",
                "map_windows",
                "waterlevel_line",  # data/nj2_design/waterlevel_line_nj2.csv: v4's vertices
                "obs_gauges",  # + 7 (the Battery, Bergen Point, 3 STN sensors, 2 cut diagnostics)
                "flux_crosssections",  # + the two cuts, the Narrows, the KvK (11-14)
            },
        )

    def test_frozen_state(self):
        """GATE 1 (2026-11-15): frozen by J2 63919024 pass 1, registered by hand."""
        self.assertFalse(NJ2.building)
        self.assertIsNone(NJ2.mesh_key)  # its own mesh, by name
        self.assertIsNone(NJ2.face_z_from)  # face z = the coarse bed
        self.assertEqual(NJ2.n_waterlevel_support, 3)  # base noaa_sandy_nj, J2 step 4b
        self.assertEqual(
            premier.EXPECTED["nj2"],
            premier.DomainFingerprint(5181372, 4367, "5759f6fa6cca6826"),
        )
        self.assertEqual(NJ2.frozen_mesh_dir().name, "frozen_mesh_nj2")
        self.assertIsNone(domain.region_source_mismatch(NJ2))

    def test_arms(self):
        names = [a.name for a in NJ2.boundary_arms]
        self.assertNotIn("narrows", names)
        self.assertNotIn("kvk_east", names)
        self.assertIn("cd_canal", names)
        self.assertEqual(len(names), len(set(names)))
        v4 = {a.name: a for a in domain.V4.boundary_arms}
        for a in NJ2.boundary_arms:
            if a.name in v4:  # the sea line's four sections + cd_canal: exactly v4's
                self.assertEqual(a, v4[a.name], a.name)
        self.assertEqual(
            domain.read_waterlevel_line(NJ2.waterlevel_line),
            domain.read_waterlevel_line(domain.V4.waterlevel_line),
        )

    def test_cut_arm_boxes_hold_their_forced_vertices(self):
        from pyproj import Transformer

        verts = {
            n: (lo, la) for n, lo, la in domain.read_waterlevel_line(NJ2.region_source)
        }
        t = Transformer.from_crs(4326, NJ2.epsg, always_xy=True)
        arms = {a.name: a for a in NJ2.boundary_arms}
        for arm, (v0, v1) in {
            "hudson": ("hudson_w", "hudson_e"),
            "hell_gate": ("hellgate_w", "hellgate_e"),
        }.items():
            x0, y0, x1, y1 = arms[arm].box
            for v in (v0, v1):
                x, y = t.transform(*verts[v])
                self.assertTrue(
                    x0 + 250 < x < x1 - 250 and y0 + 250 < y < y1 - 250, (arm, v)
                )
        self.assertEqual(verts["hudson_w"], (-73.95753, 40.86))  # user 11-04: 45 m W
        self.assertEqual(verts["astoria"], (-73.92297, 40.76945))  # user 11-03: inland

    def test_gauges(self):
        v11 = list(V11.obs_gauges)
        self.assertEqual(list(NJ2.obs_gauges[: len(v11)]), v11)
        new = [g.name for g in NJ2.obs_gauges[len(v11) :]]
        self.assertEqual(
            new,
            [
                "noaa_battery",
                "noaa_bergen_point",
                "sss_gowanus",
                "sss_hoboken",
                "sss_hackensack_hud002",
                "bc_hudson_cut",
                "bc_hell_gate",
            ],
        )

    def test_obs_file_matches_the_obs_agents(self):
        import sys

        sys.path.insert(0, str(domain.ROOT / "scripts"))
        from sync_obs_points import render

        have = (domain.DATA / "nj2_design" / "obs_nj2.obs").read_text()
        self.assertEqual(render(NJ2.obs_gauges, NJ2.epsg), have)

    def test_walls(self):
        v11 = {o.name: o for o in V11.mask_overrides}
        nj2 = {o.name: o for o in NJ2.mask_overrides}
        self.assertEqual(set(v11) - set(nj2), {"wall_bayonne"})
        self.assertEqual(set(nj2) - set(v11), {"wall_e88", "wall_hellgate_east"})
        for n in set(v11) & set(nj2):
            self.assertEqual(v11[n], nj2[n], n)
        for o in nj2.values():
            self.assertEqual((o.frm, o.to), (3, 1), o.name)

    def test_ring_is_v4_hot_plus_with_the_new_legs(self):
        hp = domain.read_waterlevel_line(
            domain.DATA / "v4_design" / "region_v4_hot_plus_vertices.csv"
        )
        nj = domain.read_waterlevel_line(NJ2.region_source)
        gone = {n for n, *_ in hp} - {n for n, *_ in nj}
        self.assertEqual(
            gone,
            {f"hudson_route_{i:02d}" for i in range(3, 22)}
            | {"narrows_w", "narrows_e"},
        )
        kept = {n: (lo, la) for n, lo, la in hp}
        for n, lo, la in nj:
            if n in kept:
                self.assertEqual(kept[n], (lo, la), n)

    def test_basin_rules_first_and_no_1x_mark_moves(self):
        import geopandas as gpd

        names = domain.hwm_basin_names(NJ2)
        self.assertEqual(
            names[:4], ("upper_bay_islands", "hudson_nj", "east_river", "upper_bay_ny")
        )
        self.assertEqual(names[4:], domain.hwm_basin_names(V11))
        g = gpd.read_file(V11.hwm_geojson).to_crs(NJ2.epsg)
        x, y = g.geometry.x.values, g.geometry.y.values
        ring = gpd.read_file(V11.region).to_crs(NJ2.epsg).geometry.iloc[0]
        inside = g.within(ring).values
        a = domain.classify_hwm_basin(x, y, V11)[inside]
        b = domain.classify_hwm_basin(x, y, NJ2)[inside]
        self.assertEqual(list(a), list(b))

    def test_snapwave_and_motf_unchanged(self):
        # user 2026-11-14: no SnapWave over the Upper Bay / lower Hudson (as Newark Bay in 1.1.0)
        self.assertEqual(NJ2.snapwave_footprint_ll, V11.snapwave_footprint_ll)
        self.assertEqual(NJ2.motf_tif, V11.motf_tif)
        self.assertEqual(NJ2.motf_valid_tif, V11.motf_valid_tif)
        # the four Newark Bay / Arthur Kill product-cutoff boxes (V4, 2026-11-13), inherited
        self.assertEqual(NJ2.motf_exclude_boxes_ll, V11.motf_exclude_boxes_ll)
        self.assertEqual(
            [b[0] for b in NJ2.motf_exclude_boxes_ll],
            [
                "newark_bay_bergen_point",
                "newark_bay_bayonne_west",
                "newark_bay_jc_route440",
                "linden_arthur_kill",
            ],
        )
        for name, d in domain.DOMAINS.items():  # every v4 variant carries them too
            if name.startswith("v4"):
                self.assertEqual(
                    d.motf_exclude_boxes_ll, NJ2.motf_exclude_boxes_ll, name
                )

    def test_bed_tiers(self):
        self.assertEqual(NJ2.elevation_list, domain.V4_ELEVATION_LIST)
        self.assertEqual(
            NJ2.coarse_elevation_list, ({"elevation": "bed_nj2_coarse_25m"},)
        )


class TestNJ2Bed2012(unittest.TestCase):
    """GATE 2 (2026-11-16): the 2012-bed face-z domain and the J3 design-gate arms."""

    def test_only_name_mesh_key_and_face_z_differ_from_nj2(self):
        b = domain.DOMAINS["nj2_bed2012"]
        diff = {
            f.name
            for f in dataclasses.fields(b)
            if getattr(b, f.name) != getattr(NJ2, f.name)
        }
        self.assertEqual(diff, {"name", "mesh_key", "face_z_from"})
        self.assertEqual(b.mesh_key, "nj2")
        self.assertEqual(b.face_z_from, "_subgrid_nj2_2012")
        self.assertEqual(b.frozen_mesh_dir(), NJ2.frozen_mesh_dir())

    def test_fingerprint_shares_nj2s_counts(self):
        fp, mesh = premier.EXPECTED["nj2_bed2012"], premier.EXPECTED["nj2"]
        self.assertEqual(
            fp, premier.DomainFingerprint(5181372, 4367, "c183d1a5f1d7bef6")
        )
        self.assertEqual(
            (fp.n_faces, fp.n_boundary_edges), (mesh.n_faces, mesh.n_boundary_edges)
        )
        self.assertNotEqual(fp.sha_z_mask, mesh.sha_z_mask)

    def test_j3_arms(self):
        from nj_sfincs.experiments import EXPERIMENTS_BY_DOMAIN

        self.assertEqual(EXPERIMENTS_BY_DOMAIN["nj2"], {})
        arms = EXPERIMENTS_BY_DOMAIN["nj2_bed2012"]
        self.assertEqual(
            set(arms),
            {
                "p4-nowaves+rain-off+slr-0m",
                "p4-nowaves+rain-off+slr-2m",
                "p4-nowaves+rain-off+slr-3m",
                "p4-nowaves+rain-off+slr-0m+struct-cohansey-checkvalve+weir-dikes-levees",
            },
        )
        for name, e in arms.items():
            with self.subTest(arm=name):
                self.assertEqual(e.subgrid_from, "_subgrid_nj2_2012")
                self.assertEqual(e.waterlevel_geodataset, "naccs_sandy_nj2")
                # naccs_nj2.log "[out] 244 support points" (J2 63919024 step 4)
                self.assertEqual(e.n_waterlevel_support, 244)
                self.assertFalse(e.rain)
                self.assertFalse(e.waves.use_waves)


def _changed(x, y, skip=()):
    return {
        f.name
        for f in dataclasses.fields(x)
        if f.name not in skip and getattr(x, f.name) != getattr(y, f.name)
    }


class TestNJ2W(unittest.TestCase):
    """nj2w (2026-11-17): nj2 + the two J3 leak walls, nothing else; nj2w_bed2012 its 2012-bed face-z domain,
    where 2.0's waves-on runs go (logs/nj2_freeze_2026-11-14/README.md §6, j3_walls/)."""

    def test_only_the_walls_differ_from_nj2(self):
        w = domain.DOMAINS["nj2w"]
        self.assertEqual(_changed(w, NJ2), {"name", "mesh_key", "mask_overrides"})
        self.assertEqual(w.mesh_key, "nj2")
        self.assertEqual(w.frozen_mesh_dir(), NJ2.frozen_mesh_dir())
        self.assertEqual(
            w.mask_overrides[: len(NJ2.mask_overrides)], NJ2.mask_overrides
        )
        new = w.mask_overrides[len(NJ2.mask_overrides) :]
        self.assertEqual(
            {o.name for o in new}, {"wall_astoria_park", "wall_millville_east"}
        )
        for o in new:
            self.assertEqual((o.frm, o.to), (3, 1), o.name)
            self.assertEqual(len(o.box), 4, o.name)

    def test_bed_domain_is_nj2w_plus_face_z(self):
        w, b = domain.DOMAINS["nj2w"], domain.DOMAINS["nj2w_bed2012"]
        self.assertEqual(_changed(b, w), {"name", "face_z_from"})
        self.assertEqual(b.face_z_from, "_subgrid_nj2_2012")
        self.assertEqual(
            _changed(b, domain.DOMAINS["nj2_bed2012"]), {"name", "mask_overrides"}
        )

    def test_bed2026_domain_is_nj2w_plus_face_z_and_cn(self):
        """nj2w_bed2026 (11-18): the 2026 bed's face z + the NLCD 2025 curve number, nothing else."""
        w, b = domain.DOMAINS["nj2w"], domain.DOMAINS["nj2w_bed2026"]
        self.assertEqual(_changed(b, w), {"name", "face_z_from", "cn_dataset"})
        self.assertEqual(b.face_z_from, "_subgrid_nj2_2026")
        self.assertEqual(b.cn_dataset, "cn_2025_v4")

    def test_waveson_arms(self):
        """1.1.0's premier with only the 2.0 domain changed (bed, NACCS file + support count, the wavemaker line
        redrawn on the 2012 bed, user 11-16); the 2.0 premier adds the dike set + Cohansey valve (user 11-17)."""
        from nj_sfincs.experiments import EXPERIMENTS_BY_DOMAIN

        self.assertEqual(EXPERIMENTS_BY_DOMAIN["nj2w"], {})
        arms = EXPERIMENTS_BY_DOMAIN["nj2w_bed2012"]
        twin = arms["p4-premier"]
        prem = arms["p4-premier+struct-cohansey-checkvalve+weir-dikes-levees"]
        b = EXPERIMENTS_BY_DOMAIN["v4_refreeze_swz_v11"][
            "p4-premier+weir-elizabeth-rahway"
        ]
        self.assertEqual(
            _changed(twin, b, ("name", "description")),
            {"subgrid_from", "waterlevel_geodataset", "n_waterlevel_support", "waves"},
        )
        self.assertEqual(_changed(twin.waves, b.waves), {"wavemaker_line"})
        self.assertEqual(twin.subgrid_from, "_subgrid_nj2_2012")
        self.assertEqual(twin.waterlevel_geodataset, "naccs_sandy_nj2")
        self.assertEqual(twin.n_waterlevel_support, 244)
        self.assertTrue(twin.waves.use_waves and twin.waves.wavemaker)
        self.assertEqual(
            twin.waves.wavemaker_line.name,
            "nj2_wavemaker_2012bed_5m_mhw_snapbeach.geojson",
        )
        self.assertTrue(twin.waves.wavemaker_line.is_file())
        self.assertEqual(
            _changed(prem, twin, ("name", "description")), {"weir_from", "drn_from"}
        )
        j3 = EXPERIMENTS_BY_DOMAIN["nj2_bed2012"][
            "p4-nowaves+rain-off+slr-0m+struct-cohansey-checkvalve+weir-dikes-levees"
        ]
        self.assertEqual((prem.weir_from, prem.drn_from), (j3.weir_from, j3.drn_from))
        self.assertTrue(prem.weir_from.is_file() and prem.drn_from.is_file())
        rainoff = arms[
            "p4-premier+rain-off+struct-cohansey-checkvalve+weir-dikes-levees"
        ]
        self.assertEqual(_changed(rainoff, prem, ("name", "description")), {"rain"})
        self.assertFalse(rainoff.rain)
        b_off = EXPERIMENTS_BY_DOMAIN["v4_refreeze_swz_v11"][
            "p4-premier+rain-off+weir-elizabeth-rahway"
        ]
        self.assertEqual(_changed(b_off, b, ("name", "description")), {"rain"})

    def test_followup_arms(self):
        """11-18: the Hell Gate test = the premier + a −0.25 m offset on the hell_gate arm; the 2026-bed premier =
        the same recipe, same name, on _subgrid_nj2_2026 (same weirs, drn and 2012-bed wavemaker line)."""
        from nj_sfincs.experiments import EXPERIMENTS_BY_DOMAIN

        name = "p4-premier+struct-cohansey-checkvalve+weir-dikes-levees"
        prem = EXPERIMENTS_BY_DOMAIN["nj2w_bed2012"][name]
        self.assertEqual(prem.boundary_arm_offsets, ())
        hg = EXPERIMENTS_BY_DOMAIN["nj2w_bed2012"][
            "p4-premier+struct-cohansey-checkvalve+tide-hellgate-m025+weir-dikes-levees"
        ]
        self.assertEqual(
            _changed(hg, prem, ("name", "description")), {"boundary_arm_offsets"}
        )
        self.assertEqual(hg.boundary_arm_offsets, (("hell_gate", -0.25),))
        self.assertIn(
            "hell_gate",
            {a.name for a in domain.DOMAINS["nj2w_bed2012"].boundary_arms},
        )
        parts = hg.name.split("+")
        self.assertEqual(
            parts[1:], sorted(parts[1:])
        )  # §6: deltas in alphabetical order
        # the 11-22 SLR map arms (calm) are tested in test_slr_arms_2026_bed, the 11-23 spin-up arms (cold_start) in
        # TestSpinupLead, the 11-24 North Wildwood bulkhead arms in test_nwbulkhead_weir_arms_2026_bed
        self.assertEqual(
            {
                k
                for k, e in EXPERIMENTS_BY_DOMAIN["nj2w_bed2026"].items()
                if e.calm is None and e.cold_start is None
            },
            {name, name + "+weir-nwbulkhead", name + "+weir-nwbulkhead+weir-seabright"},
        )
        b26 =EXPERIMENTS_BY_DOMAIN["nj2w_bed2026"][name]
        self.assertEqual(_changed(b26, prem, ("name", "description")), {"subgrid_from"})
        self.assertEqual(b26.subgrid_from, "_subgrid_nj2_2026")
        self.assertEqual(
            b26.waves, prem.waves
        )  # the 2012-bed wavemaker line (user 11-16)

    def test_waves_off_twin(self):
        """11-22: the rain-on waves-off twin = the 2.0 premier with SnapWave off, nothing else."""
        from nj_sfincs.experiments import EXPERIMENTS_BY_DOMAIN

        arms = EXPERIMENTS_BY_DOMAIN["nj2w_bed2012"]
        prem = arms["p4-premier+struct-cohansey-checkvalve+weir-dikes-levees"]
        tw = arms["p4-nowaves+struct-cohansey-checkvalve+weir-dikes-levees"]
        self.assertEqual(_changed(tw, prem, ("name", "description")), {"waves"})
        self.assertFalse(tw.waves.use_waves)
        self.assertTrue(tw.rain)
        parts = tw.name.split("+")
        self.assertEqual(parts[1:], sorted(parts[1:]))

    def test_seawall_arm(self):
        """11-22: the seawall-notch arm = the rain-off twin on _subgrid_nj2_2012_seawall, nothing else."""
        from nj_sfincs.experiments import EXPERIMENTS_BY_DOMAIN

        arms = EXPERIMENTS_BY_DOMAIN["nj2w_bed2012"]
        twin = arms["p4-premier+rain-off+struct-cohansey-checkvalve+weir-dikes-levees"]
        sw = arms["bed-seawall+p4-premier+rain-off+struct-cohansey-checkvalve+weir-dikes-levees"]
        self.assertEqual(_changed(sw, twin, ("name", "description")), {"subgrid_from"})
        self.assertEqual(sw.subgrid_from, "_subgrid_nj2_2012_seawall")
        parts = sw.name.split("+")
        self.assertEqual(parts, sorted(parts))

    def test_seabright_weir_arm(self):
        """11-23: the Sea Bright seawall arm = the rain-off twin with the seawall polylines APPENDED to the dike set's
        weir file, nothing else (logs/seabright_fable_2026-11-23/)."""
        from nj_sfincs.experiments import EXPERIMENTS_BY_DOMAIN

        arms = EXPERIMENTS_BY_DOMAIN["nj2w_bed2012"]
        twin = arms["p4-premier+rain-off+struct-cohansey-checkvalve+weir-dikes-levees"]
        sb = arms["p4-premier+rain-off+struct-cohansey-checkvalve+weir-dikes-levees+weir-seabright"]
        self.assertEqual(_changed(sb, twin, ("name", "description")), {"weir_from"})
        parts = sb.name.split("+")
        self.assertEqual(parts, sorted(parts))
        if sb.weir_from.is_file() and twin.weir_from.is_file():  # bulk data: absent on a bare checkout
            base, new = twin.weir_from.read_text(), sb.weir_from.read_text()
            self.assertTrue(new.startswith(base), "the dike set must be carried byte for byte")
            extra = new[len(base) :].splitlines()
            names = [ln for ln in extra if ln and not ln[0].isdigit() and not ln[0] == "-"]
            self.assertEqual(
                names, ["seabright_seawall_south_monmouth_beach", "seabright_seawall_north_sea_bright"]
            )
            rows = [ln.split() for ln in extra if len(ln.split()) == 4]
            self.assertEqual(len(rows), 373)
            crest = [float(r[2]) for r in rows]
            self.assertTrue(3.0 < min(crest) and max(crest) < 9.0, (min(crest), max(crest)))

    def test_seabright_weir_checks(self):
        """11-24: the two adoption checks = the rain-on waves-off twin and the rain-on 2.0 premier, each + the SAME
        seawall weir file as the rain-off arm, nothing else."""
        from nj_sfincs.experiments import EXPERIMENTS_BY_DOMAIN

        arms = EXPERIMENTS_BY_DOMAIN["nj2w_bed2012"]
        ref = arms["p4-premier+rain-off+struct-cohansey-checkvalve+weir-dikes-levees+weir-seabright"]
        for twin_name in (
            "p4-nowaves+struct-cohansey-checkvalve+weir-dikes-levees",
            "p4-premier+struct-cohansey-checkvalve+weir-dikes-levees",
        ):
            twin, arm = arms[twin_name], arms[twin_name + "+weir-seabright"]
            self.assertEqual(_changed(arm, twin, ("name", "description")), {"weir_from"})
            self.assertEqual(arm.weir_from, ref.weir_from)
            self.assertEqual(arm.name, twin_name + "+weir-seabright")
            parts = arm.name.split("+")
            self.assertEqual(parts[1:], sorted(parts[1:]))
            self.assertEqual(arm.rain, twin.rain)
            self.assertTrue(arm.rain)
        self.assertFalse(arms["p4-nowaves+struct-cohansey-checkvalve+weir-dikes-levees+weir-seabright"].waves.use_waves)

    def test_nwbulkhead_weir_arms_2026_bed(self):
        """11-24: the North Wildwood bulkhead (2.0.1 candidate, 2026 bed ONLY) = the 2026-bed premier + one polyline
        appended to its weir file (and, in the second arm, to the Sea Bright file), nothing else
        (logs/nw_bulkhead_2026-11-24/)."""
        from nj_sfincs.experiments import EXPERIMENTS_BY_DOMAIN

        arms = EXPERIMENTS_BY_DOMAIN["nj2w_bed2026"]
        twin_name = "p4-premier+struct-cohansey-checkvalve+weir-dikes-levees"
        twin = arms[twin_name]
        sb12 = EXPERIMENTS_BY_DOMAIN["nj2w_bed2012"][twin_name + "+weir-seabright"]
        for suffix, base_from in (
            ("+weir-nwbulkhead", twin.weir_from),
            ("+weir-nwbulkhead+weir-seabright", sb12.weir_from),
        ):
            arm = arms[twin_name + suffix]
            self.assertEqual(arm.name, twin_name + suffix)
            self.assertEqual(_changed(arm, twin, ("name", "description")), {"weir_from"})
            parts = arm.name.split("+")
            self.assertEqual(parts[1:], sorted(parts[1:]))
            self.assertTrue(arm.rain and arm.waves.use_waves)
            self.assertEqual(arm.subgrid_from, "_subgrid_nj2_2026")
            if arm.weir_from.is_file() and base_from.is_file():  # bulk data: absent on a bare checkout
                base, new = base_from.read_text(), arm.weir_from.read_text()
                self.assertTrue(new.startswith(base), "the base weir file must be carried byte for byte")
                extra = new[len(base) :].splitlines()
                self.assertEqual(extra[0], "north_wildwood_beachfront_bulkhead_2nd_16th_ave_2026bed")
                self.assertEqual(extra[1], "18 4")
                rows = [ln.split() for ln in extra[2:]]
                self.assertEqual(len(rows), 18)
                self.assertEqual({r[2] for r in rows}, {"3.660"})  # 12.0 ft NAVD88, city code ch. 178
                xy = [(float(r[0]), float(r[1])) for r in rows]
                self.assertTrue(all(517700 < x < 518500 and 4316150 < y < 4317000 for x, y in xy), xy)
        # the 2012 bed never gets it: the bulkhead postdates Sandy
        self.assertFalse([k for k in EXPERIMENTS_BY_DOMAIN["nj2w_bed2012"] if "nwbulkhead" in k])

    def test_slr_arms_2026_bed(self):
        """11-22: 1.1.0's eight normal-weather SLR arms re-issued on nj2w_bed2026 (logs/slr_2_0_2026-11-22/). Each
        is the 2026-bed premier made calm with the normal-weather weir; the tide arms differ from the +0 ft arm ONLY
        in the boundary file + its offset / start level, the still arms from each other only in the still level."""
        from pathlib import Path

        from nj_sfincs.experiments import EXPERIMENTS_BY_DOMAIN

        arms = EXPERIMENTS_BY_DOMAIN["nj2w_bed2026"]
        v11 = EXPERIMENTS_BY_DOMAIN["v4_refreeze_swz_v11"]
        prem = arms["p4-premier+struct-cohansey-checkvalve+weir-dikes-levees"]
        # the 11-23 NOAA-cuts A/B pair (short window) is tested in test_noaacuts_ab_arms
        # ... and the 11-24 per-gauge SLR variants in test_boundary_point_offsets
        calm = {
            k: e
            for k, e in arms.items()
            if e.calm is not None and "-spring6d" not in k and e.boundary_point_offsets is None
        }
        # the same set as 1.1.0's normal-weather arms, `bed-modernb+` dropped (this domain IS the 2026 bed)
        want = {
            k.removeprefix("bed-modernb+")
            for k in v11
            if k.startswith("bed-modernb+") and k.endswith("+weir-normalweather")
        }
        self.assertEqual(set(calm), want)
        self.assertEqual(len(calm), 8)
        for k, e in calm.items():
            self.assertEqual(e.name, k)
            parts = k.split("+")
            self.assertEqual(parts, sorted(parts))  # §6
            self.assertEqual(
                _changed(e, prem, ("name", "description")),
                {"waves", "weir_from", "meteo_from", "rain", "infiltration", "cnb_effective", "calm"},
            )
            self.assertFalse(e.waves.use_waves or e.rain or e.infiltration)
            self.assertIsNone(e.meteo_from)
            self.assertEqual(e.weir_from.name, "sfincs_modern_normalweather_dikes_levees_cohansey_nj2.weir")
            self.assertTrue(e.weir_from.is_file())
            self.assertEqual((e.drn_from, e.subgrid_from), (prem.drn_from, "_subgrid_nj2_2026"))
            self.assertEqual((e.waterlevel_geodataset, e.n_waterlevel_support), ("naccs_sandy_nj2", 244))
            # the same CalmForcing as the 1.1.0 twin, except where the nj2 boundary must differ
            c11 = v11["bed-modernb+" + k].calm
            if e.calm.boundary == "mhhw":
                self.assertEqual(e.calm, c11)
            else:
                self.assertEqual(
                    dataclasses.replace(e.calm, boundary=c11.boundary, level_m=c11.level_m, offset_m=c11.offset_m),
                    c11,
                )
                self.assertIn("/nj2/sfincs_netbndbzsbzifile_tide_ec2015_nj2_", e.calm.boundary)
                self.assertEqual(
                    Path(e.calm.boundary).name.removeprefix("sfincs_netbndbzsbzifile_tide_ec2015_nj2_"),
                    Path(c11.boundary).name.removeprefix("sfincs_netbndbzsbzifile_tide_ec2015_"),
                )
                self.assertAlmostEqual(e.calm.level_m, round(e.calm.offset_m - 0.077, 3))
                if "msl2026" not in k:  # uniform offsets: the 1.1.0 values; msl2026's mean moves with the points
                    self.assertEqual(e.calm.offset_m, c11.offset_m)
        z = calm["tide-0ft+weir-normalweather"]
        for k, e in calm.items():
            if e.calm.boundary == "mhhw" or e is z:
                continue
            self.assertEqual(_changed(e, z, ("name", "description")), {"calm"})
            self.assertEqual(_changed(e.calm, z.calm), {"offset_m", "boundary", "level_m"})
        s2, s4 = calm["still-2ft+weir-normalweather"], calm["still-4ft+weir-normalweather"]
        self.assertEqual(_changed(s4, s2, ("name", "description")), {"calm"})
        self.assertEqual(_changed(s4.calm, s2.calm), {"offset_m"})

    def test_noaacuts_ab_arms(self):
        """11-23: the NOAA-cuts A/B (logs/noaa_cuts_2026-11-23/): two calm arms = tide-0ft-msl2026 on a 6.5-day window
        with hourly zs / zsmax, differing from each other ONLY in the boundary file; the A arm's file is the SLR
        arm's own, the B arm's its NOAA-cuts twin."""
        from pathlib import Path

        from nj_sfincs.experiments import EXPERIMENTS_BY_DOMAIN, NOAACUTS_AB_WINDOW

        arms = EXPERIMENTS_BY_DOMAIN["nj2w_bed2026"]
        slr = arms["tide-0ft-msl2026+weir-normalweather"]
        a = arms["tide-0ft-msl2026-spring6d+weir-normalweather"]
        b = arms["tide-0ft-msl2026-noaacuts-spring6d+weir-normalweather"]
        # the A/B pair only: the 11-23 Hackensack bed variants (bed-hack1915*) reuse A's window on purpose
        self.assertEqual({k for k in arms if "-spring6d" in k and not k.startswith("bed-")}, {a.name, b.name})
        for e in (a, b):
            self.assertEqual(e.name.split("+"), sorted(e.name.split("+")))  # §6
            self.assertEqual(_changed(e, slr, ("name", "description")), {"calm"})
            self.assertEqual(
                dataclasses.replace(e.calm, boundary=slr.calm.boundary, tstop=slr.calm.tstop, dtmapout=slr.calm.dtmapout,
                                    dtmaxout=slr.calm.dtmaxout),
                slr.calm,
            )
            self.assertEqual((e.calm.tstart, e.calm.tstop), NOAACUTS_AB_WINDOW)
            self.assertEqual((e.calm.dtmapout, e.calm.dtmaxout), (3600.0, 3600.0))
            self.assertEqual(21600.0 % e.calm.dtmaxout, 0.0)  # dtmaxout must divide dtrstout (CLAUDE.md §4)
        self.assertEqual(a.calm.boundary, slr.calm.boundary)
        self.assertEqual(_changed(b, a, ("name", "description")), {"calm"})
        self.assertEqual(_changed(b.calm, a.calm), {"boundary"})
        self.assertEqual(Path(b.calm.boundary).parent.name, "nj2_noaacuts")
        self.assertEqual(
            Path(b.calm.boundary).name.replace("noaacuts", "ec2015"), Path(a.calm.boundary).name
        )
        if not Path(b.calm.boundary).is_file():
            self.skipTest("scratch tide files not visible here")
        import numpy as np
        import xarray as xr

        with xr.open_dataset(a.calm.boundary, decode_times=False) as fa, xr.open_dataset(
            b.calm.boundary, decode_times=False
        ) as fb:
            for v in ("time", "x", "y", "stations"):
                self.assertTrue(np.array_equal(fa[v].values, fb[v].values), v)
            same = (fa.zs.values == fb.zs.values).all(axis=0)
        self.assertEqual(int(same.sum()), 215)  # only the 29 cut points (16 hell_gate + 13 hudson) differ


class TestSpinupLead(unittest.TestCase):
    """11-23: the spin-up lead test (logs/spinup_test_2026-11-23/): five cold starts of the 2026-bed premier with
    waves off, differing from each other ONLY in ``cold_start.tstart``; ``apply_cold_start`` moves tstart (and
    dtmaxout) in the written inp and nothing else."""

    INP = (
        "tref                 = 20121028 000000\n"
        "tstart               = 20121028 000000\n"
        "tstop                = 20121031 000000\n"
        "tspinup              = 3600.0\n"
        "dtmaxout             = 21600.0\n"
        "dtrstout             = 21600.0\n"
        "zsini                = 0.0\n"
        "inifile              = sfincs_ini_regional.bin\n"
        "snapwave             = 0\n"
    )

    def test_arms(self):
        from datetime import datetime, timedelta

        from nj_sfincs.config import ColdStart
        from nj_sfincs.experiments import EXPERIMENTS_BY_DOMAIN, SPINUP_LEADS

        arms = EXPERIMENTS_BY_DOMAIN["nj2w_bed2026"]
        prem = arms["p4-premier+struct-cohansey-checkvalve+weir-dikes-levees"]
        spin = {k: e for k, e in arms.items() if e.cold_start is not None}
        self.assertEqual(len(spin), 5)
        self.assertEqual(sorted(SPINUP_LEADS), [6, 12, 24, 36, 49])
        peak = datetime(2012, 10, 30, 1)
        ref = arms["p4-nowaves+spin-lead49h+struct-cohansey-checkvalve+weir-dikes-levees"]
        self.assertEqual(ref.cold_start, ColdStart("20121028 000000", 3600.0))  # the template's own tstart
        for lead, t0 in SPINUP_LEADS.items():
            k = f"p4-nowaves+spin-lead{lead:02d}h+struct-cohansey-checkvalve+weir-dikes-levees"
            e = spin[k]
            self.assertEqual(e.name, k)
            parts = k.split("+")
            self.assertEqual(parts, sorted(parts))  # §6
            self.assertEqual(_changed(e, prem, ("name", "description")), {"waves", "cold_start"})
            self.assertEqual(e.waves.use_waves, False)
            self.assertTrue(e.rain and e.infiltration)
            self.assertEqual(datetime.strptime(e.cold_start.tstart, "%Y%m%d %H%M%S"), peak - timedelta(hours=lead))
            self.assertEqual(e.cold_start.dtmaxout, 3600.0)
            if e is not ref:
                self.assertEqual(_changed(e, ref, ("name", "description")), {"cold_start"})
                self.assertEqual(_changed(e.cold_start, ref.cold_start), {"tstart"})
        # no other arm carries a cold start, and the field stays out of every repr
        for d, xs in EXPERIMENTS_BY_DOMAIN.items():
            for k, e in xs.items():
                self.assertNotIn("cold_start", repr(e))
                if d != "nj2w_bed2026" or k not in spin:
                    self.assertIsNone(e.cold_start, (d, k))

    def test_apply_cold_start(self):
        import json
        import tempfile
        from pathlib import Path

        from nj_sfincs import model
        from nj_sfincs.config import ColdStart

        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "sfincs.inp").write_text(self.INP)
            (d / "provenance.txt").write_text("staged\n")
            rec = model.apply_cold_start(d, ColdStart("20121029 190000"))
            before = {k.strip(): v.strip() for k, v in (ln.split("=", 1) for ln in self.INP.splitlines())}
            after = model._inp_keys(d / "sfincs.inp")
            self.assertEqual({k for k in after if after[k] != before.get(k)}, {"tstart", "dtmaxout"})
            self.assertEqual((after["tstart"], after["dtmaxout"]), ("20121029 190000", "3600.0"))
            self.assertEqual(json.loads((d / model.COLD_START_META).read_text()), rec)
            self.assertEqual((rec["hours_after_tref"], rec["run_hours"]), (43.0, 29.0))
            prov = (d / "provenance.txt").read_text()
            self.assertTrue(prov.startswith("staged\n") and "cold_start = tstart 20121029 190000" in prov)
            # the template's own tstart is a legal reference
            (d / "sfincs.inp").write_text(self.INP)
            model.apply_cold_start(d, ColdStart("20121028 000000"))
            for bad in (
                ColdStart("20121027 230000"),  # before tref: no forcing
                ColdStart("20121031 000000"),  # at tstop
                ColdStart("20121029 190000", 5000.0),  # does not divide the restart cadence
            ):
                (d / "sfincs.inp").write_text(self.INP)
                with self.assertRaises(SystemExit, msg=repr(bad)):
                    model.apply_cold_start(d, bad)
            (d / "sfincs.inp").write_text(self.INP + "rstfile              = sfincs.20121029.000000.rst\n")
            with self.assertRaises(SystemExit):
                model.apply_cold_start(d, ColdStart("20121029 190000"))


class TestNJ2WOldcut(unittest.TestCase):
    """nj2w_oldcut (2026-11-22, the harbour CSI-dip Experiment 1): nj2w's mesh with Model 1.1.0's ring and forced
    Narrows / KvK-east lines; nj2w_oldcut_bed2012 its 2012-bed face-z domain. logs/csi_dip_design_2026-11-22/."""

    MASK_AND_LINES = {
        "region",
        "region_source",
        "boundary_arms",
        "mask_overrides",
        "obs_gauges",
        "dry_land_boxes_ll",
        "flux_crosssections",
    }

    def test_differs_from_nj2w_only_in_mask_and_forcing_lines(self):
        w, o = domain.DOMAINS["nj2w"], domain.DOMAINS["nj2w_oldcut"]
        self.assertEqual(_changed(o, w), {"name"} | self.MASK_AND_LINES)
        self.assertEqual(o.mesh_key, "nj2")
        self.assertEqual(o.frozen_mesh_dir(), w.frozen_mesh_dir())
        # 1.1.0's ring, verbatim
        self.assertEqual((o.region, o.region_source), (V11.region, V11.region_source))
        # 2.0's sea sections (v4's vertices) + 1.1.0's three box arms, in 1.1.0's order; no 2.0 cut
        sea = [a for a in w.boundary_arms if a.line and a.name not in ("hudson", "hell_gate")]
        self.assertEqual(list(o.boundary_arms[: len(sea)]), sea)
        self.assertEqual(
            [a.name for a in o.boundary_arms[len(sea) :]], ["narrows", "kvk_east", "cd_canal"]
        )
        v11_box = {a.name: a for a in V11.boundary_arms if not a.line}
        for a in o.boundary_arms[len(sea) :]:
            b = v11_box[a.name]
            self.assertEqual(
                _changed(a, b, ("min_cells", "max_cells")), set(), a.name
            )  # same box / type / bed rule
            self.assertLessEqual(a.min_cells, a.max_cells)
        # 1.1.0's walls (wall_bayonne back) + 2.0's Millville wall; none of the walls on the dropped ground
        names = [m.name for m in o.mask_overrides]
        self.assertEqual(o.mask_overrides[: len(V11.mask_overrides)], V11.mask_overrides)
        self.assertEqual(names[len(V11.mask_overrides) :], ["wall_millville_east"])
        self.assertIn("wall_bayonne", names)
        for gone in ("wall_e88", "wall_hellgate_east", "wall_astoria_park"):
            self.assertNotIn(gone, names)
        # 1.1.0's 48 gauges + Bergen Point + HUD-002 (both inside 1.1.0's ring)
        self.assertEqual(o.obs_gauges[:48], V11.obs_gauges)
        self.assertEqual(
            [g.name for g in o.obs_gauges[48:]], ["noaa_bergen_point", "sss_hackensack_hud002"]
        )
        self.assertEqual(o.dry_land_boxes_ll, V11.dry_land_boxes_ll)
        self.assertTrue(o.flux_crosssections.exists())
        crs = o.flux_crosssections.read_text().split()
        for s in ("barrier", "throat", "kvk", "newark_bay_s", "arthur_kill_carteret"):
            self.assertIn(s, crs)
        for s in ("narrows", "hudson_cut", "hell_gate_cut"):
            self.assertNotIn(s, crs)

    def test_bed_domain_is_oldcut_plus_face_z(self):
        o, b = domain.DOMAINS["nj2w_oldcut"], domain.DOMAINS["nj2w_oldcut_bed2012"]
        self.assertEqual(_changed(b, o), {"name", "face_z_from"})
        self.assertEqual(b.face_z_from, "_subgrid_nj2_2012")
        # = the 2.0 domain it is paired with, bar the mask / forcing lines
        self.assertEqual(
            _changed(b, domain.DOMAINS["nj2w_bed2012"]), {"name"} | self.MASK_AND_LINES
        )

    def test_fingerprints_registered_same_mesh_new_sha(self):
        w = premier.EXPECTED["nj2w"]
        for name in ("nj2w_oldcut", "nj2w_oldcut_bed2012"):
            fp = premier.EXPECTED[name]
            self.assertEqual(fp.n_faces, w.n_faces, name)
            self.assertNotEqual(fp.sha_z_mask, w.sha_z_mask, name)
            self.assertIn(fp, premier.KNOWN, name)
        self.assertNotEqual(
            premier.EXPECTED["nj2w_oldcut"].sha_z_mask,
            premier.EXPECTED["nj2w_oldcut_bed2012"].sha_z_mask,
        )

    def test_arm_differs_from_the_twin_only_in_what_the_domain_forces(self):
        from nj_sfincs.experiments import EXPERIMENTS_BY_DOMAIN

        self.assertEqual(EXPERIMENTS_BY_DOMAIN["nj2w_oldcut"], {})
        arms = EXPERIMENTS_BY_DOMAIN["nj2w_oldcut_bed2012"]
        name = "p4-nowaves+struct-cohansey-checkvalve+weir-dikes-levees"
        self.assertEqual(set(arms), {name})
        twin = EXPERIMENTS_BY_DOMAIN["nj2w_bed2012"][name]
        x = arms[name]
        self.assertEqual(x.name, twin.name)
        self.assertEqual(
            _changed(x, twin, ("description",)),
            {"waterlevel_geodataset", "n_waterlevel_support"},
        )
        # 1.1.0's NACCS file and count (its own arms declare the same pair)
        v11 = EXPERIMENTS_BY_DOMAIN["v4_refreeze_swz_v11"]["p4-nowaves+weir-elizabeth-rahway"]
        self.assertEqual(
            (x.waterlevel_geodataset, x.n_waterlevel_support),
            (v11.waterlevel_geodataset, v11.n_waterlevel_support),
        )
        self.assertFalse(x.waves.use_waves)
        self.assertTrue(x.rain)
        self.assertEqual(x.subgrid_from, "_subgrid_nj2_2012")


if __name__ == "__main__":
    unittest.main()
