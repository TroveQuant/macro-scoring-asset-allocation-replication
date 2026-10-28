"""Independently reproducible performance metrics."""
from __future__ import annotations
import numpy as np
import pandas as pd
from .errors import DataValidationError

def build_nav(monthly: pd.DataFrame) -> pd.DataFrame:
    strategy = (1 + monthly["strategy_return"]).cumprod()
    benchmark = (1 + monthly["benchmark_return"]).cumprod()
    return pd.DataFrame({"strategy_nav": strategy, "benchmark_nav": benchmark,
                         "strategy_drawdown": strategy / strategy.cummax().clip(lower=1.0) - 1,
                         "benchmark_drawdown": benchmark / benchmark.cummax().clip(lower=1.0) - 1})

EXPOSURE_METRICS = ("average_net_exposure", "average_gross_exposure", "average_long_exposure",
                    "average_short_exposure", "average_cash_weight")

def compute_exposure_metrics(allocations: pd.DataFrame) -> dict[str, float]:
    """Time-averaged risky exposure of executed weights (CASH column excluded from exposure)."""
    if "CASH" not in allocations or allocations.shape[1] < 2 or allocations.empty:
        raise DataValidationError("allocations must contain CASH and at least one risky asset")
    if allocations.isna().any().any() or not np.isfinite(allocations.to_numpy(dtype=float)).all():
        raise DataValidationError("allocations must be complete and finite")
    risky = allocations.drop(columns="CASH").astype(float)
    return {"average_net_exposure": float(risky.sum(axis=1).mean()),
            "average_gross_exposure": float(risky.abs().sum(axis=1).mean()),
            "average_long_exposure": float(risky.clip(lower=0).sum(axis=1).mean()),
            "average_short_exposure": float((-risky.clip(upper=0)).sum(axis=1).mean()),
            "average_cash_weight": float(allocations["CASH"].astype(float).mean())}

def _annualized(nav_end: float, n: int) -> float:
    return float(nav_end ** (12.0 / n) - 1.0)

def compute_metrics(monthly: pd.DataFrame, data_cutoff: str, risk_free_rate: float = 0.0,
                    allocations: pd.DataFrame | None = None) -> dict[str, object]:
    required = {"strategy_return", "benchmark_return", "turnover", "transaction_cost"}
    if not required.issubset(monthly) or monthly.empty or monthly.isna().any().any() or not np.isfinite(monthly.to_numpy()).all():
        raise DataValidationError("metrics input must be non-empty, complete and finite")
    nav = build_nav(monthly); strategy = monthly["strategy_return"]; bench = monthly["benchmark_return"]
    annual_vol = float(strategy.std(ddof=1) * np.sqrt(12)); annual = _annualized(float(nav.strategy_nav.iloc[-1]), len(monthly))
    downside_vol = float(np.sqrt(np.mean(np.minimum(strategy.to_numpy(dtype=float), 0.0) ** 2)) * np.sqrt(12))
    mdd = float(nav.strategy_drawdown.min())
    benchmark_annual = _annualized(float(nav.benchmark_nav.iloc[-1]), len(monthly))
    benchmark_vol = float(bench.std(ddof=1) * np.sqrt(12))
    benchmark_downside_vol = float(np.sqrt(np.mean(np.minimum(bench.to_numpy(dtype=float), 0.0) ** 2)) * np.sqrt(12))
    benchmark_mdd = float(nav.benchmark_drawdown.min())
    if allocations is not None and not allocations.index.equals(monthly.index):
        raise DataValidationError("allocation and return dates must be aligned")
    metrics = {"data_cutoff_date": str(data_cutoff), "backtest_start": monthly.index.min().date().isoformat(),
            "backtest_end": monthly.index.max().date().isoformat(), "observations": int(len(monthly)),
            "cumulative_return": float(nav.strategy_nav.iloc[-1] - 1), "annualized_return": annual,
            "annualized_volatility": annual_vol, "sharpe_ratio": float((annual-risk_free_rate)/annual_vol) if annual_vol else 0.0,
            "sortino_ratio": float((annual-risk_free_rate)/downside_vol) if downside_vol else 0.0,
            "max_drawdown": mdd, "calmar_ratio": float(annual/abs(mdd)) if mdd < 0 else 0.0,
            "monthly_win_rate": float((strategy > 0).mean()),
            "rebalance_count": int(len(monthly)), "annualized_turnover": float(monthly.turnover.mean()*12),
            "total_transaction_cost": float(monthly.transaction_cost.sum()),
            "benchmark_cumulative_return": float(nav.benchmark_nav.iloc[-1]-1),
            "benchmark_annualized_return": benchmark_annual,
            "benchmark_annualized_volatility": benchmark_vol,
            "benchmark_sharpe_ratio": float((benchmark_annual-risk_free_rate)/benchmark_vol) if benchmark_vol else 0.0,
            "benchmark_sortino_ratio": float((benchmark_annual-risk_free_rate)/benchmark_downside_vol) if benchmark_downside_vol else 0.0,
            "benchmark_max_drawdown": benchmark_mdd,
            "benchmark_calmar_ratio": float(benchmark_annual/abs(benchmark_mdd)) if benchmark_mdd < 0 else 0.0,
            "excess_cumulative_return": float(nav.strategy_nav.iloc[-1]-nav.benchmark_nav.iloc[-1]),
            "excess_annualized_return": float(annual-benchmark_annual)}
    if allocations is not None:
        metrics.update(compute_exposure_metrics(allocations))
    return metrics
