# Hurricane Sandy (2012) maximum flood depth — New Jersey coast, model v4_refreeze_swz

`sandy_hmax_v4_refreeze_swz_p4-premier_EPSG32618.tif`

Modelled maximum water depth during Hurricane Sandy (28–31 Oct 2012) over the New
Jersey coast and its tidal waters — the ocean coast from Cape May to the Verrazzano
Narrows with its back bays; Lower, Raritan and Sandy Hook Bays; the Arthur Kill and
Newark Bay; the tidal Raritan; and Delaware Bay with the tidal Delaware River. The far
shores (Delaware, Pennsylvania, Staten Island) are computed as part of those waters.
SFINCS compound-flood hindcast: storm surge, wave setup, wind, rain and river
discharge together. **This is a working dataset from a model still under development,
not a validated hazard layer** — read the caveats before drawing any conclusion from it.

Model run: domain `v4_refreeze_swz`, experiment `p4-premier`, exported 2026-10-30.

## Reading the file

| | |
|---|---|
| Format | GeoTIFF, single band, float32, DEFLATE-compressed, tiled, with overviews |
| **CRS** | **EPSG:32618** — UTM zone 18N, coordinates in **metres**, *not* degrees |
| Resolution | 6.249 m |
| Size | 29960 x 40168 px, 313 MB |
| NoData | NaN (tagged in the header) — dry land, permanent water, and ground outside the model |
| Units | metres of water depth above the ground surface |

The CRS is the one thing most likely to trip you up. Opening this expecting lat/lon
gives corner coordinates like `501136, 4497255`; that is not corruption, it is UTM in
metres. QGIS, ArcGIS and rasterio all reproject on the fly. If you need degrees
(EPSG:4326) say so and I will ship a reprojected copy — better that than resampling
depths yourself.

Extent: `(438968.4, 4285228.6, 626194.0, 4536245.9)` in UTM, which is `(-75.7254, 38.7067, -73.5003, 40.9774)` as (west, south, east, north) in degrees.

```python
import rioxarray
da = rioxarray.open_rasterio("sandy_hmax_v4_refreeze_swz_p4-premier_EPSG32618.tif", masked=True).squeeze()
da = da.where(da >= 0.15)          # see "wet threshold" below
# da.rio.reproject("EPSG:4326")    # only if you actually need degrees
```

The file has overviews, so it opens instantly in QGIS at any zoom. Reading the full
band into memory takes about 4.8 GB.

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
  (0.1 km²) have been removed.

Wet cells: 57,796,126 (2257 km², 4.80% of the grid rectangle);
depth range 0.05 to 15.15 m. At or above the 0.15 m threshold:
53,880,079 cells (2104 km²), median depth 1.16 m, 99th percentile
3.19 m.

### Wet threshold

The raster floor is **0.05 m** (an artifact of how the downscale is built). Our own
scoring treats a cell as wet only at **>= 0.15 m**. Below that you are looking at
numerical damp rather than flooding, and most damage curves will happily assign losses
to it. **Threshold at 0.15 m** unless you have a specific reason not to. The 0.05 m
values are left in rather than silently deleted, so the choice stays yours.

## How good is it?

- **High-water marks:** 110 USGS marks scored; bias **-0.13 m**, RMSE 0.44 m (median estimator, 50 m search radius — the bias depends on both, so always quote them with it).
- **FEMA flood extent (MOTF):** critical success index 0.78, probability of detection 0.85, false-alarm ratio 0.09. The FEMA layer covers New Jersey only; 2413 km² of New York shore is excluded from the score.
- Waves on; solver build `bin:v2.3.3-winddir-igk-igseed-wmseed-1-gf11@e15ed916`.

## Caveats — please read before trusting a number

1. **Known low bias.** Against surveyed USGS high-water marks this run reads low on
   average (numbers above). Damages computed from it will be *under*-estimates, and
   non-linearly so, because damage curves are steep near the low end.
2. **Hindcast, not a design event.** This is one storm reconstructed after the fact.
   It is not a return-period product and must not be read as one.
3. **Where it is weakest.** A few places are known to read low against surveyed marks:
   the Monmouth County coastal lakes (Deal Lake, Wreck Pond and their neighbours) by
   about 0.7–2.3 m — in Sandy they filled through dune breaches and overwash that the
   model reproduces only in part, so treat depths around them as a floor — and Cape
   May's back bays by about 0.3 m. Delaware Bay and the tidal Delaware are checked
   against only three marks: the least-tested part of the map. Raritan Bay, Sandy Hook
   Bay and the Arthur Kill, weak in earlier versions, now score like the ocean coast.
4. **Outside New Jersey, and upriver, is out of scope.** The Staten Island, Brooklyn,
   Delaware and Pennsylvania shores are in the grid so the bays and rivers behave
   correctly, but the FEMA extent the model is scored against is New Jersey only, so
   flooding there is unchecked. Each river stops at its present-day head of tide (the
   Cohansey and Neshaminy reach a little further); ground upstream is not modelled.
   **The Hudson waterfront and the Upper Bay shore are outside the model:** Hoboken, the
   east side of Jersey City and Bayonne's Upper Bay side are blank because they were not
   simulated, NOT because they stayed dry. Sandy flooded them badly, so exclude them from
   any damage total rather than counting them as undamaged.
5. **Depth only.** No velocity, no duration, no wave runup on the beach face, no
   debris — all of which matter for real damage estimation.
6. **Buildings are burned into the terrain** (footprints raised), so depths inside
   footprints are NaN or shallow by construction; read depth at the building's
   perimeter, not its centroid. **A FIAT run reading depth at the building will score
   most flooded buildings as undamaged** (97% of the footprint pixels wet on the bare-ground
   map are blank here), so a damage drop against that map is mostly this blank-map effect.
   Both maps share one water surface: comparing them does not test a change to the model's
   bed; that takes two runs with different beds, read with the same depth method. A few cells beside large buildings are too deep: rain on
   a roof drains into the sliver of ground left in that model cell (up to ~15 m near Port
   Newark, ~10 m in Atlantic City). They are kept here as the model has them; the bare-ground map drops them.

Comparing this map with its sibling (`..._bareground_...` / the plain `..._p4-premier_...`):
the same water, so depths match exactly off the footprints. About 7.5 km² of each map's
wet ground is blank in the other: a thin shoreline strip where the permanent-water cutoff
(ground near -0.5 m) falls on different pixels. It is not a flood difference; ignore it.

Questions to Ty.
