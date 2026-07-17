from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from allstar.shared.single_instance import DUPLICATE_INSTANCE_EXIT_CODE
from lifecycle import append_shutdown_log, stop_project_services


MAIN = Path(__file__).with_name("main.py")
RUNTIME_DIR = ROOT / "_OUTPUT" / "logs" / "services" / "runtime"
SHUTDOWN_LOG = ROOT / "_OUTPUT" / "logs" / "services" / "shutdown_guard.log"
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


def run() -> int:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    guard_id = os.getpid()
    state_path = RUNTIME_DIR / f"server_control_{guard_id}.json"
    clean_marker = RUNTIME_DIR / f"server_control_{guard_id}.clean"
    env = os.environ.copy()
    env["ALLSTAR_SERVER_STATE"] = str(state_path)
    env["ALLSTAR_SERVER_CLEAN_MARKER"] = str(clean_marker)
    env["ALLSTAR_SERVER_GUARDED"] = "1"

    append_shutdown_log(SHUTDOWN_LOG, f"종료 감시 시작: guard={guard_id}")
    state_path.write_text(
        '{"gui_pid": null, "streamlit_pid": null}',
        encoding="utf-8",
    )
    try:
        gui = subprocess.Popen(
            [sys.executable, str(MAIN)],
            cwd=ROOT,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP,
        )
        exit_code = gui.wait()
        if exit_code == DUPLICATE_INSTANCE_EXIT_CODE:
            append_shutdown_log(SHUTDOWN_LOG, f"중복 실행 차단: gui={gui.pid}")
        elif clean_marker.exists():
            append_shutdown_log(SHUTDOWN_LOG, f"정상 종료 확인: gui={gui.pid}")
        else:
            append_shutdown_log(SHUTDOWN_LOG, f"비정상 종료 감지: gui={gui.pid}, code={exit_code}")
            stop_project_services(ROOT, state_path, SHUTDOWN_LOG)
        return exit_code
    except Exception as error:
        append_shutdown_log(SHUTDOWN_LOG, f"종료 감시 오류: {error}")
        stop_project_services(ROOT, state_path, SHUTDOWN_LOG)
        return 1
    finally:
        state_path.unlink(missing_ok=True)
        clean_marker.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(run())
