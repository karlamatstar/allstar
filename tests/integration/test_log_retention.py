import gzip
import json
from datetime import date, datetime, timezone
from pathlib import Path

from allstar.ai_agent.evaluation import log_retention as ai_retention
from allstar.ai_agent.api import metrics as ai_metrics
from allstar.ai_agent.evaluation import live_report_generator as ai_live_report
from allstar.shared import log_retention as retention
from allstar.voc.api import metrics as voc_metrics
from allstar.voc.evaluation import log_retention as voc_retention


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def test_daily_group_keeps_latest_five_activity_dates_and_reads_gzip(tmp_path, monkeypatch):
    monkeypatch.setattr(retention, "ARCHIVE_EVENT_LOG", tmp_path / "events.jsonl")
    conversations = tmp_path / "conversations"
    judgments = tmp_path / "judgments"
    faults = tmp_path / "faults"
    for day in range(1, 8):
        key = f"2026-01-{day:02d}"
        _write_jsonl(conversations / f"{key}.jsonl", [{"day": day}])
        if day % 2 == 0:
            _write_jsonl(judgments / f"{key}.jsonl", [{"judged_day": day}])

    archived = retention.compress_daily_groups(
        (conversations, judgments, faults),
        keep_recent=5,
        current_date=date(2026, 1, 20),
    )

    assert {path.name for path in archived} == {
        "2026-01-01.jsonl.gz",
        "2026-01-02.jsonl.gz",
    }
    assert not (conversations / "2026-01-01.jsonl").exists()
    assert (conversations / "2026-01-03.jsonl").exists()
    assert [row["day"] for row in retention.read_daily_jsonl(conversations)] == list(range(1, 8))


def test_five_old_activity_dates_stay_uncompressed_after_long_inactivity(tmp_path, monkeypatch):
    monkeypatch.setattr(retention, "ARCHIVE_EVENT_LOG", tmp_path / "events.jsonl")
    directory = tmp_path / "conversations"
    for day in (1, 3, 8, 10, 12):
        _write_jsonl(directory / f"2026-01-{day:02d}.jsonl", [{"day": day}])

    assert retention.compress_daily_groups(
        (directory,), keep_recent=5, current_date=date(2026, 12, 31)
    ) == []
    assert len(list(directory.glob("*.jsonl"))) == 5
    assert not list(directory.glob("*.gz"))


def test_legacy_ai_jsonl_migrates_by_korean_date_with_verified_backup(tmp_path, monkeypatch):
    monkeypatch.setattr(retention, "ARCHIVE_EVENT_LOG", tmp_path / "events.jsonl")
    directory = tmp_path / "conversations"
    legacy = directory / "conversations.jsonl"
    rows = [
        {"request_id": "late", "timestamp": "2026-01-01T15:01:00+00:00"},
        {"request_id": "early", "timestamp": "2026-01-02T02:00:00+00:00"},
    ]
    _write_jsonl(legacy, rows)

    manifest = retention.migrate_legacy_jsonl(legacy, directory)

    assert manifest and manifest["source_lines"] == 2
    assert not legacy.exists()
    assert (directory / "2026-01-02.jsonl").exists()
    assert (directory / "legacy" / "conversations.jsonl.gz").exists()
    assert retention.read_daily_jsonl(directory) == rows
    assert retention.migrate_legacy_jsonl(legacy, directory) == manifest


def test_raw_daily_file_wins_during_atomic_gzip_transition(tmp_path):
    directory = tmp_path / "logs"
    raw = directory / "2026-01-01.jsonl"
    archive = directory / "2026-01-01.jsonl.gz"
    _write_jsonl(raw, [{"source": "raw"}])
    with gzip.open(archive, "wt", encoding="utf-8") as stream:
        stream.write(json.dumps({"source": "archive"}) + "\n")

    assert retention.daily_log_paths(directory) == [raw]
    assert retention.read_daily_jsonl(directory) == [{"source": "raw"}]


def test_voc_old_completed_runs_compress_only_sources_and_keep_reports(tmp_path, monkeypatch):
    monkeypatch.setattr(retention, "ARCHIVE_EVENT_LOG", tmp_path / "events.jsonl")
    monkeypatch.setattr(voc_retention, "PROJECT_ROOT", tmp_path)
    profile_root = tmp_path / "logs" / "voc" / "testcase" / "a"
    for index in range(7):
        run_id = f"2026010{index + 1}_120000"
        run_dir = profile_root / run_id
        source = run_dir / f"llm_judge_{run_id}.json"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(json.dumps({"run_id": run_id}), encoding="utf-8")
        report = run_dir / "report_draft" / "quality_score_report.md"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("report", encoding="utf-8")
        manifest = {
            "run_id": run_id,
            "status": "completed",
            "sources": [str(source.relative_to(tmp_path))],
            "outputs": [str(report.relative_to(tmp_path))],
        }
        (run_dir / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    archived = voc_retention.archive_old_profile_runs(profile_root)

    assert len(archived) == 2
    for index in range(2):
        run_id = f"2026010{index + 1}_120000"
        run_dir = profile_root / run_id
        assert list(run_dir.glob("llm_judge_*.json.gz"))
        assert (run_dir / "run_manifest.json").exists()
        assert (run_dir / "report_draft" / "quality_score_report.md").exists()
        manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        assert manifest["sources"][0].endswith(".json.gz")

    for index in range(2, 7):
        run_id = f"2026010{index + 1}_120000"
        assert list((profile_root / run_id).glob("llm_judge_*.json"))


def test_ai_batch_keeps_latest_five_logs_and_never_compresses_reports(tmp_path, monkeypatch):
    monkeypatch.setattr(retention, "ARCHIVE_EVENT_LOG", tmp_path / "events.jsonl")
    monkeypatch.setattr(ai_retention, "PROJECT_ROOT", tmp_path)
    log_dir = tmp_path / "logs" / "ai_agent" / "testcase"
    manifest_dir = tmp_path / "reports" / "manifests"
    report = tmp_path / "reports" / "ai_agent" / "batch" / "final_quality_report.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("latest report", encoding="utf-8")
    manifest_dir.mkdir(parents=True, exist_ok=True)
    for index in range(7):
        source = log_dir / f"ai_agent_batch_2026010{index + 1}_120000.json"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(json.dumps({"run": index}), encoding="utf-8")
        manifest = {"run_id": index, "source": str(source.relative_to(tmp_path)), "outputs": [str(report.relative_to(tmp_path))]}
        (manifest_dir / source.name).write_text(json.dumps(manifest), encoding="utf-8")

    archived = ai_retention.archive_old_batch_logs(log_dir, manifest_dir)

    assert len(archived) == 2
    assert report.read_text(encoding="utf-8") == "latest report"
    assert len(list(log_dir.glob("*.json"))) == 5
    assert len(list(log_dir.glob("*.json.gz"))) == 2
    first_manifest = json.loads(
        (manifest_dir / "ai_agent_batch_20260101_120000.json").read_text(encoding="utf-8")
    )
    assert first_manifest["source"].endswith(".json.gz")


def test_daily_writer_uses_korean_local_date(tmp_path):
    utc_time = datetime(2026, 1, 1, 15, 30, tzinfo=timezone.utc)
    path = retention.append_daily_jsonl(tmp_path, {"ok": True}, value=utc_time)

    assert path.name == "2026-01-02.jsonl"
    assert retention.read_jsonl(path) == [{"ok": True}]


def test_report_and_metric_restore_read_raw_and_compressed_daily_logs(tmp_path, monkeypatch):
    monkeypatch.setattr(retention, "ARCHIVE_EVENT_LOG", tmp_path / "events.jsonl")
    ai_dir = tmp_path / "ai"
    _write_jsonl(
        ai_dir / "2026-01-01.jsonl",
        [{"timestamp": "2026-01-01T01:00:00+00:00", "status": "error", "fault": {"type": "http_503"}}],
    )
    retention.compress_verified(ai_dir / "2026-01-01.jsonl")
    _write_jsonl(ai_dir / "2026-01-02.jsonl", [{"timestamp": "2026-01-02T01:00:00+00:00", "status": "success"}])

    assert len(ai_live_report._read_jsonl(ai_dir)) == 2
    assert ai_metrics.restore_last_activity_from_log(ai_dir) == datetime(
        2026, 1, 2, 1, tzinfo=timezone.utc
    ).timestamp()
    restored = ai_metrics.restore_service_failure_metrics_from_log(ai_dir, retries_per_failure=3)
    assert restored == {"retry": 3, "unavailable": 1, "chat_error": 1, "chat_fallback": 0}

    voc_dir = tmp_path / "voc"
    _write_jsonl(
        voc_dir / "2026-01-01.jsonl",
        [{"profile_id": "A", "finished_at": "2026-01-01T03:00:00+00:00"}],
    )
    retention.compress_verified(voc_dir / "2026-01-01.jsonl")
    latest = voc_metrics.restore_last_activity_from_logs(voc_dir)
    assert latest["A"] == datetime(2026, 1, 1, 3, tzinfo=timezone.utc).timestamp()
