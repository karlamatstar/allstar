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


def test_grafana_only_k6_keeps_metrics_and_logs_without_user_report(monkeypatch, tmp_path):
    configure_output_roots(monkeypatch, tmp_path)
    session = qa_reporting.QAReportSession(
        "ai_load", "일반 부하 시험", ["k6", "run", "load_test.js"],
        settings={"최대 가상 인원(VU)": 20, "실행 시간(초)": 60},
        write_summary_report=False,
    )
    session.start()
    assert session.command_for_execution()[2].startswith("--summary-export=")
    assert "experimental-prometheus-rw" in session.command_for_execution()
    assert f"testid={session.run_id}" in session.command_for_execution()
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
    assert result["report"] is None
    assert session.log_path.exists()
    assert session.k6_summary_path.exists()
    assert not session.report_path.exists()
    assert not session.latest_report_path.exists()
    assert not session.manifest_path.exists()
    assert not session.latest_manifest_path.exists()
    events = [json.loads(line) for line in qa_reporting.QA_EVENT_LOG.read_text(encoding="utf-8").splitlines()]
    assert events[-1]["metrics"]["response_time_p95_ms"] == 240.8
    assert events[-1]["report"] is None


def test_k6_v2_summary_metrics_are_parsed(monkeypatch, tmp_path):
    configure_output_roots(monkeypatch, tmp_path)
    session = qa_reporting.QAReportSession(
        "ai_random", "무작위 요청 시험", ["k6", "run", "random_test.js"],
        write_summary_report=False,
    )
    session.start()
    session.k6_summary_path.write_text(json.dumps({
        "metrics": {
            "http_reqs": {"count": 1558, "rate": 24.9},
            "http_req_failed": {"passes": 0, "fails": 1558, "value": 0},
            "http_req_duration": {"avg": 1507.0, "p(95)": 1526.9},
            "checks": {"passes": 1558, "fails": 0, "value": 1},
        }
    }), encoding="utf-8")

    result = session.finish("completed", 0)

    assert result["metrics"]["request_count"] == 1558
    assert result["metrics"]["failure_rate"] == 0
    assert result["metrics"]["response_time_p95_ms"] == 1526.9
    assert result["metrics"]["checks_passed"] == 1558


def test_composite_k6_wrappers_keep_summary_reports(monkeypatch, tmp_path):
    configure_output_roots(monkeypatch, tmp_path)

    for test_id in ("ai_validation", "ai_api_performance"):
        session = qa_reporting.QAReportSession(test_id, "종합 시험", ["python", "wrapper.py"])
        session.start()
        result = session.finish("completed", 0)

        assert result["report"] is not None
        assert session.report_path.exists()
        assert session.latest_manifest_path.exists()


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


def test_failed_voc_profile_draft_preserves_latest_formal_report(tmp_path):
    runner_path = ROOT / "tools" / "scripts" / "run_voc_profile.py"
    spec = importlib.util.spec_from_file_location("run_voc_profile_guard_failed", runner_path)
    assert spec and spec.loader
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    report_dir = tmp_path / "reports" / "d"
    draft_dir = tmp_path / "logs" / "run-failed" / "report_draft"
    report_dir.mkdir(parents=True)
    draft_dir.mkdir(parents=True)
    (report_dir / "quality_score_report.md").write_text("# 최근 정상 보고서\n", encoding="utf-8")
    (report_dir / "report_manifest.json").write_text('{"run_id":"good-run"}', encoding="utf-8")
    (draft_dir / "quality_score_report.md").write_text("# 실패한 부분 보고서\n", encoding="utf-8")
    manifest = {"run_id": "failed-run", "status": "failed"}

    published = runner.publish_profile_report_if_successful(
        draft_dir, report_dir, manifest, process_returncode=2, judge_failures=["TC-05"]
    )

    assert published is False
    assert (report_dir / "quality_score_report.md").read_text(encoding="utf-8") == "# 최근 정상 보고서\n"
    assert json.loads((report_dir / "report_manifest.json").read_text(encoding="utf-8"))["run_id"] == "good-run"
    assert (draft_dir / "quality_score_report.md").exists()


def test_successful_voc_profile_draft_replaces_latest_formal_report(tmp_path):
    runner_path = ROOT / "tools" / "scripts" / "run_voc_profile.py"
    spec = importlib.util.spec_from_file_location("run_voc_profile_guard_success", runner_path)
    assert spec and spec.loader
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    report_dir = tmp_path / "reports" / "a"
    draft_dir = tmp_path / "logs" / "run-good" / "report_draft"
    report_dir.mkdir(parents=True)
    (draft_dir / "assets").mkdir(parents=True)
    (report_dir / "quality_score_report.md").write_text("# 이전 보고서\n", encoding="utf-8")
    (report_dir / ".gitkeep").write_bytes(b"")
    (draft_dir / "quality_score_report.md").write_text("# 새 정상 보고서\n", encoding="utf-8")
    (draft_dir / "llm_judge_result.csv").write_text("case_id,total\nTC-01,90\n", encoding="utf-8")
    (draft_dir / "assets" / "chart.png").write_bytes(b"png")
    manifest = {"run_id": "good-run", "status": "completed"}

    published = runner.publish_profile_report_if_successful(
        draft_dir, report_dir, manifest, process_returncode=0, judge_failures=[]
    )

    assert published is True
    assert (report_dir / "quality_score_report.md").read_text(encoding="utf-8") == "# 새 정상 보고서\n"
    assert json.loads((report_dir / "report_manifest.json").read_text(encoding="utf-8")) == manifest
    assert (report_dir / "assets" / "chart.png").read_bytes() == b"png"
    assert (report_dir / ".gitkeep").read_bytes() == b""


def test_voc_profile_runner_writes_cases_to_run_draft_before_publishing():
    source = (ROOT / "tools" / "scripts" / "run_voc_profile.py").read_text(encoding="utf-8")

    assert 'draft_report_dir = log_dir / "report_draft"' in source
    assert "command = build_judge_command(draft_report_dir, case_ids)" in source
    assert '_atomic_json(log_dir / "run_manifest.json", manifest)' in source


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
