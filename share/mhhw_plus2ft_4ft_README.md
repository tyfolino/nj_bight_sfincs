# High tide + 2 ft and + 4 ft: New Jersey coast

**Preliminary, 2026-11-03.** These maps show where everyday high tide would reach on today's ground if the sea
were 2 ft (0.61 m) or 4 ft (1.22 m) higher. "High tide" here is MHHW (mean higher-high water), NOAA's usual
high-tide line from VDatum, with the rise added on top. There's no storm in these maps: no waves, wind, rain or
river flooding.

## Two versions

I made each map two ways, because they answer slightly different questions:

- **Still water (bathtub).** I raise the water to MHHW + 2 or + 4 ft and fill any low ground the sea can reach
  through a channel. A basin behind a levee or road embankment stays dry. This version assumes the tide has
  unlimited time to fill everything, so it overstates flooding far up narrow creeks and across wide marshes.
- **Tidal model.** I ran a real month of tides on the higher sea, letting the water move through the inlets,
  bays and rivers. The **mean higher-high** map shows where the day's high tide typically reaches. **I'd use
  this one as the headline.** The **month-max** map shows the single highest water of the month, a slightly
  wider upper bound.

| file | |
|---|---|
| `mhhw_plus{2,4}ft_stillwater_…tif` | still water |
| `mhhw_plus{2,4}ft_tidal_meanhigherhigh_…tif` | tidal model, typical high tide ⭐ |
| `mhhw_plus{2,4}ft_tidal_monthmax_…tif` | tidal model, highest tide of the month |
| `mhhw_plus2ft_4ft_by_region.csv` | flooded area by region, all six maps |
| `mhhw_plus2ft_4ft_vdatum_check.csv` | the tidal model's high tide vs NOAA's, by region |

## How much ground gets wet

Newly wet land (at least 0.15 m deep), in km²:

| | still water | tidal, typical | tidal, month max |
|---|---|---|---|
| + 2 ft | 583 | 371 | 520 |
| + 4 ft | 892 | 750 | 848 |

Most of the area is marsh around Delaware Bay. The regional breakdown is in `by_region.csv`.

## Where the versions disagree, and why

In Barnegat Bay and the ocean back bays the two versions agree, and the tidal model's high tide matches NOAA's
to within a few centimetres. They disagree most up the Delaware River and around Newark Bay. Part of that is
real, because a tide loses height as it travels upriver. Part is a known model weakness: in those places the
tidal model's high tide runs 10–45 cm below NOAA's (Newark Bay −0.11 m, Philadelphia −0.20, Burlington −0.29,
Great Bay −0.35, the Christina −0.45; full table in `vdatum_check.csv`). So the tidal maps **under-flood** the
river shores, and there the truth is probably somewhere between the two versions. I'm fixing this now and will
send updated tidal maps when it's done.

## Reading the files

- GeoTIFF, float32, 6.25 m pixels, with overviews. **CRS is EPSG:32618** (UTM 18N, metres, not degrees). All six
  maps share one grid, so you can difference them pixel by pixel.
- Values are **water depth above the ground, in metres**, on normally-dry land only. Water that's already there
  (bays, rivers, lakes, today's intertidal zone) is NaN, as is dry ground.
- There's no depth floor, so tiny depths at the water's edge are real. I count a pixel as wet at 0.15 m or
  more; use that threshold if you want to match my numbers.

```python
import rioxarray
da = rioxarray.open_rasterio("mhhw_plus4ft_tidal_meanhigherhigh_v4_refreeze_swz_EPSG32618.tif", masked=True).squeeze()
```

## Things to keep in mind

- **It's preliminary.** Expect replacements after the next model update.
- **Today's ground is estimated** from recent lidar. The channel and bay bottoms are still from around 2012.
- **The rise is uniform:** the same 0.61 or 1.22 m everywhere, with no subsidence and no change to the tides.
- **The Hudson waterfront is outside the model** (Hoboken, east Jersey City, Bayonne's Upper Bay side). Blank
  there means "not modelled", not "dry". Rivers stop at today's head of tide. The New York, Delaware and
  Pennsylvania shores are modelled but unchecked.
- **Buildings are raised ground,** so they read NaN. Read depth around a building, not at its centre.
- **The tidal maps have a few blank spots:** about 370 small cells near the Arthur Kill, where the model's water
  jumps around for reasons I'm still chasing. The month-max map also has a few isolated cells that are too
  high. Prefer the mean higher-high map for anything quantitative.

Questions to Ty.
