<!-- Draft GitHub issue for github.com/Deltares/SFINCS (2026-10-26; FINDINGS §44 (a)–(d), (j)). The user files it. Patch against main f3647fc: sfincs_reproducibility_main.patch. Toy evidence: logs/upstream_repro_2026-10-26/ (README). Duplicate search 10-26: none open or closed. -->

# Runs with IG waves or a wavemaker are not reproducible (unseeded `RANDOM_NUMBER`), and the wavemaker signal changes on a restart

**Summary.** Two identical SFINCS runs with `snapwave_igwaves = 1`, or with a wavemaker, give
different water levels, because the random draws behind both are never seeded. Separately, a
wavemaker run restarted from a restart file continues with a different IG signal, because the
wavemaker phase is accumulated from `tstart`. A 32-line patch fixes both (attached; we can open
a PR if that is easier).

## 1. Three unseeded draws

Nothing in SFINCS calls `RANDOM_SEED` or `RANDOM_INIT`. Since gfortran 7, an unseeded
`RANDOM_NUMBER` is seeded from the operating system, so every run draws different numbers.
On `main` (`f3647fc`):

- `snapwave/snapwave_infragravity.f90:365`, `compute_herbers`: the K = 400 component
  directions of the Herbers IG boundary, redrawn on every call (every boundary support point,
  every wave update).
- `sfincs_wavemaker.f90:1504` and `:1518`, `initialize_wavemakers`: the random phases of the
  IG and incident wavemaker components.

The Herbers draw reaches the water levels even without a wavemaker. The IG source term is
subtracted from the incident energy (`snapwave_solver.f90:953`, `- srcig_local * shinc2ig`)
and `snapwave_shinc2ig` defaults to 1.0 (`snapwave_input.f90:73`). The comments at
`snapwave_solver.f90:518` and `snapwave_data.f90:266` still say "0=default". So the draw
changes breaking, the wave force and `zs`.

## 2. The wavemaker phase is accumulated from `tstart`

```fortran
wavemaker_phi_ig(ifreq)  = modulo(wavemaker_phi_ig(ifreq) + wavemaker_dphi_ig(ifreq) * dt, 2 * pi)   ! sfincs_wavemaker.f90:1569
wavemaker_cost_ig(ifreq) = cos(2 * pi * t * wavemaker_freq_ig(ifreq) + wavemaker_phi_ig(ifreq))
```

A run started from a restart file begins this sum again at its own `tstart`. So even with
seeded phases, every component jumps by `dphi·(t_restart − tstart)` at the restart, and the IG
signal after it is a different realisation.

## What we measured

**On `main` (`f3647fc`), stock vs patched.** Native gfortran 11.5 build (`-fopenmp -O3`), with
a 4,560-cell toy: SnapWave with `snapwave_igwaves = 1`, one wavemaker polyline (120 u/v points),
3 h, `OMP_NUM_THREADS=1`. Each case was run twice from the same inputs.

In the patched pairs, every output variable is identical except the wall-clock `total_runtime`.

| | stock `main` | patched |
|---|---|---|
| IG + wavemaker, run twice: max \|Δzs\| (stations / map) | 0.35 m / 0.32 m | 0 / 0 |
| IG, no wavemaker, run twice: max \|Δzs\| (stations / map), \|Δhm0\| (map) | 0.13 mm / 7.8 mm, 6.2 cm | 0 / 0, 0 |
| IG + wavemaker, restarted at 01:00 vs uninterrupted: correlation of `zs` at the 4 surf-zone stations | −0.08 to 0.53 | 0.97 to 0.99 |
| same, max \|Δzs\| at those stations | 0.13–0.32 m | 0.04–0.10 m |

The difference that remains after a restart comes from state the restart file does not carry
(the wavemaker's mean-water-level filter, the SnapWave field and the advection velocities).
That is a separate topic.

**On a large model (v2.3.3 with the same fix):** a 4.9 M-cell SFINCS + SnapWave hindcast of
Hurricane Sandy (New Jersey). Without the seed:
- byte-identical copies differ from the first SnapWave call, also with one OpenMP thread;
- within 3 h, they differ by up to 0.41 m at a bay gauge;
- with `snapwave_igwaves = 0`, the same model repeats bit for bit.

With the seed, IG-on copies are bit-identical, also between two different clusters. That
holds with a wavemaker too (6 h, 7,940 u/v points).

## The fix (attached patch)

- `compute_herbers`: `random_seed(put=…)` with a fixed seed right before the draws, **on every
  call**. Every boundary point and every wave update then sees the same component sample,
  independent of run history: a restart, a different `dtwave` or a different number of
  boundary points does not change it.
- `initialize_wavemakers`: a fixed seed once, before the IG phase draws. The incident draws
  continue the same stream.
- `update_wavemaker_fluxes`: the phase in closed form in model time,
  `cos(2π·f·t + φ0 + dφ·t)`, with `t` in seconds since `tref` (`real*8`), instead of the
  accumulated sum. The component frequencies are unchanged (`f + dφ/2π`; see #⟨offset issue⟩
  on that offset). When `tstart = tref` this gives the same signal as before, up to
  single-precision rounding of the sum.

The seed values are arbitrary. An input keyword for the seed would let users draw an ensemble
on purpose. A deterministic quadrature over directions, in place of the Monte Carlo draw in
`compute_herbers`, would remove the randomness there entirely.
