"""AI Agent 실시간 품질 결함을 Markdown 리포트로 누적한다."""

from __future__ import annotations

import threading

from allstar.shared.paths import REPORT_ROOT

DEFECT_REPORT = REPORT_ROOT / "defects" / "chatbot" / "defect_report.md"
_LOCK = threading.Lock()


def log_defect_to_markdown(
    request_id: str,
    timestamp: str,
    question: str,
    evaluation: dict,
    model_name: str,
    judge_name: str,
) -> Path:
    """FAIL 또는 REVIEW 평가를 사람이 확인할 수 있는 리포트에 추가한다."""
    DEFECT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    decision = evaluation.get("overall_decision", "UNKNOWN")
    score = evaluation.get("total_score", "N/A")
    summary = evaluation.get("summary", "-")
    section = "\n".join([
        f"## {timestamp} · {decision}",
        "",
        f"- 요청 ID: `{request_id}`",
        f"- 대상 모델: `{model_name}`",
        f"- 평가 모델: `{judge_name}`",
        f"- 총점: `{score}`",
        f"- 질문: {question}",
        f"- 평가 요약: {summary}",
        "",
    ])
    with _LOCK:
        if not DEFECT_REPORT.exists():
            DEFECT_REPORT.write_text("# AI Agent 챗봇 품질 결함 리포트\n\n", encoding="utf-8")
        with DEFECT_REPORT.open("a", encoding="utf-8") as stream:
            stream.write(section)
    return DEFECT_REPORT
