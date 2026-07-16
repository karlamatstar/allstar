"""통합 프로젝트의 로그와 리포트 저장 경로가 기준 구조를 따르는지 확인한다."""

from pathlib import Path

from ai_quality import defect_logger, live_report_generator, quality_pipeline
from app import config
from voc.quality_diagnosis import cross_validation, llm_judge, qa_test_utils


ROOT = Path(__file__).resolve().parent.parent


def test_ai_agent_paths_are_separated():
    assert quality_pipeline.TEST_CASE_FILE == ROOT / "ai_quality" / "test_cases.json"
    assert quality_pipeline.REPORTS_DIR == ROOT / "quality" / "reports" / "ai_agent" / "batch"
    assert quality_pipeline.TESTCASE_LOG_DIR == ROOT / "logs" / "ai_agent" / "testcase"
    assert live_report_generator.REPORTS_DIR == ROOT / "quality" / "reports" / "ai_agent" / "live"
    assert config.CONVERSATION_LOG_DIR == ROOT / "logs" / "ai_agent" / "live" / "conversations"
    assert config.JUDGMENT_LOG_DIR == ROOT / "logs" / "ai_agent" / "live" / "judgments"


def test_voc_cross_validation_paths_are_separated():
    assert qa_test_utils.REPORTS_DIR == ROOT / "quality" / "reports" / "voc" / "testcase"
    assert cross_validation.REPORT_ROOT == ROOT / "quality" / "reports" / "voc" / "cross_validation"
    assert cross_validation.LOG_ROOT == ROOT / "logs" / "voc" / "cross_validation"


def test_voc_judge_accepts_separate_log_directory(tmp_path, monkeypatch):
    report_dir = tmp_path / "reports"
    log_dir = tmp_path / "logs"
    monkeypatch.setenv("VOC_JUDGE_LOG_DIR", str(log_dir))

    try:
        llm_judge.configure_output_dir(str(report_dir))
        assert llm_judge.ACTIVE_REPORTS_DIR == report_dir.resolve()
        assert llm_judge.JUDGE_LOG_DIR == log_dir.resolve()
    finally:
        monkeypatch.delenv("VOC_JUDGE_LOG_DIR")
        llm_judge.configure_output_dir(None)


def test_defect_logger_keeps_code_outside_report_directory(tmp_path, monkeypatch):
    report = tmp_path / "quality" / "reports" / "defects" / "chatbot" / "defect_report.md"
    monkeypatch.setattr(defect_logger, "DEFECT_REPORT", report)

    output = defect_logger.log_defect_to_markdown(
        request_id="req-test",
        timestamp="2026-07-16 22:00:00",
        question="테스트 질문",
        evaluation={"overall_decision": "REVIEW", "total_score": 18, "summary": "확인 필요"},
        model_name="테스트 모델",
        judge_name="테스트 평가 모델",
    )

    assert output == report
    assert "req-test" in report.read_text(encoding="utf-8")
