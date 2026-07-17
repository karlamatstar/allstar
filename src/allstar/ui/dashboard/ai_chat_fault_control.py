"""통합 대시보드에서 AI 채팅 서버 하나만 실제 중단·복구하는 장애 시험 도구."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx

from allstar.ai_agent.evaluation.live_faults import record_chat_fault, record_fault_event
from allstar.shared.paths import PROJECT_ROOT


CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
SERVICE_NAME = "portfolio-api"
VOC_SERVICE_NAME = "voc-api"


def chat_server_health(api_url: str, timeout: float = 1.0) -> tuple[bool, str]:
    try:
        response = httpx.get(f"{api_url.rstrip('/')}/health", timeout=timeout)
    except httpx.HTTPError as error:
        return False, str(error)
    return response.status_code == 200, f"HTTP {response.status_code}"


def _compose(*arguments: str, timeout: float = 60.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", *arguments],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=CREATE_NO_WINDOW,
        check=False,
    )


def stop_chat_server_and_record(
    *, question: str,
    case_id: str | None,
    api_url: str,
) -> dict[str, Any]:
    """portfolio-api를 실제 종료하고 연결 실패를 일반 챗봇 N/A 로그로 남긴다."""
    if Path("/.dockerenv").exists():
        return {
            "ok": False,
            "error": "Docker 내부 Streamlit에서는 호스트 채팅 서버를 직접 중단할 수 없습니다.",
        }

    started = time.perf_counter()
    record_fault_event("chat_server_stop_requested", service=SERVICE_NAME, case_id=case_id)
    try:
        completed = _compose("stop", SERVICE_NAME)
    except (OSError, subprocess.TimeoutExpired) as error:
        record_fault_event("chat_server_stop_failed", service=SERVICE_NAME, error=str(error))
        return {"ok": False, "error": f"채팅 서버 중단 명령 실패: {error}"}
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "원인 없음").strip()
        record_fault_event("chat_server_stop_failed", service=SERVICE_NAME, error=detail)
        return {"ok": False, "error": f"채팅 서버를 중단하지 못했습니다: {detail}"}

    deadline = time.monotonic() + 15.0
    health_detail = ""
    while time.monotonic() < deadline:
        healthy, health_detail = chat_server_health(api_url, timeout=0.7)
        if not healthy:
            break
        time.sleep(0.4)
    else:
        record_fault_event("chat_server_stop_failed", service=SERVICE_NAME, error="Health가 계속 정상임")
        return {"ok": False, "error": "중단 명령 후에도 채팅 서버 Health가 계속 정상입니다."}

    try:
        response = httpx.post(
            f"{api_url.rstrip('/')}/chat",
            json={"question": question},
            timeout=httpx.Timeout(2.0, connect=1.0),
        )
        response.raise_for_status()
    except httpx.HTTPError as error:
        connection_error = str(error)
    else:
        detail = "서버 종료 후 요청이 예상과 달리 성공했습니다."
        record_fault_event("chat_server_stop_failed", service=SERVICE_NAME, error=detail)
        return {"ok": False, "error": detail}

    latency_ms = (time.perf_counter() - started) * 1000
    message = "채팅 서버가 중단되어 질문에 답할 수 없습니다. 재접속 후 다시 시도해 주세요."
    result = record_chat_fault(
        question=question,
        case_id=case_id,
        fault_type="server_down",
        error_message=message,
        latency_ms=latency_ms,
        http_status=None,
        error_detail=connection_error or health_detail,
    )
    record_fault_event(
        "chat_server_stopped",
        service=SERVICE_NAME,
        request_id=result["request_id"],
        case_id=case_id,
        latency_ms=round(latency_ms, 1),
        connection_error=connection_error,
    )
    return {
        "ok": False,
        "fault": True,
        "server_down": True,
        "fault_type": "server_down",
        "status_code": None,
        "error": message,
        "request_id": result["request_id"],
        "report_updated": result.get("report_ok", False),
    }


def reconnect_chat_service(
    api_url: str,
    *,
    service_name: str,
    server_label: str,
    timeout: float = 45.0,
    record_events: bool = False,
) -> dict[str, Any]:
    """지정한 Docker 채팅 서비스를 시작하고 Health 200까지 확인한다."""
    if Path("/.dockerenv").exists():
        return {
            "ok": False,
            "error": f"Docker 내부 Streamlit에서는 호스트 {server_label}를 직접 재접속할 수 없습니다.",
        }
    if record_events:
        record_fault_event("chat_server_reconnect_requested", service=service_name)
    try:
        completed = _compose("up", "-d", service_name, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as error:
        if record_events:
            record_fault_event("chat_server_reconnect_failed", service=service_name, error=str(error))
        return {"ok": False, "error": f"{server_label} 시작 명령 실패: {error}"}
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "원인 없음").strip()
        if record_events:
            record_fault_event("chat_server_reconnect_failed", service=service_name, error=detail)
        return {"ok": False, "error": f"{server_label} 시작 실패: {detail}"}

    deadline = time.monotonic() + timeout
    detail = ""
    while time.monotonic() < deadline:
        healthy, detail = chat_server_health(api_url, timeout=1.0)
        if healthy:
            if record_events:
                record_fault_event("chat_server_reconnected", service=service_name, health=detail)
            return {"ok": True, "message": f"{server_label} 재접속 완료", "health": detail}
        time.sleep(1.0)
    if record_events:
        record_fault_event("chat_server_reconnect_failed", service=service_name, error=detail or "Health 시간 초과")
    return {"ok": False, "error": f"{server_label} Health 확인 시간 초과: {detail or '응답 없음'}"}


def reconnect_chat_server(api_url: str, timeout: float = 45.0) -> dict[str, Any]:
    """AI 에이전트 채팅 서버를 복구하고 장애 이벤트를 기록한다."""
    return reconnect_chat_service(
        api_url,
        service_name=SERVICE_NAME,
        server_label="채팅 서버",
        timeout=timeout,
        record_events=True,
    )


def reconnect_voc_chat_server(api_url: str, timeout: float = 45.0) -> dict[str, Any]:
    """VOC 채팅 서버를 복구한다. 인위적 장애 시험 이벤트는 만들지 않는다."""
    return reconnect_chat_service(
        api_url,
        service_name=VOC_SERVICE_NAME,
        server_label="VOC 채팅 서버",
        timeout=timeout,
        record_events=False,
    )
