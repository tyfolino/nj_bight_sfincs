"""List / download the 3DEP hydro-flattening breakline deliverables for every USGS lidar project our beds use.

Public bucket: s3://prd-tnm/StagedProducts/Elevation/metadata/<project>/<work unit>/breaklines/ (no auth).
Usage: python -I fetch_breaklines.py [--download] ; raw files go to /scratch/.../audit/water_surface/breaklines/.
"""
import argparse
import re
import sys
import time
import urllib.request
from pathlib import Path

BUCKET = "https://prd-tnm.s3.amazonaws.com/"
PROJECTS = {  # model tier / modern source  ->  3DEP project folder
    "NJ_New_Jersey_SANDY_LiDAR_15": "2014 NJ Sandy lidar (behind nj_10ft_dem / dep3 for the 2012 bed)",
    "NJ_NW_New_Jersey_6_County_Lidar_2017_B17": "usgs_nw_nj_2017",
    "NJ_South_Jersey_Lidar_2018_B18": "usgs_south_nj_2019",
    "NJ_South_Jersey_Lidar_2018_B18_FEMA": "usgs_south_nj_fema_2019",
    "NJ_NE6County_B23": "usgs_nj_ne6county_2024",
    "DE_Statewide_B23": "usgs_de_statewide_2023",
    "PA_17County_D24": "pa_17county_2024",
    "NY_SouthEast4County_A22": "usgs_ny_se4county_2022",
}
OUT = Path("/scratch/tpj8/nj_bight_sfincs_data/audit/water_surface/breaklines")


def ls(prefix, delim=True):
    keys, prefixes, marker = [], [], ""
    while True:
        q = f"{BUCKET}?prefix={prefix}" + ("&delimiter=/" if delim else "") + (f"&marker={marker}" if marker else "")
        t = urllib.request.urlopen(q, timeout=120).read().decode()
        k = re.findall(r"<Key>([^<]*)</Key>\s*<LastModified>[^<]*</LastModified>\s*<ETag>[^<]*</ETag>(?:\s*<ChecksumAlgorithm>[^<]*</ChecksumAlgorithm>)?(?:\s*<ChecksumType>[^<]*</ChecksumType>)?\s*<Size>(\d+)</Size>", t)
        keys += [(a, int(b)) for a, b in k]
        prefixes += re.findall(r"<Prefix>([^<]*)</Prefix>", t)[1:]
        if "<IsTruncated>true</IsTruncated>" not in t or not k:
            return keys, prefixes
        marker = k[-1][0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--download", action="store_true")
    a = ap.parse_args()
    total = 0
    for proj, tier in PROJECTS.items():
        _, wus = ls(f"StagedProducts/Elevation/metadata/{proj}/")
        for wu in wus:
            if "vertical_accuracy" in wu:
                continue
            keys, _ = ls(wu + "breaklines/", delim=False)
            keys = [(k, s) for k, s in keys if not k.endswith(".lock")]
            sz = sum(s for _, s in keys)
            total += sz
            print(f"{proj:42s} {wu.split('/')[-2]:28s} files {len(keys):4d}  {sz / 1e6:8.1f} MB  [{tier}]")
            if a.download:
                for k, s in keys:
                    dst = OUT / proj / wu.split("/")[-2] / k.split("/breaklines/", 1)[1]
                    if dst.exists() and dst.stat().st_size == s:
                        continue
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    for tries in range(4):
                        try:
                            urllib.request.urlretrieve(BUCKET + urllib.request.quote(k), dst)
                            break
                        except Exception as e:  # noqa: BLE001
                            print("  retry", k, e, file=sys.stderr)
                            time.sleep(5 * (tries + 1))
    print(f"TOTAL {total / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
