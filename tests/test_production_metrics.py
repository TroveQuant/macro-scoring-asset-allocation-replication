import numpy as np
import pandas as pd
import pytest
from macro_allocation.errors import DataValidationError
from macro_allocation.production_backtest import run_backtest
from macro_allocation.production_metrics import EXPOSURE_METRICS, compute_exposure_metrics, compute_metrics


def allocations():
    idx = pd.date_range("2020-01-31", periods=2, freq="ME")
    return pd.DataFrame({"A": [0.3, -0.2], "B": [-0.1, 0.0], "CASH": [0.6, 0.8]}, index=idx)


def test_exposure_metrics_separate_net_gross_short_and_cash():
    metrics = compute_exposure_metrics(allocations())
    assert set(metrics) == set(EXPOSURE_METRICS)
    assert np.isclose(metrics["average_net_exposure"], (0.2 + -0.2) / 2)
    assert np.isclose(metrics["average_gross_exposure"], (0.4 + 0.2) / 2)
    assert np.isclose(metrics["average_long_exposure"], 0.15)
    assert np.isclose(metrics["average_short_exposure"], 0.15)
    assert np.isclose(metrics["average_cash_weight"], 0.7)


def test_exposure_metrics_reject_missing_cash_or_nan():
    with pytest.raises(DataValidationError, match="CASH"):
        compute_exposure_metrics(allocations().drop(columns="CASH"))
    bad = allocations(); bad.iloc[0, 0] = np.nan
    with pytest.raises(DataValidationError, match="finite"):
        compute_exposure_metrics(bad)


def test_backtest_metrics_include_exposure_and_require_aligned_dates():
    idx = pd.date_range("2020-01-31", periods=4, freq="ME")
    pos = pd.DataFrame({"CREDIT": [1, -1, 1, 1]}, index=idx)
    ret = pd.DataFrame({"CREDIT": [.01, .02, .03, .04]}, index=idx)
    cash = pd.Series([.001] * 4, index=idx)
    result = run_backtest(pos, ret, cash, {"CREDIT": 0.5}, 10, "2020-02-29", allow_short=True)
    metrics = compute_metrics(result.monthly, "2020-04-30", allocations=result.allocations)
    assert np.isclose(metrics["average_net_exposure"], 0.5 / 3)
    assert np.isclose(metrics["average_gross_exposure"], 0.5)
    assert np.isclose(metrics["average_short_exposure"], 0.5 / 3)
    assert np.isclose(metrics["average_cash_weight"], 0.5)
    long_only = run_backtest(pos, ret, cash, {"CREDIT": 0.5}, 10, "2020-02-29")
    lo_metrics = compute_metrics(long_only.monthly, "2020-04-30", allocations=long_only.allocations)
    assert np.isclose(lo_metrics["average_net_exposure"], 1 / 3)
    assert np.isclose(lo_metrics["average_gross_exposure"], 1 / 3)
    assert lo_metrics["average_short_exposure"] == 0
    assert np.isclose(lo_metrics["average_cash_weight"], 2 / 3)
    assert "average_net_exposure" not in compute_metrics(result.monthly, "2020-04-30")
    with pytest.raises(DataValidationError, match="aligned"):
        compute_metrics(result.monthly, "2020-04-30", allocations=result.allocations.iloc[1:])
