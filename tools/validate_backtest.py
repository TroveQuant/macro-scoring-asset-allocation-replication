#!/usr/bin/env python3
"""Independent output checks for the twelve backtest invariants.

The long-only check follows ``run.allow_short`` recorded in ``report.json`` by the
run that produced the outputs, not only ``config/base.yml``.  Outputs written
before the switch existed have no such field (they came from the original
long/short code), so the check is skipped with a warning.  After a fresh
official run pass ``--require-current-run``: missing exposure metrics, a missing
``run.allow_short`` or a mismatch with the config then fail instead of warning.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np
import pandas as pd
import yaml

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_ALLOW_SHORT=False  # mirrors macro_allocation.config.DEFAULT_ALLOW_SHORT (long-only)

def fail(message: str) -> int:
    print(f"ERROR: {message}",file=sys.stderr); return 2

def warn(message: str) -> None:
    print(f"WARNING: {message}",file=sys.stderr)

def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config",default="config/base.yml",help="repository-relative config (default: config/base.yml)")
    parser.add_argument("--outputs",default="outputs",help="output directory to check (default: outputs)")
    parser.add_argument("--require-current-run",action="store_true",
                        help="fail instead of warning when exposure metrics or run.allow_short are missing, "
                             "or run.allow_short differs from the config; use right after a fresh official run")
    args=parser.parse_args(argv)
    out=ROOT/args.outputs
    try:
        cfg=yaml.safe_load((ROOT/args.config).read_text(encoding="utf-8"))
        monthly=pd.read_csv(out/"monthly_returns.csv",parse_dates=["date"]).set_index("date")
        nav=pd.read_csv(out/"nav_curve.csv",parse_dates=["date"]).set_index("date")
        weights=pd.read_csv(out/"allocation_weights.csv",parse_dates=["date"]).set_index("date")
        assets=pd.read_csv(out/"asset_returns.csv",parse_dates=["date"]).set_index("date")
        macro=pd.read_csv(out/"macro_scores.csv",parse_dates=["signal_date","observation_date","available_date"])
        reb=pd.read_csv(out/"rebalance_records.csv",parse_dates=["signal_date","execution_date","return_period_end"])
        metrics=pd.read_csv(out/"performance_metrics.csv").iloc[0]
        manifest=json.loads((out/"input_manifest.json").read_text(encoding="utf-8"))
        run=json.loads((out/"report.json").read_text(encoding="utf-8")).get("run",{})
    except Exception as exc: return fail(f"cannot load outputs ({type(exc).__name__})")
    frames=[monthly,nav,weights,assets,macro,reb]
    if any(frame.isna().any().any() for frame in frames): return fail("an output contains null values")
    for frame in frames:
        numeric=frame.select_dtypes(include=[np.number])
        if not np.isfinite(numeric.to_numpy()).all(): return fail("an output contains non-finite values")
    if not (reb.signal_date < reb.execution_date).all(): return fail("signal is not earlier than execution")
    if not (reb.execution_date <= reb.return_period_end).all(): return fail("execution follows return-period end")
    if not (macro.observation_date <= macro.available_date).all() or not (macro.available_date <= macro.signal_date).all(): return fail("macro data used before available")
    if not np.allclose(weights.drop(columns="CASH").abs().sum(axis=1)+weights.CASH,1,atol=1e-10): return fail("weights violate gross-exposure constraint")
    expected=set(cfg["assets"])|{"CASH"}
    if set(weights)!=expected or set(assets)!=expected: return fail("asset mapping is incomplete")
    active=weights.abs()>1e-12
    if (active & assets.isna()).any().any(): return fail("held asset return is missing")
    expected_cost=monthly.turnover*float(cfg["project"]["transaction_cost_bps"])/10000
    if not np.allclose(monthly.transaction_cost,expected_cost,atol=1e-12): return fail("transaction costs do not equal turnover times cost rate")
    recalc_nav=(1+monthly.strategy_return).cumprod()
    if not np.allclose(nav.strategy_nav,recalc_nav,atol=1e-12): return fail("strategy NAV cannot be independently compounded")
    recalc_dd=recalc_nav/recalc_nav.cummax()-1
    if not np.isclose(float(metrics.max_drawdown),float(recalc_dd.min()),atol=1e-12): return fail("max drawdown cannot be independently reproduced")
    if not monthly.index.equals(nav.index) or not monthly.index.equals(weights.index) or not monthly.index.equals(assets.index): return fail("strategy and benchmark dates are not aligned")
    if monthly.index.max()>pd.Timestamp(cfg["data"]["as_of_date"]): return fail("latest result uses future return")
    if manifest.get("raw_redistribution") is not False or not manifest.get("inputs"): return fail("input manifest is incomplete")
    config_short=cfg["project"].get("allow_short",DEFAULT_ALLOW_SHORT)
    if not isinstance(config_short,bool): return fail("project.allow_short in the config must be a boolean")
    run_short=run.get("allow_short") if isinstance(run,dict) else None
    if run_short is None:
        message="report.json has no run.allow_short (outputs predate the switch and came from the original long/short code)"
        if args.require_current_run: return fail(message)
        warn(message+"; long-only check skipped; rerun the official entry point."); long_only=False
    elif not isinstance(run_short,bool): return fail("run.allow_short in report.json must be a boolean")
    else:
        if run_short is not config_short:
            message=f"outputs were produced with allow_short={str(run_short).lower()} but the config says {str(config_short).lower()}"
            if args.require_current_run: return fail(message)
            warn(message+"; checking the outputs against the setting of the run that produced them.")
        long_only=run_short is False
    risky=weights.drop(columns="CASH")
    if long_only and (risky<-1e-12).any().any(): return fail("long-only run produced short weights")
    exposure={"average_net_exposure":risky.sum(axis=1).mean(),"average_gross_exposure":risky.abs().sum(axis=1).mean(),
              "average_long_exposure":risky.clip(lower=0).sum(axis=1).mean(),"average_short_exposure":(-risky.clip(upper=0)).sum(axis=1).mean(),
              "average_cash_weight":weights.CASH.mean()}
    present=[k for k in exposure if k in metrics.index]
    if present and len(present)!=len(exposure): return fail("exposure metrics are incomplete")
    if present and not all(np.isclose(float(metrics[k]),float(v),atol=1e-12) for k,v in exposure.items()): return fail("exposure metrics cannot be independently reproduced")
    if not present:
        message="performance_metrics.csv has no exposure metrics (outputs predate exposure reporting)"
        if args.require_current_run: return fail(message)
        warn(message+"; rerun the official entry point.")
    extra=(["long-only weights"] if long_only else [])+(["exposure metrics"] if present else [])
    print("Backtest validation passed: 12 invariants checked, including timing, costs, compounding and finite outputs"
          +(f"; also checked: {', '.join(extra)}." if extra else ".")+("" if present else " Exposure metrics absent."))
    return 0
if __name__=="__main__": raise SystemExit(main())
