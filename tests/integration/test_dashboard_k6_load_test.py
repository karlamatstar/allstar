from pathlib import Path

import pytest

from allstar.ui.dashboard import k6_load_runner as runner


@pytest.fixture(autouse=True)
def reset_runner():
    runner.reset_runner_for_tests()
    yield
    runner.reset_runner_for_tests()


def test_k6_dashboard_specs_keep_requested_order_and_defaults():
    assert [spec.test_id for spec in runner.K6_TEST_SPECS] == [
        "ai_smoke",
        "ai_load",
        "ai_random",
        "ai_stress",
        "ai_spike",
        "ai_validation",
        "ai_api_performance",
    ]
    defaults = {
        spec.test_id: (spec.default_vus, spec.default_duration)
        for spec in runner.K6_TEST_SPECS
    }
    assert defaults["ai_load"] == (20, 60)
    assert defaults["ai_random"] == (100, 60)
    assert defaults["ai_stress"] == (100, 120)
    assert defaults["ai_spike"] == (200, 60)
    assert runner.K6_TEST_SPEC_BY_ID["ai_api_performance"].actual_api is True
    assert runner.K6_TEST_SPEC_BY_ID["ai_validation"].actual_api is False


def test_find_k6_prefers_current_operating_system_run_binary(tmp_path, monkeypatch):
    run_dir = tmp_path / "RUN"
    run_dir.mkdir()
    expected = run_dir / ("k6.exe" if runner.os.name == "nt" else "k6")
    expected.write_bytes(b"placeholder")
    monkeypatch.setattr(runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(runner.shutil, "which", lambda _name: "system-k6")

    assert runner.find_k6_executable() == str(expected)


def test_environment_requires_k6_api_and_prometheus_but_not_grafana(monkeypatch):
    monkeypatch.setattr(runner, "find_k6_executable", lambda: "k6")
    monkeypatch.setattr(runner, "read_k6_version", lambda _path: (True, "k6 v2.1.0"))

    def probe(url, expected_text=None):
        if "3000" in url:
            return False, "연결 거부"
        return True, "HTTP 200"

    monkeypatch.setattr(runner, "probe_http", probe)
    status = runner.inspect_environment("http://localhost:8000", "http://localhost:3000")

    assert status["required_ready"] is True
    assert status["grafana"]["ok"] is False


def test_remote_runner_supplies_k6_state_and_run_snapshot(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "K6_RUNNER_URL", "http://k6-runner:8200")
    monkeypatch.setattr(runner, "PROJECT_ROOT", tmp_path)

    def request(method, path, **_kwargs):
        if path == "/health":
            return {"ok": True, "k6_version": "k6 v2.1.0"}
        if method == "POST":
            return {
                "run": {
                    "test_id": "ai_smoke",
                    "run_id": "remote-1",
                    "status": "running",
                    "finalized": False,
                    "exit_code": None,
                    "settings": {"실행 위치": "K6 전용 컨테이너"},
                    "log_path": "_OUTPUT/logs/qa/runs/ai_smoke/remote-1.log",
                    "elapsed_seconds": 1.5,
                }
            }
        return {"run": None}

    monkeypatch.setattr(runner, "_runner_request", request)
    monkeypatch.setattr(runner, "probe_http", lambda *_args, **_kwargs: (True, "HTTP 200"))

    status = runner.inspect_environment("http://portfolio-api:8000", "http://grafana:3000")
    started = runner.start_run(
        "ai_smoke",
        k6_executable="remote:k6-runner",
        portfolio_api="http://portfolio-api:8000",
    )

    assert status["execution_mode"] == "remote"
    assert status["k6"]["ok"] is True
    assert started.run_id == "remote-1"
    assert started.log_path == tmp_path / "_OUTPUT/logs/qa/runs/ai_smoke/remote-1.log"


def test_compose_separates_streamlit_and_k6_runner() -> None:
    compose = (Path(__file__).resolve().parents[2] / "compose.yml").read_text(encoding="utf-8")

    assert "  streamlit:" in compose
    assert "  k6-runner:" in compose
    assert "ops/docker/Dockerfile.streamlit" in compose
    assert "ops/docker/Dockerfile.k6_runner" in compose
    assert "K6_RUNNER_URL: http://k6-runner:8200" in compose
    assert "./_OUTPUT:/srv/app/_OUTPUT" in compose
    assert compose.count("./src/allstar/ai_agent/evaluation/test_cases.json:") >= 2
    assert compose.count("./src/allstar/voc/evaluation/test_cases.json:") >= 2
    assert "TEST_CASE_ARCHIVE_ROOT: /srv/app/_OUTPUT/archives/testcases" in compose


def test_invalid_load_values_are_rejected():
    assert runner.validate_load_settings("20", "60") == (20, 60)
    assert runner.validate_load_settings(0, 0) == (1, 10)
    assert runner.validate_load_settings(1000, 601) == (999, 600)
    with pytest.raises(ValueError, match="숫자로 입력"):
        runner.validate_load_settings("invalid", 60)


def test_actual_api_performance_requires_explicit_confirmation(monkeypatch):
    monkeypatch.setattr(runner, "K6_RUNNER_URL", "http://k6-runner:8200")
    monkeypatch.setattr(
        runner,
        "_runner_request",
        lambda *_args, **_kwargs: pytest.fail("확인 전에는 실행 서비스에 요청하면 안 됩니다."),
    )

    with pytest.raises(ValueError, match="비용 발생 가능성"):
        runner.start_run(
            "ai_api_performance",
            k6_executable="remote:k6-runner",
            portfolio_api="http://portfolio-api:8000",
        )


def test_failed_dashboard_run_keeps_previous_latest_summary(tmp_path, monkeypatch):
    sessions = []

    class FakeSession:
        def __init__(self, test_id, test_name, command, settings, write_summary_report):
            self.test_id = test_id
            self.test_name = test_name
            self.command = command
            self.settings = settings
            self.write_summary_report = write_summary_report
            self.run_id = "run-1"
            self.log_path = tmp_path / "run.log"
            self.finished = None
            sessions.append(self)

        def command_for_execution(self):
            return list(self.command)

        def start(self):
            self.log_path.write_text("시작\n", encoding="utf-8")

        def finish(self, status, exit_code, error=None):
            self.finished = (status, exit_code, self.write_summary_report)
            return {"status": status, "error": error}

        def append_output(self, text):
            with self.log_path.open("a", encoding="utf-8") as stream:
                stream.write(text)

    class FakeProcess:
        pid = 1234

        def __init__(self):
            self.returncode = None

        def poll(self):
            return self.returncode

    process = FakeProcess()
    monkeypatch.setattr(runner, "QAReportSession", FakeSession)
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *_args, **_kwargs: process)
    monkeypatch.setattr(runner, "PROJECT_ROOT", tmp_path)

    started = runner.start_run(
        "ai_validation",
        k6_executable="k6",
        portfolio_api="http://localhost:8000",
    )
    assert started.status == "running"
    process.returncode = 2
    finished = runner.poll_current_run()

    assert finished.status == "failed"
    assert sessions[0].finished == ("failed", 2, False)
    assert runner.clear_finished_run() is True
