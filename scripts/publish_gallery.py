#!/usr/bin/env python
"""Collect every domain's run galleries into the static site (GitHub Pages).

Reads ``experiments/<domain>/metrics.csv`` and each ``experiments/<domain>/<arm>/gallery/``
(``nj_sfincs/gallery.py``) and writes a pure static site — HTML / CSS / a little vanilla
JS, no framework, no basemap tiles, no API keys — into ``--site`` (default
``~/sandy_flood_site`` (GitHub tyfolino/sandy-flood-model, the user 2026-10-19: the one public site), its own git repo: ``git init -b main`` when missing, NEVER committed
here; the user commits and pushes):

    index.html                     the domains
    <domain>/index.html            sortable arm table (metrics.csv) with flag badges
    <domain>/<arm>/index.html      one page per arm: run card, flags, figures, full row
    <domain>/compare.html          "view runs": one run's figures + scores (default), or two
                                   side by side / in one frame (click to swap)
                                   (or one frame, click to swap), plus a metric diff table
    <domain>/data.js               the data the compare page reads (works from file://)

Only PNGs and the manifests' text are copied (no rasters, no tiles), so the repo stays
small. Superseded PNGs and arm pages are removed in the same pass. Every page is marked
"preliminary research diagnostics".

    python scripts/publish_gallery.py                       # every domain with a gallery
    python scripts/publish_gallery.py --domains v4_refreeze,v3
    python scripts/publish_gallery.py --site /tmp/site_test

Light (no rasters): fine on a login node.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PRELIM = "Preliminary research diagnostics — not peer-reviewed results."
FIG_ORDER = (
    "zsmax",
    "flood_depth",
    "dzsmax",
    "hwm_map",
    "hwm_summary",
    "motf",
    "gauges",
    "gauge_peaks",
    "hm0",
)

#: The arm-table / compare-table headline columns: (key, label, format, better).
#: ``better`` is used only to colour a DIFFERENCE (never to rank): "low", "high", "zero".
HEADLINE = (
    ("hwm_n_scored", "HWM n", "d", None),
    ("hwm_n_dry_scored", "dry", "d", "low"),
    ("hwm_rmse_scored_m", "RMSE m", ".3f", "low"),
    ("hwm_bias_scored_m", "bias m", "+.3f", "zero"),
    ("hwm_within0.5_scored", "±0.5 m", ".0%", "high"),
    ("hwm_rmse_scored_excl_lake_blocked_m", "RMSE excl. lakes", ".3f", "low"),
    ("hwm_rmse_scored_excl_noted_m", "RMSE excl. noted", ".3f", "low"),
    ("motf_csi", "CSI", ".3f", "high"),
    ("motf_pod", "POD", ".3f", None),
    ("motf_far", "FAR", ".3f", "low"),
    ("motf_km2_excluded_boxes", "km² excl.", ",.0f", None),
)
LABELS = (
    "engine",
    "engine_seed",
    "snapwave_direction",
    "meteo",
    "infiltration",
    "subgrid",
    "wind_scale",
    "sea_level_offset",
    "extra_discharge",
    "extent_admissible",
)

CSS = """
:root{color-scheme:dark;--bg:#16181d;--surface:#1f2228;--rule:#30343c;
--ink:#e8eaf0;--ink-2:#b4b9c6;--ink-3:#8b91a0;
--blue:#a8d0ff;--lavender:#cdb8ff;--mint:#a8e6c4;--peach:#ffc9a8;--pink:#ffa8b8;
--body:"Atkinson Hyperlegible Next","Atkinson Hyperlegible",system-ui,sans-serif;
--mono:"Atkinson Hyperlegible Mono",ui-monospace,Menlo,Consolas,monospace}
*{box-sizing:border-box}
[hidden]{display:none!important}
body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.6 var(--body)}
a{color:var(--blue);text-underline-offset:2px}
code{font-family:var(--mono);font-size:.92em}
.wrap{max-width:1300px;margin:0 auto;padding:0 16px}
nav.crumbs{color:var(--ink-3);padding:14px 0 0;font-size:15px}
header.mast{padding:10px 0 16px;border-bottom:1px solid var(--rule)}
header.mast h1{font-size:30px;line-height:1.2;margin:0 0 6px;font-weight:700}
header.mast p{margin:0 0 6px;color:var(--ink-2);max-width:80ch}
.prelim{color:var(--lavender);font-size:15px}
section{padding:22px 0 4px}
section>h2{font-size:22px;margin:0 0 10px}
.note{color:var(--ink-3);font-size:15px;max-width:90ch}
table{border-collapse:collapse;width:100%;font-size:15px}
th,td{border-bottom:1px solid var(--rule);padding:6px 10px;text-align:left;vertical-align:top}
th{color:var(--ink-2);font-weight:700;white-space:nowrap;cursor:pointer}
th.num,td.num{text-align:right}
td.num{font-family:var(--mono);font-variant-numeric:tabular-nums;white-space:nowrap}
td.lbl{color:var(--ink-2);overflow-wrap:anywhere}
th[aria-sort=ascending]::after{content:" ▲"}th[aria-sort=descending]::after{content:" ▼"}
tr:hover td{background:var(--surface)}
.scroll{overflow-x:auto}
.badge{display:inline-block;font-size:13px;padding:0 6px;margin:1px 4px 1px 0;border-radius:4px;
border:1px solid currentColor;white-space:nowrap}
.badge.serious{color:var(--pink)}.badge.caution{color:var(--peach)}.badge.info{color:var(--ink-3)}
ul.flags{padding-left:20px;margin:0;max-width:100ch}
ul.flags li{margin:4px 0;color:var(--ink-2)}
ul.flags li.serious::marker{color:var(--pink)}ul.flags li.caution::marker{color:var(--peach)}
.tiles{display:flex;flex-wrap:wrap;gap:8px 28px}
.tile .num{font:700 22px var(--mono);font-variant-numeric:tabular-nums}
.tile .lbl{color:var(--ink-3);font-size:14px}
dl.card{display:grid;grid-template-columns:minmax(140px,max-content) 1fr;gap:4px 18px;margin:0;font-size:15px}
dl.card dt{color:var(--ink-3)}
dl.card dd{margin:0;overflow-wrap:anywhere}
figure{margin:0 0 32px}
figure h3{font-size:19px;margin:0 0 6px}
figure img{width:100%;height:auto;display:block;border-radius:4px}
figcaption{color:var(--ink-2);font-size:15px;max-width:100ch;margin-top:6px}
.skip{border:1px dashed var(--rule);color:var(--ink-3);padding:14px}
details summary{cursor:pointer;color:var(--blue)}
.ctl{display:flex;flex-wrap:wrap;gap:10px 20px;align-items:end;padding:12px 0}
.ctl label{display:grid;gap:4px;color:var(--ink-3);font-size:15px}
select,button{font:16px var(--body);background:var(--surface);color:var(--ink);
border:1px solid var(--rule);border-radius:4px;padding:6px 10px}
button[aria-pressed=true]{background:var(--blue);color:var(--bg)}
select:focus-visible,button:focus-visible,th:focus-visible,a:focus-visible{outline:2px solid var(--blue);outline-offset:2px}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.pair .side h4{font-size:15px;color:var(--ink-2);margin:0 0 4px;font-weight:400}
.pair.one{grid-template-columns:1fr}
.diff.better{color:var(--mint)}.diff.worse{color:var(--pink)}
ul.next{padding-left:20px;max-width:90ch;margin:0}ul.next li{margin:6px 0;color:var(--ink-2)}
footer{margin-top:40px;border-top:1px solid var(--rule);padding:16px 0 40px;color:var(--ink-3);font-size:14px}
@media (max-width:820px){.pair{grid-template-columns:1fr}}
"""

SORT_JS = """
document.querySelectorAll('table.sortable').forEach(t=>{
 const ths=[...t.tHead.rows[0].cells];
 ths.forEach((th,i)=>{th.tabIndex=0;const go=()=>{
  const asc=th.getAttribute('aria-sort')!=='ascending';
  ths.forEach(h=>h.removeAttribute('aria-sort'));th.setAttribute('aria-sort',asc?'ascending':'descending');
  const rows=[...t.tBodies[0].rows];
  const key=r=>{const c=r.cells[i];const v=c.dataset.v;if(v!==undefined&&v!==''&&!isNaN(+v))return +v;
   return (c.textContent||'').trim().toLowerCase();};
  rows.sort((a,b)=>{const x=key(a),y=key(b);
   if(typeof x==='number'&&typeof y==='number')return asc?x-y:y-x;
   if(typeof x==='number')return -1;if(typeof y==='number')return 1;
   return asc?String(x).localeCompare(y):String(y).localeCompare(x);});
  rows.forEach(r=>t.tBodies[0].appendChild(r));};
  th.addEventListener('click',go);th.addEventListener('keydown',e=>{if(e.key==='Enter')go();});});
});
"""

COMPARE_JS = r"""
(function(){
const D=window.GALLERY_DATA, arms=Object.keys(D.arms).sort();
const selA=document.getElementById('armA'), selB=document.getElementById('armB');
const rowsEl=document.getElementById('figs'), tbl=document.getElementById('diff');
const head=document.getElementById('pairhead');
let mode=q0().get('m')||'one';
function q0(){return new URLSearchParams(location.hash.slice(1));}
arms.forEach(a=>{[selA,selB].forEach(s=>{const o=document.createElement('option');o.value=a;o.textContent=a;s.appendChild(o);});});
const q=new URLSearchParams(location.hash.slice(1));
let b=q.get('b')||arms.find(a=>a!==(D.reference||''))||arms[0];
let a=q.get('a')||(D.arms[b]&&D.arms[b].reference_arm)||D.reference||arms[0];
if(!D.arms[a])a=arms[0]; if(!D.arms[b])b=arms[Math.min(1,arms.length-1)];
selA.value=a; selB.value=b;
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fmt=(v,f)=>{if(v==null||v===''||(typeof v==='number'&&!isFinite(v)))return '—';
 if(typeof v!=='number')return esc(v);
 if(f==='d')return String(Math.round(v)); if(f.endsWith(',.0f'))return (f[0]==='+'&&v>=0?'+':'')+Math.round(v).toLocaleString('en-US'); if(f==='.0%')return (100*v).toFixed(0)+'%';
 if(f===',.0f')return Math.round(v).toLocaleString('en-US');
 const m=f.match(/(\+?)\.(\d)f/); if(m){const s=v.toFixed(+m[2]);return (m[1]&&v>=0?'+':'')+s;} return String(v);};
function badges(fl){return (fl||[]).map(f=>`<span class="badge ${f.level}" title="${esc(f.text)}">${f.level==='serious'?'!! ':f.level==='caution'?'! ':'i '}${esc(f.code)}</span>`).join('');}
function render(){
 a=selA.value;b=selB.value;history.replaceState(null,'','#a='+encodeURIComponent(a)+'&b='+encodeURIComponent(b)+'&m='+mode);
 const one=mode==='one';document.querySelectorAll('.onlypair').forEach(e=>{e.hidden=one;});
 document.querySelectorAll('[data-mode]').forEach(x=>x.setAttribute('aria-pressed',x.dataset.mode===mode));
 const A=D.arms[a],B=D.arms[b];
 const fa=(A.card.fingerprint||{}).sha,fb=(B.card.fingerprint||{}).sha;
 if(one){head.innerHTML=`<p class="note"><b>${esc(a)}</b> ${badges(A.flags)} · <a href="${esc(A.slug)}/index.html">run card and full metrics</a></p>`+
  `<p class="note">HWM numbers: estimator ${esc(A.metrics.hwm_estimator)}, radius ${esc(A.metrics.hwm_radius_m)} m.</p>`;}
 else head.innerHTML=`<p class="note">A <b>${esc(a)}</b> ${badges(A.flags)}<br>B <b>${esc(b)}</b> ${badges(B.flags)}</p>`+
  `<p class="note">${fa&&fa===fb?'Same domain fingerprint ('+esc(fa)+') — the two are on one mesh and bed.':'⚠️ Different fingerprints ('+esc(fa)+' vs '+esc(fb)+') — not the same model; do not difference.'}`+
  ` HWM numbers: estimator ${esc(A.metrics.hwm_estimator)} / ${esc(B.metrics.hwm_estimator)}, radius ${esc(A.metrics.hwm_radius_m)} / ${esc(B.metrics.hwm_radius_m)} m. A pooled difference is not a paired test — use scripts/paired_hwm_bootstrap.py.</p>`;
 if(one){let h='<thead><tr><th>metric</th><th class="num">value</th></tr></thead><tbody>';
  D.headline.forEach(([k,l,f])=>{h+=`<tr><td>${esc(l)} <span class="note">${esc(k)}</span></td><td class="num">${fmt(A.metrics[k],f)}</td></tr>`;});
  D.labels.forEach(k=>{h+=`<tr><td>${esc(k)}</td><td class="lbl">${esc((A.card.labels||{})[k])}</td></tr>`;});
  tbl.innerHTML=h+'</tbody>';}
 else{let h='<thead><tr><th>metric</th><th class="num">A</th><th class="num">B</th><th class="num">B − A</th></tr></thead><tbody>';
 D.headline.forEach(([k,l,f,better])=>{const x=A.metrics[k],y=B.metrics[k];
  let d='',cls='';if(typeof x==='number'&&typeof y==='number'&&isFinite(x)&&isFinite(y)){const dv=y-x;
   d=fmt(dv,f==='.0%'?'.0%':(f==='d'?'d':'+'+f.replace('+','')));
   if(better==='low')cls=dv<0?'better':dv>0?'worse':''; else if(better==='high')cls=dv>0?'better':dv<0?'worse':'';
   else if(better==='zero')cls=Math.abs(y)<Math.abs(x)?'better':Math.abs(y)>Math.abs(x)?'worse':'';}
  h+=`<tr><td>${esc(l)} <span class="note">${esc(k)}</span></td><td class="num">${fmt(x,f)}</td><td class="num">${fmt(y,f)}</td><td class="num diff ${cls}">${d}</td></tr>`;});
 D.labels.forEach(k=>{const x=(A.card.labels||{})[k],y=(B.card.labels||{})[k];
  h+=`<tr><td>${esc(k)}</td><td class="lbl">${esc(x)}</td><td class="lbl">${esc(y)}</td><td class="lbl">${String(x)===String(y)?'':'differs'}</td></tr>`;});
 tbl.innerHTML=h+'</tbody>';}
 const fA=Object.fromEntries((A.figures||[]).map(f=>[f.key,f])),fB=Object.fromEntries((B.figures||[]).map(f=>[f.key,f]));
 let out='';
 D.fig_order.forEach(k=>{const x=fA[k],y=fB[k];if(!x&&!y)return;const t=(x||y).title;
  const side=(f,arm,lab)=>{if(!f)return `<div class="side"><h4>${lab} · ${esc(arm)}</h4><div class="skip">not drawn</div></div>`;
   if(!f.file)return `<div class="side"><h4>${lab} · ${esc(arm)}</h4><div class="skip">${esc(f.skipped||f.error||'not drawn')}</div></div>`;
   return `<div class="side"><h4>${lab} · ${esc(arm)}</h4><a href="${esc(D.arms[arm].slug)}/${esc(f.file)}"><img loading="lazy" src="${esc(D.arms[arm].slug)}/${esc(f.file)}" alt="${esc(t)} — ${esc(arm)}"></a></div>`;};
  if(one){if(!x)return;out+=`<figure><h3>${esc(t)}</h3>${x.file?`<a href="${esc(D.arms[a].slug)}/${esc(x.file)}"><img loading="lazy" src="${esc(D.arms[a].slug)}/${esc(x.file)}" alt="${esc(t)} — ${esc(a)}"></a>`:`<div class="skip">${esc(x.skipped||x.error||'not drawn')}</div>`}<figcaption>${esc(x.caption||'')}</figcaption></figure>`;}
  else if(mode==='side'||!(x&&x.file&&y&&y.file)){
   out+=`<figure><h3>${esc(t)}</h3><div class="pair">${side(x,a,'A')}${side(y,b,'B')}</div><figcaption>${esc((y||x).caption||'')}</figcaption></figure>`;
  }else{
   out+=`<figure><h3>${esc(t)}</h3><div class="pair one"><div class="side"><h4 class="swaplab">A · ${esc(a)} — click the image to swap</h4><img class="swap" data-a="${esc(D.arms[a].slug)}/${esc(x.file)}" data-b="${esc(D.arms[b].slug)}/${esc(y.file)}" data-la="A · ${esc(a)}" data-lb="B · ${esc(b)}" src="${esc(D.arms[a].slug)}/${esc(x.file)}" alt="${esc(t)}" tabindex="0"></div></div><figcaption>${esc(y.caption||'')}</figcaption></figure>`;}
 });
 rowsEl.innerHTML=out;
 rowsEl.querySelectorAll('img.swap').forEach(im=>{const sw=()=>{const onA=im.getAttribute('src')===im.dataset.a;
  im.src=onA?im.dataset.b:im.dataset.a;im.parentNode.querySelector('.swaplab').textContent=(onA?im.dataset.lb:im.dataset.la)+' — click the image to swap';};
  im.addEventListener('click',sw);im.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();sw();}});});
}
selA.addEventListener('change',render);selB.addEventListener('change',render);
document.getElementById('swapAB').addEventListener('click',()=>{const t=selA.value;selA.value=selB.value;selB.value=t;render();});
document.querySelectorAll('[data-mode]').forEach(btn=>btn.addEventListener('click',()=>{mode=btn.dataset.mode;render();}));
render();
})();
"""


#: The plain-language "coming in the next premier" list, shown at the bottom of the home page
#: and of that domain's runs page. ⚠️ Edit it when the next premier lands (Phase 4, STATUS):
#: a stale list here gets believed.
NEXT_PREMIER = {
    "domain": "v4_refreeze",
    "as_of": "2026-10-20",
    "status": "Planned; queued as one batch of runs, not yet run.",
    "items": (
        "Repeatable waves: the wave model's random part is now seeded, so the same inputs "
        "give the same answer every time.",
        "Infragravity (IG) waves move the water: the long, slow waves under groups of "
        "ordinary waves are now fed into the water along the beach, so they raise the water "
        "level and push water ashore. Before, they were only calculated.",
        "Rain soaking in: an updated method for how much rain the ground absorbs, set for "
        "the soil conditions before Sandy.",
        "Air pressure from the ERA5 weather reanalysis, blended with the storm's wind field.",
        "Rivers enter in their channels: 12 river inflows moved off the banks and into "
        "the water.",
        "Lake beds fixed: 14 coastal lakes had a false ridge of land across them from an "
        "old elevation survey; it is removed.",
        "Creeks reopened: Beach Creek in North Wildwood (an old survey laid a false bank "
        "across it), and about 50 marsh creeks on the New Jersey Delaware Bay shore (about "
        "120 km of channel, Sluice and Dennis Creek among them) where the elevation data held "
        "the water surface instead of the creek bottom, so they could not drain at low tide. "
        "Their new bottoms are an assumption (about mean low water), not a survey.",
        "Tide gauges moved off dry ground: Cape May, Cape May Harbor and Barnegat Light sat "
        "on land in the model; each moved a few tens of metres into the water.",
        "Side runs in the same batch: two copies with a tiny change to measure the noise, "
        "waves off, no IG waves in the water, wetter and drier soil, no buildings, the Wreck Pond dune "
        "breach at two depths, waves overtopping into Deal Lake, and the older v3 model "
        "re-run on the same settings.",
    ),
}


def next_premier_section() -> str:
    n = NEXT_PREMIER
    items = "".join(f"<li>{esc(t)}</li>" for t in n["items"])
    return (
        f"<section><h2>Coming in the next premier ({esc(n['domain'])})</h2>"
        f'<p class="note">{esc(n["status"])} As of {esc(n["as_of"])}.</p>'
        f'<ul class="next">{items}</ul></section>'
    )


def esc(v) -> str:
    return html.escape("" if v is None else str(v))


def slug(arm: str) -> str:
    """A path-safe directory name for an arm ('+' and friends → '_')."""
    return re.sub(r"[^A-Za-z0-9._-]", "_", arm)


def num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def fmt(v, f: str) -> str:
    x = num(v)
    if x is None:
        return "—"
    if f == "d":
        return f"{int(round(x))}"
    return format(x, f)


def page(title: str, body: str, depth: int, desc: str = "") -> str:
    up = "../" * depth
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc or PRELIM)}">
<meta name="robots" content="noindex">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible+Next:wght@400;700&display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible+Mono:wght@400;700&display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{up}assets/site.css">
</head><body><div class="wrap">
{body}
<footer>{esc(PRELIM)} SFINCS compound-flood hindcast of Hurricane Sandy (28–31 Oct 2012),
New York Bight. Figures are made by <code>nj_sfincs/gallery.py</code> in the research repo
and collected by <code>scripts/publish_gallery.py</code>; every number is the scorer's or
the arm's <code>metrics.csv</code> row. Built {datetime.now():%Y-%m-%d %H:%M}.</footer>
</div><script src="{up}assets/sort.js"></script></body></html>
"""


def mast(kicker: str, h1: str, dek: str, crumbs: str = "") -> str:
    """``kicker`` is kept for the callers' signature; the simple layout does not show it."""
    return (
        (f'<nav class="crumbs">{crumbs}</nav>' if crumbs else "")
        + f'<header class="mast"><h1>{esc(h1)}</h1><p>{dek}</p>'
        f'<p class="prelim">{esc(PRELIM)}</p></header>'
    )


def badges(flags) -> str:
    mark = {"serious": "!! ", "caution": "! ", "info": "i "}
    return "".join(
        f'<span class="badge {esc(f["level"])}" title="{esc(f["text"])}">'
        f"{mark.get(f['level'], '')}{esc(f['code'])}</span>"
        for f in flags or []
    )


# ── reading ─────────────────────────────────────────────────────────────────────────


def read_domain(domain_name: str, exp_root: Path | None = None) -> dict:
    """{arm: entry} for one domain: every arm with a metrics row or a gallery."""
    import pandas as pd

    from nj_sfincs.gallery import GALLERY, MANIFEST, compute_flags

    root = (exp_root or ROOT / "experiments") / domain_name
    rows = {}
    csv = root / "metrics.csv"
    if csv.is_file():
        df = pd.read_csv(csv, index_col=0, low_memory=False)
        for arm, r in df.iterrows():
            rows[str(arm)] = {
                k: (
                    None
                    if (isinstance(v, float) and not math.isfinite(v))
                    else (v.item() if hasattr(v, "item") else v)
                )
                for k, v in r.items()
            }
    arms = {}
    names = set(rows)
    names |= {p.parent.parent.name for p in root.glob(f"*/{GALLERY}/{MANIFEST}")}
    for arm in sorted(names):
        mp = root / arm / GALLERY / MANIFEST
        man = json.loads(mp.read_text()) if mp.is_file() else None
        row = rows.get(arm) or (man or {}).get("metrics_row") or {}
        if man is None:
            # no gallery: the row's own labels are all there is
            flags = compute_flags(
                {
                    "extent_admissible": row.get("extent_admissible"),
                    "engine_seed": row.get("engine_seed"),
                    "engine": row.get("engine"),
                    "snapwave_direction": row.get("snapwave_direction"),
                    "audit_whole": True,
                }
            ) + [
                {
                    "code": "no_gallery",
                    "level": "info",
                    "text": "No gallery yet: python scripts/build_gallery.py --arms "
                    f"{arm}",
                }
            ]
            card = {"labels": {k: row.get(k) for k in LABELS}, "fingerprint": {}}
        else:
            flags, card = man["flags"], man["card"]
        if man is not None and arm not in rows:
            flags = flags + [
                {
                    "code": "not_in_metrics_csv",
                    "level": "caution",
                    "text": "This arm has a gallery but no current metrics.csv row.",
                }
            ]
        arms[arm] = {
            "manifest": man,
            "row": row,
            "flags": flags,
            "card": card,
            "slug": slug(arm),
            "dir": root / arm / GALLERY,
        }
    return arms


# ── writing ─────────────────────────────────────────────────────────────────────────


def copy_pngs(entry: dict, dst: Path) -> list[str]:
    dst.mkdir(parents=True, exist_ok=True)
    keep = []
    man = entry["manifest"] or {}
    for f in man.get("figures", []):
        if not f.get("file"):
            continue
        src = entry["dir"] / f["file"]
        if not src.is_file():
            continue
        out = dst / f["file"]
        if (
            not out.is_file()
            or out.stat().st_size != src.stat().st_size
            or (out.stat().st_mtime < src.stat().st_mtime)
        ):
            shutil.copy2(src, out)
        keep.append(f["file"])
    for old in dst.glob("*.png"):  # clean as you go: no superseded figure survives
        if old.name not in keep:
            old.unlink()
    return keep


def arm_page(domain_name: str, arm: str, e: dict, ref: str | None) -> str:
    man = e["manifest"] or {}
    card, row = e["card"], e["row"]
    fp = card.get("fingerprint") or {}
    tiles = "".join(
        f'<div class="tile"><div class="num">{fmt(row.get(k), f)}</div>'
        f'<div class="lbl">{esc(lbl)}</div></div>'
        for k, lbl, f, _ in HEADLINE
        if k in row
    )
    est = (
        f"{row.get('hwm_estimator', '?')}, radius {fmt(row.get('hwm_radius_m'), 'g')} m"
    )
    flags = (
        "".join(
            f'<li class="{esc(f["level"])}"><b>{esc(f["code"])}</b> — {esc(f["text"])}</li>'
            for f in e["flags"]
        )
        or "<li>No flags.</li>"
    )
    dl = []

    def add(k, v):
        if v not in (None, "", {}, []):
            dl.append(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>")

    add("domain", domain_name)
    add(
        "fingerprint",
        f"faces={fp.get('faces')} boundary_edges={fp.get('boundary_edges')}"
        f" sha={fp.get('sha')}"
        if fp.get("sha")
        else None,
    )
    add("fingerprint label", fp.get("label"))
    add("audit", (card.get("audit") or {}).get("summary"))
    for k, v in (card.get("labels") or {}).items():
        add(k, v)
    cfg = card.get("config") or {}
    add("waves", "on" if cfg.get("waves_on") else "off" if cfg else None)
    add("window", f"{cfg.get('tstart')} → {cfg.get('tstop')}" if cfg else None)
    eng = card.get("engine") or {}
    add("engine build", eng.get("build_revision"))
    add(
        "solve host / job",
        f"{eng.get('host')} / {eng.get('job_id')} ({eng.get('threads')} threads)"
        if eng
        else None,
    )
    w = card.get("wall") or {}
    if w:
        add(
            "wall",
            f"sfincs.log total {fmt(w.get('total_time_s'), ',.0f')} s, SnapWave "
            f"{fmt(w.get('time_in_snapwave_s'), ',.0f')} s; sacct {w.get('elapsed')} "
            f"{w.get('state')} on {w.get('nodelist')}",
        )
    rs = card.get("restart") or {}
    if rs:
        add(
            "restarts",
            f"{rs.get('resumes', 0)} resume(s)"
            + ("; soil state RESET" if rs.get("soil_reset") else ""),
        )
        add("restart_history.txt", " | ".join(rs.get("lines") or []))
    if card.get("labels_row_differs"):
        add(
            "metrics.csv labels that differ from the live read",
            json.dumps(card["labels_row_differs"]),
        )
    add(
        "gallery built",
        f"{man.get('built')} on {man.get('host')} "
        f"({man.get('seconds')} s, peak RSS {man.get('peak_rss_gb')} GB)"
        if man
        else None,
    )
    add("reference arm", man.get("reference_arm") or ref)
    figs = []
    for f in man.get("figures", []):
        sc = f.get("selfcheck") or {}
        chk = ""
        if "reproduces_row_4dp" in sc:
            ok = sc["reproduces_row_4dp"]
            chk = (
                " <b>Self-check:</b> the figure's numbers "
                + (
                    "reproduce"
                    if ok
                    else "do NOT reproduce"
                    if ok is False
                    else "could not be checked against"
                )
                + " the metrics.csv row to 4 dp."
            )
        if f.get("file"):
            im = (
                f'<a href="{esc(f["file"])}"><img loading="lazy" src="{esc(f["file"])}" '
                f'alt="{esc(f["title"])} — {esc(arm)}"></a>'
            )
        else:
            im = f'<div class="skip">{esc(f.get("skipped") or f.get("error"))}</div>'
        figs.append(
            f'<figure id="{esc(f["key"])}"><h3>{esc(f["title"])}</h3>{im}'
            f"<figcaption>{esc(f.get('caption', ''))}{chk}</figcaption></figure>"
        )
    if not figs:
        figs.append(
            '<div class="skip">No gallery for this arm yet — '
            f"<code>NJ_DOMAIN={esc(domain_name)} python scripts/build_gallery.py "
            f"--arms {esc(arm)}</code></div>"
        )
    full = "".join(
        f"<tr><td>{esc(k)}</td><td class='lbl'>{esc(v)}</td></tr>"
        for k, v in row.items()
    )
    cmp_link = f"../compare.html#a={esc(ref or '')}&amp;b={esc(arm)}&amp;m=side"
    body = (
        mast(
            f"<b>{esc(domain_name)}</b> · arm",
            arm,
            f"Run card, flags and the standard figure set. HWM numbers: estimator {esc(est)}."
            f" <a href='{cmp_link}'>Compare with {esc(ref)}</a>",
            f'<a href="../../index.html">runs</a> / <a href="../index.html">'
            f"{esc(domain_name)}</a> / {esc(arm)}",
        )
        + f'<section><h2>Flags</h2><ul class="flags">{flags}</ul></section>'
        + f'<section><h2>Headline</h2><div class="tiles">{tiles}</div>'
        f'<p class="note">HWM: estimator {esc(est)}, q ≤ 2, dry marks scored at ground '
        "(the <code>_scored</code> keys). CSI / POD / FAR on sheet-valid land; km² excl. = "
        "<code>motf_km2_excluded_boxes</code>.</p></section>"
        + f'<section><h2>Run card</h2><dl class="card">{"".join(dl)}</dl></section>'
        + f"<section><h2>Figures</h2>{''.join(figs)}</section>"
        + f"<section><h2>Full metrics.csv row</h2><details><summary>{len(row)} columns"
        f'</summary><div class="scroll"><table>{full}</table></div></details></section>'
    )
    return page(
        f"{arm} · {domain_name}", body, 2, f"Run gallery for {arm} on {domain_name}"
    )


def domain_index(domain_name: str, arms: dict, ref: str) -> str:
    """The arm table, kept short: the per-arm labels (engine, meteo, subgrid, ...) live on
    each arm's page. A measure every row shares is stated once above the table; it gets
    a column only when the rows differ."""
    rows = [e["row"] for e in arms.values()]

    def measure(r):
        return f"{r.get('hwm_estimator', '?')} · {fmt(r.get('hwm_radius_m'), 'g')} m"

    measures = {measure(r) for r in rows}
    excl = {fmt(r.get("motf_km2_excluded_boxes"), ",.0f") for r in rows}
    cols = [
        c
        for c in HEADLINE
        if not (c[0] == "motf_km2_excluded_boxes" and len(excl) == 1)
        and any(num(r.get(c[0])) is not None for r in rows)  # no all-blank columns
    ]
    heads = "".join(f'<th class="num">{esc(lbl)}</th>' for _, lbl, _, _ in cols)
    trs = []
    for arm, e in arms.items():
        r = e["row"]
        cells = "".join(
            f'<td class="num" data-v="{num(r.get(k)) if num(r.get(k)) is not None else ""}">'
            f"{fmt(r.get(k), f)}</td>"
            for k, _, f, _ in cols
        )
        lab = e["card"].get("labels") or {}
        cfg = e["card"].get("config") or {}
        waves = "on" if cfg.get("waves_on") else ("off" if cfg else "?")
        trs.append(
            f'<tr><td><a href="{esc(e["slug"])}/index.html">{esc(arm)}</a>'
            f"{' <span class=note>(reference)</span>' if arm == ref else ''}</td>"
            f"<td>{badges(e['flags'])}</td>"
            + (f"<td class='lbl'>{esc(measure(r))}</td>" if len(measures) > 1 else "")
            + f"<td class='lbl'>{esc(waves)}</td>"
            f"<td class='lbl'>{esc(lab.get('infiltration', r.get('infiltration')))}</td>"
            f"{cells}</tr>"
        )
    shared = []
    if len(measures) == 1:
        shared.append(f"HWM measure for every row: <b>{esc(next(iter(measures)))}</b>.")
    if len(excl) == 1:
        shared.append(
            f"CSI / POD / FAR exclude {esc(next(iter(excl)))} km² of boxes where the MOTF "
            "sheet is not valid (<code>motf_km2_excluded_boxes</code>)."
        )
    body = (
        mast(
            "",
            f"{domain_name}: every arm",
            "One row per model run (arm). Click a column header to sort. Badges are "
            "warnings, not filters; hover one for its text. "
            "<b><a href='compare.html'>View runs one at a time, or compare two →</a></b>",
            '<a href="../index.html">runs</a> / ' + esc(domain_name),
        )
        + "<section>"
        + (f'<p class="note">{" ".join(shared)}</p>' if shared else "")
        + '<div class="scroll"><table class="sortable"><thead><tr>'
        "<th>arm</th><th>flags</th>"
        + ("<th>HWM measure</th>" if len(measures) > 1 else "")
        + "<th>waves</th><th>infiltration</th>"
        + heads
        + "</tr></thead><tbody>"
        + "".join(trs)
        + "</tbody></table></div>"
        '<p class="note">HWM columns are the <code>_scored</code> keys (q ≤ 2, dry marks '
        "scored at ground). A waves-off CSI is flagged <code>waves_off_extent</code>: kept, "
        "but not on the same footing as a waves-on CSI. Differences between rows are not "
        "paired tests (scripts/paired_hwm_bootstrap.py). Engine, meteo and bed labels are "
        "on each arm's page.</p>"
        "</section>"
    )
    if domain_name == NEXT_PREMIER["domain"]:
        body += next_premier_section()
    return page(f"{domain_name} · runs", body, 1)


def compare_page(domain_name: str) -> str:
    """One run at a time by default; side by side / one frame (click to swap) on demand."""
    body = (
        mast(
            "",
            f"{domain_name}: view runs",
            "Pick a run to see its figures and scores. To compare two runs, switch to side "
            "by side, or to one frame and click the image to swap. Every figure is drawn on "
            "the same fixed scale and frame, so two runs compare by eye.",
            f'<a href="../index.html">runs</a> / <a href="index.html">{esc(domain_name)}'
            "</a> / view runs",
        )
        + '<div class="ctl"><span><button type="button" data-mode="one" aria-pressed="true">'
        'one run</button> <button type="button" data-mode="side" aria-pressed="false">'
        'side by side</button> <button type="button" data-mode="swap" aria-pressed="false">'
        "one frame, click to swap</button></span>"
        '<label>run<select id="armA"></select></label>'
        '<button id="swapAB" class="onlypair" type="button">A ⇄ B</button>'
        '<label class="onlypair">compare with<select id="armB"></select></label></div>'
        '<section id="pairhead"></section>'
        '<section><h2>Scores</h2><div class="scroll"><table id="diff"></table></div>'
        '<p class="note onlypair">Green / pink colour a difference by the metric\'s '
        "direction (lower RMSE, higher CSI, bias nearer zero); it is not a ranking and not "
        "a test.</p></section>"
        '<section><h2>Figures</h2><div id="figs"></div></section>'
        '<script src="data.js"></script><script src="../assets/compare.js"></script>'
    )
    return page(f"{domain_name} · view runs", body, 1)


def data_js(domain_name: str, arms: dict, ref: str) -> str:
    out = {
        "domain": domain_name,
        "reference": ref,
        "fig_order": FIG_ORDER,
        "headline": HEADLINE,
        "labels": LABELS,
        "arms": {},
    }
    for arm, e in arms.items():
        man = e["manifest"] or {}
        out["arms"][arm] = {
            "slug": e["slug"],
            "reference_arm": man.get("reference_arm") or ref,
            "flags": e["flags"],
            "card": {
                k: e["card"].get(k)
                for k in ("fingerprint", "labels", "config", "audit")
            },
            "metrics": {k: e["row"].get(k) for k, *_ in HEADLINE}
            | {k: e["row"].get(k) for k in ("hwm_estimator", "hwm_radius_m")},
            "figures": [
                {
                    k: f.get(k)
                    for k in ("key", "title", "file", "caption", "skipped", "error")
                }
                for f in man.get("figures", [])
            ],
        }
    return "window.GALLERY_DATA = " + json.dumps(out, default=str) + ";\n"


def site_index(domains: dict) -> str:
    trs = "".join(
        f'<tr><td><a href="{esc(d)}/index.html">{esc(d)}</a></td>'
        f'<td class="num">{len(a)}</td>'
        f'<td class="num">{sum(1 for e in a.values() if e["manifest"])}</td>'
        f'<td><a href="{esc(d)}/compare.html">view runs</a></td></tr>'
        for d, a in domains.items()
    )
    body = (
        mast(
            "<b>NJ Bight SFINCS</b> · run gallery",
            "Run gallery",
            'A standard set of figures for every model run ("arm") of the Hurricane Sandy '
            "compound-flood hindcast, per domain, so runs compare by eye. Each domain is a "
            "different model: compare arms within a domain. Start with "
            "<b><a href='v4_refreeze/compare.html'>view runs (v4)</a></b>.",
        )
        + '<section><table class="sortable"><thead><tr><th>domain</th><th class="num">arms</th>'
        f'<th class="num">with figures</th><th></th></tr></thead><tbody>{trs}</tbody>'
        "</table></section>" + next_premier_section()
    )
    return page("Run gallery", body, 0)


def ensure_repo(site: Path) -> None:
    site.mkdir(parents=True, exist_ok=True)
    if not (site / ".git").exists():
        git = shutil.which("git") or str(
            Path.home() / "nj_sandy_sfincs/micromamba/envs/sfincs/bin/git"
        )
        subprocess.run([git, "init", "-b", "main", str(site)], check=False)
    (site / ".nojekyll").touch()
    readme = site / "README.md"
    if not readme.exists():
        readme.write_text(
            "# NJ Bight SFINCS — run gallery\n\n"
            "Static site (GitHub Pages): the standard figure set of every arm of the "
            "Hurricane Sandy SFINCS hindcast, per domain, with a two-arm compare page.\n"
            "Generated by `scripts/publish_gallery.py` in the research repo "
            "(`nj_bight_sfincs`) from each arm's `gallery/` (`nj_sfincs/gallery.py`).\n"
            "Do not edit by hand — re-publish. " + PRELIM + "\n"
        )


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--site", default=str(Path.home() / "sandy_flood_site"))
    p.add_argument(
        "--domains",
        default=None,
        help="comma-separated (default: all with "
        "a metrics.csv and at least one gallery)",
    )
    p.add_argument("--exp-root", default=None, help=argparse.SUPPRESS)  # tests
    a = p.parse_args(argv)
    site = Path(a.site).expanduser()
    ensure_repo(site)
    from nj_sfincs.premier import PREMIER_NAME

    exp = Path(a.exp_root) if a.exp_root else ROOT / "experiments"
    if a.domains:
        names = a.domains.split(",")
    else:
        names = sorted(
            d.name
            for d in exp.iterdir()
            if d.is_dir() and any(d.glob("*/gallery/manifest.json"))
        )
    (site / "assets").mkdir(exist_ok=True)
    (site / "assets" / "site.css").write_text(CSS)
    (site / "assets" / "sort.js").write_text(SORT_JS)
    (site / "assets" / "compare.js").write_text(COMPARE_JS)
    domains = {}
    for d in names:
        arms = read_domain(d, exp)
        if not arms:
            continue
        domains[d] = arms
        ddir = site / d
        ddir.mkdir(exist_ok=True)
        ref = PREMIER_NAME
        n_png = 0
        for arm, e in arms.items():
            adir = ddir / e["slug"]
            n_png += len(copy_pngs(e, adir))
            (adir / "index.html").write_text(
                arm_page(d, arm, e, (e["manifest"] or {}).get("reference_arm") or ref)
            )
        live = {e["slug"] for e in arms.values()}
        for sub in ddir.iterdir():  # clean as you go: arms that no longer exist
            if sub.is_dir() and sub.name not in live:
                shutil.rmtree(sub)
        (ddir / "index.html").write_text(domain_index(d, arms, ref))
        (ddir / "compare.html").write_text(compare_page(d))
        (ddir / "data.js").write_text(data_js(d, arms, ref))
        print(f"[publish] {d}: {len(arms)} arms, {n_png} figures")
    (site / "index.html").write_text(site_index(domains))
    size = sum(
        f.stat().st_size
        for f in site.rglob("*")
        if f.is_file() and ".git" not in f.parts
    )
    print(f"[publish] {site}: {size / 1e6:.1f} MB (not committed — the user commits)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
