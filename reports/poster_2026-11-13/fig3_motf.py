"""Poster Figure 3: the model's Sandy flood extent against FEMA's MOTF surge extent.

    NJ_DOMAIN=v4_refreeze_swz_v11 python reports/poster_2026-11-13/fig3_motf.py \
        --arm p4-premier+rain-off+weir-elizabeth-rahway --stem fig3_motf

Two stages, both in this one call:

1. CLASSIFY (heavy, ~110 GB, ~10 min): every 15 m cell of the domain's MOTF raster is
   put in one class, on EXACTLY the rules of ``nj_sfincs.validate.metrics.motf_metrics``
   (the scorer): the run's native floodmap is opened through ``validate.load_floodmap``
   (de-rotated through the affine, read-only), sampled at MOTF cell centres the way the
   scorer samples it, screened with ``simulated_mask`` (the run's own active faces) and
   ``motf_exclude_mask`` (the domain's NJ-only validity raster + exclude boxes). The
   class raster is cached as a uint8 GeoTIFF under ``--cache`` (scratch), and the CSI /
   POD / FAR recomputed from it must equal the arm's published metric row (self-check,
   printed; a mismatch is reported loudly, not hidden).
2. PLOT (light): overview + three insets at full 15 m. The overview is decimated with a
   categorical-safe block mode (never bilinear): see ``decimate``.

The floodmap is never written: the script reads ``$FM_ROOT/<domain>/<arm>/
floodmap_hmax_native.tif`` (``logs/floodmap_fix_2026-11-12/rescore.sh``) when it exists,
else the run dir's ``floodmap_hmax_lev3.tif`` when it is native and fresh, else REFUSES
(it never downscales into a run dir). Same order as ``paired_hwm_bootstrap.pick_floodmap``.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

FM_ROOT = Path(os.environ.get("FM_ROOT", "/scratch/tpj8/floodmap_fix_2026-11-12"))
CACHE = Path("/scratch/tpj8/poster_2026-11-13/fig3")

# class codes of the cached raster
OUTSIDE, WATER, NOTMODEL, EXCL, DRY, HIT, MISS, FALSE = range(8)
NAMES = {
    OUTSIDE: "no data",
    WATER: "water (bed <= 0 m)",
    NOTMODEL: "land outside the model",
    EXCL: "land the FEMA map cannot judge (outside NJ)",
    DRY: "dry in both",
    HIT: "hit",
    MISS: "miss",
    FALSE: "false alarm",
}

# insets: (label, title, lon0, lon1, lat0, lat1)
INSETS = [
    ("A", "Hoboken, Jersey City, Newark Bay", -74.175, -74.015, 40.655, 40.765),
    ("B", "Barnegat Bay and Long Beach Island", -74.27, -74.07, 39.62, 39.80),
    ("C", "Cape May", -74.98, -74.80, 38.92, 39.06),
]


# ── 1. classify ─────────────────────────────────────────────────────────────────────
def pick_floodmap(dom: str, arm: str, run: Path) -> Path:
    from nj_sfincs.validate import core

    cand = FM_ROOT / dom / arm / "floodmap_hmax_native.tif"
    if cand.is_file() and core.floodmap_cache_fresh(run, cand):
        return cand
    own = run / "floodmap_hmax_lev3.tif"
    if core.floodmap_cache_fresh(run, own):
        return own
    sys.exit(
        f"no native, fresh floodmap for {arm}: neither {cand} nor {own} — score the arm "
        "first (run_experiments.py --validate-only); this script never downscales"
    )


def classify(dom: str, arm: str, out: Path) -> dict:
    import rasterio

    import nj_sfincs  # noqa: F401  (pyproj before hydromt_sfincs)
    from nj_sfincs import premier
    from nj_sfincs.config import exp_root
    from nj_sfincs.validate import core
    from nj_sfincs.validate.metrics import (
        DATA,
        DEPTH_MIN,
        motf_exclude_mask,
        motf_path,
    )

    run = exp_root() / arm
    whole, why = premier.output_complete(run)
    if whole is not True:
        sys.exit(f"{run}: output not WHOLE ({whole}: {why}) — not plotting")
    fm = pick_floodmap(dom, arm, run)
    print(f"[classify] {arm}: floodmap {fm}", flush=True)
    t0 = time.time()
    _mod, da_hmax, da_dep = core.load_floodmap(
        run, need_model=False, memo=False, floodmap_fn=fm
    )
    label = da_hmax.attrs.get("floodmap")
    print(f"[classify] loaded ({label}) in {time.time() - t0:.0f} s", flush=True)

    # ---- the scorer's sampling, line for line (metrics.motf_metrics) ----
    with rasterio.open(str(motf_path(DATA))) as r:
        motf, mtf, m_nd, prof = r.read(1), r.transform, r.nodata, r.profile
    mod_t = da_dep.rio.transform()
    mh, mw = motf.shape
    Xc = mtf.c + (np.arange(mw) + 0.5) * mtf.a
    Yc = mtf.f + (np.arange(mh) + 0.5) * mtf.e
    mc = np.clip(((Xc - mod_t.c) / mod_t.a).astype(int), 0, da_dep.shape[-1] - 1)
    mr = np.clip(((Yc - mod_t.f) / mod_t.e).astype(int), 0, da_dep.shape[-2] - 1)
    # off the dep grid altogether (clip would repeat the edge): marked OUTSIDE
    inx = ((Xc - mod_t.c) / mod_t.a >= 0) & ((Xc - mod_t.c) / mod_t.a < da_dep.shape[-1])
    iny = ((Yc - mod_t.f) / mod_t.e >= 0) & ((Yc - mod_t.f) / mod_t.e < da_dep.shape[-2])
    dv = da_dep.values
    hv = da_hmax.values
    dv = dv[0] if dv.ndim == 3 else dv
    hv = hv[0] if hv.ndim == 3 else hv
    dep_at = dv[np.ix_(mr, mc)]
    h_at = hv[np.ix_(mr, mc)]
    del da_hmax, da_dep, dv, hv, _mod
    motf_wet = motf == 1
    mod_wet = (h_at >= DEPTH_MIN) & np.isfinite(h_at)
    del h_at
    footprint = (motf != m_nd) & (dep_at > 0.0)
    sim = core.simulated_mask(run, motf.shape, mtf)
    excl = motf_exclude_mask(motf.shape, mtf)
    land_in = footprint & sim
    if excl is not None:
        land_in &= ~excl

    cls = np.full(motf.shape, WATER, np.uint8)
    cls[~np.isfinite(dep_at)] = OUTSIDE
    cls[~iny, :] = OUTSIDE
    cls[:, ~inx] = OUTSIDE
    cls[footprint & ~sim] = NOTMODEL
    if excl is not None:
        cls[footprint & sim & excl] = EXCL
    cls[land_in] = DRY
    cls[land_in & motf_wet & mod_wet] = HIT
    cls[land_in & motf_wet & ~mod_wet] = MISS
    cls[land_in & ~motf_wet & mod_wet] = FALSE
    del dep_at, footprint, sim, excl, land_in, motf_wet, mod_wet

    out.parent.mkdir(parents=True, exist_ok=True)
    prof.update(dtype="uint8", nodata=None, compress="deflate", tiled=True, count=1,
                blockxsize=256, blockysize=256)
    tmp = out.with_name(f".{out.stem}.partial.{os.getpid()}.tif")
    with rasterio.open(tmp, "w", **prof) as w:
        w.write(cls, 1)
        w.update_tags(arm=arm, domain=dom, floodmap=str(fm), floodmap_label=str(label),
                      classes=repr(NAMES), made_by=str(Path(__file__).name))
    os.replace(tmp, out)
    print(f"[classify] wrote {out} in {time.time() - t0:.0f} s", flush=True)
    return counts(cls, abs(mtf.a * mtf.e) / 1e6)


def counts(cls, km2) -> dict:
    n = np.bincount(cls.ravel(), minlength=8)
    nh, nm, nf = int(n[HIT]), int(n[MISS]), int(n[FALSE])
    return {
        "csi": nh / (nh + nm + nf),
        "pod": nh / (nh + nm),
        "far": nf / (nh + nf),
        "km2_hit": nh * km2,
        "km2_miss": nm * km2,
        "km2_false": nf * km2,
        "km2_excluded": int(n[EXCL]) * km2,
    }


def published_row(dom: str, arm: str, row_csv: Path | None):
    """The arm's metric row: an explicit CSV (rescore rows), else experiments/<dom>/metrics.csv."""
    import pandas as pd

    if row_csv is None:
        rc = REPO / "logs/floodmap_fix_2026-11-12/rows" / f"{dom}__{arm}.csv"
        row_csv = rc if rc.is_file() else REPO / "experiments" / dom / "metrics.csv"
    df = pd.read_csv(row_csv)
    key = "arm" if "arm" in df.columns else df.columns[0]
    df = df[df[key] == arm]
    if df.empty:
        return None, row_csv
    return df.iloc[-1], row_csv


# ── 2. plot ─────────────────────────────────────────────────────────────────────────
def decimate(cls: np.ndarray, f: int, flood_share: float = 0.25) -> np.ndarray:
    """Categorical block reduction by ``f`` (never bilinear).

    A block shows its commonest FLOOD class (hit / miss / false alarm) when flood
    classes cover at least ``flood_share`` of it, otherwise its commonest background
    class. Mode alone would erase thin flooded strips; any-flood-wins would inflate them.
    """
    H, W = (cls.shape[0] // f) * f, (cls.shape[1] // f) * f
    b = cls[:H, :W].reshape(H // f, f, W // f, f)
    cnt = np.stack([(b == k).sum(axis=(1, 3)) for k in range(8)])
    flood = cnt[[HIT, MISS, FALSE]]
    bg = cnt[[OUTSIDE, WATER, NOTMODEL, EXCL, DRY]]
    best_f = np.array([HIT, MISS, FALSE])[flood.argmax(0)]
    best_b = np.array([OUTSIDE, WATER, NOTMODEL, EXCL, DRY])[bg.argmax(0)]
    use_f = flood.sum(0) >= flood_share * f * f
    return np.where(use_f, best_f, best_b).astype(np.uint8)


def lonlat_box_to_rc(tr, lon0, lon1, lat0, lat1, epsg):
    from pyproj import Transformer

    t = Transformer.from_crs(4326, epsg, always_xy=True)
    xs, ys = t.transform([lon0, lon1, lon0, lon1], [lat0, lat0, lat1, lat1])
    inv = ~tr
    cols, rows = zip(*(inv * (x, y) for x, y in zip(xs, ys)))
    return (int(min(rows)), int(np.ceil(max(rows))), int(min(cols)), int(np.ceil(max(cols))))


def plot(cls_tif: Path, stats: dict, stem: str, subtitle: str, footer: str):
    import matplotlib.pyplot as plt
    import rasterio
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch, Rectangle

    from poster_style import C, apply, save

    apply()
    with rasterio.open(cls_tif) as r:
        cls = r.read(1)
        tr = r.transform
        epsg = r.crs.to_epsg()

    grey = "#BDBDBD"
    colours = {
        OUTSIDE: "#FFFFFF",
        WATER: C["water"],
        NOTMODEL: "#FFFFFF",
        EXCL: grey,
        DRY: "#E9E4D8",
        HIT: C["hit"],
        MISS: C["miss"],
        FALSE: C["false"],
    }
    cmap = ListedColormap([colours[k] for k in range(8)])
    kw = dict(cmap=cmap, vmin=-0.5, vmax=7.5, interpolation="nearest")

    # crop the overview to where something was scored (+ margin)
    scored = (cls >= DRY) | (cls == EXCL)
    rows = np.where(scored.any(1))[0]
    cols = np.where(scored.any(0))[0]
    pad = 200
    r0, r1 = max(rows[0] - pad, 0), min(rows[-1] + pad, cls.shape[0])
    c0, c1 = max(cols[0] - pad, 0), min(cols[-1] + pad, cls.shape[1])
    f = 8
    ov = decimate(cls[r0:r1, c0:c1], f)

    fig = plt.figure(figsize=(12, 13.2))
    gs = fig.add_gridspec(
        4, 2, width_ratios=[1.0, 0.82], height_ratios=[1, 1, 1, 0.5],
        hspace=0.18, wspace=0.06, left=0.02, right=0.98, top=0.93, bottom=0.02,
    )
    ax0 = fig.add_subplot(gs[0:3, 0])
    ax0.imshow(ov, **kw, extent=(c0, c0 + ov.shape[1] * f, r0 + ov.shape[0] * f, r0))
    ax0.set_title("New Jersey coast (120 m cells)", fontsize=18, loc="left")
    ax0.set_xticks([])
    ax0.set_yticks([])
    ax0.minorticks_off()
    ax0.set_aspect("equal")
    # 20 km scale bar
    km = 1000 / tr.a
    xb, yb = c0 + 0.06 * (c1 - c0), r0 + 0.95 * (r1 - r0)
    ax0.plot([xb, xb + 20 * km], [yb, yb], color="k", lw=4, solid_capstyle="butt")
    ax0.text(xb + 10 * km, yb - 0.012 * (r1 - r0), "20 km", ha="center", va="bottom", fontsize=14)

    for i, (lab, title, lo0, lo1, la0, la1) in enumerate(INSETS):
        rr0, rr1, cc0, cc1 = lonlat_box_to_rc(tr, lo0, lo1, la0, la1, epsg)
        ax0.add_patch(Rectangle((cc0, rr0), cc1 - cc0, rr1 - rr0, fill=False, ec="k", lw=1.8))
        ax0.text(cc1 + 60, rr0, lab, fontsize=20, fontweight="bold", va="top", ha="left")
        ax = fig.add_subplot(gs[i, 1])
        sub = cls[rr0:rr1, cc0:cc1]
        ax.imshow(sub, **kw, extent=(cc0, cc1, rr1, rr0))
        ax.set_xticks([])
        ax.set_yticks([])
        ax.minorticks_off()
        ax.set_aspect("equal")
        ax.set_title(f"{lab}  {title}", fontsize=16, loc="left")
        n = np.bincount(sub.ravel(), minlength=8)
        nh, nm, nf = n[HIT], n[MISS], n[FALSE]
        if nh + nm + nf:
            ax.text(
                0.015, 0.03, f"CSI {nh / (nh + nm + nf):.2f}", transform=ax.transAxes,
                fontsize=14, va="bottom", ha="left",
                bbox=dict(boxstyle="square,pad=0.25", fc="white", ec="none", alpha=0.85),
            )
        kmi = 1000 / tr.a
        xb, yb = cc0 + 0.70 * (cc1 - cc0), rr0 + 0.93 * (rr1 - rr0)
        ax.plot([xb, xb + 2 * kmi], [yb, yb], color="k", lw=3, solid_capstyle="butt")
        ax.text(xb + kmi, yb - 0.025 * (rr1 - rr0), "2 km", ha="center", va="bottom", fontsize=13)

    # legend
    handles = [
        Patch(fc=C["hit"], label="Hit: both flooded"),
        Patch(fc=C["miss"], label="Miss: FEMA flooded, model dry"),
        Patch(fc=C["false"], label="False alarm: model flooded, FEMA dry"),
        Patch(fc="#E9E4D8", ec="#999999", lw=0.5, label="Dry in both"),
        Patch(fc=C["water"], label="Open water"),
        Patch(fc=grey, label="Not scored: FEMA map is NJ-only"),
        Patch(fc="#FFFFFF", ec="#999999", lw=0.5, label="Not scored: outside the model"),
    ]
    ax0.legend(handles=handles, loc="upper left", fontsize=13.5, frameon=True,
               framealpha=0.92, edgecolor="none", borderpad=0.5, handlelength=1.3)

    # stat tiles
    axs = fig.add_subplot(gs[3, :])
    axs.axis("off")
    tiles = [
        ("CSI", stats["csi"], "overlap of the two flooded areas\n(1 = perfect match)"),
        ("POD", stats["pod"], "share of FEMA's flooded land\nthe model also floods"),
        ("FAR", stats["far"], "share of the model's flooded land\nFEMA saw dry (0 = none)"),
    ]
    for j, (k, v, gloss) in enumerate(tiles):
        x = 0.02 + j * 0.335
        axs.text(x, 0.93, k, fontsize=20, fontweight="bold", va="top", transform=axs.transAxes)
        axs.text(x + 0.085, 0.99, f"{v:.2f}", fontsize=40, fontweight="bold", va="top",
                 transform=axs.transAxes, color="k")
        axs.text(x, 0.52, gloss, fontsize=15, va="top", transform=axs.transAxes,
                 color="#333333", linespacing=1.15)
    fig.suptitle(
        "Where the model floods vs. where FEMA mapped Sandy's surge", fontsize=22,
        fontweight="bold", x=0.02, ha="left", y=0.995,
    )
    fig.text(0.02, 0.957, subtitle, fontsize=15, ha="left", color="#333333")
    fig.text(0.02, -0.005, footer, fontsize=13, ha="left", va="top", color="#555555")
    save(fig, stem)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--arm", required=True)
    ap.add_argument("--stem", required=True, help="output stem in reports/poster_2026-11-13/")
    ap.add_argument("--row", type=Path, help="metric-row CSV (default: rescore row, else metrics.csv)")
    ap.add_argument("--subtitle", default=None)
    ap.add_argument("--reclassify", action="store_true", help="ignore a cached class raster")
    ap.add_argument("--cache", type=Path, default=CACHE)
    a = ap.parse_args()

    from nj_sfincs import domain
    from nj_sfincs.validate.core import DEPTH_MIN

    dom = domain.active().name
    cls_tif = a.cache / f"{dom}__{a.arm}__motf_classes.tif"
    if a.reclassify or not cls_tif.is_file():
        stats = classify(dom, a.arm, cls_tif)
    else:
        import rasterio

        with rasterio.open(cls_tif) as r:
            stats = counts(r.read(1), abs(r.transform.a * r.transform.e) / 1e6)
        print(f"[classify] reused {cls_tif}")
    row, row_csv = published_row(dom, a.arm, a.row)
    print(
        f"[{dom}/{a.arm}] from the class raster: CSI {stats['csi']:.6f} POD {stats['pod']:.6f} "
        f"FAR {stats['far']:.6f}; km2 hit {stats['km2_hit']:.1f} miss {stats['km2_miss']:.1f} "
        f"false {stats['km2_false']:.1f} excluded {stats['km2_excluded']:.1f}"
    )
    if row is None:
        print(f"⚠️  no metric row for {a.arm} in {row_csv}: plotted numbers are the class raster's")
    else:
        d = {k: abs(stats[k] - float(row[f"motf_{k}"])) for k in ("csi", "pod", "far")}
        flag = "OK" if max(d.values()) < 5e-4 else "🔴 MISMATCH"
        print(f"[self-check vs {row_csv}] row floodmap={row.get('floodmap')} "
              f"CSI {row['motf_csi']:.6f} POD {row['motf_pod']:.6f} FAR {row['motf_far']:.6f} "
              f"-> max |diff| {max(d.values()):.2e} {flag}")
    rain = "rain off" if "rain-off" in a.arm else "rain ON"
    subtitle = a.subtitle or (
        f"Hurricane Sandy, 28-31 Oct 2012. Model 1.1.0 ({rain}) vs FEMA MOTF surge extent; "
        "scored on land, 15 m cells"
    )
    footer = (
        f"Run: {dom} / {a.arm}. FEMA Modeling Task Force (MOTF) Sandy surge extent, NJ only; "
        f"model 'flooded' = peak depth >= {DEPTH_MIN:g} m (the scorer's rule).\n"
        "Scored only on land the model simulated (its own active cells) inside NJ; "
        "open water, DE / PA / NY land and ground outside the model are not scored."
    )
    plot(cls_tif, stats, a.stem, subtitle, footer)


if __name__ == "__main__":
    main()
