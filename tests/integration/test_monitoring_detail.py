from __future__ import annotations

import json
from pathlib import Path

from allstar.ui.dashboard import views


ROOT = Path(__file__).resolve().parents[2]
LIVE = ROOT / "ops" / "monitoring" / "voc_live_dashboard.json"
LIVE_PROVISIONED = ROOT / "ops" / "monitoring" / "grafana" / "provisioning" / "dashboards" / "json" / "voc_live_dashboard.json"
QA = ROOT / "ops" / "monitoring" / "voc_qa_dashboard.json"
QA_PROVISIONED = ROOT / "ops" / "monitoring" / "grafana" / "provisioning" / "dashboards" / "json" / "voc_qa_dashboard.json"
VIEWS_SOURCE = (ROOT / "src" / "allstar" / "ui" / "dashboard" / "views.py").read_text(encoding="utf-8")


def test_voc_grafana_dashboards_include_stage_retrieval_and_failure_panels():
    for source, provisioned, mode in (
        (LIVE, LIVE_PROVISIONED, "live"),
        (QA, QA_PROVISIONED, "batch"),
    ):
        assert source.read_bytes() == provisioned.read_bytes()
        dashboard = json.loads(source.read_text(encoding="utf-8"))
        titles = {panel["title"] for panel in dashboard["panels"]}
        expressions = "\n".join(
            target.get("expr", "")
            for panel in dashboard["panels"]
            for target in panel.get("targets", [])
        )
        assert len(dashboard["panels"]) == 15
        assert any("7단계 누적 평균 처리시간" in title for title in titles)
        assert any("7단계 누적 p95 처리시간" in title for title in titles)
        assert any("오류율" in title for title in titles)
        assert any("검색 결과 분포" in title for title in titles)
        assert any("검색 0건" in title for title in titles)
        assert any("실패 원인" in title for title in titles)
        assert "voc_stage_duration_seconds" in expressions
        assert "voc_stage_runs_total" in expressions
        assert "voc_retrieval_results_total" in expressions
        assert "voc_pipeline_failures_total" in expressions
        assert f'mode="{mode}"' in expressions


def test_monitoring_page_has_periodic_core_service_summary():
    assert '@st.fragment(run_every="5s")\ndef _render_monitoring_status_summary' in VIEWS_SOURCE
    assert "핵심 서버 운영 상태" in VIEWS_SOURCE
    assert "Health·TCP 연결을 5초마다 확인" in VIEWS_SOURCE
    assert "AI 에이전트 API" in VIEWS_SOURCE
    assert "VOC API" in VIEWS_SOURCE
    assert "Prometheus" in VIEWS_SOURCE
    assert "Grafana" in VIEWS_SOURCE
    assert "_render_monitoring_status_summary()" in VIEWS_SOURCE


def test_monitoring_status_checks_ten_services_without_ai_calls(monkeypatch):
    class Response:
        status_code = 200

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, _url):
            return Response()

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(views.httpx, "Client", Client)
    monkeypatch.setattr(views.socket, "create_connection", lambda *args, **kwargs: Connection())
    views._monitoring_service_status.clear()

    result = views._monitoring_service_status(
        "http://portfolio",
        "http://voc",
        "http://prometheus",
        "http://grafana",
    )

    assert result["healthy"] == 10
    assert result["total"] == 10
    assert all(row["ok"] for row in result["rows"])

