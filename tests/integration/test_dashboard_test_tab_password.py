from pathlib import Path

from allstar.ui.dashboard.access_control import (
    DEFAULT_TEST_TAB_PASSWORD,
    TEST_TAB_PASSWORD_ENV,
    configured_test_tab_password,
    matches_test_tab_password,
)


ROOT = Path(__file__).resolve().parents[2]
APP = (ROOT / "src" / "allstar" / "ui" / "dashboard" / "streamlit_app.py").read_text(encoding="utf-8")
COMPOSE = (ROOT / "compose.yml").read_text(encoding="utf-8")
ENV_EXAMPLE = (ROOT / ".env.example").read_text(encoding="utf-8")


def test_test_tab_password_defaults_to_1234(monkeypatch):
    monkeypatch.delenv(TEST_TAB_PASSWORD_ENV, raising=False)

    assert configured_test_tab_password() == DEFAULT_TEST_TAB_PASSWORD == "1234"
    assert matches_test_tab_password("1234") is True
    assert matches_test_tab_password("4321") is False


def test_test_tab_password_can_be_changed_by_environment(monkeypatch):
    monkeypatch.setenv(TEST_TAB_PASSWORD_ENV, "9876")

    assert matches_test_tab_password("1234") is False
    assert matches_test_tab_password("9876") is True


def test_three_top_test_tabs_are_independently_password_protected():
    expected = (
        '("k6_load", "K6 부하 테스트", render_k6_load_test)',
        '("ai_testcases", "AI 에이전트 테스트케이스", render_ai_testcases)',
        '("voc_testcases", "VOC 테스트케이스", render_voc_testcases)',
    )

    assert "type=\"password\"" in APP
    assert '[data-testid="stFormSubmitButton"] button:not(:disabled)' in APP
    assert "비밀번호가 올바르지 않습니다. 비밀번호를 다시 입력해 주세요." in APP
    assert "test_tab_access_{tab_key}" in APP
    assert "gate.empty()" in APP
    assert "st.rerun()" not in APP.split("def _render_password_protected_test_tab", 1)[1].split("st.set_page_config", 1)[0]
    for call in expected:
        assert call in APP


def test_docker_streamlit_receives_the_configurable_demo_password():
    setting = "DASHBOARD_TEST_TABS_PASSWORD: ${DASHBOARD_TEST_TABS_PASSWORD:-1234}"

    assert setting in COMPOSE
    assert "DASHBOARD_TEST_TABS_PASSWORD=1234" in ENV_EXAMPLE
