"""외부 API 호출 없이 AI Agent HTTP 계약을 확인하는 테스트."""
from fastapi.testclient import TestClient

from app import main as main_module

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
