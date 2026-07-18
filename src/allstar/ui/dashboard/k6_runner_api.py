"""Streamlit과 분리된 K6·운영 시험 전용 내부 실행 API."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from allstar.shared.paths import PROJECT_ROOT
from allstar.ui.dashboard.k6_load_runner import (
    K6_MAX_DURATION,
    K6_MAX_VUS,
    K6_MIN_DURATION,
    K6_MIN_VUS,
    K6_TEST_SPEC_BY_ID,
    clear_finished_run,
    find_k6_executable,
    poll_current_run,
    read_k6_version,
    start_run,
    stop_current_run,
)


PORTFOLIO_API_URL = os.getenv("PORTFOLIO_API_URL", "http://portfolio-api:8000")


class RunRequest(BaseModel):
    test_id: str
    vus: int | None = Field(default=None, ge=K6_MIN_VUS, le=K6_MAX_VUS)
    duration: int | None = Field(default=None, ge=K6_MIN_DURATION, le=K6_MAX_DURATION)
    actual_api_confirmed: bool = False


def _relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve())


def _run_payload(run: Any) -> dict[str, Any] | None:
    if run is None:
        return None
    return {
        "test_id": run.spec.test_id,
        "run_id": run.run_id,
        "status": run.status,
        "finalized": run.finalized,
        "exit_code": run.exit_code,
        "settings": run.settings,
        "log_path": _relative(run.log_path),
        "elapsed_seconds": round(run.elapsed_seconds, 3),
    }


app = FastAPI(
    title="AllStar K6 전용 실행 서비스",
    description="허용된 AllStar 시험만 한 번에 하나씩 실행·중지하고 상태를 반환합니다.",
)


@app.get("/health")
def health() -> dict[str, Any]:
    executable = find_k6_executable()
    ok, version = read_k6_version(executable)
    run = poll_current_run()
    return {
        "ok": ok,
        "k6_version": version,
        "running": bool(run and not run.finalized),
        "allowed_tests": sorted(K6_TEST_SPEC_BY_ID),
    }


@app.post("/runs", status_code=201)
def create_run(request: RunRequest) -> dict[str, Any]:
    if request.test_id not in K6_TEST_SPEC_BY_ID:
        raise HTTPException(status_code=404, detail="허용되지 않은 시험입니다.")
    spec = K6_TEST_SPEC_BY_ID[request.test_id]
    if spec.actual_api and not request.actual_api_confirmed:
        raise HTTPException(status_code=403, detail="실제 AI API 호출과 비용 발생 가능성 확인이 필요합니다.")
    executable = find_k6_executable()
    ok, detail = read_k6_version(executable)
    if not ok or not executable:
        raise HTTPException(status_code=503, detail=f"K6 실행 준비 실패: {detail}")
    try:
        run = start_run(
            request.test_id,
            k6_executable=executable,
            portfolio_api=PORTFOLIO_API_URL,
            vus=request.vus,
            duration=request.duration,
            actual_api_confirmed=request.actual_api_confirmed,
        )
    except (RuntimeError, ValueError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"run": _run_payload(run)}


@app.get("/runs/current")
def get_current_run() -> dict[str, Any]:
    return {"run": _run_payload(poll_current_run())}


@app.post("/runs/current/stop")
def stop_run() -> dict[str, bool]:
    return {"stopped": stop_current_run()}


@app.delete("/runs/current")
def clear_run() -> dict[str, bool]:
    return {"cleared": clear_finished_run()}
