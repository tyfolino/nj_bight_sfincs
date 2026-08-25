"""Repack data/NACCS/ CHS zips into canonical per-product zips, dropping dead weight.

WHY. The CHS webtool bundles whatever was ticked into one CHSFileDownload_*.zip per
request, so the 24 request zips overlap heavily: 1,807 members exist in more than one
zip (all CRC-identical — the Aug-18 Cape May pull re-requested nodes already fetched
on Aug 7/9/13), and every timeseries ships twice, once as CSV/ and once as H5/.
Nothing in this repo reads the H5 members — both readers filter
`CSV/…Timeseries.csv` (build_naccs_boundary.py, naccs_coverage_map.py) — so the H5
tree is ~758 MB compressed of never-read duplicate bytes. Decision 2026-08-20 (user):
repack CSV-only, drop H5, delete the originals once verified.

WHAT IT WRITES. One zip per CHS product (naccs_repack_ADCIRC01.zip,
naccs_repack_STWAVE02.zip, …) holding each unique `CSV/…Timeseries.csv` member once,
plus naccs_repack_provenance.zip holding the deduped README/ files and every
original zip's PATHLOOKUP.txt under PROVENANCE/<original-zip-name>/. Member paths
inside the product zips are UNCHANGED (still `CSV/…`), so the readers need no edits.
A repack_manifest.json records member -> (crc32, size, source zips).

SAFETY.
- Report-only by default; `--apply` writes.
- Duplicate members are asserted CRC-identical across all copies — any mismatch is a
  loud abort naming the member (mirrors build_naccs_boundary's values-agree assert).
- Outputs are written as .partial and os.replace'd; re-running verifies and skips
  completed outputs (resumable).
- After writing, every output zip is re-opened and every member's stored CRC checked
  against the inventory, and the union of member names checked equal to the plan.
- `--apply` then moves the originals to _originals_pending_delete/ (NOT deleted).
  Deleting that directory is a separate, human-approved step, gated on
  `python scripts/build_naccs_boundary.py --report-only --no-cache` reproducing the
  pre-repack parse (1,287 ADCIRC points as of 2026-08-20) and, under
  NJ_DOMAIN=v1_monmouth, support sha16 21f967f9798a6945.
- Never point this at the archive's data/NACCS/ (frozen, 6 zips).

NOTE the parse cache (_sandy_parsed.npz) keys on zip count+mtimes, so the repack
invalidates it and the next read re-parses. That is correct, just slower once.

MERGE (2026-08-24). A later CHS pull lands as a new CHSFileDownload_*.zip beside the
canonical zips. The existing naccs_repack_*.zip are then read as SOURCES too: their
CSV/ members join the inventory under the same CRC-identity assert (a re-requested
node must match byte-for-byte what we already hold), and their PROVENANCE/ tree is
carried through verbatim. The outputs are a verified superset; the previous canonical
zips go to _originals_pending_delete/ with the CHS zip, never overwritten in place.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
import zlib
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NACCS = ROOT / "data" / "NACCS"
REPACK = NACCS / "_repack"
PENDING = NACCS / "_originals_pending_delete"
MANIFEST = REPACK / "repack_manifest.json"

SOURCE_GLOB = "CHSFileDownload_*.zip"
PRODUCT_RE = re.compile(r"_([A-Z]+\d+)_[A-Za-z]+\.csv$")


def inventory(zips: list[Path]) -> tuple[dict, list, dict]:
    """Scan source zips. Return (members, provenance, per_zip_counts).

    members: CSV/ and H5/ name -> dict(crc, size, sources=[zip names]).
    Aborts if the same DATA member name carries different CRCs in two zips.
    provenance: [(zip name, member name, crc, size)] for everything else —
    README/ and PATHLOOKUP.txt legitimately differ per request, so they are
    kept per-source rather than asserted identical.
    """
    members: dict[str, dict] = {}
    provenance: list[tuple[str, str, int, int, bool]] = []
    per_zip = {}
    for z in zips:
        zf = zipfile.ZipFile(z)
        infos = zf.infolist()
        per_zip[z.name] = len(infos)
        for i in infos:
            if i.is_dir():
                continue
            if not i.filename.startswith(("CSV/", "H5/")):
                # a canonical zip's PROVENANCE/ tree is already in its final layout
                key = None if z.name.startswith("naccs_repack_") else z.name
                provenance.append((key or z.name, i.filename, i.CRC, i.file_size,
                                   key is None))
                continue
            rec = members.get(i.filename)
            if rec is None:
                members[i.filename] = dict(
                    crc=i.CRC, size=i.file_size, sources=[z.name]
                )
            else:
                if rec["crc"] != i.CRC or rec["size"] != i.file_size:
                    sys.exit(
                        f"ABORT: {i.filename} differs between {rec['sources'][0]} "
                        f"(crc {rec['crc']:08x}, {rec['size']} B) and {z.name} "
                        f"(crc {i.CRC:08x}, {i.file_size} B). Two different "
                        "products are mixed under one member name — resolve by "
                        "hand before repacking."
                    )
                rec["sources"].append(z.name)
    return members, provenance, per_zip


def plan_outputs(members: dict, provenance: list) -> dict[str, dict[str, tuple]]:
    """Group members into output zips.

    Returns out_zip_name -> {out_member: (src_zip_or_None, src_member)} where a
    None src_zip means "any source zip listed in members[src_member]".

    CSV timeseries go to naccs_repack_<PRODUCT>.zip under their ORIGINAL paths.
    H5/ members are dropped (decision above). Everything else (README/,
    PATHLOOKUP.txt — per-request content) is kept verbatim, per source zip, under
    PROVENANCE/<original-zip-name>/ in the provenance zip, so no byte is silently
    discarded and no identity assumption is made about it.
    """
    outputs: dict[str, dict[str, tuple]] = defaultdict(dict)
    dropped_h5 = 0
    for name in members:
        if name.startswith("H5/"):
            dropped_h5 += 1
            continue
        m = PRODUCT_RE.search(name)
        if m:
            outputs[f"naccs_repack_{m.group(1)}.zip"][name] = (None, name)
        else:
            print(f"  ?? CSV member without a product token, kept as-is: {name}")
            outputs["naccs_repack_provenance.zip"][name] = (None, name)
    for src_zip, name, _crc, _size, verbatim in provenance:
        out_name = name if verbatim else f"PROVENANCE/{src_zip}/{name}"
        outputs["naccs_repack_provenance.zip"][out_name] = (src_zip, name)
    print(f"[plan] H5 members dropped: {dropped_h5}")
    return dict(outputs)


def _expected_crc(src: tuple, members: dict, prov_crc: dict) -> int:
    src_zip, src_name = src
    if src_zip is None:
        return members[src_name]["crc"]
    return prov_crc[(src_zip, src_name)]


def write_output(
    out: Path, mapping: dict, members: dict, prov_crc: dict, by_zip: dict
) -> None:
    """Write one canonical zip atomically, verifying CRC on the way through."""
    part = out.with_suffix(out.suffix + ".partial")
    with zipfile.ZipFile(part, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zo:
        for out_name in sorted(mapping):
            src_zip, src_name = mapping[out_name]
            if src_zip is None:
                src_zip = members[src_name]["sources"][0]
            data = by_zip[src_zip].read(src_name)
            want = _expected_crc(mapping[out_name], members, prov_crc)
            crc = zlib.crc32(data) & 0xFFFFFFFF
            if crc != want:
                part.unlink()
                sys.exit(
                    f"ABORT: {src_zip}:{src_name} read back with crc {crc:08x}, "
                    f"expected {want:08x} — source zip corrupt?"
                )
            zo.writestr(out_name, data)
    part.replace(out)


def verify_output(out: Path, mapping: dict, members: dict, prov_crc: dict) -> bool:
    """True iff `out` exists and matches the plan exactly (names + CRCs)."""
    if not out.exists():
        return False
    try:
        zf = zipfile.ZipFile(out)
    except zipfile.BadZipFile:
        return False
    got = {i.filename: i.CRC for i in zf.infolist() if not i.is_dir()}
    want = {
        o: _expected_crc(src, members, prov_crc) for o, src in mapping.items()
    }
    return got == want


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true", help="write + swap (default: report)")
    args = ap.parse_args()

    new = sorted(NACCS.glob(SOURCE_GLOB))
    canon = sorted(NACCS.glob("naccs_repack_*.zip")) if new else []
    zips = new + canon
    if canon:
        print(f"[merge] {len(new)} new CHS zip(s) + {len(canon)} canonical zips as sources")
    if not new:
        # after a completed swap the originals live in PENDING; report that state
        done = sorted(NACCS.glob("naccs_repack_*.zip"))
        if done:
            print(f"[state] no {SOURCE_GLOB} in {NACCS}; {len(done)} repacked zips "
                  f"present — repack already applied.")
            if PENDING.exists():
                n = len(list(PENDING.glob("*.zip")))
                print(f"[state] {n} originals await deletion in {PENDING}")
            return
        sys.exit(f"no {SOURCE_GLOB} in {NACCS}")

    print(f"[scan] {len(zips)} source zips in {NACCS}")
    members, provenance, per_zip = inventory(zips)
    prov_crc = {(z, n): crc for z, n, crc, _s, _v in provenance}
    n_dup = sum(len(r["sources"]) - 1 for r in members.values())
    dup_bytes = sum(
        r["size"] * (len(r["sources"]) - 1) for r in members.values()
    )
    print(f"[scan] {len(members)} unique data members; {n_dup} redundant copies "
          f"({dup_bytes / 1e9:.2f} GB uncompressed) — all CRC-verified identical; "
          f"{len(provenance)} provenance members kept per-source")

    outputs = plan_outputs(members, provenance)
    prov_size = {(z, n): s for z, n, _c, s, _v in provenance}
    for out_name in sorted(outputs):
        mapping = outputs[out_name]
        size = sum(
            members[s]["size"] if z is None else prov_size[(z, s)]
            for z, s in mapping.values()
        )
        print(f"[plan] {out_name}: {len(mapping)} members, "
              f"{size / 1e9:.2f} GB uncompressed")

    if not args.apply:
        print("\nreport only — rerun with --apply to write, verify and swap.")
        return

    REPACK.mkdir(exist_ok=True)
    by_zip = {z.name: zipfile.ZipFile(z) for z in zips}
    for out_name in sorted(outputs):
        out = REPACK / out_name
        if verify_output(out, outputs[out_name], members, prov_crc):
            print(f"[write] {out_name} already complete — skipped")
            continue
        print(f"[write] {out_name} ...")
        write_output(out, outputs[out_name], members, prov_crc, by_zip)
        if not verify_output(out, outputs[out_name], members, prov_crc):
            sys.exit(f"ABORT: {out_name} failed post-write verification")
        print(f"[write] {out_name} verified ({out.stat().st_size / 1e6:.0f} MB)")

    MANIFEST.write_text(json.dumps(
        dict(
            sources={z.name: per_zip[z.name] for z in zips},
            members={
                n: dict(crc=f"{r['crc']:08x}", size=r["size"], sources=r["sources"])
                for n, r in sorted(members.items())
            },
        ),
        indent=1,
    ))
    print(f"[write] manifest -> {MANIFEST}")

    # swap: repacked zips into data/NACCS/, originals out of the reader's glob
    PENDING.mkdir(exist_ok=True)
    for zf in by_zip.values():
        zf.close()
    for z in canon:
        z.replace(PENDING / f"{z.stem}.pre-merge-{new[-1].stem[-19:]}.zip")
    for out_name in sorted(outputs):
        (REPACK / out_name).replace(NACCS / out_name)
    for z in new:
        z.replace(PENDING / z.name)
    print(f"[swap] {len(outputs)} repacked zips -> {NACCS}")
    print(f"[swap] {len(zips)} originals -> {PENDING} (NOT deleted)")
    print("\nNEXT (before anything is deleted):")
    print("  python scripts/build_naccs_boundary.py --report-only --no-cache")
    print("    must reproduce the pre-repack unique-point count, and under")
    print("    NJ_DOMAIN=v1_monmouth the support sha16 21f967f9798a6945.")
    print(f"  Only then delete {PENDING} (user-approved step).")


if __name__ == "__main__":
    main()
