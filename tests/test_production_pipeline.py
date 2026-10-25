"""Offline wiring test for the production pipeline.

The downloader is replaced by a deterministic, test-only price fixture so the
test never touches the network. These prices are not market data and are never
written outside pytest's temporary directory.
"""
import json
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from macro_allocation import production_pipeline
from macro_allocation.config import load_config
from macro_allocation.production_metrics import EXPOSURE_METRICS
from macro_allocation.yahoo_provider import DownloadedMarketData

ROOT = Path(__file__).resolve().parents[1]


def fixture_market(config):
    symbols = [s["symbol"] for s in config["assets"].values()] + [config["cash"]["symbol"]]
    symbols += [s["symbol"] for s in config["macro_proxies"].values()]
    index = pd.bdate_range(config["data"]["download_start"], config["data"]["as_of_date"])
    rng = np.random.default_rng(20261025)
    daily = {s: pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(index)))), index=index, name=s)
             for s in symbols}
    return DownloadedMarketData(daily=daily, manifest=[{"symbol": s, "source": "pytest fixture"} for s in symbols],
                                duplicates=pd.DataFrame(columns=["symbol", "date"]))


@pytest.mark.parametrize("allow_short", [True, False])
def test_pipeline_writes_exposure_metrics_and_honours_allow_short(tmp_path, monkeypatch, allow_short):
    config = deepcopy(load_config(ROOT / "config/base.yml"))
    config["project"]["allow_short"] = allow_short
    monkeypatch.setattr(production_pipeline, "download_market_data", lambda cfg, root: fixture_market(cfg))
    production_pipeline.run_pipeline(config, tmp_path, Path("config/base.yml"))
    out = tmp_path / "outputs"
    metrics = pd.read_csv(out / "performance_metrics.csv").iloc[0]
    weights = pd.read_csv(out / "allocation_weights.csv", parse_dates=["date"]).set_index("date")
    risky = weights.drop(columns="CASH")
    for key in EXPOSURE_METRICS:
        assert key in metrics.index
    assert np.isclose(metrics.average_net_exposure, risky.sum(axis=1).mean(), atol=1e-12)
    assert np.isclose(metrics.average_cash_weight, weights.CASH.mean(), atol=1e-12)
    assert bool((risky < 0).any().any()) is allow_short
    payload = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert payload["run"]["allow_short"] is allow_short
    assert "average_cash_weight" in payload["metrics"]
    assert any("100% 满仓" in note for note in payload["limitations"])
