"""Diagnose the Keansburg HWM overshoot. READ-ONLY — writes only reports/keansburg/.

THE SYMPTOM (2026-08-20). Three marks near Keansburg (~lon −74.14, lat 40.44) read
obs ≈ 1.55 m NAVD88 and the premier run puts ~3.3 m of water on them — residuals
+1.67…+1.89 m — while every neighbour within 2 km (obs 3.6–4.4 m) validates to
±0.5 m. The marks sit in a 0.6–1.1 m pocket behind a ~2.5–2.9 m levee/road crest;
the modeled flood extent there also far exceeds MOTF.

THE TWO CANDIDATE MECHANISMS this script separates:
  (a) the MARKS are wrong for our purpose — STN metadata (datum, height-above-ground,
      environment, still-water-inside-a-structure) can put 1.55 m in a class our
      zsmax cannot be compared against. Two of the three are exactly 5.10 ft, which
      smells like one survey recorded twice.
  (b) the MODEL over-tops too easily — the USACE Keansburg levee + Waackaack Creek
      tide gates are not in the build (no structure file exists anywhere), and the
      berm crest falls outside the `bay_fringe` refinement gate (zmax=2.0), so it
      sits in 100 m cells whose subgrid tables can average a narrow crest away.

Outputs (reports/keansburg/):
  stn_records.json     full STN records for every mark in the box
  stn_table.csv        the fields that decide (a)
  transects.csv/.png   bed profiles: model subgrid vs USACE 2010 vs CUDEM, + model WSE
  marks_table.csv      scorer-style residual per mark (median, 50 m — the _scored keys'
                       estimator and radius) + MOTF wet/dry at the mark

Usage:  NJ_DOMAIN=v1_5_raritan python scripts/diagnose_keansburg.py [--skip-stn]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import nj_sfincs  # noqa: F401,E402 — pins the pyproj-before-hydromt import order
from nj_sfincs.config import exp_root  # noqa: E402

OUT = ROOT / "reports" / "keansburg"

# The Keansburg reach of the raritan_bay basin, and the three suspect marks.
BOX = (-74.22, 40.41, -74.05, 40.46)  # lon0, lat0, lon1, lat1
SUSPECTS = (6155, 6156, 6133)

# Shore-normal (N->S) transects, lon: the three suspect marks bracket by two controls
# that validate fine (6158 at -74.1632, 6154 at -74.1131). Sampled every 5 m.
TRANSECT_LONS = (-74.1632, -74.1466, -74.1422, -74.1362, -74.1131)
LAT_N, LAT_S, STEP_M = 40.4560, 40.4340, 5.0

# Scorer conventions — MUST match validate.metrics.hwm_metrics for the table to be
# quotable next to the _scored keys (never quote an HWM bias without these two).
ESTIMATOR, RADIUS_M = "median", 50.0
DEPTH_MIN, GROUND_CAP = 0.15, 0.5

STN_API = "https://stn.wim.usgs.gov/STNServices/Events/24/HWMs.json"
STN_FIELDS = (
    "hwm_id", "elev_ft", "vdatum_id", "vcollect_method_id", "hwm_quality_id",
    "hwm_type_id", "hwm_environment", "bank", "height_above_gnd", "stillwater",
    "flag_date", "survey_date", "hwm_locationdescription", "hwm_notes",
    "latitude_dd", "longitude_dd",
)


def stn_part() -> None:
    """(a): pull the full STN records for every mark in the box."""
    import requests

    r = requests.get(STN_API, timeout=60)
    r.raise_for_status()
    w, s, e, n = BOX
    recs = [x for x in r.json()
            if x.get("longitude_dd") is not None
            and w <= x["longitude_dd"] <= e and s <= x["latitude_dd"] <= n]
    (OUT / "stn_records.json").write_text(json.dumps(recs, indent=1))
    print(f"[stn] {len(recs)} STN marks in the Keansburg box -> stn_records.json")

    import csv
    with open(OUT / "stn_table.csv", "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(STN_FIELDS)
        for x in sorted(recs, key=lambda x: x.get("longitude_dd", 0)):
            wr.writerow([x.get(k) for k in STN_FIELDS])
    for x in recs:
        if x.get("hwm_id") in SUSPECTS:
            print(f"\n[stn] ── hwm_id {x['hwm_id']} "
                  f"({'IN' if x.get('hwm_quality_id', 9) <= 2 else 'not in'} "
                  "the q<=2 headline set) ──")
            for k in STN_FIELDS:
                print(f"        {k:24s} {x.get(k)!r}")


def _sampler(path):
    """Return sample(lons, lats) -> values for one raster, handling its CRS."""
    import rasterio
    from pyproj import Transformer

    src = rasterio.open(path)
    tf = (None if src.crs.to_epsg() == 4326
          else Transformer.from_crs(4326, src.crs, always_xy=True))

    def sample(lons, lats):
        xs, ys = (lons, lats) if tf is None else tf.transform(lons, lats)
        vals = np.array([v[0] for v in src.sample(zip(xs, ys))], dtype=float)
        if src.nodata is not None:
            vals[vals == src.nodata] = np.nan
        vals[np.abs(vals) > 1e5] = np.nan
        return vals

    return sample


def transect_part(run_dir: Path) -> None:
    """(b): bed profiles across the berm, model subgrid vs independent products."""
    import csv

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    products = {
        "model subgrid (3.125 m)": _sampler(run_dir / "subgrid" / "dep_subgrid_lev3.tif"),
        "USACE 2010 (~1 m)": _sampler(ROOT / "data/elevation/usace_nj_2010_topobathy_clip.tif"),
        "CUDEM 1/9\" (~3 m)": _sampler(ROOT / "data/elevation/cudem_nj.vrt"),
    }
    hmax = _sampler(run_dir / "floodmap_hmax_lev3.tif")
    dep6 = _sampler(run_dir / "subgrid" / "dep_subgrid_lev3.tif")

    nlat = int((LAT_N - LAT_S) * 111_000 / STEP_M)
    lats = np.linspace(LAT_N, LAT_S, nlat)

    fig, axes = plt.subplots(len(TRANSECT_LONS), 1,
                             figsize=(11, 2.6 * len(TRANSECT_LONS)), sharex=True)
    rows = []
    for ax, lon in zip(axes, TRANSECT_LONS):
        lons = np.full_like(lats, lon)
        prof = {name: s(lons, lats) for name, s in products.items()}
        h = hmax(lons, lats)
        wse = dep6(lons, lats) + h
        wse[~(h >= DEPTH_MIN)] = np.nan
        dist = (LAT_N - lats) * 111_000
        for name, z in prof.items():
            ax.plot(dist, z, lw=1, label=name)
        ax.plot(dist, wse, lw=1.5, ls="--", label="premier WSE (hmax)")
        ax.axhline(1.554, color="k", lw=0.6, ls=":", label="obs 1.55 m (suspect marks)")
        ax.set_title(f"lon {lon:.4f}"
                     + ("  ← control" if lon in (-74.1632, -74.1131) else
                        "  ← SUSPECT reach"), fontsize=9)
        ax.set_ylabel("m NAVD88")
        ax.grid(alpha=0.3)
        for name, z in prof.items():
            # crest = highest bed in the first 800 m from the bay side
            m = dist <= 800
            crest = np.nanmax(z[m]) if np.isfinite(z[m]).any() else np.nan
            crest_at = dist[m][np.nanargmax(z[m])] if np.isfinite(z[m]).any() else np.nan
            rows.append(dict(lon=lon, product=name, crest_m=round(float(crest), 2),
                             crest_dist_m=round(float(crest_at), 0)))
    axes[0].legend(fontsize=7, ncol=5)
    axes[-1].set_xlabel("distance south from lat 40.4560 (m)")
    fig.tight_layout()
    fig.savefig(OUT / "transects.png", dpi=150)
    with open(OUT / "transects.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=["lon", "product", "crest_m", "crest_dist_m"])
        wr.writeheader()
        wr.writerows(rows)
    print(f"[transect] {len(TRANSECT_LONS)} transects -> transects.png / transects.csv")
    print(f"[transect] crest heights (first 800 m from bay side):")
    for r in rows:
        print(f"    lon {r['lon']:.4f}  {r['product']:24s} crest {r['crest_m']:5.2f} m "
              f"at {r['crest_dist_m']:4.0f} m")


def marks_part(run_dir: Path) -> None:
    """Scorer-style residual per mark in the box + MOTF wet/dry at the mark."""
    import csv

    import geopandas as gpd

    from nj_sfincs import domain as _domain
    from nj_sfincs import validate

    _mod, da_hmax, da_dep = validate.load_floodmap(run_dir)
    hwm = gpd.read_file(str(_domain.active().hwm_geojson))
    w, s, e, n = BOX
    hwm = hwm.cx[w:e, s:n].to_crs(da_dep.rio.crs)

    depth, dep_arr = da_hmax.values, da_dep.values
    if depth.ndim == 3:
        depth, dep_arr = depth[0], dep_arr[0]
    wse = dep_arr + depth
    T = da_dep.rio.transform()
    ny, nx = wse.shape
    rad = int(round(RADIUS_M / abs(T.a)))

    motf = _sampler(ROOT / "data/validation/sandy_motf_extent.tif")
    hwm_ll = hwm.to_crs(4326)

    rows = []
    for (_, m), (_, mll) in zip(hwm.iterrows(), hwm_ll.iterrows()):
        X, Y = m.geometry.x, m.geometry.y
        col, row = int((X - T.c) / T.a), int((Y - T.f) / T.e)
        if not (0 <= row < ny and 0 <= col < nx):
            continue
        r0, c0 = max(0, row - rad), max(0, col - rad)
        sl = (slice(r0, row + rad + 1), slice(c0, col + rad + 1))
        ws, hh, dd = wse[sl], depth[sl], dep_arr[sl]
        flooded = (hh >= DEPTH_MIN) & (dd <= m["elev_m"] + GROUND_CAP)
        mod = (np.nanmedian(ws[flooded]) if flooded.any()
               else (np.nanmin(dd) if np.isfinite(dd).any() else np.nan))
        motf_wet = motf(np.array([mll.geometry.x]), np.array([mll.geometry.y]))[0]
        rows.append(dict(
            hwm_id=int(m["hwm_id"]), quality=int(m["quality"]),
            obs_m=round(float(m["elev_m"]), 3),
            mod_m=round(float(mod), 3) if np.isfinite(mod) else None,
            resid_m=round(float(mod - m["elev_m"]), 3) if np.isfinite(mod) else None,
            motf_wet=int(motf_wet) if np.isfinite(motf_wet) else None,
            suspect=int(m["hwm_id"]) in SUSPECTS,
        ))
    rows.sort(key=lambda r: -abs(r["resid_m"] or 0))
    with open(OUT / "marks_table.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)
    print(f"\n[marks] estimator={ESTIMATOR} radius={RADIUS_M:g} m "
          f"(matches the _scored keys) -> marks_table.csv")
    for r in rows:
        tag = "  <-- SUSPECT" if r["suspect"] else ""
        print(f"    {r['hwm_id']}  q{r['quality']}  obs {r['obs_m']:5.2f}  "
              f"mod {r['mod_m']}  resid {r['resid_m']}  motf_wet {r['motf_wet']}{tag}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--skip-stn", action="store_true", help="offline: skip the STN pull")
    ap.add_argument("--arm", default="naccs-premier")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    run_dir = exp_root() / args.arm
    if not (run_dir / "floodmap_hmax_lev3.tif").exists():
        sys.exit(f"no floodmap in {run_dir} — run --validate-only first")

    if not args.skip_stn:
        try:
            stn_part()
        except Exception as exc:  # noqa: BLE001 — offline is a warning, not a failure
            print(f"[stn] SKIPPED — {exc}")
    transect_part(run_dir)
    marks_part(run_dir)


if __name__ == "__main__":
    main()
