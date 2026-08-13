"""Score the Manahawkin BRACKET — the width, not the arm.

⚠️ THE ARM BEING SCORED HERE IS DELIBERATELY INADMISSIBLE. It leaves hydromt's
water-level boundary standing across the Manahawkin bay cross-section, imposing the
open-ocean level on INTERIOR bay water. That is the SAME defect class as the inlet
clamp, which scored well and cost the 2026-07-26..29 campaign. Nothing this script
prints is a candidate result. The ONLY quantity it exists to produce is the **width**
between the walled control (lower bound — the 39.70 wall can only UNDER-supply the bay)
and the bracket (upper bound — an imposed ocean level can only OVER-supply it).

That width is the most the omitted southern connection (Little Egg / Beach Haven
inlets) could possibly be worth, and it costs one run instead of a ~1.4 M-face
southward mesh rebuild plus a re-baseline of every arm.

Guards, because labelling was already proven insufficient once:
  * the control must pass ``premier.assert_sealed_domain`` (it IS a candidate);
  * the bracket must pass ``premier.assert_bracket`` — which additionally demands
    ``NJ_ALLOW_BRACKET=manahawkin-open``, so a copied command line cannot score one;
  * output goes to ``reports/bracket_manahawkin.csv``, NEVER ``reports/metrics.csv``,
    and every bracket row is stamped ``domain = BRACKET:<name> INADMISSIBLE``.

⚠️ The two arms differ by the mask ONLY, so the domain fingerprints differ ON PURPOSE
and pooling them is legitimate here for the same reason it is in
``score_interior_gauges.py``: the domain IS the treatment. Do not copy these rows into
a table beside HWM/CSI numbers.

Run:
    NJ_ROOT=$PWD NJ_DOMAIN=v2_barnegat NJ_ALLOW_BRACKET=manahawkin-open PYTHONPATH=$PWD \
        micromamba/envs/sfincs/bin/python scripts/score_bracket.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import nj_sfincs  # noqa: F401  (PROJ primer)
from nj_sfincs import premier, validate
from nj_sfincs.config import exp_root, ROOT, DATA

BRACKET = "manahawkin-open"

#: Lower bound: the shipped domain, walled at lat 39.70. It can only UNDER-supply.
WALLED = "wave-cora+bed-ehydro+mask-inlet"
#: Upper bound: same everything, 55 cells swapped active -> water-level BC. Only the
#: mask differs (z, subgrid and the wave boundary were asserted byte-identical at build).
OPEN = "BRACKET+wave-cora+bed-ehydro+mask-inlet+mask-manahawkin-open"

OUT = ROOT / "reports" / "bracket_manahawkin.csv"

#: ⚠️ PRE-REGISTERED 2026-08-03, BEFORE the run — see [[reference_bracket_pattern]].
#: Read this before looking at the numbers, not after.
#:
#: Predictions
#:   P1  the bracket adds water at the SOUTH end => Barnegat Light rises MORE than
#:       Mantoloking and the along-bay gradient goes FURTHER NEGATIVE. Hence, whatever
#:       the width, the southern wall CANNOT explain the tilt shortfall — a free result,
#:       independent of magnitude.
#:   P2  ig_tide_range_barnegat_light (0.808 walled vs 1.003 observed) rises toward or
#:       past observed — the same clamp signature the inlet repair removed.
#:
#: Decision rule on the width at MANTOLOKING
#:   < 0.25 m   retire the southward extension
#:   0.25-0.6   contributor, not explanation
#:   > 0.6 m    justifies the rebuild — but ONLY if tilt is not degraded AND the walled
#:              run's deficit lies INSIDE the bracket
RETIRE_BELOW = 0.25
REBUILD_ABOVE = 0.60

#: The pre-registration says "width at Mantoloking" without naming a statistic. Rather
#: than pick one after seeing the numbers, all three are computed and the rule is applied
#: to each; disagreement between them is reported as disagreement.
WIDTH_STATS = ("mean", "peak", "max")


def open_model(d: Path):
    """SfincsModel + outputs, skipping load_floodmap's ~2 min raster work.

    Same reasoning as ``score_interior_gauges.open_model``: the interior-gauge metrics
    need only the his points, sfincs_map.nc and sfincs.nc.
    """
    from hydromt_sfincs import SfincsModel

    mod = SfincsModel(str(d), data_libs=[str(DATA / "data_catalog.yml")], mode="r")
    validate.read_output(mod)
    return mod


def bracket_width(gauge: str) -> dict:
    """Width = bracket MODELLED level minus walled MODELLED level, at one gauge.

    Deliberately a model-minus-model difference: the width is a property of the two
    boundary treatments and does not depend on the observations at all. The observed
    error of each bound is reported separately, because the containment test — is the
    truth actually INSIDE the bracket — is a different question from how wide it is.

    Both series come from ``interior_gauge_series(source="map")``, i.e. the median over
    wet channel cells, on the model clock, restricted to ``validate.BAY_WINDOW``.
    """
    lo = validate.interior_gauge_series(exp_root() / WALLED, gauge)
    hi = validate.interior_gauge_series(exp_root() / OPEN, gauge)
    if lo.empty or hi.empty:
        return {}

    t0, t1 = validate.BAY_WINDOW
    j = lo.join(hi, lsuffix="_lo", rsuffix="_hi").loc[str(t0):str(t1)]
    j = j[np.isfinite(j[["mod_lo", "mod_hi"]]).all(axis=1)]
    if len(j) < 3:
        return {}

    w = (j["mod_hi"] - j["mod_lo"]).to_numpy()
    obs_ok = np.isfinite(j["obs_lo"].to_numpy())

    out = {
        f"width_n_{gauge}": len(j),
        # the three statistics, all of them, chosen before seeing the answer
        f"width_mean_{gauge}_m": round(float(w.mean()), 3),
        f"width_max_{gauge}_m": round(float(w[np.argmax(np.abs(w))]), 3),
        f"width_peak_{gauge}_m": round(float(j["mod_hi"].max() - j["mod_lo"].max()), 3),
        f"width_final_{gauge}_m": round(float(w[-1]), 3),
    }

    # ⭐ CONTAINMENT — the sharpest test, and it is NOT the width.
    # If the walled run is too LOW and the bracket is too HIGH, the truth lies between
    # the bounds and the southern connection is a live candidate for the difference.
    # If the bracket is STILL too low, then even an ocean level imposed on the bay's
    # southern end cannot supply the missing water, and the deficit has another source
    # entirely — a verdict that does not depend on the width at all.
    if obs_ok.any():
        e_lo = j["err_lo"].to_numpy()[obs_ok]
        e_hi = j["err_hi"].to_numpy()[obs_ok]
        out[f"err_walled_mean_{gauge}_m"] = round(float(e_lo.mean()), 3)
        out[f"err_bracket_mean_{gauge}_m"] = round(float(e_hi.mean()), 3)
        out[f"contained_{gauge}"] = bool(e_lo.mean() < 0 < e_hi.mean())
        # how much of the walled deficit the upper bound actually closes
        out[f"deficit_closed_{gauge}_frac"] = (
            round(float((e_hi.mean() - e_lo.mean()) / abs(e_lo.mean())), 3)
            if abs(e_lo.mean()) > 1e-9 else float("nan"))
    return out


def verdict(width_m: float) -> str:
    if width_m < RETIRE_BELOW:
        return "RETIRE the southward extension"
    if width_m <= REBUILD_ABOVE:
        return "CONTRIBUTOR, not explanation"
    return "REBUILD justified (subject to the two side conditions)"


def main() -> int:
    walled_dir = exp_root() / WALLED
    open_dir = exp_root() / OPEN

    # ── guards ────────────────────────────────────────────────────────────────
    # The control must be a genuine candidate; the bracket must be the named bracket
    # AND the caller must have said so out loud. Both before any number is computed.
    premier.assert_sealed_domain(walled_dir, context="score_bracket control")
    premier.assert_bracket(open_dir, BRACKET, context="score_bracket")
    brk = premier.BRACKETS[BRACKET]

    print("=" * 78)
    print(f"  INADMISSIBLE BRACKET '{brk.name}' ({brk.bound} bound)")
    print(f"  {brk.inadmissible_why}")
    print(f"  BOUNDS: {brk.bounds_what}")
    print("=" * 78 + "\n")

    for d in (walled_dir, open_dir):
        if not (d / "sfincs_map.nc").is_file():
            print(f"MISSING sfincs_map.nc in {d}")
            return 1

    rows = {}
    for label, name, d in ((f"{WALLED} (LOWER bound)", WALLED, walled_dir),
                           (f"{OPEN} (UPPER bound)", OPEN, open_dir)):
        print(f"[{name}] interior gauges ...", flush=True)
        r = validate.interior_gauge_metrics(open_model(d), d)
        r.update(validate.bay_error_decomposition(d))
        r["domain"] = (f"BRACKET:{BRACKET} INADMISSIBLE"
                       if name.startswith(premier.BRACKET_PREFIX) else "v2_barnegat")
        rows[label] = r

    print("[width] bracket - walled ...", flush=True)
    width = {"domain": f"BRACKET:{BRACKET} width — the ONLY quotable quantity here"}
    for g in validate.INTERIOR_TIDE_GAUGES:
        width.update(bracket_width(g))
    rows["WIDTH (upper - lower)"] = width

    df = pd.DataFrame.from_dict(rows, orient="index")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT)
    print(f"\nwrote {OUT}\n")

    def show(title, cols):
        cols = [c for c in cols if c in df.columns]
        if not cols:
            return
        print(f"=== {title} ===")
        with pd.option_context("display.width", 240, "display.max_columns", 60):
            print(df[cols].dropna(how="all").to_string())
        print()

    show("⭐ THE WIDTH at Mantoloking — the decision quantity",
         [f"width_{s}_mantoloking_m" for s in WIDTH_STATS]
         + ["width_final_mantoloking_m", "width_n_mantoloking"])
    show("Width at Barnegat Light — P1 predicts this EXCEEDS Mantoloking",
         [f"width_{s}_barnegat_light_m" for s in WIDTH_STATS]
         + ["width_final_barnegat_light_m"])
    show("⭐ CONTAINMENT — is the truth even inside the bracket?",
         ["err_walled_mean_mantoloking_m", "err_bracket_mean_mantoloking_m",
          "contained_mantoloking", "deficit_closed_mantoloking_frac",
          "err_walled_mean_barnegat_light_m", "err_bracket_mean_barnegat_light_m",
          "contained_barnegat_light", "deficit_closed_barnegat_light_frac"])
    show("P1 — tilt / along-bay gradient (predicted to go FURTHER NEGATIVE)",
         ["bay_tilt_err_mean_m", "bay_tilt_err_absmax_m", "bay_volume_err_mean_m",
          "bay_volume_err_final_m", "bay_dominant_term", "bay_tilt_over_volume",
          "alongbay_obs_max_m", "alongbay_matched_m", "alongbay_matched_ratio"])
    show("P2 — Barnegat Light pre-storm tidal RANGE (walled 0.808 vs obs 1.003)",
         ["ig_tide_obs_range_barnegat_light_m", "ig_tide_mod_range_barnegat_light_m",
          "ig_tide_range_err_barnegat_light_m",
          "ig_tide_mod_range_mantoloking_m", "ig_tide_range_err_mantoloking_m"])
    show("Peak level per gauge",
         ["ig_mod_peak_barnegat_light_m", "ig_peak_err_barnegat_light_m",
          "ig_mod_peak_mantoloking_m", "ig_peak_err_mantoloking_m",
          "ig_mod_peak_barnegat_inlet_sss_m", "ig_peak_err_barnegat_inlet_sss_m"])

    # ── the pre-registered rule, applied verbatim ─────────────────────────────
    print("=" * 78)
    print("  PRE-REGISTERED DECISION RULE (fixed 2026-08-03, before the run)")
    print(f"    < {RETIRE_BELOW}      retire the southward extension")
    print(f"    {RETIRE_BELOW}-{REBUILD_ABOVE}   contributor, not explanation")
    print(f"    > {REBUILD_ABOVE}      rebuild justified, IF tilt not degraded AND "
          "the deficit is contained")
    print("=" * 78)
    verdicts = {}
    for s in WIDTH_STATS:
        w = width.get(f"width_{s}_mantoloking_m")
        if w is None:
            continue
        verdicts[s] = verdict(abs(w))
        print(f"  width_{s:<5} = {w:+.3f} m  ->  {verdicts[s]}")
    if len(set(verdicts.values())) > 1:
        print("\n  ⚠️ THE THREE STATISTICS DISAGREE. The pre-registration did not name "
              "one.\n     Report the disagreement; do not pick the flattering one.")

    # side conditions, reported whatever the width says
    tilt = df["bay_tilt_err_mean_m"].dropna() if "bay_tilt_err_mean_m" in df else pd.Series(dtype=float)
    if len(tilt) == 2:
        lo_t, hi_t = abs(tilt.iloc[0]), abs(tilt.iloc[1])
        print(f"\n  side condition — tilt |err|: walled {lo_t:.3f} -> bracket {hi_t:.3f} "
              f"({'DEGRADED' if hi_t > lo_t else 'not degraded'})")
    c = width.get("contained_mantoloking")
    if c is not None:
        print(f"  side condition — deficit contained at Mantoloking: {c}")
        if not c:
            print("    ⇒ even the UPPER bound does not supply the missing water. The "
                  "southern\n      connection cannot be the source of the deficit, "
                  "whatever the width.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
