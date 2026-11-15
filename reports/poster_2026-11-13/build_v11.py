"""Poster v10 -> v11 (2026-11-15): FIAT OUT for Monday's print (user 11-15: Nithila has issues).

Writes two files from the v10 poster:
  poster_draft_2026-11-13_withFIAT.pptx  v10 untouched, FIAT stubs in place (fill when results arrive)
  poster_draft_2026-11-13.pptx            v11, no FIAT: Fig 4 box / bullets / caption removed, Results 2 findings
                                          in two columns where the box was, Impact-model row dropped, FIAT wording
                                          out of the abstract, Experiment 2, Results 2 heading and Conclusion 3.
Reads the archived v10 (drafts/), so it can be re-run. Python: /scratch/tpj8/envs/pptx.
"""
import copy
import shutil

from pptx import Presentation
from pptx.util import Inches, Pt

V10 = "drafts/poster_draft_2026-11-13_v10.pptx"
OUT = "poster_draft_2026-11-13.pptx"
R2_PT = 28                             # Results 1 is at 28 (build_v10.py)
shutil.copy2(V10, "poster_draft_2026-11-13_withFIAT.pptx")

NB = "\xa0"
p = Presentation(V10)
s = p.slides[0]
by = {sh.name: sh for sh in s.shapes}


def sub(shape, para, run, old, new):
    r = by[shape].text_frame.paragraphs[para].runs[run]
    assert old in r.text, (shape, old)
    r.text = r.text.replace(old, new)


def drop(el):
    el.getparent().remove(el)


# Abstract: the coupling is in progress, not done
sub("Abstract text", 0, 0,
    "; we also couple these flood depths with an impact model to estimate damage to individual buildings.",
    "; the same flood depths are being coupled with an impact model to estimate damage to individual buildings.")

# Methods: drop the Impact-model row, close the gap
tbl = by["Setup table"].table
row = tbl.rows[4]
assert row.cells[0].text == "Impact model"
h = row.height
drop(row._tr)
by["Setup table"].height -= h
by["Experiments text"].top -= Inches(0.7)
sub("Experiments text", 1, 0, "Experiment 2: power grid and buildings. ", "Experiment 2: power grid. ")
sub("Experiments text", 1, 1, " Delft-FIAT turns the same depths into building damage.", "")

# Results 2: heading, FIAT box out, findings in two columns over the freed width
sub("Heading Results2", 0, 0, "Results 2: Power grid and buildings", "Results 2: Power grid")
for n in ("FIAT placeholder", "FIAT bullets", "Caption 4"):
    drop(by[n]._element)
left = by["Results 2 findings"]
paras = left.text_frame.paragraphs
assert paras[4].runs[0].text == "[FIAT finding + number]"
drop(paras[4]._p)
x0, x1, gap = Inches(28.2), Inches(47.0), Inches(0.5)
w = (x1 - x0 - gap) // 2
right_el = copy.deepcopy(left._element)
left._element.addnext(right_el)
right = [sh for sh in s.shapes if sh._element is right_el][0]
right.name = "Results 2 findings (2)"
left.left, left.width = x0, w
right.left, right.width = x0 + w + gap, w
for i in (3, 2):                       # left keeps bullets 0-1 (today's ground, Newark Bay)
    drop(left.text_frame.paragraphs[i]._p)
for i in (1, 0):                       # right keeps 2-3 (substations + plants, sea-level rise)
    drop(right.text_frame.paragraphs[i]._p)
for box in (left, right):
    for para in box.text_frame.paragraphs:
        for r in para.runs:
            r.font.size = Pt(R2_PT)
        para.space_after = Pt(R2_PT * 0.33)

# Conclusions: no impact number; FIAT named in future work
sub("Conclusions text", 2, 1,
    "would flood if Sandy struck today's coast, and the same depths feed building damage estimates. ",
    "would flood if Sandy struck today's coast.")
drop(by["Conclusions text"].text_frame.paragraphs[2].runs[2]._r)
sub("Conclusions text", 3, 1, "building damage for each scenario;", "building damage (Delft-FIAT) for each scenario;")

all_txt = " ".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame)
stubs = [t for t in ("[FIAT", "[add the impact", "[inventory]", "[to be added]", "[caption") if t in all_txt]
assert not stubs, stubs
p.save(OUT)
print("saved v11 (no FIAT) ->", OUT, "; v10 with FIAT stubs -> poster_draft_2026-11-13_withFIAT.pptx")
