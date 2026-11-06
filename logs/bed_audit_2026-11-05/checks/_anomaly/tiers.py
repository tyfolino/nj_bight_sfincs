"""Every elevation tier of a bed's recipe, resampled (NEAREST) onto the 25 m context grid G25 and cached in
/scratch/.../audit/_anomaly_context/tiers/<key>.tif — used by anomaly_seam (which tier wins where) and
anomaly_disagree (CUDEM vs lidar). Nearest, not average: a cell carries one real source pixel, so a tier's
coverage edge stays sharp and its value is a real value of that tier (noisy at 25 m; the checks need >= 3 cells).

    python tiers.py [keys ...]        # default: every tier in the v1.1 and modern recipes + the CUDEM/lidar pair
"""

from __future__ import annotations

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

OUT = C.CTX / "tiers"
SKIP = {"bed_buildings_v4_cap10"}  # footprints raise by design; not a "source" for seams


def recipe_keys(bed_dir):
    d = json.JSONDecoder()
    prov = d.raw_decode(open(Path(bed_dir) / "provenance.txt").read())[0]
    return [(e["elevation"], e.get("merge_method", "")) for e in prov["elevation_list"] if e["elevation"] not in SKIP]


def warp(key):
    OUT.mkdir(parents=True, exist_ok=True)
    dst = OUT / f"{key}.tif"
    if dst.exists():
        return key, "cached"
    src = C.cat_path(key)
    if key == "modern_land_2026":  # its SOURCE raster says which lidar won each pixel (0 = the 2012 stack)
        src = Path("/scratch/tpj8/nj_bight_sfincs_data/elevation_modern_2026/modern_land_2026_source.tif")
    tr, h, w = C.g25_meta()
    te = [tr.c, tr.f + h * tr.e, tr.c + w * tr.a, tr.f]
    tmp = dst.with_suffix(".tmp.tif")
    cmd = ["gdalwarp", "-q", "-overwrite", "-t_srs", "EPSG:32618", "-te", *map(str, te), "-tr", "25", "25",
           "-r", "near", "-ot", "Float32", "-dstnodata", "nan", "-wm", "2000", "-co", "COMPRESS=DEFLATE",
           "-co", "TILED=YES", "-multi", "-wo", "NUM_THREADS=2", str(src), str(tmp)]
    meta = C.catalog().get(key, {}).get("metadata", {})
    if meta.get("crs") and key != "modern_land_2026":
        cmd[3:3] = ["-s_srs", f"EPSG:{meta['crs']}"]
    if key == "modern_land_2026":
        cmd[cmd.index("-dstnodata") + 1] = "0"
        cmd[cmd.index("-ot") + 1] = "Byte"
    r = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if r.returncode:
        return key, "FAILED " + r.stderr[-400:]
    tmp.replace(dst)
    return key, "built"


def main(keys):
    with ThreadPoolExecutor(6) as ex:
        for k, s in ex.map(warp, keys):
            print(f"{k:34s} {s}", flush=True)


if __name__ == "__main__":
    V = C.REPO / "experiments/v4_refreeze_swz"
    ks = sys.argv[1:] or sorted({k for b in ("_subgrid_v1_1", "_subgrid_modern2026") for k, _ in recipe_keys(V / b)}
                                | {"deck_fix_v4b", "alloway_pool_v4"})
    main(ks)
