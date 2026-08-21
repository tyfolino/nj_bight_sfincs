# Pre-registration — weir promote-vs-delta decision (written 2026-08-21, before scoring)

Comparison: `diag-premier-keansburg-weir` (A) vs `naccs-premier` (B). Both waves-on,
identical physics except `sfincs.weir` (89-vertex USACE protection line, crest
max(ridge, 2.9 m), cd 0.6). Declared BEFORE any A number was computed.

**Primary field: the modeled pocket levels at the three Keansburg marks**
(6155 q1 · 6156 q3 · 6133 q3; obs ≈ 1.55 m; B models ~3.3 m, residual +1.7/+1.8).
Success looks like the nowaves pair (FINDINGS §38): capping to ~2.5 m, residual → ~+0.9.
The field is the mark-sampled level from the floodmap (same estimator/radius as
`hwm_metrics`); 6155 is the only mark of the three in the q≤2 headline set.

**Secondary fields, named now:**
1. `paired_hwm_bootstrap.py A B` Δ RMSE on the common scored set — the weir should not
   make the domain WORSE (CI upper < ~+0.02 m). ⚠️ Raritan Bay marks carry the
   arm-dependent `zsmax` sub-hourly band (~±0.1–0.2 m locally); bay-wide Δ inside that
   band is not attributable. The pocket signal (~0.8 m) is 3–4× the band.
2. MOTF CSI/POD/FAR for A (same screens as `metrics.csv`) — extent must not degrade
   materially (ΔCSI worse than −0.01 would count against promotion). MOTF floods the
   pocket too (bathtub, no structures), so a small CSI *drop* from correctly drying
   the pocket is expected and does NOT count against promotion; the FA/miss split in
   the Keansburg box is the tell.

**Decision rule (recommendation only — the user decides):** promote the weir into the
premier config if the pocket caps ≈ as the nowaves pair AND neither secondary field
degrades beyond its stated bound; otherwise keep as delta arm.

⚠️ All numbers PROVISIONAL until the >26 h three-clock re-audit of the diag runs
(due after 2026-08-21 ~19:00) — the halk clobber lands late.
