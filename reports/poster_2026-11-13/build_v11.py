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
# Atlantic City, STAP Table 4) = the "< 17 % chance exceeds" value for 2100 under SSP2-4.5 (STAP Table 5: 3.8 ft);
# ~1.07 m above 2026 (+0.148 m since 1992). Counts (logs/slr_assets_2026-11-13/README.md, 11-15): + 1.22 m: typical
# high 22 touched / 3 >= half wet, month max (17 Oct 2012 spring tide) 27 / 6; today (msl2026): 1 touched (PSEG
# Sewaren 0.1 %, a bank-face artefact) / 0 >= half. Wording fixes from the Fable audit
# (logs/poster_audit_2026-11-15/AUDIT.md, items 1-11; the title is the user's call and is unchanged).
sub("Abstract text", 0, 0,
    f"nearly one-third of New Jersey assets in the domain (52 of{NB}182) would flood if Sandy struck today's coast, "
    f"while 1.2{NB}m of sea-level rise alone would put 22 of them in water on a typical high tide",
    f"more than a quarter of New Jersey assets in the domain (52 of{NB}182) would have flood water on site if Sandy "
    f"struck today's coast (preliminary), while sea level about 1.1{NB}m above today's (the top of the likely 2100 "
    "range under intermediate emissions) would put water on up to 22 of them at a typical high tide")
sub("Abstract text", 0, 0, "built on the computationally efficient SFINCS flood model:", "built on the fast SFINCS flood model:")
for r in by["Abstract text"].text_frame.paragraphs[0].runs:
    r.font.size = Pt(25)
sub("Introduction text", 0, 0,
    "and most coastal flood models are too slow to produce simulations efficiently.",
    "and detailed coastal flood models are often too slow to run many cases.")
sub("Introduction text", 1, 0, "NJ-SFINCS is the first SFINCS model", "To our knowledge, NJ-SFINCS is the first SFINCS model")
sub("Experiments text", 1, 1,
    f"and 1.2{NB}m of sea-level rise with no storm (a month of modelled tides; the typical daily high tide).",
    f"and sea level 1.2{NB}m above its 1983–2001 average with no storm (a month of modelled tides: the typical daily "
    "high tide and the month's highest).")
sub("Results 1 findings", 1, 1,
    f"at 40 gauges, Newark Bay to Cape May and up the Delaware to Philadelphia, the peak is within 0.25{NB}m at 85{NB}% "
    f"(RMSE{NB}0.23{NB}m, 0.10{NB}m low), timed to about half an hour.",
    f"at the 40 gauges with a usable crest record, Newark Bay to Cape May and up the Delaware to Philadelphia, the peak "
    f"is within 0.25{NB}m at 85{NB}% (RMSE{NB}0.23{NB}m, 0.10{NB}m low); median timing error about half an hour.")
sub("Results 1 findings", 2, 1,
    f"NJ-SFINCS floods more than{NB}86{NB}% of the New Jersey land FEMA mapped as flooded by Sandy's surge",
    f"NJ-SFINCS floods more than{NB}86{NB}% of the land FEMA mapped as flooded by Sandy's surge inside the model's "
    "New Jersey area")
sub("Results 1 findings", 3, 1,
    f"71 of the 113{NB}km² the model floods and FEMA does not are rain ponds cut off from the sea; without rain, CSI "
    "is 0.82.",
    f"of the 113{NB}km² the model floods and FEMA does not, 71 have no wet path to the sea, mostly rain ponds; without "
    "rain, CSI is 0.82 (though some real flooding is lost too).")
sub("Caption 2", 0, 1,
    "The big misses are five marks behind Deal Lake and Wreck Pond, whose outlets the model holds shut "
    f"(RMSE{NB}0.24{NB}m without them).",
    f"Three ~2{NB}m misses sit behind Deal Lake and Wreck Pond, where Sandy breached the dune and the model's dune "
    f"holds (RMSE{NB}0.24{NB}m without the five marks there).")
sub("Results 2 findings", 2, 1,
    "23 of the 27 flooded substations are high-voltage (230 kV and above).",
    "27 substations flood, 23 of them high-voltage (230 kV and above, as most mapped substations are).")
sub("Results 2 findings", 3, 0, f"1.2{NB}m of sea-level rise, no storm: ",
    f"Sea level 1.2{NB}m above its 1983–2001 average, no storm (about 1.1{NB}m above today; the top of the likely "
    "2100 range under intermediate emissions, Kopp et al. 2025): ")
sub("Results 2 findings", 3, 1,
    "22 of the 182 sit in water on a typical high tide (a month of modelled tides, preliminary).",
    "on a typical high tide 3 of the 182 have at least half their ground under water, 6 on the month's highest "
    "spring tide, and up to 22 get some water on site; today, only a waterfront sliver of one (preliminary).")
sub("Conclusions text", 2, 0, "It turns floods into risk (Experiment 2): ", "It turns floods into exposure (Experiment 2): ")
sub("Conclusions text", 2, 1,
    f"nearly one-third of New Jersey's power plants and substations in the model (52 of{NB}182) would flood if Sandy "
    "struck today's coast, ",
    f"more than a quarter of New Jersey's power plants and substations in the model (52 of{NB}182) would have flood "
    "water on site if Sandy struck today's coast (preliminary), ")
refs = by["References text"].text_frame
assert refs.paragraphs[4].runs[0].text.startswith("FEMA Modeling Task Force")
assert refs.paragraphs[5].runs[0].text.startswith("Leijnse")
kopp = copy.deepcopy(refs.paragraphs[4]._p)
refs.paragraphs[4]._p.addnext(kopp)
refs.paragraphs[5].runs[0].text = (
    "Kopp, R.E., et al. (2025). New Jersey's Rising Seas and Changing Coastal Storms: Report of the 2025 Science "
    "and Technical Advisory Panel. Rutgers University, for NJDEP, Trenton, NJ.")
for para in by["Results 2 findings"].text_frame.paragraphs:   # with-FIAT copy: room for the FIAT bullet (no-FIAT resets to R2_PT)
    for r in para.runs:
        r.font.size = Pt(24)
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
for i in (3, 1):                       # left keeps bullets 0 + 2 (Sandy today, substations + plants)
    drop(left.text_frame.paragraphs[i]._p)
for i in (2, 0):                       # right keeps 1 + 3 (Newark Bay, sea level), balancing the column heights
    drop(right.text_frame.paragraphs[i]._p)
for box in (left, right):
    for para in box.text_frame.paragraphs:
        for r in para.runs:
            r.font.size = Pt(R2_PT)
        para.space_after = Pt(R2_PT * 0.33)

# Conclusions: no impact number; FIAT named in future work
sub("Conclusions text", 2, 1,
    "struck today's coast (preliminary), and the same depths feed building damage estimates. ",
    "struck today's coast (preliminary).")
drop(by["Conclusions text"].text_frame.paragraphs[2].runs[2]._r)
sub("Conclusions text", 3, 1, "building damage for each scenario;", "building damage (Delft-FIAT) for each scenario;")

all_txt = " ".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame)
stubs = [t for t in ("[FIAT", "[add the impact", "[inventory]", "[to be added]", "[caption") if t in all_txt]
assert not stubs, stubs
p.save(OUT)
print("saved v11 (no FIAT) ->", OUT, "; with FIAT stubs ->", OUT_FIAT)
