
# ═══════════════════════════════════════════════════════════════════════════════
# nj2 — MODEL 2.0 (user 2026-11-14: domain name `nj2`). A NEW MESH (CLAUDE.md §6: 2.0 = a new
# mesh). BUILDING since 2026-11-14: ring drawn and walked, no frozen mesh / fingerprint yet.
# ═══════════════════════════════════════════════════════════════════════════════
# = 1.1.0's domain (V4_REFREEZE_SWZ_V11: v4_refreeze's river cuts at today's head of tide,
# leak walls, the Lewes edge, Keansburg / Overpeck weirs as hand-placed files) with the Upper
# Bay, the Kill van Kull, the Hudson to 40.860 and the East River to Hell Gate COMPUTED:
#   * the `narrows` and `kvk_east` forced arms and the `wall_bayonne` wall are DROPPED;
#   * two short forced cuts instead, read from NACCS points on them: `hudson` (the Hudson at
#     40.860, hudson_w -> hudson_e, 1,941 m) and `hell_gate` (the East River just below the
#     Harlem's mouth, hellgate_w -> hellgate_e, 684 m). Structural argument, as the Narrows
#     move was: each cut is one short section read from NACCS points ON it, nothing is
#     interpolated across a basin (logs/hudson_design_2026-11-02/README.md, decisions 11-03);
#   * the ring (`data/nj2_design/region_nj2_vertices.csv`) follows the Manhattan spine and the
#     Queens / Brooklyn moraine; Manhattan, Brooklyn and Queens are computed COARSE (refinement
#     option B, NY side coarse; no NY buildings — user 11-03);
#   * two declared walls on low ring ground (`wall_e88`, `wall_hellgate_east`; user 11-03 /
#     11-04, walked at 1 m on 1/9" CUDEM: logs/v2_prep_2026-11-04/README.md §3).
# One registered MESH domain (`nj2`, face z = the coarse 25 m bed) and, after the freeze, one
# FACE-Z domain per bed — `nj2_bed2012`, `nj2_bed2026` (user 2026-11-14) — same faces, same
# boundary edges, only the sha differs (2.0.0 is ONE version with two bed options, user 11-03).
# Record: logs/nj2_freeze_2026-11-14/README.md.

#: The drawn SEA line (boundary agent, 2026-11-14): v4's vertices byte for byte under an nj2 header —
#: nj2 changes nothing south of the Narrows. Its four sections, brackets and sea closure carry over.
_NJ2_WATERLEVEL_LINE = DATA / "nj2_design" / "waterlevel_line_nj2.csv"
#: The two new cuts: SEPARATE two-vertex files (the sea line is one path that also closes the sea
#: polygon, so the cuts cannot be appended to it), each a one-section line arm (flat ends: the
#: walls they meet are nobody's).
_NJ2_CUT_HUDSON = DATA / "nj2_design" / "cut_hudson_nj2.csv"
_NJ2_CUT_HELL_GATE = DATA / "nj2_design" / "cut_hell_gate_nj2.csv"
#: v4's sea-line corridor (500 m; edges agent 11-14). 50 m water faces at both cuts, so a face on
#: the line is within ~35 m of it; nothing else forced lies within 9 km; the flat ends keep the
#: walls the cuts meet out of the forced set.
_NJ2_CUT_CORRIDOR_M = _V4_LINE_CORRIDOR_M
_NJ2_SEA_SECTIONS = (
    ("delaware_mouth", "cape_henlopen"),
    ("ocean", "sp_5531"),
    ("lower_bay_entrance", "sp_3767"),
    ("rockaway_inlet", "sp_3903"),
)
_V4_LINE_ARM = {a.name: a for a in V4.boundary_arms if a.line}
_NJ2_SEA_ARMS = waterlevel_line_arms(
    _NJ2_WATERLEVEL_LINE,
    32618,
    tuple((n, first, _V4_LINE_ARM[n].why) for n, first in _NJ2_SEA_SECTIONS),
    corridor_m=_V4_LINE_CORRIDOR_M,
    counts={n: (_V4_LINE_ARM[n].min_cells, _V4_LINE_ARM[n].max_cells) for n, _ in _NJ2_SEA_SECTIONS},
)
#: Cell counts UNBRACKETED (1..10,000) until the first clean mesh probe, then tightened (v4's
#: practice, 09-27 probe -> 09-28 freeze).
_NJ2_CUT_ARMS = waterlevel_line_arms(
    _NJ2_CUT_HUDSON,
    32618,
    (
        (
            "hudson",
            "hudson_w",
            "The Hudson at 40.860, ~1 km above the GWB: hudson_w (-73.95753; 45 m W of the "
            "design vertex so the Palisades-foot bank is inside the line, user 11-04) -> hudson_e "
            "(Fort Tryon ridge), 1,941 m, ~1,400 m of it water. NACCS 4481 / 4471 / 4487 "
            "0.30-0.64 km off the line (logs/nj2_edges_2026-11-14/naccs_cuts_nj2.csv). 330 m of "
            "low bank inside the line is forced (accepted, user 11-03). Upriver is OUT; it acts "
            "only through NACCS here.",
        ),
    ),
    corridor_m=_NJ2_CUT_CORRIDOR_M,
) + waterlevel_line_arms(
    _NJ2_CUT_HELL_GATE,
    32618,
    (
        (
            "hell_gate",
            "hellgate_w",
            "The East River at Hell Gate, just below the Harlem's mouth: hellgate_w (Carl "
            "Schurz Park) -> hellgate_e (Hallets Point), 684 m, ~544 m water. NACCS 19080 / "
            "11877 ON the line, 11892 0.33 km off. The Harlem and Long Island Sound are OUT. "
            "NACCS may run ~0.2 m high here (one mark; a 2.1 note, user 11-03).",
        ),
    ),
    corridor_m=_NJ2_CUT_CORRIDOR_M,
)
#: Declared walls on low ring ground (frm 3 -> 1): the run's UTM envelope + 150 m, rounded out.
#: Both also lie within `wall_outflow_near_forced_m` (500 m) of a forced cut; declared anyway,
#: so they hold if that rule changes.
_NJ2_WALLS = (
    MaskOverride(
        "wall_e88",
        frm=3,
        to=1,
        box=(588_800, 4_514_300, 589_400, 4_514_800),
        why="e88 -> hellgate_w, 385-644 m of the 691 m leg: 261 m of 3.22 m ground (Yorkville / "
        "East End Ave). Reached from inside only at 8.4-10.4 m but from OUTSIDE at 6.44 m, so "
        "under the ring rule it stays a wall (user 11-03 decision 5).",
    ),
    MaskOverride(
        "wall_hellgate_east",
        frm=3,
        to=1,
        box=(589_700, 4_514_200, 590_300, 4_514_800),
        why="hellgate_e -> astoria, 0-300 m: Astoria's low bank (low point 2.02 m) beside the "
        "Hell Gate cut, the ONLY ring ground below 6.44 m reached from inside (1 m walk on 1/9\" "
        "CUDEM, logs/v2_prep_2026-11-04/README.md §3).",
    ),
)
#: Dropped from 1.1.0 (the Upper Bay is computed now).
_NJ2_DROPPED_ARMS = ("narrows", "kvk_east")
_NJ2_DROPPED_WALLS = ("wall_bayonne",)

#: Four HWM basin rules placed FIRST (logs/v2_validation_2026-11-03/README.md §1): without them
#: 64 of the 69 new marks (Manhattan, Brooklyn, Queens included) fall into `newark_bay`, which
#: has no east limit short of x 590 km. Checked: no 1.x mark changes basin
#: (basin_rules_check.py). The NJ / NY line is a straight fit between the marks on the two
#: banks, NOT the legal state line.
_NJ2_STATE_LINE = dict(slope_x0=582_800, slope_y0=4_510_000, slope=0.41)
_NJ2_SPINE = dict(slope_x0=583_600, slope_y0=4_506_400, slope=0.387)
_NJ2_BASIN_RULES = (
    BasinRule(
        "upper_bay_islands",
        xmin=580_300,
        xmax=581_400,
        ymin=4_504_600,
        ymax=4_506_100,
        why="Liberty + Ellis Islands: NY ground in NJ waters, west of the state line",
    ),
    BasinRule(
        "hudson_nj",
        xmin=579_000,
        ymin=4_504_500,
        ymax=4_520_000,
        side=-1,
        **_NJ2_STATE_LINE,
        why="NJ Hudson bank, Liberty State Park → Edgewater; Overpeck / Hackensack marks lie "
        "west of x 579 km or north of y 4 520 km",
    ),
    BasinRule(
        "east_river",
        ymin=4_506_300,
        ymax=4_516_000,
        side=+1,
        **_NJ2_SPINE,
        why="East of the Manhattan spine: Seaport, DUMBO, LES, Williamsburg, Newtown Creek, "
        "LIC, Astoria (Hell Gate cut at y ~4 514.6 km)",
    ),
    BasinRule(
        "upper_bay_ny",
        ymin=4_498_500,
        ymax=4_521_000,
        side=+1,
        **_NJ2_STATE_LINE,
        why="Brooklyn Upper Bay shore, the Battery, Manhattan's Hudson side",
    ),
)

#: Gauges the nj2 ring brings inside (the obs agent's table, data/nj2_design/obs_nj2.csv, "nj2 ADDED"
#: rows; 1.1.0's 48 unchanged). Two scored holdouts (the Battery, Bergen Point), three STN sensor
#: points with no pulled series (model output only), two boundary diagnostics ~110 m inside the cuts
#: (they read the imposed NACCS level: FORCING diagnostics, never holdouts). Not nudged: placed at the
#: published points; read their faces on the frozen mesh (CLAUDE.md §5) before scoring a tide.
_NJ2_NEW_GAUGES = (
    ObsGauge(
        "noaa_battery",
        -74.0142,
        40.7006,
        "surge",
        _NOAA_6MIN,
        "waterlevel",
        8518750,
        survives_crest=True,
        note="INTERIOR in nj2 (10.4 km from the Hell Gate cut, 18.3 km from the Hudson cut): a "
        "holdout of the MODEL, not of the boundary PRODUCT (NACCS was presumably validated "
        "against it; NACCS - obs peak -0.03 m). Peak 3.44 m NAVD88 10-30 01:24 UTC. Was a forcing "
        "input / outside on v1.5-v4.",
    ),
    ObsGauge(
        "noaa_bergen_point",
        -74.1463,
        40.6391,
        "surge",
        "nj2_design/obs_nj2_bergen_point_6min.nc",
        "waterlevel",
        8519483,
        survives_crest=True,
        note=_MLLW_TIE
        + ": NAVD88 = MLLW - 0.846 (station MSL-MLLW 1983-2001) + VDatum LMSL->NAVD88 at the "
        "point. KvK west mouth / Newark Bay: inside v4 too but unscored (no NAVD88). Peak 3.54 m "
        "(derived) 10-30 01:24; NACCS - obs -0.23 m. Position from CO-OPS metadata.",
    ),
    ObsGauge(
        "sss_gowanus",
        -73.98984,
        40.67688,
        note="USGS STN sensor SSS-NY-KIN (Gowanus), OFR 2013-1043: MODEL OUTPUT ONLY until its "
        "series is pulled. Published peak 3.38 m NAVD88 (11.08 ft).",
    ),
    ObsGauge(
        "sss_hoboken",
        -74.0232,
        40.7439,
        note="USGS STN SSS-NJ-HUD-001WL (Hoboken): sensor DAMAGED, no record (SIR 2016-5085 "
        "Table 4). Model output only, at the new NJ area's headline community.",
    ),
    ObsGauge(
        "sss_hackensack_hud002",
        -74.0661,
        40.7998,
        note="USGS STN SSS-NJ-HUD-002WL: peak 2.68 m NAVD88 (8.8 ft, SIR 2016-5085 Table 4), "
        "series not pulled; model output only. 180 m from mark 6095 (2.53 m).",
    ),
    ObsGauge(
        "bc_hudson_cut",
        -73.946,
        40.859,
        note="~110 m inside the hudson forced line: reads the imposed NACCS level. A FORCING "
        "diagnostic, never a holdout.",
    ),
    ObsGauge(
        "bc_hell_gate",
        -73.9385,
        40.776,
        note="~110 m inside the hell_gate forced line (the ~0.2 m NACCS question, hudson_design "
        "§6). A FORCING diagnostic, never a holdout.",
    ),
)

NJ2 = replace(
    V4_REFREEZE_SWZ_V11,
    name="nj2",
    region=DATA / "region_nj2.geojson",
    region_source=DATA / "nj2_design" / "region_nj2_vertices.csv",
    # 🔴 PLACEHOLDER path: the refinement agent's file (v4's recipe + Hudson band option B + a
    # Newark / Meadowlands NJ band + finer Cape May inlets, user 11-14). Read only at build.
    refinement=DATA / "nj2_design" / "refinement_nj2.geojson",
    mesh_key=None,  # its own data/frozen_mesh_nj2
    face_z_from=None,  # the mesh domain: face z = the coarse bed (the bed domains set it)
    building=True,  # cleared at the freeze, with the fingerprint and the support count
    n_waterlevel_support=None,  # asserted on the real mesh at the freeze
    # Same tier list as v4 / 1.x: the NY ground is CUDEM 1/9" (cudem_nj_v3 holds the 2015v1 NY
    # tiles) over 3DEP / GMRT. The 2012 Hudson channel (HD_HUD), the Brooklyn creek carves and
    # the pier carves are OVERLAYS in the 2012-bed recipe, never prepended (CLAUDE.md §5).
    elevation_list=V4_ELEVATION_LIST,
    coarse_elevation_list=({"elevation": "bed_nj2_coarse_25m"},),
    waterlevel_line=_NJ2_WATERLEVEL_LINE,
    obs_gauges=V4_REFREEZE_SWZ_V11.obs_gauges + _NJ2_NEW_GAUGES,
    boundary_arms=_NJ2_SEA_ARMS
    + tuple(
        a
        for a in V4_REFREEZE_SWZ_V11.boundary_arms
        if not a.line and a.name not in _NJ2_DROPPED_ARMS
    )
    + _NJ2_CUT_ARMS,
    mask_overrides=tuple(
        o
        for o in V4_REFREEZE_SWZ_V11.mask_overrides
        if o.name not in _NJ2_DROPPED_WALLS
    )
    + _NJ2_WALLS,
    # Positive checks on the new ground (CLAUDE.md §5: only a positive check finds a bed that
    # is present and wrong). min over each box on CUDEM 1/9" 2026-11-14: Prospect Park 19.0 m
    # (its lake), Green-Wood 5.8 m (a pond; p1 5.8, median 38), Jersey City Heights 27.1 m.
    dry_land_boxes_ll=V4_REFREEZE_SWZ_V11.dry_land_boxes_ll
    + (
        (
            "prospect_park",
            (-73.9760, 40.6600, -73.9660, 40.6700),
            10.0,
            "Prospect Park, Brooklyn moraine (CUDEM min 19.0, median 42.4 m) — new NY "
            "ground inside the nj2 ring.",
        ),
        (
            "green_wood_cemetery",
            (-74.0000, 40.6500, -73.9880, 40.6580),
            5.0,
            "Green-Wood Cemetery (CUDEM min 5.8 m at a pond, median 38.2 m).",
        ),
        (
            "jersey_city_heights",
            (-74.0580, 40.7400, -74.0480, 40.7500),
            15.0,
            "Jersey City Heights on the Bergen ridge (CUDEM min 27.1, median 40.2 m) — was "
            "the v4 ring's edge, interior now.",
        ),
    ),
    hwm_rules=_NJ2_BASIN_RULES + V4_REFREEZE_SWZ_V11.hwm_rules,
    # 276 marks = the 1.x file's 206 + 70 (69 new-area + BER-415 from SIR 2016-5085 Table 5);
    # headline 163 (q <= 2 inside the ring). logs/v2_prep_2026-11-04/README.md §4 (promoted
    # there as sandy_hwms_v2.geojson; copied byte-identical, md5 1e0214e9…).
    hwm_geojson=DATA / "validation_nj2" / "sandy_hwms_nj2.geojson",
    # MOTF: unchanged (user 11-03 decision 5): the v4 render covers the new area, and the
    # NJ-validity raster already excludes NY ground; no new exclusion boxes.
    # SnapWave: v4's footprint (v3's area + Delaware Bay) UNCHANGED — so the Upper New York
    # Bay, the KvK and the lower Hudson get NO waves, the same treatment as Newark Bay in 1.1.0
    # (user 2026-11-14). V3.region ends at the Narrows. Outside the fingerprint.
    map_windows={
        **V4_REFREEZE_SWZ_V11.map_windows,
        "upper_bay_hudson": (575_000, 595_000, 4_495_000, 4_526_000),
    },
)
