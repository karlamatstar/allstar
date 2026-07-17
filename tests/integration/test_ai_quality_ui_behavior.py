from concurrent.futures import Future

from allstar.ui.dashboard import views


def _future(value):
    future = Future()
    future.set_result(value)
    return future


def test_completed_ai_chat_request_replaces_pending_with_two_answers(monkeypatch):
    session = {"ai_chat_pending": object()}
    monkeypatch.setattr(views.st, "session_state", session)
    monkeypatch.setattr(views, "_clear_ai_live_caches", lambda: None)
    history = []
    pending = {
        "future": _future({
            "ok": True,
            "body": {"answer": "API 답변", "rule_answer": "규칙 기반 답변"},
        })
    }

    assert views._complete_ai_chat_request(history, pending) is True
    assert [message["content"] for message in history] == ["API 답변", "규칙 기반 답변"]
    assert "ai_chat_pending" not in session


def test_incomplete_ai_chat_request_keeps_typing_state(monkeypatch):
    session = {"ai_chat_pending": object()}
    monkeypatch.setattr(views.st, "session_state", session)
    history = []

    assert views._complete_ai_chat_request(history, {"future": Future()}) is False
    assert history == []
    assert "ai_chat_pending" in session


def test_quality_page_callback_moves_within_nonnegative_range(monkeypatch):
    session = {"quality_page": 1}
    monkeypatch.setattr(views.st, "session_state", session)

    views._change_quality_page("quality_page", 1)
    assert session["quality_page"] == 2
    views._change_quality_page("quality_page", -5)
    assert session["quality_page"] == 0
