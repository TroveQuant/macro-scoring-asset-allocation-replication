from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from macro_allocation.config import (
    load_config,
    validate_structure,
)


ROOT = Path(__file__).resolve().parents[1]


def test_base_config_structure_is_safe() -> None:
    config = load_config(ROOT / "config/base.yml")
    assert validate_structure(config) == []


def test_credit_is_distinct_and_adjusted_price_based() -> None:
    config = load_config(ROOT / "config/base.yml")
    assert "CREDIT" in config["assets"]
    assert "SHORT_BOND" not in config["assets"]
    assert config["assets"]["CREDIT"]["symbol"] == "VCSH"
    assert "adjusted_close" in config["assets"]["CH_BOND"]["return_semantics"]


def test_prohibited_provider_is_rejected() -> None:
    config = load_config(ROOT / "config/base.yml")
    unsafe = deepcopy(config)
    unsafe["data"]["provider"] = "synthetic_fallback"
    assert any("prohibited" in error for error in validate_structure(unsafe))


def test_absolute_output_path_is_rejected() -> None:
    config = load_config(ROOT / "config/base.yml")
    unsafe = deepcopy(config)
    unsafe["outputs"]["directory"] = "C:" + "/private/outputs"
    assert any("repository-relative" in error for error in validate_structure(unsafe))


@pytest.mark.parametrize("marker", ["mock", "random", "demo", "synthetic"])
def test_artificial_provider_is_rejected(marker: str) -> None:
    config = load_config(ROOT / "config/base.yml")
    unsafe = deepcopy(config)
    unsafe["data"]["provider"] = f"{marker}_prices"
    assert validate_structure(unsafe)


def test_allow_short_defaults_to_original_behaviour_and_must_be_boolean() -> None:
    from macro_allocation.config import allow_short
    from macro_allocation.errors import ConfigurationError

    config = load_config(ROOT / "config/base.yml")
    assert config["project"]["allow_short"] is True
    legacy = deepcopy(config)
    del legacy["project"]["allow_short"]
    assert validate_structure(legacy) == []
    assert allow_short(legacy) is True
    long_only = deepcopy(config)
    long_only["project"]["allow_short"] = False
    assert validate_structure(long_only) == []
    assert allow_short(long_only) is False
    unsafe = deepcopy(config)
    unsafe["project"]["allow_short"] = "false"
    assert any("allow_short" in error for error in validate_structure(unsafe))
    with pytest.raises(ConfigurationError):
        allow_short(unsafe)
