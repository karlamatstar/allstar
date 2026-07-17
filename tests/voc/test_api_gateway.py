from fastapi.testclient import TestClient

from allstar.voc.api import main
from allstar.voc.evaluation import progress


client = TestClient(main.app)


def test_health_and_profiles_are_public():
    assert client.get("/health").json()["status"] == "ok"
    profiles = client.get("/profiles").json()
    assert [row["profile_id"] for row in profiles] == ["A", "B", "C", "D"]
    assert profiles[0]["generation"]["model"] == "gpt-5.6-luna"
    assert profiles[0]["judge"]["model"] == "claude-sonnet-5"


def test_chat_rejects_question_mark_only_encoding_damage():
    response = client.post("/chat", json={"question": "?? ?? ??? ?? ???? ???? ???", "profile_id": "A"})
    assert response.status_code == 422
    assert "질문 문자가 손상" in response.text


def test_chat_job_records_selected_profile_without_real_api(monkeypatch, tmp_path):
    generated = []

    class FakeRunner:
        async def run(self, question, profile, **_kwargs):
            return {
                "ok": True,
                "outcome": "completed",
                "summary": "배송 지연 불만 요약",
                "policy": "배송 지연 알림과 보상 기준을 개선합니다.",
                "trace": "Timing:Interpreter=0.1s; Timing:AgentPipeline=0.2s",
            }

    async def fake_judge(question, result, spec, elapsed_seconds=None):
        return {"total": 88, "verdict": "조건부 배포 가능, 개선 후 재검증", "model": spec.model}

    monkeypatch.setenv("VOC_ALLOW_MISSING_KEYS", "true")
    monkeypatch.setattr(progress, "PROGRESS_ROOT", tmp_path)
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
    assert status["judge"]["total"] == 88
    assert status["stage_states"][-1] == "done"
    assert generated == [True]


def test_chat_preserves_no_data_result_and_skips_judge(monkeypatch, tmp_path):
    generated = []
    judged = []

    class NoDataRunner:
        async def run(self, question, profile, **_kwargs):
            return {
                "ok": False,
                "outcome": "no_data",
                "intent_json": '{"filters":["가입 방법"],"fallback_filters":["가입"]}',
                "trace": "Retriever:first_count=0; Retriever:count=0",
                "summary": "",
                "policy": "",
            }

    async def should_not_judge(*_args, **_kwargs):
        judged.append(True)

    monkeypatch.setenv("VOC_ALLOW_MISSING_KEYS", "true")
    monkeypatch.setattr(progress, "PROGRESS_ROOT", tmp_path)
    monkeypatch.setattr(main, "_runner", NoDataRunner())
    monkeypatch.setattr(main.judge, "evaluate", should_not_judge)
    monkeypatch.setattr(main.log_store, "conversation", lambda record: None)
    monkeypatch.setattr(main.log_store, "judgment", lambda record: None)
    monkeypatch.setattr(main, "generate_live_report", lambda: generated.append(True))

    accepted = client.post("/chat", json={"question": "존재하지 않는 주제", "profile_id": "A"})
    status = client.get(f"/chat/{accepted.json()['request_id']}/status").json()

    assert status["status"] == "no_data"
    assert status["judge"] is None
    assert status["result"]["intent_json"]
    assert "관련 내용을 찾을 수 없습니다" in status["result"]["answer"]
    assert judged == []
    assert generated == [True]
