from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE_DASHBOARD = ROOT / "ops" / "monitoring" / "voc_qa_dashboard.json"
PROVISIONED_DASHBOARD = (
    ROOT / "ops" / "monitoring" / "grafana" / "provisioning" / "dashboards" / "json" / "voc_qa_dashboard.json"
)


def test_voc_qa_dashboard_uses_testcase_metrics_only():
    source = json.loads(SOURCE_DASHBOARD.read_text(encoding="utf-8"))
    provisioned = json.loads(PROVISIONED_DASHBOARD.read_text(encoding="utf-8"))

    assert source["uid"] == provisioned["uid"] == "voc-qa-abcd"
    assert source["version"] == provisioned["version"] == 3
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
