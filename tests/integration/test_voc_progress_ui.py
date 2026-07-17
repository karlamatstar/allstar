"""VOC A~D 실행의 진행 상태와 대시보드 표시 계약을 검증한다."""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from allstar.ui.dashboard import views
from allstar.voc.evaluation import progress


ROOT = Path(__file__).resolve().parents[2]
VIEWS = (ROOT / "src" / "allstar" / "ui" / "dashboard" / "views.py").read_text(encoding="utf-8")
APP = (ROOT / "src" / "allstar" / "ui" / "dashboard" / "streamlit_app.py").read_text(encoding="utf-8")
RUNNER = (ROOT / "tools" / "scripts" / "run_voc_profile.py").read_text(encoding="utf-8")
SUMMARIZER = (ROOT / "src" / "allstar" / "voc" / "agents" / "summarizer.py").read_text(encoding="utf-8")
COMPOSE = (ROOT / "compose.yml").read_text(encoding="utf-8")


def _stage_explorer_app():
    from allstar.ui.dashboard import views as dashboard_views

    status = {
        "status": "completed",
        "result": {
            "intent_json": "{}",
            "trace": "Retriever:count=1",
            "summary": "요약",
            "eval_json": "{}",
            "summary_critic_json": "{}",
            "policy": "개선 답변",
        },
        "judge": "독립 평가",
    }
    dashboard_views._render_stage_explorer(status, "responsive_stage_test")


def test_progress_file_tracks_current_case_and_stage_states(tmp_path, monkeypatch):
    monkeypatch.setattr(progress, "PROGRESS_ROOT", tmp_path)
    cases = [
        {"case_id": "TC-01", "question": "첫 질문", "category": "기본"},
        {"case_id": "TC-02", "question": "둘째 질문", "category": "예외"},
    ]

    path = progress.initialize_progress("run-1", "A", cases)
    progress.start_case("run-1", "TC-01")
    progress.set_stage("run-1", "TC-01", 1, "running", "의도 분석 중")
    progress.set_stage("run-1", "TC-01", 1, "done", "의도 분석 완료")
    progress.set_stage("run-1", "TC-01", 2, "running", "검색 중")

    data = progress.read_progress("run-1")
    assert path.exists()
    assert data["profile_id"] == "A"
    assert data["current_case_id"] == "TC-01"
    assert data["current_case_index"] == 1
    assert [stage["state"] for stage in data["cases"][0]["stages"][:3]] == ["done", "running", "pending"]


def test_progress_failure_marks_active_and_remaining_stages(tmp_path, monkeypatch):
    monkeypatch.setattr(progress, "PROGRESS_ROOT", tmp_path)
    progress.initialize_progress("run-2", "B", [{"case_id": "TC-01", "question": "질문"}])
    progress.start_case("run-2", "TC-01")
    progress.set_stage("run-2", "TC-01", 3, "running")
    progress.fail_active_stage("run-2", "TC-01", "요약 실패")

    case = progress.read_progress("run-2")["cases"][0]
    assert case["status"] == "failed"
    assert case["stages"][2]["state"] == "failed"
    assert all(stage["state"] == "skipped" for stage in case["stages"][3:])


def test_dashboard_uses_partial_refresh_utf8_and_completion_guard():
    assert "@st.fragment(run_every=1.0)" in VIEWS
    assert 'env["PYTHONIOENCODING"] = "utf-8"' in VIEWS
    assert 'raw.decode("cp949", errors="replace")' in VIEWS
    assert "profile-running" in VIEWS and "profile-completed" in VIEWS
    assert "완료 상태를 먼저 닫은 뒤" in VIEWS
    assert "테스트케이스 평균" in VIEWS
    assert "interactive=False" in VIEWS
    assert VIEWS.index("단계별 결과를 볼 테스트케이스") < VIEWS.rindex("실행 내용 보기")
    assert '[data-stale="true"] {opacity:1 !important;}' in APP
    assert '[class*="st-key-stage_scroll_"] {overflow-x:auto' in APP
    assert '[class*="st-key-stage_buttons_"] [data-testid="stHorizontalBlock"]' in APP
    assert ".profile-card {height:auto; min-height:0; overflow-y:visible" in APP


def test_runner_and_summarizer_share_one_progress_run_id():
    assert '"ALLSTAR_VOC_PROGRESS_RUN_ID": run_id' in RUNNER
    assert "initialize_progress(run_id" in RUNNER
    assert 'metadata.get("x-allstar-run-id"' in SUMMARIZER
    assert "set_stage(progress_run_id" in SUMMARIZER
    summarizer_block = COMPOSE.split("  voc-summarizer:", 1)[1].split("  voc-evaluator:", 1)[0]
    assert "./_OUTPUT:/srv/app/_OUTPUT" in summarizer_block


def test_report_source_uses_readable_ranges_and_compact_pass_table():
    source = (ROOT / "src" / "allstar" / "voc" / "evaluation" / "llm_judge.py").read_text(encoding="utf-8")
    assert "80–89점" in source and "70–79점" in source and "69점 이하" in source
    assert "80~89" not in source and "~69 배포 보류" not in source
    assert "| 케이스 | 판정 | 확인 결과 | 처리시간 |" in source
    assert "PASS(예외처리) 기술 상세 펼치기" in source


def test_process_output_reads_utf8_and_legacy_cp949(tmp_path):
    utf8_log = tmp_path / "utf8.log"
    cp949_log = tmp_path / "cp949.log"
    utf8_log.write_bytes("신규 실행 로그".encode("utf-8"))
    cp949_log.write_bytes("기존 실행 로그".encode("cp949"))

    assert views._read_process_output(utf8_log) == "신규 실행 로그"
    assert views._read_process_output(cp949_log) == "기존 실행 로그"


def test_voc_run_metrics_uses_exact_log_times_and_case_average():
    log = {
        "started_at": "2026-07-17T10:00:00+09:00",
        "finished_at": "2026-07-17T10:01:10+09:00",
        "case_results": [
            {"total_seconds": 10.0},
            {"total_seconds": "20.0"},
            {"total_seconds": None},
        ],
    }

    run_seconds, average, count = views._voc_run_metrics(log)

    assert run_seconds == 70.0
    assert average == 15.0
    assert count == 2


def test_stage_selector_renders_seven_uniform_two_line_buttons():
    app = AppTest.from_function(_stage_explorer_app).run()

    assert not app.exception
    assert len(app.button) == 7
    assert app.button[4].label == "✓ 5. 결과 검토\n(Critic) 완료"
    assert app.button[6].label == "✓ 7. 독립 품질 평가\n(LLM Judge) 완료"


def test_voc_report_signature_changes_after_manifest_is_written(tmp_path, monkeypatch):
    monkeypatch.setattr(views, "VOC_REPORT_ROOT", tmp_path)
    initial = views._voc_report_signature()
    manifest = tmp_path / "testcase" / "c" / "report_manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text('{"status":"completed"}', encoding="utf-8")

    updated = views._voc_report_signature()

    assert initial != updated
    assert updated[2] == manifest.stat().st_mtime_ns
