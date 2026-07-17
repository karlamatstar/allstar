"""AI 테스트케이스 배치 실패 시 최근 정상 보고서 보존 규칙을 검증한다."""

from pathlib import Path

import pytest

from allstar.ai_agent.evaluation import quality_pipeline


def test_failed_pipeline_preserves_latest_successful_formal_report(tmp_path, monkeypatch):
    reports_dir = tmp_path / "reports"
    log_dir = tmp_path / "logs"
    manifest_dir = tmp_path / "manifests"
    reports_dir.mkdir()
    latest_report = reports_dir / "final_quality_report.md"
    latest_report.write_text("# 최근 정상 보고서\n", encoding="utf-8")

    monkeypatch.setattr(quality_pipeline, "REPORTS_DIR", reports_dir)
    monkeypatch.setattr(quality_pipeline, "TESTCASE_LOG_DIR", log_dir)
    monkeypatch.setattr(quality_pipeline, "MANIFEST_DIR", manifest_dir)
    monkeypatch.setattr(quality_pipeline, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(quality_pipeline, "validate_config", lambda: None)

    def fail_case(_case):
        raise RuntimeError("의도한 실행 실패")

    monkeypatch.setattr(quality_pipeline, "evaluate_case", fail_case)
    test_case = {"case_id": "TC-FAIL"}

    with pytest.raises(RuntimeError, match="의도한 실행 실패"):
        quality_pipeline.run_pipeline([test_case], "failed_run")

    assert latest_report.read_text(encoding="utf-8") == "# 최근 정상 보고서\n"
    assert not log_dir.exists()
    assert not manifest_dir.exists()
