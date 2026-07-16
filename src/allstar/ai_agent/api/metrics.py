from prometheus_client import Counter, Histogram, make_asgi_app

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
