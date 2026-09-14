<!-- Draft GitHub issue for github.com/Deltares/SFINCS (2026-09-14, FINDINGS §43). The user files it. -->

# SnapWave: with `snapwave_wind = 1` the imposed boundary spectrum is rotated to the mean wind direction

**File:** `source/src/snapwave/snapwave_boundaries.f90` (lines from tag v2.3.3, `091f531a`;
the file is identical on `main`, `886d10a`). **Since:** PR #194 (fix for #193).

`update_boundary_conditions` builds the support-point spectra before it chooses the
directional grid, and the later grid change is an index shift the spectra never see.

1. `update_boundary_points` (l. 705–725) centres the grid on the mean imposed direction and
   builds the lobe on it:

   ```fortran
   thetamean = wdmean_bwv
   if (ntwbnd > 0) then
      call make_theta_grid(wdmean_bwv)
   ...
   dist = sign(1.0,cos(theta - thetamean))*abs(cos(theta - thetamean))**ms
   eet_bwv(:,ib) = dist/sum(dist)*E0/dtheta
   ```

   The lobe peak now sits on the middle bin indices.

2. Back in `update_boundary_conditions` (l. 495–517) the grid is re-made around the wind,
   and the rebuild hook is commented out:

   ```fortran
   if (wind) then
      thetamean=u10dmean
      call make_theta_grid(u10dmean)
   ...
   !call build_boundary_support_points_spectra() TODO - TL: later can clean up ...
   call update_boundaries()
   ```

   `make_theta_grid` only re-labels the bins (`ind = nint(central_theta/dtheta) - ntheta/2`);
   `eet_bwv` is untouched.

3. `update_boundaries` (l. 876) copies by bin index:

   ```fortran
   ee(i,k) = eet_bwv(i,ind1_bwv_cst(ib))*fac_bwv_cst(ib) + eet_bwv(i,ind2_bwv_cst(ib))*(1.0 - fac_bwv_cst(ib))
   ```

Net: with wind on and a wave boundary, Hs, Tp and spread are kept but the spectrum is rotated
by `u10dmean − wdmean_bwv`, so it peaks in the wind direction whatever the `.bwd` file says.
With `snapwave_sector < 360` the swell is also clipped. No input-file workaround exists.
Before #194 the guard in step 2 was `if (ntwbnd > 0)`, so steps 1 and 2 agreed.

**Confirmed:** plane beach, swell from 180°, uniform wind from 45°, sector 360, dtheta 10:
boundary-cell `wavdir` is 50° with wind on, 180° with wind off, 180° with the fix below.
Hurricane Sandy hindcast (imposed SWAN swell, ERA5 wind): boundary `wavdir` equals the
domain-mean wind on 73 of 73 hours; wind off reproduces the `.bwd` file on 73 of 73.

**Fix:** move the lobe construction into the empty `build_boundary_support_points_spectra()`,
call it at l. 513 (after the final `make_theta_grid`, before `update_boundaries`), and centre
the lobe on `wdmean_bwv` rather than `thetamean` (same for `eet_bwv_ig`). This keeps #194's
wind-centred grid; wind-off runs and runs without SnapWave are bit-identical. PR ready.

Not in that PR: the interior `ee(:,k)` is stored by bin index too, so a wind swing between
calls rotates the initial guess for the next one (more iteration-cap hits in wind-on runs).
