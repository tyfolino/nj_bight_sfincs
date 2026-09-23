# Hurricane Sandy (2012) maximum flood depth — New Jersey coast, model v3

`sandy_hmax_v3_mask-drain-edge_naccs-premier_EPSG32618.tif`

Modelled maximum water depth during Hurricane Sandy (28–31 Oct 2012) over the whole
New Jersey ocean coast — Cape May to Raritan Bay and the Verrazzano Narrows, including
the back bays, the Delaware Bay shore near Cape May, and the Staten Island shore of
Lower Bay. SFINCS compound-flood hindcast: storm surge, wave setup, wind, rain and river
discharge together. **This is a working dataset from a model still under development,
not a validated hazard layer** — read the caveats before drawing any conclusion from it.

Model run: domain `v3`, experiment `mask-drain-edge+naccs-premier`, exported 2026-09-23.

## Reading the file

| | |
|---|---|
| Format | GeoTIFF, single band, float32, DEFLATE-compressed, tiled, with overviews |
| **CRS** | **EPSG:32618 (EPSG:32618)** — UTM zone 18N, coordinates in **metres**, *not* degrees |
| Resolution | 6.249 m |
| Size | 19972 x 31012 px, 149 MB |
| NoData | NaN (tagged in the header) — dry land, permanent water, and ground outside the model |
| Units | metres of water depth above the ground surface |

The CRS is the one thing most likely to trip you up. Opening this expecting lat/lon
gives corner coordinates like `501136, 4497255`; that is not corruption, it is UTM in
metres. QGIS, ArcGIS and rasterio all reproject on the fly. If you need degrees
(EPSG:4326) say so and I will ship a reprojected copy — better that than resampling
depths yourself.

Extent: `(501136.3, 4303449.7, 625948.6, 4497255.0)` in UTM, which is `(-74.9869, 38.8709, -73.511, 40.6261)` as (west, south, east, north) in degrees.

```python
import rioxarray
da = rioxarray.open_rasterio("sandy_hmax_v3_mask-drain-edge_naccs-premier_EPSG32618.tif", masked=True).squeeze()
da = da.where(da >= 0.15)          # see "wet threshold" below
# da.rio.reproject("EPSG:4326")    # only if you actually need degrees
```

The file has overviews, so it opens instantly in QGIS at any zoom. Reading the full
band into memory takes about 2.5 GB.

## What the values mean

- **Depth above ground**, not water-surface elevation. No datum conversion needed to
  use it as depth; it is already ground-relative.
- **Maximum over the whole storm**, not a snapshot. Different cells peak at different
  times, so the map is not a state the system was ever in at one instant. That is
  normally what a damage model wants, but it is worth knowing.
- **Permanent water is masked out.** Bay, river and ocean cells are NaN, so the raster
  shows flooding on land rather than the full water column.
- **Only ground the model actually simulated is kept.** The downscaling step paints
  water onto low ground just outside the model's active cells; those cells
  (0.0 km²) have been removed.

Wet cells: 26,628,412 (1040 km², 4.30% of the grid rectangle);
depth range 0.05 to 11.97 m. At or above the 0.15 m threshold:
24,529,789 cells (958 km²), median depth 1.21 m, 99th percentile
2.96 m.

### Wet threshold

The raster floor is **0.05 m** (an artifact of how the downscale is built). Our own
scoring treats a cell as wet only at **>= 0.15 m**. Below that you are looking at
numerical damp rather than flooding, and most damage curves will happily assign losses
to it. **Threshold at 0.15 m** unless you have a specific reason not to. The 0.05 m
values are left in rather than silently deleted, so the choice stays yours.

## How good is it?

- **High-water marks:** 94 USGS marks scored; bias **-0.15 m**, RMSE 0.37 m (median estimator, 50 m search radius — the bias depends on both, so always quote them with it).
- **FEMA flood extent (MOTF):** critical success index 0.71, probability of detection 0.88, false-alarm ratio 0.22. The FEMA layer covers New Jersey only; 14 km² of New York shore is excluded from the score.
- Waves on; solver build `bin:v2.3.3-winddir-fix-1-gf11@673ee3bf`.

## Caveats — please read before trusting a number

1. **Known low bias.** Against surveyed USGS high-water marks this run reads low on
   average (numbers above). Damages computed from it will be *under*-estimates, and
   non-linearly so, because damage curves are steep near the low end.
2. **Hindcast, not a design event.** This is one storm reconstructed after the fact.
   It is not a return-period product and must not be read as one.
3. **Model still in development.** A revised version of this run (a fix to how the
   model's northern edge on Staten Island drains) is finishing now and will raise
   depths around Raritan Bay and the Arthur Kill by roughly 0.1–0.3 m; the New Jersey
   ocean coast and back bays south of Sandy Hook are unaffected. Ask for the refreshed
   file if you are working north of Sandy Hook.
4. **New York land is out of scope.** The Staten Island and Brooklyn shorelines are
   in the grid only as the model's northern edge; do not read flooding there as a
   result. Jamaica Bay and Manhattan are not modelled at all.
5. **Depth only.** No velocity, no duration, no wave runup on the beach face, no
   debris — all of which matter for real damage estimation.
6. **Buildings are burned into the terrain** (footprints raised), so depths inside
   footprints are NaN or shallow by construction; read depth at the building's
   perimeter, not its centroid.

Questions to Ty.
