from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE_DASHBOARD = ROOT / "ops" / "monitoring" / "voc_qa_dashboard.json"
PROVISIONED_DASHBOARD = (
    ROOT / "ops" / "monitoring" / "grafana" / "provisioning" / "dashboards" / "json" / "voc_qa_dashboard.json"
)
LIVE_SOURCE_DASHBOARD = ROOT / "ops" / "monitoring" / "voc_live_dashboard.json"
LIVE_PROVISIONED_DASHBOARD = (
    ROOT / "ops" / "monitoring" / "grafana" / "provisioning" / "dashboards" / "json" / "voc_live_dashboard.json"
)
K6_SOURCE_DASHBOARD = ROOT / "ops" / "monitoring" / "k6_dashboard.json"
K6_PROVISIONED_DASHBOARD = (
    ROOT / "ops" / "monitoring" / "grafana" / "provisioning" / "dashboards" / "json" / "k6_dashboard.json"
)
AI_SOURCE_DASHBOARD = ROOT / "ops" / "monitoring" / "grafana_dashboard.json"
AI_PROVISIONED_DASHBOARD = (
    ROOT / "ops" / "monitoring" / "grafana" / "provisioning" / "dashboards" / "json" / "grafana_dashboard.json"
)


def test_voc_qa_dashboard_uses_testcase_metrics_only():
    source = json.loads(SOURCE_DASHBOARD.read_text(encoding="utf-8"))
    provisioned = json.loads(PROVISIONED_DASHBOARD.read_text(encoding="utf-8"))

    assert source["uid"] == provisioned["uid"] == "voc-qa-abcd"
    assert source["version"] == provisioned["version"] == 5
    assert len(source["panels"]) == len(provisioned["panels"]) == 9

    expressions = [
        target["expr"]
        for panel in source["panels"]
        for target in panel.get("targets", [])
    ]
    assert expressions
    assert all("voc_chat_" not in expression and "voc_judge_total" not in expression for expression in expressions)
    assert all("voc_testcase_" in expression for expression in expressions)


def test_prometheus_uses_persistent_docker_volume():
    compose = (ROOT / "compose.yml").read_text(encoding="utf-8")

    assert "- prometheus_data:/prometheus" in compose
    assert "volumes:\n  prometheus_data:" in compose


def test_voc_live_dashboard_separates_activity_judge_status_and_verdict():
    source = json.loads(LIVE_SOURCE_DASHBOARD.read_text(encoding="utf-8"))
    provisioned = json.loads(LIVE_PROVISIONED_DASHBOARD.read_text(encoding="utf-8"))

    assert source == provisioned
    assert source["version"] == 4
    assert len(source["panels"]) == 9
    expressions = "\n".join(
        target["expr"] for panel in source["panels"] for target in panel.get("targets", [])
    )
    assert "voc_chat_last_activity_timestamp_seconds" in expressions
    assert "voc_chat_last_activity_timestamp_seconds > 0" in expressions
    assert "voc_judge_verdict_total" in expressions
    assert "voc_judge_score_sum" in expressions
    assert "voc_judge_duration_seconds_bucket" in expressions


def test_k6_dashboard_matches_prometheus_remote_write_metrics():
    source = json.loads(K6_SOURCE_DASHBOARD.read_text(encoding="utf-8"))
    provisioned = json.loads(K6_PROVISIONED_DASHBOARD.read_text(encoding="utf-8"))

    assert source == provisioned
    assert source["version"] == 3
    expressions = "\n".join(
        target["expr"] for panel in source["panels"] for target in panel.get("targets", [])
    )
    for metric in (
        "k6_vus",
        "k6_http_reqs_total",
        "k6_http_req_failed_rate",
        "k6_http_req_duration_p95",
        "k6_data_received_total",
        "k6_data_sent_total",
    ):
        assert metric in expressions
    assert all("testid" in target["expr"] or "testid" in target.get("legendFormat", "")
               for panel in source["panels"] for target in panel.get("targets", []))


def test_grafana_dashboards_use_expected_default_time_ranges_and_refresh():
    expected = (
        (AI_SOURCE_DASHBOARD, AI_PROVISIONED_DASHBOARD, "now-30m", 10),
        (K6_SOURCE_DASHBOARD, K6_PROVISIONED_DASHBOARD, "now-1h", 3),
        (LIVE_SOURCE_DASHBOARD, LIVE_PROVISIONED_DASHBOARD, "now-30m", 4),
        (SOURCE_DASHBOARD, PROVISIONED_DASHBOARD, "now-24h", 5),
    )

    for source_path, provisioned_path, expected_from, expected_version in expected:
        source = json.loads(source_path.read_text(encoding="utf-8"))
        provisioned = json.loads(provisioned_path.read_text(encoding="utf-8"))

        assert source == provisioned
        assert source["version"] == expected_version
        assert source["refresh"] == "5s"
        assert source["time"] == {"from": expected_from, "to": "now"}


def test_elapsed_time_panels_ignore_zero_timestamps_after_restart():
    expected_guards = (
        (AI_SOURCE_DASHBOARD, "chat_last_activity_timestamp_seconds > 0"),
        (LIVE_SOURCE_DASHBOARD, "voc_chat_last_activity_timestamp_seconds > 0"),
        (SOURCE_DASHBOARD, "voc_testcase_last_report_timestamp_seconds > 0"),
    )
    for dashboard_path, guard in expected_guards:
        dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))
        expressions = "\n".join(
            target["expr"] for panel in dashboard["panels"] for target in panel.get("targets", [])
        )
        assert guard in expressions


def test_ai_error_rate_title_lists_all_forced_chat_failures():
    dashboard = json.loads(AI_SOURCE_DASHBOARD.read_text(encoding="utf-8"))
    error_panel = next(panel for panel in dashboard["panels"] if panel["id"] == 1)
    assert error_panel["title"] == "1. 오류율 (%) (503·504·서버다운)"
    assert 'chat_requests_total{status="error"}' in error_panel["targets"][0]["expr"]
    assert "increase(" in error_panel["targets"][0]["expr"]
    assert "[$__range]" in error_panel["targets"][0]["expr"]
    assert "FAIL이 아니라 N/A" in error_panel["description"]
