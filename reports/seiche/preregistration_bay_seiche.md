# Pre-registration — Raritan Bay seiche-vs-chatter (written 2026-08-21, before any number)

The open question (STATUS PICK UP item 1): the `zsmax` sub-hourly excess in Raritan Bay is
arm-dependent (premier 0.255 m vs nowaves 0.431 m, an arm gap of −0.176 m that fully
accounts for the retracted "damping"), and the 10-min `his` shows the bay ringing
differently between arms at up to 1.32 m instantaneous. **Is that motion a coherent basin
seiche, or numerical chatter?** Coherent ⇒ `zsmax` scoring stands and bay arm-comparisons
are read carefully. Incoherent ⇒ bay spatial scores need a filtered or hourly basis.

## The run this is read off

`experiments/v1_5_raritan/diag-nowaves-fasthis` — `naccs-nowaves` physics (PRE-weir),
fingerprint verified on domain, `dthisout = 60 s`, 4321 steps over the full 72 h window,
**14 observation points accepted** (SLURM 60693810, hal0344, `output WHOLE`).

⚠️ STATUS recorded that SFINCS silently dropped the six `rb_axis_*` points. That entry is
**wrong**: the run's own log lists `observation point 1..14` and `wc -l sfincs.obs` is 14.
The acceptance check STATUS demanded as a precondition therefore PASSES on the existing
run, and no re-run is required to answer the question.

**Stations.** Bay axis (six, spanning 11.6 km along the dredged Raritan Bay deep axis,
bed −10.4 to −16.2 m): `rb_axis_571k` `rb_axis_569k` `rb_axis_566k` `rb_axis_564k`
`rb_axis_561k` `rb_axis_559k`. Bay flanks: `sss_arthur_kill_mouth`, `sss_great_kills`.
**Open-coast control:** `usgs_tidal_shark_river`, `usgs_tidal_sea_bright`, `sandy_hook` —
STATUS records the open coast as clean (arm gap +0.007 m, `zsmax` and hourly agree to
1 mm), so these must show a far smaller sub-hourly amplitude than the bay. If they do not,
the signal is not bay-specific and the whole framing is wrong.

## PRIMARY field — where does the excess live in FREQUENCY?

This is the field that decides the scoring question, and it is prior to coherence.
Per station:

| field | definition |
|---|---|
| `excess_total_m` | `zsmax`(map, running max at the solver step) − `max(zs_hourly)` |
| `excess_recovered_m` | `max(zs_60s his)` − `max(zs_hourly)` |
| `recovery_frac` | `excess_recovered / excess_total` |

`zs_hourly` is the map's own hourly `zs` at the station's face; the face is the nearest
face centre to the station coordinate. `zsmax` is the max over its 3 blocks.

**No physical seiche in a 12 km, 6–16 m basin has a period below 2 minutes**, so:

* `recovery_frac` ≈ 1 ⇒ the excess is motion the 60 s record RESOLVES, and the coherence
  test below is a meaningful test *of the thing that contaminates the scores*.
* `recovery_frac` ≪ 1 ⇒ the excess lives faster than the 120 s Nyquist period — no
  candidate physical mode exists there, so that is chatter, and it is chatter that the
  coherence test cannot see. This alone would settle the scoring question.

Declared threshold: **≥ 0.7 counts as "resolved", ≤ 0.3 as "unresolved"**, between the two
is reported as partial and neither branch is claimed.

## SECONDARY fields — is the resolved part COHERENT?

High-pass each 60 s `point_zs` by subtracting a centred 61-sample (61 min) rolling mean;
`hp` is the residual. Reported over the full window and over a crest window (±6 h about
the domain-peak hour).

1. `hp_std_m`, `hp_max_m` per station — the amplitude of the sub-hourly band.
2. **Coherence between the axis ENDS** (`rb_axis_571k` vs `rb_axis_559k`, 11.6 km apart):
   peak magnitude-squared coherence γ² in the 4–60 min band and the period at which it
   peaks (Welch, ~4 h segments, 50% overlap).
3. **A common spectral peak**: the period of the largest PSD peak of `hp` in the 4–60 min
   band, per station. Do ≥ 4 of the 6 axis stations agree within ±20%?
4. **Propagation**: lag of the peak cross-correlation of `hp` between adjacent axis pairs,
   → implied speed = separation / lag, against `sqrt(g·h)` (≈ 11.7 m/s at h = 14 m,
   ≈ 7.7 m/s for the broad bay at h = 6 m).

## Decision rule, declared now

* **COHERENT (seiche)** — γ²(ends) ≥ 0.5 at a period in the 4–60 min band, AND ≥ 4 of 6
  axis stations share a common peak period within ±20%, AND the implied propagation speed
  is within a factor of 3 of `sqrt(g·h)`.
* **INCOHERENT (chatter)** — γ²(ends) < 0.3, OR no common peak, OR implied speed off
  shallow-water propagation by more than an order of magnitude.
* Anything else is **AMBIGUOUS** and will be reported as ambiguous. The rule is allowed to
  return "don't know"; it is not allowed to be relaxed after the numbers are seen.

## Stated limitations, before the fact

* 60 s sampling ⇒ **Nyquist period 120 s**. A null result in the 4–60 min band does not
  prove the absence of faster motion; it is exactly why `recovery_frac` is primary.
* This is ONE arm (waves-off, pre-weir). It can establish what the motion IS; it cannot by
  itself explain why the two arms ring *differently* — that is a second question.
* The axis points follow the **dredged navigation channel** (bed 10–16 m in a bay whose
  broad depth is ~6 m), not the open bay. A narrow deep trench can support trapped modes
  the wide basin does not, so a coherent result should be read as "coherent along the
  channel", and the flank stations (Arthur Kill mouth, Great Kills) are the check on
  whether it is basin-wide.
* n = 6 axis points over 11.6 km resolves along-axis structure coarsely; it can distinguish
  organized-vs-not, not a specific mode number.
