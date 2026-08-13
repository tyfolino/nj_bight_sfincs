"""Build parameters for the NJ Bight SFINCS model.

Two frozen dataclasses:

* ``BaseConfig`` — everything INVARIANT across the experiments (paths, grid, subgrid,
  elevation merge, simulation window, the water-level boundary source).
* ``WaveConfig`` — the SnapWave knobs, which is most of what an experiment varies.

``Experiment`` binds a name to a set of knobs. The experiment LIBRARY lives in
``experiments.py`` and is keyed by domain — see the module docstring there for why a flat
namespace was wrong.

Paths resolve against the repo root, overridable with ``NJ_ROOT``, so the CLI and a
notebook work regardless of CWD. ``nj_sfincs/__init__.py`` asserts that ``NJ_ROOT``, when
set, is this package's OWN parent.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path

ROOT = Path(os.environ.get("NJ_ROOT", Path(__file__).resolve().parents[1]))
DATA = ROOT / "data"

from . import domain as _domain  # noqa: E402  (geography registry; see domain.py)


def exp_root() -> Path:
    """``experiments/<domain>`` — the run tree for the ACTIVE domain.

    Experiment names are domain-relative on purpose: ``naccs-premier`` and
    ``_template_sealed`` name the same *configuration* on every domain, so the same name
    exists once per domain and means a different model each time. Before this split they
    lived in one flat ``experiments/``, where a merge would have silently destroyed one of
    them.

    A function, not a module constant, because ``NJ_DOMAIN`` is read at call time — a
    constant would freeze whichever domain happened to be active at import.
    """
    return ROOT / "experiments" / _domain.active().name


# Elevation merge, top → bottom; first dataset with data wins.
#
# ⚠️ ORDER IS THE WHOLE POINT. The eHydro tiers MUST outrank `usace_nj_2010`. The 2010
# lidar is green (bathymetric) and returns the real bed in clear shallow water — but in
# deep or turbid water it fails to penetrate and returns the WATER SURFACE (~0 to +2 m),
# which is indistinguishable from land. Ranked first, those bogus returns shadow CUDEM's
# correct bed and SEAL THE CHANNEL SHUT. That is what dammed Shark River Inlet (real bed
# −4.6 to −10.8 m; lidar +0.4 to +2.2 m) and left the whole Shark estuary at exactly
# +0.00 m — never flooding — through Hurricane Sandy. An eHydro survey is a boat with an
# echo sounder: the only source here that measures the bed UNDER the water, so it goes on
# top. See data/data_catalog.yml for per-layer provenance.
#
# ⚠️ `nj_10ft_dem` IS NEW-JERSEY-ONLY. Any domain reaching Staten Island, the Narrows or
# the Rockaway shore falls through it to CUDEM/3DEP there. `build_static` asserts no
# active cell has NoData in the merged bed, which is what turns that from a silent hole
# into a build error.
DEFAULT_ELEVATION_LIST: tuple[dict, ...] = (
    {"elevation": "ehydro_nj"},
    {"elevation": "shrewsbury_ehydro_2015"},
    {"elevation": "usace_nj_2010"},  # 1 m PRE-Sandy topobathy (fails in deep/turbid water)
    {"elevation": "cudem_nj"},  # 3 m fill: inlets + shelf + Raritan Bay
    {"elevation": "nj_10ft_dem", "zmin": 0.001},  # 3 m fill: inland land, NJ ONLY
    {"elevation": "cudem13_nj"},  # ~10 m fill: nearshore ocean the 1/9" product never tiled
    {"elevation": "gmrt_nj"},  # ~50 m GMRT offshore tail
)


@dataclass(frozen=True)
class BaseConfig:
    """Forcing-independent build parameters (shared by every experiment)."""

    # ── Paths ────────────────────────────────────────────────────────────────
    data_catalog: Path = DATA / "data_catalog.yml"
    domain: str = field(default_factory=lambda: _domain.active().name)
    region: Path = field(default_factory=lambda: _domain.active().region)
    refinement: Path | None = field(
        default_factory=lambda: (
            (ROOT / os.environ["NJ_REFINEMENT"])
            if os.environ.get("NJ_REFINEMENT")
            else _domain.active().refinement
        )
    )
    reclass_table: Path = DATA / "roughness" / "NLCD_CONUS_mapping.csv"
    # The land-cover raster the roughness + subgrid tables are reclassified from. A knob
    # rather than a literal in model.py so a bed-roughness arm can swap in a recoded
    # raster.
    # ⚠️ Roughness feeds `quadtree_subgrid.create`, so changing it requires a TEMPLATE
    # REBUILD — it is NOT a `prepare_experiment` swap like `waterlevel_geodataset`. The
    # domain seal is sha(z, mask) and does NOT include roughness, so a rebuilt template
    # still audits as the same domain. That is the point: comparable by construction.
    roughness_lulc: str = "nlcd_2012"
    container_sif: Path = ROOT / "sfincs-desktop.sif"

    # Reproducibility: if set to a pre-built static-mesh dir, build_static COPIES it
    # instead of rebuilding the quadtree (which is environment-sensitive — two builds of
    # identical code can differ by ~18 cells, worth ~0.04 of CSI). Keyed on the domain's
    # `mesh_key`, so the wrong mesh cannot be selected by omission; at worst the path does
    # not exist yet and build_static says so.
    #
    # ⚠️ TWO DOMAINS SHARE A MESH when they differ only in `mask_zmin` (see
    # Domain.mesh_key). The mask is re-derived on a COPY and the subgrid tables are
    # reused — every face already has them — so the boundary-depth pair costs no rebuild.
    frozen_mesh: Path | None = field(
        default_factory=lambda: (
            (ROOT / os.environ["NJ_FROZEN_MESH"])
            if os.environ.get("NJ_FROZEN_MESH")
            else _domain.active().frozen_mesh_dir()
        )
    )

    # ── Grid ─────────────────────────────────────────────────────────────────
    crs: str = "utm"  # let hydromt pick the UTM zone (→ 32618 here)
    base_res: int = 200  # level-0 cell size [m]; refined down to ~25 m
    rotated: bool = True  # rotate the grid to hug the coastline

    # ── Subgrid / mask ───────────────────────────────────────────────────────
    nr_subgrid_pixels: int = 8  # subgrid sampling per cell edge

    #: 🔴 READ FROM THE DOMAIN, not set here. `mask_zmin` is half of `sha(z, mask)` — the
    #: domain fingerprint — so an "arm" that changed it would fail `assert_sealed_domain`
    #: on its own staged copy. Boundary depth is a DOMAIN axis; see Domain.mask_zmin.
    mask_zmin: float = field(default_factory=lambda: _domain.active().mask_zmin)

    # ── Elevation merge ──────────────────────────────────────────────────────
    elevation_list: tuple[dict, ...] = DEFAULT_ELEVATION_LIST

    # ── Simulation window (Hurricane Sandy) ──────────────────────────────────
    tref: datetime = datetime(2012, 10, 28)
    tstart: datetime = datetime(2012, 10, 28)
    tstop: datetime = datetime(2012, 10, 31)
    latitude: float = field(default_factory=lambda: _domain.active().latitude)

    # ── Water-level boundary ─────────────────────────────────────────────────
    waterlevel_geodataset: str = "noaa_sandy_nj"
    waterlevel_buffer: int = field(
        default_factory=lambda: _domain.active().waterlevel_buffer
    )

    @property
    def data_libs(self) -> list[str]:
        return [str(self.data_catalog)]

    def elevation(self) -> list[dict]:
        """A fresh mutable copy of the elevation list for the hydromt API."""
        return [dict(d) for d in self.elevation_list]


@dataclass(frozen=True)
class WaveConfig:
    """The SnapWave knobs.

    Atlantic swell cannot diffract into a bay lee, so bay waves have to be *generated*
    there: via local wind-wave growth (``wave_wind``) or injected as infragravity energy
    (``wave_igwaves`` / ``wavemaker``).
    """

    use_waves: bool = False
    wave_wind: bool = False  # local wind-wave growth (routes model wind; sector→360)
    wave_igwaves: bool = False  # infragravity balance (long-period back-bay runup)
    wavemaker: bool = False  # inject waves along the ocean-side wavemaker line

    # Wave boundary forcing (ERA5-coupled support points)
    wave_geodataset: str = "era5_waves_nj"
    wave_era5_node: tuple[float, float] = (-74.0, 40.0)  # nearest valid offshore node
    wave_n_support: int = 7  # alongshore support points on the boundary

    # ── Per-support-point wave forcing ───────────────────────────────────────
    # When set, the wave boundary is read from an UNSTRUCTURED POINT file — dims
    # (time, node) with lon/lat/depth coords — and every support point gets its own
    # NEAREST node instead of one node broadcast alongshore.
    #
    # ⭐ SETTLED, and the reason this field exists. The ERA5 path CANNOT express
    # alongshore structure: a 31 km ERA5 cell cannot resolve a 25 km boundary, so all 7
    # support points receive byte-identical Hs. Worse, it is physically inadmissible at
    # the boundary depth — measured, ERA5 imposes 8.624 m in ~9.9 m of water
    # (gamma 0.86–0.89, ABOVE the 0.78 depth-limited breaking cap) at 7 of 7 points, while
    # CORA's shelf-resolving SWAN imposes 4.98–6.11 m there (gamma 0.50–0.63, admissible)
    # with 1.14 m of alongshore spread. CORA is the adopted wave boundary.
    #
    # ⚠️ CORA is not a gold standard: against NDBC 44025 at the buoy's own location and
    # depth it runs +0.49 m HIGH. That cuts in its favour rather than against it — biased
    # high offshore and STILL only asking ~5–6 m at the 10 m contour means the reduction
    # is shelf transformation, not a low source. Quote the direction, not the value.
    #
    # Path rather than a catalog key on purpose: hydromt's RasterDataset/GeoDataset drivers
    # do not describe an unstructured ADCIRC/SWAN node set.
    wave_point_dataset: Path | None = None

    # ── SnapWave / SFINCS boundary DECOUPLING ────────────────────────────────
    # Sharing the SFINCS mesh pins the wave boundary to the WATER-LEVEL boundary at
    # `Domain.mask_zmin`. Setting `decouple_snapwave` lets the SnapWave mask run out to
    # `snapwave_mask_zmin` while the SFINCS mask (and therefore the tide/surge boundary)
    # stays exactly where it is. Seal-safe: premier.py deliberately EXCLUDES snapwave_mask
    # from the domain hash, so only one variable moves.
    decouple_snapwave: bool = False
    snapwave_mask_zmin: float = -30.0  # SnapWave-only depth cut [m]
    wavemaker_line: Path = DATA / "wavemakers" / "wavemaker_line.geojson"
    dtwave: float = 1800.0  # SnapWave coupling interval [s]

    # SnapWave physics parameters. Only emitted when ``tune_physics`` is True.
    tune_physics: bool = False
    snapwave_alpha: float = 1.0  # Baldock breaking alpha
    snapwave_gamma: float = 0.78  # Baldock breaking gamma (breaking depth)
    snapwave_hmin: float = 0.01  # min water depth for SnapWave [m]
    snapwave_dtheta: int = 5  # direction bin size [deg]
    snapwave_fw: float = 0.02  # wave bottom-friction factor
    snapwave_niter: int = 100  # max iterations (÷4 internal sweeps)
    storefw: int = 1  # store extra wave output

    def sector(self) -> int:
        """Directional sector: full circle when wind can grow waves any way."""
        return 360 if self.wave_wind else 180


@dataclass(frozen=True)
class Experiment:
    """A named experiment = a label + the knobs to apply to a staged template.

    ``waterlevel_geodataset`` optionally OVERRIDES the base water-level forcing source for
    this experiment only (``None`` = inherit ``BaseConfig``). The override is applied on
    the copied template by re-running ``sf.water_level.create(..., merge=False)`` —
    everything else (mask, subgrid, waves) is identical, so a set of experiments differing
    only in this field is a clean forcing A/B.
    """

    name: str
    waves: WaveConfig
    description: str = ""
    waterlevel_geodataset: str | None = None

    #: Number of water-level support points THIS arm expects, overriding
    #: ``Domain.n_waterlevel_support`` for this arm only. Leave ``None`` unless the arm's
    #: whole point is a different node count.
    #: ⚠️ Never fix a support-point assertion by relaxing the DOMAIN value: that invariant
    #: guards every arm on the domain, and an unintended extra node is silent by nature
    #: (it cost one retired arm +0.18 m of HWM bias). Declaring it here keeps the count
    #: visible next to the arm's description. See ``model.check_waterlevel_support``.
    n_waterlevel_support: int | None = None

    #: BRACKET ONLY. Key into ``premier.BRACKETS``. A bracket is a DELIBERATELY
    #: INADMISSIBLE domain built to BOUND a quantity — never a candidate configuration.
    #: Setting this makes the runner refuse to stage it without ``NJ_ALLOW_BRACKET``,
    #: excludes it from ``--experiments all``, and keeps its metrics out of metrics.csv.
    bracket: str | None = None


def with_window(base: BaseConfig, tstop: datetime) -> BaseConfig:
    """Return a copy of ``base`` with a shorter run window (for smoke tests)."""
    return replace(base, tstop=tstop)
