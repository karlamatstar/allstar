import json
from datetime import datetime

from allstar.voc.api import metrics


class _ChildGauge:
    def __init__(self, profile, values):
        self.profile = profile
        self.values = values

    def set(self, value):
        self.values[self.profile] = value


class _ProfileGauge:
    def __init__(self):
        self.values = {}

    def labels(self, *, profile):
        return _ChildGauge(profile, self.values)


def test_voc_last_activity_is_restored_per_profile(monkeypatch, tmp_path):
    conversation_dir = tmp_path / "conversations"
    conversation_dir.mkdir()
    rows = [
        {"profile_id": "A", "timestamp": "2026-07-17T10:00:00+09:00", "finished_at": "2026-07-17T10:00:05+09:00"},
        {"profile_id": "B", "timestamp": "2026-07-17T11:00:00+09:00", "finished_at": "2026-07-17T11:00:08+09:00"},
        {"profile_id": "A", "timestamp": "2026-07-18T09:00:00+09:00", "finished_at": "2026-07-18T09:00:12+09:00"},
    ]
    (conversation_dir / "2026-07-18.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    gauge = _ProfileGauge()
    monkeypatch.setattr(metrics, "voc_chat_last_activity", gauge)

    restored = metrics.restore_last_activity_from_logs(conversation_dir)

    assert restored == {
        "A": datetime.fromisoformat(rows[2]["finished_at"]).timestamp(),
        "B": datetime.fromisoformat(rows[1]["finished_at"]).timestamp(),
    }
    assert gauge.values == restored
