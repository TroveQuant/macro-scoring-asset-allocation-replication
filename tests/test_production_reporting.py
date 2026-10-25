from macro_allocation.production_reporting import build_payload, exposure_notes, write_markdown, write_report


def test_report_discloses_short_treatment_and_benchmark_comparability(tmp_path):
    metrics = {"annualized_return": 0.01, "average_net_exposure": 0.0145,
               "average_gross_exposure": 0.4347, "average_cash_weight": 0.5653}
    run = {"status": "adapted", "allow_short": True}
    payload = build_payload(metrics, run, [], [])
    text = "\n".join(payload["limitations"])
    assert "allow_short=true" in text and "未计融券费用" in text
    assert "平均净风险敞口 1.5%" in text and "平均总敞口 43.5%" in text and "平均现金 56.5%" in text
    assert "100% 满仓" in text
    path = tmp_path / "report.md"
    write_markdown(payload, path)
    assert "average_cash_weight" in path.read_text(encoding="utf-8")
    assert any("仅做多" in note for note in exposure_notes({}, False))
    assert exposure_notes({}, None) == []


def test_html_report_shows_short_setting(tmp_path):
    figure = tmp_path / "figure.png"
    figure.write_bytes(b"not-a-production-image")
    for flag, label in ((True, "允许做空：是"), (False, "允许做空：否（仅做多）")):
        payload = build_payload({"average_net_exposure": 0.2, "average_gross_exposure": 0.2,
                                 "average_cash_weight": 0.8}, {"status": "adapted", "allow_short": flag}, [], [])
        write_report(payload, [figure], tmp_path / "report.json", tmp_path / "report.html")
        assert label in (tmp_path / "report.html").read_text(encoding="utf-8")
