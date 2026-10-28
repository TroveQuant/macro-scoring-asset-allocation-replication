from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_workflow_is_manual_only_and_runs_complete_opt_in_backtest() -> None:
    text = (ROOT / ".github/workflows/paper-replication.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "run_replication:" in text
    assert "schedule:" not in text
    assert "pull_request:" not in text
    assert "repository_dispatch:" not in text
    assert "git add --all" not in text
    assert "configure-pages" not in text
    assert "deploy-pages" not in text
    assert "smtp" not in text.lower()
    assert "git add -- outputs/report.json" in text
    assert "continue-on-error" not in text
    assert "tools/clean_outputs.py" in text
    assert "tools/validate_backtest.py --require-current-run" in text
    assert "outputs/performance_metrics.csv" in text
    assert "contents: write" in text
    assert "replicate:" in text
    assert "if: ${{ inputs.run_replication }}" in text
    assert "needs: validate" in text


def test_tests_workflow_runs_offline_suite_on_pull_requests_only() -> None:
    import yaml

    text = (ROOT / ".github/workflows/tests.yml").read_text(encoding="utf-8")
    workflow = yaml.safe_load(text)
    triggers = workflow.get("on", workflow.get(True))  # PyYAML parses a bare `on` key as True
    assert set(triggers) == {"pull_request", "workflow_dispatch"}
    assert workflow["permissions"] == {"contents": "read"}
    steps = workflow["jobs"]["offline-tests"]["steps"]
    commands = "\n".join(step.get("run", "") for step in steps)
    assert "python -m pytest -q" in commands
    assert "run_replication.py --config config/base.yml --validate-config" in commands
    assert "secrets." not in text
    assert "git push" not in text and "git commit" not in text and "git add" not in text
    assert "contents: write" not in text
