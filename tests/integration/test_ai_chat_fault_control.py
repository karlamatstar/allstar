from types import SimpleNamespace

import httpx

from allstar.ui.dashboard import ai_chat_fault_control as control


def test_stop_chat_server_records_real_connection_failure(monkeypatch):
    events = []
    recorded = []
    monkeypatch.setattr(control, "_running_inside_docker", lambda: False)
    monkeypatch.setattr(control, "_compose", lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""))
    monkeypatch.setattr(control, "chat_server_health", lambda *_args, **_kwargs: (False, "connection refused"))
    monkeypatch.setattr(control, "record_fault_event", lambda event, **details: events.append((event, details)))
    monkeypatch.setattr(
        control,
        "record_chat_fault",
        lambda **kwargs: recorded.append(kwargs) or {"request_id": "server-down-request", "report_ok": True},
    )

    def refused(*_args, **_kwargs):
        request = httpx.Request("POST", "http://localhost:8000/chat")
        raise httpx.ConnectError("actively refused", request=request)

    monkeypatch.setattr(control.httpx, "post", refused)

    result = control.stop_chat_server_and_record(
        question="질문",
        case_id="TC-001",
        api_url="http://localhost:8000",
    )

    assert result["server_down"] is True
    assert recorded[0]["fault_type"] == "server_down"
    assert recorded[0]["http_status"] is None
    assert any(event == "chat_server_stopped" for event, _details in events)


def test_reconnect_requires_health_200(monkeypatch):
    events = []
    monkeypatch.setattr(control, "_running_inside_docker", lambda: False)
    monkeypatch.setattr(control, "_compose", lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""))
    monkeypatch.setattr(control, "chat_server_health", lambda *_args, **_kwargs: (True, "HTTP 200"))
    monkeypatch.setattr(control, "record_fault_event", lambda event, **details: events.append((event, details)))

    result = control.reconnect_chat_server("http://localhost:8000")

    assert result == {"ok": True, "message": "채팅 서버 재접속 완료", "health": "HTTP 200"}
    assert events[-1][0] == "chat_server_reconnected"


def test_voc_reconnect_starts_only_voc_chat_service_without_fault_event(monkeypatch):
    commands = []
    monkeypatch.setattr(control, "_running_inside_docker", lambda: False)
    monkeypatch.setattr(
        control,
        "_compose",
        lambda *args, **kwargs: commands.append(args) or SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    monkeypatch.setattr(control, "chat_server_health", lambda *_args, **_kwargs: (True, "HTTP 200"))
    monkeypatch.setattr(
        control,
        "record_fault_event",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("VOC 재접속은 장애 시험 로그가 아님")),
    )

    result = control.reconnect_voc_chat_server("http://localhost:8100")

    assert commands == [("up", "-d", "voc-api")]
    assert result == {"ok": True, "message": "VOC 채팅 서버 재접속 완료", "health": "HTTP 200"}


def test_docker_streamlit_reconnect_uses_service_control_bridge(monkeypatch):
    calls = []
    monkeypatch.setattr(control, "SERVICE_CONTROL_URL", "http://service-control:8300")
    monkeypatch.setattr(
        control,
        "_change_service_state",
        lambda service, action, **kwargs: calls.append((service, action)) or (True, "running"),
    )
    monkeypatch.setattr(control, "chat_server_health", lambda *_args, **_kwargs: (True, "HTTP 200"))
    monkeypatch.setattr(control, "record_fault_event", lambda *_args, **_kwargs: None)

    result = control.reconnect_chat_server("http://portfolio-api:8000")

    assert calls == [("portfolio-api", "start")]
    assert result["ok"] is True
