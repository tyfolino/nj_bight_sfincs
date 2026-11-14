# Sandy Hook MOTF — is the spit's changing shape a scoring problem? (2026-11-14)

Question (user): MOTF on Sandy Hook "usually has issues" because the spit's shape changed since 2012 — was it fixed?
Answer: it was never addressed, and it does not need to be, on either bed. No exclusion box, no bed overlay.

Scorer re-created block-wise (`classify_motf.py`), reproducing 1.1.0's native re-score exactly (CSI 0.801964,
POD 0.867566, FAR 0.086164; logs/floodmap_fix_2026-11-12/rows/). Spit = Gateway, lat 40.393 → tip, Highlands kept
out (three boxes in `analyse.py`).

| bed | spit hits / misses / FA, km² | spit CSI | domain CSI |
|---|---|---|---|
| 2012 (1.1.0) | 6.70 / 0.63 / 0.30 (0.56 / 0.34 / 0.27 % of domain) | ~0.88 | 0.802 |
| 2026 (`bed-modernb+p4-premier+…`, this sampler, no published row) | 6.40 / 0.30 / 0.19 | 0.93 | 0.805 |

- 2012 bed: shorelines (0 / 0.6 m) sit on CZMIL 2012-11-16 almost everywhere (0.03–0.09 km² differ; EAARL-B
  2012-10-26: 0.06–0.12). 83 % of scored spit pixels = USACE 2010 topobathy (pre-Sandy), 17 % CUDEM (NGS 2014).
  FA = the tip where the MOTF sheet stops at the validity edge (0.14 km²), a dune-line strip (0.16), one footprint.
- 2026 bed: the shape change is real — 0.64 km² of 2012 land is water in the 2026 bed, MOTF calls 0.46 km² of it
  flooded. The scorer counts only ground > 0 m, so these drop out silently (lost hits, not FA). Quote 0.46 km² in any
  bed-vs-bed comparison on the spit.
- The predecessor's "false alarms at Sandy Hook spit" (~/nj_coast_sfincs/docs/roadmap.md:89) was its bay-setup leak.
- Optional, not recommended: tip-only box (-74.010, 40.4775, -73.995, 40.484), ΔCSI +0.00006 on 1.1.0.

Figures: `sandy_hook_motf_classes_v11.png`, `sandy_hook_motf_classes_bed2026.png`. Outputs: `analyse.txt`,
`shape.txt`, `shape_bed2026.txt`. (`sim_mask_v11.npy` cache deleted 11-14.)
