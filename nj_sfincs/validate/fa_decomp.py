"""Decompose MOTF false alarms by how the water could have got there.

WHY (2026-08-20). MOTF is a surge-only bathtub — a water surface interpolated from
HWMs/sensors over lidar. It structurally CANNOT show rain ponding. Our runs force
rain (infiltration was off when this was written; v4 premiers since 10-11 use the curve
number), and rain that ponds deeper than DEPTH_MIN scores as a FALSE ALARM
against a reference that could never contain it, deflating CSI for a reason that is
a *reference* limitation, not a model error.

THE DECOMPOSITION. On the MOTF grid, label the connected components of the model's
wet footprint (``hmax >= DEPTH_MIN``, 8-connected) and mark the components that touch
permanent tidal water (``dep <= 0``). Because ``hmax`` is a running max, its footprint
is the UNION of everything that was ever wet — so a false-alarm pixel in a component
that never touches the sea had **no wet surface path to tidal water at any point in
the run**: its water arrived as rain / local runoff (or was there at t=0), not as
surge. That is the split:

* ``motf_km2_fa_connected``    — FA with a wet path to the sea: surge-plausible;
  MOTF could in principle have adjudicated it.
* ``motf_km2_fa_disconnected`` — FA with no wet path to the sea, ever: not surge.
* (RETIRED 2026-10-20, user: ``motf_km2_fa_rainonly`` — "ponded depth within the local
  AORC storm total" was 0 BY CONSTRUCTION, since wet needs h >= DEPTH_MIN = 0.15 m and
  Sandy's total here is 5–12 cm. ⚠️ Neither key above separates rain from surge either: a
  rain-fed creek is sea-connected. The attribution is the TWIN-RUN split —
  logs/fa_rain_2026-10-20/fa_cause_split.py, FINDINGS part 4 (h): v4_refreeze
  naccs-premier 79 of 128.5 km² from rain.)
* ``motf_far_connected`` / ``motf_csi_connected`` — FAR/CSI recomputed counting only
  the connected false alarms, i.e. "the score if the reference's rain-blindness is
  excused". ⚠️ DIAGNOSTIC keys, reported ALONGSIDE ``motf_far``/``motf_csi`` — the
  headline keys are untouched (warn, never gate; flag, never delete).

The classifier is heuristic; ``diag-premier-norain`` (the rain-off copy of the
premier) is its empirical check — wet-in-premier ∧ dry-in-norain ≈ ground truth for
the rain labels.

Same screens as ``motf_metrics`` (simulated_mask + ``Domain.motf_exclude_boxes_ll``),
or the two would disagree about what was even compared.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio

from .core import DEPTH_MIN
from .metrics import DATA, motf_exclude_mask, motf_path


def sea_connected(mod_wet: np.ndarray, dep_at: np.ndarray) -> np.ndarray:
    """Which wet pixels sit in a component that touches permanent tidal water.

    8-connected components of the ever-wet footprint, seeded where the bed is at or
    below 0 m — the same rule ``fa_decomposition`` scores with, shared so a plot can
    never disagree with the CSV about which false alarms are surge-plausible.
    """
    from scipy import ndimage  # noqa: PLC0415

    labels, _n = ndimage.label(mod_wet, structure=np.ones((3, 3), dtype=int))
    seed_labels = np.unique(labels[mod_wet & (dep_at <= 0.0)])
    return np.isin(labels, seed_labels[seed_labels != 0])


def fa_decomposition(da_hmax, da_dep, model_dir: Path, data_dir: Path = DATA) -> dict:
    """The false-alarm decomposition keys. See the module docstring."""
    from .core import simulated_mask  # noqa: PLC0415

    with rasterio.open(str(motf_path(data_dir))) as r:
        motf, mtf, m_nd = r.read(1), r.transform, r.nodata
    mod_t = da_dep.rio.transform()
    mh, mw = motf.shape

    # same gather as motf_metrics: model values at MOTF cell centres
    Xc = mtf.c + (np.arange(mw) + 0.5) * mtf.a
    Yc = mtf.f + (np.arange(mh) + 0.5) * mtf.e
    mc = np.clip(((Xc - mod_t.c) / mod_t.a).astype(int), 0, da_dep.shape[-1] - 1)
    mr = np.clip(((Yc - mod_t.f) / mod_t.e).astype(int), 0, da_dep.shape[-2] - 1)
    rr, cc = np.meshgrid(mr, mc, indexing="ij")

    def _2d(a):
        return a[0] if a.ndim == 3 else a

    dep_at, h_at = _2d(da_dep.values)[rr, cc], _2d(da_hmax.values)[rr, cc]

    motf_wet = motf == 1
    mod_wet = (h_at >= DEPTH_MIN) & np.isfinite(h_at)
    footprint = (motf != m_nd) & (dep_at > 0.0)
    sim = simulated_mask(model_dir, motf.shape, mtf)
    excl = motf_exclude_mask(motf.shape, mtf)
    land_in = footprint & sim
    if excl is not None:
        land_in = land_in & ~excl

    # connectivity of the EVER-WET footprint to permanent tidal water
    connected = sea_connected(mod_wet, dep_at)

    hits = motf_wet & mod_wet & land_in
    miss = motf_wet & ~mod_wet & land_in
    fa = ~motf_wet & mod_wet & land_in
    fa_conn = fa & connected
    fa_disc = fa & ~connected

    nh, nm = int(hits.sum()), int(miss.sum())
    nfc, nfd = int(fa_conn.sum()), int(fa_disc.sum())
    km2 = abs(mtf.a * mtf.e) / 1e6
    return {
        "motf_km2_fa_connected": nfc * km2,
        "motf_km2_fa_disconnected": nfd * km2,
        "motf_far_connected": nfc / (nh + nfc) if (nh + nfc) else float("nan"),
        "motf_csi_connected": (
            nh / (nh + nm + nfc) if (nh + nm + nfc) else float("nan")
        ),
    }
