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

from pathlib import Path

import pandas as pd

from nj_sfincs.config import DATA, ROOT

#: sfincs.inp keys worth surfacing, grouped. Anything not listed is still available via
#: `read_inp`; this is the set that changes answers.
_PHYSICS = [
    ("advection", "advection"), ("coriolis", "Coriolis"), ("viscosity", "viscosity"),
    ("nuvisc", "viscosity coefficient"), ("alpha", "CFL alpha"),
    ("huthresh", "wetting threshold"), ("latitude", "domain latitude"),
    ("rhoa", "air density"), ("rhow", "water density"), ("baro", "atmospheric pressure"),
    ("cdnrb", "wind drag breakpoints"), ("cdwnd", "wind drag wind speeds"),
    ("cdval", "wind drag coefficients"), ("btfilter", "boundary filter"),
    ("zsini", "initial water level"), ("tspinup", "spin-up ramp (s)"),
]
_WAVES = [
    ("snapwave", "SnapWave enabled"), ("snapwave_wind", "wind-wave growth"),
    ("snapwave_igwaves", "infragravity"), ("snapwave_gamma", "breaking gamma"),
    ("snapwave_alpha", "alpha"), ("snapwave_fw", "friction"),
    ("snapwave_niter", "iterations"), ("snapwave_dtheta", "directional bin"),
    ("snapwave_sector", "sector"), ("dtwave", "wave update (s)"),
]
_TIME = [("tref", "reference"), ("tstart", "start"), ("tstop", "stop"),
         ("dthisout", "his output (s)"), ("dtmapout", "map output (s)")]

#: forcing file in the run dir -> what it carries and which catalog key produced it
_FORCING = [
    ("sfincs_netbndbzsbzifile.nc", "water-level boundary", "noaa_sandy_nj"),
    ("snapwave.bhs", "wave boundary (Hs)", "cora_waves_nj"),
    ("sfincs_netamuv.nc", "wind field", "era5_nj"),
    ("sfincs_netamp.nc", "pressure field", "era5_nj"),
    ("sfincs_netampr.nc", "precipitation", "aorc_sandy_nj"),
    ("sfincs_netsrcdisfile.nc", "river discharge", "usgs_sandy_discharge"),
]

#: validation targets — these are what any score in this project is measured against
_VALIDATION = [
    ("validation/sandy_hwms.geojson", "USGS high-water marks"),
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
    except Exception:
        return ""
    return str((cat.get(key) or {}).get("uri", ""))


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
            add("domain", "⚠️ BRACKET", f"{brk.name} ({brk.bound} bound) — INADMISSIBLE",
                "premier.BRACKETS")
    except Exception as e:                                   # never let this kill a report
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
                extra = {k: v for k, v in tier.items()
                         if k not in ("elevation", "elevtn")}
            else:
                name, extra = str(tier), {}
            add("elevation", f"tier {i} (top wins)",
                f"{name}" + (f"   {extra}" if extra else ""),
                catalog_uri(str(name), data_dir))
    except Exception as e:
        add("elevation", "stack", f"unavailable ({e})", "")

    # ── forcing actually present on disk ──────────────────────────────────────
    for fname, what, key in _FORCING:
        p = model_dir / fname
        if p.exists():
            add("forcing", what, f"{fname} ({p.stat().st_size/1e6:.1f} MB)",
                catalog_uri(key, data_dir) or key)
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

    # ── validation targets ───────────────────────────────────────────────────
    for rel, what in _VALIDATION:
        p = Path(data_dir) / rel
        extra = ""
        if p.suffix == ".geojson" and p.exists():
            try:
                import geopandas as gpd
                extra = f" ({len(gpd.read_file(str(p))):,} marks)"
            except Exception:
                pass
        add("validation", what, (f"{rel}{extra}" if p.exists() else f"{rel} — MISSING"),
            "data/")

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
