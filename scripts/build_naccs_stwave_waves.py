"""NACCS/CHS STWAVE wave parameters at the save points -> a SnapWave point-boundary file.

Same shape as ``build_cora_waves.py`` writes (dims ``(time, node)``, coords lon/lat/depth,
variables ``hs`` / ``tp`` / ``wd``), so an arm plugs it in through
``WaveConfig.wave_point_dataset`` and every wave support point takes its NEAREST node.

Source: the ``*_STWAVE*_Timeseries.csv`` members of ``data/NACCS/*.zip`` (the ADCIRC
members are the water level; `build_naccs_boundary.py` reads those). Sandy = storm
``001`` / ``Tropical_Historical``, 30-min, 2012-10-28 00:00 .. 10-31 24:00 (193 steps).
Columns by CODE: ``Hmo`` zero-moment height [m], ``Tp`` peak period [s], ``alpham`` mean
wave direction [deg]. ⚠️ ``alpham`` is taken as NAUTICAL / "from" (clockwise from north):
on 10-28 00:00 the nearshore points report ~28° with the wind at ~64° — a NE swell ahead
of the storm, which is the "from" reading. Declared in the file attrs; verify against the
CORA arm's directions before trusting a directional result.

⚠️ The three STWAVE grids (02 central NJ, 03 south NJ, 07 NY Bight) OVERLAP and
DISAGREE at shared save points — median max|ΔHs| 2.5–3.7 m, 07 systematically low
(measured 2026-08-26). A shared point takes the grid whose bbox centre it is nearest
to (= most interior to that grid, least affected by its lateral boundaries); the
chosen grid is recorded per node. Nodes shallower than ``--min-depth`` (8 m, the water-
level screen's value) are DROPPED so a −10 m boundary point cannot be forced by a
surf-zone node.

Time: the model window starts before 10-28, so the series is HELD at its first/last
value out to the CORA file's span (10-27 .. 11-01); the padded steps are flagged in
``time_padded`` and are pre-storm swell only.

    NJ_DOMAIN=v3 python scripts/build_naccs_stwave_waves.py
"""
from __future__ import annotations

import csv
import io
import os
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nj_sfincs import domain as _domain  # noqa: E402

NACCS = ROOT / "data" / "NACCS"
STORM_TYPE, STORM_ID = "Tropical_Historical", "001"
CODES = {"Hmo": "hs", "Tp": "tp", "alpham": "wd"}
PAD = (np.datetime64("2012-10-27T00:00"), np.datetime64("2012-11-01T00:00"))


def parse(raw: bytes):
    txt = raw.rstrip(b"\x00").decode("utf-8", "replace")
    rdr = csv.reader(io.StringIO(txt))
    next(rdr)
    codes = next(rdr)
    next(rdr)
    icol = {v: codes.index(k) for k, v in CODES.items()}
    sp = None
    t, rows = [], {v: [] for v in CODES.values()}
    for r in rdr:
        if len(r) <= max(icol.values()):
            continue
        if sp is None:
            sp, lat, lon, depth = int(r[0]), float(r[1]), float(r[2]), float(r[3])
        if r[6] == STORM_TYPE and r[5].strip() == STORM_ID:
            t.append(r[7])
            for v, i in icol.items():
                rows[v].append(float(r[i]))
    if sp is None or not t:
        return None
    return sp, lat, lon, depth, np.array(t), {v: np.array(a) for v, a in rows.items()}


def main() -> int:
    min_depth = float(sys.argv[sys.argv.index("--min-depth") + 1]) if "--min-depth" in sys.argv else 8.0
    dom = _domain.active()
    out = _domain.acquisition_dir("waves", dom) / f"naccs_stwave_{dom.name}.nc"
    grids: dict[str, dict] = {}
    tref = None
    for z in sorted(NACCS.glob("*.zip")):
        zf = zipfile.ZipFile(z)
        members = [m for m in zf.namelist()
                   if m.startswith("CSV/") and "_STWAVE" in m and m.endswith("Timeseries.csv")]
        if not members:
            continue
        print(f"[read] {z.name}: {len(members)} STWAVE timeseries")
        for m in members:
            grid = m.split("_STWAVE")[1].split("_")[0]
            got = parse(zf.read(m))
            if got is None:
                print(f"   !! {m}: no Sandy rows — skipped")
                continue
            sp, lat, lon, depth, t, d = got
            if tref is None:
                tref = t
            elif not np.array_equal(t, tref):
                sys.exit(f"SP{sp}: timestamps differ ({len(t)} vs {len(tref)})")
            g = grids.setdefault(f"STWAVE{grid}", {})
            if sp in g and not np.allclose(g[sp]["hs"], d["hs"]):
                sys.exit(f"SP{sp} appears twice in {grid} with DIFFERENT Hs — refusing")
            g[sp] = dict(lat=lat, lon=lon, depth=depth, grid=f"STWAVE{grid}", **d)
    centre = {g: (np.mean([v["lon"] for v in d.values()]), np.mean([v["lat"] for v in d.values()]))
              for g, d in grids.items()}
    pts, nshared, nshallow = {}, 0, 0
    for g, d in grids.items():
        for sp, v in d.items():
            if v["depth"] < min_depth:
                nshallow += 1
                continue
            if sp in pts:
                nshared += 1
                dk = lambda gg: np.hypot((v["lon"] - centre[gg][0]) * 0.77, v["lat"] - centre[gg][1])  # noqa: E731
                if dk(g) >= dk(pts[sp]["grid"]):
                    continue
            pts[sp] = v
    print(f"[grids] " + "; ".join(f"{g}: {len(d)} pts, centre ({c[0]:.2f},{c[1]:.2f})"
                                  for (g, d), c in zip(grids.items(), centre.values())))
    print(f"[screen] {nshallow} grid-points shallower than {min_depth:.0f} m dropped; "
          f"{nshared} shared ids resolved to the nearest-centre grid")
    from collections import Counter
    print(f"[screen] kept by grid: {dict(Counter(v['grid'] for v in pts.values()))}")
    ids = sorted(pts)
    times = np.array([np.datetime64(datetime.strptime(s, "%Y%m%d%H%M")) for s in tref])
    print(f"[read] {len(ids)} save points kept, {len(times)} steps "
          f"{times[0]} .. {times[-1]}")

    # hold-pad to the CORA span so the model window never extrapolates
    pre = np.arange(PAD[0], times[0], np.timedelta64(30, "m"))
    post = np.arange(times[-1] + np.timedelta64(30, "m"), PAD[1] + np.timedelta64(1, "m"),
                     np.timedelta64(30, "m"))
    tt = np.concatenate([pre, times, post])
    padded = np.r_[np.ones(len(pre), bool), np.zeros(len(times), bool), np.ones(len(post), bool)]

    def stack(v):
        a = np.stack([pts[i][v] for i in ids], axis=1).astype("float32")  # (time, node)
        return np.concatenate([np.repeat(a[:1], len(pre), 0), a, np.repeat(a[-1:], len(post), 0)])

    lon = np.array([pts[i]["lon"] for i in ids])
    lat = np.array([pts[i]["lat"] for i in ids])
    dep = np.array([pts[i]["depth"] for i in ids], dtype="float32")
    hs = stack("hs")
    ds = xr.Dataset(
        {"hs": (("time", "node"), hs, {"units": "m", "long_name": "zero-moment wave height Hmo"}),
         "tp": (("time", "node"), stack("tp"), {"units": "s", "long_name": "peak period"}),
         "wd": (("time", "node"), stack("wd"),
                {"units": "degrees", "long_name": "mean wave direction (nautical, FROM — "
                 "assumed, see attrs)"}),
         "time_padded": (("time",), padded, {"long_name": "1 = held value outside the "
                                                          "STWAVE record"})},
        coords={"time": tt, "lon": ("node", lon), "lat": ("node", lat),
                "depth": ("node", dep, {"units": "m", "long_name": "save point depth"}),
                "sp_id": ("node", np.array(ids)),
                "grid": ("node", np.array([pts[i]["grid"] for i in ids]))},
        attrs={
            "title": "NACCS/CHS STWAVE wave parameters at the save points — SnapWave "
                     "boundary (Hurricane Sandy, storm 001)",
            "source": "USACE CHS NACCS Validations_BaseConditions+1Tide, STWAVE02/03/07 "
                      "members of data/NACCS/*.zip",
            "domain": dom.name,
            "direction_convention": "alpham taken as nautical/'from' (clockwise from N). "
                                    "Inferred from the 10-28 00:00 NE swell vs ENE wind, "
                                    "NOT from documentation — verify.",
            "min_depth_m": min_depth,
            "time_pad": f"held first/last value to {PAD[0]} .. {PAD[1]}; see time_padded",
            "created_by": "scripts/build_naccs_stwave_waves.py",
            "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(out)
    k = np.nanargmax(hs.max(0))
    print(f"[out] depth {dep.min():.1f}..{dep.max():.1f} m (median {np.median(dep):.1f}); "
          f"{int((dep >= 8).sum())} nodes >= 8 m")
    print(f"[out] Hs max {np.nanmax(hs):.2f} m at SP{ids[k]} ({lon[k]:.3f},{lat[k]:.3f}, "
          f"{dep[k]:.1f} m) {tt[np.nanargmax(hs[:, k])]}; NaN {int(np.isnan(hs).sum())}")
    print(f"[out] wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    os.environ.setdefault("NJ_DOMAIN", "v3")
    sys.exit(main())
