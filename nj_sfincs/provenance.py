"""What a run was actually made of: data sources, forcing, physics, validation targets.

WHY THIS READS THE RUN DIR, NOT THE CONFIG. `config.py` says what the builder INTENDED;
`sfincs.inp` and the files next to it say what the solver was actually handed. Those two
have diverged before — a forcing swap that did not take, a template staged from the wrong
domain, an engine picked up from a batch-script fallback. So every value here comes off
disk, and anything that cannot be read is reported as missing rather than filled in from
the config.

Use in a notebook:

    from nj_sfincs import provenance
    provenance.manifest(exp_dir)                 # DataFrame, displays as a table
    print(provenance.summary(exp_dir))           # plain text, for a report

Catalog URIs are resolved through `data/data_catalog.yml`, of which there is exactly one.
(This note used to warn about a second copy; the two-catalog situation was an artefact of
the v1/v2 repo split and ended with the 2026-08-05 consolidation.)
"""

from __future__ import annotations

import hashlib
import os
import re
import socket
from datetime import datetime
from pathlib import Path

import pandas as pd

from nj_sfincs.config import DATA
from nj_sfincs.snapwave_params import WINDDIR_FIX_TAG

#: sfincs.inp keys worth surfacing, grouped. Anything not listed is still available via
#: `read_inp`; this is the set that changes answers.
_PHYSICS = [
    ("advection", "advection"),
    ("coriolis", "Coriolis"),
    ("viscosity", "viscosity"),
    ("nuvisc", "viscosity coefficient"),
    ("alpha", "CFL alpha"),
    ("huthresh", "wetting threshold"),
    ("latitude", "domain latitude"),
    ("rhoa", "air density"),
    ("rhow", "water density"),
    ("baro", "atmospheric pressure"),
    ("cdnrb", "wind drag breakpoints"),
    ("cdwnd", "wind drag wind speeds"),
    ("cdval", "wind drag coefficients"),
    ("btfilter", "boundary filter"),
    ("zsini", "initial water level"),
    ("tspinup", "spin-up ramp (s)"),
]
_WAVES = [
    ("snapwave", "SnapWave enabled"),
    ("snapwave_wind", "wind-wave growth"),
    ("snapwave_igwaves", "infragravity"),
    ("snapwave_gamma", "breaking gamma"),
    ("snapwave_alpha", "alpha"),
    ("snapwave_fw", "friction"),
    ("snapwave_niter", "iterations"),
    ("snapwave_dtheta", "directional bin"),
    ("snapwave_sector", "sector"),
    ("dtwave", "wave update (s)"),
    ("snapwave_hmin", "min wave depth (m)"),
    ("storefw", "store wave forces"),
    ("storewavdir", "store wave direction"),
    ("snapwave_bndfile", "support points"),
]
_TIME = [
    ("tref", "reference"),
    ("tstart", "start"),
    ("tstop", "stop"),
    ("dthisout", "his output (s)"),
    ("dtmapout", "map output (s)"),
]

#: forcing file in the run dir -> what it carries and which catalog key produced it
_FORCING = [
    ("sfincs_netbndbzsbzifile.nc", "water-level boundary", "noaa_sandy_nj"),
    ("snapwave.bhs", "wave boundary (Hs)", "cora_waves_nj"),
    ("sfincs_netamuv.nc", "wind field", "era5_nj"),
    ("sfincs_netamp.nc", "pressure field", "era5_nj"),
    ("sfincs_netampr.nc", "precipitation", "aorc_sandy_nj"),
    # ⚠️ DOMAIN-DEPENDENT, unlike every other row here: v1_monmouth uses the 6-point
    # archived file, v1_5_raritan the 8-point one that adds the Raritan and Lawrence
    # Brook. Resolved at call time so provenance names the file that was actually read.
    ("sfincs_netsrcdisfile.nc", "river discharge", None),
]


def _forcing_rows():
    """`_FORCING` with the domain-dependent catalog keys filled in."""
    from . import domain as _domain

    key = _domain.active().discharge_geodataset
    return [(f, d, k if k is not None else key) for f, d, k in _FORCING]


def _validation_rows():
    """`_VALIDATION` with the domain-dependent HWM file filled in."""
    from . import domain as _domain

    rel = _domain.active().hwm_geojson
    hwm = f"{rel.parent.name}/{rel.name}"
    return [(f if f is not None else hwm, d) for f, d in _VALIDATION]


#: validation targets — these are what any score in this project is measured against
_VALIDATION = [
    # domain-dependent, like the discharge row above — filled in by _validation_rows()
    (None, "USGS high-water marks"),
    ("validation/sandy_motf_extent.tif", "FEMA MOTF surge extent"),
    ("gtsm/noaa_sandy_validation.nc", "NOAA gauge water level"),
    ("gtsm/usgs_sandy_tidal_nj.nc", "USGS tidal + interior bay gauges"),
    ("gtsm/sandy_storm_tide_nj.nc", "USGS storm-tide sensors"),
    ("wind/sandy_wind_obs.nc", "observed 10 m wind (NDBC + CO-OPS)"),
]


def read_inp(model_dir: Path | str) -> dict:
    """Parse ``sfincs.inp`` into a dict of stripped strings."""
    p = Path(model_dir) / "sfincs.inp"
    if not p.is_file():
        return {}
    out = {}
    for ln in p.read_text().splitlines():
        if "=" in ln:
            k, _, v = ln.partition("=")
            out[k.strip()] = v.strip()
    return out


def catalog_uri(key: str, data_dir: Path = DATA) -> str:
    """Resolve a catalog key to its uri, or '' if absent."""
    try:
        import yaml

        cat = yaml.safe_load((Path(data_dir) / "data_catalog.yml").read_text()) or {}
    except Exception:  # noqa: BLE001
        return ""
    return str((cat.get(key) or {}).get("uri", ""))


# ── the engine epoch (2026-09-11, plan Phase 1b) ─────────────────────────────────
#
# Every run records WHICH BINARY solved it. Until 2026-09-10 that was implicit (one
# container) and it hid two things: a batch-script fallback that silently ran Galibier
# (v2.4.0) instead of Faber (v2.3.3), and the SnapWave wind-direction bug (FINDINGS §43)
# that every wind-on run on the unpatched engine carries. `engine.txt` in the run dir is
# the record; `engine_label()` infers one from `sfincs.log` for runs that predate it.

_BUILD_REV = re.compile(r"Build-Revision:\s*(.+)")
#: Build-Revision → short label, for runs that predate engine.txt
_KNOWN_REVISIONS = {
    "v2.3.3 mt. Faber": "container:v2.3.3-faber",
    "v2.4.0 Galibier": "container:v2.4.0-galibier",
}


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_revisions(model_dir: Path | str) -> list[str]:
    """The ``Build-Revision`` lines of ``sfincs.log`` — SFINCS's own, then SnapWave's."""
    log = Path(model_dir) / "sfincs.log"
    out: list[str] = []
    if not log.is_file():
        return out
    with open(log, errors="ignore") as fh:
        for i, line in enumerate(fh):
            m = _BUILD_REV.search(line)
            if m:
                out.append(m.group(1).strip())
            if i > 600 or len(out) == 2:
                break
    return out


def engine_record(
    model_dir: Path | str,
    kind: str,
    path: Path | str,
    *,
    host: str | None = None,
    job_id: str | None = None,
    restart_count: str | None = None,
    threads: str | None = None,
) -> dict:
    """What solved this run: ``kind`` is ``sif`` or ``bin``; ``path`` the image/binary."""
    if kind not in ("sif", "bin"):
        raise ValueError(f"kind must be 'sif' or 'bin', not {kind!r}")
    p = Path(path).resolve()
    if not p.is_file():
        raise FileNotFoundError(f"engine not found: {p}")
    st = p.stat()
    sha = _sha256(p)
    name = (
        p.stem
        if kind == "sif"
        else p.parent.parent.name
        if p.parent.name == "bin"
        else p.parent.name
    )
    revs = build_revisions(model_dir)
    rec = {
        "label": f"{kind}:{name}@{sha[:8]}",
        "kind": kind,
        "path": str(p),
        "size": str(st.st_size),
        "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
        "sha256": sha,
        "build_revision": revs[0] if revs else "",
        "snapwave_revision": revs[1] if len(revs) > 1 else "",
        "host": host or socket.gethostname(),
        "job_id": job_id or os.environ.get("SLURM_JOB_ID", ""),
        "restart_count": restart_count or os.environ.get("SLURM_RESTART_COUNT", "0"),
        "threads": threads or os.environ.get("OMP_NUM_THREADS", ""),
        "recorded": datetime.now().isoformat(timespec="seconds"),
    }
    info = p.parent.parent / "BUILD_INFO" if kind == "bin" else None
    if info is not None and info.is_file():
        for ln in info.read_text().splitlines():
            k, _, v = ln.partition(" ")
            if k in ("commit", "branch", "diffstat", "compiler", "flags"):
                rec["build_" + k] = v.strip()
    return rec


def write_engine(model_dir: Path | str, kind: str, path: Path | str, **kw) -> Path:
    """Write ``engine.txt`` and an ``[engine]`` block in ``provenance.txt``. Returns the
    engine.txt path. Idempotent: a second call replaces both."""
    model_dir = Path(model_dir)
    rec = engine_record(model_dir, kind, path, **kw)
    width = max(len(k) for k in rec) + 2
    text = "".join(f"{k:<{width}}{v}\n" for k, v in rec.items())
    out = model_dir / "engine.txt"
    out.write_text(text)
    prov = model_dir / "provenance.txt"
    if prov.is_file():
        body = prov.read_text()
        body = re.sub(r"\n\[engine\]\n(?:  .*\n?)*", "\n", body).rstrip("\n") + "\n"
        body += "\n[engine]\n" + "".join(
            f"  {k:<28} {v}   <- engine.txt\n" for k, v in rec.items()
        )
        prov.write_text(body)
    return out


def read_engine(model_dir: Path | str) -> dict | None:
    f = Path(model_dir) / "engine.txt"
    if not f.is_file():
        return None
    rec = {}
    for ln in f.read_text().splitlines():
        if ln.strip():
            k, _, v = ln.partition(" ")
            rec[k] = v.strip()
    return rec


def engine_label(model_dir: Path | str) -> str:
    """``engine.txt``'s label; else inferred from the log's Build-Revision, marked
    ``(inferred)``; else ``unknown``."""
    rec = read_engine(model_dir)
    if rec and rec.get("label"):
        return rec["label"]
    revs = build_revisions(model_dir)
    if not revs:
        return (
            "unknown (not run)"
            if not (Path(model_dir) / "sfincs_map.nc").exists()
            else "unknown (no Build-Revision in sfincs.log)"
        )
    for key, label in _KNOWN_REVISIONS.items():
        if key in revs[0]:
            return f"{label} (inferred)"
    return f"unknown [{revs[0]}] (inferred)"


def snapwave_direction(model_dir: Path | str) -> str:
    """``off`` (SnapWave off) · ``wind`` (wind on, engine without the fix — the boundary
    waves were launched in the WIND direction, FINDINGS §43) · ``imposed``.
    (Not ``n/a``: pandas reads that back from a CSV as NaN.)"""
    inp = read_inp(model_dir)
    if str(inp.get("snapwave", "0")).strip() != "1":
        return "off"
    if str(inp.get("snapwave_wind", "0")).strip() != "1":
        return "imposed"
    rec = read_engine(model_dir) or {}
    revs = " ".join(
        [rec.get("build_revision", ""), rec.get("build_branch", "")]
        + build_revisions(model_dir)
    )
    return "imposed" if WINDDIR_FIX_TAG in revs else "wind"


def subgrid_sha256(model_dir: Path | str) -> str | None:
    """sha256 of ``sfincs_subgrid.nc`` (1.1 GB on v3), cached in ``.subgrid_sha256`` keyed
    by inode/size/mtime so it is computed once per file, not once per call."""
    f = Path(model_dir) / "sfincs_subgrid.nc"
    if not f.is_file():
        return None
    st = f.stat()
    key = f"{st.st_ino} {st.st_size} {int(st.st_mtime)}"
    cache = Path(model_dir) / ".subgrid_sha256"
    if cache.is_file():
        parts = cache.read_text().split()
        if len(parts) == 4 and " ".join(parts[1:]) == key:
            return parts[0]
    sha = _sha256(f)
    try:
        cache.write_text(f"{sha} {key}\n")
    except OSError:
        pass
    return sha


def subgrid_label(model_dir: Path | str) -> str:
    """Which subgrid table this run solved on: ``template@<sha8>`` when it is the sealed
    template's file, ``_subgrid_<x>@<sha8>`` when it is an alternate table's, else
    ``unmatched@<sha8>``. Matched by inode first (hard-linked inputs), then by sha."""
    model_dir = Path(model_dir)
    f = model_dir / "sfincs_subgrid.nc"
    if not f.is_file():
        return "none"
    sha = subgrid_sha256(model_dir)
    try:
        from nj_sfincs.config import exp_root

        root = exp_root()
    except Exception:  # noqa: BLE001
        return f"unmatched@{sha[:8]}"
    ino = f.stat().st_ino
    cands = [root / "_template_sealed"] + sorted(root.glob("_subgrid_*"))
    for c in cands:
        g = c / "sfincs_subgrid.nc"
        if not g.is_file() or c.resolve() == model_dir.resolve():
            continue
        if g.stat().st_ino == ino or subgrid_sha256(c) == sha:
            name = "template" if c.name == "_template_sealed" else c.name
            return f"{name}@{sha[:8]}"
    return f"unmatched@{sha[:8]}"


def manifest(model_dir: Path | str, data_dir: Path = DATA) -> pd.DataFrame:
    """Everything that defines this run, as a table: category / item / value / source.

    Reads the run directory, so it reports what the solver was ACTUALLY given.
    """
    model_dir = Path(model_dir)
    inp = read_inp(model_dir)
    rows: list[dict] = []

    def add(cat, item, value, src=""):
        rows.append({"category": cat, "item": item, "value": value, "source": src})

    # ── domain identity ──────────────────────────────────────────────────────
    from nj_sfincs import domain as _domain
    from nj_sfincs import premier

    dom = _domain.active()
    add("domain", "name", dom.name, "NJ_DOMAIN")
    add("domain", "region", Path(dom.region).name, "domain registry")
    add("domain", "CRS", f"EPSG:{dom.epsg}", "domain registry")
    try:
        fp = premier.domain_fingerprint(model_dir)
        add("domain", "faces", f"{fp.n_faces:,}", "sfincs.nc")
        add("domain", "boundary edges", f"{fp.n_boundary_edges:,}", "sfincs.nc")
        add("domain", "sha(z,mask)", fp.sha_z_mask, "sfincs.nc")
        label = premier.KNOWN.get(fp, "UNRECOGNISED")
        add("domain", "identity", label, "premier.KNOWN")
        brk = premier.bracket_of(model_dir)
        if brk is not None:
            add(
                "domain",
                "⚠️ BRACKET",
                f"{brk.name} ({brk.bound} bound) — INADMISSIBLE",
                "premier.BRACKETS",
            )
    except Exception as e:  # noqa: BLE001  # never let this kill a report
        add("domain", "fingerprint", f"unavailable ({e})", "")

    # ── time window ──────────────────────────────────────────────────────────
    for k, lbl in _TIME:
        if k in inp:
            add("time", lbl, inp[k], "sfincs.inp")

    # ── elevation stack ──────────────────────────────────────────────────────
    try:
        from nj_sfincs.config import BaseConfig

        # NB `elevation` is a METHOD (returns a fresh mutable copy for the hydromt API),
        # not a property — iterating the bound method silently yields nothing useful.
        for i, tier in enumerate(BaseConfig().elevation()):
            if isinstance(tier, dict):
                # the catalog key lives under 'elevation' (hydromt's own naming)
                name = tier.get("elevation") or tier.get("elevtn") or str(tier)
                extra = {
                    k: v for k, v in tier.items() if k not in ("elevation", "elevtn")
                }
            else:
                name, extra = str(tier), {}
            add(
                "elevation",
                f"tier {i} (top wins)",
                f"{name}" + (f"   {extra}" if extra else ""),
                catalog_uri(str(name), data_dir),
            )
    except Exception as e:  # noqa: BLE001
        add("elevation", "stack", f"unavailable ({e})", "")

    # ── forcing actually present on disk ──────────────────────────────────────
    for fname, what, key in _forcing_rows():
        p = model_dir / fname
        if p.exists():
            add(
                "forcing",
                what,
                f"{fname} ({p.stat().st_size / 1e6:.1f} MB)",
                catalog_uri(key, data_dir) or key,
            )
        else:
            add("forcing", what, "ABSENT", key)
    for k in ("manningfile", "sbgfile", "qtrfile", "scsfile", "crsfile", "obsfile"):
        if k in inp:
            add("forcing", k, inp[k], "sfincs.inp")

    # ── physics + waves ──────────────────────────────────────────────────────
    for k, lbl in _PHYSICS:
        if k in inp:
            add("physics", lbl, inp[k], "sfincs.inp")
    for k, lbl in _WAVES:
        if k in inp:
            add("waves", lbl, inp[k], "sfincs.inp")

    # ── engine + subgrid (the epoch columns) ─────────────────────────────────
    add("engine", "engine", engine_label(model_dir), "engine.txt / sfincs.log")
    add(
        "engine",
        "SnapWave direction",
        snapwave_direction(model_dir),
        "sfincs.inp + Build-Revision (FINDINGS §43)",
    )
    try:
        add("engine", "subgrid", subgrid_label(model_dir), "sfincs_subgrid.nc")
    except Exception as e:  # noqa: BLE001  # never let this kill a report
        add("engine", "subgrid", f"unavailable ({e})", "")

    # ── validation targets ───────────────────────────────────────────────────
    for rel, what in _validation_rows():
        p = Path(data_dir) / rel
        extra = ""
        if p.suffix == ".geojson" and p.exists():
            try:
                import geopandas as gpd

                extra = f" ({len(gpd.read_file(str(p))):,} marks)"
            except Exception:  # noqa: BLE001
                pass
        add(
            "validation",
            what,
            (f"{rel}{extra}" if p.exists() else f"{rel} — MISSING"),
            "data/",
        )

    return pd.DataFrame(rows)


def summary(model_dir: Path | str, data_dir: Path = DATA) -> str:
    """``manifest`` as plain text, grouped by category — for a report or a log."""
    df = manifest(model_dir, data_dir)
    out = [f"RUN PROVENANCE — {Path(model_dir).name}", "=" * 78]
    for cat, grp in df.groupby("category", sort=False):
        out.append(f"\n[{cat}]")
        for _, r in grp.iterrows():
            src = f"   <- {r['source']}" if r["source"] else ""
            out.append(f"  {r['item']:<28} {r['value']}{src}")
    return "\n".join(out)
