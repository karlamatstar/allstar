"""QA 누적 로그와 최신 보고서 자동화 규칙을 검증한다."""

from __future__ import annotations

import json
import importlib.util
from pathlib import Path

from allstar.shared import qa_reporting


ROOT = Path(__file__).resolve().parents[2]


def configure_output_roots(monkeypatch, tmp_path):
    monkeypatch.setattr(qa_reporting, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(qa_reporting, "QA_LOG_ROOT", tmp_path / "_OUTPUT" / "logs" / "qa")
    monkeypatch.setattr(qa_reporting, "QA_REPORT_ROOT", tmp_path / "_OUTPUT" / "reports" / "qa" / "latest")
    monkeypatch.setattr(qa_reporting, "QA_MANIFEST_ROOT", tmp_path / "_OUTPUT" / "reports" / "manifests" / "qa")
    monkeypatch.setattr(qa_reporting, "QA_EVENT_LOG", tmp_path / "_OUTPUT" / "logs" / "qa" / "qa_runs.jsonl")


def test_logs_accumulate_while_latest_report_is_overwritten(monkeypatch, tmp_path):
    configure_output_roots(monkeypatch, tmp_path)

    first = qa_reporting.QAReportSession("ai_smoke", "기본 동작 시험", ["python", "first.py"])
    first.start()
    first.append_output("1 passed in 0.01s\n")
    first.finish("completed", 0)

    second = qa_reporting.QAReportSession("ai_smoke", "기본 동작 시험", ["python", "second.py"])
    second.start()
    second.append_output("1 failed in 0.02s\n")
    second.finish("failed", 1)

    logs = sorted((qa_reporting.QA_LOG_ROOT / "runs" / "ai_smoke").glob("*.log"))
    assert len(logs) == 2
    report = (qa_reporting.QA_REPORT_ROOT / "ai_smoke.md").read_text(encoding="utf-8")
    assert second.run_id in report
    assert first.run_id not in report
    assert "상태: **실패**" in report

    events = [json.loads(line) for line in qa_reporting.QA_EVENT_LOG.read_text(encoding="utf-8").splitlines()]
    assert [event["event"] for event in events] == ["started", "finished", "started", "finished"]


def test_k6_summary_metrics_are_written_to_report(monkeypatch, tmp_path):
    configure_output_roots(monkeypatch, tmp_path)
    session = qa_reporting.QAReportSession(
        "ai_load", "일반 부하 시험", ["k6", "run", "load_test.js"],
        settings={"최대 가상 인원(VU)": 20, "실행 시간(초)": 60},
    )
    session.start()
    assert session.command_for_execution()[2].startswith("--summary-export=")
    session.k6_summary_path.write_text(json.dumps({
        "metrics": {
            "http_reqs": {"values": {"count": 120}},
            "http_req_failed": {"values": {"rate": 0.025}},
            "http_req_duration": {"values": {"avg": 125.4, "p(95)": 240.8}},
            "checks": {"values": {"passes": 117, "fails": 3}},
        }
    }), encoding="utf-8")
    result = session.finish("completed", 0)

    assert result["metrics"]["request_count"] == 120
    report = session.report_path.read_text(encoding="utf-8")
    assert "요청 실패율: 2.500%" in report
    assert "p95 응답시간: 240.800ms" in report


def test_latest_manifest_points_to_accumulated_source_log(monkeypatch, tmp_path):
    configure_output_roots(monkeypatch, tmp_path)
    session = qa_reporting.QAReportSession("voc_unit", "단위 테스트", ["pytest"])
    session.start()
    session.append_output("12 passed, 2 skipped, 1 deselected in 1.00s\n")
    session.finish("completed", 0)

    manifest = json.loads(session.latest_manifest_path.read_text(encoding="utf-8"))
    assert manifest["run_id"] == session.run_id
    assert manifest["metrics"]["pytest"] == {"passed": 12, "skipped": 2, "deselected": 1}
    assert manifest["sources"] == [str(session.log_path.relative_to(tmp_path)).replace("\\", "/")]


def test_semantic_api_failure_is_reported_as_completed_with_warnings(monkeypatch, tmp_path):
    configure_output_roots(monkeypatch, tmp_path)
    session = qa_reporting.QAReportSession("voc_profile_a", "에이전트 교차 테스트 (A)", ["runner"])
    session.start()
    session.append_output("Judge 실패: Anthropic 401 API key is invalid.\nN/A - 미평가(API 실패)\n")
    result = session.finish("completed", 0)

    assert result["status"] == "completed_with_warnings"
    assert result["process_status"] == "completed"
    assert "독립 평가 실패" in result["warnings"]
    assert "상태: **경고 포함 완료**" in session.report_path.read_text(encoding="utf-8")


def test_voc_profile_runner_rejects_unrated_judge_report(tmp_path):
    runner_path = ROOT / "tools" / "scripts" / "run_voc_profile.py"
    spec = importlib.util.spec_from_file_location("run_voc_profile", runner_path)
    assert spec and spec.loader
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)

    report = tmp_path / "llm_judge_result.csv"
    report.write_text("case_id,verdict\nTC-01,미평가(API 실패)\n", encoding="utf-8-sig")

    assert runner.judge_report_failed(report) is True


def test_voc_profile_runner_uses_one_process_for_all_cases_by_default(tmp_path):
    runner_path = ROOT / "tools" / "scripts" / "run_voc_profile.py"
    spec = importlib.util.spec_from_file_location("run_voc_profile_single", runner_path)
    assert spec and spec.loader
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)

    command = runner.build_judge_command(tmp_path / "reports")

    all_cases = runner.resolve_case_ids()
    assert len(all_cases) > 2
    assert command.count("--case-id") == len(all_cases)
    assert command[command.index("--case-id") + 1] == "TC-01"
    assert all(case_id in command for case_id in all_cases)
    assert command.count("--output-dir") == 1


def test_voc_profile_runner_can_limit_agent_validation_to_two_cases(tmp_path):
    runner_path = ROOT / "tools" / "scripts" / "run_voc_profile.py"
    spec = importlib.util.spec_from_file_location("run_voc_profile_limited", runner_path)
    assert spec and spec.loader
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)

    command = runner.build_judge_command(tmp_path / "reports", ["TC-01", "TC-02"])

    assert command.count("--case-id") == 2
    assert "TC-01" in command
    assert "TC-02" in command


def test_voc_execution_summary_links_formal_profile_report(monkeypatch, tmp_path):
    configure_output_roots(monkeypatch, tmp_path)
    report_root = tmp_path / "_OUTPUT" / "reports"
    monkeypatch.setattr(qa_reporting, "REPORT_ROOT", report_root)
    formal_report = report_root / "voc" / "testcase" / "a" / "quality_score_report.md"
    formal_report.parent.mkdir(parents=True)
    formal_report.write_text("# 정식 보고서", encoding="utf-8")
    session = qa_reporting.QAReportSession("voc_profile_a", "에이전트 교차 테스트 (A)", ["runner"])
    session.start()
    result = session.finish("completed", 0)

    assert result["formal_reports"] == [str(formal_report.relative_to(tmp_path)).replace("\\", "/")]
    summary = session.report_path.read_text(encoding="utf-8")
    assert "정식 결과 보고서" in summary
    assert "quality_score_report.md" in summary
