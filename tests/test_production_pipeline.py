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


def load_validator():
    import importlib.util

    spec = importlib.util.spec_from_file_location("validate_backtest_tool", ROOT / "tools/validate_backtest.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_fixture_pipeline(tmp_path, monkeypatch, config):
    monkeypatch.setattr(production_pipeline, "download_market_data", lambda cfg, root: fixture_market(cfg))
    production_pipeline.run_pipeline(config, tmp_path, Path("config/base.yml"))
    return tmp_path / "outputs"


def write_config(path, config, allow_short):
    import yaml

    edited = deepcopy(config)
    edited["project"]["allow_short"] = allow_short
    path.write_text(yaml.safe_dump(edited, allow_unicode=True), encoding="utf-8")
    return path


def test_default_config_is_long_only_and_passes_strict_validation(tmp_path, monkeypatch):
    config = load_config(ROOT / "config/base.yml")
    out = run_fixture_pipeline(tmp_path, monkeypatch, deepcopy(config))
    weights = pd.read_csv(out / "allocation_weights.csv", parse_dates=["date"]).set_index("date")
    assert (weights.drop(columns="CASH") >= 0).all().all()
    metrics = pd.read_csv(out / "performance_metrics.csv").iloc[0]
    assert metrics.average_short_exposure == 0
    assert np.isclose(metrics.average_net_exposure, metrics.average_gross_exposure, atol=1e-12)
    payload = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert payload["run"]["allow_short"] is False
    validator = load_validator()
    cfg_path = write_config(tmp_path / "base.yml", config, False)
    assert validator.main(["--outputs", str(out), "--config", str(cfg_path), "--require-current-run"]) == 0


def test_validator_follows_the_run_setting_and_strict_mode(tmp_path, monkeypatch, capsys):
    config = load_config(ROOT / "config/base.yml")
    comparison = deepcopy(config)
    comparison["project"]["allow_short"] = True
    out = run_fixture_pipeline(tmp_path, monkeypatch, comparison)
    validator = load_validator()
    long_only_cfg = write_config(tmp_path / "long_only.yml", config, False)
    short_cfg = write_config(tmp_path / "short.yml", config, True)
    args = ["--outputs", str(out)]
    assert validator.main(args + ["--config", str(short_cfg), "--require-current-run"]) == 0
    # Config and run disagree: strict fails, otherwise the run's own setting is checked.
    assert validator.main(args + ["--config", str(long_only_cfg), "--require-current-run"]) == 2
    assert validator.main(args + ["--config", str(long_only_cfg)]) == 0
    assert "allow_short=true" in capsys.readouterr().err
    report = out / "report.json"
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["run"]["allow_short"] = False
    report.write_text(json.dumps(payload), encoding="utf-8")
    assert validator.main(args + ["--config", str(long_only_cfg)]) == 2
    assert "long-only run produced short weights" in capsys.readouterr().err
    # Outputs that predate the switch: warning only, unless the run must be current.
    del payload["run"]["allow_short"]
    report.write_text(json.dumps(payload), encoding="utf-8")
    assert validator.main(args + ["--config", str(long_only_cfg)]) == 0
    assert validator.main(args + ["--config", str(long_only_cfg), "--require-current-run"]) == 2
    payload["run"]["allow_short"] = True
    report.write_text(json.dumps(payload), encoding="utf-8")
    metrics = pd.read_csv(out / "performance_metrics.csv").drop(columns=list(EXPOSURE_METRICS))
    metrics.to_csv(out / "performance_metrics.csv", index=False)
    assert validator.main(args + ["--config", str(short_cfg)]) == 0
    assert validator.main(args + ["--config", str(short_cfg), "--require-current-run"]) == 2
    assert "no exposure metrics" in capsys.readouterr().err


def test_validator_accepts_committed_outputs_without_strict_mode():
    assert load_validator().main([]) == 0


def test_validator_default_matches_config_default():
    from macro_allocation.config import DEFAULT_ALLOW_SHORT

    assert DEFAULT_ALLOW_SHORT is False
    assert load_validator().DEFAULT_ALLOW_SHORT is DEFAULT_ALLOW_SHORT
