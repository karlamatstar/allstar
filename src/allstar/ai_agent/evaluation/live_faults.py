"""AI 실시간 챗봇의 명시적 장애 시험을 실제 대화·N/A 채점 로그로 기록한다."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from allstar.ai_agent.api.logger_config import log_conversation, log_evaluation, logger
from allstar.ai_agent.evaluation.live_report_generator import generate_live_report
from allstar.ai_agent.evaluation.live_report_status import mark_completed, mark_failed, mark_reporting
from allstar.shared.paths import AI_AGENT_LOG_ROOT


AXES = ("accuracy", "groundedness", "helpfulness", "safety", "understandability")
FAULT_EVENT_LOG = AI_AGENT_LOG_ROOT / "live" / "faults" / "fault_events.jsonl"
FAULT_EVENT_LOCK = threading.Lock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_fault_na_evaluation(reason: str, fault_type: str, http_status: int | None) -> dict[str, Any]:
    """인프라·통신 장애를 AI 품질 FAIL이 아닌 평가 불가 N/A로 만든다."""
    evaluation: dict[str, Any] = {
        axis: {"score": None, "reason": reason}
        for axis in AXES
    }
    evaluation.update({
        "total_score": None,
        "overall_decision": "N/A",
        "summary": reason,
        "fault_type": fault_type,
        "http_status": http_status,
        "evaluation_status": "infrastructure_error",
    })
    return evaluation


def record_fault_event(event: str, **details: Any) -> None:
    entry = {"timestamp": _utc_now(), "event": event, **details}
    FAULT_EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with FAULT_EVENT_LOCK, FAULT_EVENT_LOG.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry, ensure_ascii=False) + "\n")


def record_chat_fault(
    *,
    question: str,
    case_id: str | None,
    fault_type: str,
    error_message: str,
    latency_ms: float,
    http_status: int | None,
    error_detail: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """장애 질문 1건과 API·규칙 기반 N/A 평가 2행을 저장하고 최신 보고서를 갱신한다."""
    request_id = request_id or uuid.uuid4().hex
    fault = {
        "type": fault_type,
        "http_status": http_status,
        "case_id": case_id,
        "error_detail": error_detail or error_message,
    }
    log_conversation(
        question,
        error_message,
        latency_ms,
        status="error",
        rule_answer=error_message,
        request_id=request_id,
        fault=fault,
    )
    reason = (
        f"{error_message} AI 답변 품질 문제가 아닌 인프라·통신 장애이므로 채점하지 않고 N/A로 처리했습니다."
    )
    evaluation = create_fault_na_evaluation(reason, fault_type, http_status)
    for model in ("api", "rule"):
        log_evaluation(question, evaluation, model=model, request_id=request_id)

    record_fault_event(
        "chat_fault_recorded",
        request_id=request_id,
        case_id=case_id,
        fault_type=fault_type,
        http_status=http_status,
        latency_ms=round(latency_ms, 1),
        error_detail=error_detail or error_message,
    )

    mark_reporting(request_id)
    try:
        summary = generate_live_report()
    except Exception as error:
        logger.exception("장애 대화 보고서 갱신 실패: %s", error)
        mark_failed(request_id, str(error))
        return {"request_id": request_id, "report_ok": False, "report_error": str(error)}
    mark_completed(request_id, summary)
    return {"request_id": request_id, "report_ok": True, "report_summary": summary}
