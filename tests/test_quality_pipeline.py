"""실제 OpenAI API를 호출하는 통합 테스트입니다. 비용 절감을 위해 전체 30건이 아닌
소규모 표본만 파이프라인에 태워, 에이전트 호출→규칙 검증→AI Judge 채점→리포트 생성까지
엔드투엔드로 정상 동작하는지 확인합니다. 전체 배치 실행은 `python -m ai_quality.quality_pipeline`로 별도 수행하세요."""
import json

from ai_quality.quality_pipeline import TEST_CASE_FILE, load_test_cases, run_pipeline

SAMPLE_SIZE = 2


def test_pipeline_generates_reports(tmp_path, monkeypatch):
    import ai_quality.quality_pipeline as pipeline

    monkeypatch.setattr(pipeline, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(pipeline, "TESTCASE_LOG_DIR", tmp_path / "logs" / "testcase")
    monkeypatch.setattr(pipeline, "MANIFEST_DIR", tmp_path / "logs" / "manifests")
    monkeypatch.setattr(pipeline, "PROJECT_ROOT", tmp_path)

    test_cases = load_test_cases(TEST_CASE_FILE)[:SAMPLE_SIZE]
    results = run_pipeline(test_cases, timestamp="test_run")

    assert len(results) == SAMPLE_SIZE
    for result in results:
        # 케이스마다 규칙 기반/API 기반 두 채점 결과가 모두 존재해야 한다
        for model_type in ("rule_based", "api_based"):
            assert result[model_type]["evaluation"]["overall_decision"] in {"PASS", "REVIEW", "FAIL", "N/A"}

    latest_json = tmp_path / "reports" / "evaluation_result.json"
    latest_md = tmp_path / "reports" / "final_quality_report.md"
    assert latest_json.exists()
    assert latest_md.exists()

    saved = json.loads(latest_json.read_text(encoding="utf-8"))
    assert len(saved) == SAMPLE_SIZE
