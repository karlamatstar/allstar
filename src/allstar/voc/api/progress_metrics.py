"""누적 VOC 진행 기록을 Prometheus 운영 지표로 변환한다."""

from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from prometheus_client.core import CounterMetricFamily, HistogramMetricFamily

from allstar.voc.evaluation.progress import PROGRESS_ROOT, STAGE_NAMES


PROFILES = ("A", "B", "C", "D")
RUN_MODES = ("live", "batch")
STAGE_STATES = ("done", "failed", "skipped")
HISTOGRAM_BUCKETS = (0.1, 0.5, 1, 3, 5, 10, 20, 30, 60, 120, 180, 300, 600)
RETRIEVAL_BASE_SERIES = (
    ("found", "none"),
    ("no_data", "no_match"),
    ("error", "unknown"),
)
NO_DATA_REASON_PATTERN = re.compile(r"(?:원인|reason)\s*[:=]\s*([a-z_]+)", re.IGNORECASE)


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _duration(stage: dict[str, Any]) -> float | None:
    started = _parse_time(stage.get("started_at"))
    finished = _parse_time(stage.get("finished_at"))
    if not started or not finished:
        return None
    value = (finished - started).total_seconds()
    return value if value >= 0 else None


def classify_failure_reason(detail: Any) -> str:
    text = str(detail or "").lower()
    if any(token in text for token in ("401", "403", "authentication", "api key", "api_key", "x-api-key", "인증")):
        return "auth"
    if any(token in text for token in ("429", "rate limit", "rate_limit", "quota", "한도")):
        return "rate_limit"
    if any(token in text for token in ("timeout", "timed out", "deadline exceeded", "시간 초과")):
        return "timeout"
    if any(token in text for token in ("connection", "connecterror", "connection refused", "dns", "연결")):
        return "connection"
    if any(token in text for token in ("500", "502", "503", "504", "server error", "overloaded", "unavailable")):
        return "provider_server"
    if any(token in text for token in ("json", "parse", "decode", "validation", "응답 해석")):
        return "response_parse"
    if any(token in text for token in ("csv", "file not found", "no such file", "data source", "데이터 파일")):
        return "data_source"
    return "unknown"


def classify_provider(detail: Any) -> str:
    text = str(detail or "").lower()
    if "anthropic" in text or "claude" in text:
        return "anthropic"
    if "openai" in text or "gpt-" in text:
        return "openai"
    return "unknown"


def _run_mode(data: dict[str, Any]) -> str:
    cases = data.get("cases") or []
    return "live" if len(cases) == 1 and str(cases[0].get("case_id")) == "LIVE" else "batch"


def _no_data_reason(stage: dict[str, Any]) -> str:
    detail = str(stage.get("detail") or "")
    match = NO_DATA_REASON_PATTERN.search(detail)
    return match.group(1).lower() if match else "no_match"


def _is_no_data_case(case: dict[str, Any], stages: list[dict[str, Any]]) -> bool:
    if case.get("status") == "no_data":
        return True
    return any(
        stage.get("state") == "skipped" and "관련 VOC 데이터" in str(stage.get("detail") or "")
        for stage in stages[2:]
    )


def _read_progress_files(root: Path) -> Iterable[dict[str, Any]]:
    if not root.exists():
        return
    for path in sorted(root.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            yield data


def _histogram_buckets(values: list[float]) -> list[tuple[str, float]]:
    ordered = sorted(value for value in values if math.isfinite(value) and value >= 0)
    buckets = [(str(boundary), float(sum(value <= boundary for value in ordered))) for boundary in HISTOGRAM_BUCKETS]
    buckets.append(("+Inf", float(len(ordered))))
    return buckets


class VocProgressMetricsCollector:
    """진행 JSON을 매 수집 시 집계해 재시작 뒤에도 동일한 값을 제공한다."""

    def __init__(self, progress_root: Path | None = None):
        self.progress_root = progress_root or PROGRESS_ROOT

    def collect(self):
        stage_counts: Counter[tuple[str, str, str, str]] = Counter()
        stage_durations: dict[tuple[str, str, str], list[float]] = defaultdict(list)
        retrieval_counts: Counter[tuple[str, str, str, str]] = Counter()
        failure_counts: Counter[tuple[str, str, str, str, str]] = Counter()

        for data in _read_progress_files(self.progress_root):
            profile = str(data.get("profile_id") or "").upper()
            if profile not in PROFILES:
                continue
            mode = _run_mode(data)
            for case in data.get("cases") or []:
                stages = case.get("stages") or []
                for stage in stages:
                    name = str(stage.get("name") or "unknown")
                    state = str(stage.get("state") or "pending")
                    if state in STAGE_STATES:
                        stage_counts[(profile, mode, name, state)] += 1
                    elapsed = _duration(stage)
                    if elapsed is not None and state in {"done", "failed"}:
                        stage_durations[(profile, mode, name)].append(elapsed)
                    if state == "failed":
                        detail = stage.get("detail")
                        failure_counts[(
                            profile,
                            mode,
                            classify_provider(detail),
                            name,
                            classify_failure_reason(detail),
                        )] += 1

                retriever = next((stage for stage in stages if stage.get("name") == "Retriever"), None)
                if not retriever:
                    continue
                if retriever.get("state") == "failed":
                    retrieval_counts[(profile, mode, "error", classify_failure_reason(retriever.get("detail")))] += 1
                elif retriever.get("state") == "done":
                    if _is_no_data_case(case, stages):
                        retrieval_counts[(profile, mode, "no_data", _no_data_reason(retriever))] += 1
                    else:
                        retrieval_counts[(profile, mode, "found", "none")] += 1

        stage_runs = CounterMetricFamily(
            "voc_stage_runs",
            "누적 VOC 단계 실행 상태 수",
            labels=["profile", "mode", "stage", "status"],
        )
        for profile in PROFILES:
            for mode in RUN_MODES:
                for stage in STAGE_NAMES:
                    for state in STAGE_STATES:
                        stage_runs.add_metric([profile, mode, stage, state], stage_counts[(profile, mode, stage, state)])
        yield stage_runs

        stage_duration = HistogramMetricFamily(
            "voc_stage_duration_seconds",
            "누적 VOC 단계별 처리시간",
            labels=["profile", "mode", "stage"],
        )
        for profile in PROFILES:
            for mode in RUN_MODES:
                for stage in STAGE_NAMES:
                    values = stage_durations[(profile, mode, stage)]
                    stage_duration.add_metric(
                        [profile, mode, stage],
                        _histogram_buckets(values),
                        sum(values),
                    )
        yield stage_duration

        retrievals = CounterMetricFamily(
            "voc_retrieval_results",
            "VOC 검색 결과와 원인 수",
            labels=["profile", "mode", "result", "reason"],
        )
        for profile in PROFILES:
            for mode in RUN_MODES:
                for result, reason in RETRIEVAL_BASE_SERIES:
                    retrieval_counts[(profile, mode, result, reason)] += 0
        for labels, value in sorted(retrieval_counts.items()):
            retrievals.add_metric(list(labels), value)
        yield retrievals

        failures = CounterMetricFamily(
            "voc_pipeline_failures",
            "VOC 외부 API와 파이프라인 실패 원인 수",
            labels=["profile", "mode", "provider", "stage", "reason"],
        )
        for labels, value in sorted(failure_counts.items()):
            failures.add_metric(list(labels), value)
        yield failures

