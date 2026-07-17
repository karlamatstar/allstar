from prometheus_client import REGISTRY, Counter, Histogram, make_asgi_app

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

# A~D 배치는 짧게 실행되는 별도 프로세스이므로 메모리 Counter를 직접 쓰지 않는다.
# 계속 실행되는 VOC API가 공유 정식 보고서를 읽어 테스트케이스 지표를 제공한다.
voc_testcase_report_collector = VocTestcaseReportCollector()
REGISTRY.register(voc_testcase_report_collector)
