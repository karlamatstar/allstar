from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path


CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


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


def stop_project_services(root: Path, state_path: Path, log_path: Path) -> bool:
    """남아 있는 Streamlit과 현재 프로젝트의 Docker Compose 서비스만 종료한다."""
    streamlit_pid = read_streamlit_pid(state_path)
    if streamlit_pid:
        terminate_process_tree(streamlit_pid, log_path)

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
