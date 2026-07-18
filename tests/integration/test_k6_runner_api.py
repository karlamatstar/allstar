from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from allstar.ui.dashboard import k6_runner_api as api


CLIENT = TestClient(api.app)


def test_runner_rejects_unknown_and_unconfirmed_actual_api_test(monkeypatch) -> None:
    monkeypatch.setattr(api, "find_k6_executable", lambda: "/usr/local/bin/k6")
    monkeypatch.setattr(api, "read_k6_version", lambda _path: (True, "k6 v2.1.0"))

    assert CLIENT.post("/runs", json={"test_id": "unknown"}).status_code == 404
    response = CLIENT.post("/runs", json={"test_id": "ai_api_performance"})
    assert response.status_code == 403
    assert "비용 발생 가능성" in response.json()["detail"]


def test_runner_returns_whitelisted_run_snapshot(monkeypatch, tmp_path: Path) -> None:
    log_path = tmp_path / "smoke.log"
    log_path.write_text("실행 중", encoding="utf-8")
    fake = SimpleNamespace(
        spec=api.K6_TEST_SPEC_BY_ID["ai_smoke"],
        run_id="runner-1",
        status="running",
        finalized=False,
        exit_code=None,
        settings={"실행 위치": "K6 전용 컨테이너"},
        log_path=log_path,
        elapsed_seconds=1.25,
    )
    monkeypatch.setattr(api, "find_k6_executable", lambda: "/usr/local/bin/k6")
    monkeypatch.setattr(api, "read_k6_version", lambda _path: (True, "k6 v2.1.0"))
    monkeypatch.setattr(api, "start_run", lambda *_args, **_kwargs: fake)

    response = CLIENT.post("/runs", json={"test_id": "ai_smoke"})

    assert response.status_code == 201
    payload = response.json()["run"]
    assert payload["test_id"] == "ai_smoke"
    assert payload["run_id"] == "runner-1"
    assert payload["settings"]["실행 위치"] == "K6 전용 컨테이너"
