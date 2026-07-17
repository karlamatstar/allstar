from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path


CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def docker_ready(timeout: float = 3.0) -> bool:
    try:
        completed = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
            timeout=timeout,
            check=False,
        )
        return completed.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def ensure_docker_ready(log_path: Path, timeout: float = 120.0) -> bool:
    if docker_ready():
        return True
    append_shutdown_log(log_path, "Docker Desktop이 꺼져 있어 실행을 요청합니다.")
    try:
        completed = subprocess.run(
            ["docker", "desktop", "start", "--detach"],
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            creationflags=CREATE_NO_WINDOW,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        append_shutdown_log(log_path, f"Docker Desktop 실행 실패: {error}")
        return False
    if completed.returncode != 0:
        append_shutdown_log(log_path, f"Docker Desktop 실행 실패: {(completed.stdout or '').strip()}")
        return False

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if docker_ready():
            append_shutdown_log(log_path, "Docker Desktop 준비 완료")
            return True
        time.sleep(2)
    append_shutdown_log(log_path, "Docker Desktop 준비 시간 초과")
    return False


def stop_docker_desktop(log_path: Path) -> bool:
    if not docker_ready():
        return True
    try:
        completed = subprocess.run(
            ["docker", "desktop", "stop"],
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            creationflags=CREATE_NO_WINDOW,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        append_shutdown_log(log_path, f"Docker Desktop 종료 실패: {error}")
        return False
    if completed.stdout:
        append_shutdown_log(log_path, f"Docker Desktop 종료 결과: {completed.stdout.strip()}")
    return completed.returncode == 0


def running_non_project_containers(root: Path) -> list[str]:
    """현재 프로젝트에 속하지 않은 실행 중 컨테이너 이름을 반환한다."""
    if not docker_ready():
        return []
    try:
        project = subprocess.run(
            ["docker", "compose", "ps", "-q"],
            cwd=root,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
            timeout=15,
            check=False,
        )
        running = subprocess.run(
            ["docker", "ps", "--no-trunc", "--format", "{{.ID}}\t{{.Names}}"],
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    project_ids = {line.strip() for line in (project.stdout or "").splitlines() if line.strip()}
    others: list[str] = []
    for line in (running.stdout or "").splitlines():
        container_id, _, name = line.partition("\t")
        if container_id and container_id not in project_ids:
            others.append(name or container_id[:12])
    return others


def stop_project_and_docker(root: Path, state_path: Path, log_path: Path) -> bool:
    """현재 프로젝트 서비스를 정리한 다음 Docker Desktop까지 종료한다."""
    project_stopped = stop_project_services(root, state_path, log_path)
    docker_stopped = stop_docker_desktop(log_path)
    success = project_stopped and docker_stopped
    append_shutdown_log(log_path, "Docker 포함 전체 종료 완료" if success else "Docker 포함 전체 종료 중 오류 발생")
    return success


def append_shutdown_log(log_path: Path, message: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"[{timestamp}] {message}\n")


def read_streamlit_pid(state_path: Path) -> int | None:
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        pid = state.get("streamlit_pid")
        return int(pid) if pid else None
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def terminate_process_tree(pid: int, log_path: Path) -> bool:
    completed = subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        creationflags=CREATE_NO_WINDOW,
        check=False,
    )
    output = (completed.stdout or "").strip()
    if output:
        append_shutdown_log(log_path, f"Streamlit 종료 결과: {output}")
    return completed.returncode == 0


def listening_pids(port: int) -> set[int]:
    """Windows netstat에서 지정 포트를 수신 중인 PID를 찾는다."""
    try:
        completed = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return set()

    pids: set[int] = set()
    for line in (completed.stdout or "").splitlines():
        fields = line.split()
        if len(fields) < 5 or fields[0].upper() != "TCP":
            continue
        local_address, state, raw_pid = fields[1], fields[3].upper(), fields[4]
        if state != "LISTENING" or local_address.rsplit(":", 1)[-1] != str(port):
            continue
        try:
            pid = int(raw_pid)
        except ValueError:
            continue
        if pid > 4 and pid != os.getpid():
            pids.add(pid)
    return pids


def stop_project_services(root: Path, state_path: Path, log_path: Path) -> bool:
    """남아 있는 Streamlit과 현재 프로젝트의 Docker Compose 서비스만 종료한다."""
    streamlit_pid = read_streamlit_pid(state_path)
    streamlit_pids = listening_pids(8501)
    if streamlit_pid:
        streamlit_pids.add(streamlit_pid)
    for pid in sorted(streamlit_pids):
        terminate_process_tree(pid, log_path)

    if not docker_ready():
        append_shutdown_log(log_path, "Docker Desktop이 이미 꺼져 있어 Docker 서비스 종료를 생략합니다.")
        append_shutdown_log(log_path, "전체 서버 종료 완료")
        return True

    try:
        completed = subprocess.run(
            ["docker", "compose", "stop"],
            cwd=root,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            creationflags=CREATE_NO_WINDOW,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        append_shutdown_log(log_path, f"Docker 서비스 종료 실패: {error}")
        return False

    output = (completed.stdout or "").strip()
    if output:
        append_shutdown_log(log_path, f"Docker 서비스 종료 결과:\n{output}")
    success = completed.returncode == 0
    append_shutdown_log(log_path, "전체 서버 종료 완료" if success else f"Docker 종료 코드: {completed.returncode}")
    return success
