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
    monkeypatch.setattr(main_module, "_refresh_live_report_background", lambda: events.append(("refresh",)))

    main_module._score_both_and_check_jira_background(
        "질문", "API 답변", "규칙 답변", "request-1"
    )

    assert events[:2] == [("log", "api", "request-1"), ("log", "rule", "request-1")]
    assert events[-1] == ("refresh",)
