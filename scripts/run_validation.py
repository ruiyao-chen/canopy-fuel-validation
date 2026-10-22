#!/usr/bin/env python3
"""Run the full canopy-height validation and write tables, figures and a summary.

Examples
--------
# Offline, synthetic data with known truth (no Earth Engine needed):
python scripts/run_validation.py --backend synthetic

# Real data: first extract once with scripts/fetch_gee.py, then
python scripts/run_validation.py --samples data/gee_samples.csv

Outputs go to results/<label>/ (CSV tables + summary.md + run_info.json) and
figures/<label>/ (PNG), where <label> is "synthetic" or "gee".
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from canopy_fuel import config, data, experiments as E, features, validation as V  # noqa: E402


def md_table(df: pd.DataFrame, floatfmt: str = ".2f") -> str:
    cols = list(df.columns)
    def fmt(v):
        if isinstance(v, (float, np.floating)):
            return "" if np.isnan(v) else format(v, floatfmt)
        return str(v)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    lines += ["| " + " | ".join(fmt(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--backend", choices=["synthetic"], default="synthetic",
                   help="data source when --samples is not given")
    p.add_argument("--samples", default=None, help="CSV written by scripts/fetch_gee.py")
    p.add_argument("--regions", nargs="+", default=config.DEFAULT_REGIONS, choices=list(config.REGIONS))
    p.add_argument("--models", nargs="+", default=["linear", "rf", "xgb"])
    p.add_argument("--seed", type=int, default=config.SEED)
    p.add_argument("--block-km", default="auto", help="'auto' (variogram) or a number")
    p.add_argument("--buffer-km", type=float, default=1.0)
    p.add_argument("--alpha", type=float, default=config.ALPHA)
    p.add_argument("--repeats", type=int, default=10, help="random block splits for interval checks")
    p.add_argument("--n-independent", type=int, default=3,
                   help="synthetic only: fresh landscapes for the out-of-area check")
    p.add_argument("--fast", action="store_true", help="smaller ensembles (smoke test)")
    p.add_argument("--no-figures", action="store_true")
    p.add_argument("--label", default=None,
                   help="output subfolder name (default: 'gee' with --samples, else the backend)")
    args = p.parse_args()
    t0 = time.time()

    label = args.label or ("gee" if args.samples else args.backend)
    outdir = ROOT / "results" / label
    figdir = ROOT / "figures" / label
    outdir.mkdir(parents=True, exist_ok=True)

    # --- data ------------------------------------------------------------ #
    if args.samples:
        raw = data.load_samples(args.samples)
        raw = raw[raw.region.isin(args.regions)]
        # The cache keeps raw LANDFIRE EVT names; derive groups with the
        # current rules so the grouping can be revised without re-extracting.
        from canopy_fuel import gee
        raw = raw.assign(evt_group=raw["evt_name"].map(gee.evt_group))
    else:
        raw = data.get_samples(args.regions, backend=args.backend, seed=args.seed)
    df = features.add_features(data.quality_filter(raw)).reset_index(drop=True)
    synthetic = "h_true" in df
    print(f"Data: {label}  ({'SYNTHETIC, known truth' if synthetic else 'real GEDI / Sentinel-2 / SRTM'})")
    print(f"  shots: {len(raw)} raw -> {len(df)} after GEDI quality screening")
    for r, g in df.groupby("region"):
        print(f"  {r:18s} n={len(g):5d}  RH98 median {g.rh98.median():5.1f} m, "
              f"p90 {g.rh98.quantile(0.9):5.1f} m")

    # --- block size from residual variogram ------------------------------ #
    block_km, vg = V.choose_block_km(df, seed=args.seed)
    if args.block_km != "auto":
        block_km = float(args.block_km)
    print(f"\nResidual variogram practical range: "
          + ", ".join(f"{r} {v['range_m']/1000:.1f} km" for r, v in vg.items())
          + f"  ->  block size {block_km:g} km, buffer {args.buffer_km:g} km")

    # --- point accuracy under each scheme -------------------------------- #
    cv, oof = E.cv_schemes(df, args.models, block_km, buffer_m=args.buffer_km * 1000,
                           seed=args.seed, fast=args.fast)
    tr, trp = E.transfer(df, args.models, seed=args.seed, fast=args.fast)
    indep = None
    if synthetic and args.n_independent > 0:
        others = [features.add_features(data.quality_filter(
                      data.get_samples(args.regions, backend="synthetic", seed=1000 + k)))
                  for k in range(args.n_independent)]
        indep = E.independent_area(df, others, args.models, seed=args.seed, fast=args.fast)

    rows = []
    for r in sorted(df.region.unique()):
        for m in args.models:
            row = {"region": r, "model": m}
            for s in E.SCHEMES:
                c = cv[(cv.region == r) & (cv.model == m) & (cv.scheme == s) & (cv.reference == "GEDI RH98")]
                row[s] = c["rmse"].iloc[0]
            if indep is not None:
                row["new area (synthetic)"] = indep[(indep.region == r) & (indep.model == m)]["rmse"].mean()
            row["other ecoregion"] = tr[(tr.test_region == r) & (tr.model == m)]["rmse"].iloc[0]
            rows.append(row)
    rmse_by_scheme = pd.DataFrame(rows)
    print("\nRMSE vs GEDI RH98 (m) by evaluation scheme:")
    print(rmse_by_scheme.round(2).to_string(index=False))

    xgb = "xgb" if "xgb" in args.models else args.models[-1]
    full = cv[(cv.model == xgb) & (cv.scheme == "spatial")].drop(columns=["model", "scheme"])
    print(f"\n{xgb} spatial-block CV, full metrics:")
    print(full.round(3).to_string(index=False))
    print(f"\n{xgb} cross-region transfer:")
    print(tr[tr.model == xgb].round(3).to_string(index=False))

    ablation = E.feature_ablation(df, block_km, model=xgb, seed=args.seed, fast=args.fast)
    print(f"\n{xgb} feature ablation: in-region spatial CV vs cross-region RMSE (m); "
          f"bias_transfer_tall = bias on shots with GEDI RH98 >= 15 m:")
    print(ablation.round(2).to_string(index=False))

    ref_err = None
    if synthetic:
        ref_err = V.metrics_table(df, "h_true", "rh98", by=["region"])
        print("\nReference error (GEDI RH98 vs true height, after screening):")
        print(ref_err.round(3).to_string(index=False))

    # --- by height class and vegetation type ----------------------------- #
    oof_tr = oof.copy()
    oof_tr["pred:transfer"] = trp[f"pred:{xgb}:transfer"]
    hc = pd.concat([
        E.by_height_class(oof, f"pred:{xgb}:spatial", extra_by=["region"]).assign(scheme="spatial"),
        E.by_height_class(oof_tr, "pred:transfer", extra_by=["region"]).assign(scheme="transfer"),
    ], ignore_index=True)
    print(f"\n{xgb} by height class (binned on GEDI RH98):")
    print(hc.round(2).to_string(index=False))

    evt_parts = [
        V.metrics_table(oof, config.TARGET, f"pred:{xgb}:spatial", by=["region", "evt_group"]).assign(scheme="spatial"),
        V.metrics_table(oof_tr, config.TARGET, "pred:transfer", by=["region", "evt_group"]).assign(scheme="transfer"),
    ]
    for t in evt_parts:
        t["reference"] = "GEDI RH98"
    if synthetic:
        evt_parts.append(V.metrics_table(oof, "h_true", f"pred:{xgb}:spatial", by=["region", "evt_group"])
                         .assign(scheme="spatial", reference="true height"))
    evt = pd.concat(evt_parts, ignore_index=True)
    print(f"\n{xgb} by vegetation type ({'synthetic types' if synthetic else 'LANDFIRE EVT groups'}):")
    print(evt.round(2).to_string(index=False))

    # --- prediction intervals -------------------------------------------- #
    seeds = range(args.seed, args.seed + args.repeats)
    groupings = {"overall": None, "region": ["region"],
                 "pred_height_class": ["pred_height_class"], "height_class": ["height_class"]}
    within = E.repeated_intervals(E.intervals_within, seeds, groupings, df=df, block_km=block_km,
                                  alpha=args.alpha, fast=args.fast)
    within_agg = {k: E.aggregate_repeats(v) for k, v in within.items()}
    print(f"\n{1 - args.alpha:.0%} intervals, pooled model, {args.repeats} random block splits "
          f"(mean coverage +/- sd):")
    for k, v in within_agg.items():
        print(f"  by {k}:")
        print(v.round(3).to_string(index=False))

    regions = sorted(df.region.unique())
    trans_rep = []
    for a in regions:
        for b in regions:
            if a == b:
                continue
            r = E.repeated_intervals(E.intervals_transfer, seeds, {"overall": None},
                                     prefixes=("", "local:"), df=df, train_region=a,
                                     test_region=b, block_km=block_km, alpha=args.alpha,
                                     fast=args.fast)["overall"]
            trans_rep.append(r.assign(train_region=a, test_region=b))
    trans_agg = E.aggregate_repeats(pd.concat(trans_rep, ignore_index=True))
    print(f"\nIntervals under transfer (calibrated on source region, or on 20% of target blocks):")
    print(trans_agg.round(3).to_string(index=False))

    # --- write tables ---------------------------------------------------- #
    cv.to_csv(outdir / "cv_metrics.csv", index=False)
    tr.to_csv(outdir / "transfer_metrics.csv", index=False)
    ablation.to_csv(outdir / "feature_ablation.csv", index=False)
    rmse_by_scheme.to_csv(outdir / "rmse_by_scheme.csv", index=False)
    hc.to_csv(outdir / "height_class_metrics.csv", index=False)
    evt.to_csv(outdir / "vegetation_type_metrics.csv", index=False)
    if indep is not None:
        indep.to_csv(outdir / "independent_area_metrics.csv", index=False)
    if ref_err is not None:
        ref_err.to_csv(outdir / "reference_error.csv", index=False)
    for k, v in within_agg.items():
        v.to_csv(outdir / f"coverage_within_by_{k}.csv", index=False)
    trans_agg.to_csv(outdir / "coverage_transfer.csv", index=False)

    info = dict(
        label=label, synthetic=synthetic, samples=args.samples,
        regions=args.regions, models=args.models, seed=args.seed, block_km=block_km,
        buffer_km=args.buffer_km, alpha=args.alpha, repeats=args.repeats, fast=args.fast,
        n_raw=int(len(raw)), n_screened=int(len(df)),
        n_by_region={k: int(v) for k, v in df.groupby("region").size().items()},
        variogram_range_km={k: v["range_m"] / 1000 for k, v in vg.items()},
        utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        python=platform.python_version(), runtime_s=None,
    )
    try:
        import sklearn, xgboost
        info["versions"] = dict(numpy=np.__version__, pandas=pd.__version__,
                                sklearn=sklearn.__version__, xgboost=xgboost.__version__)
    except ImportError:
        pass

    # --- summary.md ------------------------------------------------------ #
    cov_cols = ["calibration", "method", "n", "coverage", "coverage_sd", "mean_width"]
    md = [f"# Results: {label}", "",
          ("**Synthetic data with known truth. These numbers test the method; they say "
           "nothing about real-world accuracy.**" if synthetic else
           "**Real GEDI L2A / Sentinel-2 / SRTM samples.**"), "",
          f"Shots after screening: {info['n_by_region']}. Block size {block_km:g} km "
          f"(variogram), buffer {args.buffer_km:g} km, {1 - args.alpha:.0%} intervals, "
          f"{args.repeats} block splits.", "",
          "## RMSE vs GEDI RH98 (m) by evaluation scheme", "", md_table(rmse_by_scheme), "",
          f"## {xgb}: spatial-block CV", "", md_table(full, ".3f"), "",
          f"## {xgb}: cross-region transfer", "", md_table(tr[tr.model == xgb], ".3f"), "",
          f"## {xgb}: feature ablation (in-region spatial CV vs transfer)", "",
          md_table(ablation), ""]
    if ref_err is not None:
        md += ["## Reference error: GEDI RH98 vs true height", "", md_table(ref_err, ".3f"), ""]
    md += [f"## {xgb}: by height class (binned on GEDI RH98)", "", md_table(hc), "",
           f"## {xgb}: by vegetation type", "", md_table(evt), ""]
    for k in groupings:
        cols = cov_cols[:2] + ([] if k == "overall" else groupings[k]) + cov_cols[2:]
        md += [f"## Interval coverage, pooled model, by {k}", "",
               md_table(within_agg[k][cols], ".3f"), ""]
    md += ["## Interval coverage under transfer", "",
           md_table(trans_agg[["train_region", "test_region"] + cov_cols], ".3f"), ""]
    (outdir / "summary.md").write_text("\n".join(md))

    # --- figures --------------------------------------------------------- #
    if not args.no_figures:
        from canopy_fuel import plotting as P
        figdir.mkdir(parents=True, exist_ok=True)
        folds = {r: V.spatial_folds(g, block_km, seed=args.seed) for r, g in df.groupby("region")}
        P.plot_study_design(df, block_km, folds, buffer_m=args.buffer_km * 1000).savefig(figdir / "study_design.png", dpi=130)
        P.plot_variogram(vg, block_km).savefig(figdir / "variogram.png", dpi=130)
        P.plot_scheme_rmse(cv, indep, tr, args.models).savefig(figdir / "rmse_by_scheme.png", dpi=130)
        P.plot_height_class(hc).savefig(figdir / "height_class_error.png", dpi=130)
        P.plot_scatter(oof, f"pred:{xgb}:spatial").savefig(figdir / "pred_vs_gedi.png", dpi=130)
        P.plot_evt_residuals(oof, f"pred:{xgb}:spatial").savefig(figdir / "residuals_by_vegetation.png", dpi=130)

        short = {"coastal_chaparral": "Coast", "sierra_conifer": "Sierra"}
        def panel(t, col):
            return t.assign(group=t[col].map(lambda v: short.get(v, str(v).split(" ")[0])))
        # predicted classes with almost no shots (e.g. <2 m: GEDI's floor keeps
        # predictions above 2 m) give meaningless coverage; leave them out
        phc = within_agg["pred_height_class"]
        p1, p2 = "Within ecoregions, by region", "by predicted height class"
        P.plot_coverage({p1: panel(within_agg["region"], "region"),
                         p2: panel(phc[phc.n >= 30], "pred_height_class")},
                        1 - args.alpha,
                        {p1: ["raw", "cqr", "mondrian_region"], p2: ["raw", "cqr", "mondrian"]},
                        args.repeats).savefig(figdir / "coverage_within.png", dpi=130)
        tt = trans_agg.assign(group=[f"{short.get(a, a)}→{short.get(b, b)}\n{c} cal."
                                     for a, b, c in zip(trans_agg.train_region, trans_agg.test_region,
                                                        trans_agg.calibration)])
        tt = tt[~((tt.calibration == "local") & (tt.method == "raw"))]
        p3 = "Across ecoregions: calibrated on source vs on 20% of target blocks"
        P.plot_coverage({p3: tt}, 1 - args.alpha, {p3: ["raw", "cqr", "mondrian"]},
                        args.repeats, legend_loc="lower right").savefig(figdir / "coverage_transfer.png", dpi=130)
        print(f"\nFigures written to {figdir}")

    info["runtime_s"] = round(time.time() - t0, 1)
    (outdir / "run_info.json").write_text(json.dumps(info, indent=2))
    print(f"Tables and summary.md written to {outdir}  ({info['runtime_s']} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
