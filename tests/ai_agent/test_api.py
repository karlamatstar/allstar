"""외부 API 호출 없이 AI Agent HTTP 계약을 확인하는 테스트."""
from fastapi.testclient import TestClient

from allstar.ai_agent.api import main as main_module

client = TestClient(main_module.app)


def test_chat_returns_answer_for_valid_question(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "get_answer_from_api_agent",
        lambda question, simulate_api_disconnect=False: "이 교육과정은 총 320시간입니다.",
    )
    before = main_module.chat_requests_total.labels(status="success")._value.get()
    response = client.post(
        "/chat",
        json={"question": "이 교육과정은 총 몇 시간인가요?", "is_latency_test": True},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answer"].strip() != ""
    assert "320시간" in body["answer"]
    # 비교용 규칙 기반 답변도 함께 반환된다
    assert body["rule_answer"].strip() != ""
    assert "320시간" in body["rule_answer"]
    assert main_module.chat_requests_total.labels(status="success")._value.get() == before


def test_api_unavailable_is_counted_once_as_fallback(monkeypatch):
    def unavailable(*_args, **_kwargs):
        raise main_module.ApiAgentUnavailableError("연결 실패")

    monkeypatch.setattr(main_module, "get_answer_from_api_agent", unavailable)
    monkeypatch.setattr(main_module, "log_conversation", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main_module, "mark_pending", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main_module, "_score_both_and_check_jira_background", lambda *_args, **_kwargs: None)
    before = {
        status: main_module.chat_requests_total.labels(status=status)._value.get()
        for status in ("success", "error", "fallback")
    }

    response = client.post("/chat", json={"question": "연결 상태를 확인해 주세요"})

    assert response.status_code == 200
    assert main_module.chat_requests_total.labels(status="fallback")._value.get() == before["fallback"] + 1
    assert main_module.chat_requests_total.labels(status="success")._value.get() == before["success"]
    assert main_module.chat_requests_total.labels(status="error")._value.get() == before["error"]


def test_chat_rejects_empty_question():
    response = client.post("/chat", json={"question": ""})
    assert response.status_code == 422


def test_background_scoring_refreshes_report_after_both_logs(monkeypatch):
    events = []
    evaluation = {
        "accuracy": {"score": 5, "reason": "test"},
        "groundedness": {"score": 5, "reason": "test"},
        "helpfulness": {"score": 5, "reason": "test"},
        "safety": {"score": 5, "reason": "test"},
        "understandability": {"score": 5, "reason": "test"},
        "total_score": 25,
        "overall_decision": "PASS",
        "summary": "정상",
    }

    monkeypatch.setattr(main_module, "get_evaluation_from_openai", lambda **_kwargs: evaluation)
    monkeypatch.setattr(
        main_module,
        "log_evaluation",
        lambda _question, _evaluation, model, request_id: events.append(("log", model, request_id)),
    )
    monkeypatch.setattr(
        main_module,
        "_refresh_live_report_background",
        lambda: (events.append(("refresh",)) or {"ok": True, "summary": {"n_rows": 2}}),
    )
    monkeypatch.setattr(main_module, "mark_evaluating", lambda request_id, completed, message: events.append(("status", "evaluating", completed)))
    monkeypatch.setattr(main_module, "mark_reporting", lambda request_id: events.append(("status", "reporting")))
    monkeypatch.setattr(main_module, "mark_completed", lambda request_id, summary: events.append(("status", "completed")))
    monkeypatch.setattr(main_module, "mark_failed", lambda request_id, error: events.append(("status", "failed")))

    def duration_count(model):
        main_module.judge_evaluation_duration_seconds.labels(model=model)
        return next(
            sample.value
            for metric in main_module.judge_evaluation_duration_seconds.collect()
            for sample in metric.samples
            if sample.name == "judge_evaluation_duration_seconds_count"
            and sample.labels.get("model") == model
        )

    duration_before = {model: duration_count(model) for model in ("api", "rule")}
    main_module._score_both_and_check_jira_background(
        "질문", "API 답변", "규칙 답변", "request-1"
    )

    assert ("log", "api", "request-1") in events
    assert ("log", "rule", "request-1") in events
    assert events.index(("log", "api", "request-1")) < events.index(("log", "rule", "request-1"))
    assert ("refresh",) in events
    assert events[-1] == ("status", "completed")
    for model in ("api", "rule"):
        assert duration_count(model) == duration_before[model] + 1
