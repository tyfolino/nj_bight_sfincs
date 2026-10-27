<!-- Draft GitHub issue for github.com/Deltares/SFINCS (2026-10-26; STATUS "Wavemaker IG spectrum shift"). A QUESTION, not a bug claim. The user files it. Numbers: logs/upstream_repro_2026-10-26/ (README). -->

# Wavemaker: the phase drift `dphi = 2π·1e-6/f` moves the lowest IG components out of their frequency bins. Is this intended?

**Where** (`main` at `f3647fc`): `initialize_wavemakers` sets a per-component phase rate

```fortran
wavemaker_dphi_ig(ifreq) = 1.0e-6 * 2 * 3.1416 / wavemaker_freq_ig(ifreq)      ! sfincs_wavemaker.f90:1506
```

and `update_wavemaker_fluxes` advances the phase with it every time step:

```fortran
wavemaker_phi_ig(ifreq)  = modulo(wavemaker_phi_ig(ifreq) + wavemaker_dphi_ig(ifreq) * dt, 2 * pi)   ! :1569
wavemaker_cost_ig(ifreq) = cos(2 * pi * t * wavemaker_freq_ig(ifreq) + wavemaker_phi_ig(ifreq))
```

The incident band does the same (l. 1520 and 1578).

**What it does.** A phase that grows at a constant rate is a frequency offset. Component *i*
oscillates at `f_i + 1e-6/f_i` Hz, while its amplitude is still computed at `f_i` (l. 1924).
The offset is the same in absolute terms at every bin width, so it is negligible at high
frequencies and large at low ones. With the default IG band (`freqminig = 0`, `freqmaxig = 0.1`,
`nfreqsig = 100`, so `df = 0.001` Hz):

| bin | nominal f (Hz) | runs at (Hz) | offset / df | period (s) |
|---|---|---|---|---|
| 1 | 0.0005 | 0.00250 | 2.0 | 2000 → 400 |
| 2 | 0.0015 | 0.00217 | 0.67 | 667 → 462 |
| 3 | 0.0025 | 0.00290 | 0.40 | 400 → 345 |
| 4 | 0.0035 | 0.00379 | 0.29 | 286 → 264 |
| 10 | 0.0095 | 0.00961 | 0.11 | 105 → 104 |

So bin 1 ends up above bins 2 and 3, and no component runs slower than 462 s, although the
band nominally reaches 2000 s. In 10 of the 100 bins the offset is more than 10 % of the bin
width.

**How much it matters.** For the spectral shape at l. 1924, the bulk spectrum barely changes:
the variance-weighted mean period is the same to the second at `Tp_ig` = 50 or 100 s, and 98 s
instead of 100 s at `Tp_ig` = 200 s. The low end does change. The share of IG variance in bins
offset by more than 10 % of `df` is 9 % at `Tp_ig` = 50 s, 26 % at 100 s and 59 % at 200 s.
For long IG periods, the slowest part of the forced signal is effectively missing. In the
incident band (`df = 0.0096` Hz) the offset is below 0.3 % of `df` everywhere, so it does not
matter there.

**Our guess at the purpose.** With evenly spaced frequencies `(k − ½)·df`, the sum of the
components repeats exactly every `2/df` = 2000 s. Breaking that repetition with an irregular
offset makes sense. If that is the purpose, an offset scaled to the bin width would do the same
job and keep every component inside its own bin. For example, a random offset in
`[−df/2, +df/2]` drawn alongside the phase, or `dphi = 2π·c·df` with a small irregular `c` per
component.

If the `1/f` form is deliberate (for example, matching XBeach or a reference spectrum), a
sentence in the docs would help users who set `freqminig = 0`.

**Context.** We noticed this while making wavemaker runs reproducible (#⟨repro issue⟩). Our
build keeps the frequencies exactly as they are in stock SFINCS, so none of our results depend
on a change here.
