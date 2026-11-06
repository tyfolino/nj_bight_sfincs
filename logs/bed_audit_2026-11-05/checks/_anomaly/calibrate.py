"""Which known cases each anomaly check catches, per bed, and the user's eye checks as a hit / false-alarm score.

    python calibrate.py LABEL [LABEL ...]       -> out/calibration_anomaly.md

Known cases (FINDINGS part 4 (l)/(m), §54, STATUS 11-05) with what SHOULD fire on which bed. A case "fires" when an
exception of the listed checks lies within RADIUS m. Eye checks: the deck short list (modern bed) and the underpass
picker (v1.1 + modern): 'open' = a real problem (a hit if any anomaly fires within RADIUS), 'keep' = the bed is
right (a false alarm if one fires).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

RADIUS = 150.0
KNOWN = [  # name, lon, lat, beds where it MUST fire, beds where it must NOT (fixed there), expected checks
    ("Alloway Lake arm: fake floor under the pool", -75.351, 39.566, "p100", "2012,modern", "anomaly_flat,anomaly_ridge"),
    ("Silver Lake (E4): CUDEM fill under the pool", -75.693, 39.438, "p100,2012", "", "anomaly_flat,anomaly_disagree"),
    ("Christina plug at Wilmington (v4e fixes it; modern still has v4c)", -75.5599, 39.7236, "p100,modern", "2012",
     "anomaly_profile"),
    ("Grays Ferry flat sill (M537)", -75.196, 39.942, "p100,2012,modern", "", "anomaly_profile,anomaly_flat"),
    ("Shark River at Ocean Ave (M271)", -74.011, 40.187, "p100,modern", "", "anomaly_profile,anomaly_flat,anomaly_ridge"),
    ("Cape May rail trestle (M181)", -74.841, 39.018, "modern", "", "anomaly_profile,anomaly_flat"),
    ("Cape May harbour footway (M232)", -74.834, 38.989, "modern", "", "anomaly_flat,anomaly_profile"),
    ("Penn's Landing pier strip (M562)", -75.140, 39.943, "modern", "", "anomaly_disagree,anomaly_ridge"),
]


def sites_from_decisions():
    out = []
    f = C.REPO / "logs/modern_decks_2026-11-04/user_decisions_2026-11-05.csv"
    s = pd.read_csv(C.REPO / "logs/modern_decks_2026-11-04/out/modern/candidates.csv", dtype={"osm_id": str})
    e = pd.read_csv(C.REPO / "logs/modern_decks_2026-11-04/out/modern/embankments.csv")
    loc = {**{r.id: (r.lon, r.lat) for r in s.itertuples()}, **{r.id: (r.lon, r.lat) for r in e.itertuples()}}
    for r in pd.read_csv(f).itertuples():
        if r.id in loc and r.final in ("open", "keep"):
            out.append(("deck", r.id, *loc[r.id], r.final, "modern"))
    u = C.REPO / "logs/underpass_sweep_2026-11-05"
    pk = pd.read_csv(u / "user_decisions_2026-11-05.csv")
    import json  # noqa: PLC0415
    import re  # noqa: PLC0415

    html = (u / "picker_page.html").read_text()
    m = re.search(r"const SITES = (\[.*?\]);\n", html, re.S)
    sites = {d["id"]: (d["lon"], d["lat"]) for d in json.loads(m.group(1))}
    for r in pk.itertuples():
        if r.id in sites and r.decision in ("open", "keep"):
            out.append(("underpass", r.id, *sites[r.id], r.decision, "both"))
    return out


def near(df, lon, lat, checks=None):
    if df.empty:
        return df
    x0, y0 = C.TO_UTM(lon, lat)
    x, y = C.TO_UTM(df.lon.values, df.lat.values)
    d = np.hypot(x - x0, y - y0)
    # an area finding is placed at its centroid: allow its own size as well
    rad = np.maximum(RADIUS, 3 * np.sqrt(pd.to_numeric(df.area_m2, errors="coerce").fillna(0).values))
    sel = d <= rad
    if checks:
        sel &= df.check.isin(checks.split(","))
    return df[sel].assign(dist=d[sel])


def load(label):
    fr = []
    for f in (C.AUD / "out" / label).glob("anomaly_*.csv"):
        x = pd.read_csv(f)
        if len(x):
            fr.append(x)
    return pd.concat(fr, ignore_index=True) if fr else pd.DataFrame(columns=C.COLS)


def main(labels):
    lines = ["# Anomaly checks: calibration", "", f"A case fires when an exception of the expected checks lies within "
             f"{RADIUS:.0f} m (or 3 x the square root of its area, for patches placed at their centroid). Beds: {', '.join(labels)}.", "", "## Known cases", "",
             "| case | must fire on | must NOT (fixed) | " + " | ".join(labels) + " |", "|---|---|---|" + "---|" * len(labels)]
    D = {lb: load(lb) for lb in labels}
    tag = {lb: ("modern" if "modern" in lb else ("p100" if "p100" in lb else "2012")) for lb in labels}
    for nm, lo, la, beds, nots, chk in KNOWN:
        cells = []
        for lb in labels:
            h = near(D[lb], lo, la, chk)
            got = (f"{h.iloc[0].check.replace('anomaly_', '')}/{h.iloc[0].kind} ({h.iloc[0].severity})"
                   if len(h) else "—")
            if tag[lb] in beds.split(","):
                mark = "✅ " if len(h) else "❌ "
            elif tag[lb] in nots.split(","):
                mark = "✅ " if not len(h) else "❌ "
            else:
                mark = "· "
            cells.append(mark + got)
        lines.append(f"| {nm} | {beds} | {nots or '–'} | " + " | ".join(cells) + " |")
    lines += ["", "## Eye checks (the user's open / keep calls)", ""]
    sites = sites_from_decisions()
    for lb in labels:
        rows = []
        for grp, sid, lo, la, dec, bed in sites:
            if bed == "modern" and tag[lb] != "modern":
                continue
            h = near(D[lb], lo, la)
            rows.append((grp, sid, dec, len(h) > 0, ";".join(sorted(set(h.check.str.replace("anomaly_", "")))) if len(h) else ""))
        if not rows:
            continue
        r = pd.DataFrame(rows, columns=["group", "id", "decision", "fired", "checks"])
        op, kp = r[r.decision == "open"], r[r.decision == "keep"]
        lines += [f"**{lb}**: of {len(op)} sites the user OPENED, {int(op.fired.sum())} fire (hits); of {len(kp)} "
                  f"the user KEPT, {int(kp.fired.sum())} fire (false alarms).", "",
                  "| group | id | user | fired | checks |", "|---|---|---|---|---|"]
        lines += [f"| {g} | {i} | {d} | {'yes' if f else 'no'} | {c} |" for g, i, d, f, c in rows]
        lines.append("")
    out = C.AUD / "out" / "calibration_anomaly.md"
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main(sys.argv[1:])
