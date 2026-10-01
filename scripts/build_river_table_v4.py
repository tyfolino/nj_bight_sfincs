"""v4 river-inflow decision table: how far each gauge's flow is from the flow that
actually crosses the model edge, and a PROPOSED scaling for the user to approve.

READ-ONLY with respect to every data product: it reads the discharge file, the ring
and the NLDI flowline cache, and writes only into ``OUT`` (``river_table.csv``,
``river_table.md``, ``summary.json``, and the HTTP cache ``cache/``).

    export PATH=$HOME/nj_sandy_sfincs/micromamba/envs/sfincs/bin:$PATH
    export PYTHONPATH=$PWD NJ_DOMAIN=v4
    export PROJ_DATA=/home/tpj8/nj_sandy_sfincs/micromamba/envs/sfincs/share/proj
    python scripts/build_river_table_v4.py [OUT]

``OUT`` defaults to ``logs/v4_design_2026-09-28/river_table`` — where the 09-28 decision
table (STATUS) and its cache live, so a re-run is offline. Promoted from that folder
2026-09-30; the logic is unchanged.

Per source (the 61 in ``usgs_sandy_discharge_v4.nc``, in ``STATIONS_V4`` order):

* gauge drainage area — USGS monitoring-locations ``drainage_area`` (mi2).
* where the river crosses the ring — the cached NLDI mainstem flowline
  (``logs/v4_design_2026-09-26/v4q/nldi_cache``; downstream from a gauge outside the
  ring, upstream from one inside) intersected with the CURRENT ring
  (``data/v4_design/region_v4_vertices.csv``).
* drainage area at the crossing — NHDPlus v2 VAA ``TotDASqKM`` of the flowline the
  crossing sits on, minus the unreached part of that flowline's own catchment
  (``AreaSqKM × (1 − fraction along)``, a linear-in-length assumption). The gauge gets
  the same treatment from its NLDI ``measure``, so the ratio compares like with like.
* area OUTSIDE the ring that drains to this source — the NLDI upstream basin polygon
  (of the crossing's flowline for a gauge above the crossing, of the gauge's flowline
  for a gauge below it) minus the ring, in EPSG:5070. This is what the model never sees
  as rain; for a gauge inside the ring it also counts side branches that cross the ring
  somewhere else (no source of their own).
* scale ratio = outside-ring area / gauge area (both NHDPlus-based).
* tidal signal — a least-squares M2/S2/K1/O1 fit to the gauge's 15-min discharge record
  over the calm 2012-10-14..26 fortnight; ``m2_pct`` = M2 amplitude / mean flow.

HTTP answers are cached in ``cache/``; a re-run is offline.
"""

# ruff: noqa: I001  (pyproj must be imported before geopandas)
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import xarray as xr

import pyproj  # noqa: F401  (before geopandas / hydromt — see nj_sfincs/__init__.py)
import geopandas as gpd
from shapely.geometry import LineString, Point, Polygon, shape
from shapely.ops import linemerge, unary_union

REPO = Path(__file__).resolve().parents[1]
HERE = Path(
    sys.argv[1] if len(sys.argv) > 1 else REPO / "logs/v4_design_2026-09-28/river_table"
)  # OUT
HERE.mkdir(parents=True, exist_ok=True)
V4Q = REPO / "logs/v4_design_2026-09-26/v4q"
CACHE = HERE / "cache"
CACHE.mkdir(exist_ok=True)
sys.path.insert(0, str(REPO))
os.environ.setdefault("NJ_DOMAIN", "v4")

from nj_sfincs import usgs_ogc  # noqa: E402

NLDI = "https://api.water.usgs.gov/nldi/linked-data"
WFS = "https://api.water.usgs.gov/geoserver/wmadata/ows"
MI2_KM2 = 2.589988
UA = {"User-Agent": "nj_bight_sfincs (research; Hurricane Sandy hindcast)"}

# ── the source list, exactly as the discharge file was built ────────────────────────
_spec = importlib.util.spec_from_file_location(
    "dl", REPO / "scripts/download_usgs_sandy_discharge.py"
)
_dl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_dl)
ST = pd.DataFrame(_dl.STATIONS_V4)
assert len(ST) == 61, len(ST)

# ── regulation: STATUS 09-26 list (gauge at / just below a dam) + reservoirs far up ──
REG_AT_DAM = {  # STATUS.md 09-26 "Regulated"
    "01377000": "gauge below Lake Tappan dam (reservoir releases)",
    "01407500": "gauge below Swimming River Reservoir dam",
    "01405030": "gauge at Westons Mills dam (Farrington Lake above)",
    "01393450": "gauge at Ursino Lake",
    "01389890": "gauge at Dundee Dam; reservoirs + diversions upstream",
    "01483700": "gauge below Silver Lake, Dover",
}
REG_FAR_UP = {  # general knowledge, NOT from STATUS — check the USGS site remarks
    "01463500": "reservoirs far upstream (NYC, F.E. Walter, Beltzville)",
    "01474500": "reservoirs upstream (Blue Marsh et al.)",
    "01400500": "Spruce Run + Round Valley reservoirs upstream",
    "01465500": "Lake Galena (Peace Valley) upstream",
    "01377500": "Woodcliff Lake reservoir upstream",
}


# ── HTTP with a file cache ──────────────────────────────────────────────────────────
def cached_json(key: str, url: str, params: dict | None = None, allow404=False):
    f = CACHE / f"{key}.json"
    if f.exists():
        return json.loads(f.read_text())
    delay = 5.0
    for _ in range(6):
        time.sleep(0.4)
        try:
            r = requests.get(url, params=params, headers=UA, timeout=180)
        except requests.RequestException as e:
            print(f"  retry {key}: {e}", file=sys.stderr)
        else:
            if r.status_code == 200:
                f.write_text(r.text)
                return r.json()
            if r.status_code == 404 and allow404:
                f.write_text("null")
                return None
            print(f"  HTTP {r.status_code} {key}", file=sys.stderr)
        time.sleep(delay)
        delay *= 2
    raise RuntimeError(f"failed: {key} {url}")


def usgs_meta(site: str) -> dict:
    f = CACHE / f"meta_{site}.json"
    if f.exists():
        return json.loads(f.read_text())
    rows = usgs_ogc.items("monitoring-locations", id=f"USGS-{site}")
    f.write_text(json.dumps(rows[0] if rows else {}))
    return rows[0] if rows else {}


def vaa(comid: int) -> dict:
    j = cached_json(
        f"vaa_{comid}",
        WFS,
        dict(
            service="WFS",
            version="2.0.0",
            request="GetFeature",
            typeName="wmadata:nhdflowline_network",
            outputFormat="application/json",
            propertyName="comid,gnis_name,lengthkm,areasqkm,totdasqkm,divdasqkm",
            CQL_FILTER=f"comid={comid}",
        ),
    )
    return j["features"][0]["properties"]


def catchment(comid: int):
    j = cached_json(
        f"cat_{comid}",
        WFS,
        dict(
            service="WFS",
            version="2.0.0",
            request="GetFeature",
            typeName="wmadata:catchmentsp",
            outputFormat="application/json",
            CQL_FILTER=f"featureid={comid}",
        ),
    )
    return unary_union([shape(ft["geometry"]) for ft in j["features"]])


def basin(kind: str, ident: str):
    j = cached_json(
        f"basin_{kind}_{ident}", f"{NLDI}/{kind}/{ident}/basin", {"simplified": "false"}
    )
    return unary_union([shape(ft["geometry"]) for ft in j["features"]])


def flowlines(site: str, mode: str) -> list[dict]:
    f = V4Q / "nldi_cache" / f"USGS-{site}_{mode}_80.json"
    if f.exists():
        j = json.loads(f.read_text())
    else:
        j = cached_json(
            f"fl_{site}_{mode}",
            f"{NLDI}/nwissite/USGS-{site}/navigation/{mode}/flowlines",
            {"distance": 80},
        )
    return [ft for ft in j["features"] if ft["geometry"]["type"] == "LineString"]


def tidal_m2(site: str) -> tuple[float, float, int]:
    """M2 amplitude as % of mean flow, and % of the HIGH-PASSED variance (flow minus
    its 25-h running mean, which removes rain events and trends) that a regular
    M2/S2/K1/O1 tide explains. A tidal gauge scores high on the second; noise does not."""
    f = CACHE / f"iv2_{site}.csv"
    if not f.exists():
        try:
            df = usgs_ogc.continuous(
                site, "00060", "ft^3/s", "2012-10-01T00:00:00Z", "2012-10-26T00:00:00Z"
            )
            df[["value"]].to_csv(f)
        except Exception as e:  # noqa: BLE001 — record the absence, do not fail
            print(f"  no IV {site}: {e}", file=sys.stderr)
            pd.DataFrame({"value": []}).to_csv(f)
    s = pd.read_csv(f, index_col=0, parse_dates=True)["value"].dropna()
    if len(s) < 200:
        return np.nan, np.nan, len(s)
    s = s.resample("15min").mean().interpolate(limit=8).dropna()
    hp = (s - s.rolling("25h", center=True).mean()).dropna()
    t = (hp.index - hp.index[0]).total_seconds().values / 3600.0
    cols = [np.ones_like(t)]
    for per in (12.4206, 12.0, 23.9345, 25.8193):
        w = 2 * np.pi / per
        cols += [np.cos(w * t), np.sin(w * t)]
    A = np.column_stack(cols)
    y = hp.values.astype(float)
    c, *_ = np.linalg.lstsq(A, y, rcond=None)
    tide = A[:, 1:] @ c[1:]
    m2 = np.hypot(c[1], c[2])
    var_hp = np.var(y)
    expl = 100 * np.var(tide) / var_hp if var_hp > 0 else 0.0
    return 100 * m2 / max(float(s.mean()), 1e-6), expl, len(s)


# ── geometry ───────────────────────────────────────────────────────────────────────
v = pd.read_csv(REPO / "data/v4_design/region_v4_vertices.csv", comment="#")
RING_LL = Polygon(zip(v.lon, v.lat))
RING_M = gpd.GeoSeries([RING_LL], crs=4326).to_crs(32618).iloc[0]
RING_EA = gpd.GeoSeries([RING_LL], crs=4326).to_crs(5070).iloc[0]


def to_m(g):
    return gpd.GeoSeries([g], crs=4326).to_crs(32618).iloc[0]


def to_ll(g):
    return gpd.GeoSeries([g], crs=32618).to_crs(4326).iloc[0]


def area_km2(g_ll):
    return gpd.GeoSeries([g_ll], crs=4326).to_crs(5070).iloc[0].area / 1e6


def outside_ring_km2(g_ll):
    ea = gpd.GeoSeries([g_ll], crs=4326).to_crs(5070).iloc[0]
    return ea.difference(RING_EA).area / 1e6


def crossing(site, mode, gauge_m):
    feats = flowlines(site, mode)
    lines_m = [
        (
            ft["properties"]["nhdplus_comid"],
            to_m(LineString(ft["geometry"]["coordinates"])),
        )
        for ft in feats
    ]
    merged = linemerge([L for _, L in lines_m])
    if merged.geom_type == "MultiLineString":
        merged = min(merged.geoms, key=lambda L: L.distance(gauge_m))
    s0 = merged.project(gauge_m)
    xs = merged.intersection(RING_M.exterior)
    pts = (
        [xs]
        if xs.geom_type == "Point"
        else [p for p in getattr(xs, "geoms", []) if p.geom_type == "Point"]
    )
    if mode == "DM":
        cand = [(merged.project(p) - s0, p) for p in pts if merged.project(p) >= s0 - 1]
    else:
        cand = [(s0 - merged.project(p), p) for p in pts if merged.project(p) <= s0 + 1]
    if not cand:
        return None
    d, p = min(cand, key=lambda t: t[0])
    comid, L = min(lines_m, key=lambda cl: cl[1].distance(p))
    frac = L.project(p) / L.length  # NHD flowlines run upstream -> downstream
    return dict(
        along_km=d / 1000, n_cross=len(pts), cross=to_ll(p), comid=int(comid), frac=frac
    )


def vaa_da(v: dict, frac_from_up: float) -> float:
    """Area draining to a point ``frac_from_up`` of the way down one NHDPlus flowline:
    DivDASqKM (= TotDASqKM unless the network diverges) minus the unreached share of
    the flowline's own catchment, assuming that share is linear in length."""
    return v["divdasqkm"] - v["areasqkm"] * (1.0 - frac_from_up)


# ── proposal rules (neutral defaults; the user decides) ─────────────────────────────
KEEP_BAND = 0.05  # |ratio - 1| within this: smaller than a daily-mean gauge's own error
SRC_OFF_M = 400  # source this far from the current crossing: placed on an older ring
DA_MISMATCH = 0.10  # NHDPlus vs USGS gauge area


def propose(r) -> tuple[str, str]:
    ratio, below = r.scale_ratio, r.side == "below"
    if not np.isfinite(ratio):
        return "ask", "no drainage area at the crossing; cannot size a scaling"
    pct = 100 * (ratio - 1)
    if r.site in REG_AT_DAM and abs(ratio - 1) > KEEP_BAND:
        return (
            "ask",
            f"regulated ({REG_AT_DAM[r.site]}); an area ratio ({ratio:.2f}) "
            "assumes natural runoff — options: keep, scale by area ratio",
        )
    ru = r.ratio_usgs_basis
    alt = f"; USGS's own gauge area gives {ru:.2f}" if r.da_mismatch else ""
    if not below and ratio > 1.5:
        return (
            "ask",
            f"gauge measures only {100 / ratio:.0f}% of what crosses — options: "
            "scale by area ratio, by ratio^0.8, keep (beyond the 0.5–1.5 range where "
            f"area scaling is usually trusted){alt}",
        )
    if (
        r.da_mismatch
        and np.isfinite(ru)
        and (
            (abs(ratio - 1) <= KEEP_BAND) != (abs(ru - 1) <= KEEP_BAND)
            or abs(ratio - ru) > 0.1
        )
    ):
        return (
            "ask",
            f"NHDPlus and USGS disagree on the gauge's area "
            f"({r.da_gauge_nhd_km2:.0f} vs {r.da_gauge_km2:.0f} km²): ratio "
            f"{ratio:.2f} or {ru:.2f} — options: keep, scale by either",
        )
    if abs(ratio - 1) <= KEEP_BAND:
        return (
            "keep as is",
            f"area feeding the edge differs from the gauge's by {pct:+.1f}%",
        )
    if below:
        if ratio < 0.3:
            return (
                "ask",
                f"{100 * (1 - ratio):.0f}% of the gauge's basin is inside the ring "
                "(rain covers it) — options: drop, scale by area ratio",
            )
        return (
            "scale by area ratio",
            f"gauge is inside the ring; {100 * (1 - ratio):.0f}% of its basin is also "
            "rained on in the model (counted twice)",
        )
    if ratio > 1.5:
        return (
            "ask",
            f"gauge measures only {100 / ratio:.0f}% of what crosses — options: "
            "scale by area ratio, by ratio^0.8, keep (beyond the 0.5–1.5 range where "
            "area scaling is usually trusted)",
        )
    return (
        "scale by area ratio",
        f"gauge is {r.along_km:.1f} km above the edge, which drains {pct:+.0f}% more area",
    )


def sanity() -> dict:
    """Gauge areas the task names, against published values."""
    known = {"01463500": 6780, "01403060": 785, "01389500": 762}
    out = {}
    for s, want in known.items():
        got = usgs_meta(s).get("drainage_area")
        out[s] = dict(
            usgs_mi2=got, expected_mi2=want, ok=bool(got and abs(got - want) < 1)
        )
    return out


def main():
    ds = xr.open_dataset(REPO / "data/discharge_v4/usgs_sandy_discharge_v4.nc")
    ids = [f"{i:08d}" for i in ds["index"].values]
    assert ids == list(ST.id), "nc order != STATIONS_V4 order"
    Q = ds["discharge"].to_pandas()
    Q.columns = ids

    rows = []
    for k, s in ST.iterrows():
        site = s.id
        print(f"[{k:2d}] {site} {s.river}", file=sys.stderr, flush=True)
        m = usgs_meta(site)
        da_usgs_mi2 = m.get("drainage_area")
        da_usgs_km2 = da_usgs_mi2 * MI2_KM2 if da_usgs_mi2 else np.nan
        g_m = to_m(Point(m["lon"], m["lat"]))
        mode = "DM" if s.side == "above" else "UM"
        flags = []
        hl = cached_json(f"nwis_{site}", f"{NLDI}/nwissite/USGS-{site}")
        hl = hl["features"][0]["properties"]
        gv = vaa(int(hl["comid"]))
        meas = float(
            hl["measure"]
        )  # 0 = downstream end of the flowline, 100 = upstream
        da_g = vaa_da(gv, 1.0 - meas / 100.0)
        diverg = abs(gv["divdasqkm"] - gv["totdasqkm"]) > 0.01 * gv["totdasqkm"]
        row = dict(
            idx=k,
            site=site,
            river=s.river,
            gauge_name=m.get("monitoring_location_name"),
            side=s.side,
            ring=(
                "gauge OUTSIDE ring (above crossing)"
                if s.side == "above"
                else "gauge INSIDE ring (below crossing)"
            ),
            da_gauge_mi2=da_usgs_mi2,
            da_gauge_km2=round(da_usgs_km2, 1),
            da_gauge_nhd_km2=round(da_g, 1),
            gauge_reach=gv["gnis_name"],
            src_lon=s.src_lon,
            src_lat=s.src_lat,
        )
        cx = crossing(site, mode, g_m)
        if cx is None:
            flags.append(
                "no ring crossing found on the NLDI flowline — area at crossing blank"
            )
            row.update(da_cross_km2=np.nan, da_outside_km2=np.nan, along_km=np.nan)
            ratio = np.nan
        else:
            cv = vaa(cx["comid"])
            da_c = vaa_da(cv, cx["frac"])
            diverg |= abs(cv["divdasqkm"] - cv["totdasqkm"]) > 0.01 * cv["totdasqkm"]
            if s.side == "above":
                # the ring itself splits the crossing reach's catchment
                b = basin("comid", str(cx["comid"]))
                out_km2, corr = outside_ring_km2(b), 0.0
            else:
                # remove the share of the gauge's own catchment that lies BELOW the gauge
                b = basin("nwissite", f"USGS-{site}")
                corr = outside_ring_km2(catchment(int(hl["comid"]))) * meas / 100.0
                out_km2 = outside_ring_km2(b) - corr
            src_m = to_m(Point(s.src_lon, s.src_lat))
            row.update(
                along_km=round(cx["along_km"], 2),
                n_cross=cx["n_cross"],
                cross_lon=round(cx["cross"].x, 5),
                cross_lat=round(cx["cross"].y, 5),
                cross_comid=cx["comid"],
                cross_reach=cv["gnis_name"],
                da_cross_km2=round(da_c, 1),
                da_outside_km2=round(out_km2, 1),
                below_gauge_corr_km2=round(corr, 1),
                src_to_cross_m=round(src_m.distance(to_m(cx["cross"]))),
            )
            if diverg:
                ratio = da_c / da_g
                flags.append(
                    "NHDPlus DIVERGENCE (basin polygon includes water routed "
                    "elsewhere): ratio from DivDA at crossing / gauge"
                )
            else:
                ratio = out_km2 / da_g
            if abs(cx["along_km"] - s.along_km) > 0.2:
                flags.append(
                    f"crossing now {cx['along_km']:.2f} km from gauge "
                    f"(file says {s.along_km})"
                )
            if row["src_to_cross_m"] > SRC_OFF_M:
                flags.append(
                    f"SOURCE {row['src_to_cross_m']} m from the current crossing "
                    "(placed on an older ring)"
                )
            if (
                cv["gnis_name"]
                and gv["gnis_name"]
                and cv["gnis_name"] != gv["gnis_name"]
            ):
                flags.append(
                    f"crossing is on '{cv['gnis_name']}', gauge on '{gv['gnis_name']}'"
                )
        row["scale_ratio"] = round(ratio, 3)
        row["ratio_basis"] = (
            "DivDA crossing / gauge"
            if diverg
            else "outside-ring basin / gauge (NHDPlus)"
        )
        row["ratio_usgs_basis"] = (
            round(ratio * da_g / da_usgs_km2, 3) if np.isfinite(da_usgs_km2) else np.nan
        )
        mism = np.isfinite(da_usgs_km2) and abs(da_g / da_usgs_km2 - 1) > DA_MISMATCH
        row["da_mismatch"] = bool(mism)

        q = Q[site]
        row["peak_q_m3s"] = round(float(q.max()), 2)
        row["peak_day"] = q.idxmax().strftime("%m-%d")
        m2, expl, n_iv = tidal_m2(site)
        row.update(
            m2_pct_of_mean=round(m2, 1) if np.isfinite(m2) else np.nan,
            tide_share_pct=round(expl, 1) if np.isfinite(expl) else np.nan,
            n_15min=n_iv,
        )

        # flags
        if site in REG_AT_DAM:
            flags.append("REGULATED: " + REG_AT_DAM[site])
        elif site in REG_FAR_UP:
            flags.append(
                "regulated far upstream (check the site remarks): " + REG_FAR_UP[site]
            )
        if np.isfinite(ratio) and ratio > 1.5:
            flags.append("PARTIAL BASIN")
        if s.side == "below":
            flags.append("gauge inside ring: in-ring part counted twice (gauge + rain)")
            if (
                not diverg
                and np.isfinite(row.get("da_cross_km2", np.nan))
                and row["da_outside_km2"] > 1.1 * row["da_cross_km2"]
            ):
                flags.append(
                    "side branches cross the ring elsewhere, unforced "
                    "(outside area > main-stem crossing area)"
                )
        if np.isfinite(row.get("along_km", np.nan)) and row["along_km"] > 5:
            flags.append(f"gauge {row['along_km']:.1f} km from the edge")
        if mism:
            flags.append(f"NHDPlus gauge area {da_g:.0f} vs USGS {da_usgs_km2:.0f} km2")
        if not da_usgs_mi2:
            flags.append("no USGS drainage area in site metadata")
        if (m.get("site_type_code") or "").endswith("TS"):
            flags.append("USGS site type: tidal stream")
        if np.isfinite(m2) and expl >= 30:
            flags.append(
                f"TIDAL signal in the flow record (tides {expl:.0f}% of "
                f"short-period variance; M2 {m2:.1f}% of mean flow)"
            )
        elif np.isfinite(m2) and expl >= 15 and m2 >= 2:
            flags.append(
                f"weak tidal signal? (tides {expl:.0f}% of short-period variance)"
            )
        elif not np.isfinite(m2):
            flags.append("tidal check not possible: no 15-min record for 2012-10")
        row["flags"] = "; ".join(flags)
        rows.append(row)

    t = pd.DataFrame(rows)
    act = t.apply(propose, axis=1, result_type="expand")
    t["proposed_action"], t["reason"] = act[0], act[1]
    fac = np.where(t.proposed_action == "scale by area ratio", t.scale_ratio, 1.0)
    t["proposed_factor"] = np.round(fac, 3)
    t["peak_q_proposed_m3s"] = np.round(t.peak_q_m3s * fac, 2)
    t["peak_q_if_ask_scaled_m3s"] = np.where(
        t.proposed_action == "ask", np.round(t.peak_q_m3s * t.scale_ratio, 2), np.nan
    )
    t.to_csv(HERE / "river_table.csv", index=False)

    f_prop = pd.Series(fac, index=t.site)
    f_askr = pd.Series(
        np.where(t.proposed_action == "ask", t.scale_ratio, fac), index=t.site
    )
    tot = {
        k: (Q * f).sum(axis=1)
        for k, f in [
            ("now", 1.0),
            ("proposed", f_prop),
            ("proposed_ask_scaled", f_askr),
        ]
    }
    summ = {
        "combined_daily_peak_m3s": {
            k: round(float(v.max()), 1) for k, v in tot.items()
        },
        "combined_peak_day": str(tot["now"].idxmax().date()),
        "sum_of_individual_peaks_m3s": {
            "now": round(float(Q.max().sum()), 1),
            "proposed": round(float((Q * f_prop).max().sum()), 1),
            "proposed_ask_scaled": round(float((Q * f_askr).max().sum()), 1),
        },
        "n_by_action": t.proposed_action.value_counts().to_dict(),
        "sanity_gauge_areas": sanity(),
    }
    (HERE / "summary.json").write_text(json.dumps(summ, indent=1))
    print(json.dumps(summ, indent=1))
    write_md(t, summ, intro_text(t, summ))


# ── the readable page ──────────────────────────────────────────────────────────────
SHORT = [  # (flag text starts with / contains, short label)
    ("REGULATED", "dam"),
    ("regulated far upstream", "res"),
    ("PARTIAL BASIN", "part"),
    ("gauge inside ring", "in"),
    ("side branches", "branch"),
    ("km from the edge", "far"),
    ("NHDPlus gauge area", "area?"),
    ("TIDAL signal", "tide"),
    ("weak tidal", "tide?"),
    ("tidal check not possible", "no15"),
    ("SOURCE ", "src-off"),
    ("DIVERGENCE", "div"),
    ("crossing now", "moved"),
    ("crossing is on", "name"),
]
ORDER = {"ask": 0, "scale by area ratio": 1, "keep as is": 2}


def short_flags(f: str) -> str:
    f = f if isinstance(f, str) else ""
    return " ".join(lab for key, lab in SHORT if key in f)


def intro_text(t: pd.DataFrame, s: dict) -> str:
    n = s["n_by_action"]
    c, sp = s["combined_daily_peak_m3s"], s["sum_of_individual_peaks_m3s"]
    d = t.peak_q_proposed_m3s - t.peak_q_m3s
    big = t.assign(d=d).reindex(d.abs().sort_values(ascending=False).index).head(6)
    ask = t[t.proposed_action == "ask"].assign(
        d=lambda x: x.peak_q_if_ask_scaled_m3s - x.peak_q_m3s
    )
    ask = ask.reindex(ask.d.abs().sort_values(ascending=False).index).head(6)
    fmt = lambda df: "; ".join(  # noqa: E731
        f"{r.river} {r.peak_q_m3s:.1f} → {r.peak_q_m3s + r.d:.1f}"
        for _, r in df.iterrows()
    )
    top3 = t.nlargest(3, "peak_q_m3s")
    return f"""# v4 river inflows — scaling decision table (proposal, 2026-09-28)

**What this is.** The v4 model gets river water from 61 USGS stream gauges
(`data/discharge_v4/usgs_sandy_discharge_v4.nc`), each injected where its river crosses
the model edge (the ring). A gauge rarely sits exactly at that crossing. A river's
*drainage area* is the land that drains to a given point; the further downstream the
point, the bigger that area and, roughly, the bigger the flow. *Drainage-area scaling*
multiplies the gauge's flow by (area draining to the crossing) ÷ (area draining to the
gauge), so the model gets the flow that really crosses its edge. It matters two ways: a
gauge upstream of the edge misses the tributaries that join in between (too little
water), and a gauge inside the ring also measures land the model already rains on (the
same water counted twice).

**How the areas were measured.** Gauge area from USGS site records (checked: Delaware at
Trenton 6,780 mi², Raritan below Calco Dam 785, Passaic at Little Falls 762 — all match).
"Area feeding the edge" = the USGS NLDI upstream basin (NHDPlus v2) minus the model ring,
i.e. the land the model never rains on that drains to this source; the ratio divides it by
the gauge's area computed the same way, so map errors cancel. "Ratio" near 1.00 means
nothing to fix. Rules used for the proposal (defaults, all yours to change): within ±5% →
keep; gauge inside the ring → scale down; gauge upstream with ratio up to 1.5 → scale up;
beyond 1.5, at a dam, or where the two area sources disagree → **ask**.

**How much it matters.** {n.get("ask", 0)} rows say **ask**, {n.get("scale by area ratio", 0)}
propose a scaling for you to approve, {n.get("keep as is", 0)} need nothing. The three
biggest sources ({", ".join(f"{r.river} {r.peak_q_m3s:.0f}" for _, r in top3.iterrows())}
m³/s) are all "keep": the Trenton and Philadelphia gauges sit 9.7 and 12.2 km inside the
ring, but the land between them and the edge is under 0.5% of their basins, so it is a
timing detail, not a volume one. All 61 rivers together peak at **{c["now"]:,.0f} m³/s**
now (daily mean, {s["combined_peak_day"]}); **{c["proposed"]:,.0f}** under the proposal
({100 * (c["proposed"] / c["now"] - 1):+.1f}%); **{c["proposed_ask_scaled"]:,.0f}** if every
"ask" row were also scaled by its ratio ({100 * (c["proposed_ask_scaled"] / c["now"] - 1):+.1f}%).
(Adding each river's own peak regardless of day: {sp["now"]:,.0f} → {sp["proposed"]:,.0f} →
{sp["proposed_ask_scaled"]:,.0f}.) The changes are local, not domain-wide. Largest proposed
changes, m³/s: {fmt(big)}. Largest "ask" rows if scaled: {fmt(ask)}.

**Also found (not scaling questions).** Beaverdam Branch (01484100) drains to the
**Mispillion**, not the Murderkill as the discharge script's label says — its crossing is on
the Mispillion, 4.2× the gauge's area. The Elizabeth River source sits ~1 km downstream of
where the river now crosses the ring (the ring was edited after the source was placed).
Tuckahoe, Absecon, Dove Nest, Spring Mill, Oyster and Cooper have no 15-minute record for
October 2012, so they could not be tested for tide in their flow; no gauge showed a tide
large enough to matter (largest: St Jones, where the tide is 43% of the short-term wiggle
but under 2% of the flow).

Sorted: **ask** first, then proposed scalings, then keep; biggest flow first within each.
"Gauge vs edge": *above* = gauge upstream of the crossing (outside the ring), *below* =
gauge inside the ring; km along the river.
"""


def write_md(t: pd.DataFrame, summ: dict, intro: str) -> None:
    t = t.assign(_o=t.proposed_action.map(ORDER)).sort_values(
        ["_o", "peak_q_m3s"], ascending=[True, False]
    )
    L = [intro, ""]
    hdr = (
        "| # | River (USGS gauge) | Gauge vs edge | Gauge area km² (mi²) | Area feeding "
        "the edge km² | Ratio | Peak now m³/s | Proposal | Peak after m³/s | Why | Flags |"
    )
    L += [hdr, "|" + "---|" * 11]
    for _, r in t.iterrows():
        where = (
            "above" if r.side == "above" else "**below**"
        ) + f", {r.along_km:.1f} km"
        after = (
            f"{r.peak_q_proposed_m3s:.1f}"
            if r.proposed_action != "ask"
            else f"{r.peak_q_m3s:.1f} or {r.peak_q_if_ask_scaled_m3s:.1f}"
        )
        act = {
            "ask": "**ASK**",
            "scale by area ratio": f"scale ×{r.scale_ratio:.2f}",
            "keep as is": "keep",
        }[r.proposed_action]
        L.append(
            f"| {r.idx} | {r.river} ({r.site}) | {where} | {r.da_gauge_km2:,.1f} "
            f"({r.da_gauge_mi2:,.4g}) | {r.da_outside_km2:,.1f} | {r.scale_ratio:.2f} | "
            f"{r.peak_q_m3s:.1f} | {act} | {after} | {r.reason} | {short_flags(r['flags'])} |"
        )
    L += [
        "",
        "**Flag key** — `dam` gauge at or just below a dam (regulated) · `res` "
        "reservoirs far upstream (not from STATUS; check the USGS site remarks) · `part` the "
        "gauge measures less than 2/3 of what crosses · `in` gauge inside the ring, so its "
        "in-ring part is counted twice · `branch` side branches of the same river cross the "
        "ring elsewhere with no source · `far` gauge > 5 km from the edge · `area?` NHDPlus "
        "and USGS disagree on the gauge's area by > 10% · `tide` / `tide?` a tide shows in "
        "the gauge's own discharge record · `no15` no 15-minute record to test for tide · "
        "`src-off` the source point is > 400 m from where the river crosses the CURRENT "
        "ring · `div` NHDPlus splits the flow here (divergence) · `moved` the crossing is "
        "not where the discharge file's notes say. Full text in `river_table.csv`, column "
        "`flags`.",
        "",
    ]
    (HERE / "river_table.md").write_text("\n".join(L))


if __name__ == "__main__":
    main()
