from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VIEWS = (ROOT / "src" / "allstar" / "ui" / "dashboard" / "views.py").read_text(encoding="utf-8")
APP = (ROOT / "src" / "allstar" / "ui" / "dashboard" / "streamlit_app.py").read_text(encoding="utf-8")
DOC = (ROOT / "_DOCS" / "AI_QUALITY_DASHBOARD_UI_IMPROVEMENTS.md").read_text(encoding="utf-8")


def test_ai_chat_confirmation_and_chat_panel_order_are_explicit():
    section = VIEWS[VIEWS.index("def render_ai_chat"):VIEWS.index("def _render_profile_cards")]
    assert section.index('"ai_chat_api_confirm"') < section.index('key="ai_chat_panel"')
    assert section.index('key="ai_chat_panel"') < section.index('key="ai_chat_input"')
    assert "disabled=not api_confirmed or bool(pending)" in section


def test_ai_chat_shows_user_first_and_typing_state_inside_chat_window():
    assert "AI_CHAT_EXECUTOR.submit(_request_ai_chat, question)" in VIEWS
    assert "history.append({\"role\": \"user\"" in VIEWS
    assert "답변을 입력하고 있습니다" in VIEWS
    assert "if pending and _complete_ai_chat_request" in VIEWS
    assert 'st.session_state.pop("ai_chat_pending", None)' in VIEWS
    assert 'stChatMessageAvatarUser' in APP
    assert 'stChatMessageAvatarAssistant' in APP
    assert "flex-direction:row-reverse" in APP


def test_live_and_batch_quality_charts_share_grouped_pagination():
    assert "def _render_grouped_quality_chart" in VIEWS
    assert 'barmode="group"' in VIEWS
    assert '[5, 10, 20, "전체"]' in VIEWS
    assert '"← 이전"' in VIEWS
    assert '"다음 →"' in VIEWS
    assert "on_click=_change_quality_page" in VIEWS
    assert 'key="ai_live_quality"' in VIEWS
    assert 'key="ai_batch_quality"' in VIEWS
    assert 'item_column="request_id", item_label="대화"' in VIEWS
    assert 'item_column="case_id", item_label="테스트케이스"' in VIEWS


def test_live_and_batch_breakdowns_share_radar_and_exact_score_table():
    assert "정확한 평균점수" in VIEWS
    assert "품질 평균" in VIEWS
    assert "점수 차이" in VIEWS
    assert "N/A·미채점 제외" in VIEWS
    assert "SCORE_DESCRIPTIONS" in VIEWS
    assert 'key="ai_live_breakdown"' in VIEWS
    assert 'key="ai_batch_breakdown"' in VIEWS
    assert "quality-score-help" in APP


def test_live_and_batch_details_keep_the_same_renderer_with_distinct_keys():
    assert '_render_quality_detail(live_df, key="ai_live_detail")' in VIEWS
    assert '_render_quality_detail(df, key="ai_batch_detail")' in VIEWS
    assert 'key=f"{key}_decision"' in VIEWS


def test_followup_document_records_all_confirmed_behaviors():
    for phrase in (
        "필수 체크 사항",
        "답변을 입력하고 있습니다",
        "좌우 막대",
        "5개, 10개, 20개, 전체",
        "정확한 평균점수 표",
        "대화별 채점 상세",
        "케이스 상세",
    ):
        assert phrase in DOC
