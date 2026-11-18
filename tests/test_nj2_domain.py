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


if __name__ == "__main__":
    unittest.main()
