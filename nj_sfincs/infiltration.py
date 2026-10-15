"""Curve number WITH recovery (SFINCS ``cnb``) on a staged quadtree run (2026-10-15).

``cna`` (the 10-11 premier) has no soil state across a restart and no recovery between rain
bands; ``cnb`` carries ``scs_Se`` in its restart file (rsttype 4) and recovers S during dry
spells (SWMM eqs. 4-36 / 4-37). Read from v2.3.3 ``sfincs_infiltration.f90``:

* inputs per ACTIVE point: ``smax`` [m] (the maximum retention), ``seff`` [m] (S at the
  start of the first rain event) and ``ks`` [mm/h] (sets the recovery rate
  ``kr = sqrt(ks / 25.4) / 75`` per hour). We write them as three binary ``real*4`` files in
  the active-point order of ``sea_level.py`` (keys ``smaxfile`` / ``sefffile`` /
  ``ksfile``), so the 2.2 GB quadtree file is never rewritten per arm.
* ``smax`` = the premier's own CN retention, ``scs`` [in] in the staged qtrfile x 0.0254, so
  the soil MAP is the premier's (NLCD 2012 x SSURGO HSG, CN II, water CN 100 -> S 0).
* ``effective`` is the antecedent-moisture knob (logs/soil_moisture_2026-10-11/README.md §5:
  S_I = 2.381 S_II, S_III = 0.435 S_II; 1.0 = AMC II, 2.38 = AMC I).
* 🔴 After ANY dry spell longer than ``0.06 / kr`` hours the engine sets
  ``Se = min(Se, smax)`` — about 2 h on sand. Sandy's 10-28 rain is light and patchy, so
  with ``smax`` = S_II an ``effective`` of 1.5 would collapse to 1.0 on most of the coastal
  plain before the main rain. Hence ``smax = max(1, effective) * S_II``: the soil can hold
  what it starts with (stated choice, 2026-10-15).
* ``ks`` = SSURGO surface-horizon ksat [µm/s] (``Domain.ksat_dataset``) at the face CENTRE
  (hydromt averages over the face; SSURGO map units are larger than most faces), capped at
  100 µm/s like hydromt, x 3.6 -> mm/h; NoData -> 0 (no recovery).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

SMAX_FILE = "sfincs_cnb_smax.bin"
SEFF_FILE = "sfincs_cnb_seff.bin"
KS_FILE = "sfincs_cnb_ks.bin"
CNB_META = "sfincs_cnb.json"
KSAT_CAP_UM_S = 100.0


def cnb_arrays(
    scs_in: np.ndarray, ksat_um_s: np.ndarray, effective: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(smax [m], seff [m], ks [mm/h]) from CN retention [in] and ksat [µm/s]."""
    if not np.isfinite(effective) or effective <= 0:
        raise ValueError(f"effective must be > 0, got {effective!r}")
    s2 = np.where(np.isfinite(scs_in), scs_in, 0.0) * 0.0254
    smax = s2 * max(1.0, float(effective))
    seff = s2 * float(effective)
    ks = np.where(np.isfinite(ksat_um_s), np.minimum(ksat_um_s, KSAT_CAP_UM_S), 0.0)
    ks = np.maximum(ks, 0.0) * 3.6
    return smax.astype("<f4"), seff.astype("<f4"), ks.astype("<f4")


def sample_ksat(
    path: Path | str, x: np.ndarray, y: np.ndarray, epsg: int
) -> np.ndarray:
    """ksat [µm/s] at points (x, y) in EPSG ``epsg``; NaN off the raster / on NoData.
    Reads the raster once and indexes it through the inverse affine (4 M points)."""
    import rasterio
    from pyproj import Transformer

    with rasterio.open(path) as src:
        tx = Transformer.from_crs(epsg, src.crs, always_xy=True)
        px, py = tx.transform(np.asarray(x, float), np.asarray(y, float))
        arr = src.read(1).astype(float)
        nod = src.nodata
        col, row = ~src.transform * (px, py)
    if nod is not None and np.isfinite(nod):
        arr[arr == nod] = np.nan
    r, c = np.floor(row).astype(np.int64), np.floor(col).astype(np.int64)
    ok = (r >= 0) & (r < arr.shape[0]) & (c >= 0) & (c < arr.shape[1])
    out = np.full(len(r), np.nan)
    out[ok] = arr[r[ok], c[ok]]
    return out


def write_cnb_inputs(
    model_dir: Path | str, effective: float, ksat_path: Path | str, epsg: int, qtr: str
) -> dict:
    """Write the three binaries + ``CNB_META`` into a STAGED dir; returns the meta.

    New inodes (write tmp + replace), so a hard-linked staged input is never written
    through (CLAUDE.md §5).
    """
    import xarray as xr

    d = Path(model_dir)
    with xr.open_dataset(d / qtr) as g:
        if "scs" not in g:
            raise SystemExit(f"cnb: {qtr} carries no 'scs' (the premier CN retention)")
        act = g["mask"].values > 0
        scs = g["scs"].values[act]
        fx = g["mesh2d_face_x"].values[act]
        fy = g["mesh2d_face_y"].values[act]
    ksat = sample_ksat(ksat_path, fx, fy, epsg)
    smax, seff, ks = cnb_arrays(scs, ksat, effective)
    for name, arr in ((SMAX_FILE, smax), (SEFF_FILE, seff), (KS_FILE, ks)):
        tmp = d / (name + ".tmp")
        arr.tofile(tmp)
        tmp.replace(d / name)
    land = smax > 0
    meta = {
        "effective": float(effective),
        "smax_factor": max(1.0, float(effective)),
        "active_points": int(act.sum()),
        "infiltrating_points": int(land.sum()),
        "ksat_source": str(ksat_path),
        "ks_missing_on_land": float(np.mean(~np.isfinite(ksat[land])))
        if land.any()
        else 0.0,
        "seff_m_p10_50_90": np.percentile(seff[land], [10, 50, 90]).round(4).tolist()
        if land.any()
        else [],
        "ks_mm_h_p10_50_90": np.percentile(ks[land], [10, 50, 90]).round(2).tolist()
        if land.any()
        else [],
    }
    (d / CNB_META).write_text(json.dumps(meta, indent=1) + "\n")
    return meta


def cnb_keys(lines: list[str]) -> list[str]:
    """The ``sfincs.inp`` lines that select ``cnb`` from the binaries. The engine picks
    ``cnb`` from ``sefffile`` only when no ``infiltration_file`` / ``scsfile`` /
    ``qinf`` > 0 / ``qinffile`` precedes it — the caller strips those."""
    return [
        f"{'smaxfile':<21}= {SMAX_FILE}",
        f"{'sefffile':<21}= {SEFF_FILE}",
        f"{'ksfile':<21}= {KS_FILE}",
    ]


def read_meta(model_dir: Path | str) -> dict | None:
    p = Path(model_dir) / CNB_META
    return json.loads(p.read_text()) if p.is_file() else None
