from allstar.ai_agent.evaluation import live_report_status


def test_live_report_status_lifecycle(tmp_path, monkeypatch):
    status_path = tmp_path / "report_status.json"
    monkeypatch.setattr(live_report_status, "STATUS_PATH", status_path)

    live_report_status.mark_pending("req-1")
    pending = live_report_status.read_status()
    assert pending["active_count"] == 1
    assert pending["latest"]["state"] == "PENDING"

    live_report_status.mark_evaluating("req-1", 1, "규칙 기반 평가 중")
    live_report_status.mark_reporting("req-1")
    reporting = live_report_status.read_status()
    assert reporting["latest"]["state"] == "REPORTING"

    live_report_status.mark_completed("req-1", {"n_rows": 2})
    completed = live_report_status.read_status()
    assert completed["active_count"] == 0
    assert completed["latest"]["state"] == "COMPLETED"
    assert completed["latest"]["report_summary"]["n_rows"] == 2


def test_live_report_status_keeps_multiple_jobs(tmp_path, monkeypatch):
    monkeypatch.setattr(live_report_status, "STATUS_PATH", tmp_path / "report_status.json")

    live_report_status.mark_pending("req-1")
    live_report_status.mark_pending("req-2")
    live_report_status.mark_failed("req-1", "테스트 오류")

    status = live_report_status.read_status()
    assert status["active_count"] == 1
    assert status["jobs"]["req-1"]["state"] == "FAILED"
    assert status["jobs"]["req-2"]["state"] == "PENDING"
