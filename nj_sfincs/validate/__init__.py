"""Validation: read a finished run and score it.

``core``    — opening output, the flood-map downscale + its caches, series helpers.
``metrics`` — the scores, driven by ``domain.Domain.obs_gauges`` and ``hwm_rules``.

Import from here; the split is an organising device, not an interface.

🔴 THE TWO RULES, repeated because they decide whether a number means anything:

* **Never quote an HWM bias without its estimator and radius.** The estimator alone flips
  the sign of the bias and inverts the ranking of every arm.
* **Waves off ⇒ CSI / POD / FAR / n_dry are INADMISSIBLE.** Score levels and phase only.

And when comparing two arms, compare them **paired** — bootstrap the per-mark differences,
not the two pooled statistics. Two arms can differ by more than either differs from the
truth while the paired difference is indistinguishable from zero.
"""

from .core import (  # noqa: F401
    DEPTH_MIN,
    PEAK_FLOOR,
    SPINUP_SKIP_H,
    aligned_pair,
    cache_clear,
    his_series,
    load_floodmap,
    map_times,
    peak_after_floor,
    prestorm_window,
    read_output,
    tidal_signal,
    uniform_series,
    wet_channel_cells,
    xcorr_lag_minutes,
    zs_at_faces,
)
from .metrics import (  # noqa: F401
    HWM_ESTIMATOR_DEFAULT,
    HWM_ESTIMATORS,
    HWM_RADIUS_M,
    basin_error_decomposition,
    evaluate,
    gauge_peak_metrics,
    gauge_series_frame,
    hwm_metrics,
    motf_metrics,
    source_phase_lag,
    tide_metrics,
)

#: Back-compat alias — the old name for ``cache_clear``.
load_floodmap_cache_clear = cache_clear
