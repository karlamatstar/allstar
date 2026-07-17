"""VOC 실시간 품질 화면과 검색 0건 표시의 비API 계약을 검증한다."""

from pathlib import Path

import pandas as pd

from allstar.ui.dashboard import views
from allstar.voc.agents.retriever import _meaningful_terms
from allstar.voc.runtime.grpc_runtime import _extract_fallback_tokens


ROOT = Path(__file__).resolve().parents[2]
VIEWS = (ROOT / "src" / "allstar" / "ui" / "dashboard" / "views.py").read_text(encoding="utf-8")


def test_insurance_signup_question_has_safe_fallback_search_term():
    tokens = _extract_fallback_tokens("보험 가입 방법에 대한 문제점을 정리해봐 주세요")
    assert "가입" in tokens
    assert _meaningful_terms(tokens) == ["가입"]


def test_no_data_stage_marks_retriever_instead_of_interpreter():
    states = views._status_stage_states({"status": "no_data"})
    assert states[0] == "done"
    assert states[1] == "no_data"
    assert states[2:] == ["skipped"] * 5


def test_voc_live_frame_excludes_legacy_twenty_point_score(monkeypatch):
    criteria = {name: maximum for name, maximum in views.VOC_SCORE_CRITERIA}
    rows = [
        {
            "request_id": "new",
            "timestamp": "2026-07-17T10:00:00+09:00",
            "question": "가입 문의",
            "profile_id": "A",
            "profile": {"generation": {}, "judge": {}},
            "status": "completed",
            "result": {"answer": "개선안"},
            "judge": {
                "rubric_version": views.VOC_RUBRIC_VERSION,
                "scores": criteria,
                "reasons": {name: "근거" for name in criteria},
                "total": 100,
                "verdict": "배포 가능",
            },
        },
        {
            "request_id": "legacy",
            "timestamp": "2026-07-17T09:00:00+09:00",
            "question": "이전 질문",
            "profile_id": "B",
            "profile": {"generation": {}, "judge": {}},
            "status": "completed",
            "result": {"answer": "이전 답변"},
            "judge": {"total": 20, "verdict": "PASS"},
        },
    ]
    monkeypatch.setattr(views, "_read_voc_live_rows", lambda: rows)

    frame = views._voc_live_frame()

    assert frame.iloc[0]["total"] == 100
    assert frame.iloc[0]["rubric"] == "9항목·100점"
    assert frame.iloc[1]["rubric"] == "이전 4항목·20점"
    assert frame.iloc[1]["verdict"] == "N/A"
    assert pd.isna(frame.iloc[1]["total"])


def test_voc_chat_has_five_quality_tabs_and_normalized_radar():
    for label in ("챗봇과 대화", "대화 로그", "품질 현황", "유형별 비교", "대화별 채점 상세"):
        assert label in VIEWS
    assert "A~D 프로필 조합 비교" in VIEWS
    assert "range\": [0, 100]" in VIEWS
    assert "데이터 없음" in VIEWS
