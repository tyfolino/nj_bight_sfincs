# Hurricane Sandy (2012) on today's ground — maximum flood depth — New Jersey coast, model v4_refreeze_swz_v11

`sandy_hmax_v4_refreeze_swz_v11_bed2026_bareground_EPSG32618.tif`

Modelled maximum water depth during Hurricane Sandy (28–31 Oct 2012) over the New
Jersey coast and its tidal waters — the ocean coast from Cape May to the Verrazzano
Narrows with its back bays; Lower, Raritan and Sandy Hook Bays; the Arthur Kill and
Newark Bay; the tidal Raritan; and Delaware Bay with the tidal Delaware River. The far
shores (Delaware, Pennsylvania, Staten Island) are computed as part of those waters.
SFINCS compound-flood model: storm surge, wave setup, wind, rain and river discharge
together. **This is a what-if, not a hindcast:** Sandy's 2012 weather, tides and rivers
are replayed over the ESTIMATED PRESENT-DAY (2026) terrain — 2023–25 lidar on land, the
latest channel surveys and today's bridge openings. The buildings and land cover inside
the model run are still the 2012-era ones (no complete modern set existed for the run);
the depth here is measured from bare 2026 ground with buildings removed. **This is a PRELIMINARY working dataset from a model still under
development, not a validated hazard layer** — read the caveats before drawing any
conclusion from it.

Model run: domain `v4_refreeze_swz_v11`, experiment `bed-modernb+p4-premier+struct-pews-checkvalve+weir-elizabeth-rahway+weir-portmonmouth`, exported 2026-11-13.

| | |
|---|---|
| Model version | Model 1.1.0's setup on the estimated 2026 terrain (its "2026 bed" twin; also the Port Monmouth gate + PEWS check valve) — not a tagged release |
| Ground (terrain) | estimated 2026 (today's) terrain, `_subgrid_modern2026b`, with the building burn REMOVED (`_subgrid_modern2026b_nobuildings`) |
| Depth measured from | **bare ground** (buildings removed) — read at a building's centroid |
| Resolution | 3.125 m, the model's native sub-grid terrain pixel (north-up, not rotated) |
| NaN means | dry, permanent water, or ground the model did not simulate |
| Status | **Preliminary** |

## Reading the file

| | |
|---|---|
| Format | GeoTIFF, single band, float32, DEFLATE-compressed, tiled, with overviews |
| **CRS** | **EPSG:32618** — UTM zone 18N, coordinates in **metres**, *not* degrees |
| Resolution | 3.125 m |
| Size | 49695 x 79160 px, 1115 MB |
| NoData | NaN (tagged in the header) — dry land, permanent water, and ground outside the model |
| Units | metres of water depth above the ground surface |

The CRS is the one thing most likely to trip you up. Opening this expecting lat/lon
gives corner coordinates like `501136, 4497255`; that is not corruption, it is UTM in
metres. QGIS, ArcGIS and rasterio all reproject on the fly. If you need degrees
(EPSG:4326) say so and I will ship a reprojected copy — better that than resampling
depths yourself.

Extent: `(437693.8, 4286275.0, 592990.6, 4533650.0)` in UTM, which is `(-75.7403, 38.7202, -73.8952, 40.954)` as (west, south, east, north) in degrees.

```python
import rioxarray
da = rioxarray.open_rasterio("sandy_hmax_v4_refreeze_swz_v11_bed2026_bareground_EPSG32618.tif", masked=True).squeeze()
da = da.where(da >= 0.15)          # see "wet threshold" below
# da.rio.reproject("EPSG:4326")    # only if you actually need degrees
```

The file has overviews, so it opens instantly in QGIS at any zoom. Reading the full
band into memory takes about 15.7 GB.

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

Wet cells: 227,041,596 (2217 km², 5.77% of the grid rectangle);
depth range 0.05 to 18.31 m. At or above the 0.15 m threshold:
211,995,587 cells (2070 km²), median depth 1.16 m, 99th percentile
3.22 m.

### Wet threshold

The raster floor is **0.05 m** (an artifact of how the downscale is built). Our own
scoring treats a cell as wet only at **>= 0.15 m**. Below that you are looking at
numerical damp rather than flooding, and most damage curves will happily assign losses
to it. **Threshold at 0.15 m** unless you have a specific reason not to. The 0.05 m
values are left in rather than silently deleted, so the choice stays yours.

## How good is it?

(no scored row found for this arm in metrics.csv)

## Caveats — please read before trusting a number

1. **Not what happened in 2012.** Use the 2012-ground map for the real event; this one
   asks what the same storm would do to today's coast. Differences between the two are
   differences of terrain only (plus the Port Monmouth gate and the PEWS check valve,
   which this run has and the 2012 one does not).
2. **Known low bias, inherited.** On 2012 ground this model setup reads slightly low
   against surveyed USGS high-water marks (the score below is this run against the 2012
   marks, which do not strictly apply to today's ground). Damages will tend to be
   under-estimates. Not a return-period or design product.
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
6. **Depth is measured from the BARE ground, buildings included.** The model
   represents buildings as raised ground that water flows around; this map takes the
   peak water level around each building and subtracts the bare ground under it, so a
   footprint carries the depth of water against that building — read it at the
   centroid or over the footprint, and subtract the first-floor height as usual.
   3,720,980 of 70,990,360 footprint pixels are wet (>= 0.15 m). A
   building large enough to fill a whole model cell can still read dry, and so can one
   that fills most of a cell where the only water in the model is rain off its own roof.
   For a damage model use the companion `..._buildings_...` GeoTIFF and per-building
   table when they ship beside this file (`scripts/fiat_building_depth.py`): they give
   every footprint the median water level of the streets within 50 m.

Off building footprints the ground is the model's own, so there the depths are the
model's normal flood map, pixel for pixel; only the footprints differ.

Questions to Ty.
