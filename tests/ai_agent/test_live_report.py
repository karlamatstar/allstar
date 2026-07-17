"""실시간 대화 리포트 생성기의 오프라인 테스트입니다. OpenAI API를 호출하지 않고,
가짜 대화/채점 로그를 임시 폴더에 만들어 리포트 산출물이 정상 생성되는지 확인합니다."""
import json

import allstar.ai_agent.evaluation.live_report_generator as live_report
import pandas as pd


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
    monkeypatch.setattr(live_report, "ASSETS_DIR", tmp_path / "reports" / "assets")

    summary = live_report.generate_live_report(timestamp="test_run")

    assert summary["n_conversations"] == 2
    assert summary["n_rows"] == 4  # 대화 2건 × 모델 2종

    latest_md = tmp_path / "reports" / "live_report.md"
    latest_csv = tmp_path / "reports" / "live_report.csv"
    assert latest_md.exists() and latest_csv.exists()

    md = latest_md.read_text(encoding="utf-8")
    assert "실시간 대화 품질 리포트" in md
    assert "FAIL" in md and "미채점" in md
    assert "한눈에 보는 품질 현황" in md
    assert "품질·판정·응답시간 그래프" in md
    assert "<details>" in md and "최근 채팅·채점 목록 열기" in md
    assert "assets/decision_distribution.png" in md

    csv_text = latest_csv.read_text(encoding="utf-8-sig")
    assert "req1" in csv_text and "req2" in csv_text
    for chart_name in (
        "decision_distribution.png",
        "quality_axis_average.png",
        "response_latency_trend.png",
    ):
        chart = tmp_path / "reports" / "assets" / chart_name
        assert chart.exists()
        assert chart.read_bytes().startswith(b"\x89PNG")

    # 자동 갱신은 원본 로그만 누적하고 보고서 이력 사본은 매번 만들지 않는다.
    assert not (tmp_path / "reports" / "history").exists()


def test_model_stats_keeps_na_separate():
    import pandas as pd

    df = pd.DataFrame([
        {"overall_decision": "PASS", "total_score": 25, **{column: 5 for column in live_report.SCORE_COLS_MD}},
        {"overall_decision": "FAIL", "total_score": 5, **{column: 1 for column in live_report.SCORE_COLS_MD}},
        {"overall_decision": "N/A", "total_score": 0, **{column: 0 for column in live_report.SCORE_COLS_MD}},
        {"overall_decision": "미채점", "total_score": None, **{column: None for column in live_report.SCORE_COLS_MD}},
    ])

    stats = live_report._model_stats(df)

    assert stats["pass"] == 1
    assert stats["fail"] == 1
    assert stats["na"] == 1
    assert stats["not_scored"] == 1
    assert stats["pass_rate"] == 50.0
    assert stats["avg_total"] == 15.0


def test_fault_chat_is_rendered_as_na_with_error_metadata(tmp_path):
    conversations = [{
        "timestamp": "2026-07-18T01:00:00+00:00",
        "request_id": "fault-1",
        "question": "임의 질문",
        "answer": "503 오류",
        "rule_answer": "503 오류",
        "latency_ms": 15.0,
        "status": "error",
        "fault": {
            "type": "http_503",
            "http_status": 503,
            "case_id": "TC-001",
            "error_detail": "service unavailable",
        },
    }]
    na = live_report.AXES
    evaluation = {
        **{axis: {"score": None, "reason": "인프라 장애"} for axis in na},
        "total_score": None,
        "overall_decision": "N/A",
        "summary": "인프라 장애로 평가 불가",
    }
    evaluations = [
        {"request_id": "fault-1", "question": "임의 질문", "model": model, "evaluation": evaluation}
        for model in ("api", "rule")
    ]

    rows = live_report.build_rows(conversations, evaluations)
    frame = pd.DataFrame(rows)
    report_path = tmp_path / "fault_report.md"
    live_report.save_live_markdown_report(frame, report_path)

    assert len(rows) == 2
    assert all(row["overall_decision"] == "N/A" for row in rows)
    assert all(row["total_score"] is None for row in rows)
    markdown = report_path.read_text(encoding="utf-8")
    assert "장애 유형: http_503" in markdown
    assert "HTTP 상태: 503" in markdown
    assert "선택 테스트케이스: TC-001" in markdown
    assert "기술 오류: service unavailable" in markdown
    assert "종합 점수: N/A" in markdown


def test_generate_live_report_without_logs(tmp_path, monkeypatch):
    monkeypatch.setattr(live_report, "CONVERSATIONS_LOG", tmp_path / "none.jsonl")
    try:
        live_report.generate_live_report()
        assert False, "NoLiveLogsError가 발생해야 합니다"
    except live_report.NoLiveLogsError:
        pass
