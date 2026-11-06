"""Bed audit check `crossing_nbi` (2026-11-05): every FHWA National Bridge Inventory structure in the model,
tested for whether the bed lets water through its opening at the level of what passes under it.

The method, its threshold reasoning and its calibration live in logs/nbi_crossings_2026-11-05/README.md and
nbi_check.py (imported here; this file only adapts it to the shared audit CLI and exceptions format,
logs/bed_audit_2026-11-05/SCHEMA.md). The NBI parse + OSM match are bed-independent and cached in
logs/nbi_crossings_2026-11-05/out/ (re-run `python -I nbi_check.py --parse --match` there for a new NBI year).

  python -I check.py --bed experiments/v4_refreeze_swz/_subgrid_v1_1b --label v1_1b --out out/v1_1b/crossing_nbi.csv
  python -I check.py --bed experiments/v4_refreeze_swz/_subgrid_v1_1 --label v1_1b --overlay-min deck_fix_v4b ...
  python -I check.py --bed experiments/v4_refreeze_swz/_subgrid_modern2026 --label modern --overlay-min deck_fix_v4 ...
`--overlay-min deck_fix_v4` on the modern bed uses common_m.Overlay() (v1.1's deck pixels, what the modern deck
pass judged); any other key is resolved read-only from data/data_catalog.yml and applied as a lower-only min.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path("/cache/home/tpj8/nj_bight_sfincs")
NBI_DIR = REPO / "logs/nbi_crossings_2026-11-05"
sys.path.insert(0, str(NBI_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO / "logs/decks_2026-11-04"))
sys.path.insert(0, str(REPO / "logs/modern_decks_2026-11-04"))
import nbi_check as N  # noqa: E402

SOURCE = ("FHWA National Bridge Inventory, 2025 submission (NJ/DE/PA/NY delimited files) + OSM bridge/way geometry"
          " + NOAA ENC BRIDGE objects (2026-11-06)")


def catalog_path(key):
    import yaml
    cat = yaml.safe_load((REPO / "data/data_catalog.yml").read_text())
    return str(REPO / "data" / cat[key]["uri"])


def build_bed(bed_dir, keys):
    from common import Bed
    from common_m import EffBed, Overlay
    p = Path(bed_dir)
    p = p if p.suffix == ".tif" else p / "subgrid/dep_subgrid_merged.tif"
    if "deck_fix_v4" in keys:   # the npz pixel set the modern deck pass used (same values as the catalog tier)
        base = EffBed(p, Overlay())
        keys = [k for k in keys if k != "deck_fix_v4"]
    else:
        base = Bed(p)
    return N.MinBed(None, [catalog_path(k) for k in keys], base=base)


def severity(cls, held_sandy):
    hs = held_sandy if np.isfinite(held_sandy) else 0.0
    if cls in ("DECK-IN-BED", "BLOCKED"):
        return "high" if hs >= 0.25 else "medium"
    if cls in ("FILL?", "OBSTRUCTED", "PARTIAL"):
        return "medium" if hs >= 0.25 else "low"
    return "low"


def enc_fields(e, r, road, lev, gap):
    """ENC columns + the chart's verdict on a WATER fault (blank for road rows / no chart match)."""
    f = dict(enc_d_m="", enc_catbrg="", enc_clear_m="", enc_horclr_m="", enc_cell="", enc_soffit_m="", enc_verdict="")
    if e is None:
        return f
    mhhw = getattr(r, "water_mhhw", np.nan)
    clear = e.clear_m
    f.update(enc_d_m=round(float(e.d), 0), enc_catbrg=e.CATBRG or "", enc_cell=e.DSNM or "",
             enc_clear_m=round(float(clear), 2) if np.isfinite(clear) else "",
             enc_horclr_m=round(float(e.HORCLR), 1) if np.isfinite(e.HORCLR) else "",
             enc_soffit_m=round(float(mhhw + clear), 2) if np.isfinite(clear) and np.isfinite(mhhw) else "")
    if road:
        return f
    base = r.cls.replace("CULVERT-", "")
    if base not in ("BLOCKED", "FILL?"):
        return f
    bed_open = gap   # nbi_check: `gap` = the LOWEST bed under the deck along the structure (absolute, m NAVD88)
    if not np.isfinite(bed_open) or not np.isfinite(mhhw):
        f["enc_verdict"] = "charted bridge; bed or MHHW unknown"
    elif bed_open >= mhhw:
        f["enc_verdict"] = (f"CONFIRMED (measured): the chart has a navigable opening"
                            f"{' with ' + format(clear, '.1f') + ' m clearance' if np.isfinite(clear) else ''}; "
                            f"the LOWEST bed under the whole deck is {bed_open:.2f} m, at or above MHHW {mhhw:.2f}")
    else:
        hor = e.HORCLR
        open_len = getattr(r, "water_open_len", np.nan)
        if base == "FILL?" and np.isfinite(hor) and np.isfinite(open_len) and open_len >= 0.5 * hor:
            f["enc_verdict"] = (f"WIDTH OK (chart): our opening ({open_len:.0f} m) matches the charted {hor:.0f} m; the "
                                f"open question is the DEPTH under the span (a water surface standing in for the bed), "
                                f"which a chart clearance does not give")
        elif np.isfinite(hor) and np.isfinite(open_len) and open_len >= 0.5 * hor:
            f["enc_verdict"] = (f"SOFTENED: our opening is water ({bed_open:.2f} < MHHW {mhhw:.2f}) and {open_len:.0f} m "
                                f"wide against the charted {hor:.0f} m: a constriction, not a block")
        else:
            f["enc_verdict"] = (f"constriction (a charted opening exists; our lowest bed under the deck {bed_open:.2f} is "
                                f"below MHHW {mhhw:.2f}, but the opening is narrower / higher than the channel either side)")
    return f


KIND = {"DECK-IN-BED": "deck_in_bed_over_road_or_rail", "BLOCKED": "waterway_opening_blocked",
        "FILL?": "water_surface_as_bed_under_bridge", "OBSTRUCTED": "obstruction_under_bridge_below_deck_level",
        "PARTIAL": "opening_narrower_than_structure", "MARGINAL": "marginal_within_lidar_accuracy",
        "NO-MATCH": "undecidable_no_osm_bridge_match", "NO-UNDER": "undecidable_no_under_feature_in_osm"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bed", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--overlay-min", action="append", default=[])
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    from common_m import TO_LL
    from scipy.spatial import cKDTree
    bed = build_bed(a.bed, a.overlay_min)
    R, _ = N.rule(None, None, bed=bed, label=a.label, write=False)
    M = pd.read_parquet(N.O / "nbi_matched.parquet")
    T = M.merge(R, on=["struct", "state"], how="left", suffixes=("", "_r"))
    T = T[~T.cls.isin(["OPEN", "CULVERT-OPEN"]) & T.cls.notna()].copy()
    # the point to look at: the worst crossing, else the waterway crossing, else the NBI point
    x = np.where(np.isfinite(T.get("road_x", np.nan)) & (T.basis == "road"), T.get("road_x", np.nan), T.get("wx", np.nan))
    y = np.where(np.isfinite(T.get("road_y", np.nan)) & (T.basis == "road"), T.get("road_y", np.nan), T.get("wy", np.nan))
    x = np.where(np.isfinite(x), x, T.x.values)
    y = np.where(np.isfinite(y), y, T.y.values)
    lon, lat = TO_LL(x, y)
    PE = REPO / "logs/power_exposure_2026-11-02"
    A = pd.concat([pd.read_csv(PE / f) for f in ("substations_exposure.csv", "plants_exposure.csv")])
    A = A[np.isfinite(A.lon) & np.isfinite(A.lat)]
    from common_m import TO_UTM
    axy = np.c_[TO_UTM(A.lon.values, A.lat.values)]
    dist, ia = cKDTree(axy).query(np.c_[x, y])
    # 2026-11-06: NOAA ENC bridges (enc.py) at the WATER crossing point, else the NBI point
    import enc as ENC
    EB = ENC.load()
    ex = np.where(np.isfinite(T.get("wx", np.nan)), T.get("wx", np.nan), T.x.values).astype(float)
    ey = np.where(np.isfinite(T.get("wy", np.nan)), T.get("wy", np.nan), T.y.values).astype(float)
    em = ENC.match(EB, ex, ey)
    SUP = ENC.load_supports()
    from shapely import wkt as _wkt
    from shapely.geometry import Point as _Pt
    pier_cols = []
    for k, r in enumerate(T.itertuples()):
        e = em[k]
        if e is not None:
            search, gsrc = e.geometry.buffer(20.0), "ENC bridge + 20 m"
        elif isinstance(getattr(r, "line_wkt", None), str):
            search, gsrc = _wkt.loads(r.line_wkt).buffer(15.0), "OSM bridge line + 15 m"
        else:
            search, gsrc = _Pt(ex[k], ey[k]).buffer(40.0), "NBI / water point + 40 m"
        n_c, w_c, pos = ENC.charted_piers(SUP, search)
        wl = getattr(r, "water_expect_len", np.nan)
        width = wl if isinstance(wl, float) and np.isfinite(wl) and wl > 0 else getattr(r, "len49", np.nan)
        pn, sp, inch, blk = ENC.nbi_piers(float(getattr(r, "spans45", np.nan) or np.nan),
                                          float(getattr(r, "spans46", np.nan) or np.nan),
                                          float(getattr(r, "len49", np.nan)), float(getattr(r, "maxspan48", np.nan)),
                                          float(width) if width is not None else np.nan)
        blk_c = min(1.0, w_c / width) if n_c and np.isfinite(width) and width > 0 else np.nan
        pier_cols.append(dict(
            piers_source=("ENC charted" if n_c else ("NBI estimate" if np.isfinite(pn) else "none")),
            piers_charted_n=n_c, piers_charted_pos=pos, piers_search=gsrc,
            piers_nbi_est=pn if np.isfinite(pn) else "", pier_spacing_m=round(sp, 1) if np.isfinite(sp) else "",
            piers_in_channel_est=inch if isinstance(inch, (int, np.integer)) else "",
            channel_width_m=round(float(width), 1) if np.isfinite(width) else "",
            blockage_frac=round(blk_c if np.isfinite(blk_c) else blk, 3) if np.isfinite(blk_c) or np.isfinite(blk) else "",
            blockage_basis=("charted support widths / channel width" if np.isfinite(blk_c) else
                            (f"NBI piers in channel x {ENC.PIER_W} m (ASSUMED width) / channel width" if np.isfinite(blk)
                             else ""))))
    rows = []
    for k, r in enumerate(T.itertuples()):
        base_cls = r.cls.replace("CULVERT-", "")
        culv = r.cls.startswith("CULVERT-")
        road = r.basis == "road"
        held = getattr(r, "road_held" if road else "water_held", np.nan)
        lev = getattr(r, "road_level" if road else "water_level", np.nan)
        gap = getattr(r, "road_gap" if road else "water_gap", np.nan)
        hs = r.held_sandy if isinstance(r.held_sandy, float) else np.nan
        kind = ("culvert_" if culv else "") + KIND.get(base_cls, base_cls.lower())
        sev = "low" if culv and base_cls != "BLOCKED" else severity(base_cls, hs)
        if base_cls == "DECK-IN-BED":
            expd = f"street {lev:.2f} m; deck soffit {lev + r.vclr54b:.2f} m (NBI 54B {r.vclr54b:.2f} m)"
            fix = f"lower the deck footprint ({r.deckw52:.0f} m along the way under) to the street, lower-only"
        elif base_cls == "BLOCKED":
            expd = f"opening at the channel either side ({lev:.2f} m) over >= half of {r.maxspan48:.0f} m (NBI 48)"
            fix = "lower the deck pixels to each side's own bank (the deck_fix_v4b rule)"
        elif base_cls == "FILL?":
            expd = "a channel bed below the water surface (flat surface at %.2f m, MHHW %.2f m)" % (
                getattr(r, "water_surface_med", np.nan), getattr(r, "water_mhhw", np.nan))
            fix = ""
        elif base_cls in ("OBSTRUCTED", "PARTIAL", "MARGINAL"):
            expd = f"street level {lev:.2f} m under a {r.deckw52:.0f} m deck"
            fix = ""
        else:
            expd, fix = "", ""
        if culv:
            fix = "sub-cell culvert: a slot or a structure, reviewer decides"
        note = (f"{r.carried} over {r.feat} ({r.und_txt}; {r.type_txt}; L49 {r.len49:.0f} m, deck {r.deckw52:.1f} m; "
                f"OSM match {r.match}, {r.d_m if np.isfinite(r.d_m) else float('nan'):.0f} m)")
        rows.append(dict(
            check="crossing_nbi", id=f"{r.state}:{str(r.struct).strip()}", lon=round(float(lon[k]), 6),
            lat=round(float(lat[k]), 6), severity=sev, kind=kind,
            metric="bed in the opening minus the under-feature level (m)" if np.isfinite(held) else "",
            value=round(float(gap), 2) if np.isfinite(gap) else "", expected=expd, units="m NAVD88",
            area_m2=round(float(r.deckw52 * min(r.len49, 60.0)), 0) if np.isfinite(r.deckw52) and np.isfinite(r.len49) else "",
            sandy_peak_m=round(float(r.zs_near), 2) if isinstance(r.zs_near, float) and np.isfinite(r.zs_near) else "",
            near_asset=A.name.values[ia[k]] if dist[k] <= 2000 else "",
            asset_km=round(float(dist[k]) / 1000, 2) if dist[k] <= 2000 else "",
            source=SOURCE, note=note, fix=fix, held_m=round(float(held), 2) if np.isfinite(held) else "",
            held_sandy_m=round(float(hs), 2) if np.isfinite(hs) else "",
            evidence=("measured (NBI 54B underclearance)" if road and np.isfinite(r.vclr54b) and r.vclr54b > 1.5
                      else "inferred (our bed vs the water / street either side)"), **enc_fields(em[k], r, road, lev, gap),
            tidal_water=bool(not road and np.isfinite(getattr(r, "water_lowest_ref", np.nan))
                             and np.isfinite(getattr(r, "water_mhhw", np.nan)) and r.water_lowest_ref < r.water_mhhw),
            **pier_cols[k]))
    E = pd.DataFrame(rows)
    order = {"high": 0, "medium": 1, "low": 2}
    E = E.sort_values(["severity", "held_sandy_m"], key=lambda c: c.map(order) if c.name == "severity" else
                      -pd.to_numeric(c, errors="coerce").fillna(-1))
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    E.to_csv(out, index=False)
    print(out, len(E), E.severity.value_counts().to_dict(), E.kind.value_counts().to_dict())


if __name__ == "__main__":
    main()
