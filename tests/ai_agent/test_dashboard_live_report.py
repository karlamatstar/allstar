import json

import pandas as pd

from allstar.ui.dashboard import views


def test_safe_json_preserves_dict_and_parses_json_text():
    value = {"total_score": 81}
    assert views._safe_json(value) is value
    assert views._safe_json('{"total_score": 92}') == {"total_score": 92}
    assert views._safe_json("not-json") == "not-json"


def test_latest_judgment_view_hides_id_and_uses_latest_evaluation():
    judgments = pd.DataFrame(
        [
            {
                "timestamp": "2026-07-17T01:00:00+00:00",
                "request_id": "same-request",
                "question": "질문",
                "model": "api",
                "evaluation": json.dumps({"total_score": 55, "overall_decision": "FAIL"}),
            },
            {
                "timestamp": "2026-07-17T01:01:00+00:00",
                "request_id": "same-request",
                "question": "질문",
                "model": "api",
                "evaluation": json.dumps({"total_score": 90, "overall_decision": "PASS"}),
            },
        ]
    )

    result = views._latest_judgment_view(judgments)

    assert list(result.columns) == ["시간", "질문", "모델", "총점", "판정", "평가 내용(Evaluation)"]
    assert len(result) == 1
    assert result.iloc[0]["모델"] == "서버 연결 방식(API)"
    assert result.iloc[0]["총점"] == 90
    assert result.iloc[0]["판정"] == "PASS"


def test_conversation_log_view_shows_background_evaluation_state():
    conversations = pd.DataFrame(
        [
            {"request_id": "done", "timestamp": "2026-07-17T01:00:00+00:00", "question": "완료 질문"},
            {"request_id": "partial", "timestamp": "2026-07-17T01:01:00+00:00", "question": "진행 질문"},
            {"request_id": "pending", "timestamp": "2026-07-17T01:02:00+00:00", "question": "대기 질문"},
        ]
    )
    judgments = pd.DataFrame(
        [
            {"request_id": "done", "model": "api"},
            {"request_id": "done", "model": "rule"},
            {"request_id": "partial", "model": "api"},
        ]
    )

    result = views._conversation_log_view(conversations, judgments)

    assert "request_id" not in result.columns
    assert result["채점 상태"].tolist() == ["완료", "진행 중", "채점 대기"]
