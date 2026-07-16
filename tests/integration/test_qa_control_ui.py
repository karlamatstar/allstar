"""QA 관리 GUI의 탭 표기와 기본 조작 구성을 검증한다."""

import importlib.util
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


def test_selected_and_unselected_tabs_use_the_same_padding():
    source = QA_CONTROL_PATH.read_text(encoding="utf-8")

    assert 'padding=[("selected", (14, 9)), ("!selected", (14, 9))]' in source
    assert 'background=[("selected", "#496080"), ("active", "#3b4a63")]' in source


def test_top_and_voc_tabs_use_two_line_labels():
    source = QA_CONTROL_PATH.read_text(encoding="utf-8")

    assert 'text="AI 상담 품질검사\\n(AI Agent QA)"' in source
    assert 'text="고객 의견 분석 품질검사\\n(VOC QA)"' in source
    assert 'text="전체 비AI 검사\\n(pytest)"' in source
    assert 'text="단위 테스트\\n(Unit Test)"' in source
    assert 'text=f"에이전트 교차 테스트\\n({profile_id})"' in source
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


def test_gui_descriptions_do_not_expose_report_folder_paths():
    source = QA_CONTROL_PATH.read_text(encoding="utf-8")

    assert "보고서는 _OUTPUT/reports에 저장됩니다" not in source
    assert "실행 방식과 확인 항목" in source
    assert "완료 후 결함 보고서가 자동 생성됩니다" in source
    assert "완료 후 성능 보고서가 자동 생성됩니다" in source
    assert "완료 후 프로필별 보고서가 자동 생성됩니다" in source
