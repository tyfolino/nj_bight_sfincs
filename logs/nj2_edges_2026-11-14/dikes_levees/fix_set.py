"""The dikes-and-levees weir set for Model 2.0, FIXED (user 11-14). Read-only on logs/weirs_dikes_levees_2026-11-12/ and
data/structures_v4/; writes only data/nj2_design/structures/ and this folder.

    source logs/weirs_dikes_levees_2026-11-12/env.sh; python -I logs/nj2_edges_2026-11-14/dikes_levees/fix_set.py

Start: `cand_recommended.weir` (24 lines, md5 bbc2af85...) + `cand_cohansey_gate.weir` (1 line) = the set the 11-13 pair ran.
Changes (every other line is copied byte for byte):
 1. chester_nld4805000005_00 -> chester_nld4805000005_redraw_2026-11-14 (chester_redraw.py): the NLD line sat on the
    creek's inner bank and blocked 18 creek-to-creek links; the redraw runs on the cell edges between the leveed cells
    and the creek (0 creek-to-creek links), same side, NLD crest.
 2. forsythe_brigantine_r1303_p0_r60 -> ..._sw_2026-11-14: at the SW-corner leak (-74.4439, 39.4640) the outline ran
    40-70 m north of the dike and took 0.47-0.84 m crests (r60 disc missed the ridge); vertices 587-594 replaced by a
    detour onto the dike crest traced on 1/9in CUDEM between hand-picked ends (ridge.py; crest 1.97-2.20 m).
 3. tuckahoe_wma_r1286_p0_r60 -> ..._ridge_2026-11-14: the outline went round a low marsh triangle south of the pool's
    diagonal dike, along the upland toe where the lidar shows no dike (crests 0.72-0.88 at the leak, -74.7211,
    39.2739); vertices 257-376 replaced by the diagonal dike's crest (1.29-1.61 m). The triangle is left OPEN.
 4. The 6 structure notches: kept FILLED (storm = shut, the user's tide-gate rule of 11-12); notch_check.csv.
    Except r1054, change 5.
 5. dbay_de_newcastle_r1054_r1054_p0_r60 (Port Penn, DE; added 2026-11-16): the notch at the lidar channel
    (-75.57129, 39.5273) is the NORTHERN TIDE GATE, broken open (port_penn_slr_study_2016.pdf: "not operational ...
    equalizes water levels between the Delaware River and the pond"; user 11-14: open, two-way, BOTH beds). The ring
    is cut into two open pieces, `_gate_open_2026-11-16_a` (vertices 0-816) and `_b` (818-901, ends on vertex 0), so
    segments 816-817-818 (x 450950, y 4375415 -> 4375445, 30 m of line on the river-side toe, crest 2.82) are gone.
    They are the only segments crossing the nj2 link that runs through the dike's lidar dip (crest 1.34 m at
    450939, 4375420; 50 m faces, pond face -> river face, uv_zmin -0.11 on both beds). Segment order is unchanged,
    so every other link keeps the crest the engine gave it. The rest of r1054's dike is as before.
"""
import hashlib
import sys
from pathlib import Path

import numpy as np

R = Path("/cache/home/tpj8/nj_bight_sfincs")
H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
sys.path.insert(0, str(R / "logs/refreeze_2026-10-06/structures"))
import ridge  # noqa: E402
from weir_on_mesh import read_weir  # noqa: E402

SRC = R / "logs/weirs_dikes_levees_2026-11-12"
OUT = R / "data/nj2_design/structures"
PREMIER_WEIR = R / "data/structures_v4/sfincs_overpeck_open_elizabeth_rahway_ground.weir"
assert hashlib.md5(PREMIER_WEIR.read_bytes()).hexdigest() == "e11966fcab8b91f2e22583c8733a4dbf"
assert hashlib.md5((SRC / "cand_recommended.weir").read_bytes()).hexdigest().startswith("bbc2af85")


def blocks(path):
    """[(name, text_block)] verbatim, in file order."""
    ln = Path(path).read_text().splitlines(keepends=True)
    out, i = [], 0
    while i < len(ln):
        if not ln[i].strip():
            i += 1
            continue
        nr = int(ln[i + 1].split()[0])
        out.append((ln[i].strip(), "".join(ln[i:i + 2 + nr])))
        i += 2 + nr
    return out


def block(name, rows):
    s = f"{name}\n{len(rows)} 4\n"
    return s + "".join(f"{x:.1f} {y:.1f} {c:.3f} 0.60\n" for x, y, c in rows[:, :3])


W = dict(read_weir(SRC / "cand_recommended.weir"))
new = {}

# 1. Chester
ch = read_weir(H / "chester_redraw.weir")[0]
new["chester_nld4805000005_00"] = block(ch[0], ch[1])

# 2. Forsythe SW corner
F = W["forsythe_brigantine_r1303_p0_r60"]
assert np.allclose(F[586, :2], (547802.5, 4368425.0)) and np.allclose(F[595, :2], (547875.0, 4368375.0)), F[[586, 595]]
fr = ridge.trace(str(H / "forsythe_sw_cudem_utm3m.npz"), (547700, 4368440), (547980, 4368270), step=10, half=40)
fr = fr[(fr[:, 0] >= 547802.0) & (fr[:, 0] <= 547880.0)]
F2 = np.vstack([F[:587, :3], fr, F[595:, :3]])
new["forsythe_brigantine_r1303_p0_r60"] = block("forsythe_brigantine_r1303_p0_r60_sw_2026-11-14", F2)

# 3. Tuckahoe region 1286
Tk = W["tuckahoe_wma_r1286_p0_r60"]
assert np.allclose(Tk[256, :2], (523950.0, 4347225.0)) and np.allclose(Tk[377, :2], (524200.0, 4347420.0)), Tk[[256, 377]]
tr = ridge.trace(str(H / "tuckahoe_1286_wide_cudem_utm3m.npz"), (523860, 4347170), (524230, 4347460), step=15, half=30)
tr = tr[8:28]  # x 523962 .. 524191: from the staircase's touch on the dike to the NE dike
T2 = np.vstack([Tk[:257, :3], tr, Tk[377:, :3]])
new["tuckahoe_wma_r1286_p0_r60"] = block("tuckahoe_wma_r1286_p0_r60_ridge_2026-11-14", T2)

# 5. r1054 northern tide gate (Port Penn): open the line at the gate
P = W["dbay_de_newcastle_r1054_r1054_p0_r60"]
assert len(P) == 902 and np.allclose(P[0, :2], P[-1, :2]), "r1054 ring changed"
assert np.allclose(P[816:819, :2], [(450950.0, 4375415.0), (450950.0, 4375430.0), (450950.0, 4375445.0)]), P[816:819]
pa, pb = P[:817, :3], P[818:, :3]
new["dbay_de_newcastle_r1054_r1054_p0_r60"] = (block("dbay_de_newcastle_r1054_r1054_p0_r60_gate_open_2026-11-16_a", pa)
                                              + block("dbay_de_newcastle_r1054_r1054_p0_r60_gate_open_2026-11-16_b", pb))
print(f"r1054: ring of {len(P)} -> open pieces {len(pa)} + {len(pb)} vertices; gap {pa[-1, :2]} -> {pb[0, :2]} "
      f"({np.hypot(*(pb[0, :2] - pa[-1, :2])):.0f} m), crest removed {P[816:819, 2].max():.2f}")

for k, a, b in (("forsythe", F, F2), ("tuckahoe 1286", Tk, T2)):
    print(f"{k}: {len(a)} -> {len(b)} vertices; inserted crest {b[:, 2].min():.2f}..")
print(f"forsythe detour crest {fr[:, 2].min():.2f}-{fr[:, 2].max():.2f}; tuckahoe ridge {tr[:, 2].min():.2f}-"
      f"{tr[:, 2].max():.2f}")

out_blocks, changed = [], []
for name, txt in blocks(SRC / "cand_recommended.weir") + blocks(SRC / "cand_cohansey_gate.weir"):
    if name in new:
        out_blocks.append(new[name])
        changed.append(name)
    else:
        out_blocks.append(txt)
assert sorted(changed) == sorted(new), changed
set_txt = "".join(out_blocks)
(OUT / "dikes_levees_cohansey_set_nj2.weir").write_text(set_txt)
full = PREMIER_WEIR.read_text()
if not full.endswith("\n"):
    full += "\n"
(OUT / "sfincs_overpeck_open_elizabeth_rahway_dikes_levees_cohansey_nj2.weir").write_text(full + set_txt)
for f in ("dikes_levees_cohansey_set_nj2.weir", "sfincs_overpeck_open_elizabeth_rahway_dikes_levees_cohansey_nj2.weir"):
    b = (OUT / f).read_bytes()
    print(f, hashlib.md5(b).hexdigest(), len(read_weir(OUT / f)), "polylines")
