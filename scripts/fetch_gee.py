#!/usr/bin/env python3
"""Extract real GEDI L2A shots + Sentinel-2 / SRTM / LANDFIRE predictors from
Google Earth Engine and cache them to CSV.

Requires an Earth Engine account:
    pip install earthengine-api
    earthengine authenticate

Example
-------
python scripts/fetch_gee.py --project YOUR_EE_PROJECT --out data/gee_samples.csv
python scripts/run_validation.py --samples data/gee_samples.csv

Extraction is separate from modelling on purpose: the CSV is the frozen
input of every real-data result, so reruns are reproducible and cheap.
Each region is also cached on its own (data/gee_samples.<region>.csv) as soon
as it is fetched; a rerun skips regions already on disk unless --refresh.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from canopy_fuel import config, data, gee  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--project", required=True, help="Earth Engine Cloud project id")
    p.add_argument("--regions", nargs="+", default=config.DEFAULT_REGIONS, choices=list(config.REGIONS))
    p.add_argument("--max-samples", type=int, default=8000, help="shots kept per region")
    p.add_argument("--tiles", type=int, default=gee.TILES_PER_SIDE, help="tiles per AOI side")
    p.add_argument("--keep-frac", type=float, default=gee.KEEP_FRAC,
                   help="per-shot hash threshold (fraction of screened shots requested)")
    p.add_argument("--seed", type=int, default=config.SEED)
    p.add_argument("--out", default=str(ROOT / "data" / "gee_samples.csv"))
    p.add_argument("--refresh", action="store_true", help="re-fetch regions already cached")
    args = p.parse_args()
    out = Path(args.out)
    t_start = time.time()

    frames = []
    for r in args.regions:
        reg = config.REGIONS[r]
        part = out.with_name(f"{out.stem}.{r}{out.suffix}")
        print(f"{r}: bbox {reg.bbox}; intended {reg.epa_l3}", flush=True)
        print(f"  EPA L3 ecoregions touched: {gee.ecoregions_in_aoi(r, args.project)}", flush=True)
        if part.exists() and not args.refresh:
            df = pd.read_csv(part)
            print(f"  using cached {part.name} ({len(df)} shots)", flush=True)
        else:
            t0 = time.time()
            df = gee.fetch_region(r, project=args.project, max_samples=args.max_samples,
                                  seed=args.seed, tiles=args.tiles, keep_frac=args.keep_frac)
            data.save_samples(df, part)
            print(f"  {len(df)} shots -> {part.name} ({time.time() - t0:.0f} s)", flush=True)
        frames.append(df)

    path = data.save_samples(pd.concat(frames, ignore_index=True), out)
    df = data.load_samples(path)
    print(f"\n{len(df)} shots written to {path} ({time.time() - t_start:.0f} s total)")
    print(df.groupby("region").agg(n=("rh98", "size"), rh98_median=("rh98", "median"),
                                   evt_groups=("evt_group", "nunique")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
