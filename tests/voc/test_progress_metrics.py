from __future__ import annotations

import json

from allstar.voc.api.progress_metrics import (
    VocProgressMetricsCollector,
    classify_failure_reason,
    classify_provider,
)


def _sample(families, name: str, **labels):
    for family in families:
        for sample in family.samples:
            if sample.name == name and all(sample.labels.get(key) == value for key, value in labels.items()):
                return sample.value
    raise AssertionError(f"표본을 찾지 못했습니다: {name} {labels}")


def test_progress_collector_aggregates_stage_duration_no_data_and_failure(tmp_path):
    progress = {
        "profile_id": "A",
        "total_cases": 2,
        "cases": [
            {
                "case_id": "TC-01",
                "status": "completed",
                "stages": [
                    {
                        "name": "Interpreter",
                        "state": "done",
                        "started_at": "2026-07-18T10:00:00+09:00",
                        "finished_at": "2026-07-18T10:00:02+09:00",
                        "detail": "완료",
                    },
                    {
                        "name": "Retriever",
                        "state": "done",
                        "started_at": "2026-07-18T10:00:02+09:00",
                        "finished_at": "2026-07-18T10:00:03+09:00",
                        "detail": "완료",
                    },
                ],
            },
            {
                "case_id": "TC-09",
                "status": "no_data",
                "stages": [
                    {
                        "name": "Retriever",
                        "state": "done",
                        "started_at": "2026-07-18T10:01:00+09:00",
                        "finished_at": "2026-07-18T10:01:04+09:00",
                        "detail": "검색 결과 0건 · 원인: retry_exhausted",
                    },
                    {
                        "name": "Summarizer",
                        "state": "skipped",
                        "started_at": None,
                        "finished_at": "2026-07-18T10:01:04+09:00",
                        "detail": "관련 VOC 데이터가 없어 실행하지 않음",
                    },
                    {
                        "name": "LLM Judge",
                        "state": "failed",
                        "started_at": "2026-07-18T10:01:04+09:00",
                        "finished_at": "2026-07-18T10:01:14+09:00",
                        "detail": "Anthropic API 429 rate limit",
                    },
                ],
            },
        ],
    }
    (tmp_path / "run.json").write_text(json.dumps(progress, ensure_ascii=False), encoding="utf-8")

    families = list(VocProgressMetricsCollector(tmp_path).collect())

    assert _sample(
        families,
        "voc_stage_runs_total",
        profile="A",
        mode="batch",
        stage="Interpreter",
        status="done",
    ) == 1
    assert _sample(
        families,
        "voc_stage_duration_seconds_sum",
        profile="A",
        mode="batch",
        stage="Retriever",
    ) == 5
    assert _sample(
        families,
        "voc_retrieval_results_total",
        profile="A",
        mode="batch",
        result="no_data",
        reason="retry_exhausted",
    ) == 1
    assert _sample(
        families,
        "voc_pipeline_failures_total",
        profile="A",
        mode="batch",
        provider="anthropic",
        stage="LLM Judge",
        reason="rate_limit",
    ) == 1


def test_failure_classification_uses_bounded_labels():
    assert classify_provider("OpenAI GPT timeout") == "openai"
    assert classify_provider("Claude 호출 실패") == "anthropic"
    assert classify_failure_reason("HTTP 401 invalid API key") == "auth"
    assert classify_failure_reason("deadline exceeded") == "timeout"
    assert classify_failure_reason("connection refused") == "connection"
    assert classify_failure_reason("unexpected text") == "unknown"

