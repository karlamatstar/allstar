from __future__ import annotations

import asyncio
import json
import os
import socket
import time
import uuid
from datetime import datetime

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException

from allstar.shared.model_profiles import get_profile, missing_keys, public_profiles
from allstar.voc.api import judge, log_store
from allstar.voc.api.metrics import (
    initialize_metric_series,
    metrics_app,
    voc_chat_last_activity,
    voc_chat_latency,
    voc_chat_total,
    voc_judge_duration,
    voc_judge_score,
    voc_judge_total,
    voc_judge_verdict_total,
)
from allstar.voc.api.report_generator import generate_live_report
from allstar.voc.api.runtime import PipelineRunner
from allstar.voc.api.schemas import ChatAccepted, ChatRequest, JobStatus
from allstar.voc.evaluation.progress import (
    fail_active_stage,
    finish_case,
    finish_progress,
    initialize_progress,
    read_progress,
    set_stage,
    start_case,
)


load_dotenv()
app = FastAPI(title="VOC HTTP Gateway", version="0.1.0")
app.mount("/metrics", metrics_app)
initialize_metric_series()

_runner = PipelineRunner()
_jobs: dict[str, dict] = {}
_jobs_lock = asyncio.Lock()
AGENTS = {
    "interpreter": os.getenv("INTERPRETER_ENDPOINT", "127.0.0.1:6001"),
    "retriever": os.getenv("RETRIEVER_ENDPOINT", "127.0.0.1:6002"),
    "summarizer": os.getenv("SUMMARIZER_ENDPOINT", "127.0.0.1:6003"),
    "evaluator": os.getenv("EVALUATOR_ENDPOINT", "127.0.0.1:6004"),
    "critic": os.getenv("CRITIC_ENDPOINT", "127.0.0.1:6005"),
    "improver": os.getenv("IMPROVER_ENDPOINT", "127.0.0.1:6006"),
}
LIVE_CASE_ID = "LIVE"


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _endpoint_open(endpoint: str) -> bool:
    host, port_text = endpoint.rsplit(":", 1)
    try:
        with socket.create_connection((host, int(port_text)), timeout=0.25):
            return True
    except OSError:
        return False


def _record_chat_metrics(profile_id: str, status: str, elapsed_seconds: float) -> None:
    """한 VOC 요청의 최종 상태·처리시간·마지막 활동 시각을 한 번만 기록한다."""
    voc_chat_total.labels(status=status, profile=profile_id).inc()
    voc_chat_latency.labels(profile=profile_id).observe(elapsed_seconds)
    voc_chat_last_activity.labels(profile=profile_id).set_to_current_time()


async def _execute(request_id: str, request: ChatRequest) -> None:
    started = time.perf_counter()
    profile = get_profile(request.profile_id)
    initialize_progress(
        request_id,
        profile.profile_id,
        [{"case_id": LIVE_CASE_ID, "question": request.question, "category": "실시간 대화"}],
    )
    start_case(request_id, LIVE_CASE_ID)
    async with _jobs_lock:
        _jobs[request_id]["status"] = "processing"
        _jobs[request_id]["current_stage"] = "VOC 6단계 파이프라인"
    try:
        result = await _runner.run(
            request.question,
            profile,
            progress_run_id=request_id,
            progress_case_id=LIVE_CASE_ID,
        )
        answer = result.get("policy") or result.get("summary") or ""
        pipeline_elapsed = round(time.perf_counter() - started, 3)
        result_with_answer = {**result, "answer": answer}
        async with _jobs_lock:
            _jobs[request_id]["result"] = result_with_answer

        if result.get("outcome") == "no_data":
            user_message = (
                "현재 등록된 VOC 데이터에서 관련 내용을 찾을 수 없습니다. "
                "보험 VOC의 불편 사항, 원인 분석 또는 개선 방안과 관련된 표현으로 다시 질문해 주세요."
            )
            result_with_answer["answer"] = user_message
            async with _jobs_lock:
                _jobs[request_id].update({
                    "status": "no_data",
                    "current_stage": "관련 데이터 없음",
                    "finished_at": _now(),
                    "elapsed_seconds": pipeline_elapsed,
                    "result": result_with_answer,
                    "judge": None,
                    "error": None,
                })
            finish_case(request_id, LIVE_CASE_ID, "no_data")
            finish_progress(request_id, "no_data")
            _record_chat_metrics(profile.profile_id, "no_data", pipeline_elapsed)
            return

        if not result.get("ok"):
            raise RuntimeError(result.get("trace") or "VOC 파이프라인이 실패했습니다.")

        async with _jobs_lock:
            _jobs[request_id]["current_stage"] = "LLM Judge"
        set_stage(request_id, LIVE_CASE_ID, 7, "running", "독립 LLM Judge 채점 진행 중")

        judge_result = None
        judge_error = None
        judge_started = time.perf_counter()
        try:
            judge_result = await judge.evaluate(
                request.question,
                result_with_answer,
                profile.judge,
                elapsed_seconds=pipeline_elapsed,
            )
            set_stage(request_id, LIVE_CASE_ID, 7, "done", "9항목·100점 독립 채점 완료")
            voc_judge_total.labels(status="success", profile=profile.profile_id).inc()
            verdict = str(judge_result.get("verdict") or "N/A")
            voc_judge_verdict_total.labels(verdict=verdict, profile=profile.profile_id).inc()
            total_score = judge_result.get("total")
            if isinstance(total_score, (int, float)):
                voc_judge_score.labels(profile=profile.profile_id).observe(total_score)
            log_store.judgment({
                "schema_version": 2,
                "request_id": request_id,
                "timestamp": _now(),
                "profile_id": profile.profile_id,
                "profile": profile.snapshot(),
                "judge": judge_result,
            })
        except Exception as error:
            judge_error = str(error)
            set_stage(request_id, LIVE_CASE_ID, 7, "failed", f"독립 채점 실패: {judge_error}")
            voc_judge_total.labels(status="error", profile=profile.profile_id).inc()
            voc_judge_verdict_total.labels(verdict="N/A", profile=profile.profile_id).inc()
        finally:
            voc_judge_duration.labels(profile=profile.profile_id).observe(
                time.perf_counter() - judge_started
            )

        elapsed = round(time.perf_counter() - started, 3)
        async with _jobs_lock:
            _jobs[request_id].update({
                "status": "completed",
                "current_stage": "완료",
                "finished_at": _now(),
                "elapsed_seconds": elapsed,
                "judge": judge_result,
                "error": f"Judge 실패: {judge_error}" if judge_error else None,
            })
        _record_chat_metrics(profile.profile_id, "success", elapsed)
        finish_case(request_id, LIVE_CASE_ID, "completed")
        finish_progress(request_id, "completed")
    except Exception as error:
        elapsed = round(time.perf_counter() - started, 3)
        fail_active_stage(request_id, LIVE_CASE_ID, str(error))
        finish_progress(request_id, "failed", str(error))
        async with _jobs_lock:
            _jobs[request_id].update({
                "status": "failed",
                "current_stage": "실패",
                "finished_at": _now(),
                "elapsed_seconds": elapsed,
                "error": str(error),
            })
        _record_chat_metrics(profile.profile_id, "error", elapsed)
    finally:
        async with _jobs_lock:
            row = dict(_jobs[request_id])
        log_store.conversation({
            "schema_version": 2,
            "request_id": request_id,
            "timestamp": row["started_at"],
            "finished_at": row.get("finished_at"),
            "question": request.question,
            "profile_id": profile.profile_id,
            "profile": profile.snapshot(),
            "status": row["status"],
            "elapsed_seconds": row.get("elapsed_seconds", 0),
            "result": row.get("result"),
            "judge": row.get("judge"),
            "error": row.get("error"),
        })
        # 대시보드의 VOC 챗봇 보고서는 수동 버튼을 누르지 않아도 매 질문마다
        # 최신 대화 로그를 기준으로 자동 갱신한다. 보고서 생성 실패가 이미 완료된
        # 챗봇 응답 자체를 실패로 바꾸면 안 되므로 오류는 실행 상태에만 보조 기록한다.
        try:
            generate_live_report()
        except Exception as report_error:
            async with _jobs_lock:
                existing = _jobs[request_id].get("error")
                note = f"보고서 자동 갱신 실패: {report_error}"
                _jobs[request_id]["error"] = f"{existing}; {note}" if existing else note


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "voc-api"}


@app.get("/agents/health")
def agents_health() -> dict:
    return {
        name: {"endpoint": endpoint, "ready": _endpoint_open(endpoint)}
        for name, endpoint in AGENTS.items()
    }


@app.get("/profiles")
def model_profiles() -> list[dict]:
    rows = []
    for value in public_profiles():
        profile = get_profile(value["profile_id"])
        rows.append({**value, "available": not missing_keys(profile), "missing_keys": missing_keys(profile)})
    return rows


def _progress_status(request_id: str) -> dict:
    progress = read_progress(request_id) or {}
    case = next(
        (row for row in progress.get("cases", []) if row.get("case_id") == LIVE_CASE_ID),
        None,
    )
    if not case:
        return {}
    stages = case.get("stages", [])
    running = next((stage for stage in stages if stage.get("state") == "running"), None)
    return {
        "stage_states": [stage.get("state", "pending") for stage in stages],
        "stage_details": [stage.get("detail") for stage in stages],
        "progress_current_stage": running.get("name") if running else None,
    }


@app.post("/chat", response_model=ChatAccepted, status_code=202)
async def chat(request: ChatRequest, background_tasks: BackgroundTasks) -> ChatAccepted:
    profile = get_profile(request.profile_id)
    unavailable = missing_keys(profile)
    if unavailable and os.getenv("VOC_ALLOW_MISSING_KEYS", "false").lower() != "true":
        raise HTTPException(503, f"필수 API 키가 없습니다: {', '.join(unavailable)}")
    request_id = uuid.uuid4().hex
    now = _now()
    async with _jobs_lock:
        _jobs[request_id] = {
            "request_id": request_id,
            "status": "queued",
            "current_stage": "대기",
            "profile_id": profile.profile_id,
            "profile": profile.snapshot(),
            "started_at": now,
            "finished_at": None,
            "elapsed_seconds": 0.0,
            "result": None,
            "judge": None,
            "error": None,
        }
    background_tasks.add_task(_execute, request_id, request)
    return ChatAccepted(request_id=request_id, status="queued", profile_id=profile.profile_id)


@app.get("/chat/{request_id}/status", response_model=JobStatus)
async def chat_status(request_id: str) -> JobStatus:
    async with _jobs_lock:
        row = _jobs.get(request_id)
        if row is None:
            raise HTTPException(404, "요청을 찾을 수 없습니다.")
        data = dict(row)
    progress_status = _progress_status(request_id)
    data.update({key: value for key, value in progress_status.items() if key != "progress_current_stage"})
    if progress_status.get("progress_current_stage") and data.get("status") not in {"completed", "failed", "no_data"}:
        data["current_stage"] = progress_status["progress_current_stage"]
    if not data.get("finished_at"):
        started = datetime.fromisoformat(data["started_at"])
        data["elapsed_seconds"] = round((datetime.now().astimezone() - started).total_seconds(), 3)
    return JobStatus(**data)


@app.post("/reports/live/generate")
def create_live_report() -> dict:
    return generate_live_report()
