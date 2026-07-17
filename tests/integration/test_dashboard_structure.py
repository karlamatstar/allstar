import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP = (ROOT / "src" / "allstar" / "ui" / "dashboard" / "streamlit_app.py").read_text(encoding="utf-8")
VIEWS = (ROOT / "src" / "allstar" / "ui" / "dashboard" / "views.py").read_text(encoding="utf-8")


def test_top_navigation_has_four_left_and_two_right_tabs():
    labels = [
        "AI 에이전트 챗봇",
        "VOC 챗봇",
        "모니터링",
        "리포트 모음",
        "AI 에이전트 테스트케이스",
        "VOC 테스트케이스",
    ]
    navigation = APP.split(") = st.tabs(", 1)[1]
    positions = [navigation.index(label) for label in labels]

    assert positions == sorted(positions)
    assert 'nth-child(5)' in APP
    assert "margin-left:auto" in APP


def test_monitoring_has_four_grafana_child_tabs():
    for label in (
        "AI 상담 실시간 운영",
        "K6 성능 부하 시험",
        "VOC 실시간 운영",
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
        "AI 상담 챗봇 보고서",
        "장애·기능 검증 보고서",
        "서버 연결 성능 보고서",
        "AI 상담 테스트케이스 보고서",
        "VOC 챗봇 보고서",
        "VOC A~D 테스트케이스 보고서",
    )
    assert all(label in VIEWS for label in labels)
    assert '["A", "B", "C", "D", "종합 비교"]' in VIEWS


def test_ai_and_voc_testcase_child_tabs_are_preserved():
    assert '["케이스 관리·실행", "배치 품질 현황", "유형별 비교", "케이스 상세"]' in VIEWS
    assert '["테스트케이스 관리", "실 테스트"]' in VIEWS
    assert "전체 테스트케이스 실행" in VIEWS
    assert "A·B·C·D 중 하나를 누르면" in VIEWS


def test_voc_has_seven_clickable_stage_definitions():
    for english in ("Interpreter", "Retriever", "Summarizer", "Evaluator", "Critic", "Improver", "LLM Judge"):
        assert english in VIEWS
    assert "_render_stage_explorer" in VIEWS
    assert "단계별 결과를 볼 테스트케이스" in VIEWS


def test_voc_gui_runner_does_not_limit_cases_but_agent_runner_can():
    assert '[sys.executable, "-u", str(PROJECT_ROOT / "tools" / "scripts" / "run_voc_profile.py"), "--profile", profile["profile_id"]]' in VIEWS
    runner = (ROOT / "tools" / "scripts" / "run_voc_profile.py").read_text(encoding="utf-8")
    assert '"--case-id"' in runner
    assert "생략하면 등록된 전체 케이스를 실행한다" in runner
