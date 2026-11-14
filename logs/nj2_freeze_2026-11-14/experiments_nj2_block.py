
# ── nj2 (Model 2.0) — 2026-11-14 (logs/nj2_freeze_2026-11-14/README.md) ─────────────────────────────
# `nj2` is the MESH domain (building, then frozen): no arms. `nj2_bed2012` = the 2012-bed face-z domain
# (registered at GATE 2, after setup_face_z), where everything runs. Its FIRST runs are the 2.0 DESIGN
# GATE, as v4's were (user / coordinator 11-14): waves-off Sandy at +0 / +2 / +3 m sea level, rain off,
# read with scripts/overflow_check.py … --compare <the +0 run>. 2.0.0 is called final only after the
# gate reads clean; a leak is a mask change (setup_boundary_depth.py, a new sha), not a new mesh.
#: The NACCS support count of data/gtsm/naccs_sandy_nj2.nc (J2 step 4's builder prints it). 🔴 None
#: until then: with None the arms fall back to the domain's BASE count and staging refuses — the
#: J3 job also refuses while this is None.
_NJ2_NACCS_SUPPORT: int | None = None
_NJ2_WL = dict(waterlevel_geodataset="naccs_sandy_nj2", n_waterlevel_support=_NJ2_NACCS_SUPPORT)
_NJ2_BED = "_subgrid_nj2_2012"
#: Model 1.1.0's premier weirs (Overpeck open, Elizabeth / Rahway levees, Keansburg) — the 2.0 default.
_NJ2_WEIR = DATA / "structures_v4" / "sfincs_overpeck_open_elizabeth_rahway_ground.weir"
#: The edges agent's fixed dikes / levees set (Chester redraw) on top of 1.1.0's weirs, + the Cohansey
#: (Bacons Neck) tide gate as a check valve (logs/nj2_edges_2026-11-14/).
_NJ2_WEIR_DIKES = DATA / "nj2_design" / "structures" / "sfincs_overpeck_open_elizabeth_rahway_dikes_levees_cohansey_nj2.weir"
_NJ2_DRN_COHANSEY = DATA / "nj2_design" / "structures" / "cohansey_bacons_neck_gate_checkvalve.drn"
_NJ2_GATE_WHY = (
    "Model 2.0 DESIGN GATE on nj2_bed2012 (2012 bed _subgrid_nj2_2012, the new nj2 mesh: Upper Bay, KvK, "
    "Hudson to 40.860 and East River to Hell Gate computed; forced cuts `hudson` / `hell_gate`): 1.1.0's "
    "p4-nowaves physics (NACCS-blend wind, cnb, the moved inflows) with RAIN OFF (rivers on) and {m:+.0f} m "
    "on the whole water-level boundary (NACCS on the drawn sea line + the two cuts, data/gtsm/"
    "naccs_sandy_nj2.nc, support count declared here) with a connected start at {m:+.0f} m. Reads where "
    "the model's own water reaches the ring edge, the walls and the river cuts (scripts/overflow_check.py "
    "--compare the +0 m run): v4's gate found Darby Creek and Cape Henlopen this way. Extent flagged "
    "extent_admissible=False like every waves-off arm."
)
EXPERIMENTS_BY_DOMAIN["nj2"] = {}
EXPERIMENTS_BY_DOMAIN["nj2_bed2012"] = {
    "p4-nowaves+rain-off+slr-0m+struct-cohansey-checkvalve+weir-dikes-levees": replace(
        EXPERIMENTS_BY_DOMAIN["v4_refreeze_swz_v11"]["p4-nowaves"],
        name="p4-nowaves+rain-off+slr-0m+struct-cohansey-checkvalve+weir-dikes-levees",
        description=_NJ2_GATE_WHY.format(m=0)
        + " Carries the edges agent's fixed dikes / levees weir set (Chester redraw) on 1.1.0's weirs + the "
        "Cohansey Bacons Neck gate as a check valve, so both are tested in one run. Read as a PAIRED comparison "
        "against the clean +0 run `p4-nowaves+rain-off+slr-0m` (same forcing, 1.1.0's weirs): every difference "
        "is the dike set + the check valve.",
        rain=False,
        sea_level_offset_m=0.0,
        subgrid_from=_NJ2_BED,
        weir_from=_NJ2_WEIR_DIKES,
        drn_from=_NJ2_DRN_COHANSEY,
        **_NJ2_WL,
    ),
    **{
        f"p4-nowaves+rain-off+slr-{m}m": replace(
            EXPERIMENTS_BY_DOMAIN["v4_refreeze_swz_v11"]["p4-nowaves"],
            name=f"p4-nowaves+rain-off+slr-{m}m",
            description=_NJ2_GATE_WHY.format(m=m)
            + (
                " The CLEAN +0 baseline (user 11-14): 1.1.0's premier weirs, the same as +2 / +3, so their "
                "--compare reads the sea level alone; also the 2.0 SMOKE run (first in J3)."
                if m == 0
                else " Looks for leaks through the new Hudson / Hell Gate edges and the ring (--compare the "
                "clean +0). Weirs = 1.1.0's premier file."
            ),
            rain=False,
            sea_level_offset_m=float(m),
            subgrid_from=_NJ2_BED,
            weir_from=_NJ2_WEIR,
            **_NJ2_WL,
        )
        for m in (0, 2, 3)
    },
}
