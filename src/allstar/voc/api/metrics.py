from prometheus_client import Counter, Histogram, make_asgi_app


metrics_app = make_asgi_app()
voc_chat_total = Counter("voc_chat_requests_total", "VOC 챗봇 요청 수", ["status", "profile"])
voc_chat_latency = Histogram(
    "voc_chat_latency_seconds",
    "VOC 전체 처리 시간",
    ["profile"],
    buckets=(1, 3, 5, 10, 20, 30, 45, 60, 90, 120, 180),
)
voc_judge_total = Counter("voc_judge_total", "VOC 최종 Judge 결과", ["status", "profile"])
