"""Another storm on the same domain: the ``Experiment.storm`` override (2026-11-24, Irene on Model 2.0.0).

The template carries SANDY: its window, its forcing files, and the domain's validation sets (gauge files, the
marks, MOTF). A ``storm-*`` arm keeps everything that is the MODEL — mesh, bed, weirs, drainage, curve numbers,
the template's cold start — and replaces everything that is the STORM, on the staged copy:

* the window: ``tref`` = ``tstart`` and ``tstop`` (``sf.config``, so every hydromt writer encodes its time axis
  against the storm's ``tref``);
* the water-level boundary (``water_level.create`` on the template's boundary cells; the arm DECLARES its support
  count, and the storm's points must be the template's or a subset of them);
* the rivers (``discharge_points.create``, snapped as at the template build; the points must be the template's
  inflow points or a subset — the inflow WALLS are the mask, so the fingerprint cannot move). The series is read
  ONE DAY wider than the window on each side: the engine interpolates between the samples that bracket ``t`` and
  indexes ``tsrc(0)`` when ``t`` precedes the first one (sfincs_discharges.f90), and a daily record clipped to a
  window that starts at 21:00 would begin 3 h in;
* rain (``precipitation.create``, as ``model.add_forcing``), wind + pressure (``meteo_from``, through
  ``model.replace_meteo_from``: the corner marker and the active-face coverage are checked there), and the
  SnapWave boundary (``add_waves`` with the storm's point file and the storm's ``tref``).

:func:`verify_staged` runs after every writer and refuses a staged dir whose ``sfincs.inp`` window is not the
storm's, whose forcing files do not cover the window on the storm's clock, or which still carries a forcing file
byte-identical to the template's (= Sandy survived). It appends the storm's own gauges to ``sfincs.obs`` and
completes the ``storm.json`` sidecar, which is how the scorer (``validate.evaluate``) and ``provenance`` know a
run dir is not Sandy. :func:`scoring_domain` is the view the scorer reads instead of the domain's Sandy sets.

🔴 A preempted storm run is RE-RUN CLEAN, not resumed: rain-on (a resume restarts the curve-number soil dry) and
waves-on (a resume starts SnapWave cold) — CLAUDE.md §4/§5.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from . import domain as _domain
from .config import DATA, StormForcing, StormValidation
from .domain import ObsGauge

#: Sidecar written into a staged storm arm. Its presence is what makes a run dir "not Sandy" to the scorer.
SIDECAR = "storm.json"
#: The storm every run without a sidecar is (the template's).
TEMPLATE_STORM = "sandy2012"
#: Forcing files a storm REPLACES (whichever the arm carries). None may be byte-identical to the template's.
NC_FORCING = (
    "sfincs_netbndbzsbzifile.nc",
    "sfincs_netsrcdisfile.nc",
    "sfincs_netamuv.nc",
    "sfincs_netamp.nc",
    "sfincs_netampr.nc",
)
WAVE_FORCING = ("snapwave.bhs", "snapwave.btp", "snapwave.bwd", "snapwave.bds")
#: How much wider than the window the river series is read (see the module docstring).
DISCHARGE_PAD = timedelta(days=1)
#: A storm point (boundary support point, inflow) is the template's when within this distance of one (m).
POINT_TOL_M = 1.0
_FMT = "%Y%m%d %H%M%S"


def _t(s: str) -> datetime:
    return datetime.strptime(" ".join(str(s).split()), _FMT)


def window(st: StormForcing) -> tuple[datetime, datetime]:
    """``(tstart, tstop)``; ``tref`` = ``tstart``."""
    t0, t1 = _t(st.tstart), _t(st.tstop)
    if not t1 > t0:
        raise ValueError(f"storm {st.name}: tstop {t1} is not after tstart {t0}")
    return t0, t1


def conflicts(exp) -> list[str]:
    """Fields an arm with ``storm`` must leave at their defaults (each would mix two storms or two windows)."""
    out = []
    for f, ok in (
        ("calm", exp.calm is None),
        ("cold_start", exp.cold_start is None),
        ("meteo_from", exp.meteo_from is None),
        ("waterlevel_geodataset", exp.waterlevel_geodataset is None),
        ("sea_level_offset_m", exp.sea_level_offset_m is None),
        ("extra_discharge", exp.extra_discharge is None),
        ("boundary_arm_offsets", not exp.boundary_arm_offsets),
        ("boundary_point_offsets", exp.boundary_point_offsets is None),
        ("wind_scale", exp.wind_scale == 1.0),
    ):
        if not ok:
            out.append(f)
    st = exp.storm
    if st is not None:
        if exp.rain and st.precip_dataset is None:
            out.append(
                f"rain (storm {st.name} has no precip_dataset: make the arm rain=False)"
            )
        if exp.waves.use_waves and st.wave_point_dataset is None:
            out.append(
                f"waves (storm {st.name} has no wave_point_dataset: make the arm waves-off)"
            )
        if exp.waves.use_waves and exp.waves.wave_grid_dataset is not None:
            out.append(
                "waves.wave_grid_dataset (a storm forces SnapWave from its wave_point_dataset)"
            )
    return out


def check_inputs(exp, data_dir: Path = DATA) -> list[str]:
    """READ-ONLY (``run_experiments.py --check``): what staging ``exp`` would refuse, or [] when it would go.

    The arm's field conflicts, every input file present (catalog keys resolved through ``data_catalog.yml``),
    the meteo pair, the wave file, and every validation file the storm scores.
    """
    from .provenance import catalog_uri

    st = exp.storm
    out = [f"also sets {f}" for f in conflicts(exp)]
    try:
        window(st)
    except ValueError as e:
        out.append(str(e))
    keys = [st.waterlevel_geodataset, st.discharge_geodataset] + (
        [st.precip_dataset] if exp.rain else []
    )
    keys += [st.support_reference] if st.support_reference else []
    for k in keys:
        uri = catalog_uri(k, data_dir)
        if not uri:
            out.append(
                f"catalog key {k!r} not in {Path(data_dir) / 'data_catalog.yml'}"
            )
        elif not (Path(data_dir) / uri).is_file():
            out.append(f"{k}: {Path(data_dir) / uri} missing")
    for f in ("sfincs_netamuv.nc", "sfincs_netamp.nc"):
        if not (Path(st.meteo_from) / f).is_file():
            out.append(f"meteo_from: {Path(st.meteo_from) / f} missing")
    if (
        exp.waves.use_waves
        and st.wave_point_dataset is not None
        and not Path(st.wave_point_dataset).is_file()
    ):
        out.append(f"wave_point_dataset {st.wave_point_dataset} missing")
    val = st.validation
    for f in sorted(
        {b for _, b in val.obs_files}
        | {g.obs_file for g in val.extra_gauges if g.obs_file}
    ):
        if not (Path(data_dir) / f).is_file():
            out.append(f"validation file {Path(data_dir) / f} missing")
    if val.hwm_geojson is not None and not Path(val.hwm_geojson).is_file():
        out.append(f"hwm_geojson {val.hwm_geojson} missing")
    if exp.n_waterlevel_support is None:
        out.append(
            "the arm declares no n_waterlevel_support (a storm's support count is the arm's to declare)"
        )
    return out


def storm_base(base, st: StormForcing):
    """``base`` on the storm's window (the clock ``add_waves`` writes the SnapWave series against)."""
    t0, t1 = window(st)
    return replace(base, tref=t0, tstart=t0, tstop=t1)


def storm_waves(wcfg, st: StormForcing):
    """The arm's WaveConfig with the storm's point file (waves-off: unchanged)."""
    if not wcfg.use_waves:
        return wcfg
    return replace(
        wcfg, wave_point_dataset=Path(st.wave_point_dataset), wave_grid_dataset=None
    )


def _points_xy(ds) -> np.ndarray:
    """``(n, 2)`` model-CRS x/y of a hydromt GeoDataset's points (``vector`` geometry, else x/y coords)."""
    if ds is None:
        return np.zeros((0, 2))
    try:
        g = ds.vector.to_gdf()
        return np.c_[g.geometry.x.values, g.geometry.y.values]
    except Exception:  # noqa: BLE001
        return np.c_[np.atleast_1d(ds["x"].values), np.atleast_1d(ds["y"].values)]


def _catalog_points_xy(sf, key: str) -> np.ndarray:
    """Model-CRS x/y of every point of catalog GeoDataset ``key`` (no clip in space or time)."""
    ds = sf.data_catalog.get_geodataset(key)
    g = ds.vector.to_gdf().to_crs(sf.crs)
    return np.c_[g.geometry.x.values, g.geometry.y.values]


def unmatched(new: np.ndarray, old: np.ndarray, tol: float = POINT_TOL_M) -> np.ndarray:
    """Indices of ``new`` points farther than ``tol`` from every ``old`` point."""
    new, old = (
        np.asarray(new, float).reshape(-1, 2),
        np.asarray(old, float).reshape(-1, 2),
    )
    if not len(new):
        return np.zeros(0, int)
    if not len(old):
        return np.arange(len(new))
    d = np.hypot(
        new[:, None, 0] - old[None, :, 0], new[:, None, 1] - old[None, :, 1]
    ).min(axis=1)
    return np.flatnonzero(d > tol)


def _md5(p: Path) -> str:
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def _source(key_or_path, data_dir: Path = DATA) -> dict:
    """A forcing source as recorded in the sidecar: catalog key (+ uri) or path, and the file's md5."""
    from .provenance import catalog_uri

    if isinstance(key_or_path, Path) or "/" in str(key_or_path):
        p = Path(key_or_path)
        rec = {"path": str(p)}
    else:
        uri = catalog_uri(str(key_or_path), data_dir)
        p = Path(data_dir) / uri if uri else None
        rec = {"catalog": str(key_or_path), "uri": uri}
    if p is not None and p.is_file():
        rec["md5"] = _md5(p)
    elif p is not None and p.is_dir():
        rec["md5"] = {f.name: _md5(f) for f in sorted(p.glob("sfincs_net*.nc"))}
    return rec


def read_sidecar(model_dir: Path | str) -> dict | None:
    p = Path(model_dir) / SIDECAR
    if not p.is_file():
        return None
    return json.loads(p.read_text())


def _write_sidecar(model_dir: Path | str, rec: dict) -> None:
    p = Path(model_dir) / SIDECAR
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(rec, indent=1, default=str) + "\n")
    tmp.replace(p)


# ── staging ──────────────────────────────────────────────────────────────────────────────────────────────────


def apply_in_memory(sf, base, exp, model_dir: Path | str) -> dict:
    """Window + boundary + rivers + rain of ``exp.storm`` onto the read-back template model ``sf``, in memory.

    Called by ``prepare_experiment`` before ``add_waves`` / ``finalize`` (which write it). Writes the first
    ``storm.json`` so the provenance manifest ``finalize`` writes already names the storm. Returns the record.
    """
    from . import model as _model

    st = exp.storm
    bad = conflicts(exp)
    if bad:
        raise SystemExit(f"[{exp.name}] storm {st.name}: also sets {bad} — refusing")
    t0, t1 = window(st)
    # the template's points, read back BEFORE the clock moves
    old_bnd = _points_xy(sf.water_level.data)
    old_src = _points_xy(sf.discharge_points.data)
    sf.config.update({"tref": t0, "tstart": t0, "tstop": t1})
    print(
        f"[storm] {st.name}: window {t0:%Y-%m-%d %H:%M} -> {t1:%Y-%m-%d %H:%M} (tref = tstart)",
        flush=True,
    )

    # water level: the template's boundary cells, the storm's series; the arm declares the count
    sf.water_level.create(
        geodataset=st.waterlevel_geodataset, buffer=base.waterlevel_buffer, merge=False
    )
    n_bnd = _model.check_waterlevel_support(sf, expect=exp.n_waterlevel_support)
    new_bnd = _points_xy(sf.water_level.data)
    ref_bnd, ref_name = old_bnd, "the template's boundary"
    if st.support_reference is not None:
        ref_bnd, ref_name = (
            _catalog_points_xy(sf, st.support_reference),
            st.support_reference,
        )
    off = unmatched(new_bnd, ref_bnd)
    if off.size:
        raise SystemExit(
            f"[storm] {st.name}: {off.size} of {len(new_bnd)} boundary support points are not points of "
            f"{ref_name} (> {POINT_TOL_M} m from all {len(ref_bnd)}): {new_bnd[off][:5].round(1).tolist()} — "
            "a storm forces the reference boundary's points (or a subset), never new ones"
        )

    # rivers: one day of pad each side (module docstring), then the template build's snap
    sf.config.update({"tstart": t0 - DISCHARGE_PAD, "tstop": t1 + DISCHARGE_PAD})
    try:
        sf.discharge_points.create(geodataset=st.discharge_geodataset, merge=False)
    finally:
        sf.config.update({"tstart": t0, "tstop": t1})
    _model._snap_sources_to_active_faces(sf)
    new_src = _points_xy(sf.discharge_points.data)
    off = unmatched(new_src, old_src)
    if off.size:
        raise SystemExit(
            f"[storm] {st.name}: {off.size} of {len(new_src)} inflows are not template inflow points: "
            f"{new_src[off][:5].round(1).tolist()} — the inflow walls are the mask; a new river is a domain question"
        )
    print(
        f"[storm] {st.name}: {n_bnd} boundary support points (template {len(old_bnd)}), "
        f"{len(new_src)} inflows (template {len(old_src)})",
        flush=True,
    )

    if exp.rain:
        # 🔴 CLEAR FIRST: hydromt's meteo ``set`` MERGES a new field into the read-back one (``self._data[v] =
        # ...``), so the template's Sandy time axis would REINDEX Irene's rain (all NaN) and its corner-marker
        # attributes would survive onto unshifted data (meteo_grid refuses that; the 2026-11-24 test staging).
        sf.precipitation.clear()
        sf.precipitation.create(
            precip=st.precip_dataset, cumulative_input=True, aggregate=False
        )
        print(f"[storm] {st.name}: rain from {st.precip_dataset}", flush=True)

    rec = {
        "storm": st.name,
        "arm": exp.name,
        "tref": t0.strftime(_FMT),
        "tstart": t0.strftime(_FMT),
        "tstop": t1.strftime(_FMT),
        "run_hours": (t1 - t0).total_seconds() / 3600.0,
        "n_waterlevel_support": n_bnd,
        "n_waterlevel_support_template": len(old_bnd),
        "support_reference": st.support_reference or "template",
        "n_support_reference": len(ref_bnd),
        "n_inflows": len(new_src),
        "n_inflows_template": len(old_src),
        "discharge_pad_h": DISCHARGE_PAD.total_seconds() / 3600.0,
        "sources": {
            "waterlevel": _source(st.waterlevel_geodataset),
            "discharge": _source(st.discharge_geodataset),
            "meteo": _source(Path(st.meteo_from)),
            "precip": _source(st.precip_dataset)
            if exp.rain
            else "off (arm rain=False)",
            "waves": (
                _source(Path(st.wave_point_dataset))
                if exp.waves.use_waves
                else "off (arm waves-off)"
            ),
        },
        "note": st.note,
    }
    _write_sidecar(model_dir, rec)
    return rec


def _abs_times(path: Path) -> tuple[datetime, datetime]:
    """First / last instant of a netCDF forcing file's time axis (CF units, read raw)."""
    import netCDF4

    with netCDF4.Dataset(path) as nc:
        t = nc["time"]
        v = np.asarray(t[:], float).ravel()
        d = netCDF4.num2date(
            [v.min(), v.max()], t.units, only_use_cftime_datetimes=False
        )
    return (
        datetime(*d[0].timetuple()[:6]),
        datetime(*d[1].timetuple()[:6]),
    )


#: Forcing files whose every value must be finite (point series); the gridded rain need only carry some rain.
_ALL_FINITE = ("sfincs_netbndbzsbzifile.nc", "sfincs_netsrcdisfile.nc")


def _bad_values(path: Path, name: str) -> str:
    """'' or what is wrong with a forcing file's VALUES (a field reindexed onto another storm's clock is NaN)."""
    import netCDF4

    if name not in _ALL_FINITE and name != "sfincs_netampr.nc":
        return ""
    with netCDF4.Dataset(path) as nc:
        var = [
            v
            for v in nc.variables.values()
            if "time" in v.dimensions and v.name != "time"
        ]
        if not var:
            return "no time-varying variable"
        vname = var[0].name
        a = np.ma.filled(np.ma.asarray(var[0][:], dtype="f8"), np.nan)
    if name in _ALL_FINITE and not np.isfinite(a).all():
        return f"{int((~np.isfinite(a)).sum())} non-finite values in {vname}"
    if name == "sfincs_netampr.nc" and not (np.isfinite(a) & (a > 0)).any():
        return f"no rain anywhere in {vname} (all NaN or zero)"
    return ""


def _ascii_times(path: Path) -> tuple[float, float]:
    """First / last time (s since tref) of a SnapWave ASCII series (first column)."""
    a = np.loadtxt(path, ndmin=2)
    return float(a[0, 0]), float(a[-1, 0])


def append_obs(model_dir: Path | str, gauges, epsg: int) -> list[str]:
    """Append ``gauges`` to the staged ``sfincs.obs`` (``x y "name"``, the template's format), as a new inode.

    Refuses a name already there or one that is a substring of / contains another (his metrics match by
    substring, ``validate.his_series``).
    """
    from pyproj import Transformer

    from . import model as _model

    obs = Path(model_dir) / "sfincs.obs"
    text = obs.read_text() if obs.is_file() else ""
    have = [ln.split('"')[1] for ln in text.splitlines() if ln.count('"') >= 2]
    new = [g.name for g in gauges]
    allnames = have + new
    for n in new:
        clash = [m for m in allnames if m != n and (n in m or m in n)]
        if clash or allnames.count(n) > 1:
            raise SystemExit(
                f"[storm] obs point {n!r} clashes with {clash or [n]} (his names match by substring)"
            )
    if not gauges:
        return []
    _model.break_hardlinks(Path(model_dir), names=("sfincs.obs",))
    tf = Transformer.from_crs(4326, epsg, always_xy=True)
    lines = []
    for g in gauges:
        x, y = tf.transform(g.lon, g.lat)
        lines.append(f'{x:11.1f} {y:11.1f} "{g.name}"')
    body = (
        text
        + ("" if text.endswith("\n") or not text else "\n")
        + "\n".join(lines)
        + "\n"
    )
    tmp = obs.with_name(obs.name + ".storm")
    tmp.write_text(body)
    tmp.replace(obs)
    return new


def verify_staged(
    model_dir: Path | str, st: StormForcing, template_dir: Path | str | None = None
) -> dict:
    """After every writer: refuse a staged storm arm that is not entirely the storm; add its gauges; seal the sidecar.

    Refuses (``SystemExit``): an inp window that is not the storm's; a ``rstfile``; ``dtmaxout`` not dividing the
    restart cadence; a netCDF forcing file whose time axis does not cover ``[tstart, tstop]``; a SnapWave series not
    covering ``[0, tstop - tref]`` s; a forcing file byte-identical to ``template_dir``'s copy (Sandy survived).
    """
    from . import model as _model

    d = Path(model_dir)
    rec = read_sidecar(d)
    if rec is None or rec.get("storm") != st.name:
        raise SystemExit(
            f"[storm] {d}: no {SIDECAR} for {st.name} — apply_in_memory did not run on this dir"
        )
    t0, t1 = window(st)
    keys = _model._inp_keys(d / "sfincs.inp")
    problems = []
    for k, want in (("tref", t0), ("tstart", t0), ("tstop", t1)):
        if k not in keys or _t(keys[k]) != want:
            problems.append(
                f"sfincs.inp {k} = {keys.get(k)!r}, not {want:%Y%m%d %H%M%S}"
            )
    if "rstfile" in keys:
        problems.append(f"sfincs.inp resumes from {keys['rstfile']}")
    dtmax = float(keys.get("dtmaxout", 0) or 0)
    if dtmax <= 0 or _model.RESTART_DT_S % dtmax:
        problems.append(
            f"dtmaxout {dtmax} does not divide the restart cadence {_model.RESTART_DT_S}"
        )

    files = {}
    for name in NC_FORCING:
        p = d / name
        if not p.is_file():
            continue
        a, b = _abs_times(p)
        files[name] = {"first": a.isoformat(" "), "last": b.isoformat(" ")}
        if a > t0 or b < t1:
            problems.append(f"{name} covers {a} .. {b}, not the window {t0} .. {t1}")
        bad = _bad_values(p, name)
        if bad:
            problems.append(f"{name}: {bad}")
    span = (t1 - t0).total_seconds()
    for name in WAVE_FORCING:
        p = d / name
        if not p.is_file():
            continue
        a, b = _ascii_times(p)
        files[name] = {"first_s": a, "last_s": b}
        if a > 0.0 or b < span:
            problems.append(
                f"{name} covers {a:.0f} .. {b:.0f} s since tref, not 0 .. {span:.0f}"
            )
    need = [
        "sfincs_netbndbzsbzifile.nc",
        "sfincs_netsrcdisfile.nc",
        "sfincs_netamuv.nc",
        "sfincs_netamp.nc",
    ]
    if "netamprfile" in keys:
        need.append("sfincs_netampr.nc")
    if keys.get("snapwave", "0").strip() == "1":
        need += list(WAVE_FORCING)
    for name in need:
        if name not in files:
            problems.append(f"{name} is missing from the staged dir")

    if template_dir is not None:
        tdir = Path(template_dir)
        for name in NC_FORCING + WAVE_FORCING:
            if (d / name).is_file() and (tdir / name).is_file():
                m = _md5(d / name)
                files.setdefault(name, {})["md5"] = m
                if m == _md5(tdir / name):
                    problems.append(
                        f"{name} is byte-identical to the template's: the template storm survived staging"
                    )
    if problems:
        raise SystemExit(
            f"[storm] {d.name}: staged dir is not {st.name}:\n  "
            + "\n  ".join(problems)
        )

    dom = _domain.active()
    added = append_obs(d, st.validation.extra_gauges, dom.epsg)
    rec.update({"verified": files, "obs_added": added})
    _write_sidecar(d, rec)
    line = (
        f"storm = {st.name}: tref = tstart {rec['tstart']}, tstop {rec['tstop']} ({rec['run_hours']:.0f} h); "
        f"boundary {rec['sources']['waterlevel'].get('catalog')} ({rec['n_waterlevel_support']} pts), rivers "
        f"{rec['sources']['discharge'].get('catalog')} ({rec['n_inflows']}), meteo {rec['sources']['meteo']['path']}, "
        f"{len(added)} storm obs points added; storm.json"
    )
    prov = d / "provenance.txt"
    text = prov.read_text() if prov.exists() else ""
    prov.unlink(missing_ok=True)
    prov.write_text(
        text + ("" if text.endswith("\n") or not text else "\n") + line + "\n"
    )
    print(f"[storm] verified: {line}", flush=True)
    return rec


# ── scoring ──────────────────────────────────────────────────────────────────────────────────────────────────


def storm_of(model_dir: Path | str) -> StormForcing | None:
    """The storm a run dir was staged with (its ``storm.json``), or None (the template's storm, Sandy)."""
    rec = read_sidecar(model_dir)
    if rec is None:
        return None
    name = rec.get("storm")
    if name not in STORMS:
        raise KeyError(
            f"{model_dir}: {SIDECAR} names storm {name!r}, not in storm.STORMS {sorted(STORMS)}"
        )
    return STORMS[name]


def storm_gauges(gauges, val: StormValidation) -> tuple[ObsGauge, ...]:
    """The domain's gauges re-pointed at the storm's records (Sandy record facts cleared) + the storm's own."""
    remap = dict(val.obs_files)
    out = [
        replace(
            g,
            obs_file=remap.get(g.obs_file) if g.obs_file else None,
            record_ends=None,
            obs_offset_m=0.0,
            published_peak=None,
            survives_crest=False,
        )
        for g in gauges
    ]
    return tuple(out) + tuple(val.extra_gauges)


def scoring_domain(st: StormForcing, dom=None):
    """The active domain as the scorer must see a ``st`` run: the storm's gauges and marks, its geometry intact.

    Use with ``domain.scoring_view``. ``hwm_geojson`` stays the domain's when the storm has none (the scorer
    skips HWMs then; see ``validate.metrics.evaluate``).
    """
    dom = dom or _domain.active()
    val = st.validation
    return replace(
        dom,
        obs_gauges=storm_gauges(dom.obs_gauges, val),
        hwm_geojson=Path(val.hwm_geojson)
        if val.hwm_geojson is not None
        else dom.hwm_geojson,
    )


def peak_floor(st: StormForcing) -> np.datetime64:
    return np.datetime64(st.validation.peak_floor.replace(" ", "T"))


def label(model_dir: Path | str) -> str:
    """``metrics.csv`` ``storm`` column: the sidecar's storm; ``calm`` for a calm arm (``calm.apply``: no weather,
    its own window); else the template's. Never raises."""
    try:
        rec = read_sidecar(model_dir)
        if rec is not None:
            return str(rec.get("storm"))
        meta = (
            Path(model_dir) / "sfincs_ini_sealevel.json"
        )  # sea_level.INI_META (calm + slr arms)
        if meta.is_file() and "boundary_source" in json.loads(meta.read_text()):
            return "calm"
    except Exception as e:  # noqa: BLE001
        return f"unreadable ({e})"
    return TEMPLATE_STORM


# ── the storms ───────────────────────────────────────────────────────────────────────────────────────────────
# Inputs and their checks: logs/irene_prep_2026-11-24/README.md; plan: logs/naccs_storms_2026-11-22/README.md §6.

_IRENE = DATA / "irene_2011"
_IRENE_VAL = "irene_2011/validation"
_IRENE_STN = f"{_IRENE_VAL}/irene_storm_tide_nj2.nc"
_IRENE_NOAA = f"{_IRENE_VAL}/noaa_irene_validation_6min.nc"


def _stn(inst: int, label: str, lon: float, lat: float) -> ObsGauge:
    return ObsGauge(
        f"irene_stn_{inst}_{label}",
        lon,
        lat,
        "surge",
        _IRENE_STN,
        "stormtide_m",
        inst,
        note="USGS STN storm-tide sensor, Irene 2011 (instrument id; stormtide_m = the prep's 30-min centred mean "
        "of floor-masked readings, logs/irene_prep_2026-11-24/validation/build_irene_storm_tide.py)",
    )


#: Irene's 15 STN sensors (instrument id, file label, lon, lat from irene_storm_tide_nj2.nc) + Tacony-Palmyra.
_IRENE_EXTRA = (
    _stn(1994, "rdg_392114075325901", -75.549722, 39.354),
    _stn(2002, "de_new_005", -75.58025, 39.504944),
    _stn(2004, "de_new_006", -75.602056, 39.577083),
    _stn(2005, "de_new_008", -75.587556, 39.651972),
    _stn(1981, "de_sus_008", -75.163639, 38.790222),
    _stn(1979, "de_sus_009", -75.13825, 38.775639),
    _stn(2003, "nj_atl_001", -74.462778, 39.553333),
    _stn(2000, "nj_atl_002", -74.726944, 39.448611),
    _stn(1992, "nj_cpm_001", -74.6275, 39.288333),
    _stn(1999, "nj_cum_002", -75.236944, 39.429167),
    _stn(2009, "nj_ocn_001", -74.198889, 39.950278),
    _stn(2012, "ny_kin_001", -74.011612, 40.579998),
    _stn(2025, "ny_kin_002", -73.988317, 40.704581),
    _stn(2014, "ny_ric_001", -74.059845, 40.593884),
    _stn(2010, "ny_ric_003", -74.230339, 40.501881),
    ObsGauge(
        "noaa_tacony_palmyra",
        -75.043,
        40.0119,
        "surge",
        _IRENE_NOAA,
        "waterlevel",
        8538886,
        note="CO-OPS 8538886 (Irene only: not in the domain's gauge set). NAVD88 = MLLW - 0.984 m, an ESTIMATE by "
        "the neighbour rule; an 18-sample gap 2011-08-28 05:18-07:00 probably misses the crest.",
    ),
)

IRENE_2011 = StormForcing(
    name="irene2011",
    tstart="20110825 210000",
    tstop="20110829 120000",
    waterlevel_geodataset="naccs_irene_nj2",
    # the 2.0 premier's boundary (244 points); the template itself carries the 3-gauge noaa_sandy_nj
    support_reference="naccs_sandy_nj2",
    # the PREMIER's recipe: NACCS-ERA5 blend wind + ERA5 pressure (the 2.0 premier's meteo_from is
    # data/wind_v4/naccs_blend_p_era5; irene_naccs_blend/ is the blend-pressure twin)
    meteo_from=_IRENE / "meteo_blend" / "irene_naccs_blend_p_era5",
    discharge_geodataset="usgs_irene_discharge_nj2",
    precip_dataset="aorc_irene_nj2",
    wave_point_dataset=_IRENE / "waves" / "cora_waves_irene_v4.nc",
    validation=StormValidation(
        # the boundary's first peak is 08-27 22:45 (south end), the NY peak 08-28 12:40; 27 h after the cold start
        peak_floor="2011-08-27 00:00",
        obs_files=(
            ("gtsm/noaa_sandy_validation_6min.nc", _IRENE_NOAA),
            ("nj2_design/obs_nj2_bergen_point_6min.nc", _IRENE_NOAA),
            ("gtsm/usgs_sandy_tidal_nj.nc", f"{_IRENE_VAL}/usgs_irene_tidal_nj2.nc"),
            ("gtsm/usgs_sandy_tidal_v3.nc", f"{_IRENE_VAL}/usgs_irene_tidal_nj2.nc"),
            ("gtsm/usgs_sandy_tidal_v4.nc", f"{_IRENE_VAL}/usgs_irene_tidal_nj2.nc"),
        ),
        extra_gauges=_IRENE_EXTRA,
        hwm_geojson=_IRENE / "validation" / "irene_hwms_nj2.geojson",
        extent=False,
    ),
    note="Hurricane Irene, Aug 2011: NACCS Val TH 002 (240 of the 244 nj2 support points, sha 98312c46abe92dce), "
    "NACCS-ERA5 blend wind + ERA5 pressure, CORA v1.1.1 waves, AORC v1.1 rain, USGS daily rivers (58 of 61). "
    "logs/irene_prep_2026-11-24/README.md",
)

#: name -> storm. A run dir's ``storm.json`` names one of these.
STORMS: dict[str, StormForcing] = {s.name: s for s in (IRENE_2011,)}
