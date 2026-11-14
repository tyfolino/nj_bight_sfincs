"""Sandy Hook MOTF tallies + candidate exclusion boxes (reads sh_window.npz, the full
class raster for domain totals). python logs/sandy_hook_motf_2026-11-14/analyse.py"""

from pathlib import Path

import numpy as np
import rasterio

HERE = Path(__file__).resolve().parent
KM2 = 15 * 15 / 1e6
# (name, (lon_min, lat_min, lon_max, lat_max)) — the Gateway NRA Sandy Hook unit,
# two pieces so Highlands (west of the Shrewsbury River) stays scored.
BOXES = (
    ("sandy_hook_neck", (-73.982, 40.393, -73.960, 40.415)),
    ("sandy_hook_mid", (-73.995, 40.415, -73.960, 40.432)),
    ("sandy_hook_north", (-74.030, 40.432, -73.960, 40.490)),
)


def tally(c):
    h, m, f = [int((c == k).sum()) for k in (1, 2, 3)]
    return h, m, f


def scores(h, m, f):
    return h / (h + m + f), h / (h + m), f / (h + f)


def main():
    with rasterio.open(HERE / "motf_class_v11.tif") as r:
        full = r.read(1)
    H, M, F = tally(full)
    print(f"DOMAIN hits {H*KM2:.3f} miss {M*KM2:.3f} FA {F*KM2:.3f} km2; "
          "CSI %.6f POD %.6f FAR %.6f" % scores(H, M, F))
    z = np.load(HERE / "sh_window.npz")
    cls, lon, lat = z["cls"], z["lon"], z["lat"]
    inbox = np.zeros(cls.shape, bool)
    for name, (w, s, e, n) in BOXES:
        b = (lon >= w) & (lon <= e) & (lat >= s) & (lat <= n)
        h, m, f = tally(cls[b])
        print(f"{name}: hits {h*KM2:.3f} miss {m*KM2:.3f} FA {f*KM2:.3f} km2; "
              f"already-invalid {int((cls[b]==5).sum())*KM2:.3f}; "
              f"correct-dry {int((cls[b]==4).sum())*KM2:.3f}")
        inbox |= b
    h, m, f = tally(cls[inbox])
    print(f"SPIT: hits {h*KM2:.3f} miss {m*KM2:.3f} FA {f*KM2:.3f} km2 "
          f"(share of domain: hits {h/H:.2%} miss {m/M:.2%} FA {f/F:.2%}); "
          f"newly excluded {(h+m+f+int((cls[inbox]==4).sum()))*KM2:.3f} km2")
    a = scores(H - h, M - m, F - f)
    b = scores(H, M, F)
    print("without spit: CSI %.6f POD %.6f FAR %.6f" % a)
    print("delta: CSI %+.4f POD %+.4f FAR %+.4f" % tuple(x - y for x, y in zip(a, b)))
    # where on the spit: by bed elevation and by source
    bed = z["bed"]
    for nm in ("usace2010", "cudem", "nj10ft", "czmil_2012_11_16", "eaarl_pre_2012_10_26"):
        v = z[nm]
        print(nm, "coverage on scored spit px %.1f%%" % (100 * np.isfinite(v[inbox & np.isin(cls, (1, 2, 3, 4))]).mean()))
    sc = inbox & np.isin(cls, (1, 2, 3, 4))
    win = np.where(np.isfinite(z["usace2010"]), "usace2010", np.where(np.isfinite(z["cudem"]), "cudem", "other"))
    for k in ("usace2010", "cudem", "other"):
        s = sc & (win == k)
        hh, mm, ff = tally(cls[s])
        print(f"bed source {k}: scored {s.sum()*KM2:.3f} km2, hits {hh*KM2:.3f} miss {mm*KM2:.3f} FA {ff*KM2:.3f}")
    cz = z["czmil_2012_11_16"]
    for k, lab in ((3, "FA"), (2, "miss"), (1, "hit")):
        s = inbox & (cls == k)
        d = bed[s] - cz[s]
        d = d[np.isfinite(d)]
        print(f"{lab}: n {s.sum()} bed p50 {np.nanmedian(bed[s]):.2f} m; CZMIL<0 share "
              f"{np.mean(cz[s][np.isfinite(cz[s])] < 0):.2f}; bed-CZMIL p10/50/90 "
              f"{np.percentile(d,10):.2f}/{np.percentile(d,50):.2f}/{np.percentile(d,90):.2f} (n {d.size})")


if __name__ == "__main__":
    main()
