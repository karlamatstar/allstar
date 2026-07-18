import logging
import threading
from datetime import datetime, timezone

from allstar.ai_agent.api.config import CONVERSATION_LOG_DIR, JUDGMENT_LOG_DIR
from allstar.shared.log_retention import (
    append_daily_jsonl,
    compress_daily_groups,
    migrate_legacy_jsonl,
)
from allstar.shared.paths import AI_AGENT_LOG_ROOT

FAULT_LOG_DIR = AI_AGENT_LOG_ROOT / "live" / "faults"
CONVERSATION_LOG_FILE = CONVERSATION_LOG_DIR / "conversations.jsonl"  # 마이그레이션할 구버전 파일
EVALUATION_LOG_FILE = JUDGMENT_LOG_DIR / "live_evaluations.jsonl"  # 마이그레이션할 구버전 파일
FAULT_EVENT_LOG_FILE = FAULT_LOG_DIR / "fault_events.jsonl"  # 마이그레이션할 구버전 파일
CONVERSATION_LOG_LOCK = threading.Lock()
EVALUATION_LOG_LOCK = threading.Lock()

logger = logging.getLogger("ai_agent")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(message)s"))
    logger.addHandler(handler)


def maintain_live_logs() -> None:
    """구버전 누적 파일을 날짜별로 전환하고 오래된 활동 날짜를 압축한다."""
    migrate_legacy_jsonl(CONVERSATION_LOG_FILE, CONVERSATION_LOG_DIR)
    migrate_legacy_jsonl(EVALUATION_LOG_FILE, JUDGMENT_LOG_DIR)
    migrate_legacy_jsonl(FAULT_EVENT_LOG_FILE, FAULT_LOG_DIR)
    compress_daily_groups((CONVERSATION_LOG_DIR, JUDGMENT_LOG_DIR, FAULT_LOG_DIR))


def compress_ai_live_logs() -> None:
    try:
        compress_daily_groups((CONVERSATION_LOG_DIR, JUDGMENT_LOG_DIR, FAULT_LOG_DIR))
    except Exception as error:
        logger.warning("AI 라이브 로그 자동 압축 실패: %s", error)


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
    append_daily_jsonl(CONVERSATION_LOG_DIR, entry, lock=CONVERSATION_LOG_LOCK)
    compress_ai_live_logs()


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
    append_daily_jsonl(JUDGMENT_LOG_DIR, entry, lock=EVALUATION_LOG_LOCK)
    compress_ai_live_logs()
