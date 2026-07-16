import json

from allstar.shared.model_profiles import get_profile
from allstar.voc.api import report_generator


def test_live_report_starts_with_profile_guide_and_records_question_profile(tmp_path, monkeypatch):
    log_dir = tmp_path / "logs"
    report_dir = tmp_path / "reports"
    manifest_dir = tmp_path / "manifests"
    log_dir.mkdir()
    profile = get_profile("C")
    row = {
        "request_id": "req-1",
        "question": "배송 불만 분석",
        "profile_id": "C",
        "profile": profile.snapshot(),
        "status": "completed",
        "elapsed_seconds": 3.2,
        "result": {"answer": "배송 불만 요약과 개선안"},
        "judge": {"total": 17, "verdict": "PASS"},
    }
    (log_dir / "2026-07-16.jsonl").write_text(
        json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(report_generator, "LOG_DIR", log_dir)
    monkeypatch.setattr(report_generator, "REPORT_DIR", report_dir)
    monkeypatch.setattr(report_generator, "MANIFEST_DIR", manifest_dir)
    monkeypatch.setattr(report_generator, "ROOT", tmp_path)

    output = report_generator.generate_live_report()
    content = (report_dir / "latest" / "voc_live_report.md").read_text(encoding="utf-8")
    assert "## A~D 모델 프로필" in content
    assert "## 질문별 결과 요약" in content
    assert "사용 프로필: **C**" in content
    assert "gpt-5.6-luna" in content
    assert output["manifest"].endswith(".json")
