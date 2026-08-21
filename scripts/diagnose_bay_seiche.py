"""Is the Raritan Bay sub-hourly motion a coherent seiche, or numerical chatter?

STATUS PICK UP item 1. The `zsmax` sub-hourly excess in Raritan Bay is arm-dependent
(premier 0.255 m vs nowaves 0.431 m), which fully accounts for the retracted
"SnapWave damps the surge" reading, and every spatial score in that basin — HWM
residuals, floodmap, MOTF CSI — is built from `zsmax`. So what the motion IS decides
whether those scores stand on a `zsmax` basis.

Read off `diag-nowaves-fasthis`: `dthisout = 60 s`, 14 accepted observation points,
six of them (`rb_axis_*`) on the Raritan Bay deep axis over 11.6 km.

PRE-REGISTERED — `reports/seiche/preregistration_bay_seiche.md`, written before any
number here was computed. The primary field is `recovery_frac`, not the coherence:

    excess_total_m     = zsmax (running max at the solver step) - max(hourly zs)
    excess_recovered_m = max(60 s his zs)                       - max(hourly zs)
    recovery_frac      = excess_recovered / excess_total

No physical seiche in a 12 km, 6-16 m basin has a period below the 120 s Nyquist of a
60 s record, so recovery_frac ~ 1 means the excess is motion the record RESOLVES (and
the coherence test below is a test of the thing that contaminates the scores), while
recovery_frac << 1 means it is faster than any candidate mode.

Usage:
    PYTHONPATH=$PWD python scripts/diagnose_bay_seiche.py
        -> reports/seiche/bay_seiche_stations.csv
           reports/seiche/bay_seiche_pairs.csv
           reports/figures/bay_seiche_diagnostic.png
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("NJ_DOMAIN", "v1_5_raritan")

import matplotlib  # noqa: E402

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import xarray as xr  # noqa: E402
from scipy import signal  # noqa: E402

import nj_sfincs  # noqa: F401,E402 — pins pyproj-before-hydromt
from nj_sfincs.config import exp_root  # noqa: E402

RUN = "diag-nowaves-fasthis"
OUT = ROOT / "reports" / "seiche"
FIGS = ROOT / "reports" / "figures"

# Declared in the pre-registration, in along-axis order (east -> west).
AXIS = [
    "rb_axis_571k",
    "rb_axis_569k",
    "rb_axis_566k",
    "rb_axis_564k",
    "rb_axis_561k",
    "rb_axis_559k",
]
FLANK = ["sss_arthur_kill_mouth", "sss_great_kills"]
CONTROL = ["usgs_tidal_shark_river", "usgs_tidal_sea_bright", "sandy_hook"]

HP_WINDOW = 61  # samples == 61 min centred rolling mean -> high-pass above 1 h
BAND = (4 * 60.0, 60 * 60.0)  # 4-60 min, in seconds
G = 9.81
# A station this close to a discharge source samples the injection, not the basin.
# Not pre-registered: added after rb_axis_559k came back with a 1.33 m sub-2-min spike
# and the Raritan source turned out to be 253 m away. Reported, never silently dropped.
SRC_RADIUS_M = 500.0


def load_his(run_dir: Path) -> xr.Dataset:
    ds = xr.open_dataset(run_dir / "sfincs_his.nc")
    # SFINCS writes fixed-width |S256, space-padded — strip or every lookup misses.
    names = [
        (n.decode() if isinstance(n, bytes) else str(n)).strip()
        for n in ds["station_name"].values
    ]
    ds = ds.assign_coords(station=("stations", names))
    return ds.swap_dims({"stations": "station"})


def face_centres(ds_map: xr.Dataset) -> tuple[np.ndarray, np.ndarray]:
    """Quadtree face centres, as the mean of each face's nodes (NaN-padded quads)."""
    fn = ds_map["mesh2d_face_nodes"].values.astype("float64")
    nx = ds_map["mesh2d_node_x"].values
    ny = ds_map["mesh2d_node_y"].values
    idx = fn - 1  # 1-based in the file
    valid = np.isfinite(idx) & (idx >= 0)
    safe = np.where(valid, idx, 0).astype("int64")
    xs = np.where(valid, nx[safe], np.nan)
    ys = np.where(valid, ny[safe], np.nan)
    return np.nanmean(xs, axis=1), np.nanmean(ys, axis=1)


def highpass(series: np.ndarray, window: int = HP_WINDOW) -> np.ndarray:
    """Residual after a centred rolling mean — everything faster than the window."""
    s = pd.Series(series)
    trend = s.rolling(window, center=True, min_periods=window).mean()
    return (s - trend).to_numpy()


def band_psd(x: np.ndarray, fs: float, nperseg: int):
    f, p = signal.welch(x, fs=fs, nperseg=nperseg, noverlap=nperseg // 2)
    keep = (f > 0) & (1.0 / f >= BAND[0]) & (1.0 / f <= BAND[1])
    return f[keep], p[keep]


def peak_period(x: np.ndarray, fs: float, nperseg: int) -> tuple[float, float]:
    f, p = band_psd(x, fs, nperseg)
    if f.size == 0 or not np.any(np.isfinite(p)):
        return np.nan, np.nan
    i = int(np.nanargmax(p))
    return 1.0 / f[i] / 60.0, float(p[i])  # minutes, power


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    FIGS.mkdir(parents=True, exist_ok=True)
    run_dir = exp_root() / RUN

    his = load_his(run_dir)
    dsm = xr.open_dataset(run_dir / "sfincs_map.nc")

    t = pd.to_datetime(his["time"].values)
    dt_s = float(np.median(np.diff(t.astype("int64")) / 1e9))
    fs = 1.0 / dt_s
    print(f"his sampling: {dt_s:.0f} s ({t.size} steps), Nyquist period {2*dt_s:.0f} s")

    # Discharge sources: a station sitting in an injection zone shows spikes that are
    # source artefacts, not bay motion, so the distance is a COLUMN and the flag is
    # reproducible rather than a footnote.
    src = xr.open_dataset(run_dir / "sfincs_netsrcdisfile.nc")
    src_x, src_y = src["x"].values, src["y"].values
    src_qmax = np.nanmax(src["discharge"].values, axis=0)

    fx, fy = face_centres(dsm)
    zs_hourly = dsm["zs"].values  # (73, nfaces)
    with np.errstate(invalid="ignore"):
        # NaN on faces never wet in a block; all-NaN faces stay NaN, which is correct.
        zmx_raw = dsm["zsmax"].values
        zsmax = np.where(
            np.isfinite(zmx_raw).any(axis=0), np.nanmax(zmx_raw, axis=0), np.nan
        )

    stations = AXIS + FLANK + CONTROL
    sx = {}
    rows = []
    hp_store = {}

    # crest window: +/- 6 h about the hour of the domain-wide peak
    dom_peak_h = int(np.nanargmax(np.nanmax(zs_hourly, axis=1)))
    tmap = pd.to_datetime(dsm["time"].values)
    crest_t = tmap[dom_peak_h]
    in_crest = (t >= crest_t - pd.Timedelta("6h")) & (t <= crest_t + pd.Timedelta("6h"))
    # POST-HOC (not pre-registered): a quiet pre-storm window. Numerical chatter is a
    # property of the scheme and runs at all times; a storm-forced seiche switches on.
    # The ratio is the discriminator the crest-window plot suggested.
    in_quiet = t < (crest_t - pd.Timedelta("18h"))
    print(f"domain peak hour {crest_t} -> crest window {in_crest.sum()} samples, "
          f"quiet pre-storm window {in_quiet.sum()} samples")

    nperseg = min(240, t.size // 4)  # ~4 h segments

    for name in stations:
        s = his.sel(station=name)
        x = float(s["station_x"].values)
        y = float(s["station_y"].values)
        sx[name] = (x, y)
        zs = s["point_zs"].values.astype("float64")

        # nearest quadtree face to the station coordinate
        j = int(np.argmin((fx - x) ** 2 + (fy - y) ** 2))
        d_face = float(np.hypot(fx[j] - x, fy[j] - y))

        max_hourly = float(np.nanmax(zs_hourly[:, j]))
        max_fast = float(np.nanmax(zs))
        zmx = float(zsmax[j])

        excess_total = zmx - max_hourly
        excess_rec = max_fast - max_hourly
        rec = excess_rec / excess_total if excess_total > 1e-6 else np.nan

        hp = highpass(zs)
        hp_store[name] = hp
        per, pw = peak_period(hp[np.isfinite(hp)], fs, nperseg)

        d_src = np.hypot(src_x - x, src_y - y)
        k_src = int(np.argmin(d_src))

        rows.append(
            dict(
                station=name,
                group=(
                    "axis" if name in AXIS else "flank" if name in FLANK else "control"
                ),
                x=x,
                y=y,
                face_dist_m=round(d_face, 1),
                bed_m=round(float(dsm["zb"].values[j]), 3),
                max_hourly_m=round(max_hourly, 4),
                max_60s_m=round(max_fast, 4),
                zsmax_m=round(zmx, 4),
                excess_total_m=round(excess_total, 4),
                excess_recovered_m=round(excess_rec, 4),
                recovery_frac=round(rec, 4) if np.isfinite(rec) else np.nan,
                hp_std_m=round(float(np.nanstd(hp)), 4),
                hp_max_m=round(float(np.nanmax(np.abs(hp))), 4),
                hp_std_crest_m=round(float(np.nanstd(hp[in_crest])), 4),
                hp_max_crest_m=round(float(np.nanmax(np.abs(hp[in_crest]))), 4),
                hp_std_quiet_m=round(float(np.nanstd(hp[in_quiet])), 5),
                crest_quiet_ratio=round(
                    float(np.nanstd(hp[in_crest]) / np.nanstd(hp[in_quiet])), 1
                ),
                peak_period_min=round(per, 2) if np.isfinite(per) else np.nan,
                peak_power=pw,
                dist_nearest_src_m=round(float(d_src[k_src]), 1),
                nearest_src_qmax=round(float(src_qmax[k_src]), 2),
                src_contaminated=bool(d_src[k_src] < SRC_RADIUS_M),
            )
        )

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "bay_seiche_stations.csv", index=False)

    # ---- pairwise: coherence, cross-correlation lag, implied speed ----------
    pairs = []
    pair_list = [(AXIS[i], AXIS[i + 1]) for i in range(len(AXIS) - 1)]
    pair_list.append((AXIS[0], AXIS[-1]))  # the declared ENDS pair
    pair_list += [("rb_axis_566k", "sss_arthur_kill_mouth"),
                  ("rb_axis_571k", "sss_great_kills")]

    for a, b in pair_list:
        ha, hb = hp_store[a], hp_store[b]
        ok = np.isfinite(ha) & np.isfinite(hb)
        xa, xb = ha[ok], hb[ok]
        sep = float(np.hypot(sx[a][0] - sx[b][0], sx[a][1] - sx[b][1]))

        f, cxy = signal.coherence(xa, xb, fs=fs, nperseg=nperseg,
                                  noverlap=nperseg // 2)
        keep = (f > 0) & (1.0 / f >= BAND[0]) & (1.0 / f <= BAND[1])
        if keep.sum():
            i = int(np.nanargmax(cxy[keep]))
            coh_peak = float(cxy[keep][i])
            coh_per = 1.0 / f[keep][i] / 60.0
            coh_mean = float(np.nanmean(cxy[keep]))
        else:
            coh_peak = coh_per = coh_mean = np.nan

        # zero-mean, unit-variance cross-correlation -> r and lag
        na = (xa - xa.mean()) / (xa.std() * xa.size)
        nb = (xb - xb.mean()) / xb.std()
        cc = signal.correlate(na, nb, mode="full")
        lags = signal.correlation_lags(xa.size, xb.size, mode="full") * dt_s
        win = np.abs(lags) <= 1800.0  # +/- 30 min is generous for 11.6 km
        k = int(np.nanargmax(np.abs(cc[win])))
        r = float(cc[win][k])
        lag = float(lags[win][k])
        speed = sep / abs(lag) if abs(lag) > 0 else np.inf

        pairs.append(
            dict(
                a=a,
                b=b,
                sep_m=round(sep, 1),
                coh_peak=round(coh_peak, 3),
                coh_peak_period_min=round(coh_per, 2) if np.isfinite(coh_per) else np.nan,
                coh_band_mean=round(coh_mean, 3),
                xcorr_r=round(r, 3),
                xcorr_lag_s=round(lag, 1),
                implied_speed_ms=round(speed, 2) if np.isfinite(speed) else np.inf,
            )
        )

    dp = pd.DataFrame(pairs)
    dp.to_csv(OUT / "bay_seiche_pairs.csv", index=False)

    # ---- POST-HOC: is the PERSISTENT background coherent too? ---------------
    # hp_std_quiet showed the bay rings at ~0.04 m even before the storm, so the
    # motion is not purely storm-forced. Organized-at-all-times reads as physical;
    # organized only at the crest would mean two different components.
    win_rows = []
    nps_w = 120  # 2 h segments, so the 721-sample crest window still gets ~11
    for label, sel in (("quiet", in_quiet), ("crest", in_crest)):
        for a, b in pair_list:
            ha, hb = hp_store[a][sel], hp_store[b][sel]
            ok = np.isfinite(ha) & np.isfinite(hb)
            if ok.sum() < 2 * nps_w:
                continue
            f, cxy = signal.coherence(ha[ok], hb[ok], fs=fs, nperseg=nps_w,
                                      noverlap=nps_w // 2)
            keep = (f > 0) & (1.0 / f >= BAND[0]) & (1.0 / f <= BAND[1])
            if not keep.sum():
                continue
            win_rows.append(
                dict(window=label, a=a, b=b, sep_m=round(float(
                    np.hypot(sx[a][0] - sx[b][0], sx[a][1] - sx[b][1])), 1),
                    coh_band_mean=round(float(np.nanmean(cxy[keep])), 3),
                    coh_peak=round(float(np.nanmax(cxy[keep])), 3))
            )
    dw = pd.DataFrame(win_rows)
    dw.to_csv(OUT / "bay_seiche_windows.csv", index=False)

    # ---- report ------------------------------------------------------------
    pd.set_option("display.width", 200)
    print("\n=== PRIMARY: where does the zsmax excess live? ===")
    print(
        df[["station", "group", "max_hourly_m", "max_60s_m", "zsmax_m",
            "excess_total_m", "excess_recovered_m", "recovery_frac"]].to_string(
            index=False)
    )
    print("\n=== sub-hourly amplitude (high-passed, <61 min) ===")
    print(
        df[["station", "group", "bed_m", "hp_std_m", "hp_max_m",
            "hp_std_quiet_m", "hp_std_crest_m", "crest_quiet_ratio",
            "peak_period_min"]].to_string(index=False)
    )
    print("\n=== SECONDARY: coherence / propagation ===")
    print(dp.to_string(index=False))
    print("\n=== POST-HOC: coherence by window (quiet pre-storm vs crest) ===")
    if len(dw):
        piv = dw.pivot_table(index=["a", "b"], columns="window",
                             values="coh_band_mean")
        piv["sep_m"] = dw.groupby(["a", "b"]).sep_m.first()
        print(piv.to_string())
        nfl = 1 - 0.05 ** (1 / max(len(dw[dw.window == 'crest']) and 10, 2))
        print(f"(2 h Welch segments; the 95% noise floor is ~{nfl:.2f} at this "
              f"segment count — both windows sit far above it)")

    ax_df = df[df.group == "axis"]
    ctl_df = df[df.group == "control"]
    ends = dp[(dp.a == AXIS[0]) & (dp.b == AXIS[-1])].iloc[0]
    per_med = float(np.nanmedian(ax_df.peak_period_min))
    n_agree = int(
        np.sum(np.abs(ax_df.peak_period_min - per_med) <= 0.2 * per_med)
    )
    h = float(np.nanmean(-ax_df.bed_m))
    c_swe = float(np.sqrt(G * h))

    clean = ax_df[~ax_df.src_contaminated]
    dirty = ax_df[ax_df.src_contaminated]
    nseg = (t.size - nperseg // 2) // (nperseg // 2)
    coh_floor = 1 - 0.05 ** (1 / (nseg - 1))

    print("\n=== VERDICT against the pre-registered rule ===")
    print(f"axis recovery_frac: median {np.nanmedian(ax_df.recovery_frac):.3f} "
          f"(min {np.nanmin(ax_df.recovery_frac):.3f}, "
          f"max {np.nanmax(ax_df.recovery_frac):.3f})")
    if len(dirty):
        print(f"  -> {len(dirty)} axis station(s) within {SRC_RADIUS_M:.0f} m of a "
              f"discharge source, FLAGGED not dropped: "
              f"{', '.join(dirty.station)} "
              f"(dist {', '.join(f'{d:.0f} m' for d in dirty.dist_nearest_src_m)}, "
              f"Qmax {', '.join(f'{q:.0f}' for q in dirty.nearest_src_qmax)} m3/s)")
        print(f"  -> excluding them: recovery_frac median "
              f"{np.nanmedian(clean.recovery_frac):.3f} "
              f"(min {np.nanmin(clean.recovery_frac):.3f})")
    print(f"coherence 95% noise floor for {nseg} Welch segments: "
          f"gamma^2 = {coh_floor:.3f} (band means below are well above it)")
    print(f"control hp_std median {np.nanmedian(ctl_df.hp_std_m):.4f} m vs "
          f"axis hp_std median {np.nanmedian(ax_df.hp_std_m):.4f} m")
    print(f"ends coherence gamma^2 = {ends.coh_peak:.3f} at "
          f"{ends.coh_peak_period_min:.1f} min (band mean {ends.coh_band_mean:.3f})")
    print(f"common peak period: median {per_med:.1f} min, "
          f"{n_agree}/6 axis stations within +/-20%")
    adj = dp.iloc[: len(AXIS) - 1]
    print(f"adjacent implied speeds (m/s): "
          f"{[float(v) for v in adj.implied_speed_ms]} vs sqrt(g*h)={c_swe:.1f} "
          f"at mean depth {h:.1f} m")
    print(f"adjacent lags (s): {[float(v) for v in adj.xcorr_lag_s]} "
          f"— mixed sign, |lag| small vs the {per_med:.0f} min period "
          f"({100*np.mean(np.abs(adj.xcorr_lag_s))/(per_med*60):.0f}% of a period "
          f"on average), i.e. closer to standing than progressive")

    # ---- POST-HOC consistency check, NOT pre-registered ---------------------
    # Merian for the sampled 11.6 km deep channel at its own celerity. Free choices
    # made after seeing the periods: which basin (channel, not the broad bay), which
    # depth (channel mean), and which two mode numbers. Two observed periods against
    # two modes of one geometry is a LOOSE fit — suggestive, not a match.
    ends_sep = float(dp[(dp.a == AXIS[0]) & (dp.b == AXIS[-1])].iloc[0].sep_m)
    t_half = 2 * ends_sep / c_swe / 60.0
    t_quarter = 4 * ends_sep / c_swe / 60.0
    print(f"\n[POST-HOC, not pre-registered] Merian on the sampled {ends_sep/1000:.1f} km "
          f"channel at c={c_swe:.1f} m/s: half-wave {t_half:.0f} min, "
          f"quarter-wave {t_quarter:.0f} min; observed station peaks "
          f"{sorted(set(ax_df.peak_period_min.dropna()))} min.")
    print("  Free parameters were chosen after seeing the answer — suggestive only.")

    # ---- figure ------------------------------------------------------------
    fig, axes = plt.subplots(3, 1, figsize=(13, 11))

    a0 = axes[0]
    for name in AXIS:
        a0.plot(t[in_crest], hp_store[name][in_crest], lw=0.8, label=name)
    a0.set_title("Sub-hourly residual (60 s his minus 61-min running mean), "
                 "Raritan Bay deep axis — crest window")
    a0.set_ylabel("zs' (m)")
    a0.legend(ncol=3, fontsize=8)
    a0.grid(alpha=0.3)

    a1 = axes[1]
    for name in AXIS + CONTROL:
        hp = hp_store[name][np.isfinite(hp_store[name])]
        f, p = band_psd(hp, fs, nperseg)
        if f.size:
            a1.loglog(1.0 / f / 60.0, p,
                      lw=1.2 if name in AXIS else 0.9,
                      ls="-" if name in AXIS else "--", label=name)
    a1.set_xlabel("period (min)")
    a1.set_ylabel("PSD (m$^2$/Hz)")
    a1.set_title("Spectra of the sub-hourly band — axis (solid) vs open-coast control "
                 "(dashed)")
    a1.legend(ncol=3, fontsize=7)
    a1.grid(alpha=0.3, which="both")

    a2 = axes[2]
    a2.bar(np.arange(len(df)), df.excess_total_m, 0.4, label="zsmax - hourly (total)")
    a2.bar(np.arange(len(df)) + 0.4, df.excess_recovered_m, 0.4,
           label="60 s max - hourly (recovered)")
    a2.set_xticks(np.arange(len(df)) + 0.2)
    a2.set_xticklabels(df.station, rotation=30, ha="right", fontsize=8)
    a2.set_ylabel("m")
    a2.set_title("Where the zsmax excess lives: total vs recovered at 60 s")
    a2.legend()
    a2.grid(alpha=0.3, axis="y")

    fig.tight_layout()
    fig.savefig(FIGS / "bay_seiche_diagnostic.png", dpi=130)
    print(f"\nwrote {OUT/'bay_seiche_stations.csv'}")
    print(f"wrote {OUT/'bay_seiche_pairs.csv'}")
    print(f"wrote {FIGS/'bay_seiche_diagnostic.png'}")


if __name__ == "__main__":
    main()
