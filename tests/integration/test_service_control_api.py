from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from allstar.ui.dashboard import service_control_api as control


def test_container_lookup_requires_same_project_and_allowed_service(monkeypatch):
    monkeypatch.setenv("ALLSTAR_COMPOSE_PROJECT", "total")
    control._project_name.cache_clear()

    def fake_docker_json(method, path, **kwargs):
        assert method == "GET"
        assert path == "/containers/json"
        return [
            {
                "Id": "allowed-container-id",
                "Labels": {
                    "com.docker.compose.project": "total",
                    "com.docker.compose.service": "portfolio-api",
                    "com.docker.compose.oneoff": "False",
                },
            },
            {
                "Id": "other-project-id",
                "Labels": {
                    "com.docker.compose.project": "other",
                    "com.docker.compose.service": "portfolio-api",
                },
            },
        ]

    monkeypatch.setattr(control, "_docker_json", fake_docker_json)

    assert control._find_container("portfolio-api")["Id"] == "allowed-container-id"


def test_unknown_service_and_action_are_rejected(monkeypatch):
    client = TestClient(control.app)

    response = client.post("/services/grafana/stop")
    assert response.status_code == 403

    response = client.post("/services/portfolio-api/restart")
    assert response.status_code == 404


def test_docker_connection_error_is_exposed_as_runtime_error(monkeypatch):
    class BrokenClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def request(self, *args, **kwargs):
            raise httpx.ConnectError("socket unavailable")

    monkeypatch.setattr(control.httpx, "Client", BrokenClient)

    with pytest.raises(RuntimeError, match="Docker Engine 연결 실패"):
        control._docker_request("GET", "/_ping")


def test_api_returns_controlled_service_state(monkeypatch):
    monkeypatch.setattr(
        control,
        "_control_service",
        lambda service, action: {
            "service": service,
            "container_id": "123456789abc",
            "status": "exited" if action == "stop" else "running",
            "running": action == "start",
        },
    )
    client = TestClient(control.app)

    stopped = client.post("/services/portfolio-api/stop")
    started = client.post("/services/voc-api/start")

    assert stopped.status_code == 200 and stopped.json()["running"] is False
    assert started.status_code == 200 and started.json()["running"] is True


def test_compose_keeps_docker_socket_out_of_streamlit():
    root = Path(__file__).resolve().parents[2]
    compose = (root / "compose.yml").read_text(encoding="utf-8")
    streamlit_block = compose.split("  streamlit:", 1)[1].split("  voc-api:", 1)[0]
    control_block = compose.split("  service-control:", 1)[1].split("  streamlit:", 1)[0]

    assert "SERVICE_CONTROL_URL: http://service-control:8300" in streamlit_block
    assert "/var/run/docker.sock" not in streamlit_block
    assert "- /var/run/docker.sock:/var/run/docker.sock" in control_block
    assert "ports:" not in control_block
    assert "SERVICE_CONTROL_URL" not in control_block
    assert "requirements.service_control.txt" in (
        root / "ops" / "docker" / "Dockerfile.service_control"
    ).read_text(encoding="utf-8")
