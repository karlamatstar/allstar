"""실시간 대화 리포트 생성기의 오프라인 테스트입니다. OpenAI API를 호출하지 않고,
가짜 대화/채점 로그를 임시 폴더에 만들어 리포트 산출물이 정상 생성되는지 확인합니다."""
import json

import allstar.ai_agent.evaluation.live_report_generator as live_report


def _fake_evaluation(decision: str, score: int) -> dict:
    axes = {a: {"score": score, "reason": "test"} for a in live_report.AXES}
    return axes | {"total_score": score * 5, "overall_decision": decision, "summary": "테스트 요약"}


def test_generate_live_report(tmp_path, monkeypatch):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    conversations = [
        {"timestamp": "2026-07-06T01:00:00+00:00", "request_id": "req1",
         "question": "총 몇 시간인가요?", "answer": "320시간입니다.", "rule_answer": "총 320시간으로 구성.",
         "latency_ms": 1200.5, "status": "success"},
        {"timestamp": "2026-07-06T01:05:00+00:00", "request_id": "req2",
         "question": "날씨 알려줘", "answer": "확인할 수 없습니다.", "rule_answer": "날씨 정보는 확인할 수 없습니다.",
         "latency_ms": 900.0, "status": "success"},
    ]
    evaluations = [
        {"timestamp": "2026-07-06T01:00:05+00:00", "request_id": "req1", "question": "총 몇 시간인가요?",
         "model": "api", "evaluation": _fake_evaluation("PASS", 5)},
        {"timestamp": "2026-07-06T01:00:06+00:00", "request_id": "req1", "question": "총 몇 시간인가요?",
         "model": "rule", "evaluation": _fake_evaluation("REVIEW", 3)},
        # req2는 api 채점만 존재 → rule 쪽은 "미채점"으로 집계되어야 한다
        {"timestamp": "2026-07-06T01:05:05+00:00", "request_id": "req2", "question": "날씨 알려줘",
         "model": "api", "evaluation": _fake_evaluation("FAIL", 1)},
    ]
    (log_dir / "conversations.jsonl").write_text(
        "\n".join(json.dumps(c, ensure_ascii=False) for c in conversations) + "\n", encoding="utf-8")
    (log_dir / "live_evaluations.jsonl").write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in evaluations) + "\n", encoding="utf-8")

    monkeypatch.setattr(live_report, "CONVERSATIONS_LOG", log_dir / "conversations.jsonl")
    monkeypatch.setattr(live_report, "LIVE_EVAL_LOG", log_dir / "live_evaluations.jsonl")
    monkeypatch.setattr(live_report, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(live_report, "HISTORY_DIR", tmp_path / "reports" / "history")

    summary = live_report.generate_live_report(timestamp="test_run")

    assert summary["n_conversations"] == 2
    assert summary["n_rows"] == 4  # 대화 2건 × 모델 2종

    latest_md = tmp_path / "reports" / "live_report.md"
    latest_csv = tmp_path / "reports" / "live_report.csv"
    assert latest_md.exists() and latest_csv.exists()

    md = latest_md.read_text(encoding="utf-8")
    assert "실시간 대화 품질 리포트" in md
    assert "FAIL" in md and "미채점" in md

    csv_text = latest_csv.read_text(encoding="utf-8-sig")
    assert "req1" in csv_text and "req2" in csv_text


def test_generate_live_report_without_logs(tmp_path, monkeypatch):
    monkeypatch.setattr(live_report, "CONVERSATIONS_LOG", tmp_path / "none.jsonl")
    try:
        live_report.generate_live_report()
        assert False, "NoLiveLogsError가 발생해야 합니다"
    except live_report.NoLiveLogsError:
        pass
