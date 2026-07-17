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
        def __init__(self, stdout="완료"):
            self.returncode = 0
            self.stdout = stdout

    def fake_run(command, **kwargs):
        commands.append((command, kwargs))
        return Completed("") if command[0] == "netstat" else Completed()

    monkeypatch.setattr(lifecycle.subprocess, "run", fake_run)

    assert lifecycle.stop_project_services(ROOT, state_path, log_path) is True
    assert commands[0][0] == ["netstat", "-ano", "-p", "tcp"]
    assert commands[1][0] == ["taskkill", "/PID", "1234", "/T", "/F"]
    assert commands[2][0] == ["docker", "info", "--format", "{{.ServerVersion}}"]
    assert commands[3][0] == ["docker", "compose", "stop"]
    assert commands[3][1]["cwd"] == ROOT
    assert "전체 서버 종료 완료" in log_path.read_text(encoding="utf-8")


def test_streamlit_can_be_found_by_port_when_saved_pid_is_missing(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    log_path = tmp_path / "shutdown.log"
    state_path.write_text(json.dumps({"streamlit_pid": None}), encoding="utf-8")
    killed = []

    class Completed:
        returncode = 0
        stdout = ""

    def fake_run(command, **kwargs):
        if command[0] == "netstat":
            result = Completed()
            result.stdout = "  TCP    127.0.0.1:8501    0.0.0.0:0    LISTENING    4321\n"
            return result
        if command[0] == "taskkill":
            killed.append(command)
        return Completed()

    monkeypatch.setattr(lifecycle.subprocess, "run", fake_run)

    assert lifecycle.stop_project_services(ROOT, state_path, log_path) is True
    assert killed == [["taskkill", "/PID", "4321", "/T", "/F"]]


def test_server_control_status_refresh_and_docker_start_are_non_blocking_by_design():
    source = (ROOT / "tools" / "server_control" / "main.py").read_text(encoding="utf-8")

    assert '"컨테이너 실행 환경 (Docker Desktop)"' in source
    assert "ThreadPoolExecutor" in source
    assert "self.status_refresh_running" in source
    assert "ensure_docker_ready(SHUTDOWN_LOG)" in source
    assert "self.status_after_id" in source


def test_server_control_has_fixed_web_shortcuts_and_korean_docker_warning():
    source = (ROOT / "tools" / "server_control" / "main.py").read_text(encoding="utf-8")
    web_links_source = source[source.index("WEB_LINKS = ["):source.index("]\n\n\ndef port_open")]

    expected_labels = [
        "AI 상담 서버 기능 명세",
        "고객 의견 분석 서버 기능 명세",
        "통합 대시보드",
        "상태 정보 수집 (Prometheus)",
        "운영 상태 화면 (Grafana)",
    ]
    positions = [web_links_source.index(label) for label in expected_labels]
    assert positions == sorted(positions)
    assert "⚪ {label}" in source
    assert "🟢" in source
    assert "해당 서버를 먼저 시작한 뒤 다시 눌러주세요." in source
    assert "Docker Desktop이 꺼져 있습니다." in source
    assert "def open_selected" not in source


def test_top_actions_are_declared_refresh_start_server_stop_docker_stop_order():
    source = (ROOT / "tools" / "server_control" / "main.py").read_text(encoding="utf-8")
    action_specs = source[source.index("action_specs = ["):source.index("for label, command, color in action_specs")]
    labels = ["상태 새로고침", "전체 시작", "서버 전체 종료", "Docker 포함 전체 종료"]
    positions = [action_specs.index(f'"{label}"') for label in labels]
    assert positions == sorted(positions)
    assert "self.stop_all_with_docker" in action_specs
    assert '"#a32626"' in action_specs


def test_server_start_rebuilds_images_and_shutdown_keeps_docker_by_default():
    source = (ROOT / "tools" / "server_control" / "main.py").read_text(encoding="utf-8")

    assert '["docker", "compose", "up", "-d", "--build", *docker_services]' in source
    assert 'self._docker("up", "-d", "--build", key' in source
    assert "stop_project_services(ROOT, self.state_path, SHUTDOWN_LOG)" in source
    assert "Docker Desktop은 유지합니다." in source
    assert "stop_project_and_docker(ROOT, self.state_path, SHUTDOWN_LOG)" in source
    assert "AllStar 이외 실행 중 컨테이너" in source


def test_server_control_uses_roomy_default_and_minimum_window_sizes():
    source = (ROOT / "tools" / "server_control" / "main.py").read_text(encoding="utf-8")

    assert "DEFAULT_WINDOW_SIZE = (1440, 900)" in source
    assert "MINIMUM_WINDOW_SIZE = (1200, 820)" in source
    assert "LEFT_PANEL_WIDTH = 440" in source
    assert 'self.geometry(f"{width}x{height}+{x}+{y}")' in source
    assert "body.add(left, minsize=420)" in source
    assert "body.add(right, minsize=700)" in source


def test_docker_is_started_and_waited_for_when_engine_is_off(tmp_path, monkeypatch):
    log_path = tmp_path / "docker.log"
    ready_states = iter([False, False, True])
    commands = []

    class Completed:
        returncode = 0
        stdout = "시작 요청 완료"

    monkeypatch.setattr(lifecycle, "docker_ready", lambda: next(ready_states))
    monkeypatch.setattr(lifecycle.time, "sleep", lambda _seconds: None)

    def fake_run(command, **kwargs):
        commands.append(command)
        return Completed()

    monkeypatch.setattr(lifecycle.subprocess, "run", fake_run)

    assert lifecycle.ensure_docker_ready(log_path, timeout=10) is True
    assert commands == [["docker", "desktop", "start", "--detach"]]
    assert "Docker Desktop 준비 완료" in log_path.read_text(encoding="utf-8")


def test_non_project_container_detection(tmp_path, monkeypatch):
    class Completed:
        def __init__(self, stdout=""):
            self.returncode = 0
            self.stdout = stdout

    monkeypatch.setattr(lifecycle, "docker_ready", lambda: True)

    def fake_run(command, **_kwargs):
        if command[:4] == ["docker", "compose", "ps", "-q"]:
            return Completed("project-id\n")
        if command[:2] == ["docker", "ps"]:
            return Completed("project-id\ttotal-api-1\nother-id\tother-project-1\n")
        raise AssertionError(command)

    monkeypatch.setattr(lifecycle.subprocess, "run", fake_run)

    assert lifecycle.running_non_project_containers(tmp_path) == ["other-project-1"]


def test_docker_inclusive_shutdown_stops_project_first(tmp_path, monkeypatch):
    events = []
    log_path = tmp_path / "shutdown.log"
    monkeypatch.setattr(
        lifecycle,
        "stop_project_services",
        lambda root, state_path, path: (events.append("project") or True),
    )
    monkeypatch.setattr(
        lifecycle,
        "stop_docker_desktop",
        lambda path: (events.append("docker") or True),
    )

    assert lifecycle.stop_project_and_docker(tmp_path, tmp_path / "state.json", log_path) is True
    assert events == ["project", "docker"]
    assert "Docker 포함 전체 종료 완료" in log_path.read_text(encoding="utf-8")
