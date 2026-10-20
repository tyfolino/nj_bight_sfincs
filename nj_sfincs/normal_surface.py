"""The USUAL surface a flood map's "water depth" is measured from (user, 2026-10-19).

A map of "depth" shows water level minus the surface that is normally there:

* on normally-dry land, the GROUND;
* on tidal water (ocean, bays, every v4 river — all are cut at today's head of tide), the
  normal high tide, **MHHW** (mean higher-high water, NTDE 1983–2001, metres NAVD88);
* on a non-tidal lake or pond, its normal POOL (the hydro-flattened lidar water surface).

Two rasters per domain carry the water part, both EPSG:32618, NaN where not defined, built
by ``scripts/build_normal_surface_v4.py`` (sources, sign convention and the CO-OPS station
check in ``data/normal_surface_<tag>/README.md``):

* ``mhhw_navd88_<tag>.tif`` — NOAA VDatum MHHW, extended ≤ 2 km onto land by nearest
  neighbour so the test "ground ≥ MHHW" works along every shore;
* ``lake_pool_<tag>.tif`` — the pool of each NON-tidal NHD lake/pond;
* ``water_mask_<tag>.tif`` — uint8, 1 = MAPPED water: an NHD river/stream/canal AREA
  polygon or any NHD lake/pond/reservoir (all_touched=False).

⭐ **Land-only convention (user, 2026-10-19): flood depth is drawn only on NORMALLY-DRY
land.** The ONE shared rule for "normally wet" is :func:`normally_wet`::

    in the water mask | a lake pool | (MHHW defined & ground < MHHW)
                      | (no MHHW & ground < 0 m NAVD88)

The water mask is there because "ground < MHHW" misses channels whose DEM holds the lidar
WATER SURFACE above MHHW — the Delaware above Trenton falls (water surface ~2 m against
MHHW 1.49 m), the Raritan up to Bound Brook — and would call them dry land under water.

The usual WATER surface is ``W = pool`` where a pool exists, else MHHW, else NaN; the usual
surface is ``max(ground, W)`` where W exists, else the ground. Where the ground stands above
W the place is normally dry and the ground wins; where it lies below, it is normally wet.

⚠️ The 2 km land extension is a nearest-neighbour fill, not a connectivity test: ground
BELOW MHHW behind a levee, dike or tide gate inside that band (the Salem diked marshes, the
Meadowlands, the Keansburg pocket) reads as normally wet, so its depth is shown above MHHW,
not above the ground.

Rasters are sampled through their affine (``~transform``), never ``x0 + col*res``
(CLAUDE.md §5, the rotated-raster trap).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from nj_sfincs import domain as _domain


def _dir(domain_name: str | None) -> Path:
    dom = _domain.DOMAINS[domain_name] if domain_name else _domain.active()
    if dom.normal_surface_dir is None:
        raise ValueError(
            f"domain {dom.name!r} has no normal_surface_dir — the usual-surface rasters "
            "were never built for it (scripts/build_normal_surface_v4.py)"
        )
    return Path(dom.normal_surface_dir)


def _tag(d: Path) -> str:
    return d.name.removeprefix("normal_surface_")


def mhhw_path(domain_name: str | None = None) -> Path:
    """MHHW [m NAVD88] raster for the domain (``NJ_DOMAIN`` when ``None``)."""
    d = _dir(domain_name)
    return d / f"mhhw_navd88_{_tag(d)}.tif"


def pool_path(domain_name: str | None = None) -> Path:
    """Non-tidal lake pool [m NAVD88] raster for the domain (``NJ_DOMAIN`` when ``None``)."""
    d = _dir(domain_name)
    return d / f"lake_pool_{_tag(d)}.tif"


def water_mask_path(domain_name: str | None = None) -> Path:
    """Mapped-water mask (uint8, 1 = NHD river/stream area or lake) for the domain."""
    d = _dir(domain_name)
    return d / f"water_mask_{_tag(d)}.tif"


def sample_raster(path: Path | str, x, y) -> np.ndarray:
    """Nearest-pixel value of band 1 at points (x, y) in the raster's CRS; NaN outside
    the raster or on nodata. Reads only the window that spans the points."""
    import rasterio
    from rasterio.windows import Window

    x = np.asarray(x, dtype="float64")
    y = np.asarray(y, dtype="float64")
    shape = np.broadcast_shapes(x.shape, y.shape)
    x, y = np.broadcast_to(x, shape).ravel(), np.broadcast_to(y, shape).ravel()
    out = np.full(x.shape, np.nan, dtype="float64")
    with rasterio.open(path) as src:
        col, row = ~src.transform @ (x, y)  # the affine, not x0 + col*res
        col = np.floor(col)
        row = np.floor(row)
        ok = (
            np.isfinite(col)
            & np.isfinite(row)
            & (col >= 0)
            & (row >= 0)
            & (col < src.width)
            & (row < src.height)
        )
        if ok.any():
            c = col[ok].astype("int64")
            r = row[ok].astype("int64")
            c0, r0 = int(c.min()), int(r.min())
            win = Window(c0, r0, int(c.max()) - c0 + 1, int(r.max()) - r0 + 1)
            a = src.read(1, window=win).astype("float64")
            if src.nodata is not None and not np.isnan(src.nodata):
                a[a == src.nodata] = np.nan
            out[ok] = a[r - r0, c - c0]
    return out.reshape(shape)


def usual_water_surface(x, y, domain_name: str | None = None) -> np.ndarray:
    """Per point (EPSG:32618 x, y) the usual WATER surface [m NAVD88]: the lake pool where
    one exists, else MHHW, else NaN."""
    pool = sample_raster(pool_path(domain_name), x, y)
    mhhw = sample_raster(mhhw_path(domain_name), x, y)
    return np.where(np.isfinite(pool), pool, mhhw)


def usual_surface(ground, W) -> np.ndarray:
    """The usual surface: the ground on normally-dry land, the water surface ``W`` on
    normally-wet ground (``max(ground, W)``); the ground wherever ``W`` is NaN."""
    ground = np.asarray(ground, dtype="float64")
    W = np.asarray(W, dtype="float64")
    return np.where(np.isfinite(W), np.maximum(ground, W), ground)


def rise_above_usual(water_level, ground, W) -> np.ndarray:
    """Water level minus the usual surface — the "water depth" every map shows."""
    return np.asarray(water_level, dtype="float64") - usual_surface(ground, W)


def normally_wet(x, y, ground, domain_name: str | None = None) -> np.ndarray:
    """Per point (EPSG:32618 x, y; ``ground`` in m NAVD88, broadcast against them): is
    this place NORMALLY WET? True when it is mapped water (NHD river area or lake), has a
    lake pool, sits below MHHW where MHHW is defined, or below 0 m NAVD88 where it is
    not. NaN ground counts as wet only through the mask or a pool. THE shared rule for
    the land-only depth maps: draw depth where ``normally_dry``."""
    ground = np.asarray(ground, dtype="float64")
    mask = sample_raster(water_mask_path(domain_name), x, y) == 1
    pool = np.isfinite(sample_raster(pool_path(domain_name), x, y))
    mhhw = sample_raster(mhhw_path(domain_name), x, y)
    has = np.isfinite(mhhw)
    with np.errstate(invalid="ignore"):
        low = np.where(has, ground < mhhw, ground < 0.0)
    return mask | pool | low


def normally_dry(x, y, ground, domain_name: str | None = None) -> np.ndarray:
    """``~normally_wet`` — where the land-only maps draw flood depth."""
    return ~normally_wet(x, y, ground, domain_name)
