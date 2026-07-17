import json
from datetime import datetime

from allstar.ai_agent.api import metrics


class _Gauge:
    value = None

    def set(self, value):
        self.value = value


class _CounterChild:
    def __init__(self, label, values):
        self.label = label
        self.values = values

    def inc(self, amount=1):
        self.values[self.label] = self.values.get(self.label, 0) + amount


class _LabeledCounter:
    def __init__(self):
        self.values = {}

    def labels(self, **labels):
        return _CounterChild(next(iter(labels.values())), self.values)


def test_ai_last_activity_is_restored_from_latest_conversation(monkeypatch, tmp_path):
    log_path = tmp_path / "conversations.jsonl"
    rows = [
        {"timestamp": "2026-07-17T10:00:00+00:00", "question": "이전 질문"},
        {"timestamp": "2026-07-18T01:02:03+00:00", "question": "장애 시험 질문"},
    ]
    log_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n손상된 줄\n",
        encoding="utf-8",
    )
    gauge = _Gauge()
    monkeypatch.setattr(metrics, "chat_last_activity_timestamp_seconds", gauge)

    restored = metrics.restore_last_activity_from_log(log_path)

    expected = datetime.fromisoformat(rows[-1]["timestamp"]).timestamp()
    assert restored == expected
    assert gauge.value == expected


def test_ai_last_activity_stays_unset_without_log(monkeypatch, tmp_path):
    gauge = _Gauge()
    monkeypatch.setattr(metrics, "chat_last_activity_timestamp_seconds", gauge)

    assert metrics.restore_last_activity_from_log(tmp_path / "missing.jsonl") is None
    assert gauge.value is None


def test_actual_and_forced_failures_restore_same_service_agent_counts(monkeypatch, tmp_path):
    log_path = tmp_path / "conversations.jsonl"
    rows = [
        {"status": "fallback", "question": "실제 API 장애"},
        {"status": "error", "fault": {"type": "http_503"}},
        {"status": "error", "fault": {"type": "server_down"}},
        {"status": "success", "question": "정상 대화"},
    ]
    log_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    retry = _LabeledCounter()
    unavailable = _LabeledCounter()
    chat_requests = _LabeledCounter()
    monkeypatch.setattr(metrics, "agent_retry_total", retry)
    monkeypatch.setattr(metrics, "agent_unavailable_total", unavailable)
    monkeypatch.setattr(metrics, "chat_requests_total", chat_requests)

    restored = metrics.restore_service_failure_metrics_from_log(log_path, retries_per_failure=3)

    assert restored == {"retry": 9, "unavailable": 3, "chat_error": 2, "chat_fallback": 1}
    assert retry.values == {"service_agent": 9}
    assert unavailable.values == {"service_agent": 3}
    assert chat_requests.values == {"error": 2, "fallback": 1}
