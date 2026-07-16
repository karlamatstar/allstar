"""통합 프로젝트의 로그와 리포트 저장 경로가 기준 구조를 따르는지 확인한다."""

from pathlib import Path

from allstar.ai_agent.api import config
from allstar.ai_agent.evaluation import defect_logger, live_report_generator, quality_pipeline
from allstar.voc.evaluation import cross_validation, llm_judge
from allstar.voc.evaluation import runtime_support as qa_test_utils


ROOT = Path(__file__).resolve().parents[2]


def test_product_code_uses_src_layout_and_old_roots_are_removed():
    assert (ROOT / "src" / "allstar" / "ai_agent" / "api").is_dir()
    assert (ROOT / "src" / "allstar" / "voc" / "api").is_dir()
    assert (ROOT / "src" / "allstar" / "ui" / "dashboard").is_dir()
    for old_root in ("app", "ai_quality", "voc_api", "voc", "quality", "logs"):
        assert not (ROOT / old_root).exists()


def test_run_launchers_point_to_tool_implementations():
    servers = (ROOT / "RUN" / "start_servers.bat").read_text(encoding="utf-8")
    qa = (ROOT / "RUN" / "start_qa.bat").read_text(encoding="utf-8")
    assert "tools\\server_control\\main.py" in servers
    assert "tools\\qa_control\\main.py" in qa


def test_compose_uses_new_dockerfiles_and_package_entrypoints():
    compose = (ROOT / "compose.yml").read_text(encoding="utf-8")
    ai_dockerfile = (ROOT / "ops" / "docker" / "Dockerfile.ai_agent").read_text(encoding="utf-8")
    assert "ops/docker/Dockerfile.ai_agent" in compose
    assert "ops/docker/Dockerfile.voc" in compose
    assert "allstar.ai_agent.api.main:app" in ai_dockerfile
    assert "allstar.voc.api.main:app" in compose
    assert "allstar.voc.agents.interpreter" in compose
    assert "./_OUTPUT:/srv/app/_OUTPUT" in compose


def test_ai_agent_paths_are_separated():
    assert quality_pipeline.TEST_CASE_FILE == ROOT / "src" / "allstar" / "ai_agent" / "evaluation" / "test_cases.json"
    assert quality_pipeline.REPORTS_DIR == ROOT / "_OUTPUT" / "reports" / "ai_agent" / "batch"
    assert quality_pipeline.TESTCASE_LOG_DIR == ROOT / "_OUTPUT" / "logs" / "ai_agent" / "testcase"
    assert live_report_generator.REPORTS_DIR == ROOT / "_OUTPUT" / "reports" / "ai_agent" / "live"
    assert config.CONVERSATION_LOG_DIR == ROOT / "_OUTPUT" / "logs" / "ai_agent" / "live" / "conversations"
    assert config.JUDGMENT_LOG_DIR == ROOT / "_OUTPUT" / "logs" / "ai_agent" / "live" / "judgments"


def test_voc_cross_validation_paths_are_separated():
    assert qa_test_utils.REPORTS_DIR == ROOT / "_OUTPUT" / "reports" / "voc" / "testcase"
    assert cross_validation.REPORT_ROOT == ROOT / "_OUTPUT" / "reports" / "voc" / "cross_validation"
    assert cross_validation.LOG_ROOT == ROOT / "_OUTPUT" / "logs" / "voc" / "cross_validation"


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
