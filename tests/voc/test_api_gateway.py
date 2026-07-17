from fastapi.testclient import TestClient

from allstar.voc.api import main


client = TestClient(main.app)


def test_health_and_profiles_are_public():
    assert client.get("/health").json()["status"] == "ok"
    profiles = client.get("/profiles").json()
    assert [row["profile_id"] for row in profiles] == ["A", "B", "C", "D"]
    assert profiles[0]["generation"]["model"] == "gpt-5.6-luna"
    assert profiles[0]["judge"]["model"] == "claude-sonnet-5"


def test_chat_job_records_selected_profile_without_real_api(monkeypatch):
    generated = []

    class FakeRunner:
        async def run(self, question, profile):
            return {
                "ok": True,
                "summary": "배송 지연 불만 요약",
                "policy": "배송 지연 알림과 보상 기준을 개선합니다.",
                "trace": "Timing:Interpreter=0.1s; Timing:AgentPipeline=0.2s",
            }

    async def fake_judge(question, answer, spec):
        return {"total": 18, "verdict": "PASS", "model": spec.model}

    monkeypatch.setenv("VOC_ALLOW_MISSING_KEYS", "true")
    monkeypatch.setattr(main, "_runner", FakeRunner())
    monkeypatch.setattr(main.judge, "evaluate", fake_judge)
    monkeypatch.setattr(main.log_store, "conversation", lambda record: None)
    monkeypatch.setattr(main.log_store, "judgment", lambda record: None)
    monkeypatch.setattr(main, "generate_live_report", lambda: generated.append(True))

    accepted = client.post("/chat", json={"question": "배송 지연 불만을 분석해줘", "profile_id": "B"})
    assert accepted.status_code == 202
    request_id = accepted.json()["request_id"]
    status = client.get(f"/chat/{request_id}/status").json()
    assert status["status"] == "completed"
    assert status["profile_id"] == "B"
    assert status["profile"]["generation"]["provider"] == "anthropic"
    assert status["profile"]["judge"]["provider"] == "openai"
    assert status["judge"]["verdict"] == "PASS"
    assert generated == [True]
