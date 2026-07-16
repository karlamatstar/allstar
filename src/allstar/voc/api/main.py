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
from allstar.voc.api.metrics import metrics_app, voc_chat_latency, voc_chat_total, voc_judge_total
from allstar.voc.api.report_generator import generate_live_report
from allstar.voc.api.runtime import PipelineRunner
from allstar.voc.api.schemas import ChatAccepted, ChatRequest, JobStatus


load_dotenv()
app = FastAPI(title="VOC HTTP Gateway", version="0.1.0")
app.mount("/metrics", metrics_app)

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


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _endpoint_open(endpoint: str) -> bool:
    host, port_text = endpoint.rsplit(":", 1)
    try:
        with socket.create_connection((host, int(port_text)), timeout=0.25):
            return True
    except OSError:
        return False


async def _execute(request_id: str, request: ChatRequest) -> None:
    started = time.perf_counter()
    profile = get_profile(request.profile_id)
    async with _jobs_lock:
        _jobs[request_id]["status"] = "processing"
        _jobs[request_id]["current_stage"] = "VOC 6단계 파이프라인"
    try:
        result = await _runner.run(request.question, profile)
        answer = result.get("policy") or result.get("summary") or ""
        if not result.get("ok"):
            raise RuntimeError(result.get("trace") or "VOC 파이프라인이 실패했습니다.")

        async with _jobs_lock:
            _jobs[request_id]["result"] = {**result, "answer": answer}
            _jobs[request_id]["current_stage"] = "LLM Judge"

        judge_result = None
        judge_error = None
        try:
            judge_result = await judge.evaluate(request.question, answer, profile.judge)
            voc_judge_total.labels(status="success", profile=profile.profile_id).inc()
            log_store.judgment({
                "schema_version": 1,
                "request_id": request_id,
                "timestamp": _now(),
                "profile_id": profile.profile_id,
                "profile": profile.snapshot(),
                "judge": judge_result,
            })
        except Exception as error:
            judge_error = str(error)
            voc_judge_total.labels(status="error", profile=profile.profile_id).inc()

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
        voc_chat_total.labels(status="success", profile=profile.profile_id).inc()
        voc_chat_latency.labels(profile=profile.profile_id).observe(elapsed)
    except Exception as error:
        elapsed = round(time.perf_counter() - started, 3)
        async with _jobs_lock:
            _jobs[request_id].update({
                "status": "failed",
                "current_stage": "실패",
                "finished_at": _now(),
                "elapsed_seconds": elapsed,
                "error": str(error),
            })
        voc_chat_total.labels(status="error", profile=profile.profile_id).inc()
    finally:
        async with _jobs_lock:
            row = dict(_jobs[request_id])
        log_store.conversation({
            "schema_version": 1,
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
    if not data.get("finished_at"):
        started = datetime.fromisoformat(data["started_at"])
        data["elapsed_seconds"] = round((datetime.now().astimezone() - started).total_seconds(), 3)
    return JobStatus(**data)


@app.post("/reports/live/generate")
def create_live_report() -> dict:
    return generate_live_report()
