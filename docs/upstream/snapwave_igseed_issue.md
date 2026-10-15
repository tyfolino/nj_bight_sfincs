<!-- Draft GitHub issue for github.com/Deltares/SFINCS (2026-10-15, FINDINGS §44/§45). The user files it. Patch: snapwave_igseed.patch -->

# SnapWave: the Herbers IG boundary draws unseeded random numbers, so waves-on runs never repeat

**File:** `source/src/snapwave/snapwave_infragravity.f90`, `compute_herbers` (l. 283–287 at tag
v2.3.3, `091f531a`; l. 287 on `main`, `eaf1283`).

```fortran
! Define random number between 0 and 1 for each wave component
do i=1,K
    call RANDOM_NUMBER(P0(i))
```

Nothing in SFINCS calls `RANDOM_SEED` or `RANDOM_INIT`. With gfortran ≥ 7 an unseeded
`RANDOM_NUMBER` is seeded from the operating system, so every run draws a different set of the
K = 400 component directions. Three lines show it (gfortran 11.5, `-fopenmp -O3`): each run of

```fortran
program t
  real :: x(3)
  call random_number(x)
  print *, x
end program
```

prints different numbers.

**Why it reaches the water levels.** The draw sets `hst_bwv_ig` / `tpt_bwv_ig` at every boundary
support point, every wave update (`update_boundary_points` → `determine_ig_bc`). The IG source term
is then subtracted from the incident energy in the solver,

```fortran
R(itheta) = ... - srcig_local(itheta, k) * shinc2ig      ! snapwave_solver.f90:664
```

and `snapwave_shinc2ig` defaults to **1.0** (`sfincs_snapwave.f90:644`). The declaration comment in
`snapwave_solver.f90:298` / `snapwave_data.f90:262` says "0=default", which is stale. So the random
draw changes the incident field, the breaking dissipation, the wave force and `zs`.

**What we see.** v2.3.3 + our wind-direction fix (#—), `snapwave_igwaves = 1`, no wavemaker,
3.4 M SnapWave nodes:
- Two runs of one binary on byte-identical inputs differ already at the first SnapWave call:
  9 vs 14 iterations, even with `OMP_NUM_THREADS=1`.
- On a 72 h hindcast, two otherwise identical runs differ by 0.12 m at a bay gauge in the first
  hour, and by 5–14 cm (median) in the peak-water map in large bays.
- With `snapwave_igwaves = 0` the same model repeats bit for bit.

**Fix (patch attached).** Seed with a fixed value immediately before the draws, on every call:

```fortran
call random_seed(size=nseed)
allocate(seed(nseed))
seed = (/(20121029 + 7919*iseed, iseed=1,nseed)/)
call random_seed(put=seed)
deallocate(seed)
```

Re-seeding on every call (not once at start-up) gives every boundary point and every update the
same sample. Results then do not depend on run history: a restart matches an uninterrupted run,
and runs with a different `dtwave` or number of boundary points draw the same components. An
alternative is a deterministic quadrature over directions instead of a Monte Carlo draw.
