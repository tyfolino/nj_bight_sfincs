#!/usr/bin/env python
"""Write ``data/nj2_design/flux_crosssections_nj2.crs`` (Domain ``nj2.flux_crosssections``).

    python logs/nj2_freeze_2026-11-14/make_crs_nj2.py [--check]

= the shared ``data/flux_crosssections.crs`` (``barrier``, ``throat``: copied VERBATIM, so every
nj2 arm still carries the sections every other domain stages) + four nj2 sections:

- ``hudson_cut``, ``hell_gate_cut``: the forced cut line (``data/nj2_design/cut_*_nj2.csv``)
  moved ``OFFSET_M`` (110 m) perpendicular INTO the domain — the side of the matching obs point
  (``bc_hudson_cut`` / ``bc_hell_gate``, ~110 m inside), so Q(t) through each cut is measured two
  50 m faces in, never on the forced faces — and extended ``EXTEND_M`` past both ring vertices
  onto the banks (outside the active mask a crossing has no uv point and adds nothing).
- ``narrows`` (Fort Wadsworth -> Fort Hamilton, under the Verrazzano) and ``kvk`` (Staten
  Island -> Bayonne at lon -74.100): computed in nj2 (v1.5-v4 FORCED them), so the Upper Bay
  exchange through each is now a model output. Ends on land: CUDEM 1/9" along each line runs
  land / water / land (+32 .. -29 .. +9 m; +19 .. -14 .. +3 m; checked 2026-11-14).

Lines run W -> E (S -> N for ``kvk``); SFINCS signs the discharge by the drawn direction, as for
``barrier`` / ``throat``. Coordinates EPSG:32618, 0.1 m. ``--check``: exit 1 if the file on
disk differs from what this would write.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "data" / "nj2_design"
OUT = D / "flux_crosssections_nj2.crs"
SHARED = ROOT / "data" / "flux_crosssections.crs"
OFFSET_M = 110.0
EXTEND_M = 150.0
T = Transformer.from_crs(4326, 32618, always_xy=True)

#: name -> (cut csv, obs point that sits ~110 m inside it (lon, lat), from obs_nj2.csv / domain.py)
CUTS = {
    "hudson_cut": (D / "cut_hudson_nj2.csv", (-73.946, 40.859)),
    "hell_gate_cut": (D / "cut_hell_gate_nj2.csv", (-73.9385, 40.776)),
}
#: interior sections, (lon, lat) end points
INTERIOR = {
    "narrows": ((-74.0600, 40.6040), (-74.0300, 40.6095)),
    "kvk": ((-74.1000, 40.6390), (-74.1000, 40.6560)),
}


def _cut_xy(path: Path) -> np.ndarray:
    with open(path, newline="") as f:
        rows = list(csv.DictReader(ln for ln in f if not ln.startswith("#")))
    return np.array([T.transform(float(r["lon"]), float(r["lat"])) for r in rows])


def inside_line(cut: np.ndarray, obs_ll) -> np.ndarray:
    """The two-vertex cut moved OFFSET_M toward ``obs_ll`` and extended EXTEND_M each end."""
    a, b = cut[0], cut[-1]
    t = (b - a) / np.linalg.norm(b - a)
    nrm = np.array([-t[1], t[0]])
    o = np.array(T.transform(*obs_ll))
    if np.dot(o - a, nrm) < 0:
        nrm = -nrm
    return np.array([a - EXTEND_M * t, b + EXTEND_M * t]) + OFFSET_M * nrm


def render() -> str:
    text = SHARED.read_text()
    if not text.endswith("\n"):
        text += "\n"
    blocks = []
    for name, (path, obs) in CUTS.items():
        blocks.append((name, inside_line(_cut_xy(path), obs)))
    for name, (p, q) in INTERIOR.items():
        blocks.append((name, np.array([T.transform(*p), T.transform(*q)])))
    for name, xy in blocks:
        text += f"{name}\n{len(xy)} 2\n" + "".join(f"{x:.1f} {y:.1f}\n" for x, y in xy)
    return text


def main(argv: list[str]) -> int:
    text = render()
    if "--check" in argv:
        same = OUT.is_file() and OUT.read_text() == text
        print(f"{OUT}: {'matches' if same else 'DIFFERS from'} the builder")
        return 0 if same else 1
    tmp = OUT.with_suffix(".crs.tmp")
    tmp.write_text(text)
    tmp.replace(OUT)
    print(text[len(SHARED.read_text()) :], end="")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
