#!/usr/bin/env python
"""Every SnapWave parameter: what we set, what the engine would have used, what it means.

    python scripts/snapwave_parameters.py experiments/v3/<arm> [<arm> ...]
        [--md docs/snapwave_parameters.md] [--html reports/snapwave_parameters.html]

Reads each run's ``sfincs.inp`` and prints, per key in
``nj_sfincs.snapwave_params.ENGINE_DEFAULTS_V233``: our value (or the default it fell
through to), the v2.3.3 engine default, the hydromt default, and a one-line meaning.
Values that DIFFER from the engine default are marked, because that is the list a
supervisor wants: what did you change, and why. Written 2026-09-11 (plan Phase 0, item D).

The engine label comes from ``engine.txt`` when a run has one (Phase 1b) and otherwise
from the ``Build-Revision`` line of ``sfincs.log``, marked ``(inferred)``. 🔴 A run with
``snapwave_wind = 1`` on an engine whose Build-Revision lacks the ``nj-winddir-fix`` tag
is flagged: its boundary waves were launched in the WIND direction (FINDINGS §43).

``--md`` writes a GENERATED Markdown table (do not hand-edit); ``--html`` writes a
self-contained page for sharing (the artifact). Both list the runs in the order given.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import html
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from nj_sfincs.provenance import read_inp
from nj_sfincs.snapwave_params import (
    ENGINE_DEFAULTS_V233,
    GROUPS,
    HYDROMT_DEFAULTS,
    MEANINGS,
    RAW_APPEND_ONLY,
    has_direction_bug,
)

_BUILD = re.compile(r"Build-Revision:\s*(.+)")


@dataclass
class RunParams:
    name: str
    path: Path
    inp: dict
    build_revision: str | None
    engine_label: str
    n_support: int | None
    direction_bug: bool

    @property
    def waves_on(self) -> bool:
        return str(self.inp.get("snapwave", "0")).strip() == "1"


def _build_revision(path: Path) -> str | None:
    log = path / "sfincs.log"
    if not log.is_file():
        return None
    with open(log, errors="ignore") as fh:
        for i, line in enumerate(fh):
            m = _BUILD.search(line)
            if m:
                return m.group(1).strip()
            if i > 400:
                break
    return None


def _engine_label(path: Path, rev: str | None) -> str:
    eng = path / "engine.txt"
    if eng.is_file():
        for line in eng.read_text().splitlines():
            if line.lower().startswith("label"):
                return line.split("=", 1)[-1].strip() or line.split(":", 1)[-1].strip()
        return eng.read_text().strip().splitlines()[0]
    if rev is None:
        return "unknown (no sfincs.log)"
    return f"container v2.3.3 [{rev}] (inferred from sfincs.log)"


def read_run(path: Path | str) -> RunParams:
    path = Path(path)
    inp = read_inp(path)
    if not inp:
        raise SystemExit(f"{path}: no sfincs.inp")
    rev = _build_revision(path)
    bnd = inp.get("snapwave_bndfile")
    n = None
    if bnd and (path / bnd).is_file():
        n = sum(1 for ln in (path / bnd).read_text().splitlines() if ln.strip())
    return RunParams(
        name=path.name,
        path=path,
        inp=inp,
        build_revision=rev,
        engine_label=_engine_label(path, rev),
        n_support=n,
        direction_bug=has_direction_bug(inp, rev),
    )


def _fmt(v) -> str:
    if isinstance(v, bool):
        return ".true." if v else ".false."
    if isinstance(v, float):
        return f"{v:.6g}"
    return str(v)


def _norm(v: str) -> str:
    """Normalise an inp value for comparison: numbers by value, strings by text."""
    s = str(v).strip().strip("'\"")
    try:
        return f"{float(s):.6g}"
    except ValueError:
        return {
            "true": ".true.",
            "false": ".false.",
            ".true.": ".true.",
            ".false.": ".false.",
        }.get(s.lower(), s)


def effective(inp: dict, key: str) -> tuple[str, bool]:
    """(value the engine used, was it written explicitly)."""
    if key in inp:
        return inp[key].strip(), True
    return _fmt(ENGINE_DEFAULTS_V233[key]), False


def group_of(key: str) -> str:
    keys = list(ENGINE_DEFAULTS_V233)
    g = GROUPS[0][0]
    for title, first in GROUPS:
        if keys.index(first) <= keys.index(key):
            g = title
    return g


def table(runs: list[RunParams]) -> pd.DataFrame:
    """One row per engine key; one column per run holding the EFFECTIVE value, with a
    trailing ``*`` when the key was absent from the inp (engine default applied) and a
    ``≠`` prefix when the effective value differs from the engine default."""
    rows = []
    for key, default in ENGINE_DEFAULTS_V233.items():
        r = {
            "group": group_of(key),
            "key": key,
            "engine_default": _fmt(default),
            "hydromt_default": _fmt(HYDROMT_DEFAULTS[key])
            if key in HYDROMT_DEFAULTS
            else "—",
            "raw_append_only": key in RAW_APPEND_ONLY,
            "meaning": MEANINGS.get(key, ""),
        }
        for run in runs:
            if not run.waves_on and key != "snapwave":
                r[run.name] = "(off)"
                continue
            val, explicit = effective(run.inp, key)
            differs = _norm(val) != _norm(_fmt(default))
            r[run.name] = ("≠ " if differs else "") + val + ("" if explicit else " *")
        rows.append(r)
    return pd.DataFrame(rows)


def differences(runs: list[RunParams]) -> pd.DataFrame:
    """The supervisor's list: keys where ANY run departs from the engine default."""
    df = table(runs)
    names = [r.name for r in runs]
    keep = df[names].apply(lambda col: col.str.startswith("≠")).any(axis=1)
    # The master switch and the boundary file names are what turning waves ON means,
    # not a lever anyone pulled; they stay in the full table below.
    keep &= (df["group"] != "Boundary files") & (df["key"] != "snapwave")
    return df[keep]


# ── renderers ────────────────────────────────────────────────────────────────────


def _caveats(runs: list[RunParams]) -> list[str]:
    out = []
    for r in runs:
        if r.direction_bug:
            out.append(
                f"{r.name}: snapwave_wind = 1 on engine [{r.build_revision}] — the "
                f"boundary waves were launched in the domain-mean WIND direction, not the "
                f"imposed .bwd direction (FINDINGS §43). Its wave numbers describe "
                f"misdirected waves."
            )
    return out


def render_text(runs: list[RunParams]) -> str:
    df = table(runs)
    names = [r.name for r in runs]
    out = []
    for r in runs:
        out.append(
            f"{r.name:<32} engine: {r.engine_label}"
            + (f"   support points: {r.n_support}" if r.n_support else "")
        )
    out.append("")
    for c in _caveats(runs):
        out.append("🔴 " + c)
    if _caveats(runs):
        out.append("")
    out.append(
        "≠ = differs from the v2.3.3 engine default;  * = key absent from the inp, "
        "engine default applied"
    )
    for g, grp in df.groupby("group", sort=False):
        out.append(f"\n[{g}]")
        cols = ["key"] + names + ["engine_default", "hydromt_default", "meaning"]
        out.append(grp[cols].to_string(index=False))
    return "\n".join(out)


def render_md(runs: list[RunParams]) -> str:
    df = table(runs)
    names = [r.name for r in runs]
    stamp = _dt.date.today().isoformat()
    out = [
        "# SnapWave parameters — GENERATED, do not hand-edit",
        "",
        f"Generated {stamp} by `scripts/snapwave_parameters.py` from the run dirs below. "
        "Regenerate after every change of premier. Engine defaults are SFINCS v2.3.3 "
        "(`sfincs_snapwave.f90::read_snapwave_input`); hydromt defaults are "
        "`hydromt_sfincs/components/config/config_variables.py`. Keys marked ⚙ reach the "
        "inp only through `model.finalize`'s raw-text append (not in hydromt's schema).",
        "",
        "| run | engine | support points | wind | direction |",
        "|---|---|---|---|---|",
    ]
    for r in runs:
        wind = r.inp.get("snapwave_wind", "0*") if r.waves_on else "(off)"
        d = (
            "🔴 WIND (misdirected)"
            if r.direction_bug
            else ("imposed" if r.waves_on else "off")
        )
        out.append(
            f"| `{r.name}` | {r.engine_label} | {r.n_support or '—'} | {wind} | {d} |"
        )
    out.append("")
    for c in _caveats(runs):
        out.append(f"🔴 **{c}**")
        out.append("")
    out.append(
        "`≠` = differs from the engine default; `*` = key absent from the inp, "
        "engine default applied."
    )
    out.append("")
    out.append("## What we changed from the engine defaults")
    out.append("")
    dd = differences(runs)
    out.append(
        "| key | "
        + " | ".join(f"`{n}`" for n in names)
        + " | engine default | meaning |"
    )
    out.append("|---|" + "---|" * len(names) + "---|---|")
    for _, r in dd.iterrows():
        out.append(
            f"| `{r.key}`{' ⚙' if r.raw_append_only else ''} | "
            + " | ".join(f"`{r[n]}`" for n in names)
            + f" | `{r.engine_default}` | {r.meaning} |"
        )
    out.append("")
    out.append("## Every key")
    for g, grp in df.groupby("group", sort=False):
        out.append("")
        out.append(f"### {g}")
        out.append("")
        out.append(
            "| key | "
            + " | ".join(f"`{n}`" for n in names)
            + " | engine | hydromt | meaning |"
        )
        out.append("|---|" + "---|" * len(names) + "---|---|---|")
        for _, r in grp.iterrows():
            out.append(
                f"| `{r.key}`{' ⚙' if r.raw_append_only else ''} | "
                + " | ".join(f"`{r[n]}`" for n in names)
                + f" | `{r.engine_default}` | {r.hydromt_default} | {r.meaning} |"
            )
    return "\n".join(out) + "\n"


_CSS = """
:root{--bg:#f6f7f5;--panel:#ffffff;--ink:#1c242c;--muted:#5d6874;--rule:#d5dbdf;
--accent:#0f6e73;--accent-ink:#0b5257;--warn-bg:#f8efdc;--warn:#8a5a10;--alert:#b23a2c;
--alert-bg:#f9e6e2;--code-bg:#eef1f0;--off:#a2abb3;
--serif:'IBM Plex Serif',Georgia,'Times New Roman',serif;
--sans:'IBM Plex Sans',system-ui,-apple-system,'Segoe UI',sans-serif;
--mono:'IBM Plex Mono',ui-monospace,Menlo,Consolas,monospace;color-scheme:light dark}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#141a1f;
--panel:#1b2229;--ink:#e4e9ed;--muted:#97a3ad;--rule:#2b353f;--accent:#54b8bd;
--accent-ink:#8ad3d6;--warn-bg:#3a2e14;--warn:#e6b35a;--alert:#ea7b6c;--alert-bg:#3d1f1a;
--code-bg:#232c34;--off:#5b6670}}
:root[data-theme="dark"]{--bg:#141a1f;--panel:#1b2229;--ink:#e4e9ed;--muted:#97a3ad;
--rule:#2b353f;--accent:#54b8bd;--accent-ink:#8ad3d6;--warn-bg:#3a2e14;--warn:#e6b35a;
--alert:#ea7b6c;--alert-bg:#3d1f1a;--code-bg:#232c34;--off:#5b6670}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);
font-size:15px;line-height:1.5;padding-block:32px 64px;padding-inline:clamp(16px,4vw,48px)}
.wrap{max-width:1180px;margin:0 auto}
header{display:flex;flex-direction:column;gap:6px;border-bottom:2px solid var(--accent);
padding-bottom:18px;margin-bottom:26px}
.eyebrow{font-family:var(--mono);font-size:12px;letter-spacing:.08em;text-transform:uppercase;
color:var(--accent-ink)}
h1{font-family:var(--serif);font-weight:600;font-size:clamp(26px,3.4vw,38px);line-height:1.15;
margin:0;text-wrap:balance}
.dek{color:var(--muted);max-width:68ch;margin:0}
h2{font-family:var(--serif);font-weight:600;font-size:22px;margin:38px 0 12px;text-wrap:balance}
h3{font-family:var(--sans);font-weight:600;font-size:13px;letter-spacing:.08em;
text-transform:uppercase;color:var(--muted);margin:28px 0 8px}
p{max-width:72ch}
code,.k{font-family:var(--mono);font-size:.92em}
.k{color:var(--accent-ink)}
.runs{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;
margin:0 0 8px;padding:0;list-style:none}
.runs li{background:var(--panel);border:1px solid var(--rule);border-radius:6px;
padding:12px 14px;display:flex;flex-direction:column;gap:4px}
.runs .name{font-family:var(--mono);font-weight:600;font-size:14px}
.runs .meta{color:var(--muted);font-size:13px}
.pill{display:inline-block;font-family:var(--mono);font-size:11px;letter-spacing:.04em;
padding:2px 8px;border-radius:999px;border:1px solid var(--rule);color:var(--muted);
width:max-content}
.pill.bad{background:var(--alert-bg);color:var(--alert);border-color:transparent;font-weight:600}
.pill.good{background:var(--code-bg);color:var(--accent-ink);border-color:transparent}
.alert{background:var(--alert-bg);border-left:4px solid var(--alert);padding:12px 16px;
border-radius:0 6px 6px 0;margin:18px 0}
.alert p{margin:0 0 6px}.alert p:last-child{margin:0}
.legend{color:var(--muted);font-size:13px;margin:10px 0 0}
.tbl{overflow-x:auto;border:1px solid var(--rule);border-radius:6px;background:var(--panel)}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{text-align:left;vertical-align:top;padding:7px 10px;border-bottom:1px solid var(--rule)}
th{font-family:var(--sans);font-weight:600;font-size:12px;letter-spacing:.06em;
text-transform:uppercase;color:var(--muted);background:var(--panel);position:sticky;top:0}
tr:last-child td{border-bottom:0}
td.key{font-family:var(--mono);white-space:nowrap;color:var(--accent-ink)}
td.val{font-family:var(--mono);white-space:nowrap;font-variant-numeric:tabular-nums}
td.val.diff{background:var(--warn-bg);color:var(--warn);font-weight:600}
td.val.off{color:var(--off);font-style:italic}
td.def{font-family:var(--mono);white-space:nowrap;color:var(--muted);
font-variant-numeric:tabular-nums}
td.meaning{min-width:26ch;max-width:52ch;color:var(--ink)}
.star{color:var(--muted);font-weight:400}
.gear{color:var(--muted);font-size:11px;margin-left:4px}
footer{margin-top:40px;color:var(--muted);font-size:13px;border-top:1px solid var(--rule);
padding-top:12px}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
"""


def render_html(runs: list[RunParams]) -> str:
    df = table(runs)
    names = [r.name for r in runs]
    stamp = _dt.date.today().isoformat()
    e = html.escape

    def cell(v: str) -> str:
        if v == "(off)":
            return '<td class="val off">off</td>'
        cls = "val diff" if v.startswith("≠") else "val"
        v = v.lstrip("≠ ")
        star = ' <span class="star">*</span>' if v.endswith("*") else ""
        return f'<td class="{cls}">{e(v.rstrip(" *"))}{star}</td>'

    def rows(frame: pd.DataFrame, with_hydromt: bool) -> str:
        out = []
        for _, r in frame.iterrows():
            gear = (
                '<span class="gear" title="raw-text append only">⚙</span>'
                if r.raw_append_only
                else ""
            )
            out.append(
                "<tr>"
                + f'<td class="key">{e(r.key)}{gear}</td>'
                + "".join(cell(r[n]) for n in names)
                + f'<td class="def">{e(r.engine_default)}</td>'
                + (
                    f'<td class="def">{e(r.hydromt_default)}</td>'
                    if with_hydromt
                    else ""
                )
                + f'<td class="meaning">{e(r.meaning)}</td></tr>'
            )
        return "\n".join(out)

    def head(with_hydromt: bool) -> str:
        return (
            "<tr><th>key</th>"
            + "".join(f"<th>{e(n)}</th>" for n in names)
            + "<th>engine v2.3.3</th>"
            + ("<th>hydromt</th>" if with_hydromt else "")
            + "<th>meaning</th></tr>"
        )

    run_cards = []
    for r in runs:
        if not r.waves_on:
            pill = '<span class="pill">SnapWave off</span>'
        elif r.direction_bug:
            pill = '<span class="pill bad">waves launched in the WIND direction</span>'
        else:
            pill = '<span class="pill good">waves in the imposed direction</span>'
        wind = r.inp.get("snapwave_wind", "0 *") if r.waves_on else "—"
        run_cards.append(
            f'<li><span class="name">{e(r.name)}</span>'
            f'<span class="meta">engine: {e(r.engine_label)}</span>'
            f'<span class="meta">support points: {r.n_support or "—"} · '
            f"snapwave_wind: {e(str(wind))}</span>{pill}</li>"
        )

    caveats = _caveats(runs)
    alert = ""
    if caveats:
        alert = (
            '<div class="alert"><p><strong>Direction caveat (FINDINGS §43).</strong> '
            "SFINCS v2.3.3–v2.4.1 with wind growth on discards the wave direction we "
            "impose at the boundary and launches the spectrum in the domain-mean wind "
            "direction. The runs below are affected; their wave numbers describe "
            "misdirected waves.</p>"
            + "".join(f"<p>{e(c)}</p>" for c in caveats)
            + "</div>"
        )

    dd = differences(runs)
    groups = "".join(
        f"<h3>{e(g)}</h3><div class='tbl'><table><thead>{head(True)}</thead>"
        f"<tbody>{rows(grp, True)}</tbody></table></div>"
        for g, grp in df.groupby("group", sort=False)
    )

    return f"""<title>SnapWave Parameter Sheet</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@400;600&family=IBM+Plex+Serif:wght@600&display=swap">
<style>{_CSS}</style>
<div class="wrap">
<header>
<span class="eyebrow">NJ Bight SFINCS · Hurricane Sandy hindcast · generated {stamp}</span>
<h1>SnapWave Parameter Sheet</h1>
<p class="dek">Every SnapWave setting in our runs, beside what the SFINCS v2.3.3 engine would
have used on its own and what hydromt-SFINCS writes by default. Highlighted cells are the
ones we changed. Values from <code>sfincs.inp</code>; defaults transcribed from the engine
source (<code>sfincs_snapwave.f90</code>) and <code>config_variables.py</code>.</p>
</header>

<h2>Runs on this sheet</h2>
<ul class="runs">{"".join(run_cards)}</ul>
{alert}

<h2>What we changed from the engine defaults</h2>
<p>The list a reviewer needs first. A highlighted value differs from the engine default;
an asterisk means the key was not in the input file and the engine default applied;
⚙ marks keys that hydromt-SFINCS does not know and that reach the input file only through
this repo's own text append.</p>
<div class="tbl"><table><thead>{head(False)}</thead><tbody>{rows(dd, False)}</tbody></table></div>

<h2>Every key, by group</h2>
<p class="legend">Same conventions. The hydromt column is “—” for keys outside hydromt's
schema.</p>
{groups}

<footer>Generated by <code>scripts/snapwave_parameters.py</code> in
<code>nj_bight_sfincs</code>. Engine defaults: SFINCS tag v2.3.3 (<code>091f531a</code>),
<code>read_snapwave_input</code> and <code>sfincs_input.f90</code>. Direction bug: FINDINGS
§43, STATUS 2026-09-10 PM.</footer>
</div>
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("runs", nargs="+", type=Path)
    ap.add_argument("--md", type=Path, default=None)
    ap.add_argument("--html", type=Path, default=None)
    a = ap.parse_args(argv)
    runs = [read_run(p) for p in a.runs]
    pd.set_option("display.width", 250, "display.max_colwidth", 80)
    print(render_text(runs))
    if a.md:
        a.md.write_text(render_md(runs))
        print(f"\nwrote {a.md}")
    if a.html:
        a.html.write_text(render_html(runs))
        print(f"wrote {a.html}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
