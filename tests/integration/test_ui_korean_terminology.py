"""주요 GUI와 대시보드가 한국어 우선 용어를 유지하는지 확인한다."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_server_control_uses_korean_first_labels_without_changing_service_ids():
    source = read("tools/server_control/main.py")

    assert "AI 상담 서버 (Portfolio API)" in source
    assert "통합 화면 (Streamlit)" in source
    assert "질문 의도 분석 (Interpreter)" in source
    assert "운영 상태 화면 (Grafana)" in source
    assert '"portfolio-api"' in source
    assert '"voc-interpreter"' in source


def test_qa_control_explains_test_and_model_terms_in_korean():
    source = read("tools/qa_control/main.py")

    assert "기본 동작 시험 (Smoke Test)" in source
    assert "한계 부하 시험 (Stress Test)" in source
    assert "독립 품질 평가(Judge)" in source
    assert "추론 끔(none)" in source
    assert "낮음(low)" in source


def test_integrated_dashboard_uses_korean_first_navigation_and_explanations():
    source = read("src/allstar/ui/dashboard/streamlit_app.py")

    assert "AI 상담 챗봇 (AI Agent)" in source
    assert "고객 의견 분석 (VOC)" in source
    assert "통합 결과 보고서 (Report)" in source
    assert "통합 상태 확인 (Monitoring)" in source
    assert "독립 품질 평가 (LLM Judge)" in source
    assert "서버 기능 명세 열기 (Portfolio Swagger)" in source


def test_legacy_dashboard_explains_monitoring_and_evaluation_terms():
    source = read("src/allstar/ui/dashboard/portfolio_legacy.py")

    assert "운영 상태 확인 (Grafana)" in source
    assert "성능 부하 시험 (k6)" in source
    assert "서버 연결 방식(API)" in source
    assert "통과(PASS)" in source
    assert "검토 필요(REVIEW)" in source
    assert "실패(FAIL)" in source
