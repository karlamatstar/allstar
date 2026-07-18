"""통합 대시보드의 의미 기반 색상·채팅 입력·자동 이동 계약을 검증한다."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP = (ROOT / "src" / "allstar" / "ui" / "dashboard" / "streamlit_app.py").read_text(encoding="utf-8")
VIEWS = (ROOT / "src" / "allstar" / "ui" / "dashboard" / "views.py").read_text(encoding="utf-8")


def test_semantic_button_colors_and_disabled_override_exist():
    assert "--allstar-positive:" in APP
    assert "--allstar-danger:" in APP
    assert "--allstar-disabled:" in APP
    assert '[data-testid="stBaseButton-primary"]' in APP
    assert '[data-testid="stBaseButton-primary"] * {color:#fff !important;}' in APP
    assert '[class*="st-key-stop_"] button' in APP
    assert '[class*="st-key-ai_fault_"] button' in APP
    assert '[class*="st-key-voc_chat_profile_"] button:not(:disabled)' in APP
    assert '[class*="st-key-k6_card_"][class*="_failed"]' in APP
    assert "border:2px solid var(--allstar-danger)" in APP
    assert ".stApp button:disabled" in APP
    assert ".stApp button:disabled *" in APP
    assert "cursor:not-allowed" in APP


def test_chat_panels_and_input_areas_are_emphasized():
    assert "border-width:2px !important" in APP
    assert '[data-testid="stChatInput"]:focus-within' in APP
    assert ".chat-input-guide" in APP
    assert ':has(.chat-input-guide)' in APP
    assert "min-height:2.25rem !important" in APP
    assert "<div class='chat-input-guide'>메시지 입력</div>" in VIEWS
    assert "<div class='chat-input-guide'>VOC 메시지 입력</div>" in VIEWS


def test_voc_execution_uses_launch_and_detail_scroll_phases():
    assert "st.session_state.voc_scroll_to_run_id = run_id" in VIEWS
    assert "st.session_state.voc_scroll_to_detail_run_id = run_id" in VIEWS
    assert '_scroll_to_voc_run_bottom(run_id, "launch")' in VIEWS
    assert '_scroll_to_voc_run_bottom(run_id, "detail")' in VIEWS
    assert 'progress.get("current_case_id") or not running' in VIEWS


def test_negative_fault_buttons_have_stable_semantic_keys():
    assert 'key="ai_fault_503"' in VIEWS
    assert 'key="ai_fault_504"' in VIEWS
    assert 'key="ai_fault_server_down"' in VIEWS
