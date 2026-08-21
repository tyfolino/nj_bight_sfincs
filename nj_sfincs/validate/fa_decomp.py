"""Decompose MOTF false alarms by how the water could have got there.

WHY (2026-08-20). MOTF is a surge-only bathtub — a water surface interpolated from
HWMs/sensors over lidar. It structurally CANNOT show rain ponding. Our runs force
rain in every arm (AORC hourly) and infiltration is effectively OFF (`model.py`
strips the CN keys from `sfincs.inp` — see FINDINGS), so rain lands on
impervious-in-effect ground and ponds. Every such pond scores as a FALSE ALARM
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
* ``motf_km2_fa_rainonly``     — the disconnected subset whose ponded depth is within
  the LOCAL AORC storm-total rain depth: conservatively attributable to rain alone.
  ⚠️ A LOWER bound — with infiltration off, a depression collects its contributing
  area's rain, so a real rain pond can be deeper than the local total.
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

#: Storm-total rain file (hourly; summed here) and the wet threshold shared with the
#: extent metric. AORC covers lat 39.66–40.57 — pixels past its edge get NaN rain and
#: can therefore never classify as rainonly, which is the conservative direction.
AORC_NC = "precip/aorc_sandy_nj.nc"


def _rain_total_m(lon: np.ndarray, lat: np.ndarray, data_dir: Path) -> np.ndarray:
    """AORC storm-total rain depth [m] at each (lon, lat), nearest-cell, NaN outside."""
    import xarray as xr  # noqa: PLC0415

    ds = xr.open_dataset(Path(data_dir) / AORC_NC)
    total = ds["precip"].sum("time").values  # mm over the window
    xs, ys = ds["x"].values, ds["y"].values
    dx, dy = xs[1] - xs[0], ys[1] - ys[0]
    ci = np.round((lon - xs[0]) / dx).astype(int)
    ri = np.round((lat - ys[0]) / dy).astype(int)
    ok = (ci >= 0) & (ci < xs.size) & (ri >= 0) & (ri < ys.size)
    out = np.full(lon.shape, np.nan)
    out[ok] = total[ri[ok], ci[ok]] / 1000.0
    ds.close()
    return out


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
    from pyproj import Transformer  # noqa: PLC0415

    from .. import domain as _domain  # noqa: PLC0415
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

    # rain budget on the disconnected subset only (lazy: skip when nothing to label)
    if fa_disc.any():
        XX, YY = np.meshgrid(Xc, Yc)
        lon, lat = Transformer.from_crs(
            _domain.active().epsg, 4326, always_xy=True
        ).transform(XX[fa_disc], YY[fa_disc])
        rain_m = _rain_total_m(lon, lat, data_dir)
        rainonly_n = int((h_at[fa_disc] <= rain_m).sum())
    else:
        rainonly_n = 0

    nh, nm = int(hits.sum()), int(miss.sum())
    nfc, nfd = int(fa_conn.sum()), int(fa_disc.sum())
    km2 = abs(mtf.a * mtf.e) / 1e6
    return {
        "motf_km2_fa_connected": nfc * km2,
        "motf_km2_fa_disconnected": nfd * km2,
        "motf_km2_fa_rainonly": rainonly_n * km2,
        "motf_far_connected": nfc / (nh + nfc) if (nh + nfc) else float("nan"),
        "motf_csi_connected": (
            nh / (nh + nm + nfc) if (nh + nm + nfc) else float("nan")
        ),
    }
