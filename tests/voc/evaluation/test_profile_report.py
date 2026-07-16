"""VOC 프로필 정식 보고서를 실행 로그만으로 재생성하는지 검증한다."""

from __future__ import annotations

import json

from allstar.shared.model_profiles import get_profile
from allstar.voc.evaluation import llm_judge
from allstar.voc.evaluation.profile_report import rebuild_profile_report_from_log


def test_rebuild_profile_report_combines_two_cases_from_one_log(tmp_path, monkeypatch):
    rubric = {
        "criteria": [{"name": "정확성", "max_score": 100}],
        "immediate_hold_conditions": [],
        "verdict_thresholds": [
            {"min_score": 90, "verdict": "배포 가능"},
            {"min_score": 0, "verdict": "배포 보류"},
        ],
    }
    rows = [
        {
            "case_id": "TC-01", "question": "첫 질문", "mode": "live",
            "judge_model": "anthropic:test", "정확성": 82, "total": 82,
            "verdict": "조건부 배포", "immediate_hold": False,
            "api_attempts": "anthropic:성공", "pipeline_seconds": 10,
            "judge_seconds": 2, "total_seconds": 12, "rationale": "첫 근거",
            "analysis": "첫 실제 답변",
        },
        {
            "case_id": "TC-02", "question": "둘째 질문", "mode": "live",
            "judge_model": "anthropic:test", "정확성": 78, "total": 78,
            "verdict": "개선 필요", "immediate_hold": False,
            "api_attempts": "anthropic:성공", "pipeline_seconds": 11,
            "judge_seconds": 3, "total_seconds": 14, "rationale": "둘째 근거",
            "analysis": "둘째 실제 답변",
        },
    ]
    log_path = tmp_path / "logs" / "llm_judge_run.json"
    log_path.parent.mkdir()
    log_path.write_text(json.dumps({
        "run_id": "run-two-cases",
        "status": "completed",
        "case_results": rows,
    }, ensure_ascii=False), encoding="utf-8")
    report_dir = tmp_path / "reports"
    monkeypatch.setattr(llm_judge, "load_json", lambda _name: rubric)

    result = rebuild_profile_report_from_log(log_path, report_dir, get_profile("A"))

    report = (report_dir / "quality_score_report.md").read_text(encoding="utf-8")
    assert result["case_ids"] == ["TC-01", "TC-02"]
    assert "대상 테스트케이스: TC-01, TC-02" in report
    assert "첫 실제 답변" in report
    assert "둘째 실제 답변" in report
    assert (report_dir / "llm_judge_result.csv").exists()
    assert (report_dir / "llm_judge_result.json").exists()
    assert len(list((report_dir / "assets").glob("*.png"))) == 3
