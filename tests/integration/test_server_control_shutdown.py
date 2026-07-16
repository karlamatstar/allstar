"""서버 관리 GUI 종료 시 프로젝트 서비스 정리 흐름을 검증한다."""

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LIFECYCLE_PATH = ROOT / "tools" / "server_control" / "lifecycle.py"
SPEC = importlib.util.spec_from_file_location("server_control_lifecycle", LIFECYCLE_PATH)
assert SPEC and SPEC.loader
lifecycle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lifecycle)


def test_launcher_starts_independent_shutdown_guard():
    launcher = (ROOT / "RUN" / "start_servers.bat").read_text(encoding="utf-8")
    assert "tools\\server_control\\shutdown_guard.py" in launcher
    assert "tools\\server_control\\main.py" not in launcher


def test_gui_registers_window_close_handler_and_clean_marker():
    source = (ROOT / "tools" / "server_control" / "main.py").read_text(encoding="utf-8")
    assert 'self.protocol("WM_DELETE_WINDOW", self.close_application)' in source
    assert "stop_project_services(ROOT, self.state_path, SHUTDOWN_LOG)" in source
    assert 'self.clean_marker.write_text("clean"' in source


def test_shutdown_stops_streamlit_tree_and_project_docker_services(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    log_path = tmp_path / "shutdown.log"
    state_path.write_text(json.dumps({"streamlit_pid": 1234}), encoding="utf-8")
    commands = []

    class Completed:
        returncode = 0
        stdout = "완료"

    def fake_run(command, **kwargs):
        commands.append((command, kwargs))
        return Completed()

    monkeypatch.setattr(lifecycle.subprocess, "run", fake_run)

    assert lifecycle.stop_project_services(ROOT, state_path, log_path) is True
    assert commands[0][0] == ["taskkill", "/PID", "1234", "/T", "/F"]
    assert commands[1][0] == ["docker", "compose", "stop"]
    assert commands[1][1]["cwd"] == ROOT
    assert "전체 서버 종료 완료" in log_path.read_text(encoding="utf-8")
