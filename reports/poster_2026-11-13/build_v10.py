"""Poster v9 -> v10 (2026-11-14): gauge + waves bullets in Results 1; SLR count 'about 30 (still water)'
-> 22 (tidal model, typical daily high tide; logs/slr_assets_2026-11-13/results/v11modernb_tidal4ft_mhh_summary.txt)."""
import copy
import sys
from pptx import Presentation
from pptx.util import Pt

R1_PT = float(sys.argv[1]) if len(sys.argv) > 1 else 28
NB = "\xa0"
p = Presentation("poster_draft_2026-11-13.pptx")
s = p.slides[0]
by = {sh.name: sh for sh in s.shapes}


def sub(shape, para, run, old, new):
    r = by[shape].text_frame.paragraphs[para].runs[run]
    assert old in r.text, (shape, old)
    r.text = r.text.replace(old, new)


sub("Abstract text", 0, 0,
    f"while 1.2{NB}m of sea-level rise alone would flood about 30 at high tide (still-water estimate)",
    f"while 1.2{NB}m of sea-level rise alone would put 22 of them in water on a typical high tide")
sub("Experiments text", 1, 1,
    f"and 1.2{NB}m of sea-level rise at high tide (still water).",
    f"and 1.2{NB}m of sea-level rise with no storm (a month of modelled tides; the typical daily high tide).")
sub("Results 2 findings", 3, 1,
    "about 30 of the 182 sit in water at high tide (still-water estimate, preliminary).",
    "22 of the 182 sit in water on a typical high tide (a month of modelled tides, preliminary).")

# Results 1: insert 'Tide gauges' after the marks bullet, 'Waves matter' at the end
tf = by["Results 1 findings"].text_frame
tmpl = tf.paragraphs[0]._p


def new_para(after_p, bold, body):
    q = copy.deepcopy(tmpl)
    after_p.addnext(q)
    from pptx.text.text import _Paragraph
    para = _Paragraph(q, tf)
    para.runs[0].text, para.runs[1].text = bold, body
    return q


q = new_para(tf.paragraphs[0]._p, "Tide gauges: ",
             f"at 40 gauges, Newark Bay to Cape May and up the Delaware to Philadelphia, the peak is within "
             f"0.25{NB}m at 85{NB}% (RMSE{NB}0.23{NB}m, 0.10{NB}m low), timed to about half an hour.")
new_para(tf.paragraphs[-1]._p, "Waves matter: ",
         f"without them the peak drops about 0.2{NB}m on the ocean coast, at the inlets and in the NJ back "
         f"bays; the error at the marks grows from 0.35 to 0.53{NB}m (0.24 to 0.30{NB}m without the five lake "
         f"marks, where waves wash over the beach).")
for para in tf.paragraphs:
    for r in para.runs:
        r.font.size = Pt(R1_PT)
    para.space_after = Pt(R1_PT * 0.33)
p.save("poster_draft_2026-11-13.pptx")
print("saved v10, Results 1 at", R1_PT, "pt")
