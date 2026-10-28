#!/usr/bin/env python3
"""Print average risky exposure and cash from an existing allocation_weights.csv (read-only)."""
from __future__ import annotations
import argparse, sys
from pathlib import Path
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from macro_allocation.production_metrics import compute_exposure_metrics  # noqa: E402

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", default="outputs/allocation_weights.csv")
    parser.add_argument("--config", default="config/base.yml")
    args = parser.parse_args()
    weights = pd.read_csv(ROOT / args.weights, parse_dates=["date"]).set_index("date")
    cfg = yaml.safe_load((ROOT / args.config).read_text(encoding="utf-8"))
    metrics = compute_exposure_metrics(weights)
    print(f"months: {len(weights)} ({weights.index.min().date()} to {weights.index.max().date()})")
    for key, value in metrics.items():
        print(f"{key}: {value:.4f}")
    print(f"months_with_short_position: {float(weights.drop(columns='CASH').lt(-1e-12).any(axis=1).mean()):.4f}")
    print(f"benchmark_net_exposure: {sum(float(v) for v in cfg['portfolio_weights'].values()):.4f} (static, fully invested)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
