"""QA 관리 GUI의 탭 표기와 기본 조작 구성을 검증한다."""

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
QA_CONTROL_PATH = ROOT / "tools" / "qa_control" / "main.py"
SPEC = importlib.util.spec_from_file_location("qa_control_main", QA_CONTROL_PATH)
assert SPEC and SPEC.loader
qa_control = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(qa_control)


def test_parenthesized_english_is_moved_to_second_tab_line():
    assert qa_control.two_line_tab_label("기본 동작 시험 (Smoke Test)") == "기본 동작 시험\n(Smoke Test)"
    assert qa_control.two_line_tab_label(
        "장애·기능 검증 시험 (Validation Test)"
    ) == "장애·기능 검증 시험\n(Validation Test)"
    assert qa_control.two_line_tab_label(
        "테스트케이스 품질 시험 (Test Case Test)"
    ) == "테스트케이스 품질 시험\n(Test Case Test)"


def test_selected_and_unselected_tabs_use_the_same_padding():
    source = QA_CONTROL_PATH.read_text(encoding="utf-8")

    assert 'padding=[("selected", (14, 9)), ("!selected", (14, 9))]' in source
    assert 'background=[("selected", "#496080"), ("active", "#3b4a63")]' in source


def test_top_and_voc_tabs_use_two_line_labels():
    source = QA_CONTROL_PATH.read_text(encoding="utf-8")

    assert 'text="AI 상담 품질검사\\n(AI Agent QA)"' in source
    assert 'text="고객 의견 분석 품질검사\\n(VOC QA)"' in source
    assert '"전체 비AI 검사\\n(pytest)"' in source
    assert '"단위 테스트\\n(Unit Test)"' in source
    assert 'f"에이전트 교차 테스트\\n({profile_id})"' in source
    assert 'title = f"에이전트 교차 테스트 ({profile_id})"' in source


def test_report_folder_button_is_removed():
    source = QA_CONTROL_PATH.read_text(encoding="utf-8")

    assert 'text="보고서 폴더"' not in source
    assert "def open_reports" not in source


def test_load_test_defaults_match_the_original_portfolio_gui():
    assert qa_control.LOAD_SETTINGS == {
        "일반 부하 시험 (Load Test)": ("20", "60"),
        "무작위 요청 시험 (Random Test)": ("100", "60"),
        "한계 부하 시험 (Stress Test)": ("100", "120"),
        "순간 급증 시험 (Spike Test)": ("200", "60"),
    }


def test_load_settings_require_positive_integers():
    assert qa_control.validate_load_settings("20", "60") == (20, 60)

    for vus, duration in (("abc", "60"), ("0", "60"), ("20", "0")):
        try:
            qa_control.validate_load_settings(vus, duration)
        except ValueError:
            pass
        else:
            raise AssertionError("잘못된 부하 설정이 허용되었습니다.")


def test_load_settings_are_forwarded_to_k6_environment():
    source = QA_CONTROL_PATH.read_text(encoding="utf-8")

    assert 'env["K6_VUS"] = str(vus)' in source
    assert 'env["SCRIPT_DURATION"] = str(duration)' in source
    assert 'env["TARGET_IP"] = "127.0.0.1:8000"' in source
    assert "설정: 최대 가상 인원 {vus}명 / 실행 시간 {duration}초" in source


def test_every_ai_test_has_a_specific_user_facing_description():
    titles = {title for title, _command, _confirm in qa_control.AI_TESTS}

    assert set(qa_control.TEST_DESCRIPTIONS) == titles
    for description in qa_control.TEST_DESCRIPTIONS.values():
        assert "확인" in description or "검증" in description
        assert "자동" in description


def test_api_performance_description_explains_independent_phases():
    description = qa_control.TEST_DESCRIPTIONS["서버 연결 성능 종합 시험 (API)"]

    assert all(label in description for label in ("1명", "10명", "25명"))
    assert "단계별 독립 실행" in description
    assert "5초간 안정화" in description


def test_every_k6_test_description_names_k6():
    descriptions_by_id = {
        qa_control.TEST_IDS[title]: description
        for title, description in qa_control.TEST_DESCRIPTIONS.items()
    }

    for test_id in qa_control.K6_REQUIRED_TEST_IDS:
        assert "K6" in descriptions_by_id[test_id]


def test_direct_k6_tests_are_grafana_only_and_composite_reports_are_preserved():
    source = QA_CONTROL_PATH.read_text(encoding="utf-8")

    assert qa_control.GRAFANA_ONLY_K6_TEST_IDS == {
        "ai_smoke", "ai_load", "ai_random", "ai_stress", "ai_spike",
    }
    assert "ai_validation" not in qa_control.GRAFANA_ONLY_K6_TEST_IDS
    assert "ai_api_performance" not in qa_control.GRAFANA_ONLY_K6_TEST_IDS
    assert "write_summary_report=self.test_id not in GRAFANA_ONLY_K6_TEST_IDS" in source
    for title, description in qa_control.TEST_DESCRIPTIONS.items():
        if qa_control.TEST_IDS[title] in qa_control.GRAFANA_ONLY_K6_TEST_IDS:
            assert "Grafana" in description
            assert "별도 사용자용 보고서는 생성하지 않습니다" in description


def test_find_k6_prefers_run_folder_then_system_path(tmp_path, monkeypatch):
    monkeypatch.setattr(qa_control, "ROOT", tmp_path)
    run_dir = tmp_path / "RUN"
    run_dir.mkdir()
    bundled = run_dir / "k6.exe"
    bundled.write_bytes(b"")
    monkeypatch.setattr(qa_control.shutil, "which", lambda _name: "C:/tools/k6.exe")

    assert qa_control.find_k6() == str(bundled)

    bundled.unlink()
    assert qa_control.find_k6() == "C:/tools/k6.exe"


def test_missing_k6_message_points_to_the_official_install_page():
    source = QA_CONTROL_PATH.read_text(encoding="utf-8")

    assert qa_control.K6_INSTALL_URL == "https://grafana.com/docs/k6/latest/set-up/install-k6/"
    assert "K6를 다운로드·설치한 뒤" in source
    assert 'messagebox.askyesno("K6 설치 필요", message)' in source
    assert "webbrowser.open(K6_INSTALL_URL)" in source


def test_gui_descriptions_do_not_expose_report_folder_paths():
    source = QA_CONTROL_PATH.read_text(encoding="utf-8")

    assert "보고서는 _OUTPUT/reports에 저장됩니다" not in source
    assert "실행 방식과 확인 항목" in source
    assert "완료 후 결함 보고서가 자동 생성됩니다" in source
    assert "완료 후 성능 보고서가 자동 생성됩니다" in source
    assert "완료 후 프로필별 보고서가 자동 생성됩니다" in source


def test_voc_profile_gui_uses_all_registered_cases():
    total_cases, api_cases = qa_control.load_voc_case_counts()
    source = QA_CONTROL_PATH.read_text(encoding="utf-8")

    assert total_cases == 10
    assert api_cases == 9
    assert "등록된 VOC 테스트케이스 전체" in qa_control.VOC_PROFILE_DESCRIPTION
    assert '"전체 테스트케이스": total_cases' in source
    assert '"실제 AI 평가 대상": api_cases' in source
    assert "대표 사례 2건만 실행합니다" not in source


def test_ai_testcase_quality_test_is_last_ai_tab_and_uses_all_cases():
    title, command, confirm = qa_control.AI_TESTS[-1]
    source = QA_CONTROL_PATH.read_text(encoding="utf-8")

    assert title == "테스트케이스 품질 시험 (Test Case Test)"
    assert command[-1] == "allstar.ai_agent.evaluation.quality_pipeline"
    assert confirm is True
    assert qa_control.TEST_IDS[title] == "ai_testcase"
    assert qa_control.load_ai_case_count() == 6
    assert "등록된 전체 테스트케이스: {total_cases}건" in source
    assert "케이스당 최대 3회" in source
    assert '"전체 테스트케이스": total_cases' in source


def test_global_execution_lock_updates_all_tab_buttons():
    app = qa_control.QAControl()
    app.withdraw()
    app.update_idletasks()
    try:
        assert len(app.test_tabs) == 15
        assert app.test_tabs[8].title_text == "테스트케이스 품질 시험 (Test Case Test)"
        assert app.minsize() == (1200, 650)
        assert all(tab.start_button.cget("state") == "normal" for tab in app.test_tabs)
        assert all(tab.stop_button.cget("state") == "disabled" for tab in app.test_tabs)

        active = app.test_tabs[0]
        assert app.acquire_execution(active) is True
        assert all(tab.start_button.cget("state") == "disabled" for tab in app.test_tabs)
        assert active.stop_button.cget("state") == "normal"
        assert all(tab.stop_button.cget("state") == "disabled" for tab in app.test_tabs[1:])

        app.release_execution(active)
        assert all(tab.start_button.cget("state") == "normal" for tab in app.test_tabs)
        assert all(tab.stop_button.cget("state") == "disabled" for tab in app.test_tabs)
    finally:
        app.destroy()


def test_run_events_are_written_as_structured_jsonl(tmp_path, monkeypatch):
    run_log = tmp_path / "qa_control_runs.jsonl"
    monkeypatch.setattr(qa_control, "RUN_LOG", run_log)

    qa_control.append_run_event({"event": "started", "status": "running", "test": "시험"})
    qa_control.append_run_event({"event": "finished", "status": "cancelled", "test": "시험"})

    events = [json.loads(line) for line in run_log.read_text(encoding="utf-8").splitlines()]
    assert [event["status"] for event in events] == ["running", "cancelled"]


def test_validation_command_excludes_external_ai_tests_by_default():
    source = (ROOT / "tools" / "scripts" / "run_validation_tests.py").read_text(encoding="utf-8")

    assert "--ignore=tests/ai_agent/test_negative_cases.py" in source
    assert "--ignore=tests/ai_agent/test_evaluation_pipeline.py" in source
    assert "--ignore=tests/voc/evaluation/test_pipeline_e2e.py" in source
    assert '"-k", "not end_to_end"' in source
