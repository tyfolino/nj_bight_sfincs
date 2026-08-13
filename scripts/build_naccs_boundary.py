#!/usr/bin/env python
"""Build a NACCS/CHS water-level boundary forcing file for Sandy.

    python scripts/build_naccs_boundary.py                  # active NJ_DOMAIN
    python scripts/build_naccs_boundary.py --report-only    # screen + report, write nothing
    python scripts/build_naccs_boundary.py --epoch-offset 0.115

Reads the CHS webtool zips in ``data/NACCS/``, extracts Sandy from each ADCIRC
save-point timeseries, screens down to the points that serve this domain's
``mask==2`` boundary, converts MSL(1992) -> NAVD88, and writes a hydromt
GeoDataset to ``data/gtsm/naccs_sandy_<domain>.nc``.

The premier boundary is TWO nodes across a 123 km gauge desert. `tide-gtsm`
raised that to 4 and lost, partly because density was never solved (11.1 km
median to the Raritan limb). This is the density fix: 112 points on v1, nothing
extrapolated past 2 km.

THE CONSTRUCTION
----------------

**1. Dedupe on save-point ID.** Area-grabs overlap — 83 of the 401 points arrived
in two zips. Repeats are free. Duplicates are asserted identical rather than
first-wins; a disagreement would mean two products got mixed into one directory.

**2. Sandy is `Tropical_Historical` AND `Storm ID == 001`.** Every file bundles
all 7 validation storms. Filtering on type alone also gets Irene, Isabel,
Josephine and Gloria.

**3. `-99999` is dry, and is never interpolated across.** 57 of 401 points are dry
more than half of Sandy. Filling them by interpolation produced the retracted
x0.613 range deficit. A point dry for even one step in the window is DROPPED, not
patched: SFINCS needs a complete series at every bnd node, and a fabricated value
there propagates into the domain.

**4. Only points within `--max-dist` of a `mask==2` cell are kept.** Grimley et al.
take 5,500+ ADCIRC points down to 341 on the SFINCS boundary, using only points
within 2.0 km so nothing is extrapolated
(`docs/campaigns/2026-08_published_boundary_practice.md`). Same rule here.

⚠️ The screen must live in the FILE. ``water_level.create`` selects by buffering
the mask==2 line by ``Domain.waterlevel_buffer`` — 100 km on v1. An unscreened
file hands SFINCS all 401 points, including deep interior Raritan Bay ones. The
buffer is a domain invariant guarding every other arm; do not retune it for one.

**5. MSL(1992) -> NAVD88 per point, from NOAA VDatum.** Also Grimley et al.'s
method. A scalar will not do — the separation drifts 0.065 m across the domain,
concentrated in the limb this campaign is about. Cached to
``data/NACCS/vdatum_lmsl_navd88.csv``.

⚠️ The epochs differ: NACCS ships MSL epoch 1992, VDatum's LMSL is 1983-2001. The
script cross-checks itself at Sandy Hook against the independently known -0.073 m
(NOAA-published, reproduced by the NACCS conversion key) and refuses to write if
they disagree by more than ``DATUM_TOL``. Measured agreement: 0.004 m.

**6. Steric is ALREADY APPLIED — do not add it.** The CHS readme documents +0.155 m
for storm 001. Across 136 deep save points the quiet pre-storm mean is +0.178 m
against a datum that should sit at ~0. Re-adding it double-counts.

**7. Secular sea-level rise is NOT applied by default.** See ``EPOCH_RISE``.

AFTER THIS RUNS
---------------

The printed support-point count must be declared as ``n_waterlevel_support=<N>``
on the ARM in ``nj_sfincs/config.py`` — never relaxed on the Domain, which guards
every other arm. ``check_waterlevel_support`` fails loudly otherwise, by design.

Per CLAUDE.md §6, report the flanking-gauge check beside the incumbent:
``python scripts/holdout_gauge_check.py``. It is a diagnostic, not a gate, and it
compares forcing products to gauges — never a model diagnostic.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
import time
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pyproj  # noqa: E402  (project convention: pyproj before hydromt_sfincs)
import xarray as xr  # noqa: E402

from nj_sfincs import domain as _domain  # noqa: E402

NACCS = ROOT / "data" / "NACCS"
OUTDIR = ROOT / "data" / "gtsm"          # legacy dir name; all forcing .nc live here
VDATUM_CACHE = NACCS / "vdatum_lmsl_navd88.csv"
PARSE_CACHE = NACCS / "_sandy_parsed.npz"

# Sandy in the CHS validation set.
STORM_TYPE = "Tropical_Historical"
STORM_ID = "001"
DRY = -9000.0                            # anything below this is the -99999 dry flag

# Keep a generous lead-in so np.interp never extrapolates at the model's tstart.
# A window that starts exactly at tstart gets silently clamped flat by np.interp
# and fabricates both tidal range and lag.
PAD_START = datetime(2012, 10, 24)
PAD_STOP = datetime(2012, 11, 1)

# Grimley et al.'s no-extrapolation limit.
DEFAULT_MAX_DIST = 2000.0                # metres

# Independently known MSL->NAVD88 at Sandy Hook: NOAA-published, and reproduced
# by the NACCS conversion key (-0.073 / -0.1218). Used to validate VDatum.
DATUM_ANCHOR = {"name": "Sandy Hook", "lon": -74.0091, "lat": 40.4669, "offset": -0.073}
DATUM_TOL = 0.030                        # metres

# ── The 1992-epoch problem (measured 2026-08-09) ─────────────────────────────
# NACCS is referenced to MSL epoch **1992**, and VDatum converts that epoch
# correctly (fitted 1992 annual-mean MSL at Sandy Hook is -0.088 m NAVD88; VDatum
# gives -0.077). But October 2012 water was not sitting at the 1992 mean. Fitting
# NOAA monthly MSL 1991-2012 (product=monthly_mean, datum=NAVD):
#
#     8531680 Sandy Hook   6.5 mm/yr   MSL1992 -0.088 -> MSL2012 +0.042   130 mm
#     8518750 The Battery  5.0 mm/yr   MSL1992 -0.074 -> MSL2012 +0.026   100 mm
#
# The CHS +0.155 m steric term cannot absorb this: the readme calls it a
# *seasonal* adjustment ("weighted average of the seasonal adjustment values from
# NOAA gauges"), so it carries the October high, not twenty years of secular rise.
#
# Measured consequence: the uncorrected product is 0.140 m low at Sandy Hook in
# the QUIET pre-storm window, before any surge, and only loses another 0.10 m
# across the whole storm (quiet -0.140 -> crest -0.238). The incumbent is the
# mirror image: -0.022 quiet, -0.221 at the crest.
#
# ⚠️ This number is measured from GAUGE RECORDS, not fitted to the NACCS residual.
# It is applied only when --epoch-offset is passed, to a separately named file, so
# the corrected and uncorrected arms differ by exactly this constant and nothing
# else. The ~0.10 m that grows during the storm is a genuine surge deficit and is
# NOT corrected here.
EPOCH_RISE = 0.115                       # mean of the two stations, metres


# ──────────────────────────────────────────────────────────────────────────────
# 1. Read the raw zips
# ──────────────────────────────────────────────────────────────────────────────
def _rows_for_sandy(raw: bytes):
    """Parse one save-point CSV. Returns (sp, lat, lon, depth, times, wl).

    ⚠️ The webtool pads every CSV with NUL bytes out to a power-of-two size
    (4 MiB / 2 MiB). The content itself is complete — this is padding, not
    truncation — but a reader that does not strip it chokes on a garbage last
    record. `rstrip(b"\\x00")` before decoding.
    """
    txt = raw.rstrip(b"\x00").decode("utf-8", "replace")
    rdr = csv.reader(io.StringIO(txt))
    for _ in range(3):                   # 3 header rows: names, codes, units
        next(rdr)
    sp = lat = lon = depth = None
    times, wl = [], []
    for r in rdr:
        if len(r) < 10:
            continue
        if sp is None:
            sp, lat, lon, depth = int(r[0]), float(r[1]), float(r[2]), float(r[3])
        if r[6] == STORM_TYPE and r[5].strip() == STORM_ID:
            times.append(r[7])
            wl.append(float(r[9]))
    if sp is None or not times:
        return None
    return sp, lat, lon, depth, np.array(times), np.array(wl, dtype="float64")


def read_zips(use_cache: bool = True) -> dict:
    """Walk data/NACCS/*.zip, dedupe on save-point ID, return {sp: record}."""
    zips = sorted(NACCS.glob("*.zip"))
    if not zips:
        sys.exit(f"no zips in {NACCS} — download from the CHS webtool first")

    stamp = np.array([z.stat().st_mtime_ns for z in zips], dtype="int64")
    if use_cache and PARSE_CACHE.exists():
        c = np.load(PARSE_CACHE, allow_pickle=True)
        if c["stamp"].shape == stamp.shape and (c["stamp"] == stamp).all():
            print(f"[read] cache hit — {len(c['sp'])} save points from {PARSE_CACHE.name}")
            return {int(s): dict(sp=int(s), lat=float(a), lon=float(o), depth=float(d),
                                 wl=w)
                    for s, a, o, d, w in zip(c["sp"], c["lat"], c["lon"], c["depth"],
                                             c["wl"])} | {"_times": c["times"]}

    pts, times_ref, ndup = {}, None, 0
    for z in zips:
        zf = zipfile.ZipFile(z)
        members = [m for m in zf.namelist()
                   if m.startswith("CSV/") and m.endswith("Timeseries.csv")]
        print(f"[read] {z.name}: {len(members)} timeseries")
        for m in members:
            got = _rows_for_sandy(zf.read(m))
            if got is None:
                print(f"   !! {m}: no Sandy rows — skipped")
                continue
            sp, lat, lon, depth, t, w = got
            if times_ref is None:
                times_ref = t
            elif not np.array_equal(t, times_ref):
                sys.exit(f"SP{sp}: Sandy timestamps differ from the other files "
                         f"({len(t)} vs {len(times_ref)}). Refusing to align by "
                         "index — that would silently shift a storm.")
            if sp in pts:
                ndup += 1
                if not np.array_equal(pts[sp]["wl"], w):
                    sys.exit(f"SP{sp} appears twice with DIFFERENT values. Two "
                             "different products are mixed in data/NACCS/.")
                continue
            pts[sp] = dict(sp=sp, lat=lat, lon=lon, depth=depth, wl=w)

    print(f"[read] {len(pts)} unique save points ({ndup} duplicate files, values agree)")
    print(f"[read] Sandy window {times_ref[0]} -> {times_ref[-1]}, {len(times_ref)} steps "
          f"@ {_step_minutes(times_ref):.0f} min")

    np.savez(PARSE_CACHE, stamp=stamp, times=times_ref,
             sp=np.array([p["sp"] for p in pts.values()]),
             lat=np.array([p["lat"] for p in pts.values()]),
             lon=np.array([p["lon"] for p in pts.values()]),
             depth=np.array([p["depth"] for p in pts.values()]),
             wl=np.array([p["wl"] for p in pts.values()]))
    return pts | {"_times": times_ref}


def _step_minutes(t: np.ndarray) -> float:
    a = datetime.strptime(str(t[0]), "%Y%m%d%H%M")
    b = datetime.strptime(str(t[1]), "%Y%m%d%H%M")
    return (b - a).total_seconds() / 60.0


# ──────────────────────────────────────────────────────────────────────────────
# 2. Screen against this domain's mask==2 boundary
# ──────────────────────────────────────────────────────────────────────────────
#: 🔴 THE DEPTH SCREEN, applied ONLY seaward of ``Domain.open_coast_max_y``.
#:
#: WHY IT EXISTS. The NACCS README states its water level "includes storm surge,
#: astronomical tide, and WAVE SETUP" (CSTORM-MS: ADCIRC coupled to STWAVE via radiation
#: stress). That by itself is NOT double counting — one-way nesting is supposed to hand
#: SFINCS the total level AT the boundary depth and let SnapWave add what develops
#: shoreward. The defect is WHERE THE SUPPORT POINTS SIT: the distance screen below has no
#: depth term, so points can sit in 0–4 m of water up to 2 km SHOREWARD of the boundary
#: they are then weighted onto.
#:
#: Measured on the parsed save points (ADCIRC node depth, open coast only):
#:     window                      slope of WL vs depth      corr
#:     quiet 10-26..10-28          -0.0047 m/m (flat)       -0.389
#:     peak  10-29 18h..10-30 04h  -0.0327 m/m              -0.835
#: ⇒ shallow points run ~+0.23 m ABOVE deep ones at the crest, and the gradient appears
#: ONLY during the storm — so it is storm-driven, not a datum or bathymetry artefact. That
#: +0.23 m cannot be split between wave setup and shoaling surge without STWAVE output, and
#: it does not need to be: SFINCS computes BOTH shoreward of the boundary.
#:
#: ⚠️ WHY IT IS NOT A BLANKET SCREEN. In a semi-enclosed bay the water is shallow
#: everywhere, the waves are small, SnapWave adds little setup — and those are exactly the
#: points that fix an under-forced interior lobe. Measured, the depth-vs-peak correlation
#: inside such a lobe is −0.371 against the open coast's −0.835. A blanket depth screen
#: would delete the useful points where the risk is lowest.
#:
#: ⚠️ AND THE BLAST RADIUS IS SMALL. Of 38 scored marks in the campaign that raised this,
#: only 3 sat where embedded OPEN-COAST setup could land. It is a CONSTRUCTION defect worth
#: fixing, not an explanation of a headline result.
DEFAULT_MIN_DEPTH = 8.0  # metres; open-coast points shallower than this are dropped


def boundary_cells(dom) -> tuple[np.ndarray, np.ndarray]:
    """(x, y) of every mask==2 cell of the frozen mesh, in the domain CRS."""
    mesh = dom.frozen_mesh_dir() / "sfincs.nc"
    if not mesh.exists():
        sys.exit(f"missing frozen mesh {mesh}")
    ds = xr.open_dataset(mesh)
    sel = ds["mask"].values == 2
    if not sel.any():
        sys.exit(f"{mesh} has no mask==2 cells")
    return ds["mesh2d_face_x"].values[sel], ds["mesh2d_face_y"].values[sel]


def support_sha(lon: np.ndarray, lat: np.ndarray) -> str:
    """16-hex digest of the support-point GEOMETRY.

    Two boundary files built from the same product but a different screen are different
    forcings, and nothing else in the file says so. Stamped into the output so a run can be
    traced to the point set that forced it, the way the domain fingerprint traces a run to
    its mesh.
    """
    import hashlib

    h = hashlib.sha256()
    h.update(np.ascontiguousarray(np.round(lon, 6), dtype="float64").tobytes())
    h.update(np.ascontiguousarray(np.round(lat, 6), dtype="float64").tobytes())
    return h.hexdigest()[:16]


def screen(
    pts: dict,
    times: np.ndarray,
    dom,
    max_dist: float,
    crs_epsg: int,
    min_depth: float = DEFAULT_MIN_DEPTH,
):
    """Keep points that (a) serve the boundary, (b) are wet all window, and (c) are deep
    enough IF they sit on the open coast.

    Returns (kept, dist, report). `kept` preserves save-point order by ID.
    """
    ids = sorted(k for k in pts if isinstance(k, int))
    lat = np.array([pts[i]["lat"] for i in ids])
    lon = np.array([pts[i]["lon"] for i in ids])
    dep = np.array([pts[i]["depth"] for i in ids])

    bx, by = boundary_cells(dom)
    tr = pyproj.Transformer.from_crs("EPSG:4326", f"EPSG:{crs_epsg}", always_xy=True)
    px, py = tr.transform(lon, lat)
    d = np.hypot(bx[:, None] - px[None, :], by[:, None] - py[None, :])

    near = d.min(axis=0)                 # per save point: distance to nearest bnd cell
    cell = d.min(axis=1)                 # per bnd cell: distance to nearest save point

    # Dry screen, evaluated ONLY inside the padded model window — a point that is
    # dry in mid-October but wet through the storm is perfectly usable.
    tt = np.array([datetime.strptime(str(s), "%Y%m%d%H%M") for s in times])
    win = (tt >= PAD_START) & (tt <= PAD_STOP)
    wet_all = np.array([np.all(pts[i]["wl"][win] > DRY) for i in ids])

    # Depth screen, SEAWARD ONLY. `open_coast_max_y` is the northing above which the coast
    # is no longer open ocean; None means the whole seaward edge is open coast.
    limit = dom.open_coast_max_y
    open_coast = np.ones(len(ids), dtype=bool) if limit is None else (py < limit)
    deep_enough = ~open_coast | (dep >= min_depth)

    keep = (near <= max_dist) & wet_all & deep_enough
    rep = dict(
        n_total=len(ids),
        n_near=int((near <= max_dist).sum()),
        n_dropped_dry=int(((near <= max_dist) & ~wet_all).sum()),
        n_open_coast=int((open_coast & (near <= max_dist)).sum()),
        n_dropped_shallow=int(
            ((near <= max_dist) & wet_all & open_coast & ~deep_enough).sum()
        ),
        min_depth_m=float(min_depth),
        n_kept=int(keep.sum()),
        n_bnd=len(bx),
        max_gap_km=float(cell.max() / 1000),
        within2=float(100 * (cell < 2000).mean()),
        within5=float(100 * (cell < 5000).mean()),
    )
    # Coverage recomputed on the KEPT set — this is the number that matters, because the
    # dropped points force nothing.
    if keep.any():
        ck = d[:, keep].min(axis=1)
        rep["kept_max_gap_km"] = float(ck.max() / 1000)
        rep["kept_within2"] = float(100 * (ck < 2000).mean())
        rep["kept_within5"] = float(100 * (ck < 5000).mean())
        rep["support_sha"] = support_sha(lon[keep], lat[keep])

        # ⭐ PER-ARM COVERAGE. Aggregate coverage HIDES "0 points on this arm", which on a
        # domain whose whole claim is that two short cross-sections carry the exchange is
        # the single most important thing to know BEFORE the run rather than after it. If
        # an arm comes back empty, the fallback is 1-node-per-arm gauge forcing —
        # defensible for a ~1 km cut, unlike a 123 km gauge desert.
        rep["per_arm"] = {}
        for arm in getattr(dom, "boundary_arms", ()):
            xmin, ymin, xmax, ymax = arm.box
            inbox = (bx > xmin) & (bx < xmax) & (by > ymin) & (by < ymax)
            if not inbox.any():
                rep["per_arm"][arm.name] = dict(
                    n_cells=0, n_pts=0, max_gap_km=float("nan")
                )
                continue
            sub = d[np.ix_(inbox, keep)]
            rep["per_arm"][arm.name] = dict(
                n_cells=int(inbox.sum()),
                # a support point "serves" this arm if its nearest cell in it is in range
                n_pts=int((sub.min(axis=0) <= max_dist).sum()),
                max_gap_km=float(sub.min(axis=1).max() / 1000),
                within2=float(100 * (sub.min(axis=1) < 2000).mean()),
            )
    return [ids[k] for k in range(len(ids)) if keep[k]], near[keep], rep


# ──────────────────────────────────────────────────────────────────────────────
# 3. MSL(1992) -> NAVD88 via NOAA VDatum
# ──────────────────────────────────────────────────────────────────────────────
def _vdatum(lon: float, lat: float) -> float:
    """NAVD88 height of 0 m LMSL at (lon, lat), i.e. the offset to ADD."""
    url = ("https://vdatum.noaa.gov/vdatumweb/api/convert?"
           f"s_x={lon:.6f}&s_y={lat:.6f}&s_z=0&region=contiguous&s_coor=geo"
           "&s_h_frame=NAD83_2011&s_v_frame=LMSL&s_v_unit=m"
           "&t_h_frame=NAD83_2011&t_v_frame=NAVD88&t_v_unit=m")
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            tz = float(json.load(r)["t_z"])
    except Exception as exc:  # noqa: BLE001
        print(f"   !! VDatum failed at ({lon:.4f},{lat:.4f}): {exc}")
        return float("nan")
    return tz if tz > -1000 else float("nan")


def datum_offsets(ids, lon, lat, refresh: bool = False) -> np.ndarray:
    """Per-save-point MSL->NAVD88, cached. Fails loudly, never silently constant."""
    cache = {}
    if VDATUM_CACHE.exists() and not refresh:
        with VDATUM_CACHE.open() as f:
            for row in csv.DictReader(f):
                cache[int(row["sp_id"])] = float(row["offset_navd88_m"])

    todo = [i for i in ids if i not in cache]
    if todo:
        print(f"[datum] querying NOAA VDatum at {len(todo)} save points "
              f"({len(cache)} cached) ...")
        for n, sp in enumerate(todo, 1):
            k = ids.index(sp)
            cache[sp] = _vdatum(lon[k], lat[k])
            if n % 25 == 0:
                print(f"   {n}/{len(todo)}")
            time.sleep(0.10)
        VDATUM_CACHE.parent.mkdir(parents=True, exist_ok=True)
        with VDATUM_CACHE.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["sp_id", "offset_navd88_m"])
            for sp in sorted(cache):
                w.writerow([sp, f"{cache[sp]:.4f}"])

    off = np.array([cache[i] for i in ids], dtype="float64")
    bad = ~np.isfinite(off)
    if bad.any():
        sys.exit(f"VDatum returned no offset at {int(bad.sum())} of {len(ids)} points "
                 f"(e.g. SP{ids[int(np.argmax(bad))]}). Refusing to fall back to a "
                 "constant — the MSL-NAVD88 separation drifts across Raritan Bay, "
                 "which is the limb this campaign is about. Re-run to retry; delete "
                 f"{VDATUM_CACHE.name} to refresh.")

    # Cross-check against the independently known value at Sandy Hook.
    a = DATUM_ANCHOR
    ka = int(np.argmin(np.hypot((lon - a["lon"]) * np.cos(np.deg2rad(a["lat"])),
                                lat - a["lat"])))
    got, want = off[ka], a["offset"]
    dkm = np.hypot((lon[ka] - a["lon"]) * np.cos(np.deg2rad(a["lat"])) * 111,
                   (lat[ka] - a["lat"]) * 111)
    print(f"[datum] anchor check at {a['name']}: nearest save point SP{ids[ka]} "
          f"({dkm:.1f} km)  VDatum {got:+.3f}  known {want:+.3f}  "
          f"diff {got - want:+.3f} m")
    if abs(got - want) > DATUM_TOL:
        sys.exit(f"VDatum disagrees with the known MSL->NAVD88 at {a['name']} by "
                 f"{got - want:+.3f} m (tolerance {DATUM_TOL:.3f}). NACCS ships MSL "
                 "epoch 1992 and VDatum's LMSL is the 1983-2001 epoch; a gap this "
                 "large means that difference is NOT negligible here and the "
                 "conversion needs the CHS per-save-point key instead.")
    print(f"[datum] offsets: mean {off.mean():+.3f}  min {off.min():+.3f}  "
          f"max {off.max():+.3f} m  (spread {off.max() - off.min():.3f} m)")
    return off


# ──────────────────────────────────────────────────────────────────────────────
# 4. Emit
# ──────────────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--domain", default=os.environ.get("NJ_DOMAIN"),
                    help="domain name (default: NJ_DOMAIN / registry default)")
    ap.add_argument("--max-dist", type=float, default=DEFAULT_MAX_DIST,
                    help="max metres from a mask==2 cell for a point to be kept "
                         f"(default {DEFAULT_MAX_DIST:.0f}, Grimley et al.'s "
                         "no-extrapolation limit)")
    ap.add_argument("--min-depth", type=float, default=DEFAULT_MIN_DEPTH,
                    help="minimum ADCIRC node depth [m] for an OPEN-COAST support point "
                         f"(default {DEFAULT_MIN_DEPTH:.0f}). ⚠️ Applied ONLY seaward of "
                         "Domain.open_coast_max_y — NACCS embeds wave setup, and a "
                         "shallow open-coast point carries ~+0.23 m of storm-driven "
                         "nearshore rise onto a deeper boundary. A BLANKET screen would "
                         "delete the interior points that fix an under-forced lobe, where "
                         "the risk is lowest. Pass 0 to disable.")
    ap.add_argument("--epoch-offset", type=float, default=0.0,
                    help="metres of secular sea-level rise to add, correcting the "
                         "1992 MSL epoch to 2012 conditions. Writes a SEPARATE file "
                         "(<name>_epoch.nc) so the uncorrected arm stays intact. "
                         f"Measured value: {EPOCH_RISE:.3f} m (see EPOCH_RISE).")
    ap.add_argument("--report-only", action="store_true",
                    help="screen and report; write nothing")
    ap.add_argument("--refresh-datum", action="store_true",
                    help="re-query VDatum instead of using the cache")
    ap.add_argument("--no-cache", action="store_true",
                    help="re-parse the zips instead of using the parse cache")
    args = ap.parse_args()

    if args.domain:
        os.environ["NJ_DOMAIN"] = args.domain
    dom = _domain.active()
    print(f"domain: {dom.name}\n")

    raw = read_zips(use_cache=not args.no_cache)
    times = raw.pop("_times")
    pts = raw

    crs_epsg = 32618                     # the mesh `crs` var carries no usable epsg attr
    kept, near, rep = screen(
        pts, times, dom, args.max_dist, crs_epsg, min_depth=args.min_depth
    )

    print(f"\n[screen] {rep['n_total']} save points -> "
          f"{rep['n_near']} within {args.max_dist:.0f} m of a mask==2 cell "
          f"-> {rep['n_kept']} kept ({rep['n_dropped_dry']} dropped: dry at some "
          "point in the window)")
    if args.min_depth > 0:
        print(f"[screen] depth screen >= {rep['min_depth_m']:.0f} m, applied to the "
              f"{rep['n_open_coast']} OPEN-COAST points only "
              f"(open_coast_max_y = {dom.open_coast_max_y}): "
              f"{rep['n_dropped_shallow']} dropped as too shallow. NACCS embeds wave "
              "setup; a shallow open-coast point carries nearshore rise onto a deeper "
              "boundary.")
    print(f"[screen] boundary coverage, {rep['n_bnd']} mask==2 cells:")
    print(f"   all {rep['n_total']} points : max gap {rep['max_gap_km']:5.2f} km  "
          f"<2km {rep['within2']:5.1f}%  <5km {rep['within5']:5.1f}%")
    if "kept_max_gap_km" in rep:
        print(f"   {rep['n_kept']} kept points : max gap {rep['kept_max_gap_km']:5.2f} km  "
              f"<2km {rep['kept_within2']:5.1f}%  <5km {rep['kept_within5']:5.1f}%")
        print(f"   support geometry sha16 : {rep['support_sha']}")
    # ⭐ PER ARM. Aggregate coverage hides "0 points on this arm" — read this, not the
    # headline percentage. An empty arm means falling back to 1-node gauge forcing there.
    if rep.get("per_arm"):
        print("[screen] per-arm coverage (an EMPTY arm is the finding, not a footnote):")
        for name, a in rep["per_arm"].items():
            if a["n_pts"] == 0:
                print(f"   🔴 {name:<14} {a['n_cells']:5d} cells   NO SUPPORT POINT "
                      "within range — fall back to 1-node gauge forcing on this arm")
            else:
                print(f"   {name:<17} {a['n_cells']:5d} cells  {a['n_pts']:4d} pts  "
                      f"max gap {a['max_gap_km']:5.2f} km  <2km {a['within2']:5.1f}%")
    if not kept:
        sys.exit("no save point survives the screen — nothing to write")
    if args.report_only:
        print("\n--report-only: screen reported, no VDatum query, nothing written")
        return 0

    lat = np.array([pts[i]["lat"] for i in kept])
    lon = np.array([pts[i]["lon"] for i in kept])
    off = datum_offsets(kept, lon, lat, refresh=args.refresh_datum)

    tt = np.array([datetime.strptime(str(s), "%Y%m%d%H%M") for s in times])
    win = (tt >= PAD_START) & (tt <= PAD_STOP)
    wl = np.stack([pts[i]["wl"][win] for i in kept], axis=1)      # (time, stations)
    assert (wl > DRY).all(), "a dry value survived the screen — the wet test is broken"
    total = wl + off[None, :] + args.epoch_offset
    if args.epoch_offset:
        print(f"[epoch] added {args.epoch_offset:+.3f} m of secular sea-level rise "
              "(1992 MSL epoch -> 2012 conditions)")

    ds = xr.Dataset(
        {"waterlevel": (("time", "stations"), total)},
        coords={"time": tt[win].astype("datetime64[ns]"),
                "stations": ("stations", np.array(kept, dtype="int64")),
                "lon": ("stations", lon),
                "lat": ("stations", lat)},
    )
    ds["waterlevel"].attrs.update(units="m", datum="NAVD88")
    ds.attrs.update(
        title=f"NACCS/CHS ADCIRC storm tide — Hurricane Sandy — {dom.name} boundary",
        source=("USACE CHS North Atlantic Coast Comprehensive Study (NACCS), "
                "Validations_BaseConditions+1Tide, ADCIRC ST_Validations, "
                "SimB1HT (base + historical tide), Post0, storm 001 Sandy 2012"),
        datum="NAVD88",
        units="m",
        domain=dom.name,
        n_support=len(kept),
        method=(f"Sandy (Tropical_Historical / ID {STORM_ID}) extracted from "
                f"{rep['n_total']} ADCIRC save points; kept the {len(kept)} that lie "
                f"within {args.max_dist:.0f} m of a mask==2 cell AND are wet at every "
                "step of the padded window; -99999 (dry) NEVER interpolated across; "
                "MSL(1992)->NAVD88 added per point from NOAA VDatum (LMSL->NAVD88)."),
        epoch_offset=(f"{args.epoch_offset:+.3f} m added for secular sea-level rise, "
                      "1992 MSL epoch -> 2012. Measured by fitting NOAA monthly MSL "
                      "1991-2012 at Sandy Hook (130 mm) and the Battery (100 mm); "
                      "measured from gauge records, NOT fitted to the model residual. "
                      "0.000 means this is the AS-PUBLISHED product."
                      if args.epoch_offset else
                      "0.000 — as-published NACCS, no epoch correction. The product is "
                      "0.140 m low at Sandy Hook in the quiet pre-storm window because "
                      "its datum is the 1992 MSL epoch; see EPOCH_RISE in the builder."),
        steric=("The CHS +0.155 m baroclinic steric adjustment for storm 001 is ALREADY "
                "APPLIED in the released timeseries (measured +0.167 m quiet-window mean "
                "at SP11329, 22 m depth). It is deliberately NOT re-added here."),
        coverage=(f"{rep['n_bnd']} mask==2 cells: max gap "
                  f"{rep.get('kept_max_gap_km', float('nan')):.2f} km, "
                  f"{rep.get('kept_within2', float('nan')):.1f}% within 2 km. "
                  "Precedent: Grimley et al. interpolate 341 ADCIRC points onto the "
                  "SFINCS boundary using only points within 2.0 km."),
        per_arm_coverage=json.dumps(rep.get("per_arm", {})),
        # The support GEOMETRY, hashed. Two files built from the same product but a
        # different screen are different forcings, and nothing else here says so.
        support_sha=rep.get("support_sha", ""),
        depth_screen=(
            f"open-coast points shallower than {rep['min_depth_m']:.0f} m dropped "
            f"({rep['n_dropped_shallow']} of {rep['n_open_coast']} open-coast points). "
            "NACCS water level INCLUDES wave setup (CSTORM-MS: ADCIRC + STWAVE via "
            "radiation stress), and the distance screen alone admits points up to 2 km "
            "SHOREWARD of the boundary they are weighted onto, carrying ~+0.23 m of "
            "storm-driven nearshore rise. Applied ONLY seaward of "
            f"open_coast_max_y={dom.open_coast_max_y}: inside a semi-enclosed bay the "
            "water is shallow everywhere, the waves are small, and those are the points "
            "that fix an under-forced interior."
            if rep["min_depth_m"] > 0 else
            "DISABLED (--min-depth 0). ⚠️ The kept set may include open-coast points "
            "shoreward of the boundary, carrying embedded wave setup."
        ),
        datum_check=(f"VDatum vs the independently known MSL->NAVD88 at "
                     f"{DATUM_ANCHOR['name']} ({DATUM_ANCHOR['offset']:+.3f} m, NOAA-"
                     "published and reproduced by the NACCS conversion key): agreed "
                     f"within {DATUM_TOL:.3f} m. NACCS MSL is epoch 1992; VDatum LMSL "
                     "is the 1983-2001 epoch."),
        time_pad=(f"Padded to {PAD_START:%Y-%m-%d} .. {PAD_STOP:%Y-%m-%d}, wider than the "
                  "model window, so np.interp never extrapolates at tstart. A product "
                  "starting exactly at tstart gets clamped flat and fabricates range "
                  "and lag."),
        created=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )

    print(f"\n[out] {len(kept)} support points, {ds.sizes['time']} steps "
          f"{str(ds.time.values[0])[:16]} -> {str(ds.time.values[-1])[:16]}")
    print(f"[out] peak {float(ds.waterlevel.max()):+.3f} m NAVD88 at "
          f"{str(ds.time.values[int(ds.waterlevel.max('stations').argmax())])[:16]}")
    print(f"[out] mean nearest-boundary distance of kept points: {near.mean():.0f} m "
          f"(max {near.max():.0f} m)")

    if args.report_only:
        print("\n--report-only: nothing written")
        return 0

    OUTDIR.mkdir(parents=True, exist_ok=True)
    suffix = "_epoch" if args.epoch_offset else ""
    out = OUTDIR / f"naccs_sandy_{dom.name}{suffix}.nc"
    tmp = out.with_suffix(".nc.tmp")
    ds.to_netcdf(tmp)
    tmp.replace(out)                     # atomic: a truncated forcing file reads clean
    print(f"[out] wrote {out}")

    print(f"""
NEXT — two things, neither automatic:

  1. Register the geodataset in data/data_catalog.yml:

       naccs_sandy_{dom.name}:
         data_type: GeoDataset
         uri: gtsm/{out.name}
         driver:
           name: geodataset_xarray
           options: {{}}
         metadata:
           category: ocean
           crs: 4326
           unit: m+NAVD88
           source: NACCS/CHS ADCIRC SimB1HT storm 001 (Sandy), {len(kept)} save points, MSL(1992)->NAVD88 via VDatum

  2. Declare the support-point count on the ARM in nj_sfincs/config.py:

       waterlevel_geodataset="naccs_sandy_{dom.name}",
       n_waterlevel_support={len(kept)},

     Do NOT relax Domain.n_waterlevel_support — that invariant guards every other
     arm on this domain, including the sealed premier.

  Then report the flanking-gauge check beside the incumbent (CLAUDE.md §6):
       python scripts/holdout_gauge_check.py
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
