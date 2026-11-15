"""Poster v12 WITH FIAT (2026-11-15): the v12 proposal + one Delft-FIAT figure slot, bullet and caption in Results 2.

User 11-15: Nithila will drop in her plot and text on Monday. Our Results 2 findings are trimmed to one column of
three bullets to make room. The FIAT text boxes are copied from the v11 with-FIAT file (same fonts), then moved and
cut to one bullet. Run build_v12_proposal.py first. Output: drafts/poster_draft_2026-11-13_v12_withFIAT.pptx.
Python: /scratch/tpj8/envs/pptx.
"""
import copy

from pptx import Presentation
from pptx.util import Inches, Pt

SRC = "drafts/poster_draft_2026-11-13_v12_proposal.pptx"
FIAT_SRC = "poster_draft_2026-11-13_withFIAT.pptx"
OUT = "drafts/poster_draft_2026-11-13_v12_withFIAT.pptx"
NB = "\xa0"
PT = 26

p = Presentation(SRC)
s = p.slides[0]
by = {sh.name: sh for sh in s.shapes}
src = {sh.name: sh for sh in Presentation(FIAT_SRC).slides[0].shapes}


def setp(shape, i, *texts):
    runs = by[shape].text_frame.paragraphs[i].runs
    assert len(runs) == len(texts), (shape, i, len(runs))
    for r, t in zip(runs, texts):
        r.text = t


def sub(shape, para, run, old, new):
    r = by[shape].text_frame.paragraphs[para].runs[run]
    assert old in r.text, (shape, old)
    r.text = r.text.replace(old, new)


def drop(el):
    el.getparent().remove(el)


def box(shape, x, y, w, h):
    shape.left, shape.top, shape.width, shape.height = Inches(x), Inches(y), Inches(w), Inches(h)


# ---- FIAT wording outside Results 2 (the user's v10 wording where there was one) ----
sub("Abstract text", 0, 0,
    "; the same flood depths are being coupled with an impact model to estimate damage to individual buildings.",
    "; we also couple these flood depths with an impact model to estimate damage to individual buildings.")
sub("Experiments text", 1, 0, "Experiment 2: power grid. ", "Experiment 2: power grid and buildings. ")
sub("Experiments text", 1, 1, f"under ≥{NB}0.15{NB}m.",
    f"under ≥{NB}0.15{NB}m. Delft-FIAT turns the same depths into building damage.")
sub("Heading Results2", 0, 0, "Results 2: Power grid", "Results 2: Power grid and buildings")
sub("Conclusions text", 3, 1, "building damage (Delft-FIAT);", "building damage for each scenario;")

# ---- our findings: one column, three bullets ----
L, R = "Results 2 findings", "Results 2 findings (2)"
setp(L, 0, "Sandy on today's ground (preliminary): ",
     f"52 of the 182 sites flood (≥{NB}0.15{NB}m on any part), 26 over at least half their ground; half are "
     "around Newark Bay.")
setp(L, 1, "Substations and big plants: ",
     "27 substations flood, 23 at 230 kV and above (as most are). Four large gas plants (Kearny, Linden, "
     "Sewaren, Sayreville) have water over 68–87 % of their ground.")
sea = copy.deepcopy(by[R].text_frame.paragraphs[1]._p)
by[L].text_frame.paragraphs[1]._p.addnext(sea)
setp(L, 2, f"Sea level about 1.1{NB}m above today's, no storm ",
     "(top of the likely 2100 range, intermediate emissions; Kopp et al. 2025): 3 sites at least half under water "
     "at a typical high tide, 6 at the spring tide; up to 22 get some water.")
drop(by[R]._element)
FIG_W = 12.2                           # Fig 3 shrunk from 13.39 in wide to give the FIAT slot room
f3 = by["Figure 3"]
f3.height = int(f3.height * FIG_W * 914400 / f3.width)
f3.width = Inches(FIG_W)
box(by["Caption 3"], 14.2, 20.25 + f3.height / 914400 + 0.1, FIG_W, 1.4)
box(by[L], 26.75, 20.25, 8.7, 7.0)
for para in by[L].text_frame.paragraphs:
    for r in para.runs:
        r.font.size = Pt(PT)
    para.space_after = Pt(PT * 0.33)

# ---- FIAT slot: figure placeholder, one bullet, caption (x 35.75-47.0) ----
tree = s.shapes._spTree
new = {}
for n in ("FIAT placeholder", "FIAT bullets", "Caption 4"):
    el = copy.deepcopy(src[n]._element)
    tree.append(el)
    new[n] = [sh for sh in s.shapes if sh._element is el][0]
x, w = 35.75, 11.25
box(new["FIAT placeholder"], x, 20.25, w, 4.6)
box(new["FIAT bullets"], x + 0.1, 24.95, w - 0.2, 1.0)
box(new["Caption 4"], x, 26.1, w, 1.2)
fb = new["FIAT bullets"].text_frame
drop(fb.paragraphs[1]._p)
for r in fb.paragraphs[0].runs:
    r.font.size = Pt(PT)
fb.paragraphs[0].runs[0].text = "[FIAT finding + number]"
for extra in fb.paragraphs[0].runs[1:]:
    drop(extra._r)

all_txt = " ".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame)
assert "[FIAT finding" in all_txt and "[caption" in all_txt
p.save(OUT)
print("saved", OUT)
