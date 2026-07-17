from allstar.ai_agent.evaluation import live_faults


def test_fault_evaluation_is_na_without_scores():
    evaluation = live_faults.create_fault_na_evaluation("서버 장애", "http_503", 503)

    assert evaluation["overall_decision"] == "N/A"
    assert evaluation["total_score"] is None
    assert evaluation["http_status"] == 503
    for axis in live_faults.AXES:
        assert evaluation[axis]["score"] is None


def test_record_chat_fault_writes_conversation_two_na_rows_and_report(monkeypatch):
    conversations = []
    evaluations = []
    events = []
    statuses = []

    monkeypatch.setattr(live_faults, "log_conversation", lambda *args, **kwargs: conversations.append((args, kwargs)))
    monkeypatch.setattr(
        live_faults,
        "log_evaluation",
        lambda question, evaluation, model, request_id: evaluations.append((question, evaluation, model, request_id)),
    )
    monkeypatch.setattr(live_faults, "record_fault_event", lambda event, **details: events.append((event, details)))
    monkeypatch.setattr(live_faults, "generate_live_report", lambda: {"n_conversations": 1, "n_rows": 2})
    monkeypatch.setattr(live_faults, "mark_reporting", lambda request_id: statuses.append(("reporting", request_id)))
    monkeypatch.setattr(live_faults, "mark_completed", lambda request_id, summary: statuses.append(("completed", request_id)))

    result = live_faults.record_chat_fault(
        question="질문",
        case_id="TC-001",
        fault_type="server_down",
        error_message="서버 중단",
        latency_ms=123.4,
        http_status=None,
        error_detail="connection refused",
        request_id="fault-request",
    )

    assert result["report_ok"] is True
    assert conversations[0][1]["status"] == "error"
    assert conversations[0][1]["fault"]["type"] == "server_down"
    assert [row[2] for row in evaluations] == ["api", "rule"]
    assert all(row[1]["overall_decision"] == "N/A" for row in evaluations)
    assert all(row[1]["total_score"] is None for row in evaluations)
    assert events[0][0] == "chat_fault_recorded"
    assert statuses == [("reporting", "fault-request"), ("completed", "fault-request")]
