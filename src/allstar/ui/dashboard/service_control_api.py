"""Docker Streamlit에서 허용된 채팅 API 컨테이너만 제어하는 내부 브리지."""

from __future__ import annotations

import json
import os
import socket
import threading
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote

import httpx
from fastapi import FastAPI, HTTPException

from allstar.shared.paths import SERVICE_LOG_ROOT


DOCKER_SOCKET = os.getenv("DOCKER_SOCKET", "/var/run/docker.sock")
ALLOWED_SERVICES = frozenset({"portfolio-api", "voc-api"})
EVENT_LOG = Path(
    os.getenv("SERVICE_CONTROL_EVENT_LOG", SERVICE_LOG_ROOT / "service_control_events.jsonl")
)
_LOG_LOCK = threading.Lock()


def _record_event(event: str, **details: Any) -> None:
    payload = {
        "timestamp": datetime.now().astimezone().isoformat(timespec="milliseconds"),
        "event": event,
        **details,
    }
    EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with _LOG_LOCK:
        with EVENT_LOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _docker_request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    timeout: float = 20.0,
) -> httpx.Response:
    try:
        transport = httpx.HTTPTransport(uds=DOCKER_SOCKET)
        with httpx.Client(
            transport=transport,
            base_url="http://docker",
            timeout=timeout,
        ) as client:
            response = client.request(method, path, params=params)
    except (httpx.HTTPError, OSError) as error:
        raise RuntimeError(f"Docker Engine 연결 실패: {error}") from error
    if response.status_code >= 400 and response.status_code != 304:
        raise RuntimeError(
            f"Docker Engine 요청 실패: HTTP {response.status_code} {response.text.strip()}"
        )
    return response


def _docker_json(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    timeout: float = 20.0,
) -> Any:
    response = _docker_request(method, path, params=params, timeout=timeout)
    try:
        return response.json()
    except ValueError as error:
        raise RuntimeError("Docker Engine이 JSON이 아닌 응답을 반환했습니다.") from error


def _validate_service(service_name: str) -> str:
    if service_name not in ALLOWED_SERVICES:
        raise ValueError("허용되지 않은 채팅 서비스입니다.")
    return service_name


@lru_cache(maxsize=1)
def _project_name() -> str:
    configured = os.getenv("ALLSTAR_COMPOSE_PROJECT", "").strip()
    if configured:
        return configured
    container = _docker_json("GET", f"/containers/{quote(socket.gethostname(), safe='')}/json")
    labels = container.get("Config", {}).get("Labels", {}) if isinstance(container, dict) else {}
    project = str(labels.get("com.docker.compose.project") or "").strip()
    if not project:
        raise RuntimeError("현재 Compose 프로젝트 이름을 확인할 수 없습니다.")
    return project


def _find_container(service_name: str) -> dict[str, Any]:
    service = _validate_service(service_name)
    project = _project_name()
    filters = {
        "label": [
            f"com.docker.compose.project={project}",
            f"com.docker.compose.service={service}",
        ]
    }
    containers = _docker_json(
        "GET",
        "/containers/json",
        params={"all": "true", "filters": json.dumps(filters, separators=(",", ":"))},
    )
    matches = []
    for container in containers if isinstance(containers, list) else []:
        labels = container.get("Labels", {})
        if (
            labels.get("com.docker.compose.project") == project
            and labels.get("com.docker.compose.service") == service
            and labels.get("com.docker.compose.oneoff") != "True"
        ):
            matches.append(container)
    if len(matches) != 1:
        raise RuntimeError(f"{service} 컨테이너를 하나로 식별할 수 없습니다: {len(matches)}개")
    return matches[0]


def _service_state(service_name: str) -> dict[str, Any]:
    container = _find_container(service_name)
    container_id = str(container.get("Id") or "")
    detail = _docker_json("GET", f"/containers/{quote(container_id, safe='')}/json")
    state = detail.get("State", {}) if isinstance(detail, dict) else {}
    return {
        "service": service_name,
        "container_id": container_id[:12],
        "status": str(state.get("Status") or "unknown"),
        "running": bool(state.get("Running")),
    }


def _control_service(service_name: str, action: Literal["start", "stop"]) -> dict[str, Any]:
    service = _validate_service(service_name)
    container = _find_container(service)
    container_id = str(container.get("Id") or "")
    _record_event("service_control_requested", service=service, action=action)
    try:
        if action == "stop":
            response = _docker_request(
                "POST", f"/containers/{quote(container_id, safe='')}/stop", params={"t": 15}, timeout=20.0
            )
        else:
            response = _docker_request(
                "POST", f"/containers/{quote(container_id, safe='')}/start", timeout=20.0
            )
        state = _service_state(service)
        expected = action == "start"
        if state["running"] is not expected:
            raise RuntimeError(f"{action} 후 실제 컨테이너 상태가 일치하지 않습니다: {state['status']}")
    except Exception as error:
        _record_event("service_control_failed", service=service, action=action, error=str(error))
        raise
    _record_event(
        "service_control_completed",
        service=service,
        action=action,
        docker_status=response.status_code,
        container_status=state["status"],
    )
    return state


app = FastAPI(
    title="AllStar 채팅 서비스 제어 브리지",
    description="현재 Compose 프로젝트의 허용된 채팅 API만 시작·중단합니다.",
)


@app.get("/health")
def health() -> dict[str, Any]:
    try:
        ping = _docker_request("GET", "/_ping", timeout=3.0).text.strip()
        project = _project_name()
    except Exception as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return {"ok": ping == "OK", "project": project, "allowed_services": sorted(ALLOWED_SERVICES)}


@app.get("/services/{service_name}")
def get_service(service_name: str) -> dict[str, Any]:
    try:
        return _service_state(service_name)
    except ValueError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/services/{service_name}/{action}")
def control_service(service_name: str, action: str) -> dict[str, Any]:
    if action not in {"start", "stop"}:
        raise HTTPException(status_code=404, detail="허용되지 않은 제어 동작입니다.")
    try:
        return _control_service(service_name, action)
    except ValueError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
