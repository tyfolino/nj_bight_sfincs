"""First-pass flood read of power plants and substations. Model 1.0.0, PRELIMINARY.

Footprints (``data/power_infra``, Robert Mieth, OSM-derived) against the Sandy bare-ground
share map and the still-water MHHW + 2 / + 4 ft maps on the modern bed. Re-read after v1.1.

    python scripts/power_exposure.py sample --maps sandy sandy_burned   per-map partials
    python scripts/power_exposure.py tables    per-asset CSVs + not_computed.csv + summary
    python scripts/power_exposure.py figure    exposure_map.png
    python scripts/power_exposure.py update --maps still_2ft still_4ft   all three, for
                                               maps that land later (the rest are kept)

THREE STATES, NEVER TWO. A blank pixel is dry ground, permanent water, or ground the model
never had, and only the run can tell them apart:

* outside the run's active faces (``validate.simulated_mask``, ``msk`` of ``p4-premier``):
  NOT COMPUTED. Hudson County's Upper Bay side stays unknown, not dry;
* inside, on the ground each map masks as water: ON WATER, its own label (Sandy: bed
  <= -0.5 m as ``export_share_floodmap``; still: ``normal_surface.normally_wet``);
* inside, on land, blank or under 0.15 m: DRY.

An asset is ``wet`` with any land pixel >= 0.15 m above the ground the map uses (read
``wet_share`` for how much of it). Otherwise it needs half its footprint on active faces to
be ``dry`` or ``on_water``; under that it is ``not_computed`` with its ``covered_frac``. An
asset with no active pixel is ``not_computed`` within ``NEAR_KM`` of the active mesh and
``out_of_model`` beyond it, and ``out_of_model`` is excluded from every total.

⚠️ The still maps burn buildings into the bed, so a building's pixels read blank (and count
as dry) there. The ``band_*`` columns read a ring ``BAND_M`` outside the footprint as a
second number, ``bldg_share`` is the footprint's share under a burn, and ``sandy_burned``
(the sibling map, same water, burned bed) measures the size of the effect.

The share maps are north-up (asserted) but the beds are ROTATED: every coordinate goes
through an affine (CLAUDE.md §5), and never ``read(boundless=True)``. Depth is not failure;
see the README in the output directory.

Ground is read on the bed's BASE band (``open_bed``, 2026-11-13). Until then every bed was
opened at rasterio's overview level 0, which is the FIRST OVERVIEW (6.25 m on v4, ``average``
resampled), not the full raster: a street pixel between two burned buildings read building
height and its water class / depth followed it (``logs/floodmap_fix_2026-11-12/README.md``;
the 11-02 tables in ``OUT`` were made that way, ``logs/slr_assets_2026-11-13/README.md`` has
the before / after on the still + 4 ft map).
"""

from __future__ import annotations

import argparse
import os
import re
import resource
import zipfile

import geopandas as gpd  # noqa: E402
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from rasterio.transform import rowcol
from rasterio.windows import Window
from scipy.ndimage import distance_transform_edt
from shapely.geometry import box

import nj_sfincs  # noqa: F401  (PROJ primer, must precede geopandas / hydromt_sfincs)
from nj_sfincs import domain, normal_surface, validate  # noqa: E402
from nj_sfincs.config import ROOT, exp_root  # noqa: E402

OUT = ROOT / "logs" / "power_exposure_2026-11-02"
RUN = exp_root() / "p4-premier"
CRS = 32618
LABEL = "Model 1.0.0, preliminary; re-read after v1.1"

WET_M = 0.15  # the repo's scoring threshold; the share maps floor at 0.05 m
PERMANENT_BED_M = -0.5  # export_share_floodmap's permanent-water cutoff
BAND_M = 30.0  # the perimeter ring, about 5 pixels
SMALL_PX = 25  # fewer pixel centres than this: all_touched
COVER_MIN = 0.5  # share of a footprint on active faces needed to call it dry
NEAR_KM = 5.0  # no active pixel, this far from the mesh or less: not computed
BURN_M = 0.5  # own bed - bare bed above this = under a building (export_share_floodmap)
RIVER_CUT_KM = 8.0  # a not-computed asset this close to a river cut is flagged upriver

SHARE = ROOT / "share"
FLOODMAPS = exp_root() / "floodmaps"
BARE_BED = (
    ROOT
    / "experiments/v4_refreeze/_subgrid_refreeze_lakes_min_nobuildings_creeks_cohansey"
    / "subgrid/dep_subgrid_merged.tif"
)
OWN_BED = RUN / "subgrid" / "dep_subgrid_merged.tif"
MODERN_BED = exp_root() / "bed-modern+still-2ft" / "subgrid" / "dep_subgrid_merged.tif"

MAPS = {
    "sandy": dict(
        title="Sandy (bare ground)",
        tif=SHARE / "sandy_hmax_v4_refreeze_swz_p4-premier_bareground_EPSG32618.tif",
        bed=BARE_BED,
    ),
    "sandy_burned": dict(
        title="Sandy (buildings burned, bias check only)",
        tif=SHARE / "sandy_hmax_v4_refreeze_swz_p4-premier_EPSG32618.tif",
        bed=OWN_BED,
    ),
    "still_2ft": dict(
        title="MHHW + 2 ft (modern bed, preliminary)",
        tif=FLOODMAPS / "bed-modern+still-2ft_depth.tif",
        bed=MODERN_BED,
        rise=0.61,
    ),
    "still_4ft": dict(
        title="MHHW + 4 ft (modern bed, preliminary)",
        tif=FLOODMAPS / "bed-modern+still-4ft_depth.tif",
        bed=MODERN_BED,
        rise=1.22,
    ),
}
SCENARIOS = ("sandy", "still_2ft", "still_4ft")
FUELS = {
    "solar": "solar",
    "gas": "gas",
    "oil": "oil",
    "petroleum coke": "oil",
    "coal": "coal",
    "nuclear": "nuclear",
    "hydro": "hydro",
    "wind": "wind",
    "battery": "battery",
    "biogas": "bio/waste",
    "biomass": "bio/waste",
    "waste": "bio/waste",
}
KV_BINS = (
    (0, 69, "<69 kV"),
    (69, 138, "69-137 kV"),
    (138, 230, "138-229 kV"),
    (230, 345, "230-344 kV"),
    (345, 1e9, ">=345 kV"),
)


def parse_mw(text: str) -> float:
    """Megawatts from OSM's text: "10 MW", "605 kW", "26991 kWp". "yes", "" and a bare
    number ("2.0", no unit) are not a capacity and stay NaN."""
    m = re.fullmatch(r"\s*([\d.,]+)\s*(GW|MW|kW|kWp|MWp)\s*", str(text))
    if not m:
        return np.nan
    scale = {"GW": 1e3, "MW": 1.0, "MWp": 1.0, "kW": 1e-3, "kWp": 1e-3}[m[2]]
    return float(m[1].replace(",", "")) * scale


def parse_kv(text: str) -> float:
    """The highest voltage on a record, in kV ("230000;138000", "138000;46000:12470",
    "230000;115000;?"). NaN when none is given."""
    volts = [float(t) for t in re.split(r"[;:]", str(text)) if re.fullmatch(r"\d+", t)]
    return max(volts) / 1e3 if volts else np.nan


def kv_bin(kv: float) -> str:
    for lo, hi, name in KV_BINS:
        if lo <= kv < hi:
            return name
    return "unknown"


def load_assets() -> gpd.GeoDataFrame:
    """Both classes, cleaned, in EPSG:32618, with state and county joined."""
    out = []
    for klass, fn in (("plant", "plant"), ("substation", "substation")):
        g = gpd.read_file(ROOT / "data" / "power_infra" / f"{fn}_polygons.geojson")
        g["klass"] = klass
        out.append(g)
    a = pd.concat(out, ignore_index=True).fillna(
        {
            c: ""
            for c in (
                "plant_source",
                "plant_output_electricity",
                "voltage",
                "eia_codes",
            )
        }
    )
    a = gpd.GeoDataFrame(a, geometry="geometry", crs=out[0].crs).to_crs(CRS)
    a["geometry"] = a.geometry.make_valid()
    a["asset"] = a.klass.str[0] + a.id.astype(str)
    a["name_blank"] = a.name.fillna("").str.strip() == ""
    a["area_m2"] = a.area.round(0)

    a["fuel"] = [
        FUELS.get(s.split(";")[0], "other") if s else "" for s in a.plant_source
    ]
    a["fuel_mixed"] = a.plant_source.str.contains(";")
    a["mw"] = a.plant_output_electricity.map(parse_mw)
    a["mw_text_only"] = (
        (a.klass == "plant") & a.mw.isna() & (a.plant_output_electricity != "")
    )
    a["kv_max"] = a.voltage.map(parse_kv)
    a["kv_class"] = [
        kv_bin(k) if c == "substation" else "" for k, c in zip(a.kv_max, a.klass)
    ]

    # one EIA code on two records, or one record carrying several (Salem + Hope Creek)
    codes = a[a.klass == "plant"].eia_codes.str.split(";").explode()
    codes = codes[codes != ""]
    twice = codes[codes.duplicated(keep=False)]
    a["eia_duplicate"] = False
    a.loc[twice.index.unique(), "eia_duplicate"] = True
    a["shared_record"] = (a.klass == "plant") & a.eia_codes.str.contains(";")
    return join_states(a)


def _census(kind: str) -> gpd.GeoDataFrame:
    """A Census cartographic boundary, downloaded once into ``OUT/census``."""
    z = OUT / "census" / f"cb_2023_us_{kind}_500k.zip"
    if not zipfile.is_zipfile(z):
        raise SystemExit(
            f"{z} missing: fetch it from www2.census.gov/geo/tiger/GENZ2023/shp/"
        )
    return gpd.read_file(f"zip://{z}").to_crs(CRS)


def join_states(a: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """State + county at each footprint's representative point; nearest for a footprint
    off the generalised shoreline (flagged). The source files carry no state field."""
    pts = gpd.GeoDataFrame(
        {"asset": a.asset}, geometry=a.representative_point(), crs=CRS
    )
    st = _census("state")[["STUSPS", "geometry"]]
    co = _census("county")[["NAME", "STUSPS", "geometry"]].rename(
        columns={"NAME": "county", "STUSPS": "county_state"}
    )
    hit = gpd.sjoin(pts, st, how="left", predicate="within").drop_duplicates("asset")
    a["state"] = hit.STUSPS.values
    a["state_by_nearest"] = a.state.isna()
    if a.state_by_nearest.any():
        near = gpd.sjoin_nearest(pts[a.state_by_nearest], st).drop_duplicates("asset")
        a.loc[a.state_by_nearest, "state"] = near.STUSPS.values
    hit = gpd.sjoin_nearest(pts, co).drop_duplicates("asset")
    a["county"] = hit.county.values
    return a


def pixels(geom, tf, shape, *, all_touched=None):
    """(rows, cols, n_outside) of a geometry on a north-up lattice, part by part so a
    multi-site relation does not rasterise the map between its parts. ``all_touched=None``
    decides per geometry: pixel centres, or all touched when centres are under SMALL_PX."""
    rr, cc = [], []
    parts = getattr(geom, "geoms", [geom])
    for touched in (False, True):
        rr, cc, n_out = [], [], 0
        for part in parts:
            if part.is_empty or part.area == 0:
                continue
            (r0, r1), (c0, c1) = rowcol(
                tf, [part.bounds[0], part.bounds[2]], [part.bounds[3], part.bounds[1]]
            )
            r0, c0 = r0 - 1, c0 - 1
            h, w = r1 - r0 + 2, c1 - c0 + 2
            wtf = tf * tf.translation(c0, r0)
            m = rasterize(
                [(part, 1)], out_shape=(h, w), transform=wtf, all_touched=touched
            )
            r, c = np.nonzero(m)
            r, c = r + r0, c + c0
            inside = (r >= 0) & (c >= 0) & (r < shape[0]) & (c < shape[1])
            n_out += int((~inside).sum())
            rr.append(r[inside])
            cc.append(c[inside])
        r = np.concatenate(rr) if rr else np.empty(0, int)
        c = np.concatenate(cc) if cc else np.empty(0, int)
        n = r.size + n_out
        if all_touched is False or touched or n >= SMALL_PX:
            break
    return r, c, n_out


def read_points(src, rows, cols) -> np.ndarray:
    """Band 1 at (rows, cols) of an open raster, through one clipped window."""
    if rows.size == 0:
        return np.empty(0, "f4")
    r0, c0 = int(rows.min()), int(cols.min())
    win = Window(c0, r0, int(cols.max()) - c0 + 1, int(rows.max()) - r0 + 1)
    return src.read(1, window=win)[rows - r0, cols - c0]


def open_bed(path):
    """A bed opened for ground reads: its BASE band (full resolution). Never rasterio's
    overview level 0, which is the first overview, not the base (module docstring)."""
    return rasterio.open(path)


def read_at_xy(src, x, y) -> np.ndarray:
    """Nearest pixel of an open raster at (x, y) through its affine (the beds are
    rotated); NaN off the raster."""
    col, row = ~src.transform * (x, y)
    col, row = np.floor(col).astype(int), np.floor(row).astype(int)
    ok = (col >= 0) & (row >= 0) & (col < src.width) & (row < src.height)
    out = np.full(x.shape, np.nan, "f4")
    out[ok] = read_points(src, row[ok], col[ok])
    return out


def classify(src, bed, sim, rows, cols, rise):
    """Per pixel: depth, active, water, ground, and blank land below the still level."""
    tf = src.transform
    depth = read_points(src, rows, cols)
    active = sim[rows, cols]
    x, y = tf * (cols + 0.5, rows + 0.5)
    ground = read_at_xy(bed, np.asarray(x), np.asarray(y))
    low = np.zeros(rows.shape, bool)
    if rise is None:
        water = ground <= PERMANENT_BED_M
    else:
        water = normal_surface.normally_wet(x, y, ground)
        low = (
            ground
            < normal_surface.sample_raster(normal_surface.mhhw_path(), x, y) + rise
        )
    # no bed under an active face: nothing can be said about it
    active = active & np.isfinite(ground)
    return depth, active, water & active, ground, low


def read_asset(src, bed, sim, geom, rise) -> dict:
    """The per-map numbers for one footprint and its perimeter band."""
    tf, shape = src.transform, src.shape
    rows, cols, n_off = pixels(geom, tf, shape)
    n_px = rows.size + n_off
    d, active, water, _, low = classify(src, bed, sim, rows, cols, rise)
    land = active & ~water
    wet = land & (d >= WET_M)
    damp = land & np.isfinite(d) & (d < WET_M)
    drip = land & ~np.isfinite(d)
    n_land = int(land.sum())
    n_wet = int(wet.sum())
    out = dict(
        n_px=n_px,
        n_off=n_off + int((~active).sum()),
        covered_frac=round(active.sum() / n_px, 4) if n_px else 0.0,
        n_land=n_land,
        n_water=int(water.sum()),
        n_wet=n_wet,
        n_damp=int(damp.sum()),
        wet_share=round(n_wet / n_land, 4) if n_land else np.nan,
        wet_share_footprint=round(n_wet / n_px, 4) if n_px else np.nan,
        depth_max=round(float(d[wet].max()), 3) if n_wet else np.nan,
        depth_median=round(float(np.median(d[wet])), 3) if n_wet else np.nan,
        low_unreached=int((drip & low).sum()) if rise is not None else 0,
    )
    c = geom.representative_point()
    cr, cc = rowcol(tf, c.x, c.y)
    if 0 <= cr < shape[0] and 0 <= cc < shape[1]:
        v = read_points(src, np.array([cr]), np.array([cc]))[0]
        out["point_depth"] = round(float(v), 3) if np.isfinite(v) else np.nan
    else:
        out["point_depth"] = np.nan

    rows, cols, _ = pixels(
        geom.buffer(BAND_M).difference(geom), tf, shape, all_touched=False
    )
    d, active, water, _, _ = classify(src, bed, sim, rows, cols, rise)
    land = active & ~water
    wet = land & (d >= WET_M)
    n = int(land.sum())
    out.update(
        band_n_land=n,
        band_wet_share=round(wet.sum() / n, 4) if n else np.nan,
        band_depth_max=round(float(d[wet].max()), 3) if wet.any() else np.nan,
        band_depth_median=round(float(np.median(d[wet])), 3) if wet.any() else np.nan,
    )
    return out


def asset_state(r: dict, dist_km: float) -> str:
    """wet / dry / on_water / not_computed / out_of_model (module docstring)."""
    if r["n_wet"] > 0:
        return "wet"
    if r["covered_frac"] == 0:
        return "not_computed" if dist_km <= NEAR_KM else "out_of_model"
    if r["covered_frac"] < COVER_MIN:
        return "not_computed"
    return "on_water" if r["n_water"] > r["n_land"] else "dry"


def model_distance(sim, tf, x, y) -> np.ndarray:
    """km from each (x, y) to the nearest active pixel, on a 32-pixel subsample of the
    mask; inf off the raster."""
    step = 32
    d = distance_transform_edt(~sim[::step, ::step]) * step * abs(tf.a) / 1e3
    col, row = ~tf * (x, y)
    row, col = np.floor(row / step).astype(int), np.floor(col / step).astype(int)
    ok = (row >= 0) & (col >= 0) & (row < d.shape[0]) & (col < d.shape[1])
    out = np.full(x.shape, np.inf)
    out[ok] = d[row[ok], col[ok]]
    return out


def sample(names: list[str]) -> None:
    """One partial CSV per map: every asset on the raster, read a window at a time."""
    missing = [str(MAPS[n]["tif"]) for n in names if not MAPS[n]["tif"].is_file()]
    if missing:
        raise SystemExit(
            "map not there yet, nothing sampled:\n  " + "\n  ".join(missing)
        )
    assets = load_assets()
    parts = OUT / "partials"
    parts.mkdir(parents=True, exist_ok=True)
    for name in names:
        m = MAPS[name]
        with (
            rasterio.open(m["tif"]) as src,
            open_bed(m["bed"]) as bed,
        ):
            if src.transform.b or src.transform.d or src.crs.to_epsg() != CRS:
                raise SystemExit(f"{m['tif']} is not north-up EPSG:{CRS}")
            sim = validate.simulated_mask(RUN, src.shape, src.transform)
            c = assets.representative_point()
            dist = model_distance(sim, src.transform, c.x.values, c.y.values)
            frame = box(*src.bounds)
            rows = []
            on = assets.intersects(frame).values
            for i in np.flatnonzero(on):
                r = read_asset(src, bed, sim, assets.geometry.iloc[i], m.get("rise"))
                r["state"] = asset_state(r, dist[i])
                r["asset"] = assets.asset.iloc[i]
                r["dist_to_model_km"] = round(float(dist[i]), 2)
                rows.append(r)
                if len(rows) % 200 == 0:
                    print(f"{name}: {len(rows)}/{on.sum()}", flush=True)
        df = pd.DataFrame(rows).set_index("asset")
        tmp = parts / f".{name}.partial.csv"
        df.to_csv(tmp)
        os.replace(
            tmp, parts / f"{name}.csv"
        )  # atomic: a truncated partial reads clean
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6
        print(
            f"{name}: {df.state.value_counts().to_dict()}, peak {rss:.1f} G", flush=True
        )


def footprint_context(assets: gpd.GeoDataFrame) -> pd.DataFrame:
    """Per asset on the raster: bare ground over the WHOLE footprint (the bed exists under
    inactive faces, so a not-computed site can still be called low or high) and the share
    of it under a building burn."""
    tif = MAPS["sandy"]["tif"]
    rows = []
    with (
        rasterio.open(tif) as src,
        open_bed(BARE_BED) as bare,
        open_bed(OWN_BED) as own,
    ):
        for i in np.flatnonzero(assets.intersects(box(*src.bounds)).values):
            r, c, _ = pixels(assets.geometry.iloc[i], src.transform, src.shape)
            x, y = src.transform * (c + 0.5, r + 0.5)
            x, y = np.asarray(x), np.asarray(y)
            g = read_at_xy(bare, x, y)
            burn = read_at_xy(own, x, y) - g
            ok = np.isfinite(g)
            rows.append(
                dict(
                    asset=assets.asset.iloc[i],
                    ground_min_m=round(float(g[ok].min()), 2) if ok.any() else np.nan,
                    ground_median_m=(
                        round(float(np.median(g[ok])), 2) if ok.any() else np.nan
                    ),
                    bldg_share=round(float((burn > BURN_M).mean()), 3) if r.size else 0,
                )
            )
    return pd.DataFrame(rows).set_index("asset")


def not_computed_why(a: pd.DataFrame) -> pd.Series:
    """Why a not-computed asset is outside: a coordinate fact, for the list only."""
    cuts = [(c.name, c.box) for c in domain.active().no_waterlevel_boxes]
    cx = np.array([(b[0] + b[2]) / 2 for _, b in cuts])
    cy = np.array([(b[1] + b[3]) / 2 for _, b in cuts])
    why = []
    for x, y, st, co in zip(a.x_utm, a.y_utm, a.state, a.county):
        d = np.hypot(cx - x, cy - y) / 1e3
        if st == "NJ" and co == "Hudson":
            why.append("Hudson County: outside the model")
        elif st == "NY" and co in ("New York", "Kings", "Queens", "Bronx"):
            why.append("NY harbor: outside the model")
        elif d.min() <= RIVER_CUT_KM:
            why.append(
                f"near river cut {cuts[int(d.argmin())][0]}: upriver or beside it"
            )
        else:
            why.append("beyond the model ring")
    return pd.Series(why, index=a.index)


def build_table() -> pd.DataFrame:
    """Assets + context + every sampled map, one row per asset."""
    assets = load_assets()
    pts = assets.representative_point()
    assets["x_utm"], assets["y_utm"] = pts.x.round(1), pts.y.round(1)
    keep = [
        "asset", "klass", "id", "name", "name_blank", "operator", "state", "county",
        "state_by_nearest", "lon", "lat", "x_utm", "y_utm", "area_m2", "eia_codes",
        "eia_duplicate", "shared_record", "plant_source", "fuel", "fuel_mixed",
        "plant_output_electricity", "mw", "mw_text_only", "voltage", "kv_max", "kv_class",
    ]  # fmt: skip
    t = pd.DataFrame(assets[keep]).set_index("asset")
    ctx = OUT / "partials" / "context.csv"
    if not ctx.is_file():
        c = footprint_context(assets)
        c.to_csv(ctx)
    t = t.join(pd.read_csv(ctx, index_col="asset"))
    for name in MAPS:
        p = OUT / "partials" / f"{name}.csv"
        if p.is_file():
            t = t.join(pd.read_csv(p, index_col="asset").add_prefix(f"{name}_"))
            t[f"{name}_state"] = t[f"{name}_state"].fillna("out_of_model")
    return t


def tally(t: pd.DataFrame, m: str) -> dict:
    """The counts for one group of assets on one map. Records, not plants."""
    s = t[f"{m}_state"]
    wet = s == "wet"
    dry = s == "dry"
    band = t[f"{m}_band_wet_share"]
    mw = t.mw.where(wet, 0.0).sum()
    return dict(
        records=int((s != "out_of_model").sum()),
        wet=int(wet.sum()),
        dry=int(dry.sum()),
        not_computed=int((s == "not_computed").sum()),
        on_water=int((s == "on_water").sum()),
        out_of_model_excluded=int((s == "out_of_model").sum()),
        wet_share_ge_25pct=int((wet & (t[f"{m}_wet_share"] >= 0.25)).sum()),
        wet_share_ge_50pct=int((wet & (t[f"{m}_wet_share"] >= 0.5)).sum()),
        dry_but_wet_perimeter_ge_25pct=int((dry & (band >= 0.25)).sum()),
        partly_outside_model=int(
            ((t[f"{m}_covered_frac"] > 0) & (t[f"{m}_covered_frac"] < 1)).sum()
        ),
        wet_mw_stated=round(float(mw), 1),
    )


def tables() -> None:
    """Per-asset CSV per class, summary by state / type / voltage / fuel per scenario."""
    t = build_table()
    done = [m for m in MAPS if f"{m}_state" in t]
    any_nc = t[[f"{m}_state" for m in done]].eq("not_computed").any(axis=1)
    t["not_computed_why"] = ""
    t.loc[any_nc, "not_computed_why"] = not_computed_why(t[any_nc])
    t.insert(0, "label", LABEL)
    for klass, fn in (("plant", "plants"), ("substation", "substations")):
        t[t.klass == klass].to_csv(OUT / f"{fn}_exposure.csv")
    # the list a total cannot show: low ground first, so Hudson County leads
    nc = ["klass", "name", "operator", "state", "county", "lon", "lat", "fuel", "mw"]
    nc += ["kv_max", "ground_median_m", "not_computed_why", "label"]
    nc += [f"{m}_state" for m in done] + [f"{done[0]}_covered_frac"]
    t.loc[any_nc, nc].sort_values("ground_median_m").to_csv(OUT / "not_computed.csv")

    rows = []
    for m in done:
        for scope, sub in (("NJ", t[t.state == "NJ"]), ("all", t)):
            for group, key in (
                ("total", None),
                ("state", "state"),
                ("type", "klass"),
                ("voltage", "kv_class"),
                ("fuel", "fuel"),
            ):
                if group == "total":
                    pieces = [("all", sub)]
                else:
                    use = sub[sub[key] != ""] if key != "state" else sub
                    pieces = list(use.groupby(key))
                for name, g in pieces:
                    r = tally(g, m)
                    if r["records"] or group == "total":
                        rows.append(
                            dict(map=m, scope=scope, group=group, value=name, **r)
                        )
    s = pd.DataFrame(rows)
    s.insert(0, "label", LABEL)
    s.to_csv(OUT / "summary_by_scenario.csv", index=False)
    print(s[(s.group.isin(["total", "type"]))].drop(columns="label").to_string())


STYLE = {
    "wet": dict(c="#1f5fa8", marker="o", label="Wet (any land pixel >= 0.15 m)", z=5),
    "dry": dict(c="#b9bcc2", marker="o", label="Dry", z=2),
    "not_computed": dict(c="#c8541e", marker="X", label="NOT COMPUTED", z=4),
    "on_water": dict(c="#35a29a", marker="D", label="On mapped water", z=3),
}


# Sites named in Sandy reports + the not-computed Hudson waterfront: (dx, dy, text), points.
FIGURE_LABELS = {
    "s3608": (-62, -22, "Sayreville (Raritan River)"),
    "s3277": (-58, 16, "Sewaren"),
    "s2753": (-58, 14, "Bayway"),
    "s2504": (-50, 18, "Essex"),
    "s2503": (-58, 24, "Marion"),
    "s2569": (22, -24, "Bayonne"),
    "s2139": (26, 12, "Hoboken (not computed)"),
    "s730": (24, 14, "North Bergen"),
}


def figure() -> None:
    """One row per map: asset state on the active mesh, whole domain + northern NJ."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Rectangle

    t = pd.concat(
        pd.read_csv(OUT / f"{n}_exposure.csv", index_col="asset", low_memory=False)
        for n in ("plants", "substations")
    )
    maps = [m for m in SCENARIOS if f"{m}_state" in t]
    with rasterio.open(MAPS["sandy"]["tif"]) as src:
        sim = validate.simulated_mask(RUN, src.shape, src.transform)[::16, ::16]
        b = src.bounds
    states = _census("state")
    zoom = (548_000, 4_465_000, 600_000, 4_525_000)
    fig, axes = plt.subplots(
        len(maps),
        2,
        figsize=(10.5, 0.8 + 7.2 * len(maps)),
        constrained_layout=True,
        squeeze=False,
    )
    for i, m in enumerate(maps):
        for j, ext in enumerate((None, zoom)):
            ax = axes[i, j]
            ax.imshow(
                np.where(sim, 1.0, np.nan),
                extent=(b.left, b.right, b.bottom, b.top),
                cmap="Greys",
                vmin=0,
                vmax=7,
                interpolation="nearest",
                zorder=0,
            )
            states.boundary.plot(ax=ax, color="#8a8d93", lw=0.5, zorder=1)
            for state, st in STYLE.items():
                g = t[t[f"{m}_state"] == state]
                ax.scatter(
                    g.x_utm,
                    g.y_utm,
                    s=(26 if ext else 13) * np.where(g.klass == "plant", 1.6, 1.0),
                    c=st["c"],
                    marker=st["marker"],
                    lw=0.3,
                    edgecolor="white",
                    zorder=st["z"],
                )
            x0, y0, x1, y1 = ext or (b.left, b.bottom, b.right, b.top)
            ax.set_xlim(x0, x1)
            ax.set_ylim(y0, y1)
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_aspect("equal")
            for sp in ax.spines.values():
                sp.set_color("#c9cbd0")
            if ext:
                ax.set_title("Northern NJ (the box at left)", fontsize=9, loc="left")
                for key, (dx, dy, text) in FIGURE_LABELS.items():
                    ax.annotate(
                        text,
                        (t.x_utm[key], t.y_utm[key]),
                        xytext=(dx, dy),
                        textcoords="offset points",
                        fontsize=7.5,
                        color="#222222",
                        arrowprops=dict(arrowstyle="-", color="#777777", lw=0.5),
                        zorder=8,
                    )
                continue
            n = t[t[f"{m}_state"] != "out_of_model"]
            c = n[f"{m}_state"].value_counts()
            nj = n[n.state == "NJ"][f"{m}_state"].value_counts()
            ax.set_title(
                f"{MAPS[m]['title']}\nwet / dry / not computed: all "
                f"{c.get('wet', 0)} / {c.get('dry', 0)} / {c.get('not_computed', 0)}; "
                f"NJ {nj.get('wet', 0)} / {nj.get('dry', 0)} / "
                f"{nj.get('not_computed', 0)}",
                fontsize=9.5,
                loc="left",
            )
            ax.add_patch(
                Rectangle(
                    zoom[:2],
                    zoom[2] - zoom[0],
                    zoom[3] - zoom[1],
                    fill=False,
                    ec="#444444",
                    lw=0.8,
                    zorder=6,
                )
            )
    handles = [
        Line2D(
            [],
            [],
            ls="",
            marker=s["marker"],
            mfc=s["c"],
            mec="white",
            ms=8,
            label=s["label"],
        )
        for s in STYLE.values()
    ]
    handles.append(Rectangle((0, 0), 1, 1, fc="#e4e4e4", label="Active model faces"))
    fig.legend(handles=handles, loc="outside lower center", ncol=3, frameon=False)
    fig.suptitle(
        f"Power plants and substations against flood maps. {LABEL}.\n"
        "Depth is not failure: floor heights, walls and site protection are unknown.\n"
        "A hindcast and still-water levels, not probabilities. Larger marks = plants.",
        fontsize=10.5,
        x=0.01,
        ha="left",
    )
    fig.savefig(OUT / "exposure_map.png", dpi=130)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("step", choices=("sample", "tables", "figure", "update"))
    ap.add_argument("--maps", nargs="+", choices=list(MAPS), default=list(MAPS))
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.step in ("sample", "update"):
        sample(a.maps)
    if a.step in ("tables", "update"):
        tables()
    if a.step in ("figure", "update"):
        figure()


if __name__ == "__main__":
    main()
