#!/usr/bin/env python
"""Tidal river beds the §54 inland-water review handed back, and a SHAPED cross-section.

    python scripts/build_riverbeds_tidal_v4.py fetch      # network: NOS, CO-OPS, eHydro (scratch)
    python scripts/build_riverbeds_tidal_v4.py evidence   # section shape from dense surveys
    python scripts/build_riverbeds_tidal_v4.py build      # the approved FLAT rule, 3 reaches
    python scripts/build_riverbeds_tidal_v4.py build --section shaped             # same, shaped
    python scripts/build_riverbeds_tidal_v4.py build --section shaped --existing  # GMRT 4 +
                                                                                  # Cohansey
    python scripts/build_riverbeds_tidal_v4.py conveyance # area below MLLW / MHHW per reach

WHY (1). The §54 review (``logs/inland_water_2026-10-05/DECISIONS.md`` case 2) excluded
three river stretches as TIDAL: the Christina at Newport, Big Timber Creek above
Westville and the St Jones at Dover. Their merged bed is CUDEM's flat ~0 m NAVD88 water
surface for 18 / 8+4+4 / 20 km, so they need a carved tidal channel, not a lake/river
repaint. The rule is the one the user approved on 2026-10-05 for the Cohansey and the GMRT
reaches (``build_riverbed_cohansey_v4.py``, ``build_riverbeds_gmrt_v4.py``): measured
soundings as a 1-D along-channel running median where they exist, else
``DEPTH_BELOW_MLLW_M`` below MLLW; flat across the NHD StreamRiver polygon (<= 300 m from
the centreline); DEEPEN ONLY against the A+ template's merged bed (ROTATED: read through
the inverse affine, self-checked against ``rasterio.sample``). MLLW - NAVD88 from NOAA
CO-OPS stations that publish both datums (VDatum's API answers 412 on this coast).

  * Christina: NOS H10042 (1982, echo sounder, 1:10k, MLLW) is a bank-to-bank survey of
    the river from Wilmington to Newport (lon -75.61); above it, to Christiana, stated.
    eHydro CR_02_UPR (2015+) ends at lon -75.561, exactly where CUDEM's bed goes flat.
  * Big Timber Creek: NOS H09886 (1980, echo sounder, 1:10k, MLW) covers the main stem to
    the fork; both branches are stated depth to where CUDEM's water surface ends.
  * St Jones: no survey above the mouth bar (NOS H10079, 1983, 6 soundings at Bowers);
    stated depth to the Silver Lake dam at Dover.

WHY (2). A FLAT section at a THALWEG depth over-deepens the banks: the Maurice's chart
soundings (sparse, mid-channel, shoal-biased) are painted bank to bank at ~-5 m. The
``--section shaped`` option paints depth below MLLW as

    d(xi) = d_c * (1 - (1 - xi) ** P),     xi = (distance to bank) / (local half-width)

i.e. MLLW at the NHD bank, d_c on the axis; section mean = d_c * P / (P + 1).
``evidence`` measured mean/thalweg depth = 0.55-0.65 on every dense survey of a natural
tidal river here (NOS H10042, H06254+H06218, H05893+H05894; eHydro MA_01_MRC; the model's
own surveyed lower Maurice), so P = 1.5 (0.60). d_c depends on what the profile MEANS
(``mg`` = the mean shape factor over the channel pixels at that station, ~0.6):
  * ``thalweg`` soundings (a chart's sparse mid-channel points): d_c = the depth;
  * ``section`` soundings (bank-to-bank lines; the running median is the section
    MEDIAN): d_c = 0.93 * depth / mg, capped at the soundings' own running p95 depth;
  * ``stated`` depth (1.2 m below MLLW, a typical depth, not a thalweg): d_c = depth /
    mg, so the section mean, and the area below MLLW, are the flat rule's.
Which kind each reach's soundings are is measured, not assumed (``evidence``: the
position across the channel of every sounding). Same deepen-only reference as each
original build (A+ merged bed; CUDEM for the Cohansey).

🔴 NEW FILES ONLY. ``_out`` refuses every pre-existing tier name (``riverbeds_v4.vrt``,
``riverbeds_gmrt_v4.vrt``, ``riverbed_gmrt_*_v4.tif``, ``riverbed_cohansey_v4.tif`` ...).
Outputs in data/elevation_v4/riverbeds/ (EPSG:32618, 5 m, NoData -9999, m NAVD88):
  flat    riverbed_tidal_<reach>_v4.tif + riverbeds_tidal_v4.vrt (+ _profiles.csv)
  shaped  riverbed_tidal_<reach>_shaped_v4.tif + riverbeds_tidal_shaped_v4.vrt
          riverbed_gmrt_<reach>_shaped_v4.tif + riverbeds_gmrt_shaped_v4.vrt
          riverbed_cohansey_shaped_v4.tif
Tables (``evidence``, ``conveyance``) go to ``--log-dir``. Apply as overlays
(``rebuild_subgrid.py --overlay <key>``), never prepended (CLAUDE.md §5).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_riverbed_cohansey_v4 as coh  # noqa: E402
import build_riverbeds_gmrt_v4 as gm  # noqa: E402
import build_riverbeds_v4 as rb  # noqa: E402
import download_nos_hydro_v4 as nos  # noqa: E402

#: bulk inputs (NOS surveys, CO-OPS datums, eHydro, NHD caches): scratch, not home
SRC = Path("/scratch/tpj8/nj_bight_sfincs_data/elevation_v4/tidal_carves")
COOPS = (
    "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/{id}/datums.json"
)
EHYDRO_MAURICE = (
    "https://ehydroprod.blob.core.usgovcloudapi.net/ehydro-surveys/CENAP/"
    "MA_01_MRC_20210721_CS.ZIP"
)
LOG_DIR = ROOT / "logs" / "refreeze_2026-10-05" / "tidal_carves"

DEPTH_BELOW_MLLW_M = 1.2  # the user's 10-05 stated depth (gm / coh use the same)
P_DEFAULT = 1.5  # section exponent: mean/thalweg 0.6, ``evidence`` (0.55-0.65 measured)
FT = 0.3048006096012192

#: Files this script must never write: the frozen / queued tiers.
PROTECTED = {
    "riverbeds_v4.vrt",
    "riverbeds_v4_profiles.csv",
    "riverbeds_gmrt_v4.vrt",
    "riverbeds_gmrt_v4_profiles.csv",
    "riverbed_cohansey_v4.tif",
    "riverbed_cohansey_v4_profile.csv",
}


def _out(name: str) -> Path:
    """A NEW output path in the riverbeds dir; refuses every existing tier's name."""
    if (
        name in PROTECTED
        or (name.startswith("riverbed_gmrt_") and not name.endswith("_shaped_v4.tif"))
        or (
            name.startswith("riverbed_")
            and name.endswith("_v4.tif")
            and "tidal" not in name
            and "shaped" not in name
        )
    ):
        raise SystemExit(f"🔴 refusing to write {name}: an existing tier")
    return rb.RB / name


@dataclass(frozen=True)
class Survey:
    sid: str
    block: str  # NCEI block, e.g. "H10001-H12000"
    year: int
    plane: str  # sounding datum, "MLLW" | "MLW"
    plane_navd88_m: float  # that plane - NAVD88 (CO-OPS, 1983-2001 epoch)


@dataclass(frozen=True)
class TReach:
    name: str
    mllw_navd88_m: float
    mhhw_navd88_m: float
    datum_note: str
    branches: tuple[gm.Branch, ...]
    surveys: tuple[Survey, ...] = ()
    kind: str = "section"  # what a sounding profile value means (module doc)
    why: str = ""


REACHES = (
    TReach(
        "christina",
        -0.907,
        0.924,
        "mean of CO-OPS 8551910 Reedy Point (MLLW -0.905, MHHW +0.875) and 8540433 "
        "Marcus Hook (-0.908, +0.973), which bracket Wilmington; the Christina's own "
        "stations (8550658 Millside, 8550714 Wilmington Marine Terminal) publish no datums",
        (
            gm.Branch(
                "Christina River",
                (-75.70, 39.62, -75.49, 39.76),
                (-75.70, 39.63),
                (-75.5606, 39.7248),  # station 7.85 km: CUDEM's surveyed bed ends
                (-75.6699, 39.6531),  # 25.6 km: Christiana, end of the tidal polygon
            ),
        ),
        (Survey("H10042", "H10001-H12000", 1982, "MLLW", -0.907),),
        kind="thalweg",  # above the federal reach H10042 runs mid-channel (xi p50 0.73)
        why="NOS H10042 (1982, bank-to-bank, MLLW) to Newport (lon -75.61); 1.2 m below "
        "MLLW above it to Christiana. Stops below R05 (Christina at Christiana, non-tidal, "
        "§54 repaint).",
    ),
    TReach(
        "bigtimber",
        -0.966,
        1.094,
        "mean of CO-OPS 8545240 Philadelphia USCG (MLLW -0.945, MHHW +1.094) and 8545530 "
        "Pier 11 (-0.987, +1.093); 8538601 Westville (on the creek) publishes no datums; "
        "H09886's MLW plane = mean MLW of the same two, -0.908",
        (
            gm.Branch(
                "Big Timber Creek",
                (-75.16, 39.80, -75.03, 39.90),
                (-75.085, 39.837),
                (-75.1318, 39.8779),  # 1.85 km: CUDEM's surveyed mouth ends
                (-75.0852, 39.8369),  # the fork
            ),
            gm.Branch(
                "North Branch Big Timber Creek",
                (-75.10, 39.78, -74.98, 39.86),
                (-74.99, 39.80),
                (-75.0852, 39.8369),
                (-75.0522, 39.8335),  # 3.95 km: CUDEM's water surface ends
            ),
            gm.Branch(
                "South Branch Big Timber Creek",
                (-75.10, 39.76, -74.98, 39.86),
                (-75.04, 39.76),
                (-75.0852, 39.8369),
                (-75.0840, 39.8110),  # 3.95 km: CUDEM's water surface ends
            ),
        ),
        (Survey("H09886", "H08001-H10000", 1980, "MLW", -0.908),),
        kind="section",  # bank to bank in the span (xi p25 0.24, p50 0.53)
        why="NOS H09886 (1980, bank-to-bank, MLW, epoch-corrected) to the fork; both "
        "branches 1.2 m below MLLW to where CUDEM's water surface ends.",
    ),
    TReach(
        "stjones",
        -0.890,
        0.921,
        "CO-OPS 8554399 Mahon River entrance (11 km N; MSL-MLLW 0.882, MHHW-MLLW 1.811) "
        "with MSL tied to NAVD88 through 8536931 Fortescue Creek (MSL-NAVD88 -0.008), as "
        "the §54 review did; the nearest stations publishing both datums are across the "
        "bay: Fortescue -0.982, Bivalve -1.040 (mean -1.011), and Lewes -0.801",
        (
            gm.Branch(
                "Saint Jones River",
                (-75.56, 39.03, -75.38, 39.20),
                (-75.55, 39.18),
                (-75.4015, 39.0667),  # Bowers: the river polygon starts
                (-75.5206, 39.1659),  # the Silver Lake dam, Dover
            ),
        ),
        (Survey("H10079", "H10001-H12000", 1983, "MLLW", -0.890),),
        kind="thalweg",  # 6 soundings on the mouth bar only
        why="No survey above the mouth bar (NOS H10079, 1983, 6 soundings at Bowers); "
        "1.2 m below MLLW to the Silver Lake dam at Dover.",
    ),
)

#: MHHW - NAVD88 of the reaches built elsewhere (CO-OPS, the stations their MLLW used)
MHHW_EXISTING = {
    "maurice": 0.873,  # 8535055 Bivalve
    "mullica": 0.502,  # 8534212 Chestnut Neck
    "tuckahoe": 0.576,  # mean 8534691 River Bend 0.550, 8535101 Middle Thorofare 0.602
    "rancocas": 1.250,  # mean 8539058 Assiscunk 1.302, 8538875 Pompeston 1.197
    "cohansey": 0.927,  # mean 8536931 Fortescue 0.978, 8551910 Reedy Point 0.875
}
#: What a GMRT reach's sounding profile value means, from where across the channel the
#: soundings sit (``evidence``; xi = 0 bank, 1 axis; bank to bank gives p25 ~0.25)
KIND_EXISTING = {
    "maurice": "thalweg",  # ENC 1:90k, xi p25 0.66 / p50 0.78
    "mullica": "thalweg",  # ENC 1:12k, xi p25 0.48 / p50 0.56
    "tuckahoe": "section",  # NOS 1937 lead line, bank to bank, xi p50 0.37
    "rancocas": "thalweg",  # ENC 1:12k, xi p25 0.52 / p50 0.63
}


# ── fetch ─────────────────────────────────────────────────────────────────────
def fetch() -> None:
    gm.fetch()  # the NHD HU4 0204 geodatabase (cached on scratch)
    for r in REACHES:
        for s in r.surveys:
            gz = SRC / "nos" / f"{s.sid}.a93.gz"
            if not gz.exists():
                rb._atomic_bytes(gz, rb._get(nos.A93.format(blk=s.block, sid=s.sid)))
    for sid in ("8551910", "8540433", "8545240", "8545530", "8554399", "8536931"):
        p = SRC / "coops" / f"datums_{sid}.json"
        if not p.exists():
            rb._atomic_bytes(p, rb._get(COOPS.format(id=sid) + "?units=metric"))
    eh = SRC / "ehydro" / "MA_01_MRC_20210721_CS.ZIP"
    if not eh.exists():
        rb._atomic_bytes(eh, rb._get(EHYDRO_MAURICE))
        with zipfile.ZipFile(eh) as f:
            f.extractall(SRC / "ehydro" / "MA_01_MRC_20210721_CS")
    print(f"inputs cached under {SRC}")


# ── geometry ──────────────────────────────────────────────────────────────────
def _nhd(r: TReach):
    """(StreamRiver polygons, named flowlines) in UTM, cached as GeoJSON on scratch."""
    import geopandas as gpd
    import pyogrio

    box = gm._reach_box(r)
    fa, ff = SRC / f"nhd_area_{r.name}.geojson", SRC / f"nhd_flowline_{r.name}.geojson"
    if not (fa.exists() and ff.exists()):
        a = pyogrio.read_dataframe(gm.NHD_GDB, layer="NHDArea", bbox=box)
        a = a[a.ftype == 460][["gnis_name", "ftype", "geometry"]]
        f = pyogrio.read_dataframe(
            gm.NHD_GDB, layer="NHDFlowline", bbox=box, columns=["gnis_name", "ftype"]
        )
        f = f[f.gnis_name.isin({b.river for b in r.branches})]
        f = f.set_geometry(f.geometry.force_2d())
        for g, p in ((a, fa), (f, ff)):
            rb._atomic_bytes(p, g.to_crs(4326).to_json().encode())
    return gpd.read_file(fa).to_crs(rb.EPSG), gpd.read_file(ff).to_crs(rb.EPSG)


def _soundings(r: TReach):
    """lon, lat, bed (m NAVD88), label: every NOS sounding of the reach's surveys."""
    lon, lat, z = [], [], []
    for s in r.surveys:
        d = nos.read_a93(
            SRC / "nos" / f"{s.sid}.a93.gz"
        )  # (lat, lon, depth below plane)
        epoch = -nos.SLR_M_PER_YR * (nos.EPOCH_MID - s.year)
        lat.append(d[:, 0])
        lon.append(d[:, 1])
        z.append(s.plane_navd88_m + epoch - d[:, 2])
    lab = "+".join(
        f"{s.sid} ({s.year}, {s.plane} {s.plane_navd88_m:+.3f})" for s in r.surveys
    )
    return (
        np.concatenate(lon),
        np.concatenate(lat),
        np.concatenate(z),
        f"NOS {lab}, epoch-corrected",
    )


@dataclass
class Part:
    """One branch: centreline, channel, profile, painted span, what the profile means."""

    line: object
    chan: object
    grid: np.ndarray
    prof: np.ndarray
    src: np.ndarray  # "soundings" | "stated" per station
    lo: float
    hi: float
    kind: str  # meaning of a "soundings" station: "thalweg" | "section"
    mllw: float
    deep: np.ndarray | None = (
        None  # running p5 of the sounding beds (the measured axis)
    )


def _deep(line, chan, snd, grid) -> np.ndarray:
    """Running 5th percentile of the sounding BEDS (m NAVD88) along the line: the deepest
    the soundings go, which caps a ``section`` reach's shaped centreline."""
    import geopandas as gpd
    import shapely

    lon, lat, z, _ = snd
    p = np.asarray(gpd.points_from_xy(lon, lat, crs=4326).to_crs(rb.EPSG))
    near = shapely.dwithin(chan, p, gm.NEAR_CHANNEL_M)
    out = np.full(grid.shape, np.nan)
    if not near.any():
        return out
    s = shapely.line_locate_point(line, p[near])
    o = np.argsort(s)
    s, zz = s[o], z[near][o]
    lo = np.searchsorted(s, grid - gm.WINDOW_M)
    hi = np.searchsorted(s, grid + gm.WINDOW_M)
    for i, (a, b) in enumerate(zip(lo, hi)):
        if b > a:
            out[i] = np.percentile(zz[a:b], 5)
    ok = np.isfinite(out)
    if ok.sum() >= 2:
        inside = (grid >= grid[ok][0]) & (grid <= grid[ok][-1])
        out[inside] = np.interp(grid[inside], grid[ok], out[ok])
    return out


def parts_tidal(r: TReach) -> list[Part]:
    area, flow = _nhd(r)
    snd = _soundings(r)
    out = []
    for b in r.branches:
        line = gm._line(b, flow)
        chan = gm._channel(area, line)
        grid, prof, src, note = gm.profile(r, line, chan, snd)
        lo, hi = _span(line, b)
        print(
            f"{r.name} / {b.river}: centreline {line.length / 1000:.1f} km, channel "
            f"{chan.area / 1e6:.2f} km²; {note}; painted span {lo:.0f}..{hi:.0f} m"
        )
        out.append(
            Part(
                line,
                chan,
                grid,
                prof,
                src,
                lo,
                hi,
                r.kind,
                r.mllw_navd88_m,
                _deep(line, chan, snd, grid),
            )
        )
    return out


def parts_gmrt(r) -> list[Part]:
    area, flow = gm._nhd(r)
    snd = gm._soundings(r)
    out = []
    for b in r.branches:
        line = gm._line(b, flow)
        chan = gm._channel(area, line)
        grid, prof, src, _ = gm.profile(r, line, chan, snd)
        lo, hi = _span(line, b)
        out.append(
            Part(
                line,
                chan,
                grid,
                prof,
                src,
                lo,
                hi,
                KIND_EXISTING[r.name],
                r.mllw_navd88_m,
                _deep(line, chan, snd, grid),
            )
        )
    return out


def parts_cohansey() -> list[Part]:
    r = coh.REACH
    line = coh.trace_centreline(r)
    chan = rb._channel(r, line)
    grid = np.arange(0.0, line.length + 25.0, 25.0)
    prof = np.full(grid.shape, coh.MLLW_NAVD88_M - coh.DEPTH_BELOW_MLLW_M)
    src = np.full(grid.shape, "stated")
    return [
        Part(
            line, chan, grid, prof, src, 0.0, line.length, "section", coh.MLLW_NAVD88_M
        )
    ]


def _span(line, b) -> tuple[float, float]:
    s_dn = line.project(gm._utm(*b.down))
    s_up = min(line.project(gm._utm(*b.up)) + gm.PAD_UP_M, line.length)
    return min(s_dn, s_up), max(s_dn, s_up)


# ── the cross-section ─────────────────────────────────────────────────────────
def g_shape(xi: np.ndarray, p: float) -> np.ndarray:
    """Depth / centreline depth at relative distance from the bank ``xi`` (0 bank, 1 axis)."""
    return 1.0 - (1.0 - np.clip(xi, 0.0, 1.0)) ** p


def centre_depth(
    depth: np.ndarray, src: np.ndarray, kind: str, p: float, mg: np.ndarray
) -> np.ndarray:
    """Centreline depth below MLLW from a profile depth, by what the profile value means.

    ``mg`` is the mean of ``g_shape`` over the channel pixels at each station (0.6 for an
    ideal P = 1.5 section; less where the polygon is all margin), so a STATED depth keeps
    its area exactly: the section mean = the stated depth. A ``section`` median becomes
    the mean the ideal shape implies (x 0.93 at P = 1.5); a ``thalweg`` stays the axis.
    """
    mg = np.clip(mg, 0.4, 1.0)  # no centreline spike where a station is all margin
    stated = src == "stated"
    if kind == "thalweg":
        f = np.where(stated, 1.0 / mg, 1.0)
    else:
        ideal = (p / (p + 1.0)) / (1.0 - 0.5**p)  # section mean / section median
        f = np.where(stated, 1.0, ideal) / mg
    return depth * f


def _mean_g(st, gg, n: int, p: float) -> np.ndarray:
    """Mean of the shape factor per 25 m station over +-50 m (NaN-free)."""
    from scipy.ndimage import uniform_filter1d

    k = np.clip(np.rint(st / 25.0).astype(int), 0, n - 1)
    num = uniform_filter1d(np.bincount(k, gg, minlength=n), 5, mode="nearest")
    den = uniform_filter1d(np.bincount(k, minlength=n).astype(float), 5, mode="nearest")
    return np.where(den > 0, num / np.maximum(den, 1e-9), p / (p + 1.0))


def _grid_for(parts: list[Part]):
    from rasterio.transform import from_origin

    bounds = np.array([pt.chan.bounds for pt in parts])
    x0 = np.floor(bounds[:, 0].min() / rb.RES) * rb.RES
    y1 = np.ceil(bounds[:, 3].max() / rb.RES) * rb.RES
    w = int(np.ceil((bounds[:, 2].max() - x0) / rb.RES))
    h = int(np.ceil((y1 - bounds[:, 1].min()) / rb.RES))
    return x0, y1, w, h, from_origin(x0, y1, rb.RES, rb.RES)


def bank_field(pt: Part, shape, T):
    """(inside mask, distance to bank m, station m, local half-width m) on the grid."""
    import shapely
    from rasterio.features import geometry_mask
    from scipy import ndimage

    inside = ~geometry_mask([pt.chan], shape, T)
    e = ndimage.distance_transform_edt(np.pad(inside, 1))[1:-1, 1:-1] * rb.RES
    rr, cc = np.nonzero(inside)
    px, py = T.c + (cc + 0.5) * rb.RES, T.f - (rr + 0.5) * rb.RES
    st = shapely.line_locate_point(pt.line, shapely.points(px, py))
    ee = e[rr, cc] - 0.5 * rb.RES  # pixel centre to the polygon edge
    k = np.clip((st / 25.0).astype(int), 0, len(pt.grid) - 1)
    bmax = np.zeros(len(pt.grid))
    np.maximum.at(bmax, k, ee)
    # running max over +-50 m: a bend hands a section's pixels to neighbouring stations
    from scipy.ndimage import maximum_filter1d

    bmax = maximum_filter1d(bmax, size=5, mode="nearest")
    return rr, cc, px, py, st, np.maximum(ee, 0.0), np.maximum(bmax[k], rb.RES)


def paint(parts: list[Part], section: str, p: float):
    """Bed (m NAVD88) on the reach grid: NaN off-channel. Returns (z, grid info, xi)."""
    x0, y1, w, h, T = _grid_for(parts)
    z = np.full((h, w), np.nan)
    for pt in parts:
        rr, cc, px, py, st, e, B = bank_field(pt, (h, w), T)
        on = (st >= pt.lo) & (st <= pt.hi)
        flat = np.interp(st[on], pt.grid, pt.prof)
        if section == "flat":
            v = flat
        else:
            dep = pt.mllw - pt.prof
            gg = g_shape(e[on] / B[on], p)
            mg = _mean_g(st[on], gg, len(pt.grid), p)
            dc = centre_depth(dep, pt.src, pt.kind, p, mg)
            if pt.kind == "section" and pt.deep is not None:
                # never deeper than the soundings themselves go (running p5 of the beds)
                cap = pt.mllw - pt.deep
                use = (pt.src == "soundings") & np.isfinite(cap)
                dc = np.where(use, np.minimum(dc, np.maximum(cap, dep)), dc)
            d = np.interp(st[on], pt.grid, dc) * gg
            v = np.where(np.interp(st[on], pt.grid, dep) > 0, pt.mllw - d, flat)
        z[rr[on], cc[on]] = np.fmin(z[rr[on], cc[on]], v)  # deepest where branches meet
    return z, (x0, y1, w, h, T)


def deepen_only(z, gridinfo, ref: str):
    """Drop every pixel where the reference bed is already at or below the new value."""
    x0, y1, *_ = gridinfo
    rr, cc = np.nonzero(np.isfinite(z))
    px, py = x0 + (cc + 0.5) * rb.RES, y1 - (rr + 0.5) * rb.RES
    if ref == "model":
        gm._self_check(px, py)
        old = gm.sample_model_bed(px, py)
    else:
        old = rb._sample(rb.CUDEM, px, py)
    new = z[rr, cc]
    keep = ~(np.isfinite(old) & (old <= new))
    z = z.copy()
    z[rr[~keep], cc[~keep]] = np.nan
    return z, old[keep], new[keep]


def write_tif(z, gridinfo, name: str, tags: dict) -> Path:
    import rasterio

    x0, y1, w, h, T = gridinfo
    out = _out(name)
    fd, tmp = tempfile.mkstemp(dir=rb.RB, prefix=f".{out.name}.", suffix=".tif")
    os.close(fd)
    with rasterio.open(
        tmp,
        "w",
        driver="GTiff",
        height=h,
        width=w,
        count=1,
        dtype="float32",
        crs=f"EPSG:{rb.EPSG}",
        transform=T,
        nodata=rb.NODATA,
        compress="deflate",
        tiled=True,
    ) as d:
        d.write(np.where(np.isfinite(z), z, rb.NODATA).astype("float32"), 1)
        d.update_tags(**{k: str(v) for k, v in tags.items()})
    os.chmod(tmp, 0o644)
    os.replace(tmp, out)
    return out


def write_vrt(name: str, tifs: list[Path]) -> Path:
    vrt = _out(name)
    subprocess.run(
        [
            "gdalbuildvrt",
            "-overwrite",
            "-srcnodata",
            str(rb.NODATA),
            "-vrtnodata",
            str(rb.NODATA),
            str(vrt),
            *map(str, tifs),
        ],
        check=True,
        capture_output=True,
    )
    print(f"wrote {vrt}")
    return vrt


# ── build ─────────────────────────────────────────────────────────────────────
def _report(name, z_before_keep_old, new, painted_px):
    km2 = painted_px * rb.RES**2 / 1e6
    print(
        f"  -> {name}: painted {km2:.2f} km²; old bed p50 "
        f"{np.nanmedian(z_before_keep_old):+.2f} -> new p50 {np.median(new):+.2f} m "
        f"(p5..p95 {np.percentile(new, 5):+.2f}..{np.percentile(new, 95):+.2f})"
    )
    return km2


def build(section: str, existing: bool, p: float) -> None:
    sfx = "" if section == "flat" else "_shaped"
    if existing:
        if section == "flat":
            raise SystemExit(
                "--existing builds the SHAPED variant only (--section shaped)"
            )
        tifs = []
        for r in gm.REACHES:
            parts = parts_gmrt(r)
            z, gi = paint(parts, section, p)
            z, old, new = deepen_only(z, gi, "model")
            tifs.append(
                write_tif(
                    z,
                    gi,
                    f"riverbed_gmrt_{r.name}_shaped_v4.tif",
                    {"reach": r.name, "section": f"shaped P={p}"},
                )
            )
            _report(tifs[-1].name, old, new, np.isfinite(z).sum())
        write_vrt("riverbeds_gmrt_shaped_v4.vrt", tifs)
        parts = parts_cohansey()
        z, gi = paint(parts, section, p)
        z, old, new = deepen_only(z, gi, "cudem")
        t = write_tif(
            z,
            gi,
            "riverbed_cohansey_shaped_v4.tif",
            {"reach": "cohansey", "section": f"shaped P={p}"},
        )
        _report(t.name, old, new, np.isfinite(z).sum())
        return
    tifs, rows = [], ["reach,branch,station_m,bed_navd88_m,source,painted_span"]
    for r in REACHES:
        parts = parts_tidal(r)
        z, gi = paint(parts, section, p)
        z, old, new = deepen_only(z, gi, "model")
        tags = {
            "reach": r.name,
            "why": r.why,
            "mllw_navd88": r.mllw_navd88_m,
            "section": "flat" if section == "flat" else f"shaped P={p}",
        }
        tifs.append(write_tif(z, gi, f"riverbed_tidal_{r.name}{sfx}_v4.tif", tags))
        _report(tifs[-1].name, old, new, np.isfinite(z).sum())
        for b, pt in zip(r.branches, parts):
            rows += [
                f"{r.name},{b.river},{s:.0f},{v:.3f},{c},{int(pt.lo <= s <= pt.hi)}"
                for s, v, c in zip(pt.grid, pt.prof, pt.src)
            ]
    write_vrt(f"riverbeds_tidal{sfx}_v4.vrt", tifs)
    if section == "flat":
        rb._atomic_bytes(
            _out("riverbeds_tidal_v4_profiles.csv"), ("\n".join(rows) + "\n").encode()
        )


# ── conveyance ────────────────────────────────────────────────────────────────
def _read_on_grid(path: Path, gridinfo) -> np.ndarray:
    """An overlay tif resampled (nearest) onto ``gridinfo``; NaN where NoData/absent."""
    import rasterio
    from rasterio.warp import Resampling, reproject

    x0, y1, w, h, T = gridinfo
    out = np.full((h, w), np.nan, dtype="float64")
    with rasterio.open(path) as s:
        reproject(
            s.read(1).astype("float64"),
            out,
            src_transform=s.transform,
            src_crs=s.crs,
            src_nodata=s.nodata,
            dst_transform=T,
            dst_crs=s.crs,
            dst_nodata=np.nan,
            resampling=Resampling.nearest,
        )
    return out


def conveyance(log_dir: Path) -> None:
    """Mean cross-section area (m²) below MLLW and MHHW over each painted span: the A+
    bed, the flat overlay applied, the shaped overlay applied (min with the bed)."""
    from shapely.ops import substring

    sets = []
    for r in REACHES:
        sets.append(
            (
                r.name,
                parts_tidal(r),
                r.mllw_navd88_m,
                r.mhhw_navd88_m,
                rb.RB / f"riverbed_tidal_{r.name}_v4.tif",
                rb.RB / f"riverbed_tidal_{r.name}_shaped_v4.tif",
            )
        )
    for r in gm.REACHES:
        sets.append(
            (
                r.name,
                parts_gmrt(r),
                r.mllw_navd88_m,
                MHHW_EXISTING[r.name],
                rb.RB / f"riverbed_gmrt_{r.name}_v4.tif",
                rb.RB / f"riverbed_gmrt_{r.name}_shaped_v4.tif",
            )
        )
    sets.append(
        (
            "cohansey",
            parts_cohansey(),
            coh.MLLW_NAVD88_M,
            MHHW_EXISTING["cohansey"],
            rb.RB / "riverbed_cohansey_v4.tif",
            rb.RB / "riverbed_cohansey_shaped_v4.tif",
        )
    )
    rows = [
        "reach,span_km,channel_km2,width_p50_m,mllw,mhhw,"
        "a_mllw_before,a_mllw_flat,a_mllw_shaped,a_mhhw_before,a_mhhw_flat,a_mhhw_shaped,"
        "painted_km2_flat,painted_km2_shaped,bed_p50_before,bed_p50_flat,bed_p50_shaped,"
        "axis_p50_flat,axis_p50_shaped"
    ]
    for name, parts, mllw, mhhw, f_flat, f_shp in sets:
        gi = _grid_for(parts)
        x0, y1, w, h, T = gi
        sel = np.zeros((h, w), bool)
        axis = np.zeros((h, w), bool)
        for pt in parts:
            rr, cc, px, py, st, e, B = bank_field(pt, (h, w), T)
            on = (st >= pt.lo) & (st <= pt.hi)
            sel[rr[on], cc[on]] = True
            ax = on & (e / B > 0.8)
            axis[rr[ax], cc[ax]] = True
        rr, cc = np.nonzero(sel)
        px, py = x0 + (cc + 0.5) * rb.RES, y1 - (rr + 0.5) * rb.RES
        z0 = gm.sample_model_bed(px, py)
        fl = _read_on_grid(f_flat, gi)[rr, cc]
        sh = _read_on_grid(f_shp, gi)[rr, cc]
        zf, zs = np.fmin(z0, fl), np.fmin(z0, sh)
        span = sum(pt.hi - pt.lo for pt in parts)
        a = rb.RES**2 / span

        def area(zz, plane):
            return float(np.nansum(np.clip(plane - zz, 0.0, None)) * a)

        ax = axis[rr, cc]
        wid = []
        for pt in parts:  # median polygon width across the span, from 100 m slices
            for s0 in np.arange(pt.lo, pt.hi, 100.0):
                seg = substring(pt.line, s0, min(s0 + 100.0, pt.hi))
                if seg.length > 50:
                    wid.append(
                        pt.chan.intersection(
                            seg.buffer(rb.MAX_HALFWIDTH_M, cap_style="flat")
                        ).area
                        / seg.length
                    )
        rows.append(
            f"{name},{span / 1000:.2f},{sel.sum() * rb.RES**2 / 1e6:.3f},"
            f"{np.median(wid):.0f},{mllw:+.3f},{mhhw:+.3f},"
            f"{area(z0, mllw):.1f},{area(zf, mllw):.1f},{area(zs, mllw):.1f},"
            f"{area(z0, mhhw):.1f},{area(zf, mhhw):.1f},{area(zs, mhhw):.1f},"
            f"{np.isfinite(fl).sum() * rb.RES**2 / 1e6:.3f},"
            f"{np.isfinite(sh).sum() * rb.RES**2 / 1e6:.3f},"
            f"{np.nanmedian(z0):+.2f},{np.nanmedian(zf):+.2f},{np.nanmedian(zs):+.2f},"
            f"{np.nanmedian(zf[ax]):+.2f},{np.nanmedian(zs[ax]):+.2f}"
        )
        print(rows[-1])
    log_dir.mkdir(parents=True, exist_ok=True)
    rb._atomic_bytes(log_dir / "conveyance.csv", ("\n".join(rows) + "\n").encode())
    print(f"wrote {log_dir / 'conveyance.csv'}")


# ── evidence: the cross-section shape of natural tidal channels here ──────────
def _xi_of_points(pt: Part, x, y):
    """(xi, station, inside) of points: distance to bank / local half-width."""
    import shapely

    x0, y1, w, h, T = _grid_for([pt])
    rr, cc, px, py, st, e, B = bank_field(pt, (h, w), T)
    Bst = np.zeros(len(pt.grid))
    k = np.clip((st / 25.0).astype(int), 0, len(pt.grid) - 1)
    np.maximum.at(Bst, k, B)
    pts = shapely.points(x, y)
    inside = shapely.contains_xy(pt.chan, x, y)
    s = shapely.line_locate_point(pt.line, pts)
    d = shapely.distance(pts, pt.chan.boundary)
    kk = np.clip((s / 25.0).astype(int), 0, len(pt.grid) - 1)
    xi = np.where(inside, d / np.maximum(Bst[kk], rb.RES), 0.0)
    return np.clip(xi, 0, 1), s, inside


def _shape_stats(label, xi, s, dep, lo, hi, binw=200.0, min_n=12):
    """Per ``binw`` slice: thalweg = p95 depth; pooled d/d_t by xi decile; fitted P."""
    m = (s >= lo) & (s <= hi) & np.isfinite(dep)
    xi, s, dep = xi[m], s[m], dep[m]
    ratio, xis, thal, means = [], [], [], []
    for b0 in np.arange(lo, hi, binw):
        k = (s >= b0) & (s < b0 + binw)
        if k.sum() < min_n:
            continue
        dt = np.percentile(dep[k], 95)
        if dt < 0.5:
            continue
        r = np.clip(dep[k] / dt, -1, 1.5)
        ratio.append(r)
        xis.append(xi[k])
        thal.append(dt)
        # section mean: average the xi-decile means (xi is uniform across a section)
        dec = [r[(xi[k] >= q) & (xi[k] < q + 0.2)] for q in np.arange(0, 1, 0.2)]
        if all(len(v) for v in dec):
            means.append(np.mean([np.mean(v) for v in dec]))
    if not ratio:
        return None
    r, x = np.concatenate(ratio), np.concatenate(xis)
    edges = np.linspace(0, 1, 11)
    dec = np.array(
        [
            np.median(r[(x >= a) & (x < b)]) if ((x >= a) & (x < b)).sum() else np.nan
            for a, b in zip(edges[:-1], edges[1:])
        ]
    )
    mid = 0.5 * (edges[:-1] + edges[1:])
    ok = np.isfinite(dec)
    ps = np.arange(0.5, 8.01, 0.05)
    sse = [np.sum((g_shape(mid[ok], q) - dec[ok]) ** 2) for q in ps]
    pfit = float(ps[int(np.argmin(sse))])
    return {
        "set": label,
        "n_points": int(len(r)),
        "n_slices": len(thal),
        "thalweg_p50_m": round(float(np.median(thal)), 2),
        "xi_p50_of_points": round(float(np.median(x)), 2),
        "mean_over_thalweg": round(float(np.median(means)), 2) if means else np.nan,
        "P_fit": round(pfit, 2),
        "P_fit_mean_ratio": round(float(np.nanmean(dec[ok])), 2),
        **{f"dec{i}": round(float(v), 2) for i, v in enumerate(dec)},
    }


def evidence(log_dir: Path) -> None:
    import geopandas as gpd

    rows = []

    def utm(lon, lat):
        p = gpd.points_from_xy(lon, lat, crs=4326).to_crs(rb.EPSG)
        return np.asarray(p.x), np.asarray(p.y)

    def from_soundings(label, pt, lon, lat, z, lo, hi):
        x, y = utm(lon, lat)
        near = (
            (x > pt.chan.bounds[0] - 200)
            & (x < pt.chan.bounds[2] + 200)
            & (y > pt.chan.bounds[1] - 200)
            & (y < pt.chan.bounds[3] + 200)
        )
        xi, s, inside = _xi_of_points(pt, x[near], y[near])
        dep = pt.mllw - z[near]
        st = _shape_stats(label, xi[inside], s[inside], dep[inside], lo, hi)
        if st:
            rows.append(st)
            print(st)

    # 1-2. the two new dense surveys (Christina H10042, Big Timber H09886)
    for r, spans in (
        (
            REACHES[0],
            ((1000, 7850, "federal reach"), (7850, 13300, "above the federal reach")),
        ),
        (REACHES[1], ((1850, 9800, "main stem"),)),
    ):
        pt = parts_tidal(r)[0]
        lon, lat, z, _ = _soundings(r)
        for lo, hi, what in spans:
            from_soundings(
                f"{r.name} NOS {r.surveys[0].sid} ({what})", pt, lon, lat, z, lo, hi
            )
    # 3-4. Tuckahoe (1937) and Mullica (1935) NOS, natural tidal rivers
    tuck = next(r for r in gm.REACHES if r.name == "tuckahoe")
    pt = parts_gmrt(tuck)[0]
    lon, lat, z, _ = gm._soundings(tuck)
    from_soundings(
        "tuckahoe NOS H06254+H06218 (1937)", pt, lon, lat, z, 0, pt.line.length
    )
    mul = next(r for r in gm.REACHES if r.name == "mullica")
    pt = parts_gmrt(mul)[0]
    lon, lat, z = [], [], []
    for sid in ("H05893", "H05894"):
        d = nos.read_a93(gm.NOS_DIR / f"{sid}.a93.gz")
        lat.append(d[:, 0])
        lon.append(d[:, 1])
        # MLW 1935 -> NAVD88: Chestnut Neck MLW -0.475, epoch-corrected
        z.append(-0.475 - nos.SLR_M_PER_YR * (nos.EPOCH_MID - 1935) - d[:, 2])
    from_soundings(
        "mullica NOS H05893+H05894 (1935)",
        pt,
        np.concatenate(lon),
        np.concatenate(lat),
        np.concatenate(z),
        0,
        pt.lo + 1000,
    )
    # 5. the Maurice: its own surveyed lower reach in the A+ bed (pixels), and eHydro
    mau = next(r for r in gm.REACHES if r.name == "maurice")
    pt = parts_gmrt(mau)[0]
    x0, y1, w, h, T = _grid_for([pt])
    rr, cc, px, py, st, e, B = bank_field(pt, (h, w), T)
    zz = gm.sample_model_bed(px, py)
    st_ = _shape_stats(
        "maurice A+ merged bed below the GMRT span (pixels)",
        np.clip(e / B, 0, 1),
        st,
        pt.mllw - zz,
        0,
        pt.lo,
        min_n=50,
    )
    if st_:
        rows.append(st_)
        print(st_)
    sp = gpd.read_file(
        SRC / "ehydro" / "MA_01_MRC_20210721_CS" / "MA_01_MRC_20210721_CS.gdb",
        layer="SurveyPoint",
    ).to_crs(rb.EPSG)
    xi, s, inside = _xi_of_points(pt, sp.geometry.x.values, sp.geometry.y.values)
    dep = sp.Z_use.astype(float).values * FT  # + ft below MLLW (CENAP)
    st_ = _shape_stats(
        "maurice eHydro MA_01_MRC 2021 (dredged channel)",
        xi[inside],
        s[inside],
        dep[inside],
        0,
        pt.line.length,
    )
    if st_:
        rows.append(st_)
        print(st_)
    # 6. where across the channel the GMRT reaches' CHART soundings sit
    for r in gm.REACHES:
        if r.points != "enc":
            continue
        pt = parts_gmrt(r)[0]
        lon, lat, z, _ = gm._soundings(r)
        x, y = utm(lon, lat)
        xi, s, inside = _xi_of_points(pt, x, y)
        k = inside & (s >= pt.lo) & (s <= pt.hi)
        if k.any():
            row = {
                "set": f"{r.name} ENC SOUNDG position (painted span)",
                "n_points": int(k.sum()),
                "xi_p50_of_points": round(float(np.median(xi[k])), 2),
                "xi_p25_of_points": round(float(np.percentile(xi[k], 25)), 2),
            }
            rows.append(row)
            print(row)
    import pandas as pd

    log_dir.mkdir(parents=True, exist_ok=True)
    out = log_dir / "section_shape_evidence.csv"
    rb._atomic_bytes(out, pd.DataFrame(rows).to_csv(index=False).encode())
    print(f"wrote {out}")


def usgs_lebanon(log_dir: Path) -> None:
    """USGS 01483740 St Jones at Lebanon (tidal, 2025 ADCP): width / area per visit."""
    import urllib.parse

    url = (
        "https://api.waterdata.usgs.gov/ogcapi/v0/collections/channel-measurements/"
        "items?"
        + urllib.parse.urlencode(
            {"monitoring_location_id": "USGS-01483740", "limit": 1000, "f": "json"}
        )
    )
    with urllib.request.urlopen(url, timeout=180) as f:
        d = json.loads(f.read())
    rows = ["time,width_m,area_m2,mean_depth_m"]
    for p in (x["properties"] for x in d["features"]):
        try:
            w, a = float(p["channel_width"]) * FT, float(p["channel_area"]) * FT**2
        except (TypeError, ValueError):
            continue
        rows.append(f"{p['time']},{w:.1f},{a:.1f},{a / w:.2f}")
    log_dir.mkdir(parents=True, exist_ok=True)
    rb._atomic_bytes(
        log_dir / "usgs_01483740_measurements.csv", ("\n".join(rows) + "\n").encode()
    )
    a = np.array([float(r.split(",")[2]) for r in rows[1:]])
    w = np.array([float(r.split(",")[1]) for r in rows[1:]])
    print(
        f"01483740: n {len(a)}; area p5/p50/p95 {np.percentile(a, [5, 50, 95])}; "
        f"width p5/p50/p95 {np.percentile(w, [5, 50, 95])}"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "stage", choices=["fetch", "evidence", "build", "conveyance", "usgs"]
    )
    ap.add_argument("--section", choices=["flat", "shaped"], default="flat")
    ap.add_argument(
        "--existing",
        action="store_true",
        help="shaped variant of the GMRT reaches and the Cohansey",
    )
    ap.add_argument("--p", type=float, default=P_DEFAULT, help="section exponent P")
    ap.add_argument("--log-dir", type=Path, default=LOG_DIR)
    a = ap.parse_args()
    if a.stage == "fetch":
        fetch()
    elif a.stage == "evidence":
        evidence(a.log_dir)
    elif a.stage == "usgs":
        usgs_lebanon(a.log_dir)
    elif a.stage == "build":
        build(a.section, a.existing, a.p)
    else:
        conveyance(a.log_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
