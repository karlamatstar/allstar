"""VOC A~D 배치 실행의 테스트케이스별 7단계 진행 상태를 공유한다."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from allstar.shared.paths import VOC_LOG_ROOT


STAGE_NAMES = [
    "Interpreter",
    "Retriever",
    "Summarizer",
    "Evaluator",
    "Critic",
    "Improver",
    "LLM Judge",
]
PROGRESS_ROOT = VOC_LOG_ROOT / "progress"


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def progress_path(run_id: str) -> Path:
    return PROGRESS_ROOT / f"{run_id}.json"


def read_progress(run_id: str) -> dict[str, Any] | None:
    try:
        return json.loads(progress_path(run_id).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_progress(run_id: str, data: dict[str, Any]) -> None:
    path = progress_path(run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid4().hex}.tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _new_stages() -> list[dict[str, Any]]:
    return [
        {
            "index": index,
            "name": name,
            "state": "pending",
            "started_at": None,
            "finished_at": None,
            "detail": None,
        }
        for index, name in enumerate(STAGE_NAMES, start=1)
    ]


def initialize_progress(run_id: str, profile_id: str, cases: list[dict[str, Any]]) -> Path:
    data = {
        "schema_version": 1,
        "run_id": run_id,
        "profile_id": profile_id,
        "status": "running",
        "started_at": _now_iso(),
        "finished_at": None,
        "current_case_id": None,
        "current_case_index": 0,
        "total_cases": len(cases),
        "error": None,
        "cases": [
            {
                "case_id": case["case_id"],
                "index": index,
                "question": case.get("question", ""),
                "category": case.get("category", ""),
                "status": "pending",
                "started_at": None,
                "finished_at": None,
                "stages": _new_stages(),
            }
            for index, case in enumerate(cases, start=1)
        ],
    }
    _write_progress(run_id, data)
    return progress_path(run_id)


def _update(run_id: str, change) -> None:
    data = read_progress(run_id)
    if not data:
        return
    change(data)
    _write_progress(run_id, data)


def start_case(run_id: str, case_id: str) -> None:
    def change(data: dict[str, Any]) -> None:
        for case in data["cases"]:
            if case["case_id"] == case_id:
                case["status"] = "running"
                case["started_at"] = case["started_at"] or _now_iso()
                data["current_case_id"] = case_id
                data["current_case_index"] = case["index"]
                return

    _update(run_id, change)


def set_stage(
    run_id: str,
    case_id: str,
    stage_index: int,
    state: str,
    detail: str | None = None,
) -> None:
    if state not in {"pending", "running", "done", "failed", "skipped"}:
        raise ValueError(f"지원하지 않는 단계 상태: {state}")

    def change(data: dict[str, Any]) -> None:
        for case in data["cases"]:
            if case["case_id"] != case_id:
                continue
            stage = case["stages"][stage_index - 1]
            stage["state"] = state
            if state == "running":
                stage["started_at"] = stage["started_at"] or _now_iso()
            if state in {"done", "failed", "skipped"}:
                stage["finished_at"] = _now_iso()
            if detail is not None:
                stage["detail"] = detail
            return

    _update(run_id, change)


def skip_stages(run_id: str, case_id: str, start_index: int, detail: str) -> None:
    for stage_index in range(start_index, len(STAGE_NAMES) + 1):
        set_stage(run_id, case_id, stage_index, "skipped", detail)


def finish_case(run_id: str, case_id: str, status: str = "completed") -> None:
    def change(data: dict[str, Any]) -> None:
        for case in data["cases"]:
            if case["case_id"] == case_id:
                case["status"] = status
                case["finished_at"] = _now_iso()
                return

    _update(run_id, change)


def fail_active_stage(run_id: str, case_id: str, detail: str) -> None:
    data = read_progress(run_id)
    if not data:
        return
    case = next((row for row in data["cases"] if row["case_id"] == case_id), None)
    if not case:
        return
    active = next((stage for stage in case["stages"] if stage["state"] == "running"), None)
    if active:
        set_stage(run_id, case_id, int(active["index"]), "failed", detail)
        skip_stages(run_id, case_id, int(active["index"]) + 1, "앞 단계 실패로 실행하지 않음")
    else:
        pending = next((stage for stage in case["stages"] if stage["state"] == "pending"), None)
        if pending:
            set_stage(run_id, case_id, int(pending["index"]), "failed", detail)
            skip_stages(run_id, case_id, int(pending["index"]) + 1, "앞 단계 실패로 실행하지 않음")
    finish_case(run_id, case_id, "failed")


def finish_progress(run_id: str, status: str, error: str | None = None) -> None:
    def change(data: dict[str, Any]) -> None:
        data["status"] = status
        data["finished_at"] = _now_iso()
        data["error"] = error

    _update(run_id, change)
