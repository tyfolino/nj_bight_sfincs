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
                "building",
                "n_waterlevel_support",
                "coarse_elevation_list",
                "boundary_arms",
                "mask_overrides",
                "dry_land_boxes_ll",
                "hwm_rules",
                "hwm_geojson",
                "map_windows",
                "waterlevel_line",  # data/nj2_design/waterlevel_line_nj2.csv: v4's vertices
                "obs_gauges",  # + 7 (the Battery, Bergen Point, 3 STN sensors, 2 cut diagnostics)
            },
        )

    def test_building_state(self):
        self.assertTrue(NJ2.building)
        self.assertIsNone(NJ2.mesh_key)
        self.assertIsNone(NJ2.face_z_from)
        self.assertIsNone(NJ2.n_waterlevel_support)
        self.assertNotIn("nj2", premier.EXPECTED)
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

        verts = {n: (lo, la) for n, lo, la in domain.read_waterlevel_line(NJ2.region_source)}
        t = Transformer.from_crs(4326, NJ2.epsg, always_xy=True)
        arms = {a.name: a for a in NJ2.boundary_arms}
        for arm, (v0, v1) in {
            "hudson": ("hudson_w", "hudson_e"),
            "hell_gate": ("hellgate_w", "hellgate_e"),
        }.items():
            x0, y0, x1, y1 = arms[arm].box
            for v in (v0, v1):
                x, y = t.transform(*verts[v])
                self.assertTrue(x0 + 250 < x < x1 - 250 and y0 + 250 < y < y1 - 250, (arm, v))
        self.assertEqual(verts["hudson_w"], (-73.95753, 40.86))  # user 11-04: 45 m W
        self.assertEqual(verts["astoria"], (-73.92297, 40.76945))  # user 11-03: inland

    def test_gauges(self):
        v11 = list(V11.obs_gauges)
        self.assertEqual(list(NJ2.obs_gauges[: len(v11)]), v11)
        new = [g.name for g in NJ2.obs_gauges[len(v11):]]
        self.assertEqual(
            new,
            ["noaa_battery", "noaa_bergen_point", "sss_gowanus", "sss_hoboken",
             "sss_hackensack_hud002", "bc_hudson_cut", "bc_hell_gate"],
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
        hp = domain.read_waterlevel_line(domain.DATA / "v4_design" / "region_v4_hot_plus_vertices.csv")
        nj = domain.read_waterlevel_line(NJ2.region_source)
        gone = {n for n, *_ in hp} - {n for n, *_ in nj}
        self.assertEqual(
            gone, {f"hudson_route_{i:02d}" for i in range(3, 22)} | {"narrows_w", "narrows_e"}
        )
        kept = {n: (lo, la) for n, lo, la in hp}
        for n, lo, la in nj:
            if n in kept:
                self.assertEqual(kept[n], (lo, la), n)

    def test_basin_rules_first_and_no_1x_mark_moves(self):
        import geopandas as gpd

        names = domain.hwm_basin_names(NJ2)
        self.assertEqual(names[:4], ("upper_bay_islands", "hudson_nj", "east_river", "upper_bay_ny"))
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
        self.assertEqual(NJ2.motf_exclude_boxes_ll, ())

    def test_bed_tiers(self):
        self.assertEqual(NJ2.elevation_list, domain.V4_ELEVATION_LIST)
        self.assertEqual(NJ2.coarse_elevation_list, ({"elevation": "bed_nj2_coarse_25m"},))


if __name__ == "__main__":
    unittest.main()
