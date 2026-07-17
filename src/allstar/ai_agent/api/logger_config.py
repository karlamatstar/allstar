import json
import logging
import threading
from datetime import datetime, timezone

from allstar.ai_agent.api.config import CONVERSATION_LOG_DIR, JUDGMENT_LOG_DIR

CONVERSATION_LOG_FILE = CONVERSATION_LOG_DIR / "conversations.jsonl"
EVALUATION_LOG_FILE = JUDGMENT_LOG_DIR / "live_evaluations.jsonl"
CONVERSATION_LOG_LOCK = threading.Lock()
EVALUATION_LOG_LOCK = threading.Lock()

logger = logging.getLogger("ai_agent")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(message)s"))
    logger.addHandler(handler)


def log_conversation(question: str, answer: str, latency_ms: float, status: str = "success",
                     rule_answer: str | None = None, request_id: str | None = None,
                     fault: dict | None = None) -> None:
    """대화 1턴을 JSONL로 기록합니다 (Grafana/Prometheus는 숫자 지표만, 원문 대화는 여기 로그 파일에 남긴다).
    answer는 API 기반 에이전트의 주 답변, rule_answer는 비교용 규칙 기반 답변.
    request_id는 채점 로그(live_evaluations.jsonl)와 짝을 맞추는 상관관계 ID."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_id": request_id,
        "question": question,
        "answer": answer,
        "rule_answer": rule_answer,
        "latency_ms": round(latency_ms, 1),
        "status": status,
    }
    if fault:
        entry["fault"] = fault
    with CONVERSATION_LOG_LOCK, open(CONVERSATION_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def log_evaluation(question: str, evaluation: dict, model: str = "api", request_id: str | None = None) -> None:
    """실시간 채점(AI Judge) 결과를 별도 JSONL로 기록합니다. model: "api" / "rule".
    request_id로 conversations.jsonl의 대화와 1:1로 연결된다."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_id": request_id,
        "question": question,
        "model": model,
        "evaluation": evaluation,
    }
    with EVALUATION_LOG_LOCK, open(EVALUATION_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
