#!/usr/bin/env python
"""Draw the run-gallery figures for finished arms, one subprocess per arm, serially.

The same figures the sweep driver draws after validation (``run_experiments.py``; see
``nj_sfincs/gallery.py``), for arms validated before the hook existed or to re-draw after
a gallery change. Arms with no ``sfincs_map.nc`` are skipped. Every arm runs in its own
process, so its rasters are released before the next; a failing arm warns and the loop
carries on. The peak RSS of each arm is read back from its ``manifest.json``.

    NJ_DOMAIN=v4_refreeze python scripts/build_gallery.py              # every finished arm
    NJ_DOMAIN=v4_refreeze python scripts/build_gallery.py --arms naccs-premier,naccs-nowaves
    NJ_DOMAIN=v3 python scripts/build_gallery.py --only zsmax,dzsmax   # re-draw two figures

⚠️ Heavier than a grep (~17 G peak per v4 arm): run on a compute node.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def finished_arms(domain_name: str) -> list[str]:
    root = ROOT / "experiments" / domain_name
    return sorted(
        p.name
        for p in root.iterdir()
        if p.is_dir()
        and not p.name.startswith(("_", "."))
        and (p / "sfincs_map.nc").is_file()
    )


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--domain", default=os.environ.get("NJ_DOMAIN"))
    p.add_argument(
        "--arms", default=None, help="comma-separated (default: all finished)"
    )
    p.add_argument("--only", default=None, help="comma-separated figure keys")
    a = p.parse_args(argv)
    if not a.domain:
        p.error("set NJ_DOMAIN or pass --domain")
    os.environ["NJ_DOMAIN"] = a.domain
    from nj_sfincs import gallery

    arms = a.arms.split(",") if a.arms else finished_arms(a.domain)
    extra = ["--only", a.only] if a.only else None
    rows = []
    for arm in arms:
        t = time.time()
        print(f"\n=== {a.domain}/{arm} ===", flush=True)
        try:
            rc = gallery.build_in_subprocess(a.domain, arm, extra=extra)
        except Exception as e:  # noqa: BLE001 — one arm must not stop the loop
            print(f"⚠️ {arm}: {e}")
            rc = -1
        mp = ROOT / "experiments" / a.domain / arm / gallery.GALLERY / gallery.MANIFEST
        rss = failed = None
        if mp.is_file():
            m = json.loads(mp.read_text())
            rss = m.get("peak_rss_gb")
            failed = [f["key"] for f in m.get("figures", []) if f.get("error")]
        rows.append((arm, rc, round(time.time() - t), rss, failed))
    print(f"\n{'arm':45s} {'rc':>3s} {'s':>6s} {'peak GB':>8s}  failed figures")
    for arm, rc, s, rss, failed in rows:
        print(f"{arm:45s} {rc:3d} {s:6d} {rss!s:>8s}  {', '.join(failed or []) or '-'}")
    return 0 if all(r[1] == 0 for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
