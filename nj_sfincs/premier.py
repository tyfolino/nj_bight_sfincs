"""THE PREMIER and the domain it stands on — one place, asserted, not remembered.

WHY THIS FILE EXISTS (2026-07-21)
---------------------------------
The tidal phase-lag A/B (``phaselag_battery`` / ``_shblend`` / ``_gtsm``) ran to completion
on SLURM — clean exit, full-length output, no warning anywhere — and was **scientifically
void**, because ``run_experiments.py`` staged it from ``experiments/_template`` while the
adopted premier lives on ``experiments/_template_sealed``. Those are different domains: the
old one still has the Navesink mass leak and a dammed Shark River Inlet.

Nothing caught it. The staging was silent, the solver was happy, and the metrics came back
as plain numbers with no marking to say which planet they were measured on. What finally
exposed it was ``stat``-ing inodes by hand, hours later.

The trap has a sharp edge worth naming: **the open coast is nearly domain-independent.**
``phaselag_battery`` reproduced the premier's Sandy Hook phase lag to within 0.3 min
(16.9 vs 17.2), which looked like proof the harness had staged correctly. It was not. The
estuary — the entire subject of the experiment — was 30% down in tidal range at Shrewsbury
and flat dead at Shark (0.03 m vs 1.35 m). A coastal control cannot validate an interior
experiment, and a control that passes on the wrong domain is worse than no control at all.

So: the premier's identity is defined HERE, checked by fingerprint, and asserted at every
point where an experiment is staged or scored.

WHAT IDENTIFIES THE DOMAIN
--------------------------
Not file size, and not the inode. Both are real signals — every ``sealed_*`` run hard-links
one 253,750,180-byte ``sfincs.nc`` (inode 579215649) while the old template's is
253,681,934 — but a per-experiment forcing override rewrites ``sfincs.nc`` in place, giving
each arm its own inode and breaking the link. Size survives that; identity does not.

What survives everything is the **mesh and the bed**:

    sealed   547,408 faces   1,635 boundary edges   sha256(z, mask)[:16] = 45f4f74ca9a2347d
    OLD      547,267 faces   1,676 boundary edges   sha256(z, mask)[:16] = ffc48087214bb848

The 41 extra boundary edges in the old domain *are* the leak: the free-outflow face hydromt
cut across the Navesink. Verified stable across ``_template_sealed``, ``faber-waves-premier``,
``faber-nowaves`` and ``galibier-waves`` (waves on and off, both engines), and distinct from
``_template`` and all three ``phaselag_*`` arms.

``snapwave_mask`` is deliberately EXCLUDED from the hash — ``add_waves`` rewrites it per wave
config, so folding it in would make no-waves and waves arms of the same domain disagree.

Audit any directory::

    PYTHONPATH=$PWD python -m nj_sfincs.premier experiments/v1_monmouth/faber-waves-premier

⚠️ ``mask_zmin`` IS HALF OF THIS HASH (this repo, 2026-08-13). It therefore lives on
``Domain``, not on ``BaseConfig``: a "boundary-depth arm" that changed it would fail
``assert_sealed_domain`` on its own staged copy. A −10 m and a −15 m boundary are two
registered DOMAINS sharing one ``mesh_key`` — two fingerprints with identical face and
boundary-edge counts differing ONLY in ``sha_z_mask``, which is exactly the trap the
archive's V2/PREMASK pair set. You cannot tell them apart by counting.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import xarray as xr

from nj_sfincs import domain as _domain
from nj_sfincs.config import exp_root

# ---------------------------------------------------------------------------
# The premier
# ---------------------------------------------------------------------------

#: The reference configuration on whatever domain is active. The NAME is the same on
#: every domain because it is the same CONFIGURATION — what changes is the domain it
#: stands on, which is why the fingerprint is checked separately below rather than being
#: inferred from a run's name.
PREMIER_NAME = "naccs-premier"

TEMPLATE_NAME = "_template_sealed"


def sealed_template() -> Path:
    """The ONLY template new experiments may be staged from, for the ACTIVE domain.

    Domain-scoped (``experiments/<domain>/_template_sealed``) because each domain has its
    own sealed template under the same name — see ``config.exp_root``.
    """
    return exp_root() / TEMPLATE_NAME


@dataclass(frozen=True)
class DomainFingerprint:
    """Identity of the physical domain: the mesh and the bed, nothing else."""

    n_faces: int
    n_boundary_edges: int
    sha_z_mask: str

    def __str__(self) -> str:
        return (
            f"faces={self.n_faces} boundary_edges={self.n_boundary_edges} "
            f"sha(z,mask)={self.sha_z_mask}"
        )


#: v1_monmouth — FROZEN, and here for one job only: proving the validation port against a
#: known answer (docs/STATUS.md). Region fixed at the Navesink leak's root + the Shark
#: eHydro inlet carve.
V1_MONMOUTH = DomainFingerprint(547408, 1635, "45f4f74ca9a2347d")

#: v1_5_raritan at mask_zmin = -10 m. Frozen 2026-08-14 from
#: ``data/frozen_mesh_v1_5_raritan_z10`` (mesh_key ``v1_5_raritan_z10``).
#:
#: ⚠️ ``v1_5_raritan_z15`` will SHARE this mesh_key and differ from this fingerprint ONLY
#: IN THE SHA — identical face and boundary-edge counts, because it is staged from this
#: same mesh by ``scripts/setup_boundary_depth.py``, which re-derives the mask on a copy.
#: You cannot tell the two apart by counting anything.
V1_5_RARITAN_Z10 = DomainFingerprint(696230, 1652, "2a23667dd16e449c")

#: The fingerprint each registered domain MUST have. Keyed by ``domain.Domain.name``, so
#: ``NJ_DOMAIN`` selects both the geography and the identity check in one move and the two
#: cannot drift apart.
#:
#: A domain with no entry here audits "UNRECOGNISED" — an unimplemented feature that reads
#: exactly like a real domain error, and therefore trains you to ignore the one alarm that
#: matters. Register a domain's fingerprint BEFORE running anything on it.
EXPECTED: dict[str, DomainFingerprint] = {
    "v1_monmouth": V1_MONMOUTH,
    "v1_5_raritan": V1_5_RARITAN_Z10,
}

KNOWN = {
    V1_MONMOUTH: "v1_monmouth FROZEN (leak fixed, Shark inlet carved) — archive fixture",
    V1_5_RARITAN_Z10: (
        "v1_5_raritan z10 FROZEN 2026-08-14 — boundary out of Raritan Bay "
        "(ocean + Narrows + Arthur Kill mouth), CoNED bed at Ward Point, Raritan discharge"
    ),
}


# ── BRACKETS: deliberately INADMISSIBLE bounds ───────────────────────────────
# A bracket is a domain built to be WRONG in a known direction, so the true answer can be
# bounded between two runs.
#
# ⚠️ WHY THESE LIVE IN THEIR OWN REGISTRY AND NOT IN ``EXPECTED``.
# Putting a bracket fingerprint in ``EXPECTED`` would make ``assert_sealed_domain`` PASS
# on it under some NJ_DOMAIN. That is precisely the property we must not have. This
# project has already lost a four-day campaign to an inadmissible boundary condition that
# scored WELL (the Barnegat Inlet clamp) — the lesson was that labelling is not enough,
# the guard has to refuse. So a bracket is recognised, named loudly, and REJECTED by the
# sealed-domain check; it is scored only through its own script into its own CSV.
#
# ``BRACKETS`` is EMPTY on a fresh repo, and the tests still assert the empty-set
# property, because the invariant has to be in place before the first bracket exists.


@dataclass(frozen=True)
class Bracket:
    """A deliberately inadmissible domain used to BOUND a quantity, never to model it."""

    name: str
    base_domain: str
    fingerprint: DomainFingerprint
    bound: str  # "upper" | "lower" — which way it is wrong, stated up front
    inadmissible_why: str
    bounds_what: str


BRACKETS: dict[str, Bracket] = {}

#: A run directory whose name starts with this is a bracket. Machine-checkable, and
#: deliberately redundant with ``Experiment.bracket`` — belt and braces, because the whole
#: point is that this cannot be forgotten.
BRACKET_PREFIX = "BRACKET+"


def bracket_of(model_dir: "Path | str") -> "Bracket | None":
    """The Bracket this directory is, or None. Matches on the domain fingerprint."""
    try:
        fp = domain_fingerprint(model_dir)
    except (FileNotFoundError, OSError):
        return None
    for b in BRACKETS.values():
        if b.fingerprint.sha_z_mask != "PENDING" and fp == b.fingerprint:
            return b
    return None


def assert_bracket(model_dir: "Path | str", name: str, context: str = "") -> None:
    """Assert this directory IS the named bracket, and that the caller meant it.

    Requires ``NJ_ALLOW_BRACKET=<name>`` in the environment. That is cheap and it means an
    accidental invocation — a sweep, a copied command line — cannot stage or score a
    bracket by mistake.
    """
    b = BRACKETS.get(name)
    if b is None:
        raise KeyError(f"unknown bracket {name!r}; known: {sorted(BRACKETS)}")
    if os.environ.get("NJ_ALLOW_BRACKET") != name:
        raise RuntimeError(
            f"{context}: refusing to touch bracket {name!r} without "
            f"NJ_ALLOW_BRACKET={name}. A bracket is a deliberately INADMISSIBLE bound, "
            f"not a candidate configuration.\n  {b.inadmissible_why}"
        )
    got = domain_fingerprint(model_dir)
    if b.fingerprint.sha_z_mask != "PENDING" and got != b.fingerprint:
        raise WrongDomainError(
            f"{context}: {model_dir} is not bracket {name!r}.\n"
            f"    expected {b.fingerprint}\n    got      {got}"
        )


def expected() -> DomainFingerprint:
    """The fingerprint the ACTIVE domain (``NJ_DOMAIN``) must have."""
    name = _domain.active().name
    if name not in EXPECTED:
        raise KeyError(
            f"domain {name!r} has no sealed fingerprint in premier.EXPECTED. Build its "
            "frozen mesh, compute sha256 over (z, mask) with domain_fingerprint(), and "
            "register it here BEFORE running anything on it — an unregistered domain "
            "cannot be told apart from a corrupted one."
        )
    return EXPECTED[name]


class WrongDomainError(RuntimeError):
    """Raised when a model directory is not on the sealed domain."""


#: How far a written observation point may sit from the coordinate the registry declares.
#: Tight, because these coordinates are HAND-PLACED: several gauges are nudged tens of
#: metres off their published position to land in a channel rather than on the bank
#: beside it. 1 m is "the same point"; anything larger is a different point.
OBS_TOL_M = 1.0


def obs_points_ok(model_dir: Path | str) -> "tuple[bool, list[str]]":
    """Do the written ``sfincs.obs`` points match the domain registry?

    ⚠️ THIS IS A GENERALISED SCAR, not a new idea. The archive hard-coded one comparison
    here — the Shrewsbury gauge, nudged 21 m into the channel so it samples water at
    −4.33 m rather than the +1.46 m bank it started on. The old template still had the
    bank point, and a bank cell that only wets during the storm returns NaN from every
    pre-storm tide and phase metric, silently, on every arm staged from it.

    That is not a Shrewsbury fact, it is a fact about hand-placed observation points, and
    every domain will have some. So it is checked against the registry rather than against
    one remembered coordinate pair.

    Returns ``(ok, problems)``. ``ok`` is True when there is no ``sfincs.obs`` to check —
    absence is a different failure and is not this function's to report.
    """
    obs = Path(model_dir) / "sfincs.obs"
    if not obs.exists():
        return True, []

    from pyproj import Transformer

    dom = _domain.active()
    written: list[tuple[str, float, float]] = []
    for line in obs.read_text().splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        try:
            written.append((parts[2], float(parts[0]), float(parts[1])))
        except ValueError:
            continue

    tf = Transformer.from_crs(4326, dom.epsg, always_xy=True)
    problems = []
    for g in dom.obs_gauges:
        want_x, want_y = tf.transform(g.lon, g.lat)
        hit = [w for w in written if g.name in w[0]]
        if not hit:
            problems.append(f"'{g.name}' is not in sfincs.obs at all")
            continue
        _, gx, gy = hit[0]
        d = float(np.hypot(gx - want_x, gy - want_y))
        if d > OBS_TOL_M:
            problems.append(
                f"'{g.name}' sits {d:.1f} m from its registered position "
                f"(written {gx:.1f},{gy:.1f}; registry {want_x:.1f},{want_y:.1f})"
            )
    return (not problems), problems


def domain_fingerprint(model_dir: Path | str) -> DomainFingerprint:
    """Fingerprint the domain in ``model_dir/sfincs.nc``."""
    path = Path(model_dir) / "sfincs.nc"
    if not path.exists():
        raise FileNotFoundError(f"no sfincs.nc in {model_dir}")
    with xr.open_dataset(path) as ds:
        h = hashlib.sha256()
        for var in ("z", "mask"):  # NOT snapwave_mask — rewritten per wave config
            h.update(var.encode())
            h.update(np.ascontiguousarray(ds[var].values).tobytes())
        return DomainFingerprint(
            int(ds.sizes["mesh2d_nFaces"]),
            int(ds.sizes["mesh2d_nBoundary_edges"]),
            h.hexdigest()[:16],
        )


def is_sealed(model_dir: Path | str) -> bool:
    """True iff ``model_dir`` sits on the ACTIVE domain. False if it has no sfincs.nc."""
    try:
        return domain_fingerprint(model_dir) == expected()
    except FileNotFoundError:
        return False


def assert_sealed_domain(model_dir: Path | str, context: str = "") -> None:
    """Raise unless ``model_dir`` is on the sealed domain for the active NJ_DOMAIN.

    Call this wherever an experiment is staged or scored. A wrong domain is not a degraded
    result — it is a different planet, and its numbers must never reach a table.
    """
    where = f"{context}: " if context else ""
    want = expected()
    dom = _domain.active().name
    got = domain_fingerprint(model_dir)

    # A BRACKET MUST BE REFUSED BY NAME, not merely fail as "some wrong domain". The
    # generic message would send the reader looking for a staging mistake; this one says
    # what the directory actually is and why it can never be a candidate.
    brk = next(
        (
            b
            for b in BRACKETS.values()
            if b.fingerprint.sha_z_mask != "PENDING" and got == b.fingerprint
        ),
        None,
    )
    if brk is not None:
        raise WrongDomainError(
            f"{where}{model_dir} is the INADMISSIBLE BRACKET '{brk.name}' "
            f"({brk.bound} bound), not a sealed domain.\n"
            f"    {brk.inadmissible_why}\n"
            f"    it bounds: {brk.bounds_what}\n"
            "  Score it with scripts/score_bracket.py and NJ_ALLOW_BRACKET set.\n"
            "  It must never enter reports/metrics.csv or sit in a table beside a "
            "candidate arm."
        )

    if got != want:
        raise WrongDomainError(
            f"{where}{model_dir} is NOT on domain '{dom}'.\n"
            f"    expected {want}  <- {KNOWN[want]}\n"
            f"    got      {got}"
            + (f"  <- {KNOWN[got]}" if got in KNOWN else "  <- UNRECOGNISED domain")
            + f"\n  Stage from {TEMPLATE_NAME}, and check NJ_DOMAIN (currently {dom!r})\n"
            "  agrees with the mesh the template was built from.\n"
            "  Results from the wrong domain are void.\n"
            "  NB the OPEN COAST barely moves between domains — a healthy open-coast\n"
            "  number is NOT evidence the domain is right."
        )

    ok, problems = obs_points_ok(model_dir)
    if not ok:
        raise WrongDomainError(
            f"{where}{model_dir} has the sealed domain but STALE observation points:\n"
            + "\n".join(f"    - {p}" for p in problems)
            + "\n  Several of these coordinates are hand-nudged into a channel; a point "
            "that\n  drifts back onto the bank beside it only wets during the storm, so "
            "every\n  pre-storm tide and phase metric silently returns NaN."
        )


def _inp(model_dir: Path, key: str) -> str | None:
    """One value out of sfincs.inp, or None. Local so premier imports nothing heavier."""
    p = Path(model_dir) / "sfincs.inp"
    if not p.is_file():
        return None
    for line in p.read_text().splitlines():
        if "=" in line and line.split("=")[0].strip() == key:
            return line.split("=", 1)[1].strip()
    return None


def output_complete(model_dir: Path | str) -> tuple[bool | None, list[str]]:
    """Does this run's output reach its own configured ``tstop``? ``None`` = no output yet.

    🔴 EVERY OTHER GUARD IN THIS FILE CHECKS *IDENTITY* — that a run is on the domain it
    claims. Nothing checked that a run's output is WHOLE, and on 2026-08-15 that gap cost
    all three v1.5 arms. The `hal*` jobs completed correctly on 08-14; ~25 h later the
    buffered writes of the `halk*` jobs that had died on the same run dirs landed on top
    of them, leaving 12-86% of the window and, on two arms, an all-fill `zsmax`.

    ⚠️ **It reads back completely clean.** The file is a valid netCDF — `time` is an
    unlimited dimension, so a short file is well-formed, not corrupt — and it carries the
    *halk* job's mtime, so it never looks stale next to anything. `sacct` says COMPLETED,
    the solver log says `Closing off SFINCS`, and the run dir still fingerprints. The only
    thing that tells you is the last timestamp against `tstop`.

    Checks the map, the his, and `zsmax`: the max-water-level blocks are written LAST, so
    they are the first thing a truncated run loses, and they are what every flood-extent
    and HWM metric is computed from. An all-fill `zsmax` scores the model bone dry.
    """
    model_dir = Path(model_dir)
    t0, t1 = _inp(model_dir, "tstart"), _inp(model_dir, "tstop")
    if not t0 or not t1:
        return None, []
    from datetime import datetime

    fmt = "%Y%m%d %H%M%S"
    span = (datetime.strptime(t1, fmt) - datetime.strptime(t0, fmt)).total_seconds()
    if span <= 0:
        return None, []

    problems: list[str] = []
    seen = False
    for fn, key in (("sfincs_map.nc", "dtmapout"), ("sfincs_his.nc", "dthisout")):
        p = model_dir / fn
        if not p.is_file():
            continue
        seen = True
        step = float(_inp(model_dir, key) or 0) or span
        # decode_times=False: an unwritten `timemax` block holds the raw netCDF float fill
        # and blows up CF time decoding, which would make this guard fail on exactly the
        # runs it exists to catch.
        with xr.open_dataset(p, decode_times=False) as ds:
            if "time" not in ds.variables or ds.sizes.get("time", 0) == 0:
                problems.append(f"{fn}: no time axis")
                continue
            last = float(np.asarray(ds["time"].values).ravel()[-1])
            if last < span - step / 2:
                problems.append(
                    f"{fn}: ends at {last / 3600:.1f} h of {span / 3600:.1f} h "
                    f"({100 * last / span:.0f}%)"
                )
            if fn == "sfincs_map.nc" and "zsmax" in ds.variables:
                z = np.asarray(ds["zsmax"].values, dtype="float64")
                # -99999 is SFINCS' fill; the attribute is present but decode is off here.
                if not np.isfinite(z).any() or not (z > -9.0e3).any():
                    problems.append("sfincs_map.nc: zsmax is entirely fill (never written)")
    if not seen:
        return None, []
    return (not problems), problems


def describe(model_dir: Path | str) -> str:
    """One-line audit of a model directory."""
    try:
        fp = domain_fingerprint(model_dir)
    except FileNotFoundError as e:
        return f"  {str(model_dir):44s} -- {e}"
    label = KNOWN.get(fp, "UNRECOGNISED")
    ok, problems = obs_points_ok(model_dir)
    obs_s = "obs OK" if ok else f"OBS STALE ({len(problems)})"
    whole, gaps = output_complete(model_dir)
    out_s = {None: "no output", True: "output WHOLE"}.get(whole, "OUTPUT TRUNCATED")
    flag = "OK  " if (fp == expected() and ok and whole is not False) else "BAD "
    line = f"  {flag}{str(model_dir):44s} {label:60s} {obs_s}  {out_s}"
    for g in gaps:
        line += f"\n      🔴 {g}"
    return line


def _main(argv: list[str] | None = None) -> int:
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        args = sorted(str(p) for p in exp_root().glob("*") if (p / "sfincs.nc").exists())
    dom = _domain.active().name
    print(f"PREMIER = {PREMIER_NAME}   template = {TEMPLATE_NAME}")
    print(f"NJ_DOMAIN = {dom}")
    print(f"expected domain: {expected()}\n")
    bad = 0
    for a in args:
        line = describe(a)
        bad += line.lstrip().startswith("BAD")
        print(line)
    print(f"\n{len(args) - bad}/{len(args)} on domain '{dom}'")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(_main())
