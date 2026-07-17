"""AI Agent 백그라운드 채점·보고서 작성 상태를 공유 파일로 관리한다."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from allstar.shared.paths import AI_AGENT_REPORT_ROOT


STATUS_PATH = AI_AGENT_REPORT_ROOT / "live" / "report_status.json"
STATUS_LOCK = threading.Lock()
ACTIVE_STATES = {"PENDING", "EVALUATING", "REPORTING"}
TERMINAL_STATES = {"COMPLETED", "FAILED"}
MAX_JOBS = 100
STALE_AFTER = timedelta(minutes=10)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_unlocked() -> dict[str, Any]:
    try:
        data = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {"updated_at": None, "jobs": {}}
    if not isinstance(data.get("jobs"), dict):
        data["jobs"] = {}
    return data


def _write_unlocked(data: dict[str, Any]) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = _utc_now()
    jobs = sorted(
        data.get("jobs", {}).items(),
        key=lambda item: str(item[1].get("updated_at") or ""),
        reverse=True,
    )[:MAX_JOBS]
    data["jobs"] = dict(jobs)
    temporary = STATUS_PATH.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(STATUS_PATH)


def _update(request_id: str, state: str, message: str, **extra: Any) -> None:
    now = _utc_now()
    with STATUS_LOCK:
        data = _read_unlocked()
        previous = data["jobs"].get(request_id, {})
        job = {
            **previous,
            "request_id": request_id,
            "state": state,
            "message": message,
            "started_at": previous.get("started_at") or now,
            "updated_at": now,
            **extra,
        }
        if state in TERMINAL_STATES:
            job["completed_at"] = now
        data["jobs"][request_id] = job
        _write_unlocked(data)


def mark_pending(request_id: str) -> None:
    _update(request_id, "PENDING", "독립 품질평가를 기다리고 있습니다.", completed=0, total=2)


def mark_evaluating(request_id: str, completed: int, message: str) -> None:
    _update(request_id, "EVALUATING", message, completed=completed, total=2)


def mark_reporting(request_id: str) -> None:
    _update(request_id, "REPORTING", "새로운 품질 보고서를 작성 중입니다.", completed=2, total=2)


def mark_completed(request_id: str, summary: dict[str, Any] | None = None) -> None:
    _update(
        request_id,
        "COMPLETED",
        "새로운 품질 보고서가 반영되었습니다.",
        completed=2,
        total=2,
        report_summary=summary or {},
    )


def mark_failed(request_id: str, error: str) -> None:
    _update(
        request_id,
        "FAILED",
        "품질 보고서 작성에 실패했습니다. 채점 로그는 보존되었습니다.",
        error=error,
    )


def read_status(path: Path | None = None) -> dict[str, Any]:
    target = path or STATUS_PATH
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"updated_at": None, "jobs": {}, "active_count": 0, "latest": None}

    jobs = data.get("jobs", {}) if isinstance(data.get("jobs"), dict) else {}
    now = datetime.now(timezone.utc)
    changed = False
    for job in jobs.values():
        if job.get("state") not in ACTIVE_STATES:
            continue
        try:
            updated = datetime.fromisoformat(str(job.get("updated_at")))
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue
        if now - updated > STALE_AFTER:
            job["state"] = "FAILED"
            job["message"] = "백그라운드 작업 상태가 오래 갱신되지 않았습니다."
            job["error"] = "상태 갱신 시간 초과"
            job["completed_at"] = _utc_now()
            changed = True

    if changed and target == STATUS_PATH:
        with STATUS_LOCK:
            _write_unlocked(data)

    ordered = sorted(jobs.values(), key=lambda job: str(job.get("updated_at") or ""), reverse=True)
    active = [job for job in ordered if job.get("state") in ACTIVE_STATES]
    return {
        **data,
        "jobs": jobs,
        "active_count": len(active),
        "active_jobs": active,
        "latest": ordered[0] if ordered else None,
    }
