"""Figures for the validation report.

Matplotlib only. Each function returns the Figure so callers can save or
embed it. Colours: a fixed three-slot categorical order (blue, orange, aqua;
checked for colour-vision-deficiency separation), a single-hue blue ramp for
magnitudes, and grey for reference lines.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

from . import config, spatial  # noqa: E402

SLOT = ["#2a78d6", "#eb6834", "#1baf7a"]       # categorical, in this order only
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS, SURFACE = "#e1e0d9", "#c3c2b7", "#fcfcfb"
BLUES = LinearSegmentedColormap.from_list(
    "blues", ["#cde2fb", "#86b6ef", "#3987e5", "#256abf", "#184f95", "#0d366b"])

REGION_LABEL = {k: r.name for k, r in config.REGIONS.items()}
MODEL_LABEL = {"linear": "Ridge", "rf": "Random forest", "xgb": "XGBoost"}

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": AXIS, "axes.linewidth": 0.8, "axes.labelcolor": INK2,
    "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlecolor": INK,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelcolor": INK2, "ytick.labelcolor": INK2,
    "font.size": 9, "legend.frameon": False, "legend.labelcolor": INK2,
})


def _regions(df_or_list):
    keys = df_or_list if isinstance(df_or_list, list) else sorted(df_or_list["region"].unique())
    return [k for k in config.REGIONS if k in keys] + [k for k in keys if k not in config.REGIONS]


def plot_study_design(df: pd.DataFrame, block_km: float, folds: dict[str, pd.Series],
                      buffer_m: float = 1000.0, show_fold: int = 0):
    """One spatial-CV fold per region: test blocks, training shots, buffer exclusion."""
    regions = _regions(df)
    fig, axes = plt.subplots(1, len(regions), figsize=(5.2 * len(regions), 5.0))
    axes = np.atleast_1d(axes)
    for ax, r in zip(axes, regions):
        g = df[df.region == r]
        f = folds[r].loc[g.index]
        te = (f == show_fold).to_numpy()
        xy = g[["x_m", "y_m"]].to_numpy() / 1000.0
        keep = spatial.buffer_mask(xy[~te] * 1000, xy[te] * 1000, buffer_m)
        tr_xy = xy[~te]
        ax.scatter(*tr_xy[~keep].T, s=2, c=AXIS, lw=0, label=f"Dropped by {buffer_m/1000:g} km buffer")
        ax.scatter(*tr_xy[keep].T, s=2, c=SLOT[0], lw=0, label="Training shots")
        ax.scatter(*xy[te].T, s=2, c=SLOT[1], lw=0, label=f"Test fold {show_fold + 1}")
        lo, hi = np.floor(xy.min(0) / block_km) * block_km, np.ceil(xy.max(0) / block_km) * block_km
        ax.set_xticks(np.arange(lo[0], hi[0] + 1e-6, block_km))
        ax.set_yticks(np.arange(lo[1], hi[1] + 1e-6, block_km))
        ax.tick_params(labelbottom=False, labelleft=False, length=0)
        ax.set_aspect("equal")
        ax.set_title(REGION_LABEL.get(r, r), loc="left")
        ax.set_xlabel(f"Grid = {block_km:g} km spatial blocks (east →)")
    axes[0].legend(loc="upper left", bbox_to_anchor=(0, -0.08), ncol=3, markerscale=5)
    fig.suptitle("Spatial block cross-validation: GEDI tracks, one test fold",
                 x=0.01, ha="left", fontsize=12, fontweight="bold", color=INK)
    fig.tight_layout()
    return fig


def plot_variogram(vg: dict, block_km: float):
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    for i, r in enumerate(_regions(list(vg))):
        v = vg[r]
        ax.plot(v["lag_m"] / 1000, v["gamma"], "-o", color=SLOT[i], lw=2, ms=4,
                label=f"{REGION_LABEL.get(r, r)} (range ≈ {v['range_m']/1000:.1f} km)")
    ax.axvline(block_km, color=MUTED, lw=1)
    ax.annotate(f"block size {block_km:g} km", (block_km, ax.get_ylim()[0]), xytext=(4, 6),
                textcoords="offset points", color=INK2, fontsize=8)
    ax.set_xlabel("Lag distance (km)")
    ax.set_ylabel("Semivariance of ridge residuals (m²)")
    ax.set_title("Residual autocorrelation sets the block size", loc="left")
    ax.legend(loc="upper right")
    fig.tight_layout()
    return fig


def plot_scheme_rmse(cv: pd.DataFrame, indep: pd.DataFrame | None, tr: pd.DataFrame,
                     models: list[str]):
    """RMSE (vs GEDI) under each evaluation scheme, per region and model."""
    regions = _regions(cv)
    schemes = ["random", "spatial", "spatial+buffer"]
    labels = ["Random\nk-fold", "Spatial\nblocks", "Spatial +\nbuffer"]
    if indep is not None and len(indep):
        schemes.append("independent")
        labels.append("New area\n(synthetic)")
    schemes.append("transfer")
    labels.append("Other\necoregion")

    fig, axes = plt.subplots(1, len(regions), figsize=(5.6 * len(regions), 3.9), sharey=True)
    axes = np.atleast_1d(axes)
    w = 0.8 / len(models)
    for ax, r in zip(axes, regions):
        for j, m in enumerate(models):
            vals = []
            for s in schemes:
                if s == "independent":
                    v = indep[(indep.region == r) & (indep.model == m)]["rmse"].mean()
                elif s == "transfer":
                    v = tr[(tr.test_region == r) & (tr.model == m)]["rmse"].mean()
                else:
                    v = cv[(cv.region == r) & (cv.model == m) & (cv.scheme == s)
                           & (cv.reference == "GEDI RH98")]["rmse"].iloc[0]
                vals.append(v)
            x = np.arange(len(schemes)) + (j - (len(models) - 1) / 2) * w
            ax.bar(x, vals, width=w * 0.85, color=SLOT[j], label=MODEL_LABEL.get(m, m))
        ax.set_xticks(np.arange(len(schemes)))
        ax.set_xticklabels(labels)
        ax.grid(axis="x", visible=False)
        ax.set_title(REGION_LABEL.get(r, r), loc="left")
    axes[0].set_ylabel("RMSE vs GEDI RH98 (m)")
    axes[0].legend(loc="upper left")
    fig.suptitle("The same model scores differently depending on how it is tested",
                 x=0.01, ha="left", fontsize=12, fontweight="bold", color=INK)
    fig.tight_layout()
    return fig


def plot_height_class(tab: pd.DataFrame, min_n: int = 30):
    """RMSE and bias by height class: spatial CV vs cross-region transfer (XGBoost)."""
    regions = _regions(tab)
    fig, axes = plt.subplots(2, len(regions), figsize=(5.6 * len(regions), 6.0), sharex=True,
                             sharey="row")
    axes = np.atleast_2d(axes).reshape(2, len(regions))
    # classes with almost no shots (real GEDI has ~no RH98 < 2 m) are left out
    big = tab[tab["n"] >= min_n]["height_class"].astype(str).unique()
    classes = [c[0] for c in config.HEIGHT_CLASSES if c[0] in big]
    for c, r in enumerate(regions):
        for i, (scheme, lab) in enumerate([("spatial", "Spatial-block CV"),
                                           ("transfer", "Trained on other ecoregion")]):
            t = tab[(tab.region == r) & (tab.scheme == scheme)].copy()
            t = t.set_index(t["height_class"].astype(str)).reindex(classes)
            t.loc[t["n"] < min_n, ["rmse", "bias"]] = np.nan
            x = np.arange(len(classes)) + (i - 0.5) * 0.38
            axes[0, c].bar(x, t["rmse"], width=0.34, color=SLOT[i], label=lab)
            axes[1, c].bar(x, t["bias"], width=0.34, color=SLOT[i], label=lab)
        axes[0, c].set_title(REGION_LABEL.get(r, r), loc="left")
        axes[1, c].axhline(0, color=AXIS, lw=0.8)
        axes[1, c].set_xticks(np.arange(len(classes)))
        axes[1, c].set_xticklabels([k.replace(" ", "\n", 1) for k in classes], fontsize=8)
        for a in axes[:, c]:
            a.grid(axis="x", visible=False)
    axes[0, 0].set_ylabel("RMSE (m)")
    axes[1, 0].set_ylabel("Bias, predicted − GEDI (m)")
    axes[0, 0].legend(loc="upper left")
    fig.suptitle("XGBoost error by fuel-relevant height class (binned on GEDI RH98)",
                 x=0.01, ha="left", fontsize=12, fontweight="bold", color=INK)
    fig.tight_layout()
    return fig


def plot_scatter(oof: pd.DataFrame, pred_col: str, ref_col: str = config.TARGET):
    regions = _regions(oof)
    fig, axes = plt.subplots(1, len(regions), figsize=(4.4 * len(regions) + 0.8, 4.3),
                             layout="constrained")
    axes = np.atleast_1d(axes)
    hi = float(np.nanpercentile(oof[ref_col], 99.5))
    for ax, r in zip(axes, regions):
        g = oof[oof.region == r]
        hb = ax.hexbin(g[ref_col], g[pred_col], gridsize=40, extent=(0, hi, 0, hi),
                       cmap=BLUES, mincnt=1, bins="log", linewidths=0)
        ax.plot([0, hi], [0, hi], color=INK2, lw=1)
        ax.set_xlim(0, hi); ax.set_ylim(0, hi); ax.set_aspect("equal")
        ax.set_xlabel(f"GEDI {ref_col.upper()} (m)")
        ax.set_title(REGION_LABEL.get(r, r), loc="left")
    axes[0].set_ylabel("Predicted (spatial-block CV) (m)")
    cb = fig.colorbar(hb, ax=axes, shrink=0.8, pad=0.02)
    cb.set_label("Shots per cell (log)", color=INK2)
    cb.outline.set_visible(False)
    return fig


def plot_coverage(agg: dict[str, pd.DataFrame], nominal: float,
                  methods: dict[str, list[str]], n_splits: int, legend_loc: str = "lower left"):
    """Interval coverage per group for each method, mean ± 1 sd over block splits.

    ``agg`` maps a panel title to an aggregated table with a ``group`` column;
    ``methods`` maps the same titles to up to three methods, drawn in slot
    order. The third slot is always the Mondrian variant for that panel.
    """
    names = {"raw": "Quantile XGBoost (raw)", "cqr": "CQR",
             "mondrian": "Mondrian CQR (per group shown)",
             "mondrian_region": "Mondrian CQR (per group shown)"}
    panels = list(agg)
    widths = [max(len(agg[p]["group"].unique()), 2) for p in panels]
    fig, axes = plt.subplots(1, len(panels), figsize=(sum(widths) * 1.15 + 1.5, 4.2),
                             sharey=True, gridspec_kw={"width_ratios": widths})
    axes = np.atleast_1d(axes)
    for ax, p in zip(axes, panels):
        t = agg[p]
        groups = list(dict.fromkeys(t["group"]))
        ms = [m for m in methods[p] if m in set(t["method"])]
        w = 0.8 / len(ms)
        for j, m in enumerate(ms):
            tt = t[t.method == m].set_index("group").reindex(groups)
            x = np.arange(len(groups)) + (j - (len(ms) - 1) / 2) * w
            ax.errorbar(x, tt["coverage"], yerr=tt["coverage_sd"].fillna(0), fmt="o",
                        ms=6, color=SLOT[j], ecolor=SLOT[j], elinewidth=1.2, capsize=0,
                        label=names.get(m, m))
        ax.axhline(nominal, color=INK2, lw=1)
        ax.set_xticks(np.arange(len(groups)))
        ax.set_xticklabels(groups, fontsize=8)
        ax.set_xlim(-0.6, len(groups) - 0.4)
        ax.grid(axis="x", visible=False)
        ax.set_title(p, loc="left", fontsize=10)
    axes[0].set_ylabel(f"Empirical coverage (target {nominal:.0%})")
    axes[0].set_ylim(0.4, 1.02)
    axes[0].legend(loc=legend_loc)
    fig.text(0.01, 0.01, f"Dots: mean over {n_splits} random spatial-block splits; "
             "bars: ±1 sd. Line: nominal coverage.", color=MUTED, fontsize=8)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    return fig


def plot_evt_residuals(oof: pd.DataFrame, pred_col: str, ref_col: str = config.TARGET):
    regions = _regions(oof)
    groups = [g for g in config.EVT_GROUPS if g in set(oof["evt_group"])]
    fig, ax = plt.subplots(figsize=(1.6 * len(groups) + 2.5, 3.9))
    w = 0.36
    for i, r in enumerate(regions):
        g = oof[oof.region == r]
        data, pos = [], []
        for k, grp in enumerate(groups):
            v = (g[pred_col] - g[ref_col])[g.evt_group == grp].dropna().to_numpy()
            if len(v) >= 20:
                data.append(v)
                pos.append(k + (i - 0.5) * (w + 0.04))
        bp = ax.boxplot(data, positions=pos, widths=w, patch_artist=True, showfliers=False,
                        medianprops=dict(color=SURFACE, lw=1.5),
                        whiskerprops=dict(color=SLOT[i]), capprops=dict(color=SLOT[i]))
        for b in bp["boxes"]:
            b.set(facecolor=SLOT[i], edgecolor=SLOT[i])
        ax.plot([], [], "s", color=SLOT[i], label=REGION_LABEL.get(r, r))
    ax.axhline(0, color=INK2, lw=1)
    ax.set_xticks(np.arange(len(groups)))
    ax.set_xticklabels(groups)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("Residual, predicted − GEDI (m)")
    ax.set_title("Spatial-CV residuals by vegetation type (box = IQR, whiskers = 1.5 IQR)",
                 loc="left")
    ax.legend(loc="lower right")
    fig.tight_layout()
    return fig
