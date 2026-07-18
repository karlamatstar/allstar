import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP = (ROOT / "src" / "allstar" / "ui" / "dashboard" / "streamlit_app.py").read_text(encoding="utf-8")
VIEWS = (ROOT / "src" / "allstar" / "ui" / "dashboard" / "views.py").read_text(encoding="utf-8")


def test_top_navigation_has_four_left_and_three_right_tabs():
    labels = [
        "AI 에이전트 챗봇",
        "VOC 챗봇",
        "모니터링",
        "보고서 모음",
        "K6 부하 테스트",
        "AI 에이전트 테스트케이스",
        "VOC 테스트케이스",
    ]
    navigation = APP.split(") = st.tabs(", 1)[1]
    positions = [navigation.index(label) for label in labels]

    assert positions == sorted(positions)
    assert 'nth-child(5)' in APP
    assert "margin-left:auto" in APP


def test_monitoring_has_four_grafana_child_tabs():
    assert "?orgId=1&kiosk" in VIEWS
    for label in (
        "AI 에이전트 실시간 운영",
        "K6 성능 부하 시험",
        "VOC 챗봇 실시간 운영",
        "VOC QA·A~D 비교",
    ):
        assert label in VIEWS

    expected = {
        "grafana_dashboard.json": "ai-agent-quality",
        "k6_dashboard.json": "k6-performance-test",
        "voc_live_dashboard.json": "voc-live-operations",
        "voc_qa_dashboard.json": "voc-qa-abcd",
    }
    dashboard_root = ROOT / "ops" / "monitoring" / "grafana" / "provisioning" / "dashboards" / "json"
    for filename, uid in expected.items():
        dashboard = json.loads((dashboard_root / filename).read_text(encoding="utf-8"))
        assert dashboard["uid"] == uid
        assert dashboard["panels"]


def test_report_collection_has_six_child_tabs_and_profile_comparison():
    labels = (
        "AI 에이전트 챗봇 보고서",
        "AI 에이전트 테스트케이스 보고서",
        "VOC 챗봇 보고서",
        "VOC 테스트케이스 보고서",
        "서버 연결 성능 보고서",
        "장애·기능 검증 보고서",
    )
    report_view = VIEWS.split("def render_reports()", 1)[1].split("def _quality_rows", 1)[0]
    positions = [report_view.index(label) for label in labels]
    assert positions == sorted(positions)
    for label in (
        "교차 테스트 (A)",
        "교차 테스트 (B)",
        "교차 테스트 (C)",
        "교차 테스트 (D)",
        "종합 비교",
    ):
        assert label in VIEWS


def test_grafana_follows_browser_system_theme():
    compose = (ROOT / "compose.yml").read_text(encoding="utf-8")
    dashboard_root = ROOT / "ops" / "monitoring" / "grafana" / "provisioning" / "dashboards" / "json"

    assert "GF_USERS_DEFAULT_THEME: system" in compose
    for path in dashboard_root.glob("*.json"):
        dashboard = json.loads(path.read_text(encoding="utf-8"))
        assert dashboard.get("style") not in {"light", "dark"}
    assert "_sync_grafana_theme_with_browser()" in VIEWS


def test_ai_and_voc_testcase_child_tabs_are_preserved():
    assert '["테스트케이스 관리", "테스트케이스 실행", "배치 품질 현황", "유형별 비교", "케이스 상세"]' in VIEWS
    assert '["테스트케이스 관리", "테스트케이스 실행"]' in VIEWS
    assert "def _render_ai_case_execution" in VIEWS
    assert "GUI 전체 실행 범위" not in VIEWS
    assert "전체 테스트케이스 실행" in VIEWS
    assert "A·B·C·D 중 하나를 누르면" in VIEWS


def test_testcase_management_expanders_scroll_to_opened_section():
    assert "def _enable_management_expander_scroll" in VIEWS
    for key in (
        "ai_case_edit_expander",
        "ai_case_add_expander",
        "ai_case_delete_expander",
        "voc_case_edit_expander",
        "voc_case_add_expander",
        "voc_case_delete_expander",
    ):
        assert f'key="{key}"' in VIEWS
    assert "__allstarManagementExpanderScrollInstalled" in VIEWS
    assert 'if (!summary || !details || details.open) return;' in VIEWS
    assert '}}, true);' in VIEWS
    assert "summary.scrollIntoView" in VIEWS
    assert 'block: "start"' in VIEWS


def test_ai_voc_and_k6_use_fixed_autoscroll_terminals():
    assert "def _render_live_terminal" in VIEWS
    assert "st.container(height=360, border=True, autoscroll=True, key=key)" in VIEWS
    assert 'key=f"{state_key}_terminal_{state.get(\'run_id\', \'current\')}"' in VIEWS
    assert 'key=f"voc_terminal_{run_id}"' in VIEWS
    assert 'key=f"k6_terminal_{run.run_id}"' in VIEWS
    assert "wrap_lines=True" in VIEWS


def test_dashboard_tabs_theme_and_narrow_layout_are_explicit():
    assert '@media (prefers-color-scheme: dark)' in APP
    assert '--allstar-bg:#0d1420' in APP
    assert '[data-baseweb="tab-list"], [role="tablist"] {' in APP
    assert '[data-testid="stTab"]::before' in APP
    assert 'background:var(--allstar-selected) !important' in APP
    assert '[data-baseweb="tab-highlight"] {display:none !important;}' in APP
    assert '.react-aria-SelectionIndicator' in APP
    assert '.block-container {padding-left:1.2rem !important; padding-right:1.2rem !important;}' in APP
    assert '@media (max-width:900px)' in APP
    assert '@media (max-width:600px)' in APP
    assert 'overflow-x:auto; flex-wrap:nowrap' in APP


def test_all_streamlit_external_api_entrypoints_use_required_confirmation_box():
    assert "def _required_api_confirmation" in VIEWS
    for key in (
        "ai_chat_api_confirm",
        "voc_chat_api_confirm",
        "ai_run_confirm",
        "voc_all_confirm",
        "k6_api_performance_confirm",
    ):
        assert f'"{key}"' in VIEWS
    assert VIEWS.count("_required_api_confirmation(") == 6  # 함수 정의 1회 + 사용 5회
    assert "disabled=not api_confirmed" in VIEWS
    assert "disabled=bool(pending) or not api_confirmed" in VIEWS
    assert '[class*="st-key-required_api_confirm_"]' in APP
    assert VIEWS.index('"voc_chat_api_confirm"') < VIEWS.index("_render_profile_cards(list(profiles)")


def test_k6_top_tab_has_seven_cards_without_child_tabs():
    assert "render_k6_load_test" in APP
    for label in (
        "기본 동작 시험",
        "일반 부하 시험",
        "무작위 요청 시험",
        "한계 부하 시험",
        "순간 급증 시험",
        "장애·기능 검증 시험",
        "서버 연결 성능 종합 시험",
    ):
        assert label in VIEWS or label in (ROOT / "src" / "allstar" / "ui" / "dashboard" / "k6_load_runner.py").read_text(encoding="utf-8")
    assert "_render_k6_load_test_fragment" in VIEWS
    assert "max_chars=50000" in VIEWS
    assert 'st.container(height=360, border=True, autoscroll=True' in VIEWS
    assert "시험 중지" in VIEWS
    assert "_scroll_to_k6_run_once" in VIEWS
    assert '@media (max-width:1399px) and (min-width:761px)' in APP
    assert 'flex:1 1 calc(50% - 1.1rem) !important' in APP
    assert '@media (max-width:760px)' in APP
    assert 'flex:1 1 100% !important' in APP
    assert '[class*="st-key-k6_card_"] > [class*="st-key-run_k6_"] {margin-top:auto;}' in APP
    assert 'grid-template-columns:2.35rem minmax(0,1fr) 2.35rem !important' in APP
    assert '[data-testid="stNumberInputField"]' in APP
    assert '[data-testid="stNumberInputStepDown"]' in APP
    assert '[data-testid="stNumberInputStepUp"]' in APP
    assert 'grid-column:1 !important' in APP
    assert 'grid-column:2 !important' in APP
    assert 'grid-column:3 !important' in APP
    assert "args=(vus_key, K6_MIN_VUS, K6_MAX_VUS)" in VIEWS
    assert "args=(duration_key, K6_MIN_DURATION, K6_MAX_DURATION)" in VIEWS
    assert "가상 인원: 최소 {K6_MIN_VUS}명 · 최대 {K6_MAX_VUS}명" in VIEWS
    assert "실행 시간: 최소 {K6_MIN_DURATION}초 · 최대 {K6_MAX_DURATION}초" in VIEWS
    assert "범위를 벗어난 값을 직접 입력하면 최소값 또는 최대값으로 자동 조정됩니다." in VIEWS
    assert "def _clamp_k6_number_input" in VIEWS
    assert "def _enable_k6_number_hold_repeat" in VIEWS
    assert "__allstarK6HoldRepeatInstalled" in VIEWS
    assert "const reachedBoundary = (button)" in VIEWS
    assert "event.stopImmediatePropagation()" in VIEWS
    assert "root.setTimeout" in VIEWS and "root.setInterval(repeat, 100)" in VIEWS
    assert '["pointerup", "pointercancel", "mouseup", "touchend"]' in VIEWS


def test_voc_has_seven_clickable_stage_definitions():
    for english in ("Interpreter", "Retriever", "Summarizer", "Evaluator", "Critic", "Improver", "LLM Judge"):
        assert english in VIEWS
    assert "_render_stage_explorer" in VIEWS
    assert "단계별 결과를 볼 테스트케이스" in VIEWS
    assert 'scroll_mode = "interactive" if interactive else "progress"' in VIEWS
    assert 'st.container(key=f"stage_scroll_{scroll_mode}_{safe_key}")' in VIEWS
    assert "horizontal=True" in VIEWS
    assert 'st.container(horizontal=True, gap="small", key=f"stage_top_{safe_key}")' in VIEWS
    assert 'st.container(width=180, key=f"stage_top_cell_{safe_key}_{index}")' in VIEWS
    assert 'st.container(width=26, key=f"stage_top_arrow_{safe_key}_{index}")' in VIEWS
    assert 'st.container(width=180, key=f"stage_cell_{safe_key}_{index}")' in VIEWS
    assert 'st.container(width=26, key=f"stage_arrow_{safe_key}_{index}")' in VIEWS
    assert 'f"{symbols[state]} {index + 1}. {korean}\\n({english}) {state_labels[state]}"' in VIEWS
    assert '[class*="st-key-stage_arrow_"]' in APP
    assert '[class*="st-key-stage_buttons_"] [data-testid="stMarkdownContainer"]' not in APP
    assert "columns = st.columns([4, .7" not in VIEWS


def test_voc_execution_cards_reserve_status_height_without_moving_buttons():
    assert "profile-card profile-execution-card" in VIEWS
    assert "profile-card-stack" in VIEWS
    assert "profile-status-slot is-empty" in VIEWS
    assert "profile-status-badge profile-status-" in VIEWS
    assert ".profile-execution-card {height:17rem; padding-bottom:14px;}" in APP
    assert ".profile-execution-card {height:19rem;}" in APP


def test_voc_chat_confirmation_controls_visual_selection_and_messenger_layout():
    assert "is_selected = confirmed and selected == profile" in VIEWS
    assert "disabled=disabled or not confirmed or is_selected or not available" in VIEWS
    assert 'type="primary" if confirmed and not is_selected and available and not disabled else "secondary"' in VIEWS
    assert "profile-status-selected" in VIEWS
    assert "profile-selected" in VIEWS
    assert "with st.container(height=520, border=True, autoscroll=True):" in VIEWS
    assert "VOC 관련 질문을 입력하면 이 영역에 메신저 형태로 대화" in VIEWS
    assert '"meta": f"사용자 · {_local_time_text()}"' in VIEWS


def test_voc_report_manifest_changes_trigger_full_app_refresh():
    assert "def _voc_report_signature" in VIEWS
    assert "def watch_voc_report_updates" in VIEWS
    assert 'VOC_REPORT_ROOT / "testcase" / profile / "report_manifest.json"' in VIEWS
    assert 'st.rerun(scope="app")' in VIEWS
    assert "watch_voc_report_updates" in APP


def test_voc_gui_runner_does_not_limit_cases_but_agent_runner_can():
    assert 'str(PROJECT_ROOT / "tools" / "scripts" / "run_voc_profile.py")' in VIEWS
    assert '"--profile", profile["profile_id"], "--run-id", run_id' in VIEWS
    runner = (ROOT / "tools" / "scripts" / "run_voc_profile.py").read_text(encoding="utf-8")
    assert '"--case-id"' in runner
    assert '"--run-id"' in runner
    assert "생략하면 등록된 전체 케이스를 실행한다" in runner
