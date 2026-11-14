"""One-off (2026-11-14): the edited build_modern_land.py with NO flags vs the 11-13 HEAD version, byte for byte.

    python logs/nj2_bed2026_2026-11-14/head_equivalence.py   (repo root, sfincs env; needs git)
Runs both on tests/test_build_modern_land.py's synthetic case (rotated bed, 2 sources) and compares the two rasters
and the source table. Writes head_equivalence.txt here.
"""
import json, multiprocessing, subprocess, sys, tempfile
# FORK: the HEAD version reads the bed from a module global, which a forkserver worker (3.14 default) re-imports
multiprocessing.set_start_method("fork", force=True)
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT))
tmpd = Path(tempfile.mkdtemp(prefix="bml_head_"))
head_src = subprocess.run(["git", "-C", str(ROOT), "show", "c60be62:scripts/build_modern_land.py"],
                          capture_output=True, text=True, check=True).stdout
(tmpd / "build_modern_land_head.py").write_text(head_src)
sys.path.insert(0, str(tmpd))
import build_modern_land as new  # noqa: E402
import build_modern_land_head as old  # noqa: E402
from tests.test_build_modern_land import TestBedOut  # noqa: E402
t = TestBedOut("test_defaults_are_the_module_constants"); t.setUp()
out = []
for mod, tag in ((new, "new"), (old, "head")):
    mod.BED, mod.OUT, mod.SOURCES = t.bed_land, t.tmp / f"out_{tag}", t.sources
    sys.argv = ["x", "--workers", "1", "--report", str(t.tmp / f"rep_{tag}")]
    assert mod.main() == 0  # both parse sys.argv (new: argv=None)
names = ("modern_land_2026.tif", "modern_land_2026_source.tif")
for n in names:
    a, b = (t.tmp / "out_new" / n).read_bytes(), (t.tmp / "out_head" / n).read_bytes()
    out.append(f"{n}: new {len(a)} B, head {len(b)} B, identical={a == b}")
ja, jb = (json.loads((t.tmp / f"rep_{k}/modern_land_sources.json").read_text()) for k in ("new", "head"))
out.append(f"modern_land_sources.json identical={ja == jb}")
t.tearDown()
print("\n".join(out)); (Path(__file__).parent / "head_equivalence.txt").write_text("\n".join(out) + "\n")
