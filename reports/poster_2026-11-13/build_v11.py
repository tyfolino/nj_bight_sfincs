"""Poster v10 -> v11 (2026-11-15): FIAT OUT for Monday's print (user 11-15: Nithila has issues).

Writes two files from the v10 poster:
  poster_draft_2026-11-13_withFIAT.pptx  v10 + the edits common to both (today's-tide baseline), FIAT stubs in place
  poster_draft_2026-11-13.pptx            v11, no FIAT: Fig 4 box / bullets / caption removed, Results 2 findings
                                          in two columns where the box was, Impact-model row dropped, FIAT wording
                                          out of the abstract, Experiment 2, Results 2 heading and Conclusion 3.
Reads the archived v10 (drafts/), so it can be re-run. Python: /scratch/tpj8/envs/pptx.
"""
import copy

from pptx import Presentation
from pptx.util import Inches, Pt

V10 = "drafts/poster_draft_2026-11-13_v10.pptx"
OUT = "poster_draft_2026-11-13.pptx"
OUT_FIAT = "poster_draft_2026-11-13_withFIAT.pptx"
R2_PT = 28                             # Results 1 is at 28 (build_v10.py)

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


# ---- edits for BOTH versions -------------------------------------------------------------------
# Today's-tide baseline for the sea-level-rise count (logs/slr_assets_2026-11-13/results/
# v11modernb_{tidal0ft,msl2026_0ft}_mhh_summary.txt, 11-15): 1 of 182 on either datum (PSEG Sewaren, 0.1 % of its land)
# 1.2 m above MHHW of the 1983-2001 datum = 3.8 ft above the 2025 NJ STAP's 2005 (1995-2014) baseline (+0.059 m at
# Atlantic City, STAP Table 4) = the "< 17 % chance exceeds" value for 2100 under SSP2-4.5 (STAP Table 5: 3.8 ft).
# Counts (logs/slr_assets_2026-11-13/README.md, 11-15): typical high tide, + 1.22 m: 22 touched / 3 >= half wet;
# today (msl2026): 1 touched (PSEG Sewaren 0.1 %, a bank-face artefact: model high tide 0.15-0.45 m above the
# adjacent channel) / 0 >= half wet.
sub("Results 2 findings", 3, 0, f"1.2{NB}m of sea-level rise, no storm: ",
    f"1.2{NB}m of sea-level rise, no storm (3.8{NB}ft above the 2005 sea level: the top of New Jersey's likely "
    "range for 2100 under intermediate emissions; Kopp et al. 2025): ")
sub("Results 2 findings", 3, 1,
    "22 of the 182 sit in water on a typical high tide (a month of modelled tides, preliminary).",
    "on a typical high tide 22 of the 182 get water on some part of the site and 3 have at least half their "
    "ground under water; today none do (a month of modelled tides, preliminary).")
sub("Abstract text", 0, 0,
    f"while 1.2{NB}m of sea-level rise alone would put 22 of them in water on a typical high tide",
    f"while 1.2{NB}m of sea-level rise alone (the top of New Jersey's likely range for 2100 under intermediate "
    "emissions) would put water on 22 of them at a typical high tide")
refs = by["References text"].text_frame
assert refs.paragraphs[4].runs[0].text.startswith("FEMA Modeling Task Force")
assert refs.paragraphs[5].runs[0].text.startswith("Leijnse")
kopp = copy.deepcopy(refs.paragraphs[4]._p)
refs.paragraphs[4]._p.addnext(kopp)
refs.paragraphs[5].runs[0].text = (
    "Kopp, R.E., et al. (2025). New Jersey's Rising Seas and Changing Coastal Storms: Report of the 2025 Science "
    "and Technical Advisory Panel. Rutgers University, for NJDEP, Trenton, NJ.")
p.save(OUT_FIAT)

# ---- no-FIAT version only ------------------------------------------------------------------------

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
print("saved v11 (no FIAT) ->", OUT, "; with FIAT stubs ->", OUT_FIAT)
