"""Poster v11 -> v12 PROPOSAL (2026-11-15): trimmed to ~800 words, bigger Conclusions (user 11-15).

Reads the print file (v11, no FIAT) and writes drafts/poster_draft_2026-11-13_v12_proposal.pptx. It does NOT
overwrite the print file: the user edits the text by hand and takes what they like from this. No number changes,
only cuts; every Fable-audit qualifier (logs/poster_audit_2026-11-15/AUDIT.md) is kept in shorter words.
Python: /scratch/tpj8/envs/pptx.
"""
from pptx import Presentation
from pptx.util import Inches, Pt

SRC = "poster_draft_2026-11-13.pptx"
OUT = "drafts/poster_draft_2026-11-13_v12_proposal.pptx"
NB = "\xa0"

p = Presentation(SRC)
s = p.slides[0]
by = {sh.name: sh for sh in s.shapes}


def setp(shape, i, *texts, pt=None):
    """Replace paragraph i's run texts one-for-one (keeps each run's bold / colour)."""
    runs = by[shape].text_frame.paragraphs[i].runs
    assert len(runs) == len(texts), (shape, i, len(runs))
    for r, t in zip(runs, texts):
        r.text = t


def size(shape, pt):
    for para in by[shape].text_frame.paragraphs:
        for r in para.runs:
            r.font.size = Pt(pt)


def drop_para(shape, i):
    el = by[shape].text_frame.paragraphs[i]._p
    el.getparent().remove(el)


# ---- Abstract + Introduction: the print file's wording and sizes, unchanged (user 11-15: keep my wording) ----

# ---- Experiments (134 -> ~95) ----
setp("Experiments text", 0, "Experiment 1: Sandy test. ",
     "Sandy (28–31 Oct 2012) on 2012 ground, all forcing on. Scored against 119 USGS high-water marks (model peak "
     f"= median within 50{NB}m of each mark) and FEMA's mapped surge extent on New Jersey land (flooded = peak "
     f"depth ≥{NB}0.15{NB}m; CSI = overlap of the two flooded areas, 1 = perfect).")
setp("Experiments text", 1, "Experiment 2: power grid. ",
     "Today's 182 New Jersey power plants and substations in the model (OpenStreetMap outlines), in two cases: "
     "Sandy on today's ground and defences (2012 sea level and buildings), and sea level 1.2{NB}m above its "
     "1983–2001 average with no storm (a month of modelled tides). A site floods if any part is under "
     f"≥{NB}0.15{NB}m.".replace("{NB}", NB))
size("Experiments text", 26)

# ---- Captions (shorter) ----
setp("Caption 1", 0, "Fig 1. NJ-SFINCS and its Sandy flood extent. ",
     "(a) The model grid and its inputs. (b) Peak flood extent vs FEMA's mapped surge, New Jersey land only; "
     "insets at 15 m with local CSI. Orange in C = building footprints (solid in the model). FEMA's map stops "
     "abruptly at Jersey City and Bayonne, so model flooding there scores as a false alarm.")

# ---- Results 1 (188 -> ~120) ----
R1 = "Results 1 findings"
setp(R1, 0, "High-water marks: ", f"RMSE 0.35{NB}m, bias −0.07{NB}m at 119 USGS marks; 93{NB}% within ±0.5{NB}m (Fig 2).")
setp(R1, 1, "Tide gauges: ",
     f"at 40 gauges with a usable crest record, Newark Bay to Cape May and Philadelphia, the peak is within "
     f"0.25{NB}m at 85{NB}% (RMSE 0.23{NB}m); median timing error about 30 minutes.")
setp(R1, 2, "FEMA's surge map: ",
     f"the model floods more than 86{NB}% of the land FEMA mapped as flooded inside its New Jersey area "
     f"(CSI{NB}0.80, FAR{NB}0.09; Fig 1b).")
setp(R1, 3, "False alarms: ",
     f"71 of the 113{NB}km² the model floods and FEMA does not have no wet path to the sea, mostly rain ponds; "
     f"without rain, CSI{NB}0.82 (some real flooding is lost too).")
setp(R1, 4, "Waves matter: ",
     f"without them, peaks drop about 0.2{NB}m on the ocean coast, inlets and back bays, and the mark RMSE grows "
     f"from 0.35 to 0.53{NB}m.")
size(R1, 28)

# ---- Results 2 (180 -> ~125) ----
setp("Results 2 findings", 0, "Sandy on today's ground (preliminary): ",
     f"52 of the 182 sites flood (≥{NB}0.15{NB}m on any part); 26 have water over at least half their ground.")
setp("Results 2 findings", 1, "Substations and big plants: ",
     "27 substations flood, 23 of them 230 kV and above (as most mapped substations are). Four large gas-fired "
     "plants (Kearny, Linden, Sewaren, Sayreville) have water over 68–87 % of their ground, a median "
     f"1.3–2.2{NB}m deep.")
setp("Results 2 findings (2)", 0, "Newark Bay: ",
     "half of the flooded sites (26 of 52) are in Hudson, Bergen, Union and Essex counties.")
setp("Results 2 findings (2)", 1, f"Sea level 1.2{NB}m above its 1983–2001 average, no storm ",
     f"(about 1.1{NB}m above today; top of the likely 2100 range, intermediate emissions; Kopp et al. 2025): 3 "
     "sites have at least half their ground under water on a typical high tide, 6 on the month's highest spring "
     "tide, and up to 22 get some water. Today: a waterfront sliver of one (preliminary).")
size("Results 2 findings", 30)
size("Results 2 findings (2)", 30)

# ---- Conclusions: shorter, much bigger, wider box (References box narrowed to make room) ----
C = "Conclusions text"
setp(C, 0, "Fast: ", "a 72-hour storm in about 3 hours on one computer, so dozens of cases are practical.")
setp(C, 1, "Accurate for Sandy: ", f"0.35{NB}m RMSE at 119 marks; more than 86{NB}% of FEMA's surge extent.")
drop_para(C, 2)   # rebuilt below: setp needs the run layout, so edit the (now) 2nd and 3rd
setp(C, 2, "Next: ",
     "more storms and sea-level cases on today's ground; building damage (Delft-FIAT); Model 2.0 with the Hudson "
     f"waterfront and Upper Bay; finer Cape May inlets (back bays read about 0.2{NB}m low).")
import copy  # noqa: E402

exposure = copy.deepcopy(by[C].text_frame.paragraphs[1]._p)
by[C].text_frame.paragraphs[1]._p.addnext(exposure)
setp(C, 2, "Useful: ",
     "if Sandy struck today, 52 of New Jersey's 182 modelled power plants and substations would have flood water "
     "on site, half of them around Newark Bay (preliminary).")
size(C, 30)
for para in by[C].text_frame.paragraphs:
    para.space_after = Pt(12)

split = Inches(31.0)                    # Conclusions | References boundary (was 26.9)
for n in ("Panel Conclusions", "Heading Conclusions"):
    by[n].width = split - Inches(0.6) - by[n].left
by[C].width = split - Inches(0.9) - by[C].left
for n in ("Panel References", "Heading References"):
    by[n].left = split
    by[n].width = Inches(47.31) - split
by["References text"].left = split + Inches(0.3)
by["References text"].width = Inches(47.0) - split - Inches(0.3)

refs = by["References text"].text_frame.paragraphs
assert refs[0].runs[0].text.startswith("Blake, E.S.") and refs[7].runs[0].text.startswith("McCallum, B.E.")
refs[0].runs[0].text = refs[0].runs[0].text.replace(
    "Blake, E.S., Kimberlain, T.B., Berg, R.J., Cangialosi, J.P., Beven, J.L. II (2013)", "Blake, E.S., et al. (2013)")
mc = refs[7].runs[0].text
refs[7].runs[0].text = "McCallum, B.E., et al." + mc[mc.index(" (20"):]
size("References text", 17)

words = sum(len(sh.text_frame.text.split()) for sh in s.shapes
            if sh.has_text_frame and sh.name not in ("Title 1", "References text"))
words += sum(len(c.text.split()) for r in by["Setup table"].table.rows for c in r.cells)
p.save(OUT)
print("saved", OUT, "| words excl. title + references:", words)
