"""Convert CHS webtool H5-only NACCS save points into the CSV layout the readers use.

WHY. `build_naccs_boundary.py` and `naccs_coverage_map.py` read `CSV/…Timeseries.csv`
members only, and `repack_naccs_zips.py` drops every `H5/` member as a duplicate of its
CSV twin. The 2026-09-24 Delaware pull (8 CHSFileDownload zips, 393 new ADCIRC points,
mouth → Trenton) was downloaded H5-ONLY, so the repack kept none of it. This writes a
CSV member for every H5 save point that has no CSV twin, into ONE new zip in
data/NACCS/, which the repack then merges like any other CHS zip.

LAYOUT (matched to the webtool's CSVs, checked on the overlap below): three header rows
(long names, model-variable codes, units), then one row per record — SP id, lat, lon,
depth (6 dp), storm name (quoted unless numeric), storm ID (as the H5 attr, e.g. `001`),
storm type (quoted), yyyymmddHHMM, then the variables in alphabetical long-name order,
storms in H5 group order. Values are written at full float64 precision (`repr`); the
webtool's CSVs round to ~11 significant digits, so a converted member differs from a
webtool one in the last digits and is never byte-identical to it.

SELF-CHECK (always runs, before anything is written): every H5 point that ALSO exists as
a webtool CSV is converted in memory and parsed by `build_naccs_boundary._rows_for_sandy`;
the Sandy timestamps must be identical and the water levels agree to 1e-9 m, or it
aborts. Points already held as CSV are then SKIPPED — the webtool CSV stays canonical.

Report-only by default; `--apply` writes data/NACCS/CHSFileDownload_<stamp>_fromH5.zip
(atomic). Sources: the given zips, default every CHSFileDownload_*.zip in data/NACCS/
and data/NACCS/_originals_pending_delete/.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import sys
import zipfile
from pathlib import Path

import netCDF4
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
NACCS = ROOT / "data" / "NACCS"
sys.path.insert(0, str(ROOT / "scripts"))
from build_naccs_boundary import _rows_for_sandy  # noqa: E402

SP_RE = re.compile(r"_SP0*(\d+)_(ADCIRC\d+|STWAVE\d+)_Timeseries")
TIME = "yyyymmddHHMM"
FIXED = ["Save Point ID", "Save Point Latitude", "Save Point Longitude",
         "Save Point Depth", "Storm Name", "Storm ID", "Storm Type", TIME]


def _num(s: str) -> bool:
    return re.fullmatch(r"[0-9]+", s) is not None


def h5_to_csv(raw: bytes) -> bytes:
    d = netCDF4.Dataset("mem", memory=raw)
    sp = int(float(d.getncattr("Save Point ID")))
    lat = float(d.getncattr("Save Point Latitude"))
    lon = float(d.getncattr("Save Point Longitude"))
    groups = list(d.groups.values())
    names = sorted(k for k in groups[0].variables if k != TIME)
    v0 = groups[0].variables
    out = io.StringIO()
    w = lambda row: out.write(",".join(row) + "\n")  # noqa: E731
    q = lambda s: f'"{s}"'  # noqa: E731
    w([q(c) for c in FIXED + names])
    w([q("")] * len(FIXED) + [q(v0[n].getncattr("Model Variable")) for n in names])
    w([q("")] * (len(FIXED) - 1) + [q(TIME)] + [q(v0[n].getncattr("Units")) for n in names])
    for g in groups:
        depth = float(g.getncattr("Save Point Depth"))
        name = str(g.getncattr("Storm Name"))
        sid = str(g.getncattr("Storm ID"))
        stype = str(g.getncattr("Storm Type"))
        t = np.asarray(g.variables[TIME][:], dtype="float64")
        cols = [np.asarray(g.variables[n][:], dtype="float64") for n in names]
        head = [str(sp), f"{lat:.6f}", f"{lon:.6f}", f"{depth:.6f}",
                name if _num(name) else q(name), sid, q(stype)]
        for i in range(len(t)):
            w(head + [str(int(round(t[i])))] + [repr(float(c[i])) for c in cols])
    return out.getvalue().encode()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("zips", nargs="*", type=Path)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    srcs = a.zips or sorted(NACCS.glob("CHSFileDownload_*.zip")) + sorted(
        (NACCS / "_originals_pending_delete").glob("CHSFileDownload_*.zip"))
    srcs = [z for z in srcs if not z.name.endswith("_fromH5.zip")]

    held: dict[tuple[int, str], tuple[Path, str]] = {}
    for z in sorted(NACCS.glob("*.zip")):
        for m in zipfile.ZipFile(z).namelist():
            if m.startswith("CSV/") and (mm := SP_RE.search(m)):
                held.setdefault((int(mm.group(1)), mm.group(2)), (z, m))

    todo: dict[tuple[int, str], tuple[Path, str]] = {}
    for z in srcs:
        for m in zipfile.ZipFile(z).namelist():
            if m.startswith("H5/") and (mm := SP_RE.search(m)):
                todo.setdefault((int(mm.group(1)), mm.group(2)), (z, m))
    overlap = sorted(k for k in todo if k in held)
    new = sorted(k for k in todo if k not in held)
    print(f"[scan] {len(srcs)} source zips: {len(todo)} H5 save points; "
          f"{len(overlap)} already held as CSV, {len(new)} to convert "
          f"({sum(1 for k in new if k[1].startswith('ADCIRC'))} ADCIRC, "
          f"{sum(1 for k in new if k[1].startswith('STWAVE'))} STWAVE)")

    nchk = 0
    for k in overlap:
        if not k[1].startswith("ADCIRC"):
            continue
        zh, mh = todo[k]
        zc, mc = held[k]
        a1 = _rows_for_sandy(h5_to_csv(zipfile.ZipFile(zh).read(mh)))
        a2 = _rows_for_sandy(zipfile.ZipFile(zc).read(mc))
        ok = (a1[0] == a2[0] and np.array_equal(a1[4], a2[4])
              and np.allclose(a1[5], a2[5], rtol=0, atol=1e-9)
              and abs(a1[1] - a2[1]) < 1e-6 and abs(a1[2] - a2[2]) < 1e-6)
        if not ok:
            sys.exit(f"[check] SP{k[0]}: the H5 conversion does NOT reproduce the webtool "
                     f"CSV (max |dwl| {np.max(np.abs(a1[5] - a2[5])):.3g}). Nothing written.")
        nchk += 1
    print(f"[check] {nchk} overlapping ADCIRC points: converted H5 == webtool CSV "
          "(Sandy timestamps identical, water level within 1e-9 m)")
    if not nchk:
        sys.exit("[check] no overlap to verify the conversion against — refusing.")

    if not a.apply:
        print("report only — rerun with --apply to write.")
        return
    stamp = sorted(srcs)[-1].stem.replace("CHSFileDownload_", "")
    out = NACCS / f"CHSFileDownload_{stamp}_fromH5.zip"
    tmp = out.with_suffix(".zip.partial")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zo:
        for k in new:
            zh, mh = todo[k]
            name = "CSV/" + Path(mh).name.replace(".h5", ".csv")
            zo.writestr(name, h5_to_csv(zipfile.ZipFile(zh).read(mh)))
        zo.writestr("README/converted_from_H5.txt",
                    "Written by scripts/naccs_h5_to_csv.py from H5 members of:\n"
                    + "\n".join(z.name for z in srcs) + "\n"
                    f"{nchk} overlapping ADCIRC points verified against webtool CSVs.\n")
    os.replace(tmp, out)
    print(f"[write] {out.name}: {len(new)} CSV members")


if __name__ == "__main__":
    main()
