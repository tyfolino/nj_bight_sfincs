"""The floodmap is downscaled on the subgrid DEM's NATIVE resolution, not its overview.

WHY THIS EXISTS (confirmed 2026-11-09, fixed 2026-11-12)
-------------------------------------------------------
hydromt's ``downscale_floodmap``, given the dep as a PATH, opens it with
``rasterio.open(dep, overview_level=0)``. In rasterio / GDAL that is the FIRST OVERVIEW,
not the base band. Our subgrid DEMs carry ``average`` overviews, so every floodmap (and
every MOTF / HWM score read off it) sat on a 2x-coarser bed that averaged building
footprints into the streets beside them: on v4, 6.25 m instead of 3.125 m, Lavallette
street pixels at 6.24 m of "ground" over a 1.25 m bed (``logs/crests_2026-11-09/``).

``validate.core.downscale_floodmap_native`` keeps hydromt's block loop and per-block
arithmetic and reads the base band. These tests pin, on a small ROTATED synthetic DEM with
average overviews (the v4 frame is rotated, CLAUDE.md §5):

* the output is on the DEM's own lattice (shape AND affine);
* a street pixel between two "buildings" reads ``zsmax - street bed``, a building pixel
  reads dry — the property the overview read broke;
* it equals hydromt's own DataArray-mode downscale on the whole in-memory DEM (same
  semantics; the block loop changes nothing), with blocks small enough to exercise the
  merged last row / column;
* ``floodmap_is_native`` calls a first-overview floodmap stale, and the pre-fix cache is
  moved aside, never deleted;
* the upstream behaviour itself (a canary: if hydromt fixes it, this test says so).
"""

import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio
import xarray as xr
import xugrid as xu
from affine import Affine
from rasterio.enums import Resampling

import nj_sfincs  # noqa: F401  (pyproj before hydromt_sfincs)
from nj_sfincs.validate import core

#: synthetic DEM: 1 m pixels, rotated 0.8 deg like the v4 subgrid frame
NY, NX, RES, ROT = 81, 97, 1.0, 0.8
X0, Y0 = 500_000.0, 4_400_000.0
STREET_Z, BUILDING_Z, ZS = 0.5, 6.0, 1.5


def _dep_array():
    """Streets at 0.5 m; 1-pixel-wide 'buildings' at 6 m on every other column.

    Average overviews (2x) blend each street pixel with a building pixel: 3.25 m, above
    the 1.5 m water — so the overview read calls every street DRY.
    """
    z = np.full((NY, NX), STREET_Z, dtype=np.float32)
    z[:, 1::2] = BUILDING_Z
    z[:3, :] = np.nan  # a nodata strip, as the real rectangle has
    return z


def _transform():
    # the subgrid frame's own convention (v1_monmouth, v4): rows run NORTH (e > 0), with
    # b = -d = -sin(rot). (With e < 0 and d < 0, rioxarray's de-rotation of this small
    # raster came back empty for BOTH read paths — a synthetic-frame artefact, not ours.)
    return Affine.translation(X0, Y0) * Affine.rotation(ROT) * Affine.scale(RES, RES)


def _write_dep(path: Path):
    prof = dict(
        driver="GTiff",
        width=NX,
        height=NY,
        count=1,
        dtype="float32",
        crs="EPSG:32618",
        transform=_transform(),
        nodata=np.nan,
        tiled=True,
        blockxsize=16,
        blockysize=16,
    )
    with rasterio.open(path, "w", **prof) as d:
        d.write(_dep_array(), 1)
    with rasterio.open(path, "r+") as d:  # as build_merged_subgrid_dep.py does
        d.build_overviews([2, 4], Resampling.average)


def _zsmax(varying=False):
    """A coarse (8 m) north-up face grid over the DEM with a flat 1.5 m peak level,
    as a UgridDataArray — what ``mod.output.data['zsmax']`` is on a quadtree run.

    ``varying``: a different level on every face (so a wrong face lookup shows) and a
    block of NaN faces (inactive), float32 like the map file."""
    xs = X0 - 40 + 8 * (np.arange(30) + 0.5)
    ys = Y0 - 40 + 8 * (np.arange(30) + 0.5)
    z = np.full((30, 30), ZS)
    if varying:
        z = ZS + 0.37 * np.sin(np.arange(900.0)).reshape(30, 30)
        z[12:16, 5:9] = np.nan
    da = xr.DataArray(z.astype(np.float32), dims=("y", "x"), coords={"y": ys, "x": xs})
    return xu.UgridDataArray.from_structured(da)


class TestFloodmapNative(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.dep = self.d / "dep_subgrid_merged.tif"
        _write_dep(self.dep)
        self.zs = _zsmax()

    def tearDown(self):
        self.tmp.cleanup()

    def _native(self, nrmax=1000, name="fm.tif"):
        out = self.d / name
        core.downscale_floodmap_native(self.zs, self.dep, out, hmin=0.05, nrmax=nrmax)
        return out

    def test_output_on_the_dem_lattice(self):
        out = self._native()
        with rasterio.open(out) as f, rasterio.open(self.dep) as d:
            self.assertEqual(f.shape, d.shape)
            self.assertEqual(f.shape, (NY, NX))
            self.assertTrue(f.transform.almost_equals(d.transform))
            self.assertAlmostEqual(abs(f.res[0]), RES, places=9)
        self.assertTrue(core.floodmap_is_native(out, self.dep))

    def test_streets_wet_buildings_dry(self):
        with rasterio.open(self._native()) as f:
            h = f.read(1)
        inner = (slice(10, NY - 10), slice(10, NX - 10))  # well inside the face grid
        streets, blds = h[inner][:, 0::2], h[inner][:, 1::2]
        np.testing.assert_allclose(streets, ZS - STREET_Z, rtol=0, atol=1e-6)
        self.assertTrue(np.isnan(blds).all())
        self.assertTrue(np.isnan(h[:3]).all(), "dep nodata stays nodata")

    def test_equals_hydromt_dataarray_mode_with_small_blocks(self):
        # 81 = 5*16 + 1 and 97 = 6*16 + 1: both merge-last rules fire. A different
        # level on every face, and NaN (inactive) faces, so a wrong lookup shows.
        self.zs = _zsmax(varying=True)
        got = {}
        for method in ("locate", "hydromt"):
            out = self.d / f"fm16_{method}.tif"
            core.downscale_floodmap_native(
                self.zs, self.dep, out, hmin=0.05, nrmax=16, method=method
            )
            with rasterio.open(out) as f:
                got[method] = f.read(1)
        T = _transform()
        cols, rows = np.meshgrid(np.arange(NX), np.arange(NY))
        xc, yc = T * (cols + 0.5, rows + 0.5)
        dep = xr.DataArray(
            _dep_array(),
            dims=("y", "x"),
            coords={"yc": (("y", "x"), yc), "xc": (("y", "x"), xc)},
        )
        dep.raster.set_crs(32618)
        want = core.utils.downscale_floodmap(zsmax=self.zs, dep=dep, hmin=0.05).values
        self.assertGreater(np.isfinite(want).sum(), 1000)
        self.assertGreater(np.unique(want[np.isfinite(want)]).size, 50)
        for method, g in got.items():
            with self.subTest(method=method):
                np.testing.assert_array_equal(np.isnan(g), np.isnan(want))
                np.testing.assert_array_equal(g, want)  # bit for bit, NaN == NaN

    def test_open_north_up_equals_rioxarray_default(self):
        """``load_floodmap``'s low-memory de-rotation: same values, coords, transform."""
        import rioxarray

        fm = self._native()
        a = rioxarray.open_rasterio(fm, masked=True).squeeze(drop=True)
        a = a.rio.reproject(a.rio.crs)
        b = core._open_north_up(fm)
        d_a = rioxarray.open_rasterio(self.dep, masked=True).squeeze(drop=True)
        d_a = d_a.rio.reproject_match(a)
        d_b = core._open_north_up(self.dep, match=b)
        for x, y in ((a, b), (d_a, d_b)):
            np.testing.assert_array_equal(x.values, y.values)
            np.testing.assert_array_equal(x["x"].values, y["x"].values)
            np.testing.assert_array_equal(x["y"].values, y["y"].values)
            self.assertEqual(tuple(x.rio.transform()), tuple(y.rio.transform()))
            self.assertEqual(x.dtype, y.dtype)
        self.assertTrue(np.isfinite(b.values).any())

    def test_first_overview_floodmap_is_stale_and_kept(self):
        # what hydromt's path mode writes: the dep's first overview lattice
        hyd = self.d / "floodmap_hmax_lev3.tif"
        core.utils.downscale_floodmap(
            zsmax=self.zs, dep=str(self.dep), hmin=0.05, floodmap_fn=str(hyd)
        )
        self.assertFalse(core.floodmap_is_native(hyd, self.dep))
        aside = core._move_aside_pre_native(hyd)
        self.assertEqual(aside.name, "floodmap_hmax_lev3.pre_native.tif")
        self.assertTrue(aside.is_file())
        self.assertFalse(hyd.exists())
        # a second pre-fix cache never overwrites the first
        hyd.write_bytes(b"x")
        aside2 = core._move_aside_pre_native(hyd)
        self.assertNotEqual(aside2, aside)
        self.assertTrue(aside.is_file() and aside2.is_file())

    def test_canary_hydromt_path_mode_reads_the_first_overview(self):
        """If this FAILS, hydromt changed ``overview_level=0`` upstream: re-check whether
        ``downscale_floodmap_native`` is still needed (the other tests stand either way)."""
        hyd = self.d / "hyd.tif"
        core.utils.downscale_floodmap(
            zsmax=self.zs, dep=str(self.dep), hmin=0.05, floodmap_fn=str(hyd)
        )
        with rasterio.open(hyd) as f, rasterio.open(self.dep) as d:
            self.assertEqual(d.overviews(1)[0], 2)
            self.assertEqual(f.shape, ((NY + 1) // 2, (NX + 1) // 2))
            h = f.read(1)
        # and on that lattice the averaged bed (3.25 m) hides every interior street: dry
        self.assertTrue(np.isnan(h[5:-5, 5:-5]).all())


if __name__ == "__main__":
    unittest.main()
