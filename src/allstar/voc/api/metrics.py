from __future__ import annotations

from datetime import datetime
from pathlib import Path

from prometheus_client import REGISTRY, Counter, Gauge, Histogram, make_asgi_app

from allstar.shared.log_retention import read_daily_jsonl
from allstar.voc.api.progress_metrics import VocProgressMetricsCollector
from allstar.voc.api.testcase_metrics import VocTestcaseReportCollector


metrics_app = make_asgi_app()
voc_chat_total = Counter("voc_chat_requests_total", "VOC 챗봇 요청 수", ["status", "profile"])
voc_chat_latency = Histogram(
    "voc_chat_latency_seconds",
    "VOC 전체 처리 시간",
    ["profile"],
    buckets=(1, 3, 5, 10, 20, 30, 45, 60, 90, 120, 180),
)
voc_judge_total = Counter("voc_judge_total", "VOC 최종 Judge 결과", ["status", "profile"])
voc_judge_verdict_total = Counter(
    "voc_judge_verdict_total",
    "VOC 독립 Judge 최종 판정 수",
    ["verdict", "profile"],
)
voc_judge_score = Histogram(
    "voc_judge_score",
    "VOC 독립 Judge 총점(0~100)",
    ["profile"],
    buckets=(0, 59, 60, 69, 70, 79, 80, 89, 90, 100),
)
voc_judge_duration = Histogram(
    "voc_judge_duration_seconds",
    "VOC 독립 Judge 처리 시간(초)",
    ["profile"],
    buckets=(1, 3, 5, 10, 20, 30, 45, 60, 90, 120),
)
voc_chat_last_activity = Gauge(
    "voc_chat_last_activity_timestamp_seconds",
    "프로필별 마지막 VOC 채팅 완료 Unix 시간",
    ["profile"],
)


def initialize_metric_series() -> None:
    """요청이 없을 때도 A~D 기본 시계열을 노출한다."""
    for profile in ("A", "B", "C", "D"):
        for status in ("success", "no_data", "error"):
            voc_chat_total.labels(status=status, profile=profile)
        for status in ("success", "error"):
            voc_judge_total.labels(status=status, profile=profile)
        for verdict in (
            "배포 가능",
            "조건부 배포 가능, 개선 후 재검증",
            "주요 개선 필요",
            "배포 보류",
            "배포 보류(즉시)",
            "N/A",
        ):
            voc_judge_verdict_total.labels(verdict=verdict, profile=profile)
        voc_chat_latency.labels(profile=profile)
        voc_judge_score.labels(profile=profile)
        voc_judge_duration.labels(profile=profile)


def restore_last_activity_from_logs(conversation_dir: Path) -> dict[str, float]:
    """누적 VOC 대화 로그에서 프로필별 최신 완료 시각을 Gauge에 복원한다."""
    latest: dict[str, float] = {}
    if not conversation_dir.exists():
        return latest
    for row in read_daily_jsonl(conversation_dir):
        try:
            profile = str(row.get("profile_id") or "").upper()
            value = row.get("finished_at") or row.get("timestamp")
            timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
        except (AttributeError, TypeError, ValueError):
            continue
        if profile not in {"A", "B", "C", "D"}:
            continue
        latest[profile] = max(latest.get(profile, 0.0), timestamp)
    for profile, timestamp in latest.items():
        if timestamp > 0:
            voc_chat_last_activity.labels(profile=profile).set(timestamp)
    return latest

# A~D 배치는 짧게 실행되는 별도 프로세스이므로 메모리 Counter를 직접 쓰지 않는다.
# 계속 실행되는 VOC API가 공유 정식 보고서를 읽어 테스트케이스 지표를 제공한다.
voc_testcase_report_collector = VocTestcaseReportCollector()
REGISTRY.register(voc_testcase_report_collector)
voc_progress_metrics_collector = VocProgressMetricsCollector()
REGISTRY.register(voc_progress_metrics_collector)
