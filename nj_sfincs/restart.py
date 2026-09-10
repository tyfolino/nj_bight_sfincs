"""Resume a preempted SFINCS solve from its newest restart file and stitch the pieces.

WHY THIS EXISTS (2026-09-10)
----------------------------
Amarel's ``main`` partition preempts. On 2026-09-10 two 40 h SnapWave solves were thrown
off their nodes in the same second, 21 h and 19 h in, and ``--requeue`` restarted both
FROM SCRATCH: SFINCS had no restart file to start from (``trstout`` off), so a day of
compute was repeated and the results slipped a day. This module makes a requeue resume
instead.

HOW SFINCS RESTARTS (source read, v2.3.3 ``sfincs_lib.f90`` / ``sfincs_output.f90``)
-------------------------------------------------------------------------------------
* ``dtrstout = <s>`` writes ``sfincs.YYYYMMDD.HHMMSS.rst`` every ``<s>`` seconds from
  ``tstart`` (verified on the hydromt example model: 6 h cadence gives eight files for a
  48 h run, the last one AT ``tstop``).
* The file holds ``zs``, ``q`` and ``uvmean`` — the hydrodynamic state — and NO clock.
  Resuming therefore means rewriting ``sfincs.inp``: ``tstart`` = the stamp,
  ``rstfile`` = the file. SnapWave is stationary (recomputed from the boundary at every
  call), so it carries no state.
* ``tspinup`` ramps the BOUNDARY water level from ``zsini`` to its forced value over the
  first ``tspinup`` seconds after ``tstart``. Left alone, a resumed run would re-ramp the
  ocean from zero for an hour in the middle of the storm — so the resume sets it to 0.
* SFINCS creates ``sfincs_map.nc`` / ``sfincs_his.nc`` fresh at start, so the earlier
  segment's output must be moved aside before the solver runs, and stitched back after.

STITCHING RULES
---------------
Segments are the retired outputs, in the order they were made, plus the final run dir.
Each segment owns the records from its own ``tstart`` up to (not including) the next
segment's ``tstart``; the last one owns everything from its start on. ``zsmax`` blocks
carry the time at which they END (``timemax``), and a segment owns the blocks with
``start < timemax <= next_start`` — the block ending exactly at the resume instant was
completed by the earlier segment; the resumed one starts its first block there. Blocks
that were never written (netCDF float fill, or beyond ``tstop``) are dropped.

🔴 ``dtmaxout`` MUST DIVIDE ``dtrstout`` (both 21600 s in ``model.add_forcing``), or a
resume point falls inside a max-water-level block and the part of that block before the
resume is lost — the HWM and extent metrics are computed from ``zsmax``. The plan step
refuses a resume whose stamp is not on the ``dtmaxout`` lattice for exactly that reason.

⚠️ A second preemption may leave restart files from an OLDER trajectory with stamps
beyond the newest segment's end (the older run got further before it died). Resuming
from one of those would leave a hole in the stitched record, so a candidate must lie
within the segment being retired: ``stamp <= last map time``.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import netCDF4
import numpy as np

INP_FMT = "%Y%m%d %H%M%S"
RST_RE = re.compile(r"^sfincs\.(\d{8})\.(\d{6})\.rst$")
SEG_DIR = "restart_segments"
ORIG_INP = "sfincs.inp.orig"
HISTORY = "restart_history.txt"
OUTPUTS = ("sfincs_map.nc", "sfincs_his.nc", "sfincs.log")
NC_FLOAT_FILL = (
    9.96e36  # netCDF default float fill; an unwritten zsmax block reads this
)

# ── sfincs.inp text helpers ──────────────────────────────────────────────────


def inp_get(text: str, key: str) -> str | None:
    for line in text.splitlines():
        if "=" in line and line.split("=", 1)[0].strip() == key:
            return line.split("=", 1)[1].strip()
    return None


def inp_set(text: str, values: dict[str, str]) -> str:
    """Replace or append ``key = value`` lines, keeping SFINCS' 20-column layout."""
    lines = text.splitlines()
    done = set()
    for i, line in enumerate(lines):
        if "=" not in line:
            continue
        k = line.split("=", 1)[0].strip()
        if k in values:
            lines[i] = f"{k:<20} = {values[k]}"
            done.add(k)
    for k, v in values.items():
        if k not in done:
            lines.append(f"{k:<20} = {v}")
    return "\n".join(lines) + "\n"


def inp_datetime(text: str, key: str) -> datetime:
    v = inp_get(text, key)
    if v is None:
        raise KeyError(f"{key!r} not in sfincs.inp")
    return datetime.strptime(v, INP_FMT)


# ── discovery ────────────────────────────────────────────────────────────────


def restart_files(model_dir: Path) -> list[tuple[datetime, Path]]:
    out = []
    for p in Path(model_dir).iterdir():
        m = RST_RE.match(p.name)
        if m:
            out.append((datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S"), p))
    return sorted(out)


def last_time_s(nc: Path) -> float | None:
    """Last value on the ``time`` axis (seconds since tref), or None if absent/empty."""
    if not nc.is_file():
        return None
    try:
        with netCDF4.Dataset(nc) as ds:
            if "time" not in ds.variables or len(ds.variables["time"]) == 0:
                return None
            return float(np.asarray(ds.variables["time"][:]).ravel()[-1])
    except OSError:
        return None  # a file the solver was writing when it died can be unreadable


def segments(model_dir: Path) -> list[Path]:
    d = Path(model_dir) / SEG_DIR
    return sorted(p for p in d.iterdir() if p.is_dir()) if d.is_dir() else []


# ── plan / prepare ───────────────────────────────────────────────────────────


@dataclass
class Plan:
    action: str  # "fresh" | "resume" | "finish"
    reason: str
    rst: Path | None = None
    t_resume: datetime | None = None


def plan(model_dir: Path) -> Plan:
    model_dir = Path(model_dir)
    inp = model_dir / "sfincs.inp"
    orig = model_dir / ORIG_INP
    text = (orig if orig.is_file() else inp).read_text()
    tref = inp_datetime(text, "tref")
    tstart = inp_datetime(text, "tstart")
    tstop = inp_datetime(text, "tstop")
    dtmap = float(inp_get(text, "dtmapout") or 0.0)
    dtmax = float(inp_get(text, "dtmaxout") or 0.0)

    end_s = last_time_s(model_dir / "sfincs_map.nc")
    stop_s = (tstop - tref).total_seconds()
    if end_s is not None and end_s >= stop_s - dtmap / 2:
        return Plan("finish", f"map already reaches tstop ({end_s / 3600:.1f} h)")

    cands = [
        (t, p)
        for t, p in restart_files(model_dir)
        if tstart < t < tstop and (end_s is None or (t - tref).total_seconds() <= end_s)
    ]
    if dtmax > 0:
        on_lattice = [
            (t, p)
            for t, p in cands
            if abs(((t - tstart).total_seconds() / dtmax) % 1.0) < 1e-6
        ]
        if len(on_lattice) < len(cands):
            cands = on_lattice  # see the module docstring: never split a zsmax block
    if not cands:
        return Plan("fresh", "no usable restart file inside the written window")
    t, p = cands[-1]
    return Plan("resume", f"newest restart file {p.name}", rst=p, t_resume=t)


def prepare(model_dir: Path) -> Plan:
    """Retire the current outputs into a segment and rewrite sfincs.inp to resume.

    Returns the plan; only ``action == "resume"`` changes anything on disk. A ``fresh``
    plan on a dir whose inp was rewritten by an earlier resume restores the original.
    """
    model_dir = Path(model_dir)
    pl = plan(model_dir)
    inp = model_dir / "sfincs.inp"
    orig = model_dir / ORIG_INP
    if pl.action != "resume":
        if pl.action == "fresh" and orig.is_file():
            shutil.copy2(orig, inp)  # a stale resume inp must not run from scratch
        return pl

    if not orig.is_file():
        shutil.copy2(inp, orig)
    text = orig.read_text()

    n = len(segments(model_dir))
    seg = model_dir / SEG_DIR / f"seg{n:02d}_{pl.t_resume:%Y%m%d.%H%M%S}"
    seg.mkdir(parents=True, exist_ok=False)
    for fn in OUTPUTS:
        p = model_dir / fn
        if p.is_file():
            shutil.move(str(p), str(seg / fn))
    # the segment's own start, so stitch() does not have to parse anything else
    seg_start = inp_datetime(inp.read_text(), "tstart")  # the inp that PRODUCED it
    (seg / "segment_start.txt").write_text(seg_start.strftime(INP_FMT) + "\n")

    new = inp_set(
        text,
        {
            "tstart": pl.t_resume.strftime(INP_FMT),
            "tspinup": "0.0",
            "rstfile": pl.rst.name,
        },
    )
    inp.write_text(new)
    with (model_dir / HISTORY).open("a") as fh:
        fh.write(
            f"{datetime.now():%Y-%m-%d %H:%M:%S} resume from {pl.rst.name}: "
            f"segment {seg.name} retired (started {seg_start:%Y-%m-%d %H:%M})\n"
        )
    return pl


# ── stitch ───────────────────────────────────────────────────────────────────


def _owned_records(
    times: np.ndarray, start_s: float, next_s: float | None
) -> np.ndarray:
    m = times >= start_s - 1e-6
    if next_s is not None:
        m &= times < next_s - 1e-6
    return np.flatnonzero(m)


def _owned_blocks(
    tmax: np.ndarray, start_s: float, next_s: float | None, stop_s: float
) -> np.ndarray:
    m = (tmax > start_s + 1e-6) & (tmax <= stop_s + 1e-6) & (tmax < NC_FLOAT_FILL)
    if next_s is not None:
        m &= tmax <= next_s + 1e-6
    return np.flatnonzero(m)


def stitch(parts: list[tuple[float, Path]], out: Path, stop_s: float) -> dict:
    """Concatenate one output file across segments.

    ``parts`` are ``(start_seconds, file)`` in time order; the last is the final run's.
    Static variables come from the last file. Written to ``out`` via a temp name, then
    atomically replaced — a half-written stitched map must never look like a run.
    """
    out = Path(out)
    tmp = out.with_name(out.name + ".stitching")
    sel_t: list[tuple[Path, np.ndarray]] = []
    sel_m: list[tuple[Path, np.ndarray]] = []
    for i, (s0, fn) in enumerate(parts):
        nxt = parts[i + 1][0] if i + 1 < len(parts) else None
        with netCDF4.Dataset(fn) as ds:
            t = np.asarray(ds.variables["time"][:], dtype="float64").ravel()
            sel_t.append((fn, _owned_records(t, s0, nxt)))
            if "timemax" in ds.variables:
                tm = np.asarray(ds.variables["timemax"][:], dtype="float64").ravel()
                sel_m.append((fn, _owned_blocks(tm, s0, nxt, stop_s)))
    n_t = sum(len(ix) for _, ix in sel_t)
    n_m = sum(len(ix) for _, ix in sel_m)

    with (
        netCDF4.Dataset(parts[-1][1]) as src,
        netCDF4.Dataset(tmp, "w", format="NETCDF4") as dst,
    ):
        dst.setncatts({k: src.getncattr(k) for k in src.ncattrs()})
        for name, dim in src.dimensions.items():
            if name == "time":
                dst.createDimension(name, None)
            elif name == "timemax":
                dst.createDimension(name, n_m)
            else:
                dst.createDimension(name, len(dim))
        for name, v in src.variables.items():
            filt = v.filters() or {}
            chunks = v.chunking()
            kw = dict(
                zlib=bool(filt.get("zlib")),
                complevel=int(filt.get("complevel") or 4),
                shuffle=bool(filt.get("shuffle")),
            )
            if isinstance(chunks, list):
                kw["chunksizes"] = [
                    min(c, len(dst.dimensions[d]) or c) if d != "time" else c
                    for c, d in zip(chunks, v.dimensions)
                ]
            fill = v.getncattr("_FillValue") if "_FillValue" in v.ncattrs() else None
            nv = dst.createVariable(name, v.dtype, v.dimensions, fill_value=fill, **kw)
            nv.setncatts({k: v.getncattr(k) for k in v.ncattrs() if k != "_FillValue"})
            if "time" in v.dimensions or "timemax" in v.dimensions:
                continue
            nv[...] = v[...]
        # record axes: copy owned rows from every part, in order
        for axis, sel in (("time", sel_t), ("timemax", sel_m)):
            names = [n for n, v in src.variables.items() if axis in v.dimensions]
            if not names:
                continue
            k = 0
            for fn, idx in sel:
                if len(idx) == 0:
                    continue
                with netCDF4.Dataset(fn) as part:
                    for i in idx:
                        for name in names:
                            pv = part.variables[name]
                            ax = pv.dimensions.index(axis)
                            sl = [slice(None)] * pv.ndim
                            sl[ax] = i
                            data = pv[tuple(sl)]
                            osl = [slice(None)] * pv.ndim
                            osl[ax] = k
                            dst.variables[name][tuple(osl)] = data
                        k += 1
    tmp.replace(out)
    return {"records": n_t, "blocks": n_m, "parts": len(parts)}


def finish(model_dir: Path) -> dict:
    """After a solve: stitch retired segments (if any), restore sfincs.inp, drop rst files."""
    model_dir = Path(model_dir)
    segs = segments(model_dir)
    inp = model_dir / "sfincs.inp"
    orig = model_dir / ORIG_INP
    text = (orig if orig.is_file() else inp).read_text()
    tref = inp_datetime(text, "tref")
    stop_s = (inp_datetime(text, "tstop") - tref).total_seconds()
    report: dict = {"segments": len(segs)}

    if segs:
        parts_start = []
        for seg in segs:
            s = datetime.strptime(
                (seg / "segment_start.txt").read_text().strip(), INP_FMT
            )
            parts_start.append((s - tref).total_seconds())
        final_start = (inp_datetime(inp.read_text(), "tstart") - tref).total_seconds()
        for fn in ("sfincs_map.nc", "sfincs_his.nc"):
            parts = [
                (s, seg / fn)
                for s, seg in zip(parts_start, segs)
                if (seg / fn).is_file()
            ]
            if (model_dir / fn).is_file():
                parts.append((final_start, model_dir / fn))
            if len(parts) < 2:
                continue
            report[fn] = stitch(parts, model_dir / fn, stop_s)
        # logs: segments first, then the final run, so the file reads in time order
        logs = [seg / "sfincs.log" for seg in segs if (seg / "sfincs.log").is_file()]
        final_log = model_dir / "sfincs.log"
        if logs:
            body = ""
            for lg in logs:
                body += (
                    f"===== {lg.parent.name} (preempted segment) =====\n"
                    + lg.read_text()
                )
            body += "===== resumed run =====\n"
            body += final_log.read_text() if final_log.is_file() else ""
            final_log.write_text(body)
        for seg in segs:
            shutil.rmtree(seg)
        shutil.rmtree(model_dir / SEG_DIR, ignore_errors=True)

    if orig.is_file():
        shutil.copy2(orig, inp)
        orig.unlink()
    removed = 0
    for _, p in restart_files(model_dir):
        p.unlink()
        removed += 1
    report["rst_removed"] = removed
    if segs or removed:
        with (model_dir / HISTORY).open("a") as fh:
            fh.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} finish: {report}\n")
    return report


def add_restart_output(text: str, dt_s: float = 21600.0) -> str:
    """Give a staged sfincs.inp restart output on the same lattice as its zsmax blocks."""
    return inp_set(text, {"dtrstout": f"{dt_s:.1f}", "dtmaxout": f"{dt_s:.1f}"})


__all__ = [
    "Plan",
    "add_restart_output",
    "finish",
    "inp_get",
    "inp_set",
    "plan",
    "prepare",
    "restart_files",
    "stitch",
]
