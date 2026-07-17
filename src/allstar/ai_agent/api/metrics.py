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
