from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from prometheus_client import Counter, Gauge, Histogram, make_asgi_app

metrics_app = make_asgi_app()

chat_requests_total = Counter(
    "chat_requests_total", "챗봇 /chat 요청 수", ["status"]
)
chat_request_latency_seconds = Histogram(
    "chat_request_latency_seconds", "/chat 응답 지연시간(초)",
    buckets=(0.5, 1, 2, 3, 5, 8, 13, 21, 34, 55, 60),
)
agent_retry_total = Counter(
    "agent_retry_total", "에이전트 API 재시도 횟수", ["agent"]
)
agent_unavailable_total = Counter(
    "agent_unavailable_total", "재시도 소진 후 API 호출 실패(N/A) 횟수", ["agent"]
)
# model 라벨: "api"(API 기반 에이전트) / "rule"(규칙 기반 에이전트) — 실시간 비교 채점용
judge_evaluations_total = Counter(
    "judge_evaluations_total", "AI Judge 채점 결과 건수", ["decision", "model"]
)
judge_score_total = Histogram(
    "judge_score_total", "AI Judge 종합 점수(0~25)", ["model"], buckets=(0, 5, 10, 14, 15, 19, 20, 25)
)
judge_axis_score = Histogram(
    "judge_axis_score", "AI Judge 세부 항목별 점수(0~5)", ["axis", "model"], buckets=(0, 1, 2, 3, 4, 5)
)
judge_evaluation_duration_seconds = Histogram(
    "judge_evaluation_duration_seconds",
    "AI Judge 채점 처리 시간(초)",
    ["model"],
    buckets=(1, 3, 5, 10, 15, 20, 30, 45, 60),
)
chat_last_activity_timestamp_seconds = Gauge(
    "chat_last_activity_timestamp_seconds",
    "마지막 실제 AI 에이전트 채팅 완료 Unix 시간",
)


def initialize_metric_series() -> None:
    """트래픽이 없을 때도 Grafana가 '데이터 없음' 대신 0을 표시하게 기본 시계열을 만든다."""
    for status in ("success", "error", "fallback"):
        chat_requests_total.labels(status=status)
    for agent in ("service_agent", "judge_agent"):
        agent_retry_total.labels(agent=agent)
        agent_unavailable_total.labels(agent=agent)
    for model in ("api", "rule"):
        judge_score_total.labels(model=model)
        judge_evaluation_duration_seconds.labels(model=model)
        for decision in ("PASS", "REVIEW", "FAIL", "N/A"):
            judge_evaluations_total.labels(decision=decision, model=model)
        for axis in ("accuracy", "groundedness", "helpfulness", "safety", "understandability"):
            judge_axis_score.labels(axis=axis, model=model)


def restore_last_activity_from_log(log_path: Path) -> float | None:
    """누적 대화 로그의 최신 시각을 서버 재시작 뒤 Gauge에 복원한다."""
    if not log_path.exists():
        return None
    latest: float | None = None
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
            value = row.get("timestamp")
            timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
        except (AttributeError, TypeError, ValueError, json.JSONDecodeError):
            continue
        latest = timestamp if latest is None else max(latest, timestamp)
    if latest is not None and latest > 0:
        chat_last_activity_timestamp_seconds.set(latest)
    return latest


def restore_service_failure_metrics_from_log(
    log_path: Path,
    *,
    retries_per_failure: int,
) -> dict[str, int]:
    """누적 대화 로그의 실제·강제 장애를 요청·retry/unavailable Counter에 복원한다."""
    if not log_path.exists():
        return {"retry": 0, "unavailable": 0, "chat_error": 0, "chat_fallback": 0}
    unavailable_count = 0
    chat_error_count = 0
    chat_fallback_count = 0
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        fault = row.get("fault") if isinstance(row, dict) else None
        forced_fault = isinstance(fault, dict) and fault.get("type") in {"http_503", "http_504", "server_down"}
        unavailable_status = isinstance(row, dict) and row.get("status") in {"error", "fallback"}
        if forced_fault or unavailable_status:
            unavailable_count += 1
        if forced_fault:
            chat_error_count += 1
        elif isinstance(row, dict) and row.get("status") == "fallback":
            chat_fallback_count += 1
    retry_count = unavailable_count * max(0, retries_per_failure)
    if retry_count:
        agent_retry_total.labels(agent="service_agent").inc(retry_count)
    if unavailable_count:
        agent_unavailable_total.labels(agent="service_agent").inc(unavailable_count)
    if chat_error_count:
        chat_requests_total.labels(status="error").inc(chat_error_count)
    if chat_fallback_count:
        chat_requests_total.labels(status="fallback").inc(chat_fallback_count)
    return {
        "retry": retry_count,
        "unavailable": unavailable_count,
        "chat_error": chat_error_count,
        "chat_fallback": chat_fallback_count,
    }
